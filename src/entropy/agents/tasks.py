"""
Görev kartları: kasadaki markdown dosyaları hem panonun hem ajanların kaynağı.

Kart neden dosya: Entropy bir işi ajana devretmek istediğinde kart yazabilmeli,
kullanıcı Obsidian'da düzenleyebilmeli ve iki taraf da aynı gerçeği görmeli.
Uygulama içi bir kuyruk bunların hiçbirini vermezdi.

Dosya biçimi `<kasa>/Entropy/Tasks/<id>.md`:

    ---
    id: 20260909-1432-rapor
    title: Sprint raporu
    status: backlog
    agent: yazar
    provider: agy
    model: ""
    skill: research
    created_at: 2026-09-09T14:32:00
    ...
    ---
    ## Hedef
    ...
    ## Kabul ölçütleri
    - ...
    ## Notlar
    ## Sonuç

Yaşam döngüsü: backlog → running → review (başarısızsa failed) → done.
"review"de durur, "done" bilinçli bir insan onayıdır: ajan çıktısını kimse
okumadan "bitti" saymak, panonun tamamını anlamsız kılardı.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.agents.mailbox import emit_terminal
from entropy.agents.registry import (
    AgentRegistry,
    default_provider,
    parse_frontmatter,
    render_frontmatter,
)

TASKS_SUBDIR = "Entropy/Tasks"

# Faz 9 / B-9.2 — kart deposu ikiye ayrıldı. Entropy'nin KENDİ kartları
# `Entropy/Tasks` altında kalır; ofis kartları ofisin kendi kasasında,
# `Entropy/Desk/Offices/<ofis>/cards/` altında durur. Ayrım eskiden yalnızca
# kart ön bilgisindeki `office:` alanındaydı; aynı klasörde durdukları için
# Obsidian'da, yedeklemede ve panolarda iki dünya karışıyordu.
DESK_OFFICES_SUBDIR = "Entropy/Desk/Offices"
OFFICE_CARDS_DIRNAME = "cards"

# Taşıma günlüğü: geri alınabilirlik için her taşınan kartın eski/yeni yolu.
MIGRATION_LOG_SUBPATH = "Entropy/Desk/_migrations.log"

# `list(office=ALL_CARDS)` iki kökü de tarar. Varsayılan (`office=None`)
# YALNIZCA Entropy kartlarını döndürür: Entropy'nin panosu ofis kartlarını
# kendi işi sanmasın diye süzme artık depo düzeyinde.
ALL_CARDS = "*"

STATUSES = ("backlog", "running", "review", "done", "failed")

# Kart gövdesindeki bölüm başlıkları; ayrıştırma ve üretme aynı listeyi kullanır.
SECTION_GOAL = "Hedef"
SECTION_CRITERIA = "Kabul ölçütleri"
SECTION_NOTES = "Notlar"
SECTION_RESULT = "Sonuç"

# Alt kart adım tavanı. agy'de adım/tur sayısını sınırlayan bir CLI bayrağı YOK
# (`agy -p --help`: yalnızca --effort ve --print-timeout), bu yüzden sınır
# prompt sözleşmesiyle konuyor.
MAX_STEPS_PER_CARD = 20

# Alt kart istemine giren proje dosya listesi tavanı (Faz 7 / C2d).
PROJECT_FILE_LIST_LIMIT = 40

COST_DISCIPLINE = (
    "[MALİYET DİSİPLİNİ]\n"
    "- Yalnızca sana verilen dosyaları ve yolları oku; deponun tamamını tarama, "
    "geniş `grep`/`glob` gezintisi yapma.\n"
    f"- En çok {MAX_STEPS_PER_CARD} araç adımı kullan; ölçütleri karşıladığında dur.\n"
    "- Aynı dosyayı ikinci kez okuma; gerekli bilgiyi ilk okumada çıkar.\n"
    "- Bilgi eksikse tahmin üretme, 'yapılamadı: <neden>' yaz."
)


@dataclass
class TaskCard:
    """Tek bir görev kartı."""

    id: str
    title: str = ""
    status: str = "backlog"
    agent: str = ""
    provider: str = field(default_factory=default_provider)
    model: str = ""
    skill: str = ""
    goal: str = ""
    criteria: List[str] = field(default_factory=list)
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    output_paths: List[str] = field(default_factory=list)
    summary: str = ""
    path: Optional[Path] = None
    notes: str = ""
    # Ofis alanları (Faz 3). Üst kart `children` ile alt kartlarını tutar, alt
    # kart `parent` ile üstünü; ağaç iki yönlü çünkü pano üstten aşağı, harness
    # ise bir alt kart bitince yukarı bakıyor ve tek yönlü bağ her iki tarafta
    # da tüm kartları taramayı gerektirirdi.
    office: str = ""
    parent: str = ""
    children: List[str] = field(default_factory=list)
    # Değerlendiricinin verdiği not (0–1) ve gerekçesi; `None` = notlanmadı.
    grade: Optional[float] = None
    verdict: str = ""
    # Kaç kez koşuldu: eşiğin altındaki alt kart bir kez yeniden koşar (retry ≤ 1).
    attempt: int = 0
    # Kart düzeyi token tavanı; 0 ise ofisin `budget_tokens` değeri geçerli.
    budget_tokens: int = 0
    # Ofis projesi (`projects/<proje>/PROJECT.md`). Boşsa kart projesizdir;
    # ofis kartları bir projeye bağlanınca rapor ve bellek o proje altında
    # toplanır ve orkestratör planlarken projenin kapsamını görür.
    project: str = ""
    # Kilit niyeti: "write" (proje dosyalarını değiştirir) | "read" | "" (çıkarım).
    # Ofis alt kartları varsayılan olarak OKUMA: paylaşımlı kilitle aynı proje
    # dizininde birbirlerini beklemeden koşabilsinler.
    intent: str = ""

    def to_frontmatter(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status if self.status in STATUSES else "backlog",
            "agent": self.agent,
            "provider": self.provider,
            "model": self.model,
            "skill": self.skill,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_paths": list(self.output_paths or []),
            "office": self.office,
            "project": self.project,
            "parent": self.parent,
            "children": list(self.children or []),
            "grade": "" if self.grade is None else round(float(self.grade), 3),
            "verdict": self.verdict,
            "attempt": int(self.attempt or 0),
            "budget_tokens": int(self.budget_tokens or 0),
            "intent": self.intent,
        }


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def new_task_id(title: str = "") -> str:
    """Zaman damgası + başlıktan türetilmiş, dosya adı olarak güvenli kimlik."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "gorev").lower()).strip("-")[:24] or "gorev"
    return f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}"


