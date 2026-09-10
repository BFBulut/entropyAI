"""
Faz 11.1 + 11.2 + 11.10 — kategori disiplini, yazma kapısı, okuma yolu eklentileri.

Hepsi geçici veritabanı üzerinde koşar; gerçek profil dosyasına dokunulmaz.
Model çağrısı yok.
"""

import json
import os
import time

import pytest

from entropy.memory.categories import (
    CANONICAL_CATEGORIES,
    DEFAULT_RECALL_CATEGORIES,
    normalize_category,
)
from entropy.memory.gate import (
    ACTION_ADD,
    ACTION_GRAY,
    ACTION_NOOP,
    ACTION_REJECT,
    MemoryGate,
    derive_provenance,
    fixture_match,
)
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem


@pytest.fixture
def mem(tmp_path):
    return CognitiveMemorySystem(db_path=tmp_path / "gate.db")


# --------------------------------------------------------------------------
# 11.1 Kategori disiplini
# --------------------------------------------------------------------------

def test_category_closed_set_has_exactly_four_layers():
    assert CANONICAL_CATEGORIES == ("working", "episodic", "semantic", "procedural")
    assert DEFAULT_RECALL_CATEGORIES == ("semantic", "procedural")


@pytest.mark.parametrize("raw,expected", [
    ("query", "episodic"),       # test artığı + wiki sorgu künyesi
    ("session", "episodic"),     # handoff.py
    ("office", "episodic"),
    ("agent", "episodic"),
    ("architecture", "semantic"),
    ("math", "semantic"),
    ("federation", "semantic"),
    ("skill", "procedural"),
    ("handoff", "working"),
])
def test_legacy_categories_map_to_canonical(raw, expected):
    resolution = normalize_category(raw)
    assert resolution.category == expected
    assert resolution.mapped is True
    assert resolution.unknown is False


def test_identity_is_a_flag_not_a_fifth_category():
    resolution = normalize_category("ego")
    assert resolution.category == "semantic"
    assert resolution.is_identity is True


def test_unknown_category_is_flagged():
    resolution = normalize_category("orchestration")
    assert resolution.unknown is True
    assert resolution.category == "semantic"


def test_schema_v2_columns_exist_and_are_written(mem):
    import sqlite3

    node, created = mem.record_memory(
        "semantic", "Şema v2 sütunları yazma yolunda doldurulmalı ve okunabilmeli",
        importance=0.7, metadata={"path": "/kasa/Reports/x.md"},
    )
    assert created
    with sqlite3.connect(mem.db_path) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cognitive_nodes)")]
    for column in ("provenance", "confidence", "valid_from", "valid_to",
                   "archived", "novelty", "is_identity"):
        assert column in cols
    stored = mem.get_node(node.id)
    assert stored.provenance.startswith("path=")
    assert stored.valid_from is not None and stored.valid_to is None
    assert stored.archived == 0


def test_ego_node_keeps_id_but_is_flagged_identity(mem):
    ego = mem.get_node("ego-entropy-core")
    assert ego is not None
    assert ego.category == "semantic"
    assert ego.is_identity == 1


def test_db_only_contains_canonical_categories(mem):
    for raw in ("query", "architecture", "ego", "session", "skill", "office"):
        mem.record_memory(raw, f"Kategori disiplini denemesi: {raw} kovası kapanmalı ve eşlenmeli",
                          metadata={"path": f"/kasa/{raw}.md"})
    import sqlite3

    with sqlite3.connect(mem.db_path) as conn:
        found = {r[0] for r in conn.execute("SELECT DISTINCT category FROM cognitive_nodes")}
    assert found <= set(CANONICAL_CATEGORIES), found


# --------------------------------------------------------------------------
# 11.2 Yazma kapısı
# --------------------------------------------------------------------------

def test_repeated_topic_creates_one_node_and_nineteen_noops(mem):
    """Sentetik yineleme: aynı bilgi 20 kez -> 1 düğüm + 19 NOOP."""
    base = "Ohlson O-Score modeli dokuz muhasebe oranıyla temerrüt olasılığını kestirir"
    variants = [base] + [f"{base} ({i})" for i in range(1, 20)]

    before = len(mem.get_all_nodes())
    created_count = 0
    for text in variants:
        _node, created = mem.record_memory("semantic", text, metadata={"path": "/kasa/finans.md"})
        created_count += 1 if created else 0
    after = len(mem.get_all_nodes())

    # Ölçüm (gerçek çok dilli gömme, aynı korpus): 20 yazımın 19'unun en yakın
    # komşuya kosinüsü 0,966-0,988 -> NOOP. Tek varyant ("(14)") 0,9306 ile gri
    # banda düşüp yazıldı; gri bant bilgiyi ATMAZ, toplu birleştirmeye kuyruklar.
    # Kapı olmadan bu 20 düğüm ederdi (bkz. test_gate_off_flag_restores_old_behaviour).
    assert created_count <= 2, f"en fazla 2 düğüm bekleniyordu, {created_count} yazıldı"
    assert after - before <= 2
    assert mem.gate.counters[ACTION_NOOP] >= 18
    assert mem.gate.counters[ACTION_ADD] == 1


