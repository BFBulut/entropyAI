#!/usr/bin/env python3
"""CLI and library utility for Hawkes Processes, Rough Volatility, Repo Plumbing, Stub Value & DeFi MEV:
- Hawkes Point Processes & LOB Toxicity (Branching Ratio, Endogeneity Index, Kyle's Lambda & Spread Decomposition)
- Rough Volatility & Fractional Brownian Motion (Gatheral-Rosenbaum H~0.1, Power-law Skew Scaling & Bergomi Forward Variance)
- Repo Market Plumbing & Collateral Scarcity (GC vs Specials, Convenience Yield & TMPG Fail Charge Rate)
- Stub Value Anomaly, Carve-Out Arbitrage & Rights Offering (Negative EV Stub, TERP & Nil-Paid Value)
- DeFi Financial Engineering: MEV Sandwich Economics & Curve v2 Dynamic Peg (Slippage Extraction & Internal Oracle Re-pegging)
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional


def calculate_hawkes_and_lob_toxicity(
    mu: float,
    alpha: float,
    beta: float,
    cov_delta_p_q: float,
    var_q: float,
    total_spread_bps: float,
    adverse_selection_pct: float = 45.0,
    inventory_risk_pct: float = 35.0
) -> Dict[str, Any]:
    """Calculates Hawkes Self-Exciting Point Process & Limit Order Book (LOB) toxicity:
    - Branching ratio (eta = alpha / beta) and endogeneity index.
    - Asymptotic stationary event intensity (lambda_inf = mu / (1 - eta)).
    - Kyle's Lambda (price impact of signed order flow: Cov(Delta P, Q) / Var(Q)).
    - Bid-Ask Spread structural decomposition into Adverse Selection, Inventory Risk, and Order Processing.
    """
    if mu <= 0.0 or alpha <= 0.0 or beta <= 0.0:
        return {"error": "Parametreler (mu, alpha, beta) pozitif olmalıdır."}
    if var_q <= 0.0:
        return {"error": "Emir akışı varyansı (var_q) pozitif olmalıdır."}
    if total_spread_bps <= 0.0:
        return {"error": "Alış-satış marjı (total_spread_bps) pozitif olmalıdır."}

    # Branching Ratio eta = alpha / beta
    branching_ratio_eta = alpha / beta
    endogeneity_index_pct = round(branching_ratio_eta * 100.0, 2)

    # Stability & asymptotic intensity
    if branching_ratio_eta < 1.0:
        asymptotic_intensity = round(mu / (1.0 - branching_ratio_eta), 4)
    else:
        asymptotic_intensity = float("inf")

    # Regime categorization
    if branching_ratio_eta < 0.70:
        stability_regime = "Kararlı / Dışsal Akış Egemen (Exogenous Driven)"
    elif branching_ratio_eta < 0.95:
        stability_regime = "Yarı-Kritik / Artan Endojen Geri Besleme (Subcritical Elevated)"
    elif branching_ratio_eta < 1.00:
        stability_regime = "Aşırı Kırılgan / Çöküş Öncesi Rejim (Near-Critical Flash Crash Risk)"
    else:
        stability_regime = "Süper-Kritik Patlama / Likidite Karadeliği (Supercritical Collapse)"

    # Kyle's Lambda: lambda = Cov(Delta P, Q) / Var(Q)
    kyles_lambda = round(cov_delta_p_q / var_q, 6)

    # Spread Decomposition (Glosten-Milgrom / Stoll framework)
    adv_pct = max(0.0, min(100.0, adverse_selection_pct))
    inv_pct = max(0.0, min(100.0 - adv_pct, inventory_risk_pct))
    proc_pct = max(0.0, round(100.0 - adv_pct - inv_pct, 2))

    spread_adverse_selection_bps = round(total_spread_bps * (adv_pct / 100.0), 2)
    spread_inventory_risk_bps = round(total_spread_bps * (inv_pct / 100.0), 2)
    spread_order_processing_bps = round(total_spread_bps * (proc_pct / 100.0), 2)

    # Algorithmic execution recommendation
    if branching_ratio_eta >= 0.95 or kyles_lambda > 0.005:
        exec_recommendation = (
            "Yüksek toksik akış ve endojen kaskad riski: Agresif piyasa emirlerinden kaçının. "
            "Gecikmeli pasif emirler, Almgren-Chriss kalıcı etki kısıtları ve buzdağı (iceberg) dilimleme kullanın."
        )
    else:
        exec_recommendation = (
            "Düşük toksisite ve dengeli emir akışı: Standart TWAP / VWAP yürütme algoritmaları "
            "ve pasif likidite sağlama katsayıları güvenle çalıştırılabilir."
        )

    return {
        "branching_ratio_eta": round(branching_ratio_eta, 4),
        "endogeneity_index_pct": endogeneity_index_pct,
        "asymptotic_intensity": asymptotic_intensity,
        "stability_regime": stability_regime,
        "kyles_lambda": kyles_lambda,
        "total_spread_bps": total_spread_bps,
        "spread_adverse_selection_bps": spread_adverse_selection_bps,
        "spread_inventory_risk_bps": spread_inventory_risk_bps,
        "spread_order_processing_bps": spread_order_processing_bps,
        "adverse_selection_pct": adv_pct,
        "inventory_risk_pct": inv_pct,
        "order_processing_pct": proc_pct,
        "execution_recommendation": exec_recommendation
    }


def calculate_rough_volatility_and_hurst(
    hurst_parameter_h: float,
    spot_vol_pct: float,
    maturities_days: Optional[List[float]] = None,
    baseline_skew_multiplier: float = 0.15
) -> Dict[str, Any]:
    """Calculates Rough Volatility & Fractional Brownian Motion metrics:
    - Hurst exponent (H) diagnosis (Gatheral-Rosenbaum rough regime H ~ 0.1 vs Brownian H = 0.5).
    - Power-law scaling of at-the-money implied volatility skew: S(T) ~ C * T^(H - 0.5).
    - Contrast against classical Markovian stochastic volatility (Heston/SABR) where S(T) ~ O(1).
    """
    if hurst_parameter_h <= 0.0 or hurst_parameter_h >= 1.0:
        return {"error": "Hurst parametresi (H) (0, 1) aralığında olmalıdır."}
    if spot_vol_pct <= 0.0:
        return {"error": "Spot volatilite pozitif olmalıdır."}

    if maturities_days is None:
        maturities_days = [1.0, 5.0, 10.0, 30.0, 60.0, 90.0, 180.0, 365.0]

    # Roughness characterization
    roughness_degree = round(0.5 - hurst_parameter_h, 4)
    if hurst_parameter_h < 0.45:
        hurst_regime = "Rough Volatilite / Anti-Kalıcı (Gatheral-Jaquier-Rosenbaum Rejimi)"
    elif hurst_parameter_h <= 0.55:
        hurst_regime = "Klasik Markovian Difüzyon / Standart Brown Hareketi (Black-Scholes/Heston)"
    else:
        hurst_regime = "Süper-Diffusive / Kalıcı Trend Rejimi (Long-Memory)"

    power_law_exponent = round(hurst_parameter_h - 0.5, 4)

    # Implied Volatility Skew term structure
    skew_term_structure = []
    for days in maturities_days:
        t_years = max(1.0 / 365.0, days / 365.0)
        # S(T) = C * T^(H - 0.5)
        skew_value = baseline_skew_multiplier * (t_years ** power_law_exponent)
        skew_term_structure.append({
            "maturity_days": days,
            "maturity_years": round(t_years, 4),
            "atm_implied_skew": round(skew_value, 4)
        })

    # Skew blowup ratio (1-day vs 1-year)
    t_1d = 1.0 / 365.0
    t_1y = 1.0
    blowup_ratio = round((t_1d ** power_law_exponent) / (t_1y ** power_law_exponent), 2)

    return {
        "hurst_parameter_h": round(hurst_parameter_h, 4),
        "roughness_degree": roughness_degree,
        "power_law_exponent": power_law_exponent,
        "hurst_regime": hurst_regime,
        "spot_vol_pct": spot_vol_pct,
        "skew_blowup_ratio_1d_vs_1y": blowup_ratio,
        "skew_term_structure": skew_term_structure,
        "theoretical_insight": (
            f"Hurst H = {hurst_parameter_h:.2f} durumunda üs (H - 0.5) = {power_law_exponent:.2f}'dir. "
            "Vade sıfıra yaklaştıkça (T -> 0) zımni volatilite skew'u güç yasasıyla dikleşir. "
            "Klasik Heston/SABR modelleri vadenin kısalmasında skew'u sabit tutmaya çalışırken, "
            "Rough Volatilite ultra-kısa vadeli piyasa opsiyon gülüşünü tam tutarlılıkla açıklar."
        )
    }


def calculate_repo_plumbing_and_specials(
    gc_repo_rate_pct: float,
    special_repo_rate_pct: float,
    fed_funds_target_pct: float,
    failed_delivery_amount: float,
    fail_duration_days: int = 1
) -> Dict[str, Any]:
    """Calculates Money Market Repo Plumbing, Collateral Scarcity & TMPG Fail Charge:
    - Specialness spread (GC Rate - Special Rate) and repo convenience yield.
    - Negative repo rate threshold and collateral squeeze mechanics.
    - TMPG (Treasury Market Practices Group) fail charge rate: max(3.0% - Fed Funds Target, 0.0%).
    - Financial penalty accrued on fails-to-deliver settlement failure.
    """
    if failed_delivery_amount < 0.0 or fail_duration_days <= 0:
        return {"error": "Teslimat tutarı pozitif ve başarısızlık süresi en az 1 gün olmalıdır."}

    # Specialness Spread = GC - Special
    specialness_spread_pct = round(max(0.0, gc_repo_rate_pct - special_repo_rate_pct), 4)
    specialness_spread_bps = round(specialness_spread_pct * 100.0, 2)
    convenience_yield_pct = specialness_spread_pct

    # Collateral Status
    if specialness_spread_bps <= 15.0:
        collateral_status = "Genel Teminat (General Collateral - GC) Dengesi"
    elif specialness_spread_bps <= 150.0:
        collateral_status = "Ilımlı Özel Talep (Mild Special / On-The-Run Prim)"
    else:
        collateral_status = "Akut Özel Sıkışma (Acute Special Squeeze / Şiddetli Teminat Kıtlığı)"

    # TMPG Fail Charge Rate: max(3.0% - Fed Funds Target, 0.0%)
    tmpg_fail_charge_rate_pct = round(max(0.0, 3.0 - fed_funds_target_pct), 4)

    # Daily money market convention (Actual/360)
    # Financial Penalty = Amount * (Rate / 100) * (Days / 360)
    fail_penalty_cost = round(failed_delivery_amount * (tmpg_fail_charge_rate_pct / 100.0) * (fail_duration_days / 360.0), 2)

    # Negative repo rate check
    negative_repo_occurred = special_repo_rate_pct < 0.0

    return {
        "gc_repo_rate_pct": gc_repo_rate_pct,
        "special_repo_rate_pct": special_repo_rate_pct,
        "specialness_spread_pct": specialness_spread_pct,
        "specialness_spread_bps": specialness_spread_bps,
        "convenience_yield_pct": convenience_yield_pct,
        "collateral_status": collateral_status,
        "fed_funds_target_pct": fed_funds_target_pct,
        "tmpg_fail_charge_rate_pct": tmpg_fail_charge_rate_pct,
        "failed_delivery_amount": failed_delivery_amount,
        "fail_duration_days": fail_duration_days,
        "fail_penalty_cost": fail_penalty_cost,
        "negative_repo_occurred": negative_repo_occurred,
        "macro_implication": (
            f"Specialness yayılması {specialness_spread_bps:.1f} bps seviyesinde. "
            f"TMPG ceza oranı %{tmpg_fail_charge_rate_pct:.2f}. "
            "Nakit borç verenler spesifik Hazine kağıdını ele geçirmek için faizden feragat etmektedir."
        )
    }


def calculate_stub_value_and_rights_offering(
    parent_market_cap: float,
    sub_market_cap: float,
    ownership_pct: float,
    current_stock_price: float,
    num_existing_shares: float,
    num_new_shares: float,
    subscription_price: float
) -> Dict[str, Any]:
    """Calculates Stub Value Carve-Out Anomaly & Rights Offering Economics:
    - Stub Value = Parent Market Cap - (Ownership % * Sub Market Cap).
    - Negative Enterprise Value / Negative Stub diagnosis (Palm/3Com anomaly).
    - Theoretical Ex-Rights Price (TERP) and Nil-Paid Right Value.
    - Dilution ratio and subscription discount from market price.
    """
    if parent_market_cap <= 0.0 or sub_market_cap <= 0.0:
        return {"error": "Piyasa değerleri pozitif olmalıdır."}
    if ownership_pct <= 0.0 or ownership_pct > 100.0:
        return {"error": "Sahiplik oranı %0 ile %100 arasında olmalıdır."}
    if current_stock_price <= 0.0 or subscription_price <= 0.0:
        return {"error": "Hisse ve rüçhan fiyatları pozitif olmalıdır."}
    if num_existing_shares <= 0.0 or num_new_shares <= 0.0:
        return {"error": "Hisse adetleri pozitif olmalıdır."}

    # 1. Stub Value Analysis
    sub_stake_value = sub_market_cap * (ownership_pct / 100.0)
    stub_value = round(parent_market_cap - sub_stake_value, 2)
    stub_margin_pct = round((stub_value / parent_market_cap) * 100.0, 2)
    is_negative_stub = stub_value < 0.0

    if is_negative_stub:
        stub_diagnosis = (
            "NEGATİF STUB ANOMALİSİ: Ana şirketin bağlı ortaklık haricindeki tüm operasyonları "
            "ve nakit rezervleri piyasa tarafından negatif fiyatlanmaktadır. "
            "Klasik Carve-out/Spin-off arbitrajı (Ana şirkette Uzun, Bağlı ortaklıkta Kısa), "
            "ancak açığa satış borçlanma maliyeti (hard-to-borrow) dikkatle incelenmelidir."
        )
    else:
        stub_diagnosis = "POZİTİF STUB: Ana şirketin ana operasyonları pozitif piyasa değerine sahiptir."

    # 2. Rights Offering (Rüçhan Hakkı) Analysis
    # TERP = (N_old * P_old + N_new * P_sub) / (N_old + N_new)
    total_shares_post = num_existing_shares + num_new_shares
    terp = round(
        (num_existing_shares * current_stock_price + num_new_shares * subscription_price) / total_shares_post,
        4
    )

    # Theoretical Nil-Paid Right Value: V_right = P_old - TERP
    nil_paid_right_value = round(current_stock_price - terp, 4)

    # Subscription discount
    subscription_discount_pct = round(((current_stock_price - subscription_price) / current_stock_price) * 100.0, 2)

    # Dilution factor
    dilution_pct = round((num_new_shares / total_shares_post) * 100.0, 2)

    # Rights ratio (e.g. 1 new share for every X existing shares)
    rights_ratio = round(num_existing_shares / num_new_shares, 2)

    return {
        "parent_market_cap": parent_market_cap,
        "sub_market_cap": sub_market_cap,
        "ownership_pct": ownership_pct,
        "sub_stake_value": round(sub_stake_value, 2),
        "stub_value": stub_value,
        "stub_margin_pct": stub_margin_pct,
        "is_negative_stub": is_negative_stub,
        "stub_diagnosis": stub_diagnosis,
        "current_stock_price": current_stock_price,
        "subscription_price": subscription_price,
        "terp": terp,
        "nil_paid_right_value": nil_paid_right_value,
        "subscription_discount_pct": subscription_discount_pct,
        "dilution_pct": dilution_pct,
        "rights_ratio": f"1:{rights_ratio}",
        "total_shares_post": total_shares_post
    }


def calculate_defi_mev_and_curve_v2(
    victim_input_amount: float,
    victim_slippage_tolerance_pct: float,
    pool_reserve_x: float,
    pool_reserve_y: float,
    gas_and_builder_cost_usd: float,
    current_internal_oracle_price: float,
    market_spot_price: float,
    repeg_threshold_bps: float = 50.0
) -> Dict[str, Any]:
    """Calculates DeFi MEV Sandwich Extraction Economics & Curve v2 Dynamic Peg Re-centering:
    - Frontrun sizing to push victim to exact maximum slippage boundary.
    - Extractable gross value and net profit after builder bribes and gas priority fees.
    - Curve v2 internal oracle price deviation (distance from market spot price).
    - Dynamic re-pegging trigger condition and concentrated liquidity capital efficiency.
    """
    if victim_input_amount <= 0.0 or pool_reserve_x <= 0.0 or pool_reserve_y <= 0.0:
        return {"error": "İşlem tutarı ve havuz rezervleri pozitif olmalıdır."}
    if victim_slippage_tolerance_pct <= 0.0 or current_internal_oracle_price <= 0.0 or market_spot_price <= 0.0:
        return {"error": "Kayma toleransı ve fiyatlar pozitif olmalıdır."}

    # Constant Product initial spot price P = Y / X
    initial_spot_price = pool_reserve_y / pool_reserve_x

    # Victim slippage threshold price
    slippage_frac = victim_slippage_tolerance_pct / 100.0
    worst_acceptable_price = initial_spot_price * (1.0 + slippage_frac)

    # Sizing frontrun transaction: amount of X to push spot price to worst_acceptable_price
    # Target delta P / P = slippage_frac -> dx_frontrun approx (X / 2) * slippage_frac
    approx_frontrun_x = round((pool_reserve_x / 2.0) * slippage_frac, 2)

    # Theoretical gross extractable value from victim's enforced slippage:
    price_delta = worst_acceptable_price - initial_spot_price
    gross_mev_usd = round(victim_input_amount * price_delta, 2)
    net_mev_profit_usd = round(gross_mev_usd - gas_and_builder_cost_usd, 2)
    mev_viable = net_mev_profit_usd > 0.0

    # Curve v2 Dynamic Peg Analysis
    price_diff = abs(market_spot_price - current_internal_oracle_price)
    peg_distance_bps = round((price_diff / current_internal_oracle_price) * 10000.0, 2)

    repeg_triggered = peg_distance_bps > repeg_threshold_bps

    # Capital efficiency multiplier of Curve v2 concentrated range vs x*y=k
    capital_efficiency_multiplier = round(max(2.0, min(50.0, 5000.0 / (peg_distance_bps + 100.0))), 2)

    return {
        "initial_spot_price": round(initial_spot_price, 4),
        "worst_acceptable_victim_price": round(worst_acceptable_price, 4),
        "approx_optimal_frontrun_x": approx_frontrun_x,
        "gross_mev_usd": gross_mev_usd,
        "gas_and_builder_cost_usd": gas_and_builder_cost_usd,
        "net_mev_profit_usd": net_mev_profit_usd,
        "mev_viable": mev_viable,
        "mev_status": "KÂRLI SANDVİÇ (Viable MEV)" if mev_viable else "ZARARLI / GAS İFLASI (Unviable)",
        "internal_oracle_price": current_internal_oracle_price,
        "market_spot_price": market_spot_price,
        "peg_distance_bps": peg_distance_bps,
        "repeg_threshold_bps": repeg_threshold_bps,
        "repeg_triggered": repeg_triggered,
        "repeg_status": (
            "DİNAMİK YENİDEN MERKEZLEME TETİKLENDİ: Dahili EMA kahini piyasa fiyatına doğru kaydırılıyor."
            if repeg_triggered else "STABİL PEG: Havuz konsantre likidite aralığında dengeli."
        ),
        "capital_efficiency_multiplier": f"{capital_efficiency_multiplier}x"
    }


def main():
    parser = argparse.ArgumentParser(description="Hawkes, Rough Volatility, Repo Plumbing, Stub & DeFi MEV CLI Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Hawkes parser
    p_hawkes = subparsers.add_parser("hawkes", help="Hawkes Point Process and LOB Toxicity")
    p_hawkes.add_argument("--mu", type=float, required=True)
    p_hawkes.add_argument("--alpha", type=float, required=True)
    p_hawkes.add_argument("--beta", type=float, required=True)
    p_hawkes.add_argument("--cov", type=float, required=True)
    p_hawkes.add_argument("--var", type=float, required=True)
    p_hawkes.add_argument("--spread", type=float, required=True)
    p_hawkes.add_argument("--adverse", type=float, default=45.0)
    p_hawkes.add_argument("--inventory", type=float, default=35.0)

    # Rough Volatility parser
    p_rough = subparsers.add_parser("rough_vol", help="Rough Volatility & Hurst Exponent")
    p_rough.add_argument("--hurst", type=float, required=True)
    p_rough.add_argument("--spot-vol", type=float, required=True)

    # Repo parser
    p_repo = subparsers.add_parser("repo", help="Repo Plumbing, Specials and TMPG Fails")
    p_repo.add_argument("--gc", type=float, required=True)
    p_repo.add_argument("--special", type=float, required=True)
    p_repo.add_argument("--ff-target", type=float, required=True)
    p_repo.add_argument("--failed-amount", type=float, required=True)
    p_repo.add_argument("--days", type=int, default=1)

    # Stub value parser
    p_stub = subparsers.add_parser("stub", help="Stub Value Carve-Out and Rights Offering")
    p_stub.add_argument("--parent-cap", type=float, required=True)
    p_stub.add_argument("--sub-cap", type=float, required=True)
    p_stub.add_argument("--ownership", type=float, required=True)
    p_stub.add_argument("--stock-price", type=float, required=True)
    p_stub.add_argument("--existing-shares", type=float, required=True)
    p_stub.add_argument("--new-shares", type=float, required=True)
    p_stub.add_argument("--sub-price", type=float, required=True)

    # DeFi MEV parser
    p_defi = subparsers.add_parser("defi", help="DeFi MEV Sandwich and Curve v2 Peg")
    p_defi.add_argument("--victim-input", type=float, required=True)
    p_defi.add_argument("--slippage", type=float, required=True)
    p_defi.add_argument("--reserve-x", type=float, required=True)
    p_defi.add_argument("--reserve-y", type=float, required=True)
    p_defi.add_argument("--gas-usd", type=float, required=True)
    p_defi.add_argument("--oracle-price", type=float, required=True)
    p_defi.add_argument("--spot-price", type=float, required=True)

    args = parser.parse_args()

    if args.command == "hawkes":
        res = calculate_hawkes_and_lob_toxicity(
            mu=args.mu,
            alpha=args.alpha,
            beta=args.beta,
            cov_delta_p_q=args.cov,
            var_q=args.var,
            total_spread_bps=args.spread,
            adverse_selection_pct=args.adverse,
            inventory_risk_pct=args.inventory
        )
    elif args.command == "rough_vol":
        res = calculate_rough_volatility_and_hurst(
            hurst_parameter_h=args.hurst,
            spot_vol_pct=args.spot_vol
        )
    elif args.command == "repo":
        res = calculate_repo_plumbing_and_specials(
            gc_repo_rate_pct=args.gc,
            special_repo_rate_pct=args.special,
            fed_funds_target_pct=args.ff_target,
            failed_delivery_amount=args.failed_amount,
            fail_duration_days=args.days
        )
    elif args.command == "stub":
        res = calculate_stub_value_and_rights_offering(
            parent_market_cap=args.parent_cap,
            sub_market_cap=args.sub_cap,
            ownership_pct=args.ownership,
            current_stock_price=args.stock_price,
            num_existing_shares=args.existing_shares,
            num_new_shares=args.new_shares,
            subscription_price=args.sub_price
        )
    elif args.command == "defi":
        res = calculate_defi_mev_and_curve_v2(
            victim_input_amount=args.victim_input,
            victim_slippage_tolerance_pct=args.slippage,
            pool_reserve_x=args.reserve_x,
            pool_reserve_y=args.reserve_y,
            gas_and_builder_cost_usd=args.gas_usd,
            current_internal_oracle_price=args.oracle_price,
            market_spot_price=args.spot_price
        )
    else:
        res = {"error": "Bilinmeyen komut."}

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
