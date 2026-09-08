"""
Yönlendirme kalitesinin bağımsız tutma kümesi (holdout) üzerinde regresyon kilidi.

tests/data/routing_holdout.jsonl, ayar yaptığımız routing_eval.jsonl'dan bağımsız
bir örneklemdir: örnekler .entropy/chat_history.json'dan değil, Obsidian kasasındaki
finans raporlarının başlık/ilk paragraflarından ve görev adlarından türetildi. Bu
yüzden buradaki eşikler "ölçtüğümüz kümede iyileştik" değil, "genelledi" der.

Eşikler ölçülen değerin biraz altına konur: amaç gelecekteki bir gerileme (ör.
anahtar kelime silinmesi, uzunluk cezasının geri gelmesi) sessizce geçmesin.
"""

import json
from pathlib import Path

import pytest

from entropy.skills.manager import SkillManager

REPO_ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = REPO_ROOT / "tests" / "data" / "routing_holdout.jsonl"
EVALSET = REPO_ROOT / "tests" / "data" / "routing_eval.jsonl"


def _load(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


@pytest.fixture(scope="module")
def sm():
    m = SkillManager(root_skills_dir=REPO_ROOT / "skills")
    # Kullanıcının açık/kapalı tercihleri ölçümü kirletmesin (yalnızca bellekte).
    for s in m.list_skills():
        m._enabled_cache[s.name] = True
    return m


def _score(sm, rows):
    correct = 0
    fin_tp = fin_fn = fin_fp = 0
    false_positives = 0
    negatives = 0
    for row in rows:
        got, _conf = sm.score_skill_for_prompt(
            row["prompt"], last_skill=row.get("last_skill"), history=row.get("history")
        )
        got = getattr(got, "name", None)
        exp = row.get("expected")
        correct += int(got == exp)
        if exp is None:
            negatives += 1
            false_positives += int(got is not None)
        if exp == "financial-auditor":
            fin_tp += int(got == exp)
            fin_fn += int(got != exp)
        elif got == "financial-auditor":
            fin_fp += 1
    return {
        "n": len(rows),
        "accuracy": correct / len(rows),
        "fin_recall": fin_tp / (fin_tp + fin_fn) if (fin_tp + fin_fn) else 0.0,
        "fin_precision": fin_tp / (fin_tp + fin_fp) if (fin_tp + fin_fp) else 0.0,
        "false_positives": false_positives,
        "negatives": negatives,
    }


def test_holdout_dataset_is_independent_of_chat_history():
    rows = _load(HOLDOUT)
    assert len(rows) == 30
    assert all(r.get("source") != "chat" for r in rows), (
        "tutma kümesi sohbet geçmişinden örnek almamalı: ayar kümesiyle bağımlı olur"
    )
    eval_prompts = {r["prompt"] for r in _load(EVALSET)}
    assert not ({r["prompt"] for r in rows} & eval_prompts), "örnekler çakışıyor"
    assert any(r.get("expected") is None for r in rows), "yanlış pozitif ölçecek kontrol yok"


def test_financial_routing_generalizes_on_holdout(sm):
    res = _score(sm, _load(HOLDOUT))
    # Ölçülen (2026-09-08): doğruluk %100, finans duyarlılığı %100, 0 yanlış pozitif.
    assert res["fin_recall"] >= 0.90, f"finans duyarlılığı düştü: {res}"
    assert res["accuracy"] >= 0.90, f"tutma kümesi doğruluğu düştü: {res}"
    assert res["false_positives"] == 0, f"alakasız mesaja yetenek atandı: {res}"


def test_no_false_positive_regression_on_eval_set(sm):
    res = _score(sm, _load(EVALSET))
    # Ölçülen (2026-09-08): doğruluk %90,7, finans duyarlılığı %85, 0/11 yanlış pozitif.
    assert res["false_positives"] == 0, f"yanlış pozitif arttı: {res}"
    assert res["fin_recall"] >= 0.80, f"finans duyarlılığı gerilemesi: {res}"
    assert res["accuracy"] >= 0.85, f"genel doğruluk gerilemesi: {res}"


def test_long_description_does_not_penalize_keyword_match(tmp_path):
    """
    Uzun açıklama, ad/anahtar kelime eşleşmesini bastırmamalı.

    Regresyon: BM25 uzunluk cezası TOPLAM puana uygulandığı için, açıklaması
    damıtmayla 3.877 karaktere büyüyen financial-auditor'ın tam anahtar kelime
    eşleşmesi (+5,0) karar eşiğinin altına düşüyordu; kısa açıklamalı
    pdf-analyzer aynı mesajı kazanıyordu.
    """
    for name, desc in [
        ("financial-auditor", "Sirket bilancolarini denetler. " + "detay " * 700),
        ("pdf-analyzer", "PDF belgelerini inceler ve tablo ayiklar"),
    ]:
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: \"{desc}\"\ntags: x\n---\n\n# {name}\n\nTalimat.\n",
            encoding="utf-8",
        )
    m = SkillManager(root_skills_dir=tmp_path)
    for s in m.list_skills():
        m._enabled_cache[s.name] = True

    got, conf = m.score_skill_for_prompt("ATATP hissesi icin temettu verimi ne kadar")
    assert getattr(got, "name", None) == "financial-auditor"
    assert conf >= 0.5
