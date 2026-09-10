"""
Faz 12-A: `/memory merge`, `/memory dream`, `/wiki compile` köprü kablolaması.

Araştırma A §3.3: üç komut da köprüsüz koşuyordu (yanlış sembol adı, yutulan
`TypeError`, sabit `send_prompt=None`). Bu dosya kabloyu uçtan uca ölçer:
komut → uyarlayıcı → modülün `send_prompt` parametresi.
"""

from __future__ import annotations

import threading

import pytest

from entropy.core import slash_commands as sc


# Faz 12-B: üç komut da ARKA PLANDA koşuyor. Testler `--wait <sn>` bayrağıyla
# işin bitmesini bekler (Qt olay döngüsü yok) ve sonucu `bus.memory_job_progress`
# yükünden okur — kullanıcıya dönen HTML artık yalnızca "başladı" makbuzudur.
def _finished_message(job: str) -> str:
    """Arka plan işinin son sonucu (`bus.memory_job_progress` ile aynı yük).

    Sinyal Qt kuyruğundan geçtiği için olay döngüsüz testte okunamaz; aynı yük
    `slash_commands.last_memory_job()` ile de sunulur.
    """
    payload = sc.last_memory_job(job)
    assert payload.get("state") == "finished", f"iş bitmedi: {payload}"
    return str(payload.get("message") or "")


class FakeBridge:
    """Sahte köprü: arka plan görev yüzeyini taklit eder, süreç açmaz."""

    provider_name = "agy"
    selected_model = "gemini-3.8-flash-low"
    active_project_dir = None

    def __init__(self, answer: str = "[]", ok: bool = True):
        self.answer = answer
        self.ok = ok
        self.calls: list[dict] = []

    def send_background_task_async(self, task_id, task_name, prompt, **kw):
        self.calls.append({"task_id": task_id, "task_name": task_name,
                           "prompt": prompt, **kw})
        kw["on_result"](self.answer, self.ok)


# --------------------------------------------------------------------------
# /memory merge
# --------------------------------------------------------------------------


def test_memory_merge_calls_run_merge_round_with_bridge(monkeypatch):
    seen = {}

    def fake_round(memory=None, send_prompt=None, limit=8, gate=None, graph=None):
        seen["send_prompt"] = send_prompt
        seen["limit"] = limit
        seen["memory"] = memory
        return {"merged": 3, "pending": 0}

    monkeypatch.setattr("entropy.memory.gray_merge.run_merge_round", fake_round)
    bridge = FakeBridge()
    out = sc._handle_memory("merge --wait 5", bridge)

    assert "Gri Bant" in out and "arka planda" in out
    assert "merged" in _finished_message("memory-merge")
    assert callable(seen["send_prompt"]), "köprü geçmedi: kuru koşum kaldı"
    assert seen["limit"] == 8
    assert seen["memory"] is not None, "gerçek bellek nesnesi geçmeli"
    # Uyarlayıcı gerçekten köprüye gidiyor mu.
    assert seen["send_prompt"]("soru") == "[]"
    assert bridge.calls and bridge.calls[0]["prompt"] == "soru"


def test_memory_merge_without_bridge_is_dry_run(monkeypatch):
    seen = {}

    def fake_round(memory=None, send_prompt=None, **kw):
        seen["send_prompt"] = send_prompt
        return {"pending": 4}

    monkeypatch.setattr("entropy.memory.gray_merge.run_merge_round", fake_round)
    out = sc._handle_memory("merge --wait 5", None)
    assert seen["send_prompt"] is None
    assert "kuru koşum" in out


def test_memory_merge_import_error_surfaces_real_reason(monkeypatch):
    """Hata yutulmaz: kullanıcı 'modül kurulu değil' yalanı yerine gerçeği görür."""
    import builtins

    real_import = builtins.__import__

    def boom(name, *a, **k):
        if name == "entropy.memory.gray_merge":
            raise ImportError("numpy yok (deneme)")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    out = sc._handle_memory("merge", None)
    assert "numpy yok (deneme)" in out


# --------------------------------------------------------------------------
# /memory dream
# --------------------------------------------------------------------------


def test_memory_dream_passes_bridge(monkeypatch):
    seen = {}

    class Rapor:
        def __init__(self):
            self.summary = "20 küme, 23 birleştirme"

    def fake_dream(memory=None, send_prompt=None, **kw):
        seen["send_prompt"] = send_prompt
        return Rapor()

    monkeypatch.setattr("entropy.memory.dream.dream_and_consolidate", fake_dream)
    out = sc._handle_memory("dream --wait 5", FakeBridge())
    assert callable(seen["send_prompt"]), "/memory dream hâlâ send_prompt=None geçiyor"
    assert "Rüya Döngüsü" in out


# --------------------------------------------------------------------------
# /wiki compile
# --------------------------------------------------------------------------


