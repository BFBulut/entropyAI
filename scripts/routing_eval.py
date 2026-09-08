"""
Yetenek yönlendirme doğruluk düzeneği — ölçülebilir karar kalitesi.

Neden
-----
`SkillManager.auto_detect_skill_for_prompt` eşikleri (anlamsal taban/kazanç/tavan,
gönderme önceliği, karar eşiği) bugüne kadar birkaç örnek üzerinden elle
ayarlandı. Bu betik, gerçek kullanım verisinden türetilmiş sabit bir küme
(tests/data/routing_eval.jsonl) üzerinde precision/recall/yanlış pozitif oranını
ve karışıklık tablosunu üretir; eşik değişiklikleri artık iddia değil ölçümle
savunulur.

Kullanım
--------
  python scripts/routing_eval.py                 # ölç, .entropy/perf/routing_eval.jsonl'a ekle
  python scripts/routing_eval.py --no-write      # yalnız bas
  python scripts/routing_eval.py --real-skills   # kullanıcının gerçek yetenek kataloğuyla
  python scripts/routing_eval.py --show-errors   # yanlış kararları tek tek listele
  python scripts/routing_eval.py --set SEMANTIC_FLOOR=0.34 --set SEMANTIC_GAIN=8
  python scripts/routing_eval.py --report 5      # ölçme, son koşuların trendini bas

Küme
----
Örnekler üç gerçek kaynaktan çıkarıldı: .entropy/chat_history.json (kullanıcı
mesajları), ~/.entropy/tasks_ledger.db görev adları ve Obsidian kasasındaki rapor
başlıkları. Kişisel veri içermez. `ambiguous: true` işaretli örnekler (iki yetenek
de savunulabilir) ana metrikte sayılır ama ayrıca dökülür; eşik ayarı yaparken
belirsizler üzerinden kazanç iddia etmemek için.

Varsayılan kip yalıtılmış katalogdur (depo kökündeki `skills/`), böylece sonuç
makineden makineye aynıdır. `--real-skills` gerçek keşif yolunu (proje + kullanıcı
+ eklenti yetenekleri) kullanır ve prodüksiyondaki yanlış pozitifleri gösterir.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from entropy.core import perf_history  # noqa: E402
from entropy.core.perf_history import LOWER_BETTER, NEUTRAL  # noqa: E402

DATASET = REPO_ROOT / "tests" / "data" / "routing_eval.jsonl"
HISTORY = REPO_ROOT / ".entropy" / "perf" / "routing_eval.jsonl"

# Eşik adı → SkillManager sınıf özniteliği (--set ile geçici olarak değiştirilir).
TUNABLES = {
    "SEMANTIC_FLOOR": "_SEMANTIC_FLOOR",
    "SEMANTIC_GAIN": "_SEMANTIC_GAIN",
    "SEMANTIC_CAP": "_SEMANTIC_CAP",
    "SEMANTIC_MAX_DOMINANT_RATIO": "_SEMANTIC_MAX_DOMINANT_RATIO",
    "SEMANTIC_MIN_TOKENS": "_SEMANTIC_MIN_TOKENS",
    "ANAPHORA_PRIOR": "_ANAPHORA_PRIOR",
    "DECISION_THRESHOLD": "_DECISION_THRESHOLD",
}

NONE_LABEL = "(yok)"


def load_dataset(path: Path = DATASET) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            rows.append(json.loads(line))
    return rows


def build_manager(real_skills: bool):
    """Değerlendirme için yetenek yöneticisi; durum dosyasına hiçbir şey yazmaz."""
    from entropy.skills.manager import SkillManager

    if real_skills:
        sm = SkillManager(project_dir=REPO_ROOT)
    else:
        sm = SkillManager(root_skills_dir=REPO_ROOT / "skills")
    # Kullanıcının açık/kapalı tercihleri ölçümü kirletmesin: katalogdaki her
    # yetenek etkin sayılır. Yalnızca bellekteki önbellek değişir (_save_state yok).
    for s in sm.list_skills():
        sm._enabled_cache[s.name] = True
    return sm


def predict(sm, row: Dict[str, Any]) -> Tuple[Optional[str], Optional[float]]:
    """Karar ve güven puanı tek sıralamadan; iki ayrı çağrı ölçümü ikiye katlardı."""
    try:
        res, conf = sm.score_skill_for_prompt(
            row["prompt"], last_skill=row.get("last_skill"), history=row.get("history")
        )
    except AttributeError:  # eski sürüm: yalnızca karar
        res = sm.auto_detect_skill_for_prompt(
            row["prompt"], last_skill=row.get("last_skill"), history=row.get("history")
        )
        conf = None
    return getattr(res, "name", None), conf


def evaluate(sm, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_label = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0})
    confusion: Counter = Counter()
    errors: List[Dict[str, Any]] = []
    correct = 0
    amb_total = amb_correct = 0
    neg_total = neg_wrong = 0
    confidences: List[float] = []

    for row in rows:
        expected = row.get("expected")
        got, conf = predict(sm, row)
        if conf is not None:
            confidences.append(conf)

        ok = (got == expected)
        correct += int(ok)
        confusion[(expected or NONE_LABEL, got or NONE_LABEL)] += 1

        if expected is not None:
            per_label[expected]["support"] += 1
        if ok:
            if expected is not None:
                per_label[expected]["tp"] += 1
        else:
            if expected is not None:
                per_label[expected]["fn"] += 1
            if got is not None:
                per_label[got]["fp"] += 1
            errors.append({"id": row.get("id"), "prompt": row["prompt"][:70],
                           "expected": expected, "got": got,
                           "ambiguous": bool(row.get("ambiguous"))})

        if row.get("ambiguous"):
            amb_total += 1
            amb_correct += int(ok)
        if expected is None:
            neg_total += 1
            neg_wrong += int(got is not None)

    labels = sorted(per_label)
    per_class = {}
    f1s = []
    for lb in labels:
        d = per_label[lb]
        prec = d["tp"] / (d["tp"] + d["fp"]) if (d["tp"] + d["fp"]) else 0.0
        rec = d["tp"] / (d["tp"] + d["fn"]) if (d["tp"] + d["fn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[lb] = {"precision": prec, "recall": rec, "f1": f1, **d}
        if d["support"]:
            f1s.append(f1)

    total = len(rows)
    routed = sum(n for (_e, g), n in confusion.items() if g != NONE_LABEL)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0.0,
        "per_class": per_class,
        "confusion": confusion,
        "errors": errors,
        "ambiguous": {"total": amb_total, "correct": amb_correct},
        "negatives": {"total": neg_total, "wrong": neg_wrong,
                      "fp_rate": neg_wrong / neg_total if neg_total else 0.0},
        "routed": routed,
        "mean_confidence": (sum(confidences) / len(confidences)) if confidences else None,
    }


def render(res: Dict[str, Any], show_errors: bool = False) -> str:
    out: List[str] = []
    out.append(f"Örnek: {res['total']}  Doğru: {res['correct']}  "
               f"Doğruluk: {res['accuracy']*100:.1f}%  Makro F1: {res['macro_f1']:.3f}")
    neg = res["negatives"]
    out.append(f"Alakasız mesajlar: {neg['total']} örnek, {neg['wrong']} yanlış pozitif "
               f"(oran {neg['fp_rate']*100:.1f}%)")
    amb = res["ambiguous"]
    if amb["total"]:
        out.append(f"Belirsiz örnekler: {amb['correct']}/{amb['total']} doğru")
    if res.get("mean_confidence") is not None:
        out.append(f"Ortalama güven: {res['mean_confidence']:.3f}")
    out.append("")
    out.append(f"{'yetenek':26s} {'kesinlik':>9s} {'duyarlilik':>11s} {'F1':>6s} {'destek':>7s}")
    for lb, d in res["per_class"].items():
        out.append(f"{lb:26s} {d['precision']*100:8.1f}% {d['recall']*100:10.1f}% "
                   f"{d['f1']:6.3f} {d['support']:7d}")
    out.append("")
    out.append("Karışıklık tablosu (beklenen -> bulunan):")
    for (exp, got), n in sorted(res["confusion"].items(), key=lambda kv: (-kv[1], kv[0])):
        mark = "  " if exp == got else "X "
        out.append(f"  {mark}{exp:26s} -> {got:26s} {n}")
    if show_errors and res["errors"]:
        out.append("")
        out.append("Yanlış kararlar:")
        for e in res["errors"]:
            tag = " [belirsiz]" if e["ambiguous"] else ""
            out.append(f"  {e['id']:10s} bekl={e['expected']} bulundu={e['got']}{tag}")
            out.append(f"             {e['prompt']}")
    return "\n".join(out)


def to_metrics(res: Dict[str, Any]) -> Dict[str, Any]:
    """Perf kayıt defteri biçimi: hata oranları düşük-iyi, sayımlar nötr."""
    m: Dict[str, Any] = {
        "routing_error_pct": {"value": round((1 - res["accuracy"]) * 100, 2), "unit": "%",
                              "direction": LOWER_BETTER},
        "routing_false_positive_pct": {"value": round(res["negatives"]["fp_rate"] * 100, 2),
                                       "unit": "%", "direction": LOWER_BETTER},
        "routing_accuracy_pct": {"value": round(res["accuracy"] * 100, 2), "unit": "%",
                                 "direction": NEUTRAL},
        "routing_macro_f1": {"value": round(res["macro_f1"], 4), "unit": "f1",
                             "direction": NEUTRAL},
        "routing_examples": {"value": res["total"], "unit": "adet", "direction": NEUTRAL},
    }
    for lb, d in res["per_class"].items():
        key = lb.replace("-", "_")
        m[f"routing_f1_{key}"] = {"value": round(d["f1"], 4), "unit": "f1", "direction": NEUTRAL}
    return m


def apply_overrides(pairs: List[str]) -> Dict[str, Any]:
    from entropy.skills.manager import SkillManager

    applied = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--set biçimi AD=DEGER olmalı: {pair}")
        name, raw = pair.split("=", 1)
        name = name.strip().upper()
        attr = TUNABLES.get(name)
        if not attr or not hasattr(SkillManager, attr):
            raise SystemExit(f"bilinmeyen eşik: {name} (seçenekler: {', '.join(TUNABLES)})")
        cur = getattr(SkillManager, attr)
        value = type(cur)(raw) if not isinstance(cur, bool) else raw.lower() == "true"
        setattr(SkillManager, attr, value)
        applied[name] = value
    return applied


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Yetenek yönlendirme doğruluk ölçümü")
    ap.add_argument("--dataset", default=str(DATASET))
    ap.add_argument("--no-write", action="store_true", help="geçmişe yazma")
    ap.add_argument("--real-skills", action="store_true",
                    help="yalıtılmış depo kataloğu yerine gerçek keşif yolunu kullan")
    ap.add_argument("--show-errors", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="AD=DEGER",
                    help="eşiği geçici olarak değiştir (kalıcı değil)")
    ap.add_argument("--report", nargs="?", const=5, type=int, default=None,
                    help="ölçme, son N koşunun trendini bas")
    args = ap.parse_args(argv)

    if args.report is not None:
        runs = perf_history.load_runs(HISTORY, limit=args.report)
        if not runs:
            print("Kayıt yok.")
            return 0
        print(perf_history.render_trend_markdown(runs))
        return 0

    overrides = apply_overrides(args.set)
    rows = load_dataset(Path(args.dataset))
    sm = build_manager(args.real_skills)
    res = evaluate(sm, rows)
    print(render(res, show_errors=args.show_errors))

    if not args.no_write:
        extra = {"suite": "routing_eval",
                 "dataset": Path(args.dataset).name,
                 "real_skills": bool(args.real_skills),
                 "overrides": overrides}
        path = perf_history.append_run(to_metrics(res), path=HISTORY, extra=extra)
        print(f"\nKayıt eklendi: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
