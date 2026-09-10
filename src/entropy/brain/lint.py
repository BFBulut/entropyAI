"""
Wiki sağlık denetimi (`/lint`): LLM'siz, kota harcamayan tutarlılık kontrolü.

Neyi çözüyor
------------
Wiki katmanı (bkz. memory/wiki.py) türetilmiş sayfalar üretir: kavramlar
playbook'un bölümlerinden, varlıklar sezgisel çıkarımdan gelir. Türetilmiş
her katman bayatlar: playbook yeni sürüme geçer ama sayfalar eski sürümde
kalır, bir sayfa silinir ama ona giden `[[bağ]]` kalır, bir varlık iki farklı
sayısal değerle anılır. Bunların hiçbirini görmek için model çağırmak gerekmez;
hepsi dosya sisteminde ve metinde görünen olgulardır.

Denetimler
----------
  orphan          hiç bağ almayan sayfa (üretildi ama kimse göstermiyor)
  broken_link     hedefi kasada bulunmayan `[[wikilink]]`
  stale           kaynağı playbook'un güncel sürümünden eski sayfa
  missing_concept playbook'ta başlık var, kavram sayfası yok
  contradiction   aynı varlık için farklı sayısal değer/tarih (regex sezgisi)
  unread_report   damıtmaya girmemiş kaynak rapor
  open_task       aktarım sayfasındaki kapanmamış "Açık İşler" maddesi

Çıktı: sohbete HTML tablo, kasaya `Skills/<yetenek>/wiki/lint.md`. Kullanıcı
dosyalarına dokunulmaz; yalnızca wiki/ altındaki lint.md yazılır.
"""

from __future__ import annotations

import datetime
import html as _html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from entropy.brain.wiki import (
    concepts_dir,
    entities_dir,
    queries_dir,
    split_playbook_sections,
    wiki_dir,
)

logger = logging.getLogger(__name__)

# Denetim kimliği → insan okur etiketi. Sıra çıktı sırasıdır: önce yapısal
# bozukluk (kırık bağ), sonra bayatlık, en sonda içerik şüphesi.
CHECK_LABELS = {
    "broken_link": "Kırık bağ",
    "orphan": "Öksüz sayfa",
    "stale": "Bayat sayfa",
    "missing_concept": "Eksik kavram sayfası",
    "contradiction": "Çelişki adayı",
    "unread_report": "Okunmamış rapor",
    "open_task": "Kapanmamış iş",
}
CHECK_ORDER = list(CHECK_LABELS)

# Çelişki sezgisi: bir varlık sayfasının adı geçen satırlardaki sayı/tarih.
# Birimsiz sayı çelişki sinyali DEĞİLDİR: "1." ile başlayan madde numaraları ve
# sürüm numaraları her sayfada farklıdır ve hepsi doğrudur. Yalnızca birimli
# değerler (ve tarihler) iddia sayılır.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(%|TL|USD|EUR|₺|\$)|"
                        r"(?<![\w.])(%)\s*(\d{1,3}(?:[.,]\d+)?)")
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4})\b")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*)?\]\]")
# Aktarım sayfasında kapanmamış madde: "—" boş bölüm işaretidir, iş değildir.
_OPEN_TASK_HEADING = "Açık İşler"

# Tek denetimde raporlanacak azami bulgu. Lint bir liste değil bir sinyaldir;
# 400 satırlık tablo okunmaz.
MAX_FINDINGS_PER_CHECK = 25


@dataclass
class LintFinding:
    check: str
    page: str
    message: str

    @property
    def label(self) -> str:
        return CHECK_LABELS.get(self.check, self.check)


@dataclass
class LintResult:
    skill: str
    findings: List[LintFinding] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def by_check(self) -> Dict[str, List[LintFinding]]:
        out: Dict[str, List[LintFinding]] = {}
        for f in self.findings:
            out.setdefault(f.check, []).append(f)
        return out

    def counts(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self.by_check().items()}

    @property
    def total(self) -> int:
        return len(self.findings)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _fm(text: str, key: str) -> str:
    m = re.search(rf"(?m)^{re.escape(key)}\s*:\s*(.+?)\s*$", text or "")
    return m.group(1).strip().strip('"').strip("'") if m else ""


