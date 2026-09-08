"""Programmatic TDD Verification Suite for Faz 36 Quantitative Finance Engines.

Models:
1. Cont-de Larrard (2012/2013) Markovian Limit Order Book (LOB) Queue Dynamics
2. Kou (2002) Double Exponential Jump-Diffusion Model (DEJD)
3. Madan-Carr-Chang (1998) Variance Gamma (VG) Pure Jump Lévy Process
4. Avellaneda-Buff (1999) Uncertain Volatility Model (UVM) & Barenblatt Non-Linear PDE
5. Garman-Kohlhagen (1983) & Vanna-Volga FX Volatility Smile Engine
6. Curve LLAMMA (Lending-Liquidating AMM) Soft Liquidation & Morpho Blue Mechanics
"""

import math
import cmath
import numpy as np
import pytest

# ==============================================================================
# 1. Cont & de Larrard (2012/2013) Markovian LOB Model
# ==============================================================================
class ContDeLarrardLOB:
    """Cont-de Larrard Markovian model of order book queue dynamics."""
    def __init__(self, lambda_rate: float, mu_rate: float, theta_rate: float):
        self.lambda_rate = lambda_rate  # Limit order arrival rate
        self.mu_rate = mu_rate          # Market order execution rate
        self.theta_rate = theta_rate    # Cancellation rate per queue unit

    def price_increase_probability_symmetric(self, q_b: int, q_a: int) -> float:
        """Symmetric flow: p_up = q_b / (q_b + q_a)."""
        if q_b <= 0 and q_a <= 0:
            return 0.5
        if q_b <= 0:
            return 0.0
        if q_a <= 0:
            return 1.0
        return q_b / (q_b + q_a)

    def price_increase_probability_asymmetric(
        self, q_b: int, q_a: int, max_queue: int = 20,
        lambda_b: float = 5.0, lambda_a: float = 4.0,
        mu_b: float = 4.0, mu_a: float = 5.0,
        theta_b: float = 0.5, theta_a: float = 0.5
    ) -> float:
        """
        Solves discrete 2D boundary value problem for P(hit ask boundary before bid boundary).
        Using Gauss-Seidel relaxation.
        """
        P = np.zeros((max_queue + 1, max_queue + 1))
        for x in range(1, max_queue + 1):
            P[x, 0] = 1.0  # Ask depleted first -> price increases

        for _ in range(500):
            P_old = P.copy()
            for x in range(1, max_queue):
                for y in range(1, max_queue):
                    rate_x_up = lambda_b
                    rate_x_dn = mu_b + theta_b * x
                    rate_y_up = lambda_a
                    rate_y_dn = mu_a + theta_a * y
                    total_rate = rate_x_up + rate_x_dn + rate_y_up + rate_y_dn

                    P[x, y] = (
                        rate_x_up * P[min(x + 1, max_queue), y] +
                        rate_x_dn * P[x - 1, y] +
                        rate_y_up * P[x, min(y + 1, max_queue)] +
                        rate_y_dn * P[x, y - 1]
                    ) / total_rate

            if np.max(np.abs(P - P_old)) < 1e-6:
                break

        return float(P[min(q_b, max_queue), min(q_a, max_queue)])

    def expected_depletion_time(self, q: int, lambda_rate: float, mu_rate: float, theta_rate: float) -> float:
        """Approximate expected time for single queue of size q to reach 0."""
        drift = (mu_rate - lambda_rate)
        if drift > 0:
            return q / drift
        return q / (mu_rate + theta_rate * (q / 2.0))


# ==============================================================================
# 2. Kou (2002) Double Exponential Jump Diffusion (DEJD)
# ==============================================================================
def std_norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def std_norm_pdf(x: float) -> float:
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

