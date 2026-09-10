"""Phase 29: Quantitative Financial Engineering & Continuous-Time Modeling Architecture.

Core Pillars:
1. Hagan et al. (2002) SABR Stochastic Volatility Closed-Form Asymptotic Model & Smile Calibration
2. Demeterfi-Derman-Kamal-Zou (1999) Variance Swap Replication, Fair Strike & Convexity Adjustment
3. Garman & Kohlhagen (1983) Analytic FX Currency Option Pricing & Complete Cross-Currency Greeks
4. Merton (1976) Jump-Diffusion Option Pricing Model & Poisson Series Expansion
5. Continuous Kelly Criterion, Grossman-Zhou Drawdown Distribution & Ruin Probability
6. Marcos López de Prado (2019) Hierarchical Equal Risk Contribution (HERC) Asset Allocation
"""

import argparse
from dataclasses import dataclass, field
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# 0. NUMERICAL & DISTRIBUTION HELPER FUNCTIONS
# ==============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def _black_scholes_call(s: float, k: float, t: float, sigma: float, r: float, q: float = 0.0) -> float:
    """Standard Black-Scholes-Merton European Call pricer."""
    if t <= 0.0:
        return max(0.0, s - k)
    if sigma <= 1e-9:
        return max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t))
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return s * math.exp(-q * t) * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)

def _black_scholes_put(s: float, k: float, t: float, sigma: float, r: float, q: float = 0.0) -> float:
    """Standard Black-Scholes-Merton European Put pricer."""
    if t <= 0.0:
        return max(0.0, k - s)
    if sigma <= 1e-9:
        return max(0.0, k * math.exp(-r * t) - s * math.exp(-q * t))
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return k * math.exp(-r * t) * _norm_cdf(-d2) - s * math.exp(-q * t) * _norm_cdf(-d1)


# ==============================================================================
# 1. HAGAN ET AL. (2002) SABR STOCHASTIC VOLATILITY ENGINE
# ==============================================================================

@dataclass
class SABRParameters:
    alpha: float    # Initial stochastic volatility (alpha > 0)
    beta: float     # CEV elasticity exponent (0 <= beta <= 1)
    rho: float      # Correlation (-1 < rho < 1)
    nu: float       # Volatility of volatility (nu >= 0)

@dataclass
class SABRSmilePoint:
    strike: float
    forward: float
    maturity: float
    implied_black_vol: float
    call_price: float
    put_price: float

@dataclass
class SABRCalibrationResult:
    alpha: float
    beta: float
    rho: float
    nu: float
    rmse: float
    fitted_strikes: List[float]
    fitted_vols: List[float]
    market_vols: List[float]

