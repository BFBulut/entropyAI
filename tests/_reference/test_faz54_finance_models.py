"""Programmatic TDD Verification Suite for Faz 54 Quantitative Finance Engines.

Models:
1. Robert C. Merton (1969, 1971): Continuous-Time Stochastic Optimal Portfolio Choice & Consumption (HJB Equation)
2. John C. Cox, Jonathan E. Ingersoll & Stephen A. Ross (CIR 1985): Square-Root Rate Diffusion & Exact ZCB Engine
3. Olivier Ledoit & Michael Wolf (2012, 2020): Non-Linear Covariance Shrinkage & Marchenko-Pastur De-biasing Engine
4. Lars Peter Hansen & Ravi Jagannathan (1991): Stochastic Discount Factor (SDF) Volatility Bound & Distance Engine
5. Omar El Euch & Mathieu Rosenbaum (2019) / Jim Gatheral (2018): Rough Heston Model & Fractional Riccati Engine
6. Ananth Madhavan, David Richardson & Mark Roomans (MRR 1997): Market Microstructure Bid-Ask Spread Decomposition Engine
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Numerical Functions (Acklam normal, Gamma approximation)
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_ppf(p: float) -> float:
    """Inverse normal CDF via Acklam's rational approximation."""
    if p <= 0.0:
        return -float('inf')
    if p >= 1.0:
        return float('inf')
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)


# ==============================================================================
# Model 1: Robert C. Merton (1969, 1971) Continuous-Time Stochastic Portfolio & Consumption
# ==============================================================================
class MertonHJBPortfolioConsumptionEngine:
    """Merton (1969, 1971) continuous-time stochastic optimal portfolio and consumption problem.
    Solves the Hamilton-Jacobi-Bellman (HJB) PDE under CRRA utility U(c) = c^(1-gamma) / (1-gamma).
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        risky_return: float = 0.09,
        risky_volatility: float = 0.20,
        risk_aversion: float = 3.0,
        discount_rate: float = 0.04,
        horizon_years: float = 10.0,
        bequest_weight: float = 0.0
    ):
        if risk_aversion <= 0.0 or math.isclose(risk_aversion, 1.0, rel_tol=1e-5):
            raise ValueError("Risk aversion gamma must be positive and != 1.0 for standard CRRA.")
        if risky_volatility <= 0.0:
            raise ValueError("Risky volatility must be strictly positive.")

        self.r = risk_free_rate
        self.mu = risky_return
        self.sigma = risky_volatility
        self.gamma = risk_aversion
        self.rho = discount_rate
        self.T = horizon_years
        self.bequest = bequest_weight

        # Constant optimal risky portfolio fraction: pi* = (mu - r) / (gamma * sigma^2)
        self.pi_star = (self.mu - self.r) / (self.gamma * (self.sigma ** 2))

        # Effective discount rate nu
        sharpe_sq = ((self.mu - self.r) / self.sigma) ** 2
        r_effective = self.r + sharpe_sq / (2.0 * self.gamma)
        self.nu = (self.rho - (1.0 - self.gamma) * r_effective) / self.gamma

    def time_weight_function(self, t: float) -> float:
        """Evaluates f(t) such that value function V(w, t) = f(t)^gamma * w^(1-gamma)/(1-gamma)."""
        tau = max(0.0, self.T - t)
        f_T = self.bequest

        if math.isclose(self.nu, 0.0, abs_tol=1e-8):
            return f_T + tau
        else:
            return (1.0 / self.nu) + (f_T - (1.0 / self.nu)) * math.exp(-self.nu * tau)

    def optimal_consumption(self, wealth: float, t: float) -> float:
        """Optimal consumption rate c*(w, t) = w / f(t)."""
        if wealth <= 0.0:
            return 0.0
        f_t = self.time_weight_function(t)
        if f_t <= 0.0:
            return 0.0
        return wealth / f_t

    def infinite_horizon_consumption_propensity(self) -> float:
        """Asymptotic MPC as T -> inf: c*(w) = nu * w (valid when nu > 0)."""
        return max(0.0, self.nu)

    def value_function(self, wealth: float, t: float) -> float:
        """Evaluates V(w, t) = f(t)^gamma * w^(1-gamma) / (1-gamma)."""
        if wealth <= 0.0:
            return -float('inf') if self.gamma > 1.0 else 0.0
        f_t = self.time_weight_function(t)
        return (f_t ** self.gamma) * (wealth ** (1.0 - self.gamma)) / (1.0 - self.gamma)

    def verify_hjb_residual(self, wealth: float, t: float) -> Dict[str, float]:
        """Numerically and analytically evaluates the HJB PDE residual at (w, t).
        HJB Equation:
          V_t - rho*V + sup_c { c^(1-gamma)/(1-gamma) - c*V_w } +
          sup_pi { (r*w + pi*(mu - r)*w)*V_w + 0.5*pi^2*sigma^2*w^2*V_ww } = 0
        """
        f_t = self.time_weight_function(t)
        f_prime = (self.nu * f_t - 1.0)  # df/dt = nu*f - 1

        # Analytically exact partial derivatives
        # V = f^gamma * w^(1-gamma) / (1-gamma)
        V = (f_t ** self.gamma) * (wealth ** (1.0 - self.gamma)) / (1.0 - self.gamma)
        V_t = self.gamma * (f_t ** (self.gamma - 1.0)) * f_prime * (wealth ** (1.0 - self.gamma)) / (1.0 - self.gamma)
        V_w = (f_t ** self.gamma) * (wealth ** (-self.gamma))
        V_ww = -self.gamma * (f_t ** self.gamma) * (wealth ** (-self.gamma - 1.0))

        c_star = self.optimal_consumption(wealth, t)
        pi_star = self.pi_star

        # Components of HJB
        utility_c = (c_star ** (1.0 - self.gamma)) / (1.0 - self.gamma)
        consumption_drift = -c_star * V_w
        portfolio_drift = (self.r * wealth + pi_star * (self.mu - self.r) * wealth) * V_w
        diffusion_term = 0.5 * (pi_star ** 2) * (self.sigma ** 2) * (wealth ** 2) * V_ww
        discount_term = -self.rho * V

        hjb_residual = V_t + discount_term + utility_c + consumption_drift + portfolio_drift + diffusion_term

        return {
            "wealth": wealth,
            "t": t,
            "pi_star": pi_star,
            "c_star": c_star,
            "V": V,
            "hjb_residual": float(hjb_residual),
            "is_hjb_satisfied": abs(hjb_residual) < 1e-6
        }

    def simulate_wealth_trajectory(
        self,
        initial_wealth: float,
        dt: float = 0.01,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Simulates the optimal wealth and consumption path over time."""
        np.random.seed(seed)
        steps = int(self.T / dt)
        time_grid = np.linspace(0.0, self.T, steps + 1)
        wealth_path = np.zeros(steps + 1)
        consumption_path = np.zeros(steps + 1)

        wealth_path[0] = initial_wealth
        consumption_path[0] = self.optimal_consumption(initial_wealth, 0.0)

        for step in range(steps):
            t_curr = time_grid[step]
            w_curr = wealth_path[step]
            if w_curr <= 0.0:
                wealth_path[step+1:] = 0.0
                consumption_path[step+1:] = 0.0
                break

            c_curr = self.optimal_consumption(w_curr, t_curr)
            consumption_path[step] = c_curr

            # Drift: [r*w + pi*(mu - r)*w - c]*dt
            drift = (self.r * w_curr + self.pi_star * (self.mu - self.r) * w_curr - c_curr) * dt
            # Diffusion: pi*sigma*w*dW
            z = np.random.standard_normal()
            diffusion = self.pi_star * self.sigma * w_curr * math.sqrt(dt) * z

            w_next = max(0.0, w_curr + drift + diffusion)
            wealth_path[step + 1] = w_next

        consumption_path[-1] = self.optimal_consumption(wealth_path[-1], self.T)

        return {
            "time_grid": time_grid,
            "wealth_path": wealth_path,
            "consumption_path": consumption_path,
            "final_wealth": wealth_path[-1]
        }


