"""Phase 30: Quantitative Financial Engineering & Institutional Risk Architecture.

Core Pillars:
1. Malliavin Calculus Monte Carlo Greeks Engine (Zero-bias weight Greeks for continuous and discontinuous payoffs)
2. Double Heston & Heston 3/2 Super-Linear Volatility Engine (Multi-scale variance & Lewis-Lipton CIR inverse)
3. Piterbarg (2010) Multi-Currency Collateralized Discounting & Cheapest-to-Deliver (CTD) Collateral Engine
4. Smart Order Routing (SOR) & Dark Pool Allocation Engine (Fragmented liquidity, adverse selection & delay cost)
5. Cross-Holding / Circular Ownership Matrix Decomposition & HoldCo Discount Forensic Engine
6. Uniswap v3/v4 Geometric Mean TWAP Oracle Manipulation Economics & Arbitrageur Leakage Engine
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


# ==============================================================================
# 1. MALLIAVIN CALCULUS MONTE CARLO GREEKS ENGINE
# ==============================================================================

@dataclass
class MalliavinGreeksResult:
    option_price: float
    delta_malliavin: float
    gamma_malliavin: float
    vega_malliavin: float
    delta_standard_err: float
    gamma_standard_err: float
    is_discontinuous_payoff: bool
    analytic_delta_benchmark: Optional[float] = None
    analytic_gamma_benchmark: Optional[float] = None


class MalliavinGreeksEngine:
    """
    Monte Carlo Greek computation via Malliavin Calculus Integration by Parts (Fournié et al. 1999).
    Enables computation of Delta, Gamma, and Vega WITHOUT differentiating the payoff g(S_T).
    Extremely accurate for discontinuous payoffs (e.g. Digital / Binary calls) where finite
    difference (bump-and-reprice) exhibits explosive O(1/epsilon) variance.
    """

    @staticmethod
    def calculate_greeks(
        s0: float,
        k_strike: float,
        r: float,
        sigma: float,
        t_mat: float,
        n_paths: int = 100000,
        payoff_type: str = "vanilla_call",
        seed: Optional[int] = 42
    ) -> MalliavinGreeksResult:
        """
        Calculates price, Delta, Gamma, and Vega using Malliavin weights:
        - Delta Weight: pi^Delta = W_T / (s0 * sigma * T)
        - Gamma Weight: pi^Gamma = (W_T^2 / (sigma * T) - 1/sigma - W_T) / (s0^2 * sigma * T)
        - Vega Weight:  pi^Vega  = (W_T^2 - T) / sigma - W_T * sqrt(T) (scaled)
        """
        if s0 <= 0 or k_strike <= 0:
            raise ValueError("s0 and k_strike must be strictly positive.")
        if t_mat <= 0 or sigma <= 0:
            raise ValueError("Time to maturity and volatility must be strictly positive.")
        if n_paths < 1000:
            raise ValueError("n_paths must be at least 1000 for convergence.")

        rng = np.random.default_rng(seed)
        z = rng.standard_normal(n_paths)
        sqrt_t = math.sqrt(t_mat)
        w_t = sqrt_t * z

        drift = (r - 0.5 * sigma * sigma) * t_mat
        s_t = s0 * np.exp(drift + sigma * w_t)
        disc = math.exp(-r * t_mat)

        # Payoff calculation
        is_discontinuous = False
        if payoff_type == "digital_call":
            payoff = np.where(s_t > k_strike, 1.0, 0.0)
            is_discontinuous = True
        elif payoff_type == "vanilla_call":
            payoff = np.maximum(s_t - k_strike, 0.0)
        elif payoff_type == "vanilla_put":
            payoff = np.maximum(k_strike - s_t, 0.0)
        else:
            raise ValueError(f"Unsupported payoff_type: {payoff_type}")

        # Malliavin weights
        weight_delta = w_t / (s0 * sigma * t_mat)
        weight_gamma = ( (w_t**2 / (sigma * t_mat)) - (1.0 / sigma) - w_t ) / (s0 * s0 * sigma * t_mat)
        weight_vega = (w_t**2 - t_mat) / sigma - w_t * sqrt_t

        price_samples = disc * payoff
        delta_samples = disc * payoff * weight_delta
        gamma_samples = disc * payoff * weight_gamma
        vega_samples = disc * payoff * (w_t**2 / (sigma * t_mat) - 1.0 / sigma - w_t) * sigma * sqrt_t / s0

        price = float(np.mean(price_samples))
        delta = float(np.mean(delta_samples))
        gamma = float(np.mean(gamma_samples))
        vega = float(np.mean(vega_samples))

        delta_se = float(np.std(delta_samples, ddof=1) / math.sqrt(n_paths))
        gamma_se = float(np.std(gamma_samples, ddof=1) / math.sqrt(n_paths))

        # Benchmarks for vanilla calls
        analytic_delta = None
        analytic_gamma = None
        if payoff_type == "vanilla_call":
            d1 = (math.log(s0 / k_strike) + (r + 0.5 * sigma * sigma) * t_mat) / (sigma * sqrt_t)
            analytic_delta = float(_norm_cdf(d1))
            analytic_gamma = float(_norm_pdf(d1) / (s0 * sigma * sqrt_t))
        elif payoff_type == "digital_call":
            d2 = (math.log(s0 / k_strike) + (r - 0.5 * sigma * sigma) * t_mat) / (sigma * sqrt_t)
            analytic_delta = float(disc * _norm_pdf(d2) / (s0 * sigma * sqrt_t))

        return MalliavinGreeksResult(
            option_price=price,
            delta_malliavin=delta,
            gamma_malliavin=gamma,
            vega_malliavin=vega,
            delta_standard_err=delta_se,
            gamma_standard_err=gamma_se,
            is_discontinuous_payoff=is_discontinuous,
            analytic_delta_benchmark=analytic_delta,
            analytic_gamma_benchmark=analytic_gamma
        )


# ==============================================================================
# 2. DOUBLE HESTON & HESTON 3/2 SUPER-LINEAR VOLATILITY ENGINE
# ==============================================================================

@dataclass
class DoubleHestonResult:
    spot_price: float
    total_initial_variance: float
    fast_reverting_variance: float
    slow_reverting_variance: float
    feller_ratio_fast: float
    feller_ratio_slow: float
    simulated_terminal_mean: float
    integrated_variance_mean: float
    term_structure_profile: str


@dataclass
class HestonThreeHalvesResult:
    spot_price: float
    initial_variance: float
    super_linear_exponent: float
    vix_call_proxy_price: float
    variance_skewness: float
    vol_of_vol_amplification: float


class StochasticVolatilityAdvancedEngine:
    """
    Advanced Multi-Scale and Super-Linear Stochastic Volatility:
    1. Double Heston (Christoffersen et al. 2009): Two CIR variance processes (fast & slow mean-reversion).
    2. Heston 3/2 Model (Lewis 2000): Volatility of variance scales as v^(3/2), capturing VIX smile spikes.
    """

    @staticmethod
    def simulate_double_heston(
        s0: float,
        r: float,
        v1_0: float,
        kappa1: float,
        theta1: float,
        sigma_v1: float,
        rho1: float,
        v2_0: float,
        kappa2: float,
        theta2: float,
        sigma_v2: float,
        rho2: float,
        t_mat: float = 1.0,
        n_steps: int = 252,
        n_paths: int = 5000,
        seed: Optional[int] = 101
    ) -> DoubleHestonResult:
        """
        Simulates two-factor Heston model:
        v(t) = v1(t) + v2(t)
        v1: Fast scale (e.g. kappa1 = 10.0, capturing short-term spikes)
        v2: Slow scale (e.g. kappa2 = 0.5, capturing macroeconomic business cycles)
        """
        if s0 <= 0 or v1_0 < 0 or v2_0 < 0:
            raise ValueError("Prices and initial variances must be non-negative.")

        feller1 = (2.0 * kappa1 * theta1) / (sigma_v1 * sigma_v1)
        feller2 = (2.0 * kappa2 * theta2) / (sigma_v2 * sigma_v2)

        dt = t_mat / n_steps
        sqrt_dt = math.sqrt(dt)

        rng = np.random.default_rng(seed)
        s = np.full(n_paths, s0, dtype=np.float64)
        v1 = np.full(n_paths, v1_0, dtype=np.float64)
        v2 = np.full(n_paths, v2_0, dtype=np.float64)
        integrated_var = np.zeros(n_paths, dtype=np.float64)

        for _ in range(n_steps):
            z_s1 = rng.standard_normal(n_paths)
            z_v1_indep = rng.standard_normal(n_paths)
            z_s2 = rng.standard_normal(n_paths)
            z_v2_indep = rng.standard_normal(n_paths)

            z_v1 = rho1 * z_s1 + math.sqrt(max(0.0, 1.0 - rho1 * rho1)) * z_v1_indep
            z_v2 = rho2 * z_s2 + math.sqrt(max(0.0, 1.0 - rho2 * rho2)) * z_v2_indep

            # Full truncation Euler scheme for CIR
            v1_pos = np.maximum(v1, 0.0)
            v2_pos = np.maximum(v2, 0.0)

            v1_next = v1 + kappa1 * (theta1 - v1_pos) * dt + sigma_v1 * np.sqrt(v1_pos) * sqrt_dt * z_v1
            v2_next = v2 + kappa2 * (theta2 - v2_pos) * dt + sigma_v2 * np.sqrt(v2_pos) * sqrt_dt * z_v2

            v1 = np.maximum(v1_next, 0.0)
            v2 = np.maximum(v2_next, 0.0)

            tot_v = v1 + v2
            integrated_var += tot_v * dt

            # Asset diffusion
            w_s = (np.sqrt(v1) * z_s1 + np.sqrt(v2) * z_s2) / np.sqrt(np.maximum(1e-12, tot_v))
            s = s * np.exp((r - 0.5 * tot_v) * dt + np.sqrt(tot_v) * sqrt_dt * w_s)

        profile = f"Çift Ölçekli Volatilite: Hızlı Sönüm (kappa1={kappa1:.1f}) + Yavaş Makro Taban (kappa2={kappa2:.1f})"

        return DoubleHestonResult(
            spot_price=float(s0),
            total_initial_variance=float(v1_0 + v2_0),
            fast_reverting_variance=float(v1_0),
            slow_reverting_variance=float(v2_0),
            feller_ratio_fast=float(feller1),
            feller_ratio_slow=float(feller2),
            simulated_terminal_mean=float(np.mean(s)),
            integrated_variance_mean=float(np.mean(integrated_var)),
            term_structure_profile=profile
        )

    @staticmethod
    def simulate_heston_three_halves(
        s0: float,
        r: float,
        v0: float,
        kappa: float,
        theta: float,
        epsilon: float,
        rho: float,
        t_mat: float = 0.25,
        n_steps: int = 100,
        n_paths: int = 5000,
        vix_strike: float = 0.20,
        seed: Optional[int] = 102
    ) -> HestonThreeHalvesResult:
        """
        Heston 3/2 Model:
        dv(t) = kappa * v(t) * (theta - v(t)) dt + epsilon * v(t)^(3/2) dW_v(t)
        Crucial for VIX derivatives where vol-of-vol explodes during market crises.
        """
        dt = t_mat / n_steps
        sqrt_dt = math.sqrt(dt)

        rng = np.random.default_rng(seed)
        v = np.full(n_paths, v0, dtype=np.float64)

        for _ in range(n_steps):
            zv = rng.standard_normal(n_paths)
            v_pos = np.maximum(v, 1e-6)
            drift = kappa * v_pos * (theta - v_pos) * dt
            diffusion = epsilon * (v_pos ** 1.5) * sqrt_dt * zv
            v = np.maximum(v + drift + diffusion, 1e-6)

        v_terminal = v
        vol_terminal = np.sqrt(v_terminal)
        disc = math.exp(-r * t_mat)

        vix_call_payoff = np.maximum(vol_terminal - vix_strike, 0.0)
        vix_call_price = float(disc * np.mean(vix_call_payoff))

        skew = float(np.mean((vol_terminal - np.mean(vol_terminal))**3) / (np.std(vol_terminal)**3 + 1e-12))
        amplification = float(np.mean(v_terminal**1.5) / (np.mean(v_terminal)**1.5 + 1e-12))

        return HestonThreeHalvesResult(
            spot_price=float(s0),
            initial_variance=float(v0),
            super_linear_exponent=1.5,
            vix_call_proxy_price=vix_call_price,
            variance_skewness=skew,
            vol_of_vol_amplification=amplification
        )


# ==============================================================================
# 3. PITERBARG (2010) MULTI-CURRENCY COLLATERALIZED DISCOUNTING ENGINE
# ==============================================================================

@dataclass
class CollateralCurrencyQuote:
    currency: str
    collateral_rate: float
    domestic_foreign_basis: float
    haircut: float = 0.0


@dataclass
class PiterbargDiscountResult:
    effective_collateral_rate: float
    piterbarg_discount_factor: float
    zero_coupon_present_value: float
    cheapest_to_deliver_currency: str
    embedded_option_value_bps: float
    multi_currency_breakdown: List[Dict[str, Any]]


class PiterbargCollateralDiscountEngine:
    """
    Vladimir Piterbarg (2010) Framework:
    'Funding beyond discount: collateral agreements and derivatives capital'.
    Models derivative discounting under multi-currency ISDA CSA collateral agreements
    with embedded Cheapest-to-Deliver (CTD) collateral optionality.
    """

    @staticmethod
    def calculate_discount_curve(
        notional: float,
        maturity_years: float,
        domestic_r: float,
        collateral_quotes: List[CollateralCurrencyQuote],
        volatility_basis: float = 0.02
    ) -> PiterbargDiscountResult:
        """
        Calculates the effective collateralized discount rate and CTD optionality.
        r_eff = c_k(t) - y_X(t)
        For multi-currency CSA, party posts min_k (c_k + cost), yielding an option benefit.
        """
        if maturity_years <= 0 or notional <= 0:
            raise ValueError("Maturity and notional must be positive.")
        if not collateral_quotes:
            raise ValueError("At least one collateral quote must be provided.")

        evaluated_rates = []
        for q in collateral_quotes:
            # Effective funding cost for posting currency k in domestic terms:
            all_in_rate = q.collateral_rate - q.domestic_foreign_basis + (q.haircut * 0.01)
            evaluated_rates.append({
                "currency": q.currency,
                "raw_collateral_rate": q.collateral_rate,
                "basis": q.domestic_foreign_basis,
                "haircut": q.haircut,
                "all_in_domestic_rate": all_in_rate
            })

        evaluated_rates.sort(key=lambda x: x["all_in_domestic_rate"])
        ctd = evaluated_rates[0]
        base_rate = ctd["all_in_domestic_rate"]

        # Embedded CTD Collateral Option: If 2 or more currencies are eligible
        n_eligible = len(evaluated_rates)
        ctd_option_bps = 0.0
        if n_eligible > 1:
            diff_second = evaluated_rates[1]["all_in_domestic_rate"] - base_rate
            spread_vol = volatility_basis * math.sqrt(maturity_years)
            ctd_option_bps = max(0.0, (spread_vol * 0.3989 - 0.5 * diff_second)) * 10000.0

        effective_rate = base_rate - (ctd_option_bps / 10000.0)
        df = math.exp(-effective_rate * maturity_years)
        pv = notional * df

        return PiterbargDiscountResult(
            effective_collateral_rate=float(effective_rate),
            piterbarg_discount_factor=float(df),
            zero_coupon_present_value=float(pv),
            cheapest_to_deliver_currency=ctd["currency"],
            embedded_option_value_bps=float(ctd_option_bps),
            multi_currency_breakdown=evaluated_rates
        )


# ==============================================================================
# 4. SMART ORDER ROUTING (SOR) & FRAGMENTED VENUES ENGINE
# ==============================================================================

@dataclass
class VenueQuote:
    venue_id: str
    venue_type: str  # 'lit' or 'dark'
    available_liquidity: float
    bid_price: float
    ask_price: float
    fee_per_share: float  # positive for taker fee, negative for rebate
    latency_ms: float
    fill_probability: float  # 1.0 for lit, <= 1.0 for dark
    adverse_selection_cost: float = 0.0  # cost per share if filled in dark pool


@dataclass
class SmartOrderRoutingResult:
    total_order_size: float
    side: str
    routed_allocations: Dict[str, float]
    effective_average_price: float
    total_fees_paid: float
    expected_slippage: float
    adverse_selection_risk: float
    lit_ratio: float
    dark_ratio: float


class SmartOrderRoutingEngine:
    """
    Cartea-Jaimungal & Wang (2014) Optimal Smart Order Routing (SOR).
    Allocates an institutional block order across fragmented Lit exchanges and Dark Pools
    balancing liquidity depth, maker/taker fees, fill latency, and adverse selection.
    """

    @staticmethod
    def optimize_route(
        order_size: float,
        side: str,
        venues: List[VenueQuote],
        urgency_parameter: float = 0.5
    ) -> SmartOrderRoutingResult:
        """
        Optimizes allocation across venues:
        1. Dark pools receive passive allocation up to their expected non-toxic fill capacity.
        2. Remaining size is routed to Lit venues based on best net execution price (Price +/- Fee).
        """
        if order_size <= 0:
            raise ValueError("Order size must be strictly positive.")
        if side.lower() not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'.")
        if not venues:
            raise ValueError("At least one venue must be provided.")

        side_buy = (side.lower() == "buy")
        allocations: Dict[str, float] = {v.venue_id: 0.0 for v in venues}
        remaining_size = order_size

        # 1. Evaluate Dark Pools: allocate if urgency allows and fill prob is reasonable
        dark_venues = [v for v in venues if v.venue_type.lower() == "dark"]
        total_dark_allocated = 0.0

        for dv in dark_venues:
            if remaining_size <= 0:
                break
            safe_dark_cap = dv.available_liquidity * dv.fill_probability * (1.0 - 0.5 * urgency_parameter)
            alloc = min(remaining_size, safe_dark_cap)
            allocations[dv.venue_id] = alloc
            remaining_size -= alloc
            total_dark_allocated += alloc

        # 2. Evaluate Lit Venues: sort by all-in effective price
        lit_venues = [v for v in venues if v.venue_type.lower() == "lit"]

        def lit_cost_key(v: VenueQuote) -> float:
            p = v.ask_price if side_buy else -v.bid_price
            fee = v.fee_per_share
            lat_pen = (v.latency_ms / 10.0) * 0.0001 * urgency_parameter
            return p + fee + lat_pen

        lit_venues.sort(key=lit_cost_key)

        for lv in lit_venues:
            if remaining_size <= 0:
                break
            alloc = min(remaining_size, lv.available_liquidity)
            allocations[lv.venue_id] += alloc
            remaining_size -= alloc

        # If order not completely filled, force residual to deepest venue
        if remaining_size > 0 and lit_venues:
            deepest = max(lit_venues, key=lambda v: v.available_liquidity)
            allocations[deepest.venue_id] += remaining_size
            remaining_size = 0.0

        # Calculate weighted average execution metrics
        total_spent = 0.0
        total_fees = 0.0
        total_adverse = 0.0
        total_lit = 0.0

        venue_map = {v.venue_id: v for v in venues}
        for vid, qty in allocations.items():
            if qty <= 0:
                continue
            v = venue_map[vid]
            base_p = v.ask_price if side_buy else v.bid_price
            total_spent += qty * base_p
            total_fees += qty * v.fee_per_share
            if v.venue_type.lower() == "dark":
                total_adverse += qty * v.adverse_selection_cost
            else:
                total_lit += qty

        avg_price = (total_spent + total_fees) / order_size
        benchmark_price = (lit_venues[0].ask_price if side_buy else lit_venues[0].bid_price) if lit_venues else avg_price
        slippage = abs(avg_price - benchmark_price)

        return SmartOrderRoutingResult(
            total_order_size=order_size,
            side=side.upper(),
            routed_allocations=allocations,
            effective_average_price=float(avg_price),
            total_fees_paid=float(total_fees),
            expected_slippage=float(slippage),
            adverse_selection_risk=float(total_adverse / order_size),
            lit_ratio=float(total_lit / order_size),
            dark_ratio=float(total_dark_allocated / order_size)
        )


# ==============================================================================
# 5. CROSS-HOLDING / CIRCULAR OWNERSHIP & HOLDCO FORENSICS ENGINE
# ==============================================================================

@dataclass
class CrossHoldingResult:
    reported_market_caps: List[float]
    standalone_operating_values: List[float]
    double_counted_equity_volume: float
    direct_ownership_matrix: List[List[float]]
    leontief_inverse_matrix: List[List[float]]
    holdco_nav: float
    holdco_market_cap: float
    holdco_discount_percent: float
    activist_unbundling_upside_percent: float


class CrossHoldingHoldCoEngine:
    """
    Brioschi, Buzzacchi & Colombo (1989) & Faccio-Lang Matrix Decomposition.
    Unwinds circular corporate cross-ownership:
    V_market = V_operating + C * V_market  =>  V_market = (I - C)^(-1) * V_operating
    Reveals true standalone operating value, eliminates double counting,
    and quantifies Holding Company Discount & activist unbundling catalysts.
    """

    @staticmethod
    def analyze_cross_holdings(
        reported_market_caps: List[float],
        ownership_matrix: List[List[float]],
        holdco_index: int = 0,
        holdco_traded_market_cap: Optional[float] = None
    ) -> CrossHoldingResult:
        """
        reported_market_caps: [V_1, V_2, ..., V_n]
        ownership_matrix: C where C[i][j] is the fraction of firm j owned by firm i.
        holdco_traded_market_cap: Optional actual traded market cap of HoldCo (to calculate HoldCo discount against SOTP NAV).
        """
        n = len(reported_market_caps)
        if n == 0 or len(ownership_matrix) != n:
            raise ValueError("Dimensions of market caps and ownership matrix must match.")

        v_m = np.array(reported_market_caps, dtype=np.float64)
        c = np.array(ownership_matrix, dtype=np.float64)

        # Ensure diagonal is 0
        np.fill_diagonal(c, 0.0)

        # I - C matrix
        eye = np.eye(n, dtype=np.float64)
        i_minus_c = eye - c

        # Invert (I - C)
        try:
            leontief_inv = np.linalg.inv(i_minus_c)
        except np.linalg.LinAlgError:
            raise ValueError("Singular ownership matrix: circular ownership structure is invalid.")

        # V_operating = (I - C) * V_market
        v_operating = np.dot(i_minus_c, v_m)

        # Standalone values should be non-negative in healthy corporate groups
        v_operating_clean = np.maximum(v_operating, 0.0)

        total_reported = float(np.sum(v_m))
        total_operating = float(np.sum(v_operating_clean))
        double_counted = max(0.0, total_reported - total_operating)

        # HoldCo NAV = Operating Value of HoldCo + Sum(c[holdco][j] * V_m[j])
        holdco_mcap = float(holdco_traded_market_cap if holdco_traded_market_cap is not None else v_m[holdco_index])
        holdco_subs_val = float(np.sum(c[holdco_index, :] * v_m))
        holdco_nav = float(v_operating_clean[holdco_index] + holdco_subs_val)

        discount = 0.0
        if holdco_nav > 1e-6:
            discount = max(0.0, (holdco_nav - holdco_mcap) / holdco_nav)

        upside = 0.0
        if holdco_mcap > 1e-6:
            upside = max(0.0, (holdco_nav - holdco_mcap) / holdco_mcap)

        return CrossHoldingResult(
            reported_market_caps=[float(x) for x in v_m],
            standalone_operating_values=[float(x) for x in v_operating_clean],
            double_counted_equity_volume=float(double_counted),
            direct_ownership_matrix=[[float(cell) for cell in row] for row in c],
            leontief_inverse_matrix=[[float(cell) for cell in row] for row in leontief_inv],
            holdco_nav=float(holdco_nav),
            holdco_market_cap=float(holdco_mcap),
            holdco_discount_percent=float(discount * 100.0),
            activist_unbundling_upside_percent=float(upside * 100.0)
        )

    @staticmethod
    def solve_equilibrium_market_caps(
        standalone_operating_values: List[float],
        ownership_matrix: List[List[float]]
    ) -> List[float]:
        """
        Forward calculation: Given standalone operating values and cross-ownership matrix C,
        calculates equilibrium consolidated market caps: V_m = (I - C)^(-1) * V_op.
        """
        n = len(standalone_operating_values)
        c = np.array(ownership_matrix, dtype=np.float64)
        np.fill_diagonal(c, 0.0)
        eye = np.eye(n, dtype=np.float64)
        leontief_inv = np.linalg.inv(eye - c)
        v_op = np.array(standalone_operating_values, dtype=np.float64)
        v_m = np.dot(leontief_inv, v_op)
        return [float(x) for x in v_m]


# ==============================================================================
# 6. UNISWAP V3/V4 TWAP ORACLE MANIPULATION ECONOMICS ENGINE
# ==============================================================================

@dataclass
class OracleManipulationResult:
    initial_price: float
    target_manipulated_price: float
    time_window_seconds: int
    blocks_manipulated: int
    pool_liquidity_l: float
    single_block_slippage_cost: float
    leakage_to_arbitrageurs_per_block: float
    total_cumulative_manipulation_cost: float
    resulting_twap_price: float
    is_attack_economically_viable: bool
    max_borrowable_collateral_breakeven: float


class UniswapTwapOracleManipulationEngine:
    """
    Angeris, Chitra, Evans (2020/2021) Constant Function AMM TWAP Security.
    Computes the exact economic cost of manipulating a Uniswap v3/v4 Geometric Mean TWAP Oracle.
    Calculates single-block price distortion, multi-block leakage to arbitrageurs,
    and protocol solvency limits against flash-loan/multi-block price attacks.
    """

    @staticmethod
    def calculate_attack_cost(
        p0_true: float,
        p_target: float,
        window_seconds: int = 1800,  # 30-minute standard TWAP
        blocks_manipulated: int = 5,
        block_time_seconds: int = 12,
        pool_liquidity_l: float = 10000000.0,  # Uniswap L parameter
        borrowing_fee_rate: float = 0.0005,
        protocol_exploit_gain: float = 500000.0
    ) -> OracleManipulationResult:
        """
        Computes the cost of holding price at p_target for k blocks:
        1. Single-block swap cost (slippage from p0 to p_target)
        2. Arbitrageur leakage per block:
           Every block, arbitrageurs will bring price back towards p0_true.
           Cost = L * (sqrt(p_target) - sqrt(p0_true))^2
        3. Geometric TWAP shift:
           ln(TWAP) = ( (W - k*t)*ln(p0) + (k*t)*ln(p_target) ) / W
        """
        if p0_true <= 0 or p_target <= 0:
            raise ValueError("Prices must be strictly positive.")
        if window_seconds <= 0 or blocks_manipulated <= 0:
            raise ValueError("Window and blocks must be positive.")

        # Slippage cost to move price from p0 to p_target
        sqrt_p0 = math.sqrt(p0_true)
        sqrt_pt = math.sqrt(p_target)

        if p_target > p0_true:
            capital_in_pool = pool_liquidity_l * abs(sqrt_pt - sqrt_p0)
            initial_slippage = capital_in_pool * abs(sqrt_pt - sqrt_p0) / sqrt_p0
        else:
            capital_in_pool = pool_liquidity_l * abs(1.0 / sqrt_pt - 1.0 / sqrt_p0) * p0_true
            initial_slippage = capital_in_pool * abs(sqrt_p0 - sqrt_pt) / sqrt_pt

        # Arbitrageur leakage per block
        arbitrageur_leakage_per_block = pool_liquidity_l * ((sqrt_pt - sqrt_p0) ** 2)

        # Total cumulative cost across k blocks
        duration_manipulated = blocks_manipulated * block_time_seconds
        capital_borrow_cost = capital_in_pool * borrowing_fee_rate * blocks_manipulated
        total_leakage = arbitrageur_leakage_per_block * (blocks_manipulated - 1)
        total_cost = initial_slippage + total_leakage + capital_borrow_cost

        # Resulting TWAP
        w = float(window_seconds)
        t_m = min(w, float(duration_manipulated))
        log_twap = ((w - t_m) * math.log(p0_true) + t_m * math.log(p_target)) / w
        twap_result = math.exp(log_twap)

        is_viable = (protocol_exploit_gain > total_cost)

        return OracleManipulationResult(
            initial_price=float(p0_true),
            target_manipulated_price=float(p_target),
            time_window_seconds=int(window_seconds),
            blocks_manipulated=int(blocks_manipulated),
            pool_liquidity_l=float(pool_liquidity_l),
            single_block_slippage_cost=float(initial_slippage),
            leakage_to_arbitrageurs_per_block=float(arbitrageur_leakage_per_block),
            total_cumulative_manipulation_cost=float(total_cost),
            resulting_twap_price=float(twap_result),
            is_attack_economically_viable=bool(is_viable),
            max_borrowable_collateral_breakeven=float(total_cost)
        )


# ==============================================================================
# CLI INTERFACE FOR TESTING & INTEROPERABILITY
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 30: Quantitative Financial Engineering Architecture")
    parser.add_argument("--demo", action="store_true", help="Run comprehensive institutional analytics demo")
    args = parser.parse_args()

    if args.demo:
        print("=== 1. Malliavin Calculus Monte Carlo Greeks ===")
        malliavin_res = MalliavinGreeksEngine.calculate_greeks(
            s0=100.0, k_strike=100.0, r=0.05, sigma=0.20, t_mat=1.0, n_paths=20000, payoff_type="vanilla_call"
        )
        print(f"Vanilla Call Price: ${malliavin_res.option_price:.4f}")
        print(f"Malliavin Delta:    {malliavin_res.delta_malliavin:.4f} (Analytic: {malliavin_res.analytic_delta_benchmark:.4f})")
        print(f"Malliavin Gamma:    {malliavin_res.gamma_malliavin:.4f} (Analytic: {malliavin_res.analytic_gamma_benchmark:.4f})")

        print("\n=== 2. Double Heston & Heston 3/2 ===")
        dh_res = StochasticVolatilityAdvancedEngine.simulate_double_heston(
            s0=100.0, r=0.03, v1_0=0.02, kappa1=8.0, theta1=0.02, sigma_v1=0.3, rho1=-0.7,
            v2_0=0.02, kappa2=0.5, theta2=0.02, sigma_v2=0.1, rho2=-0.3, t_mat=0.5, n_steps=50, n_paths=1000
        )
        print(f"Double Heston Terminal Mean: ${dh_res.simulated_terminal_mean:.2f}, Feller Fast: {dh_res.feller_ratio_fast:.2f}")

        print("\n=== 3. Piterbarg Multi-Currency Collateral Discounting ===")
        quotes = [
            CollateralCurrencyQuote("USD", 0.045, 0.0, 0.0),
            CollateralCurrencyQuote("EUR", 0.032, -0.010, 0.02),
            CollateralCurrencyQuote("JPY", 0.005, -0.038, 0.04)
        ]
        pit_res = PiterbargCollateralDiscountEngine.calculate_discount_curve(1000000.0, 5.0, 0.045, quotes)
        print(f"CTD Currency: {pit_res.cheapest_to_deliver_currency}, Effective Rate: {pit_res.effective_collateral_rate:.4%}")
        print(f"CTD Option Value: {pit_res.embedded_option_value_bps:.2f} bps")

        print("\n=== 4. Smart Order Routing (SOR) ===")
        venues = [
            VenueQuote("NYSE_Lit", "lit", 50000, 100.00, 100.02, 0.0030, 2.5, 1.0),
            VenueQuote("BATS_Lit", "lit", 30000, 100.00, 100.02, -0.0015, 1.2, 1.0),
            VenueQuote("Crossfinder_Dark", "dark", 40000, 100.00, 100.01, 0.0010, 5.0, 0.65, 0.0050)
        ]
        sor_res = SmartOrderRoutingEngine.optimize_route(60000, "buy", venues, urgency_parameter=0.4)
        print(f"Routed: {sor_res.routed_allocations}, Avg Price: ${sor_res.effective_average_price:.4f}")

        print("\n=== 5. Cross-Holding / HoldCo Forensics ===")
        m_caps = [5000.0, 3000.0, 2000.0]
        c_matrix = [
            [0.0, 0.40, 0.20],
            [0.10, 0.0, 0.30],
            [0.15, 0.05, 0.0]
        ]
        cross_res = CrossHoldingHoldCoEngine.analyze_cross_holdings(m_caps, c_matrix, holdco_index=0)
        print(f"HoldCo NAV: ${cross_res.holdco_nav:.1f}M, Reported Mcap: ${cross_res.holdco_market_cap:.1f}M")
        print(f"HoldCo Discount: {cross_res.holdco_discount_percent:.2f}%, Unbundling Upside: {cross_res.activist_unbundling_upside_percent:.2f}%")

        print("\n=== 6. Uniswap TWAP Oracle Manipulation ===")
        twap_res = UniswapTwapOracleManipulationEngine.calculate_attack_cost(
            p0_true=2000.0, p_target=3000.0, window_seconds=1800, blocks_manipulated=5, pool_liquidity_l=500000.0
        )
        print(f"Cumulative Attack Cost: ${twap_res.total_cumulative_manipulation_cost:,.2f}")
        print(f"Resulting 30m TWAP: ${twap_res.resulting_twap_price:.2f}")
        print(f"Attack Viable for $500k exploit? {twap_res.is_attack_economically_viable}")


if __name__ == "__main__":
    main()
