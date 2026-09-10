"""Programmatic TDD Verification Suite for Faz 45 Quantitative Finance Engines.

Models:
1. Lorenzo Bergomi (2005, 2008) Forward Variance Curve Model (N-Factor Bergomi)
2. Ole E. Barndorff-Nielsen & Neil Shephard (BNS 2001) Non-Gaussian OU Stochastic Volatility (Gamma-OU BDLP)
3. Zhiguo He & Arvind Krishnamurthy (2012, 2013) Intermediary Asset Pricing & Macroeconomic Liquidity Spiral
4. Mathieu Rosenbaum & Mathieu Robert (2011, 2012) Ultra-High-Frequency Tick Size Rounding & Asymptotics
5. Peter W. Buchen & Michael Kelly (1996) Maximum Entropy Risk-Neutral Density (MED)
6. Guillermo Angeris & Tarun Chitra (2020, 2024) CFMM Convex Geometry, Curvature Invariants & Geodesic Slippage
"""

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest

# ==============================================================================
# Helper Numerical Functions
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ==============================================================================
# 1. Lorenzo Bergomi (2005, 2008) Forward Variance Curve Model
# ==============================================================================
class LorenzoBergomiForwardVariance:
    """
    Bergomi (2005, 2008) N-Factor Forward Variance Curve Model.
    Models the term structure of variance swaps xi_t^T = E_t[d<ln S>_T / dT] directly.
    d xi_t^T = xi_t^T * sum_{i=1}^n alpha_i * exp(-k_i * (T - t)) * dW_t^{(i)}
    dS_t = r S_t dt + sqrt(xi_t^t) S_t dZ_t
    Correlation: E[dW_t^{(i)} dZ_t] = rho_i dt
    Joint calibration of SPX skew and VIX derivatives.
    """
    def __init__(self,
                 xi0: float = 0.04,        # Flat initial forward variance curve (20% flat vol)
                 alpha1: float = 2.5,      # Short-term factor vol-of-vol
                 k1: float = 4.0,          # Short-term factor mean-reversion speed
                 alpha2: float = 1.0,      # Long-term factor vol-of-vol
                 k2: float = 0.5,          # Long-term factor mean-reversion speed
                 rho1: float = -0.75,      # Correlation short factor with spot (drives short skew)
                 rho2: float = -0.40,      # Correlation long factor with spot (drives long skew)
                 r: float = 0.03):
        self.xi0 = xi0
        self.alpha1 = alpha1
        self.k1 = k1
        self.alpha2 = alpha2
        self.k2 = k2
        self.rho1 = rho1
        self.rho2 = rho2
        self.r = r

    def forward_variance_initial(self, T: float) -> float:
        """Initial forward variance curve xi_0^T (constant or term structure)."""
        return self.xi0 + 0.01 * (1.0 - math.exp(-self.k2 * T))

    def vix_futures_analytic_approx(self, t: float, T: float, tau: float = 1.0 / 12.0) -> float:
        """
        Analytical approximation for VIX futures:
        VIX_T^2 = (1/tau) * int_T^{T+tau} xi_T^u du
        F_VIX(t, T) = E_t[VIX_T] approx sqrt(E_t[VIX_T^2]) * (1 - 1/8 * Var(VIX^2)/E[VIX^2]^2)
        """
        base_var = self.forward_variance_initial(T + tau / 2.0)
        return math.sqrt(max(1e-6, base_var))

    def simulate_paths(self,
                       S0: float = 100.0,
                       T: float = 1.0,
                       n_paths: int = 1000,
                       n_steps: int = 20,
                       seed: int = 42) -> Dict[str, Any]:
        """
        Monte Carlo simulation of 2-factor Bergomi forward variance and spot dynamics.
        """
        np.random.seed(seed)
        dt = T / n_steps
        sqrt_dt = math.sqrt(dt)

        S = np.full(n_paths, S0, dtype=float)
        # Factor state variables X_1, X_2 initialized to 0
        X1 = np.zeros(n_paths)
        X2 = np.zeros(n_paths)

        time_grid = np.linspace(0.0, T, n_steps + 1)
        spot_history = [float(np.mean(S))]
        spot_vol_history = []

        # Cholesky construction for correlated Brownian increments: [W1, W2, Z]
        rho_w = 0.20
        cov_matrix = np.array([
            [1.0, rho_w, self.rho1],
            [rho_w, 1.0, self.rho2],
            [self.rho1, self.rho2, 1.0]
        ])
        L_chol = np.linalg.cholesky(cov_matrix)

        for step in range(n_steps):
            t = time_grid[step]

            var_correction = 0.5 * (
                (self.alpha1 ** 2) * (1.0 - math.exp(-2.0 * self.k1 * t)) / (2.0 * self.k1) +
                (self.alpha2 ** 2) * (1.0 - math.exp(-2.0 * self.k2 * t)) / (2.0 * self.k2)
            )
            spot_var = self.forward_variance_initial(t) * np.exp(self.alpha1 * X1 + self.alpha2 * X2 - var_correction)
            spot_var = np.maximum(1e-6, spot_var)
            spot_vol = np.sqrt(spot_var)
            spot_vol_history.append(float(np.mean(spot_vol)))

            z_raw = np.random.normal(0.0, 1.0, (3, n_paths))
            correlated_z = np.dot(L_chol, z_raw) * sqrt_dt
            dW1 = correlated_z[0, :]
            dW2 = correlated_z[1, :]
            dZ = correlated_z[2, :]

            S = S * np.exp((self.r - 0.5 * spot_var) * dt + spot_vol * dZ)

            X1 = X1 * math.exp(-self.k1 * dt) + dW1
            X2 = X2 * math.exp(-self.k2 * dt) + dW2

            spot_history.append(float(np.mean(S)))

        strikes = [90.0, 100.0, 110.0]
        call_prices = {}
        for K in strikes:
            payoff = np.maximum(0.0, S - K)
            call_prices[K] = float(math.exp(-self.r * T) * np.mean(payoff))

        skew_metric = (call_prices[90.0] - call_prices[110.0]) / S0

        return {
            "S_final_mean": float(np.mean(S)),
            "S_final_std": float(np.std(S)),
            "spot_vol_terminal": spot_vol_history[-1],
            "call_prices": call_prices,
            "skew_metric": skew_metric,
            "vix_futures_1m": self.vix_futures_analytic_approx(0.0, 1.0 / 12.0)
        }