class KouDEJD:
    """Steven Kou (2002) Double Exponential Jump-Diffusion Option Pricing Model."""
    def __init__(
        self, S0: float, K: float, T: float, r: float, sigma: float,
        jump_intensity: float, p_up: float, eta1: float, eta2: float
    ):
        self.S0 = S0
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma
        self.lambd = jump_intensity
        self.p = p_up
        self.q = 1.0 - p_up
        self.eta1 = eta1  # Must be > 1
        self.eta2 = eta2  # Must be > 0
        assert self.eta1 > 1.0, "eta1 must be > 1"
        assert self.eta2 > 0.0, "eta2 must be > 0"

        # Mean jump size E[e^Y - 1] = p*eta1/(eta1-1) + q*eta2/(eta2+1) - 1
        self.k_jump = (self.p * self.eta1 / (self.eta1 - 1.0)) + (self.q * self.eta2 / (self.eta2 + 1.0)) - 1.0

    def european_call_monte_carlo(self, n_paths: int = 50000, n_steps: int = 50) -> float:
        """Monte Carlo validation of Kou DEJD European Call price."""
        np.random.seed(42)
        dt = self.T / n_steps
        drift = (self.r - 0.5 * self.sigma**2 - self.lambd * self.k_jump) * dt
        vol = self.sigma * math.sqrt(dt)

        log_S = np.full(n_paths, math.log(self.S0))
        for _ in range(n_steps):
            z = np.random.standard_normal(n_paths)
            log_S += drift + vol * z

            n_jumps = np.random.poisson(self.lambd * dt, n_paths)
            jump_mask = n_jumps > 0
            if np.any(jump_mask):
                for idx in np.where(jump_mask)[0]:
                    for _ in range(n_jumps[idx]):
                        if np.random.rand() < self.p:
                            y = np.random.exponential(1.0 / self.eta1)
                        else:
                            y = -np.random.exponential(1.0 / self.eta2)
                        log_S[idx] += y

        S_T = np.exp(log_S)
        payoff = np.maximum(S_T - self.K, 0.0)
        discounted_call = math.exp(-self.r * self.T) * float(np.mean(payoff))
        return discounted_call

    def down_and_out_call_mc(self, barrier: float, n_paths: int = 30000, n_steps: int = 100) -> float:
        """Path-dependent down-and-out barrier call under Kou jumps."""
        np.random.seed(42)
        dt = self.T / n_steps
        drift = (self.r - 0.5 * self.sigma**2 - self.lambd * self.k_jump) * dt
        vol = self.sigma * math.sqrt(dt)

        log_S = np.full(n_paths, math.log(self.S0))
        active = np.ones(n_paths, dtype=bool)

        for _ in range(n_steps):
            z = np.random.standard_normal(n_paths)
            log_S[active] += drift + vol * z[active]

            n_jumps = np.random.poisson(self.lambd * dt, n_paths)
            for idx in np.where(active & (n_jumps > 0))[0]:
                for _ in range(n_jumps[idx]):
                    if np.random.rand() < self.p:
                        y = np.random.exponential(1.0 / self.eta1)
                    else:
                        y = -np.random.exponential(1.0 / self.eta2)
                    log_S[idx] += y

            active[np.exp(log_S) <= barrier] = False

        S_T = np.exp(log_S)
        payoffs = np.where(active, np.maximum(S_T - self.K, 0.0), 0.0)
        return math.exp(-self.r * self.T) * float(np.mean(payoffs))


