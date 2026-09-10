"""
Entropy'nin sistem istemi kurucusu — TEK kaynak (Faz 9, iş 9.3).

Neyi çözüyor
------------
Claude sağlayıcısında Entropy'nin kimliği `--append-system-prompt` ile Claude
Code'un 12.438 karakterlik VARSAYILAN istemine EK olarak gidiyordu (araştırma A
§1.1). Sonuç: kimliğin payı %39, sırası SONUNCU; kullanıcı "yazılım mühendisliği
ajanı" kimliğiyle ve kullanıcının kişisel `# auto memory` talimatlarıyla
konuşuyordu. Faz 9'da `--system-prompt-file` ile varsayılan istem tamamen
DÜŞÜYOR; bu yüzden Claude Code'un yerleşik araç kuralları da düşüyor ve araç
kullanım sözleşmesinin bu istemde AÇIKÇA yazılması gerekiyor (araştırma A §4.1
"en riskli parça" uyarısı).

Sözleşme
--------
`build_system_prompt(kind, provider=..., ...)` sohbet ve kart yollarının ikisini
de besler. Köprü tarafı (agy-1) bu metni ya `--system-prompt-file` dosyasına
yazar ya da bayrak desteklenmiyorsa `claude_bridge.build_system_context_block`
ile stdin'deki ilk kullanıcı mesajının başına gömer — **her iki yolda da metin
aynıdır**, bu modül tek bir dizge döndürür.

Bölümler ve kırpma önceliği
---------------------------
    1. Kimlik            (asla kırpılmaz)
    2. Araç sözleşmesi   (yalnız Claude; varsayılan istem düştüğü için)
    4. Manifest          (Entropy ajanları + Desk orkestratörleri + kart spec'i)
    3. Bilişsel bağlam   (context_builder çıktısı; ilk kırpılan büyük blok)
    5. Sohbet özeti      (en son kırpılan)

Numaralar rapor sırasını, sıralama ise KIRPMA önceliğini gösterir: metinde
sıra 1-2-3-4-5, bütçe daralınca düşme sırası 5 → 3 → 4 → 2 → 1.

Kapsam dışı
-----------
Desk orkestratörleri için ayrı bir kurucu YOKTUR ve olmayacaktır: onlar
`agents/desk_registry.orchestrator_spec()` isteminden beslenir ve Entropy AI'ın
varlığını bilmezler (mimari kural 3, `tests/test_architecture_rules.py`).
"""

from __future__ import annotations

import importlib
import re

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Bölüm karakter bütçeleri. Toplamları `DEFAULT_MAX_CHARS`ın altında kalır;
# artan pay bilişsel bağlama (bölüm 3) devredilir çünkü tek esneyebilen odur.
DEFAULT_MAX_CHARS = 8000
BUDGET_IDENTITY = 1200
BUDGET_TOOL_CONTRACT = 2000
BUDGET_MANIFEST = 1400
BUDGET_HISTORY = 700
# Bilişsel bağlamın alt sınırı: bunun altına düşerse bölüm hiç eklenmez
# (yarım kalmış bir playbook alıntısı hiç olmamasından kötüdür).
MIN_CONTEXT_CHARS = 300

# Entropy'nin kendi onaylı kurallarının payı (Faz 10-A): kimlik bölümünün
# sonuna eklenir, bütçesi kimliğin bütçesinden AYRIDIR.
BUDGET_RULES = 600

# Pano araçlarının (Faz 12-C) payı: araç sözleşmesinin sonuna eklenir, kendi
# tavanı vardır. Entropy sohbette bu blokla ajanına kart açar; blok büyürse
# araç sözleşmesinin geri kalanını ezmesin diye ayrı kelepçelenir.
BUDGET_BOARD_TOOLS = 600

# Kırpma önceliği: sona doğru gidildikçe önce düşer. Kurallar bağlamdan sonra
# düşer: kullanıcının "kalıcı yap" dediği bir kural, geri çağrılan bir nottan
# daha bağlayıcıdır.
TRIM_ORDER = ("history", "context", "rules", "manifest", "tools", "identity")

