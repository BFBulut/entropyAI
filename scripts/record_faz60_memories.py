"""
Script to inject Faz 60 Quantitative Finance Research Findings into Entropy AI's Cognitive Memory System.
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

def main():
    mem = CognitiveMemorySystem()
    memories = [
        (
            "semantic",
            "Andrea Frazzini & Lasse Heje Pedersen (2014) Betting Against Beta (BAB) & Leverage Constraints: "
            "Because many investors (mutual funds, retail, pension funds) face borrowing and leverage constraints, "
            "they overweight high-beta assets to achieve higher returns, causing high-beta assets to be overpriced "
            "and flattening the Security Market Line (SML). The BAB factor exploits this by ranking assets by beta, "
            "taking leveraged long positions in low-beta assets (k_L = 1/beta_L) and de-leveraged short positions in "
            "high-beta assets (k_H = 1/beta_H), creating a market-neutral portfolio (beta_BAB = 0) with significant "
            "positive risk-adjusted alpha (alpha_BAB > 0) directly compensating for the shadow cost of borrowing.",
            0.99,
            {"source": "research_2026_phase60", "standard": "Frazzini_Pedersen_BAB_2014"}
        ),
        (
            "semantic",
            "Sanford J. Grossman & Joseph E. Stiglitz (1980) Information Acquisition Equilibrium & Grossman-Stiglitz Paradox: "
            "Proves the impossibility of informationally efficient markets: if prices fully reflect private information, "
            "no trader has an economic incentive to expend positive resources (cost c > 0) to collect information, "
            "leading to an uninformative market. In competitive equilibrium under CARA utility and noise trader supply x ~ N(0, var_x), "
            "an endogenous fraction lambda* of informed traders emerges where Var(theta|uninformed)/Var(theta|informed) = exp(2*a*c). "
            "Price informativeness rho^2 = Corr(P, theta)^2 is strictly less than 1, proving prices cannot be fully revealing.",
            0.99,
            {"source": "research_2026_phase60", "standard": "Grossman_Stiglitz_Paradox_1980"}
        ),
        (
            "semantic",
            "Francis A. Longstaff & Eduardo S. Schwartz (2001) Least-Squares Monte Carlo (LSM) Option Valuation: "
            "A breakthrough simulation method for valuing American and Bermudan options across complex path-dependent dynamics. "
            "At each discrete exercise date prior to expiration, the algorithm identifies in-the-money (ITM) paths and performs "
            "cross-sectional ordinary least squares (OLS) regression of discounted future realized cash flows on polynomial basis "
            "functions (1, S, S^2, S^3). This yields an accurate estimate of continuation value to compare against immediate exercise "
            "payoff, isolating the optimal stopping boundary and computing the exact non-negative early exercise premium (EEP >= 0).",
            0.99,
            {"source": "research_2026_phase60", "standard": "Longstaff_Schwartz_LSM_2001"}
        ),
        (
            "semantic",
            "Robert F. Engle & Simone Manganelli (2004) CAViaR (Conditional Autoregressive Value at Risk): "
            "Models the conditional tail quantile of portfolio returns directly via an autoregressive process, bypassing "
            "rigid distributional assumptions (normality, Student-t). Offers Symmetric Absolute Value (SAV) and Asymmetric Slope (AS) "
            "specifications estimated via Koenker-Bassett (1978) check/pinball loss function minimization. Out-of-sample "
            "validity and serial independence of quantile hits (Hit_t = I(r_t < q_t) - theta) are verified using the "
            "Dynamic Quantile (DQ) test statistic, which follows an asymptotic Chi-Square distribution.",
            0.99,
            {"source": "research_2026_phase60", "standard": "Engle_Manganelli_CAViaR_2004"}
        ),
        (
            "semantic",
            "K. Geert Rouwenhorst (1995) Markov Chain Discretization of Highly Persistent Processes: "
            "A recursive method for discretizing continuous Gaussian AR(1) processes (y_t = rho*y_{t-1} + eps_t) onto an N-state "
            "discrete Markov chain. Unlike the Tauchen (1986) method which suffers severe moment distortions when persistence rho -> 1, "
            "the Rouwenhorst binomial recursion preserves the unconditional mean, variance, and first-order autocorrelation "
            "with near-zero error even for extreme persistence (rho = 0.999), making it the gold standard in macro-finance and dynamic option lattices.",
            0.98,
            {"source": "research_2026_phase60", "standard": "Rouwenhorst_Markov_Discretization_1995"}
        ),
        (
            "semantic",
            "Peter Carr & Dilip Madan (1998, 2001) / Derman & Kani (1998) Model-Free Implied Variance & CBOE VIX: "
            "Proves that any twice-differentiable European payoff H(S_T) can be replicated model-free via a static portfolio of cash, "
            "underlying stock, and a continuum of out-of-the-money calls and puts weighted by H''(K). Applied to the log-contract "
            "H(S_T) = -2*ln(S_T/S_*), H''(K) = 2/K^2, this provides the exact mathematical foundation of the CBOE VIX index. "
            "Empirical VIX consistently exceeds realized volatility, creating a persistent positive Variance Risk Premium (VRP = sigma_IV^2 - sigma_RV^2 > 0).",
            0.99,
            {"source": "research_2026_phase60", "standard": "Carr_Madan_ModelFree_VIX_1998"}
        )
    ]

    print("--- INGESTING FAZ 60 RESEARCH FINDINGS INTO COGNITIVE MEMORY ---")
    for category, content, importance, meta in memories:
        node, is_new = mem.record_memory(category, content, importance, meta)
        status = "CREATED" if is_new else "UPDATED"
        print(f"[{status}] Node ID: {node.id} | Category: {node.category} | Strength: {node.calculate_ebbinghaus_strength():.2f}")

    print("\n--- VALIDATING HYBRID RECALL ---")
    query = "Betting Against Beta leverage constraints CAViaR LSM VIX Carr Madan Rouwenhorst"
    results = mem.hybrid_recall(query, top_k=6)
    for node, score in results:
        print(f"Matched: {node.id} | Score: {score:.4f} | Snippet: {node.content[:80]}...")

    print("\n[SUCCESS] Faz 60 financial engineering memories successfully sealed in cognitive_memory.db.")

if __name__ == "__main__":
    main()
