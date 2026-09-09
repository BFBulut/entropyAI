# Faz 10 Ara Raporu — v0.7.1 (hotfix + dilim A/B)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.7.1` · Build: `dist\EntropyAI\EntropyAI.exe` (aynalandı, MD5 dist_check ile aynı)

## Sonuç
Tam paket **2283 test geçti, 0 hata** (v0.7.0: 2126; +157). Kota: 2 kısa agy turu (efor düzeltmesi canlı doğrulaması).

## Bildirdiklerin
- **agy'de efor ve model karışıklığı:** agy'de efor model adına gömülü (`gemini-3.8-flash-{low,medium,high}`, Pro `low/high`). `--effort` artık agy'ye hiç gönderilmiyor; efor kutusu sağlayıcı ve modele göre doluyor (agy 3/2/0, Claude 5), efor seçimi agy'de model varyantını değiştiriyor. Ayarlardaki Claude'dan sızmış `xhigh/max` değerleri açılışta onarılıyor. Canlı turda kartın açık modelinin kalıcı eforla ezildiği ikinci bir hata bulunup düzeltildi (`gemini-3.8-flash-medium` artık `-medium` olarak gidiyor).
- **Claude efor `low`:** transcript'te 28 kaydın hepsinde `effort: low`; seçim gerçekten geçiyor.
- **175k / +75k:** 7 istekte 37,5k yeni içerik + 132k ucuz önbellek okuması; tek turda hiçbir zaman 175k istem gitmedi. Yetenek gövdesi isteme yapıştırılmıyordu; yine de bütçe kodlandı (tek yetenek ≤ 12k karakter, financial-auditor 38k → 11,8k).
- **Entropy `_internal\AGENTS.md` ve dist klasörünü "proje" sandı:** proje kökü hiç kaydedilmiyordu ve paketli sürümde exe klasörüne düşüyordu. Artık kaydediliyor, paket klasörü reddediliyor, `--add-dir` proje + Obsidian kasası + çalışma alanı. `AGENTS.md` paketten çıktı.
- **"Supabase" hataları (bilişsel bellek modülü):** bulut Supabase yok. Gerçek kusurlar: yeni anılar yalnızca `cognitive_nodes`'a yazılıyor, graf tabloları üretimde hiç güncellenmiyordu (sapma 35 kayıt) ve 13 istisna sessizce yutuluyordu. Artık tek işlemde iki depoya yazım, açılış/rüya döngüsünde uzlaştırma (sapma 0, yedekli), hatalar günlük + `last_errors` + sinyal, gömme hatası anıyı kaybetmiyor (`pending` + yeniden gömme), `delete_memory` iki depodan siliyor. "105 / 7" farkı veri kaybı değil: çizim kotası ve bağlam bütçesi; gerçek toplam 1404+.
- **Marka kuralı:** iki ad da hiçbir dosyada yok (docs, tests, veri, scratch, notlar); testler kelimeyi parçalı kuruyor.

## Desk çekirdek mantığı (senin tarifin) — dilim A/B
- **Dosya tabanlı ortak bellek:** ofis kökünde `workspace/{BOARD.md, ARCHITECTURE.md, RULES.md}` (depo kirletilmez); her ajan istemi "önce şu dosyaları oku" doğuş talimatıyla başlıyor; pano kart değişince yeniden yazılıyor; orkestratör mimari notu düşebiliyor.
- **Kontrol noktası disiplini:** `[KONTROL NOKTASI]` blokları `workspace/checkpoints/<kart>.md`'ye; yeniden koşuda "kaldığın yer" istemde, eski çıktı değil.
- **Kanıtla kapatma:** `done` yalnızca yeşil `[KANIT]` ile; kanıtsız/kırmızı kart `review`'da "kanıt eksik"; değerlendirici kanıt ölçütü alıyor.
- **Onaylı kalıcı kurallar:** `[KURAL]` adayları kuyrukta; Desk Bellek sekmesinde ve Zen'de (Entropy'nin kendi kuralları) "Kalıcı yap / Reddet"; onaylılar sistem istemine giriyor; log/hata metni kural sayılmıyor.
- **Gizli terminaller + köprü + durum eşleme:** `agent_stream` sinyali (ajan/ofis/kart etiketli; düşünüyor/çalışıyor/boşta/hata); agy kartları ilk kez akış yayıyor; Desk "Terminaller" sekmesi ajan başına bölme, sprite balonu/tuşlama/volta, tıkla → bölme; koşan ajana stdin mesajı kapısı (stdin'i açık tutan etkileşimli kart kipi dilim C'de).
- **Orkestratör araştırma döngüsü:** orkestratörün arama aracı kadro kontrolü yüzünden hiç devreye girmiyordu; düzeltildi (en çok 3 arama, kaynak zorunlu).
- **Desk kendi kasası:** veri kökü `Entropy/Desk/Offices` → kasa kökünde `Desk/Offices` (tek seferlik geçiş uygulandı: Araştırma Ofisi 14 klasör / 10 dosya); ajanların gördüğü yollarda artık "Entropy" yok.
- Koşan karta yorum (`instruct_office(task_id=…)`) kartı durdurmadan istemine giriyor.

## Test yalıtımı
Testler artık gerçek bellek DB'sine, görev defterine ve ayar dosyasına dokunmuyor (öncesi/sonrası mtime ve satır sayıları aynı). Defterde testlerden kalan 4 kirli satır silindi, `default_project_path` pytest klasöründen `C:\EntropiAI`'ye çekildi.

## Kalan dilimler (C–E)
Etkileşimli kart kipi (terminal girdisi), proje = depo + dal, kart başına worktree (Windows güvenli), PR akışı (gh yoksa dal + diff), diff paneli, makbuz görünümü (ofis raporu = makbuz), ekip şablonları, harcama şeridi tamamlama, gerçek ofis koşusuyla uçtan uca doğrulama.

## Açık kalanlar
- Benzerlik eşiği (`SIMILARITY_MIN`) korpus boyutuna duyarlı; kalibrasyon yapılmadı.
- Kural adayı, kanıt ve kontrol noktası akışı gerçek sağlayıcıyla uçtan uca koşulmadı (dilim E).
- Balonlar kalabalık ofiste üst üste binebilir.