VALID_KINDS = ("chat", "card")


# ---------------------------------------------------------------------------
# 1. Kimlik
# ---------------------------------------------------------------------------

# TEK KAYNAK. `claude_bridge.build_chat_system_prompt` ve
# `agy_bridge` içindeki `system_directive` metinleri bu sabitle değiştirilecek
# (iş 9.2/9.4, agy-1). Çekirdek cümleler bugünkü part14 metninden alınmıştır;
# eklenen kısımlar Entropy'nin kendi ajanlarını ve Desk'i geliştirme/komuta
# yetkisidir (mimari kural: Entropy tüm orkestratörleri bilir, ters yön yok).
IDENTITY_TEXT = (
    "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin.\n"
    "Kullanıcıya daima Türkçe, net, samimi ve profesyonel bir üslupla yanıt ver.\n"
    "Kendi hafıza sisteminden, Obsidian notlarından ve geçmiş kararlarından "
    "tamamen haberdarsın; bir şeyi hatırlıyorsan kaynağını söyle, "
    "hatırlamıyorsan uydurma.\n"
    "Kendi ajanlarını (Entropy Agents) ve Entropy Agent Desk ofislerini "
    "oluşturabilir, düzenleyebilir ve onlara iş verebilirsin; ofis "
    "orkestratörleri sana rapor eder, sen onlara komut verirsin.\n"
    "Ölç, iddia etme: bir sonucu bildirirken dosya yolu, satır ya da sayı ver."
)


def identity_section(orchestrators: Optional[List[Dict[str, str]]] = None) -> str:
    """Bölüm 1: kimlik + (varsa) orkestratör adları."""
    text = f"[KİMLİK]\n{IDENTITY_TEXT}"
    names = [
        str(o.get("office") or o.get("name") or "").strip()
        for o in (orchestrators or [])
    ]
    names = [n for n in names if n]
    if names:
        text += "\nKomuta ettiğin ofisler: " + ", ".join(sorted(set(names))) + "."
    return text


def promoted_rules_section(max_chars: int = BUDGET_RULES) -> str:
    """
    Bölüm 1'in devamı: kullanıcının "kalıcı yap" dediği kurallar.

    Kaynak ofis ajanlarınınkiyle AYNI depodur (`memory.promoted_rules`); Entropy
    kendi kayıtlarını `office="entropy"` altında tutar. Onaysız aday asla girmez.
    """
    try:
        from entropy.brain.promoted_rules import ENTROPY_OFFICE, rules_section

        return _trim(rules_section(ENTROPY_OFFICE, max_chars=max_chars), max_chars)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 2. Araç sözleşmesi (yalnız Claude)
# ---------------------------------------------------------------------------

# Claude Code'un varsayılan istemi düştüğünde kaybolan yerleşik kurallar burada
# yeniden yazılır. Sıra rastgele değil: en sık ihlal edilen kural (okumadan
# düzenleme) başta.
TOOL_CONTRACT_RULES: Tuple[str, ...] = (
    "Bir dosyayı Edit ya da Write ile değiştirmeden ÖNCE mutlaka Read ile oku; "
    "okumadan düzenleme yapma.",
    "Edit'te `old_string` dosyada BENZERSİZ olmalı; değilse çevresine bağlam "
    "satırı ekleyerek benzersizleştir.",
    "Var olan bir dosyayı tamamen yeniden yazmak yerine hedefli Edit kullan; "
    "Write yalnızca yeni dosya için.",
    "Dosya yollarını her zaman MUTLAK ver (ör. C:\\EntropiAI\\src\\...).",
    "Arama için Grep/Glob kullan; Bash'i yalnızca başka aracın yapamadığı iş "
    "için çalıştır. Kabuk Windows'tur: PowerShell ya da Git Bash sözdizimi "
    "kullan, kaçış dizisi içeren metni heredoc ile yazma.",
    "Yıkıcı işlem yok: dosya/dizin silme, `git reset --hard`, `git push --force`, "
    "kayıt defteri değişikliği ve toplu yeniden adlandırma kullanıcının açık "
    "isteği olmadan yapılmaz.",
    "Web araçlarını (WebSearch/WebFetch) kullandığında bulguyu KAYNAK bağlantısı "
    "ile birlikte ver; kaynaksız web iddiası yazma.",
    "Yanıtını Markdown ile biçimlendir: başlık, madde, kod bloğu. Uzun kod "
    "dökümü yerine dosya:satır referansı ver.",
    "Emin olmadığın bir şeyi doğrulanmış gibi anlatma; ölçebiliyorsan ölç, "
    "ölçemiyorsan 'doğrulanamadı' de.",
)


