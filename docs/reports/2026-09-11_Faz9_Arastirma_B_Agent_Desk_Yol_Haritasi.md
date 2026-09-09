# Faz 9 — Araştırma B: Entropy Agent Desk ve Entropy AI Karşılaştırmalı Analiz ve Yol Haritası

**Tarih:** 2026-09-11
**Depo:** `C:\EntropiAI` (v0.6.0, `pyproject.toml:6`)
**Kapsam:** Salt okunur inceleme. Hiçbir kaynak dosya değiştirilmedi, hiçbir model çağrısı yapılmadı (kota harcanmadı).
**Yöntem:** (a) ticari referans ürünün ürün sayfası ve üreticinin geliştirme videolarından çıkarılan özellik listesi, (b) 2026 benzerlerinin taraması, (c) öğrenen ajan literatürü ve kayıt defteri ekosistemi, (d) depo üzerinde dosya:satır kanıtlı durum tespiti.

**Marka notu:** Ticari referans ürün bu raporda yalnızca **"ticari referans ürün"** olarak anılır. Üretici adı ve alan adı bilinçli olarak yazılmamıştır; kaynakçada "üretici sitesi" ve "üreticinin geliştirme videoları" biçiminde geçer.

---

## 0. Yönetici Özeti

Üç cümlelik durum:

1. **Bellek ve ofis mimarisi olgun.** Desk'in kendi kasası, düğüm-bağ (A-MEM) ofis grafı, tek yönlü ofis→Entropy aktarımı ve orkestratörün Entropy'yi bilmemesi kuralı **kod düzeyinde gerçekten uygulanmış** durumda (`src/entropy/memory/office_graph.py:11-27`, `src/entropy/agents/desk_registry.py:69-72`).
2. **Yön ayrımı arayüzde sızıyor.** Ofis kartları Entropy'nin kendi görev kartlarıyla **aynı klasörde** (`Entropy/Tasks/`) duruyor ve Entropy'nin "Görevler" sekmesi bu kartları **süzmeden** gösteriyor. Kullanıcının "Desk Entropy'ye görev yolluyor, saçma" algısının teknik kaynağı budur — mesaj yönü değil, **depo ve görünüm ortaklığı**.
3. **Desk henüz "gerçek geliştirme ofisi" değil.** Ajan başına adlandırılmış terminal, git worktree/dal izolasyonu, PR/inceleme akışı ve maliyet/kota paneli yok; ticari referansın ana farklılaştırıcıları tam olarak bunlar.

En kritik tek bulgu (P0): `src/entropy/ui/modes/zen_mode.py:315` satırında `TaskBoardWidget()` **ofis parametresi olmadan** kuruluyor; `src/entropy/ui/widgets/task_board_widget.py:480-481` ise süzmeyi yalnızca `self.office` doluyken uyguluyor. Sonuç: Entropy'nin panosu tüm ofis kartlarını listeliyor.

---

## 1. Ticari Referans: ticari referans ürün

Aşağıdaki liste, ürün sayfasından ve üreticinin geliştirme videolarının başlık/açıklama içeriğinden çıkarılmıştır.

### 1.1 Ofis / ekip modeli
- Masaüstü uygulaması; makinede **sanal bir AI ofisi** kurar. Ajanlar kalıcı kimlik taşır, masalarda oturur, eşzamanlı çalışır.
- Kullanıcı kod yazmaz; işi **kanban tarzı bir görev panosundan** dağıtır ("patron gibi yönet").
- Canlı ofis görünümü ajan durumunu (çalışıyor / boşta) gösterir.
- Rol ve kalıcı belleğe sahip **adlandırılmış işçiler** (named workers).

### 1.2 Ajan başına adlandırılmış terminal (ana farklılaştırıcı)
- Her ajan için **bağımsız terminal bölmesi**; bölme sayısında sınır yok, dörtlü bölme ve sınırsız döşeme ağacı.
- Terminal **ajanın kendi adını taşır**; komut kutusu ajana adıyla hitap eder.
- Ofisteki sprite'a tıklanınca o ajanın terminali açılır.
- Bölmeler ayraç sürüklenerek canlı yeniden boyutlanır.
- Gerçek CLI çıktısı ve oturum günlükleri; canlı dosya düzenleme ve anlık diff gösterimi; ajanlar için gömülü tarayıcı.
- Kendi ifadesiyle worktree orkestratörlerinden farkı: "her bölme adlandırılmış bir işçiyle biter".

### 1.3 Bellek grafı
- "Kalıcı kimlik + bellek": ajanlar kararları ve tercihleri hatırlar.
- **Bellek grafı görselleştirmesi** (düğümler + bağlar, yakınlaştırma).
- Kullanıcının **onaylayıp yükselttiği bellek kuralları** (memory rules) — insan onayı bellek yazımının kapısında.

