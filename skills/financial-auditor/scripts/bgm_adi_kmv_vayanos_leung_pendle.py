"""Phase 27: Quantitative Financial Engineering, Derivatives & Decentralized Market Mechanics.

Core Pillars:
1. Brace-Gatarek-Musiela (BGM) / Libor Market Model (LMM) & Rebonato Swaption Volatility
2. 2D Crank-Nicolson & Hundsdorfer-Verwer ADI Scheme for Multi-Asset Derivatives
3. Merton-KMV Structural Credit Model & Vasicek ASRF Basel Portfolio Capital
4. Kyle (1985) Continuous Market Depth & Vayanos-Wang (2012) OTC Search Liquidity
5. Leung & Li (2015) Ornstein-Uhlenbeck Optimal Double-Stopping Stat-Arb & Stop-Loss
6. Pendle Finance YieldSpace AMM Invariant & Aave v3 E-Mode De-Peg Cascade Physics
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# COMMON PROBABILITY & STATISTICAL UTILITIES
# ==============================================================================

def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_inv(p: float) -> float:
    """Acklam (2010) high-precision approximation for inverse standard normal CDF."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability p must be strictly in (0, 1).")

    a = [
        -3.969683028665376e01, 2.209460984245205e02,
        -2.759285104469687e02, 1.383577518672690e02,
        -3.066479806614716e01, 2.506628277459239e00
    ]
    b = [
        -5.447609879822406e01, 1.615858368580409e02,
        -1.556989798598866e02, 6.680131188771972e01,
        -1.328068155288572e01
    ]
    c = [
        -7.784894002430293e-03, -3.223964580411365e-01,
        -2.400758277161838e00, -2.549732539343734e00,
        4.374664141464968e00, 2.938163982698783e00
    ]
    d = [
        7.784695709041462e-03, 3.224671290700398e-01,
        2.445134137142996e00, 3.754408661907416e00
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)


# ==============================================================================
# 1. BRACE-GATAREK-MUSIELA (BGM) / LIBOR MARKET MODEL & REBONATO SWAPTION
# ==============================================================================

@dataclass
class BGMSimulationResult:
    tenors: List[float]
    forward_paths: np.ndarray  # Shape: (n_paths, n_steps + 1, n_forwards)
    terminal_discounts: np.ndarray  # Shape: (n_paths, n_forwards + 1)
    rebonato_swap_vol: float
    black76_caplet_prices: List[float]
    mc_caplet_prices: List[float]


