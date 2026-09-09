"""Dynamic Slash Commands Registry and Discovery Engine for Antigravity & Entropy AI."""

import logging
import threading
import time
from dataclasses import dataclass
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
        description="Aktif LLM modelini görüntüler veya yeni bir modele geçiş yapar.",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/model <model_adı>",
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
    return (
        f"<b>Akıl Yürütme Eforu</b> artık <b>{_html_escape(level)}</b>"
        f"{f' ({_html_escape(provider)})' if provider else ''}."
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
    `/task <ajan> <başlık> :: <hedef>` — kart oluşturur ve hemen çalıştırır.
    `/task stop <id>` — süren kartı keser.

    Ayırıcı `::` kasıtlı: başlık ve hedefin ikisi de boşluk içerir, tek boşlukla
    ayırmak "hangi kelimeden sonrası hedef" sorusunu tahmine bırakırdı.
    """
    from dataclasses import replace as _replace

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
        if card.status != "running":
            return (f"<b>📋 Görev</b><br/>'{_html_escape(card_id)}' çalışmıyor "
                    f"(durum: {_html_escape(card.status)}).")
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

    task_id = board.run(card.id)
    if not task_id:
        board.update(_replace(card, status="failed", summary="Köprü başlatılamadı."))
        return (f"<b>📋 Görev</b><br/>Kart oluşturuldu ama başlatılamadı: "
                f"<code>{_html_escape(card.id)}</code>")
    return (
        f"<b>📋 Görev Devredildi</b><br/>"
        f"🤖 {_html_escape(spec.name)} → {_html_escape(card.title)}<br/>"
        f"<span style='color:#8B949E;font-size:11px;'>Hedef: {_html_escape(card.goal)}<br/>"
        f"Kart: <code>{_html_escape(str(card.path))}</code><br/>"
        f"Arka planda çalışıyor; bitince kart <b>review</b> olur. "
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


def _desk_usage() -> str:
    """Tek yerde tutulan `/desk` kullanım metni (hata yollarının hepsi buraya döner)."""
    return (
        "<b>🏢 Agent Desk</b><br/>"
        "<code>/desk</code> · <code>/desk office add &lt;ad&gt; :: &lt;amaç&gt;</code> · "
        "<code>/desk office rm &lt;ad&gt;</code><br/>"
        "<code>/desk agent add|edit|rm &lt;ofis&gt; &lt;ad&gt; :: &lt;açıklama&gt;</code><br/>"
        "<code>/desk project add &lt;ofis&gt; &lt;ad&gt; :: &lt;hedef&gt;</code><br/>"
        "<code>/desk task &lt;ofis&gt; [@proje] &lt;başlık&gt; :: &lt;hedef&gt;</code> · "
        "<code>/desk stop &lt;kart&gt;</code>"
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
        try:
            project = offices.create_project(
                office_name, DeskProject(name=project_name, goal=detail, charter=detail)
            )
        except Exception as exc:
            return f"<b>🏢 Proje</b><br/>Yazılamadı: {_html_escape(exc)}"
        return (
            f"<b>🏢 Proje</b><br/>{_html_escape(office_name)} / "
            f"{_html_escape(project.name)} oluşturuldu.<br/>"
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

    from entropy.agents.registry import AgentSpec

    existing = agents.get(agent_name)
    if action == "add" and existing is not None:
        return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(agent_name)}' bu ofiste zaten var."
    if action == "edit" and existing is None:
        return f"<b>🤖 Ofis Ajanı</b><br/>'{_html_escape(agent_name)}' bu ofiste yok."
    office = offices.get(office_name)
    spec = existing or AgentSpec(
        name=agent_name,
        role="worker",
        provider=(office.default_provider if office else "agy"),
        model=(office.default_model if office else ""),
        tools_policy="read-write",
        memory_path=f"memory/{agent_name}.md",
    )
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
                c for c in board.list()
                if c.office == spec.name and not c.parent and c.status in ("running", "review")
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


def _handle_wiki(args: str) -> str:
    """
    `/wiki <yetenek>`: playbook'tan kavram/varlık sayfalarını elle üretir.

    Model çağırmaz (bkz. memory/wiki.ingest_playbook_to_wiki), bu yüzden kota
    harcamaz; damıtma bittiğinde aynı işlev zaten otomatik çalışır.
    """
    from entropy.memory.wiki import ingest_playbook_to_wiki

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
        /wiki <yetenek>          playbook'tan kavram/varlık sayfaları üretir (model yok)
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
        return _handle_agent_detail(args)
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

    # Wiki katmanı: ikisi de model çağırmaz, bu yüzden yerel komuttur.
    if head_low == "/wiki":
        return _handle_wiki(args)
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

