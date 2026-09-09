# Faz 7 İlerleme Raporu — v0.5.0

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.5.0` · Build: `dist\EntropyAI\EntropyAI.exe` (uygulama kapalıydı; doğrudan dist, smoke 0, 20 sn canlı temiz)

## Sonuç
Tam paket **1868 test geçti, 0 regresyon** (Faz 6: 1807; +61 yeni). Kalan 9 hata Faz 7 dışı, takipsiz medya test dosyalarında (eksik mp4/mp3). Kota: 0 model çağrısı.

Bu faz kendi öz-denetim raporumun uygulamasıydı: 13 kanıtlı kusur (A1–A13) ve eksik özellik listesi (B) üzerinde çalışıldı.

## Kusur düzeltmeleri
- **Ofis raporları ve wiki sorgu sayfaları Rapor Merkezi'ne girmiyordu** (`Reports` / `reports` büyük-küçük harf süzgeci) → rapor akışı yola değil **türe** bağlı (`report | query | office_report | session`); künyeler tür/ofis/yetenek/önem taşıyor, önem grafik deposundan geliyor. Gerçek kasada 860 → 865 künye (5 sorgu sayfası akışa girdi).
- **Bütçe koruması başarısız kartlarda kördü** → başarısız/iptal görevlerde de son `usage` kaydediliyor (akıştaki ara usage dahil); bütçe **çağrı öncesi** kontrol ediliyor (kalan ≤ tahmin ise kart başlatılmaz); alt kart başına adım tavanı (araç çağrısı sayacı, aşınca süreç kesilir); alt kart istemine yalnızca ilk 40 proje yolu.
- **Yetim/iptal görevler terminal olay yaymıyordu** → kanban ve ofis durumu artık "çalışıyor"da takılmıyor.
- **Orkestratör araç yasağı yaptırımsızdı** → kod bloğu/diff/dosya yazma izi olan çıktı reddedilir, bir kez uyarıyla yeniden istenir, ikincide kart "orkestratör kod üretti" ile kapanır (alt ajanlara uygulanmaz).
- **Bağlanmamış API'ler** → orkestratör planlamadan önce ofis grafı + son 3 rapor ile **bilgi tazeleme** bölümü alıyor; WebSearch yetkili ajan varsa araştırma notu adımı planlanıp ofis grafına "bulgu" olarak yazılıyor; ofisten Entropy'ye alım rüya döngüsüne ve ofis raporu yazımına bağlandı (aralık kısıtlı, kotasız); biten projeler Entropy grafına `task` düğümü + `produced` kenarıyla giriyor.
- **Claude `--append-system-prompt-file` yolu** doğrulandı (4k üstünde dosya bayrağı argv'de, satır içi bayrak yok).
- **Graf çökme koruması** için gerçek günlükteki `NoneType.strip` çökmesine (13:52, 14:13) dayanan regresyon testi.
- **Cron COM istisnası (0x8001010d)** → 23 döküm incelendi: hepsinde atan iş parçacığı ana iş parçacığı, zamanlayıcı döngüsü yalnızca `Event.wait`'te seyirci. Hipotez çürütüldü, kod değiştirilmedi; iş parçacığı güvenliği testle kilitlendi. İstisna ölümcül değil.
- **Kasa hijyeni** → 50 artık `AgentDesk/office_*` klasörü ve 3 hayalet ofis (`arastirma`, `ofis`, `yazim`; yalnız layout.json) `Entropy/_archive/2026-09-09/` altına taşındı (silinmedi). Not: bu üç klasör künyesiz olduğu için Desk ofis sayısı 0'a düştü; ofisi sen oluşturacaksın.
- **Marka adı** docs dahil her yerde 0; kalıcı test (`src`, `skills`, `docs`).

## Entropy Agent Desk
- **Oturma yerleri:** masa dört yanı ve kanepe hücreleri de yer (7 → 21 aday); yayılan atama (orkestratör merkez masası, sonra en uzak boş yer); 10 ajanda hiçbir iki karakter komşu değil.
- **Yarım ekran profili:** tek monitörde sağ yarı (%50 × %90), ikinci monitörde %88; kayıtlı geometri korunur; panel minimumları 1930 → 904 px; Zen + Desk 1920×1040'ta yan yana kesişmeden.
- **Bellek sekmesi:** ofis grafı mini graf (tür renkli, düğüme tıkla → not; sanal ajan/rapor düğümleri küçük ofiste boş bırakmıyor), MEMORY.md altta.
- **Projeler sekmesi:** liste, ekle, durum, kartları süz.
- **Kart başına sağlayıcı/model/efor/bütçe** (görev diyaloğu + kart detayı), ofis başlığında harcama rozeti (veri yoksa gizli) ve iki sağlayıcı kimlik rozeti.
- **Kadro:** orkestratörün oluşturduğu ajanlar rozetli ve düzenlenebilir; "Yeni Ajan" ofisin kendi `agents/` klasörüne yazar (`create_member`); ofis üyeleri yalnızca ofiste tanımlı ajanlardır.
- Zen sol rapor paneli örtük minimumu 1420 → 389 px (kırpılma bitti).

## Mimari kural denetimi (kalıcı test)
Orkestratör istemlerinde "Entropy" yok · araçlar salt okunur · `Entropy/Agents` ile `Desk/Offices/*/agents` kesişmiyor · marka adı 0.

## Ölçüm
Perf düzeneği: bağlam kurma −5,5 %, graf kurma −8,4 %, yönlendirme −8,4 %, playbook durumu +13 % (eşik altı). Graf 1114 düğüm / 3810 bağ sabit.

## Ekran görüntüleri
`scratch/ui/phase7/`: scene_10_agents, memory_graph, projects_tab, assign_dialog, desk_zen_side_by_side_1920x1040, zen_report_panel_460/390. (Offscreen ortamda yazı tipi yok; kanıt geometri.)

## Açık kalanlar
- Gerçek sağlayıcıyla doğrulanmayanlar: alt kart token tahmini (30k, kalibre edilmeli), agy `step_update` olaylarında usage alanı, harcama rozeti dolu ofiste, ikinci monitör yolu.
- Tam paket ~%95'te (`test_ui_report_center_and_lifestyle`) bir koşumda süreç düzeyinde öldü; dosya tek başına 44/44, kalan 86 test ayrı koşumda geçti; kök neden bulunamadı (birikimli Qt/WebEngine kaynak tükenmesi şüphesi).
- Depo kökü ve `tests/` altında ajan koşumlarından kalma takipsiz artıklar (`canivopets_*`, `talking_bugs`, `module_task_*`, `autonomous_agent_architecture_faz*`, `cognitive_memory.db`); üçü paketi kırıyor. Silme kararı sende.
- Ofis düzeyinde "sınırsız bütçe" ifade edilemiyor (0 → varsayılan 120k).
- Gerçek ofis koşusu (kota kararın) yapılmadı.
