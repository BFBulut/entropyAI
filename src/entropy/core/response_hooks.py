"""
Entropy'nin sohbet yanıtı üzerindeki tek kanca (Faz 12-B).

İki iş yapar ve ikisi de iki köprüde AYNI yerden geçer (`core.provider`
karışımındaki `finalize_chat_text`), yani agy ve claude kolları ayrışamaz:

1. **Otonom görev üretimi** — yanıttaki `[PANO board_create] {json} [/PANO]`
   bloğu bir kart doğurur (`agents.board_autonomy`), tetikleyici uyandırılır ve
   blok, görüntülenen metinden çıkarılıp yerine tek satırlık makbuz konur.
2. **Özet temizliği** — geriye kalan araç/etiket blokları
   (`[PANO …]`, `[KONTROL NOKTASI]`, `[KANIT]`, `[KURAL]`) kullanıcıya
   gösterilen metinden ve sohbet geçmişinden çıkarılır.

Neden köprüde, arayüzde değil: sohbet geçmişini (`_save_chat_turn`) ve
`bus.agent_turn_completed` yükünü köprü üretiyor. Arayüzde temizlemek, ham
JSON'un diskteki geçmişe ve bağlam kurucuya girmesini engellemezdi.

Geçersiz JSON yok sayılır (`board_tools.parse_tool_calls` bozuk bloğu atlar) ve
günlüğe düşer: tek yazım hatası turu çöpe atmamalı.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def entropy_tools_section() -> str:
    """
    Entropy'nin SİSTEM İSTEMİNE eklenecek pano araç sözleşmesi.

    Hafıza katmanının `memory.system_prompt.build_system_prompt` işlevi bu tek
    çağrıyı yapar; araç metninin kaynağı `agents.board_tools` olarak kalır
    (iki yerde iki sözleşme metni tutmak, araştırma C'nin ölçtüğü "sözleşme ile
    davranış çelişkisi" sınıfının ta kendisidir).

    Modül yoksa boş dize döner: istem üretimi asla bu yüzden patlamaz.
    """
    try:
        from entropy.agents.board_tools import tools_section

        return tools_section(for_entropy=True)
    except Exception:
        logger.debug("Entropy araç sözleşmesi üretilemedi", exc_info=True)
        return ""


def process_chat_response(text: str, board=None, registry=None) -> str:
    """
    Sohbet yanıtını tüketir ve GÖRÜNTÜLENECEK metni döndürür.

    Yan etkileri (kart açma, tetikleyici uyandırma, olay yayma) burada olur;
    hiçbiri istisna yükseltmez. Blok yoksa metin (temizlik dışında) değişmez.
    """
    raw = text or ""
    if not raw.strip():
        return raw
    receipts = _consume_board_create(raw, board=board, registry=registry)
    try:
        from entropy.agents.board_tools import strip_tool_blocks

        cleaned = strip_tool_blocks(raw)
    except Exception:
        logger.debug("Araç blokları temizlenemedi", exc_info=True)
        cleaned = raw
    if not receipts:
        return cleaned
    tail = "\n".join(receipts)
    return (cleaned + "\n\n" + tail).strip() if cleaned else tail


def _consume_board_create(text: str, board=None, registry=None) -> List[str]:
    """`board_create` bloklarını yürütür; makbuz satırlarını döndürür."""
    try:
        from entropy.agents import board_autonomy, board_tools
    except Exception:
        return []
    try:
        calls = [c for c in board_tools.parse_tool_calls(text)
                 if c.name == "board_create"]
    except Exception:
        logger.warning("Pano blokları ayrıştırılamadı", exc_info=True)
        return []
    if not calls:
        return []

    receipts: List[str] = []
    limit = board_autonomy.MAX_CARDS_PER_TURN
    for call in calls[:limit]:
        try:
            card, note = board_autonomy.create_card_from_args(
                call.args, board=board, registry=registry
            )
        except Exception as exc:
            logger.warning("Otonom kart açılamadı: %s", exc, exc_info=True)
            receipts.append(f"Görev açılamadı: {exc}")
            continue
        if card is None:
            logger.info("board_create reddedildi: %s", note)
            receipts.append(f"Görev açılamadı: {note}")
            continue
        board_autonomy.announce(card)
        board_autonomy.wake_dispatcher()
        line = board_autonomy.receipt_line(card.title or card.id, card.agent or "")
        if note:
            line += f" ({note})"
        receipts.append(line)
    if len(calls) > limit:
        skipped = len(calls) - limit
        logger.info("Tur başına kart tavanı aşıldı: %d blok yok sayıldı", skipped)
        receipts.append(
            f"({skipped} kart bloğu yok sayıldı: tur başına en fazla {limit} kart)"
        )
    return receipts


__all__ = ["process_chat_response", "entropy_tools_section"]
