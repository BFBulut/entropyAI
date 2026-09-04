---
name: financial-auditor
description: >-
  Şirket bilançolarını, forensik kâr kalitesini (Altman-Z, Beneish-M, Dechow-F, IFRS-16), beklenti değerlemesini (Ters DCF), birim ekonomisini (SaaS, Bankacılık), piyasa mikroyapısını (VWAP, OBI, VPIN, Perold Implementation Shortfall), LBO getirisini, M&A akretif/dilütif analizini, crack spread'i, Black-Litterman'ı, asimetrik riskleri (Sortino, Calmar, VaR/CVaR), Pairs Trading Z-skorunu, Short Squeeze riskini, VC waterfall'ını, AMM geçici kaybını, GYO FFO/AFFO/Cap Rate değerlemesini, sigortacılık kombine oranını, AB SKDM karbon vergisini, CDS hazard rate'ini, Avellaneda-Stoikov HFT kotasyonunu, egemen borç kartopu sürdürülebilirliğini (DSA), ALM Durasin Boşluğunu (EVE), proje finansmanı DSCR'ını, birleşme arbitrajını, Grinold aktif yönetim kanununu (IR=IC*sqrt(N)), Volatilite Risk Primini (VRP varyans swapları), Taylor Kuralı politika faizini, TIPS başa baş enflasyonunu, Miller-Orr stokastik nakit yönetimini, stabilcoin sağlık faktörünü, Nelson-Siegel getiri eğrisini, Heston & SABR stokastik volatilitesini, TSMOM kriz alfasını, hisse geri alımı E/P değer testini, Fed net likiditesini, Kredi Notu Göçünü (Fallen Angel LGD), PE Fon Metriklerini (DPI, TVPI, Kaplan-Schoar PME), XVA türev ailesini (CVA, DVA, FVA, MVA, KVA), IMF ARA döviz rezerv yeterliliğini, Dupire yerel volatilitesini, getiri eğrisi PCA kelebek arbitrajını, M&A collar/CVR modellerini, kripto fonlama taşıma arbitrajını ve katmanlı FX korumasını analiz eder.
tags: finance, forensic, valuation, lbo, m-and-a, portfolio-risk, sortino, calmar, var-cvar, statarb, pairs-trading, short-squeeze, venture-capital, impermanent-loss, reit, insurance, cbam, cds, hft, sovereign-debt, alm, duration-gap, project-finance, dscr, merger-arbitrage, garch, grinold, vrp, variance-swaps, dividend-recap, circuit-breaker, taylor-rule, breakeven-inflation, miller-orr, stablecoin, vpin, heston, sabr, tsmom, buyback, ifrs16, fed-plumbing, implementation-shortfall, credit-migration, fallen-angel, private-equity, pme, xva, cva, imf-ara, dupire, butterfly, convexity-bias, m-and-a-collar, cvr, crypto-basis, funding-rate, uniswap-v3, layered-hedging
version: 15.0.0
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

## 12. Piyasa Mikroyapısı, Faiz Eğrisi & Konveksite Motoru (`microstructure_convexity_forensic.py`)
- **VPIN Toksik Akış & Flash Crash Tespiti**:
  ```bash
  python skills/financial-auditor/scripts/microstructure_convexity_forensic.py vpin --buy-vol 150000 --total-vol 200000
  ```
- **Almgren-Chriss Optimal Likidasyon & Kalıcı Etki**:
  ```bash
  python skills/financial-auditor/scripts/microstructure_convexity_forensic.py almgren --shares 500000 --adv 2000000 --daily-vol 0.02 --gamma 0.0000001 --eta 0.0000005 --lambda-risk 0.000001
  ```
- **Nelson-Siegel Faiz Eğrisi Dekompozisyonu**:
  ```bash
  python skills/financial-auditor/scripts/microstructure_convexity_forensic.py nelson-siegel --maturity 10.0 --b0 4.5 --b1 -1.5 --b2 0.8 --lambda-val 0.06
  ```

## 13. Faktör Yatırımı, SABR & Likidite Süngeri Motoru (`factor_liquidity_commodity.py`)
- **Zaman Serisi Momentumu (TSMOM) & Volatilite Ölçekleme**:
  ```bash
  python skills/financial-auditor/scripts/factor_liquidity_commodity.py tsmom --returns-12m 0.25 --daily-vol 0.01 --target-vol 0.15
  ```
- **Hisse Geri Alımı Gerçek Değer Yaratım Sınavı**:
  ```bash
  python skills/financial-auditor/scripts/factor_liquidity_commodity.py buyback --price 50.0 --eps 5.0 --debt-rate 6.0 --tax-rate 25.0
  ```