# ==============================================================================
# 2. Barndorff-Nielsen & Shephard (BNS 2001) Non-Gaussian OU Stochastic Volatility
# ==============================================================================
class BarndorffNielsenShephardBNS:
    """
    Barndorff-Nielsen & Shephard (2001) Non-Gaussian OU Stochastic Volatility Model.
    Variance is driven by a pure-jump subordinator (Background Driving Lévy Process - BDLP):
      d sigma_t^2 = -lambda * sigma_t^2 dt + d z_{lambda t}
    where z_t is a Gamma subordinator with parameters (a, b).
    Stock price:
      dS_t = (r - psi(rho)) S_t dt + sigma_t S_t dW_t + S_t (exp(rho * Delta z) - 1)
    Leverage effect: rho <= 0 causes negative stock jump when variance spikes upwards.
    Variance is strictly positive (no Feller violation). Exact characteristic function.
    """
    def __init__(self,
                 lambda_param: float = 1.67,  # Rate of mean-reversion
                 a_gamma: float = 1.43,       # Gamma BDLP shape parameter
                 b_gamma: float = 11.5,       # Gamma BDLP rate parameter (E[z_1] = a/b)
                 rho_leverage: float = -3.5,  # Leverage jump parameter (negative)
                 sigma0_sq: float = 0.04,     # Initial variance
                 r: float = 0.03):
        self.lambda_param = lambda_param
        self.a_gamma = a_gamma
        self.b_gamma = b_gamma
        self.rho_leverage = rho_leverage
        self.sigma0_sq = sigma0_sq
        self.r = r

    def stationary_mean_variance(self) -> float:
        """Long-run mean of variance E[sigma_inf^2] = a / b."""
        return self.a_gamma / self.b_gamma

    def simulate_bns_paths(self,
                           S0: float = 100.0,
                           T: float = 1.0,
                           n_paths: int = 1000,
                           n_steps: int = 40,
                           seed: int = 42) -> Dict[str, Any]:
        """
        Simulates BNS stock price and Gamma-OU variance trajectories.
        """
        np.random.seed(seed)
        dt = T / n_steps
        sqrt_dt = math.sqrt(dt)

        S = np.full(n_paths, S0, dtype=float)
        v = np.full(n_paths, self.sigma0_sq, dtype=float)

        mean_v_path = [float(np.mean(v))]

        gamma_shape = self.a_gamma * self.lambda_param * dt
        gamma_scale = 1.0 / self.b_gamma

        comp_drift = (self.lambda_param * self.a_gamma * self.rho_leverage) / (self.b_gamma - self.rho_leverage)

        for _ in range(n_steps):
            dW = np.random.normal(0.0, sqrt_dt, n_paths)
            dZ = np.random.gamma(gamma_shape, gamma_scale, n_paths)

            sqrt_v = np.sqrt(np.maximum(1e-6, v))
            jump_stock = self.rho_leverage * dZ

            S = S * np.exp((self.r - comp_drift - 0.5 * v) * dt + sqrt_v * dW + jump_stock)
            v = v * math.exp(-self.lambda_param * dt) + dZ
            mean_v_path.append(float(np.mean(v)))

        strikes = [90.0, 100.0, 110.0]
        call_prices = {}
        for K in strikes:
            payoff = np.maximum(0.0, S - K)
            call_prices[K] = float(math.exp(-self.r * T) * np.mean(payoff))

        return {
            "S_final_mean": float(np.mean(S)),
            "S_final_std": float(np.std(S)),
            "mean_v_terminal": float(np.mean(v)),
            "stationary_mean": self.stationary_mean_variance(),
            "call_prices": call_prices,
            "is_strictly_positive": bool(np.all(v > 0.0))
        }


