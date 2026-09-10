"""Programmatic TDD Verification Suite for Faz 42 Quantitative Finance Engines.

Models:
1. Refet Gürkaynak, Brian Sack & Jonathan H. Wright (GSW 2007) B-Spline Treasury Yield Curve & Instantaneous Forward Rates
2. Multivariate Continuous-Time Kelly Growth-Optimal Portfolio (GOP) & Sid Browne (1999) Drawdown Constraints
3. Ananth Madhavan, David Richardson & Mark Roomans (MRR 1997) 3-Component Market Microstructure Spread Model
4. J.P. Morgan CreditMetrics (1997) Asset Return Correlation Multi-State Rating Migration & Portfolio Credit VaR
5. L.C.G. Rogers & Z. Shi (1995) 1D Reduced PDE & Michael Curran (1992) Geometric Conditioning for Arithmetic Asian Options
6. Euler v2 & FraxLend Kink-Free PID Dynamic Interest Rate Control Loop & ERC-4626 Isolated Lending Vaults
"""

import math
from typing import Dict, Any, List, Tuple
import numpy as np
import pytest

# ==============================================================================
# Helper Normal CDF and PPF (Standard Normal Distribution Functions)
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

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
# 1. Gürkaynak-Sack-Wright (GSW 2007) Spline Yield Curve Engine
# ==============================================================================
class GSWSplineYieldCurve:
    """Federal Reserve GSW B-Spline Term Structure and Forward Rate Curve Engine."""
    def __init__(self, beta0: float, beta1: float, knots: List[float], gamma: List[float]):
        self.beta0 = float(beta0)
        self.beta1 = float(beta1)
        self.knots = np.array(knots, dtype=float)
        self.gamma = np.array(gamma, dtype=float)
        assert len(self.knots) == len(self.gamma), "Knots and gamma must have equal length"

    def instantaneous_forward_rate(self, m: float) -> float:
        """Calculate f(m) = beta0 + beta1 * m + sum gamma_k * max(0, m - kappa_k)^3."""
        if m < 0:
            return self.beta0
        spline_term = float(np.sum([g * max(0.0, m - k)**3 for g, k in zip(self.gamma, self.knots)]))
        return self.beta0 + self.beta1 * m + spline_term

    def discount_factor(self, m: float, steps: int = 200) -> float:
        r"""Calculate d(m) = exp(- \int_0^m f(s) ds)."""
        if m <= 0.0:
            return 1.0
        grid = np.linspace(0.0, m, steps)
        f_vals = np.array([self.instantaneous_forward_rate(s) for s in grid])
        integral = float(np.sum((f_vals[:-1] + f_vals[1:]) / 2.0 * (grid[1] - grid[0])))
        return math.exp(-integral)

    def zero_coupon_yield(self, m: float, steps: int = 200) -> float:
        r"""Calculate y(m) = (1/m) \int_0^m f(s) ds = - ln(d(m)) / m."""
        if m <= 0.0:
            return self.beta0
        df = self.discount_factor(m, steps=steps)
        return - math.log(df) / m

    def decompose_fomc_shock(self, pre_f: List[float], post_f: List[float], maturities: List[float]) -> Dict[str, float]:
        """
        Decompose FOMC policy announcement into Target Surprise vs Forward Guidance (Path) Surprise.
        Target surprise = Delta f(1M or 3M)
        Path surprise = Delta f(2Y) - Delta f(3M)
        """
        assert len(pre_f) == len(post_f) == len(maturities)
        delta_f = {mat: post - pre for mat, pre, post in zip(maturities, pre_f, post_f)}
        target_shock = delta_f.get(0.25, delta_f[maturities[0]])
        path_shock = delta_f.get(2.0, delta_f[maturities[-1]]) - target_shock
        return {
            "target_surprise_bps": float(target_shock * 10000),
            "path_surprise_bps": float(path_shock * 10000)
        }


