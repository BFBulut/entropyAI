"""Interactive Cyber Skills & Tools Management Widget for Zen Mode."""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QElapsedTimer, QTimer, Slot
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.ui.widgets.header_bar import repolish
from entropy.skills.manager import SkillManager, SkillDefinition
from entropy.ui.themes.cyber_theme import CYBER_THEME
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import live_palette as _live_palette
from entropy.ui.design import TOKENS, icon as design_icon
from entropy.ui.widgets.lifecycle import clear_layout

# Faz 12-F: canli palet — tema degisince gomulu govdeler de doner.
_P = _live_palette()

#: Ağır yeniden kurulumların birleştirme penceresi (ms). Arama kutusuna
#: yazarken ya da salvo hâlinde sinyal gelirken tek yeniden kurulum yapılır.
REBUILD_DEBOUNCE_MS = 300

#: Satır düğmelerinin ikon adları (Codicons). Faz 13-A2 madde 2: bu düğmeler
#: `QPushButton("")` olarak kuruluyor ve ikon HİÇ atanmıyordu; ekranda boş kare
#: görünüyorlardı. `accessibleName` dolu olduğu için G13-1 kapısı da onları
#: geçiriyordu — kapı artık `pixmap(16)` ile GERÇEKTEN çizilebilirlik ölçüyor.
ROW_ICONS = {
    "distill": "beaker",       # damıt (artımlı)
    "refresh": "refresh",      # tazele (tüm arşiv)
    "edit": "edit",            # SKILL.md düzenle
    "folder": "folder-opened",
    "delete": "trash",
}


def apply_row_icon(button, key: str, tone: str = "muted") -> bool:
    """Satır düğmesine ikon koyar; QtAwesome yoksa metin yedeğine düşer.

    Döner değer: ikon gerçekten çizilebilir mi. `QIcon()` boş nesnesi
    `isNull()` ile yakalanmaz olabildiği için `pixmap(16)` denetlenir —
    "boş kare" hatasının kök nedeni buydu.
    """
    color = TOKENS["color"]["text"] if tone == "muted" else TOKENS["color"].get(tone, TOKENS["color"]["text"])
    ico = design_icon(ROW_ICONS.get(key, key), color=color)
    drawable = ico is not None and not ico.isNull() and not ico.pixmap(16, 16).isNull()
    if drawable:
        button.setIcon(ico)
        return True
    # Yedek: ikon çizilemiyorsa düğme BOŞ kalmaz (ui-design §0.10).
    fallback = {"distill": "D", "refresh": "T", "edit": "E", "folder": "K", "delete": "X"}
    button.setText(button.text() or fallback.get(key, "?"))
    return False