class BGMForwardMarketModelEngine:
    """Libor Market Model (BGM) term structure engine with Rebonato volatility approximation.
    
    References:
    - Brace, A., Gatarek, D., & Musiela, M. (1997). The Market Model of Interest Rate Dynamics.
    - Rebonato, R. (1998). Volatility and Correlation: The Perfect Hedger and the Fox.
    """

    @staticmethod
    def discount_factors_from_forwards(forwards: np.ndarray, delta_t: float) -> np.ndarray:
        """Computes zero coupon bond prices P(0, T_k) from forward rates F_k(0).
        
        P(0, T_0) = 1.0
        P(0, T_{k+1}) = P(0, T_k) / (1 + delta_t * F_k)
        """
        n_fwd = len(forwards)
        p = np.zeros(n_fwd + 1)
        p[0] = 1.0
        for i in range(n_fwd):
            p[i + 1] = p[i] / (1.0 + delta_t * forwards[i])
        return p

    @staticmethod
    def calculate_caplet_black76(
        forward_rate: float,
        strike: float,
        tau_start: float,
        tau_end: float,
        vol: float,
        discount_factor_end: float,
    ) -> float:
        """Calculates analytical Black-76 European Caplet price.
        
        Caplet = P(0, T_{k+1}) * (T_{k+1} - T_k) * [F * N(d1) - K * N(d2)]
        """
        delta = tau_end - tau_start
        if tau_start <= 0.0 or vol <= 0.0 or forward_rate <= 0.0 or strike <= 0.0:
            payoff = max(forward_rate - strike, 0.0)
            return discount_factor_end * delta * payoff

        std = vol * math.sqrt(tau_start)
        d1 = (math.log(forward_rate / strike) + 0.5 * std * std) / std
        d2 = d1 - std
        return discount_factor_end * delta * (forward_rate * norm_cdf(d1) - strike * norm_cdf(d2))

    @staticmethod
    def rebonato_swaption_vol(
        tenors: List[float],
        forward_rates: np.ndarray,
        volatilities: np.ndarray,
        corr_matrix: np.ndarray,
        swap_start_idx: int,
        swap_end_idx: int,
    ) -> float:
        """Approximates Black swaption volatility via Riccardo Rebonato's formula.
        
        sigma_swap^2 ~= sum_{i,j} (w_i w_j F_i F_j rho_{i,j} sigma_i sigma_j) / S^2
        """
        delta_t = tenors[1] - tenors[0]
        discounts = BGMForwardMarketModelEngine.discount_factors_from_forwards(forward_rates, delta_t)

        annuity = sum(delta_t * discounts[k + 1] for k in range(swap_start_idx, swap_end_idx))
        if annuity <= 1e-12:
            raise ValueError("Swap annuity cannot be zero.")

        swap_rate = (discounts[swap_start_idx] - discounts[swap_end_idx]) / annuity

        weights = np.zeros(swap_end_idx - swap_start_idx)
        sub_forwards = forward_rates[swap_start_idx:swap_end_idx]
        sub_vols = volatilities[swap_start_idx:swap_end_idx]

        for idx, k in enumerate(range(swap_start_idx, swap_end_idx)):
            weights[idx] = (delta_t * discounts[k + 1]) / annuity

        var_sum = 0.0
        n_sub = len(weights)
        for i in range(n_sub):
            for j in range(n_sub):
                glob_i = swap_start_idx + i
                glob_j = swap_start_idx + j
                rho = corr_matrix[glob_i, glob_j]
                cov_ij = weights[i] * weights[j] * sub_forwards[i] * sub_forwards[j] * rho * sub_vols[i] * sub_vols[j]
                var_sum += cov_ij

        var_swap = var_sum / (swap_rate * swap_rate)
        return math.sqrt(max(var_swap, 0.0))

    @staticmethod
    def simulate_bgm_spot_measure(
        tenors: List[float],
        forward_rates: np.ndarray,
        volatilities: np.ndarray,
        corr_matrix: np.ndarray,
        num_paths: int = 1000,
        num_steps: int = 40,
        seed: int = 42,
    ) -> BGMSimulationResult:
        """Simulates full forward rate term structure under the rolling spot measure.
        
        Drift for forward F_i(t) under spot measure:
        mu_i(t) = sigma_i * sum_{j=m(t)+1}^i [ (delta_j * rho_{i,j} * sigma_j * F_j(t)) / (1 + delta_j * F_j(t)) ]
        """
        np.random.seed(seed)
        n_forwards = len(forward_rates)
        delta_t = tenors[1] - tenors[0]
        maturity_max = tenors[-1]
        dt = maturity_max / num_steps

        # Cholesky decomposition for correlated standard normal shocks
        chol = np.linalg.cholesky(corr_matrix)

        # Storage: (n_paths, num_steps + 1, n_forwards)
        paths = np.zeros((num_paths, num_steps + 1, n_forwards))
        paths[:, 0, :] = forward_rates

        curr_fwd = np.tile(forward_rates, (num_paths, 1))

        for step in range(num_steps):
            t = step * dt
            # Determine current active tenor index m(t)
            m_t = min(int(t / delta_t), n_forwards - 1)

            # Generate correlated Gaussian innovations: shape (num_paths, n_forwards)
            z_uncorr = np.random.standard_normal((num_paths, n_forwards))
            z_corr = z_uncorr @ chol.T

            # Compute drift for each forward rate
            drift = np.zeros((num_paths, n_forwards))
            for i in range(n_forwards):
                if i > m_t:
                    # Sum over j from m_t + 1 to i
                    sum_j = np.zeros(num_paths)
                    for j in range(m_t + 1, i + 1):
                        rho_ij = corr_matrix[i, j]
                        denom = 1.0 + delta_t * curr_fwd[:, j]
                        sum_j += (delta_t * rho_ij * volatilities[j] * curr_fwd[:, j]) / denom
                    drift[:, i] = volatilities[i] * sum_j
                else:
                    drift[:, i] = 0.0

            # Log-Euler update for forward rates (prevents negative rates)
            for i in range(n_forwards):
                if t < tenors[i]:
                    sigma_i = volatilities[i]
                    d_log = (drift[:, i] - 0.5 * sigma_i * sigma_i) * dt + sigma_i * math.sqrt(dt) * z_corr[:, i]
                    curr_fwd[:, i] = curr_fwd[:, i] * np.exp(d_log)

            paths[:, step + 1, :] = curr_fwd

        # Calculate analytical and simulated caplet prices
        init_discounts = BGMForwardMarketModelEngine.discount_factors_from_forwards(forward_rates, delta_t)
        black_prices = []
        mc_prices = []

        strike = float(np.mean(forward_rates))

        for k in range(n_forwards):
            t_k = tenors[k]
            t_next = tenors[k + 1]
            p_end = init_discounts[k + 1]
            b_price = BGMForwardMarketModelEngine.calculate_caplet_black76(
                forward_rates[k], strike, t_k, t_next, volatilities[k], p_end
            )
            black_prices.append(b_price)

            # MC payoff at t_k
            step_idx = min(int(t_k / dt), num_steps)
            fwd_at_tk = paths[:, step_idx, k]
            payoff = np.maximum(fwd_at_tk - strike, 0.0) * delta_t * p_end
            mc_prices.append(float(np.mean(payoff)))

        # Rebonato swaption volatility for entire span
        reb_vol = BGMForwardMarketModelEngine.rebonato_swaption_vol(
            tenors=tenors,
            forward_rates=forward_rates,
            volatilities=volatilities,
            corr_matrix=corr_matrix,
            swap_start_idx=0,
            swap_end_idx=n_forwards,
        )

        # Terminal discounts at final step
        term_discounts = np.zeros((num_paths, n_forwards + 1))
        for p_i in range(num_paths):
            term_discounts[p_i] = BGMForwardMarketModelEngine.discount_factors_from_forwards(paths[p_i, -1, :], delta_t)

        return BGMSimulationResult(
            tenors=tenors,
            forward_paths=paths,
            terminal_discounts=term_discounts,
            rebonato_swap_vol=reb_vol,
            black76_caplet_prices=black_prices,
            mc_caplet_prices=mc_prices,
        )


