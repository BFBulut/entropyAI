"""Programmatic TDD Verification Suite for Faz 55 Quantitative Finance Engines.

Models:
1. Lawrence R. Glosten & Paul R. Milgrom (1985): Sequential Trade Microstructure, Bayesian Dealer Learning & Bid-Ask Spread Dynamics
2. Robert F. Engle & Kenneth F. Kroner (1995): BEKK Multivariate GARCH(1,1), Positive Definite Covariance Dynamics & Dynamic Hedge Ratios
3. Giovanni Barone-Adesi & Robert E. Whaley (1987): Efficient Analytic Approximation of American Option Values & Optimal Early Exercise Boundary
4. Hayne E. Leland (1985): Option Replication with Proportional Transaction Costs, Modified Volatility (sigma_hat) & Endogenous Option Spreads
5. Andrew W. Lo & A. Craig MacKinlay (1988, 1997): Variance Ratio (VR) Specification Test for the Random Walk Hypothesis & Market Efficiency
6. Lars E.O. Svensson (1994, 1995): Nelson-Siegel-Svensson (NSS) 6-Parameter Extended Term Structure of Interest Rates & Forward Rates
"""

import math
import time
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
# Model 1: Lawrence R. Glosten & Paul R. Milgrom (1985) Microstructure Model
# ==============================================================================
class GlostenMilgromMicrostructureEngine:
    """Glosten & Milgrom (1985) Sequential Trade Microstructure Model.
    Prices assets in the presence of informed traders with asymmetric information
    and noise traders, with exact Bayesian dealer posterior belief updating.
    """

    def __init__(
        self,
        value_low: float = 80.0,
        value_high: float = 120.0,
        prior_high: float = 0.50,
        informed_fraction: float = 0.30,
        noise_buy_prob: float = 0.50
    ):
        if value_low >= value_high:
            raise ValueError("value_low must be strictly less than value_high.")
        if not (0.0 < prior_high < 1.0):
            raise ValueError("prior_high must be in (0, 1).")
        if not (0.0 <= informed_fraction < 1.0):
            raise ValueError("informed_fraction mu must be in [0, 1).")
        if not (0.0 < noise_buy_prob < 1.0):
            raise ValueError("noise_buy_prob gamma must be in (0, 1).")

        self.V_L = float(value_low)
        self.V_H = float(value_high)
        self.pi_t = float(prior_high)  # P(V = V_H | F_t)
        self.mu = float(informed_fraction)
        self.gamma = float(noise_buy_prob)

    def current_expected_value(self) -> float:
        """Unconditional expectation of asset value: E[V | F_t] = V_L + pi_t * (V_H - V_L)."""
        return self.V_L + self.pi_t * (self.V_H - self.V_L)

    def compute_quotes(self, current_pi: Optional[float] = None) -> Dict[str, float]:
        """Calculates competitive risk-neutral dealer quotes:
        Ask = E[V | Buy], Bid = E[V | Sell].
        """
        pi = self.pi_t if current_pi is None else current_pi
        mu = self.mu
        gamma = self.gamma

        # P(Buy | V_H) = mu + (1 - mu)*gamma
        p_buy_vh = mu + (1.0 - mu) * gamma
        # P(Buy | V_L) = (1 - mu)*gamma
        p_buy_vl = (1.0 - mu) * gamma

        # P(Sell | V_H) = (1 - mu)*(1 - gamma)
        p_sell_vh = (1.0 - mu) * (1.0 - gamma)
        # P(Sell | V_L) = mu + (1 - mu)*(1 - gamma)
        p_sell_vl = mu + (1.0 - mu) * (1.0 - gamma)

        # Posterior upon Buy:
        prob_buy = pi * p_buy_vh + (1.0 - pi) * p_buy_vl
        pi_buy = (pi * p_buy_vh) / prob_buy if prob_buy > 0.0 else pi
        ask_price = self.V_L + pi_buy * (self.V_H - self.V_L)

        # Posterior upon Sell:
        prob_sell = pi * p_sell_vh + (1.0 - pi) * p_sell_vl
        pi_sell = (pi * p_sell_vh) / prob_sell if prob_sell > 0.0 else pi
        bid_price = self.V_L + pi_sell * (self.V_H - self.V_L)

        spread = max(0.0, ask_price - bid_price)
        mid_price = 0.5 * (ask_price + bid_price)

        return {
            "ask_price": float(ask_price),
            "bid_price": float(bid_price),
            "spread": float(spread),
            "mid_price": float(mid_price),
            "pi_buy": float(pi_buy),
            "pi_sell": float(pi_sell),
            "expected_value": float(self.V_L + pi * (self.V_H - self.V_L))
        }

    def update_belief(self, trade_sign: int) -> float:
        """Applies exact Bayesian updating given observed trade sign:
        trade_sign == +1 (Buy), -1 (Sell).
        Updates and returns new pi_{t+1}.
        """
        quotes = self.compute_quotes()
        if trade_sign == 1:
            self.pi_t = quotes["pi_buy"]
        elif trade_sign == -1:
            self.pi_t = quotes["pi_sell"]
        else:
            raise ValueError("trade_sign must be +1 (Buy) or -1 (Sell).")
        return self.pi_t

    def simulate_sequence(
        self,
        n_trades: int = 100,
        true_state: str = "H",
        seed: int = 42
    ) -> Dict[str, Any]:
        """Simulates sequential order flow under a true state and measures price discovery."""
        np.random.seed(seed)
        v_true = self.V_H if true_state.upper() == "H" else self.V_L

        belief_history = [self.pi_t]
        ask_history = []
        bid_history = []
        spread_history = []
        trade_history = []

        for _ in range(n_trades):
            quotes = self.compute_quotes()
            ask_history.append(quotes["ask_price"])
            bid_history.append(quotes["bid_price"])
            spread_history.append(quotes["spread"])

            # Determine who trades: Informed (prob mu) or Noise (prob 1-mu)
            if np.random.rand() < self.mu:
                # Informed trader knows true state
                trade = 1 if true_state.upper() == "H" else -1
            else:
                # Noise trader buys with prob gamma, sells with prob 1-gamma
                trade = 1 if np.random.rand() < self.gamma else -1

            trade_history.append(trade)
            new_pi = self.update_belief(trade)
            belief_history.append(new_pi)

        return {
            "true_value": v_true,
            "final_belief": self.pi_t,
            "belief_history": belief_history,
            "ask_history": ask_history,
            "bid_history": bid_history,
            "spread_history": spread_history,
            "trade_history": trade_history,
            "is_converged_to_true_state": (self.pi_t > 0.85 if true_state.upper() == "H" else self.pi_t < 0.15)
        }


