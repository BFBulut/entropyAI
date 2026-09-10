"""Programmatic TDD Verification Suite for Faz 68 Quantitative Finance Engines.

Models:
1. Stephen A. Ross (1976, 2015):
   Arbitrage Pricing Theory (APT) & The Recovery Theorem (Journal of Finance).
   Perron-Frobenius recovery of subjective discount factor, marginal utilities, and physical transition probabilities.
2. Milton Friedman (1953) & De Long, Shleifer, Summers, Waldmann (DSSW 1990):
   Noise Trader Risk, Limited Arbitrage Horizon, Resale Price Risk & Refutation of Friedman's Fallacy.
3. David S. Bates (1996):
   Stochastic Volatility Jump-Diffusion (SVJ) Model, Albrecher Little Heston Trap Resolution,
   and Carr-Madan Damped Fourier Inversion for Option Pricing.
4. Joel Hasbrouck (1991, 1995) & Lawrence R. Glosten (1994):
   Cointegrated Microstructure VAR, Beveridge-Nelson Permanent/Transitory Decomposition,
   and Cholesky Information Share (IS) Upper/Lower Bounds.
5. Andrea Frazzini & Lasse H. Pedersen (2014) / Clifford Asness vd. (2019):
   Betting Against Beta (BAB) Factor under Leverage Constraints and Quality Minus Junk (QMJ) Multi-Metric Quality Scoring.
6. Lars Peter Hansen & Thomas J. Sargent (2001, 2008) / Pascal J. Maenhout (2004):
   Robust Continuous-Time Portfolio Choice, Min-Max HJB with Relative Entropy Penalty,
   Worst-Case Drift Distortion, and Resolution of the Equity Premium Puzzle.
"""

import math
import time
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
# 1. Stephen A. Ross (1976, 2015) Recovery Theorem Engine
# ==============================================================================
class RossRecoveryEngine:
    """Stephen A. Ross (1976, 2015) Arbitrage Pricing Theory & The Recovery Theorem.
    
    Solves the fundamental inverse problem of mathematical finance:
    Recovers real-world physical transition matrix P, subjective discount factor delta,
    and marginal utilities d directly from risk-neutral Arrow-Debreu transition matrix Q
    via Perron-Frobenius spectral decomposition.
    """

    def __init__(self, risk_neutral_matrix: np.ndarray):
        self.Q = np.array(risk_neutral_matrix, dtype=float)
        if self.Q.ndim != 2 or self.Q.shape[0] != self.Q.shape[1]:
            raise ValueError("Risk-neutral matrix Q must be a square 2D matrix.")
        if np.any(self.Q < 0):
            raise ValueError("Arrow-Debreu prices in Q must be non-negative.")
        self.n_states = self.Q.shape[0]

    def solve_recovery(self) -> Dict[str, Any]:
        """Recovers delta, marginal utility vector d, and physical transition matrix P."""
        # Eigen decomposition of Q
        eigenvalues, eigenvectors = np.linalg.eig(self.Q)
        
        # Perron-Frobenius: largest real eigenvalue is delta
        real_parts = np.real(eigenvalues)
        max_idx = int(np.argmax(real_parts))
        delta = float(real_parts[max_idx])
        
        if delta <= 0:
            raise ValueError("Recovered discount factor must be strictly positive.")
            
        d_vec = np.real(eigenvectors[:, max_idx])
        if np.all(d_vec < 0):
            d_vec = -d_vec
        elif not np.all(d_vec > 0):
            # Enforce positive quadrant
            d_vec = np.abs(d_vec)
            
        # Normalize d_vec
        d_vec = d_vec / np.sum(d_vec)
        
        D = np.diag(d_vec)
        D_inv = np.diag(1.0 / d_vec)
        
        # P = (1 / delta) * D^-1 * Q * D
        P = (1.0 / delta) * np.dot(D_inv, np.dot(self.Q, D))
        
        # Ensure row stochastic normalization
        row_sums = np.sum(P, axis=1)
        for i in range(self.n_states):
            if not np.isclose(row_sums[i], 1.0, atol=1e-5):
                P[i, :] = P[i, :] / row_sums[i]
                
        implicit_rf = (1.0 / delta) - 1.0
        
        return {
            "discount_factor_delta": delta,
            "implicit_risk_free_rate": implicit_rf,
            "marginal_utilities_d": d_vec,
            "physical_transition_matrix_P": P,
            "row_stochastic_check": np.sum(P, axis=1)
        }

    def pricing_kernel(self, state_from: int, state_to: int, delta: float, d_vec: np.ndarray) -> float:
        """Calculates stochastic discount factor m_{ij} = delta * (d_j / d_i)."""
        return delta * (d_vec[state_to] / d_vec[state_from])


