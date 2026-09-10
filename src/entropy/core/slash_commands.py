"""Dynamic Slash Commands Registry and Discovery Engine for Antigravity & Entropy AI."""

import logging
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

@dataclass
class SlashCommand:
    name: str                  # e.g. "/boost", "/goal", "/financial-auditor", "/obsidian:search"
    description: str           # User-friendly explanation
    category: str              # "builtin", "skill", "mcp", "mcp_tool", "tool"
    badge: str                 # "⚡ AGY", "🎯 YETENEK", "🔌 MCP", "🔌 MCP ARAÇ", "🛠️ ARAÇ"
    color: str                 # Cyber hex color
    usage: Optional[str] = None # e.g. "/boost <görev>"
    metadata: Optional[Dict[str, Any]] = None

BUILTIN_AGY_COMMANDS: List[SlashCommand] = [
    SlashCommand(
        name="/boost",
        description="Yüksek akıl yürütme ve derin düşünme modunu etkinleştirir (High reasoning effort).",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/boost <istek>",
    ),
    SlashCommand(
        name="/goal",
        description="Oturum için spesifik bir hedef belirler ve adımları hedefe odaklar.",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/goal <hedef>",
    ),
    SlashCommand(
        name="/grill-me",
        description="Fikrinizi, mimarinizi veya kodunuzu acımasızca sorgular; kör noktaları ortaya çıkarır.",
        category="builtin",
        badge="⚡ AGY",
        color="#FF0055",
        usage="/grill-me <fikir/mimari>",
    ),
    SlashCommand(
        name="/teamwork-preview",
        description="İşbirlikçi çoklu ajan (orchestrator + worker + tester) modunda önizleme yapar.",
        category="builtin",
        badge="⚡ AGY",
        color="#9D00FF",
        usage="/teamwork-preview <görev>",
    ),
    SlashCommand(
        name="/team-upgrade",
        description="Takım mimarisini ve ajan yeteneklerini en son yetkinliklerle yükseltir.",
        category="builtin",
        badge="⚡ AGY",
        color="#9D00FF",
        usage="/team-upgrade",
    ),
    SlashCommand(
        name="/learn",
        description="Mevcut oturumdaki çözüm ve mimarileri kalıcı bilişsel hafızaya kaydeder.",
        category="builtin",
        badge="⚡ AGY",
        color="#00FF9D",
        usage="/learn <konu/bilgi>",
    ),
    SlashCommand(
        name="/plan",
        description="Kod yazmadan önce adım adım uygulama ve mimari planı oluşturur (Plan mode).",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/plan <özellik>",
    ),
    SlashCommand(
        name="/browser",
        description="Tarayıcı otomasyonu ve web aracı ile canlı web araştırması yürütür.",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/browser <arama/url>",
    ),
    SlashCommand(
        name="/schedule",
        description="Arka plan görevleri ve zamanlanmış cron otomasyonları oluşturur.",
        category="builtin",
        badge="⚡ AGY",
        color="#FFB300",
        usage="/schedule <dakika/saat> <görev>",
    ),
    SlashCommand(
        name="/compact",
        description="Konuşma geçmişini ve bağlam penceresini özetleyerek optimize eder.",
        category="builtin",
        badge="⚡ AGY",
        color="#8B949E",
        usage="/compact",
    ),
    SlashCommand(
        name="/clear",
        description="Mevcut sohbet oturumunu ve terminal ekranını sıfırlar.",
        category="builtin",
        badge="⚡ AGY",
        color="#8B949E",
        usage="/clear",
    ),
    SlashCommand(
        name="/help",
        description="Kullanılabilir tüm slash komutlarını, yetenekleri ve MCP'leri listeler.",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/help",
    ),
    SlashCommand(
        name="/skills",
        description="Kullanılabilir tüm Antigravity ve yerel uzmanlık yeteneklerini listeler.",
        category="builtin",
        badge="⚡ AGY",
        color="#00FF9D",
        usage="/skills",
    ),
    SlashCommand(
        name="/model",
        description="Entropy'nin kendi modelini görüntüler veya değiştirir (kalıcı ayar).",
        category="builtin",
        badge="⚡ Yerel",
        color="#00F0FF",
        usage="/model <model_adı>",
    ),
    SlashCommand(
        name="/board",
        description="Pano özeti: durum sayıları, sahiplenmeler, son olaylar. `pick` ile kartı ajana verir.",
        category="builtin",
        badge="⚡ Yerel",
        color="#00FF9D",
        usage="/board [pick <kart> <ajan>] [auto on|off]",
    ),
    SlashCommand(
        name="/lock",
        description="Öz-amplifikasyon kilidini açar/kapatır (kalıcı ayar).",
        category="builtin",
        badge="⚡ Yerel",
        color="#9D00FF",
        usage="/lock [on|off]",
    ),
    SlashCommand(
        name="/memory",
        description="Hafıza bakımı: gri bant kuyruğunu birleştirir (merge) ya da rüya döngüsünü koşar (dream).",
        category="builtin",
        badge="⚡ Yerel",
        color="#9D00FF",
        usage="/memory merge|dream",
    ),
    SlashCommand(
        name="/effort",
        description="Akıl yürütme eforunu kalıcı olarak ayarlar (agy: low|medium|high, claude: + xhigh|max).",
        category="builtin",
        badge="⚡ Yerel",
        color="#00F0FF",
        usage="/effort [<seviye>]",
    ),
    SlashCommand(
        name="/usage",
        description="Oturum ve delta token kullanım metriklerini detaylandırır.",
        category="builtin",
        badge="⚡ AGY",
        color="#00FF9D",
        usage="/usage",
    ),
    SlashCommand(
        name="/permissions",
        description="Araç çalıştırma izinlerini ve güvenlik onaylarını yönetir.",
        category="builtin",
        badge="⚡ AGY",
        color="#FFB300",
        usage="/permissions",
    ),
]

# Uygulama içinde yürütülen, AGY'ye HİÇ gitmeyen komutlar. BUILTIN_AGY_COMMANDS'tan
# ayrı tutulur: o liste "her üyesi AGY'ye iletilen ⚡ AGY komutu" sözleşmesini
# taşır (test_slash_commands bunu doğrular). Kategori, komut paletinin stil
# eşlemesi için "builtin" bırakılmıştır; yürütme yolu try_handle_local_command'dır.
LOCAL_COMMANDS: List[SlashCommand] = [
    SlashCommand(
        name="/distill",
        description="Bir yeteneğin birikmiş raporlarından çalışma yordamı (playbook) damıtır. Argümansız: bekleyenleri listeler.",
        category="builtin",
        badge="📘 YORDAM",
        color="#00FF9D",
        usage="/distill [<yetenek_adı>|all|index|stop [<yetenek>]|refresh <yetenek>]",
    ),
    SlashCommand(
        name="/handoff",
        description="Bu oturum için devir sayfası yazar (hedef, kararlar, açık işler, sonraki adım) ve bağlamı sıkıştırır.",
        category="builtin",
        badge="🔁 AKTARIM",
        color="#00F0FF",
        usage="/handoff [not]",
    ),
    SlashCommand(
        name="/provider",
        description="Aktif CLI sağlayıcısını gösterir veya değiştirir (agy | claude).",
        category="builtin",
        badge="🔀 SAĞLAYICI",
        color="#9D00FF",
        usage="/provider [agy|claude]",
    ),
    SlashCommand(
        name="/agents",
        description="Kasadaki ajanları listeler (ad, rol, sağlayıcı, yetenekler).",
        category="builtin",
        badge="🤖 AJAN",
        color="#9D00FF",
        usage="/agents",
    ),
    SlashCommand(
        name="/agent",
        description="Bir ajanın ayrıntısını gösterir (model, araç politikası, gövde özeti).",
        category="builtin",
        badge="🤖 AJAN",
        color="#9D00FF",
        usage="/agent <ad>",
    ),
    SlashCommand(
        name="/task",
        description="Bir işi ajana devreder: kart oluşturur ve arka planda çalıştırır.",
        category="builtin",
        badge="📋 GÖREV",
        color="#FFB300",
        usage="/task <ajan> <başlık> :: <hedef>  |  /task stop <id>",
    ),
    SlashCommand(
        name="/tasks",
        description="Görev kartlarını durumlarıyla birlikte listeler.",
        category="builtin",
        badge="📋 GÖREV",
        color="#FFB300",
        usage="/tasks [backlog|running|review|done|failed]",
    ),
    SlashCommand(
        name="/offices",
        description="Ofisleri listeler (amaç, orkestratör, değerlendirici, üyeler).",
        category="builtin",
        badge="🏢 OFİS",
        color="#00F0FF",
        usage="/offices",
    ),
    SlashCommand(
        name="/desk",
        description="Agent Desk: ofisleri ve süren kartları gösterir; işi bir ofise devreder.",
        category="builtin",
        badge="🏢 OFİS",
        color="#00F0FF",
        usage="/desk  |  /desk task <ofis> <başlık> :: <hedef>  |  /desk stop <kart>",
    ),
    SlashCommand(
        name="/ask",
        description="Bir ofisin posta kutusuna soru/talimat bırakır; ofis planlarken okur.",
        category="builtin",
        badge="✉️ POSTA",
        color="#00F0FF",
        usage="/ask <ofis> <soru>",
    ),
    SlashCommand(
        name="/chat",
        description="Entropy AI ile bir ofis/ajan arasında agentic sohbetin bir turunu başlatır.",
        category="builtin",
        badge="💬 SOHBET",
        color="#9D00FF",
        usage="/chat <ofis|ajan> <mesaj>",
    ),
    SlashCommand(
        name="/login",
        description="Sağlayıcı giriş durumu (agy/Claude) ve giriş yönlendirmesi; model çağırmaz.",
        category="builtin",
        badge="🔑 KİMLİK",
        color="#FFA657",
        usage="/login [agy|claude]",
    ),
    SlashCommand(
        name="/wiki",
        description="Playbook'tan kavram ve varlık wiki sayfalarını üretir (model çağırmaz).",
        category="builtin",
        badge="📗 WİKİ",
        color="#00FF9D",
        usage="/wiki <yetenek>",
    ),
    SlashCommand(
        name="/lint",
        description="Wiki sağlık denetimi: öksüz/bayat sayfa, kırık bağ, çelişki adayı.",
        category="builtin",
        badge="🩺 DENETİM",
        color="#FFB300",
        usage="/lint [<yetenek>|all]",
    ),
]

# Kartın durumu için arayüzde ve komut çıktısında kullanılan simge/renk.
_STATUS_STYLE = {
    "backlog": ("⏳", "#8B949E"),
    "running": ("▶", "#00F0FF"),
    "review": ("🔍", "#FFB300"),
    "done": ("✔", "#00FF9D"),
    "failed": ("✖", "#e06c75"),
}


def _html_escape(text: str) -> str:
    import html as _html
    return _html.escape(str(text))


def _handle_provider(cmd: dict, bridge) -> str:
    """
    `/provider` sonucunu yürütür: show -> mevcut sağlayıcı/model; set -> arayüz
    yöneticisi üzerinden canlı köprü değişimi; error -> ayrıştırıcı mesajı.
    """
    action = cmd.get("action")
    if action == "error":
        return f"<span style='color:#e06c75;'>{cmd.get('message', 'Geçersiz /provider komutu.')}</span>"

    if action == "show":
        name = getattr(bridge, "provider_name", "agy")
        model = getattr(bridge, "selected_model", "") or "-"
        return (
            "<b>Sağlayıcı</b><br>"
            f"Aktif: <b>{name}</b><br>"
            f"Model: <code>{model}</code><br>"
            "<i>Değiştirmek için: /provider agy | /provider claude</i>"
        )

    name = cmd.get("provider", "")
    from entropy.ui.manager import EntropyUIManager
    mgr = getattr(EntropyUIManager, "instance", None)
    if mgr is None:
        return ("<span style='color:#e06c75;'>Arayüz yöneticisi hazır değil; "
                "sağlayıcı değiştirilemedi.</span>")
    try:
        ok = mgr.switch_provider(name)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Sağlayıcı değiştirilemedi: {e}</span>"
    if not ok:
        return f"<span style='color:#e06c75;'>Sağlayıcı '{name}' olarak değiştirilemedi.</span>"
    new_model = getattr(getattr(mgr, "bridge", None), "selected_model", "") or "-"
    return f"<b>Sağlayıcı</b> artık <b>{name}</b> (model: <code>{new_model}</code>)."


