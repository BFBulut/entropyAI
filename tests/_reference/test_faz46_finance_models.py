"""Programmatic TDD Verification Suite for Faz 46 Quantitative Finance Engines.

Models:
1. Acharya, Pedersen, Philippon, Richardson (2012, 2017) & Brownlees-Engle (2017) SRISK, MES & Macroprudential Systemic Capital Shortfall
2. Robert Geske (1979) Compound Option Valuation of Corporate Debt with Multi-Period Coupon Obligations & Bivariate Normal Credit Spreads
3. Easley, Kiefer, O'Hara & Paperman (EKOP 1996) Probability of Informed Trading (PIN) & Asymmetric Information Microstructure
4. John H. Cochrane & Jesús Saá-Requejo (2000) Good-Deal Asset Price Bounds in Incomplete Markets & SDF Volatility Constraint
5. Robert C. Merton (1973) Intertemporal CAPM (ICAPM) & Multi-Factor State-Variable Hedging Demands
6. A. D. Roy (1952) / Kataoka (1963) Safety-First Portfolio Theory & Asymmetric Downside Ruin Avoidance
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

def bivariate_norm_cdf(a: float, b: float, rho: float, n_points: int = 100) -> float:
    """
    Bivariate normal cumulative distribution function N2(a, b; rho).
    Evaluated using Gauss-Legendre quadrature along the conditioning integral:
    N2(a, b; rho) = int_{-inf}^a phi(x) * Phi((b - rho*x) / sqrt(1 - rho^2)) dx.
    """
    if abs(rho) >= 1.0:
        if rho >= 1.0:
            return norm_cdf(min(a, b))
        else:
            return max(0.0, norm_cdf(a) - norm_cdf(-b))
    
    lower = -8.0
    if a < lower:
        return 0.0
    if a > 8.0 and b > 8.0:
        return 1.0

    x_nodes, weights = np.polynomial.legendre.leggauss(n_points)
    mid = 0.5 * (a + lower)
    half_width = 0.5 * (a - lower)
    x = mid + half_width * x_nodes
    
    sqrt_1_rho2 = math.sqrt(1.0 - rho * rho)
    phi_x = np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    
    arg = (b - rho * x) / sqrt_1_rho2
    phi_cond = 0.5 * (1.0 + np.vectorize(math.erf)(arg / math.sqrt(2.0)))
    
    val = half_width * np.sum(weights * phi_x * phi_cond)
    return float(np.clip(val, 0.0, 1.0))


# ==============================================================================
# 1. Acharya-Pedersen-Philippon-Richardson (2012, 2017) & Brownlees-Engle SRISK
# ==============================================================================
class AcharyaPedersenSRISK:
    """
    Acharya, Pedersen, Philippon, Richardson (2012, 2017) & Brownlees-Engle (2017)
    Systemic Risk, Marginal Expected Shortfall (MES), LRMES, and SRISK Engine.
    
    SRISK measures the capital shortfall of a financial institution during a systemic crisis:
    SRISK_{i,t} = max(0, k * D_{i,t} - (1 - k) * (1 - LRMES_{i,t}) * W_{i,t})
    where:
      k: Prudential regulatory capital ratio (e.g., 8%)
      D: Book value of debt / liabilities
      W: Market value of equity
      LRMES: Long-Run Marginal Expected Shortfall (expected equity drop during 40% aggregate market crash)
    """
    def __init__(self, k_capital_ratio: float = 0.08, market_crisis_drawdown: float = 0.40):
        if not (0.0 < k_capital_ratio < 1.0):
            raise ValueError("Capital ratio k must be in (0, 1).")
        self.k = k_capital_ratio
        self.S = market_crisis_drawdown

    def compute_lrmes_from_mes(self, daily_mes: float) -> float:
        """
        Approximates Long-Run Marginal Expected Shortfall (LRMES) from daily MES:
        LRMES = 1 - exp(-18 * MES) as established by Acharya et al. (2012).
        """
        if daily_mes < 0:
            raise ValueError("MES must be non-negative.")
        return float(1.0 - math.exp(-18.0 * daily_mes))

    def compute_lrmes_from_beta(self, dynamic_beta: float) -> float:
        """
        Computes LRMES conditioned on an aggregate market crash S (e.g., S = 40%):
        LRMES = 1 - (1 - S)^beta.
        """
        if dynamic_beta <= 0:
            raise ValueError("Beta must be strictly positive.")
        return float(1.0 - math.pow(1.0 - self.S, dynamic_beta))

    def compute_srisk(self,
                      equity_market_cap: float,
                      book_debt: float,
                      lrmes: float) -> Dict[str, Any]:
        """
        Calculates SRISK capital shortfall and financial resilience metrics.
        """
        if equity_market_cap <= 0:
            raise ValueError("Equity market cap must be positive.")
        if book_debt < 0:
            raise ValueError("Book debt cannot be negative.")
        if not (0.0 <= lrmes <= 1.0):
            raise ValueError("LRMES must be between 0 and 1.")

        w = equity_market_cap
        d = book_debt

        equity_crisis = (1.0 - lrmes) * w
        assets_crisis = d + equity_crisis
        required_capital = self.k * assets_crisis

        raw_shortfall = self.k * d - (1.0 - self.k) * (1.0 - lrmes) * w
        srisk = max(0.0, raw_shortfall)
        leverage_ratio = (d + w) / w
        crisis_leverage = assets_crisis / equity_crisis if equity_crisis > 0 else float("inf")

        return {
            "srisk": srisk,
            "raw_shortfall": raw_shortfall,
            "equity_market_cap": w,
            "book_debt": d,
            "lrmes": lrmes,
            "equity_crisis": equity_crisis,
            "assets_crisis": assets_crisis,
            "required_capital": required_capital,
            "is_systemically_deficient": (srisk > 0.0),
            "leverage_ratio": leverage_ratio,
            "crisis_leverage": crisis_leverage,
        }

    def compute_systemic_contributions(self, institutions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates system-wide aggregate SRISK and each institution's systemic percentage share.
        """
        results = []
        total_srisk = 0.0

        for inst in institutions:
            name = inst["name"]
            w = inst["equity"]
            d = inst["debt"]
            lrmes = inst.get("lrmes")
            if lrmes is None:
                if "beta" in inst:
                    lrmes = self.compute_lrmes_from_beta(inst["beta"])
                elif "daily_mes" in inst:
                    lrmes = self.compute_lrmes_from_mes(inst["daily_mes"])
                else:
                    raise ValueError("Institution must provide lrmes, beta, or daily_mes.")

            res = self.compute_srisk(w, d, lrmes)
            res["name"] = name
            total_srisk += res["srisk"]
            results.append(res)

        for res in results:
            res["srisk_share"] = (res["srisk"] / total_srisk) if total_srisk > 0 else 0.0
            res["pigouvian_surcharge"] = res["srisk"] * 0.015

        return {
            "total_systemic_srisk": total_srisk,
            "institutions": results,
            "vulnerable_count": sum(1 for r in results if r["is_systemically_deficient"])
        }


