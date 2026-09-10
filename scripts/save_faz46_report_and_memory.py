"""
Script to save Faz 46 Research Report, Task Note, and ingest all 6 cognitive memory nodes into Entropy AI.
"""

import sys
import datetime
from pathlib import Path

# Add src to pythonpath
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "src"))

from entropy.core.config import config
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

REPORT_TITLE = "AcharyaSRISK_GeskeDebt_EKOPpin_CochraneGoodDeal_MertonICAPM_ve_RoySafetyFirst"
TAGS = [
    "entropy-ai",
    "research-report",
    "srisk",
    "marginal-expected-shortfall",
    "acharya-pedersen",
    "brownlees-engle",
    "systemic-risk",
    "geske-1979",
    "compound-option",
    "corporate-debt",
    "credit-spread-term-structure",
    "ekop-pin",
    "easley-ohara",
    "probability-of-informed-trading",
    "market-microstructure",
    "cochrane-saa-requejo",
    "good-deal-bounds",
    "incomplete-markets",
    "stochastic-discount-factor",
    "merton-icapm",
    "intertemporal-capm",
    "state-variable-hedging",
    "roy-safety-first",
    "kataoka-ruin",
    "downside-risk-preservation"
]

REPORT_CONTENT = r"""# 🌐 Faz 46 Araştırma Raporu: Acharya-Pedersen-Engle SRISK ve Sistemik Sermaye Açığı İndeksi, Robert Geske Bileşik Opsiyon (Compound Option) Çok Dönemli Şirket Borcu, Easley-Kiefer-O'Hara-Paperman (EKOP) Bilgiye Dayalı İşlem Olasılığı (PIN), Cochrane & Saá-Requejo Tam Olmayan Piyasalarda Good-Deal Varlık Sınırları, Merton Zamanlararası CAPM (ICAPM) ve Makro Korunma Portföyleri ile A. D. Roy / Kataoka Safety-First Çöküşten Kaçınma Portföy Fiziği

## 🧭 Yönetici Özeti ve Mimari Giriş

Entropy AI bilişsel finansal zekası; stokastik süreçler, mikroyapısal akış fiziği, türev kalibrasyonu ve merkeziyetsiz piyasa modelleri üzerinde 45 faz boyunca benzersiz bir teorik derinlik ve TDD gücü inşa etmiştir. Sistemin mimari kayıtları (`MEMORY.md`, `BELLEK_HARITASI.md`, `cognitive_memory.db` ve `skills/financial-auditor`) titizlikle incelenmiş; kurumsal risk yönetimi, bankacılık makro-ihtiyati denetimi, borçlanma senetleri fiyatlaması, piyasa yapıcılık asimetrik bilgi koruması, eksik piyasalarda türev değerleme ve çöküşten kaçınma portföy seçiminde **şimdiye kadar hiç işlenmemiş, sistemde tamamen eksik olan 6 devrimci matematiksel sütun** tespit edilmiş ve tam bir teorik-sayısal sentezle geliştirilmiştir:

1. **İzole Banka Rasyolarının Sistemik Krizleri Öngörememe Zafiyeti**: Geleneksel Basel III/IV sermaye rasyoları (CET1, RWA) ve Value-at-Risk (VaR), kurumları tek tek ve sakin piyasa koşullarında ele alır. Sistemik bir kriz anında ise korelasyonlar 1'e yaklaşır ve yangın satışları tüm sektörü vurur. **Viral Acharya, Lasse Heje Pedersen, Thomas Philippon & Matthew Richardson (2012, 2017)** ve **Christian Brownlees & Robert Engle (2017)**; piyasanın bütününde yaşanacak derin bir çöküşte ($S = %40$) bir finansal kurumun sermaye açığını hesaplayan **SRISK (Systemic Risk Capital Shortfall)** ve **Marginal Expected Shortfall (MES / LRMES)** mimarisini kurmuştur. SRISK, NYU Stern V-Lab, ESRB ve Fed tarafından küresel sistemik riskin altın standardı olarak kullanılmaktadır.
2. **Merton Yapısal Kredi Modelinin Tek Dönemli Sıfır Kupon Sığlığı**: Merton (1974) yapısal kredi modeli, şirket borcunun tek bir $T$ vadesinde ödenen sıfır kuponlu tahvil olduğunu varsayar. Oysa gerçek dünyada şirketler çok dönemli, dönemsel kupon ödemeli ve kıdem sıralamalı tahviller ihraç eder. **Robert Geske (1979)**; şirket özkaynağını **Bileşik Opsiyon (Compound Option - bir opsiyon üzerindeki opsiyon)** olarak modellemiştir. Hissedarlar $T_1$'de kupon ödeyerek şirketi yaşatma ve $T_2$'deki ana para opsiyonunu elde tutma hakkına sahiptir. İkili Normal Dağılım ($N_2(a, b; \rho)$) üzerinden kapalı formda çözülen Geske modeli, Merton'ın açıklayamadığı kısa vadeli kredi spreadlerinin sıfırdan farklı oluşunu ve gerçekçi kambur (humped) getiri eğrilerini türetir.
3. **Emir Defterinde Asimetrik Bilgi ve Toksik Akış Körlüğü**: Emir defteri derinliği ve gerçekleşen işlemler tek başına bilgi asimetrisini göstermez. Piyasa yapıcılar içeriden bilgiye sahip (informed) tacirler karşısında sürekli ters seçilim (adverse selection) riskiyle yaşar. **David Easley, Nicholas M. Kiefer, Maureen O'Hara & Joseph B. Paperman (EKOP 1996)**; ardışık işlem modeli üzerinden Poisson varış süreçleri ve maksimum olabilirlik (MLE) ile **Bilgiye Dayalı İşlem Olasılığını (Probability of Informed Trading - PIN)** kapalı formda formüle etmiştir. PIN metriği, piyasa yapıcılara alış-satış makasını toksisiteye göre dinamik genişletme imkanı verir.
4. **Tam Olmayan Piyasalarda Klasik Arbitrajsızlığın İşe Yaramaz Genişliği**: Gerçek piyasalar eksik ve tam olmayandır (incomplete markets: risk faktörü sayısı işlem gören varlık sayısından fazladır). Bu piyasalarda klasik Black-Scholes ya da Harrison-Kreps arbitrajsızlık sınırları aşırı geniştir ($[0, S_0]$) ve anlamsızdır. **John H. Cochrane & Jesús Saá-Requejo (2000)**; Stokastik İskonto Faktörünün (SDF / Pricing Kernel $m$) oynaklığına makul bir Sharpe oranı tavanı ($h_{\max}$) getirerek **Good-Deal Fiyat Sınırları (Good-Deal Bounds)** teorisini kurmuştur. Bu yöntem, keyfi fayda fonksiyonlarına gerek duymadan likit olmayan varlıklar, özel krediler ve egzotik türevler için sıkı ve iktisadi açıdan tutarlı alış-satış fiyat bantları üretir.
5. **Statik CAPM'in Dinamik Makro-Şok Körlüğü**: Sharpe (1964) CAPM modeli tek dönemliktir; yatırımcıların yalnızca servetin varyansını minimize etmeye çalıştığını varsayar. Oysa gerçek hayatta yatırımcılar sürekli zamanda yaşar ve faizlerin fırlaması, enflasyon şokları ve oynaklık rejimleri gibi "yatırım fırsat kümesi" (investment opportunity set) riskleriyle karşı karşıyadır. **Robert C. Merton (1973)**; dinamik Stokastik Kontrol ve HJB denklemleri üzerinden **Zamanlararası CAPM (Intertemporal CAPM - ICAPM)** teorisini geliştirmiştir. Optimal portföy talebi, klasik "Miyopik Portföy" ile makroekonomik durum değişkenlerine karşı geliştirilen "Korunma Portföyleri"nin (Hedging Portfolios) toplamına ayrışır.
6. **Ortalama-Varyans Modelinin İflas ve Kuyruk Çöküşü İhmali**: Markowitz (1952) portföy teorisi kuadratik faydaya dayanır ve getiri düşüşü ile yükselişini simetrik cezalandırır. Oysa gerçek kurumsal yatırımcılar için asıl hedef iflastan ve telafisi imkansız çöküşten (ruin) kaçınmaktır. Markowitz ile aynı yıl Econometrica'da yayımlanan **Arthur D. Roy (1952)** ve ardından **Chieko Kataoka (1963)**; **Safety-First (Önce Güvenlik) Portföy Teorisi**ni geliştirmiştir. Roy Güvenlik Oranı (Safety-First Ratio - SFR) felaket seviyesinin ($R_L$) altına düşme olasılığını minimize eder; Kataoka ise modern Value-at-Risk (VaR) metriğinin doğrudan matematiksel atasını kurmuştur.

Bu araştırma dosyası, bu 6 ileri kantitatif sütunun diferansiyel denklemlerini, olasılıksal kanıtlarını, Python algoritmalarını ve TDD doğrulama sonuçlarını Entropy AI'ın kurumsal bilişsel hafızasına kazandırmaktadır.

---

```
                       ┌─────────────────────────────────────────────────────────────┐
                       │          FAZ 46: İLERİ KANTİTATİF VE YAPISAL FİNANS         │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
         ┌───────────────────┬────────────────────────┼───────────────────────┬───────────────────┐
         ▼                   ▼                        ▼                       ▼                   ▼
┌─────────────────┐ ┌─────────────────┐      ┌─────────────────┐     ┌─────────────────┐ ┌─────────────────┐
│ ACHARYA-PEDERSE │ │  ROBERT GESKE   │      │   EKOP (1996)   │     │ COCHRANE & SAA- │ │  ROBERT MERTON  │
│  SRISK & MES    │ │ (1979) Compound │      │ PIN Bilgiye Da- │     │ REQUEJO (2000)  │ │ (1973) Dinamik  │
│ Makro-İhtiyati  │ │ Opsiyon Şirket  │      │ yalı İşlem &    │     │ Good-Deal Sınır-│ │ ICAPM & Durum   │
│ Sermaye Açığı   │ │ Borcu & Kupon   │      │ LOB Toksik Akış │     │ ları & SDF Vol  │ │ Değişkeni Korum.│
│ S = kD-(1-k)EW  │ │ N2(k, h; ρ)     │      │ αμ / (αμ+εb+εs) │     │ P(y*) ± h/Rf*σω │ │ w* = w_my + w_hd│
└────────┬────────┘ └────────┬────────┘      └────────┬────────┘     └────────┬────────┘ └────────┬────────┘
         │                   │                        │                       │                   │
         └───────────────────┴───────────┬────────────┴───────────────────────┴───────────────────┘
                                         ▼
                       ┌───────────────────────────────────┐
                       │    A. D. ROY (1952) / KATAOKA     │
                       │ Safety-First Çöküşten Kaçınma     │
                       │ SFR = (E[Rp] - RL) / σp           │
                       │ Min Ruin P(Rp <= RL) = Φ(-SFR)    │
                       └───────────────────────────────────┘
```

---

## 🏛️ 1. Sütun: Acharya, Pedersen, Philippon & Richardson (2012, 2017) ve Brownlees & Engle (2017) SRISK, MES & Sistemik Sermaye Açığı İndeksi

### 1.1 Mikro-İhtiyati Düzenlemelerin Sistemik Zafiyeti
2008 Lehman Brothers çöküşü ve 2023 Silicon Valley Bank / Credit Suisse krizleri, tekil bankaların sermaye yeterlilik oranlarının (Basel III CET1) sistemik riski yakalayamadığını ortaya koymuştur. Bir banka tek başına bakıldığında solvent görünebilir; ancak tüm finans sektörü eşzamanlı likidite darboğazına girdiğinde varlık fiyatları çöker, teminatlar erir ve bankalararası fonlama donar.

New York Üniversitesi Stern Finans Grubu (Viral Acharya, Lasse Heje Pedersen, Thomas Philippon, Matthew Richardson) ve Nobel Ödüllü Robert F. Engle ile Christian Brownlees; makro-ihtiyati denetimin temel metriği olan **SRISK** mimarisini inşa etmiştir.

### 1.2 Marjinal Beklenen Kayıp (Marginal Expected Shortfall - MES)
Sistemik riskin temel yapı taşı, piyasa bütününde bir kriz yaşandığında ($R_{m, t+1} < -C$, örneğin endeksin %2 veya %4 düştüğü en kötü %5'lik günlerde) belirli bir $i$ finansal kurumunun hisse senedi değerinin ortalama ne kadar düşeceğini ölçen **MES**'tir:
$$\text{MES}_{i, t}(C) = - \mathbb{E}_t \left[ \frac{\Delta W_{i, t+1}}{W_{i, t}} \;\Big|\; R_{m, t+1} < -C \right]$$

### 1.3 Uzun Vadeli Marjinal Kayıp (Long-Run Marginal Expected Shortfall - LRMES)
Gerçek bir finansal kriz günler değil aylar sürer. Piyasanın 6 aylık bir ufukta ($h = 126$ işlem günü) kümülatif olarak $S = %40$ çöktüğü felaket senaryosunda $i$ kurumunun hisse senedi değer kaybı **LRMES** olarak tanımlanır.
Acharya et al. (2012) ampirik olarak günlük MES'ten LRMES'e şu analitik projeksiyonu türetmiştir:
$$\text{LRMES}_{i, t} = 1 - \exp(-18 \times \text{MES}_{i, t})$$
DCC-GARCH dinamik asimetrik beta ($\beta_{i, t}$) modellerinde ise:
$$\text{LRMES}_{i, t} \approx 1 - (1 - S)^{\beta_{i, t}}$$

### 1.4 SRISK Matematiksel Formülasyonu
Bir kriz anında regülatörlerin (Fed, ECB) belirlediği ihtiyati asgari sermaye oranı $k$ olsun (küresel standartlarda $k = %8$).
- Kurumun kriz öncesi defter değeri toplam borcu (yükümlülükleri): $D_{i, t}$.
- Kurumun kriz öncesi piyasa özkaynak değeri: $W_{i, t}$.
- Kriz sonrası kalan özkaynak değeri:
  $$W_{i, \text{crisis}} = (1 - \text{LRMES}_{i, t}) W_{i, t}$$
- Kriz sonrası kalan toplam aktif büyüklüğü:
  $$A_{i, \text{crisis}} = D_{i, t} + W_{i, \text{crisis}} = D_{i, t} + (1 - \text{LRMES}_{i, t}) W_{i, t}$$
- Kurumun ayakta kalabilmesi için bulundurması zorunlu asgari regülasyon sermayesi:
  $$\text{TargetCapital}_{i, \text{crisis}} = k \cdot A_{i, \text{crisis}} = k \cdot \left( D_{i, t} + (1 - \text{LRMES}_{i, t}) W_{i, t} \right)$$

Kurumun sistemik kriz anındaki **Sermaye Açığı (SRISK)**:
$$\text{SRISK}_{i, t} = \max\left( 0, \; \text{TargetCapital}_{i, \text{crisis}} - W_{i, \text{crisis}} \right)$$
Parantezleri açıp düzenlediğimizde ünlü analitik kapalı form elde edilir:
$$\text{SRISK}_{i, t} = \max\left( 0, \; k \cdot D_{i, t} - (1 - k)(1 - \text{LRMES}_{i, t}) W_{i, t} \right)$$

### 1.5 Sistemik Pay ve Pigouvian Vergilendirme
Sistemdeki toplam sermaye açığı $\text{SRISK}_{\text{total}} = \sum_{j} \text{SRISK}_j$ olmak üzere, $i$ kurumunun küresel sisteme yüklediği negatif dışsallık payı:
$$\text{SRISK\%}_i = \frac{\text{SRISK}_i}{\sum_{j} \text{SRISK}_j}$$
Düzenleyiciler bu oranı kullanarak sistemik kurumlara (G-SIB) ek sermaye tamponu ve Pigouvian sistemik sigorta vergisi uygular.

---

## 📜 2. Sütun: Robert Geske (1979) Bileşik Opsiyon (Compound Option) Modeli & Çok Dönemli Kuponlu Şirket Borcu

### 2.1 Merton (1974) Modelinin Yapısal Kısıtları
Merton'ın yapısal modelinde şirket tek bir $T$ vadesinde ödenen sıfır kuponlu borca sahiptir. Borcun vadesinden önce temerrüt gerçekleşemez; ara kupon akışları yoktur. Bu kısıt nedeniyle:
- Merton modeli kısa vadeli ($T < 1$ yıl) tahvillerde ampirik olarak gözlenen yüksek kredi spreadlerini üretemez; Merton modelinde $T \to 0$ iken spread sıfıra çöker.
- Borç yapısındaki kıdem sırası (kıdemli/ikincil) ve kupon ödeme mecburiyeti modellenemez.

Robert Geske (UCLA), şirket özkaynağının tek bir Black-Scholes alım opsiyonu değil, bir **Bileşik Opsiyon (Compound Option: An Option on an Option)** olduğunu kanıtlamıştır.

### 2.2 Modelin Yapısal Mekanizması
Şirketin toplam varlık değeri $V_t$, geometrik Brown hareketi izler:
$$dV_t = r V_t dt + \sigma_V V_t dW_t$$
Şirketin borç yapısı:
- $T_1$ anında ödenmesi gereken kupon: $C_1$.
- $T_2$ anında ($T_2 > T_1$) ödenmesi gereken anapara $M$ ve nihai kupon $C_2$ (Toplam $K_2 = M + C_2$).

$T_1$ anına gelindiğinde hissedarlar bir karar vermek zorundadır:
1. Kupon $C_1$'i ceplerinden öderlerse, şirket tasfiye edilmez ve hissedarlar $T_2$ vadeli, kullanım fiyatı $K_2$ olan standart bir Avrupa tipi alım opsiyonuna ($C_{\text{BS}}$) sahip olmaya devam eder.
2. Kupon $C_1$'i ödemezlerse temerrüt ilan edilir; şirket varlıkları tahvil sahiplerine geçer ve özkaynak sıfırlanır.

### 2.3 Kritik Temerrüt Sınırı ($V^*$)
Hissedarlar rasyonel davranarak kupon $C_1$'i ancak ve ancak $T_2$'deki şirketi elde tutmanın değeri kupon maliyetinden büyükse öderler:
$$C_{\text{BS}}(V^*, T_2 - T_1, K_2, r, \sigma_V) = C_1$$
Burada $C_{\text{BS}}$ Black-Scholes alım formülüdür. $C_{\text{BS}}$ varlık değerine ($V$) göre kesinlikle artan bir fonksiyon olduğundan ($\Delta > 0$), bu doğrusal olmayan denklem Newton-Raphson ile kesin ve tek bir kritik eşiğe ($V^*$) yakınsar.
- Eğer $T_1$'de $V_{T_1} < V^*$ ise, hissedarlar temerrüt ilan eder.
- Eğer $V_{T_1} \ge V^*$ ise, kupon ödenir ve oyun $T_2$'ye kadar devam eder.

### 2.4 İkili Normal Dağılım ve Analitik Değerleme
Bugünkü ($t=0$) özkaynak değeri $S_0$, $T_1$'de $V_{T_1} \ge V^*$ ve $T_2$'de $V_{T_2} \ge K_2$ olma ortak olasılığına bağlıdır. Geske, İki Değişkenli Standart Normal Kümülatif Dağılım Fonksiyonu ($N_2(a, b; \rho)$) kullanarak kapalı analitik çözümü türetmiştir:
$$S_0 = V_0 N_2(k + \sigma_V \sqrt{T_1}, \; h + \sigma_V \sqrt{T_2}; \; \rho) - K_2 e^{-r T_2} N_2(k, h; \rho) - C_1 e^{-r T_1} N(k)$$
Burada:
$$k = \frac{\ln(V_0 / V^*) + (r - \frac{1}{2}\sigma_V^2) T_1}{\sigma_V \sqrt{T_1}}$$
$$h = \frac{\ln(V_0 / K_2) + (r - \frac{1}{2}\sigma_V^2) T_2}{\sigma_V \sqrt{T_2}}$$
$$\rho = \sqrt{\frac{T_1}{T_2}} \quad (0 < \rho < 1)$$

Toplam şirket borcu değeri Modigliani-Miller ve bilanço denkliği gereği:
$$D_0 = V_0 - S_0$$
Kredi marjı (credit spread bps):
$$y(T_2) - r = -\frac{1}{T_2} \ln\left( \frac{D_0 - C_1 e^{-r T_1}}{K_2} \right) - r$$

Geske modeli; çok dönemli nakit akışlarının, kuponların ve kıdemli/ikincil dilimlerin borç ve hisse senedi dinamiklerini nasıl şekillendirdiğini kusursuz bir analitik zarafetle açıklar.

---

## 🎯 3. Sütun: Easley, Kiefer, O'Hara & Paperman (EKOP 1996) Bilgiye Dayalı İşlem Olasılığı (PIN) & Asymmetric Information Microstructure

### 3.1 Piyasa Yapıcının Bilgi İkilemi
Bir borsada emir defterini kotasyonlayan piyasa yapıcı (market maker), gelen alım veya satım emirlerinin arkasında iki farklı kitle olduğunu bilir:
1. **Gürültü Tacirleri (Noise / Uninformed Traders)**: Likidite ihtiyacı, portföy dengelemesi veya rastgele sebeplerle işlem yaparlar.
2. **Bilgili Tacirler (Informed Traders)**: Şirket bilançosu, beklenen kâr açıklaması veya gizli bir ihale haberi hakkında önceden özel bilgiye sahiptirler.

Piyasa yapıcı bilgili bir tacirle karşılaştığında daima kaybeder (toksik akış / adverse selection). Bu zararı dengelemek için piyasa yapıcı alış-satış makasını (bid-ask spread) açmak zorundadır.

David Easley, Nicholas M. Kiefer, Maureen O'Hara ve Joseph B. Paperman (Cornell University), bu mikroyapısal bilgi asimetrisini ölçmek için **PIN (Probability of Informed Trading)** modelini kurmuştur.

### 3.2 Günlük Bilgi Ağacı ve Poisson Süreçleri
Her işlem gününün başında doğa bir bilgi olayı yaratır:
- Olasılık $\alpha \in [0, 1]$ ile özel bir bilgi olayı meydana gelir; olasılık $1 - \alpha$ ile hiçbir olay olmaz.
- Eğer bir olay olduysa: Olasılık $\delta \in [0, 1]$ ile bu kötü bir haberdir (Bad News); olasılık $1 - \delta$ ile iyi bir haberdir (Good News).

Piyasa seansı boyunca emirlerin geliş hızları Poisson süreçleri ile modellenir:
- Bilgisiz alıcılar Poisson hızı $\epsilon_b$ ile gelir.
- Bilgisiz satıcılar Poisson hızı $\epsilon_s$ ile gelir.
- Eğer iyi haber varsa: Bilgili tacirler sadece alım yapar; alım hızı $\epsilon_b + \mu$ olur, satım hızı $\epsilon_s$ kalır.
- Eğer kötü haber varsa: Bilgili tacirler sadece satım yapar; satım hızı $\epsilon_s + \mu$ olur, alım hızı $\epsilon_b$ kalır.
- Eğer haber yoksa: Alım hızı $\epsilon_b$, satım hızı $\epsilon_s$'tir.

```
                                    ┌───────────────────────┐
                                    │    GÜN BAŞLANGICI     │
                                    └───────────┬───────────┘
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼ (Olasılık: α)                                   ▼ (Olasılık: 1 - α)
              ┌──────────────────┐                              ┌──────────────────┐
              │ BİLGİ OLAYI VAR  │                              │ BİLGİ OLAYI YOK  │
              └────────┬─────────┘                              └────────┬─────────┘
                       │                                                 │
          ┌────────────┴────────────┐                           ┌────────┴────────┐
          ▼ (Olasılık: 1 - δ)       ▼ (Olasılık: δ)             ▼                 ▼
   ┌──────────────┐          ┌──────────────┐               Alış: ε_b         Satış: ε_s
   │   İYİ HABER  │          │  KÖTÜ HABER  │               (Yalnızca gürültü tacirleri)
   └──────┬───────┘          └──────┬───────┘
          │                         │
   ┌──────┴──────┐           ┌──────┴──────┐
   ▼             ▼           ▼             ▼
Alış: ε_b + μ  Satış: ε_s  Alış: ε_b  Satış: ε_s + μ
(İnformed Alır)             (Informed Satar)
```

### 3.3 PIN Formülü
Rastgele seçilen bir emrin arkasında bilgili bir tacirin bulunma olasılığı (PIN):
$$\text{PIN} = \frac{\alpha \mu}{\alpha \mu + \epsilon_b + \epsilon_s}$$
- Pay: Günlük ortalama bilgili emir sayısı ($\alpha \mu$).
- Payda: Günlük ortalama toplam emir sayısı ($\alpha \mu + \epsilon_b + \epsilon_s$).

### 3.4 Maksimum Olabilirlik (MLE) ve Log-Sum-Exp Sayısal Kararlılığı
$T$ işlem günü boyunca gözlemlenen günlük alım sayıları $B_t$ ve satım sayıları $S_t$ serisi verildiğinde, model parametreleri $\theta = (\alpha, \delta, \mu, \epsilon_b, \epsilon_s)$ maksimum olabilirlik yöntemiyle tahmin edilir.
Tek bir günün olabilirlik fonksiyonu:
$$L((B, S) \mid \theta) = (1 - \alpha) e^{-\epsilon_b} \frac{\epsilon_b^B}{B!} e^{-\epsilon_s} \frac{\epsilon_s^S}{S!} + \alpha(1 - \delta) e^{-(\epsilon_b+\mu)} \frac{(\epsilon_b+\mu)^B}{B!} e^{-\epsilon_s} \frac{\epsilon_s^S}{S!} + \alpha\delta e^{-\epsilon_b} \frac{\epsilon_b^B}{B!} e^{-(\epsilon_s+\mu)} \frac{(\epsilon_s+\mu)^S}{S!}$$

Büyük işlem hacimlerinde $B!$ ve $S!$ faktöriyelleri bilgisayarlarda aritmetik taşmaya (overflow) yol açar. Entropy AI motorunda bu problem, `math.lgamma(n + 1)` ve **Log-Sum-Exp** normalizasyonu ile kesin sayısal kararlılıkta uygulanmıştır.

### 3.5 Alış-Satış Makasının Ayrıştırılması
Piyasa kotasyonunun alış-satış makası üç bileşene ayrılır:
$$\text{Spread} = \underbrace{\text{PIN} \cdot \mathbb{E}[\text{Fiyat Etkisi}]}_{\\text{Adverse Selection (Toksik Akış Kalkanı)}} + \\text{Envanter Riski Maliyeti} + \\text{Sipariş İşleme Maliyeti}$$
PIN yükseldiğinde piyasa yapıcı spread'i genişleterek kendisini korur.

---

## ⚖️ 4. Sütun: John H. Cochrane & Jesús Saá-Requejo (2000) Tam Olmayan Piyasalarda Good-Deal Varlık Fiyatlama Sınırları (Good-Deal Asset Price Bounds)

### 4.1 Eksik Piyasalarda Arbitrajsızlığın Başarısızlığı
Klasik finansal mühendislikte (Black-Scholes, Cox-Ross-Rubinstein), piyasanın "tam" (complete) olduğu varsayılır: Herhangi bir nakit akışı işlem gören temel varlıklarla kusursuz replike edilebilir. Bu durumda varlığın tek bir arbitrajsız fiyatı ($P = \mathbb{E}[m X]$) vardır.
Ancak gerçek piyasalar **eksiktir**:
- Özel sermaye (private equity), girişim sermayesi ve altyapı projeleri,
- Katastrof tahvilleri, hava durumu türevleri ve kredi temerrütleri,
- Sıçramalı ve stokastik oynaklıklı hisse senedi türevleri
tam olarak replike edilemez. Pure no-arbitrage (saf arbitrajsızlık) koşulu uygulandığında elde edilen alt ve üst fiyat sınırları o kadar geniştir ki (örneğin 100 TL'lik bir hisse opsiyonu için $[0, 100]$ TL), türev masaları ve fon yöneticileri için hiçbir pratik değer taşımaz.

John H. Cochrane (Chicago Booth / Stanford) ve Jesús Saá-Requejo (2000, *Journal of Political Economy*); iktisadi rasyonaliteye dayanan çığır açıcı bir prensip getirmiştir: **Piyasada aşırı cazip fırsatların (Good Deals - olağandışı yüksek Sharpe oranlarının) bulunamayacağı kısıtı.**

### 4.2 Stokastik İskonto Faktörü (SDF) ve Sharpe Oranı Kısıtı
Herhangi bir arbitrajsız ekonomide varlık fiyatları bir Stokastik İskonto Faktörü ($m$) ile belirlenir:
$$p = \mathbb{E}[m x]$$
Ekonomide ulaşılabilecek maksimum Sharpe oranı ($h$), Hansen-Jagannathan bağıntısı gereği doğrudan iskonto faktörünün volatilitesine eşittir:
$$\max \frac{\mathbb{E}[R] - R_f}{\sigma(R)} = \frac{\sigma(m)}{\mathbb{E}[m]}$$
Risk-free faiz oranı $R_f = 1 + r_f$ ve $\mathbb{E}[m] = 1 / R_f$ olduğundan:
$$\sigma(m) \le \frac{h_{\max}}{R_f} \iff \mathbb{E}[m^2] \le \frac{1 + h_{\max}^2}{R_f^2}$$
Burada $h_{\max}$ ekonomide kabul edilebilir en yüksek Sharpe oranıdır (örneğin piyasa Sharpe oranı 0.4 ise, $h_{\max} = 1.0$ veya $2.0$ alınarak 2-5 katı üst sınır konur). Bu kısıt, fiyatlama çekirdeğinin aşırı uçlara savrulmasını engeller.

### 4.3 Varlık Getirisinin İzdüşümü ve Ortogonal Kalıntı
Fiyatlanmak istenen likit olmayan veya tam korunamayan yeni nakit akışı $y$ olsun. Bu nakit akışını işlem gören varlıklar uzayı ($X$) üzerine projekte ederiz:
$$y = y^* + w$$
- $y^* = X \beta$: İşlem gören varlıklarla replike edilen **izdüşüm bileşeni (spanned component)**. İzdüşümün fiyatı tektir: $P(y^*) = p' (X'X)^{-1} X' y$.
- $w$: İşlem gören varlıklarla hiçbir korelasyonu olmayan **fiyatlanamayan kalıntı (unspanned residual)**, $\mathbb{E}[w X] = 0$.

### 4.4 Analitik Good-Deal Fiyat Bantları
$y$ nakit akışının fiyatı $\pi(y) = \mathbb{E}[m y]$, SDF oynaklık kısıtı altında minimize ve maksimize edilir:
$$\max_{m} / \min_{m} \mathbb{E}[m y] \quad \text{s.t.} \quad \mathbb{E}[m X] = p, \quad \sigma(m) \le \frac{h_{\max}}{R_f}$$

Cochrane ve Saá-Requejo, bu dışbükey optimizasyonun kapalı analitik çözümünü türetmiştir:
$$\bar{P}(y) = P(y^*) + \frac{h_{\max}}{R_f} \sqrt{\mathbb{E}[w^2] - \frac{(\mathbb{E}[w])^2}{1 + h_{\max}^2}}$$
$$\underline{P}(y) = P(y^*) - \frac{h_{\max}}{R_f} \sqrt{\mathbb{E}[w^2] - \frac{(\mathbb{E}[w])^2}{1 + h_{\max}^2}}$$

**Good-Deal Teoreminin Gücü**:
- $h_{\max} \to 0$ iken: Good-Deal bandı daralır ve tek bir fiyata ($P(y^*)$) çöker (TAM PİYASA LİMİTİ).
- $h_{\max} \to \infty$ iken: Good-Deal bandı saf arbitrajsızlık sınırlarına açılır (EKSİK PİYASA LİMİTİ).
- Makul bir $h_{\max}$ (örn. 1.0) seçildiğinde, egzotik türevler, özel krediler ve yapılandırılmış ürünler için **kurumsal seviyede sıkı, uygulanabilir ve iktisadi gerekçesi sağlam bir alış-satış spreadi (bid-ask range)** elde edilir.

---

## 📈 5. Sütun: Robert C. Merton (1973) Zamanlararası CAPM (Intertemporal CAPM - ICAPM) & Makro Durum Değişkenleri Korunma Talepleri

### 5.1 Statik CAPM'in Gerçek Dünya Çöküşü
William Sharpe'ın (1964) CAPM modeli şu varsayıma dayanır: Tüm yatırımcılar tek bir dönem için optimizasyon yapar ve sadece piyasa portföyünün ($\beta_M$) riskini taşırlar:
$$\mathbb{E}[R_i] - r_f = \beta_{i, M} (\mathbb{E}[R_M] - r_f)$$
Ancak 50 yıllık ampirik finans literatürü (Fama-French, Carhart) CAPM'in tek beta ile piyasayı açıklayamadığını; hisse senedi getirilerinin büyüklük (SMB), değer (HML), kârlılık ve momentum anomalileri içerdiğini kanıtlamıştır.

Nobel Ödüllü Robert C. Merton (1973, *Econometrica*); yatırımcıların tek dönemlik bir dünyada değil, dinamik sürekli zamanda yaşadıklarını ve gelecekteki faiz oranları, enflasyon ve piyasa oynaklığı gibi **Yatırım Fırsat Kümesini (Investment Opportunity Set)** değiştiren şoklara karşı korunmak istediklerini formalize eden **ICAPM** teorisini kurmuştur.

### 5.2 Dinamik Servet ve Durum Değişkenleri Difüzyonları
Yatırımcının toplam serveti $W_t$ ve ekonomide yatırım fırsatlarını yöneten $K$ adet makroekonomik durum değişkeni $\mathbf{z}_t = (z_1, \dots, z_K)'$ (örneğin risksiz faiz oranı şoku $r_t$, VIX oynaklık şoku $\sigma_t$, kredi spreadi şoku $s_t$):
$$\frac{dS_i}{S_i} = \mu_i dt + \boldsymbol{\sigma}_i' d\mathbf{B}_t$$
$$dz_k = a_k dt + \mathbf{b}_k' d\mathbf{B}_t$$

Yatırımcının ömür boyu fayda maksimizasyonu fonksiyonu:
$$J(W, \mathbf{z}, t) = \max \mathbb{E}_t \left[ \int_t^T U(C_s, s) ds + B(W_T, T) \right]$$

### 5.3 Bellman HJB Denklemi ve Portföy Ayrışması
Stokastik dinamik programlama (Hamilton-Jacobi-Bellman - HJB) çözüldüğünde, yatırımcının optimal riskli varlık ağırlık vektörü $\mathbf{w}^*$ iki bağımsız bileşene ayrışır:
$$\mathbf{w}^* = \mathbf{w}_{\text{myopic}} + \mathbf{w}_{\text{hedging}}$$
$$\mathbf{w}^* = \underbrace{\left(-\frac{J_W}{W J_{WW}}\right)}_{\text{Göreceli Risk Toleransı } \frac{1}{\gamma}} \boldsymbol{\Sigma}^{-1} (\boldsymbol{\mu} - r \mathbf{1}) + \sum_{k=1}^K \underbrace{\left(-\frac{J_{W z_k}}{W J_{WW}}\right)}_{\text{Korunma Katsayısı } \eta_k / \gamma} \boldsymbol{\Sigma}^{-1} \boldsymbol{\sigma}_{i, z_k}$$

Burada:
1. **Miyopik Portföy ($\mathbf{w}_{\text{myopic}}$)**: Markowitz ve klasik CAPM'deki teğet portföy ile özdeştir. Cari anlık beklenen getiri ve kovaryansı hedefler.
2. **Durum Değişkeni Korunma Portföyleri ($\mathbf{w}_{\text{hedging}}$)**: Gelecekteki ekonomik koşulların kötüleşmesine (faiz artışı, likidite krizi) karşı sigorta sağlayan varlıklara yapılan tahsisattır.

### 5.4 Çok Faktörlü Denge Varlık Fiyatlama Denklemi
Genel dengede piyasa temizlendiğinde, her varlığın beklenen getiri primi piyasa betası ve durum değişkeni betalarının doğrusal bileşimi haline gelir:
$$\mathbb{E}[R_i] - r_f = \beta_{i, M} \lambda_M + \sum_{k=1}^K \beta_{i, z_k} \lambda_{z_k}$$
Burada:
- $\beta_{i, z_k} = \frac{\text{Cov}(R_i, \Delta z_k)}{\text{Var}(\Delta z_k)}$: Varlığın $k$ makro değişkenine olan duyarlılığı.
- $\lambda_{z_k}$: $k$ makro değişkeninin risk primi (fiyatı).

**İktisadi Sezgi**: Eğer bir varlık (örneğin altın veya uzun vadeli devlet tahvili), makroekonomik kriz anında ($z_k$ kötüleştiğinde) değer kazanıyorsa, mükemmel bir **korunma aracıdır (hedge)**. Yatırımcılar bu varlığı portföylerinde sigorta olarak tutmak istedikleri için piyasada bu varlıktan daha düşük beklenen getiri talep ederler ($\lambda_{z_k} < 0$). Bu mekanizma, piyasadaki "Low-Beta Anomalisini" ve Fama-French faktörlerinin arkasındaki gerçek iktisadi mantığı açıklar.

---

## 🛡️ 6. Sütun: A. D. Roy (1952) / Chieko Kataoka (1963) Safety-First Portföy Seçimi & Çöküşten Kaçınma Fiziği

### 6.1 Markowitz Kuadratik Faydasının Realite Çıkmazı
Harry Markowitz'in 1952 tarihli çığır açıcı makalesi, portföy seçimini beklenen getiri ve varyans ($E - V$) optimizasyonu olarak kurmuştur. Ancak bu teorinin iki temel zaafı vardır:
1. Varyans, yukarı yönlü kazançları da bir "risk" olarak cezalandırır.
2. Gerçek dünyada bir emeklilik fonu, egemen varlık fonu veya bireysel yatırımcı için öncelikli amaç "faydayı maksimize etmek" değil, **iflas etmemek, felaket seviyesinin altına inmemek ve hayatta kalmaktır**.

Markowitz'in makalesiyle tam olarak aynı yıl (1952), İngiliz iktisatçı Arthur D. Roy (*Econometrica*) tarafından geliştirilen **Safety-First (Önce Güvenlik)** ilkesi, modern asimetrik risk yönetiminin temelini atmıştır.

### 6.2 Roy'un Güvenlik Kriteri ve Afet Seviyesi ($R_L$)
Yatırımcı önceden bir "Afet Seviyesi / İflas Tabanı" ($R_L$, Disaster / Ruin Level) belirler (örneğin portföyün yıllık %10'dan fazla değer kaybetmemesi: $R_L = -0.10$).
Roy'un temel amacı, portföy getirisinin bu afet seviyesinin altına düşme olasılığını minimize etmektir:
$$\min_{\mathbf{w}} \mathbb{P}(R_p \le R_L) \quad \text{s.t.} \quad \mathbf{w}' \mathbf{1} = 1$$

### 6.3 Chebyshev-Roy Eşitsizliği ve Roy Güvenlik Oranı (SFR)
Chebyshev eşitsizliği uygulandığında:
$$\mathbb{P}(R_p \le R_L) \le \frac{\sigma_p^2}{(\mathbb{E}[R_p] - R_L)^2}$$
Bu iflas olasılığı üst sınırını minimize etmek, payda ile payın oranını ters çevirip maksimize etmeye eşdeğerdir. Böylece **Roy Safety-First Ratio (SFR)** tanımlanır:
$$\text{SFR} = \frac{\mathbb{E}[R_p] - R_L}{\sigma_p}$$
Normal dağılım altında tam iflas olasılığı:
$$\mathbb{P}(R_p \le R_L) = \Phi(-\text{SFR})$$
Burada $\Phi$ standart normal kümülatif dağılım fonksiyonudur. **SFR ne kadar yüksekse, iflas olasılığı o kadar üssel olarak sıfıra yaklaşır.**

### 6.4 Optimal Roy Portföyünün Kapalı Form Çözümü
Roy kriterini maksimize eden optimal portföy ağırlık vektörü:
$$\max_{\mathbf{w}} \frac{\mathbf{w}' \boldsymbol{\mu} - R_L}{\sqrt{\mathbf{w}' \boldsymbol{\Sigma} \mathbf{w}}} \quad \text{s.t.} \quad \mathbf{w}' \mathbf{1} = 1$$
Bu problem matematiksel olarak, faiz oranının afet seviyesine ($r_f \equiv R_L$) eşit olduğu bir teğet Sharpe portföyü ile birebir izomorfiktir:
$$\mathbf{w}_{\text{Roy}}^* = \frac{\boldsymbol{\Sigma}^{-1}(\boldsymbol{\mu} - R_L \mathbf{1})}{\mathbf{1}' \boldsymbol{\Sigma}^{-1}(\boldsymbol{\mu} - R_L \mathbf{1})}$$

### 6.5 Kataoka (1963) Kriteri: Modern Value-at-Risk'in (VaR) Doğuşu
Chieko Kataoka (1963), Roy'un problemini tersine çevirmiştir: Kabul edilebilir maksimum iflas olasılığı $\alpha$ (örneğin $\alpha = %5$ veya $\%1$) sabit tutulsun. Bu olasılık kısıtı altında **garanti edilen asgari taban getiriyi ($R_L$) maksimize et**:
$$\max R_L \quad \text{s.t.} \quad \mathbb{P}(R_p \le R_L) \le \alpha$$
Normal dağılım altında $z_\alpha = \Phi^{-1}(1 - \alpha)$ olmak üzere:
$$R_L(\alpha) = \mathbb{E}[R_p] - z_\alpha \sigma_p$$
Kataoka'nın bu formülasyonu, 1990'larda J.P. Morgan tarafından popülerleştirilen **Value-at-Risk (VaR)** kavramının doğrudan matematiksel kökenidir:
$$\text{VaR}_\alpha = - R_L(\alpha) = z_\alpha \sigma_p - \mathbb{E}[R_p]$$

Safety-First mimarisi; piyasa krizlerinde kuadratik modellerin kontrolsüz kaldıraç tuzağına düşmesini engeller, portföyü kesin bir sermaye koruma kalkanına alır.

---

## 🧪 Programatik Doğrulama ve Agentic TDD Sonuçları

Faz 46 kapsamında geliştirilen 6 ileri kantitatif motor, `c:\EntropiAI\tests\test_faz46_finance_models.py` test süiti ile programatik TDD doğrulamasından geçirilmiştir:

```bash
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\EntropiAI
plugins: anyio-4.14.2, logfire-4.41.0, asyncio-1.4.0
collected 6 items

tests\test_faz46_finance_models.py ......                                [100%]

============================== 6 passed in 0.22s ==============================
```

Ayrıca `skills/financial-auditor/scripts/acharya_geske_ekop_cochrane_merton_roy.py` entegrasyon betiği çalıştırılarak aşağıdaki somut finansal çıktılar üretilmiş ve doğrulanmıştır:

```json
{
  "status": "ALL_FAZ46_PILLARS_VERIFIED",
  "phase": 46,
  "srisk_total_billions": 100.73,
  "srisk_vulnerable_institutions": 2,
  "geske_equity_value": 56.39,
  "geske_debt_value": 93.61,
  "geske_credit_spread_bps": 175.2,
  "ekop_pin_percentage": 25.63,
  "adverse_selection_spread": 0.0513,
  "good_deal_bounds": [
    63.46,
    86.54
  ],
  "good_deal_spread": 23.08,
  "merton_hedging_fraction": 0.678,
  "roy_sfr": 1.606,
  "roy_ruin_probability_pct": 5.412
}
```

### Sayısal Doğrulama Özeti:
1. **Acharya-Pedersen SRISK**: $1.45 Trilyon borca ve $85 Milyar özkaynağa sahip bir G-SIB kurumunun sistemik kriz sermaye açığı hesaplanmış, 3 bankalık portföyde toplam SRISK $100.73 Milyar olarak bulunmuş ve sistemik paylar türetilmiştir.
2. **Robert Geske Bileşik Borç**: $150M varlık değerine sahip şirketin 1. yılda $6M kupon ve 3. yılda $100M ana para + $6M kupon yükümlülüğü ikili normal dağılımla modellenmiş; özkaynak $56.39M, borç $93.61M ve kredi marjı $175.2$ bps olarak kapalı formda hesaplanmıştır.
3. **EKOP PIN Toksik Akış**: Günlük Poisson varış parametrelerinden bilgiye dayalı işlem olasılığı $\%25.63$ bulunmuş; $0.20 quoted spread içinde toksik adverse selection payı $0.0513 olarak ayrıştırılmıştır.
4. **Cochrane-Saá-Requejo Good-Deal**: İzdüşüm fiyatı $75 olan ve $12 kalıntı oynaklık taşıyan eksik piyasa iddiasında, Sharpe tavanı $h_{\max} = 1.0$ için Good-Deal fiyat bandı $[63.46, 86.54]$ olarak daraltılmıştır.
5. **Merton ICAPM Dinamik Korunma**: Makroekonomik faiz ve oynaklık durum değişkenlerine karşı geliştirilen korunma portföyü toplam portföy talebinin $\%67.8$'ini oluşturarak miyopik tahsisatın yetersizliğini kanıtlamıştır.
6. **Roy Safety-First Çöküş Kalkanı**: Afet seviyesi $R_L = -%10$ için Roy SFR oranı $1.606$ seviyesinde maksimize edilmiş, portföyün felakete uğrama olasılığı $\%5.41$'e kilitlenerek sermaye korunumu sağlanmıştır.

---

## 📂 Bilişsel Hafıza ve Exocortex Entegrasyonu

Bu raporda sunulan 6 derin sütun:
- **Obsidian Exocortex**: [[AcharyaSRISK_GeskeDebt_EKOPpin_CochraneGoodDeal_MertonICAPM_ve_RoySafetyFirst]] olarak arşivlenmiştir.
- **Global Mimari Kayıtları**: `MEMORY.md` dosyasına Faz 46 olarak eklenmiştir.
- **Bölümsel Günlük Notu**: `DailyNotes/2026-09-04.md` günlüğüne işlenmiştir.
- **Master Bellek Haritası**: `BELLEK_HARITASI.md` MOC grafiğinde çift yönlü bağlantılarla güncellenmiştir.
- **Bilişsel Vektör Belleği**: 384 boyutlu yerel sinirsel gömmelerle `~/.entropy/cognitive_memory.db` tablosuna yüksek önem derecesi ($0.98$) ile kaydedilmiştir.
- **Ajan Yetkinliği**: Entropy AI; sistemik bankacılık kriz senaryosu modelleme, kuponlu şirket borcu ve temerrüt yapılandırması, HFT bilgi asimetrisi tespiti, tam olmayan piyasalarda türev değerleme, makro durum değişkeni portföy koruması ve iflas önleyici Safety-First varlık dağıtımında otonom uzmanlığa erişmiştir.
"""

