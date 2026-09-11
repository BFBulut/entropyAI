"""
Rapor başlığı türetme (Faz 13-A, araştırma notu §1.5).

Kök neden: köprüler rapor başlığını **kullanıcının istem satırının ilk 40
karakterinden** üretiyordu; kasada "Tamamdır, şimdi senden yeni bir yetenek
(+2)" gibi başlıklar oluştu. Bu modül tek gerçek kaynağın çekirdek tarafıdır:

    gövdedeki ilk `# H1`  →  ilk anlamlı cümle  →  `fallback`

**Kullanıcının istem satırı hiçbir zaman başlık kaynağı değildir.**

Saf Python (Qt/kasa/ajan bağımlılığı yok) ki köprüler, testler ve ileride
arayüz katmanı aynı sözleşmeyi paylaşabilsin. Okuma tarafındaki
`ui/widgets/report_center.derive_report_title` aynı sırayı izler; ikisi
sonradan tek kaynağa birleştirilecek.
"""

from __future__ import annotations

import re

#: Başlık üst sınırı (karakter). `vault_manager.REPORT_TITLE_MAX` ile aynı.
TITLE_MAX_CHARS = 80

#: Dosya adında yasak karakterler (Windows).
_UNSAFE_FILENAME_RE = re.compile(r'[\\/*?:"<>|]')

#: Satır bloğu olarak yazılan makine etiketleri (`board_tools.LINE_BLOCK_TAGS`).
_LINE_BLOCK_TAGS = ("[KONTROL NOKTASI]", "[KANIT]")
#: Tek satırlık makine etiketleri.
_LINE_TAGS = ("[KURAL]",)

_BRACKET_LINE_RE = re.compile(r"^\[[^\]]+\]\s*$")
_PANO_OPEN_RE = re.compile(r"\[PANO\b[^\]]*\]", re.IGNORECASE)
_PANO_CLOSE = "[/PANO]"
_HAFIZA_OPEN_RE = re.compile(r"\[HAFIZA\b[^\]]*\]", re.IGNORECASE)
_HAFIZA_CLOSE = "[/HAFIZA]"

#: "Tamamdır, şimdi …" gibi sohbet açılışları başlık olamaz.
_CHAT_OPENERS = (
    "tamam", "tamamdır", "tamamdir", "peki", "evet", "hayır", "hayir",
    "şimdi", "simdi", "merhaba", "selam", "teşekkür", "tesekkur", "harika",
    "süper", "super", "elbette", "anladım", "anladim", "olur", "hadi",
    "tabii", "güzel", "guzel", "ok", "okay",
)


# --------------------------------------------------------------- yardımcılar

def strip_frontmatter(text: str) -> str:
    """Baştaki YAML ön bilgisini (`---` … `---`) atar."""
    raw = str(text or "")
    if not raw.lstrip("﻿").startswith("---"):
        return raw
    body = raw.lstrip("﻿")
    end = body.find("\n---", 3)
    if end == -1:
        return raw
    rest = body[end + 4:]
    return rest.lstrip("\r\n")


def strip_machine_blocks(text: str) -> str:
    """`[PANO …] … [/PANO]`, `[HAFIZA] … [/HAFIZA]`, `[KANIT]`, `[KONTROL NOKTASI]`, `[KURAL]` siler."""
    out = str(text or "")
    # Faz 14-D: alt ajanın hafıza bloğu da makine bloğudur, kullanıcıya gösterilmez.
    for open_re, close_tag in ((_PANO_OPEN_RE, _PANO_CLOSE), (_HAFIZA_OPEN_RE, _HAFIZA_CLOSE)):
        while True:
            m = open_re.search(out)
            if m is None:
                break
            end = out.upper().find(close_tag, m.end())
            stop = len(out) if end == -1 else end + len(close_tag)
            out = out[: m.start()] + out[stop:]

    kept = []
    skipping = False
    for line in out.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if skipping:
            if not stripped:
                skipping = False
                continue
            if _BRACKET_LINE_RE.match(stripped) and upper not in _LINE_BLOCK_TAGS:
                skipping = False
            else:
                continue
        if upper in _LINE_BLOCK_TAGS:
            skipping = True
            continue
        if any(upper.startswith(tag) for tag in _LINE_TAGS):
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_code_fences(text: str) -> str:
    """Üç tırnaklı kod bloklarını atar (içindeki `#` yorumu başlık olmasın)."""
    kept = []
    inside = False
    for line in str(text or "").splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            kept.append(line)
    return "\n".join(kept)


