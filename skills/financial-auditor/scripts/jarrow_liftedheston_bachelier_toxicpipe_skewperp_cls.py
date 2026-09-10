"""Phase 31: Quantitative Financial Engineering & Institutional Risk Architecture.

Core Pillars:
1. Jarrow-Yildirim (2003) Inflation Derivatives & Real/Nominal Curve Engine (Foreign Currency Analogy, ZCIS, YoY, Cap/Floor)
2. Lifted Heston Multi-Factor Volatility Engine (Abi Jaber, El Euch & Rosenbaum 2019 Markovian rational lifting of rough Heston)
3. Louis Bachelier (1900) Normal Volatility & Negative Asset/Yield Pricing Engine (WTI negative prices, normal Greeks, implied vol solver)
4. Toxic Convertible PIPE & Death Spiral Arbitrage Forensic Engine (Floating conversion discount, reflexive dilution, short-selling trap)
5. Perpetual DEX Skew Funding Physics & Pool Counterparty Risk Engine (GMX/Synthetix pool delta exposure, velocity skew rate, insolvency stress)
6. CLS Settlement Risk, Multilateral Netting Algebra & FX Triangular Arbitrage Engine (Herstatt risk, PvP netting efficiency, cross-currency loops)
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
# 1. JARROW-YILDIRIM (2003) ENFLASYON TÜREVLERİ & GERÇEK/NOMİNAL EĞRİ MOTORU
# ==============================================================================

@dataclass
class ZCISResult:
    maturity: float
    nominal_discount_factor: float
    real_discount_factor: float
    breakeven_inflation_rate: float
    fair_zcis_rate: float
    expected_cpi_index: float
    inflation_risk_premium_estimate: float


@dataclass
class InflationCapFloorResult:
    maturity: float
    strike_rate: float
    caplet_price: float
    floorlet_price: float
    cpi_forward: float
    normal_implied_vol: float
    put_call_parity_diff: float


class JarrowYildirimEngine:
    """
    Jarrow & Yildirim (2003) Inflation Derivatives Pricing Engine.
    Uses the foreign-currency analogy (HJM framework):
    - Real economy is treated as the 'foreign' economy.
    - Nominal economy is treated as the 'domestic' economy.
    - CPI Index I(t) is treated as the 'exchange rate' converting real goods to nominal money.
    """

    @staticmethod
    def price_zero_coupon_inflation_swap(
        cpi_0: float,
        nominal_zero_rate: float,
        real_zero_rate: float,
        maturity: float,
        survey_expected_inflation: Optional[float] = None
    ) -> ZCISResult:
        """
        Prices a Zero-Coupon Inflation Swap (ZCIS).
        ZCIS cash flow at maturity T: (I(T) / I(0) - 1) vs ((1 + K_ZCIS)^T - 1).
        Under no-arbitrage: P_r(0, T) = P_n(0, T) * (1 + K_ZCIS)^T.
        Hence K_ZCIS = (P_r(0, T) / P_n(0, T))^(1/T) - 1.
        """
        if cpi_0 <= 0 or maturity <= 0:
            raise ValueError("cpi_0 and maturity must be strictly positive.")

        p_n = math.exp(-nominal_zero_rate * maturity)
        p_r = math.exp(-real_zero_rate * maturity)

        # Fair ZCIS compounded rate
        fair_zcis = (p_r / p_n) ** (1.0 / maturity) - 1.0

        # Breakeven inflation rate (continuous approximation)
        beir = nominal_zero_rate - real_zero_rate

        # Expected CPI forward level
        cpi_fwd = cpi_0 * (p_r / p_n)

        # Inflation Risk Premium (ERP)
        erp = 0.0
        if survey_expected_inflation is not None:
            erp = beir - survey_expected_inflation

        return ZCISResult(
            maturity=maturity,
            nominal_discount_factor=p_n,
            real_discount_factor=p_r,
            breakeven_inflation_rate=beir,
            fair_zcis_rate=fair_zcis,
            expected_cpi_index=cpi_fwd,
            inflation_risk_premium_estimate=erp
        )

    @staticmethod
    def price_inflation_cap_floor(
        cpi_0: float,
        nominal_rate: float,
        real_rate: float,
        sigma_inflation: float,
        strike_rate: float,
        maturity: float
    ) -> InflationCapFloorResult:
        """
        Prices Inflation Caplet and Floorlet on cumulative inflation:
        Payoff = max(I(T)/I(0) - (1+K)^T, 0) for Caplet.
        Uses Black-76 formulation under the T-forward nominal measure.
        """
        if cpi_0 <= 0 or maturity <= 0 or sigma_inflation <= 0:
            raise ValueError("cpi_0, maturity, and sigma_inflation must be strictly positive.")

        p_n = math.exp(-nominal_rate * maturity)
        p_r = math.exp(-real_rate * maturity)

        # Forward index ratio F = I_T / I_0
        fwd_ratio = p_r / p_n
        k_ratio = (1.0 + strike_rate) ** maturity

        vol_sqrt_t = sigma_inflation * math.sqrt(maturity)
        d1 = (math.log(fwd_ratio / k_ratio) + 0.5 * vol_sqrt_t * vol_sqrt_t) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t

        caplet = p_n * (fwd_ratio * _norm_cdf(d1) - k_ratio * _norm_cdf(d2))
        floorlet = p_n * (k_ratio * _norm_cdf(-d2) - fwd_ratio * _norm_cdf(-d1))

        parity_diff = abs((caplet - floorlet) - p_n * (fwd_ratio - k_ratio))

        return InflationCapFloorResult(
            maturity=maturity,
            strike_rate=strike_rate,
            caplet_price=caplet,
            floorlet_price=floorlet,
            cpi_forward=cpi_0 * fwd_ratio,
            normal_implied_vol=sigma_inflation,
            put_call_parity_diff=parity_diff
        )


# ==============================================================================
# 2. LIFTED HESTON MODELİ & RASYONEL ÇOK FAKTÖRLÜ YAKLAŞIM MOTORU
# ==============================================================================

@dataclass
class LiftedHestonResult:
    hurst_h: float
    num_factors: int
    mean_variance: float
    variance_std: float
    short_term_skew_approx: float
    weights: List[float]
    mean_reversions: List[float]
    sample_paths: List[float]


class LiftedHestonEngine:
    """
    Lifted Heston Engine (Abi Jaber, El Euch & Rosenbaum 2019).
    Lifts non-Markovian rough Heston (H < 1/2) with singular fractional kernel K(t) = t^(H-1/2)/Gamma(H+1/2)
    to a Markovian multi-factor system using optimal geometric sum of n exponentials:
    K^n(t) = sum_{i=1}^n c_i^n * exp(-x_i^n * t).
    Solves the O(N^2) memory bottleneck while perfectly preserving rough volatility skew explosions.
    """

    @staticmethod
    def calibrate_rational_kernel(
        hurst_h: float,
        num_factors: int = 15,
        t_max: float = 2.0,
        r_base: float = 2.5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calibrates geometric nodes x_i and weights c_i for the rational approximation of
        the fractional kernel K(t) = t^(alpha-1) / Gamma(alpha), where alpha = H + 1/2.
        """
        if not (0.0 < hurst_h < 0.5):
            raise ValueError("Hurst index H must be strictly in (0, 0.5) for rough volatility.")
        if num_factors < 2:
            raise ValueError("num_factors must be at least 2.")

        alpha = hurst_h + 0.5  # alpha in (0.5, 1.0)
        
        # Geometric mean reversion speeds
        x1 = 1.0 / t_max * 0.1
        x = np.array([x1 * (r_base ** i) for i in range(num_factors)])

        # Weights c_i ensuring exact integration over power-law spectrum
        gamma_alpha = math.gamma(alpha)
        gamma_2_minus_alpha = math.gamma(2.0 - alpha)
        factor = (r_base ** (1.0 - alpha) - 1.0) / (gamma_alpha * gamma_2_minus_alpha)
        c = np.array([factor * (x[i] ** (alpha - 1.0)) for i in range(num_factors)])
        
        # Normalize weights so sum matches kernel integral
        target_integral = (t_max ** alpha) / (alpha * gamma_alpha)
        approx_integral = np.sum(c * (1.0 - np.exp(-x * t_max)) / x)
        if approx_integral > 0:
            c *= (target_integral / approx_integral)

        return c, x

    @staticmethod
    def simulate_lifted_variance(
        v0: float,
        theta: float,
        nu_vol_of_vol: float,
        hurst_h: float = 0.10,
        num_factors: int = 10,
        t_mat: float = 1.0,
        n_steps: int = 252,
        seed: Optional[int] = 42
    ) -> LiftedHestonResult:
        """
        Simulates the multi-factor lifted variance process:
        V^n(t) = v0 + sum_{i=1}^n c_i U_i(t)
        dU_i(t) = (-x_i U_i(t) - lambda * V^n(t)) dt + nu * sqrt(V^n(t)) dW_t
        """
        if v0 <= 0 or theta <= 0 or nu_vol_of_vol <= 0:
            raise ValueError("v0, theta, and nu_vol_of_vol must be strictly positive.")

        c, x = LiftedHestonEngine.calibrate_rational_kernel(hurst_h, num_factors, t_mat)
        dt = t_mat / n_steps
        sqrt_dt = math.sqrt(dt)

        rng = np.random.default_rng(seed)
        u = np.zeros(num_factors)
        v_path = np.zeros(n_steps + 1)
        v_path[0] = v0

        # Mean reversion parameter
        lam = 0.5

        for step in range(1, n_steps + 1):
            curr_v = max(v_path[step - 1], 1e-6)
            sqrt_v = math.sqrt(curr_v)
            dw = rng.standard_normal() * sqrt_dt

            # Vectorized multi-factor update (Euler-Maruyama with absorption)
            du = (-x * u - lam * (curr_v - theta)) * dt + nu_vol_of_vol * sqrt_v * dw
            u += du
            # Lifted variance is the weighted sum
            next_v = theta + np.sum(c * u)
            v_path[step] = max(next_v, 1e-6)

        # Rough short-term skew theoretical scaling: S(T) ~ T^(H - 0.5)
        skew_scaling = (0.01) ** (hurst_h - 0.5)

        return LiftedHestonResult(
            hurst_h=hurst_h,
            num_factors=num_factors,
            mean_variance=float(np.mean(v_path)),
            variance_std=float(np.std(v_path)),
            short_term_skew_approx=float(skew_scaling),
            weights=[float(val) for val in c],
            mean_reversions=[float(val) for val in x],
            sample_paths=[float(val) for val in v_path[:10]]
        )


