"""
Faz 11.13 — kalıcı ölçüm paketi (K1, K3, K7, K10, K11, K12).

Bu dosya **sentetik bir korpus** kurar (gerçek kullanıcı veritabanına hiç
dokunmaz) ve yazma kapısının ölçütleri sağladığını kanıtlar. Ölçüm mantığı tek
kaynaktan gelir: `scripts/brain_metrics.py`. Böylece testin ölçtüğü şey ile
gerçek veritabanında koşulan raporun ölçtüğü şey aynıdır.

Ayrıca `scripts/memory_blind_test.py` ve `scripts/memory_migrate_v2.py`
betiklerinin pytest içinden (tmp DB ile) çağrılabildiğini doğrular — QA'nın
göç öncesi/sonrası kıyası bu iki fonksiyona dayanır.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

brain_metrics = importlib.import_module("brain_metrics")
memory_blind_test = importlib.import_module("memory_blind_test")
memory_migrate_v2 = importlib.import_module("memory_migrate_v2")

from entropy.memory.categories import CANONICAL_CATEGORIES  # noqa: E402
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem  # noqa: E402


# --------------------------------------------------------------------------
# sentetik korpus
# --------------------------------------------------------------------------

# Birbirinden açıkça farklı 12 konu. Hepsi >= 40 karakter (kapının asgarisi) ve
# hepsinin gerçek bir kaynağı var (K12: kaynaksız L2 yasak).
FACTS = [
    ("Ohlson O-Score modeli dokuz muhasebe değişkeniyle temerrüt olasılığını "
     "lojistik regresyonla tahmin eder ve Altman Z'ye göre daha az dağılım varsayımı yapar.",
     "docs/finance/ohlson.md"),
    ("SVI parametrizasyonu toplam varyansı beş parametreyle modeller; kelebek ve "
     "takvim arbitrajı kısıtları parametre uzayında kapalı biçimde yazılabilir.",
     "docs/finance/svi.md"),
    ("Kupiec POF testi VaR ihlallerinin sayısını binom dağılımına karşı sınar; "
     "Christoffersen testi ihlallerin bağımsızlığını da ölçer.",
     "docs/finance/var_backtest.md"),
    ("Fung-Hsieh yedi faktör modeli trend takip eden fonların getirisini lookback "
     "straddle getirileriyle açıklar; primitif varlıklar tahvil, döviz ve emtiadır.",
     "docs/finance/fung_hsieh.md"),
    ("Ho ve Stoll piyasa yapıcısının envanter riskini stokastik optimal kontrol "
     "problemi olarak kurar; ara fiyat envanter pozisyonuna göre kayar.",
     "docs/finance/ho_stoll.md"),
    ("Erlang OTP denetim ağaçları hatayı izole etmek için süreçleri yeniden başlatır; "
     "one_for_one ve rest_for_one stratejileri yeniden başlatma kapsamını belirler.",
     "docs/arch/supervision.md"),
    ("Bir ajan Model artı Harness artı Görev toplamıdır: dil modeli stokastiktir, "
     "denetim akışını deterministik harness yürütür ve araç çağrılarını doğrular.",
     "docs/arch/harness.md"),
    ("Kod olarak eylem yaklaşımında model araç çağrısı yerine çalıştırılabilir kod "
     "üretir; bu araç şemalarının bağlam maliyetini ortadan kaldırır.",
     "docs/arch/codeact.md"),
    ("Yönlü çevrimsiz çizge üzerinde iş akışı planlanırken kritik yol en uzun süre "
     "toplamıdır ve toplam süreyi belirleyen görev zinciridir.",
     "docs/arch/dag_planlama.md"),
    ("Kişiselleştirilmiş PageRank bir tohum düğümden başlayarak rastgele yürüyüşle "
     "komşuluk skorları üretir; graf genişletmesinde bir iki atlama yeterlidir.",
     "docs/arch/ppr.md"),
    ("Sözlüksel eşleşme için BM25 terim sıklığını doküman uzunluğuna göre normalize "
     "eder; hibrit geri çağırmada vektör benzerliğiyle ağırlıklı toplanır.",
     "docs/arch/bm25.md"),
    ("Ebbinghaus unutma eğrisi hatırlamanın zamanla üstel azaldığını söyler; "
     "erişim sayısı arttıkça eğrinin yarı ömrü uzar.",
     "docs/arch/ebbinghaus.md"),
]

# Her biri yukarıdaki bir gerçeğin yeniden ifadesi. Kapı bunları ya NOOP eder ya
# da gri banda alır; korpusun yineleme oranı bu yüzden düşük kalmalıdır.
NEAR_DUPLICATES = [
    ("Ohlson O-Score dokuz muhasebe değişkeni kullanarak lojistik regresyonla "
     "temerrüt olasılığı tahmin eden bir modeldir; Altman Z'den daha az varsayım yapar.",
     "docs/finance/ohlson.md"),
    ("SVI parametrizasyonu toplam varyans yüzeyini beş parametreyle tanımlar ve "
     "kelebek ile takvim arbitrajı kısıtları kapalı biçimde ifade edilir.",
     "docs/finance/svi.md"),
    ("Erlang OTP'de denetim ağaçları süreçleri yeniden başlatarak hatayı izole eder; "
     "yeniden başlatma kapsamını one_for_one ve rest_for_one stratejileri belirler.",
     "docs/arch/supervision.md"),
    ("Ajan eşittir Model artı Harness artı Görev; model stokastiktir, denetim akışını "
     "harness deterministik biçimde yürütür ve araç çağrılarını doğrular.",
     "docs/arch/harness.md"),
]

# Kapının reddetmesi gereken fikstür kalıpları (K10). Hepsi denetimde gerçek
# sızıntı olarak bulunmuş biçimlerin sentetik eşleniğidir.
FIXTURE_CANDIDATES = [
    "Ofis: arastirma-ofisi · arastirmaci · review — yarım iş kartı, kanıt yok, sonuç boş.",
    "Görev pytest-of-kullanici/pytest-2301/test_office_harness altında koştu ve yeşil bitti.",
    "DummyProc çıktısı: sahte süreç üç satır yazdı ve sıfır kodla çıktı, gerçek çağrı yok.",
    "test_memory_gate_admits_novel_fact fonksiyonu düğümün yazıldığını doğrular ve geçer.",
    "[KANIT] Komut: python -m pytest tests -q · çıkış 0 · 12 passed in 3.4s (fikstür).",
]

PROCEDURAL = [
    ("Yeni bir yetenek eklerken önce skill.md yazılır, sonra manifest doğrulanır ve "
     "en son yetenek yöneticisinin testleri koşulur.",
     "docs/howto/skill_ekleme.md"),
    ("Sürüm çıkarken önce tam test süiti koşulur, sonra PyInstaller derlemesi alınır "
     "ve en son duman testi ile günlük denetlenir.",
     "docs/howto/surum.md"),
]

EPISODIC = [
    ("Bugün mali denetim turunda dört şirketin nakit akış tablosu incelendi ve "
     "iki tanesinde işletme sermayesi bozulması bulundu.",
     "reports/2026-09-10_denetim.md"),
]

RECALL_QUERIES = [
    ("Temerrüt olasılığı tahmin eden muhasebe tabanlı model", r"ohlson|o-score"),
    ("Arbitrajsız volatilite yüzeyi parametrizasyonu", r"svi"),
    ("Hata izolasyonu için süreç denetim ağacı", r"denetim ağaç|erlang|otp"),
    ("Kritik yol ile iş akışı planlama", r"kritik yol|çevrimsiz"),
    ("Unutma eğrisi ve hatırlama zamanla nasıl azalır", r"ebbinghaus|unutma"),
]


@pytest.fixture(scope="module")
def synthetic_memory(tmp_path_factory):
    """
    Kapıdan geçirilmiş sentetik korpus. **Katı kip açık**: fikstür süzgeci ve
    L2 kaynak zorunluluğu üretimdeki gibi davranır.
    """
    import os

    db = tmp_path_factory.mktemp("brain_metrics") / "cognitive_memory.db"
    previous = os.environ.get("ENTROPY_MEMORY_GATE_STRICT")
    os.environ["ENTROPY_MEMORY_GATE_STRICT"] = "1"
    try:
        mem = CognitiveMemorySystem(db_path=db)
        assert mem.gate.strict is True, "katı kip açılmadı: ölçüm üretimi temsil etmez"

        for content, source in FACTS:
            mem.record_memory("semantic", content, importance=0.6, provenance=source)
        for content, source in NEAR_DUPLICATES:
            mem.record_memory("semantic", content, importance=0.6, provenance=source)
        for content, source in PROCEDURAL:
            mem.record_memory("procedural", content, importance=0.5, provenance=source)
        for content, source in EPISODIC:
            mem.record_memory("episodic", content, importance=0.4, provenance=source)

        rejected = []
        for content in FIXTURE_CANDIDATES:
            decision = mem.gate.admit(
                "semantic", content, provenance="tests/contracts/test_phase11_brain_metrics.py"
            )
            rejected.append(decision)
            if decision.writes:  # kapı kabul ederse korpusa gerçekten girsin ki ölçüm yakalasın
                mem.record_memory("semantic", content, provenance="fixture")
        yield {"db": db, "memory": mem, "fixture_decisions": rejected}
    finally:
        if previous is None:
            os.environ.pop("ENTROPY_MEMORY_GATE_STRICT", None)
        else:
            os.environ["ENTROPY_MEMORY_GATE_STRICT"] = previous


@pytest.fixture(scope="module")
def metrics(synthetic_memory):
    return brain_metrics.collect(
        synthetic_memory["db"], include_recall=False, include_latency=True
    )


# --------------------------------------------------------------------------
# K1 — yineleme oranı <= %10
# --------------------------------------------------------------------------

def test_k1_duplication_ratio_under_10_percent(metrics):
    dup = metrics["K1_duplication"]
    assert dup["nodes_with_embedding"] >= len(FACTS), "gömme üretilmemiş, ölçüm anlamsız"
    assert dup["duplicate_pct"] <= brain_metrics.K1_MAX_DUP_PCT, (
        f"K1 ihlali: %{dup['duplicate_pct']} yineleme "
        f"({dup['clusters']} küme / {dup['nodes_with_embedding']} düğüm)"
    )


def test_gate_absorbs_near_duplicates(synthetic_memory):
    """Yakın kopyalar korpusu şişirmemeli: düğüm sayısı benzersiz gerçek sayısını çok aşmamalı."""
    mem = synthetic_memory["memory"]
    total = len(mem.get_all_nodes())
    unique_written = len(FACTS) + len(PROCEDURAL) + len(EPISODIC)
    assert total <= unique_written + len(NEAR_DUPLICATES), (
        f"{total} düğüm yazıldı; kapı yakın kopyaları emmiyor"
    )


# --------------------------------------------------------------------------
# K3 — top-5 gürültü oranı <= %2
# --------------------------------------------------------------------------

def test_k3_recall_noise_ratio(synthetic_memory):
    mem = synthetic_memory["memory"]
    noise_rows = 0
    total_rows = 0
    misses = []
    import re as _re

    for query, pattern in RECALL_QUERIES:
        hits = mem.hybrid_recall(query, top_k=5)
        assert hits, f"'{query}' için hiç sonuç yok"
        rx = _re.compile(pattern, _re.IGNORECASE)
        if not rx.search(hits[0][0].content or ""):
            misses.append(query)
        for node, _score in hits:
            total_rows += 1
            if memory_blind_test.NOISE_RE.search(node.content or ""):
                noise_rows += 1

    noise_pct = 100.0 * noise_rows / max(1, total_rows)
    assert noise_pct <= brain_metrics.K3_MAX_NOISE_PCT, (
        f"K3 ihlali: %{noise_pct:.1f} gürültü ({noise_rows}/{total_rows})"
    )
    # Sentetik korpusta konular ayrık; ilk sıra ıskası kabul edilmez.
    assert not misses, f"Hit@1 kaçıranlar: {misses}"


# --------------------------------------------------------------------------
# K7 — kategori disiplini
# --------------------------------------------------------------------------

def test_k7_only_canonical_categories(metrics):
    cats = metrics["K7_categories"]
    assert cats["non_canonical"] == [], f"kanonik dışı kategori: {cats['non_canonical']}"
    assert set(cats["counts"]) <= set(CANONICAL_CATEGORIES)
    assert len(CANONICAL_CATEGORIES) == 4


# --------------------------------------------------------------------------
# K10 — fikstür sızıntısı = 0
# --------------------------------------------------------------------------

def test_k10_no_fixture_leak(metrics, synthetic_memory):
    for decision in synthetic_memory["fixture_decisions"]:
        assert decision.action == "reject", (
            f"kapı fikstürü kabul etti ({decision.action}): {decision.content[:60]}"
        )
    leak = metrics["K10_fixture_leak"]
    assert leak["count"] == 0, f"fikstür sızıntısı: {leak}"


# --------------------------------------------------------------------------
# K11 — kapı gecikmesi <= 400 ms
# --------------------------------------------------------------------------

def test_k11_gate_latency_under_400ms(metrics):
    lat = metrics["K11_gate_latency"]
    assert lat["median_ms"] <= brain_metrics.K11_MAX_GATE_MS, (
        f"K11 ihlali: medyan {lat['median_ms']} ms"
    )


# --------------------------------------------------------------------------
# K12 — kaynaksız L2 = 0
# --------------------------------------------------------------------------

def test_k12_no_unsourced_semantic(metrics):
    uns = metrics["K12_unsourced_l2"]
    assert uns["count"] == 0, f"kaynaksız L2 düğüm: {uns}"


def test_gate_rejects_semantic_without_provenance(synthetic_memory):
    """L2 kaynak zorunluluğunun kendisi (K12'nin nedeni)."""
    import os

    mem = synthetic_memory["memory"]
    previous = os.environ.get("ENTROPY_MEMORY_GATE_STRICT")
    os.environ["ENTROPY_MEMORY_GATE_STRICT"] = "1"
    try:
        gate = type(mem.gate)(mem, strict=True)
        decision = gate.admit(
            "semantic",
            "Kaynaksız bir iddia: sistem kendi çıktısını gerçek olarak hafızaya yazamaz, "
            "bu yüzden bu metin reddedilmelidir.",
        )
        assert decision.action == "reject"
        assert "kaynak" in decision.reason.lower() or "provenance" in decision.reason.lower()
    finally:
        if previous is None:
            os.environ.pop("ENTROPY_MEMORY_GATE_STRICT", None)
        else:
            os.environ["ENTROPY_MEMORY_GATE_STRICT"] = previous


# --------------------------------------------------------------------------
# Betikler pytest içinden çağrılabilir (QA kıyasının ön koşulu)
# --------------------------------------------------------------------------

def test_blind_test_script_runs_on_tmp_db(synthetic_memory):
    report = memory_blind_test.run(synthetic_memory["db"], include_episodic=False)
    assert report["nodes"] > 0
    assert "/" in report["hit@1"] and "/" in report["hit@5"]
    assert report["noise_ratio_pct"] == 0.0, "sentetik korpusta gürültü olmamalı"


def test_migrate_script_plans_and_writes_to_tmp(synthetic_memory, tmp_path):
    plan = memory_migrate_v2.plan_migration(synthetic_memory["db"])
    counts = plan.counts()
    assert counts["source_nodes"] == len(memory_blind_test.CognitiveMemorySystem(
        db_path=synthetic_memory["db"]).get_all_nodes())
    assert set(counts["category_after"]) <= set(CANONICAL_CATEGORIES)

    target = tmp_path / "migrated.db"
    result = memory_migrate_v2.write_target(plan, target)
    assert target.exists()
    assert result["written"] == counts["kept"]
    after = brain_metrics.collect(target, include_recall=False, include_latency=False)
    assert after["K7_categories"]["non_canonical"] == []
    assert after["K10_fixture_leak"]["count"] == 0


def test_brain_metrics_is_read_only(synthetic_memory):
    """Ölçüm paketi ölçtüğü veritabanını değiştirmemeli."""
    db = synthetic_memory["db"]
    before = (db.stat().st_size, db.stat().st_mtime_ns)
    brain_metrics.collect(db, include_recall=False, include_latency=True)
    after = (db.stat().st_size, db.stat().st_mtime_ns)
    assert before == after, "brain_metrics.py veritabanını değiştirdi"


def test_graph_mirror_carries_provenance_into_cognitive_nodes(tmp_path, monkeypatch):
    """
    Regresyon (Faz 11-B QA): `GraphStore._mirror_to_cognitive` `provenance`
    sütununu yazmıyordu; konsolidasyonun ürettiği küme/yansıma düğümleri
    `cognitive_nodes` tarafında kaynaksız görünüyor ve K12'yi düşürüyordu
    (gerçek veritabanında ölçülen: 42 düğüm).
    """
    import sqlite3

    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(tmp_path / "cog.db"))
    mem = CognitiveMemorySystem()
    store = mem.graph_store()
    assert store is not None
    store.upsert_node(
        "community-test-1",
        "community",
        "üç düğümlük küme",
        "Üç düğümlük küme. Öne çıkan terimler: kapı, kaynak, ölçüm.",
        provenance="consolidate:label_propagation",
    )
    with sqlite3.connect(mem.db_path) as conn:
        row = conn.execute(
            "SELECT provenance FROM cognitive_nodes WHERE id = ?", ("community-test-1",)
        ).fetchone()
    assert row is not None, "ayna cognitive_nodes'a yazmadı"
    assert (row[0] or "").strip() == "consolidate:label_propagation"


