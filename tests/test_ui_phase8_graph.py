"""Faz 8: bilgi grafı kanvası (U1-U8) şablon sözleşmesi testleri.

Grafik JS'i burada gerçek veriyle çalıştırılmaz (ölçüm koşumu offscreen
QWebEngine ile `scratch/ui/phase8/` altında yapılır); buradaki testler şablonun
sözleşmesini doğrular: kuvvet/LOD sabitleri, etiket motoru, efsane süzmesi,
arama sınırı, mini harita ve türetilmiş alanların varlığı.
"""

import os
import re
import shutil
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from entropy.ui.widgets import knowledge_graph as kg

TPL = kg.GRAPH_HTML_TEMPLATE


def _script_body() -> str:
    return TPL.split("<script>", 1)[1].rsplit("</script>", 1)[0]


# --------------------------------------------------------------------------
# U1: kuvvet ince ayarı, halkalar, sektör
# --------------------------------------------------------------------------

def test_u1_force_tuning_constants():
    assert "const CHARGE_BASE = -30;" in TPL              # d3 varsayılanı (eski -230 kalktı)
    assert "const DISTANCE_MAX = 400;" in TPL
    assert "const VELOCITY_DECAY = 0.40;" in TPL
    assert "const alphaDecay = 0.0228;" in TPL
    assert "CHARGE_BASE * (1 + Math.log(1 + n._deg))" in TPL   # derece ağırlıklı itme
    assert "const RING_R = [0, 260, 520, 780, 0];" in TPL      # forceRadial halkaları
    assert "RADIAL_STRENGTH" in TPL and "SECTOR_STRENGTH" in TPL
    assert "function assignSectors" in TPL                     # ağırlıklı radyal sektör


def test_u1_layout_is_deterministic():
    # Tohumlu üreteç dışında rastgelelik yok: Math.random hiçbir yerde geçmez.
    assert "Math.random" not in TPL
    assert "function mulberry32" in TPL and "function hashSeed" in TPL


# --------------------------------------------------------------------------
# U2: dört bantlı LOD
# --------------------------------------------------------------------------

def test_u2_four_lod_bands_and_thresholds():
    assert "const LOD_FAR = 0.25;" in TPL
    assert "const LOD_MAP = 0.75;" in TPL
    assert "const LOD_BRANCH = 1.2;" in TPL
    assert "const BAND_MAX_LEVEL = [2, 3, 4, 4];" in TPL   # ZMLT tutarlılığı: monoton
    assert "function lodBand" in TPL and "function lodFade" in TPL
    # Geriye uyum: eski tek eşik adı korunur.
    assert "const DETAIL_ZOOM = LOD_MAP;" in TPL


def test_u2_band_change_does_not_reheat_simulation():
    body = TPL.split("function applyZoom", 1)[1].split("// ---- Kuvvet", 1)[0]
    assert "relayoutGraph();" in body
    # Bant geçişinde alpha'ya DEĞER ATANMAZ (eski kod alpha = 0.5 yapıyordu).
    assert "alpha =" not in body and "alpha=" not in body


def test_u2_viewport_culling():
    assert "function viewportWorldRect" in TPL
    assert "n._level >= 4 && !inView(n)" in TPL


# --------------------------------------------------------------------------
# U3: efsane
# --------------------------------------------------------------------------

def test_u3_legend_is_single_row_and_filters_empty_categories():
    # Kapalı efsane yüksekliği 26 px.
    css = TPL.split("#legend {", 1)[1].split("}", 1)[0]
    assert "height: 26px;" in css
    body = TPL.split("function buildLegend", 1)[1].split("function toggleLegendPanel", 1)[0]
    assert "if (total > 0) filled.push" in body        # boş kategori çizilmez
    assert "cnt.textContent = String(total);" in body  # kategori sayısı yazılır
    assert "function toggleLegendPanel" in TPL         # katlanabilir panel


def test_u3_dead_controls_are_hidden_and_fit_subtracts_overlays():
    body = TPL.split("function initGraphControls", 1)[1].split("buildLegend();", 1)[0]
    assert "classList.toggle('empty', !anyLive)" in body
    assert ".ctrl-group.disabled { display: none; }" in TPL
    assert "function viewInsets" in TPL
    fit = TPL.split("function fitNodesToView", 1)[1].split("function fitToView", 1)[0]
    assert "viewInsets()" in fit


# --------------------------------------------------------------------------
# U4: etiket motoru
# --------------------------------------------------------------------------

def test_u4_label_engine_priority_bitmap_and_cache():
    assert "const LABEL_CELL = 8;" in TPL
    assert "const LABEL_GRID = 90;" in TPL          # ızgara seyreltmesi
    assert "new Uint8Array(w * h)" in TPL           # doluluk bit haritası
    assert "function bitsFree" in TPL and "function bitsMark" in TPL
    assert "function labelSprite" in TPL            # bitmap önbelleği
    assert "ctx.drawImage(sp.canvas" in TPL
    order = TPL.split("function ensureLabelOrder", 1)[1].split("}", 2)[0]
    # Öncelik: level -> importance -> degree
    assert "a._level - b._level" in order
    assert "b._imp - a._imp" in order
    assert "b._deg - a._deg" in order