# ==============================================================================
# 3. LOUIS BACHELIER (1900) NORMAL VOLATİLİTE & NEGATİF FİYAT/FAİZ MOTORU
# ==============================================================================

@dataclass
class BachelierPricingResult:
    forward_price: float
    strike: float
    call_price: float
    put_call_parity_put_price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    is_negative_underlying: bool
    black_implied_vol_atm_approx: Optional[float]


class BachelierPricingEngine:
    """
    Louis Bachelier (1900) Arithmetic Brownian Motion & Normal Volatility Engine.
    Unlike Black-76/Black-Scholes (which crashes on negative prices), Bachelier supports:
    - Negative underlying commodity prices (e.g. WTI Crude at -$37.63 on April 20, 2020)
    - Negative interest rates (e.g. EUR/CHF / Bund yields at -0.50%)
    - Strike prices K <= 0.
    """

    @staticmethod
    def price_normal_option(
        forward: float,
        strike: float,
        t_mat: float,
        sigma_normal: float,
        r: float = 0.0
    ) -> BachelierPricingResult:
        """
        Calculates European Call and Put under Bachelier arithmetic motion:
        dF = sigma_N * dW.
        d = (F - K) / (sigma_N * sqrt(T))
        Call = exp(-r*T) * [ (F - K)*Phi(d) + sigma_N * sqrt(T) * phi(d) ]
        Put  = exp(-r*T) * [ (K - F)*Phi(-d) + sigma_N * sqrt(T) * phi(d) ]
        """
        if t_mat <= 0 or sigma_normal <= 0:
            raise ValueError("t_mat and sigma_normal must be strictly positive.")

        disc = math.exp(-r * t_mat)
        sqrt_t = math.sqrt(t_mat)
        sigma_sqrt_t = sigma_normal * sqrt_t

        diff = forward - strike
        d = diff / sigma_sqrt_t

        nd = _norm_cdf(d)
        npd = _norm_pdf(d)

        call_price = disc * (diff * nd + sigma_sqrt_t * npd)
        put_price = disc * (-diff * _norm_cdf(-d) + sigma_sqrt_t * npd)

        # Normal Greeks
        delta = disc * nd
        gamma = disc * npd / sigma_sqrt_t
        vega = disc * sqrt_t * npd
        theta = -disc * (sigma_normal / (2.0 * sqrt_t)) * npd + r * call_price

        # ATM Black-76 equivalent approx: sigma_Black ~ sigma_Normal / F (valid when F > 0)
        black_equiv = None
        if forward > 0:
            black_equiv = sigma_normal / forward

        return BachelierPricingResult(
            forward_price=forward,
            strike=strike,
            call_price=call_price,
            put_call_parity_put_price=put_price,
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
            is_negative_underlying=(forward <= 0),
            black_implied_vol_atm_approx=black_equiv
        )

    @staticmethod
    def solve_implied_normal_vol(
        market_price: float,
        forward: float,
        strike: float,
        t_mat: float,
        r: float = 0.0,
        max_iter: int = 100,
        tol: float = 1e-7
    ) -> float:
        """
        Newton-Raphson solver for Bachelier Normal Implied Volatility.
        Extremely stable due to strictly positive and monotonic normal Vega.
        """
        if market_price <= 0 or t_mat <= 0:
            raise ValueError("market_price and t_mat must be strictly positive.")

        # Initial guess via Brenner-Subrahmanyam normal approx
        disc = math.exp(-r * t_mat)
        intrinsic = disc * max(forward - strike, 0.0)
        if market_price <= intrinsic:
            raise ValueError("Market price is below intrinsic value.")

        # Initial seed
        sigma = (market_price / disc) * math.sqrt(2.0 * math.pi / t_mat)
        if sigma <= 0:
            sigma = 1.0

        for _ in range(max_iter):
            res = BachelierPricingEngine.price_normal_option(forward, strike, t_mat, sigma, r)
            diff = res.call_price - market_price
            if abs(diff) < tol:
                return sigma
            if res.vega < 1e-12:
                break
            sigma -= diff / res.vega
            if sigma <= 1e-6:
                sigma = 1e-6

        return sigma


