"""
Faz 11-D — gri bant birleştirme (11.3), rüya döngüsü v2 (11.7),
wiki derleme hattı (11.8), genel sohbet beyin paketi (11.9).

Hepsi tmp kasa + tmp veritabanı üzerinde koşar. **Gerçek model çağrısı yok:**
köprü gerektiren her adım `send_prompt(prompt) -> str` sahtesiyle sınanır
(`distiller.run_with_bridge` sözleşmesinin aynısı).
"""

import json
import time
from pathlib import Path

import pytest

from entropy.memory import dream, gray_merge, wiki
from entropy.memory.context_builder import (
    BUDGET_GENERAL_BRAIN,
    CognitiveContextBuilder,
)
from entropy.memory.playbook import PlaybookStore, SkillPlaybook
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem


@pytest.fixture
def mem(tmp_path):
    return CognitiveMemorySystem(db_path=tmp_path / "brain.db")


def _seed_node(mem, content, category="semantic", importance=0.5, embedding=None):
    """Kapıdan geçirerek düğüm yazar; gerekirse gömmeyi deterministik yapar."""
    node, _ = mem.record_memory(
        category=category, content=content, importance=importance,
        metadata={"path": "tests/fixture.md"}, provenance="tests/fixture.md",
    )
    if embedding is not None:
        node.embedding = list(embedding)
        mem._save_node(node)
    return node


def _reset_queue(mem):
    """Kapının fikstür yazımları sırasında kuyruğa attığı adayları temizler."""
    path = mem.gate.queue_path
    if path.exists():
        path.unlink()


def _queue_pair(mem, candidate, neighbour, similarity=0.87):
    """Gri bant kuyruğuna elle bir satır ekler (kapının yazdığı biçimin aynısı)."""
    path = mem.gate.queue_path
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(), "status": "pending", "node_id": candidate.id,
        "category": candidate.category, "content": candidate.content,
        "similarity": similarity, "nearest_id": neighbour.id,
        "nearest_content": neighbour.content, "provenance": "tests/fixture.md",
        "reason": "gri bant (test)",
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ==========================================================================
# 11.3 — gri bant kuyruğu birleştirme turu
# ==========================================================================


def _five_candidates(mem):
    pairs = []
    nodes = []
    for i in range(5):
        neighbour = _seed_node(mem, f"Komşu bilgi {i}: ölçüm sonucu {i} olarak kaydedildi ve doğrulandı.")
        candidate = _seed_node(mem, f"Aday bilgi {i}: ölçüm sonucu {i} olarak raporlandı, doğrulama yapıldı.")
        nodes.append((candidate, neighbour))
    _reset_queue(mem)
    for candidate, neighbour in nodes:
        _queue_pair(mem, candidate, neighbour)
        pairs.append((candidate, neighbour))
    return pairs


def test_gray_round_five_candidates_three_merge_two_keep(mem):
    pairs = _five_candidates(mem)
    assert len(mem.gate.pending_gray()) == 5

    def fake_bridge(prompt):
        # Tek istem: beş çift de aynı promptta olmalı.
        for cand, _ in pairs:
            assert cand.id in prompt
        decisions = []
        for i, (cand, _) in enumerate(pairs):
            action = "merge" if i < 3 else "keep_both"
            decisions.append({
                "id": cand.id, "action": action,
                "content": f"Birleşik metin {i}" if action == "merge" else "",
                "reason": "test",
            })
        return "```json\n" + json.dumps({"decisions": decisions}) + "\n```"

    res = gray_merge.run_merge_round(mem, send_prompt=fake_bridge)

    assert res.turns == 1, "N aday TEK istemde sorulmalı"
    assert res.candidates == 5
    assert res.merged == 3
    assert res.kept == 2
    assert res.superseded == 0
    assert res.errors == []
    # Kuyruk temizlendi (satırlar silinmedi, `done` oldu).
    assert mem.gate.pending_gray() == []
    assert gray_merge.gray_stats(mem)["done"] == 5
    # Birleşenlerin adayları arşivlendi, komşular güncellendi.
    for i, (cand, neighbour) in enumerate(pairs):
        cand_node = mem.get_node(cand.id)
        neigh_node = mem.get_node(neighbour.id)
        if i < 3:
            assert int(cand_node.archived) == 1
            assert neigh_node.content == f"Birleşik metin {i}"
        else:
            assert int(cand_node.archived) == 0
            assert int(neigh_node.archived) == 0


