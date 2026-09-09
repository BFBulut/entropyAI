"""
Faz 8: birleşik graf verisinin temizlenmesi ve zenginleştirilmesi.

`KnowledgeGraphWidget.build_unified_graph()` ham düğüm/kenar listesini üretir;
bu modül onu UI'nin ihtiyaç duyduğu hâle getirir:

* M1 — sarkan kenar, öz-döngü, yinelenen çift ve katalog kenarı temizliği
* M3 — `GraphStore` köprüsü (`importance`, `t_valid_from/to`, `type`,
  `community_id`, `community` düğümleri + `member_of` kenarları)
* M4 — `level`, `degree`, `child_count`, `short_label` / `label`, kenar
  `weight` ve `kind`
* M5 — topluluk kalitesi (Louvain varsa Louvain, yoksa mevcut etiket yayılımı),
  küçük toplulukların katlanması, `community_label` / `community_size`
* M6 — 80'den çok çocuğu olan ebeveynlerin konu alt dallarına bölünmesi

Tüm alanlar EKLENİR; mevcut alanlar (`is_tree_link`, `is_catalog_link`,
`community`, `cluster`, `parent_hub` …) korunur, geriye uyum bozulmaz.
Modül saf veri işler: dosya yazmaz, model çağırmaz.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# Kenar türleri (UI `kind` alanını bu kümede bekler).
KIND_TREE = "tree"
KIND_WIKILINK = "wikilink"
KIND_SIMILARITY = "similarity"
KIND_MEMBER_OF = "member_of"
KIND_DERIVED_FROM = "derived_from"

# Kenar türü -> taban ağırlık (0..1). Benzerlik kenarları kendi skorunu taşır.
_KIND_WEIGHT = {
    KIND_TREE: 0.9,
    KIND_MEMBER_OF: 0.8,
    KIND_DERIVED_FROM: 0.7,
    KIND_WIKILINK: 0.45,
    KIND_SIMILARITY: 0.5,
}

# Düğüm grubundan seviye (ağaç derinliği yoksa geri düşülür).
_GROUP_LEVEL = {
    "ego": 0,
    "hub": 1,
    "project": 2,
    "skill": 2,
    "office": 2,
    "mcp": 2,
    "agent": 2,
    "subbranch": 3,
    "community": 3,
    "topic": 3,
}

MAX_SHORT_LABEL = 28
MAX_CHILDREN = 80
MIN_COMMUNITY_SIZE = 4          # 3 ve altı topluluk katlanır
TARGET_COMMUNITY_RANGE = (15, 40)

_LABEL_STOPWORDS = {
    "ve", "ile", "icin", "için", "the", "and", "of", "a", "an", "raporu", "rapor",
    "report", "gorev", "görev", "master", "doktrini", "doktrin", "notlar", "notes",
    "analiz", "analysis", "final", "yeni", "guncel", "güncel", "genel", "tam",
    "obsidian", "dosyasi", "dosyası", "md", "entropy", "entropiai",
}

_DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")
_PHASE_RE = re.compile(r"(?i)\bfaz\s*[-_]?\s*(\d{1,3})")
_GOREV_RE = re.compile(r"(?i)^gorev[_\s-]+(?P<skill>[a-z0-9\-]+)[_\s-]+(?P<rest>.*)$")


# --------------------------------------------------------------------------
# M1: kenar temizliği
# --------------------------------------------------------------------------

def _link_kind(link: Dict[str, Any]) -> str:
    if link.get("is_tree_link"):
        return KIND_TREE
    if link.get("is_similarity_link"):
        return KIND_SIMILARITY
    explicit = (link.get("type") or "").strip()
    if explicit in (KIND_MEMBER_OF, KIND_DERIVED_FROM, KIND_SIMILARITY, KIND_WIKILINK):
        return explicit
    return KIND_WIKILINK


def clean_links(
    nodes: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Sarkan hedefli, öz-döngü ve yinelenen kenarları atar; katalog kenarlarını
    JSON'a hiç yazmaz. Her kenara `kind` ve `weight` (0..1) ekler.

    Yinelenen çiftlerde en güçlü kenar kazanır (ağaç > member_of > benzerlik >
    wikilink); wikilink tekrarları ağırlığa bonus olarak yansır, kenar
    çoğaltılmaz.
    """
    ids = {n["id"] for n in nodes}
    priority = {
        KIND_TREE: 5, KIND_MEMBER_OF: 4, KIND_DERIVED_FROM: 3,
        KIND_SIMILARITY: 2, KIND_WIKILINK: 1,
    }
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    repeats: Counter = Counter()
    for link in links:
        src, dst = link.get("source"), link.get("target")
        if src not in ids or dst not in ids or src == dst:
            continue
        if link.get("is_catalog_link"):
            # Katalog yayları hiç çizilmiyordu ama JSON'un %30'unu tutuyordu.
            continue
        kind = _link_kind(link)
        key = (src, dst) if kind == KIND_TREE else tuple(sorted((src, dst)))
        repeats[key] += 1
        current = best.get(key)
        if current is not None and priority[current["kind"]] >= priority[kind]:
            continue
        out = dict(link)
        out["source"], out["target"] = src, dst
        out["kind"] = kind
        best[key] = out

    cleaned: List[Dict[str, Any]] = []
    for key, link in best.items():
        kind = link["kind"]
        if kind == KIND_SIMILARITY:
            weight = float(link.get("weight") or _KIND_WEIGHT[kind])
        elif kind == KIND_WIKILINK:
            weight = min(1.0, _KIND_WEIGHT[kind] + 0.08 * (repeats[key] - 1))
        else:
            weight = float(link.get("weight") or _KIND_WEIGHT[kind])
        link["weight"] = round(max(0.0, min(1.0, weight)), 3)
        link.pop("is_catalog_link", None)
        cleaned.append(link)
    return cleaned