def tool_contract_section(commands: Optional[List[str]] = None) -> str:
    """
    Bölüm 2: araç kullanım sözleşmesi + Entropy'nin slash komutları.

    Slash komutları BURADA yazılır çünkü izole kipte `--disable-slash-commands`
    ile CLI'ın kendi komut kataloğu düşer; kullanıcının yazdığı `/distill`,
    `/desk` gibi komutlar CLI'ın değil ENTROPY'nin komutlarıdır.
    """
    lines = ["[ARAÇ SÖZLEŞMESİ]"]
    lines += [f"- {rule}" for rule in TOOL_CONTRACT_RULES]
    cmds = commands if commands is not None else entropy_command_names()
    if cmds:
        lines.append(
            "- Slash komutları Claude Code'un değil ENTROPY'nindir; "
            "kullanıcı bunlardan birini yazarsa uygulama kendisi yürütür, sen "
            "komutu taklit etme: " + " ".join(cmds)
        )
    return "\n".join(lines)


#: Entropy'nin SOHBET yolunda önceliği olan araç — bütçe taşarsa ilk bu kalır.
PRIMARY_BOARD_TOOL = "[PANO board_create]"

_PANO_BLOCK_RE = re.compile(r"^\[PANO ", re.MULTILINE)


def _split_board_blocks(text: str) -> Tuple[str, List[str]]:
    """Araç metnini (başlık, `[PANO ...]` blokları) olarak ayırır."""
    marks = [m.start() for m in _PANO_BLOCK_RE.finditer(text)]
    if not marks:
        return text, []
    header = text[: marks[0]].strip()
    blocks: List[str] = []
    for i, start in enumerate(marks):
        stop = marks[i + 1] if i + 1 < len(marks) else len(text)
        block = text[start:stop].strip()
        if block:
            blocks.append(block)
    return header, blocks


def _fit_board_tools(text: str, limit: int) -> str:
    """
    Araç metnini bütçeye blok bütünlüğünü bozmadan sığdırır.

    Ham metin (12-B sözleşmesi) 600 karakterden uzun: körlemesine baştan
    kırpmak `board_create` bloğunu — Entropy'nin sohbette gerçekten kullandığı
    tek aracı — düşürüyordu. Bu yüzden bloklar bütün olarak seçilir ve
    `board_create` en öne alınır; kalan bütçeye sığan diğer bloklar özgün
    sıralarıyla eklenir. Yarım bir JSON şablonu isteme asla girmez.
    """
    if limit <= 0 or not text:
        return ""
    if len(text) <= limit:
        return text
    header, blocks = _split_board_blocks(text)
    if not blocks:
        return _trim(text, limit)
    ordered = sorted(blocks, key=lambda b: 0 if b.startswith(PRIMARY_BOARD_TOOL) else 1)
    parts: List[str] = []
    used = 0
    if header and len(header) + 2 <= limit - min(len(b) for b in ordered[:1]):
        parts.append(header)
        used = len(header)
    chosen: List[str] = []
    for block in ordered:
        extra = len(block) + (2 if (parts or chosen) else 0)
        if used + extra > limit:
            continue
        chosen.append(block)
        used += extra
    if not chosen:  # başlık bile birinci bloğa yer bırakmıyorsa: blok öncelikli
        return _trim(ordered[0], limit)
    chosen.sort(key=blocks.index)
    return "\n\n".join(parts + chosen)


