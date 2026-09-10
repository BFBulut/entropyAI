"""
Faz 12-C: beynin kapanışı + beceri sentezi v1.

Kapsam:
  1. `system_prompt` bölüm 2'ye pano araçları eki (guard'lı, ≤ 600 karakter)
  2. `wiki.compile_skill` artımlılık sözleşmesi (`WIKI.state.json`, parçalı koşu)
  3. `gray_merge` kasa günlüğü (`Entropy/Memory/merge_log.md`) + K9 raporu
  4. `memory.skill_synthesis` beceri adayı üretimi, öz-doğrulama, onay/ret

Gerçek model çağrısı YOK: köprü her yerde sahte `send_prompt`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from entropy.memory import gray_merge, system_prompt, wiki  # noqa: E402
from entropy.memory import skill_synthesis as ss  # noqa: E402
from entropy.memory.playbook import PlaybookStore, SkillPlaybook  # noqa: E402


SKILL = "rapor-denetleyici"


# ---------------------------------------------------------------- fikstürler


def _vault_with_skill(tmp_path: Path, reports: int = 3) -> PlaybookStore:
    store = PlaybookStore(vault_path=tmp_path)
    store.save(SkillPlaybook(
        skill=SKILL,
        procedure=(
            "## Adımlar\n"
            "- Kaynak dosyayı oku ve tabloları çıkar.\n"
            "- Sayıları çapraz doğrula.\n"
            "- Bulguları kaynağıyla birlikte yaz.\n"
        ),
        source_count=reports,
        processed_count=reports,
    ))
    rdir = store.reports_dir(SKILL)
    rdir.mkdir(parents=True, exist_ok=True)
    for i in range(reports):
        (rdir / f"Rapor_{i}.md").write_text(
            f"# Rapor {i}\n\nBulgu {i}: tablo satır sayısı {10 + i}.\n",
            encoding="utf-8",
        )
    return store


def _fake_bridge(calls: list):
    def _send(prompt: str) -> str:
        calls.append(prompt)
        return (
            "## Ne zaman kullanılır\n- Tekrarlayan tablo denetimlerinde.\n"
            "- Tek seferlik işlerde kullanma.\n\n"
            "## Ortam varsayımları\n- Python 3.13, ağ gerekmez.\n\n"
            "## Girdiler\n- `--input` ile JSON dosya yolu.\n\n"
            "## Çıktılar\n- `sonuc.json`: bulgu listesi.\n\n"
            "## Adımlar\n1. Dosyayı oku.\n2. Tabloyu çıkar.\n3. Sayıları doğrula.\n\n"
            "## Sonlandırma ölçütü\n- `pytest tests/` yeşil ve `sonuc.json` boş değil.\n\n"
            "## Kaynaklar\n- Playbook: `PLAYBOOK.md`\n"
        )
    return _send


# ------------------------------------------------- 1. pano araçları (bölüm 2)


def test_board_tools_section_is_skipped_when_symbol_missing(monkeypatch):
    """12-B sembolü hiçbir modülde yoksa kopya metin tutulmaz: bölüm boş kalır."""
    import entropy.agents.board_tools as bt
    import entropy.core.response_hooks as rh

    monkeypatch.delattr(rh, "entropy_tools_section", raising=False)
    monkeypatch.delattr(bt, "entropy_tools_section", raising=False)
    assert system_prompt.board_tools_section() == ""


def test_board_tools_section_uses_the_real_12b_symbol_within_budget():
    """Monkeypatch YOK: gerçek `response_hooks` metni istemde ve bütçede."""
    section = system_prompt.board_tools_section()
    assert "[PANO board_create]" in section
    assert "[/PANO]" in section, "blok bütünlüğü korunur (yarım JSON şablonu yok)"
    assert len(section) <= system_prompt.BUDGET_BOARD_TOOLS <= 600

    chat = system_prompt.build_system_prompt("chat", provider="claude")
    assert "[PANO board_create]" in chat
    # Araç sözleşmesinin EKİdir: sözleşme hâlâ yerinde.
    assert "[ARAÇ SÖZLEŞMESİ]" in chat


def test_board_tools_section_falls_back_to_board_tools_module(monkeypatch):
    """`response_hooks` yoksa geriye dönük `agents.board_tools` yolu çalışır."""
    import entropy.agents.board_tools as bt
    import entropy.core.response_hooks as rh

    monkeypatch.delattr(rh, "entropy_tools_section", raising=False)
    monkeypatch.setattr(
        bt, "entropy_tools_section",
        lambda: '[PANO board_create]\n{"title": "<başlık>"}\n[/PANO]',
        raising=False,
    )
    assert "board_create" in system_prompt.board_tools_section()


def test_real_section_overflows_raw_budget_and_is_trimmed():
    """Ham 12-B metni bütçeden uzun; kırpma bloklarla yapılır, board_create kalır."""
    from entropy.core.response_hooks import entropy_tools_section

    raw = entropy_tools_section()
    assert len(raw) > system_prompt.BUDGET_BOARD_TOOLS, "ham metin zaten bütçede"
    section = system_prompt.board_tools_section()
    assert len(section) < len(raw)
    assert "[PANO board_create]" in section
    assert section.count("[PANO ") == section.count("[/PANO]")


def test_board_tools_section_is_clamped_to_budget(monkeypatch):
    import entropy.core.response_hooks as rh

    monkeypatch.setattr(rh, "entropy_tools_section", lambda: "x" * 5000, raising=False)
    assert len(system_prompt.board_tools_section()) <= system_prompt.BUDGET_BOARD_TOOLS


def test_board_tools_not_in_card_prompt_or_agy():
    """Gerçek sembolle: kart kipinde ve agy yolunda pano aracı YOK."""
    card = system_prompt.build_system_prompt("card", provider="claude")
    assert "board_create" not in card
    agy = system_prompt.build_system_prompt("chat", provider="agy")
    assert "board_create" not in agy


# --------------------------------------------- 2. wiki artımlılık sözleşmesi


def test_wiki_state_is_written_and_second_call_spends_zero_turns(tmp_path):
    store = _vault_with_skill(tmp_path, reports=2)
    calls: list = []

    first = wiki.compile_skill(
        SKILL, bridge=_fake_bridge(calls), budget_turns=8,
        vault_path=tmp_path, store=store,
    )
    assert first["turns"] == 2, first
    assert first["processed"] == 2 and first["remaining"] == 0

    state_path = wiki.wiki_state_path(SKILL, tmp_path)
    assert state_path.is_file(), "WIKI.state.json yazılmadı"
    processed = json.loads(state_path.read_text(encoding="utf-8"))["processed"]
    assert sorted(processed) == ["Rapor_0", "Rapor_1"]

    second = wiki.compile_skill(
        SKILL, bridge=_fake_bridge(calls), budget_turns=8,
        vault_path=tmp_path, store=store,
    )
    assert second["turns"] == 0, "artımlılık bozuk: ikinci çağrı kota harcadı"
    assert len(calls) == 2


def test_wiki_budget_turns_splits_run_and_remaining_is_reported(tmp_path):
    """Parçalı koşu sözleşmesi: kalan raporlar `remaining` ile döner."""
    store = _vault_with_skill(tmp_path, reports=5)
    calls: list = []
    bridge = _fake_bridge(calls)

    first = wiki.compile_skill(SKILL, bridge=bridge, budget_turns=2,
                               vault_path=tmp_path, store=store)
    assert first["turns"] == 2 and first["remaining"] == 3

    second = wiki.compile_skill(SKILL, bridge=bridge, budget_turns=2,
                                vault_path=tmp_path, store=store)
    assert second["turns"] == 2 and second["remaining"] == 1

    third = wiki.compile_skill(SKILL, bridge=bridge, budget_turns=2,
                               vault_path=tmp_path, store=store)
    assert third["turns"] == 1 and third["remaining"] == 0
    assert len(calls) == 5, "aynı rapor iki kez turlandı"
    assert third["lint"] is not None and "total" in third["lint"]


def test_wiki_without_bridge_spends_no_turn(tmp_path):
    store = _vault_with_skill(tmp_path, reports=2)
    out = wiki.compile_skill(SKILL, bridge=None, vault_path=tmp_path, store=store)
    assert out["turns"] == 0 and out["remaining"] == 2


# --------------------------------- 3. gri tur kasa günlüğü + K9 raporu


class _FakeGate:
    def __init__(self, tmp_path: Path, rows):
        self.queue_path = tmp_path / "memory" / "gray_queue.jsonl"
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._rows = rows

    def pending_gray(self):
        return list(self._rows)


class _FakeMemory:
    def __init__(self, gate):
        self.gate = gate

    def get_all_nodes(self):
        return []


def test_merge_round_appends_vault_log_line(tmp_path):
    rows = [{
        "node_id": "n1", "category": "semantic", "content": "A",
        "similarity": 0.9, "nearest_id": "n0", "nearest_content": "A'",
        "provenance": "report:x", "reason": "gri",
    }]
    memory = _FakeMemory(_FakeGate(tmp_path, rows))
    res = gray_merge.run_merge_round(memory=memory, send_prompt=None,
                                     vault_path=tmp_path)
    assert res.candidates == 1 and res.turns == 0  # kuru koşum: model çağrılmadı
    log = gray_merge.merge_log_path(tmp_path)
    assert log.is_file() and res.vault_log == str(log)
    body = log.read_text(encoding="utf-8")
    assert "1 aday" in body and "0 tur" in body


def test_merge_round_without_candidates_writes_nothing(tmp_path):
    memory = _FakeMemory(_FakeGate(tmp_path, []))
    res = gray_merge.run_merge_round(memory=memory, send_prompt=None,
                                     vault_path=tmp_path)
    assert res.candidates == 0 and res.vault_log is None
    assert not gray_merge.merge_log_path(tmp_path).exists()


def test_brain_metrics_k9_reports_ratio_and_last_round(tmp_path):
    import brain_metrics

    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "gray_queue.jsonl").write_text(
        json.dumps({"node_id": "a", "status": "pending"}) + "\n"
        + json.dumps({"node_id": "b", "status": "done"}) + "\n",
        encoding="utf-8",
    )
    (mem_dir / "gray_merge_log.jsonl").write_text(
        json.dumps({"candidates": 5, "merged": 3, "kept": 2, "turns": 1}) + "\n",
        encoding="utf-8",
    )
    report = brain_metrics.gray_queue_report(tmp_path / "cognitive_memory.db", nodes=100)
    assert report == {
        "rows": 2, "pending": 1, "done": 1, "nodes": 100, "ratio_pct": 2.0,
        "rounds": 1,
        "last_round": {"candidates": 5, "merged": 3, "kept": 2, "turns": 1},
    }


def test_brain_metrics_k6_wiki_share_is_measurable(tmp_path):
    """K6 hesaplayıcı kalıcı: wiki bölümünün bağlam içindeki payı."""
    import brain_metrics
    from entropy.memory.context_builder import AssembledContext, ContextSection

    ctx = AssembledContext(budget=4000)
    ctx.sections = [
        ContextSection(title="w", body="x" * 400, kind="wiki_pages", tokens=100),
        ContextSection(title="r", body="y" * 1200, kind="recall", tokens=300),
    ]

    class _B:
        def build(self, query, skill_name=None, token_budget=4000, **kwargs):
            # Ölçüm kasayı tüketmemeli: aktarım bölümü kapalı istenir.
            assert kwargs.get("include_handoff") is False
            return ctx

    out = brain_metrics.context_metrics(queries=["a", "b"], builder=_B())
    assert out["queries"] == 2
    assert out["K6_wiki_pct"] == 25.0
    assert out["K4_budget_pct"] == 10.0
    assert out["K5_distilled_pct"] == 25.0


# ------------------------------------------------ 4. beceri sentezi v1


def test_recurring_signal_needs_three_reports(tmp_path):
    store = _vault_with_skill(tmp_path, reports=3)
    signals = ss.recurring_signals(vault_path=tmp_path, store=store)
    names = {s["skill"]: s for s in signals}
    assert SKILL in names and names[SKILL]["reports"] == 3
    assert names[SKILL]["has_playbook"] is True

    store2 = _vault_with_skill(tmp_path / "az", reports=2)
    assert ss.recurring_signals(vault_path=tmp_path / "az", store=store2) == []


def test_synthesize_without_bridge_writes_candidate_skeleton(tmp_path):
    store = _vault_with_skill(tmp_path)
    out = ss.synthesize_skill(SKILL, vault_path=tmp_path, store=store)

    assert out["turns"] == 0, "kotasız kol model çağırdı"
    base = ss.candidate_dir(SKILL, tmp_path)
    assert (base / "SKILL.md").is_file()
    assert (base / "scripts" / f"{ss.slugify(SKILL)}.py").is_file()
    assert (base / "tests" / f"test_{ss.slugify(SKILL)}.py").is_file()
    assert (base / "CANDIDATE.json").is_file()

    text = (base / "SKILL.md").read_text(encoding="utf-8")
    for title in ss.REQUIRED_SECTIONS:
        assert f"## {title}" in text, f"şema bölümü eksik: {title}"
    assert "- Playbook:" in text, "kaynak (provenance) yazılmadı"

    # Kotasız kol da doğrulanabilir olmalı: zorunlu bölümler playbook/wiki/rapor
    # kaynağından gerçek içerikle dolar, yer tutucu kalmaz.
    assert ss.PLACEHOLDER_MARK not in text, "yer tutucu kaldı: bölüm doldurulmadı"
    assert out["status"] == ss.STATUS_VALIDATED, out["findings"]
    assert all(out["checks"].values()), out["checks"]
    assert "Rapor_0" in text, "çıktı bölümü rapor başlıklarından türemedi"


def test_synthesize_without_playbook_stays_draft(tmp_path):
    """Kaynak yoksa uydurma yok: bölümler yer tutucu kalır, aday taslaktır."""
    store = PlaybookStore(vault_path=tmp_path)
    rdir = store.reports_dir("kaynaksiz-yetenek")
    rdir.mkdir(parents=True, exist_ok=True)

    out = ss.synthesize_skill("kaynaksiz-yetenek", vault_path=tmp_path, store=store)

    assert out["turns"] == 0
    assert out["status"] == ss.STATUS_DRAFT, out["checks"]
    assert out["checks"]["schema_complete"] is False
    text = (ss.candidate_dir("kaynaksiz-yetenek", tmp_path) / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert ss.PLACEHOLDER_MARK in text


def test_single_turn_enrichment_validates_and_promotes(tmp_path):
    store = _vault_with_skill(tmp_path)
    calls: list = []
    out = ss.synthesize_skill(SKILL, send_prompt=_fake_bridge(calls),
                              vault_path=tmp_path, store=store)

    assert len(calls) == 1 and out["turns"] == 1, "tek turdan fazla kota harcandı"
    assert out["status"] == ss.STATUS_VALIDATED, out["findings"]
    assert all(out["checks"].values())

    state = json.loads(ss.candidate_state_path(SKILL, tmp_path).read_text(encoding="utf-8"))
    assert state["schema_version"] == ss.SCHEMA_VERSION
    assert state["skill"] == SKILL and state["sources"]

    listed = ss.list_candidates(tmp_path)
    assert [c["name"] for c in listed] == [ss.slugify(SKILL)]
    assert listed[0]["status"] == ss.STATUS_VALIDATED

    promoted = ss.promote_skill(SKILL, vault_path=tmp_path)
    assert promoted["ok"] is True
    target = ss.promoted_root(tmp_path) / ss.slugify(SKILL)
    assert (target / "SKILL.md").is_file()
    assert not (target / "CANDIDATE.json").exists(), "durum dosyası kasaya kopyalandı"
    assert ss.list_candidates(tmp_path)[0]["status"] == ss.STATUS_APPROVED


def test_promoted_skill_is_discovered_by_skill_manager(tmp_path):
    store = _vault_with_skill(tmp_path)
    ss.synthesize_skill(SKILL, send_prompt=_fake_bridge([]), vault_path=tmp_path, store=store)
    ss.promote_skill(SKILL, vault_path=tmp_path)

    manager = pytest.importorskip("entropy.skills.manager")
    mgr = manager.SkillManager(root_skills_dir=ss.promoted_root(tmp_path))
    names = {s.name for s in mgr.list_skills()}
    assert ss.slugify(SKILL) in names, names


def test_draft_candidate_cannot_be_promoted(tmp_path):
    """Kaynaksız yetenek taslakta kalır ve yükseltilemez."""
    store = PlaybookStore(vault_path=tmp_path)
    store.reports_dir("kaynaksiz-yetenek").mkdir(parents=True, exist_ok=True)
    ss.synthesize_skill("kaynaksiz-yetenek", vault_path=tmp_path, store=store)
    out = ss.promote_skill("kaynaksiz-yetenek", vault_path=tmp_path)
    assert out["ok"] is False and out["reason"] == "doğrulamadan geçmedi"
    assert not (ss.promoted_root(tmp_path) / "kaynaksiz-yetenek").exists()


def test_reject_keeps_files_and_blocks_promotion(tmp_path):
    store = _vault_with_skill(tmp_path)
    ss.synthesize_skill(SKILL, send_prompt=_fake_bridge([]), vault_path=tmp_path, store=store)
    out = ss.reject_skill(SKILL, reason="kaynak yetersiz", vault_path=tmp_path)

    assert out["status"] == ss.STATUS_REJECTED
    assert (ss.candidate_dir(SKILL, tmp_path) / "SKILL.md").is_file(), "aday silindi"
    assert ss.promote_skill(SKILL, vault_path=tmp_path)["ok"] is False


def test_validation_flags_brand_and_internal_leak(tmp_path):
    store = _vault_with_skill(tmp_path)
    ss.synthesize_skill(SKILL, send_prompt=_fake_bridge([]), vault_path=tmp_path, store=store)
    path = ss.candidate_dir(SKILL, tmp_path) / "SKILL.md"
    leak = "".join(("mur", "atify"))
    path.write_text(path.read_text(encoding="utf-8") + f"\n- {leak} ile karşılaştır\n",
                    encoding="utf-8")

    check = ss.validate_candidate(SKILL, vault_path=tmp_path)
    assert check["checks"]["no_leak"] is False
    assert any("marka" in f for f in check["findings"])
    assert ss.leak_findings("bu paket Entropy AI içindir")


def test_generated_candidate_has_no_internal_leak(tmp_path):
    store = _vault_with_skill(tmp_path)
    out = ss.synthesize_skill(SKILL, send_prompt=_fake_bridge([]),
                              vault_path=tmp_path, store=store)
    text = (ss.candidate_dir(SKILL, tmp_path) / "SKILL.md").read_text(encoding="utf-8")
    assert ss.leak_findings(text) == []
    assert out["checks"]["no_leak"] is True
