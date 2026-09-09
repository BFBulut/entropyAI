"""
Yetenek wiki'si (v0): sorgu sayfaları, indeks ve günlük.

Neyi çözüyor
------------
Bir ajan turu bittiğinde ortaya çıkan bilgi bugün ya rapora (uzun, damıtmaya
girer) ya da hiçbir yere gitmiyor. Ama turların çoğu "rapor" değil "sorgu"dur:
"bu API şu parametreyi alıyor mu", "şu ölçüm kaç çıktı". Bunlar tekrar
edilebilir bir yordam değildir, dolayısıyla playbook damıtmasına KAYNAK
sayılmamalıdır; ama bir sonraki turda hatırlanmaları gerekir.

Bu modül o turları `Skills/<yetenek>/wiki/queries/` altına kısa, maskelenmiş
sayfalar olarak yazar, `index.md` ile kategorilere böler, `log.md` ile
append-only bir zaman çizgisi tutar ve bilişsel belleğe `category="query"`
düğümü kaydeder. Böylece geri çağırma ve bağlam kurucu bu bilgiyi görür,
damıtma görmez (bkz. playbook._NON_REPORT_DIRS).

Kasadaki kullanıcı dosyalarına dokunulmaz: yalnızca wiki/ alt ağacı yazılır.
"""

from __future__ import annotations

import datetime
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from entropy.core.config import config

logger = logging.getLogger(__name__)

# Sayfa gövdesi tavanı. Sorgu sayfası bir rapor değildir: 4000 karakter
# (~1000 token) bir turun kararını ve ölçümünü taşımaya yeter, arşivini değil.
QUERY_BODY_MAX_CHARS = 4000
# Bilişsel bellek düğümü tavanı. Geri çağırma sonuçları bağlamda 800 token'lık
# bir dilimi paylaşır; tek düğüm o dilimi tek başına yiyemez.
MEMORY_NODE_MAX_CHARS = 1500

# Yeteneksiz (genel) sorgular buraya gider.
GLOBAL_WIKI_DIRNAME = "Wiki"
DEFAULT_CATEGORY = "Sorgular"

# Ofis kartı bittiğinde yazılan sayfanın kategorisi. Sayfanın kendisi normal bir
# wiki sorgu sayfasıdır (aynı geri çağırma havuzu, aynı damıtma dışlaması);
# ofis klasörüne yalnızca wikilink'li KISA bir özet düşer, kopya değil: iki tam
# kopya olsaydı geri çağırma aynı metni iki kez sayardı.
OFFICE_REPORT_CATEGORY = "Ofis raporları"
# Ofis klasöründeki özetin gövde tavanı (karakter). Özet bir işaretçidir.
OFFICE_SUMMARY_MAX_CHARS = 600

_INDEX_HEADER = "# {title} — Wiki\n\n"
_LOG_HEADER = "# {title} — Wiki Günlüğü\n\n"

# Karpathy'nin LLM-wiki deseni: ham (raporlar) → üretilmiş sayfalar (wiki) →
# şema (GEMINI.md). Burada "üretilmiş sayfa" iki türdür:
#   concept — playbook'un bir bölümünden ("Çalışma Adımları" gibi) türeyen yordam
#             parçası; sorguya göre bağlama tek başına girebilecek büyüklükte.
#   entity  — o yordamda ve raporlarda tekrar eden ad (araç, kurum, dosya).
# İkisi de damıtmaya KAYNAK değildir (wiki/ zaten _NON_REPORT_DIRS içinde):
# playbook'tan türedikleri için kaynak sayılsalardı damıtma kendi çıktısını
# yeniden okurdu.
CONCEPT_CATEGORY = "Kavramlar"
ENTITY_CATEGORY = "Varlıklar"
PROCEDURE_CATEGORY = "Yordam"
SESSION_CATEGORY = "Oturumlar"

