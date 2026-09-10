"""Automated pytest suite for report sanitization, graph navigation, and UI reader improvements."""

import os
import json
import pytest
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from entropy.core.event_bus import bus
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.widgets.knowledge_graph import GraphWebEnginePage, KnowledgeGraphWidget
from entropy.ui.widgets.memory_inspector_dialog import MemoryInspectorDialog
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.modes.chat_mode import ChatModeWindow

def test_report_sanitization_on_save(tmp_path):
    """Verify that save_research_report strips BOM, ANSI escapes, carriage returns, and control chars."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    
    dirty_content = (
        "\ufeff\x1b[32m# Başlık\x1b[0m\r\n"
        "İçerik satırı \x00\x08 ve \x1b[2Ktemiz metin.\r\n"
        "Normal satır."
    )
    
    rep_file = vm.save_research_report("Test_Sanitized_Report", dirty_content, tags=["test"])
    saved_text = rep_file.read_text(encoding="utf-8")
    
    assert "\ufeff" not in saved_text
    assert "\x1b" not in saved_text
    assert "\r" not in saved_text
    assert "\x00" not in saved_text
    assert "İçerik satırı  ve temiz metin." in saved_text
    assert "Normal satır." in saved_text

def test_graph_web_engine_page_url_interception():
    """Verify GraphWebEnginePage accurately extracts node_id with slash and URL encoded characters."""
    # Test query format: entropy-node://select?id=Reports%2FMerkez_Bankasi
    test_url = QUrl("entropy-node://select?id=Reports%2FMerkez_Bankasi")
    node_id = GraphWebEnginePage.extract_node_id_from_url(test_url)
    assert node_id == "Reports/Merkez_Bankasi"

def test_memory_inspector_empty_id_does_not_fall_back_to_first_report(qapp, tmp_path):
    """Verify MemoryInspectorDialog with empty node_id renders generic node, never first report."""
    dialog = MemoryInspectorDialog(node_id="", parent=None)
    assert "Hafıza ve Bağlam Denetleyicisi - " in dialog.windowTitle()
    dialog.close()

def test_memory_inspector_exact_matching(qapp, tmp_path):
    """Verify MemoryInspectorDialog matches the exact targeted report file."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    file_a = vm.save_research_report("Report_Alpha", "# Alpha Content", tags=["a"])
    file_b = vm.save_research_report("Report_Beta", "# Beta Content", tags=["b"])
    
    dialog = MemoryInspectorDialog(node_id=str(file_b), parent=None)
    assert "Report_Beta" in dialog.windowTitle()
    dialog.close()

def test_reports_viewer_flexible_resizing_and_buttons(qapp):
    """Verify ReportsViewerWidget list widget can expand and has read/open action buttons."""
    viewer = ReportsViewerWidget()
    
    # List widget width is flexible (not fixed at 200)
    assert viewer.list_widget.maximumWidth() > 400
    # Faz 7: minimumlar 160 -> 120 dusuruldu ki dar Zen sol paneli kirpilmasin.
    # Iddia "en az 160" degil, "esnek ama kullanilabilir bir taban" olmali.
    assert 100 <= viewer.list_widget.minimumWidth() <= 160
    # Asil olcum: butun panelin minimum genisligi. Faz 7 oncesi ~676 px idi,
    # simdi <= 400 px olmali (olculen: 389).
    assert viewer.minimumSizeHint().width() <= 400
    
    # Explicit action buttons exist
    assert hasattr(viewer, "btn_read_report")
    assert hasattr(viewer, "btn_open_standalone")
    # Faz 11-E adim 3: dugme metninden emoji kaldirildi (ikon design.icon()).
    assert viewer.btn_read_report.text() == "Raporu Oku"
    assert viewer.btn_open_standalone.text() == "Ayrı Aç ↗"
    
    # Splitter is non-collapsible for both sides
    assert viewer.splitter.isCollapsible(0) is False
    assert viewer.splitter.isCollapsible(1) is False
    viewer.close()
    qapp.processEvents()

def test_zen_mode_notification_deduplication(qapp, tmp_path):
    """Verify notification pills and chat cards in ZenModeWindow do not produce duplicates."""
    from entropy.core.agy_bridge import AgyProcessBridge
    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    zen.show()
    test_path = str(tmp_path / "Test_Report.md")
    Path(test_path).write_text("# Test", encoding="utf-8")
    
    # Emit twice rapidly
    zen._on_report_created(test_path)
    zen._on_report_created(test_path)
    
    # Count pills in layout
    pills = [zen.notification_stack_layout.itemAt(i).widget() for i in range(zen.notification_stack_layout.count())]
    report_pills = [p for p in pills if getattr(p, "path_or_content", "") == test_path]
    
    assert len(report_pills) == 1
    zen.close()
    qapp.processEvents()