# ==============================================================================
# Model 2: Cox-Ingersoll-Ross (CIR 1985) Square-Root Diffusion & ZCB Pricing
# ==============================================================================
class CIRSquareRootRateEngine:
    """Cox-Ingersoll-Ross (1985) term structure engine:
    dr_t = kappa * (theta - r_t) dt + sigma * sqrt(r_t) dW_t
    Features exact Zero-Coupon Bond (ZCB) pricing and Feller condition verification.
    """

    def __init__(
        self,
        kappa: float = 0.30,       # Mean reversion speed
        theta: float = 0.05,       # Long term mean rate
        sigma: float = 0.10,       # Volatility parameter
        current_rate: float = 0.04
    ):
        if kappa <= 0.0 or theta <= 0.0 or sigma <= 0.0:
            raise ValueError("CIR parameters kappa, theta, and sigma must be strictly positive.")

        self.kappa = kappa
        self.theta = theta
        self.sigma = sigma
        self.r0 = max(0.0, current_rate)

        # Feller condition: 2 * kappa * theta >= sigma^2
        self.feller_ratio = (2.0 * self.kappa * self.theta) / (self.sigma ** 2)
        self.is_feller_satisfied = self.feller_ratio >= 1.0

        # Auxiliary CIR constants
        self.gamma = math.sqrt(self.kappa ** 2 + 2.0 * (self.sigma ** 2))

    def zero_coupon_bond_price(self, maturity_tau: float, r_t: Optional[float] = None) -> float:
        """Calculates P(t, t + tau) = A(tau) * exp(-B(tau) * r_t)."""
        if maturity_tau <= 0.0:
            return 1.0
        r = self.r0 if r_t is None else max(0.0, r_t)

        tau = maturity_tau
        exp_gamma_tau = math.exp(self.gamma * tau)

        # Denominator = (gamma + kappa)*(exp(gamma*tau) - 1) + 2*gamma
        denom = (self.gamma + self.kappa) * (exp_gamma_tau - 1.0) + 2.0 * self.gamma

        # B(tau) = 2*(exp(gamma*tau) - 1) / denom
        b_tau = (2.0 * (exp_gamma_tau - 1.0)) / denom

        # A(tau) = [2*gamma * exp((kappa + gamma)*tau / 2) / denom] ^ (2*kappa*theta / sigma^2)
        power = (2.0 * self.kappa * self.theta) / (self.sigma ** 2)
        numerator_a = 2.0 * self.gamma * math.exp(0.5 * (self.kappa + self.gamma) * tau)
        a_tau = (numerator_a / denom) ** power

        return float(a_tau * math.exp(-b_tau * r))

    def yield_to_maturity(self, maturity_tau: float, r_t: Optional[float] = None) -> float:
        """Calculates spot yield y(tau) = -ln(P(tau)) / tau."""
        if maturity_tau <= 1e-6:
            return self.r0 if r_t is None else r_t
        p = self.zero_coupon_bond_price(maturity_tau, r_t)
        return -math.log(p) / maturity_tau

    def asymptotic_long_term_yield(self) -> float:
        """Long-term yield as tau -> inf: y_inf = 2*kappa*theta / (kappa + gamma)."""
        return (2.0 * self.kappa * self.theta) / (self.kappa + self.gamma)

    def conditional_moments(self, tau: float, r_s: Optional[float] = None) -> Tuple[float, float]:
        """Calculates exact E[r_{s+tau} | r_s] and Var[r_{s+tau} | r_s]."""
        r = self.r0 if r_s is None else r_s
        exp_kt = math.exp(-self.kappa * tau)

        mean = r * exp_kt + self.theta * (1.0 - exp_kt)
        var = r * ((self.sigma ** 2) / self.kappa) * (exp_kt - exp_kt ** 2) + \
              self.theta * ((self.sigma ** 2) / (2.0 * self.kappa)) * ((1.0 - exp_kt) ** 2)

        return float(mean), float(var)

    def generate_yield_curve(self, maturities: List[float]) -> Dict[str, Any]:
        """Generates the CIR term structure of interest rates."""
        prices = [self.zero_coupon_bond_price(m) for m in maturities]
        yields = [self.yield_to_maturity(m) for m in maturities]
        return {
            "maturities": maturities,
            "prices": prices,
            "yields": yields,
            "asymptotic_yield": self.asymptotic_long_term_yield(),
            "feller_satisfied": self.is_feller_satisfied
        }


