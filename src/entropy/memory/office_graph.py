"""
Faz 6 — Entropy Agent Desk ofis belleği: düğüm-bağ (A-MEM) grafı.

Veri kökü **Desk'in kendi kasası**dır:
    <kasa>/Entropy/Desk/Offices/<ofis>/
        OFFICE.md
        agents/<ad>/AGENT.md , MEMORY.md
        memory/graph.json          <- bu modülün deposu
        memory/notes/<slug>.md     <- her düğümün markdown notu
        projects/<proje>/ , reports/ , inbox/ , layout.json

Tasarım kararları:

1. Ofis grafı **yerel ve dosya tabanlıdır** (JSON + markdown). Entropy'nin
   SQLite grafına yazmaz; ofis, Entropy AI'dan habersizdir. Tek yön vardır:
   ofis -> Entropy (`ingest_office_into_entropy`). Ters yön yoktur; bu
   modülde Entropy grafından okuma yapan tek bir çağrı bile bulunmaz.

2. A-MEM (Zettelkasten) ilkesi: yeni not yazıldığında başlık/gövde TF-IDF
   benzerliğiyle en yakın notlara `related` bağı kurulur ve komşu notun
   "## İlgili" bölümü güncellenir. Bağ kurma LLM istemez, ücretsizdir.

3. Not dosyalarında ve graph.json içinde **mutlak yol tutulmaz** (yalnızca
   `notes/<slug>.md` gibi ofise göreli yollar). Aksi hâlde kasa yolundaki
   "Entropy" dizgesi ofis bağlamına sızardı; orkestratör istemi Entropy'ye
   dair hiçbir iz taşımamalıdır (bkz. `orchestrator_context`).
"""

from __future__ import annotations

import json
import math
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from entropy.core.config import config
from entropy.memory.reconcile import tr_lower

# --- sözleşme ---------------------------------------------------------------

DESK_SUBDIR = "Desk"
DESK_SCOPE_PREFIX = "desk:"

# Düğüm türleri (Türkçe anahtar, UI etiketi de aynı).
NOTE_KINDS = ("proje", "gorev", "karar", "bulgu", "ajan", "kaynak")

# Kenar türleri.
EDGE_KINDS = ("produced", "decided", "derived_from", "assigned", "related", "member_of")

# Ofis düğüm türü -> Entropy graf düğüm türü (ingest sırasında).
KIND_TO_ENTROPY_TYPE = {
    "proje": "task",
    "gorev": "task",
    "karar": "fact",
    "bulgu": "fact",
    "ajan": "agent",
    "kaynak": "entity",
    "rapor": "report",
}

# Faz 3 tohumları: kullanıcı ofisini kendisi kuracağı için taşınmaz, silinir.
SEED_OFFICES = ("arastirma-ofisi",)
# Tohum orkestratör/değerlendirici Desk'e ait; Entropy'nin kendi ajanları
# (analist, arastirmaci, yazar) kasada kalır.
SEED_DESK_AGENTS = ("orkestrator", "degerlendirici")
ENTROPY_OWN_AGENTS = ("analist", "arastirmaci", "yazar")

_RELATED_HEADING = "## İlgili"
_STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "için", "icin", "the", "and", "of",
    "olarak", "en", "çok", "cok", "daha", "ama", "veya", "ya", "ki", "mi",
}


# --- yollar -----------------------------------------------------------------


def _safe(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in (name or "")).strip()
    return cleaned or "office"


def _slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^\w]+", "-", tr_lower(text or "")).strip("-")
    return (s or "x")[:limit]


def _vault_root(vault_path: Optional[Path] = None) -> Path:
    return Path(vault_path) if vault_path else Path(config.obsidian_vault_path)


def desk_root(vault_path: Optional[Path] = None) -> Path:
    """`<kasa>/Entropy/Desk` — Desk'in kendi veri kökü."""
    return _vault_root(vault_path) / "Entropy" / DESK_SUBDIR


def desk_offices_dir(vault_path: Optional[Path] = None) -> Path:
    return desk_root(vault_path) / "Offices"


def desk_office_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    return desk_offices_dir(vault_path) / _safe(office)


def legacy_offices_dir(vault_path: Optional[Path] = None) -> Path:
    """Faz 3 ofis kökü (`<kasa>/Entropy/Offices`)."""
    return _vault_root(vault_path) / "Entropy" / "Offices"