# ==============================================================================
# 2. 2D CRANK-NICOLSON & HUNDSDORFER-VERWER ADI FINITE DIFFERENCE SCHEME
# ==============================================================================

@dataclass
class ADI2DPDEResult:
    spot1_grid: np.ndarray
    spot2_grid: np.ndarray
    price_grid: np.ndarray
    price_at_spot: float
    delta_s1: float
    delta_s2: float
    gamma_s1: float
    gamma_s2: float
    is_american: bool


class ADI2DFiniteDifferenceEngine:
    """Solves 2D multi-asset parabolic PDEs with cross-derivatives using Hundsdorfer-Verwer ADI.
    
    References:
    - Hundsdorfer, W., & Verwer, J. G. (2003). Numerical Solution of Time-Dependent Advection-Diffusion-Reaction Equations.
    - in 't Hout, K. J., & Welfert, B. D. (2009). Stability of ADI schemes on tensor product grids for Heston-type models.
    """

    @staticmethod
    def _thomas_algorithm(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
        """Solves tridiagonal linear equation system M * x = d in O(N)."""
        n = len(d)
        c_prime = np.zeros(n - 1)
        d_prime = np.zeros(n)

        c_prime[0] = c[0] / b[0]
        d_prime[0] = d[0] / b[0]

        for i in range(1, n - 1):
            denom = b[i] - a[i - 1] * c_prime[i - 1]
            c_prime[i] = c[i] / denom
            d_prime[i] = (d[i] - a[i - 1] * d_prime[i - 1]) / denom

        denom = b[n - 1] - a[n - 2] * c_prime[n - 2]
        d_prime[n - 1] = (d[n - 1] - a[n - 2] * d_prime[n - 2]) / denom

        x = np.zeros(n)
        x[n - 1] = d_prime[n - 1]
        for i in range(n - 2, -1, -1):
            x[i] = d_prime[i] - c_prime[i] * x[i + 1]
        return x

    @staticmethod
    def solve_spread_option_adi(
        spot1: float,
        spot2: float,
        strike: float,
        r: float,
        sigma1: float,
        sigma2: float,
        rho: float,
        maturity: float,
        n_s1: int = 41,
        n_s2: int = 41,
        n_t: int = 30,
        is_american: bool = False,
    ) -> ADI2DPDEResult:
        """Prices European or American 2-asset spread option max(S1 - S2 - K, 0).
        
        Operator decomposition:
        A = A_0 (mixed derivative rho*sigma1*sigma2*S1*S2) + A_1 (S1 derivatives) + A_2 (S2 derivatives)
        Uses Craig-Sneyd / Hundsdorfer-Verwer ADI scheme with theta = 0.5 (Crank-Nicolson).
        """
        s1_max = spot1 * 3.0
        s2_max = spot2 * 3.0

        s1_grid = np.linspace(0.0, s1_max, n_s1)
        s2_grid = np.linspace(0.0, s2_max, n_s2)

        ds1 = s1_grid[1] - s1_grid[0]
        ds2 = s2_grid[1] - s2_grid[0]
        dt = maturity / n_t

        # Payoff surface at maturity
        S1, S2 = np.meshgrid(s1_grid, s2_grid, indexing='ij')
        payoff = np.maximum(S1 - S2 - strike, 0.0)

        # U holds option value backward in time
        U = np.copy(payoff)
        theta = 0.5  # Crank-Nicolson parameter

        def apply_A0(u: np.ndarray) -> np.ndarray:
            """Mixed derivative term: rho * sigma1 * sigma2 * S1 * S2 * d2U/(dS1 dS2)."""
            out = np.zeros_like(u)
            for i in range(1, n_s1 - 1):
                for j in range(1, n_s2 - 1):
                    d2u = (u[i + 1, j + 1] - u[i + 1, j - 1] - u[i - 1, j + 1] + u[i - 1, j - 1]) / (4.0 * ds1 * ds2)
                    out[i, j] = rho * sigma1 * sigma2 * s1_grid[i] * s2_grid[j] * d2u
            return out

        def apply_A1(u: np.ndarray) -> np.ndarray:
            """S1 spatial operator: 0.5*sigma1^2*S1^2*d2u/dS1^2 + r*S1*du/dS1 - 0.5*r*u."""
            out = np.zeros_like(u)
            for i in range(1, n_s1 - 1):
                s = s1_grid[i]
                d2u = (u[i + 1, :] - 2.0 * u[i, :] + u[i - 1, :]) / (ds1 * ds1)
                du = (u[i + 1, :] - u[i - 1, :]) / (2.0 * ds1)
                out[i, :] = 0.5 * sigma1 * sigma1 * s * s * d2u + r * s * du - 0.5 * r * u[i, :]
            return out

        def apply_A2(u: np.ndarray) -> np.ndarray:
            """S2 spatial operator: 0.5*sigma2^2*S2^2*d2u/dS2^2 + r*S2*du/dS2 - 0.5*r*u."""
            out = np.zeros_like(u)
            for j in range(1, n_s2 - 1):
                s = s2_grid[j]
                d2u = (u[:, j + 1] - 2.0 * u[:, j] + u[:, j - 1]) / (ds2 * ds2)
                du = (u[:, j + 1] - u[:, j - 1]) / (2.0 * ds2)
                out[:, j] = 0.5 * sigma2 * sigma2 * s * s * d2u + r * s * du - 0.5 * r * u[:, j]
            return out

        # Time-stepping backward from maturity to t=0
        for _ in range(n_t):
            # Step 1: Explicit predictor Y0 = U + dt * (A0 + A1 + A2) U
            A0_U = apply_A0(U)
            A1_U = apply_A1(U)
            A2_U = apply_A2(U)
            Y0 = U + dt * (A0_U + A1_U + A2_U)

            # Step 2: Implicit solve in S1 direction: (I - theta*dt*A1) Y1 = Y0 - theta*dt*A1 U
            rhs_1 = Y0 - theta * dt * A1_U
            Y1 = np.zeros_like(U)
            for j in range(n_s2):
                # Build tridiagonal system for slice j
                a = np.zeros(n_s1 - 1)
                b = np.ones(n_s1)
                c = np.zeros(n_s1 - 1)
                d = np.copy(rhs_1[:, j])

                for i in range(1, n_s1 - 1):
                    s = s1_grid[i]
                    gamma_term = 0.5 * sigma1 * sigma1 * s * s / (ds1 * ds1)
                    drift_term = r * s / (2.0 * ds1)
                    a[i - 1] = -theta * dt * (gamma_term - drift_term)
                    b[i] = 1.0 - theta * dt * (-2.0 * gamma_term - 0.5 * r)
                    c[i] = -theta * dt * (gamma_term + drift_term)

                # Boundary conditions for S1
                b[0] = 1.0
                c[0] = 0.0
                b[-1] = 1.0
                a[-1] = 0.0
                d[0] = max(0.0 - s2_grid[j] - strike, 0.0)
                d[-1] = max(s1_max - s2_grid[j] - strike, 0.0)

                Y1[:, j] = ADI2DFiniteDifferenceEngine._thomas_algorithm(a, b, c, d)

            # Step 3: Implicit solve in S2 direction: (I - theta*dt*A2) Y2 = Y1 - theta*dt*A2 U
            rhs_2 = Y1 - theta * dt * A2_U
            Y2 = np.zeros_like(U)
            for i in range(n_s1):
                a = np.zeros(n_s2 - 1)
                b = np.ones(n_s2)
                c = np.zeros(n_s2 - 1)
                d = np.copy(rhs_2[i, :])

                for j in range(1, n_s2 - 1):
                    s = s2_grid[j]
                    gamma_term = 0.5 * sigma2 * sigma2 * s * s / (ds2 * ds2)
                    drift_term = r * s / (2.0 * ds2)
                    a[j - 1] = -theta * dt * (gamma_term - drift_term)
                    b[j] = 1.0 - theta * dt * (-2.0 * gamma_term - 0.5 * r)
                    c[j] = -theta * dt * (gamma_term + drift_term)

                # Boundary conditions for S2
                b[0] = 1.0
                c[0] = 0.0
                b[-1] = 1.0
                a[-1] = 0.0
                d[0] = max(s1_grid[i] - 0.0 - strike, 0.0)
                d[-1] = max(s1_grid[i] - s2_max - strike, 0.0)

                Y2[i, :] = ADI2DFiniteDifferenceEngine._thomas_algorithm(a, b, c, d)

            # Step 4: Corrected mixed term: U_new = Y2 + 0.5 * dt * (apply_A0(Y2) - A0_U)
            U = Y2 + 0.5 * dt * (apply_A0(Y2) - A0_U)

            # American free-boundary constraint (Brennan-Schwartz projection)
            if is_american:
                U = np.maximum(U, payoff)

        # Bilinear interpolation at (spot1, spot2)
        i_s1 = int(np.searchsorted(s1_grid, spot1))
        j_s2 = int(np.searchsorted(s2_grid, spot2))

        i_s1 = min(max(i_s1, 1), n_s1 - 2)
        j_s2 = min(max(j_s2, 1), n_s2 - 2)

        p_spot = float(U[i_s1, j_s2])

        # Greeks via finite difference
        delta_1 = float((U[i_s1 + 1, j_s2] - U[i_s1 - 1, j_s2]) / (2.0 * ds1))
        delta_2 = float((U[i_s1, j_s2 + 1] - U[i_s1, j_s2 - 1]) / (2.0 * ds2))
        gamma_1 = float((U[i_s1 + 1, j_s2] - 2.0 * U[i_s1, j_s2] + U[i_s1 - 1, j_s2]) / (ds1 * ds1))
        gamma_2 = float((U[i_s1, j_s2 + 1] - 2.0 * U[i_s1, j_s2] + U[i_s1, j_s2 - 1]) / (ds2 * ds2))

        return ADI2DPDEResult(
            spot1_grid=s1_grid,
            spot2_grid=s2_grid,
            price_grid=U,
            price_at_spot=p_spot,
            delta_s1=delta_1,
            delta_s2=delta_2,
            gamma_s1=gamma_1,
            gamma_s2=gamma_2,
            is_american=is_american,
        )


# ==============================================================================
# 3. MERTON-KMV STRUCTURAL MODEL & VASICEK ASRF BASEL PORTFOLIO CAPITAL
# ==============================================================================

@dataclass
class KMVResult:
    asset_value: float
    asset_volatility: float
    distance_to_default: float
    expected_default_frequency: float
    leverage_ratio: float


@dataclass
class VasicekASRFResult:
    portfolio_pd: float
    lgd: float
    asset_correlation: float
    confidence_level: float
    var_capital_pct: float
    expected_loss_pct: float
    unexpected_loss_capital_pct: float
    maturity_adjustment: float
    rwa_per_million: float


class KMVVasicekCreditEngine:
    """KMV structural default model and Basel II/III Vasicek ASRF portfolio capital engine.
    
    References:
    - Crosbie, P., & Bohn, J. (2003). Modeling Default Risk (Moody's KMV).
    - Vasicek, O. (2002). The Distribution of Loan Portfolio Value.
    - Basel Committee on Banking Supervision (BCBS) Comprehensive Framework.
    """

    @staticmethod
    def solve_kmv_asset_parameters(
        equity_val: float,
        equity_vol: float,
        debt_nominal: float,
        r: float,
        t: float = 1.0,
        mu_a: float = 0.05,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> KMVResult:
        """Solves simultaneous non-linear system for unobserved (V_A, sigma_A).
        
        1) E = V_A * N(d1) - D * exp(-r*T) * N(d2)
        2) sigma_E = (V_A / E) * N(d1) * sigma_A
        """
        # Initial guesses
        v_a = equity_val + debt_nominal
        sigma_a = equity_vol * (equity_val / v_a)

        disc_debt = debt_nominal * math.exp(-r * t)

        for _ in range(max_iter):
            std = sigma_a * math.sqrt(t)
            d1 = (math.log(v_a / debt_nominal) + (r + 0.5 * sigma_a * sigma_a) * t) / std
            d2 = d1 - std

            nd1 = norm_cdf(d1)
            nd2 = norm_cdf(d2)

            f1 = v_a * nd1 - disc_debt * nd2 - equity_val
            f2 = (v_a / equity_val) * nd1 * sigma_a - equity_vol

            if abs(f1) < tol and abs(f2) < tol:
                break

            # Update V_A from equation 1 (fixed point / Newton step)
            v_a_new = (equity_val + disc_debt * nd2) / max(nd1, 1e-6)
            # Update sigma_A from equation 2
            sigma_a_new = (equity_vol * equity_val) / max(v_a_new * nd1, 1e-6)

            v_a = 0.5 * (v_a + v_a_new)
            sigma_a = 0.5 * (sigma_a + sigma_a_new)

        # Distance to Default (DD)
        dd = (math.log(v_a / debt_nominal) + (mu_a - 0.5 * sigma_a * sigma_a) * t) / (sigma_a * math.sqrt(t))
        edf = norm_cdf(-dd)
        leverage = debt_nominal / v_a

        return KMVResult(
            asset_value=v_a,
            asset_volatility=sigma_a,
            distance_to_default=dd,
            expected_default_frequency=edf,
            leverage_ratio=leverage,
        )

    @staticmethod
    def calculate_vasicek_asrf(
        pd: float,
        lgd: float = 0.45,
        rho: Optional[float] = None,
        confidence_level: float = 0.999,
        maturity_years: float = 2.5,
        ead: float = 1_000_000.0,
    ) -> VasicekASRFResult:
        """Calculates Basel ASRF regulatory capital requirement and Unexpected Loss (UL).
        
        VaR_alpha = LGD * N( (N^{-1}(PD) + sqrt(rho)*N^{-1}(alpha)) / sqrt(1 - rho) )
        """
        if pd <= 0.0 or pd >= 1.0:
            raise ValueError("PD must be in (0, 1).")

        # Basel standard corporate correlation formula if rho is not provided
        if rho is None:
            rho = 0.12 * ((1.0 - math.exp(-50.0 * pd)) / (1.0 - math.exp(-50.0))) + \
                  0.24 * (1.0 - (1.0 - math.exp(-50.0 * pd)) / (1.0 - math.exp(-50.0)))

        q_norm = norm_inv(confidence_level)
        pd_norm = norm_inv(pd)

        cond_pd = norm_cdf((pd_norm + math.sqrt(rho) * q_norm) / math.sqrt(1.0 - rho))
        var_capital = lgd * cond_pd
        el = pd * lgd

        # Basel maturity adjustment
        b = (0.11852 - 0.05478 * math.log(pd)) ** 2
        ma = (1.0 + (maturity_years - 2.5) * b) / (1.0 - 1.5 * b)

        ul_capital = max(var_capital - el, 0.0) * ma
        rwa = ul_capital * 12.5 * ead

        return VasicekASRFResult(
            portfolio_pd=pd,
            lgd=lgd,
            asset_correlation=rho,
            confidence_level=confidence_level,
            var_capital_pct=var_capital,
            expected_loss_pct=el,
            unexpected_loss_capital_pct=ul_capital,
            maturity_adjustment=ma,
            rwa_per_million=rwa,
        )


# ==============================================================================
# 4. KYLE (1985) CONTINUOUS DEPTH & VAYANOS-WANG (2012) OTC SEARCH LIQUIDITY
# ==============================================================================

@dataclass
class KyleEquilibriumResult:
    lambda_depth: float  # Price impact parameter
    beta_trading: float  # Informed trading aggressiveness
    expected_profit: float
    residual_variance: float
    price_trajectory: List[float]
    order_flow_trajectory: List[float]


@dataclass
class VayanosWangOTCResult:
    unconstrained_price: float
    dealer_bid_price: float
    dealer_ask_price: float
    bid_ask_spread: float
    illiquidity_discount_pct: float
    search_friction_component: float
    inventory_penalty_component: float


class KyleVayanosMarketMicrostructureEngine:
    """Continuous informed trading and OTC search-and-bargaining asset pricing engine.
    
    References:
    - Kyle, A. S. (1985). Continuous Auctions and Informed Trader.
    - Vayanos, D., & Wang, T. (2012). Liquidity and Asset Prices under Asymmetric Information and Search Frictions.
    """

    @staticmethod
    def solve_kyle_continuous(
        prior_mean: float,
        prior_var: float,
        noise_var_rate: float,
        horizon_t: float = 1.0,
        true_value: float = 105.0,
        num_steps: int = 50,
        seed: int = 42,
    ) -> KyleEquilibriumResult:
        """Simulates Kyle's continuous auction equilibrium with constant lambda.
        
        lambda = sqrt(Sigma_0) / (sigma_u * sqrt(T))
        beta(t) = sigma_u / sqrt(Sigma_0 * (1 - t/T))
        """
        np.random.seed(seed)
        sigma_u = math.sqrt(noise_var_rate)
        lam = math.sqrt(prior_var) / (sigma_u * math.sqrt(horizon_t))

        dt = horizon_t / num_steps
        p = prior_mean
        prices = [p]
        orders = [0.0]

        curr_sigma = prior_var

        for step in range(num_steps):
            t = step * dt
            time_left = max(horizon_t - t, dt * 0.1)
            beta_t = sigma_u / math.sqrt(prior_var * (time_left / horizon_t))

            # Noise trading innovation
            dz = np.random.normal(0.0, sigma_u * math.sqrt(dt))

            # Informed order flow
            dx = beta_t * (true_value - p) * dt
            dy = dx + dz

            # Price update
            p += lam * dy
            prices.append(p)
            orders.append(dy)

        res_var = prior_var * (1.0 - (num_steps * dt) / horizon_t)
        exp_profit = 0.5 * abs(true_value - prior_mean) * sigma_u * math.sqrt(horizon_t)

        return KyleEquilibriumResult(
            lambda_depth=lam,
            beta_trading=sigma_u / math.sqrt(prior_var),
            expected_profit=exp_profit,
            residual_variance=max(res_var, 0.0),
            price_trajectory=prices,
            order_flow_trajectory=orders,
        )

    @staticmethod
    def calculate_vayanos_wang_otc_spread(
        unconstrained_price: float,
        low_utility_flow: float,
        high_utility_flow: float,
        r: float,
        search_intensity: float,
        dealer_inventory: float,
        dealer_carrying_cost: float,
        dealer_bargaining_power: float = 0.5,
    ) -> VayanosWangOTCResult:
        """Computes OTC bid-ask prices with search frictions and dealer inventory penalties.
        
        Bid = P* - Delta_search - Delta_inventory
        """
        # Search friction wedge between high and low valuation states
        delta_search = (high_utility_flow - low_utility_flow) / (r + search_intensity)
        # Dealer inventory financing and capital constraint wedge
        delta_inv = (dealer_carrying_cost * max(dealer_inventory, 0.0)) / max(1.0 - dealer_bargaining_power, 0.01)

        bid = unconstrained_price - (1.0 - dealer_bargaining_power) * delta_search - delta_inv
        ask = unconstrained_price + dealer_bargaining_power * delta_search + (0.5 * delta_inv)

        spread = max(ask - bid, 0.0)
        discount_pct = max((unconstrained_price - bid) / unconstrained_price, 0.0)

        return VayanosWangOTCResult(
            unconstrained_price=unconstrained_price,
            dealer_bid_price=bid,
            dealer_ask_price=ask,
            bid_ask_spread=spread,
            illiquidity_discount_pct=discount_pct,
            search_friction_component=delta_search,
            inventory_penalty_component=delta_inv,
        )


# ==============================================================================
# 5. LEUNG & LI (2015) OU OPTIMAL DOUBLE-STOPPING & STOP-LOSS ENGINE
# ==============================================================================

@dataclass
class LeungLiOptimalPolicyResult:
    mean_reversion_theta: float
    equilibrium_mu: float
    volatility_sigma: float
    optimal_entry_level: float
    optimal_exit_level: float
    stop_loss_level: float
    expected_entry_delay: float
    expected_trade_duration: float
    expected_net_profit: float


class LeungLiOptimalStoppingEngine:
    """Optimal double-stopping boundaries for Ornstein-Uhlenbeck statistical arbitrage.
    
    References:
    - Leung, T., & Li, X. (2015). Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss.
    - Song, Q. S., Yin, G., & Zhang, Q. (2009). Optimal entry and exit times in pairs trading.
    """

    @staticmethod
    def calculate_optimal_boundaries(
        theta: float,
        mu: float,
        sigma: float,
        r: float,
        c_entry: float = 0.005,
        c_exit: float = 0.005,
        stop_loss_l: Optional[float] = None,
    ) -> LeungLiOptimalPolicyResult:
        """Determines optimal entry d*, target exit b*, and stop-loss L on OU spread.
        
        dX_t = theta*(mu - X_t)*dt + sigma*dW_t
        """
        if theta <= 0.0 or sigma <= 0.0:
            raise ValueError("Theta and sigma must be positive.")

        stationary_std = sigma / math.sqrt(2.0 * theta)

        # Default stop-loss at -2.5 standard deviations if not supplied
        if stop_loss_l is None:
            stop_loss_l = mu - 2.5 * stationary_std

        # Analytical heuristic bounds derived from Leung & Li variational inequality:
        # Exit level b* is above mu + transaction costs:
        b_star = mu + 0.84 * stationary_std + (c_exit * 1.5)
        # Entry level d* is below mu - transaction costs:
        d_star = mu - 0.95 * stationary_std - (c_entry * 1.5)

        # Ensure d* > stop_loss_l
        if d_star <= stop_loss_l:
            d_star = stop_loss_l + 0.2 * stationary_std

        # Expected times to hit boundaries via Ornstein-Uhlenbeck first passage time
        # E[tau_{d* | mu}] ~= (1/theta) * ln((mu - d*) / stationary_std + 1)
        entry_delay = (1.0 / theta) * math.log(abs(mu - d_star) / stationary_std + 1.0)
        trade_duration = (1.0 / theta) * math.log(abs(b_star - d_star) / stationary_std + 1.0)

        # Expected profit considering entry and exit costs
        exp_pnl = (b_star - d_star) - (c_entry + c_exit)

        return LeungLiOptimalPolicyResult(
            mean_reversion_theta=theta,
            equilibrium_mu=mu,
            volatility_sigma=sigma,
            optimal_entry_level=d_star,
            optimal_exit_level=b_star,
            stop_loss_level=stop_loss_l,
            expected_entry_delay=entry_delay,
            expected_trade_duration=trade_duration,
            expected_net_profit=exp_pnl,
        )


# ==============================================================================
# 6. PENDLE YIELDSPACE AMM & AAVE V3 E-MODE DE-PEG CASCADE PHYSICS
# ==============================================================================

@dataclass
class PendleYieldSpaceResult:
    pt_price: float
    yt_price: float
    implied_apy: float
    maturity_years: float
    slippage_pct: float
    new_pt_reserve: float
    new_asset_reserve: float


@dataclass
class AaveEModeRiskResult:
    health_factor: float
    current_ltv: float
    max_emode_ltv: float
    liquidation_threshold: float
    critical_depeg_pct: float
    is_liquidatable: bool
    liquidation_bonus_pct: float
    max_safe_borrow: float


class PendleAaveDeFiEngine:
    """Pendle YieldSpace AMM invariant and Aave v3 E-Mode high-leverage liquidation mechanics.
    
    References:
    - Pendle Finance Documentation & YieldSpace Whitepaper (2021).
    - Aave v3 Technical Paper: Efficiency Mode & Cross-Collateral Risk Engine.
    """

    @staticmethod
    def strip_yield_tokens(
        sy_price: float,
        implied_apy: float,
        maturity_years: float,
    ) -> Tuple[float, float]:
        """Separates Standardized Yield into Principal Token (PT) and Yield Token (YT).
        
        P_PT = 1 / (1 + APY)^t
        P_YT = P_SY - P_PT
        """
        if maturity_years <= 0.0:
            return sy_price, 0.0

        p_pt = 1.0 / math.pow(1.0 + implied_apy, maturity_years)
        p_yt = max(sy_price - p_pt, 0.0)
        return p_pt, p_yt

    @staticmethod
    def yieldspace_swap_pt(
        pt_reserve: float,
        asset_reserve: float,
        maturity_years: float,
        pt_in: float,
    ) -> PendleYieldSpaceResult:
        """Executes swap on Pendle YieldSpace AMM invariant: x^{1-t} + y^{1-t} = K.
        
        Solves for output asset when PT is deposited into the liquidity pool.
        """
        if maturity_years <= 0.0:
            # At maturity, PT trades 1:1 with underlying asset
            return PendleYieldSpaceResult(
                pt_price=1.0,
                yt_price=0.0,
                implied_apy=0.0,
                maturity_years=0.0,
                slippage_pct=0.0,
                new_pt_reserve=pt_reserve + pt_in,
                new_asset_reserve=asset_reserve - pt_in,
            )

        power = 1.0 - maturity_years
        k = math.pow(pt_reserve, power) + math.pow(asset_reserve, power)

        new_pt = pt_reserve + pt_in
        new_asset = math.pow(k - math.pow(new_pt, power), 1.0 / power)

        asset_out = asset_reserve - new_asset

        # Marginal spot price: d(asset) / d(PT)
        spot_pt_price = math.pow(pt_reserve / asset_reserve, maturity_years)
        effective_price = asset_out / pt_in
        slippage = max((spot_pt_price - effective_price) / spot_pt_price, 0.0)

        implied_apy = math.pow(1.0 / effective_price, 1.0 / maturity_years) - 1.0
        p_yt = max(1.0 - effective_price, 0.0)

        return PendleYieldSpaceResult(
            pt_price=effective_price,
            yt_price=p_yt,
            implied_apy=implied_apy,
            maturity_years=maturity_years,
            slippage_pct=slippage,
            new_pt_reserve=new_pt,
            new_asset_reserve=new_asset,
        )

    @staticmethod
    def evaluate_aave_emode(
        collateral_units: float,
        collateral_price: float,
        borrowed_units: float,
        debt_price: float,
        emode_ltv: float = 0.97,
        emode_lt: float = 0.98,
        liquidation_bonus: float = 0.015,
    ) -> AaveEModeRiskResult:
        """Evaluates Aave v3 E-Mode health factor, leverage capacity, and critical de-peg shock.
        
        HF = (Collateral * Price_coll * LT) / (Debt * Price_debt)
        """
        collateral_val = collateral_units * collateral_price
        debt_val = borrowed_units * debt_price

        if debt_val <= 1e-12:
            return AaveEModeRiskResult(
                health_factor=999.0,
                current_ltv=0.0,
                max_emode_ltv=emode_ltv,
                liquidation_threshold=emode_lt,
                critical_depeg_pct=-1.0,
                is_liquidatable=False,
                liquidation_bonus_pct=liquidation_bonus,
                max_safe_borrow=collateral_val * emode_ltv,
            )

        current_ltv = debt_val / collateral_val
        hf = (collateral_val * emode_lt) / debt_val
        is_liq = hf < 1.0

        # Critical price de-peg required to trigger liquidation:
        # (Collateral * Price_coll * (1 + delta) * LT) / Debt_val = 1.0
        # 1 + delta = Debt_val / (Collateral_val * LT)
        crit_depeg = (debt_val / (collateral_val * emode_lt)) - 1.0

        max_safe_borrow = collateral_val * emode_ltv

        return AaveEModeRiskResult(
            health_factor=hf,
            current_ltv=current_ltv,
            max_emode_ltv=emode_ltv,
            liquidation_threshold=emode_lt,
            critical_depeg_pct=crit_depeg,
            is_liquidatable=is_liq,
            liquidation_bonus_pct=liquidation_bonus,
            max_safe_borrow=max_safe_borrow,
        )

    @staticmethod
    def simulate_depeg_cascade(
        collateral_units: float,
        debt_units: float,
        initial_price_ratio: float,
        depeg_path: List[float],
        emode_ltv: float = 0.97,
        emode_lt: float = 0.98,
        liquidation_bonus: float = 0.015,
    ) -> List[Dict[str, Any]]:
        """Simulates path of health factor and liquidation cascade as collateral de-pegs from debt."""
        results = []
        debt_price = 1.0

        for price_ratio in depeg_path:
            coll_price = price_ratio
            risk = PendleAaveDeFiEngine.evaluate_aave_emode(
                collateral_units=collateral_units,
                collateral_price=coll_price,
                borrowed_units=debt_units,
                debt_price=debt_price,
                emode_ltv=emode_ltv,
                emode_lt=emode_lt,
                liquidation_bonus=liquidation_bonus,
            )
            results.append({
                "collateral_price": coll_price,
                "health_factor": risk.health_factor,
                "is_liquidatable": risk.is_liquidatable,
                "current_ltv": risk.current_ltv,
                "critical_depeg_pct": risk.critical_depeg_pct,
            })
        return results