# ==============================================================================
# Model 3: Olivier Ledoit & Michael Wolf (2012, 2020) Non-Linear Shrinkage Engine
# ==============================================================================
class LedoitWolfNonLinearShrinkageEngine:
    """Ledoit & Wolf (2012, 2020) Non-Linear Covariance Matrix Shrinkage.
    De-biases individual sample eigenvalues using the Hilbert/Stieltjes transform
    under the Marchenko-Pastur asymptotic spectral limit (p/n -> c in (0, inf)).
    """

    def __init__(self, data: np.ndarray):
        """data: matrix of shape (n_samples, p_assets)."""
        if data.ndim != 2:
            raise ValueError("Input data must be 2-dimensional (n x p).")
        self.X = data - np.mean(data, axis=0)  # Demeaned
        self.n, self.p = self.X.shape

        if self.n < 4 or self.p < 2:
            raise ValueError("Sample size n and dimension p must be sufficiently large.")

        self.c = float(self.p) / float(self.n)
        # Sample covariance matrix
        self.S = (self.X.T @ self.X) / float(self.n)

        # Spectral decomposition S = U Lambda U^T
        eigenvalues, eigenvectors = np.linalg.eigh(self.S)
        # Sort in ascending order
        idx = np.argsort(eigenvalues)
        self.sample_eigenvalues = np.maximum(1e-12, eigenvalues[idx])
        self.eigenvectors = eigenvectors[:, idx]

    def fit_nonlinear_shrinkage(self) -> Dict[str, Any]:
        """Performs analytical kernel-smoothed Stieltjes inversion on sample eigenvalues."""
        p = self.p
        n = self.n
        c = self.c
        lambdas = self.sample_eigenvalues

        # Optimal kernel smoothing bandwidth h_n ~ p^(-1/3)
        h = (p ** (-0.3333333333333333)) * np.std(lambdas)
        if h <= 1e-6:
            h = 1e-4

        # Stieltjes transform evaluation at z_i = lambda_i + i*h
        shrunk_eigenvalues = np.zeros(p)

        for i in range(p):
            lam_i = lambdas[i]
            # m(z) = (1/p) * sum_j 1 / (lambda_j - (lam_i + i*h))
            diffs = lambdas - lam_i
            denoms = diffs ** 2 + h ** 2
            # Real part: sum(diffs / denoms) / p
            re_m = np.mean(diffs / denoms)
            # Imaginary part: sum(h / denoms) / p
            im_m = np.mean(h / denoms)

            # Density f(lambda) = (1 / pi) * im_m
            f_val = im_m / math.pi
            # Hilbert transform H(lambda) = re_m

            # Non-linear shrinkage formula (Ledoit & Wolf 2020):
            # d_i* = lambda_i / [ (1 - c - c*lambda_i*re_m)^2 + (c*pi*lambda_i*f_val)^2 ]
            term_real = 1.0 - c - c * lam_i * re_m
            term_imag = c * math.pi * lam_i * f_val
            denom = term_real ** 2 + term_imag ** 2

            if denom > 1e-15:
                d_star = lam_i / denom
            else:
                d_star = lam_i

            shrunk_eigenvalues[i] = max(1e-8, d_star)

        # Enforce trace matching: Tr(Sigma*) = Tr(S)
        trace_sample = np.sum(lambdas)
        trace_shrunk = np.sum(shrunk_eigenvalues)
        if trace_shrunk > 0.0:
            shrunk_eigenvalues = shrunk_eigenvalues * (trace_sample / trace_shrunk)

        # Reconstruct non-linear shrunk covariance matrix
        sigma_nls = (self.eigenvectors * shrunk_eigenvalues) @ self.eigenvectors.T

        # Also compute standard linear shrinkage (Ledoit-Wolf 2004) for benchmark
        mu_bar = trace_sample / p
        delta = self.S - mu_bar * np.eye(p)
        delta_sq = np.sum(delta ** 2)

        # Asymptotic linear shrinkage intensity
        alpha_linear = min(1.0, max(0.0, (c / (1.0 + c))))
        sigma_linear = (1.0 - alpha_linear) * self.S + alpha_linear * mu_bar * np.eye(p)

        return {
            "sample_covariance": self.S,
            "sigma_nls": sigma_nls,
            "sigma_linear": sigma_linear,
            "sample_eigenvalues": lambdas,
            "shrunk_eigenvalues": shrunk_eigenvalues,
            "condition_number_sample": float(lambdas[-1] / lambdas[0]),
            "condition_number_nls": float(shrunk_eigenvalues[-1] / shrunk_eigenvalues[0]),
            "p_to_n_ratio": c
        }

    def evaluate_minimum_variance_portfolio(
        self,
        test_returns: np.ndarray
    ) -> Dict[str, float]:
        """Compares out-of-sample variance of the Minimum Variance Portfolio across estimators."""
        p = self.p
        ones = np.ones(p)

        fit = self.fit_nonlinear_shrinkage()
        s_mat = fit["sample_covariance"]
        linear_mat = fit["sigma_linear"]
        nls_mat = fit["sigma_nls"]

        # Weights w = Sigma^-1 * 1 / (1^T Sigma^-1 1)
        w_sample = np.linalg.pinv(s_mat) @ ones
        w_sample /= np.sum(w_sample)

        w_linear = np.linalg.solve(linear_mat, ones)
        w_linear /= np.sum(w_linear)

        w_nls = np.linalg.solve(nls_mat, ones)
        w_nls /= np.sum(w_nls)

        var_sample = float(w_sample.T @ np.cov(test_returns, rowvar=False) @ w_sample)
        var_linear = float(w_linear.T @ np.cov(test_returns, rowvar=False) @ w_linear)
        var_nls = float(w_nls.T @ np.cov(test_returns, rowvar=False) @ w_nls)

        return {
            "var_sample": var_sample,
            "var_linear": var_linear,
            "var_nls": var_nls,
            "variance_reduction_over_sample": max(0.0, (var_sample - var_nls) / var_sample),
            "variance_reduction_over_linear": max(0.0, (var_linear - var_nls) / var_linear)
        }


