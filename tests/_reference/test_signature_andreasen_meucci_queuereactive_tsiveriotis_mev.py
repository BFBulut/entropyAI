"""Unit and programmatic verification tests for Phase 26 Quantitative Financial Engine.

Covers:
- Path Signatures & Lead-Lag Transform (Lyons, Bayer)
- Andreasen-Huge Arbitrage-Free Volatility Interpolation
- Meucci Minimum Torsion & Effective Number of Bets (ENB)
- Huang-Lehalle-Rosenbaum Queue-Reactive LOB Dynamics
- Tsiveriotis-Fernandes Convertible Bond Decoupled Valuation & Greeks
- MEV-Boost PBS Bundle Auctions & AMM Toxic Flow Arbitrage
"""

import math
import numpy as np
from pathlib import Path
import sys
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from signature_andreasen_meucci_queuereactive_tsiveriotis_mev import (
    PathSignatureEngine,
    AndreasenHugeVolEngine,
    MeucciTorsionEngine,
    QueueReactiveLOBEngine,
    TsiveriotisFernandesConvertibleEngine,
    MEVBoostPBSEngine,
)


def test_path_signature_lead_lag_and_shuffle_identity():
    """Verify lead-lag transform, signature tensor integrals and shuffle product."""
    prices = [100.0, 102.0, 101.0, 105.0, 104.0]
    ll_path = PathSignatureEngine.lead_lag_transform(prices)

    # 2n - 1 points = 2*5 - 1 = 9 points in R^2
    assert ll_path.shape == (9, 2)
    assert ll_path[0, 0] == 100.0 and ll_path[0, 1] == 100.0
    assert ll_path[-1, 0] == 104.0 and ll_path[-1, 1] == 104.0

    sig = PathSignatureEngine.compute_signature_2d(ll_path)
    assert sig.level_0 == 1.0

    # Level 1 should match net displacement
    dx0 = 104.0 - 100.0
    dx1 = 104.0 - 100.0
    assert math.isclose(sig.level_1[0], dx0, rel_tol=1e-5)
    assert math.isclose(sig.level_1[1], dx1, rel_tol=1e-5)

    # Shuffle product identity: S^{0,1} + S^{1,0} == S^0 * S^1
    s01 = sig.level_2[0][1]
    s10 = sig.level_2[1][0]
    expected_prod = sig.level_1[0] * sig.level_1[1]
    assert math.isclose(s01 + s10, expected_prod, rel_tol=1e-4)

    # Lévy area antisymmetry
    assert math.isclose(sig.levy_areas["A_12"], -sig.levy_areas["A_21"], rel_tol=1e-6)
    # Total feature vector length: 1 + 2 + 4 = 7
    assert len(sig.total_feature_vector) == 7


def test_andreasen_huge_vol_interpolation():
    """Verify discrete Dupire implicit PDE calibration and arbitrage-free properties."""
    spot = 100.0
    rate = 0.03
    div_yield = 0.01
    expiry = 0.5
    market_strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
    market_vols = [0.28, 0.24, 0.20, 0.18, 0.19]

    dense_strikes = np.linspace(70.0, 130.0, 31)
    res = AndreasenHugeVolEngine.calibrate_and_interpolate(
        spot=spot,
        rate=rate,
        div_yield=div_yield,
        expiry=expiry,
        market_strikes=market_strikes,
        market_vols=market_vols,
        dense_strikes=dense_strikes,
    )

    # All call prices should be non-negative
    assert np.all(res.call_prices >= 0.0)

    # Monotonicity: call price must decrease with strike
    diffs = np.diff(res.call_prices)
    assert np.all(diffs <= 1e-4)

    # Implied vols should be positive and bounded
    assert np.all(res.implied_vols > 0.0)
    assert np.all(res.implied_vols < 1.0)
    assert res.is_arbitrage_free is True
    assert res.butterfly_arbitrage_count == 0


def test_meucci_minimum_torsion_and_enb():
    """Verify minimum torsion diagonalizes covariance and computes Effective Number of Bets."""
    # 3-asset covariance matrix with correlations
    cov = np.array([
        [0.04, 0.015, 0.01],
        [0.015, 0.09, 0.025],
        [0.01, 0.025, 0.16],
    ])

    torsion = MeucciTorsionEngine.compute_minimum_torsion(cov)
    assert torsion.shape == (3, 3)

    # T * cov * T' must be diagonal (off-diagonals close to zero)
    factor_cov = torsion @ cov @ torsion.T
    off_diag = factor_cov - np.diag(np.diag(factor_cov))
    assert np.max(np.abs(off_diag)) < 1e-4

    # Equal weighted portfolio
    weights_eq = np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0])
    res_eq = MeucciTorsionEngine.analyze_portfolio(weights_eq, cov)

    assert 1.0 <= res_eq.effective_number_of_bets <= 3.0
    assert math.isclose(np.sum(res_eq.factor_risk_contributions), 1.0, rel_tol=1e-5)
    assert res_eq.portfolio_volatility > 0.0

    # Concentrated portfolio on asset 1
    weights_conc = np.array([0.95, 0.025, 0.025])
    res_conc = MeucciTorsionEngine.analyze_portfolio(weights_conc, cov)
    # Concentrated portfolio has significantly lower ENB
    assert res_conc.effective_number_of_bets < res_eq.effective_number_of_bets