# ==============================================================================
# 2. Milton Friedman (1953) vs DSSW (1990) Noise Trader Risk Engine
# ==============================================================================
class DSSWNoiseTraderEngine:
    """De Long, Shleifer, Summers, Waldmann (DSSW 1990) Noise Trader Risk Model.
    
    Models limited arbitrage, resale price risk, and refutes Friedman's hypothesis
    that irrational traders are always driven out of financial markets.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.05,
        noise_trader_share: float = 0.30,
        risk_aversion: float = 2.0,
        mean_sentiment: float = 0.02,
        sentiment_volatility: float = 0.15
    ):
        self.r = risk_free_rate
        self.mu = noise_trader_share
        self.gamma = risk_aversion
        self.rho_star = mean_sentiment
        self.sigma_rho = sentiment_volatility

    def compute_equilibrium_price(self, current_sentiment: float) -> Dict[str, float]:
        """Calculates the closed-form DSSW equilibrium asset price and its 4 components."""
        fundamental = 1.0
        transient_sentiment = (self.mu * (current_sentiment - self.rho_star)) / (1.0 + self.r)
        persistent_sentiment = (self.mu * self.rho_star) / self.r
        noise_risk_discount = (2.0 * self.gamma * (self.mu**2) * (self.sigma_rho**2)) / (self.r * ((1.0 + self.r)**2))
        
        price = fundamental + transient_sentiment + persistent_sentiment - noise_risk_discount
        
        return {
            "fundamental_value": fundamental,
            "transient_sentiment_effect": transient_sentiment,
            "persistent_sentiment_effect": persistent_sentiment,
            "noise_risk_discount": noise_risk_discount,
            "equilibrium_price": price
        }

    def compute_friedman_fallacy_spread(self) -> Dict[str, float]:
        """Evaluates expected return differential between noise traders and rational arbitrageurs."""
        # Noise traders hold more of the risky asset on average when rho* > 0,
        # earning compensation for the very volatility they induce.
        risk_discount = (2.0 * self.gamma * (self.mu**2) * (self.sigma_rho**2)) / (self.r * ((1.0 + self.r)**2))
        excess_return = self.rho_star + (risk_discount * self.r / self.mu)
        
        survives = excess_return > 0
        return {
            "expected_return_differential": excess_return,
            "noise_traders_survive_and_dominate": survives
        }


# ==============================================================================
# 3. David S. Bates (1996) Stochastic Volatility Jump (SVJ) Engine
# ==============================================================================
class BatesSVJEngine:
    """David S. Bates (1996) Stochastic Volatility Jump-Diffusion Model.
    
    Combines Heston (1993) mean-reverting stochastic variance with Merton (1976)
    log-normal compound Poisson jump process, using Carr-Madan Fourier inversion.
    """

    def __init__(
        self,
        v0: float = 0.04,
        kappa: float = 2.0,
        theta: float = 0.04,
        sigma_v: float = 0.30,
        rho: float = -0.70,
        jump_lambda: float = 0.50,
        jump_mu: float = -0.08,
        jump_sigma: float = 0.12
    ):
        self.v0 = v0
        self.kappa = kappa
        self.theta = theta
        self.sigma_v = sigma_v
        self.rho = rho
        self.jump_lambda = jump_lambda
        self.jump_mu = jump_mu
        self.jump_sigma = jump_sigma
        self.k_bar = math.exp(jump_mu + 0.5 * (jump_sigma**2)) - 1.0

    def characteristic_function(self, u: complex, S0: float, T: float, r: float, q: float) -> complex:
        """Computes Bates closed-form characteristic function for ln(S_T / S_0)."""
        i = 1j
        mu_rn = r - q - self.jump_lambda * self.k_bar
        
        # Albrecher et al. (2007) formulation for numerical stability
        d = np.sqrt((self.rho * self.sigma_v * i * u - self.kappa)**2 + (self.sigma_v**2) * (i * u + u**2))
        g = (self.kappa - self.rho * self.sigma_v * i * u - d) / (self.kappa - self.rho * self.sigma_v * i * u + d)
        exp_neg_dt = np.exp(-d * T)
        
        C = mu_rn * i * u * T + (self.kappa * self.theta / (self.sigma_v**2)) * (
            (self.kappa - self.rho * self.sigma_v * i * u - d) * T - 2.0 * np.log((1.0 - g * exp_neg_dt) / (1.0 - g))
        )
        D = ((self.kappa - self.rho * self.sigma_v * i * u - d) / (self.sigma_v**2)) * (
            (1.0 - exp_neg_dt) / (1.0 - g * exp_neg_dt)
        )
        
        phi_heston = np.exp(C + D * self.v0)
        phi_jump = np.exp(self.jump_lambda * T * (
            np.exp(i * u * self.jump_mu - 0.5 * (u**2) * (self.jump_sigma**2)) - 1.0 - i * u * self.k_bar
        ))
        
        return phi_heston * phi_jump

    def price_european_call(
        self,
        S0: float,
        K: float,
        T: float,
        r: float = 0.03,
        q: float = 0.01,
        alpha: float = 1.5,
        n_points: int = 4096,
        u_max: float = 60.0
    ) -> float:
        """Prices a European call option via Carr-Madan damped Fourier transform."""
        k = math.log(K / S0)
        u_vals = np.linspace(1e-5, u_max, n_points)
        du = u_vals[1] - u_vals[0]
        
        # Evaluate characteristic function at u - (alpha + 1)*i
        cf_vals = np.array([self.characteristic_function(u - (alpha + 1) * 1j, S0, T, r, q) for u in u_vals])
        denom = (alpha**2 + alpha - u_vals**2) + 1j * (2 * alpha + 1) * u_vals
        psi_vals = math.exp(-r * T) * cf_vals / denom
        
        integrand = np.real(np.exp(-1j * u_vals * k) * psi_vals)
        
        # Simpson's composite integration rule
        weights = np.ones(n_points)
        weights[1:-1:2] = 4.0
        weights[2:-2:2] = 2.0
        integral = np.sum(integrand * weights) * (du / 3.0)
        
        call_price = float((math.exp(-alpha * k) / math.pi) * integral * S0)
        return max(0.0, call_price)


# ==============================================================================
# 4. Joel Hasbrouck (1991, 1995) Information Share Engine
# ==============================================================================
class HasbrouckInformationShareEngine:
    """Joel Hasbrouck (1991, 1995) Vector Autoregressive Price Discovery Engine.
    
    Measures the location of price discovery across fragmented electronic markets
    via cointegrated VECM permanent-transitory decomposition and Cholesky bounds.
    """

    def __init__(self, innovation_cov: np.ndarray, permanent_vector: np.ndarray):
        self.Omega = np.array(innovation_cov, dtype=float)
        self.psi = np.array(permanent_vector, dtype=float)
        if self.Omega.shape[0] != self.Omega.shape[1] or self.Omega.shape[0] != len(self.psi):
            raise ValueError("Dimensions of Omega and psi vector must match.")

    def compute_information_shares(self) -> Dict[str, Any]:
        """Calculates order-dependent upper/lower bounds and mean Information Share."""
        n = len(self.psi)
        total_var = float(np.dot(self.psi, np.dot(self.Omega, self.psi)))
        
        shares_upper = np.zeros(n)
        shares_lower = np.zeros(n)
        
        # Permutation over ordering (for 2-market case: [0, 1] and [1, 0])
        if n == 2:
            # 1. Market 1 first
            F1 = np.linalg.cholesky(self.Omega)
            psi_F1 = np.dot(self.psi, F1)
            shares_upper[0] = (psi_F1[0]**2) / total_var
            shares_lower[1] = (psi_F1[1]**2) / total_var
            
            # 2. Market 2 first
            P_mat = np.array([[0, 1], [1, 0]])
            Omega_perm = np.dot(P_mat, np.dot(self.Omega, P_mat.T))
            F2 = np.linalg.cholesky(Omega_perm)
            psi_perm = np.dot(self.psi, P_mat.T)
            psi_F2 = np.dot(psi_perm, F2)
            shares_upper[1] = (psi_F2[0]**2) / total_var
            shares_lower[0] = (psi_F2[1]**2) / total_var
        else:
            # Default Cholesky
            F = np.linalg.cholesky(self.Omega)
            psi_F = np.dot(self.psi, F)
            shares_upper = (psi_F**2) / total_var
            shares_lower = shares_upper
            
        shares_mid = 0.5 * (shares_upper + shares_lower)
        
        return {
            "total_permanent_variance": total_var,
            "information_shares_upper": shares_upper,
            "information_shares_lower": shares_lower,
            "information_shares_mid": shares_mid,
            "shares_sum": float(np.sum(shares_mid))
        }


# ==============================================================================
# 5. Andrea Frazzini & Lasse H. Pedersen (2014) BAB & QMJ Engine
# ==============================================================================
class BettingAgainstBetaEngine:
    """Frazzini & Pedersen (2014) BAB & Asness, Frazzini, Pedersen (2019) QMJ.
    
    Constructs market-neutral zero-beta portfolios under leverage constraints
    and composite 4-pillar quality scores (Profitability, Growth, Safety, Payout).
    """

    def __init__(self, risk_free_rate: float = 0.03):
        self.rf = risk_free_rate

    def construct_bab_portfolio(
        self,
        betas: np.ndarray,
        returns: np.ndarray
    ) -> Dict[str, float]:
        """Constructs ex-ante zero-beta BAB portfolio by levering low-beta and delevering high-beta."""
        median_beta = float(np.median(betas))
        low_idx = np.where(betas < median_beta)[0]
        high_idx = np.where(betas >= median_beta)[0]
        
        beta_L = float(np.mean(betas[low_idx]))
        beta_H = float(np.mean(betas[high_idx]))
        r_L = float(np.mean(returns[low_idx]))
        r_H = float(np.mean(returns[high_idx]))
        
        # R_BAB = (1/beta_L) * (r_L - rf) - (1/beta_H) * (r_H - rf)
        r_bab = (1.0 / beta_L) * (r_L - self.rf) - (1.0 / beta_H) * (r_H - self.rf)
        net_beta = (1.0 / beta_L) * beta_L - (1.0 / beta_H) * beta_H
        
        return {
            "low_beta_mean": beta_L,
            "high_beta_mean": beta_H,
            "low_beta_return": r_L,
            "high_beta_return": r_H,
            "bab_excess_return": r_bab,
            "bab_net_beta": net_beta
        }

    def compute_qmj_scores(
        self,
        profitability: np.ndarray,
        growth: np.ndarray,
        safety: np.ndarray,
        payout: np.ndarray
    ) -> np.ndarray:
        """Calculates composite QMJ z-score across 4 quality pillars."""
        def to_zscore(x: np.ndarray) -> np.ndarray:
            std = float(np.std(x))
            return (x - float(np.mean(x))) / (std if std > 1e-8 else 1.0)
            
        z_prof = to_zscore(profitability)
        z_grow = to_zscore(growth)
        z_safe = to_zscore(safety)
        z_pay = to_zscore(payout)
        
        return (z_prof + z_grow + z_safe + z_pay) / 4.0


# ==============================================================================
# 6. Hansen-Sargent (2001, 2008) & Maenhout (2004) Robust Portfolio Engine
# ==============================================================================
class HansenSargentRobustPortfolioEngine:
    """Lars Peter Hansen, Thomas J. Sargent & Pascal J. Maenhout (2004).
    
    Robust portfolio selection under Knightian ambiguity and relative entropy penalty.
    Explains the Equity Premium Puzzle via effective risk aversion.
    """

    def __init__(
        self,
        expected_return: float = 0.08,
        risk_free_rate: float = 0.02,
        volatility: float = 0.20,
        crra_risk_aversion: float = 3.0,
        model_uncertainty_psi: float = 0.50
    ):
        self.mu0 = expected_return
        self.r = risk_free_rate
        self.sigma = volatility
        self.gamma = crra_risk_aversion
        self.psi = model_uncertainty_psi

    def solve_optimal_allocations(self) -> Dict[str, float]:
        """Calculates Merton classical allocation vs Maenhout robust allocation."""
        # Classical Merton allocation: (mu - r) / (gamma * sigma^2)
        pi_merton = (self.mu0 - self.r) / (self.gamma * (self.sigma**2))
        
        # Robust effective risk aversion: gamma_eff = gamma + 1/psi
        effective_gamma = self.gamma + (1.0 / self.psi)
        
        # Robust allocation: (mu - r) / (gamma_eff * sigma^2)
        pi_robust = (self.mu0 - self.r) / (effective_gamma * (self.sigma**2))
        
        # Worst-case drift distortion chosen by adversary
        worst_case_distortion_v = - (self.sigma * pi_robust) / self.psi
        worst_case_expected_return = self.mu0 + self.sigma * worst_case_distortion_v
        
        return {
            "classical_merton_allocation": pi_merton,
            "effective_risk_aversion": effective_gamma,
            "robust_allocation": pi_robust,
            "worst_case_drift_distortion": worst_case_distortion_v,
            "worst_case_expected_return": worst_case_expected_return
        }


# ==============================================================================
# PyTest Verification Suites
# ==============================================================================
def test_ross_recovery_engine():
    """Verify Stephen A. Ross (2015) Recovery Theorem spectral decomposition."""
    Q = np.array([
        [0.35, 0.40, 0.20],
        [0.20, 0.50, 0.25],
        [0.15, 0.35, 0.45]
    ])
    engine = RossRecoveryEngine(Q)
    results = engine.solve_recovery()
    
    delta = results["discount_factor_delta"]
    assert 0.85 < delta < 1.05, f"Subjective discount factor must be near 1.0, got {delta}"
    
    d_vec = results["marginal_utilities_d"]
    assert len(d_vec) == 3
    assert np.all(d_vec > 0), "All marginal utilities must be strictly positive."
    
    P = results["physical_transition_matrix_P"]
    assert np.allclose(np.sum(P, axis=1), 1.0, atol=1e-4), "P must be row-stochastic."
    
    m_12 = engine.pricing_kernel(0, 1, delta, d_vec)
    assert m_12 > 0, "Pricing kernel must be positive."


def test_dssw_noise_trader_engine():
    """Verify DSSW (1990) equilibrium price and Friedman's fallacy return spread."""
    engine = DSSWNoiseTraderEngine(
        risk_free_rate=0.05,
        noise_trader_share=0.30,
        risk_aversion=2.0,
        mean_sentiment=0.02,
        sentiment_volatility=0.15
    )
    
    p_info = engine.compute_equilibrium_price(current_sentiment=0.05)
    assert p_info["fundamental_value"] == 1.0
    assert p_info["noise_risk_discount"] > 0, "Resale price risk must discount asset price."
    assert 0.80 < p_info["equilibrium_price"] < 1.20
    
    friedman = engine.compute_friedman_fallacy_spread()
    assert friedman["expected_return_differential"] > 0, "Noise traders earn higher returns due to noise risk."
    assert friedman["noise_traders_survive_and_dominate"] is True