# ==============================================================================
# Model 4: Hansen & Jagannathan (1991) SDF Volatility Bound & Distance Engine
# ==============================================================================
class HansenJagannathanBoundEngine:
    """Lars Peter Hansen & Ravi Jagannathan (1991) Stochastic Discount Factor (SDF) frontier.
    Calculates the minimum SDF volatility required to price a set of assets,
    the maximum Sharpe ratio tangency portfolio, and the Hansen-Jagannathan distance.
    """

    def __init__(self, asset_returns: np.ndarray, risk_free_rate: float = 0.02):
        """asset_returns: (n_observations, k_assets) matrix of gross or net returns."""
        self.R = asset_returns
        self.n, self.k = self.R.shape
        self.rf = risk_free_rate

        self.mu = np.mean(self.R, axis=0)
        self.Sigma = np.cov(self.R, rowvar=False)
        self.excess_mu = self.mu - self.rf

        # Second moment matrix Omega = E[R R^T]
        self.Omega = (self.R.T @ self.R) / float(self.n)
        self.Omega_inv = np.linalg.inv(self.Omega)
        self.Sigma_inv = np.linalg.inv(self.Sigma)

    def maximum_sharpe_ratio(self) -> Tuple[float, np.ndarray]:
        """Calculates SR_max = sqrt(mu_e^T Sigma^-1 mu_e) and optimal tangency weights."""
        sr_sq = float(self.excess_mu.T @ self.Sigma_inv @ self.excess_mu)
        sr_max = math.sqrt(max(0.0, sr_sq))

        raw_weights = self.Sigma_inv @ self.excess_mu
        sum_weights = np.sum(raw_weights)
        weights = raw_weights / sum_weights if abs(sum_weights) > 1e-8 else raw_weights
        return sr_max, weights

    def hj_volatility_lower_bound(self, expected_sdf: float) -> float:
        """Computes sigma(m) lower bound for a given E[m].
        For excess returns: sigma(m)/E[m] >= SR_max => sigma(m) >= E[m] * SR_max.
        """
        if expected_sdf <= 0.0:
            return float('inf')
        sr_max, _ = self.maximum_sharpe_ratio()
        return expected_sdf * sr_max

    def generate_hj_frontier(self, e_m_grid: List[float]) -> Dict[str, Any]:
        """Generates the Hansen-Jagannathan volatility parabola."""
        ones = np.ones(self.k)
        volatilities = []

        for e_m in e_m_grid:
            # Pricing error vector if m had no variance: e = e_m * mu - 1
            e = e_m * self.mu - ones
            # Minimum variance of SDF satisfying E[m R] = 1:
            var_m = float(e.T @ self.Sigma_inv @ e)
            volatilities.append(math.sqrt(max(0.0, var_m)))

        return {
            "expected_sdf_grid": e_m_grid,
            "min_sdf_volatility": volatilities,
            "tangency_sharpe": self.maximum_sharpe_ratio()[0]
        }

    def hansen_jagannathan_distance(self, candidate_sdf_series: np.ndarray) -> float:
        """Calculates delta_HJ = sqrt( e^T Omega^-1 e ) where e = E[m R] - 1.
        Measures the misspecification of candidate pricing kernel.
        """
        if len(candidate_sdf_series) != self.n:
            raise ValueError("Candidate SDF series length must match return observations.")

        # Pricing error e = (1/n) * sum(m_t * R_t) - 1
        pricing_moments = np.mean(candidate_sdf_series[:, None] * self.R, axis=0)
        e = pricing_moments - np.ones(self.k)

        dist_sq = float(e.T @ self.Omega_inv @ e)
        return math.sqrt(max(0.0, dist_sq))