def _handle_effort(cmd: dict, bridge) -> str:
    """
    `/effort` sonucunu yürütür: show -> mevcut/geçerli seviyeler; set -> köprüye
    yazar ve ayara kalıcılaştırır. Model çağırmaz, tamamen yerel.
    """
    action = cmd.get("action")
    levels = []
    try:
        levels = list(bridge.effort_levels())
    except Exception:
        levels = []

    if action == "error":
        return f"<span style='color:#e06c75;'>{_html_escape(cmd.get('message', 'Geçersiz /effort komutu.'))}</span>"

    if action == "show":
        current = getattr(bridge, "selected_effort", "") or "-"
        return (
            "<b>Akıl Yürütme Eforu</b><br>"
            f"Aktif: <b>{_html_escape(current)}</b><br>"
            f"Geçerli seviyeler: <code>{_html_escape(', '.join(levels) or '-')}</code><br>"
            "<i>Değiştirmek için: /effort &lt;seviye&gt;</i>"
        )

    level = cmd.get("effort", "")
    try:
        bridge.set_effort(level)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Efor ayarlanamadı: {_html_escape(e)}</span>"
    provider = getattr(bridge, "provider_name", "")
    # agy'de efor ayrı bir bayrak değil, MODEL VARYANTIDIR: `/effort low` model
    # adını da değiştirir ve kullanıcı bunu görmeli (üst çubuktaki model kutusu
    # sessizce başka bir ada geçmiş gibi görünüyordu).
    model_note = ""
    if provider == "agy":
        model = getattr(bridge, "selected_model", "") or ""
        if model:
            model_note = f" Model: <code>{_html_escape(model)}</code>."
    return (
        f"<b>Akıl Yürütme Eforu</b> artık <b>{_html_escape(level)}</b>"
        f"{f' ({_html_escape(provider)})' if provider else ''}.{model_note}"
    )


def _handle_handoff(note: str, bridge) -> str:
    """
    `/handoff [not]`: devir sayfasını yazar, köprüye sıkıştırmayı önerir, özet basar.

    Sayfa yazımı model çağırmaz (bkz. memory/handoff.py); bu yüzden komut kota
    harcamaz ve bağlam dolduğunda güvenle çalıştırılabilir. Sıkıştırma köprüye
    aittir: `compress_history_with_handoff(page)` varsa çağrılır, yoksa sayfa
    yine de yazılmıştır — aktarımın değeri sıkıştırmaya bağlı değildir.
    """
    from entropy.memory.handoff import write_handoff

    history = list(getattr(bridge, "conversation_history", None) or [])
    if not history:
        return (
            "<b>🔁 Oturum Aktarımı</b><br/>Bu oturumda kaydedilmiş tur yok; "
            "devredilecek bir şey bulunamadı."
        )

    project_dir = getattr(bridge, "active_project_dir", None)
    meta = {
        "note": note or "",
        "project": Path(project_dir).name if project_dir else None,
        "turns": len(history),
    }
    usage = getattr(bridge, "cumulative_usage", None)
    if isinstance(usage, dict):
        meta.update({k: v for k, v in usage.items() if isinstance(v, int)})

    try:
        path = write_handoff(history, meta)
    except Exception as exc:
        return f"<b>🔁 Oturum Aktarımı</b><br/>Sayfa yazılamadı: {_html_escape(exc)}"

    compressed = False
    compress = getattr(bridge, "compress_history_with_handoff", None)
    if callable(compress):
        try:
            compressed = bool(compress(str(path)))
        except Exception as exc:
            logger.warning("Aktarım sonrası bağlam sıkıştırılamadı: %s", exc)

    from entropy.memory.handoff import SECTION_TITLES, load_latest_handoff

    page = load_latest_handoff() or {}
    sections = page.get("sections") or {}
    rows = []
    for key in ("hedef", "acik_isler", "sonraki_adim"):
        items = sections.get(key) or []
        if items:
            rows.append(
                f"<div style='margin-top:2px;'><b style='color:#00F0FF;'>{SECTION_TITLES[key]}:</b> "
                f"{_html_escape('; '.join(items[:2]))}</div>"
            )
    return (
        f"<b>🔁 Oturum Aktarımı Yazıldı</b> ({len(history)} tur)"
        + "".join(rows)
        + f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>Sayfa: <code>{_html_escape(path)}</code>"
        + ("<br/>Bağlam sıkıştırıldı; sohbet aktarım sayfasından sürüyor." if compressed
           else "<br/>Sayfa bir sonraki oturuma 'Önceki oturum' olarak enjekte edilecek.")
        + "</div>"
    )


def _handle_agents(bridge) -> str:
    """`/agents`: kasadaki ajanların listesi."""
    from entropy.agents.registry import AGENTS_SUBDIR, AgentRegistry

    registry = AgentRegistry()
    specs = registry.list()
    if not specs:
        return (
            "<b>🤖 Ajanlar</b><br/>Kasada tanımlı ajan yok.<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>Tanım yolu: "
            f"<code>{_html_escape(AGENTS_SUBDIR)}/&lt;ad&gt;/AGENT.md</code></span>"
        )
    rows = "".join(
        f"<tr><td style='padding:2px 10px 2px 0;color:#9D00FF;'>🤖 {_html_escape(s.name)}</td>"
        f"<td style='padding:2px 10px 2px 0;'>{_html_escape(s.role or '-')}</td>"
        f"<td style='padding:2px 10px 2px 0;color:#8B949E;'>{_html_escape(s.provider)}"
        f"{'/' + _html_escape(s.model) if s.model else ''}</td>"
        f"<td style='padding:2px 0;'>{_html_escape(', '.join(s.skills) or '-')}</td></tr>"
        for s in specs
    )
    return (
        f"<b>🤖 Ajanlar</b> ({len(specs)})"
        f"<table style='font-size:11px;margin-top:4px;'>{rows}</table>"
        "<div style='color:#8B949E;font-size:11px;margin-top:4px;'>"
        "Ayrıntı: <code>/agent &lt;ad&gt;</code> · Devret: "
        "<code>/task &lt;ajan&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code></div>"
    )


def _handle_agent_detail(name: str) -> str:
    """`/agent <ad>`: tek ajanın ayrıntısı."""
    from entropy.agents.registry import AgentRegistry

    if not name:
        return "<b>🤖 Ajan</b><br/>Kullanım: <code>/agent &lt;ad&gt;</code>"
    registry = AgentRegistry()
    spec = registry.get(name.split()[0])
    if spec is None:
        known = ", ".join(s.name for s in registry.list()) or "(yok)"
        return (f"<b>🤖 Ajan</b><br/>'{_html_escape(name)}' adında ajan yok.<br/>"
                f"Mevcut: {_html_escape(known)}")
    body = " ".join((spec.prompt or "").split())
    if len(body) > 400:
        body = body[:400] + "…"
    return (
        f"<b>🤖 {_html_escape(spec.name)}</b> — {_html_escape(spec.role or 'genel')}<br/>"
        f"{_html_escape(spec.description)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Sağlayıcı: {_html_escape(spec.provider)}"
        f"{' · Model: ' + _html_escape(spec.model) if spec.model else ''}"
        f"{' · Çaba: ' + _html_escape(spec.effort) if spec.effort else ''}"
        f" · Araçlar: {_html_escape(spec.tools_policy or '-')}"
        f" · Yetenekler: {_html_escape(', '.join(spec.skills) or '-')}</span>"
        f"<div style='margin-top:4px;'>{_html_escape(body)}</div>"
        f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>Kaynak: "
        f"<code>{_html_escape(str(spec.path))}</code></div>"
    )


def _handle_tasks(args: str) -> str:
    """`/tasks [durum]`: kartların listesi."""
    from entropy.agents.tasks import STATUSES, TaskBoard

    status = args.strip().lower() or None
    if status and status not in STATUSES:
        return (f"<b>📋 Görevler</b><br/>Bilinmeyen durum '{_html_escape(status)}'. "
                f"Geçerli: {', '.join(STATUSES)}")
    board = TaskBoard()
    cards = board.list(status=status)
    if not cards:
        return "<b>📋 Görevler</b><br/>Kart yok."
    rows = ""
    for c in cards:
        icon, color = _STATUS_STYLE.get(c.status, ("•", "#8B949E"))
        rows += (
            f"<tr><td style='padding:2px 10px 2px 0;color:{color};'>{icon} {_html_escape(c.status)}</td>"
            f"<td style='padding:2px 10px 2px 0;'>{_html_escape(c.title)}</td>"
            f"<td style='padding:2px 10px 2px 0;color:#9D00FF;'>{_html_escape(c.agent or '-')}</td>"
            f"<td style='padding:2px 0;color:#8B949E;'><code>{_html_escape(c.id)}</code></td></tr>"
        )
    return (
        f"<b>📋 Görev Kartları</b> ({len(cards)})"
        f"<table style='font-size:11px;margin-top:4px;'>{rows}</table>"
        "<div style='color:#8B949E;font-size:11px;margin-top:4px;'>"
        "Durdur: <code>/task stop &lt;id&gt;</code></div>"
    )


def _handle_task(args: str) -> str:
    """
    `/task <ajan> <başlık> :: <hedef>` — kartı YALNIZCA oluşturur.
    `/task stop <id>` — süren kartı keser.

    Faz 11-C'de davranış değişti: komut artık `board.run()` ÇAĞIRMAZ. Kart
    `assigned` olarak panoya düşer ve koşturmayı `BoardDispatcher` yapar.
    Neden: kart oluşturulduğu satırda başlatıldığı sürece `backlog` durumu hiç
    beklemiyordu, yani pano bir kuyruk değil bir kayıt defteriydi; sahiplenme,
    öncelik, eşzamanlılık tavanı ve kurtarma gibi kavramların hiçbiri
    çalışamıyordu.

    Ayırıcı `::` kasıtlı: başlık ve hedefin ikisi de boşluk içerir, tek boşlukla
    ayırmak "hangi kelimeden sonrası hedef" sorusunu tahmine bırakırdı.
    """
    from entropy.agents.registry import AgentRegistry
    from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id

    args = (args or "").strip()
    if not args:
        return ("<b>📋 Görev</b><br/>Kullanım: "
                "<code>/task &lt;ajan&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code> ya da "
                "<code>/task stop &lt;id&gt;</code>")

    board = TaskBoard()
    if args.lower().startswith("stop"):
        card_id = args.split(None, 1)[1].strip() if len(args.split(None, 1)) > 1 else ""
        if not card_id:
            return "<b>📋 Görev</b><br/>Kullanım: <code>/task stop &lt;id&gt;</code>"
        card = board.get(card_id)
        if card is None:
            return f"<b>📋 Görev</b><br/>'{_html_escape(card_id)}' kimlikli kart yok."
        if card.status not in ("running", "taken", "assigned"):
            return (f"<b>📋 Görev</b><br/>'{_html_escape(card_id)}' çalışmıyor "
                    f"(durum: {_html_escape(card.status)}).")
        if card.status != "running":
            # Henüz süreç doğmamış kart: iptal geçişi yeter, öldürülecek bir
            # şey yok.
            try:
                board.apply_event(card_id, "task.canceled", actor="user",
                                  payload={"summary": "Kullanıcı iptal etti."})
            except Exception as exc:
                return f"<b>📋 Görev</b><br/>İptal edilemedi: {_html_escape(exc)}"
            return (f"<b>📋 Görev İptal Edildi</b><br/>{_html_escape(card.title)} "
                    f"(süreç başlamamıştı).")
        killed = board.stop(card_id)
        return (f"<b>📋 Görev Durduruldu</b><br/>{_html_escape(card.title)} "
                f"({'süreç sonlandırıldı' if killed else 'kart kapatıldı'}).")

    head, sep, goal = args.partition("::")
    parts = head.split()
    if len(parts) < 2:
        return ("<b>📋 Görev</b><br/>Ajan ve başlık gerekli: "
                "<code>/task &lt;ajan&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code>")
    agent_name = parts[0]
    title = " ".join(parts[1:]).strip()
    goal = goal.strip() if sep else ""

    registry = AgentRegistry()
    spec = registry.get(agent_name)
    if spec is None:
        known = ", ".join(s.name for s in registry.list()) or "(yok)"
        return (f"<b>📋 Görev</b><br/>'{_html_escape(agent_name)}' adında ajan yok.<br/>"
                f"Mevcut: {_html_escape(known)}")

    card = TaskCard(
        id=new_task_id(title),
        title=title,
        status="backlog",
        agent=spec.name,
        provider=spec.provider,
        model=spec.model,
        skill=(spec.skills or [""])[0],
        goal=goal or title,
    )
    try:
        card = board.create(card)
    except Exception as exc:
        return f"<b>📋 Görev</b><br/>Kart yazılamadı: {_html_escape(exc)}"

    # Kart panoya "atanmış" olarak düşer; sahiplenme ve başlatma tetikleyicinin
    # işidir. Geçiş durum makinesinden geçtiği için olay günlüğüne de yazılır.
    try:
        card = board.apply_event(card.id, "task.assigned", actor="user",
                                 payload={"agent": spec.name}) or card
    except Exception as exc:
        return (f"<b>📋 Görev</b><br/>Kart oluşturuldu ama panoya alınamadı: "
                f"{_html_escape(exc)}")

    dispatched = False
    try:
        from entropy.agents.dispatcher import board_dispatcher

        dispatcher = board_dispatcher()
        if dispatcher is not None:
            dispatcher.start()
            dispatched = True
    except Exception:
        dispatched = False

    hint = ("Pano sıradaki turda ajanı uyandıracak"
            if dispatched else
            "Tetikleyici kapalı: kart panoda bekliyor")
    return (
        f"<b>📋 Görev Panoya Düştü</b><br/>"
        f"🤖 {_html_escape(spec.name)} → {_html_escape(card.title)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Hedef: {_html_escape(card.goal)}<br/>"
        f"Kart: <code>{_html_escape(str(card.path))}</code> "
        f"(durum: <b>{_html_escape(card.status)}</b>)<br/>"
        f"{hint}; bitince kart <b>review</b> olur. "
        f"Durdurmak için: <code>/task stop {_html_escape(card.id)}</code></span>"
    )


