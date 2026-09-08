"""Programmatic TDD Verification Suite for Faz 50 Quantitative Finance Engines.

Models:
1. R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002) Conditional Value-at-Risk (CVaR) Optimization via Auxiliary Convex Programming & Simplex Projection
2. Dmitry Kramkov & Walter Schachermayer (1999, 2003) General Incomplete Market Utility Maximization, Asymptotic Elasticity & Dual Supermartingale Deflators
3. Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004) Stochastic Mesh Method for High-Dimensional Bermudan & American Option Pricing
4. Mark Broadie, Paul Glasserman & Steven G. Kou (1997) Continuity Correction for Discrete Barrier Options (The Shifted Barrier Theorem)
5. Hans Föllmer & Alexander Schied (2002) Convex & Entropic Risk Measures (Entropic Value-at-Risk / EVaR & Dual Robust Representation)
6. Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce M. Hill (1975) Extreme Value Theory (EVT), Peak-Over-Threshold (POT) & Generalized Pareto Distribution (GPD)
"""

import math
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


def golden_section_search(f, a: float, b: float, tol: float = 1e-6, max_iter: int = 100) -> float:
    """1D minimization using golden section search."""
    invphi = (math.sqrt(5.0) - 1.0) / 2.0
    invphi2 = (3.0 - math.sqrt(5.0)) / 2.0
    (a, b) = (min(a, b), max(a, b))
    h = b - a
    if h <= tol:
        return 0.5 * (a + b)
    n = int(math.ceil(math.log(tol / h) / math.log(invphi)))
    n = min(n, max_iter)
    c = a + invphi2 * h
    d = a + invphi * h
    yc = f(c)
    yd = f(d)
    for _ in range(n):
        if yc < yd:
            b = d
            d = c
            yd = yc
            h = invphi * h
            c = a + invphi2 * h
            yc = f(c)
        else:
            a = c
            c = d
            yc = yd
            h = invphi * h
            d = a + invphi * h
            yd = f(d)
    return 0.5 * (a + b)


def project_simplex(v: np.ndarray) -> np.ndarray:
    """
    Exact projection of vector v onto probability simplex sum(w) = 1, w >= 0.
    Algorithm by Duchi et al. (2008).
    """
    n = len(v)
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    indices = np.arange(1, n + 1)
    cond = u * indices > (cssv - 1.0)
    rho = np.nonzero(cond)[0][-1]
    theta = (cssv[rho] - 1.0) / (rho + 1.0)
    w = np.maximum(v - theta, 0.0)
    return w


