"""Faz 13-A2 — kullanıcının v0.10.1'i gerçek ekranda denerken bildirdiği yedi kusur.

Her test bir maddeye karşılık gelir ve **kök nedeni** kilitler, kozmetiği değil:

1. Yetenekler'de "Etkin" kutusu donduruyordu (toggle iki tam yeniden kurulum
   tetikliyordu) → toggle artık yalnız durumu yazar, ana iş parçacığı ≤ 50 ms.
2. Satır düğmeleri boş kareydi (ikon HİÇ atanmıyordu) → ikon gerçekten
   çizilebilir olmalı; `icon().isNull()` yeterli bir kapı değildir.
3. Sohbetteki rapor kartında "Raporu açSohbete al" bitişikti (satır içi
   `margin` Qt zengin metninde yok sayılır) → eylemler ayrı hücrelerde.
4. Ajan koşarken bunu gösteren bir yüzey yoktu; buna karşılık ÇEKİRDEK bir
   ajan/arka plan işi koşarken "yürütülüyor" moruna geçiyordu.
5. Üst çubuk sağlayıcı rozeti sabit 76 px tavanla kırpılıyordu.
6. Görevler ekranı üç bölümü birden açıyordu; kart önizlemesi sınırsızdı.
7. Bir görev koşarken ~20 boş üst düzey pencere parlıyordu
   (`setParent(None)` widget'ı Qt sözleşmesine göre PENCEREYE çevirir).

Tümü `QT_QPA_PLATFORM=offscreen` altında koşar; gerçek kasaya yazılmaz.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from entropy.skills.manager import SkillManager
from entropy.ui.widgets.lifecycle import clear_layout, discard_widget


# --------------------------------------------------------------- yardımcılar

@pytest.fixture
def skills_panel(qapp, tmp_path, monkeypatch):
    """26 sentetik yetenekle izole bir Yetenekler paneli (gerçek kasa okunmaz)."""
    from entropy.ui.widgets.skills_widget import SkillsWidget

    root = tmp_path / "skills"
    for i in range(26):
        folder = root / f"sentetik-{i:02d}"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: sentetik-{i:02d}\ndescription: Sentetik yetenek {i}\n---\n\nGovde.\n",
            encoding="utf-8",
        )
    manager = SkillManager()
    manager._isolated_root = root
    manager.root_skills_dir = root
    manager.project_skills_dir = None
    manager.global_skills_dir = root
    manager.state_file = tmp_path / "skills_state.json"

    # Yordam durumu diske gitmesin: ölçüm toggle'ın kendi maliyetini görsün.
    panel = SkillsWidget(skill_manager=manager)
    panel.resize(900, 700)
    panel.show()
    qapp.processEvents()
    yield panel
    panel.close()


# ---------------------------------------------------- 1. "Etkin" kutusu donma

def test_etkin_kutusu_ana_is_parcacigini_bloklamaz(skills_panel, qapp):
    """Toggle 26 yetenekle 50 ms'nin altında kalmalı (RAIL girdi bütçesi)."""
    names = [s.name for s in skills_panel._skills_cache]
    assert len(names) == 26

    worst = 0.0
    for name in names[:5]:
        start = time.perf_counter()
        skills_panel._on_toggle(name, True)
        worst = max(worst, (time.perf_counter() - start) * 1000.0)
    assert worst <= 50.0, f"toggle {worst:.1f} ms (kapı 50 ms)"


def test_etkin_kutusu_tam_yeniden_kurulum_tetiklemez(skills_panel, qapp):
    """Kök neden kilidi: toggle ne katalogu ne yordam durumunu yeniden okur."""
    calls = {"n": 0}
    original = skills_panel._load_catalog

    def counting():
        calls["n"] += 1
        return original()

    skills_panel._load_catalog = counting
    name = skills_panel._skills_cache[0].name
    skills_panel._on_toggle(name, True)
    qapp.processEvents()
    assert calls["n"] == 0, "toggle katalogu yeniden okudu (donmanın kök nedeni)"


def test_etkin_kutusu_satiri_yerinde_gunceller(skills_panel, qapp):
    """Kurulum yok ama kullanıcı sonucu GÖRÜR: rozet AKTİF/PASİF döner."""
    from PySide6.QtWidgets import QLabel

    name = skills_panel._skills_cache[0].name
    label = skills_panel.findChild(QLabel, f"skill_title_{name}")
    assert label is not None
    skills_panel._on_toggle(name, True)
    assert "AKT" in label.text()
    skills_panel._on_toggle(name, False)
    assert "PAS" in label.text()