# İndeks başlıklarının sabit sırası. Alfabetik sıralama "Kavramlar"ı
# "Sorgular"dan önce koyar ama "Yordam"ı en sona atardı; okuma sırası
# genelden özele olmalı.
INDEX_CATEGORY_ORDER = [
    PROCEDURE_CATEGORY,
    CONCEPT_CATEGORY,
    ENTITY_CATEGORY,
    DEFAULT_CATEGORY,
    OFFICE_REPORT_CATEGORY,
    SESSION_CATEGORY,
]

# Tek bir kavram/varlık sayfası gövde tavanı (karakter). Bağlam kurucu wiki
# sayfalarına 400 token (~1600 karakter) ayırır; sayfanın tek başına o dilimi
# aşması bir işe yaramaz, yalnızca kırpılır.
WIKI_PAGE_MAX_CHARS = 2400
# Bir damıtmadan üretilecek azami varlık sayfası. Sezgisel çıkarım gürültülüdür;
# üst sınır olmadan tek playbook 60+ öksüz sayfa üretiyor.
MAX_ENTITY_PAGES = 12
# Çok kelimeli aday için asgari geçiş sayısı. Tek geçen büyük harfli ikili
# çoğunlukla cümle başıdır, varlık değil.
MIN_ENTITY_OCCURRENCES = 2


# ---------------------------------------------------------------- yardımcılar


def _mask(text: str) -> str:
    """Araç çıktısı maskesi; ortak yardımcı yoksa metin olduğu gibi kalır."""
    try:
        from entropy.core.masking import mask_tool_output

        return mask_tool_output(text or "")
    except Exception:  # pragma: no cover - ortak maske her zaman var
        return text or ""


def _safe(name: str) -> str:
    """Dizin adı olarak güvenli yetenek adı (PlaybookStore._safe ile aynı kural)."""
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in (name or "")).strip()
    return cleaned or "skill"


def _slugify(text: str, max_len: int = 60) -> str:
    raw = (text or "").strip().lower()
    raw = raw.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    raw = raw.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return (raw[:max_len].rstrip("-")) or "sorgu"


def _vault_root(vault_path: Optional[Path] = None) -> Path:
    return Path(vault_path) if vault_path else Path(config.obsidian_vault_path)


def wiki_dir(skill: Optional[str], vault_path: Optional[Path] = None) -> Path:
    """Yeteneğin wiki kökü; yetenek boşsa kasa geneli `Entropy/Wiki/`."""
    root = _vault_root(vault_path) / "Entropy"
    if skill and str(skill).strip():
        return root / "Skills" / _safe(skill) / "wiki"
    return root / GLOBAL_WIKI_DIRNAME


def queries_dir(skill: Optional[str], vault_path: Optional[Path] = None) -> Path:
    return wiki_dir(skill, vault_path) / "queries"


def concepts_dir(skill: Optional[str], vault_path: Optional[Path] = None) -> Path:
    return wiki_dir(skill, vault_path) / "concepts"


def entities_dir(skill: Optional[str], vault_path: Optional[Path] = None) -> Path:
    return wiki_dir(skill, vault_path) / "entities"


def offices_dir(vault_path: Optional[Path] = None) -> Path:
    """Ofis kökü. Faz 6'da Desk ayrıldı: `Entropy/Desk/Offices` tek kaynaktır."""
    from entropy.memory.office_graph import desk_offices_dir

    return desk_offices_dir(vault_path)


def office_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    return offices_dir(vault_path) / _safe(office)


def office_reports_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    return office_dir(office, vault_path) / "reports"


def _frontmatter_value(text: str, key: str) -> str:
    m = re.search(rf"(?m)^{re.escape(key)}\s*:\s*(.+?)\s*$", text or "")
    if not m:
        return ""
    return m.group(1).strip().strip('"').strip("'")


