# Entropy AI Faz 8 — Bilişsel Hafıza Grafiği Tasarım Notu (Eylül 2026)

Kapsam: `src/entropy/ui/widgets/knowledge_graph.py` (Canvas 2D kuvvet yerleşimi, 3186 satır), `src/entropy/memory/obsidian/vault_manager.py` (`build_knowledge_graph`, `build_graph_with_communities`), `src/entropy/memory/graph_store.py` (çift zamanlı düğüm/kenar/topluluk, önem, PPR). Salt okunur araştırma; kod değişmedi, model API çağrısı yapılmadı. Sürüm: v0.5.1, dal `ai/v0.1.7`.

Ölçüm yöntemi: offscreen Qt (`QT_QPA_PLATFORM=offscreen`) ile gerçek kasadan (`C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault`) `build_unified_graph()` çıktısı çözümlendi; aynı çıktı `GRAPH_HTML_TEMPLATE` ile HTML'e basılıp Chromium'da 1100×760 kanvasta çalıştırıldı ve `tickPhysics()` / `render()` süreleri `performance.now()` ile ölçüldü. Ölçüm betikleri geçici dizinde kaldı, depoya girmedi.

---

## 1. Mevcut durum: ölçümler ve görsel sorunlar

### 1.1 Veri ölçümleri (gerçek kasa, 2026-09-10)

