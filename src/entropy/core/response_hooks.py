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

        section = tools_section(for_entropy=True)
    except Exception:
        logger.debug("Entropy araç sözleşmesi üretilemedi", exc_info=True)
        section = ""
    # Faz 14-C: geçici ajan çağrısı. Kart açmak (`board_create`) uzun soluklu
    # iş içindir; bir yetenek/araştırma koşusu için kart, kadro ve tetikleyici
    # gerekmez — `[AJAN run]` bloğu tek seferlik bir ajan doğurur.
    try:
        from entropy.agents.ephemeral import AGENT_TOOL_SECTION

        section = (section + "\n\n" + AGENT_TOOL_SECTION).strip()
    except Exception:
        logger.debug("Geçici ajan sözleşmesi eklenemedi", exc_info=True)
    return section


def _active_provider() -> str:
    """
    Sohbet turunu koşan sağlayıcının adı ("claude" | "agy" | "").

    Önce canlı köprünün `provider_name`i, o yoksa yapılandırmanın varsayılanı
    okunur. Neden gerekli: `[DESK …]` düzenleme blokları YALNIZCA claude sohbet
    yolunda geçerlidir (Faz 13-C.3); agy kolunda blok metinden temizlenir ama
    hiçbir şey uygulanmaz.
    """
    try:
        from entropy.ui.manager import EntropyUIManager

        mgr = getattr(EntropyUIManager, "instance", None)
        bridge = getattr(mgr, "bridge", None) if mgr is not None else None
        name = str(getattr(bridge, "provider_name", "") or "").strip().lower()
        if name:
            return name
    except Exception:
        pass
    try:
        from entropy.core.config import config

        return str(config.default_provider() or "").strip().lower()
    except Exception:
        return ""


def process_chat_response(text: str, board=None, registry=None,
                          provider: str = "") -> str:
    """
    Sohbet yanıtını tüketir ve GÖRÜNTÜLENECEK metni döndürür.

    Yan etkileri (kart açma, tetikleyici uyandırma, olay yayma) burada olur;
    hiçbiri istisna yükseltmez. Blok yoksa metin (temizlik dışında) değişmez.
    """
    raw = text or ""
    if not raw.strip():
        return raw
    receipts = _consume_board_create(raw, board=board, registry=registry)
    # Faz 13-C.3: Entropy → Desk düzenlemesi. Yapısal bloklar onay kuyruğuna
    # düşer, `msg` doğrudan uygulanır; ikisi de YALNIZCA claude sohbet yolunda.
    receipts += _consume_desk_blocks(raw, provider=provider)
    # Faz 14-C: `[AJAN run]` — Entropy'nin kendi kararıyla geçici ajan açması.
    # Onay ARANMAZ: ajan açmak Entropy'nin işidir (kart açmak zaten onaysız);
    # ajanın izin isteyen araçları 14-B onay kuyruğundan geçer.
    receipts += _consume_agent_blocks(raw)
    try:
        from entropy.agents.board_tools import strip_tool_blocks

        cleaned = strip_tool_blocks(raw)
    except Exception:
        logger.debug("Araç blokları temizlenemedi", exc_info=True)
        cleaned = raw
    try:
        from entropy.agents.ephemeral import strip_agent_blocks

        cleaned = strip_agent_blocks(cleaned)
    except Exception:
        logger.debug("Geçici ajan bloğu temizlenemedi", exc_info=True)
    if not receipts:
        return cleaned
    tail = "\n".join(receipts)
    return (cleaned + "\n\n" + tail).strip() if cleaned else tail


def _consume_agent_blocks(text: str) -> List[str]:
    """`[AJAN run]` bloklarını tüketir; makbuz satırlarını döndürür."""
    try:
        from entropy.agents import ephemeral

        return list(ephemeral.consume_agent_blocks(text) or [])
    except Exception:
        logger.warning("Geçici ajan blokları tüketilemedi", exc_info=True)
        return []


