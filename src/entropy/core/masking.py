"""
Araç çıktısı maskeleme: uzun araç gövdelerini kısa bir yer tutucuya indirger.

Neden: bir turun ham metni ledger özetine, `bus.task_completed` özetine ve
belleğe yazılırken içindeki araç çıktısı blokları (dosya okuma, komut çıktısı,
grep sonucu) metnin %90'ını kaplayabiliyor. Bu bloklar bir sonraki turda modele
geri beslendiğinde bağlamı doldurur ama hiçbir bilgi taşımaz: özet için önemli
olan hangi aracın hangi kaynağa dokunduğudur, çıktının kendisi değil.

Aynı maske hem köprü (özet/ledger) hem de bellek yazımı (memory-rag) tarafında
kullanılır; tek yardımcı olması iki tarafın aynı metni farklı kırpmasını önler.
"""

from __future__ import annotations

import re
from typing import Optional

# Bu eşiğin üstündeki araç çıktısı gövdeleri yer tutucuya çevrilir. 2000 karakter
# ~500 token: bir hata iletisi ya da kısa dosya parçası bu sınırın altında kalır
# ve olduğu gibi korunur.
TOOL_OUTPUT_MASK_LIMIT = 2000

# Köprülerin ürettiği araç blokları. AGY: "[✔ ARAÇ TAMAMLANDI: Read (0.10s)]\n
# Sonuç: ..."; Claude Code: "[✔ Araç: Read] Sonuç: ...". Ortak biçim, blok
# başlığından sonra "Sonuç:" ya da "Result:" ile gelen gövdedir.
_BLOCK_RE = re.compile(
    r"(?P<head>\[(?:[^\[\]\n]*?)(?:ARAÇ|Araç|TOOL|Tool)(?:[^\[\]\n]*?)\][ \t]*\n?"
    r"[ \t]*(?:Sonuç|Sonuc|Result|Output|Çıktı)\s*:\s*)"
    r"(?P<body>.*?)"
    r"(?=\n\[|\Z)",
    re.DOTALL,
)

# Kaynak ipucu: blok başlığındaki araç adı ve gövdedeki ilk yol/komut.
_TOOL_NAME_RE = re.compile(r"(?:ARAÇ|Araç|TOOL|Tool)[^:\]]*:\s*([A-Za-z0-9_\-\.]+)")
_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s\"'<>|]+|/[^\s\"'<>|]{3,})")


def _describe_source(head: str, body: str) -> str:
    """Maskelenen bloğun kaynağını (araç adı + yol/komut) tek satırda anlatır."""
    parts = []
    m = _TOOL_NAME_RE.search(head)
    if m:
        parts.append(m.group(1))
    p = _PATH_RE.search(body[:400])
    if p:
        parts.append(p.group(0))
    return " ".join(parts) if parts else "bilinmiyor"


def mask_tool_output(text: Optional[str], limit: int = TOOL_OUTPUT_MASK_LIMIT) -> str:
    """
    Metindeki uzun araç çıktısı gövdelerini yer tutucuyla değiştirir.

    Yer tutucu biçimi: `[araç çıktısı: N karakter, kaynak: <yol/komut>]`.
    Sınırın altındaki bloklara ve araç bloğu olmayan metne dokunulmaz; girdi
    boşsa boş dize döner (çağıranların None kontrolü yapmasına gerek kalmasın).
    """
    if not text:
        return ""

    def _repl(m: re.Match) -> str:
        body = m.group("body")
        if len(body) <= limit:
            return m.group(0)
        source = _describe_source(m.group("head"), body)
        return f"{m.group('head')}[araç çıktısı: {len(body)} karakter, kaynak: {source}]"

    return _BLOCK_RE.sub(_repl, text)