# --------------------------------------------------------------------------
# M3: GraphStore köprüsü
# --------------------------------------------------------------------------

def _store_match_keys(node: Dict[str, Any]) -> List[str]:
    """Bir graf düğümünün GraphStore'da aranacak anahtarları (öncelik sırasıyla)."""
    keys = [str(node.get("id") or "")]
    path = str(node.get("path") or "")
    if not path:
        info = str(node.get("info") or "")
        if info.startswith("Obsidian Dosyası: "):
            path = info.split(": ", 1)[1]
    if path:
        keys.append(path)
    name = str(node.get("name") or "").strip()
    if name:
        keys.append(name.lower())
    return [k for k in keys if k]


def bridge_graph_store(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    graph_store: Any,
) -> Dict[str, int]:
    """
    GraphStore düğümlerinden `importance` / `t_valid_from` / `t_valid_to` /
    `type` / `community_id` alanlarını eşleşen graf düğümlerine yazar ve
    topluluk düğümlerini `member_of` kenarlarıyla grafa ekler.

    Eşleştirme sırası: düğüm kimliği → dosya yolu (provenance) → başlık.
    Eşleşmeyen düğümler kaybolmaz; onlara grup tabanlı varsayılan yazılır.
    """
    stats = {"matched": 0, "communities": 0, "member_of": 0}
    by_key: Dict[str, Any] = {}
    community_ids: Set[str] = set()
    try:
        store_nodes = graph_store.all_nodes()
        communities = {c.id: c for c in graph_store.list_communities()}
    except Exception:
        store_nodes, communities = [], {}

    for sn in store_nodes:
        by_key.setdefault(sn.id, sn)
        prov = str(getattr(sn, "provenance", "") or "")
        if prov:
            by_key.setdefault(prov, sn)
        title = str(getattr(sn, "title", "") or "").strip().lower()
        if title:
            by_key.setdefault(title, sn)

    by_id = {n["id"]: n for n in nodes}
    node_ids = set(by_id)
    member_of_source: Dict[str, str] = {}
    for n in nodes:
        matched = None
        for key in _store_match_keys(n):
            matched = by_key.get(key)
            if matched is not None:
                break
        if matched is None:
            continue
        stats["matched"] += 1
        n["importance"] = round(float(getattr(matched, "importance", 0.5) or 0.5), 4)
        n["type"] = getattr(matched, "type", None) or n.get("type") or "fact"
        n["t_valid_from"] = float(getattr(matched, "created_at", 0.0) or 0.0)
        n["store_id"] = matched.id
        try:
            valid = graph_store.is_node_valid(matched.id)
        except Exception:
            valid = True
        n["t_valid_to"] = None if valid else float(getattr(matched, "updated_at", 0.0) or 0.0)
        member_of_source[matched.id] = n["id"]

    # Topluluk düğümleri: yalnız grafta üyesi olanlar eklenir (boş topluluk
    # düğümü kullanıcının göremeyeceği bir nokta olurdu).
    for cid, comm in communities.items():
        try:
            edges = graph_store.get_edges(dst=cid, edge_type=KIND_MEMBER_OF, valid_only=True)
        except Exception:
            edges = []
        members = [member_of_source.get(e.src) for e in edges]
        members = [m for m in members if m and m in node_ids]
        if not members:
            continue
        if cid not in node_ids:
            node_ids.add(cid)
            community_ids.add(cid)
            # Etiket birden çok toplulukta aynı olabiliyor (GraphStore etiket
            # yayılımı ölçümü: 7 topluluk "otonom / görev / ajan"); üye sayısı
            # ekiyle ad tekilleşir.
            comm_name = comm.label or cid
            if comm.member_count:
                comm_name = f"{comm_name} ({comm.member_count})"
            comm_node = {
                "id": cid,
                "name": comm_name,
                "group": "community",
                "cluster_group": "cognitive",
                "type": "community",
                "info": comm.summary or comm.label or cid,
                "val": 13,
                "importance": 0.6,
                "t_valid_from": 0.0,
                "t_valid_to": None,
                "member_count": comm.member_count,
                "x": 0.0,
                "y": 0.0,
            }
            nodes.append(comm_node)
            by_id[cid] = comm_node
            stats["communities"] += 1
        for member in members:
            links.append({
                "source": member,
                "target": cid,
                "alias": "community",
                "type": KIND_MEMBER_OF,
                "kind": KIND_MEMBER_OF,
                "weight": _KIND_WEIGHT[KIND_MEMBER_OF],
            })
            stats["member_of"] += 1
            by_id[member]["community_id"] = cid
    return stats


