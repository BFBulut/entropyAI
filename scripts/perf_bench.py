"""
Entropy AI performans düzeneği — tekrarlanabilir mikro ölçümler ve gelişim trendi.

Kullanım
--------
  python scripts/perf_bench.py                     # tüm ölçümler, .entropy/perf/history.jsonl'a ekler
  python scripts/perf_bench.py --only imports      # yalnız seçili grup(lar)
  python scripts/perf_bench.py --repeat 5          # tekrar sayısı (medyan alınır)
  python scripts/perf_bench.py --no-write          # ölç, geçmişe yazma
  python scripts/perf_bench.py --report            # ölçme, son koşuların trendini bas
  python scripts/perf_bench.py --report 5          # son 5 koşu

Ölçüm ilkeleri
--------------
* Her ölçüm varsayılan 3 tekrar, **medyan** raporlanır (ortalama değil: tek bir
  takılma medyanı bozmaz).
* İçe aktarma süreleri ayrı bir alt süreçte ölçülür; aynı süreçte ikinci kez
  import etmek sys.modules önbelleğinden döner ve gerçek maliyeti gizler.
* Ölçüm gecikme (ms) ve miktar (adet/token) olarak ikiye ayrılır. Miktarlar
  "notr" yönlüdür: artmaları kötüleşme sayılmaz.
* Hiçbir ölçüm kasaya veya veritabanına yazmaz; yalnızca okuma yapılır. Tek
  yazma, koşu sonucunun .entropy/perf/history.jsonl'a eklenmesidir.

Gruplar: imports, cognitive, context, graph, routing, playbook
"""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from entropy.core import perf_history  # noqa: E402
from entropy.core.perf_history import LOWER_BETTER, NEUTRAL  # noqa: E402

DEFAULT_REPEAT = 3

GROUPS = ("imports", "cognitive", "context", "graph", "routing", "playbook")

HEAVY_MODULES = {
    "import_zen_mode_ms": "entropy.ui.modes.zen_mode",
    "import_cognitive_memory_ms": "entropy.memory.supabase.cognitive_memory",
    "import_knowledge_graph_ms": "entropy.ui.widgets.knowledge_graph",
}

RECALL_QUERIES = [
    "finansal denetim raporunda hangi oranlara bakılır",
    "bilgi grafiği düğüm fiziği nasıl çalışıyor",
    "otonom görev zamanlayıcı hataları",
    "obsidian kasası bellek senkronizasyonu",
    "token bütçesi ve bağlam kurucu",
]

CONTEXT_CASES = [
    ("financial_auditor", "financial-auditor", "ENJSA bilançosunda borçluluk ve nakit akışı riski"),
    ("media_agency", "media-agency-soldier", "canivopets için içerik takvimi ve büyüme önerisi"),
    ("no_skill", None, "entropy uygulamasının performansı neden düştü"),
]

ROUTING_PROMPTS = [
    "ENJSA'nın son bilançosunu denetle",
    "bu şirketin nakit akışını analiz et",
    "canivopets sitesini incele ve büyüme önerisi çıkar",
    "instagram için reklam metni yaz",
    "bunu slayt yap",
    "sunum hazırlar mısın",
    "şu pdf dosyasını özetle",
    "yeni bir yetenek oluştur",
    "kod tabanında hata ayıkla ve testleri koş",
    "bugün hava nasıl",
]

PLAYBOOK_SKILL = "financial-auditor"


# --------------------------------------------------------------------------
# yardımcılar
# --------------------------------------------------------------------------

