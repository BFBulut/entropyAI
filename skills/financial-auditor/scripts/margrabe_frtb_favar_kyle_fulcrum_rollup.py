"""Phase 29: Quantitative Financial Engineering & Institutional Risk Architecture.

Core Pillars:
1. Margrabe (1978) Exchange Options & Kirk (1995) Approximate Spread Options Engine
2. Basel III/IV FRTB (Fundamental Review of the Trading Book) & Expected Shortfall (ES) Engine
3. FAVAR (Factor-Augmented VAR) & Dynamic Factor Model (DFM) Macro Nowcasting Engine
4. Cross-Asset Market Impact Matrix & Kyle-Back (1992) Continuous-Time Insider Trading Engine
5. Distressed Debt Restructuring: Enterprise Value Chasm, Fulcrum Security & Section 363 Auction Engine
6. Layer-2 Rollup Economics, EIP-4844 Blob Space Fee Dynamics & Shared Sequencer Margin Engine
"""

import argparse
from dataclasses import dataclass, field
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# 0. NUMERICAL HELPER FUNCTIONS
# ==============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ==============================================================================
# 1. MARGRABE (1978) & KIRK (1995) SPREAD OPTIONS ENGINE
# ==============================================================================

@dataclass
class MargrabeExchangeResult:
    option_price: float
    volatility_spread: float
    delta_asset1: float
    delta_asset2: float
    d1: float
    d2: float
    ratio_s1_s2: float

@dataclass
class KirkSpreadResult:
    option_price: float
    effective_volatility: float
    delta_asset1: float
    delta_asset2: float
    d1: float
    d2: float
    intrinsic_value: float


class MargrabeKirkSpreadEngine:
    """Analytical multi-asset pricing for exchange options and commodity/energy spreads."""

    @staticmethod
    def price_margrabe_exchange(
        s1: float,
        s2: float,
        q1: float,
        q2: float,
        sigma1: float,
        sigma2: float,
        rho: float,
        t_mat: float
    ) -> MargrabeExchangeResult:
        """
        Margrabe (1978) formula for European option to exchange Asset 2 for Asset 1:
        Payoff = max(S1(T) - S2(T), 0).
        """
        if s1 <= 0 or s2 <= 0:
            raise ValueError("Asset prices must be strictly positive.")
        if t_mat <= 0:
            raise ValueError("Time to maturity must be positive.")
        if not (-1.0 <= rho <= 1.0):
            raise ValueError("Correlation rho must be in [-1, 1].")

        var_spread = sigma1 * sigma1 + sigma2 * sigma2 - 2.0 * rho * sigma1 * sigma2
        sigma_spread = math.sqrt(max(1e-12, var_spread))

        sqrt_t = math.sqrt(t_mat)
        disc_s1 = s1 * math.exp(-q1 * t_mat)
        disc_s2 = s2 * math.exp(-q2 * t_mat)

        d1 = (math.log(disc_s1 / disc_s2) + 0.5 * sigma_spread * sigma_spread * t_mat) / (sigma_spread * sqrt_t)
        d2 = d1 - sigma_spread * sqrt_t

        nd1 = _norm_cdf(d1)
        nd2 = _norm_cdf(d2)

        price = disc_s1 * nd1 - disc_s2 * nd2
        delta1 = math.exp(-q1 * t_mat) * nd1
        delta2 = -math.exp(-q2 * t_mat) * nd2

        return MargrabeExchangeResult(
            option_price=float(max(0.0, price)),
            volatility_spread=float(sigma_spread),
            delta_asset1=float(delta1),
            delta_asset2=float(delta2),
            d1=float(d1),
            d2=float(d2),
            ratio_s1_s2=float(s1 / s2)
        )

    @staticmethod
    def price_kirk_spread(
        s1: float,
        s2: float,
        strike_k: float,
        r: float,
        sigma1: float,
        sigma2: float,
        rho: float,
        t_mat: float,
        a_ratio: float = 1.0
    ) -> KirkSpreadResult:
        """
        Kirk (1995) approximation for spread options with non-zero strike K:
        Payoff = max(S1(T) - a * S2(T) - K, 0).
        Commonly used in energy spark spreads (Electricity vs Gas) and refinery crack spreads.
        """
        if s1 <= 0 or s2 <= 0:
            raise ValueError("Asset prices must be positive.")
        if t_mat <= 0:
            raise ValueError("Maturity must be positive.")

        k_disc = strike_k * math.exp(-r * t_mat)
        f2 = a_ratio * s2 + k_disc
        if f2 <= 0:
            raise ValueError("Effective denominator asset (a*S2 + K*e^-rT) must be positive.")

        w = (a_ratio * s2) / f2
        var_kirk = sigma1 * sigma1 + (w * sigma2) ** 2 - 2.0 * rho * sigma1 * (w * sigma2)
        sigma_kirk = math.sqrt(max(1e-12, var_kirk))

        sqrt_t = math.sqrt(t_mat)
        d1 = (math.log(s1 / f2) + 0.5 * sigma_kirk * sigma_kirk * t_mat) / (sigma_kirk * sqrt_t)
        d2 = d1 - sigma_kirk * sqrt_t

        nd1 = _norm_cdf(d1)
        nd2 = _norm_cdf(d2)

        price = s1 * nd1 - f2 * nd2
        intrinsic = max(0.0, s1 - a_ratio * s2 - strike_k)

        delta1 = nd1
        delta2 = -a_ratio * nd2 * w

        return KirkSpreadResult(
            option_price=float(max(intrinsic, price)),
            effective_volatility=float(sigma_kirk),
            delta_asset1=float(delta1),
            delta_asset2=float(delta2),
            d1=float(d1),
            d2=float(d2),
            intrinsic_value=float(intrinsic)
        )