def test_u4_label_has_four_candidate_positions():
    body = TPL.split("const cands = [", 1)[1].split("];", 1)[0]
    assert body.count("[") == 4, "dört aday konum (sağ/sol/üst/alt) bekleniyor"


# --------------------------------------------------------------------------
# U5: hover / hit-test / breadcrumb
# --------------------------------------------------------------------------

def test_u5_hover_dim_hittest_and_breadcrumb():
    assert "function dimFactor" in TPL
    dim = TPL.split("function dimFactor", 1)[1].split("}", 3)[0]
    assert "0.6" in dim and "0.12" in dim          # 2-adım 0.6, diğerleri 0.12
    assert "function nodeAt" in TPL and "hitGrid" in TPL
    assert "}, 80);" in TPL                        # 80 ms hover gecikmesi
    assert "function updateBreadcrumb" in TPL
    assert "fitNodesToView(branch.length ? branch : [draggedNode], 250)" in TPL


# --------------------------------------------------------------------------
# U6: topluluk gövdesi ve paletler
# --------------------------------------------------------------------------

def test_u6_hulls_and_cvd_safe_palettes():
    assert "function convexHull" in TPL and "function drawHulls" in TPL
    assert "function drawHullLabels" in TPL
    assert "const OKABE_ITO = [" in TPL
    assert TPL.count("const TOL_12 = [") == 1
    tol = TPL.split("const TOL_12 = [", 1)[1].split("];", 1)[0]
    assert len(re.findall(r"#[0-9A-F]{6}", tol)) == 12
    okabe = TPL.split("const OKABE_ITO = [", 1)[1].split("];", 1)[0]
    assert len(re.findall(r"#[0-9A-F]{6}", okabe)) == 8
    # Hale artık altın açı HSL değil, ayrık 12 tondan gelir.
    assert "137.508" not in TPL


# --------------------------------------------------------------------------
# U7: arama, yol, mini harita
# --------------------------------------------------------------------------

def test_u7_search_limit_is_eight():
    body = TPL.split("function searchNodes", 1)[1].split("function onSearchInput", 1)[0]
    assert "hits.slice(0, 8)" in body, "arama en çok 8 sonuç döndürmeli"
    assert "needle.length < 2" in body


def test_u7_path_and_minimap():
    assert "function showPath" in TPL              # BFS "yol göster"
    assert "function drawMinimap" in TPL and "function buildMinimap" in TPL
    assert "const MINIMAP_W = 160, MINIMAP_H = 110" in TPL
    assert "function minimapPan" in TPL            # tıkla/sürükle ile pan
    # Ctrl+F kancası
    assert "e.key === 'f' || e.key === 'F'" in TPL


# --------------------------------------------------------------------------
# U8: kenar stili
# --------------------------------------------------------------------------

def test_u8_edge_styles():
    assert "const FAN_THRESHOLD = 40;" in TPL      # 40+ çocuklu ebeveynde yelpaze
    assert "function fanOrigin" in TPL
    assert "Array.isArray(l.bundle)" in TPL        # Python'dan gelen demet
    assert "s._cid && s._cid === t._cid" in TPL    # benzerlik yalnız topluluk içi


# --------------------------------------------------------------------------
# Türetilmiş alanlar: yeni alanlar gelmemişse JS türetir, gelirse tercih eder
# --------------------------------------------------------------------------

@pytest.mark.parametrize("field,derived", [
    ("typeof n.level === 'number'", "n._level = 4"),
    ("typeof n.degree === 'number'", "degreeCount.get(n.id)"),
    ("typeof n.child_count === 'number'", "kids.length"),
    ("typeof n.short_label === 'string'", "shortenLabel(n.name)"),
])
def test_new_fields_are_preferred_but_derived_when_missing(field, derived):
    assert field in TPL, f"alan tercih edilmiyor: {field}"
    assert derived in TPL, f"türetme yok: {derived}"


def test_measurement_hook_exists():
    assert "window.__graphStats" in TPL
    for key in ("labels", "physMs", "drawMs", "frameMs", "drawnNodes"):
        assert key in TPL


# --------------------------------------------------------------------------
# Korunan davranışlar (Faz 6 sözleşmesi)
# --------------------------------------------------------------------------

def test_existing_behaviours_preserved():
    for token in (
        "STRUCTURAL_GROUPS",
        "function computeBranchSet",
        "function setIsolationMode",
        "function setSelectedNode",
        "function toggleBranchExpansion",
        "entropy-node://select?id=",
        "function zoomIn",
        "function zoomOut",
        "function resetView",
    ):
        assert token in TPL, f"kaybolan davranış: {token}"


def test_python_api_unchanged():
    for name in ("select_node", "apply_scope", "refresh_graph", "schedule_view_fit", "build_unified_graph"):
        assert hasattr(kg.KnowledgeGraphWidget, name)


@pytest.mark.skipif(shutil.which("node") is None, reason="node yok")
def test_script_body_is_valid_javascript(tmp_path):
    js = _script_body().replace("__NODES__", "[]").replace("__LINKS__", "[]")
    path = tmp_path / "graph_check.js"
    path.write_text(js, encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