def test_gray_round_supersede_archives_neighbour(mem):
    neighbour = _seed_node(mem, "Kota tavanı günde 100 tur olarak ölçüldü ve raporlandı.")
    candidate = _seed_node(mem, "Kota tavanı günde 250 tur olarak ölçüldü, yeni ölçüm geçerli.")
    _reset_queue(mem)
    _queue_pair(mem, candidate, neighbour)

    res = gray_merge.run_merge_round(
        mem, send_prompt=lambda p: json.dumps(
            {"decisions": [{"id": candidate.id, "action": "supersede", "reason": "yeni değer"}]}),
    )
    assert res.superseded == 1
    assert int(mem.get_node(neighbour.id).archived) == 1
    assert int(mem.get_node(candidate.id).archived) == 0


def test_gray_round_without_bridge_is_dry_run(mem):
    _five_candidates(mem)
    res = gray_merge.run_merge_round(mem, send_prompt=None)
    assert res.turns == 0 and res.candidates == 5
    assert len(mem.gate.pending_gray()) == 5, "kuru koşum kuyruğu boşaltmamalı"


def test_gray_round_unparsable_response_keeps_queue(mem):
    _five_candidates(mem)
    res = gray_merge.run_merge_round(mem, send_prompt=lambda p: "olmadı, JSON yok")
    assert res.turns == 1 and res.merged == 0
    assert len(mem.gate.pending_gray()) == 5
    assert res.errors


def test_gray_round_is_cancellable(mem):
    _five_candidates(mem)

    def fake_bridge(prompt):
        gray_merge.cancel_merge()
        return json.dumps({"decisions": []})

    res = gray_merge.run_merge_round(mem, send_prompt=fake_bridge)
    assert len(mem.gate.pending_gray()) == 5
    gray_merge.reset_cancel()
    assert res.merged == 0


def test_gray_round_is_idempotent(mem):
    pairs = _five_candidates(mem)
    bridge = lambda p: json.dumps({"decisions": [
        {"id": c.id, "action": "keep_both"} for c, _ in pairs]})
    first = gray_merge.run_merge_round(mem, send_prompt=bridge)
    second = gray_merge.run_merge_round(mem, send_prompt=bridge)
    assert first.candidates == 5 and second.candidates == 0
    assert second.turns == 0


def test_k9_gray_write_ratio_is_measurable(mem):
    _five_candidates(mem)
    stats = gray_merge.gray_stats(mem)
    assert stats["total_gray"] == 5
    # 10 fikstür düğümü + `ego-entropy-core` tohumu.
    assert stats["nodes"] == 11
    # K9 = gri bant satırı / düğüm; hedef ≤ %2 (bu fikstürde kasıtlı olarak yüksek).
    assert stats["ratio"] == pytest.approx(5 / 11)


def test_parse_merge_response_tolerates_noise():
    text = "Tamam, kararlar:\n{\"decisions\": [{\"id\": \"a\", \"action\": \"MERGE\"}]}\nUmarım yardımcı olur."
    parsed = gray_merge.parse_merge_response(text)
    assert parsed == {"a": {"action": "merge", "content": "", "reason": ""}}
    assert gray_merge.parse_merge_response("") == {}
    assert gray_merge.parse_merge_response('{"decisions": [{"id": "a", "action": "sil"}]}') == {}


# ==========================================================================
# 11.7 — rüya döngüsü v2
# ==========================================================================


def test_cluster_and_merge_duplicates_without_llm(mem):
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    keep = _seed_node(mem, "Aynı konu birinci sürüm: rapor biçimi tablo olmalı.", importance=0.9, embedding=vec_a)
    dup1 = _seed_node(mem, "Aynı konu ikinci sürüm: rapor biçimi tablo olmalıdır.", importance=0.4, embedding=vec_a)
    dup2 = _seed_node(mem, "Aynı konu üçüncü sürüm: raporun biçimi tablodur.", importance=0.3, embedding=vec_a)
    other = _seed_node(mem, "Bambaşka bir konu: kota ölçümü ledger özetinden okunur.", importance=0.8, embedding=vec_b)

    clusters, merged = dream.merge_duplicates(mem)
    assert clusters == 1 and merged == 2
    assert int(mem.get_node(keep.id).archived) == 0
    assert int(mem.get_node(dup1.id).archived) == 1
    assert int(mem.get_node(dup2.id).archived) == 1
    assert int(mem.get_node(other.id).archived) == 0


