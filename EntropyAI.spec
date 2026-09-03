# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None
project_root = Path.cwd()

a = Analysis(
    ['run_entropy.py'],
    pathex=[str(project_root), str(project_root / 'src')],
    binaries=[],
    datas=[
        ('entropy.ico', '.'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'pydantic',
        'apscheduler',
        'sqlite3',
        'entropy',
        'entropy.core',
        'entropy.core.config',
        'entropy.core.event_bus',
        'entropy.core.agy_bridge',
        'entropy.ui',
        'entropy.ui.manager',
        'entropy.ui.themes.cyber_theme',
        'entropy.ui.widgets.core_visualizer',
        'entropy.ui.widgets.terminal_pane',
        'entropy.ui.widgets.reports_viewer',
        'entropy.ui.widgets.knowledge_graph',
        'entropy.ui.widgets.mcp_drawer',
        'entropy.ui.modes.zen_mode',
        'entropy.ui.modes.floating_mode',
        'entropy.ui.modes.chat_mode',
        'entropy.memory',
        'entropy.memory.obsidian.vault_manager',
        'entropy.memory.supabase.cognitive_memory',
        'entropy.memory.rag.project_indexer',
        'entropy.tools',
        'entropy.tools.synthesizer',
        'entropy.mcp',
        'entropy.mcp.manager',
        'entropy.scheduler',
        'entropy.scheduler.cron_engine',
        'entropy.platform',
        'entropy.platform.autostart',
        'entropy.platform.clipboard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'IPython'],
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