# ==============================================================================
# 2. BASEL III/IV FRTB (FUNDAMENTAL REVIEW OF THE TRADING BOOK) ENGINE
# ==============================================================================

@dataclass
class FRTBExpectedShortfallResult:
    unscaled_es_97_5: float
    liquidity_adjusted_es: float
    horizon_contributions: Dict[str, float]
    var_99: float
    es_to_var_ratio: float

@dataclass
class FRTBCapitalSummary:
    ima_capital_charge: float
    nmrf_capital_charge: float
    total_market_risk_capital: float
    pla_test_passed: bool
    pla_spearman_corr: float
    pla_ks_stat: float


class FRTBMarketRiskEngine:
    """Basel Committee FRTB Market Risk Capital, Liquidity Horizons and NMRF Engine."""

    @staticmethod
    def calculate_liquidity_adjusted_es(
        returns_base_10d: np.ndarray,
        alpha: float = 0.975
    ) -> FRTBExpectedShortfallResult:
        """
        Computes 97.5% Expected Shortfall across Basel FRTB regulatory liquidity horizons:
        LH in {10, 20, 40, 60, 120} days.
        """
        if len(returns_base_10d) < 100:
            raise ValueError("At least 100 return observations required for robust tail ES.")

        # Losses = -returns (positive value = financial loss)
        losses = np.sort(-returns_base_10d)
        n = len(losses)
        cutoff_idx = int(math.floor(alpha * n))
        tail_losses = losses[cutoff_idx:]
        es_base = float(np.mean(tail_losses))
        var_99 = float(np.percentile(losses, 99.0))

        # Regulatory scale factors based on sqrt(LH / 10)
        # Horizons: LH1=10d, LH2=20d, LH3=40d, LH4=60d, LH5=120d
        horizons = [10, 20, 40, 60, 120]
        # Cumulative ES components
        es_components = {}
        sum_sq = 0.0

        for i in range(len(horizons)):
            lh_curr = horizons[i]
            scale = math.sqrt(lh_curr / 10.0)
            es_j = es_base * scale
            if i == 0:
                diff = es_j
                term = diff ** 2
            else:
                diff = es_j - es_components[f"LH_{horizons[i-1]}d"]
                term = (diff ** 2) * ((lh_curr - horizons[i-1]) / 10.0)

            es_components[f"LH_{lh_curr}d"] = es_j
            sum_sq += term

        liq_adj_es = math.sqrt(sum_sq)
        ratio = liq_adj_es / max(1e-6, var_99)

        return FRTBExpectedShortfallResult(
            unscaled_es_97_5=es_base,
            liquidity_adjusted_es=float(liq_adj_es),
            horizon_contributions=es_components,
            var_99=var_99,
            es_to_var_ratio=float(ratio)
        )

    @staticmethod
    def evaluate_frtb_desk_capital(
        liq_adj_es: float,
        nmrf_stresses: List[float],
        rtpl_series: np.ndarray,
        hpl_series: np.ndarray,
        supervisory_multiplier: float = 1.5
    ) -> FRTBCapitalSummary:
        """
        Assesses Trading Desk eligibility under IMA (Internal Models Approach) vs fallback SA-TB.
        Runs PLA (P&L Attribution) test (Spearman correlation and KS test).
        """
        n = len(rtpl_series)
        if n != len(hpl_series) or n < 30:
            raise ValueError("RTPL and HPL series must have equal length >= 30.")

        rank_r = np.argsort(np.argsort(rtpl_series))
        rank_h = np.argsort(np.argsort(hpl_series))
        d_sq = np.sum((rank_r - rank_h) ** 2)
        spearman_corr = 1.0 - (6.0 * d_sq) / (n * (n * n - 1.0))

        # Kolmogorov-Smirnov test of CDF distance
        r_sorted = np.sort(rtpl_series)
        h_sorted = np.sort(hpl_series)
        all_vals = np.sort(np.concatenate([r_sorted, h_sorted]))
        cdf_r = np.searchsorted(r_sorted, all_vals, side='right') / n
        cdf_h = np.searchsorted(h_sorted, all_vals, side='right') / n
        ks_stat = float(np.max(np.abs(cdf_r - cdf_h)))

        # Basel PLA Pass Criteria: Spearman >= 0.80 and KS <= 0.09 (Green Zone)
        pla_passed = bool(spearman_corr >= 0.80 and ks_stat <= 0.09)

        # IMA Capital Charge = mc * ES
        ima_charge = supervisory_multiplier * liq_adj_es

        # Non-Modellable Risk Factors (NMRF) Stress Capital Charge
        nmrf_charge = math.sqrt(sum(s * s for s in nmrf_stresses)) if nmrf_stresses else 0.0

        total_capital = ima_charge + nmrf_charge if pla_passed else (ima_charge * 1.6 + nmrf_charge * 1.4)

        return FRTBCapitalSummary(
            ima_capital_charge=float(ima_charge),
            nmrf_capital_charge=float(nmrf_charge),
            total_market_risk_capital=float(total_capital),
            pla_test_passed=pla_passed,
            pla_spearman_corr=float(spearman_corr),
            pla_ks_stat=float(ks_stat)
        )