def _wikilink(path: Any) -> str:
    """Yol ya da metinden `[[stem]]` üretir."""
    s = str(path or "").strip()
    if not s:
        return ""
    stem = Path(s).stem if ("/" in s or "\\" in s or s.lower().endswith(".md")) else s
    return f"[[{stem}]]"


# ------------------------------------------------------------- sayfa yazımı


def _render_query_page(
    skill: str,
    title: str,
    body: str,
    meta: Dict[str, Any],
    sources: List[str],
) -> str:
    created = str(meta.get("created") or datetime.datetime.now().isoformat(timespec="seconds"))
    category = str(meta.get("category") or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY
    fm = [
        "---",
        f"type: query",
        f"skill: {skill}",
        f'title: "{title}"',
        f"category: {category}",
        f"agent: {meta.get('agent') or ''}",
        f"provider: {meta.get('provider') or ''}",
        f"model: {meta.get('model') or ''}",
        f"task_id: {meta.get('task_id') or ''}",
        f"created: {created}",
    ]
    if sources:
        fm.append("sources:")
        fm.extend(f"  - {s}" for s in sources)
    else:
        fm.append("sources: []")
    fm.append("---")

    parts = ["\n".join(fm), "", f"# {title}", "", body.strip()]
    if sources:
        parts += ["", "## Kaynaklar", ""]
        parts += [f"- {_wikilink(s)}" for s in sources if _wikilink(s)]
    return "\n".join(parts).rstrip() + "\n"


def write_query_page(skill: str, title: str, body: str, meta: dict) -> Path:
    """
    Bir sorgu turunu wiki sayfası olarak yazar ve yolunu döndürür.

    Yan etkileri: `index.md` ve `log.md` güncellenir, bilişsel belleğe
    `category="query"` düğümü yazılır. Bellek yazımı başarısız olursa sayfa yine
    de kalır: kalıcı olan dosyadır, düğüm ondan yeniden üretilebilir.

    `meta` anahtarları: agent, provider, model, task_id, created, category,
    output_paths (kaynak çıktılar), vault_path (test/izolasyon), memory
    (bellek sistemi enjeksiyonu).
    """
    meta = dict(meta or {})
    vault_path = meta.get("vault_path")
    title = (str(title or "").strip() or "Sorgu")[:160]

    sources = [str(p) for p in (meta.get("output_paths") or []) if str(p).strip()]

    masked = _mask(str(body or ""))
    if len(masked) > QUERY_BODY_MAX_CHARS:
        masked = masked[: QUERY_BODY_MAX_CHARS - 1].rstrip() + "…"

    target = queries_dir(skill, vault_path)
    target.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    slug = _slugify(title)
    path = target / f"{today}-{slug}.md"
    n = 2
    while path.exists():
        path = target / f"{today}-{slug}-{n}.md"
        n += 1

    path.write_text(_render_query_page(skill or "", title, masked, meta, sources), encoding="utf-8")

    try:
        rebuild_wiki_index(skill, vault_path=vault_path)
    except Exception as exc:  # pragma: no cover - indeks sayfayı düşürmemeli
        logger.warning("Wiki indeksi güncellenemedi (%s): %s", skill, exc)
    try:
        append_wiki_log(skill, title, str(meta.get("agent") or "bilinmiyor"), vault_path=vault_path)
    except Exception as exc:  # pragma: no cover
        logger.warning("Wiki günlüğü yazılamadı (%s): %s", skill, exc)

    office = str(meta.get("office") or "").strip()
    category = str(meta.get("category") or "").strip()
    if office and category == OFFICE_REPORT_CATEGORY:
        try:
            write_office_report_summary(office, title, path, masked, meta, sources)
        except Exception as exc:  # pragma: no cover - özet sayfayı düşürmemeli
            logger.warning("Ofis raporu özeti yazılamadı (%s): %s", office, exc)
        # Faz 7: yeni ofis raporu = ofis belleğinin Entropy grafına akma anı.
        # Modelsiz, kota harcamayan alım; arka planda ve aralık kısıtlı.
        # `vault_path` verilmişse (test/izolasyon) tetiklenmez: izole bir kasanın
        # içeriği üretim grafına yazılmamalı.
        try:
            if not vault_path:
                from entropy.memory.office_graph import schedule_office_ingest

                schedule_office_ingest(background=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("Ofis alımı tetiklenemedi (%s): %s", office, exc)

    _store_query_node(path, skill, title, masked, meta, sources)
    return path


def append_office_log(
    office: str,
    title: str,
    agent: str = "",
    vault_path: Optional[Path] = None,
    kind: str = "report",
) -> Path:
    """Ofisin `log.md`'sine append-only tek satır ekler."""
    root = office_dir(office, vault_path)
    root.mkdir(parents=True, exist_ok=True)
    log = root / "log.md"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{stamp}] {kind}: {title} ({agent or 'bilinmiyor'})" + "\n"
    header = "" if log.exists() else f"# {office} — Ofis Günlüğü" + "\n\n"
    with open(log, "a", encoding="utf-8") as f:
        f.write(header + line)
    return log


def write_office_report_summary(
    office: str,
    title: str,
    page_path: Path,
    masked_body: str,
    meta: Dict[str, Any],
    sources: Optional[List[str]] = None,
) -> Path:
    """
    Ofis klasörüne wikilink'li KISA özet yazar ve ofis günlüğünü günceller.

    Tam metin wiki sorgu sayfasında kalır (`page_path`); burada yalnızca
    başlık, not, alt kart sayısı ve sayfaya bağ vardır. Kopya değildir:
    geri çağırma havuzuna wiki sayfası girer, bu dosya bir işaretçidir.
    """
    vault_path = meta.get("vault_path")
    sources = list(sources or [])
    target = office_reports_dir(office, vault_path)
    target.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    slug = _slugify(title)
    path = target / f"{today}-{slug}.md"
    n = 2
    while path.exists():
        path = target / f"{today}-{slug}-{n}.md"
        n += 1

    summary = (masked_body or "").strip()
    if len(summary) > OFFICE_SUMMARY_MAX_CHARS:
        summary = summary[: OFFICE_SUMMARY_MAX_CHARS - 1].rstrip() + "…"

    fm = [
        "---",
        "type: office_report",
        f"office: {office}",
        f"skill: {meta.get('skill') or ''}",
        f'title: "{title}"',
        f"category: {OFFICE_REPORT_CATEGORY}",
        f"agent: {meta.get('agent') or ''}",
        f"task_id: {meta.get('task_id') or ''}",
        f"grade: {meta.get('grade') if meta.get('grade') is not None else ''}",
        f"children_count: {meta.get('children_count') if meta.get('children_count') is not None else ''}",
        f"page: {page_path.stem}",
        f"created: {meta.get('created') or datetime.datetime.now().isoformat(timespec='seconds')}",
        "---",
    ]
    parts = [
        "\n".join(fm),
        "",
        f"# {title}",
        "",
        f"Tam sayfa: {_wikilink(page_path)}",
        "",
        "## Özet",
        "",
        summary,
    ]
    if sources:
        parts += ["", "## Çıktılar", ""] + [f"- {_wikilink(s)}" for s in sources if _wikilink(s)]
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    try:
        append_office_log(office, title, str(meta.get("agent") or "bilinmiyor"), vault_path=vault_path)
    except Exception as exc:  # pragma: no cover
        logger.warning("Ofis günlüğü yazılamadı (%s): %s", office, exc)
    return path


def _store_query_node(
    path: Path,
    skill: str,
    title: str,
    masked_body: str,
    meta: Dict[str, Any],
    sources: List[str],
) -> bool:
    """Sorguyu bilişsel belleğe `query` düğümü olarak yazar; başarılıysa True."""
    try:
        memory = meta.get("memory")
        if memory is None:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

            memory = CognitiveMemorySystem()
        content = f"{title}\n{masked_body}".strip()
        if len(content) > MEMORY_NODE_MAX_CHARS:
            content = content[: MEMORY_NODE_MAX_CHARS - 1].rstrip() + "…"
        memory.store_node(
            category="query",
            content=content,
            importance=0.6,
            metadata={
                "kind": "wiki_query",
                "path": str(path),
                "skill": skill or "",
                "agent": meta.get("agent") or "",
                "task_id": meta.get("task_id") or "",
                "sources": sources,
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            },
        )
        return True
    except Exception as exc:
        logger.warning("Sorgu için bellek düğümü yazılamadı (%s): %s", path, exc)
        return False


# ------------------------------------------------------------ indeks/günlük


def append_wiki_log(
    skill: Optional[str],
    title: str,
    agent: str = "",
    vault_path: Optional[Path] = None,
    kind: str = "query",
) -> Path:
    """`log.md`'ye append-only tek satır ekler; dosya yoksa başlıkla oluşturur."""
    root = wiki_dir(skill, vault_path)
    root.mkdir(parents=True, exist_ok=True)
    log = root / "log.md"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{stamp}] {kind}: {title} ({agent or 'bilinmiyor'})\n"
    header = "" if log.exists() else _LOG_HEADER.format(title=skill or "Entropy")
    with open(log, "a", encoding="utf-8") as f:
        f.write(header + line)
    return log


