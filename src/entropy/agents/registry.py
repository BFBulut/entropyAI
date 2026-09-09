"""
Ajan kayıt defteri: kasadaki AGENT.md dosyaları tek kaynak.

Neden kasada, uygulama içinde değil: kullanıcı ajanlarını Obsidian'da (ya da
herhangi bir metin düzenleyicide) yazabilmeli, sürümleyebilmeli ve Entropy'nin
kendisi de bir dosya yazarak yeni ajan tanımlayabilmeli. Uygulama içi bir JSON
deposu bu üç yolu da kapatırdı.

Dosya biçimi YAML ön bilgi + markdown gövde:

    ---
    name: arastirmaci
    role: research
    description: Web ve kasa araştırması yapar, kaynaklı özet çıkarır.
    provider: agy
    model: gemini-3.8-flash-high
    effort: medium
    skills: [research, media]
    tools_policy: read-only
    memory_path: Entropy/AgentMemory/arastirmaci.md
    ---
    # arastirmaci
    <ajan gövdesi: rol yönergesi, çalışma biçimi, çıktı sözleşmesi>

Gövde doğrudan sağlayıcıya derlenen sistem istemidir (bkz. compile.py); görev
kartı çalıştırılırken de prompt'un başına konur (bkz. tasks.py).

Ayrıştırma sağlam: PyYAML varsa o, yoksa yerleşik basit ayrıştırıcı kullanılır.
PyYAML isteğe bağlı bir bağımlılık (pyproject: extras) ve paketlenmiş exe'de
bulunmayabiliyor; ajan katmanı onsuz da çalışmak zorunda.
"""

from __future__ import annotations

import datetime
import re
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

from entropy.core import paths as _paths

# Kasa içindeki göreli konumlar. Tek yerde durur: hem izleyici hem görev kartları
# hem de manifest'e yazılan "şuraya dosya koy" yönergesi buradan okur.
AGENTS_SUBDIR = "Entropy/Agents"

# Desk'in kasa kökü. Burada yalnızca DIŞLAMA için var: Entropy'nin ajan listesi
# `Entropy/Desk/**` altındaki hiçbir tanımı içeremez (Ek-1, Faz 9). Gerçek Desk
# yolları `entropy.agents.desk_registry` içinde tanımlı; buraya import etmek
# döngüsel bağımlılık olurdu.
DESK_ROOT_SUBDIR = _paths.DESK_ROOT_SUBDIR
LEGACY_DESK_ROOT_SUBDIRS = _paths.LEGACY_DESK_ROOT_SUBDIRS

# Hangi tohum tanımların bir kez yazıldığını tutan işaret dosyası. Ajanlar ve
# ofisler aynı deseni kullanır (her biri kendi klasöründe).
SEED_MARKER_FILENAME = ".seeded.json"