def test_knowledge_graph_unified_nodes_and_reports(qapp, tmp_path):
    """Verify KnowledgeGraphWidget properly classifies research reports with 'Reports' group and val=16."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Finansal_Rapor_Bilan", "# Bilanço Analizi", tags=["bilanco"])
    
    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]
    links = graph["links"]
    
    # 1. Ego node exists
    ego = next((n for n in nodes if n["id"] == "ego-entropy-core"), None)
    assert ego is not None
    assert ego["group"] == "ego"
    assert ego["val"] == 22
    
    # 2. Report node is classified into 'Reports' group with radius 16
    rep_node = next((n for n in nodes if "Finansal_Rapor_Bilan" in n["name"]), None)
    assert rep_node is not None
    assert rep_node["group"] == "Reports"
    assert rep_node["val"] == 16
    
    # 3. Report is linked in the hierarchical tree structure to its parent hub
    rep_link = next((l for l in links if l["target"] == rep_node["id"]), None)
    assert rep_link is not None
    assert rep_link["source"] == rep_node["parent_hub"]
    assert rep_link.get("is_tree_link") is True
    widget.close()

def test_knowledge_graph_html_generation_and_escaping(qapp, tmp_path):
    """Verify GRAPH_HTML_TEMPLATE escaping prevents script injection and contains report styling."""
    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("XSS_Test", "# Test </script><script>alert(1)</script>", tags=["test"])
    
    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph_data = widget.build_unified_graph()
    
    nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False).replace("</", "<\\/")
    links_json = json.dumps(graph_data["links"], ensure_ascii=False).replace("</", "<\\/")
    html_content = GRAPH_HTML_TEMPLATE.replace("__NODES__", nodes_json).replace("__LINKS__", links_json)
    
    # No unescaped closing script inside node payload
    assert "</script><script>" not in html_content
    # Legend contains research reports category.
    # Faz 8: efsane LEGEND_DEFS'ten kuruluyor, etiket "Raporlar" olarak kisaldi.
    assert "['Reports', 'Raporlar', ['Reports']]" in html_content
    assert "#FF0055" in html_content
    widget.close()

def test_knowledge_graph_js_runtime_execution(qapp, tmp_path):
    """Execute the full knowledge graph JavaScript in Node.js to verify zero runtime errors."""
    import shutil
    import subprocess
    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE
    
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js not installed on system")
        
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Report_1", "# Report 1 Content", tags=["r1"])
    vm.save_research_report("Report_2", "# Report 2 Content [[Report_1]]", tags=["r2"])
    
    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph_data = widget.build_unified_graph()
    
    nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False).replace("</", "<\\/")
    links_json = json.dumps(graph_data["links"], ensure_ascii=False).replace("</", "<\\/")
    html = GRAPH_HTML_TEMPLATE.replace("__NODES__", nodes_json).replace("__LINKS__", links_json)
    
    start = html.find("<script>") + len("<script>")
    end = html.find("</script>")
    js_code = html[start:end]
    
    test_harness = """
const window = {
    innerWidth: 1024,
    innerHeight: 768,
    addEventListener: () => {},
    onerror: null,
    location: { href: '' }
};
const document = {
    documentElement: { clientWidth: 1024, clientHeight: 768 },
    // Faz 8: toggleCategory efsane/rozet ogelerini data-cat ile soluklastiriyor.
    querySelectorAll: () => [],
    createElement: (tag) => ({
        style: {}, className: '', textContent: '', children: [],
        classList: { toggle: () => {} },
        setAttribute: () => {}, getAttribute: () => undefined,
        appendChild: function (c) { this.children.push(c); },
        addEventListener: () => {}
    }),
    getElementById: (id) => ({
        getContext: () => ({
            fillStyle: '',
            strokeStyle: '',
            lineWidth: 1,
            font: '',
            fillRect: () => {},
            save: () => {},
            restore: () => {},
            translate: () => {},
            scale: () => {},
            beginPath: () => {},
            moveTo: () => {},
            lineTo: () => {},
            stroke: () => {},
            fill: () => {},
            arc: () => {},
            rect: () => {},
            roundRect: () => {},
            // Faz 8 sablonu: hull/kavis cizimi ve kirpma.
            closePath: () => {},
            quadraticCurveTo: () => {},
            clearRect: () => {},
            strokeRect: () => {},
            setLineDash: () => {},
            clip: () => {},
            drawImage: () => {},
            globalAlpha: 1,
            textAlign: '',
            textBaseline: '',
            measureText: () => ({ width: 60 }),
            fillText: () => {},
            createLinearGradient: () => ({ addColorStop: () => {} }),
            createRadialGradient: () => ({ addColorStop: () => {} })
        }),
        addEventListener: () => {},
        style: {},
        classList: { toggle: () => {} },
        // Faz 8: buildLegend efsane cubugunu DOM'a ekliyor.
        children: [],
        textContent: '',
        innerHTML: '',
        disabled: false,
        offsetHeight: 30,
        setAttribute: () => {},
        getAttribute: () => undefined,
        appendChild: function (c) { this.children.push(c); },
        getBoundingClientRect: () => ({ left: 0, top: 0 })
    })
};
let requestAnimationFrame = (cb) => {};
let setTimeout = (cb) => cb();

""" + js_code + """

// Execute 30 physics/render frames to verify stability
for (let i = 0; i < 30; i++) {
    render();
}