# ==============================================================================
# 2. Robert Geske (1979) Compound Option Corporate Debt Model
# ==============================================================================
class RobertGeskeCorporateDebt:
    """
    Robert Geske (1979) Compound Option Model for Corporate Liabilities.
    Models multi-period corporate debt where equity is a compound call option
    (an option to pay coupon C1 at T1 to maintain the option to pay face value M+C2 at T2).
    """
    def __init__(self,
                 r: float = 0.04,
                 sigma_v: float = 0.25):
        if r < 0:
            raise ValueError("Interest rate must be non-negative.")
        if sigma_v <= 0:
            raise ValueError("Firm asset volatility must be positive.")
        self.r = r
        self.sigma_v = sigma_v

    def black_scholes_call(self, V: float, tau: float, K: float) -> float:
        """Standard Black-Scholes call option price."""
        if tau <= 0 or V <= 0 or K <= 0:
            return max(0.0, V - K)
        d1 = (math.log(V / K) + (self.r + 0.5 * self.sigma_v ** 2) * tau) / (self.sigma_v * math.sqrt(tau))
        d2 = d1 - self.sigma_v * math.sqrt(tau)
        return V * norm_cdf(d1) - K * math.exp(-self.r * tau) * norm_cdf(d2)

    def find_critical_firm_value(self,
                                 T1: float,
                                 T2: float,
                                 C1: float,
                                 total_terminal_obligation: float,
                                 tol: float = 1e-7,
                                 max_iter: int = 100) -> float:
        """
        Solves for critical firm value V* at T1 satisfying:
        BS_Call(V*, T2 - T1, M + C2) = C1 using Newton-Raphson.
        """
        tau = T2 - T1
        K = total_terminal_obligation
        V = K + C1 * math.exp(self.r * tau)
        
        for _ in range(max_iter):
            d1 = (math.log(V / K) + (self.r + 0.5 * self.sigma_v ** 2) * tau) / (self.sigma_v * math.sqrt(tau))
            price = self.black_scholes_call(V, tau, K)
            diff = price - C1
            if abs(diff) < tol:
                return V
            delta = norm_cdf(d1)
            delta = max(delta, 1e-4)
            V = V - diff / delta
            if V <= 0:
                V = 1e-3

        return V

    def price_compound_equity_and_debt(self,
                                       V0: float,
                                       T1: float,
                                       T2: float,
                                       C1: float,
                                       M: float,
                                       C2: float) -> Dict[str, Any]:
        """
        Prices equity, debt, default probabilities, and credit spread under Geske (1979).
        """
        if T1 <= 0 or T2 <= T1:
            raise ValueError("Maturities must satisfy 0 < T1 < T2.")
        if V0 <= 0 or M <= 0 or C1 < 0 or C2 < 0:
            raise ValueError("Financial parameters must be strictly positive.")

        K2 = M + C2
        V_star = self.find_critical_firm_value(T1, T2, C1, K2)

        rho = math.sqrt(T1 / T2)
        sqrt_T1 = math.sqrt(T1)
        sqrt_T2 = math.sqrt(T2)

        k = (math.log(V0 / V_star) + (self.r - 0.5 * self.sigma_v ** 2) * T1) / (self.sigma_v * sqrt_T1)
        h = (math.log(V0 / K2) + (self.r - 0.5 * self.sigma_v ** 2) * T2) / (self.sigma_v * sqrt_T2)

        n2_1 = bivariate_norm_cdf(k + self.sigma_v * sqrt_T1, h + self.sigma_v * sqrt_T2, rho)
        n2_2 = bivariate_norm_cdf(k, h, rho)
        n1_k = norm_cdf(k)

        equity_value = (
            V0 * n2_1
            - K2 * math.exp(-self.r * T2) * n2_2
            - C1 * math.exp(-self.r * T1) * n1_k
        )
        equity_value = max(0.0, min(V0, equity_value))
        debt_value = V0 - equity_value

        prob_default_T1 = 1.0 - norm_cdf(k)
        prob_survival_T2 = n2_2
        prob_default_total = 1.0 - prob_survival_T2

        credit_spread_bps = 0.0
        if debt_value > 0 and K2 > 0:
            effective_yield = -math.log(max(1e-6, (debt_value - C1 * math.exp(-self.r * T1)) / K2)) / T2
            credit_spread_bps = max(0.0, (effective_yield - self.r) * 10000.0)

        return {
            "firm_value": V0,
            "equity_value": equity_value,
            "debt_value": debt_value,
            "critical_firm_value_T1": V_star,
            "prob_default_T1": prob_default_T1,
            "prob_default_total": prob_default_total,
            "credit_spread_bps": credit_spread_bps,
            "rho": rho,
            "leverage": debt_value / V0,
        }