# ==============================================================================
# Model 2: Robert F. Engle & Kenneth F. Kroner (1995) BEKK-GARCH(1,1) Engine
# ==============================================================================
class BEKKGARCHCovarianceEngine:
    """Engle & Kroner (1995) BEKK-GARCH(1,1) Multivariate Volatility Engine:
    H_t = C C^T + A^T (eps_{t-1} eps_{t-1}^T) A + B^T H_{t-1} B
    Guarantees positive definiteness H_t > 0 for all t by construction.
    """

    def __init__(
        self,
        C_matrix: np.ndarray,
        A_matrix: np.ndarray,
        B_matrix: np.ndarray,
        initial_H: Optional[np.ndarray] = None
    ):
        K = C_matrix.shape[0]
        if C_matrix.shape != (K, K) or A_matrix.shape != (K, K) or B_matrix.shape != (K, K):
            raise ValueError("C, A, and B matrices must all be square (K x K).")

        self.K = K
        self.C = np.array(C_matrix, dtype=float)
        self.A = np.array(A_matrix, dtype=float)
        self.B = np.array(B_matrix, dtype=float)

        # Baseline constant intercept matrix Omega = C C^T
        self.Omega = self.C @ self.C.T

        # Initial covariance
        if initial_H is not None:
            if initial_H.shape != (K, K):
                raise ValueError("initial_H shape must match K x K.")
            self.H_curr = np.array(initial_H, dtype=float)
        else:
            self.H_curr = np.copy(self.Omega)

    def is_positive_definite(self, matrix: np.ndarray) -> bool:
        """Verifies positive definiteness via Cholesky decomposition."""
        try:
            np.linalg.cholesky(matrix)
            return True
        except np.linalg.LinAlgError:
            return False

    def update_step(self, shock_vector: np.ndarray) -> np.ndarray:
        """Computes H_t = Omega + A^T (eps eps^T) A + B^T H_{t-1} B."""
        eps = np.array(shock_vector, dtype=float).reshape(self.K, 1)
        outer_eps = eps @ eps.T

        shock_term = self.A.T @ outer_eps @ self.A
        persistence_term = self.B.T @ self.H_curr @ self.B

        H_next = self.Omega + shock_term + persistence_term
        # Enforce exact symmetry numerically
        H_next = 0.5 * (H_next + H_next.T)

        self.H_curr = H_next
        return self.H_curr

    def filter_covariance_trajectory(self, shock_series: np.ndarray) -> Dict[str, Any]:
        """Filters dynamic covariance matrices over T steps given residual shocks."""
        T, K = shock_series.shape
        if K != self.K:
            raise ValueError(f"Shock series dimension {K} does not match model dimension {self.K}.")

        cov_history = []
        corr_history = []
        hedge_ratio_history = []

        for t in range(T):
            H_t = self.update_step(shock_series[t])
            cov_history.append(H_t)

            # Dynamic Correlation: rho_ij = H_ij / sqrt(H_ii * H_jj)
            diag_vols = np.sqrt(np.maximum(1e-10, np.diag(H_t)))
            outer_vols = np.outer(diag_vols, diag_vols)
            corr_t = H_t / outer_vols
            np.fill_diagonal(corr_t, 1.0)
            corr_history.append(corr_t)

            # Minimum variance dynamic hedge ratio beta* = H_12 / H_22
            if self.K >= 2:
                beta_12 = float(H_t[0, 1] / H_t[1, 1]) if H_t[1, 1] > 1e-10 else 0.0
                hedge_ratio_history.append(beta_12)

        return {
            "covariance_history": np.array(cov_history),
            "correlation_history": np.array(corr_history),
            "hedge_ratio_12": np.array(hedge_ratio_history) if self.K >= 2 else None,
            "final_covariance": self.H_curr,
            "all_positive_definite": all(self.is_positive_definite(H) for H in cov_history)
        }

    def measure_volatility_spillovers(self) -> Dict[str, Any]:
        """Quantifies cross-asset transmission channels via off-diagonal elements in A and B."""
        arch_spillover = np.abs(self.A)
        np.fill_diagonal(arch_spillover, 0.0)

        garch_spillover = np.abs(self.B)
        np.fill_diagonal(garch_spillover, 0.0)

        total_spillover = arch_spillover + garch_spillover
        return {
            "arch_spillover_matrix": arch_spillover,
            "garch_spillover_matrix": garch_spillover,
            "total_spillover_matrix": total_spillover,
            "max_cross_spillover": float(np.max(total_spillover))
        }


