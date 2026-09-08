"""Automated pytest suite for Phase 29: Quantitative Financial Engineering.

Tests:
1. Margrabe (1978) Exchange Options & Kirk (1995) Spread Options
2. Basel III/IV FRTB Expected Shortfall & PLA Eligibility Tests
3. FAVAR Macro Factor Extraction & Dynamic Factor Nowcasting
4. Cross-Asset Market Impact Matrix & Kyle-Back Insider Trading Equilibrium
5. Distressed Debt Enterprise Value Waterfall, Fulcrum Security & Section 363 Auction
6. Layer-2 Rollup Economics, EIP-4844 Blob Space Pricing & Sequencer Margin
"""

from pathlib import Path
import sys
import math
import pytest
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from margrabe_frtb_favar_kyle_fulcrum_rollup import (
    MargrabeKirkSpreadEngine,
    FRTBMarketRiskEngine,
    FAVARNowcastingEngine,
    CrossAssetImpactKyleEngine,
    DistressedDebtFulcrumEngine,
    RollupEconomicsBlobEngine,
    _norm_cdf,
    _norm_pdf,
)


# ==============================================================================
# 1. MARGRABE & KIRK SPREAD OPTION TESTS
# ==============================================================================

def test_margrabe_exchange_option_properties():
    """Verify Margrabe exchange option pricing, delta signs and volatility spread."""
    res = MargrabeKirkSpreadEngine.price_margrabe_exchange(
        s1=100.0, s2=90.0, q1=0.02, q2=0.01, sigma1=0.25, sigma2=0.20, rho=0.5, t_mat=1.0
    )

    assert res.option_price > 0.0
    assert res.volatility_spread > 0.0
    # Effective spread vol: sqrt(0.25^2 + 0.20^2 - 2*0.5*0.25*0.20) = sqrt(0.0625 + 0.04 - 0.05) = sqrt(0.0525) ~ 0.2291
    assert pytest.approx(res.volatility_spread, rel=1e-3) == math.sqrt(0.25**2 + 0.20**2 - 2 * 0.5 * 0.25 * 0.20)
    # Long asset 1 delta must be positive, short asset 2 delta must be negative
    assert res.delta_asset1 > 0.0
    assert res.delta_asset2 < 0.0
    assert res.ratio_s1_s2 == pytest.approx(100.0 / 90.0)


def test_margrabe_zero_volatility_identity():
    """When both volatilities are identical and correlation is 1, spread vol is 0."""
    res = MargrabeKirkSpreadEngine.price_margrabe_exchange(
        s1=110.0, s2=100.0, q1=0.0, q2=0.0, sigma1=0.20, sigma2=0.20, rho=1.0, t_mat=1.0
    )
    # Price should be exactly S1 - S2 = 10.0
    assert pytest.approx(res.option_price, abs=1e-3) == 10.0


def test_kirk_spread_option_spark_spread():
    """Verify Kirk approximation for energy/commodity spark spread with non-zero strike."""
    res = MargrabeKirkSpreadEngine.price_kirk_spread(
        s1=65.0, s2=30.0, strike_k=5.0, r=0.04, sigma1=0.35, sigma2=0.25, rho=0.40, t_mat=0.5, a_ratio=1.5
    )

    # Intrinsic value: max(65 - 1.5*30 - 5, 0) = max(65 - 45 - 5, 0) = 15.0
    assert res.intrinsic_value == 15.0
    # Option price must exceed or equal intrinsic value
    assert res.option_price >= res.intrinsic_value
    assert res.effective_volatility > 0.0
    assert res.delta_asset1 > 0.0
    assert res.delta_asset2 < 0.0


# ==============================================================================
# 2. BASEL III/IV FRTB MARKET RISK TESTS
# ==============================================================================

def test_frtb_liquidity_adjusted_expected_shortfall():
    """Verify 97.5% Expected Shortfall across Basel liquidity horizons."""
    np.random.seed(101)
    returns_10d = np.random.normal(0.001, 0.02, 500)

    res = FRTBMarketRiskEngine.calculate_liquidity_adjusted_es(returns_10d, alpha=0.975)

    assert res.unscaled_es_97_5 > 0.0
    assert res.liquidity_adjusted_es > res.unscaled_es_97_5
    assert "LH_10d" in res.horizon_contributions
    assert "LH_120d" in res.horizon_contributions
    assert res.var_99 > 0.0
    # ES is systematically greater than or equal to tail quantile
    assert res.unscaled_es_97_5 >= res.var_99 * 0.8


