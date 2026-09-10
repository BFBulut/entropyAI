"""Programmatic TDD Verification Suite for Faz 66 Quantitative Finance Engines.

Models:
1. J. Michael Harrison & Stanley R. Pliska (1981, 1983) / Delbaen & Schachermayer (1994):
   Fundamental Theorems of Asset Pricing (FTAP), Equivalent Martingale Measures (EMM),
   Radon-Nikodym Density Process, Girsanov Change of Measure, and Super-Hedging Bounds.
2. David Heath, Robert Jarrow & Andrew Morton (HJM 1992):
   Forward-Rate Term Structure Modeling, No-Arbitrage Forward Drift Restriction,
   Analytical Zero-Coupon Bond Pricing, and Bond Volatility Structure.
3. Robert E. Lucas Jr. (1978) (Nobel Prize in Economics 1995):
   Lucas Asset Pricing Tree in Pure Exchange Economy, Stochastic Discount Factor (SDF),
   Closed-Form Price-Dividend Ratio, Gross Equity Return, and Equity Premium.
4. Roger D. Huang & Hans R. Stoll (1997):
   Structural Three-Way Bid-Ask Spread Decomposition (Adverse Selection, Inventory Holding,
   and Order Processing Costs) via Trade Direction Markov Transitions.
5. Michael R. Gibbons, Stephen A. Ross & Jay Shanken (GRS 1989):
   GRS Finite-Sample F-Test for Mean-Variance Efficiency, Joint Alpha Null Hypothesis,
   and Quadratic Expansion of the Maximum Squared Sharpe Ratio.
6. Peter F. Christoffersen (1998) & Paul H. Kupiec (1995):
   Value-at-Risk (VaR) Statistical Backtesting: Kupiec Unconditional Coverage LR_uc,
   Christoffersen Independence Markov LR_ind, and Combined Conditional Coverage LR_cc.
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Math Primitives
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def chi2_cdf_1df(x: float) -> float:
    """Analytical CDF of Chi-square distribution with 1 degree of freedom."""
    if x <= 0.0:
        return 0.0
    return 2.0 * norm_cdf(math.sqrt(x)) - 1.0


def chi2_cdf_2df(x: float) -> float:
    """Analytical CDF of Chi-square distribution with 2 degrees of freedom."""
    if x <= 0.0:
        return 0.0
    return 1.0 - math.exp(-0.5 * x)


def f_cdf_approx(F: float, df1: int, df2: int) -> float:
    """Approximation of F-distribution CDF via regularized beta / Paulson-Wilson transform."""
    if F <= 0.0:
        return 0.0
    # Wilson-Hilferty transformation for F to standard normal
    d1 = float(df1)
    d2 = float(df2)
    term1 = (1.0 - 2.0 / (9.0 * d2)) * (F ** (1.0 / 3.0)) - (1.0 - 2.0 / (9.0 * d1))
    term2 = math.sqrt((2.0 / (9.0 * d2)) * (F ** (2.0 / 3.0)) + (2.0 / (9.0 * d1)))
    z = term1 / term2
    return max(0.0, min(1.0, norm_cdf(z)))


# ==============================================================================
# 1. Harrison & Pliska (1981, 1983) / Delbaen & Schachermayer (1994) Engine
# ==============================================================================
class HarrisonPliskaFTAPEngine:
    """J. Michael Harrison & Stanley R. Pliska (1981, 1983) / Delbaen & Schachermayer (1994).
    
    Fundamental Theorems of Asset Pricing (FTAP), Equivalent Martingale Measures (EMM),
    Girsanov Change of Measure, and Incomplete Market Super-Hedging Bounds.
    """

    @staticmethod
    def continuous_girsanov_density(
        mu: float,
        r: float,
        sigma: float,
        T: float,
        W_T: float
    ) -> Dict[str, Any]:
        """Calculates market price of risk, Radon-Nikodym derivative Z_T, and Girsanov shift.
        
        theta = (mu - r) / sigma
        Z_T = exp(-theta * W_T - 0.5 * theta^2 * T)
        """
        if sigma <= 1e-7:
            raise ValueError("Volatility sigma must be strictly positive.")
        theta = (mu - r) / sigma
        exponent = -theta * W_T - 0.5 * (theta ** 2) * T
        Z_T = math.exp(exponent)
        
        # Novikov condition check: E[exp(0.5 * theta^2 * T)] < infinity
        novikov_exponent = 0.5 * (theta ** 2) * T
        novikov_satisfied = novikov_exponent < 500.0
        
        return {
            "market_price_of_risk": theta,
            "radon_nikodym_density": Z_T,
            "drift_under_P": mu,
            "drift_under_Q": r,
            "girsanov_drift_shift": -theta,
            "novikov_satisfied": novikov_satisfied,
            "novikov_exponent": novikov_exponent
        }

    @staticmethod
    def verify_discrete_ftap_completeness(
        payoff_matrix: np.ndarray,
        asset_prices: np.ndarray,
        r: float = 0.0
    ) -> Dict[str, Any]:
        """Verifies FTAP 1 (NFLVR / existence of EMM Q > 0) and FTAP 2 (Completeness / uniqueness of Q).
        
        payoff_matrix D: (M, S) where M is number of traded assets, S is number of states.
        asset_prices S0: (M,) initial prices.
        EMM condition: D * q = (1 + r) * S0, with q_s > 0 for all s in {1..S} and sum(q_s) = 1.
        """
        M, S = payoff_matrix.shape
        discounted_prices = (1.0 + r) * asset_prices
        
        # We need to solve: D * q = discounted_prices, sum(q) = 1, q > 0
        # Augmented system: A * q = b
        A = np.vstack([payoff_matrix, np.ones((1, S))])
        b = np.append(discounted_prices, 1.0)
        
        # Rank of augmented matrix and payoff matrix
        rank_D = int(np.linalg.matrix_rank(payoff_matrix))
        rank_A = int(np.linalg.matrix_rank(A))
        
        # Least-squares solution
        q_sol, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
        
        # Check if q is strictly positive and valid probability distribution
        is_martingale = np.allclose(payoff_matrix @ q_sol, discounted_prices, atol=1e-5)
        sums_to_one = np.isclose(np.sum(q_sol), 1.0, atol=1e-5)
        is_strictly_positive = bool(np.all(q_sol > 1e-6))
        
        arbitrage_free = is_martingale and sums_to_one and is_strictly_positive
        is_complete = arbitrage_free and (rank_D == S - 1 or rank_A == S)
        
        return {
            "num_assets": M,
            "num_states": S,
            "rank_payoff": rank_D,
            "rank_augmented": rank_A,
            "q_measure": q_sol.tolist(),
            "arbitrage_free": arbitrage_free,
            "market_complete": is_complete,
            "unique_emm": is_complete
        }

    @staticmethod
    def incomplete_market_superhedging_bounds(
        S0: float,
        u: float,
        m: float,
        d: float,
        K: float,
        r: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates super-replication (upper) and sub-replication (lower) bounds in trinomial incomplete market.
        
        Asset can move to S0*u, S0*m, S0*d with u > 1+r > d and u > m > d.
        For a call option H = max(0, S_T - K):
        EMMs are parametrized by probability q_m in [0, q_m_max].
        """
        R = 1.0 + r
        if not (u > R > d and u > m > d):
            raise ValueError("Parameters must satisfy u > 1+r > d and u > m > d.")
        
        # Payoffs at maturity
        H_u = max(0.0, S0 * u - K)
        H_m = max(0.0, S0 * m - K)
        H_d = max(0.0, S0 * d - K)
        
        # Under EMM: q_u * u + q_m * m + q_d * d = R, q_u + q_m + q_d = 1
        # => q_u * (u - d) + q_m * (m - d) = R - d
        # => q_u = [(R - d) - q_m * (m - d)] / (u - d)
        # => q_d = [(u - R) - q_m * (u - m)] / (u - d)
        # Strict positivity: q_u > 0 and q_d > 0 gives range for q_m
        q_m_max = min((R - d) / (m - d), (u - R) / (u - m))
        
        # Evaluate option price across the boundary of EMM simplex
        q_m_vals = [0.0001, q_m_max - 0.0001]
        prices = []
        for q_m in q_m_vals:
            q_u = ((R - d) - q_m * (m - d)) / (u - d)
            q_d = ((u - R) - q_m * (u - m)) / (u - d)
            V = (1.0 / R) * (q_u * H_u + q_m * H_m + q_d * H_d)
            prices.append(V)
            
        lower_bound = min(prices)
        upper_bound = max(prices)
        spread = upper_bound - lower_bound
        
        return {
            "S0": S0,
            "K": K,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "superhedging_spread": spread,
            "is_incomplete": spread > 1e-6
        }


