"""
Canlı doğrulama koşusunda bulunan iki Claude köprüsü kusurunun regresyonu.

Kaynak: gerçek `agy` + `claude` CLI ile koşulan `dogrulama` ofisi (Faz 7 canlı
teyit). Claude sağlayıcılı ofis alt kartı, prompt'u eşiğin altında olduğu için
argv'den geçti; Windows'ta `claude` bir toplu iş sarmalayıcısı (`claude.CMD`)
olduğundan `cmd.exe` çok satırlı argümanı ilk satır sonunda kesti ve modele
yalnızca `# ozetleyici-claude` başlığı ulaştı. Model "bana görev metni
verilmedi" diyerek durdu, kart `failed` oldu, ledger satırında `total_tokens`
NULL kaldı ve harcanan token ofis bütçesine hiç yazılmadı.
"""

import json
import threading

import pytest


class _DummyStdout:
    def __init__(self, lines):
        self._iter = iter(lines)

    def readline(self):
        return next(self._iter, "")

    def close(self):
        pass


def _bridge(tmp_path, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = ClaudeCodeBridge()
    bridge.set_project_directory(tmp_path)
    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger", ledger)
    return bridge, ledger


def test_multiline_prompt_never_stays_in_argv(tmp_path, monkeypatch):
    """
    Çok satırlı ama KISA prompt argv'de kalmamalı; stdin NDJSON'dan geçmeli.

    Eşik testi değil: uzunluk sınırının çok altındaki (~300 karakter) bir ofis
    alt kartı prompt'u da satır sonu içerdiği için argv'den çıkarılmalı.
    """
    bridge, _ = _bridge(tmp_path, monkeypatch)
    prompt = "# ozetleyici-claude\n\n[GÖREV SÖZLEŞMESİ]\nHedef: README özetle.\n"
    assert len(prompt) < 1000

    captured = {}

    class DummyProc:
        def __init__(self, args, *a, **kw):
            captured["argv"] = list(args)
            captured["stdin_kwarg"] = kw.get("stdin")
            self.stdout = _DummyStdout([
                json.dumps({"type": "assistant",
                            "message": {"content": [{"type": "text", "text": "tamam"}]}}) + "\n",
                json.dumps({"type": "result", "result": "tamam",
                            "usage": {"input_tokens": 10, "output_tokens": 5}}) + "\n",
                "",
            ])
            self.stdin = None
            self.pid = 1234

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="ml-1", task_name="cok satirli", prompt=prompt,
        on_result=lambda text, ok: done.set(), save_report=False,
        project_path=str(tmp_path), needs_write=False,
    )
    assert done.wait(timeout=15), "on_result çağrılmadı"

    argv = captured["argv"]
    assert "-p" in argv
    payload = argv[argv.index("-p") + 1]
    assert "\n" not in payload, (
        "Çok satırlı prompt argv'de kaldı; cmd.exe sarmalayıcısı ilk satırdan "
        f"sonrasını kesecekti: {payload!r}"
    )
    assert payload == ""
    assert "--input-format" in argv and argv[argv.index("--input-format") + 1] == "stream-json"


def test_multiline_system_prompt_goes_to_file_flag(tmp_path, monkeypatch):
    """Kısa ama çok satırlı sistem istemi de argv'de kalmamalı (aynı kesilme)."""
    from entropy.core.claude_bridge import SYSTEM_PROMPT_FILE_FLAG

    bridge, _ = _bridge(tmp_path, monkeypatch)
    cmd = bridge.build_command("tek satir", append_system_prompt="satir1\nsatir2")
    assert SYSTEM_PROMPT_FILE_FLAG in cmd, cmd
    assert "--append-system-prompt" not in cmd
    for token in cmd:
        assert "\n" not in token, f"argv'de çok satırlı argüman kaldı: {token!r}"


def test_failed_task_records_usage_in_ledger(tmp_path, monkeypatch):
    """
    Başarısız Claude görevinin token maliyeti ledger'a yazılmalı.

    Canlıda başarısız alt kartın `total_tokens` sütunu NULL kaldı; harness o
    yüzden gerçek maliyeti göremeyip karakter/4 tahminine düştü ve ofis bütçesi
    yakılan token'ı hiç saymadı. AGY köprüsü bunu A7a'da düzeltmişti.
    """
    bridge, ledger = _bridge(tmp_path, monkeypatch)

    class DummyProc:
        def __init__(self, args, *a, **kw):
            # Metin yok -> success False; ama usage geldi.
            self.stdout = _DummyStdout([
                json.dumps({"type": "result", "subtype": "error_during_execution",
                            "is_error": True, "result": "",
                            "usage": {"input_tokens": 900, "output_tokens": 100}}) + "\n",
                "",
            ])
            self.stdin = None
            self.pid = 99

        def wait(self):
            return 1

        def poll(self):
            return 1

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="fail-1", task_name="basarisiz", prompt="tek satir",
        on_result=lambda text, ok: done.set(), save_report=False,
        project_path=str(tmp_path), needs_write=False,
    )
    assert done.wait(timeout=15)

    rec = ledger.get_task("fail-1")
    assert rec is not None
    assert rec["status"] == "FAILED"
    assert rec.get("total_tokens"), f"başarısız görevin usage'ı yazılmadı: {rec}"


def test_claude_background_task_accepts_no_max_steps(tmp_path, monkeypatch):
    """
    BELGELEME testi: Claude köprüsü `max_steps` almıyor (adım tavanı yok).

    `TaskBoard.run` tavanı `_accepts_kwarg` ile eleyip düşürüyor; yani
    `MAX_STEPS_PER_CARD` yalnızca AGY alt kartlarında yaptırımlı. Bu test
    kusuru kilitler: parite sağlandığında ters çevrilmeli.
    """
    from entropy.agents.tasks import _accepts_kwarg
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.claude_bridge import ClaudeCodeBridge

    assert _accepts_kwarg(AgyProcessBridge.send_background_task_async, "max_steps") is True
    assert _accepts_kwarg(ClaudeCodeBridge.send_background_task_async, "max_steps") is False
