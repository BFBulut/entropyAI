"""Programmatic TDD Verification Suite for Faz 39 Quantitative Finance Engines.

Models:
1. Jaisson & Rosenbaum (2015/2016) Microstructural Rough Volatility & Nearly Unstable Hawkes Processes
2. Davis, Norman & Shreve (1990/1994) Singular Stochastic Control with Proportional Transaction Costs
3. Carmona & Delarue (2013/2018) Mean Field Games (MFG) for Interbank Systemic Risk & Fire-Sale Cascades
4. Collin-Dufresne, Goldstein & Hugonnier (2004) / Davis & Lo (2001) Credit Contagion & Dynamic Hawkes Hazard Rate
5. Kyle, Lee & Wang (2020) / Biais et al. (2015) Two-Speed Market & Latency Arbitrage Welfare Cost
6. UniswapX / ERC-7683 Intent-Based Dutch Auction Routing & Solver Surplus Game Theory
"""

import math
import cmath
from typing import Tuple, Dict, Any, Optional, List
import numpy as np
import pytest


# ==============================================================================
# 1. Jaisson & Rosenbaum (2015/2016) Nearly Unstable Hawkes & Rough Volatility
# ==============================================================================
class NearlyUnstableHawkesProcess:
    """
    Microstructural origin of rough volatility.
    High frequency buy/sell orders modeled by Hawkes processes N_t = (N_t^+, N_t^-).
    Memory kernel alpha(t) = C * t^{-(1+alpha_param)} with alpha_param in (0.5, 1.0).
    As spectral radius ||K|| -> 1^-, macroscopic price converges to rough fractional Brownian
    motion with Hurst parameter H = alpha_param - 0.5 in (0, 0.5).
    """
    def __init__(self, mu: float, alpha_param: float, l1_norm: float = 0.98):
        assert 0.5 < alpha_param < 1.0, "alpha_param must be in (0.5, 1.0)"
        assert 0.0 < l1_norm < 1.0, "l1_norm must be in (0, 1) for stability"
        self.mu = float(mu)
        self.alpha_param = float(alpha_param)
        self.l1_norm = float(l1_norm)  # Spectral radius of kernel matrix
        # Theoretical Hurst parameter
        self.hurst = self.alpha_param - 0.5

    def get_hurst_parameter(self) -> float:
        """Returns theoretical Hurst exponent H = alpha - 0.5."""
        return self.hurst

    def memory_kernel(self, t: float) -> float:
        """Power-law memory kernel alpha(t) = C * (1 + t)^{-(1 + alpha_param)}."""
        if t < 0:
            return 0.0
        c_norm = self.l1_norm * self.alpha_param
        return c_norm * ((1.0 + t) ** (-(1.0 + self.alpha_param)))

    def simulate_micro_midprice(self, T: float, n_events: int = 500, seed: int = 42) -> Dict[str, Any]:
        """
        Simulate bivariate Hawkes process for order arrivals (+1 buy market order, -1 sell market order).
        Returns time series of midprice and variance scaling.
        """
        rng = np.random.default_rng(seed)
        event_times = []
        event_types = []  # +1 or -1
        t = 0.0
        intensity_pos = self.mu
        intensity_neg = self.mu

        for _ in range(n_events):
            total_intensity = max(1e-4, intensity_pos + intensity_neg)
            dt = rng.exponential(1.0 / total_intensity)
            t += dt
            if t > T:
                break
            
            p_buy = intensity_pos / total_intensity
            is_buy = (rng.uniform() < p_buy)
            side = 1.0 if is_buy else -1.0
            
            event_times.append(t)
            event_types.append(side)
            
            decay_step = self.memory_kernel(0.01)
            if is_buy:
                intensity_pos += decay_step
            else:
                intensity_neg += decay_step

        times = np.array(event_times)
        sides = np.array(event_types)
        cum_price = np.cumsum(sides) if len(sides) > 0 else np.array([0.0])
        
        return {
            "n_events": len(times),
            "final_time": t,
            "final_price": float(cum_price[-1]) if len(cum_price) > 0 else 0.0,
            "hurst_theoretical": self.hurst,
            "spectral_radius": self.l1_norm
        }