def test_queue_reactive_lob_dynamics():
    """Verify limit order fill probability decreases and wait time increases with queue depth."""
    queue_size = 50
    arrival_rate = 5.0
    cancel_rate_per_lot = 0.05
    market_exec_rate = 4.0
    adverse_rate = 0.10

    # Top of book (priority 1)
    res_top = QueueReactiveLOBEngine.calculate_fill_dynamics(
        queue_size=queue_size,
        order_priority=1,
        arrival_rate=arrival_rate,
        cancel_rate_per_lot=cancel_rate_per_lot,
        market_execution_rate=market_exec_rate,
        adverse_tick_rate=adverse_rate,
    )

    # Deep in queue (priority 30)
    res_deep = QueueReactiveLOBEngine.calculate_fill_dynamics(
        queue_size=queue_size,
        order_priority=30,
        arrival_rate=arrival_rate,
        cancel_rate_per_lot=cancel_rate_per_lot,
        market_execution_rate=market_exec_rate,
        adverse_tick_rate=adverse_rate,
    )

    # Top of book fills with higher probability than deep in queue
    assert res_top.fill_probability > res_deep.fill_probability
    # Expected fill time is much faster at top of book
    assert res_top.expected_fill_time < res_deep.expected_fill_time
    # Queue half-life is positive
    assert res_top.queue_half_life > 0.0
    assert res_deep.cancel_probability_before_fill > res_top.cancel_probability_before_fill


def test_tsiveriotis_fernandes_convertible_bond():
    """Verify decoupled PDE convertible bond valuation, equity/debt split, and Greeks."""
    face_value = 1000.0
    conversion_ratio = 10.0  # Parity = 10 * Spot
    coupon_rate = 0.04
    maturity = 3.0
    rf_rate = 0.03
    credit_spread = 0.02
    vol = 0.30

    # 1) Out of the money (low spot: 50 -> parity 500 < 1000)
    res_otm = TsiveriotisFernandesConvertibleEngine.price_convertible(
        spot=50.0,
        face_value=face_value,
        conversion_ratio=conversion_ratio,
        coupon_rate=coupon_rate,
        maturity=maturity,
        risk_free_rate=rf_rate,
        credit_spread=credit_spread,
        volatility=vol,
        steps=30,
    )
    # In OTM regime, debt value should dominate equity value
    assert res_otm.pure_debt_value > res_otm.equity_conversion_value
    assert res_otm.total_price > res_otm.parity
    assert res_otm.delta > 0.0

    # 2) Deep in the money (high spot: 150 -> parity 1500 > 1000)
    res_itm = TsiveriotisFernandesConvertibleEngine.price_convertible(
        spot=150.0,
        face_value=face_value,
        conversion_ratio=conversion_ratio,
        coupon_rate=coupon_rate,
        maturity=maturity,
        risk_free_rate=rf_rate,
        credit_spread=credit_spread,
        volatility=vol,
        steps=30,
    )
    # In ITM regime, equity value should dominate
    assert res_itm.equity_conversion_value > res_itm.pure_debt_value
    assert res_itm.delta > res_otm.delta  # Delta approaches conversion ratio (10)
    assert res_itm.total_price >= res_itm.parity - 1.0

    # Credit spread widening reduces bond value (CS01 > 0 represents positive dollar loss per 1 bp widening)
    assert res_otm.cs01 > 0.0


def test_mev_boost_pbs_and_amm_toxic_arbitrage():
    """Verify PBS bundle auction distribution and CFMM toxic flow extraction."""
    # AMM pool state: 1000 X, 2,000,000 Y => pool price = 2000 Y per X
    pool_x = 1000.0
    pool_y = 2_000_000.0
    ext_price_high = 2200.0  # Market moved up to 2200
    fee_rate = 0.003

    dx_out, dy_in, profit = MEVBoostPBSEngine.calculate_toxic_arbitrage_cfmm(
        pool_x=pool_x,
        pool_y=pool_y,
        ext_price=ext_price_high,
        fee_rate=fee_rate,
    )

    assert dx_out > 0.0
    assert dy_in > 0.0
    assert profit > 0.0

    # No arb when external price is within fee bounds
    dx_0, dy_0, profit_0 = MEVBoostPBSEngine.calculate_toxic_arbitrage_cfmm(
        pool_x=pool_x,
        pool_y=pool_y,
        ext_price=2000.0,
        fee_rate=0.01,
    )
    assert profit_0 == 0.0

    # PBS Auction simulation
    mev_opps = [5000.0, 12000.0, 3000.0]  # Gross MEV in block = 20,000
    pbs_res = MEVBoostPBSEngine.simulate_pbs_auction(
        gross_mev_opportunities=mev_opps,
        searcher_bid_fraction=0.85,
        builder_margin=0.05,
        pool_liquidity=5_000_000.0,
        asset_volatility=0.50,
        private_rebate_fraction=0.40,
    )

    assert pbs_res.toxic_arbitrage_extracted == 20000.0
    # Searcher keeps (1 - 0.85) = 15% = 3000
    assert math.isclose(pbs_res.searcher_net_profit, 3000.0, rel_tol=1e-5)
    # Builder bids 95% of 17000 to proposer = 16150
    assert math.isclose(pbs_res.proposer_revenue, 16150.0, rel_tol=1e-5)
    # LVR rate = 0.125 * 0.25 * 5,000,000 = 156,250
    assert math.isclose(pbs_res.lvr_instantaneous_rate, 156250.0, rel_tol=1e-5)
    # User rebate = 40% of 20000 = 8000
    assert math.isclose(pbs_res.private_pool_rebate, 8000.0, rel_tol=1e-5)
