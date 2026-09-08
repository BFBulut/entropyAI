"""
/distill yerel komutu ve damıtmanın köprü üzerinden arka planda çalışması.

Köprü sahte: send_background_task_async kaydedilir ve istenirse hemen tamamlanır.
Böylece AGY'ye gitmeden, on_result geri çağrısı ve playbook_updated sinyali
uçtan uca doğrulanır.
"""

from pathlib import Path

import pytest

from entropy.core.event_bus import bus
from entropy.core.slash_commands import try_handle_local_command
from entropy.memory.distiller import PlaybookDistiller
from entropy.memory.playbook import PlaybookStore, SkillReportIndex


class _FakeBridge:
    """send_background_task_async çağrısını yakalar; complete() ile sonucu teslim eder."""

    def __init__(self, project_dir=None):
        self.active_project_dir = project_dir
        self.calls = []

    def send_background_task_async(self, **kwargs):
        self.calls.append(kwargs)

    def complete(self, text: str, success: bool = True):
        for call in self.calls:
            cb = call.get("on_result")
            if cb:
                cb(text, success)


def _skill_store(root: Path, skill: str, n: int) -> PlaybookStore:
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (rep / f"r{i}.md").write_text(f"---\ntitle: R{i}\n---\n\nSite denetimi adimi {i}.\n" + "x" * 500, encoding="utf-8")
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


def test_run_via_bridge_starts_background_task_and_ingests(tmp_path):
    store = _skill_store(tmp_path, "demo", 3)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()

    got = []
    bus.playbook_updated.connect(got.append)
    try:
        started = d.run_via_bridge(bridge, "demo", description="deneme")
        assert started["skill"] == "demo"
        assert started["sources"] == 3
        assert len(bridge.calls) == 1

        call = bridge.calls[0]
        assert call["save_report"] is False, "damıtma çıktısı rapor arşivine yazılmamalı"
        assert call["mode"] == "accept-edits", "plan modu agy'de keşif/plan döngüsü tetikliyor; sohbet modu kullanılmalı"
        assert "YETENEK YORDAMI DAMITMA" in call["prompt"]
        assert store.load("demo") is None, "sonuç gelmeden playbook yazılmamalı"

        bridge.complete("## Calisma Adimlari\n1. Tara.\n2. Karsilastir.")
        pb = store.load("demo")
        assert pb is not None and pb.source_count == 3
        assert got == ["demo"], "playbook_updated sinyali yayınlanmalı"
    finally:
        bus.playbook_updated.disconnect(got.append)


def test_run_via_bridge_failed_task_leaves_playbook_untouched(tmp_path):
    store = _skill_store(tmp_path, "demo", 2)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()
    d.run_via_bridge(bridge, "demo")
    bridge.complete("", success=False)
    assert store.load("demo") is None


def test_run_via_bridge_without_sources_returns_none(tmp_path):
    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))
    bridge = _FakeBridge()
    assert PlaybookDistiller(store=store).run_via_bridge(bridge, "bos") is None
    assert bridge.calls == []