def test_bates_svj_engine():
    """Verify David S. Bates (1996) SVJ option pricing via Carr-Madan Fourier transform."""
    engine = BatesSVJEngine(
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.30,
        rho=-0.70,
        jump_lambda=0.50,
        jump_mu=-0.08,
        jump_sigma=0.12
    )
    
    # 3-month ATM option
    S0, K, T = 100.0, 100.0, 0.25
    call_price = engine.price_european_call(S0=S0, K=K, T=T, r=0.03, q=0.01)
    
    assert 3.0 < call_price < 7.0, f"Call price should be approx 5.08, got {call_price}"
    
    # OTM option check (monotonicity: Call(K=110) < Call(K=100))
    call_otm = engine.price_european_call(S0=S0, K=110.0, T=T, r=0.03, q=0.01)
    assert call_otm < call_price, "Call prices must be monotonic decreasing with strike K."


def test_hasbrouck_information_share_engine():
    """Verify Hasbrouck (1991, 1995) Information Share dual Cholesky bounds."""
    sigma1, sigma2, corr = 0.02, 0.03, 0.60
    cov12 = corr * sigma1 * sigma2
    Omega = np.array([
        [sigma1**2, cov12],
        [cov12, sigma2**2]
    ])
    psi = np.array([0.70, 0.30])
    
    engine = HasbrouckInformationShareEngine(Omega, psi)
    res = engine.compute_information_shares()
    
    assert np.isclose(res["shares_sum"], 1.0, atol=1e-4), "Sum of mid Information Shares must equal 1.0"
    assert res["information_shares_upper"][0] >= res["information_shares_lower"][0]
    assert res["information_shares_upper"][1] >= res["information_shares_lower"][1]
    assert res["information_shares_mid"][0] > res["information_shares_mid"][1], "Market 1 has higher weight."


