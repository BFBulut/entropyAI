"""
FAZ 3d QA — ofis belleği cephe modülü ve harness'ın gerçek kasaya yazımı.

Pencere (`entropy.desk.window`) `entropy.memory.office_memory.load_office_memory`
bekliyor; depolama `entropy.memory.agent_memory` içinde. Bu dosya iki katmanın
imza uyumunu ve harness -> wiki/bellek yazımının gerçekten dosya ürettiğini
kanıtlar. Gerçek agy çağrısı yok: köprü sahte, kasa tmp_path.
"""

import json
import threading

import pytest

from entropy.agents.harness import OfficeHarness
from entropy.agents.offices import OfficeRegistry
from entropy.agents.registry import AgentRegistry
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id
from entropy.memory import agent_memory as am
from entropy.memory import office_memory as om
from entropy.memory import wiki


# --- cephe modülü ----------------------------------------------------------


def test_facade_reexports_write_helpers():
    assert om.append_office_memory is am.append_office_memory
    assert om.consolidate_office_memory is am.consolidate_office_memory
    assert om.office_memory_path is am.office_memory_path


def test_facade_returns_full_text_when_budget_is_none(tmp_path):
    for i in range(3):
        am.append_office_memory(
            "ofis",
            {"title": f"kart {i}", "vault_path": tmp_path,
             "learning": f"öğrenim {i} " + "z" * 200},
        )
    full = om.load_office_memory("ofis", vault_path=tmp_path)
    raw = am.office_memory_path("ofis", tmp_path).read_text(encoding="utf-8")
    assert full == raw
    # Tam metin, 300 token'lık özetten kesinlikle daha uzun olmalı.
    budgeted = om.load_office_memory("ofis", budget_tokens=300, vault_path=tmp_path)
    assert 0 < len(budgeted) < len(full)
    assert budgeted == am.load_office_memory("ofis", budget_tokens=300, vault_path=tmp_path)


def test_facade_is_safe_on_missing_office_and_empty_name(tmp_path):
    assert om.load_office_memory("", vault_path=tmp_path) == ""
    assert om.load_office_memory("yok-boyle-ofis", vault_path=tmp_path) == ""


def test_desk_window_helper_uses_facade(tmp_path, monkeypatch):
    """Pencerenin yardımcı fonksiyonu cepheden TAM metni almalı."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path, raising=False)
    am.append_office_memory("ofis", {"title": "kart", "vault_path": tmp_path,
                                     "learning": "cepheden okunmalı"})
    from entropy.desk import window as desk_window

    text = desk_window.load_office_memory("ofis")
    assert "cepheden okunmalı" in text
    assert desk_window.load_office_memory("") == ""


# --- harness -> gerçek kasa -------------------------------------------------


class _Bridge:
    provider_name = "agy"

    def __init__(self, responses):
        self.responses = list(responses)
        self._lock = threading.RLock()

    def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                   on_result=None, save_report=True, agent=None, **kw):
        with self._lock:
            text, ok = "", False
            for idx, (matcher, body, good) in enumerate(self.responses):
                if matcher in task_id:
                    self.responses.pop(idx)
                    text, ok = body, good
                    break
        if on_result is not None:
            on_result(text, ok)
        return task_id

    def terminate_background_task(self, task_id):
        return True


@pytest.fixture(autouse=True)
def _clean_active():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


def test_harness_writes_office_report_memory_and_log_to_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    vault = tmp_path / "Vault"
    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)

    registry = AgentRegistry(vault_path=vault)
    offices = OfficeRegistry(vault_path=vault)
    board = TaskBoard(vault_path=vault)
    registry.ensure_defaults()
    offices.ensure_defaults()

    plan = "```json\n" + json.dumps({"subtasks": [
        {"title": "Kaynak taraması", "goal": "kaynakları listele",
         "criteria": ["3 kaynak"], "agent": "arastirmaci",
         "provider": "agy", "model": ""}
    ]}, ensure_ascii=False) + "\n```"

    card = board.create(TaskCard(
        id=new_task_id("Sürüm notu"), title="Sürüm notu", status="backlog",
        agent="orkestrator", provider="agy", office="arastirma-ofisi",
        skill="arastirma", goal="10 maddelik not", criteria=["10 madde"],
    ))

    harness = OfficeHarness(
        "arastirma-ofisi", board=board, registry=registry,
        offices=offices, bridge_factory=lambda provider: _Bridge([
            ("office-plan", plan, True),
            ("card-", "Bulgular: A, B, C", True),
            ("office-eval", '```json\n{"grades": []}\n```', True),
        ]),
    )
    harness.start(card.id)

    assert board.get(card.id).status == "review"

    # 1) wiki sorgu sayfası
    pages = list(wiki.queries_dir("arastirma", vault).glob("*.md"))
    assert pages, "wiki sorgu sayfası yazılmadı"
    page_text = pages[0].read_text(encoding="utf-8")
    assert f"category: {wiki.OFFICE_REPORT_CATEGORY}" in page_text

    # 2) Offices/<ofis>/reports özeti — kategori bayrağına bağlı
    reports = list(wiki.office_reports_dir("arastirma-ofisi", vault).glob("*.md"))
    assert reports, "ofis raporu özeti yazılmadı (meta['category'] eksik olabilir)"

    # 3) MEMORY.md — cephe modülünden tam metin okunabilmeli
    mem_text = om.load_office_memory("arastirma-ofisi", vault_path=vault)
    assert "Sürüm notu" in mem_text

    # 4) ofis günlüğü
    log = wiki.office_dir("arastirma-ofisi", vault) / "log.md"
    assert log.exists() and log.read_text(encoding="utf-8").strip()