def test_forget_stale_archives_never_recalled_old_low_value_nodes(mem):
    old = _seed_node(mem, "Bir kez yazılmış, hiç geri çağrılmamış, önemsiz eski not.", importance=0.2)
    fresh = _seed_node(mem, "Yeni ve önemli bir bulgu: kapı gecikmesi medyan 234 ms.", importance=0.9)
    identity = _seed_node(mem, "Entropy'nin kimliği: kullanıcının onayladığı kalıcı kural.", importance=0.2)
    import sqlite3

    long_ago = time.time() - 60 * 86400.0
    with sqlite3.connect(mem.db_path) as conn:
        conn.execute("UPDATE cognitive_nodes SET last_accessed = ?, access_count = 1", (long_ago,))
        conn.execute("UPDATE cognitive_nodes SET is_identity = 1 WHERE id = ?", (identity.id,))
        conn.commit()
    mem._invalidate_recall_index()

    assert dream.forget_stale(mem) == 1
    assert int(mem.get_node(old.id).archived) == 1
    assert int(mem.get_node(fresh.id).archived) == 0, "önemli düğüm unutulmaz"
    assert int(mem.get_node(identity.id).archived) == 0, "kimlik/kural muaf"


def test_wiki_promotion_needs_three_nodes_on_one_topic(mem):
    vec = [0.0, 0.0, 1.0]
    for i in range(3):
        _seed_node(mem, f"Aynı konu {i}: finansal denetimde nakit akışı tablosu zorunludur.",
                   importance=0.5 + i / 100.0, embedding=vec)
    _seed_node(mem, "Tek başına duran bir konu: PySide6 offscreen sürücüsü.",
               importance=0.5, embedding=[0.0, 1.0, 0.0])

    cands = dream.wiki_promotion_candidates(mem)
    assert len(cands) == 1
    assert cands[0]["members"] == 3


def test_dream_cycle_reports_every_step_and_has_no_episodic_precondition(mem, tmp_path):
    """Epizodik düğüm YOK: eski koşul kalksaydı döngü hiç iş yapmazdı."""
    vec = [1.0, 0.0, 0.0]
    _seed_node(mem, "Konsolide edilecek birinci kayıt: kota ölçümü ledger'dan okunur.",
               importance=0.9, embedding=vec)
    _seed_node(mem, "Konsolide edilecek ikinci kayıt: kota ölçümü ledger özetinden okunur.",
               importance=0.4, embedding=vec)
    cand = _seed_node(mem, "Gri aday: rapor biçimi tablo olmalı, başlık zorunlu.")
    near = _seed_node(mem, "Gri komşu: rapor biçimi tablodur, başlık gerekir.")
    _reset_queue(mem)
    _queue_pair(mem, cand, near)

    report = dream.dream_and_consolidate(
        mem,
        send_prompt=lambda p: json.dumps({"decisions": [
            {"id": cand.id, "action": "keep_both", "reason": "farklı"}]}),
        vault_path=tmp_path,
    )

    assert report.gray_candidates == 1
    assert report.gray_turns == 1
    assert report.gray_kept == 1
    assert report.duplicate_clusters >= 1
    assert report.duplicates_merged >= 1
    assert report.nodes_before == 5  # 4 fikstür + ego tohumu
    assert report.nodes_active_after < report.nodes_before
    assert report.duration_s >= 0.0
    assert isinstance(report.errors, list)
    # Kasaya tek satırlık günlük düştü.
    log = dream.dream_log_path(tmp_path)
    assert log.is_file()
    assert "yeniden gömme" in log.read_text(encoding="utf-8")
    assert report.as_dict()["gray"]["kept"] == 1


def test_dream_cycle_without_bridge_calls_no_model(mem, tmp_path):
    cand = _seed_node(mem, "Gri aday: kapı gecikmesi 234 ms ölçüldü, kabul edilebilir.")
    near = _seed_node(mem, "Gri komşu: kapı gecikmesi 240 ms ölçüldü, sınırda.")
    _reset_queue(mem)
    _queue_pair(mem, cand, near)

    report = dream.dream_and_consolidate(mem, send_prompt=None, vault_path=tmp_path)
    assert report.gray_turns == 0
    assert report.gray_candidates == 1
    assert len(mem.gate.pending_gray()) == 1, "köprüsüz turda kuyruk korunur"
    assert report.errors == [] or all(e["step"] != "gray_merge" for e in report.errors)