# ==============================================================================
# 2. David Heath, Robert Jarrow & Andrew Morton (HJM 1992) Engine
# ==============================================================================
class HeathJarrowMortonHJMEngine:
    """David Heath, Robert Jarrow & Andrew Morton (1992).
    
    Forward-Rate Term Structure Modeling, Arbitrage-Free Drift Restriction,
    Zero-Coupon Bond Pricing, and Analytical Forward Curve Evolution.
    """

    @staticmethod
    def forward_rate_drift_restriction(
        sigma_f: float,
        T: float,
        t: float,
        model_type: str = "constant"
    ) -> float:
        """Calculates risk-neutral forward rate drift alpha(t, T) = sigma(t, T) * int_t^T sigma(t, u) du.
        
        If sigma(t, u) = sigma_0 (constant):
        int_t^T sigma_0 du = sigma_0 * (T - t)
        alpha(t, T) = sigma_0^2 * (T - t)
        
        If sigma(t, u) = sigma_0 * exp(-lambda * (u - t)) (Vasicek-type / exponentially damped):
        int_t^T sigma_0 * exp(-lambda*(u-t)) du = (sigma_0 / lambda) * [1 - exp(-lambda*(T-t))]
        alpha(t, T) = (sigma_0^2 / lambda) * exp(-lambda*(T-t)) * [1 - exp(-lambda*(T-t))]
        """
        tau = max(0.0, T - t)
        if model_type == "constant":
            return (sigma_f ** 2) * tau
        elif model_type == "exponential":
            lam = 0.15  # standard mean reversion rate
            integral = (sigma_f / lam) * (1.0 - math.exp(-lam * tau))
            vol_t_T = sigma_f * math.exp(-lam * tau)
            return vol_t_T * integral
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    @classmethod
    def evolve_forward_curve(
        cls,
        maturities: np.ndarray,
        initial_forward_curve: np.ndarray,
        dt: float,
        sigma_f: float,
        dW: float,
        model_type: str = "constant"
    ) -> Dict[str, Any]:
        """Evolves the forward curve f(0, T) to f(dt, T) under the exact no-arbitrage HJM condition.
        
        df(t, T) = alpha(t, T) * dt + sigma(t, T) * dW
        """
        evolved_curve = np.zeros_like(initial_forward_curve)
        drifts = np.zeros_like(initial_forward_curve)
        vols = np.zeros_like(initial_forward_curve)
        
        for i, T in enumerate(maturities):
            if T < dt:
                evolved_curve[i] = initial_forward_curve[i]
                continue
            alpha_i = cls.forward_rate_drift_restriction(sigma_f, T, dt, model_type=model_type)
            drifts[i] = alpha_i
            
            if model_type == "constant":
                vol_i = sigma_f
            else:
                lam = 0.15
                vol_i = sigma_f * math.exp(-lam * (T - dt))
            vols[i] = vol_i
            
            df = alpha_i * dt + vol_i * dW
            evolved_curve[i] = initial_forward_curve[i] + df
            
        # Analytical short rate at t = dt is f(dt, dt)
        short_rate = float(evolved_curve[0])
        
        return {
            "initial_curve": initial_forward_curve.tolist(),
            "evolved_curve": evolved_curve.tolist(),
            "drifts": drifts.tolist(),
            "vols": vols.tolist(),
            "short_rate_dt": short_rate
        }

    @staticmethod
    def zero_coupon_bond_price(
        maturities: np.ndarray,
        forward_curve: np.ndarray
    ) -> np.ndarray:
        """Computes zero-coupon bond prices P(0, T) = exp(-int_0^T f(0, u) du) using trapezoidal integration."""
        n = len(maturities)
        bond_prices = np.zeros(n)
        bond_prices[0] = 1.0  # P(0, 0) = 1
        
        cumulative_integral = 0.0
        for i in range(1, n):
            dT = maturities[i] - maturities[i - 1]
            f_avg = 0.5 * (forward_curve[i] + forward_curve[i - 1])
            cumulative_integral += f_avg * dT
            bond_prices[i] = math.exp(-cumulative_integral)
            
        return bond_prices

    @staticmethod
    def bond_volatility_structure(
        sigma_f: float,
        T: float,
        t: float = 0.0,
        model_type: str = "constant"
    ) -> float:
        """Computes zero-coupon bond volatility sigma_P(t, T) = int_t^T sigma(t, u) du."""
        tau = max(0.0, T - t)
        if model_type == "constant":
            return sigma_f * tau
        elif model_type == "exponential":
            lam = 0.15
            return (sigma_f / lam) * (1.0 - math.exp(-lam * tau))
        else:
            raise ValueError("Unknown model type")


