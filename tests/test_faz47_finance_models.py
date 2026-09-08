"""Programmatic TDD Verification Suite for Faz 47 Quantitative Finance Engines.

Models:
1. Vladimir Piterbarg (2010) Multi-Currency Collateralized Discounting & Cheapest-to-Deliver (CTD) Collateral Option
2. Robert Goldstein, Nengjiu Ju & Hayne Leland (GJL 2001) Dynamic EBIT-Based Capital Structure & Endogenous Default Barrier
3. Albert S. Kyle (1985) & Kerry Back (1992) Continuous-Time Monopolistic Informed Trading & Information Absorption
4. Bruno Biais, Pierre Hillion & Chester Spatt (1995) / Christine Parlour (1998) Dynamic LOB Order Choice & Queue Fill Probability Game
5. Tobias Adrian & Markus K. Brunnermeier (2016) CoVaR, Delta-CoVaR (ΔCoVaR) & Macroprudential Systemic Risk Quantile Regression
6. Nicolae Gârleanu & Lasse Heje Pedersen (2011) Margin-Based Asset Pricing & The Leverage-Margin Basis Spread
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


def norm_ppf(p: float) -> float:
    """Inverse normal CDF (Beasley-Springer-Moro approximation)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability p must be in (0, 1).")
    a = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
    b = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
    c = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
         0.02764388103386354, 0.0038405729373609, 0.0003951804535326,
         0.0000321767881768, 0.0000002888167364, 0.0000003960315187]
    
    y = p - 0.5
    if abs(y) < 0.42:
        r = y * y
        x = y * (((a[3]*r + a[2])*r + a[1])*r + a[0]) / ((((b[3]*r + b[2])*r + b[1])*r + b[0])*r + 1.0)
        return x
    else:
        r = p if y < 0 else 1.0 - p
        r = math.log(-math.log(r))
        x = c[0]
        for i in range(1, 9):
            x += c[i] * (r ** i)
        return -x if y < 0 else x


# ==============================================================================
# 1. Vladimir Piterbarg (2010) Multi-Currency Collateral Discounting & CTD Option
# ==============================================================================
class PiterbargCollateralizedDiscounting:
    """
    Vladimir Piterbarg (2010) Collateralized Derivatives Discounting and
    Cheapest-to-Deliver (CTD) Multi-Currency Collateral Option Engine.
    
    Under ISDA CSA agreements where the collateral poster can post in multiple currencies k,
    the effective collateral rate is the maximum net yield (cheapest funding cost):
    c*(t) = max_k (c_k(t) + basis_k(t))
    For two collateral choices (e.g. USD vs EUR), the collateral switch option is priced
    via Margrabe's exchange option formulation.
    """
    def __init__(self, domestic_rf: float = 0.03):
        self.r_d = domestic_rf

    def effective_collateral_rate_deterministic(self,
                                                collateral_rates: Dict[str, float],
                                                fx_basis_spreads: Dict[str, float]) -> Tuple[str, float]:
        """
        Determines the optimal CTD collateral choice under deterministic rates:
        effective_yield_k = c_k - basis_k.
        """
        best_currency = None
        max_net_rate = -float("inf")
        
        for ccy, rate in collateral_rates.items():
            basis = fx_basis_spreads.get(ccy, 0.0)
            net_rate = rate - basis
            if net_rate > max_net_rate:
                max_net_rate = net_rate
                best_currency = ccy

        return best_currency, max_net_rate

    def collateral_choice_option_margrabe(self,
                                          V1: float,
                                          V2: float,
                                          sigma1: float,
                                          sigma2: float,
                                          rho: float,
                                          T: float) -> Dict[str, float]:
        """
        Prices the continuous collateral choice (switch) option between two collateral assets
        using Margrabe's exchange option formula:
        Option = E[max(V1_T, V2_T)] = V2 + Call(V1, V2, T, sigma_eff)
        sigma_eff = sqrt(sigma1^2 + sigma2^2 - 2*rho*sigma1*sigma2)
        """
        if T <= 0:
            return {"option_value": max(V1, V2), "ctd_spread": max(V1, V2) - min(V1, V2)}
        
        sigma_sq = sigma1**2 + sigma2**2 - 2.0 * rho * sigma1 * sigma2
        sigma_eff = math.sqrt(max(1e-12, sigma_sq))
        
        sqrt_T = math.sqrt(T)
        d1 = (math.log(V1 / V2) + 0.5 * sigma_sq * T) / (sigma_eff * sqrt_T)
        d2 = d1 - sigma_eff * sqrt_T
        
        call_exchange = V1 * norm_cdf(d1) - V2 * norm_cdf(d2)
        ctd_value = V2 + call_exchange  # Equal to E[max(V1, V2)]
        spread_over_baseline = ctd_value - V1

        return {
            "ctd_collateral_value": ctd_value,
            "call_exchange_value": call_exchange,
            "effective_volatility": sigma_eff,
            "spread_over_asset1": spread_over_baseline,
            "delta_asset1": norm_cdf(d1),
            "delta_asset2": 1.0 - norm_cdf(d2),
        }

    def discount_factor_with_ctd(self,
                                 base_rate: float,
                                 ctd_spread_bps: float,
                                 maturity: float) -> float:
        """
        Computes the multi-currency CSA discount factor:
        P_CSA(0, T) = exp(-(base_rate + ctd_spread) * T).
        """
        eff_rate = base_rate + (ctd_spread_bps / 10000.0)
        return math.exp(-eff_rate * maturity)