def _vault_root(vault_path: Optional[Path]) -> Path:
    if vault_path is not None:
        return Path(vault_path)
    from entropy.core.config import config

    return Path(config.obsidian_vault_path)


def _all_stems(vault_path: Optional[Path], cache: Optional[Dict[str, Set[str]]] = None) -> Set[str]:
    """
    Kasadaki tüm markdown dosya adları (wikilink hedefi çözümü için).

    `cache` verilirse tarama yetenek başına değil kasa başına bir kez yapılır:
    `/lint all` 20 yetenekte 20 kez rglob çalıştırıyordu ve maliyet yetenek
    sayısıyla değil kasa boyutuyla ölçeklenmeli.
    """
    root = _vault_root(vault_path) / "Entropy"
    key = str(root)
    if cache is not None and key in cache:
        return cache[key]
    stems = {p.stem for p in root.rglob("*.md")} if root.is_dir() else set()
    if cache is not None:
        cache[key] = stems
    return stems


def _wiki_pages(skill: str, vault_path: Optional[Path]) -> List[Path]:
    out: List[Path] = []
    for d in (concepts_dir(skill, vault_path), entities_dir(skill, vault_path),
              queries_dir(skill, vault_path)):
        if d.is_dir():
            out.extend(sorted(d.glob("*.md")))
    return out


def _numeric_claims(text: str, name: str) -> Set[str]:
    """Adın geçtiği satırlardaki sayı ve tarihleri döndürür (çelişki sezgisi)."""
    claims: Set[str] = set()
    low = name.lower()
    for line in (text or "").splitlines():
        if low not in line.lower():
            continue
        # Başlık ve bağ satırları bilgi taşımaz; slug içindeki rakamları
        # (2026-09-09-rapor gibi) çelişki sanmamak için elenir.
        if line.lstrip().startswith(("#", "- [[", "  - ")) or "[[" in line:
            continue
        for m in _DATE_RE.finditer(line):
            claims.add(m.group(1))
        for m in _NUMBER_RE.finditer(line):
            if m.group(1):
                claims.add(f"{m.group(1)}{m.group(2)}")
            else:
                claims.add(f"{m.group(3)}{m.group(4)}")
    return claims