# ==============================================================================
# 3. Robert E. Lucas Jr. (1978) Engine
# ==============================================================================
class LucasAssetPricingTreeEngine:
    """Robert E. Lucas Jr. (1978) (Nobel Prize in Economics 1995).
    
    Lucas Asset Pricing Tree in Pure Exchange Economy, Stochastic Discount Factor (SDF),
    Analytical Price-Dividend Ratio, Gross Equity Return, and Equity Premium.
    """

    @staticmethod
    def solve_equilibrium_pricing(
        beta: float,
        gamma: float,
        mu_g: float,
        sigma_g: float
    ) -> Dict[str, Any]:
        """Calculates closed-form equilibrium price-dividend ratio, risk-free rate, and equity premium.
        
        Representative agent with CRRA utility u(C) = C^(1-gamma) / (1-gamma).
        Dividend growth g = ln(y_{t+1}/y_t) ~ N(mu_g, sigma_g^2).
        SDF: M_{t+1} = beta * exp(-gamma * g_{t+1}).
        
        Price-dividend ratio psi = P/y satisfies:
        psi = E[beta * exp((1-gamma)*g)] / (1 - E[beta * exp((1-gamma)*g)])
        """
        if not (0.0 < beta < 1.0):
            raise ValueError("Subjective discount factor beta must be in (0, 1).")
        if gamma < 0.0:
            raise ValueError("Relative risk aversion gamma must be non-negative.")
            
        # Expected SDF growth component
        # E[exp((1-gamma)*g)] = exp((1-gamma)*mu_g + 0.5 * (1-gamma)^2 * sigma_g^2)
        exponent_growth = (1.0 - gamma) * mu_g + 0.5 * ((1.0 - gamma) ** 2) * (sigma_g ** 2)
        kernel_growth = beta * math.exp(exponent_growth)
        
        if kernel_growth >= 1.0:
            raise ValueError("Transversality / Convergence condition violated: beta * E[g^(1-gamma)] >= 1.")
            
        # Price-dividend ratio psi = P / y
        price_dividend_ratio = kernel_growth / (1.0 - kernel_growth)
        
        # Risk-free rate R_f = 1 / E[M]
        # E[M] = beta * exp(-gamma * mu_g + 0.5 * gamma^2 * sigma_g^2)
        expected_sdf = beta * math.exp(-gamma * mu_g + 0.5 * (gamma ** 2) * (sigma_g ** 2))
        gross_risk_free_rate = 1.0 / expected_sdf
        net_risk_free_rate = gross_risk_free_rate - 1.0
        
        # Gross expected stock return E[R_stock] = E[(P_{t+1} + y_{t+1}) / P_t]
        # = ((psi + 1) / psi) * E[exp(g)] = ((psi + 1) / psi) * exp(mu_g + 0.5 * sigma_g^2)
        gross_expected_return = ((price_dividend_ratio + 1.0) / price_dividend_ratio) * math.exp(mu_g + 0.5 * (sigma_g ** 2))
        net_expected_return = gross_expected_return - 1.0
        
        # Equity Risk Premium
        equity_premium = net_expected_return - net_risk_free_rate
        
        # Hansen-Jagannathan bound check: std(M) / E[M]
        var_sdf = (beta ** 2) * math.exp(-2.0 * gamma * mu_g + (gamma ** 2) * (sigma_g ** 2)) * (math.exp((gamma ** 2) * (sigma_g ** 2)) - 1.0)
        std_sdf = math.sqrt(max(0.0, var_sdf))
        hj_sharpe_bound = std_sdf / expected_sdf
        
        return {
            "price_dividend_ratio": price_dividend_ratio,
            "gross_risk_free_rate": gross_risk_free_rate,
            "net_risk_free_rate": net_risk_free_rate,
            "gross_expected_stock_return": gross_expected_return,
            "net_expected_stock_return": net_expected_return,
            "equity_risk_premium": equity_premium,
            "hj_sharpe_bound": hj_sharpe_bound
        }