# ==============================================================================
# 2. Goldstein, Ju & Leland (GJL 2001) Dynamic EBIT Capital Structure Model
# ==============================================================================
class GoldsteinJuLelandCapitalStructure:
    """
    Robert Goldstein, Nengjiu Ju & Hayne Leland (GJL 2001)
    Dynamic Capital Structure Model with EBIT-Based Endogenous Default.
    """
    def __init__(self,
                 r: float = 0.05,
                 mu: float = 0.01,
                 sigma: float = 0.20,
                 tau_tax: float = 0.25,
                 alpha_bankruptcy: float = 0.30):
        if r <= mu:
            raise ValueError("Interest rate r must exceed EBIT drift mu for convergence.")
        if sigma <= 0:
            raise ValueError("Volatility sigma must be positive.")
        self.r = r
        self.mu = mu
        self.sigma = sigma
        self.tau = tau_tax
        self.alpha = alpha_bankruptcy

        # Characteristic exponent negative root: gamma_neg < 0
        a = 0.5 * sigma**2
        b = mu - 0.5 * sigma**2
        c = -r
        disc = b**2 - 4.0 * a * c
        self.gamma_neg = (-b - math.sqrt(disc)) / (2.0 * a)

    def unlevered_firm_value(self, delta_0: float) -> float:
        """Present value of unlevered cash flows after tax: (1 - tau) * delta_0 / (r - mu)."""
        return (1.0 - self.tau) * delta_0 / (self.r - self.mu)

    def solve_endogenous_default_barrier(self, coupon: float) -> float:
        """
        Solves for the endogenous default barrier delta_B* where shareholders
        optimally abandon the firm (smooth pasting condition dE/d delta = 0).
        """
        gamma = abs(self.gamma_neg)
        factor = gamma / (gamma + 1.0)
        return factor * ((self.r - self.mu) / self.r) * coupon

    def price_capital_structure(self, delta_0: float, coupon: float) -> Dict[str, Any]:
        """
        Evaluates equity value, debt value, tax shield, bankruptcy costs,
        and credit spread for current EBIT delta_0 and coupon obligation C.
        """
        if delta_0 <= 0 or coupon <= 0:
            raise ValueError("EBIT and coupon must be strictly positive.")

        delta_B = self.solve_endogenous_default_barrier(coupon)
        if delta_0 <= delta_B:
            # Immediate default
            recovery = (1.0 - self.alpha) * self.unlevered_firm_value(delta_0)
            return {
                "delta_0": delta_0,
                "delta_B": delta_B,
                "is_defaulted": True,
                "equity_value": 0.0,
                "debt_value": recovery,
                "firm_value": recovery,
                "tax_shield": 0.0,
                "bankruptcy_costs": self.alpha * self.unlevered_firm_value(delta_0),
                "credit_spread_bps": float("inf"),
            }

        p_B = (delta_0 / delta_B) ** self.gamma_neg

        # Unlevered asset value
        V_u = self.unlevered_firm_value(delta_0)
        V_u_at_B = self.unlevered_firm_value(delta_B)

        # Tax shield value: (tau * C / r) * (1 - p_B)
        tax_shield = (self.tau * coupon / self.r) * (1.0 - p_B)

        # Expected bankruptcy costs: alpha * V_u(delta_B) * p_B
        bankruptcy_costs = self.alpha * V_u_at_B * p_B

        # Debt value
        debt_risk_free = coupon / self.r
        debt_recovery = (1.0 - self.alpha) * V_u_at_B
        debt_value = debt_risk_free * (1.0 - p_B) + debt_recovery * p_B

        # Total levered firm value
        firm_value = V_u + tax_shield - bankruptcy_costs

        # Equity value
        equity_value = max(0.0, firm_value - debt_value)

        # Effective yield and credit spread on debt
        yield_debt = coupon / debt_value if debt_value > 0 else float("inf")
        credit_spread_bps = max(0.0, (yield_debt - self.r) * 10000.0)

        return {
            "delta_0": delta_0,
            "delta_B": delta_B,
            "is_defaulted": False,
            "p_default_state_price": p_B,
            "unlevered_value": V_u,
            "tax_shield": tax_shield,
            "bankruptcy_costs": bankruptcy_costs,
            "debt_value": debt_value,
            "equity_value": equity_value,
            "total_firm_value": firm_value,
            "leverage_ratio": debt_value / firm_value,
            "credit_spread_bps": credit_spread_bps,
        }


