"""Entropy AI Application Entry Point."""

import argparse
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

import entropy.core.config  # noqa: F401  (alt modülün yüklenmesi için)
from entropy.core.config import config

# `import entropy.core.config as m` MODÜLÜ değil config NESNESİNİ bağlar
# (entropy/core/__init__.py adı yeniden dışa aktarıyor); modül yalnızca
# sys.modules üzerinden güvenle alınır.
config_module = sys.modules["entropy.core.config"]
from entropy.core.provider import create_bridge
from entropy.scheduler.cron_engine import TaskScheduler
from entropy.ui.manager import EntropyUIManager

def main():
    parser = argparse.ArgumentParser(description="Entropy AI Agentic Desktop Operating System")
    parser.add_argument("--mode", choices=["zen", "floating", "chat"], default=None, help="Initial desktop mode")
    parser.add_argument("--project", default=None, help="Project directory to mount")
    # Sürümün tek kaynağı pyproject.toml (entropy.__version__ oradan türer).
    from entropy import __app_name__, __version__

    parser.add_argument("--version", action="version",
                        version=f"{__app_name__} {__version__}")
    args = parser.parse_args()

    # Pencereli derlemede stderr yok: kapanış nedenleri ancak dosyaya yazılırsa görülür.
    from entropy.core.config import STATE_DIR
    from entropy.core.crash_log import install_crash_logging
    install_crash_logging(STATE_DIR / "logs")

    # Faz 6: yuksek DPI'da olcek yuvarlanmasi (125%/150%) pencere boyutlarini
    # ekran disina tasiriyordu. PassThrough ile olcek yuvarlanmaz; QApplication
    # kurulmadan once ayarlanmali, sonrasinda etkisizdir.
    if QApplication.instance() is None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setQuitOnLastWindowClosed(False)

    # Faz 9: uygulama font zincirine emoji yedegi. Kullanicinin sisteminde
    # "Segoe UI Emoji" OpenType olarak cozulemedigi icin (gunlukte 176 satir
    # `OpenType support missing`) rozetlerdeki emojiler ici bos kutu (tofu)
    # ciziliyordu -- ust cubuktaki "bos kirmizi kare" buydu.
    from entropy.ui.widgets.ui_polish import apply_emoji_font_fallback
    apply_emoji_font_fallback(app)

    # Tek kopya: zaten çalışan bir kopya varsa onu öne getirip çık. Pencere
    # kapatılınca süreç tepside yaşadığı için ikinci başlatmalar aynı belleği
    # paylaşan kopyalar üretiyor ve donmaya yol açıyordu.
    from entropy.core.single_instance import SingleInstanceGuard
    guard = SingleInstanceGuard(parent=app)
    if not guard.try_acquire():
        guard.notify_existing()
        print(f"[{config.app_name}] Zaten çalışıyor; mevcut pencere öne getirildi.")
        return 0

    icon_path = Path.cwd() / "entropy.ico"
    if not icon_path.exists():
        icon_path = Path(__file__).resolve().parents[2] / "entropy.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Initialize Core Bridge & Scheduler
    # Köprü artık doğrudan kurulmaz: hangi CLI'ın (agy / claude) kullanılacağı
    # ayarlardan gelir ve fabrika o sağlayıcının köprüsünü üretir.
    bridge = create_bridge(config)
    print(f"[{config.app_name}] Sağlayıcı: {getattr(bridge, 'provider_name', 'agy')} "
          f"(model: {bridge.selected_model})")
    if args.project:
        bridge.set_project_directory(args.project)
    elif config_module.is_bundle_dir(bridge.active_project_dir):
        # Paketlenmiş sürümde proje kökü .exe klasörüne düşmüş: ajan orada
        # kendi paket artıklarını (`_internal/AGENTS.md`, `_internal/skills`)
        # gerçek proje sanıyordu. Nötr çalışma alanına al; kullanıcı gerçek
        # projeyi üst çubuktaki "Proje" düğmesiyle seçer.
        bridge.set_project_directory(config_module.default_workspace_root())

    # Önceki oturum bir arka plan görevi sürerken kapandıysa ledger'da o satır
    # sonsuza dek RUNNING kalıyordu; görev panelinde hayalet iş olarak görünüyordu.
    from entropy.core.task_ledger import task_ledger
    orphaned = task_ledger.mark_orphans_failed()
    if orphaned:
        print(f"[{config.app_name}] Önceki oturumdan yarım kalan {orphaned} görev kapatıldı.")

    # Yetenek dizinleri canlı izlenir: internetten indirilen ya da başka bir CLI
    # tarafından yazılan bir SKILL.md, uygulama yeniden başlatılmadan panelde ve
    # `/` komut listesinde belirsin (bus.skills_updated).
    from entropy.skills.manager import start_skill_watcher
    start_skill_watcher(project_dir=bridge.active_project_dir)

    # Kasadaki rapor dosyaları (Obsidian vault) da canlı izlenir: bir alt ajan
    # rapor yazdığında yetenek kartındaki 📘 sayacı yeniden başlatmadan güncellensin
    # (bus.reports_updated).
    from entropy.memory.report_watcher import start_report_watcher, stop_report_watcher
    try:
        start_report_watcher()
    except Exception as e:
        print(f"[{config.app_name}] Rapor izleyici başlatılamadı: {e}")

    # Ajan kayıt defteri: kasadaki AGENT.md dosyaları iki sağlayıcının biçimine
    # derlenir. Açılışta ve proje değiştiğinde koşar; agy/claude ajan tanımlarını
    # SÜRECİN ÇALIŞMA DİZİNİNE göre keşfettiği için proje değişince yeni kökte de
    # bulunmaları gerekiyor. Derleme, kaynak değişmemişse dosyaya dokunmaz.
    from entropy.agents.bootstrap import bootstrap_agents
    from entropy.agents.watchers import start_agent_watchers, stop_agent_watchers

    def _compile_agents(project_dir=None):
        result = bootstrap_agents(project_dir or bridge.active_project_dir)
        print(f"[{config.app_name}] {result.summary()}")

    _compile_agents()
    from entropy.core.event_bus import bus as _bus
    _bus.project_changed.connect(_compile_agents)

    # Ajan tanımları ve görev kartları kasada canlı izlenir: kullanıcı Obsidian'da
    # bir kart yazdığında ya da bir ajan gövdesini düzenlediğinde panel yeniden
    # başlatmadan güncellenir (bus.agents_updated / bus.task_cards_updated).
    try:
        start_agent_watchers()
    except Exception as e:
        print(f"[{config.app_name}] Ajan izleyicileri başlatılamadı: {e}")

    # Posta kutuları (Faz 5): ofis/ajan/Entropy gelen kutularını izler ve
    # değişimde bus.mailbox_updated yayar. QFileSystemWatcher + yoklama birlikte
    # çünkü kasa çoğu kurulumda OneDrive altında ve yalnız izleyici olay kaçırıyor.
    mailbox_watcher = None
    try:
        from entropy.agents.mailbox import MailboxWatcher

        mailbox_watcher = MailboxWatcher()
        mailbox_watcher.start()
    except Exception as e:
        print(f"[{config.app_name}] Posta kutusu izleyicisi başlatılamadı: {e}")

    # Kimlik/durum katmanı: giriş, hesap, kota ipucu. Problar model ÇAĞIRMAZ
    # (claude auth status --json / agy models), bu yüzden açılışta koşmaları
    # kota harcamaz.
    try:
        from entropy.core.identity import identity

        identity.start()
    except Exception as e:
        print(f"[{config.app_name}] Kimlik katmanı başlatılamadı: {e}")

    # Ofis zincirleri kesintiden sürer: uygulama kapandığında köprü süreçleri
    # ölüyor ama kart dosyalarında durum `running` kalıyordu. Model çağrısı
    # ürettiği için ayarla kapatılabilir (config.desk_auto_resume).
    if getattr(config, "desk_auto_resume", True):
        try:
            from entropy.agents.harness import OfficeHarness
            resumed = OfficeHarness.resume_all()
            if resumed:
                print(f"[{config.app_name}] Yarım kalan {len(resumed)} ofis kartı sürdürüldü.")
        except Exception as e:
            print(f"[{config.app_name}] Ofis zincirleri sürdürülemedi: {e}")

    # Pano tetikleyicisi (Faz 11-C.2): önce UZLAŞTIR, sonra turu başlat.
    # Uzlaştırma olmadan önceki oturumda yarım kalan `taken`/`running` kartlar
    # sonsuza dek kilitli kalıyordu (kilidin sahibi ölü bir PID). Turun kendisi
    # `config.board_auto_dispatch` ile kapatılabilir: her tur potansiyel bir
    # model çağrısıdır ve kullanıcı uygulamayı "sessiz" açabilmeli.
    from entropy.agents.bootstrap import start_board_dispatch, stop_board_dispatch

    dispatch = start_board_dispatch(app)
    print(f"[{config.app_name}] Pano: {dispatch.summary()}")

    scheduler = TaskScheduler.get_instance()

    # Faz 11-D: gece konsolidasyonu (`daily-dreaming`) idempotent kaydedilir.
    from entropy.agents.bootstrap import ensure_memory_tasks

    ensure_memory_tasks(scheduler)

    def handle_scheduled_task(task):
        from entropy.core.event_bus import bus
        if task.id == "daily-dreaming":
            try:
                from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                cog = CognitiveMemorySystem()
                # Faz 11-D: rüya döngüsü v2 (`memory.dream`). Eski
                # `CognitiveMemorySystem.dream_and_consolidate` 48 saat +
                # epizodik koşuluna bağlıydı, zamanlanmış görev çoğu gece boş
                # dönüyordu. `send_prompt=None` → bu adım KOTA HARCAMAZ;
                # model sentezi aşağıdaki arka plan görevidir.
                try:
                    from entropy.memory.dream import dream_and_consolidate

                    rules = dream_and_consolidate(memory=cog, send_prompt=None)
                except Exception:
                    rules = cog.dream_and_consolidate()
                detail = getattr(rules, "summary", None)
                detail = detail() if callable(detail) else (
                    f"{len(rules)} özet" if hasattr(rules, "__len__") else str(rules))
                bus.terminal_output_received.emit(
                    f"[Otonom Görev] Hafıza konsolidasyonu tamamlandı ({' '.join(str(detail).split())[:300]}).\n")

                # Gerçek sentez AGY ile, arka planda: ledger'a kaydolur, sohbeti kilitlemez.
                # Çıktı rapor arşivine değil doğrudan bilişsel belleğe yazılır.
                consolidation_prompt = cog.build_consolidation_prompt()
                if consolidation_prompt:
                    def _store(full_text: str, ok: bool, _cog=cog):
                        if ok and _cog.store_consolidation(full_text):
                            bus.terminal_output_received.emit("[Otonom Görev] AGY konsolidasyonu belleğe işlendi.\n")
                            bus.cognitive_memory_updated.emit()

                    bridge.send_background_task_async(
                        task_id=f"consolidate-{int(__import__('time').time())}",
                        task_name="Bilişsel Konsolidasyon",
                        prompt=consolidation_prompt,
                        mode="accept-edits",  # "plan" modu keşif/plan döngüsü tetikliyor (bkz. distiller)
                        on_result=_store,
                        save_report=False,
                    )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.id == "obsidian-sync":
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                log_p = ovm.append_daily_log("Otonom arka plan senkronu.")
                moc_p = ovm.sync_map_of_content()
                bus.terminal_output_received.emit(f"[Otonom Görev] Obsidian günlüğü ve {moc_p.name} senkronlandı.\n")
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.id == "rag-reindex":
            try:
                from entropy.memory.rag.project_indexer import ProjectIndexer
                indexer = ProjectIndexer(config.default_project_path)
                cnt = indexer.scan_and_index()
                bus.terminal_output_received.emit(f"[Otonom Görev] Proje kodları indekslendi ({cnt} dosya).\n")
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.prompt:
            bridge.send_prompt_async(task.prompt)

    scheduler.set_execution_callback(handle_scheduled_task)
    scheduler.start()

    # Launch UI Manager
    ui_manager = EntropyUIManager(bridge=bridge)
    initial_mode = args.mode or config.default_mode
    ui_manager.switch_mode(initial_mode)
    guard.activated.connect(ui_manager.bring_to_front)

    # Kapanış kancası: tepsiden çıkış, son pencerenin kapatılması ve tek kopya
    # devri yollarının hepsi burada birleşir. Kanca olmadan çalışan agy süreçleri
    # (ve altlarındaki language_server ağacı) öksüz kalıyor, ledger satırları
    # sonsuza dek RUNNING görünüyordu. Bütçe 3 sn: kapanış donmamalı.
    def _on_quit():
        try:
            stats = bridge.shutdown(timeout=3.0)
            if stats.get("processes") or stats.get("tasks"):
                print(f"[{config.app_name}] Kapanış: {stats['processes']} süreç sonlandırıldı, "
                      f"{stats['tasks']} görev iptal edildi.")
        except Exception as e:
            print(f"[{config.app_name}] Kapanış temizliği hatası: {e}")
        try:
            stop_report_watcher()
        except Exception:
            pass
        try:
            stop_agent_watchers()
        except Exception:
            pass
        try:
            if mailbox_watcher is not None:
                mailbox_watcher.stop()
        except Exception:
            pass
        try:
            from entropy.core.identity import identity

            identity.stop()
        except Exception:
            pass
        try:
            scheduler.stop()
        except Exception:
            pass
        try:
            stop_board_dispatch()
        except Exception:
            pass

    app.aboutToQuit.connect(_on_quit)

    print(f"[{config.app_name}] Started in {initial_mode.upper()} mode.")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
