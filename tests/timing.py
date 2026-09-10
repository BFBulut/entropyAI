"""
Yük altında dayanıklı bekleme bütçeleri (Faz 11 kapanış QA).

**Sorun (ölçülmüş):** `tests/desk/test_office_hardening.py` ve
`tests/desk/test_office_harness.py` tek başına koşarken 25,5 sn'de yeşil
(en yavaş test 6,86 sn), ama **tam süit altında** zaman aşımına giriyordu.
Kök neden ürün hatası değil, testlerin **sabit duvar saati** bütçeleri:
`Event.wait(10)`, `_wait_until(..., 20)` gibi değerler boştaki makineye göre
seçilmişti. 2.300 testlik süitte aynı çekirdekler paylaşıldığında gerçek
süre 3-5 katına çıkıyor ve bütçe patlıyordu.

**Çözüm (esnetme değil):** bütçe makinenin o anki hızıyla ÖLÇÜLEREK
ölçeklenir. Doğruluk iddiası değişmez — bozuk kod hâlâ başarısız olur,
yalnızca "ne kadar bekleyeyim" sorusu ölçüme bağlanır.

Kullanım::

    from tests.timing import budget

    assert done.wait(budget(10))

`ENTROPY_TEST_TIMEOUT_SCALE` ile elle geçersiz kılınabilir (CI için).
"""

from __future__ import annotations

import os
import time

# Kalibrasyon çekirdeği: referans makinede ~0,010 sn süren saf-Python döngü.
_CALIBRATION_ITERATIONS = 200_000
_REFERENCE_SECONDS = 0.010

# Ölçek tavanı: yük ne olursa olsun bir test 8 kattan fazla beklemesin
# (aksi hâlde gerçek bir kilitlenme süiti dakikalarca askıda tutar).
MIN_SCALE = 1.0
MAX_SCALE = 8.0

# Ölçüm 1 sn'den eskiyse tazelenir: yük süit boyunca değişir, açılıştaki tek
# ölçüm yanıltır. Kalibrasyonun kendi maliyeti referansta 10 ms'dir.
_CACHE_TTL_S = 1.0

_scale: float | None = None
_scale_at: float = 0.0


def _measure_scale() -> float:
    override = os.environ.get("ENTROPY_TEST_TIMEOUT_SCALE", "").strip()
    if override:
        try:
            return max(MIN_SCALE, min(MAX_SCALE, float(override)))
        except ValueError:
            pass
    start = time.perf_counter()
    acc = 0
    for i in range(_CALIBRATION_ITERATIONS):
        acc += i & 7
    elapsed = time.perf_counter() - start
    assert acc >= 0  # döngü optimize edilip atılmasın
    return max(MIN_SCALE, min(MAX_SCALE, elapsed / _REFERENCE_SECONDS))


def timeout_scale(refresh: bool = False) -> float:
    """Ölçüm anındaki yük katsayısı (tembel, süreç başına bir kez ölçülür)."""
    global _scale, _scale_at
    now = time.monotonic()
    if _scale is None or refresh or (now - _scale_at) > _CACHE_TTL_S:
        _scale = _measure_scale()
        _scale_at = now
    return _scale


def budget(seconds: float) -> float:
    """Sabit saniyeyi makinenin o anki hızına göre ölçeklenmiş bütçeye çevirir."""
    return float(seconds) * timeout_scale()
