"""
Kontrol noktası disiplini (Faz 10-A / 2).

Bir modül/kart bitince ajan kısa bir durum özetini DİSKE yazar. Çökme sonrası
kaldığı yerden devam ederken sohbet geçmişi değil bu özet okunur: geçmiş hem
pahalıdır (her turda yeniden gönderilir) hem de çökmede kaybolur.

Dosya:  <kasa>/Desk/Offices/<ofis>/workspace/checkpoints/<kart-id>.md

Blok sözleşmesi (alt ajan çıktısında, harness ayrıştırır):

    [KONTROL NOKTASI]
    yapılan: kart deposu ayrıldı
    sonraki: pano üretimini bağla
    dosyalar: src/entropy/memory/office_workspace.py
    testler: 4 geçti

    [KANIT]
    komut: python -m pytest tests/test_x.py -q
    sonuç: yeşil
    özet: 4 passed

`[KANIT]` bloğu "kanıtla kapatma" içindir: bir kart ancak yeşil kanıtla
`done` olabilir. Bu modül karar vermez, yalnızca ayrıştırır.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "CHECKPOINT_BLOCK_TAG",
    "PROOF_BLOCK_TAG",
    "RESUME_MAX_CHARS",
    "checkpoints_dir",
    "checkpoint_path",
    "write_checkpoint",
    "read_checkpoint",
    "resume_section",
    "parse_checkpoint_block",
    "parse_proof_block",
    "checkpoint_instruction",
]

CHECKPOINT_BLOCK_TAG = "[KONTROL NOKTASI]"
PROOF_BLOCK_TAG = "[KANIT]"

# Devam özetinin karakter tavanı: isteme giren bir bloktur, uzarsa bağlam yer.
RESUME_MAX_CHARS = 800

# Alan adı eş anlamlıları — alt ajanlar Türkçe/İngilizce karışık yazıyor.
_FIELD_ALIASES: Dict[str, str] = {
    "yapılan": "done",
    "yapilan": "done",
    "yapıldı": "done",
    "done": "done",
    "özet": "summary",
    "ozet": "summary",
    "summary": "summary",
    "sonraki": "next_steps",
    "sonraki adım": "next_steps",
    "sonraki adımlar": "next_steps",
    "next": "next_steps",
    "dosyalar": "files_touched",
    "dosya": "files_touched",
    "files": "files_touched",
    "testler": "tests",
    "test": "tests",
    "tests": "tests",
}

_PROOF_FIELD_ALIASES: Dict[str, str] = {
    "komut": "command",
    "command": "command",
    "sonuç": "result",
    "sonuc": "result",
    "result": "result",
    "özet": "summary",
    "ozet": "summary",
    "summary": "summary",
    "çıktı": "summary",
    "cikti": "summary",
}

_GREEN_WORDS = ("yeşil", "yesil", "green", "geçti", "gecti", "passed", "pass", "başarılı")
_RED_WORDS = ("kırmızı", "kirmizi", "red", "kaldı", "failed", "fail", "hata", "error")

_LIST_SPLIT_RE = re.compile(r"[,;]|\s{2,}")


def _safe(name: str) -> str:
    cleaned = "".join(
        c if c.isalnum() or c in " -_" else "_" for c in (name or "")
    ).strip()
    return cleaned or "office"


def checkpoints_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    from entropy.memory.office_workspace import workspace_dir

    return workspace_dir(office, vault_path) / "checkpoints"


def checkpoint_path(
    office: str, card_id: str, vault_path: Optional[Path] = None
) -> Path:
    return checkpoints_dir(office, vault_path) / f"{_safe(card_id)}.md"


def _as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in _LIST_SPLIT_RE.split(value)]
        return [p for p in parts if p]
    out: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def write_checkpoint(
    office: str,
    card_id: str,
    *,
    summary: str = "",
    done: str = "",
    next_steps: str = "",
    files_touched=None,
    tests: Optional[str] = None,
    author: str = "",
    vault_path: Optional[Path] = None,
) -> Path:
    """
    Kontrol noktasını yazar (üzerine yazar: son durum tek kayıttır).

    Dosya içinde bir "Geçmiş" bölümü tutulur; önceki özet oraya bir satır olarak
    düşer. Böylece devam eden ajan tek dosyada hem son durumu hem kısa tarihçeyi
    görür, ayrı arşiv klasörü gerekmez.
    """
    path = checkpoint_path(office, card_id, vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = read_checkpoint(office, card_id, vault_path)
    history: List[str] = list((previous or {}).get("history") or [])
    if previous and (previous.get("summary") or previous.get("done")):
        stamp = previous.get("updated_at") or ""
        line = previous.get("summary") or previous.get("done") or ""
        history.append(f"- {stamp} — {line}".strip())
    history = history[-10:]

    files = _as_list(files_touched)
    now = datetime.now().isoformat(timespec="seconds")
    lines: List[str] = [
        f"# Kontrol noktası: {card_id}",
        "",
        f"- Kart: {card_id}",
        f"- Yazan: {author or '-'}",
        f"- Güncelleme: {now}",
        "",
        "## Özet",
        "",
        (summary or done or "-").strip(),
        "",
        "## Yapılan",
        "",
        (done or "-").strip(),
        "",
        "## Sonraki adımlar",
        "",
        (next_steps or "-").strip(),
        "",
        "## Dokunulan dosyalar",
        "",
    ]
    lines += [f"- {f}" for f in files] or ["- (yok)"]
    lines += ["", "## Testler", "", (tests or "-").strip(), "", "## Geçmiş", ""]
    lines += history or ["- (yok)"]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


_SECTION_RE = re.compile(r"^##\s+(.*?)\s*$")


def read_checkpoint(
    office: str, card_id: str, vault_path: Optional[Path] = None
) -> Optional[Dict[str, object]]:
    """Kontrol noktasını sözlük olarak okur; yoksa None."""
    path = checkpoint_path(office, card_id, vault_path)
    try:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = m.group(1).strip().lower()
            sections[current] = []
            continue
        if current is None:
            m2 = re.match(r"^-\s*([^:]+):\s*(.*)$", line)
            if m2:
                meta[m2.group(1).strip().lower()] = m2.group(2).strip()
            continue
        sections[current].append(line)

    def _text(name: str) -> str:
        return "\n".join(sections.get(name, [])).strip()

    def _items(name: str) -> List[str]:
        out = []
        for ln in sections.get(name, []):
            ln = ln.strip()
            if ln.startswith("- ") and ln != "- (yok)":
                out.append(ln[2:].strip())
        return out

    return {
        "card_id": card_id,
        "office": office,
        "author": meta.get("yazan", ""),
        "updated_at": meta.get("güncelleme", meta.get("guncelleme", "")),
        "summary": _text("özet"),
        "done": _text("yapılan"),
        "next_steps": _text("sonraki adımlar"),
        "files_touched": _items("dokunulan dosyalar"),
        "tests": _text("testler"),
        "history": _items("geçmiş"),
        "path": str(path),
    }


def resume_section(
    office: str,
    card_id: str,
    vault_path: Optional[Path] = None,
    max_chars: int = RESUME_MAX_CHARS,
) -> str:
    """
    Çökme sonrası isteme giren "kaldığın yer" bloğu (≤ `max_chars`).

    Kontrol noktası yoksa boş dize döner — yeni kart hiç kontrol noktası
    görmemelidir, yoksa var olmayan bir işi sürdürmeye çalışır.
    """
    data = read_checkpoint(office, card_id, vault_path)
    if not data:
        return ""
    limit = max(0, int(max_chars))
    parts: List[str] = ["[KALDIĞIN YER]"]
    if data.get("summary"):
        parts.append(f"Durum: {data['summary']}")
    elif data.get("done"):
        parts.append(f"Durum: {data['done']}")
    if data.get("next_steps") and data["next_steps"] != "-":
        parts.append(f"Sonraki: {data['next_steps']}")
    files = data.get("files_touched") or []
    if files:
        parts.append("Dosyalar: " + ", ".join(files[:5]))
    if data.get("tests") and data["tests"] != "-":
        parts.append(f"Testler: {data['tests']}")
    text = "\n".join(p.strip() for p in parts if p and p.strip())
    if len(text) > limit:
        cut = text[:limit]
        nl = cut.rfind("\n")
        text = (cut[:nl] if nl > limit * 0.6 else cut).rstrip()
    return text


# ------------------------------------------------------------------ ayrıştırma


def _block_body(text: str, tag: str) -> Optional[str]:
    """Etiketten sonraki `alan: değer` satırlarını döndürür."""
    if not text:
        return None
    idx = text.upper().find(tag.upper())
    if idx < 0:
        return None
    rest = text[idx + len(tag):]
    out: List[str] = []
    for line in rest.splitlines():
        stripped = line.strip()
        if not stripped:
            if out:
                break
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            break
        out.append(stripped)
    return "\n".join(out) if out else None


def _fields(body: str, aliases: Dict[str, str]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in body.splitlines():
        line = re.sub(r"^[-*]\s+", "", line.strip())
        m = re.match(r"^([^:]{1,24}):\s*(.*)$", line)
        if not m:
            continue
        key = aliases.get(m.group(1).strip().lower())
        if not key:
            continue
        value = m.group(2).strip()
        if value:
            data[key] = value
    return data


def parse_checkpoint_block(text: str) -> Optional[Dict[str, object]]:
    """
    Alt ajan çıktısındaki `[KONTROL NOKTASI]` bloğunu sözlüğe çevirir.

    Dönüş anahtarları `write_checkpoint` parametreleriyle birebir aynıdır:
    `done`, `next_steps`, `files_touched` (liste), `tests`, `summary`.
    Blok yoksa ya da hiçbir alan tanınmadıysa None.
    """
    body = _block_body(text, CHECKPOINT_BLOCK_TAG)
    if body is None:
        return None
    data = _fields(body, _FIELD_ALIASES)
    if not data:
        return None
    out: Dict[str, object] = {
        "done": data.get("done", ""),
        "next_steps": data.get("next_steps", ""),
        "tests": data.get("tests", ""),
        "summary": data.get("summary", "") or data.get("done", ""),
        "files_touched": _as_list(data.get("files_touched", "")),
    }
    return out


def parse_proof_block(text: str) -> Optional[Dict[str, object]]:
    """
    `[KANIT]` bloğunu çözer: `command`, `result` (`green`/`red`/`unknown`),
    `ok` (bool|None), `summary`.

    Sonuç satırı yoksa ya da anlaşılmıyorsa `result="unknown"`, `ok=None`:
    "kanıt yok" ile "kanıt kırmızı" karıştırılmamalıdır.
    """
    body = _block_body(text, PROOF_BLOCK_TAG)
    if body is None:
        return None
    data = _fields(body, _PROOF_FIELD_ALIASES)
    if not data:
        return None
    raw = (data.get("result") or "").lower()
    result, ok = "unknown", None
    if any(w in raw for w in _GREEN_WORDS):
        result, ok = "green", True
    if any(w in raw for w in _RED_WORDS):
        result, ok = "red", False
    return {
        "command": data.get("command", ""),
        "result": result,
        "ok": ok,
        "summary": data.get("summary", ""),
        "raw_result": data.get("result", ""),
    }


def checkpoint_instruction(card_id: str = "") -> str:
    """Alt ajana verilen blok yazma talimatı (harness istemin sonuna ekler)."""
    hedef = f" ({card_id})" if card_id else ""
    return (
        f"İşin bitince{hedef} yanıtının SONUNA şu iki bloğu ekle:\n"
        f"{CHECKPOINT_BLOCK_TAG}\n"
        "yapılan: <bir cümle>\n"
        "sonraki: <bir cümle>\n"
        "dosyalar: <virgülle ayrılmış yollar>\n"
        "testler: <komut ve sonuç>\n"
        f"{PROOF_BLOCK_TAG}\n"
        "komut: <koştuğun doğrulama komutu>\n"
        "sonuç: yeşil|kırmızı\n"
        "özet: <tek satır çıktı özeti>"
    )