def lint_skill(skill: str, vault_path: Optional[Path] = None, store: Any = None,
               stem_cache: Optional[Dict[str, Set[str]]] = None) -> LintResult:
    """
    Bir yeteneğin wiki'sini denetler; hiçbir dosya yazmaz (rapor ayrı işlevdir).
    """
    from entropy.brain.playbook import PlaybookStore

    store = store or PlaybookStore(vault_path=vault_path)
    vault_path = vault_path if vault_path is not None else store.vault_path
    result = LintResult(skill=skill)

    pb = store.load(skill)
    pages = _wiki_pages(skill, vault_path)
    stems = _all_stems(vault_path, stem_cache)
    texts = {p: _read(p) for p in pages}

    result.stats = {
        "pages": len(pages),
        "playbook_version": int(getattr(pb, "version", 0) or 0) if pb else 0,
        "concepts": sum(1 for t in texts.values() if _fm(t, "type") == "concept"),
        "entities": sum(1 for t in texts.values() if _fm(t, "type") == "entity"),
    }

    # --- kırık bağlar ve gelen bağ sayacı ---------------------------------
    incoming: Dict[str, int] = {p.stem: 0 for p in pages}
    scan_files = list(pages)
    if pb is not None:
        scan_files.append(store.playbook_path(skill))
    index_page = wiki_dir(skill, vault_path) / "index.md"
    if index_page.is_file():
        scan_files.append(index_page)

    for path in scan_files:
        text = texts.get(path) or _read(path)
        for m in _WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target:
                continue
            if target in incoming and path.stem != target:
                # İndeks her sayfaya bağlar; öksüzlüğü indeks değil içerik
                # bağları belirlemeli, yoksa hiçbir sayfa öksüz görünmez.
                if path != index_page:
                    incoming[target] += 1
            elif target not in stems:
                result.findings.append(LintFinding(
                    "broken_link", path.stem, f"`[[{target}]]` kasada yok"))

    # --- öksüz sayfalar ---------------------------------------------------
    for p in pages:
        if incoming.get(p.stem, 0) == 0:
            result.findings.append(LintFinding(
                "orphan", p.stem, "hiçbir sayfadan bağ almıyor"))

    # --- bayat sayfalar ---------------------------------------------------
    pb_version = result.stats["playbook_version"]
    if pb is not None:
        for p in pages:
            t = texts.get(p, "")
            if _fm(t, "type") not in ("concept", "entity"):
                continue
            try:
                sv = int(_fm(t, "source_version") or 0)
            except ValueError:
                sv = 0
            if sv < pb_version:
                result.findings.append(LintFinding(
                    "stale", p.stem,
                    f"kaynak sürüm v{sv}, playbook v{pb_version}"))

    # --- eksik kavram sayfaları -------------------------------------------
    if pb is not None:
        have = {_fm(texts.get(p, ""), "title").lower()
                for p in pages if _fm(texts.get(p, ""), "type") == "concept"}
        for title, _body in split_playbook_sections(pb.procedure):
            if title.lower() not in have:
                result.findings.append(LintFinding(
                    "missing_concept", title, "playbook başlığının kavram sayfası yok"))

    # --- çelişki adayları --------------------------------------------------
    entity_names = [
        _fm(texts.get(p, ""), "title") for p in pages
        if _fm(texts.get(p, ""), "type") == "entity"
    ]
    for name in [n for n in entity_names if n]:
        seen: Dict[str, List[str]] = {}
        for p in pages:
            for claim in _numeric_claims(texts.get(p, ""), name):
                seen.setdefault(claim, []).append(p.stem)
        if len(seen) > 1:
            claims = ", ".join(sorted(seen)[:4])
            where = ", ".join(sorted({s for v in seen.values() for s in v})[:3])
            result.findings.append(LintFinding(
                "contradiction", name,
                f"farklı değerler: {claims} ({where})"))

    # --- okunmamış raporlar ------------------------------------------------
    try:
        sources = list(store.source_reports(skill))
        processed = store.processed_among(skill, sources)
        if processed is None:
            read_n = int(getattr(pb, "processed_count", 0) or 0) if pb else 0
            unread = max(0, len(sources) - read_n)
        else:
            unread = max(0, len(sources) - len(processed))
        result.stats["reports"] = len(sources)
        result.stats["unread"] = unread
        if unread:
            result.findings.append(LintFinding(
                "unread_report", skill,
                f"{unread}/{len(sources)} rapor damıtmaya girmedi"))
    except Exception as exc:  # pragma: no cover - rapor sayımı denetimi düşürmemeli
        logger.warning("Okunmamış rapor sayılamadı (%s): %s", skill, exc)

    # --- kapanmamış aktarım işleri ----------------------------------------
    result.findings.extend(_open_task_findings(vault_path))

    # Denetim başına tavan: bulgular sinyaldir, döküm değil.
    trimmed: List[LintFinding] = []
    per_check: Dict[str, int] = {}
    for f in result.findings:
        per_check[f.check] = per_check.get(f.check, 0) + 1
        if per_check[f.check] <= MAX_FINDINGS_PER_CHECK:
            trimmed.append(f)
    result.findings = trimmed
    return result


def _open_task_findings(vault_path: Optional[Path]) -> List[LintFinding]:
    """En yeni aktarım sayfasındaki kapanmamış "Açık İşler" maddeleri."""
    out: List[LintFinding] = []
    try:
        from entropy.brain.handoff import sessions_dir
    except Exception:  # pragma: no cover
        return out
    d = sessions_dir(vault_path)
    if not d.is_dir():
        return out
    pages = sorted((p for p in d.glob("*.md") if p.stem.lower() != "log"),
                   key=lambda p: p.name, reverse=True)
    if not pages:
        return out
    page = pages[0]
    text = _read(page)
    m = re.search(rf"(?ms)^##\s+{re.escape(_OPEN_TASK_HEADING)}\s*$(.*?)(?=^##\s|\Z)", text)
    if not m:
        return out
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s.startswith("- ") or s in ("- —", "-"):
            continue
        item = s[2:].strip()
        # Kapanmış madde: tamamlanmış onay kutusu.
        if item.startswith("[x]") or item.startswith("[X]") or item == "—":
            continue
        out.append(LintFinding("open_task", page.stem, item[:160]))
    return out


