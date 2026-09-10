"""
Rapor → sohbet kartı (Faz 11-C, iş 3).

Sözleşme: `bus.task_report_ready(dict)` =
`{card_id, title, agent, status, ok, summary, report_path, output_paths}`.

Bir ajan işini bitirdiğinde raporu kasaya düşüyor ama sohbette hiçbir iz
kalmıyordu: kullanıcı raporu ancak Raporlar sekmesinde arayarak buluyordu.
Bu modül yükü iki yüzeye çevirir:

* `report_card_html(payload)` — sohbete basılan kart (özet ilk 300 karakter,
  "Raporu aç" ve "Sohbete al" bağlantıları).
* `report_context_block(payload)` — "Sohbete al" seçilince bir sonraki
  istemin başına eklenen `[RAPOR: …] … [/RAPOR]` bloğu.

İki bağlantı şeması: `entropy-report://<yol>` (mevcut rapor okuyucu) ve
`entropy-context://<kart_id>` (bağlam kuyruğu). İkisi de modların
`_on_anchor_clicked` işleyicisinde çözülür.

Qt gerektirmez; testten doğrudan çağrılabilir.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Sohbet kartında gösterilen özet uzunluğu (sözleşme: ilk 300 karakter).
SUMMARY_LIMIT = 300

CONTEXT_SCHEME = "entropy-context://"
REPORT_SCHEME = "entropy-report://"


def normalize_report_payload(payload: Any) -> Dict[str, Any]:
    """Yükü sözleşme alanlarına indirger; eksik alan uydurulmaz, boş kalır."""
    data = payload if isinstance(payload, dict) else {}
    outputs = data.get("output_paths") or []
    if isinstance(outputs, (str, Path)):
        outputs = [str(outputs)]
    return {
        "card_id": str(data.get("card_id") or ""),
        "title": str(data.get("title") or "(başlıksız görev)"),
        "agent": str(data.get("agent") or ""),
        "status": str(data.get("status") or ""),
        "ok": bool(data.get("ok")),
        "summary": str(data.get("summary") or ""),
        "report_path": str(data.get("report_path") or ""),
        "output_paths": [str(p) for p in outputs if str(p)],
    }


def short_summary(text: str, limit: int = SUMMARY_LIMIT) -> str:
    """Özetin ilk `limit` karakteri; kesilirse sonuna üç nokta konur."""
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def resolve_report_path(payload: Dict[str, Any]) -> str:
    """Açılacak dosya: önce `report_path`, yoksa ilk `.md` çıktısı."""
    data = normalize_report_payload(payload)
    if data["report_path"]:
        return data["report_path"]
    for path in data["output_paths"]:
        if str(path).lower().endswith(".md"):
            return str(path)
    return data["output_paths"][0] if data["output_paths"] else ""


def report_card_html(payload: Dict[str, Any]) -> str:
    """Sohbete basılan rapor kartı (belirteç renkleri, yerel onaltılık yok)."""
    from entropy.ui.design import TOKENS

    c = TOKENS["color"]
    ty = TOKENS["type"]
    space = TOKENS["space"]
    data = normalize_report_payload(payload)
    tone = c["ok"] if data["ok"] else c["warn"]
    title = html.escape(data["title"])
    meta_bits = [b for b in (data["agent"], data["status"]) if b]
    meta = html.escape(" · ".join(meta_bits))
    summary = html.escape(short_summary(data["summary"]))
    path = resolve_report_path(data)

    parts = [
        f"<div style='background:{c['surface.raised']}; border:1px solid {tone};"
        f" border-radius:{TOKENS['radius']['md']}px;"
        f" padding:{space['2']}px {space['3']}px; margin:{space['2']}px 0;'>",
        f"<div style='color:{tone}; font-size:{ty['label']['size']}px;"
        f" font-weight:bold; letter-spacing:0.6px;'>RAPOR GELDİ</div>",
        f"<div style='color:{c['text']}; font-size:{ty['body']['size']}px;"
        f" font-weight:bold; margin:{space['1']}px 0;'>{title}</div>",
    ]
    if meta:
        parts.append(
            f"<div style='color:{c['text.muted']}; font-size:{ty['label']['size']}px;'>"
            f"{meta}</div>"
        )
    if summary:
        parts.append(
            f"<div style='color:{c['text']}; font-size:{ty['label']['size']}px;"
            f" margin:{space['2']}px 0;'>{summary}</div>"
        )
    links = []
    if path:
        links.append(
            f"<a href='{REPORT_SCHEME}{Path(path).as_posix()}'"
            f" style='color:{c['accent']}; font-size:{ty['label']['size']}px;"
            f" text-decoration:none; margin-right:{space['3']}px;'>Raporu aç</a>"
        )
    links.append(
        f"<a href='{CONTEXT_SCHEME}{html.escape(data['card_id'] or data['title'])}'"
        f" style='color:{c['accent']}; font-size:{ty['label']['size']}px;"
        f" text-decoration:none;'>Sohbete al</a>"
    )
    parts.append("<div>" + "".join(links) + "</div>")
    parts.append("</div>")
    return "".join(parts)


def report_context_block(payload: Dict[str, Any]) -> str:
    """"Sohbete al": bir sonraki isteme eklenen düz metin bloğu."""
    data = normalize_report_payload(payload)
    head_bits = [data["title"]]
    if data["agent"]:
        head_bits.append(data["agent"])
    if data["status"]:
        head_bits.append(data["status"])
    lines = ["[RAPOR: " + " | ".join(head_bits) + "]"]
    summary = short_summary(data["summary"])
    if summary:
        lines.append(summary)
    path = resolve_report_path(data)
    if path:
        lines.append(f"Kaynak: {path}")
    lines.append("[/RAPOR]")
    return "\n".join(lines)


def notification_title(payload: Dict[str, Any]) -> str:
    """Bildirim merkezi girdisinin başlığı."""
    data = normalize_report_payload(payload)
    bits = [data["title"]]
    if data["agent"]:
        bits.append(data["agent"])
    return " · ".join(bits)


class ReportContextQueue:
    """
    "Sohbete al" ile biriken rapor bloklarının kuyruğu.

    Kuyruk bir sonraki isteme eklenir ve boşaltılır: aynı rapor iki kez
    gönderilmez. Qt'siz, testten doğrudan çağrılabilir.
    """

    def __init__(self) -> None:
        self._payloads: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []

    def add(self, payload: Dict[str, Any]) -> str:
        data = normalize_report_payload(payload)
        key = data["card_id"] or data["title"]
        if key not in self._payloads:
            self._order.append(key)
        self._payloads[key] = data
        return key

    def has(self, key: str) -> bool:
        return key in self._payloads

    def __len__(self) -> int:
        return len(self._order)

    def blocks(self) -> List[str]:
        return [report_context_block(self._payloads[k]) for k in self._order]

    def apply(self, prompt: str) -> str:
        """Kuyruğu istemin başına ekler ve kuyruğu boşaltır."""
        if not self._order:
            return prompt
        prefix = "\n\n".join(self.blocks())
        self.clear()
        return f"{prefix}\n\n{prompt}" if prompt else prefix

    def clear(self) -> None:
        self._payloads.clear()
        self._order.clear()


def find_payload(payloads: Dict[str, Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    """`entropy-context://<anahtar>` çözümü; bulunamazsa None."""
    return payloads.get(key)
