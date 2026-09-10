---
title: "Bilgi Edinme Dengesi ve Piyasa Fiyat Keşfi"
subtitle: "Grossman-Stiglitz (1980) Paradoksu ve Hasbrouck (1991, 1995) Bilgi Paylaşımı (IS / GIS)"
author: "Entropy AI"
date: "2026-09-06"
theme: gaia
paginate: true
math: katex
---

# Bilgi Edinme Dengesi ve Piyasa Fiyat Keşfi

### Grossman-Stiglitz (1980) Paradoksu ve Hasbrouck (1991, 1995) Bilgi Paylaşımı (IS / GIS)

**Sunum:** Entropy AI  
**Kurum:** Kantitatif Finans ve Piyasa Mikroyapısı Araştırma Grubu  
**Tarih:** 2026-09-06  

<!--
🎙️ Notlar: Bu seminerde modern finansal mikroyapının iki temel köşe taşını inceliyoruz: Bilgi edinmenin içsel dengesi ve parçalanmış piyasalarda fiyat keşfinin ekonometrik ayrıştırması.
-->


---

## 1. Grossman-Stiglitz (1980) Paradoksu: Giriş

*Etkin Piyasalar Hipotezinin (EMH) İçsel Çelişkisi*

- **Temel Teorem:** Bilgi edinme maliyeti sıfırdan büyük ($c > 0$) olduğunda, tam bilgi etkinliğine sahip bir piyasanın var olması imkansızdır.
- **Mantıksal Kısır Döngü:** Eğer piyasa fiyatı $P$ tüm özel bilgiyi ($\theta$) kusursuzca yansıtıyorsa, hiçbir rasyonel aktör pozitif kaynak ($c > 0$) harcayarak bilgi toplamaz.
- **Piyasanın Çöküşü:** Ancak kimse bilgi toplamazsa, fiyat $P$ hiçbir özel bilgiyi yansıtamaz ve piyasa tamamen bilgisiz kalır.
- **Çözüm Yolu:** Fiyattaki gürültü (Noise Traders / Likidite Şoku) sayesinde bilgi kısmen gizlenir ve dengede pozitif oranda bilgili tüccar ($\lambda^*$) hayatta kalır.

> [!NOTE]
> Eğer piyasalar Fama anlamında güçlü formda etkin olsaydı, bilgiye yatırım yapan tüm analistler ve fonlar iflas ederdi.


<!--
🎙️ Notlar: Sanford Grossman ve Joseph Stiglitz 1980 AER makalelerinde EMH'nin kalbine matematiksel bir hançer saplamıştır: Bilgi bedava değilse piyasa asla tam etkin olamaz.
-->


---

## 2. Grossman-Stiglitz Denge Denklemi

$$
\frac{\text{Var}(\theta \mid \text{uninformed})}{\text{Var}(\theta \mid \text{informed})} = e^{2ac}
$$

- **$a$:** Negatif üstel CARA fayda fonksiyonundaki mutlak riskten kaçınma katsayısı ($U(W) = -e^{-aW}$).
- **$c > 0$:** Özel bilgi sinyali $y = \theta + \epsilon$ toplamanın katlanılan parasal maliyeti.
- **$\text{Var}(\theta \mid \text{informed})$:** Bilgili tüccarın sinyal sonrası nihai değer $\theta$ üzerindeki koşullu varyansı.
- **$\text{Var}(\theta \mid \text{uninformed})$:** Bilgisiz tüccarın yalnızca piyasa fiyatını gözlemleyerek ulaştığı koşullu varyans.
- **İçsel Denge Oranı ($\lambda^*$):** Bilgili tüccar oranı $\lambda \in (0, 1)$ endojen olarak belirlenir.
- **Eksik Fiyat Bilgilendiriciliği:** Fiyat bilgilendiriciliği $\rho^2 = \text{Corr}(P, \theta)^2 < 1$ olmak zorundadır. Piyasada her zaman gürültü tüccarı arzı $x \sim \mathcal{N}(0, \sigma_x^2)$ bulunmalıdır.

> [!NOTE]
> Varyans oranı tam olarak e^(2ac) katına ulaştığında, bilgili ve bilgisiz tüccarların beklenen faydaları eşitlenir.


<!--
🎙️ Notlar: Formülde görüldüğü üzere maliyet c arttıkça veya riskten kaçınma a yükseldikçe, bilgisizlerin katlandığı belirsizlik katlanarak artar.
-->


---

## 3. Grossman-Stiglitz Denge Mekaniği

### Bilgili Tüccarlar (Informed, λ*)
- Özel sinyali $y = \theta + \epsilon$ gözlemler.
- Kişi başı sabit $c > 0$ araştırma maliyetine katlanır.
- Talep fonksiyonu: $X_I(P, y) = \frac{E[\theta \mid y] - P}{a \cdot \text{Var}(\theta \mid y)}$.
- Fiyat üzerindeki bilgi baskısını oluşturur.

