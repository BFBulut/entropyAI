# Faz 5 İlerleme Raporu — v0.3.0

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.3.0` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist, smoke 0, 20 sn canlı temiz)

## Sonuç
Tam paket **1789 test geçti, 0 regresyon** (Faz 4: 1688; +101). Kota: 0 model çağrısı. Gerçek bellek veritabanı yedekli göçle yeni grafa taşındı (yedek: `~/.entropy/backups/cognitive_memory.20260909_094030.db`).

## Yapılanlar
### Tek bilinç: birleşik bellek grafı (5.1–5.2)
- Aynı SQLite içinde `nodes / edges / communities`; düğüm türleri episode/fact/entity/procedure/agent/office/task/report/session/community; kenarlar derived_from/contradicts/supersedes/triggered/produced/member_of/similar_to; **çift zamanlı** kenarlar (`t_valid_from/to`, `ingested_at`), önem puanı, provenans.
- Göç kayıpsız ve geri dönüşlü: 910 → 912 düğüm, 972 kenar, 0,15 sn; konsolidasyon 89 topluluk + 1 yansıma, 1,6 sn; geri çağırma eşitliği 3/3 sorguda birebir. Konsolidasyon rüya döngüsüne bağlandı.
- LLM'siz uzlaştırma: kopya birleştirme, çelişkide eski kenar geçersizleştirilir + `supersedes` (silme yok). Geri çağırma: hibrit tohumlama → PPR yayılımı → "yalnızca geçerli" + tür/zaman/kapsam filtresi; 5 ilişkisel sorgunun 3'ünde yeni komşular.
- Desk belleği (ofis/ajan MEMORY.md) kapsam alt-grafı olarak aynı grafta; kapsam sızıntısı testle engelli.

### Ajan iletişimi ve yönetim (5.3)
- A2A benzeri posta kutuları (`Offices/<ofis>/inbox`, `Agents/<ad>/inbox`, `Entropy/Inbox`), atomik yazım, ajan→ajan yalnızca aynı ofis, **terminal olay sözleşmesi** (harness, pano; asılı görev yok). Orkestratör planlamadan önce Entropy'nin talimatlarını okur; ofis raporu Entropy gelen kutusuna düşer. `/ask <ofis>`, ofis durum panosu.

### Tek Entropy kimliği ve agentic sohbet (5.4)
- Sağlayıcı durum katmanı: Claude `auth status --json` (max abonelik, e-posta), agy `agy models` + `~/.gemini` hesap/oturum penceresi; 5 dk yenileme, üst çubukta rozet, `/login` yönlendirmesi; Claude için isteğe bağlı `CLAUDE_CONFIG_DIR` "Entropy profili".
- Konuşma eşlemesi (`--conversation` / `--resume`), sağlayıcı değişse de korunur; `AgenticChat` + `/chat <ofis|ajan>`: Entropy bir sağlayıcıda, ofis ajanı ötekinde, posta kutusu üzerinden sıralı turlar. Not: tek abonelik teknik olarak iki oturum demektir; agy makine başına tek Google hesabı.

### Rapor Merkezi ve yaşam tarzı arayüz (5.5)
- Kümeleme (başlık TF-IDF + ofis + kart), digest kartları (bulgular + karar önerisi), önem × aciliyet, güven eşiği ile sessiz bölüm, okundu/pin/arşiv/budama, "Orkestratöre sor" → `/ask`; gerçek kasada 854 rapor → 9 öne çıkan, 178 sessiz küme.
- Komut paleti (Ctrl+K), odak modu (Ctrl+Shift+F), "Bugün" zaman çizelgesi, bildirim merkezi, sağlayıcı rozeti; Zen ve Chat paralel; rapor araç çubuğu kırpması giderildi.

### Graf görselleştirme (5.6)
- Kontrol şeridi: zaman kaydırıcısı, tür/önem filtreleri, "yalnızca geçerli" varsayılan, topluluk düğümleri tıklayınca açılır; alanlar yoksa kontroller pasif; 1001 düğümde 1,8 ms/kare fizik (gerçek rasterleştirme hariç).

## Ekran görüntüleri
`scratch/ui/phase5/`: report_center_200, report_center_quiet_expanded, command_palette, focus_mode_on/off, timeline_today, notification_center, provider_badge, graph_control_strip, graph_community_expanded, zen_full_report_center (gerçek kasa), topbar_provider_badge.

## Açık kalanlar
- Gerçek sağlayıcıyla canlı doğrulanmayanlar: agentic sohbet turu, agy `--conversation` ile arka plan devamı, posta kutusu izleyicisi dolu kutuda, kimlik rozetinin canlı değeri (canlı koşuda prob başlamadan görüntü alındı).
- Gerçek WebEngine içi grafik ekran görüntüsü alınamıyor (offscreen GPU); görüntüler headless Chromium ile.
- Öksüz görevlerin kapanışına terminal olay eklenmedi; `claude_config_dir` için ayar ekranı alanı yok.
- Faz 3'ten kalan: gerçek ofis koşusu (kota kararın) yeniden yapılmadı.
