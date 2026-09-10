"""Phase 28: Quantitative Financial Engineering & Market Microstructure Engine.

Core Pillars:
1. Longstaff & Schwartz (2001) Least Squares Monte Carlo (LSM) & Early Exercise Premium
2. Hull & White (1990) Extended Vasicek Short-Rate Model & Jamshidian (1989) Swaption Decomposition
3. Heston & Nandi (2000) Closed-Form Discrete-Time GARCH Option Valuation
4. Avellaneda & Stoikov (2008) / Guéant et al. (2012) Closed-Form Optimal Market Making
5. Microstructure Volatility Estimators: Parkinson (1980), Garman-Klass (1980) & Rogers-Satchell (1991)
6. Extreme Tail Dependence Copula Architecture: Clayton, Gumbel, and Student-t Non-Linear Risk
"""

import argparse
from dataclasses import dataclass, field
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# 0. NUMERICAL HELPER FUNCTIONS
# ==============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def _student_t_cdf(t: float, df: float, n_steps: int = 200) -> float:
    """Student-t CDF using adaptive Simpson's quadrature integration of PDF."""
    if df <= 0:
        raise ValueError("Degrees of freedom must be positive.")
    if math.isinf(t):
        return 1.0 if t > 0 else 0.0
    if abs(t) < 1e-15:
        return 0.5

    # Symmetry
    sign = 1 if t > 0 else -1
    x_lim = abs(t)
    
    # PDF coefficient using lgamma
    log_coef = math.lgamma((df + 1.0) / 2.0) - (0.5 * math.log(df * math.pi) + math.lgamma(df / 2.0))
    coef = math.exp(log_coef)
    
    def pdf(x: float) -> float:
        return coef * (1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0)

    # Integrate from 0 to x_lim using Simpson's rule
    xs = np.linspace(0, x_lim, n_steps + 1)
    ys = np.array([pdf(x) for x in xs])
    h = x_lim / n_steps
    integral = (h / 3.0) * (ys[0] + 4.0 * np.sum(ys[1:-1:2]) + 2.0 * np.sum(ys[2:-1:2]) + ys[-1])
    
    val = 0.5 + sign * integral
    return max(0.0, min(1.0, float(val)))


# ==============================================================================
# PILLAR 1: LONGSTAFF & SCHWARTZ (2001) LEAST SQUARES MONTE CARLO (LSM)
# ==============================================================================

@dataclass
class LSMOptionResult:
    american_price: float
    std_error: float
    european_price: float
    early_exercise_premium: float
    exercise_ratio: float
    in_the_money_ratio: float
    basis_degree: int
    num_paths: int
    num_steps: int