SECTIONS = (SECTION_GOAL, SECTION_CRITERIA, SECTION_NOTES, SECTION_RESULT)

# Bölüm sınırı YALNIZCA bu dört başlıktır. Eskiden herhangi bir `## ...` satırı
# sınır sayılıyordu ve ajan çıktısı `## Bulgular` gibi bir başlık içerdiğinde
# "Sonuç" bölümü ilk başlıkta kesiliyordu: 29k karakterlik çıktı geri okunduğunda
# birkaç yüz karaktere iniyordu.
_SECTION_HEAD_RE = re.compile(r"^##\s+(" + "|".join(re.escape(s) for s in SECTIONS) + r")\s*$")

# Gövde metni tesadüfen tam da bu dört başlıktan birini içerebilir. O durumda
# yazarken bir seviye indirilir ve görünmez bir HTML yorumu işareti konur;
# okurken aynı işaretle geri yükselir. Simetrik olduğu için kayıpsız.
_ESCAPE_MARK = "<!--entropy-esc-->"
_ESCAPED_HEAD_RE = re.compile(
    r"^###\s+(" + "|".join(re.escape(s) for s in SECTIONS) + r")\s*" + re.escape(_ESCAPE_MARK) + r"\s*$"
)


def _escape_body(text: str) -> str:
    """Bölüm sınırıyla çakışan başlıkları bir seviye indirir (yazma yönü)."""
    if not text:
        return text or ""
    out = []
    for line in text.splitlines():
        m = _SECTION_HEAD_RE.match(line)
        out.append(f"### {m.group(1)} {_ESCAPE_MARK}" if m else line)
    return "\n".join(out)


def _unescape_body(text: str) -> str:
    """`_escape_body`nin tersi (okuma yönü)."""
    if not text or _ESCAPE_MARK not in text:
        return text or ""
    out = []
    for line in text.splitlines():
        m = _ESCAPED_HEAD_RE.match(line)
        out.append(f"## {m.group(1)}" if m else line)
    return "\n".join(out)