def _query_pages(skill: Optional[str], vault_path: Optional[Path] = None) -> List[Path]:
    d = queries_dir(skill, vault_path)
    if not d.is_dir():
        return []
    # Dosya adı tarihle başlar: ad sıralaması kronolojiktir ve OneDrive'da
    # güvenilmeyen mtime'a bağlı kalmaz.
    return sorted(d.glob("*.md"), key=lambda p: p.name, reverse=True)


def rebuild_wiki_index(skill: Optional[str], vault_path: Optional[Path] = None) -> Path:
    """
    `index.md`'yi mevcut playbook + sorgu sayfalarından yeniden kurar.

    İndeks türetilmiş bir dosyadır: elle düzenlenmesi beklenmez, her yazımda
    diskteki gerçeğe göre yeniden üretilir. Kategori başlıkları sayfaların
    frontmatter'ındaki `category` alanından gelir.
    """
    root = wiki_dir(skill, vault_path)
    root.mkdir(parents=True, exist_ok=True)
    index = root / "index.md"

    lines: List[str] = [_INDEX_HEADER.format(title=skill or "Entropy").rstrip("\n"), ""]

    playbook = root.parent / "PLAYBOOK.md"
    if skill and playbook.is_file():
        lines += ["## Yordam", "", f"- [[{playbook.stem}]] — damıtılmış çalışma yordamı", ""]

    grouped: Dict[str, List[str]] = {}
    pages = list(_query_pages(skill, vault_path))
    # Üretilmiş sayfalar da indekse girer; kategori frontmatter'daki `category`
    # alanından gelir, dizin adından değil (dizin bir uygulama detayıdır).
    for extra in (concepts_dir(skill, vault_path), entities_dir(skill, vault_path)):
        if extra.is_dir():
            pages.extend(sorted(extra.glob("*.md"), key=lambda p: p.name))
    for page in pages:
        try:
            text = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        category = _frontmatter_value(text, "category") or DEFAULT_CATEGORY
        title = _frontmatter_value(text, "title") or page.stem
        created = _frontmatter_value(text, "created")[:10]
        entry = f"- [[{page.stem}]] — {title}" + (f" ({created})" if created else "")
        grouped.setdefault(category, []).append(entry)

    ordered = [c for c in INDEX_CATEGORY_ORDER if c in grouped]
    ordered += [c for c in sorted(grouped) if c not in INDEX_CATEGORY_ORDER]
    for category in ordered:
        lines += [f"## {category}", ""] + grouped[category] + [""]

    if not grouped and not (skill and playbook.is_file()):
        lines += ["_Henüz sayfa yok._", ""]

    index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return index


