"""Programmatic TDD Verification Suite for Faz 61 Quantitative Finance Engines.

Models:
1. Lars Peter Hansen (1982) & Alastair R. Hall (2005): Generalized Method of Moments (GMM), Two-Stage Optimal Weighting Matrix (W* = S^-1), Newey-West (1987) HAC Spectral Covariance & Hansen's J-Test of Overidentifying Restrictions
2. Robert Novy-Marx (2013): Gross Profitability Premium (GP/A), Orthogonal Quality-Value Synergy & True Economic Profitability Factor Engine
3. Viral V. Acharya & Lasse Heje Pedersen (2005): Liquidity-Adjusted CAPM (LCAPM), 4-Beta Risk Decomposition (Market Beta, Commonality in Liquidity, Flight-to-Liquidity, Crash Liquidity Dry-up) & Net Illiquidity Return Premium
4. Rajnish Mehra & Edward C. Prescott (1985) / Robert E. Lucas Jr. (1978): Consumption-Based Capital Asset Pricing Model (CCAPM), Lucas Tree Economy, CRRA Impossibility Bound & The Equity Premium Puzzle Engine
5. H. Gifford Fong & Oldrich A. Vasicek (1984) / Stephen J. Brown & Philip H. Dybvig (1986): Yield Curve Immunization under Non-Parallel Shifts, M-Square (M^2) Cash Flow Dispersion Minimization & Convexity Risk Engine
6. Richard C. Grinold (1989), Ronald N. Kahn (2000) & Roger Clarke, Harindra de Silva, Steven Thorley (2002): The Generalized Fundamental Law of Active Management (FLAM), Transfer Coefficient (TC), Information Coefficient (IC), Strategy Breadth (BR) & Alpha Sizing Engine
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


def regularized_gamma_p(a: float, x: float) -> float:
    """Lower regularized incomplete gamma function P(a, x) for Chi-Square CDF.
    Used for chi-square cumulative distribution function: CDF(chi2, k) = P(k/2, chi2/2).
    """
    if x <= 0.0 or a <= 0.0:
        return 0.0
    if x < a + 1.0:
        # Series expansion
        ap = a
        sum_val = 1.0 / a
        del_val = sum_val
        for _ in range(100):
            ap += 1.0
            del_val *= x / ap
            sum_val += del_val
            if abs(del_val) < abs(sum_val) * 1e-12:
                break
        return sum_val * math.exp(-x + a * math.log(x) - math.lgamma(a))
    else:
        # Continued fraction approximation for upper gamma Q(a, x), then P = 1 - Q
        b = x + 1.0 - a
        c = 1e30
        d = 1.0 / b
        h = d
        for i in range(1, 100):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            del_val = d * c
            h *= del_val
            if abs(del_val - 1.0) < 1e-12:
                break
        q_val = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
        return max(0.0, min(1.0, 1.0 - q_val))


def chi2_cdf(x: float, df: int) -> float:
    """Cumulative distribution function of chi-square distribution with df degrees of freedom."""
    if x <= 0.0 or df <= 0:
        return 0.0
    return regularized_gamma_p(df / 2.0, x / 2.0)


# ==============================================================================
# Model 1: Lars Peter Hansen (1982) & Alastair R. Hall (2005) GMM Engine
# ==============================================================================
class GeneralizedMethodOfMomentsEngine:
    """Lars Peter Hansen (1982) & Alastair R. Hall (2005) GMM Engine.
    
    Provides 2-step optimal GMM estimation, Newey-West (1987) HAC covariance matrix,
    asymptotic standard errors, and Hansen's J-test of overidentifying restrictions.
    Moments: E[Z_t' (y_t - X_t * theta)] = 0.
    """

    @staticmethod
    def compute_newey_west_hac(
        moment_errors: np.ndarray,
        max_lags: int = 2
    ) -> np.ndarray:
        """Computes Newey-West (1987) Heteroskedasticity and Autocorrelation Consistent
        (HAC) spectral covariance matrix S with Bartlett kernel:
            S = Gamma_0 + sum_{j=1}^L (1 - j / (L+1)) * (Gamma_j + Gamma_j')
        """
        T, q = moment_errors.shape
        gamma_0 = (moment_errors.T @ moment_errors) / T
        S = gamma_0.copy()

        for j in range(1, max_lags + 1):
            weight = 1.0 - (j / (max_lags + 1.0))
            gamma_j = (moment_errors[j:].T @ moment_errors[:-j]) / T
            S += weight * (gamma_j + gamma_j.T)

        # Enforce positive semi-definiteness via eigenvalue thresholding
        eigvals, eigvecs = np.linalg.eigh(S)
        eigvals = np.maximum(eigvals, 1e-8)
        S_psd = eigvecs @ np.diag(eigvals) @ eigvecs.T
        return S_psd

    @classmethod
    def estimate_linear_gmm(
        cls,
        y: np.ndarray,
        X: np.ndarray,
        Z: np.ndarray,
        max_lags: int = 2
    ) -> Dict[str, Any]:
        """Runs 2-Step Optimal GMM for linear model y = X * theta + e with instruments Z.
        
        Args:
            y: Dependent variable array of shape (T, 1) or (T,)
            X: Regressors array of shape (T, p)
            Z: Instruments array of shape (T, q) with q >= p
            max_lags: Maximum lag for Newey-West HAC
            
        Returns:
            Dictionary containing estimates, standard errors, J-stat, p-value, and diagnostics.
        """
        y = np.asarray(y, dtype=float).reshape(-1, 1)
        X = np.asarray(X, dtype=float)
        Z = np.asarray(Z, dtype=float)
        T, p = X.shape
        _, q = Z.shape

        if q < p:
            raise ValueError(f"Model is under-identified: q={q} instruments < p={p} parameters.")

        # Step 1: 2SLS / Identity Weighting W_1 = (Z'Z / T)^(-1)
        ZtZ = (Z.T @ Z) / T
        W_1 = np.linalg.pinv(ZtZ)
        
        ZtX = (Z.T @ X) / T
        Zty = (Z.T @ y) / T

        bread_1 = ZtX.T @ W_1 @ ZtX
        theta_1 = np.linalg.pinv(bread_1) @ (ZtX.T @ W_1 @ Zty)

        # First stage residuals and moment errors: u_t = Z_t * e_t
        resid_1 = y - X @ theta_1
        moment_errors_1 = Z * resid_1  # Shape (T, q)

        # Compute Newey-West HAC matrix S
        S = cls.compute_newey_west_hac(moment_errors_1, max_lags=max_lags)
        W_2 = np.linalg.pinv(S)

        # Step 2: Optimal GMM with W_2 = S^-1
        bread_2 = ZtX.T @ W_2 @ ZtX
        theta_2 = np.linalg.pinv(bread_2) @ (ZtX.T @ W_2 @ Zty)

        # Second stage residuals and moments
        resid_2 = y - X @ theta_2
        g_bar = (Z.T @ resid_2) / T  # Shape (q, 1)

        # Asymptotic Covariance of theta: V = (1/T) * (ZtX' * W_2 * ZtX)^(-1)
        V_theta = np.linalg.pinv(bread_2) / T
        std_errors = np.sqrt(np.maximum(np.diag(V_theta), 1e-12))
        t_stats = (theta_2.flatten() / std_errors).tolist()

        # Hansen's J-Test: J = T * g_bar' * W_2 * g_bar ~ Chi-Square(q - p)
        J_stat = float(T * (g_bar.T @ W_2 @ g_bar)[0, 0])
        df = q - p
        if df > 0:
            j_p_value = 1.0 - chi2_cdf(J_stat, df)
        else:
            j_p_value = 1.0  # Exactly identified model (J = 0 identically)

        return {
            "theta_step1": theta_1.flatten().tolist(),
            "theta_step2": theta_2.flatten().tolist(),
            "std_errors": std_errors.tolist(),
            "t_stats": t_stats,
            "J_stat": J_stat,
            "degrees_of_freedom": df,
            "J_p_value": j_p_value,
            "model_rejected": j_p_value < 0.05,
            "sample_size": T,
            "num_instruments": q,
            "num_parameters": p
        }


# ==============================================================================
# Model 2: Robert Novy-Marx (2013) Gross Profitability Premium Engine
# ==============================================================================
class NovyMarxGrossProfitabilityEngine:
    """Robert Novy-Marx (2013) Gross Profitability Premium (GP/A).
    
    Demonstrates that Gross Profits-to-Assets (GP/A) has extraordinary power
    in predicting the cross-section of equity returns, acts as the orthogonal
    counterpart to Value (HML), and dramatically expands the efficient frontier.
        GP/A = (Revenues - Cost of Goods Sold) / Total Assets
    """

    @staticmethod
    def compute_gross_profitability(
        revenues: np.ndarray,
        cogs: np.ndarray,
        total_assets: np.ndarray
    ) -> np.ndarray:
        """Computes Gross Profitability (GP/A) ratio for a panel/vector of firms."""
        rev = np.asarray(revenues, dtype=float)
        cost = np.asarray(cogs, dtype=float)
        assets = np.asarray(total_assets, dtype=float)
        gp = rev - cost
        return np.where(assets > 0, gp / assets, 0.0)

    @staticmethod
    def sort_and_construct_pma_factor(
        gp_a: np.ndarray,
        returns: np.ndarray,
        n_quantiles: int = 5
    ) -> Dict[str, Any]:
        """Constructs Profitable Minus Unprofitable (PMA) long-short factor.
        Sorts firms into quantiles by GP/A and computes the spread return.
        """
        gp_a = np.asarray(gp_a, dtype=float)
        returns = np.asarray(returns, dtype=float)

        # Determine quantile thresholds
        percentiles = np.linspace(0, 100, n_quantiles + 1)
        bins = np.percentile(gp_a, percentiles)

        quantile_returns = []
        for i in range(n_quantiles):
            mask = (gp_a >= bins[i]) & (gp_a <= bins[i + 1] if i == n_quantiles - 1 else gp_a < bins[i + 1])
            if np.any(mask):
                quantile_returns.append(float(np.mean(returns[mask])))
            else:
                quantile_returns.append(0.0)

        # High minus Low Gross Profitability
        pma_spread = quantile_returns[-1] - quantile_returns[0]

        return {
            "quantile_returns": quantile_returns,
            "pma_spread": pma_spread,
            "high_profitability_ret": quantile_returns[-1],
            "low_profitability_ret": quantile_returns[0],
            "is_monotonic_trend": quantile_returns[-1] > quantile_returns[0]
        }

    @staticmethod
    def double_sort_value_profitability(
        bm_ratio: np.ndarray,
        gp_a: np.ndarray,
        returns: np.ndarray
    ) -> Dict[str, Any]:
        """Executes a 2x2 double-sort on Book-to-Market (Value) and GP/A (Profitability).
        
        Demonstrates that Value and Profitability are negatively correlated in characteristics
        but positively synergistic in portfolio returns.
        """
        bm = np.asarray(bm_ratio, dtype=float)
        gp = np.asarray(gp_a, dtype=float)
        ret = np.asarray(returns, dtype=float)

        med_bm = np.median(bm)
        med_gp = np.median(gp)

        # Quadrants:
        # Q1: Low BM, Low GP (Growth / Unprofitable - "Junk Growth")
        # Q2: Low BM, High GP (Growth / Profitable - "Quality Growth")
        # Q3: High BM, Low GP (Value / Unprofitable - "Value Traps")
        # Q4: High BM, High GP (Value / Profitable - "Super Quality Value")
        q1_mask = (bm < med_bm) & (gp < med_gp)
        q2_mask = (bm < med_bm) & (gp >= med_gp)
        q3_mask = (bm >= med_bm) & (gp < med_gp)
        q4_mask = (bm >= med_bm) & (gp >= med_gp)

        r_q1 = float(np.mean(ret[q1_mask])) if np.any(q1_mask) else 0.0
        r_q2 = float(np.mean(ret[q2_mask])) if np.any(q2_mask) else 0.0
        r_q3 = float(np.mean(ret[q3_mask])) if np.any(q3_mask) else 0.0
        r_q4 = float(np.mean(ret[q4_mask])) if np.any(q4_mask) else 0.0

        # Controlling for Value: Profitability spread among Value firms: Q4 - Q3
        gp_spread_in_value = r_q4 - r_q3
        # Controlling for Profitability: Value spread among Profitable firms: Q4 - Q2
        value_spread_in_profitable = r_q4 - r_q2

        # Combined synergistic portfolio (equal weight Q4 long vs Q1 short)
        synergistic_spread = r_q4 - r_q1

        # Correlation between BM and GP/A
        corr_bm_gp = float(np.corrcoef(bm, gp)[0, 1])

        return {
            "r_junk_growth_q1": r_q1,
            "r_quality_growth_q2": r_q2,
            "r_value_trap_q3": r_q3,
            "r_super_value_q4": r_q4,
            "gp_spread_in_value": gp_spread_in_value,
            "value_spread_in_profitable": value_spread_in_profitable,
            "synergistic_spread": synergistic_spread,
            "characteristic_correlation": corr_bm_gp,
            "orthogonal_hedging_benefit": corr_bm_gp < 0.05
        }

    @staticmethod
    def factor_spanning_regression(
        pma_returns: np.ndarray,
        mkt_returns: np.ndarray,
        smb_returns: np.ndarray,
        hml_returns: np.ndarray
    ) -> Dict[str, float]:
        """Runs Fama-French 3-Factor spanning regression for PMA:
            PMA_t = alpha + beta_mkt * MKT_t + beta_smb * SMB_t + beta_hml * HML_t + e_t
        Reveals that PMA produces positive economic alpha and often negative HML loading.
        """
        T = len(pma_returns)
        X = np.column_stack([np.ones(T), mkt_returns, smb_returns, hml_returns])
        y = pma_returns.reshape(-1, 1)

        betas = np.linalg.pinv(X.T @ X) @ (X.T @ y)
        alpha = float(betas[0, 0])
        b_mkt = float(betas[1, 0])
        b_smb = float(betas[2, 0])
        b_hml = float(betas[3, 0])

        resid = y - X @ betas
        sigma_sq = float((resid.T @ resid)[0, 0] / max(1, T - 4))
        var_cov = sigma_sq * np.linalg.pinv(X.T @ X)
        se_alpha = math.sqrt(max(1e-12, var_cov[0, 0]))
        t_alpha = alpha / se_alpha

        return {
            "alpha": alpha,
            "se_alpha": se_alpha,
            "t_alpha": t_alpha,
            "beta_mkt": b_mkt,
            "beta_smb": b_smb,
            "beta_hml": b_hml,
            "has_significant_alpha": t_alpha > 1.96
        }


# ==============================================================================
# Model 3: Viral V. Acharya & Lasse Heje Pedersen (2005) LCAPM Engine
# ==============================================================================
class AcharyaPedersenLCAPMEngine:
    """Viral V. Acharya & Lasse Heje Pedersen (2005) Liquidity-Adjusted CAPM (LCAPM).
    
    Decomposes asset risk into market return risk and three systematic liquidity risks:
        E[R_i - R_f] = E[c_i] + lambda * (beta^1 + beta^2 - beta^3 - beta^4)
    where:
        beta^1: Cov(R_i, R_m) / Var(R_m - c_m)  [Standard Market Beta]
        beta^2: Cov(c_i, c_m) / Var(R_m - c_m)  [Commonality in Liquidity]
        beta^3: Cov(R_i, c_m) / Var(R_m - c_m)  [Return Sensitivity to Market Liquidity]
        beta^4: Cov(c_i, R_m) / Var(R_m - c_m)  [Illiquidity Sensitivity to Market Return]
    """

    @staticmethod
    def estimate_four_betas(
        asset_returns: np.ndarray,
        asset_illiquidities: np.ndarray,
        market_returns: np.ndarray,
        market_illiquidities: np.ndarray
    ) -> Dict[str, float]:
        """Estimates the 4 distinct betas of Acharya-Pedersen LCAPM."""
        Ri = np.asarray(asset_returns, dtype=float)
        ci = np.asarray(asset_illiquidities, dtype=float)
        Rm = np.asarray(market_returns, dtype=float)
        cm = np.asarray(market_illiquidities, dtype=float)

        net_Rm = Rm - cm
        var_net_m = float(np.var(net_Rm, ddof=1))
        if var_net_m <= 1e-12:
            var_net_m = 1e-6

        cov_r_rm = float(np.cov(Ri, Rm)[0, 1])
        cov_c_cm = float(np.cov(ci, cm)[0, 1])
        cov_r_cm = float(np.cov(Ri, cm)[0, 1])
        cov_c_rm = float(np.cov(ci, Rm)[0, 1])

        beta_1 = cov_r_rm / var_net_m  # Standard market beta
        beta_2 = cov_c_cm / var_net_m  # Commonality in liquidity (+ premium)
        beta_3 = cov_r_cm / var_net_m  # Flight-to-liquidity (- premium because cov is negative)
        beta_4 = cov_c_rm / var_net_m  # Depressed liquidity in down markets (- premium because cov is negative)

        # Unified net systematic liquidity beta
        beta_net = beta_1 + beta_2 - beta_3 - beta_4

        return {
            "beta_1_market": beta_1,
            "beta_2_commonality": beta_2,
            "beta_3_flight_to_liquidity": beta_3,
            "beta_4_crash_illiquidity": beta_4,
            "beta_net_lcapm": beta_net,
            "var_net_market": var_net_m
        }

    @classmethod
    def compute_expected_excess_return(
        cls,
        mean_illiquidity_ci: float,
        lambda_market_price_of_risk: float,
        betas: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculates expected excess return decomposed into direct cost and risk premia:
            E[R_i - R_f] = E[c_i] + lambda * beta_net
        """
        b1 = betas["beta_1_market"]
        b2 = betas["beta_2_commonality"]
        b3 = betas["beta_3_flight_to_liquidity"]
        b4 = betas["beta_4_crash_illiquidity"]

        direct_cost = mean_illiquidity_ci
        market_premium = lambda_market_price_of_risk * b1
        commonality_premium = lambda_market_price_of_risk * b2
        flight_to_liq_premium = lambda_market_price_of_risk * (-b3)
        crash_dryup_premium = lambda_market_price_of_risk * (-b4)

        total_systematic_liquidity_premium = commonality_premium + flight_to_liq_premium + crash_dryup_premium
        total_expected_excess_return = direct_cost + market_premium + total_systematic_liquidity_premium

        return {
            "direct_illiquidity_cost": direct_cost,
            "market_risk_premium": market_premium,
            "commonality_premium": commonality_premium,
            "flight_to_liquidity_premium": flight_to_liq_premium,
            "crash_dryup_premium": crash_dryup_premium,
            "total_liquidity_risk_premium": total_systematic_liquidity_premium,
            "total_expected_excess_return": total_expected_excess_return
        }


# ==============================================================================
# Model 4: Rajnish Mehra & Edward C. Prescott (1985) CCAPM Engine
# ==============================================================================
class MehraPrescottCCAPMEngine:
    """Rajnish Mehra & Edward C. Prescott (1985) / Robert E. Lucas Jr. (1978)
    Consumption-Based Asset Pricing Model (CCAPM) & Equity Premium Puzzle Engine.
    
    Demonstrates the stark disconnect between macroeconomic consumption volatility
    and the historical equity risk premium under standard CRRA utility:
        ln E[R_e] - ln R_f = gamma * Cov(ln(C_{t+1}/C_t), ln R_e)
    """

    @staticmethod
    def solve_equity_premium_puzzle(
        mean_consumption_growth: float,
        std_consumption_growth: float,
        std_equity_return: float,
        corr_consumption_equity: float,
        observed_equity_premium: float
    ) -> Dict[str, Any]:
        """Calculates the theoretical equity premium under CRRA risk aversion gamma,
        and computes the implied gamma required to justify observed historical equity premium.
        """
        cov_c_e = std_consumption_growth * std_equity_return * corr_consumption_equity
        if cov_c_e <= 1e-9:
            cov_c_e = 1e-4

        # Implied relative risk aversion gamma* = Premium / Cov(c, e)
        implied_gamma = observed_equity_premium / cov_c_e

        # Standard microeconomic benchmark predictions (gamma = 2.0 and gamma = 5.0)
        theoretical_premium_gamma_2 = 2.0 * cov_c_e
        theoretical_premium_gamma_5 = 5.0 * cov_c_e

        unexplained_gap_at_gamma_2 = observed_equity_premium - theoretical_premium_gamma_2

        return {
            "observed_equity_premium": observed_equity_premium,
            "consumption_equity_covariance": cov_c_e,
            "implied_risk_aversion_gamma": implied_gamma,
            "theoretical_premium_gamma_2": theoretical_premium_gamma_2,
            "theoretical_premium_gamma_5": theoretical_premium_gamma_5,
            "unexplained_gap_at_gamma_2": unexplained_gap_at_gamma_2,
            "is_puzzle_present": implied_gamma > 10.0
        }

    @staticmethod
    def compute_risk_free_rate_puzzle(
        time_preference_beta: float,
        gamma: float,
        mean_consumption_growth: float,
        std_consumption_growth: float
    ) -> Dict[str, Any]:
        """Demonstrates Philippe Weil (1989) Risk-Free Rate Puzzle:
        If gamma is high enough to match the equity premium, the predicted risk-free rate
        explodes to unrealistically high levels:
            ln R_f = -ln(beta) + gamma * mu_c - 0.5 * gamma^2 * sigma_c^2
        """
        var_c = std_consumption_growth ** 2
        r_f_log = -math.log(time_preference_beta) + gamma * mean_consumption_growth - 0.5 * (gamma ** 2) * var_c
        r_f_annual = math.exp(r_f_log) - 1.0

        return {
            "gamma_used": gamma,
            "log_risk_free_rate": r_f_log,
            "annualized_risk_free_rate": r_f_annual,
            "is_risk_free_rate_counterfactually_high": r_f_annual > 0.15
        }

    @staticmethod
    def evaluate_hansen_jagannathan_sdf_bound(
        equity_sharpe_ratio: float,
        gamma: float,
        std_consumption_growth: float
    ) -> Dict[str, Any]:
        """Evaluates whether the CCAPM Stochastic Discount Factor satisfies the
        Hansen-Jagannathan (1991) volatility bound:
            sigma(M) / E[M] >= Sharpe Ratio
        For log-normal CRRA: sigma(M) / E[M] = sqrt(exp(gamma^2 * sigma_c^2) - 1)
        """
        sdf_vol_ratio = math.sqrt(math.exp((gamma * std_consumption_growth) ** 2) - 1.0)
        bound_satisfied = sdf_vol_ratio >= equity_sharpe_ratio

        return {
            "equity_sharpe_ratio": equity_sharpe_ratio,
            "sdf_volatility_ratio": sdf_vol_ratio,
            "bound_satisfied": bound_satisfied,
            "sdf_volatility_shortfall": max(0.0, equity_sharpe_ratio - sdf_vol_ratio)
        }


# ==============================================================================
# Model 5: H. Gifford Fong & Oldrich A. Vasicek (1984) M^2 Immunization Engine
# ==============================================================================
class FongVasicekImmunizationEngine:
    """H. Gifford Fong & Oldrich A. Vasicek (1984) / Stephen J. Brown & Philip H. Dybvig (1986)
    Bond Immunization under Arbitrary Yield Curve Shifts & M^2 Dispersion Minimization.
    
    Protects portfolios against non-parallel yield shifts and twists.
    While Macaulay duration matches horizon (D = H), the change in portfolio value is bounded by:
        Delta P / P >= -(D - H) * Delta y_0 - 0.5 * M^2 * K_max
    where M^2 is the cash flow dispersion around target horizon H:
        M^2 = sum_t w_t * (t - H)^2
    """

    @staticmethod
    def compute_cash_flow_immunization_metrics(
        cash_flows: np.ndarray,
        maturities: np.ndarray,
        yield_rate: float,
        target_horizon_H: float
    ) -> Dict[str, float]:
        """Calculates Price, Macaulay Duration, Convexity, and Fong-Vasicek M^2 dispersion."""
        cf = np.asarray(cash_flows, dtype=float)
        t = np.asarray(maturities, dtype=float)

        discount_factors = (1.0 + yield_rate) ** (-t)
        pvs = cf * discount_factors
        total_price = float(np.sum(pvs))

        if total_price <= 1e-12:
            raise ValueError("Total bond price must be positive.")

        weights = pvs / total_price

        # Macaulay Duration: D = sum w_t * t
        mac_duration = float(np.sum(weights * t))
        mod_duration = mac_duration / (1.0 + yield_rate)

        # Convexity: C = sum w_t * t * (t + 1) / (1 + y)^2
        convexity = float(np.sum(weights * t * (t + 1.0)) / ((1.0 + yield_rate) ** 2))

        # Fong-Vasicek M^2 Cash Flow Dispersion around H: M^2 = sum w_t * (t - H)^2
        m_squared = float(np.sum(weights * ((t - target_horizon_H) ** 2)))

        return {
            "price": total_price,
            "macaulay_duration": mac_duration,
            "modified_duration": mod_duration,
            "convexity": convexity,
            "m_squared_dispersion": m_squared,
            "duration_matched": abs(mac_duration - target_horizon_H) < 1e-3
        }

    @classmethod
    def compare_bullet_vs_barbell_immunization(
        cls,
        target_horizon_H: float,
        yield_rate: float
    ) -> Dict[str, Any]:
        """Compares a pure bullet portfolio (maturing exactly at H) with a barbell portfolio
        (short and long bonds) engineered to have the exact same duration D = H.
        Proves that the barbell has substantially higher M^2 dispersion, making it
        vulnerable to yield curve curvature and twisting shifts.
        """
        # Bullet: 100% at H
        bullet_cf = np.array([1000.0])
        bullet_t = np.array([target_horizon_H])
        bullet_metrics = cls.compute_cash_flow_immunization_metrics(
            bullet_cf, bullet_t, yield_rate, target_horizon_H
        )

        # Barbell: 50% at H - 4 years, 50% at H + 4 years (e.g. 1y and 9y for H = 5y)
        delta_t = 4.0
        t1 = max(0.5, target_horizon_H - delta_t)
        t2 = target_horizon_H + delta_t

        # Weighting to ensure Macaulay duration equals target_horizon_H
        # w1 * t1 + (1 - w1) * t2 = H => w1 * (t1 - t2) = H - t2 => w1 = (t2 - H) / (t2 - t1)
        w1 = (t2 - target_horizon_H) / (t2 - t1)
        w2 = 1.0 - w1

        # Determine cash flows that produce these present value weights
        pv_target = 1000.0
        cf1 = (w1 * pv_target) * ((1.0 + yield_rate) ** t1)
        cf2 = (w2 * pv_target) * ((1.0 + yield_rate) ** t2)

        barbell_cf = np.array([cf1, cf2])
        barbell_t = np.array([t1, t2])
        barbell_metrics = cls.compute_cash_flow_immunization_metrics(
            barbell_cf, barbell_t, yield_rate, target_horizon_H
        )

        # Maximum curvature risk under a severe 100 bps non-linear twist
        max_curvature_k = 0.0001
        bullet_min_loss = -0.5 * bullet_metrics["m_squared_dispersion"] * max_curvature_k
        barbell_min_loss = -0.5 * barbell_metrics["m_squared_dispersion"] * max_curvature_k

        return {
            "bullet_m2": bullet_metrics["m_squared_dispersion"],
            "barbell_m2": barbell_metrics["m_squared_dispersion"],
            "bullet_macaulay_duration": bullet_metrics["macaulay_duration"],
            "barbell_macaulay_duration": barbell_metrics["macaulay_duration"],
            "bullet_lower_bound_loss": bullet_min_loss,
            "barbell_lower_bound_loss": barbell_min_loss,
            "barbell_dispersion_ratio": barbell_metrics["m_squared_dispersion"] / max(1e-6, bullet_metrics["m_squared_dispersion"]),
            "is_bullet_strictly_superior_in_dispersion": bullet_metrics["m_squared_dispersion"] < barbell_metrics["m_squared_dispersion"]
        }


# ==============================================================================
# Model 6: Grinold, Kahn & Clarke-de Silva-Thorley FLAM Engine
# ==============================================================================
class GrinoldKahnFLAMEngine:
    """Richard C. Grinold (1989), Ronald N. Kahn (2000) & Clarke, de Silva & Thorley (2002)
    The Generalized Fundamental Law of Active Management (FLAM) & Transfer Coefficient Engine.
    
    Formulates:
        IR = TC * IC * sqrt(BR)
    where:
        IR: Information Ratio (Active Return / Tracking Error)
        IC: Information Coefficient (Skill / Signal-Return Correlation)
        BR: Strategy Breadth (Number of independent active bets per year)
        TC: Transfer Coefficient (Correlation between unconstrained and constrained active bets)
    """

    @staticmethod
    def calculate_generalized_flam(
        information_coefficient: float,
        strategy_breadth: int,
        transfer_coefficient: float = 1.0
    ) -> Dict[str, float]:
        """Calculates Information Ratio and expected active value added under constraints."""
        ic = float(information_coefficient)
        br = int(strategy_breadth)
        tc = max(0.0, min(1.0, float(transfer_coefficient)))

        unconstrained_ir = ic * math.sqrt(br)
        constrained_ir = tc * unconstrained_ir
        constraint_drag_pct = (1.0 - tc) * 100.0

        return {
            "information_coefficient": ic,
            "strategy_breadth": br,
            "transfer_coefficient": tc,
            "unconstrained_ir": unconstrained_ir,
            "constrained_ir": constrained_ir,
            "constraint_drag_pct": constraint_drag_pct
        }

    @staticmethod
    def generate_grinold_alphas(
        raw_signals: np.ndarray,
        residual_volatilities: np.ndarray,
        information_coefficient: float
    ) -> np.ndarray:
        """Grinold's Alpha Equation:
            alpha_i = Volatility_i * IC * z_score_i
        Standardizes signals cross-sectionally to have mean 0 and variance 1.
        """
        sig = np.asarray(raw_signals, dtype=float)
        vols = np.asarray(residual_volatilities, dtype=float)
        z = (sig - np.mean(sig)) / max(1e-8, np.std(sig))
        return vols * information_coefficient * z

    @classmethod
    def optimize_constrained_active_weights(
        cls,
        alphas: np.ndarray,
        residual_volatilities: np.ndarray,
        benchmark_weights: np.ndarray,
        risk_aversion_lambda: float = 0.5
    ) -> Dict[str, Any]:
        """Computes unconstrained optimal active weights:
            w_i^* = (1 / (2 * lambda)) * (alpha_i / omega_i^2)
        and compares with long-only constrained weights:
            w_portfolio = max(0, w_benchmark + w_active)
        Computes the empirical Transfer Coefficient:
            TC = Corr(w^*, w_constrained)
        """
        a = np.asarray(alphas, dtype=float)
        omega = np.asarray(residual_volatilities, dtype=float)
        b = np.asarray(benchmark_weights, dtype=float)

        # Unconstrained active weights: w* = alpha / (2 * lambda * omega^2), then cash neutral
        raw_w_star = a / (2.0 * risk_aversion_lambda * (omega ** 2))
        w_star = raw_w_star - np.mean(raw_w_star)  # dollar neutral

        # Long-only constrained portfolio: total weight w_port >= 0
        tentative_port = b + w_star
        constrained_port = np.maximum(0.0, tentative_port)
        constrained_port /= np.sum(constrained_port)  # renormalize to sum to 1.0
        constrained_active_w = constrained_port - b

        # Empirical Transfer Coefficient
        norm_w_star = np.std(w_star)
        norm_w_con = np.std(constrained_active_w)
        if norm_w_star > 1e-8 and norm_w_con > 1e-8:
            transfer_coeff = float(np.corrcoef(w_star, constrained_active_w)[0, 1])
        else:
            transfer_coeff = 1.0

        return {
            "unconstrained_active_weights": w_star.tolist(),
            "constrained_active_weights": constrained_active_w.tolist(),
            "empirical_transfer_coefficient": transfer_coeff,
            "has_constraint_drag": transfer_coeff < 0.95
        }


# ==============================================================================
# Pytest Verification Suite
# ==============================================================================
class TestFaz61QuantitativeFinanceEngines:
    """TDD test suite verifying mathematical exactness, numerical convergence,
    and theoretical invariants of all 6 Faz 61 quantitative finance engines.
    """

    def test_generalized_method_of_moments_engine(self):
        """Tests Hansen (1982) 2-step GMM, Newey-West HAC, and J-test."""
        np.random.seed(42)
        T = 400
        p = 2  # Constant + Regressor
        q = 4  # Constant + 3 Instruments

        # Data generating process: y = theta_0 + theta_1 * x + e
        true_theta = np.array([1.5, -0.8])
        Z = np.column_stack([np.ones(T), np.random.randn(T, q - 1)])
        # Regressor X correlated with instruments + noise
        x1 = 0.6 * Z[:, 1] + 0.4 * Z[:, 2] + 0.2 * np.random.randn(T)
        X = np.column_stack([np.ones(T), x1])

        # Serially correlated errors (MA(1))
        innovations = np.random.randn(T)
        e = np.zeros(T)
        for t in range(1, T):
            e[t] = innovations[t] + 0.5 * innovations[t - 1]
        y = X @ true_theta + e

        res = GeneralizedMethodOfMomentsEngine.estimate_linear_gmm(y, X, Z, max_lags=2)

        # Estimates must be close to true parameters
        theta_est = res["theta_step2"]
        assert abs(theta_est[0] - true_theta[0]) < 0.35
        assert abs(theta_est[1] - true_theta[1]) < 0.35
        assert res["degrees_of_freedom"] == q - p
        assert res["J_stat"] >= 0.0
        # Overidentifying restrictions should not be rejected on valid DGP (p-value > 0.05)
        assert res["J_p_value"] > 0.05
        assert not res["model_rejected"]

    def test_novy_marx_gross_profitability_engine(self):
        """Tests Novy-Marx (2013) Gross Profitability calculation, PMA sorting,
        and double-sort value-profitability synergy.
        """
        np.random.seed(101)
        N = 250
        rev = np.random.uniform(500, 2000, N)
        cogs = rev * np.random.uniform(0.3, 0.8, N)
        assets = np.random.uniform(800, 4000, N)

        gp_a = NovyMarxGrossProfitabilityEngine.compute_gross_profitability(rev, cogs, assets)
        assert len(gp_a) == N
        assert np.all(gp_a >= 0.0)

        # Generate returns where GP/A predicts returns positively
        bm_ratio = np.random.uniform(0.2, 1.8, N)
        returns = 0.08 + 0.15 * gp_a + 0.10 * bm_ratio + np.random.randn(N) * 0.05

        pma_res = NovyMarxGrossProfitabilityEngine.sort_and_construct_pma_factor(gp_a, returns, n_quantiles=5)
        assert pma_res["pma_spread"] > 0.0
        assert pma_res["is_monotonic_trend"]

        double_sort = NovyMarxGrossProfitabilityEngine.double_sort_value_profitability(bm_ratio, gp_a, returns)
        assert double_sort["gp_spread_in_value"] > 0.0
        assert double_sort["value_spread_in_profitable"] > 0.0
        assert double_sort["synergistic_spread"] > pma_res["pma_spread"] * 0.8

        # Test spanning regression
        T = 120
        pma_rets = np.random.normal(0.04, 0.08, T)
        mkt = np.random.normal(0.06, 0.15, T)
        smb = np.random.normal(0.02, 0.10, T)
        hml = np.random.normal(0.03, 0.10, T)
        span_res = NovyMarxGrossProfitabilityEngine.factor_spanning_regression(pma_rets, mkt, smb, hml)
        assert "alpha" in span_res
        assert "t_alpha" in span_res

    def test_acharya_pedersen_lcapm_engine(self):
        """Tests Acharya & Pedersen (2005) 4-Beta LCAPM decomposition."""
        np.random.seed(202)
        T = 200
        Rm = np.random.normal(0.008, 0.04, T)
        cm = np.maximum(0.001, np.random.normal(0.005, 0.002, T))

        # Asset correlated with market and liquidity
        Ri = 0.005 + 1.2 * Rm - 1.5 * cm + np.random.normal(0, 0.02, T)
        ci = 0.002 + 0.8 * cm - 0.5 * Rm + np.random.normal(0, 0.001, T)

        betas = AcharyaPedersenLCAPMEngine.estimate_four_betas(Ri, ci, Rm, cm)
        assert betas["beta_1_market"] > 0.8
        assert betas["beta_2_commonality"] > 0.0
        assert betas["beta_3_flight_to_liquidity"] < 0.0  # Asset falls when market illiquidity rises
        assert betas["beta_4_crash_illiquidity"] < 0.0  # Asset illiquidity rises when market falls

        # Unified net beta must be higher than market beta due to liquidity penalties
        assert betas["beta_net_lcapm"] > betas["beta_1_market"]

        exp_ret = AcharyaPedersenLCAPMEngine.compute_expected_excess_return(
            mean_illiquidity_ci=float(np.mean(ci)),
            lambda_market_price_of_risk=0.06,
            betas=betas
        )
        assert exp_ret["total_liquidity_risk_premium"] > 0.0
        assert exp_ret["total_expected_excess_return"] > exp_ret["market_risk_premium"]

    def test_mehra_prescott_ccapm_engine(self):
        """Tests Mehra & Prescott (1985) equity premium puzzle, Weil risk-free rate puzzle,
        and Hansen-Jagannathan SDF bound.
        """
        mean_c = 0.0183
        std_c = 0.0200
        std_e = 0.1654
        corr_ce = 0.40
        historical_premium = 0.0618

        res = MehraPrescottCCAPMEngine.solve_equity_premium_puzzle(
            mean_c, std_c, std_e, corr_ce, historical_premium
        )
        # Implied risk aversion must exceed 10 (demonstrating the historical puzzle)
        assert res["implied_risk_aversion_gamma"] > 20.0
        assert res["is_puzzle_present"]
        assert res["theoretical_premium_gamma_2"] < historical_premium * 0.15

        # Weil Risk-Free Rate Puzzle: At gamma = 25, rf is counterfactually high
        rf_res = MehraPrescottCCAPMEngine.compute_risk_free_rate_puzzle(
            time_preference_beta=0.99,
            gamma=res["implied_risk_aversion_gamma"],
            mean_consumption_growth=mean_c,
            std_consumption_growth=std_c
        )
        assert rf_res["is_risk_free_rate_counterfactually_high"]

        # Hansen-Jagannathan bound check
        sharpe = historical_premium / std_e  # ~0.37
        hj_res_low_gamma = MehraPrescottCCAPMEngine.evaluate_hansen_jagannathan_sdf_bound(
            sharpe, gamma=2.0, std_consumption_growth=std_c
        )
        assert not hj_res_low_gamma["bound_satisfied"]  # Fails at low gamma
        hj_res_high_gamma = MehraPrescottCCAPMEngine.evaluate_hansen_jagannathan_sdf_bound(
            sharpe, gamma=res["implied_risk_aversion_gamma"], std_consumption_growth=std_c
        )
        assert hj_res_high_gamma["bound_satisfied"]  # Satisfied at high gamma

    def test_fong_vasicek_immunization_engine(self):
        """Tests Fong & Vasicek (1984) M^2 cash flow dispersion and bullet vs. barbell immunization."""
        H = 5.0
        y = 0.05
        comp = FongVasicekImmunizationEngine.compare_bullet_vs_barbell_immunization(H, y)

        # Both portfolios have Macaulay duration equal to horizon H = 5.0
        assert abs(comp["bullet_macaulay_duration"] - H) < 1e-3
        assert abs(comp["barbell_macaulay_duration"] - H) < 1e-3

        # Bullet M^2 is zero (zero dispersion around H), while barbell M^2 is large
        assert comp["bullet_m2"] < 1e-6
        assert comp["barbell_m2"] > 14.0
        assert comp["is_bullet_strictly_superior_in_dispersion"]
        assert comp["bullet_lower_bound_loss"] > comp["barbell_lower_bound_loss"]

    def test_grinold_kahn_flam_engine(self):
        """Tests Grinold & Kahn (1989, 2000) Generalized FLAM, Transfer Coefficient,
        and active weight optimization under long-only constraints.
        """
        # Generalized FLAM formula
        flam = GrinoldKahnFLAMEngine.calculate_generalized_flam(
            information_coefficient=0.08,
            strategy_breadth=400,
            transfer_coefficient=0.65
        )
        assert flam["unconstrained_ir"] == pytest.approx(0.08 * 20.0, rel=1e-3)  # 1.60
        assert flam["constrained_ir"] == pytest.approx(0.65 * 1.60, rel=1e-3)    # 1.04
        assert flam["constraint_drag_pct"] == pytest.approx(35.0, rel=1e-3)

        # Generate Grinold alphas
        np.random.seed(303)
        N = 50
        signals = np.random.randn(N)
        vols = np.random.uniform(0.15, 0.35, N)
        alphas = GrinoldKahnFLAMEngine.generate_grinold_alphas(signals, vols, information_coefficient=0.08)
        assert len(alphas) == N
        assert np.mean(alphas) == pytest.approx(0.0, abs=1e-2)

        # Portfolio optimization with long-only constraints
        bench = np.ones(N) / N
        opt = GrinoldKahnFLAMEngine.optimize_constrained_active_weights(
            alphas, vols, bench, risk_aversion_lambda=0.5
        )
        assert opt["empirical_transfer_coefficient"] < 1.0
        assert opt["has_constraint_drag"]