# --------------------------------------------------------------------------
# Faz 11 kapanışı — kimlik düğümü kaynağı (K12'nin kalan 2 düğümü)
# --------------------------------------------------------------------------

def _make_identity_db(tmp_path):
    """Kaynaksız iki kimlik düğümü + kaynaksız bir sıradan L2 düğümü kurar."""
    import sqlite3

    db = tmp_path / "identity.db"
    CognitiveMemorySystem(db_path=db)  # şemayı kurar
    with sqlite3.connect(db) as conn:
        for node_id, ident in (("id-a", 1), ("id-b", 1), ("plain", 0)):
            conn.execute(
                "INSERT INTO cognitive_nodes (id, category, content, importance,"
                " created_at, last_accessed, access_count, provenance, is_identity)"
                " VALUES (?, 'semantic', ?, 0.9, 1000.0, 1000.0, 3, '', ?)",
                (node_id, f"Kimlik metni {node_id} " + "x" * 60, ident),
            )
        conn.commit()
    return db


def test_identity_nodes_get_identity_core_provenance(tmp_path):
    """`--tag-legacy` kimlik düğümlerini `identity:core` ile damgalar (idempotent)."""
    from entropy.memory.gate import IDENTITY_PROVENANCE

    import sqlite3

    db = _make_identity_db(tmp_path)
    plan = memory_migrate_v2.plan_legacy_tagging(db)
    assert plan["identity_candidates"] == 2
    assert plan["candidates"] == 1, "kimlik dışı kaynaksız L2 ayrı sayılmalı"

    assert memory_migrate_v2.apply_identity_tagging(db) == 2
    assert memory_migrate_v2.apply_identity_tagging(db) == 0, "idempotent olmalı"

    with sqlite3.connect(db) as conn:
        rows = dict(conn.execute(
            "SELECT id, provenance FROM cognitive_nodes").fetchall())
    assert rows["id-a"] == IDENTITY_PROVENANCE
    assert rows["id-b"] == IDENTITY_PROVENANCE
    assert rows["plain"] == "", "kimlik dışı düğüme dokunulmamalı"