def test_frtb_desk_pla_eligibility():
    """Verify P&L Attribution test: passes when RTPL and HPL closely correlate."""
    np.random.seed(42)
    n = 100
    hpl = np.random.normal(0, 100_000, n)
    # Well aligned RTPL with slight noise
    rtpl_good = hpl + np.random.normal(0, 10_000, n)
    # Poorly aligned RTPL
    rtpl_bad = np.random.normal(0, 100_000, n)

    summary_good = FRTBMarketRiskEngine.evaluate_frtb_desk_capital(
        liq_adj_es=500_000.0, nmrf_stresses=[120_000.0, 80_000.0],
        rtpl_series=rtpl_good, hpl_series=hpl
    )
    assert summary_good.pla_test_passed is True
    assert summary_good.pla_spearman_corr >= 0.80
    assert summary_good.pla_ks_stat <= 0.09
    assert summary_good.total_market_risk_capital > 0.0

    summary_bad = FRTBMarketRiskEngine.evaluate_frtb_desk_capital(
        liq_adj_es=500_000.0, nmrf_stresses=[120_000.0, 80_000.0],
        rtpl_series=rtpl_bad, hpl_series=hpl
    )
    assert summary_bad.pla_test_passed is False
    # Capital charge is penalized when failing PLA test
    assert summary_bad.total_market_risk_capital > summary_good.total_market_risk_capital


# ==============================================================================
# 3. FAVAR & MACRO NOWCASTING TESTS
# ==============================================================================

def test_favar_dynamic_factor_extraction():
    """Verify Factor-Augmented VAR dimension reduction and policy betas."""
    np.random.seed(202)
    t_len, n_vars = 120, 25
    latent_f = np.random.normal(0, 1, (t_len, 3))
    loadings = np.random.normal(0, 1, (3, n_vars))
    panel = latent_f @ loadings + np.random.normal(0, 0.3, (t_len, n_vars))
    policy_rate = 0.05 + 0.01 * latent_f[:, 0] + np.random.normal(0, 0.005, t_len)

    res = FAVARNowcastingEngine.extract_favar_factors(panel, policy_rate, n_factors=3)

    assert res.factors.shape == (t_len, 3)
    assert res.factor_loadings.shape == (n_vars, 3)
    assert len(res.explained_variance_ratio) == 3
    assert res.explained_variance_ratio[0] >= res.explained_variance_ratio[1]
    assert len(res.policy_beta) == n_vars
    assert 0.0 <= res.r_squared_avg <= 1.0


def test_nowcasting_news_decomposition():
    """Verify DFM incoming data surprise revisions and 95% confidence band."""
    indicators = {
        "industrial_production": (1.8, 1.2, 0.25),   # +0.6 surprise * 0.25 = +0.15%
        "retail_sales": (0.5, 0.8, 0.20),            # -0.3 surprise * 0.20 = -0.06%
        "pmi_manufacturing": (52.0, 50.0, 0.05),     # +2.0 surprise * 0.05 = +0.10%
    }
    res = FAVARNowcastingEngine.compute_nowcast(base_gdp_growth=2.0, monthly_indicators=indicators)

    # Net surprise = 0.15 - 0.06 + 0.10 = +0.19% -> Nowcast = 2.19%
    assert pytest.approx(res.nowcast_current_quarter, rel=1e-3) == 2.19
    assert res.prior_quarter_benchmark == 2.0
    assert res.confidence_interval_95[0] < res.nowcast_current_quarter < res.confidence_interval_95[1]


# ==============================================================================
# 4. CROSS-ASSET MARKET IMPACT & KYLE-BACK TESTS
# ==============================================================================

def test_cross_asset_impact_manipulation_check():
    """Verify Gatheral & Schied symmetry condition detects price manipulation."""
    # Arbitrage-free symmetric positive-definite impact matrix
    lambda_sym = np.array([
        [0.0010, 0.0004],
        [0.0004, 0.0008]
    ])
    vols = np.array([50000.0, 30000.0])

    res_sym = CrossAssetImpactKyleEngine.analyze_cross_asset_impact(lambda_sym, vols)
    assert res_sym.is_arbitrage_free is True
    assert res_sym.asymmetry_norm < 1e-6
    assert len(res_sym.total_execution_impact) == 2

    # Asymmetric impact matrix (allows round-trip arbitrage)
    lambda_asym = np.array([
        [0.0010, 0.0008],
        [0.0001, 0.0008]
    ])
    res_asym = CrossAssetImpactKyleEngine.analyze_cross_asset_impact(lambda_asym, vols)
    assert res_asym.is_arbitrage_free is False
    assert res_asym.asymmetry_norm > 1e-4


