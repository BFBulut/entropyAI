# Faz 5 — Tasarım Raporu: Birleşik Bilinç, Bellek Grafiği, Ajan İletişimi, Tek Kimlik

Tarih: 2026-09-10 · Taban: v0.2.1 (Faz 4 sonu) · Hedef: `v0.3.0` · Adlandırma: ana zekâ **Entropy AI**, ofis paneli **Entropy Agent Desk** (uygulamada başka marka adı geçmez)

## 1. Amaç (senin sözlerinle)
Entropy AI, ofislerdeki orkestratörlerle konuşabilsin, raporlarını toplayıp Zen'de sınıflandırıp gösterebilsin (çok rapor → düzgün triyaj), arayüz "yaşam tarzı" düzeyinde yenilensin, Agent Desk belleği Entropy belleğine katılıp **tek bilinç** olsun, graf ileri düzey bilişsel sistemlerdeki gibi kurulsun, ajanlar arası orkestrasyon/iletişim/yönetim güçlensin, Antigravity + Claude tek girişle senkron çalışsın ve aralarında "agentic sohbet" olsun.

## 2. Araştırmanın verdiği kararlar (kaynaklar: Faz 5 araştırma notu, `2026-09-10_Faz5_Arastirma_Notu.md`)
- **Bellek grafiği:** Zep/Graphiti'nin **çift zamanlı** modeli (her kenarda `t_valid_from/to` + `ingested_at`; çelişkide silme yok, geçersizleştirme + `supersedes`) ve 2026 uzlaşısı: **yazma anında çelişki/kopya uzlaştırması** daha iyi sıralayıcıdan çok kazandırır. CoALA'nın dört bellek türü düğüm etiketi olur; Generative Agents'ın önem puanı ve yansıma/özet düğümleri eklenir; HippoRAG 2 tarzı tohumlu PPR yayılımı geri çağırmaya girer. A-MEM'in "yazarken bağ kur, komşuyu güncelle" ilkesi wiki katmanına (Faz 4) uygulanır.
- **Ajan iletişimi:** kısa yolda **dosya tabanlı posta kutusu + bus olayı**, mesaj şeması **A2A benzeri** (task_id, durum, rol, parça, zorunlu terminal olay) — ileride yerel A2A sunucusuna şema değişmeden geçiş. Claude Code Agent Teams'in "posta kutusu + paylaşılan görev listesi" deseni referans.
- **Rapor triyajı:** inceleme yorgunluğuna karşı güven eşiği ile yönlendirme, kümeleme + digest kartları, önem × aciliyet, okundu/pin/arşiv; gözlemlenebilirlik için Langfuse tarzı toplu/açık görünüm.
- **Tek kimlik:** iki oturum birbirini tanımaz; agy makine başına tek Google girişi (OS keyring), Claude `CLAUDE_CONFIG_DIR` ile izole profil. "Tek Entropy kimliği" = **tek durum katmanı** (giriş var mı, kota/oturum penceresi, son hata, yeniden giriş yönlendirme), oturum devam bayrakları (`agy -c/--conversation`, `claude --resume/--continue`) Entropy konuşma kimliğine eşlenir.