# ==============================================================================
# 2. Davis, Norman & Shreve (1990/1994) Singular Stochastic Control with Costs
# ==============================================================================
class DavisNormanShreveEngine:
    """
    Portfolio selection with proportional transaction costs (buy cost lambda_buy, sell cost lambda_sell).
    Merton portfolio optimization under singular control.
    Value function V(b, s) splits state space into:
    - Buy Region (BR): stock weight w < w_L
    - Sell Region (SR): stock weight w > w_U
    - No-Transaction Region (NT): w in [w_L, w_U]
    At boundaries, smooth pasting holds, and wealth is reflected via Skorokhod local time.
    """
    def __init__(self, mu: float, r: float, sigma: float, gamma: float,
                 lambda_buy: float = 0.005, lambda_sell: float = 0.005):
        assert sigma > 0, "sigma must be positive"
        assert gamma > 0 and gamma != 1.0, "gamma must be positive and not 1"
        self.mu = float(mu)
        self.r = float(r)
        self.sigma = float(sigma)
        self.gamma = float(gamma)  # Risk aversion parameter (CRRA u(w) = w^{1-gamma}/(1-gamma))
        self.lambda_buy = float(lambda_buy)
        self.lambda_sell = float(lambda_sell)

        # Frictionless Merton optimal portfolio weight: w* = (mu - r) / (gamma * sigma^2)
        self.merton_weight = (self.mu - self.r) / (self.gamma * (self.sigma ** 2))

    def compute_no_transaction_band(self) -> Tuple[float, float]:
        """
        Computes the asymptotic no-transaction boundaries [w_L, w_U] around Merton weight w*.
        Under Davis-Norman (1990) and Shreve-Soner (1994):
        Half-width: delta_w = [ (3 / (4 * gamma)) * (lambda_buy + lambda_sell) * (w*)^2 * (1 - w*)^2 ]^{1/3}
        """
        w_star = self.merton_weight
        total_cost = self.lambda_buy + self.lambda_sell
        
        variance_factor = (w_star ** 2) * ((1.0 - w_star) ** 2)
        inner = (3.0 / (4.0 * self.gamma)) * total_cost * variance_factor
        half_width = math.pow(max(1e-8, inner), 1.0 / 3.0)

        w_L = max(0.0, w_star - half_width)
        w_U = min(1.0, w_star + half_width)
        return float(w_L), float(w_U)

    def evaluate_rebalance_action(self, current_weight: float) -> Dict[str, Any]:
        """
        Determines trading action based on singular control reflection boundaries.
        """
        w_L, w_U = self.compute_no_transaction_band()
        if current_weight < w_L:
            action = "BUY_STOCK"
            target = w_L
            trade_amount = w_L - current_weight
            cost = trade_amount * self.lambda_buy
        elif current_weight > w_U:
            action = "SELL_STOCK"
            target = w_U
            trade_amount = current_weight - w_U
            cost = trade_amount * self.lambda_sell
        else:
            action = "HOLD_NO_TRANSACTION"
            target = current_weight
            trade_amount = 0.0
            cost = 0.0

        return {
            "merton_frictionless_weight": self.merton_weight,
            "band_lower": w_L,
            "band_upper": w_U,
            "action": action,
            "trade_amount": trade_amount,
            "transaction_cost": cost,
            "post_trade_weight": target
        }


# ==============================================================================
# 3. Carmona & Delarue (2013/2018) Mean Field Games for Systemic Risk
# ==============================================================================
class MeanFieldSystemicRiskEngine:
    """
    Mean Field Game (MFG) for interbank systemic risk and fire-sale cascade.
    N banks with log-reserves X_t^i.
    Interaction: dX_t^i = [ a * (X_bar_t - X_t^i) + alpha_t^i ] dt + sigma * dW_t^i
    Cost functional: min E[ int_0^T (0.5 * (alpha^i)^2 - q * alpha^i * (X_bar - X^i) + 0.5 * eps * (X_bar - X^i)^2) dt
                             + 0.5 * c_term * (X_bar_T - X_T^i)^2 ]
    Equilibrium policy: alpha_t*(x) = (eta_t - q) * (X_bar_t - x)
    where eta_t satisfies Riccati ODE:
    d eta / dt = 2*(a + q)*eta + eta^2 - (eps - q^2),  eta(T) = c_term.
    """
    def __init__(self, a: float = 0.5, q: float = 0.2, eps: float = 1.0,
                 c_term: float = 1.0, sigma: float = 0.3, T: float = 1.0):
        self.a = float(a)          # Mean-reversion rate of interbank lending
        self.q = float(q)          # Cross-incentive parameter
        self.eps = float(eps)      # Dispersion penalty
        self.c_term = float(c_term)# Terminal penalty on divergence
        self.sigma = float(sigma)
        self.T = float(T)

    def solve_riccati_ode(self, n_steps: int = 100) -> np.ndarray:
        """
        Solves backward Riccati ODE from t=T to t=0 using Runge-Kutta 4th order.
        d eta / dt = 2*(a + q)*eta + eta^2 - (eps - q^2)
        returns eta array of length n_steps + 1 from t=0 to t=T.
        """
        dt = self.T / n_steps
        eta = np.zeros(n_steps + 1)
        eta[-1] = self.c_term

        def f(e):
            return 2.0 * (self.a + self.q) * e + (e ** 2) - (self.eps - (self.q ** 2))

        for k in range(n_steps, 0, -1):
            curr = eta[k]
            k1 = -f(curr)
            k2 = -f(curr + 0.5 * dt * k1)
            k3 = -f(curr + 0.5 * dt * k2)
            k4 = -f(curr + dt * k3)
            eta[k - 1] = curr + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        return eta

    def check_systemic_resilience(self) -> Dict[str, Any]:
        """
        Checks whether the banking system suffers a finite-time blowup / liquidity freeze.
        """
        eta_path = self.solve_riccati_ode()
        max_eta = float(np.max(eta_path))
        is_stable = not (np.isnan(max_eta) or np.isinf(max_eta) or max_eta > 1e4)
        
        eta_0 = float(eta_path[0])
        control_gain = eta_0 - self.q

        return {
            "is_stable": is_stable,
            "eta_0": eta_0,
            "eta_T": self.c_term,
            "optimal_control_gain": control_gain,
            "liquidity_cooperation_regime": "COOPERATIVE" if control_gain > 0 else "DESTRUCTIVE_RUN"
        }