def test_kyle_back_insider_trading_equilibrium():
    """Verify Kyle-Back continuous-time market depth and insider profit."""
    res = CrossAssetImpactKyleEngine.compute_kyle_back_equilibrium(
        fundamental_value=120.0,
        current_price=100.0,
        noise_trader_vol=5000.0,
        time_to_horizon=0.5,
        prior_variance=400.0
    )

    assert res.insider_trading_speed > 0.0
    assert res.market_depth_lambda > 0.0
    assert res.terminal_expected_profit > 0.0
    assert res.equilibrium_efficiency == 1.0


# ==============================================================================
# 5. DISTRESSED DEBT FULCRUM & SECTION 363 TESTS
# ==============================================================================

def test_distressed_waterfall_and_fulcrum_identification():
    """Verify Enterprise Value allocation across priority tranches and fulcrum discovery."""
    tranches = [
        ("1st Lien Secured Bank Debt", 1, 300_000_000.0),
        ("2nd Lien Senior Notes", 2, 250_000_000.0),
        ("Senior Unsecured Notes", 3, 200_000_000.0),
        ("Subordinated Debentures", 4, 150_000_000.0)
    ]

    # EV = $450M: 1st Lien gets $300M (100%), 2nd Lien gets remaining $150M of $250M (60% coverage) -> FULCRUM!
    # Junior tranches get 0%. Existing equity is wiped out.
    res = DistressedDebtFulcrumEngine.evaluate_fulcrum_waterfall(450_000_000.0, tranches)

    assert res.fulcrum_tranche_name == "2nd Lien Senior Notes"
    assert pytest.approx(res.fulcrum_coverage_ratio, rel=1e-3) == 0.60
    assert res.senior_recovery_rate == 1.0
    assert res.junior_unsecured_recovery_rate == 0.0
    assert res.existing_equity_wiped_out is True


def test_section_363_stalking_horse_auction():
    """Verify Section 363 bankruptcy auction with break-up fee and overbids."""
    res = DistressedDebtFulcrumEngine.model_section_363_sale(
        stalking_horse_bid=100_000_000.0,
        break_up_fee_pct=0.03,
        expense_reimbursement=1_000_000.0,
        auction_rounds=3,
        min_overbid_step=2_500_000.0
    )

    assert res.break_up_fee == 3_000_000.0
    assert res.expense_reimbursement == 1_000_000.0
    assert res.winning_bid_value > res.stalking_horse_bid
    assert res.net_proceeds_to_estate > res.stalking_horse_bid


# ==============================================================================
# 6. LAYER-2 ROLLUP ECONOMICS & EIP-4844 TESTS
# ==============================================================================

def test_eip4844_blob_fee_dynamics():
    """Verify EIP-4844 exponential blob fee increases when usage exceeds target."""
    # When block contains 5 blobs (target=3), fee must increase
    res_high = RollupEconomicsBlobEngine.calculate_eip4844_blob_fee(
        current_blob_base_fee_wei=100_000_000.0, actual_blobs_in_block=5, target_blobs_per_block=3
    )
    assert res_high.fee_percentage_change > 0.0
    assert res_high.next_blob_base_fee_wei > 100_000_000.0

    # When block contains 1 blob (target=3), fee must decrease
    res_low = RollupEconomicsBlobEngine.calculate_eip4844_blob_fee(
        current_blob_base_fee_wei=100_000_000.0, actual_blobs_in_block=1, target_blobs_per_block=3
    )
    assert res_low.fee_percentage_change < 0.0
    assert res_low.next_blob_base_fee_wei < 100_000_000.0


def test_rollup_operating_margin_and_calldata_savings():
    """Verify Rollup profitability equation and EIP-4844 cost reduction."""
    res = RollupEconomicsBlobEngine.analyze_rollup_margin(
        l2_tx_count=200_000,
        avg_l2_tx_fee_eth=0.00005,  # 10 ETH revenue
        mev_revenue_eth=2.0,        # 2 ETH MEV -> Total Rev = 12 ETH
        blobs_used=50,
        blob_base_fee_gwei=1.0,
        l1_execution_gas_eth=1.5,
        zk_proof_cost_eth=0.5
    )

    assert res.l2_total_revenue_eth == 12.0
    assert res.l1_total_cost_eth < res.l2_total_revenue_eth
    assert res.net_operating_profit_eth > 0.0
    assert res.operating_profit_margin > 0.50
    assert res.da_cost_savings_vs_calldata_pct > 80.0
    assert res.sequencer_bankruptcy_risk is False
