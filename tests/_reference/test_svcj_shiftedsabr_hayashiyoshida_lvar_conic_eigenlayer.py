"""Unit and Integration Tests for Phase 30: Quantitative Financial Engineering.

Verifies:
1. Bates & Eraker-Johannes-Polson (2003) SVCJ Engine & Put-Call Parity
2. Shifted-SABR & Normal (Bachelier) SABR under Negative Rates & Greeks
3. Hayashi-Yoshida (2005) Asynchronous Covariance & Millisecond Lead-Lag Detection
4. Bangia-Jarrow Liquidity-Adjusted VaR & Expected Shortfall (L-VaR & L-ES)
5. Madan-Schoutens (2008) Conic Finance Two-Price Economy (Choquet & Wang/MinMaxVar)
6. EigenLayer Cryptoeconomic Re-Staking, Correlated Slashing & LRT De-Peg Arbitrage
7. Boundary conditions, input validation, and mathematical invariants
"""

import math
import numpy as np
import pytest

from pathlib import Path
import sys
import pytest
import math
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from svcj_shiftedsabr_hayashiyoshida_lvar_conic_eigenlayer import (
    SVCJOptionEngine,
    ShiftedSABREngine,
    HayashiYoshidaEngine,
    LiquidityRiskEngine,
    ConicFinanceEngine,
    EigenLayerReStakingEngine,
    norm_cdf,
    norm_pdf,
    norm_ppf,
)


# ==============================================================================
# 1. SVCJ ENGINE & PUT-CALL PARITY TESTS
# ==============================================================================

def test_svcj_option_engine_pricing_and_moments():
    """Validates SVCJ option pricing, Put-Call parity, and moments."""
    spot = 100.0
    rate = 0.04
    dividend = 0.01
    maturity = 0.5
    strike = 100.0

    engine = SVCJOptionEngine(
        spot=spot,
        rate=rate,
        dividend=dividend,
        v0=0.04,
        kappa=2.5,
        theta=0.04,
        sigma_v=0.35,
        rho=-0.7,
        jump_intensity=0.3,
        mu_s=-0.06,
        sigma_s=0.12,
        mu_v=0.04,
        rho_j=-0.4,
    )

    # 1. Price Call and Put
    call_price = engine.price_european_option(strike=strike, maturity=maturity, is_call=True)
    put_price = engine.price_european_option(strike=strike, maturity=maturity, is_call=False)

    assert call_price > 0.0, "Call price must be strictly positive."
    assert put_price > 0.0, "Put price must be strictly positive."

    # 2. Put-Call Parity: C - P = S * exp(-q*T) - K * exp(-r*T)
    expected_parity = spot * math.exp(-dividend * maturity) - strike * math.exp(-rate * maturity)
    actual_parity = call_price - put_price
    assert math.isclose(actual_parity, expected_parity, abs_tol=1e-4), (
        f"Put-Call Parity violated: {actual_parity} vs {expected_parity}"
    )

    # 3. Test ITM / OTM monotonicity
    otm_call = engine.price_european_option(strike=120.0, maturity=maturity, is_call=True)
    itm_call = engine.price_european_option(strike=80.0, maturity=maturity, is_call=True)
    assert itm_call > call_price > otm_call, "Call prices must be monotonically decreasing with strike."

    # 4. Test moments computation
    moments = engine.compute_moments(t=maturity)
    assert moments["total_variance"] > 0.0
    assert moments["annualized_vol"] > 0.0
    assert 0.0 < moments["jump_share_pct"] < 100.0


# ==============================================================================
# 2. SHIFTED-SABR & NORMAL SABR FOR NEGATIVE RATES
# ==============================================================================