# ==============================================================================
# 2. Multivariate Kelly GOP & Sid Browne Drawdown Control
# ==============================================================================
class MultivariateKellyGOP:
    """Continuous-Time Multivariate Growth-Optimal Portfolio with Sid Browne Drawdown Constraints."""
    def __init__(self, mu: np.ndarray, Sigma: np.ndarray, r: float):
        self.mu = np.array(mu, dtype=float)
        self.Sigma = np.array(Sigma, dtype=float)
        self.r = float(r)
        self.N = len(self.mu)
        assert self.Sigma.shape == (self.N, self.N)
        self.Sigma_inv = np.linalg.inv(self.Sigma)

    def compute_gop_weights(self) -> np.ndarray:
        """Analytic unconstrained Growth-Optimal Portfolio weights pi^* = Sigma^{-1} (mu - r 1)."""
        excess_return = self.mu - self.r
        return self.Sigma_inv @ excess_return

    def expected_growth_rate(self, pi: np.ndarray) -> float:
        """Calculate g(pi) = r + pi^T (mu - r 1) - 0.5 * pi^T Sigma pi."""
        excess = self.mu - self.r
        quad = float(pi.T @ self.Sigma @ pi)
        lin = float(np.dot(pi, excess))
        return self.r + lin - 0.5 * quad

    def apply_browne_drawdown_control(self, W_t: float, M_t: float, alpha: float) -> Tuple[np.ndarray, float]:
        """
        Sid Browne (1999) optimal stochastic control for drawdown constraint W_t >= alpha * M_t.
        c(W, M) = max(0, (W - alpha * M) / W).
        Returns adjusted weights pi^*_browne and leverage scaling factor c.
        """
        assert 0.0 < alpha < 1.0, "alpha must be in (0, 1)"
        assert M_t >= W_t, "Historical maximum M_t must be >= current wealth W_t"
        floor = alpha * M_t
        if W_t <= floor:
            return np.zeros(self.N), 0.0
        c_scale = (W_t - floor) / W_t
        pi_gop = self.compute_gop_weights()
        return c_scale * pi_gop, float(c_scale)


# ==============================================================================
# 3. Madhavan-Richardson-Roomans (MRR 1997) Market Microstructure
# ==============================================================================
class MRRMarketMicrostructure:
    """Madhavan, Richardson & Roomans (1997) Trade Indicator Microstructure Model."""
    def __init__(self, theta: float, phi: float, rho: float):
        self.theta = float(theta)  # Permanent asymmetric information parameter
        self.phi = float(phi)      # Transitory order processing / exchange fee
        self.rho = float(rho)      # Order flow autocorrelation (-1 < rho < 1)
        assert self.theta >= 0, "theta must be non-negative"
        assert self.phi >= 0, "phi must be non-negative"
        assert -1.0 < self.rho < 1.0, "rho must be in (-1, 1)"

    def expected_spread(self) -> float:
        """Total expected bid-ask spread S = 2 * (phi + theta)."""
        return 2.0 * (self.phi + self.theta)

    def spread_decomposition(self) -> Dict[str, float]:
        """Decompose spread into Information Asymmetry vs Order Processing shares."""
        total = self.expected_spread()
        info_share = self.theta / (self.phi + self.theta) if total > 0 else 0.0
        processing_share = self.phi / (self.phi + self.theta) if total > 0 else 0.0
        return {
            "total_spread": total,
            "information_share": info_share,
            "processing_share": processing_share
        }

    def simulate_price_series(self, T: int = 1000, sigma_epsilon: float = 0.02, sigma_xi: float = 0.01) -> Dict[str, np.ndarray]:
        """Simulate order flow q_t and observed prices P_t under MRR dynamics."""
        q = np.zeros(T)
        p = np.zeros(T)
        v = np.zeros(T)
        v[0] = 100.0
        p[0] = 100.0
        q[0] = 1.0 if np.random.rand() > 0.5 else -1.0

        for t in range(1, T):
            prob_continue = 0.5 * (1.0 + self.rho)
            if q[t-1] == 1.0:
                q[t] = 1.0 if np.random.rand() < prob_continue else -1.0
            else:
                q[t] = -1.0 if np.random.rand() < prob_continue else 1.0

            epsilon_t = np.random.normal(0, sigma_epsilon)
            xi_t = np.random.normal(0, sigma_xi)

            v[t] = v[t-1] + self.theta * (q[t] - self.rho * q[t-1]) + epsilon_t
            p[t] = v[t] + self.phi * q[t] + xi_t

        delta_p = np.diff(p)
        return {"prices": p, "trades": q, "delta_p": delta_p, "fundamentals": v}


