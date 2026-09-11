"""`tests/_reference/` toplama kuralları.

Bu klasör sevk edilen ürün kodunu sınamayan ispat defterlerini tutar; tamamı
normalde toplanır ve koşar. Tek istisna aşağıdadır: sınadığı modül üründen
arşive alındığı için artık içe aktarılamayan dosya toplama dışı bırakılır
(aksi hâlde `ModuleNotFoundError` süitin tamamını kırar).
"""

from __future__ import annotations

#: Faz 13-C / ADR-0009: `entropy.core.claude_bg` arşivlendi
#: (`docs/_archive/spikes/claude_bg/claude_bg.py`), 32 test toplama dışı.
collect_ignore = ["test_phase11_claude_bg.py"]
