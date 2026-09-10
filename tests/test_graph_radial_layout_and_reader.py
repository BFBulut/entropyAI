"""Organik kuvvet grafiği düzeni ve yenilenen rapor okuyucusu için testler."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
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
// Faz 6: yaprak raporlar acilista gizlidir (kademeli detay). Fizik olcumu
// TUM dugumler uzerinde yapilmali; bu yuzden detay esigi asilir.
applyZoom(Math.max(zoom, DETAIL_ZOOM + 0.2), width / 2, height / 2);

function settle(limit) {
  let frames = 0;
  while (frames < (limit || 3000)) { render(); frames++; if (alpha < alphaMin && !draggedNode) break; }
  return frames;
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
function overlapCount() {
  const v = nodes.filter(n => isNodeVisible(n) && isNodeInScope(n));
  let c = 0;
  for (let i = 0; i < v.length; i++) {
    for (let j = i + 1; j < v.length; j++) {
      const d = Math.hypot(v[j].x - v[i].x, v[j].y - v[i].y);
      if (d < (v[i].val || 12) + (v[j].val || 12) - 1) c++;
    }
  }
  return c;
}
function meanDistances() {
  let simSum = 0, simN = 0;
  links.forEach(l => {
    if (!l.is_similarity_link || !l.sourceNode || !l.targetNode) return;
    simSum += Math.hypot(l.targetNode.x - l.sourceNode.x, l.targetNode.y - l.sourceNode.y);
    simN++;
  });
  // Faz 6: karsilastirma tabani gorunurlukten bagimsiz olmali; sigdirma
  // zoom'u detay esiginin altina indiginde yapraklar gizlenir ama konumlari
  // benzetimde hesaplanmistir.
  const v = nodes.filter(n => n.group === 'Reports');
  let rndSum = 0, rndN = 0;
  for (let i = 0; i < v.length; i += 3) {
    for (let j = i + 1; j < v.length; j += 5) {
      rndSum += Math.hypot(v[j].x - v[i].x, v[j].y - v[i].y);
      rndN++;
    }
  }
  return { sim: simN ? simSum / simN : -1, rand: rndN ? rndSum / rndN : -1, simLinks: simN };
}

const res = {};
const t0 = Date.now();
res.settleFrames = settle();
res.settleMs = Date.now() - t0;
fitToView();
res.settled_off = offscreen();
res.overlaps = overlapCount();
res.dist = meanDistances();
res.positions = nodes.map(n => [n.id, Math.round(n.x * 100) / 100, Math.round(n.y * 100) / 100]);

// Durulmuş benzetimin kare maliyeti (fps tavanı için).
alpha = 0.5;
const t1 = Date.now();
for (let i = 0; i < 40; i++) { alpha = 0.5; tickPhysics(); }
res.tickMs = (Date.now() - t1) / 40;

// Odak değişimi aynı motoru seçili dala uygular.
setScope('all_cognitive');
settle();
fitToView();
res.scoped_off = offscreen();

let nan = 0, oob = 0;
nodes.forEach(n => { if (isNaN(n.x) || isNaN(n.y)) nan++; if (Math.abs(n.x) > 40000 || Math.abs(n.y) > 40000) oob++; });
res.nan = nan; res.oob = oob;
console.log(JSON.stringify(res));
"""


