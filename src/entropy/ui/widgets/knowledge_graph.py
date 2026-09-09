"""Interactive Hierarchical Constellation Knowledge Graph Viewer using QWebEngineView with multi-foci centroid physics."""

import os
import re
import json
import math
from pathlib import Path
from typing import Optional, Dict, List, Any, Set, Tuple
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QComboBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

from entropy.core.event_bus import bus
from entropy.core.config import config
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.skills.manager import SkillManager
from entropy.mcp.manager import MCPManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

# Rapor kümesi açma/kapama düğümleri kaldırıldı (2026-09-08): "87 rapor" halkası
# tıklandığında görünüm baştan kuruluyor, kullanıcı yerini kaybediyordu. Artık
# bütün yapraklar her zaman küçük noktalar olarak görünür; kalabalık, kümeleme
# yerine benzerlik kenarları + topluluk renklendirmesiyle okunur kılınır.

# Yaprak düğümler arasında kurulan k-NN benzerlik kenarları. Kosinüs eşiği
# altındaki çiftler bağlanmaz; k komşu, düğüm başına üst sınırdır.
SIMILARITY_K = 4
SIMILARITY_MIN = 0.34
# Benzerlik hesabına giren yaprak grupları (dal/hub düğümleri hariç).
SIMILARITY_GROUPS = {"Reports", "obsidian", "semantic", "episodic", "procedural", "DailyNotes"}

# Başlıklarda ayırt edici olmayan sözcükler.
SIMILARITY_STOPWORDS = {
    "rapor", "report", "analiz", "analysis", "icin", "için", "ile", "ve", "the", "and",
    "faz", "phase", "2026", "2025", "notlar", "notes", "final", "yeni", "guncel",
}


def _similarity_tokens(name: str) -> List[str]:
    """Başlıktan ayırt edici belirteçler; deterministik ve dile duyarsız."""
    slug = normalize_slug(name)
    out = []
    for tok in slug.split("-"):
        if len(tok) < 4 or tok in SIMILARITY_STOPWORDS or tok.isdigit():
            continue
        out.append(tok)
    return out


def build_similarity_links(
    leaf_nodes: List[Dict[str, Any]],
    k: int = SIMILARITY_K,
    threshold: float = SIMILARITY_MIN,
) -> List[Dict[str, Any]]:
    """
    Yaprak düğümler arasında TF-IDF kosinüs benzerliğine dayalı k-NN kenarları.

    Ters indeks kullanılır: yalnızca en az bir belirteci paylaşan çiftler
    karşılaştırılır, bu yüzden maliyet O(N²) değil paylaşılan belirteç sayısıyla
    orantılıdır (900 raporda ölçülen: ~40 ms).
    """
    docs: List[Tuple[str, Dict[str, float]]] = []
    postings: Dict[str, List[int]] = {}
    raw: List[List[str]] = []
    for n in leaf_nodes:
        toks = _similarity_tokens(n.get("name", ""))
        raw.append(toks)
    df: Dict[str, int] = {}
    for toks in raw:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    total_docs = max(1, len(raw))
    for i, toks in enumerate(raw):
        vec: Dict[str, float] = {}
        for t in set(toks):
            # Her belgede geçen bir belirteç (ör. "entropiai") ayırt edici değil.
            idf = math.log(total_docs / (1.0 + df.get(t, 1)))
            if idf <= 0:
                continue
            vec[t] = idf
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm <= 0:
            docs.append((leaf_nodes[i]["id"], {}))
            continue
        vec = {t: v / norm for t, v in vec.items()}
        docs.append((leaf_nodes[i]["id"], vec))
        for t in vec:
            postings.setdefault(t, []).append(i)

    links: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for i, (nid, vec) in enumerate(docs):
        if not vec:
            continue
        scores: Dict[int, float] = {}
        for t, w in vec.items():
            plist = postings.get(t, ())
            # Çok yaygın belirteçler (yüzlerce belge) hem ayırt edici değil hem
            # de karşılaştırma sayısını patlatır; atlanır.
            if len(plist) > 60:
                continue
            for j in plist:
                if j == i:
                    continue
                other = docs[j][1].get(t)
                if other:
                    scores[j] = scores.get(j, 0.0) + w * other
        best = sorted(
            ((s, j) for j, s in scores.items() if s >= threshold),
            key=lambda p: (-p[0], docs[p[1]][0]),
        )[:k]
        for score, j in best:
            a, b = sorted((nid, docs[j][0]))
            if (a, b) in seen:
                continue
            seen.add((a, b))
            links.append({
                "source": a,
                "target": b,
                "is_similarity_link": True,
                "weight": round(min(1.0, score), 3),
            })
    return links


