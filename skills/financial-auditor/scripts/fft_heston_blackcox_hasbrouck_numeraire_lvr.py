"""
FFT_HESTON_BLACKCOX_HASBROUCK_NUMERAIRE_LVR.PY
Entropy AI - Phase 34: Advanced Quantitative Financial Engineering, Fourier Pricing,
Credit Barrier Structural Models, Microstructure Price Discovery & Cryptoeconomic LVR.

Modules:
1. Carr-Madan (1999) Fast Fourier Transform (FFT) Option Pricing Engine
   - Characteristic function mapping, dampening factor alpha, Simpson's quadrature weights
   - Arbitrage-free whole-smile surface pricing in O(N log N) time
2. Heston (1993) Semi-Analytic Formulation & Albrecher et al. (2007) Little-Trap Resolution
   - Branch-cut-free continuous complex logarithm formulation
   - Gauss-Legendre quadrature integration for P1 and P2, implied volatility solver
3. Black & Cox (1976) First-Passage Time Credit Risk & Safety Covenant Engine
   - Time-dependent exponential absorbing barrier C(t) = K * exp(-gamma * (T - t))
   - Analytic first-passage hitting distribution, survival probability, credit spread curve
4. Hasbrouck (1991) Information Share & Gonzalo-Granger (1995) Component Share
   - Cointegrated multi-venue price discovery, VECM permanent-transitory decomposition
   - Cholesky factorization upper/lower bounds and orthogonalized information share
5. Geman, El Karoui & Rochet (1995) Change of Numeraire & Forward Neutral Measure Engine
   - Radon-Nikodym derivative, P(t, T) bond numeraire, forward price martingale property
   - Margrabe (1978) asset exchange option derived via pure numeraire transformation
6. Milionis, Moallemi, Roughgarden & Zhang (2022) Loss-Versus-Rebalancing (LVR) Microstructure
   - Continuous-time toxic arbitrage extraction vs path-independent Impermanent Loss
   - Concentrated liquidity (Uniswap v3) LVR and LP fee-to-volatility breakeven condition
"""

import math
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import numpy as np


# ==============================================================================
# 0. HELPER FUNCTIONS & NORMAL DISTRIBUTION
# ==============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _black_scholes_call_price(s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Analytical Black-Scholes call price with continuous dividend yield q."""
    if t <= 0.0 or sigma <= 0.0:
        return max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t))
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return s * math.exp(-q * t) * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)


def _black_scholes_implied_vol(s: float, k: float, t: float, r: float, price: float, q: float = 0.0) -> float:
    """Invert Black-Scholes formula for implied volatility using Brent / Newton bisection."""
    intrinsic = max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t))
    if price <= intrinsic:
        return 0.001
    
    vol_low, vol_high = 0.001, 5.0
    for _ in range(60):
        vol_mid = 0.5 * (vol_low + vol_high)
        p_mid = _black_scholes_call_price(s, k, t, r, vol_mid, q)
        if abs(p_mid - price) < 1e-7:
            return vol_mid
        if p_mid > price:
            vol_high = vol_mid
        else:
            vol_low = vol_mid
    return 0.5 * (vol_low + vol_high)


# ==============================================================================
# 1. CARR-MADAN (1999) FAST FOURIER TRANSFORM (FFT) OPTION PRICING ENGINE
# ==============================================================================

@dataclass
class FFTPriceResult:
    strikes: np.ndarray
    call_prices: np.ndarray
    put_prices: np.ndarray
    implied_vols: np.ndarray
    grid_points: int
    alpha: float
    eta: float
    lambda_k: float


