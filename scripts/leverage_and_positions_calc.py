#!/usr/bin/env python3
"""Quantitative educational calculator for Long, Short, and Leveraged Trading positions.
Calculates position sizing, return on equity (ROE), liquidation price, and margin call thresholds.
"""

from typing import Dict, Any


def calculate_long_position(
    entry_price: float,
    exit_price: float,
    collateral: float,
    leverage: float = 1.0,
    maintenance_margin_rate: float = 0.10,
) -> Dict[str, Any]:
    """Calculates metrics for a Long (Buy) position."""
    if entry_price <= 0 or collateral <= 0 or leverage <= 0:
        raise ValueError("Price, collateral, and leverage must be positive.")

    position_size = collateral * leverage
    quantity = position_size / entry_price
    price_change_pct = ((exit_price - entry_price) / entry_price) * 100.0
    pnl = (exit_price - entry_price) * quantity
    roe_pct = (pnl / collateral) * 100.0

    # Liquidation occurs when equity drops below maintenance margin:
    # Equity = Collateral + (P_liq - P_entry) * Quantity = Position_size * maintenance_margin_rate
    # Collateral + (P_liq - P_entry) * (Collateral * Leverage / P_entry) = Collateral * Leverage * mm
    # 1 + (P_liq/P_entry - 1) * Leverage = Leverage * mm
    # P_liq = P_entry * (1 - (1 - Leverage * mm) / Leverage) = P_entry * (1 - 1/Leverage + mm)
    if leverage > 1.0:
        liquidation_price = entry_price * (1.0 - (1.0 / leverage) + maintenance_margin_rate)
        liquidation_price = max(0.0, round(liquidation_price, 2))
    else:
        liquidation_price = 0.0  # In 1x spot, liquidation does not happen unless price drops to 0

    return {
        "position_type": "LONG",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "collateral": collateral,
        "leverage": leverage,
        "position_size": round(position_size, 2),
        "quantity": round(quantity, 4),
        "price_change_pct": round(price_change_pct, 2),
        "pnl": round(pnl, 2),
        "roe_pct": round(roe_pct, 2),
        "liquidation_price": liquidation_price,
        "is_liquidated": exit_price <= liquidation_price if leverage > 1.0 else False,
    }


def calculate_short_position(
    entry_price: float,
    exit_price: float,
    collateral: float,
    leverage: float = 1.0,
    maintenance_margin_rate: float = 0.10,
) -> Dict[str, Any]:
    """Calculates metrics for a Short (Sell) position."""
    if entry_price <= 0 or collateral <= 0 or leverage <= 0:
        raise ValueError("Price, collateral, and leverage must be positive.")

    position_size = collateral * leverage
    quantity = position_size / entry_price
    price_change_pct = ((entry_price - exit_price) / entry_price) * 100.0
    pnl = (entry_price - exit_price) * quantity
    roe_pct = (pnl / collateral) * 100.0

    # Liquidation for Short: when price rises such that remaining equity hits maintenance margin
    # Collateral + (P_entry - P_liq) * Quantity = Position_size * mm
    # 1 + (1 - P_liq/P_entry) * Leverage = Leverage * mm
    # P_liq = P_entry * (1 + (1 / Leverage) - maintenance_margin_rate)
    if leverage > 1.0:
        liquidation_price = entry_price * (1.0 + (1.0 / leverage) - maintenance_margin_rate)
        liquidation_price = round(liquidation_price, 2)
    else:
        # In 1x short, doubling the price wipes out collateral
        liquidation_price = round(entry_price * (2.0 - maintenance_margin_rate), 2)

    return {
        "position_type": "SHORT",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "collateral": collateral,
        "leverage": leverage,
        "position_size": round(position_size, 2),
        "quantity": round(quantity, 4),
        "price_change_pct": round(price_change_pct, 2),
        "pnl": round(pnl, 2),
        "roe_pct": round(roe_pct, 2),
        "liquidation_price": liquidation_price,
        "is_liquidated": exit_price >= liquidation_price,
    }


if __name__ == "__main__":
    import json
    long_res = calculate_long_position(100.0, 110.0, 10000.0, 5.0)
    short_res = calculate_short_position(100.0, 90.0, 10000.0, 5.0)
    print("Long Position Example (5x):", json.dumps(long_res, indent=2))
    print("Short Position Example (5x):", json.dumps(short_res, indent=2))