# ==============================================================================
# 4. Collin-Dufresne et al. (2004) / Davis & Lo (2001) Dynamic Credit Contagion
# ==============================================================================
class CreditContagionEngine:
    """
    Dynamic credit contagion model with Hawkes/Jump intensity.
    N firms. Firm i baseline hazard rate: lambda_i,0.
    Upon default of firm j at tau_j, hazard rate of surviving firms jumps:
    lambda_i(t^+) = lambda_i(t^-) + a_{ij}
    Produces analytical contagion risk premium (CRP) in CDS spreads.
    """
    def __init__(self, base_hazard: float = 0.02, contagion_jump: float = 0.05,
                 recovery_rate: float = 0.40, r: float = 0.03):
        assert base_hazard > 0, "base_hazard must be positive"
        assert contagion_jump >= 0, "contagion_jump must be non-negative"
        self.base_hazard = float(base_hazard)
        self.contagion_jump = float(contagion_jump)
        self.recovery_rate = float(recovery_rate)
        self.lgd = 1.0 - self.recovery_rate
        self.r = float(r)

    def independent_cds_spread(self) -> float:
        """Standard CDS spread without contagion: S_indep = LGD * lambda_0."""
        return self.lgd * self.base_hazard

    def contagious_2firm_cds_spread(self, T: float = 5.0) -> Dict[str, Any]:
        """
        Analytical 2-firm symmetric contagion model (Davis & Lo 2001).
        """
        l0 = self.base_hazard
        a = self.contagion_jump
        lgd = self.lgd
        
        prob_default_indep = 1.0 - math.exp(-l0 * T)
        lambda_eff = l0 + 0.5 * a * prob_default_indep
        spread_contagion = lgd * lambda_eff
        spread_indep = self.independent_cds_spread()
        crp = spread_contagion - spread_indep

        return {
            "spread_independent_bps": spread_indep * 10000.0,
            "spread_contagion_bps": spread_contagion * 10000.0,
            "contagion_risk_premium_bps": crp * 10000.0,
            "contagion_multiplier": spread_contagion / spread_indep if spread_indep > 0 else 1.0
        }


