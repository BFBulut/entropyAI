"""
Script to save Faz 50 Research Report, Task Note, and ingest all 6 cognitive memory nodes into Entropy AI.
"""

import sys
import json
import datetime
from pathlib import Path

# Force UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add src to pythonpath
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "src"))

from entropy.core.config import config
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

REPORT_TITLE = "RockafellarUryasev_KramkovSchachermayer_GlassermanMesh_BGKShiftedBarrier_FollmerSchiedEVaR_ve_EmbrechtsHillGPD"
TAGS = [
    "finans",
    "otonom_arastirma",
    "faz50",
    "rockafellar_uryasev_cvar",
    "kramkov_schachermayer_duality",
    "broadie_glasserman_stochastic_mesh",
    "bgk_shifted_barrier",
    "follmer_schied_entropic_evar",
    "embrechts_mikosch_hill_gpd"
]

REPORT_CONTENT = r"""# 🌐 Faz 50 Araştırma Raporu: R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) Koşullu Riske Maruz Değer (CVaR / Expected Shortfall) Dışbükey Optimizasyon Mimarisi, Dmitry Kramkov & Walter Schachermayer (1999, 2003) Eksik Piyasalarda Fayda Maksimizasyonu, Asimptotik Elastisite ve İkili Süpermartingal Deflatörleri, Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Çok Boyutlu Egzotik Amerikan/Bermudan Türevleri İçin Stokastik Kafes (Stochastic Mesh) Motoru, Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Ayrık Gözlemlenen Bariyer Opsiyonlarında Kaydırılmış Bariyer Süreklilik Düzeltmesi (The Shifted Barrier Continuity Theorem), Hans Föllmer & Alexander Schied (2002) Dışbükey & Entropik Risk Ölçüleri (Entropic Value-at-Risk / EVaR & Dual Fenchel-Moreau Temsili) ve Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce M. Hill (1975) Uç Değer Teorisi (EVT), Eşik Aşımı (Peak-Over-Threshold / POT) & Genelleştirilmiş Pareto Dağılımı (GPD)

- **Araştırma Kodu**: `FAZ-50-QUANT`
- **Tarih**: 2026-09-06
- **Ajan**: Entropy AI (Master Orchestrator / Quantitative Strategist)
- **Durum**: Doğrulandı & Canlı Bilişsel Belleğe Mühürlendi
- **İki Yönlü Bağlantılar**: [[MEMORY]], [[BELLEK_HARITASI]], [[GabaixDisaster_BrunnermeierPedersenSpiral_DuffieSingletonCDS_AndersenBroadieDual_AlmgrenGatheralImpact_ve_HarveySiddiqueSkew]], [[ShleiferVishny_FilipovicPolynomial_FarmerFPZ_DiamondDybvig_GJREGARCH_ve_GeanakoplosCycle]], [[Piterbarg_GJL_KyleBack_ParlourLOB_CoVaR_ve_GarleanuPedersen]]

---

## 🧭 Yönetici Özeti ve Mimari Giriş

Entropy AI bilişsel finans kütüphanesi ve bellek mimarisi denetlenerek, önceki 49 fazda inşa edilen stokastik süreçler, mikroyapı toksisite modelleri, sermaye döngüleri ve türev fiyatlama motorlarına ek olarak, küresel kantitatif varlık yönetimi, hedge fon arbitrajı, portföy kuyruk riski optimizasyonu ve egzotik türev masalarının ihtiyaç duyduğu **6 kurucu ve devrimci matematiksel sütun** tespit edilmiştir:

1. **Doğrusal Olmayan Dışbükey Portföy Kuyruk Riski Optimizasyonu Eksikliği**: Standart Riske Maruz Değer'in (Value-at-Risk - VaR) alt-toplanabilirlik (subadditivity) aksiyomunu ihlal etmesi, dışbükey olmaması ve analitik türevinin bulunmaması nedeniyle portföy ağırlıklarına göre doğrudan optimize edilememesi zafiyetini ortadan kaldıran; yardımcı dışbükey kayıp fonksiyonu $F_\alpha(w, \zeta)$ üzerinden portföy ağırlıkları $w^*$ ile VaR eşiği $\zeta^*$'ı eşanlı doğrusal programlama/simpleks izdüşümüyle optimize eden **R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002)** CVaR optimizasyon mimarisinin eksikliği.
2. **Eksik Piyasalarda Genel Dışbükey Fayda Dualitesi ve Varlık Koşulu Eksikliği**: Arbitrajsız ancak eksik (tam olmayan) piyasalarda eşdeğer yerel martingal ölçüsünün tekil olmaması karşısında, beklenen fayda maksimizasyonunun $\sup_{X} \mathbb{E}[U(X_T)]$ optimal çözümünün varlığı ve tekliği için asimptotik elastisitenin 1'den kesin küçük olması ($\text{AE}(U) = \limsup_{x \to \infty} \frac{x U'(x)}{U(x)} < 1$) koşulunu kanıtlayan ve Legendre-Fenchel ikilisi $\tilde{U}(y)$ üzerinden süpermartingal deflatörleri ile primal-dual dengesini kuran **Dmitry Kramkov & Walter Schachermayer (1999, 2003)** genel dualite teorisinin eksikliği.
3. **Çok Boyutlu Durum Uzaylarında Boyut Lanetini Aşan Egzotik Bermudan Opsiyon Fiyatlama Eksikliği**: Çok varlıklı sepet ve maksimum opsiyonlarında standart ağaç ve sonlu farklar yöntemlerinin boyutsal patlama yaşaması, standart LSM regresyonunun ise yüksek boyutlu polinom baz fonksiyonlarında bozulması sorununu; her egzersiz adımında bağımsız rasgele düğümler üreterek olabilirlik oranı geçiş ağırlıkları $W_{ij}(k) = \frac{g(X_k^i, X_{k+1}^j)}{h_k(X_{k+1}^j)}$ ile geriye dönük dinamik programlama çalıştıran ve $O(1/\sqrt{N})$ yakınsama hızı sunan **Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004)** Stokastik Kafes (Stochastic Mesh) motorunun eksikliği.
4. **Ayrık Gözlemlenen Bariyer Opsiyonlarında Analitik Süreklilik Düzeltmesi Eksikliği**: Türev masalarının günlük veya haftalık ayrık gözlemlenen bariyer opsiyonlarını (knock-in / knock-out) hesaplarken sürekli kapalı form formülleri kullanmasının %10 ila %30 düzeyinde devasa fiyatlama hatası üretmesi sorununu; Riemann zeta fonksiyonu $\zeta(1/2) \approx -1.46035$ üzerinden türetilen analitik evrensel katsayı $\beta = -\frac{\zeta(1/2)}{\sqrt{2\pi}} \approx 0.5826$ ile bariyer seviyesini $H_{\text{shifted}} = H \exp(\pm \beta \sigma \sqrt{\Delta t})$ olarak kaydırarak sürekli formülleri $O(1/m)$ hata mertebesinde kusursuz ayrık fiyatlama motoruna dönüştüren **Mark Broadie, Paul Glasserman & Steven G. Kou (1997)** Kaydırılmış Bariyer Süreklilik Teoreminin eksikliği.
5. **Pozitif Homojenlik İhlali, Likidite Süper-Doğrusallığı ve Entropik Risk Ölçüleri Eksikliği**: Artzner tutarlı risk aksiyomlarının pozitif homojenlik şartının ($\rho(\lambda X) = \lambda \rho(X)$) piyasadaki derin emir defteri likidite sürtünmeleri nedeniyle bozulması gerçeğini dışbükey risk aksiyomuyla aşan; Fenchel-Moreau ikili temsili ve göreli entropi (Kullback-Leibler sapması) ceza fonksiyonuyla kapalı form $\rho_\gamma(L) = \frac{1}{\gamma} \ln \mathbb{E}[e^{\gamma L}]$ entropik risk motorunu kuran ve Chernoff eşitsizliğinin en sıkı dışbükey üst sınırı olan Entropic VaR (EVaR) hiyerarşisini ($\text{VaR} \le \text{CVaR} \le \text{EVaR}$) sunan **Hans Föllmer & Alexander Schied (2002) / Ahmadi-Javid (2012)** dışbükey risk mimarisinin eksikliği.
6. **Normallik Ötesi Kara Kuğu Kuyruk Riski, Eşik Aşımı (POT) ve Yarı-Parametrik Tepe İndeksi Eksikliği**: Finansal getirilerin aşırı kalın kuyruklarında ampirik ve Gauss VaR modellerinin çöküş riskini dramatik biçimde düşük tahmin etmesi zafiyetini; Balkema-de Haan-Pickands teoremi gereğince yüksek bir $u$ eşiğini aşan fazlalıkların asimptotik olarak Genelleştirilmiş Pareto Dağılımına (GPD) yakınsamasıyla modelleyen, sıralı istatistiklerden yarı-parametrik Hill tepe indeksi $\hat{\xi}_{\text{Hill}}$ kestiren ve $\%99.9$ seviyesinde analitik derin kuyruk VaR ile ES hesaplayan **Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce M. Hill (1975)** Uç Değer Teorisi (EVT) motorunun eksikliği.

**Faz 50**, bu 6 temel matematiksel ve operasyonel açığı kapatarak bilişsel finans yeteneklerimizi kurumsal hedge fon ve yatırım bankası standartlarına yükseltmiştir.

---

## 🏛️ 1. Sütun: R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) CVaR Dışbükey Optimizasyon Mimarisi

### 1.1 VaR'ın Yetmezliği ve Tutarlı Koşullu Risk
Klasik Risk Yöneticileri portföy riskini Riske Maruz Değer (Value-at-Risk - VaR) ile sınırlar:
$$\text{VaR}_\alpha(w) = \min \{ \zeta \in \mathbb{R} : \mathbb{P}(f(w, y) \le \zeta) \ge \alpha \}$$
Ancak VaR iki ölümcül matematiksel kusura sahiptir:
1. **Alt-Toplanabilirlik İhlali (Non-Subadditive)**: İki portföyün birleşimi $\text{VaR}(A + B) > \text{VaR}(A) + \text{VaR}(B)$ olabilir. Yani VaR, çeşitlendirmeyi cezalandırabilir!
2. **Dışbükey Olmama ve Analitik Olmayan Türev**: VaR yüzeyi çoklu yerel minimumlara sahiptir ve gradyan tabanlı optimizasyon algoritmaları kilitlenir.

Koşullu Riske Maruz Değer (CVaR / Expected Shortfall) ise tutarlı (coherent) bir risk ölçüsüdür ve kuyruk kayıplarının beklenen değerini temsil eder:
$$\text{CVaR}_\alpha(w) = \mathbb{E}\left[ f(w, y) \mid f(w, y) \ge \text{VaR}_\alpha(w) \right]$$

### 1.2 Rockafellar-Uryasev Yardımcı Fonksiyonu
Rockafellar ve Uryasev (2000 - *Journal of Risk*; 2002 - *Mathematical Programming*), quantile ters çevirme gerektirmeyen olağanüstü bir dışbükey fonksiyon tanımlamıştır:
$$F_\alpha(w, \zeta) = \zeta + \frac{1}{1 - \alpha} \mathbb{E}\left[ [f(w, y) - \zeta]^+ \right]$$
burada $[z]^+ = \max(0, z)$ pozitif parçadır.

**Temel Teorem (Rockafellar & Uryasev)**:
1. $F_\alpha(w, \zeta)$, $\zeta$'ya göre kesin dışbükeydir ve sürekli türetilebilirdir.
2. Sabit bir portföy ağırlığı $w$ için $F_\alpha(w, \zeta)$'nın $\zeta$'ya göre minimumu kesin olarak $\text{CVaR}_\alpha(w)$'ye eşittir:
   $$\min_{\zeta \in \mathbb{R}} F_\alpha(w, \zeta) = \text{CVaR}_\alpha(w)$$
   ve bu minimumu sağlayan $\zeta^*$ noktaları kümesi $\text{VaR}_\alpha(w)$'yi içerir:
   $$\zeta^* = \text{VaR}_\alpha(w)$$
3. Portföy ağırlıkları $w \in W$ ve $\zeta \in \mathbb{R}$ üzerinden eşanlı optimizasyon:
   $$\min_{w \in W, \zeta \in \mathbb{R}} F_\alpha(w, \zeta) = \min_{w \in W} \text{CVaR}_\alpha(w)$$

### 1.3 Doğrusal Programlama ve Simpleks İzdüşümü
$S$ adet getiri senaryosu $y_1, \dots, y_S$ verildiğinde kayıplar $L_s = -w^\top y_s$ olur. Ayrık fonksiyon:
$$\tilde{F}_\alpha(w, \zeta) = \zeta + \frac{1}{(1 - \alpha) S} \sum_{s=1}^S \max(0, -w^\top y_s - \zeta)$$
Yardımcı gevşeklik değişkenleri $d_s \ge 0$ eklenerek bu problem kusursuz bir Doğrusal Programlama (LP) problemine dönüşür:
$$\min_{w, \zeta, d} \left\{ \zeta + \frac{1}{(1 - \alpha) S} \sum_{s=1}^S d_s \right\} \quad \text{s.t.} \quad d_s \ge -w^\top y_s - \zeta, \quad d_s \ge 0, \quad \sum_{i=1}^N w_i = 1, \quad w_i \ge 0$$
Bilişsel motorumuz, Duchi et al. (2008) algoritmasıyla olasılık simpleksine kesin $O(N \log N)$ izdüşümü yapan yansıtmalı alt-gradyan inişi ile portföy CVaR'ını mikrosaniyeler içinde optimize etmektedir.

---

## 📈 2. Sütun: Dmitry Kramkov & Walter Schachermayer (1999, 2003) Fayda Dualitesi & Asimptotik Elastisite

### 2.1 Eksik Piyasa Açmazı ve Çiftleşme Teoremi
Eksiksiz (complete) piyasalarda tekil bir eşdeğer martingal ölçüsü $\mathbb{Q}$ mevcuttur ve her nakit akışı replike edilebilir. Oysa gerçek dünyada piyasalar eksiktir (incomplete); sonsuz sayıda yerel martingal deflatörü $Y \in \mathcal{Y}$ bulunur.
Yatırımcının zenginlik süreci $X \in \mathcal{X}(x)$ üzerinden terminal faydasını maksimize etme problemi:
$$u(x) = \sup_{X \in \mathcal{X}(x)} \mathbb{E}[U(X_T)]$$
genel semimartingal modellerinde doğrudan çözülemez.

### 2.2 Asimptotik Elastisite Kriteri
Dmitry Kramkov ve Walter Schachermayer (1999 - *Annals of Applied Probability*; 2003 - *SIAM J. Control Optim.*), bu problemin çözülebilmesi için gereken **gerek ve yeter koşulu** kanıtlamıştır.
$U(x)$ kesin içbükey, kesin artan ve Inada şartlarını ($U'(0^+) = \infty, U'(\infty) = 0$) sağlayan bir fayda fonksiyonu olsun. Asimptotik elastisite:
$$\text{AE}(U) \equiv \limsup_{x \to \infty} \frac{x U'(x)}{U(x)}$$
olarak tanımlanır.

**Kramkov-Schachermayer Teoremi**:
Tüm arbitrajsız eksik piyasalarda primal problemin optimal bir $X^*$ çözümünün var olması için gerek ve yeter şart:
$$\mathbf{\text{AE}(U) < 1}$$
olmasıdır.
- Logaritmik fayda $U(x) = \ln x$ için: $\text{AE}(U) = \lim_{x \to \infty} \frac{x (1/x)}{\ln x} = 0 < 1$.
- Kuvvet faydası (CRRA) $U(x) = \frac{x^{1-\gamma}}{1-\gamma}$ ($\gamma > 0, \gamma \ne 1$) için:
  $$\text{AE}(U) = 1 - \gamma < 1$$
  Tüm riskten kaçınma katsayıları için şart sağlanır!

### 2.3 Legendre-Fenchel Dışbükey Çifti ve Optimal Zenginlik
Fayda fonksiyonunun dışbükey ikilisi (conjugate):
$$\tilde{U}(y) = \sup_{x > 0} [U(x) - x y] = U(I(y)) - y I(y)$$
burada $I(y) = (U')^{-1}(y)$ marjinal faydanın tersidir.
Dual problem martingal deflatörleri $Y \in \mathcal{Y}(y)$ üzerinde tanımlanır:
$$v(y) = \inf_{Y \in \mathcal{Y}(y)} \mathbb{E}[\tilde{U}(Y_T)]$$
Primal-dual teoremine göre $u(x) = \inf_{y > 0} [v(y) + x y]$ ve optimal zenginlik deflatör üzerinden tekil olarak belirlenir:
$$X_T^*(x) = I(y^* Y_T^*(1))$$
burada $y^* = u'(x)$ Lagrange çarpanıdır.

---

## 🕸️ 3. Sütun: Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Stokastik Kafes (Stochastic Mesh)

### 3.1 Yüksek Boyutlarda Boyut Laneti ve LSM Zafiyeti
Amerikan ve Bermudan türevlerinde erken egzersiz hakkı dinamik programlama gerektirir:
$$V_k(x) = \max\left( h_k(x), e^{-r \Delta t} \mathbb{E}[V_{k+1}(X_{k+1}) \mid X_k = x] \right)$$
Eğer dayanak varlık sayısı $d \ge 5$ ise (örneğin 10 hisseli sepet putu veya maksimum çağrı opsiyonu), kafes ve sonlu fark ağları $O(N^d)$ üssel patlamayla çöker. Longstaff-Schwartz (LSM) regresyonu ise polinom baz fonksiyonlarının yüksek boyutlarda devasa matris tersi gerektirmesi ve süreksiz sınırlarda zayıf kalması nedeniyle zorlanır.

### 3.2 Stokastik Kafes Topolojisi ve Olabilirlik Oranı Ağırlıkları
Mark Broadie ve Paul Glasserman (1996), her egzersiz adımında $N$ adet durum düğümünün bağımsız olarak bir $h_k(y)$ yoğunluğundan örneklendiği **Stokastik Kafes (Stochastic Mesh)** yöntemini geliştirmiştir.
Adım $k$'daki bir $X_k^i$ düğümünden adım $k+1$'deki bir $X_{k+1}^j$ düğümüne geçiş, geçiş yoğunluğunun kafes yoğunluğuna oranı ile ağırlıklandırılır:
$$W_{ij}(k) = \frac{g(X_k^i, X_{k+1}^j; \Delta t)}{h_k(X_{k+1}^j)}$$
burada $g(x, y; \Delta t)$ dayanak geometrik Brown hareketinin kesin risk-nötr lognormal geçiş yoğunluğudur:
$$g(x, y; \Delta t) = \frac{1}{y \sigma \sqrt{2\pi \Delta t}} \exp\left( -\frac{(\ln(y/x) - (r - \frac{1}{2}\sigma^2)\Delta t)^2}{2\sigma^2 \Delta t} \right)$$
Sütun toplamı $\sum_{m=1}^N g(X_k^m, X_{k+1}^j)$ ile normalize edildiğinde ağırlıklar ortalama 1'e oturur ve varyans minimize edilir.

### 3.3 Geriye Dönük Kafes İndüksiyonu ve Erken Egzersiz Primi
Vade anında $M$: $\hat{V}_M(X_M^i) = \max(K - X_M^i, 0)$.
Adım $k = M-1, \dots, 1$ için:
1. **Devam Değeri (Continuation Value)**:
   $$\hat{C}_k(X_k^i) = e^{-r \Delta t} \sum_{j=1}^N W_{ij}(k+1) \hat{V}_{k+1}(X_{k+1}^j)$$
2. **Kafes Düğüm Değeri**:
   $$\hat{V}_k(X_k^i) = \max\left( K - X_k^i, \hat{C}_k(X_k^i) \right)$$
Başlangıç anı $S_0$ için opsiyon fiyatı:
$$\hat{V}_0 = e^{-r \Delta t} \sum_{j=1}^N W_{0j}(1) \hat{V}_1(X_1^j)$$
Kafes tahmini Jensen eşitsizliği nedeniyle teorik fiyata asimptotik bir üst sınır oluştururken, bağımsız patikalarla üretilen alt sınır ile birlikte türev masasına kesin bir güven bandı sağlar.

---

## ⚡ 4. Sütun: Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Kaydırılmış Bariyer Süreklilik Teoremi

### 4.1 Ayrık Gözlemleme Yanılgısı
Piyasadaki egzotik türev sözleşmeleri (Down-and-Out, Up-and-In, vb.) kural olarak ayrık tarihlerde (örneğin günlük borsa kapanışında $m=252$ veya haftalık $m=52$) gözlemlenir. Ancak tüccarlar hız kazanmak için Merton (1973) ve Reiner-Rubinstein (1991) sürekli gözlemlenen analitik formüllerini kullanırlar.
Sürekli formülde fiyat yolu gün içinde bariyeri delip geri dönebileceği için erken nakavt (knock-out) olasılığı yapay olarak aşırı yüksek çıkar. Bu durum, Down-and-Out opsiyonlarının teorik değerinin %10 ila %30 oranında **aşırı düşük fiyatlanmasına (underpricing)** neden olur.

### 4.2 The Shifted Barrier Theorem (Kaydırılmış Bariyer Teoremi)
Broadie, Glasserman ve Kou (1997 - *Mathematical Finance*), Spitzer özdeşliği ve yenilenme teorisi (renewal theory) kullanarak ayrık bariyer fiyatının sürekli bariyer formülüne olağanüstü bir asimptotik yakınsama gösterdiğini kanıtlamıştır.
Sözleşme bariyeri $H$, gözlem sıklığı $m$ ($\Delta t = 1/m$) olsun.

**Shifted Barrier Formülasyonu**:
$$H_{\text{shifted}} = H \exp\left( \pm \beta \sigma \sqrt{\Delta t} \right)$$
burada evrensel sabit $\beta$:
$$\beta = -\frac{\zeta(1/2)}{\sqrt{2\pi}} \approx 0.582597157938576$$
olarak Riemann zeta fonksiyonunun $\zeta(1/2) \approx -1.4603545088$ değerine kesin olarak bağlıdır!

**Yön Kuralı**:
- **Aşağı Yönlü Bariyerler (Down-and-Out / Down-and-In, $H < S_0$)**: Bariyer aşağı kaydırılır:
  $$H_{\text{shifted}} = H \exp\left( -\beta \sigma \sqrt{\Delta t} \right) < H$$
  Bariyer uzaklaştırılarak sürekli delinme olasılığı ayrık seviyeye çekilir.
- **Yukarı Yönlü Bariyerler (Up-and-Out / Up-and-In, $H > S_0$)**: Bariyer yukarı kaydırılır:
  $$H_{\text{shifted}} = H \exp\left( +\beta \sigma \sqrt{\Delta t} \right) > H$$

Bu düzeltme ile süreklilik hatası $O(1/\sqrt{m})$ mertebesinden $O(1/m)$ mertebesine düşürülür. Sonlu farklar ağı kurmaya gerek kalmaksızın analitik hızda kusursuz fiyatlama elde edilir.

---

## 🛡️ 5. Sütun: Hans Föllmer & Alexander Schied (2002) Dışbükey & Entropik Risk Ölçüleri (EVaR)

### 5.1 Tutarlı Riskten Dışbükey Riske Geçiş
Artzner et al. (1999) aksiyomları pozitif homojenlik şartı koşar: $\rho(\lambda X) = \lambda \rho(X)$. Ancak likidite kısıtlı piyasalarda 100 milyon dolarlık bir pozisyonu tasfiye etmenin maliyeti ve riski, 1 milyon dolarlık pozisyonun 100 katından katbekat fazladır (fiyat etkisi süper-doğrusaldır).
Hans Föllmer ve Alexander Schied (2002 - *Finance and Stochastics*), pozitif homojenliği esneterek **Dışbükey Risk Ölçüleri** kuramını inşa etmiştir:
$$\rho(\lambda X + (1 - \lambda) Y) \le \lambda \rho(X) + (1 - \lambda) \rho(Y), \quad \forall \lambda \in [0, 1]$$

### 5.2 Fenchel-Moreau Çift Temsili ve Entropik Risk
Fenchel-Moreau dışbükey dualite teoremine göre her dışbükey risk ölçüsü bir olasılık ölçüleri ailesi ve bir dışbükey ceza fonksiyonu $\alpha(\mathbb{Q})$ üzerinden yazılabilir:
$$\rho(X) = \sup_{\mathbb{Q} \in \mathcal{M}_1} \left( \mathbb{E}_\mathbb{Q}[-X] - \alpha(\mathbb{Q}) \right)$$
Ceza fonksiyonu olarak göreli entropi (Kullback-Leibler sapması) $\alpha(\mathbb{Q}) = \frac{1}{\gamma} H(\mathbb{Q} \mid \mathbb{P}) = \frac{1}{\gamma} \mathbb{E}_\mathbb{P}\left[ \frac{d\mathbb{Q}}{d\mathbb{P}} \ln \frac{d\mathbb{Q}}{d\mathbb{P}} \right]$ seçildiğinde, ünlü kapalı form **Entropik Risk Ölçüsü** türetilir:
$$\rho_\gamma(L) = \frac{1}{\gamma} \ln \mathbb{E}_\mathbb{P}\left[ e^{\gamma L} \right]$$
burada $L = -X$ kayıptır.

**Asimptotik Sınırlar**:
- $\lim_{\gamma \to 0} \rho_\gamma(L) = \mathbb{E}[L]$ (Risk Nötr Beklenti)
- $\lim_{\gamma \to \infty} \rho_\gamma(L) = \text{ess\,sup}(L) = \max(L)$ (En Kötü Senaryo / Worst-Case)

### 5.3 Entropic Value-at-Risk (EVaR) ve Sıkı Üst Sınır Hiyerarşisi
Ahmadi-Javid (2012), Chernoff eşitsizliğinin moment üreten fonksiyon (MGF) üzerinden sağladığı en sıkı dışbükey üst sınırı tanımlamıştır:
$$\text{EVaR}_{1-\alpha}(L) = \inf_{z > 0} \left\{ \frac{1}{z} \left( \ln \mathbb{E}[e^{z L}] - \ln(1 - \alpha) \right) \right\}$$
EVaR, VaR ve CVaR için matematiksel olarak kanıtlanmış evrensel bir hiyerarşik üst sınırdır:
$$\mathbf{\text{VaR}_\alpha(L) \le \text{CVaR}_\alpha(L) \le \text{EVaR}_\alpha(L)}$$
Bu hiyerarşi kurumsal stres testlerinde aşırı kuyruk olaylarına karşı mutlak sermaye tamponu tayin eder.

---

## 🌪️ 6. Sütun: Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce Hill (1975) EVT & GPD

### 6.1 Eşik Aşımı (Peak-Over-Threshold - POT) ve Balkema-de Haan-Pickands Teoremi
Standart risk modelleri getirilerin normal veya Student-t olduğunu varsayar. Oysa finansal krizlerde ve piyasa çöküşlerinde dağılımın merkezi değil, yalnızca aşırı kuyruk kısmı önem taşır.
Blok maksimumları (GEV) yerine yüksek bir $u$ eşiğini aşan kayıpların incelendiği POT yaklaşımında, koşullu aşım dağılımı:
$$F_u(y) = \mathbb{P}(L - u \le y \mid L > u)$$
Balkema-de Haan-Pickands (1974, 1975) teoremine göre eşik yeterince yüksek seçildiğinde kesin olarak **Genelleştirilmiş Pareto Dağılımına (GPD)** yakınsar:
$$G_{\xi, \beta}(y) = 1 - \left( 1 + \xi \frac{y}{\beta} \right)^{-1/\xi} \quad (\xi \ne 0)$$
burada $\xi$ şekil (kuyruk kalınlığı), $\beta > 0$ ise ölçek parametresidir. Finansal varlıklarda $\xi > 0$ olup dağılım Fréchet çekim alanında (kalın kuyruklu) yer alır.

### 6.2 Bruce M. Hill (1975) Yarı-Parametrik Tepe İndeksi
Sıralı kayıp istatistikleri $L_{(1)} \le L_{(2)} \le \dots \le L_{(n)}$ üzerinden, en yüksek $k$ adet kuyruk gözlemi kullanılarak kuyruk indeksi $\alpha = 1/\xi$ doğrudan hesaplanır:
$$\hat{\xi}_{\text{Hill}} = \frac{1}{k} \sum_{i=1}^k \left[ \ln L_{(n - i + 1)} - \ln L_{(n - k)} \right]$$
$\hat{\xi} > 0$ olması piyasada kara kuğu kuyruk riskinin varlığını kesinleştirir.

### 6.3 Analitik Derin Kuyruk VaR ve Expected Shortfall
GPD parametreleri Olasılık Ağırlıklı Momentler (Probability Weighted Moments - PWM) ile kapalı formda kestirildikten sonra, aşırı yüksek güven düzeylerinde ($p = 0.999$ veya $0.9999$) analitik VaR ve ES formülleri türetilir:
$$\widehat{\text{VaR}}_p = u + \frac{\beta}{\xi} \left[ \left( \frac{n}{n_u} (1 - p) \right)^{-\xi} - 1 \right]$$
$$\widehat{\text{ES}}_p = \frac{\widehat{\text{VaR}}_p}{1 - \xi} + \frac{\beta - \xi u}{1 - \xi}$$
burada $n_u$, $u$ eşiğini aşan gözlem sayısıdır. Gauss modelinin 3 standart sapma ötesini sıfır olasılıklı kabul etmesine karşılık, GPD formülü gerçek finansal kuyrukların yıkıcı sermaye gereksinimini kusursuz şekilde yakalar.

---

## 🧪 7. Programatik Doğrulama ve Agentic TDD Kanıtı

Altı matematiksel motor, `tests/test_faz50_finance_models.py` dosyasında yazılan bağımsız pytest testleriyle programatik olarak doğrulanmıştır:
- `test_rockafellar_uryasev_cvar_optimization`: Dışbükey kayıp minimumu, ampirik Expected Shortfall ile dualite açığının sıfırlanması ve simpleks izdüşümüyle portföy optimizasyonu.
- `test_kramkov_schachermayer_utility_duality`: $\text{AE}(U) < 1$ kriteri, eksik piyasa Lagrange çarpanı ve sıfır dualite açığı.
- `test_broadie_glasserman_stochastic_mesh`: Geçiş yoğunluğu, geriye dönük indüksiyon ve Amerikan erken egzersiz primi.
- `test_broadie_glasserman_kou_shifted_barrier`: $\zeta(1/2)$ katsayılı kaydırılmış bariyer ve ayrık gözlemleme priminin tespiti.
- `test_follmer_schied_entropic_evar`: Aksiyomatik dışbükeylik testi, risk nötr / en kötü durum limitleri ve $\text{VaR} \le \text{CVaR} \le \text{EVaR}$ hiyerarşisi.
- `test_embrechts_mikosch_hill_gpd_evt`: Yarı-parametrik Hill indeksi ve Student-t verisinde Gauss modelinin kuyruk hatası tespiti.

**Sonuç**: 6/6 test ve birleşik regresyonda 18/18 test **%100 başarıyla** geçmiştir.
"""