def _handle_offices(_args: str = "") -> str:
    """`/offices`: kasadaki ofislerin listesi."""
    from entropy.agents.offices import OFFICES_SUBDIR, OFFICE_FILENAME, OfficeRegistry

    registry = OfficeRegistry()
    specs = registry.list()
    if not specs:
        return (
            "<b>🏢 Ofisler</b><br/>Kasada tanımlı ofis yok.<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>Ofis dosyası: "
            f"<code>{OFFICES_SUBDIR}/&lt;ad&gt;/{OFFICE_FILENAME}</code></span>"
        )
    rows = []
    for spec in specs:
        members = ", ".join(spec.members) or "-"
        rows.append(
            f"🏢 <b>{_html_escape(spec.name)}</b> — {_html_escape(spec.purpose or '-')}<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>orkestratör: "
            f"{_html_escape(spec.orchestrator or '-')} · değerlendirici: "
            f"{_html_escape(spec.evaluator or '-')} · üyeler: {_html_escape(members)} · "
            f"paralel: {spec.max_parallel} · bütçe: {spec.budget_tokens} token</span>"
        )
    return (
        f"<b>🏢 Ofisler ({len(specs)})</b><br/>" + "<br/>".join(rows) +
        "<br/><span style='color:#8B949E;font-size:11px;'>Devret: "
        "<code>/desk task &lt;ofis&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code></span>"
    )


def _is_seed_leftover(offices, spec) -> bool:
    """`is_seed_leftover` için güvenli sarmalayıcı (hata listeyi düşürmesin)."""
    try:
        from entropy.agents.desk_registry import is_seed_leftover

        return bool(is_seed_leftover(spec, offices))
    except Exception:
        return False


def _desk_usage() -> str:
    """Tek yerde tutulan `/desk` kullanım metni (hata yollarının hepsi buraya döner)."""
    return (
        "<b>🏢 Agent Desk</b><br/>"
        "<code>/desk</code> · <code>/desk office add &lt;ad&gt; :: &lt;amaç&gt;</code> · "
        "<code>/desk office rm &lt;ad&gt;</code><br/>"
        "<code>/desk agent add|edit|rm &lt;ofis&gt; &lt;ad&gt; :: &lt;açıklama&gt;</code><br/>"
        "<code>/desk project add &lt;ofis&gt; &lt;ad&gt; :: &lt;hedef&gt;</code> · "
        "<code>… :: &lt;depo yolu&gt; [dal]</code><br/>"
        "<code>/desk templates</code> · "
        "<code>/desk create &lt;ofis&gt; --template &lt;ad&gt;</code><br/>"
        "<code>/desk review &lt;kart&gt;</code> · "
        "<code>/desk push &lt;kart&gt;</code><br/>"
        "<code>/desk task &lt;ofis&gt; [@proje] &lt;başlık&gt; :: &lt;hedef&gt;</code> · "
        "<code>/desk stop &lt;kart&gt;</code><br/>"
        "<code>/desk msg &lt;ofis&gt; :: &lt;talimat&gt;</code>"
    )


def _handle_desk_admin(verb: str, rest: str, offices) -> str:
    """
    `/desk office|agent|project ...` — Desk'in kendi kadrosunun yönetimi.

    Hepsi YEREL: dosya yazar, model çağırmaz, kota harcamaz. Ofis açıldığı anda
    orkestratörü de doğar (kural 2); ajan ekleme/silme ofisin çalışma dizinine
    yeniden derlenir, aksi hâlde sağlayıcı eski kadroyu görüyordu.
    """
    from entropy.agents.desk_registry import DeskOffice, DeskProject

    action, _, tail = rest.partition(" ")
    action = action.strip().lower()
    body, sep, detail = tail.partition("::")
    names = body.split()
    detail = detail.strip() if sep else ""

    if verb == "office":
        if action == "add":
            if not names:
                return _desk_usage()
            name = names[0]
            try:
                spec = offices.create(DeskOffice(name=name, purpose=detail, charter=detail))
            except FileExistsError:
                return f"<b>🏢 Ofis</b><br/>'{_html_escape(name)}' zaten var."
            except Exception as exc:
                return f"<b>🏢 Ofis</b><br/>Yazılamadı: {_html_escape(exc)}"
            return (
                f"<b>🏢 Ofis Açıldı</b><br/>{_html_escape(spec.name)}<br/>"
                f"<span style='color:#8B949E;font-size:11px;'>Orkestratör "
                f"<code>{_html_escape(spec.orchestrator)}</code> otomatik oluşturuldu "
                f"(kod yazmaz; araştırır, planlar, raporlar). Klasör: "
                f"<code>{_html_escape(str(offices.office_dir(spec.name)))}</code></span>"
            )
        if action in ("rm", "remove", "delete"):
            if not names:
                return _desk_usage()
            ok = offices.delete(names[0])
            return (f"<b>🏢 Ofis</b><br/>'{_html_escape(names[0])}' "
                    + ("silindi." if ok else "bulunamadı."))
        return _desk_usage()

    if verb == "project":
        if action != "add" or len(names) < 2:
            return _desk_usage()
        office_name, project_name = names[0], names[1]
        if offices.get(office_name) is None:
            return f"<b>🏢 Proje</b><br/>'{_html_escape(office_name)}' adında ofis yok."
        # Faz 10-C: proje artık bir DEPO ve bir DAL olabilir.
        # `:: <repo> [dal]` — ilk parça var olan bir klasörse depo sayılır,
        # değilse eski davranış (hedef metni) korunur. Geriye uyum bedava.
        repo_path, base_branch, goal = "", "", detail
        if detail:
            first, _, tail = detail.partition(" ")
            if Path(first.strip().strip('"')).is_dir():
                repo_path = first.strip().strip('"')
                base_branch = tail.strip()
                goal = ""
        try:
            project = offices.create_project(
                office_name,
                DeskProject(name=project_name, goal=goal, charter=goal,
                            repo_path=repo_path, base_branch=base_branch),
            )
        except Exception as exc:
            return f"<b>🏢 Proje</b><br/>Yazılamadı: {_html_escape(exc)}"
        repo_note = (
            f"Depo: <code>{_html_escape(project.repo_path)}</code> @ "
            f"<code>{_html_escape(project.base_branch or 'HEAD')}</code><br/>"
            if project.repo_path else ""
        )
        return (
            f"<b>🏢 Proje</b><br/>{_html_escape(office_name)} / "
            f"{_html_escape(project.name)} oluşturuldu.<br/>{repo_note}"
            f"<span style='color:#8B949E;font-size:11px;'>Karta bağlamak için: "
            f"<code>/desk task {_html_escape(office_name)} @{_html_escape(project.name)} "
            f"&lt;başlık&gt; :: &lt;hedef&gt;</code></span>"
        )

    # verb == "agent"
    if len(names) < 2:
        return _desk_usage()
    office_name, agent_name = names[0], names[1]
    if offices.get(office_name) is None:
        return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(office_name)}' adında ofis yok."
    agents = offices.agents(office_name)
    if action in ("rm", "remove", "delete"):
        office = offices.get(office_name)
        if agent_name == (office.orchestrator if office else ""):
            return ("<b>🤖 Ofis Ajanı</b><br/>Orkestratör silinemez: ofisin planlayıcısı "
                    "odur. Ofisi kapatmak için <code>/desk office rm</code>.")
        ok = agents.delete(agent_name)
        return (f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(agent_name)}' "
                + ("silindi." if ok else "bulunamadı."))
    if action not in ("add", "edit"):
        return _desk_usage()
    from dataclasses import replace as _replace

    existing = agents.get(agent_name)
    if action == "add" and existing is not None:
        return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(agent_name)}' bu ofiste zaten var."
    if action == "edit" and existing is None:
        return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(agent_name)}' bu ofiste yok."
    # `add` yolu `create_member` üzerinden geçer: ofis üyeliği tanım DOSYASIYLA
    # doğar, `members` ön bilgisine ad yazmakla değil (Faz 7 / QA bulgusu).
    if existing is None:
        try:
            spec = offices.create_member(
                office_name, agent_name, role="worker",
                description=detail or "", prompt=detail or "",
            )
        except Exception as exc:
            return f"<b>🤖 Ofis Ajanı</b><br/>Yazılamadı: {_html_escape(exc)}"
        if spec is None:
            return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(office_name)}' ofisi okunamadı."
    else:
        spec = existing
        if detail:
            spec = _replace(spec, description=detail, prompt=(spec.prompt or detail))
        try:
            agents.update(spec)
        except Exception as exc:
            return f"<b>🤖 Ofis Ajanı</b><br/>Yazılamadı: {_html_escape(exc)}"
    return (
        f"<b>🤖 Ofis Ajanı</b><br/>{_html_escape(office_name)} / "
        f"{_html_escape(agent_name)} kaydedildi ve derlendi.<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Tanım: "
        f"<code>{_html_escape(str(agents.agent_file(agent_name)))}</code></span>"
    )


def _handle_desk_phase10(verb: str, rest: str, offices, board) -> str:
    """
    `/desk templates|create|review|push` (Faz 10-C).

    Hepsi YEREL: şablon okuma, ofis yazma, `git diff` okuma. Tek istisna
    `push`: uzak depoya yazar ve YALNIZCA bu komuttan çağrılır — harness ve
    `prepare_review` push'a hiç dokunmaz.
    """
    from entropy.agents import templates as _tpl

    if verb in ("template", "templates"):
        rows = _tpl.list_templates(getattr(offices, "vault_path", None))
        if not rows:
            return "<b>🏢 Şablonlar</b><br/>Şablon bulunamadı."
        body = "<br/>".join(
            f"<code>{_html_escape(r['name'])}</code> — {_html_escape(r['title'])} · "
            f"{_html_escape(', '.join(r['agents']))}"
            for r in rows
        )
        return (f"<b>🏢 Ekip Şablonları</b><br/>{body}<br/>"
                f"<span style='color:#8B949E;font-size:11px;'>Kullanım: "
                f"<code>/desk create &lt;ofis&gt; --template &lt;ad&gt;</code></span>")

    if verb == "create":
        parts = rest.split()
        if not parts:
            return _desk_usage()
        office_name = parts[0]
        template = ""
        for i, tok in enumerate(parts[1:], start=1):
            if tok == "--template" and i + 1 < len(parts):
                template = parts[i + 1]
        if not template:
            return ("<b>🏢 Ofis</b><br/>Kullanım: "
                    "<code>/desk create &lt;ofis&gt; --template &lt;ad&gt;</code>")
        try:
            office = _tpl.create_office_from_template(
                template, office_name, desk=offices
            )
        except FileExistsError:
            return f"<b>🏢 Ofis</b><br/>'{_html_escape(office_name)}' zaten var."
        except Exception as exc:
            return f"<b>🏢 Ofis</b><br/>Açılamadı: {_html_escape(exc)}"
        roster = ", ".join(s.name for s in offices.agents(office_name).list())
        return (
            f"<b>🏢 Ofis Açıldı</b><br/>{_html_escape(office.name)} "
            f"({_html_escape(template)} şablonu)<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>Kadro: "
            f"{_html_escape(roster)} · sağlayıcı "
            f"<code>{_html_escape(office.default_provider)}</code></span>"
        )

    # review / push: kart kimliği ister
    if not rest.strip():
        return _desk_usage()
    card = board.get(rest.strip())
    if card is None:
        return f"<b>🏢 İnceleme</b><br/>'{_html_escape(rest.strip())}' kimlikli kart yok."
    from entropy.agents import pr_flow as _pr

    project = None
    if card.office and card.project:
        project = offices.get_project(card.office, card.project)
    base = (project.base_branch if project is not None else "") or ""

    if verb == "review":
        data = _pr.prepare_review(card, base_branch=base)
        gh = "kurulu" if _pr.gh_available() else "kurulu değil"
        return (
            f"<b>🏢 İnceleme</b><br/>{_html_escape(card.title)}<br/>"
            f"{_html_escape(str(data.get('summary') or ''))}<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>gh: {gh} · dalı göndermek "
            f"için <code>/desk push {_html_escape(card.id)}</code></span>"
        )

    # verb == "push" — açık kullanıcı eylemi
    result = _pr.push_branch(card, confirm=True)
    if not result.get("pushed"):
        why = result.get("skipped") or result.get("error") or "bilinmeyen neden"
        return f"<b>🏢 Dal Gönderilmedi</b><br/>{_html_escape(str(why))}"
    review = _pr.prepare_review(card, base_branch=base)
    pr = _pr.create_draft_pr(card, office=card.office, base_branch=base, review=review)
    if pr.get("skipped"):
        return (f"<b>🏢 Dal Gönderildi</b><br/>"
                f"<code>{_html_escape(str(result.get('branch')))}</code><br/>"
                f"<span style='color:#8B949E;font-size:11px;'>Taslak PR açılmadı "
                f"({_html_escape(str(pr.get('skipped')))}); yerel dal + diff özeti "
                f"geçerli.</span>")
    url = str(pr.get("url") or "")
    if url:
        try:
            from dataclasses import replace as _replace

            board.update(_replace(card, pr_url=url))
        except Exception:
            pass
    return (f"<b>🏢 Taslak PR</b><br/>"
            f"<code>{_html_escape(str(result.get('branch')))}</code><br/>"
            f"{_html_escape(url or 'PR açıldı')}")