def _seed_missing(marker_path, defaults, existing, write) -> List[str]:
    """
    Ad bazında eksik tohumları yazar; yazılan adları döndürür.

    Kural: bir tohum adı ya diskte VARSA ya da işaret dosyasında "bir kez
    yazılmış" diye geçiyorsa atlanır. Böylece (a) sürümle gelen yeni tohumlar
    mevcut kasaya düşer, (b) kullanıcının sildiği tohum geri dirilmez.

    İşaret dosyası hiç yoksa (bu sürümden önce kurulmuş kasa) o ana kadarki
    tohumlar "görülmemiş" sayılır: eksik olanlar bir kez yazılır ve dosya
    oluşur. Bunun bilinen bedeli, bu sürümden ÖNCE silinmiş bir tohum ajanın
    tek seferliğine geri gelmesidir; alternatifi yeni rollerin hiç gelmemesiydi.
    """
    import json as _json

    seen: set = set()
    try:
        raw = _json.loads(Path(marker_path).read_text(encoding="utf-8"))
        seen = {str(n) for n in (raw.get("seeded") or [])}
    except Exception:
        seen = set()

    created: List[str] = []
    for spec in defaults:
        if spec.name in seen or spec.name in existing:
            continue
        try:
            write(spec)
            created.append(spec.name)
        except Exception:
            continue

    try:
        marker = Path(marker_path)
        marker.parent.mkdir(parents=True, exist_ok=True)
        merged = sorted(seen | {s.name for s in defaults})
        marker.write_text(
            _json.dumps({"seeded": merged}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return created
AGENT_FILENAME = "AGENT.md"

VALID_PROVIDERS = ("agy", "claude")

# Sabit "agy" varsayılanı yerine tek kaynak (Faz 9 / B-9.5). Kullanıcı yalnızca
# Claude aboneliğiyle çalışmak istediğinde yeni ofis/ajan/kart varsayılanları da
# Claude olmalı; eskiden 14+ noktada sabit "agy" yazıyordu ve sistem sessizce
# agy'ye düşüyordu.
_PROVIDER_FALLBACK = "agy"


def default_provider() -> str:
    """Yapılandırmadaki varsayılan sağlayıcı; okunamazsa `agy`."""
    value = ""
    try:
        from entropy.core.config import config

        getter = getattr(config, "default_provider", None)
        value = getter() if callable(getter) else getattr(config, "provider", "")
    except Exception:
        value = ""
    value = str(value or "").strip().lower()
    return value if value in VALID_PROVIDERS else _PROVIDER_FALLBACK

# Ofis içindeki görev tipi. `role` alanı serbest metin olarak kaldı (mevcut
# ajanlarda "research", "report writing" gibi açıklayıcı değerler var ve onları
# tek kelimeye indirmek kullanıcının yazdığı dosyaları bozardı); bu üç değer
# ayrıca tanınır ve `AgentSpec.office_role` ile normalleştirilir.
OFFICE_ROLES = ("worker", "orchestrator", "evaluator")

# Manifest bölümü için üst sınır (karakter). ~4 karakter ≈ 1 token olduğundan
# 600 karakter ≈ 150 token; sözleşmedeki bütçe budur. Bölüm her turda enjekte
# edildiği için sınır sert: ajan sayısı artarsa liste kesilir, bütçe aşılmaz.
MANIFEST_CHAR_BUDGET = 600


@dataclass
class AgentSpec:
    """Tek bir ajan tanımı (kaynak dosyanın bellek içi karşılığı)."""

    name: str
    role: str = ""
    description: str = ""
    provider: str = field(default_factory=default_provider)
    model: str = ""
    effort: str = ""
    skills: List[str] = field(default_factory=list)
    tools_policy: str = ""
    memory_path: str = ""
    prompt: str = ""
    path: Optional[Path] = None
    updated_at: str = ""
    # Ajanın bağlı olduğu ofis ("" = serbest ajan). Ofis üyeliği ofis dosyasında
    # da yazılı; buradaki alan ters yönde arama (bu ajan hangi ofiste) içindir.
    office: str = ""
    # Sağlayıcı başına model geçersiz kılma: {"agy": ..., "claude": ...}.
    # Boşsa derleme `model` alanından eşleme yapar (bkz. compile.py). Gerekli
    # oldu çünkü tek `model` alanı Claude derlemesine Gemini adı taşıyordu.
    models: Dict[str, str] = field(default_factory=dict)

    @property
    def office_role(self) -> str:
        """`role` alanının ofis görevine indirgenmiş hâli (bilinmeyen → worker)."""
        low = (self.role or "").strip().lower()
        return low if low in OFFICE_ROLES else "worker"

    def model_for(self, provider: str) -> str:
        """Sağlayıcıya özel model adı; tanımlı değilse genel `model`."""
        return str((self.models or {}).get((provider or "").strip().lower()) or "")

    def to_frontmatter(self) -> Dict[str, object]:
        """Diske yazılacak ön bilgi sözlüğü (gövde hariç)."""
        data: Dict[str, object] = {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "provider": self.provider if self.provider in VALID_PROVIDERS else default_provider(),
            "model": self.model,
            "effort": self.effort,
            "skills": list(self.skills or []),
            "tools_policy": self.tools_policy,
            "memory_path": self.memory_path,
            "office": self.office,
        }
        # Çift model yalnızca tanımlıysa yazılır: her ajana boş bir eşleme
        # eklemek kasadaki dosyaları gereksiz yere kalabalıklaştırırdı.
        for provider in VALID_PROVIDERS:
            value = (self.models or {}).get(provider)
            if value:
                data[f"model_{provider}"] = value
        return data


# ---------------------------------------------------------------------------
# Ön bilgi ayrıştırma / üretme
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _parse_simple_yaml(text: str) -> Dict[str, object]:
    """
    PyYAML yokken yeten en küçük ayrıştırıcı: `anahtar: değer` ve liste biçimleri.

    Desteklenen: düz skaler, `[a, b]` satır içi listesi ve `- öge` blok listesi.
    İç içe eşleme desteklenmez — ajan ön bilgisi kasıtlı olarak düz tutulmuştur;
    derinleşen bir şema hem kullanıcı için hem bu ayrıştırıcı için tuzak olurdu.
    """
    data: Dict[str, object] = {}
    current_list_key: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, [])
            value = stripped[2:].strip().strip("'\"")
            if isinstance(data[current_list_key], list) and value:
                data[current_list_key].append(value)
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            # Sonraki satırlar blok liste olabilir.
            current_list_key = key
            data[key] = []
            continue
        current_list_key = None
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
            data[key] = [v for v in items if v]
        else:
            data[key] = value.strip("'\"")
    return data


def parse_frontmatter(text: str) -> tuple[Dict[str, object], str]:
    """Markdown metnini (ön bilgi sözlüğü, gövde) ikilisine ayırır."""
    if not text:
        return {}, ""
    m = _FRONTMATTER_RE.match(text.lstrip("﻿"))
    if not m:
        return {}, text.strip()
    raw_front, body = m.group(1), m.group(2)
    data: Dict[str, object] = {}
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(raw_front)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
    if not data:
        data = _parse_simple_yaml(raw_front)
    return data, body.strip()


def render_frontmatter(data: Dict[str, object]) -> str:
    """
    Ön bilgiyi YAML olarak yazar (PyYAML'siz de doğru çıktı verir).

    Elle yazılıyor çünkü PyYAML isteğe bağlı; ayrıca `safe_dump` Türkçe
    karakterleri kaçış dizisine çevirebiliyor ve kasadaki dosya okunaksız hâle
    geliyordu (allow_unicode her çağrı noktasında hatırlanması gereken bir ayar).
    """
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(v) for v in value)
            lines.append(f"{key}: [{rendered}]")
        elif value is None:
            lines.append(f"{key}: ")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            text = str(value)
            # Çok satırlı değer ön bilgide yeri olmayan bir şeydir; tek satıra indirilir.
            text = " ".join(text.splitlines())
            lines.append(f"{key}: {text}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Varsayılan ajanlar
# ---------------------------------------------------------------------------

DEFAULT_AGENTS: List[AgentSpec] = [
    AgentSpec(
        name="arastirmaci",
        role="research",
        description="Web, kasa ve proje kaynaklarını tarar; kaynaklı, doğrulanabilir özet çıkarır.",
        provider="agy",
        model="gemini-3.8-flash-high",
        effort="medium",
        skills=[],
        tools_policy="read-only",
        memory_path="Entropy/AgentMemory/arastirmaci.md",
        prompt=(
            "Sen Entropy'nin araştırmacı ajanısın. Görevin bir soruyu kaynaklarıyla "
            "birlikte yanıtlamak.\n\n"
            "Çalışma biçimin:\n"
            "1. Soruyu alt sorulara böl; her biri için en az iki bağımsız kaynak ara.\n"
            "2. Kasadaki mevcut raporları ve projedeki dosyaları önce kontrol et; "
            "aynı işi ikinci kez yapma.\n"
            "3. Bulguları iddia + kaynak biçiminde yaz; kaynağı olmayan cümleyi "
            "'doğrulanmadı' diye işaretle.\n"
            "4. Dosya değiştirme; yalnızca oku ve rapor et.\n\n"
            "Çıktın: kısa yönetici özeti, madde madde bulgular, kaynak listesi ve "
            "açık kalan sorular."
        ),
    ),
    AgentSpec(
        name="analist",
        role="analysis",
        description="Veriyi ve bulguları çözümler; varsayımları, riskleri ve sayısal sonuçları çıkarır.",
        provider="agy",
        model="",
        effort="high",
        skills=[],
        tools_policy="read-write",
        memory_path="Entropy/AgentMemory/analist.md",
        prompt=(
            "Sen Entropy'nin analist ajanısın. Görevin ham bulguyu karara "
            "dönüştürmek.\n\n"
            "Çalışma biçimin:\n"
            "1. Önce veriyi ve varsayımları açıkça listele; eksik veriyi tahminle "
            "doldurma, eksik olduğunu söyle.\n"
            "2. Hesap yaptıysan ara adımları göster; sonuç tek başına yeterli değil.\n"
            "3. En az bir karşı senaryo ve bir risk maddesi üret.\n"
            "4. İddialarını ölçüyle destekle; 'iyileşti' değil 'x'ten y'ye indi' yaz.\n\n"
            "Çıktın: varsayımlar, çözümleme, sayısal sonuçlar, riskler, öneri."
        ),
    ),
    AgentSpec(
        name="yazar",
        role="report writing",
        description="Bulguları okunur bir rapora dönüştürür; Türkçe, yalın ve kanıtlı yazar.",
        provider="agy",
        model="",
        effort="medium",
        skills=[],
        tools_policy="read-write",
        memory_path="Entropy/AgentMemory/yazar.md",
        prompt=(
            "Sen Entropy'nin yazar ajanısın. Görevin dağınık bulguyu tek parça, "
            "okunur bir metne çevirmek.\n\n"
            "Çalışma biçimin:\n"
            "1. Önce okuyucuyu ve metnin amacını belirle; buna göre uzunluk seç.\n"
            "2. Başlıklar altında ilerle; her bölüm tek bir fikri anlatsın.\n"
            "3. Süslü dil, pazarlama sıfatı ve emoji kullanma; kanıtı olmayan "
            "övgü cümlesi yazma.\n"
            "4. Türkçe yaz; teknik terimleri gerektiğinde İngilizce özgün hâliyle ver.\n\n"
            "Çıktın: başlıklı markdown rapor; sonunda kaynaklar ve açık işler."
        ),
    ),
    AgentSpec(
        name="orkestrator",
        role="orchestrator",
        description="Bir ofis kartını en çok beş alt göreve böler ve ajanlara dağıtır.",
        provider="agy",
        model="gemini-3.8-flash-high",
        effort="medium",
        skills=[],
        tools_policy="read-only",
        memory_path="Entropy/AgentMemory/orkestrator.md",
        prompt=(
            "Sen Entropy'nin orkestratör ajanısın. Görevin bir işi yapmak değil, "
            "yapılabilir alt görevlere bölmek.\n\n"
            "Çalışma biçimin:\n"
            "1. Kartın hedefini ve ofis tüzüğünü oku; kabul standartlarını alt "
            "görevlere dağıt.\n"
            "2. En çok 5 alt görev üret. Her alt görev tek bir soruya yanıt "
            "versin ve tek bir ajana atansın.\n"
            "3. Alt görevler birbirinin çıktısını beklemesin; paralel "
            "koşabilecek biçimde böl.\n"
            "4. Yalnızca ofis üyesi ajanlara atama yap; olmayan ajan adı uydurma.\n"
            "5. Açıklama yazma; yanıtın TEK bir ```json kod bloğu olsun.\n\n"
            "Çıktı şeman:\n"
            '```json\n'
            '{"subtasks": [{"title": "...", "goal": "...", '
            '"criteria": ["..."], "agent": "...", "provider": "agy", "model": ""}]}\n'
            '```'
        ),
    ),
    AgentSpec(
        name="degerlendirici",
        role="evaluator",
        description="Alt görev çıktılarını kabul ölçütlerine karşı notlar; eksikleri sayar.",
        provider="agy",
        model="gemini-3.8-flash-high",
        effort="medium",
        skills=[],
        tools_policy="read-only",
        memory_path="Entropy/AgentMemory/degerlendirici.md",
        prompt=(
            "Sen Entropy'nin değerlendirici ajanısın. Üretmezsin, notlarsın.\n\n"
            "Çalışma biçimin:\n"
            "1. Her alt görevi YALNIZCA kendi kabul ölçütlerine göre değerlendir; "
            "hoşuna gitmesi ölçüt değildir.\n"
            "2. Notu 0 ile 1 arasında ver: 1.0 tüm ölçütler kanıtıyla karşılandı, "
            "0.6 kabul edilebilir alt sınır, 0.0 çıktı yok.\n"
            "3. Karşılanmayan her ölçütü 'missing' listesine tek tek yaz.\n"
            "4. Açıklama yazma; yanıtın TEK bir ```json kod bloğu olsun.\n\n"
            "Çıktı şeman:\n"
            '```json\n'
            '{"grades": [{"id": "...", "grade": 0.0, "verdict": "...", '
            '"missing": ["..."]}]}\n'
            '```'
        ),
    ),
]


# ---------------------------------------------------------------------------
# Kayıt defteri
# ---------------------------------------------------------------------------


class AgentRegistry:
    """
    Kasadaki ajan tanımlarının CRUD'u ve sağlayıcı biçimlerine derlenmesi.

    Örnek durumu tutmaz: her `list()` diski okur. Ajan dosyalarını Entropy'nin
    kendisi, kullanıcı ve harici bir CLI aynı anda yazabildiği için bellek içi
    bir önbellek hızlıca bayatlardı; dosya sayısı (onlar mertebesinde) okumayı
    ucuz tutuyor.
    """

    def __init__(self, vault_path: Optional[Path | str] = None):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.agents_dir = self.vault_path / AGENTS_SUBDIR

    # -- yollar --------------------------------------------------------

    def agent_dir(self, name: str) -> Path:
        return self.agents_dir / name

    def agent_file(self, name: str) -> Path:
        return self.agent_dir(name) / AGENT_FILENAME

    # -- okuma ---------------------------------------------------------

    def _is_desk_path(self, path: Path) -> bool:
        """
        Yol Desk'in kasasının (`<kasa>/Desk`, eski kurulumda `Entropy/Desk`)
        altında mı?

        Ek-1 (Faz 9): Entropy'nin kadrosu ofis ajanlarını ASLA içermez. Dizin
        ayrımı zaten bunu sağlıyor, ama bağlantı (junction/symlink) ya da elle
        taşınmış bir klasör ayrımı sessizce deliyordu; kural artık açık.
        """
        try:
            resolved = path.resolve()
            roots = [(self.vault_path / DESK_ROOT_SUBDIR).resolve()]
            # Eski kök de dışlanır: geçiş henüz koşmamış bir kasada (ya da
            # kullanıcı elle geri koyduysa) ofis ajanı Entropy kadrosuna
            # sızmasın.
            roots += [
                (self.vault_path / sub).resolve() for sub in LEGACY_DESK_ROOT_SUBDIRS
            ]
        except OSError:
            return False
        return any(r == resolved or r in resolved.parents for r in roots)

    def list(self) -> List[AgentSpec]:
        """Diskteki tüm ajanlar (ada göre sıralı); bozuk dosyalar atlanır."""
        specs: List[AgentSpec] = []
        try:
            if not self.agents_dir.is_dir():
                return specs
            for child in sorted(self.agents_dir.iterdir()):
                if not child.is_dir() or self._is_desk_path(child):
                    continue
                spec = self._read(child / AGENT_FILENAME)
                if spec is not None:
                    specs.append(spec)
        except OSError:
            return specs
        return specs

    def get(self, name: str) -> Optional[AgentSpec]:
        path = self.agent_file(name)
        if self._is_desk_path(path):
            return None
        return self._read(path)

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
        # Çift model: nested `models: {agy: ..., claude: ...}` (PyYAML varsa) ya
        # da düz `model_agy` / `model_claude` anahtarları. İkisi de desteklenir
        # çünkü yerleşik ayrıştırıcı iç içe eşleme okuyamıyor.
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
            office=str(front.get("office") or ""),
            models=models,
        )

    # -- yazma ---------------------------------------------------------

    def create(self, spec: AgentSpec) -> AgentSpec:
        """Yeni ajan yazar; aynı adda ajan varsa hata verir (sessizce ezmez)."""
        if self.agent_file(spec.name).exists():
            raise FileExistsError(f"'{spec.name}' adında bir ajan zaten var.")
        return self._write(spec)

    def update(self, spec: AgentSpec) -> AgentSpec:
        """Var olan ajanı günceller (yoksa oluşturur)."""
        return self._write(spec)

    def _write(self, spec: AgentSpec) -> AgentSpec:
        if not (spec.name or "").strip():
            raise ValueError("Ajan adı boş olamaz.")
        path = self.agent_file(spec.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (spec.prompt or "").strip()
        if not body.startswith("#"):
            body = f"# {spec.name}\n\n{body}".strip()
        content = f"{render_frontmatter(spec.to_frontmatter())}\n\n{body}\n"
        path.write_text(content, encoding="utf-8")
        self._notify(spec.name)
        return replace(spec, path=path)

    def delete(self, name: str) -> bool:
        """Ajanı (klasörüyle birlikte) siler; silindiyse True."""
        target = self.agent_dir(name)
        if not target.is_dir():
            return False
        shutil.rmtree(target, ignore_errors=True)
        self._notify(name)
        return not target.exists()

    @staticmethod
    def _notify(name: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.agents_updated.emit(name)
        except Exception:
            pass

    # -- varsayılanlar --------------------------------------------------

    def ensure_defaults(self) -> List[str]:
        """
        Eksik tohum ajanları AD BAZINDA tamamlar; oluşturulan adları döndürür.

        Eskiden "klasör tamamen boşsa yaz" kuralı vardı ve Faz 3'te kadroya
        eklenen `orkestrator`/`degerlendirici` mevcut kasalara hiç gelmiyordu:
        kasada zaten üç ajan olduğu için tohumlama atlanıyordu.

        Kullanıcının bilinçli sildiği ajanı geri getirmemek için hangi tohumun
        bir kez yazıldığı `<kasa>/Entropy/Agents/.seeded.json` işaret dosyasında
        tutulur. Yalnızca İLK KEZ görülen tohum adları yazılır.
        """
        return _seed_missing(
            marker_path=self.agents_dir / SEED_MARKER_FILENAME,
            defaults=DEFAULT_AGENTS,
            existing={spec.name for spec in self.list()},
            write=self._write,
        )

    # -- derleme --------------------------------------------------------

    def compile_all(self, project_dir: Optional[Path | str] = None) -> Dict[str, Dict[str, Path]]:
        """Tüm ajanları sağlayıcı biçimlerine derler: {ajan_adı: {sağlayıcı: yol}}."""
        from entropy.agents.compile import compile_agent

        import logging

        out: Dict[str, Dict[str, Path]] = {}
        for spec in self.list():
            try:
                out[spec.name] = compile_agent(spec, project_dir)
            except Exception as exc:
                # Sessiz yutma, açılışta hangi ajanın derlenmediğini gizliyordu.
                logging.getLogger(__name__).warning(
                    "Ajan derlenemedi (%s): %s", spec.name, exc
                )
                continue
        return out


# ---------------------------------------------------------------------------
# Manifest bölümü
# ---------------------------------------------------------------------------


def agents_manifest(registry: Optional[AgentRegistry] = None) -> str:
    """
    Prompt'a enjekte edilen "Ajanlar" bölümü (≤ ~150 token).

    İçerik: her ajanın adı, rolü ve yetenekleri + devretme kuralı + kaynak dosya
    yolu biçimi. Yol biçimi kasıtlı olarak burada: Entropy'nin kendisi yeni bir
    ajan ya da görev kartı oluşturmak istediğinde dosyayı nereye yazacağını
    bilmesi gerekiyor; aksi hâlde "bir ajan oluştur" isteği havada kalıyordu.
    """
    try:
        registry = registry or AgentRegistry()
        specs = registry.list()
    except Exception:
        return ""
    if not specs:
        return ""

    lines = ["[AJANLAR]"]
    for spec in specs:
        skills = ", ".join(spec.skills) if spec.skills else "-"
        row = f"- 🤖 {spec.name} ({spec.role or 'genel'}) · yetenekler: {skills}"
        if len("\n".join(lines)) + len(row) > MANIFEST_CHAR_BUDGET:
            lines.append("- … (tam liste için /agents)")
            break
        lines.append(row)
    lines.append(
        "KURAL: Bir işi ajana devretmek için `/task <ajan> <başlık> :: <hedef>` "
        "biçiminde öner ya da Entropy/Tasks altına kart yaz "
        f"(ajan tanımı: {AGENTS_SUBDIR}/<ad>/{AGENT_FILENAME})."
    )
    return "\n".join(lines)