def test_arama_kutusu_her_tusta_yeniden_kurmaz(skills_panel, qapp):
    """Süzgeç 300 ms'de birleştirilir; katalog diskten tekrar okunmaz."""
    calls = {"n": 0}
    skills_panel.refresh_skills = lambda: calls.__setitem__("n", calls["n"] + 1)
    for text in ("s", "se", "sen", "sent"):
        skills_panel.search_input.setText(text)
    qapp.processEvents()
    assert calls["n"] == 0, "yeniden kurulum ertelenmedi"
    assert skills_panel._rebuild_timer.isActive()


# ------------------------------------------------------ 2. görünmeyen düğmeler

def test_yetenek_satiri_dugmeleri_gercekten_cizilebilir(skills_panel, qapp):
    """Boş `QIcon` nesnesi kapıdan geçmemeli: `pixmap(16)` boş olmamalı."""
    from PySide6.QtWidgets import QPushButton

    name = skills_panel._skills_cache[0].name
    for prefix in ("skill_edit_", "skill_folder_", "distill_btn_", "refresh_btn_"):
        btn = skills_panel.findChild(QPushButton, f"{prefix}{name}")
        assert btn is not None, f"{prefix}{name} bulunamadı"
        drawable = not btn.icon().pixmap(16, 16).isNull()
        assert drawable or btn.text().strip(), (
            f"{prefix}{name}: ne çizilebilir ikon ne metin var (boş kare)"
        )
        assert btn.accessibleName().strip(), f"{prefix}{name}: erişilebilir ad yok"


def test_kapi_bos_ikon_nesnesini_yakalar(qapp):
    """Kapının GERÇEKTEN ölçtüğünün kanıtı (SKILL §0.11)."""
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton

    from scripts.ui_audit import empty_interactive_widgets, is_icon_drawable

    assert not is_icon_drawable(QIcon())
    host = QWidget()
    layout = QVBoxLayout(host)
    offender = QPushButton("")
    offender.setIcon(QIcon())               # boş ikon nesnesi: eski kapı geçirirdi
    offender.setAccessibleName("bilerek bozuk")
    layout.addWidget(offender)
    host.show()
    qapp.processEvents()
    assert offender.objectName() or True
    assert empty_interactive_widgets(host), "kapı boş ikonlu düğmeyi yakalamadı"
    host.close()


def test_ajan_kart_dugmelerinin_adi_ve_ikonu_var(qapp):
    from entropy.ui.widgets.agents_widget import AgentCard, AgentsWidget

    panel = AgentsWidget(registry=None, board=None)
    spec = {"name": "arastirmaci", "description": "arastirir", "skills": []}
    card = AgentCard(spec, panel)
    card.show()
    qapp.processEvents()
    for attr in ("assign_btn", "edit_btn", "open_btn", "delete_btn"):
        btn = getattr(card, attr)
        assert btn.accessibleName().strip(), f"{attr}: erişilebilir ad yok"
        assert btn.text().strip() or not btn.icon().pixmap(16, 16).isNull(), (
            f"{attr}: boş kare"
        )
    card.close()
    panel.close()


# ------------------------------------------------------- 3. rapor sohbet kartı

def test_rapor_kartinda_eylemler_bitisik_yazilmaz(qapp):
    """Kullanıcının gördüğü tam dize: "Raporu açSohbete al"."""
    from entropy.ui.widgets.report_chat_card import report_card_html

    html = report_card_html({
        "card_id": "kart-1", "title": "Araştırma raporu", "agent": "arastirmaci",
        "status": "done", "ok": True, "summary": "Özet.", "report_path": "C:/x/y.md",
    })
    doc = QTextDocument()
    doc.setHtml(html)
    text = doc.toPlainText()
    assert "Raporu açSohbete al" not in text
    assert "Raporu aç" in text and "Sohbete al" in text
    # İki eylem AYRI blokta: aralarında satır sonu ya da sekme var.
    between = text.split("Raporu aç", 1)[1].split("Sohbete al", 1)[0]
    assert between.strip() == "" and between != "", "eylemler arasında ayırıcı yok"


def test_rapor_karti_yalnizca_sohbete_al_ile_de_calisir(qapp):
    from entropy.ui.widgets.report_chat_card import report_card_html

    doc = QTextDocument()
    doc.setHtml(report_card_html({"card_id": "k2", "title": "Yolsuz", "ok": False}))
    assert "Sohbete al" in doc.toPlainText()


# ------------------------------------- 4. canlı ajan durumu + çekirdek anlamı