def _handle_desk(args: str) -> str:
    """
    `/desk` — ofisler + süren ofis kartları.
    `/desk task <ofis> <başlık> :: <hedef>` — üst kart açar ve harness'ı başlatır.
    `/desk stop <kart>` — ofis zincirini keser (alt kartlarla birlikte).

    `/task` ile ayrımı bilinçli: `/task` tek ajana tek çağrı, `/desk task` bir
    ofise planlama-yürütme-değerlendirme zinciri demektir; ikisi aynı komutta
    toplansaydı kullanıcı hangi maliyeti başlattığını göremezdi.
    """
    from entropy.agents.harness import OfficeHarness
    from entropy.agents.offices import OfficeRegistry
    from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id

    args = (args or "").strip()
    offices = OfficeRegistry()
    board = TaskBoard()

    if not args:
        rows = []
        for spec in offices.list():
            active = [
                c for c in board.list(office=spec.name)
                if not c.parent and c.status in ("running", "review")
            ]
            harness = OfficeHarness(spec.name, board=board, offices=offices)
            parts = []
            for c in active:
                # Harcama tahminden değil, harness'ın ledger'dan topladığı
                # gerçek sayıdan okunur; kullanıcı kartın kaç token yaktığını
                # ancak burada görebiliyor.
                spent = int(harness._card_state(c.id).get("tokens", 0))
                budget = int(c.budget_tokens or spec.budget_tokens or 0)
                cost = f", {spent:,} tk" + (f"/{budget:,}" if budget else "")
                parts.append(
                    f"{_html_escape(c.title)} ({_html_escape(c.status)}"
                    + (f", not {c.grade}" if c.grade is not None else "")
                    + _html_escape(cost) + ")"
                )
            state = ", ".join(parts) or "boşta"
            # Pano verisi tek üreticiden (mailbox.office_status) okunur; `/desk`
            # ve Agent Desk aynı sayıları göstersin diye.
            try:
                from entropy.agents.mailbox import office_status

                info = office_status(spec.name, vault_path=offices.vault_path)
                unread = int(info.get("inbox_unread") or 0)
                last = (info.get("recent_terminal") or [])[-1:]
            except Exception:
                unread, last = 0, []
            extra = f" · ✉️ {unread} okunmamış" if unread else ""
            if last:
                extra += f" · son olay: {_html_escape(str(last[0].get('status')))}"
            # Ek-2: eski build tohumundan kalan ofisler işaretlenir (silinmez).
            # İşaretin TEK ölçütü `OFFICE.md`'deki `seed: true`; ad tabanlı sezgi
            # kullanıcının kendi açtığı ofisi yanlışlıkla tohum gösteriyordu.
            if _is_seed_leftover(offices, spec):
                extra += " · ⚠️ eski tohum"
            rows.append(
                f"🏢 <b>{_html_escape(spec.name)}</b> — {_html_escape(spec.purpose or '-')}<br/>"
                f"<span style='color:#8B949E;font-size:11px;'>{state}{extra}</span>"
            )
        if not rows:
            return ("<b>🏢 Agent Desk</b><br/>Tanımlı ofis yok. "
                    "Ofis dosyası yazıp <code>/offices</code> ile doğrulayabilirsin.")
        return (
            "<b>🏢 Agent Desk</b><br/>" + "<br/>".join(rows) +
            "<br/><span style='color:#8B949E;font-size:11px;'>"
            "<code>/desk task &lt;ofis&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code> · "
            "<code>/desk stop &lt;kart&gt;</code></span>"
        )

    verb, _, rest = args.partition(" ")
    verb = verb.strip().lower()
    rest = rest.strip()

    if verb in ("office", "agent", "project"):
        return _handle_desk_admin(verb, rest, offices)

    # Faz 10-C: şablondan ofis, inceleme özeti ve (yalnızca kullanıcı eylemiyle)
    # dal gönderme. Üçü de yerel: model çağırmaz, kota harcamaz.
    if verb in ("template", "templates", "create", "review", "push"):
        return _handle_desk_phase10(verb, rest, offices, board)

    if verb == "msg":
        # Faz 9 / B-9.3: Entropy → orkestratör talimat yolu. Model ÇAĞIRMAZ;
        # talimat ofisin kutusuna düşer ve bir sonraki planlamada prompt'un
        # [TALİMAT] bölümüne girer. `/ask` ile ayrımı bilinçli: soru yanıtlanır,
        # talimat plana dönüşür.
        from entropy.agents.mailbox import instruct_office, office_mailbox

        head, sep, instruction = rest.partition("::")
        office_name = head.strip()
        instruction = instruction.strip() if sep else ""
        if not office_name or not instruction:
            return ("<b>🏢 Ofise Talimat</b><br/>Kullanım: "
                    "<code>/desk msg &lt;ofis&gt; :: &lt;talimat&gt;</code>")
        if offices.get(office_name) is None:
            known = ", ".join(s.name for s in offices.list()) or "(yok)"
            return (f"<b>🏢 Ofise Talimat</b><br/>'{_html_escape(office_name)}' adında ofis yok.<br/>"
                    f"Mevcut: {_html_escape(known)}")
        try:
            msg = instruct_office(office_name, instruction)
        except Exception as exc:
            return f"<b>🏢 Ofise Talimat</b><br/>Yazılamadı: {_html_escape(exc)}"
        unread = office_mailbox(office_name).unread_count()
        return (
            f"<b>🏢 Talimat Bırakıldı</b><br/>{_html_escape(office_name)}: "
            f"{_html_escape(instruction)}<br/>"
            f"<span style='color:#8B949E;font-size:11px;'>Mesaj: "
            f"<code>{_html_escape(msg.id)}</code> · kutuda {unread} okunmamış · "
            f"orkestratör bir sonraki planlamada [TALİMAT] bölümünde görür.</span>"
        )

    if verb == "stop":
        if not rest:
            return "<b>🏢 Agent Desk</b><br/>Kullanım: <code>/desk stop &lt;kart&gt;</code>"
        card = board.get(rest)
        if card is None:
            return f"<b>🏢 Agent Desk</b><br/>'{_html_escape(rest)}' kimlikli kart yok."
        if not card.office:
            return (f"<b>🏢 Agent Desk</b><br/>'{_html_escape(rest)}' bir ofis kartı değil; "
                    f"<code>/task stop {_html_escape(rest)}</code> kullan.")
        harness = OfficeHarness(card.office, board=board, offices=offices)
        harness.stop(card.id)
        return (f"<b>🏢 Ofis Durduruldu</b><br/>{_html_escape(card.title)} "
                f"({_html_escape(card.office)}) zinciri kesildi.")

    if verb != "task":
        return _desk_usage()

    head, sep, goal = rest.partition("::")
    parts = head.split()
    # `@proje` işareti kartı bir ofis projesine bağlar; proje kartın bağlamıdır
    # ve orkestratörün plan prompt'una projenin tüzüğü girer.
    project = ""
    for token in list(parts):
        if token.startswith("@") and len(token) > 1:
            project = token[1:]
            parts.remove(token)
    if len(parts) < 2:
        return ("<b>🏢 Agent Desk</b><br/>Ofis ve başlık gerekli: "
                "<code>/desk task &lt;ofis&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code>")
    office_name = parts[0]
    title = " ".join(parts[1:]).strip()
    goal = goal.strip() if sep else ""

    spec = offices.get(office_name)
    if spec is None:
        known = ", ".join(s.name for s in offices.list()) or "(yok)"
        return (f"<b>🏢 Agent Desk</b><br/>'{_html_escape(office_name)}' adında ofis yok.<br/>"
                f"Mevcut: {_html_escape(known)}")

    card = TaskCard(
        id=new_task_id(title),
        title=title,
        status="backlog",
        agent=spec.orchestrator,
        provider=spec.default_provider,
        model=spec.default_model,
        goal=goal or title,
        office=spec.name,
        project=project,
    )
    try:
        card = board.create(card)
    except Exception as exc:
        return f"<b>🏢 Agent Desk</b><br/>Kart yazılamadı: {_html_escape(exc)}"

    harness = OfficeHarness(spec.name, board=board, offices=offices)
    if not harness.start(card.id):
        return (f"<b>🏢 Agent Desk</b><br/>Kart oluşturuldu ama zincir başlatılamadı: "
                f"<code>{_html_escape(card.id)}</code>")
    return (
        f"<b>🏢 Ofise Devredildi</b><br/>"
        f"🏢 {_html_escape(spec.name)} → {_html_escape(card.title)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Hedef: {_html_escape(card.goal)}<br/>"
        f"Orkestratör {_html_escape(spec.orchestrator or '-')} planı çıkarıyor; "
        f"alt kartlar {spec.max_parallel} paralel koşacak, "
        f"{_html_escape(spec.evaluator or spec.orchestrator or '-')} notlayacak.<br/>"
        f"Kart: <code>{_html_escape(card.id)}</code> · Durdur: "
        f"<code>/desk stop {_html_escape(card.id)}</code></span>"
    )


def _handle_ask(args: str) -> str:
    """
    `/ask <ofis> <soru>` — ofisin posta kutusuna `question` bırakır.

    Model ÇAĞIRMAZ ve kota harcamaz: mesaj yalnızca kutuya yazılır. Ofis o
    soruyu bir sonraki planlamada okur (harness `pending_instructions` ile plan
    prompt'una ekler); acil yanıt isteniyorsa `/chat <ofis> ...` kullanılır —
    ayrım bilinçli, biri asenkron yön verme, öteki senkron sohbet.
    """
    from entropy.agents.mailbox import ask_office, office_mailbox
    from entropy.agents.offices import OfficeRegistry

    args = (args or "").strip()
    if not args:
        return ("<b>✉️ Ofise Sor</b><br/>Kullanım: "
                "<code>/ask &lt;ofis&gt; &lt;soru&gt;</code>")
    office_name, _, question = args.partition(" ")
    question = question.strip()
    offices = OfficeRegistry()
    if offices.get(office_name) is None:
        known = ", ".join(s.name for s in offices.list()) or "(yok)"
        return (f"<b>✉️ Ofise Sor</b><br/>'{_html_escape(office_name)}' adında ofis yok.<br/>"
                f"Mevcut: {_html_escape(known)}")
    if not question:
        return ("<b>✉️ Ofise Sor</b><br/>Soru boş olamaz: "
                f"<code>/ask {_html_escape(office_name)} &lt;soru&gt;</code>")
    try:
        msg = ask_office(office_name, question)
    except Exception as exc:
        return f"<b>✉️ Ofise Sor</b><br/>Mesaj yazılamadı: {_html_escape(exc)}"
    unread = office_mailbox(office_name).unread_count()
    return (
        f"<b>✉️ 🏢 {_html_escape(office_name)} posta kutusuna bırakıldı</b><br/>"
        f"{_html_escape(question)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Mesaj: <code>{_html_escape(msg.id)}</code> · "
        f"kutuda {unread} okunmamış · ofis bir sonraki planlamada okur. "
        f"Hemen konuşmak için: <code>/chat {_html_escape(office_name)} &lt;mesaj&gt;</code></span>"
    )