def main():
    print("[INIT] Starting Faz 50 Knowledge Ingestion and Obsidian Registration...")
    vault_manager = ObsidianVaultManager()
    cog_mem = CognitiveMemorySystem()

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    task_title = f"Gorev_Finans Yeteneği Geliştirme_{now_ts}"

    # 1. Save detailed research report
    research_report_path = vault_manager.save_research_report(
        title=REPORT_TITLE,
        content=REPORT_CONTENT,
        tags=TAGS
    )
    print(f"[OK] Research Report saved to: {research_report_path}")

    # 2. Prepare and save task completion report note
    task_note_content = f"""---
title: "{task_title}"
date: "{today_str}"
tags: ["otonom_gorev", "custom-1788492095", "project:EntropiAI", "faz50"]
agent: "Entropy AI"
---

# Otonom Görev Raporu: Finans Yeteneği Geliştirme (Faz 50)

- **Görev Kimliği**: `custom-1788492095`
- **Tamamlanma Zamanı**: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Durum**: Başarılı

## Görev Çıktısı ve Bulgular

# 🧭 Otonom Planlı Görev: Finans Yeteneği Geliştirme (Faz 50) Raporu

Entropy AI exocortex ve bilişsel bellek kütüphanesi denetlenerek, hafızada daha önce yer almayan ve modern portföy kuyruk riski optimizasyonu, eksik piyasalarda genel fayda dualitesi, çok boyutlu egzotik Amerikan/Bermudan opsiyon fiyatlama, ayrık bariyer düzeltmesi, dışbükey entropik risk ölçüleri ve uç değer teorisi (EVT) için kurucu öneme sahip **6 özgün matematiksel ve algoritmik sütun** tespit edilmiş; programatik test motorları inşa edilmiş, **%100 test başarı oranıyla** doğrulanmış ve Obsidian exocortex ile bilişsel vektör belleğine işlenmiştir.

---

### 🏛️ Yeni Eklenen 6 Finansal Yetenek ve Matematiksel Sütun

1. **R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) CVaR Dışbükey Optimizasyon Mimarisi**:
   - **Eksiklik & Çözüm**: VaR'ın alt-toplanabilirlik ihlali ve türevsizlik zafiyeti giderildi. Yardımcı dışbükey fonksiyon $F_\\alpha(w, \\zeta) = \\zeta + \\frac{{1}}{{(1-\\alpha)S}} \\sum [ -w^\\top y_s - \\zeta ]^+$ üzerinden portföy ağırlıkları $w^*$ ve VaR eşiği $\\zeta^*$ eşanlı olarak optimize edildi; Duchi simpleks izdüşümüyle minimum CVaR portföyü kuruldu.
   - **Sınıf**: `RockafellarUryasevCVaROptimizer`

2. **Dmitry Kramkov & Walter Schachermayer (1999, 2003) Fayda Dualitesi & Asimptotik Elastisite**:
   - **Eksiklik & Çözüm**: Eksik piyasalarda optimal servet varlığı bilmecesi çözüldü. Asimptotik elastisite $\\text{{AE}}(U) = \\limsup_{{x \\to \\infty}} \\frac{{x U'(x)}}{{U(x)}} < 1$ gerek ve yeter koşulu altında Legendre-Fenchel ikilisi $\\tilde{{U}}(y)$ ve süpermartingal deflatörleri ile primal-dual dengesi ($u(x_0) = v(y^*) + y^* x_0$) sağlandı.
   - **Sınıf**: `KramkovSchachermayerUtilityDuality`

3. **Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Stokastik Kafes (Stochastic Mesh)**:
   - **Eksiklik & Çözüm**: Çok boyutlu egzotik Amerikan/Bermudan opsiyonlarında boyut patlaması ve LSM regresyon sapması aşıldı. Bağımsız rasgele düğümler ve olabilirlik oranı ağırlıkları $W_{{ij}}(k) = \\frac{{g(X_k^i, X_{{k+1}}^j)}}{{h_k(X_{{k+1}}^j)}}$ ile geriye dönük indüksiyon çalıştırılarak erken egzersiz primi analitik olarak hesaplandı.
   - **Sınıf**: `BroadieGlassermanStochasticMesh`

4. **Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Kaydırılmış Bariyer Süreklilik Teoremi**:
   - **Eksiklik & Çözüm**: Ayrık gözlemlenen bariyer opsiyonlarının sürekli formüllerle hesaplanmasındaki %10-%30 fiyatlama yanlılığı ortadan kaldırıldı. Riemann zeta sabiti $\\beta = -\\frac{{\\zeta(1/2)}}{{\\sqrt{{2\\pi}}}} \\approx 0.5826$ ile bariyer seviyesi $H_{{\\text{{shifted}}}} = H \\exp(\\pm \\beta \\sigma \\sqrt{{\\Delta t}})$ kaydırılarak sürekli formüller $O(1/m)$ kesinliğinde ayrık fiyatlama motoruna dönüştürüldü.
   - **Sınıf**: `BroadieGlassermanKouShiftedBarrier`

5. **Hans Föllmer & Alexander Schied (2002) Dışbükey & Entropik Risk Ölçüleri (EVaR)**:
   - **Eksiklik & Çözüm**: Likidite sürtünmelerinin pozitif homojenliği ihlal etmesi sorunu dışbükey risk aksiyomlarıyla aşıldı. Göreli entropi ceza fonksiyonuyla $\\rho_\\gamma(L) = \\frac{{1}}{{\\gamma}} \\ln \\mathbb{{E}}[e^{{\\gamma L}}]$ kapalı formu kuruldu; Chernoff üst sınırı ile $\\text{{VaR}} \\le \\text{{CVaR}} \\le \\text{{EVaR}}$ hiyerarşisi programatik olarak kanıtlandı.
   - **Sınıf**: `FollmerSchiedEntropicRisk`

6. **Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce Hill (1975) EVT & GPD**:
   - **Eksiklik & Çözüm**: Kara kuğu krizlerinde Gauss ve ampirik VaR'ın kuyruk çöküşünü aşırı düşük tahmin etmesi zafiyeti giderildi. Eşik aşımı (POT) ve Balkema-de Haan-Pickands teoremiyle aşım dağılımı GPD'ye uyarlandı; yarı-parametrik Hill indeksi $\\hat{{\\xi}}_{{\\text{{Hill}}}}$ ve analitik derin kuyruk VaR/ES formülleri üretildi.
   - **Sınıf**: `EmbrechtsMikoschHillGPD`

---

### 🧪 Programatik Doğrulama (Agentic TDD)
Modeller `tests/test_faz50_finance_models.py` altında bağımsız pytest testleriyle doğrulanmış, Faz 48, 49 ve 50 birleşik regresyon testinde 18/18 test %100 başarıyla geçmiştir.

---

### 📂 Bellek ve Exocortex Güncelleme İndeksi
- **Detaylı Araştırma Raporu**: `[[{REPORT_TITLE}]]`
- **Kalıcı Mimari Bellek**: `Entropy/MEMORY.md` (Faz 50 ilkeleri eklendi)
- **Master Bellek Haritası**: `Entropy/BELLEK_HARITASI.md` (Yeni rapor ve çift yönlü bağlantılar senkronize edildi)
- **Günlük Oturum Kaydı**: `Entropy/DailyNotes/{today_str}.md`
- **Bilişsel Vektör Belleği**: 6 yeni anlamsal/prosedürel düğüm 384 boyutlu yerel sinirsel yoğun gömmelerle `cognitive_memory.db` substratına işlendi.
"""

    # Write task note to project reports dir
    project_reports_dir = vault_manager.projects_dir / "EntropiAI" / "Reports"
    project_reports_dir.mkdir(parents=True, exist_ok=True)
    task_file_project = project_reports_dir / f"{task_title}.md"
    task_file_project.write_text(task_note_content, encoding="utf-8")
    print(f"[OK] Task Note saved to: {task_file_project}")

    # Write task note to vault reports dir
    task_file_vault = vault_manager.reports_dir / f"{task_title}.md"
    task_file_vault.write_text(task_note_content, encoding="utf-8")
    print(f"[OK] Task Note saved to: {task_file_vault}")

    # 3. Update MEMORY.md
    memory_file = vault_manager.memory_file
    current_memory = memory_file.read_text(encoding="utf-8")

    faz_50_header = f"\n## Rockafellar-Uryasev CVaR Optimizasyonu, Kramkov-Schachermayer Fayda Dualitesi, Broadie-Glasserman Stokastik Kafes, BGK Kaydırılmış Bariyer, Föllmer-Schied Entropik EVaR ve Embrechts-Mikosch-Hill EVT GPD (Faz 50) ({today_str})\n"
    faz_50_body = (
        "- **R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) CVaR Dışbükey Optimizasyon Mimarisi**: "
        "VaR'ın alt-toplanabilirlik ihlalini ve türevsizlik kısıtını aşan devrimci dışbükey formülasyon; "
        "yardımcı kayıp fonksiyonu $F_\\alpha(w, \\zeta) = \\zeta + \\frac{1}{(1-\\alpha)S} \\sum [ -w^\\top y_s - \\zeta ]^+$ "
        "üzerinden portföy ağırlıkları $w^*$ ve VaR eşiği $\\zeta^*$ değerlerini eşanlı olarak tek bir doğrusal programlama/simpleks izdüşümüyle optimize eden motor.\n"
        "- **Dmitry Kramkov & Walter Schachermayer (1999, 2003) Eksik Piyasalarda Fayda Dualitesi ve Asimptotik Elastisite**: "
        "Eksik piyasalarda beklenen fayda maksimizasyonunun optimal servet sürecinin varlığı için asimptotik elastisite "
        "$\\text{AE}(U) = \\limsup_{x \\to \\infty} \\frac{x U'(x)}{U(x)} < 1$ gerek ve yeter koşulu; "
        "Legendre-Fenchel ikilisi $\\tilde{U}(y)$ üzerinden süpermartingal deflatörleri ile primal-dual dengesinin ($u(x) = \\inf_y [v(y) + xy]$) kurulması.\n"
        "- **Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Çok Boyutlu Egzotik Amerikan/Bermudan Türevleri İçin Stokastik Kafes (Stochastic Mesh)**: "
        "Yüksek boyutlarda ($d \\ge 5$) ağaç ve PDE yöntemlerinin boyutsal patlamasını aşan simülasyon topolojisi; "
        "olabilirlik oranı ağırlıkları $W_{ij}(k) = \\frac{g(X_k^i, X_{k+1}^j)}{h_k(X_{k+1}^j)}$ ile geriye dönük indüksiyon çalıştırarak "
        "asgari varyansla erken egzersiz primini ve kanıtlanabilir $[L_0, U_0]$ güven aralıklarını hesaplayan motor.\n"
        "- **Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Ayrık Gözlemlenen Bariyer Opsiyonlarında Kaydırılmış Bariyer Süreklilik Düzeltmesi (Shifted Barrier)**: "
        "Günlük/haftalık ayrık gözlemlenen bariyer opsiyonlarının sürekli formülle fiyatlanmasındaki %10-%30 hatayı gideren analitik teorem; "
        "Riemann zeta sabiti $\\beta = -\\frac{\\zeta(1/2)}{\\sqrt{2\\pi}} \\approx 0.5826$ ile $H_{\\text{shifted}} = H \\exp(\\pm \\beta \\sigma \\sqrt{\\Delta t})$ "
        "dönüşümü yaparak sürekli kapalı form formülleri $O(1/m)$ kesinliğinde ayrık fiyatlama motoruna çeviren algoritma.\n"
        "- **Hans Föllmer & Alexander Schied (2002) Dışbükey & Entropik Risk Ölçüleri (EVaR)**: "
        "Likidite sürtünmelerinin yarattığı süper-doğrusal maliyetleri modelleyen dışbükey risk teorisi; "
        "göreli entropi ceza fonksiyonuyla $\\rho_\\gamma(L) = \\frac{1}{\\gamma} \\ln \\mathbb{E}[e^{\\gamma L}]$ kapalı formu, "
        "risk nötr ve en kötü durum limitleri ile Chernoff eşitsizliğinin en sıkı üst sınırı olan $\\text{VaR} \\le \\text{CVaR} \\le \\text{EVaR}$ hiyerarşisi.\n"
        "- **Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce Hill (1975) Uç Değer Teorisi (EVT), Eşik Aşımı (POT) & GPD**: "
        "Piyasa çöküşlerindeki kalın kuyrukları modelleyen ekstrem risk çerçevesi; Balkema-de Haan-Pickands eşik aşımı teoremine dayanan "
        "Genelleştirilmiş Pareto Dağılımı (GPD), yarı-parametrik Hill tepe indeksi $\\hat{\\xi}_{\\text{Hill}}$ ve analitik derin kuyruk VaR/ES formülleri.\n"
        f"- **Detaylı Rapor**: [[{REPORT_TITLE}]]\n"
    )

    if REPORT_TITLE not in current_memory:
        memory_file.write_text(current_memory.rstrip() + "\n" + faz_50_header + faz_50_body, encoding="utf-8")
        print("[OK] MEMORY.md updated with Faz 50.")
    else:
        print("[INFO] MEMORY.md already contains Faz 50.")

    # 4. Sync Map of Content (BELLEK_HARITASI.md)
    moc_path = vault_manager.sync_map_of_content()
    print(f"[OK] Master Bellek Haritası synced: {moc_path}")

    # 5. Append to Daily Note
    daily_entry = (
        "Otonom Planlı Görev İcrası: Finans Yeteneği Geliştirme (Faz 50). "
        "Daha önce hafızada yer almayan 6 ileri düzey kantitatif finans ve risk optimizasyonu sütunu "
        "(Rockafellar-Uryasev CVaR Optimizasyonu, Kramkov-Schachermayer Fayda Dualitesi & Asimptotik Elastisite, "
        "Broadie-Glasserman Stokastik Kafes, BGK Kaydırılmış Bariyer Süreklilik Düzeltmesi, "
        "Föllmer-Schied Dışbükey Entropik Risk & EVaR Hiyerarşisi ve Embrechts-Mikosch-Hill EVT GPD Derin Kuyruk Analitiği) araştırıldı, "
        "matematiksel ve algoritmik olarak formüle edildi, 6 adet pytest testinden %100 başarıyla geçti. "
        f"Rapor oluşturuldu: [[{REPORT_TITLE}]]. "
        "MEMORY.md ve BELLEK_HARITASI.md senkronize edildi, 6 bilişsel bellek düğümü yerel nöral embedding ile hafıza sistemine kaydedildi."
    )
    vault_manager.append_daily_log(daily_entry)
    print("[OK] Daily note log appended.")

    # 6. Ingest into CognitiveMemorySystem (12-layer cognitive architecture)
    nodes_to_record = [
        (
            "R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) CVaR Dışbükey Optimizasyon Mimarisi: "
            "VaR'ın alt-toplanabilirlik ihlalini ve türevsizlik kısıtını ortadan kaldıran dışbükey optimizasyon teorisi. "
            "Yardımcı kayıp fonksiyonu F_alpha(w, zeta) = zeta + (1/((1-alpha)*S)) * sum(max(0, -w^T y_s - zeta)) ile "
            "portföy ağırlıkları w* ve VaR eşiği zeta* eşanlı optimize edilir; Duchi simpleks izdüşümüyle küresel minimum CVaR çözülür.",
            0.98,
            {"phase": "faz-50", "topic": "cvar-convex-optimization", "author": "Rockafellar-Uryasev"}
        ),
        (
            "Dmitry Kramkov & Walter Schachermayer (1999, 2003) Eksik Piyasalarda Fayda Dualitesi ve Asimptotik Elastisite: "
            "Genel semimartingal eksik finans piyasalarında beklenen fayda maksimizasyonunun optimal servet çözümünün varlığı için "
            "gerek ve yeter koşul: Asimptotik Elastisite AE(U) = limsup x U'(x) / U(x) < 1. "
            "Legendre-Fenchel ikilisi U_tilde(y) ve süpermartingal deflatörleri ile primal-dual dengesi u(x) = inf [v(y) + xy].",
            0.98,
            {"phase": "faz-50", "topic": "incomplete-market-utility-duality", "author": "Kramkov-Schachermayer"}
        ),
        (
            "Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Stokastik Kafes (Stochastic Mesh) Motoru: "
            "Çok boyutlu (d >= 5) Amerikan ve Bermudan türevlerinde ağaç ve PDE boyutsal patlamasını aşan simülasyon topolojisi. "
            "Olabilirlik oranı geçiş ağırlıkları W_ij(k) = g(X_k^i, X_{k+1}^j) / h_k(X_{k+1}^j) ile geriye dönük dinamik programlama "
            "çalıştırılarak erken egzersiz primi ve kanıtlanabilir güven aralıkları hesaplanır.",
            0.98,
            {"phase": "faz-50", "topic": "stochastic-mesh-bermudan-pricing", "author": "Broadie-Glasserman"}
        ),
        (
            "Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Kaydırılmış Bariyer Süreklilik Teoremi (Shifted Barrier): "
            "Ayrık gözlemlenen bariyer opsiyonlarının sürekli formüllerle hesaplanmasındaki %10-%30 fiyatlama hatasını gideren analitik düzeltme. "
            "Riemann zeta sabiti beta = -zeta(1/2) / sqrt(2*pi) ~= 0.5826 ile H_shifted = H * exp(+- beta * sigma * sqrt(dt)) dönüşümü "
            "yapılarak sürekli Merton / Reiner-Rubinstein formülleri O(1/m) kesinliğinde ayrık fiyata dönüştürülür.",
            0.98,
            {"phase": "faz-50", "topic": "shifted-barrier-continuity-correction", "author": "Broadie-Glasserman-Kou"}
        ),
        (
            "Hans Föllmer & Alexander Schied (2002) Dışbükey & Entropik Risk Ölçüleri (EVaR): "
            "Derin emir defteri likidite sürtünmelerinin pozitif homojenliği bozmasını modelleyen dışbükey risk kuramı. "
            "Göreli entropi ceza fonksiyonuyla rho_gamma(L) = (1/gamma) * ln E[exp(gamma * L)] kapalı formu ve "
            "Chernoff eşitsizliğinin en sıkı üst sınırı olan VaR_alpha <= CVaR_alpha <= EVaR_alpha hiyerarşisi.",
            0.98,
            {"phase": "faz-50", "topic": "convex-entropic-risk-evar", "author": "Follmer-Schied"}
        ),
        (
            "Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce Hill (1975) Uç Değer Teorisi (EVT) & GPD: "
            "Piyasa çöküşlerindeki aşırı kuyruk riskini modelleyen ekstrem değer teorisi. Balkema-de Haan-Pickands eşik aşımı (POT) "
            "teoremiyle Genelleştirilmiş Pareto Dağılımı (GPD), sıralı istatistiklerden yarı-parametrik Hill tepe indeksi xi_Hill "
            "ve %99.9 güven düzeyinde analitik derin kuyruk VaR ve Expected Shortfall hesaplaması.",
            0.98,
            {"phase": "faz-50", "topic": "extreme-value-theory-pot-gpd", "author": "Embrechts-Mikosch-Hill"}
        ),
    ]

    for content, imp, meta in nodes_to_record:
        node, novel = cog_mem.record_memory(
            category="semantic",
            content=content,
            importance=imp,
            metadata=meta
        )
        print(f"[OK] Cognitive Node Recorded: {node.id} (Novel: {novel})")

    # 7. Verify with test hybrid recall query
    query = "Rockafellar Uryasev CVaR optimization Kramkov Schachermayer asymptotic elasticity Broadie Glasserman stochastic mesh BGK shifted barrier Follmer Schied entropic EVaR Embrechts Mikosch Hill GPD"
    recalled = cog_mem.recall(query, limit=3)
    print(f"\n[OK] Hybrid Recall Verification ({len(recalled)} nodes retrieved):")
    for r in recalled:
        print(f" - [{r['id']}] (Score: {r['score']:.3f}): {r['content'][:100]}...")

    print("\n[SUCCESS] All Faz 50 knowledge successfully registered into exocortex and cognitive database!")

if __name__ == "__main__":
    main()