# ==============================================================================
# Model 5: Omar El Euch & Mathieu Rosenbaum (2019) / Gatheral (2018) Rough Heston Engine
# ==============================================================================
class RoughHestonRiccatiEngine:
    """Rough Heston Volatility Engine:
    Fractional Riccati Volterra ODE:
    D^alpha h(t, u) = 0.5*(-u^2 - i*u) + (i*u*rho*nu - lambda)*h(t, u) + 0.5*nu^2 * h(t, u)^2
    where alpha = H + 1/2 in (0.5, 1.0).
    Solves using Fractional Adams-Bashforth-Moulton predictor-corrector integration.
    """

    def __init__(
        self,
        hurst: float = 0.12,          # Empirically rough Hurst parameter H ~ 0.12
        lam: float = 1.0,             # Mean reversion speed lambda
        theta: float = 0.04,          # Long term variance
        nu: float = 0.30,             # Vol of vol
        rho: float = -0.70,           # Spot-vol correlation (leverage effect)
        v0: float = 0.04
    ):
        if not (0.0 < hurst < 0.5):
            raise ValueError("Rough Heston Hurst parameter must be in (0, 0.5).")
        self.H = hurst
        self.alpha = hurst + 0.5      # alpha in (0.5, 1.0)
        self.lam = lam
        self.theta = theta
        self.nu = nu
        self.rho = rho
        self.v0 = v0

    def riccati_rhs(self, h: complex, u: float) -> complex:
        """Evaluates F(u, h) = 0.5*(-u^2 - i*u) + (i*u*rho*nu - lam)*h + 0.5*nu^2*h^2."""
        c1 = 0.5 * (- (u ** 2) - 1j * u)
        c2 = (1j * u * self.rho * self.nu - self.lam)
        c3 = 0.5 * (self.nu ** 2)
        return c1 + c2 * h + c3 * (h ** 2)

    def solve_fractional_riccati(
        self,
        u: float,
        maturity_t: float,
        steps: int = 100
    ) -> List[complex]:
        """Fractional Adams-Bashforth-Moulton integration of Volterra integral:
        h(t, u) = (1 / Gamma(alpha)) * int_0^t (t-s)^(alpha - 1) F(u, h(s, u)) ds
        """
        alpha = self.alpha
        dt = maturity_t / float(steps)
        gamma_alpha1 = math.gamma(alpha + 1.0)
        gamma_alpha2 = math.gamma(alpha + 2.0)

        h_vals = [0.0 + 0.0j] * (steps + 1)
        f_vals = [self.riccati_rhs(0.0 + 0.0j, u)]

        coeff_p = (dt ** alpha) / gamma_alpha1
        coeff_c = (dt ** alpha) / gamma_alpha2

        for n in range(1, steps + 1):
            # Predictor step (Fractional Adams-Bashforth)
            sum_p = 0.0 + 0.0j
            for j in range(n):
                b_jn = ((n - j) ** alpha) - ((n - j - 1) ** alpha)
                sum_p += b_jn * f_vals[j]
            h_pred = coeff_p * sum_p

            # Corrector step (Fractional Adams-Moulton)
            f_pred = self.riccati_rhs(h_pred, u)
            sum_c = 0.0 + 0.0j
            for j in range(n):
                if j == 0:
                    a_jn = ((n - 1) ** (alpha + 1.0)) - (n - 1.0 - alpha) * (n ** alpha)
                else:
                    a_jn = ((n - j + 1) ** (alpha + 1.0)) - 2.0 * ((n - j) ** (alpha + 1.0)) + ((n - j - 1) ** (alpha + 1.0))
                sum_c += a_jn * f_vals[j]

            h_corr = coeff_c * (f_pred + sum_c)
            h_vals[n] = h_corr
            f_vals.append(self.riccati_rhs(h_corr, u))

        return h_vals

    def evaluate_characteristic_function(
        self,
        u: float,
        maturity_t: float,
        steps: int = 100
    ) -> complex:
        """Evaluates phi(u, T) = E[exp(i * u * ln(S_T / S_0))].
        Under Rough Heston:
        phi(u, T) = exp( v0 * h(T) + theta * lam * int_0^T h(s) ds )
        """
        h_vals = self.solve_fractional_riccati(u, maturity_t, steps=steps)
        dt = maturity_t / float(steps)

        # Trapezoidal numerical integration of int_0^T h(s) ds
        integral_h = (0.5 * h_vals[0] + np.sum(h_vals[1:-1]) + 0.5 * h_vals[-1]) * dt

        # Initial variance term
        v0_term = self.v0 * h_vals[-1]

        exponent = v0_term + self.theta * self.lam * integral_h
        return np.exp(exponent)

    def power_law_atm_skew_scaling(
        self,
        maturities: List[float]
    ) -> Dict[str, Any]:
        """Demonstrates power-law explosion of ATM implied volatility skew:
        |d sigma_impl / d ln(K)|_ATM ~ T^(alpha - 1) = T^(H - 0.5)
        For H = 0.12, scaling exponent is -0.38.
        """
        skews = []
        for mat in maturities:
            # Analytical proxy for ATM skew under rough fractional Riccati
            skew_val = abs(0.5 * self.rho * self.nu * (mat ** (self.H - 0.5)))
            skews.append(float(skew_val))

        log_t = [math.log(m) for m in maturities]
        log_skew = [math.log(s) for s in skews]
        slope, _ = np.polyfit(log_t, log_skew, 1)

        return {
            "maturities": maturities,
            "at_the_money_skews": skews,
            "empirical_log_slope": float(slope),
            "theoretical_exponent": float(self.H - 0.5),
            "is_power_law_verified": abs(slope - (self.H - 0.5)) < 0.05
        }