def _handle_login(args: str) -> str:
    """
    `/login [agy|claude]` — YALNIZCA yönlendirme.

    Giriş akışını Entropy başlatmaz: iki CLI da tarayıcı tabanlı OAuth istiyor ve
    onu bir alt süreçten sürüklemek hem kırılgan hem de kullanıcının kimlik
    bilgisini görünmez bir yere taşımak olurdu. Burada durum probu koşar ve ne
    yapılacağı yazılır.
    """
    from entropy.core.identity import PROVIDERS, identity, login_guidance

    name = (args or "").strip().lower().split()[0] if (args or "").strip() else ""
    targets = [name] if name in PROVIDERS else list(PROVIDERS)
    if name and name not in PROVIDERS:
        return (f"<b>🔑 Giriş</b><br/>Bilinmeyen sağlayıcı '{_html_escape(name)}'. "
                f"Geçerli: {', '.join(PROVIDERS)}.")
    rows = []
    for provider in targets:
        status = identity.refresh(provider)
        if status.logged_in:
            detail = " · ".join(x for x in [
                f"hesap: {status.account_hint or 'bilinmiyor'}",
                f"plan: {status.plan}" if status.plan else "",
                f"kota: {status.quota_hint}",
                status.session_window,
            ] if x)
            rows.append(
                f"✅ <b>{_html_escape(provider)}</b> — giriş açık<br/>"
                f"<span style='color:#8B949E;font-size:11px;'>{_html_escape(detail)}</span>"
            )
        else:
            guide = _html_escape(login_guidance(provider)).replace("\n", "<br/>")
            err = f"<br/><span style='color:#FF7B72;font-size:11px;'>Son hata: {_html_escape(status.last_error)}</span>" if status.last_error else ""
            rows.append(
                f"⛔ <b>{_html_escape(provider)}</b> — giriş yok{err}<br/>"
                f"<span style='color:#8B949E;font-size:11px;'>{guide}</span>"
            )
    return "<b>🔑 Sağlayıcı Kimliği</b><br/>" + "<br/><br/>".join(rows)


def _handle_chat(args: str, bridge=None) -> str:
    """
    `/chat <ofis|ajan> <mesaj>` — agentic sohbetin BİR turunu başlatır.

    Tur arka planda koşar (köprü çağrısı saniyeler sürüyor) ve yanıt posta
    kutusuna `report` olarak düşer; sohbete "🏢 <ofis>" balonu olarak arayüz
    basar. Burada senkron beklenseydi Zen/Chat penceresi donardı.
    """
    import threading as _threading

    from entropy.agents.offices import OfficeRegistry
    from entropy.agents.registry import AgentRegistry
    from entropy.core.identity import AgenticChat

    args = (args or "").strip()
    if not args:
        return ("<b>💬 Agentic Sohbet</b><br/>Kullanım: "
                "<code>/chat &lt;ofis|ajan&gt; &lt;mesaj&gt;</code>")
    target, _, message = args.partition(" ")
    message = message.strip()
    kind = "office" if OfficeRegistry().get(target) is not None else (
        "agent" if AgentRegistry().get(target) is not None else ""
    )
    if not kind:
        return (f"<b>💬 Agentic Sohbet</b><br/>'{_html_escape(target)}' adında ofis ya da ajan yok. "
                "<code>/offices</code> · <code>/agents</code>")
    if not message:
        return (f"<b>💬 Agentic Sohbet</b><br/>Mesaj boş olamaz: "
                f"<code>/chat {_html_escape(target)} &lt;mesaj&gt;</code>")

    conversation_id = (
        getattr(bridge, "current_conversation_id", None)
        or getattr(bridge, "current_session_id", None)
        or "entropy-chat"
    )
    chat = AgenticChat(str(conversation_id), target, target_kind=kind)
    _threading.Thread(target=lambda: (chat.send(message), chat.close()), daemon=True).start()
    provider = chat._target_provider()
    return (
        f"<b>💬 Agentic Sohbet · 🏢 {_html_escape(target)}</b><br/>"
        f"{_html_escape(message)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Karşı taraf "
        f"{_html_escape(provider)} sağlayıcısında yanıtlıyor; konuşma kimliği "
        f"<code>{_html_escape(str(conversation_id))}</code>. Yanıt gelen kutusuna "
        f"düşünce sohbette 🏢 balonu olarak görünür.</span>"
    )


def _handle_wiki(args: str, bridge=None) -> str:
    """
    `/wiki <yetenek>`: playbook'tan kavram/varlık sayfalarını elle üretir.

    Model çağırmaz (bkz. memory/wiki.ingest_playbook_to_wiki), bu yüzden kota
    harcamaz; damıtma bittiğinde aynı işlev zaten otomatik çalışır.
    """
    from entropy.memory.wiki import ingest_playbook_to_wiki

    parts = (args or "").split()
    if parts and parts[0].lower() == "compile":
        return _handle_wiki_compile(parts[1:], bridge)

    name = (args or "").split()[0] if (args or "").strip() else ""
    if not name:
        return "<b>📗 Wiki</b><br/>Kullanım: <code>/wiki &lt;yetenek&gt;</code>"
    try:
        res = ingest_playbook_to_wiki(name)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Wiki üretilemedi: {_html_escape(str(e))}</span>"
    if not res.get("written"):
        reason = res.get("reason") or "üretilecek bölüm yok"
        return (f"<b>📗 Wiki</b><br/>'{_html_escape(name)}' için sayfa üretilmedi: "
                f"{_html_escape(str(reason))}.")
    concepts = res.get("concepts") or []
    entities = res.get("entities") or []
    return (
        f"<b>📗 Wiki Güncellendi — {_html_escape(name)}</b><br/>"
        f"{len(concepts)} kavram, {len(entities)} varlık sayfası "
        f"(toplam {res['written']}).<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Kavramlar: "
        f"{_html_escape(', '.join(concepts[:6])) or '-'}<br/>Varlıklar: "
        f"{_html_escape(', '.join(entities[:6])) or '-'}<br/>"
        f"İndeks: <code>{_html_escape(str(res.get('index') or '-'))}</code></span>"
    )


def _handle_wiki_compile(parts: List[str], bridge=None) -> str:
    """
    `/wiki compile <yetenek> [--turns N]`: wiki sayfalarını çok turlu derler.

    Derleyici hafıza ajanının modülüdür
    (`memory.wiki.compile_skill(skill, bridge=send_prompt, budget_turns=N)`).
    `--turns` KULLANICININ verdiği kota tavanıdır (`budget_turns`): derleme
    model çağırır, bu yüzden varsayılan 1'dir. Kullanıcıya yazılan tur sayısı
    tavan değil, modülün **gerçekten harcadığı** tur sayısıdır.
    """
    args = [p for p in parts if p]
    turns = 1
    name = ""
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--turns", "-n") and i + 1 < len(args):
            try:
                turns = max(1, int(args[i + 1]))
            except ValueError:
                pass
            i += 2
            continue
        if token.startswith("--turns="):
            try:
                turns = max(1, int(token.split("=", 1)[1]))
            except ValueError:
                pass
            i += 1
            continue
        if not name:
            name = token
        i += 1
    if not name:
        return ("<b>📗 Wiki Derleme</b><br/>Kullanım: "
                "<code>/wiki compile &lt;yetenek&gt; [--turns N]</code>")
    try:
        from entropy.memory.wiki import compile_skill
    except ImportError as e:
        return ("<b>📗 Wiki Derleme</b><br/>Derleyici içe aktarılamadı: "
                f"<code>{_html_escape(e)}</code>")
    send_prompt, bridge_note = _memory_send_prompt(bridge, f"Wiki derleme: {name}")
    try:
        res = compile_skill(name, bridge=send_prompt, budget_turns=turns)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Derleme başarısız: {_html_escape(e)}</span>"
    detail = res if isinstance(res, dict) else _result_fields(res)
    spent = detail.get("turns", 0) if isinstance(detail, dict) else 0
    rows = "".join(
        f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>{_html_escape(k)}</td>"
        f"<td>{_html_escape(v)}</td></tr>" for k, v in detail.items()
    )
    return (f"<b>📗 Wiki Derlendi — {_html_escape(name)}</b> "
            f"({_html_escape(spent)} tur harcandı, tavan {turns}){bridge_note}"
            f"<table style='font-size:11px;margin-top:4px;'>{rows}</table>")


def _handle_model(args: str, bridge) -> str:
    """
    `/model [<ad>]`: **Entropy'nin kendi** model ayarını gösterir/değiştirir.

    Eskiden bu komut yerel değildi ve olduğu gibi CLI'a gidiyordu: kullanıcı
    `/model claude-opus-5` yazdığında Entropy'nin üst çubuğu değişmiyor, yalnız
    o turluk alt süreç etkileniyordu. Artık köprüye yazılır ve ayara
    kalıcılaşır (`bridge.set_model`), yani /effort ile aynı sözleşme.
    """
    name = (args or "").strip()
    provider = getattr(bridge, "provider_name", "") or "-"
    if not name:
        models = []
        try:
            models = list(bridge.fetch_available_models())
        except Exception:
            models = []
        return (
            "<b>Model</b><br/>"
            f"Sağlayıcı: <b>{_html_escape(provider)}</b><br/>"
            f"Aktif: <code>{_html_escape(getattr(bridge, 'selected_model', '') or '-')}</code><br/>"
            + (f"Geçerli: <code>{_html_escape(', '.join(models[:12]))}</code><br/>" if models else "")
            + "<i>Değiştirmek için: /model &lt;ad&gt;</i>"
        )
    name = name.split()[0]
    try:
        from entropy.core.config import is_valid_model_for

        if not is_valid_model_for(provider, name):
            return (f"<span style='color:#e06c75;'>'{_html_escape(name)}' "
                    f"{_html_escape(provider)} sağlayıcısının modeli değil.</span>")
    except Exception:
        pass
    try:
        bridge.set_model(name)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Model ayarlanamadı: {_html_escape(e)}</span>"
    try:
        from entropy.core.event_bus import bus

        bus.provider_status_updated.emit(provider, {"model": getattr(
            bridge, "selected_model", name)})
    except Exception:
        pass
    return (f"<b>Model</b> artık <code>"
            f"{_html_escape(getattr(bridge, 'selected_model', name) or name)}</code> "
            f"({_html_escape(provider)}).")


def _handle_agent_setting(args: str) -> str:
    """
    `/agent effort <ad> <seviye>` ve `/agent model <ad> <model>`.

    Kaynak tek: kasadaki `AGENT.md`. Yazıldıktan sonra ajan iki sağlayıcı
    biçimine YENİDEN DERLENİR ve **oturumu tazelenir**: oturum imzası
    `sha1(istem|model|efor)` olduğu için model/efor değişimi eski oturumu
    geçersiz kılar; tazelenmezse ajan bir sonraki turda hâlâ eski modelle
    konuşurdu.
    """
    from entropy.agents.registry import AgentRegistry

    parts = (args or "").split()
    verb = parts[0].lower() if parts else ""
    if len(parts) < 3:
        return ("<b>🤖 Ajan Ayarı</b><br/>Kullanım: "
                "<code>/agent effort &lt;ad&gt; &lt;seviye&gt;</code> · "
                "<code>/agent model &lt;ad&gt; &lt;model&gt;</code>")
    name, value = parts[1], parts[2]
    registry = AgentRegistry()
    spec = registry.get(name)
    if spec is None:
        known = ", ".join(s.name for s in registry.list()) or "(yok)"
        return (f"<b>🤖 Ajan Ayarı</b><br/>'{_html_escape(name)}' adında ajan yok.<br/>"
                f"Mevcut: {_html_escape(known)}")

    if verb == "effort":
        from entropy.core.provider import effort_levels_for

        level = value.lower()
        levels = []
        try:
            levels = list(effort_levels_for(spec.provider, spec.model))
        except Exception:
            levels = []
        if levels and level not in levels:
            return (f"<span style='color:#e06c75;'>Bilinmeyen efor "
                    f"'{_html_escape(level)}'. Geçerli: "
                    f"{_html_escape(', '.join(levels))}.</span>")
        updated = replace(spec, effort=level)
        field_note = f"Çaba: <b>{_html_escape(level)}</b>"
    else:
        from entropy.agents.compile import normalize_model_text

        model, effort_hint = normalize_model_text(value, spec.provider)
        updated = replace(spec, model=model or value,
                          effort=effort_hint or spec.effort)
        field_note = f"Model: <code>{_html_escape(updated.model)}</code>"

    try:
        registry.update(updated)
        from entropy.agents.compile import compile_agent

        compiled = compile_agent(updated)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Ajan güncellenemedi: {_html_escape(e)}</span>"
    refreshed = _refresh_agent_session(updated.name)
    return (
        f"<b>🤖 {_html_escape(updated.name)}</b> güncellendi — {field_note}"
        f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>"
        f"Derlendi: <code>{_html_escape(str((compiled or {}).get('agy', '-')))}</code>"
        + ("<br/>Oturum tazelendi (imza değişti): ajan bir sonraki turda yeni "
           "modelle/eforla başlar." if refreshed else "")
        + "</div>"
    )