class SABRStochasticVolatilityEngine:
    """Hagan et al. (2002) SABR model for interest rate swaptions, caplets, and FX smiles."""

    @staticmethod
    def implied_volatility(
        f: float,
        k: float,
        t: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float
    ) -> float:
        """Hagan (2002) asymptotic implied Black-76 volatility formula."""
        if f <= 0.0 or k <= 0.0 or t <= 0.0 or alpha <= 0.0:
            return max(0.001, alpha)

        one_minus_beta = 1.0 - beta
        fk_prod = f * k

        # ATM Case (or very close)
        if abs(f - k) / f < 1e-5:
            f_omb = f ** one_minus_beta
            term1 = alpha / f_omb
            bracket = 1.0 + (
                ((one_minus_beta ** 2) * (alpha ** 2)) / (24.0 * (f ** (2.0 * one_minus_beta)))
                + (rho * beta * nu * alpha) / (4.0 * f_omb)
                + ((2.0 - 3.0 * rho * rho) * (nu ** 2)) / 24.0
            ) * t
            return max(0.0001, term1 * bracket)

        # OTM / ITM Case
        log_fk = math.log(f / k)
        fk_pow = fk_prod ** (one_minus_beta / 2.0)
        z = (nu / alpha) * fk_pow * log_fk

        # Small z expansion
        if abs(z) < 1e-6:
            chi_ratio = 1.0 + 0.5 * rho * z + ((3.0 * rho * rho - 1.0) / 12.0) * (z * z)
        else:
            sqrt_term = math.sqrt(max(0.0, 1.0 - 2.0 * rho * z + z * z))
            denom_arg = (sqrt_term + z - rho) / (1.0 - rho)
            if denom_arg <= 0.0:
                chi_ratio = 1.0
            else:
                chi_z = math.log(denom_arg)
                chi_ratio = z / chi_z

        denom_series = fk_pow * (
            1.0
            + ((one_minus_beta ** 2) / 24.0) * (log_fk ** 2)
            + ((one_minus_beta ** 4) / 1920.0) * (log_fk ** 4)
        )

        higher_order = 1.0 + (
            ((one_minus_beta ** 2) * (alpha ** 2)) / (24.0 * (fk_prod ** one_minus_beta))
            + (rho * beta * nu * alpha) / (4.0 * fk_pow)
            + ((2.0 - 3.0 * rho * rho) * (nu ** 2)) / 24.0
        ) * t

        sigma_bs = (alpha / denom_series) * chi_ratio * higher_order
        return max(0.0001, sigma_bs)

    @classmethod
    def price_black76(
        cls,
        f: float,
        k: float,
        t: float,
        r: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float,
        is_call: bool = True
    ) -> float:
        """Prices European option on forward using SABR implied volatility in Black-76 formula."""
        sigma = cls.implied_volatility(f, k, t, alpha, beta, rho, nu)
        discount = math.exp(-r * t)
        if t <= 0.0:
            intrinsic = max(0.0, f - k) if is_call else max(0.0, k - f)
            return discount * intrinsic

        d1 = (math.log(f / k) + 0.5 * sigma * sigma * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        if is_call:
            return discount * (f * _norm_cdf(d1) - k * _norm_cdf(d2))
        else:
            return discount * (k * _norm_cdf(-d2) - f * _norm_cdf(-d1))

    @classmethod
    def generate_smile(
        cls,
        f: float,
        strikes: List[float],
        t: float,
        r: float,
        alpha: float,
        beta: float,
        rho: float,
        nu: float
    ) -> List[SABRSmilePoint]:
        """Generates full implied volatility smile across strikes."""
        points = []
        for k in strikes:
            vol = cls.implied_volatility(f, k, t, alpha, beta, rho, nu)
            call_p = cls.price_black76(f, k, t, r, alpha, beta, rho, nu, is_call=True)
            put_p = cls.price_black76(f, k, t, r, alpha, beta, rho, nu, is_call=False)
            points.append(SABRSmilePoint(
                strike=k,
                forward=f,
                maturity=t,
                implied_black_vol=vol,
                call_price=call_p,
                put_price=put_p
            ))
        return points

    @classmethod
    def calibrate_sabr(
        cls,
        f: float,
        t: float,
        strikes: List[float],
        market_vols: List[float],
        fixed_beta: float = 0.5,
        max_iter: int = 1000
    ) -> SABRCalibrationResult:
        """Calibrates alpha, rho, nu to market implied volatilities via coordinate descent."""
        atm_vol = market_vols[len(market_vols) // 2]
        alpha = atm_vol * (f ** (1.0 - fixed_beta))
        rho = 0.0
        nu = 0.3

        def loss(a, r_corr, n_vol):
            total_err = 0.0
            for k_val, m_vol in zip(strikes, market_vols):
                pred = cls.implied_volatility(f, k_val, t, a, fixed_beta, r_corr, n_vol)
                total_err += (pred - m_vol) ** 2
            return math.sqrt(total_err / len(strikes))

        best_loss = loss(alpha, rho, nu)
        step_a = alpha * 0.05
        step_r = 0.05
        step_n = 0.05

        for _ in range(max_iter):
            improved = False
            for da in [-step_a, step_a]:
                na = max(0.0001, alpha + da)
                l = loss(na, rho, nu)
                if l < best_loss:
                    best_loss = l
                    alpha = na
                    improved = True

            for dr in [-step_r, step_r]:
                nr = max(-0.99, min(0.99, rho + dr))
                l = loss(alpha, nr, nu)
                if l < best_loss:
                    best_loss = l
                    rho = nr
                    improved = True

            for dn in [-step_n, step_n]:
                nn = max(0.001, nu + dn)
                l = loss(alpha, rho, nn)
                if l < best_loss:
                    best_loss = l
                    nu = nn
                    improved = True

            if not improved:
                step_a *= 0.7
                step_r *= 0.7
                step_n *= 0.7
                if step_a < 1e-5 and step_r < 1e-5 and step_n < 1e-5:
                    break

        fitted = [cls.implied_volatility(f, k_val, t, alpha, fixed_beta, rho, nu) for k_val in strikes]
        return SABRCalibrationResult(
            alpha=alpha,
            beta=fixed_beta,
            rho=rho,
            nu=nu,
            rmse=best_loss,
            fitted_strikes=strikes,
            fitted_vols=fitted,
            market_vols=market_vols
        )


# ==============================================================================
# 2. DEMETERFI ET AL. (1999) VARIANCE SWAP REPLICATION ENGINE
# ==============================================================================

@dataclass
class VarianceSwapReplicationResult:
    s0: float
    forward: float
    maturity: float
    fair_variance_strike_pct2: float   # K_var in (% variance)^2
    fair_volatility_strike_pct: float  # sqrt(K_var) in %
    convexity_adjustment_pct: float    # Jensen's inequality difference
    expected_realized_vol_pct: float   # E[sigma_R]
    replicated_put_count: int
    replicated_call_count: int
    strikes: List[float]
    weights: List[float]

@dataclass
class VarianceSwapSettlementResult:
    realized_variance_pct2: float
    realized_volatility_pct: float
    variance_strike_pct2: float
    variance_notional: float
    vega_notional: float
    payoff_pnl: float
    volatility_risk_premium_pct: float

class VarianceSwapReplicationEngine:
    """Replication of variance swaps via continuum of OTM options & mark-to-market."""

    @staticmethod
    def calculate_realized_variance(prices: List[float], annualization_factor: float = 252.0) -> Tuple[float, float]:
        """Calculates realized variance and annualized volatility from a sequence of daily prices."""
        if len(prices) < 2:
            return 0.0, 0.0
        p = np.array(prices, dtype=float)
        log_rets = np.log(p[1:] / p[:-1])
        n = len(log_rets)
        rv = (annualization_factor / n) * np.sum(log_rets ** 2)
        vol = math.sqrt(max(0.0, rv))
        return float(rv * 10000.0), float(vol * 100.0)

    @classmethod
    def replicate_fair_strike(
        cls,
        s0: float,
        r: float,
        t: float,
        strikes: List[float],
        market_put_prices: List[float],
        market_call_prices: List[float],
        variance_of_realized_vol: float = 0.002
    ) -> VarianceSwapReplicationResult:
        """Demeterfi-Derman-Kamal-Zou (1999) discrete log-contract replication."""
        forward = s0 * math.exp(r * t)
        strikes = sorted(strikes)
        m = len(strikes)

        s_star = strikes[0]
        for k in strikes:
            if k <= forward:
                s_star = k
            else:
                break

        offset = (2.0 / t) * (r * t - (forward / s_star - 1.0) - math.log(s_star / s0))

        integral_sum = 0.0
        put_count = 0
        call_count = 0
        weights = []

        for i, k in enumerate(strikes):
            if i == 0:
                dk = (strikes[1] - strikes[0]) / 2.0
            elif i == m - 1:
                dk = (strikes[-1] - strikes[-2]) / 2.0
            else:
                dk = (strikes[i + 1] - strikes[i - 1]) / 2.0

            w_k = dk / (k * k)
            weights.append(w_k)

            if k < s_star:
                p_k = market_put_prices[i]
                integral_sum += w_k * p_k
                put_count += 1
            elif k > s_star:
                c_k = market_call_prices[i]
                integral_sum += w_k * c_k
                call_count += 1
            else:
                mid_opt = 0.5 * (market_put_prices[i] + market_call_prices[i])
                integral_sum += w_k * mid_opt

        fair_var = offset + (2.0 * math.exp(r * t) / t) * integral_sum
        fair_var = max(0.0001, fair_var)
        fair_vol = math.sqrt(fair_var)

        convexity_adj = variance_of_realized_vol / (8.0 * (fair_var ** 1.5))
        expected_vol = max(0.0, fair_vol - convexity_adj)

        return VarianceSwapReplicationResult(
            s0=s0,
            forward=forward,
            maturity=t,
            fair_variance_strike_pct2=fair_var * 10000.0,
            fair_volatility_strike_pct=fair_vol * 100.0,
            convexity_adjustment_pct=convexity_adj * 100.0,
            expected_realized_vol_pct=expected_vol * 100.0,
            replicated_put_count=put_count,
            replicated_call_count=call_count,
            strikes=strikes,
            weights=weights
        )

    @classmethod
    def settle_variance_swap(
        cls,
        prices: List[float],
        fair_variance_strike_pct2: float,
        vega_notional: float,
        annualization_factor: float = 252.0
    ) -> VarianceSwapSettlementResult:
        """Computes expiration settlement PnL and Volatility Risk Premium."""
        rv_pct2, rv_vol_pct = cls.calculate_realized_variance(prices, annualization_factor)
        k_vol_pct = math.sqrt(fair_variance_strike_pct2)

        var_notional = vega_notional / (2.0 * k_vol_pct)
        pnl = var_notional * (rv_pct2 - fair_variance_strike_pct2)
        vrp = k_vol_pct - rv_vol_pct

        return VarianceSwapSettlementResult(
            realized_variance_pct2=rv_pct2,
            realized_volatility_pct=rv_vol_pct,
            variance_strike_pct2=fair_variance_strike_pct2,
            variance_notional=var_notional,
            vega_notional=vega_notional,
            payoff_pnl=pnl,
            volatility_risk_premium_pct=vrp
        )


# ==============================================================================
# 3. GARMAN & KOHLHAGEN (1983) ANALYTIC FX OPTION ENGINE
# ==============================================================================

@dataclass
class FXOptionGreeks:
    spot: float
    strike: float
    maturity: float
    call_price: float
    put_price: float
    spot_delta_call: float
    spot_delta_put: float
    forward_delta_call: float
    dual_delta_call: float
    gamma: float
    vega: float
    theta_call: float
    rho_domestic: float
    rho_foreign: float
    vanna: float
    volga: float

class GarmanKohlhagenFXEngine:
    """European FX currency option pricing and full cross-currency Greeks engine."""

    @classmethod
    def price_and_greeks(
        cls,
        spot: float,
        strike: float,
        t: float,
        sigma: float,
        r_domestic: float,
        r_foreign: float
    ) -> FXOptionGreeks:
        """Calculates exact Garman-Kohlhagen European Call/Put and complete analytic Greeks."""
        if t <= 0.0 or sigma <= 1e-9:
            c = max(0.0, spot * math.exp(-r_foreign * t) - strike * math.exp(-r_domestic * t))
            p = max(0.0, strike * math.exp(-r_domestic * t) - spot * math.exp(-r_foreign * t))
            return FXOptionGreeks(
                spot=spot, strike=strike, maturity=t,
                call_price=c, put_price=p,
                spot_delta_call=1.0 if spot > strike else 0.0,
                spot_delta_put=-1.0 if spot < strike else 0.0,
                forward_delta_call=1.0 if spot > strike else 0.0,
                dual_delta_call=0.0, gamma=0.0, vega=0.0, theta_call=0.0,
                rho_domestic=0.0, rho_foreign=0.0, vanna=0.0, volga=0.0
            )

        sqrt_t = math.sqrt(t)
        disc_d = math.exp(-r_domestic * t)
        disc_f = math.exp(-r_foreign * t)

        d1 = (math.log(spot / strike) + (r_domestic - r_foreign + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
        d2 = d1 - sigma * sqrt_t

        n_d1 = _norm_cdf(d1)
        n_d2 = _norm_cdf(d2)
        pdf_d1 = _norm_pdf(d1)

        call_price = spot * disc_f * n_d1 - strike * disc_d * n_d2
        put_price = strike * disc_d * _norm_cdf(-d2) - spot * disc_f * _norm_cdf(-d1)

        # Greeks
        spot_delta_call = disc_f * n_d1
        spot_delta_put = -disc_f * _norm_cdf(-d1)
        forward_delta_call = n_d1
        dual_delta_call = -disc_d * n_d2

        gamma = (disc_f * pdf_d1) / (spot * sigma * sqrt_t)
        vega = spot * disc_f * sqrt_t * pdf_d1

        term1 = -(spot * disc_f * pdf_d1 * sigma) / (2.0 * sqrt_t)
        term2 = r_foreign * spot * disc_f * n_d1
        term3 = -r_domestic * strike * disc_d * n_d2
        theta_call = term1 + term2 + term3

        rho_d = strike * t * disc_d * n_d2
        rho_f = -spot * t * disc_f * n_d1

        vanna = -disc_f * pdf_d1 * (d2 / sigma)
        volga = vega * (d1 * d2 / sigma)

        return FXOptionGreeks(
            spot=spot,
            strike=strike,
            maturity=t,
            call_price=call_price,
            put_price=put_price,
            spot_delta_call=spot_delta_call,
            spot_delta_put=spot_delta_put,
            forward_delta_call=forward_delta_call,
            dual_delta_call=dual_delta_call,
            gamma=gamma,
            vega=vega,
            theta_call=theta_call,
            rho_domestic=rho_d,
            rho_foreign=rho_f,
            vanna=vanna,
            volga=volga
        )

    @classmethod
    def covered_interest_parity_basis(
        cls,
        spot: float,
        forward_market: float,
        t: float,
        r_domestic: float,
        r_foreign: float
    ) -> float:
        """Calculates CIP cross-currency basis in basis points: Basis = (1/T) ln(F_mkt/S) - (r_d - r_f)."""
        theoretical_diff = r_domestic - r_foreign
        market_implied_diff = (1.0 / t) * math.log(forward_market / spot)
        basis = (market_implied_diff - theoretical_diff) * 10000.0
        return basis


# ==============================================================================
# 4. MERTON (1976) JUMP-DIFFUSION ENGINE
# ==============================================================================

@dataclass
class MertonJumpResult:
    spot: float
    strike: float
    maturity: float
    call_price: float
    put_price: float
    jump_delta: float
    jump_gamma: float
    truncated_terms: int
    poisson_weight_sum: float

class MertonJumpDiffusionEngine:
    """Robert Merton (1976) jump-diffusion European option pricing via Poisson series expansion."""

    @classmethod
    def price_european(
        cls,
        s0: float,
        k: float,
        t: float,
        r: float,
        sigma: float,
        lambda_jump: float,
        mu_jump: float,
        sigma_jump: float,
        max_terms: int = 60,
        tol: float = 1e-12
    ) -> MertonJumpResult:
        """Computes analytical Merton jump-diffusion call and put prices."""
        kappa = math.exp(mu_jump + 0.5 * sigma_jump * sigma_jump) - 1.0
        lambda_prime = lambda_jump * (1.0 + kappa)

        call_sum = 0.0
        delta_sum = 0.0
        gamma_sum = 0.0
        weight_sum = 0.0

        poisson_factor = math.exp(-lambda_prime * t)
        factorial_n = 1.0

        terms_used = 0
        for n in range(max_terms):
            if n > 0:
                factorial_n *= n
            poisson_weight = poisson_factor * ((lambda_prime * t) ** n) / factorial_n
            weight_sum += poisson_weight

            sigma_n = math.sqrt(sigma * sigma + (n * sigma_jump * sigma_jump) / t)
            r_n = r - lambda_jump * kappa + (n * math.log(1.0 + kappa)) / t

            c_n = _black_scholes_call(s0, k, t, sigma_n, r_n, q=0.0)

            d1_n = (math.log(s0 / k) + (r_n + 0.5 * sigma_n * sigma_n) * t) / (sigma_n * math.sqrt(t))
            delta_n = _norm_cdf(d1_n)
            gamma_n = _norm_pdf(d1_n) / (s0 * sigma_n * math.sqrt(t))

            call_sum += poisson_weight * c_n
            delta_sum += poisson_weight * delta_n
            gamma_sum += poisson_weight * gamma_n

            terms_used = n + 1
            if poisson_weight < tol and n > 5:
                break

        put_price = call_sum - s0 + k * math.exp(-r * t)

        return MertonJumpResult(
            spot=s0,
            strike=k,
            maturity=t,
            call_price=call_sum,
            put_price=put_price,
            jump_delta=delta_sum,
            jump_gamma=gamma_sum,
            truncated_terms=terms_used,
            poisson_weight_sum=weight_sum
        )

    @classmethod
    def simulate_paths(
        cls,
        s0: float,
        t: float,
        r: float,
        sigma: float,
        lambda_jump: float,
        mu_jump: float,
        sigma_jump: float,
        n_steps: int = 100,
        n_paths: int = 5000,
        seed: Optional[int] = 42
    ) -> Tuple[np.ndarray, float]:
        """Vectorized Monte Carlo path generation under Merton jump-diffusion."""
        if seed is not None:
            np.random.seed(seed)

        dt = t / n_steps
        kappa = math.exp(mu_jump + 0.5 * sigma_jump * sigma_jump) - 1.0
        drift = (r - lambda_jump * kappa - 0.5 * sigma * sigma) * dt
        vol_step = sigma * math.sqrt(dt)

        log_paths = np.zeros((n_paths, n_steps + 1))
        log_paths[:, 0] = math.log(s0)

        for step in range(1, n_steps + 1):
            z = np.random.standard_normal(n_paths)
            jump_counts = np.random.poisson(lambda_jump * dt, size=n_paths)

            jump_incs = np.zeros(n_paths)
            active_jumps = jump_counts > 0
            if np.any(active_jumps):
                for idx in np.where(active_jumps)[0]:
                    k_jumps = jump_counts[idx]
                    j_samples = np.random.normal(mu_jump, sigma_jump, size=k_jumps)
                    jump_incs[idx] = np.sum(j_samples)

            log_paths[:, step] = log_paths[:, step - 1] + drift + vol_step * z + jump_incs

        price_paths = np.exp(log_paths)
        mc_terminal = price_paths[:, -1]
        return price_paths, float(np.mean(mc_terminal))


# ==============================================================================
# 5. CONTINUOUS KELLY CRITERION & DRAWDOWN PROBABILITY ENGINE
# ==============================================================================

@dataclass
class KellyGrowthProfile:
    mu: float
    r: float
    sigma: float
    sharpe_ratio: float
    full_kelly_f: float
    half_kelly_f: float
    max_growth_rate: float
    half_kelly_growth_rate: float
    growth_efficiency_ratio: float
    drawdown_eval_depths: List[float]
    full_kelly_mdd_probs: List[float]
    half_kelly_mdd_probs: List[float]

@dataclass
class RuinAnalysisResult:
    initial_wealth: float
    stop_wealth: float
    target_wealth: float
    allocation_f: float
    ruin_probability: float
    success_probability: float

class ContinuousKellyGrowthEngine:
    """Continuous-time Kelly optimal growth, Grossman-Zhou drawdown probability and ruin theory."""

    @classmethod
    def analyze_growth_profile(
        cls,
        mu: float,
        r: float,
        sigma: float,
        eval_drawdowns: Optional[List[float]] = None
    ) -> KellyGrowthProfile:
        """Calculates continuous Kelly leverage, growth curve, and Grossman-Zhou drawdown distributions."""
        if sigma <= 1e-6:
            raise ValueError("Volatility sigma must be strictly positive.")

        eval_drawdowns = eval_drawdowns or [0.10, 0.20, 0.30, 0.50, 0.70]
        excess_ret = mu - r
        sharpe = excess_ret / sigma
        f_star = excess_ret / (sigma * sigma)
        f_half = 0.5 * f_star

        max_growth = r + 0.5 * (sharpe ** 2)
        half_growth = r + 0.375 * (sharpe ** 2)
        efficiency = (half_growth - r) / max(1e-9, max_growth - r)

        full_mdd = []
        half_mdd = []
        for d in eval_drawdowns:
            p_full = (1.0 - d) ** 1.0
            p_half = (1.0 - d) ** 3.0
            full_mdd.append(p_full)
            half_mdd.append(p_half)

        return KellyGrowthProfile(
            mu=mu,
            r=r,
            sigma=sigma,
            sharpe_ratio=sharpe,
            full_kelly_f=f_star,
            half_kelly_f=f_half,
            max_growth_rate=max_growth,
            half_kelly_growth_rate=half_growth,
            growth_efficiency_ratio=efficiency,
            drawdown_eval_depths=eval_drawdowns,
            full_kelly_mdd_probs=full_mdd,
            half_kelly_mdd_probs=half_mdd
        )

    @classmethod
    def calculate_ruin_probability(
        cls,
        w0: float,
        w_stop: float,
        w_target: float,
        mu: float,
        r: float,
        sigma: float,
        f: float
    ) -> RuinAnalysisResult:
        """Computes analytical ruin probability under Geometric Brownian Motion scale function."""
        if w_stop >= w0 or w_target <= w0 or f <= 0.0:
            return RuinAnalysisResult(w0, w_stop, w_target, f, 1.0, 0.0)

        f_star = (mu - r) / (sigma * sigma)
        gamma = 1.0 - 2.0 * (f_star / f)

        if abs(gamma) < 1e-6:
            p_ruin = math.log(w_target / w0) / math.log(w_target / w_stop)
        else:
            s_target = (w_target / w_stop) ** gamma
            s_w0 = (w0 / w_stop) ** gamma
            p_ruin = (s_target - s_w0) / max(1e-12, s_target - 1.0)

        p_ruin = max(0.0, min(1.0, p_ruin))
        p_success = 1.0 - p_ruin

        return RuinAnalysisResult(
            initial_wealth=w0,
            stop_wealth=w_stop,
            target_wealth=w_target,
            allocation_f=f,
            ruin_probability=p_ruin,
            success_probability=p_success
        )


# ==============================================================================
# 6. LÓPEZ DE PRADO (2019) HIERARCHICAL EQUAL RISK CONTRIBUTION (HERC)
# ==============================================================================

@dataclass
class HERCAllocationResult:
    asset_names: List[str]
    weights: List[float]
    portfolio_volatility: float
    diversification_ratio: float
    effective_constituents_enc: float
    cluster_order: List[int]
    distance_matrix: List[List[float]]

class HierarchicalEqualRiskContributionEngine:
    """Marcos López de Prado (2019) HERC asset allocation via recursive tree bisection."""

    @staticmethod
    def correlation_distance(corr: np.ndarray) -> np.ndarray:
        """Computes correlation distance matrix D_ij = sqrt(0.5 * (1 - rho_ij))."""
        dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
        np.fill_diagonal(dist, 0.0)
        return dist

    @classmethod
    def _hierarchical_clustering(cls, dist: np.ndarray) -> List[Tuple[int, int, float, int]]:
        """Pure-Python / NumPy Ward / Average linkage agglomerative clustering."""
        n = dist.shape[0]
        clusters = {i: [i] for i in range(n)}
        d_matrix = dist.copy().astype(float)

        linkage = []
        cluster_id = n

        while len(clusters) > 1:
            min_dist = float("inf")
            c1_best, c2_best = -1, -1

            keys = sorted(clusters.keys())
            for i in range(len(keys)):
                k1 = keys[i]
                for j in range(i + 1, len(keys)):
                    k2 = keys[j]
                    d_val = d_matrix[k1, k2]
                    if d_val < min_dist:
                        min_dist = d_val
                        c1_best, c2_best = k1, k2

            members_c1 = clusters[c1_best]
            members_c2 = clusters[c2_best]
            new_members = members_c1 + members_c2
            count = len(new_members)

            linkage.append((c1_best, c2_best, min_dist, count))

            new_dim = cluster_id + 1
            if d_matrix.shape[0] < new_dim:
                new_d = np.zeros((new_dim + 10, new_dim + 10))
                new_d[:d_matrix.shape[0], :d_matrix.shape[1]] = d_matrix
                d_matrix = new_d

            for k in clusters.keys():
                if k != c1_best and k != c2_best:
                    d_new = (len(members_c1) * d_matrix[c1_best, k] + len(members_c2) * d_matrix[c2_best, k]) / count
                    d_matrix[cluster_id, k] = d_new
                    d_matrix[k, cluster_id] = d_new

            del clusters[c1_best]
            del clusters[c2_best]
            clusters[cluster_id] = new_members
            cluster_id += 1

        return linkage

    @classmethod
    def _get_leaf_order(cls, linkage: List[Tuple[int, int, float, int]], n: int) -> List[int]:
        """Extracts sorted leaves from linkage dendrogram."""
        tree = {i: [i] for i in range(n)}
        cluster_id = n
        for c1, c2, _, _ in linkage:
            tree[cluster_id] = tree[c1] + tree[c2]
            cluster_id += 1
        return tree[cluster_id - 1]

    @classmethod
    def allocate_herc(
        cls,
        cov: np.ndarray,
        asset_names: Optional[List[str]] = None
    ) -> HERCAllocationResult:
        """Computes Hierarchical Equal Risk Contribution weights via recursive bisection."""
        n = cov.shape[0]
        asset_names = asset_names or [f"Asset_{i+1}" for i in range(n)]

        std_diag = np.sqrt(np.diag(cov))
        std_diag = np.where(std_diag <= 1e-9, 1e-4, std_diag)
        corr = cov / np.outer(std_diag, std_diag)
        corr = np.clip(corr, -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)
        dist = cls.correlation_distance(corr)

        linkage = cls._hierarchical_clustering(dist)
        leaf_order = cls._get_leaf_order(linkage, n)

        weights = {i: 1.0 for i in leaf_order}
        clusters = [leaf_order]

        def get_cluster_variance(cluster_indices: List[int]) -> float:
            sub_cov = cov[np.ix_(cluster_indices, cluster_indices)]
            sub_vars = np.diag(sub_cov)
            inv_vars = 1.0 / np.maximum(1e-8, sub_vars)
            w_sub = inv_vars / np.sum(inv_vars)
            c_var = float(w_sub.T @ sub_cov @ w_sub)
            return max(1e-9, c_var)

        while len(clusters) > 0:
            clusters_next = []
            for clus in clusters:
                if len(clus) > 1:
                    mid = len(clus) // 2
                    left = clus[:mid]
                    right = clus[mid:]

                    var_l = get_cluster_variance(left)
                    var_r = get_cluster_variance(right)

                    std_l = math.sqrt(var_l)
                    std_r = math.sqrt(var_r)
                    alpha_l = std_r / (std_l + std_r)
                    alpha_r = 1.0 - alpha_l

                    for idx in left:
                        weights[idx] *= alpha_l
                    for idx in right:
                        weights[idx] *= alpha_r

                    if len(left) > 1:
                        clusters_next.append(left)
                    if len(right) > 1:
                        clusters_next.append(right)
            clusters = clusters_next

        final_w = np.array([weights[i] for i in range(n)])
        final_w = final_w / np.sum(final_w)

        port_var = float(final_w.T @ cov @ final_w)
        port_vol = math.sqrt(max(1e-9, port_var))
        weighted_vol = float(np.sum(final_w * std_diag))
        div_ratio = weighted_vol / max(1e-9, port_vol)
        enc = 1.0 / float(np.sum(final_w ** 2))

        return HERCAllocationResult(
            asset_names=asset_names,
            weights=final_w.tolist(),
            portfolio_volatility=port_vol,
            diversification_ratio=div_ratio,
            effective_constituents_enc=enc,
            cluster_order=leaf_order,
            distance_matrix=dist.tolist()
        )


# ==============================================================================
# 7. STANDALONE CLI INTERFACE
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 29: Advanced Financial Engineering CLI")
    subparsers = parser.add_subparsers(dest="command", help="Financial engine commands")

    sabr_p = subparsers.add_parser("sabr", help="Hagan (2002) SABR Implied Volatility")
    sabr_p.add_argument("--forward", type=float, default=100.0)
    sabr_p.add_argument("--strike", type=float, default=100.0)
    sabr_p.add_argument("--t", type=float, default=1.0)
    sabr_p.add_argument("--alpha", type=float, default=0.20)
    sabr_p.add_argument("--beta", type=float, default=0.5)
    sabr_p.add_argument("--rho", type=float, default=-0.3)
    sabr_p.add_argument("--nu", type=float, default=0.4)

    vs_p = subparsers.add_parser("varswap", help="Demeterfi Variance Swap Replication")
    vs_p.add_argument("--s0", type=float, default=100.0)
    vs_p.add_argument("--r", type=float, default=0.04)
    vs_p.add_argument("--t", type=float, default=1.0)

    fx_p = subparsers.add_parser("fx", help="Garman-Kohlhagen European FX Option Greeks")
    fx_p.add_argument("--spot", type=float, default=1.10)
    fx_p.add_argument("--strike", type=float, default=1.10)
    fx_p.add_argument("--t", type=float, default=0.5)
    fx_p.add_argument("--sigma", type=float, default=0.12)
    fx_p.add_argument("--rd", type=float, default=0.05)
    fx_p.add_argument("--rf", type=float, default=0.03)

    merton_p = subparsers.add_parser("merton", help="Merton Jump-Diffusion Option Pricing")
    merton_p.add_argument("--s0", type=float, default=100.0)
    merton_p.add_argument("--k", type=float, default=100.0)
    merton_p.add_argument("--t", type=float, default=1.0)
    merton_p.add_argument("--r", type=float, default=0.05)
    merton_p.add_argument("--sigma", type=float, default=0.15)
    merton_p.add_argument("--lam", type=float, default=1.0)
    merton_p.add_argument("--muj", type=float, default=-0.05)
    merton_p.add_argument("--sigmaj", type=float, default=0.10)

    kelly_p = subparsers.add_parser("kelly", help="Continuous Kelly & Drawdown Probability")
    kelly_p.add_argument("--mu", type=float, default=0.12)
    kelly_p.add_argument("--r", type=float, default=0.04)
    kelly_p.add_argument("--sigma", type=float, default=0.18)

    herc_p = subparsers.add_parser("herc", help="Hierarchical Equal Risk Contribution")
    herc_p.add_argument("--n_assets", type=int, default=5)

    args = parser.parse_args()

    if args.command == "sabr":
        vol = SABRStochasticVolatilityEngine.implied_volatility(
            args.forward, args.strike, args.t, args.alpha, args.beta, args.rho, args.nu
        )
        call_p = SABRStochasticVolatilityEngine.price_black76(
            args.forward, args.strike, args.t, 0.05, args.alpha, args.beta, args.rho, args.nu, is_call=True
        )
        print(json.dumps({"implied_black_vol": vol, "call_price": call_p}, indent=2))

    elif args.command == "fx":
        res = GarmanKohlhagenFXEngine.price_and_greeks(
            args.spot, args.strike, args.t, args.sigma, args.rd, args.rf
        )
        print(json.dumps(res.__dict__, indent=2))

    elif args.command == "merton":
        res = MertonJumpDiffusionEngine.price_european(
            args.s0, args.k, args.t, args.r, args.sigma, args.lam, args.muj, args.sigmaj
        )
        print(json.dumps(res.__dict__, indent=2))

    elif args.command == "kelly":
        res = ContinuousKellyGrowthEngine.analyze_growth_profile(args.mu, args.r, args.sigma)
        print(json.dumps(res.__dict__, indent=2))

    else:
        print("Specify a valid subcommand (sabr, varswap, fx, merton, kelly, herc).")

if __name__ == "__main__":
    main()