# ==============================================================================
# 3. FAVAR & MACRO NOWCASTING (DYNAMIC FACTOR MODEL) ENGINE
# ==============================================================================

@dataclass
class FAVARResult:
    factors: np.ndarray             # (T, K) dynamic factors
    factor_loadings: np.ndarray     # (N, K) factor loadings
    explained_variance_ratio: List[float]
    policy_beta: np.ndarray         # Sensitivity of macro indicators to policy rate shock
    r_squared_avg: float

@dataclass
class NowcastResult:
    nowcast_current_quarter: float
    prior_quarter_benchmark: float
    surprise_contributions: Dict[str, float]
    confidence_interval_95: Tuple[float, float]


class FAVARNowcastingEngine:
    """Factor-Augmented VAR (FAVAR) & Dynamic Factor Model (DFM) Nowcasting."""

    @staticmethod
    def extract_favar_factors(
        macro_panel: np.ndarray,
        policy_rate: np.ndarray,
        n_factors: int = 3
    ) -> FAVARResult:
        """
        Bernanke, Boivin & Eliasz (2005) Factor-Augmented VAR.
        macro_panel: (T, N) panel of standardized macro indicators (production, employment, CPI, credit).
        policy_rate: (T,) central bank target policy rate (Fed Funds / CBRT AOFM).
        """
        t_len, n_vars = macro_panel.shape
        if t_len != len(policy_rate):
            raise ValueError("Time dimension mismatch between panel and policy rate.")

        means = np.mean(macro_panel, axis=0)
        stds = np.std(macro_panel, axis=0)
        stds[stds < 1e-8] = 1.0
        x_std = (macro_panel - means) / stds

        # SVD decomposition for Static Principal Components
        u, s, vt = np.linalg.svd(x_std, full_matrices=False)
        factors = u[:, :n_factors] * s[:n_factors]
        loadings = vt[:n_factors, :].T

        total_var = np.sum(s ** 2)
        var_explained = [(float(s[i] ** 2) / float(total_var)) for i in range(n_factors)]

        # Policy regression: X_i = Lambda_f * F + beta_p * PolicyRate + eps
        design = np.column_stack([factors, policy_rate.reshape(-1, 1)])
        theta = np.linalg.lstsq(design, x_std, rcond=None)[0]
        policy_betas = theta[-1, :]

        pred = design @ theta
        resids = x_std - pred
        r2_vals = 1.0 - (np.var(resids, axis=0) / np.var(x_std, axis=0))
        r2_avg = float(np.mean(r2_vals))

        return FAVARResult(
            factors=factors,
            factor_loadings=loadings,
            explained_variance_ratio=var_explained,
            policy_beta=policy_betas,
            r_squared_avg=max(0.0, min(1.0, r2_avg))
        )

    @staticmethod
    def compute_nowcast(
        base_gdp_growth: float,
        monthly_indicators: Dict[str, Tuple[float, float, float]]
    ) -> NowcastResult:
        """
        Giannone, Reichlin & Small (2008) DFM Nowcasting news decomposition.
        Computes marginal revision to current quarter GDP based on incoming data surprise.
        """
        revisions = {}
        total_revision = 0.0

        for indicator, (actual, expected, weight) in monthly_indicators.items():
            surprise = actual - expected
            impact = surprise * weight
            revisions[indicator] = float(impact)
            total_revision += impact

        nowcast = base_gdp_growth + total_revision
        uncertainty = 0.45 / math.sqrt(max(1, len(monthly_indicators)))
        ci_lower = nowcast - 1.96 * uncertainty
        ci_upper = nowcast + 1.96 * uncertainty

        return NowcastResult(
            nowcast_current_quarter=float(nowcast),
            prior_quarter_benchmark=float(base_gdp_growth),
            surprise_contributions=revisions,
            confidence_interval_95=(float(ci_lower), float(ci_upper))
        )