def _run_layout_measurement(tmp_path, graph_data, name="layout_measure.js") -> dict:
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
    script = tmp_path / name
    script.write_text(NODE_HARNESS + js + MEASURE_TAIL, encoding="utf-8")
    node_bin = shutil.which("node")
    result = subprocess.run(
        [node_bin, str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert result.returncode == 0, f"Node hata verdi: {result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_force_layout_engine_present_and_clusters_removed():
    """Radyal sektör motoru ve rapor kümesi düğümleri kaldırılmış olmalı."""
    # Kuvvet motoru: Barnes-Hut itme + bağ türüne göre yay + çakışma ızgarası
    assert "function buildQuadtree" in GRAPH_HTML_TEMPLATE
    assert "function applyCharge" in GRAPH_HTML_TEMPLATE
    assert "function resolveCollisions" in GRAPH_HTML_TEMPLATE
    assert "LINK_KINDS" in GRAPH_HTML_TEMPLATE
    assert "similarity" in GRAPH_HTML_TEMPLATE
    # Deterministik tohum: Math.random yok
    assert "mulberry32" in GRAPH_HTML_TEMPLATE
    assert "Math.random" not in GRAPH_HTML_TEMPLATE
    # Radyal sektör motoru gitti
    assert "LAYOUT_START_ANGLE" not in GRAPH_HTML_TEMPLATE
    assert "LEAF_ARC" not in GRAPH_HTML_TEMPLATE
    # Küme açma/kapama mekanizması gitti
    assert "expandedClusters" not in GRAPH_HTML_TEMPLATE
    assert "toggleCluster" not in GRAPH_HTML_TEMPLATE
    assert "report-cluster" not in GRAPH_HTML_TEMPLATE
    # Topluluk tonu ve yakınlık kenarları çiziliyor
    assert "communityTint" in GRAPH_HTML_TEMPLATE
    # Faz 8: yakinlik kenarlari ayri bir dizi degil, LINK_KINDS uzerinden
    # siniflandirilip cizim dalinda ele aliniyor.
    assert "if (l.is_similarity_link) return 'similarity';" in GRAPH_HTML_TEMPLATE
    assert "else if (kind === 'similarity')" in GRAPH_HTML_TEMPLATE


def test_graph_has_no_cluster_toggle_nodes(qapp, tmp_path):
    """Grafik verisinde '87 rapor' türü küme düğümü ve cluster_of bağı olmamalı."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(40):
        vm.save_research_report(f"Kume_Testi_{i}", f"# Rapor {i}", tags=["autonomous-agent"])
    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    widget.close()

    assert not [n for n in graph["nodes"] if n.get("group") == "report-cluster"]
    assert not [n for n in graph["nodes"] if n.get("cluster_of")]
    reports = [n for n in graph["nodes"] if n.get("group") == "Reports"]
    assert len(reports) == 40, "tüm raporlar tek tek düğüm olarak durmalı"
    assert all("community" in n for n in graph["nodes"])
    assert graph["similarity_links"] > 0, "benzerlik kenarları üretilmeli"


def test_similarity_links_pull_related_reports_together(qapp, tmp_path):
    """Benzer başlıklı raporlar aynı kümeye çekilmeli (yakınlık kenarları)."""
    vm = ObsidianVaultManager(vault_path=tmp_path)
    topics = [
        "SABR volatilite yuzeyi kalibrasyonu",
        "CLO tranche kredi riski",
        "Otonom ajan harness mimarisi",
        "Obsidian exocortex bellek katmani",
    ]
    for i in range(48):
        topic = topics[i % len(topics)]
        vm.save_research_report(f"{topic} Faz{i}", f"# {topic}\n\nicerik", tags=["autonomous-agent"])
    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    widget.close()

    reports = {n["id"]: n["name"] for n in graph["nodes"] if n.get("group") == "Reports"}
    sim = [
        l for l in graph["links"]
        if l.get("is_similarity_link") and l["source"] in reports and l["target"] in reports
    ]
    assert sim, "benzerlik kenarı üretilmedi"
    names = reports
    # Bağlanan çiftler aynı konuyu paylaşmalı
    same_topic = 0
    for l in sim:
        a, b = names.get(l["source"], ""), names.get(l["target"], "")
        if any(t.split()[0].lower() in a.lower() and t.split()[0].lower() in b.lower() for t in topics):
            same_topic += 1
    assert same_topic / len(sim) > 0.85, f"benzerlik kenarlarının çoğu aynı konuda olmalı: {same_topic}/{len(sim)}"


@pytest.mark.parametrize("report_count", [60])
def test_organic_layout_settles_deterministically_without_overlap(qapp, tmp_path, report_count):
    """Kuvvet yerleşimi: deterministik, çakışmasız, ekran dışı düğümsüz ve akıcı."""
    if not shutil.which("node"):
        pytest.skip("Node.js kurulu değil")

    vm = ObsidianVaultManager(vault_path=tmp_path)
    # Baslıklar cok kelimeli: `build_similarity_links` TF-IDF esigi (0.34)
    # korpus buyuklugune duyarlidir; iki kelimelik basliklarda ("SABR
    # volatilite FazN") benzersiz `fazN` belirteci normalize vektorde payi
    # ezip kosinusu 0.23'e dusuruyor ve HIC benzerlik kenari uretilmiyor.
    # Bu test eskiden yalnizca kullanicinin GERCEK `~/.entropy/cognitive_memory.db`
    # dosyasindaki ~80 anlamsal dugum korpusu buyuttugu icin geciyordu
    # (genel durum bagimliligi). Kendi korpusuyla ayakta durmasi icin
    # basliklar gercek rapor baslıklari gibi zenginlestirildi.
    topics = [
        "SABR volatilite yuzeyi kalibrasyonu",
        "CLO kredi riski dilim analizi",
        "Otonom ajan harness mimarisi",
        "Obsidian bellek grafi senkronizasyonu",
    ]
    for i in range(report_count):
        tag = "autonomous-agent" if i % 2 == 0 else "financial-auditor"
        vm.save_research_report(f"{topics[i % 4]} Faz{i}", f"# Rapor {i}", tags=[tag])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    widget.close()

    res = _run_layout_measurement(tmp_path, graph)
    again = _run_layout_measurement(tmp_path, graph, name="layout_measure_2.js")

    assert res["nan"] == 0 and res["oob"] == 0
    # 1. Benzetim sınırlı sayıda karede durulur ve donar
    assert res["settleFrames"] <= 400, f"durulma çok uzun: {res['settleFrames']} kare"
    # 2. Durulunca düğümler üst üste binmez
    assert res["overlaps"] == 0, f"{res['overlaps']} çakışan çift"
    # 3. Sığdırma sonrası ekran dışı düğüm kalmaz (odak değişiminde de)
    assert res["settled_off"]["off"] == 0
    assert res["scoped_off"]["off"] == 0
    # 4. Aynı veri her açılışta aynı yerleşimi verir (tohumlu, Math.random yok)
    assert res["positions"] == again["positions"], "yerleşim deterministik değil"
    # 5. Benzer raporlar birbirine belirgin biçimde yakın
    assert res["dist"]["simLinks"] > 0
    assert res["dist"]["sim"] < res["dist"]["rand"] * 0.5, res["dist"]
    # 6. Kare maliyeti 30 fps bütçesinin (33 ms) çok altında
    assert res["tickMs"] < 20, f"kare başına {res['tickMs']} ms"


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
    # Faz 11-E emoji temizligi basliklardan takvim emojisini kaldirdi;
    # olculen sey grubun VARLIGI ve etiketi, emoji degil.
    assert date_headers, "tarih gruplama basligi uretmedi"
    assert any(
        any(w in h for w in ("Bugün", "Dün", "Bu Hafta", "Bu Ay", "20"))
        for h in date_headers
    ), date_headers

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