### Bilgisiz Tüccarlar (Uninformed, 1 - λ*)
- Yalnızca piyasa denge fiyatı $P$'yi gözlemler.
- Sıfır araştırma maliyetiyle piyasada işlem yapar.
- Talebi fiyattan sinyal türetir: $E[\theta \mid P]$.
- Gürültü tüccarı arzı $x$'i tam ayırt edemez (Sinyal/Gürültü Ayrımı).

> [!TIP]
> Denge ancak $\lambda^* \in (0, 1)$ aralığında var olabilir. $\lambda=0$ da $\lambda=1$ de kararsızdır.


<!--
🎙️ Notlar: Bilgisiz tüccarlar fiyatı gözlemleyerek bedavacılık (free-riding) yapmaya çalışır. Ancak gürültü tüccarları piyasada olmasaydı fiyat bilgiyi %100 açığa vurur ve bedavacılık sistemi yok ederdi.
-->


---

## 4. Joel Hasbrouck (1991, 1995): Fiyat Keşfi & Cointegrated VAR

*Parçalanmış Elektronik Piyasalarda Fiyat Liderliğinin Ölçülmesi*

- **Problem:** Aynı finansal varlık (hisse senedi, tahvil, Bitcoin) birden fazla borsada (NYSE vs NASDAQ, Binance vs Coinbase) eşzamanlı işlem görmektedir.
- **Tek Fiyat Kanunu & Eşbütünleşme:** Arbitraj sayesinde fiyatlar uzun vadede birlikte hareket eder: Fiyat serileri $p_t = [p_{1,t}, p_{2,t}, \dots, p_{n,t}]'$ **$I(1)$ eşbütünleşiktir**.
- **Beveridge-Nelson Ayrıştırması:** Fiyat vektörü iki bileşene ayrılır: Kalıcı ortak rassal yürüyüş (Martingale / İçsel Değer $m_t$) ve geçici mikroyapı gürültüsü ($s_t$).
- **Soru:** Ortak içsel değer yeniliği $\epsilon_t$'ye hangi borsa yön vermektedir?

> [!NOTE]
> Hasbrouck Bilgi Paylaşımı (Information Share - IS), fiyat keşfinin tam coğrafi konumunu milisaniye seviyesinde tespit eder.


<!--
🎙️ Notlar: Hasbrouck 1995 JOF makalesiyle finansal ekonometriye muazzam bir araç kazandırdı: Vektör Hata Düzeltme Modeli (VECM) üzerinden bilgi payı hesaplama.
-->


---

## 5. Hasbrouck Beveridge-Nelson & VECM Ayrıştırması

$$
p_t = \iota m_t + s_t, \quad m_t = m_{t-1} + \psi \epsilon_t
$$

