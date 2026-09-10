"""Programmatic TDD Verification Suite for Faz 48 Quantitative Finance Engines.

Models:
1. Andrei Shleifer & Robert W. Vishny (1997) Limits of Arbitrage & Performance-Based Arbitrage (PBA)
2. Damir Filipović, Paul Schneider & Josef Teichmann (2016) Polynomial Jump-Diffusion Processes & Exact Moment Matrix-Exponential Pricing Engine
3. J. Doyne Farmer, Paolo Patelli & Ilija I. Zovko (2005) Zero-Intelligence Order Flow, Limit Order Book Equilibrium & Sublinear Price Impact
4. Douglas W. Diamond & Philip H. Dybvig (1983) Bank Runs, Liquidity Transformation & Deposit Insurance Game Theory
5. Tim Bollerslev (1986) / Glosten, Jagannathan & Runkle (GJR 1993) & Daniel B. Nelson (EGARCH 1991) Asymmetric Leverage Volatility & News Impact Engine
6. John Geanakoplos (2010) The Leverage Cycle, Heterogeneous Beliefs & Endogenous Margin Collateral Spiral
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


# ==============================================================================
# 1. Andrei Shleifer & Robert W. Vishny (1997) Limits of Arbitrage & PBA
# ==============================================================================
class ShleiferVishnyLimitsOfArbitrage:
    """
    Shleifer & Vishny (1997) Limits of Arbitrage & Performance-Based Arbitrage (PBA).
    
    Arbitrageurs manage outside capital. When noise trader sentiment pushes prices further
    away from fundamental value (interim loss), fund outflows force the arbitrageur to
    liquidate positions prematurely, causing mispricing to widen rather than narrow.
    """
    def __init__(self, fundamental_value: float = 1.0):
        self.fundamental_value = fundamental_value

    def calculate_interim_price_and_return(
        self,
        initial_price: float,
        sentiment_shock: float
    ) -> Tuple[float, float]:
        """
        Price at t=2 under sentiment shock S: P_2 = fundamental_value - S.
        Interim return for an arbitrageur long the mispriced asset: R_1 = (P_2 - P_1) / P_1.
        """
        p2 = max(0.01, self.fundamental_value - sentiment_shock)
        ret = (p2 - initial_price) / initial_price
        return p2, ret

    def fund_flow_response(
        self,
        interim_return: float,
        initial_capital: float,
        responsiveness_kappa: float = 0.8
    ) -> float:
        """
        Performance-Based fund flows:
        New capital = Capital_after_pnl + F(R)
        where F(R) = kappa * interim_return * initial_capital (outflow if R < 0).
        """
        pnl_capital = initial_capital * (1.0 + interim_return)
        flow = responsiveness_kappa * interim_return * initial_capital
        total_available_capital = max(0.0, pnl_capital + flow)
        return total_available_capital

    def check_margin_and_liquidation(
        self,
        available_capital: float,
        position_shares: float,
        current_price: float,
        margin_requirement: float = 0.25
    ) -> Dict[str, float]:
        """
        Evaluates margin maintenance and forced liquidation:
        Required equity = margin_requirement * position_value.
        If available_capital < required equity, forced liquidation occurs.
        """
        position_value = position_shares * current_price
        required_equity = margin_requirement * position_value
        is_margin_breached = available_capital < required_equity

        if is_margin_breached:
            # Maximum shares that can be held with available capital:
            max_allowed_value = available_capital / margin_requirement if margin_requirement > 0 else position_value
            max_allowed_shares = max_allowed_value / current_price
            forced_liquidation_shares = max(0.0, position_shares - max_allowed_shares)
            new_position_shares = max_allowed_shares
        else:
            forced_liquidation_shares = 0.0
            new_position_shares = position_shares

        return {
            "is_margin_breached": float(is_margin_breached),
            "available_capital": available_capital,
            "position_value": position_value,
            "required_equity": required_equity,
            "forced_liquidation_shares": forced_liquidation_shares,
            "retained_shares": new_position_shares
        }

    def optimal_arbitrage_allocation(
        self,
        initial_wealth: float,
        prob_worse: float,
        shock_initial: float,
        shock_worse: float,
        leverage_ratio: float = 2.0,
        margin_requirement: float = 0.35,
        risk_aversion_gamma: float = 2.0
    ) -> Dict[str, float]:
        """
        Evaluates optimal allocation under PBA fear of interim liquidation:
        Compares leveraged aggressive vs prudent arbitrageur allocation.
        """
        p1 = self.fundamental_value - shock_initial
        # Aggressive leveraged investment:
        agg_investment = initial_wealth * leverage_ratio
        agg_debt = agg_investment - initial_wealth
        agg_shares = agg_investment / p1

        # Prudent unleveraged investment keeping a cash buffer:
        prudent_shares = 0.6 * (initial_wealth / p1)

        # Scenario Worse: price drops to p2_worse
        p2_worse = self.fundamental_value - shock_worse
        ret_worse = (p2_worse - p1) / p1

        # Aggressive position equity after price drop and fund outflows:
        agg_pos_val = agg_shares * p2_worse
        agg_equity_before_flow = max(0.0, agg_pos_val - agg_debt)
        # Fund flow response based on performance:
        flow_agg = 1.2 * ret_worse * initial_wealth
        agg_avail_cap = max(0.0, agg_equity_before_flow + flow_agg)
        check_agg = self.check_margin_and_liquidation(agg_avail_cap, agg_shares, p2_worse, margin_requirement)

        # Prudent position:
        prud_pos_val = prudent_shares * p2_worse
        flow_prud = 0.6 * ret_worse * initial_wealth
        prud_avail_cap = max(0.0, prud_pos_val + (initial_wealth * 0.4) + flow_prud)
        check_prud = self.check_margin_and_liquidation(prud_avail_cap, prudent_shares, p2_worse, margin_requirement)

        return {
            "p1": p1,
            "p2_worse": p2_worse,
            "agg_liquidation": check_agg["forced_liquidation_shares"],
            "prud_liquidation": check_prud["forced_liquidation_shares"],
            "under_investment_incentive": 1.0 if check_agg["forced_liquidation_shares"] > 0 else 0.0
        }


# ==============================================================================
# 2. Damir Filipović et al. (2016) Polynomial Processes Engine
# ==============================================================================
class FilipovicPolynomialProcessEngine:
    """
    Filipović, Schneider & Teichmann (2016) Polynomial Jump-Diffusion Engine.
    
    The infinitesimal generator maps polynomials of degree <= m to polynomials of degree <= m.
    This allows exact calculation of conditional moments via matrix exponentiation
    without Riccati ODEs or numerical Fourier inversions!
    """
    def __init__(self, kappa: float, theta: float, sigma: float):
        """
        Jacobi Stochastic Volatility process on [0, 1]:
        dX_t = kappa * (theta - X_t) dt + sigma * sqrt(X_t * (1 - X_t)) dW_t
        """
        self.kappa = kappa
        self.theta = theta
        self.sigma = sigma

    def construct_generator_matrix(self, max_degree: int) -> np.ndarray:
        """
        Constructs the (m+1) x (m+1) generator matrix A representation:
        A * (1, x, x^2, ..., x^m)^T
        A is lower triangular (bidiagonal).
        """
        m = max_degree
        A = np.zeros((m + 1, m + 1), dtype=float)

        # k = 0: A(1) = 0
        A[0, 0] = 0.0

        for k in range(1, m + 1):
            # Term from drift: kappa * (theta - x) * k * x^{k-1} = k*kappa*theta*x^{k-1} - k*kappa*x^k
            # Term from diff: 0.5 * sigma^2 * (x - x^2) * k * (k - 1) * x^{k-2}
            #               = 0.5 * k * (k - 1) * sigma^2 * x^{k-1} - 0.5 * k * (k - 1) * sigma^2 * x^k
            coeff_prev = k * self.kappa * self.theta + 0.5 * k * (k - 1) * (self.sigma ** 2)
            coeff_diag = - (k * self.kappa + 0.5 * k * (k - 1) * (self.sigma ** 2))

            A[k, k - 1] = coeff_prev
            A[k, k] = coeff_diag

        return A

    def matrix_exponential(self, A: np.ndarray, dt: float, order: int = 25) -> np.ndarray:
        """
        Computes exp(A * dt) using Taylor series with scaling and squaring.
        """
        norm_A = np.linalg.norm(A * dt, ord=np.inf)
        squarings = int(max(0, math.ceil(math.log2(norm_A + 1e-12)))) if norm_A > 0.5 else 0
        scaled_A = (A * dt) / (2.0 ** squarings)

        # Taylor expansion
        n = A.shape[0]
        term = np.eye(n, dtype=float)
        res = np.eye(n, dtype=float)
        for i in range(1, order + 1):
            term = np.dot(term, scaled_A) / i
            res += term

        # Squaring step
        for _ in range(squarings):
            res = np.dot(res, res)

        return res

    def compute_conditional_moments(
        self,
        x0: float,
        T: float,
        max_degree: int = 4
    ) -> List[float]:
        """
        Computes E[X_T^k | X_0 = x0] for k = 0, ..., max_degree exactly.
        E[p(X_T) | X_0] = exp(A * T) * p(x0)
        """
        A = self.construct_generator_matrix(max_degree)
        exp_AT = self.matrix_exponential(A, T)
        p_x0 = np.array([x0 ** k for k in range(max_degree + 1)], dtype=float)
        moments = np.dot(exp_AT, p_x0)
        return [float(m) for m in moments]

    def variance_swap_fair_strike(
        self,
        x0: float,
        T: float
    ) -> float:
        """
        Computes the fair strike of a variance swap:
        K_var = (1 / T) * integral_0^T E[X_t | X_0] dt
        Using analytical expectation of 1st moment:
        E[X_t | X_0] = theta + (x0 - theta) * exp(-kappa * t)
        Integral = theta * T + (x0 - theta) * (1 - exp(-kappa * T)) / kappa
        Strike = Integral / T.
        """
        if self.kappa == 0:
            return x0
        integral = self.theta * T + (x0 - self.theta) * (1.0 - math.exp(-self.kappa * T)) / self.kappa
        return integral / T


# ==============================================================================
# 3. J. Doyne Farmer, Paolo Patelli & Ilija I. Zovko (2005) LOB Mechanics
# ==============================================================================
class FarmerPatelliZovkoLOB:
    """
    Farmer, Patelli & Zovko (FPZ 2005) Zero-Intelligence Limit Order Book Mechanics.
    
    Models Poisson order flow of limit orders (alpha), market orders (mu),
    and cancellations (delta), determining the equilibrium spread, depth density,
    and sublinear price impact law.
    """
    def __init__(self, alpha: float = 0.15, mu: float = 0.10, delta: float = 0.05):
        """
        alpha: Limit order placement density (orders / price_unit / sec)
        mu: Market order arrival rate (orders / sec)
        delta: Cancellation rate per order (1 / sec)
        """
        self.alpha = alpha
        self.mu = mu
        self.delta = delta

    def stationary_depth_density(self) -> float:
        """
        Steady-state order depth density far from the spread:
        n* = alpha / delta (orders / price_unit).
        """
        return self.alpha / self.delta

    def equilibrium_spread(self) -> float:
        """
        Equilibrium characteristic bid-ask spread under FPZ scaling:
        S* ~ (mu / alpha) * sqrt(delta / mu) = sqrt(mu * delta) / alpha.
        """
        return math.sqrt(self.mu * self.delta) / self.alpha

    def power_law_price_impact(
        self,
        volume_Q: float,
        beta_exponent: float = 0.5
    ) -> float:
        """
        Price impact under FPZ / Bouchaud Square Root Law:
        Delta P = (delta / alpha)^beta * Q^beta where beta ~ 0.5.
        """
        scale = (self.delta / self.alpha) ** beta_exponent
        return scale * (volume_Q ** beta_exponent)

    def simulate_lob_depth_profile(
        self,
        max_ticks: int = 10,
        dt: float = 1.0
    ) -> Dict[int, float]:
        """
        Computes expected queue size at each price tick from the inside quote:
        At distance x, cancellation balances placement: Q(x) = (alpha / delta) * (1 - exp(-delta * t)).
        """
        profile = {}
        for tick in range(1, max_ticks + 1):
            depth = (self.alpha / self.delta) * (1.0 - math.exp(-self.delta * tick * dt * 2.0))
            profile[tick] = float(depth)
        return profile


# ==============================================================================
# 4. Douglas W. Diamond & Philip H. Dybvig (1983) Bank Run Engine
# ==============================================================================
class DiamondDybvigBankRunEngine:
    """
    Diamond & Dybvig (1983) Bank Runs, Liquidity Transformation & Deposit Insurance.
    
    Banks transform illiquid long-term assets (return R > 1, scrap L < 1) into liquid
    demand deposits (c1* > 1).
    Multiple equilibria exist: Pareto optimal sharing vs Panic Bank Run equilibrium.
    """
    def __init__(
        self,
        lambda_impatient: float = 0.4,
        R_long: float = 1.5,
        L_scrap: float = 0.6,
        gamma_risk_aversion: float = 2.0
    ):
        self.lambd = lambda_impatient
        self.R = R_long
        self.L = L_scrap
        self.gamma = gamma_risk_aversion

    def optimal_contract(self) -> Tuple[float, float]:
        """
        Optimal risk-sharing contract (c1*, c2*) solving:
        u'(c1*) = R * u'(c2*) where u(c) = c^(1-gamma) / (1-gamma).
        c1^(-gamma) = R * c2^(-gamma) => c2 = c1 * R^(1/gamma).
        Resource constraint: lambda * c1 + (1 - lambda) * (c2 / R) = 1.
        """
        g = self.gamma
        ratio = self.R ** (1.0 / g)
        c1 = 1.0 / (self.lambd + (1.0 - self.lambd) * (ratio / self.R))
        c2 = c1 * ratio
        return c1, c2

    def patient_depositor_payoffs(
        self,
        fraction_withdrawing_f: float,
        c1: float
    ) -> Dict[str, float]:
        """
        Payoff to a patient depositor withdrawing at t=1 vs waiting until t=2,
        given fraction f of total depositors withdraw at t=1.
        """
        if fraction_withdrawing_f * c1 <= 1.0:
            payoff_wait = (1.0 - fraction_withdrawing_f * c1) * self.R / max(1e-6, 1.0 - fraction_withdrawing_f)
            payoff_run = c1
            bank_solvent = True
        else:
            payoff_wait = 0.0
            prob_served = min(1.0, 1.0 / (fraction_withdrawing_f * c1))
            payoff_run = prob_served * c1
            bank_solvent = False

        return {
            "fraction_f": fraction_withdrawing_f,
            "payoff_wait": payoff_wait,
            "payoff_run": payoff_run,
            "bank_solvent": float(bank_solvent),
            "run_incentive": float(payoff_run > payoff_wait)
        }

    def bank_run_threshold(self, c1: float) -> float:
        """
        The critical fraction f* beyond which payoff_wait < payoff_run (bank run occurs).
        """
        num = self.R - c1
        denom = c1 * (self.R - 1.0)
        f_star = num / denom if denom > 0 else 1.0
        return max(0.0, min(1.0, f_star))

    def suspension_of_convertibility_policy(
        self,
        actual_withdrawals_f: float,
        c1: float
    ) -> Dict[str, float]:
        """
        Suspension of convertibility halts withdrawals once f reaches lambda_impatient.
        Guarantees bank solvency and eliminates the bank run equilibrium!
        """
        effective_withdrawals = min(actual_withdrawals_f, self.lambd)
        remaining_wealth = 1.0 - effective_withdrawals * c1
        c2_guaranteed = remaining_wealth * self.R / (1.0 - self.lambd)

        return {
            "effective_withdrawals": effective_withdrawals,
            "c2_guaranteed": c2_guaranteed,
            "run_prevented": 1.0
        }


# ==============================================================================
# 5. Bollerslev (1986) / GJR (1993) & Nelson (1991) Asymmetric Volatility
# ==============================================================================
class GJREGARCHVolatilityEngine:
    """
    GJR-GARCH & Nelson's EGARCH Asymmetric Volatility Engine.
    
    Captures the leverage effect / volatility asymmetry: negative returns create
    higher volatility than positive returns of identical magnitude.
    """
    def __init__(self):
        pass

    def gjr_garch_step(
        self,
        last_variance: float,
        last_residual: float,
        omega: float,
        alpha: float,
        gamma: float,
        beta: float
    ) -> float:
        """
        GJR-GARCH(1,1) recursion:
        sigma_t^2 = omega + (alpha + gamma * I_{last < 0}) * epsilon_{t-1}^2 + beta * sigma_{t-1}^2
        """
        indicator = 1.0 if last_residual < 0.0 else 0.0
        new_var = omega + (alpha + gamma * indicator) * (last_residual ** 2) + beta * last_variance
        return max(1e-6, new_var)

    def gjr_unconditional_variance(
        self,
        omega: float,
        alpha: float,
        gamma: float,
        beta: float
    ) -> float:
        """
        Unconditional long-term variance:
        bar_sigma^2 = omega / (1 - alpha - beta - 0.5 * gamma).
        """
        denom = 1.0 - alpha - beta - 0.5 * gamma
        if denom <= 0:
            raise ValueError("GJR-GARCH parameters do not satisfy the covariance-stationarity condition.")
        return omega / denom

    def egarch_step(
        self,
        last_log_variance: float,
        last_residual: float,
        last_sigma: float,
        omega: float,
        alpha: float,
        gamma: float,
        beta: float
    ) -> Tuple[float, float]:
        """
        Nelson (1991) EGARCH(1,1) recursion:
        ln(sigma_t^2) = omega + beta * ln(sigma_{t-1}^2) + alpha * (|z_{t-1}| - sqrt(2/pi)) + gamma * z_{t-1}
        where z_{t-1} = epsilon_{t-1} / sigma_{t-1}.
        Returns (new_log_variance, new_variance).
        """
        z = last_residual / max(1e-6, last_sigma)
        expected_abs_z = math.sqrt(2.0 / math.pi)
        new_log_var = omega + beta * last_log_variance + alpha * (abs(z) - expected_abs_z) + gamma * z
        new_var = math.exp(new_log_var)
        return new_log_var, new_var

    def news_impact_curve(
        self,
        omega: float,
        alpha: float,
        gamma: float,
        beta: float,
        model_type: str = "GJR",
        grid_points: int = 50
    ) -> Dict[str, List[float]]:
        """
        News Impact Curve: sigma_t^2 as a function of shock epsilon_{t-1} in [-3*sigma, +3*sigma].
        """
        bar_var = self.gjr_unconditional_variance(omega, alpha, gamma, beta)
        bar_sigma = math.sqrt(bar_var)
        eps_grid = np.linspace(-3.0 * bar_sigma, 3.0 * bar_sigma, grid_points)
        variances = []

        for eps in eps_grid:
            if model_type == "GJR":
                v = self.gjr_garch_step(bar_var, float(eps), omega, alpha, gamma, beta)
            else:
                log_v = math.log(bar_var)
                _, v = self.egarch_step(log_v, float(eps), bar_sigma, omega, alpha, gamma, beta)
            variances.append(float(v))

        return {
            "residuals": [float(x) for x in eps_grid],
            "variances": variances
        }

    def multi_step_forward_forecast(
        self,
        current_variance: float,
        horizon: int,
        omega: float,
        alpha: float,
        gamma: float,
        beta: float
    ) -> List[float]:
        """
        Multi-step analytical forward variance forecast:
        E_t[sigma_{t+k}^2] = bar_sigma^2 + (alpha + beta + 0.5 * gamma)^(k-1) * (sigma_{t+1}^2 - bar_sigma^2).
        """
        bar_var = self.gjr_unconditional_variance(omega, alpha, gamma, beta)
        persistence = alpha + beta + 0.5 * gamma
        forecasts = []

        for k in range(1, horizon + 1):
            term = (persistence ** (k - 1)) * (current_variance - bar_var)
            f_k = bar_var + term
            forecasts.append(float(max(1e-6, f_k)))

        return forecasts


# ==============================================================================
# 6. John Geanakoplos (2010) The Leverage Cycle & Collateral Spiral
# ==============================================================================
class GeanakoplosLeverageCycleEngine:
    """
    John Geanakoplos (2010) The Leverage Cycle & Collateralized Equilibrium.
    
    Heterogeneous beliefs + non-recourse collateral contracts determine equilibrium
    asset prices, margins (haircuts), and leverage simultaneously.
    Margin shocks trigger non-linear fire-sale spirals.
    """
    def __init__(self, Y_up: float = 1.0, Y_down: float = 0.4):
        """
        Future asset payoffs: Y_up in good state, Y_down in bad state.
        """
        self.Y_up = Y_up
        self.Y_down = Y_down

    def investor_valuation(self, belief_q: float) -> float:
        """
        Subjective expected payoff: V(q) = q * Y_up + (1 - q) * Y_down.
        """
        return belief_q * self.Y_up + (1.0 - belief_q) * self.Y_down

    def collateral_margin_and_leverage(self, price_P: float) -> Tuple[float, float, float]:
        """
        Non-recourse loan limit = Y_down (riskless debt).
        Margin downpayment = m = P - Y_down.
        Haircut h = m / P = 1 - Y_down / P.
        Leverage Lambda = P / m = P / (P - Y_down).
        """
        margin_cash = max(1e-4, price_P - self.Y_down)
        haircut = margin_cash / price_P
        leverage = price_P / margin_cash
        return margin_cash, haircut, leverage

    def solve_equilibrium_price(
        self,
        total_supply: float = 100.0,
        total_wealth_pool: float = 60.0
    ) -> Dict[str, float]:
        """
        Solves for equilibrium price P and marginal buyer belief q* where:
        Total assets held by optimists [q*, 1] equals supply S:
        P = Y_down + (Total Wealth / S)
        and P = V(q*) = q* * Y_up + (1 - q*) * Y_down.
        """
        margin_cash_needed = total_wealth_pool / total_supply
        price = self.Y_down + margin_cash_needed

        spread = self.Y_up - self.Y_down
        q_star = (price - self.Y_down) / spread if spread > 0 else 0.5
        q_star = max(0.0, min(1.0, q_star))

        _, haircut, leverage = self.collateral_margin_and_leverage(price)

        return {
            "equilibrium_price": float(price),
            "marginal_buyer_q": float(q_star),
            "haircut": float(haircut),
            "leverage": float(leverage)
        }

    def simulate_leverage_cycle_shock(
        self,
        baseline_price: float,
        downside_shock_Y_down: float,
        wealth_reduction_factor: float = 0.3
    ) -> Dict[str, float]:
        """
        Simulates the collapse phase of the leverage cycle:
        1. Downside valuation Y_down drops.
        2. Lenders raise haircuts (margin spiral).
        3. Optimists suffer equity wipeouts, reducing buying wealth.
        4. Asset price crashes far below fundamental value.
        """
        old_margin, old_haircut, old_lev = self.collateral_margin_and_leverage(baseline_price)

        new_engine = GeanakoplosLeverageCycleEngine(Y_up=self.Y_up, Y_down=downside_shock_Y_down)
        post_shock_wealth = 60.0 * (1.0 - wealth_reduction_factor)
        post_shock_eq = new_engine.solve_equilibrium_price(total_supply=100.0, total_wealth_pool=post_shock_wealth)

        price_crash_pct = (post_shock_eq["equilibrium_price"] - baseline_price) / baseline_price

        return {
            "pre_price": baseline_price,
            "pre_leverage": old_lev,
            "post_price": post_shock_eq["equilibrium_price"],
            "post_leverage": post_shock_eq["leverage"],
            "post_haircut": post_shock_eq["haircut"],
            "price_crash_pct": price_crash_pct,
            "margin_spiral_active": float(post_shock_eq["haircut"] > old_haircut)
        }


# ==============================================================================
# Pytest Verification Suites (100% Agentic TDD)
# ==============================================================================
def test_shleifer_vishny_limits_of_arbitrage():
    engine = ShleiferVishnyLimitsOfArbitrage(fundamental_value=100.0)

    # 1. Price and interim return
    p2, r1 = engine.calculate_interim_price_and_return(initial_price=90.0, sentiment_shock=25.0)
    assert p2 == 75.0
    assert pytest.approx(r1, 1e-4) == (75.0 - 90.0) / 90.0

    # 2. Fund flow response under interim loss
    capital_init = 1000.0
    avail_cap = engine.fund_flow_response(interim_return=r1, initial_capital=capital_init, responsiveness_kappa=0.8)
    pnl_cap = capital_init * (1.0 + r1)
    assert avail_cap < pnl_cap
    assert avail_cap > 0.0

    # 3. Margin breach & liquidation
    margin_res = engine.check_margin_and_liquidation(
        available_capital=200.0,
        position_shares=10.0,
        current_price=75.0,
        margin_requirement=0.40
    )
    assert margin_res["is_margin_breached"] == 1.0
    assert margin_res["forced_liquidation_shares"] > 0.0
    assert pytest.approx(margin_res["retained_shares"] * 75.0 * 0.40, 1e-3) == 200.0

    # 4. Optimal allocation under PBA
    alloc = engine.optimal_arbitrage_allocation(
        initial_wealth=1000.0,
        prob_worse=0.3,
        shock_initial=10.0,
        shock_worse=30.0,
        margin_requirement=0.30
    )
    assert alloc["under_investment_incentive"] == 1.0


def test_filipovic_polynomial_process():
    engine = FilipovicPolynomialProcessEngine(kappa=1.5, theta=0.04, sigma=0.1)

    # 1. Generator matrix structure
    A = engine.construct_generator_matrix(max_degree=3)
    assert A.shape == (4, 4)
    assert np.all(A[0, :] == 0.0)
    for r in range(4):
        for c in range(r + 1, 4):
            assert A[r, c] == 0.0

    # 2. Matrix exponential
    exp_A = engine.matrix_exponential(A, dt=1.0)
    assert exp_A.shape == (4, 4)
    assert pytest.approx(exp_A[0, 0], 1e-6) == 1.0
    assert pytest.approx(np.sum(exp_A[0, 1:]), 1e-6) == 0.0

    # 3. Conditional moments
    moments = engine.compute_conditional_moments(x0=0.02, T=0.5, max_degree=3)
    assert len(moments) == 4
    assert pytest.approx(moments[0], 1e-5) == 1.0
    assert moments[1] > 0.02
    assert moments[1] < 0.04
    assert moments[2] > 0.0

    # 4. Variance swap strike
    k_var = engine.variance_swap_fair_strike(x0=0.02, T=1.0)
    assert k_var > 0.02
    assert k_var < 0.04


def test_farmer_patelli_zovko_lob():
    engine = FarmerPatelliZovkoLOB(alpha=0.20, mu=0.10, delta=0.05)

    # 1. Steady state density
    density = engine.stationary_depth_density()
    assert density == 0.20 / 0.05

    # 2. Equilibrium spread
    spread = engine.equilibrium_spread()
    assert pytest.approx(spread, 1e-3) == math.sqrt(0.005) / 0.20

    # 3. Power-law price impact (Square Root Law)
    impact_small = engine.power_law_price_impact(volume_Q=10.0, beta_exponent=0.5)
    impact_large = engine.power_law_price_impact(volume_Q=40.0, beta_exponent=0.5)
    ratio = impact_large / impact_small
    assert pytest.approx(2.0, rel=1e-3) == ratio

    # 4. Depth profile
    profile = engine.simulate_lob_depth_profile(max_ticks=5)
    assert len(profile) == 5
    assert profile[1] < profile[3] < profile[5]


def test_diamond_dybvig_bank_run():
    engine = DiamondDybvigBankRunEngine(lambda_impatient=0.3, R_long=1.6, L_scrap=0.5, gamma_risk_aversion=2.0)

    # 1. Optimal contract
    c1_star, c2_star = engine.optimal_contract()
    assert c1_star > 1.0
    assert c2_star > c1_star
    assert c2_star < 1.6

    # 2. Patient consumer payoffs under normal vs run fraction
    normal_payoffs = engine.patient_depositor_payoffs(fraction_withdrawing_f=0.3, c1=c1_star)
    assert normal_payoffs["bank_solvent"] == 1.0
    assert normal_payoffs["run_incentive"] == 0.0

    run_payoffs = engine.patient_depositor_payoffs(fraction_withdrawing_f=0.85, c1=c1_star)
    assert run_payoffs["run_incentive"] == 1.0

    # 3. Bank run threshold
    f_star = engine.bank_run_threshold(c1_star)
    assert f_star > 0.3
    assert f_star < 1.0

    # 4. Suspension of convertibility
    susp_res = engine.suspension_of_convertibility_policy(actual_withdrawals_f=0.9, c1=c1_star)
    assert susp_res["effective_withdrawals"] == 0.3
    assert susp_res["run_prevented"] == 1.0


def test_gjr_egarch_asymmetric_volatility():
    engine = GJREGARCHVolatilityEngine()
    omega, alpha, gamma, beta = 0.05, 0.05, 0.12, 0.80

    # 1. Unconditional variance
    uncond_var = engine.gjr_unconditional_variance(omega, alpha, gamma, beta)
    expected_uncond = 0.05 / 0.09
    assert pytest.approx(uncond_var, 1e-4) == expected_uncond

    # 2. Asymmetric leverage effect: negative shock produces higher variance than positive
    pos_shock_var = engine.gjr_garch_step(uncond_var, +1.5, omega, alpha, gamma, beta)
    neg_shock_var = engine.gjr_garch_step(uncond_var, -1.5, omega, alpha, gamma, beta)
    assert neg_shock_var > pos_shock_var
    diff = neg_shock_var - pos_shock_var
    assert pytest.approx(diff, 1e-4) == gamma * (1.5 ** 2)

    # 3. EGARCH step
    log_v, v = engine.egarch_step(math.log(uncond_var), -1.0, math.sqrt(uncond_var), -0.1, 0.1, -0.15, 0.95)
    assert v > 0.0
    assert math.exp(log_v) == pytest.approx(v, 1e-5)

    # 4. News impact curve
    nic = engine.news_impact_curve(omega, alpha, gamma, beta, model_type="GJR", grid_points=20)
    assert len(nic["residuals"]) == 20
    assert len(nic["variances"]) == 20

    # 5. Multi-step forward forecast
    forecasts = engine.multi_step_forward_forecast(uncond_var * 2.0, horizon=5, omega=omega, alpha=alpha, gamma=gamma, beta=beta)
    assert len(forecasts) == 5
    assert forecasts[0] > forecasts[1] > forecasts[4]
    assert forecasts[4] > uncond_var


def test_geanakoplos_leverage_cycle():
    engine = GeanakoplosLeverageCycleEngine(Y_up=1.0, Y_down=0.4)

    # 1. Valuations
    v_optimist = engine.investor_valuation(0.9)
    v_pessimist = engine.investor_valuation(0.1)
    assert pytest.approx(0.94, rel=1e-4) == v_optimist
    assert pytest.approx(0.46, rel=1e-4) == v_pessimist

    # 2. Collateral margin and leverage
    m, h, lev = engine.collateral_margin_and_leverage(price_P=0.8)
    assert pytest.approx(m, 1e-4) == 0.4
    assert pytest.approx(h, 1e-4) == 0.5
    assert pytest.approx(lev, 1e-4) == 2.0

    # 3. Equilibrium price
    eq = engine.solve_equilibrium_price(total_supply=100.0, total_wealth_pool=60.0)
    assert eq["equilibrium_price"] == 1.0
    assert eq["marginal_buyer_q"] == 1.0
    assert pytest.approx(eq["haircut"], 1e-4) == 0.6
    assert pytest.approx(eq["leverage"], 1e-4) == 1.0 / 0.6

    # 4. Leverage cycle shock simulation
    shock_res = engine.simulate_leverage_cycle_shock(
        baseline_price=1.0,
        downside_shock_Y_down=0.1,
        wealth_reduction_factor=0.4
    )
    assert shock_res["margin_spiral_active"] == 1.0
    assert shock_res["post_price"] < shock_res["pre_price"]
    assert shock_res["price_crash_pct"] < 0.0