# ==============================================================================
# 3. Albert S. Kyle (1985) & Kerry Back (1992) Continuous Informed Trading Model
# ==============================================================================
class KyleBackContinuousInformedTrading:
    """
    Albert S. Kyle (1985) & Kerry Back (1992) Continuous-Time Monopolistic
    Insider Trading and Information Absorption Model.
    """
    def __init__(self,
                 p0: float = 100.0,
                 sigma0_variance: float = 25.0,
                 sigma_u_noise_vol: float = 2.0,
                 T: float = 1.0):
        if sigma0_variance <= 0 or sigma_u_noise_vol <= 0 or T <= 0:
            raise ValueError("Variance, noise volatility, and horizon T must be positive.")
        self.p0 = p0
        self.Sigma0 = sigma0_variance
        self.sigma_u = sigma_u_noise_vol
        self.T = T
        
        # Equilibrium constant market impact lambda
        self.lambda_kyle = math.sqrt(self.Sigma0) / (self.sigma_u * math.sqrt(self.T))

    def variance_remaining(self, t: float) -> float:
        """Conditional variance of asset value at time t: Sigma_t = Sigma_0 * (1 - t/T)."""
        t_clamped = min(self.T, max(0.0, t))
        return self.Sigma0 * (1.0 - t_clamped / self.T)

    def trading_intensity_beta(self, t: float) -> float:
        """Trading aggressiveness beta_t: beta_t = sigma_u / (sqrt(Sigma_0) * sqrt(T - t))."""
        rem_time = max(1e-6, self.T - t)
        return self.sigma_u / (math.sqrt(self.Sigma0) * math.sqrt(rem_time))

    def expected_insider_profit(self) -> float:
        """Analytical expected profit for the monopolistic informed trader."""
        return 0.5 * math.sqrt(self.Sigma0) * self.sigma_u * math.sqrt(self.T)

    def simulate_trajectory(self, v_realized: float, n_steps: int = 100) -> Dict[str, np.ndarray]:
        """Simulates a continuous trajectory of prices, insider trades, and cumulative volume."""
        dt = self.T / n_steps
        times = np.linspace(0, self.T, n_steps + 1)
        
        P = np.zeros(n_steps + 1)
        P[0] = self.p0
        X = np.zeros(n_steps + 1)
        
        # Standard Brownian noise for liquidity traders
        dW = np.random.normal(0.0, math.sqrt(dt), n_steps)
        dZ = self.sigma_u * dW
        
        for i in range(n_steps):
            t = times[i]
            beta_t = self.trading_intensity_beta(t)
            dX_t = beta_t * (v_realized - P[i]) * dt
            X[i + 1] = X[i] + dX_t
            dY_t = dX_t + dZ[i]
            P[i + 1] = P[i] + self.lambda_kyle * dY_t
            
        return {
            "times": times,
            "prices": P,
            "insider_cumulative_position": X,
            "terminal_price": P[-1],
            "price_error_at_expiry": abs(P[-1] - v_realized),
            "theoretical_lambda": self.lambda_kyle,
        }