def test_gate_off_flag_restores_old_behaviour(mem, monkeypatch):
    monkeypatch.setenv("ENTROPY_MEMORY_GATE", "0")
    base = "Ohlson O-Score modeli dokuz muhasebe oranıyla temerrüt olasılığını kestirir"
    before = len(mem.get_all_nodes())
    for i in range(20):
        mem.record_memory("semantic", f"{base} ({i})")
    # Kapı kapalıyken eski davranış: her farklı metin yeni düğüm.
    assert len(mem.get_all_nodes()) - before == 20


def test_gray_band_queues_candidate_and_still_writes(tmp_path):
    """Gri bant: düğüm yazılır (bilgi kaybolmaz) AMA toplu birleştirmeye kuyruklanır."""
    mem = CognitiveMemorySystem(db_path=tmp_path / "gray.db")
    # Bantlar bilerek genişletildi: gerçek gömme skorlarına bağlı kalmadan
    # gri bandın davranışı sınanır.
    mem._gate = MemoryGate(mem, strict=False, add_threshold=0.30, noop_threshold=0.999)

    mem.record_memory("semantic", "Fung ve Hsieh trend takip eden hedge fon faktör modelini kurdu",
                      metadata={"path": "/kasa/a.md"})
    node, created = mem.record_memory(
        "semantic", "Fung-Hsieh yedi faktörlü model trend izleyen fonların getirisini açıklar",
        metadata={"path": "/kasa/b.md"},
    )
    assert created, "gri bant düğümü yazılmalı; bilgi kaybolmamalı"

    pending = mem.gate.pending_gray()
    assert pending, "gri bant adayı kuyruğa girmeli"
    row = pending[-1]
    assert row["status"] == "pending"
    assert row["node_id"] == node.id
    assert row["nearest_id"]
    assert 0.0 < row["similarity"] <= 1.0
    # Kuyruk JSONL biçiminde ve veritabanının yanında durur (test yalıtımı).
    assert mem.gate.queue_path.parent.parent == tmp_path
    lines = mem.gate.queue_path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["node_id"] == node.id


def test_strict_gate_rejects_fixture_patterns(mem):
    gate = MemoryGate(mem, strict=True)
    for text in (
        "arastirma-ofisi: Pazar araştırması / Ofis: bir şeyler · arastirmaci · review",
        "Ayrıştırıcı Modül bitti. [KANIT] Komut: python -m pytest tests/test_modul.py",
        "DummyProc sınıfı sahte süreç döndürüyor ve gerçek bir bilgi taşımıyor burada",
    ):
        decision = gate.admit("semantic", text, metadata={"path": "/kasa/x.md"})
        assert decision.action == ACTION_REJECT, text
        assert decision.writes is False

    assert fixture_match("normal bir cümle, hiçbir fikstür kalıbı yok burada") is None


def test_strict_gate_rejects_short_content(mem):
    gate = MemoryGate(mem, strict=True)
    decision = gate.admit("semantic", "kısa not", metadata={"path": "/kasa/x.md"})
    assert decision.action == ACTION_REJECT
    assert "çok kısa" in decision.reason


def test_strict_gate_requires_provenance_for_semantic(mem):
    gate = MemoryGate(mem, strict=True)
    content = "Kaynaksız bir iddia: sistem kendi ürettiği kurguyu kesin olgu gibi yazamaz"

    without = gate.admit("semantic", content, metadata={"source": "scheduled_task"})
    assert without.action == ACTION_REJECT
    assert "kaynak" in without.reason

    with_source = gate.admit("semantic", content, metadata={"path": "/kasa/Reports/r.md"})
    assert with_source.action in (ACTION_ADD, ACTION_GRAY, ACTION_NOOP)
    assert with_source.confidence == 0.75