# ------------------------------------------------- playbook → wiki sayfaları

# Cümle başı büyük harfli sözcükler varlık değildir; en sık görülenleri eleriz.
_ENTITY_STOPWORDS = {
    "bu", "su", "şu", "her", "bir", "ve", "ama", "eger", "eğer", "not", "ayrica",
    "ayrıca", "once", "önce", "sonra", "adim", "adım", "adimlar", "adımlar",
    "asla", "daima", "tum", "tüm", "hangi", "neden", "nasil", "nasıl", "ornek",
    "örnek", "ozet", "özet", "sonuc", "sonuç", "karar", "girdi", "cikti", "çıktı",
    "kaynak", "kaynaklar", "yordam", "kural", "kurallar", "asama", "aşama",
    "toplam", "yeni", "eski", "varsa", "yoksa", "icin", "için", "the", "and",
}

# Çok kelimeli özel ad: art arda en az iki büyük harfle başlayan sözcük.
_ENTITY_MULTIWORD_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]{1,}(?:\s+[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]{1,}){1,3})\b"
)
# Araç/dosya adı: geri tırnak içi (`agy`, `PLAYBOOK.md`).
_ENTITY_BACKTICK_RE = re.compile(r"`([A-Za-z][\w\-\./]{1,40})`")
# İç büyük harfli tek sözcük (PySide6, GitHub, SkillPlaybook) — Türkçede cümle
# başı bu kalıbı üretmez, dolayısıyla tek geçiş bile yeterlidir.
_ENTITY_CAMEL_RE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+)\b")