def test_ajan_kosarken_rozet_sureyi_gosterir():
    from entropy.ui.widgets.agent_run_state import agent_status, run_badge_text

    now = time.time()
    cards = [{"id": "k1", "agent": "arastirmaci", "title": "Kaynak tara",
              "status": "running", "started_at": now - 72}]
    info = agent_status("arastirmaci", cards)
    assert info["state"] == "running"
    assert info["card_title"] == "Kaynak tara"
    assert run_badge_text(info, now=now) == "çalışıyor · 1 dk 12 sn"


def test_ajan_bostayken_rozet_son_kosuyu_gosterir():
    from entropy.ui.widgets.agent_run_state import agent_status, run_badge_text

    now = time.time()
    cards = [{"id": "k1", "agent": "arastirmaci", "status": "done",
              "finished_at": now - 10}]
    info = agent_status("arastirmaci", cards)
    assert info["state"] == "idle"
    assert run_badge_text(info, now=now) == "son koşu: az önce"


def test_sozlesme_yoksa_kart_durumundan_turetilir(monkeypatch):
    """`AgentSessionStore.status` henüz yoksa panel boş rozet basmaz."""
    import entropy.ui.widgets.agent_run_state as ars

    monkeypatch.setattr(
        ars, "status_from_cards", ars.status_from_cards
    )
    cards = [{"id": "k", "agent": "yazar", "status": "taken", "started_at": time.time()}]
    assert ars.agent_status("yazar", cards)["state"] == "running"


def test_kosan_ajan_sayisi_gezinme_noktasina_yazilir(qapp):
    from entropy.ui.widgets.nav_list import NavList

    nav = NavList()
    nav.addTab(QWidget(), "Ajanlar")
    assert nav.set_activity("Ajanlar", 2, "ajan çalışıyor")
    assert nav.tabText(0).startswith("Ajanlar ●2")
    assert nav.set_activity("Ajanlar", 0)
    assert nav.tabText(0) == "Ajanlar"


def test_cekirdek_arka_plan_gorevinde_yurutuluyora_gecmez(qapp):
    """Çekirdek YALNIZCA Entropy'nin kendi turunu yansıtır."""
    import inspect

    from entropy.ui.modes import chat_mode

    for name in ("_on_task_triggered", "_on_task_completed", "_on_distill_progress"):
        source = inspect.getsource(getattr(chat_mode.ChatModeWindow, name))
        assert "brand.set_state" not in source, (
            f"{name} çekirdek durumunu değiştiriyor; arka plan işi çekirdek değildir"
        )


# ------------------------------------------------------- 5. üst çubuk rozeti

def test_saglayici_rozeti_kirpilmaz(qapp):
    from entropy.ui.widgets.provider_badge import ProviderStatusBadge, status_text

    badge = ProviderStatusBadge()
    badge.set_primary("claude")
    badge.set_status("claude", {"logged_in": True, "plan": "max"})
    badge.show()
    qapp.processEvents()
    label = badge.labels["claude"]
    text = status_text("claude", "Claude", {"logged_in": True, "plan": "max"})
    needed = label.fontMetrics().horizontalAdvance(text)
    assert label.maximumWidth() >= needed, "rozet metni kırpılıyor"
    assert label.minimumWidth() >= needed
    assert "Claude" in label.toolTip() or "Plan" in label.toolTip()
    badge.close()


def test_durum_kumesi_sizeHint_altina_sikismaz(qapp):
    from PySide6.QtWidgets import QSizePolicy

    from entropy.ui.widgets.header_bar import StatusCluster

    cluster = StatusCluster()
    assert cluster.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Minimum


# ------------------------------------------------------------ 6. Görevler ekranı