class CarrMadanFFTEngine:
    """
    Carr & Madan (1999) Fast Fourier Transform Option Pricing Engine.
    Prices European calls across an entire strike grid in O(N log N) using
    the characteristic function phi(u) = E[exp(i * u * ln(S_T))].
    """

    def __init__(self, s0: float, r: float, t: float, q: float = 0.0):
        if s0 <= 0 or t <= 0:
            raise ValueError("s0 and t must be positive.")
        self.s0 = float(s0)
        self.r = float(r)
        self.t = float(t)
        self.q = float(q)

    @staticmethod
    def black_scholes_char_func(s0: float, r: float, t: float, sigma: float, q: float = 0.0) -> Callable[[complex], complex]:
        """Return the analytical characteristic function of log(S_T) under Black-Scholes."""
        drift = math.log(s0) + (r - q - 0.5 * sigma * sigma) * t
        variance = sigma * sigma * t

        def phi(u: complex) -> complex:
            return np.exp(1j * u * drift - 0.5 * variance * (u ** 2))

        return phi

    def price_options_fft(
        self,
        char_func: Callable[[complex], complex],
        n: int = 4096,
        alpha: float = 1.5,
        eta: float = 0.25,
    ) -> FFTPriceResult:
        """
        Execute Carr-Madan FFT pricing algorithm.
        - n: Number of discretization points (power of 2, e.g. 1024, 2048, 4096)
        - alpha: Dampening parameter (typically 1.2 to 1.75)
        - eta: Grid spacing in Fourier space (delta_v)
        """
        if (n & (n - 1)) != 0:
            raise ValueError("n must be a power of 2 for FFT efficiency.")
        if alpha <= 0:
            raise ValueError("alpha must be positive for dampening.")

        # Log-strike grid spacing lambda_k = 2 * pi / (n * eta)
        lambda_k = (2.0 * math.pi) / (n * eta)
        b = (n * lambda_k) / 2.0  # k ranges from -b to +b
        k_grid = -b + np.arange(n) * lambda_k
        strikes = np.exp(k_grid)

        # Fourier frequencies v_j = j * eta
        v_j = np.arange(n) * eta

        # Simpson's rule weights: (3 + (-1)^j - delta_{j0}) / 3
        simpson_weights = np.empty(n, dtype=float)
        simpson_weights[0] = 1.0 / 3.0
        for j in range(1, n):
            simpson_weights[j] = (4.0 if j % 2 == 1 else 2.0) / 3.0
        simpson_weights[-1] = 1.0 / 3.0

        # Evaluate dampened Fourier transform psi(v)
        # psi(v) = exp(-r * T) * phi(v - (alpha + 1) * i) / [alpha^2 + alpha - v^2 + i * (2 * alpha + 1) * v]
        u_shifted = v_j - (alpha + 1.0) * 1j
        phi_vals = np.array([char_func(u) for u in u_shifted], dtype=complex)

        denom = (alpha ** 2 + alpha - v_j ** 2) + 1j * (2.0 * alpha + 1.0) * v_j
        psi_vals = np.exp(-self.r * self.t) * phi_vals / denom

        # Construct input array for standard FFT: x_j = exp(i * b * v_j) * psi(v_j) * eta * simpson_weights
        fft_input = np.exp(1j * b * v_j) * psi_vals * eta * simpson_weights
        fft_output = np.fft.fft(fft_input)

        # Call prices: C(k_u) = exp(-alpha * k_u) / pi * Re(fft_output)
        call_prices = (np.exp(-alpha * k_grid) / math.pi) * np.real(fft_output)
        call_prices = np.maximum(0.0, call_prices)

        # Put prices via Put-Call Parity: P = C - S0 * exp(-q*T) + K * exp(-r*T)
        discounted_s = self.s0 * math.exp(-self.q * self.t)
        discounted_k = strikes * math.exp(-self.r * self.t)
        put_prices = np.maximum(0.0, call_prices - discounted_s + discounted_k)

        # Filter realistic strike window around spot (e.g. 0.4 * S0 to 2.5 * S0)
        valid_mask = (strikes >= 0.4 * self.s0) & (strikes <= 2.5 * self.s0)
        sub_strikes = strikes[valid_mask]
        sub_calls = call_prices[valid_mask]
        sub_puts = put_prices[valid_mask]

        implied_vols = np.array([
            _black_scholes_implied_vol(self.s0, k, self.t, self.r, cp, self.q)
            for k, cp in zip(sub_strikes, sub_calls)
        ])

        return FFTPriceResult(
            strikes=sub_strikes,
            call_prices=sub_calls,
            put_prices=sub_puts,
            implied_vols=implied_vols,
            grid_points=n,
            alpha=alpha,
            eta=eta,
            lambda_k=lambda_k
        )

    def price_single_strike(
        self,
        char_func: Callable[[complex], complex],
        target_strike: float,
        n: int = 4096,
        alpha: float = 1.5,
        eta: float = 0.25
    ) -> Dict[str, float]:
        """Interpolate FFT surface for an exact target strike."""
        res = self.price_options_fft(char_func, n=n, alpha=alpha, eta=eta)
        call_interp = float(np.interp(target_strike, res.strikes, res.call_prices))
        put_interp = float(np.interp(target_strike, res.strikes, res.put_prices))
        iv_interp = float(np.interp(target_strike, res.strikes, res.implied_vols))
        return {
            "target_strike": target_strike,
            "call_price": call_interp,
            "put_price": put_interp,
            "implied_vol": iv_interp
        }