def test_local_command_index_rebuilds_into_injected_store(monkeypatch, tmp_path):
    """/distill index gerçek kasaya değil enjekte edilen depoya yazmalı."""
    import entropy.skills.manager as sm_mod
    from entropy.skills.manager import SkillDefinition

    ent = tmp_path / "Entropy" / "Reports"
    ent.mkdir(parents=True)
    (ent / "site_denetimi.md").write_text("---\ntitle: Site\n---\n\n" + "web sitesi seo rakip analizi " * 40, encoding="utf-8")
    (ent / "bilanco.md").write_text("---\ntitle: Bilanco\n---\n\n" + "bilanco nakit akim denetim " * 40, encoding="utf-8")

    class _SM:
        def __init__(self, *a, **k):
            pass

        def list_skills(self):
            return [
                SkillDefinition(name="media-agency-soldier", description="d", instructions="", path=str(tmp_path), scripts=[]),
                SkillDefinition(name="financial-auditor", description="d", instructions="", path=str(tmp_path), scripts=[]),
            ]

        def auto_detect_skill_for_prompt(self, text, **kw):
            low = text.lower()
            if "seo" in low:
                return self.list_skills()[0]
            if "bilanco" in low:
                return self.list_skills()[1]
            return None

    monkeypatch.setattr(sm_mod, "SkillManager", _SM)

    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))
    out = try_handle_local_command("/distill index", _FakeBridge(), distiller=PlaybookDistiller(store=store))
    assert out and "2 rapor tarandı" in out and "2 tanesi" in out
    assert (tmp_path / "idx.json").is_file()
    assert {p.stem for p in store.index.paths_for("media-agency-soldier")} == {"site_denetimi"}
    assert {p.stem for p in store.index.paths_for("financial-auditor")} == {"bilanco"}


def test_background_task_report_is_attributed_to_detected_skill(tmp_path, monkeypatch):
    """
    Arka plan görevinin raporu, prompt'tan tespit edilen yeteneğe atfedilmeli.

    Bu atıf olmadan zamanlanmış araştırma raporları hiçbir yetenek için damıtma
    kaynağı sayılmaz (eski kasada 0 rapor atıflıydı).
    """
    import entropy.memory.obsidian.vault_manager as vm_mod
    import entropy.memory.supabase.cognitive_memory as cm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))

    captured = {}

    def fake_save(self, title, content, tags=None, project_name=None, skill_name=None):
        captured.update(title=title, project_name=project_name, skill_name=skill_name)
        out = tmp_path / "rapor.md"
        out.write_text(content, encoding="utf-8")
        return out

    monkeypatch.setattr(vm_mod.ObsidianVaultManager, "save_research_report", fake_save)
    monkeypatch.setattr(cm_mod.CognitiveMemorySystem, "store_node", lambda self, **kw: (None, False))

    class _Skill:
        name = "media-agency-soldier"

    monkeypatch.setattr(bridge, "detect_skill_for_prompt", lambda prompt, sm=None: _Skill())

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
                '{"event": "step_update", "step_update": {"text_delta": "Site incelendi"}}\n',
                '{"event": "result", "result": {"response": "Buyume onerileri hazir"}}\n',
                "",
            ])
            self.pid = 4242

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    bridge._execute_background_task_worker(
        task_id="attr-1",
        task_name="Site Denetimi",
        prompt="canivopets sitesini incele ve buyume onerileri cikar",
        mode="plan",
    )

    assert captured["skill_name"] == "media-agency-soldier"
    assert captured["project_name"] == tmp_path.name


def test_real_bridge_background_task_delivers_full_output_and_skips_report(tmp_path, monkeypatch):
    """
    Gerçek köprü imzası: on_result tam çıktıyla çağrılmalı, save_report=False iken
    kasaya rapor yazılmamalı.

    Sahte köprüyle yazılan testler imza uyumsuzluğunu gizliyordu; bu test gerçek
    send_background_task_async / worker yolunu (Popen sahteyle) uçtan uca sürer.
    """
    import threading

    import entropy.memory.obsidian.vault_manager as vm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))

    saved = []
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
                '{"event": "step_update", "step_update": {"text_delta": "## Adimlar\\n1. Tara."}}\n',
                '{"event": "result", "result": {"response": "tamam"}}\n',
                "",
            ])
            self.pid = 4243

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    done = threading.Event()
    got = {}

    def on_result(text, ok):
        got.update(text=text, ok=ok)
        done.set()

    bridge.send_background_task_async(
        task_id="real-1",
        task_name="Damıtma Denemesi",
        prompt="yordam damit",
        mode="plan",
        on_result=on_result,
        save_report=False,
    )
    assert done.wait(timeout=10), "on_result çağrılmadı"
    assert got["ok"] is True
    assert "Adimlar" in got["text"]
    assert saved == [], "save_report=False iken rapor yazılmamalı"