# ==============================================================================
# 4. CROSS-ASSET MARKET IMPACT & KYLE-BACK (1992) INSIDER TRADING ENGINE
# ==============================================================================

@dataclass
class CrossAssetImpactResult:
    is_arbitrage_free: bool
    permanent_impact_matrix: np.ndarray
    asymmetry_norm: float
    total_execution_impact: np.ndarray
    eigenvalues_impact: List[float]

@dataclass
class KyleBackInsiderResult:
    insider_trading_speed: float
    market_depth_lambda: float
    terminal_expected_profit: float
    information_dissipation_rate: float
    equilibrium_efficiency: float


class CrossAssetImpactKyleEngine:
    """Multi-asset cross-impact matrix verification and Kyle-Back continuous trading."""

    @staticmethod
    def analyze_cross_asset_impact(
        lambda_matrix: np.ndarray,
        order_volumes: np.ndarray
    ) -> CrossAssetImpactResult:
        """
        Gatheral & Schied (2011) No-Manipulation condition:
        Permanent impact matrix Lambda MUST be symmetric and positive semi-definite.
        """
        n = lambda_matrix.shape[0]
        if lambda_matrix.shape[1] != n or len(order_volumes) != n:
            raise ValueError("Impact matrix must be square (N, N) matching order volume size.")

        asym = lambda_matrix - lambda_matrix.T
        asym_norm = float(np.linalg.norm(asym, ord='fro'))

        eigvals = np.linalg.eigvalsh(0.5 * (lambda_matrix + lambda_matrix.T))
        min_eig = float(np.min(eigvals))

        is_arb_free = bool(asym_norm < 1e-5 and min_eig >= -1e-6)
        price_impact = lambda_matrix @ order_volumes

        return CrossAssetImpactResult(
            is_arbitrage_free=is_arb_free,
            permanent_impact_matrix=lambda_matrix,
            asymmetry_norm=asym_norm,
            total_execution_impact=price_impact,
            eigenvalues_impact=[float(e) for e in eigvals]
        )

    @staticmethod
    def compute_kyle_back_equilibrium(
        fundamental_value: float,
        current_price: float,
        noise_trader_vol: float,
        time_to_horizon: float,
        prior_variance: float
    ) -> KyleBackInsiderResult:
        """
        Kyle (1985) & Back (1992) Continuous-Time Insider Trading Model.
        """
        if time_to_horizon <= 0 or noise_trader_vol <= 0 or prior_variance <= 0:
            raise ValueError("Time, noise volatility, and prior variance must be positive.")

        lambda_param = math.sqrt(prior_variance) / (noise_trader_vol * math.sqrt(time_to_horizon))
        beta_t = noise_trader_vol / (math.sqrt(prior_variance) * math.sqrt(time_to_horizon))
        gap = fundamental_value - current_price
        expected_profit = (gap ** 2) / (2.0 * lambda_param)
        dissipation_rate = beta_t * lambda_param

        return KyleBackInsiderResult(
            insider_trading_speed=float(beta_t),
            market_depth_lambda=float(lambda_param),
            terminal_expected_profit=float(expected_profit),
            information_dissipation_rate=float(dissipation_rate),
            equilibrium_efficiency=1.0
        )