# ==============================================================================
# 4. Roger D. Huang & Hans R. Stoll (1997) Engine
# ==============================================================================
class HuangStollSpreadDecompositionEngine:
    """Roger D. Huang & Hans R. Stoll (1997).
    
    Structural Three-Way Bid-Ask Spread Decomposition (Adverse Selection, Inventory Holding,
    and Order Processing Costs) via Trade Direction Markov Transitions.
    """

    @staticmethod
    def estimate_spread_components(
        midquote_changes: np.ndarray,
        trade_indicators: np.ndarray,
        spread: float
    ) -> Dict[str, Any]:
        """Decomposes spread S into:
        alpha: Adverse selection (private information)
        beta: Inventory holding cost
        gamma: Order processing cost (1 - alpha - beta)
        
        Regression model:
        Delta M_t = (alpha + beta) * (S/2) * Q_t - alpha * (1 - 2*pi) * (S/2) * Q_{t-1} + e_t
        where pi = P(Q_t = Q_{t-1}).
        """
        T = len(trade_indicators)
        if len(midquote_changes) != T:
            raise ValueError("midquote_changes and trade_indicators must have same length.")
        if T < 10:
            raise ValueError("Sample size too small for Huang-Stoll estimation.")
            
        # Estimate Markov continuation probability pi = P(Q_t == Q_{t-1})
        continuations = np.sum(trade_indicators[1:] == trade_indicators[:-1])
        pi = float(continuations / (T - 1))
        
        # Regressors:
        # X1_t = (S / 2) * Q_t
        # X2_t = (S / 2) * Q_{t-1}
        half_spread = spread / 2.0
        X1 = half_spread * trade_indicators[1:]
        X2 = half_spread * trade_indicators[:-1]
        Y = midquote_changes[1:]
        
        # OLS: Y = b1 * X1 + b2 * X2
        # where b1 = alpha + beta
        # b2 = -alpha * (1 - 2*pi) = alpha * (2*pi - 1)
        X = np.column_stack([X1, X2])
        coeffs, residuals, rank, s = np.linalg.lstsq(X, Y, rcond=None)
        b1, b2 = coeffs[0], coeffs[1]
        
        # Recover alpha, beta, gamma
        # If 2*pi - 1 != 0: alpha = b2 / (2*pi - 1)
        denom = 2.0 * pi - 1.0
        if abs(denom) > 1e-4:
            alpha = float(b2 / denom)
        else:
            alpha = float(max(0.0, b1 * 0.5))
            
        # Bound alpha within reasonable theoretical boundaries [0, 1]
        alpha = max(0.0, min(0.8, alpha))
        beta = max(0.0, min(0.8, float(b1 - alpha)))
        
        gamma = max(0.0, 1.0 - alpha - beta)
        # Normalize sum to 1.0
        total = alpha + beta + gamma
        alpha /= total
        beta /= total
        gamma /= total
        
        return {
            "half_spread": half_spread,
            "markov_continuation_prob": pi,
            "b1_combined_coef": float(b1),
            "b2_lagged_coef": float(b2),
            "adverse_selection_alpha": alpha,
            "inventory_cost_beta": beta,
            "order_processing_gamma": gamma,
            "alpha_dollar": alpha * spread,
            "beta_dollar": beta * spread,
            "gamma_dollar": gamma * spread
        }