def test_long_prompt_goes_through_stdin_not_argv(tmp_path, monkeypatch):
    """
    20k karakteri aşan prompt argv'ye değil stdin NDJSON'a gitmeli.

    Regresyon: 24 raporluk damıtma prompt'u Windows'un 32.767 karakterlik komut
    satırı sınırına takılıp "[WinError 206]" ile hiç başlayamıyordu.
    """
    import json
    import subprocess

    from entropy.core.agy_bridge import ARGV_PROMPT_SAFE_LIMIT, AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))

    seen = {}

    class DummyStdin:
        def __init__(self):
            self.buf = []
            self.closed = False

        def write(self, s):
            self.buf.append(s)

        def flush(self):
            pass

        def close(self):
            self.closed = True

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            seen["cmd"] = list(cmd)
            seen["stdin_kw"] = kwargs.get("stdin")
            self.stdin = DummyStdin() if kwargs.get("stdin") == subprocess.PIPE else None
            seen["proc"] = self
            self.stdout = DummyStdout(['{"event": "result", "result": {"response": "ok"}}\n', ""])
            self.pid = 4244

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    long_prompt = "rapor metni " * (ARGV_PROMPT_SAFE_LIMIT // 10)
    assert len(long_prompt) > ARGV_PROMPT_SAFE_LIMIT

    bridge._execute_background_task_worker(
        task_id="stdin-1", task_name="Uzun Damıtma", prompt=long_prompt, mode="plan", save_report=False
    )

    cmd = seen["cmd"]
    p_idx = cmd.index("-p")
    assert cmd[p_idx + 1] == "", "uzun prompt argv'de kalmamalı"
    assert "--input-format" in cmd and cmd[cmd.index("--input-format") + 1] == "stream-json"
    assert seen["stdin_kw"] == subprocess.PIPE
    proc = seen["proc"]
    assert proc.stdin.closed, "stdin yazıldıktan sonra kapatılmalı (aksi hâlde agy bekler)"
    msg = json.loads("".join(proc.stdin.buf))
    assert msg == {"event": "user", "message": {"role": "user", "content": long_prompt}}


def test_short_prompt_stays_on_argv(tmp_path, monkeypatch):
    import subprocess

    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))
    seen = {}

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            seen["cmd"] = list(cmd)
            seen["stdin_kw"] = kwargs.get("stdin")
            self.stdin = None
            self.stdout = DummyStdout(['{"event": "result", "result": {"response": "ok"}}\n', ""])
            self.pid = 4245

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    bridge._execute_background_task_worker(task_id="argv-1", task_name="Kısa", prompt="kisa prompt", mode="plan", save_report=False)
    cmd = seen["cmd"]
    assert cmd[cmd.index("-p") + 1] == "kisa prompt"
    assert "--input-format" not in cmd
    assert seen["stdin_kw"] == subprocess.DEVNULL


