"""Programmatic TDD Verification Suite for Faz 59 Quantitative Finance Engines.

Models:
1. Eugene F. Fama & Kenneth R. French (2015, 2016): Five-Factor Asset Pricing Model, Factor Construction & HML Spanning Redundancy Engine
2. Clifford S. Asness, Andrea Frazzini & Lasse Heje Pedersen (2019): Quality Minus Junk (QMJ), Multi-Dimensional Z-Scoring & Flight-to-Quality Engine
3. James A. Ohlson (1980): O-Score Conditional Logit Bankruptcy Probability & Financial Distress Engine
4. William Fung & David A. Hsieh (2001, 2004): Seven-Factor Hedge Fund / CTA Risk Premia & Lookback Straddle Crisis Alpha Engine
5. Robert J. Shiller (1981, 2000, 2015): Cyclically Adjusted P/E (CAPE), Excess CAPE Yield (ECY) & 10-Year Real Return Decomposition Engine
6. Aswath Damodaran (2012, 2024): Synthetic Credit Rating, Country Risk Premium (CRP) & Endogenous WACC Optimal Capital Structure Engine
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Numerical Functions (Pure Python + NumPy)
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def logistic_sigmoid(z: float) -> float:
    """Logistic sigmoid function bounded safely to avoid numerical overflow."""
    if z > 35.0:
        return 1.0
    if z < -35.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


# ==============================================================================
# Model 1: Fama-French (2015, 2016) Five-Factor Model & Factor Spanning Engine
# ==============================================================================
class FamaFrenchFiveFactorEngine:
    """Eugene F. Fama & Kenneth R. French (2015, 2016) Five-Factor Model.
    R_{it} - R_{ft} = alpha_i + beta_mkt * MKT + beta_smb * SMB + beta_hml * HML
                     + beta_rmw * RMW + beta_cma * CMA + e_{it}
    Features:
    - OLS factor regression decomposition
    - 2x2x2 sorting factor construction (Size, Profitability, Investment)
    - Factor Spanning / Redundancy Test for HML
    - Gibbons-Ross-Shanken (GRS 1989) test for joint alpha zero significance.
    """

    @staticmethod
    def fit_factor_model(
        asset_returns: np.ndarray,
        factor_matrix: np.ndarray
    ) -> Dict[str, Any]:
        """Runs OLS regression of asset returns on the 5 factors.
        Args:
            asset_returns: (T,) excess returns of test asset
            factor_matrix: (T, K) matrix of factors [MKT, SMB, HML, RMW, CMA]
        Returns:
            Dictionary with alpha, betas, t-stats, R2, and residuals.
        """
        T, K = factor_matrix.shape
        X = np.column_stack([np.ones(T), factor_matrix])
        inv_XtX = np.linalg.pinv(X.T @ X)
        params = inv_XtX @ (X.T @ asset_returns)
        alpha = float(params[0])
        betas = params[1:]

        fitted = X @ params
        residuals = asset_returns - fitted
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((asset_returns - np.mean(asset_returns)) ** 2)
        r2 = 1.0 - (ss_res / max(1e-12, ss_tot))

        # Standard errors
        dof = T - (K + 1)
        sigma2_eps = ss_res / max(1, dof)
        var_params = sigma2_eps * np.diag(inv_XtX)
        se_params = np.sqrt(np.maximum(1e-12, var_params))
        t_stats = params / se_params

        return {
            "alpha": alpha,
            "betas": betas.tolist(),
            "t_alpha": float(t_stats[0]),
            "t_betas": t_stats[1:].tolist(),
            "r_squared": float(r2),
            "residuals": residuals,
            "sigma_epsilon": float(math.sqrt(sigma2_eps))
        }

    @staticmethod
    def construct_rmw_and_cma_factors(
        universe_returns: np.ndarray,
        market_caps: np.ndarray,
        operating_profitability: np.ndarray,
        total_asset_growth: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Constructs 2x2x2 independent factor portfolios:
        Size split at median (Small vs Big)
        Profitability split at median (Robust vs Weak)
        Investment split at median (Conservative vs Aggressive)
        """
        median_size = np.median(market_caps)
        median_prof = np.median(operating_profitability)
        median_inv = np.median(total_asset_growth)

        is_small = market_caps <= median_size
        is_big = ~is_small

        is_robust = operating_profitability >= median_prof
        is_weak = ~is_robust

        is_conservative = total_asset_growth <= median_inv
        is_aggressive = ~is_conservative

        # RMW: 0.5 * (Small Robust + Big Robust) - 0.5 * (Small Weak + Big Weak)
        ret_sr = np.mean(universe_returns[:, is_small & is_robust], axis=1)
        ret_br = np.mean(universe_returns[:, is_big & is_robust], axis=1)
        ret_sw = np.mean(universe_returns[:, is_small & is_weak], axis=1)
        ret_bw = np.mean(universe_returns[:, is_big & is_weak], axis=1)
        rmw = 0.5 * (ret_sr + ret_br) - 0.5 * (ret_sw + ret_bw)

        # CMA: 0.5 * (Small Conservative + Big Conservative) - 0.5 * (Small Aggressive + Big Aggressive)
        ret_sc = np.mean(universe_returns[:, is_small & is_conservative], axis=1)
        ret_bc = np.mean(universe_returns[:, is_big & is_conservative], axis=1)
        ret_sa = np.mean(universe_returns[:, is_small & is_aggressive], axis=1)
        ret_ba = np.mean(universe_returns[:, is_big & is_aggressive], axis=1)
        cma = 0.5 * (ret_sc + ret_bc) - 0.5 * (ret_sa + ret_ba)

        return {"RMW": rmw, "CMA": cma}

    @staticmethod
    def test_hml_factor_spanning(
        hml_series: np.ndarray,
        mkt: np.ndarray,
        smb: np.ndarray,
        rmw: np.ndarray,
        cma: np.ndarray
    ) -> Dict[str, Any]:
        """Fama & French (2015) Spanning / Redundancy Test:
        HML_t = alpha + beta_mkt * MKT + beta_smb * SMB + beta_rmw * RMW + beta_cma * CMA + e_t
        If alpha is statistically insignificant (t-stat close to 0) and R2 is high,
        HML is spanned / redundant when RMW and CMA are included.
        """
        other_factors = np.column_stack([mkt, smb, rmw, cma])
        fit = FamaFrenchFiveFactorEngine.fit_factor_model(hml_series, other_factors)
        is_redundant = abs(fit["t_alpha"]) < 2.0
        return {
            "alpha": fit["alpha"],
            "t_alpha": fit["t_alpha"],
            "r_squared": fit["r_squared"],
            "is_redundant": is_redundant,
            "rmw_loading": fit["betas"][2],
            "cma_loading": fit["betas"][3]
        }

    @staticmethod
    def gibbons_ross_shanken_test(
        test_assets_returns: np.ndarray,
        factors: np.ndarray
    ) -> Dict[str, Any]:
        """Gibbons, Ross & Shanken (GRS 1989) test for joint significance of alphas."""
        T, N = test_assets_returns.shape
        _, K = factors.shape

        X = np.column_stack([np.ones(T), factors])
        inv_XtX = np.linalg.pinv(X.T @ X)
        B = inv_XtX @ (X.T @ test_assets_returns)
        alphas = B[0, :]
        residuals = test_assets_returns - (X @ B)
        sigma_eps = (residuals.T @ residuals) / (T - K - 1)

        f_bar = np.mean(factors, axis=0)
        f_centered = factors - f_bar
        sigma_f = (f_centered.T @ f_centered) / (T - 1)

        f_factor = 1.0 + float(f_bar.T @ np.linalg.pinv(sigma_f) @ f_bar)
        inv_sigma_eps = np.linalg.pinv(sigma_eps)
        alpha_term = float(alphas.T @ inv_sigma_eps @ alphas)

        scaling = (T - N - K) / (N * f_factor)
        grs_stat = float(scaling * alpha_term)

        return {
            "grs_statistic": grs_stat,
            "df_1": N,
            "df_2": T - N - K,
            "alphas": alphas.tolist(),
            "mean_abs_alpha": float(np.mean(np.abs(alphas)))
        }