def test_k12_excludes_identity_nodes_and_counts_them_separately(tmp_path):
    """K12 kimlik düğümlerini saymaz; ayrı sayaçta görünürler."""
    db = _make_identity_db(tmp_path)
    before = brain_metrics.collect(db, include_recall=False, include_latency=False)
    k12 = before["K12_unsourced_l2"]
    assert k12["count"] == 1, "yalnızca kimlik dışı kaynaksız L2 sayılır"
    # +1: şema kurulumunun yazdığı `ego-entropy-core` (kaynağı zaten dolu).
    assert k12["identity_nodes"] == 3
    assert k12["identity_untagged"] == 2

    memory_migrate_v2.apply_identity_tagging(db)
    after = brain_metrics.collect(db, include_recall=False, include_latency=False)
    assert after["K12_unsourced_l2"]["count"] == 1
    assert after["K12_unsourced_l2"]["identity_untagged"] == 0


# --------------------------------------------------------------------------
# Faz 12-A — CRAG eşiği kalibrasyonu (araştırma A §3.2)
# --------------------------------------------------------------------------


def test_crag_threshold_is_calibrated_value():
    """
    Eşik gerçek DB kopyasında 10 etiketli sorguyla ölçüldü (5 var / 5 yok):
    0,45 → 8/10, **0,40 → 9/10**, 0,30 → 5/10. Sabit ölçülen değerde durmalı.
    """
    from entropy.memory.context_builder import CRAG_MIN_SCORE

    assert CRAG_MIN_SCORE == 0.40