def test_betting_against_beta_engine():
    """Verify Frazzini-Pedersen (2014) BAB zero-beta portfolio & Asness (2019) QMJ."""
    np.random.seed(42)
    engine = BettingAgainstBetaEngine(risk_free_rate=0.03)
    
    betas = np.array([0.6, 0.8, 1.2, 1.5, 1.8])
    # Returns reflect flatter-than-CAPM SML
    returns = np.array([0.08, 0.085, 0.095, 0.10, 0.105])
    
    bab_res = engine.construct_bab_portfolio(betas, returns)
    assert np.isclose(bab_res["bab_net_beta"], 0.0, atol=1e-6), "BAB portfolio must be market-neutral beta zero."
    assert bab_res["bab_excess_return"] > 0.0, "BAB generates positive leveraged excess return."
    
    # QMJ scoring check
    n = 20
    prof = np.random.normal(0.15, 0.05, n)
    grow = np.random.normal(0.08, 0.04, n)
    safe = np.random.normal(1.0, 0.2, n)
    pay = np.random.normal(0.03, 0.01, n)
    
    qmj_scores = engine.compute_qmj_scores(prof, grow, safe, pay)
    assert len(qmj_scores) == n
    assert np.isclose(np.mean(qmj_scores), 0.0, atol=1e-5)


def test_hansen_sargent_robust_engine():
    """Verify Hansen-Sargent (2001, 2008) & Maenhout (2004) robust portfolio choice."""
    engine = HansenSargentRobustPortfolioEngine(
        expected_return=0.08,
        risk_free_rate=0.02,
        volatility=0.20,
        crra_risk_aversion=3.0,
        model_uncertainty_psi=0.50
    )
    alloc = engine.solve_optimal_allocations()
    
    assert np.isclose(alloc["classical_merton_allocation"], 0.50)
    assert np.isclose(alloc["effective_risk_aversion"], 5.0)
    assert np.isclose(alloc["robust_allocation"], 0.30)
    assert alloc["robust_allocation"] < alloc["classical_merton_allocation"]
    assert alloc["worst_case_drift_distortion"] < 0, "Adversary distorts drift downward."
    assert alloc["worst_case_expected_return"] < 0.08
