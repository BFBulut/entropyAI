"""Radyal tidy grafik düzeni ve yenilenen rapor okuyucusu için testler."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE, KnowledgeGraphWidget
from entropy.ui.widgets.reports_viewer import (
    ReportsViewerWidget,
    move_to_trash,
    obsidian_uri,
    read_report_meta,
)

NODE_HARNESS = """
function makeCtx() {
  return {
    fillStyle: '', strokeStyle: '', lineWidth: 1, font: '', globalAlpha: 1,
    textAlign: 'left', textBaseline: 'alphabetic',
    fillRect: () => {}, clearRect: () => {}, save: () => {}, restore: () => {},
    translate: () => {}, scale: () => {}, beginPath: () => {}, closePath: () => {},
    moveTo: () => {}, lineTo: () => {}, quadraticCurveTo: () => {},
    stroke: () => {}, fill: () => {}, arc: () => {}, rect: () => {}, roundRect: () => {},
    setLineDash: () => {}, measureText: (t) => ({ width: (t || '').length * 6 }),
    fillText: () => {},
    createLinearGradient: () => ({ addColorStop: () => {} }),
    createRadialGradient: () => ({ addColorStop: () => {} })
  };
}
const window = {
  innerWidth: 1200, innerHeight: 800,
  addEventListener: () => {}, onerror: null, location: { href: '' }
};
const document = {
  documentElement: { clientWidth: 1200, clientHeight: 800 },
  getElementById: () => ({
    getContext: () => makeCtx(), addEventListener: () => {},
    style: {}, classList: { toggle: () => {} }, width: 1200, height: 800
  })
};
let requestAnimationFrame = () => {};
let setTimeout = (cb) => cb();
let clearTimeout = () => {};
"""

MEASURE_TAIL = """
function segInt(a, b, c, d) {
  const d1 = (d.x - c.x) * (a.y - c.y) - (d.y - c.y) * (a.x - c.x);
  const d2 = (d.x - c.x) * (b.y - c.y) - (d.y - c.y) * (b.x - c.x);
  const d3 = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const d4 = (b.x - a.x) * (d.y - a.y) - (b.y - a.y) * (d.x - a.x);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}
function drawnTreeLinks() {
  const out = [];
  links.forEach(l => {
    if (l.is_catalog_link || !l.is_tree_link) return;
    const s = l.sourceNode, t = l.targetNode;
    if (!s || !t) return;
    if (!isNodeVisible(s) || !isNodeVisible(t)) return;
    if (!isNodeInScope(s) || !isNodeInScope(t)) return;
    out.push(l);
  });
  return out;
}
function countCrossings() {
  const ls = drawnTreeLinks();
  let n = 0;
  for (let i = 0; i < ls.length; i++) {
    for (let j = i + 1; j < ls.length; j++) {
      const a = ls[i], b = ls[j];
      if (a.sourceNode === b.sourceNode || a.sourceNode === b.targetNode ||
          a.targetNode === b.sourceNode || a.targetNode === b.targetNode) continue;
      if (segInt(a.sourceNode, a.targetNode, b.sourceNode, b.targetNode)) n++;
    }
  }
  return { crossings: n, links: ls.length };
}
function offscreen() {
  let off = 0, vis = 0;
  nodes.forEach(n => {
    if (!isNodeVisible(n) || !isNodeInScope(n)) return;
    vis++;
    const sx = n.x * zoom + panX, sy = n.y * zoom + panY;
    if (sx < -2 || sx > width + 2 || sy < -2 || sy > height + 2) off++;
  });
  return { off: off, vis: vis };
}
const res = {};
fitToView();
res.frame1 = countCrossings();
res.frame1_off = offscreen();
let frames = 0;
while (frames < 1000) { render(); frames++; if (alpha < alphaMin && !draggedNode) break; }
res.settleFrames = frames;
fitToView();
res.settled = countCrossings();
res.settled_off = offscreen();

// Kümeleri aç: yapraklar kümenin sektöründe açılmalı, kesişme oluşmamalı.
nodes.forEach(n => { if (n.group === 'report-cluster') expandedClusters.add(n.id); });
relayoutGraph();
for (let i = 0; i < 400; i++) { render(); if (alpha < alphaMin) break; }
fitToView();
res.expanded = countCrossings();
res.expanded_off = offscreen();

// Kapsam değişimi aynı kuralı seçili dala uygular.
expandedClusters.clear();
setScope('all_cognitive');
for (let i = 0; i < 400; i++) { render(); if (alpha < alphaMin) break; }
fitToView();
res.scoped = countCrossings();
res.scoped_off = offscreen();