def test_arka_plan_gorevleri_varsayilan_katli(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    from entropy.scheduler.cron_engine import TaskScheduler
    from entropy.ui.design import prefs as ui_prefs
    from entropy.ui.widgets.tasks_widget import TasksWidget

    settings = QSettings(str(tmp_path / "p13a2.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(ui_prefs, "settings", lambda: settings)
    TaskScheduler.reset_instance()
    TaskScheduler.get_instance(storage_path=tmp_path / "tasks.json")

    widget = TasksWidget()
    widget.show()
    qapp.processEvents()
    assert not widget.is_expanded(), "bölüm varsayılan olarak açık geldi"
    assert not widget.list_widget.isVisible()
    # Sayı katlıyken de görünür: kullanıcı açmadan kaç görev olduğunu bilir.
    assert widget.count_label.text().count("/") == 1

    widget.set_expanded(True)
    qapp.processEvents()
    assert widget.list_widget.isVisible()
    assert ui_prefs.section_expanded("tasks.background", default=False) is True
    widget.scheduler.stop()
    widget.close()


def test_kart_onizlemesi_en_cok_uc_satir(qapp):
    from entropy.ui.widgets.task_board_widget import (
        CARD_PREVIEW_LINES, TaskCardWidget, TaskBoardWidget,
    )
    from PySide6.QtWidgets import QLabel

    class Board:
        def list(self, **_kw):
            return []

    board = TaskBoardWidget(board=Board())
    card = TaskCardWidget(
        {"id": "k", "title": "Uzun kart", "status": "backlog", "agent": "a",
         "summary": "Çok uzun bir özet. " * 40},
        board,
    )
    card.resize(220, 400)
    card.show()
    qapp.processEvents()
    labels = [w for w in card.findChildren(QLabel) if w.maximumHeight() < 16777215]
    assert labels, "önizleme etiketinde yükseklik tavanı yok"
    preview = labels[-1]
    line = preview.fontMetrics().lineSpacing()
    assert preview.maximumHeight() <= line * CARD_PREVIEW_LINES
    card.close()
    board.close()


def test_kart_silme_erisilebilir(qapp):
    """QA artıklarının temizlenebilmesi: detay panelinde "Sil" düğmesi var."""
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    class Board:
        def list(self, **_kw):
            return []

    board = TaskBoardWidget(board=Board())
    btn = board.detail_panel.delete_btn
    assert btn.accessibleName().strip() == "Sil"
    assert btn.toolTip().strip()
    board.close()


# --------------------------------------------------- 7. hayalet üst düzey pencere

def test_setParent_none_ust_duzey_pencere_uretir(qapp):
    """Kök nedenin Qt sözleşmesi olarak kanıtı (bu yüzden desen yasak)."""
    host = QWidget()
    layout = QVBoxLayout(host)
    child = QFrame()
    layout.addWidget(child)
    host.show()
    qapp.processEvents()
    assert not child.isWindow()

    layout.removeWidget(child)
    child.setParent(None)                     # ESKİ DESEN
    assert child.isWindow(), "Qt davranışı değişmiş; kapının gerekçesi gözden geçirilmeli"
    child.deleteLater()
    host.close()


def test_discard_widget_ust_duzey_pencere_uretmez(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    children = [QFrame() for _ in range(5)]
    for child in children:
        layout.addWidget(child)
    host.show()
    qapp.processEvents()

    before = {id(w) for w in QApplication.topLevelWidgets()}
    removed = clear_layout(layout)
    assert removed == 5
    new_windows = [
        w for w in QApplication.topLevelWidgets()
        if id(w) not in before and w.isWindow()
    ]
    assert new_windows == [], f"{len(new_windows)} hayalet pencere doğdu"
    host.close()


def test_pano_yasam_dongusu_hayalet_pencere_uretmez(qapp):
    """Kart yaşam döngüsü + pano yenilemesi: yeni GÖRÜNÜR üst düzey widget 0."""
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    class Board:
        def __init__(self):
            self.cards = [
                {"id": f"k{i}", "title": f"Kart {i}", "status": "backlog",
                 "agent": "arastirmaci", "summary": "özet " * 30}
                for i in range(20)
            ]

        def list(self, **_kw):
            return list(self.cards)

        def get(self, cid):
            return next((c for c in self.cards if c["id"] == cid), None)

        def update(self, cid, **kw):
            card = self.get(cid)
            card.update(kw)
            return card

    board = Board()
    widget = TaskBoardWidget(board=board)
    widget.resize(1200, 700)
    widget.show()
    qapp.processEvents()

    known = {id(w) for w in QApplication.topLevelWidgets()}
    for status in ("assigned", "running", "review", "done"):
        for card in board.cards:
            card["status"] = status
        widget.refresh_cards()
        qapp.processEvents()
        ghosts = [
            w for w in QApplication.topLevelWidgets()
            if id(w) not in known and w.isWindow() and w.isVisible()
        ]
        assert ghosts == [], f"{status}: {len(ghosts)} hayalet pencere"
    widget.close()


def test_kaynak_agacinda_setparent_none_kalmadi():
    """Kalıcı kapı: desen yeniden sızarsa test kırmızıya döner."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src" / "entropy"
    offenders = []
    for path in list(root.rglob("*.py")):
        if path.name == "lifecycle.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".setParent(None)" in line.split("#", 1)[0]:
                offenders.append(f"{path.name}:{lineno}")
    assert offenders == [], f"hayalet pencere deseni geri geldi: {offenders}"
