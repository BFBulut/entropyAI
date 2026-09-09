# Faz 3 — Agent Desk Tasarım Raporu (onay bekliyor)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` (v0.1.9 üzerine) · Hedef sürüm `v0.2.0`

## 1. Araştırmanın söyledikleri (kaynaklar sonda)

- **AgentSpace (muratify.com/products/agentspace):** hedeflediğimiz şeyin ticari karşılığı. Piksel ofis + kanban + ajan başına adlandırılmış terminal + bellek grafiği; "lead" ajan görevi böler, ekip paralel çalışır, sonuç raporla kapanır. Kapalı kaynak, 15–49 $/ay, kendi anahtarını getir. Alınacak en güçlü fikir: **sprite'a tıkla → o ajanın oturumu/terminali açılsın**; ayırt edici olacağımız yer: açık bellek grafiği, yerel RAG, iki sağlayıcı (agy + Claude).
- **pixel-agents (MIT):** PixiJS/Phaser yok, **düz Canvas 2D**; veri kaynağı **hook/olay akışı birincil, JSONL log taraması yedek**; karakterler CC0 değil, kredili paket. Bizim `bus` sinyallerimiz doğrudan kanvasa beslenebilir.
- **agent-office (MIT):** Phaser + Colyseus + SQLite + Ollama; ajanlar boşta bile ~15 sn'de bir LLM çağırıyor — kota için sürdürülemez. Ders: **hareket tamamen istemci tarafı animasyon**, LLM yalnızca kartlar için.
- **AI Town (MIT):** spritesheet + vektör bellek ("en benzer 3 anı" enjeksiyonu). Bizde zaten var (hibrit geri çağırma).
- **Orkestrasyon:** CrewAI hierarchical (yönetici ajan böler ve gözden geçirir), OpenAI handoffs, LangGraph supervisor + checkpoint, Anthropic Dynamic Workflows (Mayıs 2026: koordinasyon konuşmanın dışında, ilerleme sürekli kaydedilir, kesintiden devam). Claude Code alt ajanları `.claude/agents/*.md` (model: sonnet/opus/tam id/inherit), agy `.agents/agents/`. Sabit şelale rol zincirleri (ChatDev/MetaGPT) tek geliştiriciye uymuyor.
- **Sprite:** Kenney CC0 en güvenli; LimeZu Modern Office ücretli + kredi zorunlu. v1'de mevcut yordamsal çizim (`desk/legacy/pixel_canvas.py`, 962 satır, bağımsız) kullanılır; CC0 paket Faz 4.
- **Bulunan kusur:** derlenmiş Claude ajanı `gemini-3.8-flash-high` modelini Claude'a taşıyor (Claude Code 404 verdi). Derlemede sağlayıcı-model eşlemesi şart.

## 2. Tasarım

### 2.1 Veri modeli (kasada, düz markdown)
```
Entropy/Offices/<ofis>/OFFICE.md      ön bilgi: name, purpose, orchestrator (ajan adı), evaluator (ajan adı, isteğe bağlı),
                                      members [ajan adları], default_provider, default_model, max_parallel (2), budget_tokens;
                                      gövde: ofis tüzüğü (ne yapar, kabul standartları)
Entropy/Offices/<ofis>/MEMORY.md      ofis belleği (agent_memory deseniyle: günlük + öğrenilenler + arşiv, LLM'siz konsolidasyon)
Entropy/Agents/<ajan>/AGENT.md        mevcut; yeni alan: office (isteğe bağlı), role: orchestrator|evaluator|worker
Entropy/Tasks/<id>.md                 mevcut; yeni alanlar: office, parent (üst kart), children [alt kartlar], grade (0–1), verdict
```
Orkestratör ve değerlendirici de birer AGENT.md'dir (ofis düzeyinde seçilir); derlemede her ikisi de agy ve Claude biçimine gider. **Model eşlemesi:** Claude derlemesinde Gemini model adı görülürse `inherit` yazılır (ya da `claude-sonnet-5`), agy derlemesinde Claude model adı görülürse `gemini-3.8-flash-high`; ön bilgide `models: {agy: ..., claude: ...}` çift alan da desteklenir.

### 2.2 Ofis harness'ı (dosya tabanlı, üç adım)
1. **Planlama (1 çağrı):** ofise düşen kart → orkestratör ajanı `--agent` ile koşar; çıktı yapılandırılmış (≤5 alt kart: başlık, hedef, kabul ölçütleri, atanan ajan, sağlayıcı/model). Entropy bunları `Tasks/` altına `parent` bağıyla yazar. Orkestratör sonuç metnini değil **dosyayı** üretir (Karpathy/Anthropic harness ilkesi: aktarım dosyayla).
2. **Yürütme (paralel, ofis başına `max_parallel`):** alt kartlar mevcut `TaskBoard.run` ile kendi ajanlarının sağlayıcısında koşar; çıktılar rapor + query sayfası + ajan belleği (Faz 2 altyapısı).
3. **Değerlendirme (1 çağrı):** değerlendirici (yoksa orkestratör) alt kart çıktılarını kabul ölçütlerine karşı notlar (`grade`, `verdict`, eksikler); eşiğin altında kalan alt kart bir kez yeniden koşar (`retry ≤ 1`); sonra üst kart `review`'a düşer, **ofis raporu** `Skills/<yetenek>/wiki/queries/` + ofis belleği güncellenir.
Kota koruması: kart başına `budget_tokens`, ofis başına eşzamanlılık, her adımda tahmin (Faz 1 tahmin altyapısı) ve terminalde canlı sayaç. Kesinti: kart durumları dosyada olduğu için uygulama yeniden açılınca kaldığı yerden sürer (Dynamic Workflows ilkesi).