def apply_default_fields(nodes: Iterable[Dict[str, Any]]) -> None:
    """
    GraphStore'da karşılığı olmayan düğümlere tür/önem/zaman varsayılanı.

    Zaman kaydırıcısı ve önem eşiği tek bir eksik alanda kapanıyordu; bu yüzden
    her düğümün `type`, `importance`, `t_valid_from` alanı DOLU olmak zorunda.
    """
    from entropy.memory.obsidian.vault_manager import _graph_node_type

    base = {
        "report": 0.55, "session": 0.4, "fact": 0.5, "episode": 0.4,
        "procedure": 0.55, "entity": 0.35, "task": 0.5, "agent": 0.5,
        "office": 0.5, "community": 0.6,
    }
    struct = {"ego": 1.0, "hub": 0.95, "project": 0.85, "skill": 0.85,
              "subbranch": 0.75, "topic": 0.7, "mcp": 0.7}
    for n in nodes:
        group = n.get("group", "")
        if not n.get("type"):
            n["type"] = _graph_node_type(group) if group not in struct else group
        if n.get("importance") is None:
            n["importance"] = struct.get(group, base.get(n["type"], 0.45))
        if n.get("t_valid_from") is None:
            n["t_valid_from"] = 0.0
        if "t_valid_to" not in n:
            n["t_valid_to"] = None