# ==============================================================================
# 4. TOKSİK ÖLÜM SARMALI PIPE FİNANSMANI FORENSİK MOTORU
# ==============================================================================

@dataclass
class DeathSpiralSimulationResult:
    initial_price: float
    final_price: float
    initial_shares_out: float
    final_shares_out: float
    dilution_factor: float
    is_company_bankrupt: bool
    total_short_profit: float
    steps_taken: int
    conversion_prices: List[float]


class ToxicConvertibleForensicEngine:
    """
    Forensic Engine for Toxic Convertibles / Death Spiral PIPE (Private Investment in Public Equity).
    Models predatory hedge fund short-selling against floating-rate convertible debentures:
    Conversion price P_conv = (1 - discount) * min(P_{lookback}).
    Lower price -> More shares issued -> Severe dilution -> Price collapses further -> Reflexive Death Spiral.
    """

    @staticmethod
    def simulate_death_spiral(
        debt_face_value: float,
        initial_stock_price: float,
        initial_shares_out: float,
        conversion_discount: float = 0.20,
        kyle_lambda_impact: float = 0.000005,
        short_volume_per_step: float = 20000.0,
        conversion_floor_price: Optional[float] = 0.05,
        max_steps: int = 20
    ) -> DeathSpiralSimulationResult:
        """
        Simulates the death spiral loop between short-selling and variable conversions.
        """
        if initial_stock_price <= 0 or initial_shares_out <= 0 or debt_face_value <= 0:
            raise ValueError("Stock price, shares, and debt must be positive.")
        if not (0.0 < conversion_discount < 1.0):
            raise ValueError("Conversion discount must be between 0 and 1.")

        p_curr = initial_stock_price
        shares_curr = initial_shares_out
        remaining_debt = debt_face_value
        debt_chunk_per_step = debt_face_value / max_steps
        total_short_profit = 0.0

        p_conv_history = []
        is_bankrupt = False
        steps = 0

        for step in range(max_steps):
            steps += 1
            # 1. Hedge fund shorts shares in the market, pushing price down
            price_drop = kyle_lambda_impact * short_volume_per_step
            p_curr = max(0.001, p_curr - price_drop)

            # 2. Conversion price calculated at floating discount to depressed market price
            p_conv = max(0.0005, p_curr * (1.0 - conversion_discount))
            if conversion_floor_price is not None and p_conv < conversion_floor_price:
                # Company hits floor: cannot convert, triggers default/restructuring
                is_bankrupt = True
                p_conv_history.append(p_conv)
                break

            p_conv_history.append(p_conv)

            # 3. New shares minted to cover debt conversion
            new_shares = debt_chunk_per_step / p_conv
            shares_curr += new_shares
            remaining_debt -= debt_chunk_per_step

            # 4. Hedge fund delivers newly minted cheap shares to cover short position
            # Fund shorted at p_curr + price_drop/2 on avg, converts at p_conv: locked-in spread profit
            profit_per_share = max(0.0, p_curr - p_conv)
            total_short_profit += profit_per_share * min(new_shares, short_volume_per_step)

            # Dilution impact on market valuation
            dilution_drag = (new_shares / shares_curr) * 0.5
            p_curr = max(0.001, p_curr * (1.0 - dilution_drag))

            if p_curr <= 0.01:
                is_bankrupt = True
                break

        dilution = shares_curr / initial_shares_out

        return DeathSpiralSimulationResult(
            initial_price=initial_stock_price,
            final_price=p_curr,
            initial_shares_out=initial_shares_out,
            final_shares_out=shares_curr,
            dilution_factor=dilution,
            is_company_bankrupt=is_bankrupt,
            total_short_profit=total_short_profit,
            steps_taken=steps,
            conversion_prices=p_conv_history
        )