def _refresh_agent_session(name: str) -> bool:
    """Ajanın kalıcı oturumunu düşürür; imza değiştiği için yeniden kurulur."""
    try:
        from entropy.core.identity import AgentSessionStore

        # `forget(agent)` sağlayıcı verilmediğinde ajanın TÜM oturumlarını
        # düşürür: model değişimi sağlayıcıyı da değiştirmiş olabilir.
        return bool(AgentSessionStore().forget(name))
    except Exception:
        logger.debug("Ajan oturumu tazelenemedi: %s", name, exc_info=True)
    return False


_BOOL_WORDS = {"on": True, "aç": True, "ac": True, "true": True, "1": True,
               "off": False, "kapat": False, "false": False, "0": False}


def _toggle_setting(key: str, value: str, title: str, usage: str,
                    on_change=None) -> str:
    """
    Boole bir ayarı gösterir ya da kalıcı olarak değiştirir (model çağırmaz).

    Değer verilmezse yalnızca mevcut durum yazılır. `on_change(yeni_değer)`
    ayarın çalışan sistemdeki karşılığını uygular (ör. tetikleyiciyi
    başlat/durdur); hatası komutu düşürmez, satır olarak raporlanır.
    """
    from entropy.core.config import config as cfg

    word = (value or "").strip().lower()
    if not word:
        state = "AÇIK" if bool(getattr(cfg, key, False)) else "KAPALI"
        return (f"<b>{title}</b><br/>Durum: <b>{state}</b>"
                f"<div style='color:#8B949E;font-size:11px;'>Kullanım: "
                f"<code>{_html_escape(usage)}</code></div>")
    if word not in _BOOL_WORDS:
        return (f"<b>{title}</b><br/>Anlaşılmayan değer: "
                f"<code>{_html_escape(word)}</code>. Kullanım: "
                f"<code>{_html_escape(usage)}</code>")
    new_value = _BOOL_WORDS[word]
    setattr(cfg, key, new_value)
    try:
        cfg.save_settings()
    except Exception as e:
        return (f"<span style='color:#e06c75;'>Ayar kaydedilemedi: "
                f"{_html_escape(e)}</span>")
    extra = ""
    if on_change is not None:
        try:
            extra = on_change(new_value) or ""
        except Exception as e:
            extra = f" (uygulanamadı: {_html_escape(e)})"
    state = "AÇIK" if new_value else "KAPALI"
    return f"<b>{title}</b><br/>Durum: <b>{state}</b>{extra}"


def _apply_board_auto(enabled: bool) -> str:
    """Ayarı çalışan tetikleyiciye uygular: açıksa başlat, kapalıysa durdur."""
    from entropy.agents.dispatcher import board_dispatcher

    dispatcher = board_dispatcher()
    if enabled:
        dispatcher.start()
        return " · tetikleyici başlatıldı"
    dispatcher.stop()
    return " · tetikleyici durduruldu"


def _handle_lock(args: str) -> str:
    """`/lock [on|off]` — öz-amplifikasyon kilidi (Faz 11.6) anahtarı."""
    return _toggle_setting(
        "amplification_lock", (args or "").strip(),
        title="🔒 Öz-amplifikasyon kilidi",
        usage="/lock on|off",
    )


# -- arayüz (komut paleti) için boole anahtarlar ---------------------------
# Faz 11 kapanışı: `amplification_lock` ve `board_auto_dispatch` ayarlarının
# arayüzde karşılığı yoktu (yalnızca slash komutu). Palet bu iki işlevi
# çağırır; ikisi de ayarı kalıcılaştırır ve model ÇAĞIRMAZ.

def toggle_amplification_lock(value: Optional[bool] = None) -> Tuple[bool, str]:
    """Öz-amplifikasyon kilidini çevirir (değer verilmezse tersine çevirir)."""
    from entropy.core.config import config as cfg

    new_value = (not bool(getattr(cfg, "amplification_lock", True))
                 if value is None else bool(value))
    _toggle_setting("amplification_lock", "on" if new_value else "off",
                    title="Öz-amplifikasyon kilidi", usage="/lock on|off")
    state = bool(getattr(cfg, "amplification_lock", True))
    return state, f"Öz-amplifikasyon kilidi {'AÇIK' if state else 'KAPALI'}"


def toggle_board_auto_dispatch(value: Optional[bool] = None) -> Tuple[bool, str]:
    """Pano otomatik dağıtımını çevirir ve çalışan tetikleyiciye uygular."""
    from entropy.core.config import config as cfg

    new_value = (not bool(getattr(cfg, "board_auto_dispatch", True))
                 if value is None else bool(value))
    _toggle_setting("board_auto_dispatch", "on" if new_value else "off",
                    title="Pano otomatik dağıtım", usage="/board auto on|off",
                    on_change=_apply_board_auto)
    state = bool(getattr(cfg, "board_auto_dispatch", True))
    return state, f"Pano otomatik dağıtım {'AÇIK' if state else 'KAPALI'}"


def _handle_board(args: str) -> str:
    """
    `/board` (özet) ve `/board pick <kart> <ajan>` (elle sahiplenme).

    Model çağırmaz: özet kart dosyalarından ve olay günlüğünden okunur.
    `pick` kartı ajana atar, kilidini alır ve tetikleyiciyi UYANDIRIR — kartın
    koşmasını 3 sn'lik turu beklemeden başlatmanın tek yolu budur.
    """
    from entropy.agents.board_events import board_event_log
    from entropy.agents.dispatcher import ClaimStore, board_dispatcher
    from entropy.agents.tasks import STATUSES, TaskBoard

    parts = (args or "").split()
    board = TaskBoard()

    if parts and parts[0].lower() == "auto":
        return _toggle_setting(
            "board_auto_dispatch", parts[1] if len(parts) > 1 else "",
            title="📋 Pano — Otomatik tetikleyici",
            usage="/board auto on|off",
            on_change=_apply_board_auto,
        )

    if parts and parts[0].lower() == "pick":
        if len(parts) < 3:
            return ("<b>📋 Pano</b><br/>Kullanım: "
                    "<code>/board pick &lt;kart&gt; &lt;ajan&gt;</code>")
        card_id, agent = parts[1], parts[2]
        card = board.get(card_id)
        if card is None:
            return f"<b>📋 Pano</b><br/>'{_html_escape(card_id)}' adlı kart yok."
        try:
            if (card.agent or "") != agent or card.status == "backlog":
                board.apply_event(card.id, "task.assigned", actor="user",
                                  payload={"agent": agent})
        except Exception as e:
            return (f"<span style='color:#e06c75;'>Kart atanamadı: "
                    f"{_html_escape(e)}</span>")
        core = board_dispatcher().core
        picked = core.pick(agent)
        if picked is None:
            lease = ClaimStore(board.vault_path).read(card.id)
            owner = (lease or {}).get("agent") or "-"
            return (f"<b>📋 Pano</b><br/>'{_html_escape(card_id)}' sahiplenilemedi "
                    f"(durum: {_html_escape(card.status)}, kilit sahibi: "
                    f"{_html_escape(owner)}).")
        return (
            f"<b>📋 Pano — Sahiplenildi</b><br/>"
            f"<code>{_html_escape(picked.id)}</code> → <b>{_html_escape(agent)}</b> "
            f"(durum: {_html_escape(picked.status)}). Tetikleyici sıradaki turda "
            f"başlatacak."
        )

    cards = board.list()
    counts = {s: 0 for s in STATUSES}
    for card in cards:
        counts[card.status] = counts.get(card.status, 0) + 1
    status_row = " · ".join(f"{s}: <b>{counts.get(s, 0)}</b>"
                            for s in STATUSES if counts.get(s))
    claims = ClaimStore(board.vault_path).list()
    claim_rows = "".join(
        f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>"
        f"{_html_escape(c.get('card_id', '-'))}</td>"
        f"<td style='padding:2px 10px 2px 0;'>{_html_escape(c.get('agent', '-'))}</td>"
        f"<td style='padding:2px 0;color:#8B949E;'>bitiş {_html_escape(c.get('expiry', '-'))}</td></tr>"
        for c in claims[:8]
    )
    try:
        log = board_event_log(board.vault_path)
        events = log.read()[-6:]
        taskboard = log.taskboard_path
    except Exception:
        events, taskboard = [], None
    event_rows = "".join(
        f"<div style='color:#8B949E;font-size:11px;'>#{e.get('seq', '?')} "
        f"{_html_escape(e.get('ts', ''))} · {_html_escape(e.get('action', ''))} · "
        f"{_html_escape(e.get('task_id', ''))} ({_html_escape(e.get('actor', ''))})</div>"
        for e in reversed(events)
    )
    return (
        f"<b>📋 Pano</b> ({len(cards)} kart)<br/>{status_row or 'kart yok'}"
        + (f"<div style='margin-top:4px;'><b>Sahiplenmeler</b>"
           f"<table style='font-size:11px;'>{claim_rows}</table></div>" if claim_rows else "")
        + (f"<div style='margin-top:4px;'><b>Son olaylar</b>{event_rows}</div>"
           if event_rows else "")
        + f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>Pano dosyası: "
          f"<code>{_html_escape(str(taskboard or '-'))}</code> · Sahiplen: "
          f"<code>/board pick &lt;kart&gt; &lt;ajan&gt;</code></div>"
    )


def _result_fields(res) -> dict:
    """Dataclass/nesne sonucunu görüntülenebilir alan sözlüğüne indirger."""
    import dataclasses

    if dataclasses.is_dataclass(res) and not isinstance(res, type):
        return {f.name: getattr(res, f.name) for f in dataclasses.fields(res)}
    return {"sonuç": res}


def _memory_send_prompt(bridge, label: str):
    """
    Hafıza turları için `(send_prompt, not)` üretir.

    Köprü yoksa ya da arka plan yüzeyi sunmuyorsa `None` döner: modüller o
    durumda **kuru koşuma** iner (model çağrılmaz). Hata YUTULMAZ; kullanıcıya
    gerçek neden bir not olarak gösterilir.
    """
    from entropy.core.bridge_prompt import BridgeUnavailable, make_send_prompt

    if bridge is None:
        return None, ("<div style='color:#8B949E;font-size:11px;'>Köprü yok → "
                      "kuru koşum (model çağrılmadı).</div>")
    try:
        return make_send_prompt(bridge, label=label), ""
    except BridgeUnavailable as e:
        return None, (f"<div style='color:#e5c07b;font-size:11px;'>Kuru koşum: "
                      f"{_html_escape(e)}</div>")