# ==============================================================================
# 5. DISTRESSED DEBT: FULCRUM SECURITY & SECTION 363 ENGINE
# ==============================================================================

@dataclass
class DebtTranche:
    name: str
    priority_rank: int
    face_value: float
    recovery_value: float = 0.0
    recovery_rate: float = 0.0
    equity_stake_awarded: float = 0.0
    is_fulcrum: bool = False

@dataclass
class DistressedRestructuringResult:
    enterprise_value: float
    fulcrum_tranche_name: str
    fulcrum_coverage_ratio: float
    senior_recovery_rate: float
    junior_unsecured_recovery_rate: float
    existing_equity_wiped_out: bool
    tranches_summary: List[Dict[str, Any]]

@dataclass
class Section363AuctionResult:
    winning_bid_value: float
    stalking_horse_bid: float
    break_up_fee: float
    expense_reimbursement: float
    net_proceeds_to_estate: float
    overbid_increment: float


class DistressedDebtFulcrumEngine:
    """Corporate distress waterfall, Fulcrum security identification and Section 363 sales."""

    @staticmethod
    def evaluate_fulcrum_waterfall(
        enterprise_value: float,
        tranches: List[Tuple[str, int, float]]
    ) -> DistressedRestructuringResult:
        """
        Identifies the Fulcrum Security in Chapter 11 where Enterprise Value is exhausted.
        """
        sorted_tranches = sorted(tranches, key=lambda x: x[1])
        remaining_ev = enterprise_value

        results: List[DebtTranche] = []
        fulcrum_found = False
        fulcrum_name = "None"
        fulcrum_cov = 1.0

        for name, rank, face in sorted_tranches:
            t = DebtTranche(name=name, priority_rank=rank, face_value=face)
            if remaining_ev >= face:
                t.recovery_value = face
                t.recovery_rate = 1.0
                remaining_ev -= face
            elif remaining_ev > 0:
                t.recovery_value = remaining_ev
                t.recovery_rate = remaining_ev / face
                t.is_fulcrum = True
                t.equity_stake_awarded = 1.0
                fulcrum_name = name
                fulcrum_cov = t.recovery_rate
                fulcrum_found = True
                remaining_ev = 0.0
            else:
                t.recovery_value = 0.0
                t.recovery_rate = 0.0
                t.is_fulcrum = False

            results.append(t)

        senior_rec = results[0].recovery_rate if results else 0.0
        junior_rec = results[-1].recovery_rate if results else 0.0

        summary = [
            {
                "name": t.name,
                "rank": t.priority_rank,
                "face": t.face_value,
                "recovery": t.recovery_value,
                "rate": t.recovery_rate,
                "fulcrum": t.is_fulcrum,
                "equity_share": t.equity_stake_awarded
            }
            for t in results
        ]

        return DistressedRestructuringResult(
            enterprise_value=enterprise_value,
            fulcrum_tranche_name=fulcrum_name,
            fulcrum_coverage_ratio=float(fulcrum_cov),
            senior_recovery_rate=float(senior_rec),
            junior_unsecured_recovery_rate=float(junior_rec),
            existing_equity_wiped_out=True if not fulcrum_found or fulcrum_name != "None" else False,
            tranches_summary=summary
        )

    @staticmethod
    def model_section_363_sale(
        stalking_horse_bid: float,
        break_up_fee_pct: float = 0.03,
        expense_reimbursement: float = 1_500_000.0,
        auction_rounds: int = 3,
        min_overbid_step: float = 2_000_000.0
    ) -> Section363AuctionResult:
        """
        Section 363 Bankruptcy asset sale auction mechanics.
        """
        break_up_fee = stalking_horse_bid * break_up_fee_pct
        min_initial_overbid = stalking_horse_bid + break_up_fee + expense_reimbursement + min_overbid_step

        current_bid = min_initial_overbid
        for _ in range(max(0, auction_rounds - 1)):
            current_bid += min_overbid_step

        net_proceeds = current_bid - break_up_fee - expense_reimbursement

        return Section363AuctionResult(
            winning_bid_value=float(current_bid),
            stalking_horse_bid=float(stalking_horse_bid),
            break_up_fee=float(break_up_fee),
            expense_reimbursement=float(expense_reimbursement),
            net_proceeds_to_estate=float(net_proceeds),
            overbid_increment=float(min_overbid_step)
        )