def _clean_inline(text: str) -> str:
    # Alt çizgi YALNIZCA vurgu olarak sarmaladığında atılır: `Gorev_kart_2026`
    # gibi tanımlayıcılar başlıkta bozulmamalı.
    text = re.sub(r"(?<!\w)_(\S[^_]*?)_(?!\w)", r"\1", str(text or ""))
    text = re.sub(r"[*`]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # [ad](hedef) → ad
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate(text: str, max_len: int) -> str:
    """Sonu kelime sınırında düzgün kırpar."""
    text = text.strip(" .!?…-–—:;,")
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-–—")


def _looks_like_chat_opener(text: str) -> bool:
    first = re.split(r"[\s,.:;!?]+", text.lower().strip(), maxsplit=1)[0]
    return first in _CHAT_OPENERS


def title_from_h1(body: str) -> str:
    """Gövdedeki ilk `# H1` (ön bilgi, makine blokları ve kod atlanır)."""
    text = _strip_code_fences(strip_machine_blocks(strip_frontmatter(body)))
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        if level != 1:
            continue
        candidate = _clean_inline(stripped.lstrip("#"))
        if candidate:
            return candidate
    return ""


def first_meaningful_sentence(body: str) -> str:
    """İlk anlamlı cümle: en az 3 kelime, başlık/liste/blok satırları atlanır."""
    text = _strip_code_fences(strip_machine_blocks(strip_frontmatter(body)))
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ">", "|", "---", "===")):
            continue
        if _BRACKET_LINE_RE.match(stripped):
            continue
        cleaned = _clean_inline(re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", stripped))
        if not cleaned:
            continue
        sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0].strip()
        if len(sentence.split()) < 3:
            continue
        return sentence
    return ""


# --------------------------------------------------------------- genel API

def derive_report_title(body: str, fallback: str = "", *, max_len: int = TITLE_MAX_CHARS) -> str:
    """
    Rapor başlığını GÖVDEDEN türetir.

    Sıra: ilk `# H1` → ilk anlamlı cümle → `fallback` → "Araştırma Raporu".
    Kullanıcının istem satırı hiçbir zaman kaynak değildir (§1.5).
    """
    for candidate in (title_from_h1(body), first_meaningful_sentence(body)):
        candidate = _truncate(candidate, max_len)
        if candidate and not _looks_like_chat_opener(candidate):
            return candidate
    tail = _truncate(_clean_inline(fallback), max_len)
    return tail or "Araştırma Raporu"


def safe_filename_title(title: str, *, max_len: int = TITLE_MAX_CHARS) -> str:
    """Başlığı dosya adı olarak güvenli hâle getirir (Windows yasak karakterleri)."""
    text = _UNSAFE_FILENAME_RE.sub("", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = _truncate(text, max_len)
    return text or "Arastirma_Raporu"


# ---------------------------------------------------- oturum notu (Faz 13-A)

def session_note_path(entropy_dir, title: str, now=None):
    """`Entropy/Sessions/<YYYY-MM-DD>/<HHMM>-<konu>.md` yolunu üretir."""
    from datetime import datetime
    from pathlib import Path

    now = now or datetime.now()
    slug = safe_filename_title(title, max_len=48)
    slug = re.sub(r"\s+", "-", slug).strip("-") or "oturum"
    day = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%H%M")
    directory = Path(entropy_dir) / "Sessions" / day
    path = directory / f"{stamp}-{slug}.md"
    n = 2
    while path.exists():
        path = directory / f"{stamp}-{slug}-{n}.md"
        n += 1
    return path


def _yaml_value(value: str) -> str:
    text = str(value or "").replace('"', "'").replace("\n", " ")
    return f'"{text}"'


def save_session_note(
    entropy_dir,
    body: str,
    *,
    provider: str = "",
    model: str = "",
    skill: str = "",
    title: str = "",
    now=None,
):
    """
    Serbest sohbet turunu `Entropy/Sessions/` altına yazar (rapor DEĞİL).

    Faz 13-A: sohbet turları artık rapora dönüşmüyor (§1.5), ama kullanıcı
    verisi kaybolmasın diye `type: session` künyesiyle diske düşer. Rapor
    Merkezi bu klasörü ayrı süzgeçle gösterir.
    """
    from datetime import datetime
    from pathlib import Path

    now = now or datetime.now()
    text = str(body or "")
    clean_title = title or derive_report_title(text, fallback="Sohbet Turu")
    path = session_note_path(Path(entropy_dir), clean_title, now=now)
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "\n".join(
        [
            "---",
            "type: session",
            f"title: {_yaml_value(clean_title)}",
            f"created: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"provider: {_yaml_value(provider)}",
            f"model: {_yaml_value(model)}",
            f"skill: {_yaml_value(skill)}",
            "---",
            "",
        ]
    )
    path.write_text(front + text.strip() + "\n", encoding="utf-8")
    return path