# ==============================================================================
# 2. HESTON (1993) LITTLE-TRAP SEMI-ANALYTIC PRICING ENGINE
# ==============================================================================

@dataclass
class HestonPricingResult:
    call_price: float
    put_price: float
    p1: float
    p2: float
    implied_vol: float
    feller_ratio: float
    feller_satisfied: bool


class HestonLittleTrapEngine:
    """
    Heston (1993) Stochastic Volatility Semi-Analytic Pricing Engine.
    Uses the branch-cut-free formulation of Albrecher, Mayer, Schoutens & Tistaert (2007)
    ('The Little Trap') to prevent discontinuities in the complex logarithm.
    
    dS_t = (r - q) S_t dt + sqrt(V_t) S_t dW_t^S
    dV_t = kappa * (theta - V_t) dt + sigma_v * sqrt(V_t) dW_t^V
    Corr(dW^S, dW^V) = rho
    """

    def __init__(
        self,
        kappa: float,
        theta: float,
        sigma_v: float,
        v0: float,
        rho: float,
        r: float,
        q: float = 0.0
    ):
        if kappa <= 0 or theta <= 0 or sigma_v <= 0 or v0 <= 0:
            raise ValueError("Heston parameters kappa, theta, sigma_v, v0 must be positive.")
        if not (-1.0 <= rho <= 1.0):
            raise ValueError("rho must be within [-1, 1].")

        self.kappa = float(kappa)
        self.theta = float(theta)
        self.sigma_v = float(sigma_v)
        self.v0 = float(v0)
        self.rho = float(rho)
        self.r = float(r)
        self.q = float(q)

    @property
    def feller_ratio(self) -> float:
        """Feller condition ratio: 2 * kappa * theta / (sigma_v^2). Ratio > 1 ensures V_t > 0."""
        return (2.0 * self.kappa * self.theta) / (self.sigma_v ** 2)

    def characteristic_function(self, u: complex, s0: float, t: float) -> complex:
        """
        Albrecher et al. (2007) stable formulation of Heston characteristic function
        phi(u) = E[exp(i * u * ln(S_T))].
        Ensures continuous complex logarithm across all maturities and strikes.
        """
        kappa = self.kappa
        theta = self.theta
        sigma = self.sigma_v
        rho = self.rho
        v0 = self.v0
        r = self.r
        q = self.q

        # d = sqrt((kappa - i * rho * sigma * u)^2 + sigma^2 * (u^2 + i * u))
        alpha_term = kappa - 1j * rho * sigma * u
        d = np.sqrt(alpha_term ** 2 + (sigma ** 2) * (u ** 2 + 1j * u))

        # Albrecher formulation: g = (kappa - i * rho * sigma * u - d) / (kappa - i * rho * sigma * u + d)
        g = (alpha_term - d) / (alpha_term + d)

        # C(u, tau) and D(u, tau)
        exp_minus_dt = np.exp(-d * t)
        c_term = (r - q) * 1j * u * t + (kappa * theta / (sigma ** 2)) * (
            (alpha_term - d) * t - 2.0 * np.log((1.0 - g * exp_minus_dt) / (1.0 - g))
        )
        d_term = ((alpha_term - d) / (sigma ** 2)) * ((1.0 - exp_minus_dt) / (1.0 - g * exp_minus_dt))

        return np.exp(c_term + d_term * v0 + 1j * u * math.log(s0))

    def price_european(
        self,
        s0: float,
        k: float,
        t: float,
        n_quad: int = 128,
        u_max: float = 100.0
    ) -> HestonPricingResult:
        """
        Price European call and put using Gauss-Legendre quadrature integration
        over the Gil-Pelaez inversion formula.
        """
        # Gauss-Legendre nodes and weights on [-1, 1]
        nodes, weights = np.polynomial.legendre.leggauss(n_quad)
        # Change of interval from [-1, 1] to [0, u_max]
        u_nodes = 0.5 * u_max * (nodes + 1.0)
        u_weights = 0.5 * u_max * weights

        ln_k = math.log(k)

        # Integrands for P1 and P2:
        # P2: characteristic function with argument u
        # P1: characteristic function with argument (u - i) normalized by S0 * exp((r-q)*t)
        phi_2_vals = np.array([self.characteristic_function(u, s0, t) for u in u_nodes])
        phi_1_vals = np.array([
            self.characteristic_function(u - 1j, s0, t) / (s0 * math.exp((self.r - self.q) * t))
            for u in u_nodes
        ])

        integrand_1 = np.real(np.exp(-1j * u_nodes * ln_k) * phi_1_vals / (1j * u_nodes))
        integrand_2 = np.real(np.exp(-1j * u_nodes * ln_k) * phi_2_vals / (1j * u_nodes))

        int_1 = float(np.sum(u_weights * integrand_1))
        int_2 = float(np.sum(u_weights * integrand_2))

        p1 = 0.5 + (1.0 / math.pi) * int_1
        p2 = 0.5 + (1.0 / math.pi) * int_2

        # Numerical bounds for probabilities [0, 1]
        p1 = max(0.0, min(1.0, p1))
        p2 = max(0.0, min(1.0, p2))

        call_price = s0 * math.exp(-self.q * t) * p1 - k * math.exp(-self.r * t) * p2
        call_price = max(0.0, call_price)

        # Put price via Put-Call Parity
        put_price = max(0.0, call_price - s0 * math.exp(-self.q * t) + k * math.exp(-self.r * t))

        implied_vol = _black_scholes_implied_vol(s0, k, t, self.r, call_price, self.q)

        return HestonPricingResult(
            call_price=call_price,
            put_price=put_price,
            p1=p1,
            p2=p2,
            implied_vol=implied_vol,
            feller_ratio=self.feller_ratio,
            feller_satisfied=(self.feller_ratio > 1.0)
        )