def test_wiki_compile_passes_bridge_and_budget_turns(monkeypatch):
    seen = {}

    def fake_compile(skill, bridge=None, budget_turns=8, **kw):
        seen.update(skill=skill, bridge=bridge, budget_turns=budget_turns)
        return {"skill": skill, "turns": 5, "pages": 18, "remaining": 20}

    monkeypatch.setattr("entropy.memory.wiki.compile_skill", fake_compile)
    out = sc._handle_wiki("compile yazilim --turns 7 --wait 5", FakeBridge())

    assert seen["skill"] == "yazilim"
    assert seen["budget_turns"] == 7, "--turns budget_turns'e geçmedi"
    assert callable(seen["bridge"]), "wiki derleyicisi köprüsüz koşuyor"
    assert "tavan 7" in out
    # GERÇEK harcanan tur iş sonucunda gelir, tavan değil.
    assert "turns: 5" in _finished_message("wiki-compile")


def test_wiki_compile_reports_zero_turns_without_bridge(monkeypatch):
    monkeypatch.setattr(
        "entropy.memory.wiki.compile_skill",
        lambda skill, bridge=None, budget_turns=8, **kw: {"turns": 0, "pages": 3},
    )
    out = sc._handle_wiki("compile yazilim --turns 4 --wait 5", None)
    assert "kuru koşum" in out
    assert "turns: 0" in _finished_message("wiki-compile")


def test_wiki_plain_command_still_needs_no_bridge(monkeypatch):
    """`/wiki <yetenek>` model çağırmaz; köprü olmadan da çalışır."""
    monkeypatch.setattr(
        "entropy.memory.wiki.ingest_playbook_to_wiki",
        lambda name, **kw: {"written": 2, "concepts": ["a"], "entities": ["b"], "index": "i.md"},
    )
    out = sc._handle_wiki("yazilim", None)
    assert "Wiki Güncellendi" in out


# --------------------------------------------------------------------------
# Gerçek köprü yolu (sahte Popen) — sahte köprüyle geçen test yetmez.
# --------------------------------------------------------------------------


def test_real_bridge_send_prompt_returns_full_output(tmp_path, monkeypatch):
    """
    `make_send_prompt` GERÇEK `AgyProcessBridge.send_background_task_async`
    yolunu sürer (süreç sahte Popen ile taklit edilir): dönen dize turun tam
    çıktısıdır ve kasaya rapor YAZILMAZ (ara ürün).
    """
    import entropy.memory.obsidian.vault_manager as vm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.bridge_prompt import make_send_prompt
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))

    saved: list = []
    monkeypatch.setattr(
        vm_mod.ObsidianVaultManager,
        "save_research_report",
        lambda self, *a, **k: saved.append((a, k)) or (tmp_path / "x.md"),
    )

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout([
                '{"event": "step_update", "step_update": '
                '{"text_delta": "{\\"decisions\\": []}"}}\n',
                '{"event": "result", "result": {"response": "tamam"}}\n',
                "",
            ])
            self.pid = 5150

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    send = make_send_prompt(bridge, label="Gri bant birleştirme")
    out = send("aday listesi")

    assert "decisions" in out, f"tam çıktı gelmedi: {out!r}"
    assert saved == [], "hafıza turu kasaya rapor yazmamalı (ara ürün)"


def test_send_prompt_times_out_and_kills_task(monkeypatch):
    """Yanıt gelmezse tur sonsuza kadar beklemez; görev sonlandırılır."""
    from entropy.core.bridge_prompt import make_send_prompt

    killed: list[str] = []

    class Sessiz:
        def send_background_task_async(self, task_id, task_name, prompt, **kw):
            return None  # on_result hiç çağrılmaz

        def terminate_background_task(self, task_id):
            killed.append(task_id)

    send = make_send_prompt(Sessiz(), label="Test", timeout=0.2)
    with pytest.raises(TimeoutError):
        send("bir şey")
    assert killed, "zaman aşımında arka plan görevi öldürülmedi"


def test_send_prompt_returns_empty_on_failure():
    """Başarısız tur boş dize döner (modüller bunu 'karar yok' sayar)."""
    from entropy.core.bridge_prompt import make_send_prompt

    send = make_send_prompt(FakeBridge(answer="yarım", ok=False))
    assert send("x") == ""


def test_send_prompt_counts_turns():
    from entropy.core.bridge_prompt import make_send_prompt, turn_count

    bridge = FakeBridge(answer="ok")
    send = make_send_prompt(bridge)
    assert turn_count(send) == 0
    send("a")
    send("b")
    assert turn_count(send) == 2
    assert len(bridge.calls) == 2
    # Her tur ayrı görev kimliği alır (ledger çakışmasın).
    assert bridge.calls[0]["task_id"] != bridge.calls[1]["task_id"]


def test_send_prompt_is_thread_safe_enough_for_worker_delivery():
    """on_result işçi iş parçacığından gelse de çağıran çözülür."""
    from entropy.core.bridge_prompt import make_send_prompt

    class Gecikmeli:
        def send_background_task_async(self, task_id, task_name, prompt, **kw):
            threading.Timer(0.05, lambda: kw["on_result"]("geç cevap", True)).start()

    send = make_send_prompt(Gecikmeli(), timeout=5)
    assert send("soru") == "geç cevap"