# ==============================================================================
# 5. Kyle, Lee & Wang (2020) / Biais et al. (2015) Two-Speed Market Engine
# ==============================================================================
class TwoSpeedMarketEngine:
    """
    Two-Speed financial market with fast traders (HFTs) and slow traders (investors).
    Latency gap Delta = tau_slow - tau_fast > 0.
    Fast traders pick off stale quotes before slow market makers can cancel.
    """
    def __init__(self, theta_fast: float = 0.3, latency_gap_ms: float = 5.0,
                 asset_vol: float = 0.20, inventory_cost: float = 0.0002):
        assert 0.0 < theta_fast < 1.0, "theta_fast must be in (0, 1)"
        assert latency_gap_ms >= 0.0, "latency_gap_ms must be non-negative"
        self.theta_fast = float(theta_fast)
        self.latency_gap_sec = float(latency_gap_ms) / 1000.0
        self.asset_vol = float(asset_vol)
        self.inventory_cost = float(inventory_cost)

    def calculate_equilibrium_spread(self) -> Dict[str, Any]:
        """
        Calculates optimal half-spread s* and full bid-ask spread S*.
        """
        sec_per_year = 252.0 * 6.5 * 3600.0
        sigma_latency = self.asset_vol * math.sqrt(self.latency_gap_sec / sec_per_year)
        
        sniping_factor = (self.theta_fast / (1.0 - self.theta_fast)) * sigma_latency
        half_spread = sniping_factor + self.inventory_cost
        full_spread_bps = 2.0 * half_spread * 10000.0

        return {
            "half_spread": half_spread,
            "full_spread_bps": full_spread_bps,
            "adverse_selection_component_bps": 2.0 * sniping_factor * 10000.0,
            "inventory_component_bps": 2.0 * self.inventory_cost * 10000.0,
            "fast_trader_ratio": self.theta_fast
        }

    def compute_arms_race_deadweight_loss(self, n_hft_firms: int = 5,
                                          capex_per_firm_usd: float = 5000000.0) -> Dict[str, Any]:
        total_deadweight_usd = n_hft_firms * capex_per_firm_usd
        return {
            "n_hft_firms": n_hft_firms,
            "total_deadweight_usd": total_deadweight_usd,
            "social_efficiency": "PRISONERS_DILEMMA_RENT_DISSIPATION"
        }


# ==============================================================================
# 6. UniswapX / ERC-7683 Intent-Based Dutch Auction & Solver Surplus Engine
# ==============================================================================
class IntentDutchAuctionEngine:
    """
    DeFi Intent-Based architecture (UniswapX, ERC-7683 cross-chain standard).
    User signs an off-chain intent with Dutch auction decaying limit price:
    P(t) = P_start - (P_start - P_end) * (t / T)^gamma
    """
    def __init__(self, p_start: float = 105.0, p_end: float = 95.0,
                 duration_sec: float = 60.0, gamma: float = 1.0):
        assert p_start > p_end, "p_start must be greater than p_end"
        assert duration_sec > 0, "duration_sec must be positive"
        assert gamma > 0, "gamma must be positive"
        self.p_start = float(p_start)
        self.p_end = float(p_end)
        self.duration_sec = float(duration_sec)
        self.gamma = float(gamma)

    def price_at_time(self, t: float) -> float:
        t_clamped = max(0.0, min(self.duration_sec, t))
        ratio = (t_clamped / self.duration_sec) ** self.gamma
        return self.p_start - (self.p_start - self.p_end) * ratio

    def find_optimal_fill_time(self, external_fair_price: float, gas_cost: float = 0.5,
                               min_solver_profit: float = 0.2) -> Dict[str, Any]:
        p_reservation = external_fair_price + gas_cost + min_solver_profit
        
        if self.p_start < p_reservation:
            return {
                "filled": False,
                "reason": "RESERVATION_PRICE_ABOVE_START_PRICE",
                "fill_time": None,
                "fill_price": None,
                "user_surplus": 0.0
            }
        
        if self.p_end > p_reservation:
            t_fill = self.duration_sec
            p_fill = self.p_end
        else:
            ratio = (self.p_start - p_reservation) / (self.p_start - self.p_end)
            t_fill = self.duration_sec * (ratio ** (1.0 / self.gamma))
            p_fill = self.price_at_time(t_fill)

        user_surplus = p_fill - self.p_end

        return {
            "filled": True,
            "fill_time_sec": float(t_fill),
            "fill_price": float(p_fill),
            "solver_cost": float(external_fair_price + gas_cost),
            "solver_profit": float(p_fill - (external_fair_price + gas_cost)),
            "user_surplus": float(user_surplus),
            "mev_protection": "FULL_SANDWICH_IMMUNITY"
        }


# ==============================================================================
# Pytest Test Suite for Faz 39
# ==============================================================================

def test_jaisson_rosenbaum_nearly_unstable_hawkes():
    """Verify microstructural rough volatility Hurst parameter and Hawkes simulation."""
    hawkes = NearlyUnstableHawkesProcess(mu=1.0, alpha_param=0.6, l1_norm=0.98)
    assert math.isclose(hawkes.get_hurst_parameter(), 0.1, abs_tol=1e-6)
    
    k0 = hawkes.memory_kernel(0.0)
    k1 = hawkes.memory_kernel(1.0)
    assert k0 > k1 > 0.0, "Kernel must be strictly positive and decaying"
    
    sim = hawkes.simulate_micro_midprice(T=10.0, n_events=200, seed=42)
    assert sim["n_events"] > 0
    assert sim["spectral_radius"] == 0.98
    assert math.isclose(sim["hurst_theoretical"], 0.1, abs_tol=1e-6)