def test_daily_dreaming_task_registration_is_idempotent():
    class FakeScheduler:
        def __init__(self):
            self.tasks = {}
            self.calls = 0

        def schedule_task(self, task_id, name, prompt, interval_type, interval_value, **kw):
            self.calls += 1
            self.tasks[task_id] = {"id": task_id, "name": name, "interval": interval_type}
            return self.tasks[task_id]

    sched = FakeScheduler()
    dream.ensure_daily_dreaming_task(sched)
    dream.ensure_daily_dreaming_task(sched)
    assert sched.calls == 1
    assert dream.DAILY_DREAM_TASK_ID in sched.tasks


# ==========================================================================
# 11.8 — wiki derleme hattı
# ==========================================================================


@pytest.fixture
def skill_vault(tmp_path):
    """Tmp kasada bir yetenek: playbook + 5 rapor."""
    store = PlaybookStore(vault_path=tmp_path)
    skill = "financial-auditor"
    store.save(SkillPlaybook(
        skill=skill,
        procedure=(
            "## Ne Zaman Kullanılır\nFinansal tablo denetimi istendiğinde.\n\n"
            "## Çalışma Adımları\n1. Nakit akışını oku.\n2. Oranları hesapla.\n\n"
            "## Çıktı Biçimi\nTablo + kısa yorum.\n"
        ),
        source_count=5,
        processed_count=5,
    ))
    reports_dir = store.reports_dir(skill)
    reports_dir.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (reports_dir / f"2026-09-0{i + 1} Denetim {i}.md").write_text(
            "---\nskill: financial-auditor\n---\n"
            f"# Denetim {i}\n\nNakit akışı {i} milyon TL, borç/özkaynak oranı 0.{i}.\n",
            encoding="utf-8",
        )
    return tmp_path, store, skill


def test_compile_skill_five_reports_pages_index_and_zero_contradiction(skill_vault):
    vault, store, skill = skill_vault
    turns = []

    def fake_bridge(prompt):
        turns.append(prompt)
        assert "WİKİ KAVRAM SAYFASI DERLEME" in prompt
        return (
            "- Denetim raporunun kalıcı bilgisi: nakit akışı tablosu zorunludur.\n"
            "- Borç/özkaynak oranı her raporda verilir.\n"
        )

    res = wiki.compile_skill(skill, bridge=fake_bridge, budget_turns=10,
                             vault_path=vault, store=store)

    assert res["turns"] == 5, "rapor başına bir tur"
    assert len(res["new_pages"]) == 5
    assert res["processed"] == 5 and res["remaining"] == 0
    index = Path(res["index"])
    assert index.is_file()
    index_text = index.read_text(encoding="utf-8")
    assert "## Kavramlar" in index_text
    # Karpathy L2: kavram + varlık sayfaları + rapor sayfaları hepsi indekste.
    for page in res["new_pages"]:
        assert Path(page).stem in index_text
    assert Path(res["log"]).is_file()
    # Çelişki denetimi
    assert res["lint"] is not None
    assert res["lint"]["counts"].get("contradiction", 0) == 0


def test_compile_skill_is_incremental_second_call_spends_zero_turns(skill_vault):
    vault, store, skill = skill_vault
    calls = {"n": 0}

    def fake_bridge(prompt):
        calls["n"] += 1
        return "- Kalıcı bilgi: nakit akışı tablosu zorunludur, oran raporlanır.\n"

    first = wiki.compile_skill(skill, bridge=fake_bridge, vault_path=vault, store=store)
    second = wiki.compile_skill(skill, bridge=fake_bridge, vault_path=vault, store=store)

    assert first["turns"] == 5
    assert second["turns"] == 0
    assert calls["n"] == 5
    assert "yeni rapor yok" in second["reason"]
    state = wiki.load_wiki_state(skill, vault)
    assert len(state["processed"]) == 5


def test_compile_skill_respects_budget_turns(skill_vault):
    vault, store, skill = skill_vault
    res = wiki.compile_skill(
        skill, bridge=lambda p: "- Kalıcı bilgi: nakit akışı tablosu zorunlu, oran verilir.\n",
        budget_turns=2, vault_path=vault, store=store)
    assert res["turns"] == 2
    assert res["processed"] == 2 and res["remaining"] == 3


def test_compile_skill_without_bridge_calls_no_model(skill_vault):
    vault, store, skill = skill_vault
    res = wiki.compile_skill(skill, bridge=None, vault_path=vault, store=store)
    assert res["turns"] == 0
    assert res["new_pages"] == []
    # Playbook tabanlı sayfalar yine üretilir (LLM'siz).
    assert res["base"]["written"] >= 3
    assert res["pages"]