# ==============================================================================
# 3. Easley, Kiefer, O'Hara & Paperman (EKOP 1996) PIN Model
# ==============================================================================
class EKOPProbabilityOfInformedTrading:
    """
    Easley, Kiefer, O'Hara & Paperman (1996) Probability of Informed Trading (PIN) Engine.
    PIN = (alpha * mu) / (alpha * mu + epsilon_b + epsilon_s)
    """
    def __init__(self,
                 alpha: float = 0.30,
                 delta: float = 0.40,
                 mu: float = 250.0,
                 epsilon_b: float = 120.0,
                 epsilon_s: float = 120.0):
        if not (0.0 <= alpha <= 1.0 and 0.0 <= delta <= 1.0):
            raise ValueError("Probabilities alpha and delta must be in [0, 1].")
        if mu <= 0 or epsilon_b <= 0 or epsilon_s <= 0:
            raise ValueError("Arrival rates must be strictly positive.")
        self.alpha = alpha
        self.delta = delta
        self.mu = mu
        self.epsilon_b = epsilon_b
        self.epsilon_s = epsilon_s

    def compute_pin(self) -> float:
        """Computes the structural Probability of Informed Trading (PIN)."""
        informed_arrival = self.alpha * self.mu
        uninformed_arrival = self.epsilon_b + self.epsilon_s
        return float(informed_arrival / (informed_arrival + uninformed_arrival))

    def log_likelihood_single_day(self, B: int, S: int) -> float:
        """
        Log-likelihood of observing B buys and S sells on a single trading day,
        evaluated using a numerically stable log-sum-exp factorization.
        """
        lgamma_B = math.lgamma(B + 1)
        lgamma_S = math.lgamma(S + 1)

        ln_1_alpha = math.log(max(1e-12, 1.0 - self.alpha))
        c1 = ln_1_alpha - self.epsilon_b + B * math.log(self.epsilon_b) - self.epsilon_s + S * math.log(self.epsilon_s)

        ln_alpha = math.log(max(1e-12, self.alpha))
        ln_1_delta = math.log(max(1e-12, 1.0 - self.delta))
        c2 = (ln_alpha + ln_1_delta
              - (self.epsilon_b + self.mu) + B * math.log(self.epsilon_b + self.mu)
              - self.epsilon_s + S * math.log(self.epsilon_s))

        ln_delta = math.log(max(1e-12, self.delta))
        c3 = (ln_alpha + ln_delta
              - self.epsilon_b + B * math.log(self.epsilon_b)
              - (self.epsilon_s + self.mu) + S * math.log(self.epsilon_s + self.mu))

        max_c = max(c1, c2, c3)
        log_sum = max_c + math.log(math.exp(c1 - max_c) + math.exp(c2 - max_c) + math.exp(c3 - max_c))
        return float(log_sum - lgamma_B - lgamma_S)

    def total_log_likelihood(self, trade_days: List[Tuple[int, int]]) -> float:
        """Computes aggregate log-likelihood over a sequence of trading days."""
        return sum(self.log_likelihood_single_day(b, s) for b, s in trade_days)

    def decompose_spread(self, quoted_spread: float) -> Dict[str, float]:
        """Decomposes bid-ask spread into adverse selection and inventory components."""
        pin = self.compute_pin()
        adverse_selection_spread = quoted_spread * pin
        inventory_and_processing = quoted_spread * (1.0 - pin)
        return {
            "pin": pin,
            "quoted_spread": quoted_spread,
            "adverse_selection_component": adverse_selection_spread,
            "inventory_and_order_processing": inventory_and_processing,
            "toxicity_ratio": pin / (1.0 - pin) if pin < 1.0 else float("inf")
        }