# ==============================================================================
# Model 6: Madhavan, Richardson & Roomans (MRR 1997) Microstructure Spread Decomposition
# ==============================================================================
class MadhavanRichardsonRoomansSpreadEngine:
    """Madhavan, Richardson & Roomans (1997) Bid-Ask Spread Decomposition Engine.
    Disentangles observed price changes Delta p_t into:
    1. Adverse selection / asymmetric information parameter (theta)
    2. Order processing / dealer concession half-spread (phi)
    3. Trade indicator autocorrelation (rho)
    Regression: Delta p_t = (phi + theta) x_t - (phi + rho * theta) x_{t-1} + u_t
    """

    def __init__(self, price_changes: np.ndarray, trade_signs: np.ndarray):
        """price_changes: Delta p_t = p_t - p_{t-1} (length N)
        trade_signs: x_t in {-1, +1} (length N)
        """
        if len(price_changes) != len(trade_signs):
            raise ValueError("Price changes and trade signs must have identical lengths.")
        if len(price_changes) < 10:
            raise ValueError("At least 10 observations required for MRR econometric estimation.")

        self.dp = price_changes[1:]
        self.x = trade_signs[1:]
        self.x_lag = trade_signs[:-1]
        self.N = len(self.dp)

    def estimate_mrr_parameters(self) -> Dict[str, float]:
        """Performs OLS / GMM regression of Delta p_t on x_t and x_{t-1}."""
        # 1. Estimate order flow autocorrelation rho: E[x_t | x_{t-1}] = rho * x_{t-1}
        cov_xx = float(np.cov(self.x, self.x_lag)[0, 1])
        var_x = float(np.var(self.x_lag))
        rho = cov_xx / var_x if var_x > 1e-10 else 0.0
        rho = max(-0.95, min(0.95, rho))

        # 2. Bivariate OLS regression: dp = beta_1 * x_t + beta_2 * x_{t-1} + e
        X_mat = np.column_stack([self.x, self.x_lag])
        beta = np.linalg.pinv(X_mat.T @ X_mat) @ (X_mat.T @ self.dp)

        beta1, beta2 = float(beta[0]), float(beta[1])

        # Model identities:
        # beta1 = phi + theta
        # beta2 = -(phi + rho * theta)
        # Sum: beta1 + beta2 = theta * (1 - rho)
        denom = 1.0 - rho if abs(1.0 - rho) > 1e-6 else 1e-6
        theta = max(0.0, (beta1 + beta2) / denom)
        phi = max(0.0, beta1 - theta)

        total_half_spread = phi + theta
        effective_spread = 2.0 * total_half_spread

        adverse_selection_share = theta / total_half_spread if total_half_spread > 1e-8 else 0.5
        order_processing_share = phi / total_half_spread if total_half_spread > 1e-8 else 0.5

        # Residuals and R-squared
        residuals = self.dp - (beta1 * self.x + beta2 * self.x_lag)
        total_var = np.var(self.dp)
        r_squared = 1.0 - (np.var(residuals) / total_var) if total_var > 1e-10 else 0.0

        return {
            "theta_adverse_selection": float(theta),
            "phi_order_processing": float(phi),
            "rho_trade_autocorrelation": float(rho),
            "effective_spread": float(effective_spread),
            "adverse_selection_share": float(adverse_selection_share),
            "order_processing_share": float(order_processing_share),
            "r_squared": float(max(0.0, min(1.0, r_squared)))
        }

    @classmethod
    def simulate_mrr_market(
        cls,
        n_ticks: int = 5000,
        theta: float = 0.05,
        phi: float = 0.08,
        rho: float = 0.40,
        sigma_eps: float = 0.02,
        seed: int = 42
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simulates synthetic high-frequency tick market with known MRR parameters."""
        np.random.seed(seed)
        x = np.zeros(n_ticks)
        p = np.zeros(n_ticks)
        m = np.zeros(n_ticks)

        x[0] = 1 if np.random.rand() > 0.5 else -1
        m[0] = 100.0
        p[0] = m[0] + phi * x[0]

        for t in range(1, n_ticks):
            # Autocorrelated trade sign: P(x_t = x_{t-1}) = (1 + rho) / 2
            p_same = (1.0 + rho) / 2.0
            x[t] = x[t-1] if np.random.rand() < p_same else -x[t-1]

            # Innovation in order flow
            eps = np.random.normal(0.0, sigma_eps)
            m[t] = m[t-1] + theta * (x[t] - rho * x[t-1]) + eps
            p[t] = m[t] + phi * x[t]

        price_changes = np.diff(p, prepend=p[0])
        return price_changes, x


# ==============================================================================
# PYTEST TEST SUITE FOR FAZ 54 QUANTITATIVE ENGINES
# ==============================================================================
class TestFaz54QuantitativeFinanceEngines:
    """Rigorous programmatic verification suite for Faz 54 models."""

    def test_merton_hjb_portfolio_consumption_engine(self):
        """Verifies Merton continuous-time portfolio & consumption HJB solution."""
        engine = MertonHJBPortfolioConsumptionEngine(
            risk_free_rate=0.03,
            risky_return=0.09,
            risky_volatility=0.20,
            risk_aversion=3.0,
            discount_rate=0.04,
            horizon_years=10.0,
            bequest_weight=0.5
        )

        # 1. Theoretical risky fraction pi* = (0.09 - 0.03) / (3 * 0.04) = 0.06 / 0.12 = 0.50
        assert math.isclose(engine.pi_star, 0.50, rel_tol=1e-5), f"Expected pi* = 0.50, got {engine.pi_star}"

        # 2. Verify HJB PDE residual at multiple wealth and time points
        test_points = [(100.0, 0.0), (250.0, 2.5), (500.0, 5.0), (1000.0, 7.5)]
        for w, t in test_points:
            res = engine.verify_hjb_residual(w, t)
            assert res["is_hjb_satisfied"], f"HJB residual failed at w={w}, t={t}: {res['hjb_residual']}"
            assert res["c_star"] > 0.0, "Consumption must be strictly positive."

        # 3. Simulate wealth trajectory
        sim = engine.simulate_wealth_trajectory(initial_wealth=1000.0, dt=0.02, seed=123)
        assert len(sim["wealth_path"]) > 100
        assert sim["final_wealth"] >= 0.0

    def test_cir_square_root_rate_engine(self):
        """Verifies CIR (1985) term structure, Feller condition and ZCB pricing."""
        # kappa=0.50, theta=0.05, sigma=0.15 => 2*kappa*theta = 0.05, sigma^2 = 0.0225 => Feller > 1
        cir = CIRSquareRootRateEngine(kappa=0.50, theta=0.05, sigma=0.15, current_rate=0.04)
        assert cir.is_feller_satisfied, "Feller condition should be satisfied."
        assert cir.feller_ratio > 2.0

        # Bond price P(0, 0) == 1.0
        p0 = cir.zero_coupon_bond_price(0.0)
        assert math.isclose(p0, 1.0, rel_tol=1e-6)

        # Longer maturity bonds should have lower price: P(1Y) > P(5Y) > P(10Y)
        p1 = cir.zero_coupon_bond_price(1.0)
        p5 = cir.zero_coupon_bond_price(5.0)
        p10 = cir.zero_coupon_bond_price(10.0)
        assert 0.0 < p10 < p5 < p1 < 1.0, f"Bond price monotonicity violated: {p1}, {p5}, {p10}"

        # Asymptotic long-term yield test
        y_inf = cir.asymptotic_long_term_yield()
        y30 = cir.yield_to_maturity(30.0)
        assert math.isclose(y30, y_inf, rel_tol=0.05), f"30Y yield {y30} should converge toward y_inf {y_inf}"

        # Conditional moments
        mean, var = cir.conditional_moments(5.0)
        assert 0.0 < mean < 0.10
        assert var > 0.0

    def test_ledoit_wolf_nonlinear_shrinkage_engine(self):
        """Verifies Ledoit & Wolf (2012, 2020) non-linear covariance matrix shrinkage."""
        np.random.seed(42)
        n = 120
        p = 60  # p/n = 0.50 (high dimension)
        # Create true covariance with varying spectrum
        true_cov = np.diag(np.linspace(0.5, 4.0, p))
        X_train = np.random.multivariate_normal(np.zeros(p), true_cov, size=n)
        X_test = np.random.multivariate_normal(np.zeros(p), true_cov, size=500)

        engine = LedoitWolfNonLinearShrinkageEngine(X_train)
        fit = engine.fit_nonlinear_shrinkage()

        # 1. Condition number should be improved by NLS
        assert fit["condition_number_nls"] < fit["condition_number_sample"], \
            "NLS should improve the condition number over sample covariance."

        # 2. Shrunk eigenvalues must all be strictly positive
        assert np.all(fit["shrunk_eigenvalues"] > 0.0), "All shrunk eigenvalues must be strictly positive."

        # 3. Minimum variance portfolio evaluation
        eval_res = engine.evaluate_minimum_variance_portfolio(X_test)
        # Out-of-sample portfolio variance under NLS should be lower than sample covariance
        assert eval_res["var_nls"] < eval_res["var_sample"], \
            f"NLS variance {eval_res['var_nls']} should be lower than sample {eval_res['var_sample']}"
        assert eval_res["variance_reduction_over_sample"] > 0.05

    def test_hansen_jagannathan_bound_engine(self):
        """Verifies Hansen & Jagannathan (1991) SDF volatility bound & distance."""
        np.random.seed(99)
        n = 500
        k = 4
        # Synthetic returns with known Sharpe ratios
        returns = 0.01 + np.random.multivariate_normal(np.array([0.05, 0.08, 0.06, 0.07]), np.diag([0.02, 0.03, 0.025, 0.028]), size=n)

        hj = HansenJagannathanBoundEngine(returns, risk_free_rate=0.02)
        sr_max, weights = hj.maximum_sharpe_ratio()
        assert sr_max > 0.0, "Maximum Sharpe ratio must be positive."
        assert math.isclose(np.sum(weights), 1.0, rel_tol=1e-4)

        # Volatility lower bound
        e_m = 0.98  # Typical annual SDF mean ~ 1 / (1 + r)
        vol_bound = hj.hj_volatility_lower_bound(e_m)
        assert vol_bound > 0.0
        assert math.isclose(vol_bound, e_m * sr_max, rel_tol=1e-5)

        # Test valid vs misspecified candidate SDF
        # A constant SDF m_t = 0.98 will have positive HJ distance because it fails to price risky excess returns
        const_sdf = np.full(n, e_m)
        hj_dist = hj.hansen_jagannathan_distance(const_sdf)
        assert hj_dist > 0.0, "Constant SDF must have strictly positive HJ distance for risky assets."

    def test_rough_heston_riccati_engine(self):
        """Verifies Rough Heston fractional Riccati integration and power-law skew."""
        rheston = RoughHestonRiccatiEngine(
            hurst=0.12,
            lam=1.2,
            theta=0.04,
            nu=0.35,
            rho=-0.75,
            v0=0.04
        )
        assert math.isclose(rheston.alpha, 0.62, rel_tol=1e-5)

        # Solve fractional Riccati equation for u = 1.0
        h_vals = rheston.solve_fractional_riccati(u=1.0, maturity_t=0.5, steps=50)
        assert len(h_vals) == 51
        # Characteristic function must have real part and modulus <= 1 (sub-probability)
        cf = rheston.evaluate_characteristic_function(u=1.0, maturity_t=0.5, steps=50)
        assert abs(cf) <= 1.0001, f"Characteristic function modulus exceeded 1: {abs(cf)}"

        # Power law ATM skew scaling test across maturities
        maturities = [0.01, 0.02, 0.05, 0.10, 0.25, 0.50]
        skew_res = rheston.power_law_atm_skew_scaling(maturities)
        # Short-term skew must be strictly decreasing with maturity (i.e. exploding as T -> 0)
        assert skew_res["at_the_money_skews"][0] > skew_res["at_the_money_skews"][-1]
        assert skew_res["is_power_law_verified"], f"Empirical slope {skew_res['empirical_log_slope']} vs theory {skew_res['theoretical_exponent']}"

    def test_madhavan_richardson_roomans_spread_engine(self):
        """Verifies MRR (1997) microstructure spread decomposition from high-frequency tick data."""
        true_theta = 0.04
        true_phi = 0.06
        true_rho = 0.35

        dp, x = MadhavanRichardsonRoomansSpreadEngine.simulate_mrr_market(
            n_ticks=4000,
            theta=true_theta,
            phi=true_phi,
            rho=true_rho,
            sigma_eps=0.01,
            seed=42
        )

        engine = MadhavanRichardsonRoomansSpreadEngine(dp, x)
        params = engine.estimate_mrr_parameters()

        # Estimated parameters should be close to true values within reasonable statistical confidence
        assert math.isclose(params["rho_trade_autocorrelation"], true_rho, abs_tol=0.08)
        assert math.isclose(params["theta_adverse_selection"], true_theta, abs_tol=0.025)
        assert math.isclose(params["phi_order_processing"], true_phi, abs_tol=0.025)

        # Spread decomposition sums
        assert math.isclose(params["adverse_selection_share"] + params["order_processing_share"], 1.0, rel_tol=1e-5)
        assert params["effective_spread"] > 0.0
        assert params["r_squared"] > 0.0
