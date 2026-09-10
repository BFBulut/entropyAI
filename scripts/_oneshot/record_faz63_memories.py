"""
Script to inject Faz 63 Quantitative Finance Research Findings into Entropy AI's Cognitive Memory System.
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
            "Andrew Ang, Joseph Chen & Yuhang Xing (2006) Downside Risk Asset Pricing: "
            "Investors exhibit asymmetric risk aversion, caring far more about losses during market crashes "
            "than gains during bull runs. Ang, Chen & Xing decompose market co-movement into Downside Beta "
            "(beta^- = Cov(r_i, r_m | r_m < mu_m) / Var(r_m | r_m < mu_m)) and Upside Beta (beta^+). "
            "Assets with high relative downside beta (Delta beta = beta^- - beta > 0) demand an empirical cross-sectional "
            "expected return premium of 4-6% annually (E[R_i - R_f] = beta * lambda_m + (beta^- - beta) * lambda^-) "
            "that cannot be explained by standard CAPM, Fama-French factors, momentum, or liquidity.",
            0.99,
            {"source": "research_2026_phase63", "standard": "Ang_Chen_Xing_Downside_Risk_2006"}
        ),
        (
            "semantic",
            "Michael Stutzer (2000) Portfolio Performance Index & Cramér's Large Deviations: "
            "A universal non-parametric portfolio performance metric rooted in Cramér's Large Deviations Principle "
            "and Kullback-Leibler relative entropy. Evaluates the asymptotic exponential decay rate I_S at which the "
            "probability of trailing a benchmark vanishes as horizon T -> infinity: P((1/T) sum d_t <= 0) ~ exp(-T * I_S). "
            "Formulated as I_S = max_{theta <= 0} [ -ln( (1/N) sum exp(theta * d_t) ) ]. Unlike the symmetric Sharpe ratio, "
            "the Stutzer Index severely penalizes negative skewness, fat left tails, and option-writing disaster risks.",
            0.99,
            {"source": "research_2026_phase63", "standard": "Stutzer_Performance_Index_2000"}
        ),
        (
            "semantic",
            "Harry Markowitz (1956) & Marcos López de Prado (2012) Critical Line Algorithm (CLA): "
            "The exact mathematical quadratic programming algorithm designed specifically for constrained portfolio optimization "
            "under box bounds (l_i <= w_i <= u_i, e.g. long-only with individual asset caps). Solves the piecewise linear "
            "efficient frontier by partitioning assets into a Free set (F) and Bounded sets (L, U), identifying exact corner "
            "portfolios along the frontier. Eliminates the catastrophic numerical instabilities and false local minima of generic "
            "quadratic solvers when covariance matrices are ill-conditioned.",
            0.99,
            {"source": "research_2026_phase63", "standard": "Markowitz_LopezDePrado_CLA_2012"}
        ),
        (
            "semantic",
            "Peter Carr & Liuren Wu (2009) Variance Risk Premium (VRP) & Corridor Variance Swaps (CVS): "
            "Quantifies the systematic negative variance risk premium VRP = E^Q[RV] - E^P[RV] > 0, representing the insurance "
            "premium equity investors pay to hedge market volatility. Addresses the fatal flaw of standard log-contract variance swaps, "
            "which diverge to infinity upon severe price jumps (S_T -> 0), by restricting strike integration to a bounded price corridor "
            "[B_L, B_U]. Replicates the fair corridor variance strike via semi-static vanilla options weighted by 2/K^2.",
            0.99,
            {"source": "research_2026_phase63", "standard": "Carr_Wu_VRP_CorridorSwaps_2009"}
        ),
        (
            "semantic",
            "David Easley, Marcos López de Prado & Maureen O'Hara (2011, 2012) VPIN (Volume-Synchronized Probability of Toxicity): "
            "A high-frequency market microstructure metric replacing calendar time with a Volume Clock (constant volume buckets V). "
            "Employs Bulk Volume Classification (BVC) via Gaussian normal CDF of price changes (V_tau^B = V * Phi(Delta P / sigma_dp)) "
            "to compute order flow toxicity VPIN = sum |V_tau^B - V_tau^S| / (N * V). High VPIN signals toxic informed flow, causing "
            "market maker inventory exhaustion, quote withdrawal, and liquidity evaporation, serving as a reliable early warning for Flash Crashes.",
            0.99,
            {"source": "research_2026_phase63", "standard": "Easley_LopezDePrado_OHara_VPIN_2012"}
        ),
        (
            "semantic",
            "Ole E. Barndorff-Nielsen & Neil Shephard (2004, 2006) / Huang & Tauchen (2005) Bipower Variation & Jump Detection: "
            "Decomposes high-frequency quadratic variation (RV = sum r_i^2) into continuous Brownian diffusion and discontinuous Poisson jumps. "
            "Realized Bipower Variation (BV = (pi/2) sum |r_i| |r_{i-1}|) is immune to isolated jumps, converging strictly to integrated variance. "
            "Coupled with Realized Tripower Quarticity (TQ), the Huang-Tauchen standardized Z-statistic tests the null hypothesis of no jumps, "
            "enabling robust statistical detection of jump arrivals (Z > 2.326 at 99% confidence) and pure continuous variance isolation.",
            0.99,
            {"source": "research_2026_phase63", "standard": "BarndorffNielsen_Shephard_Bipower_2004"}
        )
    ]

    print("--- INGESTING FAZ 63 RESEARCH FINDINGS INTO COGNITIVE MEMORY ---")
    for category, content, importance, meta in memories:
        node, is_new = mem.record_memory(category, content, importance, meta)
        status = "CREATED" if is_new else "UPDATED"
        print(f"[{status}] Node ID: {node.id} | Category: {node.category} | Strength: {node.calculate_ebbinghaus_strength():.2f}")

    print("\n--- VALIDATING HYBRID RECALL ---")
    query = "Downside beta Ang Chen Xing Stutzer Index Critical Line Algorithm VRP Corridor Swap VPIN Bipower Variation"
    results = mem.hybrid_recall(query, top_k=6)
    for node, score in results:
        print(f"Matched: {node.id} | Score: {score:.4f} | Snippet: {node.content[:80]}...")

    print("\n[SUCCESS] Faz 63 financial engineering memories successfully sealed in cognitive_memory.db.")

if __name__ == "__main__":
    main()