# ==============================================================================
# 5. Michael R. Gibbons, Stephen A. Ross & Jay Shanken (GRS 1989) Engine
# ==============================================================================
class GibbonsRossShankenGRSEngine:
    """Michael R. Gibbons, Stephen A. Ross & Jay Shanken (1989).
    
    GRS Finite-Sample F-Test for Mean-Variance Efficiency, Joint Alpha Null Hypothesis,
    and Quadratic Expansion of the Maximum Squared Sharpe Ratio.
    """

    @staticmethod
    def compute_grs_test(
        alphas: np.ndarray,
        residual_covariance: np.ndarray,
        factor_returns: np.ndarray,
        T: int
    ) -> Dict[str, Any]:
        """Calculates the GRS F-statistic and p-value.
        
        alphas: (N,) vector of pricing errors
        residual_covariance: (N, N) residual covariance matrix Sigma_eps
        factor_returns: (T, K) matrix of benchmark factor returns
        T: number of time periods
        
        GRS = [(T - N - K) / N] * [1 + mu_K' Sigma_K^(-1) mu_K]^(-1) * [alpha' Sigma_eps^(-1) alpha]
        """
        N = len(alphas)
        K = factor_returns.shape[1] if factor_returns.ndim > 1 else 1
        
        if T <= N + K:
            raise ValueError(f"Sample size T ({T}) must be strictly greater than N + K ({N + K}).")
            
        # Factor mean vector and covariance matrix
        if factor_returns.ndim == 1:
            factor_returns = factor_returns.reshape(-1, 1)
        mu_K = np.mean(factor_returns, axis=0)
        cov_K = np.cov(factor_returns, rowvar=False)
        if K == 1:
            cov_K = np.array([[float(cov_K)]])
            
        inv_cov_K = np.linalg.pinv(cov_K)
        # Factor Sharpe ratio squared: Sh_K^2 = mu_K' * inv_cov_K * mu_K
        factor_sharpe_sq = float(mu_K.T @ inv_cov_K @ mu_K)
        
        # Residual covariance inversion
        inv_sigma_eps = np.linalg.pinv(residual_covariance)
        alpha_quad = float(alphas.T @ inv_sigma_eps @ alphas)
        
        # GRS F-Statistic
        df1 = N
        df2 = T - N - K
        grs_stat = ((T - N - K) / N) * (1.0 / (1.0 + factor_sharpe_sq)) * alpha_quad
        
        # Approximate p-value
        cdf_val = f_cdf_approx(grs_stat, df1, df2)
        p_value = max(0.0, min(1.0, 1.0 - cdf_val))
        
        # Reject null hypothesis of zero alphas at 5% significance
        reject_null = p_value < 0.05
        
        return {
            "N_assets": N,
            "K_factors": K,
            "T_periods": T,
            "df1": df1,
            "df2": df2,
            "factor_sharpe_sq": factor_sharpe_sq,
            "alpha_quadratic_form": alpha_quad,
            "grs_statistic": grs_stat,
            "p_value": p_value,
            "reject_null_5pct": reject_null
        }