| Ölçüt | Değer | Not |
|---|---|---|
| Düğüm / kenar | **1145 / 3825** | JSON 570 KB + 701 KB = 1,27 MB; `setHtml` ile her yenilemede yeniden ayrıştırılıyor (`refresh_graph`, satır 3126) |
| Yapısal düğüm (açılış iskeleti) | **58** | `STRUCTURAL_GROUPS` (satır 951): ego 1, hub 5, project 6, skill 22, subbranch 12, mcp 6, agent 6 |
| Yaprak | 1087 | Reports 837, semantic 84, obsidian 79, mcp-tool 71, DailyNotes 7, query 6, episodic 2, procedural 1 |
| Kenar türleri | tree 1144, wikilink 983, similarity 537, catalog (gizli) 1161 | Catalog kenarları hiç çizilmiyor ama JSON'da taşınıyor (%30 yük) |
| Sarkan kenar (ucu düğüm olmayan) | **376** (324'ü catalog değil) | Hedefler: `wikilinks` 63, `Wikilink` 56, `Wikilinks` 31, `wikilink` 31, `Hedef` 12, `Note` 6… — rapor gövdesindeki `[[wikilink]]` örnek metinleri gerçek bağ sanılıyor |
| Öz-döngü / yinelenen çift | 23 / 110 | Öz-döngüler rapor sayfasının kendi adına `[[…]]` vermesinden |
| Derece (catalog hariç) | ort 4,09, **medyan 1**, maks 203 | 679 düğüm (%59) yalnızca tek ağaç kenarıyla asılı: saf yıldız-yaprak |
| Bağlı bileşen | 1 | İzole düğüm yok (her yaprak bir ebeveyne zorla bağlanıyor) |
| Ağaç derinliği | 0:1, 1:7, 2:53, **3:1001**, 4:83 | Hiyerarşi düz: düğümlerin %87'si üçüncü seviyede |
| En büyük yıldızlar (çocuk sayısı) | ALM/Basel/Risk **202**, EntropiAI projesi **188**, Agent Desks & Harness **185**, test_bridge_background_task_fa0 86, Araştırma & Özetler 78, Faz 91-104 68 | Üç ebeveyn toplam 575 yaprak (%50) |
| Test artığı projeler | `test_bridge_background_task_fa0/le0`, `test_project_directory_binding0` | Kasa `Projects/` altında kalmış pytest çıktıları; **195 yaprak** taşıyor, grafikte gerçek proje gibi görünüyor |
| Rapor etiketi uzunluğu | ort **52,5**, medyan 46, maks 180 karakter | 837 rapordan 834'ü 24 karakterde kırpılıyor (satır 2050); kırpılınca yalnızca **145 farklı** etiket kalıyor: `Gorev_Otonom Ajan Mima..` ×182, `Gorev_Automated Securi..` ×102, `Gorev_Failing Autonomo..` ×102 |
| Aynı adlı düğüm grupları | 16 | `# Pazar araştırması\n\nOfis:...` ×46 (cognitive_nodes içeriğinin ilk 26 karakteri, satır 2806), `Core Architecture Guidelines` ×24, `Pixel Agents Rendering Rules` ×24; **66 düğüm adında satır sonu** var |
| Topluluk (etiket yayılımı, `assign_communities`) | **88**; boyutlar 156, 119, 91, 90, 87, 61… | 47 topluluk ≤3 üyeli (gürültü); tonlar altın açıyla 88 renge dağılıyor → ayırt edilemez |
| Benzerlik kenarı ağırlığı | ort 0,77, medyan 0,72, min 0,34 | Yalnızca başlık TF-IDF'i (`build_similarity_links`), içerik yok |
| `importance` / `t_valid_from` / `type` alanı olan düğüm | **0 / 0 / 0** | Zaman kaydırıcısı, önem eşiği, tür filtresi, "yalnızca geçerli", "toplulukları kapat" **hepsi pasif** (`initGraphControls`: `hasTimeData=false`, `hasImportanceData=false`, `hasCommunityData=false`) |
| GraphStore (aynı makinede) | 1092 düğüm, 1555 kenar (similar_to 953, member_of 582, derived_from 20), **89 topluluk** | `graph_view_data()` ve `build_graph_with_communities()` UI'dan **hiç çağrılmıyor** (grep: yalnızca tanımlar). Faz 5.6 kontrol şeridi bu yüzden boş çalışıyor |
| `build_unified_graph` süresi | 0,30 s (kasa önbellekli) | Yenileme darboğazı `setHtml` + 1,27 MB JSON ayrıştırma, Python değil |

### 1.2 Yerleşim ve çizim ölçümleri (Chromium, 1100×760)

| Durum | zoom | görünür düğüm | benzetim kenarı | fizik/kare (medyan / maks) | çizim/kare (medyan / maks) | çizilen etiket |
|---|---|---|---|---|---|---|
| Açılış iskeleti (sığdırılmış) | 0,385 | 58 | 53 | 0,10 / 0,30 ms | 0,40 / 0,90 ms | 21 / 58 |
| Detay eşiği geçildi (`DETAIL_ZOOM`=0,9) | 0,95 | 1145 | 2317 | **5,4 / 7,0 ms** | 1,6 / 18,9 ms | 45 |
| Yakın (1,5×) | 1,5 | 1145 | 2317 | 5,4 / 6,7 ms | **6,4 / 31,2 ms** | 1087 |
| Tek dal açık (ALM, 202 yaprak) | 0,137 | 260 | — | — | — | **11** |

Yerleşim geometrisi (1145 düğüm, 250 tık sonra):

- Dünya yayılımı **8864 × 8613 birim**; bunu sığdıran zoom 0,077 olurdu. `DETAIL_ZOOM`=0,9'da görünüm alanına **1145 düğümden 4'ü** giriyor. Yani "yakınlaşınca yapraklar açılır" kuralı, yapraklar açıldığında kullanıcının bütünü görmesini fiziksel olarak imkânsız kılıyor; ekran görüntüsünde yalnızca uzun mavi çizgiler ve 2-3 düğüm kalıyor.
- Ağaç kenarı uzunluğu medyan **557**, p90 **1647** birim; hedef uzunluk `LINK_KINDS.tree.distance`=120 + yarıçaplar ≈ 150. Yaylar hedefin 4-10 katına esniyor çünkü itme `CHARGE=-230 × val/12` (rapor için −307) 1145 düğümde yayı eziyor; d3'ün varsayılanı −30'dur (kaynak [1]).
- 382 ağaç kenarlık örneklemde **180 kesişme**.
- ALM dalı açıldığında 202 yaprak ebeveynden medyan **598** birim uzağa savruluyor (min 176, maks 1548); yapraklar birbirine değmiyor (32 birimden yakın çift: 0) ama etiketlerin hiçbiri çizilmiyor (11 etiket, hepsi yapısal). Görsel sonuç: ebeveynin çevresinde 200 kırmızı noktalı "yıldız bulutu", ne bir başlık ne bir alt yapı.

### 1.3 Görsel sorunlar (ekran görüntüsü + kod kanıtı)

1. **Efsane kanvasın üst şeridini kaplıyor.** 15 kategori, iki satır, 1100 px genişlikte **1080×60 px**; altına 40 px kontrol şeridi. Şerit efsanenin altına JS ile yerleştirilse de (`initGraphControls`, satır 863) sığdırma hesabı (`fitToView`, satır 1769) bu örtüleri düşmüyor, düğümler efsanenin altına giriyor. Efsanede 4 kategori (Kavramlar, Varlıklar, Topluluklar, Ofis Kümesi) bu kasada 0 düğüm taşıyor ama yine de gösteriliyor.
2. **Kırpılmış etiketler anlamsız.** 24 karakter kırpma + `Gorev_<yetenek>_<tarih>` adlandırma kalıbı → 182 rapor aynı `Gorev_Otonom Ajan Mima..` etiketiyle. Etiket öncelik sırası yok: `placedLabels` "önce gelen kazanır" (satır 2079), sıra `nodes` dizisinin ekleme sırası (ego → hub → … → raporlar), derece/önemden bağımsız.
3. **Alt dal etiketleri açılışta gizli.** `labelZoomFloor=[0,0,0.7,1.35]` (satır 2042); açılış sığdırması 0,385 < 0,7 olduğundan 12 alt dal ve 6 ajan adı açılışta görünmüyor; kullanıcı 12 pembe noktanın ne olduğunu ancak üstüne gelince öğreniyor.
4. **Detay geçişi "ya hep ya hiç".** Tek eşik (`DETAIL_ZOOM`) 58 → 1145 düğüm sıçraması yapıyor; benzetim yeniden ısınıyor (`syncDetailState` → alpha 0,5), dünya 8,8k birime şişiyor, görünüm kayboluyor.
5. **Yıldız patlaması.** 202/188/185 çocuklu ebeveynler `compute_radial_fan_leaf_pos` ile halka halka tohumlanıyor (satır 365) ama kuvvet benzetimi tohumu eziyor; yapraklar tek yay + güçlü itme ile ebeveynden eşit uzaklıkta dairesel bulut oluşturuyor. Sınıflandırma (`classify_report_to_hub`, `classify_financial_subbranch`) anahtar sözcük tabanlı; eşleşmeyen her finans raporu ALM'ye, her proje raporu `EntropiAI`ya düşüyor (varsayılan dal = çöp kutusu).
6. **Topluluk rengi bilgi taşımıyor.** 88 topluluk × altın açı tonu; hale saydamlığı 0,20. Aynı hue'ya yakın 10+ topluluk var, kullanıcı ayıramıyor. GraphStore'daki 89 etiketli topluluk (`label`, `summary`, `member_count`) UI'a gelmiyor.
7. **Wikilink kenarlarının üçte biri sahte.** 324 sarkan, 23 öz-döngü, 110 yinelenen. `extract_wikilinks` rapor gövdesindeki kod blokları/örnekleri ayıklamıyor; `MEMORY`/`BELLEK_HARITASI` 131-133 dereceli katalog düğümleri "hidden" ama düğüm olarak duruyor.
8. **Kontrol şeridi ölü.** Zaman/önem/tür/geçerlilik/topluluk kontrolleri gerçek veride pasif (bkz. 1.1). Kullanıcı 5 kontrol görüyor, hiçbiri çalışmıyor.
9. **Etkileşim eksikleri.** Hover komşuluk vurgusu yalnızca kenar boyuyor, komşu olmayanları soluklaştırmıyor; hit-test doğrusal tarama (`handleMouseMove`, satır 1687: `for i in nodes` her mousemove'da 1145 döngü); arama yok; mini harita yok; breadcrumb yok; "yol göster" yok; tıkla-odaklan görünümü seçili düğüme kaydırmıyor (`setSelectedNode` → `fitToView` bütüne sığdırıyor).
10. **Performans tavanı.** 1145 düğümde fizik 5,4 ms + çizim 6,4 ms ≈ 12 ms/kare → teorik 80 fps, ama çizim maksimumu 31 ms (etiket ölçümü + 1087 pil çizimi) ve QWebEngine'in yazılım kompozisyonu ile 50 fps'nin altına inme riski yüksek. 3000 düğüm hedefinde `applyCharge` özyinelemeli JS + `resolveCollisions` `Map<string>` anahtarlı ızgara (`gx + ',' + gy` dize üretimi, satır 1477) ölçeklenmez.

---

## 2. Araştırma bulguları (kaynaklı)

### 2.1 Kuvvet yerleşiminde ölçek
- **d3-force varsayılanları** [1]: `forceManyBody.strength=-30`, `theta=0.9`, `distanceMin=1`, `distanceMax=∞`; `forceLink.distance=30`, `strength = 1/min(count(source),count(target))` ("ağır bağlı düğümlerin yaylarını otomatik zayıflatır, kararlılığı artırır"); `forceCollide.iterations=1` ("iterasyon arttıkça sertlik artar, kısmi örtüşme kalkar"); `alphaDecay≈0.0228` (300 iterasyon), `velocityDecay=0.4`. Entropy'de `CHARGE=-230` (7,7×), `VELOCITY_DECAY=0.42`, `alphaDecay=0.020` (≈240 iterasyon): itme aşırı, yay zayıf → şişme.
- **forceRadial** [1]: "belirtilen yarıçaptaki çembere doğru konum kuvveti; strength 0.1 = her uygulamada çembere olan uzaklığın onda biri". Düğümün hiyerarşi seviyesine göre farklı yarıçap vermek "hiyerarşi halkası" yerleşiminin standart yoludur; d3-force-3d README aynı API'yi 1D/2D/3D için sunar [2].
- **ForceAtlas2** (Jacomy ve ark., PLOS ONE 2014) [3]: itme dereceye bağlı `Fr = kr·(deg(n1)+1)(deg(n2)+1)/d`; **LinLog** modu `Fa = -ln(1+d)` "Newman modülerliğine karşılık gelen yerleşim, kümeleri sıkılaştırır"; **Dissuade Hubs** `Fa = -d/(deg(n2)+1)` "yüksek dereceli düğümleri çevreye iter, otoriteleri merkezde tutar"; **Prevent Overlap** düğüm boyutunu mesafeye ekler; "swinging" ölçen uyarlanabilir hız. 202 çocuklu yıldızlar için Dissuade Hubs + LinLog doğrudan uygulanabilir reçetedir.
- **Obsidian graph view** [4][5]: kuvvet ayarları "Center force / Repel force / Link force / Link distance"; varsayılanlar (topluluk ölçümü) centerStrength 0,48, repelStrength 16,41, linkStrength 0,44, linkDistance 198. Filtreler: arama, etiket, ek, "Existing files only", "Orphans"; Gruplar: sorguya göre renk; Görüntü: "Text fade threshold", "Node size", "Link thickness"; Yerel graf: derinlik kaydırıcısı. Topluluk deneyimi [6]: 200 nottan sonra "hairball", 500 nottan sonra performans sorunu; öneri önce filtre, sonra grup rengi.

### 2.2 Hiyerarşik / kümelenmiş yerleşim
- **Modülerlik kümelemesi = kuvvet yerleşimi** (Noack 2009) [7]: LinLog enerji modeli modülerlik optimizasyonuna denktir; kuvvet yerleşiminde kümeler istenen çıktıysa doğrusal-logaritmik çekim kullanılmalı.
- **Topluluk keşfi + kuvvet yerleşimi** (Louvain + "community gravity", Springer 2021; TVCG Kasım 2024 "Improved Visual Saliency of Graph Clusters with Orderable Node-Link Layouts") [8][9]: önce topluluk bul, her topluluğa kendi ağırlık merkezi/çekimi ver, toplulukları ayrı yerleştir ("cluster-first"); kümelerin görsel belirginliği artar.
- **fCoSE** (Cytoscape.js, Bilkent i-Vis) [10]: bileşik düğüm (compound) desteği + kısıt (sabit konum, hizalama, göreli yerleşim); spektral başlangıç + kuvvet ince ayarı, CoSE'nin 2 katı hız. Kısıtlı yerleşim fikri (hub'ları sabitle, yaprakları serbest bırak) Entropy'nin `FIXED_IDS` mantığının olgun hâli.
- **vis-network kümeleme** [11]: "outside-in" (tek bağlantılı düğümler ebeveyne katlanır) ve "inside-out" (en yüksek dereceli %3 hub belirlenir) kümeleme; büyük veri yüklenirken önce kümelenmiş gösterilir. Entropy'de %59 derece-1 düğüm = outside-in katlamanın ideal adayı.
- **Bubble Sets / hull** [12][13]: kümeyi çevreleyen izokontur; çalışmalar renk + hull'un yalnız renkten daha okunur olduğunu, konkav/alfa şeklinin konveks gövdeden gereksiz alanı kestiğini gösteriyor; 64 öğeye kadar Bubble Sets ile KelpFusion arasında anlamlı fark yok → basit alfa-şekil yeterli.

### 2.3 Kenar demetleme ve saydamlık
- **FDEB** (Holten & van Wijk 2009) [14]: kenarlar birbirini çeken yaylar; hiyerarşi ve kontrol ağı gerekmez; "belirgin dağınıklık azalması, yüksek seviyeli kenar desenleri görünür, eğrilik değişimi en aza iner". Maliyet O(E²) — 3000+ kenarda çevrimdışı/Python'da hesaplanıp kontrol noktaları JSON ile taşınmalı, tarayıcıda değil.
- ZMLT/GraphMaps çalışması [15] uyarır: "çoğu insan süper-düğüm ve kenar demetleme gibi hiyerarşik küme gösterimlerini okuyamaz"; harita benzeri çok seviyeli gösterim görev başarımı, hatırlama ve ilgi açısından üstün. Demetleme yalnızca uzak bakışta ve ağaç gövdesinde uygulanmalı, yaprak kenarlarında değil.

### 2.4 Ayrıntı düzeyi (LOD) ve anlamsal yakınlaştırma
- **ZMLT** (arXiv 1906.05996) [15]: yedi özellik — her seviyede gerçek düğüm/yol, bir seviyede görünen şey daha derin seviyelerde de görünür (tutarlılık), etiket çakışması yok, kenar kesişmesi yok, çizim alanı etiket alanıyla orantılı. Entropy'nin tek eşiği bunun yerine 3-4 seviyeli (iskelet → topluluk → dal → yaprak) kademeyi gerektirir.
- **Ontoloji grafiklerinde semantik zoom** (K-CAP 2017) [16]: bilgiyi üç katmana ayır, her katman için ayrı çizim hesapla; "önem seviyesi + zoom ölçeği" ile ayrıntı seç; kenar toplulaştırma + etiket gizleme.
- **Sigma.js** [17][18]: WebGL düğüm/kenar, Canvas etiket; etiket seçimi **dörtlü ağaç + etiket ızgarası** ile: `labelDensity=1`, `labelGridCellSize=100`, `labelRenderedSizeThreshold=6` (ekranda 6 px'ten küçük düğüme etiket yok); `hideEdgesOnMove`/`hideLabelsOnMove` ile kaydırma sırasında kenar/etiket gizleme. Her ızgara hücresinde en büyük düğümün etiketi kazanır → "hub-first" etiketleme doğrudan bu kural.

### 2.5 Etiket yerleştirme
- **Occupancy bitmap** (Chen ve ark., IEEE VIS 2021 "Fast and Flexible Overlap Detection for Chart Labeling") [19]: öncelik sıralı açgözlü yerleştirme, aday konumlar (sağ/sol/üst/alt), doluluk bit haritası ile O(1) çakışma testi; dörtlü ağaç/kaba kuvvetten belirgin hızlı. Observable örnekleri [20][21] aynı deseni Canvas'ta gösteriyor.
- Entropy'nin mevcut yaklaşımı kaba kuvvet (`placedLabels` doğrusal tarama, O(L²)) ve tek aday konum (sağ); öncelik yok.

### 2.6 Renk ve kodlama
- Kategorik palet: insan gözü 6-8 rengi güvenilir ayırır; Okabe-Ito 8 renk CVD-güvenli, Paul Tol 12'ye kadar; daha fazlası için şekil/ikon/doku kodlaması [22][23]. Entropy 15 kategori + 88 topluluk tonu + hover rengi kullanıyor.
- Önem→boyut, zaman→doygunluk/solukluk; Obsidian "Animate" (kronolojik oynatma) ve "Text fade threshold" [4].

### 2.7 Etkileşim
- Sigma.js hover deseni [17][24]: `enterNode` → komşu kümesi; `nodeReducer` ile komşu olmayanları `#333`'e boya ve etiketini kaldır; `leaveNode` → eski hâl. Gephi Sigma export "Hover behavior > dim".
- Bilgi grafı gezgini desenleri [25][26]: Focus+Context (odak ayrıntı, bağlam korunur), mini harita "her zaman görünür çağrı kutusu", konum tabanlı breadcrumb (gezinti geçmişi değil hiyerarşi), "n adım komşuluk" ve yüklem filtreleri; InfraNodus/Kumu gibi araçlarda topluluk etiketleri (öne çıkan terimler) kümenin üstünde yazı olarak.
- Semantic zoom + minimap (arXiv 2510.00003) [27]: mini harita + seviyeli ayrıntı birlikte kullanılınca yön kaybı azalıyor.

### 2.8 Canvas 2D performansı
- **OffscreenCanvas + Worker** [28][29]: çizimi ana iş parçacığından ayırır; Qt WebEngine (Chromium) destekler. Fizik zaten ayrı iş parçacığına (Worker) alınabilir: 5,4 ms/kare ana iş parçacığından çıkar.
- **Metin önbelleği** [30][31]: `fillText` pahalı; her etiketi bir kez offscreen'e çizip `drawImage` ile bas (10 ms → 1 ms ölçülmüş), ya da xterm.js tarzı glif atlası. `measureText` sonuçlarını önbellekle (Entropy bunu `_textWidth` ile kısmen yapıyor).
- **Kirli dikdörtgen / katmanlı kanvas** [32]: statik kenarlar bir kanvasta, hareketli/hover katmanı üstte; yalnızca değişen bölge yeniden çizilir. Benzetim durduğunda (alpha < alphaMin) kenar katmanı tamamen sabitlenir.
- **Dörtlü ağaç hit-test** [20]: mousemove'da doğrusal tarama yerine fizik için zaten kurulan dörtlü ağaç kullanılır (`d3.quadtree.find` benzeri).

---

## 3. Tasarım: Entropy grafı için somut plan

Amaç: 1100 düğümde ilk bakışta **okunur bir harita** (Obsidian "hairball" değil), üç tık içinde herhangi bir rapora ulaşma, 3000 düğümde akıcılık.

### 3.1 Veri modeli (Python tarafı, `build_unified_graph` çıktısına eklenen alanlar)

| Alan | Kaynak | Kullanım |
|---|---|---|
| `level` (0 ego, 1 hub, 2 dal/proje/yetenek/ofis, 3 topluluk/alt dal, 4 yaprak) | ağaç derinliği + grup | halka yarıçapı, LOD, etiket önceliği |
| `importance` 0..1 | GraphStore `importance` (varsa) ya da `_importance_by_provenance` + derece | boyut, etiket önceliği, önem kaydırıcısı |
| `t_valid_from`, `t_valid_to`, `type` | GraphStore / dosya mtime + frontmatter | zaman kaydırıcısı, geçerlilik, tür filtresi (şu an 0 düğümde var) |
| `community`, `community_label`, `community_size` | Louvain/Leiden (çözünürlük ayarlı) ya da GraphStore `communities` tablosu; ≤3 üyeli topluluklar ebeveyn topluluğa katlanır | hale, hull, topluluk özet düğümü, efsane |
| `short_label` (≤ 28 kr, tekilleştirilmiş) + `label` (tam) | `Gorev_<yetenek>_<tarih>_<konu>` kalıbından konu + tarih; aynı `short_label` çakışırsa sonek | etiket |
| `degree`, `child_count` | kenar sayımı | hub önemi, Dissuade Hubs, katlama |
| kenar `weight` (0..1), `kind` (tree/wikilink/similarity/member_of/derived_from) | mevcut bayraklar + GraphStore türleri | yay sertliği, kalınlık, saydamlık |
| kenar `bundle` (isteğe bağlı: FDEB kontrol noktaları, yalnız level ≤ 2 gövde kenarları) | Python'da çevrimdışı | uzak bakışta demet çizimi |

Veri temizliği (aynı iş paketinde): sarkan wikilink hedefleri (`wikilinks`, `Hedef`, `Note`…) ve öz-döngüler atılır; kod bloğu/inline-kod içindeki `[[…]]` ayıklanmaz; catalog kenarları JSON'a hiç yazılmaz (−1161 kenar, ≈ −300 KB); `Projects/test_*` dizinleri graftan hariç tutulur (195 yaprak); cognitive düğüm adı ilk satırdan üretilir, satır sonu temizlenir, ≥ 5 aynı adlı düğüm tek düğüme birleştirilir ya da sayaç eklenir.

### 3.2 Yerleşim: hiyerarşik halka + topluluk paketleme + kuvvet ince ayarı

1. **Halka iskeleti (forceRadial):** level 1 hub'lar r₁=260, level 2 dallar r₂=520, level 3 topluluk/alt dallar r₃=780, yapraklar ebeveynin çevresinde r₄ = 60–160 (yerel). Her seviye için `forceRadial(strength 0.08–0.12)`; hub'lar açıya sabitlenmez, yalnız yarıçapa çekilir (kollar organik kalır).
2. **Sektör çekimi:** her hub'ın alt ağacına hub'ın açısı etrafında ±(π/hubSayısı) genişliğinde sektör ağırlık merkezi (`forceX/forceY` hedefi, strength 0.03). Bir dalın yaprakları başka dalın alanına akmaz; kesişme sayısı düşer.
3. **Topluluk paketleme ("cluster-first"):** yapraklar önce topluluk merkezine (strength 0.05) çekilir; topluluk merkezleri ebeveyn dal çevresinde daire paketleme (`d3.packSiblings` eşleniği, Python'da) ile tohumlanır. ≥ 40 yapraklı dallar için yapraklar topluluk düğümüne katlanmış başlar (vis-network outside-in).
4. **Kuvvet parametreleri:** `CHARGE` −30 × (1 + log(1+derece)) (ForceAtlas2 derece ağırlıklı itme; sabit −230 kalkar); `distanceMax` 400 (uzak düğümler itmez → dünya şişmez); yay sertliği d3 kuralı `1/min(deg)` korunur, ağaç yay uzunluğu 60 (yaprak) / 140 (dal); **Dissuade Hubs**: yaprak→hub çekimi `/(deg+1)`; `velocityDecay` 0.4, `alphaDecay` 0.0228; çakışma yarıçapı = düğüm yarıçapı + 2 px, 2 iterasyon.
5. **Kabul ölçütü:** 1145 düğümde dünya yayılımı ≤ 3000×3000 birim (şimdi 8864×8613); ağaç kenarı medyanı ≤ 200 birim (şimdi 557); 382'lik örneklemde ağaç kenarı kesişmesi ≤ 60 (şimdi 180); yerleşim deterministik (aynı veri → aynı konum, tohum korunur).

### 3.3 LOD kuralları (zoom eşikleri; ekran-piksel tabanlı, ölçek `zoom`)

| Zoom | Görünen düğümler | Etiket | Kenar |
|---|---|---|---|
| < 0,25 (uzak) | level ≤ 2 + topluluk özet düğümleri (üye sayısıyla boyut) | level ≤ 1 + en önemli 12 topluluk etiketi | yalnız gövde (level ≤ 2), demetlenmiş, α 0,35 |
| 0,25–0,6 (harita) | + level 3, topluluk hull'ları (alfa şekil, α 0,08 dolgu) | + level 2, topluluk etiketleri (hull üstünde) | + topluluk içi benzerlik kenarları α 0,15 |
| 0,6–1,2 (dal) | + yapraklar **yalnız görünüm alanındaki + seçili dalın** (viewport culling: ekran dışındaki yapraklar benzetime girmez) | ızgara tabanlı etiket (hücre 90 px, hücrede en yüksek `importance`), yaprak etiketleri ≥ 8 px düğümlerde | + yaprak ağaç kenarları, wikilink α 0,25 |
| > 1,2 (yakın) | hepsi (görünüm alanında) | tüm çakışmayanlar, tam `label` (kırpma yok, 2 satıra sarma) | + wikilink kesikli, ağırlığa göre kalınlık |

Kural: bir seviyede görünen düğüm daha yakın seviyelerde kaybolmaz (ZMLT tutarlılığı). Geçişler sert eşik değil 0,1'lik ara bant ile α-karışım (fade), benzetim yeniden ısıtılmaz — yapraklar ebeveynin konumundan "büyüyerek" çıkar (150 ms tween).

### 3.4 Etiketleme
- Öncelik = `level` (küçük önce) → `importance` → `degree`; sıralı liste bir kez hesaplanır, her kare yalnız görünürler süzülür.
- Yerleştirme: 4 aday (sağ, sol, üst, alt), doluluk bit haritası (ekranı 8 px hücrelere böl, `Uint8Array`), O(1) çakışma; kazanamayan etiket hover'da gösterilir.
- Metin: `short_label` ≤ 28 kr; hub/dal 12 px 600, topluluk 11 px 600 + üye sayısı rozeti, yaprak 10 px 400; pil yerine yalnızca yumuşak gölge (`shadowBlur` 0, 1 px koyu kontur ile "halo" — pil dolguları uzak bakışta kutu kalabalığı yapıyor).
- Etiket bitmap önbelleği: metin bir kez offscreen kanvasa çizilir, `drawImage` ile basılır; zoom değişince yalnızca ölçek değişir (metin ekran sabit boyutta olduğu için önbellek geçersiz olmaz).

### 3.5 Kenar stili
- Gövde (level ≤ 2): 1,6 px, α 0,45, hafif eğri; uzak bakışta FDEB demeti (Python'dan gelen 3-5 kontrol noktalı Bezier).
- Yaprak ağaç kenarı: 0,8 px düz, α 0,22; ebeveynden çıkan kenar sayısı > 40 ise ebeveyn çevresinde "yelpaze" gösterimi (kenarlar ebeveyne değil ebeveynin 24 px çapındaki halkasına bağlanır → yıldız merkezi kararmaz).
- Benzerlik: 0,7 px, topluluk rengi α 0,18, yalnız aynı topluluk içinde; topluluklar arası benzerlik hover'da.
- Wikilink: kesikli, ağırlıkla 0,8–2 px; sahte hedefler yok.
- Hover/seçim: seçili düğümün 1-adım komşuluğu tam renk, 2-adım α 0,6, diğer her şey α 0,12 (Sigma "dim" deseni); kenar üzerinde okuma yönü için küçük ok yalnız hover'da.

### 3.6 Efsane (katlanabilir, küçük)
- Sol üstte tek satır, **yalnız bu veride düğümü olan** kategoriler (boş 4 kategori gizli), her kategori sayısıyla (`Raporlar 837`); genişlik ≤ 420 px, yükseklik 26 px; tıklayınca açılan panelde tam liste + topluluk paleti + kenar türleri.
- Kontrol şeridi (zaman/önem/tür/geçerli) efsane panelinin içine taşınır ve **veri yoksa çizilmez** (şimdi 5 ölü kontrol görünüyor).
- `fitToView` örtü alanlarını (efsane, şerit, sağ alt düğmeler) sığdırma dikdörtgeninden düşer.

### 3.7 Mini harita, hover, tıkla, arama, breadcrumb
- **Mini harita:** sağ altta 160×110 px, yalnız level ≤ 3 düğümler nokta olarak; görünüm dikdörtgeni; tıkla/sürükle ile pan; benzetim durduktan sonra bitmap olarak önbelleklenir (her kare çizilmez).
- **Hover:** dim deseni + bilgi kutusu (mevcut), 80 ms gecikme (hızlı geçişlerde titreme yok); hit-test dörtlü ağaçtan.
- **Tıkla:** yaprak → rapor okuyucu (mevcut sinyal); dal/topluluk → o dal açılır ve görünüm **dala sığdırılır** (bütüne değil), animasyonlu 250 ms; çift tık → dal izole (👁️ ile aynı).
- **Breadcrumb:** kanvasın üst orta kısmında `Çekirdek › Yetenekler › financial-auditor › ALM & Risk › <rapor>`; her parça tıklanabilir (`computeBranchSet` atalar zinciri zaten var).
- **Arama:** üst sağda `Ctrl+F` kutusu; ad + `info` üstünde önek/altdizi (tarayıcıda, 1145 düğüm için ≤ 2 ms); sonuç listesi ≤ 8 satır; seçince düğüme uçuş + vurgu + gerekiyorsa dal açma. "Yol göster": iki düğüm seçilince ağaç + wikilink üzerinden en kısa yol (BFS) vurgulanır.
- **Zaman:** slider verisi geldiğinde Obsidian "Animate" benzeri ▶ ile kronolojik oynatma.

### 3.8 Performans hedefleri ve mimari
- Hedef: **1100 düğümde ≥ 50 fps (≤ 20 ms/kare)**, **3000 düğümde ≥ 30 fps (≤ 33 ms/kare)** ana iş parçacığında; kaydırma/zoom sırasında etiket gizleme yok (ölçüm: `performance.now()` ile 120 kare medyan + p95, QWebEngine içinde `page.runJavaScript` ile toplanır ve `docs/reports` ölçüm tablosuna yazılır).
- Fizik Web Worker'a (`OffscreenCanvas` şart değil; konumlar `Float32Array` transfer): ana iş parçacığı yalnız çizer. Benzetim durunca kenar katmanı statik bitmap; hover/seçim üst katman.
- Viewport culling: benzetim ve çizim yalnız görünüm ±%30 marj içindeki yaprakları alır; yapısal düğümler her zaman.
- `resolveCollisions` ızgara anahtarı tamsayı (`gx * 65536 + gy`), dize üretimi kalkar; `applyCharge` özyinelemesi yığın tabanlı döngüye çevrilir; dörtlü ağaç yeniden kullanılarak hit-test.
- JSON diyet: catalog kenarları ve `info` metinleri (rapor yolu) çıkarılır (tıklamada Python'dan istenir); hedef ≤ 500 KB.
- Yenileme: `setHtml` yerine `runJavaScript("applyGraphDelta(...)")` ile artımlı güncelleme (düğüm ekleme/çıkarma), konumlar korunur → kullanıcı yerini kaybetmez.

---

## 4. İş listesi (öncelikli, kabul ölçütlü)

### 4.1 memory-rag-engineer (veri)

| # | Öncelik | İş | Kabul ölçütü |
|---|---|---|---|
| M1 | P0 | Wikilink temizliği: kod bloğu/inline-kod içindeki `[[…]]` ayıklanmaz; hedefi düğüm olmayan kenarlar ve öz-döngüler `build_unified_graph` çıktısına girmez; catalog kenarları JSON'a yazılmaz | Sarkan kenar 0 (şimdi 376), öz-döngü 0 (23), yinelenen çift 0 (110); JSON ≤ 900 KB; mevcut graf testleri yeşil |
| M2 | P0 | `Projects/test_*` (pytest kalıntısı) dizinleri graftan hariç; cognitive düğüm adı ilk satırdan, satır sonsuz, ≤ 40 kr; ≥ 5 aynı adlı düğüm tekilleştirilir | Test projesi 0 (şimdi 3, 195 yaprak); adında `\n` olan düğüm 0 (66); aynı adlı grup ≤ 3 (16) |
| M3 | P0 | GraphStore köprüsü: `build_unified_graph` içinde `graph_store.graph_view_data()`/`list_communities()` ile eşleşen düğümlere `importance`, `t_valid_from/to`, `type`, `community_id` yazılır; `community` düğümleri (89) `member_of` kenarlarıyla grafa girer | `hasTimeData/hasImportanceData/hasCommunityData` gerçek kasada `true`; kontrol şeridinin 5 kontrolü çalışır; ≥ %80 rapor düğümünde `importance` |
| M4 | P0 | `level`, `degree`, `child_count`, `short_label`/`label` alanları; `short_label` `Gorev_<yetenek>_<tarih>_<konu>` kalıbından konu odaklı ve tekil | 837 raporda ≥ 700 farklı `short_label` (şimdi 145); hiçbiri > 28 kr |
| M5 | P1 | Topluluk kalitesi: Louvain/Leiden (networkx yoksa mevcut etiket yayılımı + çözünürlük); ≤ 3 üyeli topluluklar ebeveyn topluluğa katlanır; her topluluğa 3 terimlik etiket + üye sayısı (GraphStore `_label_propagation` etiketleme kodu yeniden kullanılır); benzerlik hesabına başlık yanında ilk 400 karakter içerik | Topluluk sayısı 15–40 (şimdi 88); ≤3 üyeli topluluk 0 (47); her topluluğun `community_label` dolu; modülerlik ≥ 0,45 (ölçülür) |
| M6 | P1 | Rapor sınıflandırma iyileştirme: "varsayılan dal" yerine frontmatter `skill`/`tags` ve içerik anahtar sözcükleriyle alt dal; 40+ yapraklı alt dallar konu topluluklarına bölünür | Tek ebeveynin çocuk sayısı ≤ 80 (şimdi 202/188/185) |
| M7 | P2 | Çevrimdışı FDEB (gövde kenarları, level ≤ 2) ve topluluk merkezi daire paketleme tohumları; kenar `weight` normalize | `bundle` alanı gövde kenarlarının ≥ %90'ında; hesap ≤ 300 ms (1145 düğüm) |
| M8 | P2 | Artımlı graf farkı: `graph_delta(prev_signature)` → eklenen/silinen düğüm-kenar listesi | Tek rapor eklenince fark ≤ 5 KB; tam yeniden kurmadan UI güncellenir |

### 4.2 ui-engineer (JS/kanvas, `knowledge_graph.py` şablonu)

| # | Öncelik | İş | Kabul ölçütü |
|---|---|---|---|
| U1 | P0 | Kuvvet ince ayarı: derece ağırlıklı itme (−30·(1+log(1+deg))), `distanceMax` 400, Dissuade Hubs yaprak çekimi, d3 varsayılan decay'ler; `forceRadial` halkaları (level 1/2/3) + sektör çekimi | Dünya yayılımı ≤ 3000×3000; ağaç kenarı medyanı ≤ 200; kesişme örneklemde ≤ 60; deterministik; 58 iskelet düğümü açılışta örtüşmesiz |
| U2 | P0 | Kademeli LOD (3.3 tablosu): 4 bant, α-karışımlı geçiş, benzetim yeniden ısıtılmaz, viewport culling; ZMLT tutarlılığı | Detay eşiği geçişinde kare süresi sıçraması ≤ 8 ms; zoom 0,95'te görünüm alanında ≥ 60 düğüm (şimdi 4); açılışta alt dal etiketleri görünür |
| U3 | P0 | Efsane: tek satır, yalnız dolu kategoriler + sayılar, katlanabilir panel; ölü kontroller gizli; `fitToView` örtüleri düşer | Efsane yüksekliği ≤ 28 px kapalıyken; 1100×760'ta örtü alanı ≤ %8 (şimdi %13 üst + %5 alt); hiçbir düğüm efsane altında kalmaz |
| U4 | P0 | Etiket motoru: öncelik listesi (level → importance → degree), 4 aday konum, doluluk bit haritası, `short_label`, bitmap önbelleği, ızgara tabanlı seyreltme (90 px) | Zoom 0,5'te ≥ 25 farklı okunur etiket (şimdi 21 ve 12 alt dal etiketi yok); etiket yerleştirme ≤ 1,5 ms/kare 1145 düğümde; çakışan etiket 0 |
| U5 | P1 | Hover "dim" deseni (1-adım tam, 2-adım 0,6, diğer 0,12), dörtlü ağaç hit-test, 80 ms hover gecikmesi; tıkla-dala-sığdır (250 ms tween); breadcrumb | mousemove maliyeti ≤ 0,3 ms (1145 düğüm); dal tıklamasında dal görünüm alanının ≥ %60'ını kaplar |
| U6 | P1 | Topluluk hull (alfa şekil, α 0,08) + hull üstünde topluluk etiketi + üye rozeti; ≤ 8 renkli CVD-güvenli palet (Okabe-Ito/Tol) kategori için, topluluk için ayrık 12 ton | Zoom 0,25–0,6'da hull ve etiket görünür; hull çizimi ≤ 2 ms/kare |
| U7 | P1 | Arama kutusu (`Ctrl+F`, ≤ 8 sonuç, uçuş+vurgu), "yol göster" (BFS), mini harita (bitmap önbellekli, tıkla-pan) | Arama ≤ 5 ms; mini harita çizimi statikken 0 ms/kare; yol vurgusu ≤ 20 ms |
| U8 | P1 | Kenar stili: gövde demet (Python `bundle`), 40+ çocuklu ebeveynde yelpaze halkası, wikilink ağırlık kalınlığı, benzerlik yalnız topluluk içi | Yıldız merkezinde kenar üst üste binmesi görsel olarak kalkar (ekran görüntüsü kıyası); kenar çizimi ≤ 3 ms/kare |
| U9 | P2 | Performans mimarisi: fizik Web Worker (`Float32Array` transfer), statik kenar katmanı bitmap, tamsayı ızgara anahtarı, yığın tabanlı Barnes-Hut, `hideEdgesOnMove` benzeri kaydırma modu; QWebEngine içi ölçüm kancası (`window.__graphStats`) | 1145 düğüm ≥ 50 fps (medyan ≤ 20 ms, p95 ≤ 28 ms); 3000 sentetik düğüm ≥ 30 fps; ölçüm tablosu rapora eklenir |
| U10 | P2 | Artımlı güncelleme `applyGraphDelta` (setHtml yerine), konum koruma; zaman kaydırıcısına ▶ kronolojik oynatma | Yeni rapor eklenince görünüm/zoom korunur; yenileme ≤ 150 ms |

Sıralama önerisi: M1–M4 + U1–U4 (Faz 8a, "okunur harita"), sonra M5–M6 + U5–U8 (Faz 8b, "keşif"), sonra M7–M8 + U9–U10 (Faz 8c, "ölçek"). qa-build-engineer her alt fazda: gerçek kasa ölçüm betiği (bu notun 1.1/1.2 tabloları) yeniden koşulur ve önce/sonra kıyası rapora girer.

---

## 5. Kaynaklar

1. d3-force belgeleri — many-body (strength −30, theta 0.9, Barnes-Hut), link (strength 1/min(count)), collide (iterations), position/forceRadial (strength 0.1), simulation (alphaDecay ≈ 0.0228 = 300 iterasyon, velocityDecay 0.4): https://d3js.org/d3-force/many-body · https://d3js.org/d3-force/link · https://d3js.org/d3-force/collide · https://d3js.org/d3-force/position · https://d3js.org/d3-force/simulation
2. d3-force-3d (vasturiano) README: https://github.com/vasturiano/d3-force-3d
3. Jacomy M., Venturini T., Heymann S., Bastian M. "ForceAtlas2, a Continuous Graph Layout Algorithm for Handy Network Visualization Designed for the Gephi Software", PLOS ONE 2014: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0098679
4. Obsidian Help — Graph view (Filters, Groups, Display, Forces, Local graph): https://obsidian.md/help/plugins/graph
5. Obsidian graph kuvvet varsayılanları (topluluk dökümü, doğrulanmadı): https://deepwiki.com/sakuramodki/obsidian/2.1-graph-visualization ; Graph Pro eklentisi: https://github.com/air-mark/graph-pro
6. "Obsidian's Graph View Is Beautiful and Almost Completely Useless" (Code Culture, blog): https://codeculture.store/blogs/developer-culture/obsidian-graph-view-useful ; "Making Obsidian's Graph View Actually Useful" (Dan Holloran): https://danholloran.me/posts/making-obsidians-graph-view-actually-useful
7. Noack A. "Modularity clustering is force-directed layout", Phys. Rev. E 2009: https://arxiv.org/pdf/0807.4052
8. "Force-Directed Graph Layout Based on Community Discovery and Clustering Optimization", Springer 2021: https://link.springer.com/chapter/10.1007/978-981-16-6775-6_46
9. "Improved Visual Saliency of Graph Clusters with Orderable Node-Link Layouts", IEEE TVCG (Kasım 2024): https://pubmed.ncbi.nlm.nih.gov/39259626/
10. fCoSE (Bilkent i-Vis) — cytoscape.js-fcose README ve makale: https://github.com/iVis-at-Bilkent/cytoscape.js-fcose · https://yoksis.bilkent.edu.tr/pdf/files/15807.pdf
11. vis-network belgeleri — clustering (outside-in / inside-out, hub %3): https://www.hlt.inesc-id.pt/~david/wiki/pt/extensions/vis/docs/network.html · https://visjs.github.io/vis-network/examples/
12. Collins C., Penn G., Carpendale S. "Bubble Sets: Revealing Set Relations with Isocontours over Existing Visualizations", TVCG 2009: https://www.researchgate.net/publication/38015424
13. "A task-based evaluation of combined set and network visualization", Information Sciences 2017: https://www.sciencedirect.com/science/article/pii/S002002551630384X ; "Node, Node-Link, and Node-Link-Group Diagrams: An Evaluation": https://www.researchgate.net/publication/261475318
14. Holten D., van Wijk J. "Force-Directed Edge Bundling for Graph Visualization", CGF 2009: https://onlinelibrary.wiley.com/doi/10.1111/j.1467-8659.2009.01450.x · PDF: https://classes.engineering.wustl.edu/cse557/readings/holten-edgebundling.pdf
15. "Multi-level tree based approach for interactive graph visualization with semantic zoom" (ZMLT), arXiv 1906.05996: https://arxiv.org/abs/1906.05996 · uygulama: https://github.com/cns-iu/map4sci ; GraphMaps: https://www.researchgate.net/publication/322874161
16. Wiens V. ve ark. "Semantic Zooming for Ontology Graph Visualizations", K-CAP 2017: https://dl.acm.org/doi/10.1145/3148011.3148015
17. Sigma.js — ana sayfa ve renderer belgeleri (WebGL düğüm/kenar, Canvas etiket, dörtlü ağaç): https://www.sigmajs.org/ · https://www.sigmajs.org/docs/advanced/renderers/ · https://github.com/jacomyal/sigma.js/
18. Sigma.js `settings.ts` (labelDensity 1, labelGridCellSize 100, labelRenderedSizeThreshold 6, hideEdgesOnMove, hideLabelsOnMove): https://github.com/jacomyal/sigma.js/blob/main/packages/sigma/src/settings.ts
19. Chen Z. ve ark. "Fast and Flexible Overlap Detection for Chart Labeling with Occupancy Bitmap", IEEE VIS 2021: https://idl.cs.washington.edu/files/2021-FastLabels-VIS.pdf
20. Observable — "Collision Detection with quadtree" (Raven Gao): https://observablehq.com/@ravengao/collision-detection-with-quadtree
21. Observable — "Brute-force label collision detection (occlusion)" (Ralph Spandl): https://observablehq.com/@spandl/label-collision-detection-occlusion
22. Okabe-Ito paleti (8 renk, CVD-güvenli): https://easystats.github.io/see/reference/scale_color_okabeito.html · https://conceptviz.app/blog/okabe-ito-palette-hex-codes-complete-reference
23. "Best Color Palettes for Scientific Figures (2026)" — 6–8 renk sınırı, Paul Tol 12: https://scifig.ai/blog/color-palettes-scientific-figures
24. Sigma.js hover/dim deseni (issue #798, Rapidops örnekleri): https://github.com/jacomyal/sigma.js/issues/798 · https://rapidops.medium.com/7-helpful-sigma-js-examples-to-master-graph-visualization-a8cadf9e9b14
25. yFiles "Guide to Creating Knowledge Graph Visualizations" (focus+context, komşuluk genişletme): https://www.yfiles.com/resources/how-to/guide-to-visualizing-knowledge-graphs
26. "Hierarchical Knowledge Graphs: A Novel Information Representation for Exploratory Search Tasks", arXiv 2005.01716 (mini harita çağrı kutusu): https://arxiv.org/pdf/2005.01716 ; Breadcrumb desenleri 2026 (Eleken): https://www.eleken.co/blog-posts/breadcrumbs-ux
27. "Semantic Zoom and Mini-Maps for Software Cities", arXiv 2510.00003: https://arxiv.org/html/2510.00003v1
28. web.dev — "OffscreenCanvas: speed up your canvas operations with a web worker": https://web.dev/articles/offscreen-canvas
29. Scott Logic — "Rendering charts with OffscreenCanvas": https://blog.scottlogic.com/2020/03/19/offscreen-canvas.html
30. Mirko Sertic — "Supercharging HTML5 Canvas Text Performance" (fillText önbelleği, 10 ms → 1 ms): https://www.mirkosertic.de/blog/2015/03/tuning-html5-canvas-filltext/
31. ghostty-web issue #163 — glif atlası / drawImage vs fillText tartışması: https://github.com/coder/ghostty-web/issues/163
32. MDN "Optimizing canvas" ve ag-Grid "Optimising HTML5 Canvas Rendering" (katmanlı kanvas, kirli dikdörtgen): https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas · https://blog.ag-grid.com/optimising-html5-canvas-rendering-best-practices-and-techniques/
33. Mahfuza R., Mondal D., Gutwin C. "Design and Evaluation of Visual Summaries to Improve Readability of Large Network Visualizations", Graphics Interface 2025 (ACM 403 verdi, USask deposu): https://harvest.usask.ca/items/0b1c9cdd-040f-42c0-b932-772b15bae0ac
34. Louvain vs etiket yayılımı (çözünürlük sınırı, küçük topluluklar): https://neo4j.com/docs/graph-data-science/current/algorithms/louvain/ · https://arxiv.org/pdf/1612.02463
35. InfraNodus — topluluk etiketleri / Force Atlas kümeleri (ürün belgesi): https://infranodus.com/use-case/visualize-knowledge-graphs-pkm

Not: [5], [6], [23], [35] blog/ürün kaynağıdır; sayısal iddiaları (Obsidian varsayılan kuvvetleri, 200/500 not eşikleri) doğrulanmamış sayılmalı. Bu nottaki tüm Entropy ölçümleri yukarıda tarif edilen betiklerle bu makinede alınmıştır ve QA tekrar koşabilir.
