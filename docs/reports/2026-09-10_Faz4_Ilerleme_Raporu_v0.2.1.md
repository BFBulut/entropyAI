# Faz 4 İlerleme Raporu — v0.2.1

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.2.1` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist, smoke 0, 20 sn canlı temiz)

## Sonuç
Tam paket **1688 test geçti, 0 regresyon** (Faz 3: 1635; +53 yeni). Kota: 0 token.

## Yapılanlar
- **Wiki katmanı v1 (Karpathy deseni):** `Skills/<yetenek>/wiki/` altında kavram sayfaları (playbook bölümlerinden) ve varlık sayfaları (LLM'siz sezgi: çok kelimeli özel adlar, araç adları), çapraz `[[bağ]]`lar, kategori sıralı `index.md`, append-only `log.md`; damıtma bitince otomatik ingest; `/wiki <yetenek>`. Gerçek kasada financial-auditor için 15 sayfa üretecek (kuru koşum).
- **`/lint [<yetenek>|all]`:** 7 LLM'siz denetim (kırık bağ, öksüz, bayat, eksik kavram, çelişki adayı — yalnızca birimli sayı/tarih, okunmamış rapor, açık handoff maddesi), sohbette HTML tablo + `wiki/lint.md`. Gerçek kasada `all`: 7 yetenek, 34 bulgu (27'si "eksik kavram sayfası": wiki henüz doldurulmadı; autonomous-agent'ta 1 kırık bağ; 4 yetenekte okunmamış rapor).
- **Bağlam kurucu:** sorguya göre en iyi 2 wiki sayfası (400 token), playbook'la kopya olanlar elenir; ölçüm: yordam sorgularında 0 ek token, varlık sorgusunda +92 token ile ilgili sayfalar giriyor.
- **Arayüz cilası:** legacy paket silindi, "agentspace üreticisi" sıfır, "Entropy Agent Desk" adları; liste/kanban/ofis panellerinde kırpma + tam metin ipucu + kaydırma politikası; diyalog tipografisi 14 px; sahne etiketleri; roster genişliği; akış paneli ortak CSS; grafik efsanesinde ofisler/kavram/varlık; boş model yer tutucusu.
- **Rapor Merkezi iskeleti:** Raporlar sekmesinde "Gelen" şeridi (son 24 saat, okundu/pin/arşiv, pin pencereyi aşar), Zen üst çubuğu ve Chat'te okunmadı rozeti, Chat'te "Gelen" sekmesi; durum `.entropy/report_inbox.json`.

## Ekran görüntüleri
`scratch/ui/phase4/01_agent_desk_full.png … 09_chat_full.png`, `lint_all.html`. Kozmetik: 1280 px genişlikte Zen sol rapor araç çubuğu etiketleri kırpılıyor (Faz 5 Rapor Merkezi'nde çözülecek).

## Ölçüm notları
Bağlam kurma süresi financial-auditor'da +%8 kod maliyeti (wiki sayfa seçimi), kalan artış korpus büyümesi (131 → 161 rapor). Token bütçesi değişmedi.

## Açık kalanlar (Faz 5'e)
- Gelen rozeti ilk açılışta Raporlar sekmesine girilmeden 0 kalıyor; rapor izleyicisine bağlanacak. `report_inbox.json` budaması (`prune`) çağrılmıyor.
- Wiki ingest canlı damıtmayla uçtan uca doğrulanmadı; `/wiki financial-auditor` ile elle üretilebilir (kota yok, LLM'siz).
- Çelişki sezgisi birimsiz eşikleri kaçırıyor (bilinçli).

## Faz 5 (doğrudan geçiliyor, yetkinle)
Tasarım: `2026-09-10_Faz5_Tasarim_Raporu.md`. Kalemler 5.1–5.6 üç ajanla, sonunda QA ve `v0.3.0`.