def board_tools_section(max_chars: int = BUDGET_BOARD_TOOLS) -> str:
    """
    Bölüm 2'nin eki: Entropy'nin pano araçları (`[PANO board_create]`).

    Metnin tek kaynağı 12-B'nin sunduğu semboldür; önce
    `core.response_hooks.entropy_tools_section`, o yoksa geriye dönük olarak
    `agents.board_tools.entropy_tools_section` denenir. Hiçbiri yoksa bölüm
    sessizce **atlanır**: hafıza katmanı pano sözleşmesinin kopyasını tutmaz,
    tuttuğu anda iki metin ayrışır.
    """
    fn = None
    for module_name in ("entropy.core.response_hooks", "entropy.agents.board_tools"):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        candidate = getattr(module, "entropy_tools_section", None)
        if callable(candidate):
            fn = candidate
            break
    if fn is None:
        return ""
    try:
        text = fn() or ""
    except Exception:  # pragma: no cover - araç metni istemi düşürmez
        return ""
    return _fit_board_tools(str(text).strip(), max(0, int(max_chars or 0)))


def entropy_command_names(limit: int = 24) -> List[str]:
    """
    Entropy'nin slash komut adları — tek kaynak `core.slash_commands`.

    Kopya liste tutulmaz: komut eklendiğinde istem kendiliğinden güncellenir.
    """
    try:
        from entropy.core.slash_commands import BUILTIN_AGY_COMMANDS, LOCAL_COMMANDS
    except Exception:
        return []
    names: List[str] = []
    for cmd in list(LOCAL_COMMANDS) + list(BUILTIN_AGY_COMMANDS):
        name = str(getattr(cmd, "name", "") or "").strip()
        if name and name not in names:
            names.append(name)
    return names[:limit]


# ---------------------------------------------------------------------------
# 3. Bilişsel bağlam
# ---------------------------------------------------------------------------


