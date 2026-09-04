---
name: financial-auditor
description: >-
  Şirket bilançolarını, forensik kâr kalitesini (Altman-Z, Beneish-M), beklenti değerlemesini (Ters DCF), birim ekonomisini (SaaS, Bankacılık), piyasa mikroyapısını (VWAP, OBI), LBO getirisini, M&A akretif/dilütif analizini, crack spread'i, Black-Litterman'ı, asimetrik riskleri (Sortino, Calmar, VaR/CVaR), Pairs Trading Z-skorunu, Short Squeeze riskini, VC waterfall'ını, AMM geçici kaybını, GYO FFO/AFFO/Cap Rate değerlemesini, sigortacılık kombine oranını, AB SKDM karbon vergisini, CDS hazard rate'ini, Avellaneda-Stoikov HFT kotasyonunu, egemen borç kartopu sürdürülebilirliğini (DSA), ALM Durasin Boşluğunu (EVE), proje finansmanı DSCR'ını, birleşme arbitrajını, Grinold aktif yönetim kanununu (IR=IC*sqrt(N)), Volatilite Risk Primini (VRP varyans swapları), Taylor Kuralı politika faizini, TIPS başa baş enflasyonunu, Miller-Orr stokastik nakit yönetimini ve aşırı teminatlı stabilcoin sağlık faktörünü analiz eder.
tags: finance, forensic, valuation, lbo, m-and-a, portfolio-risk, sortino, calmar, var-cvar, statarb, pairs-trading, short-squeeze, venture-capital, impermanent-loss, reit, insurance, cbam, cds, hft, sovereign-debt, alm, duration-gap, project-finance, dscr, merger-arbitrage, garch, grinold, vrp, variance-swaps, dividend-recap, circuit-breaker, taylor-rule, breakeven-inflation, miller-orr, stablecoin
version: 11.0.0
---

# Financial Auditor Skill & Decennial Hedge Fund Intelligence Platform

Bu yetenek; temel finansal tablolardan başlayarak forensik kâr denetimi, özel sermaye (LBO), kurumsal birleşmeler (M&A), emtia vadeli eğrileri, asimetrik portföy riski, istatistiksel arbitraj, para piyasaları, short squeeze, girişim sermayesi (VC), gayrimenkul (GYO/REIT), sigortacılık float'ı, AB SKDM (CBAM) karbon vergisi, yapılandırılmış kredi (CLO/CDS), HFT piyasa yapıcılığı, egemen borç (DSA), varlık-yükümlülük yönetimi (ALM duration gap), proje finansmanı (DSCR/CFADS), birleşme arbitrajı, Grinold aktif portföy kanunu, varyans swapları (VRP) ve likidite karadeliklerine kadar küresel bir yatırım bankası ve multi-strateji mega hedge fon düzeyinde eksiksiz karar desteği sağlar.

## 1. Temel Finansal Rasyolar (`financial_ratios.py`)
```bash
python skills/financial-auditor/scripts/financial_ratios.py --current-assets 500000 --current-liab 250000 --net-income 80000 --revenue 1000000 --equity 400000
```

## 2. Forensik & Değerleme Analiz Motoru (`advanced_analytics.py`)
- **Altman Z-Score**: İflas riski ($Z < 1.81$).
- **Beneish M-Score**: Kâr makyajlama alarmı ($M > -1.78$).
- **Ters DCF**: Piyasa fiyatının ima ettiği serbest nakit akışı büyüme beklentisi.
- **Fraksiyonel Kelly**: Sermaye koruma odaklı optimal pozisyon boyutu.

## 3. Sektörel Birim Ekonomisi ve Kantitatif Motor (`quant_calculator.py`)
- **SaaS**: Rule of 40 ($Büyüme + FCF \ge 40\%$), Magic Number, LTV/CAC.
- **Bankacılık**: Net Faiz Marjı (NIM), Basel III Sermaye Yeterlilik Rasyosu (CAR).
- **Tahvil**: Modifiye Durasin ve Konveksite ile faiz hassasiyet simülasyonu.
- **Mikroyapı**: Emir Defteri Dengesizliği (OBI) ve VWAP icra ortalaması.

## 4. Özel Durumlar & LBO Modellemesi (`special_situations.py`)
- **Kaldıraçlı Satın Alma (LBO)**: Sponsor özkaynak çarpanı (MOIC) ve yıllık bileşik getiri (IRR).
- **M&A Birleşme Akretif / Dilütif Analizi**: Standalone vs Pro-forma EPS ve hisse ihraç sulanması.
- **3:2:1 Rafineri Crack Spread**: Benzin, motorin ve ham petrol varil kârlılığı.
- **Guidotti-Greenspan Kur Şoku Oranı**: Net döviz rezervi / kısa vadeli dış borç.

## 5. Portföy Riski & İstatistiksel Arbitraj Motoru (`portfolio_risk.py`)
- **Sortino Oranı**: Aşağı yönlü negatif sapmaları cezalandıran asimetrik risk metriği.
- **Calmar Oranı**: Yıllık bileşik getiri (CAGR) / Maksimum Drawdown (MDD).
- **Parametrik VaR ve %97.5 CVaR (Expected Shortfall)**: Kuyruk riski sermaye kaybı.
- **Pairs Trading Z-Skoru**: Eşbütünleşik çiftlerde ortalamaya dönüş (Mean-reversion) al/sat sinyali.