# --------------------------------------------------------------------------
# M4: seviye, derece, çocuk sayısı, etiketler
# --------------------------------------------------------------------------

def assign_levels(
    nodes: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
) -> None:
    """`level` (0..4), `degree` ve `child_count` alanlarını yazar."""
    children: Dict[str, List[str]] = defaultdict(list)
    degree: Counter = Counter()
    by_id = {n["id"]: n for n in nodes}
    for l in links:
        degree[l["source"]] += 1
        degree[l["target"]] += 1
        if l.get("kind") == KIND_TREE:
            children[l["source"]].append(l["target"])

    roots = [n["id"] for n in nodes if n.get("group") == "ego"] or [
        n["id"] for n in nodes if n.get("group") == "hub"
    ]
    level: Dict[str, int] = {}
    frontier = [(r, 0) for r in roots]
    while frontier:
        nid, depth = frontier.pop()
        if nid in level and level[nid] <= depth:
            continue
        level[nid] = depth
        for child in children.get(nid, ()):  # ağaç kenarları döngüsüzdür
            if child not in level:
                frontier.append((child, min(depth + 1, 4)))

    for n in nodes:
        group = n.get("group", "")
        lvl = level.get(n["id"])
        if lvl is None:
            lvl = _GROUP_LEVEL.get(group, 4)
        elif group in ("community", "topic"):
            lvl = 3
        n["level"] = int(lvl)
        n["degree"] = int(degree.get(n["id"], 0))
        n["child_count"] = len(children.get(n["id"], ()))


def _clean_title(raw: str) -> str:
    text = (raw or "").replace("\r", " ").replace("\n", " ")
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[^\w\s()]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def make_short_label(name: str, taken: Set[str]) -> str:
    """
    Ayırt edici, ≤ 28 karakterlik ve tekil etiket.

    `Gorev_<yetenek>_<tarih>_<konu>` kalıbında konu ve tarih öne alınır; başlıkta
    `Faz NN` ya da tarih varsa etiketin sonuna işaretçi olarak eklenir (182 rapor
    aynı ön eki paylaşıyordu, ayırt eden bilgi kuyruktaydı).
    """
    raw = (name or "").strip()
    marker = ""
    phase = _PHASE_RE.search(raw)
    date = _DATE_RE.search(raw)
    if phase:
        marker = f"F{phase.group(1)}"
    elif date:
        marker = f"{date.group(2)}.{date.group(3)}"

    body = raw
    m = _GOREV_RE.match(_clean_title(raw).replace(" ", "_"))
    if m:
        body = m.group("rest")
    body = _clean_title(body)
    body = _PHASE_RE.sub(" ", body)
    body = _DATE_RE.sub(" ", body)

    words = [w for w in body.split() if w and w.lower() not in _LABEL_STOPWORDS]
    if not words:
        words = [w for w in _clean_title(raw).split() if w] or ["Düğüm"]

    budget = MAX_SHORT_LABEL - (len(marker) + 1 if marker else 0)
    head = ""
    for w in words:
        candidate = (head + " " + w).strip()
        if len(candidate) > budget:
            break
        head = candidate
    if not head:
        head = words[0][:budget]

    def _compose(core: str) -> str:
        return (core + (" " + marker if marker else "")).strip()[:MAX_SHORT_LABEL]

    label = _compose(head)
    if label not in taken:
        taken.add(label)
        return label

    # Çakışma: sıradaki ayırt edici sözcükler denenir, olmazsa sayaç eklenir.
    used = set(head.split())
    for w in words:
        if w in used:
            continue
        core = (head + " " + w)[: max(1, budget)]
        candidate = _compose(core)
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    for i in range(2, 500):
        suffix = f" ·{i}"
        candidate = (label[: MAX_SHORT_LABEL - len(suffix)] + suffix)
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    taken.add(label)
    return label


