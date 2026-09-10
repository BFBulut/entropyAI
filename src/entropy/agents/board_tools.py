"""
Pano araçları — ajanın panoya YAZABİLDİĞİ tek sözleşme (Faz 11-C.5).

Neden dört (+bir) araç
----------------------
Ajanın gördüğü yüzey bilinçli olarak dar: izole kipte en fazla 8 yerleşik araç
var, MCP çekmecesi (119 ad ≈ 2.4k token) ve yetenek kataloğu (32 yetenek ≈
3.8k token) kapalı. Sorun "çok araç" değildi, **sıfır pano aracı**ydı: ajan
panoyu yalnızca isteme gömülen metinden görüyor, panoya hiçbir şey yazamıyordu;
kontrol noktası ve kanıt bile serbest metinden regex'le geri ayrıştırılıyordu.

Ajanın araçları:

  board_next(agent)      → sıradaki kart (bul + sahiplen + taşı, TEK çağrı)
  board_checkpoint(...)  → kontrol noktası (serbest metin değil, sözleşme)
  board_finish(...)      → KANIT zorunlu; kanıtsız kapanış reddedilir
  board_ask(...)         → Entropy'ye soru (posta kutusu), bloke etmez

Entropy'nin (ajanların DEĞİL) tek ek aracı:

  board_create(...)      → sohbetteki karardan kart doğurmak

Açıkça reddedilenler: `board_list/get/search/move/set_status/assign/release/
priority/comment/link/stats`. Her biri ya `board_next`in içinde birleşiktir, ya
insanın işidir (`review → done` insan onayıdır), ya da durum makinesini
dışarıdan bozar (`board_move` = keyfi geçiş, tablo anlamsızlaşır). Ajan durum
makinesinin kullanıcısı değil, KONUSUDUR.

Taşıma biçimi
-------------
Gerçek bir MCP sunucusu DEĞİL. Claude izole kipte `--strict-mcp-config` ile
koşuyor ve MCP ad alanı kapalı; agy'de karşılık gelen bir izolasyon yok. İki
sağlayıcıda da AYNI metin sözleşmesi kullanılır: ajan çıktısına satır başında

    [PANO board_finish]
    {"task_id": "...", "summary": "...", "proof": {...}}
    [/PANO]

bloğu yazar, harness bunu ayrıştırır. Etiket sabittir; serbest metinden çıkarım
her sağlayıcıda başka sonuç veriyordu (`CHECKPOINT_TAG` deneyimi).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

OPEN_RE = re.compile(r"^\[PANO\s+(board_[a-z_]+)\]\s*$", re.MULTILINE)
CLOSE_TAG = "[/PANO]"

# Ajanın gördüğü araçlar (Entropy'nin ek aracı listede DEĞİL).
AGENT_TOOLS: Tuple[str, ...] = ("board_next", "board_checkpoint",
                                "board_finish", "board_ask")
ENTROPY_TOOLS: Tuple[str, ...] = ("board_create",)
ALL_TOOLS: Tuple[str, ...] = AGENT_TOOLS + ENTROPY_TOOLS

# Dönüş biçimi kuralları (Anthropic araç rehberi 3-4): kimlik yerine ad,
# varsayılan `concise`, listeler kırpılır.
CRITERIA_LIMIT = 10
INPUT_PATHS_LIMIT = 40


class ToolError(Exception):
    """Araç çağrısı reddedildi. Mesaj YÖNLENDİRİCİDİR: ne yapılacağını söyler."""


@dataclass
class ToolCall:
    """Ajan çıktısından ayrıştırılmış tek araç çağrısı."""

    name: str
    args: Dict[str, object] = field(default_factory=dict)
    raw: str = ""


def parse_tool_calls(text: str) -> List[ToolCall]:
    """
    Ajan çıktısındaki `[PANO <araç>] … [/PANO]` bloklarını ayrıştırır.

    Bozuk JSON blok ATLANIR, istisna atılmaz: tek bir yazım hatası koşunun
    tamamını çöpe atmamalı; ayrıştırılamayan blok zaten hiçbir etki üretmez.
    """
    out: List[ToolCall] = []
    for m in OPEN_RE.finditer(text or ""):
        name = m.group(1)
        if name not in ALL_TOOLS:
            continue
        end = (text or "").find(CLOSE_TAG, m.end())
        body = (text or "")[m.end():end if end != -1 else len(text or "")]
        raw = body.strip()
        args: Dict[str, object] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    args = parsed
            except ValueError:
                continue
        out.append(ToolCall(name=name, args=args, raw=raw))
    return out


def validate_finish(args: Dict[str, object]) -> Optional[str]:
    """
    `board_finish` kanıt denetimi. Dönüş: hata metni ya da None.

    Close-with-proof kuralı araç düzeyinde: kanıtsız kapanış REDDEDİLİR ve
    hata mesajı ajanı testi koşmaya yönlendirir ("geçersiz" demekle yetinmez).
    Kart bu durumda `done` olmaz; `review`de insan önüne gelir.
    """
    proof = args.get("proof")
    if not isinstance(proof, dict) or not proof:
        return ("kanıt yok: testi koş ve `proof` alanını "
                '{"command": "pytest tests/... -q", "result": "<çıktı>", '
                '"green": true} biçiminde doldur')
    if not str(proof.get("command") or "").strip():
        return ("kanıt eksik: `proof.command` boş — koştuğun test komutunu "
                "aynen yaz (ör. `pytest tests/test_x.py -q`)")
    if not str(proof.get("result") or "").strip():
        return ("kanıt eksik: `proof.result` boş — komutun ÇIKTISINI yaz "
                "(ör. `12 passed in 3.4s`)")
    if proof.get("green") is not True:
        return ("kanıt yeşil değil: testler geçmeden kart kapanmaz; hatayı "
                "düzelt, testi yeniden koş ve `proof.green` alanını true yap")
    return None


def finish_outcome(args: Dict[str, object]) -> Tuple[str, Optional[str]]:
    """
    `board_finish` çağrısının sonucu: (hedef durum, ret nedeni).

    Kanıtsız çağrı kartı `review`de bırakır — ajan "bitti" diyemez ama işi de
    çöpe gitmez; kararı insan verir. Kanıt AÇIKÇA kırmızıysa (`green: false`)
    kart `failed`a düşer.
    """
    reason = validate_finish(args)
    proof = args.get("proof")
    if isinstance(proof, dict) and proof.get("green") is False:
        return "failed", reason
    if reason:
        return "review", reason
    return "review", None


def normalize_next(card) -> Dict[str, object]:
    """
    `board_next` dönüşü — yüksek sinyalli, kırpılmış.

    `uuid` yerine ad, tam yol yerine göreli yol; kriter listesi 10, girdi yolu
    40 ile sınırlı (mevcut `PROJECT_FILE_LIST_LIMIT` çıpası).
    """
    if card is None:
        return {}
    criteria = list(getattr(card, "criteria", None) or [])[:CRITERIA_LIMIT]
    inputs = list(getattr(card, "input_paths", None) or [])[:INPUT_PATHS_LIMIT]
    out: Dict[str, object] = {
        "task_id": getattr(card, "id", ""),
        "title": getattr(card, "title", ""),
        "goal": getattr(card, "goal", ""),
        "criteria": criteria,
        "input_paths": inputs,
        "agent": getattr(card, "agent", ""),
    }
    checkpoint = str(getattr(card, "checkpoint", "") or "")
    if checkpoint:
        out["checkpoint"] = checkpoint
    priority = str(getattr(card, "priority", "") or "")
    if priority:
        out["priority"] = priority
    return out


# --- isteme giren sözleşme metni ---------------------------------------------
# Ölçülebilir hedef: beş aracın toplam şema maliyeti ≤ 800 token. Karşılaştırma
# çıpası kodda: kapatılan MCP çekmecesi 119 araç ≈ 2.4k token.

_AGENT_TOOLS_TEXT = """[PANO ARAÇLARI]
Panoya yalnızca aşağıdaki bloklarla yazabilirsin. Blok SATIR BAŞINDA başlar,
gövdesi tek bir JSON nesnesidir ve `[/PANO]` ile kapanır.