# ==============================================================================
# 6. Peter F. Christoffersen (1998) & Paul H. Kupiec (1995) Engine
# ==============================================================================
class ChristoffersenKupiecVaRBacktestEngine:
    """Peter F. Christoffersen (1998) & Paul H. Kupiec (1995).
    
    Value-at-Risk (VaR) Statistical Backtesting: Kupiec Unconditional Coverage LR_uc,
    Christoffersen Independence Markov LR_ind, and Combined Conditional Coverage LR_cc.
    """

    @staticmethod
    def run_backtest(
        losses: np.ndarray,
        var_forecasts: np.ndarray,
        alpha_coverage: float = 0.95
    ) -> Dict[str, Any]:
        """Runs Kupiec Unconditional Coverage, Christoffersen Independence, and Conditional Coverage tests.
        
        losses: realized loss vector (positive for losses)
        var_forecasts: forecasted VaR vector (positive threshold)
        alpha_coverage: e.g. 0.95 or 0.99 (expected violation prob p = 1 - alpha)
        """
        T = len(losses)
        if len(var_forecasts) != T:
            raise ValueError("losses and var_forecasts must have identical length.")
            
        p = 1.0 - alpha_coverage
        # Indicator sequence: 1 if loss > VaR, 0 otherwise
        hits = (losses > var_forecasts).astype(int)
        N_violations = int(np.sum(hits))
        p_hat = N_violations / T if T > 0 else 0.0
        
        # 1. Kupiec LR_uc Test
        # LR_uc = -2 * ln( L(p) / L(p_hat) )
        # L(p) = (1 - p)^(T - N) * p^N
        if N_violations == 0:
            lr_uc = -2.0 * math.log((1.0 - p) ** T)
        elif N_violations == T:
            lr_uc = -2.0 * math.log(p ** T)
        else:
            log_L_null = (T - N_violations) * math.log(1.0 - p) + N_violations * math.log(p)
            log_L_alt = (T - N_violations) * math.log(1.0 - p_hat) + N_violations * math.log(p_hat)
            lr_uc = -2.0 * (log_L_null - log_L_alt)
        lr_uc = max(0.0, lr_uc)
        p_value_uc = 1.0 - chi2_cdf_1df(lr_uc)
        
        # 2. Christoffersen LR_ind Test (Markov transition test)
        # Counts of transitions: n00, n01, n10, n11
        n00, n01, n10, n11 = 0, 0, 0, 0
        for t in range(1, T):
            prev = hits[t - 1]
            curr = hits[t]
            if prev == 0 and curr == 0:
                n00 += 1
            elif prev == 0 and curr == 1:
                n01 += 1
            elif prev == 1 and curr == 0:
                n10 += 1
            elif prev == 1 and curr == 1:
                n11 += 1
                
        pi_01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
        pi_11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
        pi_2 = (n01 + n11) / (n00 + n01 + n10 + n11) if (n00 + n01 + n10 + n11) > 0 else 0.0
        
        # Log likelihood under independence
        log_L_ind_null = 0.0
        if 0.0 < pi_2 < 1.0:
            log_L_ind_null = (n00 + n10) * math.log(1.0 - pi_2) + (n01 + n11) * math.log(pi_2)
            
        log_L_ind_alt = 0.0
        if 0.0 < pi_01 < 1.0:
            log_L_ind_alt += n00 * math.log(1.0 - pi_01) + n01 * math.log(pi_01)
        if 0.0 < pi_11 < 1.0:
            log_L_ind_alt += n10 * math.log(1.0 - pi_11) + n11 * math.log(pi_11)
            
        lr_ind = -2.0 * (log_L_ind_null - log_L_ind_alt)
        lr_ind = max(0.0, lr_ind)
        p_value_ind = 1.0 - chi2_cdf_1df(lr_ind)
        
        # 3. Christoffersen LR_cc Conditional Coverage (Joint test)
        lr_cc = lr_uc + lr_ind
        p_value_cc = 1.0 - chi2_cdf_2df(lr_cc)
        
        return {
            "T_observations": T,
            "N_violations": N_violations,
            "expected_violations": T * p,
            "empirical_failure_rate": p_hat,
            "expected_failure_rate": p,
            "kupiec_lr_uc": lr_uc,
            "p_value_uc": p_value_uc,
            "reject_uc_5pct": p_value_uc < 0.05,
            "transition_matrix": {
                "n00": n00, "n01": n01,
                "n10": n10, "n11": n11
            },
            "christoffersen_lr_ind": lr_ind,
            "p_value_ind": p_value_ind,
            "reject_ind_5pct": p_value_ind < 0.05,
            "christoffersen_lr_cc": lr_cc,
            "p_value_cc": p_value_cc,
            "reject_cc_5pct": p_value_cc < 0.05
        }