def _consume_desk_blocks(text: str, provider: str = "") -> List[str]:
    """`[DESK …]` bloklarını tüketir (yalnız claude); makbuz satırları döner."""
    name = str(provider or "").strip().lower() or _active_provider()
    if name != "claude":
        return []
    try:
        from entropy.agents import desk_admin

        return list(desk_admin.consume_desk_calls(text) or [])
    except Exception:
        logger.warning("Desk blokları tüketilemedi", exc_info=True)
        return []


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


# --- "onaylıyorum" çözümü (Faz 14-B) ----------------------------------------
#
# Kullanıcı "onaylıyorum" yazdığında bu mesaj MODELE GİTMEZ: bekleyen iş
# kuyruğunda (`core/pending.py`) gerçek bir kayıt varsa kararı uygulama verir.
# Ölçülen arıza buydu — mesaj CLI'ya gidiyordu, modelin onaylanacak bir şeyi
# olmadığı için "bağlam bana ulaşmadı" ya da "iki komut onay bekliyor" diye
# uyduruyordu. Kuyruk boşsa yanıt TEK SATIR olur ve yine modele gidilmez.

_APPROVE_WORDS = (
    "onaylıyorum", "onayla", "onaylandı", "onay veriyorum", "evet onayla",
    "kabul ediyorum", "izin ver", "onaylıyom",
)
_REJECT_WORDS = (
    "reddet", "reddediyorum", "iptal et", "izin verme", "onaylamıyorum",
)


def _normalize_tr(text: str) -> str:
    """Türkçe güvenli küçültme (`İ`/`I` Python'da yanlış eşleşiyor)."""
    return (
        str(text or "")
        .replace("İ", "i")
        .replace("I", "ı")
        .lower()
        .strip()
        .strip(".!?,;: ")
    )


def parse_approval_command(text: str):
    """
    Mesajı onay komutuna çevirir: `(karar, kimlik)` ya da `None`.

    Kimlik yalnızca "onayla <id>" biçiminde verilirse dolar.
    """
    norm = _normalize_tr(text)
    if not norm or len(norm) > 120:
        return None
    parts = norm.split()
    head = parts[0]
    rest = " ".join(parts[1:]).strip()
    for word in _APPROVE_WORDS:
        if norm == word or (norm.startswith(word + " ") and len(word.split()) == 1):
            return ("approve", rest if head == word else "")
    for word in _REJECT_WORDS:
        if norm == word or norm.startswith(word + " "):
            return ("reject", rest if head == word else "")
    return None


def resolve_approval_message(text: str, pending_queue=None):
    """
    Onay komutunu kuyrukta çözer; sohbete basılacak TEK SATIRI döndürür.

    `None` dönerse mesaj onay komutu değildir ve normal tur akışı sürer.
    """
    parsed = parse_approval_command(text)
    if parsed is None:
        return None
    decision, wanted_id = parsed
    try:
        if pending_queue is None:
            from entropy.core.pending import PendingQueue

            pending_queue = PendingQueue()
        items = list(pending_queue.list() or [])
    except Exception:
        logger.warning("Bekleyen işler okunamadı", exc_info=True)
        return "Bekleyen onaylar okunamadı."
    if wanted_id:
        items = [i for i in items if str(i.get("id") or "").endswith(wanted_id)]
        if not items:
            return f"Bekleyen onay yok: {wanted_id}"
    if not items:
        return "Bekleyen onay yok."
    if len(items) > 1:
        lines = [
            f"{i + 1}. [{it.get('risk', 'low')}] {it.get('title') or it.get('id')} "
            f"(kimlik: {it.get('id')})"
            for i, it in enumerate(items)
        ]
        return (
            f"{len(items)} onay bekliyor; hangisi? "
            + " | ".join(lines)
            + " — 'onayla <kimlik>' yaz."
        )
    item = items[0]
    try:
        record = pending_queue.resolve(str(item.get("id")), decision)
    except Exception as exc:
        logger.warning("Onay uygulanamadı", exc_info=True)
        return f"Onay uygulanamadı: {exc}"
    title = str(record.get("title") or record.get("id") or "")
    if decision == "approve":
        return f"✔ onaylandı: {title}"
    return f"⛔ reddedildi: {title}"


__all__ = [
    "process_chat_response",
    "entropy_tools_section",
    "parse_approval_command",
    "resolve_approval_message",
]
