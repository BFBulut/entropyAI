"""Automated pytest test suite for Special Situations, LBO and Commodity Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from special_situations import (
    calculate_lbo_returns,
    calculate_ma_accretion_dilution,
    calculate_crack_spread,
    calculate_guidotti_greenspan
)


def test_lbo_returns():
    # Sponsor invests 30M equity, 70M debt for 100M EV.
    # Exits at 140M EV after 5 years, pays down 40M debt (remaining debt = 30M).
    # Ending equity = 140 - 30 = 110M.
    # MOIC = 110 / 30 = 3.67x.
    # IRR = (3.6667)^(1/5) - 1 ~= 29.68%
    res = calculate_lbo_returns(
        entry_ev=100.0,
        exit_ev=140.0,
        initial_debt=70.0,
        debt_paid_down=40.0,
        initial_equity=30.0,
        holding_years=5.0
    )
    assert res["moic"] == 3.67
    assert res["irr_pct"] > 25.0
    assert res["target_met"] is True
    assert "Üst Düzey" in res["performance_verdict"]

    # Invalid input
    err = calculate_lbo_returns(100, 100, 50, 0, 0, 5)
    assert "error" in err


def test_ma_accretion_dilution():
    # Acquirer: 100M NI, 50M shares -> EPS = 2.0. Share price = 40 (P/E = 20).
    # Target: 30M NI, buys for 300M (P/E = 10).
    # Since Target P/E (10) < Acquirer P/E (20), deal MUST be accretive!
    # Shares issued = 300 / 40 = 7.5M. Total shares = 57.5M.
    # Total NI = 130M -> Pro-forma EPS = 130 / 57.5 = 2.261.
    res = calculate_ma_accretion_dilution(
        acquirer_share_price=40.0,
        acquirer_shares_out=50.0,
        acquirer_net_income=100.0,
        target_equity_value=300.0,
        target_net_income=30.0
    )
    assert res["standalone_eps"] == 2.0
    assert res["pro_forma_eps"] > 2.2
    assert "AKRETİF" in res["transaction_type"]
    assert res["eps_pct_change"] > 0

    # Dilutive deal: Target P/E is higher than Acquirer P/E
    dilutive_res = calculate_ma_accretion_dilution(
        acquirer_share_price=40.0,
        acquirer_shares_out=50.0,
        acquirer_net_income=100.0,
        target_equity_value=600.0,  # Paying 600M for 10M NI (P/E = 60)
        target_net_income=10.0
    )
    assert "DİLÜTİF" in dilutive_res["transaction_type"]
    assert dilutive_res["eps_pct_change"] < 0


def test_crack_spread():
    # Crude = $75, Gas = $105, Diesel = $110
    # Spread = (2 * 105 + 1 * 110 - 3 * 75) / 3 = (210 + 110 - 225) / 3 = 95 / 3 = $31.67 / bbl
    res = calculate_crack_spread(
        crude_oil_price_bbl=75.0,
        gasoline_price_bbl=105.0,
        diesel_price_bbl=110.0
    )
    assert res["crack_spread_per_bbl"] == 31.67
    assert "Çok Yüksek Rafineri Marjı" in res["margin_status"]


def test_guidotti_greenspan():
    # Safe country: 120B net reserves, 80B short-term external debt -> Ratio = 1.5
    safe_res = calculate_guidotti_greenspan(net_fx_reserves=120.0, short_term_external_debt=80.0)
    assert safe_res["guidotti_greenspan_ratio"] == 1.5
    assert "Güvenli Liman" in safe_res["resilience_status"]

    # Risky country: 30B net reserves, 60B short-term debt -> Ratio = 0.5
    risky_res = calculate_guidotti_greenspan(net_fx_reserves=30.0, short_term_external_debt=60.0)
    assert risky_res["guidotti_greenspan_ratio"] == 0.5
    assert "Kur Şoku Riski" in risky_res["resilience_status"]
