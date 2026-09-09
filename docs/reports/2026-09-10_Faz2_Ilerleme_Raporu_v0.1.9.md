# Faz 2 İlerleme Raporu — v0.1.9

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Commit `be8e4f0` · Etiket `v0.1.9` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist)

## Sonuç
Faz 2'nin tüm kalemleri tamamlandı. Tam paket **1529 test geçti** (Faz 1: 1436); QA bir ürün hatası yakalayıp düzeltti, bir ikincisi kısa düzeltme turunda kapandı. Kota: 0 token (bir ajanın uçtan uca smoke'u geçici kasada kısa bir gerçek görev başlatmış olabilir; ölçülmedi).

## Yapılanlar

### 1. Entropy'nin kendi ajanları
- Kaynak: `<kasa>/Entropy/Agents/<ad>/AGENT.md` (ön bilgi: name, role, provider, model, effort, skills, tools_policy, memory; gövde: sistem istemi). PyYAML yoksa yerleşik ayrıştırıcı.
- **İki CLI'a derleme:** `.agents/agents/<ad>/agent.md` (agy) ve `.claude/agents/<ad>.md` (Claude); uygulama kökü + etkin proje + varsayılan proje köküne; içerik aynıysa dosyaya dokunulmaz, kullanıcının elle yazdığı ajanlara dokunulmaz. Açılışta ve proje değişince `bootstrap_agents` (tohum → derleme, loglu). Kanıt: derlenen `analist/arastirmaci/yazar` Claude Code'un ajan listesinde belirdi.
- Tohum ajanlar (yalnızca kasa boşken): `arastirmaci` (web/kasa tarama), `analist`, `yazar`; gemini-3.8-flash-high.
- Farkındalık: her istemin manifestine ajan listesi (≤150 token) ve "işi ajana devretme" kuralı; komutlar `/agents`, `/agent <ad>`, `/task <ajan> <başlık> :: <hedef>`, `/tasks [durum]`, `/task stop <id>`. Entropy dosya yazarak da ajan/kart oluşturabilir.

### 2. Görev kartları
- `<kasa>/Entropy/Tasks/<id>.md` sözleşmesi (Hedef / Kabul ölçütleri / Notlar / Sonuç). Durumlar: Bekliyor → Çalışıyor → İnceleme (başarısız kırmızı) → Bitti.
- Çalıştırma kartın sağlayıcısında (`--agent <ad>` ile derlenmiş ajan); bitince özet + çıktı yolları, rapor yeteneğe atfedilir, **query sayfası** ve **ajan belleği** yazılır.

### 3. Arayüz (Zen ve Chat paralel)
- **Ajanlar** sekmesi (MCP Sunucuları yanında): liste (rol, sağlayıcı/model, efor, yetenek rozetleri, son görev), Ekle/Düzenle diyaloğu (sağlayıcıya göre model, yetenek çoklu seçim, araç politikası, markdown gövde), Sil, Görev ver, Dosyayı aç. Chat'te aynı panel.
- **Görev panosu**: Zen "Görevler" sekmesinde kanban (üst) + zamanlanmış görevler (alt); detay paneli (hedef, ölçütler, çıktıları rapor okuyucuda aç, sözleşme dosyası), Çalıştır/Durdur/Bitti/Sil. Chat'te açık görev rozeti + kompakt liste.
- Zen'e Sağlayıcı seçici; iki modda bağlam doluluk rozeti (%60'ta turuncu, "/handoff önerilir"); Claude için önbellek yazımı ayrı kalem; yerel komut çıktıları okunur kart.

### 4. Hafıza / wiki v0
- Query sayfaları `Skills/<yetenek>/wiki/queries/<tarih>-<konu>.md` + `index.md` + `log.md` + bellek düğümü (maskelenmiş, ≤1500 karakter); bağlam kurucu bunları rapor havuzuna alıyor.
- Ajan belleği `Agents/<ad>/MEMORY.md`: görev günlüğü + öğrenilenler, her 10 kayıtta LLM'siz konsolidasyon, 6000 karakter tavanı; aktif ajan varsa bağlama 300 token ile giriyor.
- Sessions/Tasks/Agents/wiki dosyaları damıtma kaynağı sayılmıyor; grafik verisinde `query` grubu (renk/ikon Faz 4'te).

### 5. Claude sohbet yolu tamamlandı
Proje kilidi, yetenek çözümü, `--append-system-prompt` ile bilişsel bağlam ve manifest, ekler (Claude'un Read aracı yerel görsel/PDF okuyabildiği için dosya yolu + `--add-dir`), `--agent`, `--resume` ile çok tur. Ortak mantık iki köprünün paylaştığı mixin'de.

## QA'nın yakaladığı hatalar
- Görev panosu query sayfası ve ajan belleğini kendi kasası yerine genel kasaya yazıyordu (bir test gerçek kasaya `Agents/yazar/MEMORY.md` yazdı; kalıntı temizlendi). Düzeltildi + regresyon testi.
- Açılışta ajan derlemesi yalnızca exe'nin kendi köküne yazıyordu (`APP_ROOT`); artık üç köke, hatalar loglu. Düzeltildi + 6 test.

## Ekran görüntüleri
`scratch/ui/phase2/`: agents_tab_seeded.png, agent_edit_dialog.png, task_board_kanban.png, chat_agents_panel.png, zen_top_bar.png, zen_full.png. Kozmetik notlar: Ajanlar listesinin altında boş beyaz alan; model alanı boşken "agy / · efor high" sarkan ayraç (Faz 4 cilası).

## Açık kalanlar
- `TaskBoard.run` gerçek sağlayıcıyla uçtan uca denenmedi (kota). Sen bir kart verip görebilirsin: Ajanlar → arastirmaci → Görev ver.
- Kanban'da sürükle-bırak yok (düğmeyle durum geçişi).
- stream-json içinde görsel content block desteği doğrulanamadı; ekler Read aracı yoluyla.
- Grafikte `query` ve sentetik `skill/<ad>` düğümleri henüz renksiz.

## Faz 3 önerisi (onay bekliyor)
Önce araştırma turu (GitHub'daki çoklu ajan ofis projeleri, ticari referans ürün benzeri uygulamalar, harness örnekleri, video anlatımları) ve ayrı bir Faz 3 tasarım raporu; onayından sonra uygulama: `src/entropy/desk/` ayrı pencere, ofisler (oluştur/düzenle/sil), ofis orkestratörü ve ofis ajanları (oluştur/düzenle/sil), piksel sahne (legacy çizim kodu), kart panosu, ortak bellek, ikinci monitör konumu; sonunda `v0.2.0`.
