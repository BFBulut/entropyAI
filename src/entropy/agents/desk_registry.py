"""
Agent Desk kayıt defteri: Desk'in KENDİ ofisleri, ajanları ve projeleri.

Neden ayrı bir defter: Faz 6'ya kadar Desk, Entropy'nin `Entropy/Agents/`
ajanlarını ödünç alıyordu. Bu iki şeyi birden bozuyordu — Entropy'nin kendi
kadrosu ofis planlamasıyla kirleniyor, ofis ajanları da Entropy'nin sistem
kimliğini (ve "Entropy" adını) miras alıyordu. Artık ayrım kesin:

    <kasa>/Entropy/Desk/Offices/<ofis>/
        OFFICE.md              ofis tüzüğü + ön bilgi (workdir dâhil)
        agents/<ad>/AGENT.md   ofisin kendi ajanları (orkestratör + altlar)
        MEMORY.md, memory/     bellek katmanının alanı (bu modül yazmaz)
        projects/<proje>/PROJECT.md
        reports/, inbox/, layout.json

Kurallar (kullanıcı sözleşmesi):
- TOHUM YOK. Ofisi kullanıcı açar; açıldığı anda o ofisin `orkestrator` ajanı
  otomatik yazılır ve derlenir.
- Orkestratör kod yazmaz: araştırır, planlar, raporlar. Araç politikası
  `read-only` ve derlemeye yazma/komut yasağı kuralları düşer (bkz. compile.py).
- Ofis ajanlarının istemlerinde "Entropy" geçmez; Desk ajanları Entropy'den
  habersizdir. Bu yüzden `memory_path` gibi alanlar da ofise GÖRELİ yazılır
  (`memory/orkestrator.md`), mutlak kasa yolu değil.
- Derleme ofisin çalışma dizinine yapılır: `workdir` doluysa o (kullanıcının
  proje klasörü), boşsa ofis klasörünün kendisi.
"""

from __future__ import annotations

import datetime
import logging
import shutil
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

from entropy.agents.compile import normalize_model_text
from entropy.agents.registry import (
    AGENT_FILENAME,
    VALID_PROVIDERS,
    AgentSpec,
    default_provider,
    parse_frontmatter,
    render_frontmatter,
)

# Desk'in veri kökü. `Entropy/Offices` (Faz 3) artık okunmaz; eski kurulumlar
# `entropy.memory.office_graph.migrate_legacy_offices` ile taşınır.
DESK_SUBDIR = "Entropy/Desk/Offices"
OFFICE_FILENAME = "OFFICE.md"
AGENTS_DIRNAME = "agents"
PROJECTS_DIRNAME = "projects"
PROJECT_FILENAME = "PROJECT.md"
REPORTS_DIRNAME = "reports"
INBOX_DIRNAME = "inbox"
MEMORY_DIRNAME = "memory"
MEMORY_FILENAME = "MEMORY.md"
LAYOUT_FILENAME = "layout.json"

logger = logging.getLogger(__name__)

ORCHESTRATOR_AGENT = "orkestrator"
ORCHESTRATOR_ROLE = "orchestrator"

# Geçiş günlüğü: kasada kendiliğinden yapılan her onarım buraya yazılır
# (kart taşıması `tasks.py`, orkestratör politikası bu dosya).
MIGRATION_LOG_SUBPATH = "Entropy/Desk/_migrations.log"

DEFAULT_MAX_PARALLEL = 2
DEFAULT_BUDGET_TOKENS = 120000

# Manifest bölümü üst sınırı (karakter). ~4 karakter ≈ 1 token.
DESK_MANIFEST_CHAR_BUDGET = 520

