"""Programmatic TDD Verification Suite for Faz 43 Quantitative Finance Engines.

Models:
1. Epstein-Zin (1989) & Bansal-Yaron (2004) Long-Run Risk (LRR) Macro-Finance Engine
2. Campbell-Cochrane (1999) External Habit Formation & Countercyclical Risk Premia
3. Klibanoff, Marinacci & Mukerji (KMM 2005) Smooth Ambiguity / Knightian Uncertainty Portfolio Engine
4. Almgren (2003) & Gatheral (2010) Non-Linear Power-Law Market Impact & Transient Resilient Execution
5. Brigo & Mercurio (2001) Two-Factor Hull-White (G2++) Short-Rate & Multi-Factor Swaption Engine
6. Ethena USDe Delta-Neutral Synthetic Dollar Mechanics & Dynamic Reserve Solvency Fragility Engine
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
# 1. Epstein-Zin (1989) & Bansal-Yaron (2004) Long-Run Risk (LRR) Engine
# ==============================================================================
class BansalYaronLRR:
    """
    Epstein & Zin (1989) recursive preferences with Bansal & Yaron (2004) Long-Run Risk.
    Decouples relative risk aversion (gamma) from elasticity of intertemporal substitution (psi).
    State variables:
      - x_t: persistent expected consumption growth
      - sigma_t^2: stochastic consumption variance
    """
    def __init__(self,
                 mu: float = 0.018,         # Mean consumption growth (annualized, 1.8%)
                 rho: float = 0.979,        # Persistence of long-run growth component
                 phi_e: float = 0.044,      # Volatility scale of long-run growth shock
                 sigma_bar: float = 0.0078, # Baseline consumption volatility
                 nu: float = 0.987,         # Persistence of consumption volatility
                 sigma_w: float = 0.0000023,# Vol-of-vol
                 gamma: float = 10.0,       # Risk aversion
                 psi: float = 1.5,          # Elasticity of intertemporal substitution (EIS)
                 beta: float = 0.998,       # Subjective discount factor
                 kappa_1: float = 0.997     # Campbell-Shiller linearization parameter
                 ):
        self.mu = mu
        self.rho = rho
        self.phi_e = phi_e
        self.sigma_bar = sigma_bar
        self.sigma_bar_sq = sigma_bar ** 2
        self.nu = nu
        self.sigma_w = sigma_w
        self.gamma = gamma
        self.psi = psi
        self.beta = beta
        self.kappa_1 = kappa_1

        if abs(1.0 - 1.0 / self.psi) < 1e-7:
            raise ValueError("psi cannot be exactly 1.0 in this parameterization")
        self.theta = (1.0 - self.gamma) / (1.0 - 1.0 / self.psi)

    def solve_log_price_consumption_coefficients(self) -> Tuple[float, float]:
        """
        Solves for A1 (loading on x_t) and A2 (loading on sigma_t^2)
        in log wealth-consumption ratio: z_t = A0 + A1 * x_t + A2 * sigma_t^2.
        """
        A1 = (1.0 - 1.0 / self.psi) / (1.0 - self.kappa_1 * self.rho)
        numerator = 0.5 * ((1.0 - self.gamma) + (self.kappa_1 * A1 * self.phi_e) ** 2)
        denominator = 1.0 - self.kappa_1 * self.nu
        A2 = numerator / denominator
        return A1, A2

    def compute_equity_risk_premium(self, x_t: float = 0.0, sigma_t_sq: Optional[float] = None) -> Dict[str, float]:
        """
        Decomposes equity risk premium into short-run consumption risk,
        long-run growth risk, and economic uncertainty (volatility) risk.
        """
        if sigma_t_sq is None:
            sigma_t_sq = self.sigma_bar_sq

        A1, A2 = self.solve_log_price_consumption_coefficients()
        lambda_c = self.gamma
        lambda_x = (1.0 - self.theta) * self.kappa_1 * A1 * self.phi_e
        beta_c = 1.0
        beta_x = self.kappa_1 * A1 * self.phi_e

        prem_short_run = lambda_c * beta_c * sigma_t_sq
        prem_long_run = lambda_x * beta_x * sigma_t_sq
        total_premium = prem_short_run + prem_long_run

        return {
            "theta": self.theta,
            "A1_loading": A1,
            "A2_loading": A2,
            "lambda_consumption": lambda_c,
            "lambda_long_run": lambda_x,
            "premium_short_run_pct": prem_short_run * 100.0,
            "premium_long_run_pct": prem_long_run * 100.0,
            "total_risk_premium_pct": total_premium * 100.0
        }


# ==============================================================================
# 2. Campbell-Cochrane (1999) External Habit Formation Engine
# ==============================================================================
class CampbellCochraneHabit:
    """
    Campbell & Cochrane (1999) Consumption-Based Asset Pricing with Habit Formation.
    Surplus consumption ratio S_t = (C_t - X_t) / C_t, log surplus s_t = ln(S_t).
    """
    def __init__(self,
                 g: float = 0.0189,
                 sigma: float = 0.015,
                 phi: float = 0.97,
                 gamma: float = 2.0,
                 delta: float = 0.95
                 ):
        self.g = g
        self.sigma = sigma
        self.phi = phi
        self.gamma = gamma
        self.delta = delta

        self.S_bar = self.sigma * math.sqrt(self.gamma / (1.0 - self.phi))
        self.s_bar = math.log(self.S_bar)
        self.s_max = self.s_bar + 0.5 * (1.0 - self.S_bar ** 2)
        self.S_max = math.exp(self.s_max)

    def sensitivity_function(self, s: float) -> float:
        if s >= self.s_max:
            return 0.0
        val = 1.0 - 2.0 * (s - self.s_bar)
        if val < 0.0:
            return 0.0
        return (1.0 / self.S_bar) * math.sqrt(val) - 1.0

    def local_risk_aversion(self, s: float) -> float:
        return self.gamma * math.exp(-s)

    def conditional_sharpe_ratio(self, s: float) -> float:
        lam = self.sensitivity_function(s)
        return self.gamma * self.sigma * (1.0 + lam)

    def risk_free_rate(self) -> float:
        return -math.log(self.delta) + self.gamma * self.g - 0.5 * self.gamma * (1.0 - self.phi)


# ==============================================================================
# 3. Klibanoff, Marinacci & Mukerji (KMM 2005) Smooth Ambiguity Portfolio Engine
# ==============================================================================
class KMMAmbiguityPortfolio:
    """
    Klibanoff, Marinacci & Mukerji (2005) Smooth Ambiguity / Knightian Uncertainty Engine.
    """
    def __init__(self,
                 r_f: float = 0.03,
                 mu_bar: float = 0.08,
                 tau: float = 0.03,
                 sigma: float = 0.16,
                 gamma: float = 3.0,
                 alpha_amb: float = 5.0
                 ):
        self.r_f = r_f
        self.mu_bar = mu_bar
        self.tau = tau
        self.tau_sq = tau ** 2
        self.sigma = sigma
        self.sigma_sq = sigma ** 2
        self.gamma = gamma
        self.alpha_amb = alpha_amb

    def optimal_risky_weight(self, ambiguity_on: bool = True) -> float:
        excess_return = self.mu_bar - self.r_f
        if not ambiguity_on:
            denom = self.gamma * self.sigma_sq
        else:
            denom = self.gamma * self.sigma_sq + self.alpha_amb * self.tau_sq
        return excess_return / denom

    def ambiguity_discount_ratio(self) -> float:
        amb_term = self.alpha_amb * self.tau_sq
        risk_term = self.gamma * self.sigma_sq
        return amb_term / (risk_term + amb_term)

    def required_risk_premium(self, target_weight: float = 0.5) -> float:
        total_aversion_denom = self.gamma * self.sigma_sq + self.alpha_amb * self.tau_sq
        return target_weight * total_aversion_denom


# ==============================================================================
# 4. Almgren (2003) & Gatheral (2010) Non-Linear Power-Law Market Impact Engine
# ==============================================================================
class NonLinearPowerLawExecution:
    """
    Almgren (2003) & Gatheral (2010) Transient Non-Linear Execution Engine.
    """
    def __init__(self,
                 total_shares: float = 100000.0,
                 time_horizon: float = 1.0,
                 n_steps: int = 100,
                 s0: float = 100.0,
                 sigma: float = 0.20,
                 eta: float = 0.0005,
                 alpha: float = 0.5,
                 gamma_0: float = 0.0002,
                 tau_0: float = 0.05,
                 beta: float = 0.6,
                 risk_aversion: float = 1e-6
                 ):
        self.total_shares = total_shares
        self.T = time_horizon
        self.n_steps = n_steps
        self.dt = time_horizon / n_steps
        self.s0 = s0
        self.sigma = sigma
        self.eta = eta
        self.alpha = alpha
        self.gamma_0 = gamma_0
        self.tau_0 = tau_0
        self.beta = beta
        self.risk_aversion = risk_aversion

    def kernel_decay(self, t: float) -> float:
        return self.gamma_0 / ((t + self.tau_0) ** self.beta)

    def twap_schedule(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        t_grid = np.linspace(0, self.T, self.n_steps + 1)
        v_const = self.total_shares / self.T
        v_traj = np.full(self.n_steps, v_const)
        q_traj = self.total_shares * (1.0 - t_grid / self.T)
        return t_grid, q_traj, v_traj

    def optimal_nonlinear_schedule(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        t_grid = np.linspace(0, self.T, self.n_steps + 1)
        q = self.total_shares * (1.0 - t_grid / self.T)
        n_iters = 80
        lr = 0.05
        for _ in range(n_iters):
            v = (q[:-1] - q[1:]) / self.dt
            grad = np.zeros(self.n_steps - 1)
            for k in range(self.n_steps - 1):
                vk = max(1e-6, v[k])
                vk1 = max(1e-6, v[k+1])
                d_impact = (1.0 + self.alpha) * self.eta * (vk1 ** self.alpha - vk ** self.alpha)
                d_risk = self.risk_aversion * (self.sigma ** 2) * q[k+1] * self.dt
                grad[k] = d_impact + d_risk
            q[1:-1] -= lr * grad * 1e4
            for k in range(1, self.n_steps):
                q[k] = min(q[k-1], max(0.0, q[k]))
            q[-1] = 0.0

        v = (q[:-1] - q[1:]) / self.dt
        return t_grid, q, v

    def calculate_execution_shortfall(self, q: np.ndarray, v: np.ndarray) -> Dict[str, float]:
        temp_cost = np.sum(self.eta * (np.abs(v) ** (1.0 + self.alpha)) * self.dt)
        variance_term = (self.sigma ** 2) * np.sum((q[:-1] ** 2) * self.dt)
        total_shortfall_cash = temp_cost
        shortfall_bps = (total_shortfall_cash / (self.total_shares * self.s0)) * 10000.0

        return {
            "total_shortfall_cash": total_shortfall_cash,
            "shortfall_bps": shortfall_bps,
            "variance_of_shortfall": variance_term,
            "half_life_time": float(np.interp(self.total_shares * 0.5, q[::-1], np.linspace(0, self.T, len(q))[::-1]))
        }


# ==============================================================================
# 5. Brigo & Mercurio (2001) Two-Factor Hull-White (G2++) Short-Rate Engine
# ==============================================================================
class G2ppTwoFactorHullWhite:
    """
    Brigo & Mercurio (2001/2006) Two-Factor Additive Gaussian Short Rate Model (G2++).
    """
    def __init__(self,
                 a: float = 0.05,
                 b: float = 0.10,
                 sigma: float = 0.012,
                 eta: float = 0.008,
                 rho: float = -0.65,
                 r0: float = 0.035
                 ):
        if a <= 0 or b <= 0:
            raise ValueError("Mean reversion speeds a and b must be positive")
        if abs(a - b) < 1e-6:
            raise ValueError("a and b must be distinct in standard G2++ form")
        self.a = a
        self.b = b
        self.sigma = sigma
        self.eta = eta
        self.rho = rho
        self.r0 = r0

    def variance_V(self, t: float, T: float) -> float:
        tau = T - t
        exp_a = math.exp(-self.a * tau)
        exp_b = math.exp(-self.b * tau)
        exp_2a = math.exp(-2.0 * self.a * tau)
        exp_2b = math.exp(-2.0 * self.b * tau)
        exp_ab = math.exp(-(self.a + self.b) * tau)

        term1 = (self.sigma ** 2 / self.a ** 2) * (tau + 2.0 / self.a * exp_a - 1.0 / (2.0 * self.a) * exp_2a - 3.0 / (2.0 * self.a))
        term2 = (self.eta ** 2 / self.b ** 2) * (tau + 2.0 / self.b * exp_b - 1.0 / (2.0 * self.b) * exp_2b - 3.0 / (2.0 * self.b))
        term3 = 2.0 * self.rho * (self.sigma * self.eta / (self.a * self.b)) * (
            tau + (exp_a - 1.0) / self.a + (exp_b - 1.0) / self.b - (exp_ab - 1.0) / (self.a + self.b)
        )
        return term1 + term2 + term3

    def zero_coupon_bond(self, t: float, T: float, x_t: float = 0.0, y_t: float = 0.0) -> float:
        if T <= t:
            return 1.0
        tau = T - t
        P_M_0_T = math.exp(-self.r0 * T)
        P_M_0_t = math.exp(-self.r0 * t) if t > 0 else 1.0
        ratio = P_M_0_T / P_M_0_t

        B_a = (1.0 - math.exp(-self.a * tau)) / self.a
        B_b = (1.0 - math.exp(-self.b * tau)) / self.b

        V_0_T = self.variance_V(0.0, T)
        V_0_t = self.variance_V(0.0, t) if t > 0 else 0.0
        V_t_T = self.variance_V(t, T)

        convexity_adj = 0.5 * (V_t_T - V_0_T + V_0_t)
        factor_loading = - (B_a * x_t + B_b * y_t)

        return ratio * math.exp(factor_loading + convexity_adj)

    def european_swaption_approx(self,
                                 T_exp: float,
                                 T_mat: float,
                                 fixed_rate: float,
                                 notional: float = 1e6,
                                 is_payer: bool = True
                                 ) -> float:
        swap_tenor = T_mat - T_exp
        freq = 1.0
        n_coupons = int(round(swap_tenor / freq))
        payment_dates = [T_exp + (i + 1) * freq for i in range(n_coupons)]

        P_exp = self.zero_coupon_bond(0.0, T_exp)
        P_mat = self.zero_coupon_bond(0.0, T_mat)
        annuity = sum(self.zero_coupon_bond(0.0, Ti) * freq for Ti in payment_dates)
        forward_swap_rate = (P_exp - P_mat) / annuity

        B_a_eff = (1.0 - math.exp(-self.a * swap_tenor)) / (self.a * swap_tenor)
        B_b_eff = (1.0 - math.exp(-self.b * swap_tenor)) / (self.b * swap_tenor)
        var_x = (self.sigma ** 2 / (2.0 * self.a)) * (1.0 - math.exp(-2.0 * self.a * T_exp))
        var_y = (self.eta ** 2 / (2.0 * self.b)) * (1.0 - math.exp(-2.0 * self.b * T_exp))
        cov_xy = self.rho * (self.sigma * self.eta / (self.a + self.b)) * (1.0 - math.exp(-(self.a + self.b) * T_exp))

        total_swap_var = (B_a_eff ** 2) * var_x + (B_b_eff ** 2) * var_y + 2.0 * B_a_eff * B_b_eff * cov_xy
        sigma_swap = math.sqrt(max(1e-8, total_swap_var / T_exp))

        d1 = (math.log(forward_swap_rate / fixed_rate) + 0.5 * (sigma_swap ** 2) * T_exp) / (sigma_swap * math.sqrt(T_exp))
        d2 = d1 - sigma_swap * math.sqrt(T_exp)

        if is_payer:
            price = notional * annuity * (forward_swap_rate * norm_cdf(d1) - fixed_rate * norm_cdf(d2))
        else:
            price = notional * annuity * (fixed_rate * norm_cdf(-d2) - forward_swap_rate * norm_cdf(-d1))

        return max(0.0, price)


# ==============================================================================
# 6. Ethena USDe Delta-Neutral Basis Fragility & Dynamic Solvency Engine
# ==============================================================================
class EthenaUSDeSolvencyEngine:
    """
    Quantitative Modeling of Ethena USDe Delta-Neutral Synthetic Dollar.
    """
    def __init__(self,
                 total_usde_supply: float = 3e9,
                 steth_staking_apy: float = 0.035,
                 perp_funding_apy: float = 0.08,
                 susde_staking_ratio: float = 0.60,
                 susde_target_yield: float = 0.12,
                 reserve_fund_usd: float = 4.5e7,
                 maintenance_margin: float = 0.05,
                 steth_initial_discount: float = 0.001
                 ):
        self.usde_supply = total_usde_supply
        self.steth_apy = steth_staking_apy
        self.funding_apy = perp_funding_apy
        self.susde_ratio = susde_staking_ratio
        self.susde_supply = total_usde_supply * susde_staking_ratio
        self.susde_target = susde_target_yield
        self.reserve_fund = reserve_fund_usd
        self.mmr = maintenance_margin
        self.discount = steth_initial_discount

    def protocol_annual_cashflow(self, custom_funding_rate: Optional[float] = None) -> Dict[str, float]:
        f_rate = self.funding_apy if custom_funding_rate is None else custom_funding_rate
        staking_rev = self.usde_supply * self.steth_apy
        funding_rev = self.usde_supply * f_rate
        gross_rev = staking_rev + funding_rev
        susde_outflow = self.susde_supply * self.susde_target
        net_cashflow = gross_rev - susde_outflow

        return {
            "staking_revenue_usd": staking_rev,
            "funding_revenue_usd": funding_rev,
            "gross_revenue_usd": gross_rev,
            "susde_yield_outflow_usd": susde_outflow,
            "net_cashflow_usd": net_cashflow,
            "net_margin_pct": (net_cashflow / self.usde_supply) * 100.0
        }

    def simulate_negative_funding_runway(self, negative_funding_apy: float = -0.15) -> Dict[str, float]:
        net_drain_rate_pct = abs(negative_funding_apy) - self.steth_apy
        if net_drain_rate_pct <= 0:
            return {
                "net_drain_rate_pct": 0.0,
                "daily_burn_usd": 0.0,
                "runway_days": float("inf"),
                "is_insolvent": False
            }

        annual_burn_usd = self.usde_supply * net_drain_rate_pct
        daily_burn_usd = annual_burn_usd / 365.0
        runway_days = self.reserve_fund / daily_burn_usd

        return {
            "net_drain_rate_pct": net_drain_rate_pct * 100.0,
            "daily_burn_usd": daily_burn_usd,
            "annual_burn_usd": annual_burn_usd,
            "runway_days": runway_days,
            "is_insolvent": runway_days < 30.0
        }

    def steth_depeg_margin_call_threshold(self, eth_price: float = 3000.0) -> Dict[str, float]:
        d_crit_1x = 1.0 - self.mmr
        initial_margin = 0.20
        d_crit_5x = initial_margin - self.mmr
        buffer_5x_pct = max(0.0, (d_crit_5x - self.discount)) * 100.0

        return {
            "critical_discount_1x_pct": d_crit_1x * 100.0,
            "critical_discount_5x_pct": d_crit_5x * 100.0,
            "current_discount_pct": self.discount * 100.0,
            "buffer_to_margin_call_5x_pct": buffer_5x_pct,
            "is_margin_call_triggered": self.discount >= d_crit_5x
        }


# ==============================================================================
# Pytest Verification Suite
# ==============================================================================

def test_bansal_yaron_long_run_risk():
    """Validates Epstein-Zin recursive preferences & Bansal-Yaron LRR analytical formulas."""
    by = BansalYaronLRR(gamma=10.0, psi=1.5, rho=0.979, phi_e=0.044)
    A1, A2 = by.solve_log_price_consumption_coefficients()

    assert A1 > 0.0, f"A1 should be positive when psi > 1, got {A1}"
    assert A1 > 10.0, f"A1 typical value is around 14-16, got {A1}"
    assert by.theta < 0.0, f"theta should be negative, got {by.theta}"
    assert A2 < 0.0, f"A2 should be negative (volatility discount), got {A2}"

    metrics = by.compute_equity_risk_premium()
    assert metrics["total_risk_premium_pct"] > 0.0
    assert metrics["premium_long_run_pct"] > 0.0
    assert metrics["premium_long_run_pct"] > metrics["premium_short_run_pct"]


def test_campbell_cochrane_habit_formation():
    """Validates Campbell-Cochrane (1999) surplus consumption and countercyclical Sharpe ratio."""
    cc = CampbellCochraneHabit(g=0.0189, sigma=0.015, phi=0.97, gamma=2.0)

    assert 0.0 < cc.S_bar < 0.5, f"S_bar should be approx 0.05-0.10, got {cc.S_bar}"

    lam_bar = cc.sensitivity_function(cc.s_bar)
    expected_lam_bar = (1.0 / cc.S_bar) - 1.0
    assert pytest.approx(lam_bar, rel=1e-5) == expected_lam_bar

    s_recession = cc.s_bar - 0.3
    s_boom = cc.s_bar + 0.1
    eta_recession = cc.local_risk_aversion(s_recession)
    eta_bar = cc.local_risk_aversion(cc.s_bar)
    eta_boom = cc.local_risk_aversion(s_boom)
    assert eta_recession > eta_bar > eta_boom

    sr_recession = cc.conditional_sharpe_ratio(s_recession)
    sr_bar = cc.conditional_sharpe_ratio(cc.s_bar)
    sr_boom = cc.conditional_sharpe_ratio(s_boom)
    assert sr_recession > sr_bar > sr_boom

    rf = cc.risk_free_rate()
    assert 0.0 < rf < 0.15


def test_kmm_smooth_ambiguity_portfolio():
    """Validates Klibanoff-Marinacci-Mukerji (2005) Knightian ambiguity asset allocation."""
    kmm = KMMAmbiguityPortfolio(r_f=0.03, mu_bar=0.08, tau=0.03, sigma=0.16, gamma=3.0, alpha_amb=6.0)

    pi_classical = kmm.optimal_risky_weight(ambiguity_on=False)
    pi_ambiguity = kmm.optimal_risky_weight(ambiguity_on=True)

    assert 0.0 < pi_ambiguity < pi_classical
    discount = kmm.ambiguity_discount_ratio()
    assert 0.0 < discount < 1.0
    assert pytest.approx(pi_ambiguity, rel=1e-4) == pi_classical * (1.0 - discount)

    req_prem_base = kmm.required_risk_premium(target_weight=0.5)
    kmm_high_amb = KMMAmbiguityPortfolio(r_f=0.03, mu_bar=0.08, tau=0.03, sigma=0.16, gamma=3.0, alpha_amb=15.0)
    req_prem_high = kmm_high_amb.required_risk_premium(target_weight=0.5)
    assert req_prem_high > req_prem_base


def test_almgren_gatheral_nonlinear_execution():
    """Validates Almgren-Gatheral square-root power-law market impact & liquidation trajectory."""
    exec_engine = NonLinearPowerLawExecution(
        total_shares=50000.0,
        time_horizon=1.0,
        n_steps=50,
        s0=100.0,
        alpha=0.5,
        eta=0.0005,
        risk_aversion=1e-5
    )

    t_grid, q_opt, v_opt = exec_engine.optimal_nonlinear_schedule()

    assert pytest.approx(q_opt[0], abs=1.0) == 50000.0
    assert pytest.approx(q_opt[-1], abs=1.0) == 0.0
    assert v_opt[0] > v_opt[-1]

    metrics = exec_engine.calculate_execution_shortfall(q_opt, v_opt)
    assert metrics["shortfall_bps"] > 0.0
    assert metrics["variance_of_shortfall"] > 0.0
    assert 0.0 < metrics["half_life_time"] < 0.5


def test_g2pp_two_factor_hull_white():
    """Validates Brigo & Mercurio (2001) G2++ analytical bond prices and European swaption formula."""
    g2 = G2ppTwoFactorHullWhite(a=0.05, b=0.12, sigma=0.015, eta=0.009, rho=-0.60, r0=0.035)

    P0 = g2.zero_coupon_bond(0.0, 0.0)
    P1 = g2.zero_coupon_bond(0.0, 1.0)
    P5 = g2.zero_coupon_bond(0.0, 5.0)
    P10 = g2.zero_coupon_bond(0.0, 10.0)

    assert pytest.approx(P0, abs=1e-5) == 1.0
    assert 1.0 > P1 > P5 > P10 > 0.0

    V_5 = g2.variance_V(0.0, 5.0)
    assert V_5 > 0.0

    payer_swaption = g2.european_swaption_approx(T_exp=1.0, T_mat=5.0, fixed_rate=0.035, notional=1e6, is_payer=True)
    receiver_swaption = g2.european_swaption_approx(T_exp=1.0, T_mat=5.0, fixed_rate=0.035, notional=1e6, is_payer=False)

    assert payer_swaption > 0.0
    assert receiver_swaption > 0.0
    payer_higher_k = g2.european_swaption_approx(T_exp=1.0, T_mat=5.0, fixed_rate=0.045, notional=1e6, is_payer=True)
    assert payer_higher_k < payer_swaption


def test_ethena_usde_solvency_and_fragility():
    """Validates Ethena USDe delta-neutral yield mechanics, reserve runway, and de-peg margin calls."""
    engine = EthenaUSDeSolvencyEngine(
        total_usde_supply=3e9,
        steth_staking_apy=0.035,
        perp_funding_apy=0.08,
        susde_staking_ratio=0.60,
        susde_target_yield=0.12,
        reserve_fund_usd=4.5e7,
        maintenance_margin=0.05,
        steth_initial_discount=0.002
    )

    cf = engine.protocol_annual_cashflow()
    assert cf["gross_revenue_usd"] > 0.0
    assert cf["net_cashflow_usd"] > 0.0
    assert cf["net_margin_pct"] > 3.0

    runway = engine.simulate_negative_funding_runway(negative_funding_apy=-0.15)
    assert pytest.approx(runway["net_drain_rate_pct"], abs=0.1) == 11.5
    assert runway["daily_burn_usd"] > 0.0
    assert 40.0 < runway["runway_days"] < 60.0
    assert not runway["is_insolvent"]

    thresholds = engine.steth_depeg_margin_call_threshold()
    assert pytest.approx(thresholds["critical_discount_5x_pct"], abs=0.1) == 15.0
    assert thresholds["buffer_to_margin_call_5x_pct"] > 14.0
    assert not thresholds["is_margin_call_triggered"]
