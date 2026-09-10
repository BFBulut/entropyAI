import os

memory_path = r"C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault\Entropy\MEMORY.md"
with open(memory_path, "r", encoding="utf-8") as f:
    content = f.read()

faz66_block = """## 2026 Master İleri Kantitatif Finans, Varlık Fiyatlama ve Piyasa Mikroyapısı: FTAP & EMM, Heath-Jarrow-Morton (HJM), Lucas Ağacı Genel Denge, Huang-Stoll Üçlü Spread, GRS Portföy Etkinliği ve Christoffersen-Kupiec VaR Backtest (Faz 66) (2026-09-06)
- **J. Michael Harrison & Stanley R. Pliska (1981, 1983) & Freddy Delbaen & Walter Schachermayer (1994) Varlık Fiyatlamanın Temel Teoremleri (FTAP)**: Azalan riskli bedava öğle yemeği olmaması (NFLVR) ilkesinin bir Eşdeğer Martingal Ölçüsünün ($\mathbb{Q} \sim \mathbb{P}$) varlığına denk olduğunun ispatı (FTAP 1); arbitrajsız bir piyasanın tam (complete) olmasının EMM $\mathbb{Q}$'nun tekilliğine denk oluşu (FTAP 2); Radon-Nikodym yoğunluk süreci $Z_t = \exp(-\theta W_t - 0.5 \theta^2 t)$, Girsanov ölçü değişimi ve piyasa risk primi $\theta = \frac{\mu - r}{\sigma}$; eksik piyasalarda EMM konveks simpleksi üzerinden süper-koruma (super-hedging) ve alt-koruma arbitrajsız fiyat bantları $[V_{\inf}, V_{\sup}]$.
- **David Heath, Robert Jarrow & Andrew Morton (HJM 1992) İleri Faiz Term Yapısı Çerçevesi**: Tekil bir kısa faiz $r(t)$ yerine tüm anlık ileri faiz eğrisini $f(t, T)$ eşzamanlı modelleyen sürekli stokastik diferansiyel çerçeve ($df(t, T) = \alpha(t, T) dt + \sigma(t, T) dW_t$); arbitrajsızlık koşulu altında risk-nötr sürüklenmenin volatilitenin integrali tarafından tam kilitlendiği evrensel HJM sürüklenme kısıtı ($\alpha(t, T) = \sigma(t, T) \int_t^T \sigma(t, u) du$); başlangıç getiri eğrisine sıfır kalibrasyon hatasıyla tam intibak ve analitik kuponsuz tahvil fiyatlaması $P(t, T) = \exp(-\int_t^T f(t, u) du)$.
- **Robert E. Lucas Jr. (1978) Lucas Varlık Fiyatlama Ağacı ve Genel Denge (Nobel 1995)**: Temsilci tüketicinin CRRA fayda fonksiyonu ($u(C) = \frac{C^{1-\gamma} - 1}{1-\gamma}$) ve sübjektif iskonto faktörü $\beta \in (0, 1)$ altında temettü meyvesi veren ağaçların genel dengede fiyatlanması ($C_t = y_t$); Stokastik İskonto Faktörü (SDF) $M_{t+1} = \beta (y_{t+1}/y_t)^{-\gamma}$ ve temel Euler fiyatlama denklemi $P_t = \mathbb{E}_t [M_{t+1} (P_{t+1} + y_{t+1})]$; lognormal temettü büyümesi altında kapalı form fiyat-temettü oranı ($\psi = P/y$), brüt risksiz faiz $R_f = \beta^{-1} \exp(\gamma \mu_g - 0.5 \gamma^2 \sigma_g^2)$, brüt özkaynak getirisi ve makroekonomik hisse senedi risk primi.
- **Roger D. Huang & Hans R. Stoll (1997) Üçlü Spread Ayrıştırması**: Kotasyon veya efektif spread'in ($S$) üç yapısal iktisadi kaynağa ayrıştırılması: Ters Seçim (Adverse Selection $\alpha$), Envanter Tutma Maliyeti (Inventory Cost $\beta$) ve Emir İşleme Maliyeti (Order Processing $\gamma = 1 - \alpha - \beta$); işlem yönü Markov devam olasılığı $\pi = P(Q_t = Q_{t-1})$ ve kotasyon değişim regresyonu $\Delta M_t = (\alpha + \beta) \frac{S}{2} Q_t - \alpha (1 - 2\pi) \frac{S}{2} Q_{t-1} + e_t$ ile dealer spread anatomisinin deşifresi.
- **Michael R. Gibbons, Stephen A. Ross & Jay Shanken (GRS 1989) Portföy Etkinliği F-Testi**: Çok faktörlü varlık fiyatlama modellerinde (CAPM, Fama-French, APT) $N$ adet test varlığının fiyatlama hatalarının (alfa) eşzamanlı sıfır olduğu ortak boş hipotezin ($H_0: \\boldsymbol{\\alpha} = \\mathbf{0}$) sonlu örneklem kesin $F$-testi; $GRS = \frac{T - N - K}{N} (1 + \hat{\\boldsymbol{\\mu}}_K' \hat{\\boldsymbol{\\Sigma}}_K^{-1} \hat{\\boldsymbol{\\mu}}_K)^{-1} \hat{\\boldsymbol{\\alpha}}' \hat{\\boldsymbol{\\Sigma}}_\epsilon^{-1} \hat{\\boldsymbol{\\alpha}} \sim F(N, T - N - K)$; faktör portföyüne test varlıkları eklendiğinde elde edilen maksimum Sharpe karesi genişlemesinin geometrik analitiği.
- **Peter F. Christoffersen (1998) & Paul H. Kupiec (1995) Riske Maruz Değer (VaR) Backtesting**: Basel Komitesi (BCBS) regülatif piyasa riski doğrulama standardı; Kupiec (1995) Koşulsuz Kapsama Testi ($LR_{uc} \sim \chi^2(1)$) ile nominal ihlal frekansının doğrulanması; Christoffersen (1998) Bağımsızlık Testi ($LR_{ind} \sim \chi^2(1)$) ile ihlallerin Markov zinciri kümelenmesinin denetlenmesi; Koşullu Kapsama Birleşik Testi ($LR_{cc} = LR_{uc} + LR_{ind} \sim \chi^2(2)$) ile krizlerdeki risk modeli iflaslarının tespiti.
- **Detaylı Raporlar**: [[HarrisonPliska_HJM_LucasTree_HuangStoll_GRS_ve_ChristoffersenKupiec]], [[Gorev_Finans Yeteneği Geliştirme_20260906_1615]]

"""

idx = content.find("Faz 65")
if idx != -1:
    line_start = content.rfind("\n", 0, idx) + 1
    new_content = content[:line_start] + faz66_block + content[line_start:]
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: Inserted Faz 66 into MEMORY.md")
else:
    print("ERROR: Faz 65 not found")