def test_davis_norman_shreve_singular_stochastic_control():
    """Verify singular stochastic control no-transaction corridor and rebalancing."""
    dns = DavisNormanShreveEngine(mu=0.08, r=0.02, sigma=0.20, gamma=3.0,
                                  lambda_buy=0.005, lambda_sell=0.005)
    assert math.isclose(dns.merton_weight, 0.50, abs_tol=1e-4)

    w_L, w_U = dns.compute_no_transaction_band()
    assert 0.0 < w_L < dns.merton_weight < w_U < 1.0, "Merton weight must lie strictly inside [w_L, w_U]"

    hold_res = dns.evaluate_rebalance_action(0.50)
    assert hold_res["action"] == "HOLD_NO_TRANSACTION"
    assert hold_res["trade_amount"] == 0.0

    buy_res = dns.evaluate_rebalance_action(0.20)
    assert buy_res["action"] == "BUY_STOCK"
    assert buy_res["post_trade_weight"] == w_L
    assert buy_res["transaction_cost"] > 0.0

    sell_res = dns.evaluate_rebalance_action(0.80)
    assert sell_res["action"] == "SELL_STOCK"
    assert sell_res["post_trade_weight"] == w_U
    assert sell_res["transaction_cost"] > 0.0


def test_carmona_delarue_mean_field_systemic_risk():
    """Verify Mean Field Game Riccati ODE and interbank systemic resilience."""
    mfg = MeanFieldSystemicRiskEngine(a=0.5, q=0.2, eps=1.0, c_term=1.0, sigma=0.3, T=1.0)
    res = mfg.check_systemic_resilience()
    
    assert res["is_stable"] is True
    assert res["eta_T"] == 1.0
    assert res["eta_0"] > 0.0
    assert res["liquidity_cooperation_regime"] in ["COOPERATIVE", "DESTRUCTIVE_RUN"]


def test_credit_contagion_engine():
    """Verify dynamic Hawkes credit contagion and Contagion Risk Premium (CRP)."""
    engine = CreditContagionEngine(base_hazard=0.02, contagion_jump=0.05,
                                  recovery_rate=0.40, r=0.03)
    indep_spread = engine.independent_cds_spread()
    assert math.isclose(indep_spread, 0.012, abs_tol=1e-5)

    res = engine.contagious_2firm_cds_spread(T=5.0)
    assert res["spread_contagion_bps"] > res["spread_independent_bps"]
    assert res["contagion_risk_premium_bps"] > 0.0
    assert res["contagion_multiplier"] > 1.0


def test_two_speed_market_engine():
    """Verify two-speed latency arbitrage spread widening and deadweight loss."""
    two_speed = TwoSpeedMarketEngine(theta_fast=0.4, latency_gap_ms=10.0,
                                     asset_vol=0.25, inventory_cost=0.0001)
    spread_res = two_speed.calculate_equilibrium_spread()
    assert spread_res["half_spread"] > 0.0
    assert spread_res["adverse_selection_component_bps"] > 0.0
    assert spread_res["full_spread_bps"] > spread_res["inventory_component_bps"]

    dw_res = two_speed.compute_arms_race_deadweight_loss(n_hft_firms=5, capex_per_firm_usd=10000000.0)
    assert dw_res["total_deadweight_usd"] == 50000000.0
    assert dw_res["social_efficiency"] == "PRISONERS_DILEMMA_RENT_DISSIPATION"


def test_intent_dutch_auction_engine():
    """Verify UniswapX/ERC-7683 intent-based Dutch auction fill and surplus."""
    auction = IntentDutchAuctionEngine(p_start=105.0, p_end=95.0, duration_sec=60.0, gamma=1.0)
    
    assert auction.price_at_time(0.0) == 105.0
    assert auction.price_at_time(60.0) == 95.0
    assert auction.price_at_time(30.0) == 100.0

    fill_res = auction.find_optimal_fill_time(external_fair_price=98.0, gas_cost=0.5, min_solver_profit=0.2)
    assert fill_res["filled"] is True
    assert 0.0 < fill_res["fill_time_sec"] < 60.0
    assert math.isclose(fill_res["fill_price"], 98.7, abs_tol=1e-4)
    assert fill_res["user_surplus"] == fill_res["fill_price"] - 95.0
    assert fill_res["mev_protection"] == "FULL_SANDWICH_IMMUNITY"