def assign_labels(nodes: Sequence[Dict[str, Any]]) -> None:
    """Her düğüme tam `label` ve tekil `short_label` yazar."""
    taken: Set[str] = set()
    # Sıra deterministik ve önemliden önemsize: hub'lar kısa adı önce kapar.
    order = sorted(
        nodes,
        key=lambda n: (n.get("level", 4), -float(n.get("importance") or 0.0), n["id"]),
    )
    for n in order:
        full = re.sub(r"\s+", " ", str(n.get("name") or n["id"]).replace("\n", " ")).strip()
        n["label"] = full
        n["short_label"] = make_short_label(full, taken)


# --------------------------------------------------------------------------
# M6: aşırı büyük ebeveynlerin konu alt dallarına bölünmesi
# --------------------------------------------------------------------------

def _topic_tokens(name: str) -> List[str]:
    return [
        w.lower() for w in _clean_title(name).split()
        if len(w) > 3 and w.lower() not in _LABEL_STOPWORDS and not w.isdigit()
    ]


def split_large_parents(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    max_children: int = MAX_CHILDREN,
) -> int:
    """
    `max_children`'dan çok yaprağı olan her ebeveyni konu alt dallarına böler.

    Konu, yaprak başlıklarındaki en ayırt edici ortak terimden gelir; artakalan
    yapraklar `Diğer` alt dalına düşer. Yeni düğümler `group="topic"`,
    `parent_hub` = eski ebeveyn; kenarlar ağaç kenarıdır.
    """
    by_id = {n["id"]: n for n in nodes}
    children: Dict[str, List[str]] = defaultdict(list)
    for l in links:
        if l.get("kind") == KIND_TREE or l.get("is_tree_link"):
            children[l["source"]].append(l["target"])

    created = 0
    for parent, kids in sorted(children.items()):
        if len(kids) <= max_children or parent not in by_id:
            continue
        leaves = [k for k in kids if by_id.get(k) and not children.get(k)]
        if len(leaves) <= max_children:
            continue

        df: Counter = Counter()
        tokens_of: Dict[str, List[str]] = {}
        for k in leaves:
            toks = _topic_tokens(by_id[k].get("name", ""))
            tokens_of[k] = toks
            df.update(set(toks))

        # Hedef grup sayısı: her grup ≤ max_children olacak kadar.
        target_groups = max(2, math.ceil(len(leaves) / max_children) + 1)
        candidates = [t for t, c in df.most_common() if 3 <= c <= max_children]
        chosen: List[str] = []
        assigned: Dict[str, str] = {}
        for term in candidates:
            if len(chosen) >= max(target_groups, 4) * 3:
                break
            members = [k for k in leaves if k not in assigned and term in tokens_of[k]]
            if len(members) < 3:
                continue
            chosen.append(term)
            for k in members:
                assigned[k] = term
        if not chosen:
            continue

        groups: Dict[str, List[str]] = defaultdict(list)
        for k in leaves:
            groups[assigned.get(k, "diger")].append(k)
        # Kalan çok büyükse eşit parçalara bölünür (tek ebeveyn ≤ 80 kuralı).
        rest = groups.pop("diger", [])
        if rest:
            for i in range(0, len(rest), max_children):
                groups[f"diger-{i // max_children + 1}"] = rest[i:i + max_children]
        for term, members in list(groups.items()):
            if len(members) > max_children:
                del groups[term]
                for i in range(0, len(members), max_children):
                    groups[f"{term}-{i // max_children + 1}"] = members[i:i + max_children]

        parent_node = by_id[parent]
        for term, members in sorted(groups.items()):
            slug = re.sub(r"[^a-z0-9]+", "-", term).strip("-") or "grup"
            topic_id = f"topic-{parent}-{slug}"
            if topic_id in by_id:
                continue
            label = term.replace("-", " ").title() if not term.startswith("diger") else "Diğer"
            topic = {
                "id": topic_id,
                "name": f"{label} ({len(members)})",
                "group": "topic",
                "cluster": parent_node.get("cluster", ""),
                "cluster_group": parent_node.get("cluster_group", ""),
                "parent_hub": parent,
                "info": f"Konu alt dalı: {label} — {len(members)} rapor",
                "val": 13,
                "x": parent_node.get("x", 0.0),
                "y": parent_node.get("y", 0.0),
            }
            nodes.append(topic)
            by_id[topic_id] = topic
            links.append({
                "source": parent, "target": topic_id,
                "is_tree_link": True, "kind": KIND_TREE,
                "weight": _KIND_WEIGHT[KIND_TREE],
            })
            created += 1
            member_set = set(members)
            for l in links:
                if l.get("source") == parent and l.get("target") in member_set and (
                    l.get("kind") == KIND_TREE or l.get("is_tree_link")
                ):
                    l["source"] = topic_id
            for k in members:
                by_id[k]["parent_hub"] = topic_id
    return created


