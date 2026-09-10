"""
Oturum aktarımı (handoff): bir sohbetin kalıcı, yapılandırılmış devir sayfası.

Sorun
-----
Bir oturum bittiğinde (bağlam doldu, uygulama kapandı, sohbet sıfırlandı) o
oturumun neyi neden yaptığı buharlaşıyor. Sonraki oturum ya sıfırdan başlıyor ya
da ham geçmişi geri yükleyip bağlamı yeniden dolduruyor. İkisi de pahalı.

Çözüm
-----
Oturumun sonunda dokuz bölümlük bir devir sayfası yazılır. Sayfa, bir sonraki
oturuma 300 token bütçesiyle "Önceki oturum" olarak enjekte edilir.

Neden LLM çağrısı yok
---------------------
Aktarım sayfası, kullanıcı "artık bitti" dediği anda yazılır — yani tam olarak
kotanın en değerli olduğu anda. Özet için bir tur daha model harcamak, kaçınmaya
çalıştığımız maliyetin ta kendisi olurdu. Bunun yerine çıkarımsal (extractive)
çalışılır: başlıklar, komutlar, dosya yolları, rapor adları, karar/hata kalıpları
ve son turların kısaltılmış metni geçmişten doğrudan toplanır. Sonuç "akıllı" bir
özet değil, DOĞRU bir kayıttır; bir sonraki oturumun ihtiyacı da budur.

Aktarım sayfaları damıtma kaynağı DEĞİLDİR (bkz. playbook._NON_REPORT_DIRS):
yordam değil olay taşırlar. Bağlam kurucu ve geri çağırma onları ayrıca görür.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from entropy.core.config import STATE_DIR, config

logger = logging.getLogger(__name__)

# Sayfanın bölümleri ve sırası. Sıra rastgele değil: bir sonraki oturum önce
# "ne yapıyorduk" (hedef), sonra "neyi bir daha tartışmayalım" (kararlar), sonra
# "ne kaldı" (açık işler) sorularını sorar. Kaynaklar en sonda çünkü en hacimli
# ve en az acil bölümdür.
SECTION_ORDER: Tuple[str, ...] = (
    "hedef",
    "kararlar",
    "acik_isler",
    "dosyalar",
    "hatalar",
    "sonraki_adim",
    "yetenekler",
    "olcumler",
    "kaynaklar",
)

SECTION_TITLES: Dict[str, str] = {
    "hedef": "Hedef",
    "kararlar": "Alınan Kararlar",
    "acik_isler": "Açık İşler",
    "dosyalar": "Dokunulan Dosyalar / Yollar",
    "hatalar": "Hatalar ve Çözümleri",
    "sonraki_adim": "Sonraki Adım",
    "yetenekler": "Kullanılan Yetenekler / Ajanlar",
    "olcumler": "Ölçümler ve Tokenlar",
    "kaynaklar": "Kaynaklar",
}

# Bölüm başına azami madde. Sayfa bir sonraki oturuma 300 token'la giriyor;
# 40 maddelik bir "dokunulan dosyalar" listesi o bütçeyi tek başına yer.
MAX_ITEMS_PER_SECTION = 8

# Son turların kısaltılmış metni. Dört tur, "az önce ne konuşuluyordu"yu taşımaya
# yeter; daha fazlası sayfayı ham geçmişin kopyasına çevirir.
RECENT_TURNS = 4
RECENT_TURN_CHARS = 400

_DECISION_PATTERNS = re.compile(
    r"(karar|karara|seçildi|secildi|tercih ed|kullanılacak|kullanilacak|kullanacağız|"
    r"kullanacagiz|yerine|vazgeç|vazgec|kabul ed|onaylandı|onaylandi|benimse|"
    r"decided|decision|chose|we will use|instead of)",
    re.IGNORECASE,
)
_OPEN_WORK_PATTERNS = re.compile(
    r"(yarım kal|yarim kal|eksik|yapılmadı|yapilmadi|yazılmadı|yazilmadi|kalan|"
    r"bekliyor|beklemede|todo|açık iş|acik is|henüz|henuz|yapılacak|yapilacak|"
    r"ertelen|doğrulanamadı|dogrulanamadi|test edilmedi|"
    r"pending|remaining|not done|unresolved)",
    re.IGNORECASE,
)
_ERROR_PATTERNS = re.compile(
    r"(hata|hatası|hatasi|başarısız|basarisiz|çöktü|coktu|traceback|exception|"
    r"error|failed|crash|çözüldü|cozuldu|düzeltildi|duzeltildi|fixed|resolved)",
    re.IGNORECASE,
)
_NEXT_PATTERNS = re.compile(
    r"(sonraki adım|sonraki adim|sıradaki|siradaki|bir sonraki|devam ed|next step|"
    r"next:|ardından yap|ardindan yap|planlanan)",
    re.IGNORECASE,
)

# Windows ve POSIX yolları + proje-göreli dosya adları.
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s`\"'<>|,;()\[\]]+"
    r"|(?:\./)?(?:[\w.\-]+[\\/])+[\w.\-]+\.\w{1,5}"
    r"|\b[\w.\-]+\.(?:py|md|json|toml|yaml|yml|ts|tsx|js|spec|txt|ini|cfg))"
)
_URL_RE = re.compile(r"https?://[^\s`\"'<>|)\]]+")
_COMMAND_RE = re.compile(r"(?m)(?:^|\s)(/[a-zA-Z][\w\-:]*)")
_MEASURE_RE = re.compile(
    r"[~≈]?\d[\d.,]*\s*(?:token|tokens?|karakter|char|ms|sn|saniye|s\b|dakika|dk|"
    r"%|kb|mb|gb|rapor|dosya|satır|satir|tur|kez)",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,4}\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"(?m)^\s{0,6}(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")


def _mask(text: str) -> str:
    """Araç çıktısı maskesi; ortak yardımcı yoksa yerel eşdeğeri kullanılır."""
    try:
        from entropy.core.masking import mask_tool_output

        return mask_tool_output(text)
    except Exception:
        # Yerel eşdeğer: uzun kod/çıktı çitlerini yer tutucuya indir. Ortak maske
        # (agy tarafında yazılıyor) henüz yoksa aktarım yazımı düşmemeli.
        def _repl(m: "re.Match") -> str:
            body = m.group(1)
            if len(body) <= 2000:
                return m.group(0)
            return f"```\n[araç çıktısı: {len(body)} karakter]\n```"

        return re.sub(r"```[a-zA-Z]*\n(.*?)```", _repl, text or "", flags=re.DOTALL)


def _slugify(text: str, max_len: int = 48) -> str:
    """Dosya adına uygun, ASCII, tireli konu etiketi."""
    raw = (text or "").strip().lower()
    raw = raw.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    raw = raw.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return (raw[:max_len].rstrip("-")) or "oturum"


def _clean_line(line: str, max_len: int = 180) -> str:
    """Tek satırı madde olarak kullanılabilir hâle getirir."""
    s = re.sub(r"\s+", " ", (line or "").strip())
    s = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", s)
    # Yalnızca `*` ve backtick düşer. Alt çizgi KALIR: markdown italiği sanıp
    # silmek `skills_widget.py` ve `source_reports` gibi tanımlayıcıları
    # bozuyordu — aktarım sayfasının en değerli içeriği tam olarak bunlar.
    s = re.sub(r"[*`]{1,3}", "", s)
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


def _dedup(items: Sequence[str], limit: int = MAX_ITEMS_PER_SECTION) -> List[str]:
    """Sırayı koruyarak yinelenenleri atar ve tavana kırpar (karşılaştırma harf duyarsız)."""
    seen = set()
    out: List[str] = []
    for it in items:
        key = it.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it.strip())
        if len(out) >= limit:
            break
    return out


def _normalize_history(history: Any) -> List[Dict[str, str]]:
    """Geçmişi {role, content} listesine indirger; biçim bozuksa boş liste."""
    out: List[Dict[str, str]] = []
    if not isinstance(history, (list, tuple)):
        return out
    for turn in history:
        if isinstance(turn, dict):
            role = str(turn.get("role") or turn.get("sender") or "user").lower()
            content = turn.get("content", turn.get("text", ""))
        elif isinstance(turn, (list, tuple)) and len(turn) >= 2:
            role, content = str(turn[0]).lower(), turn[1]
        else:
            continue
        content = str(content or "")
        if not content.strip():
            continue
        out.append({"role": "assistant" if role.startswith("a") else "user", "content": content})
    return out


def _lines_matching(turns: List[Dict[str, str]], pattern: "re.Pattern", roles=("assistant", "user")) -> List[str]:
    """Kalıba uyan, madde/cümle uzunluğundaki satırlar."""
    hits: List[str] = []
    for turn in turns:
        if turn["role"] not in roles:
            continue
        for raw in turn["content"].splitlines():
            if len(raw.strip()) < 12 or len(raw.strip()) > 400:
                continue
            if pattern.search(raw):
                hits.append(_clean_line(raw))
    return hits


def extract_sections(history: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """
    Geçmişten dokuz bölümü çıkarımsal olarak üretir. Model çağrısı yoktur.

    Boş kalan bölüm sayfada "—" ile görünür: bilgi yokluğu da bilgidir; uydurulmuş
    bir madde, sonraki oturumu yanlış yönlendirir.
    """
    meta = dict(meta or {})
    turns = _normalize_history(history)
    all_text = "\n".join(t["content"] for t in turns)
    user_text = "\n".join(t["content"] for t in turns if t["role"] == "user")

    sections: Dict[str, List[str]] = {k: [] for k in SECTION_ORDER}

    # 1. Hedef: kullanıcının ilk anlamlı isteği; meta.note verilmişse başa geçer.
    goal: List[str] = []
    note = str(meta.get("note") or "").strip()
    if note:
        goal.append(_clean_line(note, 220))
    for turn in turns:
        if turn["role"] != "user":
            continue
        for raw in turn["content"].splitlines():
            cleaned = _clean_line(raw, 220)
            if len(cleaned) >= 15 and not cleaned.startswith("/"):
                goal.append(cleaned)
                break
        if len(goal) >= 2:
            break
    sections["hedef"] = _dedup(goal, 2)

    sections["kararlar"] = _dedup(_lines_matching(turns, _DECISION_PATTERNS))
    sections["acik_isler"] = _dedup(_lines_matching(turns, _OPEN_WORK_PATTERNS))

    # 4. Dosyalar: metindeki her yol. Sıklığa göre değil, ilk görülme sırasına
    # göre; bir oturumda önce dokunulan dosya çoğunlukla asıl konudur.
    sections["dosyalar"] = _dedup(_PATH_RE.findall(all_text), MAX_ITEMS_PER_SECTION)

    sections["hatalar"] = _dedup(_lines_matching(turns, _ERROR_PATTERNS))

    # 6. Sonraki adım: açık ifade varsa o; yoksa son yanıtın son maddesi.
    nexts = _lines_matching(turns, _NEXT_PATTERNS)
    if not nexts and turns:
        for turn in reversed(turns):
            if turn["role"] != "assistant":
                continue
            bullets = _BULLET_RE.findall(turn["content"])
            if bullets:
                nexts = [_clean_line(bullets[-1])]
            break
    sections["sonraki_adim"] = _dedup(nexts, 4)

    # 7. Yetenek/ajanlar: meta bildirimi + geçmişteki eğik çizgi komutları.
    used: List[str] = []
    for key in ("skills", "agents"):
        value = meta.get(key)
        if isinstance(value, str):
            used.append(value)
        elif isinstance(value, (list, tuple, set)):
            used.extend(str(v) for v in value)
    used.extend(_COMMAND_RE.findall(user_text))
    sections["yetenekler"] = _dedup(used, MAX_ITEMS_PER_SECTION)

    # 8. Ölçümler: meta sayaçları önce (kesin), sonra metinden yakalananlar (kanıt).
    measures: List[str] = []
    for key in ("input_tokens", "output_tokens", "total_tokens", "tokens", "duration_s", "turns"):
        if meta.get(key) is not None:
            measures.append(f"{key}: {meta[key]}")
    if not any(k in meta for k in ("turns",)):
        measures.append(f"turns: {len(turns)}")
    measures.extend(m.strip() for m in _MEASURE_RE.findall(all_text)[:40])
    sections["olcumler"] = _dedup(measures, MAX_ITEMS_PER_SECTION)

    # 9. Kaynaklar: rapor adları (.md) ve bağlantılar.
    resources = [p for p in _PATH_RE.findall(all_text) if p.lower().endswith(".md")]
    resources.extend(_URL_RE.findall(all_text))
    for key in ("reports", "sources"):
        value = meta.get(key)
        if isinstance(value, (list, tuple, set)):
            resources.extend(str(v) for v in value)
    sections["kaynaklar"] = _dedup(resources, MAX_ITEMS_PER_SECTION)

    return sections


def recent_turns_digest(history: Any, turns: int = RECENT_TURNS, chars: int = RECENT_TURN_CHARS) -> str:
    """Son turların maskelenmiş ve kırpılmış metni."""
    items = _normalize_history(history)[-max(0, turns):]
    out: List[str] = []
    for turn in items:
        body = _mask(turn["content"]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if len(body) > chars:
            body = body[:chars].rstrip() + "…"
        label = "Kullanıcı" if turn["role"] == "user" else "Ajan"
        out.append(f"**{label}:** {body}")
    return "\n\n".join(out)


def sessions_dir(vault_path: Optional[Path] = None) -> Path:
    root = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
    return root / "Entropy" / "Sessions"


def render_handoff(
    sections: Dict[str, List[str]],
    digest: str = "",
    meta: Optional[Dict[str, Any]] = None,
    title: str = "",
) -> str:
    """Bölümleri markdown sayfasına çevirir (frontmatter + dokuz başlık + son turlar)."""
    meta = dict(meta or {})
    now = datetime.datetime.now()
    parts = [
        "---",
        f'title: "{title or "Oturum Aktarımı"}"',
        "kind: handoff",
        f"date: {now.date().isoformat()}",
        f"created_at: {now.isoformat(timespec='seconds')}",
    ]
    if meta.get("project"):
        parts.append(f'project: "{meta["project"]}"')
    parts.append("tags: [entropy-ai, handoff, session]")
    parts.append("---")
    parts.append("")
    parts.append(f"# 🔁 {title or 'Oturum Aktarımı'}")
    parts.append("")

    for key in SECTION_ORDER:
        parts.append(f"## {SECTION_TITLES[key]}")
        items = sections.get(key) or []
        if items:
            parts.extend(f"- {it}" for it in items)
        else:
            parts.append("—")
        parts.append("")

    if digest.strip():
        parts.append("## Son Turlar (kısaltılmış)")
        parts.append("")
        parts.append(digest.strip())
        parts.append("")

    return "\n".join(parts)


def write_handoff(
    history: Any,
    meta: Optional[Dict[str, Any]] = None,
    vault_path: Optional[Path] = None,
    memory: Any = None,
) -> Path:
    """
    Aktarım sayfasını yazar ve yolunu döndürür.

    Yan etkileri: `Sessions/log.md`'ye tek satır ekler ve bilişsel belleğe bir
    "session" düğümü kaydeder (geri çağırma sayfayı bulabilsin diye). Bellek
    yazımı başarısız olursa sayfa yine de yazılmış olur: kalıcı olan dosyadır,
    bellek ondan yeniden üretilebilir.
    """
    meta = dict(meta or {})
    sections = extract_sections(history, meta)
    digest = recent_turns_digest(history)

    topic = str(meta.get("topic") or "").strip()
    if not topic:
        topic = (sections.get("hedef") or ["oturum"])[0]
    slug = _slugify(topic)
    title = str(meta.get("title") or "").strip() or f"Oturum Aktarımı — {topic[:60]}"

    target_dir = sessions_dir(vault_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    path = target_dir / f"{today}-{slug}.md"
    # Aynı gün aynı konuda ikinci aktarım öncekini ezmemeli.
    n = 2
    while path.exists():
        path = target_dir / f"{today}-{slug}-{n}.md"
        n += 1

    path.write_text(render_handoff(sections, digest, meta, title), encoding="utf-8")

    # Günlük: tek satır, en yeni en altta. Sayfaların dizini olmadan Sessions/
    # klasörü birkaç hafta içinde okunamaz hâle gelir.
    log = target_dir / "log.md"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{stamp}] [[{path.stem}]] — {_clean_line(topic, 120)}\n"
    header = "" if log.exists() else "# Oturum Aktarımları\n\n"
    with open(log, "a", encoding="utf-8") as f:
        f.write(header + line)

    _store_session_node(path, sections, title, meta, memory)
    return path


def _store_session_node(
    path: Path,
    sections: Dict[str, List[str]],
    title: str,
    meta: Dict[str, Any],
    memory: Any = None,
) -> bool:
    """Aktarımı bilişsel belleğe "session" düğümü olarak yazar; başarılıysa True."""
    try:
        if memory is None:
            from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

            memory = CognitiveMemorySystem()
        summary_bits = []
        for key in ("hedef", "kararlar", "acik_isler", "sonraki_adim"):
            items = sections.get(key) or []
            if items:
                summary_bits.append(f"{SECTION_TITLES[key]}: " + "; ".join(items[:3]))
        content = _mask(f"{title}\n" + "\n".join(summary_bits))
        memory.store_node(
            category="session",
            content=content,
            importance=0.7,
            metadata={
                "kind": "handoff",
                "path": str(path),
                "project": meta.get("project"),
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            },
        )
        return True
    except Exception as exc:
        logger.warning("Aktarım için bellek düğümü yazılamadı (%s): %s", path, exc)
        return False


def _is_office_report(path: Path) -> bool:
    """
    Dosya bir ofis raporu mu (ön bilgide `type: office_report`)?

    Ofis kartı bitişinde Sessions/ değil ofis raporu yazılır; yine de eski ya da
    elle taşınmış bir dosya Sessions/ altına düşerse aktarım olarak okunmamalı:
    ofis raporu bir sonraki oturumun "nerede kalmıştık"ı değildir.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:400]
    except OSError:
        return False
    return bool(re.search(r"(?m)^type:\s*office_report\s*$", head))