# ==============================================================================
# 6. LAYER-2 ROLLUP ECONOMICS & EIP-4844 BLOB FEE ENGINE
# ==============================================================================

@dataclass
class BlobFeeMarketResult:
    next_blob_base_fee_wei: float
    next_blob_base_fee_gwei: float
    target_blobs: int
    actual_blobs: int
    fee_percentage_change: float
    l1_data_cost_eth: float

@dataclass
class RollupProfitabilityResult:
    l2_total_revenue_eth: float
    l1_total_cost_eth: float
    net_operating_profit_eth: float
    operating_profit_margin: float
    da_cost_savings_vs_calldata_pct: float
    sequencer_bankruptcy_risk: bool


class RollupEconomicsBlobEngine:
    """EIP-4844 Blob Space fee pricing, Rollup unit economics and DA cost squeeze."""

    @staticmethod
    def calculate_eip4844_blob_fee(
        current_blob_base_fee_wei: float,
        actual_blobs_in_block: int,
        target_blobs_per_block: int = 3,
        update_fraction: float = 3338477.0
    ) -> BlobFeeMarketResult:
        """
        EIP-4844 exponential blob fee update rule.
        """
        delta = actual_blobs_in_block - target_blobs_per_block
        multiplier = math.exp(delta / (update_fraction / 1e6))
        next_fee_wei = max(1.0, current_blob_base_fee_wei * multiplier)
        next_fee_gwei = next_fee_wei / 1e9

        pct_change = ((next_fee_wei - current_blob_base_fee_wei) / current_blob_base_fee_wei) * 100.0
        l1_cost_eth = (next_fee_wei * 131072 * actual_blobs_in_block) / 1e18

        return BlobFeeMarketResult(
            next_blob_base_fee_wei=float(next_fee_wei),
            next_blob_base_fee_gwei=float(next_fee_gwei),
            target_blobs=target_blobs_per_block,
            actual_blobs=actual_blobs_in_block,
            fee_percentage_change=float(pct_change),
            l1_data_cost_eth=float(l1_cost_eth)
        )

    @staticmethod
    def analyze_rollup_margin(
        l2_tx_count: int,
        avg_l2_tx_fee_eth: float,
        mev_revenue_eth: float,
        blobs_used: int,
        blob_base_fee_gwei: float,
        l1_execution_gas_eth: float,
        zk_proof_cost_eth: float = 0.0
    ) -> RollupProfitabilityResult:
        """
        Computes Layer-2 Rollup operating margin and compares EIP-4844 blob cost vs legacy calldata.
        """
        l2_rev = (l2_tx_count * avg_l2_tx_fee_eth) + mev_revenue_eth
        blob_fee_wei = blob_base_fee_gwei * 1e9
        blob_da_cost = (blob_fee_wei * 131072 * blobs_used) / 1e18
        l1_total_cost = blob_da_cost + l1_execution_gas_eth + zk_proof_cost_eth

        net_profit = l2_rev - l1_total_cost
        margin = (net_profit / max(1e-12, l2_rev)) if l2_rev > 0 else -1.0

        legacy_calldata_cost = (16 * 131072 * blobs_used * 30e9) / 1e18
        savings_pct = max(0.0, ((legacy_calldata_cost - blob_da_cost) / max(1e-12, legacy_calldata_cost)) * 100.0)
        bankruptcy_risk = bool(l1_total_cost > l2_rev)

        return RollupProfitabilityResult(
            l2_total_revenue_eth=float(l2_rev),
            l1_total_cost_eth=float(l1_total_cost),
            net_operating_profit_eth=float(net_profit),
            operating_profit_margin=float(margin),
            da_cost_savings_vs_calldata_pct=float(savings_pct),
            sequencer_bankruptcy_risk=bankruptcy_risk
        )