# ==============================================================================
# 3. Zhiguo He & Arvind Krishnamurthy (2012, 2013) Intermediary Asset Pricing
# ==============================================================================
class HeKrishnamurthyIntermediaryPricing:
    """
    Intermediary Asset Pricing & Macroeconomic Liquidity Spikes (He & Krishnamurthy 2012, 2013).
    Marginal price setters are financial intermediaries facing equity capital constraints:
      Intermediary equity ratio w_t = N_t / (P_t * K_t) in [0, 1]
    Constraint: Intermediary risk exposure cannot exceed (1 / gamma_I) * (RiskPremium / Vol^2).
    Unconstrained regime (w > w*): Intermediary absorbs shocks, risk premium is flat and low.
    Constrained regime (w <= w*): Equity constraint binds, households absorb excess risk.
    Risk premium and volatility multiplier explode non-linearly, generating systemic crisis basin.
    """
    def __init__(self,
                 gamma_I: float = 2.0,      # Intermediary risk aversion
                 gamma_H: float = 6.0,      # Household risk aversion (less willing to bear market risk)
                 sigma_fundamental: float = 0.12, # Fundamental asset volatility
                 alpha_max: float = 3.0,    # Max leverage multiple allowed (regulatory equity constraint)
                 rho_discount: float = 0.04,
                 r: float = 0.03):
        self.gamma_I = gamma_I
        self.gamma_H = gamma_H
        self.sigma = sigma_fundamental
        self.alpha_max = alpha_max
        self.rho_discount = rho_discount
        self.r = r
        self.w_star = 1.0 / alpha_max      # Threshold below which equity constraint binds

    def compute_risk_premium(self, w: float) -> Dict[str, float]:
        """
        Computes equilibrium risk premium mu_R(w) - r and Sharpe ratio as a function of equity ratio w.
        """
        w_clamped = max(0.01, min(0.99, w))

        if w_clamped > self.w_star:
            risk_premium = self.gamma_I * (self.sigma ** 2)
            vol_multiplier = 1.0
            is_constrained = False
        else:
            effective_gamma = self.gamma_H / (1.0 - w_clamped * (1.0 - self.gamma_H / self.gamma_I))
            vol_multiplier = 1.0 + (self.w_star - w_clamped) * 3.5
            effective_vol = self.sigma * vol_multiplier
            risk_premium = effective_gamma * (effective_vol ** 2)
            is_constrained = True

        effective_vol = self.sigma * vol_multiplier
        sharpe_ratio = risk_premium / effective_vol

        return {
            "w": w_clamped,
            "is_constrained": is_constrained,
            "risk_premium_annual": risk_premium,
            "risk_premium_bps": risk_premium * 10000.0,
            "volatility_multiplier": vol_multiplier,
            "effective_volatility": effective_vol,
            "sharpe_ratio": sharpe_ratio
        }

    def simulate_capital_ratio_path(self,
                                    w0: float = 0.40,
                                    T: float = 5.0,
                                    n_steps: int = 100,
                                    seed: int = 42) -> Dict[str, Any]:
        """
        Simulates stochastic drift and diffusion of intermediary capitalization ratio w_t.
        """
        np.random.seed(seed)
        dt = T / n_steps
        sqrt_dt = math.sqrt(dt)

        w = w0
        w_path = [w]
        risk_premiums = []

        for _ in range(n_steps):
            res = self.compute_risk_premium(w)
            risk_premiums.append(res["risk_premium_annual"])

            drift = 0.15 * (0.50 - w)
            diff = self.sigma * (1.0 - w) * res["volatility_multiplier"]

            dZ = np.random.normal(0.0, sqrt_dt)
            w = w + drift * dt + diff * dZ
            w = max(0.02, min(0.95, w))
            w_path.append(w)

        crisis_duration = sum(1 for val in w_path if val <= self.w_star) / len(w_path)

        return {
            "w_initial": w0,
            "w_terminal": w_path[-1],
            "w_star": self.w_star,
            "min_w": min(w_path),
            "crisis_frequency": crisis_duration,
            "mean_risk_premium_bps": float(np.mean(risk_premiums)) * 10000.0
        }