# Orkestratörün sistem istemi. İçinde "Entropy" GEÇMEZ ve geçmemeli: ofis
# ajanları çağıran uygulamayı bilmez, yalnızca kendi ofislerini bilir.
# Şema iki bölümlüdür: `subtasks` (bu turun planı) ve isteğe bağlı `new_agents`
# (eksik uzmanlık varsa orkestratörün kendi kadrosuna eklediği ajanlar).
ORCHESTRATOR_PROMPT = (
    "Sen bu ofisin orkestratör ajanısın. İşi SEN yapmazsın; araştırır, "
    "planlar, dağıtır ve raporlarsın.\n\n"
    "Sert kurallar:\n"
    "1. Kod yazmazsın, dosya oluşturmaz/değiştirmez, komut çalıştırmazsın. "
    "Yalnızca okuma ve araştırma araçların var.\n"
    "2. Her plandan önce bilgini tazele: ofis belleğini, ofis grafını ve "
    "gerekiyorsa dış kaynakları oku; eski varsayımla plan yapma.\n"
    "3. En çok 5 alt görev üret. Her alt görev tek bir soruya yanıt versin, "
    "tek bir alt ajana atansın ve diğerlerinin çıktısını beklemesin.\n"
    "4. Kadrondaki bir ajan işi karşılamıyorsa yeni bir alt ajan tanımla; "
    "uydurma ada görev atama.\n"
    "5. Açıklama yazma; yanıtın TEK bir ```json kod bloğu olsun.\n\n"
    "Çıktı şeman:\n"
    "```json\n"
    '{"subtasks": [{"title": "...", "goal": "...", "criteria": ["..."], '
    '"agent": "<kadrondaki ad>", '
    '"provider": "<o ajanın sağlayıcısı>", "model": ""}],\n'
    ' "new_agents": [{"name": "...", "role": "worker", "description": "...", '
    '"provider": "<ofisin varsayılan sağlayıcısı>", "model": "", '
    '"tools_policy": "read-write", '
    '"prompt": "..."}]}\n'
    "```\n"
    "`new_agents` yalnızca gerçekten eksik bir uzmanlık varsa yazılır; "
    "yoksa alan hiç bulunmaz."
)

# Değerlendirici yoksa orkestratör notlar; not verme istemi de aynı dosyada
# tutulur ki ofis tek ajanla da uçtan uca kapansın.
# Not: ön bilgi düz YAML olarak yazılıyor ve değerler tırnaklanmıyor; bu yüzden
# açıklamada ": " KULLANILMAZ (Claude Code ön bilgiyi ayrıştıramıyordu).
ORCHESTRATOR_DESCRIPTION = (
    "Ofisin planlayıcısı — araştırır, işi alt görevlere böler, alt ajanları "
    "tanımlar ve sonucu raporlar. Kod yazmaz."
)


@dataclass
class DeskProject:
    """Ofis projesi: kartların bağlandığı iş kümesi (`projects/<ad>/PROJECT.md`)."""

    name: str
    office: str = ""
    goal: str = ""
    charter: str = ""
    path: Optional[Path] = None


@dataclass
class DeskOffice:
    """Tek bir Desk ofisi (`OFFICE.md` dosyasının bellek içi karşılığı)."""

    name: str
    purpose: str = ""
    orchestrator: str = ORCHESTRATOR_AGENT
    evaluator: str = ""
    members: List[str] = field(default_factory=list)
    default_provider: str = field(default_factory=default_provider)
    default_model: str = ""
    # Ofisin varsayılan efor düzeyi (low|medium|high|xhigh|max). `default_model`
    # serbest metinse ("fable 5.1 high effort") oradan ayrıştırılır.
    default_effort: str = ""
    max_parallel: int = DEFAULT_MAX_PARALLEL
    # Ofis düzeyi token tavanı. 0 = SINIRSIZ (harness `_budget`/`_can_afford`
    # sıfırı zaten "tavan yok" olarak okuyor).
    budget_tokens: int = DEFAULT_BUDGET_TOKENS
    # Ofisin çalışma dizini: kullanıcının proje klasörü. Boşsa ofis klasörü.
    workdir: str = ""
    charter: str = ""
    path: Optional[Path] = None
    updated_at: str = ""

    def to_frontmatter(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "orchestrator": self.orchestrator or ORCHESTRATOR_AGENT,
            "evaluator": self.evaluator,
            "members": list(self.members or []),
            "default_provider": self.default_provider or default_provider(),
            "default_model": self.default_model,
            "default_effort": self.default_effort,
            "max_parallel": self.max_parallel,
            "budget_tokens": self.budget_tokens,
            "workdir": self.workdir,
        }

    def roster(self) -> List[str]:
        """Ofiste görevi olan tüm ajanlar (yinelenmeden, sıralı)."""
        out: List[str] = []
        for name in [self.orchestrator, self.evaluator, *(self.members or [])]:
            if name and name not in out:
                out.append(name)
        return out