# ==============================================================================
# 4. Bruno Biais, Pierre Hillion, Chester Spatt (1995) & Christine Parlour (1998)
#    Dynamic Limit Order Book Order Placement Game & Queue Fill Probability
# ==============================================================================
class BiaisParlourLOBGame:
    """
    Bruno Biais, Pierre Hillion & Chester Spatt (1995) / Christine Parlour (1998)
    Dynamic Limit Order Book Order Placement Game & Fill Probability Engine.
    """
    def __init__(self,
                 tick_size: float = 0.01,
                 order_arrival_intensity: float = 10.0,
                 time_horizon: float = 1.0,
                 adverse_selection_alpha: float = 0.005):
        self.tick = tick_size
        self.lam = order_arrival_intensity
        self.tau = time_horizon
        self.alpha_adv = adverse_selection_alpha

    def queue_fill_probability(self, queue_position: int) -> float:
        """
        Probability that at least (queue_position + 1) market orders arrive within tau:
        P_fill = P(Poisson(lambda * tau) >= q + 1) = 1 - sum_{k=0}^q e^(-mu) * mu^k / k!
        """
        if queue_position < 0:
            return 1.0
        mu = self.lam * self.tau
        cum_prob = 0.0
        term = math.exp(-mu)
        cum_prob += term
        for k in range(1, queue_position + 1):
            term *= (mu / k)
            cum_prob += term
        return max(0.0, min(1.0, 1.0 - cum_prob))

    def evaluate_order_payoffs(self,
                               spread: float,
                               queue_position: int,
                               private_valuation: float = 0.0) -> Dict[str, Any]:
        """
        Evaluates expected payoff of a Buyer placing a Limit Buy vs Market Buy.
        """
        if spread <= 0:
            raise ValueError("Spread must be positive.")

        p_fill = self.queue_fill_probability(queue_position)
        adverse_selection = self.alpha_adv * (1.0 + 0.1 * queue_position)

        market_order_payoff = private_valuation - (spread / 2.0)
        limit_order_payoff = p_fill * (private_valuation + (spread / 2.0) - adverse_selection)

        prefers_limit_order = (limit_order_payoff > market_order_payoff)
        expected_surplus = max(market_order_payoff, limit_order_payoff)

        return {
            "spread": spread,
            "queue_position": queue_position,
            "fill_probability": p_fill,
            "adverse_selection_cost": adverse_selection,
            "market_order_payoff": market_order_payoff,
            "limit_order_payoff": limit_order_payoff,
            "prefers_limit_order": prefers_limit_order,
            "optimal_order_type": "LIMIT" if prefers_limit_order else "MARKET",
            "surplus": expected_surplus,
        }

    def find_indifference_queue_threshold(self, spread: float, private_valuation: float = 0.0) -> int:
        """
        Finds critical queue cutoff q* such that for q <= q*, trader submits Limit Order;
        for q > q*, queue is too long, submits Market Order.
        """
        for q in range(0, 100):
            res = self.evaluate_order_payoffs(spread, q, private_valuation)
            if not res["prefers_limit_order"]:
                return max(0, q - 1)
        return 99


