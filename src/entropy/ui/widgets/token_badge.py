"""
Token rozeti metni — Zen ve Chat modlarının ortak biçimlendiricisi.

Önceki rozet tek bir sayaç gösteriyordu ve o sayaç "son olay"a göre anlam
değiştiriyordu: sohbet turu bittiğinde son turun deltası, arka plan görevi
bittiğinde o görevin toplamı — ikisi de "Tokens: N" etiketiyle. Damıtma
sırasında görülen "Tokens: 62,226" sohbet kullanımı sanılıyordu.

Bu biçimlendirici iki kalemi her zaman ayrı ve adıyla gösterir:
  Sohbet: <oturum toplamı> (+son tur)  ·  Arka plan: <toplam> (son görev)
"""

from __future__ import annotations

from typing import Any, Tuple


def _k(n: int) -> str:
    """Kısa gösterim: 950 -> '950', 62_226 -> '62k', 1_250_000 -> '1.25M'."""
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n // 1_000}k"
    return str(n)


def format_token_badge(bridge: Any) -> Tuple[str, str]:
    """(rozet metni, araç ipucu) döndürür; tüm değerler köprüden okunur."""
    sess = int(getattr(bridge, "session_total_tokens", 0) or 0)
    turn_total = int(getattr(bridge, "total_tokens_used", 0) or 0)
    turn_out = int(getattr(bridge, "latest_output_tokens", 0) or 0)
    turn_in = int(getattr(bridge, "latest_input_tokens", 0) or 0)
    turn_think = int(getattr(bridge, "latest_thinking_tokens", 0) or 0)
    turn_cache = int(getattr(bridge, "latest_cache_read_tokens", 0) or 0)
    turns = int(getattr(bridge, "session_turn_count", 0) or 0)
    sess_cache = int(getattr(bridge, "session_cache_tokens", 0) or 0)

    bg_total = int(getattr(bridge, "background_total_tokens", 0) or 0)
    last_bg = dict(getattr(bridge, "last_background_usage", {}) or {})
    last_bg_total = int(last_bg.get("total_tokens", 0) or 0)

    chat_part = f"Sohbet: {_k(sess)}" + (f" (+{_k(turn_total)})" if turn_total > 0 else "")
    bg_part = f"Arka plan: {_k(bg_total)}" + (f" (son {_k(last_bg_total)})" if last_bg_total > 0 else "")

    if sess == 0 and bg_total == 0:
        text = "Tokens: 0"
    elif bg_total == 0:
        text = chat_part
    elif sess == 0:
        text = bg_part
    else:
        text = f"{chat_part}  ·  {bg_part}"

    tooltip = (
        "Gerçek Antigravity (AGY) token kullanımı\n"
        "\n"
        "SOHBET (bu konuşma)\n"
        f"• Oturum toplamı: {sess:,} token ({turns} tur)\n"
        f"• Son tur: {turn_total:,} = girdi {turn_in:,} + çıktı {turn_out:,} "
        f"(düşünme {turn_think:,} çıktı içinde; önbellek {turn_cache:,})\n"
        f"• Oturum önbellek toplamı: {sess_cache:,}\n"
        "\n"
        "ARKA PLAN (damıtma, konsolidasyon, zamanlanmış görevler)\n"
        f"• Uygulama açıldığından beri: {bg_total:,} token\n"
        + (
            f"• Son görev: {last_bg_total:,} = girdi {int(last_bg.get('input_tokens', 0) or 0):,} "
            f"+ çıktı {int(last_bg.get('output_tokens', 0) or 0):,}\n"
            if last_bg_total
            else "• Henüz arka plan görevi çalışmadı\n"
        )
        + "\nGörev başına kalıcı kayıt: Görevler sekmesi / tasks_ledger.db"
    )
    return text, tooltip