# ==============================================================================
# 5. PERPETUAL DEX SKEW FONLAMA FİZİĞİ & LP HAVUZ KARŞI TARAF MOTORU
# ==============================================================================

@dataclass
class PerpDexPoolStatus:
    pool_total_liquidity: float
    long_open_interest: float
    short_open_interest: float
    net_pool_delta_exposure: float
    current_skew_funding_rate_hourly: float
    hourly_borrow_fee_long: float
    hourly_borrow_fee_short: float
    unrealized_trader_pnl: float
    pool_nav: float
    pool_drawdown_pct: float
    is_pool_insolvent: bool


class PerpDexPoolRiskEngine:
    """
    Perpetual DEX (GMX / Synthetix) Counterparty Pool Risk Engine.
    Models:
    - Liquidity Providers as the universal counterparty: LP Delta = -(Trader Longs - Trader Shorts).
    - Skew Funding Rate (Velocity Model): FR = (OI_long - OI_short) / Pool_Capacity * k_skew.
    - Capital Utilization Borrow Fee.
    - Extreme trader momentum run and pool insolvency stress test.
    """

    @staticmethod
    def evaluate_pool_state(
        pool_initial_liquidity: float,
        cumulative_fees_collected: float,
        long_oi: float,
        short_oi: float,
        underlying_price_change_pct: float,
        skew_sensitivity_k: float = 0.001,
        borrow_base_rate_hourly: float = 0.0001
    ) -> PerpDexPoolStatus:
        """
        Evaluates pool solvency, delta exposure, and funding rate equilibrium.
        """
        if pool_initial_liquidity <= 0:
            raise ValueError("Pool liquidity must be strictly positive.")

        # Net pool delta: if traders are net long, the pool is short (negative delta)
        net_oi = long_oi - short_oi
        pool_delta = -net_oi

        # Skew funding rate per hour (Longs pay Shorts if net_oi > 0)
        skew_ratio = net_oi / pool_initial_liquidity
        funding_rate_hourly = skew_ratio * skew_sensitivity_k

        # Borrow fee based on pool asset utilization
        util_long = min(1.0, long_oi / pool_initial_liquidity)
        util_short = min(1.0, short_oi / pool_initial_liquidity)
        borrow_fee_long = util_long * borrow_base_rate_hourly
        borrow_fee_short = util_short * borrow_base_rate_hourly

        # Trader aggregate PnL
        # Long traders gain with positive price change, short traders gain with negative
        trader_long_pnl = long_oi * underlying_price_change_pct
        trader_short_pnl = short_oi * (-underlying_price_change_pct)
        total_trader_pnl = trader_long_pnl + trader_short_pnl

        # Pool NAV = Initial Liquidity + Fees - Trader PnL
        raw_nav = pool_initial_liquidity + cumulative_fees_collected - total_trader_pnl
        pool_nav = max(0.0, raw_nav)
        drawdown_pct = min(1.0, max(0.0, (pool_initial_liquidity - pool_nav) / pool_initial_liquidity))
        is_insolvent = raw_nav <= 0.0

        return PerpDexPoolStatus(
            pool_total_liquidity=pool_initial_liquidity,
            long_open_interest=long_oi,
            short_open_interest=short_oi,
            net_pool_delta_exposure=pool_delta,
            current_skew_funding_rate_hourly=funding_rate_hourly,
            hourly_borrow_fee_long=borrow_fee_long,
            hourly_borrow_fee_short=borrow_fee_short,
            unrealized_trader_pnl=total_trader_pnl,
            pool_nav=pool_nav,
            pool_drawdown_pct=drawdown_pct,
            is_pool_insolvent=is_insolvent
        )


