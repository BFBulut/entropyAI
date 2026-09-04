"""Automated pytest test suite for ALM, Project Finance, Merger Arbitrage and GARCH Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from alm_project_arbitrage import (
    calculate_duration_gap_eve_impact,
    calculate_project_dscr,
    calculate_merger_arbitrage_odds,
    calculate_garch_next_variance
)


def test_duration_gap_eve_impact():
    # Assets = 1000M, Liab = 900M, Equity = 100M (Equity multiplier = 10x)
    # Asset duration = 6.0 years, Liab duration = 1.0 year
    # Leverage = 900/1000 = 0.90
    # Duration Gap = 6.0 - (0.90 * 1.0) = 5.10 years
    # Yield shock = +200 bps (+0.02)
    # EVE change = - (5.10 * 10) * 0.02 = -1.02 (-102% - Equity wiped out!)
    res = calculate_duration_gap_eve_impact(
        total_assets=1000.0,
        total_liabilities=900.0,
        asset_duration=6.0,
        liability_duration=1.0,
        yield_shock_bps=200.0
    )
    assert res["duration_gap_years"] == 5.1
    assert res["eve_pct_change"] == -102.0
    assert "KRİTİK İFLAS RİSKİ" in res["alm_risk_tier"]

    # Balanced ALM bank: Da = 2.0, Dl = 1.5, shock = 50 bps
    bal_res = calculate_duration_gap_eve_impact(1000.0, 800.0, 2.0, 1.5, 50.0)
    assert abs(bal_res["eve_pct_change"]) < 10.0
    assert "KONTROL ALTINDA" in bal_res["alm_risk_tier"]

    # Invalid input
    err = calculate_duration_gap_eve_impact(100, 150, 2, 1)
    assert "error" in err


def test_project_dscr():
    # CFADS = 150M, Principal = 70M, Interest = 30M -> Total DS = 100M
    # DSCR = 150 / 100 = 1.50x (Strong)
    res = calculate_project_dscr(cfads=150.0, principal_repayment=70.0, interest_payment=30.0)
    assert res["dscr"] == 1.5
    assert "GÜÇLÜ" in res["covenant_status"]

    # Covenant breach: CFADS = 105M, DS = 100M -> DSCR = 1.05x
    breach_res = calculate_project_dscr(cfads=105.0, principal_repayment=70.0, interest_payment=30.0)
    assert breach_res["dscr"] == 1.05
    assert "SÖZLEŞME İHLALİ" in breach_res["covenant_status"]

    # Default: CFADS = 80M, DS = 100M -> DSCR = 0.80x
    def_res = calculate_project_dscr(cfads=80.0, principal_repayment=70.0, interest_payment=30.0)
    assert def_res["dscr"] == 0.80
    assert "TEMERRÜT" in def_res["covenant_status"]

    # Invalid
    err = calculate_project_dscr(100, 0, 0)
    assert "error" in err


def test_merger_arbitrage_odds():
    # Offer = 100 TL, Unaffected = 70 TL, Spot = 95 TL
    # Denom = 100 - 70 = 30. Spot - Unaffected = 95 - 70 = 25.
    # Implied prob = 25 / 30 = 83.3%
    # Deal spread = 100 - 95 = 5 TL (Gross spread = 5/95 = 5.26%)
    res = calculate_merger_arbitrage_odds(spot_price=95.0, offer_price=100.0, unaffected_price=70.0)
    assert res["deal_spread"] == 5.0
    assert res["gross_arbitrage_spread_pct"] == 5.26
    assert res["market_implied_success_prob_pct"] == 83.3
    assert "Orta Seviye" in res["antitrust_risk_verdict"]

    # High closing probability: Spot = 98 TL -> Prob = 28 / 30 = 93.3%
    safe_res = calculate_merger_arbitrage_odds(98.0, 100.0, 70.0)
    assert safe_res["market_implied_success_prob_pct"] == 93.3
    assert "Yüksek Kapanma Olasılığı" in safe_res["antitrust_risk_verdict"]

    # Invalid input
    err = calculate_merger_arbitrage_odds(50.0, 100.0, 70.0)
    assert "error" in err


def test_garch_next_variance():
    # Omega = 0.00001, Alpha = 0.10, Beta = 0.85 (Persistence = 0.95)
    # Prev variance = 0.0004 (2% daily vol), Prev shock = 0.03 (+3% unexpected return)
    # Next var = 0.00001 + 0.10 * (0.0009) + 0.85 * (0.0004) = 0.00001 + 0.00009 + 0.00034 = 0.00044
    res = calculate_garch_next_variance(
        omega=0.00001,
        alpha=0.10,
        beta=0.85,
        prev_variance=0.0004,
        prev_residual_shock=0.03
    )
    assert res["persistence_factor"] == 0.95
    assert res["next_period_conditional_variance"] == 0.00044
    assert res["next_period_conditional_volatility_pct"] > 2.0
    assert "Durağan" in res["process_stability"]