# ==============================================================================
# Model 3: Barone-Adesi & Whaley (1987) American Option Engine
# ==============================================================================
class BaroneAdesiWhaleyAmericanOptionEngine:
    """Barone-Adesi & Whaley (1987) Efficient Analytic Approximation of American Option Values.
    Computes optimal early exercise boundaries (S* and S**) via Newton-Raphson
    and calculates exact European and American call/put option values and Greeks.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.02,
        volatility: float = 0.25
    ):
        if volatility <= 0.0:
            raise ValueError("Volatility must be strictly positive.")
        self.r = float(risk_free_rate)
        self.q = float(dividend_yield)
        self.b = self.r - self.q  # Cost-of-carry
        self.sigma = float(volatility)

    def european_black_scholes(
        self,
        S: float,
        X: float,
        T: float,
        is_call: bool = True
    ) -> Dict[str, float]:
        """Standard Black-Scholes-Merton formula with continuous dividend yield."""
        if T <= 0.0:
            intrinsic = max(0.0, S - X) if is_call else max(0.0, X - S)
            return {"price": float(intrinsic), "delta": 1.0 if (is_call and S > X) else 0.0}

        sqrt_T = math.sqrt(T)
        sigma_sqrt_T = self.sigma * sqrt_T
        d1 = (math.log(S / X) + (self.b + 0.5 * self.sigma ** 2) * T) / sigma_sqrt_T
        d2 = d1 - sigma_sqrt_T

        df_r = math.exp(-self.r * T)
        df_b = math.exp((self.b - self.r) * T)

        if is_call:
            price = S * df_b * norm_cdf(d1) - X * df_r * norm_cdf(d2)
            delta = df_b * norm_cdf(d1)
        else:
            price = X * df_r * norm_cdf(-d2) - S * df_b * norm_cdf(-d1)
            delta = df_b * (norm_cdf(d1) - 1.0)

        gamma = (df_b * norm_pdf(d1)) / (S * sigma_sqrt_T)

        return {
            "price": float(max(0.0, price)),
            "delta": float(delta),
            "gamma": float(gamma),
            "d1": float(d1),
            "d2": float(d2)
        }

    def critical_price_call(self, X: float, T: float, max_iter: int = 100, tol: float = 1e-6) -> float:
        """Solves for S* (early exercise critical stock price for American Call) via Newton-Raphson."""
        if self.b >= self.r:
            return float('inf')

        sig_sq = self.sigma ** 2
        M = 2.0 * self.r / sig_sq
        N = 2.0 * self.b / sig_sq
        K = 1.0 - math.exp(-self.r * T)

        q2 = (-(N - 1.0) + math.sqrt((N - 1.0) ** 2 + 4.0 * M / K)) / 2.0

        q2_inf = (-(N - 1.0) + math.sqrt((N - 1.0) ** 2 + 4.0 * M)) / 2.0
        S_star_inf = X / (1.0 - 1.0 / q2_inf)
        h2 = -(self.b * T + 2.0 * self.sigma * math.sqrt(T)) * (X / (S_star_inf - X))
        S_seed = X + (S_star_inf - X) * (1.0 - math.exp(h2))
        S_curr = max(X * 1.001, S_seed)

        for _ in range(max_iter):
            bs = self.european_black_scholes(S_curr, X, T, is_call=True)
            c = bs["price"]
            d1 = bs["d1"]
            df_b = math.exp((self.b - self.r) * T)

            lhs = S_curr - X
            rhs = c + (1.0 - df_b * norm_cdf(d1)) * (S_curr / q2)
            f_val = lhs - rhs

            if abs(f_val) < tol:
                return float(S_curr)

            f_prime = 1.0 - df_b * norm_cdf(d1) - (1.0 - df_b * norm_cdf(d1)) / q2 + \
                      (df_b * norm_pdf(d1)) / (q2 * self.sigma * math.sqrt(T))

            if abs(f_prime) < 1e-12:
                break

            S_next = S_curr - f_val / f_prime
            if S_next <= X:
                S_next = (S_curr + X) * 0.5

            if abs(S_next - S_curr) < tol:
                return float(S_next)
            S_curr = S_next

        return float(S_curr)

    def critical_price_put(self, X: float, T: float, max_iter: int = 100, tol: float = 1e-6) -> float:
        """Solves for S** (early exercise critical stock price for American Put) via Newton-Raphson."""
        sig_sq = self.sigma ** 2
        M = 2.0 * self.r / sig_sq
        N = 2.0 * self.b / sig_sq
        K = 1.0 - math.exp(-self.r * T)

        q1 = (-(N - 1.0) - math.sqrt((N - 1.0) ** 2 + 4.0 * M / K)) / 2.0

        q1_inf = (-(N - 1.0) - math.sqrt((N - 1.0) ** 2 + 4.0 * M)) / 2.0
        S_star_inf = X / (1.0 - 1.0 / q1_inf)
        h1 = (self.b * T - 2.0 * self.sigma * math.sqrt(T)) * (X / (X - S_star_inf))
        S_seed = S_star_inf + (X - S_star_inf) * math.exp(h1)
        S_curr = min(X * 0.999, max(1e-4, S_seed))

        for _ in range(max_iter):
            bs = self.european_black_scholes(S_curr, X, T, is_call=False)
            p = bs["price"]
            d1 = bs["d1"]
            df_b = math.exp((self.b - self.r) * T)

            lhs = X - S_curr
            rhs = p - (1.0 - df_b * norm_cdf(-d1)) * (S_curr / q1)
            f_val = lhs - rhs

            if abs(f_val) < tol:
                return float(S_curr)

            f_prime = -1.0 - df_b * (norm_cdf(d1) - 1.0) + (1.0 - df_b * norm_cdf(-d1)) / q1 + \
                      (df_b * norm_pdf(-d1)) / (q1 * self.sigma * math.sqrt(T))

            if abs(f_prime) < 1e-12:
                break

            S_next = S_curr - f_val / f_prime
            if S_next >= X or S_next <= 0.0:
                S_next = S_curr * 0.5

            if abs(S_next - S_curr) < tol:
                return float(S_next)
            S_curr = S_next

        return float(S_curr)

    def price_american_option(
        self,
        S: float,
        X: float,
        T: float,
        is_call: bool = True
    ) -> Dict[str, float]:
        """Evaluates American option price, early exercise premium, and critical boundary."""
        bs = self.european_black_scholes(S, X, T, is_call=is_call)
        euro_price = bs["price"]

        if is_call:
            if self.b >= self.r:
                return {
                    "american_price": euro_price,
                    "european_price": euro_price,
                    "early_exercise_premium": 0.0,
                    "critical_price": float('inf'),
                    "is_early_exercise_optimal": False
                }

            S_star = self.critical_price_call(X, T)
            if S >= S_star:
                amer_price = max(0.0, S - X)
                early_optimal = True
            else:
                sig_sq = self.sigma ** 2
                M = 2.0 * self.r / sig_sq
                N = 2.0 * self.b / sig_sq
                K = 1.0 - math.exp(-self.r * T)
                q2 = (-(N - 1.0) + math.sqrt((N - 1.0) ** 2 + 4.0 * M / K)) / 2.0

                bs_star = self.european_black_scholes(S_star, X, T, is_call=True)
                df_b = math.exp((self.b - self.r) * T)
                A2 = (S_star / q2) * (1.0 - df_b * norm_cdf(bs_star["d1"]))
                amer_price = euro_price + A2 * ((S / S_star) ** q2)
                early_optimal = False

            return {
                "american_price": float(amer_price),
                "european_price": float(euro_price),
                "early_exercise_premium": float(max(0.0, amer_price - euro_price)),
                "critical_price": float(S_star),
                "is_early_exercise_optimal": early_optimal
            }
        else:
            S_star = self.critical_price_put(X, T)
            if S <= S_star:
                amer_price = max(0.0, X - S)
                early_optimal = True
            else:
                sig_sq = self.sigma ** 2
                M = 2.0 * self.r / sig_sq
                N = 2.0 * self.b / sig_sq
                K = 1.0 - math.exp(-self.r * T)
                q1 = (-(N - 1.0) - math.sqrt((N - 1.0) ** 2 + 4.0 * M / K)) / 2.0

                bs_star = self.european_black_scholes(S_star, X, T, is_call=False)
                df_b = math.exp((self.b - self.r) * T)
                A1 = -(S_star / q1) * (1.0 - df_b * norm_cdf(-bs_star["d1"]))
                amer_price = euro_price + A1 * ((S / S_star) ** q1)
                early_optimal = False

            return {
                "american_price": float(amer_price),
                "european_price": float(euro_price),
                "early_exercise_premium": float(max(0.0, amer_price - euro_price)),
                "critical_price": float(S_star),
                "is_early_exercise_optimal": early_optimal
            }


# ==============================================================================
# Model 4: Hayne E. Leland (1985) Option Replication with Transaction Costs Engine
# ==============================================================================
class LelandReplicationTransactionCostEngine:
    """Hayne E. Leland (1985) Option Pricing and Replication with Transaction Costs.
    Computes modified volatility sigma_hat and endogenous option Bid-Ask spreads
    derived from underlying trading friction k and rebalancing frequency dt.
    """

    def __init__(
        self,
        base_volatility: float = 0.20,
        transaction_cost_rate: float = 0.01,
        rebalancing_dt_days: float = 1.0
    ):
        if base_volatility <= 0.0 or transaction_cost_rate < 0.0 or rebalancing_dt_days <= 0.0:
            raise ValueError("Invalid volatility, transaction cost, or rebalancing interval.")

        self.sigma = float(base_volatility)
        self.k = float(transaction_cost_rate)
        self.dt = float(rebalancing_dt_days) / 365.25

    def modified_volatility(self, gamma_sign: int = 1) -> float:
        """Computes Leland's modified volatility:
        sigma_hat^2 = sigma^2 * [ 1 + sign(Gamma) * sqrt(2/pi) * (k / (sigma * sqrt(dt))) ]
        """
        factor = math.sqrt(2.0 / math.pi) * (self.k / (self.sigma * math.sqrt(self.dt)))
        inside = 1.0 + gamma_sign * factor
        if inside <= 1e-6:
            return 1e-3
        return float(self.sigma * math.sqrt(inside))

    def evaluate_leland_option(
        self,
        S: float,
        X: float,
        T: float,
        r: float = 0.04,
        is_call: bool = True
    ) -> Dict[str, float]:
        """Prices Call/Put with Leland modified ask and bid volatilities."""
        sigma_ask = self.modified_volatility(gamma_sign=+1)
        sigma_bid = self.modified_volatility(gamma_sign=-1)

        def bs_price(vol: float) -> float:
            d1 = (math.log(S / X) + (r + 0.5 * vol ** 2) * T) / (vol * math.sqrt(T))
            d2 = d1 - vol * math.sqrt(T)
            if is_call:
                return float(S * norm_cdf(d1) - X * math.exp(-r * T) * norm_cdf(d2))
            else:
                return float(X * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1))

        price_frictionless = bs_price(self.sigma)
        price_ask = bs_price(sigma_ask)
        price_bid = bs_price(sigma_bid)

        option_spread = max(0.0, price_ask - price_bid)

        return {
            "price_frictionless": float(price_frictionless),
            "price_ask": float(price_ask),
            "price_bid": float(price_bid),
            "option_bid_ask_spread": float(option_spread),
            "sigma_ask": float(sigma_ask),
            "sigma_bid": float(sigma_bid),
            "volatility_spread": float(sigma_ask - sigma_bid)
        }

    def total_expected_transaction_costs(
        self,
        S: float,
        X: float,
        T: float,
        r: float = 0.04
    ) -> float:
        """Computes the expected cumulative hedging transactions costs over [0, T]."""
        res = self.evaluate_leland_option(S, X, T, r=r, is_call=True)
        return float(res["price_ask"] - res["price_frictionless"])


# ==============================================================================
# Model 5: Andrew W. Lo & A. Craig MacKinlay (1988, 1997) Variance Ratio Engine
# ==============================================================================
class LoMacKinlayVarianceRatioEngine:
    """Lo & MacKinlay (1988) Variance Ratio Specification Test for the Random Walk Hypothesis.
    Calculates homoskedastic test statistic z(q) and heteroskedasticity-robust z*(q).
    """

    def __init__(self, log_prices: np.ndarray):
        p = np.array(log_prices, dtype=float)
        if len(p) < 20:
            raise ValueError("Log prices must contain at least 20 observations.")
        self.p = p
        self.nq = len(p) - 1
        self.returns = np.diff(p)
        self.mu = (p[-1] - p[0]) / float(self.nq)

        demeaned_r = self.returns - self.mu
        self.sigma_a_sq = float(np.sum(demeaned_r ** 2) / (self.nq - 1.0))

    def compute_variance_ratio(self, q: int) -> Dict[str, Any]:
        """Evaluates VR(q) = sigma_c^2(q) / sigma_a^2, z(q) [RW1], and z*(q) [RW3]."""
        if q < 2 or q >= self.nq:
            raise ValueError(f"Lag q must satisfy 2 <= q < {self.nq}.")

        nq = self.nq
        p = self.p
        mu = self.mu

        q_returns = p[q:] - p[:-q] - q * mu
        m = float(q * (nq - q + 1.0) * (1.0 - float(q) / float(nq)))
        sigma_c_sq = float(np.sum(q_returns ** 2) / m)

        vr = float(sigma_c_sq / self.sigma_a_sq) if self.sigma_a_sq > 0.0 else 1.0

        # 1. Homoskedastic Asymptotic Test Statistic z(q) under RW1
        theta_homo = (2.0 * (2.0 * q - 1.0) * (q - 1.0)) / (3.0 * q * nq)
        z_homo = (vr - 1.0) / math.sqrt(theta_homo)
        p_val_homo = 2.0 * (1.0 - norm_cdf(abs(z_homo)))

        # 2. Heteroskedastic-Robust Asymptotic Test Statistic z*(q) under RW3
        demeaned_r = self.returns - mu
        sum_sq = np.sum(demeaned_r ** 2)

        theta_hetero = 0.0
        for j in range(1, q):
            weight = ((2.0 * (q - j)) / float(q)) ** 2
            cross_sq = np.sum((demeaned_r[j:] ** 2) * (demeaned_r[:-j] ** 2))
            delta_j = cross_sq / (sum_sq ** 2)
            theta_hetero += weight * delta_j

        z_hetero = (vr - 1.0) / math.sqrt(theta_hetero) if theta_hetero > 0.0 else 0.0
        p_val_hetero = 2.0 * (1.0 - norm_cdf(abs(z_hetero)))

        return {
            "q_lag": q,
            "variance_ratio": vr,
            "z_homoskedastic": float(z_homo),
            "p_value_homoskedastic": float(p_val_homo),
            "z_heteroskedastic_robust": float(z_hetero),
            "p_value_heteroskedastic_robust": float(p_val_hetero),
            "is_random_walk_rejected_5pct": bool(p_val_hetero < 0.05),
            "market_state": "Mean-Reverting" if vr < 0.95 else ("Trending/Momentum" if vr > 1.05 else "Random Walk")
        }

    def multi_horizon_profile(self, q_list: List[int]) -> List[Dict[str, Any]]:
        """Computes variance ratio profile across multiple horizons."""
        return [self.compute_variance_ratio(q) for q in q_list]


# ==============================================================================
# Model 6: Lars E.O. Svensson (1994, 1995) 6-Parameter Term Structure Engine
# ==============================================================================
class SvenssonTermStructureEngine:
    """Svensson (1994, 1995) 6-Parameter Term Structure & Forward Rate Engine:
    y(m) = beta0 + beta1*((1 - exp(-m/tau1))/(m/tau1)) +
           beta2*(((1 - exp(-m/tau1))/(m/tau1)) - exp(-m/tau1)) +
           beta3*(((1 - exp(-m/tau2))/(m/tau2)) - exp(-m/tau2))
    """

    def __init__(
        self,
        beta0: float = 0.06,
        beta1: float = -0.02,
        beta2: float = 0.03,
        beta3: float = -0.015,
        tau1: float = 1.5,
        tau2: float = 6.0
    ):
        if tau1 <= 0.0 or tau2 <= 0.0:
            raise ValueError("Decay parameters tau1 and tau2 must be strictly positive.")

        self.beta0 = float(beta0)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.beta3 = float(beta3)
        self.tau1 = float(tau1)
        self.tau2 = float(tau2)

    def spot_yield(self, maturity: float) -> float:
        """Calculates zero-coupon spot yield y(m)."""
        if maturity <= 1e-6:
            return self.beta0 + self.beta1

        m = float(maturity)
        t1 = m / self.tau1
        t2 = m / self.tau2

        factor1 = (1.0 - math.exp(-t1)) / t1
        factor2 = factor1 - math.exp(-t1)
        factor3 = (1.0 - math.exp(-t2)) / t2 - math.exp(-t2)

        return float(self.beta0 + self.beta1 * factor1 + self.beta2 * factor2 + self.beta3 * factor3)

    def instantaneous_forward_rate(self, maturity: float) -> float:
        """Calculates instantaneous forward rate f(m) = y(m) + m * y'(m)."""
        if maturity <= 1e-6:
            return self.beta0 + self.beta1

        m = float(maturity)
        exp1 = math.exp(-m / self.tau1)
        exp2 = math.exp(-m / self.tau2)

        term1 = self.beta1 * exp1
        term2 = self.beta2 * (m / self.tau1) * exp1
        term3 = self.beta3 * (m / self.tau2) * exp2

        return float(self.beta0 + term1 + term2 + term3)

    def discount_factor(self, maturity: float) -> float:
        """Calculates zero coupon bond price P(0, m) = exp(-m * y(m))."""
        if maturity <= 0.0:
            return 1.0
        y = self.spot_yield(maturity)
        return float(math.exp(-maturity * y))

    def generate_yield_curve(self, maturities: List[float]) -> Dict[str, Any]:
        """Generates full yield, forward and discount factor vectors."""
        yields = [self.spot_yield(m) for m in maturities]
        forwards = [self.instantaneous_forward_rate(m) for m in maturities]
        discounts = [self.discount_factor(m) for m in maturities]

        return {
            "maturities": maturities,
            "spot_yields": yields,
            "forward_rates": forwards,
            "discount_factors": discounts,
            "asymptotic_yield": self.beta0,
            "short_rate_y0": self.beta0 + self.beta1
        }

    @classmethod
    def fit_svensson(
        cls,
        maturities: np.ndarray,
        yields: np.ndarray,
        fixed_tau1: float = 1.5,
        fixed_tau2: float = 6.0
    ) -> "SvenssonTermStructureEngine":
        """Fits Svensson parameters via linear regression on loadings for fixed tau1, tau2."""
        m = np.array(maturities, dtype=float)
        y = np.array(yields, dtype=float)

        t1 = m / fixed_tau1
        t2 = m / fixed_tau2

        f1 = (1.0 - np.exp(-t1)) / t1
        f2 = f1 - np.exp(-t1)
        f3 = (1.0 - np.exp(-t2)) / t2 - np.exp(-t2)
        f0 = np.ones_like(m)

        X = np.column_stack([f0, f1, f2, f3])
        betas = np.linalg.pinv(X.T @ X) @ (X.T @ y)

        return cls(
            beta0=betas[0],
            beta1=betas[1],
            beta2=betas[2],
            beta3=betas[3],
            tau1=fixed_tau1,
            tau2=fixed_tau2
        )