# ==============================================================================
# 6. CLS YERLEŞİM RİSKİ, ÇOK TARAFLI NETLEŞTİRME & FX ÜÇGEN ARBİTRAJI
# ==============================================================================

@dataclass
class MultilateralNettingResult:
    gross_settlement_volume: float
    net_funding_required: float
    netting_efficiency_pct: float
    institution_net_positions: Dict[str, float]
    is_conservation_of_money_satisfied: bool


@dataclass
class TriangularArbitrageResult:
    cross_currency_pair: str
    direct_bid: float
    direct_ask: float
    synthetic_bid: float
    synthetic_ask: float
    arbitrage_profit_bps: float
    arbitrage_direction: str  # 'Direct_Overpriced', 'Synthetic_Overpriced', or 'None'
    is_profitable_after_fees: bool


class CLSAndTriangularArbitrageEngine:
    """
    CLS (Continuous Linked Settlement) Herstatt Risk Netting & FX Triangular Arbitrage Engine.
    - Multilateral Netting: Solves bilateral obligations matrix B_ij, reducing gross funding obligations by >90%.
    - Triangular FX Arbitrage: Detects non-linear discrepancies between direct cross rates (e.g. EUR/JPY)
      and synthetic pairs (EUR/USD * USD/JPY) accounting for bid-ask spreads and transaction fees.
    """

    @staticmethod
    def calculate_multilateral_netting(
        obligations_matrix: np.ndarray,
        institution_names: List[str]
    ) -> MultilateralNettingResult:
        """
        Multilateral Netting Algebra:
        B_ij is the gross amount institution i owes to institution j.
        Gross Volume = sum_{i,j} B_ij.
        Net Position of i: N_i = sum_j B_ji - sum_j B_ij (Inflows minus Outflows).
        Net Funding Required = 0.5 * sum_i |N_i|.
        """
        if obligations_matrix.shape[0] != len(institution_names) or obligations_matrix.shape[1] != len(institution_names):
            raise ValueError("Matrix dimensions must match institution list length.")

        gross_vol = float(np.sum(obligations_matrix))
        if gross_vol == 0:
            return MultilateralNettingResult(0.0, 0.0, 0.0, {}, True)

        # Inflows to i = sum over rows (j owes i) -> column sum
        inflows = np.sum(obligations_matrix, axis=0)
        # Outflows from i = sum over columns (i owes j) -> row sum
        outflows = np.sum(obligations_matrix, axis=1)

        net_positions = inflows - outflows
        sum_net = float(np.sum(net_positions))
        conservation = abs(sum_net) < 1e-7

        total_net_funding = float(0.5 * np.sum(np.abs(net_positions)))
        efficiency = (1.0 - (total_net_funding / gross_vol)) * 100.0

        pos_dict = {name: float(net_positions[idx]) for idx, name in enumerate(institution_names)}

        return MultilateralNettingResult(
            gross_settlement_volume=gross_vol,
            net_funding_required=total_net_funding,
            netting_efficiency_pct=efficiency,
            institution_net_positions=pos_dict,
            is_conservation_of_money_satisfied=conservation
        )

    @staticmethod
    def detect_triangular_arbitrage(
        pair_a_b: Tuple[float, float],  # EUR/USD (Bid, Ask)
        pair_b_c: Tuple[float, float],  # USD/JPY (Bid, Ask)
        pair_a_c: Tuple[float, float],  # EUR/JPY (Bid, Ask)
        fee_rate_bps: float = 1.0       # Transaction fee per leg in bps
    ) -> TriangularArbitrageResult:
        """
        Triangular Arbitrage check for Currency Triplet A, B, C:
        Direct rate: A/C.
        Synthetic rate: (A/B) * (B/C).
        Path 1: Buy A/C direct (at ask), sell synthetic (Bid(A/B) * Bid(B/C)).
        Path 2: Buy synthetic (Ask(A/B) * Ask(B/C)), sell direct (at bid).
        """
        eur_usd_bid, eur_usd_ask = pair_a_b
        usd_jpy_bid, usd_jpy_ask = pair_b_c
        eur_jpy_bid, eur_jpy_ask = pair_a_c

        # Synthetic EUR/JPY
        synthetic_bid = eur_usd_bid * usd_jpy_bid
        synthetic_ask = eur_usd_ask * usd_jpy_ask

        fee_mult = (1.0 - (fee_rate_bps * 1e-4)) ** 3

        # Check Path 1: Direct is cheaper than synthetic bid
        # Buy direct at eur_jpy_ask, convert through USD to sell at synthetic_bid
        profit_path1_bps = ((synthetic_bid / eur_jpy_ask) * fee_mult - 1.0) * 10000.0

        # Check Path 2: Direct bid is higher than synthetic ask
        # Sell direct at eur_jpy_bid, buy synthetic at synthetic_ask
        profit_path2_bps = ((eur_jpy_bid / synthetic_ask) * fee_mult - 1.0) * 10000.0

        direction = "None"
        max_profit = 0.0

        if profit_path1_bps > 0 and profit_path1_bps >= profit_path2_bps:
            direction = "Synthetic_Overpriced"
            max_profit = profit_path1_bps
        elif profit_path2_bps > 0 and profit_path2_bps > profit_path1_bps:
            direction = "Direct_Overpriced"
            max_profit = profit_path2_bps

        return TriangularArbitrageResult(
            cross_currency_pair="EUR/JPY",
            direct_bid=eur_jpy_bid,
            direct_ask=eur_jpy_ask,
            synthetic_bid=synthetic_bid,
            synthetic_ask=synthetic_ask,
            arbitrage_profit_bps=max(0.0, max_profit),
            arbitrage_direction=direction,
            is_profitable_after_fees=(max_profit > 0.0)
        )