### 1.4 Maliyet / kota paneli
- Her bölmenin **üstünde** token kullanımı: gerçek tüketim ve API-eşdeğeri maliyet.
- Limit dolduğunda **çift hesap arasında abonelik geçişi**.
- **Yüzdelik kota çubuğu bilinçli olarak yok**: "motorlar kalan kotayı yayımlamıyor". (Bu, Entropy'nin `identity.py` kararıyla birebir örtüşüyor — bkz. §4.7.)

### 1.5 İzin modeli ve entegrasyonlar
- Kapsam tabanlı izinler (dev/prod ayrımı), **şifreli sır kasası**.
- Ön bağlı servisler: hata izleme, kod barındırma, ürün analitiği, ödeme, veritabanı, barındırma/dağıtım. Bugün 8 entegrasyon canlı, 13 yol haritasında.
- Veri ayrımı açıkça ilan edilmiş: kod, terminal çıktısı, oturum günlükleri, ajan raporları, yüklenen görseller, motor anahtarları **diskte kalır**; hesap/lisans, kadro, pano kartları (başlık/açıklama/durum/atanan), onaylanmış bellek kuralları ve analitik **hesaba senkronlanır**.
- BYOA (kendi anahtarını getir): token maliyeti kullanıcının kendi aboneliğinden; anahtarlar diskten çıkmaz.

### 1.6 Çoklu sağlayıcı
- Bugün çalışan motorlar: Claude Code, Codex, GitHub Copilot CLI, Goose, Gemini CLI, Qwen Code, OpenCode, Crush.
- Codex üzerinden dolaylı: Groq, DeepSeek, Kimi K2/K3.

### 1.7 Bildirimler, zamanlama ve mobil
- Mobil eşlikçi: **read-along** (ajan çalışırken canlı takip), sesle görev verme, ekran görüntüsü/foto ekleme, bekleyen işi onaylama/reddetme.
- Bağlantı özel ağ üzerinden (WireGuard tabanlı tünel), cihaz başına token kimlik doğrulama ve iptal.
- Mobilden **dosya silinemez, ayar değiştirilemez** — yetki daraltma tasarımı.

### 1.8 Ekip şablonları / ajan oluşturma UX'i
- Plan katmanları kadro büyüklüğüyle tanımlı (3 işçi → sınırsız işçi; 1 çalışma alanı → sınırsız).
- "Ekip koltukları" ve "token-writer kredisi" henüz yol haritasında.
- Ürün, kendi ajan kadrosuyla geliştiriliyor; 112 günde 45 ajan, 2.960 görev, 2.888 commit iddiası kamuya açık ölçüt olarak sunuluyor.

### 1.9 Piksel sahne etkileşimleri
- Piksel-sanat ofis metaforu; ajan sprite'ına tıklama → o ajanın terminali.
- Ajanlar masaya yürür, oturur, yazarken/okurken farklı animasyon oynatır.

**Desk için doğrudan çıkarım:** Ticari referansın üç ayağı var — (1) ajan başına gerçek terminal, (2) onaylanabilir bellek kuralları, (3) bölme başına maliyet göstergesi. Entropy Agent Desk'te (2) kısmen, (1) ve (3) hiç yok.

---

## 2. 2026 Benzerleri — Desk'e Taşınabilir Somut Fikirler

Her başlıkta **1-3 taşınabilir fikir** ve neden taşınabilir olduğu.

### 2.1 pixel-agents (MIT, açık kaynak)
- **Ne:** Terminaldeki AI kodlama ajanlarını animasyonlu piksel karakterlere çeviren VS Code eklentisi + bağımsız CLI. React 19 + Vite + Canvas 2D; Fastify sunucu.
- **Veri kaynağı:** İki yol — (a) `SessionStart`, `PreToolUse`, `PermissionRequest` gibi Claude Code kancaları, (b) kanca yoksa `~/.claude/projects/` altındaki oturum transkriptlerini tarayan sezgisel yedek.
- **Taşınabilir 1 — Kanca tabanlı durum akışı:** Desk sahnesi bugün `bus.office_progress` gibi uygulama içi sinyallere bağlı (`src/entropy/desk/scene.py:545`). Claude Code kancalarını da bir kaynak olarak eklemek, Desk dışında başlatılmış bir CLI oturumunu da sahnede canlandırır.
- **Taşınabilir 2 — İzin baloncuğu:** "Ajan girdi/izin bekliyor" durumunun konuşma balonuyla gösterimi. Desk'te bekleyen kart görünür ama *neyi beklediği* görünmüyor.
- **Taşınabilir 3 — Adlandırılmış alanlar (named areas):** Çalışma alanı klasörlerini ofis bölgelerine eşleme. Desk'in `projects/` kavramıyla birebir eşlenir (`src/entropy/desk/projects_panel.py`).
- **Not:** Sprite sayfası düzeni zaten pixel-agents ile aynı (`src/entropy/desk/engine/sprites.py:4-8`: 16x32 kare, satır başına 7 kare, 112x96 PNG). Yani görsel motor tarafında uyum sağlanmış durumda.

### 2.2 Claude Squad
- **Ne:** Terminal UI; birden çok kodlama ajanını **her biri kendi tmux oturumunda**, değişiklikleri **git worktree** ile izole ederek yönetir. Klavye odaklı, SSH üzerinden çalışır.
- **Taşınabilir 1 — Oturum = worktree eşlemesi:** Her alt kart için bir worktree; kart bitince worktree birleştirilir/atılır. Desk'te bu kavram `src/entropy/tools/autonomous_agent_architecture.py:138-163` içinde **tasarlanmış ama bağlanmamış** (bkz. §4.5).
- **Taşınabilir 2 — Klavye öncelikli gezinme:** Desk penceresinde ofis/kart/ajan arasında klavyeyle geçiş; ikinci monitörde açık kalan bir pencere için fare zorunluluğu maliyet.

### 2.3 Conductor / Vibe Kanban / Crystal (Nimbalyst) / Emdash / Baton
- **Ne:** Paralel kodlama-ajanı orkestratörleri ailesi. Ortak omurga: izole git worktree + kanban + diff/PR incelemesi. Vibe Kanban ticari olarak kapandı (10 Nisan 2026) ama açık kaynak olarak tamamen yerel mimariyle sürüyor; Crystal artık Nimbalyst adıyla.
- **Taşınabilir 1 — Kart → dal → PR zinciri:** Kart tamamlandığında otomatik dal + taslak PR açma. Desk'in kart yaşam döngüsü `backlog → running → review → done` (`src/entropy/agents/tasks.py:26`) zaten "review" durağı içeriyor; PR bu durağın doğal karşılığı.
- **Taşınabilir 2 — Yerel-öncelikli mimari:** Vibe Kanban'ın kapanış sonrası tamamen yerelleşmesi, Desk'in dosya tabanlı kasa kararını doğruluyor; bu kararı değiştirmemek gerek.
- **Taşınabilir 3 — Paylaşımlı kod bilgi grafı:** Bu ailedeki bazı araçlar (ör. Tempest) worktree'ler arasında paylaşılan yerel kod-bilgi grafıyla oturumlar arası token tüketimini düşürüyor. Desk'in `OfficeGraph`'ı bunu ofis düzeyinde yapıyor ama **kod tabanı düzeyinde** bir indeks yok.

### 2.4 Paperclip
- **Ne:** Kod yazmadan ajan "işe alınan", çalışmalarının UI'dan izlendiği çok-ajanlı işletim katmanı (pazarlama/outbound odaklı). CrewAI gibi kod merkezli çerçevelerden farkı: çalışma zamanı bir arayüz.
- **Taşınabilir 1 — "İşe alma" akışı:** Rol tanımından ajan üretme sihirbazı. Desk'te `AgentsWidget` düzenleme yapıyor ama şablondan üretme yok.

### 2.5 CrewAI Studio + skills.sh
- **Ne:** CrewAI kendi **skill kayıt defterini** `skills.sh` üzerinden dağıtıyor (`npx skills add <owner>/<repo>`); Flows, Crews ve dokümana duyarlı ajanlar Claude Code, Cursor, Codex için kurulabiliyor. Kurumsal katman erişim denetimi, analitik ve **iş akışı şablonları** ekliyor.
- **Taşınabilir 1 — Ekip şablonu (crew template):** "Araştırma ofisi", "Refaktör ofisi", "QA ofisi" gibi hazır kadro şablonları; ofis oluştururken tek seçimle 3-4 alt ajanı doğurur.
- **Taşınabilir 2 — Tek komutla skill kurulumu:** `skills.sh` biçimindeki `<owner>/<repo>` kısayolu, Entropy'nin bugünkü tam-URL zorunluluğundan (`src/entropy/skills/manager.py:502-517`) daha az sürtünmeli.

### 2.6 OpenAI Codex cloud / Agents SDK
- **Ne:** Yönetilen bulut kum havuzlarında **yerel paralel arka plan yürütme**; çok adımlı görevler izole sandbox'larda eşzamanlı koşar. SWE-bench Verified'da %72,1.
- **Taşınabilir 1 — Görev başına kum havuzu sözleşmesi:** Alt kartın hangi dizine yazma hakkı olduğunu kart üstünde ilan etmek. Desk'te `tools_policy` alanı var (`read-only`/`read-write`/`full`, `src/entropy/agents/harness.py:637`) ama **dizin kapsamı** yok.
- **Taşınabilir 2 — Ölçülebilir başarı kıstası:** Ofis raporlarına kabul ölçütü geçme oranı yazmak; Desk'te not (`grade`) var, toplu istatistik yok.

### 2.7 Cursor background agents
- **Ne:** Uzak bulut VM'lerine iş devri: depo klonlanır, dalda çalışılır, biten iş **PR olarak açılır**. Şubat 2026 "Cloud Agents with Computer Use" güncellemesiyle her ajana kendi VM'i, tarayıcı erişimi ve **video kaydı** verildi.
- **Taşınabilir 1 — İş kanıtı olarak kayıt:** Ajanın ne yaptığının video/ekran görüntüsü kaydı. Desk'te `StreamPanel` canlı metin akışı gösteriyor ama arşivlenmiş görsel kanıt yok.
- **Taşınabilir 2 — Dal-öncelikli çalışma:** Ajan asla ana dala yazmaz; bu kural Desk'te hiç yok.

### 2.8 Devin (Devin Desktop)
- **Ne:** 2 Haziran 2026'da Windsurf, Devin Desktop olarak yeniden konumlandı; uygulama bir **Agent Command Center** ile açılıyor. Devin Local (Rust yeniden yazımı) yaklaşık %30 daha token-verimli ve **paralel alt ajan doğurabiliyor**.
- **Taşınabilir 1 — Komuta merkezi ilk ekran:** Desk penceresi bugün ofis seçimiyle açılıyor; "tüm ofisler + tüm koşan kartlar + toplam harcama" tek ekranı yok.
- **Taşınabilir 2 — Token verimliliğini ürün ölçütü saymak:** Desk'in `estimate_subcard_tokens` (`src/entropy/agents/harness.py:99`) altyapısı var; ölçüm yüzeye çıkmıyor.

### 2.9 Google Antigravity IDE ajan yöneticisi
- **Ne:** "Kenar çubuğunda AI" modelini bırakıp iki yüzeye ayırıyor: **Editor View** ve **Agent Manager** (aynı anda birden çok ajanı koşturup denetleme). Antigravity 2.0 (19 Mayıs 2026, Google I/O) bağımsız masaüstü uygulaması, CLI, SDK, kurumsal katman ve **dinamik alt ajanlar** ekledi.
- **Taşınabilir 1 — Artifacts (kanıt makbuzları):** Plan, görev listesi, ekran görüntüsü, tarayıcı kaydı gibi **incelenebilir makbuzlar**; insan ham günlük okumadan işi doğrular. **Bu, Desk için en yüksek getirili tek fikir**: orkestratörün plan JSON'u zaten var, ama "makbuz" olarak sunulmuyor.
- **Taşınabilir 2 — Artifact üzerine yorum:** Kullanıcı makbuğa doğrudan geri bildirim bırakır, ajan **akışını durdurmadan** bunu içselleştirir. Desk'te geri bildirim ancak kartı durdurup yeniden başlatarak veriliyor.
- **Taşınabilir 3 — Tarayıcı doğrulaması:** Ajanın kendi işini tarayıcıda doğrulaması (UI testi, dashboard okuma).

### 2.10 Anthropic Dynamic Workflows / Managed Agents / Claude Code subagent-teams
- **Ne:** Claude Agent SDK, Claude Code'u çalıştıran koşum takımının kendisini kütüphane olarak veriyor (Python + TypeScript): ajan döngüsü, yerleşik araçlar, **alt ajan doğurma**, oturumlar, MCP entegrasyonu. **Claude Managed Agents** (8 Nisan 2026) ise koşum takımını, kum havuzunu ve oturum günlüğünü Anthropic'in altyapısında çalıştıran barındırılan REST API.
- **Mimari ayrım (Desk için doğrudan geçerli):** *Subagent*'lar ana ajanla **aynı oturumda** çalışır ve yalnızca sonucu rapor eder; *Agent Teams* ise **bağımsız bağlamlara** sahip, aralarında doğrudan iletişim kuran ve **paylaşımlı bir görev listesi** üzerinden koordine olan Claude örnekleridir.
- **Taşınabilir 1 — İki kipin ayrılması:** Desk bugün tek kip uyguluyor (orkestratör planlar → alt kartlar bağımsız koşar → orkestratör notlar). "Agent Teams" kipi (alt ajanlar arası doğrudan mesajlaşma) `mailbox._check_scope` sayesinde **zaten mümkün** ama hiçbir yerde kullanılmıyor (`src/entropy/agents/mailbox.py:239-270`).
- **Taşınabilir 2 — Denetlenebilirlik:** Her alt ajanın ne yaptığı, hangi sırayla ve neden — tek konsolda. Desk'in `reports/` klasörü bunu dosya olarak tutuyor; birleşik bir zaman çizelgesi görünümü yok (`src/entropy/ui/widgets/timeline_panel.py` var ama ofis kapsamı yok).
- **Taşınabilir 3 — Barındırılan koşum takımı seçeneği:** Uzun koşuları kullanıcının makinesi kapalıyken sürdürmek. Entropy'nin abonelik-kimlik doğrulamalı CLI kararıyla çelişir; **bilinçli olarak kapsam dışı bırakılmalı**.

---

## 3. "Öğrenen Entropy" için Araştırma

### 3.1 Skill keşfi ve kayıt defterleri
- **SKILL.md standardı:** Anthropic'in iç biçimi olarak başlayıp Aralık 2025'te açık standart olarak yayımlandı; aylar içinde AI kodlama ajanlarını genişletmenin baskın mekanizması oldu. **30'dan fazla platform** destekliyor: Codex CLI, Claude Code, Gemini CLI, GitHub Copilot, Cursor, VS Code, Roo Code, Goose.
- **Yapı:** YAML ön bilgisi + Markdown gövde; isteğe bağlı `scripts/`, `references/`, `assets/` alt dizinleri.
- **Bağlam maliyeti (kritik sayı):** Ajan açılışta **yalnızca ad ve açıklamayı** yükler; 100 skill'lik bir kütüphane bağlama kabaca **5.000-10.000 token** ekler. Bu, Entropy'nin skill sayısı arttıkça açılış maliyetinin doğrusal büyüyeceği anlamına gelir — keşif tasarımının ilk kısıtı budur.
- **Ölçek:** Şubat 2026 sonu itibarıyla **280.000'den fazla** skill kamuya açık; ezici çoğunluğu merkeziyetsiz üçüncü taraf.
- **Denetim ayrımı:** Anthropic küçük, elle küratörlü bir dizin ve bir iş ortağı dizini (Atlassian, Canva, Cloudflare, Figma, Notion, Ramp, Sentry, Stripe, Zapier) tutuyor — **hepsi incelenmiş**. Topluluk dizinleri **büyük, açık ve büyük ölçüde denetlenmemiş**.
- **Paket yöneticisi katmanı:** `skills.sh` gibi kayıt defterleri `npx skills add <owner>/<repo>` biçiminde tek komutla kurulum veriyor. Akademik tarafta **Skilldex**, hiyerarşik kapsam tabanlı dağıtımla bir skill paket yöneticisi/kayıt defteri öneriyor (arXiv 2604.16911).
- **Entropy için sonuç:** Keşif **iki kademeli** olmalı — küratörlü/iş ortağı dizini varsayılan güvenilir kaynak, topluluk dizini yalnızca kullanıcı onayıyla. Ve keşfedilen her skill için **ad+açıklama bütçesi** (≤ 10.000 token) bir tavan olarak izlenmeli.

### 3.2 MCP kayıt defteri ile otomatik keşif/kurulum
- **Resmî kayıt defteri:** `registry.modelcontextprotocol.io` — Anthropic, GitHub ve Microsoft destekli. **Kod barındırmaz**; yalnızca sunucunun nerede bulunacağını ve nasıl kurulacağını anlatan **üst veriyi** tutar.
- **Sağladıkları (Temmuz 2026 itibarıyla, önizleme):** standartlaştırılmış sunucu üst verisi, **ad alanı doğrulaması** (namespace verification), paket referansları, uzak uç nokta tanımları, sürüm kayıtları ve istemciler/alt kayıt defterleri için bir API.
- **Otomatik keşif:** Sunucu `/.well-known/mcp/server.json` yayımlarsa kayıt defteri onu **kendiliğinden bulur**; istemciler kayıt defterinden bulup kurar.
- **İstemci örneği:** VS Code'da `chat.mcp.gallery.enabled` açılıp Uzantılar görünümünde `@mcp` aranarak sunucu taranıp kurulabiliyor. GitHub'ın kendi MCP Registry'si de ayrı bir keşif yüzeyi.
- **Güvenlik:** 2026 tarihli değerlendirmeler keşfin yanına **doğrulama** adımını koymayı vurguluyor (ad alanı doğrulanmış mı, paket imzalı mı, uzak uç nokta beklenen alan adında mı).
- **Entropy için sonuç:** `mcp_drawer` bugün tamamen elle CRUD (`src/entropy/ui/widgets/mcp_drawer.py:377-393`). Kayıt defteri API'si **model çağırmadan** aranabilir; yani skill/MCP keşfi **kota harcamaz**. Bu, Faz 11'in en ucuz parçası.

### 3.3 Kendi skill'ini yazma döngüsü
- **Voyager (temel referans):** Üç bileşen — (1) keşfi en üst düzeye çıkaran **otomatik müfredat**, (2) karmaşık davranışları saklayıp geri çağıran, **yürütülebilir koddan oluşan sürekli büyüyen skill kütüphanesi**, (3) ortam geri bildirimini, yürütme hatalarını ve **öz-doğrulamayı** program iyileştirmeye katan yinelemeli istem mekanizması.
- **2026 uzantıları:** Skill'leri yürütme geri bildiriminden rafine etme; markdown/davranışsal skill'leri **kalıcı, kendini iyileştiren bellek** olarak ele alma; skill kütüphanelerini kapsülleme, hiyerarşik bilgi tabanı, erişim (retrieval), bağımlılık yönetimi ve **etkin küratörlükle** ölçekte yönetme.
- **Korkuluklar (2026 literatürü):** *SkillAudit* — eşleştirilmiş yörünge denetimiyle **gerçek-referanssız** skill evrimi; *Bilevel Optimization of Agent Skills via MCTS* — skill üretimini arama problemi olarak kurma; metabilişsel öğrenme çalışmaları, gerçek öz-iyileştirmenin **içsel metabiliş** gerektirdiğini savunuyor.
- **Entropy için sonuç — üç kapı:** (a) **Öz-doğrulama kapısı**: yeni skill kabul edilmeden önce kendi örnek girdisinde koşturulur; (b) **İnsan onayı kapısı**: ticari referansın "onaylanmış bellek kuralları" deseni, skill'e uygulanır; (c) **Geri alma kapısı**: her otomatik yazılan skill sürümlenir ve tek tuşla geri alınır. Entropy'de `SkillManager.create_skill` (`src/entropy/skills/manager.py:440`) hazır ama **yalnızca arayüzden** çağrılıyor (`src/entropy/ui/widgets/skills_widget.py:738`) — otonom döngü yok, dolayısıyla korkuluklar da yok.

### 3.4 Entropy'nin 3-4 ajanıyla etkileşim
- **Handoff (devir):** Bir ajanın bağlamı diğerine devretmesi. Entropy'de `src/entropy/memory/handoff.py` var (20 KB); ofis dışı Entropy ajanları için devir sözleşmesi mevcut.
- **Tartışma (debate):** Agent Teams deseni — bağımsız bağlamlar, doğrudan iletişim, paylaşımlı görev listesi. Entropy'de `AgenticChat` (`src/entropy/core/identity.py:545-660`) **Entropy ile tek bir hedef** arasında sıralı tur alışverişi yapıyor; çok taraflı tartışma yok.
- **Değerlendirici (evaluator):** Desk'te rol olarak var (`DeskOffice.evaluator`, `src/entropy/agents/desk_registry.py:126`) ve yoksa orkestratör notluyor (`src/entropy/agents/desk_registry.py:98-99`). Entropy'nin **kendi** ajanları için böyle bir değerlendirici rolü tanımlı değil.
- **Sonuç:** Entropy tarafında eksik olan, ofis tarafında zaten çözülmüş: rol ayrımı (planlayıcı/işçi/değerlendirici) ve terminal olay sözleşmesi. Faz 11'de bu desen ofisten Entropy'ye **ters yönde** ödünç alınmalı.

---

## 4. Mevcut Durum — Kanıtlı Tespit

### 4.1 Ofis kaydı, orkestratör doğuşu ve yön kuralları — **VAR**

| Kural | Durum | Kanıt |
|---|---|---|
| Desk'in kendi kökü, Entropy'den ayrı | ✅ Var | `desk_registry.py:47` → `DESK_SUBDIR = "Entropy/Desk/Offices"` |
| Tohum ofis/ajan YOK | ✅ Var | `desk_registry.py:17` "TOHUM YOK. Ofisi kullanıcı açar" |
| Ofis oluşunca orkestratör otomatik doğar | ✅ Var | `desk_registry.py:455-463` — `create()` içinde `ensure_orchestrator(spec.name)`; "ofis doğumu ile orkestratörünkü tek işlemdir" |
| Orkestratör kod yazmaz | ✅ Var (çift kilit) | İstem: `desk_registry.py:74-78` ("İşi SEN yapmazsın… Kod yazmazsın"); Denetim: `harness.py:179-186` `orchestrator_produced_code()` |
| Orkestratör kendi alt ajanlarını üretir/düzenler | ✅ Var | `harness.py:764-814` `_apply_new_agents()`; var olan adı **ezmez** |
| Orkestratör Entropy'yi bilmez | ✅ Var | `desk_registry.py:69-72` "İçinde 'Entropy' GEÇMEZ ve geçmemeli"; `build_plan_prompt` (`harness.py:743-763`) içinde Entropy geçmiyor |
| Entropy tüm orkestratörleri bilir | ✅ Var | `desk_registry.py:788-826` `desk_manifest()`; `provider.py:454-460` ile istemin içine enjekte ediliyor |
| Ofis belleği düğüm-bağlı graf | ✅ Var | `office_graph.py:160-330`; A-MEM/Zettelkasten, TF-IDF `related` bağı, LLM istemez |
| Desk "Bellek" sekmesi grafı gösterir | ✅ Var | `desk/memory_panel.py:1-20`; QPainter mini graf + MEMORY.md |
| Ofis→Entropy tek yön | ✅ Var | `office_graph.py:15-18` "Tek yön vardır: ofis → Entropy (`ingest_office_into_entropy`). Ters yön yoktur" |
| Piksel görsel pixel-agents tabanlı | ✅ Var | `desk/engine/sprites.py:4-8` — sprite sayfası düzeni birebir aynı |
| Ticari referansın üretici adı kodda geçmiyor | ✅ Doğrulandı | Depo genelinde arama sonuçsuz |

### 4.2 Kart deposu ve görünüm ayrımı — **YARIM (P0 kaynağı)**

Kullanıcının "Desk Entropy'ye görev yolluyor, saçma" tespitinin teknik kaynağı:

1. **Ofis kartları Entropy'nin kartlarıyla aynı klasörde.**
   `src/entropy/agents/tasks.py:51` → `TASKS_SUBDIR = "Entropy/Tasks"`
   Ofis kartı ile Entropy kartını ayıran tek şey, kart ön bilgisindeki `office:` alanı (`tasks.py:103`, `tasks.py:387`). Yani ayrım **dosya sisteminde değil, alan düzeyinde**.

2. **Entropy'nin Görevler paneli ofis kartlarını süzmüyor.**
   `src/entropy/ui/modes/zen_mode.py:315` → `self.task_board_widget = TaskBoardWidget()` — **`office` parametresi verilmemiş**.
   `src/entropy/ui/widgets/task_board_widget.py:480-481`:
   ```python
   if self.office:
       cards = [c for c in cards if str(spec_field(c, "office", "")) == self.office]
   ```
   `self.office` boş olduğu için **süzme hiç çalışmıyor**. Entropy'nin "Görevler" sekmesi (`zen_mode.py:313-325`, üstte kanban + altta zamanlanmış görevler) tüm Desk ofis kartlarını Entropy'nin kendi kartlarıymış gibi listeliyor.
   Karşılaştırma: Desk penceresi **doğru** yapıyor — `desk/board_panel.py:31` → `TaskBoardWidget(parent=self, board=board, office=office)`.

3. **Terminal olayları Entropy'nin gelen kutusuna varsayılan olarak akıyor.**
   `src/entropy/agents/mailbox.py:464-470` → `emit_terminal(..., to=ENTROPY_OWNER, ...)`; `tasks.py:674` ve `tasks.py:716` bunu her kart bitişinde çağırıyor. Bu **doğru yön** (rapor akışı), ama ofis kartı ile Entropy kartı ayrımı yapılmadığı için Entropy'nin kutusu ofis gürültüsüyle doluyor.

4. **Çekirdek çipleri:** `src/entropy/ui/widgets/core_visualizer.py` içinde kart/ofis kavramı **yok** (arama sonuçsuz); çekirdek yalnızca durum (`idle/thinking/executing/error`) gösteriyor. Yani "çekirdek çipleri ofis kartlarını gösteriyor" iddiası **doğrulanmadı** — sorun tek başına Görevler panelinde.

### 4.3 Entropy → orkestratör yönü — **YARIM**

| Yol | Durum | Kanıt |
|---|---|---|
| `/ask <ofis> <soru>` → ofis kutusuna `question` | ✅ Var, bağlı | `slash_commands.py:906-924` → `ask_office()`; `mailbox.py:396-409` |
| `instruct_office()` → ofis kutusuna `instruction` | ⚠️ **Tanımlı ama HİÇBİR YERDEN ÇAĞRILMIYOR** | `mailbox.py:411-424`; depo genelinde `mailbox.py` dışında çağrı yok |
| `/desk task <ofis> …` → üst kart + harness | ✅ Var | `slash_commands.py:752-895` |
| Kutu planlamadan önce okunuyor | ✅ Var | `harness.py:690-700` → `pending_instructions()` + `instructions_section()`; okunanlar `mark_read` ile işaretleniyor |
| Koşan bir karta ortada müdahale | ❌ Yok | Yalnızca `/desk stop` var (`slash_commands.py:828-843`); geri bildirim vermek için kartı öldürüp yeniden açmak gerekiyor |
| `/chat` ile ofisle sıralı diyalog | ✅ Var | `slash_commands.py:1155` → `_handle_chat`; `identity.py:545-660` `AgenticChat.send()` |

### 4.4 Orkestratör → Entropy raporu — **VAR**

| Yol | Durum | Kanıt |
|---|---|---|
| Kart zinciri bitince Entropy kutusuna rapor | ✅ Var | `harness.py:1174-1186` → `report_to_entropy()`; `mailbox.py:426-462` |
| Rapor Merkezi rozeti tek kaynaktan | ✅ Var | `mailbox.py:456-461` → `bus.report_inbox_unread.emit(...)` |
| Ofis çıktısı Entropy bilgi grafına | ✅ Var | `harness.py:1206-1222` → `ingest_office_into_entropy()` |
| Ofis raporu wiki'ye | ✅ Var | `harness.py:1225-1240`; `memory/wiki.py:299` `write_office_report_summary()` |
| Ofis/ajan belleğine yazım | ✅ Var | `harness.py:1281-1295`; `memory/agent_memory.py:234-256` |
| Rapor gelen kutusu arayüzü | ✅ Var | `ui/widgets/report_inbox.py` (504 satır), okundu/pin/arşiv kalıcı |

**Yön güvenliği açığı (P1):** `Mailbox._check_scope` (`mailbox.py:239-270`) yalnızca `self.owner_kind == "agent"` iken çalışıyor. Entropy'nin kutusu (`owner_kind == "entropy"`) **her türden mesajı, her göndericiden** kabul ediyor. Yani bir ofis ajanı teknik olarak Entropy'ye `kind="instruction"` yollayabilir. Bugün böyle bir çağrı **yok**, ama kural kodla değil **teamülle** korunuyor.

### 4.5 Ajan başına terminal, worktree, PR — **YOK**

| Özellik | Durum | Kanıt |
|---|---|---|
| Ajan başına adlandırılmış terminal | ❌ Yok | `ui/widgets/terminal_pane.py` (101 satır) **tek global** akış konsolu; `zen_mode.py:545` "Canlı AGY Çıktı Akışı", `chat_mode.py:581` "Canlı AGY Akış Konsolu" |
| Köprü akışının ajan etiketi | ❌ Yok | `desk/stream_panel.py:8-11`: "köprü akışı ajan başına etiketlemiyor (tek `token_chunk_received` var)… ajan başına ayrıştırma köprü sözleşmesi genişleyince yapılabilir" |
| Bölme/döşeme ağacı | ❌ Yok | Desk sekmeleri sabit: Kartlar / Akış / Projeler / Bellek (`desk/window.py:261-264`) |
| Sprite'a tıkla → o ajanın terminali | ⚠️ Yarım | `desk/scene.py:200` `agent_clicked` sinyali var; `StreamPanel.focus_agent()` sadece **odak penceresi** açıyor, gerçek terminal değil |
| git worktree izolasyonu | ⚠️ Ölü kod | `tools/autonomous_agent_architecture.py:138-163, 668-703` (`WorktreeDesk`, `spawn_worktree_desk`, `merge_desk_worktree`) — **yalnızca kendi `faz*` türevleri tarafından import ediliyor**, Desk'ten hiçbir çağrı yok |
| Proje = depo/dal eşlemesi | ❌ Yok | `DeskProject` alanları: `name, office, goal, charter, path` (`desk_registry.py:109-117`) — repo/branch alanı **yok** |
| PR / inceleme akışı | ❌ Yok | Depo genelinde PR açma çağrısı yok; kart yaşam döngüsündeki `review` durağı **insan okuması** anlamında (`tasks.py:26-28`) |
| Diff gösterimi | ❌ Yok | — |

### 4.6 Skill ve MCP keşfi — **YARIM**

| Özellik | Durum | Kanıt |
|---|---|---|
| Yerel skill taraması | ✅ Var | `skills/manager.py:71-133` `discover_skill_dirs()` (proje > kök > kullanıcı sırası) |
| SKILL.md ön bilgi ayrıştırma | ✅ Var | `skills/manager.py:349` `parse_skill_file()` |
| URL/GitHub'dan skill içe aktarma | ✅ Var | `skills/manager.py:502-604`; zip güvenli çıkarma `safe_extract_zip` (`:179`), ad temizleme `sanitize_skill_name` (`:155`) |
| Kayıt defterinden **arama/keşif** | ❌ Yok | Tam URL gerekiyor; `skills.sh` tarzı `<owner>/<repo>` kısayolu yok |
| Claude eklenti pazar yeri taraması | ❌ Bilinçli kapalı | `skills/manager.py:113` "Claude eklenti pazar yeri bilerek taranmıyor" |
| Entropy'nin **kendi** skill'ini yazması | ❌ Yok | `create_skill` (`:440`) yalnızca `skills_widget.py:738`'den, yani elle çağrılıyor |
| MCP sunucu CRUD | ✅ Var | `ui/widgets/mcp_drawer.py:377-420` ekle/düzenle/sil/aç-kapat |
| MCP **kayıt defteri** entegrasyonu | ❌ Yok | `registry.modelcontextprotocol.io` çağrısı depoda yok |

### 4.7 Model, kimlik, kota — **YARIM**

| Özellik | Durum | Kanıt |
|---|---|---|
| İki sağlayıcı (agy + claude) | ✅ Var | `agents/registry.py:95` `VALID_PROVIDERS = ("agy", "claude")`; `config.py:235` |
| Oturum/kimlik doğrulama okuma | ✅ Var | `core/identity.py:123` `claude auth status --json` — model çağırmaz, kota harcamaz |
| Kota yüzdesi | ❌ Yok (bilinçli) | `identity.py:167-171`: "Claude CLI kalan kotayı ya da pencere sıfırlanma anını bildirmiyor… Uydurma bir yüzde göstermek yanlış güven verirdi" — **ticari referansın kararıyla aynı** |
| Kart/ofis token bütçesi | ✅ Var | `harness.py:383-476` `_budget` / `_spend` / `_can_afford`; `DEFAULT_BUDGET_TOKENS = 120000` (`desk_registry.py:64`) |
| Gerçek maliyet (USD) | ⚠️ Yarım | `claude_bridge.py:887` `total_cost_usd` okunuyor; **arayüzde ofis/ajan kırılımı yok** |
| Harcama görünürlüğü | ⚠️ Yarım | Yalnızca `/desk` metin çıktısında (`slash_commands.py:783-789`); panel yok |
| **Claude-yalnız tam çalışma** | ⚠️ **Riskli** | Varsayılanlar her yerde `"agy"`: `config.py:135`, `desk_registry.py:128/223/243/414/424/510-512/581`, `harness.py:757/759/792/887/1387`. Orkestratör istem şeması bile `"provider": "agy"` örneğini dayatıyor (`desk_registry.py:89-91`, `harness.py:757-759`) — model, kadroda Claude ajanı olsa bile plana `agy` yazmaya eğilimli |

### 4.8 Diğer

| Özellik | Durum | Kanıt |
|---|---|---|
| Bildirim merkezi | ✅ Var | `ui/widgets/notification_center.py` — son 50 olay, tıklanınca hedefe git |
| Zamanlama (cron) | ✅ Var | `scheduler/cron_engine.py`; `ui/widgets/tasks_widget.py` |
| Tek örnek kilidi | ✅ Var | `core/single_instance.py` |
| Çökme günlüğü | ✅ Var | `core/crash_log.py` |
| Ofis CRUD arayüzü | ✅ Var | `desk/offices_panel.py` (19 KB) |
| Ajan CRUD + rol atama | ✅ Var | `desk/roster_panel.py` + `ui/widgets/agents_widget.py:914` (orkestratör/değerlendirici yap) |
| Ekip şablonu | ❌ Yok | Ofis boş kadroyla doğuyor |
| Sahne yürüme/animasyon | ✅ Var | `desk/scene.py:470-528` `walk_to_seat` / `_advance_walk`; durum `state_for_tool` (`:191`) |
| Test paketi | ✅ Var | `tests/` altında 189 test dosyası; `test_architecture_rules.py` mimari kuralları test ediyor |

---

## 5. Özellik Matrisi

Gösterim: ✅ var · ⚠️ yarım · ❌ yok · — ilgisiz

| # | Özellik | Biz (v0.6.0) | ticari referans ürün | Diğerleri (kim) |
|---|---|:--:|:--:|---|
| 1 | Ofis / ekip modeli | ✅ | ✅ | ✅ Paperclip, CrewAI Studio |
| 2 | Kanban görev panosu | ✅ | ✅ | ✅ Vibe Kanban, Conductor |
| 3 | Orkestratör rolü (kod yazmaz) | ✅ | ⚠️ (lead) | ✅ Claude subagent-teams (lead agent) |
| 4 | Orkestratör kendi alt ajanını üretir | ✅ | ⚠️ | ✅ Antigravity 2.0 dinamik alt ajanlar |
| 5 | Değerlendirici / not verme | ✅ | ❌ | ⚠️ Codex (SWE-bench dış ölçüt) |
| 6 | **Ajan başına adlandırılmış terminal** | ❌ | ✅ | ✅ Claude Squad (tmux), Conductor |
| 7 | Sınırsız bölme / döşeme ağacı | ❌ | ✅ | ⚠️ Claude Squad |
| 8 | **git worktree izolasyonu** | ⚠️ (ölü kod) | ✅ | ✅ Claude Squad, Crystal/Nimbalyst, Conductor |
| 9 | **PR / inceleme akışı** | ❌ | ✅ | ✅ Cursor bg agents, Codex cloud, Devin |
| 10 | Anlık diff gösterimi | ❌ | ✅ | ✅ Vibe Kanban, Conductor |
| 11 | Ajanlar için tarayıcı | ❌ | ✅ | ✅ Antigravity, Cursor (Computer Use) |
| 12 | **Bellek grafı (düğüm-bağ)** | ✅ | ✅ | ⚠️ Tempest (kod grafı) |
| 13 | Onaylanabilir bellek kuralları | ❌ | ✅ | — |
| 14 | Ofis/ajan wiki + RAG | ✅ | ❌ | ❌ |
| 15 | **Maliyet/kota paneli** | ⚠️ (metin) | ✅ (bölme başına) | ⚠️ Cursor (plan bazlı) |
| 16 | Yüzdelik kota çubuğu | ❌ (bilinçli) | ❌ (bilinçli) | ❌ |
| 17 | Çift hesap / abonelik geçişi | ❌ | ✅ | ❌ |
| 18 | Token bütçe tavanı (kart/ofis) | ✅ | ❌ | ❌ |
| 19 | İzin modeli (dev/prod kapsam) | ⚠️ (`tools_policy`) | ✅ | ✅ Codex sandbox |
| 20 | Şifreli sır kasası | ❌ | ✅ | ✅ Cursor, Devin |
| 21 | Bildirimler | ✅ | ✅ | ✅ |
| 22 | Zamanlama (cron) | ✅ | ❌ | ⚠️ Codex cloud |
| 23 | Çoklu sağlayıcı | ⚠️ (2: agy+claude) | ✅ (8 motor) | ✅ Conductor, Vibe Kanban |
| 24 | Ekip şablonları | ❌ | ⚠️ (yol haritası) | ✅ CrewAI Studio |
| 25 | Piksel sahne + tıkla-etkileş | ⚠️ (odak, terminal değil) | ✅ | ✅ pixel-agents (MIT) |
| 26 | Ajan oluşturma/düzenleme UX | ✅ | ✅ | ✅ Paperclip |
| 27 | Mobil eşlikçi / read-along | ❌ | ✅ | ❌ |
| 28 | Sesle görev verme | ❌ | ✅ | ❌ |
| 29 | **Artifacts (kanıt makbuzları)** | ⚠️ (rapor dosyası) | ⚠️ (rapor+log) | ✅ **Antigravity** |
| 30 | Makbuz üzerine akış kesmeden yorum | ❌ | ⚠️ (mobil onay) | ✅ Antigravity |
| 31 | Video/ekran kaydı kanıtı | ❌ | ❌ | ✅ Cursor bg agents |
| 32 | Skill kayıt defteri keşfi | ❌ | — | ✅ skills.sh, Skilldex, Anthropic dizini |
| 33 | MCP kayıt defteri keşfi | ❌ | — | ✅ registry.modelcontextprotocol.io, VS Code, GitHub MCP Registry |
| 34 | Kendi skill'ini yazma döngüsü | ❌ | — | ✅ Voyager türevleri (araştırma) |
| 35 | Ajanlar arası doğrudan mesajlaşma | ⚠️ (altyapı var, kullanılmıyor) | ❌ | ✅ Claude Agent Teams |
| 36 | Tek yönlü Desk↛Entropy yalıtımı | ⚠️ (teamül) | — | — |
| 37 | Yerel-öncelikli / dosya tabanlı | ✅ | ✅ | ✅ Vibe Kanban (2026 sonrası) |
| 38 | Barındırılan koşum takımı | ❌ (kapsam dışı) | ❌ | ✅ Claude Managed Agents, Codex cloud |

**Okuma:** 38 satırda bizim ✅ sayımız 14, ⚠️ 9, ❌ 15. En büyük yoğunlaşma **geliştirme ofisi** ekseninde (6-11, 19-20): burada 6 satırın 5'i ❌. Bellek ekseninde (12-14, 18) ise ticari referansın **önündeyiz** (wiki+RAG ve bütçe tavanı onda yok).

---

## 6. Boşluk Analizi

### P0 — Faz 9'da düzeltilmezse ürün yanlış çalışıyor sayılır

**P0-1 — Entropy'nin Görevler paneli ofis kartlarını gösteriyor.**
Kanıt: `zen_mode.py:315` (`TaskBoardWidget()` ofissiz) + `task_board_widget.py:480-481` (süzme yalnızca `self.office` doluyken).
Etki: Kullanıcı Desk'in kartlarını Entropy'nin işi sanıyor; "Desk Entropy'ye görev yolluyor" algısı doğrudan buradan.
Not: Desk penceresi doğru davranıyor (`board_panel.py:31`), yani asimetri.

**P0-2 — Ofis kartları Entropy kartlarıyla aynı klasörde.**
Kanıt: `tasks.py:51` `TASKS_SUBDIR = "Entropy/Tasks"`; ayrım yalnızca `office:` ön bilgi alanı (`tasks.py:103`).
Etki: Obsidian'da, yedeklemede ve elle düzenlemede iki dünya karışıyor. Desk'in "kendi kasası" kuralı (`desk_registry.py:47`) kartlar için **uygulanmamış**.

**P0-3 — Entropy → orkestratör "talimat" yolu bağlanmamış.**
Kanıt: `mailbox.py:411-424` `instruct_office()` tanımlı; depoda `mailbox.py` dışında **hiç çağrılmıyor**. Kullanıcının elinde yalnızca `/ask` (soru) var.
Etki: Kullanıcının bildirdiği "Entropy orkestratörlere görev/mesaj yollar" kuralı yarım; harness kutuyu okumaya hazır (`harness.py:690-700`) ama kutuya talimat düşüren bir yüzey yok.

**P0-4 — Ters yön kodla engellenmiyor.**
Kanıt: `mailbox.py:239-242` — `_check_scope` yalnızca `owner_kind == "agent"` iken çalışıyor; Entropy kutusu her mesaj türünü kabul ediyor.
Etki: Bugün ihlal yok ama kural yalnızca teamülle korunuyor; bir sonraki fazda bir alt ajan Entropy'ye `instruction` yazarsa hiçbir şey durdurmaz.

**P0-5 — Claude-yalnız çalışma garanti değil.**
Kanıt: `"agy"` varsayılanı 14+ noktada sabit (`config.py:135`, `desk_registry.py:128/223/243/414/424/510-512/581`, `harness.py:757/759/792/887/1387`); orkestratör istem şeması `"provider": "agy"` örneğini dayatıyor (`desk_registry.py:89-91`).
Etki: agy kotası bittiğinde ya da kullanıcı yalnızca Claude aboneliğiyle çalışmak istediğinde ofis planı yine `agy` ajanları üretir.

### P1 — Faz 10'un ön koşulları

**P1-1 — Ajan başına terminal yok, köprü akışı ajan etiketlemiyor.** `terminal_pane.py` tek global konsol; `stream_panel.py:8-11` sorunu kendi yorumunda kabul ediyor. Bu, ticari referansın **1 numaralı** farklılaştırıcısı.

**P1-2 — Proje ≠ depo/dal.** `DeskProject` (`desk_registry.py:109-117`) repo/branch taşımıyor; `worktree` kodu (`tools/autonomous_agent_architecture.py:138-163`) bağlanmamış ölü ada.

**P1-3 — PR/inceleme akışı yok.** Kartın `review` durağı var (`tasks.py:26`) ama karşılığı bir dal/PR değil, insan okuması.

**P1-4 — Maliyet paneli yok.** Sayı toplanıyor (`harness.py:383-476`, `claude_bridge.py:887`) ama yalnızca `/desk` metninde görünüyor (`slash_commands.py:783-789`).

**P1-5 — Orkestratör "araştırma" döngüsü yüzeysel.** `_can_web_search()` (`harness.py:629-641`) yalnızca kadroda `read-only`/`full` politikalı ajan **var mı** diye bakıyor; orkestratörün kendisine gerçek bir arama aracı verilmiyor. Sonuçta `research_notes` **modelin kendi belleğinden** yazılıyor, taze veriden değil.

**P1-6 — Koşan karta müdahale yok.** Yalnızca `stop` (`slash_commands.py:828-843`). Antigravity'nin "makbuğa yorum bırak, ajan durmadan içselleştirsin" deseni yok.

**P1-7 — Ekip şablonu yok.** Ofis boş kadroyla doğuyor; kullanıcı her ofis için alt ajanları elle ya da orkestratörün `new_agents`'ıyla kurmak zorunda.

### P2 — Faz 11+ ve sonrası

**P2-1 — Skill kayıt defteri keşfi yok.** Tam URL zorunlu (`skills/manager.py:502-517`).
**P2-2 — MCP kayıt defteri keşfi yok.** `mcp_drawer.py` tamamen elle.
**P2-3 — Entropy kendi skill'ini yazmıyor.** `create_skill` yalnızca arayüzden (`skills_widget.py:738`).
**P2-4 — Entropy'nin ajanlarıyla çok taraflı tartışma yok.** `AgenticChat` tek hedefli, sıralı (`identity.py:545-660`).
**P2-5 — Şifreli sır kasası yok.**
**P2-6 — Kanıt kaydı (görsel/video) yok.**
**P2-7 — Mobil / sesli yüzey yok.** (Kapsam kararı gerekir; ticari referansın ayrıştığı alan.)

---

## 7. Yol Haritası

Her madde: **kabul ölçütü** · **ajan** · **risk** · **kota**.
Ajan kısaltmaları: `agy` = agy-integration-engineer · `ui` = ui-engineer · `mem` = memory-rag-engineer · `qa` = qa-build-engineer.

### FAZ 9 — Kırılanları düzelt, yönü ve veriyi ayır (bu faz)

| # | İş | Kabul ölçütü | Ajan | Risk | Kota |
|---|---|---|---|---|---|
| 9.1 | **Entropy panosu ofis kartlarını süzsün** — `TaskBoardWidget`'a `exclude_offices: bool` ekle; `zen_mode.py:315` bunu `True` ile kursun | Ofis kartı olan bir kasada Zen "Görevler" sekmesi **yalnızca `office` alanı boş** kartları listeler; Desk penceresi eskisi gibi ofis kartlarını gösterir; iki panelin kart sayıları toplamı toplam kart sayısına eşit | ui | Düşük. Mevcut `office` süzgeci mantığına ek koşul; Desk yolu değişmez | **0** (model çağrısı yok) |
| 9.2 | **Kart deposunu ayır** — ofis kartları `Entropy/Desk/Offices/<ofis>/cards/`, Entropy kartları `Entropy/Tasks/`. `TaskBoard`'a kök çözümleyici; eski konumdaki ofis kartları ilk açılışta taşınır | Var olan kasada geçiş sonrası: ofis kartları yeni yolda, Entropy kartları yerinde; `/desk` ve Desk panosu aynı kartları gösteriyor; geri alma için taşıma günlüğü yazılıyor | agy | **Orta-yüksek.** Kart yolu kodun her yerinde; kısmi taşıma iki kaynaklı gerçek yaratır. Taşıma tek işlemde, doğrulamalı ve idempotent olmalı | **0** |
| 9.3 | **`/desk msg <ofis> :: <talimat>`** — `instruct_office()`'i yüzeye bağla; Desk penceresine "Ofise talimat" kutusu | Komut çalıştıktan sonra ofis `inbox/` altında `kind="instruction"` mesajı var; bir sonraki planlamada `build_plan_prompt` çıktısında `[TALİMAT]` bölümü görünüyor ve mesaj `read=true` işaretleniyor | agy + ui | Düşük. `pending_instructions` zaten çağrılıyor (`harness.py:695`) | **0** yazma; doğrulama için 1 küçük planlama koşusu (~3-5k token) |
| 9.4 | **Yön kilidi** — `Mailbox._check_scope`'u Entropy kutusu için genişlet: `owner_kind == "entropy"` iken yalnızca `report`/`status` kabul; `instruction`/`question` gelirse `MailboxScopeError` | Ofis adından Entropy kutusuna `instruction` yollamayı deneyen test **istisna alıyor**; `report_to_entropy` ve `emit_terminal` etkilenmiyor | agy | Düşük-orta. `emit_terminal` `status` gönderiyor, `report_to_entropy` `report` — ikisi de izinli. `identity.py:632`'deki `AgenticChat` yanıtı da `report`, uyumlu | **0** |
| 9.5 | **Sağlayıcı nötrleştirme** — `agy` sabitlerini `config.provider`'dan türet; orkestratör istem şemasındaki `"provider": "agy"` örneğini `"provider": "<kadrodaki ajanın sağlayıcısı>"` yap; ofis varsayılanı `config.provider` | `config.provider = "claude"` iken: yeni ofis `default_provider="claude"`, orkestratör planı `claude` sağlayıcılı alt kartlar üretiyor, uçtan uca kart zinciri **agy hiç çağrılmadan** kapanıyor | agy | **Orta.** 14+ noktada varsayılan; biri atlanırsa sessizce agy'ye düşer. `VALID_PROVIDERS` doğrulaması korunmalı | Claude ile 1 uçtan uca ofis koşusu (~15-25k token) |
| 9.6 | **Sprite tıklaması → o ajanın akışı (ara adım)** — `agent_clicked` → `StreamPanel.focus_agent()` bağlantısını doğrula ve panel başlığına ajan adını yaz | Sahnede bir ajana tıklandığında Akış sekmesi öne gelir, başlıkta ajanın adı yazar, o ajanın son kart özeti görünür | ui | Düşük | **0** |
| 9.7 | **Regresyon ve mimari testleri** — 9.1-9.5 için test; `test_architecture_rules.py`'a "Entropy panosu ofis kartı göstermez" ve "ofis Entropy'ye talimat yollayamaz" kuralları | Tam paket yeşil; yeni 5+ test; PyInstaller derlemesi `dist_check`'e alınıp smoke testten geçiyor | qa | Düşük. **Not:** çalışan exe `dist/` klasörünü kilitler; derleme öncesi süreç kapatılmalı | **0** |

**Faz 9 çıkış ölçütü:** Kullanıcı Zen'de "Görevler"e baktığında **yalnızca kendi** kartlarını görür; Desk'te ofis kartlarını görür; `/desk msg` ile bir orkestratöre talimat yollayıp bir sonraki planlamada o talimatın plana girdiğini izleyebilir; `config.provider="claude"` iken sistem uçtan uca çalışır.

### FAZ 10 — Desk'i gerçek geliştirme ofisine çevir

| # | İş | Kabul ölçütü | Ajan | Risk | Kota |
|---|---|---|---|---|---|
| 10.1 | **Köprü akışına ajan etiketi** — `token_chunk_received` sinyaline `agent`/`card_id` alanı ekle (geriye uyumlu ikinci sinyal) | İki alt kart aynı anda koşarken `StreamPanel` her ikisini **ayrı** tamponda tutuyor; karışma yok | agy | **Yüksek.** Köprü sözleşmesi değişikliği; `stream_panel.py:8-11`'in "köprü sözleşmesi genişleyince" notu tam olarak bu iş. Eski sinyal bir sürüm boyunca korunmalı | 2 paralel kart koşusu (~20-30k token) |
| 10.2 | **Ajan başına adlandırılmış terminal** — Desk'e "Terminaller" sekmesi; her koşan ajan için ayrı bölme, başlıkta ajan adı; sprite tıklaması ilgili bölmeyi öne getirir | 3 ajan paralel koşarken 3 ayrı bölme, her biri kendi adıyla, kendi çıktısıyla; bölme ayracı sürüklenerek boyutlanıyor; kapanan kartın bölmesi arşivleniyor (silinmiyor) | ui | Orta. 10.1'e bağımlı. Bölme sayısı 4+ olunca Desk penceresi (1400x880) dar kalabilir — döşeme ağacı değil, sekme+bölme melezi öner | **0** (UI); doğrulama için 10.1 koşusu yeniden kullanılır |
| 10.3 | **Proje = depo + dal** — `DeskProject`'e `repo_path`, `base_branch`, `worktree_root` alanları; `projects_panel` formuna karşılıkları | Proje oluştururken depo yolu seçilebiliyor; geçersiz yol/dal reddediliyor; mevcut projeler alanlar boş olarak geçerli kalıyor | agy | Düşük-orta. Şema genişletme; ön bilgi ayrıştırıcı geriye uyumlu olmalı (`desk_registry.py:414-424` deseni) | **0** |
| 10.4 | **Kart başına worktree** — alt kart başlarken `git worktree add <root>/<kart-id> -b desk/<kart-id>`; kart bitince worktree korunur, kart silinince temizlenir. `tools/autonomous_agent_architecture.py:668-703`'teki tasarım **yeniden yazılarak** değil, sözleşmesi örnek alınarak bağlanır | İki alt kart aynı depoda **aynı anda** çalışıp birbirinin dosyalarını görmüyor; her kartın dalı `desk/<kart-id>`; kart iptal edilince worktree ve dal temizleniyor | agy | **Yüksek.** Windows'ta worktree + dosya kilidi; ajan `cd` yapmazsa yanlış ağaçta çalışır. Kart isteminde çalışma dizini **açıkça** belirtilmeli (`tasks.py:481` `project_file_section` genişletilir) | Paralel 2 kart (~20-30k) |
| 10.5 | **PR akışı** — kart `review`'a geçince `gh pr create --draft` ile taslak PR; PR bağlantısı kart ön bilgisine ve rapora yazılır. `gh` yoksa **dal + diff özeti** yedek yolu | Kart `review`'a geçtiğinde PR bağlantısı kartta görünüyor; `gh` kurulu değilse kart yine `review`'a geçiyor ve rapora diff özeti düşüyor (kart **başarısız olmuyor**) | agy | Orta. Dış araç bağımlılığı; kimlik doğrulama kullanıcıda. Yedek yol zorunlu | **0** (PR açmak model çağrısı değil) |
| 10.6 | **Diff paneli** — Desk'e "Değişiklikler" sekmesi: seçili kartın worktree'sindeki `git diff --stat` + dosya bazlı diff | Kart seçilince değişen dosya listesi ve satır sayıları görünüyor; dosyaya tıklayınca renkli diff açılıyor | ui | Düşük-orta. Büyük diff'lerde performans — dosya başına tembel yükleme | **0** |
| 10.7 | **Maliyet/kota paneli** — Desk üst şeridinde: ofis toplamı, kart başına harcama/bütçe, sağlayıcı kimliği ve oturum penceresi. **Yüzdelik kota çubuğu YOK** (`identity.py:167-171` kararı korunur) | Şeritte ofis toplam token, koşan kart başına `harcanan/bütçe`, sağlayıcı ve hesap ipucu görünüyor; sayılar `/desk` metniyle **birebir** aynı | ui + agy | Düşük. Veri zaten toplanıyor (`harness._card_state`, `claude_bridge.last_total_cost_usd`); tek kaynak kuralı korunmalı | **0** |
| 10.8 | **Orkestratör gerçek araştırma döngüsü** — orkestratöre salt-okunur web arama aracı; `research_notes` **taze veriden** yazılsın. `_can_web_search()` kadro kontrolünden **araç varlığı** kontrolüne dönsün | Aynı kart iki kez planlandığında ikinci planın `research_notes`'u birinciden farklı ve **kaynak bağlantısı** içeriyor; notlar ofis grafına `kind="bulgu"` olarak düşüyor (`harness.py:642-680`) | agy + mem | Orta. Arama kotası ve gecikme; orkestratörün araç yasağı (`orchestrator_produced_code`) **bozulmamalı** — arama okuma, yazma değil | Planlama başına +3-8k token |
| 10.9 | **Makbuz (artifact) görünümü** — orkestratör planı, alt kart çıktıları ve değerlendirme notu tek bir "makbuz" sayfasında; kullanıcı **kartı durdurmadan** yorum bırakabilsin (yorum ofis kutusuna `instruction` olarak düşer) | Koşan bir karta makbuz üzerinden yorum bırakıldığında, bir sonraki alt kart isteminde o yorum görünüyor; kart durmuyor | ui + agy | Orta. Akış ortasında istem değişimi; yorum yalnızca **henüz başlamamış** alt kartlara uygulanmalı, koşanı kesmemeli | Doğrulama koşusu (~10k) |
| 10.10 | **Ekip şablonları** — "Araştırma", "Refaktör", "QA", "Medya" ofis şablonları; ofis oluştururken tek seçimle orkestratör + 3 alt ajan | Şablon seçilerek açılan ofisin kadrosunda 4 ajan var, roller atanmış, ilk kart **ek düzenleme olmadan** koşuyor | agy | Düşük. `_apply_new_agents` deseni yeniden kullanılır; var olan adı ezmeme kuralı korunur (`harness.py:764-814`) | Şablon başına 1 duman testi (~5k) |
| 10.11 | **QA + derleme** | Tam paket yeşil; 10.1/10.4 için paralellik testleri; `dist_check` derlemesi ve smoke test | qa | Düşük | **0** |

**Faz 10 çıkış ölçütü:** Kullanıcı bir ofise gerçek bir depo bağlar, üç alt ajanın **ayrı worktree'lerde, ayrı adlandırılmış terminallerde** paralel çalıştığını izler, biten işi diff'ten görür, taslak PR bağlantısını alır ve harcamayı tek şeritten okur.

### FAZ 11+ — Öğrenen Entropy

| # | İş | Kabul ölçütü | Ajan | Risk | Kota |
|---|---|---|---|---|---|
| 11.1 | **MCP kayıt defteri keşfi** — `mcp_drawer`'a arama sekmesi; `registry.modelcontextprotocol.io` API'sinden arama, ad alanı doğrulaması gösterimi, tek tıkla ekleme | Aramada sonuç listeleniyor; her satırda ad alanı **doğrulanmış mı** rozeti var; eklenen sunucu `mcp.json`'a yazılıyor ve bağlantı denemesi sonucu gösteriliyor | agy + ui | Düşük-orta. Kayıt defteri **önizleme** aşamasında; API değişebilir. Doğrulanmamış sunucu için açık uyarı zorunlu | **0** (kayıt defteri araması model çağrısı değil) |
| 11.2 | **Skill kayıt defteri keşfi** — `<owner>/<repo>` kısayolu ve arama; küratörlü/iş ortağı dizini varsayılan, topluluk dizini **kullanıcı onayıyla** | `<owner>/<repo>` yazarak skill kurulabiliyor; topluluk kaynağı için onay diyaloğu çıkıyor; kurulan skill `discover_skill_dirs()` sırasında görünüyor | agy | Orta. **280.000+** skill'in çoğu denetlenmemiş; `safe_extract_zip` (`skills/manager.py:179`) ve `sanitize_skill_name` (`:155`) korumaları **genişletilmeli** | **0** |
| 11.3 | **Skill bağlam bütçesi ölçer** — etkin skill'lerin ad+açıklama toplamını token olarak göster; eşik (10k) aşılınca uyar | Yetenekler sekmesinde "bağlam maliyeti: N token" görünüyor; 100 skill'lik sentetik kasada ölçüm gerçek istem uzunluğuyla ±%15 uyumlu | mem | Düşük. Literatürdeki 5-10k/100 skill referansı doğrulama kıstası | **0** |
| 11.4 | **Kendi skill'ini yazma döngüsü — üç kapılı** — (a) Entropy tekrarlayan bir işi saptayınca skill taslağı üretir, (b) taslak kendi örnek girdisinde koşturulur (öz-doğrulama), (c) kullanıcı onaylamadan **etkinleşmez**; her sürüm geri alınabilir | Aynı iş üç kez tekrarlandığında Entropy skill önerisi üretiyor; öz-doğrulama başarısızsa öneri **sunulmuyor**; onaylanan skill sürümlü, tek tuşla geri alınabiliyor | mem + agy | **Yüksek.** Öz-iyileştirmenin klasik riski: kötü skill'in kendini pekiştirmesi. Üç kapı (doğrulama + insan onayı + geri alma) **pazarlık konusu değil**. Voyager türevi literatür de öz-doğrulamayı zorunlu sayıyor | Taslak+doğrulama başına ~8-15k token |
| 11.5 | **Onaylanabilir bellek kuralları** — ticari referansın deseni: damıtılan yordamlar "kural adayı" olarak sunulur, kullanıcı onaylayınca kalıcı belleğe yükselir | Damıtma sonrası aday kurallar listesi çıkıyor; onaylanan kural `MEMORY.md`'ye ve grafa yazılıyor; reddedilen bir daha önerilmiyor | mem + ui | Düşük-orta. `distiller.py` çıktısı zaten yordam üretiyor; kapı eklemek yeterli | Damıtma zaten kota harcıyor; +0 |
| 11.6 | **Entropy'nin ajanlarıyla çok taraflı tartışma** — `AgenticChat`'i N hedefli hale getir; paylaşımlı görev listesi + değerlendirici rol (Claude Agent Teams deseni) | Üç ajan aynı soruya bağımsız yanıt üretiyor, değerlendirici notluyor, Entropy sentezi rapor olarak yazıyor; her turun maliyeti ayrı görünüyor | agy + mem | **Yüksek maliyet.** N ajan = N kat token. Tur sayısı ve bütçe tavanı **zorunlu** (`harness._budget` deseni Entropy tarafına taşınmalı) | Tartışma başına 30-60k token |
| 11.7 | **Şifreli sır kasası** — API anahtarları ve entegrasyon jetonları için yerel şifreli depo; ajanlara kapsamlı erişim | Anahtar düz metin olarak diske yazılmıyor; ajan yalnızca kendisine tanımlı kapsamdaki sırrı okuyabiliyor; kasa kilidi uygulama kapanınca kapanıyor | agy | Orta. Windows DPAPI / keyring bağımlılığı; yedekleme ve kurtarma senaryosu tasarlanmalı | **0** |
| 11.8 | **Kanıt kaydı** — ekran görüntüsü/kısa kayıt; makbuğa iliştirilir (Cursor/Antigravity deseni) | UI değişikliği yapan bir kart bittiğinde makbuzda öncesi/sonrası görüntü var | ui + qa | Düşük-orta. Disk büyümesi — saklama süresi sınırı gerekir | **0** |

**Kapsam dışı bırakılanlar (bilinçli):** barındırılan/bulut koşum takımı (abonelik-kimlik doğrulamalı yerel CLI kararıyla çelişir), mobil eşlikçi ve sesli komut (ayrı ürün yüzeyi; önce §7 Faz 10 tamamlanmalı), yüzdelik kota çubuğu (motorlar kalan kotayı yayımlamıyor — ticari referans da aynı kararı vermiş).

---

## 8. Kaynaklar

### Ticari referans
- **Üretici sitesi** — ticari referans ürün ürün sayfası ve ürün ekosistemi tanıtımı. (URL bilinçli olarak yazılmamıştır.)
- **Üreticinin geliştirme videoları** — ürünün canlı yayın/geliştirme video serisinden derlenen özellik açıklamaları (ajan başına adlandırılmış terminal, bölme ağacı, sprite tıklaması, worktree orkestratörlerinden farkı).

### Piksel ofis / görselleştirme
- pixel-agents (MIT) — https://github.com/pixel-agents-hq/pixel-agents
- agent-office (piksel-sanat sanal ofis, kalıcı bellek) — https://github.com/harishkotra/agent-office
- "How I Built AgentOffice" — https://dev.to/harishkotra/how-i-built-agentoffice-self-growing-ai-teams-in-a-pixel-art-virtual-office-4o0p

### Paralel ajan orkestratörleri
- awesome-agent-orchestrators — https://github.com/andyrewlee/awesome-agent-orchestrators
- "9 Open-Source Agent Orchestrators for AI Coding (2026)" — https://www.augmentcode.com/tools/open-source-agent-orchestrators
- "Parallel coding-agent orchestrators — Conductor and the 2026 ecosystem" — https://rustman.org/wiki/conductor-parallel-agents/
- "Best Multi-Agent Coding Tools for Claude Code and Codex Users (2026)" — https://nimbalyst.com/blog/best-multi-agent-coding-tools-2026/
- "The Best Tools to Run Multiple Claude Code Agents (2026)" — https://munderdiffl.in/blog/best-claude-code-multi-agent-tools/
- "The Code Agent Orchestra" (Addy Osmani) — https://addyosmani.com/blog/code-agent-orchestra/
- "AI Agents Need Their Own Desk, and Git Worktrees Give Them One" — https://towardsdatascience.com/ai-agents-need-their-own-desk-and-git-worktrees-give-it-one/

### Bulut / arka plan ajanları
- "Cursor Background Agents: Complete Guide (2026)" — https://www.morphllm.com/cursor-background-agents
- "8 Cloud Coding Agents That Open PRs While You Sleep" — https://ssojet.com/blog/best-cloud-coding-agents
- "Devin vs Claude Code vs Codex 2026: 8 Agents Tested" — https://techsy.io/en/blog/background-coding-agents-compared
- "AI Coding Agents Compared: Codex vs Devin vs Cursor vs Claude Code (2026)" — https://toolchase.com/blog/ai-coding-agents-2026/

### Google Antigravity
- Antigravity IDE ürün sayfası — https://antigravity.google/product/antigravity-ide/
- Antigravity Docs — https://antigravity.google/docs/ide/overview/
- "Build with Google Antigravity" — https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/
- "Google Antigravity Explained: 2026 Beginner-to-Expert Guide" — https://helply.com/blog/google-antigravity-explained

### Anthropic ajan altyapısı
- "Claude Agent SDK and Managed Agents: Where to Run Production Agents" — https://hatchworks.com/blog/claude/claude-agent-sdk-and-managed-agents/
- "Claude Agent SDK & Managed Agents: Anthropic's Q2 2026 Agent Infrastructure Play" — https://zylos.ai/research/2026-04-20-claude-agent-sdk-managed-agents-architecture/
- "Anthropic Agent SDK: What It Ships vs. What It Leaves to You" — https://www.augmentcode.com/guides/anthropic-agent-sdk-what-ships-vs-what-you-build
- "Code with Claude 2026: 5 New Agent Features" — https://www.mindstudio.ai/blog/code-with-claude-2026-new-agent-features

### Agent Skills ekosistemi
- "The Agent Skills Ecosystem in 2026" — https://agentman.ai/blog/agent-skills-ecosystem-report-2026
- "What Are Agent Skills? SKILL.md Explained" — https://parallel.ai/articles/what-are-agent-skills
- "The Codex CLI Skills Ecosystem: agentskills.io and Community Skills" — https://codex.danielvaughan.com/2026/03/27/codex-cli-skills-ecosystem/
- Skilldex (skill paket yöneticisi/kayıt defteri, arXiv) — https://arxiv.org/html/2604.16911v1
- CrewAI Skills — https://docs.crewai.com/en/skills · https://www.skills.sh/crewaiinc/skills

### MCP kayıt defteri
- Resmî MCP Registry — https://registry.modelcontextprotocol.io/
- "Introducing the MCP Registry" — https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/
- "MCP Registry in 2026: How to Discover, Verify, and Safely Connect MCP Servers" — https://digitalthoughtdisruption.com/2026/07/20/mcp-registry-discover-verify-safely-connect-servers/
- "Meet the GitHub MCP Registry" — https://github.blog/ai-and-ml/github-copilot/meet-the-github-mcp-registry-the-fastest-way-to-discover-mcp-servers/
- "Getting Started With the Official MCP Registry API" — https://nordicapis.com/getting-started-with-the-official-mcp-registry-api/

### Öz-iyileştiren ajanlar / skill kütüphanesi
- Voyager: An Open-Ended Embodied Agent with LLMs — https://arxiv.org/abs/2305.16291 · https://voyager.minedojo.org/
- "Truly Self-Improving Agents Require Intrinsic Metacognitive Learning" — https://arxiv.org/pdf/2506.05109
- SkillAudit: Ground-Truth-Free Skill Evolution via Paired Trajectory Auditing — https://arxiv.org/pdf/2606.14239
- Bilevel Optimization of Agent Skills via Monte Carlo Tree Search — https://arxiv.org/pdf/2604.15709
- "Voyager: Skill Libraries as the Foundation for Lifelong AI Agent Learning" — https://beancount.io/bean-labs/research-logs/2026/05/08/voyager-open-ended-embodied-agent-lifelong-learning

### Diğer
- Paperclip AI Agent Orchestrator — https://websearchapi.ai/blog/paperclip-ai-agent-orchestrator
- "AI Agent Workspace: Why Standalone Agents Fail in Real Workflows" — https://buda.im/blog/ai-agent-workspace

### Depo kanıtları (bu raporda atıf yapılan dosyalar)
`src/entropy/agents/tasks.py` · `src/entropy/agents/harness.py` · `src/entropy/agents/mailbox.py` · `src/entropy/agents/desk_registry.py` · `src/entropy/agents/registry.py` · `src/entropy/memory/office_graph.py` · `src/entropy/memory/wiki.py` · `src/entropy/memory/agent_memory.py` · `src/entropy/skills/manager.py` · `src/entropy/core/slash_commands.py` · `src/entropy/core/identity.py` · `src/entropy/core/config.py` · `src/entropy/core/provider.py` · `src/entropy/core/claude_bridge.py` · `src/entropy/desk/window.py` · `src/entropy/desk/board_panel.py` · `src/entropy/desk/stream_panel.py` · `src/entropy/desk/memory_panel.py` · `src/entropy/desk/projects_panel.py` · `src/entropy/desk/roster_panel.py` · `src/entropy/desk/scene.py` · `src/entropy/desk/engine/sprites.py` · `src/entropy/ui/modes/zen_mode.py` · `src/entropy/ui/widgets/task_board_widget.py` · `src/entropy/ui/widgets/terminal_pane.py` · `src/entropy/ui/widgets/mcp_drawer.py` · `src/entropy/ui/widgets/core_visualizer.py` · `src/entropy/ui/widgets/report_inbox.py` · `src/entropy/tools/autonomous_agent_architecture.py`