def lint_vault(vault_path: Optional[Path] = None, skills: Optional[List[str]] = None) -> List[LintResult]:
    """Kasadaki tüm yetenekleri (ya da verilenleri) denetler."""
    from entropy.brain.playbook import PlaybookStore

    store = PlaybookStore(vault_path=vault_path)
    if skills is None:
        root = store.vault_path / "Entropy" / "Skills"
        skills = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    # Kasa taramasi yetenekler arasinda paylasilir (bkz. _all_stems).
    cache: Dict[str, Set[str]] = {}
    return [lint_skill(s, vault_path=vault_path, store=store, stem_cache=cache) for s in skills]


# ------------------------------------------------------------------ çıktılar


def render_lint_html(results: List[LintResult]) -> str:
    """Sohbete basılacak HTML tablo."""
    if not results:
        return "<b>🩺 Wiki Denetimi</b><br/>Denetlenecek yetenek bulunamadı."
    rows: List[str] = []
    total = 0
    for res in results:
        counts = res.counts()
        total += res.total
        cells = "".join(
            f"<td style='padding:2px 10px 2px 0;color:{'#e06c75' if counts.get(c) else '#8B949E'};'>"
            f"{counts.get(c, 0)}</td>"
            for c in CHECK_ORDER
        )
        rows.append(
            f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>{_html.escape(res.skill)}</td>"
            f"<td style='padding:2px 10px 2px 0;'>{res.stats.get('pages', 0)} sayfa</td>{cells}</tr>"
        )
    head = "".join(
        f"<th style='text-align:left;padding:2px 10px 2px 0;color:#8B949E;font-weight:normal;'>"
        f"{_html.escape(CHECK_LABELS[c])}</th>" for c in CHECK_ORDER
    )
    detail_lines: List[str] = []
    for res in results:
        for f in res.findings[:12]:
            detail_lines.append(
                f"• <b>{_html.escape(f.label)}</b> — {_html.escape(f.page)}: {_html.escape(f.message)}"
            )
    detail = ("<div style='color:#8B949E;margin-top:6px;'>"
              + "<br/>".join(detail_lines[:20]) + "</div>") if detail_lines else ""
    return (
        f"<b>🩺 Wiki Denetimi</b> — {total} bulgu"
        f"<table style='margin-top:4px;'>"
        f"<tr><th style='text-align:left;padding:2px 10px 2px 0;color:#8B949E;font-weight:normal;'>Yetenek</th>"
        f"<th style='text-align:left;padding:2px 10px 2px 0;color:#8B949E;font-weight:normal;'>Boyut</th>{head}</tr>"
        f"{''.join(rows)}</table>"
    ) + detail


def render_lint_markdown(res: LintResult) -> str:
    """`lint.md` gövdesi: türetilmiş dosyadır, her denetimde yeniden yazılır."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        "---",
        "type: lint",
        f"skill: {res.skill}",
        f"findings: {res.total}",
        f"generated: {now}",
        "---",
        "",
        f"# 🩺 {res.skill} — Wiki Denetimi",
        "",
        f"{res.stats.get('pages', 0)} sayfa "
        f"({res.stats.get('concepts', 0)} kavram, {res.stats.get('entities', 0)} varlık), "
        f"playbook v{res.stats.get('playbook_version', 0)}. Toplam {res.total} bulgu.",
        "",
    ]
    grouped = res.by_check()
    if not res.findings:
        lines += ["Bulgu yok.", ""]
    for check in CHECK_ORDER:
        items = grouped.get(check) or []
        if not items:
            continue
        lines += [f"## {CHECK_LABELS[check]} ({len(items)})", ""]
        lines += [f"- **{f.page}** — {f.message}" for f in items]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_lint_report(res: LintResult, vault_path: Optional[Path] = None) -> Path:
    """`Skills/<yetenek>/wiki/lint.md` yazar ve yolunu döndürür."""
    root = wiki_dir(res.skill, vault_path)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "lint.md"
    path.write_text(render_lint_markdown(res), encoding="utf-8")
    return path