// Test category toggling
const mockLegendItem = { classList: { toggle: () => {} } };
toggleCategory('Reports', mockLegendItem);
render();
toggleCategory('obsidian', mockLegendItem);
render();
toggleCategory('ego', mockLegendItem);
render();
"""
    
    script_file = tmp_path / "test_knowledge_graph.js"
    script_file.write_text(test_harness, encoding="utf-8")
    
    result = subprocess.run([node_bin, str(script_file)], capture_output=True, text=True)
    assert result.returncode == 0, f"Node.js script failed: {result.stderr}"
    assert "ReferenceError" not in result.stderr
    assert "Render loop error" not in result.stderr
    widget.close()


def test_knowledge_graph_fit_to_view_and_physics_clamping(qapp, tmp_path):
    """Verify that fitToView scales and centers all nodes and physics forces remain strictly bounded."""
    import shutil
    import subprocess
    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE

    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js not installed on system")

    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(25):
        vm.save_research_report(f"Report_AutoFit_{i}", f"# Content {i} [[Report_AutoFit_{max(0, i-1)}]]", tags=["test"])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph_data = widget.build_unified_graph()
    nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False).replace("</", "<\\/")
    links_json = json.dumps(graph_data["links"], ensure_ascii=False).replace("</", "<\\/")
    html = GRAPH_HTML_TEMPLATE.replace("__NODES__", nodes_json).replace("__LINKS__", links_json)

    start = html.find("<script>") + len("<script>")
    end = html.find("</script>")
    js_code = html[start:end]

    test_harness = """
const window = {
    innerWidth: 400,
    innerHeight: 300,
    addEventListener: () => {},
    onerror: (msg) => { console.error('JS Error: ' + msg); },
    location: { href: '' }
};
const document = {
    documentElement: { clientWidth: 400, clientHeight: 300 },
    getElementById: (id) => ({
        getContext: () => ({
            fillStyle: '',
            strokeStyle: '',
            lineWidth: 1,
            font: '',
            fillRect: () => {},
            save: () => {},
            restore: () => {},
            translate: () => {},
            scale: () => {},
            beginPath: () => {},
            moveTo: () => {},
            lineTo: () => {},
            stroke: () => {},
            fill: () => {},
            arc: () => {},
            rect: () => {},
            roundRect: () => {},
            // Faz 8 sablonu: hull/kavis cizimi ve kirpma.
            closePath: () => {},
            quadraticCurveTo: () => {},
            clearRect: () => {},
            strokeRect: () => {},
            setLineDash: () => {},
            clip: () => {},
            drawImage: () => {},
            globalAlpha: 1,
            textAlign: '',
            textBaseline: '',
            measureText: () => ({ width: 50 }),
            fillText: () => {},
            createLinearGradient: () => ({ addColorStop: () => {} }),
            createRadialGradient: () => ({ addColorStop: () => {} })
        }),
        addEventListener: () => {},
        style: {},
        classList: { toggle: () => {} },
        // Faz 8: buildLegend efsane cubugunu DOM'a ekliyor.
        children: [],
        textContent: '',
        innerHTML: '',
        disabled: false,
        offsetHeight: 30,
        setAttribute: () => {},
        getAttribute: () => undefined,
        appendChild: function (c) { this.children.push(c); },
        getBoundingClientRect: () => ({ left: 0, top: 0 })
    })
};
let requestAnimationFrame = (cb) => {};
let setTimeout = (cb) => cb();

""" + js_code + """

// 1. Verify fitToView function exists and runs
fitToView();
if (zoom <= 0 || zoom > 2.0) {
    throw new Error('Invalid fit zoom: ' + zoom);
}

// 2. Run 40 physics frames and check coordinate boundedness
for (let i = 0; i < 40; i++) {
    render();
}

let nanCount = 0;
let outOfBoundsCount = 0;
nodes.forEach(n => {
    if (isNaN(n.x) || isNaN(n.y)) nanCount++;
    if (Math.abs(n.x) > 5000 || Math.abs(n.y) > 5000) outOfBoundsCount++;
});

if (nanCount > 0) throw new Error('Found NaN coordinates: ' + nanCount);
if (outOfBoundsCount > 0) throw new Error('Found exploding coordinates: ' + outOfBoundsCount);

// 3. Re-fit view after physics
fitToView();
let visibleCount = 0;
nodes.forEach(n => {
    const sx = n.x * zoom + panX;
    const sy = n.y * zoom + panY;
    if (sx >= -50 && sx <= width + 50 && sy >= -50 && sy <= height + 50) {
        visibleCount++;
    }
});

if (visibleCount < nodes.length * 0.9) {
    throw new Error('Too few nodes visible after fitToView: ' + visibleCount + '/' + nodes.length);
}
"""

    script_file = tmp_path / "test_fit_clamping.js"
    script_file.write_text(test_harness, encoding="utf-8")

    result = subprocess.run([node_bin, str(script_file)], capture_output=True, text=True)
    assert result.returncode == 0, f"Node.js fit test failed: {result.stderr}"
    widget.close()