# ==============================================================================
# 4. J.P. Morgan CreditMetrics (1997) Rating Migration Engine
# ==============================================================================
class CreditMetricsEngine:
    """CreditMetrics Multi-State Rating Migration and Portfolio Credit VaR Engine."""
    RATING_NAMES = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'D']

    def __init__(self, transition_matrix: np.ndarray):
        self.trans_mat = np.array(transition_matrix, dtype=float)
        assert self.trans_mat.shape == (8, 8), "Transition matrix must be 8x8"
        for r in range(8):
            assert abs(np.sum(self.trans_mat[r, :]) - 1.0) < 1e-4

    def compute_thresholds(self, current_rating_idx: int) -> Dict[str, float]:
        """Compute standard normal threshold values Z_{g, k} = Phi^{-1}(sum_{m=k}^D p_{g, m})."""
        probs = self.trans_mat[current_rating_idx, :]
        cum_probs = np.cumsum(probs[::-1])[::-1]
        thresholds = {}
        for idx, label in enumerate(self.RATING_NAMES[:-1]):
            prob_at_or_worse = cum_probs[idx + 1]
            prob_clipped = max(1e-6, min(1.0 - 1e-6, prob_at_or_worse))
            thresholds[label] = float(norm_ppf(prob_clipped))
        return thresholds

    def simulate_portfolio_losses(self, obligor_ratings: List[int], bond_notionals: List[float],
                                  betas: List[float], bond_values_by_rating: np.ndarray,
                                  recovery_rate: float = 0.40, n_scenarios: int = 2000) -> Dict[str, float]:
        """Simulate multi-obligor portfolio P&L distribution under single-factor Merton model."""
        M = len(obligor_ratings)
        threshold_tables = [self.compute_thresholds(r) for r in obligor_ratings]

        base_portfolio_val = sum(bond_values_by_rating[r, r] * notional
                                 for r, notional in zip(obligor_ratings, bond_notionals))

        portfolio_values = np.zeros(n_scenarios)
        for s in range(n_scenarios):
            X = np.random.normal(0, 1)
            total_s = 0.0
            for i in range(M):
                beta_i = betas[i]
                e_i = np.random.normal(0, 1)
                R_i = beta_i * X + math.sqrt(1.0 - beta_i**2) * e_i

                th = threshold_tables[i]
                curr_state = 7
                for idx, label in enumerate(self.RATING_NAMES[:-1]):
                    if R_i > th[label]:
                        curr_state = idx
                        break

                if curr_state == 7:
                    val = bond_notionals[i] * recovery_rate
                else:
                    orig_rating = obligor_ratings[i]
                    val = bond_values_by_rating[orig_rating, curr_state] * bond_notionals[i]
                total_s += val
            portfolio_values[s] = total_s

        losses = base_portfolio_val - portfolio_values
        el = float(np.mean(losses))
        credit_var_99 = float(np.percentile(losses, 99.0))
        ul = credit_var_99 - el

        return {
            "base_value": float(base_portfolio_val),
            "expected_loss": el,
            "credit_var_99": credit_var_99,
            "unexpected_loss": ul
        }


# ==============================================================================
# 5. Rogers-Shi & Michael Curran (1992) Arithmetic Asian Option Engine
# ==============================================================================
class AsianOptionRogersCurran:
    """Rogers-Shi Similarity Transformation & Michael Curran Geometric Conditioning for Asian Options."""
    def __init__(self, S0: float, K: float, T: float, r: float, sigma: float):
        self.S0 = float(S0)
        self.K = float(K)
        self.T = float(T)
        self.r = float(r)
        self.sigma = float(sigma)
        assert self.S0 > 0 and self.K > 0 and self.T > 0 and self.sigma > 0

    def rogers_shi_variable(self, A_t: float, S_t: float) -> float:
        """Compute similarity state variable x = (K * T - A_t) / S_t."""
        return (self.K * self.T - A_t) / S_t

    def curran_geometric_lower_bound(self) -> float:
        """Analytic lower bound for arithmetic Asian call using conditioning on geometric average."""
        mu_G = (self.r - 0.5 * self.sigma**2) / 2.0
        sigma_G = self.sigma / math.sqrt(3.0)

        d1 = (math.log(self.S0 / self.K) + (mu_G + 0.5 * sigma_G**2) * self.T) / (sigma_G * math.sqrt(self.T))
        d2 = d1 - sigma_G * math.sqrt(self.T)

        geom_val = math.exp(-self.r * self.T) * (
            self.S0 * math.exp(mu_G * self.T + 0.5 * sigma_G**2 * self.T) * norm_cdf(d1)
            - self.K * norm_cdf(d2)
        )
        return max(0.0, float(geom_val))

    def monte_carlo_arithmetic_asian(self, steps: int = 100, paths: int = 2000) -> Dict[str, float]:
        """Benchmark Monte Carlo simulation for continuous arithmetic average Asian call."""
        dt = self.T / steps
        nudt = (self.r - 0.5 * self.sigma**2) * dt
        sigsdt = self.sigma * math.sqrt(dt)

        payoffs = np.zeros(paths)
        for p in range(paths):
            S = self.S0
            sum_S = S
            for _ in range(steps):
                z = np.random.normal(0, 1)
                S *= math.exp(nudt + sigsdt * z)
                sum_S += S
            arith_avg = sum_S / (steps + 1)
            payoffs[p] = max(0.0, arith_avg - self.K)

        price = float(np.mean(payoffs) * math.exp(-self.r * self.T))
        se = float(np.std(payoffs) / math.sqrt(paths) * math.exp(-self.r * self.T))
        return {"mc_price": price, "std_err": se}