# ==============================================================================
# 1. Rockafellar & Uryasev (2000, 2002) CVaR Optimization Engine
# ==============================================================================
class RockafellarUryasevCVaROptimizer:
    """
    R. Tyrrell Rockafellar & Stanislav Uryasev (2000, 2002).
    Optimization of Conditional Value-at-Risk (CVaR / Expected Shortfall).

    Minimizes the auxiliary convex objective:
    F_alpha(w, zeta) = zeta + (1 / ((1 - alpha) * S)) * sum( max(0, -w^T y_s - zeta) )
    Computing optimal portfolio weights w* and Value-at-Risk zeta* simultaneously.
    """
    def __init__(self, confidence_alpha: float = 0.95):
        if not (0.0 < confidence_alpha < 1.0):
            raise ValueError("Confidence alpha must be strictly in (0, 1).")
        self.alpha = confidence_alpha

    def rockafellar_loss_function(self, weights: np.ndarray, zeta: float, return_scenarios: np.ndarray) -> float:
        """
        Evaluates F_alpha(w, zeta) on return scenarios (S x N).
        Loss is L_s = -w^T y_s.
        """
        portfolio_returns = return_scenarios @ weights
        losses = -portfolio_returns
        tail_excess = np.maximum(0.0, losses - zeta)
        s_count = len(losses)
        f_val = zeta + (1.0 / ((1.0 - self.alpha) * s_count)) * np.sum(tail_excess)
        return float(f_val)

    def compute_cvar_and_var(self, weights: np.ndarray, return_scenarios: np.ndarray) -> Dict[str, float]:
        """
        Computes exact empirical VaR and CVaR for given portfolio weights,
        verifying the Rockafellar-Uryasev minimum property.
        """
        portfolio_returns = return_scenarios @ weights
        losses = -portfolio_returns
        var_quantile = float(np.percentile(losses, self.alpha * 100.0))

        # Minimize F_alpha over zeta in neighborhood of empirical VaR
        f_obj = lambda z: self.rockafellar_loss_function(weights, z, return_scenarios)
        zeta_opt = golden_section_search(f_obj, var_quantile - 0.2, var_quantile + 0.2, tol=1e-5)
        cvar_val = self.rockafellar_loss_function(weights, zeta_opt, return_scenarios)

        # Standard tail average expected shortfall
        tail_losses = losses[losses >= var_quantile]
        sample_es = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_quantile

        return {
            "var_alpha": var_quantile,
            "zeta_optimal": zeta_opt,
            "cvar_rockafellar": cvar_val,
            "sample_expected_shortfall": sample_es,
            "rockafellar_duality_gap": abs(cvar_val - sample_es)
        }

    def optimize_portfolio_cvar(
        self,
        return_scenarios: np.ndarray,
        n_iterations: int = 150,
        learning_rate: float = 0.05
    ) -> Dict[str, Any]:
        """
        Projected subgradient descent over the probability simplex to find minimum CVaR weights.
        """
        s_count, n_assets = return_scenarios.shape
        w = np.ones(n_assets) / n_assets

        for _ in range(n_iterations):
            portfolio_returns = return_scenarios @ w
            losses = -portfolio_returns
            zeta = float(np.percentile(losses, self.alpha * 100.0))

            # Subgradient of F_alpha w.r.t w:
            # d/dw F = (1 / ((1 - alpha) * S)) * sum_{s: L_s > zeta} (-y_s)
            indicator = (losses > zeta).astype(float)
            if np.sum(indicator) > 0:
                grad_w = -(1.0 / ((1.0 - self.alpha) * s_count)) * (indicator @ return_scenarios)
            else:
                grad_w = np.zeros(n_assets)

            # Gradient step and projection onto simplex
            w_step = w - learning_rate * grad_w
            w = project_simplex(w_step)

        metrics = self.compute_cvar_and_var(w, return_scenarios)
        mean_ret = float(np.mean(return_scenarios @ w))

        return {
            "optimal_weights": w,
            "optimal_cvar": metrics["cvar_rockafellar"],
            "optimal_var": metrics["var_alpha"],
            "portfolio_expected_return": mean_ret
        }


