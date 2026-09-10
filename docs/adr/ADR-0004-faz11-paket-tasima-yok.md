# ADR-0004 — Faz 11'de paket taşıması yapılmaz (`memory → brain` Faz 12'ye ertelendi)

- Durum: **kabul edildi**
- Tarih: 2026-09-10
- Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_B_Depo_Denetimi.md` §6.2–6.3

## Bağlam

Hedeflenen paket şeması `core / brain / agents / desk / ui / skills`. Bugünkü şemayla
karşılaştırıldığında **tek gerçek fark** bilgi katmanının (`memory/` + `skills/`) `brain/`
altında toplanmasıdır; `core`, `agents`, `desk`, `ui`, `skills` zaten mevcuttur.

Yalnızca `entropy.memory` → `entropy.brain` yeniden adlandırmasının dokunduğu yüzey ölçüldü:

| Yüzey | Dokunulan |
|---|---:|
| `src/` içindeki içe aktarmalar | 41 dosya |
| `tests/` içindeki içe aktarmalar | 41 dosya |
| `EntropyAI.spec` hiddenimports | 22 satır |
| **Toplam** | **~104 dosya** |

## Karar

Faz 11-A **tek bir `import` satırına dokunmaz**. Paket adları olduğu gibi kalır; bu fazda
yalnızca silme, arşivleme, `docs/` iskeleti, kök markdown düzeltmesi, `.gitignore` ve test
dizini düzeni yapılır. `memory → brain` taşıması **Faz 12**'dir ve ön koşulu şudur:
`docs/ARCHITECTURE.md` yazılmış, tam süit yeşil ve `.exe` bir kez sorunsuz derlenmiş olmalı.
Taşıma tek commit'te: `git mv` + otomatik değiştirme + spec güncellemesi + tam süit +
`dist_check` derlemesi.

## Gerekçe

1. Aşama 1 kullanıcının isteğinin **tamamını** (silme, klasör düzeni, boşları kaldırma,
   markdown'ları düzeltme) **sıfır regresyon riskiyle** karşılıyor: kazanç ~4,5 GB disk,
   17.000+ dosya, 3,4 MB ölü kaynak.
2. Aşama 2 saf estetik bir kazanç için 104 dosyaya dokunuyor ve **sessiz paketleme hatası**
   riski taşıyor: `EntropyAI.spec` hiddenimports bir **dizgi** listesidir; bir satır atlanırsa
   `.exe` sessizce eksik paketlenir. Faz 10-C'de tam olarak bu oldu (worktree/PR/şablon/makbuz
   yolları `.exe`'de sessizce kapanmıştı).
3. İkisini aynı fazda birleştirmek, bir sorun çıktığında hangisinin sebep olduğunu
   **ölçülemez** kılar.

## Sonuçlar

- Faz 11-A'nın kanıtı basittir: test sayısı yalnızca silinen prototip kadar düşer
  (2.374 → 2.042) ve başka hiçbir sayı değişmez.
- `skills/__init__.py` `_LAZY` haritası ve `provider.py` içindeki dizgi eşlemeleri Faz 12'de
  metin olarak taşınmalıdır (AST tabanlı bir araç bunları göremez).
- `~/.entropy` altındaki kullanıcı durumu paket adına göre anahtarlanmıyor; Faz 12'de veri
  göçü gerekmeyecek. Tek gerçek risk içe aktarma yollarıdır.
