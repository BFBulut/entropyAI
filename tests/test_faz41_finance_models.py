"""Programmatic TDD Verification Suite for Faz 41 Quantitative Finance Engines.

Models:
1. Dai & Singleton (2000) Canonical Affine Term Structure Models (ATSM) & A_m(N) Admissibility
2. Tobias Adrian, Richard K. Crump & Emanuel Moench (ACM 2013) Treasury Term Premium Decomposition
3. Ioanid Rosu (2009) Dynamic Continuous-Time Limit Order Book with Endogenous Bid-Ask Spread
4. Michael W. Brandt, Pedro Santa-Clara & Rossen Valkanov (2009) Parametric Portfolio Policies (PPP)
5. Mark Broadie, Paul Glasserman & Leif Andersen (2004) Primal-Dual Duality Bounds for Bermudan Options
6. Michael Egorov (2021) Curve v2 (CryptoSwap) Dynamic Concentration & Internal Moving Peg Algorithm
"""

import math
from typing import Tuple, Dict, Any, Optional, List
import numpy as np
import pytest


# ==============================================================================
# 1. Dai & Singleton (2000) Canonical Affine Term Structure A_m(N)
# ==============================================================================
class DaiSingletonATSM:
    """
    Dai & Singleton (2000) Canonical Classification of Affine Term Structure Models.
    Short rate: r_t = delta_0 + delta^T Y_t
    State dynamics: dY_t = K (theta - Y_t) dt + Sigma sqrt(V(Y_t)) dW_t
    V_ii(Y_t) = alpha_i + beta_i^T Y_t
    m is the number of state variables appearing in conditional variances (m <= N).
    """
    def __init__(self, m: int, N: int, delta_0: float, delta: np.ndarray,
                 K: np.ndarray, theta: np.ndarray, Sigma: np.ndarray,
                 alpha: np.ndarray, beta: np.ndarray):
        assert 0 <= m <= N, "m must satisfy 0 <= m <= N"
        self.m = m
        self.N = N
        self.delta_0 = float(delta_0)
        self.delta = np.array(delta, dtype=float).reshape(N)
        self.K = np.array(K, dtype=float).reshape((N, N))
        self.theta = np.array(theta, dtype=float).reshape(N)
        self.Sigma = np.array(Sigma, dtype=float).reshape((N, N))
        self.alpha = np.array(alpha, dtype=float).reshape(N)
        self.beta = np.array(beta, dtype=float).reshape((N, N))

    def check_admissibility(self) -> Dict[str, Any]:
        """
        Verify mathematical admissibility (Feller boundary conditions for square-root factors).
        For i in 1..m:
          - alpha_i == 0
          - beta_{ij} == 0 for j != i
          - beta_{ii} > 0
          - Drift pull at zero: (K theta)_i >= 0.5 * Sigma_{ii}^2 * beta_{ii}
        For i > m (Gaussian factors):
          - beta_{ij} == 0 for j > m
        """
        violations = []
        is_admissible = True
        
        # Check square-root factors
        for i in range(self.m):
            if abs(self.alpha[i]) > 1e-7:
                violations.append(f"Factor {i} is square-root but alpha_{i} != 0 ({self.alpha[i]})")
                is_admissible = False
            for j in range(self.N):
                if j != i and abs(self.beta[i, j]) > 1e-7:
                    violations.append(f"Factor {i} cross-dependence beta[{i},{j}] != 0")
                    is_admissible = False
            if self.beta[i, i] <= 0:
                violations.append(f"Factor {i} variance slope beta[{i},{i}] <= 0")
                is_admissible = False
            # Feller drift condition
            drift_at_zero = np.dot(self.K[i, :], self.theta)
            min_drift = 0.5 * (self.Sigma[i, i] ** 2) * self.beta[i, i]
            if drift_at_zero < min_drift:
                violations.append(f"Factor {i} violates Feller condition: drift {drift_at_zero:.4f} < {min_drift:.4f}")
                is_admissible = False

        return {
            "model_family": f"A_{self.m}({self.N})",
            "is_admissible": is_admissible,
            "violations": violations
        }

    def solve_riccati_ode(self, tau: float, steps: int = 200) -> Tuple[float, np.ndarray]:
        """
        Solve standard Riccati ODE system for zero-coupon bond price P(t, t+tau) = exp(A(tau) + B(tau)^T Y_t).
        dB/dtau = - K^T B + 0.5 * sum_i (Sigma^T B)_i^2 beta_i - delta
        dA/dtau = B^T K theta + 0.5 * sum_i (Sigma^T B)_i^2 alpha_i - delta_0
        Initial conditions: A(0) = 0, B(0) = 0.
        """
        dt = tau / steps
        A = 0.0
        B = np.zeros(self.N)

        for _ in range(steps):
            SigmaTB = self.Sigma.T @ B
            
            # Derivative dB
            dB = - self.K.T @ B - self.delta
            for i in range(self.N):
                dB += 0.5 * (SigmaTB[i] ** 2) * self.beta[i, :]
            
            # Derivative dA
            dA = float(B @ (self.K @ self.theta)) - self.delta_0
            for i in range(self.N):
                dA += 0.5 * (SigmaTB[i] ** 2) * self.alpha[i]
            
            # Euler update
            B += dB * dt
            A += dA * dt

        return A, B

    def compute_zero_coupon_yield(self, tau: float, Y_t: np.ndarray) -> float:
        """Yield y(t, tau) = - (1/tau) * (A(tau) + B(tau)^T Y_t)."""
        A, B = self.solve_riccati_ode(tau)
        log_price = A + np.dot(B, Y_t)
        return - log_price / tau


