"""
BoardDispatcher — panoyu ÇEKMELİ tetikleyici (Faz 11-C.2).

Yön değişikliği
---------------
Faz 11 öncesi kartı hep bir insan ya da harness İTİYORDU: `/task` kartı
oluşturduğu satırda `board.run(card.id)` diyordu, yani `backlog` durumu hiç
beklemiyor ve pano bir kuyruk değil bir kayıt defteri gibi çalışıyordu.
Artık `/task` kartı YALNIZCA oluşturur (`backlog`/`assigned`); koşturmayı bu
tetikleyici yapar ve her tur "panoda sana atanmış kart var mı" diye sorar.

Atomik sahiplenme
-----------------
İki turun (ya da iki uygulama örneğinin) aynı kartı almasını engelleyen tek
şey `claims/<id>.lock` dosyasının `O_CREAT|O_EXCL` ile açılmasıdır — "yoksa
oluştur" ilkelinin taşınabilir hâli. kanban-md'nin Unix'te kullandığı "kart
dosyasını salt-okunur yap" numarası Windows'ta güvenilir değil (ACL'ler ve
OneDrive senkronu araya girer), üstelik kart Obsidian'da açıkken sahiplenmeyi
kilitlerdi. Kilit AYRI dosyada: kart dosyasına dokunulmaz.

Qt bağımlılığı
--------------
Çekirdek (`BoardDispatcherCore`) Qt'siz ve saf Python; testler ve başsız koşu
onu doğrudan kullanır. `BoardDispatcher` yalnızca ince bir `QTimer` sarmalıdır.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.core import paths as _paths
from entropy.agents import board_fsm

logger = logging.getLogger(__name__)

# Kira süresi: sahiplenilmiş ama koşmayan kart bu süre sonunda serbest kalır.
DEFAULT_CLAIM_TIMEOUT_S = 3600
# Tur aralığı: `_VaultWatcher`ın 5 sn'lik yoklamasıyla aynı büyüklük.
DEFAULT_INTERVAL_S = 3
# Entropy panosunun eşzamanlı koşu tavanı.
DEFAULT_MAX_PARALLEL = 2

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "": 3}


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def pid_alive(pid: int) -> bool:
    """
    PID canlı mı (Windows dâhil).

    `os.kill(pid, 0)` POSIX'te ilkel yol; Windows'ta Python bunu
    `OpenProcess` üzerinden taklit eder ve ölü PID için `OSError` verir.
    Belirsizlik durumunda CANLI kabul edilir: yanlışlıkla devralıp aynı kartı
    iki kez koşturmak, bir saat beklemekten pahalıdır.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class ClaimStore:
    """`Entropy/Board/claims/<id>.lock` kiralarının okuma/yazma yüzeyi."""

    def __init__(self, vault_path: Optional[Path | str] = None,
                 timeout_s: int = DEFAULT_CLAIM_TIMEOUT_S):
        self.vault_path = Path(vault_path) if vault_path is not None else None
        self.timeout_s = int(timeout_s or DEFAULT_CLAIM_TIMEOUT_S)

    @property
    def dir(self) -> Path:
        return _paths.board_claims_dir(self.vault_path)

    def path_for(self, card_id: str) -> Path:
        safe = "".join(ch if (ch.isalnum() or ch in "-_.") else "-"
                       for ch in str(card_id or ""))
        return self.dir / f"{safe}.lock"

    def read(self, card_id: str) -> Optional[dict]:
        try:
            return json.loads(self.path_for(card_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def acquire(self, card_id: str, agent: str) -> Optional[dict]:
        """
        Kartı atomik olarak sahiplenir; alınamazsa None.

        Süresi dolmuş VE sahibi ölmüş bir kira devralınır (kilit silinip
        yeniden oluşturulur); PID canlıysa devralınmaz.
        """
        path = self.path_for(card_id)
        expiry = _now() + datetime.timedelta(seconds=self.timeout_s)
        lease = {
            "card_id": str(card_id),
            "agent": str(agent or ""),
            "pid": os.getpid(),
            "acquired_at": _now().isoformat(timespec="seconds"),
            "expiry": expiry.isoformat(timespec="seconds"),
        }
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        payload = json.dumps(lease, ensure_ascii=False).encode("utf-8")
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if not self.expired(card_id):
                return None
            # Devralma: eski kilit silinir ve YENİDEN O_EXCL denenir. Silip
            # doğrudan yazmak yarışın kapısını yeniden açardı.
            try:
                path.unlink()
            except OSError:
                return None
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except OSError:
                return None
        except OSError:
            return None
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        return lease

    def expired(self, card_id: str) -> bool:
        """Kira doldu VE sahibi ölü mü? (İkisi birden olmadan devir yok.)"""
        lease = self.read(card_id)
        if lease is None:
            return True
        if pid_alive(lease.get("pid") or 0) and str(lease.get("pid")) != str(os.getpid()):
            return False
        try:
            expiry = datetime.datetime.fromisoformat(str(lease.get("expiry") or ""))
        except ValueError:
            return True
        if expiry > _now():
            # Kendi sürecimizin canlı kirası: süresi dolmadıysa devralınmaz.
            return False
        return True

    def release(self, card_id: str) -> bool:
        try:
            self.path_for(card_id).unlink()
            return True
        except OSError:
            return False

    def list(self) -> List[dict]:
        out: List[dict] = []
        try:
            for p in sorted(self.dir.glob("*.lock")):
                try:
                    out.append(json.loads(p.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    continue
        except OSError:
            return out
        return out


class BoardDispatcherCore:
    """
    Qt'siz tur mantığı: gez → sahiplen → başlat.

    `runner` sözleşmesi: `runner(card_id, agent_spec) -> Optional[str]`
    (ledger görev kimliği ya da None). Varsayılan `TaskBoard.run`'dır; testler
    sahte bir runner geçerek kota harcamadan turu ölçebilir.
    """

    def __init__(
        self,
        board=None,
        registry=None,
        vault_path: Optional[Path | str] = None,
        runner: Optional[Callable[[str, object], Optional[str]]] = None,
        claim_timeout_s: Optional[int] = None,
        max_parallel: Optional[int] = None,
    ):
        from entropy.agents.tasks import TaskBoard

        self.board = board if board is not None else TaskBoard(vault_path=vault_path)
        self.vault_path = Path(vault_path) if vault_path is not None else Path(self.board.vault_path)
        self._registry = registry
        self.claims = ClaimStore(self.vault_path, timeout_s=claim_timeout_s
                                 or _cfg("board_claim_timeout_s", DEFAULT_CLAIM_TIMEOUT_S))
        self.max_parallel = int(max_parallel or _cfg("entropy_max_parallel",
                                                     DEFAULT_MAX_PARALLEL))
        self._runner = runner
        self._lock = threading.RLock()
        self._starting: set = set()

    # -- yardımcılar ---------------------------------------------------

    @property
    def registry(self):
        if self._registry is None:
            from entropy.agents.registry import AgentRegistry

            self._registry = AgentRegistry(vault_path=self.vault_path)
        return self._registry

    def _run(self, card_id: str, agent_spec) -> Optional[str]:
        if self._runner is not None:
            return self._runner(card_id, agent_spec)
        return self.board.run(card_id)

    def running_count(self) -> int:
        """Şu an koşan/sahiplenilmiş Entropy kartı sayısı (ofis kartları hariç)."""
        return len([c for c in self.board.list()
                    if c.status in ("taken", "running") and not c.office])

    def busy(self, agent: str) -> bool:
        """Bu ajanın devam eden bir kartı var mı?"""
        agent = str(agent or "").strip()
        for card in self.board.list():
            if card.office:
                continue
            if str(card.agent or "").strip() == agent and card.status in ("taken", "running"):
                return True
        return False

    # -- sahiplenme ----------------------------------------------------

    def candidates(self, agent: str) -> List:
        """
        Bu ajana atanmış, sahiplenilmeyi bekleyen kartlar.

        Sıra: `priority` (P0 > P1 > P2 > boş) → `created_at` → `id`. Eskiden
        sıralama yalnızca dosya adıydı, yani "acil" diye bir kavram yoktu.
        """
        agent = str(agent or "").strip()
        rows = [c for c in self.board.list(status="assigned")
                if not c.office and str(c.agent or "").strip() == agent]
        rows.sort(key=lambda c: (
            _PRIORITY_ORDER.get(str(getattr(c, "priority", "") or "").upper(), 3),
            str(c.created_at or ""),
            str(c.id or ""),
        ))
        return rows

    def pick(self, agent: str) -> Optional[object]:
        """
        ATOMİK: bul + sahiplen + `taken`a taşı. Alınamazsa None.

        Tek çağrı olması bilinçli (kanban-md'nin `pick --claim` komutu):
        "listele, sonra sahiplen" iki ayrı çağrı olsaydı arada yarış penceresi
        kalırdı ve tam da engellemek istediğimiz şey oluşurdu.
        """
        for card in self.candidates(agent):
            lease = self.claims.acquire(card.id, agent)
            if lease is None:
                continue
            try:
                moved = self.board.apply_event(
                    card.id, "task.claimed", actor=agent,
                    payload={"claimed": True, "claimed_by": agent,
                             "claim_expiry": lease.get("expiry", ""),
                             "agent": agent},
                )
            except board_fsm.InvalidTransition:
                self.claims.release(card.id)
                continue
            if moved is None:
                self.claims.release(card.id)
                continue
            return moved
        return None

    # -- tur -----------------------------------------------------------

    def tick(self) -> List[str]:
        """
        Bir tur: her ajan için en çok bir kart başlatır.

        Dönüş: bu turda başlatılan kart kimlikleri.
        """
        started: List[str] = []
        try:
            specs = list(self.registry.list())
        except Exception:
            logger.exception("Ajan kadrosu okunamadı; tur atlandı")
            return started
        for spec in specs:
            name = str(getattr(spec, "name", "") or "").strip()
            if not name:
                continue
            if getattr(spec, "office", ""):
                # Ofis ajanı Entropy panosundan iş almaz: Desk'in kendi
                # harness'ı onu itmeli kipte besliyor ve tek yönlü akış korunur.
                continue
            if self.running_count() >= self.max_parallel:
                break
            if self.busy(name):
                continue
            card = self.pick(name)
            if card is None:
                continue
            with self._lock:
                if card.id in self._starting:
                    continue
                self._starting.add(card.id)
            try:
                task_id = self._run(card.id, spec)
            except Exception:
                logger.exception("Kart başlatılamadı: %s", card.id)
                task_id = None
            finally:
                with self._lock:
                    self._starting.discard(card.id)
            if task_id:
                started.append(card.id)
            else:
                # Başlatılamayan kart kilidiyle birlikte kuyruğa döner; aksi
                # hâlde kilit bir saat boyunca kartı rehin alırdı.
                self.claims.release(card.id)
                try:
                    self.board.apply_event(card.id, "claim.expired", actor="dispatcher",
                                           payload={"pid_alive": False,
                                                    "reason": "başlatılamadı"})
                except board_fsm.InvalidTransition:
                    pass
        return started

    # -- uzlaştırma ----------------------------------------------------

    def reconcile(self) -> List[str]:
        """
        Açılış uzlaştırıcısı: asılı kalan kartları kurtarır (rapor G6/C.12).

        Kural: `taken`/`running` görünen ama kilidi ölü olan kart `assigned`a
        çekilir. Kontrol noktası varsa iş baştan yapılmaz — ajan `checkpoint`
        dosyasından sürer; yoksa `attempt` artırılmadan yeniden kuyruğa girer
        (kesinti ajanın hatası değildir).

        PID canlıysa kart OLDUĞU GİBİ bırakılır: `claude --bg` ile başlatılmış
        bir oturum uygulamadan bağımsız yaşayabiliyor.
        """
        touched: List[str] = []
        self._clear_orphan_live_states()
        for card in self.board.list():
            if card.office or card.status not in ("taken", "running"):
                continue
            lease = self.claims.read(card.id)
            if lease is not None and pid_alive(lease.get("pid") or 0) \
                    and int(lease.get("pid") or 0) != os.getpid():
                continue
            self.claims.release(card.id)
            reason = ("Kesinti: uygulama koşu sırasında kapandı; "
                      + ("kontrol noktasından sürdürülecek."
                         if str(card.checkpoint or "").strip()
                         else "kart yeniden kuyruğa alındı."))
            try:
                self.board.apply_event(
                    card.id, "claim.expired", actor="reconciler",
                    payload={"pid_alive": False, "reason": reason},
                )
            except board_fsm.InvalidTransition:
                try:
                    self.board.reset_card(card.id, reason=reason, actor="reconciler")
                except Exception:
                    continue
            touched.append(card.id)
        if touched:
            self.board.rewrite_taskboard()
        return touched

    def _clear_orphan_live_states(self) -> List[str]:
        """
        Açılışta sahipsiz kalan `running` ajan durumlarını temizler (13-A2).

        Kart tarafı kurtarılsa bile ajanın `state.json`ı "koşuyor" kalabilir:
        çöken süreç kart durumunu hiç yazamamış olabilir. Bir ajan ancak
        gerçekten `taken`/`running` bir kartı VARSA koşuyor sayılır; kalan her
        "running" kaydı öksüzdür.
        """
        cleared: List[str] = []
        try:
            from entropy.core.identity import agent_session_store

            store = agent_session_store(self.vault_path)
            busy = {str(c.agent or "").strip() for c in self.board.list()
                    if not c.office and c.status in ("taken", "running")}
            root = store.state_path("x").parent.parent
            for entry in sorted(root.glob("*/state.json")):
                name = entry.parent.name
                if name in busy:
                    continue
                if store.clear_live_state(name):
                    cleared.append(name)
        except Exception:
            logger.debug("Öksüz ajan durumu temizlenemedi", exc_info=True)
        return cleared


def _cfg(name: str, default):
    try:
        from entropy.core.config import config

        value = getattr(config, name, default)
        return value if value is not None else default
    except Exception:
        return default


class BoardDispatcher:
    """
    `BoardDispatcherCore`un uygulama içi (Qt) sarmalı.

    Neden Python ve uygulama içi, ayrı bir servis değil: tetikleyicinin
    `config`, `bus`, `ConversationMap`, proje kilidi, `TaskLedger` ve köprü
    önbelleğiyle AYNI süreçte olması gerekiyor; ayrı bir süreç bunların hepsi
    için ikinci bir gerçek kaynak demekti. Darboğaz da burada değil: tur
    maliyeti milisaniye, iş süresi CLI'ın model gecikmesi (dakikalar).
    """

    def __init__(self, core: Optional[BoardDispatcherCore] = None,
                 interval_s: Optional[int] = None, parent=None):
        self.core = core if core is not None else BoardDispatcherCore()
        self.interval_s = int(interval_s or _cfg("board_dispatch_interval_s",
                                                 DEFAULT_INTERVAL_S))
        self._timer = None
        self._parent = parent
        self._connected = False

    def start(self) -> bool:
        """Zamanlayıcıyı kurar. Qt yoksa ya da ayar kapalıysa False."""
        if not _cfg("board_auto_dispatch", True):
            return False
        try:
            from PySide6.QtCore import QTimer
        except Exception:
            logger.info("Qt yok; BoardDispatcher zamanlayıcısı kurulmadı.")
            return False
        if self._timer is not None:
            return True
        self._timer = QTimer(self._parent)
        self._timer.setInterval(max(1, self.interval_s) * 1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        try:
            from entropy.core.event_bus import bus

            # Olayla uyanma: kart yazılır yazılmaz tur döner, yoklamayı bekletmez.
            bus.task_cards_updated.connect(lambda _cid="": self._on_tick())
            self._connected = True
        except Exception:
            pass
        return True

    def stop(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def _on_tick(self) -> None:
        try:
            self.core.tick()
        except Exception:
            logger.exception("Pano turu hata verdi")

    # Kolaylık: çağıranlar çekirdeğe inmek zorunda kalmasın.
    def tick(self) -> List[str]:
        return self.core.tick()

    def reconcile(self) -> List[str]:
        return self.core.reconcile()


_dispatcher: Optional[BoardDispatcher] = None


def board_dispatcher(create: bool = True) -> Optional[BoardDispatcher]:
    """Süreç içi tek tetikleyici (ana pencere kurar, slash komutları uyandırır)."""
    global _dispatcher
    if _dispatcher is None and create:
        _dispatcher = BoardDispatcher()
    return _dispatcher


def reset_dispatcher() -> None:
    """Test yalıtımı."""
    global _dispatcher
    if _dispatcher is not None:
        _dispatcher.stop()
    _dispatcher = None


__all__ = [
    "DEFAULT_CLAIM_TIMEOUT_S", "DEFAULT_INTERVAL_S", "DEFAULT_MAX_PARALLEL",
    "ClaimStore", "BoardDispatcherCore", "BoardDispatcher", "board_dispatcher",
    "reset_dispatcher", "pid_alive",
]