def load_latest_handoff(vault_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    En son aktarım sayfası: {path, title, body, sections}; yoksa None.

    "En son" dosya adındaki tarihten belirlenir, mtime'dan değil: kasa OneDrive'da
    ve senkron tüm dosyalara aynı anda dokunabiliyor.
    """
    target_dir = sessions_dir(vault_path)
    if not target_dir.is_dir():
        return None
    candidates = [
        p for p in target_dir.glob("*.md")
        if p.name.lower() != "log.md" and not _is_office_report(p)
    ]
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda p: (p.stem, p.name))[-1]
    try:
        raw = latest.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    title = latest.stem
    m = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', raw)
    if m:
        title = m.group(1).strip()
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", raw, count=1, flags=re.DOTALL).strip()

    sections: Dict[str, List[str]] = {}
    title_to_key = {v: k for k, v in SECTION_TITLES.items()}
    for heading, block in re.findall(r"(?m)^##\s+(.+?)\s*\n(.*?)(?=^##\s|\Z)", body, re.DOTALL):
        key = title_to_key.get(heading.strip())
        if not key:
            continue
        items = [_clean_line(b) for b in _BULLET_RE.findall(block)]
        sections[key] = [i for i in items if i and i != "—"]

    return {"path": str(latest), "title": title, "body": body, "sections": sections}


# ---------------------------------------------------------------------------
# "Bir kez enjekte et" işareti
# ---------------------------------------------------------------------------
# Aktarım BİR SONRAKİ oturuma girmelidir, her tura değil: 300 token her turda
# yeniden ödenirse aktarımın kazandırdığı bağlam, maliyetiyle eşitlenir. Enjekte
# edilen sayfanın yolu burada işaretlenir; aynı sayfa ikinci kez girmez.
_CONSUMED_FILE = STATE_DIR / "handoff_consumed.json"


def consumed_handoff_path() -> Optional[str]:
    try:
        if _CONSUMED_FILE.is_file():
            return json.loads(_CONSUMED_FILE.read_text(encoding="utf-8")).get("path")
    except (OSError, ValueError):
        return None
    return None


def mark_handoff_consumed(path: str) -> None:
    try:
        _CONSUMED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CONSUMED_FILE.write_text(
            json.dumps({"path": str(path), "at": datetime.datetime.now().isoformat(timespec="seconds")}),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Aktarım işareti yazılamadı: %s", exc)


def pending_handoff(vault_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Henüz hiçbir oturuma enjekte edilmemiş en son aktarım; yoksa None."""
    latest = load_latest_handoff(vault_path)
    if not latest:
        return None
    if consumed_handoff_path() == latest["path"]:
        return None
    return latest
