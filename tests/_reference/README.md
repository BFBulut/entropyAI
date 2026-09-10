# `tests/_reference/` — referans (ispat defteri) testleri

Bu 82 dosya **sevk edilen ürün kodunu sınamaz**: `entropy.*` içinden hiçbir şey
içe aktarmazlar. Nicel finans modellerinin kendi kendine yeten ispat defterleridir
(`skills/financial-auditor/scripts` ve `scripts/` altındaki denetim araçlarına bakarlar).

Neden ayrıldı: hız değil (**563 test / ~7 s**, süitin %1,7'si), **ölçüm dürüstlüğü**.
Kökte dururken "2.347 test yeşil" cümlesi ürün güvencesini %24 abartıyordu.

- Toplama sayısı **değişmedi** — dosyalar yalnızca yer değiştirdi, `pyproject.toml`
  ve `conftest.py` dokunulmadı; `pytest` hâlâ hepsini toplar.
- Yalnız bu grubu koşmak: `pytest tests/_reference -q`
- Yalnız ürün süiti: `pytest tests --ignore=tests/_reference -q`
- Taşımada tek kod değişikliği: `Path(__file__).parent.parent` → `Path(__file__).parents[2]`
  (49 dosyada depo kökü bir seviye derinleşti).
