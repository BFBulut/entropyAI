# Entropy AI — Karma Mimari ve Faz Planı (v2, onay bekliyor)

Tarih: 2026-09-09 · Orkestratör: Claude Fable 5.1 (high) · Uygulayıcılar: 4 ajan, Opus 5 low effort · Önceki rapor: `2026-09-09_Entropy_AI_Durum_ve_Yol_Haritasi_v0.1.7.md`

Kaynaklar (§3b): Claude Code sıkıştırma rehberi https://hidekazu-konishi.com/entry/claude_code_compaction_and_long_session_guide.html · Codex/Claude Code/OpenCode karşılaştırması https://codex.danielvaughan.com/2026/04/14/context-compaction-deep-dive-codex-cli-claude-code-opencode/ · Gözlem maskeleme çalışması https://arxiv.org/pdf/2508.21433 · Slipstream https://arxiv.org/pdf/2605.08580 · Bağlam mühendisliği 2026 https://www.louisbouchard.ai/context-engineering-2026/ · Bellek/sıkıştırma/temizleme https://tianpan.co/blog/2026/02/26/context-engineering-memory-compaction-tool-clearing · Antigravity geçiş rehberi https://medium.com/@niels.buekers/from-gemini-to-antigravity-the-developers-survival-guide-to-google-s-new-agentic-cli-ea0579cfd1a0 · Antigravity devam ettirme https://www.codeagentswarm.com/en/guides/antigravity-cli-conversation-history · Handoff/CLAUDE.md https://blink.new/blog/claude-code-context-management

## 0. Çalışma düzeni (senin kurallarınla)
- Ben plan, analiz, görev dağıtımı, rapor inceleme ve sana geri dönüş yaparım; kod yazmam.
- Ajanlar yalnızca benim emrimde çalışır, sana hiç dönmez; düşündüklerini ajan transkriptlerinden ve her faz sonundaki raporumdan görürsün.
- Her faz sonunda: commit + build + test kanıtı + ekran görüntüleri + rapor. Bir sonraki faza **senin onayınla** geçilir. Faz içinde onay istemem; token biterse de sormam, kaldığım yerden devam ederim.
- Sürüm: her faz `ai/v0.1.x` branch'inde etiketlenir. **Not:** bu depoda `origin` uzak adresi tanımlı değil (`git remote -v` boş). Faz 1'de push için GitHub adresini yazman yeterli; ekleyip `ai/v0.1.7` + etiketleri ben gönderirim.

## 1. Yeni mimari: iki sağlayıcı, tek köprü

**Kimlik doğrulama gerçeği.** Claude API her zaman token başına ücretlidir (Opus 5: 5$/25$ per 1M), Claude aboneliğine dahil değildir. Aboneliğin kapsadığı programatik yol **Claude Code CLI'ın başsız modu**dur: `claude -p --output-format stream-json` (kurulu: 2.1.265). Bu, agy'nin `agy -p --output-format stream-json` yolunun birebir eşidir. Gemini tarafında Antigravity aboneliği aynı şekilde `agy` üzerinden kullanılır.

**Tasarım.**
```
ProviderBridge (soyut)        ── send_prompt_async, send_background_task_async, agents, usage, cancel, shutdown
├── AgyBridge   (mevcut AgyProcessBridge; Gemini aboneliği; .agents/agents/<ad>/agent.md)
├── ClaudeCodeBridge (yeni; claude -p stream-json; abonelik oturumu `claude login`; .claude/agents/<ad>.md; MCP: .mcp.json)
└── ClaudeApiBridge (isteğe bağlı; ANTHROPIC_API_KEY varsa; anthropic SDK, claude-opus-5; yalnızca kullanıcı açarsa)
```
- Ayarlar: sağlayıcı seçimi (Antigravity / Claude Code / Claude API), her sağlayıcı için model listesi ve varsayılan model, oturum durumu rozeti (agy: kota; claude: `claude auth status`). Üst çubuktaki model seçici sağlayıcıya göre dolar.
- Ortak akış olayları (stream-json → bus sinyalleri) tek adaptörden geçer; token muhasebesi, ledger, rapor kaydı, damıtma, konsolidasyon **sağlayıcıdan bağımsız** kalır.
- Ajan tanımı tek kaynaktan iki biçime derlenir (bkz. §2): agy için `.agents/agents/<ad>/agent.md`, Claude Code için `.claude/agents/<ad>.md` (model/effort/tools ön bilgisi).
- Aynı görev her iki sağlayıcıda da koşabilir; kart üzerinde sağlayıcı ve model görünür.

