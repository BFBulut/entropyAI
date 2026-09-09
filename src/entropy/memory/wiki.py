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

_INDEX_HEADER = "# {title} — Wiki\n\n"
_LOG_HEADER = "# {title} — Wiki Günlüğü\n\n"


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

    _store_query_node(path, skill, title, masked, meta, sources)
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
    for page in _query_pages(skill, vault_path):
        try:
            text = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        category = _frontmatter_value(text, "category") or DEFAULT_CATEGORY
        title = _frontmatter_value(text, "title") or page.stem
        created = _frontmatter_value(text, "created")[:10]
        entry = f"- [[{page.stem}]] — {title}" + (f" ({created})" if created else "")
        grouped.setdefault(category, []).append(entry)

    for category in sorted(grouped):
        lines += [f"## {category}", ""] + grouped[category] + [""]

    if not grouped and not (skill and playbook.is_file()):
        lines += ["_Henüz sayfa yok._", ""]

    index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return index