# ==============================================================================
# PYTEST VERIFICATION SUITE
# ==============================================================================

def test_harrison_pliska_ftap_engine():
    """Verify FTAP 1 & 2 theorems, Girsanov density, and super-hedging bounds."""
    # 1. Girsanov Density Verification
    girs = HarrisonPliskaFTAPEngine.continuous_girsanov_density(
        mu=0.10, r=0.04, sigma=0.20, T=1.0, W_T=0.5
    )
    assert pytest.approx(girs["market_price_of_risk"], 1e-4) == 0.30
    assert girs["radon_nikodym_density"] > 0.0
    assert girs["novikov_satisfied"] is True
    
    # 2. Discrete Complete Market FTAP (Binary state / Binomial model)
    # Asset 1: Bond (payoff 1.05 in both states), Asset 2: Stock (120 in up, 80 in down)
    D_complete = np.array([
        [1.05, 1.05],
        [120.0, 80.0]
    ])
    S0_complete = np.array([1.0, 100.0])
    res_complete = HarrisonPliskaFTAPEngine.verify_discrete_ftap_completeness(
        payoff_matrix=D_complete, asset_prices=S0_complete, r=0.05
    )
    assert res_complete["arbitrage_free"] is True
    assert res_complete["market_complete"] is True
    assert len(res_complete["q_measure"]) == 2
    assert all(q > 0.0 for q in res_complete["q_measure"])
    
    # 3. Incomplete Market Super-Hedging Bounds (Trinomial model)
    bounds = HarrisonPliskaFTAPEngine.incomplete_market_superhedging_bounds(
        S0=100.0, u=1.3, m=1.05, d=0.8, K=100.0, r=0.05
    )
    assert bounds["is_incomplete"] is True
    assert bounds["lower_bound"] < bounds["upper_bound"]
    assert bounds["superhedging_spread"] > 0.0


def test_heath_jarrow_morton_hjm_engine():
    """Verify HJM no-arbitrage drift restriction, curve evolution, and bond pricing."""
    # 1. Constant volatility HJM drift restriction: alpha(t, T) = sigma^2 * (T - t)
    sigma = 0.015
    drift_const = HeathJarrowMortonHJMEngine.forward_rate_drift_restriction(
        sigma_f=sigma, T=5.0, t=2.0, model_type="constant"
    )
    assert pytest.approx(drift_const, 1e-6) == (sigma ** 2) * 3.0
    
    # 2. Curve evolution test
    maturities = np.array([0.5, 1.0, 2.0, 5.0, 10.0])
    f0 = np.array([0.03, 0.032, 0.035, 0.04, 0.045])
    evolved = HeathJarrowMortonHJMEngine.evolve_forward_curve(
        maturities=maturities,
        initial_forward_curve=f0,
        dt=0.5,
        sigma_f=0.015,
        dW=0.1,
        model_type="constant"
    )
    assert len(evolved["evolved_curve"]) == len(f0)
    assert all(d >= 0.0 for d in evolved["drifts"])
    
    # 3. Zero-coupon bond price calculation
    bond_prices = HeathJarrowMortonHJMEngine.zero_coupon_bond_price(maturities, f0)
    assert bond_prices[0] == 1.0
    # Prices must strictly decrease with maturity for positive forward rates
    assert np.all(np.diff(bond_prices) < 0.0)