# ==============================================================================
# CLI DEMO INTERFACE
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 31 Quantitative Finance Engine CLI")
    parser.add_argument("--demo", action="store_true", help="Run all 6 engine demonstrations")
    args = parser.parse_args()

    if args.demo:
        print("=== Phase 31: Quantitative Financial Architecture Demo ===")
        # 1. Jarrow-Yildirim
        jy = JarrowYildirimEngine.price_zero_coupon_inflation_swap(100.0, 0.045, 0.020, 5.0, 0.023)
        print(f"[1] Jarrow-Yildirim: BEIR={jy.breakeven_inflation_rate*100:.2f}%, Fair ZCIS={jy.fair_zcis_rate*100:.2f}%, ERP={jy.inflation_risk_premium_estimate*100:.2f}%")

        # 2. Lifted Heston
        lh = LiftedHestonEngine.simulate_lifted_variance(0.04, 0.04, 0.3, hurst_h=0.10, num_factors=10)
        print(f"[2] Lifted Heston: Mean Var={lh.mean_variance:.4f}, Skew Scaling={lh.short_term_skew_approx:.2f}")

        # 3. Bachelier
        bach = BachelierPricingEngine.price_normal_option(-10.0, 0.0, 0.25, 20.0, 0.01)
        print(f"[3] Bachelier (Negative WTI): Call={bach.call_price:.3f}, Put={bach.put_call_parity_put_price:.3f}, Delta={bach.delta:.3f}")

        # 4. Toxic PIPE
        pipe = ToxicConvertibleForensicEngine.simulate_death_spiral(1000000.0, 10.0, 1000000.0)
        print(f"[4] Toxic PIPE: Final P={pipe.final_price:.3f}, Dilution={pipe.dilution_factor:.1f}x, Bankrupt={pipe.is_company_bankrupt}")

        # 5. Perp DEX Pool
        pool = PerpDexPoolRiskEngine.evaluate_pool_state(10000000.0, 500000.0, 8000000.0, 2000000.0, 0.15)
        print(f"[5] Perp DEX: Pool Delta={pool.net_pool_delta_exposure:.0f}, Funding Rate/hr={pool.current_skew_funding_rate_hourly*100:.4f}%, NAV=${pool.pool_nav:.0f}")

        # 6. CLS Netting
        mat = np.array([[0, 50, 30], [20, 0, 70], [40, 10, 0]], dtype=float)
        cls_res = CLSAndTriangularArbitrageEngine.calculate_multilateral_netting(mat, ["Bank A", "Bank B", "Bank C"])
        print(f"[6] CLS Netting: Gross=${cls_res.gross_settlement_volume}M, Net=${cls_res.net_funding_required}M, Efficiency={cls_res.netting_efficiency_pct:.1f}%")


if __name__ == "__main__":
    main()