# --------------------------------------------------------------------------
# M5: topluluklar
# --------------------------------------------------------------------------

def detect_communities(
    nodes: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    resolution: float = 1.15,
    seed: int = 42,
) -> Dict[str, int]:
    """
    Louvain (networkx varsa) ile topluluk bulur; yoksa çağıran etiket yayılımına
    geri düşer. Küçük topluluklar (≤3) ağaç ebeveyninin topluluğuna katlanır.
    """
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except Exception:
        return {}

    g = nx.Graph()
    g.add_nodes_from(n["id"] for n in nodes)
    for l in links:
        w = float(l.get("weight") or 0.5)
        if g.has_edge(l["source"], l["target"]):
            g[l["source"]][l["target"]]["weight"] += w
        else:
            g.add_edge(l["source"], l["target"], weight=w)

    parts = louvain_communities(g, weight="weight", resolution=resolution, seed=seed)
    parts = sorted(parts, key=lambda c: (-len(c), sorted(c)[0]))
    comm: Dict[str, int] = {}
    for idx, part in enumerate(parts, start=1):
        for nid in part:
            comm[nid] = idx

    # Küçük toplulukları ağaç ebeveyninin topluluğuna katla.
    parent_of: Dict[str, str] = {}
    for l in links:
        if l.get("kind") == KIND_TREE:
            parent_of.setdefault(l["target"], l["source"])
    sizes = Counter(comm.values())
    for _ in range(3):
        tiny = {c for c, s in sizes.items() if s < MIN_COMMUNITY_SIZE}
        if not tiny:
            break
        for nid, cid in list(comm.items()):
            if cid not in tiny:
                continue
            parent = parent_of.get(nid)
            if parent and comm.get(parent) not in tiny and parent in comm:
                comm[nid] = comm[parent]
        sizes = Counter(comm.values())

    # Hâlâ küçük kalanlar en büyük komşu topluluğa katılır.
    sizes = Counter(comm.values())
    tiny = {c for c, s in sizes.items() if s < MIN_COMMUNITY_SIZE}
    if tiny:
        for nid, cid in list(comm.items()):
            if cid not in tiny:
                continue
            neighbours = Counter(
                comm[m] for m in g.neighbors(nid)
                if m in comm and comm[m] not in tiny
            )
            if neighbours:
                comm[nid] = neighbours.most_common(1)[0][0]

    # Hedef aralık: 40'tan çok topluluk varsa en küçükleri komşularına katla.
    sizes = Counter(comm.values())
    while len(sizes) > TARGET_COMMUNITY_RANGE[1]:
        smallest = min(sizes, key=lambda c: (sizes[c], c))
        members = [nid for nid, cid in comm.items() if cid == smallest]
        moved = False
        for nid in members:
            neighbours = Counter(
                comm[m] for m in g.neighbors(nid) if comm.get(m) not in (None, smallest)
            )
            if neighbours:
                comm[nid] = neighbours.most_common(1)[0][0]
                moved = True
        if not moved:
            break
        sizes = Counter(comm.values())

    # Kimlikleri 1..N aralığına sıkıştır (boyuta göre sıralı, deterministik).
    order = [c for c, _ in sorted(sizes.items(), key=lambda p: (-p[1], p[0]))]
    remap = {c: i + 1 for i, c in enumerate(order)}
    return {nid: remap.get(cid, 0) for nid, cid in comm.items()}


