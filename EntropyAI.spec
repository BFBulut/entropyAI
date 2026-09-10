# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None
project_root = Path.cwd()

# Faz 11-E: ikon seti QtAwesome (MIT) üzerinden Codicons ailesinden gelir.
# Bilinen paketleme sorunu (spyder-ide/qtawesome#78): font `.ttf` ve charmap
# `.json` dosyaları paketlenmezse ikonlar boş çıkar — bu yüzden fonts klasörü
# datas'a açıkça eklenir. QtAwesome kurulu değilse arayüz çalışmaya devam eder
# (icons.icon() boş QIcon döndürür), o yüzden girdi koşullu.
qtawesome_datas = []
try:
    import qtawesome as _qta

    _qta_fonts = Path(_qta.__file__).parent / 'fonts'
    if _qta_fonts.is_dir():
        qtawesome_datas.append((str(_qta_fonts), 'qtawesome/fonts'))
except Exception:
    pass

a = Analysis(
    ['run_entropy.py'],
    pathex=[str(project_root), str(project_root / 'src')],
    binaries=[],
    datas=[
        ('entropy.ico', '.'),
        # Faz 12-E (üçüzleme kararı): `skills/` TEK PARÇA paketlenmeye devam
        # ediyor, dosya dosya SAYILMIYOR. Gerekçe ölçüyle: yetenekler çalışma
        # anında yol çözümüyle bulunur — `SkillManager` ağacı tarayıp `SKILL.md`
        # arar, `skills/media_agency_soldier_engine.py:33`
        # `root/"skills"/"media-agency-soldier"/"scripts"` yolunu diskten kurar.
        # Açık liste yazmak, spec'in yukarıda kaydettiği Faz 10-C sessiz
        # düşmesinin aynı sınıfını geri getirir (bir girdi atlanır, .exe'de
        # yetenek sessizce kaybolur). Bunun yerine ÜÇÜZLEME KAYNAKTA çözüldü:
        # `skills/media-agency-soldier/` kökündeki 6 ölü proxy dosyası
        # (1.107 satır) `docs/_archive/skills/media-agency-soldier-root-proxies/`
        # altına alındı; pakete artık iki katman giriyor — kanonik
        # `media-agency-soldier/{SKILL.md,scripts}` ve testlerin kullandığı
        # alt çizgili proxy paketi. Kanıt: `docs/_archive/skills/README.md`.
        ('skills', 'skills'),
        # AGENTS.md PAKETLENMEZ: eski, elle yazılmış bir kadro listesiydi
        # (CodeArchitect / Tester / Researcher / MemoryConsolidator) ve
        # `_internal/AGENTS.md` olarak .exe'nin yanına düşüyordu. Ajan okuma
        # izni o klasöre uzandığında Entropy kendi kadrosunu oradan
        # "öğreniyor" ve var olmayan ajanları sayıyordu. Tek gerçek kaynak
        # kasadaki `Entropy/Agents` kayıt defteridir (entropy.agents.registry).
        ('src/entropy/desk/assets', 'entropy/desk/assets'),
        # Faz 10-C: yerleşik ekip şablonları (Araştırma/Refaktör/QA/Medya).
        # Salt veri (`OFFICE.md` + `agents/*/AGENT.md`); ilk kullanımda kasadaki
        # `Desk/Templates` klasörüne KOPYALANIR, kasada varsa dokunulmaz.
        ('src/entropy/desk/templates', 'entropy/desk/templates'),
        # Faz 11-E: ui-design yeteneği zaten ('skills','skills') ile paketleniyor.
    ] + qtawesome_datas,
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'pydantic',
        'sqlite3',
        'entropy',
        'entropy.core',
        'entropy.core.config',
        'entropy.core.event_bus',
        'entropy.core.agy_bridge',
        'entropy.core.task_ledger',
        'entropy.core.project_lock',
        'entropy.core.slash_commands',
        'entropy.core.provider',
        'entropy.core.report_title',
        'entropy.core.claude_bridge',
        'entropy.core.masking',
        'entropy.core.perf_history',
        # Faz 10: Desk veri koku, ofis calisma alani, kontrol noktalari,
        # terfi eden kurallar ve bunlarin arayuz karsiliklari.
        'entropy.core.paths',
        'entropy.memory.office_workspace',
        'entropy.memory.checkpoints',
        'entropy.memory.promoted_rules',
        'entropy.ui.widgets.rules_panel',
        'entropy.desk.terminals_panel',
        'entropy.desk.changes_panel',
        'entropy.desk.receipt',
        'entropy.desk.receipt_panel',
        'entropy.ui',
        'entropy.ui.manager',
        'entropy.ui.themes.cyber_theme',
        # Faz 11-E adım 1: tasarım sistemi (belirteç → QSS → ikon).
        'entropy.ui.design',
        'entropy.ui.design.tokens',
        'entropy.ui.design.qss',
        'entropy.ui.design.icons',
        'entropy.ui.design.embedded',
        'entropy.ui.design.prefs',
        'qtawesome',
        'qtpy',
        'entropy.ui.widgets.core_visualizer',
        'entropy.ui.widgets.terminal_pane',
        'entropy.ui.widgets.reports_viewer',
        'entropy.ui.widgets.knowledge_graph',
        'entropy.ui.widgets.memory_inspector_dialog',
        'entropy.ui.widgets.standalone_report_window',
        'entropy.ui.widgets.mcp_drawer',
        'entropy.ui.widgets.slash_command_popup',
        'entropy.ui.modes.zen_mode',
        'entropy.ui.modes.floating_mode',
        'entropy.ui.modes.chat_mode',
        'entropy.ui.widgets.skills_widget',
        'entropy.ui.widgets.skill_candidates_panel',
        'entropy.ui.widgets.office_cards_panel',
        'entropy.ui.widgets.settings_dialog',
        'entropy.ui.widgets.tasks_widget',
        'entropy.ui.widgets.notification_pill',
        'entropy.ui.widgets.token_badge',
        'entropy.ui.widgets.markdown_renderer',
        'entropy.ui.widgets.agents_widget',
        'entropy.ui.widgets.task_board_widget',
        'entropy.ui.widgets.ui_polish',
        'entropy.ui.widgets.report_inbox',
        # Faz 5 UI parcalari
        'entropy.ui.widgets.report_center',
        'entropy.ui.widgets.command_palette',
        'entropy.ui.widgets.focus_mode',
        'entropy.ui.widgets.timeline_panel',
        'entropy.ui.widgets.notification_center',
        'entropy.ui.widgets.provider_badge',
        # Faz 8 pencere/yerlesim yardimcilari.
        'entropy.ui.widgets.frameless',
        'entropy.ui.widgets.flow_layout',
        # Faz 9 slash istem paleti ve izole sistem istemi olusturucu.
        'entropy.ui.widgets.slash_prompt',
        'entropy.memory.system_prompt',
        'entropy.agents',
        # Faz 5 posta kutusu ve kimlik
        'entropy.agents.mailbox',
        'entropy.core.identity',
        'entropy.agents.registry',
        'entropy.agents.compile',
        'entropy.agents.tasks',
        'entropy.agents.offices',
        'entropy.agents.harness',
        'entropy.agents.bootstrap',
        # Faz 6: Desk kayit defteri, ofis grafigi, piksel sahne motoru,
        # pencere sigdirma ve efor secici.
        'entropy.agents.desk_registry',
        # Faz 10-C: bu moduller yalnizca calisma aninda importlib ile
        # cagriliyor; PyInstaller statik tarayicisi goremedigi icin paketten
        # dusuyor ve .exe'de worktree/PR/sablon/makbuz yollari sessizce
        # kapaniyordu.
        'entropy.agents.worktrees',
        'entropy.agents.pr_flow',
        'entropy.agents.templates',
        'entropy.memory.office_graph',
        'entropy.desk.engine',
        'entropy.desk.engine.assets',
        'entropy.desk.engine.furniture',
        'entropy.desk.engine.layout',
        'entropy.desk.engine.pathing',
        'entropy.desk.engine.sprites',
        'entropy.desk.engine.tilemap',
        'entropy.ui.window_sizing',
        'entropy.ui.widgets.effort_selector',
        'entropy.desk.window',
        'entropy.desk.scene',
        'entropy.desk.offices_panel',
        'entropy.desk.roster_panel',
        'entropy.desk.board_panel',
        'entropy.desk.stream_panel',
        # Faz 7: Desk bellek/proje panelleri, kasa hijyeni, cokme gunlugu,
        # tek ornek kilidi, paket koku modulleri.
        'entropy.desk.memory_panel',
        'entropy.desk.projects_panel',
        'entropy.memory.vault_hygiene',
        'entropy.core.crash_log',
        'entropy.core.single_instance',
        'entropy.main',
        'entropy.ui.modes',
        'entropy.ui.widgets',
        'entropy.skills.media_agency_soldier',
        'entropy.skills.media_agency_soldier_engine',
        'entropy.agents.watchers',
        'entropy.skills',
        'entropy.skills.manager',
        'entropy.skills.pdf_engine',
        'pypdf',
        'yaml',
        'entropy.memory',
        'entropy.memory.playbook',
        'entropy.memory.distiller',
        'entropy.memory.context_builder',
        'entropy.memory.report_watcher',
        'entropy.memory.handoff',
        'entropy.memory.obsidian.vault_manager',
        'entropy.memory.wiki',
        'entropy.memory.lint',
        'entropy.memory.agent_memory',
        # Faz 5 graf katmani
        'entropy.memory.graph_store',
        'entropy.memory.reconcile',
        # Faz 8 graf zenginlestirme (Louvain icin networkx).
        'entropy.memory.graph_enrich',
        'networkx',
        'networkx.algorithms.community',
        'entropy.memory.office_memory',
        'entropy.memory.supabase.cognitive_memory',
        'numpy',
        'entropy.memory.rag.project_indexer',
        'entropy.tools',
        'entropy.tools.synthesizer',
        'entropy.mcp',
        'entropy.mcp.manager',
        'entropy.scheduler',
        'entropy.scheduler.cron_engine',
        'entropy.platform',
        'entropy.platform.clipboard',
        'entropy.desk',
        # Faz 12-A: Faz 11'de eklenen 15 modul spec'te hic gecmiyordu (arastirma
        # B §2.3). Cogu statik import ile cagriliyor, ama spec ile kaynak
        # arasindaki sapma Faz 10-C'de tam olarak bu sinifta sessiz bir dusme
        # uretmisti; kalici esleme testi tests/contracts/test_spec_sync.py.
        'entropy.agents.amplification',
        'entropy.agents.board_events',
        'entropy.agents.board_fsm',
        'entropy.agents.board_tools',
        # Faz 12-B: otonom pano (araç yürütücüsü, kart üretimi, oturum bütçesi).
        'entropy.agents.board_tool_exec',
        'entropy.agents.board_autonomy',
        'entropy.agents.session_budget',
        'entropy.agents.dispatcher',
        'entropy.core.claude_bg',
        'entropy.memory.categories',
        'entropy.memory.dream',
        'entropy.memory.gate',
        'entropy.memory.gray_merge',
        # Faz 12-C: beceri sentezi (slash komutu calisma aninda ice aktariyor).
        'entropy.memory.skill_synthesis',
        'entropy.ui.widgets.agent_session_badge',
        'entropy.ui.widgets.header_bar',
        'entropy.ui.widgets.nav_list',
        'entropy.ui.widgets.report_card_bridge',
        'entropy.ui.widgets.report_chat_card',
        # Faz 12-A: hafiza turlarinin kopru uyarlayicisi (slash komutlari
        # calisma aninda ice aktariyor).
        'entropy.core.bridge_prompt',
        'entropy.core.response_hooks',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EntropyAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='entropy.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EntropyAI',
)