# ==============================================================================
# 4. John H. Cochrane & Jesús Saá-Requejo (2000) Good-Deal Asset Price Bounds
# ==============================================================================
class CochraneSaaRequejoGoodDealBounds:
    """
    Cochrane & Saá-Requejo (2000) Good-Deal Asset Price Bounds in Incomplete Markets.
    sigma(m) <= h_max / R_f
    """
    def __init__(self, rf: float = 0.03, h_max: float = 1.0):
        if rf < -0.5:
            raise ValueError("Risk-free rate rf cannot be less than -50%.")
        if h_max <= 0:
            raise ValueError("Maximum Sharpe ratio bound h_max must be positive.")
        self.rf = rf
        self.Rf = 1.0 + rf
        self.h_max = h_max

    def compute_bounds(self,
                       spanned_price: float,
                       unspanned_residual_std: float,
                       unspanned_residual_mean: float = 0.0) -> Dict[str, Any]:
        """Computes the analytical Good-Deal bid-ask price bounds."""
        if unspanned_residual_std < 0:
            raise ValueError("Residual standard deviation cannot be negative.")

        w_mean = unspanned_residual_mean
        w_var = unspanned_residual_std ** 2
        second_moment = w_var + w_mean ** 2

        term = second_moment - (w_mean ** 2) / (1.0 + self.h_max ** 2)
        term = max(0.0, term)
        multiplier = (self.h_max / self.Rf) * math.sqrt(term)

        p_upper = spanned_price + multiplier
        p_lower = spanned_price - multiplier

        spread = p_upper - p_lower
        relative_spread = (spread / spanned_price) if spanned_price > 0 else float("nan")

        return {
            "spanned_price": spanned_price,
            "good_deal_lower_bound": p_lower,
            "good_deal_upper_bound": p_upper,
            "good_deal_spread": spread,
            "relative_spread": relative_spread,
            "h_max": self.h_max,
            "unspanned_risk_premium": multiplier,
        }

    def evaluate_payoff_projection(self,
                                   traded_payoffs: np.ndarray,
                                   traded_prices: np.ndarray,
                                   target_payoff: np.ndarray) -> Dict[str, Any]:
        """Performs projection of target payoff y onto traded asset payoff matrix X."""
        X = traded_payoffs
        p = traded_prices
        y = target_payoff

        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        y_spanned = X @ beta
        w = y - y_spanned

        spanned_price = float(np.dot(p, beta))
        res_mean = float(np.mean(w))
        res_std = float(np.std(w))

        return self.compute_bounds(spanned_price, res_std, res_mean)