def label_communities(
    nodes: Sequence[Dict[str, Any]],
    communities: Dict[str, int],
) -> Dict[int, str]:
    """Her topluluğa üye adlarından üç terimlik etiket üretir."""
    by_comm: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        cid = communities.get(n["id"])
        if cid is not None:
            by_comm[cid].append(n)
    doc_freq: Counter = Counter()
    for cid, members in by_comm.items():
        terms = set()
        for m in members:
            terms.update(_topic_tokens(m.get("name", "")))
        doc_freq.update(terms)
    total = max(1, len(by_comm))

    labels: Dict[int, str] = {}
    for cid, members in by_comm.items():
        tf: Counter = Counter()
        for m in members:
            tf.update(set(_topic_tokens(m.get("name", ""))))
        scored = sorted(
            tf.items(),
            key=lambda p: (-(p[1] * math.log(total / (1 + doc_freq[p[0]]) + 1.0)), p[0]),
        )
        top = [t for t, _ in scored[:3]]
        # Ayırt edici terim yoksa en kalabalık yapısal düğümün adı kullanılır.
        if not top:
            struct = sorted(members, key=lambda m: m.get("level", 4))
            top = [str(struct[0].get("name", "")).strip()[:20]] if struct else [f"Küme {cid}"]
        labels[cid] = " · ".join(t.title() for t in top if t)
    return labels


def modularity(
    nodes: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    key: str = "community",
) -> float:
    """Ağırlıksız Newman modülerliği (ölçüm betiğiyle aynı formül)."""
    comm = {n["id"]: n.get(key) for n in nodes if n.get(key) is not None}
    deg: Dict[str, float] = defaultdict(float)
    intra: Dict[Any, float] = defaultdict(float)
    tot: Dict[Any, float] = defaultdict(float)
    m = 0.0
    for l in links:
        s, t = l["source"], l["target"]
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


# --------------------------------------------------------------------------
# JSON diyeti
# --------------------------------------------------------------------------

MAX_INFO_CHARS = 120
_INFO_PATH_RE = re.compile(r"(?i)^(Obsidian Dosyası: )(.*)$")


def slim_payload(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
) -> None:
    """
    JSON'u küçültür: `info` metinleri kırpılır, dosya yolları kasaya göreli
    yazılır, iç alanlar (`store_id`) düşer, anlamsız `alias` kopyaları silinir.

    Ölçüm 2026-09-09: `info` tek başına düğüm JSON'unun %18'iydi (142 KB);
    bilişsel düğümlerde bütün içerik taşınıyordu.
    """
    for n in nodes:
        n.pop("store_id", None)
        # `label` yalnızca `name`den FARKLIYSA taşınır (UI `label || name`
        # okur): 996 düğümde birebir kopya 52 KB tutuyordu.
        if n.get("label") == n.get("name"):
            n.pop("label", None)
        if n.get("t_valid_to") is None:
            n.pop("t_valid_to", None)
        if isinstance(n.get("t_valid_from"), float):
            n["t_valid_from"] = int(n["t_valid_from"])
        for axis in ("x", "y"):
            if isinstance(n.get(axis), float):
                n[axis] = round(n[axis], 1)
        info = n.get("info")
        if not isinstance(info, str):
            continue
        m = _INFO_PATH_RE.match(info)
        if m:
            path = m.group(2).replace("\\", "/")
            idx = path.rfind("/Entropy/")
            if idx >= 0:
                path = path[idx + len("/Entropy/"):]
            info = m.group(1) + path
        if len(info) > MAX_INFO_CHARS:
            info = info[:MAX_INFO_CHARS - 1].rstrip() + "…"
        n["info"] = info
    for l in links:
        alias = l.get("alias")
        if alias is not None and (
            not alias
            or l.get("kind") in (KIND_SIMILARITY, KIND_TREE)
            or alias == l.get("target")
            or str(l.get("target", "")).endswith("/" + str(alias))
        ):
            l.pop("alias", None)
        if isinstance(l.get("weight"), float):
            l["weight"] = round(l["weight"], 2)


