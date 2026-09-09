"""
Faz 8 graf verisi ölçüm betiği (tasarım notu §1.1 tablosunun kalıcı hâli).

Gerçek kasadan `build_unified_graph()` çıktısını üretir ve JSON boyutu, sarkan
kenar, öz-döngü, yinelenen çift, etiket çeşitliliği, topluluk kalitesi, modülerlik
gibi ölçütleri hesaplar. Salt okunur: kasaya hiçbir şey yazmaz, model çağrısı
yapmaz.

Kullanım:
    QT_QPA_PLATFORM=offscreen python scripts/graph_metrics.py [--json cikti.json]
    ... --vault "C:/.../Obsidian Vault"   (varsayılan: config'teki kasa)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _GraphHost:
    """`build_unified_graph()` yalnızca beş özniteliğe dokunur (bkz. perf_bench)."""

    def __init__(self, project_dir: Path, vault_path: Path | None = None):
        from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
        from entropy.mcp.manager import MCPManager
        from entropy.skills.manager import SkillManager

        self.active_project_dir = Path(project_dir)
        self.vault_manager = ObsidianVaultManager(vault_path) if vault_path else ObsidianVaultManager()
        self.cognitive_memory = CognitiveMemorySystem()
        self.skill_manager = SkillManager(project_dir=self.active_project_dir)
        self.mcp_manager = MCPManager()


def _modularity(nodes: List[Dict[str, Any]], links: List[Dict[str, Any]], key: str = "community") -> float:
    """Ağırlıksız Newman modülerliği; topluluk alanı yoksa 0."""
    comm = {n["id"]: n.get(key) for n in nodes if n.get(key) is not None}
    if not comm:
        return 0.0
    deg: Dict[str, float] = defaultdict(float)
    m = 0.0
    intra: Dict[Any, float] = defaultdict(float)
    tot: Dict[Any, float] = defaultdict(float)
    for l in links:
        s, t = l.get("source"), l.get("target")
        if s not in comm or t not in comm or s == t:
            continue
        deg[s] += 1.0
        deg[t] += 1.0
        m += 1.0
        if comm[s] == comm[t]:
            intra[comm[s]] += 1.0
    if m <= 0:
        return 0.0
    for nid, d in deg.items():
        tot[comm[nid]] += d
    return sum(intra[c] / m - (tot[c] / (2.0 * m)) ** 2 for c in tot)


def collect(data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    ids = {n["id"] for n in nodes}

    dangling = [l for l in links if l.get("source") not in ids or l.get("target") not in ids]
    self_loops = [l for l in links if l.get("source") == l.get("target")]
    pairs = Counter(
        (l.get("source"), l.get("target"))
        for l in links
        if l.get("source") in ids and l.get("target") in ids and l.get("source") != l.get("target")
    )
    dup_pairs = sum(c - 1 for c in pairs.values() if c > 1)

    degree: Dict[str, int] = defaultdict(int)
    child_count: Dict[str, int] = defaultdict(int)
    for l in links:
        s, t = l.get("source"), l.get("target")
        if s in ids:
            degree[s] += 1
        if t in ids:
            degree[t] += 1
        if l.get("is_tree_link") and s in ids:
            child_count[s] += 1

    groups = Counter(n.get("group", "?") for n in nodes)
    kinds = Counter(
        "tree" if l.get("is_tree_link") else
        "similarity" if l.get("is_similarity_link") else
        "catalog" if l.get("is_catalog_link") else
        l.get("kind") or "wikilink"
        for l in links
    )

    reports = [n for n in nodes if n.get("group") == "Reports"]
    short_labels = {n.get("short_label") or (n.get("name") or "")[:24] for n in reports}
    name_groups = Counter((n.get("name") or "") for n in nodes)
    dup_names = [k for k, c in name_groups.items() if c >= 5]
    newline_names = [n["id"] for n in nodes if "\n" in (n.get("name") or "")]

    test_projects = [
        n["id"] for n in nodes
        if n.get("group") == "project" and n.get("id", "").startswith("subhub-project-test")
    ]
    test_leaves = [
        n["id"] for n in nodes
        if "Projects\\test_" in str(n.get("info", "")) or "Projects/test_" in str(n.get("info", ""))
    ]

    comms = Counter(n.get("community") for n in nodes if n.get("community") is not None)
    tiny = [c for c, s in comms.items() if s <= 3]

    top_parents = Counter(child_count).most_common(6)

    return {
        "nodes": len(nodes),
        "links": len(links),
        "json_kb": round(len(json.dumps(data, ensure_ascii=False).encode("utf-8")) / 1024.0, 1),
        "dangling_links": len(dangling),
        "dangling_targets_top": Counter(
            l.get("target") for l in links if l.get("target") not in ids
        ).most_common(8),
        "self_loops": len(self_loops),
        "duplicate_pairs": dup_pairs,
        "link_kinds": dict(kinds),
        "groups": dict(groups),
        "max_degree": max(degree.values(), default=0),
        "max_child_count": max(child_count.values(), default=0),
        "top_parents": top_parents,
        "report_nodes": len(reports),
        "distinct_report_short_labels": len(short_labels),
        "max_short_label_len": max((len(s) for s in short_labels), default=0),
        "duplicate_name_groups": len(dup_names),
        "names_with_newline": len(newline_names),
        "test_project_hubs": len(test_projects),
        "test_project_leaves": len(test_leaves),
        "communities": len(comms),
        "tiny_communities": len(tiny),
        "modularity": round(_modularity(nodes, links), 4),
        "nodes_with_importance": sum(1 for n in nodes if n.get("importance") is not None),
        "nodes_with_t_valid_from": sum(1 for n in nodes if n.get("t_valid_from") is not None),
        "nodes_with_type": sum(1 for n in nodes if n.get("type")),
        "nodes_with_community_id": sum(1 for n in nodes if n.get("community_id")),
        "nodes_with_level": sum(1 for n in nodes if n.get("level") is not None),
        "nodes_with_short_label": sum(1 for n in nodes if n.get("short_label")),
        "community_nodes": sum(1 for n in nodes if n.get("group") == "community"),
        "reports_with_importance_from_store": sum(
            1 for n in reports if n.get("importance") is not None
        ),
        "hasTimeData": any(n.get("t_valid_from") for n in nodes),
        "hasImportanceData": any(n.get("importance") is not None for n in nodes),
        "hasCommunityData": any(n.get("community_id") or n.get("community") for n in nodes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None, help="kasa kökü (varsayılan: config)")
    ap.add_argument("--json", dest="json_out", default=None, help="ölçümleri JSON'a yaz")
    ap.add_argument("--project", default=str(REPO_ROOT))
    args = ap.parse_args()

    from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget

    host = _GraphHost(Path(args.project), Path(args.vault) if args.vault else None)
    t0 = time.perf_counter()
    data = KnowledgeGraphWidget.build_unified_graph(host)
    build_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    metrics = collect(data)
    metrics["build_ms"] = build_ms
    text = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