def split_playbook_sections(procedure: str) -> List[tuple]:
    """
    Playbook gövdesini `(başlık, gövde)` çiftlerine böler (## ve ### seviyeleri).

    Başlıksız bir giriş paragrafı yok sayılır: kavram sayfasının adı başlıktan
    gelir, adsız bir sayfa indeksi kirletir.
    """
    out: List[tuple] = []
    title: Optional[str] = None
    buf: List[str] = []
    for line in (procedure or "").splitlines():
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if m:
            if title:
                out.append((title, "\n".join(buf).strip()))
            title = m.group(1).strip()
            buf = []
        elif title:
            buf.append(line)
    if title:
        out.append((title, "\n".join(buf).strip()))
    return out


def extract_entities(
    texts: List[str],
    exclude: Optional[List[str]] = None,
    must_appear_in: Optional[str] = None,
) -> List[str]:
    """
    Metinlerden varlık adaylarını sezgisel olarak çıkarır (LLM YOK).

    Üç kalıp: çok kelimeli özel ad, geri tırnaklı araç/dosya adı, iç büyük
    harfli tek sözcük. Çok kelimeli adaylar için asgari geçiş sayısı aranır;
    tek geçen büyük harfli ikili çoğunlukla cümle başıdır. Sonuç sıklığa göre
    sıralı ve MAX_ENTITY_PAGES ile sınırlıdır.

    `must_appear_in` verilirse aday o metinde de geçmelidir. Çağıran bunu
    playbook gövdesiyle doldurur: yalnızca rapor BAŞLIĞINDA geçen bir ad hiçbir
    kavram sayfasından bağ almaz ve doğduğu anda öksüz bir sayfa olur.
    """
    blob = "\n".join(t for t in texts if t)
    if not blob.strip():
        return []
    banned = {(e or "").strip().lower() for e in (exclude or [])}
    counts: Dict[str, int] = {}
    strong: Dict[str, bool] = {}

    def _add(name: str, is_strong: bool) -> None:
        name = re.sub(r"\s+", " ", (name or "").strip(" .,:;()[]"))
        if len(name) < 3 or len(name) > 60:
            return
        if name.lower() in banned:
            return
        words = name.split()
        if words[0].lower() in _ENTITY_STOPWORDS:
            return
        if all(len(w) <= 2 for w in words):
            return
        counts[name] = counts.get(name, 0) + 1
        strong[name] = strong.get(name, False) or is_strong

    for m in _ENTITY_MULTIWORD_RE.finditer(blob):
        _add(m.group(1), False)
    for m in _ENTITY_BACKTICK_RE.finditer(blob):
        _add(m.group(1), True)
    for m in _ENTITY_CAMEL_RE.finditer(blob):
        _add(m.group(1), True)

    anchor = (must_appear_in or "").lower()
    picked = [
        (n, c) for n, c in counts.items()
        if (strong.get(n) or c >= MIN_ENTITY_OCCURRENCES)
        and (not anchor or n.lower() in anchor)
    ]
    picked.sort(key=lambda x: (-x[1], x[0].lower()))
    return [n for n, _ in picked[:MAX_ENTITY_PAGES]]


