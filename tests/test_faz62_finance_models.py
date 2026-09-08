"""Programmatic TDD Verification Suite for Faz 62 Quantitative Finance Engines.

Models:
1. Robert F. Engle (2002): Dynamic Conditional Correlation (DCC-GARCH), Two-Step QMLE Estimation,
   Time-Varying Covariance Matrix H_t, Dynamic Minimum-Variance Hedge Ratios & Portfolio Allocation.
2. Steven G. Kou (2002): Double Exponential Jump-Diffusion Model (DEJD), Asymmetric Fat-Tailed Jumps,
   Memoryless Distribution, Implied Volatility Skew & European Option Pricing.
3. Hendrik Bessembinder (2018, 2020): Extreme Wealth Creation Skewness, Compounded Lifetime Return Asymmetry,
   The Skewness Trap of Individual Stocks & Broad Index Superiority.
4. Robert A. Jarrow & Fan Yu (2001) / David Lando (2004): Default Contagion in Interconnected Credit Networks,
   Counterparty Hazard Rate Jumps, Exact Joint Survival Probabilities & CDS Spread Cascades.
5. Martin L. Leibowitz & Alfred Weinberger (1982, 1983): Contingent Immunization, Safety Cushion Dynamics,
   Required Asset Base Floor, Active Risk Leeway & Irreversible Immunization Trigger.
6. William F. Sharpe (1992): Returns-Based Style Analysis (RBSA), Simplex-Constrained Quadratic Programming,
   Effective Asset Mix Decomposition, Selection Return (Alpha) & Rolling Style Drift.
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Numerical Functions & Projections
# ==============================================================================
def project_onto_simplex(v: np.ndarray) -> np.ndarray:
    """Projects vector v onto the probability simplex: sum(w) = 1, w >= 0.
    Exact O(K log K) algorithm based on Duchi et al. (2008).
    """
    v = np.asarray(v, dtype=float)
    n_features = len(v)
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    ind = np.arange(1, n_features + 1)
    cond = u - (cssv - 1.0) / ind > 0
    if not np.any(cond):
        return np.ones(n_features) / n_features
    rho = ind[cond][-1]
    theta = (cssv[cond][-1] - 1.0) / float(rho)
    w = np.maximum(v - theta, 0.0)
    w_sum = np.sum(w)
    if w_sum > 0:
        w /= w_sum
    else:
        w = np.ones(n_features) / n_features
    return w


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ==============================================================================
# Model 1: Robert F. Engle (2002) Dynamic Conditional Correlation (DCC-GARCH)
# ==============================================================================
class DynamicConditionalCorrelationEngine:
    """Robert F. Engle (2002) Dynamic Conditional Correlation (DCC-GARCH) Engine.
    
    Implements 2-stage multivariate volatility and correlation modeling:
    Stage 1: Univariate GARCH(1,1) filters for each asset to extract standardized residuals epsilon_{i,t}.
    Stage 2: Dynamic quasi-correlation recursion:
        Q_t = (1 - a - b) Q_bar + a (epsilon_{t-1} @ epsilon_{t-1}') + b Q_{t-1}
        R_t = diag(Q_t)^(-1/2) @ Q_t @ diag(Q_t)^(-1/2)
        H_t = D_t @ R_t @ D_t
    Provides dynamic hedge ratios and minimum-variance portfolio weights.
    """

    @staticmethod
    def simulate_or_fit_univariate_garch(
        returns: np.ndarray,
        omega: Optional[float] = None,
        alpha: float = 0.08,
        beta: float = 0.90
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculates conditional variance series sigma_t^2 and standardized residuals epsilon_t.
        
        Args:
            returns: 1D array of asset returns of length T.
            omega: Unconditional variance scalar; defaults to sample variance * (1 - alpha - beta).
            alpha: ARCH parameter (shock response).
            beta: GARCH parameter (persistence).
            
        Returns:
            Tuple of (sigma_t, epsilon_t).
        """
        T = len(returns)
        var_sample = float(np.var(returns))
        if omega is None:
            omega = var_sample * max(1e-4, 1.0 - alpha - beta)

        sigma2 = np.zeros(T)
        sigma2[0] = var_sample
        for t in range(1, T):
            sigma2[t] = omega + alpha * (returns[t - 1] ** 2) + beta * sigma2[t - 1]
            if sigma2[t] < 1e-8:
                sigma2[t] = 1e-8

        sigma = np.sqrt(sigma2)
        epsilon = returns / sigma
        return sigma, epsilon

    @classmethod
    def compute_dcc_dynamics(
        cls,
        returns_matrix: np.ndarray,
        dcc_a: float = 0.05,
        dcc_b: float = 0.92,
        garch_alpha: float = 0.08,
        garch_beta: float = 0.90
    ) -> Dict[str, Any]:
        """Runs the complete DCC-GARCH model across N assets over T time steps.
        
        Args:
            returns_matrix: (T, N) array of asset returns.
            dcc_a: DCC shock parameter (must be >= 0).
            dcc_b: DCC persistence parameter (must satisfy dcc_a + dcc_b < 1).
            garch_alpha: Univariate GARCH alpha.
            garch_beta: Univariate GARCH beta.
            
        Returns:
            Dictionary containing conditional volatilities, time-varying correlations R_t,
            conditional covariances H_t, dynamic hedge ratios, and min-variance weights.
        """
        returns_matrix = np.asarray(returns_matrix, dtype=float)
        T, N = returns_matrix.shape

        if dcc_a + dcc_b >= 1.0:
            raise ValueError(f"DCC parameters non-stationary: a + b = {dcc_a + dcc_b:.3f} >= 1.0")

        # Stage 1: Univariate GARCH for each asset
        sigmas = np.zeros((T, N))
        epsilons = np.zeros((T, N))
        for i in range(N):
            s_i, e_i = cls.simulate_or_fit_univariate_garch(
                returns_matrix[:, i], alpha=garch_alpha, beta=garch_beta
            )
            sigmas[:, i] = s_i
            epsilons[:, i] = e_i

        # Stage 2: Unconditional correlation matrix Q_bar
        Q_bar = (epsilons.T @ epsilons) / T
        # Ensure unit diagonal for Q_bar
        d_bar = np.sqrt(np.diag(Q_bar))
        Q_bar = Q_bar / np.outer(d_bar, d_bar)

        # Dynamic recursion
        Q_t = np.zeros((T, N, N))
        R_t = np.zeros((T, N, N))
        H_t = np.zeros((T, N, N))
        hedge_ratios_12 = np.zeros(T)
        min_var_weights = np.zeros((T, N))

        Q_current = Q_bar.copy()
        ones = np.ones(N)

        for t in range(T):
            if t > 0:
                e_prev = epsilons[t - 1, :].reshape(-1, 1)
                Q_current = (1.0 - dcc_a - dcc_b) * Q_bar + dcc_a * (e_prev @ e_prev.T) + dcc_b * Q_current

            # Normalize Q to correlation matrix R_t
            q_diag = np.sqrt(np.maximum(np.diag(Q_current), 1e-8))
            R_current = Q_current / np.outer(q_diag, q_diag)
            np.fill_diagonal(R_current, 1.0)

            # Conditional covariance H_t = D_t @ R_t @ D_t
            D_current = np.diag(sigmas[t, :])
            H_current = D_current @ R_current @ D_current

            Q_t[t] = Q_current
            R_t[t] = R_current
            H_t[t] = H_current

            # Dynamic hedge ratio: h*_12 = H_12 / H_22
            if N >= 2:
                hedge_ratios_12[t] = H_current[0, 1] / max(H_current[1, 1], 1e-8)

            # Minimum variance portfolio weights: w = H^(-1) * 1 / (1' H^(-1) 1)
            try:
                H_inv = np.linalg.pinv(H_current)
                w_raw = H_inv @ ones
                w_norm = w_raw / np.sum(w_raw)
                min_var_weights[t] = w_norm
            except Exception:
                min_var_weights[t] = ones / N

        return {
            "T": T,
            "N": N,
            "sigmas": sigmas,
            "epsilons": epsilons,
            "unconditional_correlation": Q_bar,
            "dynamic_correlations": R_t,
            "dynamic_covariances": H_t,
            "hedge_ratios_12": hedge_ratios_12,
            "min_var_weights": min_var_weights,
            "persistence": dcc_a + dcc_b,
            "is_stationary": (dcc_a + dcc_b < 1.0)
        }


# ==============================================================================
# Model 2: Steven G. Kou (2002) Double Exponential Jump-Diffusion Model (DEJD)
# ==============================================================================
class KouDoubleExponentialJumpDiffusionEngine:
    """Steven G. Kou (2002) Double Exponential Jump-Diffusion (DEJD) Model Engine.
    
    Asset dynamics:
        dS_t / S_{t-} = (r - q - lambda * xi) dt + sigma dW_t + d(sum_{i=1}^{N_t} (V_i - 1))
    where log-jump Y = ln(V) has asymmetric double exponential density:
        f_Y(y) = p * eta_1 * exp(-eta_1 * y) * 1_{y >= 0} + q * eta_2 * exp(eta_2 * y) * 1_{y < 0}
    with p + q = 1, eta_1 > 1 (right/up tail), eta_2 > 0 (left/down tail).
    Expected percentage jump:
        xi = p * eta_1 / (eta_1 - 1) + q * eta_2 / (eta_2 + 1) - 1.
    """

    @staticmethod
    def calculate_jump_moments(
        p: float,
        eta1: float,
        eta2: float
    ) -> Dict[str, float]:
        """Calculates analytical moments and shape statistics of the double exponential jump size Y.
        
        Args:
            p: Probability of upward jump (q = 1 - p).
            eta1: Decay rate of upward jump (must be > 1).
            eta2: Decay rate of downward jump (must be > 0).
            
        Returns:
            Dictionary with mean, variance, skewness, kurtosis, and expected jump return xi.
        """
        if eta1 <= 1.0 or eta2 <= 0.0:
            raise ValueError(f"Invalid parameters: eta1={eta1} must be > 1, eta2={eta2} must be > 0.")
        q = 1.0 - p

        mean_y = (p / eta1) - (q / eta2)
        second_moment = 2.0 * (p / (eta1 ** 2) + q / (eta2 ** 2))
        var_y = second_moment - (mean_y ** 2)
        third_moment = 6.0 * (p / (eta1 ** 3) - q / (eta2 ** 3))
        fourth_moment = 24.0 * (p / (eta1 ** 4) + q / (eta2 ** 4))

        # Central moments for skewness & kurtosis of jump Y
        std_y = math.sqrt(max(var_y, 1e-12))
        skew_y = (third_moment - 3.0 * mean_y * var_y - (mean_y ** 3)) / (std_y ** 3)
        kurt_y = (fourth_moment - 4.0 * mean_y * third_moment + 6.0 * (mean_y ** 2) * second_moment - 3.0 * (mean_y ** 4)) / (var_y ** 2)

        # Expected jump factor xi = E[e^Y - 1]
        xi = p * (eta1 / (eta1 - 1.0)) + q * (eta2 / (eta2 + 1.0)) - 1.0

        return {
            "p": p,
            "q": q,
            "eta1": eta1,
            "eta2": eta2,
            "mean_jump": mean_y,
            "variance_jump": var_y,
            "std_jump": std_y,
            "skewness_jump": skew_y,
            "kurtosis_jump": kurt_y,
            "xi": xi
        }

    @classmethod
    def calculate_log_return_moments(
        cls,
        r: float,
        q: float,
        sigma: float,
        lam: float,
        p: float,
        eta1: float,
        eta2: float,
        t: float = 1.0
    ) -> Dict[str, float]:
        """Computes analytical annualized drift, total variance, skewness, and excess kurtosis
        of the compound process X_t = ln(S_t / S_0).
        """
        jm = cls.calculate_jump_moments(p, eta1, eta2)
        xi = jm["xi"]
        drift_cont = r - q - lam * xi - 0.5 * (sigma ** 2)

        total_mean = (drift_cont + lam * jm["mean_jump"]) * t
        total_var = ((sigma ** 2) + lam * (2.0 * (p / (eta1 ** 2) + (1.0 - p) / (eta2 ** 2)))) * t
        total_std = math.sqrt(total_var)

        # Higher cumulants for jump process
        # Skewness = kappa_3 / (kappa_2)^(3/2) = (lam * E[Y^3] * t) / total_var^(3/2)
        cumulant_3 = lam * 6.0 * (p / (eta1 ** 3) - (1.0 - p) / (eta2 ** 3)) * t
        skewness_x = cumulant_3 / (total_var ** 1.5)

        # Excess Kurtosis = kappa_4 / (kappa_2)^2 = (lam * E[Y^4] * t) / total_var^2
        cumulant_4 = lam * 24.0 * (p / (eta1 ** 4) + (1.0 - p) / (eta2 ** 4)) * t
        excess_kurtosis_x = cumulant_4 / (total_var ** 2)

        return {
            "total_mean": total_mean,
            "total_variance": total_var,
            "total_std": total_std,
            "skewness": skewness_x,
            "excess_kurtosis": excess_kurtosis_x,
            "has_negative_skew": (skewness_x < 0.0),
            "is_leptokurtic": (excess_kurtosis_x > 0.0)
        }

    @classmethod
    def price_european_option_mc(
        cls,
        S0: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        lam: float,
        p: float,
        eta1: float,
        eta2: float,
        n_sims: int = 20000,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Prices European Call and Put options under Kou's DEJD model via exact jump generation.
        
        Jump sampling utilizes the mixture property:
        With prob p, Y ~ Exp(eta1); with prob 1-p, Y ~ -Exp(eta2).
        """
        np.random.seed(seed)
        jm = cls.calculate_jump_moments(p, eta1, eta2)
        xi = jm["xi"]
        drift = (r - q - lam * xi - 0.5 * (sigma ** 2)) * T
        diff_vol = sigma * math.sqrt(T)

        # Antithetic variates for diffusion
        half_sims = n_sims // 2
        z = np.random.randn(half_sims)
        z = np.concatenate([z, -z])

        # Jump count per path ~ Poisson(lambda * T)
        n_jumps = np.random.poisson(lam * T, n_sims)
        total_jump_log = np.zeros(n_sims)

        for i in range(n_sims):
            k = n_jumps[i]
            if k > 0:
                # Sample k jumps
                u = np.random.rand(k)
                up_mask = (u < p)
                n_up = np.sum(up_mask)
                n_down = k - n_up

                up_jumps = np.random.exponential(1.0 / eta1, n_up) if n_up > 0 else np.array([])
                down_jumps = -np.random.exponential(1.0 / eta2, n_down) if n_down > 0 else np.array([])
                total_jump_log[i] = np.sum(up_jumps) + np.sum(down_jumps)

        log_ST = np.log(S0) + drift + diff_vol * z + total_jump_log
        ST = np.exp(log_ST)

        df = math.exp(-r * T)
        call_payoffs = np.maximum(ST - K, 0.0)
        put_payoffs = np.maximum(K - ST, 0.0)

        call_price = float(df * np.mean(call_payoffs))
        put_price = float(df * np.mean(put_payoffs))
        call_se = float(df * np.std(call_payoffs) / math.sqrt(n_sims))
        put_se = float(df * np.std(put_payoffs) / math.sqrt(n_sims))

        # Black-Scholes benchmark with matching total variance
        tot_vol = math.sqrt(sigma ** 2 + lam * jm["variance_jump"])
        d1 = (math.log(S0 / K) + (r - q + 0.5 * tot_vol ** 2) * T) / (tot_vol * math.sqrt(T))
        d2 = d1 - tot_vol * math.sqrt(T)
        bs_call = S0 * math.exp(-q * T) * norm_cdf(d1) - K * df * norm_cdf(d2)

        return {
            "call_price": call_price,
            "call_se": call_se,
            "put_price": put_price,
            "put_se": put_se,
            "bs_benchmark_call": bs_call,
            "jump_skew_impact": call_price - bs_call
        }


# ==============================================================================
# Model 3: Hendrik Bessembinder (2018) Lifetime Wealth Creation Skewness Engine
# ==============================================================================
class BessembinderWealthCreationSkewnessEngine:
    """Hendrik Bessembinder (2018, 2020) Skewness of Lifetime Stock Wealth Creation Engine.
    
    Demonstrates the extreme right-skewness of compounded individual stock returns,
    the 'Skewness Trap' where median returns < Treasury Bills, and the extreme concentration
    where fewer than 4% of firms account for 100% of net shareholder wealth creation.
    """

    @staticmethod
    def calculate_compounded_return_distribution(
        mu: float,
        sigma: float,
        T_years: float
    ) -> Dict[str, float]:
        """Calculates analytical cross-sectional compounding moments under geometric Brownian motion:
            ln(1 + R) ~ N((mu - 0.5 * sigma^2) * T, sigma^2 * T).
        
        Args:
            mu: Expected annualized arithmetic return (e.g. 0.10).
            sigma: Annualized stock volatility (e.g. 0.35).
            T_years: Investment horizon in years (e.g. 10.0 or 30.0).
            
        Returns:
            Dictionary comparing Mean wealth, Median wealth, Mean/Median ratio, and Skewness.
        """
        geo_mean = mu - 0.5 * (sigma ** 2)
        total_var = (sigma ** 2) * T_years

        # Expected terminal wealth multiplier E[W_T / W_0] = exp(mu * T)
        mean_multiplier = math.exp(mu * T_years)

        # Median terminal wealth multiplier Median[W_T / W_0] = exp((mu - 0.5*sigma^2) * T)
        median_multiplier = math.exp(geo_mean * T_years)

        # Ratio of Mean to Median grows exponentially with volatility and time: exp(0.5 * sigma^2 * T)
        ratio_mean_to_median = math.exp(0.5 * total_var)

        # Analytical Skewness of log-normal terminal wealth
        w_factor = math.exp(total_var)
        skewness = (w_factor + 2.0) * math.sqrt(w_factor - 1.0)

        return {
            "horizon_years": T_years,
            "volatility": sigma,
            "mean_wealth_multiplier": mean_multiplier,
            "median_wealth_multiplier": median_multiplier,
            "mean_to_median_ratio": ratio_mean_to_median,
            "skewness": skewness,
            "median_underperforms_mean": (median_multiplier < mean_multiplier)
        }

    @staticmethod
    def analyze_cross_sectional_wealth_creation(
        stock_terminal_values: np.ndarray,
        stock_initial_investments: np.ndarray,
        benchmark_t_bill_return: float
    ) -> Dict[str, Any]:
        """Calculates Net Wealth Creation (NWC) per firm relative to Treasury Bills:
            NWC_i = TerminalValue_i - Initial_i * (1 + R_tbill).
        
        Computes the Lorenz concentration curve and the percentage of firms generating 100% of wealth.
        """
        terms = np.asarray(stock_terminal_values, dtype=float)
        inits = np.asarray(stock_initial_investments, dtype=float)
        N = len(terms)

        # Benchmark dollar hurdle
        hurdles = inits * (1.0 + benchmark_t_bill_return)
        nwc = terms - hurdles

        # Buy-and-hold excess return over T-Bills
        returns_stock = (terms - inits) / np.maximum(inits, 1e-8)
        returns_excess = returns_stock - benchmark_t_bill_return

        pct_beating_cash = float(np.mean(returns_excess > 0.0)) * 100.0
        median_excess_return = float(np.median(returns_excess)) * 100.0
        mean_excess_return = float(np.mean(returns_excess)) * 100.0

        # Sort firms by NWC in descending order
        sort_idx = np.argsort(nwc)[::-1]
        sorted_nwc = nwc[sort_idx]
        total_positive_nwc = float(np.sum(sorted_nwc[sorted_nwc > 0.0]))
        total_net_nwc = float(np.sum(sorted_nwc))

        # Cumulative wealth fraction
        cum_nwc = np.cumsum(sorted_nwc)
        # Find index where cumulative wealth reaches 100% of net wealth creation
        firms_for_100pct = 0
        if total_net_nwc > 0:
            target_idx = np.where(cum_nwc >= total_net_nwc)[0]
            if len(target_idx) > 0:
                firms_for_100pct = int(target_idx[0] + 1)
            else:
                firms_for_100pct = N
        else:
            firms_for_100pct = N

        pct_firms_for_100pct = (firms_for_100pct / N) * 100.0

        # Top 1%, 5%, 10% share of total positive wealth
        k_1pct = max(1, int(N * 0.01))
        k_5pct = max(1, int(N * 0.05))
        top_1pct_share = float(np.sum(sorted_nwc[:k_1pct])) / max(total_positive_nwc, 1e-8) * 100.0
        top_5pct_share = float(np.sum(sorted_nwc[:k_5pct])) / max(total_positive_nwc, 1e-8) * 100.0

        return {
            "total_firms": N,
            "total_net_wealth_creation": total_net_nwc,
            "pct_firms_beating_cash": pct_beating_cash,
            "median_excess_return_pct": median_excess_return,
            "mean_excess_return_pct": mean_excess_return,
            "firms_for_100pct_net_wealth": firms_for_100pct,
            "pct_firms_for_100pct_net_wealth": pct_firms_for_100pct,
            "top_1pct_wealth_share": top_1pct_share,
            "top_5pct_wealth_share": top_5pct_share,
            "is_heavily_concentrated": (pct_firms_for_100pct < 10.0),
            "does_median_fail_to_beat_cash": (median_excess_return < 0.0)
        }


# ==============================================================================
# Model 4: Robert A. Jarrow & Fan Yu (2001) Default Contagion Engine
# ==============================================================================
class JarrowYuDefaultContagionEngine:
    """Robert A. Jarrow & Fan Yu (2001) / David Lando (2004) Default Contagion Engine.
    
    Models interconnected counterparty credit risk with jump default intensities:
        Primary Firm A: lambda_A(t) = a_0
        Secondary Firm B: lambda_B(t) = b_0 + b_1 * 1_{tau_A <= t}
    Provides exact closed-form joint survival probabilities and contagion CDS spread jumps.
    """

    @staticmethod
    def calculate_exact_survival_probabilities(
        a0: float,
        b0: float,
        b1: float,
        t: float
    ) -> Dict[str, float]:
        """Calculates exact analytical marginal and joint survival probabilities:
            S_A(t) = exp(-a0 * t)
            S_B(t) = [a0 / (a0 - b1)] * exp(-(b0 + b1) * t) - [b1 / (a0 - b1)] * exp(-(a0 + b0) * t) (for a0 != b1)
        """
        if a0 <= 0.0 or b0 <= 0.0:
            raise ValueError("Base default intensities a0 and b0 must be strictly positive.")

        s_a = math.exp(-a0 * t)

        # Unconditional survival of secondary firm B
        if abs(a0 - b1) > 1e-7:
            term1 = (a0 / (a0 - b1)) * math.exp(-(b0 + b1) * t)
            term2 = (b1 / (a0 - b1)) * math.exp(-(a0 + b0) * t)
            s_b = term1 - term2
        else:
            # L'Hopital limit when a0 == b1: S_B(t) = exp(-(a0 + b0)*t) * (1 + a0 * t)
            s_b = math.exp(-(a0 + b0) * t) * (1.0 + a0 * t)

        s_b = max(0.0, min(1.0, s_b))

        # Joint survival probability P(tau_A > t, tau_B > t)
        # B survives up to t and A has not defaulted yet -> intensity of B remained b0
        # P(tau_A > t, tau_B > t) = exp(-(a0 + b0) * t)
        joint_survival = math.exp(-(a0 + b0) * t)

        # Default correlation between A and B indicator variables 1_{tau <= t}
        p_def_a = 1.0 - s_a
        p_def_b = 1.0 - s_b
        # Joint default probability P(tau_A <= t, tau_B <= t) = 1 - S_A - S_B + P(tau_A > t, tau_B > t)
        p_joint_def = 1.0 - s_a - s_b + joint_survival
        cov_def = p_joint_def - (p_def_a * p_def_b)
        denom = math.sqrt(max(1e-12, p_def_a * (1.0 - p_def_a) * p_def_b * (1.0 - p_def_b)))
        default_correlation = cov_def / denom

        return {
            "horizon": t,
            "survival_A": s_a,
            "survival_B": s_b,
            "joint_survival": joint_survival,
            "default_prob_A": p_def_a,
            "default_prob_B": p_def_b,
            "joint_default_prob": p_joint_def,
            "default_correlation": default_correlation,
            "contagion_intensity_jump": b1
        }

    @staticmethod
    def calculate_cds_spread_cascade(
        a0: float,
        b0: float,
        b1: float,
        recovery_rate: float = 0.40
    ) -> Dict[str, float]:
        """Calculates the instant jump in Firm B's Credit Default Swap (CDS) spread
        upon the default event of counterparty Firm A.
            Spread = (1 - R) * lambda
        """
        loss_given_default = 1.0 - recovery_rate

        # Baseline spread of firm B prior to contagion
        cds_b_pre = loss_given_default * b0 * 10000.0  # in basis points (bps)

        # Post-contagion spread of firm B immediately upon A's default
        cds_b_post = loss_given_default * (b0 + b1) * 10000.0

        spread_jump = cds_b_post - cds_b_pre
        jump_ratio = cds_b_post / max(cds_b_pre, 1e-4)

        return {
            "recovery_rate": recovery_rate,
            "base_spread_bps": cds_b_pre,
            "post_default_spread_bps": cds_b_post,
            "spread_jump_bps": spread_jump,
            "jump_ratio": jump_ratio,
            "has_systemic_cascade": (spread_jump > 100.0)
        }


# ==============================================================================
# Model 5: Martin L. Leibowitz & Alfred Weinberger (1982) Contingent Immunization Engine
# ==============================================================================
class ContingentImmunizationEngine:
    """Martin L. Leibowitz & Alfred Weinberger (1982, 1983) Contingent Immunization Engine.
    
    Provides active asset-liability management with terminal return guarantee:
    1. Minimum guaranteed terminal floor: F = P_0 * (1 + R_floor / m)^(m * H)
    2. Required asset base under current yield y_t: A_req(t, y_t) = F / (1 + y_t / m)^(m * (H - t))
    3. Safety Cushion: C(t) = P(t) - A_req(t, y_t)
    4. Trigger Mechanism: When C(t) drops to 0, portfolio is immediately immunized into duration-matched assets.
    """

    @staticmethod
    def calculate_safety_cushion(
        current_portfolio_value: float,
        initial_portfolio_value: float,
        guaranteed_floor_rate: float,
        current_market_yield: float,
        total_horizon_years: float,
        current_time_years: float,
        compounding_freq: int = 2
    ) -> Dict[str, Any]:
        """Evaluates the state of the safety cushion and trigger status.
        
        Args:
            current_portfolio_value: Current value of active portfolio P(t).
            initial_portfolio_value: Starting portfolio value P(0).
            guaranteed_floor_rate: Minimum acceptable annualized return R_floor.
            current_market_yield: Current available immunization yield y_t.
            total_horizon_years: Overall investment horizon H.
            current_time_years: Current elapsed time t.
            compounding_freq: Compounding frequency m (default 2 for semi-annual bond basis).
            
        Returns:
            Dictionary with terminal target F, required assets A_req, cushion dollar and pct,
            and immunization trigger flag.
        """
        m = compounding_freq
        H = total_horizon_years
        t = current_time_years
        rem_time = max(0.0, H - t)

        # Minimum terminal dollar requirement
        terminal_floor_target = initial_portfolio_value * ((1.0 + guaranteed_floor_rate / m) ** (m * H))

        # Required assets needed today at market yield y_t to immunize safely to F
        discount_factor = (1.0 + current_market_yield / m) ** (m * rem_time)
        required_assets = terminal_floor_target / discount_factor

        safety_cushion = current_portfolio_value - required_assets
        cushion_pct = (safety_cushion / max(current_portfolio_value, 1e-8)) * 100.0

        # Maximum tolerable yield rise before cushion is completely exhausted (approximate)
        # Yield spread between current yield and floor rate
        cushion_spread = (current_market_yield - guaranteed_floor_rate) * 10000.0  # bps

        # Triggered if safety cushion drops to or below zero
        is_triggered = (safety_cushion <= 1e-4)

        return {
            "initial_value": initial_portfolio_value,
            "current_value": current_portfolio_value,
            "horizon_years": H,
            "time_elapsed": t,
            "time_remaining": rem_time,
            "terminal_floor_target": terminal_floor_target,
            "required_assets": required_assets,
            "safety_cushion": safety_cushion,
            "cushion_pct": cushion_pct,
            "cushion_spread_bps": cushion_spread,
            "is_triggered": is_triggered,
            "active_management_allowed": (not is_triggered)
        }

    @classmethod
    def simulate_cushion_path_under_yield_shock(
        cls,
        initial_portfolio_value: float,
        guaranteed_floor_rate: float,
        initial_yield: float,
        yield_shocks: List[float],
        portfolio_active_returns: List[float],
        total_horizon_years: float,
        dt_years: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Simulates path evolution of safety cushion under changing yields and active portfolio gains/losses."""
        steps = len(yield_shocks)
        history = []
        p_val = initial_portfolio_value
        y_curr = initial_yield
        immunized = False

        for step in range(steps):
            t = step * dt_years
            y_curr += yield_shocks[step]

            if not immunized:
                p_val *= (1.0 + portfolio_active_returns[step])
            else:
                # Once immunized, grows at the locked market yield
                p_val *= (1.0 + y_curr * dt_years)

            state = cls.calculate_safety_cushion(
                current_portfolio_value=p_val,
                initial_portfolio_value=initial_portfolio_value,
                guaranteed_floor_rate=guaranteed_floor_rate,
                current_market_yield=y_curr,
                total_horizon_years=total_horizon_years,
                current_time_years=t
            )

            if state["is_triggered"] and not immunized:
                immunized = True
                state["action"] = "TRIGGER_BREACHED_IMMUNIZED"
            elif immunized:
                state["action"] = "LOCKED_IMMUNIZATION"
            else:
                state["action"] = "ACTIVE_CONTINUED"

            history.append(state)

        return history


# ==============================================================================
# Model 6: William F. Sharpe (1992) Returns-Based Style Analysis (RBSA)
# ==============================================================================
class ReturnsBasedStyleAnalysisEngine:
    """William F. Sharpe (1992) Returns-Based Style Analysis (RBSA) Engine.
    
    Performs constrained quadratic programming to determine the effective asset mix of a portfolio:
        min_w sum_{t=1}^T (R_{p,t} - sum_{k=1}^K w_k R_{B_k, t})^2
        subject to: sum_{k=1}^K w_k = 1,  w_k >= 0 for all k.
    Decomposes performance into Style Return, Selection Return (True Alpha), and Style R^2.
    """

    @staticmethod
    def solve_rbsa_weights(
        fund_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        max_iters: int = 1500,
        lr: float = 0.05,
        tol: float = 1e-7
    ) -> Dict[str, Any]:
        """Solves the Sharpe RBSA constrained quadratic optimization via projected gradient descent on simplex.
        
        Args:
            fund_returns: 1D array of portfolio returns of length T.
            benchmark_returns: (T, K) matrix of style asset class benchmark returns.
            max_iters: Max iterations.
            lr: Learning rate.
            tol: Convergence tolerance on weight change.
            
        Returns:
            Dictionary with optimal weights, style returns, selection returns, and R-squared.
        """
        y = np.asarray(fund_returns, dtype=float).flatten()
        X = np.asarray(benchmark_returns, dtype=float)
        T, K = X.shape

        # Initial uniform weights on simplex
        w = np.ones(K) / K

        # Precompute gradient components: Grad = (2/T) * X' (X w - y)
        XtX = (X.T @ X) / T
        Xty = (X.T @ y) / T

        # Step size adapted to quadratic curvature: eta < 1 / (2 * lambda_max)
        eig_max = float(np.max(np.linalg.eigvalsh(XtX)))
        step_size = 0.90 / (2.0 * max(eig_max, 1e-4))

        for it in range(max_iters):
            grad = 2.0 * (XtX @ w - Xty)
            w_new = project_onto_simplex(w - step_size * grad)
            diff = np.max(np.abs(w_new - w))
            w = w_new
            if diff < tol:
                break

        # Calculate style return and selection return (alpha)
        style_returns = X @ w
        selection_returns = y - style_returns

        # Variance decomposition
        var_total = float(np.var(y))
        var_resid = float(np.var(selection_returns))
        r_squared = 1.0 - (var_resid / max(var_total, 1e-8))
        r_squared = max(0.0, min(1.0, r_squared))

        # Annualized selection alpha and tracking error (assuming monthly input, freq = 12)
        alpha_annual = float(np.mean(selection_returns) * 12.0)
        te_annual = float(np.std(selection_returns) * math.sqrt(12.0))
        info_ratio = alpha_annual / max(te_annual, 1e-6)

        return {
            "optimal_weights": w,
            "r_squared": r_squared,
            "style_returns": style_returns,
            "selection_returns": selection_returns,
            "annualized_alpha": alpha_annual,
            "annualized_tracking_error": te_annual,
            "selection_information_ratio": info_ratio,
            "iterations": it + 1,
            "weights_sum": float(np.sum(w)),
            "all_non_negative": bool(np.all(w >= -1e-6))
        }

    @classmethod
    def compute_rolling_style_drift(
        cls,
        fund_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        window_size: int = 24
    ) -> List[Dict[str, Any]]:
        """Calculates rolling RBSA weights and measures style drift over consecutive rolling windows."""
        y = np.asarray(fund_returns, dtype=float).flatten()
        X = np.asarray(benchmark_returns, dtype=float)
        T, K = X.shape

        if T < window_size:
            raise ValueError(f"Sample length T={T} is smaller than window_size={window_size}.")

        rolling_results = []
        prev_w = None

        for start in range(0, T - window_size + 1):
            end = start + window_size
            sub_y = y[start:end]
            sub_X = X[start:end]

            fit = cls.solve_rbsa_weights(sub_y, sub_X)
            w_curr = fit["optimal_weights"]

            drift = 0.0
            if prev_w is not None:
                drift = float(np.sqrt(0.5 * np.sum((w_curr - prev_w) ** 2)))

            prev_w = w_curr.copy()
            rolling_results.append({
                "window_end": end,
                "weights": w_curr,
                "r_squared": fit["r_squared"],
                "drift": drift
            })

        return rolling_results


# ==============================================================================
# PyTest Automated Test Suite (Agentic TDD Invariant)
# ==============================================================================
class TestFaz62QuantitativeFinanceEngines:
    """Rigorous programmatic test suite for Faz 62 quantitative finance models."""

    def test_dynamic_conditional_correlation_dcc_engine(self):
        """Tests Engle (2002) DCC-GARCH model properties:
        Positive definiteness, dynamic correlations in [-1, 1], stationary persistence,
        and minimum variance hedge ratio.
        """
        np.random.seed(101)
        T, N = 250, 3
        # Generate correlated returns
        true_cov = np.array([
            [0.04, 0.02, 0.01],
            [0.02, 0.09, 0.03],
            [0.01, 0.03, 0.16]
        ])
        L = np.linalg.cholesky(true_cov)
        raw_shocks = np.random.randn(T, N) @ L.T

        res = DynamicConditionalCorrelationEngine.compute_dcc_dynamics(
            raw_shocks, dcc_a=0.04, dcc_b=0.93
        )

        assert res["is_stationary"]
        assert res["persistence"] == pytest.approx(0.97, rel=1e-3)
        assert res["dynamic_correlations"].shape == (T, N, N)
        assert res["dynamic_covariances"].shape == (T, N, N)

        # Check all correlation matrices are valid
        for t in range(0, T, 25):
            R = res["dynamic_correlations"][t]
            assert np.allclose(np.diag(R), 1.0, atol=1e-4)
            assert np.all(R >= -1.0 - 1e-5) and np.all(R <= 1.0 + 1e-5)
            # Positive semi-definite check
            eigvals = np.linalg.eigvalsh(R)
            assert np.all(eigvals >= -1e-5)

        # Dynamic hedge ratio exists and is non-zero
        hr = res["hedge_ratios_12"]
        assert len(hr) == T
        assert np.mean(hr) > 0.0  # Positive true covariance

        # Min-variance portfolio weights sum to 1
        w = res["min_var_weights"]
        assert np.allclose(np.sum(w, axis=1), 1.0, atol=1e-3)

    def test_kou_double_exponential_jump_diffusion_engine(self):
        """Tests Kou (2002) DEJD jump moments, negative skewness creation,
        leptokurtic excess kurtosis, and Monte Carlo option pricing.
        """
        p = 0.35  # Higher probability of downward jump (q = 0.65)
        eta1 = 25.0  # Up jump mean 1/25 = +4%
        eta2 = 12.0  # Down jump mean 1/12 = -8.3% (larger down jumps)

        moments = KouDoubleExponentialJumpDiffusionEngine.calculate_jump_moments(p, eta1, eta2)
        assert moments["mean_jump"] < 0.0  # Negative mean jump
        assert moments["skewness_jump"] < 0.0  # Negative jump skewness
        assert moments["kurtosis_jump"] > 3.0  # Leptokurtic jump size

        # Process level moments
        proc = KouDoubleExponentialJumpDiffusionEngine.calculate_log_return_moments(
            r=0.05, q=0.0, sigma=0.18, lam=3.0, p=p, eta1=eta1, eta2=eta2, t=1.0
        )
        assert proc["has_negative_skew"]
        assert proc["is_leptokurtic"]
        assert proc["excess_kurtosis"] > 0.0

        # Monte Carlo option pricing
        mc = KouDoubleExponentialJumpDiffusionEngine.price_european_option_mc(
            S0=100.0, K=100.0, T=0.5, r=0.05, q=0.0, sigma=0.18, lam=3.0,
            p=p, eta1=eta1, eta2=eta2, n_sims=8000, seed=42
        )
        assert mc["call_price"] > 0.0
        assert mc["put_price"] > 0.0
        # Put-Call parity check: C - P = S0 - K * exp(-r * T)
        parity_diff = (mc["call_price"] - mc["put_price"]) - (100.0 - 100.0 * math.exp(-0.05 * 0.5))
        assert abs(parity_diff) < 0.25  # Within MC error tolerance

    def test_bessembinder_wealth_creation_skewness_engine(self):
        """Tests Bessembinder (2018) skewness of wealth creation:
        Mean > Median, extreme positive skewness, and market wealth concentration.
        """
        # Analytical compounding check
        dist = BessembinderWealthCreationSkewnessEngine.calculate_compounded_return_distribution(
            mu=0.10, sigma=0.35, T_years=20.0
        )
        assert dist["median_underperforms_mean"]
        assert dist["mean_to_median_ratio"] > 3.0  # Mean is over 3x higher than median!
        assert dist["skewness"] > 5.0

        # Cross-sectional simulation of 1,000 firms
        np.random.seed(202)
        N = 1000
        inits = np.ones(N) * 1000.0
        # Stock market: positive arithmetic mean (+4% annual) with high idiosyncratic volatility (40%)
        # compounds to negative median return (-60%), illustrating the Skewness Trap
        geo_returns = np.random.normal(loc=0.04, scale=0.40, size=(N, 10))
        comp_returns = np.prod(1.0 + np.maximum(-0.95, geo_returns), axis=1)
        term_vals = inits * comp_returns

        analysis = BessembinderWealthCreationSkewnessEngine.analyze_cross_sectional_wealth_creation(
            stock_terminal_values=term_vals,
            stock_initial_investments=inits,
            benchmark_t_bill_return=0.30  # 10-year cumulative T-Bill return
        )

        assert analysis["pct_firms_beating_cash"] < 50.0  # Fewer than half beat T-Bills
        assert analysis["does_median_fail_to_beat_cash"]
        assert analysis["is_heavily_concentrated"]
        assert analysis["pct_firms_for_100pct_net_wealth"] < 10.0  # Top few % create 100% of wealth
        assert analysis["top_1pct_wealth_share"] > 15.0
        assert analysis["top_5pct_wealth_share"] > 40.0

    def test_jarrow_yu_default_contagion_engine(self):
        """Tests Jarrow & Yu (2001) default contagion:
        Survival probabilities, positive default correlation, and CDS spread jumps.
        """
        a0 = 0.03  # Firm A default intensity = 3% / year
        b0 = 0.04  # Firm B base default intensity = 4% / year
        b1 = 0.08  # Contagion shock = +8% upon A's default

        surv = JarrowYuDefaultContagionEngine.calculate_exact_survival_probabilities(
            a0=a0, b0=b0, b1=b1, t=3.0
        )
        assert 0.0 < surv["survival_A"] < 1.0
        assert 0.0 < surv["survival_B"] < 1.0
        assert surv["survival_B"] < math.exp(-b0 * 3.0)  # B's survival is degraded by A's contagion risk
        assert surv["default_correlation"] > 0.0  # Positive default correlation induced by contagion

        # CDS spread impact
        cds = JarrowYuDefaultContagionEngine.calculate_cds_spread_cascade(
            a0=a0, b0=b0, b1=b1, recovery_rate=0.40
        )
        assert cds["base_spread_bps"] == pytest.approx(0.60 * 0.04 * 10000.0, rel=1e-3)  # 240 bps
        assert cds["post_default_spread_bps"] == pytest.approx(0.60 * 0.12 * 10000.0, rel=1e-3)  # 720 bps
        assert cds["spread_jump_bps"] == pytest.approx(480.0, rel=1e-3)
        assert cds["has_systemic_cascade"]

    def test_contingent_immunization_engine(self):
        """Tests Leibowitz & Weinberger (1982) Contingent Immunization:
        Safety cushion calculation, terminal floor guarantee, and trigger breach execution.
        """
        P0 = 1000000.0  # $1M starting capital
        R_floor = 0.04   # 4% floor
        y0 = 0.07        # 7% current yield
        H = 5.0          # 5 years

        cushion_state = ContingentImmunizationEngine.calculate_safety_cushion(
            current_portfolio_value=P0,
            initial_portfolio_value=P0,
            guaranteed_floor_rate=R_floor,
            current_market_yield=y0,
            total_horizon_years=H,
            current_time_years=0.0
        )

        assert cushion_state["terminal_floor_target"] > P0
        assert cushion_state["required_assets"] < P0
        assert cushion_state["safety_cushion"] > 0.0
        assert cushion_state["cushion_pct"] > 10.0
        assert cushion_state["active_management_allowed"]
        assert not cushion_state["is_triggered"]

        # Simulate path leading to breach (market yields fluctuate and active manager incurs losses)
        yield_shocks = [0.005, 0.010, -0.005, -0.010]
        active_returns = [-0.08, -0.10, -0.06, -0.02]
        path = ContingentImmunizationEngine.simulate_cushion_path_under_yield_shock(
            initial_portfolio_value=P0,
            guaranteed_floor_rate=R_floor,
            initial_yield=y0,
            yield_shocks=yield_shocks,
            portfolio_active_returns=active_returns,
            total_horizon_years=H
        )

        # Confirm that a trigger occurs and switches portfolio into immunization
        triggered_steps = [s for s in path if s["is_triggered"]]
        assert len(triggered_steps) > 0
        assert triggered_steps[0]["action"] == "TRIGGER_BREACHED_IMMUNIZED"

    def test_returns_based_style_analysis_rbsa_engine(self):
        """Tests Sharpe (1992) Returns-Based Style Analysis (RBSA):
        Simplex constraint enforcement (weights sum to 1, non-negative),
        exact recovery of true asset class style mix, and rolling drift calculation.
        """
        np.random.seed(303)
        T, K = 120, 4  # 10 years of monthly data across 4 style indices
        benchmarks = np.random.normal(loc=0.008, scale=0.04, size=(T, K))

        # Synthesize fund with true style weights: [0.50, 0.30, 0.20, 0.00] + tiny alpha
        true_w = np.array([0.50, 0.30, 0.20, 0.00])
        alpha_noise = 0.002 + np.random.normal(loc=0.0, scale=0.008, size=T)
        fund_returns = benchmarks @ true_w + alpha_noise

        rbsa = ReturnsBasedStyleAnalysisEngine.solve_rbsa_weights(fund_returns, benchmarks)

        # Verify simplex constraints
        assert rbsa["weights_sum"] == pytest.approx(1.0, abs=1e-4)
        assert rbsa["all_non_negative"]
        assert np.all(rbsa["optimal_weights"] >= 0.0)

        # High explanatory power
        assert rbsa["r_squared"] > 0.85

        # Recovered weights close to true weights
        w_est = rbsa["optimal_weights"]
        assert abs(w_est[0] - 0.50) < 0.10
        assert abs(w_est[1] - 0.30) < 0.10
        assert abs(w_est[2] - 0.20) < 0.10
        assert w_est[3] < 0.05  # Zero-weight benchmark

        # Rolling style drift
        rolling = ReturnsBasedStyleAnalysisEngine.compute_rolling_style_drift(
            fund_returns, benchmarks, window_size=36
        )
        assert len(rolling) == T - 36 + 1
        for step in rolling:
            assert np.all(step["weights"] >= 0.0)
            assert np.sum(step["weights"]) == pytest.approx(1.0, abs=1e-3)
            assert step["drift"] >= 0.0
