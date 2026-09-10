"""
Script to inject Faz 65 Quantitative Finance Research Findings into Entropy AI's Cognitive Memory System.
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

def main():
    mem = CognitiveMemorySystem()
    memories = [
        (
            "semantic",
            "Douglas T. Breeden & Robert H. Litzenberger (1978) State-Contingent Prices Implicit in Option Prices & RND: "
            "Foundational theorem proving that the second partial derivative of European call prices with respect to strike K "
            "recovers the exact Arrow-Debreu state-contingent prices and the risk-neutral probability density function (RND): "
            "q(K) = d^2 C / dK^2 and f^*(S_T = K) = e^{r T} * (d^2 C / dK^2). "
            "Replicated model-free through butterfly spreads: [C(K - dK) - 2C(K) + C(K + dK)] / dK^2. "
            "Allows non-parametric extraction of forward price, higher-order risk-neutral skewness, and tail kurtosis.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Breeden_Litzenberger_RND_1978"}
        ),
        (
            "semantic",
            "Sanford J. Grossman & Merton H. Miller (1988) Determinants of Market Liquidity & Capital Commitment: "
            "Seminal microstructure equilibrium model where buyers and sellers arrive asynchronously at rate lambda. "
            "Dealers (market makers) bridge the time gap by committing scarce risk capital and holding inventory over interval tau = 1/lambda. "
            "The equilibrium bid-ask spread and price concession are proportional to dealer risk aversion (gamma_m), "
            "fundamental return variance (sigma^2), and order size Q: Spread S = (2 * gamma_m * sigma^2 * Q) / (lambda * (1 + capital_factor)) + 2*c. "
            "Explains sudden liquidity dry-ups when market maker capital buffers are constrained.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Grossman_Miller_Liquidity_1988"}
        ),
        (
            "semantic",
            "Gary Gorton & Andrew Metrick (2012) & Krishnamurthy-Nagel-Orlov (2014) Run on Repo & Haircut Spiral: "
            "Structural theory of modern shadow banking runs taking place in wholesale short-term collateralized repo markets. "
            "Runs manifest not as retail cash withdrawals, but as explosive collateral haircut hikes (m_t jumping from 5% to 50%+). "
            "Because maximum leverage is strictly bound by L = 1/m, haircut shocks force instantaneous asset fire-sales. "
            "Fire-sale price impacts depress collateral market values, creating a self-fulfilling recursive insolvency deleveraging cascade.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Gorton_Metrick_Repo_Run_2012"}
        ),
        (
            "semantic",
            "George Tauchen & Mark R. Pitts (1983) & Peter K. Clark (1973) Mixture of Distributions Hypothesis (MDH): "
            "Subordinated stochastic process model proving that asset returns and trading volume are jointly generated "
            "by a latent, unobservable information arrival rate I_t: R_t | I_t ~ N(0, sigma_e^2 * I_t) and V_t | I_t = mu_V * I_t + eps_t. "
            "Unconditionally generates leptokurtic fat tails (Kurtosis = 3 * E[I^2] / (E[I])^2 > 3) and establishes "
            "the empirical positive correlation between trading volume and return volatility without violating martingale properties.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Tauchen_Pitts_MDH_1983"}
        ),
        (
            "semantic",
            "Geert Bekaert & Campbell R. Harvey (1995, 1997) Time-Varying Financial Market Integration Model: "
            "Dynamic regime-switching asset pricing framework evaluating how emerging markets transition from capital segmentation to world integration. "
            "Under complete segmentation (phi = 0), local assets are priced strictly by local variance; under complete integration (phi = 1), "
            "they are priced strictly by world covariance beta: E_t[R_i] - R_f = phi_t * beta_{i,W} * lambda_W + (1 - phi_t) * lambda_{i,L} * Var(R_i). "
            "Logistic transition functions demonstrate dramatic cost of capital compression and global diversification benefits.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Bekaert_Harvey_Market_Integration_1995"}
        ),
        (
            "semantic",
            "Richard Roll (1984) & Kenneth R. French (1980) Microstructure Spread & Trading Time Volatility: "
            "Roll (1984) proves that in an efficient market with bid-ask bounce, serial covariance of price changes is negative: "
            "Cov(Delta P_t, Delta P_{t-1}) = -s^2 / 4, yielding Roll's implicit effective spread estimator s = 2 * sqrt(-Cov) "
            "directly from transaction prices without quote data. "
            "French (1980) variance ratio demonstrates that volatility is 3 to 7 times higher during active exchange trading hours "
            "than closed weekend/night hours, proving that private information revealed through trading drives volatility rather than clock time.",
            0.99,
            {"source": "research_2026_phase65", "standard": "Roll_French_Microstructure_1984"}
        )
    ]

    print("--- INGESTING FAZ 65 RESEARCH FINDINGS INTO COGNITIVE MEMORY ---")
    for category, content, importance, meta in memories:
        node, is_new = mem.record_memory(category, content, importance, meta)
        status = "CREATED" if is_new else "UPDATED"
        print(f"[{status}] Node ID: {node.id} | Category: {node.category} | Strength: {node.calculate_ebbinghaus_strength():.2f}")

    print("\n--- VALIDATING HYBRID RECALL ---")
    query = "Breeden Litzenberger Grossman Miller Gorton Metrick Tauchen Pitts Bekaert Harvey Roll French"
    results = mem.hybrid_recall(query, top_k=6)
    for node, score in results:
        print(f"Matched: {node.id} | Score: {score:.4f} | Snippet: {node.content[:80]}...")

    print("\n[SUCCESS] Faz 65 financial engineering memories successfully sealed in cognitive_memory.db.")

if __name__ == "__main__":
    main()