def _median(values: List[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return float(statistics.median(clean))


def _metric(
    values: List[float],
    *,
    unit: str = "ms",
    direction: str = LOWER_BETTER,
    note: str = "",
) -> Dict[str, Any]:
    return {
        "value": _median(values),
        "unit": unit,
        "direction": direction,
        "samples": [round(float(v), 3) for v in values if v is not None],
        "note": note,
    }


def _error_metric(exc: BaseException, *, unit: str = "ms", direction: str = LOWER_BETTER) -> Dict[str, Any]:
    return {
        "value": None,
        "unit": unit,
        "direction": direction,
        "samples": [],
        "error": f"{type(exc).__name__}: {exc}",
    }


def _time_ms(fn: Callable[[], Any]) -> tuple:
    """Fonksiyonu çalıştırır; (geçen_ms, sonuç) döndürür."""
    t0 = time.perf_counter()
    result = fn()
    return (time.perf_counter() - t0) * 1000.0, result


def _repeat_ms(fn: Callable[[], Any], repeat: int) -> tuple:
    samples: List[float] = []
    last = None
    for _ in range(max(1, repeat)):
        elapsed, last = _time_ms(fn)
        samples.append(elapsed)
    return samples, last


def _guard(metrics: Dict[str, Any], name: str, producer: Callable[[], Dict[str, Any]], **fallback) -> None:
    """Bir ölçüm patlarsa tüm koşuyu düşürmez; hata metriğe yazılır."""
    try:
        result = producer()
        if isinstance(result, dict) and "value" in result:
            metrics[name] = result
        elif isinstance(result, dict):
            metrics.update(result)
    except Exception as exc:  # ölçüm hatası ölçümün kendisidir, yutulmaz
        print(f"  ! {name} ölçülemedi: {type(exc).__name__}: {exc}", file=sys.stderr)
        if os.environ.get("ENTROPY_PERF_TRACE"):
            traceback.print_exc()
        metrics[name] = _error_metric(exc, **fallback)


# --------------------------------------------------------------------------
# 1) içe aktarma süreleri (alt süreçte, gerçekten soğuk)
# --------------------------------------------------------------------------

def _subprocess_import_ms(module: str) -> Optional[float]:
    code = (
        "import time, importlib\n"
        "t = time.perf_counter()\n"
        f"importlib.import_module({module!r})\n"
        "print(round((time.perf_counter() - t) * 1000.0, 3))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip()[-400:] or f"exit {proc.returncode}")
    return float((proc.stdout or "").strip().splitlines()[-1])


def bench_imports(repeat: int) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    for name, module in HEAVY_MODULES.items():
        def producer(module=module):
            samples = [_subprocess_import_ms(module) for _ in range(max(1, repeat))]
            return _metric(samples, note=f"alt süreç, {module}")
        _guard(metrics, name, producer)
    return metrics


# --------------------------------------------------------------------------
# 2) bilişsel bellek: soğuk açılış + hibrit geri çağırma
# --------------------------------------------------------------------------

def bench_cognitive(repeat: int, db_path: Optional[Path] = None) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

    def _new():
        return CognitiveMemorySystem(db_path) if db_path else CognitiveMemorySystem()

    def cold_open():
        samples, mem = _repeat_ms(_new, repeat)
        metrics["_mem"] = mem
        return _metric(samples, note="CognitiveMemorySystem() kurucu (şema + ego tohumu)")

    _guard(metrics, "cognitive_cold_open_ms", cold_open)
    mem = metrics.pop("_mem", None)
    if mem is None:
        try:
            mem = _new()
        except Exception as exc:
            metrics["hybrid_recall_5q_ms"] = _error_metric(exc)
            return metrics

    # Gömme motoru ilk çağrıda yüklenir; bu tek seferlik maliyet ayrı ölçülür ki
    # sorgu gecikmesini şişirmesin.
    def engine_warmup():
        elapsed, _ = _time_ms(lambda: mem.hybrid_recall(RECALL_QUERIES[0], top_k=5))
        return _metric([elapsed], note="ilk çağrı: gömme motoru yüklenmesi dahil, tek ölçüm")

    _guard(metrics, "recall_first_call_ms", engine_warmup)

    def recall_batch():
        def one_pass():
            total = 0
            for q in RECALL_QUERIES:
                total += len(mem.hybrid_recall(q, top_k=5))
            return total
        samples, hits = _repeat_ms(one_pass, repeat)
        metrics["recall_hits"] = {
            "value": float(hits or 0), "unit": "count", "direction": NEUTRAL,
            "note": f"{len(RECALL_QUERIES)} sorguda dönen toplam düğüm",
        }
        per_q = _median(samples)
        if per_q is not None:
            metrics["hybrid_recall_per_query_ms"] = {
                "value": per_q / len(RECALL_QUERIES), "unit": "ms",
                "direction": LOWER_BETTER, "note": "5 sorgu medyanının sorgu başına payı",
            }
        return _metric(samples, note=f"{len(RECALL_QUERIES)} sorgu, motor ısınmış")

    _guard(metrics, "hybrid_recall_5q_ms", recall_batch)

    def node_count():
        n = len(mem.get_all_nodes())
        return {"value": float(n), "unit": "count", "direction": NEUTRAL,
                "note": "kasadaki bilişsel düğüm sayısı (ölçek bağlamı)"}

    _guard(metrics, "cognitive_node_count", node_count, unit="count", direction=NEUTRAL)
    return metrics


# --------------------------------------------------------------------------
# 3) bağlam kurucu: süre + token toplamı
# --------------------------------------------------------------------------

def bench_context(repeat: int, project_dir: Optional[Path] = None) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    from entropy.memory.context_builder import CognitiveContextBuilder

    builder = CognitiveContextBuilder()
    proj = Path(project_dir) if project_dir else REPO_ROOT

    for label, skill, query in CONTEXT_CASES:
        def producer(label=label, skill=skill, query=query):
            def one():
                return builder.build(query, skill_name=skill, token_budget=4000, project_dir=proj)
            samples, ctx = _repeat_ms(one, repeat)
            metrics[f"context_tokens_{label}"] = {
                "value": float(getattr(ctx, "tokens", 0)), "unit": "token",
                "direction": NEUTRAL,
                "note": f"{len(getattr(ctx, 'sections', []))} bölüm / bütçe 4000",
            }
            return _metric(samples, note=f"skill={skill or 'yok'}")
        _guard(metrics, f"context_build_ms_{label}", producer)
    return metrics


# --------------------------------------------------------------------------
# 4) bilgi grafiği: veri kurma süresi + düğüm/kenar sayısı
# --------------------------------------------------------------------------

class _GraphHost:
    """
    build_unified_graph() yalnızca beş özniteliğe dokunur; Qt widget'ı kurmadan
    da çalışır. WebEngine kurulumu ölçüme karışmasın diye veri kurma bu iskelet
    üzerinde ölçülür (grafiğin çizimi değil, verinin üretimi ölçülüyor).
    """

    def __init__(self, project_dir: Path):
        from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
        from entropy.mcp.manager import MCPManager
        from entropy.skills.manager import SkillManager

        self.active_project_dir = Path(project_dir)
        self.vault_manager = ObsidianVaultManager()
        self.cognitive_memory = CognitiveMemorySystem()
        self.skill_manager = SkillManager(project_dir=self.active_project_dir)
        self.mcp_manager = MCPManager()


def bench_graph(repeat: int, project_dir: Optional[Path] = None) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}

    def producer():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget

        host = _GraphHost(Path(project_dir) if project_dir else REPO_ROOT)
        build = KnowledgeGraphWidget.build_unified_graph

        samples, data = _repeat_ms(lambda: build(host), repeat)
        data = data or {}
        metrics["graph_nodes"] = {
            "value": float(len(data.get("nodes", []))), "unit": "count",
            "direction": NEUTRAL, "note": "build_unified_graph düğüm sayısı",
        }
        metrics["graph_links"] = {
            "value": float(len(data.get("links", []))), "unit": "count",
            "direction": NEUTRAL, "note": "build_unified_graph kenar sayısı",
        }
        return _metric(samples, note="widget kurmadan, yalnız veri üretimi")

    _guard(metrics, "graph_build_ms", producer)
    return metrics


# --------------------------------------------------------------------------
# 5) yetenek yönlendirme gecikmesi
# --------------------------------------------------------------------------

def bench_routing(repeat: int, project_dir: Optional[Path] = None) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    from entropy.skills.manager import SkillManager

    manager = SkillManager(project_dir=Path(project_dir) if project_dir else REPO_ROOT)

    def producer():
        # İlk çağrı yetenek gömmelerini kurar; ısınma ayrı ölçülür.
        warm, _ = _time_ms(lambda: manager.auto_detect_skill_for_prompt(ROUTING_PROMPTS[0]))
        metrics["routing_first_call_ms"] = {
            "value": warm, "unit": "ms", "direction": LOWER_BETTER,
            "note": "ilk çağrı: yetenek gömmelerinin kurulması dahil, tek ölçüm",
        }

        def one_pass():
            hits = 0
            for prompt in ROUTING_PROMPTS:
                if manager.auto_detect_skill_for_prompt(prompt) is not None:
                    hits += 1
            return hits

        samples, hits = _repeat_ms(one_pass, repeat)
        metrics["routing_matched"] = {
            "value": float(hits or 0), "unit": "count", "direction": NEUTRAL,
            "note": f"{len(ROUTING_PROMPTS)} promptun kaçı bir yeteneğe düştü",
        }
        per_p = _median(samples)
        if per_p is not None:
            metrics["routing_per_prompt_ms"] = {
                "value": per_p / len(ROUTING_PROMPTS), "unit": "ms",
                "direction": LOWER_BETTER, "note": "10 prompt medyanının prompt başına payı",
            }
        return _metric(samples, note=f"{len(ROUTING_PROMPTS)} prompt, ısınmış")

    _guard(metrics, "routing_10_prompts_ms", producer)
    return metrics


# --------------------------------------------------------------------------
# 6) PlaybookStore.status
# --------------------------------------------------------------------------

def bench_playbook(
    repeat: int,
    skill: str = PLAYBOOK_SKILL,
    vault_path: Optional[Path] = None,
    store: Any = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    from entropy.memory.playbook import PlaybookStore, SkillReportIndex

    if store is None:
        if vault_path is not None:
            # Testler gerçek kasaya değil, kendi tmp kasalarına bakar.
            store = PlaybookStore(
                vault_path=Path(vault_path),
                index=SkillReportIndex(index_path=Path(vault_path) / "skill_report_index.json"),
            )
        else:
            store = PlaybookStore()

    def producer():
        samples, status = _repeat_ms(lambda: store.status(skill), repeat)
        status = status or {}
        metrics["playbook_source_reports"] = {
            "value": float(status.get("sources", status.get("source_count", 0)) or 0),
            "unit": "count", "direction": NEUTRAL,
            "note": f"{skill} için taranan kaynak rapor sayısı",
        }
        return _metric(samples, note=f"PlaybookStore.status('{skill}')")

    _guard(metrics, "playbook_status_ms", producer)
    return metrics


# --------------------------------------------------------------------------
# koşu
# --------------------------------------------------------------------------

def run_bench(
    repeat: int = DEFAULT_REPEAT,
    groups: Optional[List[str]] = None,
    project_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    vault_path: Optional[Path] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Seçili grupları ölçer ve metrik sözlüğü döndürür (geçmişe yazmaz)."""
    selected = [g for g in (groups or GROUPS) if g in GROUPS]
    metrics: Dict[str, Any] = {}
    runners: Dict[str, Callable[[], Dict[str, Any]]] = {
        "imports": lambda: bench_imports(repeat),
        "cognitive": lambda: bench_cognitive(repeat, db_path=db_path),
        "context": lambda: bench_context(repeat, project_dir=project_dir),
        "graph": lambda: bench_graph(repeat, project_dir=project_dir),
        "routing": lambda: bench_routing(repeat, project_dir=project_dir),
        "playbook": lambda: bench_playbook(repeat, vault_path=vault_path),
    }
    for group in selected:
        if verbose:
            print(f"[perf] {group} ...", flush=True)
        t0 = time.perf_counter()
        try:
            metrics.update(runners[group]())
        except Exception as exc:
            print(f"  ! {group} grubu düştü: {type(exc).__name__}: {exc}", file=sys.stderr)
            if os.environ.get("ENTROPY_PERF_TRACE"):
                traceback.print_exc()
            metrics[f"{group}_group_error"] = _error_metric(exc)
        if verbose:
            print(f"[perf] {group} bitti ({(time.perf_counter() - t0):.1f} sn)", flush=True)
    return metrics


def render_current(metrics: Dict[str, Any]) -> str:
    """Tek koşunun okunabilir tablosu."""
    lines = ["| Metrik | Değer | Birim | Örnekler |", "|---|---|---|---|"]
    for name, raw in metrics.items():
        m = perf_history.normalize_metric(raw)
        if m.get("error"):
            lines.append(f"| {name} | HATA | {m.get('unit','')} | {m['error'][:80]} |")
            continue
        value_txt = perf_history.format_metric(m)
        samples = "; ".join(perf_history.format_number(s) for s in (m.get("samples") or [])[:5])
        lines.append(f"| {name} | {value_txt} | {m.get('unit','')} | {samples} |")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Entropy AI performans düzeneği")
    parser.add_argument("--report", nargs="?", const=10, type=int, default=None,
                        help="Ölçme; son N koşunun trend tablosunu bas (varsayılan 10)")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help="Ölçüm başına tekrar (medyan alınır)")
    parser.add_argument("--only", type=str, default="", help=f"Virgülle grup seçimi: {', '.join(GROUPS)}")
    parser.add_argument("--history", type=str, default="", help="history.jsonl yolu (varsayılan .entropy/perf/history.jsonl)")
    parser.add_argument("--no-write", action="store_true", help="Sonucu geçmişe yazma")
    parser.add_argument("--threshold", type=float, default=perf_history.REGRESSION_THRESHOLD_PCT,
                        help="Kötüleşme eşiği (%%)")
    parser.add_argument("--note", type=str, default="", help="Koşuya iliştirilecek serbest not")
    args = parser.parse_args(argv)

    history_path = Path(args.history) if args.history else perf_history.default_history_path()

    if args.report is not None:
        runs = perf_history.load_runs(history_path)
        print(f"# Performans trendi\n\nKaynak: {history_path}\n")
        print(perf_history.render_trend_markdown(runs, threshold=args.threshold, limit=args.report))
        return 0

    groups = [g.strip() for g in args.only.split(",") if g.strip()] or None
    t0 = time.perf_counter()
    metrics = run_bench(repeat=args.repeat, groups=groups)
    total = time.perf_counter() - t0

    print("\n# Koşu sonucu\n")
    print(render_current(metrics))
    print(f"\nToplam ölçüm süresi: {total:.1f} sn, tekrar: {args.repeat}")

    if not args.no_write:
        extra = {"repeat": args.repeat, "groups": groups or list(GROUPS),
                 "wall_seconds": round(total, 2)}
        if args.note:
            extra["note"] = args.note
        path = perf_history.append_run(metrics, history_path, extra=extra)
        print(f"Geçmişe eklendi: {path}")
        runs = perf_history.load_runs(path)
        print("\n# Trend\n")
        print(perf_history.render_trend_markdown(runs, threshold=args.threshold, limit=10))
    else:
        print("(--no-write: geçmişe yazılmadı)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