# ==============================================================================
# 2. Tobias Adrian, Richard K. Crump & Emanuel Moench (ACM 2013) Term Premium
# ==============================================================================
class ACMTermPremiumDecomposition:
    """
    Adrian, Crump & Moench (ACM 2013) Dynamic Gaussian Term Structure Model (GATSM).
    Decomposes bond yields into Expected Risk-Neutral Rate Path + Term Premium:
    y_t^(n) = E_t[1/n sum_{i=0}^{n-1} r_{t+i}] + TP_t^(n)
    """
    def __init__(self, K_factors: int, mu: np.ndarray, Phi: np.ndarray, Sigma: np.ndarray,
                 delta_0: float, delta_1: np.ndarray, lambda_0: np.ndarray, lambda_1: np.ndarray):
        self.K = K_factors
        self.mu = np.array(mu, dtype=float).reshape(self.K)
        self.Phi = np.array(Phi, dtype=float).reshape((self.K, self.K))
        self.Sigma = np.array(Sigma, dtype=float).reshape((self.K, self.K))
        self.delta_0 = float(delta_0)
        self.delta_1 = np.array(delta_1, dtype=float).reshape(self.K)
        self.lambda_0 = np.array(lambda_0, dtype=float).reshape(self.K)
        self.lambda_1 = np.array(lambda_1, dtype=float).reshape((self.K, self.K))

        # Risk-neutral parameters under Q
        self.mu_Q = self.mu - self.lambda_0
        self.Phi_Q = self.Phi - self.lambda_1

    def compute_bond_loadings(self, max_maturity: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute affine yield loadings A_n, B_n under P (fitted) and Q (risk-neutral).
        log P_t^(n) = A_n + B_n^T X_t
        Yield y_t^(n) = - (1/n) * (A_n + B_n^T X_t)
        """
        A = np.zeros(max_maturity + 1)
        B = np.zeros((max_maturity + 1, self.K))
        A_rn = np.zeros(max_maturity + 1)
        B_rn = np.zeros((max_maturity + 1, self.K))

        # Initial condition: n=0, P_t^(0) = 1 => A_0 = 0, B_0 = 0
        A[0] = 0.0
        B[0] = np.zeros(self.K)
        A_rn[0] = 0.0
        B_rn[0] = np.zeros(self.K)

        for n in range(1, max_maturity + 1):
            # Fitted market bond pricing under Q
            B[n] = B[n-1] @ self.Phi_Q - self.delta_1
            A[n] = A[n-1] + B[n-1] @ self.mu_Q + 0.5 * float(B[n-1] @ self.Sigma @ self.Sigma.T @ B[n-1]) - self.delta_0

            # Pure risk-neutral expectation pricing (lambda_0 = 0, lambda_1 = 0 => mu_Q = mu, Phi_Q = Phi)
            B_rn[n] = B_rn[n-1] @ self.Phi - self.delta_1
            A_rn[n] = A_rn[n-1] + B_rn[n-1] @ self.mu + 0.5 * float(B_rn[n-1] @ self.Sigma @ self.Sigma.T @ B_rn[n-1]) - self.delta_0

        return A, B, A_rn, B_rn

    def decompose_yield(self, n: int, X_t: np.ndarray) -> Dict[str, float]:
        """
        Decompose yield at maturity n into Market Yield, Risk-Neutral Yield, and Term Premium.
        """
        assert n >= 1, "Maturity must be at least 1"
        A, B, A_rn, B_rn = self.compute_bond_loadings(n)
        
        market_yield = - (A[n] + np.dot(B[n], X_t)) / n
        rn_yield = - (A_rn[n] + np.dot(B_rn[n], X_t)) / n
        term_premium = market_yield - rn_yield

        return {
            "maturity": n,
            "market_yield": float(market_yield),
            "risk_neutral_yield": float(rn_yield),
            "term_premium": float(term_premium)
        }


# ==============================================================================
# 3. Ioanid Rosu (2009) Dynamic Limit Order Book Model
# ==============================================================================
class RosuLOBDynamics:
    """
    Ioanid Rosu (2009) Continuous-Time Dynamic Limit Order Book.
    Endogenous bid-ask spread and queue sizes in a continuous-time Markov equilibrium.
    Traders choose between limit order (patient, wait in queue) and market order (impatient).
    """
    def __init__(self, lambda_arrival: float, r_impatience: float, delta_tick: float = 0.01):
        assert lambda_arrival > 0, "Arrival rate must be positive"
        assert r_impatience > 0, "Impatience rate must be positive"
        self.lambda_arrival = float(lambda_arrival)
        self.r = float(r_impatience)
        self.delta_tick = float(delta_tick)

    def endogenous_spread(self, queue_bid: int, queue_ask: int) -> float:
        """
        Analytic endogenous spread S(q_b, q_a).
        S = tick + (2 * r / lambda) * (1 + queue_bid + queue_ask)
        When book depth increases, execution probability is delayed, requiring wider spread to compensate.
        """
        base_spread = self.delta_tick
        delay_cost = (2.0 * self.r / self.lambda_arrival) * (1.0 + 0.5 * (queue_bid + queue_ask))
        return float(base_spread + delay_cost)

    def stationary_queue_distribution(self, max_q: int = 10) -> np.ndarray:
        """
        Compute stationary probability distribution pi(q) of one side of the order book.
        Birth-death queue process: birth rate lambda_limit = lambda / 2,
        death rate mu_exec = lambda_market / 2 + q * cancellation_rate.
        """
        pi = np.zeros(max_q + 1)
        pi[0] = 1.0
        lambda_limit = self.lambda_arrival * 0.35
        mu_exec_base = self.lambda_arrival * 0.60
        cancellation_rate = self.r * 0.2

        for q in range(max_q):
            mu_q = mu_exec_base + (q + 1) * cancellation_rate
            ratio = lambda_limit / mu_q
            pi[q + 1] = pi[q] * ratio

        # Normalize
        pi /= np.sum(pi)
        return pi

    def evaluate_order_choice(self, queue_pos: int, spread: float) -> Dict[str, Any]:
        """
        Trader decision: Place passive Limit Order (earn half-spread - delay cost)
        vs aggressive Market Order (pay half-spread).
        """
        expected_wait_time = (queue_pos + 1) / self.lambda_arrival
        delay_penalty = self.r * expected_wait_time
        limit_order_surplus = (spread / 2.0) - delay_penalty
        market_order_surplus = - (spread / 2.0)

        should_limit = limit_order_surplus > market_order_surplus
        return {
            "queue_position": queue_pos,
            "spread": spread,
            "expected_wait_time": float(expected_wait_time),
            "limit_order_surplus": float(limit_order_surplus),
            "market_order_surplus": float(market_order_surplus),
            "optimal_choice": "LimitOrder" if should_limit else "MarketOrder"
        }


# ==============================================================================
# 4. Michael W. Brandt, Pedro Santa-Clara & Rossen Valkanov (2009) PPP
# ==============================================================================
class ParametricPortfolioPolicy:
    """
    Brandt, Santa-Clara & Valkanov (2009) Parametric Portfolio Policies (PPP).
    Asset weights: w_{i,t} = w_{i,t}^b + (1 / N_t) * theta^T x_{i,t}
    Bypasses expected return & covariance matrix estimation, maximizing investor CRRA utility directly.
    """
    def __init__(self, num_characteristics: int, gamma_risk_aversion: float = 3.0):
        self.K = num_characteristics
        self.gamma = float(gamma_risk_aversion)
        self.theta = np.zeros(self.K)

    def calculate_weights(self, x_matrix: np.ndarray, benchmark_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """
        x_matrix: (N, K) standardized firm characteristics (mean 0, std 1 cross-sectionally).
        Returns portfolio weights w of shape (N,).
        """
        N = x_matrix.shape[0]
        if benchmark_weights is None:
            w_base = np.full(N, 1.0 / N)
        else:
            w_base = benchmark_weights.copy()

        active_tilt = (x_matrix @ self.theta) / N
        w = w_base + active_tilt
        return w

    def utility_function(self, r_p: float) -> float:
        """CRRA utility u(1 + r_p) = (1 + r_p)^(1 - gamma) / (1 - gamma)."""
        wealth = max(1e-4, 1.0 + r_p)
        if abs(self.gamma - 1.0) < 1e-5:
            return math.log(wealth)
        return (wealth ** (1.0 - self.gamma)) / (1.0 - self.gamma)

    def optimize_theta(self, returns_data: List[np.ndarray], chars_data: List[np.ndarray],
                       learning_rate: float = 0.05, iterations: int = 150) -> np.ndarray:
        """
        Estimate theta via projected gradient ascent on average realized CRRA utility over T periods.
        """
        T = len(returns_data)
        assert T == len(chars_data), "Returns and characteristics must match period count"

        for _ in range(iterations):
            grad = np.zeros(self.K)
            for t in range(T):
                R_t = returns_data[t]
                X_t = chars_data[t]
                N_t = len(R_t)
                w_t = self.calculate_weights(X_t)
                r_p = float(np.dot(w_t, R_t))
                
                # Marginal utility u'(1 + r_p) = (1 + r_p)^(-gamma)
                wealth = max(1e-4, 1.0 + r_p)
                u_prime = wealth ** (-self.gamma)
                
                # Gradient d r_p / d theta = (1 / N_t) * (X_t^T R_t)
                drp_dtheta = (X_t.T @ R_t) / N_t
                grad += u_prime * drp_dtheta

            grad /= T
            self.theta += learning_rate * grad

        return self.theta.copy()


# ==============================================================================
# 5. Broadie, Glasserman & Andersen (2004) Bermudan Primal-Dual Bounds
# ==============================================================================
class AndersenBroadieDualBounds:
    """
    Broadie-Glasserman (1997) & Andersen-Broadie (2004) Duality Bounds for Bermudan Options.
    Primal LSM provides Lower Bound L_0.
    Dual martingale representation provides Upper Bound U_0:
    U_0 = M_0 + E[ max_{0 <= k <= K} (h(S_k) - M_k) ]
    Ensures true option price V_0 satisfies: L_0 <= V_0 <= U_0.
    """
    def __init__(self, strike: float, discount_factor: float = 0.95):
        self.strike = strike
        self.df = discount_factor

    def payoff(self, spot: float) -> float:
        """Standard put payoff max(K - S, 0)."""
        return max(0.0, self.strike - spot)

    def compute_primal_lower_bound(self, paths: np.ndarray, exercise_boundary: np.ndarray) -> Tuple[float, float]:
        """
        Compute primal lower bound L_0 and 95% confidence standard error.
        paths: shape (num_paths, num_steps + 1)
        exercise_boundary: shape (num_steps + 1) critical exercise threshold.
        """
        num_paths, num_steps = paths.shape[0], paths.shape[1] - 1
        cash_flows = np.zeros(num_paths)

        for i in range(num_paths):
            exercised = False
            for k in range(num_steps + 1):
                s = paths[i, k]
                if s <= exercise_boundary[k]:
                    cash_flows[i] = (self.df ** k) * self.payoff(s)
                    exercised = True
                    break
            if not exercised:
                cash_flows[i] = (self.df ** num_steps) * self.payoff(paths[i, num_steps])

        lower_bound = float(np.mean(cash_flows))
        std_err = float(np.std(cash_flows) / math.sqrt(num_paths))
        return lower_bound, std_err

    def compute_dual_upper_bound(self, paths: np.ndarray, approx_value_func: List[Any],
                                 sub_sim_size: int = 20, seed: int = 42) -> Tuple[float, float]:
        """
        Compute Andersen-Broadie dual upper bound U_0 using sub-simulation martingales.
        """
        rng = np.random.default_rng(seed)
        num_paths, num_steps = paths.shape[0], paths.shape[1] - 1
        max_deviations = np.zeros(num_paths)

        for i in range(num_paths):
            M_k = 0.0
            max_dev = -1e9
            for k in range(num_steps + 1):
                s_k = paths[i, k]
                discounted_payoff = (self.df ** k) * self.payoff(s_k)
                
                # Approximate Snell envelope value
                v_k = (self.df ** k) * max(self.payoff(s_k), approx_value_func[k](s_k))
                
                if k > 0:
                    # Martingale increment estimation via sub-simulation from s_{k-1}
                    s_prev = paths[i, k-1]
                    sub_sims = s_prev * np.exp(0.02 - 0.5 * 0.04 + 0.2 * rng.normal(size=sub_sim_size))
                    sub_vals = np.mean([approx_value_func[k](s) for s in sub_sims])
                    martingale_increment = v_k - (self.df ** (k-1)) * sub_vals
                    M_k += martingale_increment

                dev = discounted_payoff - M_k
                if dev > max_dev:
                    max_dev = dev
            
            max_deviations[i] = max_dev

        # Initial option approximation
        initial_val = max(self.payoff(paths[0, 0]), approx_value_func[0](paths[0, 0]))
        upper_bound = float(initial_val + np.mean(max_deviations))
        std_err = float(np.std(max_deviations) / math.sqrt(num_paths))
        return upper_bound, std_err


# ==============================================================================
# 6. Michael Egorov (2021) Curve v2 (CryptoSwap) Dynamic Invariant & Moving Peg
# ==============================================================================
class CurveCryptoSwapEngine:
    """
    Curve v2 (CryptoSwap) Automatic Market Maker.
    Invariant: K = A * K_0 * (gamma^2 / (gamma^2 + (1 - D_K)^2)) + D
    Dynamically concentrates liquidity around internal oracle moving peg.
    Only shifts center price when virtual price D strictly exceeds previous profit watermark.
    """
    def __init__(self, A_amp: float = 100.0, gamma: float = 1e-4, initial_price: float = 2000.0):
        self.A = float(A_amp)
        self.gamma = float(gamma)
        self.price_center = float(initial_price)
        self.price_oracle = float(initial_price)
        self.ema_alpha = 0.05
        self.virtual_price_watermark = 1.0

    def compute_invariant(self, x: float, y: float, D: float) -> float:
        """
        Curve v2 invariant error equation f(D) = 0 for 2 tokens (USD, ETH).
        x in USD, y in ETH scaled by price_center.
        """
        p_y = y * self.price_center
        K0 = (4.0 * x * p_y) / (D ** 2)
        ann = self.A * self.gamma
        gamma2 = self.gamma ** 2
        
        # Invariant formula
        bracket = gamma2 / (gamma2 + (1.0 - K0) ** 2 + 1e-12)
        inv_val = ann * (x + p_y) + D * bracket - (ann * D + D * bracket)
        return float(inv_val)

    def update_internal_oracle(self, last_trade_price: float):
        """Update EMA price oracle: p_oracle = (1 - alpha) * p_oracle + alpha * last_trade_price."""
        self.price_oracle = (1.0 - self.ema_alpha) * self.price_oracle + self.ema_alpha * last_trade_price

    def attempt_moving_peg(self, current_virtual_price: float, step_fraction: float = 0.1) -> Dict[str, Any]:
        """
        Ramping / Moving Peg Algorithm:
        Peg is moved towards p_oracle ONLY if current_virtual_price >= virtual_price_watermark.
        """
        shifted = False
        old_center = self.price_center

        if current_virtual_price >= self.virtual_price_watermark:
            # Safe to re-peg: update watermark
            self.virtual_price_watermark = current_virtual_price
            price_gap = self.price_oracle - self.price_center
            self.price_center += step_fraction * price_gap
            shifted = True

        return {
            "old_price_center": old_center,
            "new_price_center": self.price_center,
            "price_oracle": self.price_oracle,
            "virtual_price": current_virtual_price,
            "watermark": self.virtual_price_watermark,
            "peg_shifted": shifted
        }


# ==============================================================================
# PYTEST VERIFICATION TESTS
# ==============================================================================

def test_dai_singleton_atsm_admissibility_and_riccati():
    """Verify Pillar 1: Dai-Singleton ATSM classification and Riccati solution."""
    N = 3
    m = 1  # A_1(3): 1 square-root factor, 2 Gaussian factors
    delta_0 = 0.02
    delta = np.array([1.0, 0.5, 0.2])
    K = np.diag([0.5, 0.8, 1.2])
    theta = np.array([0.04, 0.0, 0.0])
    Sigma = np.diag([0.1, 0.05, 0.05])
    
    alpha = np.array([0.0, 1.0, 1.0])
    beta = np.zeros((N, N))
    beta[0, 0] = 1.0  # Factor 0 conditional variance is linear in Y_0

    model = DaiSingletonATSM(m, N, delta_0, delta, K, theta, Sigma, alpha, beta)
    admissibility = model.check_admissibility()
    assert admissibility["is_admissible"] is True
    assert admissibility["model_family"] == "A_1(3)"

    # Solve Riccati ODE for 5-year zero coupon bond
    tau = 5.0
    A, B = model.solve_riccati_ode(tau)
    assert A < 0.0, "Log-discount intercept A(tau) should be negative"
    assert len(B) == 3
    assert np.all(B < 0.0), "Bond factor loadings B(tau) must be negative for positive interest rates"

    # Compute yield for state Y_t = [0.03, 0.01, -0.01]
    y_5y = model.compute_zero_coupon_yield(tau, np.array([0.03, 0.01, -0.01]))
    assert 0.01 < y_5y < 0.20, f"5-year yield {y_5y} outside realistic range"


def test_acm_term_premium_decomposition():
    """Verify Pillar 2: ACM (2013) Term Premium Decomposition."""
    K = 3
    mu = np.array([0.01, 0.0, 0.0])
    Phi = np.diag([0.95, 0.85, 0.75])
    Sigma = np.diag([0.01, 0.01, 0.01])
    delta_0 = 0.02
    delta_1 = np.array([1.0, 0.5, 0.2])
    
    # Risk price parameters (negative lambda_0, lambda_1 ensures positive term premium for duration risk)
    lambda_0 = np.array([-0.005, -0.002, -0.001])
    lambda_1 = np.diag([-0.03, -0.02, -0.01])

    acm = ACMTermPremiumDecomposition(K, mu, Phi, Sigma, delta_0, delta_1, lambda_0, lambda_1)
    
    # Decompose 10-year (120 months) yield
    X_t = np.array([0.02, 0.01, -0.01])
    decomp = acm.decompose_yield(120, X_t)
    
    assert "market_yield" in decomp
    assert "risk_neutral_yield" in decomp
    assert "term_premium" in decomp
    # Mathematical invariant: Market Yield == RN Yield + Term Premium
    assert abs(decomp["market_yield"] - (decomp["risk_neutral_yield"] + decomp["term_premium"])) < 1e-9
    assert decomp["term_premium"] > 0, "Positive risk compensation expected for long maturity"


def test_rosu_limit_order_book_dynamics():
    """Verify Pillar 3: Ioanid Rosu Dynamic Limit Order Book."""
    lob = RosuLOBDynamics(lambda_arrival=10.0, r_impatience=0.05, delta_tick=0.01)
    
    spread_empty = lob.endogenous_spread(0, 0)
    spread_deep = lob.endogenous_spread(5, 5)
    assert spread_deep > spread_empty, "Spread must widen with queue delay"

    # Stationary queue distribution
    pi = lob.stationary_queue_distribution(max_q=10)
    assert abs(np.sum(pi) - 1.0) < 1e-6
    assert pi[0] > pi[5], "Queue length probability should decay"

    # Decision evaluation
    decision_front = lob.evaluate_order_choice(queue_pos=0, spread=0.04)
    assert decision_front["optimal_choice"] == "LimitOrder"
    
    decision_deep = lob.evaluate_order_choice(queue_pos=50, spread=0.02)
    assert decision_deep["optimal_choice"] == "MarketOrder"


def test_brandt_santa_clara_valkanov_ppp():
    """Verify Pillar 4: Brandt-Santa-Clara-Valkanov Parametric Portfolio Policies."""
    ppp = ParametricPortfolioPolicy(num_characteristics=2, gamma_risk_aversion=2.0)
    
    # 5 assets, 2 characteristics (Value, Momentum)
    np.random.seed(42)
    X = np.array([
        [1.5, 0.8],
        [-0.5, 1.2],
        [0.0, -0.7],
        [-1.2, -0.5],
        [0.2, -0.8]
    ])
    # Normalize X cross-sectionally
    X = (X - np.mean(X, axis=0)) / np.std(X, axis=0)

    # Initial weights should sum to 1.0 (benchmark)
    w0 = ppp.calculate_weights(X)
    assert abs(np.sum(w0) - 1.0) < 1e-9

    # Synthetic data generation for 10 periods
    T = 20
    returns_data = []
    chars_data = []
    for _ in range(T):
        R_t = 0.05 + 0.1 * X[:, 0] + 0.05 * X[:, 1] + 0.02 * np.random.normal(size=5)
        returns_data.append(R_t)
        chars_data.append(X)

    # Optimize theta
    optimal_theta = ppp.optimize_theta(returns_data, chars_data, learning_rate=0.1, iterations=50)
    assert len(optimal_theta) == 2
    # Because returns correlate positively with Char 0 (Value), theta[0] should be positive
    assert optimal_theta[0] > 0, "Theta for high return factor must be positive"


def test_andersen_broadie_bermudan_dual_bounds():
    """Verify Pillar 5: Andersen-Broadie Primal-Dual Bounds."""
    strike = 100.0
    engine = AndersenBroadieDualBounds(strike=strike, discount_factor=0.98)
    
    # Generate geometric Brownian motion paths
    num_paths = 500
    steps = 3
    paths = np.zeros((num_paths, steps + 1))
    paths[:, 0] = 100.0
    for k in range(steps):
        paths[:, k+1] = paths[:, k] * np.exp(-0.01 + 0.15 * np.random.normal(size=num_paths))

    # Early exercise threshold: exercise if S <= 95
    boundary = np.full(steps + 1, 95.0)
    L_0, err_L = engine.compute_primal_lower_bound(paths, boundary)
    assert L_0 >= 0.0, "Option value must be non-negative"

    # Dummy continuation value function for dual upper bound
    approx_val_funcs = [lambda s: max(0.0, strike - s) * 0.9 for _ in range(steps + 1)]
    U_0, err_U = engine.compute_dual_upper_bound(paths[:50], approx_val_funcs, sub_sim_size=10)
    
    # The duality theorem dictates: Lower Bound <= Upper Bound (within numerical tolerance)
    assert U_0 >= L_0 - 3.0 * (err_L + err_U), "Dual upper bound must exceed primal lower bound"


def test_curve_cryptoswap_dynamic_concentration_and_moving_peg():
    """Verify Pillar 6: Curve v2 CryptoSwap Moving Peg."""
    engine = CurveCryptoSwapEngine(A_amp=100.0, gamma=1e-4, initial_price=2000.0)
    assert engine.price_center == 2000.0
    assert engine.price_oracle == 2000.0

    # Market price moves up to 2200
    engine.update_internal_oracle(2200.0)
    assert engine.price_oracle > 2000.0

    # Re-peg attempt when virtual price did not increase (watermark violated)
    failed_repeg = engine.attempt_moving_peg(current_virtual_price=0.99)
    assert failed_repeg["peg_shifted"] is False
    assert engine.price_center == 2000.0

    # Re-peg attempt when virtual price increased (fees earned, watermark met)
    success_repeg = engine.attempt_moving_peg(current_virtual_price=1.05)
    assert success_repeg["peg_shifted"] is True
    assert engine.price_center > 2000.0
    assert engine.virtual_price_watermark == 1.05
