# Entropy AI Faz 5 — Dış Araştırma Notu (Eylül 2026)

Kapsam: bellek grafiği mimarileri, ajanlar arası iletişim, rapor triyaj UX'i, iki sağlayıcılı tek kimlik. Yalnızca web taraması; "doğrulanmadı" işaretli maddeler tek kaynaklı veya blog kaynaklıdır.

## 1. Bilişsel bellek grafiği: dışarıda ne yapılıyor
- **Zep / Graphiti (arXiv:2501.13956):** sohbet "episode" olarak alınır, LLM ile varlık+ilişki çıkarılır, **çift zamanlı** grafa yazılır: her kenarda `t_valid`/`t_invalid` ve ingest zamanı. Çelişkide eski kenar silinmez, geçersizleştirilir; "şu an ne doğru / 3 ay önce ne doğruydu / nereden geldi" soruları yanıtlanır. Geri çağırma hibrit (semantik + BM25 + graf gezinme). Entropy için en doğrudan kopyalanabilir desen.
- **Mem0:** kullanıcı/oturum/ajan kapsamlarında olgu çıkarma; zamansal sorgu modeli yok; LongMemEval'da Zep'in gerisinde (doğrulanmadı, satıcı blogu).
- **Letta / MemGPT:** core (bağlamda küçük blok) / recall (aranabilir geçmiş) / archival (araçla sorgulanan uzun dönem); ajan kendi belleğini araçlarla düzenler. Entropy'de AGENT.md/MEMORY.md ayrımı kaba karşılığı; eksik: ajanın core bloğunu güncelleme aracı.
- **A-MEM (arXiv:2502.12110):** Zettelkasten notları; yazılırken ilgili notlara kendiliğinden bağ kurar ve komşu notların özetlerini günceller; %85–93 token tasarrufu iddiası. Obsidian kasamız buna yakın; eksik olan otomatik bağ + komşu revizyonu.
- **CoALA (TMLR 2024):** çalışma / episodik / semantik / prosedürel bellek; Entropy karşılıkları: bağlam kurucu / oturum-rapor / olgular / PLAYBOOK. Tek grafın düğüm türü etiketleri olarak kullanılabilir.
- **HippoRAG 2 (arXiv:2502.14802):** pasaj + ifade düğümleri, tohumlu Personalized PageRank; ilişkisel sorularda ~7 F1 kazanç. Mevcut hibrit geri çağırmaya eklenecek en ucuz iyileştirme: tohumlu k-adım yayılım / PPR yeniden sıralama.
- **Generative Agents:** puan = yenilik + önem + ilgi; yansıma ile üst seviye çıkarımlar. Entropy'nin Ebbinghaus'u yeniliği kapsıyor; önem ve yansıma/özet düğümü muhtemelen eksik.
- **Cognee:** vektör + LLM sentezli graf; yalnızca-ekleme yazım + periyodik yeniden konsolidasyon (arka plan işi).
- **2026 uzlaşısı:** yazma anında çelişki uzlaştırması, daha iyi sıralayıcıdan çok kazandırır; yığılmış çelişkiler top-k'da birlikte dönünce davranış tutarsızlaşır; arka planda yakın-kopya birleştirme hiyerarşik mimariden daha etkili.

### Entropy için önerilen birleşik graf şeması
Düğüm türleri: episode, fact, entity, procedure, agent, office, task, report, session, community. Kenar türleri: derived_from, contradicts, supersedes, triggered, produced, member_of, similar_to. Her kenarda `t_valid_from`, `t_valid_to` (NULL = geçerli), `ingested_at`; çelişkide eski kenara `t_valid_to` + `supersedes`; hiç silme yok. Puanlama: importance + recency (Ebbinghaus) + relevance. Sorgu: hibrit tohumlama → 2–3 adım yayılım/PPR → tür ve zaman filtresi → bütçeye göre kırpma. Desk/ofis belleği ayrı depo değil, aynı grafta office/agent düğümüne bağlı alt-graf.

### Görselleştirme (1000+ düğüm)
Varsayılan görünümde topluluk/özet düğümleri ve kademeli açılma; çok ölçekli düzen; zaman penceresi kaydırıcısı; tür ve önem filtreleri; etiketler yalnızca zoom eşiğinin üstünde. Entropy karşılığı: açılışta ~80–150 topluluk düğümü, "geçerli olanlar" varsayılan filtre, zaman kaydırıcısı, tür renkleri.