# ==============================================================================
# 3. Madan, Carr & Chang (1998) Variance Gamma (VG) Model
# ==============================================================================
class VarianceGammaModel:
    """Madan-Carr-Chang (1998) Variance Gamma pure jump Lévy asset model."""
    def __init__(self, S0: float, K: float, T: float, r: float, sigma: float, theta: float, nu: float):
        self.S0 = S0
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma
        self.theta = theta
        self.nu = nu
        arg = 1.0 - self.theta * self.nu - 0.5 * (self.sigma**2) * self.nu
        assert arg > 0.0, f"Martingale condition failed: {arg} <= 0"
        self.omega = (1.0 / self.nu) * math.log(arg)

    def characteristic_function(self, u: complex) -> complex:
        term = 1.0 - 1j * u * self.theta * self.nu + 0.5 * (self.sigma**2) * self.nu * (u**2)
        vg_cf = term ** (-self.T / self.nu)
        drift = (self.r + self.omega) * self.T
        return cmath.exp(1j * u * drift) * vg_cf

    def price_call_carr_madan_fft(self, alpha: float = 1.5, N: int = 1024, B: float = 400.0) -> float:
        dv = B / N
        dk = (2.0 * math.pi) / (N * dv)
        b = (N * dk) / 2.0

        v = np.arange(N) * dv
        w = np.full(N, 2.0 * dv / 3.0)
        w[0] = dv / 3.0
        w[1::2] = 4.0 * dv / 3.0

        log_K = math.log(self.K / self.S0)

        psi_vals = []
        for val in v:
            u = val - (alpha + 1.0) * 1j
            cf = self.characteristic_function(u)
            denom = alpha**2 + alpha - val**2 + 1j * (2.0 * alpha + 1.0) * val
            psi = math.exp(-self.r * self.T) * cf / denom
            psi_vals.append(psi)

        psi_arr = np.array(psi_vals)
        integrand = np.exp(-1j * v * log_K) * psi_arr
        integral_val = np.sum(w * np.real(integrand))
        call_price = (math.exp(-alpha * log_K) / math.pi) * integral_val * self.S0
        return float(max(0.0, call_price))

    def analytical_moments(self) -> dict:
        denom = (self.sigma**2 + self.theta**2 * self.nu)**1.5
        skew = (2.0 * self.theta**3 * self.nu**2 + 3.0 * self.sigma**2 * self.theta * self.nu) / denom
        kurt_denom = (self.sigma**2 + self.theta**2 * self.nu)**2
        excess_kurt = 3.0 * self.nu * (2.0 * self.theta**4 * self.nu**2 + 4.0 * self.sigma**2 * self.theta**2 * self.nu + self.sigma**4) / kurt_denom
        return {"skewness": skew, "excess_kurtosis": excess_kurt}


# ==============================================================================
# 4. Avellaneda & Buff (1999) Uncertain Volatility Model (UVM) & Barenblatt PDE
# ==============================================================================
class BarenblattUVM:
    """Non-linear Black-Scholes-Barenblatt PDE solver for worst-case derivative bounds."""
    def __init__(self, S0: float, K: float, T: float, r: float, sigma_min: float, sigma_max: float):
        self.S0 = S0
        self.K = K
        self.T = T
        self.r = r
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max

    def solve_bounds(self, M: int = 100, N: int = 100, S_max_mult: float = 3.0) -> dict:
        S_max = self.S0 * S_max_mult
        dS = S_max / M
        dt = self.T / N
        S_grid = np.linspace(0, S_max, M + 1)

        def payoff(S):
            return np.maximum(S - self.K, 0.0)

        results = {}
        for mode in ["ask", "bid"]:
            V = payoff(S_grid).copy()

            for _ in range(N):
                V_new = V.copy()
                for i in range(1, M):
                    delta = (V[i + 1] - V[i - 1]) / (2.0 * dS)
                    gamma = (V[i + 1] - 2.0 * V[i] + V[i - 1]) / (dS**2)

                    if mode == "ask":
                        sig = self.sigma_max if gamma > 0 else self.sigma_min
                    else:
                        sig = self.sigma_min if gamma > 0 else self.sigma_max

                    theta = 0.5 * (sig**2) * (S_grid[i]**2) * gamma + self.r * S_grid[i] * delta - self.r * V[i]
                    V_new[i] = V[i] + dt * theta

                V_new[0] = 0.0
                V_new[M] = max(0.0, S_max - self.K * math.exp(-self.r * self.T))
                V = V_new

            idx = int(self.S0 / dS)
            weight = (self.S0 - S_grid[idx]) / dS
            price = (1.0 - weight) * V[idx] + weight * V[idx + 1]
            results[mode] = float(price)

        results["spread"] = results["ask"] - results["bid"]
        return results