def test_shifted_sabr_negative_rates_and_bachelier():
    """Validates Shifted-SABR and Normal SABR for zero/negative forward rates."""
    # Negative forward rate scenario (e.g. EUR/CHF or JPY post-2016)
    forward = -0.005  # -50 bps
    shift = 0.03      # 300 bps shift ensures forward + shift = 250 bps > 0
    alpha = 0.006     # 60 bps normal vol
    maturity = 1.0

    engine = ShiftedSABREngine(
        forward_rate=forward,
        shift=shift,
        alpha=alpha,
        beta=0.0,  # Pure Normal / Bachelier SABR
        rho=-0.3,
        nu=0.45,
    )

    # ATM Strike (negative)
    strike_atm = forward
    strike_otm_call = 0.005  # +50 bps
    strike_otm_put = -0.015  # -150 bps

    # Normal vol must be positive
    vol_atm = engine.normal_sabr_volatility(strike=strike_atm, maturity=maturity)
    vol_call = engine.normal_sabr_volatility(strike=strike_otm_call, maturity=maturity)
    vol_put = engine.normal_sabr_volatility(strike=strike_otm_put, maturity=maturity)

    assert vol_atm > 0.0
    assert vol_call > 0.0
    assert vol_put > 0.0

    # Pricing under Bachelier
    call_atm = engine.bachelier_option_price(strike=strike_atm, maturity=maturity, is_call=True)
    put_atm = engine.bachelier_option_price(strike=strike_atm, maturity=maturity, is_call=False)

    # At ATM strike (F = K), Call and Put must be equal
    assert math.isclose(call_atm, put_atm, rel_tol=1e-5)

    # Put-Call Parity in Bachelier: C - P = (F - K) * df
    call_otm = engine.bachelier_option_price(strike=strike_otm_call, maturity=maturity, is_call=True)
    put_itm = engine.bachelier_option_price(strike=strike_otm_call, maturity=maturity, is_call=False)
    assert math.isclose(call_otm - put_itm, forward - strike_otm_call, abs_tol=1e-6)

    # Shifted Black Volatility
    shifted_vol = engine.shifted_black_volatility(strike=0.0, maturity=maturity)
    assert shifted_vol > 0.0


# ==============================================================================
# 3. HAYASHI-YOSHIDA ASYNCHRONOUS COVARIANCE & LEAD-LAG
# ==============================================================================

def test_hayashi_yoshida_asynchronous_covariance_and_lead_lag():
    """Validates Hayashi-Yoshida non-synchronous covariance and millisecond lead-lag detection."""
    np.random.seed(42)
    n_ticks = 200

    # Generate asynchronous irregular timestamps
    dt_x = np.random.exponential(scale=0.05, size=n_ticks)
    times_x = np.cumsum(dt_x)

    # Asset X is a random walk
    innovations_x = np.random.normal(scale=0.1, size=n_ticks)
    prices_x = 100.0 + np.cumsum(innovations_x)

    # Asset Y is an asynchronous series that lags X by true_lag = 0.25 seconds
    true_lag = 0.25
    dt_y = np.random.exponential(scale=0.06, size=n_ticks)
    times_y = np.cumsum(dt_y)

    # Y prices sample X with lag plus small idiosyncratic noise
    prices_y = np.interp(times_y - true_lag, times_x, prices_x) + np.random.normal(scale=0.02, size=n_ticks)

    engine = HayashiYoshidaEngine(times_x, prices_x, times_y, prices_y)

    # 1. Compute zero-lag HY Covariance
    cov_zero, rv_x, rv_y, overlaps = engine.compute_hy_covariance(time_shift_y=0.0)
    assert rv_x > 0.0 and rv_y > 0.0
    assert overlaps > 0
    assert not math.isnan(cov_zero)

    # 2. Detect optimal lead-lag
    result = engine.detect_lead_lag(max_lag=1.0, lag_steps=41)
    assert result.num_overlapping_pairs > 0
    assert abs(result.correlation) <= 1.0

    # Optimal lag should be positive around true_lag (Asset X leads Asset Y)
    assert result.optimal_lag > 0.0, f"Expected Asset X to lead, but got lag {result.optimal_lag}"
    assert "Asset X leads Asset Y" in result.lead_asset


# ==============================================================================
# 4. LIQUIDITY-ADJUSTED VaR & EXPECTED SHORTFALL (L-VaR & L-ES)
# ==============================================================================

def test_liquidity_adjusted_var_and_expected_shortfall():
    """Validates Bangia-Jarrow Liquidity-Adjusted VaR and Expected Shortfall."""
    position = 20_000_000.0
    shares = 200_000.0
    daily_vol = 1_000_000.0

    engine = LiquidityRiskEngine(
        position_value=position,
        order_shares=shares,
        mid_price=100.0,
        daily_volume=daily_vol,
        daily_volatility=0.025,
        mean_spread_pct=0.003,
        vol_spread_pct=0.0015,
        impact_gamma=0.20,
    )

    res_99 = engine.calculate_l_var(confidence_level=0.99, holding_period_days=1.0)
    res_95 = engine.calculate_l_var(confidence_level=0.95, holding_period_days=1.0)

    # Pure VaR < Total L-VaR
    assert res_99.total_l_var > res_99.pure_var
    assert res_99.exogenous_l_cost > 0.0
    assert res_99.endogenous_l_cost > 0.0

    # 99% VaR must be higher than 95% VaR
    assert res_99.total_l_var > res_95.total_l_var

    # Expected Shortfall must exceed VaR
    assert res_99.l_expected_shortfall > res_99.total_l_var
    assert res_99.liquidity_premium_pct > 0.0


