# ADR-0008 — `entropy.memory` → `entropy.brain` paket taşıması yapıldı (Faz 13-B)

- Durum: **kabul edildi**
- Tarih: 2026-09-11
- Yerine geçtiği karar: [ADR-0004](ADR-0004-faz11-paket-tasima-yok.md) ("Faz 11'de taşıma yapılmaz")
- Kaynak: `docs/reports/2026-09-10_Faz13_Arastirma_Notu.md` §2 (K6)

## Bağlam

Belgelenmiş hedef paket şeması `core / brain / agents / desk / ui / skills`.
`memory` adı ile paketin gerçek kapsamı (yazma kapısı, kategoriler, rüya döngüsü,
gri bant birleştirme, wiki derleme, playbook, bağlam kurucu, ofis çalışma alanı)
arasındaki fark her yeni ajanı yanlış yönlendiriyordu.

ADR-0004 taşımayı beş risk ön koşuluna bağlamıştı; Faz 13 araştırması **beşinin de
yeşil** olduğunu ölçtü (ARCHITECTURE.md yazıldı, tam süit yeşil, `.exe` derlendi,
kalıcı spec eşleme testi var, tek seferlik betikler `scripts/_oneshot/` altına
ayrıldı). Karşılanmayan tek şey sayısal "≤ 100 dosya" **hedefiydi** (ölçülen 113) —
bu bir risk kapısı değildi ve yüzey her fazda büyüyordu (41 → 45 → 48 `src` dosyası).

## Karar

1. `git mv src/entropy/memory src/entropy/brain` (27 modül).
2. `entropy.memory` / `entropy/memory` dizgileri `src/`, `tests/`, `scripts/`
   (`_oneshot/` dâhil), `EntropyAI.spec` ve canlı belgelerde yeni adla değiştirilir.
   **`docs/reports/` altındaki tarihsel raporlar dokunulmaz** (geçmiş dondurulur).
3. Eski ad bir sürüm boyunca **uyumluluk şimi** ile yaşar:
   `src/entropy/memory/__init__.py` bir `sys.meta_path` bulucusu kurar ve
   `entropy.memory.<alt>` adını `entropy.brain.<alt>` modülünün **aynı nesnesine**
   bağlar; içe aktarımda `DeprecationWarning` verir.
   **Ömür: v0.11.x; v0.12.0'da silinir.**
4. Şim `EntropyAI.spec` hiddenimports listesine eklenir (exe'de sessizce kaybolmasın).

## Gerekçe

- ADR-0004'ün asıl riski **spec sapmasıydı** (Faz 10-C'de `.exe` sessizce eksik
  paketlenmişti); bu risk artık `tests/contracts/test_spec_sync.py` ile **kalıcı
  olarak** ölçülüyor, tek seferlik bir dikkat işi değil.
- Şim, dış atıfları ve koşulmayan 55 `_oneshot/` betiğini çalışır tutar; geri alma
  maliyetini düşürür.
- Taşıma **tek commit** ve **tek başına bir dilimde** (13-B) yapıldı; başka hiçbir
  ajan aynı anda `src/`, `tests/` ya da spec'e yazmadı, böylece olası bir `.exe`
  hatasının sebebi ölçülebilir kalıyor (ADR-0004 §3).

## Sonuçlar

- Kullanıcı verisi **taşınmadı**: `~/.entropy` ve Obsidian kasası paket adına göre
  anahtarlanmıyor. Salt okunur tarama, `~/.entropy` altındaki hiçbir durum/indeks
  dosyasında (`*.json`, `*.db`) `entropy.memory` dizgisi bulmadı; kasadaki eşleşmeler
  yalnızca **tarihsel rapor metinleridir** ve dokunulmadı.
- Veri yolları paket adından bağımsızdır ve **değişmedi**: `~/.entropy/memory/`,
  `<db klasörü>/memory/gray_queue.jsonl`, `<db klasörü>/memory/gray_merge_log.jsonl`.
- Sözleşme testi `tests/contracts/test_brain_package_move.py` şu dördünü kalıcı
  ölçer: eski ada atıf sayacı 0, şim kimliği (`is`), `DeprecationWarning`,
  spec'te şim girdisi.
- **Geri alma:** taşıma tek commit olduğu için `git revert <commit>` yeterlidir;
  veri göçü olmadığı için geri almanın yan etkisi yoktur.
- v0.12.0 açılırken yapılacak: `src/entropy/memory/` silinir, spec'ten
  `'entropy.memory'` girdisi çıkarılır, `test_brain_package_move.py`'nin şim
  testleri kaldırılır (atıf sayacı testi kalır).