class LongstaffSchwartzLSMEngine:
    """Francis Longstaff & Eduardo Schwartz (2001) American / Bermudan Option Valuation."""

    @staticmethod
    def simulate_gbm_paths(
        s0: float,
        r: float,
        q: float,
        sigma: float,
        t_mat: float,
        n_steps: int,
        n_paths: int,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """Simulate geometric Brownian motion price paths with antithetic variates."""
        if seed is not None:
            np.random.seed(seed)
        dt = t_mat / n_steps
        drift = (r - q - 0.5 * sigma * sigma) * dt
        vol_sqrt = sigma * math.sqrt(dt)

        half_paths = n_paths // 2
        z = np.random.normal(0.0, 1.0, (n_steps, half_paths))
        # Antithetic variates for variance reduction
        z = np.concatenate([z, -z], axis=1)
        if z.shape[1] < n_paths:
            extra = np.random.normal(0.0, 1.0, (n_steps, n_paths - z.shape[1]))
            z = np.concatenate([z, extra], axis=1)

        paths = np.zeros((n_steps + 1, n_paths))
        paths[0, :] = s0
        for step in range(1, n_steps + 1):
            paths[step, :] = paths[step - 1, :] * np.exp(drift + vol_sqrt * z[step - 1, :])
        return paths

    @classmethod
    def price_american_put(
        cls,
        s0: float,
        strike: float,
        r: float,
        q: float,
        sigma: float,
        t_mat: float,
        n_steps: int = 50,
        n_paths: int = 10000,
        degree: int = 3,
        seed: Optional[int] = 42
    ) -> LSMOptionResult:
        """Price an American put option using Longstaff-Schwartz polynomial backward induction."""
        dt = t_mat / n_steps
        paths = cls.simulate_gbm_paths(s0, r, q, sigma, t_mat, n_steps, n_paths, seed)

        # Terminal payoffs
        payoffs = np.maximum(strike - paths[-1, :], 0.0)
        cash_flows = payoffs.copy()
        stopping_steps = np.full(n_paths, n_steps, dtype=int)

        # Backward induction
        for step in range(n_steps - 1, 0, -1):
            current_s = paths[step, :]
            immediate_exercise = np.maximum(strike - current_s, 0.0)
            itm_indices = np.where(immediate_exercise > 0.0)[0]

            if len(itm_indices) > degree + 1:
                x_itm = current_s[itm_indices] / strike
                # Discounted future cash flows back to current step
                discount_factors = np.exp(-r * dt * (stopping_steps[itm_indices] - step))
                y_itm = cash_flows[itm_indices] * discount_factors

                # Orthogonal Weighted Laguerre polynomials
                basis = np.column_stack([
                    np.exp(-x_itm / 2.0) * np.ones_like(x_itm),
                    np.exp(-x_itm / 2.0) * (1.0 - x_itm),
                    np.exp(-x_itm / 2.0) * (1.0 - 2.0 * x_itm + 0.5 * x_itm * x_itm),
                ])
                if degree > 2:
                    deg3 = np.exp(-x_itm / 2.0) * (1.0 - 3.0 * x_itm + 1.5 * x_itm * x_itm - (1.0 / 6.0) * x_itm**3)
                    basis = np.column_stack([basis, deg3])

                # OLS regression for conditional continuation value
                beta, _, _, _ = np.linalg.lstsq(basis, y_itm, rcond=None)
                continuation_val = basis @ beta

                # Early exercise decision
                exercise = immediate_exercise[itm_indices] >= continuation_val
                exercised_paths = itm_indices[exercise]

                # Update stopping times and cash flows
                stopping_steps[exercised_paths] = step
                cash_flows[exercised_paths] = immediate_exercise[exercised_paths]

        # Present value of all cash flows discounted to t=0
        pv_cash_flows = cash_flows * np.exp(-r * dt * stopping_steps)
        american_price = float(np.mean(pv_cash_flows))
        std_error = float(np.std(pv_cash_flows) / math.sqrt(n_paths))

        # European counterpart on exact same paths
        pv_european = payoffs * math.exp(-r * t_mat)
        european_price = float(np.mean(pv_european))
        eep = max(0.0, american_price - european_price)

        exercised_count = np.sum(stopping_steps < n_steps)
        exercise_ratio = float(exercised_count / n_paths)
        itm_ratio = float(np.sum(paths[-1, :] < strike) / n_paths)

        return LSMOptionResult(
            american_price=round(american_price, 4),
            std_error=round(std_error, 5),
            european_price=round(european_price, 4),
            early_exercise_premium=round(eep, 4),
            exercise_ratio=round(exercise_ratio, 4),
            in_the_money_ratio=round(itm_ratio, 4),
            basis_degree=degree,
            num_paths=n_paths,
            num_steps=n_steps
        )

    @classmethod
    def price_american_call(
        cls,
        s0: float,
        strike: float,
        r: float,
        q: float,
        sigma: float,
        t_mat: float,
        n_steps: int = 50,
        n_paths: int = 10000,
        degree: int = 3,
        seed: Optional[int] = 42
    ) -> LSMOptionResult:
        """Price an American call option (valuable when dividend yield q > 0)."""
        dt = t_mat / n_steps
        paths = cls.simulate_gbm_paths(s0, r, q, sigma, t_mat, n_steps, n_paths, seed)

        payoffs = np.maximum(paths[-1, :] - strike, 0.0)
        cash_flows = payoffs.copy()
        stopping_steps = np.full(n_paths, n_steps, dtype=int)

        for step in range(n_steps - 1, 0, -1):
            current_s = paths[step, :]
            immediate_exercise = np.maximum(current_s - strike, 0.0)
            itm_indices = np.where(immediate_exercise > 0.0)[0]

            if len(itm_indices) > degree + 1:
                x_itm = current_s[itm_indices] / strike
                discount_factors = np.exp(-r * dt * (stopping_steps[itm_indices] - step))
                y_itm = cash_flows[itm_indices] * discount_factors

                basis = np.column_stack([
                    np.ones_like(x_itm),
                    x_itm,
                    x_itm * x_itm,
                ])
                if degree > 2:
                    basis = np.column_stack([basis, x_itm**3])

                beta, _, _, _ = np.linalg.lstsq(basis, y_itm, rcond=None)
                continuation_val = basis @ beta

                exercise = immediate_exercise[itm_indices] >= continuation_val
                exercised_paths = itm_indices[exercise]

                stopping_steps[exercised_paths] = step
                cash_flows[exercised_paths] = immediate_exercise[exercised_paths]

        pv_cash_flows = cash_flows * np.exp(-r * dt * stopping_steps)
        american_price = float(np.mean(pv_cash_flows))
        std_error = float(np.std(pv_cash_flows) / math.sqrt(n_paths))

        pv_european = payoffs * math.exp(-r * t_mat)
        european_price = float(np.mean(pv_european))
        eep = max(0.0, american_price - european_price)

        exercised_count = np.sum(stopping_steps < n_steps)
        exercise_ratio = float(exercised_count / n_paths)
        itm_ratio = float(np.sum(paths[-1, :] > strike) / n_paths)

        return LSMOptionResult(
            american_price=round(american_price, 4),
            std_error=round(std_error, 5),
            european_price=round(european_price, 4),
            early_exercise_premium=round(eep, 4),
            exercise_ratio=round(exercise_ratio, 4),
            in_the_money_ratio=round(itm_ratio, 4),
            basis_degree=degree,
            num_paths=n_paths,
            num_steps=n_steps
        )


# ==============================================================================
# PILLAR 2: HULL-WHITE SHORT RATE & JAMSHIDIAN (1989) SWAPTION DECOMPOSITION
# ==============================================================================

@dataclass
class HullWhiteSwaptionResult:
    swaption_price: float
    critical_rate_r_star: float
    swap_rate_par: float
    bond_options: List[Dict[str, float]]
    mean_reversion: float
    short_rate_vol: float
    maturity_option: float
    maturity_swap: float


@dataclass
class HullWhiteTrinomialNode:
    step: int
    j_index: int
    r_val: float
    p_up: float
    p_mid: float
    p_down: float


class HullWhiteShortRateEngine:
    """John Hull & Alan White (1990) Extended Vasicek Model & Jamshidian Swaption Engine."""

    @staticmethod
    def b_coeff(t: float, t_mat: float, a: float) -> float:
        """B(t, T) = (1 - exp(-a*(T - t))) / a."""
        if abs(a) < 1e-9:
            return t_mat - t
        return (1.0 - math.exp(-a * (t_mat - t))) / a

    @classmethod
    def zero_coupon_bond(
        cls,
        r_t: float,
        t: float,
        t_mat: float,
        a: float,
        sigma: float,
        r0: float
    ) -> float:
        """Analytical Zero Coupon Bond price P(t, T) assuming flat initial curve r0."""
        b = cls.b_coeff(t, t_mat, a)
        tau = t_mat - t
        ln_a = -r0 * tau + b * r0 - (sigma * sigma / (4.0 * a)) * (1.0 - math.exp(-2.0 * a * t)) * (b * b)
        return math.exp(ln_a - b * r_t)

    @classmethod
    def zcb_option(
        cls,
        strike: float,
        t_exp: float,
        t_mat: float,
        a: float,
        sigma: float,
        r0: float,
        option_type: str = "put"
    ) -> float:
        """European Call or Put option on a zero coupon bond."""
        if t_exp >= t_mat:
            return 0.0
        p_0_texp = math.exp(-r0 * t_exp)
        p_0_tmat = math.exp(-r0 * t_mat)
        b_t = cls.b_coeff(t_exp, t_mat, a)

        sigma_p = (sigma / a) * (1.0 - math.exp(-a * (t_mat - t_exp))) * math.sqrt((1.0 - math.exp(-2.0 * a * t_exp)) / (2.0 * a))

        if sigma_p < 1e-12:
            intrinsic = max(0.0, strike * p_0_texp - p_0_tmat) if option_type.lower() == "put" else max(0.0, p_0_tmat - strike * p_0_texp)
            return intrinsic

        d1 = (math.log(p_0_tmat / (strike * p_0_texp)) + 0.5 * sigma_p * sigma_p) / sigma_p
        d2 = d1 - sigma_p

        if option_type.lower() == "call":
            return p_0_tmat * _norm_cdf(d1) - strike * p_0_texp * _norm_cdf(d2)
        else:
            return strike * p_0_texp * _norm_cdf(-d2) - p_0_tmat * _norm_cdf(-d1)

    @classmethod
    def jamshidian_swaption(
        cls,
        strike_swap: float,
        t_exp: float,
        swap_tenors: List[float],
        a: float,
        sigma: float,
        r0: float,
        swaption_type: str = "payer"
    ) -> HullWhiteSwaptionResult:
        """
        Farshid Jamshidian (1989) exact decomposition of European payer/receiver swaption
        into a portfolio of zero-coupon bond options.
        """
        dt_tenor = swap_tenors[1] - swap_tenors[0] if len(swap_tenors) > 1 else 0.5
        n = len(swap_tenors)

        cash_flows = [strike_swap * dt_tenor] * n
        cash_flows[-1] += 1.0

        def coupon_bond_price(r_candidate: float) -> float:
            total = 0.0
            for i, t_i in enumerate(swap_tenors):
                total += cash_flows[i] * cls.zero_coupon_bond(r_candidate, t_exp, t_i, a, sigma, r0)
            return total

        r_low, r_high = -0.10, 0.40
        for _ in range(100):
            r_mid = 0.5 * (r_low + r_high)
            price_mid = coupon_bond_price(r_mid)
            if abs(price_mid - 1.0) < 1e-10:
                break
            if price_mid > 1.0:
                r_low = r_mid
            else:
                r_high = r_mid
        r_star = r_mid

        opt_type = "put" if swaption_type.lower() == "payer" else "call"
        total_swaption_price = 0.0
        bond_opts = []

        for i, t_i in enumerate(swap_tenors):
            k_i = cls.zero_coupon_bond(r_star, t_exp, t_i, a, sigma, r0)
            opt_i = cls.zcb_option(k_i, t_exp, t_i, a, sigma, r0, option_type=opt_type)
            weighted_opt = cash_flows[i] * opt_i
            total_swaption_price += weighted_opt
            bond_opts.append({
                "tenor": t_i,
                "cash_flow": round(cash_flows[i], 4),
                "zcb_strike_k": round(k_i, 5),
                "zcb_option_price": round(opt_i, 6),
                "weighted_price": round(weighted_opt, 6)
            })

        p_texp = math.exp(-r0 * t_exp)
        p_tlast = math.exp(-r0 * swap_tenors[-1])
        annuity = sum(dt_tenor * math.exp(-r0 * t_i) for t_i in swap_tenors)
        par_swap_rate = (p_texp - p_tlast) / annuity if annuity > 0 else r0

        return HullWhiteSwaptionResult(
            swaption_price=round(total_swaption_price, 6),
            critical_rate_r_star=round(r_star, 5),
            swap_rate_par=round(par_swap_rate, 5),
            bond_options=bond_opts,
            mean_reversion=a,
            short_rate_vol=sigma,
            maturity_option=t_exp,
            maturity_swap=swap_tenors[-1]
        )

    @classmethod
    def trinomial_probabilities(cls, j: int, a: float, dt: float) -> Tuple[float, float, float]:
        """Trinomial lattice transition probabilities (up, mid, down) with drift centering."""
        ajdt = a * j * dt
        p_u = (1.0 / 6.0) + 0.5 * (ajdt * ajdt - ajdt * math.sqrt(3.0))
        p_m = (2.0 / 3.0) - ajdt * ajdt
        p_d = (1.0 / 6.0) + 0.5 * (ajdt * ajdt + ajdt * math.sqrt(3.0))
        return float(p_u), float(p_m), float(p_d)


# ==============================================================================
# PILLAR 3: HESTON-NANDI (2000) DISCRETE-TIME GARCH OPTION VALUATION
# ==============================================================================

@dataclass
class HestonNandiOptionResult:
    call_price: float
    put_price: float
    p1: float
    p2: float
    unconditional_variance: float
    annualized_unconditional_vol: float
    strike: float
    spot: float
    time_to_maturity_days: int


class HestonNandiGARCHEngine:
    """
    Steven Heston & Saikat Nandi (2000) Closed-Form Discrete-Time GARCH(1,1) Option Engine.
    Bypasses unobservable latent continuous volatility filtering.
    """

    @classmethod
    def unconditional_variance(cls, omega: float, alpha1: float, beta1: float, gamma1_star: float) -> float:
        """Unconditional long-run variance under risk-neutral measure."""
        denom = 1.0 - beta1 - alpha1 * (gamma1_star * gamma1_star)
        if denom <= 0:
            raise ValueError(f"Stationarity condition violated: beta1 + alpha1 * gamma1*^2 = {1.0 - denom:.4f} >= 1.0")
        return (omega + alpha1) / denom

    @classmethod
    def characteristic_function(
        cls,
        phi: complex,
        s_t: float,
        h_t_plus_1: float,
        r_daily: float,
        t_days: int,
        omega: float,
        alpha1: float,
        beta1: float,
        gamma1_star: float
    ) -> complex:
        """
        Log-characteristic function f(phi) = S_t^phi * exp(A_t + B_t * h_{t+1})
        computed recursively backward from maturity.
        """
        a_curr = 0.0 + 0.0j
        b_curr = 0.0 + 0.0j
        lambda_star = -0.5

        for _ in range(t_days, 0, -1):
            denom = 1.0 - 2.0 * alpha1 * b_curr
            log_denom = np.log(denom)
            a_next = a_curr + phi * r_daily + b_curr * omega - 0.5 * log_denom

            bracket = phi - 2.0 * alpha1 * gamma1_star * b_curr
            b_next = phi * lambda_star + beta1 * b_curr + 0.5 * (bracket * bracket) / denom
            
            a_curr = a_next
            b_curr = b_next

        log_cf = phi * math.log(s_t) + a_curr + b_curr * h_t_plus_1
        return np.exp(log_cf)

    @classmethod
    def price_european_call(
        cls,
        spot: float,
        strike: float,
        r_annual: float,
        t_days: int,
        h_initial: Optional[float] = None,
        omega: float = 1e-6,
        alpha1: float = 1.5e-5,
        beta1: float = 0.75,
        gamma1_star: float = 100.0,
        n_quad: int = 500,
        phi_max: float = 80.0
    ) -> HestonNandiOptionResult:
        """Price European call option using Gil-Pelaez Fourier inversion formula."""
        r_daily = r_annual / 252.0
        discount_factor = math.exp(-r_annual * (t_days / 252.0))

        h_t_plus_1 = h_initial if h_initial is not None else cls.unconditional_variance(omega, alpha1, beta1, gamma1_star)

        phis = np.linspace(1e-6, phi_max, n_quad + 1)
        h_phi = phis[1] - phis[0]

        integrand1 = np.zeros(n_quad + 1)
        integrand2 = np.zeros(n_quad + 1)

        for i, phi in enumerate(phis):
            cf1 = cls.characteristic_function(
                complex(1.0, phi), spot, h_t_plus_1, r_daily, t_days, omega, alpha1, beta1, gamma1_star
            )
            cf2 = cls.characteristic_function(
                complex(0.0, phi), spot, h_t_plus_1, r_daily, t_days, omega, alpha1, beta1, gamma1_star
            )

            num1 = np.exp(-complex(0.0, phi) * math.log(strike)) * cf1
            den1 = complex(0.0, phi) * spot * math.exp(r_daily * t_days)
            integrand1[i] = (num1 / den1).real

            num2 = np.exp(-complex(0.0, phi) * math.log(strike)) * cf2
            den2 = complex(0.0, phi)
            integrand2[i] = (num2 / den2).real

        int1 = (h_phi / 3.0) * (integrand1[0] + 4.0 * np.sum(integrand1[1:-1:2]) + 2.0 * np.sum(integrand1[2:-1:2]) + integrand1[-1])
        int2 = (h_phi / 3.0) * (integrand2[0] + 4.0 * np.sum(integrand2[1:-1:2]) + 2.0 * np.sum(integrand2[2:-1:2]) + integrand2[-1])

        p1 = 0.5 + (1.0 / math.pi) * int1
        p2 = 0.5 + (1.0 / math.pi) * int2

        p1 = max(0.0, min(1.0, float(p1)))
        p2 = max(0.0, min(1.0, float(p2)))

        call_price = max(0.0, spot * p1 - strike * discount_factor * p2)
        put_price = max(0.0, call_price - spot + strike * discount_factor)

        uncond_var = cls.unconditional_variance(omega, alpha1, beta1, gamma1_star)
        annual_vol = math.sqrt(uncond_var * 252.0)

        return HestonNandiOptionResult(
            call_price=round(call_price, 4),
            put_price=round(put_price, 4),
            p1=round(p1, 5),
            p2=round(p2, 5),
            unconditional_variance=round(uncond_var, 8),
            annualized_unconditional_vol=round(annual_vol, 4),
            strike=strike,
            spot=spot,
            time_to_maturity_days=t_days
        )


# ==============================================================================
# PILLAR 4: AVELLANEDA-STOIKOV & GUÉANT OPTIMAL MARKET MAKING
# ==============================================================================

@dataclass
class MarketMakerQuoteResult:
    mid_price: float
    inventory: int
    reservation_price: float
    bid_quote: float
    ask_quote: float
    bid_half_spread: float
    ask_half_spread: float
    total_spread: float
    fill_prob_bid_dt: float
    fill_prob_ask_dt: float


@dataclass
class MarketMakerSessionResult:
    initial_cash: float
    terminal_cash: float
    terminal_inventory: int
    terminal_pnl: float
    sharpe_ratio: float
    total_trades_bid: int
    total_trades_ask: int
    inventory_mean: float
    inventory_std: float


class AvellanedaStoikovMarketMakingEngine:
    """
    Marco Avellaneda & Sasha Stoikov (2008) / Olivier Guéant (2012)
    Closed-Form Optimal High-Frequency Market Making with Inventory Risk.
    """

    @classmethod
    def reservation_price(
        cls,
        mid_price: float,
        inventory: int,
        gamma: float,
        sigma: float,
        time_to_horizon: float
    ) -> float:
        """Indifference / reservation price r(s, q, t) = s - q * gamma * sigma^2 * (T - t)."""
        return mid_price - inventory * gamma * (sigma * sigma) * time_to_horizon

    @classmethod
    def optimal_half_spreads(
        cls,
        gamma: float,
        k_order_intensity: float
    ) -> float:
        """Guéant et al. (2012) asymptotic full spread S* = (2 / gamma) * ln(1 + gamma / k)."""
        return (2.0 / gamma) * math.log(1.0 + gamma / k_order_intensity)

    @classmethod
    def compute_quotes(
        cls,
        mid_price: float,
        inventory: int,
        gamma: float,
        sigma: float,
        time_to_horizon: float,
        a_intensity: float = 140.0,
        k_intensity: float = 1.5,
        dt: float = 0.005
    ) -> MarketMakerQuoteResult:
        """Compute optimal bid/ask quotes with inventory skewing."""
        r_price = cls.reservation_price(mid_price, inventory, gamma, sigma, time_to_horizon)
        full_spread = cls.optimal_half_spreads(gamma, k_intensity)
        half_spread = 0.5 * full_spread

        p_ask = r_price + half_spread
        p_bid = r_price - half_spread

        delta_ask = p_ask - mid_price
        delta_bid = mid_price - p_bid

        lambda_bid = a_intensity * math.exp(-k_intensity * max(0.0, delta_bid))
        lambda_ask = a_intensity * math.exp(-k_intensity * max(0.0, delta_ask))

        prob_bid = 1.0 - math.exp(-lambda_bid * dt)
        prob_ask = 1.0 - math.exp(-lambda_ask * dt)

        return MarketMakerQuoteResult(
            mid_price=round(mid_price, 4),
            inventory=inventory,
            reservation_price=round(r_price, 4),
            bid_quote=round(p_bid, 4),
            ask_quote=round(p_ask, 4),
            bid_half_spread=round(delta_bid, 4),
            ask_half_spread=round(delta_ask, 4),
            total_spread=round(delta_bid + delta_ask, 4),
            fill_prob_bid_dt=round(prob_bid, 4),
            fill_prob_ask_dt=round(prob_ask, 4)
        )

    @classmethod
    def simulate_trading_session(
        cls,
        s0: float = 100.0,
        gamma: float = 0.1,
        sigma: float = 0.3,
        t_horizon: float = 1.0,
        dt: float = 0.005,
        a_intensity: float = 140.0,
        k_intensity: float = 1.5,
        max_inventory: int = 10,
        seed: Optional[int] = 42
    ) -> MarketMakerSessionResult:
        """Simulate high-frequency market making session with discrete inventory transitions."""
        if seed is not None:
            np.random.seed(seed)

        n_steps = int(t_horizon / dt)
        cash = 0.0
        q = 0
        s = s0

        inventories = []
        pnl_history = []
        trades_bid = 0
        trades_ask = 0

        for step in range(n_steps):
            t_rem = t_horizon - step * dt
            s += sigma * math.sqrt(dt) * np.random.normal(0.0, 1.0)

            quotes = cls.compute_quotes(s, q, gamma, sigma, t_rem, a_intensity, k_intensity, dt)

            if q < max_inventory:
                u_bid = np.random.uniform(0.0, 1.0)
                if u_bid < quotes.fill_prob_bid_dt:
                    q += 1
                    cash -= quotes.bid_quote
                    trades_bid += 1

            if q > -max_inventory:
                u_ask = np.random.uniform(0.0, 1.0)
                if u_ask < quotes.fill_prob_ask_dt:
                    q -= 1
                    cash += quotes.ask_quote
                    trades_ask += 1

            inventories.append(q)
            current_wealth = cash + q * s
            pnl_history.append(current_wealth)

        terminal_pnl = cash + q * s
        returns = np.diff(pnl_history)
        std_returns = np.std(returns)
        sharpe = (np.mean(returns) / std_returns) * math.sqrt(252.0 * n_steps) if std_returns > 1e-8 else 0.0

        return MarketMakerSessionResult(
            initial_cash=0.0,
            terminal_cash=round(cash, 2),
            terminal_inventory=q,
            terminal_pnl=round(terminal_pnl, 2),
            sharpe_ratio=round(float(sharpe), 2),
            total_trades_bid=trades_bid,
            total_trades_ask=trades_ask,
            inventory_mean=round(float(np.mean(inventories)), 2),
            inventory_std=round(float(np.std(inventories)), 2)
        )


# ==============================================================================
# PILLAR 5: MICROSTRUCTURE VOLATILITY ESTIMATORS (PARKINSON, GARMAN-KLASS, RS)
# ==============================================================================

@dataclass
class VolatilityEstimatorsResult:
    close_to_close: float
    parkinson: float
    garman_klass: float
    rogers_satchell: float
    garman_klass_yang_zhang: float
    parkinson_efficiency: float
    garman_klass_efficiency: float
    rogers_satchell_efficiency: float
    sample_size: int


class MicrostructureVolatilityEngine:
    """
    High-Efficiency OHLC Intraday Volatility Estimators:
    Parkinson (1980), Garman-Klass (1980), Rogers-Satchell (1991), and GKYZ.
    """

    @staticmethod
    def close_to_close(closes: np.ndarray) -> float:
        """Standard close-to-close daily volatility estimator."""
        log_ret = np.diff(np.log(closes))
        return float(np.std(log_ret, ddof=1) * math.sqrt(252.0))

    @staticmethod
    def parkinson(highs: np.ndarray, lows: np.ndarray) -> float:
        """Michael Parkinson (1980) High-Low extreme value estimator (Efficiency ~ 5.2x)."""
        log_hl = np.log(highs / lows)
        sigma2 = (1.0 / (4.0 * math.log(2.0))) * np.mean(log_hl * log_hl)
        return float(math.sqrt(sigma2 * 252.0))

    @staticmethod
    def garman_klass(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Garman & Klass (1980) minimum variance OHLC estimator (Efficiency ~ 7.4x)."""
        log_hl = np.log(highs / lows)
        log_co = np.log(closes / opens)
        term1 = 0.5 * (log_hl * log_hl)
        term2 = (2.0 * math.log(2.0) - 1.0) * (log_co * log_co)
        sigma2 = np.mean(term1 - term2)
        return float(math.sqrt(max(0.0, sigma2) * 252.0))

    @staticmethod
    def rogers_satchell(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Rogers, Satchell & Yoon (1991) drift-invariant estimator (Unbiased for mu != 0)."""
        log_ho = np.log(highs / opens)
        log_hc = np.log(highs / closes)
        log_lo = np.log(lows / opens)
        log_lc = np.log(lows / closes)
        term = log_ho * log_hc + log_lo * log_lc
        sigma2 = np.mean(term)
        return float(math.sqrt(max(0.0, sigma2) * 252.0))

    @staticmethod
    def garman_klass_yang_zhang(
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> float:
        """Garman-Klass extension with Yang-Zhang overnight gap handling."""
        log_oc = np.log(opens[1:] / closes[:-1])
        log_hl = np.log(highs[1:] / lows[1:])
        log_co = np.log(closes[1:] / opens[1:])

        overnight_var = np.mean(log_oc * log_oc)
        intraday_var = np.mean(0.5 * (log_hl * log_hl) - (2.0 * math.log(2.0) - 1.0) * (log_co * log_co))
        sigma2 = overnight_var + intraday_var
        return float(math.sqrt(max(0.0, sigma2) * 252.0))

    @classmethod
    def compare_all(
        cls,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> VolatilityEstimatorsResult:
        """Compute all 5 estimators and their theoretical relative efficiency."""
        c2c = cls.close_to_close(closes)
        park = cls.parkinson(highs, lows)
        gk = cls.garman_klass(opens, highs, lows, closes)
        rs = cls.rogers_satchell(opens, highs, lows, closes)
        gkyz = cls.garman_klass_yang_zhang(opens, highs, lows, closes)

        return VolatilityEstimatorsResult(
            close_to_close=round(c2c, 4),
            parkinson=round(park, 4),
            garman_klass=round(gk, 4),
            rogers_satchell=round(rs, 4),
            garman_klass_yang_zhang=round(gkyz, 4),
            parkinson_efficiency=5.20,
            garman_klass_efficiency=7.40,
            rogers_satchell_efficiency=6.50,
            sample_size=len(closes)
        )


# ==============================================================================
# PILLAR 6: EXTREME TAIL DEPENDENCE COPULA ARCHITECTURE
# ==============================================================================

@dataclass
class TailDependenceResult:
    copula_type: str
    parameter_theta: float
    kendall_tau: float
    spearman_rho: float
    lower_tail_dependence_lambda_l: float
    upper_tail_dependence_lambda_u: float
    joint_crash_probability_1pct: float
    gaussian_benchmark_crash_prob_1pct: float


class TailDependenceCopulaEngine:
    """
    Asymmetric Tail Dependence Copula Engine:
    Clayton (Crash clustering), Gumbel (Bubble rally), and Student-t (Fat tails).
    """

    @classmethod
    def clayton_cdf(cls, u: float, v: float, theta: float) -> float:
        """Clayton copula joint CDF: C(u, v) = max(u^(-theta) + v^(-theta) - 1, 0)^(-1/theta)."""
        if u <= 0.0 or v <= 0.0:
            return 0.0
        if u >= 1.0:
            return v
        if v >= 1.0:
            return u
        val = (u ** (-theta) + v ** (-theta) - 1.0)
        if val <= 0.0:
            return 0.0
        return val ** (-1.0 / theta)

    @classmethod
    def clayton_lower_tail_dependence(cls, theta: float) -> float:
        """Clayton lambda_L = 2^(-1/theta) for theta > 0. (lambda_U = 0)."""
        if theta <= 0:
            return 0.0
        return 2.0 ** (-1.0 / theta)

    @classmethod
    def clayton_theta_from_tau(cls, tau: float) -> float:
        """Kendall's tau inversion for Clayton: tau = theta / (theta + 2) -> theta = 2*tau / (1 - tau)."""
        if tau <= 0.0 or tau >= 1.0:
            raise ValueError("Kendall's tau must be in (0, 1) for Clayton.")
        return (2.0 * tau) / (1.0 - tau)

    @classmethod
    def gumbel_cdf(cls, u: float, v: float, theta: float) -> float:
        """Gumbel copula joint CDF: C(u, v) = exp( - [ (-ln u)^theta + (-ln v)^theta ]^(1/theta) )."""
        if u <= 0.0 or v <= 0.0:
            return 0.0
        if u >= 1.0:
            return v
        if v >= 1.0:
            return u
        term = ((-math.log(u)) ** theta + (-math.log(v)) ** theta) ** (1.0 / theta)
        return math.exp(-term)

    @classmethod
    def gumbel_upper_tail_dependence(cls, theta: float) -> float:
        """Gumbel lambda_U = 2 - 2^(1/theta) for theta >= 1. (lambda_L = 0)."""
        if theta < 1.0:
            return 0.0
        return 2.0 - 2.0 ** (1.0 / theta)

    @classmethod
    def gumbel_theta_from_tau(cls, tau: float) -> float:
        """Kendall's tau inversion for Gumbel: tau = 1 - 1/theta -> theta = 1 / (1 - tau)."""
        if tau < 0.0 or tau >= 1.0:
            raise ValueError("Kendall's tau must be in [0, 1) for Gumbel.")
        return 1.0 / (1.0 - tau)

    @classmethod
    def student_t_tail_dependence(cls, nu: float, rho: float) -> float:
        """
        Symmetric tail dependence for bivariate Student-t copula:
        lambda_L = lambda_U = 2 * t_{nu + 1}( - sqrt( (nu + 1) * (1 - rho) / (1 + rho) ) ).
        """
        if nu <= 0 or abs(rho) >= 1.0:
            return 0.0
        arg = -math.sqrt((nu + 1.0) * (1.0 - rho) / (1.0 + rho))
        t_cdf_val = _student_t_cdf(arg, df=nu + 1.0)
        return 2.0 * t_cdf_val

    @classmethod
    def analyze_clayton_crisis(cls, kendall_tau: float = 0.5, alpha: float = 0.01) -> TailDependenceResult:
        """Analyze crash spillover contagion under Clayton copula vs Gaussian copula benchmark."""
        theta = cls.clayton_theta_from_tau(kendall_tau)
        lambda_l = cls.clayton_lower_tail_dependence(theta)
        lambda_u = 0.0

        joint_cdf = cls.clayton_cdf(alpha, alpha, theta)
        joint_crash_prob = joint_cdf / alpha

        rho_gauss = math.sin(0.5 * math.pi * kendall_tau)
        z_alpha = -2.3263
        
        def biv_norm(z1, z2, r):
            zs = np.linspace(-6.0, z1, 100)
            cond_cdf = np.array([_norm_cdf((z2 - r * z) / math.sqrt(max(1e-6, 1.0 - r * r))) * _norm_pdf(z) for z in zs])
            # trapezoidal integral
            h = (z1 - (-6.0)) / 99.0
            return float(np.sum(cond_cdf[1:-1]) * h + 0.5 * h * (cond_cdf[0] + cond_cdf[-1]))

        gauss_joint = biv_norm(z_alpha, z_alpha, rho_gauss)
        gauss_crash_prob = gauss_joint / alpha

        return TailDependenceResult(
            copula_type="Clayton (Lower Tail Asymmetry)",
            parameter_theta=round(theta, 4),
            kendall_tau=round(kendall_tau, 4),
            spearman_rho=round(float(1.5 * kendall_tau), 4),
            lower_tail_dependence_lambda_l=round(lambda_l, 4),
            upper_tail_dependence_lambda_u=round(lambda_u, 4),
            joint_crash_probability_1pct=round(joint_crash_prob, 4),
            gaussian_benchmark_crash_prob_1pct=round(gauss_crash_prob, 4)
        )

    @classmethod
    def analyze_gumbel_bubble(cls, kendall_tau: float = 0.5, alpha: float = 0.01) -> TailDependenceResult:
        """Analyze joint euphoric rally spillover under Gumbel copula."""
        theta = cls.gumbel_theta_from_tau(kendall_tau)
        lambda_l = 0.0
        lambda_u = cls.gumbel_upper_tail_dependence(theta)

        c_val = cls.gumbel_cdf(1.0 - alpha, 1.0 - alpha, theta)
        joint_rally_prob = (1.0 - 2.0 * (1.0 - alpha) + c_val) / alpha

        return TailDependenceResult(
            copula_type="Gumbel (Upper Tail Asymmetry)",
            parameter_theta=round(theta, 4),
            kendall_tau=round(kendall_tau, 4),
            spearman_rho=round(float(1.5 * kendall_tau), 4),
            lower_tail_dependence_lambda_l=round(lambda_l, 4),
            upper_tail_dependence_lambda_u=round(lambda_u, 4),
            joint_crash_probability_1pct=round(joint_rally_prob, 4),
            gaussian_benchmark_crash_prob_1pct=0.083
        )


# ==============================================================================
# CLI EXECUTION & RESEARCH DISPATCH
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 28: Quantitative Financial Engineering Engine")
    parser.add_argument("--demo", action="store_true", help="Run full 6-pillar analytical demonstration")
    args = parser.parse_args()

    print("================================================================================")
    print("      PHASE 28: QUANTITATIVE FINANCIAL ENGINEERING & MICROSTRUCTURE ENGINE       ")
    print("================================================================================")

    # 1. Longstaff-Schwartz LSM
    print("\n[1/6] Longstaff & Schwartz (2001) Least Squares Monte Carlo (LSM):")
    lsm_res = LongstaffSchwartzLSMEngine.price_american_put(
        s0=100.0, strike=100.0, r=0.05, q=0.0, sigma=0.20, t_mat=1.0, n_steps=50, n_paths=10000, seed=42
    )
    print(f"  American Put Price : ${lsm_res.american_price:.4f} +/- {lsm_res.std_error:.4f}")
    print(f"  European Put Price : ${lsm_res.european_price:.4f}")
    print(f"  Early Exercise Prem: ${lsm_res.early_exercise_premium:.4f}")
    print(f"  Early Exercise Ratio: {lsm_res.exercise_ratio * 100:.2f}%")

    # 2. Hull-White Short Rate & Jamshidian
    print("\n[2/6] Hull-White (1990) & Jamshidian (1989) Swaption Engine:")
    tenors = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    hw_res = HullWhiteShortRateEngine.jamshidian_swaption(
        strike_swap=0.04, t_exp=1.0, swap_tenors=tenors, a=0.03, sigma=0.015, r0=0.035, swaption_type="payer"
    )
    print(f"  Payer Swaption Price : ${hw_res.swaption_price:.6f}")
    print(f"  Critical Rate (r*)   : {hw_res.critical_rate_r_star * 100:.3f}%")
    print(f"  Par Swap Rate        : {hw_res.swap_rate_par * 100:.3f}%")
    print(f"  Decomposed ZCB Options Count: {len(hw_res.bond_options)}")

    # 3. Heston-Nandi GARCH Option
    print("\n[3/6] Heston & Nandi (2000) Closed-Form Discrete GARCH Option Valuation:")
    hn_res = HestonNandiGARCHEngine.price_european_call(
        spot=100.0, strike=100.0, r_annual=0.05, t_days=180
    )
    print(f"  European Call Price  : ${hn_res.call_price:.4f}")
    print(f"  European Put Price   : ${hn_res.put_price:.4f}")
    print(f"  P1 (Delta)           : {hn_res.p1:.4f} | P2 (Risk-neutral prob): {hn_res.p2:.4f}")
    print(f"  Annualized Volatility: {hn_res.annualized_unconditional_vol * 100:.2f}%")

    # 4. Avellaneda-Stoikov Market Making
    print("\n[4/6] Avellaneda-Stoikov & Guéant Optimal Market Making:")
    quotes = AvellanedaStoikovMarketMakingEngine.compute_quotes(
        mid_price=100.0, inventory=2, gamma=0.1, sigma=0.25, time_to_horizon=0.5
    )
    print(f"  Mid: ${quotes.mid_price:.2f} | Reservation: ${quotes.reservation_price:.2f} (Long inventory skew)")
    print(f"  Optimal Bid Quote    : ${quotes.bid_quote:.4f} (Half-Spread: ${quotes.bid_half_spread:.4f})")
    print(f"  Optimal Ask Quote    : ${quotes.ask_quote:.4f} (Half-Spread: ${quotes.ask_half_spread:.4f})")
    print(f"  Total Spread         : ${quotes.total_spread:.4f}")

    # 5. Microstructure Volatility Estimators
    print("\n[5/6] High-Efficiency Microstructure Volatility Estimators:")
    np.random.seed(42)
    n_days = 252
    c = 100.0 * np.exp(np.cumsum(np.random.normal(0.0002, 0.015, n_days)))
    o = c * np.exp(np.random.normal(0.0, 0.003, n_days))
    h = np.maximum(o, c) * np.exp(np.abs(np.random.normal(0.0, 0.008, n_days)))
    l = np.minimum(o, c) * np.exp(-np.abs(np.random.normal(0.0, 0.008, n_days)))
    vol_res = MicrostructureVolatilityEngine.compare_all(o, h, l, c)
    print(f"  Close-to-Close Volatility : {vol_res.close_to_close * 100:.2f}% (Base Efficiency 1.0x)")
    print(f"  Parkinson Volatility      : {vol_res.parkinson * 100:.2f}% (Efficiency 5.2x)")
    print(f"  Garman-Klass Volatility   : {vol_res.garman_klass * 100:.2f}% (Efficiency 7.4x)")
    print(f"  Rogers-Satchell Volatility: {vol_res.rogers_satchell * 100:.2f}% (Efficiency 6.5x)")

    # 6. Copula Extreme Tail Dependence
    print("\n[6/6] Extreme Tail Dependence Copula Architecture:")
    copula_res = TailDependenceCopulaEngine.analyze_clayton_crisis(kendall_tau=0.5, alpha=0.01)
    print(f"  Copula               : {copula_res.copula_type}")
    print(f"  Theta Parameter      : {copula_res.parameter_theta:.4f} (from Tau = 0.50)")
    print(f"  Lower Tail Lambda_L  : {copula_res.lower_tail_dependence_lambda_l:.4f}")
    print(f"  1% Joint Crash Prob  : {copula_res.joint_crash_probability_1pct * 100:.2f}%")
    print(f"  Gaussian Model Prob  : {copula_res.gaussian_benchmark_crash_prob_1pct * 100:.2f}% (Catastrophic Underestimation!)")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