# ==============================================================================
# 6. Euler v2 / FraxLend PID Dynamic Interest Rate Controller
# ==============================================================================
class EulerPIDInterestRateModel:
    """Euler v2 / FraxLend Kink-Free PID Dynamic Interest Rate Controller."""
    def __init__(self, u_target: float = 0.85, kp: float = 2.0, ki: float = 0.5, kd: float = 0.1,
                 min_rate: float = 0.005, max_rate: float = 1.0):
        self.u_target = float(u_target)
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.min_rate = float(min_rate)
        self.max_rate = float(max_rate)

        self.integral_error = 0.0
        self.prev_error = 0.0

    def step(self, current_u: float, current_rate: float, dt: float = 1.0 / 365.0) -> Tuple[float, Dict[str, float]]:
        """Execute one control step."""
        error = current_u - self.u_target
        self.integral_error += error * dt
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error

        delta_ln_r = (self.kp * error + self.ki * self.integral_error + self.kd * derivative) * dt
        new_rate = current_rate * math.exp(delta_ln_r)
        clamped_rate = max(self.min_rate, min(self.max_rate, new_rate))

        metrics = {
            "error": error,
            "proportional_term": self.kp * error,
            "integral_term": self.ki * self.integral_error,
            "derivative_term": self.kd * derivative,
            "delta_ln_r": delta_ln_r
        }
        return clamped_rate, metrics


# ==============================================================================
# Automated Pytest Test Cases
# ==============================================================================

def test_gsw_spline_properties():
    """Test GSW B-spline continuity, forward rate evaluation and discount factors."""
    knots = [2.0, 5.0, 10.0]
    gamma = [0.001, -0.0008, 0.0005]
    gsw = GSWSplineYieldCurve(beta0=0.03, beta1=0.005, knots=knots, gamma=gamma)

    assert abs(gsw.instantaneous_forward_rate(0.0) - 0.03) < 1e-6
    f_5y = gsw.instantaneous_forward_rate(5.0)
    assert f_5y > 0.03

    df_1y = gsw.discount_factor(1.0)
    df_5y = gsw.discount_factor(5.0)
    df_10y = gsw.discount_factor(10.0)
    assert 1.0 > df_1y > df_5y > df_10y > 0.0

    y_5y = gsw.zero_coupon_yield(5.0)
    assert 0.01 < y_5y < 0.15

    mats = [0.25, 2.0, 5.0]
    pre = [0.030, 0.035, 0.040]
    post = [0.035, 0.042, 0.045]
    shocks = gsw.decompose_fomc_shock(pre, post, mats)
    assert abs(shocks["target_surprise_bps"] - 50.0) < 1e-4
    assert abs(shocks["path_surprise_bps"] - 20.0) < 1e-4


def test_multivariate_kelly_and_browne():
    """Test Multivariate Kelly GOP and Sid Browne Drawdown Control."""
    mu = np.array([0.10, 0.12, 0.15])
    r = 0.03
    Sigma = np.array([
        [0.04, 0.01, 0.01],
        [0.01, 0.06, 0.02],
        [0.01, 0.02, 0.09]
    ])
    kelly = MultivariateKellyGOP(mu, Sigma, r)
    pi_gop = kelly.compute_gop_weights()

    assert len(pi_gop) == 3
    assert np.all(pi_gop > 0)

    g_gop = kelly.expected_growth_rate(pi_gop)
    g_rf = kelly.expected_growth_rate(np.zeros(3))
    assert g_gop > g_rf

    pi_b_peak, c_peak = kelly.apply_browne_drawdown_control(W_t=100.0, M_t=100.0, alpha=0.80)
    assert abs(c_peak - 0.20) < 1e-5
    assert np.allclose(pi_b_peak, 0.20 * pi_gop)

    pi_b_floor, c_floor = kelly.apply_browne_drawdown_control(W_t=80.1, M_t=100.0, alpha=0.80)
    assert c_floor < 0.002
    assert np.all(pi_b_floor < 0.01)

    pi_b_breach, c_breach = kelly.apply_browne_drawdown_control(W_t=79.0, M_t=100.0, alpha=0.80)
    assert c_breach == 0.0
    assert np.all(pi_b_breach == 0.0)