# ==============================================================================
# 5. Robert C. Merton (1973) Intertemporal CAPM (ICAPM)
# ==============================================================================
class MertonIntertemporalCAPM:
    """
    Robert C. Merton (1973) Intertemporal CAPM (ICAPM) Engine.
    Optimal portfolio = Myopic tangency portfolio + intertemporal state variable hedging demands.
    """
    def __init__(self,
                 rf: float = 0.04,
                 relative_risk_aversion: float = 3.0):
        if relative_risk_aversion <= 0:
            raise ValueError("Relative risk aversion gamma must be positive.")
        self.rf = rf
        self.gamma = relative_risk_aversion

    def compute_optimal_portfolio(self,
                                  expected_excess_returns: np.ndarray,
                                  covariance_matrix: np.ndarray,
                                  state_variable_covariances: Optional[np.ndarray] = None,
                                  hedging_propensities: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """Computes Merton's optimal asset allocation split."""
        mu_e = np.asarray(expected_excess_returns, dtype=float)
        sigma = np.asarray(covariance_matrix, dtype=float)

        sigma_inv = np.linalg.inv(sigma)
        w_myopic = (1.0 / self.gamma) * (sigma_inv @ mu_e)

        w_hedging = np.zeros_like(w_myopic)
        if state_variable_covariances is not None and hedging_propensities is not None:
            cov_z = np.asarray(state_variable_covariances, dtype=float)
            eta = np.asarray(hedging_propensities, dtype=float)
            for k in range(len(eta)):
                w_hedging += (eta[k] / self.gamma) * (sigma_inv @ cov_z[:, k])

        w_total = w_myopic + w_hedging

        return {
            "w_myopic": w_myopic,
            "w_hedging": w_hedging,
            "w_total": w_total,
            "hedging_fraction": float(np.sum(np.abs(w_hedging)) / (np.sum(np.abs(w_total)) + 1e-12)),
            "myopic_fraction": float(np.sum(np.abs(w_myopic)) / (np.sum(np.abs(w_total)) + 1e-12))
        }

    def compute_equilibrium_expected_returns(self,
                                            market_beta: np.ndarray,
                                            market_risk_premium: float,
                                            state_variable_betas: np.ndarray,
                                            state_variable_premia: np.ndarray) -> np.ndarray:
        """Multi-beta ICAPM equilibrium return pricing."""
        beta_m = np.asarray(market_beta, dtype=float)
        beta_z = np.asarray(state_variable_betas, dtype=float)
        lambda_z = np.asarray(state_variable_premia, dtype=float)

        macro_hedge_premium = beta_z @ lambda_z
        excess_return = beta_m * market_risk_premium + macro_hedge_premium
        return self.rf + excess_return


# ==============================================================================
# 6. A. D. Roy (1952) / Kataoka (1963) Safety-First Portfolio Theory
# ==============================================================================
class RoySafetyFirstPortfolio:
    """
    A. D. Roy (1952) / Kataoka (1963) Safety-First Portfolio Engine.
    SFR = (E[R_p] - R_L) / sigma_p
    P(R_p <= R_L) = Phi(-SFR)
    """
    def __init__(self, disaster_floor_return: float = -0.10):
        self.R_L = disaster_floor_return

    def compute_sfr(self, mean_return: float, std_return: float) -> float:
        """Computes Roy's Safety-First Ratio (SFR)."""
        if std_return <= 0:
            raise ValueError("Standard deviation must be strictly positive.")
        return float((mean_return - self.R_L) / std_return)

    def ruin_probability(self, mean_return: float, std_return: float) -> float:
        """Calculates exact ruin probability under normality assumption."""
        sfr = self.compute_sfr(mean_return, std_return)
        return float(norm_cdf(-sfr))

    def kataoka_disaster_floor(self, mean_return: float, std_return: float, alpha: float = 0.05) -> float:
        """Computes Kataoka's floor return at confidence level alpha."""
        if not (0.0 < alpha < 0.5):
            raise ValueError("Risk level alpha must be in (0, 0.5).")
        z_alpha = norm_ppf(1.0 - alpha)
        return float(mean_return - z_alpha * std_return)

    def find_optimal_roy_weights(self,
                                 expected_returns: np.ndarray,
                                 covariance_matrix: np.ndarray) -> Dict[str, Any]:
        """Finds optimal Roy Safety-First portfolio weights."""
        mu = np.asarray(expected_returns, dtype=float)
        sigma = np.asarray(covariance_matrix, dtype=float)
        ones = np.ones_like(mu)

        sigma_inv = np.linalg.inv(sigma)
        excess = mu - self.R_L * ones

        unnormalized_w = sigma_inv @ excess
        sum_w = float(np.sum(unnormalized_w))

        if sum_w == 0:
            weights = ones / len(mu)
        else:
            weights = unnormalized_w / sum_w

        port_mean = float(np.dot(weights, mu))
        port_var = float(weights.T @ sigma @ weights)
        port_std = math.sqrt(max(1e-12, port_var))

        sfr = self.compute_sfr(port_mean, port_std)
        ruin_prob = self.ruin_probability(port_mean, port_std)

        return {
            "optimal_weights": weights,
            "portfolio_mean": port_mean,
            "portfolio_std": port_std,
            "roy_sfr": sfr,
            "ruin_probability": ruin_prob,
            "disaster_floor": self.R_L,
        }


# ==============================================================================
# PyTest Unit Verification Suite
# ==============================================================================

def test_acharya_pedersen_srisk():
    """Verify Acharya-Pedersen-Engle SRISK calculation and systemic share."""
    engine = AcharyaPedersenSRISK(k_capital_ratio=0.08, market_crisis_drawdown=0.40)
    
    lrmes = engine.compute_lrmes_from_mes(0.035)
    assert 0.40 < lrmes < 0.55
    
    res = engine.compute_srisk(equity_market_cap=50.0, book_debt=950.0, lrmes=lrmes)
    assert res["is_systemically_deficient"] is True
    assert res["srisk"] > 40.0
    assert res["leverage_ratio"] == 20.0
    
    safe_res = engine.compute_srisk(equity_market_cap=200.0, book_debt=100.0, lrmes=0.20)
    assert safe_res["srisk"] == 0.0
    assert safe_res["is_systemically_deficient"] is False

    institutions = [
        {"name": "MegaBank", "equity": 60.0, "debt": 900.0, "beta": 1.4},
        {"name": "ShadowLender", "equity": 20.0, "debt": 380.0, "beta": 1.6},
        {"name": "ConservativeBank", "equity": 100.0, "debt": 200.0, "beta": 0.6},
    ]
    sys_res = engine.compute_systemic_contributions(institutions)
    assert sys_res["total_systemic_srisk"] > 0.0
    assert sum(inst["srisk_share"] for inst in sys_res["institutions"]) == pytest.approx(1.0, abs=1e-5)


def test_robert_geske_compound_debt():
    """Verify Robert Geske (1979) compound option pricing and credit spreads."""
    engine = RobertGeskeCorporateDebt(r=0.04, sigma_v=0.25)

    res = engine.price_compound_equity_and_debt(
        V0=120.0, T1=1.0, T2=3.0, C1=5.0, M=80.0, C2=5.0
    )

    assert 0.0 < res["equity_value"] < 120.0
    assert 0.0 < res["debt_value"] < 120.0
    assert res["equity_value"] + res["debt_value"] == pytest.approx(120.0, abs=1e-4)
    assert res["critical_firm_value_T1"] > 0.0
    assert 0.0 <= res["prob_default_T1"] <= 1.0
    assert 0.0 <= res["prob_default_total"] <= 1.0
    assert res["credit_spread_bps"] > 0.0


def test_ekop_pin_model():
    """Verify Easley-Kiefer-O'Hara-Paperman (1996) PIN and log-likelihood."""
    ekop = EKOPProbabilityOfInformedTrading(
        alpha=0.35, delta=0.45, mu=300.0, epsilon_b=150.0, epsilon_s=150.0
    )
    pin = ekop.compute_pin()
    expected_pin = (0.35 * 300.0) / (0.35 * 300.0 + 300.0)
    assert pin == pytest.approx(expected_pin, abs=1e-5)

    trade_days = [(200, 160), (320, 150), (140, 310), (155, 148)]
    total_ll = ekop.total_log_likelihood(trade_days)
    assert not math.isnan(total_ll)
    assert total_ll < 0.0

    spread_res = ekop.decompose_spread(quoted_spread=0.25)
    assert spread_res["adverse_selection_component"] + spread_res["inventory_and_order_processing"] == pytest.approx(0.25, abs=1e-5)


def test_cochrane_saa_requejo_good_deal_bounds():
    """Verify Cochrane-Saá-Requejo (2000) Good-Deal Bounds."""
    gd = CochraneSaaRequejoGoodDealBounds(rf=0.04, h_max=1.2)
    
    bounds = gd.compute_bounds(spanned_price=50.0, unspanned_residual_std=10.0, unspanned_residual_mean=0.0)
    assert bounds["good_deal_lower_bound"] < 50.0 < bounds["good_deal_upper_bound"]
    assert bounds["good_deal_spread"] > 0.0
    
    tight_gd = CochraneSaaRequejoGoodDealBounds(rf=0.04, h_max=0.01)
    tight_bounds = tight_gd.compute_bounds(spanned_price=50.0, unspanned_residual_std=10.0)
    assert tight_bounds["good_deal_spread"] < bounds["good_deal_spread"]
    assert tight_bounds["good_deal_lower_bound"] == pytest.approx(50.0, abs=0.2)


def test_merton_icapm():
    """Verify Merton (1973) ICAPM optimal portfolio decomposition and multi-beta pricing."""
    icapm = MertonIntertemporalCAPM(rf=0.03, relative_risk_aversion=2.5)

    mu_e = np.array([0.06, 0.08, 0.05])
    sigma = np.array([
        [0.04, 0.01, 0.01],
        [0.01, 0.06, 0.02],
        [0.01, 0.02, 0.05]
    ])
    cov_z = np.array([
        [-0.01, 0.02],
        [-0.02, 0.01],
        [ 0.03, -0.01]
    ])
    eta = np.array([1.2, 0.8])

    res = icapm.compute_optimal_portfolio(mu_e, sigma, cov_z, eta)
    assert len(res["w_total"]) == 3
    assert not np.allclose(res["w_hedging"], 0.0)
    assert np.allclose(res["w_total"], res["w_myopic"] + res["w_hedging"])

    beta_m = np.array([1.0, 1.2, 0.8])
    beta_z = np.array([[0.5, -0.2], [0.8, 0.4], [-0.3, 0.1]])
    lambda_z = np.array([0.02, -0.015])
    
    exp_ret = icapm.compute_equilibrium_expected_returns(beta_m, market_risk_premium=0.05,
                                                         state_variable_betas=beta_z,
                                                         state_variable_premia=lambda_z)
    assert len(exp_ret) == 3
    assert np.all(exp_ret > icapm.rf)


def test_roy_safety_first():
    """Verify A. D. Roy (1952) and Kataoka (1963) Safety-First Portfolio."""
    roy = RoySafetyFirstPortfolio(disaster_floor_return=-0.12)

    sfr = roy.compute_sfr(mean_return=0.10, std_return=0.15)
    assert sfr == pytest.approx(1.4667, abs=1e-3)

    ruin_p = roy.ruin_probability(mean_return=0.10, std_return=0.15)
    assert 0.05 < ruin_p < 0.10

    floor_95 = roy.kataoka_disaster_floor(mean_return=0.10, std_return=0.15, alpha=0.05)
    assert floor_95 < 0.10

    mu = np.array([0.08, 0.12, 0.15])
    cov = np.array([
        [0.02, 0.005, 0.008],
        [0.005, 0.04, 0.015],
        [0.008, 0.015, 0.07]
    ])
    opt_res = roy.find_optimal_roy_weights(mu, cov)
    assert np.sum(opt_res["optimal_weights"]) == pytest.approx(1.0, abs=1e-5)
    assert opt_res["roy_sfr"] > 0.0
    assert 0.0 < opt_res["ruin_probability"] < 0.10