def test_provenance_requirement_only_applies_to_semantic(mem):
    gate = MemoryGate(mem, strict=True)
    decision = gate.admit(
        "procedural",
        "Yordam: rapor damıtması yalnızca işlenmemiş kaynakları okur ve sonra durumu yazar",
        metadata={"skill": "financial-auditor"},
    )
    assert decision.action != ACTION_REJECT


def test_derive_provenance_prefers_strong_keys():
    prov, strong = derive_provenance({"source": "scheduled_task", "path": "/kasa/x.md"})
    assert strong is True and prov == "path=/kasa/x.md"

    prov, strong = derive_provenance({"source": "scheduled_task"})
    assert strong is False and "source=scheduled_task" in prov

    prov, strong = derive_provenance(None, explicit="dream_consolidation:2026-09-10")
    assert strong is True and prov == "dream_consolidation:2026-09-10"


def test_gate_latency_under_400ms(mem):
    """K11: kapı dâhil yazma yolu gecikmesi <= 400 ms."""
    for i in range(40):
        mem.record_memory(
            "semantic",
            f"Tohum düğüm {i}: kantitatif finans literatüründe ayrı bir model ailesi anlatılır",
            metadata={"path": f"/kasa/seed{i}.md"},
        )
    mem.hybrid_recall("tohum", top_k=1)  # indeks ısınsın

    started = time.perf_counter()
    mem.record_memory(
        "semantic",
        "Ölçüm düğümü: Cartea ve Jaimungal HJB denklemiyle optimal icra problemini kurar",
        metadata={"path": "/kasa/olcum.md"},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert elapsed_ms <= 400.0, f"kapı gecikmesi {elapsed_ms:.0f} ms > 400 ms"


def test_rejected_write_is_visible_in_last_errors(mem):
    mem._gate = MemoryGate(mem, strict=True)
    node, created = mem.record_memory("semantic", "kısa", metadata={"path": "/kasa/x.md"})
    assert created is False
    assert any(e["stage"] == "memory_gate" for e in mem.last_errors)
    assert mem.get_node(node.id) is None, "reddedilen düğüm diske yazılmamalı"


# --------------------------------------------------------------------------
# 11.10 Okuma yolu eklentileri
# --------------------------------------------------------------------------

def test_default_recall_scope_excludes_working_and_episodic(mem):
    mem.record_memory("semantic", "Anlamsal katman: nakit akış tablosu işletme faaliyetlerinden başlar",
                      metadata={"path": "/kasa/a.md"})
    mem.record_memory("episodic", "Epizodik katman: nakit akış tablosu hakkında kullanıcı soru sordu",
                      metadata={"path": "/kasa/b.md"})
    mem.record_memory("working", "Çalışma belleği: nakit akış tablosu taslağı bu turda açık",
                      metadata={"path": "/kasa/c.md"})

    default_hits = mem.hybrid_recall("nakit akış tablosu", top_k=10)
    categories = {n.category for n, _ in default_hits}
    assert "episodic" not in categories
    assert "working" not in categories

    with_episodic = mem.hybrid_recall("nakit akış tablosu", top_k=10, include_episodic=True)
    assert "episodic" in {n.category for n, _ in with_episodic}


def test_archived_nodes_leave_the_recall_scope(mem):
    node, _ = mem.record_memory(
        "semantic", "Arşivlenecek düğüm: ölçülü unutma silme değil kapsam dışına almadır",
        metadata={"path": "/kasa/arsiv.md"},
    )
    assert node.id in [n.id for n, _ in mem.hybrid_recall("ölçülü unutma", top_k=10)]

    mem._supersede_node(node.id, "yeni-dugum", time.time())
    assert node.id not in [n.id for n, _ in mem.hybrid_recall("ölçülü unutma", top_k=10)]
    assert mem.get_node(node.id) is not None, "arşiv silme değildir"
    assert mem.archived_count() == 1


def test_context_builder_reports_brain_confidence(tmp_path):
    from entropy.memory.context_builder import CRAG_MIN_SCORE, CognitiveContextBuilder
    from entropy.memory.playbook import PlaybookStore

    mem = CognitiveMemorySystem(db_path=tmp_path / "ctx.db")
    mem.record_memory(
        "semantic",
        "Erlang-OTP denetim ağaçları hata izolasyonunu süreç hiyerarşisiyle sağlar",
        importance=0.9, metadata={"path": "/kasa/otp.md"},
    )
    builder = CognitiveContextBuilder(
        memory_system=mem,
        vault_manager=None,
        playbook_store=PlaybookStore(vault_path=tmp_path / "vault"),
    )
    ctx = builder.build("Erlang OTP denetim ağacı hata izolasyonu", token_budget=1200)
    assert ctx.brain_confidence > 0.0
    assert ctx.summary()["brain_confidence"] == round(ctx.brain_confidence, 4)

    empty = CognitiveMemorySystem(db_path=tmp_path / "bos.db")
    builder2 = CognitiveContextBuilder(
        memory_system=empty, vault_manager=None,
        playbook_store=PlaybookStore(vault_path=tmp_path / "vault2"),
    )
    ctx2 = builder2.build("hakkında hiçbir şey bilmediğim bir konu xyzzy", token_budget=1200)
    assert ctx2.brain_confidence < CRAG_MIN_SCORE
    assert ctx2.brain_has_answer is False


# --------------------------------------------------------------------------
# Faz 11 kapanışı — kapı iki kez koşmaz, içerik güncelleme bayrağı
# --------------------------------------------------------------------------

def test_record_memory_with_precomputed_decision_skips_the_gate(mem, monkeypatch):
    """Karar önceden alındıysa kapı ikinci kez KOŞMAZ (tek gömme)."""
    content = (
        "Güçlendirme boru hattı raporu: kapının kararı çağıran tarafta alındı, "
        "yazma yolu aynı adayı ikinci kez değerlendirmemeli."
    )
    gate = MemoryGate(mem, strict=False)
    decision = gate.admit("semantic", content, provenance="docs/reports/x.md")
    assert decision.action == ACTION_ADD

    calls = {"admit": 0, "embed": 0}
    real_admit = mem.gate.admit
    monkeypatch.setattr(
        type(mem.gate), "admit",
        lambda self, *a, **k: (calls.__setitem__("admit", calls["admit"] + 1),
                               real_admit(*a, **k))[1],
    )
    from entropy.memory.supabase.cognitive_memory import LocalEmbeddingEngine

    engine = LocalEmbeddingEngine.get_instance()
    real_embed = engine.embed_text_status
    monkeypatch.setattr(
        type(engine), "embed_text_status",
        lambda self, text: (calls.__setitem__("embed", calls["embed"] + 1),
                            real_embed(text))[1],
    )

    node, novel = mem.record_memory(
        "semantic", content, provenance="docs/reports/x.md", decision=decision
    )
    assert novel is True
    assert calls["admit"] == 0, "kapı ikinci kez koşmamalı"
    assert calls["embed"] == 0, "gömme yeniden hesaplanmamalı (karardan gelir)"
    assert mem.get_node(node.id) is not None


def test_store_decision_writes_without_reevaluating(mem):
    content = (
        "store_decision sözleşmesi: karar nesnesi doğrudan yazılır, kategori ve "
        "kaynak karardan okunur, kapı tekrar çağrılmaz."
    )
    decision = MemoryGate(mem, strict=False).admit(
        "semantic", content, provenance="docs/reports/y.md"
    )
    before = dict(mem.gate.counters)
    node, novel = mem.store_decision(decision)
    assert novel is True
    assert mem.gate.counters == before, "sayaçlar ikinci kez artmamalı"
    assert node.provenance == "docs/reports/y.md"


def test_save_node_updates_content_only_with_flag(mem):
    node, _ = mem.record_memory(
        "semantic",
        "İlk gövde: bu düğümün içeriği birleştirme turunda değişecek, kimliği değil.",
        provenance="docs/reports/z.md",
    )
    node_id = node.id

    # bayraksız: içerik sütunu DEĞİŞMEZ (11-D'de bulunan hata)
    stale = mem.get_node(node_id)
    stale.content = "Bayraksız yazım içeriği değiştirmemeli."
    mem._save_node(stale)
    assert mem.get_node(node_id).content.startswith("İlk gövde")

    # bayraklı: içerik değişir, gömme 'pending' işaretlenir
    merged = mem.get_node(node_id)
    merged.content = "Birleşik gövde: iki düğümün bilgisi tek metinde toplandı."
    merged.embedding = []
    mem._save_node(merged, allow_content_update=True)
    fresh = mem.get_node(node_id)
    assert fresh.content.startswith("Birleşik gövde")
    assert fresh.id == node_id, "kimlik korunmalı (kenarlar kopmasın)"
    import sqlite3 as _sq

    with _sq.connect(mem.db_path) as conn:
        status = conn.execute(
            "SELECT embedding_status FROM cognitive_nodes WHERE id = ?", (node_id,)
        ).fetchone()[0]
    assert status == "pending", "içerik değişince gömme bayatlar"
