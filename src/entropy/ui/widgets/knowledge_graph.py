"""Interactive Hierarchical Constellation Knowledge Graph Viewer using QWebEngineView with multi-foci centroid physics."""

import os
import re
import json
import math
from pathlib import Path
from typing import Optional, Dict, List, Any, Set, Tuple
from functools import partial

from PySide6.QtCore import QRunnable, Qt, QThreadPool, QTimer, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QComboBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

from entropy.core.event_bus import bus
from entropy.core.config import config
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager, is_test_artifact_name
from entropy.memory.graph_enrich import enrich_graph
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
SIMILARITY_K = 3  # Faz 8: k=4 iken 716 benzerlik kenari (JSON %13); k=3 kumelemeyi bozmuyor
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


COGNITIVE_NAME_MAX = 40


def _cognitive_node_name(content: str, counts: Optional[Dict[str, int]] = None) -> str:
    """
    Bilişsel bellek düğümünün adı: içeriğin İLK ANLAMLI SATIRI.

    Satır sonu taşımaz (kanvasta ad tek satır çizilir), ≤ 40 karakterdir ve aynı
    ad 5'ten çok kez tekrar ederse sayaç eki alır (`counts` verilirse). Ölçüm
    2026-09-09: eski "ilk 26 karakter" kuralı 80 düğüm adına satır sonu, 5 gruba
    da çakışan ad koyuyordu.
    """
    first = ""
    for line in (content or "").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            first = stripped
            break
    if not first:
        first = (content or "").strip().replace("\n", " ")[:COGNITIVE_NAME_MAX]
    first = re.sub(r"\s+", " ", first).strip()
    if len(first) > COGNITIVE_NAME_MAX:
        first = first[:COGNITIVE_NAME_MAX - 1].rstrip() + "…"
    if counts is None:
        return first
    seen = counts.get(first, 0)
    counts[first] = seen + 1
    if seen == 0:
        return first
    suffix = f" ({seen + 1})"
    return (first[: COGNITIVE_NAME_MAX - len(suffix)]).rstrip() + suffix


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
        /* Faz 8 / U3: efsane tek satır, yalnızca bu veride düğümü olan
           kategoriler + sayılar. Kapalıyken yüksekliği 26 px'i geçmez; tam
           liste, topluluk paleti ve kontroller katlanan panelin içindedir. */
        #legend {
            position: absolute;
            top: 8px;
            left: 8px;
            font-size: 11px;
            background: rgba(14, 20, 32, 0.92);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 3px 8px;
            display: flex;
            align-items: center;
            gap: 8px;
            backdrop-filter: blur(6px);
            z-index: 10;
            max-width: 460px;
            height: 26px;
            overflow: hidden;
            white-space: nowrap;
        }
        #legendToggle {
            cursor: pointer;
            color: #00F0FF;
            font-weight: 700;
            padding: 0 3px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            padding: 1px 4px;
            border-radius: 4px;
            transition: all 0.15s ease;
        }
        .legend-item:hover { background: rgba(0, 240, 255, 0.12); }
        .legend-item.dimmed { opacity: 0.30; text-decoration: line-through; }
        .legend-count { color: #8B949E; font-size: 10px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        /* Katlanan panel: tam kategori listesi + topluluk paleti + kontroller. */
        #legendPanel {
            position: absolute;
            top: 40px;
            left: 8px;
            display: none;
            font-size: 11px;
            background: rgba(14, 20, 32, 0.96);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 8px 10px;
            z-index: 11;
            max-width: 460px;
            color: #C9D1D9;
            backdrop-filter: blur(6px);
        }
        #legendPanel.open { display: block; }
        #legendPanelItems { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
        #graphControls {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 10px;
            border-top: 1px solid #1F2B42;
            padding-top: 6px;
        }
        #graphControls.empty { display: none; }
        .ctrl-group { display: flex; align-items: center; gap: 5px; }
        .ctrl-group.disabled { display: none; }
        #graphControls select, #graphControls input[type=range] {
            background: #0E1420;
            color: #00F0FF;
            border: 1px solid #1F2B42;
            border-radius: 4px;
            font-size: 11px;
            padding: 1px 4px;
        }
        #graphControls input[type=range] { width: 110px; padding: 0; }
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
        /* U7: arama kutusu (Ctrl+F) */
        #searchBox {
            position: absolute;
            top: 8px;
            right: 8px;
            z-index: 12;
            display: none;
            background: rgba(14, 20, 32, 0.96);
            border: 1px solid #00F0FF;
            border-radius: 6px;
            padding: 4px 6px;
            width: 260px;
        }
        #searchBox.open { display: block; }
        #searchInput {
            width: 100%;
            background: #0E1420;
            color: #F0F6FC;
            border: 1px solid #1F2B42;
            border-radius: 4px;
            font-size: 11px;
            padding: 3px 6px;
            outline: none;
        }
        #searchResults { margin-top: 4px; max-height: 168px; overflow: hidden; }
        .search-hit {
            padding: 3px 6px;
            font-size: 11px;
            border-radius: 4px;
            cursor: pointer;
            color: #C9D1D9;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .search-hit:hover { background: rgba(0, 240, 255, 0.14); color: #00F0FF; }
        /* U5: breadcrumb — hiyerarşideki konum, gezinti geçmişi değil. */
        #breadcrumb {
            position: absolute;
            top: 8px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9;
            font-size: 11px;
            color: #8B949E;
            background: rgba(14, 20, 32, 0.82);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 3px 10px;
            display: none;
            max-width: 46vw;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
        #breadcrumb .crumb { cursor: pointer; color: #79C0FF; }
        #breadcrumb .crumb:hover { color: #00F0FF; text-decoration: underline; }
        #infoBox {
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 300px;
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
        <span id="legendToggle" onclick="toggleLegendPanel()" title="Tüm kategoriler, topluluk paleti ve filtreler">☰</span>
    </div>
    <div id="legendPanel">
        <div id="legendPanelItems"></div>
        <div id="graphControls">
            <div class="ctrl-group" id="grpTime">
                <span title="Kaydırıcıyı geçmişe çekince o tarihte henüz oluşmamış düğümler solar.">🕓 Zaman</span>
                <input type="range" id="timeSlider" min="0" max="100" value="100"
                       oninput="onTimeSlider(this.value)" title="Bellek zaman penceresi">
                <span id="timeLabel">şimdi</span>
            </div>
            <div class="ctrl-group" id="grpType">
                <span title="Yalnızca seçili düğüm türünü göster">🏷 Tür</span>
                <select id="typeFilter" onchange="onTypeFilter(this.value)">
                    <option value="">tümü</option>
                </select>
            </div>
            <div class="ctrl-group" id="grpImportance">
                <span title="Önem puanı bu eşiğin altındaki düğümler gizlenir">⭐ Önem</span>
                <input type="range" id="importanceSlider" min="0" max="100" value="0"
                       oninput="onImportanceSlider(this.value)" title="En düşük önem">
                <span id="importanceLabel">0.00</span>
            </div>
            <div class="ctrl-group" id="grpValid">
                <label title="Geçersizleştirilmiş (t_valid_to dolu) düğümleri gizler.">
                    <input type="checkbox" id="onlyValid" checked onchange="onOnlyValid(this.checked)">
                    yalnızca geçerli
                </label>
            </div>
            <div class="ctrl-group" id="grpCommunity">
                <button class="ctrl-btn" style="width:auto; padding:0 8px;" onclick="collapseAllCommunities()"
                        title="Bütün toplulukları kapat (açılış görünümü)">⊟ toplulukları kapat</button>
            </div>
        </div>
    </div>
    <div id="breadcrumb"></div>
    <div id="searchBox">
        <input id="searchInput" type="text" placeholder="Ara (Ctrl+F) — Esc kapatır" oninput="onSearchInput(this.value)">
        <div id="searchResults"></div>
    </div>
    <div id="controls">
        <button class="ctrl-btn" onclick="toggleSearch()" title="Ara (Ctrl+F)">🔍</button>
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

        // Faz 8 / U9: ölçüm kancası. QWebEngine içinden
        // page.runJavaScript("window.__graphStats") ile okunur; kare süresi,
        // görünür düğüm/etiket sayısı ve yerleşim yayılımı buradan raporlanır.
        window.__graphStats = {
            nodes: nodes.length, links: links.length,
            simNodes: 0, simLinks: 0, drawnNodes: 0, drawnLinks: 0,
            labels: 0, labelMs: 0, physMs: 0, drawMs: 0, frameMs: 0,
            zoom: 1, band: 0, worldW: 0, worldH: 0, frames: []
        };

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
        let userAdjustedView = false;
        let settledFitDone = false;
        let isPanning = false;
        let panStartX = 0;
        let panStartY = 0;

        const activeCategories = {
            'ego': true, 'hub': true, 'project': true, 'skill': true,
            'subbranch': true, 'mcp': true, 'mcp-tool': true, 'cognitive': true,
            'semantic': true, 'episodic': true, 'procedural': true,
            'Reports': true, 'obsidian': true, 'DailyNotes': true,
            'office': true, 'agent': true, 'query': true,
            'hub-offices': true, 'concept': true, 'community': true, 'entity': true
        };

        // ---- Faz 5.6: çift zamanlı bellek kontrolleri ----
        function parseGraphTime(v) {
            if (v === null || v === undefined || v === '') return null;
            if (typeof v === 'number') return v < 1e11 ? v * 1000 : v;
            const parsed = Date.parse(String(v));
            return isNaN(parsed) ? null : parsed;
        }

        let hasTimeData = false;
        let hasImportanceData = false;
        let hasValidityData = false;
        let hasCommunityData = false;
        const nodeTypes = [];
        const communityMembers = new Map();

        nodes.forEach(n => {
            n._tFrom = parseGraphTime(n.t_valid_from);
            n._tTo = parseGraphTime(n.t_valid_to);
            n._imp = (typeof n.importance === 'number') ? n.importance : null;
            n._type = n.type || '';
            if (n._tFrom !== null) hasTimeData = true;
            if (n._tTo !== null) hasValidityData = true;
            if (n._imp !== null) hasImportanceData = true;
            if (n._type && nodeTypes.indexOf(n._type) < 0) nodeTypes.push(n._type);
            if (n.group === 'community') {
                hasCommunityData = true;
                if (typeof n.member_count === 'number' && n.member_count > 0) {
                    n.val = Math.max(n.val || 12, 12 + Math.log(1 + n.member_count) * 6);
                }
            }
        });

        const communityIds = new Set();
        nodes.forEach(n => { if (n.group === 'community') communityIds.add(String(n.id)); });

        function memberCommunityOf(n) {
            if (!n || n.group === 'community') return null;
            if (n.community_id) return String(n.community_id);
            if (n.parent_hub && communityIds.has(String(n.parent_hub))) return String(n.parent_hub);
            return n._memberOf || null;
        }

        links.forEach(l => {
            if (!l || l.type !== 'member_of') return;
            const src = String(l.source && l.source.id ? l.source.id : l.source);
            const dst = String(l.target && l.target.id ? l.target.id : l.target);
            if (communityIds.has(dst)) {
                const node = nodeMap.get(src);
                if (node) node._memberOf = dst;
            }
        });
        nodes.forEach(n => {
            const cid = memberCommunityOf(n);
            if (cid) communityMembers.set(cid, (communityMembers.get(cid) || 0) + 1);
        });

        let timeMin = Infinity, timeMax = -Infinity;
        nodes.forEach(n => {
            if (n._tFrom !== null) {
                if (n._tFrom < timeMin) timeMin = n._tFrom;
                if (n._tFrom > timeMax) timeMax = n._tFrom;
            }
        });
        if (!isFinite(timeMin) || !isFinite(timeMax) || timeMax <= timeMin) hasTimeData = false;

        const expandedCommunities = new Set();
        let timeCursor = 1.0;
        let minImportance = 0.0;
        let typeFilter = '';
        let onlyValid = true;

        function timeCursorMs() {
            if (!hasTimeData) return Infinity;
            return timeMin + (timeMax - timeMin) * timeCursor;
        }
        function isOutsideTimeWindow(n) {
            if (!hasTimeData || n._tFrom === null) return false;
            return n._tFrom > timeCursorMs();
        }
        function isInvalidated(n) {
            return hasValidityData && n._tTo !== null && n._tTo <= timeCursorMs();
        }
        function isCollapsedMember(n) {
            if (!hasCommunityData) return false;
            const cid = memberCommunityOf(n);
            return !!cid && !expandedCommunities.has(cid);
        }
        function toggleCommunity(id) {
            const key = String(id);
            if (expandedCommunities.has(key)) expandedCommunities.delete(key);
            else expandedCommunities.add(key);
            relayoutAndFit(0.6, false);
            return expandedCommunities.has(key);
        }
        function collapseAllCommunities() {
            expandedCommunities.clear();
            relayoutAndFit(0.6, false);
        }
        function onTimeSlider(value) {
            timeCursor = Math.max(0, Math.min(1, Number(value) / 100));
            const label = document.getElementById('timeLabel');
            if (label) {
                if (!hasTimeData) label.textContent = 'veri yok';
                else if (timeCursor >= 1) label.textContent = 'şimdi';
                else label.textContent = new Date(timeCursorMs()).toISOString().slice(0, 10);
            }
            requestRender();
        }
        function onImportanceSlider(value) {
            minImportance = Math.max(0, Math.min(1, Number(value) / 100));
            const label = document.getElementById('importanceLabel');
            if (label) label.textContent = minImportance.toFixed(2);
            relayoutAndFit(0.4, false);
        }
        function onTypeFilter(value) {
            typeFilter = String(value || '');
            relayoutAndFit(0.4, false);
        }
        function onOnlyValid(checked) {
            onlyValid = !!checked;
            requestRender();
        }

        // ---- Faz 6: ağaç yapısı, seçim ve dal izolasyonu ----
        const treeChildren = new Map();
        const treeParent = new Map();
        const neighborIds = new Map();

        function addNeighbor(a, b) {
            let s = neighborIds.get(a);
            if (!s) { s = new Set(); neighborIds.set(a, s); }
            s.add(b);
        }

        links.forEach(l => {
            const s = l.sourceNode, t = l.targetNode;
            if (!s || !t) return;
            if (l.is_catalog_link) return;
            addNeighbor(s.id, t.id);
            addNeighbor(t.id, s.id);
            if (l.is_tree_link) {
                let kids = treeChildren.get(s.id);
                if (!kids) { kids = []; treeChildren.set(s.id, kids); }
                kids.push(t.id);
                if (!treeParent.has(t.id)) treeParent.set(t.id, s.id);
            }
        });

        // Kenar çifti indeksi: parent_hub ile türetilen ebeveynlikler için
        // sentetik ağaç kenarı üretilir. Aksi hâlde (bu kasada alt dalların bir
        // kısmı) düğüm ekranda ebeveynine bağlanmadan yalnız duruyordu.
        const linkPairs = new Set();
        links.forEach(l => {
            if (!l.sourceNode || !l.targetNode) return;
            linkPairs.add(l.sourceNode.id + '>' + l.targetNode.id);
            linkPairs.add(l.targetNode.id + '>' + l.sourceNode.id);
        });
        nodes.forEach(n => {
            if (!treeParent.has(n.id) && n.parent_hub && nodeMap.has(String(n.parent_hub))) {
                const pid = String(n.parent_hub);
                treeParent.set(n.id, pid);
                let kids = treeChildren.get(pid);
                if (!kids) { kids = []; treeChildren.set(pid, kids); }
                if (kids.indexOf(n.id) === -1) kids.push(n.id);
                if (!linkPairs.has(pid + '>' + n.id)) {
                    const parent = nodeMap.get(pid);
                    const syn = {
                        source: pid, target: n.id, is_tree_link: true, is_synthetic: true,
                        sourceNode: parent, targetNode: n
                    };
                    links.push(syn);
                    linkPairs.add(pid + '>' + n.id);
                    linkPairs.add(n.id + '>' + pid);
                    addNeighbor(pid, n.id);
                    addNeighbor(n.id, pid);
                }
            }
        });

        // ---- Faz 8: türetilmiş alanlar ----
        //
        // memory-rag-engineer `level, importance, degree, child_count,
        // short_label, community_id` alanlarını `build_unified_graph` çıktısına
        // ekliyor. Alanlar HENÜZ GELMEMİŞ OLABİLİR: geldiyse tercih edilir,
        // gelmediyse burada türetilir (level ağaç derinliğinden, degree kenar
        // sayımından, short_label ad kırpmasından). İki durumda da aşağıdaki
        // kod tek bir alan adına (`_level`, `_deg`, `_imp`, `_short`) bakar.
        const STRUCTURAL_GROUPS = {
            'ego': 1, 'hub': 1, 'hub-offices': 1, 'project': 1, 'skill': 1,
            'subbranch': 1, 'mcp': 1, 'office': 1, 'agent': 1, 'community': 1,
            'cognitive': 1
        };

        const GROUP_LEVEL = {
            'ego': 0, 'hub': 1, 'hub-offices': 1,
            'project': 2, 'skill': 2, 'mcp': 2, 'office': 2, 'community': 2, 'cognitive': 2,
            'subbranch': 3, 'agent': 3
        };

        const degreeCount = new Map();
        links.forEach(l => {
            if (l.is_catalog_link) return;
            const s = l.sourceNode, t = l.targetNode;
            if (!s || !t || s === t) return;
            degreeCount.set(s.id, (degreeCount.get(s.id) || 0) + 1);
            degreeCount.set(t.id, (degreeCount.get(t.id) || 0) + 1);
        });

        function treeDepth(id) {
            let d = 0, cur = id, guard = 0;
            while (guard++ < 64) {
                const p = treeParent.get(cur);
                if (!p || p === cur) break;
                d++; cur = p;
            }
            return d;
        }

        // `Gorev_<yetenek>_<tarih>_<konu>` kalıbından konuya odaklı kısa etiket.
        const NEWLINE_RE = new RegExp('[' + String.fromCharCode(13) + String.fromCharCode(10) + ']+', 'g');
        function flattenName(name) {
            return String(name || '').replace(NEWLINE_RE, ' ').replace(/[ ]{2,}/g, ' ').trim();
        }
        function shortenLabel(name) {
            let s = flattenName(name);
            if (s.indexOf('Gorev_') === 0 || s.indexOf('Görev_') === 0) {
                const parts = s.split('_');
                if (parts.length >= 3) s = parts.slice(2).join(' ').trim() || s;
            }
            s = s.replace(/^[0-9]{4}-[0-9]{2}-[0-9]{2}[ _-]*/, '');
            if (s.length > 28) s = s.substring(0, 27).trim() + '…';
            return s || String(name || '');
        }

        const shortLabelSeen = new Map();
        let maxDegree = 1, maxChildren = 1;
        nodes.forEach(n => {
            const deg = (typeof n.degree === 'number') ? n.degree : (degreeCount.get(n.id) || 0);
            n._deg = deg;
            if (deg > maxDegree) maxDegree = deg;
            const kids = treeChildren.get(n.id);
            n._childCount = (typeof n.child_count === 'number') ? n.child_count : (kids ? kids.length : 0);
            if (n._childCount > maxChildren) maxChildren = n._childCount;
        });
        nodes.forEach(n => {
            if (typeof n.level === 'number') n._level = n.level;
            else if (!STRUCTURAL_GROUPS[n.group]) {
                // Yaprak (rapor/anı/araç): kasadaki ağaç derinliği 3'te düz
                // olduğu için derinlik yaprak ayrımı yapmaz; grup yapar.
                n._level = 4;
            } else {
                const d = treeDepth(n.id);
                const g = GROUP_LEVEL[n.group];
                n._level = Math.min(3, (d > 0) ? d : (g === undefined ? 3 : g));
            }
            if (n._imp === null) {
                // Türetilmiş önem: seviye (küçük = önemli) + normalize derece.
                const lvlPart = 1 - Math.min(4, n._level) / 4;
                const degPart = Math.log(1 + n._deg) / Math.log(1 + maxDegree);
                n._imp = Math.max(0, Math.min(1, 0.6 * lvlPart + 0.4 * degPart));
                n._impDerived = true;
            }
            let sl = (typeof n.short_label === 'string' && n.short_label) ? n.short_label : shortenLabel(n.name);
            const seen = shortLabelSeen.get(sl);
            if (seen) {
                shortLabelSeen.set(sl, seen + 1);
                sl = sl + ' (' + (seen + 1) + ')';
            } else {
                shortLabelSeen.set(sl, 1);
            }
            n._short = sl;
            n._full = flattenName(n.name);
            n._cid = (n.community_id !== undefined && n.community_id !== null)
                ? String(n.community_id)
                : (memberCommunityOf(n) || (typeof n.community === 'number' ? 'c' + n.community : null));
        });

        // Kök hub (level 1 atası): sektör çekiminde ve breadcrumb'da kullanılır.
        function rootHubOf(id) {
            let cur = id, guard = 0, last = id;
            while (guard++ < 64) {
                const n = nodeMap.get(cur);
                if (n && n._level === 1) return cur;
                const p = treeParent.get(cur);
                if (!p || p === cur) break;
                last = cur; cur = p;
            }
            return (nodeMap.get(cur) && nodeMap.get(cur)._level === 1) ? cur : last;
        }
        const hubIds = nodes.filter(n => n._level === 1).map(n => n.id).sort();
        nodes.forEach(n => { n._rootHub = rootHubOf(n.id); n._sector = null; });

        // U1 sektör çekimi: her düğüm ebeveyninin açı diliminden alt ağaç
        // büyüklüğü oranında pay alır (klasik ağırlıklı radyal ağaç). Kardeş
        // dallar açısal olarak ayrıldığı için bir dalın yaprakları komşu dalın
        // alanına akmaz ve ağaç kenarları birbirini kesmez.
        const subtreeSize = new Map();
        const treeRoots = [];
        (function computeSubtreeSizes() {
            const order = [];
            const seen = new Set();
            nodes.forEach(n => { if (!treeParent.has(n.id)) treeRoots.push(n.id); });
            const stack = treeRoots.slice();
            while (stack.length) {
                const cur = stack.pop();
                if (seen.has(cur)) continue;
                seen.add(cur);
                order.push(cur);
                const kids = treeChildren.get(cur);
                if (kids) for (let i = 0; i < kids.length; i++) if (!seen.has(kids[i])) stack.push(kids[i]);
            }
            for (let i = order.length - 1; i >= 0; i--) {
                const kids = treeChildren.get(order[i]);
                let s = 1;
                if (kids) for (let j = 0; j < kids.length; j++) s += (subtreeSize.get(kids[j]) || 1);
                subtreeSize.set(order[i], s);
            }
        })();

        (function assignSectors() {
            let total = 0;
            treeRoots.forEach(id => { total += (subtreeSize.get(id) || 1); });
            if (total <= 0) total = 1;
            const queue = [];
            let a0 = 0;
            treeRoots.forEach(id => {
                const span = (subtreeSize.get(id) || 1) / total * Math.PI * 2;
                queue.push([id, a0, a0 + span]);
                a0 += span;
            });
            let guard = 0;
            while (queue.length && guard++ < 500000) {
                const item = queue.shift();
                const id = item[0], s = item[1], e = item[2];
                const n = nodeMap.get(id);
                if (n) { n._a0 = s; n._a1 = e; n._sector = (s + e) / 2; }
                const kids = treeChildren.get(id);
                if (!kids || !kids.length) continue;
                let tot = 0;
                for (let i = 0; i < kids.length; i++) tot += (subtreeSize.get(kids[i]) || 1);
                let cur = s;
                const sorted = kids.slice().sort();
                for (let i = 0; i < sorted.length; i++) {
                    const span = (subtreeSize.get(sorted[i]) || 1) / Math.max(1, tot) * (e - s);
                    queue.push([sorted[i], cur, cur + span]);
                    cur += span;
                }
            }
        })();

        function computeBranchSet(rootId) {
            const out = new Set();
            if (!rootId || !nodeMap.has(rootId)) return out;
            const queue = [rootId];
            while (queue.length) {
                const cur = queue.shift();
                if (out.has(cur)) continue;
                out.add(cur);
                const kids = treeChildren.get(cur);
                if (kids) for (let i = 0; i < kids.length; i++) queue.push(kids[i]);
            }
            let p = treeParent.get(rootId);
            let guard = 0;
            while (p && guard++ < 64) { out.add(p); p = treeParent.get(p); }
            const nb = neighborIds.get(rootId);
            if (nb) nb.forEach(id => out.add(id));
            return out;
        }

        let selectedNodeId = null;
        let isolatedIds = null;

        function recomputeIsolation() {
            isolatedIds = (isIsolated && selectedNodeId) ? computeBranchSet(selectedNodeId) : null;
        }

        // ---- Faz 8 / U2: dört bantlı LOD ----
        //
        // Tek eşik (58 -> 1145 düğüm) yerine dört bant: uzak / harita / dal /
        // yakın. ZMLT tutarlılığı: bir bantta görünen düğüm daha yakın bantlarda
        // KAYBOLMAZ (maxLevel monoton artar). Geçişler sert değil: 0,1'lik ara
        // bantta α-karışımıyla belirir, benzetim yeniden ısıtılmaz.
        const LOD_FAR = 0.25;
        const LOD_MAP = 0.75;
        const LOD_BRANCH = 1.2;
        const LOD_FADE = 0.10;
        // Geriye uyum: eski tek eşik adı korunur (yaprakların açıldığı bant).
        const DETAIL_ZOOM = LOD_MAP;

        function lodBand(z) {
            if (z < LOD_FAR) return 0;
            if (z < LOD_MAP) return 1;
            if (z < LOD_BRANCH) return 2;
            return 3;
        }
        const BAND_MAX_LEVEL = [2, 3, 4, 4];
        function bandMaxLevel() { return BAND_MAX_LEVEL[lodBand(zoom)]; }

        // Düğümün belirdiği zoom eşiği: α-karışımı bunun etrafında yapılır.
        function appearZoom(n) {
            if (n._level <= 2) return 0;
            if (n._level === 3) return LOD_FAR;
            return LOD_MAP;
        }
        function lodFade(n) {
            // Kullanıcının açtığı dal / izolasyon kümesi LOD solmasına tabi
            // değildir: dala sığdırma zoom'u eşiğin altında kalsa bile yapraklar
            // görünür kalır.
            if (isExplicitlyShown(n)) return 1;
            const az = appearZoom(n);
            if (az <= 0) return 1;
            if (zoom >= az + LOD_FADE) return 1;
            if (zoom <= az) return 0;
            return (zoom - az) / LOD_FADE;
        }

        const structuralCount = nodes.filter(n => STRUCTURAL_GROUPS[n.group]).length;
        const detailsAlwaysOn = structuralCount < 8;
        const expandedBranches = new Set();

        function isDetailNode(n) {
            return !STRUCTURAL_GROUPS[n.group] || n._level >= 4;
        }
        function detailsGloballyVisible() {
            return detailsAlwaysOn || zoom >= DETAIL_ZOOM;
        }
        // Kullanıcı bu düğümü açıkça açtı mı? (dal açma, izolasyon, seçim)
        function isExplicitlyShown(n) {
            if (isolatedIds && isolatedIds.has(n.id)) return true;
            if (expandedBranches.size === 0) return false;
            if (expandedBranches.has(n.id)) return true;
            if (n.parent_hub && expandedBranches.has(String(n.parent_hub))) return true;
            if (n.skill_hub && expandedBranches.has(String(n.skill_hub))) return true;
            const p = treeParent.get(n.id);
            return !!(p && expandedBranches.has(p));
        }

        function isDetailShown(n) {
            if (detailsAlwaysOn) return true;
            if (isExplicitlyShown(n)) return true;
            return n._level <= bandMaxLevel();
        }

        let lastDetailState = null;
        function syncDetailState() {
            const cur = lodBand(zoom);
            if (lastDetailState === null) { lastDetailState = cur; return false; }
            if (cur !== lastDetailState) {
                lastDetailState = cur;
                simDirty = true;
                return true;
            }
            return false;
        }

        function toggleBranchExpansion(id) {
            const key = String(id);
            if (expandedBranches.has(key)) expandedBranches.delete(key);
            else expandedBranches.add(key);
        }

        function isNodeVisible(n) {
            if (!n) return false;
            if (isolatedIds && !isolatedIds.has(n.id)) return false;
            if (!isCategoryActive(n.group)) return false;
            if (typeFilter && n._type && n._type !== typeFilter) return false;
            if (minImportance > 0 && n._imp !== null && !n._impDerived && n._imp < minImportance) return false;
            if (isCollapsedMember(n)) return false;
            if (isDetailNode(n) && !isDetailShown(n)) return false;
            return true;
        }

        function nodeAlphaFactor(n) {
            if (isInvalidated(n)) return onlyValid ? 0.10 : 0.45;
            if (isOutsideTimeWindow(n)) return 0.12;
            return 1.0;
        }

        function isCategoryActive(group) {
            if (!group) return true;
            if (group === 'subbranch' && activeCategories['skill'] === false) return false;
            if ((group === 'semantic' || group === 'episodic' || group === 'procedural')
                && activeCategories['cognitive'] === false) return false;
            if (group === 'mcp-tool' && activeCategories['mcp'] === false) return false;
            if ((group === 'DailyNotes' || group === 'obsidian')
                && activeCategories['cognitive'] === false) return false;
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
            recomputeIsolation();
            userAdjustedView = false;
            relayoutAndFit(1.0, true);
            fitToView();
        }

        function setSelectedNode(id) {
            selectedNodeId = id ? String(id) : null;
            if (selectedNodeId && !expandedBranches.has(selectedNodeId)) {
                expandedBranches.add(selectedNodeId);
            }
            recomputeIsolation();
            updateBreadcrumb();
            userAdjustedView = false;
            relayoutAndFit(0.7, true);
            fitToView();
        }

        function setScope(newScope) {
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
            if (el && el.classList) el.classList.toggle('dimmed', !newState);
            document.querySelectorAll('[data-cat="' + cat + '"]').forEach(e => {
                e.classList.toggle('dimmed', !newState);
            });
            relayoutAndFit(0.5, false);
        }

        function updateDimensions() {
            width = canvas.width = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0, 300);
            height = canvas.height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0, 250);
            requestRender();
        }
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
            'ego': '#00F0FF', 'hub': '#79C0FF', 'project': '#388BFD', 'skill': '#00FF9D',
            'subbranch': '#FF79C6', 'mcp': '#F778BA', 'mcp-tool': '#D2A8FF',
            'cognitive': '#7EE787', 'semantic': '#7EE787', 'episodic': '#FFB300',
            'procedural': '#58A6FF', 'Reports': '#FF0055', 'DailyNotes': '#E3B341',
            'obsidian': '#BC8CFF', 'office': '#FFB000', 'agent': '#2DD4BF',
            'query': '#C792EA', 'hub-offices': '#FFC94D', 'concept': '#9BE9A8',
            'entity': '#8CC8FF', 'community': '#FFD166'
        };

        // U6: renk körlüğüne güvenli paletler. OKABE_ITO kategori yedeği
        // (tabloda olmayan grup), TOL_12 ise topluluk tonlarıdır: 88 topluluğu
        // altın açıyla 88 tona dağıtmak yerine 12 ayrık ton döngüsü kullanılır.
        const OKABE_ITO = ['#E69F00', '#56B4E9', '#009E73', '#F0E442',
                           '#0072B2', '#D55E00', '#CC79A7', '#999999'];
        const TOL_12 = ['#332288', '#88CCEE', '#44AA99', '#117733', '#999933', '#DDCC77',
                        '#CC6677', '#882255', '#AA4499', '#6699CC', '#DDAA33', '#BB5566'];

        const groupIcons = {
            'office': '🏢', 'agent': '🤖', 'query': '🔎', 'hub-offices': '🏢',
            'concept': '📗', 'entity': '🏷', 'community': '🔮'
        };
        function getNodeIcon(group) { return groupIcons[group] || ''; }
        function getNodeColor(group) {
            if (colors[group]) return colors[group];
            return OKABE_ITO[Math.abs(hashSeed(String(group || ''))) % OKABE_ITO.length];
        }

        function communityIndex(n) {
            if (typeof n.community === 'number') return n.community;
            if (n._cid) return Math.abs(hashSeed(String(n._cid))) % TOL_12.length;
            return 0;
        }
        function communityColor(n) { return TOL_12[communityIndex(n) % TOL_12.length]; }
        function communityTint(n, a) {
            const hex = communityColor(n);
            const r = parseInt(hex.substring(1, 3), 16);
            const g = parseInt(hex.substring(3, 5), 16);
            const b = parseInt(hex.substring(5, 7), 16);
            return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
        }

        // ---- U3: efsane (tek satır, yalnız dolu kategoriler + sayılar) ----
        const LEGEND_DEFS = [
            ['ego', 'Çekirdek', ['ego']],
            ['hub', 'Ana Hublar', ['hub']],
            ['project', 'Projeler', ['project']],
            ['skill', 'Yetenekler', ['skill']],
            ['subbranch', 'Alt Dallar', ['subbranch']],
            ['mcp', 'MCP', ['mcp', 'mcp-tool']],
            ['cognitive', 'Bilişsel Bellek', ['cognitive', 'semantic', 'episodic', 'procedural', 'obsidian', 'DailyNotes']],
            ['Reports', 'Raporlar', ['Reports']],
            ['office', '🏢 Ofisler', ['office']],
            ['agent', '🤖 Ajanlar', ['agent']],
            ['query', '🔎 Sorgular', ['query']],
            ['hub-offices', '🏢 Ofis Kümesi', ['hub-offices']],
            ['concept', '📗 Kavramlar', ['concept']],
            ['entity', '🏷 Varlıklar', ['entity']],
            ['community', '🔮 Topluluklar', ['community']]
        ];

        function legendCounts() {
            const counts = new Map();
            nodes.forEach(n => counts.set(n.group, (counts.get(n.group) || 0) + 1));
            return counts;
        }

        function buildLegend() {
            const counts = legendCounts();
            const bar = document.getElementById('legend');
            const panel = document.getElementById('legendPanelItems');
            if (!bar || !panel || typeof document.createElement !== 'function') return;
            const filled = [];
            LEGEND_DEFS.forEach(def => {
                let total = 0;
                def[2].forEach(g => { total += (counts.get(g) || 0); });
                // Boş kategori hiç çizilmez: bu kasada 0 düğümlü 4 kategori
                // efsanenin yarısını kaplıyordu.
                if (total > 0) filled.push([def[0], def[1], total]);
            });
            filled.sort((a, b) => b[2] - a[2]);
            const mk = (cat, label, total) => {
                const el = document.createElement('div');
                el.className = 'legend-item';
                el.setAttribute('data-cat', cat);
                el.onclick = function () { toggleCategory(cat, el); };
                const dot = document.createElement('span');
                dot.className = 'dot';
                dot.style.background = getNodeColor(cat);
                el.appendChild(dot);
                const txt = document.createElement('span');
                txt.textContent = label;
                el.appendChild(txt);
                const cnt = document.createElement('span');
                cnt.className = 'legend-count';
                cnt.textContent = String(total);
                el.appendChild(cnt);
                return el;
            };
            // Şerit yalnız en kalabalık 5 kategoriyi gösterir; gerisi panelde.
            filled.slice(0, 5).forEach(f => bar.appendChild(mk(f[0], f[1], f[2])));
            if (filled.length > 5) {
                const more = document.createElement('span');
                more.className = 'legend-count';
                more.textContent = '+' + (filled.length - 5);
                bar.appendChild(more);
            }
            filled.forEach(f => panel.appendChild(mk(f[0], f[1], f[2])));
            window.__graphStats.legendCategories = filled.length;
        }

        function toggleLegendPanel() {
            const panel = document.getElementById('legendPanel');
            if (panel && panel.classList) panel.classList.toggle('open');
        }

        function initGraphControls() {
            const setDisabled = (groupId, inputId, disabled) => {
                const group = document.getElementById(groupId);
                if (group && group.classList) group.classList.toggle('disabled', disabled);
                const input = document.getElementById(inputId);
                if (input) input.disabled = disabled;
            };
            setDisabled('grpTime', 'timeSlider', !hasTimeData);
            setDisabled('grpImportance', 'importanceSlider', !hasImportanceData);
            setDisabled('grpValid', 'onlyValid', !hasValidityData);
            setDisabled('grpType', 'typeFilter', nodeTypes.length === 0);
            const community = document.getElementById('grpCommunity');
            if (community && community.classList) community.classList.toggle('disabled', !hasCommunityData);
            // Hiçbir kontrol etkin değilse şerit tamamen gizlenir: kullanıcı
            // çalışmayan 5 kontrol görmesin.
            const strip = document.getElementById('graphControls');
            const anyLive = hasTimeData || hasImportanceData || hasValidityData || hasCommunityData || nodeTypes.length > 0;
            if (strip && strip.classList) strip.classList.toggle('empty', !anyLive);
            const select = document.getElementById('typeFilter');
            if (select && select.appendChild && typeof document.createElement === 'function') {
                nodeTypes.slice().sort().forEach(t => {
                    const option = document.createElement('option');
                    option.value = t;
                    option.textContent = t;
                    select.appendChild(option);
                });
            }
            const label = document.getElementById('timeLabel');
            if (label) label.textContent = hasTimeData ? 'şimdi' : 'veri yok';
        }
        buildLegend();
        initGraphControls();

        // ⟲ düğmesi
        function resetView() {
            userAdjustedView = false;
            updateDimensions();
            fitToView();
        }

        function applyZoom(newZoom, ax, ay) {
            newZoom = Math.max(0.05, Math.min(4.5, newZoom));
            if (newZoom === zoom) return;
            const wasBand = lodBand(zoom);
            panX = ax - (ax - panX) * (newZoom / zoom);
            panY = ay - (ay - panY) * (newZoom / zoom);
            zoom = newZoom;
            userAdjustedView = true;
            if (isPanning) {
                panStartX = ax - panX;
                panStartY = ay - panY;
            }
            if (lodBand(zoom) !== wasBand) {
                // U2: bant değişince yalnızca görünür küme tazelenir. Benzetim
                // YENİDEN ISITILMAZ (eski davranış alpha'yı 0,5'e çekip yerleşimi
                // sıfırlıyordu); yeni yapraklar ebeveynlerinin yanında belirir.
                lastDetailState = lodBand(zoom);
                relayoutGraph();
            }
            requestRender();
        }

        // ---- Kuvvet yerleşimi (U1) ----
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

        // U1: yay hedefleri kısaldı (gövde 140, yaprak 60) ve sertlik d3
        // kuralıyla (1/min(derece)) normalize ediliyor.
        const LINK_KINDS = {
            trunk: { distance: 140, strength: 0.50 },
            tree: { distance: 60, strength: 0.50 },
            wikilink: { distance: 95, strength: 0.22 },
            similarity: { distance: 46, strength: 0.35 }
        };
        const TRUNK_LEVELS = 2;

        function linkKind(l) {
            if (l.is_similarity_link) return 'similarity';
            if (l.is_tree_link) {
                const t = l.targetNode;
                return (t && t._level <= TRUNK_LEVELS) ? 'trunk' : 'tree';
            }
            return 'wikilink';
        }

        // ForceAtlas2 tarzı derece ağırlıklı itme: sabit -230 yerine
        // -30 * (1 + ln(1 + derece)). distanceMax 400: uzak düğümler birbirini
        // itmez, dünya şişmez.
        const CHARGE_BASE = -30;
        const DISTANCE_MAX = 400;
        const DISTANCE_MAX_2 = DISTANCE_MAX * DISTANCE_MAX;
        const THETA2 = 0.81;
        const CENTER_PULL = 0.010;
        const VELOCITY_DECAY = 0.40;
        // forceRadial halkaları (level 1/2/3) ve sektör çekimi.
        const RING_R = [0, 260, 520, 780, 0];
        const RADIAL_STRENGTH = 0.10;
        const SECTOR_STRENGTH = 0.09;

        let simLinks = [];
        let simNodes = [];
        let simDirty = true;

        let positionsInitialized = false;
        function initNodePositions() {
            if (positionsInitialized) return;
            const cx = width / 2;
            const cy = height / 2;
            nodes.forEach(n => {
                n.vx = 0;
                n.vy = 0;
                if (n.group === 'ego') { n.x = cx; n.y = cy; return; }
                // U1: tohum konumu halka + sektör kuralına göre deterministik
                // üretilir; kuvvet benzetimi bunu organik hâle getirir.
                const ring = RING_R[Math.min(4, n._level)] || 0;
                const j = mulberry32(hashSeed(n.id + '|seed'));
                if (n._sector !== null) {
                    // Tohum: kendi açı dilimi içinde, seviyesinin halkasında.
                    const wedge = Math.max(0.002, (n._a1 - n._a0));
                    const ang = n._a0 + wedge * (0.15 + 0.7 * j());
                    let r = ring;
                    if (r <= 0) {
                        const parent = nodeMap.get(treeParent.get(n.id));
                        const base = parent ? (RING_R[Math.min(4, parent._level)] || 780) : 780;
                        r = base + 90 + j() * 90;
                    }
                    n.x = cx + Math.cos(ang) * r;
                    n.y = cy + Math.sin(ang) * r;
                } else {
                    const ang = j() * Math.PI * 2;
                    const r = 140 + j() * 420;
                    n.x = cx + Math.cos(ang) * r;
                    n.y = cy + Math.sin(ang) * r;
                }
                const jj = mulberry32(hashSeed(n.id + '|j'));
                n.x += (jj() - 0.5) * 1.5;
                n.y += (jj() - 0.5) * 1.5;
            });
            links.forEach(l => {
                l.sourceNode = nodeMap.get(l.source);
                l.targetNode = nodeMap.get(l.target);
            });
            positionsInitialized = true;
        }

        function rebuildSimulation() {
            simNodes = [];
            const inSet = new Set();
            for (let i = 0; i < nodes.length; i++) {
                const n = nodes[i];
                if (!isNodeVisible(n)) continue;
                if (!isNodeInScope(n) && (isIsolated || currentScope !== 'all')) continue;
                simNodes.push(n);
                inSet.add(n.id);
                n._charge = CHARGE_BASE * (1 + Math.log(1 + n._deg)) * (1 + (n.val || 12) / 48);
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
                const w = (typeof l.weight === 'number') ? Math.max(0.3, Math.min(1.5, l.weight)) : 1;
                const ds = degree.get(l.sourceNode.id) || 1;
                const dt = degree.get(l.targetNode.id) || 1;
                l._k = (kind.strength * w) / Math.min(ds, dt);
                l._len = kind.distance + (l.sourceNode.val || 12) + (l.targetNode.val || 12);
                // Dissuade Hubs (ForceAtlas2): yüksek dereceli uç çevreye
                // itilmesin diye çekim o ucun derecesine bölünür; hafif uç
                // (yaprak) daha çok hareket eder.
                l._bias = ds / (ds + dt);
            }
            simDirty = false;
            window.__graphStats.simNodes = simNodes.length;
            window.__graphStats.simLinks = simLinks.length;
        }

        // ---- Barnes-Hut dörtlü ağacı ----
        let lastTree = null;
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
            lastTree = subdivide(list, x0, y0, x0 + w, y0 + w, 0);
            return lastTree;
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
                x0: x0, y0: y0, x1: x1, y1: y1, q: q,
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
            // distanceMax: hücre tamamen 400 biriminden uzaktaysa hiç itmez.
            const half = w * 0.71;
            if (d2 > (DISTANCE_MAX + half) * (DISTANCE_MAX + half)) return;
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
                if (dd > DISTANCE_MAX_2) continue;
                if (dd < 25) dd = 25;
                const f = (o._charge || 0) * k / dd;
                p.vx += ddx * f;
                p.vy += ddy * f;
            }
        }

        // ---- Izgara tabanlı çakışma çözümü (tamsayı anahtar, dize üretmez) ----
        function resolveCollisions(list) {
            let maxR = 12;
            for (let i = 0; i < list.length; i++) {
                const r = (list[i].val || 12) + 2;
                if (r > maxR) maxR = r;
            }
            const cell = maxR * 2;
            const grid = new Map();
            const cells = [];
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                const gx = Math.floor(p.x / cell) + 32768;
                const gy = Math.floor(p.y / cell) + 32768;
                const key = gx * 65536 + gy;
                let b = grid.get(key);
                if (!b) { b = []; grid.set(key, b); cells.push(key); }
                b.push(p);
            }
            for (let c = 0; c < cells.length; c++) {
                const key = cells[c];
                const bucket = grid.get(key);
                for (let ox = 0; ox <= 1; ox++) {
                    for (let oy = (ox === 0 ? 0 : -1); oy <= 1; oy++) {
                        const other = (ox === 0 && oy === 0) ? bucket : grid.get(key + ox * 65536 + oy);
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
            }
        }

        function relayoutGraph() {
            simDirty = true;
            rebuildSimulation();
            hitGridDirty = true;
            hullCacheDirty = true;
        }

        function relayoutAndFit(alphaKick, refit) {
            relayoutGraph();
            alpha = Math.max(alpha, alphaKick || 0.6);
            settledFitDone = !refit;
            requestRender();
        }

        let alpha = 1.0;
        const alphaMin = 0.008;
        const alphaDecay = 0.0228;   // d3 varsayılanı: ~300 iterasyon

        function tickPhysics() {
            if (isPanning) return;
            if (alpha < alphaMin && !draggedNode) return;
            if (simDirty) rebuildSimulation();

            const t0 = performance.now();
            const cx = width / 2;
            const cy = height / 2;

            const egoNode = nodeMap.get('ego-entropy-core');
            if (egoNode && egoNode !== draggedNode) {
                egoNode.x = cx; egoNode.y = cy; egoNode.vx = 0; egoNode.vy = 0;
            }

            const list = simNodes;
            if (list.length === 0) { alpha *= (1 - alphaDecay); return; }

            // 1. Yaylar
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

            // 2. Karşılıklı itme (Barnes-Hut, distanceMax 400)
            const tree = buildQuadtree(list);
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.group === 'ego' || p === draggedNode) continue;
                applyCharge(tree, p, alpha);
            }

            // 3. forceRadial halkaları + sektör çekimi + merkez
            for (let i = 0; i < list.length; i++) {
                const p = list[i];
                if (p.group === 'ego' || p === draggedNode) continue;
                const dx0 = p.x - cx, dy0 = p.y - cy;
                const ring = RING_R[Math.min(4, p._level)] || 0;
                if (ring > 0) {
                    const d = Math.sqrt(dx0 * dx0 + dy0 * dy0) || 1;
                    const k = (ring - d) / d * RADIAL_STRENGTH * alpha;
                    p.vx += dx0 * k;
                    p.vy += dy0 * k;
                }
                if (p._sector !== null) {
                    // Sektör: dalın yaprakları başka dalın alanına akmasın.
                    const r = Math.sqrt(dx0 * dx0 + dy0 * dy0) || 1;
                    const tx = cx + Math.cos(p._sector) * r;
                    const ty = cy + Math.sin(p._sector) * r;
                    p.vx += (tx - p.x) * SECTOR_STRENGTH * alpha;
                    p.vy += (ty - p.y) * SECTOR_STRENGTH * alpha;
                }
                p.vx += (cx - p.x) * CENTER_PULL * alpha;
                p.vy += (cy - p.y) * CENTER_PULL * alpha;
            }

            // 4. Konum güncellemesi
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

            // 5. Çakışma
            resolveCollisions(list);
            resolveCollisions(list);

            alpha *= (1 - alphaDecay);
            hitGridDirty = true;
            hullCacheDirty = true;
            minimapDirty = true;
            window.__graphStats.physMs = performance.now() - t0;
        }

        // ---- U5: dörtlü ağaç / uzamsal ızgara ile hit-test ----
        //
        // Eski kod her mousemove'da 1145 düğümü doğrusal tarıyordu. Konumlar
        // yalnızca fizik tıkında değiştiği için ızgara "kirli" işaretlenir ve
        // en fazla kare başına bir kez yeniden kurulur.
        const HIT_CELL = 64;
        let hitGrid = new Map();
        let hitGridDirty = true;

        function rebuildHitGrid() {
            hitGrid = new Map();
            for (let i = 0; i < simNodes.length; i++) {
                const n = simNodes[i];
                const gx = Math.floor(n.x / HIT_CELL) + 32768;
                const gy = Math.floor(n.y / HIT_CELL) + 32768;
                const key = gx * 65536 + gy;
                let b = hitGrid.get(key);
                if (!b) { b = []; hitGrid.set(key, b); }
                b.push(n);
            }
            hitGridDirty = false;
        }

        function nodeAt(wx, wy) {
            if (hitGridDirty) rebuildHitGrid();
            const gx = Math.floor(wx / HIT_CELL) + 32768;
            const gy = Math.floor(wy / HIT_CELL) + 32768;
            let best = null, bestD = Infinity;
            for (let ox = -1; ox <= 1; ox++) {
                for (let oy = -1; oy <= 1; oy++) {
                    const b = hitGrid.get((gx + ox) * 65536 + (gy + oy));
                    if (!b) continue;
                    for (let i = 0; i < b.length; i++) {
                        const n = b[i];
                        const r = Math.max(n.val || 12, 4 / Math.max(zoom, 0.05)) + 3;
                        const dx = n.x - wx, dy = n.y - wy;
                        const d2 = dx * dx + dy * dy;
                        if (d2 < r * r && d2 < bestD) { bestD = d2; best = n; }
                    }
                }
            }
            return best;
        }

        // ---- U5: hover "dim" deseni (Sigma.js) ----
        let focusNode = null;
        let hop1 = null, hop2 = null;
        function computeFocusSets(n) {
            hop1 = new Set(); hop2 = new Set();
            if (!n) return;
            hop1.add(n.id);
            const nb = neighborIds.get(n.id);
            if (nb) nb.forEach(id => hop1.add(id));
            hop1.forEach(id => {
                const s = neighborIds.get(id);
                if (s) s.forEach(x => { if (!hop1.has(x)) hop2.add(x); });
            });
        }
        function dimFactor(n) {
            if (!focusNode) return 1;
            if (hop1 && hop1.has(n.id)) return 1;
            if (hop2 && hop2.has(n.id)) return 0.6;
            return 0.12;
        }

        // ---- U4: etiket motoru (öncelik + doluluk bit haritası + sprite) ----
        const LABEL_CELL = 8;          // doluluk bit haritası hücresi (px)
        const LABEL_GRID = 90;         // seyreltme ızgarası (px) — Sigma.js deseni
        const LABEL_GRID_SPARSE = 60;  // yalnız iskelet görünürken daha sık etiket
        const LABEL_BUDGET = 220;      // kare başına en çok etiket
        let labelBits = null;
        let labelBitsW = 0, labelBitsH = 0;
        let labelOrder = null;
        let placedLabels = [];

        function ensureLabelBits() {
            const w = Math.ceil(width / LABEL_CELL), h = Math.ceil(height / LABEL_CELL);
            if (!labelBits || w !== labelBitsW || h !== labelBitsH) {
                labelBitsW = w; labelBitsH = h;
                labelBits = new Uint8Array(w * h);
            } else {
                labelBits.fill(0);
            }
        }
        function bitsFree(x, y, w, h) {
            if (x < 0 || y < 0 || x + w > width || y + h > height) return false;
            const c0 = Math.floor(x / LABEL_CELL), c1 = Math.ceil((x + w) / LABEL_CELL);
            const r0 = Math.floor(y / LABEL_CELL), r1 = Math.ceil((y + h) / LABEL_CELL);
            for (let r = r0; r < r1; r++) {
                const base = r * labelBitsW;
                for (let c = c0; c < c1; c++) if (labelBits[base + c]) return false;
            }
            return true;
        }
        function bitsMark(x, y, w, h) {
            const c0 = Math.max(0, Math.floor(x / LABEL_CELL)), c1 = Math.min(labelBitsW, Math.ceil((x + w) / LABEL_CELL));
            const r0 = Math.max(0, Math.floor(y / LABEL_CELL)), r1 = Math.min(labelBitsH, Math.ceil((y + h) / LABEL_CELL));
            for (let r = r0; r < r1; r++) {
                const base = r * labelBitsW;
                for (let c = c0; c < c1; c++) labelBits[base + c] = 1;
            }
        }

        // Öncelik: level (küçük önce) -> importance -> degree. Bir kez hesaplanır.
        function ensureLabelOrder() {
            if (labelOrder) return;
            labelOrder = nodes.slice().sort((a, b) => {
                if (a._level !== b._level) return a._level - b._level;
                if (b._imp !== a._imp) return b._imp - a._imp;
                if (b._deg !== a._deg) return b._deg - a._deg;
                return a.id < b.id ? -1 : 1;
            });
        }

        // Metin bitmap önbelleği: fillText yerine drawImage.
        const spriteCache = new Map();
        function labelSprite(text, fontSize, weight, color) {
            const key = text + '|' + fontSize + '|' + weight + '|' + color;
            let sp = spriteCache.get(key);
            if (sp) return sp;
            const font = weight + ' ' + fontSize + 'px "Segoe UI Variable Text", "Segoe UI", "Inter", system-ui, sans-serif';
            let w = 0;
            try {
                ctx.save(); ctx.font = font; w = ctx.measureText(text).width; ctx.restore();
            } catch (e) { w = text.length * fontSize * 0.55; }
            const pad = 3;
            const cw = Math.ceil(w + pad * 2), ch = Math.ceil(fontSize + pad * 2 + 3);
            let cv = null;
            try {
                cv = document.createElement('canvas');
                cv.width = Math.max(1, cw); cv.height = Math.max(1, ch);
                const c2 = cv.getContext('2d');
                c2.font = font;
                c2.textBaseline = 'middle';
                // Pil dolgusu yerine koyu kontur "halo": uzak bakışta kutu
                // kalabalığı yapmaz, koyu zeminde okunur kalır.
                c2.lineWidth = 3;
                c2.strokeStyle = 'rgba(8, 11, 16, 0.92)';
                c2.strokeText(text, pad, ch / 2);
                c2.fillStyle = color;
                c2.fillText(text, pad, ch / 2);
            } catch (e) { cv = null; }
            sp = { canvas: cv, w: cw, h: ch, text: text, color: color, font: font };
            if (spriteCache.size > 900) spriteCache.clear();
            spriteCache.set(key, sp);
            return sp;
        }

        function labelStyleFor(n) {
            const lvl = Math.min(4, n._level);
            const size = [13, 12, 11.5, 11, 10][lvl];
            const weight = lvl === 0 ? '700' : (lvl <= 2 ? '600' : '400');
            return { size: size, weight: weight };
        }

        // Etiketleri yerleştirir ve çizer. Ekran koordinatlarında çalışır:
        // yazı boyutu zoom'dan bağımsız piksel sabittir.
        function drawLabels(viewNodes) {
            const t0 = performance.now();
            ensureLabelBits();
            ensureLabelOrder();
            placedLabels = [];
            const cellTaken = new Set();
            const band = lodBand(zoom);
            const cellSize = (band <= 1) ? LABEL_GRID_SPARSE : LABEL_GRID;
            const gridW = Math.ceil(width / cellSize) + 2;
            const minScreenR = [3, 3, 4, 5][band];
            const visSet = viewNodes;
            let placed = 0;
            for (let i = 0; i < labelOrder.length && placed < LABEL_BUDGET; i++) {
                const n = labelOrder[i];
                if (!visSet.has(n)) continue;
                const sx = n.x * zoom + panX;
                const sy = n.y * zoom + panY;
                if (sx < -40 || sy < -20 || sx > width + 40 || sy > height + 20) continue;
                const r = Math.max((n.val || 12) * zoom, 3);
                const isHovered = (n === hoveredNode);
                if (!isHovered) {
                    // Ekranda çok küçük kalan düğüme etiket yok (Sigma.js
                    // labelRenderedSizeThreshold) ve 90 px ızgarada bir etiket.
                    if (r < minScreenR) continue;
                    const cell = (Math.floor(sy / cellSize) * gridW) + Math.floor(sx / cellSize);
                    if (cellTaken.has(cell)) continue;
                    if (dimFactor(n) < 0.5) continue;
                }
                const st = labelStyleFor(n);
                // Yakın bantta tam ad, uzakta kısa etiket.
                const text = (isHovered || zoom >= LOD_BRANCH) ? n._full : n._short;
                if (!text) continue;
                const color = isHovered ? getNodeColor(n.group) : '#E6EDF3';
                const sp = labelSprite(text, st.size, st.weight, color);
                // Dört aday konum: sağ, sol, üst, alt.
                const cands = [
                    [sx + r + 5, sy - sp.h / 2],
                    [sx - r - 5 - sp.w, sy - sp.h / 2],
                    [sx - sp.w / 2, sy - r - 4 - sp.h],
                    [sx - sp.w / 2, sy + r + 4]
                ];
                let px = null, py = null;
                for (let c = 0; c < cands.length; c++) {
                    if (bitsFree(cands[c][0], cands[c][1], sp.w, sp.h)) {
                        px = cands[c][0]; py = cands[c][1]; break;
                    }
                }
                if (px === null) {
                    if (!isHovered) continue;
                    px = cands[0][0]; py = cands[0][1];
                }
                bitsMark(px, py, sp.w, sp.h);
                if (!isHovered) {
                    cellTaken.add((Math.floor(sy / cellSize) * gridW) + Math.floor(sx / cellSize));
                }
                placedLabels.push({ x: px, y: py, w: sp.w, h: sp.h, id: n.id });
                placed++;
                ctx.globalAlpha = Math.min(1, lodFade(n)) * (isHovered ? 1 : Math.max(0.35, dimFactor(n)));
                if (sp.canvas) {
                    ctx.drawImage(sp.canvas, Math.round(px), Math.round(py));
                } else {
                    ctx.font = sp.font;
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = color;
                    ctx.fillText(text, px + 3, py + sp.h / 2);
                }
                ctx.globalAlpha = 1;
            }
            window.__graphStats.labels = placedLabels.length;
            window.__graphStats.labelMs = performance.now() - t0;
        }

        // ---- U6: topluluk gövdeleri (convex hull + etiket + rozet) ----
        let hullCache = null;
        let hullCacheDirty = true;
        function convexHull(pts) {
            if (pts.length < 3) return pts;
            const p = pts.slice().sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
            const cross2 = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
            const lower = [];
            for (let i = 0; i < p.length; i++) {
                while (lower.length >= 2 && cross2(lower[lower.length - 2], lower[lower.length - 1], p[i]) <= 0) lower.pop();
                lower.push(p[i]);
            }
            const upper = [];
            for (let i = p.length - 1; i >= 0; i--) {
                while (upper.length >= 2 && cross2(upper[upper.length - 2], upper[upper.length - 1], p[i]) <= 0) upper.pop();
                upper.push(p[i]);
            }
            lower.pop(); upper.pop();
            return lower.concat(upper);
        }

        function computeHulls() {
            const groups = new Map();
            for (let i = 0; i < simNodes.length; i++) {
                const n = simNodes[i];
                if (n._level <= 1) continue;
                const cid = n._cid;
                if (!cid) continue;
                let g = groups.get(cid);
                if (!g) { g = []; groups.set(cid, g); }
                g.push(n);
            }
            const out = [];
            groups.forEach((members, cid) => {
                if (members.length < 6) return;
                const hull = convexHull(members.map(m => [m.x, m.y]));
                if (hull.length < 3) return;
                let cx = 0, cy = 0;
                members.forEach(m => { cx += m.x; cy += m.y; });
                const head = members.slice().sort((a, b) => b._imp - a._imp)[0];
                out.push({
                    cid: cid, hull: hull, size: members.length,
                    cx: cx / members.length, cy: cy / members.length,
                    color: communityColor(members[0]),
                    label: (head && head.community_label) ? String(head.community_label) : (head ? head._short : cid)
                });
            });
            out.sort((a, b) => b.size - a.size);
            hullCache = out.slice(0, 12);
            hullCacheDirty = false;
        }

        let hullBuiltAt = 0;
        function drawHulls() {
            const band = lodBand(zoom);
            if (band < 1 || band > 2) return;
            // Gövde hesabı benzetim sürerken her karede değil, en çok 250 ms'de
            // bir tazelenir: 1000 düğümde convex hull kare bütçesini yer.
            const now = performance.now();
            if ((hullCacheDirty && now - hullBuiltAt > 250) || !hullCache) {
                computeHulls();
                hullBuiltAt = now;
            }
            if (!hullCache) return;
            for (let i = 0; i < hullCache.length; i++) {
                const h = hullCache[i];
                ctx.beginPath();
                for (let j = 0; j < h.hull.length; j++) {
                    const p = h.hull[j];
                    if (j === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
                }
                ctx.closePath();
                ctx.globalAlpha = 0.08;
                ctx.fillStyle = h.color;
                ctx.fill();
                ctx.globalAlpha = 0.30;
                ctx.strokeStyle = h.color;
                ctx.lineWidth = 1.2 / zoom;
                ctx.stroke();
                ctx.globalAlpha = 1;
            }
        }

        function drawHullLabels() {
            const band = lodBand(zoom);
            if (band < 1 || band > 2 || !hullCache) return;
            for (let i = 0; i < hullCache.length; i++) {
                const h = hullCache[i];
                const sx = h.cx * zoom + panX, sy = h.cy * zoom + panY;
                if (sx < 0 || sy < 0 || sx > width || sy > height) continue;
                const txt = h.label + '  (' + h.size + ')';
                const sp = labelSprite(txt, 11, '600', h.color);
                const px = sx - sp.w / 2, py = sy - sp.h / 2;
                if (!bitsFree(px, py, sp.w, sp.h)) continue;
                bitsMark(px, py, sp.w, sp.h);
                ctx.globalAlpha = 0.9;
                if (sp.canvas) ctx.drawImage(sp.canvas, Math.round(px), Math.round(py));
                ctx.globalAlpha = 1;
            }
        }

        // ---- U7: mini harita (bitmap önbellekli) ----
        const MINIMAP_W = 160, MINIMAP_H = 110, MINIMAP_PAD = 12;
        let minimapCanvas = null;
        let minimapDirty = true;
        let minimapBox = null;   // dünya kutusu

        function minimapRect() {
            return { x: width - MINIMAP_W - MINIMAP_PAD, y: height - MINIMAP_H - MINIMAP_PAD - 36, w: MINIMAP_W, h: MINIMAP_H };
        }
        function buildMinimap() {
            let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
            const pts = [];
            for (let i = 0; i < simNodes.length; i++) {
                const n = simNodes[i];
                if (n._level > 3) continue;
                pts.push(n);
                if (n.x < x0) x0 = n.x;
                if (n.x > x1) x1 = n.x;
                if (n.y < y0) y0 = n.y;
                if (n.y > y1) y1 = n.y;
            }
            if (!pts.length || !isFinite(x0)) { minimapCanvas = null; minimapDirty = false; return; }
            const pad = 40;
            x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
            minimapBox = { x0: x0, y0: y0, x1: x1, y1: y1 };
            try {
                const cv = document.createElement('canvas');
                cv.width = MINIMAP_W; cv.height = MINIMAP_H;
                const c2 = cv.getContext('2d');
                c2.fillStyle = 'rgba(8, 11, 16, 0.86)';
                c2.fillRect(0, 0, MINIMAP_W, MINIMAP_H);
                c2.strokeStyle = '#1F2B42';
                c2.strokeRect(0.5, 0.5, MINIMAP_W - 1, MINIMAP_H - 1);
                const sc = Math.min(MINIMAP_W / (x1 - x0), MINIMAP_H / (y1 - y0));
                for (let i = 0; i < pts.length; i++) {
                    const n = pts[i];
                    c2.fillStyle = getNodeColor(n.group);
                    const mx = (n.x - x0) * sc, my = (n.y - y0) * sc;
                    const rr = n._level <= 1 ? 2.2 : 1.3;
                    c2.fillRect(mx - rr, my - rr, rr * 2, rr * 2);
                }
                minimapCanvas = cv;
                minimapBox.scale = sc;
            } catch (e) { minimapCanvas = null; }
            minimapDirty = false;
        }
        let minimapBuiltAt = 0;
        function drawMinimap() {
            const now = performance.now();
            if ((minimapDirty && now - minimapBuiltAt > 250) || !minimapCanvas) {
                buildMinimap();
                minimapBuiltAt = now;
            }
            if (!minimapCanvas || !minimapBox) return;
            const R = minimapRect();
            ctx.drawImage(minimapCanvas, R.x, R.y);
            // Görünüm dikdörtgeni
            const sc = minimapBox.scale;
            const vx0 = (-panX / zoom - minimapBox.x0) * sc;
            const vy0 = (-panY / zoom - minimapBox.y0) * sc;
            const vw = (width / zoom) * sc, vh = (height / zoom) * sc;
            ctx.save();
            ctx.beginPath();
            ctx.rect(R.x, R.y, R.w, R.h);
            ctx.clip();
            ctx.strokeStyle = '#00F0FF';
            ctx.lineWidth = 1;
            ctx.strokeRect(R.x + vx0, R.y + vy0, vw, vh);
            ctx.restore();
        }
        function minimapPan(mx, my) {
            if (!minimapBox || !minimapBox.scale) return false;
            const R = minimapRect();
            if (mx < R.x || my < R.y || mx > R.x + R.w || my > R.y + R.h) return false;
            const wx = minimapBox.x0 + (mx - R.x) / minimapBox.scale;
            const wy = minimapBox.y0 + (my - R.y) / minimapBox.scale;
            panX = width / 2 - wx * zoom;
            panY = height / 2 - wy * zoom;
            userAdjustedView = true;
            requestRender();
            return true;
        }

        // ---- Görünüm tweeni (U5: tıkla-dala-sığdır 250 ms) ----
        let tween = null;
        function tweenTo(z, px, py, ms) {
            tween = { z0: zoom, x0: panX, y0: panY, z1: z, x1: px, y1: py, t0: performance.now(), ms: ms || 250 };
            requestRender();
        }
        function stepTween() {
            if (!tween) return false;
            const k = Math.min(1, (performance.now() - tween.t0) / tween.ms);
            const e = k < 0.5 ? 2 * k * k : -1 + (4 - 2 * k) * k;
            zoom = tween.z0 + (tween.z1 - tween.z0) * e;
            panX = tween.x0 + (tween.x1 - tween.x0) * e;
            panY = tween.y0 + (tween.y1 - tween.y0) * e;
            if (k >= 1) { tween = null; syncDetailState(); relayoutGraph(); return false; }
            return true;
        }

        function boundsOf(list) {
            let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
            for (let i = 0; i < list.length; i++) {
                const n = list[i];
                if (typeof n.x !== 'number' || isNaN(n.x)) continue;
                if (n.x < x0) x0 = n.x;
                if (n.x > x1) x1 = n.x;
                if (n.y < y0) y0 = n.y;
                if (n.y > y1) y1 = n.y;
            }
            if (!isFinite(x0)) return null;
            return { x0: x0, y0: y0, x1: x1, y1: y1 };
        }

        // U3: sığdırma dikdörtgeninden örtüler (efsane, breadcrumb, mini harita,
        // düğmeler) düşülür; düğüm efsanenin altında kalmaz.
        function viewInsets() {
            const lg = document.getElementById('legend');
            const top = (lg && lg.offsetHeight ? lg.offsetHeight : 26) + 14;
            return { top: top, bottom: 46, left: 8, right: MINIMAP_W + 2 * MINIMAP_PAD };
        }

        function fitNodesToView(list, ms) {
            const b = boundsOf(list);
            if (!b) return;
            const ins = viewInsets();
            const availW = Math.max(80, width - ins.left - ins.right);
            const availH = Math.max(80, height - ins.top - ins.bottom);
            const spanX = Math.max(100, b.x1 - b.x0 + 100);
            const spanY = Math.max(100, b.y1 - b.y0 + 100);
            const z = Math.max(0.05, Math.min(1.85, Math.min(availW / spanX, availH / spanY) * 0.92));
            const midX = (b.x0 + b.x1) / 2, midY = (b.y0 + b.y1) / 2;
            const px = ins.left + availW / 2 - midX * z;
            const py = ins.top + availH / 2 - midY * z;
            if (ms) { tweenTo(z, px, py, ms); return; }
            zoom = z; panX = px; panY = py;
            syncDetailState();
            relayoutGraph();
            requestRender();
        }

        function fitToView() {
            if (isPanning) return;
            width = canvas.width = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0, 300);
            height = canvas.height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0, 250);
            const targetNodes = nodes.filter(n => isNodeVisible(n) && isNodeInScope(n));
            if (targetNodes.length === 0) return;
            fitNodesToView(targetNodes, 0);
        }

        function zoomIn() { applyZoom(zoom * 1.25, width / 2, height / 2); }
        function zoomOut() { applyZoom(zoom / 1.25, width / 2, height / 2); }

        // ---- U5: breadcrumb ----
        function ancestorChain(id) {
            const chain = [];
            let cur = id, guard = 0;
            while (cur && guard++ < 32) {
                chain.unshift(cur);
                cur = treeParent.get(cur);
            }
            return chain;
        }
        function updateBreadcrumb() {
            const el = document.getElementById('breadcrumb');
            if (!el) return;
            if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
                el.style.display = 'none';
                el.innerHTML = '';
                return;
            }
            const chain = ancestorChain(selectedNodeId);
            const parts = chain.map(id => {
                const n = nodeMap.get(id);
                const label = n ? n._short : id;
                return '<span class="crumb" onclick="focusNodeById(' + JSON.stringify(id).replace(/"/g, '&quot;') + ')">' + label + '</span>';
            });
            el.innerHTML = parts.join(' › ');
            el.style.display = 'block';
        }

        function focusNodeById(id) {
            const n = nodeMap.get(String(id));
            if (!n) return;
            selectedNodeId = n.id;
            expandedBranches.add(n.id);
            recomputeIsolation();
            relayoutGraph();
            updateBreadcrumb();
            const branch = [];
            computeBranchSet(n.id).forEach(bid => {
                const bn = nodeMap.get(bid);
                if (bn && isNodeVisible(bn)) branch.push(bn);
            });
            userAdjustedView = true;
            settledFitDone = true;
            fitNodesToView(branch.length ? branch : [n], 250);
        }

        // ---- U7: arama + yol göster ----
        let searchHighlight = null;
        let pathHighlight = null;

        function toggleSearch() {
            const box = document.getElementById('searchBox');
            if (!box || !box.classList) return;
            box.classList.toggle('open');
            const inp = document.getElementById('searchInput');
            if (box.classList.contains('open') && inp && inp.focus) inp.focus();
        }

        function searchNodes(q) {
            const needle = String(q || '').toLocaleLowerCase('tr');
            if (needle.length < 2) return [];
            const hits = [];
            for (let i = 0; i < nodes.length && hits.length < 400; i++) {
                const n = nodes[i];
                const hay = (n._full + ' ' + (n.info || '')).toLocaleLowerCase('tr');
                const at = hay.indexOf(needle);
                if (at < 0) continue;
                hits.push({ n: n, score: (at === 0 ? 0 : 1) + n._level * 0.1 - n._imp });
            }
            hits.sort((a, b) => a.score - b.score);
            return hits.slice(0, 8).map(h => h.n);
        }

        function onSearchInput(q) {
            const box = document.getElementById('searchResults');
            if (!box) return;
            box.innerHTML = '';
            const hits = searchNodes(q);
            hits.forEach(n => {
                const d = document.createElement('div');
                d.className = 'search-hit';
                d.textContent = n._short + '  · ' + n.group;
                d.onclick = function () { flyToNode(n.id); };
                box.appendChild(d);
            });
            window.__graphStats.searchHits = hits.length;
        }

        function flyToNode(id) {
            const n = nodeMap.get(String(id));
            if (!n) return;
            expandedBranches.add(n.id);
            const p = treeParent.get(n.id);
            if (p) expandedBranches.add(p);
            selectedNodeId = n.id;
            searchHighlight = n.id;
            recomputeIsolation();
            relayoutGraph();
            updateBreadcrumb();
            userAdjustedView = true;
            settledFitDone = true;
            tweenTo(Math.max(zoom, 1.3), width / 2 - n.x * Math.max(zoom, 1.3), height / 2 - n.y * Math.max(zoom, 1.3), 250);
        }

        // İki düğüm arasında ağaç + wikilink üzerinden en kısa yol (BFS).
        function showPath(fromId, toId) {
            const start = String(fromId), goal = String(toId);
            if (!nodeMap.has(start) || !nodeMap.has(goal)) return null;
            const prev = new Map();
            const seen = new Set([start]);
            const q = [start];
            while (q.length) {
                const cur = q.shift();
                if (cur === goal) break;
                const nb = neighborIds.get(cur);
                if (!nb) continue;
                nb.forEach(x => {
                    if (seen.has(x)) return;
                    seen.add(x); prev.set(x, cur); q.push(x);
                });
            }
            if (!seen.has(goal)) { pathHighlight = null; return null; }
            const path = [goal];
            let cur = goal;
            while (prev.has(cur)) { cur = prev.get(cur); path.unshift(cur); }
            pathHighlight = new Set(path);
            requestRender();
            return path;
        }

        // ---- Çizim ----
        let hoveredNode = null;
        let draggedNode = null;
        let isDragging = false;
        let startX = 0, startY = 0;
        let hoverTimer = null;

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
            applyZoom(zoom * zoomFactor, e.clientX - rect.left, e.clientY - rect.top);
        }, { passive: false });

        canvas.addEventListener('contextmenu', (e) => { e.preventDefault(); });

        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            if (minimapPan(mx, my)) return;
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
                startX = mx; startY = my;
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

        function applyHover(n) {
            if (n === hoveredNode) return;
            hoveredNode = n;
            focusNode = n;
            computeFocusSets(n);
            if (n) {
                canvas.style.cursor = 'pointer';
                infoBox.style.display = 'block';
                const col = getNodeColor(n.group);
                let extraBadge = '';
                if (n.group === 'community') {
                    const count = communityMembers.get(String(n.id)) || n.member_count || 0;
                    const open = expandedCommunities.has(String(n.id));
                    extraBadge = '<br/><span style="display:inline-block; margin-top:4px; padding:2px 8px; background:rgba(255, 209, 102, 0.15); border:1px solid #FFD166; border-radius:4px; color:#FFD166; font-size:10px; font-weight:600;">🔮 ' + count + ' üye — tıkla: ' + (open ? 'kapat' : 'aç') + '</span>';
                } else if (n.id.includes('MEMORY') || n.id.includes('BELLEK_HARITASI')) {
                    extraBadge = '<br/><span style="display:inline-block; margin-top:4px; padding:2px 8px; background:rgba(255, 170, 0, 0.15); border:1px solid #FFAA00; border-radius:4px; color:#FFAA00; font-size:10px; font-weight:600;">📑 İndeks Kataloğu</span>';
                }
                infoBox.innerHTML = '<b style="color:' + col + '; font-size:13px;">' + n._full + '</b> <span style="color:#8B949E; font-size:11px;">[' + n.group + ']</span> <span style="color:#00FF9D; font-size:11px; margin-left:8px;">(Detayları Açmak İçin Tıkla)</span>' + extraBadge + '<br/><span style="color:#C9D1D9; font-size:11px; line-height:1.4;">' + (n.info || '') + '</span>';
            } else {
                canvas.style.cursor = isPanning ? 'grabbing' : 'default';
                infoBox.style.display = 'none';
            }
            requestRender();
        }

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
                    draggedNode.x = (mx - panX) / zoom;
                    draggedNode.y = (my - panY) / zoom;
                    alpha = 0.25;
                }
                requestRender();
                return;
            }

            const wx = (mx - panX) / zoom;
            const wy = (my - panY) / zoom;
            const hit = nodeAt(wx, wy);
            // U5: 80 ms gecikme — hızlı geçişlerde bilgi kutusu titremez.
            if (hit === hoveredNode) return;
            if (hoverTimer) clearTimeout(hoverTimer);
            if (!hit) { applyHover(null); return; }
            hoverTimer = setTimeout(() => { hoverTimer = null; applyHover(hit); }, 80);
        }

        window.addEventListener('mousemove', handleMouseMove);

        function handleMouseUp(e) {
            if (draggedNode && !isDragging && (!e || e.button === 0)) {
                if (draggedNode.group === 'community') {
                    toggleCommunity(draggedNode.id);
                    draggedNode = null; isDragging = false; isPanning = false;
                    requestRender();
                    return;
                }
                selectedNodeId = draggedNode.id;
                if (!isDetailNode(draggedNode)) {
                    // U5: dala tıkla -> dal açılır ve görünüm O DALA sığdırılır
                    // (bütüne değil), 250 ms tween ile.
                    toggleBranchExpansion(draggedNode.id);
                    recomputeIsolation();
                    relayoutGraph();
                    updateBreadcrumb();
                    alpha = Math.max(alpha, 0.5);
                    if (expandedBranches.has(draggedNode.id)) {
                        const branch = [];
                        computeBranchSet(draggedNode.id).forEach(bid => {
                            const bn = nodeMap.get(bid);
                            if (bn && isNodeVisible(bn)) branch.push(bn);
                        });
                        userAdjustedView = true;
                        settledFitDone = true;
                        fitNodesToView(branch.length ? branch : [draggedNode], 250);
                    }
                } else {
                    recomputeIsolation();
                    updateBreadcrumb();
                }
                const url = 'entropy-node://select?id=' + encodeURIComponent(draggedNode.id);
                window.location.href = url;
            }
            draggedNode = null;
            isDragging = false;
            isPanning = false;
            if (canvas) canvas.style.cursor = hoveredNode ? 'pointer' : 'default';
            requestRender();
        }

        window.addEventListener('mouseup', handleMouseUp);
        window.addEventListener('blur', () => {
            isPanning = false; draggedNode = null; isDragging = false;
            requestRender();
        });
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F')) {
                e.preventDefault();
                const box = document.getElementById('searchBox');
                if (box && box.classList && !box.classList.contains('open')) toggleSearch();
                else { const i = document.getElementById('searchInput'); if (i && i.focus) i.focus(); }
            } else if (e.key === 'Escape') {
                const box = document.getElementById('searchBox');
                if (box && box.classList && box.classList.contains('open')) toggleSearch();
                searchHighlight = null;
                pathHighlight = null;
                requestRender();
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

        // U8: 40+ çocuklu ebeveynde kenarlar merkeze değil, ebeveynin çevresindeki
        // 24 px'lik halkaya bağlanır — yıldız merkezi kararmaz.
        const FAN_THRESHOLD = 40;
        const FAN_RADIUS = 24;
        function fanOrigin(parent, child) {
            if (!parent || (parent._childCount || 0) < FAN_THRESHOLD) return parent;
            const dx = child.x - parent.x, dy = child.y - parent.y;
            const d = Math.hypot(dx, dy) || 1;
            const r = Math.min(FAN_RADIUS, d * 0.5);
            return { x: parent.x + dx / d * r, y: parent.y + dy / d * r };
        }

        // U2: görünüm alanı kırpması (culling). Çizim ve etiket yalnızca
        // görünümün %30 marjı içindeki düğümleri işler.
        function viewportWorldRect(margin) {
            const m = margin === undefined ? 0.3 : margin;
            const w = width / zoom, h = height / zoom;
            const x0 = -panX / zoom - w * m, y0 = -panY / zoom - h * m;
            return { x0: x0, y0: y0, x1: x0 + w * (1 + 2 * m), y1: y0 + h * (1 + 2 * m) };
        }

        function render() {
            isRendering = false;
            const tFrame = performance.now();
            // U2: bant değişimi görünür kümeyi tazeler, benzetimi ISITMAZ.
            if (syncDetailState()) relayoutGraph();
            const tweening = stepTween();
            tickPhysics();

            const tDraw = performance.now();
            ctx.save();
            if (typeof ctx.clearRect === 'function') ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = '#080B10';
            ctx.fillRect(0, 0, width, height);
            ctx.translate(panX, panY);
            ctx.scale(zoom, zoom);

            const vr = viewportWorldRect(0.3);
            const inView = (n) => (n.x >= vr.x0 && n.x <= vr.x1 && n.y >= vr.y0 && n.y <= vr.y1);

            // Çizilecek düğüm kümesi: LOD + kapsam + görünüm kırpması.
            const viewNodes = new Set();
            for (let i = 0; i < nodes.length; i++) {
                const n = nodes[i];
                if (isNaN(n.x) || isNaN(n.y)) continue;
                if (!isNodeVisible(n)) continue;
                if (!isNodeInScope(n) && isIsolated && currentScope !== 'all') continue;
                // Yapısal düğümler her zaman çizilir (ZMLT tutarlılığı),
                // yapraklar yalnız görünüm alanında (U2 culling).
                if (n._level >= 4 && !inView(n)) continue;
                viewNodes.add(n);
            }

            drawHulls();

            const band = lodBand(zoom);
            const trunkLinks = [];
            const leafLinks = [];
            const wikiLinks = [];
            const simLinksDraw = [];
            for (let i = 0; i < simLinks.length; i++) {
                const l = simLinks[i];
                const s = l.sourceNode, t = l.targetNode;
                if (!viewNodes.has(s) || !viewNodes.has(t)) continue;
                if (s === hoveredNode || t === hoveredNode) continue;
                const kind = linkKind(l);
                if (kind === 'trunk') trunkLinks.push(l);
                // Yapısal düğüme (level <= 3) giden ağaç kenarı her bantta
                // çizilir; yalnız YAPRAK kenarları bant 2'de açılır.
                else if (kind === 'tree') { if (band >= 2 || t._level <= 3) leafLinks.push(l); }
                else if (kind === 'similarity') {
                    // U8: benzerlik kenarı yalnız topluluk içi; topluluklar arası
                    // bağ hover'da görünür.
                    if (band >= 1 && s._cid && s._cid === t._cid) simLinksDraw.push(l);
                } else if (band >= 2) wikiLinks.push(l);
            }

            // Gövde kenarları: bundle alanı geldiyse Bezier kontrol noktalarıyla
            // demetlenmiş, yoksa hafif eğri.
            if (trunkLinks.length) {
                ctx.lineWidth = 1.6 / zoom;
                ctx.strokeStyle = 'rgba(56, 139, 253, 0.45)';
                ctx.beginPath();
                for (let i = 0; i < trunkLinks.length; i++) {
                    const l = trunkLinks[i];
                    if (Array.isArray(l.bundle) && l.bundle.length >= 2) {
                        ctx.moveTo(l.sourceNode.x, l.sourceNode.y);
                        for (let k = 0; k < l.bundle.length; k++) {
                            const p = l.bundle[k];
                            ctx.lineTo(p[0], p[1]);
                        }
                        ctx.lineTo(l.targetNode.x, l.targetNode.y);
                    } else {
                        drawCurvedLink(l.sourceNode, l.targetNode, 0.06);
                    }
                }
                ctx.stroke();
            }

            if (leafLinks.length) {
                ctx.lineWidth = 0.8 / zoom;
                ctx.strokeStyle = 'rgba(56, 139, 253, 0.22)';
                ctx.beginPath();
                for (let i = 0; i < leafLinks.length; i++) {
                    const l = leafLinks[i];
                    const o = fanOrigin(l.sourceNode, l.targetNode);
                    ctx.moveTo(o.x, o.y);
                    ctx.lineTo(l.targetNode.x, l.targetNode.y);
                }
                ctx.stroke();
            }

            if (simLinksDraw.length) {
                // Renk başına tek yol: 500+ benzerlik kenarında ayrı ayrı
                // stroke() çağırmak kare süresinin yarısını yiyordu.
                ctx.lineWidth = 0.7 / zoom;
                const byTint = new Map();
                for (let i = 0; i < simLinksDraw.length; i++) {
                    const l = simLinksDraw[i];
                    const key = communityIndex(l.sourceNode) % TOL_12.length;
                    let b = byTint.get(key);
                    if (!b) { b = []; byTint.set(key, b); }
                    b.push(l);
                }
                byTint.forEach((group, key) => {
                    ctx.strokeStyle = communityTint(group[0].sourceNode, 0.18);
                    ctx.beginPath();
                    for (let i = 0; i < group.length; i++) {
                        ctx.moveTo(group[i].sourceNode.x, group[i].sourceNode.y);
                        ctx.lineTo(group[i].targetNode.x, group[i].targetNode.y);
                    }
                    ctx.stroke();
                });
            }

            // Wikilink: kesikli, ağırlığa göre 0,8–2 px.
            if (wikiLinks.length) {
                if (typeof ctx.setLineDash === 'function') ctx.setLineDash([4 / zoom, 4 / zoom]);
                ctx.strokeStyle = 'rgba(167, 139, 250, 0.40)';
                // Ağırlık üç kalınlık kovasına yuvarlanır; kova başına tek yol.
                const buckets = [[], [], []];
                for (let i = 0; i < wikiLinks.length; i++) {
                    const l = wikiLinks[i];
                    const w = (typeof l.weight === 'number') ? Math.max(0.8, Math.min(2, 0.8 + l.weight * 1.2)) : 1.0;
                    buckets[w < 1.2 ? 0 : (w < 1.7 ? 1 : 2)].push(l);
                }
                const bw = [0.8, 1.4, 2.0];
                for (let b = 0; b < 3; b++) {
                    if (!buckets[b].length) continue;
                    ctx.lineWidth = bw[b] / zoom;
                    ctx.beginPath();
                    for (let i = 0; i < buckets[b].length; i++) {
                        drawCurvedLink(buckets[b][i].sourceNode, buckets[b][i].targetNode, 0.12);
                    }
                    ctx.stroke();
                }
                if (typeof ctx.setLineDash === 'function') ctx.setLineDash([]);
            }

            // Yol vurgusu (U7)
            if (pathHighlight) {
                ctx.lineWidth = 2.6 / zoom;
                ctx.strokeStyle = '#00FF9D';
                ctx.beginPath();
                for (let i = 0; i < simLinks.length; i++) {
                    const l = simLinks[i];
                    if (pathHighlight.has(l.sourceNode.id) && pathHighlight.has(l.targetNode.id)) {
                        ctx.moveTo(l.sourceNode.x, l.sourceNode.y);
                        ctx.lineTo(l.targetNode.x, l.targetNode.y);
                    }
                }
                ctx.stroke();
            }

            // Hover kenarları
            if (hoveredNode) {
                ctx.lineWidth = 2.4 / zoom;
                for (let i = 0; i < links.length; i++) {
                    const l = links[i];
                    if (l.is_catalog_link) continue;
                    const s = l.sourceNode, t = l.targetNode;
                    if (!s || !t) continue;
                    if (s !== hoveredNode && t !== hoveredNode) continue;
                    try {
                        const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
                        grad.addColorStop(0, getNodeColor(s.group));
                        grad.addColorStop(1, getNodeColor(t.group));
                        ctx.strokeStyle = grad;
                    } catch (err) {
                        ctx.strokeStyle = getNodeColor((s === hoveredNode ? t : s).group);
                    }
                    ctx.beginPath();
                    drawCurvedLink(s, t, 0.12);
                    ctx.stroke();
                }
            }

            // Düğümler
            let drawn = 0;
            viewNodes.forEach(n => {
                const inScope = isNodeInScope(n);
                if (!inScope && isIsolated && currentScope !== 'all') return;
                const color = getNodeColor(n.group);
                const isHovered = (n === hoveredNode);
                const r = Math.max((n.val || 12) * (isHovered ? 1.3 : 1.0), 3 / Math.max(zoom, 0.05));
                const fade = lodFade(n);
                if (fade <= 0.01) return;
                ctx.globalAlpha = (inScope ? 1.0 : 0.08) * nodeAlphaFactor(n) * fade * dimFactor(n);

                if (isHovered || n._level <= 1 || n.id === searchHighlight) {
                    try {
                        const glow = ctx.createRadialGradient(n.x, n.y, r * 0.2, n.x, n.y, r * 2.2);
                        glow.addColorStop(0, (n.id === searchHighlight ? '#00FF9D' : color) + 'aa');
                        glow.addColorStop(1, color + '00');
                        ctx.fillStyle = glow;
                    } catch (e) { ctx.fillStyle = color; }
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 2.2, 0, Math.PI * 2);
                    ctx.fill();
                } else if (n._level <= 3 || band >= 3) {
                    // Topluluk halesi yalnız yapısal düğümlerde ve en yakın
                    // bantta: 700 yaprakta ek daire çizmek çizim süresini
                    // ikiye katlıyordu (topluluk dokusu hull ile veriliyor).
                    ctx.fillStyle = communityTint(n, 0.18);
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 1.5, 0, Math.PI * 2);
                    ctx.fill();
                }

                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
                ctx.fill();

                const icon = (n._level <= 3) ? getNodeIcon(n.group) : '';
                if (icon) {
                    ctx.save();
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.font = Math.max(r * 1.1, 8) + 'px "Segoe UI Emoji", "Segoe UI Symbol", sans-serif';
                    ctx.fillText(icon, n.x, n.y);
                    ctx.restore();
                } else if (n._level <= 3) {
                    ctx.fillStyle = '#FFFFFF';
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 0.35, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.globalAlpha = 1.0;
                drawn++;
            });

            ctx.restore();

            // Etiketler ve mini harita ekran uzayında (zoom'dan bağımsız).
            drawLabels(viewNodes);
            drawHullLabels();
            drawMinimap();

            window.__graphStats.drawnNodes = drawn;
            window.__graphStats.drawnLinks = trunkLinks.length + leafLinks.length + wikiLinks.length + simLinksDraw.length;
            window.__graphStats.zoom = zoom;
            window.__graphStats.band = band;
            window.__graphStats.drawMs = performance.now() - tDraw;
            window.__graphStats.frameMs = performance.now() - tFrame;
            const fr = window.__graphStats.frames;
            fr.push(window.__graphStats.frameMs);
            if (fr.length > 240) fr.shift();

            const needNext = tweening || (alpha >= alphaMin && !isPanning) || !!draggedNode;
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
        lastDetailState = lodBand(zoom);
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
        self._refresh_timer.setInterval(1500)
        self._graph_job_running = False
        self._graph_job_again = False
        self._refresh_timer.timeout.connect(self.refresh_graph_async)

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
        self._run_js("setIsolationMode(%s);" % ("true" if checked else "false"))

    def _run_js(self, script: str) -> bool:
        """Kanvas JS'ini çalıştırır; offscreen/başsız kipte sessizce yok sayılır."""
        page = self.web_view.page() if hasattr(self.web_view, "page") else None
        if page is None:
            return False
        try:
            page.runJavaScript(script)
            return True
        except Exception:
            return False

    def select_node(self, node_id: str):
        """Dışarıdan (odak listesi, rapor tıklaması) seçili düğümü bildirir."""
        if not node_id:
            return
        safe = json.dumps(str(node_id))
        self._run_js(
            "if (typeof setSelectedNode === 'function') { setSelectedNode(%s); }" % safe
        )

    # --- Faz 6: kanvas ölçüsü panelle birlikte güncellensin ---
    #
    # Zen kipinde grafik paneli açılışta gizli olabiliyor; sayfa 0x0 bir alanda
    # yüklenince sığdırma yanlış ölçüye göre yapılıp grafik köşede minik kalıyordu.
    # Panel gösterildiğinde ve yeniden boyutlandığında kanvas ölçüsü + sığdırma
    # tazelenir (arka arkaya gelen olaylar tek çağrıda toplanır).
    def _ensure_fit_timer(self) -> QTimer:
        timer = getattr(self, "_fit_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(180)
            timer.timeout.connect(self._apply_view_fit)
            self._fit_timer = timer
        return timer

    @Slot()
    def schedule_view_fit(self):
        self._ensure_fit_timer().start()

    @Slot()
    def _apply_view_fit(self):
        self._run_js(
            "if (typeof updateDimensions === 'function') { updateDimensions(); fitToView(); }"
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.schedule_view_fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_view_fit()

    def apply_scope(self, scope_key: str):
        """Programmatically switch scope and update canvas."""
        self.current_scope = scope_key
        if hasattr(self.web_view, "page") and self.web_view.page():
            try:
                self.web_view.page().runJavaScript(f"setScope('{scope_key}');")
            except Exception:
                pass

    def closeEvent(self, event):
        # Faz 8: pencere birden cok kez kapatilinca ayni sinyalleri tekrar
        # cozmek libpyside'in "Failed to disconnect" RuntimeWarning'ini
        # basiyordu; cozme yalnizca ilk kapanista yapilir.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
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
                # Faz 8/M2: `Projects/test_*` pytest kalıntısıdır, proje değil.
                if is_test_artifact_name(p_sub.name):
                    continue
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
        cog_name_counts: Dict[str, int] = {}
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
                            # Faz 8/M2: ad İLK SATIRDAN gelir, satır sonu
                            # taşımaz ve ≤ 40 karakterdir. Eskiden ilk 26
                            # karakter ham alınıyordu; "# Pazar araştırması\n\nOfis:"
                            # gibi 46 düğüm aynı ada düşüyordu.
                            short_name = _cognitive_node_name(content, cog_name_counts)

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
                # Faz 8/M6: ön bilgideki `skill`/`tags` sınıflandırmaya girer;
                # eskiden `tags=None` geçiliyordu ve eşleşmeyen her rapor
                # varsayılan dala (çöp kutusu) düşüyordu.
                fm_tags = list(o_node.get("tags") or [])
                if o_node.get("skill"):
                    fm_tags.insert(0, f"skill:{o_node['skill']}")
                parent_hub, cluster_id, cluster_grp = classify_report_to_hub(
                    title=o_name,
                    path_str=o_path,
                    tags=fm_tags or None,
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

        data = {
            "nodes": nodes,
            "links": links,
            "similarity_links": len(sim_links),
            "communities": len(set(communities.values())),
            "known_projects": known_projects,
            "registered_skills": registered_skills
        }

        # Faz 8: temizlik + zenginleştirme (bkz. entropy.memory.graph_enrich).
        # Sarkan/katalog/öz-döngü kenarları düşer; `level`, `degree`,
        # `child_count`, `short_label`, `importance`, `t_valid_from/to`,
        # `type`, `community_id/label/size` ve kenar `kind`/`weight` eklenir.
        if (os.environ.get("ENTROPY_GRAPH_ENRICH") or "").strip().lower() in ("0", "false", "off"):
            # Ölçüm/karşılaştırma kaçış kapısı: ham (Faz 7) çıktı döner.
            return data
        store = getattr(self, "graph_store", None)
        if store is None:
            try:
                from entropy.memory.graph_store import GraphStore
                # Aynı SQLite dosyası paylaşılır: ayrı bir bağlantı açmak
                # testlerde geçici veritabanını atlayıp gerçek belleğe düşerdi.
                store = GraphStore(memory=self.cognitive_memory)
            except Exception:
                store = None
        try:
            data = enrich_graph(data, graph_store=store)
        except Exception:
            # Zenginleştirme çökerse graf yine çizilir (ham veri geriye uyumlu).
            pass
        return data

    def refresh_graph(self):
        """Grafi yeniden kurar ve kanvasi tazeler (senkron; ilk yukleme/testler)."""
        self._render_graph(self.build_unified_graph())

    @Slot()
    def refresh_graph_async(self):
        """Faz 9: pahali graf insasini (Louvain dahil ~2,5 sn) isci is parcaciginda kosar.

        `build_unified_graph` + `enrich_graph` saf veri isidir, Qt nesnesine
        dokunmaz; sonuc `bus.invoke_on_main` ile ana is parcaciginda cizilir.
        """
        if getattr(self, "_graph_job_running", False):
            self._graph_job_again = True
            return
        self._graph_job_running = True
        self._graph_job_again = False
        widget = self

        class _GraphJob(QRunnable):
            def run(self):  # isci is parcacigi
                try:
                    data = widget.build_unified_graph()
                except Exception:
                    data = None
                bus.invoke_on_main(partial(widget._apply_async_graph, data))

        QThreadPool.globalInstance().start(_GraphJob())

    def _apply_async_graph(self, data):
        try:
            self._graph_job_running = False
            if data is not None:
                self._render_graph(data)
            if getattr(self, "_graph_job_again", False):
                self._graph_job_again = False
                self._refresh_timer.start()
        except RuntimeError:
            return

    def _render_graph(self, graph_data):
        """Kanvas + kapsam combosu guncellemesi (YALNIZCA ana is parcacigi)."""
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