# ==============================================================================
# 3. BLACK & COX (1976) FIRST-PASSAGE CREDIT DEFAULT & COVENANT ENGINE
# ==============================================================================

@dataclass
class BlackCoxCreditResult:
    firm_value: float
    covenant_barrier_0: float
    covenant_barrier_t: float
    survival_probability: float
    cumulative_default_prob: float
    risky_bond_price: float
    risk_free_bond_price: float
    credit_spread_bps: float
    hazard_rate_equivalent: float


class BlackCoxCreditEngine:
    """
    Black & Cox (1976) Structural Credit Risk Engine with Safety Covenants.
    Default occurs at the FIRST TIME the firm value V_t hits the absorbing
    time-dependent barrier C(t) = K * exp(-gamma * (T - t)).
    
    dV_t = (r - q) V_t dt + sigma_V V_t dW_t
    """

    def __init__(self, r: float, q: float = 0.0):
        self.r = float(r)
        self.q = float(q)

    def survival_probability(
        self,
        v0: float,
        k_barrier: float,
        gamma: float,
        t: float,
        sigma_v: float
    ) -> float:
        """
        Analytic survival probability Q(tau > T) under Black-Cox absorbing barrier.
        Barrier: C(t) = k_barrier * exp(-gamma * (T - t)).
        At t=0, C(0) = k_barrier * exp(-gamma * T).
        """
        if v0 <= 0 or k_barrier <= 0 or sigma_v <= 0 or t <= 0:
            raise ValueError("v0, k_barrier, sigma_v, t must be strictly positive.")

        c0 = k_barrier * math.exp(-gamma * t)
        if v0 <= c0:
            return 0.0  # Already defaulted at t=0

        # Drift of Y_t = ln(V_t / C(t)): mu = r - q - 0.5 * sigma_v^2 - gamma
        mu = self.r - self.q - 0.5 * (sigma_v ** 2) - gamma
        y0 = math.log(v0 / c0)
        sqrt_t = math.sqrt(t)

        d1 = (y0 + mu * t) / (sigma_v * sqrt_t)
        d2 = (-y0 + mu * t) / (sigma_v * sqrt_t)

        # Scale factor: exp(-2 * mu * y0 / sigma_v^2)
        exponent = -2.0 * mu * y0 / (sigma_v ** 2)
        # Avoid numerical overflow in exponent
        exp_factor = math.exp(max(-100.0, min(100.0, exponent)))

        q_surv = _norm_cdf(d1) - exp_factor * _norm_cdf(d2)
        return max(0.0, min(1.0, q_surv))

    def price_corporate_bond(
        self,
        v0: float,
        face_value: float,
        k_barrier: float,
        gamma: float,
        t: float,
        sigma_v: float,
        recovery_rate: float = 0.40
    ) -> BlackCoxCreditResult:
        """
        Price zero-coupon corporate bond under Black-Cox safety covenants.
        If no default: pays face_value at T.
        If default: recovery is paid based on fraction of covenant barrier or face value.
        """
        c0 = k_barrier * math.exp(-gamma * t)
        c_t = k_barrier
        surv_prob = self.survival_probability(v0, k_barrier, gamma, t, sigma_v)
        default_prob = 1.0 - surv_prob

        # Risk-free bond price
        p_rf = face_value * math.exp(-self.r * t)

        # Risky bond value: discounted expected payoff
        # Standard industrial proxy:
        p_risky = face_value * math.exp(-self.r * t) * (surv_prob + recovery_rate * default_prob)

        # Credit spread in basis points: s = -ln(P_risky / Face) / T - r
        if p_risky > 0:
            yield_to_mat = -math.log(p_risky / face_value) / t
            credit_spread = max(0.0, yield_to_mat - self.r)
            spread_bps = credit_spread * 10000.0
        else:
            spread_bps = 10000.0

        hazard_equiv = -math.log(max(1e-12, surv_prob)) / t

        return BlackCoxCreditResult(
            firm_value=v0,
            covenant_barrier_0=c0,
            covenant_barrier_t=c_t,
            survival_probability=surv_prob,
            cumulative_default_prob=default_prob,
            risky_bond_price=p_risky,
            risk_free_bond_price=p_rf,
            credit_spread_bps=spread_bps,
            hazard_rate_equivalent=hazard_equiv
        )