def test_lucas_asset_pricing_tree_engine():
    """Verify Lucas tree equilibrium price-dividend ratio, risk-free rate, and equity premium."""
    eq = LucasAssetPricingTreeEngine.solve_equilibrium_pricing(
        beta=0.96, gamma=2.5, mu_g=0.02, sigma_g=0.03
    )
    assert eq["price_dividend_ratio"] > 0.0
    assert eq["gross_risk_free_rate"] > 1.0
    assert eq["net_expected_stock_return"] > eq["net_risk_free_rate"]
    assert eq["equity_risk_premium"] > 0.0
    assert eq["hj_sharpe_bound"] > 0.0


def test_huang_stoll_spread_decomposition_engine():
    """Verify Huang & Stoll three-way spread decomposition."""
    np.random.seed(42)
    T = 200
    spread = 0.50
    half_spread = spread / 2.0
    
    # Simulate trade indicators with continuation tendency (pi = 0.65)
    trade_indicators = np.zeros(T)
    trade_indicators[0] = 1.0
    for t in range(1, T):
        if np.random.rand() < 0.65:
            trade_indicators[t] = trade_indicators[t - 1]
        else:
            trade_indicators[t] = -trade_indicators[t - 1]
            
    # Simulate midquote changes with private information impact and inventory mean-reversion
    midquote_changes = 0.3 * half_spread * trade_indicators + np.random.normal(0, 0.02, T)
    
    decomp = HuangStollSpreadDecompositionEngine.estimate_spread_components(
        midquote_changes=midquote_changes,
        trade_indicators=trade_indicators,
        spread=spread
    )
    assert 0.0 <= decomp["adverse_selection_alpha"] <= 1.0
    assert 0.0 <= decomp["inventory_cost_beta"] <= 1.0
    assert 0.0 <= decomp["order_processing_gamma"] <= 1.0
    assert pytest.approx(
        decomp["adverse_selection_alpha"] + decomp["inventory_cost_beta"] + decomp["order_processing_gamma"],
        1e-4
    ) == 1.0


def test_gibbons_ross_shanken_grs_engine():
    """Verify GRS F-test statistic under true null and alternative hypotheses."""
    np.random.seed(42)
    T = 500
    N = 5
    K = 1
    
    factor_returns = np.random.normal(0.008, 0.04, (T, K))
    
    # 1. Under H0: alphas = 0
    zero_alphas = np.zeros(N)
    resids = np.random.normal(0, 0.02, (T, N))
    cov_eps = np.cov(resids, rowvar=False)
    
    grs_h0 = GibbonsRossShankenGRSEngine.compute_grs_test(
        alphas=zero_alphas,
        residual_covariance=cov_eps,
        factor_returns=factor_returns,
        T=T
    )
    assert pytest.approx(grs_h0["grs_statistic"], 1e-6) == 0.0
    assert grs_h0["reject_null_5pct"] is False
    
    # 2. Under H1: large pricing errors
    large_alphas = np.array([0.05, -0.04, 0.06, -0.05, 0.07])
    grs_h1 = GibbonsRossShankenGRSEngine.compute_grs_test(
        alphas=large_alphas,
        residual_covariance=cov_eps,
        factor_returns=factor_returns,
        T=T
    )
    assert grs_h1["grs_statistic"] > 5.0
    assert grs_h1["reject_null_5pct"] is True


def test_christoffersen_kupiec_var_backtest_engine():
    """Verify Kupiec and Christoffersen VaR backtesting statistics and likelihood ratio tests."""
    np.random.seed(42)
    T = 1000
    alpha = 0.95
    # Standard normal returns
    losses = np.random.normal(0.0, 1.0, T)
    # Perfect VaR forecast at 95% quantile
    perfect_var = np.full(T, 1.64485)
    
    res_ideal = ChristoffersenKupiecVaRBacktestEngine.run_backtest(
        losses=losses,
        var_forecasts=perfect_var,
        alpha_coverage=alpha
    )
    # Ideal model should not reject unconditional or conditional coverage
    assert res_ideal["reject_uc_5pct"] is False
    assert res_ideal["reject_ind_5pct"] is False
    assert res_ideal["reject_cc_5pct"] is False
    
    # 2. Flawed model with systematic under-coverage (VaR set too low)
    bad_var = np.full(T, 0.50)  # far too many violations
    res_bad = ChristoffersenKupiecVaRBacktestEngine.run_backtest(
        losses=losses,
        var_forecasts=bad_var,
        alpha_coverage=alpha
    )
    assert res_bad["reject_uc_5pct"] is True
    assert res_bad["reject_cc_5pct"] is True