def _render_generated_page(
    page_type: str,
    skill: str,
    title: str,
    category: str,
    body: str,
    sources: List[str],
    links: List[str],
    created: str,
    source_version: int = 0,
) -> str:
    """Kavram/varlık sayfasının tam metni (ön bilgi + gövde + çapraz bağlar)."""
    fm = [
        "---",
        f"type: {page_type}",
        f"skill: {skill}",
        f'title: "{title}"',
        f"category: {category}",
        f"source_version: {source_version}",
        f"created: {created}",
        f"updated: {datetime.datetime.now().isoformat(timespec='seconds')}",
    ]
    if sources:
        fm.append("sources:")
        fm.extend(f"  - {_wikilink(s)}" for s in sources if _wikilink(s))
    else:
        fm.append("sources: []")
    fm.append("---")

    parts = ["\n".join(fm), "", f"# {title}", "", (body or "").strip()]
    if links:
        seen = []
        for l in links:
            w = _wikilink(l)
            if w and w not in seen:
                seen.append(w)
        if seen:
            parts += ["", "## İlgili", ""] + [f"- {w}" for w in seen]
    if sources:
        parts += ["", "## Kaynaklar", ""] + [f"- {_wikilink(s)}" for s in sources if _wikilink(s)]
    return "\n".join(parts).rstrip() + "\n"


def _existing_created(path: Path) -> Optional[str]:
    """Sayfa varsa `created` alanını korur: yeniden üretim doğum tarihini silmez."""
    try:
        return _frontmatter_value(path.read_text(encoding="utf-8", errors="ignore"), "created") or None
    except OSError:
        return None


