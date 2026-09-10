"""
Kategori disiplini (Brain v2, şema v2 — Faz 11.1).

Neden
-----
Üretim veritabanında `category` serbest metindi: denetimde **17 farklı değer**
dolaşıyordu (`semantic` 1276, `procedural` 134, `query` 93, `episodic` 11,
`architecture` 8, `office` 8, `agent` 2, `ego` 2, `session` 2 ve 8 tekil değer)
ve düğümlerin %82,6'sı tek bir kovaya yığılmıştı. `query` diye bir biliş katmanı
yok; o değer tamamen test artığıdır.

Ne yapıyor
----------
CoALA hizalı **kapalı küme**: dört kalıcı katman

    working    (L0) — tur/oturum kapsamlı, geri çağırmaya girmez
    episodic   (L1) — "ne oldu": tur kaydı, rapor künyesi, ofis kartı
    semantic   (L2) — "ne doğru": atomik olgu; kaynak (provenance) zorunlu
    procedural (L3) — "nasıl yapılır": yordam, beceri, playbook künyesi

Kimlik ve kullanıcı onaylı kurallar (L4) **ayrı bir kategori değil**, ayrı bir
bayraktır: `cognitive_nodes.is_identity`. Sebep: aynı bilgi hem anlamsal olgudur
hem kimliğe aittir; kategori kovası bunu taşıyamaz ve beşinci bir kova K7
ölçütünü ("tam 4 kategori") kırar.

Bu modül saf veri işlemedir: veritabanı bilmez, model çağırmaz.
"""

from __future__ import annotations

from typing import Dict, NamedTuple, Set, Tuple

# Kapalı küme. Bu dördü dışında bir değer diske YAZILMAZ.
WORKING = "working"
EPISODIC = "episodic"
SEMANTIC = "semantic"
PROCEDURAL = "procedural"

CANONICAL_CATEGORIES: Tuple[str, ...] = (WORKING, EPISODIC, SEMANTIC, PROCEDURAL)
CANONICAL_SET: Set[str] = set(CANONICAL_CATEGORIES)

# Varsayılan geri çağırma kapsamı (Faz 11.10): L2 + L3.
# L0 çalışma belleği hiç indekslenmez; L1 epizodik yalnızca açık istekle gelir
# (denetimdeki 10 sorgulu kör testte tek kaçırmanın nedeni, epizodik/fikstür
# düğümlerinin top-5'i işgal etmesiydi).
DEFAULT_RECALL_CATEGORIES: Tuple[str, ...] = (SEMANTIC, PROCEDURAL)

# Eski (uydurma) kategorilerin eşlemesi. Anahtarlar küçük harfe indirilmiş
# hâlleriyle aranır. Değer = (kanonik kategori, kimlik bayrağı).
LEGACY_CATEGORY_MAP: Dict[str, Tuple[str, bool]] = {
    # --- L1 epizodik: "ne oldu" kayıtları -----------------------------------
    "query": (EPISODIC, False),          # test artığı + wiki sorgu künyesi
    "session": (EPISODIC, False),        # handoff.py oturum devri
    "office": (EPISODIC, False),         # ofis kartı künyesi
    "agent": (EPISODIC, False),          # ajan olayı
    "task": (EPISODIC, False),
    "report": (EPISODIC, False),
    "episode": (EPISODIC, False),        # graph_store NODE_TYPES aynalaması
    "interaction": (EPISODIC, False),
    "log": (EPISODIC, False),
    # --- L2 anlamsal: "ne doğru" --------------------------------------------
    "architecture": (SEMANTIC, False),   # uydurma "N-Layer" serisinin kovası
    "math": (SEMANTIC, False),
    "federation": (SEMANTIC, False),
    "protocol": (SEMANTIC, False),
    "fact": (SEMANTIC, False),           # graph_store aynalaması
    "entity": (SEMANTIC, False),
    "community": (SEMANTIC, False),
    "knowledge": (SEMANTIC, False),
    "research": (SEMANTIC, False),
    "concept": (SEMANTIC, False),
    "consolidation": (SEMANTIC, False),
    # --- L3 yordamsal: "nasıl yapılır" --------------------------------------
    "procedure": (PROCEDURAL, False),    # graph_store aynalaması
    "skill": (PROCEDURAL, False),
    "playbook": (PROCEDURAL, False),
    "how_to": (PROCEDURAL, False),
    "howto": (PROCEDURAL, False),
    "wiki": (PROCEDURAL, False),
    # --- L0 çalışma belleği --------------------------------------------------
    "scratch": (WORKING, False),
    "checkpoint": (WORKING, False),
    "handoff": (WORKING, False),
    # --- L4 kimlik / kural: kategori değil, BAYRAK ---------------------------
    "ego": (SEMANTIC, True),
    "identity": (SEMANTIC, True),
    "persona": (SEMANTIC, True),
    "self": (SEMANTIC, True),
    "rule": (SEMANTIC, True),
    "promoted_rule": (SEMANTIC, True),
}


class CategoryResolution(NamedTuple):
    """`normalize_category` sonucu."""

    category: str        # kanonik dört değerden biri
    is_identity: bool    # L4 kimlik/kural bayrağı
    mapped: bool         # eski bir addan eşlendi mi
    unknown: bool        # ne kanonik ne de bilinen eski ad


def normalize_category(raw: str) -> CategoryResolution:
    """
    Serbest metin kategoriyi kanonik dörtlüye indirger.

    Bilinmeyen değerler `semantic`e düşer ama `unknown=True` ile işaretlenir;
    kapı (`MemoryGate`) katı kipte bunları reddeder, gevşek kipte eşleyip
    günlüğe yazar. Böylece hiçbir yol sessizce yeni bir kova açamaz.
    """
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in CANONICAL_SET:
        return CategoryResolution(key, False, False, False)
    if key in LEGACY_CATEGORY_MAP:
        category, identity = LEGACY_CATEGORY_MAP[key]
        return CategoryResolution(category, identity, True, False)
    return CategoryResolution(SEMANTIC, False, True, True)


def is_canonical(raw: str) -> bool:
    return (raw or "").strip().lower() in CANONICAL_SET