# ==============================================================================
# CLI HARNESS
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 29 Financial Engineering CLI")
    parser.add_argument("--demo", action="store_true", help="Run self-diagnostic demonstrations")
    args = parser.parse_args()

    if args.demo:
        print("=== Phase 29: Quantitative Financial Engineering Demo ===")
        m_res = MargrabeKirkSpreadEngine.price_margrabe_exchange(
            s1=100.0, s2=90.0, q1=0.02, q2=0.01, sigma1=0.25, sigma2=0.20, rho=0.6, t_mat=1.0
        )
        print(f"Margrabe Option Value: ${m_res.option_price:.4f}, Vol Spread: {m_res.volatility_spread:.4f}")

        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.015, 250)
        es_res = FRTBMarketRiskEngine.calculate_liquidity_adjusted_es(returns)
        print(f"FRTB Liquidity Adjusted ES: {es_res.liquidity_adjusted_es:.4f}, Ratio: {es_res.es_to_var_ratio:.2f}")

        tranches = [
            ("1st Lien Senior Secured", 1, 300_000_000.0),
            ("2nd Lien Notes", 2, 200_000_000.0),
            ("Senior Unsecured Notes", 3, 250_000_000.0),
        ]
        dist_res = DistressedDebtFulcrumEngine.evaluate_fulcrum_waterfall(420_000_000.0, tranches)
        print(f"Fulcrum Tranche: {dist_res.fulcrum_tranche_name}, Coverage: {dist_res.fulcrum_coverage_ratio:.2%}")

        rollup_res = RollupEconomicsBlobEngine.analyze_rollup_margin(
            l2_tx_count=500_000, avg_l2_tx_fee_eth=0.00008, mev_revenue_eth=5.0,
            blobs_used=120, blob_base_fee_gwei=1.5, l1_execution_gas_eth=4.0
        )
        print(f"Rollup Operating Margin: {rollup_res.operating_profit_margin:.2%}, Savings vs Calldata: {rollup_res.da_cost_savings_vs_calldata_pct:.2f}%")


if __name__ == "__main__":
    main()