# ==============================================================================
# PYTEST TEST SUITE FOR FAZ 55 QUANTITATIVE ENGINES
# ==============================================================================
class TestFaz55QuantitativeFinanceEngines:
    """Rigorous programmatic verification suite for Faz 55 models."""

    def test_glosten_milgrom_microstructure_engine(self):
        """Verifies Glosten & Milgrom (1985) sequential trade microstructure model."""
        gm_zero_info = GlostenMilgromMicrostructureEngine(
            value_low=100.0,
            value_high=200.0,
            prior_high=0.5,
            informed_fraction=0.0
        )
        quotes_zero = gm_zero_info.compute_quotes()
        assert math.isclose(quotes_zero["spread"], 0.0, abs_tol=1e-8)
        assert math.isclose(quotes_zero["ask_price"], quotes_zero["bid_price"], abs_tol=1e-8)
        assert math.isclose(quotes_zero["ask_price"], 150.0, abs_tol=1e-8)

        gm = GlostenMilgromMicrostructureEngine(
            value_low=100.0,
            value_high=200.0,
            prior_high=0.5,
            informed_fraction=0.35
        )
        quotes = gm.compute_quotes()
        assert quotes["spread"] > 5.0
        assert quotes["ask_price"] > quotes["expected_value"] > quotes["bid_price"]

        sim = gm.simulate_sequence(n_trades=120, true_state="H", seed=42)
        assert sim["is_converged_to_true_state"], f"Final belief {sim['final_belief']} did not converge toward 1.0"
        assert sim["final_belief"] > 0.85

    def test_bekk_garch_covariance_engine(self):
        """Verifies Engle & Kroner (1995) BEKK-GARCH(1,1) positive definite dynamics."""
        K = 2
        C = np.array([[0.05, 0.0],
                      [0.02, 0.04]])
        A = np.array([[0.20, 0.05],
                      [0.02, 0.25]])
        B = np.array([[0.90, 0.02],
                      [0.01, 0.88]])

        bekk = BEKKGARCHCovarianceEngine(C_matrix=C, A_matrix=A, B_matrix=B)
        assert bekk.is_positive_definite(bekk.Omega)

        np.random.seed(123)
        T_steps = 50
        shocks = np.random.normal(0.0, 0.02, size=(T_steps, K))
        res = bekk.filter_covariance_trajectory(shocks)

        assert res["all_positive_definite"], "All BEKK covariance matrices must be strictly positive definite."
        assert len(res["covariance_history"]) == T_steps

        corrs = res["correlation_history"]
        for corr_mat in corrs:
            assert np.all(corr_mat >= -1.0 - 1e-6) and np.all(corr_mat <= 1.0 + 1e-6)
            assert math.isclose(corr_mat[0, 0], 1.0, abs_tol=1e-6)

        spillovers = bekk.measure_volatility_spillovers()
        assert spillovers["max_cross_spillover"] > 0.0

    def test_barone_adesi_whaley_american_option_engine(self):
        """Verifies Barone-Adesi & Whaley (1987) American Option pricing and early exercise boundary."""
        baw = BaroneAdesiWhaleyAmericanOptionEngine(
            risk_free_rate=0.06,
            dividend_yield=0.03,
            volatility=0.20
        )

        S = 100.0
        X = 100.0
        T = 0.5

        put_res = baw.price_american_option(S, X, T, is_call=False)
        assert put_res["american_price"] >= put_res["european_price"], "American put price must be >= European put."
        assert put_res["early_exercise_premium"] >= 0.0
        assert put_res["critical_price"] < X, f"Put critical boundary S** {put_res['critical_price']} must be below strike {X}."

        put_deep_itm = baw.price_american_option(S=50.0, X=100.0, T=0.5, is_call=False)
        assert put_deep_itm["is_early_exercise_optimal"], "Deep ITM Put must trigger early exercise."
        assert math.isclose(put_deep_itm["american_price"], 50.0, abs_tol=1e-4)

        call_res = baw.price_american_option(S, X, T, is_call=True)
        assert call_res["american_price"] >= call_res["european_price"]
        assert call_res["critical_price"] > X, f"Call critical boundary S* {call_res['critical_price']} must be above strike {X}."

        baw_no_div = BaroneAdesiWhaleyAmericanOptionEngine(risk_free_rate=0.05, dividend_yield=0.0, volatility=0.20)
        call_no_div = baw_no_div.price_american_option(S=100.0, X=100.0, T=0.5, is_call=True)
        assert math.isclose(call_no_div["american_price"], call_no_div["european_price"], rel_tol=1e-5)
        assert math.isclose(call_no_div["early_exercise_premium"], 0.0, abs_tol=1e-8)

    def test_leland_replication_transaction_cost_engine(self):
        """Verifies Leland (1985) transaction costs option replication and modified volatility."""
        leland = LelandReplicationTransactionCostEngine(
            base_volatility=0.20,
            transaction_cost_rate=0.015,
            rebalancing_dt_days=1.0
        )

        sigma_ask = leland.modified_volatility(gamma_sign=+1)
        sigma_bid = leland.modified_volatility(gamma_sign=-1)

        assert sigma_ask > 0.20 > sigma_bid, f"Expected sigma_ask > 0.20 > sigma_bid, got {sigma_ask}, {sigma_bid}"

        S = 100.0
        X = 100.0
        T = 0.5
        res = leland.evaluate_leland_option(S, X, T, r=0.04, is_call=True)

        assert res["price_ask"] > res["price_frictionless"] > res["price_bid"], \
            f"Expected Ask > Frictionless > Bid, got {res['price_ask']}, {res['price_frictionless']}, {res['price_bid']}"
        assert res["option_bid_ask_spread"] > 0.0

        leland_zero = LelandReplicationTransactionCostEngine(base_volatility=0.20, transaction_cost_rate=0.0, rebalancing_dt_days=1.0)
        res_zero = leland_zero.evaluate_leland_option(S, X, T, r=0.04, is_call=True)
        assert math.isclose(res_zero["option_bid_ask_spread"], 0.0, abs_tol=1e-8)
        assert math.isclose(res_zero["price_ask"], res_zero["price_frictionless"], abs_tol=1e-8)

    def test_lo_mackinlay_variance_ratio_engine(self):
        """Verifies Lo & MacKinlay (1988) Variance Ratio Test under RW1 and RW3."""
        np.random.seed(99)
        n = 1000

        iid_shocks = np.random.normal(0.0005, 0.01, size=n)
        rw_log_prices = np.cumsum(iid_shocks) + 4.60

        vr_engine = LoMacKinlayVarianceRatioEngine(rw_log_prices)
        vr_2 = vr_engine.compute_variance_ratio(q=2)

        assert math.isclose(vr_2["variance_ratio"], 1.0, abs_tol=0.15)
        assert not vr_2["is_random_walk_rejected_5pct"]

        ou_prices = np.zeros(n)
        x = 0.0
        for i in range(1, n):
            x = x * 0.5 + np.random.normal(0.0, 0.01)
            ou_prices[i] = 4.60 + x

        vr_engine_mr = LoMacKinlayVarianceRatioEngine(ou_prices)
        vr_mr = vr_engine_mr.compute_variance_ratio(q=5)

        assert vr_mr["variance_ratio"] < 0.60
        assert vr_mr["is_random_walk_rejected_5pct"]
        assert vr_mr["market_state"] == "Mean-Reverting"

    def test_svensson_term_structure_engine(self):
        """Verifies Svensson (1994, 1995) 6-parameter yield curve and forward rates."""
        svensson = SvenssonTermStructureEngine(
            beta0=0.05,
            beta1=-0.02,
            beta2=0.04,
            beta3=-0.02,
            tau1=1.5,
            tau2=6.0
        )

        assert math.isclose(svensson.spot_yield(0.0), 0.03, rel_tol=1e-5)
        assert math.isclose(svensson.spot_yield(100.0), 0.05, abs_tol=0.002)

        assert math.isclose(svensson.instantaneous_forward_rate(0.0), 0.03, rel_tol=1e-5)

        maturities = [0.25, 1.0, 2.0, 5.0, 10.0, 30.0]
        curve = svensson.generate_yield_curve(maturities)

        discounts = curve["discount_factors"]
        assert all(0.0 < d <= 1.0 for d in discounts)
        assert discounts[0] > discounts[1] > discounts[2] > discounts[3] > discounts[4] > discounts[5]

        fitted = SvenssonTermStructureEngine.fit_svensson(
            maturities=np.array(maturities),
            yields=np.array(curve["spot_yields"]),
            fixed_tau1=1.5,
            fixed_tau2=6.0
        )
        fitted_curve = fitted.generate_yield_curve(maturities)
        np.testing.assert_allclose(fitted_curve["spot_yields"], curve["spot_yields"], atol=1e-5)