def test_background_task_usage_is_counted_and_persisted(tmp_path, monkeypatch):
    """
    Arka plan görevinin agy 'usage' değeri: oturum sayacına eklenmeli, rozet
    sinyali yayılmalı ve ledger'a görev başına yazılmalı. Önceden hiçbiri olmuyordu.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.event_bus import bus
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", ledger)

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
                '{"event": "result", "result": {"response": "bitti", '
                '"usage": {"input_tokens": 17000, "output_tokens": 2500, "thinking_tokens": 900, '
                '"cache_read_tokens": 100, "total_tokens": 19500}}}\n',
                "",
            ])
            self.pid = 4246
            self.stdin = None

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    emitted = []
    bus.token_usage_updated.connect(emitted.append)
    try:
        bridge._execute_background_task_worker(task_id="u-1", task_name="Damıtma", prompt="x", mode="plan", save_report=False)
        bridge._execute_background_task_worker(task_id="u-2", task_name="Damıtma", prompt="y", mode="plan", save_report=False)
    finally:
        bus.token_usage_updated.disconnect(emitted.append)

    assert bridge.background_total_tokens == 39000
    assert bridge.last_background_usage["output_tokens"] == 2500
    assert 19500 in emitted

    row = ledger.get_task("u-1")
    assert row["total_tokens"] == 19500 and row["input_tokens"] == 17000 and row["output_tokens"] == 2500
    totals = ledger.token_totals()
    assert totals == {"input_tokens": 34000, "output_tokens": 5000, "total_tokens": 39000, "tasks_with_usage": 2}


def test_ledger_migrates_token_columns_on_old_db(tmp_path):
    """Eski şemalı bir ledger açıldığında token sütunları eklenmeli, veri korunmalı."""
    import sqlite3

    from entropy.core.task_ledger import TaskLedger

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, task_name TEXT NOT NULL, project_path TEXT, status TEXT NOT NULL, "
        "created_at TIMESTAMP, started_at TIMESTAMP, completed_at TIMESTAMP, error TEXT, result_summary TEXT)"
    )
    con.execute("INSERT INTO tasks VALUES ('old-1','Eski','p','SUCCESS','t','t','t',NULL,'ok')")
    con.commit()
    con.close()

    ledger = TaskLedger(db_path=db)
    row = ledger.get_task("old-1")
    assert row["result_summary"] == "ok"
    assert ledger.token_totals()["tasks_with_usage"] == 0
    ledger.record_task_success("old-1", summary="ok", usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    assert ledger.get_task("old-1")["total_tokens"] == 15


def test_local_command_ignores_non_distill():
    assert try_handle_local_command("merhaba", _FakeBridge()) is None
    assert try_handle_local_command("/help", _FakeBridge()) is None
    assert try_handle_local_command("/distillery", _FakeBridge()) is None


def test_local_command_unknown_skill_reports_available(monkeypatch, tmp_path):
    """Bilinmeyen yetenek adı AGY'ye gitmemeli; mevcut adlar listelenmeli."""
    import entropy.core.slash_commands as sc

    class _SM:
        def __init__(self, *a, **k):
            pass

        def list_skills(self):
            from entropy.skills.manager import SkillDefinition
            return [SkillDefinition(name="gercek-yetenek", description="d", instructions="", path=str(tmp_path), scripts=[])]

    import entropy.skills.manager as sm_mod
    monkeypatch.setattr(sm_mod, "SkillManager", _SM)

    out = try_handle_local_command("/distill olmayan", _FakeBridge())
    assert out is not None
    assert "olmayan" in out and "gercek-yetenek" in out


def test_run_via_bridge_uses_distiller_subagent_in_project_dir(tmp_path):
    """Damıtma agy'nin araçsız 'distiller' alt ajanıyla koşar; tanım proje dizinine yazılır."""
    from entropy.memory.distiller import DISTILL_AGENT_MD

    store = _skill_store(tmp_path, "demo", 2)
    proj = tmp_path / "proj"
    proj.mkdir()
    bridge = _FakeBridge(project_dir=proj)
    PlaybookDistiller(store=store).run_via_bridge(bridge, "demo")
    assert bridge.calls[0]["agent"] == "distiller"
    agent_md = proj / ".agents" / "agents" / "distiller" / "agent.md"
    assert agent_md.read_text(encoding="utf-8") == DISTILL_AGENT_MD
    assert "model: flash" in DISTILL_AGENT_MD and "subagent: true" in DISTILL_AGENT_MD


def test_run_via_bridge_without_project_dir_falls_back_to_default_agent(tmp_path):
    store = _skill_store(tmp_path, "demo", 2)
    bridge = _FakeBridge(project_dir=None)
    PlaybookDistiller(store=store).run_via_bridge(bridge, "demo")
    assert bridge.calls[0]["agent"] is None