# ==============================================================================
# Model 2: Asness, Frazzini & Pedersen (2019) Quality Minus Junk (QMJ) Engine
# ==============================================================================
class QualityMinusJunkEngine:
    """Clifford S. Asness, Andrea Frazzini & Lasse Heje Pedersen (2019) QMJ.
    Defines Quality across 4 pillars: Profitability, Growth, Safety, Payout.
    Features:
    - Cross-sectional Winsorization and Z-score standardization
    - Percentile ranking and 4-pillar Composite Quality Index
    - Long/Short Quality vs Junk portfolio spread
    - 'Flight to Quality' crisis hedge correlation analysis.
    """

    @staticmethod
    def standardize_and_rank(values: np.ndarray) -> np.ndarray:
        """Winsorizes at 1st and 99th percentiles and computes standardized rank."""
        p1 = np.percentile(values, 1.0)
        p99 = np.percentile(values, 99.0)
        clipped = np.clip(values, p1, p99)
        std = np.std(clipped)
        if std < 1e-10:
            return np.zeros_like(values)
        z = (clipped - np.mean(clipped)) / std
        # Rank-order normalization to [0, 1]
        order = np.argsort(z)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.linspace(0.0, 1.0, len(values))
        return ranks

    @classmethod
    def compute_composite_quality_score(
        cls,
        roe: np.ndarray,
        gross_margin: np.ndarray,
        accruals_to_assets: np.ndarray,  # Negative for quality (lower accruals = higher earnings quality)
        growth_5yr_sales: np.ndarray,
        market_beta: np.ndarray,          # Negative for safety (lower beta = higher safety)
        leverage_debt_to_assets: np.ndarray,  # Negative for safety
        total_payout_yield: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Calculates 4 Quality pillars:
        1. Profitability: ROE + Gross Margin - Accruals
        2. Growth: 5-year sales growth
        3. Safety: -Beta - Leverage
        4. Payout: Total Payout Yield
        """
        # Pillar 1: Profitability
        z_roe = cls.standardize_and_rank(roe)
        z_gm = cls.standardize_and_rank(gross_margin)
        z_acc = cls.standardize_and_rank(-accruals_to_assets)
        prof_score = (z_roe + z_gm + z_acc) / 3.0

        # Pillar 2: Growth
        growth_score = cls.standardize_and_rank(growth_5yr_sales)

        # Pillar 3: Safety
        z_beta = cls.standardize_and_rank(-market_beta)
        z_lev = cls.standardize_and_rank(-leverage_debt_to_assets)
        safety_score = (z_beta + z_lev) / 2.0

        # Pillar 4: Payout
        payout_score = cls.standardize_and_rank(total_payout_yield)

        # Overall composite Quality score (equal-weighted average of 4 pillars)
        composite_quality = (prof_score + growth_score + safety_score + payout_score) / 4.0

        return {
            "profitability": prof_score,
            "growth": growth_score,
            "safety": safety_score,
            "payout": payout_score,
            "composite_quality": composite_quality
        }

    @staticmethod
    def construct_qmj_factor(
        returns_universe: np.ndarray,
        composite_quality: np.ndarray,
        top_decile_cutoff: float = 0.70,
        bottom_decile_cutoff: float = 0.30
    ) -> Dict[str, Any]:
        """Constructs Long Top Quality, Short Junk portfolio.
        Returns:
            qmj_return_series: (T,)
            sharpe_ratio: annualized Sharpe ratio
            flight_to_quality_correlation: correlation with market drawdown indicator
        """
        is_quality = composite_quality >= np.quantile(composite_quality, top_decile_cutoff)
        is_junk = composite_quality <= np.quantile(composite_quality, bottom_decile_cutoff)

        ret_quality = np.mean(returns_universe[:, is_quality], axis=1)
        ret_junk = np.mean(returns_universe[:, is_junk], axis=1)
        qmj_spread = ret_quality - ret_junk

        mean_spread = np.mean(qmj_spread)
        std_spread = np.std(qmj_spread)
        sharpe = (mean_spread / max(1e-8, std_spread)) * math.sqrt(252.0)

        # Flight to Quality test: during market downturns (market return < 0), does QMJ outperform?
        market_proxy = np.mean(returns_universe, axis=1)
        down_mask = market_proxy < 0.0
        alpha_in_down_market = float(np.mean(qmj_spread[down_mask])) if np.any(down_mask) else 0.0

        return {
            "qmj_spread": qmj_spread,
            "quality_mean": float(np.mean(ret_quality)),
            "junk_mean": float(np.mean(ret_junk)),
            "annualized_sharpe": float(sharpe),
            "alpha_in_down_market": alpha_in_down_market
        }


# ==============================================================================
# Model 3: James A. Ohlson (1980) O-Score Conditional Logit Bankruptcy Engine
# ==============================================================================
class OhlsonOScoreEngine:
    """James A. Ohlson (1980) O-Score Financial Distress Logit Model.
    P(Bankruptcy) = 1 / (1 + exp(-y))
    where:
    y = -1.32 - 0.407 * ln(TA / GNP) + 6.03 * (TL / TA) - 1.43 * (WC / TA)
        + 0.0757 * (CL / CA) - 1.72 * X - 2.37 * (NI / TA) - 1.83 * (FFO / TL)
        + 0.285 * Y - 0.521 * ((NI_t - NI_{t-1}) / (|NI_t| + |NI_{t-1}|))
    with X = 1 if TL > TA (insolvency), 0 otherwise.
         Y = 1 if NI negative in last 2 years, 0 otherwise.
    Default threshold: P > 0.38 indicates severe insolvency danger.
    """

    @staticmethod
    def calculate_o_score(
        total_assets: float,
        gnp_price_index: float,
        total_liabilities: float,
        working_capital: float,
        current_liabilities: float,
        current_assets: float,
        net_income: float,
        funds_from_operations: float,
        prior_net_income: float,
        two_year_net_income_negative: bool
    ) -> Dict[str, Any]:
        """Calculates Ohlson's y score and default probability."""
        if total_assets <= 0.0:
            raise ValueError("Total assets must be strictly positive.")

        # Scaled log size
        size_term = math.log(max(1e-6, total_assets / max(1e-6, gnp_price_index)))

        # Ratios
        tl_ta = total_liabilities / total_assets
        wc_ta = working_capital / total_assets
        cl_ca = current_liabilities / max(1e-6, current_assets)
        ni_ta = net_income / total_assets
        ffo_tl = funds_from_operations / max(1e-6, total_liabilities)

        # Binary indicator X: 1 if liabilities exceed assets (negative book equity)
        x_indicator = 1.0 if total_liabilities > total_assets else 0.0

        # Binary indicator Y: 1 if net income negative for last 2 years
        y_indicator = 1.0 if two_year_net_income_negative else 0.0

        # Change in net income
        denom_ni = abs(net_income) + abs(prior_net_income)
        delta_ni = (net_income - prior_net_income) / max(1e-6, denom_ni)

        # Ohlson logit formula
        y = (
            -1.32
            - 0.407 * size_term
            + 6.03 * tl_ta
            - 1.43 * wc_ta
            + 0.0757 * cl_ca
            - 1.72 * x_indicator
            - 2.37 * ni_ta
            - 1.83 * ffo_tl
            + 0.285 * y_indicator
            - 0.521 * delta_ni
        )

        prob_default = logistic_sigmoid(y)
        is_distressed = prob_default > 0.38

        return {
            "y_score": float(y),
            "prob_default": float(prob_default),
            "is_distressed": is_distressed,
            "size_component": float(-0.407 * size_term),
            "leverage_component": float(6.03 * tl_ta),
            "profitability_component": float(-2.37 * ni_ta)
        }

    @staticmethod
    def batch_classify(
        dataset: List[Dict[str, Any]],
        cutoff_threshold: float = 0.38
    ) -> Dict[str, Any]:
        """Classifies a portfolio of firms and reports distress rates."""
        results = []
        distressed_count = 0
        for firm in dataset:
            res = OhlsonOScoreEngine.calculate_o_score(**firm)
            results.append(res)
            if res["prob_default"] > cutoff_threshold:
                distressed_count += 1

        distress_rate = distressed_count / max(1, len(dataset))
        return {
            "distressed_count": distressed_count,
            "distress_rate": float(distress_rate),
            "individual_results": results
        }


# ==============================================================================
# Model 4: Fung & Hsieh (2001, 2004) Seven-Factor Trend Following Engine
# ==============================================================================
class FungHsiehSevenFactorEngine:
    """William Fung & David A. Hsieh (2001, 2004) 7-Factor Model for Hedge Funds.
    Trend followers (CTAs) produce option-like straddle returns:
    Primitive Trend-Following Strategies (PTFS):
    - PTFS FX (Currency lookback straddle)
    - PTFS Commodity (Commodity lookback straddle)
    - PTFS Bond (Interest rate lookback straddle)
    Combined with equity market, size spread, 10Y yield change, and Baa credit spread.
    Demonstrates 'Crisis Alpha' / smile payoff during volatility spikes.
    """

    @staticmethod
    def simulate_lookback_straddle_payoff(
        underlying_paths: np.ndarray
    ) -> np.ndarray:
        """Computes lookback straddle payoff: Max(S_t) - Min(S_t) scaled by initial S_0.
        Args:
            underlying_paths: (T, N_steps) asset price paths
        Returns:
            straddle_returns: (T,) normalized payoff
        """
        s0 = underlying_paths[:, 0]
        max_s = np.max(underlying_paths, axis=1)
        min_s = np.min(underlying_paths, axis=1)
        # Lookback call payoff: Max(S) - S_T; Lookback put: S_T - Min(S)
        # Total lookback straddle: Max(S) - Min(S)
        payoff = (max_s - min_s) / s0
        return payoff

    @staticmethod
    def fit_fung_hsieh_model(
        fund_excess_returns: np.ndarray,
        ptfs_bond: np.ndarray,
        ptfs_fx: np.ndarray,
        ptfs_commodity: np.ndarray,
        sp500_excess: np.ndarray,
        russell_minus_sp500: np.ndarray,
        delta_10y_yield: np.ndarray,
        delta_credit_spread: np.ndarray
    ) -> Dict[str, Any]:
        """Fits Fung-Hsieh 7-factor model via OLS."""
        T = len(fund_excess_returns)
        factor_matrix = np.column_stack([
            ptfs_bond,
            ptfs_fx,
            ptfs_commodity,
            sp500_excess,
            russell_minus_sp500,
            delta_10y_yield,
            delta_credit_spread
        ])

        X = np.column_stack([np.ones(T), factor_matrix])
        inv_XtX = np.linalg.pinv(X.T @ X)
        params = inv_XtX @ (X.T @ fund_excess_returns)
        alpha = float(params[0])
        betas = params[1:]

        fitted = X @ params
        residuals = fund_excess_returns - fitted
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((fund_excess_returns - np.mean(fund_excess_returns)) ** 2)
        r2 = 1.0 - (ss_res / max(1e-12, ss_tot))

        dof = T - 8
        sigma2 = ss_res / max(1, dof)
        var_params = sigma2 * np.diag(inv_XtX)
        t_stats = params / np.sqrt(np.maximum(1e-12, var_params))

        factor_names = ["PTFS_Bond", "PTFS_FX", "PTFS_Commodity", "SP500", "Size_Spread", "Delta_10Y", "Delta_Credit"]
        beta_dict = {name: float(b) for name, b in zip(factor_names, betas)}
        t_stat_dict = {name: float(t) for name, t in zip(factor_names, t_stats[1:])}

        # Trend Exposure Ratio: sum of weights on PTFS vs traditional equity
        ptfs_exposure = sum(abs(beta_dict[k]) for k in ["PTFS_Bond", "PTFS_FX", "PTFS_Commodity"])

        return {
            "alpha": alpha,
            "t_alpha": float(t_stats[0]),
            "r_squared": float(r2),
            "betas": beta_dict,
            "t_stats": t_stat_dict,
            "ptfs_total_exposure": float(ptfs_exposure)
        }


# ==============================================================================
# Model 5: Robert J. Shiller (1981, 2000, 2015) CAPE, ECY & 10Y Return Engine
# ==============================================================================
class ShillerCAPEReturnDecompositionEngine:
    """Robert J. Shiller Cyclically Adjusted P/E (CAPE) & Excess CAPE Yield (ECY).
    Features:
    - 10-year inflation-adjusted real earnings moving average
    - Excess CAPE Yield (ECY) = (1 / CAPE) - Real Bond Yield
    - Gordon-Shiller 10-Year Return Decomposition:
      R_10Y ~ Dividend Yield + Real EPS Growth + (1/10) * ln(CAPE_terminal / CAPE_current)
    - Ornstein-Uhlenbeck mean-reverting valuation forecast.
    """

    @staticmethod
    def calculate_cape_and_ecy(
        nominal_price: float,
        trailing_10yr_nominal_earnings: np.ndarray,
        cpi_series: np.ndarray,
        current_cpi: float,
        real_10yr_bond_yield: float
    ) -> Dict[str, Any]:
        """Calculates CAPE and Excess CAPE Yield."""
        if len(trailing_10yr_nominal_earnings) != len(cpi_series):
            raise ValueError("Earnings and CPI series must have identical length.")

        # Inflate nominal earnings to current CPI terms
        inflation_factors = current_cpi / np.maximum(1e-6, cpi_series)
        real_earnings = trailing_10yr_nominal_earnings * inflation_factors
        avg_real_earnings = np.mean(real_earnings)

        if avg_real_earnings <= 0.0:
            raise ValueError("Average 10-year real earnings must be positive.")

        cape = nominal_price / avg_real_earnings
        earnings_yield = 1.0 / cape
        ecy = earnings_yield - real_10yr_bond_yield

        return {
            "cape": float(cape),
            "earnings_yield": float(earnings_yield),
            "excess_cape_yield": float(ecy),
            "avg_real_earnings": float(avg_real_earnings)
        }

    @staticmethod
    def decompose_10yr_forward_return(
        current_cape: float,
        target_terminal_cape: float,
        current_dividend_yield: float,
        expected_real_eps_growth: float,
        horizon_years: float = 10.0
    ) -> Dict[str, Any]:
        """Decomposes expected 10-year annualized real equity return:
        E[R] = Div_Yield + g_real + (1 / T) * ln(CAPE_terminal / CAPE_current)
        """
        if current_cape <= 0.0 or target_terminal_cape <= 0.0:
            raise ValueError("CAPE values must be strictly positive.")

        valuation_expansion_annual = (1.0 / horizon_years) * math.log(target_terminal_cape / current_cape)
        total_expected_return = current_dividend_yield + expected_real_eps_growth + valuation_expansion_annual

        return {
            "total_expected_real_return": float(total_expected_return),
            "dividend_yield_contribution": float(current_dividend_yield),
            "earnings_growth_contribution": float(expected_real_eps_growth),
            "valuation_multiple_contribution": float(valuation_expansion_annual),
            "is_multiple_contracting": valuation_expansion_annual < 0.0
        }

    @staticmethod
    def simulate_mean_reverting_cape(
        current_cape: float,
        long_term_median_cape: float,
        speed_of_reversion: float,
        annual_volatility: float,
        horizon_years: int = 10,
        n_simulations: int = 1000,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Simulates Ornstein-Uhlenbeck process for ln(CAPE):
        d(ln(CAPE)) = kappa * (ln(CAPE_bar) - ln(CAPE)) dt + sigma * dW
        """
        np.random.seed(seed)
        dt = 1.0 / 12.0
        n_steps = horizon_years * 12
        ln_cape_bar = math.log(long_term_median_cape)

        ln_cape = np.full(n_simulations, math.log(current_cape))
        for _ in range(n_steps):
            dw = np.random.normal(0.0, math.sqrt(dt), n_simulations)
            ln_cape += speed_of_reversion * (ln_cape_bar - ln_cape) * dt + annual_volatility * dw

        terminal_capes = np.exp(ln_cape)
        median_terminal = float(np.median(terminal_capes))
        q05 = float(np.percentile(terminal_capes, 5.0))
        q95 = float(np.percentile(terminal_capes, 95.0))

        return {
            "median_terminal_cape": median_terminal,
            "q05_terminal_cape": q05,
            "q95_terminal_cape": q95,
            "mean_reversion_half_life": float(math.log(2.0) / max(1e-6, speed_of_reversion))
        }


# ==============================================================================
# Model 6: Aswath Damodaran (2012, 2024) Synthetic Rating, CRP & WACC Engine
# ==============================================================================
class DamodaranCorporateCostOfCapitalEngine:
    """Aswath Damodaran Synthetic Credit Rating, Country Risk Premium & Optimal WACC.
    Features:
    - Interest Coverage Ratio (ICR) to Synthetic Rating & Default Spread mapping
    - Country Risk Premium: CRP = Sovereign Spread * (Sigma_Equity / Sigma_Bond)
    - Hamada leveraged beta adjustment: Beta_L = Beta_U * [1 + (1 - T) * (D / E)]
    - Endogenous Cost of Debt and WACC minimization across capital structure grid.
    """

    # Damodaran standard lookup table for large manufacturing/service firms
    RATING_GRID = [
        (8.50, "AAA", 0.0060),
        (6.50, "AA", 0.0085),
        (5.50, "A+", 0.0110),
        (4.25, "A", 0.0125),
        (3.00, "BBB", 0.0160),
        (2.50, "BB+", 0.0225),
        (2.00, "BB", 0.0300),
        (1.50, "B+", 0.0425),
        (1.25, "B", 0.0550),
        (0.80, "CCC", 0.0800),
        (0.00, "D", 0.1200),
    ]

    @classmethod
    def get_synthetic_rating(cls, interest_coverage_ratio: float) -> Tuple[str, float]:
        """Maps Interest Coverage Ratio (EBIT / Interest Expense) to rating and spread."""
        if interest_coverage_ratio <= 0.0:
            return ("D", 0.1200)
        for threshold, rating, spread in cls.RATING_GRID:
            if interest_coverage_ratio >= threshold:
                return (rating, spread)
        return ("D", 0.1200)

    @staticmethod
    def calculate_country_risk_premium(
        sovereign_default_spread: float,
        equity_volatility: float,
        sovereign_bond_volatility: float
    ) -> float:
        """Damodaran CRP = Sovereign Spread * (Sigma_Equity / Sigma_Bond)."""
        relative_vol = equity_volatility / max(1e-6, sovereign_bond_volatility)
        return float(sovereign_default_spread * relative_vol)

    @classmethod
    def calculate_cost_of_capital(
        cls,
        ebit: float,
        debt: float,
        equity_market_value: float,
        unlevered_beta: float,
        risk_free_rate: float,
        mature_market_erp: float,
        tax_rate: float,
        country_risk_premium: float = 0.0,
        firm_revenue_exposure_to_em: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates WACC with endogenous credit rating and Hamada beta."""
        total_value = debt + equity_market_value
        debt_to_equity = debt / max(1e-6, equity_market_value)
        debt_ratio = debt / total_value

        # Hamada equation
        levered_beta = unlevered_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)

        # Cost of Equity
        cost_of_equity = (
            risk_free_rate
            + levered_beta * mature_market_erp
            + firm_revenue_exposure_to_em * country_risk_premium
        )

        # Initial interest rate estimation
        # Iteratively solve for interest expense = Debt * K_d
        k_d_pre_tax = risk_free_rate + 0.015  # seed spread
        for _ in range(5):
            interest_expense = debt * k_d_pre_tax
            icr = ebit / max(1e-4, interest_expense)
            rating, spread = cls.get_synthetic_rating(icr)
            k_d_pre_tax = risk_free_rate + spread

        k_d_after_tax = k_d_pre_tax * (1.0 - tax_rate)

        wacc = debt_ratio * k_d_after_tax + (1.0 - debt_ratio) * cost_of_equity

        return {
            "wacc": float(wacc),
            "cost_of_equity": float(cost_of_equity),
            "cost_of_debt_pre_tax": float(k_d_pre_tax),
            "cost_of_debt_after_tax": float(k_d_after_tax),
            "synthetic_rating": rating,
            "default_spread": float(spread),
            "levered_beta": float(levered_beta),
            "icr": float(icr)
        }

    @classmethod
    def optimize_capital_structure(
        cls,
        ebit: float,
        total_firm_enterprise_value: float,
        unlevered_beta: float,
        risk_free_rate: float,
        mature_market_erp: float,
        tax_rate: float,
        growth_rate: float = 0.02,
        grid_points: int = 19
    ) -> Dict[str, Any]:
        """Sweeps debt ratios from 0% to 90% to find optimal debt ratio minimizing WACC."""
        debt_ratios = np.linspace(0.0, 0.90, grid_points)
        wacc_list = []
        firm_value_list = []
        ratings = []

        best_wacc = float("inf")
        optimal_debt_ratio = 0.0
        best_rating = "AAA"

        free_cash_flow_firm = ebit * (1.0 - tax_rate)

        for d_ratio in debt_ratios:
            debt = d_ratio * total_firm_enterprise_value
            equity = total_firm_enterprise_value - debt
            res = cls.calculate_cost_of_capital(
                ebit=ebit,
                debt=debt,
                equity_market_value=equity,
                unlevered_beta=unlevered_beta,
                risk_free_rate=risk_free_rate,
                mature_market_erp=mature_market_erp,
                tax_rate=tax_rate
            )
            w = res["wacc"]
            # Firm value under constant growth model V = FCFF / (WACC - g)
            denom = max(0.005, w - growth_rate)
            firm_val = free_cash_flow_firm / denom

            wacc_list.append(w)
            firm_value_list.append(firm_val)
            ratings.append(res["synthetic_rating"])

            if w < best_wacc:
                best_wacc = w
                optimal_debt_ratio = float(d_ratio)
                best_rating = res["synthetic_rating"]

        return {
            "optimal_debt_ratio": optimal_debt_ratio,
            "minimum_wacc": float(best_wacc),
            "optimal_rating": best_rating,
            "debt_ratios": debt_ratios.tolist(),
            "wacc_curve": wacc_list,
            "firm_values": firm_value_list
        }


# ==============================================================================
# Pytest Test Verification Suite
# ==============================================================================
class TestFaz59QuantitativeFinanceEngines:
    """Agentic TDD Verification Suite enforcing 100% test pass rate."""

    def test_fama_french_five_factor_engine(self):
        """Model 1: Verify Fama-French 5-Factor regression, factor construction, and HML redundancy."""
        np.random.seed(42)
        T = 200
        N = 10

        # Simulate factors
        mkt = np.random.normal(0.008, 0.04, T)
        smb = np.random.normal(0.002, 0.02, T)
        rmw = np.random.normal(0.004, 0.02, T)
        cma = np.random.normal(0.003, 0.015, T)

        # HML as partially spanned by RMW and CMA + small noise
        hml = 0.1 * mkt - 0.2 * smb + 0.45 * rmw + 0.60 * cma + np.random.normal(0.0, 0.005, T)

        factors = np.column_stack([mkt, smb, hml, rmw, cma])

        # Test Asset
        true_betas = np.array([1.10, 0.35, 0.20, 0.40, -0.25])
        asset_ret = 0.001 + factors @ true_betas + np.random.normal(0, 0.01, T)

        fit = FamaFrenchFiveFactorEngine.fit_factor_model(asset_ret, factors)
        assert abs(fit["betas"][0] - 1.10) < 0.15
        assert abs(fit["betas"][1] - 0.35) < 0.15
        assert fit["r_squared"] > 0.85

        # 2. Factor Spanning / Redundancy Test
        span_res = FamaFrenchFiveFactorEngine.test_hml_factor_spanning(hml, mkt, smb, rmw, cma)
        assert span_res["is_redundant"] is True
        assert span_res["r_squared"] > 0.80

        # 3. Factor Construction
        universe_ret = np.random.normal(0.01, 0.05, (T, 40))
        caps = np.random.uniform(100, 10000, 40)
        prof = np.random.uniform(0.05, 0.35, 40)
        inv = np.random.uniform(0.01, 0.20, 40)

        factor_build = FamaFrenchFiveFactorEngine.construct_rmw_and_cma_factors(
            universe_ret, caps, prof, inv
        )
        assert len(factor_build["RMW"]) == T
        assert len(factor_build["CMA"]) == T

        # 4. GRS Test
        assets_ret = factors @ np.random.uniform(0.5, 1.5, (5, N)) + np.random.normal(0, 0.01, (T, N))
        grs = FamaFrenchFiveFactorEngine.gibbons_ross_shanken_test(assets_ret, factors)
        assert grs["grs_statistic"] > 0.0
        assert grs["df_1"] == N
        assert grs["df_2"] == T - N - 5

    def test_quality_minus_junk_engine(self):
        """Model 2: Verify Asness-Frazzini-Pedersen QMJ standardization, scoring, and flight-to-quality."""
        np.random.seed(101)
        N_firms = 50
        T = 150

        roe = np.random.normal(0.18, 0.08, N_firms)
        gm = np.random.normal(0.40, 0.12, N_firms)
        accruals = np.random.normal(0.03, 0.04, N_firms)
        growth = np.random.normal(0.08, 0.05, N_firms)
        beta = np.random.normal(1.0, 0.3, N_firms)
        lev = np.random.normal(0.35, 0.15, N_firms)
        payout = np.random.normal(0.03, 0.02, N_firms)

        q_scores = QualityMinusJunkEngine.compute_composite_quality_score(
            roe, gm, accruals, growth, beta, lev, payout
        )

        assert len(q_scores["composite_quality"]) == N_firms
        assert np.all(q_scores["composite_quality"] >= 0.0)
        assert np.all(q_scores["composite_quality"] <= 1.0)

        # QMJ Factor construction
        # High quality firms should have positive drift, junk higher volatility and lower drift
        comp_q = q_scores["composite_quality"]
        returns = np.zeros((T, N_firms))
        market_shock = np.random.normal(-0.005, 0.02, T)

        for i in range(N_firms):
            drift = 0.0005 + 0.0005 * comp_q[i]
            # Junk suffers more in market drops
            sens = 1.2 - 0.4 * comp_q[i]
            returns[:, i] = drift + sens * market_shock + np.random.normal(0, 0.015, T)

        factor_res = QualityMinusJunkEngine.construct_qmj_factor(returns, comp_q)
        assert factor_res["quality_mean"] > factor_res["junk_mean"]
        assert factor_res["annualized_sharpe"] > 0.0
        # In down market, quality outperforms junk
        assert factor_res["alpha_in_down_market"] > 0.0

    def test_ohlson_o_score_engine(self):
        """Model 3: Verify Ohlson O-Score conditional logit distress probability and classification."""
        # 1. Healthy Corporation (Blue Chip)
        healthy_res = OhlsonOScoreEngine.calculate_o_score(
            total_assets=10000.0,
            gnp_price_index=110.0,
            total_liabilities=3000.0,
            working_capital=2500.0,
            current_liabilities=1000.0,
            current_assets=3500.0,
            net_income=1200.0,
            funds_from_operations=1500.0,
            prior_net_income=1000.0,
            two_year_net_income_negative=False
        )

        assert healthy_res["prob_default"] < 0.10
        assert healthy_res["is_distressed"] is False
        assert healthy_res["profitability_component"] < 0.0  # Profitable reduces distress

        # 2. Distressed Zombie Firm
        distressed_res = OhlsonOScoreEngine.calculate_o_score(
            total_assets=500.0,
            gnp_price_index=110.0,
            total_liabilities=650.0,   # Negative equity (TL > TA)
            working_capital=-150.0,
            current_liabilities=300.0,
            current_assets=150.0,
            net_income=-120.0,
            funds_from_operations=-80.0,
            prior_net_income=-100.0,
            two_year_net_income_negative=True
        )

        assert distressed_res["prob_default"] > 0.38
        assert distressed_res["is_distressed"] is True
        assert distressed_res["y_score"] > healthy_res["y_score"]

        # 3. Batch Portfolio Classification
        dataset = [
            {
                "total_assets": 5000.0, "gnp_price_index": 100.0, "total_liabilities": 2000.0,
                "working_capital": 1000.0, "current_liabilities": 800.0, "current_assets": 1800.0,
                "net_income": 400.0, "funds_from_operations": 500.0, "prior_net_income": 350.0,
                "two_year_net_income_negative": False
            },
            {
                "total_assets": 400.0, "gnp_price_index": 100.0, "total_liabilities": 500.0,
                "working_capital": -100.0, "current_liabilities": 250.0, "current_assets": 150.0,
                "net_income": -80.0, "funds_from_operations": -30.0, "prior_net_income": -60.0,
                "two_year_net_income_negative": True
            }
        ]
        batch_res = OhlsonOScoreEngine.batch_classify(dataset)
        assert batch_res["distressed_count"] == 1
        assert abs(batch_res["distress_rate"] - 0.50) < 1e-4

    def test_fung_hsieh_seven_factor_engine(self):
        """Model 4: Verify Fung-Hsieh 7-factor trend following decomposition and lookback straddle."""
        np.random.seed(88)
        T = 180
        n_steps = 22

        # Simulate asset paths for lookback straddle
        fx_paths = 100.0 * np.exp(np.cumsum(np.random.normal(0, 0.02, (T, n_steps)), axis=1))
        com_paths = 100.0 * np.exp(np.cumsum(np.random.normal(0, 0.03, (T, n_steps)), axis=1))
        bond_paths = 100.0 * np.exp(np.cumsum(np.random.normal(0, 0.01, (T, n_steps)), axis=1))

        ptfs_fx = FungHsiehSevenFactorEngine.simulate_lookback_straddle_payoff(fx_paths)
        ptfs_com = FungHsiehSevenFactorEngine.simulate_lookback_straddle_payoff(com_paths)
        ptfs_bond = FungHsiehSevenFactorEngine.simulate_lookback_straddle_payoff(bond_paths)

        assert np.all(ptfs_fx > 0.0)  # Straddles always have non-negative payoff
        assert np.all(ptfs_com > 0.0)
        assert np.all(ptfs_bond > 0.0)

        # Market factors
        sp500 = np.random.normal(0.008, 0.035, T)
        size_spread = np.random.normal(0.001, 0.015, T)
        d_10y = np.random.normal(0.0, 0.005, T)
        d_credit = np.random.normal(0.0, 0.003, T)

        # Synthetic Trend Following Fund
        cta_returns = (
            0.002
            + 0.35 * ptfs_bond
            + 0.40 * ptfs_fx
            + 0.30 * ptfs_com
            - 0.10 * sp500
            + np.random.normal(0, 0.005, T)
        )

        res = FungHsiehSevenFactorEngine.fit_fung_hsieh_model(
            cta_returns, ptfs_bond, ptfs_fx, ptfs_com, sp500, size_spread, d_10y, d_credit
        )

        assert res["r_squared"] > 0.75
        assert res["betas"]["PTFS_Bond"] > 0.25
        assert res["betas"]["PTFS_FX"] > 0.30
        assert res["betas"]["PTFS_Commodity"] > 0.20
        assert res["ptfs_total_exposure"] > 0.80

    def test_shiller_cape_return_decomposition_engine(self):
        """Model 5: Verify Shiller CAPE, Excess CAPE Yield, and 10Y return decomposition."""
        np.random.seed(55)
        # 10 years of trailing earnings (10 annual observations)
        nominal_earnings = np.array([25.0, 27.0, 30.0, 28.0, 33.0, 36.0, 40.0, 42.0, 45.0, 50.0])
        cpi = np.array([180.0, 185.0, 190.0, 195.0, 202.0, 210.0, 218.0, 225.0, 235.0, 245.0])
        current_cpi = 245.0
        nominal_price = 1500.0
        real_10y_yield = 0.018

        cape_res = ShillerCAPEReturnDecompositionEngine.calculate_cape_and_ecy(
            nominal_price, nominal_earnings, cpi, current_cpi, real_10y_yield
        )

        assert cape_res["cape"] > 15.0
        assert cape_res["earnings_yield"] == 1.0 / cape_res["cape"]
        assert cape_res["excess_cape_yield"] == cape_res["earnings_yield"] - real_10y_yield

        # 2. Return Decomposition
        # If CAPE is elevated at 30 and expected to mean-revert to 20:
        decomp = ShillerCAPEReturnDecompositionEngine.decompose_10yr_forward_return(
            current_cape=30.0,
            target_terminal_cape=20.0,
            current_dividend_yield=0.018,
            expected_real_eps_growth=0.025,
            horizon_years=10.0
        )

        assert decomp["is_multiple_contracting"] is True
        assert decomp["valuation_multiple_contribution"] < 0.0
        assert abs(decomp["total_expected_real_return"] - (0.018 + 0.025 + decomp["valuation_multiple_contribution"])) < 1e-6

        # 3. Mean Reverting Simulation
        sim_res = ShillerCAPEReturnDecompositionEngine.simulate_mean_reverting_cape(
            current_cape=32.0,
            long_term_median_cape=18.0,
            speed_of_reversion=0.15,
            annual_volatility=0.20,
            horizon_years=10,
            n_simulations=500
        )
        assert sim_res["median_terminal_cape"] < 32.0  # Mean reverts downwards towards 18
        assert sim_res["mean_reversion_half_life"] > 0.0

    def test_damodaran_cost_of_capital_engine(self):
        """Model 6: Verify Damodaran synthetic rating, country risk premium, and optimal WACC capital structure."""
        # 1. Synthetic Rating
        rating, spread = DamodaranCorporateCostOfCapitalEngine.get_synthetic_rating(5.8)
        assert rating == "A+"
        assert spread == 0.0110

        rating_low, spread_low = DamodaranCorporateCostOfCapitalEngine.get_synthetic_rating(1.1)
        assert rating_low == "CCC"
        assert spread_low == 0.0800

        # 2. Country Risk Premium
        # Emerging market: sovereign CDS spread = 2.5%, equity vol = 24%, bond vol = 16%
        crp = DamodaranCorporateCostOfCapitalEngine.calculate_country_risk_premium(
            sovereign_default_spread=0.025,
            equity_volatility=0.24,
            sovereign_bond_volatility=0.16
        )
        assert abs(crp - 0.0375) < 1e-6  # 0.025 * (24 / 16) = 0.0375 (3.75%)

        # 3. Cost of Capital Calculation
        coc = DamodaranCorporateCostOfCapitalEngine.calculate_cost_of_capital(
            ebit=500.0,
            debt=800.0,
            equity_market_value=3200.0,
            unlevered_beta=0.90,
            risk_free_rate=0.04,
            mature_market_erp=0.05,
            tax_rate=0.25,
            country_risk_premium=crp,
            firm_revenue_exposure_to_em=0.40
        )

        assert coc["levered_beta"] > 0.90  # Hamada formula increases beta
        assert coc["cost_of_equity"] > 0.04
        assert coc["cost_of_debt_pre_tax"] > 0.04
        assert coc["wacc"] > 0.0

        # 4. Optimal Capital Structure Search
        opt_res = DamodaranCorporateCostOfCapitalEngine.optimize_capital_structure(
            ebit=500.0,
            total_firm_enterprise_value=4000.0,
            unlevered_beta=0.90,
            risk_free_rate=0.04,
            mature_market_erp=0.05,
            tax_rate=0.25,
            growth_rate=0.02
        )

        assert 0.10 <= opt_res["optimal_debt_ratio"] <= 0.75
        assert opt_res["minimum_wacc"] < max(opt_res["wacc_curve"])
        assert len(opt_res["wacc_curve"]) == 19