## 3. Mimari
### 3.1 Birleşik graf (tek bilinç)
- Tek depo: mevcut SQLite bilişsel bellek genişletilir (ayrı graf DB yok). Tablolar: `nodes(id, type, title, body, importance, created_at, updated_at, scope)`; `edges(src, dst, type, t_valid_from, t_valid_to, ingested_at, weight, provenance)`; `communities(id, label, summary, member_count)`.
- Düğüm türleri: `episode`, `fact`, `entity`, `procedure`, `agent`, `office`, `task`, `report`, `session`, `community`. Kenar türleri: `derived_from`, `contradicts`, `supersedes`, `triggered`, `produced`, `member_of`, `similar_to`.
- Yazma yolu (ingest): rapor/görev/oturum düğümü → olgu çıkarımı (önce kural tabanlı: başlık/anahtar-değer/sayısal ifade; LLM'li çıkarım yalnızca damıtma sırasında, bütçeli) → kopya/çelişki uzlaştırma (aynı varlık + aynı yüklem, farklı değer → eski kenar `t_valid_to`, yeni kenar `supersedes`) → önem puanı (kaynak türü, tekrar sayısı, kullanıcı sabitlemesi).
- Okuma yolu (query): hibrit tohumlama (vektör + BM25) → 2 adım yayılım / PPR → "yalnızca geçerli" ve tür/zaman filtresi → bütçeye göre kırpma. Ebbinghaus + önem + ilgi ağırlıklı skor.
- Desk belleği: `Offices/*/MEMORY.md` ve `Agents/*/MEMORY.md` kapsam düğümlerine `member_of` ile bağlı **alt-graf**; ayrı depo yok. Kapsam sızıntısına karşı sorguda kapsam filtresi (varsayılan: aktif ofis + genel).
- Konsolidasyon (arka plan, LLM'siz + isteğe bağlı bütçeli LLM): yakın-kopya birleştirme, topluluk özet düğümleri (etiket yayılımı zaten var), yansıma düğümleri (10 olay → 1 çıkarım).
- Görselleştirme: açılışta topluluk/özet düğümleri (~100), tıklayınca kademeli açılma, **zaman kaydırıcısı**, tür ve önem filtreleri, "geçerli olanlar" varsayılan; mevcut Canvas 2D motoru korunur.

### 3.2 Ajan iletişimi ve yönetim
- Posta kutuları: `Offices/<ofis>/inbox/*.json` ve `Agents/<ad>/inbox/*.json` (atomik yaz-yeniden adlandır); mesaj şeması A2A benzeri: `{id, task_id, from, to, role, kind: instruction|report|question|status, parts, status, created_at, terminal: bool}`. Her görev terminal olay yayar (completed/failed/canceled) — asılı görev yok.
- Entropy AI ↔ orkestratör: Entropy, ofis posta kutusuna talimat bırakır; orkestratör kart planlarken okur; sonuç raporu Entropy'nin gelen kutusuna (Rapor Merkezi) düşer. Ajanlar arası doğrudan mesaj (eş-eş) yalnızca aynı ofis içinde.
- Yönetim: ofis durum panosu (salt-okunur özet), kota/harcama, çalışan görevler, son terminal olaylar; `/desk` ve Agent Desk'te aynı veri.
- Gözlemlenebilirlik: ledger'a adım/araç düzeyinde iz (mevcut stream olaylarından), Langfuse tarzı toplu/açık görünüm (Faz 5-opsiyonel).

### 3.3 Rapor Merkezi (Zen ve Chat)
- Gelen kutusu (Faz 4 iskeleti üzerine): kaynak (yetenek/ofis/ajan/oturum), önem × aciliyet rozeti, otomatik kümeleme (konu + ofis + kart; başlık TF-IDF/gömme), küme başına **digest kartı** (3 satır bulgu + 1 karar önerisi), okundu/pin/arşiv, güven eşiği: yüksek güvenli rutin raporlar otomatik arşive "sessiz" düşer, düşük güvenliler öne çıkar.
- Orkestratör sohbeti: kartın üstünde "orkestratöre sor / revizyon iste" → posta kutusuna mesaj, yanıt aynı iş parçacığında; Entropy sohbetinde `/ask <ofis> ...`.
- Yaşam tarzı arayüz: komut paleti (Ctrl+K), odak modu (tek panel), zaman çizelgesi (bugün ne oldu), bildirim merkezi; Zen/Chat paralel.

### 3.4 Tek kimlik ve agentic sohbet
- Sağlayıcı durum katmanı: her sağlayıcı için giriş durumu, kota/oturum penceresi (CLI çıktısından), son hata; rozet ve ayarlar; giriş düşünce yönlendirme (`claude login`, agy giriş akışı). Claude için isteğe bağlı `CLAUDE_CONFIG_DIR` "Entropy profili".
- Konuşma eşlemesi: Entropy `conversation_id` ↔ agy `--conversation` / Claude `--resume`; her tur uygun bayrakla devam.
- Agentic sohbet: Entropy AI bir sağlayıcıda, ofis ajanı ötekinde; aktarım posta kutusu + bus; sohbette iki taraf ayrı balonla görünür; kesinti/handoff sayfası (Faz 1) her iki tarafta.

## 4. İş kalemleri, ajanlar, kabul
| # | İş | Ajan | Kabul |
|---|---|---|---|
| 5.1 | Graf şeması göçü (çift zamanlı kenarlar, düğüm türleri, önem, provenans), kopya/çelişki uzlaştırma, PPR yayılımı, "yalnızca geçerli" filtresi | memory-rag | Göç testi (eski DB → yeni şema), çelişki senaryosu (eski kenar geçersiz, yeni supersedes), geri çağırma sıralaması eşitlik + yayılım kazancı ölçümü |
| 5.2 | Desk belleğinin tek grafa katılması (kapsam alt-grafı), topluluk/yansıma özet düğümleri, arka plan konsolidasyon | memory-rag | Kapsam sızıntısı testi; özet düğümü sayısı; konsolidasyon süresi |
| 5.3 | Posta kutusu + A2A benzeri mesaj şeması + terminal olay sözleşmesi; Entropy↔orkestratör talimat/rapor akışı; `/ask <ofis>` | agy-integration | Sahte köprüyle: talimat → plan → rapor gelen kutusunda; asılı görev testi (terminal zorunlu) |
| 5.4 | Sağlayıcı durum katmanı + konuşma eşlemesi + agentic sohbet | agy-integration | `claude auth status`/agy durumu rozeti; oturum devam bayrakları testte doğru; iki sağlayıcılı sohbet sahte köprüyle |
| 5.5 | Rapor Merkezi (kümeleme, digest, önem×aciliyet, güven eşiği, orkestratör sohbeti), komut paleti, odak modu, zaman çizelgesi, bildirim merkezi; Zen/Chat paralel | ui-engineer | Ekran görüntüleri; 200 sahte raporla okunabilirlik; testler |
| 5.6 | Graf görselleştirme: topluluk açılımı, zaman kaydırıcısı, tür/önem filtreleri, "geçerli" varsayılan | ui-engineer (+memory veri) | 1000+ düğümde ≥30 fps; ekran görüntüsü |
| 5.7 | QA: tam paket, build, perf trendi, canlı 20 sn, gerçek koşu (kota kararın) | qa-build | 0 regresyon |

Sıra: 5.1 → 5.2 (memory) ‖ 5.3 → 5.4 (agy) ‖ 5.5 (ui) → 5.6 (ui, 5.2 verisiyle) → 5.7. Sonunda `v0.3.0` ve Faz 5 ilerleme raporu.

## 5. Riskler ve kararlar
- Şema göçü mevcut 900 düğümü etkiler: yedek + geri dönüş; göç testi zorunlu.
- LLM'li olgu çıkarımı kota yer: yalnızca damıtma anında ve bütçeli; varsayılan kural tabanlı.
- agy'de makine başına tek hesap: çoklu hesap yalnızca API anahtarıyla; tasarım tek hesap varsayar.
- Rapor triyajının yanlış "sessiz arşiv" kararı: güven eşiği ayarlanabilir, arşiv her zaman görünür.
