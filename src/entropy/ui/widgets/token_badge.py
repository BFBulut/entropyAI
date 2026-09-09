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

    # Ek-1 (Faz 9): `total_tokens_used` artik YALNIZCA son turun toplami
    # (claude_bridge._apply_chat_usage). Oturum toplami `session_total_tokens`.
    # Onbellek okumasi ayri kalem olarak gosterilir; oturumun buyuk kismi
    # onbellekten geliyorsa "Sohbet: 77k" rakami pahali sanilmasin.
    chat_part = f"Sohbet: {_k(sess)}" + (f" (+{_k(turn_total)})" if turn_total > 0 else "")
    if sess_cache > 0:
        chat_part += f"  ·  önbellek {_k(sess_cache)}"
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
        + usage_breakdown_text(bridge)
        + "\nGörev başına kalıcı kayıt: Görevler sekmesi / tasks_ledger.db"
    )
    return text, tooltip


# Bağlam doluluğu bu oranı aşınca rozet turuncuya döner ve /handoff önerilir.
CONTEXT_WARN_RATIO = 0.60

CONTEXT_OK_COLOR = "#3DE8A8"
CONTEXT_WARN_COLOR = "#FFC24D"


def usage_breakdown_text(bridge: Any) -> str:
    """
    `bridge.usage_breakdown()` varsa kalem kalem döküm satırları üretir.

    Claude tarafında önbellek YAZIMI ayrı ücretlendirilir ve önbellek okumasıyla
    karıştırılırsa maliyet yanlış okunur; bu yüzden ayrı bir kalem olarak
    gösterilir. Köprü bu metodu sunmuyorsa boş dize döner (geriye dönük uyum).
    """
    fn = getattr(bridge, "usage_breakdown", None)
    if not callable(fn):
        return ""
    try:
        data = dict(fn() or {})
    except Exception:
        return ""
    if not data:
        return ""
    return (
        "\nKALEM DÖKÜMÜ\n"
        f"• Girdi: {int(data.get('input', 0) or 0):,}\n"
        f"• Çıktı: {int(data.get('output', 0) or 0):,}\n"
        f"• Önbellek okuma: {int(data.get('cache_read', 0) or 0):,}\n"
        f"• Önbellek yazımı: {int(data.get('cache_write', 0) or 0):,}\n"
        f"• Toplam: {int(data.get('total', 0) or 0):,}\n"
    )


def context_fill_ratio(bridge: Any, pressure: float = None) -> float:
    """
    Bağlam doluluk oranı: önce köprünün kendi ölçümü, yoksa son sinyal değeri.

    `bus.context_pressure` yalnızca eşiğin üstüne ilk çıkışta yayıldığı için tek
    kaynak olamaz; köprü `context_fill_ratio()` sunuyorsa o esas alınır.
    """
    fn = getattr(bridge, "context_fill_ratio", None)
    if callable(fn):
        try:
            value = float(fn())
            if value > 0:
                return value
        except Exception:
            pass
    try:
        return max(0.0, float(pressure or 0.0))
    except Exception:
        return 0.0


def format_context_badge(bridge: Any, pressure: float = None):
    """
    (metin, ipucu, renk) — bağlam doluluk rozeti.

    %60 üstünde rozet turuncuya döner ve ipucu /handoff önerir; bu eşik
    `provider.CONTEXT_PRESSURE_THRESHOLD` ile aynıdır.
    """
    ratio = context_fill_ratio(bridge, pressure)
    percent = int(round(ratio * 100))
    text = f"Bağlam: %{percent}"
    warn = ratio >= CONTEXT_WARN_RATIO
    color = CONTEXT_WARN_COLOR if warn else CONTEXT_OK_COLOR

    used = 0
    window = 0
    try:
        used = int(bridge.context_used_tokens())
        window = int(bridge.context_window_size())
    except Exception:
        pass
    lines = [f"Bağlam penceresi doluluğu: %{percent}"]
    if window:
        lines.append(f"Kullanılan: {used:,} / {window:,} token")
    if warn:
        lines.append("")
        lines.append("Doluluk %60'ı aştı — /handoff önerilir.")
        lines.append("Aktarım geçmişi özetleyip bağlamı boşaltır.")
    return text, "\n".join(lines), color


def format_token_badge_from_detail(detail: Any) -> Tuple[str, str]:
    """
    `bus.token_usage_detail` sozlugunden rozet metni (Faz 9).

    Kopru sinyali `{"session", "turn", "cache_read", "cost_weighted"}` yayar
    (`ClaudeCodeBridge.usage_badge_fields`). Rozet bu tek kaynagi okur; koprunun
    ic alanlarini widget'lardan tek tek okumak, `total_tokens_used`in anlami
    degistiginde (oturum -> son tur) sessiz yanlis sayilara yol acmisti.
    """
    d = dict(detail or {})
    sess = int(d.get("session", 0) or 0)
    turn = int(d.get("turn", 0) or 0)
    cache = int(d.get("cache_read", 0) or 0)
    weighted = int(d.get("cost_weighted", 0) or 0)

    if sess == 0 and turn == 0:
        text = "Tokens: 0"
    else:
        text = f"Sohbet: {_k(sess)}" + (f" (+{_k(turn)})" if turn > 0 else "")
        if cache > 0:
            text += f"  ·  önbellek {_k(cache)}"
    tooltip = (
        "SOHBET (bu konusma)\n"
        f"• Oturum toplamı: {sess:,} token\n"
        f"• Son tur: {turn:,}\n"
        f"• Önbellek okuması (oturum): {cache:,}\n"
        f"• Maliyet ağırlıklı toplam: {weighted:,}\n"
    )
    return text, tooltip