### 2.3 Pencere ve sahne
- `src/entropy/desk/`: `window.py` (`AgentDeskWindow`, bağımsız üst pencere; konum/boyut/monitör hatırlanır), `scene.py` (legacy `PixelCanvas` üzerine ofis sahnesi: ajan başına masa, durumlar boşta/düşünüyor/çalışıyor/hata/bekliyor, orkestratör masası merkezde; hareket tamamen istemci tarafı), `offices_panel.py` (ofis listesi + oluştur/düzenle/sil), `roster_panel.py` (ofis ajanları: ekle/düzenle/sil, orkestratör/değerlendirici atama — Faz 2 `AgentsWidget` ofis filtresiyle yeniden kullanılır), `board_panel.py` (ofise süzülmüş kanban + üst/alt kart ağacı — Faz 2 `TaskBoardWidget`), `stream_panel.py` (seçili ajanın canlı çıktısı; sprite'a tıkla → bu panel).
- Veri kaynağı: `bus` olayları (task_triggered/completed, task_cards_updated, agent_turn_*, token_chunk) birincil; köprü sessizse ledger/kart dosyaları yedek.
- Giriş noktaları: Zen ve Chat üst çubuğunda **"Agent Desk"** düğmesi (başlığın sağında), `/desk` komutu, tepsi menüsü.
- Ofis belleği bilgi grafiğinde `office` düğümü olarak (memory-rag Faz 2'de `query` grubunu eklemişti; renk/ikonla birlikte).

### 2.4 Entropy ile bütünleşme
- Manifestte ofis listesi (ad + amaç + orkestratör), kural: "kapsamlı işleri `/desk task <ofis> <başlık> :: <hedef>` ile ofise ver".
- Ofis raporları query sayfası olarak bağlam kurucuya girer; ofis belleği aktif ofis varsa 300 token ile.
- İki sağlayıcı: ofis varsayılanı + ajan başına geçersiz kılma; kart kendi sağlayıcısında koşar.

## 3. İş bölümü ve kabul ölçütleri

| Adım | Ajan | Kabul |
|---|---|---|
| 3a Veri + harness: OFFICE.md kayıt defteri, ajan role/office alanları, model eşlemesi düzeltmesi, orkestratör planlama şeması ve ayrıştırıcı, alt kart ağacı, değerlendirme ve retry, kesintiden devam, `/desk` komutları, manifest | agy-integration | Sahte köprüyle uçtan uca: kart → 3 alt kart → koşu → not → ofis raporu; derleme testinde Gemini adı Claude'a gitmiyor |
| 3b Pencere + sahne + paneller | ui-engineer | Pencere ikinci monitörde açılıp konumu hatırlanıyor; ofis oluştur/düzenle/sil; roster CRUD; sahnede durumlar canlı; sprite tıkla → akış paneli; ekran görüntüleri |
| 3c Ofis belleği, grafik `office`/`query` düğümleri (renk/ikon), ofis raporu → wiki, bağlam kurucuya ofis belleği | memory-rag | Tmp kasada bellek/rapor/grafik testleri |
| 3d QA: tam paket, build, canlı 20 sn, ekran görüntüleri; **bir gerçek uçtan uca ofis koşusu** (kota onayınla: küçük bir kart, tahmini 30–60k token, sonuç raporda) | qa-build | 0 regresyon; gerçek koşu kanıtı |

Sıra: 3a ve 3c paralel → 3b (sözleşme sabit olduğu için aynı anda başlayabilir) → 3d. Sonunda `v0.2.0`, Faz 3 ilerleme raporu.

## 4. Kararlar (senden onay)
1. Görselleştirme v1: yordamsal çizim (mevcut `PixelCanvas`), CC0 sprite Faz 4 — kabul mü?
2. Gerçek uçtan uca ofis koşusu için kota (tek kart, ~30–60k token) — onay?
3. Değerlendirici ayrı ajan (tohum: `degerlendirici`) mı, orkestratör mü? Önerim: ayrı ajan (üretim ile değerlendirme ayrılsın; Anthropic harness ilkesi).

## Kaynaklar
AgentSpace https://muratify.com/products/agentspace · pixel-agents https://github.com/pixel-agents-hq/pixel-agents · agent-office https://github.com/harishkotra/agent-office · Bit Office https://github.com/longyangxi/bit-office · AI Town https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md · Dynamic Workflows https://claude.com/blog/introducing-dynamic-workflows-in-claude-code · Claude Code subagents https://code.claude.com/docs/en/sub-agents · Antigravity custom agents https://antigravity.google/docs/cli/subagents/ · ChatDev https://arxiv.org/html/2307.07924v5 · AutoGen GroupChat https://microsoft.github.io/autogen/dev/user-guide/core-user-guide/design-patterns/group-chat.html · Kenney CC0 https://kenney-assets.itch.io/ · LimeZu Modern Office https://limezu.itch.io/modernoffice