# ==============================================================================
# 5. CONIC FINANCE TWO-PRICE ECONOMY
# ==============================================================================

def test_conic_finance_two_price_economy():
    """Validates Two-Price economy under Choquet expectation with Wang & MinMaxVar distortions."""
    np.random.seed(123)
    # Generate skewed asset return payoffs (e.g. short put option payoff)
    samples = np.random.normal(loc=10.0, scale=5.0, size=200)

    engine = ConicFinanceEngine(samples=samples)

    # 1. Wang Distortion
    res_wang = engine.price_cash_flow(distortion_type="wang", distortion_param=0.30)
    # Invariant: Bid <= Mid <= Ask (No Free Lunch in Conic Finance)
    assert res_wang.bid_price <= res_wang.mid_price, f"Bid {res_wang.bid_price} > Mid {res_wang.mid_price}"
    assert res_wang.ask_price >= res_wang.mid_price, f"Ask {res_wang.ask_price} < Mid {res_wang.mid_price}"
    assert res_wang.spread >= 0.0

    # 2. Parameter Sensitivity: Higher distortion param -> wider spread
    res_wang_high = engine.price_cash_flow(distortion_type="wang", distortion_param=0.60)
    assert res_wang_high.spread > res_wang.spread

    # 3. MinMaxVar Distortion
    res_minmax = engine.price_cash_flow(distortion_type="minmaxvar", distortion_param=0.25)
    assert res_minmax.bid_price <= res_minmax.mid_price <= res_minmax.ask_price
    assert res_minmax.spread >= 0.0


# ==============================================================================
# 6. EIGENLAYER RE-STAKING & LRT DE-PEG ARBITRAGE
# ==============================================================================

def test_eigenlayer_restaking_and_depeg_dynamics():
    """Validates cryptoeconomic re-staking yield, correlated slashing, and fair LRT peg discount."""
    engine = EigenLayerReStakingEngine(
        base_eth_staking_yield=0.033,
        avs_yields=[0.018, 0.022, 0.030],
        avs_allocations=[0.5, 0.3, 0.2],
        avs_slash_severities=[0.05, 0.10, 0.25],
        independent_failure_prob=0.015,
        systemic_correlated_prob=0.008,
        protocol_fee=0.10,
        unbonding_delay_days=14.0,
    )

    result = engine.evaluate_restaking_portfolio(
        opportunity_cost_rate=0.045,
        market_liquidity_factor=1.5,
    )

    # Yield hierarchy
    assert result.total_yield_apr > result.net_yield_apr
    assert result.expected_slashing_loss > 0.0

    # Unbonding delay fair pricing discount
    assert 0.0 < result.lrt_fair_ratio <= 1.0
    assert result.secondary_depeg_discount >= 0.0
    assert isinstance(result.liquidation_cascade_risk, str)


# ==============================================================================
# 7. BOUNDARY & ERROR HANDLING INVARIANTS
# ==============================================================================

def test_engine_boundary_and_validation_errors():
    """Validates parameter sanity checks and exception handling across modules."""
    # Negative spot in SVCJ
    with pytest.raises(ValueError):
        SVCJOptionEngine(spot=-10.0)

    # Invalid correlation in SVCJ
    with pytest.raises(ValueError):
        SVCJOptionEngine(rho=1.5)

    # Invalid forward + shift in Shifted SABR
    with pytest.raises(ValueError):
        ShiftedSABREngine(forward_rate=-0.05, shift=0.02, beta=0.5)

    # Mismatched lengths in Hayashi-Yoshida
    with pytest.raises(ValueError):
        HayashiYoshidaEngine(np.array([1, 2]), np.array([10]), np.array([1, 2]), np.array([10, 20]))

    # Invalid confidence level in L-VaR
    with pytest.raises(ValueError):
        eng = LiquidityRiskEngine()
        eng.calculate_l_var(confidence_level=1.2)

    # Unknown distortion in Conic Finance
    with pytest.raises(ValueError):
        c_eng = ConicFinanceEngine(np.random.normal(size=20))
        c_eng.price_cash_flow(distortion_type="nonexistent")

    # Mismatched dimensions in EigenLayer
    with pytest.raises(ValueError):
        EigenLayerReStakingEngine(avs_yields=[0.01], avs_allocations=[0.5, 0.5])
