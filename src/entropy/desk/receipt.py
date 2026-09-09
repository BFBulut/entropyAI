"""
Ofis raporu = "makbuz": bölümlere ayırma, bulma ve salt-okuma HTML'i.

Faz 10-C. Ofis raporu `Offices/<ofis>/reports/<kart>.md` altında durur ve
sözleşmeye göre şu `##` başlıklarını taşır:

    Plan · İlerleme · Değerlendirme · Kanıt · Değişiklikler · PR · Maliyet ·
    Yorumlar

Bu modülde Qt YOKTUR: ayrıştırma saf fonksiyondur, hem Desk'in makbuz bölmesi
hem de Zen Rapor Merkezi'nin salt-okuma görünümü aynı kaynağı kullanır (tek
üretici kuralı). Eksik bölüm hata değildir; ilgili başlık "—" ile görünür,
böylece kullanıcı raporun neyi *yazmadığını* da görür.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Makbuz bölümleri: gösterim sırası sözleşmedeki sıradır.
RECEIPT_SECTIONS: Tuple[str, ...] = (
    "Plan",
    "İlerleme",
    "Değerlendirme",
    "Kanıt",
    "Değişiklikler",
    "PR",
    "Maliyet",
    "Yorumlar",
)

# Bölüm başına ikon: katlanabilir başlıkta göz taraması kolaylaşsın.
SECTION_ICONS: Dict[str, str] = {
    "Plan": "🗺",
    "İlerleme": "⏳",
    "Değerlendirme": "⚖",
    "Kanıt": "🔬",
    "Değişiklikler": "📝",
    "PR": "🔀",
    "Maliyet": "💰",
    "Yorumlar": "💬",
}

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _normalize(name: str) -> str:
    """Başlık eşlemesi için: kılıf ve baştaki/sondaki işaretler yok sayılır."""
    return re.sub(r"[^0-9a-zçğıöşü]+", "", (name or "").strip().lower())


_NORMALIZED = {_normalize(s): s for s in RECEIPT_SECTIONS}
# Türkçe kılıf tuzağı: "İLERLEME".lower() → "i̇lerleme" (birleşik nokta).
_NORMALIZED.setdefault("i̇lerleme", "İlerleme")
_NORMALIZED.setdefault("degerlendirme", "Değerlendirme")
_NORMALIZED.setdefault("degisiklikler", "Değişiklikler")
_NORMALIZED.setdefault("kanit", "Kanıt")


def canonical_section(name: str) -> str:
    """Rapordaki başlığı sözleşme adına eşler; tanınmazsa ham adı döner."""
    return _NORMALIZED.get(_normalize(name), (name or "").strip())


def parse_receipt(text: str) -> Dict[str, str]:
    """
    `##` başlıklarına göre bölümleri çıkarır → {bölüm adı: gövde}.

    Tanınmayan başlıklar da sözlüğe girer (rapor kaybolmasın); sıralamayı
    `receipt_order()` verir.
    """
    body = str(text or "")
    out: Dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        name = canonical_section(m.group(1))
        chunk = body[start:end].strip()
        if name in out and chunk:
            out[name] = (out[name] + "\n\n" + chunk).strip()
        else:
            out[name] = chunk
    return out


def receipt_order(sections: Dict[str, str]) -> List[str]:
    """Sözleşme sırası önce, tanınmayan başlıklar sonda (alfabetik)."""
    known = [s for s in RECEIPT_SECTIONS]
    extra = sorted(k for k in sections if k not in RECEIPT_SECTIONS)
    return known + extra


def is_receipt(text: str) -> bool:
    """Metin ofis makbuzu mu? En az üç sözleşme bölümü varsa evet."""
    found = set(parse_receipt(text)) & set(RECEIPT_SECTIONS)
    return len(found) >= 3


def receipt_summary(sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Rozetler için özet: kanıt var mı, PR bağlantısı, maliyet satırı, değişiklik
    sayısı. Hepsi metinden okunur; ajan katmanına çağrı yapılmaz.
    """
    proof = (sections.get("Kanıt") or "").strip()
    changes = (sections.get("Değişiklikler") or "").strip()
    pr = (sections.get("PR") or "").strip()
    cost = (sections.get("Maliyet") or "").strip()
    url = ""
    m = re.search(r"https?://\S+", pr)
    if m:
        url = m.group(0).rstrip(").,")
    change_lines = [
        ln for ln in changes.splitlines()
        if ln.strip().startswith(("-", "*", "|")) and "---" not in ln
    ]
    return {
        "has_proof": bool(proof and proof not in ("—", "-")),
        "proof_text": proof,
        "pr_url": url,
        "change_count": len(change_lines),
        "cost_text": cost.splitlines()[0].strip() if cost else "",
    }


# ---------------------------------------------------------------- dosya bulma