class AddSkillDialog(QDialog):
    """Dialog to manually register or synthesize a new skill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Yetenek (Skill) Oluştur")
        self.setFixedSize(500, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: crypto-trader veya code-optimizer")
        form.addRow("Yetenek Adı:", self.name_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Bu yetenek ne yapar, ne zaman devreye girer?")
        form.addRow("Açıklama:", self.desc_input)

        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Yetenek Yönergeleri & Talimatlar (Markdown):</b>"))
        self.instructions_input = QTextEdit()
        self.instructions_input.setPlaceholderText(
            "# Yetenek Kullanım Talimatları\n\n"
            "1. Kullanıcı bu analizi talep ettiğinde şu adımları izleyin...\n"
            "2. Çıktıyı şu formatta hazırlayın..."
        )
        layout.addWidget(self.instructions_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setAccessibleName("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Yeteneği Kaydet")
        save_btn.setAccessibleName("Yeteneği Kaydet")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _on_save(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        inst = self.instructions_input.toPlainText().strip()
        if not name or not desc or not inst:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen tüm alanları doldurun.")
            return
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.desc_input.text().strip(), self.instructions_input.toPlainText().strip()

class DownloadSkillDialog(QDialog):
    """Dialog to download a raw SKILL.md from a web or GitHub URL."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İnternetten Skill (SKILL.md) İndir")
        self.setFixedSize(480, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://github.com/owner/repo veya raw SKILL.md bağlantısı")
        form.addRow("Skill / GitHub URL:", self.url_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Opsiyonel özel yetenek adı (boş bırakılabilir)")
        form.addRow("Özel İsim:", self.name_input)

        layout.addLayout(form)

        info_lbl = QLabel(f"<span style='color:{_P["text_muted"]}; font-size:11px;'>Not: Doğrudan GitHub depo adresi (https://github.com/...), raw SKILL.md veya .zip arşivi bağlantısı girebilirsiniz. Otomatik olarak taranıp sisteme yüklenecektir.</span>")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        dl_btn = QPushButton("İndir ve Yükle")
        dl_btn.setAccessibleName("İndir ve Yükle")
        dl_btn.setProperty("variant", "primary")
        dl_btn.clicked.connect(self._on_download)
        btn_box.addWidget(dl_btn)

        layout.addLayout(btn_box)

    def _on_download(self):
        url = self.url_input.text().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.warning(self, "Geçersiz URL", "Lütfen geçerli bir http/https bağlantısı girin.")
            return
        self.accept()

    def get_data(self):
        return self.url_input.text().strip(), self.name_input.text().strip() or None

class SkillEditorDialog(QDialog):
    """SKILL.md dosyasını uygulama içinde düzenleyen basit editör."""

    def __init__(self, skill_path: Path, skill_name: str = "", parent=None):
        super().__init__(parent)
        self.skill_path = Path(skill_path)
        self.setWindowTitle(f"Yetenek Düzenle: {skill_name or self.skill_path.name}")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        path_lbl = QLabel(str(self.skill_path))
        path_lbl.setWordWrap(True)
        layout.addWidget(path_lbl)

        self.editor = QTextEdit()
        try:
            self.editor.setPlainText(self.skill_path.read_text(encoding="utf-8"))
        except Exception as e:
            self.editor.setPlainText(f"# Dosya okunamadı: {e}")
        layout.addWidget(self.editor)

        btn_box = QHBoxLayout()
        self.system_btn = QPushButton("Sistem Editöründe Aç")
        self.system_btn.setAccessibleName("Sistem Editöründe Aç")
        self.system_btn.clicked.connect(self.open_in_system_editor)
        btn_box.addWidget(self.system_btn)
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setAccessibleName("Kaydet")
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(self.save_btn)

        layout.addLayout(btn_box)

    def open_in_system_editor(self) -> bool:
        """SKILL.md'yi işletim sisteminin varsayılan editöründe açar."""
        if not self.skill_path.exists():
            return False
        try:
            if os.name == "nt":
                os.startfile(str(self.skill_path))
            else:
                subprocess.run(["xdg-open", str(self.skill_path)])
            return True
        except Exception:
            return False

    def save(self) -> bool:
        """Editördeki içeriği diske yazar ve yetenek kataloğunu tazeler."""
        try:
            self.skill_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Kaydedilemedi", f"SKILL.md yazılamadı: {e}")
            return False
        bus.skills_updated.emit()
        return True

    def _on_save(self):
        if self.save():
            self.accept()


class SkillsWidget(QFrame):
    """Visual dock to browse, toggle, download, and manage AI Skills."""

    def __init__(self, parent=None, skill_manager: Optional[SkillManager] = None, bridge=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.skill_manager = skill_manager or SkillManager()
        # Yordam damıtma arka plan görevi olarak köprü üzerinden başlatılır;
        # köprü verilmezse damıtma düğmesi pasif kalır, panel yine çalışır.
        self.bridge = bridge

        # ---- Faz 13-A2 madde 1: donma önlemi -------------------------------
        # "Etkin" kutusuna basınca uygulama gerçekten kilitleniyordu (Windows
        # "yanıt vermiyor" diyaloğu). Ölçüm (22 yetenek, offscreen):
        #   list_skills()            232 ms   (tüm SKILL.md'lerin diskten okunup ayrıştırılması)
        #   PlaybookStore.status x22 1.058 ms (yetenek başına kasa taraması)
        #   _on_toggle               1.961 ms (ikisi de İKİ KEZ: doğrudan çağrı + bus.skills_updated)
        # Toggle'ın hiçbiri için gerekçesi yok: etkinlik durumu ne katalogu ne
        # de yordam durumunu değiştirir. Artık toggle yalnızca durumu yazar ve
        # o satırın rozetini günceller; katalog + yordam durumu önbellekte
        # tutulur ve yalnızca gerçekten değiştiklerinde (rapor/yordam/proje
        # sinyali ya da "Yenile") yeniden hesaplanır.
        self._skills_cache: Optional[List[SkillDefinition]] = None
        self._playbook_states: Dict[str, Dict[str, Any]] = {}
        self._catalog_dirty = True
        #: Kendi yazdığımız durumun geri tepen `skills_updated` sinyali
        #: yüzünden tam yeniden kurulum yapılmaz.
        self._suppress_bus_refresh = False
        #: Salvo hâlinde gelen sinyalleri tek yeniden kurulumda birleştirir.
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(REBUILD_DEBOUNCE_MS)
        self._rebuild_timer.timeout.connect(self.refresh_skills)
        #: Son yeniden kurulumun ana iş parçacığı süresi (ms) — kapı ölçer.
        self.last_rebuild_ms: float = 0.0
        self.last_toggle_ms: float = 0.0

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("Yetenekler")
        title_label.setProperty("role", "heading")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        dl_btn = QPushButton("URL'den İndir")
        dl_btn.setProperty("variant", "primary")
        dl_btn.clicked.connect(self._open_download_dialog)
        header_layout.addWidget(dl_btn)

        add_btn = QPushButton("+ Yeni Yetenek")
        add_btn.setAccessibleName("+ Yeni Yetenek")
        add_btn.setProperty("variant", "primary")
        add_btn.clicked.connect(self._open_add_dialog)
        header_layout.addWidget(add_btn)

        self.sync_btn = QPushButton("Yenile")
        self.sync_btn.setAccessibleName("Yenile")
        self.sync_btn.clicked.connect(self.reload_from_disk)
        header_layout.addWidget(self.sync_btn)

        self.layout.addLayout(header_layout)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Yetenek ara (örn: pdf, finans, medya)...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.layout.addWidget(self.search_input)

        # Scroll Area for Skill Cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container = QWidget()
        self.skills_layout = QVBoxLayout(container)
        self.skills_layout.setContentsMargins(0, 4, 0, 4)
        self.skills_layout.setSpacing(6)
        scroll_area.setWidget(container)
        self.layout.addWidget(scroll_area)

        # Reactive signal updates.
        # Doğrudan bound method'a bağlanır; `bus` süreç ömrü boyunca yaşayan bir
        # singleton olduğundan araya lambda konulmamalıdır: lambda'nın QObject
        # alıcısı olmadığı için widget silindikten sonra da çağrılmaya devam eder
        # ve "Internal C++ object already deleted" hatası üretir. Bound method'da
        # ise Qt, alıcı yok edilince bağlantıyı kendiliğinden koparır.
        bus.skills_updated.connect(self._on_skills_updated)
        bus.project_changed.connect(self._on_project_changed)
        bus.playbook_updated.connect(self._on_playbook_updated)
        bus.distill_progress.connect(self._on_distill_progress)
        # Kasaya yeni rapor düştüğünde sayaç ve düğme, uygulama yeniden
        # başlatılmadan güncellensin (ReportWatcher ya da rapor yazımı yayar).
        bus.reports_updated.connect(self._on_reports_updated)

        # Rapor izleyicisi süreç genelinde tektir ve yeniden çağrı güvenlidir.
        # Buradan başlatılır çünkü kasadaki rapor değişimini canlı görmesi
        # gereken tek yüzey bu panel; main.py bunu ayrıca çağırırsa ikinci
        # izleyici açılmaz. (Kapanışta stop_report_watcher() çağrılmalıdır.)
        try:
            from entropy.brain.report_watcher import start_report_watcher

            start_report_watcher()
        except Exception:
            pass

        self.refresh_skills()

    def _on_project_changed(self, new_dir: str):
        """Update skills directory when project changes without polluting the workspace."""
        proj_path = Path(new_dir)
        proj_skills = proj_path / "skills"
        if proj_skills.exists():
            self.skill_manager.project_skills_dir = proj_skills
            self.skill_manager.root_skills_dir = proj_skills
        else:
            self.skill_manager.project_skills_dir = None
            self.skill_manager.root_skills_dir = self.skill_manager.global_skills_dir
        self._catalog_dirty = True
        self.refresh_skills()

    # ------------------------------------------------------------ önbellek

    def _load_catalog(self) -> List[SkillDefinition]:
        """Katalog + yordam durumları; yalnızca kirliyse diskten okunur.

        İkisi de **diske gider** (SKILL.md ayrıştırma + kasa taraması) ve
        birlikte ~1,3 sn sürer; bu yüzden tek bir "kirli" bayrağına bağlıdır.
        Etkinlik durumu bu verilerin hiçbirini değiştirmez.
        """
        if not self._catalog_dirty and self._skills_cache is not None:
            return self._skills_cache
        skills = self.skill_manager.list_skills()
        states: Dict[str, Dict[str, Any]] = {}
        try:
            from entropy.brain.playbook import PlaybookStore

            store = PlaybookStore()
            for s in skills:
                try:
                    states[s.name] = store.status(s.name)
                except Exception:
                    states[s.name] = {}
        except Exception:
            pass
        self._skills_cache = skills
        self._playbook_states = states
        self._catalog_dirty = False
        return skills

    def schedule_refresh(self, dirty: bool = False) -> None:
        """Yeniden kurulumu 300 ms'de birleştirir (salvo tek turda toplanır)."""
        if dirty:
            self._catalog_dirty = True
        self._rebuild_timer.start()

    @Slot()
    def _on_skills_updated(self):
        """`bus.skills_updated` — kendi toggle yazımımızsa tam kurulum yapılmaz."""
        if self._suppress_bus_refresh:
            return
        self.schedule_refresh(dirty=True)

    @Slot()
    def _on_search_changed(self):
        # Her tuş vuruşunda tam kurulum yapmak panelde 1 sn'lik takılma
        # üretiyordu; süzgeç katalogu değiştirmez, yalnızca satırları eler.
        self.schedule_refresh(dirty=False)

    def refresh_skills(self):
        """Satırları yeniden kurar (katalog önbellekten gelir)."""
        elapsed = QElapsedTimer()
        elapsed.start()
        clear_layout(self.skills_layout)

        skills = self._load_catalog()
        filter_text = self.search_input.text().strip().lower()

        for s in skills:
            if filter_text and filter_text not in s.name.lower() and filter_text not in s.description.lower():
                continue

            card = QFrame()
            card.setProperty("role", "panel")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(12)

            icon_lbl = QLabel("<span style='font-size:18px;'></span>")
            icon_lbl.setProperty("role", "label")
            card_layout.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(3)

            status_badge = f"<span style='color:{_P["ok"]}; font-size:11px; font-weight:bold;'>● AKTİF</span>" if s.enabled else f"<span style='color:{_P["text_muted"]}; font-size:11px;'>○ PASİF</span>"
            script_badge = f"<span style='background:{_P["bg"]}; color:{_P["accent"]}; border:1px solid {_P["line_strong"]}; border-radius:3px; padding:1px 5px; font-size:11px;'>{len(s.scripts)} Araç</span>" if s.scripts else ""
            
            title_text = f"<b style='color:{_P["text"]}; font-size:13px;'>{s.name}</b> &nbsp; {status_badge} &nbsp; {script_badge}"
            name_lbl = QLabel(title_text)
            name_lbl.setObjectName(f"skill_title_{s.name}")
            name_lbl.setProperty("role", "label")

            desc_lbl = QLabel(f"<span style='color:{_P["text_muted"]}; font-size:11px;'>{s.description[:85]}</span>")
            desc_lbl.setProperty("role", "label")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            # Active toggle
            cb = QCheckBox("Etkin")
            cb.setObjectName(f"skill_toggle_{s.name}")
            cb.setAccessibleName(f"{s.name} yeteneğini etkinleştir")
            cb.setChecked(s.enabled)
            cb.toggled.connect(lambda checked, s_name=s.name: self._on_toggle(s_name, checked))
            card_layout.addWidget(cb)

            # Yordam (playbook) düğmesi: durum rozeti + damıtma tetikleyici.
            # Renk yordamın durumunu söyler: yeşil güncel, sarı bayat/yok-ama-kaynak-var,
            # gri kaynak yok. Kullanıcı hangi yeteneğin "öğrendiğini" tek bakışta görür.
            pb_state = self._playbook_states.get(s.name, {})
            state = pb_state.get("state", "kaynak-yok")
            n_src = pb_state.get("source_count", 0)
            # Faz 11-E: renk artık düz onaltılık değil, anlamsal `tone`
            # belirteci. Eşleme aynı: guncel -> ok (yeşil), kismi/bayat/yok ->
            # warn (turuncu), kaynak-yok -> nötr (gri).
            if state == "guncel":
                pb_tone = "ok"
                pb_tip = f"Yordam güncel ({pb_state.get('distilled_from', 0)} rapordan)"
            elif state in ("bayat", "hafif-degisim"):
                pb_tone = "warn"
                pb_tip = f"Yordam bayat: {n_src} rapor var, yeniden damıtılabilir"
            elif state == "yok":
                pb_tone = "warn"
                pb_tip = f"Yordam yok, {n_src} rapor damıtılmayı bekliyor"
            elif state == "kismi":
                # Kısmi damıtma (ya da yeni/değişmiş rapor): turuncu; önceden bu durum
                # "kaynak yok" dalına düşüp gri görünüyor, düğme kapalı sanılıyordu.
                pb_tone = "warn"
                pb_tip = (
                    f"Yordam kısmi: {pb_state.get('distilled_from', 0)}/{n_src}"
                    " rapor okundu; damıtma kaldığı yerden sürer"
                )
            else:
                pb_tone = "muted"
                pb_tip = "Kaynak rapor yok; damıtılacak bir şey yok"

            # İki ayrı eylem. "Damıt" artımlıdır: yalnızca okunmamış raporları
            # işler. Okunmamış yoksa düğme kapanır ve kullanıcı "Tazele"yi bilerek
            # seçer — tek düğme olduğunda "Damıt" sessizce tüm arşivi yeniden
            # okutuyordu (513 raporda ~20 tur AGY kotası).
            unread = max(0, n_src - pb_state.get("distilled_from", 0))
            pb_btn = QPushButton("" if not unread else f"{unread}")
            pb_btn.setObjectName(f"distill_btn_{s.name}")
            pb_btn.setMinimumWidth(26)
            pb_btn.setToolTip(
                f"{pb_tip}\n"
                + (f"Tıkla: {unread} yeni raporu damıt (artımlı, AGY kotası harcar)"
                   if unread else "Okunmamış rapor yok; tazelemek için düğmesini kullan")
            )
            pb_btn.setAccessibleName(f"{s.name}: yeni raporları damıt")
            pb_btn.setProperty("role", "icon")
            pb_btn.setProperty("tone", pb_tone)
            apply_row_icon(pb_btn, "distill", pb_tone)
            pb_btn.setEnabled(self.bridge is not None and unread > 0)
            pb_btn.clicked.connect(lambda _, s_name=s.name, s_desc=s.description: self._on_distill(s_name, s_desc))
            card_layout.addWidget(pb_btn)

            rf_btn = QPushButton("")
            rf_btn.setObjectName(f"refresh_btn_{s.name}")
            rf_btn.setProperty("role", "icon")
            rf_btn.setToolTip(
                f"Tazele: '{s.name}' için {n_src} raporun TAMAMI yeniden okunur.\n"
                "Pahalıdır; yalnızca yordamın bozulduğunu düşünüyorsan kullan."
            )
            rf_btn.setAccessibleName(f"{s.name}: yordamı tazele (tüm arşiv)")
            rf_btn.setProperty("role", "icon")
            rf_btn.setProperty("tone", pb_tone)
            apply_row_icon(rf_btn, "refresh", pb_tone)
            rf_btn.setEnabled(self.bridge is not None and n_src > 0)
            rf_btn.clicked.connect(
                lambda _, s_name=s.name, s_desc=s.description: self._on_distill(s_name, s_desc, refresh=True)
            )
            card_layout.addWidget(rf_btn)

            # İlerleme sayacı: damıtılan/toplam. Yalnızca kaynak varsa gösterilir;
            # tamamlanınca yeşil, kısmi/bayat iken sarı.
            if n_src > 0:
                done = pb_state.get("distilled_from", 0)
                counter = QLabel(f"{done}/{n_src}")
                counter.setObjectName(f"distill_counter_{s.name}")
                counter.setToolTip("Damıtılan rapor / toplam rapor")
                counter.setProperty("role", "badge")
                counter.setProperty("tone", pb_tone)
                card_layout.addWidget(counter)

            # Edit button: SKILL.md'yi uygulama içi editörde açar
            edit_btn = QPushButton("")
            edit_btn.setAccessibleName("SKILL.md dosyasını düzenle")
            edit_btn.setObjectName(f"skill_edit_{s.name}")
            edit_btn.setProperty("role", "icon")
            edit_btn.setToolTip("SKILL.md dosyasını düzenle (uygulama içi editör / sistem editörü)")
            apply_row_icon(edit_btn, "edit")
            edit_btn.clicked.connect(lambda _, s_name=s.name, s_path=s.path: self._on_edit_skill(s_name, s_path))
            card_layout.addWidget(edit_btn)

            # Open folder button
            folder_btn = QPushButton("")
            folder_btn.setAccessibleName("Yetenek Klasörünü Aç")
            folder_btn.setObjectName(f"skill_folder_{s.name}")
            folder_btn.setProperty("role", "icon")
            folder_btn.setToolTip("Yetenek Klasörünü Aç")
            apply_row_icon(folder_btn, "folder")
            folder_btn.clicked.connect(lambda _, s_path=s.path: self._open_folder(Path(s_path).parent))
            card_layout.addWidget(folder_btn)

            # Delete button
            del_btn = QPushButton("")
            del_btn.setAccessibleName("Yeteneği Sil")
            del_btn.setProperty("role", "icon")
            del_btn.setToolTip("Yeteneği Sil")
            apply_row_icon(del_btn, "delete", "danger")
            del_btn.clicked.connect(lambda _, s_name=s.name: self._on_delete(s_name))
            card_layout.addWidget(del_btn)

            self.skills_layout.addWidget(card)

        self.skills_layout.addStretch()
        self.last_rebuild_ms = elapsed.elapsed()

    @Slot()
    def reload_from_disk(self):
        """"Yenile" düğmesi: önbelleği ATAR, katalogu ve yordam durumlarını
        diskten yeniden okur. Kullanıcının bilerek beklemeyi kabul ettiği tek yol."""
        self._catalog_dirty = True
        self.refresh_skills()

    def _filter_skills(self):
        """Geriye dönük ad (testler kullanıyor); süzgeç birleştirilir."""
        self.schedule_refresh(dirty=False)

    def _on_distill(self, skill_name: str, description: str = "", refresh: bool = False):
        """
        Seçilen yetenek için yordam damıtmayı arka planda başlatır.

        refresh=False (): yalnızca okunmamış raporlar işlenir.
        refresh=True  (): tüm arşiv yeniden okunur — ayrı ve açık bir eylem.
        """
        if self.bridge is None:
            QMessageBox.information(self, "Yordam Damıtma", "Damıtma için AGY köprüsü gerekli; bu panel köprüsüz açılmış.")
            return
        from entropy.brain.distiller import PlaybookDistiller

        if skill_name in PlaybookDistiller.active_skills():
            QMessageBox.information(
                self, "Yordam Damıtma", f"'{skill_name}' için damıtma zaten sürüyor; ikinci zincir açılmadı."
            )
            return

        distiller = PlaybookDistiller()
        plan = distiller.plan(skill_name)
        if plan["sources_total"] == 0:
            QMessageBox.information(self, "Yordam Damıtma", f"'{skill_name}' için kaynak rapor yok.")
            return

        unread = distiller.unread_count(skill_name)
        if not refresh and unread == 0:
            QMessageBox.information(
                self,
                "Yordam Damıtma",
                f"'{skill_name}' için okunmamış rapor yok ({plan['sources_total']} rapor işlenmiş).\n\n"
                "Tüm arşivi yeniden okutmak istiyorsan (Tazele) düğmesini kullan.",
            )
            return

        if refresh:
            title, detail = (
                "Yordam Tazeleme",
                f"'{skill_name}' için {plan['sources_total']} raporun TAMAMI yeniden okunacak "
                f"(~{plan['estimated_total_tokens']:,} token, {plan['estimated_total_passes']} tur; AGY kotası harcar).",
            )
        else:
            title, detail = (
                "Yordam Damıtma",
                f"'{skill_name}' için {unread} yeni rapor işlenecek; bu turda "
                f"{plan['sources_this_pass']} tanesi (~{plan['estimated_prompt_tokens']:,} token, AGY kotası harcar).",
            )

        answer = QMessageBox.question(
            self,
            title,
            f"{detail}\n\nArka planda çalışır; bitince Skills/<yetenek>/PLAYBOOK.md yazılır.\n\nBaşlatılsın mı?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        started = distiller.run_via_bridge(
            self.bridge, skill_name, description=description or "", allow_refresh=refresh
        )
        if started and not started.get("already_running"):
            bus.terminal_output_received.emit(
                f"[Damıtma] '{skill_name}' başlatıldı: {started['sources']} rapor, ~{started['prompt_tokens']:,} token.\n"
            )

    def _on_playbook_updated(self, _skill_name: str):
        self.schedule_refresh(dirty=True)

    def _on_reports_updated(self, _skill_name: str = ""):
        """Kaynak raporlar değişti: durum yeniden hesaplanmalı (sayaç/düğme canlı)."""
        try:
            from entropy.brain.playbook import clear_file_facts_cache

            clear_file_facts_cache()
        except Exception:
            pass
        self.schedule_refresh(dirty=True)

    def _on_distill_progress(self, skill_name: str, done: int, total: int):
        """Tur bittiğinde sayaç tam yenileme beklemeden güncellenir."""
        counter = self.findChild(QLabel, f"distill_counter_{skill_name}")
        if counter is not None:
            counter.setText(f"{done}/{total}")
            counter.setProperty("role", "badge")
            counter.setProperty("tone", "ok" if done >= total else "warn")
            repolish(counter)

    def _on_toggle(self, skill_name: str, enabled: bool):
        """"Etkin" kutusu: YALNIZCA durumu yazar ve o satırın rozetini çevirir.

        Faz 13-A2 madde 1'in kök nedeni buradaydı: eskiden hem doğrudan
        `refresh_skills()` çağrılıyor hem de `toggle_skill` içindeki
        `bus.skills_updated` ikinci bir tam kurulumu tetikliyordu; her kurulum
        22 SKILL.md ayrıştırması + 22 kasa taraması demekti (ölçüm: 1.961 ms,
        gerçek ekranda "yanıt vermiyor"). Etkinlik durumu ne katalogu ne de
        yordam durumunu değiştirdiği için ikisine de gerek yok.
        """
        elapsed = QElapsedTimer()
        elapsed.start()
        self._suppress_bus_refresh = True
        try:
            self.skill_manager.toggle_skill(skill_name, enabled)
        finally:
            self._suppress_bus_refresh = False
        # Önbellekteki tanım da döner: sonraki kurulum doğru kutuyu çizsin.
        for skill in (self._skills_cache or []):
            if skill.name == skill_name:
                try:
                    skill.enabled = enabled
                except Exception:
                    pass
                break
        self._update_row_state(skill_name, enabled)
        self.last_toggle_ms = elapsed.elapsed()

    def _update_row_state(self, skill_name: str, enabled: bool) -> None:
        """Tek satırın AKTİF/PASİF rozetini yerinde günceller (kurulum yok)."""
        label = self.findChild(QLabel, f"skill_title_{skill_name}")
        if label is None:
            return
        text = label.text()
        active = (
            f"<span style='color:{_P["ok"]}; font-size:11px;"
            f" font-weight:bold;'>● AKTİF</span>"
        )
        passive = (
            f"<span style='color:{_P["text_muted"]}; font-size:11px;'>"
            f"○ PASİF</span>"
        )
        label.setText(text.replace(passive, active) if enabled else text.replace(active, passive))

    def _on_delete(self, skill_name: str):
        reply = QMessageBox.question(
            self,
            "Yeteneği Sil",
            f"'{skill_name}' yeteneğini ve araç dosyalarını kalıcı olarak silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.skill_manager.delete_skill(skill_name)
            self._catalog_dirty = True
            self.refresh_skills()

    def _on_edit_skill(self, skill_name: str, skill_path: str):
        """SKILL.md'yi uygulama içi editörde açar; dosya yoksa klasörü açar."""
        path = Path(skill_path)
        if path.is_dir():
            path = path / "SKILL.md"
        if not path.exists():
            QMessageBox.warning(self, "Dosya Yok", f"'{skill_name}' için SKILL.md bulunamadı:\n{path}")
            return None
        dlg = SkillEditorDialog(path, skill_name, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._catalog_dirty = True
            self.refresh_skills()
        return dlg

    def _open_folder(self, folder_path: Path):
        if folder_path.exists():
            if os.name == "nt":
                os.startfile(str(folder_path))
            else:
                subprocess.run(["xdg-open", str(folder_path)])

    def _open_add_dialog(self):
        dlg = AddSkillDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, desc, inst = dlg.get_data()
            self.skill_manager.create_skill(name, desc, inst)
            QMessageBox.information(self, "Başarılı", f"'{name}' yeteneği başarıyla oluşturuldu!")
            self._catalog_dirty = True
            self.refresh_skills()

    def _open_download_dialog(self):
        dlg = DownloadSkillDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            url, custom_name = dlg.get_data()
            skill = self.skill_manager.download_skill_from_url(url, custom_name)
            if skill:
                QMessageBox.information(self, "Başarılı", f"'{skill.name}' yeteneği internetten başarıyla indirildi!")
                self._catalog_dirty = True
                self.refresh_skills()
            else:
                QMessageBox.critical(self, "Hata", "Yetenek URL'den indirilemedi. Lütfen bağlantıyı kontrol edin.")

    def closeEvent(self, event):
        try:
            bus.skills_updated.disconnect(self._on_skills_updated)
        except Exception:
            pass
        try:
            bus.project_changed.disconnect(self._on_project_changed)
        except Exception:
            pass
        super().closeEvent(event)