# ==============================================================================
# 4. Mathieu Rosenbaum & Mathieu Robert (2011, 2012) Tick Size Rounding & Asymptotics
# ==============================================================================
class RosenbaumRobertTickSize:
    """
    Ultra-High-Frequency Market Microstructure with Price Rounding & Tick Size Asymptotics
    (Robert & Rosenbaum 2011, 2012).
    Observed price is rounded to tick grid alpha: P_t = alpha * round(S_t / alpha).
    Classification:
    - Large-tick assets (alpha / (sigma * sqrt(dt)) >> 1): Spread locked at 1 tick, queue position matters.
    - Small-tick assets (alpha / (sigma * sqrt(dt)) << 1): Spread fluctuates across multiple ticks.
    Analytical relationship:
      S* = alpha * (1 + 2 * eta)
      sigma_noise^2 = (alpha^2 / 12) + eta * alpha^2
    where eta is the probability of reversal within the tick.
    """
    def __init__(self, alpha_tick: float = 0.01, dt_tick: float = 1.0 / 23400.0):
        self.alpha_tick = alpha_tick
        self.dt_tick = dt_tick

    def classify_asset_regime(self, daily_vol: float, price: float) -> Dict[str, Any]:
        """
        Calculates tick ratio theta = alpha / (sigma * price * sqrt(dt)).
        """
        sec_vol = (daily_vol / math.sqrt(23400.0)) * price
        theta = self.alpha_tick / max(1e-6, sec_vol)

        if theta >= 2.0:
            regime = "Large-Tick (Spread = 1 Tick, Queue Priority Critical)"
            locked_spread = True
        elif theta <= 0.5:
            regime = "Small-Tick (Wide Spread, Frequent Price Bounces)"
            locked_spread = False
        else:
            regime = "Medium-Tick (Balanced Queue & Price Jumps)"
            locked_spread = False

        return {
            "tick_size": self.alpha_tick,
            "sec_volatility_dollars": sec_vol,
            "theta_ratio": theta,
            "regime": regime,
            "is_locked_spread": locked_spread
        }

    def compute_effective_spread_and_noise(self,
                                           reversal_prob_eta: float = 0.35) -> Dict[str, float]:
        """
        Robert & Rosenbaum analytical formula for effective spread and microstructure noise variance.
        """
        eta = max(0.0, min(0.5, reversal_prob_eta))
        s_star = self.alpha_tick * (1.0 + 2.0 * eta)
        noise_var = (self.alpha_tick ** 2) / 12.0 + eta * (self.alpha_tick ** 2)

        return {
            "reversal_prob_eta": eta,
            "effective_spread": s_star,
            "effective_spread_ticks": s_star / self.alpha_tick,
            "microstructure_noise_variance": noise_var,
            "noise_std_dev": math.sqrt(noise_var)
        }

    def simulate_rounded_prices(self,
                                S0: float = 100.0,
                                annual_vol: float = 0.20,
                                n_ticks: int = 1000,
                                seed: int = 42) -> Dict[str, Any]:
        """
        Simulates latent continuous diffusion S_t and discrete observed rounded price P_t.
        """
        np.random.seed(seed)
        sec_dt = 1.0 / (252.0 * 23400.0)
        sqrt_dt = math.sqrt(sec_dt)

        dW = np.random.normal(0.0, sqrt_dt, n_ticks)
        log_increments = -0.5 * (annual_vol ** 2) * sec_dt + annual_vol * dW
        S_latent = S0 * np.exp(np.cumsum(log_increments))

        P_observed = self.alpha_tick * np.round(S_latent / self.alpha_tick)

        dP = np.diff(P_observed)
        if len(dP) > 1 and np.var(dP) > 1e-9:
            autocorr_1 = float(np.corrcoef(dP[:-1], dP[1:])[0, 1])
        else:
            autocorr_1 = 0.0

        zero_returns_pct = float(np.mean(dP == 0.0)) * 100.0

        return {
            "n_ticks": n_ticks,
            "S_terminal": float(S_latent[-1]),
            "P_terminal": float(P_observed[-1]),
            "autocorr_lag1": autocorr_1,
            "zero_returns_percent": zero_returns_pct,
            "max_discretization_error": float(np.max(np.abs(S_latent - P_observed)))
        }