def _handle_memory(args: str, bridge) -> str:
    """
    `/memory merge` (gri bant toplu turu) ve `/memory dream` (rüya döngüsü).

    İkisi de HAFIZA AJANININ modüllerine bağlıdır (11-D); modül henüz yoksa
    komut kullanıcıya bunu söyler ve hata vermez — ajan katmanı hafıza
    katmanına sert bağımlı olamaz.
    """
    verb = ((args or "").split() or [""])[0].lower()
    if verb not in ("merge", "dream"):
        return ("<b>🧠 Hafıza</b><br/>Kullanım: <code>/memory merge</code> "
                "(gri bant kuyruğunu toplu işler) · <code>/memory dream</code> "
                "(rüya/konsolidasyon döngüsü)")

    if verb == "merge":
        try:
            from entropy.memory.gray_merge import run_merge_round
        except ImportError as e:
            return ("<b>🧠 Hafıza — Gri Bant</b><br/>Toplu birleştirme modülü "
                    f"içe aktarılamadı: <code>{_html_escape(e)}</code>")
        send_prompt, bridge_note = _memory_send_prompt(bridge, "Gri bant birleştirme")
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

        try:
            res = run_merge_round(CognitiveMemorySystem(), send_prompt=send_prompt, limit=8)
        except Exception as e:
            return f"<span style='color:#e06c75;'>Birleştirme başarısız: {_html_escape(e)}</span>"
        detail = res if isinstance(res, dict) else _result_fields(res)
        rows = "".join(
            f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>{_html_escape(k)}</td>"
            f"<td>{_html_escape(v)}</td></tr>" for k, v in detail.items()
        )
        return (f"<b>🧠 Gri Bant Birleştirildi</b>{bridge_note}"
                f"<table style='font-size:11px;'>{rows}</table>")

    from entropy.memory.dream import dream_and_consolidate
    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

    send_prompt, bridge_note = _memory_send_prompt(bridge, "Rüya döngüsü")
    try:
        # Faz 11-D sözleşmesi: `/memory dream` → `memory.dream`. Köprü varsa
        # gri bant adımı gerçek tur koşar; yoksa kuru koşuma düşer.
        result = dream_and_consolidate(memory=CognitiveMemorySystem(), send_prompt=send_prompt)
    except Exception as e:
        return f"<span style='color:#e06c75;'>Rüya döngüsü koşamadı: {_html_escape(e)}</span>"
    if isinstance(result, dict):
        detail = ", ".join(f"{k}: {v}" for k, v in result.items())
    elif isinstance(result, (list, tuple)):
        detail = f"{len(result)} özet"
    else:
        detail = " ".join(str(getattr(result, "summary", result) or "").split())[:400]
    return (f"<b>🧠 Rüya Döngüsü</b>{bridge_note}<br/>{_html_escape(detail) or 'sonuç yok'}"
            "<div style='color:#8B949E;font-size:11px;margin-top:4px;'>"
            "Konsolidasyon doğrudan bilişsel belleğe yazılır.</div>")


def _handle_lint(args: str) -> str:
    """`/lint [<yetenek>|all]`: wiki sağlık denetimi; sonucu lint.md'ye de yazar."""
    from entropy.memory.lint import lint_skill, lint_vault, render_lint_html, write_lint_report

    target = (args or "").strip()
    try:
        if not target or target.lower() == "all":
            results = lint_vault()
        else:
            results = [lint_skill(target.split()[0])]
    except Exception as e:
        return f"<span style='color:#e06c75;'>Denetim yapılamadı: {_html_escape(str(e))}</span>"
    if not results:
        return "<b>🩺 Wiki Denetimi</b><br/>Kasada denetlenecek yetenek yok."
    written = 0
    for res in results:
        try:
            write_lint_report(res)
            written += 1
        except Exception as e:  # pragma: no cover - rapor yazımı sonucu düşürmemeli
            logger.warning("lint.md yazılamadı (%s): %s", res.skill, e)
    return render_lint_html(results) + (
        f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>"
        f"{written} yetenek için <code>wiki/lint.md</code> güncellendi.</div>"
    )


def try_handle_local_command(prompt: str, bridge, distiller=None) -> Optional[str]:
    """
    AGY'ye gitmeden uygulama içinde yürütülen komutları işler.

    Zen ve Chat modlarının ikisi de bunu çağırır; böylece yerel komut mantığı tek
    yerde durur ve iki mod ayrışamaz. Dönen değer sohbete basılacak HTML'dir;
    None dönerse komut yerel değildir ve normal akış devam eder.

    Yerel komutlar:
        /distill                 bekleyen damıtmaları ve maliyetlerini listeler
        /distill <yetenek>       yalnızca OKUNMAMIŞ raporları damıtır (artımlı)
        /distill refresh <yet.>  tüm arşivi yeniden okur (açık istek; pahalı)
        /distill all             bekleyen tüm yetenekler için başlatır
        /distill index           kasadaki raporları yeteneklere yeniden eşler
        /distill stop [<yetenek>|all]  zincirlenen damıtmayı durdurur
        /ask <ofis> <soru>       ofisin posta kutusuna soru bırakır (asenkron)
        /chat <ofis|ajan> <msj>  agentic sohbetin bir turunu başlatır
        /effort [<seviye>]       akıl yürütme eforunu gösterir/ayarlar (kalıcı)
        /login [agy|claude]      sağlayıcı giriş durumu ve giriş yönlendirmesi
        /handoff [not]           oturum devir sayfası yazar ve bağlamı sıkıştırır
        /board                   pano özeti (durumlar, sahiplenmeler, son olaylar)
        /board pick <kart> <ajan>  kartı ajana atar ve kilidini alır
        /board auto [on|off]     otomatik tetikleyiciyi açar/kapatır (kalıcı)
        /lock [on|off]           öz-amplifikasyon kilidini açar/kapatır (kalıcı)
        /model [<ad>]            Entropy'nin KENDİ modelini gösterir/değiştirir
        /agent effort <ad> <sev> ajanın eforunu AGENT.md'ye yazar, derler, oturumu tazeler
        /agent model <ad> <model>  ajanın modelini AGENT.md'ye yazar, derler, oturumu tazeler
        /memory merge            gri bant kuyruğunu toplu işler (hafıza katmanı)
        /memory dream            rüya/konsolidasyon döngüsünü koşar
        /wiki <yetenek>          playbook'tan kavram/varlık sayfaları üretir (model yok)
        /wiki compile <yet.> [--turns N]  wiki sayfalarını çok turlu derler
        /lint [<yetenek>|all]    wiki sağlık denetimi; wiki/lint.md yazar

    `distiller` testler için enjekte edilebilir; verilmezse gerçek depo kullanılır.
    """
    text = (prompt or "").strip()
    # Tam token eşleşmesi: startswith("/distill") "/distillery" gibi başka bir
    # komutu da yakalar ve onu yerel sanıp AGY'ye gitmesini engellerdi.
    head, _, args = text.partition(" ")
    head_low = head.lower()
    args = args.strip()

    # /provider: ayrıştırma köprü tarafında (provider.provider_command), yürütme
    # burada. Yerel komut olduğu için asla AGY/Claude'a gitmez.
    from entropy.core.provider import provider_command
    pcmd = provider_command(text)
    if pcmd is not None:
        return _handle_provider(pcmd, bridge)

    # /effort: seviye kümesi köprüden okunur (agy ve claude farklı kümeler
    # sunuyor); ayrıştırma provider.py'de, yürütme burada.
    from entropy.core.provider import effort_command
    ecmd = effort_command(text, bridge)
    if ecmd is not None:
        return _handle_effort(ecmd, bridge)

    if head_low == "/handoff":
        return _handle_handoff(args, bridge)

    # Ajan ve görev kartı komutları: hepsi yerel: kart yazımı ve listeleme model
    # çağırmaz, yalnızca /task <ajan> ... kartı çalıştırırken köprüyü kullanır.
    if head_low == "/agents":
        return _handle_agents(bridge)
    if head_low == "/agent":
        # `/agent effort|model <ad> <değer>` ayarı değiştirir; tek argüman
        # ayrıntı gösterir. Ayrım ilk sözcükte: ajan adı "effort"/"model"
        # olamaz (kayıt defteri o adları ayırıyor).
        if (args.split() or [""])[0].lower() in ("effort", "model"):
            return _handle_agent_setting(args)
        return _handle_agent_detail(args)
    if head_low == "/model":
        return _handle_model(args, bridge)
    if head_low == "/board":
        return _handle_board(args)
    if head_low == "/lock":
        return _handle_lock(args)
    if head_low == "/memory":
        return _handle_memory(args, bridge)
    if head_low == "/tasks":
        return _handle_tasks(args)
    if head_low == "/task":
        return _handle_task(args)
    if head_low == "/offices":
        return _handle_offices(args)
    if head_low == "/desk":
        return _handle_desk(args)

    # Posta kutusu ve kimlik (Faz 5): üçü de model çağırmaz. /chat yalnızca turu
    # KUYRUĞA alır ve hemen döner; asıl köprü çağrısı arka planda koşar.
    if head_low == "/ask":
        return _handle_ask(args)
    if head_low == "/login":
        return _handle_login(args)
    if head_low == "/chat":
        return _handle_chat(args, bridge)

    # Wiki katmanı: `/wiki <yetenek>` ve `/lint` model çağırmaz;
    # `/wiki compile` köprüyü çağırandan alır (Faz 12-A sözleşmesi).
    if head_low == "/wiki":
        return _handle_wiki(args, bridge)
    if head_low == "/lint":
        return _handle_lint(args)

    if head_low != "/distill":
        return None

    from entropy.memory.distiller import PlaybookDistiller
    from entropy.skills.manager import SkillManager

    sm = SkillManager(project_dir=getattr(bridge, "active_project_dir", None))
    skills = {s.name: s for s in sm.list_skills() if s.enabled}
    distiller = distiller or PlaybookDistiller()

    if args.lower().startswith("stop"):
        # Zincirlenen damıtmayı durdurur: sıradaki tur başlamaz, süren görev kesilir.
        target = args.split(None, 1)[1].strip() if len(args.split(None, 1)) > 1 else "all"
        names = distiller.active_skills() if target == "all" else [target]
        if not names:
            return "<b>📘 Yordam Damıtma</b><br/>Süren damıtma yok."
        rows = []
        for name in names:
            killed = distiller.cancel(name, bridge)
            rows.append(f"• {_html_escape(name)}: zincir durduruldu{' ve süren görev sonlandırıldı' if killed else ''}.")
        return "<b>📘 Damıtma Durduruldu</b><br/>" + "<br/>".join(rows)

    if args.lower() == "index":
        # Eski (yetenek klasörü dışındaki) raporları sınıflandırıp indeksler.
        # Yeni raporlar zaten Skills/<yetenek>/Reports/ altına düştüğü için bu,
        # yalnızca geçmiş arşivi damıtmaya kaynak yapmak için gerekir.
        from entropy.memory.playbook import discover_reports

        store = distiller.store
        reports = discover_reports(store.vault_path)
        names = set(skills)

        def _classify(title: str, head_text: str) -> Optional[str]:
            hit = sm.auto_detect_skill_for_prompt(f"{title} {head_text[:1500]}")
            return hit.name if hit and hit.name in names else None

        dist = store.index.rebuild(reports, _classify)
        assigned = sum(dist.values())
        rows = "".join(
            f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>{_html_escape(k)}</td><td>{v} rapor</td></tr>"
            for k, v in dist.items()
        )
        return (
            f"<b>📘 Rapor İndeksi Yenilendi</b><br/>{len(reports)} rapor tarandı, {assigned} tanesi yeteneklere eşlendi"
            f"{', ' + str(len(reports) - assigned) + ' eşleşmedi' if len(reports) - assigned else ''}."
            f"<table style='font-size:11px;margin-top:4px;'>{rows}</table>"
            f"<div style='color:#8B949E;font-size:11px;margin-top:4px;'>İndeks: <code>{_html_escape(str(store.index.index_path))}</code></div>"
        )

    if not args:
        pending = distiller.pending(list(skills))
        if not pending:
            return "<b>📘 Yordam Damıtma</b><br/>Bekleyen damıtma yok — tüm yeteneklerin playbook'u güncel ya da kaynak raporu yok."
        rows = "".join(
            f"<tr><td style='padding:2px 10px 2px 0;color:#00F0FF;'>{_html_escape(p['skill'])}</td>"
            f"<td style='padding:2px 10px 2px 0;'>{p['distilled_from']}/{p['sources_total']} işlendi</td>"
            f"<td style='padding:2px 10px 2px 0;'>bu turda {p['sources_this_pass']}</td>"
            f"<td style='padding:2px 10px 2px 0;color:#8B949E;'>~{p['estimated_prompt_tokens']:,} token/tur</td>"
            # Asıl fatura tek tur değil, zincirin tamamı: tur sayısı × tur boyutu.
            f"<td style='padding:2px 0;color:#FFA657;'>toplam ~{p['estimated_total_tokens']:,} token "
            f"({p['estimated_total_passes']} tur"
            f"{', ' + str(p['duplicates_skipped']) + ' kopya elendi' if p.get('duplicates_skipped') else ''})</td></tr>"
            for p in pending
        )
        return (
            "<b>📘 Bekleyen Yordam Damıtmaları</b>"
            f"<table style='font-size:11px;margin-top:4px;'>{rows}</table>"
            "<div style='color:#8B949E;font-size:11px;margin-top:6px;'>"
            "Başlatmak için: <code>/distill &lt;yetenek&gt;</code> veya <code>/distill all</code>. "
            "Damıtma AGY kotası harcar; sonuç <code>Skills/&lt;yetenek&gt;/PLAYBOOK.md</code> olarak kasaya yazılır."
            "</div>"
        )

    # "Damıt" artımlıdır: yalnızca okunmamış raporlar işlenir. Tüm arşivi yeniden
    # okumak (513 rapor ≈ 20 tur) açık bir istektir; sessizce olmaz.
    allow_refresh = False
    if args.lower().startswith("refresh"):
        allow_refresh = True
        args = args.split(None, 1)[1].strip() if len(args.split(None, 1)) > 1 else ""
        if not args:
            return "<b>📘 Yordam Tazeleme</b><br/>Kullanım: <code>/distill refresh &lt;yetenek&gt;</code>"

    targets: List[str]
    if args.lower() == "all":
        targets = [p["skill"] for p in distiller.pending(list(skills))]
        if not targets:
            return "<b>📘 Yordam Damıtma</b><br/>Bekleyen damıtma yok."
    else:
        name = args.split()[0]
        if name not in skills:
            known = ", ".join(sorted(skills)) or "(yok)"
            return f"<b>📘 Yordam Damıtma</b><br/>'{_html_escape(name)}' adında etkin bir yetenek yok.<br/>Mevcut: {_html_escape(known)}"
        targets = [name]

    lines = ["<b>📘 Yordam Damıtma Başlatıldı</b>"]
    for name in targets:
        started = distiller.run_via_bridge(
            bridge, name, description=skills[name].description or "", allow_refresh=allow_refresh
        )
        if not started:
            total = distiller.plan(name)["sources_total"]
            if total and not allow_refresh:
                lines.append(
                    f"• {_html_escape(name)}: okunmamış rapor yok ({total} rapor işlenmiş). "
                    f"Tüm arşivi yeniden okumak için: <code>/distill refresh {_html_escape(name)}</code>"
                )
            else:
                lines.append(f"• {_html_escape(name)}: kaynak rapor yok, atlandı.")
            continue
        if started.get("already_running"):
            lines.append(
                f"• {_html_escape(name)}: damıtma zaten sürüyor; ikinci zincir açılmadı. "
                f"Durdurmak için: /distill stop {_html_escape(name)}"
            )
            continue
        lines.append(
            f"• {_html_escape(name)}: {started['batch_start']}→{started['batch_start'] + started['sources']}/{started['sources_total']} "
            f"rapor bu turda, ~{started['prompt_tokens']:,} token. Turlar arka planda zincirlenir; "
            "ilerleme yetenek kartında (📘 sayaç) ve terminalde görünür."
        )
    return "<br/>".join(lines)


