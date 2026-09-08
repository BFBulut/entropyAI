"""
Performans ölçüm geçmişi: JSONL kayıt defteri ve trend tablosu.

Neden ayrı bir modül
--------------------
Ölçümü yapan betik (scripts/perf_bench.py) ile ölçümü saklayan/karşılaştıran
mantık ayrı tutulur; böylece kayıt biçimi ve trend hesabı testlerden doğrudan
çağrılabilir, gerçek `.entropy` dizinine yazmadan tmp dizinde doğrulanabilir.

Kayıt biçimi (her satır bir koşu, JSONL)
---------------------------------------
{
  "schema": 1,
  "timestamp": "2026-09-08T01:02:03+00:00",
  "git_sha": "8d7900b",
  "git_dirty": true,
  "machine": {"os": "...", "python": "...", "cpu_count": 16, ...},
  "metrics": {
      "import_zen_mode_ms": {"value": 812.4, "unit": "ms", "direction": "lower_better",
                             "samples": [...], "note": "..."},
      ...
  }
}

Metrik yönü
-----------
"lower_better"  → artış kötüleşmedir (gecikmeler).
"neutral"       → sayım/miktar (düğüm sayısı, token toplamı); değişim raporlanır
                  ama kötüleşme olarak işaretlenmez.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1

# Bu oranı aşan kötüleşme raporda işaretlenir.
REGRESSION_THRESHOLD_PCT = 20.0

LOWER_BETTER = "lower_better"
NEUTRAL = "neutral"


def repo_root() -> Path:
    """src/entropy/core/perf_history.py → depo kökü."""
    return Path(__file__).resolve().parents[3]


def default_history_path(base_dir: Optional[Path] = None) -> Path:
    """
    Geçmiş dosyasının yolu.

    Öncelik: açık `base_dir` > ENTROPY_PERF_HOME > <depo kökü>/.entropy
    Testler ENTROPY_PERF_HOME ile tmp dizine yönlendirir; gerçek `.entropy`
    yalnızca gerçek koşuda yazılır.
    """
    if base_dir is not None:
        base = Path(base_dir)
    else:
        env = os.environ.get("ENTROPY_PERF_HOME")
        base = Path(env).expanduser() if env else repo_root() / ".entropy"
    return base / "perf" / "history.jsonl"


def git_sha(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Kısa git sha ve çalışma ağacının kirli olup olmadığı. Git yoksa boş döner."""
    cwd = Path(cwd) if cwd else repo_root()
    info: Dict[str, Any] = {"sha": "", "dirty": None}
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd), capture_output=True, text=True, timeout=20,
        )
        if sha.returncode == 0:
            info["sha"] = sha.stdout.strip()
        st = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd), capture_output=True, text=True, timeout=30,
        )
        if st.returncode == 0:
            info["dirty"] = bool(st.stdout.strip())
    except Exception:
        pass
    return info


def machine_info() -> Dict[str, Any]:
    """Ölçümün karşılaştırılabilir olması için makine/yorumlayıcı künyesi."""
    return {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "hostname": platform.node(),
    }


def normalize_metric(raw: Any) -> Dict[str, Any]:
    """Ham ölçümü tek biçime getirir: sayı da sözlük de kabul edilir."""
    if isinstance(raw, dict):
        metric = dict(raw)
    else:
        metric = {"value": raw}
    metric.setdefault("unit", "ms")
    metric.setdefault("direction", LOWER_BETTER)
    if metric.get("value") is not None:
        try:
            metric["value"] = float(metric["value"])
        except (TypeError, ValueError):
            metric["value"] = None
    return metric


def build_record(
    metrics: Dict[str, Any],
    *,
    extra: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
    collect_git: bool = True,
) -> Dict[str, Any]:
    git = git_sha(cwd) if collect_git else {"sha": "", "dirty": None}
    record: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git.get("sha", ""),
        "git_dirty": git.get("dirty"),
        "machine": machine_info(),
        "metrics": {k: normalize_metric(v) for k, v in (metrics or {}).items()},
    }
    if extra:
        record["extra"] = extra
    return record


def append_run(
    metrics: Dict[str, Any],
    path: Optional[Path] = None,
    *,
    extra: Optional[Dict[str, Any]] = None,
    collect_git: bool = True,
) -> Path:
    """Koşuyu JSONL'a ekler ve dosya yolunu döndürür."""
    target = Path(path) if path else default_history_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    record = build_record(metrics, extra=extra, collect_git=collect_git)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target


