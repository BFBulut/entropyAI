"""Slash komutlarının istem metninden ayıklanması (Faz 9).

Sorun (kullanıcı, gerçek koşu): `/media-agency-soldier reklam metni yaz` yazınca
üst çubukta "🎯 YETENEK: /media-agency-soldier" çipi belirdi ama sağlayıcı CLI'ı
`Unknown command: /media-agency-soldier` döndürdü. Kök neden: arayüz yetenek
slash'ını tanıyıp yeteneği etkinleştiriyor, ama token'ı istemden **çıkarmıyordu**;
ham metin CLI'a gidiyor, CLI kendi ad alanında bulamıyordu
(bkz. `docs/reports/2026-09-11_Faz9_Teshis_Notu.md` §4).

Bu modül saf metin işidir (Qt'siz), Chat ve Zen aynı davranışı paylaşsın diye
tek yerde durur.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set


def strip_slash_token(prompt: str, token: str) -> str:
    """`/token` geçişini istemden bir kez siler, kalanı döndürür."""
    name = str(token or "").lstrip("/")
    if not name:
        return prompt
    pattern = re.compile(r"(?:^|\s)/" + re.escape(name) + r"\b[ \t]*", re.IGNORECASE)
    return pattern.sub(" ", prompt, count=1).strip()


def strip_skill_tokens(prompt: str, tokens: Iterable[str]) -> str:
    """Yetenek slash token'larının hepsini istemden temizler."""
    out = prompt
    for token in tokens:
        out = strip_slash_token(out, token)
    return out.strip()


def unknown_slash_token(
    prompt: str,
    known_tokens: Set[str],
    passthrough: Optional[Set[str]] = None,
) -> str:
    """İstem bilinmeyen bir slash komutuyla BAŞLIYORSA o token'ı döndürür.

    Yalnızca ilk token denetlenir: metin ortasındaki `/foo` bir yol ya da tarih
    olabilir, onu engellemek kullanıcıyı bloke ederdi. `passthrough` sağlayıcı
    CLI'ının kendi tanıdığı komutlardır (ör. `/compact`) — bunlar geçirilir.
    """
    text = str(prompt or "").strip()
    if not text.startswith("/"):
        return ""
    match = re.match(r"/([a-zA-Z0-9_\-:]+)", text)
    if not match:
        return ""
    token = match.group(1).lower()
    if token in {t.lstrip("/").lower() for t in known_tokens}:
        return ""
    if passthrough and token in {t.lstrip("/").lower() for t in passthrough}:
        return ""
    return token


#: Sağlayıcı CLI'ının kendi tanıdığı, Entropy kaydında olmasa da geçirilecek komutlar.
CLI_PASSTHROUGH = {
    "compact", "clear", "cost", "review", "resume", "context", "output-style",
    "vim", "memory", "init", "add-dir", "mcp", "config", "doctor", "status",
}


def unknown_slash_html(token: str, suggestions: Optional[List[str]] = None) -> str:
    """Bilinmeyen slash için Entropy'nin kendi hata metni (CLI'a gitmez)."""
    body = (
        f"❓ <b>Bilinmeyen komut:</b> <code>/{token}</code><br/>"
        "Bu komut Entropy'nin kayıtlı komutları, yetenekleri ve MCP araçları"
        " arasında yok; sağlayıcıya da gönderilmedi."
    )
    if suggestions:
        shown = ", ".join(f"<code>/{s.lstrip('/')}</code>" for s in suggestions[:5])
        body += f"<br/>Bunu mu demek istediniz: {shown}"
    body += "<br/>Tüm komutlar için <code>/help</code> yazın."
    return body


def close_matches(token: str, known_tokens: Iterable[str], limit: int = 5) -> List[str]:
    """Basit ön ek/alt dize eşleşmesiyle öneri listesi."""
    token = str(token or "").lstrip("/").lower()
    if not token:
        return []
    out: List[str] = []
    for candidate in known_tokens:
        name = str(candidate).lstrip("/")
        low = name.lower()
        if low.startswith(token[:3]) or token in low:
            out.append(name)
        if len(out) >= limit:
            break
    return out