class OfficeAgents:
    """
    Tek bir ofisin ajan defteri.

    `AgentRegistry` ile aynı yüzeyi (list/get/create/update/delete) sunar; ofis
    harness'ı ve Desk panelleri ikisini de aynı biçimde kullanabilsin diye.
    Fark: dosyalar `Entropy/Agents` altında değil, ofisin kendi `agents/`
    klasöründe durur ve her yazımdan sonra ofis çalışma dizinine derlenir.
    """

    def __init__(self, desk: "DeskRegistry", office: str):
        self.desk = desk
        self.office = office

    # -- yollar --------------------------------------------------------

    @property
    def agents_dir(self) -> Path:
        return self.desk.agents_dir(self.office)

    def agent_dir(self, name: str) -> Path:
        return self.agents_dir / name

    def agent_file(self, name: str) -> Path:
        return self.agent_dir(name) / AGENT_FILENAME

    # -- okuma ---------------------------------------------------------

    def list(self) -> List[AgentSpec]:
        specs: List[AgentSpec] = []
        try:
            if not self.agents_dir.is_dir():
                return specs
            for child in sorted(self.agents_dir.iterdir()):
                if not child.is_dir():
                    continue
                spec = self._read(child / AGENT_FILENAME)
                if spec is not None:
                    specs.append(spec)
        except OSError:
            return specs
        return specs

    def get(self, name: str) -> Optional[AgentSpec]:
        return self._read(self.agent_file(name)) if name else None

    def _read(self, path: Path) -> Optional[AgentSpec]:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        name = str(front.get("name") or path.parent.name).strip()
        if not name:
            return None
        skills = front.get("skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        provider = str(front.get("provider") or default_provider()).strip().lower()
        models: Dict[str, str] = {}
        nested = front.get("models")
        if isinstance(nested, dict):
            for key, value in nested.items():
                key = str(key).strip().lower()
                if key in VALID_PROVIDERS and value:
                    models[key] = str(value)
        for provider_name in VALID_PROVIDERS:
            value = front.get(f"model_{provider_name}")
            if value:
                models[provider_name] = str(value)
        try:
            updated = datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            updated = ""
        return AgentSpec(
            name=name,
            role=str(front.get("role") or ""),
            description=str(front.get("description") or ""),
            provider=provider if provider in VALID_PROVIDERS else default_provider(),
            model=str(front.get("model") or ""),
            effort=str(front.get("effort") or ""),
            skills=[str(s) for s in skills],
            tools_policy=str(front.get("tools_policy") or ""),
            memory_path=str(front.get("memory_path") or ""),
            prompt=body,
            path=path,
            updated_at=updated,
            office=self.office,
            models=models,
        )

    # -- yazma ---------------------------------------------------------

    def create(self, spec: AgentSpec) -> AgentSpec:
        if self.agent_file(spec.name).exists():
            raise FileExistsError(f"'{spec.name}' adında bir ajan bu ofiste zaten var.")
        return self._write(spec)

    def update(self, spec: AgentSpec) -> AgentSpec:
        return self._write(spec)

    def _write(self, spec: AgentSpec) -> AgentSpec:
        if not (spec.name or "").strip():
            raise ValueError("Ajan adı boş olamaz.")
        spec = replace(spec, office=self.office)
        path = self.agent_file(spec.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (spec.prompt or "").strip()
        if not body.startswith("#"):
            body = f"# {spec.name}\n\n{body}".strip()
        content = f"{render_frontmatter(spec.to_frontmatter())}\n\n{body}\n"
        path.write_text(content, encoding="utf-8")
        spec = replace(spec, path=path)
        self.desk.compile_agent(self.office, spec)
        self.desk._notify_agents(spec.name)
        return spec

    def delete(self, name: str) -> bool:
        target = self.agent_dir(name)
        if not target.is_dir():
            return False
        shutil.rmtree(target, ignore_errors=True)
        # Derlenmiş kopyalar da gider; aksi hâlde silinen ajan sağlayıcıya
        # görünmeye devam ediyor ve orkestratör ona görev atayabiliyordu.
        root = self.desk.workdir(self.office)
        for stale in (root / ".agents" / "agents" / name,):
            shutil.rmtree(stale, ignore_errors=True)
        try:
            (root / ".claude" / "agents" / f"{name}.md").unlink()
        except OSError:
            pass
        self.desk._notify_agents(name)
        return not target.exists()


class DeskRegistry:
    """
    Desk ofislerinin CRUD'u. Durum tutmaz; her okuma diski görür.

    `AgentRegistry`/eski `OfficeRegistry` ile aynı ilke: dosyaları kullanıcı da
    (Obsidian) uygulama da yazabildiği için bellek içi önbellek bayatlıyordu.
    """

    def __init__(self, vault_path: Optional[Path | str] = None):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.offices_dir = self.vault_path / DESK_SUBDIR
        self._migrate_orchestrator_policies_once()

    # -- yollar --------------------------------------------------------

    def office_dir(self, name: str) -> Path:
        return self.offices_dir / name

    def office_file(self, name: str) -> Path:
        return self.office_dir(name) / OFFICE_FILENAME

    def agents_dir(self, name: str) -> Path:
        return self.office_dir(name) / AGENTS_DIRNAME

    def projects_dir(self, name: str) -> Path:
        return self.office_dir(name) / PROJECTS_DIRNAME

    def reports_dir(self, name: str) -> Path:
        return self.office_dir(name) / REPORTS_DIRNAME

    def inbox_dir(self, name: str) -> Path:
        return self.office_dir(name) / INBOX_DIRNAME

    def memory_dir(self, name: str) -> Path:
        return self.office_dir(name) / MEMORY_DIRNAME

    def layout_file(self, name: str) -> Path:
        return self.office_dir(name) / LAYOUT_FILENAME

    def workdir(self, name: str) -> Path:
        """
        Ofis ajanlarının derleneceği/koşacağı kök.

        `OFFICE.md`'deki `workdir` (kullanıcının proje klasörü) varsa o; yoksa
        ofis klasörünün kendisi. Var olmayan bir yol ofis klasörüne düşer:
        sağlayıcı olmayan bir cwd'de hiç başlamıyordu.
        """
        spec = self.get(name)
        raw = (spec.workdir if spec else "") or ""
        if raw:
            try:
                candidate = Path(raw).expanduser()
                if candidate.is_dir():
                    return candidate
            except Exception:
                pass
        return self.office_dir(name)

    def agents(self, name: str) -> OfficeAgents:
        """Ofisin ajan defteri (harness ve paneller bunu kullanır)."""
        return OfficeAgents(self, name)

    # -- okuma ---------------------------------------------------------

    def list(self) -> List[DeskOffice]:
        specs: List[DeskOffice] = []
        try:
            if not self.offices_dir.is_dir():
                return specs
            for child in sorted(self.offices_dir.iterdir()):
                if not child.is_dir():
                    continue
                spec = self._read(child / OFFICE_FILENAME)
                if spec is not None:
                    specs.append(spec)
        except OSError:
            return specs
        return specs

    def get(self, name: str) -> Optional[DeskOffice]:
        return self._read(self.office_file(name)) if name else None

    @staticmethod
    def _int(value, fallback: int, allow_zero: bool = False) -> int:
        """
        Ön bilgideki tamsayı; geçersizse varsayılan.

        `allow_zero=True` yalnızca `budget_tokens` için: 0 SINIRSIZ demektir ve
        varsayılana düşürülmemelidir. Eskiden `budget_tokens: 0` yazan ofis
        sessizce 120k tavana geri dönüyordu ve kullanıcı sınırsız istediğini
        sanıyordu. Negatif değer yine varsayılana düşer (anlamı yok).
        """
        try:
            out = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        if out == 0:
            return 0 if allow_zero else fallback
        return out if out > 0 else fallback

    def _read(self, path: Path) -> Optional[DeskOffice]:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        name = str(front.get("name") or path.parent.name).strip()
        if not name:
            return None
        provider = str(front.get("default_provider") or default_provider()).strip().lower()
        try:
            updated = datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            updated = ""
        # `default_model` kullanıcı tarafından elle yazılıyor ve serbest metin
        # olabiliyor ("fable 5.1 high effort"). Bu dizge doğrudan `--model`e
        # geçince CLI `unrecognized_model` ile ölüyordu; okuma sırasında
        # sağlayıcıya göre normalize edilir ve efor sözcüğü ayrıştırılıp
        # `default_effort` alanına düşer (ön bilgideki açık efor önceliklidir).
        office_provider = provider if provider in VALID_PROVIDERS else default_provider()
        raw_model = str(front.get("default_model") or "")
        raw_effort = str(front.get("default_effort") or "").strip().lower()
        model, parsed_effort = normalize_model_text(raw_model, office_provider)
        spec = DeskOffice(
            name=name,
            purpose=str(front.get("purpose") or ""),
            orchestrator=str(front.get("orchestrator") or ORCHESTRATOR_AGENT),
            evaluator=str(front.get("evaluator") or ""),
            default_provider=office_provider,
            default_model=model,
            default_effort=raw_effort or (parsed_effort or ""),
            max_parallel=self._int(front.get("max_parallel"), DEFAULT_MAX_PARALLEL),
            budget_tokens=self._int(front.get("budget_tokens"), DEFAULT_BUDGET_TOKENS,
                                    allow_zero=True),
            workdir=str(front.get("workdir") or ""),
            charter=body,
            path=path,
            updated_at=updated,
        )
        # Üyeler ön bilgiden DEĞİL, ajan klasöründen türetilir: orkestratör
        # planlama sırasında yeni alt ajan yazabiliyor ve ön bilgiyi ayrıca
        # güncellemek iki kaynaklı bir gerçeklik yaratırdı.
        members: List[str] = []
        evaluator = spec.evaluator
        for agent in OfficeAgents(self, name).list():
            role = agent.office_role
            if agent.name == spec.orchestrator or role == ORCHESTRATOR_ROLE:
                continue
            if role == "evaluator":
                evaluator = evaluator or agent.name
                continue
            members.append(agent.name)
        return replace(spec, members=members, evaluator=evaluator)

    # -- yazma ---------------------------------------------------------

    def create(self, spec: DeskOffice) -> DeskOffice:
        """
        Ofisi ve iskeletini yazar, ardından ORKESTRATÖRÜ otomatik oluşturur.

        Tohum ofis yoktur; ofis kullanıcı isteğiyle doğar. Ama orkestratörsüz
        ofis işlevsizdir (planlama çağrısı yapacak kimse yok), bu yüzden ofisin
        doğumu ile orkestratörünkü tek işlemdir.
        """
        if self.office_file(spec.name).exists():
            raise FileExistsError(f"'{spec.name}' adında bir ofis zaten var.")
        requested_members = list(spec.members or [])
        spec = self._write(spec)
        self.ensure_orchestrator(spec.name)
        # Faz 7 (QA): `members` alanı yalnızca bir DİLEK listesidir. Ofisin
        # gerçek kadrosu `agents/` altındaki tanım dosyalarından okunur
        # (bkz. `_read`), bu yüzden tanımsız bir üye adı sessizce kayboluyordu.
        # Alan kaldırılmıyor (kullanıcı niyetini taşıyor) ama uyarı veriliyor;
        # üyeyi gerçekten kadroya almak için `create_member` kullanılmalı.
        missing = [n for n in requested_members if self.agents(spec.name).get(n) is None]
        if missing:
            logger.warning(
                "Ofis '%s': tanım dosyası olmayan üye adları kadroya alınmadı: %s "
                "(create_member ile tanımlayın).",
                spec.name, ", ".join(missing),
            )
        return self.get(spec.name) or spec

    def create_member(
        self,
        office_name: str,
        name: str,
        role: str = "worker",
        description: str = "",
        provider: str = "",
        model: str = "",
        tools_policy: str = "read-write",
        prompt: str = "",
    ) -> Optional[AgentSpec]:
        """
        Ofise gerçek bir üye ekler (`agents/<ad>/AGENT.md` yazar ve derler).

        Ofis üyeliği DOSYAYLA tanımlıdır: `members` ön bilgisine ad yazmak üye
        yaratmaz. `/desk agent add` ve orkestratörün `new_agents` bölümü aynı
        yoldan geçer. Var olan üye EZİLMEZ; mevcut tanım döner.
        """
        name = (name or "").strip()
        if not name:
            raise ValueError("Üye adı boş olamaz.")
        office = self.get(office_name)
        if office is None:
            return None
        agents = self.agents(office_name)
        existing = agents.get(name)
        if existing is not None:
            return existing
        role = (role or "worker").strip().lower()
        if role == ORCHESTRATOR_ROLE:
            # Ofisin tek orkestratörü vardır ve o `ensure_orchestrator` ile doğar.
            role = "worker"
        provider = (provider or office.default_provider or default_provider()).strip().lower()
        if provider not in VALID_PROVIDERS:
            provider = default_provider()
        return agents.update(AgentSpec(
            name=name,
            role=role,
            description=description or f"{office_name} ofisi üyesi",
            provider=provider,
            model=model or office.default_model or "",
            effort=office.default_effort or "",
            tools_policy=(tools_policy or "read-write").strip().lower(),
            memory_path=f"memory/{name}.md",
            prompt=prompt,
            office=office_name,
        ))

    def update(self, spec: DeskOffice) -> DeskOffice:
        return self._write(spec)

    def _write(self, spec: DeskOffice) -> DeskOffice:
        if not (spec.name or "").strip():
            raise ValueError("Ofis adı boş olamaz.")
        path = self.office_file(spec.name)
        for folder in (
            self.agents_dir(spec.name),
            self.projects_dir(spec.name),
            self.reports_dir(spec.name),
            self.inbox_dir(spec.name),
            self.memory_dir(spec.name),
        ):
            folder.mkdir(parents=True, exist_ok=True)
        body = (spec.charter or "").strip()
        if not body.startswith("#"):
            body = f"# {spec.name}\n\n{body}".strip()
        content = f"{render_frontmatter(spec.to_frontmatter())}\n\n{body}\n"
        path.write_text(content, encoding="utf-8")
        self._notify(spec.name)
        return replace(spec, path=path)

    def delete(self, name: str) -> bool:
        target = self.office_dir(name)
        if not target.is_dir():
            return False
        shutil.rmtree(target, ignore_errors=True)
        # Ofis gidince süren sağlayıcı konuşması da düşer: eşlemede kalan kimlik
        # aynı adla açılan YENİ bir ofisi eski ofisin bağlamına bağlardı.
        try:
            from entropy.core.identity import conversation_map

            conversation_map.forget(f"office:{name}")
        except Exception:
            pass
        self._notify(name)
        return not target.exists()

    # -- geçişler --------------------------------------------------------

    # Kasa başına tek kez: her `DeskRegistry()` kurulumunda tüm ofisleri okumak
    # pahalı ve gereksiz; geçiş zaten idempotent.
    _policy_migrated_vaults: set = set()
    _policy_lock = threading.Lock()

    def _migrate_orchestrator_policies_once(self) -> None:
        key = str(self.vault_path)
        with DeskRegistry._policy_lock:
            if key in DeskRegistry._policy_migrated_vaults:
                return
            DeskRegistry._policy_migrated_vaults.add(key)
        try:
            self.migrate_orchestrator_policies()
        except Exception:
            logger.warning("Orkestratör araç politikası geçişi yapılamadı.", exc_info=True)

    def migrate_orchestrator_policies(self) -> List[str]:
        """
        Kayıtlı ofislerin orkestratörlerini `read-only` politikaya çeker.

        Neden: sözleşme "orkestratör kod yazmaz" diyor ama kasadaki eski/elle
        yazılmış tanımlarda (canlı ofiste `Alfa`: `tools_policy: full`) politika
        yazma araçlarını açıyordu. Claude derlemesi rolü görünce araç listesini
        zaten kısıyor; agy tarafında ise KAYNAK politika okunuyor, yani yasak
        sağlayıcıya göre değişiyordu. Kaynak dosya tek gerçek olsun diye AGENT.md
        güncellenir, derlenmiş kopyalar yeniden üretilir ve
        `Entropy/Desk/_migrations.log`'a satır düşer. İdempotent: politika zaten
        `read-only` ise dosyaya dokunulmaz.
        """
        changed: List[str] = []
        entries: List[str] = []
        for office in self.list():
            name = office.orchestrator or ORCHESTRATOR_AGENT
            agents = self.agents(office.name)
            spec = agents.get(name)
            if spec is None:
                continue
            policy = (spec.tools_policy or "").strip().lower()
            if policy == "read-only":
                continue
            try:
                agents.update(replace(spec, tools_policy="read-only"))
            except Exception as exc:
                entries.append(f"hata\torkestratör-politika\t{office.name}\t{name}\t{exc}")
                continue
            changed.append(f"{office.name}/{name}")
            entries.append(
                f"orkestratör-politika\t{office.name}\t{name}\t{policy or '-'}\tread-only"
            )
        if entries:
            self._append_migration_log(entries)
        if changed:
            logger.info("Orkestratör politikası normalize edildi: %s", ", ".join(changed))
        return changed

    def _append_migration_log(self, entries: List[str]) -> None:
        path = self.vault_path / MIGRATION_LOG_SUBPATH
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for row in entries:
                    fh.write(f"{stamp}\t{row}\n")
        except OSError:
            logger.warning("Geçiş günlüğü yazılamadı: %s", path)

    # -- orkestratör ----------------------------------------------------

    def orchestrator_spec(self, office: DeskOffice) -> AgentSpec:
        """
        Ofisin varsayılan orkestratör tanımı.

        `tools_policy="read-only"` sözleşmenin kendisi: derleme bunu Claude
        tarafında `tools: Read, Glob, Grep, WebFetch, WebSearch` listesine,
        agy tarafında yazma/komut yasağı kurallarına çevirir (compile.py).
        `memory_path` ofise göreli — mutlak kasa yolu prompt'a "Entropy" dizgesi
        sızdırırdı.
        """
        name = office.orchestrator or ORCHESTRATOR_AGENT
        return AgentSpec(
            name=name,
            role=ORCHESTRATOR_ROLE,
            description=ORCHESTRATOR_DESCRIPTION,
            provider=office.default_provider or default_provider(),
            model=office.default_model or "",
            # Ofis eforu (OFFICE.md'deki serbest metinden ayrıştırılmış olabilir)
            # orkestratöre miras kalır; yoksa "medium".
            effort=office.default_effort or "medium",
            tools_policy="read-only",
            memory_path=f"{MEMORY_DIRNAME}/{name}.md",
            prompt=ORCHESTRATOR_PROMPT,
            office=office.name,
        )

    def ensure_orchestrator(self, office_name: str) -> Optional[AgentSpec]:
        """Orkestratör yoksa yazar ve derler; varsa dokunmaz."""
        office = self.get(office_name)
        if office is None:
            return None
        agents = self.agents(office_name)
        existing = agents.get(office.orchestrator or ORCHESTRATOR_AGENT)
        if existing is not None:
            return existing
        return agents.update(self.orchestrator_spec(office))

    # -- projeler -------------------------------------------------------

    def list_projects(self, office_name: str) -> List[DeskProject]:
        out: List[DeskProject] = []
        base = self.projects_dir(office_name)
        try:
            if not base.is_dir():
                return out
            for child in sorted(base.iterdir()):
                if not child.is_dir():
                    continue
                project = self.get_project(office_name, child.name)
                if project is not None:
                    out.append(project)
        except OSError:
            return out
        return out

    def get_project(self, office_name: str, project: str) -> Optional[DeskProject]:
        path = self.projects_dir(office_name) / project / PROJECT_FILENAME
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        return DeskProject(
            name=str(front.get("name") or project),
            office=office_name,
            goal=str(front.get("goal") or ""),
            charter=body,
            path=path,
        )

    def create_project(self, office_name: str, project: DeskProject) -> DeskProject:
        if not (project.name or "").strip():
            raise ValueError("Proje adı boş olamaz.")
        path = self.projects_dir(office_name) / project.name / PROJECT_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (project.charter or "").strip()
        if not body.startswith("#"):
            body = f"# {project.name}\n\n{body}".strip()
        front = {"name": project.name, "office": office_name, "goal": project.goal}
        path.write_text(f"{render_frontmatter(front)}\n\n{body}\n", encoding="utf-8")
        self._notify(office_name)
        return replace(project, office=office_name, path=path)

    # -- derleme --------------------------------------------------------

    def compile_agent(self, office_name: str, spec: AgentSpec) -> Dict[str, Path]:
        """Tek ajanı ofis çalışma dizinine derler."""
        from entropy.agents.compile import compile_agent_to

        return compile_agent_to(spec, self.workdir(office_name))

    def compile_office(self, office_name: str) -> Dict[str, Dict[str, Path]]:
        """Ofisin tüm ajanlarını derler: {ajan: {sağlayıcı: yol}}."""
        out: Dict[str, Dict[str, Path]] = {}
        for spec in self.agents(office_name).list():
            try:
                out[spec.name] = self.compile_agent(office_name, spec)
            except Exception:
                continue
        return out

    def compile_all(self) -> Dict[str, Dict[str, Dict[str, Path]]]:
        return {office.name: self.compile_office(office.name) for office in self.list()}

    # -- olaylar --------------------------------------------------------

    @staticmethod
    def _notify(name: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.offices_updated.emit(name)
        except Exception:
            pass

    @staticmethod
    def _notify_agents(name: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.agents_updated.emit(name)
        except Exception:
            pass


class DeskAgentsView:
    """
    Tüm Desk ofislerinin ajanlarını tek listede gösteren salt-okunur görünüm.

    Desk panelleri (roster, ofis düzenleme) ajan adı seçtirirken Entropy'nin
    `Entropy/Agents` kadrosunu GÖREMEZ; bu görünüm o kadroyu değil, yalnızca
    ofislerin kendi ajanlarını döndürür.
    """

    def __init__(self, desk: Optional[DeskRegistry] = None):
        self.desk = desk or DeskRegistry()

    def list(self) -> List[AgentSpec]:
        out: List[AgentSpec] = []
        for office in self.desk.list():
            out.extend(self.desk.agents(office.name).list())
        return out

    def get(self, name: str) -> Optional[AgentSpec]:
        for spec in self.list():
            if spec.name == name:
                return spec
        return None

    # Yazma yolları ajanın KENDİ ofisine yönlendirilir. Panel (AgentsWidget)
    # `create/update/delete` çağırıyor; bunlar olmadan Desk'in kadro panelinde
    # düzenleme sessizce AttributeError'a düşüyordu.
    def _office_of(self, spec: AgentSpec) -> Optional[str]:
        office = (getattr(spec, "office", "") or "").strip()
        if office:
            return office
        existing = self.get(spec.name)
        return (existing.office or None) if existing is not None else None

    def create(self, spec: AgentSpec) -> AgentSpec:
        office = self._office_of(spec)
        if not office:
            raise ValueError("Ofis ajanı bir ofise bağlı olmalı (`office` alanı boş).")
        return self.desk.agents(office).create(spec)

    def update(self, spec: AgentSpec) -> AgentSpec:
        office = self._office_of(spec)
        if not office:
            raise ValueError("Ofis ajanı bir ofise bağlı olmalı (`office` alanı boş).")
        return self.desk.agents(office).update(spec)

    def delete(self, name: str) -> bool:
        spec = self.get(name)
        if spec is None or not spec.office:
            return False
        return self.desk.agents(spec.office).delete(name)


# ---------------------------------------------------------------------------
# Manifest bölümü
# ---------------------------------------------------------------------------


def desk_roster(desk: Optional[DeskRegistry] = None) -> List[Dict[str, object]]:
    """
    Ofis/orkestratör listesi (bellek ajanının `desk_roster()` sözleşmesi).

    Bellek katmanı kendi (graf destekli) sürümünü sağlıyorsa `desk_manifest`
    onu tercih eder; bu işlev güvenli geri düşüştür ve `entropy.memory`
    kurulmamışken de manifestin dolu kalmasını sağlar.
    """
    try:
        desk = desk or DeskRegistry()
        specs = desk.list()
    except Exception:
        return []
    return [
        {
            "office": spec.name,
            "orchestrator": spec.orchestrator or ORCHESTRATOR_AGENT,
            "purpose": spec.purpose,
            "agents": len(spec.members or []),
        }
        for spec in specs
    ]


def _roster_rows() -> List[Dict[str, object]]:
    """Önce bellek ajanının `desk_roster()`ı (koruma altında), sonra yerel."""
    try:
        from entropy.memory.office_graph import desk_roster as memory_roster  # type: ignore
    except Exception:
        memory_roster = None  # type: ignore
    if memory_roster is not None:
        try:
            rows = memory_roster()
            if isinstance(rows, list) and rows:
                return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
    return desk_roster()


def is_seed_leftover(office, desk: Optional[DeskRegistry] = None) -> bool:
    """
    Bu ofis eski bir build tohumundan mı kalmış (Ek-2, Faz 9)?

    TEK ölçüt `OFFICE.md` ön bilgisindeki `seed: true`. Ad tabanlı sezgi
    (`KNOWN_SEED_OFFICES`) kaldırıldı: kullanıcının kendi açtığı "Araştırma
    Ofisi" o listedeki adla eşleşiyor ve `/desk` çıktısında canlı ofis "eski
    tohum" diye işaretleniyordu. Bir ofisin tohum olduğunu yalnızca onu YAZAN
    taraf bilebilir, adı bilemez. SİLME YOK — kural yalnızca işaretlemek için;
    kullanıcının kendi açtığı ofisle eski tohumu ayırt edebilmesi gerekiyor,
    ama bir ofisi otomatik silmek geri alınamaz bir karardı (arşivleme QA'nın
    işi). `find_ghost_offices` bilerek genişletilmedi: o bellek katmanının
    dosyası ve "hayalet" kavramı (kaydı olmayan klasör) bundan başkadır.
    """
    name = getattr(office, "name", office)
    name = str(name or "").strip()
    if not name:
        return False
    desk = desk if desk is not None else DeskRegistry()
    try:
        text = desk.office_file(name).read_text(encoding="utf-8")
    except OSError:
        return False
    front, _ = parse_frontmatter(text)
    return str(front.get("seed") or "").strip().lower() in ("true", "1", "evet", "yes")


def desk_manifest(desk: Optional[DeskRegistry] = None) -> str:
    """
    Prompt'a enjekte edilen "Ofisler" bölümü (≤ ~130 token).

    Entropy TÜM orkestratörleri bilir: hangi ofis var, orkestratörü kim ve o
    ofise nasıl iş verilir. Ters yön geçerli değil — ofis ajanları Entropy'yi
    bilmez (bkz. ORCHESTRATOR_PROMPT).
    """
    rows = _roster_rows() if desk is None else [
        {
            "office": s.name,
            "orchestrator": s.orchestrator or ORCHESTRATOR_AGENT,
            "purpose": s.purpose,
        }
        for s in desk.list()
    ]
    if not rows:
        return ""
    lines = ["[OFİSLER]"]
    for row in rows:
        name = str(row.get("office") or row.get("name") or "").strip()
        if not name:
            continue
        purpose = " ".join(str(row.get("purpose") or "").split())
        if len(purpose) > 60:
            purpose = purpose[:57] + "..."
        orchestrator = str(row.get("orchestrator") or "-")
        line = f"- 🏢 {name} · {purpose or '-'} · orkestratör: {orchestrator}"
        if len("\n".join(lines)) + len(line) > DESK_MANIFEST_CHAR_BUDGET:
            lines.append("- … (tam liste için /desk)")
            break
        lines.append(line)
    if len(lines) == 1:
        return ""
    lines.append(
        "KURAL: Bir ofise iş vermek için `/desk task <ofis> <başlık> :: <hedef>`, "
        "soru sormak için `/ask <ofis> <soru>` kullan."
    )
    return "\n".join(lines)
