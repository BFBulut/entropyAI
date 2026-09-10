"""
Faz 13-A — rapor başlığı + "sohbet turu rapor değildir" sözleşmesi (§1.5).

Kök neden: köprüler başlığı kullanıcının istem satırının ilk 40 karakterinden
üretiyordu ("Tamamdır, şimdi senden yeni bir yetenek (+2)") ve 8 anahtar
kelimelik sezgi serbest sohbet turlarını rapora çeviriyordu.

Testler GERÇEK köprü yolunu (`subprocess.Popen` taklidiyle) sürer; sahte
köprüyle yazılmış bir test bu sözleşmeyi doğrulayamaz.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from entropy.core.report_title import (
    derive_report_title,
    safe_filename_title,
    save_session_note,
)


# --------------------------------------------------------------- saf başlık

def test_h1_wins_over_user_prompt_line():
    """(a) İstem "Tamamdır, şimdi …" olsa da başlık gövdedeki H1'dir."""
    body = "Bir giriş cümlesi burada.\n\n# Vektör Veritabanı Karşılaştırması\n\nİçerik."
    assert derive_report_title(body, fallback="dosya-adi") == "Vektör Veritabanı Karşılaştırması"


def test_first_sentence_when_no_h1():
    """(b) H1 yoksa ilk anlamlı cümle (≥ 3 kelime, düzgün kırpılır)."""
    body = "Kısa\n\nBu rapor üç farklı vektör deposunu karşılaştırır. İkinci cümle."
    assert derive_report_title(body) == "Bu rapor üç farklı vektör deposunu karşılaştırır"


def test_long_sentence_is_trimmed_on_word_boundary():
    body = "Bu " + "uzun kelime " * 30 + "son."
    title = derive_report_title(body, max_len=40)
    assert len(title) <= 40
    assert not title.endswith(" ")
    assert "uzun" in title


def test_fallback_when_body_has_no_title_source():
    """(c) H1 da cümle de yoksa fallback (dosya adı) kullanılır."""
    assert derive_report_title("ok.", fallback="Gorev_kart_20260910") == "Gorev_kart_20260910"
    assert derive_report_title("", fallback="") == "Araştırma Raporu"


def test_machine_blocks_and_code_fences_are_skipped():
    """(d) `[PANO]/[KANIT]/[KONTROL NOKTASI]` blokları ve kod blokları atlanır."""
    body = (
        "---\ntitle: yanlış başlık\n---\n"
        "[KANIT]\ntest: 12 passed\n\n"
        "[PANO board_create] {\"title\": \"kart\"} [/PANO]\n"
        "[KONTROL NOKTASI]\nadim: 1\n\n"
        "```\n# kod içindeki başlık\n```\n\n"
        "# Gerçek Rapor Başlığı\n\ngövde\n"
    )
    assert derive_report_title(body) == "Gerçek Rapor Başlığı"


def test_chat_opener_is_never_a_title():
    body = "Tamamdır, şimdi senden yeni bir yetenek istiyorum.\n"
    assert derive_report_title(body, fallback="yedek") == "yedek"


def test_safe_filename_title_strips_forbidden_characters():
    assert safe_filename_title('a/b:c*d?"<>|') == "abcd"
    assert safe_filename_title("   ") == "Arastirma_Raporu"


def test_session_note_frontmatter_and_layout(tmp_path):
    path = save_session_note(
        tmp_path / "Entropy",
        "# Sohbet Konusu\n\ngövde",
        provider="agy",
        model="gemini-3.8-flash-high",
        skill="financial-auditor",
    )
    text = path.read_text(encoding="utf-8")
    assert "type: session" in text
    assert 'title: "Sohbet Konusu"' in text
    assert 'provider: "agy"' in text
    assert 'model: "gemini-3.8-flash-high"' in text
    assert path.parent.parent.name == "Sessions"
    assert len(path.parent.name) == 10  # YYYY-MM-DD
    assert path.name[:4].isdigit()  # HHMM-<konu>.md


# ------------------------------------------------------- gerçek köprü yolu

class _DummyStdout:
    def __init__(self, lines):
        self._iter = iter(lines)

    def readline(self):
        return next(self._iter, "")

    def close(self):
        pass