- **IFRS-16 Faaliyet Kiralaması Kapitalizasyonu**:
  ```bash
  python skills/financial-auditor/scripts/factor_liquidity_commodity.py ifrs16 --payment 10.0 --years 5 --discount-rate 5.0 --ebitda 50.0 --net-debt 100.0
  ```
- **SABR Faiz Türevi Swaption Volatilite Modeli**:
  ```bash
  python skills/financial-auditor/scripts/factor_liquidity_commodity.py sabr --forward 0.04 --strike 0.04 --maturity 1.0 --alpha 0.05 --beta 0.5 --rho -0.2 --nu 0.4
  ```

## 14. İleri İcra, Kredi Göçü, PE Metrikleri, XVA & Kriz Motoru (`execution_pe_xva_crisis.py`)
- **Perold Implementation Shortfall & Karekök Piyasa Etkisi**:
  ```bash
  python skills/financial-auditor/scripts/execution_pe_xva_crisis.py shortfall --decision 100.0 --arrival 100.20 --execution 100.50 --final 101.00 --executed-shares 8000 --target-shares 10000 --fees 50 --vol 0.015 --volume 1000000
  ```
- **Kredi Notu Göçü, Fallen Angel & LGD Beklenen Zarar**:
  ```bash
  python skills/financial-auditor/scripts/execution_pe_xva_crisis.py credit-migration --ead 10000000 --pd-current 0.4 --recovery 40.0 --pd-downgrade 3.5 --stress-recovery 30.0
  ```
- **Özel Sermaye (PE) Fon Metrikleri & Kaplan-Schoar PME**:
  ```bash
  python skills/financial-auditor/scripts/execution_pe_xva_crisis.py pe-metrics --pic 100 --distributions 150 --nav 50 --bench-dist 225 --bench-calls 180
  ```
- **XVA Türev Fiyatlama Düzeltmeleri (CVA, DVA, FVA, MVA, KVA)**:
  ```bash
  python skills/financial-auditor/scripts/execution_pe_xva_crisis.py xva --pv 1000000 --ee 500000 --cp-pd 2.0 --cp-recovery 40.0 --ene 300000 --own-pd 1.0 --own-recovery 40.0 --funding-spread 1.0 --initial-margin 100000 --margin-cost 2.0 --reg-capital 200000 --hurdle-rate 10.0
  ```
- **IMF ARA Rezerv Yeterliliği ve Döviz Krizi Barometresi**:
  ```bash
  python skills/financial-auditor/scripts/execution_pe_xva_crisis.py imf-ara --reserves 66.0 --st-debt 100.0 --portfolio 50.0 --m2 200.0 --exports 150.0
  ```

## 15. Volatilite Yüzeyi, Kelebek PCA, M&A Collar & Kripto Arbitraj Motoru (`volatility_surface_crypto_arbitrage.py`)
- **Dupire Yerel Volatilite & Skew Analizi**:
  ```bash
  python skills/financial-auditor/scripts/volatility_surface_crypto_arbitrage.py dupire --iv 20.0 --dvol-dt 0.01 --dvol-dk -0.02 --strike 100.0 --spot 100.0 --maturity 1.0
  ```
- **Faiz Eğrisi PCA Kelebek (5Y Butterfly) & Konveksite Yanlılığı**:
  ```bash
  python skills/financial-auditor/scripts/volatility_surface_crypto_arbitrage.py butterfly --y2 4.2 --y5 4.0 --y10 4.4 --y30 4.6
  ```
- **M&A Collar (Yaka) Koridoru & CVR Değerlemesi**:
  ```bash
  python skills/financial-auditor/scripts/volatility_surface_crypto_arbitrage.py collar --buyer-price 50.0 --floor 40.0 --cap 60.0 --ratio 0.50 --cvr-payout 5.0 --cvr-prob 80.0 --cvr-years 2.0
  ```
- **Kripto Perpetual Fonlama Oranı Arbitrajı & Uniswap v3 Konsantre Likidite**:
  ```bash
  python skills/financial-auditor/scripts/volatility_surface_crypto_arbitrage.py crypto-basis --spot 60000.0 --perp 60300.0 --funding 0.05 --lp-lower 50000.0 --lp-upper 72000.0
  ```
- **Katmanlı Dinamik Döviz Koruma Merdiveni & MTM Likidite Şoku**:
  ```bash
  python skills/financial-auditor/scripts/volatility_surface_crypto_arbitrage.py fx-layered --exposure 10000000.0 --spot 34.0 --q1 80.0 --q2 60.0 --q3 40.0 --q4 20.0
  ```