- **$p_t$:** $n$ adet farklı borsadaki kotasyon fiyat vektörü.
- **$m_t$:** Ortak kalıcı martingale içsel değer bileşeni ($m_t = m_{t-1} + \psi \epsilon_t$).
- **$s_t$:** Sıfır ortalamalı durağan mikroyapı gürültüsü (Bid-Ask bounce, likidite şokları).
- **$\psi$:** VECM hareketli ortalama (Wold MA) uzun dönem etki vektörü ($[\psi_1, \psi_2, \dots, \psi_n]$).
- **$\epsilon_t$:** Yenilik vektörü, kovaryans matrisi $\Omega = E[\epsilon_t \epsilon_t']$.
- Eşbütünleşme vektörü gereği $\psi$ vektörünün satırları birbirine özdeştir: $\psi = \iota \beta'$.
- Kalıcı varyans: $\sigma_m^2 = \psi \Omega \psi'$ formülüyle hesaplanır.

> [!NOTE]
> Tüm piyasalar aynı uzun vadeli içsel değere bağlıdır; ancak bu değere ilk tepki veren borsa liderdir.


<!--
🎙️ Notlar: Burada psi vektörü hangi piyasanın yeniliklerinin kalıcı fiyata geçtiğini gösterir. Eğer psi_1 büyükse 1. borsa fiyatı yönlendiriyor demektir.
-->


---

## 6. Cholesky Ayrışımı & Hasbrouck Information Share (IS)

*Yenilik Korelasyonu ve Sıralama Bağımlılığı Çözümü*

### Cholesky Faktörizasyonu & IS Formülü
- Kovaryans matrisi alt üçgensel faktörlere ayrılır:
- $$\Omega = F F'$$
- $j$. piyasanın Bilgi Paylaşımı (Information Share):
- $$IS_j = \frac{([\psi F]_j)^2}{\psi \Omega \psi'}$$
- Payların toplamı bire eşittir: $\sum_{j=1}^n IS_j = 1$.

### Ekonometrik Sınırlar & Ortak Bilgi Payı (GIS)
- **Sıralama Bağımlılığı:** $\Omega$ köşegen değilse (borsalar arası korelasyon $\rho \neq 0$), Cholesky sıralaması üst ve alt sınırlar ($IS_j^{\max}, IS_j^{\min}$) üretir.
- İlk sıradaki borsa en yüksek korelasyon payını alır.
- **Çözüm (Midpoint / GIS):**
- $$IS_j^{\text{mid}} = \frac{IS_j^{\max} + IS_j^{\min}}{2}$$
- Lien-Shrestha (2009) Generalized IS (GIS) ile özdeğer tabanlı sıralamadan bağımsız metrik elde edilir.

> [!TIP]
> Kripto para piyasalarında Binance ve Coinbase arasındaki fiyat keşfi liderliği bu metodolojiyle ölçülmektedir.


<!--
🎙️ Notlar: Cholesky matrisinde birinci sıraya koyduğunuz borsa korelasyondan aslan payını alır. Bu yüzden akademik standart alt ve üst sınırları hesaplayıp ortalamasını almaktır.
-->


---

## 7. İki Teorinin Birleşik Piyasa Mimarisi

*Grossman-Stiglitz Paradoksu ➔ Hasbrouck Fiyat Keşfi Köprüsü*

### Bilgi Edinme Düzeyi (Grossman-Stiglitz)
- **Neden Bilgi Toplanır?** Bilgili tüccarlar beklenen kâr elde etmek için araştırma yapar ($c > 0$).
- **Fiyatın Rolü:** Bilgiyi agregasyonla piyasaya taşır ancak asla tam etkin olamaz ($\rho^2 < 1$).
- **Gürültü Şartı:** Likidite tüccarları olmasa piyasa likiditesi tamamen kurur (No-Trade Theorem).

### Emir Akışı & Uygulama (Hasbrouck)
- **Bilgi Nerede Fiyata Dönüşür?** Bilgili tüccarların girdiği limit ve piyasa emirlerinde (Order Flow Informativeness).
- **Fiyat Keşfi Konumu:** En derin likiditeye ve en düşük gecikmeye (latency) sahip borsa en yüksek $IS_j$ payını alır.
- **Kalıcı Etki:** Bilgili emir akışı kalıcı fiyat şokuna ($\psi \epsilon_t$) dönüşür.

> [!TIP]
> Grossman-Stiglitz bilginin piyasaya NEDEN girdiğini, Hasbrouck ise bu bilginin NEREDE fiyata dönüştüğünü kanıtlar.


<!--
🎙️ Notlar: Bu iki teori bir madalyonun iki yüzüdür. Biri bilginin ekonomik varoluş koşulunu açıklar, diğeri ise bu bilginin parçalanmış emir defterlerindeki ekonometrik izini sürer.
-->


---

## 8. Sonuç & Temel Çıkarımlar

- **Tam Etkinlik İmkansızdır:** Grossman & Stiglitz (1980), bilgi maliyetli ($c > 0$) olduğu sürece piyasa fiyatlarının özel bilgiyi %100 yansıtamayacağını ispatlamıştır. Piyasada alfa ve aktif yönetim her zaman var olmak zorundadır.
- **Gürültü Piyasayı Yaşatır:** Gürültü tüccarları ($x \sim \mathcal{N}(0, \sigma_x^2)$) olmadan bilgi ticareti yapılamaz; bilgisizler bedavacılıkla tüm bilgiyi çekip sistemi kilitler.
- **Fiyat Keşfi Ölçülebilirdir:** Joel Hasbrouck (1991, 1995), eşbütünleşik VAR ve Beveridge-Nelson ayrıştırmasıyla kalıcı içsel değer yeniliklerinin hangi borsadan kaynaklandığını ($IS_j$) kesin matematiksel sınırlarla ortaya koymuştur.
- **Modern Uygulama:** HFT algoritmaları, arbitraj botları ve kripto türev borsaları (Binance Perp vs Coinbase Spot) arasındaki liderlik rekabeti Hasbrouck Information Share ile modellenmektedir.

> [!NOTE]
> Teşekkürler! Sorularınız ve Kantitatif Tartışma İçin Söz Sizde.


<!--
🎙️ Notlar: Sunumumuz burada sona erdi. Grossman-Stiglitz ve Hasbrouck ekolü, günümüz algoritmik piyasa yapıcılığının ve yüksek frekanslı ticaretin temel referans noktası olmaya devam etmektedir.
-->