# ==============================================================================
# 4. HASBROUCK (1991) INFORMATION SHARE & GONZALO-GRANGER (1995) COMPONENT SHARE
# ==============================================================================

@dataclass
class HasbrouckPriceDiscoveryResult:
    hasbrouck_is_lower: np.ndarray
    hasbrouck_is_upper: np.ndarray
    hasbrouck_is_mid: np.ndarray
    gonzalo_granger_cs: np.ndarray
    common_factor_variance: float
    cointegrating_vector: np.ndarray
    alpha_adjustment_speeds: np.ndarray


class HasbrouckPriceDiscoveryEngine:
    """
    Hasbrouck (1991) Information Share (IS) & Gonzalo-Granger (1995) Component Share (CS).
    Measures the share of price discovery contributed by multiple trading venues
    (e.g., Binance vs CME, Nasdaq vs Dark Pools) in a cointegrated price system.
    """

    @staticmethod
    def estimate_price_discovery(
        price_series: np.ndarray,
        lags: int = 1
    ) -> HasbrouckPriceDiscoveryResult:
        """
        Estimate IS and CS from concurrent log-price series of K venues.
        price_series: array of shape (T, K)
        """
        t_obs, k_venues = price_series.shape
        if k_venues < 2:
            raise ValueError("At least 2 venues required for price discovery analysis.")

        # Log returns delta_P: shape (T-1, K)
        returns = np.diff(price_series, axis=0)

        # Error correction term: deviations from venue 1 (basis venue)
        # z_{t-1} = P_{i, t-1} - P_{1, t-1} for i=2..K
        ecm_term = price_series[:-1, 1:] - price_series[:-1, :1]  # shape (T-1, K-1)

        # Regress returns on lagged returns and ECM term via OLS
        if t_obs > 10:
            x_reg = np.hstack([ecm_term[:-1, :], returns[:-1, :]])
            y_reg = returns[1:, :]
        else:
            x_reg = ecm_term
            y_reg = returns

        # OLS estimation of residuals
        beta_ols = np.linalg.pinv(x_reg.T @ x_reg) @ (x_reg.T @ y_reg)
        residuals = y_reg - x_reg @ beta_ols
        omega = np.cov(residuals, rowvar=False)

        # Adjustment speeds alpha from first (K-1) rows of beta_ols
        alpha = beta_ols[:k_venues - 1, :].T  # shape (K, K-1)

        # Gonzalo-Granger orthogonal vector alpha_perp
        if k_venues == 2:
            a1 = alpha[0, 0]
            a2 = alpha[1, 0]
            denom = abs(a1) + abs(a2)
            if denom > 1e-12:
                cs_weights = np.array([abs(a2) / denom, abs(a1) / denom])
            else:
                cs_weights = np.array([0.5, 0.5])
            psi = cs_weights
        else:
            u, s, vh = np.linalg.svd(alpha.T)
            alpha_perp = vh[-1, :]
            alpha_perp = np.abs(alpha_perp)
            cs_weights = alpha_perp / np.sum(alpha_perp)
            psi = cs_weights

        # Total common factor variance: psi * Omega * psi'
        common_var = float(psi @ omega @ psi.T)
        if common_var <= 1e-15:
            common_var = 1e-6

        # Hasbrouck Information Share with Cholesky factorization
        f_nat = np.linalg.cholesky(omega + 1e-12 * np.eye(k_venues))
        is_natural = ((psi @ f_nat) ** 2) / common_var

        # Reverse ordering:
        p_rev = np.eye(k_venues)[::-1]
        omega_rev = p_rev @ omega @ p_rev
        f_rev = np.linalg.cholesky(omega_rev + 1e-12 * np.eye(k_venues))
        psi_rev = psi @ p_rev
        is_rev_unordered = ((psi_rev @ f_rev) ** 2) / common_var
        is_reversed = is_rev_unordered @ p_rev

        is_lower = np.minimum(is_natural, is_reversed)
        is_upper = np.maximum(is_natural, is_reversed)
        is_mid = 0.5 * (is_lower + is_upper)

        if np.sum(is_mid) > 0:
            is_mid = is_mid / np.sum(is_mid)

        return HasbrouckPriceDiscoveryResult(
            hasbrouck_is_lower=is_lower,
            hasbrouck_is_upper=is_upper,
            hasbrouck_is_mid=is_mid,
            gonzalo_granger_cs=cs_weights,
            common_factor_variance=common_var,
            cointegrating_vector=np.array([1.0, -1.0]),
            alpha_adjustment_speeds=alpha.flatten()
        )


