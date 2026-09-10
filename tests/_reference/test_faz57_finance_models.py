"""Programmatic TDD Verification Suite for Faz 57 Quantitative Finance Engines.

Models:
1. John Y. Campbell & Tuomo Vuolteenaho (2004): Bad Beta, Good Beta (Two-Beta ICAPM & VAR News Decomposition)
2. Barr Rosenberg (1974) & Barra: Fundamental Factor Risk Model, WLS Factor Returns & Active Risk Budgeting (MCAR)
3. Gary P. Brinson, L. Randolph Hood & Gilbert L. Beebower (1986) & Brinson-Fachler (1985): Portfolio Performance Attribution & Cariño Multi-Period Linking
4. Roy D. Henriksson & Robert C. Merton (1981) / M. Hashem Pesaran & Allan Timmermann (1995): Market Timing Put Option Regression & Non-Parametric Directional Predictability
5. John Hull & Alan White (1994): Two-Factor Short Rate Model (Hull-White 2F / G2++) & Correlated Term Structure Twisting
6. Brad Barber & Terrance Odean (2000, 2001) / Hersh Shefrin & Meir Statman (1985): Behavioral Finance, Disposition Effect (PGR vs PLR) & Overconfidence Penalty
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


# ==============================================================================
# Model 1: Campbell & Vuolteenaho (2004) "Bad Beta, Good Beta" (Two-Beta ICAPM)
# ==============================================================================
class CampbellVuolteenahoTwoBetaEngine:
    """John Y. Campbell & Tuomo Vuolteenaho (2004) Two-Beta ICAPM.
    Decomposes market returns into Cash-Flow News (N_CF) and Discount-Rate News (N_DR)
    via vector autoregression (VAR(1)), and computes Bad Beta (cash flow risk) vs Good Beta (discount rate risk).
    Pricing equation: E[R_i] - R_f = gamma * sigma_M^2 * beta_CF + sigma_M^2 * beta_DR.
    """

    @staticmethod
    def var_news_decomposition(
        var_coefficients: np.ndarray,
        var_residuals: np.ndarray,
        rho: float = 0.96
    ) -> Dict[str, np.ndarray]:
        """Decomposes VAR innovations into Cash-Flow news (N_CF) and Discount-Rate news (N_DR).
        var_coefficients: Gamma matrix (K, K) where z_{t+1} = Gamma @ z_t + u_{t+1}.
                          Variable 1 is excess market return (r_M - E[r_M]).
        var_residuals: Matrix (T, K) of VAR innovations u_t.
        rho: Campbell-Shiller log-linear discount parameter (typically 0.96 for annual, ~0.99 for monthly).
        Returns dict with N_DR (T,), N_CF (T,), and total news (T,).
        """
        K = var_coefficients.shape[0]
        T = var_residuals.shape[0]

        I = np.eye(K)
        # lambda_DR = e1' * rho * Gamma * (I - rho * Gamma)^(-1)
        # Using solve for numerical stability: (I - rho * Gamma)' x = (rho * Gamma)' e1
        e1 = np.zeros(K)
        e1[0] = 1.0

        M = I - rho * var_coefficients
        rho_Gamma = rho * var_coefficients
        lambda_DR = np.linalg.solve(M.T, rho_Gamma.T @ e1)

        # N_DR = u_t @ lambda_DR
        n_dr = var_residuals @ lambda_DR

        # N_CF = (e1 + lambda_DR)' u_t
        lambda_CF = e1 + lambda_DR
        n_cf = var_residuals @ lambda_CF

        # Total market unexpected return = e1' u_t = N_CF - N_DR
        n_total = var_residuals[:, 0]

        return {
            "n_dr": n_dr,
            "n_cf": n_cf,
            "n_total": n_total,
            "lambda_dr": lambda_DR,
            "lambda_cf": lambda_CF
        }

    @staticmethod
    def estimate_betas(
        asset_returns: np.ndarray,
        n_cf: np.ndarray,
        n_dr: np.ndarray,
        market_unexpected: np.ndarray
    ) -> Dict[str, float]:
        """Calculates Bad Beta (beta_CF) and Good Beta (beta_DR) for an asset.
        asset_returns: (T,) array of asset excess returns.
        n_cf: (T,) Cash flow news series.
        n_dr: (T,) Discount rate news series.
        market_unexpected: (T,) market innovation series.
        """
        var_market = float(np.var(market_unexpected, ddof=1))
        if var_market <= 0:
            raise ValueError("Market unexpected variance must be strictly positive.")

        cov_cf = float(np.cov(asset_returns, n_cf)[0, 1])
        cov_dr = float(np.cov(asset_returns, -n_dr)[0, 1])

        beta_cf = cov_cf / var_market  # Bad beta
        beta_dr = cov_dr / var_market  # Good beta
        beta_total = beta_cf + beta_dr

        return {
            "beta_cf": beta_cf,
            "beta_dr": beta_dr,
            "beta_total": beta_total,
            "market_var": var_market
        }

    @staticmethod
    def calculate_expected_return(
        beta_cf: float,
        beta_dr: float,
        market_var: float,
        gamma: float = 5.0
    ) -> Dict[str, float]:
        """Calculates ICAPM two-beta required risk premium:
        E[R_i] - R_f = gamma * market_var * beta_cf + market_var * beta_dr.
        """
        cf_premium = gamma * market_var * beta_cf
        dr_premium = market_var * beta_dr
        total_risk_premium = cf_premium + dr_premium

        # Standard CAPM comparison with same total beta
        beta_total = beta_cf + beta_dr
        capm_premium = gamma * market_var * beta_total

        return {
            "expected_excess_return": total_risk_premium,
            "cf_risk_contribution": cf_premium,
            "dr_risk_contribution": dr_premium,
            "bad_beta_weight_ratio": gamma,
            "capm_excess_return": capm_premium,
            "value_growth_spread": total_risk_premium - capm_premium
        }


# ==============================================================================
# Model 2: Barr Rosenberg (1974) & Barra Fundamental Factor Risk Model
# ==============================================================================
class BarraFactorRiskEngine:
    """Barr Rosenberg (1974) Barra Fundamental Cross-Sectional Risk Model.
    r_it = sum_k X_{ik} f_{kt} + u_{it}.
    Estimates pure factor returns via WLS, forecasts asset covariance:
    Sigma = X Sigma_F X' + Delta,
    and decomposes portfolio active tracking error into Systematic Factor Risk vs Specific Risk,
    along with Marginal Contribution to Active Risk (MCAR).
    """

    @staticmethod
    def estimate_factor_returns_wls(
        returns: np.ndarray,
        factor_exposures: np.ndarray,
        weights: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """Runs Cross-Sectional Weighted Least Squares (WLS) regression:
        f_t = (X' V^(-1) X)^(-1) X' V^(-1) r_t.
        returns: (N,) vector of asset returns at time t.
        factor_exposures: (N, K) matrix of style & industry exposures.
        weights: (N,) vector of regression weights (e.g. sqrt(market_cap)), default uniform.
        """
        N, K = factor_exposures.shape
        if len(returns) != N:
            raise ValueError("Dimensions of returns and factor exposures must match.")

        if weights is None:
            W = np.eye(N)
        else:
            w_norm = weights / np.sum(weights)
            W = np.diag(w_norm)

        XtW = factor_exposures.T @ W
        XtWX = XtW @ factor_exposures
        XtWr = XtW @ returns

        factor_returns = np.linalg.solve(XtWX, XtWr)
        fitted = factor_exposures @ factor_returns
        residuals = returns - fitted

        return {
            "factor_returns": factor_returns,
            "fitted_returns": fitted,
            "residuals": residuals
        }

    @staticmethod
    def forecast_asset_covariance(
        factor_exposures: np.ndarray,
        factor_covariance: np.ndarray,
        specific_variances: np.ndarray
    ) -> np.ndarray:
        """Constructs NxN asset covariance matrix: Sigma = X @ Sigma_F @ X.T + diag(specific_variances)."""
        X = factor_exposures
        Sigma_F = factor_covariance
        Delta = np.diag(specific_variances)
        return X @ Sigma_F @ X.T + Delta

    @staticmethod
    def active_risk_decomposition(
        portfolio_weights: np.ndarray,
        benchmark_weights: np.ndarray,
        factor_exposures: np.ndarray,
        factor_covariance: np.ndarray,
        specific_variances: np.ndarray
    ) -> Dict[str, Any]:
        """Decomposes portfolio active risk (Tracking Error) into Systematic Factor Risk and Specific Risk:
        delta_w = w_P - w_B
        Total Active Variance = delta_w' Sigma delta_w
        Factor Active Variance = delta_w' X Sigma_F X' delta_w
        Specific Active Variance = delta_w' Delta delta_w.
        Computes Marginal Contribution to Active Risk (MCAR).
        """
        delta_w = portfolio_weights - benchmark_weights
        N = len(delta_w)

        # Factor active exposures: (K,) = X' delta_w
        active_factor_exposure = factor_exposures.T @ delta_w

        # Factor variance component
        factor_active_var = float(active_factor_exposure.T @ factor_covariance @ active_factor_exposure)
        factor_active_var = max(0.0, factor_active_var)

        # Specific variance component
        specific_active_var = float(np.sum((delta_w ** 2) * specific_variances))
        specific_active_var = max(0.0, specific_active_var)

        total_active_var = factor_active_var + specific_active_var
        tracking_error = math.sqrt(total_active_var)

        # Marginal Contribution to Active Risk (MCAR): Sigma @ delta_w / tracking_error
        Sigma = factor_exposures @ factor_covariance @ factor_exposures.T + np.diag(specific_variances)
        if tracking_error > 1e-12:
            mcar = (Sigma @ delta_w) / tracking_error
            # Percentage contribution to active risk: delta_w_i * mcar_i / tracking_error
            pcar = (delta_w * mcar) / tracking_error
        else:
            mcar = np.zeros(N)
            pcar = np.zeros(N)

        return {
            "tracking_error": tracking_error,
            "total_active_variance": total_active_var,
            "factor_active_variance": factor_active_var,
            "specific_active_variance": specific_active_var,
            "factor_risk_proportion": factor_active_var / total_active_var if total_active_var > 0 else 0.0,
            "specific_risk_proportion": specific_active_var / total_active_var if total_active_var > 0 else 0.0,
            "active_factor_exposures": active_factor_exposure,
            "mcar": mcar,
            "pcar": pcar
        }


# ==============================================================================
# Model 3: Gary P. Brinson, L. Randolph Hood & Gilbert L. Beebower (BHB 1986) & Brinson-Fachler (1985)
# ==============================================================================
class BrinsonPerformanceAttributionEngine:
    """Brinson, Hood & Beebower (1986) & Brinson-Fachler (1985) Performance Attribution.
    Decomposes portfolio excess return R_P - R_B into:
    1. Allocation Effect: A_i = (w_i^P - w_i^B) * (R_i^B - R_B) (Brinson-Fachler) or (w_i^P - w_i^B) * R_i^B (BHB)
    2. Selection Effect: S_i = w_i^B * (R_i^P - R_i^B)
    3. Interaction Effect: I_i = (w_i^P - w_i^B) * (R_i^P - R_i^B)
    Includes Cariño (1999) logarithmic linking coefficient for multi-period geometric compounding.
    """

    @staticmethod
    def single_period_attribution(
        portfolio_weights: np.ndarray,
        portfolio_returns: np.ndarray,
        benchmark_weights: np.ndarray,
        benchmark_returns: np.ndarray,
        method: str = "brinson_fachler"
    ) -> Dict[str, Any]:
        """Calculates exact single-period performance attribution.
        portfolio_weights, benchmark_weights: (M,) sector weights summing to 1.0.
        portfolio_returns, benchmark_returns: (M,) sector returns.
        method: 'brinson_fachler' or 'bhb'.
        """
        R_P = float(np.sum(portfolio_weights * portfolio_returns))
        R_B = float(np.sum(benchmark_weights * benchmark_returns))
        excess_return = R_P - R_B

        delta_w = portfolio_weights - benchmark_weights
        delta_r = portfolio_returns - benchmark_returns

        # Selection and Interaction
        selection = benchmark_weights * delta_r
        interaction = delta_w * delta_r

        # Allocation
        if method.lower() == "brinson_fachler":
            allocation = delta_w * (benchmark_returns - R_B)
        else:  # classic BHB
            allocation = delta_w * benchmark_returns

        total_allocation = float(np.sum(allocation))
        total_selection = float(np.sum(selection))
        total_interaction = float(np.sum(interaction))

        attributed_excess = total_allocation + total_selection + total_interaction

        return {
            "portfolio_return": R_P,
            "benchmark_return": R_B,
            "excess_return": excess_return,
            "allocation_by_sector": allocation,
            "selection_by_sector": selection,
            "interaction_by_sector": interaction,
            "total_allocation": total_allocation,
            "total_selection": total_selection,
            "total_interaction": total_interaction,
            "attributed_excess": attributed_excess,
            "reconciliation_error": abs(excess_return - attributed_excess)
        }

    @staticmethod
    def carino_multi_period_linking(
        periodic_p_returns: List[float],
        periodic_b_returns: List[float],
        periodic_attributions: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """Cariño (1999) logarithmic linking model:
        Compounded excess return R_cum^P - R_cum^B = sum_t k_t * excess_t
        where k_t = [ln(1+R_t^P) - ln(1+R_t^B)] / (R_t^P - R_t^B) / [ln(1+R_cum^P) - ln(1+R_cum^B)] / (R_cum^P - R_cum^B).
        """
        T = len(periodic_p_returns)
        if len(periodic_b_returns) != T or len(periodic_attributions) != T:
            raise ValueError("All periodic lists must have identical length.")

        # Compounded cumulative returns
        cum_p = float(np.prod([1.0 + r for r in periodic_p_returns]) - 1.0)
        cum_b = float(np.prod([1.0 + r for r in periodic_b_returns]) - 1.0)
        total_cum_excess = cum_p - cum_b

        # Global coefficient K
        diff_cum = cum_p - cum_b
        log_diff_cum = math.log(1.0 + cum_p) - math.log(1.0 + cum_b)
        if abs(diff_cum) < 1e-12:
            K = 1.0 / (1.0 + cum_p)
        else:
            K = log_diff_cum / diff_cum

        # Compute k_t weights
        k_weights = []
        for t in range(T):
            r_pt = periodic_p_returns[t]
            r_bt = periodic_b_returns[t]
            diff_t = r_pt - r_bt
            log_diff_t = math.log(1.0 + r_pt) - math.log(1.0 + r_bt)
            if abs(diff_t) < 1e-12:
                k_t_raw = 1.0 / (1.0 + r_pt)
            else:
                k_t_raw = log_diff_t / diff_t
            k_weights.append(k_t_raw / K)

        cum_alloc = sum(k_weights[t] * periodic_attributions[t]["allocation"] for t in range(T))
        cum_select = sum(k_weights[t] * periodic_attributions[t]["selection"] for t in range(T))
        cum_inter = sum(k_weights[t] * periodic_attributions[t]["interaction"] for t in range(T))

        total_linked_excess = cum_alloc + cum_select + cum_inter

        return {
            "cum_portfolio_return": cum_p,
            "cum_benchmark_return": cum_b,
            "total_cum_excess": total_cum_excess,
            "cum_allocation": cum_alloc,
            "cum_selection": cum_select,
            "cum_interaction": cum_inter,
            "total_linked_excess": total_linked_excess,
            "linking_error": abs(total_cum_excess - total_linked_excess)
        }


# ==============================================================================
# Model 4: Henriksson-Merton (1981) Market Timing & Pesaran-Timmermann (1995) Directional Test
# ==============================================================================
class HenrikssonMertonPesaranMarketTimingEngine:
    """Roy D. Henriksson & Robert C. Merton (1981) Market Timing Model:
    R_pt - R_ft = alpha_p + beta_p (R_mt - R_ft) + gamma_p max(0, R_ft - R_mt) + eps_pt
    (where gamma_p > 0 indicates downside protective market timing),
    and M. Hashem Pesaran & Allan Timmermann (1995) Directional Accuracy Test:
    S_n = (P_hat - P_*) / sqrt(V(P_hat) - V(P_*)) ~ N(0, 1).
    """

    @staticmethod
    def estimate_henriksson_merton(
        portfolio_excess_returns: np.ndarray,
        market_excess_returns: np.ndarray
    ) -> Dict[str, float]:
        """Runs OLS estimation of Henriksson-Merton option timing regression:
        y_t = alpha + beta * x_t + gamma * max(0, -x_t) + eps_t.
        A positive gamma indicates that the manager successfully hedges downside market movements.
        """
        T = len(portfolio_excess_returns)
        if len(market_excess_returns) != T:
            raise ValueError("Returns series must match length.")

        downside_put = np.maximum(0.0, -market_excess_returns)

        # Design matrix X: [1, market_excess, downside_put]
        X = np.column_stack([np.ones(T), market_excess_returns, downside_put])
        XtX = X.T @ X
        XtY = X.T @ portfolio_excess_returns
        params = np.linalg.solve(XtX, XtY)

        alpha = float(params[0])
        beta = float(params[1])
        gamma = float(params[2])

        fitted = X @ params
        residuals = portfolio_excess_returns - fitted
        sse = float(np.sum(residuals ** 2))
        dof = T - 3
        mse = sse / dof

        var_params = np.linalg.inv(XtX) * mse
        se_alpha = math.sqrt(max(1e-12, var_params[0, 0]))
        se_beta = math.sqrt(max(1e-12, var_params[1, 1]))
        se_gamma = math.sqrt(max(1e-12, var_params[2, 2]))

        t_alpha = alpha / se_alpha
        t_beta = beta / se_beta
        t_gamma = gamma / se_gamma

        # R-squared
        sst = float(np.sum((portfolio_excess_returns - np.mean(portfolio_excess_returns)) ** 2))
        r_squared = 1.0 - (sse / sst) if sst > 0 else 0.0

        return {
            "alpha": alpha,
            "beta": beta,
            "gamma_timing": gamma,
            "t_alpha": t_alpha,
            "t_beta": t_beta,
            "t_gamma": t_gamma,
            "r_squared": r_squared,
            "has_market_timing_skill": bool(gamma > 0 and t_gamma > 1.96)
        }

    @staticmethod
    def pesaran_timmermann_directional_test(
        actual_returns: np.ndarray,
        predicted_returns: np.ndarray
    ) -> Dict[str, Any]:
        """M. Hashem Pesaran & Allan Timmermann (1995) Non-Parametric Directional Accuracy Test.
        Tests whether the direction of predictions matches actual signs better than chance.
        Returns proportion of correct predictions (P_hat), baseline (P_star), and PT test statistic ~ N(0, 1).
        """
        T = len(actual_returns)
        if len(predicted_returns) != T:
            raise ValueError("Arrays must have identical dimensions.")

        y = (actual_returns > 0).astype(int)
        y_hat = (predicted_returns > 0).astype(int)

        # Proportion of correct direction
        p_hat = float(np.mean(y == y_hat))

        # Marginal probabilities
        p_y = float(np.mean(y))
        p_y_hat = float(np.mean(y_hat))

        # Expected proportion under independence: P* = p_y * p_y_hat + (1 - p_y) * (1 - p_y_hat)
        p_star = p_y * p_y_hat + (1.0 - p_y) * (1.0 - p_y_hat)

        # Variances
        v_p_hat = (p_star * (1.0 - p_star)) / T

        v_p_star = (
            ((2.0 * p_y - 1.0) ** 2) * (p_y_hat * (1.0 - p_y_hat) / T) +
            ((2.0 * p_y_hat - 1.0) ** 2) * (p_y * (1.0 - p_y) / T) +
            (4.0 * p_y * p_y_hat * (1.0 - p_y) * (1.0 - p_y_hat)) / (T * T)
        )

        denom = math.sqrt(max(1e-12, v_p_hat - v_p_star))
        pt_stat = (p_hat - p_star) / denom
        p_value = 1.0 - norm_cdf(pt_stat)

        return {
            "success_ratio": p_hat,
            "baseline_probability": p_star,
            "pt_statistic": pt_stat,
            "p_value": p_value,
            "is_significant_95": bool(pt_stat > 1.645)  # one-sided 95%
        }


# ==============================================================================
# Model 5: John Hull & Alan White (1994) Two-Factor Short Rate Model (Hull-White 2F / G2++)
# ==============================================================================
class HullWhiteTwoFactorEngine:
    """John Hull & Alan White (1994) Two-Factor Short-Rate Model (G2++).
    r(t) = phi(t) + u(t) + v(t)
    du(t) = -a u(t) dt + sigma1 dW1(t)
    dv(t) = -b v(t) dt + sigma2 dW2(t)
    dW1 dW2 = rho dt.
    Allows imperfect correlation between short and long rates, capturing yield curve twist & slope dynamics.
    Provides closed-form zero-coupon bond pricing:
    P(t, T) = (P(0, T)/P(0, t)) * exp(-B_a u - B_b v - 0.5 [V(0, T) - V(0, t) - V(t, T)]).
    """

    def __init__(
        self,
        a: float,
        b: float,
        sigma1: float,
        sigma2: float,
        rho: float,
        discount_curve: Optional[Dict[float, float]] = None
    ):
        if a <= 0 or b <= 0:
            raise ValueError("Mean-reversion rates a and b must be strictly positive.")
        if abs(rho) > 1.0:
            raise ValueError("Correlation rho must lie within [-1, 1].")

        self.a = a
        self.b = b
        self.sigma1 = sigma1
        self.sigma2 = sigma2
        self.rho = rho
        # Mapping from maturity T -> discount factor P(0, T)
        self.discount_curve = discount_curve or {}

    @staticmethod
    def B(param: float, tau: float) -> float:
        """B(k, tau) = (1 - exp(-k * tau)) / k."""
        if tau <= 0:
            return 0.0
        return (1.0 - math.exp(-param * tau)) / param

    def V(self, t: float, T: float) -> float:
        """Analytical variance function V(t, T) for Hull-White 2F."""
        tau = T - t
        if tau <= 0:
            return 0.0

        a, b = self.a, self.b
        s1, s2, rho = self.sigma1, self.sigma2, self.rho

        term1 = (s1 ** 2) / (a ** 2) * (tau + 2.0 * math.exp(-a * tau) / a - math.exp(-2.0 * a * tau) / (2.0 * a) - 1.5 / a)
        term2 = (s2 ** 2) / (b ** 2) * (tau + 2.0 * math.exp(-b * tau) / b - math.exp(-2.0 * b * tau) / (2.0 * b) - 1.5 / b)
        term3 = 2.0 * rho * s1 * s2 / (a * b) * (
            tau + (math.exp(-a * tau) - 1.0) / a + (math.exp(-b * tau) - 1.0) / b - (math.exp(-(a + b) * tau) - 1.0) / (a + b)
        )
        return term1 + term2 + term3

    def zero_coupon_bond_price(
        self,
        t: float,
        T: float,
        u_t: float = 0.0,
        v_t: float = 0.0,
        p0_t: Optional[float] = None,
        p0_T: Optional[float] = None
    ) -> float:
        """Calculates closed-form discount bond price P(t, T) given state variables u(t) and v(t)."""
        if T <= t:
            return 1.0

        p0_t_val = p0_t or self.discount_curve.get(t, math.exp(-0.04 * t))
        p0_T_val = p0_T or self.discount_curve.get(T, math.exp(-0.04 * T))

        tau = T - t
        B_a = self.B(self.a, tau)
        B_b = self.B(self.b, tau)

        # Variance adjustment: 0.5 * [V(t, T) - V(0, T) + V(0, t)]
        # Under standard formula: -0.5 * (V(0, T) - V(0, t) - V(t, T))
        var_adj = 0.5 * (self.V(0.0, T) - self.V(0.0, t) - self.V(t, T))

        exponent = -B_a * u_t - B_b * v_t - var_adj
        return (p0_T_val / p0_t_val) * math.exp(exponent)

    def bond_return_correlation(self, tau1: float, tau2: float) -> float:
        """Computes instantaneous correlation between yields of two different maturities tau1 and tau2.
        In 1-factor model this is identically 1.0. In 2-factor model it is strictly < 1.0!
        """
        B_a1 = self.B(self.a, tau1)
        B_b1 = self.B(self.b, tau1)
        B_a2 = self.B(self.a, tau2)
        B_b2 = self.B(self.b, tau2)

        cov12 = (
            (self.sigma1 ** 2) * B_a1 * B_a2 +
            (self.sigma2 ** 2) * B_b1 * B_b2 +
            self.rho * self.sigma1 * self.sigma2 * (B_a1 * B_b2 + B_b1 * B_a2)
        )
        var1 = (self.sigma1 ** 2) * (B_a1 ** 2) + (self.sigma2 ** 2) * (B_b1 ** 2) + 2.0 * self.rho * self.sigma1 * self.sigma2 * B_a1 * B_b1
        var2 = (self.sigma1 ** 2) * (B_a2 ** 2) + (self.sigma2 ** 2) * (B_b2 ** 2) + 2.0 * self.rho * self.sigma1 * self.sigma2 * B_a2 * B_b2

        denom = math.sqrt(max(1e-12, var1 * var2))
        return min(1.0, max(-1.0, cov12 / denom))


# ==============================================================================
# Model 6: Barber & Odean (2000, 2001) / Shefrin & Statman (1985) Disposition Effect
# ==============================================================================
class BarberOdeanDispositionEffectEngine:
    """Brad Barber & Terrance Odean (2000, 2001) / Hersh Shefrin & Meir Statman (1985).
    Evaluates behavioral bias:
    1. Proportion of Gains Realized (PGR) = RG / (RG + PG)
    2. Proportion of Losses Realized (PLR) = RL / (RL + PL)
    3. Disposition Ratio (DR) = PGR / PLR (DR > 1 indicates disposition effect: selling winners too early, holding losers too long).
    4. Two-sample Z-statistic for significance testing.
    5. Overconfidence Penalty: Net Return = Gross Return - Turnover * Roundtrip Trading Cost.
    """

    @staticmethod
    def calculate_disposition_metrics(
        realized_gains: int,
        paper_gains: int,
        realized_losses: int,
        paper_losses: int
    ) -> Dict[str, Any]:
        """Computes PGR, PLR, Disposition Ratio, and Z-score."""
        tot_gains = realized_gains + paper_gains
        tot_losses = realized_losses + paper_losses

        if tot_gains <= 0 or tot_losses <= 0:
            raise ValueError("Total gains and total losses opportunities must be strictly positive.")

        pgr = realized_gains / tot_gains
        plr = realized_losses / tot_losses

        disposition_ratio = pgr / plr if plr > 0 else float("inf")

        # Standard error of difference: sqrt(pgr*(1-pgr)/N_g + plr*(1-plr)/N_l)
        se_pgr = (pgr * (1.0 - pgr)) / tot_gains
        se_plr = (plr * (1.0 - plr)) / tot_losses
        se_diff = math.sqrt(max(1e-12, se_pgr + se_plr))

        z_score = (pgr - plr) / se_diff
        p_value = 1.0 - norm_cdf(z_score)

        return {
            "pgr": pgr,
            "plr": plr,
            "disposition_ratio": disposition_ratio,
            "z_score": z_score,
            "p_value": p_value,
            "has_significant_disposition_effect": bool(z_score > 1.96 and disposition_ratio > 1.0)
        }

    @staticmethod
    def simulate_overconfidence_penalty(
        gross_alpha: float,
        turnover_rates: np.ndarray,
        roundtrip_cost_bps: float = 50.0
    ) -> Dict[str, np.ndarray]:
        """Barber & Odean (2000) 'Trading is Hazardous to Your Wealth'.
        Net Alpha = Gross Alpha - Turnover * Cost.
        turnover_rates: annual portfolio turnover (e.g. 0.20 for 20%, 2.5 for 250%).
        roundtrip_cost_bps: transaction fee + bid/ask spread in basis points (1 bp = 0.0001).
        """
        cost_rate = roundtrip_cost_bps * 1e-4
        drag = turnover_rates * cost_rate
        net_alphas = gross_alpha - drag

        return {
            "turnover_rates": turnover_rates,
            "cost_drags": drag,
            "net_alphas": net_alphas,
            "break_even_turnover": gross_alpha / cost_rate if cost_rate > 0 else float("inf")
        }


# ==============================================================================
# PyTest Verification Suite
# ==============================================================================
class TestFaz57QuantitativeFinanceEngines:
    """Agentic TDD Verification Suite for Faz 57 Quantitative Finance Engines."""

    def test_campbell_vuolteenaho_two_beta_engine(self):
        """Model 1: Verify Campbell & Vuolteenaho (2004) VAR news decomposition and Bad/Good Beta."""
        np.random.seed(42)
        T = 200
        K = 2  # 2-state VAR: [market_excess, dividend_yield]

        # Stable VAR transition matrix
        Gamma = np.array([
            [0.25, 0.15],
            [0.05, 0.60]
        ])
        residuals = np.random.normal(0.0, 0.05, size=(T, K))

        # 1. Decompose news
        decomp = CampbellVuolteenahoTwoBetaEngine.var_news_decomposition(Gamma, residuals, rho=0.96)
        n_dr = decomp["n_dr"]
        n_cf = decomp["n_cf"]
        n_total = decomp["n_total"]

        # Exact identity: N_total = N_CF - N_DR
        assert np.allclose(n_total, n_cf - n_dr, atol=1e-10)

        # 2. Estimate betas for Value stock (higher CF risk) and Growth stock (higher DR risk)
        # Value stock: sensitive to cash-flow news
        value_returns = 1.2 * n_cf + 0.3 * (-n_dr) + np.random.normal(0.0, 0.02, T)
        # Growth stock: sensitive to discount-rate news
        growth_returns = 0.2 * n_cf + 1.1 * (-n_dr) + np.random.normal(0.0, 0.02, T)

        val_betas = CampbellVuolteenahoTwoBetaEngine.estimate_betas(value_returns, n_cf, n_dr, n_total)
        gro_betas = CampbellVuolteenahoTwoBetaEngine.estimate_betas(growth_returns, n_cf, n_dr, n_total)

        assert val_betas["beta_cf"] > gro_betas["beta_cf"]
        assert gro_betas["beta_dr"] > val_betas["beta_dr"]

        # 3. Two-beta pricing equation
        mkt_var = val_betas["market_var"]
        val_exp = CampbellVuolteenahoTwoBetaEngine.calculate_expected_return(val_betas["beta_cf"], val_betas["beta_dr"], mkt_var, gamma=5.0)
        gro_exp = CampbellVuolteenahoTwoBetaEngine.calculate_expected_return(gro_betas["beta_cf"], gro_betas["beta_dr"], mkt_var, gamma=5.0)

        # Because gamma=5, value stock gets higher expected return despite having similar or lower total beta
        assert val_exp["expected_excess_return"] > gro_exp["expected_excess_return"]
        assert val_exp["cf_risk_contribution"] > gro_exp["cf_risk_contribution"]

    def test_barra_factor_risk_engine(self):
        """Model 2: Verify Barra cross-sectional WLS factor returns, covariance forecasting, and active risk decomposition."""
        np.random.seed(101)
        N = 25  # 25 assets
        K = 4   # 4 factors: [Market, Size, Value, Momentum]

        # Standardized factor exposures
        X = np.random.normal(0.0, 1.0, size=(N, K))
        X[:, 0] = 1.0  # market intercept

        true_factors = np.array([0.02, -0.005, 0.012, 0.018])
        noise = np.random.normal(0.0, 0.01, size=N)
        returns = X @ true_factors + noise

        # 1. WLS estimation of pure factor returns
        weights = np.linspace(1.0, 5.0, N)
        wls_res = BarraFactorRiskEngine.estimate_factor_returns_wls(returns, X, weights=weights)
        assert len(wls_res["factor_returns"]) == K
        assert np.allclose(wls_res["factor_returns"], true_factors, atol=0.01)

        # 2. Covariance construction
        Sigma_F = np.diag([0.04, 0.02, 0.025, 0.03])
        specific_vars = np.full(N, 0.05)
        Sigma_asset = BarraFactorRiskEngine.forecast_asset_covariance(X, Sigma_F, specific_vars)
        assert Sigma_asset.shape == (N, N)
        # Symmetry & Positive definiteness
        assert np.allclose(Sigma_asset, Sigma_asset.T)
        eigvals = np.linalg.eigvalsh(Sigma_asset)
        assert (eigvals > 0).all()

        # 3. Active Risk Decomposition
        w_p = np.full(N, 1.0 / N)
        w_b = np.zeros(N)
        w_b[:10] = 1.0 / 10  # concentrated benchmark

        decomp = BarraFactorRiskEngine.active_risk_decomposition(w_p, w_b, X, Sigma_F, specific_vars)
        assert decomp["tracking_error"] > 0.0
        assert abs(decomp["total_active_variance"] - (decomp["factor_active_variance"] + decomp["specific_active_variance"])) < 1e-12
        assert abs(decomp["factor_risk_proportion"] + decomp["specific_risk_proportion"] - 1.0) < 1e-10

        # MCAR sum property: sum(delta_w_i * MCAR_i) = tracking_error
        delta_w = w_p - w_b
        sum_pcar = float(np.sum(decomp["pcar"]))
        assert abs(sum_pcar - 1.0) < 1e-8

    def test_brinson_performance_attribution_engine(self):
        """Model 3: Verify Brinson-Fachler single-period attribution and Cariño multi-period linking."""
        w_p = np.array([0.40, 0.35, 0.25])  # Technology, Financials, Energy
        r_p = np.array([0.15, 0.05, -0.02])
        w_b = np.array([0.30, 0.40, 0.30])
        r_b = np.array([0.10, 0.04, 0.01])

        # 1. Single period Brinson-Fachler
        res = BrinsonPerformanceAttributionEngine.single_period_attribution(w_p, r_p, w_b, r_b, method="brinson_fachler")
        assert abs(res["reconciliation_error"]) < 1e-12

        # Positive allocation to Technology (overweighted good sector)
        assert res["allocation_by_sector"][0] > 0.0
        # Positive selection in Technology (picked better stocks)
        assert res["selection_by_sector"][0] > 0.0

        # 2. Multi-period Cariño linking
        p_rets = [0.03, -0.01, 0.04]
        b_rets = [0.02, -0.015, 0.025]
        period_attribs = [
            {"allocation": 0.005, "selection": 0.004, "interaction": 0.001},
            {"allocation": 0.002, "selection": 0.003, "interaction": 0.000},
            {"allocation": 0.007, "selection": 0.006, "interaction": 0.002},
        ]

        linked = BrinsonPerformanceAttributionEngine.carino_multi_period_linking(p_rets, b_rets, period_attribs)
        assert abs(linked["linking_error"]) < 1e-10
        assert linked["total_cum_excess"] > 0.0
        assert abs(linked["total_cum_excess"] - (linked["cum_allocation"] + linked["cum_selection"] + linked["cum_interaction"])) < 1e-10

    def test_henriksson_merton_pesaran_market_timing_engine(self):
        """Model 4: Verify Henriksson-Merton option timing regression and Pesaran-Timmermann directional test."""
        np.random.seed(77)
        T = 150
        mkt_excess = np.random.normal(0.005, 0.04, T)

        # Successful timer: when market is negative, portfolio cushions loss
        true_alpha = 0.002
        true_beta = 0.85
        true_gamma = 0.40  # strong market timing
        downside_put = np.maximum(0.0, -mkt_excess)
        port_excess = true_alpha + true_beta * mkt_excess + true_gamma * downside_put + np.random.normal(0.0, 0.005, T)

        hm_res = HenrikssonMertonPesaranMarketTimingEngine.estimate_henriksson_merton(port_excess, mkt_excess)
        assert hm_res["gamma_timing"] > 0.20
        assert hm_res["t_gamma"] > 2.0
        assert hm_res["has_market_timing_skill"] is True

        # Pesaran-Timmermann Directional Test
        # Case A: Random noise forecasts
        random_pred = np.random.normal(0.0, 1.0, T)
        pt_random = HenrikssonMertonPesaranMarketTimingEngine.pesaran_timmermann_directional_test(mkt_excess, random_pred)
        assert pt_random["pt_statistic"] < 1.96

        # Case B: Skilled directional forecast (85% correct signs)
        skilled_pred = np.where(np.random.rand(T) < 0.85, mkt_excess, -mkt_excess)
        pt_skilled = HenrikssonMertonPesaranMarketTimingEngine.pesaran_timmermann_directional_test(mkt_excess, skilled_pred)
        assert pt_skilled["success_ratio"] > 0.75
        assert pt_skilled["pt_statistic"] > 3.0
        assert pt_skilled["is_significant_95"] is True

    def test_hull_white_two_factor_engine(self):
        """Model 5: Verify Hull-White 2F (G2++) bond pricing and imperfect correlation across maturities."""
        a = 0.10
        b = 0.40
        sigma1 = 0.012
        sigma2 = 0.018
        rho = -0.70  # strong negative correlation

        engine = HullWhiteTwoFactorEngine(a, b, sigma1, sigma2, rho)

        # 1. Variance function positivity
        v_0_5 = engine.V(0.0, 5.0)
        assert v_0_5 > 0.0

        # 2. Discount bond pricing
        p_0_5 = engine.zero_coupon_bond_price(t=0.0, T=5.0, u_t=0.0, v_t=0.0)
        assert 0.0 < p_0_5 < 1.0

        # When short rates jump up (u > 0, v > 0), bond prices fall
        p_shocked = engine.zero_coupon_bond_price(t=1.0, T=5.0, u_t=0.02, v_t=0.01)
        p_unshocked = engine.zero_coupon_bond_price(t=1.0, T=5.0, u_t=0.0, v_t=0.0)
        assert p_shocked < p_unshocked

        # 3. Imperfect correlation: 2Y vs 10Y rates have correlation < 1.0
        corr_2_10 = engine.bond_return_correlation(tau1=2.0, tau2=10.0)
        assert 0.0 < corr_2_10 < 0.99  # Crucial: NOT 1.0 as in 1-factor model!

        # As maturities approach each other, correlation approaches 1.0
        corr_close = engine.bond_return_correlation(tau1=5.0, tau2=5.05)
        assert corr_close > 0.999

    def test_barber_odean_disposition_effect_engine(self):
        """Model 6: Verify Shefrin-Statman disposition ratio and Barber-Odean overconfidence turnover penalty."""
        # Realistic investor data: sells 120 winners out of 200, but only 40 losers out of 200
        res = BarberOdeanDispositionEffectEngine.calculate_disposition_metrics(
            realized_gains=120, paper_gains=80, realized_losses=40, paper_losses=160
        )
        assert res["pgr"] == 0.60
        assert res["plr"] == 0.20
        assert abs(res["disposition_ratio"] - 3.0) < 1e-10
        assert res["z_score"] > 5.0
        assert res["has_significant_disposition_effect"] is True

        # Overconfidence turnover penalty
        gross_alpha = 0.03  # 3% gross alpha
        turnovers = np.array([0.20, 1.0, 3.0, 5.0])  # 20%, 100%, 300%, 500%
        sim = BarberOdeanDispositionEffectEngine.simulate_overconfidence_penalty(
            gross_alpha=gross_alpha, turnover_rates=turnovers, roundtrip_cost_bps=50.0
        )

        assert sim["net_alphas"][0] > 0.025   # low turnover preserves alpha
        assert sim["net_alphas"][-1] < 0.005  # excessive turnover kills alpha
        assert sim["break_even_turnover"] == 6.0
