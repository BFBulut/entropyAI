"""
Performans düzeneğinin kendi testleri.

Burada ölçülen şey hız değil, düzeneğin doğruluğu:
  * koşu tmp dizindeki JSONL'a yazılıyor mu, geri okunuyor mu,
  * trend tablosu üretiliyor ve %20'yi aşan kötüleşme işaretleniyor mu,
  * gerçek Obsidian kasasına ve gerçek .entropy/perf'e hiçbir şey yazılmıyor mu.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from entropy.core import perf_history  # noqa: E402


@pytest.fixture(scope="module")
def perf_bench():
    """scripts/perf_bench.py paket içinde değil; dosya yolundan yüklenir."""
    path = REPO_ROOT / "scripts" / "perf_bench.py"
    spec = importlib.util.spec_from_file_location("perf_bench_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# kayıt defteri
# ---------------------------------------------------------------------------

def test_append_run_writes_jsonl_with_metadata(tmp_path):
    history = tmp_path / "perf" / "history.jsonl"

    perf_history.append_run({"a_ms": 100.0}, history)
    perf_history.append_run({"a_ms": {"value": 120.0, "unit": "ms"}}, history)

    assert history.is_file()
    lines = history.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    record = json.loads(lines[0])
    assert record["schema"] == perf_history.SCHEMA_VERSION
    assert record["timestamp"]
    assert "git_sha" in record
    assert record["machine"]["python"]
    # Çıplak sayı da tam metriğe normalize edilir.
    assert record["metrics"]["a_ms"] == {
        "value": 100.0, "unit": "ms", "direction": perf_history.LOWER_BETTER,
    }


def test_load_runs_skips_corrupt_lines_and_honors_limit(tmp_path):
    history = tmp_path / "history.jsonl"
    for value in (1.0, 2.0, 3.0):
        perf_history.append_run({"m_ms": value}, history, collect_git=False)
    with open(history, "a", encoding="utf-8") as f:
        f.write("{bozuk json\n\n")

    assert len(perf_history.load_runs(history)) == 3
    last_two = perf_history.load_runs(history, limit=2)
    assert [r["metrics"]["m_ms"]["value"] for r in last_two] == [2.0, 3.0]
    assert perf_history.load_runs(tmp_path / "yok.jsonl") == []


def test_default_history_path_follows_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPY_PERF_HOME", str(tmp_path))
    assert perf_history.default_history_path() == tmp_path / "perf" / "history.jsonl"

    monkeypatch.delenv("ENTROPY_PERF_HOME", raising=False)
    assert perf_history.default_history_path().parts[-2:] == ("perf", "history.jsonl")
    assert perf_history.default_history_path(tmp_path / "x") == tmp_path / "x" / "perf" / "history.jsonl"


# ---------------------------------------------------------------------------
# trend / regresyon
# ---------------------------------------------------------------------------

def test_percent_change_edges():
    assert perf_history.percent_change(100.0, 120.0) == pytest.approx(20.0)
    assert perf_history.percent_change(100.0, 50.0) == pytest.approx(-50.0)
    assert perf_history.percent_change(0.0, 5.0) is None
    assert perf_history.percent_change(None, 5.0) is None
    assert perf_history.percent_change(5.0, None) is None


def test_is_regression_only_for_lower_better_over_threshold():
    assert perf_history.is_regression(perf_history.LOWER_BETTER, 25.0) is True
    assert perf_history.is_regression(perf_history.LOWER_BETTER, 19.9) is False
    assert perf_history.is_regression(perf_history.NEUTRAL, 500.0) is False
    assert perf_history.is_regression(perf_history.LOWER_BETTER, None) is False


def test_trend_markdown_flags_regression_but_not_counts(tmp_path):
    history = tmp_path / "history.jsonl"
    perf_history.append_run(
        {
            "slow_ms": {"value": 100.0},
            "stable_ms": {"value": 100.0},
            "graph_nodes": {"value": 500.0, "unit": "count", "direction": perf_history.NEUTRAL},
        },
        history, collect_git=False,
    )
    perf_history.append_run(
        {
            "slow_ms": {"value": 160.0},          # +%60 → kötüleşme
            "stable_ms": {"value": 105.0},        # +%5  → eşiğin altında
            "graph_nodes": {"value": 900.0, "unit": "count", "direction": perf_history.NEUTRAL},
        },
        history, collect_git=False,
    )

    table = perf_history.render_trend_markdown(perf_history.load_runs(history))

    assert "| slow_ms |" in table and "| stable_ms |" in table and "| graph_nodes |" in table
    assert "+60,0%" in table or "+60.0%" in table
    assert "KOTULESME" in table
    assert "Eşiği aşan kötüleşmeler: slow_ms." in table
    # Sayım metriği %80 artmış olsa da kötüleşme sayılmaz.
    slow_row = [ln for ln in table.splitlines() if ln.startswith("| slow_ms ")][0]
    nodes_row = [ln for ln in table.splitlines() if ln.startswith("| graph_nodes ")][0]
    assert "KOTULESME" in slow_row
    assert "KOTULESME" not in nodes_row and "notr" in nodes_row


def test_trend_markdown_handles_empty_and_single_run(tmp_path):
    assert "yok" in perf_history.render_trend_markdown([])
    history = tmp_path / "history.jsonl"
    perf_history.append_run({"m_ms": 10.0}, history, collect_git=False)
    table = perf_history.render_trend_markdown(perf_history.load_runs(history))
    assert "| m_ms |" in table
    assert "Eşiği aşan kötüleşme yok." in table


def test_trend_tolerates_error_metrics(tmp_path):
    history = tmp_path / "history.jsonl"
    perf_history.append_run({"m_ms": {"value": None, "error": "ImportError: yok"}}, history, collect_git=False)
    table = perf_history.render_trend_markdown(perf_history.load_runs(history))
    assert "HATA" in table


# ---------------------------------------------------------------------------
# düzeneğin uçtan uca koşusu (tmp kasa, tmp geçmiş)
# ---------------------------------------------------------------------------

def test_run_bench_writes_to_tmp_history_and_renders_trend(perf_bench, tmp_path):
    """
    Gerçek ölçüm yolu: en ucuz grup (playbook) tmp kasa üzerinde koşturulur,
    sonuç tmp JSONL'a yazılır ve trend üretilir. Gerçek kasa ve gerçek
    .entropy/perf dosyasına dokunulmaz.
    """
    vault = tmp_path / "vault"
    (vault / "Entropy" / "Skills").mkdir(parents=True)
    history = tmp_path / "perf" / "history.jsonl"
    real_history = perf_history.default_history_path()
    real_before = real_history.stat().st_mtime if real_history.exists() else None

    metrics = perf_bench.run_bench(repeat=2, groups=["playbook"], vault_path=vault, verbose=False)

    assert "playbook_status_ms" in metrics
    m = metrics["playbook_status_ms"]
    assert m.get("error") is None, m.get("error")
    assert m["value"] is not None and m["value"] >= 0.0
    assert len(m["samples"]) == 2
    assert metrics["playbook_source_reports"]["direction"] == perf_history.NEUTRAL

    perf_history.append_run(metrics, history, extra={"repeat": 2, "groups": ["playbook"]})
    runs = perf_history.load_runs(history)
    assert len(runs) == 1
    assert runs[0]["extra"]["groups"] == ["playbook"]

    table = perf_history.render_trend_markdown(runs)
    assert "| playbook_status_ms |" in table

    # Tmp kasa okundu; gerçek geçmiş dosyası değişmedi.
    after = real_history.stat().st_mtime if real_history.exists() else None
    assert after == real_before
    assert not list(vault.rglob("PLAYBOOK.md"))


def test_run_bench_unknown_group_is_ignored(perf_bench):
    assert perf_bench.run_bench(repeat=1, groups=["olmayan-grup"], verbose=False) == {}


def test_failing_measurement_is_recorded_not_raised(perf_bench, monkeypatch):
    """Bir ölçüm patlarsa koşu düşmez; hata metrik olarak kaydedilir."""
    def boom(*_a, **_k):
        raise RuntimeError("ölçüm patladı")

    monkeypatch.setattr(perf_bench, "bench_playbook", boom)
    metrics = perf_bench.run_bench(repeat=1, groups=["playbook"], verbose=False)
    assert "playbook_group_error" in metrics
    assert "ölçüm patladı" in metrics["playbook_group_error"]["error"]


def test_report_mode_does_not_measure(perf_bench, tmp_path, capsys, monkeypatch):
    """--report yalnızca okur: hiçbir ölçüm fonksiyonu çağrılmaz."""
    history = tmp_path / "history.jsonl"
    perf_history.append_run({"m_ms": 12.0}, history, collect_git=False)

    def fail(*_a, **_k):
        raise AssertionError("--report ölçüm yapmamalı")

    monkeypatch.setattr(perf_bench, "run_bench", fail)
    rc = perf_bench.main(["--report", "5", "--history", str(history)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "| m_ms |" in out
    assert "Performans trendi" in out