def trim_to_sections(text: str, limit: int) -> str:
    """
    Metni `limit` karakterin altına, BÖLÜM BÜTÜNLÜĞÜNÜ bozmadan kırpar.

    Değerlendirici prompt'u için: ham `text[:1500]` kesmesi cümlenin ortasında
    duruyor ve değerlendirici eksik gördüğü bölümü "yapılmamış" sayıyordu. Burada
    yalnızca tam markdown blokları (başlıktan başlığa) alınır.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    blocks: List[List[str]] = [[]]
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line) and blocks[-1]:
            blocks.append([])
        blocks[-1].append(line)
    kept: List[str] = []
    total = 0
    for block in blocks:
        chunk = "\n".join(block)
        if kept and total + len(chunk) + 1 > limit:
            break
        kept.append(chunk)
        total += len(chunk) + 1
    out = "\n".join(kept)
    if len(out) > limit:
        # Tek blok bile sığmıyor: sert kesmekten başka seçenek yok.
        out = out[:limit]
    if len(out) < len(text):
        out = out.rstrip() + "\n\n[... çıktı kırpıldı; tamamı kartta]"
    return out


def _split_sections(body: str) -> Dict[str, str]:
    """Gövdeyi bilinen `## Başlık` bölümlerine ayırır."""
    sections: Dict[str, str] = {}
    current = None
    buf: List[str] = []
    for line in (body or "").splitlines():
        m = _SECTION_HEAD_RE.match(line)
        if m:
            if current:
                sections[current] = _unescape_body("\n".join(buf).strip())
            current = m.group(1).strip()
            buf = []
        elif current:
            buf.append(line)
    if current:
        sections[current] = _unescape_body("\n".join(buf).strip())
    return sections


# Proje dosyalarını değiştirme niyeti taşıyan fiiller. Liste kasıtlı olarak dar:
# "rapor yaz" gibi kasaya üreten işler yazma kilidi almamalı, yoksa her alt kart
# yeniden sıraya girer ve ofis paralelliği anlamsızlaşır.
_WRITE_INTENT_RE = re.compile(
    r"\b(refactor|refaktör|kodu?\s+(değiştir|düzelt|yaz)|dosyayı?\s+(değiştir|düzenle|güncelle|sil)|"
    r"düzenle|yamala|patch|implement|uygula|commit|migrasyon|migration|"
    r"testleri?\s+(ekle|yaz)|hata\s*ayıkla|debug|derle|build)\b",
    re.IGNORECASE,
)


def _accepts_kwarg(func, name: str) -> bool:
    """`func` verilen adlı anahtar argümanı (ya da **kwargs) kabul ediyor mu?"""
    import inspect

    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False
    if name in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def resolve_card_model(card: "TaskCard", agent_spec=None, provider: str = "") -> str:
    """
    Kartın bu koşuda kullanacağı ham model adı (Faz 9.5).

    Sıra: (1) kartın `model` alanı, (2) ajan tanımının modeli. İki durumda da ad
    `compile.resolve_model` tablosundan geçirilir; sağlayıcıya ait olmayan bir ad
    (ör. `provider: claude` + `model: gemini-3.1-pro-high`) o sağlayıcının
    karşılığına çevrilir. Boş dönüş = "oturumun modelini miras al".

    Eskiden kartın `model` alanı hiçbir yere aktarılmıyordu; köprü üst çubuğun
    modelini kullanıyor ve claude kartları `unrecognized_model` ile ölüyordu.
    """
    from entropy.agents.compile import CLAUDE_FALLBACK_MODEL, resolve_model
    from entropy.agents.registry import AgentSpec

    provider = (provider or "").strip().lower()
    raw = (card.model or "").strip()
    spec = agent_spec
    if raw:
        # Kart modeli ajan tanımını geçersiz kılar; tabloyu kullanabilmek için
        # geçici bir spec'e sarılır (resolve_model spec üzerinden çalışıyor).
        spec = AgentSpec(name=card.agent or card.id, model=raw)
    if spec is None:
        return ""
    resolved = (resolve_model(spec, provider) or "").strip()
    if not resolved or resolved.lower() == CLAUDE_FALLBACK_MODEL:
        # "inherit": köprü kendi oturum modelinde kalsın.
        return ""
    return resolved


def agent_spec_payload(agent_spec) -> Optional[dict]:
    """Ajan tanımının sistem istemine giren, sağlayıcıdan bağımsız özeti."""
    if agent_spec is None:
        return None
    return {
        "name": getattr(agent_spec, "name", "") or "",
        "role": getattr(agent_spec, "role", "") or "",
        "description": getattr(agent_spec, "description", "") or "",
        "prompt": getattr(agent_spec, "prompt", "") or "",
        "tools_policy": getattr(agent_spec, "tools_policy", "") or "",
        "office": getattr(agent_spec, "office", "") or "",
    }


def card_needs_write(card: "TaskCard", agent_spec=None) -> bool:
    """
    Kart proje dizininde YAZMA kilidi gerektiriyor mu?

    Sıra: (1) kartın açık `intent` alanı, (2) ajanın `tools_policy` kısıtı,
    (3) ofis alt kartıysa varsayılan OKUMA, (4) metinde yazma fiili araması.
    """
    intent = (card.intent or "").strip().lower()
    if intent in ("write", "yazma", "rw"):
        return True
    if intent in ("read", "okuma", "ro", "read-only"):
        return False
    if agent_spec is not None and (getattr(agent_spec, "tools_policy", "") or "").lower() in (
        "read-only", "readonly", "okuma"
    ):
        return False
    if card.parent or card.office:
        # Ofis alt kartı: aksi açıkça yazılmadıkça okuma kilidiyle koşar.
        return False
    text = " ".join([card.title or "", card.goal or "", " ".join(card.criteria or []), card.notes or ""])
    return bool(_WRITE_INTENT_RE.search(text))


def _bullets(text: str) -> List[str]:
    return [
        re.sub(r"^[-*]\s+", "", ln).strip()
        for ln in (text or "").splitlines()
        if ln.strip().startswith(("-", "*"))
    ]


class TaskBoard:
    """Kasadaki görev kartlarının CRUD'u ve yürütülmesi."""

    # Sağlayıcı başına köprü önbelleği: bir kart "claude" derken etkin köprü
    # "agy" ise o sağlayıcının köprüsü kurulur. Her kart için yeni köprü kurmak
    # süreç başına onlarca boşta CLI oturumu ve token sayacı demekti.
    _bridge_cache: Dict[str, object] = {}
    _bridge_lock = threading.Lock()

    def __init__(self, vault_path: Optional[Path | str] = None):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.tasks_dir = self.vault_path / TASKS_SUBDIR
        self.desk_offices_dir = self.vault_path / DESK_OFFICES_SUBDIR
        self._migrate_office_cards_once()

    # -- yollar --------------------------------------------------------

    def office_cards_dir(self, office: str) -> Path:
        """Bir ofisin kart klasörü (`Entropy/Desk/Offices/<ofis>/cards`)."""
        return self.desk_offices_dir / str(office).strip() / OFFICE_CARDS_DIRNAME

    def _office_card_dirs(self) -> List[Path]:
        """Diskte var olan tüm ofis kart klasörleri."""
        out: List[Path] = []
        try:
            if not self.desk_offices_dir.is_dir():
                return out
            for child in sorted(self.desk_offices_dir.iterdir()):
                if not child.is_dir():
                    continue
                cards = child / OFFICE_CARDS_DIRNAME
                if cards.is_dir():
                    out.append(cards)
        except OSError:
            return out
        return out

    # -- okuma ---------------------------------------------------------

    def card_file(self, task_id: str, office: Optional[str] = None) -> Path:
        """
        Kartın dosya yolu.

        `office` verilmişse doğrudan o ofisin kart klasörü kullanılır (yazma
        yolu bunu kullanır: kart hangi ofise aitse oraya yazılır). Verilmemişse
        önce Entropy kökü, sonra ofis kökleri aranır; hiçbirinde yoksa Entropy
        kökü döner — yani "yeni kart" varsayılan olarak Entropy'nindir.
        """
        office = (office or "").strip()
        if office:
            return self.office_cards_dir(office) / f"{task_id}.md"
        entropy_path = self.tasks_dir / f"{task_id}.md"
        if entropy_path.is_file():
            return entropy_path
        for cards_dir in self._office_card_dirs():
            candidate = cards_dir / f"{task_id}.md"
            if candidate.is_file():
                return candidate
        return entropy_path

    def list(self, status: Optional[str] = None,
             office: Optional[str] = None) -> List[TaskCard]:
        """
        Kartlar. `office=None` → YALNIZCA Entropy kartları,
        `office="<ad>"` → yalnızca o ofisin kartları,
        `office=ALL_CARDS` → iki kök birden.
        """
        cards: List[TaskCard] = []
        scope = (office or "").strip()
        if scope == ALL_CARDS:
            roots = [self.tasks_dir] + self._office_card_dirs()
        elif scope:
            roots = [self.office_cards_dir(scope)]
        else:
            roots = [self.tasks_dir]
        for root in roots:
            try:
                if not root.is_dir():
                    continue
                for path in sorted(root.glob("*.md")):
                    card = self._read(path)
                    if card is None:
                        continue
                    if status is not None and card.status != status:
                        continue
                    # Entropy kökündeki bir kart `office:` taşıyorsa (taşıma
                    # yapılamamış kalıntı) Entropy listesine KARIŞTIRILMAZ.
                    if not scope and card.office:
                        continue
                    if scope and scope != ALL_CARDS and card.office != scope:
                        continue
                    cards.append(card)
            except OSError:
                continue
        return cards

    def get(self, task_id: str) -> Optional[TaskCard]:
        return self._read(self.card_file(task_id))

    def _read(self, path: Path) -> Optional[TaskCard]:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        sections = _split_sections(body)
        outputs = front.get("output_paths") or []
        if isinstance(outputs, str):
            outputs = [o.strip() for o in outputs.split(",") if o.strip()]
        status = str(front.get("status") or "backlog").strip().lower()
        children = front.get("children") or []
        if isinstance(children, str):
            children = [c.strip() for c in children.split(",") if c.strip()]
        raw_grade = front.get("grade")
        try:
            grade = float(raw_grade) if str(raw_grade).strip() not in ("", "None") else None
        except (TypeError, ValueError):
            grade = None
        try:
            attempt = int(str(front.get("attempt") or 0).strip() or 0)
        except (TypeError, ValueError):
            attempt = 0
        try:
            budget_tokens = int(str(front.get("budget_tokens") or 0).strip() or 0)
        except (TypeError, ValueError):
            budget_tokens = 0
        return TaskCard(
            id=str(front.get("id") or path.stem),
            title=str(front.get("title") or path.stem),
            status=status if status in STATUSES else "backlog",
            agent=str(front.get("agent") or ""),
            provider=str(front.get("provider") or default_provider()),
            model=str(front.get("model") or ""),
            skill=str(front.get("skill") or ""),
            goal=sections.get(SECTION_GOAL, "").strip(),
            criteria=_bullets(sections.get(SECTION_CRITERIA, "")),
            created_at=str(front.get("created_at") or ""),
            started_at=str(front.get("started_at") or ""),
            finished_at=str(front.get("finished_at") or ""),
            output_paths=[str(o) for o in outputs],
            summary=sections.get(SECTION_RESULT, "").strip(),
            notes=sections.get(SECTION_NOTES, "").strip(),
            path=path,
            office=str(front.get("office") or ""),
            project=str(front.get("project") or ""),
            parent=str(front.get("parent") or ""),
            children=[str(c) for c in children],
            grade=grade,
            verdict=str(front.get("verdict") or ""),
            attempt=attempt,
            budget_tokens=budget_tokens,
            intent=str(front.get("intent") or "").strip().lower(),
        )

    # -- yazma ---------------------------------------------------------

    def create(self, card: TaskCard) -> TaskCard:
        if not card.id:
            card = replace(card, id=new_task_id(card.title))
        if not card.created_at:
            card = replace(card, created_at=_now())
        if self.card_file(card.id, office=card.office).exists() or self.get(card.id) is not None:
            raise FileExistsError(f"'{card.id}' kimlikli kart zaten var.")
        return self._write(card)

    def update(self, card: TaskCard) -> TaskCard:
        return self._write(card)

    def _write(self, card: TaskCard) -> TaskCard:
        # Kartın kökü `office` alanından türer: ofis kartı ofisin kasasına,
        # Entropy kartı `Entropy/Tasks` altına yazılır.
        path = self.card_file(card.id, office=card.office)
        # Kart ofis kazandıysa (ya da kaybettiyse) eski kökteki kopya silinir;
        # aksi hâlde aynı kimlikle iki dosya kalır ve iki kaynaklı gerçek olur.
        old = self.card_file(card.id)
        if old != path and old.is_file():
            try:
                old.unlink()
            except OSError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "-"
        body = (
            f"## {SECTION_GOAL}\n{_escape_body(card.goal) or '-'}\n\n"
            f"## {SECTION_CRITERIA}\n{criteria}\n\n"
            f"## {SECTION_NOTES}\n{_escape_body(card.notes)}\n\n"
            f"## {SECTION_RESULT}\n{_escape_body(card.summary)}\n"
        )
        path.write_text(f"{render_frontmatter(card.to_frontmatter())}\n\n{body}", encoding="utf-8")
        self._notify(card.id)
        return replace(card, path=path)

    def delete(self, task_id: str) -> bool:
        path = self.card_file(task_id)
        if not path.is_file():
            return False
        try:
            path.unlink()
        except OSError:
            return False
        self._notify(task_id)
        return True

    # -- taşıma (Faz 9 / B-9.2) ------------------------------------------

    # Kasa başına tek kez koşar: her `TaskBoard()` kurulumunda diski taramak
    # gereksiz; taşıma zaten idempotent ama ucuz olmalı.
    _migrated_vaults: set = set()
    _migrate_lock = threading.Lock()

    def _migrate_office_cards_once(self) -> None:
        key = str(self.vault_path.resolve() if self.vault_path.exists() else self.vault_path)
        with TaskBoard._migrate_lock:
            if key in TaskBoard._migrated_vaults:
                return
            TaskBoard._migrated_vaults.add(key)
        try:
            self.migrate_office_cards()
        except Exception:
            logging.getLogger(__name__).warning("Ofis kartı taşıması yapılamadı.", exc_info=True)

    def migrate_office_cards(self) -> List[str]:
        """
        `Entropy/Tasks` altında kalmış OFİS kartlarını ofis kasasına taşır.

        Tek işlemde, doğrulamalı ve idempotent: hedefte aynı içerik zaten
        varsa kaynak silinir, hedef farklıysa kaynak DOKUNULMADAN bırakılır
        (iki kaynaklı gerçeği sessizce çözmek veri kaybı riskiydi). Her adım
        `Entropy/Desk/_migrations.log` dosyasına yazılır.
        """
        moved: List[str] = []
        entries: List[str] = []
        try:
            if not self.tasks_dir.is_dir():
                return moved
            candidates = sorted(self.tasks_dir.glob("*.md"))
        except OSError:
            return moved
        desk_offices = self._desk_agent_offices()
        with TaskBoard._migrate_lock:
            for path in candidates:
                card = self._read(path)
                if card is None:
                    continue
                if not card.office:
                    # Ofissiz ama ajanı bir DESK ofisine ait olan kart: kullanıcı
                    # `/task ... Alfa` yazarken "ofise iş vermek" istiyordu, kart
                    # ise Entropy kökünde ofissiz doğuyor ve `run()` kadro
                    # kontrolüne takılıp `failed` oluyordu. Niyet ajandan
                    # okunabildiği için kart o ofise devredilir.
                    if self._claim_card_for_office(path, card, desk_offices, moved, entries):
                        continue
                    continue
                target = self.office_cards_dir(card.office) / path.name
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                try:
                    if target.is_file():
                        if target.read_text(encoding="utf-8") == text:
                            path.unlink()
                            entries.append(f"tekrar\t{path}\t{target}")
                        else:
                            entries.append(f"çakışma\t{path}\t{target}")
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8")
                    # Doğrulama: hedef okunabiliyor ve aynı kimliği taşıyor mu?
                    check = self._read(target)
                    if check is None or check.id != card.id:
                        entries.append(f"doğrulanamadı\t{path}\t{target}")
                        continue
                    path.unlink()
                    moved.append(card.id)
                    entries.append(f"taşındı\t{path}\t{target}")
                except OSError as exc:
                    entries.append(f"hata\t{path}\t{target}\t{exc}")
        if entries:
            self._append_migration_log(entries)
        if moved:
            logging.getLogger(__name__).info("Ofis kartı taşındı (%d): %s", len(moved), ", ".join(moved))
            self._notify("")
        return moved

    def _desk_agent_offices(self) -> Dict[str, str]:
        """`{ajan adı: ofis}` — Desk ofislerinin tüm kadrosu (orkestratör dâhil)."""
        try:
            from entropy.agents.desk_registry import DeskRegistry

            desk = DeskRegistry(vault_path=self.vault_path)
            out: Dict[str, str] = {}
            for office in desk.list():
                for name in office.roster():
                    out.setdefault(name, office.name)
            return out
        except Exception:
            return {}

    def _claim_card_for_office(self, path: Path, card: "TaskCard",
                               desk_offices: Dict[str, str],
                               moved: List[str], entries: List[str]) -> bool:
        """
        Ofissiz kartı, ajanının ofisine devreder. Devredilirse True.

        Koşan kart DOKUNULMAZ (yürütmenin altından dosya çekmek sonucu
        kaybettirirdi) ve hedefte aynı adlı bir kart varsa çakışma yazılıp
        kaynak bırakılır. Yazma doğrulanamazsa kaynak geri konur.
        """
        office = desk_offices.get((card.agent or "").strip())
        if not office or card.status == "running":
            return False
        target = self.office_cards_dir(office) / path.name
        try:
            source_text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        if target.is_file():
            entries.append(f"çakışma\t{path}\t{target}")
            return False
        try:
            self._write(replace(card, office=office))
        except OSError as exc:
            entries.append(f"hata\t{path}\t{target}\t{exc}")
            return False
        check = self._read(target)
        if check is None or check.id != card.id or check.office != office:
            # Geri al: kaynak dosya `_write` sırasında silinmiş olabilir.
            try:
                path.write_text(source_text, encoding="utf-8")
                target.unlink()
            except OSError:
                pass
            entries.append(f"doğrulanamadı\t{path}\t{target}")
            return False
        moved.append(card.id)
        entries.append(f"ofise-atandı\t{path}\t{target}\t{office}")
        return True

    def _append_migration_log(self, entries: List[str]) -> None:
        path = self.vault_path / MIGRATION_LOG_SUBPATH
        stamp = _now()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for row in entries:
                    fh.write(f"{stamp}\t{row}\n")
        except OSError:
            logging.getLogger(__name__).warning("Taşıma günlüğü yazılamadı: %s", path)

    @staticmethod
    def _notify(task_id: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.task_cards_updated.emit(task_id)
        except Exception:
            pass

    # -- yürütme --------------------------------------------------------

    @classmethod
    def bridge_for(cls, provider: str, bridge_factory: Optional[Callable] = None):
        """
        Kartın sağlayıcısına uygun köprüyü verir.

        Sıra: (1) test/çağıran enjeksiyonu, (2) etkin köprü aynı sağlayıcıysa o,
        (3) süreç genelinde önbelleklenen, o sağlayıcıya ait yeni köprü.
        """
        provider = (provider or "agy").strip().lower()
        if bridge_factory is not None:
            return bridge_factory(provider)

        try:
            from entropy.ui.manager import EntropyUIManager

            mgr = getattr(EntropyUIManager, "instance", None)
            active = getattr(mgr, "bridge", None) if mgr is not None else None
            if active is not None and getattr(active, "provider_name", None) == provider:
                return active
        except Exception:
            pass

        with cls._bridge_lock:
            cached = cls._bridge_cache.get(provider)
            if cached is not None:
                return cached
            from entropy.core.provider import create_bridge

            bridge = create_bridge(provider=provider)
            cls._bridge_cache[provider] = bridge
            return bridge

    @staticmethod
    def project_file_section(project_path: Optional[str], limit: int = PROJECT_FILE_LIST_LIMIT) -> str:
        """
        Alt kart istemine giren PROJE DOSYA LİSTESİ (ilk `limit` yol).

        Faz 7 (C2d): alt ajan kendi başına depoyu taramasın diye istemde hazır
        bir dosya haritası verilir. Liste bilerek kısa ve göreli: tam ağaç
        tek başına on binlerce token ediyordu ve mutlak yollar istemde kasa
        konumunu sızdırıyordu. Gizli klasörler (`.git`, `__pycache__`, `node_modules`)
        atlanır: gürültüden başka bir şey taşımıyorlar.
        """
        if not project_path:
            return ""
        root = Path(project_path)
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
                ".pytest_cache", "dist", "build", ".idea", ".vscode"}
        paths: List[str] = []
        try:
            if not root.is_dir():
                return ""
            for current, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
                for name in sorted(files):
                    if name.startswith("."):
                        continue
                    try:
                        rel = str(Path(current, name).relative_to(root))
                    except ValueError:
                        continue
                    paths.append(rel.replace("\\", "/"))
                    if len(paths) >= limit:
                        break
                if len(paths) >= limit:
                    break
        except OSError:
            return ""
        if not paths:
            return ""
        return (
            "[PROJE DOSYALARI]\n"
            f"(ilk {len(paths)} yol; kök: proje dizini)\n"
            + "\n".join(f"- {p}" for p in paths)
        )

    def build_prompt(self, card: TaskCard, agent_spec=None, project_path: Optional[str] = None) -> str:
        """
        Ajanın gövdesi + görev sözleşmesi + kabul ölçütleri.

        Ajan gövdesi prompt'a da konur (yalnızca `--agent` ile geçilmez): derlenmiş
        ajan tanımı sağlayıcının bulamadığı bir kökten koşulduğunda sessizce
        yok sayılıyor ve görev genel bir asistan tarafından yapılıyordu. Gövdenin
        prompt'ta olması bu durumda da rolü garanti eder.
        """
        parts: List[str] = []
        if agent_spec is not None and (agent_spec.prompt or "").strip():
            parts.append(agent_spec.prompt.strip())
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "- (belirtilmedi)"
        parts.append(
            "[GÖREV SÖZLEŞMESİ]\n"
            f"Başlık: {card.title}\n"
            f"Hedef: {card.goal or card.title}\n"
            f"Kabul ölçütleri:\n{criteria}\n\n"
            "Kurallar: Ölçütlerin her birini tek tek ele al ve karşılandığını "
            "kanıtıyla göster. Yapamadığın maddeyi 'yapılamadı' diye açıkça yaz; "
            "sessizce atlama. Yanıtın Türkçe ve markdown olsun.\n\n"
            # Maliyet disiplini: kota koruması yalnızca bütçe sayacıyla değil,
            # görevin kendi kapsamıyla da yapılır. Sınırsız keşif yetkisi verilen
            # bir alt kart tek başına ofisin bütçesini bitiriyordu.
            f"{COST_DISCIPLINE}"
        )
        files_block = self.project_file_section(project_path)
        if files_block:
            parts.append(files_block)
        if card.notes:
            parts.append(f"[NOTLAR]\n{card.notes}")
        return "\n\n".join(parts)

    def run(
        self,
        card_id: str,
        bridge_factory: Optional[Callable] = None,
        on_done: Optional[Callable[[str, bool], None]] = None,
        agent_registry=None,
        project_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Kartı arka planda çalıştırır; ledger görev kimliğini döndürür.

        Çağrı bloke etmez: köprünün `send_background_task_async`ı iş parçacığı
        açar, sonuç geri çağrıda işlenir. Kart hemen `running` olur ki pano
        (ve ikinci bir /task çağrısı) aynı işi iki kez başlatmasın.

        `on_done(kart_id, başarılı)` kart kapandıktan SONRA çağrılır (köprünün
        işçi iş parçacığında). Ofis harness'ı sıradaki alt kartı buradan
        başlatır; Qt sinyaline bağlanmak zorunda kalsaydı harness bir olay
        döngüsü olmadan (arka plan görevi, test) çalışamazdı.
        """
        card = self.get(card_id)
        if card is None:
            return None
        if card.status == "running":
            return None

        # Ajan defteri dışarıdan verilebilir: ofis kartlarının ajanı Entropy'nin
        # kadrosunda değil, ofisin kendi `agents/` klasöründedir (Faz 6).
        registry = agent_registry or AgentRegistry(vault_path=self.vault_path)
        agent_spec = registry.get(card.agent) if card.agent else None
        # Ek-1 (Faz 9): Entropy kartı (office boş) YALNIZCA Entropy kadrosundaki
        # bir ajana koşar. Bir ofis orkestratörünün adı Entropy kartına
        # yazıldığında kart sessizce genel bir asistanla koşuyordu; iki kadro
        # birbirine karışmasın diye bu artık açık bir hata.
        if card.agent and not card.office and agent_spec is None:
            self._write(replace(
                card,
                status="failed",
                finished_at=_now(),
                summary=f"Koşulmadı: '{card.agent}' ajanı Entropy kadrosunda değil.",
            ))
            emit_terminal(f"card-{card.id}", card.agent, "failed",
                          summary=f"'{card.agent}' ajanı Entropy kadrosunda değil.",
                          vault_path=self.vault_path)
            return None
        provider = (
            card.provider
            or (agent_spec.provider if agent_spec else "")
            or default_provider()
        ).lower()
        bridge = self.bridge_for(provider, bridge_factory=bridge_factory)
        if bridge is None:
            return None

        # MODEL (Faz 9.5). Kartın `model` alanı yürütmeye HİÇ geçmiyordu: köprü
        # üst çubuğun modeliyle koşuyor, `provider: claude` olan bir kart
        # `gemini-3.1-pro-high` ile başlatılıp `unrecognized_model` ile ölüyordu.
        # Ad `resolve_model` ile sağlayıcıya çevrilir (gemini-* -> claude-opus-5)
        # ve o koşuya `model=` olarak geçirilir.
        run_model = resolve_card_model(card, agent_spec=agent_spec, provider=provider)

        prompt = self.build_prompt(card, agent_spec=agent_spec, project_path=project_path)
        needs_write = card_needs_write(card, agent_spec=agent_spec)
        task_id = f"card-{card.id}"
        card = replace(card, status="running", started_at=_now(), provider=provider)
        self._write(card)

        def _on_result(full_text: str, ok: bool, _card_id=card.id):
            self._finish(_card_id, full_text, ok)
            if on_done is not None:
                try:
                    on_done(_card_id, ok)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Kart tamamlama geri çağrısı hata verdi (%s)", _card_id
                    )

        kwargs = dict(
            task_id=task_id,
            task_name=card.title or card.id,
            prompt=prompt,
            mode="accept-edits",
            on_result=_on_result,
            save_report=True,
            agent=card.agent or None,
            # Okuma niyetli kart paylaşımlı kilitle koşar; aksi hâlde aynı
            # proje dizinindeki ikinci alt kart 60 sn bekleyip ölüyordu.
            needs_write=needs_write,
            # Adım tavanı yaptırımı: istemdeki "en çok N adım" ricası
            # tutmadığında köprü akıştaki araç olaylarını sayıp süreci öldürür.
            max_steps=MAX_STEPS_PER_CARD,
            # Kartın modeli o koşuya uygulanır; boşsa köprü oturum modelinde kalır.
            model=run_model or None,
            # Ajanın kimliği kartın sistem istemine girer (Faz 9.4).
            agent_spec=agent_spec_payload(agent_spec),
        )
        # Ofis kartı kendi çalışma dizininde koşar; derlenmiş ajan tanımı orada.
        if project_path:
            kwargs["project_path"] = str(project_path)
        # `needs_write` bilmeyen dar köprü sözleşmeleri (ve sahte köprüler) için
        # imza denetimi. TypeError'ı yakalayıp yeniden denemek yanlış olurdu:
        # köprünün KENDİ gövdesinden gelen bir TypeError görevi iki kez
        # başlatırdı.
        for optional in ("needs_write", "project_path", "max_steps", "model", "agent_spec"):
            if optional in kwargs and not _accepts_kwarg(
                bridge.send_background_task_async, optional
            ):
                kwargs.pop(optional, None)
        try:
            bridge.send_background_task_async(**kwargs)
        except Exception as exc:
            self._finish(card.id, f"Görev başlatılamadı: {exc}", False)
            if on_done is not None:
                try:
                    on_done(card.id, False)
                except Exception:
                    pass
            return None
        return task_id

    def stop(self, card_id: str) -> bool:
        """Süren kartı keser; kart `failed` olur."""
        card = self.get(card_id)
        if card is None or card.status != "running":
            return False
        killed = False
        for provider in ("agy", "claude"):
            bridge = self._bridge_cache.get(provider)
            if bridge is None:
                continue
            try:
                bridge.terminate_background_task(f"card-{card_id}")
                killed = True
            except Exception:
                continue
        try:
            from entropy.ui.manager import EntropyUIManager

            mgr = getattr(EntropyUIManager, "instance", None)
            active = getattr(mgr, "bridge", None) if mgr is not None else None
            if active is not None:
                active.terminate_background_task(f"card-{card_id}")
                killed = True
        except Exception:
            pass
        self._write(replace(card, status="failed", finished_at=_now(),
                            summary="Kullanıcı isteğiyle durduruldu."))
        emit_terminal(card.id, card.office or card.agent or "entropy", "canceled",
                      "Kullanıcı isteğiyle durduruldu.", vault_path=self.vault_path)
        return killed

    # -- tamamlama ------------------------------------------------------

    def _finish(self, card_id: str, full_text: str, ok: bool) -> None:
        """
        Görev bitince kartı günceller, wiki sayfası ve ajan belleği yazar.

        Bellek katmanı çağrıları içe aktarma koruması altında: `entropy.memory.wiki`
        ve `agent_memory` memory-rag tarafından sağlanıyor; henüz yoksa kart yine
        de doğru biçimde kapanmalı — ajan katmanı onlara bağımlı olamaz.
        """
        card = self.get(card_id)
        if card is None:
            return
        summary = (full_text or "").strip()
        outputs = list(card.output_paths or [])

        if ok and summary:
            page = self._write_wiki_page(card, summary)
            if page:
                outputs.append(str(page))
            self._append_agent_memory(card, summary)

        card = replace(
            card,
            status="review" if ok else "failed",
            finished_at=_now(),
            # Özet KIRPILMAZ: kart artık `##` başlıklı uzun çıktıyı kayıpsız
            # geri okuyabiliyor ve tek gerçek kaynak o. Kırpma, çıktının
            # tüketildiği yerde (değerlendirici prompt'u) yapılır.
            summary=summary if summary else ("Çıktı üretilmedi." if not ok else ""),
            output_paths=outputs,
        )
        self._write(card)
        # TERMİNAL SÖZLEŞMESİ (A2A): kart kapandığı ANDA terminal olay yayılır.
        # `review` de bir sondur — koşu bitti, karar insanın; asılı görevle
        # bitmiş görevi ayırt edebilmenin tek yolu bu olay.
        emit_terminal(
            card.id,
            card.office or card.agent or "entropy",
            "completed" if ok else "failed",
            (summary or "")[:500],
            vault_path=self.vault_path,
        )

    def _write_wiki_page(self, card: TaskCard, body: str):
        try:
            from entropy.memory.wiki import write_query_page  # type: ignore
        except Exception:
            return None
        try:
            return write_query_page(
                card.skill or "",
                card.title or card.id,
                body,
                {
                    "task_id": card.id,
                    "agent": card.agent,
                    "provider": card.provider,
                    "goal": card.goal,
                    # Panonun bağlı olduğu kasa; yoksa genel yapılandırma kasasına
                    # yazılır ve testler kullanıcı kasasını kirletir.
                    "vault_path": self.vault_path,
                },
            )
        except Exception:
            return None

    def _append_agent_memory(self, card: TaskCard, body: str) -> None:
        try:
            from entropy.memory.agent_memory import append_agent_memory  # type: ignore
        except Exception:
            return
        try:
            append_agent_memory(
                card.agent,
                {
                    "task_id": card.id,
                    "title": card.title,
                    "goal": card.goal,
                    "summary": body[:1000],
                    "at": _now(),
                    "vault_path": self.vault_path,
                },
            )
        except Exception:
            return