def legacy_agents_dir(vault_path: Optional[Path] = None) -> Path:
    return _vault_root(vault_path) / "Entropy" / "Agents"


# --- küçük TF-IDF -----------------------------------------------------------


def _tokens(text: str) -> List[str]:
    return [
        t for t in re.split(r"[^\wçğıöşüÇĞİÖŞÜ]+", tr_lower(text or ""))
        if len(t) > 2 and t not in _STOPWORDS
    ]


def _tfidf_vectors(docs: Sequence[str]) -> List[Dict[str, float]]:
    """Belge başına L2-normalize edilmiş tf-idf sözlüğü."""
    tokenized = [_tokens(d) for d in docs]
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    n = max(1, len(docs))
    vectors: List[Dict[str, float]] = []
    for toks in tokenized:
        tf = Counter(toks)
        vec = {
            # sklearn tarzı düzeltilmiş idf (+1): küçük ofis grafında (n=2)
            # ham log terimi 0'a düşer ve her benzerlik sıfır çıkardı.
            term: (count / len(toks)) * (math.log((1 + n) / (1 + df[term])) + 1.0)
            for term, count in tf.items()
        } if toks else {}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({k: v / norm for k, v in vec.items()})
    return vectors


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


# --- graf -------------------------------------------------------------------


class OfficeGraph:
    """
    Tek bir ofisin düğüm-bağ belleği.

    Depo: `<ofis>/memory/graph.json` (düğümler + kenarlar) ve her düğüm için
    `<ofis>/memory/notes/<slug>.md`. JSON tek yazımlık (atomik replace) tutulur;
    OneDrive'da mtime güvenilmez olduğu için sürüm/karşılaştırma içerik
    üzerinden yapılır.
    """

    def __init__(self, office: str, vault_path: Optional[Path] = None):
        self.office = office
        self.vault_path = Path(vault_path) if vault_path else None
        self.root = desk_office_dir(office, vault_path)
        self.memory_dir = self.root / "memory"
        self.notes_dir = self.memory_dir / "notes"
        self.graph_path = self.memory_dir / "graph.json"
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._load()

    # -- kalıcılık ---------------------------------------------------

    def _load(self) -> None:
        try:
            raw = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for node in raw.get("nodes", []) or []:
            if isinstance(node, dict) and node.get("id"):
                self.nodes[str(node["id"])] = node
        for edge in raw.get("edges", []) or []:
            if isinstance(edge, dict) and edge.get("src") and edge.get("dst"):
                self.edges.append(edge)

    def save(self) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "office": self.office,
            "version": 1,
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }
        tmp = self.graph_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self.graph_path)
        return self.graph_path

    # -- yazma -------------------------------------------------------

    def add_note(
        self,
        kind: str,
        title: str,
        body: str = "",
        links: Optional[Sequence[Tuple[str, str]]] = None,
        agent: Optional[str] = None,
        auto_link: bool = True,
        max_auto_links: int = 3,
        threshold: float = 0.12,
        node_id: Optional[str] = None,
        source: str = "",
    ) -> Dict[str, Any]:
        """
        Yeni not düğümü yazar; markdown notunu üretir ve A-MEM bağlarını kurar.

        `links` = [(hedef_düğüm_id, kenar_türü), ...] açık bağlar.
        `agent` verilirse ajan düğümü açılır ve nota `assigned` bağı kurulur.
        Dönen sözlük düğümün kendisidir (`id`, `kind`, `title`, `note`).
        """
        kind = (kind or "bulgu").strip().lower()
        nid = node_id or self._unique_id(kind, title)
        now = time.time()
        node = {
            "id": nid,
            "kind": kind if kind in NOTE_KINDS else "bulgu",
            "title": (title or nid).strip(),
            "body": (body or "").strip(),
            "created_at": now,
            "updated_at": now,
            "note": f"notes/{_slug(nid)}.md",
            "source": source,
        }
        if agent:
            node["agent"] = agent
        self.nodes[nid] = node

        for dst, etype in (links or []):
            self.link(nid, dst, etype)

        if agent:
            agent_id = self.ensure_agent(agent)
            self.link(agent_id, nid, "assigned")

        related: List[str] = []
        if auto_link:
            related = [
                other for other, _score in self.query(
                    f"{node['title']} {node['body']}", k=max_auto_links, exclude=(nid,)
                ) if _score >= threshold
            ]
            for other in related:
                self.link(nid, other, "related")
                self._append_related_section(other, nid)

        self._write_note(node, related)
        self.save()
        return node

    def ensure_agent(self, agent: str) -> str:
        """Ajan düğümünü (varsa) döndürür, yoksa açar. Not dosyası yazmaz."""
        agent_id = f"ajan-{_slug(agent)}"
        if agent_id not in self.nodes:
            now = time.time()
            self.nodes[agent_id] = {
                "id": agent_id, "kind": "ajan", "title": agent, "body": "",
                "created_at": now, "updated_at": now, "note": "", "source": "",
            }
        return agent_id

    def link(self, src: str, dst: str, edge_type: str = "related", weight: float = 1.0) -> bool:
        """Kenar ekler (aynısı varsa yinelemez). Bilinmeyen tür `related` olur."""
        if not src or not dst or src == dst:
            return False
        etype = edge_type if edge_type in EDGE_KINDS else "related"
        for edge in self.edges:
            if edge["src"] == src and edge["dst"] == dst and edge["type"] == etype:
                return False
        self.edges.append(
            {"src": src, "dst": dst, "type": etype, "weight": float(weight), "at": time.time()}
        )
        return True

    def ingest_agent_memories(self) -> int:
        """
        `agents/<ad>/MEMORY.md` girdilerini düğüme çevirir ve ajana `member_of`
        ile bağlar. Ofis dosyaları okunur, değiştirilmez.
        """
        agents_dir = self.root / "agents"
        added = 0
        if not agents_dir.is_dir():
            return 0
        for memory_file in sorted(agents_dir.glob("*/MEMORY.md")):
            name = memory_file.parent.name
            agent_id = self.ensure_agent(name)
            try:
                text = memory_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("-") or len(stripped) < 12:
                    continue
                entry = stripped.lstrip("-").strip()
                nid = f"bulgu-{_slug(name)}-{_slug(entry, 24)}"
                if nid in self.nodes:
                    continue
                self.add_note(
                    "bulgu", entry[:120], entry, node_id=nid,
                    source=f"agents/{name}/MEMORY.md", auto_link=True,
                )
                self.link(self.nodes[nid]["id"], agent_id, "member_of")
                added += 1
        if added:
            self.save()
        return added

    # -- okuma -------------------------------------------------------

    def neighbors(self, node_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """`node_id`'nin (yönsüz) komşuları; `depth` adım genişletir."""
        seen = {node_id}
        frontier = {node_id}
        for _ in range(max(1, depth)):
            nxt = set()
            for edge in self.edges:
                if edge["src"] in frontier:
                    nxt.add(edge["dst"])
                elif edge["dst"] in frontier:
                    nxt.add(edge["src"])
            frontier = nxt - seen
            seen |= frontier
            if not frontier:
                break
        return [self.nodes[n] for n in seen if n != node_id and n in self.nodes]

    def query(
        self, text: str, k: int = 5, exclude: Sequence[str] = ()
    ) -> List[Tuple[str, float]]:
        """Başlık+gövde TF-IDF kosinüsüyle en yakın `k` düğüm: [(id, skor)]."""
        candidates = [n for n in self.nodes.values() if n["id"] not in set(exclude)]
        if not candidates or not (text or "").strip():
            return []
        docs = [f"{n.get('title','')} {n.get('body','')}" for n in candidates] + [text]
        vecs = _tfidf_vectors(docs)
        qvec = vecs[-1]
        scored = [
            (n["id"], _cosine(vecs[i], qvec)) for i, n in enumerate(candidates)
        ]
        scored.sort(key=lambda p: (-p[1], p[0]))
        return [(nid, round(s, 4)) for nid, s in scored[:k] if s > 0]

    def to_view_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Desk "Bellek" sekmesi için düğüm/kenar JSON'u (mini-graf çizimi)."""
        nodes_out = [
            {
                "id": n["id"],
                "name": n.get("title") or n["id"],
                "group": n.get("kind", "bulgu"),
                "kind": n.get("kind", "bulgu"),
                "office": self.office,
                "created_at": n.get("created_at", 0.0),
                "note": n.get("note", ""),
                "degree": self._degree(n["id"]),
            }
            for n in self.nodes.values()
        ]
        links_out = [
            {
                "source": e["src"], "target": e["dst"], "type": e["type"],
                "alias": e["type"], "weight": e.get("weight", 1.0),
            }
            for e in self.edges
            if e["src"] in self.nodes and e["dst"] in self.nodes
        ]
        return {"nodes": nodes_out, "links": links_out}

    def export_markdown(self) -> str:
        """Grafın insan okunur özeti (ofis raporlarına eklenebilir)."""
        lines = [f"# {self.office} — Ofis Belleği", ""]
        for kind in NOTE_KINDS:
            group = [n for n in self.nodes.values() if n.get("kind") == kind]
            if not group:
                continue
            lines.append(f"## {kind.capitalize()} ({len(group)})")
            for n in sorted(group, key=lambda x: x.get("created_at", 0.0)):
                first = (n.get("body") or "").strip().splitlines()
                summary = first[0][:160] if first else ""
                lines.append(f"- [[{n['title']}]]{(' — ' + summary) if summary else ''}")
            lines.append("")
        lines.append(f"Bağ sayısı: {len(self.edges)}")
        return "\n".join(lines) + "\n"

    # -- iç yardımcılar ----------------------------------------------

    def _degree(self, node_id: str) -> int:
        return sum(1 for e in self.edges if e["src"] == node_id or e["dst"] == node_id)

    def _unique_id(self, kind: str, title: str) -> str:
        base = f"{kind}-{_slug(title)}"
        nid = base
        i = 2
        while nid in self.nodes:
            nid = f"{base}-{i}"
            i += 1
        return nid

    def _write_note(self, node: Dict[str, Any], related: Sequence[str]) -> Path:
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        path = self.notes_dir / f"{_slug(node['id'])}.md"
        lines = [
            "---",
            f"id: {node['id']}",
            f"kind: {node['kind']}",
            f"office: {self.office}",
            "---",
            "",
            f"# {node['title']}",
            "",
            node.get("body", ""),
            "",
            _RELATED_HEADING,
        ]
        for other in related:
            title = self.nodes.get(other, {}).get("title", other)
            lines.append(f"- [[{title}]]")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def _append_related_section(self, node_id: str, new_id: str) -> None:
        """Komşu notun "## İlgili" bölümüne yeni notu ekler (A-MEM güncellemesi)."""
        node = self.nodes.get(node_id)
        if not node or not node.get("note"):
            return
        path = self.root / "memory" / node["note"]
        title = self.nodes.get(new_id, {}).get("title", new_id)
        entry = f"- [[{title}]]"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return
        if entry in text:
            return
        if _RELATED_HEADING in text:
            text = text.rstrip() + "\n" + entry + "\n"
        else:
            text = text.rstrip() + f"\n\n{_RELATED_HEADING}\n{entry}\n"
        try:
            path.write_text(text, encoding="utf-8")
        except OSError:
            return
        node["updated_at"] = time.time()


# --- orkestratör bağlamı (Entropy'den habersiz) ------------------------------


def orchestrator_context(
    office: str, task: str = "", k: int = 6, vault_path: Optional[Path] = None
) -> str:
    """
    Ofis orkestratörü için istem bağlamı — **yalnızca ofis grafından** üretilir.

    Orkestratörler Entropy AI'dan habersizdir: burada ne Entropy grafı okunur
    ne de "Entropy" dizgesi çıktıya girer (son adımda süzülür; mutlak yol da
    basılmaz).
    """
    graph = OfficeGraph(office, vault_path)
    if not graph.nodes:
        return ""
    if (task or "").strip():
        picked = [nid for nid, _ in graph.query(task, k=k)]
    else:
        picked = [
            n["id"] for n in sorted(
                graph.nodes.values(), key=lambda x: -x.get("created_at", 0.0)
            )[:k]
        ]
    lines = [f"# Ofis Belleği ({office})", ""]
    for nid in picked:
        node = graph.nodes.get(nid)
        if not node:
            continue
        body = " ".join((node.get("body") or "").split())[:220]
        lines.append(f"- ({node.get('kind')}) {node.get('title')}{(': ' + body) if body else ''}")
    text = "\n".join(lines) + "\n"
    # Güvenlik ağı: kasadan gelen bir metin "Entropy" içerse bile istem taşımaz.
    return re.sub(r"[Ee]ntrop[iy][A-Za-zİıĞğŞşÖöÇçÜü]*", "sistem", text)


# --- Entropy'ye akış (tek yön) ----------------------------------------------


def office_scope(office: str) -> str:
    return f"{DESK_SCOPE_PREFIX}{_safe(office)}"


def ingest_office_into_entropy(
    office: str,
    store: Optional[Any] = None,
    vault_path: Optional[Path] = None,
    max_reports: int = 20,
) -> Dict[str, Any]:
    """
    Ofis projelerini/kararlarını/bulgularını ve raporlarını Entropy'nin birleşik
    grafına `scope="desk:<ofis>"` ile ekler; hepsi ofis düğümüne `member_of`
    ile bağlanır. Ters yön YOKTUR: ofis grafına hiçbir şey yazılmaz.
    """
    from entropy.memory.graph_store import GraphStore

    st = store if store is not None else GraphStore()
    graph = OfficeGraph(office, vault_path)
    scope = office_scope(office)
    stats = {"scope": scope, "nodes": 0, "reports": 0, "edges": 0, "office_id": ""}

    office_id = f"office-{_slug(office)}"
    st.upsert_node(
        office_id, "office", office, body=f"desk ofisi: {office}", scope=scope,
        provenance=str(desk_office_dir(office, vault_path)),
    )
    stats["office_id"] = office_id

    for node in graph.nodes.values():
        ntype = KIND_TO_ENTROPY_TYPE.get(node.get("kind", ""), "fact")
        nid = f"desk-{_slug(office)}-{node['id']}"
        st.upsert_node(
            nid, ntype, node.get("title") or node["id"], body=node.get("body", ""),
            scope=scope, provenance=f"{office}/{node.get('note') or node['id']}",
            metadata={"desk_office": office, "desk_kind": node.get("kind")},
        )
        stats["nodes"] += 1
        if not st.get_edges(src=nid, dst=office_id, edge_type="member_of"):
            st.add_edge(nid, office_id, "member_of", provenance=office)
            stats["edges"] += 1

    reports_dir = desk_office_dir(office, vault_path) / "reports"
    if reports_dir.is_dir():
        for report in sorted(reports_dir.glob("*.md"))[:max_reports]:
            try:
                text = report.read_text(encoding="utf-8", errors="ignore")[:8000]
            except OSError:
                continue
            nid = f"desk-{_slug(office)}-report-{_slug(report.stem)}"
            st.upsert_node(
                nid, "report", report.stem, body=text, scope=scope,
                provenance=str(report), metadata={"desk_office": office},
            )
            if not st.get_edges(src=nid, dst=office_id, edge_type="member_of"):
                st.add_edge(nid, office_id, "member_of", provenance=office)
                stats["edges"] += 1
            stats["reports"] += 1

    # Ofis projeleri de Entropy'nin belleğine akar (klasör adı = proje).
    projects_dir = desk_office_dir(office, vault_path) / "projects"
    if projects_dir.is_dir():
        for proj in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
            nid = f"desk-{_slug(office)}-proje-{_slug(proj.name)}"
            st.upsert_node(
                nid, "task", proj.name, body=f"{office} ofisi projesi: {proj.name}",
                scope=scope, provenance=str(proj),
                metadata={"desk_office": office, "desk_kind": "proje"},
            )
            if not st.get_edges(src=nid, dst=office_id, edge_type="member_of"):
                st.add_edge(nid, office_id, "member_of", provenance=office)
                stats["edges"] += 1
            stats["nodes"] += 1
    return stats


def ingest_all_offices(
    store: Optional[Any] = None, vault_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Tüm Desk ofislerini Entropy grafına alır (kota harcamaz, model yok)."""
    out = []
    base = desk_offices_dir(vault_path)
    if not base.is_dir():
        return out
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        out.append(ingest_office_into_entropy(child.name, store=store, vault_path=vault_path))
    return out


def desk_scopes(vault_path: Optional[Path] = None) -> List[str]:
    """Kasadaki tüm Desk ofisleri için kapsam adları (salt okunur görünürlük)."""
    base = desk_offices_dir(vault_path)
    if not base.is_dir():
        return []
    return [office_scope(p.name) for p in sorted(base.iterdir()) if p.is_dir()]


# --- roster (Entropy manifesti için bilgi katmanı) ---------------------------


def _front_matter(path: Path) -> Dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    body = text.split("---", 2)
    if len(body) < 3:
        return {}
    out: Dict[str, str] = {}
    for line in body[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip().lower()] = value.strip()
    return out


def desk_roster(vault_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Entropy'nin manifestine eklenecek orkestratör listesi.

    Her ofis için: `office`, `orchestrator`, `purpose`, `last_report`,
    `agents`, `path`. Entropy tüm orkestratörleri bilir; orkestratörler
    Entropy'yi bilmez (bkz. `orchestrator_context`).
    """
    base = desk_offices_dir(vault_path)
    roster: List[Dict[str, Any]] = []
    if not base.is_dir():
        return roster
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        fm = _front_matter(child / "OFFICE.md")
        reports_dir = child / "reports"
        last_report = ""
        if reports_dir.is_dir():
            # OneDrive'da mtime güvenilmez; ad sıralaması (tarih önekli) kullanılır.
            names = sorted((p.name for p in reports_dir.glob("*.md")), reverse=True)
            last_report = names[0] if names else ""
        agents_dir = child / "agents"
        agents = (
            [p.name for p in sorted(agents_dir.iterdir()) if p.is_dir()]
            if agents_dir.is_dir() else []
        )
        roster.append({
            "office": fm.get("name") or child.name,
            "orchestrator": fm.get("orchestrator", ""),
            "purpose": fm.get("purpose", ""),
            "last_report": last_report,
            "agents": agents,
            "path": str(child),
        })
    return roster


# --- Faz 3 -> Faz 6 geçişi ---------------------------------------------------


def migrate_legacy_offices(
    vault_path: Optional[Path] = None, dry_run: bool = True
) -> Dict[str, Any]:
    """
    `Entropy/Offices/*` -> `Entropy/Desk/Offices/*` taşıması ve tohum temizliği.

    - Tohum ofis (`arastirma-ofisi`) taşınmaz, silinir: kullanıcı ofisini
      kendisi kuracak.
    - Tohum Desk ajanları (orkestrator, degerlendirici) `Entropy/Agents`'tan
      kaldırılır; analist/arastirmaci/yazar Entropy'nin kendi ajanları olarak
      kalır.
    - `dry_run=True` (varsayılan) hiçbir şeye dokunmaz, yalnızca planı döndürür.
    """
    plan: Dict[str, Any] = {
        "dry_run": bool(dry_run), "moves": [], "deletes": [], "kept": [],
        "conflicts": [], "applied": False,
    }
    src_base = legacy_offices_dir(vault_path)
    dst_base = desk_offices_dir(vault_path)

    if src_base.is_dir():
        for child in sorted(src_base.iterdir()):
            if child.is_file():
                plan["deletes"].append(str(child))
                continue
            if child.name in SEED_OFFICES:
                plan["deletes"].append(str(child))
                continue
            target = dst_base / child.name
            if target.exists():
                plan["conflicts"].append(str(target))
                continue
            plan["moves"].append({"from": str(child), "to": str(target)})

    agents_base = legacy_agents_dir(vault_path)
    if agents_base.is_dir():
        for child in sorted(p for p in agents_base.iterdir() if p.is_dir()):
            if child.name in SEED_DESK_AGENTS:
                plan["deletes"].append(str(child))
            else:
                plan["kept"].append(str(child))

    if dry_run:
        return plan

    for move in plan["moves"]:
        dst = Path(move["to"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(move["from"], str(dst))
    for target in plan["deletes"]:
        p = Path(target)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    # Kaynak kök boş kaldıysa kaldırılır (kullanıcı dosyası kalmışsa dokunulmaz).
    try:
        if src_base.is_dir() and not any(src_base.iterdir()):
            src_base.rmdir()
    except OSError:
        pass
    plan["applied"] = True
    return plan


__all__ = [
    "OfficeGraph", "NOTE_KINDS", "EDGE_KINDS", "DESK_SCOPE_PREFIX",
    "desk_root", "desk_offices_dir", "desk_office_dir", "office_scope",
    "orchestrator_context", "ingest_office_into_entropy", "ingest_all_offices",
    "desk_scopes", "desk_roster", "migrate_legacy_offices",
]