## 2. Ajanlar arası iletişim ve yönetim
- **A2A:** Linux Foundation'da; v1.0 Ocak 2026 (imzalı Agent Card). Agent Card `/.well-known/agent-card.json`; JSON-RPC 2.0 + SSE; Task durumları: submitted, working, input_required, auth_required, completed, failed, canceled, rejected. Kural: her görev terminal olay yayımlamalı.
- **Desenler:** orkestratör-işçi varsayılan; blackboard yazma çakışmasına açık; posta kutusu/kuyruk büyük ağlarda daha iyi ölçekleniyor.
- **Claude Code Agent Teams (Şubat 2026, deneysel):** takım lideri + eşler; posta kutusu + paylaşılan görev listesi; eşler doğrudan mesajlaşır. Ofis modelimizle örtüşen referans.
- **Öneri:** dosya tabanlı posta kutusu + bus olayı (`Offices/<ofis>/inbox/*.json`, atomik yaz-yeniden adlandır), mesaj şeması A2A'ya benzer; blackboard yalnızca salt-okunur ofis durum panosu.

## 3. Rapor triyaj UX'i
- Ana risk inceleme yorgunluğu: güven eşiğine göre yönlendirme, çıktıları kaynak işin yüzeyine toplama, bağlam bazlı duruş onayı.
- Gözlemlenebilirlik: Langfuse graf görünümünün Aggregated/Expanded kipleri; kullanılabilir araçlar ile çağrılanlar ayrı.
- Zen için Rapor Merkezi: gelen kutusu (okunmadı/pin/arşiv), otomatik kümeleme (konu + ofis + kart) ve küme başına digest kartı, önem × aciliyet rozeti, 3 satır bulgu + 1 karar önerisi, rapordan grafa `report` düğümü, orkestratöre sor / revizyon iste düğmesi (asenkron eskalasyon).

## 4. Tek giriş, iki sağlayıcı
- İki oturum birbirini tanımaz (doğrulandı). `agy` Gemini CLI'ın halefi; Gemini CLI ücretsiz/Pro/Ultra için 18 Haziran 2026'da kapatıldı; `agy` `~/.gemini` dizinini yeniden kullanır.
- agy abonelik kimliğini OS keyring'de tutar ve makine başına tek giriş; profil seçici yok (tek kaynak, doğrulanmadı). Çoklu hesap yalnızca Gemini API anahtarıyla. Claude Code `CLAUDE_CONFIG_DIR` ile tam izole profil verir.
- Kota: Antigravity kotası uygulama + CLI + SDK arasında ortak; ajan kendi kalan kotasını göremez; rozet CLI çıktısından türetilmeli.
- Oturum devam: `agy -c/--continue`, `--conversation <id>`; Claude `--continue`, `--resume`.
- Öneri: "tek Entropy kimliği" = tek durum katmanı (giriş, kota/oturum penceresi, son hata, yeniden giriş yönlendirme), Claude için `CLAUDE_CONFIG_DIR` ile Entropy profili, iki CLI arasında ortak konuşma kimliği + dosya posta kutusu.

## 5. Muhtemel boşluklar (dış bakış, kanıtlanmadı)
Zamansal geçerlilik yok; yazma anında çelişki tespiti yok; önem puanı yok; yansıma/özet düğümü yok; ajanlar arası doğrudan mesajlaşma yok; terminal durum sözleşmesi yok; rapor triyajı yok; gözlemlenebilirlik izi yok; kota rozeti tahmini.

## 6. Öncelikli iş kalemleri
1. Çift zamanlı kenar alanları + "yalnızca geçerli" filtresi. 2. Yazma anında çelişki/kopya uzlaştırması + arka plan konsolidasyon. 3. Birleşik graf (desk belleği kapsam kenarıyla). 4. Dosya posta kutusu + A2A benzeri şema + zorunlu terminal durum. 5. Zen Rapor Merkezi. 6. Tohumlu graf yayılımı (PPR) + önem skoru. 7. Grafik okunabilirliği (topluluk düğümleri, kademeli açılma, zaman kaydırıcısı). 8. Sağlayıcı durum katmanı (giriş rozeti, kota, `CLAUDE_CONFIG_DIR`, oturum eşlemesi). 9. (opsiyonel) adım/araç düzeyinde iz + token muhasebesi.

## Kaynaklar
Zep (arXiv:2501.13956) · Graphiti (Neo4j blog) · Zep temporal KG · Particula: Mem0 vs Zep vs Letta vs Cognee (2026) · Vectorize: Mem0 vs Letta · A-MEM (arXiv:2502.12110) · HippoRAG 2 (arXiv:2502.14802) · CoALA özeti (Medium/CodeX) · Hindsight: The Consolidation Problem (May 2026) · Mem0: memory eviction · Tyk: A2A spec · Wikipedia: Agent2Agent · Developers Digest: Claude Code Agent Teams 2026 · Multi-agent orchestration patterns · GI 2025 visual summaries for large networks · Multi-scale community visualization · Agent observability 2026 · Velt: human-in-the-loop (June 2026) · Human review bottleneck (May 2026) · continuumcode: Antigravity CLI guide · agentsroom: Antigravity single login (Aug 2026) · gemini-cli discussion #27274 · Claude Code docs: sessions, .claude directory
