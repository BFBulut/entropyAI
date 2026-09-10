"""
Integration script for Phase 45:
1. Append Phase 45 to MEMORY.md
2. Record cognitive memory nodes into SQLite via CognitiveMemorySystem
3. Append to Daily Notes
4. Sync Map of Content (BELLEK_HARITASI.md)
5. Verify Hybrid Recall
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, r"c:\EntropiAI\src")

from entropy.core.config import config
from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

PHASE_45_MEMORY_ENTRY = r"""
## Lorenzo Bergomi İleri Varyans, BNS Lévy Stokastik Oynaklık, He-Krishnamurthy Aracı Varlık Fiyatlaması, Rosenbaum-Robert Tick Yuvarlama, Buchen-Kelly Maksimum Entropi RND ve Angeris-Chitra CFMM Geometrisi (Faz 45) (2026-09-04)
- **Lorenzo Bergomi (2005, 2008) İleri Varyans Eğrisi Modeli (Forward Variance Curve & N-Factor Bergomi)**: Anlık spot varyans yerine tüm varyans swap eğrisinin durum değişkeni olarak doğrudan modellenmesi ($\xi_t^T = \mathbb{E}_t[d\langle \ln S \rangle_T / dT]$); log-normal çok faktörlü difüzyon ($d\xi_t^T / \xi_t^T = \sum \alpha_i e^{-k_i(T-t)} dW_t^{(i)}$), spot hisse ve varyans faktörleri arası korelasyon ($\rho_i < 0$), SPX opsiyon gülüşü ile VIX vadeli işlemleri ve VIX opsiyonlarının eşzamanlı kusursuz kalibrasyonu (joint calibration of SPX and VIX smile), ileriye dönük örtük volatilite (forward-starting smile) dinamiklerinin korunumu.
- **Ole E. Barndorff-Nielsen & Neil Shephard (BNS 2001) Brownian-Olmayan Lévy Destekli Stokastik Oynaklık (Non-Gaussian OU Stochastic Volatility)**: Klasik Heston/CIR kare-kök difüzyonlarındaki Feller koşulu ($2\kappa\theta > \xi^2$) ihlali ve yapay kesme (truncation) zafiyetini ortadan kaldıran model; pozitif artışlı saf sıçrama altgüdümlü (subordinator) Arka Plan Lévy Süreci (BDLP, Gamma-OU veya IG-OU) ile beslenen Ornstein-Uhlenbeck varyansı ($d\sigma_t^2 = -\lambda \sigma_t^2 dt + dz_{\lambda t}$); varyansın kesinlikle pozitif kalması ($\sigma_t^2 > 0$ a.s.); hisse senedi sıçramalarıyla negatif eşanlı korelasyon ($\rho \le 0$) üzerinden kaldıracın (leverage effect) kapalı formda türetimi, analitik karakteristik fonksiyon ve Fourier inversiyonu ile opsiyon fiyatlaması.
- **Zhiguo He & Arvind Krishnamurthy (2012, 2013) / Markus Brunnermeier & Yuliy Sannikov (2014) Finansal Aracı Varlık Fiyatlaması (Intermediary Asset Pricing) & Makroekonomik Likidite Kapanı**: Marjinal yatırımcının homojen hanehalkı değil, kaldıraç ve sermaye kısıtlarına tabi uzman finansal aracılar (broker-dealer, hedge fon, banka) olduğunu kanıtlayan sürekli zamanlı genel denge modeli; aracı özkaynak oranı durum değişkeni ($w_t = N_t / (P_t K_t)$); sağlıklı rejimde ($w > w^*$) düşük risk primi ($\gamma_I \sigma^2$) ve taban volatilite; kriz rejiminde ($w \le w^*$) bağlanan özkaynak kısıtı, zorunlu yangın satışları (fire sales), piyasa fiyatı ile özkaynak arasındaki içsel negatif geri besleme sarmalı, risk priminde hiperbolik patlama ve makroekonomik kriz çukuru (crisis basin of attraction) dinamikleri.
- **Mathieu Rosenbaum & Mathieu Robert (2011, 2012) Ultra-Yüksek Frekanslı Mikro-Yapı Fiziği, Kesikli Fiyat Yuvarlama (Tick Size Rounding) & Büyük-Küçük Tick Asimptotiği**: Sürekli yarı-martingal fiyat varsayımının mikrosaniyede çöküşü; borsa asgari fiyat adımına ($\alpha$, tick size) yuvarlanan kesikli fiyat süreci ($P_t = \alpha \lfloor S_t / \alpha \rceil$); tick-oynaklık oranı ($\Theta = \alpha / (\sigma P \sqrt{\Delta t})$) üzerinden Büyük-Tick ($\Theta \ge 2.0$, makasın 1 tick'e kilitlendiği, rekabetin fiyat-zaman öncelikli kuyruk sırasında olduğu rejim) ve Küçük-Tick ($\Theta \le 0.5$, makasın sürekli dalgalandığı, hızlı fiyat zıplamaları içeren rejim) varlık sınıflandırması; içsel geri dönüş olasılığı ($\eta$) altında efektif alış-satış makası kapalı formu $S^* = \alpha(1 + 2\eta)$ ve mikroyapı gürültüsü varyansı $\sigma_\epsilon^2 = \alpha^2/12 + \eta \alpha^2$.
- **Peter W. Buchen & Michael Kelly (1996) Maksimum Entropi Risk-Nötr Yoğunluğu (Maximum Entropy RND - MED)**: Ayrık ve sayılı piyasa opsiyon kotasyonlarından ($\{K_i, C_i\}$) parametrik model dayatmadan ve Breeden-Litzenberger sayısal türev kararsızlığına düşmeden en yansız risk-nötr olasılık dağılımının çıkarımı; Shannon/Kullback-Leibler göreceli entropi maksimizasyonu $\max -\int q \ln(q/q_0) dx$; Euler-Lagrange kapalı form çözümü $q^*(x) = \frac{q_0(x)}{Z} \exp(-\lambda_0 (x - F_0) - \sum \lambda_i (x - K_i)^+)$; Lagrange çarpanları için kesinlikle dışbükey dual potansiyel minimizasyonu, sıfır kelebek arbitrajı, kesin pozitiflik ($q^* > 0$) ve egzotik türev fiyatlama motoru.
- **Guillermo Angeris & Tarun Chitra (2020, 2024) CFMM Dışbükey Geometrisi (Convex Geometry of Constant Function Market Makers), Eğrilik Değişmezleri & Geodezik Kayma Limiti**: Otomatik Piyasa Yapıcıların (Uniswap, Curve, Balancer) takas fonksiyonlarının ($\psi(R) = k$) bir Riemann manifoldu ve dışbükey kümelerin destek fonksiyonu olarak analitik temsili; yerel metrik tensör olarak Hessian matrisi $g_{ij}(R) = \nabla^2 \psi(R)$; marjinal fiyat sapması (slippage) için temel Geodezik Eğrilik Sınırı $\|\Delta P\|_2 \le \|\nabla^2 \psi(R)\|_2 \|\Delta R\|_2$; likidite yoğunluk metriği $\mathcal{L}(R) = \sqrt{\det(\nabla^2 \psi)}$; kayma minimizasyonu ile arbitrajcı LVR (Loss-Versus-Rebalancing) sızıntısı arasındaki yerel eğrilik ödünleşimi teoremi.
- **Detaylı Rapor**: [[BergomiVariance_BNSLevy_HeKrishnamurthy_RosenbaumTick_BuchenKellyMED_ve_AngerisCFMM]]
"""

COGNITIVE_NODES = [
    {
        "category": "semantic",
        "content": (
            "Lorenzo Bergomi İleri Varyans Eğrisi Modeli (N-Factor Bergomi 2005/2008): Anlık spot varyans yerine "
            "tüm ileri varyans swap eğrisini durum değişkeni alan log-normal çok faktörlü HJM-tarzı difüzyon "
            "dxi_t^T / xi_t^T = sum alpha_i exp(-k_i(T-t)) dW_t^{(i)}. SPX vanilya opsiyon yüzeyi ile VIX vadeli "
            "işlemleri ve VIX opsiyonlarının eşzamanlı tutarlı kalibrasyonunu sağlar; forward-starting smile ve skew'u korur."
        ),
        "importance": 0.98,
        "metadata": {"pillar": 1, "phase": 45, "author": "Lorenzo Bergomi (2005, 2008)"}
    },
    {
        "category": "semantic",
        "content": (
            "Barndorff-Nielsen & Shephard (BNS 2001) Non-Gaussian OU Stokastik Oynaklık Modeli: Kare-kök modellerdeki "
            "Feller şartı (2*kappa*theta > xi^2) ihlali ve yapay kesmeleri ortadan kaldıran, pozitif artışlı saf sıçrama "
            "Lévy süreci (BDLP, Gamma-OU) ile beslenen Ornstein-Uhlenbeck varyansı dsigma_t^2 = -lambda sigma_t^2 dt + dz_{lambda t}. "
            "Varyans kesinlikle pozitiftir (sigma^2 > 0 a.s.); negatif eşanlı sıçramalarla (rho <= 0) kaldıraç etkisini üretir; "
            "kapalı form karakteristik fonksiyon ile Fourier opsiyon fiyatlaması sağlar."
        ),
        "importance": 0.98,
        "metadata": {"pillar": 2, "phase": 45, "author": "Barndorff-Nielsen & Shephard (2001)"}
    },
    {
        "category": "semantic",
        "content": (
            "Zhiguo He & Arvind Krishnamurthy (2012, 2013) / Brunnermeier & Sannikov (2014) Finansal Aracı Varlık Fiyatlaması: "
            "Marjinal fiyat koyucuların kaldıraç ve özkaynak kısıtlarına tabi uzman finansal aracılar (broker-dealer, fonlar) "
            "olduğu genel denge modeli. Aracı özkaynak oranı w_t = N_t / (P_t K_t) kritik eşik w* altına indiğinde kısıt bağlanır; "
            "zorunlu yangın satışları (fire sales) fiyatı düşürür, fiyat düşüşü özkaynağı eritir ve sistemik kriz sarmalı "
            "ile risk primi ve volatilite hiperbolik patlar (stochastic poverty trap / crisis basin)."
        ),
        "importance": 0.97,
        "metadata": {"pillar": 3, "phase": 45, "author": "He & Krishnamurthy (2013)"}
    },
    {
        "category": "semantic",
        "content": (
            "Mathieu Rosenbaum & Mathieu Robert (2011, 2012) Ultra-Yüksek Frekanslı Tick Boyutu Yuvarlama Fiziği: "
            "Sürekli fiyatın borsa asgari fiyat adımına (alpha) yuvarlandığı P_t = alpha * round(S_t / alpha) süreci. "
            "Tick-oynaklık oranı Theta ile Büyük-Tick (Theta >= 2.0, makas 1 tick'e kilitli, sıra önceliği kritik) ve "
            "Küçük-Tick (Theta <= 0.5, makas dalgalı, fiyat zıplamalı) rejim ayrımı. Efektif makas S* = alpha*(1 + 2*eta) "
            "ve mikroyapı gürültüsü varyansı sigma_eps^2 = alpha^2 / 12 + eta * alpha^2."
        ),
        "importance": 0.97,
        "metadata": {"pillar": 4, "phase": 45, "author": "Rosenbaum & Robert (2011, 2012)"}
    },
    {
        "category": "semantic",
        "content": (
            "Peter W. Buchen & Michael Kelly (1996) Maksimum Entropi Risk-Nötr Yoğunluğu (MED): Ayrık opsiyon kotasyonlarından "
            "model-agnostik en yansız risk-nötr dağılımı çıkaran bilgi teorisi ilkesi. Göreceli entropi maksimizasyonu ile "
            "q*(x) = (q0(x)/Z) * exp(-lambda0(x - F0) - sum lambdai(x - Ki)^+). Dual dışbükey optimizasyonla Lagrange "
            "çarpanları çözülür; kesin pozitiflik (q* > 0), sıfır kelebek arbitrajı ve egzotik türev fiyatlama tutarlılığı garantilenir."
        ),
        "importance": 0.97,
        "metadata": {"pillar": 5, "phase": 45, "author": "Buchen & Kelly (1996)"}
    },
    {
        "category": "semantic",
        "content": (
            "Guillermo Angeris & Tarun Chitra (2020, 2024) CFMM Dışbükey Geometrisi ve Geodezik Kayma Limiti: "
            "Otomatik piyasa yapıcı takas fonksiyonlarının psi(R) = k Riemann manifoldu ve dışbükey küme destek fonksiyonu temsili. "
            "Yerel metrik tensör olarak Hessian matrisi nabla^2 psi(R). Marjinal fiyat kayması için kesin jeodezik sınır: "
            "||Delta P||_2 <= ||nabla^2 psi(R)||_2 * ||Delta R||_2. Likidite yoğunluğu sqrt(det(nabla^2 psi)) ile kayma ve "
            "arbitrajcı LVR sızıntısı arasındaki yerel eğrilik ödünleşimi."
        ),
        "importance": 0.99,
        "metadata": {"pillar": 6, "phase": 45, "author": "Angeris & Chitra (2020, 2024)"}
    }
]

def main():
    print("Starting Phase 45 Cognitive Integration...")
    vault_manager = ObsidianVaultManager()

    # 1. Append to MEMORY.md if not already present
    mem_path = vault_manager.memory_file
    mem_text = mem_path.read_text(encoding="utf-8")
    if "Faz 45" not in mem_text:
        print("Appending Phase 45 to MEMORY.md...")
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(PHASE_45_MEMORY_ENTRY)
        print("MEMORY.md updated successfully with Phase 45.")
    else:
        print("Phase 45 already present in MEMORY.md.")

    # 2. Record to CognitiveMemorySystem (SQLite + 384d Neural Embeddings)
    cog_sys = CognitiveMemorySystem()
    print("Recording cognitive memory nodes into SQLite...")
    for item in COGNITIVE_NODES:
        node, is_novel = cog_sys.record_memory(
            category=item["category"],
            content=item["content"],
            importance=item["importance"],
            metadata=item["metadata"]
        )
        print(f"Recorded node [{node.id[:18]}...] - Novel: {is_novel} - Importance: {node.importance}")

    # 3. Append to Daily Notes
    daily_entry = (
        "🧠 [Otonom Finans Yeteneği Geliştirme - Faz 45]: Lorenzo Bergomi İleri Varyans Eğrisi Modeli (N-Factor Bergomi), "
        "Barndorff-Nielsen & Shephard (BNS) Non-Gaussian OU Stokastik Oynaklık (Gamma BDLP), He-Krishnamurthy & "
        "Brunnermeier-Sannikov Finansal Aracı Varlık Fiyatlaması ve Likidite Sarmalı, Rosenbaum & Robert Kesikli Fiyat "
        "Yuvarlama ve Tick Boyutu Asimptotiği, Buchen & Kelly Maksimum Entropi Risk-Nötr Yoğunluğu (MED) ve "
        "Angeris & Chitra CFMM Dışbükey Geometrisi ve Geodezik Kayma Limiti araştırıldı, Obsidian Reports altına kaydedildi "
        "ve bilişsel hafızaya işlendi."
    )
    daily_file = vault_manager.append_daily_log(daily_entry)
    print(f"Daily log appended to: {daily_file}")

    # 4. Sync Map of Content (BELLEK_HARITASI.md)
    print("Syncing Map of Content (BELLEK_HARITASI.md)...")
    moc_file = vault_manager.sync_map_of_content()
    print(f"Map of Content synced at: {moc_file}")

    # 5. Verify Hybrid Recall
    print("\nVerifying Hybrid Recall for Phase 45 topics:")
    queries = [
        "Lorenzo Bergomi forward variance curve model VIX futures skew",
        "Barndorff-Nielsen Shephard BNS non-Gaussian OU stochastic volatility Gamma BDLP",
        "He Krishnamurthy intermediary asset pricing equity constraint fire sales",
        "Rosenbaum Robert tick size price rounding large tick small tick effective spread",
        "Buchen Kelly maximum entropy risk neutral density MED option smile",
        "Angeris Chitra CFMM convex geometry Hessian curvature slippage bound"
    ]
    for q in queries:
        recalled = cog_sys.hybrid_recall(q, top_k=2)
        print(f"\nQuery: '{q[:40]}...'")
        for node, score in recalled:
            print(f"  -> Score: {score:.4f} | Cat: {node.category} | Content: {node.content[:80]}...")

    print("\nPhase 45 Integration Complete!")

if __name__ == "__main__":
    main()