def load_runs(path: Optional[Path] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Geçmişi eskiden yeniye okur; bozuk satırlar sessizce atlanır."""
    target = Path(path) if path else default_history_path()
    if not target.exists():
        return []
    runs: List[Dict[str, Any]] = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None and limit > 0:
        runs = runs[-limit:]
    return runs


def percent_change(previous: Optional[float], current: Optional[float]) -> Optional[float]:
    """Önceki koşuya göre yüzde değişim. Önceki 0 veya eksikse hesaplanamaz."""
    if previous is None or current is None:
        return None
    try:
        if previous == 0:
            return None
        return (current - previous) / previous * 100.0
    except (TypeError, ZeroDivisionError):
        return None


def is_regression(direction: str, change_pct: Optional[float], threshold: float = REGRESSION_THRESHOLD_PCT) -> bool:
    """Yalnızca 'düşük iyidir' metriklerinde, eşiği aşan artış kötüleşmedir."""
    if change_pct is None or direction != LOWER_BETTER:
        return False
    return change_pct > threshold


_TR_NUM = str.maketrans({",": ".", ".": ","})


def format_number(value: Optional[float], decimals: int = 1) -> str:
    """Türkçe sayı biçimi: binlik nokta, ondalık virgül (1.880,3)."""
    if value is None:
        return "-"
    return f"{value:,.{decimals}f}".translate(_TR_NUM)


def format_metric(metric: Optional[Dict[str, Any]]) -> str:
    if not metric:
        return "-"
    if metric.get("error"):
        return "HATA"
    value = metric.get("value")
    if value is None:
        return "-"
    decimals = 0 if metric.get("unit") in ("count", "token", "tokens") else 1
    return format_number(value, decimals)


# Geriye dönük ad.
_fmt_value = format_metric


def _run_label(run: Dict[str, Any]) -> str:
    ts = str(run.get("timestamp", ""))[:16].replace("T", " ")
    sha = run.get("git_sha") or "?"
    dirty = "*" if run.get("git_dirty") else ""
    return f"{ts} ({sha}{dirty})"


def render_trend_markdown(
    runs: List[Dict[str, Any]],
    *,
    threshold: float = REGRESSION_THRESHOLD_PCT,
    limit: Optional[int] = None,
) -> str:
    """
    Son N koşunun trendini markdown tablo olarak üretir.

    Sütunlar: metrik, birim, her koşunun değeri, son koşunun bir öncekine göre
    yüzde değişimi ve eşiği aşan kötüleşme işareti.
    """
    if not runs:
        return "Kayıtlı performans koşusu yok."

    window = runs[-limit:] if (limit and limit > 0) else runs

    # Metrik sırası: en yeni koşudaki sıra korunur, eski koşulardaki ekler sona eklenir.
    names: List[str] = []
    for run in reversed(window):
        for name in (run.get("metrics") or {}):
            if name not in names:
                names.append(name)

    headers = ["Metrik", "Birim"] + [_run_label(r) for r in window] + ["Δ% (son vs önceki)", "Durum"]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]

    regressions: List[str] = []
    for name in names:
        metrics_by_run = [(run.get("metrics") or {}).get(name) for run in window]
        latest = next((m for m in reversed(metrics_by_run) if m), None)
        unit = (latest or {}).get("unit", "")
        direction = (latest or {}).get("direction", LOWER_BETTER)

        cur = (metrics_by_run[-1] or {}).get("value") if metrics_by_run else None
        prev = (metrics_by_run[-2] or {}).get("value") if len(metrics_by_run) > 1 else None
        change = percent_change(prev, cur)
        regressed = is_regression(direction, change, threshold)
        if regressed:
            regressions.append(name)

        change_txt = "-" if change is None else f"{'+' if change >= 0 else '-'}{format_number(abs(change))}%"
        if regressed:
            status = f"KOTULESME (>%{threshold:.0f})"
        elif direction == NEUTRAL:
            status = "notr"
        elif change is not None and change < -threshold:
            status = "iyilesme"
        else:
            status = "ok"

        row = [name, unit] + [_fmt_value(m) for m in metrics_by_run] + [change_txt, status]
        lines.append("| " + " | ".join(row) + " |")

    table = "\n".join(lines)
    footer = (
        f"\n\nToplam koşu: {len(runs)} (gösterilen: {len(window)}). "
        f"Kötüleşme eşiği: %{threshold:.0f}."
    )
    if regressions:
        footer += "\n\nEşiği aşan kötüleşmeler: " + ", ".join(regressions) + "."
    else:
        footer += "\n\nEşiği aşan kötüleşme yok."
    return table + footer