def cognitive_section(
    query: str,
    project_path: Optional[str] = None,
    skill_name: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Bölüm 3: `context_builder` çıktısı (playbook/wiki/handoff/ajan belleği).

    Token bütçesi orada (4000) uygulanır; buradaki iş yalnızca karakter
    bütçesine göre kırpmaktır. Hata yutulur: bağlam üretilemiyorsa istem
    bağlamsız ama GEÇERLİ kalmalıdır.
    """
    if not (query or "").strip():
        return ""
    try:
        from entropy.brain.context_builder import (
            DEFAULT_TOKEN_BUDGET,
            CognitiveContextBuilder,
        )

        project_dir = Path(project_path) if project_path else None
        ctx = CognitiveContextBuilder().build(
            query,
            skill_name=skill_name,
            token_budget=DEFAULT_TOKEN_BUDGET,
            project_dir=project_dir,
            meta=meta,
        )
        rendered = ctx.render().strip()
    except Exception:
        return ""
    if not rendered:
        return ""
    return f"[BİLİŞSEL BAĞLAM]\n{rendered}"


# ---------------------------------------------------------------------------
# 4. Manifest
# ---------------------------------------------------------------------------


def _desk_rows() -> List[Dict[str, str]]:
    try:
        from entropy.agents.desk_registry import _roster_rows

        return list(_roster_rows() or [])
    except Exception:
        return []


def manifest_section(agent_spec: Optional[Dict[str, Any]] = None) -> str:
    """
    Bölüm 4: Entropy'nin kendi ajanları + Desk orkestratörleri (+ kart spec'i).

    Manifest üreticileri KOPYALANMAZ; `agents.registry.agents_manifest` ve
    `agents.desk_registry.desk_manifest` doğrudan çağrılır — bunlar bugün de
    köprülerin kullandığı tek kaynaktır.
    """
    parts: List[str] = []
    try:
        from entropy.agents.registry import agents_manifest

        text = (agents_manifest() or "").strip()
        if text:
            parts.append(text)
    except Exception:
        pass
    try:
        from entropy.agents.desk_registry import desk_manifest

        text = (desk_manifest() or "").strip()
        if text:
            parts.append(text)
    except Exception:
        pass
    spec_text = agent_spec_section(agent_spec)
    if spec_text:
        parts.append(spec_text)
    return "\n\n".join(parts)


def agent_spec_section(agent_spec: Optional[Dict[str, Any]]) -> str:
    """
    Kart kipinde koşan ajanın künyesi: rol, izinler ve sistem istemi gövdesi.

    Arka plan kartları bugüne kadar HİÇ sistem istemi almıyordu (araştırma A
    §1.3: ölçülen Entropy payı 0 karakter); bu bölüm o boşluğu kapatır.
    """
    if not isinstance(agent_spec, dict) or not agent_spec:
        return ""
    name = str(agent_spec.get("name") or agent_spec.get("agent") or "").strip()
    role = str(agent_spec.get("role") or agent_spec.get("description") or "").strip()
    tools = agent_spec.get("tools") or agent_spec.get("tools_policy") or ""
    if isinstance(tools, (list, tuple)):
        tools = ", ".join(str(t) for t in tools)
    body = str(
        agent_spec.get("system_prompt")
        or agent_spec.get("prompt")
        or agent_spec.get("instructions")
        or ""
    ).strip()

    lines = ["[BU KOŞUNUN AJANI]"]
    if name:
        lines.append(f"Ad: {name}")
    if role:
        lines.append(f"Rol: {' '.join(role.split())}")
    if str(tools).strip():
        lines.append(f"İzinler/araçlar: {str(tools).strip()}")
    if body:
        lines.append("Görev tanımı:\n" + body)
    return "\n".join(lines) if len(lines) > 1 else ""


# ---------------------------------------------------------------------------
# 5. Sohbet özeti
# ---------------------------------------------------------------------------


def history_section(history_summary: str) -> str:
    text = (history_summary or "").strip()
    if not text:
        return ""
    return f"[ÖNCEKİ SOHBET ÖZETİ]\n{text}"


# ---------------------------------------------------------------------------
# Kırpma ve birleştirme
# ---------------------------------------------------------------------------


def _trim(text: str, limit: int) -> str:
    """Metni karakter tavanına indirir; mümkünse satır sınırından keser."""
    if limit <= 0 or not text:
        return ""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    nl = cut.rfind("\n")
    if nl > limit * 0.6:
        cut = cut[:nl]
    return cut.rstrip()


def _tools_block(is_claude: bool, kind: str) -> str:
    """
    Bölüm 2 = araç sözleşmesi (+ sohbette pano araçları).

    Pano bloğu YALNIZCA `kind="chat"`te eklenir: kart kipinde koşan ajanın
    kendi araç metni zaten ajan tarafında verilir, Entropy'nin kart açma
    yetkisi sohbete aittir.
    """
    if not is_claude:
        return ""
    text = _trim(tool_contract_section(), BUDGET_TOOL_CONTRACT)
    if kind != "chat":
        return text
    board = board_tools_section()
    return (text + "\n\n" + board) if board else text


def build_system_prompt(
    kind: str,
    *,
    provider: str,
    project_path: Optional[str] = None,
    agent_spec: Optional[Dict[str, Any]] = None,
    query: str = "",
    history_summary: str = "",
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """
    Entropy'nin tam sistem istemini kurar (sohbet ve kart için TEK yol).

    Parametreler
    ------------
    kind:
        `"chat"` (sohbet turu) ya da `"card"` (arka plan görev kartı).
    provider:
        `"claude"` ya da `"agy"`. Araç sözleşmesi (bölüm 2) YALNIZCA Claude'da
        eklenir: AGY kendi varsayılan istemini korur, oraya ikinci bir araç
        sözleşmesi yazmak hem yer harcar hem çelişki üretir.
    project_path:
        Bilişsel bağlamın proje bölümü için çalışılan dizin.
    agent_spec:
        Kart kipinde koşan ajanın künyesi (rol, izinler, istem gövdesi).
    query:
        Kullanıcının mesajı / kartın hedefi — geri çağırmanın sorgusudur.
    history_summary:
        Çağıranın hazırladığı önceki sohbet özeti (bu modül konuşma tutmaz).
    max_chars:
        Toplam üst sınır. Aşılırsa kırpma sırası: özet → bağlam → manifest →
        araç sözleşmesi → kimlik (kimlik pratikte hiç kırpılmaz).

    Deterministiktir: aynı girdi + aynı kasa durumu aynı metni verir; tarih,
    saat ya da rastgele değer içermez.
    """
    kind = (kind or "chat").strip().lower()
    if kind not in VALID_KINDS:
        kind = "chat"
    provider_name = (provider or "").strip().lower()
    is_claude = provider_name == "claude"
    limit = max(0, int(max_chars or 0)) or DEFAULT_MAX_CHARS

    desk_rows = _desk_rows()
    sections: Dict[str, str] = {
        "identity": _trim(identity_section(desk_rows), BUDGET_IDENTITY),
        "rules": promoted_rules_section(),
        "tools": _tools_block(is_claude, kind),
        "manifest": _trim(
            manifest_section(agent_spec if kind == "card" else None), BUDGET_MANIFEST
        ),
        "history": _trim(history_section(history_summary), BUDGET_HISTORY),
    }

    # Bilişsel bağlam artan payı alır: sabit bölümler yerleştikten sonra kalan
    # yer neyse odur. Bu yüzden bütçesi sabit değil, hesaplanır.
    fixed = sum(
        len(sections[k]) for k in ("identity", "rules", "tools", "manifest", "history")
    )
    separators = 5 * 2  # bölümler arası "\n\n"
    context_budget = limit - fixed - separators
    context = ""
    if context_budget >= MIN_CONTEXT_CHARS:
        context = _trim(
            cognitive_section(
                query,
                project_path=project_path,
                meta={"agent": (agent_spec or {}).get("name")} if agent_spec else None,
            ),
            context_budget,
        )
    sections["context"] = context

    # Metindeki sıra: kimlik → araç sözleşmesi → bağlam → manifest → özet.
    order = ("identity", "rules", "tools", "context", "manifest", "history")
    parts = [sections[k] for k in order if sections.get(k)]
    text = "\n\n".join(parts)

    # Son güvenlik ağı: bir bölüm beklenenden büyük döndüyse öncelik sırasıyla
    # düşür, en sonda sert kırp. Sözleşme "≤ max_chars" — istisnasız.
    for key in TRIM_ORDER:
        if len(text) <= limit:
            break
        if not sections.get(key):
            continue
        sections[key] = ""
        parts = [sections[k] for k in order if sections.get(k)]
        text = "\n\n".join(parts)
    if len(text) > limit:
        text = _trim(text, limit)
    return text


def section_lengths(
    kind: str,
    *,
    provider: str,
    project_path: Optional[str] = None,
    agent_spec: Optional[Dict[str, Any]] = None,
    query: str = "",
    history_summary: str = "",
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Dict[str, int]:
    """
    Ölçüm yardımcısı: bölüm başına karakter sayısı + toplam.

    Testler ve `/usage` benzeri teşhis yolları için; istem üretimini
    tekrarlamamak adına aynı çağrıyı kullanır.
    """
    text = build_system_prompt(
        kind,
        provider=provider,
        project_path=project_path,
        agent_spec=agent_spec,
        query=query,
        history_summary=history_summary,
        max_chars=max_chars,
    )
    headers = {
        "identity": "[KİMLİK]",
        "rules": "[ONAYLI KURALLAR]",
        "tools": "[ARAÇ SÖZLEŞMESİ]",
        "context": "[BİLİŞSEL BAĞLAM]",
        "manifest_agents": "[AJANLAR]",
        "manifest_offices": "[OFİSLER]",
        "agent_spec": "[BU KOŞUNUN AJANI]",
        "history": "[ÖNCEKİ SOHBET ÖZETİ]",
    }
    positions = sorted(
        (text.find(h), key) for key, h in headers.items() if text.find(h) >= 0
    )
    out: Dict[str, int] = {"total": len(text)}
    for i, (pos, key) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[key] = end - pos
    return out
