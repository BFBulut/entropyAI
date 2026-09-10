"""
Köprü → `send_prompt(prompt) -> str` uyarlayıcısı (Faz 12-A).

Hafıza katmanının üç konsolidasyon modülü (`memory.gray_merge.run_merge_round`,
`memory.dream.dream_and_consolidate`, `memory.wiki.compile_skill`) köprüyü
tanımaz: hepsi `distiller.run_with_bridge` sözleşmesindeki **eşzamanlı**
`send_prompt(prompt) -> str` çağrılabilirini bekler. Sağlayıcı seçimi çağıranın
işidir (`config.provider`); bu modül o seçimi tek yerde yapar ve etkin köprünün
arka plan görev yolunu bloklayan bir çağrılabilire sarar.

Neden arka plan yolu: `send_background_task_async` her iki sağlayıcıda da
sonucun tamamını `on_result(full_text, success)` ile verir (sinyaller yalnızca
özet taşır) ve **işçi iş parçacığından** çağrılır; bu yüzden çağıran iş
parçacığında `threading.Event` ile beklemek kilitlenme üretmez.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Tek turun duvar saati tavanı (saniye). Konsolidasyon istemleri uzun sürebilir
#: ama sonsuz bekleme arayüzü kilitler.
DEFAULT_TURN_TIMEOUT = 900.0


class BridgeUnavailable(RuntimeError):
    """Etkin köprü yok ya da arka plan görev yüzeyini sunmuyor."""


def active_bridge(bridge: Any = None) -> Any:
    """
    Kullanılacak köprüyü döndürür.

    Çağıran zaten etkin köprüyü tutuyorsa (arayüz, slash komutları) onu verir.
    Vermezse sağlayıcı seçimi `config.provider` üzerinden yapılır ve ilgili
    köprü sınıfı örneklenir.
    """
    if bridge is not None:
        return bridge
    from entropy.core.config import config

    provider = (getattr(config, "provider", "") or "").strip().lower()
    if not provider:
        try:
            provider = (config.default_provider() or "").strip().lower()
        except Exception:  # pragma: no cover - ayar okunamazsa agy varsayılan
            provider = "agy"
    if provider == "claude":
        from entropy.core.claude_bridge import ClaudeProcessBridge

        return ClaudeProcessBridge()
    from entropy.core.agy_bridge import AgyProcessBridge

    return AgyProcessBridge()


def make_send_prompt(
    bridge: Any = None,
    *,
    label: str = "Hafıza turu",
    timeout: float = DEFAULT_TURN_TIMEOUT,
    agent: Optional[str] = None,
    on_turn: Optional[Callable[[int, bool], None]] = None,
) -> Callable[[str], str]:
    """
    Etkin köprüden eşzamanlı bir `send_prompt(prompt) -> str` üretir.

    `label` görev adının önekidir (ledger'da görünür). `agent` verilirse tur
    kısıtlı bir alt ajanla koşar. `on_turn(sıra, başarı)` her turdan sonra
    çağrılır (isteğe bağlı ilerleme kancası).

    Kota: her çağrı **bir** model turudur. Çağıran tur sayısını sınırlar
    (`budget_turns`, `limit`); bu uyarlayıcı kendi başına tur açmaz.
    """
    target = active_bridge(bridge)
    runner = getattr(target, "send_background_task_async", None)
    if not callable(runner):
        raise BridgeUnavailable(
            "Etkin köprü arka plan görev yüzeyini sunmuyor "
            f"({type(target).__name__}.send_background_task_async yok)."
        )

    def _send(prompt: str) -> str:
        index = int(getattr(_send, "_entropy_turns", 0) or 0) + 1
        done = threading.Event()
        box: dict = {"text": "", "ok": False}

        def _on_result(full_text: str, success: bool) -> None:
            box["text"] = full_text or ""
            box["ok"] = bool(success)
            done.set()

        task_id = f"memround-{uuid.uuid4().hex[:8]}"
        task_name = f"{label} [{index}]"
        runner(
            task_id,
            task_name,
            prompt,
            mode="accept-edits",
            on_result=_on_result,
            save_report=False,
            agent=agent,
        )
        started = time.time()
        if not done.wait(timeout):
            try:
                target.terminate_background_task(task_id)
            except Exception:  # pragma: no cover - temizlik hatası turu bozmaz
                logger.warning("Zaman aşımına uğrayan tur sonlandırılamadı: %s", task_id)
            raise TimeoutError(
                f"{label}: model turu {timeout:.0f} sn içinde yanıt vermedi ({task_id})."
            )
        _send._entropy_turns = index  # type: ignore[attr-defined]
        if on_turn is not None:
            try:
                on_turn(index, box["ok"])
            except Exception:  # pragma: no cover
                pass
        logger.info(
            "%s turu %d bitti (%.1f sn, başarı=%s, %d karakter).",
            label, index, time.time() - started, box["ok"], len(box["text"]),
        )
        if not box["ok"]:
            return ""
        return box["text"]

    _send._entropy_turns = 0  # type: ignore[attr-defined]
    return _send


def turn_count(send_prompt: Any) -> int:
    """Uyarlayıcının şu ana kadar harcadığı tur sayısı (test/rapor için)."""
    return int(getattr(send_prompt, "_entropy_turns", 0) or 0)