def office_reports_dir(office: str, vault_path: Any = None) -> Optional[Path]:
    """`<kasa>/Desk/Offices/<ofis>/reports`; kasa yolu çözülemezse None."""
    if not office:
        return None
    try:
        from entropy.core import paths as _paths
        from entropy.core.config import config

        base = vault_path if vault_path is not None else config.obsidian_vault_path
        return _paths.desk_offices_dir(Path(base)) / office / "reports"
    except Exception:
        return None


def find_receipt_path(office: str, card_id: str, vault_path: Any = None) -> Optional[Path]:
    """
    Kartın makbuz dosyası: `reports/<kart>.md`. Tam ad yoksa kart kimliğini
    İÇEREN ilk dosyaya düşülür (ajan katmanı adı zenginleştirebilir).
    """
    directory = office_reports_dir(office, vault_path)
    if directory is None or not card_id:
        return None
    exact = directory / f"{card_id}.md"
    if exact.exists():
        return exact
    try:
        candidates = sorted(p for p in directory.glob("*.md") if card_id in p.name)
    except Exception:
        candidates = []
    return candidates[0] if candidates else None


def load_receipt(office: str, card_id: str, vault_path: Any = None) -> Tuple[Optional[Path], str]:
    """(yol, ham metin); dosya yoksa (None, "")."""
    path = find_receipt_path(office, card_id, vault_path)
    if path is None:
        return None, ""
    try:
        return path, path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return path, ""


# ---------------------------------------------------------------- HTML


def _section_body_html(name: str, body: str, css: Dict[str, str]) -> str:
    """Bölüm gövdesi: markdown tablo/listesi kaba biçimle HTML'e çevrilir."""
    text = (body or "").strip()
    if not text:
        return f"<div style='color:{css['dim']};'>—</div>"
    lines = text.splitlines()
    out: List[str] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append(
                    f"<table cellspacing='0' cellpadding='4' "
                    f"style='border-collapse:collapse; margin:4px 0;'>"
                )
                in_table = True
            row = "".join(
                f"<td style='border:1px solid {css['line']}; color:{css['body']};"
                f" font-size:11px;'>{html.escape(c)}</td>"
                for c in cells
            )
            out.append(f"<tr>{row}</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            out.append(
                f"<div style='color:{css['body']}; font-size:11px; margin-left:10px;'>"
                f"• {html.escape(stripped[2:])}</div>"
            )
        else:
            out.append(
                f"<div style='color:{css['body']}; font-size:11px;'>{html.escape(stripped)}</div>"
            )
    if in_table:
        out.append("</table>")
    return "".join(out)


def receipt_html(sections: Dict[str, str], tokens: Optional[Dict[str, str]] = None) -> str:
    """
    Makbuzun salt-okuma HTML'i (Zen Rapor Merkezi ve Desk özeti aynı çıktıyı
    kullanır). `tokens` verilmezse okuma teması yüklenir; tema yoksa yalın
    renkler kullanılır (widget'sız testlerde de çalışsın).
    """
    css = {"body": "#C9D1D9", "dim": "#8B949E", "line": "#1F2B42",
           "accent": "#58A6FF", "text": "#F0F6FC"}
    if tokens:
        css.update(tokens)
    else:
        try:
            from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

            css.update({
                "body": RT["text_body"], "dim": RT["text_dim"],
                "line": RT["divider_soft"], "accent": RT["accent"], "text": RT["text"],
            })
        except Exception:
            pass
    summary = receipt_summary(sections)
    parts = [f"<div style='font-family:sans-serif;'>"]
    badges = []
    badges.append(
        "🔬 kanıt var" if summary["has_proof"] else "🔬 kanıt yok"
    )
    if summary["change_count"]:
        badges.append(f"📝 {summary['change_count']} değişiklik")
    if summary["pr_url"]:
        badges.append("🔀 PR")
    if summary["cost_text"]:
        badges.append(f"💰 {summary['cost_text'][:40]}")
    parts.append(
        f"<div style='color:{css['dim']}; font-size:11px; margin-bottom:6px;'>"
        + " · ".join(html.escape(b) for b in badges)
        + "</div>"
    )
    for name in receipt_order(sections):
        if name not in sections and name not in RECEIPT_SECTIONS:
            continue
        icon = SECTION_ICONS.get(name, "▪")
        parts.append(
            f"<div style='color:{css['accent']}; font-size:12px; font-weight:600;"
            f" margin-top:8px;'>{icon} {html.escape(name)}</div>"
        )
        parts.append(_section_body_html(name, sections.get(name, ""), css))
    if summary["pr_url"]:
        url = html.escape(summary["pr_url"])
        parts.append(
            f"<div style='margin-top:8px;'><a href='{url}' style='color:{css['accent']};"
            f" font-size:11px;'>{url}</a></div>"
        )
    parts.append("</div>")
    return "".join(parts)


# Geriye/dışa dönük ad: makbuz bölüm gövdesini HTML'e çeviren yardımcı.
section_body_html = _section_body_html