def _agy_popen(text: str):
    payload = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = _DummyStdout([
                '{"event": "step_update", "step_update": {"text_delta": "%s"}}\n' % payload,
                '{"event": "result", "result": {"response": "ok"}}\n',
                "",
            ])
            self.pid = 9911
            self.stdin = None

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    return DummyProc


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    """Geçici kasa: gerçek kasa bu testlerde SALT OKUNUR."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "vault", raising=False)
    return tmp_path / "vault" / "Entropy"


def _run_agy_chat(prompt: str, answer: str, monkeypatch, tmp_path):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path / "proj")
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )
    monkeypatch.setattr("subprocess.Popen", _agy_popen(answer))
    bridge._execute_prompt_worker(prompt)
    return bridge


def _reports(entropy_dir: Path):
    root = Path(entropy_dir)
    return [p for p in root.rglob("*.md") if "Sessions" not in p.parts and p.parent.name == "Reports"]


def _sessions(entropy_dir: Path):
    return sorted((Path(entropy_dir) / "Sessions").rglob("*.md"))


def test_free_chat_with_research_keyword_writes_session_not_report(vault, tmp_path, monkeypatch):
    """(e) "araştır" geçen serbest sohbet + uzun başlıklı yanıt → RAPOR YOK."""
    answer = "# Vektör Depoları\n\n" + ("Bu bölüm karşılaştırma içerir. " * 20)
    _run_agy_chat("Tamamdır, şimdi senden yeni bir yetenek: bunu araştır", answer, monkeypatch, tmp_path)

    assert _reports(vault) == [], "serbest sohbet turu rapora dönüşmemeli"
    notes = _sessions(vault)
    assert len(notes) == 1
    text = notes[0].read_text(encoding="utf-8")
    assert "type: session" in text
    assert 'title: "Vektör Depoları"' in text
    assert "Tamamdır" not in text.splitlines()[2]  # istem satırı başlık değil


def test_explicit_learn_writes_report_with_body_title(vault, tmp_path, monkeypatch):
    """(f-1) Açık `/learn` → rapor oluşur, başlık GÖVDEDEN gelir."""
    answer = "# Kubernetes Operatörleri\n\n" + ("Detay. " * 40)
    _run_agy_chat("/learn Tamamdır, şimdi senden yeni bir yetenek (+2)", answer, monkeypatch, tmp_path)

    reports = _reports(vault)
    assert len(reports) == 1
    assert "Kubernetes" in reports[0].name
    assert "Tamamd" not in reports[0].name
    assert _sessions(vault) == []


def test_autonomous_task_prompt_writes_report(vault, tmp_path, monkeypatch):
    """(f-2) `[OTONOM PLANLI GÖREV]` → rapor oluşur (`Gorev_` öneki korunur)."""
    answer = "# Günlük Tarama\n\n" + ("Bulgu. " * 40)
    _run_agy_chat("[OTONOM PLANLI GÖREV: Gunluk Tarama] devam et", answer, monkeypatch, tmp_path)

    reports = _reports(vault)
    assert len(reports) == 1
    assert reports[0].name.startswith("Gorev_")
    assert _sessions(vault) == []


def test_background_card_report_title_comes_from_output(vault, tmp_path, monkeypatch):
    """(f-3) Pano kartı çıktısı → `Gorev_<gövdeden türetilmiş>_<zaman>`."""
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path / "proj")
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )
    monkeypatch.setattr(
        "subprocess.Popen", _agy_popen("# Devir Kartı Sonucu\n\n" + ("Ayrinti. " * 30))
    )

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="card-1",
        task_name="Tamamdır, şimdi senden yeni bir yetenek (+2)",
        prompt="finansal denetim raporu hazırla",
        on_result=lambda *a: done.set(),
        save_report=True,
        skill="",  # kart yeteneksiz
    )
    assert done.wait(timeout=15)

    reports = _reports(vault)
    assert len(reports) == 1
    assert "Devir" in reports[0].name
    assert "Tamamd" not in reports[0].name


def test_skill_less_card_report_does_not_land_in_foreign_skill_folder(vault, tmp_path, monkeypatch):
    """
    (g) QA bulgusu: yeteneksiz kartın raporu `Skills/financial-auditor/Reports/`
    altına düşüyordu (istem sezgisi kartın boş `skill` alanını eziyordu).
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path / "proj")
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )
    monkeypatch.setattr("subprocess.Popen", _agy_popen("# Kart Sonucu\n\nGövde metni burada."))

    class _Skill:
        name = "financial-auditor"

    monkeypatch.setattr(
        AgyProcessBridge, "detect_skill_for_prompt", lambda self, *a, **k: _Skill()
    )

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="card-2",
        task_name="devir karti d",
        prompt="finansal denetim yap",
        on_result=lambda *a: done.set(),
        save_report=True,
        skill="",
    )
    assert done.wait(timeout=15)

    reports = _reports(vault)
    assert len(reports) == 1
    assert "Skills" not in reports[0].parts, reports[0]


def test_taskboard_passes_card_skill_to_bridge():
    """(g-2) `TaskBoard` köprüye kartın yetenek alanını geçirir."""
    import inspect

    from entropy.agents import tasks as tasks_mod

    src = inspect.getsource(tasks_mod.TaskBoard.run)
    assert "skill=card.skill" in src
    assert '"skill"' in src  # imza süzgecinde de var
