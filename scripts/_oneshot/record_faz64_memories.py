"""
Script to inject Faz 64 Quantitative Finance Research Findings into Entropy AI's Cognitive Memory System.
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
            "Michael B. Gordy (2003) Asymptotic Single Risk Factor (ASRF) Model & Basel Credit Capital: "
            "Proves that credit portfolio Value-at-Risk is exactly additive across individual obligors if and only if "
            "the portfolio is asymptotically fine-grained and governed by a single systematic economic state factor X ~ N(0, 1). "
            "Underpins the Basel II/III/IV Internal Ratings-Based (IRB) formula: "
            "K_i = [ LGD_i * Phi( (Phi^-1(PD_i) + sqrt(rho_i) * Phi^-1(0.999)) / sqrt(1 - rho_i) ) - LGD_i * PD_i ] * MA(M_i). "
            "Defines endogenous asset correlation rho(PD) ranging between 12% and 24% and maturity adjustment MA(M).",
            0.99,
            {"source": "research_2026_phase64", "standard": "Gordy_ASRF_Basel_2003"}
        ),
        (
            "semantic",
            "Jack L. Treynor & Kay K. Mazuy (1966) Quadratic Market Timing & Convexity Beta Engine: "
            "Classic quadratic regression model separating security selection alpha from macroeconomic market timing curvature: "
            "r_{p,t} - r_{f,t} = alpha + beta * (r_{m,t} - r_{f,t}) + gamma * (r_{m,t} - r_{f,t})^2 + eps_t. "
            "A positive and statistically significant gamma > 0 establishes genuine market timing ability, providing a synthetic "
            "call option on the market index and inducing dynamic effective beta sensitivity beta_eff(r_m) = beta + 2 * gamma * r_m.",
            0.99,
            {"source": "research_2026_phase64", "standard": "Treynor_Mazuy_Market_Timing_1966"}
        ),
        (
            "semantic",
            "Fulvio Corsi (2009) & Andersen-Bollerslev-Diebold (2007) HAR-RV & HAR-RV-J Volatility Models: "
            "Heterogeneous Autoregressive Model of Realized Volatility based on the Heterogeneous Market Hypothesis: "
            "decomposes volatility into daily, weekly (5-day), and monthly (22-day) cascade horizons: "
            "RV_{t+1}^(d) = c + beta_d * RV_t^(d) + beta_w * RV_t^(w) + beta_m * RV_t^(m) + eps_{t+1}. "
            "Reproduces long-memory persistence without fractional integration. The HAR-RV-J extension isolates continuous "
            "diffusion C_t = min(RV_t, BV_t) from discontinuous Poisson jumps J_t = max(0, RV_t - BV_t) via Bipower Variation.",
            0.99,
            {"source": "research_2026_phase64", "standard": "Corsi_HAR_RV_2009"}
        ),
        (
            "semantic",
            "Tarun Chordia, Richard Roll & Avanidhar Subrahmanyam (2000, 2002) Order Imbalance & Microstructure Liquidity: "
            "Microstructure econometric framework proving that daily buyer-initiated vs seller-initiated order imbalances "
            "(OIB_t = (V_B - V_S)/(V_B + V_S)) exert large contemporaneous price impacts (a_1 > 0) followed by inventory-induced "
            "return reversals (a_2 < 0) as market makers restore inventory. Discovered Commonality in Liquidity, demonstrating "
            "that individual stock liquidity co-moves with market-wide liquidity shocks.",
            0.99,
            {"source": "research_2026_phase64", "standard": "Chordia_Roll_Subrahmanyam_OIB_2002"}
        ),
        (
            "semantic",
            "Ivo Welch & Amit Goyal (2008) & Campbell-Thompson (2008) Out-of-Sample Return Predictability: "
            "Foundational macro-finance empirical benchmark proving that traditional predictive regression variables (D/P, E/P, "
            "term spread, default spread) fail to outperform the naive Historical Average (HA) out-of-sample (OOS R^2 <= 0). "
            "Formulated the Out-of-Sample R^2 metric and showed that Campbell-Thompson economic constraints (sign restrictions on "
            "slope and non-negative equity premium) restore statistical and economic significance in forecasting stock market returns.",
            0.99,
            {"source": "research_2026_phase64", "standard": "Welch_Goyal_Return_Predictability_2008"}
        ),
        (
            "semantic",
            "Wayne E. Ferson & Campbell R. Harvey (1991, 1993) Conditional Multi-Beta Asset Pricing Engine: "
            "Resolves static CAPM anomalies by modeling factor betas and expected returns as affine functions of macroeconomic "
            "state instruments Z_{t-1}: beta_i(Z_{t-1}) = b_{i,0} + b_{i,1}*Z_{t-1}. Uses cross-sectional interaction regressions "
            "to prove that predictable variations in equity and bond returns are predominantly driven by time-varying risk premiums "
            "rather than time-varying factor sensitivities.",
            0.99,
            {"source": "research_2026_phase64", "standard": "Ferson_Harvey_Conditional_Beta_1991"}
        )
    ]

    print("--- INGESTING FAZ 64 RESEARCH FINDINGS INTO COGNITIVE MEMORY ---")
    for category, content, importance, meta in memories:
        node, is_new = mem.record_memory(category, content, importance, meta)
        status = "CREATED" if is_new else "UPDATED"
        print(f"[{status}] Node ID: {node.id} | Category: {node.category} | Strength: {node.calculate_ebbinghaus_strength():.2f}")

    print("\n--- VALIDATING HYBRID RECALL ---")
    query = "ASRF Basel Gordy Treynor Mazuy HAR-RV Corsi Order Imbalance Chordia Welch Goyal Ferson Harvey"
    results = mem.hybrid_recall(query, top_k=6)
    for node, score in results:
        print(f"Matched: {node.id} | Score: {score:.4f} | Snippet: {node.content[:80]}...")

    print("\n[SUCCESS] Faz 64 financial engineering memories successfully sealed in cognitive_memory.db.")

if __name__ == "__main__":
    main()