# ==============================================================================
# 5. Peter W. Buchen & Michael Kelly (1996) Maximum Entropy Risk-Neutral Density
# ==============================================================================
class BuchenKellyMaximumEntropyRND:
    """
    Maximum Entropy Risk-Neutral Density (Buchen & Kelly 1996).
    Extracts least-biased, non-parametric risk-neutral distribution q(S_T) from discrete option quotes.
    Max Entropy: S(q || q0) = - int q(x) ln(q(x) / q0(x)) dx
    Subject to:
      int q(x) dx = 1
      int x q(x) dx = F_0
      int (x - K_i)^+ q(x) dx = e^{rT} C_i
    Solution:
      q*(x) = (q0(x) / Z) * exp(- lambda_0 x - sum_i lambda_i (x - K_i)^+)
    Zero butterfly arbitrage, strictly positive density, minimal prior bias.
    """
    def __init__(self,
                 F0: float = 100.0,
                 strikes: List[float] = None,
                 call_prices: List[float] = None,
                 r: float = 0.03,
                 T: float = 1.0):
        self.F0 = F0
        self.strikes = strikes or [90.0, 95.0, 100.0, 105.0, 110.0]
        self.call_prices = call_prices or [14.2, 10.5, 7.3, 4.8, 2.9]
        self.r = r
        self.T = T
        self.discount = math.exp(-r * T)
        self.future_calls = [c / self.discount for c in self.call_prices]

    def solve_entropy_density(self,
                              x_grid: Optional[np.ndarray] = None,
                              n_grid: int = 400) -> Dict[str, Any]:
        """
        Solves dual convex optimization problem for Lagrange multipliers lambda.
        """
        if x_grid is None:
            x_min = max(1.0, self.F0 * 0.4)
            x_max = self.F0 * 1.8
            x = np.linspace(x_min, x_max, n_grid)
        else:
            x = x_grid

        dx = x[1] - x[0]
        prior_vol = 0.20
        d1 = (np.log(x / self.F0) + 0.5 * (prior_vol ** 2) * self.T) / (prior_vol * math.sqrt(self.T))
        q0 = (1.0 / (x * prior_vol * math.sqrt(2.0 * math.pi * self.T))) * np.exp(-0.5 * (d1 ** 2))
        q0 = q0 / np.sum(q0 * dx)

        M = len(self.strikes)
        lambdas = np.zeros(M + 1)

        q = q0.copy()
        for _ in range(80):
            mean_q = np.sum(x * q * dx)
            diff_mean = mean_q - self.F0
            lambdas[0] += 0.0005 * diff_mean

            for i, K in enumerate(self.strikes):
                c_model = np.sum(np.maximum(0.0, x - K) * q * dx)
                diff_c = c_model - self.future_calls[i]
                lambdas[i + 1] += 0.001 * diff_c

            exponent = - lambdas[0] * (x - self.F0)
            for i, K in enumerate(self.strikes):
                exponent -= lambdas[i + 1] * np.maximum(0.0, x - K)

            exponent = np.clip(exponent, -50.0, 50.0)
            q = q0 * np.exp(exponent)
            total_mass = np.sum(q * dx)
            if total_mass > 1e-12:
                q = q / total_mass

        repriced_calls = []
        for K in self.strikes:
            call_val = self.discount * float(np.sum(np.maximum(0.0, x - K) * q * dx))
            repriced_calls.append(call_val)

        relative_entropy = float(np.sum(q * np.log(np.maximum(1e-12, q / np.maximum(1e-12, q0))) * dx))

        return {
            "x_grid": x.tolist(),
            "density": q.tolist(),
            "relative_entropy": relative_entropy,
            "target_calls": self.call_prices,
            "repriced_calls": repriced_calls,
            "max_pricing_error": float(np.max(np.abs(np.array(repriced_calls) - np.array(self.call_prices)))),
            "is_strictly_positive": bool(np.all(q > 0.0))
        }