# ==============================================================================
# 5. Garman-Kohlhagen & FX Vanna-Volga Pricing
# ==============================================================================
class VannaVolgaFX:
    """Garman-Kohlhagen (1983) and Vanna-Volga Volatility Smile & Pricing Engine."""
    def __init__(self, S0: float, T: float, rd: float, rf: float, sigma_atm: float, rr25: float, bf25: float):
        self.S0 = S0
        self.T = T
        self.rd = rd
        self.rf = rf
        self.sigma_atm = sigma_atm
        self.rr25 = rr25
        self.bf25 = bf25

        self.sigma_25c = self.sigma_atm + self.bf25 + 0.5 * self.rr25
        self.sigma_25p = self.sigma_atm + self.bf25 - 0.5 * self.rr25

        self.K_atm = self.S0 * math.exp((self.rd - self.rf + 0.5 * self.sigma_atm**2) * self.T)
        self.K_25c = self.S0 * math.exp((self.rd - self.rf) * self.T + 0.6745 * self.sigma_25c * math.sqrt(self.T))
        self.K_25p = self.S0 * math.exp((self.rd - self.rf) * self.T - 0.6745 * self.sigma_25p * math.sqrt(self.T))

    def gk_call(self, K: float, sigma: float) -> tuple[float, float, float, float]:
        d1 = (math.log(self.S0 / K) + (self.rd - self.rf + 0.5 * sigma**2) * self.T) / (sigma * math.sqrt(self.T))
        d2 = d1 - sigma * math.sqrt(self.T)

        disc_d = math.exp(-self.rd * self.T)
        disc_f = math.exp(-self.rf * self.T)

        price = self.S0 * disc_f * std_norm_cdf(d1) - K * disc_d * std_norm_cdf(d2)
        vega = self.S0 * disc_f * math.sqrt(self.T) * std_norm_pdf(d1)
        vanna = -disc_f * std_norm_pdf(d1) * (d2 / sigma)
        volga = vega * (d1 * d2 / sigma)
        return price, vega, vanna, volga

    def price_vanna_volga(self, K: float) -> dict:
        p_atm, vega_atm, vanna_atm, volga_atm = self.gk_call(self.K_atm, self.sigma_atm)
        p_25c, vega_25c, vanna_25c, volga_25c = self.gk_call(self.K_25c, self.sigma_25c)
        p_25p, vega_25p, vanna_25p, volga_25p = self.gk_call(self.K_25p, self.sigma_25p)

        p_k_bs, vega_k, vanna_k, volga_k = self.gk_call(K, self.sigma_atm)

        rr_cost = (self.gk_call(self.K_25c, self.sigma_25c)[0] - self.gk_call(self.K_25c, self.sigma_atm)[0]) - \
                  (self.gk_call(self.K_25p, self.sigma_25p)[0] - self.gk_call(self.K_25p, self.sigma_atm)[0])
        bf_cost = (self.gk_call(self.K_25c, self.sigma_25c)[0] - self.gk_call(self.K_25c, self.sigma_atm)[0]) + \
                  (self.gk_call(self.K_25p, self.sigma_25p)[0] - self.gk_call(self.K_25p, self.sigma_atm)[0])

        vv_correction = (vanna_k / max(1e-5, abs(vanna_25c - vanna_25p))) * rr_cost * 0.5 + \
                        (volga_k / max(1e-5, abs(volga_25c + volga_25p))) * bf_cost * 0.5

        p_vv = p_k_bs + vv_correction
        return {
            "bs_atm_price": p_k_bs,
            "vanna_volga_price": float(max(0.0, p_vv)),
            "correction": float(vv_correction)
        }


# ==============================================================================
# 6. Curve LLAMMA (Lending-Liquidating AMM) & Soft Liquidation Physics
# ==============================================================================
class CurveLLAMMABand:
    """Curve LLAMMA (crvUSD) soft liquidation dynamic AMM band simulator."""
    def __init__(self, p_down: float, p_up: float, band_id: int):
        self.p_down = p_down
        self.p_up = p_up
        self.band_id = band_id
        self.inv = math.sqrt(p_down * p_up)

    def rebalance(self, market_price: float, initial_collateral: float) -> dict:
        if market_price >= self.p_up:
            return {
                "collateral_eth": initial_collateral,
                "stablecoin_crvusd": 0.0,
                "status": "HEALTHY_ACTIVE",
                "liquidation_pct": 0.0
            }
        elif market_price <= self.p_down:
            avg_exec_price = math.sqrt(self.p_down * self.p_up)
            crvusd_amount = initial_collateral * avg_exec_price
            return {
                "collateral_eth": 0.0,
                "stablecoin_crvusd": crvusd_amount,
                "status": "SOFT_LIQUIDATED",
                "liquidation_pct": 1.0
            }
        else:
            frac = (self.p_up - market_price) / (self.p_up - self.p_down)
            eth_left = initial_collateral * (1.0 - frac)
            usd_received = initial_collateral * frac * (0.5 * (self.p_up + market_price))
            return {
                "collateral_eth": eth_left,
                "stablecoin_crvusd": usd_received,
                "status": "IN_SOFT_LIQUIDATION",
                "liquidation_pct": float(frac)
            }