def ingest_playbook_to_wiki(
    skill: str,
    vault_path: Optional[Path] = None,
    store: Any = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    PLAYBOOK.md'den kavram ve varlık sayfaları üretir (LLM YOK, kota harcamaz).

    Kaynak yalnızca damıtılmış yordam ve yeteneğin rapor BAŞLIKLARIdır; rapor
    gövdeleri okunmaz, böylece maliyet arşivin boyutuna bağlanmaz. `dry_run`
    hiçbir şey yazmadan aynı sayımı döndürür: gerçek kasada güvenle ölçülür.

    Dönen: {"skill", "concepts", "entities", "written", "pages", "index", "log"}
    """
    from entropy.memory.playbook import PlaybookStore

    store = store or PlaybookStore(vault_path=vault_path)
    vault_path = vault_path if vault_path is not None else store.vault_path
    pb = store.load(skill)
    result: Dict[str, Any] = {
        "skill": skill,
        "concepts": [],
        "entities": [],
        "written": 0,
        "pages": [],
        "index": None,
        "log": None,
        "reason": "",
    }
    if pb is None or not (pb.procedure or "").strip():
        result["reason"] = "playbook yok"
        return result

    sections = split_playbook_sections(pb.procedure)
    if not sections:
        result["reason"] = "playbook'ta başlık yok"
        return result

    try:
        reports = list(store.source_reports(skill))
    except Exception:  # pragma: no cover - rapor listesi sayfa üretimini düşürmemeli
        reports = []
    report_titles = [p.stem for p in reports]
    playbook_link = store.playbook_path(skill).stem

    headings = [t for t, _ in sections]
    entities = extract_entities(
        [pb.procedure] + report_titles,
        exclude=headings + [skill, playbook_link],
        must_appear_in=pb.procedure,
    )
    result["concepts"] = list(headings)
    result["entities"] = list(entities)
    if dry_run:
        result["written"] = len(headings) + len(entities)
        return result

    now = datetime.datetime.now().isoformat(timespec="seconds")
    c_dir = concepts_dir(skill, vault_path)
    e_dir = entities_dir(skill, vault_path)
    c_dir.mkdir(parents=True, exist_ok=True)
    if entities:
        e_dir.mkdir(parents=True, exist_ok=True)

    # Sayfa adı yetenekle ön eklenir: iki yeteneğin "Çıktı Biçimi" sayfası aynı
    # stem'i taşısaydı Obsidian wikilink'leri birbirine karışırdı.
    prefix = _slugify(skill, 24)
    concept_paths: Dict[str, Path] = {
        title: c_dir / f"{prefix}-{_slugify(title)}.md" for title in headings
    }
    entity_paths: Dict[str, Path] = {
        name: e_dir / f"{prefix}-{_slugify(name)}.md" for name in entities
    }

    written: List[Path] = []
    for title, body in sections:
        path = concept_paths[title]
        # Çapraz bağ: bu bölümde adı geçen varlıklar + diğer kavram sayfaları.
        mentioned = [n for n in entities if n.lower() in body.lower()]
        links = [str(entity_paths[n]) for n in mentioned]
        links += [str(p) for t, p in concept_paths.items() if t != title]
        links.append(playbook_link)
        text = _render_generated_page(
            "concept", skill, title, CONCEPT_CATEGORY,
            (body or "")[:WIKI_PAGE_MAX_CHARS],
            sources=[playbook_link], links=links,
            created=_existing_created(path) or now,
            source_version=int(getattr(pb, "version", 0) or 0),
        )
        path.write_text(text, encoding="utf-8")
        written.append(path)

    for name in entities:
        path = entity_paths[name]
        low = name.lower()
        in_sections = [t for t, b in sections if low in b.lower()]
        src_reports = [p for p in report_titles if low in p.lower()]
        lines = [f"`{name}` — {skill} yordamında ve raporlarında geçen ad."]
        if in_sections:
            lines += ["", "Geçtiği bölümler: " + ", ".join(in_sections) + "."]
        text = _render_generated_page(
            "entity", skill, name, ENTITY_CATEGORY,
            "\n".join(lines),
            sources=[playbook_link] + src_reports[:5],
            links=[str(concept_paths[t]) for t in in_sections],
            created=_existing_created(path) or now,
            source_version=int(getattr(pb, "version", 0) or 0),
        )
        path.write_text(text, encoding="utf-8")
        written.append(path)

    result["written"] = len(written)
    result["pages"] = [str(p) for p in written]
    try:
        result["index"] = str(rebuild_wiki_index(skill, vault_path=vault_path))
    except Exception as exc:  # pragma: no cover
        logger.warning("Wiki indeksi güncellenemedi (%s): %s", skill, exc)
    try:
        result["log"] = str(append_wiki_log(
            skill,
            f"{len(headings)} kavram, {len(entities)} varlık sayfası üretildi "
            f"(playbook v{getattr(pb, 'version', 0)})",
            agent="wiki",
            vault_path=vault_path,
            kind="ingest",
        ))
    except Exception as exc:  # pragma: no cover
        logger.warning("Wiki günlüğü yazılamadı (%s): %s", skill, exc)
    return result