## 2. Entropy'nin kendi ajanları ("Ajanlar" sekmesi)
Sol paneldeki "MCP Sunucuları" sekmesinin yanına **Ajanlar**. Teferruatsız, dosya tabanlı:
- Kaynak: `<kasa>/Entropy/Agents/<ad>/AGENT.md` — ön bilgi: `name, role, provider (agy|claude), model, effort, skills: [...], tools/policy, memory: Agents/<ad>/MEMORY.md`, gövde: sistem istemi. Entropy bu dosyayı iki CLI biçimine derler (§1), yani kalıcı ajan hem Entropy'de hem CLI'da aynı kişidir; model sapması biter.
- Sekme: liste (rol, sağlayıcı, model, son görev, durum), Ekle/Düzenle (markdown editörü + model açılır listesi), Sil, "Görev ver". Entropy kendisi de ajan ekleyip düzenleyebilir (agy/claude görevine `Agents/` klasörü yazma izni ve manifestte ajan listesi).
- Farkındalık: her istemin manifestine ajan listesi (ad+rol+yetenekler) girer; Entropy "bu işi X ajanına ver" diyebilir.
- Görev kartları (basit kanban: Bekliyor / Çalışıyor / İnceleme / Bitti): kart = kasadaki görev sözleşmesi dosyası (`Entropy/Tasks/<id>.md`: hedef, ölçütler, ajan, sağlayıcı, çıktı yolu). Kart çalışınca mevcut arka plan görev yolu kullanılır; bitince rapor kasaya yazılır, yeteneğe atfedilir ve damıtmaya girer.
- Ajan → Entropy raporu **query sayfası** biçimindedir (Karpathy wiki'nin "query çıktısını sayfa olarak geri yaz" ilkesi): `Skills/<yetenek>/wiki/queries/<tarih>-<konu>.md` + `log.md` satırı. Entropy bunları bağlam kurucuda kullanır.

## 3. Entropy AI Agent Desk (uygulama içi)
- Eski `src/entropy/agent_desk/`, `Agents/*`, `EntropyAgentDesk.spec`, `run_agent_desk.py` silinir (senin onayınla; kullanılabilir piksel/ofis varlıkları `src/entropy/desk/assets/` altına taşınır).
- Yeni paket `src/entropy/desk/`: **ayrı pencere** (üst çubukta "Entropy AI" yanında "Agent Desk" düğmesi; pencere bağımsız, ikinci monitöre taşınabilir, konum/boyut hatırlanır).
- Model: Ofis = harness. Her ofiste bir **orkestratör ajanı** (planner) + üretici ajanlar + değerlendirici; ajanlar §2'deki kalıcı ajanlardır (ofise atanır). Görev kartları ofise düşer; orkestratör böler, ajanlar koşar, değerlendirici ölçütlerle notlar; sonuç kasaya rapor + wiki sayfası olarak iner; Entropy'nin bilişsel belleğiyle aynı SQLite ve kasa kullanılır (ofis belleği = `Agents/<ofis>/` altında MEMORY.md + wikilink'ler).
- Görsel: piksel ofis sahnesi (masa başına ajan, durum animasyonu: boşta/çalışıyor/hata), sağda kart panosu ve canlı çıktı akışı. Sağlayıcı ve model ajan kartında görünür.

## 3b. Bağlam aktarımı ve token temizliği (harness, ajan, wiki, hafıza için)

**Araştırmanın söylediği (2026).**
- Üretim uzlaşısı üç katman: (1) oturum içi çalışma belleği (tam, kayıpsız), (2) uzun oturumda **çapalı artımlı özet** ile sıkıştırılmış oturum belleği, (3) oturumlar arası kalıcı depo. Sıkıştırma varsayılan değil, adı konmuş bir kısıta yanıt olmalı; önbellekli istemde her şeyi tutmak çoğu zaman daha ucuz ve daha doğru.
- **Gözlem maskeleme** (eski araç çıktılarını yer tutucuyla değiştirmek) LLM özetlemesi kadar etkili ve %50+ ucuz (arXiv 2508.21433); özetleme çalışma süresine ~%15 ekliyor. Araç sonucu temizleme (tool-result clearing) sıfır maliyetli ilk adım.
- Claude Code: `/compact` (3 kademeli: araç sonucu kırpma → önbellek dostu strateji → 9 bölümlü yapılandırılmış özet), API tarafında `compact-2026-01-12` (sunucu tarafı özet) ve `context-management` (araç sonucu/düşünce temizleme). Pratik kural: **%60 doluluğa gelince sıkıştır, %90'ı bekleme; kapatmadan önce handoff yaz.** Slipstream (2605.08580) sıkıştırmayı yörüngeye karşı doğrulamayı öneriyor.
- Antigravity CLI: `/compress` yok; sıkıştırma arka planda otomatik; devam `agy -c` / `agy --conversation <id>`; konuşmalar `~/.gemini` altında.
- Dynamic Workflows (Mayıs 2026): tek büyük bağlam yerine **temiz bağlamlı alt ajanlara yayılım**; hiçbir ajan bağlam biriktirmez — tam da ofis/kart modelimiz.

**Entropy'ye uygulama.**
1. **Sohbet handoff'u.** Köprü, konuşma boyutunu (girdi token tahmini + agy `usage`) izler; %60 eşiğinde ya da `/handoff` komutuyla 9 bölümlü **yapılandırılmış aktarım sayfası** yazar (`Entropy/Sessions/<tarih>-<konu>.md`: hedef, kararlar, açık işler, dosyalar, hatalar, sonraki adım, kullanılan yetenekler/ajanlar, ölçümler, kaynaklar) ve yeni bir agy/claude konuşması bu sayfa + playbook ile başlar. Sayfa wiki'ye bağlanır (log.md) ve bağlam kurucu bir sonraki oturumda onu seçer. Kullanıcı sohbeti hiç kesilmez; "+ Yeni Sohbet" de aynı handoff'u üretir.
2. **Araç sonucu maskeleme.** Arka plan görevlerinin çıktıları belleğe ve rapora yazılırken uzun araç çıktıları yer tutucuyla değiştirilir (özet + dosya yolu); ledger ve bilişsel bellek bu maskelenmiş biçimi tutar. Terminal paneli ham akışı gösterir, bellek göstermez.
3. **Ajan ve ofis.** Her kart temiz bağlamla koşar (yeni süreç), aktarım yalnızca görev sözleşmesi + rapor dosyasıyla olur; orkestratör ajanı kendi bağlamını kart özetleriyle (maskelenmiş) taşır; ofis belleği `Agents/<ofis>/MEMORY.md` çapalı artımlı özetle güncellenir (her görev sonunda ekleme, her 10 görevde konsolidasyon).
4. **Wiki ve hafıza.** Damıtma ve query sayfaları zaten "bir kez derle" katmanı; ona **oturum aktarımı** ve **görev özetleri** de girer. Bilişsel belleğe yazılan her düğüm maskelenmiş ve kısa tutulur; Ebbinghaus zayıflaması kalır. Lint, handoff sayfalarındaki "açık işler"i takip eder.
5. **Ölçüm.** Token rozeti bağlam doluluk yüzdesi gösterir; perf düzeneğine "oturum başına token / handoff sayısı" metriği eklenir; hedef: uzun bir oturumda toplam token, handoff'suz senaryonun ≤ %60'ı.

## 4. Fazlar (her faz: kod → hedefli testler → tam paket → build → ekran görüntüleri → rapor → senin onayın)

| Faz | Kapsam | Ajanlar | Kabul ölçütleri |
|---|---|---|---|
| **1 — Temel ve kusurlar** | (a) `ProviderBridge` soyutlaması + `ClaudeCodeBridge` (stream-json, abonelik oturumu, `claude auth status` rozeti) + ayarlarda sağlayıcı/model seçimi; (b) canlı rapor→yetenek atfı ve **artımlı damıtma** (yeni rapor 5 sn içinde sayaçta; "Damıt" yalnızca okunmamışları işler; tazeleme ayrı; google-flow düğmesi açılır); (c) eski Agent Desk'in silinmesi, varlıkların taşınması; (d) **bağlam doluluk ölçümü + `/handoff` + %60'ta otomatik aktarım sayfası + araç sonucu maskeleme** (§3b 1-2); (e) sürüm `v0.1.8`, push | agy-integration (a,c,d-köprü), memory-rag (b, d-sayfa/wiki), qa-build (test/build) | Her iki sağlayıcıda tek kelimelik gerçek prob başarılı (senin onayınla, ~2 çağrı); 2009+ test geçer; yeni rapor artımlı damıtılır (gerçek kasada kanıt) |
| **2 — Ajanlar ve kartlar** | AGENT.md kaynağı ve iki CLI'a derleme; "Ajanlar" sekmesi (liste/ekle/düzenle/sil/görev ver); manifestte ajan farkındalığı; görev kartları (kanban) + görev sözleşmesi dosyası; ajan raporlarının query sayfası olarak kasaya inmesi; Zen ve Chat paralel | agy-integration (derleme, manifest), ui-engineer (sekme, kartlar), memory-rag (query sayfaları, log) | Ajan ekle → kart ver → rapor kasada + sayaçta; Entropy sohbette ajanı adıyla önerir; `v0.1.9` |
| **3 — Agent Desk penceresi** | `src/entropy/desk/`: ayrı pencere, ofisler, orkestratör/değerlendirici rolleri, piksel sahne, kart panosu, ortak bellek, ikinci monitör konumu. **Yönetim:** ofis oluştur/düzenle/sil, ofis orkestratörü oluştur/düzenle/sil, ofis ajanı oluştur/düzenle/sil (rol, sağlayıcı, model, yetenekler, bellek dosyası); tümü kasadaki AGENT.md/OFFICE.md dosyalarına yazar. **Faz başında araştırma:** güncel GitHub depoları (çoklu ajan ofis/“agent space” projeleri, örn. agentspace.agentspace üreticisi.com benzeri), harness örnekleri ve video anlatımları taranır; bulgular ayrı bir Faz 3 tasarım raporu olarak onaya sunulur, uygulama ondan sonra başlar | ui-engineer (pencere, sahne), agy-integration (ofis harness'ı, roller), memory-rag (ofis belleği, wikilink) | Ofis oluştur → ajan ata → görev ver → değerlendirici notu → rapor; pencere taşınabilir; `v0.2.0` |
| **4 — Wiki katmanı, lint, arayüz cilası** | `Skills/<y>/wiki` (index/log/kavram sayfaları) + `/lint`; bağlam kurucunun sayfa seçmesi; arayüz modernizasyonu (özellik kaybı yok, ekran görüntün ölçüt); performans trendi | memory-rag, ui-engineer, qa-build | Lint listesi; playbook tavanında bilgi kaybı yok; kötüleşme yok; `v0.2.1` |

Faz 1'in içinde senden istenecek tek şey: GitHub adresi ve iki sağlayıcıda birer küçük gerçek prob için "olur" (kota). Onayın gelince Faz 1'i başlatıyorum.