# ==============================================================================
# 5. GEMAN, EL KAROUI & ROCHET (1995) CHANGE OF NUMERAIRE ENGINE
# ==============================================================================

@dataclass
class NumeraireExchangeResult:
    option_value: float
    forward_ratio: float
    volatility_spread: float
    d1: float
    d2: float
    numeraire_asset: str
    target_asset: str


class NumeraireChangeEngine:
    """
    Geman, Nicole El Karoui & Jean-Charles Rochet (1995) Change of Numeraire Engine.
    Demonstrates pricing via measure changes:
    - Zero-coupon bond numeraire P(t, T) -> Forward neutral measure Q^T
    - Asset numeraire S2 -> Margrabe (1978) option to exchange S2 for S1
    """

    @staticmethod
    def margrabe_exchange_option(
        s1: float,
        s2: float,
        sigma1: float,
        sigma2: float,
        rho: float,
        t: float,
        q1: float = 0.0,
        q2: float = 0.0
    ) -> NumeraireExchangeResult:
        """
        Price Margrabe option to exchange S2 for S1: Payoff = (S1_T - S2_T)^+.
        Derived by choosing S2 as numeraire:
        Under Q^{S2}, the relative price Z_t = S1_t / S2_t is a driftless martingale
        with volatility sigma_Z = sqrt(sigma1^2 - 2*rho*sigma1*sigma2 + sigma2^2).
        """
        if s1 <= 0 or s2 <= 0 or t <= 0:
            raise ValueError("s1, s2, and t must be positive.")

        f1 = s1 * math.exp(-q1 * t)
        f2 = s2 * math.exp(-q2 * t)

        vol_sq = sigma1 ** 2 - 2.0 * rho * sigma1 * sigma2 + sigma2 ** 2
        vol_z = math.sqrt(max(1e-12, vol_sq))

        d1 = (math.log(f1 / f2) + 0.5 * (vol_z ** 2) * t) / (vol_z * math.sqrt(t))
        d2 = d1 - vol_z * math.sqrt(t)

        val = f1 * _norm_cdf(d1) - f2 * _norm_cdf(d2)

        return NumeraireExchangeResult(
            option_value=max(0.0, val),
            forward_ratio=f1 / f2,
            volatility_spread=vol_z,
            d1=d1,
            d2=d2,
            numeraire_asset="S2",
            target_asset="S1"
        )

    @staticmethod
    def forward_measure_discounting_factor(
        yield_rate: float,
        t: float
    ) -> float:
        """Zero-coupon bond numeraire P(0, T) = exp(-yield_rate * T)."""
        return math.exp(-yield_rate * t)