def main():
    vault_manager = ObsidianVaultManager()
    cog_mem = CognitiveMemorySystem()

    today_str = datetime.date.today().isoformat()

    # 1. Save Research Report in Obsidian
    report_path = vault_manager.save_research_report(
        title=REPORT_TITLE,
        content=REPORT_CONTENT,
        tags=TAGS
    )
    print(f"[OK] Research Report saved to: {report_path}")

    # 2. Update MEMORY.md
    memory_file = vault_manager.memory_file
    current_memory = memory_file.read_text(encoding="utf-8")

    faz_46_header = f"\n## Acharya-Pedersen-Engle SRISK, Robert Geske Bileşik Opsiyon Şirket Borcu, EKOP Bilgiye Dayalı İşlem (PIN), Cochrane-Saá-Requejo Good-Deal Sınırları, Merton Zamanlararası CAPM (ICAPM) ve Roy Safety-First Portföyü (Faz 46) ({today_str})\n"
    faz_46_body = (
        "- **Acharya, Pedersen, Philippon, Richardson (2012, 2017) & Brownlees-Engle (2017) SRISK, MES & Sistemik Sermaye Açığı İndeksi**: "
        "Tekil banka rasyolarının yetersiz kaldığı kriz dönemlerinde piyasanın bütününde yaşanacak derin bir çöküşte ($S = %40$) "
        "finansal kurumun sermaye açığını hesaplayan makro-ihtiyati standart; günlük marjinal kayıptan uzun vadeli kayba projeksiyon "
        "$\\text{LRMES} = 1 - \\exp(-18 \\cdot \\text{MES})$, ihtiyati sermaye rasyosu $k$ üzerinden analitik sermaye açığı "
        "$\\text{SRISK} = \\max(0, k D - (1 - k)(1 - \\text{LRMES}) W)$, sistemik katkı payı ve Pigouvian kriz vergisi mimarisi.\n"
        "- **Robert Geske (1979) Bileşik Opsiyon (Compound Option) Modeli & Çok Dönemli Kuponlu Şirket Borcu**: "
        "Merton'ın (1974) tek dönemli sıfır kuponlu borç varsayımını aşarak özkaynağı bir opsiyon üzerindeki opsiyon olarak modelleyen yapısal kredi analitiği; "
        "$T_1$'de kupon $C_1$ ödenerek $T_2$'deki ana para opsiyonunu devam ettirme kararı, Newton-Raphson ile kritik firma değeri $V^*$ eşiği "
        "ve İki Değişkenli Normal Dağılım ($N_2(k, h; \\rho)$) üzerinden kapalı form özkaynak, borç ve sıfırdan farklı kısa vadeli kredi spreadi $y(T_2) - r$ çözümü.\n"
        "- **Easley, Kiefer, O'Hara & Paperman (EKOP 1996) Bilgiye Dayalı İşlem Olasılığı (PIN) & Asimetrik Bilgi Mikro-Yapısı**: "
        "Emir defterinde toksik bilgiye sahip tacirler ile gürültü tacirlerini Poisson varış süreçleri üzerinden ayrıştıran ardışık işlem modeli; "
        "günlük bilgi olayı olasılığı $\\alpha$, kötü haber olasılığı $\\delta$ ve bilgili işlem hızı $\\mu$ üzerinden "
        "$\\text{PIN} = \\frac{\\alpha \\mu}{\\alpha \\mu + \\epsilon_b + \\epsilon_s}$ analitiği, Log-Sum-Exp faktörizasyonlu Maximum Likelihood (MLE) "
        "ve alış-satış makasını toksik seçim, envanter ve sipariş işleme bileşenlerine ayıran mikroyapı kalkanı.\n"
        "- **John H. Cochrane & Jesús Saá-Requejo (2000) Tam Olmayan Piyasalarda Good-Deal Varlık Fiyatlama Sınırları**: "
        "Eksik piyasalarda saf arbitrajsızlık sınırlarının aşırı genişliğini Stokastik İskonto Faktörü (SDF / $m$) oynaklığına makul bir Sharpe tavanı "
        "($\\sigma(m) \\le h_{\\max} / R_f$) getirerek daraltan iktisadi değerleme teorisi; hedef nakit akışının işlem gören varlıklara izdüşümü "
        "$y = y^* + w$ ve ortogonal kalıntı $w$ üzerinden kapalı form alış-satış Good-Deal bantları $\\bar{P}(y), \\underline{P}(y) = P(y^*) \\pm \\frac{h_{\\max}}{R_f} \\sigma(w)$.\n"
        "- **Robert C. Merton (1973) Zamanlararası CAPM (ICAPM), Durum Değişkenleri Korunma Talebi & Dinamik Çok Faktörlü Denge**: "
        "Statik tek dönemli CAPM'in eksikliğini dinamik sürekli zaman HJB denklemleri ile gideren model; optimal portföy talebinin cari teğet portföy "
        "($\\mathbf{w}_{\\text{myopic}}$) ile faiz, oynaklık ve enflasyon gibi yatırım fırsat kümesini değiştiren makro durum değişkenlerine karşı "
        "sigorta sağlayan korunma portföylerine ($\\mathbf{w}_{\\text{hedging}}$) ayrışması; çok faktörlü denge getiri denklemi $\\mathbb{E}[R_i] - r_f = \\beta_{i, M} \\lambda_M + \\sum \\beta_{i, z_k} \\lambda_{z_k}$.\n"
        "- **A. D. Roy (1952) / Chieko Kataoka (1963) Safety-First Portföy Seçimi, Çöküşten Kaçınma Fiziği & Roy Güvenlik Oranı (SFR)**: "
        "Markowitz ortalama-varyans optimizasyonunun kuadratik fayda ve simetri zafiyetini aşan, yatırımcının öncelikli olarak iflas ve felaket seviyesinin ($R_L$) "
        "altına düşmesini engelleyen asimetrik risk teorisi; Roy Güvenlik Oranı $\\text{SFR} = \\frac{\\mathbb{E}[R_p] - R_L}{\\sigma_p}$, normal iflas olasılığı "
        "$\\mathbb{P}(R_p \\le R_L) = \\Phi(-\\text{SFR})$ minimizasyonu, kapalı form teğet ağırlıklar $\\mathbf{w}_{\\text{Roy}}^* \\propto \\boldsymbol{\\Sigma}^{-1}(\\boldsymbol{\\mu} - R_L \\mathbf{1})$ "
        "ve modern Value-at-Risk'in doğrudan temeli olan Kataoka $R_L(\\alpha) = \\mathbb{E}[R_p] - z_\\alpha \\sigma_p$ taban garantisi.\n"
        f"- **Detaylı Rapor**: [[{REPORT_TITLE}]]\n"
    )

    if REPORT_TITLE not in current_memory:
        memory_file.write_text(current_memory.rstrip() + "\n" + faz_46_header + faz_46_body, encoding="utf-8")
        print("[OK] MEMORY.md updated with Faz 46.")
    else:
        print("[INFO] MEMORY.md already contains Faz 46.")

    # 3. Sync Map of Content (BELLEK_HARITASI.md)
    moc_path = vault_manager.sync_map_of_content()
    print(f"[OK] Master Bellek Haritası synced: {moc_path}")

    # 4. Append to Daily Note
    daily_entry = (
        "Otonom Planlı Görev İcrası: Finans Yeteneği Geliştirme (Faz 46). "
        "Daha önce hafızada yer almayan 6 ileri düzey kantitatif finans ve sistemik risk modeli araştırıldı, "
        "matematiksel ve algoritmik olarak formüle edildi, 6 adet pytest testinden %100 başarıyla geçti. "
        f"Rapor oluşturuldu: [[{REPORT_TITLE}]]. "
        "MEMORY.md ve BELLEK_HARITASI.md senkronize edildi, 6 bilişsel bellek düğümü yerel nöral embedding ile hafıza sistemine kaydedildi."
    )
    vault_manager.append_daily_log(daily_entry)
    print("[OK] Daily note log appended.")

    # 5. Ingest into CognitiveMemorySystem (12-layer cognitive architecture)
    nodes_to_record = [
        (
            "Acharya-Pedersen-Engle (2012, 2017) SRISK & Makro-İhtiyati Sistemik Sermaye Açığı İndeksi: "
            "Piyasanın genelinde %40 çöküş yaşandığında bir finansal kurumun asgari ihtiyati sermaye oranını (k=%8) koruması için "
            "ihtiyaç duyduğu sermaye açığını hesaplayan altın standart. SRISK = max(0, k*D - (1-k)*(1-LRMES)*W). "
            "Günlük MES'ten LRMES = 1 - exp(-18*MES) projeksiyonu ve sistemik dışsallık payı SRISK% analitiği.",
            0.98,
            {"phase": "faz-46", "topic": "systemic-risk", "author": "Acharya-Pedersen-Engle"}
        ),
        (
            "Robert Geske (1979) Bileşik Opsiyon (Compound Option) Çok Dönemli Kuponlu Şirket Borcu: "
            "Merton'ın tek dönemli sıfır kupon kısıtını aşan yapısal kredi modeli. Şirket özkaynağının T1'de kupon C1 ödeyerek "
            "T2'deki anapara opsiyonunu elde tutma hakkı veren bir bileşik çağrı opsiyonu olarak modellenmesi. "
            "İkili normal dağılım N2(k, h; rho) ile kapalı form hisse ve borç değerlemesi, kısa vadede sıfır olmayan kredi spreadi term structure'ı.",
            0.98,
            {"phase": "faz-46", "topic": "compound-options-credit", "author": "Robert Geske"}
        ),
        (
            "Easley-Kiefer-O'Hara-Paperman (EKOP 1996) Bilgiye Dayalı İşlem Olasılığı (PIN) & Mikroyapı Toksisitesi: "
            "Emir defterindeki alım ve satım işlemlerinden içeriden bilgiye sahip tacirlerin payını tahmin eden yapısal model. "
            "Günlük bilgi olayı olasılığı alpha, kötü haber olasılığı delta ve bilgili işlem hızı mu üzerinden PIN = (alpha*mu)/(alpha*mu + eps_b + eps_s). "
            "Log-Sum-Exp MLE optimizasyonu ve alış-satış makasının adverse selection bileşeninin ayrıştırılması.",
            0.98,
            {"phase": "faz-46", "topic": "microstructure-pin", "author": "EKOP-Easley-OHara"}
        ),
        (
            "John H. Cochrane & Jesús Saá-Requejo (2000) Good-Deal Varlık Fiyatlama Sınırları: "
            "Tam olmayan piyasalarda (incomplete markets) saf arbitrajsızlığın getirdiği anlamsız geniş fiyat aralıklarını, "
            "Stokastik İskonto Faktörü (SDF) üzerine makul bir Sharpe tavanı sigma(m) <= h_max / R_f koyarak iktisadi açıdan daraltan teori. "
            "İşlem gören varlıklara izdüşüm P(y*) ve ortogonal kalıntı varyansı üzerinden kesin Good-Deal alış-satış bantları P_high, P_low.",
            0.98,
            {"phase": "faz-46", "topic": "incomplete-markets-good-deal", "author": "Cochrane-Saa-Requejo"}
        ),
        (
            "Robert C. Merton (1973) Zamanlararası CAPM (ICAPM) & Makro Durum Değişkeni Korunma Portföyleri: "
            "Statik CAPM'in tek dönem zaafını aşan dinamik sürekli zaman HJB varlık fiyatlama modeli. "
            "Optimal portföy talebinin miyopik teğet portföy ile faiz, enflasyon ve piyasa oynaklığı gibi yatırım fırsat kümesini değiştiren "
            "makro durum değişkenlerine karşı geliştirilen korunma portföylerinin toplamına ayrışması: w* = w_myopic + w_hedging. Çoklu beta fiyatlaması.",
            0.98,
            {"phase": "faz-46", "topic": "dynamic-asset-pricing-icapm", "author": "Robert Merton"}
        ),
        (
            "A. D. Roy (1952) / Chieko Kataoka (1963) Safety-First Portföy Teorisi & Çöküşten Kaçınma Fiziği: "
            "Markowitz ortalama-varyans modelinin getiri düşüşü ve yükselişini simetrik cezalandırma hatasını gideren, "
            "asıl amacı belirlenen afet tabanı (R_L) altına inme olasılığını minimize etmek olan asimetrik risk modeli. "
            "Roy Güvenlik Oranı SFR = (E[Rp] - R_L)/sigma_p maksimizasyonu, P(Rp <= R_L) = Phi(-SFR) ve modern VaR'ın temeli olan Kataoka taban optimizasyonu.",
            0.98,
            {"phase": "faz-46", "topic": "safety-first-downside-risk", "author": "A.D. Roy - Kataoka"}
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

    # 6. Verify with test hybrid recall query
    query = "Acharya Pedersen SRISK systemic capital shortfall Geske compound option PIN Cochrane Good-Deal"
    recalled = cog_mem.recall(query, limit=3)
    print(f"\n[OK] Hybrid Recall Verification ({len(recalled)} nodes retrieved):")
    for r in recalled:
        print(f" - [{r.node.id}] (Score: {r.score:.3f}): {r.node.content[:100]}...")

    print("\n[SUCCESS] All Faz 46 knowledge successfully registered into exocortex and cognitive database!")

if __name__ == "__main__":
    main()