[PANO board_next]
{"agent": "<adın>"}
[/PANO]
  Sıradaki kartı alır (bulur + sahiplenir + sana taşır). Tek kart döner.

[PANO board_checkpoint]
{"task_id": "<kart>", "done": "<bitirdiğin iş>", "next": "<sıradaki adım>",
 "files": ["<dokunduğun yollar>"], "tests": "<komut ve sonucu>"}
[/PANO]
  Her modül sonunda yaz. Koşu yarıda kesilirse bu bloktan sürdürülür.

[PANO board_finish]
{"task_id": "<kart>", "summary": "<özet>",
 "proof": {"command": "<koştuğun test>", "result": "<çıktısı>", "green": true},
 "outputs": ["<ürettiğin dosyalar>"]}
[/PANO]
  KANIT ZORUNLU: testi koşmadan kart kapanmaz. Kanıtsız çağrı reddedilir ve
  kart insan incelemesine (review) kalır.

[PANO board_ask]
{"task_id": "<kart>", "question": "<takıldığın nokta>"}
[/PANO]
  Bilgi eksikse TAHMİN ÜRETME; soruyu buradan sor, çalışmaya devam et."""

_ENTROPY_TOOL_TEXT = """[PANO board_create]
{"title": "<başlık>", "goal": "<hedef>", "criteria": ["<ölçüt>"],
 "agent": "<ajan>", "priority": "P1", "effort": "<low|medium|high>",
 "input_paths": ["<girdi>"]}
[/PANO]
  Bir işi devretmeye karar verdiğinde kart doğurur. Kartı SEN koşturmazsın:
  pano sıradaki turda ajanı uyandırır."""


def tools_section(for_entropy: bool = False) -> str:
    """İsteme eklenecek araç sözleşmesi metni."""
    if for_entropy:
        return _AGENT_TOOLS_TEXT + "\n\n" + _ENTROPY_TOOL_TEXT
    return _AGENT_TOOLS_TEXT


def tool_names(for_entropy: bool = False) -> Tuple[str, ...]:
    return ALL_TOOLS if for_entropy else AGENT_TOOLS


__all__ = [
    "AGENT_TOOLS", "ENTROPY_TOOLS", "ALL_TOOLS", "ToolCall", "ToolError",
    "parse_tool_calls", "validate_finish", "finish_outcome", "normalize_next",
    "tools_section", "tool_names", "CRITERIA_LIMIT", "INPUT_PATHS_LIMIT",
]
