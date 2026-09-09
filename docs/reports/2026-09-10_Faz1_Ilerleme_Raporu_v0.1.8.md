# Faz 1 İlerleme Raporu — v0.1.8

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Commit `6dac415` · Etiket `v0.1.8` · Build: `dist\EntropyAI\EntropyAI.exe` (04:02, dist'e aynalandı)

## Sonuç
Faz 1'in beş kalemi tamamlandı. Tam paket: **1436 test geçti**; 9 başarısız test depoda olmayan medya varlıklarına bağlı izlenmeyen dosyalar (canivopets/talking_bugs), ürünle ilgisiz. Build 248 sn, smoke çıkışı 0, 20 sn canlı çalıştırmada logda hata yok, performansta kötüleşme yok. Kota: iki gerçek prob, toplam ~54,6k token (Claude tarafı 46k, çoğu önbellek oluşturma, 0,46$; agy 8,4k).

## Yapılanlar

### 1. Sağlayıcı soyutlaması ve Claude Code köprüsü
- `ProviderBridge` protokolü; `AgyProcessBridge` aynen uyuyor, davranış değişmedi.
- `ClaudeCodeBridge`: `claude -p --output-format stream-json --verbose` (verbose şart, yoksa yalnız result gelir), stdin NDJSON (`{"type":"user",...}` — agy'de `event`), izin kipi eşlemesi, `--model`, `--resume` ile oturum devamı, taskkill /T ile iptal, ledger kaydı (`provider` sütunu), `claude auth status --json` → oturum rozeti (abonelik max, giriş yapılmış).
- Ayarlar: `provider`, sağlayıcı başına model listesi; `create_bridge(config)`, çalışırken `switch_provider`; Chat üst çubuğunda **Sağlayıcı** seçici (ekran görüntüsü: `scratch/ui/phase1/chat_topbar.png`); `/provider [agy|claude]` komutu.
- Claude API: yalnızca tespit ve ayar bayrağı (ücretli olduğu için uygulama yok, açıkça açılmadıkça kullanılmaz).
- Prob sonuçları: Claude → "ok", olaylar init/assistant/result; agy → "ok".

### 2. Canlı rapor atfı ve artımlı damıtma (kök neden bulundu)
- Neden: rapor kaydında **proje yetenekten önce** değerlendiriliyordu; `skill:` etiketli 77 raporun 67'si `Projects/*/Reports/` altına düşüp damıtmaya görünmezdi; indeks yalnızca `/distill index` ile yenileniyordu.
- Düzeltme: yetenek klasörü öncelikli kayıt, etiket taraması proje klasörlerini de kapsıyor, artımlı indeks (yeni dosya 0,07 sn'de eklenir), `ReportWatcher` canlı izleme, kartlarda iki ayrı eylem: **📘 N** (yalnız yeni N rapor) ve **♻** (tazeleme, tüm arşiv).
- Gerçek kasa şimdi: google-flow **0/3 (düğme açık)**, financial-auditor 104/121, autonomous-agent 513/516, media-agency-soldier 16/20, permissioned-github 0/27. Kartlar bu sayıları gösteriyor (`scratch/ui/phase1/zen_skill_cards.png`).

### 3. Bağlam aktarımı ve token temizliği
- `context_fill_ratio` ve %60'ta `bus.context_pressure`; köprü, aktarım sayfası varsa geçmişi "sayfa + son 4 tur"a sıkıştırır.
- `/handoff [not]`: 9 bölümlü aktarım sayfası (`Entropy/Sessions/<tarih>-<konu>.md` + `log.md` + bellekte session düğümü), LLM çağrısız; sonraki oturumda bağlam kurucu 300 token bütçesiyle bir kez enjekte eder (örnek sayfa 374 token, bağlama giren 105).
- Araç sonucu maskeleme: 2000 karakteri aşan araç çıktıları ledger, bildirim ve bellek yazımında yer tutucuya dönüşüyor.

### 4. Eski Agent Desk temizliği
- `src/entropy/agent_desk` (44 modül), `Agents/`, `EntropyAgentDesk.spec`, `run_agent_desk.py` ve yalnızca ona ait 169 test silindi. Piksel/ofis çizim kodu (`pixel_canvas`, `office_detail_widget`, `offices_overview_widget`) `src/entropy/desk/legacy/` altında; ayrı sprite dosyası yoktu (çizim yordamsal). Spec'teki ölü `Agents` datas kaldırıldı, yeni modüller hiddenimports'a eklendi.

## Açık kalanlar (Faz 2'ye taşınan)
- Claude köprüsünde sohbet yolunun ek özellikleri: proje kilidi, yetenek çözümü, PDF/görsel eki, bilişsel bağlam enjeksiyonu (agy köprüsünde var, Claude'a taşınmadı).
- Sağlayıcı seçici yalnızca Chat'te; Zen'de yok. `bus.context_pressure` arayüzde rozet olarak gösterilmiyor.
- Claude'un `cache_creation_input_tokens` kalemi toplam token'a dahil; rozet agy'ye göre yüksek görünecek, ayrı kalem olarak gösterilmesi gerekebilir.
- `/provider` ile gerçek köprü değişimi canlı denenmedi (kota).
- Damıtmanın kendisi bu fazda koşturulmadı; google-flow için `/distill google-flow` (3 rapor, tek tur, ~10k token) senin komutunla.

## Faz 2 önerisi (onay bekliyor)
Ajanlar ve kartlar: `Entropy/Agents/<ad>/AGENT.md` kaynağı ve iki CLI'a derleme; "Ajanlar" sekmesi (liste/ekle/düzenle/sil/görev ver); manifestte ajan farkındalığı; görev kartları (kanban) + görev sözleşmesi dosyası; ajan raporlarının query sayfası olarak kasaya inmesi; Claude köprüsünün sohbet yolu tamamlanması; Zen'e sağlayıcı seçici ve bağlam doluluk rozeti. Sonunda `v0.1.9`.