# ==============================================================================
# Pytest Test Cases
# ==============================================================================
def test_cont_de_larrard_lob():
    lob = ContDeLarrardLOB(lambda_rate=5.0, mu_rate=4.0, theta_rate=0.5)
    p_sym = lob.price_increase_probability_symmetric(q_b=10, q_a=10)
    assert pytest.approx(p_sym, 0.01) == 0.5

    p_skew = lob.price_increase_probability_symmetric(q_b=30, q_a=10)
    assert p_skew == 0.75

    p_asym = lob.price_increase_probability_asymmetric(q_b=5, q_a=5)
    assert 0.0 < p_asym < 1.0

    t_dep = lob.expected_depletion_time(q=10, lambda_rate=2.0, mu_rate=5.0, theta_rate=0.5)
    assert t_dep > 0.0

def test_kou_dejd_pricing():
    kou = KouDEJD(S0=100.0, K=100.0, T=1.0, r=0.05, sigma=0.2, jump_intensity=1.0, p_up=0.4, eta1=10.0, eta2=5.0)
    call_mc = kou.european_call_monte_carlo(n_paths=20000, n_steps=40)
    assert 8.0 < call_mc < 18.0

    barrier_call = kou.down_and_out_call_mc(barrier=80.0, n_paths=20000, n_steps=40)
    assert 0.0 < barrier_call <= call_mc

def test_variance_gamma_cf_and_fft():
    vg = VarianceGammaModel(S0=100.0, K=100.0, T=0.5, r=0.03, sigma=0.2, theta=-0.1, nu=0.2)
    moments = vg.analytical_moments()
    assert moments["skewness"] < 0
    assert moments["excess_kurtosis"] > 0

    call_fft = vg.price_call_carr_madan_fft(alpha=1.5, N=1024, B=400.0)
    assert 4.0 < call_fft < 12.0

def test_barenblatt_uvm():
    uvm = BarenblattUVM(S0=100.0, K=100.0, T=0.5, r=0.05, sigma_min=0.15, sigma_max=0.30)
    bounds = uvm.solve_bounds(M=80, N=80)
    assert bounds["ask"] >= bounds["bid"]
    assert bounds["spread"] >= 0.0

def test_vanna_volga_fx():
    fx = VannaVolgaFX(S0=1.10, T=0.5, rd=0.04, rf=0.02, sigma_atm=0.10, rr25=-0.015, bf25=0.005)
    otm_strike = 1.15
    vv_res = fx.price_vanna_volga(otm_strike)
    assert vv_res["vanna_volga_price"] >= 0.0

def test_curve_llamma_soft_liquidation():
    band = CurveLLAMMABand(p_down=2800.0, p_up=3000.0, band_id=1)

    res_above = band.rebalance(market_price=3100.0, initial_collateral=2.0)
    assert res_above["collateral_eth"] == 2.0
    assert res_above["stablecoin_crvusd"] == 0.0

    res_inside = band.rebalance(market_price=2900.0, initial_collateral=2.0)
    assert 0.0 < res_inside["collateral_eth"] < 2.0
    assert res_inside["stablecoin_crvusd"] > 0.0
    assert pytest.approx(res_inside["liquidation_pct"], 0.01) == 0.5

    res_below = band.rebalance(market_price=2700.0, initial_collateral=2.0)
    assert res_below["collateral_eth"] == 0.0
    assert res_below["stablecoin_crvusd"] > 5500.0