# ==============================================================================
# 5. Tobias Adrian & Markus K. Brunnermeier (2016) CoVaR & Delta-CoVaR Engine
# ==============================================================================
class AdrianBrunnermeierCoVaR:
    """
    Tobias Adrian & Markus K. Brunnermeier (AER 2016) CoVaR and Delta-CoVaR (ΔCoVaR)
    Macroprudential Systemic Risk Engine via Linear Quantile Regression.
    """
    def __init__(self, quantile_q: float = 0.05):
        if not (0.0 < quantile_q < 0.5):
            raise ValueError("Quantile q must be in (0, 0.5), typically 0.01 or 0.05.")
        self.q = quantile_q

    def fit_linear_quantile_regression(self,
                                       y: np.ndarray,
                                       X: np.ndarray,
                                       max_iter: int = 150,
                                       tol: float = 1e-6) -> np.ndarray:
        """
        Solves linear quantile regression using IRLS with Huber smoothing.
        """
        n, p = X.shape
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        delta = 1e-4

        for _ in range(max_iter):
            resid = y - X @ beta
            weights = np.where(np.abs(resid) < delta,
                               0.5 / delta,
                               np.abs(self.q - (resid < 0.0)) / (np.abs(resid) + 1e-8))
            W = np.diag(weights)
            XTW = X.T @ W
            beta_new = np.linalg.solve(XTW @ X + 1e-8 * np.eye(p), XTW @ y)
            if np.max(np.abs(beta_new - beta)) < tol:
                break
            beta = beta_new

        return beta

    def compute_delta_covar(self,
                            institution_returns: np.ndarray,
                            system_returns: np.ndarray,
                            state_variables: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Computes VaR_i(q), VaR_i(50%), CoVaR, and Delta-CoVaR contribution.
        """
        r_i = np.asarray(institution_returns, dtype=float)
        r_sys = np.asarray(system_returns, dtype=float)
        n = len(r_i)

        var_i_q = float(np.percentile(r_i, self.q * 100.0))
        var_i_med = float(np.percentile(r_i, 50.0))

        ones = np.ones((n, 1))
        if state_variables is not None:
            M = np.asarray(state_variables, dtype=float)
            if M.ndim == 1:
                M = M.reshape(-1, 1)
            X = np.hstack([ones, M, r_i.reshape(-1, 1)])
            current_m = np.mean(M, axis=0)
        else:
            X = np.hstack([ones, r_i.reshape(-1, 1)])
            current_m = np.array([])

        beta_q = self.fit_linear_quantile_regression(r_sys, X)
        beta_institution = beta_q[-1]

        delta_covar = beta_institution * (var_i_q - var_i_med)

        if state_variables is not None:
            x_distress = np.hstack([[1.0], current_m, [var_i_q]])
            covar_distress = float(np.dot(beta_q, x_distress))
        else:
            covar_distress = float(beta_q[0] + beta_q[1] * var_i_q)

        return {
            "quantile": self.q,
            "institution_var_q": var_i_q,
            "institution_var_median": var_i_med,
            "beta_sensitivity": beta_institution,
            "covar_at_distress": covar_distress,
            "delta_covar": delta_covar,
            "systemic_impact_score": abs(delta_covar),
            "is_systemically_significant": abs(delta_covar) > 0.02,
        }


# ==============================================================================
# 6. Nicolae Gârleanu & Lasse Heje Pedersen (2011) Margin-Based Asset Pricing
# ==============================================================================
class GarleanuPedersenMarginPricing:
    """
    Nicolae Gârleanu & Lasse Heje Pedersen (RFS 2011)
    Margin-Based Asset Pricing & The Leverage-Margin Basis Spread Engine.
    """
    def __init__(self,
                 rf: float = 0.03,
                 market_risk_premium: float = 0.05,
                 margin_shadow_price_psi: float = 0.04):
        if rf < 0 or market_risk_premium < 0 or margin_shadow_price_psi < 0:
            raise ValueError("Financial rates and shadow price must be non-negative.")
        self.rf = rf
        self.lambda_M = market_risk_premium
        self.psi = margin_shadow_price_psi

    def required_return(self, market_beta: float, margin_haircut: float) -> float:
        """Computes expected asset return under binding margin constraints."""
        if not (0.0 <= margin_haircut <= 1.0):
            raise ValueError("Margin haircut must be in [0, 1].")
        return self.rf + market_beta * self.lambda_M + margin_haircut * self.psi

    def compute_law_of_one_price_basis(self,
                                       haircut_high: float,
                                       haircut_low: float) -> Dict[str, Any]:
        """
        Computes the theoretical Basis spread between a high-margin asset (e.g. corporate bond)
        and a low-margin asset (e.g. CDS contract or derivative substitute).
        """
        if haircut_high < haircut_low:
            raise ValueError("haircut_high must be greater than haircut_low.")

        delta_margin = haircut_high - haircut_low
        basis_spread = delta_margin * self.psi
        basis_bps = basis_spread * 10000.0

        return {
            "haircut_high": haircut_high,
            "haircut_low": haircut_low,
            "margin_difference": delta_margin,
            "shadow_price_psi": self.psi,
            "basis_spread_annual": basis_spread,
            "basis_spread_bps": basis_bps,
            "implied_funding_cost_gap": delta_margin * self.psi,
        }

    def solve_equilibrium_shadow_price(self,
                                       aggregate_wealth: float,
                                       leverage_bound: float,
                                       unconstrained_demand_volume: float) -> float:
        """
        Solves for shadow price psi when aggregate investor capital is constrained.
        """
        capacity = leverage_bound * aggregate_wealth
        excess_demand = max(0.0, unconstrained_demand_volume - capacity)
        psi = excess_demand / (aggregate_wealth + 1e-8)
        return float(min(0.25, psi))


# ==============================================================================
# PyTest Unit Verification Suite
# ==============================================================================

def test_piterbarg_collateralized_discounting():
    """Verify Vladimir Piterbarg (2010) collateral discounting & CTD Margrabe option."""
    engine = PiterbargCollateralizedDiscounting(domestic_rf=0.035)

    # Test 1: Deterministic CTD choice
    rates = {"USD": 0.045, "EUR": 0.025, "GBP": 0.038}
    basis = {"USD": 0.002, "EUR": -0.001, "GBP": 0.005}  # Net: USD=0.043, EUR=0.026, GBP=0.033
    best_ccy, best_rate = engine.effective_collateral_rate_deterministic(rates, basis)
    assert best_ccy == "USD"
    assert best_rate == pytest.approx(0.043, abs=1e-5)

    # Test 2: Stochastic Margrabe CTD Option
    res = engine.collateral_choice_option_margrabe(
        V1=1.0, V2=0.98, sigma1=0.15, sigma2=0.12, rho=0.60, T=1.0
    )
    assert res["ctd_collateral_value"] >= max(1.0, 0.98)
    assert res["effective_volatility"] > 0.0
    assert res["call_exchange_value"] > 0.0

    # Test 3: Discount factor with CTD spread
    df = engine.discount_factor_with_ctd(base_rate=0.03, ctd_spread_bps=25.0, maturity=5.0)
    assert 0.0 < df < 1.0
    assert df == pytest.approx(math.exp(-(0.03 + 0.0025) * 5.0), abs=1e-6)


def test_goldstein_ju_leland_capital_structure():
    """Verify Goldstein, Ju & Leland (GJL 2001) dynamic EBIT capital structure."""
    gjl = GoldsteinJuLelandCapitalStructure(r=0.06, mu=0.01, sigma=0.22, tau_tax=0.25, alpha_bankruptcy=0.35)

    # Test unlevered value
    v_u = gjl.unlevered_firm_value(delta_0=10.0)
    assert v_u == pytest.approx((1.0 - 0.25) * 10.0 / (0.06 - 0.01), abs=1e-4)

    # Test endogenous barrier
    delta_B = gjl.solve_endogenous_default_barrier(coupon=6.0)
    assert 0.0 < delta_B < 10.0

    # Test healthy firm pricing
    res = gjl.price_capital_structure(delta_0=15.0, coupon=6.0)
    assert res["is_defaulted"] is False
    assert res["equity_value"] > 0.0
    assert res["debt_value"] > 0.0
    assert res["tax_shield"] > 0.0
    assert res["bankruptcy_costs"] > 0.0
    assert res["credit_spread_bps"] > 0.0
    assert res["total_firm_value"] > res["unlevered_value"]

    # Test distressed firm default
    distressed = gjl.price_capital_structure(delta_0=delta_B * 0.5, coupon=6.0)
    assert distressed["is_defaulted"] is True
    assert distressed["equity_value"] == 0.0


def test_kyle_back_continuous_informed_trading():
    """Verify Albert S. Kyle (1985) & Kerry Back (1992) continuous insider trading."""
    kyle = KyleBackContinuousInformedTrading(p0=100.0, sigma0_variance=16.0, sigma_u_noise_vol=2.0, T=1.0)

    # Constant market depth
    assert kyle.lambda_kyle == pytest.approx(4.0 / 2.0, abs=1e-5)

    # Linear variance reduction
    assert kyle.variance_remaining(t=0.0) == 16.0
    assert kyle.variance_remaining(t=0.5) == 8.0
    assert kyle.variance_remaining(t=1.0) == 0.0

    # Aggressiveness explodes at horizon
    beta_0 = kyle.trading_intensity_beta(t=0.0)
    beta_half = kyle.trading_intensity_beta(t=0.75)
    assert beta_half > beta_0

    # Analytical profit
    profit = kyle.expected_insider_profit()
    assert profit == pytest.approx(0.5 * 4.0 * 2.0 * 1.0, abs=1e-5)

    # Simulation convergence
    np.random.seed(42)
    sim = kyle.simulate_trajectory(v_realized=108.0, n_steps=200)
    assert len(sim["prices"]) == 201
    assert sim["price_error_at_expiry"] < 5.0


def test_biais_parlour_lob_game():
    """Verify Biais-Hillion-Spatt (1995) & Parlour (1998) order choice and fill probabilities."""
    lob = BiaisParlourLOBGame(tick_size=0.01, order_arrival_intensity=12.0, time_horizon=1.0, adverse_selection_alpha=0.004)

    # Queue fill probabilities monotonic decreasing in depth
    p0 = lob.queue_fill_probability(queue_position=0)
    p5 = lob.queue_fill_probability(queue_position=5)
    p20 = lob.queue_fill_probability(queue_position=20)
    assert 0.95 < p0 <= 1.0
    assert p5 < p0
    assert p20 < p5

    # Payoff evaluation
    res_front = lob.evaluate_order_payoffs(spread=0.05, queue_position=1, private_valuation=0.10)
    assert res_front["prefers_limit_order"] is True

    res_back = lob.evaluate_order_payoffs(spread=0.02, queue_position=30, private_valuation=0.10)
    assert res_back["prefers_limit_order"] is False

    cutoff = lob.find_indifference_queue_threshold(spread=0.04, private_valuation=0.05)
    assert 0 <= cutoff <= 50


def test_adrian_brunnermeier_covar():
    """Verify Tobias Adrian & Markus K. Brunnermeier (2016) CoVaR and Delta-CoVaR."""
    covar_engine = AdrianBrunnermeierCoVaR(quantile_q=0.05)

    np.random.seed(123)
    n = 250
    market_factor = np.random.normal(0.0, 0.02, n)
    r_bank = 0.8 * market_factor + np.random.normal(0.0, 0.015, n)
    r_sys = 0.7 * market_factor + 0.5 * r_bank + np.random.normal(0.0, 0.01, n)

    res = covar_engine.compute_delta_covar(institution_returns=r_bank,
                                          system_returns=r_sys,
                                          state_variables=market_factor)

    assert res["institution_var_q"] < res["institution_var_median"]
    assert res["beta_sensitivity"] > 0.0
    assert res["delta_covar"] < 0.0
    assert res["systemic_impact_score"] > 0.0


def test_garleanu_pedersen_margin_pricing():
    """Verify Nicolae Gârleanu & Lasse Heje Pedersen (2011) margin-based asset pricing."""
    engine = GarleanuPedersenMarginPricing(rf=0.03, market_risk_premium=0.05, margin_shadow_price_psi=0.04)

    ret_low_margin = engine.required_return(market_beta=1.0, margin_haircut=0.10)
    ret_high_margin = engine.required_return(market_beta=1.0, margin_haircut=0.50)
    assert ret_high_margin > ret_low_margin
    assert (ret_high_margin - ret_low_margin) == pytest.approx(0.40 * 0.04, abs=1e-5)

    basis = engine.compute_law_of_one_price_basis(haircut_high=0.60, haircut_low=0.15)
    assert basis["margin_difference"] == pytest.approx(0.45, abs=1e-5)
    assert basis["basis_spread_bps"] == pytest.approx(0.45 * 0.04 * 10000.0, abs=1e-4)

    psi = engine.solve_equilibrium_shadow_price(aggregate_wealth=100.0, leverage_bound=4.0, unconstrained_demand_volume=550.0)
    assert psi > 0.0
