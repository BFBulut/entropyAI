"""Dynamic Slash Commands Registry and Discovery Engine for Antigravity & Entropy AI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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
        name="/agents",
        description="Sistemde tanımlı özel uzmanlık ajanlarını ve rollerini listeler.",
        category="builtin",
        badge="⚡ AGY",
        color="#9D00FF",
        usage="/agents",
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
        description="Model düşünme bütçesini ve akıl yürütme seviyesini ayarlar (low | medium | high).",
        category="builtin",
        badge="⚡ AGY",
        color="#00F0FF",
        usage="/effort <low|medium|high>",
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
        usage="/distill [<yetenek_adı>|all|index|stop [<yetenek>]]",
    ),
]


def _html_escape(text: str) -> str:
    import html as _html
    return _html.escape(str(text))


def try_handle_local_command(prompt: str, bridge, distiller=None) -> Optional[str]:
    """
    AGY'ye gitmeden uygulama içinde yürütülen komutları işler.

    Zen ve Chat modlarının ikisi de bunu çağırır; böylece yerel komut mantığı tek
    yerde durur ve iki mod ayrışamaz. Dönen değer sohbete basılacak HTML'dir;
    None dönerse komut yerel değildir ve normal akış devam eder.

    Şu an tek yerel komut /distill:
        /distill                 bekleyen damıtmaları ve maliyetlerini listeler
        /distill <yetenek>       o yetenek için damıtmayı arka planda başlatır
        /distill all             bekleyen tüm yetenekler için başlatır
        /distill index           kasadaki raporları yeteneklere yeniden eşler
        /distill stop [<yetenek>|all]  zincirlenen damıtmayı durdurur

    `distiller` testler için enjekte edilebilir; verilmezse gerçek depo kullanılır.
    """
    text = (prompt or "").strip()
    # Tam token eşleşmesi: startswith("/distill") "/distillery" gibi başka bir
    # komutu da yakalar ve onu yerel sanıp AGY'ye gitmesini engellerdi.
    head, _, args = text.partition(" ")
    if head.lower() != "/distill":
        return None
    args = args.strip()

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
            f"<td style='padding:2px 0;color:#8B949E;'>~{p['estimated_prompt_tokens']:,} token/tur</td></tr>"
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
        started = distiller.run_via_bridge(bridge, name, description=skills[name].description or "")
        if not started:
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

class SlashCommandRegistry:
    """Registry that aggregates and dynamically queries builtin, skill, MCP, and tool commands."""

    def __init__(self, mcp_manager: Optional[Any] = None):
        self.mcp_manager = mcp_manager

    def get_all_commands(self, project_dir: Optional[Path] = None) -> List[SlashCommand]:
        """Fetch all commands with fresh real-time dynamic resolution and name deduplication."""
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