## 6. Para Piyasası, Short Squeeze & VC Motoru (`market_liquidity_vc.py`)
- **Short Squeeze Alarmı**: Short Float %, Days-to-Cover (SIR) ve Borrow Fee riski.
- **Girişim Sermayesi (VC) Seyrelmesi**: Pre/Post-money, hisse fiyatı ve kurucu sulanması.
- **AMM Geçici Kayıp (Impermanent Loss - IL)**: Uniswap $x \cdot y = k$ fiyat kayması.
- **Merkez Bankası AOFM**: Ağırlıklı Ortalama Fonlama Maliyeti hesabı.

## 7. GYO, Sigortacılık & Karbon Motoru (`reit_insurance_carbon.py`)
- **GYO (REIT) FFO & AFFO**: Net nakit yaratma gücü ve temettü sürdürülebilirliği.
- **Kapitalizasyon Oranı (Cap Rate)**: Gayrimenkul getiri oranı ($NOI / Değer$).
- **Sigortacılık Kombine Oran (Combined Ratio)**: Hasar ve giderlerin primlere oranı.
- **AB SKDM (CBAM) Karbon Vergisi**: Sınırda karbon maliyet yükümlülüğü.

## 8. Yapılandırılmış Kredi, HFT & Egemen Borç Motoru (`structured_sovereign_credit.py`)
- **CDS İma Edilen Temerrüt Olasılığı (Hazard Rate)**: $PD \approx Spread / (1 - R)$.
- **Avellaneda-Stoikov HFT Rezervasyon Fiyatı**: Envanter riskine göre asimetrik kotasyon.
- **Egemen Borç Kartopu Etkisi (DSA)**: Borç/GSYİH stabilizasyonu için faiz dışı denge.
- **CLO Aşırı Teminatlandırma (OC) Testi**: Kıdemli borç koruma oranı.

## 9. ALM, Proje Finansmanı & Birleşme Arbitrajı Motoru (`alm_project_arbitrage.py`)
- **ALM Durasin Boşluğu (Duration Gap) & EVE**: Faiz şokunda özkaynak erimesi (SVB iflas testi).
- **Proje Finansmanı DSCR**: Borç servisi karşılama oranı ve temettü kısıtlama sözleşmesi.
- **Birleşme Arbitrajı İma Edilen Başarı Olasılığı ($P_{success}$)**: Teklif kapanma ihtimali.
- **GARCH(1,1) Koşullu Volatilite**: Oynaklık kümelenmesi güncellemesi.

## 10. Kantitatif Alfa, Volatilite Arbitrajı & Çöküş Motoru (`alpha_volatility_crash.py`)
- **Grinold Aktif Yönetim Kanunu**: $IR \approx IC \times \sqrt{N}$ bilgi oranı hesabı.
  ```bash
  python skills/financial-auditor/scripts/alpha_volatility_crash.py grinold --ic 0.04 --breadth 2500
  ```
- **Volatilite Risk Primi (VRP) & Varyans Swapı İtfası**:
  ```bash
  python skills/financial-auditor/scripts/alpha_volatility_crash.py vrp --iv 20.0 --rv 16.0 --vega 10000
  ```
- **Temettü Yeniden Finansmanı (Dividend Recap)**: Kaldıraç sıçraması ve PE nakit dönüşü.
  ```bash
  python skills/financial-auditor/scripts/alpha_volatility_crash.py recap --ebitda 20 --debt 30 --new-debt 80 --equity 70 --dividend 75
  ```
- **Devre Kesici (LULD / VBTS) Mesafesi**:
  ```bash
  python skills/financial-auditor/scripts/alpha_volatility_crash.py circuit --price 109.5 --base 100 --band 10.0
  ```

## 11. Makro Taylor Kuralı, TIPS & Stabilcoin Motoru (`macro_taylor_stablecoin.py`)
- **Taylor Kuralı & Politika Faizi Boşluğu**:
  ```bash
  python skills/financial-auditor/scripts/macro_taylor_stablecoin.py taylor --neutral 2.0 --inflation 4.5 --target 2.0 --output-gap 1.0 --actual-rate 5.0
  ```
- **TIPS Başa Baş Enflasyon Oranı**:
  ```bash
  python skills/financial-auditor/scripts/macro_taylor_stablecoin.py tips --nominal 4.30 --real 1.95
  ```
- **Miller-Orr Stokastik Kurumsal Nakit Yönetimi**:
  ```bash
  python skills/financial-auditor/scripts/macro_taylor_stablecoin.py miller-orr --cost 50 --variance 1000000 --rate 0.0001 --lower 5000 --current 32000
  ```
- **Stabilcoin Sağlık Faktörü (Health Factor) & Tasfiye Riski**:
  ```bash
  python skills/financial-auditor/scripts/macro_taylor_stablecoin.py stablecoin --collateral 150000 --threshold 0.80 --borrowed 100000
  ```

