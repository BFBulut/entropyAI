# Entropy AI — Durum Analizi ve Yol Haritası (v0.1.7)

Tarih: 2026-09-09 · Yazar: Orkestratör (Claude Fable 5.1) · Sürüm: `ai/v0.1.7` branch, `v0.1.7` etiketi

## 1. Projemiz ne hâlde

Ölçülen durum (son QA fazı, 2026-09-08):

| Alan | Durum | Kanıt |
|---|---|---|
| Test paketi | 2009 test, 0 hata | tam koşu 277 sn |
| Bilişsel bellek | 859 düğüm, 862 not; hibrit geri çağırma yeni sorguda ~95 ms | perf_bench |
| Bağlam bütçesi | 4000 token tavanı; yetenekli turda ~3,3k, yeteneksizde ~1,1k | perf_bench |
| Yordam damıtma | financial-auditor 104/104, media-agency-soldier 16/16, autonomous-agent 513/513 (ekranda), tazeleme tüm arşivi kapsıyor | kasa durumu |
| Yönlendirme | doğruluk %90,7, makro F1 0,889, yanlış pozitif %0 | routing_eval |
| Grafik | organik kuvvet düzeni, 4–6 ms/kare, kurulum 0,6 sn | ölçüm |
| Başlangıç | içe aktarma 713 ms; pencere ~12 sn | QA |
| Sağlamlık | kapanış kancası, çökme günlüğü, tek kopya, iş parçacığı düzeltmeleri | testler |

Kullanıcı ekranından görülen açık sorunlar (bu raporun 1. fazının konusu):

1. **Yeni raporlar damıtma sayacına düşmüyor.** financial-auditor ve autonomous-agent için yeni araştırmalar yapıldığında "damıtılacak öğeler" değişmiyor; "Damıt" sıfırdan tazeleme yapıyor, yeni raporları eklemiyor. Olası kök nedenler (doğrulanacak): rapor→yetenek atfı yalnızca statik indeksle (`/distill index`) yapılıyor ve yeni raporlar indekse girmiyor; `PlaybookStore.status` dosya-bilgisi önbelleği yeni dosyayı görmüyor; yetenek kartı durumu yalnızca yenilemede hesaplanıyor. Beklenen davranış: rapor kaydedildiği anda yeteneğine atfedilir, sayaç canlı artar, "Damıt" yalnızca okunmamışları işler; tazeleme ayrı ve açık bir eylemdir.
2. **google-flow yeteneğinde damıtma düğmesi kapalı.** Yetenek kendi kendine oluşturulmuş (slash, hafıza haritası, yetenek kartı var) ama hiçbir rapor ona atfedilmediği için "kaynak yok" durumunda. Aynı kök neden.
3. **Arayüz.** Özellikler tamam, ama görsel dil ağır: koyu bloklar, sıkışık paneller, küçük punto, kart içi düğme kalabalığı. Ekran görüntüsündeki dört panel (Raporlar / Sistem / Bilişsel Hafıza / Sohbet+Terminal) korunarak modern ve okunaklı bir düzen gerekiyor.
4. **Ajan modeli.** Bir görev verildiğinde tek seferlik alt ajan kurulup kilitlenme/model sapması yaşanıyor. İstenen: kalıcı ajanlar, aynı model (gemini-3.8-flash-high), yetenekleri akıllı kullanan, ofislerde örgütlenmiş bir **Agent Desk** paneli.

## 2. Araştırma: güncel mimariler ve bize düşen dersler

### 2.1 Karpathy'nin LLM Wiki deseni (Nisan 2026)
Üç katman: `raw/` (değişmez kaynaklar), `wiki/` (LLM'in yazdığı ve baktığı özet/varlık/kavram sayfaları, `index.md`, `log.md`), şema dosyası (`CLAUDE.md`). Üç işlem: **ingest** (yeni kaynağı işle, 10–15 sayfaya dokun), **query** (wiki'den yanıtla, değerli yanıtı sayfa olarak geri yaz), **lint** (çelişki, bayat iddia, öksüz sayfa, eksik çapraz bağ). İlke: "bilgi bir kez derlenir, her sorguda yeniden türetilmez."