def test_mrr_microstructure_model():
    """Test Madhavan-Richardson-Roomans (1997) spread decomposition."""
    mrr = MRRMarketMicrostructure(theta=0.015, phi=0.010, rho=0.25)
    decomp = mrr.spread_decomposition()

    assert abs(decomp["total_spread"] - 0.050) < 1e-6
    assert abs(decomp["information_share"] - 0.60) < 1e-6
    assert abs(decomp["processing_share"] - 0.40) < 1e-6

    sim = mrr.simulate_price_series(T=200)
    assert len(sim["prices"]) == 200
    assert len(sim["delta_p"]) == 199
    assert np.all(np.isin(sim["trades"], [-1.0, 1.0]))


def test_creditmetrics_engine():
    """Test CreditMetrics rating transition thresholds and credit VaR simulation."""
    mat = np.array([
        [0.9081, 0.0833, 0.0068, 0.0006, 0.0012, 0.0000, 0.0000, 0.0000],
        [0.0070, 0.9065, 0.0779, 0.0064, 0.0006, 0.0014, 0.0002, 0.0000],
        [0.0009, 0.0227, 0.9105, 0.0552, 0.0074, 0.0026, 0.0001, 0.0006],
        [0.0002, 0.0033, 0.0595, 0.8693, 0.0530, 0.0117, 0.0012, 0.0018],
        [0.0003, 0.0014, 0.0067, 0.0773, 0.8053, 0.0884, 0.0100, 0.0106],
        [0.0000, 0.0011, 0.0024, 0.0043, 0.0648, 0.8346, 0.0407, 0.0521],
        [0.0022, 0.0000, 0.0022, 0.0130, 0.0238, 0.1124, 0.6486, 0.1978],
        [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 1.0000]
    ])
    cm = CreditMetricsEngine(mat)
    th_bbb = cm.compute_thresholds(current_rating_idx=3)

    assert th_bbb["AAA"] > th_bbb["A"] > th_bbb["BBB"] > th_bbb["CCC"]

    values = np.zeros((8, 8))
    for orig in range(8):
        for mig in range(8):
            values[orig, mig] = 100.0 - mig * 4.0

    res = cm.simulate_portfolio_losses(
        obligor_ratings=[3, 3, 4],
        bond_notionals=[1000.0, 1000.0, 1000.0],
        betas=[0.5, 0.5, 0.4],
        bond_values_by_rating=values,
        recovery_rate=0.40,
        n_scenarios=500
    )
    assert res["base_value"] > 0
    assert res["credit_var_99"] >= res["expected_loss"]
    assert res["unexpected_loss"] >= 0


def test_asian_option_curran_rogers():
    """Test Rogers-Shi transformation and Curran geometric lower bound for Asian options."""
    asian = AsianOptionRogersCurran(S0=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20)

    x = asian.rogers_shi_variable(A_t=25.0, S_t=100.0)
    assert abs(x - 0.75) < 1e-6

    curran_lb = asian.curran_geometric_lower_bound()
    assert curran_lb > 0.0

    d1 = (math.log(100.0 / 100.0) + (0.05 + 0.5 * 0.04) * 1.0) / 0.20
    d2 = d1 - 0.20
    bs_call = 100.0 * norm_cdf(d1) - 100.0 * math.exp(-0.05) * norm_cdf(d2)

    assert curran_lb < bs_call

    mc = asian.monte_carlo_arithmetic_asian(steps=50, paths=1000)
    assert mc["mc_price"] >= curran_lb - 2.0 * mc["std_err"]


def test_euler_pid_dynamic_interest_controller():
    """Test Euler v2 PID controller response to utilization shocks."""
    pid = EulerPIDInterestRateModel(u_target=0.85, kp=3.0, ki=0.8, kd=0.1)

    r_target, m_target = pid.step(current_u=0.85, current_rate=0.05)
    assert abs(m_target["error"]) < 1e-7
    assert abs(r_target - 0.05) < 1e-4

    r_high, m_high = pid.step(current_u=0.95, current_rate=0.05)
    assert r_high > 0.05
    assert m_high["proportional_term"] > 0

    pid_low = EulerPIDInterestRateModel(u_target=0.85, kp=3.0, ki=0.8, kd=0.1)
    r_low, m_low = pid_low.step(current_u=0.60, current_rate=0.05)
    assert r_low < 0.05
    assert m_low["proportional_term"] < 0