let nan = 0, oob = 0;
nodes.forEach(n => { if (isNaN(n.x) || isNaN(n.y)) nan++; if (Math.abs(n.x) > 5000 || Math.abs(n.y) > 5000) oob++; });
res.nan = nan; res.oob = oob;
console.log(JSON.stringify(res));
"""


def _run_layout_measurement(tmp_path, graph_data) -> dict:
    """Grafiği Node.js'te çalıştırıp düzen ölçümlerini döndürür."""
    nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False).replace("</", "<\\/")
    links_json = json.dumps(graph_data["links"], ensure_ascii=False).replace("</", "<\\/")
    html = (
        GRAPH_HTML_TEMPLATE
        .replace("__NODES__", nodes_json)
        .replace("__LINKS__", links_json)
        .replace("__INITIAL_SCOPE__", "all")
        .replace("__ACTIVE_PROJECT_SLUG__", "entropiai")
    )
    js = html[html.find("<script>") + len("<script>"):html.find("</script>")]
    script = tmp_path / "layout_measure.js"
    script.write_text(NODE_HARNESS + js + MEASURE_TAIL, encoding="utf-8")
    node_bin = shutil.which("node")
    result = subprocess.run([node_bin, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"Node hata verdi: {result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_radial_layout_engine_present_in_template():
    """Düzen motoru ve kenar ayrımı şablonda bulunmalı."""
    assert "function relayoutGraph()" in GRAPH_HTML_TEMPLATE
    assert "relayoutAndFit" in GRAPH_HTML_TEMPLATE
    assert "LAYOUT_START_ANGLE" in GRAPH_HTML_TEMPLATE
    # Yaprak kenarları düz, gövde kenarları eğri çizilir
    assert "leafLinks" in GRAPH_HTML_TEMPLATE
    assert "TRUNK_TARGETS" in GRAPH_HTML_TEMPLATE
    # Kapsam ve küme değişiminde aynı kural yeniden uygulanır
    assert "relayoutAndFit(0.30);" in GRAPH_HTML_TEMPLATE


@pytest.mark.parametrize("report_count", [30])
def test_radial_layout_has_no_edge_crossings_and_no_offscreen(qapp, tmp_path, report_count):
    """Gerçekçi veride ağaç kenarları kesişmemeli, sığdırma sonrası ekran dışı düğüm kalmamalı."""
    if not shutil.which("node"):
        pytest.skip("Node.js kurulu değil")

    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(report_count):
        tag = "autonomous-agent" if i % 2 == 0 else "financial-auditor"
        vm.save_research_report(f"Layout_Report_{i}", f"# Rapor {i}", tags=[tag])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    res = _run_layout_measurement(tmp_path, graph)
    widget.close()

    assert res["nan"] == 0
    assert res["oob"] == 0
    # 1. İlk kare zaten düzenli (fizik durulmasını beklemez)
    assert res["frame1"]["crossings"] == 0, f"İlk karede kesişme: {res['frame1']}"
    assert res["frame1_off"]["off"] == 0
    # 2. Durulduktan sonra da düzen korunur ve hızlı durulur
    assert res["settled"]["crossings"] == 0, f"Durulunca kesişme: {res['settled']}"
    assert res["settled_off"]["off"] == 0
    assert res["settleFrames"] <= 80, f"Durulma çok uzun: {res['settleFrames']} kare"
    # 3. Küme açılınca yapraklar kümenin sektöründe açılır, kesişme oluşmaz
    assert res["expanded"]["crossings"] == 0, f"Küme açıkken kesişme: {res['expanded']}"
    assert res["expanded_off"]["off"] == 0
    # 4. Odak değişince aynı kural seçili dala uygulanır
    assert res["scoped"]["crossings"] == 0, f"Kapsam değişiminde kesişme: {res['scoped']}"
    assert res["scoped_off"]["off"] == 0


def test_read_report_meta_parses_frontmatter(tmp_path):
    """Rapor künyesi ön maddeden başlık, tarih, etiket ve yetenek çıkarır."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    path = vm.save_research_report(
        "Kantitatif Risk Analizi", "# Gövde\n\n| a | b |\n| --- | --- |\n| 1 | 2 |",
        tags=["risk", "skill:financial-auditor"]
    )
    meta = read_report_meta(path)
    assert meta["title"] == "Kantitatif Risk Analizi"
    assert meta["skill"] == "financial-auditor"
    assert "risk" in meta["tags"]
    assert len(meta["date"]) == 10
    assert meta["modified"]


def test_reports_viewer_grouping_filter_and_search(qapp, tmp_path):
    """Liste yeteneğe/tarihe göre gruplanır, filtre ve arama kayıtları daraltır."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Alfa Raporu", "# Alfa", tags=["skill:financial-auditor"])
    vm.save_research_report("Beta Raporu", "# Beta", tags=["skill:autonomous-agent"])

    viewer = ReportsViewerWidget(vault_manager=vm)
    viewer.active_project_dir = tmp_path
    viewer.refresh_reports()

    titles = [e["title"] for e in viewer._entries]
    assert "Alfa Raporu" in titles and "Beta Raporu" in titles

    # Gruplama seçenekleri ve filtre listesi
    assert viewer.group_combo.count() == 3
    assert viewer.filter_combo.findData("skill:financial-auditor") > 0
    assert viewer.filter_combo.findData("skill:autonomous-agent") > 0

    # Yeteneğe göre gruplama grup başlığı satırı üretir (seçilemez)
    headers = [
        viewer.list_widget.item(i)
        for i in range(viewer.list_widget.count())
        if viewer.list_widget.item(i).data(0x0100) is None
    ]
    assert len(headers) >= 2

    # Arama daraltır
    viewer.search_input.setText("alfa")
    labels = [
        viewer.list_widget.item(i).text()
        for i in range(viewer.list_widget.count())
        if viewer.list_widget.item(i).data(0x0100)
    ]
    assert any("Alfa" in t for t in labels)
    assert not any("Beta" in t for t in labels)

    # Filtre daraltır
    viewer.search_input.setText("")
    idx = viewer.filter_combo.findData("skill:autonomous-agent")
    viewer.filter_combo.setCurrentIndex(idx)
    labels = [
        viewer.list_widget.item(i).text()
        for i in range(viewer.list_widget.count())
        if viewer.list_widget.item(i).data(0x0100)
    ]
    assert any("Beta" in t for t in labels)
    assert not any("Alfa" in t for t in labels)

    # Tarihe göre gruplama da başlık üretir
    viewer.filter_combo.setCurrentIndex(0)
    viewer.group_combo.setCurrentIndex(1)
    date_headers = [
        viewer.list_widget.item(i).text()
        for i in range(viewer.list_widget.count())
        if viewer.list_widget.item(i).data(0x0100) is None
    ]
    assert any("📅" in h for h in date_headers)

    viewer.close()
    qapp.processEvents()


def test_reports_viewer_meta_panel_and_node_selection(qapp, tmp_path):
    """Grafikten gelen düğüm kimliği raporu açar ve künye paneli dolar."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    report = vm.save_research_report("Grafik Kaynakli Rapor", "# Gövde", tags=["skill:autonomous-agent"])

    viewer = ReportsViewerWidget(vault_manager=vm)
    viewer.active_project_dir = tmp_path
    viewer.refresh_reports()

    # Arama kutusu hedefi gizlese bile açılır (filtreler temizlenir)
    viewer.search_input.setText("eslesmeyen-arama-metni")
    node_id = f"Reports/{report.stem}"
    assert viewer.open_report_by_path_or_id(node_id) is True
    assert viewer._current_path == str(report)
    assert viewer.meta_panel.isVisible() or viewer.meta_panel.text()
    assert "Grafik Kaynakli Rapor" in viewer.meta_panel.text()
    assert "autonomous-agent" in viewer.meta_panel.text()

    # Tam yol ile de bulunur
    assert viewer.open_report_by_path_or_id(str(report)) is True

    viewer.close()
    qapp.processEvents()


def test_reports_viewer_has_obsidian_and_folder_buttons(qapp, tmp_path):
    """Obsidian'da aç ve klasörü aç düğmeleri mevcut, URI biçimi doğru."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    report = vm.save_research_report("URI Testi", "# Gövde", tags=["t"])

    viewer = ReportsViewerWidget(vault_manager=vm)
    assert hasattr(viewer, "btn_open_obsidian")
    assert hasattr(viewer, "btn_open_folder")
    viewer.close()
    qapp.processEvents()

    uri = obsidian_uri(report, tmp_path)
    assert uri.startswith("obsidian://open?vault=")
    assert "file=" in uri
    assert "URI" in uri


def test_delete_moves_report_to_trash_not_permanent(tmp_path):
    """Silme kalıcı değildir: dosya çöp klasörüne taşınır, kaynak kalkar."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    report = vm.save_research_report("Silinecek Rapor", "# Gövde", tags=["t"])
    trash_root = tmp_path / ".trash"

    destination = move_to_trash(report, trash_root)
    assert not report.exists()
    if destination != "recycle-bin":
        moved = Path(destination)
        assert moved.exists()
        assert moved.parent == trash_root
        assert "Gövde" in moved.read_text(encoding="utf-8")
        # Çöp klasörü kasadaki Entropy dizininin dışında olmalı (liste/grafik geri getirmesin)
        assert "Entropy" not in moved.parts


def test_reports_viewer_source_has_no_permanent_unlink():
    """Rapor okuyucusunda kalıcı silme (unlink) çağrısı bulunmamalı."""
    src = Path(__file__).resolve().parents[1] / "src" / "entropy" / "ui" / "widgets" / "reports_viewer.py"
    text = src.read_text(encoding="utf-8")
    assert ".unlink(" not in text
    assert "move_to_trash" in text