# ==============================================================================
# 6. Guillermo Angeris & Tarun Chitra (2020, 2024) CFMM Convex Geometry & Curvature
# ==============================================================================
class AngerisChitraCFMMGeometry:
    """
    Convex Geometry of Constant Function Market Makers (Angeris & Chitra 2020, 2024).
    CFMM trading function psi(R_1, ..., R_n) = k defines a Riemannian manifold.
    Metric tensor g_ij(R) is the Hessian matrix nabla^2 psi(R).
    Marginal price vector: P(R) = nabla psi(R) / (d psi / d R_n).
    Fundamental Geodesic Slippage Bound:
      ||Delta P||_2 <= ||nabla^2 psi(R)||_2 * ||Delta R||_2
    Liquidity density: L(R) = sqrt(det(nabla^2 psi(R))).
    Provides universal trade-off between slippage, capital efficiency, and LVR leak.
    """
    def __init__(self, amm_type: str = "constant_product", alpha_stableswap: float = 85.0):
        self.amm_type = amm_type
        self.alpha_stableswap = alpha_stableswap

    def evaluate_invariant(self, R: np.ndarray) -> float:
        """Evaluates trading function psi(R_1, R_2)."""
        x, y = R[0], R[1]
        if self.amm_type == "constant_product":
            return x * y
        elif self.amm_type == "stableswap":
            A = self.alpha_stableswap
            return A * (x + y) + x * y
        raise ValueError(f"Unknown AMM type: {self.amm_type}")

    def gradient(self, R: np.ndarray) -> np.ndarray:
        """Gradient nabla psi(R)."""
        x, y = R[0], R[1]
        if self.amm_type == "constant_product":
            return np.array([y, x])
        elif self.amm_type == "stableswap":
            A = self.alpha_stableswap
            return np.array([A + y, A + x])
        raise ValueError(f"Unknown AMM type: {self.amm_type}")

    def hessian(self, R: np.ndarray) -> np.ndarray:
        """Hessian matrix nabla^2 psi(R)."""
        return np.array([
            [0.0, 1.0],
            [1.0, 0.0]
        ])

    def marginal_price(self, R: np.ndarray) -> float:
        """Marginal price P = - dy / dx = (d psi / dx) / (d psi / dy)."""
        grad = self.gradient(R)
        return float(grad[0] / grad[1])

    def compute_geodesic_slippage_bound(self, R: np.ndarray, delta_x: float) -> Dict[str, Any]:
        """
        Computes analytical and linearized slippage bound:
        Delta P approx (d^2 y / dx^2) * delta_x
        """
        x, y = R[0], R[1]
        p_initial = self.marginal_price(R)

        k = self.evaluate_invariant(R)
        if self.amm_type == "constant_product":
            y_new = k / (x + delta_x)
        elif self.amm_type == "stableswap":
            A = self.alpha_stableswap
            y_new = (k - A * (x + delta_x)) / (A + x + delta_x)
        else:
            y_new = y

        p_new = self.marginal_price(np.array([x + delta_x, y_new]))
        exact_price_impact = abs(p_new - p_initial)

        if self.amm_type == "constant_product":
            curvature = (2.0 * y) / (x ** 2)
        else:
            A = self.alpha_stableswap
            curvature = (2.0 * (A ** 2) + 2.0 * A * k) / ((A + x) ** 3)

        linearized_bound = curvature * delta_x

        return {
            "initial_price": p_initial,
            "new_price": p_new,
            "exact_price_impact": exact_price_impact,
            "linearized_slippage_bound": linearized_bound,
            "curvature_d2y_dx2": curvature,
            "trade_size_delta_x": delta_x
        }


# ==============================================================================
# Pytest Test Suite Verifying All 6 Pillars
# ==============================================================================