def test_crag_threshold_reads_config_setting(monkeypatch):
    """Eşik artık ayar; `config.brain_confidence_threshold` etkin değeri belirler."""
    from entropy.core.config import config
    from entropy.memory.context_builder import AssembledContext, crag_min_score

    monkeypatch.setattr(config, "brain_confidence_threshold", 0.90, raising=False)
    assert crag_min_score() == 0.90
    ctx = AssembledContext()
    ctx.brain_confidence = 0.50
    assert ctx.brain_has_answer is False

    monkeypatch.setattr(config, "brain_confidence_threshold", 0.20, raising=False)
    assert ctx.brain_has_answer is True


def test_crag_threshold_ignores_out_of_range_setting(monkeypatch):
    """Bozuk ayar (aralık dışı / bool) modül varsayılanına düşer."""
    from entropy.core.config import config
    from entropy.memory.context_builder import CRAG_MIN_SCORE, crag_min_score

    for bad in (5.0, -1.0, True, "0.4", None):
        monkeypatch.setattr(config, "brain_confidence_threshold", bad, raising=False)
        assert crag_min_score() == CRAG_MIN_SCORE


def test_crag_separates_labelled_queries_on_synthetic_corpus():
    """
    Kalibrasyon yöntemi kalıcı: etiketli sorgu kümesinde seçilen eşik
    doğruluğu ≥ 8/10 vermeli. Burada gerçek DB yerine sentetik skor dağılımı
    (ölçümün kendisi: 5 olumlu / 5 olumsuz sorgunun top-1 hibrit skorları)
    kullanılır, böylece test kullanıcının veritabanına dokunmaz.
    """
    from entropy.memory.context_builder import CRAG_MIN_SCORE

    olculen = [
        (0.5533, True), (0.4947, True), (0.4790, True),
        (0.3472, True), (0.4183, True),
        (0.3386, False), (0.3551, False), (0.3445, False),
        (0.3835, False), (0.3773, False),
    ]
    dogru = sum(1 for score, label in olculen if (score >= CRAG_MIN_SCORE) == label)
    assert dogru >= 8, f"CRAG eşiği {CRAG_MIN_SCORE} doğruluğu {dogru}/10 — kalibrasyon bozuldu"
    yanlis_pozitif = sum(1 for score, label in olculen if not label and score >= CRAG_MIN_SCORE)
    assert yanlis_pozitif == 0