# ==============================================================================
# 6. MILIONIS ET AL. (2022) LOSS-VERSUS-REBALANCING (LVR) ENGINE
# ==============================================================================

@dataclass
class LVRAnalysisResult:
    impermanent_loss_pct: float
    cumulative_lvr_usd: float
    lvr_rate_annual_pct: float
    fee_income_usd: float
    net_lp_profit_usd: float
    fee_to_lvr_ratio: float
    breakeven_volume_required_daily: float
    is_lp_profitable: bool


class MilionisLVREngine:
    """
    Milionis, Moallemi, Roughgarden & Zhang (2022) Loss-Versus-Rebalancing Engine.
    Quantifies the path-dependent economic rent extracted by toxic arbitrageurs
    from automated market makers (AMMs) like Uniswap v2 and v3.
    
    dLVR_t = (1/8) * sigma^2 * S_t * L_t dt
    """

    @staticmethod
    def calculate_impermanent_loss(price_ratio: float) -> float:
        """
        Standard path-independent Impermanent Loss (IL) for 50/50 pool.
        k = S_T / S_0
        IL(k) = 2 * sqrt(k) / (1 + k) - 1
        """
        if price_ratio <= 0:
            return -1.0
        return (2.0 * math.sqrt(price_ratio) / (1.0 + price_ratio)) - 1.0

    @staticmethod
    def constant_product_lvr(
        spot: float,
        pool_liquidity_l: float,
        annual_volatility: float,
        time_horizon_years: float
    ) -> float:
        """
        Instantaneous / cumulative LVR for Constant Product AMM (x * y = L^2):
        LVR = (1/8) * sigma^2 * S_0 * L * T (under flat price expectation).
        For pool value V_0 = 2 * L * sqrt(S_0):
        Annual LVR rate = sigma^2 / 8 of pool value per year.
        """
        if spot <= 0 or pool_liquidity_l <= 0 or annual_volatility <= 0:
            raise ValueError("All inputs must be strictly positive.")

        pool_val = 2.0 * pool_liquidity_l * math.sqrt(spot)
        annual_lvr = 0.125 * (annual_volatility ** 2) * pool_val
        return annual_lvr * time_horizon_years

    @staticmethod
    def analyze_lp_profitability(
        initial_spot: float,
        terminal_spot: float,
        pool_tvl_usd: float,
        annual_volatility: float,
        fee_tier: float,  # e.g. 0.0030 for 0.3%
        daily_volume_usd: float,
        time_days: float = 30.0
    ) -> LVRAnalysisResult:
        """
        Full LP accounting comparing Fees, Impermanent Loss, and LVR.
        Fee revenue = fee_tier * daily_volume * days.
        LVR = (1/8) * sigma^2 * TVL * (days / 365).
        """
        time_years = time_days / 365.0
        price_ratio = terminal_spot / initial_spot
        il_pct = MilionisLVREngine.calculate_impermanent_loss(price_ratio)

        # LVR dollar amount
        annual_lvr_rate = 0.125 * (annual_volatility ** 2)
        cum_lvr = annual_lvr_rate * pool_tvl_usd * time_years

        # Fees collected
        total_volume = daily_volume_usd * time_days
        total_fees = total_volume * fee_tier

        # Net LP profit against rebalancing benchmark
        net_profit = total_fees - cum_lvr
        fee_to_lvr = total_fees / cum_lvr if cum_lvr > 0 else float("inf")

        # Daily volume required to break even against LVR
        breakeven_daily_vol = cum_lvr / (fee_tier * time_days) if fee_tier > 0 else float("inf")

        return LVRAnalysisResult(
            impermanent_loss_pct=il_pct,
            cumulative_lvr_usd=cum_lvr,
            lvr_rate_annual_pct=annual_lvr_rate * 100.0,
            fee_income_usd=total_fees,
            net_lp_profit_usd=net_profit,
            fee_to_lvr_ratio=fee_to_lvr,
            breakeven_volume_required_daily=breakeven_daily_vol,
            is_lp_profitable=(net_profit > 0)
        )

    @staticmethod
    def concentrated_liquidity_lvr_multiplier(
        p_lower: float,
        p_upper: float,
        current_price: float
    ) -> float:
        """
        Multiplier of LVR for concentrated liquidity (Uniswap v3)
        relative to full-range Uniswap v2.
        L_v3 / L_v2 = 1 / (1 - sqrt(p_lower / p_upper)).
        """
        if p_lower >= p_upper or p_lower <= 0:
            raise ValueError("p_lower must be positive and less than p_upper.")
        return 1.0 / (1.0 - math.sqrt(p_lower / p_upper))