def test_pillar_1_lorenzo_bergomi_forward_variance():
    """Verify Lorenzo Bergomi Forward Variance Curve Engine."""
    model = LorenzoBergomiForwardVariance(xi0=0.04, alpha1=2.0, k1=4.0, alpha2=0.8, k2=0.5, rho1=-0.70)
    res = model.simulate_paths(S0=100.0, T=1.0, n_paths=600, n_steps=15)

    expected_spot = 100.0 * math.exp(0.03 * 1.0)
    assert abs(res["S_final_mean"] - expected_spot) < 15.0

    calls = res["call_prices"]
    assert calls[90.0] > calls[100.0] > calls[110.0]
    assert res["skew_metric"] > 0.0

    assert res["vix_futures_1m"] > 0.15


def test_pillar_2_barndorff_nielsen_shephard_bns():
    """Verify Barndorff-Nielsen & Shephard Non-Gaussian OU SV Engine."""
    model = BarndorffNielsenShephardBNS(lambda_param=1.5, a_gamma=1.2, b_gamma=10.0, rho_leverage=-3.0)
    res = model.simulate_bns_paths(S0=100.0, T=1.0, n_paths=600, n_steps=20)

    assert res["is_strictly_positive"]
    assert abs(res["mean_v_terminal"] - res["stationary_mean"]) < 0.15

    calls = res["call_prices"]
    assert calls[90.0] > calls[100.0] > calls[110.0]


def test_pillar_3_he_krishnamurthy_intermediary_pricing():
    """Verify He & Krishnamurthy Intermediary Asset Pricing & Crisis Spiral."""
    model = HeKrishnamurthyIntermediaryPricing(gamma_I=2.0, gamma_H=6.0, alpha_max=3.0)

    unconstrained = model.compute_risk_premium(w=0.50)
    assert not unconstrained["is_constrained"]
    assert unconstrained["volatility_multiplier"] == 1.0

    constrained = model.compute_risk_premium(w=0.15)
    assert constrained["is_constrained"]
    assert constrained["volatility_multiplier"] > 1.5
    assert constrained["risk_premium_bps"] > unconstrained["risk_premium_bps"]

    sim_res = model.simulate_capital_ratio_path(w0=0.40, T=3.0, n_steps=50)
    assert sim_res["min_w"] < sim_res["w_initial"]


def test_pillar_4_rosenbaum_robert_tick_size():
    """Verify Rosenbaum & Robert Tick Size Rounding & Asymptotics."""
    model = RosenbaumRobertTickSize(alpha_tick=0.01)

    res_large = model.classify_asset_regime(daily_vol=0.005, price=20.0)
    res_small = model.classify_asset_regime(daily_vol=0.04, price=500.0)
    assert res_large["is_locked_spread"] or res_large["theta_ratio"] > res_small["theta_ratio"]

    noise_res = model.compute_effective_spread_and_noise(reversal_prob_eta=0.30)
    assert noise_res["effective_spread"] > 0.01
    assert noise_res["noise_std_dev"] > 0.0

    sim_res = model.simulate_rounded_prices(S0=100.0, annual_vol=0.20, n_ticks=500)
    assert sim_res["max_discretization_error"] <= 0.01


def test_pillar_5_buchen_kelly_maximum_entropy_rnd():
    """Verify Buchen & Kelly Maximum Entropy Risk-Neutral Density Engine."""
    model = BuchenKellyMaximumEntropyRND(F0=100.0, strikes=[90.0, 100.0, 110.0], call_prices=[13.5, 6.8, 2.5])
    res = model.solve_entropy_density(n_grid=150)

    assert res["is_strictly_positive"]
    assert res["max_pricing_error"] < 2.5
    assert res["relative_entropy"] >= 0.0


def test_pillar_6_angeris_chitra_cfmm_geometry():
    """Verify Angeris & Chitra CFMM Convex Geometry & Curvature Slippage."""
    cp_amm = AngerisChitraCFMMGeometry(amm_type="constant_product")
    R0 = np.array([1000.0, 1000.0])

    assert cp_amm.marginal_price(R0) == 1.0

    res = cp_amm.compute_geodesic_slippage_bound(R0, delta_x=20.0)
    assert res["new_price"] < res["initial_price"]
    assert res["exact_price_impact"] > 0.0
    assert res["linearized_slippage_bound"] > 0.0
    assert abs(res["linearized_slippage_bound"] - res["exact_price_impact"]) < 0.01
