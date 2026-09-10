"""
Ajan önyüklemesi: açılışta ve proje değiştiğinde koşan tek giriş noktası.

Daha önce bu mantık `entropy.main` içinde gömülüydü ve test edilemiyordu:
istisnalar `print` ile yutuluyor, pencereli derlemede stderr olmadığı için
derlemenin hiç koşmadığı ancak diske bakılarak anlaşılıyordu. Ayrıca
paketlenmiş sürümde `APP_ROOT` .exe'nin klasörü (`dist/EntropyAI`) olduğundan
üretilen tanımlar gerçek proje kökünde görünmüyordu.

Sözleşme:
- `ensure_defaults()` ÖNCE koşar (tohum ajanlar diske düşer), derleme SONRA;
  aksi hâlde ilk açılışta hiçbir şey derlenmezdi.
- Derleme yalnızca kayıt defterindeki adlar için dosya yazar; başka bir ajanı
  (kullanıcının elle yazdığı `.claude/agents/*.md` ya da `.agents/agents/distiller`)
  ne siler ne de değiştirir.
- Her adım loglanır; hata önyüklemeyi durdurmaz.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    """Önyükleme özeti; çağıran (UI/terminal) bunu kullanıcıya basar."""

    created: List[str] = field(default_factory=list)
    # Faz 6: tohum ofis yok; hazırlanan (orkestratörü + derlemesi
    # doğrulanan) ofislerin adları.
    offices_ready: List[str] = field(default_factory=list)
    compiled: Dict[str, Dict[str, Path]] = field(default_factory=dict)
    roots: List[Path] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        if self.error:
            return f"Ajan önyüklemesi başarısız: {self.error}"
        parts = []
        if self.created:
            parts.append(f"varsayılan ajanlar oluşturuldu: {', '.join(self.created)}")
        if self.offices_ready:
            parts.append(f"ofisler hazır: {', '.join(self.offices_ready)}")
        if self.compiled:
            parts.append(
                f"{len(self.compiled)} ajan derlendi ({', '.join(sorted(self.compiled))}) "
                f"-> {', '.join(str(r) for r in self.roots)}"
            )
        return "; ".join(parts) or "derlenecek ajan yok"


@dataclass
class DispatchStartResult:
    """Açılış kablolamasının özeti (`start_board_dispatch`)."""

    recovered: List[str] = field(default_factory=list)
    started: bool = False
    dispatcher: object = None
    error: Optional[str] = None

    def summary(self) -> str:
        if self.error:
            return f"Pano tetikleyicisi başlatılamadı: {self.error}"
        parts = []
        if self.recovered:
            parts.append(f"asılı kalan {len(self.recovered)} kart kuyruğa alındı")
        parts.append("tetikleyici açık" if self.started else "tetikleyici kapalı (ayar)")
        return "; ".join(parts)


def start_board_dispatch(app=None) -> DispatchStartResult:
    """
    Açılış kablolaması: **önce uzlaştır, sonra turu başlat** (Faz 11-C).

    Sıra bilinçli: uzlaştırma olmadan önceki oturumda yarım kalan
    `taken`/`running` kartlar sonsuza dek kilitli kalır (kilidin sahibi ölü bir
    PID) ve ilk tur onları göremez. Tur `config.board_auto_dispatch` ile
    kapatılabilir; uzlaştırma HER HÂLÜKÂRDA koşar çünkü model çağırmaz ve
    "sessiz açılış" isteyen kullanıcı da asılı kart istemez.

    `app` verilirse (QApplication) kapanış kancası `aboutToQuit`e takılır:
    zamanlayıcı süreçten önce durmalı, yoksa kapanış sırasında yeni bir tur
    kart başlatabilir.
    """
    from entropy.agents.dispatcher import board_dispatcher

    result = DispatchStartResult()
    try:
        dispatcher = board_dispatcher()
        result.dispatcher = dispatcher
        result.recovered = list(dispatcher.reconcile() or [])
        result.started = bool(dispatcher.start())
        if app is not None:
            about = getattr(app, "aboutToQuit", None)
            if about is not None:
                about.connect(dispatcher.stop)
    except Exception as exc:
        result.error = str(exc)
        logger.exception("Pano tetikleyicisi başlatılamadı")
    return result


def ensure_memory_tasks(scheduler=None) -> Optional[str]:
    """
    Gece konsolidasyonunu (`daily-dreaming`) açılışta garanti eder (Faz 11-D).

    `memory.dream.ensure_daily_dreaming_task` yazılmıştı ama ÜRÜNDE HİÇBİR
    ÇAĞIRANI YOKTU (QA 11-C/D bulgusu): görev yalnızca eski kurulumlarda
    `scheduler_tasks.json` içinde duruyordu, temiz kurulumda rüya döngüsü hiç
    zamanlanmıyordu. Kayıt idempotenttir ve **model çağırmaz**; hata
    önyüklemeyi durdurmaz.

    Dönüş: kaydedilen görev kimliği ya da None.
    """
    try:
        from entropy.brain.dream import DAILY_DREAM_TASK_ID, ensure_daily_dreaming_task
    except Exception:
        logger.debug("Rüya modülü yok; gece konsolidasyonu kaydedilmedi", exc_info=True)
        return None
    try:
        task = ensure_daily_dreaming_task(scheduler)
    except Exception:
        logger.exception("Gece konsolidasyonu kaydedilemedi")
        return None
    return DAILY_DREAM_TASK_ID if task is not None else None


def stop_board_dispatch() -> bool:
    """Kapanış: tetikleyiciyi durdurur (kanca takılamadıysa elle çağrılır)."""
    try:
        from entropy.agents.dispatcher import board_dispatcher

        dispatcher = board_dispatcher(create=False)
        if dispatcher is None:
            return False
        dispatcher.stop()
        return True
    except Exception:
        logger.debug("Tetikleyici durdurulamadı", exc_info=True)
        return False


def bootstrap_agents(
    project_dir: Optional[Path | str] = None,
    vault_path: Optional[Path | str] = None,
) -> BootstrapResult:
    """
    Tohum ajanları garanti eder ve tüm ajanları sağlayıcı biçimlerine derler.

    `project_dir` None/geçersizse derleme yine de uygulama köküne ve ayarlardaki
    etkin projeye yazar (bkz. `compile_roots`), yani hiçbir durumda sessizce
    atlanmaz.
    """
    from entropy.agents.compile import compile_roots
    from entropy.agents.desk_registry import DeskRegistry
    from entropy.agents.registry import AgentRegistry

    result = BootstrapResult()
    try:
        registry = AgentRegistry(vault_path=vault_path)
        result.created = registry.ensure_defaults()
        if result.created:
            logger.info("Varsayılan ajanlar oluşturuldu: %s", ", ".join(result.created))
        # Desk ofisleri TOHUMLANMAZ (Faz 6, kural 2): ofisi kullanıcı açar.
        # Yapılan tek şey, var olan her ofisin orkestratörünü ve derlemesini
        # garanti etmek — kasadan elle silinmiş bir orkestratör ofisi sessizce
        # işlevsiz bırakıyordu.
        desk = DeskRegistry(vault_path=vault_path)
        # Eski `Entropy/Offices` kurulumunun taşınması bellek ajanının işi;
        # modül yoksa (ya da taşınacak bir şey yoksa) sessizce atlanır. Açılışta
        # bir kez koşar: taşıma işlevi kendi içinde tekrarlanabilir olmalı.
        try:
            from entropy.brain.office_graph import migrate_legacy_offices  # type: ignore
        except Exception:
            migrate_legacy_offices = None  # type: ignore
        if migrate_legacy_offices is not None:
            try:
                moved = migrate_legacy_offices(vault_path=vault_path)
                if moved:
                    logger.info("Eski ofisler taşındı: %s", moved)
            except Exception:
                logger.warning("Eski ofis taşıması başarısız", exc_info=True)
        for office in desk.list():
            try:
                desk.ensure_orchestrator(office.name)
                desk.compile_office(office.name)
                result.offices_ready.append(office.name)
            except Exception:
                logger.warning("Ofis hazırlanamadı: %s", office.name)
        # Faz 10-D: takip turu özetlerini kart notlarına yazan dinleyici.
        # Bir kez bağlanır; bağlanmazsa etkileşimli turlar hiçbir yerde iz
        # bırakmazdı (ledger toplamı köprüde, insan okuyacak özet burada).
        try:
            from entropy.agents.tasks import connect_followup_recorder

            connect_followup_recorder(vault_path=vault_path)
        except Exception:
            logger.warning("Takip turu dinleyicisi bağlanamadı.", exc_info=True)
        result.roots = compile_roots(project_dir)
        result.compiled = registry.compile_all(project_dir)
        logger.info(
            "Ajan derlemesi: %d ajan, kökler=%s",
            len(result.compiled),
            [str(r) for r in result.roots],
        )
    except Exception as exc:  # önyükleme uygulamayı düşürmemeli
        result.error = str(exc)
        logger.exception("Ajan önyüklemesi başarısız")
    return result
