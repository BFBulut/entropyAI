"""Automated test suite for Long, Short and Leveraged Trading Calculator."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from leverage_and_positions_calc import calculate_long_position, calculate_short_position


def test_spot_long_position():
    # 10,000 TL collateral, 1x leverage, entry 100 TL, exit 110 TL (+10% price move)
    res = calculate_long_position(entry_price=100.0, exit_price=110.0, collateral=10000.0, leverage=1.0)

    assert res["position_type"] == "LONG"
    assert res["position_size"] == 10000.0
    assert res["quantity"] == 100.0
    assert res["price_change_pct"] == 10.0
    assert res["pnl"] == 1000.0
    assert res["roe_pct"] == 10.0
    assert res["liquidation_price"] == 0.0
    assert res["is_liquidated"] is False


def test_leveraged_long_position_5x():
    # 10,000 TL collateral, 5x leverage -> 50,000 TL position size
    # Price rises +10% (100 -> 110)
    res = calculate_long_position(entry_price=100.0, exit_price=110.0, collateral=10000.0, leverage=5.0)

    assert res["position_size"] == 50000.0
    assert res["quantity"] == 500.0
    assert res["pnl"] == 5000.0
    assert res["roe_pct"] == 50.0  # 5x leverage multiplies +10% into +50% return!
    assert res["liquidation_price"] == 90.0  # 100 * (1 - 1/5 + 0.10) = 90.0
    assert res["is_liquidated"] is False


def test_leveraged_long_liquidation():
    # If price drops to 88 TL (below 90 TL liquidation price)
    res = calculate_long_position(entry_price=100.0, exit_price=88.0, collateral=10000.0, leverage=5.0)

    assert res["liquidation_price"] == 90.0
    assert res["is_liquidated"] is True
    assert res["pnl"] == -6000.0
    assert res["roe_pct"] == -60.0


def test_spot_short_position():
    # 10,000 TL collateral, 1x leverage, entry 100 TL, exit 90 TL (-10% price drop)
    res = calculate_short_position(entry_price=100.0, exit_price=90.0, collateral=10000.0, leverage=1.0)

    assert res["position_type"] == "SHORT"
    assert res["position_size"] == 10000.0
    assert res["quantity"] == 100.0
    assert res["pnl"] == 1000.0
    assert res["roe_pct"] == 10.0
    assert res["is_liquidated"] is False


def test_leveraged_short_position_5x():
    # 10,000 TL collateral, 5x leverage -> 50,000 TL position size
    # Price drops -10% (100 -> 90)
    res = calculate_short_position(entry_price=100.0, exit_price=90.0, collateral=10000.0, leverage=5.0)

    assert res["position_size"] == 50000.0
    assert res["quantity"] == 500.0
    assert res["pnl"] == 5000.0
    assert res["roe_pct"] == 50.0  # 5x leverage turns -10% price drop into +50% profit!
    assert res["liquidation_price"] == 110.0  # 100 * (1 + 1/5 - 0.10) = 110.0
    assert res["is_liquidated"] is False


def test_leveraged_short_liquidation():
    # If price rises to 112 TL (above 110 TL liquidation price)
    res = calculate_short_position(entry_price=100.0, exit_price=112.0, collateral=10000.0, leverage=5.0)

    assert res["liquidation_price"] == 110.0
    assert res["is_liquidated"] is True
    assert res["pnl"] == -6000.0
    assert res["roe_pct"] == -60.0


def test_invalid_parameters():
    with pytest.raises(ValueError):
        calculate_long_position(entry_price=-10.0, exit_price=100.0, collateral=1000.0)

    with pytest.raises(ValueError):
        calculate_short_position(entry_price=100.0, exit_price=90.0, collateral=-500.0)