# ==============================================================================
# 2. Kramkov & Schachermayer (1999, 2003) Utility Maximization & Duality
# ==============================================================================
class KramkovSchachermayerUtilityDuality:
    """
    Dmitry Kramkov & Walter Schachermayer (1999, 2003).
    Duality in Incomplete Financial Markets & Asymptotic Elasticity AE(U) < 1.

    Characterizes existence of optimal wealth X* and martingale deflator Y*.
    """
    def __init__(self, risk_aversion_gamma: float = 2.0, utility_type: str = "power"):
        self.gamma = risk_aversion_gamma
        self.utility_type = utility_type

    def asymptotic_elasticity(self) -> float:
        """
        Computes asymptotic elasticity AE(U) = limsup_{x -> inf} x * U'(x) / U(x).
        Kramkov-Schachermayer Theorem: AE(U) < 1 is necessary and sufficient for optimal wealth existence.
        """
        if self.utility_type == "log" or abs(self.gamma - 1.0) < 1e-6:
            return 0.0
        elif self.utility_type == "power":
            return 1.0 - self.gamma
        else:
            raise NotImplementedError(f"Unknown utility type: {self.utility_type}")

    def check_admissibility() -> bool:
        pass

    def check_admissibility(self) -> bool:
        """Verifies Kramkov-Schachermayer criterion AE(U) < 1."""
        return self.asymptotic_elasticity() < 1.0

    def primal_utility(self, x: float) -> float:
        """Primal utility U(x)."""
        if x <= 0:
            return -float("inf")
        if abs(self.gamma - 1.0) < 1e-6 or self.utility_type == "log":
            return math.log(x)
        return (x ** (1.0 - self.gamma)) / (1.0 - self.gamma)

    def marginal_utility(self, x: float) -> float:
        """U'(x)."""
        if x <= 0:
            return float("inf")
        return x ** (-self.gamma)

    def inverse_marginal(self, y: float) -> float:
        """I(y) = (U')^(-1)(y)."""
        if y <= 0:
            return float("inf")
        return y ** (-1.0 / self.gamma)

    def legendre_fenchel_conjugate(self, y: float) -> float:
        """
        Dual conjugate utility:
        U_tilde(y) = sup_{x > 0} [ U(x) - x * y ] = U(I(y)) - y * I(y)
        """
        if y <= 0:
            return float("inf")
        if abs(self.gamma - 1.0) < 1e-6 or self.utility_type == "log":
            return -math.log(y) - 1.0
        return (self.gamma / (1.0 - self.gamma)) * (y ** ((self.gamma - 1.0) / self.gamma))

    def solve_incomplete_market_duality(
        self,
        initial_wealth_x0: float,
        state_deflators: np.ndarray,
        state_probs: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Solves Kramkov-Schachermayer primal-dual equilibrium across incomplete market states.
        """
        n_states = len(state_deflators)
        probs = state_probs if state_probs is not None else np.ones(n_states) / n_states

        power_term = (self.gamma - 1.0) / self.gamma
        expected_deflator_factor = float(np.sum(probs * (state_deflators ** power_term)))

        y_star = (expected_deflator_factor / initial_wealth_x0) ** self.gamma
        optimal_terminal_wealth = np.array([self.inverse_marginal(y_star * y_k) for y_k in state_deflators])

        budget_expenditure = float(np.sum(probs * state_deflators * optimal_terminal_wealth))
        primal_value = float(np.sum(probs * np.array([self.primal_utility(x) for x in optimal_terminal_wealth])))

        dual_conjugate_exp = float(np.sum(probs * np.array([self.legendre_fenchel_conjugate(y_star * y_k) for y_k in state_deflators])))
        dual_value = dual_conjugate_exp + y_star * initial_wealth_x0

        duality_gap = abs(primal_value - dual_value)

        return {
            "ae_value": self.asymptotic_elasticity(),
            "is_admissible": self.check_admissibility(),
            "optimal_multiplier_y_star": y_star,
            "optimal_terminal_wealth": optimal_terminal_wealth,
            "budget_expenditure": budget_expenditure,
            "primal_value": primal_value,
            "dual_value": dual_value,
            "duality_gap": duality_gap
        }


# ==============================================================================
# 3. Broadie & Glasserman (1996) / Glasserman (2004) Stochastic Mesh Engine
# ==============================================================================
class BroadieGlassermanStochasticMesh:
    """
    Mark Broadie & Paul Glasserman (1996) / Paul Glasserman (2004).
    Stochastic Mesh Method for High-Dimensional Bermudan & American Derivative Pricing.
    """
    def __init__(self, strike: float, risk_free_rate: float, volatility: float):
        self.strike = strike
        self.r = risk_free_rate
        self.sigma = volatility

    def transition_density(self, x: float, y: float, dt: float) -> float:
        """Risk-neutral lognormal transition density g(x, y; dt)."""
        if x <= 0 or y <= 0 or dt <= 0:
            return 0.0
        mu_log = math.log(x) + (self.r - 0.5 * self.sigma**2) * dt
        sigma_log = self.sigma * math.sqrt(dt)
        diff = math.log(y) - mu_log
        dens = (1.0 / (y * sigma_log * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * (diff / sigma_log)**2)
        return float(dens)

    def price_bermudan_put_mesh(
        self,
        spot: float,
        tenor: float,
        n_exercise_dates: int = 4,
        nodes_per_date: int = 120,
        random_seed: int = 42
    ) -> Dict[str, float]:
        """
        Prices a Bermudan put option using the Stochastic Mesh backward recursion.
        """
        np.random.seed(random_seed)
        dt = tenor / n_exercise_dates
        disc = math.exp(-self.r * dt)

        mesh = np.zeros((n_exercise_dates, nodes_per_date))
        current_spots = np.full(nodes_per_date, spot)
        for step in range(n_exercise_dates):
            z = np.random.normal(0, 1, nodes_per_date)
            current_spots = current_spots * np.exp((self.r - 0.5 * self.sigma**2) * dt + self.sigma * math.sqrt(dt) * z)
            mesh[step, :] = current_spots

        values = np.maximum(self.strike - mesh[-1, :], 0.0)

        for step in range(n_exercise_dates - 2, -1, -1):
            x_nodes = mesh[step, :]
            y_nodes = mesh[step + 1, :]

            g_mat = np.zeros((nodes_per_date, nodes_per_date))
            for i in range(nodes_per_date):
                for j in range(nodes_per_date):
                    g_mat[i, j] = self.transition_density(x_nodes[i], y_nodes[j], dt)

            col_sums = np.sum(g_mat, axis=0, keepdims=True)
            col_sums[col_sums == 0] = 1e-12
            weights = g_mat / col_sums

            continuation = disc * (weights @ values)
            exercise_val = np.maximum(self.strike - x_nodes, 0.0)
            values = np.maximum(exercise_val, continuation)

        y_first = mesh[0, :]
        g_0 = np.array([self.transition_density(spot, y, dt) for y in y_first])
        g_sum = np.sum(g_0) if np.sum(g_0) > 0 else 1.0
        weights_0 = g_0 / g_sum
        mesh_put_price = disc * float(np.sum(weights_0 * values))

        d1 = (math.log(spot / self.strike) + (self.r + 0.5 * self.sigma**2) * tenor) / (self.sigma * math.sqrt(tenor))
        d2 = d1 - self.sigma * math.sqrt(tenor)
        euro_put = self.strike * math.exp(-self.r * tenor) * norm_cdf(-d2) - spot * norm_cdf(-d1)

        early_exercise_premium = max(0.0, mesh_put_price - euro_put)

        return {
            "mesh_bermudan_put": mesh_put_price,
            "european_put_benchmark": euro_put,
            "early_exercise_premium": early_exercise_premium,
            "is_early_exercise_positive": mesh_put_price >= euro_put - 1e-4
        }


# ==============================================================================
# 4. Broadie, Glasserman & Kou (1997) Shifted Barrier Continuity Engine
# ==============================================================================
class BroadieGlassermanKouShiftedBarrier:
    """
    Mark Broadie, Paul Glasserman & Steven G. Kou (1997).
    Continuity Correction for Discretely Monitored Barrier Options.

    The Shifted Barrier Theorem:
    H_shifted = H * exp( +- beta * sigma * sqrt(dt) )
    where beta = -zeta(1/2) / sqrt(2*pi) ~= 0.5826.
    """
    BETA_RIEMANN_ZETA: float = 0.582597157938576

    def __init__(self, risk_free_rate: float, volatility: float):
        self.r = risk_free_rate
        self.sigma = volatility

    def compute_shifted_barrier(
        self,
        nominal_barrier: float,
        monitoring_freq_m: int,
        barrier_direction: str = "down"
    ) -> float:
        """
        Calculates the effective continuous shifted barrier H_shifted.
        """
        dt = 1.0 / monitoring_freq_m
        shift_exponent = self.BETA_RIEMANN_ZETA * self.sigma * math.sqrt(dt)

        if barrier_direction.lower() in ["down", "down_and_out", "down_and_in"]:
            h_shifted = nominal_barrier * math.exp(-shift_exponent)
        elif barrier_direction.lower() in ["up", "up_and_out", "up_and_in"]:
            h_shifted = nominal_barrier * math.exp(+shift_exponent)
        else:
            raise ValueError(f"Unknown barrier direction: {barrier_direction}")
        return float(h_shifted)

    def continuous_down_and_out_call(
        self,
        spot: float,
        strike: float,
        barrier: float,
        tenor: float
    ) -> float:
        """
        Exact closed-form Merton / Reiner-Rubinstein continuous Down-and-Out Call (barrier <= strike).
        """
        if spot <= barrier:
            return 0.0

        sig_sqrt_t = self.sigma * math.sqrt(tenor)
        mu = (self.r - 0.5 * self.sigma**2) / (self.sigma**2)
        lam = mu + 1.0

        d1 = (math.log(spot / strike) + (self.r + 0.5 * self.sigma**2) * tenor) / sig_sqrt_t
        d2 = d1 - sig_sqrt_t
        vanilla_call = spot * norm_cdf(d1) - strike * math.exp(-self.r * tenor) * norm_cdf(d2)

        y1 = (math.log(barrier**2 / (spot * strike)) + (self.r + 0.5 * self.sigma**2) * tenor) / sig_sqrt_t
        y2 = y1 - sig_sqrt_t
        barrier_factor = (barrier / spot) ** (2.0 * lam)
        barrier_factor_k = (barrier / spot) ** (2.0 * lam - 2.0)

        di_call = spot * barrier_factor * norm_cdf(y1) - strike * math.exp(-self.r * tenor) * barrier_factor_k * norm_cdf(y2)
        do_call = max(0.0, vanilla_call - di_call)
        return float(do_call)

    def price_discrete_barrier_bgk(
        self,
        spot: float,
        strike: float,
        nominal_barrier: float,
        tenor: float,
        monitoring_freq_m: int
    ) -> Dict[str, float]:
        """
        Prices a discrete barrier option using the BGK Shifted Barrier Correction.
        """
        continuous_price = self.continuous_down_and_out_call(spot, strike, nominal_barrier, tenor)
        shifted_barrier = self.compute_shifted_barrier(nominal_barrier, monitoring_freq_m, barrier_direction="down")
        bgk_discrete_price = self.continuous_down_and_out_call(spot, strike, shifted_barrier, tenor)
        monitoring_bias = bgk_discrete_price - continuous_price

        return {
            "nominal_barrier": nominal_barrier,
            "shifted_barrier": shifted_barrier,
            "continuous_price": continuous_price,
            "bgk_discrete_price": bgk_discrete_price,
            "monitoring_bias": monitoring_bias,
            "relative_bias_pct": (monitoring_bias / continuous_price) * 100.0 if continuous_price > 0 else 0.0
        }


# ==============================================================================
# 5. Föllmer & Schied (2002) Convex & Entropic Risk Measures (EVaR)
# ==============================================================================
class FollmerSchiedEntropicRisk:
    """
    Hans Föllmer & Alexander Schied (2002).
    Convex & Entropic Risk Measures, Dual Representation & Entropic VaR (EVaR).
    """
    def __init__(self, default_gamma: float = 1.0):
        if default_gamma <= 0:
            raise ValueError("Risk aversion parameter gamma must be strictly positive.")
        self.gamma = default_gamma

    def entropic_risk_measure(self, loss_samples: np.ndarray, gamma: Optional[float] = None) -> float:
        """
        Computes closed-form Entropic Risk Measure:
        rho_gamma(L) = (1 / gamma) * ln( E[ exp(gamma * L) ] )
        """
        g = gamma if gamma is not None else self.gamma
        n = len(loss_samples)
        max_val = np.max(g * loss_samples)
        log_exp_sum = max_val + np.log(np.sum(np.exp(g * loss_samples - max_val)) / n)
        return float(log_exp_sum / g)

    def verify_convexity(
        self,
        losses_x: np.ndarray,
        losses_y: np.ndarray,
        lambda_mix: float = 0.5
    ) -> Dict[str, Any]:
        """
        Verifies axiomatic convexity:
        rho( lambda * X + (1 - lambda) * Y ) <= lambda * rho(X) + (1 - lambda) * rho(Y)
        """
        mixed_losses = lambda_mix * losses_x + (1.0 - lambda_mix) * losses_y
        rho_mix = self.entropic_risk_measure(mixed_losses)
        rho_x = self.entropic_risk_measure(losses_x)
        rho_y = self.entropic_risk_measure(losses_y)
        rho_linear_combo = lambda_mix * rho_x + (1.0 - lambda_mix) * rho_y

        convexity_slack = rho_linear_combo - rho_mix
        is_convex = convexity_slack >= -1e-7

        return {
            "rho_mixed": rho_mix,
            "rho_linear_combination": rho_linear_combo,
            "convexity_slack": convexity_slack,
            "is_convex": is_convex
        }

    def verify_limits(self, loss_samples: np.ndarray) -> Dict[str, float]:
        """
        Verifies limiting behavior:
        lim_{gamma -> 0} rho_gamma = E[L] (Risk Neutrality)
        lim_{gamma -> inf} rho_gamma = max(L) (Worst-Case / Essential Supremum)
        """
        mean_loss = float(np.mean(loss_samples))
        max_loss = float(np.max(loss_samples))
        rho_near_zero = self.entropic_risk_measure(loss_samples, gamma=1e-4)
        rho_large = self.entropic_risk_measure(loss_samples, gamma=20.0)

        return {
            "empirical_mean": mean_loss,
            "rho_limit_zero": rho_near_zero,
            "empirical_max": max_loss,
            "rho_limit_large": rho_large,
            "error_to_mean": abs(rho_near_zero - mean_loss)
        }

    def compute_evar(self, loss_samples: np.ndarray, alpha: float = 0.95) -> Dict[str, float]:
        """
        Ahmadi-Javid (2012) Entropic Value-at-Risk (EVaR):
        EVaR_alpha(L) = inf_{z > 0} (1 / z) * [ ln( E[ exp(z * L) ] ) - ln(1 - alpha) ]
        """
        n = len(loss_samples)

        def evar_obj(z: float) -> float:
            if z <= 1e-6:
                return float("inf")
            max_val = np.max(z * loss_samples)
            ln_mgf = max_val + np.log(np.sum(np.exp(z * loss_samples - max_val)) / n)
            val = (ln_mgf - math.log(1.0 - alpha)) / z
            return float(val)

        z_opt = golden_section_search(evar_obj, 0.01, 10.0, tol=1e-5)
        evar_val = evar_obj(z_opt)

        var_val = float(np.percentile(loss_samples, alpha * 100.0))
        cvar_val = float(np.mean(loss_samples[loss_samples >= var_val]))

        return {
            "var_alpha": var_val,
            "cvar_alpha": cvar_val,
            "evar_alpha": evar_val,
            "optimal_z": z_opt,
            "is_bounding_hierarchy_valid": (var_val <= cvar_val + 1e-5) and (cvar_val <= evar_val + 1e-5)
        }


# ==============================================================================
# 6. Embrechts, Klüppelberg & Mikosch (1997) / Hill (1975) EVT GPD Engine
# ==============================================================================
class EmbrechtsMikoschHillGPD:
    """
    Paul Embrechts, Claudia Klüppelberg & Thomas Mikosch (1997) / Bruce M. Hill (1975).
    Extreme Value Theory (EVT), Peak-Over-Threshold (POT) & Generalized Pareto Distribution (GPD).
    """
    def __init__(self):
        pass

    def hill_estimator(self, losses: np.ndarray, k_tail_order_stats: int) -> Dict[str, float]:
        """
        Calculates the Hill (1975) estimator of the tail index alpha = 1 / xi.
        """
        sorted_losses = np.sort(losses)
        n = len(sorted_losses)
        if k_tail_order_stats >= n or k_tail_order_stats < 2:
            raise ValueError(f"k must be in [2, n-1]. Given k={k_tail_order_stats}, n={n}")

        threshold_val = sorted_losses[n - k_tail_order_stats - 1]
        tail_slice = sorted_losses[n - k_tail_order_stats:]

        if threshold_val <= 0:
            shift = abs(threshold_val) + 1.0
            tail_slice = tail_slice + shift
            threshold_val = threshold_val + shift

        log_ratios = np.log(tail_slice) - math.log(threshold_val)
        xi_hill = float(np.mean(log_ratios))
        tail_index_alpha = 1.0 / xi_hill if xi_hill > 0 else float("inf")

        return {
            "xi_shape_hill": xi_hill,
            "tail_index_alpha": tail_index_alpha,
            "tail_cutoff_threshold": float(threshold_val),
            "is_heavy_tailed": xi_hill > 0.0
        }

    def fit_gpd_probability_weighted_moments(self, excesses: np.ndarray) -> Tuple[float, float]:
        """
        Fits Generalized Pareto Distribution GPD(xi, beta) using Hosking & Wallis (1987) PWM.
        """
        y = np.sort(excesses)
        m = len(y)
        a0 = float(np.mean(y))
        weights = (1.0 - (np.arange(1, m + 1) - 0.35) / m)
        a1 = float(np.mean(weights * y))

        denom = a0 - 2.0 * a1
        if abs(denom) < 1e-8:
            denom = 1e-8
        xi = 2.0 - a0 / denom
        beta = (2.0 * a0 * a1) / denom

        xi = max(-0.5, min(0.95, xi))
        beta = max(1e-4, beta)
        return float(xi), float(beta)

    def extreme_tail_var_and_es(
        self,
        losses: np.ndarray,
        threshold_u: float,
        confidence_p: float = 0.999
    ) -> Dict[str, float]:
        """
        Balkema-de Haan-Pickands analytic VaR and Expected Shortfall under GPD.
        """
        n = len(losses)
        excesses = losses[losses > threshold_u] - threshold_u
        n_u = len(excesses)
        if n_u < 10:
            raise ValueError(f"Insufficient exceedances (n_u={n_u}) above threshold {threshold_u}")

        xi, beta = self.fit_gpd_probability_weighted_moments(excesses)

        tail_prob_ratio = (n / n_u) * (1.0 - confidence_p)
        if tail_prob_ratio <= 0:
            tail_prob_ratio = 1e-12
        var_gpd = threshold_u + (beta / xi) * ((tail_prob_ratio ** (-xi)) - 1.0)

        if xi < 1.0:
            es_gpd = (var_gpd / (1.0 - xi)) + (beta - xi * threshold_u) / (1.0 - xi)
        else:
            es_gpd = float("inf")

        mu = float(np.mean(losses))
        sigma = float(np.std(losses))
        # z score for 99.9% is ~3.0902
        z_score = 3.09023
        gaussian_var = mu + z_score * sigma

        return {
            "threshold_u": threshold_u,
            "n_exceedances": n_u,
            "gpd_xi_shape": xi,
            "gpd_beta_scale": beta,
            "evt_var_999": float(var_gpd),
            "evt_es_999": float(es_gpd),
            "gaussian_var_benchmark": float(gaussian_var),
            "tail_underestimation_ratio": float(var_gpd / gaussian_var) if gaussian_var > 0 else 1.0
        }


# ==============================================================================
# Pytest Verification Suite
# ==============================================================================
def test_rockafellar_uryasev_cvar_optimization():
    """Verify Rockafellar & Uryasev (2000, 2002) CVaR convex optimization."""
    optimizer = RockafellarUryasevCVaROptimizer(confidence_alpha=0.95)

    np.random.seed(42)
    scenarios = np.random.normal(0.001, 0.02, (2000, 3))
    crash_idx = np.random.choice(2000, 40, replace=False)
    scenarios[crash_idx, 2] -= 0.10

    weights = np.array([0.3, 0.3, 0.4])
    metrics = optimizer.compute_cvar_and_var(weights, scenarios)

    assert metrics["cvar_rockafellar"] > metrics["var_alpha"], "CVaR must strictly dominate VaR"
    assert metrics["rockafellar_duality_gap"] < 0.005, "Rockafellar loss must match empirical Expected Shortfall"

    opt_res = optimizer.optimize_portfolio_cvar(scenarios, n_iterations=100)
    opt_w = opt_res["optimal_weights"]
    assert np.isclose(np.sum(opt_w), 1.0, atol=1e-5), "Optimal weights must sum to 1"
    assert np.all(opt_w >= -1e-6), "No short selling constraint"
    assert opt_w[2] < opt_w[0], "Optimizer must penalize heavy crash-risk asset 3"
    assert opt_res["optimal_cvar"] < metrics["cvar_rockafellar"], "Optimized CVaR must be lower than naive weights"


def test_kramkov_schachermayer_utility_duality():
    """Verify Kramkov & Schachermayer (1999, 2003) utility duality & asymptotic elasticity."""
    engine = KramkovSchachermayerUtilityDuality(risk_aversion_gamma=2.5, utility_type="power")

    ae = engine.asymptotic_elasticity()
    assert ae == -1.5, f"AE for gamma=2.5 must be 1 - 2.5 = -1.5"
    assert engine.check_admissibility() is True, "Must satisfy Kramkov-Schachermayer criterion AE(U) < 1"

    x0 = 100.0
    deflators = np.array([0.7, 0.9, 1.1, 1.4])
    probs = np.array([0.25, 0.25, 0.25, 0.25])

    sol = engine.solve_incomplete_market_duality(x0, deflators, probs)
    assert sol["is_admissible"] is True
    assert np.isclose(sol["budget_expenditure"], x0, atol=1e-6), "Optimal terminal wealth must satisfy budget constraint"
    assert sol["duality_gap"] < 1e-5, f"Primal-dual gap must vanish in convex duality: {sol['duality_gap']}"
    assert sol["optimal_terminal_wealth"][0] > sol["optimal_terminal_wealth"][-1]


def test_broadie_glasserman_stochastic_mesh():
    """Verify Broadie & Glasserman (1996) Stochastic Mesh Bermudan option engine."""
    mesh_engine = BroadieGlassermanStochasticMesh(strike=100.0, risk_free_rate=0.05, volatility=0.20)

    dens = mesh_engine.transition_density(100.0, 105.0, 0.25)
    assert dens > 0.0

    spot = 95.0
    res = mesh_engine.price_bermudan_put_mesh(
        spot=spot,
        tenor=1.0,
        n_exercise_dates=4,
        nodes_per_date=100,
        random_seed=123
    )

    assert res["mesh_bermudan_put"] > 5.0, "Put price must exceed immediate exercise value"
    assert res["is_early_exercise_positive"] is True, "Bermudan put price must equal or exceed European put"
    assert res["mesh_bermudan_put"] >= res["european_put_benchmark"] - 1e-4


def test_broadie_glasserman_kou_shifted_barrier():
    """Verify Broadie, Glasserman & Kou (1997) Shifted Barrier Continuity Theorem."""
    engine = BroadieGlassermanKouShiftedBarrier(risk_free_rate=0.04, volatility=0.25)

    spot = 100.0
    strike = 100.0
    barrier = 85.0
    tenor = 0.5
    m_freq = 52

    res = engine.price_discrete_barrier_bgk(spot, strike, barrier, tenor, monitoring_freq_m=m_freq)

    assert res["shifted_barrier"] < barrier, "Down barrier must be shifted downward"
    assert abs(res["shifted_barrier"] - 85.0 * math.exp(-0.582597 * 0.25 * math.sqrt(1.0/52.0))) < 1e-3
    assert res["monitoring_bias"] > 0.0, "Discrete monitoring must produce higher Down-and-Out value"
    assert res["bgk_discrete_price"] > res["continuous_price"]
    assert res["relative_bias_pct"] > 0.5, "Monitoring bias is non-negligible"


def test_follmer_schied_entropic_evar():
    """Verify Föllmer & Schied (2002) Convex & Entropic Risk and EVaR bounding hierarchy."""
    engine = FollmerSchiedEntropicRisk(default_gamma=1.5)

    np.random.seed(42)
    losses_x = np.random.normal(2.0, 5.0, 1500)
    losses_y = np.random.exponential(4.0, 1500)

    convexity_res = engine.verify_convexity(losses_x, losses_y, lambda_mix=0.4)
    assert convexity_res["is_convex"] is True, "Convex risk measure must satisfy rho(l*X + (1-l)*Y) <= l*rho(X) + (1-l)*rho(Y)"
    assert convexity_res["convexity_slack"] >= -1e-7

    limits = engine.verify_limits(losses_x)
    assert limits["error_to_mean"] < 0.05, "lim_{gamma->0} rho_gamma must converge to E[L]"
    assert limits["rho_limit_large"] > limits["empirical_mean"], "High gamma penalizes tail risk severely"

    evar_res = engine.compute_evar(losses_y, alpha=0.95)
    assert evar_res["is_bounding_hierarchy_valid"] is True, "Must satisfy fundamental theorem VaR <= CVaR <= EVaR"
    assert evar_res["var_alpha"] <= evar_res["cvar_alpha"] + 1e-5
    assert evar_res["cvar_alpha"] <= evar_res["evar_alpha"] + 1e-5


def test_embrechts_mikosch_hill_gpd_evt():
    """Verify Embrechts, Klüppelberg & Mikosch (1997) & Hill (1975) EVT & GPD deep tail risk."""
    engine = EmbrechtsMikoschHillGPD()

    np.random.seed(789)
    df = 3.0
    t_samples = np.random.standard_t(df, size=3000)
    losses = np.maximum(0.0, t_samples * 2.0 + 1.0)

    k_tail = 150
    hill_res = engine.hill_estimator(losses, k_tail_order_stats=k_tail)
    assert hill_res["is_heavy_tailed"] is True, "Student-t(3) must be detected as heavy-tailed (xi > 0)"
    assert 0.15 < hill_res["xi_shape_hill"] < 0.65, f"Hill xi estimate expected near 0.33, got {hill_res['xi_shape_hill']}"

    threshold = float(np.percentile(losses, 92.0))
    evt_res = engine.extreme_tail_var_and_es(losses, threshold_u=threshold, confidence_p=0.999)

    assert evt_res["evt_var_999"] > threshold, "Extreme VaR must exceed threshold"
    assert evt_res["evt_es_999"] > evt_res["evt_var_999"], "Expected Shortfall must exceed VaR"
    assert evt_res["tail_underestimation_ratio"] > 1.1, "Gaussian VaR must severely underestimate heavy-tail black swan risk"