def get_dynamic_skill_commands(project_dir: Optional[Path] = None) -> List[SlashCommand]:
    """Dynamically discover and parse skills from active project, system Gemini, and default locations in real-time."""
    commands: List[SlashCommand] = []
    seen: Set[str] = set()

    try:
        from entropy.skills.manager import SkillManager
        from entropy.core.config import config

        # Keşif tek bir yerde tanımlıdır; yetenek paneli de aynı listeyi kullanır.
        # Ayrı keşif mantıkları, bir yeteneğin `/` ile seçilebilmesine ama panelde
        # görünmemesine yol açıyordu.
        from entropy.skills.manager import discover_skill_dirs

        dirs_to_check: List[Path] = discover_skill_dirs(project_dir)

        # Helper parser instance
        parser_sm = SkillManager(root_skills_dir=dirs_to_check[0] if dirs_to_check else (home / ".entropy" / "skills"))

        for d in dirs_to_check:
            if not d.exists() or not d.is_dir():
                continue

            # Case A: d itself contains SKILL.md directly
            direct_skill = d / "SKILL.md"
            if direct_skill.exists():
                skill_def = parser_sm.parse_skill_file(direct_skill)
                if skill_def and skill_def.name not in seen:
                    seen.add(skill_def.name)
                    cmd_name = f"/{skill_def.name}" if not skill_def.name.startswith("/") else skill_def.name
                    desc = " ".join((skill_def.description or f"{skill_def.name} uzmanlık yeteneği.").split())
                    commands.append(SlashCommand(
                        name=cmd_name,
                        description=desc,
                        category="skill",
                        badge="🎯 YETENEK",
                        color="#00FF9D",
                        usage=f"{cmd_name} <istek>",
                        metadata={"skill_name": skill_def.name, "path": str(direct_skill)}
                    ))

            # Case B: d contains subdirectories with SKILL.md
            try:
                for sub in d.iterdir():
                    if not sub.is_dir():
                        continue
                    s_file = sub / "SKILL.md"
                    if s_file.exists():
                        skill_def = parser_sm.parse_skill_file(s_file)
                        if skill_def and skill_def.name not in seen:
                            seen.add(skill_def.name)
                            cmd_name = f"/{skill_def.name}" if not skill_def.name.startswith("/") else skill_def.name
                            desc = " ".join((skill_def.description or f"{skill_def.name} uzmanlık yeteneği.").split())
                            commands.append(SlashCommand(
                                name=cmd_name,
                                description=desc,
                                category="skill",
                                badge="🎯 YETENEK",
                                color="#00FF9D",
                                usage=f"{cmd_name} <istek>",
                                metadata={"skill_name": skill_def.name, "path": str(s_file)}
                            ))
            except Exception:
                pass
    except Exception:
        pass

    return commands

def get_dynamic_mcp_commands(mcp_manager: Optional[Any] = None) -> List[SlashCommand]:
    """Dynamically discover MCP servers and tools from McpManager in real-time."""
    commands: List[SlashCommand] = []
    seen: Set[str] = set()

    try:
        from entropy.mcp.manager import default_mcp_manager
        mgr = mcp_manager or default_mcp_manager
        servers = mgr.list_servers()
        for s in servers:
            s_name = s.get("name", "").strip()
            if not s_name:
                continue
            cmd_name = f"/{s_name}" if not s_name.startswith("/") else s_name
            if cmd_name not in seen:
                seen.add(cmd_name)
                s_type = s.get("type", "stdio")
                target = s.get("target", "")
                desc = f"MCP Sunucusu ({s_type}): {target}" if target else f"MCP Sunucusu ({s_type})"
                commands.append(SlashCommand(
                    name=cmd_name,
                    description=desc,
                    category="mcp",
                    badge="🔌 MCP",
                    color="#FFB300",
                    usage=f"{cmd_name} <istek/eylem>",
                    metadata={"server_name": s_name, "type": s_type, "target": target}
                ))

            # Fetch sub-tools for this server
            tools = mgr.list_tools(s_name)
            for t in tools:
                t_name = t.get("name", "").strip()
                t_desc = t.get("description", "").strip()
                tool_cmd = f"/{s_name}:{t_name}"
                if tool_cmd not in seen:
                    seen.add(tool_cmd)
                    commands.append(SlashCommand(
                        name=tool_cmd,
                        description=t_desc or f"{s_name} - {t_name} aracı",
                        category="mcp_tool",
                        badge="🔌 MCP ARAÇ",
                        color="#FFB300",
                        usage=f"{tool_cmd} <parametreler>",
                        metadata={"server_name": s_name, "tool_name": t_name}
                    ))
    except Exception:
        pass

    return commands

def get_dynamic_tool_commands() -> List[SlashCommand]:
    """Dynamically discover synthesized self-tools in real-time."""
    commands: List[SlashCommand] = []
    try:
        from entropy.tools.synthesizer import default_synthesizer
        for tool_name, tool in default_synthesizer.registered_tools.items():
            cmd_name = f"/{tool_name}" if not tool_name.startswith("/") else tool_name
            commands.append(SlashCommand(
                name=cmd_name,
                description=tool.description or f"Sentezlenmiş dinamik araç ({tool.tier})",
                category="tool",
                badge="🛠️ ARAÇ",
                color="#D2A8FF",
                usage=f"{cmd_name} <parametreler>",
                metadata={"tool_name": tool_name, "tier": tool.tier}
            ))
    except Exception:
        pass

    return commands

# ---------------------------------------------------------------------------
# Komut kataloğu önbelleği
#
# get_all_commands her çağrıda tüm yetenek dizinlerini tarayıp her SKILL.md'yi
# ayrıştırıyordu. Giriş kutusunda "/" ile başlayan her tuş vuruşu bu taramayı
# ana iş parçacığında tetikliyordu; ölçüm: tuş başına 65–223 ms (medyan 96 ms).
# Katalog nadiren değişir, bu yüzden kısa ömürlü bir önbellekte tutulur ve
# yetenek/MCP kataloğu değiştiğinde (bus.skills_updated, bus.mcp_servers_updated)
# arayüz tarafından açıkça geçersiz kılınır.
# ---------------------------------------------------------------------------

COMMAND_CACHE_TTL_SECONDS = 30.0
_COMMAND_CACHE: Dict[str, Tuple[float, List["SlashCommand"]]] = {}
_COMMAND_CACHE_LOCK = threading.Lock()


def invalidate_command_cache() -> None:
    """Komut kataloğu önbelleğini boşaltır (yetenek/MCP değişiminde çağrılır)."""
    with _COMMAND_CACHE_LOCK:
        _COMMAND_CACHE.clear()


def command_cache_stats() -> Dict[str, int]:
    """Testler ve tanılama için önbellek durumu."""
    with _COMMAND_CACHE_LOCK:
        return {"entries": len(_COMMAND_CACHE)}


class SlashCommandRegistry:
    """Registry that aggregates and dynamically queries builtin, skill, MCP, and tool commands."""

    def __init__(self, mcp_manager: Optional[Any] = None):
        self.mcp_manager = mcp_manager

    def get_all_commands(self, project_dir: Optional[Path] = None) -> List[SlashCommand]:
        """
        Tüm komutları döndürür; sonuç kısa süre önbelleklenir.

        Önbellek anahtarı proje dizini: farklı projelerde farklı yetenek kümesi
        bulunur. TTL dolduğunda ya da katalog geçersiz kılındığında yeniden taranır.
        """
        cache_key = str(project_dir or "")
        now = time.monotonic()
        with _COMMAND_CACHE_LOCK:
            hit = _COMMAND_CACHE.get(cache_key)
            if hit and (now - hit[0]) < COMMAND_CACHE_TTL_SECONDS:
                return list(hit[1])

        fresh = self._discover_all_commands(project_dir)
        with _COMMAND_CACHE_LOCK:
            _COMMAND_CACHE[cache_key] = (time.monotonic(), fresh)
        return list(fresh)

    def _discover_all_commands(self, project_dir: Optional[Path] = None) -> List[SlashCommand]:
        """Diski/MCP'yi gerçekten tarayan asıl keşif (önbelleksiz)."""
        all_cmds: List[SlashCommand] = []
        seen_names: Set[str] = set()

        raw_list: List[SlashCommand] = []
        raw_list.extend(BUILTIN_AGY_COMMANDS)
        raw_list.extend(LOCAL_COMMANDS)
        raw_list.extend(get_dynamic_skill_commands(project_dir))
        raw_list.extend(get_dynamic_mcp_commands(self.mcp_manager))
        raw_list.extend(get_dynamic_tool_commands())

        for cmd in raw_list:
            c_key = cmd.name.lower()
            if c_key not in seen_names:
                seen_names.add(c_key)
                all_cmds.append(cmd)

        return all_cmds

    def filter_commands(self, query: str, project_dir: Optional[Path] = None) -> List[SlashCommand]:
        """
        Filter commands based on user search prefix/query with intelligent ranking.
        1. Exact prefix matches on command name (e.g. '/bo' -> '/boost')
        2. Substring matches on command name
        3. Matches on description or badge keywords
        """
        all_cmds = self.get_all_commands(project_dir)
        q = (query or "").strip()
        if not q or q == "/":
            return all_cmds

        search_key = q[1:].lower() if q.startswith("/") else q.lower()

        prefix_matches: List[SlashCommand] = []
        substring_name_matches: List[SlashCommand] = []
        desc_matches: List[SlashCommand] = []

        for cmd in all_cmds:
            c_name = cmd.name[1:].lower() if cmd.name.startswith("/") else cmd.name.lower()
            if c_name.startswith(search_key):
                prefix_matches.append(cmd)
            elif search_key in c_name:
                substring_name_matches.append(cmd)
            elif search_key in cmd.description.lower() or search_key in cmd.badge.lower():
                desc_matches.append(cmd)

        return prefix_matches + substring_name_matches + desc_matches