def assign_communities(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    rounds: int = 8,
) -> Dict[str, int]:
    """
    Etiket yayılımı ile topluluk tespiti (networkx'siz, deterministik).

    Louvain modülerlik optimizasyonu daha iyi bölütler verir ama networkx bağımlılığı
    ve ~O(m log n) maliyeti getirir; burada amaç renk tonu üretmek olduğu için
    ağırlıklı etiket yayılımı yeterli. Düğümler kimliğe göre sıralı gezildiğinden
    sonuç her çalıştırmada aynıdır.
    """
    adj: Dict[str, List[Tuple[str, float]]] = {}
    ids = {n["id"] for n in nodes}
    for l in links:
        if l.get("is_catalog_link"):
            continue
        s, t = l.get("source"), l.get("target")
        if s not in ids or t not in ids:
            continue
        w = 2.5 * float(l.get("weight", 1.0)) if l.get("is_similarity_link") else (
            0.6 if l.get("is_tree_link") else 1.0
        )
        adj.setdefault(s, []).append((t, w))
        adj.setdefault(t, []).append((s, w))

    label: Dict[str, str] = {n["id"]: n["id"] for n in nodes}
    order = sorted(ids)
    for _ in range(rounds):
        changed = False
        for nid in order:
            neigh = adj.get(nid)
            if not neigh:
                continue
            tally: Dict[str, float] = {}
            for other, w in neigh:
                lab = label[other]
                tally[lab] = tally.get(lab, 0.0) + w
            best = min(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if best != label[nid]:
                label[nid] = best
                changed = True
        if not changed:
            break

    # Etiketleri küçük tamsayılara indirger (renk tonu için).
    index: Dict[str, int] = {}
    out: Dict[str, int] = {}
    for nid in order:
        lab = label[nid]
        if lab not in index:
            index[lab] = len(index)
        out[nid] = index[lab]
    return out

# Deterministic keywords for virtual taxonomy classification
FINANCIAL_KEYWORDS = [
    "finans", "bilanço", "bilanco", "audit", "risk", "volatilite", "hjm", "black_scholes",
    "sabr", "opsiyon", "kredi", "tahvil", "portfoy", "portföy", "clo", "stoikov", "cfmm",
    "uniswap", "defi", "lbo", "alm", "arbitraj", "varlık", "faiz", "türbülans", "bachelier",
    "heston", "duffie", "merton", "svi", "crypto", "stablecoin", "yield", "curve", "quanto",
    "equity", "hedge", "acharya", "geske", "avellaneda", "bgm", "basel", "bergomi", "cgmy",
    "cir", "cppi", "carr", "cheyette", "cont", "dai", "dupire", "epstein", "faktor", "gsw",
    "gueant", "guyon", "hansen", "hawkes", "jaisson", "jarrow", "kantitatif", "longstaff",
    "malliavin", "margrabe", "merkez", "mikroyapi", "ozel", "pathsignatures", "qrheston",
    "rmt", "svcj", "sektorel", "stokastik", "taylor", "ticaret", "whalley", "wishart",
    "yapilandirilmis", "deleveraging", "sofr", "fama", "macbeth", "leland", "toft", "bouchaud",
    "at1", "rbergomi", "breeden", "ctd", "nav", "zhou", "mbs", "gibson", "schwartz"
]

PDF_KEYWORDS = ["pdf", "eklenen pdf", "dokuman", "döküman", "belge"]

MEDIA_KEYWORDS = ["media", "ajans", "pazarlama", "marketing", "reklam", "kampanya", "sosyal medya"]

AUTONOMOUS_KEYWORDS = [
    "otonom", "autonomous", "agent", "harness", "agentdesks", "a2a", "acp",
    "token fizigi", "token fiziği", "faz", "letta", "openhands", "microkernel",
    "task_or_research", "security audit", "failing autonomous", "supervision"
]


def normalize_slug(text: str) -> str:
    """Normalize text into a clean, deterministic URL-safe and graph-safe slug with Turkish character support."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    normalized = str(text).translate(tr_map).lower().replace("_", "-")
    slug = re.sub(r'[^a-zA-Z0-9\-]', '-', normalized).strip('-')
    slug = re.sub(r'-+', '-', slug)
    return slug if slug else "item"


def classify_report_to_hub(
    title: str,
    path_str: str,
    tags: Optional[List[str]],
    registered_skills: List[str],
    known_projects: List[str]
) -> Tuple[str, str, str]:
    """
    Deterministically classify a report into (parent_hub_id, cluster_id, cluster_group)
    without altering files on disk (Virtual Taxonomy).
    """
    p = Path(path_str)
    parts = p.parts

    # 1. Path-based classification
    if "Projects" in parts:
        idx = parts.index("Projects")
        if len(parts) > idx + 1:
            proj_name = parts[idx + 1]
            slug = normalize_slug(proj_name)
            return f"subhub-project-{slug}", f"project:{slug}", "projects"

    if "Skills" in parts:
        idx = parts.index("Skills")
        if len(parts) > idx + 1:
            skill_name = parts[idx + 1]
            slug = normalize_slug(skill_name)
            return f"subhub-skill-{slug}", f"skill:{slug}", "skills"

    # 2. Tag-based classification
    if tags:
        for t in tags:
            t_str = str(t).strip().lower()
            if t_str.startswith("project:"):
                proj = t_str.split("project:", 1)[1].strip()
                slug = normalize_slug(proj)
                return f"subhub-project-{slug}", f"project:{slug}", "projects"
            if t_str.startswith("skill:"):
                sk = t_str.split("skill:", 1)[1].strip()
                slug = normalize_slug(sk)
                return f"subhub-skill-{slug}", f"skill:{slug}", "skills"
            for sk in registered_skills:
                sk_clean = normalize_slug(sk)
                if t_str == sk_clean or t_str == sk.lower():
                    return f"subhub-skill-{sk_clean}", f"skill:{sk_clean}", "skills"
            for proj in known_projects:
                p_clean = normalize_slug(proj)
                if t_str == p_clean or t_str == proj.lower():
                    return f"subhub-project-{p_clean}", f"project:{p_clean}", "projects"

    # 3. Dynamic match against registered skills
    title_lower = title.lower()
    for sk in registered_skills:
        sk_clean = normalize_slug(sk)
        if sk_clean in title_lower or sk_clean.replace("-", " ") in title_lower:
            return f"subhub-skill-{sk_clean}", f"skill:{sk_clean}", "skills"
        tokens = [tk for tk in sk_clean.split("-") if len(tk) > 3]
        if any(tk in title_lower for tk in tokens):
            return f"subhub-skill-{sk_clean}", f"skill:{sk_clean}", "skills"

    # 4. Specialized keyword taxonomy (check autonomous first so security audits don't get trapped by generic audit keyword)
    if any(k in title_lower for k in AUTONOMOUS_KEYWORDS):
        if "autonomous-agent" in registered_skills:
            return "subhub-skill-autonomous-agent", "skill:autonomous-agent", "skills"
        for sk in registered_skills:
            if "agent" in sk.lower() or "otonom" in sk.lower():
                sk_clean = normalize_slug(sk)
                return f"subhub-skill-{sk_clean}", f"skill:{sk_clean}", "skills"

    if any(k in title_lower for k in FINANCIAL_KEYWORDS):
        for sk in registered_skills:
            if "finan" in sk.lower() or "audit" in sk.lower():
                sk_clean = normalize_slug(sk)
                return f"subhub-skill-{sk_clean}", f"skill:{sk_clean}", "skills"
        return "subhub-skill-financial-auditor", "skill:financial-auditor", "skills"

    if any(k in title_lower for k in PDF_KEYWORDS):
        return "subhub-skill-pdf-analyzer", "skill:pdf-analyzer", "skills"

    if any(k in title_lower for k in MEDIA_KEYWORDS):
        return "subhub-skill-media-agency-soldier", "skill:media-agency-soldier", "skills"

    # 5. Check known projects
    for proj in known_projects:
        p_clean = normalize_slug(proj)
        if p_clean in title_lower or p_clean.replace("-", " ") in title_lower:
            return f"subhub-project-{p_clean}", f"project:{p_clean}", "projects"

    # 6. Fallback: assign to primary project sub-hub
    primary_proj = known_projects[0] if known_projects else "entropiai"
    p_slug = normalize_slug(primary_proj)
    return f"subhub-project-{p_slug}", f"project:{p_slug}", "projects"


def classify_autonomous_subbranch(title: str) -> str:
    """Deterministically assign autonomous agent report to dendritic milestone sub-branch."""
    tl = title.lower()
    m = re.search(r'faz\s*(\d+)', tl)
    if m:
        faz_num = int(m.group(1))
        if faz_num <= 80:
            return "subbranch-agent-faz66-80"
        elif faz_num <= 90:
            return "subbranch-agent-faz81-90"
        else:
            return "subbranch-agent-faz91-104"
    if any(w in tl for w in [
        "desk", "harness", "supervision", "task_or_research",
        "gorev", "görev", "job", "failing autonomous", "security audit"
    ]):
        return "subbranch-agent-desks"
    if any(w in tl for w in ["a2a", "acp", "protokol", "protocol"]):
        return "subbranch-agent-faz81-90"
    return "subbranch-agent-faz66-80"


def classify_financial_subbranch(title: str) -> str:
    """Deterministically assign financial auditor report to dendritic topic sub-branch."""
    tl = title.lower()
    if any(w in tl for w in ["clo", "lbo", "kredi", "tahvil", "credit", "at1"]):
        return "subbranch-fin-clo-credit"
    if any(w in tl for w in ["volatilite", "svi", "sabr", "heston", "opsiyon", "bachelier", "bergomi", "quanto"]):
        return "subbranch-fin-vol-options"
    if any(w in tl for w in ["defi", "uniswap", "cfmm", "arbitraj", "stableswap", "crypto", "stablecoin"]):
        return "subbranch-fin-defi-arb"
    return "subbranch-fin-risk-alm"


def classify_cognitive_semantic_subbranch(content: str) -> str:
    """Deterministically assign cognitive semantic memory to dendritic milestone sub-branch."""
    cl = content.lower()
    if any(k in cl for k in ["memory", "kimlik", "persona", "ego", "kendilik", "kural"]):
        return "subbranch-cog-sem-core"
    if any(k in cl for k in [
        "mimar", "architect", "karar", "decision", "katman", "layer", "protokol",
        "zero-api", "antigravity", "microkernel", "harness", "tasarım", "pattern"
    ]):
        return "subbranch-cog-sem-arch"
    if any(k in cl for k in [
        "bilanço", "bilanco", "finans", "portföy", "portfoy", "kredi", "likidite",
        "oran", "değer yatırım", "buffett", "graham", "risk", "opsiyon", "varlık", "tahvil", "sabr", "faiz", "stokastik"
    ]):
        return "subbranch-cog-sem-finance"
    return "subbranch-cog-sem-research"


def compute_radial_fan_leaf_pos(
    p_x: float,
    p_y: float,
    branch_angle: float,
    count: int,
    base_dist: float = 65.0,
    ring_spacing: float = 48.0,
    span: float = 1.20
) -> tuple[float, float]:
    """
    Computes natural multi-tier radial fan coordinates around parent subbranch.
    Spans nodes across concentric rings (tiers) fanning outward along branch_angle.
    Prevents single-vector straight sticks and guarantees anti-collision spacing.
    """
    k = 0
    cur = count
    while True:
        r_k = base_dist + k * ring_spacing
        arc = r_k * span
        cap = max(3, int(arc / 32.0))
        if cur < cap:
            break
        cur -= cap
        k += 1

    r = base_dist + k * ring_spacing + (5.0 if cur % 2 == 1 else -3.0)
    if cap == 1:
        ang_offset = 0.0
    else:
        ang_offset = -span / 2.0 + cur * (span / (cap - 1))

    total_angle = branch_angle + ang_offset
    leaf_x = round(p_x + r * math.cos(total_angle), 1)
    leaf_y = round(p_y + r * math.sin(total_angle), 1)
    return leaf_x, leaf_y


GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background: #080B10;
            overflow: hidden;
            color: #F0F6FC;
            font-family: 'Segoe UI', Consolas, sans-serif;
            user-select: none;
            width: 100vw;
            height: 100vh;
        }
        #canvas {
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        #legend {
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 11px;
            background: rgba(14, 20, 32, 0.92);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 5px 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            backdrop-filter: blur(6px);
            z-index: 10;
            max-width: calc(100vw - 20px);
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            padding: 2px 5px;
            border-radius: 4px;
            transition: all 0.15s ease;
        }
        .legend-item:hover {
            background: rgba(0, 240, 255, 0.12);
        }
        .legend-item.dimmed {
            opacity: 0.30;
            text-decoration: line-through;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        #controls {
            position: absolute;
            bottom: 12px;
            right: 12px;
            display: flex;
            gap: 6px;
            z-index: 10;
        }
        .ctrl-btn {
            background: rgba(14, 20, 32, 0.92);
            border: 1px solid #1F2B42;
            border-radius: 4px;
            color: #00F0FF;
            font-weight: bold;
            font-size: 13px;
            width: 28px;
            height: 28px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            backdrop-filter: blur(4px);
        }
        .ctrl-btn:hover {
            background: #00F0FF;
            color: #080B10;
            border-color: #00F0FF;
        }
        #infoBox {
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 120px;
            background: rgba(14, 20, 32, 0.95);
            border: 1px solid #00F0FF;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
            color: #F0F6FC;
            display: none;
            z-index: 10;
            backdrop-filter: blur(6px);
        }
    </style>
</head>
<body>
    <div id="legend">
        <div class="legend-item" onclick="toggleCategory('ego', this)"><span class="dot" style="background:#00F0FF;"></span> Çekirdek</div>
        <div class="legend-item" onclick="toggleCategory('hub', this)"><span class="dot" style="background:#79C0FF;"></span> Ana Hublar</div>
        <div class="legend-item" onclick="toggleCategory('project', this)"><span class="dot" style="background:#388BFD;"></span> Projeler</div>
        <div class="legend-item" onclick="toggleCategory('skill', this)"><span class="dot" style="background:#00FF9D;"></span> Yetenekler</div>
        <div class="legend-item" onclick="toggleCategory('subbranch', this)"><span class="dot" style="background:#FF79C6;"></span> Alt Dallar</div>
        <div class="legend-item" onclick="toggleCategory('mcp', this)"><span class="dot" style="background:#F778BA;"></span> MCP</div>
        <div class="legend-item" onclick="toggleCategory('cognitive', this)"><span class="dot" style="background:#7EE787;"></span> Bilişsel Bellek</div>
        <div class="legend-item" onclick="toggleCategory('Reports', this)"><span class="dot" style="background:#FF0055;"></span> Araştırma Raporları</div>
        <div class="legend-item" onclick="toggleCategory('office', this)"><span class="dot" style="background:#FFB000;"></span> 🏢 Ofisler</div>
        <div class="legend-item" onclick="toggleCategory('agent', this)"><span class="dot" style="background:#2DD4BF;"></span> 🤖 Ajanlar</div>
        <div class="legend-item" onclick="toggleCategory('query', this)"><span class="dot" style="background:#C792EA;"></span> 🔎 Sorgular & Ofis Raporları</div>
        <div class="legend-item" onclick="toggleCategory('hub-offices', this)"><span class="dot" style="background:#FFC94D;"></span> 🏢 Ofis Kümesi</div>
        <div class="legend-item" onclick="toggleCategory('concept', this)"><span class="dot" style="background:#9BE9A8;"></span> 📗 Kavramlar</div>
        <div class="legend-item" onclick="toggleCategory('entity', this)"><span class="dot" style="background:#8CC8FF;"></span> 🏷 Varlıklar</div>
    </div>
    <div id="controls">
        <button class="ctrl-btn" onclick="zoomIn()" title="Yakınlaştır">+</button>
        <button class="ctrl-btn" onclick="zoomOut()" title="Uzaklaştır">-</button>
        <button class="ctrl-btn" onclick="resetView()" title="Görünümü Sığdır / Sıfırla">⟲</button>
    </div>
    <div id="infoBox"></div>
    <canvas id="canvas"></canvas>

    <script>
        window.onerror = function(msg, url, line) {
            console.error("Canvas Graph Error: " + msg + " line " + line);
            const box = document.getElementById('infoBox');
            if (box) {
                box.style.display = 'block';
                box.style.borderColor = '#FF4D4D';
                box.innerHTML = "Hafıza Haritası Hatası: " + msg;
            }
        };

        const nodes = __NODES__;
        const links = __LINKS__;
        let currentScope = "__INITIAL_SCOPE__";
        const activeProjectSlug = "__ACTIVE_PROJECT_SLUG__";

        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const infoBox = document.getElementById('infoBox');

        let width = 600;
        let height = 400;

        const nodeMap = new Map();
        nodes.forEach(n => {
            nodeMap.set(n.id, n);
            if (n.name && !nodeMap.has(n.name)) nodeMap.set(n.name, n);
        });

        links.forEach(l => {
            l.sourceNode = nodeMap.get(l.source);
            l.targetNode = nodeMap.get(l.target);
            if (!l.sourceNode && typeof l.source === 'string') {
                l.sourceNode = nodes.find(n => n.name === l.source || n.id.includes(l.source));
            }
            if (!l.targetNode && typeof l.target === 'string') {
                l.targetNode = nodes.find(n => n.name === l.target || n.id.includes(l.target));
            }
        });

        let zoom = 1.0;
        let panX = 0;
        let panY = 0;
        // Yükleme sırasındaki sığdırma fizik açılmadan çalışır; ağaç sonradan
        // genişleyince görünüm bir köşede kalıyordu. Benzetim durulunca bir kez
        // daha sığdırılır — kullanıcı o arada yakınlaştırdı/kaydırdıysa dokunulmaz.
        let userAdjustedView = false;
        let settledFitDone = false;
        let isPanning = false;
        let panStartX = 0;
        let panStartY = 0;

        const activeCategories = {
            'ego': true,
            'hub': true,
            'project': true,
            'skill': true,
            'subbranch': true,
            'mcp': true,
            'mcp-tool': true,
            'cognitive': true,
            'semantic': true,
            'episodic': true,
            'procedural': true,
            'Reports': true,
            'obsidian': true,
            'DailyNotes': true,
            'office': true,
            'agent': true,
            'query': true,
            // Faz 4: bellek ajani bu gruplari veri tarafinda uretiyor.
            // 'hub-offices' ofis kumesinin govde dugumu; 'concept' ve 'entity'
            // bilissel bellekten cikan kavram/varlik yapraklari.
            'hub-offices': true,
            'concept': true,
            'entity': true
        };

        // Rapor kümesi açma/kapama düğümü YOKTUR. Tüm yapraklar her zaman
        // görünür; tıklama yalnızca seçim yapar, yerleşimi yeniden kurmaz.
        function isNodeVisible(n) {
            if (!n) return false;
            return isCategoryActive(n.group);
        }

        function isCategoryActive(group) {
            if (!group) return true;
            if (group === 'subbranch') {
                if (activeCategories['skill'] === false) return false;
            }
            if (group === 'semantic' || group === 'episodic' || group === 'procedural') {
                if (activeCategories['cognitive'] === false) return false;
            }
            if (group === 'mcp-tool') {
                if (activeCategories['mcp'] === false) return false;
            }
            if (group === 'DailyNotes' || group === 'obsidian') {
                if (activeCategories['cognitive'] === false) return false;
            }
            return activeCategories[group] !== false;
        }

        function isNodeInScope(n) {
            if (!n) return false;
            if (currentScope === 'all') return true;
            if (n.group === 'ego') return true;

            if (currentScope === 'active_project' || currentScope.startsWith('project:')) {
                const targetSlug = (currentScope === 'active_project') ? activeProjectSlug : currentScope.replace('project:', '');
                if (n.id === 'hub-projects') return true;
                if (n.cluster === 'project:' + targetSlug || n.id === 'subhub-project-' + targetSlug) return true;
                if (n.parent_hub === 'subhub-project-' + targetSlug) return true;
                return false;
            }

            if (currentScope === 'all_skills') {
                if (n.id === 'hub-skills') return true;
                if (n.cluster_group === 'skills' || n.group === 'skill' || n.group === 'subbranch' || (n.parent_hub && (n.parent_hub.startsWith('subhub-skill-') || n.parent_hub.startsWith('subbranch-')))) return true;
                return false;
            }

            if (currentScope.startsWith('skill:')) {
                const targetSkill = currentScope.replace('skill:', '');
                const targetSubhub = 'subhub-skill-' + targetSkill;
                if (n.id === 'hub-skills') return true;
                if (n.id === targetSubhub || n.cluster === 'skill:' + targetSkill) return true;
                if (n.parent_hub === targetSubhub || (n.cluster && n.cluster === 'skill:' + targetSkill)) return true;
                return false;
            }

            if (currentScope === 'all_mcp') {
                if (n.id === 'hub-mcp') return true;
                if (n.cluster_group === 'mcp' || n.group === 'mcp' || n.group === 'mcp-tool' || (n.parent_hub && n.parent_hub.startsWith('subhub-mcp-'))) return true;
                return false;
            }

            if (currentScope === 'all_offices') {
                if (n.id === 'hub-offices') return true;
                if (n.cluster_group === 'offices' || n.group === 'office' || n.group === 'agent') return true;
                // Ofise bagli sorgu sayfalari (ofis raporlari) da odakta kalir.
                if (n.group === 'query' && n.parent_hub && n.parent_hub.startsWith('office/')) return true;
                return false;
            }

            if (currentScope === 'all_cognitive') {
                if (n.id === 'hub-cognitive') return true;
                if (n.cluster_group === 'cognitive' || ['semantic', 'episodic', 'procedural', 'DailyNotes'].includes(n.group) || (n.parent_hub && (n.parent_hub.startsWith('subhub-cog-') || n.parent_hub.startsWith('subbranch-cog-')))) return true;
                return false;
            }

            return true;
        }

        let isIsolated = false;
        function setIsolationMode(val) {
            isIsolated = !!val;
            userAdjustedView = false;
            relayoutAndFit(1.0, true);
        }

        function setScope(newScope) {
            // Odak değişince aynı radyal kural seçili dal için uygulanır:
            // kapsam dışı düğümler düzenden çıkar, seçili dal tüm çemberi kaplar.
            currentScope = newScope;
            userAdjustedView = false;
            relayoutAndFit(1.0, true);
        }

        let isRendering = false;
        function requestRender() {
            if (!isRendering) {
                isRendering = true;
                requestAnimationFrame(render);
            }
        }

        function toggleCategory(cat, el) {
            const newState = !activeCategories[cat];
            activeCategories[cat] = newState;
            el.classList.toggle('dimmed', !newState);
            // Kategori kapanınca kalan düğümler boşluğu organik olarak doldurur;
            // görünüm sıçramasın diye yeniden sığdırma yapılmaz.
            relayoutAndFit(0.5, false);
        }

        function updateDimensions() {
            // Kanvasın kendi ölçüsü hesaba katılmaz: bir kez büyüyünce clientWidth
            // o değerde kalıyor ve panel küçülünce sığdırma eski büyük kanvasa göre
            // yapılıp grafik sağ altta minik kalıyordu.
            width = canvas.width = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0, 300);
            height = canvas.height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0, 250);
            requestRender();
        }
        // Panel yeniden boyutlanınca (Zen penceresi açılışta büyükten küçülür) yalnızca
        // kanvas ölçüsü değil, sığdırma da yenilenir; kullanıcı görünümü elle
        // ayarladıysa dokunulmaz.
        let resizeTimer = null;
        window.addEventListener('resize', () => {
            updateDimensions();
            if (resizeTimer) clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                resizeTimer = null;
                relayoutGraph();
                if (!userAdjustedView) fitToView();
            }, 150);
        });
        updateDimensions();

        const colors = {
            'ego': '#00F0FF',
            'hub': '#79C0FF',
            'project': '#388BFD',
            'skill': '#00FF9D',
            'subbranch': '#FF79C6',
            'mcp': '#F778BA',
            'mcp-tool': '#D2A8FF',
            'cognitive': '#7EE787',
            'semantic': '#7EE787',
            'episodic': '#FFB300',
            'procedural': '#58A6FF',
            'Reports': '#FF0055',
            'DailyNotes': '#E3B341',
            'obsidian': '#BC8CFF',
            'office': '#FFB000',
            'agent': '#2DD4BF',
            'query': '#C792EA',
            'hub-offices': '#FFC94D',
            'concept': '#9BE9A8',
            'entity': '#8CC8FF'
        };

        // Grup ikonlari: efsanedeki dizgeyle ayni. Ikon yalnizca ofis/ajan/sorgu
        // gibi yapisal dugumlerde cizilir; yuzlerce rapor yapraginda emoji
        // cizmek kare suresini gereksiz yere buyutur.
        const groupIcons = {
            'office': '🏢',
            'agent': '🤖',
            'query': '🔎',
            'hub-offices': '🏢',
            'concept': '📗',
            'entity': '🏷'
        };

        function getNodeIcon(group) {
            return groupIcons[group] || '';
        }

        function getNodeColor(group) {
            return colors[group] || '#79C0FF';
        }

        // Topluluk tonu: etiket yayılımıyla bulunan topluluklar altın açı ile
        // ayrık renk tonlarına eşlenir. Yalnızca hale/benzerlik kenarı boyanır;
        // düğümün çekirdek rengi grup rengidir (efsane geçerli kalsın).
        function communityTint(n, a) {
            const c = (typeof n.community === 'number') ? n.community : 0;
            const hue = (c * 137.508) % 360;
            return 'hsla(' + hue.toFixed(1) + ', 72%, 62%, ' + a + ')';
        }

        // ⟲ düğmesi: kullanıcı görünümü elle değiştirmiş olsa da sıfırlar.
        function resetView() {
            userAdjustedView = false;
            fitToView();
        }

        // ---- Organik kuvvet yerleşimi (çevrimdışı d3-force eşleniği) ----
        //
        // Eski radyal sektör motoru kaldırıldı: her düğümü önceden hesaplanmış bir
        // açı/halka noktasına yapıştırdığı için grafik "yapay" görünüyordu. Yerine
        // Obsidian graph view'ün de kullandığı kuvvet yönelimli yaklaşım geldi:
        //
        //   * yay (link):     bağ türüne göre farklı hedef uzunluk ve sertlik
        //   * itme (charge):  Barnes-Hut dörtlü ağacı ile O(n log n)
        //   * çakışma:        tek tip ızgara üzerinden O(n)
        //   * merkeze çekim:  kopuk bileşenler uzaya savrulmasın diye çok zayıf
        //
        // Konumlar tohumlu bir sözde-rastgele dizinden üretilir; gerçek rastgelelik
        // hiçbir yerde kullanılmaz, yani her açılışta aynı yerleşim çıkar. Benzetim
        // durulunca (alpha < alphaMin) tamamen durur ve kare çizilmez.

        function hashSeed(str) {
            let h = 2166136261 >>> 0;
            for (let i = 0; i < str.length; i++) {
                h ^= str.charCodeAt(i);
                h = Math.imul(h, 16777619) >>> 0;
            }
            return h >>> 0;
        }

        function mulberry32(a) {
            return function () {
                a |= 0; a = (a + 0x6D2B79F5) | 0;
                let t = Math.imul(a ^ (a >>> 15), 1 | a);
                t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
                return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
            };
        }

        // Bağ türüne göre yay parametreleri. Ağaç bağı zayıftır (hiyerarşi
        // görünsün ama yerleşimi dikte etmesin), wikilink orta, gömme/başlık
        // benzerliği en güçlüsüdür: benzer raporlar birbirine yapışır.
        const LINK_KINDS = {
            tree: { distance: 120, strength: 0.10 },
            wikilink: { distance: 95, strength: 0.22 },
            similarity: { distance: 46, strength: 0.55 }
        };

        function linkKind(l) {
            if (l.is_similarity_link) return 'similarity';
            if (l.is_tree_link) return 'tree';
            return 'wikilink';
        }

        const CHARGE = -230;         // Düğüm başına itme katsayısı
        const THETA2 = 0.81;         // Barnes-Hut (0.9^2)
        const CENTER_PULL = 0.010;   // Merkeze çok zayıf çekim
        const VELOCITY_DECAY = 0.42;

        let simLinks = [];           // Fizikte kullanılan (görünür) kenarlar
        let simNodes = [];           // Fizikte kullanılan (görünür) düğümler
        let simDirty = true;

        let positionsInitialized = false;
        function initNodePositions() {
            if (positionsInitialized) return;
            const cx = width / 2;
            const cy = height / 2;

            nodes.forEach(n => {
                n.vx = 0;
                n.vy = 0;
                if (n.group === 'ego') {
                    n.x = cx; n.y = cy;
                    return;
                }
                if (typeof n.x === 'number' && typeof n.y === 'number' && (n.x !== 0 || n.y !== 0)) {
                    // Python tarafı deterministik bir tohum konumu üretir; kuvvet
                    // benzetimi bunu organik yerleşime dönüştürür.
                    n.x = cx + n.x;
                    n.y = cy + n.y;
                } else {
                    const h = hashSeed(n.id);
                    const rnd = mulberry32(h);
                    const ang = rnd() * Math.PI * 2;
                    const r = 140 + rnd() * 420;
                    n.x = cx + Math.cos(ang) * r;
                    n.y = cy + Math.sin(ang) * r;
                }
                // Tohumlu, deterministik mikro sarsıntı: tam üst üste binen
                // düğümler itme kuvvetinde sıfıra bölünmesin.
                const j = mulberry32(hashSeed(n.id + '|j'));
                n.x += (j() - 0.5) * 1.5;
                n.y += (j() - 0.5) * 1.5;
            });

            links.forEach(l => {
                l.sourceNode = nodeMap.get(l.source);
                l.targetNode = nodeMap.get(l.target);
            });

            positionsInitialized = true;
        }

        // Görünür düğüm/kenar kümesini ve yay katsayılarını tazeler.
        // d3-force'taki gibi yay sertliği düğüm derecesine göre normalize edilir:
        // 300 çocuklu bir hub, tek bir yaprak tarafından savrulmaz.
        function rebuildSimulation() {
            simNodes = [];
            const inSet = new Set();
            for (let i = 0; i < nodes.length; i++) {
                const n = nodes[i];
                if (!isNodeVisible(n)) continue;
                if (!isNodeInScope(n) && (isIsolated || currentScope !== 'all')) continue;
                simNodes.push(n);
                inSet.add(n.id);
                n._charge = CHARGE * ((n.val || 12) / 12);
            }

            const degree = new Map();
            const cand = [];
            for (let i = 0; i < links.length; i++) {
                const l = links[i];
                if (l.is_catalog_link) continue;
                const s = l.sourceNode, t = l.targetNode;
                if (!s || !t || s === t) continue;
                if (!inSet.has(s.id) || !inSet.has(t.id)) continue;
                degree.set(s.id, (degree.get(s.id) || 0) + 1);
                degree.set(t.id, (degree.get(t.id) || 0) + 1);
                cand.push(l);
            }
            simLinks = cand;
            for (let i = 0; i < simLinks.length; i++) {
                const l = simLinks[i];
                const kind = LINK_KINDS[linkKind(l)];
                const w = (l.is_similarity_link && typeof l.weight === 'number') ? Math.max(0.3, l.weight) : 1;
                const ds = degree.get(l.sourceNode.id) || 1;
                const dt = degree.get(l.targetNode.id) || 1;
                l._k = (kind.strength * w) / Math.min(ds, dt);
                l._len = kind.distance + (l.sourceNode.val || 12) + (l.targetNode.val || 12);
                l._bias = ds / (ds + dt);
            }
            simDirty = false;
        }

        // ---- Barnes-Hut dörtlü ağacı ----
        function buildQuadtree(list) {
            if (list.length === 0) return null;
            let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.x < x0) x0 = p.x;
                if (p.x > x1) x1 = p.x;
                if (p.y < y0) y0 = p.y;
                if (p.y > y1) y1 = p.y;
            }
            const w = Math.max(x1 - x0, y1 - y0, 1);
            return subdivide(list, x0, y0, x0 + w, y0 + w, 0);
        }

        function subdivide(pts, x0, y0, x1, y1, depth) {
            let q = 0, sx = 0, sy = 0, wsum = 0;
            for (let i = 0; i < pts.length; i++) {
                const p = pts[i];
                const c = Math.abs(p._charge || 1);
                q += (p._charge || 0);
                sx += p.x * c; sy += p.y * c; wsum += c;
            }
            const node = {
                x0: x0, y0: y0, x1: x1, y1: y1,
                q: q,
                cx: wsum > 0 ? sx / wsum : (x0 + x1) / 2,
                cy: wsum > 0 ? sy / wsum : (y0 + y1) / 2,
                kids: null, pts: null
            };
            if (pts.length <= 2 || depth >= 18 || (x1 - x0) < 1) {
                node.pts = pts;
                return node;
            }
            const mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
            const b = [[], [], [], []];
            for (let i = 0; i < pts.length; i++) {
                const p = pts[i];
                b[(p.x >= mx ? 1 : 0) + (p.y >= my ? 2 : 0)].push(p);
            }
            node.kids = [
                b[0].length ? subdivide(b[0], x0, y0, mx, my, depth + 1) : null,
                b[1].length ? subdivide(b[1], mx, y0, x1, my, depth + 1) : null,
                b[2].length ? subdivide(b[2], x0, my, mx, y1, depth + 1) : null,
                b[3].length ? subdivide(b[3], mx, my, x1, y1, depth + 1) : null
            ];
            return node;
        }

        function applyCharge(node, p, k) {
            if (!node) return;
            const dx = node.cx - p.x;
            const dy = node.cy - p.y;
            let d2 = dx * dx + dy * dy;
            const w = node.x1 - node.x0;
            if (node.kids && (w * w) < THETA2 * d2) {
                if (d2 < 25) d2 = 25;
                const f = node.q * k / d2;
                p.vx += dx * f;
                p.vy += dy * f;
                return;
            }
            if (node.kids) {
                applyCharge(node.kids[0], p, k);
                applyCharge(node.kids[1], p, k);
                applyCharge(node.kids[2], p, k);
                applyCharge(node.kids[3], p, k);
                return;
            }
            const list = node.pts;
            for (let i = 0; i < list.length; i++) {
                const o = list[i];
                if (o === p) continue;
                const ddx = o.x - p.x, ddy = o.y - p.y;
                let dd = ddx * ddx + ddy * ddy;
                if (dd < 25) dd = 25;
                const f = (o._charge || 0) * k / dd;
                p.vx += ddx * f;
                p.vy += ddy * f;
            }
        }

        // ---- Izgara tabanlı çakışma çözümü (O(n)) ----
        function resolveCollisions(list) {
            let maxR = 12;
            for (let i = 0; i < list.length; i++) {
                const r = (list[i].val || 12) + 2;
                if (r > maxR) maxR = r;
            }
            const cell = maxR * 2;
            const grid = new Map();
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                const gx = Math.floor(p.x / cell), gy = Math.floor(p.y / cell);
                const key = gx + ',' + gy;
                let b = grid.get(key);
                if (!b) { b = []; grid.set(key, b); }
                b.push(p);
            }
            grid.forEach((bucket, key) => {
                const parts = key.split(',');
                const gx = parseInt(parts[0], 10), gy = parseInt(parts[1], 10);
                for (let ox = 0; ox <= 1; ox++) {
                    for (let oy = (ox === 0 ? 0 : -1); oy <= 1; oy++) {
                        const other = (ox === 0 && oy === 0) ? bucket : grid.get((gx + ox) + ',' + (gy + oy));
                        if (!other) continue;
                        for (let i = 0; i < bucket.length; i++) {
                            const a = bucket[i];
                            const jStart = (other === bucket) ? i + 1 : 0;
                            for (let j = jStart; j < other.length; j++) {
                                const b2 = other[j];
                                if (a === b2) continue;
                                let dx = b2.x - a.x, dy = b2.y - a.y;
                                let d = Math.sqrt(dx * dx + dy * dy);
                                const rmin = (a.val || 12) + (b2.val || 12) + 3;
                                if (d >= rmin) continue;
                                if (d < 0.01) { dx = 1; dy = 0; d = 1; }
                                const push = ((rmin - d) / d) * 0.5;
                                const px = dx * push, py = dy * push;
                                if (a.group !== 'ego' && a !== draggedNode) { a.x -= px; a.y -= py; }
                                if (b2.group !== 'ego' && b2 !== draggedNode) { b2.x += px; b2.y += py; }
                            }
                        }
                    }
                }
            });
        }

        // Görünürlük/kapsam değişimlerinde benzetim yeniden ısıtılır. Yerleşim
        // sıfırdan kurulmaz: düğümler bulundukları yerden organik olarak akar.
        function relayoutGraph() {
            simDirty = true;
            rebuildSimulation();
        }

        // refit=false ise görünüm kullanıcının bıraktığı yerde kalır: sığdırma
        // yalnızca yüklemede, Odak değişiminde ve kullanıcı ⟲ düğmesine bastığında
        // yapılır (kategori açıp kapatmak ekranı zıplatmasın).
        function relayoutAndFit(alphaKick, refit) {
            relayoutGraph();
            alpha = Math.max(alpha, alphaKick || 0.6);
            settledFitDone = !refit;
            requestRender();
        }

        let alpha = 1.0;
        const alphaMin = 0.008;
        const alphaDecay = 0.020;

        function tickPhysics() {
            if (isPanning) return;
            if (alpha < alphaMin && !draggedNode) return;
            if (simDirty) rebuildSimulation();

            const cx = width / 2;
            const cy = height / 2;

            const egoNode = nodeMap.get('ego-entropy-core');
            if (egoNode && egoNode !== draggedNode) {
                egoNode.x = cx;
                egoNode.y = cy;
                egoNode.vx = 0;
                egoNode.vy = 0;
            }

            const list = simNodes;
            if (list.length === 0) { alpha *= (1 - alphaDecay); return; }

            // 1. Yaylar (link force) — d3'teki gibi konum üzerinden, iki uca bias'lı.
            for (let i = 0; i < simLinks.length; i++) {
                const l = simLinks[i];
                const s = l.sourceNode, t = l.targetNode;
                let dx = (t.x + t.vx) - (s.x + s.vx);
                let dy = (t.y + t.vy) - (s.y + s.vy);
                let d = Math.sqrt(dx * dx + dy * dy);
                if (d < 0.01) { dx = 0.5; dy = 0.5; d = 0.71; }
                const f = ((d - l._len) / d) * alpha * l._k;
                const fx = dx * f, fy = dy * f;
                if (t.group !== 'ego' && t !== draggedNode) { t.vx -= fx * l._bias; t.vy -= fy * l._bias; }
                if (s.group !== 'ego' && s !== draggedNode) { s.vx += fx * (1 - l._bias); s.vy += fy * (1 - l._bias); }
            }

            // 2. Karşılıklı itme (Barnes-Hut): 1000 düğümde ~10 bin işlem/kare.
            const tree = buildQuadtree(list);
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.group === 'ego' || p === draggedNode) continue;
                applyCharge(tree, p, alpha);
            }

            // 3. Merkeze zayıf çekim: benzerlik kenarı olmayan yapraklar sonsuza gitmesin.
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.group === 'ego' || p === draggedNode) continue;
                p.vx += (cx - p.x) * CENTER_PULL * alpha;
                p.vy += (cy - p.y) * CENTER_PULL * alpha;
            }

            // 4. Konum güncellemesi (Verlet, hız sönümlü).
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.group === 'ego' || p === draggedNode) { p.vx = 0; p.vy = 0; continue; }
                p.vx *= (1 - VELOCITY_DECAY);
                p.vy *= (1 - VELOCITY_DECAY);
                if (p.vx > 40) p.vx = 40; else if (p.vx < -40) p.vx = -40;
                if (p.vy > 40) p.vy = 40; else if (p.vy < -40) p.vy = -40;
                p.x += p.vx;
                p.y += p.vy;
            }

            // 5. Çakışma: düğümler üst üste binmesin (etiket okunurluğu için şart).
            resolveCollisions(list);

            alpha *= (1 - alphaDecay);
        }

        let hoveredNode = null;
        let draggedNode = null;
        let isDragging = false;
        let startX = 0, startY = 0;

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            userAdjustedView = true;
            const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
            const newZoom = Math.max(0.05, Math.min(4.5, zoom * zoomFactor));

            panX = mx - (mx - panX) * (newZoom / zoom);
            panY = my - (my - panY) * (newZoom / zoom);
            zoom = newZoom;
            if (isPanning) {
                panStartX = e.clientX - panX;
                panStartY = e.clientY - panY;
            }
            requestRender();
        }, { passive: false });

        canvas.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });

        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            // Middle or right click always pans
            if (e.button === 1 || e.button === 2) {
                isPanning = true;
                panStartX = e.clientX - panX;
                panStartY = e.clientY - panY;
                canvas.style.cursor = 'grabbing';
                userAdjustedView = true;
                requestRender();
                return;
            }

            if (hoveredNode && isNodeInScope(hoveredNode) && (!isIsolated || currentScope === 'all')) {
                draggedNode = hoveredNode;
                startX = mx;
                startY = my;
                isDragging = false;
                alpha = 0.35;
            } else {
                isPanning = true;
                panStartX = e.clientX - panX;
                panStartY = e.clientY - panY;
                canvas.style.cursor = 'grabbing';
            }
            requestRender();
        });

        function handleMouseMove(e) {
            if (isPanning) {
                panX = e.clientX - panStartX;
                panY = e.clientY - panStartY;
                requestRender();
                return;
            }

            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (draggedNode) {
                const distMoved = Math.hypot(mx - startX, my - startY);
                if (distMoved > 4) {
                    isDragging = true;
                    const wx = (mx - panX) / zoom;
                    const wy = (my - panY) / zoom;
                    draggedNode.x = wx;
                    draggedNode.y = wy;
                    alpha = 0.25;
                }
                requestRender();
                return;
            }

            const wx = (mx - panX) / zoom;
            const wy = (my - panY) / zoom;
            const prevHovered = hoveredNode;
            hoveredNode = null;

            for (let i = nodes.length - 1; i >= 0; i--) {
                const n = nodes[i];
                if (!isNodeVisible(n)) continue;
                if (!isNodeInScope(n) && (isIsolated || currentScope !== 'all')) continue;
                const r = n.val || 12;
                const dx = n.x - wx;
                const dy = n.y - wy;
                if (dx * dx + dy * dy < (r + 3) * (r + 3)) {
                    hoveredNode = n;
                    break;
                }
            }

            if (hoveredNode !== prevHovered) {
                requestRender();
            }

            if (hoveredNode) {
                canvas.style.cursor = 'pointer';
                infoBox.style.display = 'block';
                const col = getNodeColor(hoveredNode.group);
                let extraBadge = '';
                if (hoveredNode.id.includes('MEMORY') || hoveredNode.id.includes('BELLEK_HARITASI')) {
                    extraBadge = `<br/><span style="display:inline-block; margin-top:4px; padding:2px 8px; background:rgba(255, 170, 0, 0.15); border:1px solid #FFAA00; border-radius:4px; color:#FFAA00; font-size:10px; font-weight:600;">📑 İndeks Kataloğu (Görsel karmaşayı önlemek için 200+ indeks çizgisi gizlendi)</span>`;
                }
                infoBox.innerHTML = `<b style="color:${col}; font-size:13px;">${hoveredNode.name}</b> <span style="color:#8B949E; font-size:11px;">[${hoveredNode.group}]</span> <span style="color:#00FF9D; font-size:11px; margin-left:8px;">(Detayları Açmak İçin Tıkla)</span>${extraBadge}<br/><span style="color:#C9D1D9; font-size:11px; line-height:1.4;">${hoveredNode.info || ''}</span>`;
            } else {
                canvas.style.cursor = isPanning ? 'grabbing' : 'default';
                infoBox.style.display = 'none';
            }
        }

        window.addEventListener('mousemove', handleMouseMove);

        function handleMouseUp(e) {
            if (draggedNode && !isDragging && (!e || e.button === 0)) {
                const url = 'entropy-node://select?id=' + encodeURIComponent(draggedNode.id);
                window.location.href = url;
            }
            draggedNode = null;
            isDragging = false;
            isPanning = false;
            if (canvas) {
                canvas.style.cursor = hoveredNode ? 'pointer' : 'default';
            }
            requestRender();
        }

        window.addEventListener('mouseup', handleMouseUp);
        window.addEventListener('blur', () => {
            isPanning = false;
            draggedNode = null;
            isDragging = false;
            requestRender();
        });

        function zoomIn() {
            const cx = width / 2;
            const cy = height / 2;
            const newZoom = Math.min(4.5, zoom * 1.25);
            userAdjustedView = true;
            panX = cx - (cx - panX) * (newZoom / zoom);
            panY = cy - (cy - panY) * (newZoom / zoom);
            zoom = newZoom;
            if (isPanning) {
                panStartX = cx - panX;
                panStartY = cy - panY;
            }
            requestRender();
        }

        function zoomOut() {
            const cx = width / 2;
            const cy = height / 2;
            const newZoom = Math.max(0.05, zoom / 1.25);
            userAdjustedView = true;
            panX = cx - (cx - panX) * (newZoom / zoom);
            panY = cy - (cy - panY) * (newZoom / zoom);
            zoom = newZoom;
            if (isPanning) {
                panStartX = cx - panX;
                panStartY = cy - panY;
            }
            requestRender();
        }

        function fitToView() {
            if (isPanning) return;
            // Sığdırma her zaman güncel panel ölçüsüne göre.
            width = canvas.width = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0, 300);
            height = canvas.height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0, 250);
            const targetNodes = nodes.filter(n => isNodeVisible(n) && isNodeInScope(n));
            if (targetNodes.length === 0) return;

            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            targetNodes.forEach(n => {
                if (n.x < minX) minX = n.x;
                if (n.x > maxX) maxX = n.x;
                if (n.y < minY) minY = n.y;
                if (n.y > maxY) maxY = n.y;
            });

            const spanX = Math.max(100, maxX - minX + 100);
            const spanY = Math.max(100, maxY - minY + 100);

            const scaleX = width / spanX;
            const scaleY = height / spanY;
            zoom = Math.max(0.05, Math.min(1.85, Math.min(scaleX, scaleY) * 0.88));

            const midX = (minX + maxX) / 2;
            const midY = (minY + maxY) / 2;
            panX = width / 2 - midX * zoom;
            panY = height / 2 - midY * zoom;
            requestRender();
        }

        // Çakışan etiketler: aynı karede daha önce çizilen etiketlerin ekran dikdörtgenleri.
        // Düğümler düzey sırasıyla gelir (çekirdek, dallar, yapraklar); önce gelen kazanır.
        let placedLabels = [];

        function render() {
            isRendering = false;
            tickPhysics();
            placedLabels = [];

            ctx.save();
            if (typeof ctx.clearRect === 'function') {
                ctx.clearRect(0, 0, width, height);
            }
            ctx.fillStyle = '#080B10';
            ctx.fillRect(0, 0, width, height);

            ctx.translate(panX, panY);
            ctx.scale(zoom, zoom);

            // 1. Draw Links with Organic Bézier Synapses (Decoupled from Catalog Index Spiderwebs)
            const bgLinks = [];
            const treeLinks = [];      // Ana dal/gövde kenarları: hafif eğri
            const leafLinks = [];      // Yaprak kenarları: düz ve ince
            const semanticLinks = [];
            const similarityLinks = [];   // Yakınlık (k-NN) kenarları: her zaman soluk çizilir
            // Gövde = çekirdekten çıkan ya da bir dal/küme düğümüne giden kenar.
            const TRUNK_TARGETS = { 'hub': 1, 'project': 1, 'skill': 1, 'mcp': 1, 'subbranch': 1, 'office': 1, 'agent': 1 };

            links.forEach(l => {
                if (l.is_catalog_link) return; // Completely hide catalog index spiderwebs!
                const s = l.sourceNode;
                const t = l.targetNode;
                if (!s || !t) return;
                if (!isNodeVisible(s) || !isNodeVisible(t)) return;

                const sInScope = isNodeInScope(s);
                const tInScope = isNodeInScope(t);
                const bothInScope = sInScope && tInScope;

                if (!bothInScope) {
                    // Kapsam dışı arka plan kenarları yalnızca yakınlaşınca çizilir;
                    // uzaktan bakışta yüzlerce soluk çizgi yalnızca gürültü ekliyordu.
                    if ((!isIsolated || currentScope === 'all') && zoom >= 1.0) {
                        bgLinks.push(l);
                    }
                } else if (s !== hoveredNode && t !== hoveredNode) {
                    if (l.is_similarity_link) {
                        similarityLinks.push(l);
                    } else if (l.is_tree_link) {
                        if (TRUNK_TARGETS[t.group] || s.group === 'ego') treeLinks.push(l);
                        else leafLinks.push(l);
                    } else if (zoom >= 1.35) {
                        // Anlamsal çapraz bağlantılar (wikilink) detay düzeyidir: ağaç
                        // yapısı okunabilsin diye yalnızca yakınlaşınca ya da üzerine
                        // gelinince gösterilir.
                        semanticLinks.push(l);
                    }
                }
            });

            function drawCurvedLink(s, t, curvFactor) {
                ctx.moveTo(s.x, s.y);
                const dx = t.x - s.x;
                const dy = t.y - s.y;
                const dist = Math.hypot(dx, dy);
                if (dist > 3 && typeof ctx.quadraticCurveTo === 'function') {
                    let nx = -dy / dist;
                    let ny = dx / dist;
                    const mx = (s.x + t.x) * 0.5;
                    const my = (s.y + t.y) * 0.5;
                    if (mx * nx + my * ny < 0) { nx = -nx; ny = -ny; }
                    const h = Math.min(26.0, dist * curvFactor);
                    ctx.quadraticCurveTo(mx + nx * h, my + ny * h, t.x, t.y);
                } else {
                    ctx.lineTo(t.x, t.y);
                }
            }

            // Inactive / Out-of-Scope Background Links
            if (bgLinks.length > 0) {
                ctx.lineWidth = 0.8;
                ctx.strokeStyle = 'rgba(31, 43, 66, 0.10)';
                ctx.beginPath();
                for (let i = 0; i < bgLinks.length; i++) {
                    const l = bgLinks[i];
                    drawCurvedLink(l.sourceNode, l.targetNode, 0.08);
                }
                ctx.stroke();
            }

            // Yakınlık kenarları: benzer raporları birbirine bağlayan kısa, soluk
            // çizgiler. Topluluk tonuyla boyanır; grafiğin "organik doku"su budur.
            if (similarityLinks.length > 0) {
                ctx.lineWidth = 0.7;
                for (let i = 0; i < similarityLinks.length; i++) {
                    const l = similarityLinks[i];
                    ctx.strokeStyle = communityTint(l.sourceNode, 0.22);
                    ctx.beginPath();
                    ctx.moveTo(l.sourceNode.x, l.sourceNode.y);
                    ctx.lineTo(l.targetNode.x, l.targetNode.y);
                    ctx.stroke();
                }
            }

            // Semantic Cross-References (Genuine Wikilinks between reports) - Soft Violet Dashes
            if (semanticLinks.length > 0) {
                ctx.lineWidth = 1.1;
                ctx.strokeStyle = 'rgba(167, 139, 250, 0.40)';
                if (typeof ctx.setLineDash === 'function') ctx.setLineDash([4, 4]);
                ctx.beginPath();
                for (let i = 0; i < semanticLinks.length; i++) {
                    const l = semanticLinks[i];
                    drawCurvedLink(l.sourceNode, l.targetNode, 0.12);
                }
                ctx.stroke();
                if (typeof ctx.setLineDash === 'function') ctx.setLineDash([]);
            }

            // Yaprak kenarları: düz, ince — sektör içinde kısa kaldıkları için
            // eğri gerekmez ve düz çizgi ağacın okunurluğunu artırır.
            if (leafLinks.length > 0) {
                ctx.lineWidth = 0.9;
                ctx.strokeStyle = 'rgba(56, 139, 253, 0.26)';
                ctx.beginPath();
                for (let i = 0; i < leafLinks.length; i++) {
                    const l = leafLinks[i];
                    ctx.moveTo(l.sourceNode.x, l.sourceNode.y);
                    ctx.lineTo(l.targetNode.x, l.targetNode.y);
                }
                ctx.stroke();
            }

            // Ana dal (gövde) kenarları: hafif eğri, biraz daha kalın.
            if (treeLinks.length > 0) {
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = 'rgba(56, 139, 253, 0.44)';
                ctx.beginPath();
                for (let i = 0; i < treeLinks.length; i++) {
                    const l = treeLinks[i];
                    drawCurvedLink(l.sourceNode, l.targetNode, 0.06);
                }
                ctx.stroke();
            }

            // 2. Draw Hovered Links with Radiant Gradient Synaptic Glow
            if (hoveredNode) {
                ctx.lineWidth = 2.4;
                links.forEach(l => {
                    if (l.is_catalog_link) return; // Never shoot 200 laser lines across the screen on hover!
                    const s = l.sourceNode;
                    const t = l.targetNode;
                    if (!s || !t) return;
                    if (s === hoveredNode || t === hoveredNode) {
                        const other = (s === hoveredNode ? t : s);
                        try {
                            const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
                            grad.addColorStop(0, getNodeColor(s.group));
                            grad.addColorStop(1, getNodeColor(t.group));
                            ctx.strokeStyle = grad;
                        } catch (e) {
                            ctx.strokeStyle = getNodeColor(other.group);
                        }
                        ctx.beginPath();
                        drawCurvedLink(s, t, 0.12);
                        ctx.stroke();
                    }
                });
            }

            // 3. Draw Nodes and Anti-Collision Pill Labels
            nodes.forEach(n => {
                if (!isNodeVisible(n) || isNaN(n.x) || isNaN(n.y)) return;

                const inScope = isNodeInScope(n);
                if (!inScope && isIsolated && currentScope !== 'all') return;

                const color = getNodeColor(n.group);
                const isHovered = (n === hoveredNode);
                // Uzaklaşınca düğümler toz tanesine dönüyordu: ekranda en az ~3 px kalsın.
                const r = Math.max((n.val || 12) * (isHovered ? 1.3 : 1.0), 3 / Math.max(zoom, 0.05));

                ctx.globalAlpha = inScope ? 1.0 : 0.08;

                // Outer Glow on Hover or Hub or Subbranch
                if (isHovered || n.group === 'ego' || n.group === 'hub' || n.group === 'subbranch') {
                    try {
                        const glow = ctx.createRadialGradient(n.x, n.y, r * 0.2, n.x, n.y, r * 2.2);
                        glow.addColorStop(0, color + 'aa');
                        glow.addColorStop(1, color + '00');
                        ctx.fillStyle = glow;
                    } catch (e) {
                        ctx.fillStyle = color;
                    }
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 2.2, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    // Hale topluluk tonunda: aynı topluluğun düğümleri gözle
                    // ayırt edilebilir bir doku oluşturur.
                    ctx.fillStyle = communityTint(n, 0.20);
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 1.5, 0, Math.PI * 2);
                    ctx.fill();
                }

                // Inner Solid Circle
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
                ctx.fill();

                // Cekirdek: ikonu olan gruplarda (ofis/ajan/sorgu) beyaz nokta
                // yerine ikon cizilir; boylece dugum turu renkten bagimsiz da
                // okunur ve efsanedeki ikonla birebir eslesir.
                const icon = getNodeIcon(n.group);
                if (icon) {
                    ctx.save();
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.font = `${Math.max(r * 1.1, 8)}px "Segoe UI Emoji", "Segoe UI Symbol", sans-serif`;
                    ctx.fillText(icon, n.x, n.y);
                    ctx.restore();
                } else {
                    ctx.fillStyle = '#FFFFFF';
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 0.35, 0, Math.PI * 2);
                    ctx.fill();
                }

                // Pill Label: Level of Detail (LOD) - Hubs & Subbranches visible by default, leaves visible when hovered or zoomed
                const lvl = (n.group === 'ego') ? 0
                    : (n.group === 'hub' || n.group === 'project' || n.group === 'skill') ? 1
                    : (n.group === 'subbranch') ? 2 : 3;
                // Etiketler ekran ölçeğinde çizilir (aşağıda); bu yüzden hangi düzeyin
                // hangi yakınlıkta görüneceği burada ayarlanır, boyut hep okunur kalır.
                const labelZoomFloor = [0, 0, 0.7, 1.35][lvl];
                const shouldDrawLabel = inScope && (isHovered || zoom >= labelZoomFloor);

                if (shouldDrawLabel) {
                    let labelText = n.name || '';
                    if (!isHovered && labelText.length > 24) {
                        labelText = labelText.substring(0, 22) + '..';
                    }

                    // Tipografi düzeye göre: çekirdek > ana dal > alt dal > yaprak.
                    // Tek yazı ailesi, monospace karışımı yok; pil etiketler aynı yükseklikte.
                    const level = (n.group === 'ego') ? 0
                        : (n.group === 'hub' || n.group === 'project' || n.group === 'skill') ? 1
                        : (n.group === 'subbranch') ? 2 : 3;
                    const isHeader = level <= 2;
                    const fontSize = [13, 11.5, 10.5, 10][level];
                    const weight = level === 0 ? '700' : (level === 1 ? '600' : (level === 2 ? '600' : '400'));
                    ctx.font = `${weight} ${fontSize}px "Segoe UI Variable Text", "Segoe UI", "Inter", system-ui, sans-serif`;
                    
                    if (isHovered) {
                        if (n._hoverTextWidth === undefined) {
                            n._hoverTextWidth = ctx.measureText(labelText).width;
                        }
                    } else if (n._textWidth === undefined) {
                        n._textWidth = ctx.measureText(labelText).width;
                    }
                    const textWidth = isHovered ? n._hoverTextWidth : n._textWidth;
                    // Piksel sabit etiket: yakınlık ne olursa olsun yazı 10–13 px kalır.
                    // (Önceden dünya ölçeğindeydi: sığdırma 0.48'de 10 px yazı 5 px oluyordu.)
                    const pillX = r * zoom + 6;
                    const pillY = -9;
                    // Ekran dikdörtgeni; daha önce yerleşmiş bir etiketle çakışıyorsa
                    // (üzerine gelinmemişse) bu etiket bu karede çizilmez.
                    const sx = n.x * zoom + panX + pillX, sy = n.y * zoom + panY + pillY;
                    const sw = textWidth + 10, sh = 18;
                    let collides = false;
                    if (!isHovered && lvl > 0) {
                        for (let i = 0; i < placedLabels.length; i++) {
                            const q = placedLabels[i];
                            if (sx < q.x + q.w + 4 && sx + sw + 4 > q.x && sy < q.y + q.h + 2 && sy + sh + 2 > q.y) { collides = true; break; }
                        }
                    }
                    if (collides) { ctx.globalAlpha = 1.0; return; }
                    placedLabels.push({ x: sx, y: sy, w: sw, h: sh });
                    ctx.save();
                    ctx.translate(n.x, n.y);
                    ctx.scale(1 / zoom, 1 / zoom);
                    const pillW = textWidth + 10;
                    const pillH = 18;

                    ctx.fillStyle = isHovered ? (color + '44') : 'rgba(8, 11, 16, 0.88)';
                    ctx.strokeStyle = isHovered ? color : 'rgba(31, 43, 66, 0.85)';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    if (typeof ctx.roundRect === 'function') {
                        ctx.roundRect(pillX, pillY, pillW, pillH, 4);
                    } else {
                        ctx.rect(pillX, pillY, pillW, pillH);
                    }
                    ctx.fill();
                    ctx.stroke();

                    ctx.fillStyle = isHovered ? color : '#E6EDF3';
                    ctx.fillText(labelText, pillX + 5, pillY + 13);
                    ctx.restore();
                }

                ctx.globalAlpha = 1.0;
            });

            ctx.restore();

            const needNext = (alpha >= alphaMin && !isPanning) || !!draggedNode;
            if (needNext) {
                isRendering = true;
                requestAnimationFrame(render);
            } else {
                isRendering = false;
                if (!settledFitDone) {
                    settledFitDone = true;
                    if (!userAdjustedView) fitToView();
                }
            }
        }

        updateDimensions();
        initNodePositions();
        relayoutGraph();
        fitToView();
        alpha = 1.0;
        settledFitDone = false;
        requestRender();

        setTimeout(() => {
            updateDimensions();
            relayoutGraph();
            fitToView();
            requestRender();
        }, 120);
    </script>
</body>
</html>
"""


class GraphWebEnginePage(QWebEnginePage):
    """Custom WebEnginePage intercepting entropy-node:// clicks."""

    @staticmethod
    def extract_node_id_from_url(url) -> Optional[str]:
        """Extract and unquote node identifier from an entropy-node:// URL."""
        if url.scheme() == "entropy-node":
            import urllib.parse
            from PySide6.QtCore import QUrlQuery
            q = QUrlQuery(url)
            node_id = urllib.parse.unquote(q.queryItemValue("id"))
            if not node_id:
                raw = url.toString()
                if "id=" in raw:
                    node_id = urllib.parse.unquote(raw.split("id=", 1)[1].split("&")[0])
                elif "entropy-node://select?id=" in raw:
                    node_id = urllib.parse.unquote(raw.split("entropy-node://select?id=", 1)[1])
                elif "entropy-node://" in raw:
                    node_id = urllib.parse.unquote(raw.replace("entropy-node://", "").strip("/"))
            return node_id if node_id else None
        return None

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        node_id = self.extract_node_id_from_url(url)
        if node_id:
            bus.node_selected.emit(node_id)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class KnowledgeGraphWidget(QFrame):
    """
    Dynamic Hierarchical Constellation Knowledge Graph Widget.
    Discovers projects, skills, MCPs, and cognitive memories dynamically into four category hubs,
    with multi-foci centroid physics, anti-squish seed layout, and an interactive scope filter.
    """

    def __init__(self, parent=None, vault_manager: Optional[ObsidianVaultManager] = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()
        self.cognitive_memory = CognitiveMemorySystem()
        self.skill_manager = SkillManager()
        self.mcp_manager = MCPManager()

        self.active_project_dir: Path = Path(config.default_project_path)
        self.current_scope: str = "all"
        self.skill_manager = SkillManager(project_dir=self.active_project_dir)
        self.mcp_manager = MCPManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header bar with Title, Scope Selector, Isolation toggle, and Refresh button
        header = QHBoxLayout()
        header.setSpacing(8)

        # Başlık kısa tutulur; uzun başlık + geniş açılır liste + iki düğme dar
        # panelde sığmıyor ve sağdaki düğmeler kesiliyordu.
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>🌐 BİLİŞSEL HAFIZA</b>")
        title_label.setToolTip("Bilişsel Hafıza ve Bilgi Haritası")
        header.addWidget(title_label)
        header.addStretch()

        # Scope Selector Dropdown
        self.scope_label = QLabel("<span style='color:#8B949E; font-size:11px;'>Odak:</span>")
        header.addWidget(self.scope_label)

        self.scope_combo = QComboBox()
        self.scope_combo.setFixedHeight(26)
        # Genişliği içeriğe değil panele göre: uzun seçenek adları listeyi taşırmasın.
        self.scope_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.scope_combo.setMinimumContentsLength(12)
        self.scope_combo.setMaximumWidth(220)
        self.scope_combo.setStyleSheet("""
            QComboBox {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
                min-width: 240px;
            }
            QComboBox:hover {
                border-color: #00F0FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #0E1420;
                color: #F0F6FC;
                border: 1px solid #00F0FF;
                selection-background-color: #1F2B42;
                selection-color: #00F0FF;
            }
        """)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        header.addWidget(self.scope_combo)

        # Isolation toggle button: "Sadece Seçili Dalı Göster"
        self.isolate_btn = QPushButton("👁️")
        self.isolate_btn.setCheckable(True)
        self.isolate_btn.setFixedSize(30, 26)
        self.isolate_btn.setToolTip("Açık: Yalnızca seçili dal ve alt düğümlerini gösterir (tüm diğer dalları gizler).\nKapalı: Tüm hafıza görünümünde seçili dalı vurgular, diğerlerini saydamlaştırır.")
        self.isolate_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #8B949E;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #00FF9D;
                color: #00FF9D;
            }
            QPushButton:checked {
                background-color: rgba(0, 255, 157, 0.15);
                color: #00FF9D;
                border-color: #00FF9D;
            }
        """)
        self.isolate_btn.toggled.connect(self._on_isolate_toggled)
        header.addWidget(self.isolate_btn)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Grafiği yenile")
        self.refresh_btn.setFixedSize(30, 26)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_graph)
        header.addWidget(self.refresh_btn)

        self.layout.addLayout(header)

        # WebEngine View with custom Navigation Page (lightweight placeholder in offscreen CI/CD mode)
        is_offscreen = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        if is_offscreen:
            self.web_view = QLabel("Knowledge Graph [Headless Engine Active]")
            self.web_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.web_view.setStyleSheet("background: #080B10; color: #00F0FF; font-family: monospace; border-radius: 6px;")
            self.web_page = None
            self.layout.addWidget(self.web_view)
        else:
            self.web_view = QWebEngineView()
            self.web_page = GraphWebEnginePage(self.web_view)
            self.web_view.setPage(self.web_page)
            self.web_view.setStyleSheet("background: #080B10; border-radius: 6px;")
            self.layout.addWidget(self.web_view)

        # Grafiğin yeniden kurulması pahalıdır: ~840 düğüm + ~3000 bağlantı için
        # build_unified_graph() yaklaşık 1.3 sn sürer ve setHtml() sayfayı baştan
        # yükleyip 1 MB JSON'u yeniden ayrıştırır. Aşağıdaki altı sinyal tek bir
        # sohbet turunda birkaç kez birden tetiklenebildiğinden, hepsi tek bir
        # gecikmeli yenilemede toplanır.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(1200)
        self._refresh_timer.timeout.connect(self.refresh_graph)

        # Auto-refresh on signals
        bus.report_created.connect(self._on_report_created)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.knowledge_graph_updated.connect(self.schedule_refresh)
        bus.cognitive_memory_updated.connect(self.schedule_refresh)
        bus.skills_updated.connect(self.schedule_refresh)
        bus.project_changed.connect(self._on_project_changed)

        self.refresh_graph()

    @Slot()
    def schedule_refresh(self):
        """Yenilemeyi geciktirir; arka arkaya gelen sinyaller tek yenilemede toplanır."""
        self._refresh_timer.start()

    @Slot(str)
    def _on_report_created(self, _: str):
        self.schedule_refresh()

    @Slot(str)
    def _on_turn_completed(self, _: str):
        self.schedule_refresh()

    @Slot(str)
    def _on_project_changed(self, new_dir: str):
        # Proje değişimi kapsamı tümüyle değiştirir; burada gecikme istemiyoruz.
        self._refresh_timer.stop()
        self.active_project_dir = Path(new_dir)
        self.skill_manager = SkillManager(project_dir=self.active_project_dir)
        self.refresh_graph()

    def _on_scope_changed(self, index: int):
        data = self.scope_combo.currentData()
        if data:
            self.apply_scope(data)

    def _on_isolate_toggled(self, checked: bool):
        if hasattr(self.web_view, "page") and self.web_view.page():
            try:
                js_val = "true" if checked else "false"
                self.web_view.page().runJavaScript(f"setIsolationMode({js_val});")
            except Exception:
                pass

    def apply_scope(self, scope_key: str):
        """Programmatically switch scope and update canvas."""
        self.current_scope = scope_key
        if hasattr(self.web_view, "page") and self.web_view.page():
            try:
                self.web_view.page().runJavaScript(f"setScope('{scope_key}');")
            except Exception:
                pass

    def closeEvent(self, event):
        try:
            bus.report_created.disconnect(self._on_report_created)
        except Exception:
            pass
        try:
            bus.agent_turn_completed.disconnect(self._on_turn_completed)
        except Exception:
            pass
        try:
            bus.knowledge_graph_updated.disconnect(self.schedule_refresh)
        except Exception:
            pass
        try:
            bus.cognitive_memory_updated.disconnect(self.schedule_refresh)
        except Exception:
            pass
        try:
            bus.skills_updated.disconnect(self.schedule_refresh)
        except Exception:
            pass
        try:
            self._refresh_timer.stop()
        except Exception:
            pass
        try:
            bus.project_changed.disconnect(self._on_project_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def build_unified_graph(self) -> Dict[str, Any]:
        """
        Build the dynamic 4-hub hierarchical constellation graph.
        - Central Ego Core
        - 4 Main Category Hubs (hub-projects, hub-skills, hub-mcp, hub-cognitive)
        - Dynamic sub-hubs for each discovered project, skill, and MCP server
        - Deterministic virtual taxonomy for reports
        - Decoupled index catalog springs (is_catalog_link=True)
        - Initial orbital coordinates pre-calculated for anti-squish layout
        """
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []
        node_ids = set()

        # 1. Central Ego Core (val=22)
        ego_id = "ego-entropy-core"
        node_ids.add(ego_id)
        nodes.append({
            "id": ego_id,
            "name": "Entropy AI Çekirdeği",
            "group": "ego",
            "info": "Otonom Ajan İşletim Sistemi Kimlik Düğümü",
            "val": 22,
            "x": 0,
            "y": 0,
            "cluster_group": "ego"
        })

        # 2. Four Main Category Hubs (Generous radial separation from Central Ego Core)
        cat_hubs = [
            ("hub-projects", "📁 Projeler & Çalışma Alanları", "projects", -145.0 * math.pi / 180.0, 400.0),
            ("hub-skills", "🎯 Uzmanlık Yetenekleri", "skills", -45.0 * math.pi / 180.0, 400.0),
            ("hub-mcp", "🔌 MCP Sunucuları & Araçları", "mcp", 45.0 * math.pi / 180.0, 400.0),
            ("hub-cognitive", "🧠 Bilişsel Bellek & Episodik Anılar", "cognitive", 135.0 * math.pi / 180.0, 400.0),
            # Ofisler batıda: dört mevcut hub çeyreklerde duruyor, 180° boştu.
            ("hub-offices", "🏢 Ofisler & Ajanlar", "offices", 180.0 * math.pi / 180.0, 400.0),
        ]
        for hub_id, hub_name, c_grp, angle, r_cat in cat_hubs:
            node_ids.add(hub_id)
            nodes.append({
                "id": hub_id,
                "name": hub_name,
                "group": "hub",
                "cluster_group": c_grp,
                "parent_hub": ego_id,
                "info": f"Ana Kategori Hub: {hub_name}",
                "val": 18,
                "x": round(math.cos(angle) * r_cat, 1),
                "y": round(math.sin(angle) * r_cat, 1)
            })
            links.append({"source": ego_id, "target": hub_id, "is_tree_link": True})

        # Discover dynamic skills and MCP servers
        skills = self.skill_manager.list_skills()
        registered_skills = [s.name for s in skills]

        servers = self.mcp_manager.list_servers()

        # Known projects
        known_projects = [config.default_project_path.name]
        if self.active_project_dir and self.active_project_dir.name not in known_projects:
            known_projects.append(self.active_project_dir.name)
        if self.vault_manager.projects_dir.exists():
            for p_sub in self.vault_manager.projects_dir.iterdir():
                if p_sub.is_dir() and p_sub.name not in known_projects:
                    known_projects.append(p_sub.name)

        leaf_counters: Dict[str, int] = {}

        # 3. Dynamic Sub-Hubs & Dendritic Branches
        # 3A. Projects Sub-Hubs (Branch towards Upper-Left)
        hub_proj_node = next(n for n in nodes if n["id"] == "hub-projects")
        num_proj = max(1, len(known_projects))
        for i, p_name in enumerate(known_projects):
            p_slug = normalize_slug(p_name)
            subhub_id = f"subhub-project-{p_slug}"
            if subhub_id not in node_ids:
                node_ids.add(subhub_id)
                ang = -145.0 * math.pi / 180.0 + (i - (num_proj - 1) / 2) * 0.52
                r_sub = 170.0 + 90.0 * (i % 2)
                nodes.append({
                    "id": subhub_id,
                    "name": f"📁 {p_name}",
                    "group": "project",
                    "cluster": f"project:{p_slug}",
                    "cluster_group": "projects",
                    "parent_hub": "hub-projects",
                    "info": f"Çalışma Alanı / Proje: {p_name}",
                    "val": 15,
                    "x": round(hub_proj_node["x"] + math.cos(ang) * r_sub, 1),
                    "y": round(hub_proj_node["y"] + math.sin(ang) * r_sub, 1)
                })
                links.append({"source": "hub-projects", "target": subhub_id, "is_tree_link": True})

        # 3B. Dynamic Skills Sub-Hubs with Dendritic Sub-Branches
        hub_skill_node = next(n for n in nodes if n["id"] == "hub-skills")

        # Dendritic sub-branches fanning outward in dedicated non-overlapping sectors
        AUTONOMOUS_SUBBRANCHES = [
            ("subbranch-agent-faz66-80", "Faz 66-80: Temel Ajan Mimarisi", "Çekirdek ajan yürütme ve bellek modelleri", 650.0, -135.0),
            ("subbranch-agent-faz81-90", "Faz 81-90: Otonom Protokoller", "A2A, ACP ve çoklu ajan işbirliği protokolleri", 740.0, -55.0),
            ("subbranch-agent-faz91-104", "Faz 91-104: İleri Bilişsel Karar", "Bilişsel karar ağaçları ve derin optimizasyon", 740.0, 55.0),
            ("subbranch-agent-desks", "Agent Desks & Harness", "Ajan çalışma masaları, sandbox ve denetim", 650.0, 135.0),
        ]

        FINANCIAL_SUBBRANCHES = [
            ("subbranch-fin-clo-credit", "Kredi & Yapılandırılmış CLO", "CLO Tranche, LBO ve tahvil yapıları", -135.0, -650.0),
            ("subbranch-fin-vol-options", "Volatilite & Stokastik Opsiyon", "SVI, SABR, Heston ve türev fiyatlama", -55.0, -740.0),
            ("subbranch-fin-defi-arb", "DeFi, Likidite & Arbitraj", "CFMM, Uniswap V3 ve algoritmik likidite", 55.0, -740.0),
            ("subbranch-fin-risk-alm", "ALM, Basel & Risk Yönetimi", "Aktif-pasif yönetimi ve regülasyon denetimi", 135.0, -650.0),
        ]

        dyn_skills = [s for s in skills if s.name not in ("autonomous-agent", "financial-auditor")]

        for i, s in enumerate(skills):
            s_slug = normalize_slug(s.name)
            subhub_id = f"subhub-skill-{s_slug}"
            if subhub_id not in node_ids:
                node_ids.add(subhub_id)

                if s.name == "autonomous-agent":
                    # Autonomous Agent radiates directly East (heading right! theta = 0) at R = 420px from Core
                    skill_x = 420.0
                    skill_y = 0.0
                    p_hub = ego_id
                elif s.name == "financial-auditor":
                    # Financial Auditor radiates directly North (heading up! theta = -90 deg) at R = 420px from Core
                    skill_x = 0.0
                    skill_y = -420.0
                    p_hub = ego_id
                else:
                    # Dynamic new skills radiate into open sectors in NE (theta = -45 deg, R >= 450px)
                    k = dyn_skills.index(s) if s in dyn_skills else i
                    ang = -45.0 * math.pi / 180.0 + (k - (max(1, len(dyn_skills)) - 1) / 2) * 0.22
                    r_skill_hub = 480.0 + k * 45.0
                    skill_x = round(math.cos(ang) * r_skill_hub, 1)
                    skill_y = round(math.sin(ang) * r_skill_hub, 1)
                    p_hub = "hub-skills"

                nodes.append({
                    "id": subhub_id,
                    "name": f"🎯 {s.name}",
                    "group": "skill",
                    "cluster": f"skill:{s_slug}",
                    "cluster_group": "skills",
                    "parent_hub": p_hub,
                    "info": f"Yetenek: {s.name} - {s.description[:120]}",
                    "val": 15,
                    "x": skill_x,
                    "y": skill_y
                })
                links.append({"source": p_hub, "target": subhub_id, "is_tree_link": True})

                # Dendritic sub-branches for autonomous-agent (cascades outward to the right)
                if s.name == "autonomous-agent":
                    for sb_id, sb_name, sb_info, sb_x, sb_y in AUTONOMOUS_SUBBRANCHES:
                        if sb_id not in node_ids:
                            node_ids.add(sb_id)
                            nodes.append({
                                "id": sb_id,
                                "name": f"🌿 {sb_name}",
                                "group": "subbranch",
                                "cluster": f"skill:{s_slug}",
                                "cluster_group": "skills",
                                "parent_hub": subhub_id,
                                "info": f"Alt Dal: {sb_info}",
                                "val": 13,
                                "x": sb_x,
                                "y": sb_y
                            })
                            links.append({"source": subhub_id, "target": sb_id, "is_tree_link": True})

                # Dendritic sub-branches for financial-auditor (fans out upwards)
                elif s.name == "financial-auditor":
                    for sb_id, sb_name, sb_info, sb_x, sb_y in FINANCIAL_SUBBRANCHES:
                        if sb_id not in node_ids:
                            node_ids.add(sb_id)
                            nodes.append({
                                "id": sb_id,
                                "name": f"🌿 {sb_name}",
                                "group": "subbranch",
                                "cluster": f"skill:{s_slug}",
                                "cluster_group": "skills",
                                "parent_hub": subhub_id,
                                "info": f"Alt Dal: {sb_info}",
                                "val": 13,
                                "x": sb_x,
                                "y": sb_y
                            })
                            links.append({"source": subhub_id, "target": sb_id, "is_tree_link": True})

                # Skill executable scripts
                for sc in s.scripts:
                    sc_id = f"tool-{s_slug}-{normalize_slug(sc['name'])}"
                    if sc_id not in node_ids:
                        node_ids.add(sc_id)
                        if s.name == "financial-auditor":
                            effective_sc_parent = classify_financial_subbranch(sc["name"])
                            if not any(n["id"] == effective_sc_parent for n in nodes):
                                effective_sc_parent = subhub_id
                        else:
                            effective_sc_parent = subhub_id

                        p_node = next((n for n in nodes if n["id"] == effective_sc_parent), None)
                        p_x = p_node.get("x", skill_x) if p_node else skill_x
                        p_y = p_node.get("y", skill_y) if p_node else skill_y

                        count_sc = leaf_counters.get(effective_sc_parent, 0)
                        leaf_counters[effective_sc_parent] = count_sc + 1

                        if effective_sc_parent.startswith("subbranch-fin-"):
                            b_ang = math.atan2(p_y - (-420.0), p_x - 0.0)
                        elif effective_sc_parent.startswith("subbranch-agent-"):
                            b_ang = math.atan2(p_y - 0.0, p_x - 420.0)
                        else:
                            b_ang = math.atan2(p_y, p_x) if (p_x != 0 or p_y != 0) else 0.0

                        sc_x, sc_y = compute_radial_fan_leaf_pos(p_x, p_y, b_ang, count_sc)

                        nodes.append({
                            "id": sc_id,
                            "name": f"⚙️ {sc['name']}",
                            "group": "mcp-tool",
                            "cluster": f"skill:{s_slug}",
                            "cluster_group": "skills",
                            "parent_hub": effective_sc_parent,
                            "info": f"Yetenek Komut Dosyası: {sc['path']}",
                            "val": 10,
                            "x": sc_x,
                            "y": sc_y
                        })
                        links.append({"source": effective_sc_parent, "target": sc_id, "is_tree_link": True})

        # 3C. Dynamic MCP Sub-Hubs & Tools
        hub_mcp_node = next(n for n in nodes if n["id"] == "hub-mcp")
        num_srv = max(1, len(servers))
        for i, srv in enumerate(servers):
            srv_name = srv["name"]
            srv_slug = normalize_slug(srv_name)
            subhub_id = f"subhub-mcp-{srv_slug}"
            if subhub_id not in node_ids:
                node_ids.add(subhub_id)
                ang = math.pi * 0.25 + (i - (num_srv - 1) / 2) * 0.32
                r_mcp_sub = 150.0 + 35.0 * (i % 2)
                srv_x = round(hub_mcp_node["x"] + math.cos(ang) * r_mcp_sub, 1)
                srv_y = round(hub_mcp_node["y"] + math.sin(ang) * r_mcp_sub, 1)
                nodes.append({
                    "id": subhub_id,
                    "name": f"🔌 {srv_name}",
                    "group": "mcp",
                    "cluster": f"mcp:{srv_slug}",
                    "cluster_group": "mcp",
                    "parent_hub": "hub-mcp",
                    "info": f"MCP Sunucusu: {srv_name} ({srv.get('type', 'stdio')})",
                    "val": 15,
                    "x": srv_x,
                    "y": srv_y
                })
                links.append({"source": "hub-mcp", "target": subhub_id, "is_tree_link": True})

                tools = self.mcp_manager.list_tools(srv_name)
                num_tools = max(1, len(tools))
                for t_idx, tool in enumerate(tools):
                    tool_id = f"mcp-tool-{srv_slug}-{tool['name']}"
                    if tool_id not in node_ids:
                        node_ids.add(tool_id)
                        t_ang = ang + (t_idx - (num_tools - 1) / 2) * 0.50
                        r_tool = 55.0 + 20.0 * (t_idx % 2)
                        nodes.append({
                            "id": tool_id,
                            "name": f"🛠️ {tool['name']}",
                            "group": "mcp-tool",
                            "cluster": f"mcp:{srv_slug}",
                            "cluster_group": "mcp",
                            "parent_hub": subhub_id,
                            "info": f"MCP Aracı [{srv_name}]: {tool['name']} - {tool.get('description', '')}",
                            "val": 10,
                            "x": round(srv_x + math.cos(t_ang) * r_tool, 1),
                            "y": round(srv_y + math.sin(t_ang) * r_tool, 1)
                        })
                        links.append({"source": subhub_id, "target": tool_id, "is_tree_link": True})

        # 3D. Cognitive Sub-Hubs & Dendritic Sub-Branches
        hub_cog_node = next(n for n in nodes if n["id"] == "hub-cognitive")
        cog_subhubs = [
            ("subhub-cog-episodic", "⏳ Episodik Anılar", "episodic", math.pi * 0.53, 180.0),
            ("subhub-cog-semantic", "🧠 Semantik Bellek", "semantic", math.pi * 0.75, 220.0),
            ("subhub-cog-procedural", "⚙️ Prosedürel Bellek", "procedural", math.pi * 0.97, 180.0),
        ]
        for c_id, c_name, c_cat, ang, r_dist in cog_subhubs:
            node_ids.add(c_id)
            nodes.append({
                "id": c_id,
                "name": c_name,
                "group": c_cat,
                "cluster": f"cognitive:{c_cat}",
                "cluster_group": "cognitive",
                "parent_hub": "hub-cognitive",
                "info": f"Bilişsel Katman: {c_name}",
                "val": 15,
                "x": round(hub_cog_node["x"] + math.cos(ang) * r_dist, 1),
                "y": round(hub_cog_node["y"] + math.sin(ang) * r_dist, 1)
            })
            links.append({"source": "hub-cognitive", "target": c_id, "is_tree_link": True})

        # Dendritic sub-branches for cognitive semantic memory fanning outward in SW
        COG_SEMANTIC_SUBBRANCHES = [
            ("subbranch-cog-sem-core", "🌿 Çekirdek Kimlik & Kararlar", "Ego, persona ve mimari kararlar", -477.9, 624.2),
            ("subbranch-cog-sem-arch", "🌿 Mimari & İlkeler", "Sistem mimarisi, zero-api ve protokoller", -581.5, 667.4),
            ("subbranch-cog-sem-research", "🌿 Araştırma & Özetler", "Bilişsel araştırma özetleri ve RAG", -713.5, 638.2),
            ("subbranch-cog-sem-finance", "🌿 Finans & Kantitatif", "Bilanço, portföy ve değerleme modelleri", -689.5, 505.7),
        ]
        for sb_id, sb_name, sb_info, sb_x, sb_y in COG_SEMANTIC_SUBBRANCHES:
            if sb_id not in node_ids:
                node_ids.add(sb_id)
                nodes.append({
                    "id": sb_id,
                    "name": sb_name,
                    "group": "subbranch",
                    "cluster": "cognitive:semantic",
                    "cluster_group": "cognitive",
                    "parent_hub": "subhub-cog-semantic",
                    "info": f"Alt Dal: {sb_info}",
                    "val": 13,
                    "x": sb_x,
                    "y": sb_y
                })
                links.append({"source": "subhub-cog-semantic", "target": sb_id, "is_tree_link": True})

        # 4. Cognitive Memory Nodes from SQLite
        try:
            import sqlite3
            if self.cognitive_memory.db_path.exists():
                with sqlite3.connect(self.cognitive_memory.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, category, content, importance FROM cognitive_nodes ORDER BY created_at DESC LIMIT 80")
                    for row in cursor.fetchall():
                        c_id, cat, content, imp = row[0], row[1], row[2], row[3]
                        if c_id not in node_ids:
                            node_ids.add(c_id)
                            short_name = content[:26] + ("..." if len(content) > 26 else "")

                            if cat == "episodic":
                                p_hub = "subhub-cog-episodic"
                                node_grp = "episodic"
                            elif cat in ("procedural", "task"):
                                p_hub = "subhub-cog-procedural"
                                node_grp = "procedural"
                            else:
                                p_hub = classify_cognitive_semantic_subbranch(content)
                                if not any(n["id"] == p_hub for n in nodes):
                                    p_hub = "subbranch-cog-sem-core"
                                node_grp = "semantic"

                            c_count = leaf_counters.get(p_hub, 0)
                            leaf_counters[p_hub] = c_count + 1

                            parent_node = next((n for n in nodes if n["id"] == p_hub), hub_cog_node)
                            p_x = parent_node.get("x", hub_cog_node["x"])
                            p_y = parent_node.get("y", hub_cog_node["y"])

                            if p_hub.startswith("subbranch-cog-sem-"):
                                sem_hub = next((n for n in nodes if n["id"] == "subhub-cog-semantic"), hub_cog_node)
                                b_ang = math.atan2(p_y - sem_hub["y"], p_x - sem_hub["x"])
                            elif p_hub in ("subhub-cog-episodic", "subhub-cog-procedural"):
                                b_ang = math.atan2(p_y - hub_cog_node["y"], p_x - hub_cog_node["x"])
                            else:
                                b_ang = math.atan2(p_y, p_x) if (p_x != 0 or p_y != 0) else (math.pi * 0.75)

                            c_leaf_x, c_leaf_y = compute_radial_fan_leaf_pos(p_x, p_y, b_ang, c_count)

                            nodes.append({
                                "id": c_id,
                                "name": short_name,
                                "group": node_grp,
                                "cluster": f"cognitive:{node_grp}",
                                "cluster_group": "cognitive",
                                "parent_hub": p_hub,
                                "info": content,
                                "val": max(10, int(imp * 16)),
                                "x": c_leaf_x,
                                "y": c_leaf_y
                            })
                            links.append({"source": p_hub, "target": c_id, "is_tree_link": True})
        except Exception:
            pass

        # 5. Obsidian Vault Notes & Research Reports with Deterministic Virtual Taxonomy & Dendritic Sub-Branches
        obsidian_data = self.vault_manager.build_knowledge_graph()

        # Kasa grafiğinden gelen aidiyet bağları (dosya yolundan türetilmiş,
        # metinden değil): sorgu sayfası -> yetenek/ofis, ofis -> ajan.
        owner_of: Dict[str, str] = {}
        office_of_agent: Dict[str, str] = {}
        for o_link in obsidian_data["links"]:
            alias = (o_link.get("alias") or "").strip()
            if alias in ("skill", "office"):
                owner_of.setdefault(o_link["source"], o_link["target"])
            elif alias in ("orkestrator", "degerlendirici", "uye"):
                office_of_agent.setdefault(o_link["target"], o_link["source"])

        # Ofis/ajan/yetenek düğümleri yapraklardan ÖNCE eklenmeli: yaprak
        # yerleşimi ebeveynin konumundan hesaplanıyor, ebeveyn henüz yoksa
        # yaprak yanlış dala düşerdi. Sıralama kararlı: geri kalan düzen aynı.
        _ORDER = {"office": 0, "agent": 0, "skill": 0}
        obsidian_nodes = sorted(
            obsidian_data["nodes"], key=lambda n: _ORDER.get(n.get("group", ""), 1)
        )

        for o_node in obsidian_nodes:
            o_id = o_node["id"]
            if o_id in node_ids:
                continue
            node_ids.add(o_id)

            o_path = o_node.get("path", "")
            o_name = o_node["name"]
            grp = o_node.get("group", "obsidian")
            is_report = (grp == "Reports") or ("Reports" in o_path)
            is_daily = (grp == "DailyNotes") or ("DailyNotes" in o_path)
            is_memory = (o_name == "MEMORY")

            if grp in ("office", "agent", "query", "skill"):
                # Faz 3: ofis düğümleri, ofis ajanları ve sorgu/ofis raporu
                # yaprakları. Renk ve ikon şablondaki `colors`/`groupIcons`
                # eşlemesinden gelir; burada yalnızca ağaçtaki yerleri kurulur.
                if grp == "office":
                    parent_hub = "hub-offices"
                    cluster_id = f"office:{normalize_slug(o_name)}"
                    cluster_grp = "offices"
                    node_val = 15
                elif grp == "agent":
                    parent_hub = office_of_agent.get(o_id, "hub-offices")
                    if not any(n["id"] == parent_hub for n in nodes):
                        parent_hub = "hub-offices"
                    cluster_id = "offices:agents"
                    cluster_grp = "offices"
                    node_val = 12
                elif grp == "skill":
                    slug = normalize_slug(o_name)
                    subhub = f"subhub-skill-{slug}"
                    parent_hub = subhub if any(n["id"] == subhub for n in nodes) else "hub-skills"
                    cluster_id = f"skill:{slug}"
                    cluster_grp = "skills"
                    node_val = 13
                else:  # query (wiki sorgusu ya da ofis raporu özeti)
                    owner = owner_of.get(o_id, "")
                    if owner.startswith("office/"):
                        parent_hub = owner if any(n["id"] == owner for n in nodes) else "hub-offices"
                        cluster_id = f"office:{normalize_slug(owner.split('/', 1)[1])}"
                        cluster_grp = "offices"
                    elif owner.startswith("skill/"):
                        slug = normalize_slug(owner.split("/", 1)[1])
                        subhub = f"subhub-skill-{slug}"
                        if any(n["id"] == subhub for n in nodes):
                            parent_hub = subhub
                        elif any(n["id"] == owner for n in nodes):
                            parent_hub = owner
                        else:
                            parent_hub = "hub-skills"
                        cluster_id = f"skill:{slug}"
                        cluster_grp = "skills"
                    else:
                        parent_hub = "hub-skills"
                        cluster_id = "skill:genel"
                        cluster_grp = "skills"
                    node_val = 12
                effective_parent = parent_hub
                node_group = grp
            elif is_report:
                parent_hub, cluster_id, cluster_grp = classify_report_to_hub(
                    title=o_name,
                    path_str=o_path,
                    tags=None,
                    registered_skills=registered_skills,
                    known_projects=known_projects
                )
                if not any(n["id"] == parent_hub for n in nodes):
                    p_slug = normalize_slug(known_projects[0])
                    parent_hub = f"subhub-project-{p_slug}"
                    cluster_id = f"project:{p_slug}"
                    cluster_grp = "projects"

                # Dendritic sub-branch resolution for autonomous and financial skills
                effective_parent = parent_hub
                if parent_hub == "subhub-skill-autonomous-agent":
                    sb = classify_autonomous_subbranch(o_name)
                    if any(n["id"] == sb for n in nodes):
                        effective_parent = sb
                elif parent_hub == "subhub-skill-financial-auditor":
                    sb = classify_financial_subbranch(o_name)
                    if any(n["id"] == sb for n in nodes):
                        effective_parent = sb

                node_group = "Reports"
                node_val = 16  # Preserves test requirement for report val
            elif is_daily:
                parent_hub = "subhub-cog-episodic"
                effective_parent = parent_hub
                cluster_id = "cognitive:episodic"
                cluster_grp = "cognitive"
                node_group = "DailyNotes"
                node_val = 11
            elif is_memory:
                parent_hub = "subhub-cog-semantic"
                effective_parent = "subbranch-cog-sem-core"
                cluster_id = "cognitive:semantic"
                cluster_grp = "cognitive"
                node_group = "semantic"
                node_val = 14
            else:
                p_slug = normalize_slug(known_projects[0])
                parent_hub = f"subhub-project-{p_slug}"
                effective_parent = parent_hub
                cluster_id = f"project:{p_slug}"
                cluster_grp = "projects"
                node_group = "obsidian"
                node_val = 11

            # Bilateral dendritic vine placement along branch angle (prevents circular ball swarming)
            count = leaf_counters.get(effective_parent, 0)
            leaf_counters[effective_parent] = count + 1

            parent_node = next((n for n in nodes if n["id"] == effective_parent), hub_proj_node)
            parent_x = parent_node.get("x", 0.0)
            parent_y = parent_node.get("y", 0.0)
            if effective_parent.startswith("subbranch-fin-"):
                branch_angle = math.atan2(parent_y - (-420.0), parent_x - 0.0)
            elif effective_parent.startswith("subbranch-agent-"):
                branch_angle = math.atan2(parent_y - 0.0, parent_x - 420.0)
            elif effective_parent.startswith("subbranch-cog-sem-"):
                sem_hub = next((n for n in nodes if n["id"] == "subhub-cog-semantic"), hub_cog_node)
                branch_angle = math.atan2(parent_y - sem_hub["y"], parent_x - sem_hub["x"])
            elif effective_parent in ("subhub-cog-episodic", "subhub-cog-procedural"):
                branch_angle = math.atan2(parent_y - hub_cog_node["y"], parent_x - hub_cog_node["x"])
            else:
                branch_angle = math.atan2(parent_y, parent_x) if (parent_x != 0 or parent_y != 0) else 0.0

            leaf_x, leaf_y = compute_radial_fan_leaf_pos(parent_x, parent_y, branch_angle, count)

            nodes.append({
                "id": o_id,
                "name": o_name,
                "group": node_group,
                "cluster": cluster_id,
                "cluster_group": cluster_grp,
                "parent_hub": effective_parent,
                "skill_hub": parent_hub,
                "info": f"Obsidian Dosyası: {o_path}",
                "val": node_val,
                "x": leaf_x,
                "y": leaf_y
            })
            links.append({"source": effective_parent, "target": o_id, "is_tree_link": True})

        # Add wikilinks from Obsidian notes (decoupled if catalog)
        for link in obsidian_data["links"]:
            is_cat = link.get("is_catalog_link", False)
            if "BELLEK_HARITASI" in link["source"] or "MEMORY" in link["source"]:
                is_cat = True
            links.append({
                "source": link["source"],
                "target": link["target"],
                "alias": link.get("alias", ""),
                "is_catalog_link": is_cat
            })

        # Fallback foundational nodes if graph is sparse
        if len(nodes) < 6:
            default_nodes = [
                ("sem-01", "semantic", "subhub-cog-semantic", "Zero-API Antigravity CLI Politikası", "Harici API anahtarı olmadan yerel CLI üzerinden çalışma."),
                ("sem-02", "semantic", "subhub-cog-semantic", "Obsidian Exocortex Bellek Yapısı", "Yerel Markdown dosyalarında bilgi ağı saklama."),
                ("sem-03", "semantic", "subhub-cog-semantic", "Supabase pgvector Mem0 Entegrasyonu", "12 katmanlı unutma eğrisi ve semantik geri çağırma."),
                ("epi-01", "episodic", "subhub-cog-episodic", "Son Kodlama ve Test Seansı", "Otomatik testler başarıyla yürütüldü."),
            ]
            for n_id, grp, p_hub, name, info in default_nodes:
                if n_id not in node_ids:
                    node_ids.add(n_id)
                    nodes.append({
                        "id": n_id,
                        "name": name,
                        "group": grp,
                        "cluster": f"cognitive:{grp}",
                        "cluster_group": "cognitive",
                        "parent_hub": p_hub,
                        "info": info,
                        "val": 12
                    })
                    links.append({"source": p_hub, "target": n_id, "is_tree_link": True})

        # Post-flight zero-overlap anti-collision relaxation pass
        FIXED_IDS = {
            "ego-entropy-core", "hub-projects", "hub-skills", "hub-mcp", "hub-cognitive", "hub-offices",
            "subhub-skill-autonomous-agent", "subhub-skill-financial-auditor"
        }
        # Kaba kuvvet O(N²) tarama 1000 düğümde tur başına ~500 bin çift ediyor ve
        # 15 tur birkaç saniye sürüyordu; her grafik yenilemesinde arayüz donuyordu.
        # Düğümler x'e göre sıralanıp yalnızca x farkı olası en büyük çakışma
        # mesafesinden küçük olan çiftler denetlenir (süpürme-budama). Atlanan
        # çiftler tanım gereği çakışamaz, sonuç aynı kalır.
        # Bu geçiş artık yalnızca TOHUM konumlarını düzeltir: son yerleşimi kuvvet
        # benzetimindeki çakışma çözümü belirler. 900 raporluk bir arşivde 60 tur
        # 5,4 saniye sürüyordu (ölçüldü) ve grafik her yenilendiğinde arayüz
        # donuyordu; büyük arşivlerde tur sayısı düşürüldü.
        max_val = max((n.get("val", 12) for n in nodes), default=12)
        prune_dx = 2.0 * (2.0 * max_val + 3.0)
        relax_rounds = 60 if len(nodes) <= 300 else 6
        for _ in range(relax_rounds):
            overlap_found = False
            order = sorted(nodes, key=lambda n: n.get("x", 0.0))
            for i in range(len(order)):
                a = order[i]
                for j in range(i + 1, len(order)):
                    b = order[j]
                    dx = b["x"] - a["x"]
                    if dx > prune_dx:
                        break
                    dy = b["y"] - a["y"]
                    d = math.hypot(dx, dy)
                    r_min = (a.get("val", 12) + b.get("val", 12)) + 3.0
                    if d < r_min:
                        overlap_found = True
                        if d < 0.001:
                            dx = 1.0
                            dy = 0.0
                            d = 1.0
                        overlap = (r_min - d)
                        px = (dx / d) * (overlap * 0.52)
                        py = (dy / d) * (overlap * 0.52)
                        if b["id"] not in FIXED_IDS:
                            b["x"] = round(b["x"] + px, 1)
                            b["y"] = round(b["y"] + py, 1)
                        if a["id"] not in FIXED_IDS:
                            a["x"] = round(a["x"] - px, 1)
                            a["y"] = round(a["y"] - py, 1)
            if not overlap_found:
                break

        # Yakınlık kenarları: raporlar birbirine ağaçtaki yerine göre değil,
        # içeriklerinin benzerliğine göre de çekilsin. Bu kenarlar ağaç kenarı
        # değildir (is_similarity_link), fizik motorunda en güçlü yaydır.
        leaf_nodes = [n for n in nodes if n.get("group") in SIMILARITY_GROUPS]
        sim_links = build_similarity_links(leaf_nodes)
        links.extend(sim_links)

        # Topluluklar: renk tonu/hale için. Ağaç + benzerlik kenarları üzerinde
        # ağırlıklı etiket yayılımı.
        communities = assign_communities(nodes, links)
        for n in nodes:
            n["community"] = communities.get(n["id"], 0)

        return {
            "nodes": nodes,
            "links": links,
            "similarity_links": len(sim_links),
            "communities": len(set(communities.values())),
            "known_projects": known_projects,
            "registered_skills": registered_skills
        }

    def refresh_graph(self):
        """Re-generate unified graph JSON and update WebEngine canvas and Scope Selector."""
        graph_data = self.build_unified_graph()

        # Update Scope Selector combo box without resetting if selection still valid
        prev_data = self.scope_combo.currentData() or self.current_scope
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()

        # Default: All Memory (Galaxy View)
        self.scope_combo.addItem("🌐 Tüm Hafıza (Galaksi Görünümü)", "all")

        # Active Project
        active_slug = normalize_slug(self.active_project_dir.name)
        self.scope_combo.addItem(f"📁 Aktif Proje ({self.active_project_dir.name})", "active_project")

        # Individual Projects
        for p_name in graph_data["known_projects"]:
            p_slug = normalize_slug(p_name)
            self.scope_combo.addItem(f"📁 Proje: {p_name}", f"project:{p_slug}")

        # All Skills & Individual Skills
        self.scope_combo.addItem("🎯 Yetenekler (Tüm Yetenek Dalları)", "all_skills")
        for s_name in graph_data["registered_skills"]:
            s_slug = normalize_slug(s_name)
            display_name = s_name
            if s_name == "autonomous-agent":
                display_name = "Otonom Ajan Mimarisi (autonomous-agent)"
            elif s_name == "financial-auditor":
                display_name = "Finansal Denetçi & Kantitatif Analiz (financial-auditor)"
            self.scope_combo.addItem(f"🎯 Yetenek: {display_name}", f"skill:{s_slug}")

        # All MCP & All Cognitive
        self.scope_combo.addItem("🏢 Ofisler (Ofisler, Ajanlar, Ofis Raporları)", "all_offices")
        self.scope_combo.addItem("🔌 MCP Sunucuları & Araçları", "all_mcp")
        self.scope_combo.addItem("🧠 Bilişsel Bellek & Anılar", "all_cognitive")

        # Restore previous selection or default to 'all'
        target_idx = self.scope_combo.findData(prev_data)
        if target_idx >= 0:
            self.scope_combo.setCurrentIndex(target_idx)
            self.current_scope = prev_data
        else:
            self.scope_combo.setCurrentIndex(0)
            self.current_scope = "all"
        self.scope_combo.blockSignals(False)

        if not hasattr(self.web_view, "setHtml"):
            return

        nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False).replace("</", "<\\/")
        links_json = json.dumps(graph_data["links"], ensure_ascii=False).replace("</", "<\\/")

        html_content = (
            GRAPH_HTML_TEMPLATE
            .replace("__NODES__", nodes_json)
            .replace("__LINKS__", links_json)
            .replace("__INITIAL_SCOPE__", self.current_scope)
            .replace("__ACTIVE_PROJECT_SLUG__", active_slug)
        )
        self.web_view.setHtml(html_content)