def filter_cross_community_similarity(
    nodes: Sequence[Dict[str, Any]],
    links: List[Dict[str, Any]],
) -> int:
    """
    Topluluklar arası benzerlik kenarlarını düşürür (tasarım §3.5: benzerlik
    yalnızca topluluk içinde çizilir). Ağaç ve wikilink kenarları korunur.
    """
    comm = {n["id"]: n.get("community") for n in nodes}
    keep: List[Dict[str, Any]] = []
    dropped = 0
    for l in links:
        if l.get("kind") == KIND_SIMILARITY:
            a, b = comm.get(l["source"]), comm.get(l["target"])
            if a is not None and b is not None and a != b:
                dropped += 1
                continue
        keep.append(l)
    links[:] = keep
    return dropped


# --------------------------------------------------------------------------
# Giriş noktası
# --------------------------------------------------------------------------

def enrich_graph(
    data: Dict[str, Any],
    graph_store: Any = None,
    max_children: int = MAX_CHILDREN,
) -> Dict[str, Any]:
    """
    Ham graf verisini temizler ve zenginleştirir; aynı sözlüğü döndürür.

    Çağıran (UI) yalnızca bunu çağırır: sıralama önemlidir, çünkü seviye ve
    topluluk hesapları temizlenmiş kenarlar ve bölünmüş dallar üzerinde yapılır.
    """
    nodes: List[Dict[str, Any]] = data.get("nodes", [])
    links: List[Dict[str, Any]] = data.get("links", [])

    links = clean_links(nodes, links)                       # M1
    if graph_store is not None:                             # M3
        data["graph_store_bridge"] = bridge_graph_store(nodes, links, graph_store)
    apply_default_fields(nodes)
    data["topic_nodes"] = split_large_parents(nodes, links, max_children)   # M6
    apply_default_fields(nodes)   # yeni konu düğümleri de alanlarını alsın
    assign_levels(nodes, links)                             # M4
    assign_labels(nodes)                                    # M4

    communities = detect_communities(nodes, links)          # M5
    if communities:
        labels = label_communities(nodes, communities)
        sizes = Counter(communities.values())
        for n in nodes:
            cid = communities.get(n["id"])
            if cid is None:
                continue
            n["community"] = cid
            n["community_label"] = labels.get(cid, "")
            n["community_size"] = int(sizes.get(cid, 0))
        data["communities"] = len(sizes)
        data["community_labels"] = {str(k): v for k, v in sorted(labels.items())}
        data["modularity"] = round(modularity(nodes, links), 4)
        data["dropped_similarity_links"] = filter_cross_community_similarity(nodes, links)

    slim_payload(nodes, links)
    data["nodes"] = nodes
    data["links"] = links
    return data


__all__ = [
    "enrich_graph", "clean_links", "bridge_graph_store", "assign_levels",
    "assign_labels", "make_short_label", "split_large_parents",
    "detect_communities", "label_communities", "modularity",
    "KIND_TREE", "KIND_WIKILINK", "KIND_SIMILARITY", "KIND_MEMBER_OF",
    "KIND_DERIVED_FROM", "MAX_SHORT_LABEL", "MAX_CHILDREN",
]