**Entropy'ye eşleme.** Zaten aynı iskeletteyiz: Reports/ = raw, Skills/<yetenek>/PLAYBOOK.md = wiki'nin yordam sayfası, GEMINI.md = şema, damıtma = ingest, bağlam kurucu = query. Eksik olan üç şey: (a) yetenek başına **varlık/kavram sayfaları** ve **index.md/log.md** (bugün tek bir playbook'a sıkışıyoruz, 9000 karakter tavanına dayanıp son bölümler düşüyor); (b) **lint** işlemi (çelişki ve bayatlık denetimi, öksüz rapor tespiti); (c) **query'nin geri yazması** (iyi bir yanıtın wiki'ye sayfa olarak dönmesi). Öneri: playbook'u "yordam sayfası" olarak koru, yanına `Skills/<yetenek>/wiki/` (kavramlar, varlıklar, index, log) ekle; damıtma çıktısını bu sayfalara dağıt; bağlam kurucu sorguya göre sayfa seçsin. Raporların atfı ingest anında yapılır (1. fazın 2. maddesi tam da budur).

### 2.2 RAG mimarileri (2026)
GraphRAG, LightRAG, HippoRAG, PathRAG çok atlamalı sorularda kazandırıyor; ACL 2026'daki "Is GraphRAG needed?" çalışması ise çoğu kurumsal senaryoda hibrit vektör+BM25'in yeterli olduğunu ve grafiğin yalnızca ilişkisel/çok atlamalı sorularda değer kattığını gösteriyor. Asıl kayma **agentic RAG**: sabit bir getirim boru hattı yerine modelin kademeli arayüzlerle (indeks → özet → parça) kendi aramasını yönetmesi (A-RAG). Bellek katmanları üçe ayrıldı: bağlam içi, vektör, oturumlar arası kalıcı bellek.

**Bize düşen.** Hibrit geri çağırmamız ve Ebbinghaus/yenilik ağırlıklarımız yerinde; GraphRAG'e geçmek gereksiz maliyet. Yapılacak: (a) wikilink/benzerlik grafiğimiz üzerinde **kişiselleştirilmiş PageRank** ile komşu genişletme (HippoRAG'in ucuz çok atlaması) — grafik verisi zaten var; (b) bağlam kurucuya **agentic döngü**: ilk bağlam yetmezse ajan `index.md` → sayfa → rapor sırasıyla derinleşsin; (c) benzerlik kenarlarını başlık TF-IDF yerine gerçek gömme vektörleriyle kur (mevcut fastembed).

### 2.3 Harness mühendisliği
2026'nın ana yatırım alanı: sabit modelin etrafındaki ortam (istemler, araçlar, bağlam politikası, kancalar, sandbox, geri bildirim döngüleri). Anthropic'in uzun süreli uygulama harness'ı üç rolü ayırıyor: **Planner** (kısa isteği spesifikasyona açar), **Generator** (özellikleri parça parça uygular, git kullanır), **Evaluator** (çalışan uygulamayı gerçekten kullanır, sert eşikli ölçütlerle notlar). Aktarımlar dosyayla yapılır ("sprint sözleşmesi"); ilkeler: üretimle değerlendirmeyi ayır, tercihleri somut ölçütlere çevir, model iyileştikçe harness'ı sadeleştir. LangChain ekibi yalnızca harness'ı düzenleyerek Terminal Bench'te 30. sıradan 5.'ye çıktı.

**Bize düşen.** Bu oturumda uyguladığımız orkestratör + 4 ajan + QA düzeni tam bu desendir. Entropy'nin içine taşınacak hâli **Agent Desk**'tir: her ofis = bir harness (orkestratör + üretici ajanlar + değerlendirici), aktarımlar kasadaki dosyalarla (görev sözleşmesi, ilerleme, rapor), değerlendirici gradable ölçütlerle. Ajanlar agy'nin özel ajan mekanizmasıyla (`.agents/agents/<ad>/agent.md`: `model`, `rules`, `commandExecutionPolicy`) **kalıcı** tanımlanır; model orada sabitlenir, böylece "alt ajan kurup modelin sapması" biter. Tek seferlik iş için de kalıcı bir persona kullanılır; görev bitince ajan değil yalnızca görev kapanır.

### 2.4 Obsidian ekosistemi
Şubat 2026'dan beri Obsidian'ın resmî CLI'ı var (arama, not oluşturma, günlük not, ekleme); kasa "ajanların düşündüğü, hatırladığı altyapı" olarak konumlanıyor; Vault Operator (yerel vektör indeks + wikilink genişletme + yeniden sıralayıcı) ve claude-obsidian (kaynak yakalama, iddia defteri, kasa kanıtıyla yanıt) gibi eklentiler var.

**Bize düşen.** Düz markdown ve wikilink'te kalmak doğru karar. Ekleme: Obsidian CLI varsa raporları/wiki sayfalarını onun üzerinden yazıp Obsidian'ın kendi grafiği ve arama indeksini de güncel tutmak; iddia defteri (kaynak→iddia) fikrini lint'e taşımak.

### 2.5 Google Flow / Veo
Flow bir stüdyo arayüzü, Veo 3.1 model; otomasyon için Gemini API/Vertex yolu var (ücretli, Flow kredilerinden ayrı; Flow'da günde 50 ücretsiz kredi). Bizim google-flow yeteneği tarayıcı üzerinden Flow'u kullanıyor; kalıcı ve ölçülebilir yol Gemini API'de Veo 3.1. Damıtma için önce rapor atfı gerekir (1. faz).

## 3. Birinci faz planı (onay bekliyor)

Dört ajan: `ui-engineer`, `memory-rag-engineer`, `agy-integration-engineer`, `qa-build-engineer` (hepsi Opus 5, low effort). Orkestratör kod yazmaz.

| # | İş | Ajan | Kabul ölçütü |
|---|---|---|---|
| 1 | Rapor→yetenek atfı canlı: rapor kaydedilince aktif yeteneğe atfedilir (Skills/<y>/Reports + indeks anında güncellenir, ReportWatcher), kart sayacı canlı artar, "Damıt" yalnızca okunmamışları işler, tazeleme ayrı eylem; google-flow düğmesi açılır | memory-rag | Yeni rapor 5 sn içinde sayaçta; damıt = artımlı; test + gerçek kasada kanıt |
| 2 | Wiki katmanı v1: Skills/<y>/wiki (index.md, log.md, kavram sayfaları) + lint komutu (`/lint <yetenek>`) + bağlam kurucunun sayfa seçmesi | memory-rag | Playbook tavanı aşılmadan bilgi kaybı yok; lint öksüz/bayat listesi |
| 3 | Arayüz modernizasyonu (özellik kaybı yok): üst çubukta "Agent Desk" düğmesi, panel ızgarası ve boşluklar, tipografi, kart sadeleştirme (ikon düğmeler + menü), rozetler; Zen ve Chat paralel | ui-engineer | Offscreen ekran görüntüleri + tüm UI testleri; dört panel korunur |
| 4 | Agent Desk paneli v1 (ayrı pencere, ikinci monitöre taşınabilir): ofisler (mevcut Pixel Studio varlıkları), ofis başına orkestratör + kalıcı ajanlar (agy özel ajan dosyaları, model sabit gemini-3.8-flash-high), görev atama → arka plan görevi → rapor → kasa; ofis belleği Entropy bilişsel belleğiyle ortak | agy-integration + ui | Ofis oluştur/ajan ekle/görev ver/rapor gör akışı çalışır; ajanlar `.agents/agents` altında kalıcı |
| 5 | Harness disiplini: her ajan görevi için dosya tabanlı "görev sözleşmesi" (hedef, ölçütler, çıktı), değerlendirici ajanın (QA) gradable ölçütlerle notlaması, tam paket + build | qa-build | Sözleşme dosyası şablonu; QA raporu ölçüt tablosu |

Sıra: 1 → 3 ve 4 paralel → 2 → 5. Kota: 1 ve 2 damıtma çağırmaz; 4'ün uçtan uca testi gerçek agy görevi ister (kullanıcı onayıyla, küçük görev).

## 4. Riskler ve açık kararlar
- **Agent Desk tabanı.** Depoda `src/entropy/agent_desk/` (izlenmeyen) ve `Agents/` dizinleri var; bağımsız EntropyAgentDesk uygulaması korunacak, Entropy içindeki panel onun ofis/piksel modüllerini yeniden kullanacak. Ayrı bir çatal kaçınılmazsa raporda gerekçelendirilir.
- **Kalıcı ajan kimliği.** agy ajan tanımı çalışma dizinine göre keşfedilir; proje değişince ajan görünmez. Çözüm: ofis ajanları uygulama kökünde (`.agents/agents/`) ve proje köküne bağlanan sembolik/ kopya tanım.
- **Wiki katmanı tokeni.** Sayfa sayısı arttıkça bağlam seçimi zorlaşır; index.md ile sorgu bazlı seçim ve 4000 token tavanı korunur.
- **GitHub.** Depoda uzak yok ve `gh` kurulu değil; `ai/v0.1.7` ve `v0.1.7` yerelde. Push için: `git remote add origin <url>` sonra `git push -u origin ai/v0.1.7 --tags`.

## Kaynaklar
- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Obsidian LLM Wiki uygulaması: https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base-andrej-karphaty
- GraphRAG/HippoRAG/PathRAG karşılaştırması: https://medium.com/graph-praxis/graphrag-vs-hipporag-vs-pathrag-vs-og-rag-choosing-the-right-architecture-for-your-knowledge-graph-a4745e8b125f
- A-RAG (agentic RAG): https://arxiv.org/pdf/2602.03442 · Is GraphRAG needed? (ACL 2026): https://aclanthology.org/2026.gem-main.40.pdf
- Anthropic harness tasarımı: https://www.anthropic.com/engineering/harness-design-long-running-apps · Fowler: https://martinfowler.com/articles/harness-engineering.html · Awesome harness: https://github.com/ai-boost/awesome-harness-engineering
- Ajan yığını 2026 (O'Reilly): https://www.oreilly.com/radar/the-ai-agents-stack-2026-edition/ · Kalıcı ajan belleği: https://arxiv.org/pdf/2604.01670 · Bellek durumu 2026: https://mem0.ai/blog/state-of-ai-agent-memory-2026
- Obsidian kasa = bilgi grafiği: https://medium.com/@vreshch/your-obsidian-vault-is-already-a-knowledge-graph-i-turned-on-the-lights-56c07233db89 · Vault Operator: https://community.obsidian.md/plugins/vault-operator
- Veo/Gemini API: https://ai.google.dev/gemini-api/docs/video · Flow rehberi: https://aividpipeline.com/blog/google-flow-veo-3-1-guide-2026
