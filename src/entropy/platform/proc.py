"""
Alt süreç bayrakları — Windows'ta konsol penceresi AÇILMASIN (Faz 13-A2).

Sorun
-----
Paketlenmiş `EntropyAI.exe` **pencereli** (konsolsuz) bir süreçtir. Böyle bir
süreç `subprocess` ile bir konsol uygulaması (`claude`, `agy`, `git`, `gh`,
`where`, `tasklist`, `taskkill`) başlattığında Windows o çocuk için **yeni bir
konsol penceresi** açar. Kullanıcının ölçümü: tek bir kart koşusunda ekranda
onlarca pencere yanıp sönüyordu (sürüm probu, ikili arama, git durumu, MCP
listesi, koşu sonunda `taskkill`…).

Çözüm iki bayraktır ve **ikisi birden** gerekir:

* `creationflags=CREATE_NO_WINDOW` — yeni konsol tahsis edilmez;
* `startupinfo=STARTF_USESHOWWINDOW + SW_HIDE` — bazı ikililer (özellikle
  `cmd.exe` üzerinden koşan `shell=True` çağrıları ve konsol alt sistemi olan
  Node sarmalayıcıları) bayrağa rağmen kendi penceresini gösterebiliyor;
  `STARTUPINFO` o pencereyi de gizler.

`CREATE_NO_WINDOW` ile `DETACHED_PROCESS` **birlikte kullanılamaz** (Windows
`ERROR_INVALID_PARAMETER` verir); bu yüzden `popen_kwargs` çağıranın verdiği
`creationflags`i EZMEZ, üstüne VEYA'lar ve `DETACHED_PROCESS` varsa
`CREATE_NO_WINDOW`u eklemez.

Windows dışında iki alan da anlamsızdır: sözlük **boş** döner, yani çağrı
yerleri koşullu kod yazmaz.

Kullanıcıya GÖRÜNMESİ istenen kabuk çağrıları (`explorer /select,`, `open -R`,
`xdg-open`) bu yardımcıyı KULLANMAZ; sözleşme testi onları ayrıca muaf tutar.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict

__all__ = ["IS_WINDOWS", "CREATE_NO_WINDOW", "popen_kwargs", "hidden_startupinfo"]

IS_WINDOWS = sys.platform.startswith("win")

#: `subprocess.CREATE_NO_WINDOW` yalnızca Windows'ta tanımlı; sabit burada
#: normalleştirilir ki çağrı yerleri `getattr(subprocess, ...)` yazmasın.
CREATE_NO_WINDOW = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
_DETACHED_PROCESS = int(getattr(subprocess, "DETACHED_PROCESS", 0) or 0)


def hidden_startupinfo():
    """`SW_HIDE` ayarlı `STARTUPINFO` (Windows dışında None)."""
    if not IS_WINDOWS:
        return None
    try:
        info = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        info.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0) or 0)
        return info
    except Exception:
        return None


def popen_kwargs(**extra: Any) -> Dict[str, Any]:
    """
    `subprocess.Popen/run/...` çağrılarına eklenecek pencere gizleme kwarg'ları.

    Çağıran kendi `creationflags`ini verirse korunur (VEYA'lanır); başka
    anahtarlar olduğu gibi geçer, böylece
    `subprocess.run(cmd, **popen_kwargs(timeout=10))` yazılabilir.
    """
    kwargs: Dict[str, Any] = dict(extra)
    if not IS_WINDOWS:
        kwargs.pop("_hide", None)
        return kwargs
    flags = int(kwargs.get("creationflags") or 0)
    if not (_DETACHED_PROCESS and flags & _DETACHED_PROCESS):
        flags |= CREATE_NO_WINDOW
    kwargs["creationflags"] = flags
    if kwargs.get("startupinfo") is None:
        info = hidden_startupinfo()
        if info is not None:
            kwargs["startupinfo"] = info
    return kwargs