# ==========================================================================
# 11.9 — genel sohbet beyin paketi
# ==========================================================================


class _FakeVault:
    def read_global_memory(self):
        return "Kalıcı hafıza: kullanıcı Türkçe yanıt ister ve ölçüm bekler."


def test_general_brain_section_only_when_no_skill(skill_vault, mem):
    vault, store, skill = skill_vault
    # Kimlik düğümü + wiki sayfaları (LLM'siz üretim)
    node, _ = mem.record_memory(
        category="ego",
        content="Entropy: kendi becerilerini öğrenen, ölçen ve raporlayan bir sistemim.",
        importance=0.95, provenance="system",
    )
    wiki.ingest_playbook_to_wiki(skill, vault_path=vault, store=store)

    builder = CognitiveContextBuilder(memory_system=mem, vault_manager=_FakeVault(),
                                      playbook_store=store)
    general = builder.build("nakit akışı tablosu nasıl okunur", skill_name=None,
                            include_handoff=False)
    kinds = {s.kind for s in general.sections}
    assert "general_brain" in kinds

    scoped = builder.build("nakit akışı tablosu nasıl okunur", skill_name=skill,
                           include_handoff=False)
    assert "general_brain" not in {s.kind for s in scoped.sections}
    assert "playbook" in {s.kind for s in scoped.sections}


def test_general_brain_contains_rules_and_cross_skill_wiki_but_no_identity(skill_vault, mem):
    vault, store, skill = skill_vault
    mem.record_memory(
        category="ego",
        content="Entropy: kendi becerilerini öğrenen, ölçen ve raporlayan bir sistemim.",
        importance=0.95, provenance="system",
    )
    from entropy.memory import promoted_rules

    rule = promoted_rules.propose_rule(
        promoted_rules.ENTROPY_OFFICE,
        "",
        "Bu projede ölçüm olmadan iddia yazılmaz.",
        vault_path=vault,
    )
    promoted_rules.promote(promoted_rules.ENTROPY_OFFICE, rule.id, vault_path=vault)
    wiki.ingest_playbook_to_wiki(skill, vault_path=vault, store=store)

    builder = CognitiveContextBuilder(memory_system=mem, vault_manager=_FakeVault(),
                                      playbook_store=store)
    section = builder._general_brain_section("nakit akışı tablosu", BUDGET_GENERAL_BRAIN)
    assert section is not None
    assert section.kind == "general_brain"
    # Faz 13-A2: KİMLİK bloğu beyin paketinden ÇIKARILDI. Kimlik sistem
    # isteminin 1. bölümünde zaten var; bağlamda ikinci kopyası hem 300 token
    # boşa gidiyordu hem de `brain_lookup` onu "yanıt" sanıp araştırma
    # kartlarını kapatıyordu (gerçek ekran kanıtı, STATE §2.9).
    assert "[Kimlik]" not in section.body
    assert "kendi becerilerini öğrenen" not in section.body
    assert "ölçüm olmadan iddia yazılmaz" in section.body
    assert "[Wiki]" in section.body
    assert section.tokens <= BUDGET_GENERAL_BRAIN


def test_general_brain_respects_budget_and_lifts_usage(skill_vault, mem):
    vault, store, skill = skill_vault
    mem.record_memory(
        category="ego",
        content="Entropy kimliği: " + ("ölçüm ve kanıt zorunludur. " * 40),
        importance=0.95, provenance="system",
    )
    wiki.ingest_playbook_to_wiki(skill, vault_path=vault, store=store)
    builder = CognitiveContextBuilder(memory_system=mem, vault_manager=_FakeVault(),
                                      playbook_store=store)

    ctx = builder.build("nakit akışı", skill_name=None, include_handoff=False)
    brain = [s for s in ctx.sections if s.kind == "general_brain"]
    assert brain and brain[0].tokens <= BUDGET_GENERAL_BRAIN
    assert ctx.tokens <= ctx.budget
    summary = ctx.summary()
    assert any(s["kind"] == "general_brain" for s in summary["sections"])


def test_cross_skill_wiki_pages_are_discovered(skill_vault, mem):
    vault, store, skill = skill_vault
    wiki.ingest_playbook_to_wiki(skill, vault_path=vault, store=store)
    builder = CognitiveContextBuilder(memory_system=mem, vault_manager=_FakeVault(),
                                      playbook_store=store)
    assert builder._all_skill_names() == [skill]
    assert builder._wiki_page_files(None), "yeteneksiz çağrı tüm sayfaları görmeli"
