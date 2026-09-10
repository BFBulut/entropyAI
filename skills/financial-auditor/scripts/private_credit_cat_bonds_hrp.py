#!/usr/bin/env python3
"""CLI and library utility for Private Credit, Cat Bonds, LMT Distressed Maneuvers, HRP & Dispersion Trading:
- Private Credit & Unitranche Lending (SOFR + Spread, OID, PIK, Leverage/FCCR Covenants & Equity Cure)
- Catastrophe Bonds & Insurance-Linked Securities (ILS, Parametric vs Indemnity, Expected Loss, Spread Multiple)
- Liability Management Transactions (LMT / Creditor-on-Creditor Violence, J.Crew Dropdown & Serta Uptiering)
- Hierarchical Risk Parity (HRP / Lopez de Prado Machine Learning Portfolio Allocation)
- Correlation Swaps & Dispersion Trading Arbitrage (Implied vs Realized Correlation, Vega-Neutral Basket)
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional


def calculate_private_credit_and_unitranche(
    sofr_pct: float,
    margin_spread_bps: float,
    oid_pct: float,
    pik_spread_bps: float,
    total_debt: float,
    ebitda: float,
    interest_expense: float,
    capex: float = 0.0,
    tax_expense: float = 0.0,
    tenor_years: float = 5.0,
    covenant_max_leverage: float = 6.0,
    covenant_min_fccr: float = 1.20,
    first_out_ratio_pct: float = 50.0,
    first_out_spread_bps: float = 400.0,
    last_out_spread_bps: float = 800.0
) -> Dict[str, Any]:
    """Calculates Private Credit, Direct Lending & Unitranche debt economics:
    - Cash Coupon, PIK (Payment-In-Kind), OID (Original Issue Discount) effective yield.
    - First-Out / Last-Out (FOLO) syndication tranche economics under Agreement Among Lenders (AAL).
    - Leverage covenant test (Total Debt / EBITDA) and FCCR (Fixed Charge Coverage Ratio).
    - Equity Cure injection sizing required to remedy covenant default.
    """
    if total_debt <= 0 or ebitda <= 0 or tenor_years <= 0 or interest_expense <= 0:
        return {"error": "Toplam borç, EBITDA, vade ve faiz gideri pozitif olmalıdır."}

    cash_margin_pct = margin_spread_bps / 100.0
    cash_coupon_pct = sofr_pct + cash_margin_pct
    pik_rate_pct = pik_spread_bps / 100.0
    total_coupon_pct = cash_coupon_pct + pik_rate_pct

    # All-in Yield (IRR approximation: Total Coupon + OID amortized over tenor)
    oid_annualized_pct = oid_pct / tenor_years
    all_in_effective_yield_pct = total_coupon_pct + oid_annualized_pct

    # First-Out / Last-Out (FOLO) Unitranche Tranches
    fo_ratio = max(0.0, min(100.0, first_out_ratio_pct)) / 100.0
    lo_ratio = 1.0 - fo_ratio

    fo_debt = total_debt * fo_ratio
    lo_debt = total_debt * lo_ratio

    fo_rate_pct = sofr_pct + (first_out_spread_bps / 100.0)
    lo_rate_pct = sofr_pct + (last_out_spread_bps / 100.0)

    blended_folo_rate_pct = (fo_debt * fo_rate_pct + lo_debt * lo_rate_pct) / total_debt

    # Covenant Metrics
    current_leverage = total_debt / ebitda
    leverage_breach = current_leverage > covenant_max_leverage
    leverage_cushion_turns = round(covenant_max_leverage - current_leverage, 2)

    # FCCR = (EBITDA - CapEx - Cash Taxes) / Interest Expense
    free_cash_for_charges = ebitda - capex - tax_expense
    current_fccr = free_cash_for_charges / interest_expense
    fccr_breach = current_fccr < covenant_min_fccr
    fccr_cushion = round(current_fccr - covenant_min_fccr, 2)

    # Equity Cure Requirement (Cash infusion to pay down debt or boost EBITDA to cure leverage breach)
    if leverage_breach:
        equity_cure_required = round(max(0.0, total_debt - (covenant_max_leverage * ebitda)), 2)
    else:
        equity_cure_required = 0.0

    # Risk Diagnosis
    if leverage_breach and fccr_breach:
        covenant_status = "KRİTİK İHLAL: Hem Kaldıraç hem FCCR kısıtları aşıldı. Temerrüt veya derhal Equity Cure zorunlu."
    elif leverage_breach:
        covenant_status = f"KALDIRAÇ İHLALİ: Borç/EBITDA ({current_leverage:.2f}x) > {covenant_max_leverage:.2f}x. Sponsor onarımı gerekli."
    elif fccr_breach:
        covenant_status = f"FCCR İHLALİ: Nakit karşılama ({current_fccr:.2f}x) < {covenant_min_fccr:.2f}x. Faiz ödeme baskısı yüksek."
    else:
        covenant_status = "GÜVENLİ KORİDOR: Kredi sözleşmesi kısıtları (Kaldıraç & FCCR) karşılanıyor."

    return {
        "sofr_base_rate_pct": round(sofr_pct, 2),
        "cash_margin_bps": round(margin_spread_bps, 1),
        "cash_coupon_pct": round(cash_coupon_pct, 2),
        "pik_spread_bps": round(pik_spread_bps, 1),
        "total_nominal_coupon_pct": round(total_coupon_pct, 2),
        "oid_pct": round(oid_pct, 2),
        "all_in_effective_yield_pct": round(all_in_effective_yield_pct, 2),
        "first_out_debt": round(fo_debt, 2),
        "last_out_debt": round(lo_debt, 2),
        "first_out_all_in_rate_pct": round(fo_rate_pct, 2),
        "last_out_all_in_rate_pct": round(lo_rate_pct, 2),
        "blended_folo_rate_pct": round(blended_folo_rate_pct, 2),
        "current_leverage_ratio": round(current_leverage, 2),
        "covenant_max_leverage": round(covenant_max_leverage, 2),
        "leverage_cushion_turns": leverage_cushion_turns,
        "current_fccr": round(current_fccr, 2),
        "covenant_min_fccr": round(covenant_min_fccr, 2),
        "fccr_cushion": fccr_cushion,
        "equity_cure_required": equity_cure_required,
        "covenant_status_diagnosis": covenant_status
    }


def calculate_cat_bond_and_ils(
    collateral_principal: float,
    spread_bps: float,
    expected_loss_pct: float,
    attachment_prob_pct: float,
    exhaustion_prob_pct: float,
    trigger_type: str = "parametric",
    collateral_yield_pct: float = 4.50,
    beta_to_market: float = 0.02
) -> Dict[str, Any]:
    """Calculates Catastrophe Bond (Cat Bond) & Insurance-Linked Securities (ILS) metrics:
    - Investor all-in yield (SPV Treasury collateral return + Reinsurance spread).
    - Expected Net Return, Spread Multiple (Spread / Expected Loss).
    - Trigger typology evaluation (Parametric vs Indemnity vs Industry Loss Index vs Modeled Loss).
    - Zero-Beta market correlation and diversification power.
    """
    if collateral_principal <= 0 or spread_bps < 0 or expected_loss_pct <= 0:
        return {"error": "Teminat anaparası, spread ve beklenen zarar pozitif olmalıdır."}

    spread_pct = spread_bps / 100.0
    total_yield_pct = collateral_yield_pct + spread_pct
    net_expected_return_pct = total_yield_pct - expected_loss_pct

    # Spread Multiple (Pricing Benchmark)
    spread_multiple = spread_pct / expected_loss_pct

    # Trigger Assessment
    valid_triggers = ["parametric", "indemnity", "industry_loss", "modeled_loss"]
    clean_trigger = trigger_type.lower() if trigger_type.lower() in valid_triggers else "parametric"

    trigger_profiles = {
        "parametric": {
            "name": "Parametrik Tetikleyici",
            "moral_hazard": "Sıfır",
            "settlement_speed": "Anlık (Günler içinde)",
            "trapped_collateral_risk": "Yok",
            "basis_risk": "Orta/Yüksek (Sigortacının gerçek zararı ile endeks ölçümü sapabilir)"
        },
        "indemnity": {
            "name": "Tazminat Esaslı (Indemnity) Tetikleyici",
            "moral_hazard": "Yüksek (Sponsor hasar dosyalarını yönetir)",
            "settlement_speed": "Yavaş (Aylar/Yıllar sürebilir)",
            "trapped_collateral_risk": "Yüksek (Dava ve audit süreçlerinde kilitli teminat)",
            "basis_risk": "Sıfır (Birebir şirketin nihai bilançodaki net hasarına bağlı)"
        },
        "industry_loss": {
            "name": "Sektörel Hasar Endeksi (PCS / PERILS)",
            "moral_hazard": "Çok Düşük",
            "settlement_speed": "Orta (Endeks nihai raporuna bağlı)",
            "trapped_collateral_risk": "Düşük/Orta",
            "basis_risk": "Orta"
        },
        "modeled_loss": {
            "name": "Modellenmiş Hasar (AIR / RMS Simülasyonu)",
            "moral_hazard": "Düşük",
            "settlement_speed": "Hızlı/Orta",
            "trapped_collateral_risk": "Düşük",
            "basis_risk": "Model kalibrasyon hatasına duyarlı"
        }
    }

    # Market Multiples Regime
    if spread_multiple >= 3.5:
        pricing_regime = "SERT PİYASA (Hard Market): Sermaye kıtlığı var; yatırımcı yüksek risk primi çarpanı elde ediyor."
    elif spread_multiple >= 2.2:
        pricing_regime = "DENGELİ REJİM (Normal Market): Tarihsel getiri/zarar çarpanı ortalamasında fiyatlama."
    else:
        pricing_regime = "YUMUŞAK PİYASA (Soft Market): Bol reasürans likiditesi; risk primleri sıkışmış."

    return {
        "collateral_principal": round(collateral_principal, 2),
        "collateral_yield_pct": round(collateral_yield_pct, 2),
        "reinsurance_spread_bps": round(spread_bps, 1),
        "reinsurance_spread_pct": round(spread_pct, 2),
        "total_cat_bond_yield_pct": round(total_yield_pct, 2),
        "expected_loss_pct": round(expected_loss_pct, 2),
        "net_expected_return_pct": round(net_expected_return_pct, 2),
        "spread_multiple": round(spread_multiple, 2),
        "attachment_probability_pct": round(attachment_prob_pct, 2),
        "exhaustion_probability_pct": round(exhaustion_prob_pct, 2),
        "trigger_type": clean_trigger,
        "trigger_profile": trigger_profiles[clean_trigger],
        "beta_to_equity_market": round(beta_to_market, 3),
        "portfolio_diversification_status": "SIFIR-BETA AKTİF: Hisse senedi ve kredi döngülerinden bağımsız saf aktüeryal risk primi.",
        "pricing_regime_diagnosis": pricing_regime
    }


def calculate_lmt_dropdown_uptiering(
    existing_debt: float,
    collateral_value: float,
    dropdown_asset_value: float,
    new_priming_debt: float,
    minority_debt: float,
    majority_debt: float,
    distressed_ev: float,
    transaction_type: str = "dropdown"
) -> Dict[str, Any]:
    """Calculates Liability Management Transactions (LMT) & Creditor-on-Creditor Violence:
    - Dropdown Maneuver (J.Crew tactic): Carving out crown-jewel assets to Unrestricted Subsidiary to raise priming debt.
    - Uptiering Maneuver (Serta tactic): Non-pro-rata priming amendment creating Super-Priority lien subordinating minority lenders.
    - Collateral leakage, pro-rata vs post-transaction recovery rates, and creditor haircut analysis.
    """
    if existing_debt <= 0 or collateral_value <= 0 or distressed_ev <= 0 or new_priming_debt <= 0:
        return {"error": "Mevcut borç, teminat, stres altındaki EV ve yeni borç pozitif olmalıdır."}

    clean_type = transaction_type.lower()
    if clean_type not in ["dropdown", "uptiering"]:
        clean_type = "dropdown"

    # Pre-Transaction Baseline
    baseline_collateral_coverage_pct = (collateral_value / existing_debt) * 100.0
    baseline_recovery_rate_pct = min(100.0, (distressed_ev / existing_debt) * 100.0)

    if clean_type == "dropdown":
        # J.Crew style: Dropdown asset transferred away to Unrestricted Sub
        post_collateral_value = max(0.0, collateral_value - dropdown_asset_value)
        collateral_leakage_pct = (dropdown_asset_value / collateral_value) * 100.0
        post_collateral_coverage_pct = (post_collateral_value / existing_debt) * 100.0

        # In distressed scenario: New priming debt has 1st lien on dropdown asset
        remaining_ev_for_legacy = max(0.0, distressed_ev - new_priming_debt)
        legacy_recovery_rate_pct = min(100.0, (remaining_ev_for_legacy / existing_debt) * 100.0)
        priming_recovery_rate_pct = min(100.0, (min(distressed_ev, dropdown_asset_value) / new_priming_debt) * 100.0)

        haircut_to_legacy_pct = round(baseline_recovery_rate_pct - legacy_recovery_rate_pct, 2)
        minority_recovery_rate_pct = legacy_recovery_rate_pct
        majority_recovery_rate_pct = legacy_recovery_rate_pct

        legal_vulnerability = "J.Crew Trapdoor Riski: Kısıtlanmamış iştirak yatırım sepeti (unrestricted sub basket) esnekliği ve teminat transferi."

    else:
        # Serta style: Majority lenders participate in Super-Priority Priming facility
        super_senior_debt = new_priming_debt + majority_debt
        subordinated_minority_debt = minority_debt

        # Distressed waterfall:
        available_for_super = min(distressed_ev, super_senior_debt)
        super_senior_recovery_rate_pct = (available_for_super / super_senior_debt) * 100.0

        # 2. Junior Subordinated Minority receives remainder
        remaining_for_minority = max(0.0, distressed_ev - super_senior_debt)
        if subordinated_minority_debt > 0:
            minority_recovery_rate_pct = min(100.0, (remaining_for_minority / subordinated_minority_debt) * 100.0)
        else:
            minority_recovery_rate_pct = 0.0

        majority_recovery_rate_pct = super_senior_recovery_rate_pct
        legacy_recovery_rate_pct = minority_recovery_rate_pct
        collateral_leakage_pct = 0.0
        post_collateral_value = collateral_value
        post_collateral_coverage_pct = baseline_collateral_coverage_pct
        haircut_to_legacy_pct = round(baseline_recovery_rate_pct - minority_recovery_rate_pct, 2)

        legal_vulnerability = "Serta Uptiering Riski: 'Sacred Rights' (Kutsal Haklar) pro-rata paylaşım ihlali ve iyi niyet (Good Faith) davaları."

    return {
        "transaction_type": clean_type.upper(),
        "existing_debt": round(existing_debt, 2),
        "initial_collateral_value": round(collateral_value, 2),
        "baseline_collateral_coverage_pct": round(baseline_collateral_coverage_pct, 2),
        "baseline_recovery_rate_pct": round(baseline_recovery_rate_pct, 2),
        "distressed_enterprise_value": round(distressed_ev, 2),
        "new_priming_debt_injected": round(new_priming_debt, 2),
        "collateral_leakage_pct": round(collateral_leakage_pct, 2),
        "post_collateral_coverage_pct": round(post_collateral_coverage_pct, 2),
        "majority_lender_recovery_rate_pct": round(majority_recovery_rate_pct, 2),
        "minority_lender_recovery_rate_pct": round(minority_recovery_rate_pct, 2),
        "minority_creditor_haircut_loss_pct": haircut_to_legacy_pct,
        "legal_and_covenant_vulnerability": legal_vulnerability,
        "distressed_tactics_diagnosis": (
            f"ALACAKLI ÇATIŞMASI: {clean_type.upper()} işlemi sonucunda dışarıda kalan alacaklılar "
            f"%{haircut_to_legacy_pct:.1f} telafi kaybına uğradı."
        )
    }


def calculate_hierarchical_risk_parity(
    asset_names: List[str],
    volatilities_pct: List[float],
    correlation_matrix: List[List[float]]
) -> Dict[str, Any]:
    """Calculates Hierarchical Risk Parity (HRP / Marcos Lopez de Prado):
    1. Distance matrix computation: D(i,j) = sqrt(0.5 * (1 - rho_i,j))
    2. Tree formation & clustering proxy.
    3. Quasi-diagonalization to group similar assets adjacently.
    4. Recursive Bisection with inverse-variance cluster allocation.
    Solves Markowitz Mean-Variance ill-conditioning and inversion instability.
    """
    n = len(asset_names)
    if n < 2 or len(volatilities_pct) != n or len(correlation_matrix) != n:
        return {"error": "Varlık sayısı en az 2 olmalı ve tüm matris boyutları eşleşmelidir."}

    for row in correlation_matrix:
        if len(row) != n:
            return {"error": "Korelasyon matrisi kare (N x N) olmalıdır."}

    # Step 1: Distance matrix: D_ij = sqrt(0.5 * (1 - rho_ij))
    distance_matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            rho = max(-1.0, min(1.0, correlation_matrix[i][j]))
            d = math.sqrt(max(0.0, 0.5 * (1.0 - rho)))
            row.append(d)
        distance_matrix.append(row)

    # Step 2 & 3: Simplified deterministic quasi-diagonalization order
    distances_to_first = [(distance_matrix[0][i], i) for i in range(n)]
    distances_to_first.sort()
    sorted_indices = [idx for _, idx in distances_to_first]

    sorted_assets = [asset_names[i] for i in sorted_indices]
    sorted_vols = [volatilities_pct[i] / 100.0 for i in sorted_indices]

    # Step 4: Recursive Bisection
    def _recursive_bisection(items: List[int], current_weights: Dict[int, float]):
        if len(items) <= 1:
            return

        mid = len(items) // 2
        left = items[:mid]
        right = items[mid:]

        inv_var_left = sum(1.0 / max(1e-6, (sorted_vols[i] ** 2)) for i in left)
        inv_var_right = sum(1.0 / max(1e-6, (sorted_vols[i] ** 2)) for i in right)

        var_left = 1.0 / max(1e-6, inv_var_left)
        var_right = 1.0 / max(1e-6, inv_var_right)

        alpha = 1.0 - (var_left / (var_left + var_right))

        for i in left:
            current_weights[i] *= alpha
        for i in right:
            current_weights[i] *= (1.0 - alpha)

        _recursive_bisection(left, current_weights)
        _recursive_bisection(right, current_weights)

    initial_weights = {i: 1.0 for i in range(len(sorted_indices))}
    _recursive_bisection(list(range(len(sorted_indices))), initial_weights)

    # Normalize weights
    total_w = sum(initial_weights.values())
    hrp_weights = {}
    for local_idx, raw_w in initial_weights.items():
        original_idx = sorted_indices[local_idx]
        hrp_weights[asset_names[original_idx]] = round((raw_w / total_w) * 100.0, 2)

    # Compare with standard Equal-Weight (1/N) and pure Inverse-Variance (IVP)
    inv_var_raw = [1.0 / max(1e-6, (v / 100.0) ** 2) for v in volatilities_pct]
    total_ivp = sum(inv_var_raw)
    ivp_weights = {asset_names[i]: round((inv_var_raw[i] / total_ivp) * 100.0, 2) for i in range(n)}
    equal_weight = round(100.0 / n, 2)

    return {
        "asset_count": n,
        "quasi_diagonalized_order": sorted_assets,
        "hrp_weights_pct": hrp_weights,
        "inverse_variance_weights_pct": ivp_weights,
        "equal_weight_benchmark_pct": equal_weight,
        "markowitz_condition_status": (
            "TEKİLLİK BAĞIŞIKLIĞI: HRP, Markowitz matris tersi alma zorunluluğunu kaldırarak "
            "kovaryans gürültü büyütmesini (noise amplification) engeller."
        )
    }


def calculate_dispersion_and_correlation_swap(
    index_implied_vol_pct: float,
    component_vols_pct: List[float],
    component_weights: List[float],
    realized_correlation: float,
    index_vega_notional: float = 100000.0,
    correlation_strike: float = 0.50
) -> Dict[str, Any]:
    """Calculates Correlation Swap & Dispersion Trading Arbitrage:
    - Implied Correlation from index vs single-stock implied volatilities.
    - Correlation Risk Premium (CRP) = rho_implied - rho_realized.
    - Dispersion trading structure (Short Index Vega + Long Component Stocks Vega).
    - Correlation Swap cash payoff.
    """
    if index_implied_vol_pct <= 0 or not component_vols_pct or not component_weights:
        return {"error": "Endeks volatilitesi ve hisse verileri pozitif ve geçerli olmalıdır."}

    n = len(component_vols_pct)
    if len(component_weights) != n:
        return {"error": "Bileşen volatiliteleri ile ağırlık listelerinin uzunluğu eşit olmalıdır."}

    # Normalize weights
    sum_w = sum(component_weights)
    if sum_w <= 0:
        return {"error": "Ağırlıklar toplamı pozitif olmalıdır."}
    w = [cw / sum_w for cw in component_weights]
    sigma_indiv = [v / 100.0 for v in component_vols_pct]
    sigma_idx = index_implied_vol_pct / 100.0

    # 1. Sum of weighted variances: sum(w_i^2 * sigma_i^2)
    var_indiv_sum = sum((w[i] ** 2) * (sigma_indiv[i] ** 2) for i in range(n))

    # 2. Cross product sum: sum_{i != j} (w_i * w_j * sigma_i * sigma_j)
    cross_sum = 0.0
    for i in range(n):
        for j in range(n):
            if i != j:
                cross_sum += w[i] * w[j] * sigma_indiv[i] * sigma_indiv[j]

    if cross_sum <= 0:
        return {"error": "Çapraz ağırlık-volatilite toplamı geçersiz."}

    # Implied Correlation calculation
    rho_implied = (sigma_idx ** 2 - var_indiv_sum) / cross_sum
    rho_implied = max(0.0, min(1.0, rho_implied))

    # Correlation Risk Premium (CRP)
    realized_corr_clamped = max(-1.0, min(1.0, realized_correlation))
    correlation_risk_premium = rho_implied - realized_corr_clamped

    # Dispersion PnL simulation (Short Index Straddle + Long Basket Straddles)
    dispersion_spread_gain = max(0.0, correlation_risk_premium)
    estimated_dispersion_pnl = round(index_vega_notional * dispersion_spread_gain * 100.0, 2)

    # Correlation Swap Payoff: Notional * (Realized Correlation - Correlation Strike)
    corr_swap_payoff = round(index_vega_notional * (realized_corr_clamped - correlation_strike), 2)

    # Diagnosis
    if correlation_risk_premium >= 0.15:
        regime = "GÜÇLÜ DAĞILIM (Long Dispersion): Zımni korelasyon aşırı şişmiş; endeks satıp hisse alma kârlı."
    elif correlation_risk_premium <= -0.05:
        regime = "TERS DAĞILIM (Short Dispersion): Gerçekleşen korelasyon zımniden yüksek; panik/kriz eşzamanlılığı."
    else:
        regime = "NÖTR KORELASYON: Zımni ve gerçekleşen korelasyon dengeli."

    return {
        "index_implied_vol_pct": round(index_implied_vol_pct, 2),
        "implied_correlation": round(rho_implied, 4),
        "realized_correlation": round(realized_corr_clamped, 4),
        "correlation_risk_premium": round(correlation_risk_premium, 4),
        "correlation_strike": round(correlation_strike, 4),
        "correlation_swap_payoff": corr_swap_payoff,
        "dispersion_arbitrage_pnl_estimate": estimated_dispersion_pnl,
        "index_vega_notional": round(index_vega_notional, 2),
        "dispersion_regime_diagnosis": regime
    }


def main():
    parser = argparse.ArgumentParser(
        description="Private Credit, Cat Bonds, LMT Distressed Maneuvers, HRP & Dispersion Trading Utility"
    )
    subparsers = parser.add_subparsers(dest="command", help="Komutlar")

    # 1. Private Credit & Unitranche
    pc_parser = subparsers.add_parser("private-credit", help="Özel Kredi, Unitranche ve Covenant Analizi")
    pc_parser.add_argument("--sofr", type=float, default=5.25, help="SOFR Taban Faizi (%)")
    pc_parser.add_argument("--margin", type=float, default=650.0, help="Nakit Kredi Marjı (bps)")
    pc_parser.add_argument("--oid", type=float, default=2.0, help="Original Issue Discount (OID %)")
    pc_parser.add_argument("--pik", type=float, default=150.0, help="PIK Tahakkuk Marjı (bps)")
    pc_parser.add_argument("--debt", type=float, required=True, help="Toplam Borç Tutarı")
    pc_parser.add_argument("--ebitda", type=float, required=True, help="Yıllık EBITDA")
    pc_parser.add_argument("--interest", type=float, required=True, help="Yıllık Faiz Gideri")
    pc_parser.add_argument("--capex", type=float, default=0.0, help="Yatırım Harcamaları (CapEx)")
    pc_parser.add_argument("--tax", type=float, default=0.0, help="Nakit Vergiler")
    pc_parser.add_argument("--tenor", type=float, default=5.0, help="Borç Vadesi (Yıl)")
    pc_parser.add_argument("--max-leverage", type=float, default=6.0, help="Maksimum Kaldıraç Kısıtı")
    pc_parser.add_argument("--min-fccr", type=float, default=1.20, help="Asgari FCCR Kısıtı")

    # 2. Cat Bonds & ILS
    cat_parser = subparsers.add_parser("cat-bond", help="Katastrof Tahvilleri (Cat Bond) ve ILS Analizi")
    cat_parser.add_argument("--principal", type=float, required=True, help="Teminat Anaparası")
    cat_parser.add_argument("--spread", type=float, required=True, help="Reasürans Prim Marjı (bps)")
    cat_parser.add_argument("--el", type=float, required=True, help="Modellenmiş Beklenen Yıllık Zarar (EL %)")
    cat_parser.add_argument("--attachment", type=float, required=True, help="Bağlanma (Attachment) Olasılığı (%)")
    cat_parser.add_argument("--exhaustion", type=float, required=True, help="Tükenme (Exhaustion) Olasılığı (%)")
    cat_parser.add_argument("--trigger", type=str, default="parametric", choices=["parametric", "indemnity", "industry_loss", "modeled_loss"])
    cat_parser.add_argument("--collateral-yield", type=float, default=4.50, help="Hazine Bonosu Teminat Getirisi (%)")

    # 3. LMT Distressed Maneuvers
    lmt_parser = subparsers.add_parser("lmt", help="Alacaklı Çatışması & Yükümlülük Yönetimi (Dropdown / Uptiering)")
    lmt_parser.add_argument("--existing-debt", type=float, required=True, help="Mevcut Borç Tutarı")
    lmt_parser.add_argument("--collateral", type=float, required=True, help="Mevcut Teminat Değeri")
    lmt_parser.add_argument("--dropdown-asset", type=float, default=0.0, help="Aktarılan Değerli Varlık (Dropdown)")
    lmt_parser.add_argument("--new-priming", type=float, required=True, help="Yeni Kıdemli Borç Tutarı")
    lmt_parser.add_argument("--minority-debt", type=float, default=0.0, help="Dışlanan Azınlık Alacaklı Borcu")
    lmt_parser.add_argument("--majority-debt", type=float, default=0.0, help="Katılan Çoğunluk Alacaklı Borcu")
    lmt_parser.add_argument("--distressed-ev", type=float, required=True, help="Stres Senaryosu Şirket Değeri (EV)")
    lmt_parser.add_argument("--type", type=str, default="dropdown", choices=["dropdown", "uptiering"], help="İşlem Tipi")

    # 4. Hierarchical Risk Parity (HRP)
    hrp_parser = subparsers.add_parser("hrp", help="Hiyerarşik Risk Paritesi (Lopez de Prado ML Portföy)")
    hrp_parser.add_argument("--assets", nargs="+", required=True, help="Varlık Sembolleri (örn: SPY TLT GLD VNQ)")
    hrp_parser.add_argument("--vols", nargs="+", type=float, required=True, help="Yıllık Volatiliteler (%)")
    hrp_parser.add_argument("--corr-flat", nargs="+", type=float, required=True, help="Düzleştirilmiş N x N Korelasyon Matrisi")

    # 5. Correlation Swaps & Dispersion Trading
    disp_parser = subparsers.add_parser("dispersion", help="Korelasyon Takası ve Dağılım Arbitrajı")
    disp_parser.add_argument("--index-iv", type=float, required=True, help="Endeks İma Edilen Volatilitesi (%)")
    disp_parser.add_argument("--component-ivs", nargs="+", type=float, required=True, help="Bileşen Volatiliteleri (%)")
    disp_parser.add_argument("--weights", nargs="+", type=float, required=True, help="Bileşen Ağırlıkları")
    disp_parser.add_argument("--realized-corr", type=float, required=True, help="Gerçekleşen Ortalama Korelasyon")
    disp_parser.add_argument("--vega-notional", type=float, default=100000.0, help="Endeks Vega Pozisyon Boyutu ($)")
    disp_parser.add_argument("--corr-strike", type=float, default=0.50, help="Korelasyon Takası Uygulama Değeri")

    args = parser.parse_args()

    if args.command == "private-credit":
        res = calculate_private_credit_and_unitranche(
            sofr_pct=args.sofr,
            margin_spread_bps=args.margin,
            oid_pct=args.oid,
            pik_spread_bps=args.pik,
            total_debt=args.debt,
            ebitda=args.ebitda,
            interest_expense=args.interest,
            capex=args.capex,
            tax_expense=args.tax,
            tenor_years=args.tenor,
            covenant_max_leverage=args.max_leverage,
            covenant_min_fccr=args.min_fccr
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "cat-bond":
        res = calculate_cat_bond_and_ils(
            collateral_principal=args.principal,
            spread_bps=args.spread,
            expected_loss_pct=args.el,
            attachment_prob_pct=args.attachment,
            exhaustion_prob_pct=args.exhaustion,
            trigger_type=args.trigger,
            collateral_yield_pct=args.collateral_yield
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "lmt":
        res = calculate_lmt_dropdown_uptiering(
            existing_debt=args.existing_debt,
            collateral_value=args.collateral,
            dropdown_asset_value=args.dropdown_asset,
            new_priming_debt=args.new_priming,
            minority_debt=args.minority_debt,
            majority_debt=args.majority_debt,
            distressed_ev=args.distressed_ev,
            transaction_type=args.type
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "hrp":
        n = len(args.assets)
        if len(args.corr_flat) != n * n:
            print(json.dumps({"error": f"{n} varlık için {n*n} adet korelasyon değeri girilmelidir."}, ensure_ascii=False))
            return
        corr_matrix = [args.corr_flat[i*n : (i+1)*n] for i in range(n)]
        res = calculate_hierarchical_risk_parity(
            asset_names=args.assets,
            volatilities_pct=args.vols,
            correlation_matrix=corr_matrix
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "dispersion":
        res = calculate_dispersion_and_correlation_swap(
            index_implied_vol_pct=args.index_iv,
            component_vols_pct=args.component_ivs,
            component_weights=args.weights,
            realized_correlation=args.realized_corr,
            index_vega_notional=args.vega_notional,
            correlation_strike=args.corr_strike
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
