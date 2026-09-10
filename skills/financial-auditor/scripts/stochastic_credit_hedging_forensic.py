#!/usr/bin/env python3
"""CLI and library utility for Stochastic Rates, Credit Portfolio Copula, Deep Hedging,
Forensic Off-Balance SPV / Reverse Factoring & ISDA Restructuring:
1. Hull-White 1-Factor Interest Rate Model & Bermudan Swaption LSM (Least Squares Monte Carlo)
2. Credit Portfolio Risk, David X. Li Gaussian Copula vs Student-t & Synthetic CDO Tranches
3. Deep Hedging, Marcos Lopez de Prado Fractional Differentiation & Metalabeling Bet Sizing
4. Forensic Cash Flow, Reverse Factoring (Greensill/Carillion) & Off-Balance Sheet SPV Hidden Debt
5. ISDA Determinations Committee Credit Events, Cheapest-to-Deliver (CTD) & Manufactured Default
"""

import argparse
import json
import math
import random
from typing import Dict, Any, List, Optional, Tuple


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_inv(p: float) -> float:
    """Approximation of the inverse normal cumulative distribution function (Acklam algorithm)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Olasılık 0 ile 1 arasında kesin açık aralıkta olmalıdır.")

    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
               (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)


def calculate_hull_white_swaption_lsm(
    notional: float,
    strike_rate: float,
    tenor_years: float,
    exercise_years: List[float],
    mean_reversion_a: float,
    volatility_sigma: float,
    initial_short_rate: float,
    n_simulations: int = 1500,
    seed: int = 42
) -> Dict[str, Any]:
    """Hull-White 1-Factor Interest Rate Model & Bermudan Swaption Valuation via
    Longstaff-Schwartz Least Squares Monte Carlo (LSM):
    - dr(t) = [theta(t) - a*r(t)]dt + sigma*dW(t)
    - Zero Coupon Bond analytical formula P(t, T) = A(t, T) * exp(-B(t, T)*r(t))
    - Swap NPV calculation at each Bermudan exercise date
    - Backward induction regression of continuation values for optimal early exercise
    """
    if notional <= 0.0:
        return {"error": "Nominal değer pozitif olmalıdır."}
    if strike_rate <= 0.0 or strike_rate >= 1.0:
        return {"error": "Kullanım faiz oranı (strike_rate) 0 ile 1 arasında olmalıdır."}
    if mean_reversion_a <= 0.0:
        return {"error": "Ortalamaya dönüş hızı (mean_reversion_a) pozitif olmalıdır."}
    if volatility_sigma <= 0.0:
        return {"error": "Stokastik faiz oynaklığı (volatility_sigma) pozitif olmalıdır."}
    if not exercise_years:
        return {"error": "En az bir egzersiz tarihi (exercise_years) belirtilmelidir."}

    sorted_exercises = sorted([float(e) for e in exercise_years if 0.0 < e < tenor_years])
    if not sorted_exercises:
        return {"error": "Egzersiz tarihleri 0 ile swap vadesi (tenor) arasında olmalıdır."}

    rng = random.Random(seed)

    # Analytic B(t, T) helper
    def B(t: float, T: float) -> float:
        return (1.0 - math.exp(-mean_reversion_a * (T - t))) / mean_reversion_a

    # Flat initial forward curve approximation f(0, t) = initial_short_rate
    # P(0, T) = exp(-initial_short_rate * T)
    def P_0(T: float) -> float:
        return math.exp(-initial_short_rate * T)

    def A(t: float, T: float) -> float:
        b_val = B(t, T)
        p_ratio = P_0(T) / max(1e-12, P_0(t))
        term = b_val * initial_short_rate - (volatility_sigma**2 / (4.0 * mean_reversion_a)) * (1.0 - math.exp(-2.0 * mean_reversion_a * t)) * (b_val**2)
        return p_ratio * math.exp(term)

    def bond_price(t: float, T: float, r_t: float) -> float:
        return A(t, T) * math.exp(-B(t, T) * r_t)

    # Payoff of Payer Swaption at time t with underlying swap maturing at tenor_years
    # Fixed payer receives floating, pays fixed strike
    def swap_npv(t: float, r_t: float) -> float:
        remaining_payments = []
        cur = math.floor(t) + 1.0
        while cur <= tenor_years:
            if cur > t:
                remaining_payments.append(cur)
            cur += 1.0
        if not remaining_payments:
            return 0.0

        p_end = bond_price(t, tenor_years, r_t)
        annuity = sum(bond_price(t, ti, r_t) for ti in remaining_payments)
        if annuity <= 0.0:
            return 0.0
        par_swap_rate = (1.0 - p_end) / annuity
        intrinsic = notional * max(0.0, par_swap_rate - strike_rate) * annuity
        return intrinsic

    num_steps_per_year = 10
    total_steps = int(math.ceil(sorted_exercises[-1] * num_steps_per_year))
    dt = sorted_exercises[-1] / max(1, total_steps)

    time_grid = [step * dt for step in range(total_steps + 1)]
    exercise_step_indices = []
    for ex in sorted_exercises:
        idx = min(range(len(time_grid)), key=lambda i: abs(time_grid[i] - ex))
        exercise_step_indices.append(idx)

    paths_r = []
    paths_disc = []
    for _ in range(n_simulations):
        r = initial_short_rate
        path_r_steps = [r]
        disc = 1.0
        path_disc_steps = [disc]

        for step_idx in range(total_steps):
            t_cur = time_grid[step_idx]
            theta_t = mean_reversion_a * initial_short_rate + (volatility_sigma**2 / (2.0 * mean_reversion_a)) * (1.0 - math.exp(-2.0 * mean_reversion_a * t_cur))
            dr = (theta_t - mean_reversion_a * r) * dt + volatility_sigma * math.sqrt(dt) * rng.gauss(0.0, 1.0)
            r += dr
            disc *= math.exp(-r * dt)
            path_r_steps.append(r)
            path_disc_steps.append(disc)

        paths_r.append(path_r_steps)
        paths_disc.append(path_disc_steps)

    # Longstaff-Schwartz Backward Induction
    num_exercises = len(sorted_exercises)
    cash_flows = [0.0] * n_simulations
    exercise_time_idx = [exercise_step_indices[-1]] * n_simulations

    last_ex_step = exercise_step_indices[-1]
    last_ex_time = time_grid[last_ex_step]
    for p in range(n_simulations):
        r_val = paths_r[p][last_ex_step]
        cash_flows[p] = swap_npv(last_ex_time, r_val)

    for ex_k in range(num_exercises - 2, -1, -1):
        step_k = exercise_step_indices[ex_k]
        t_k = time_grid[step_k]

        itm_indices = []
        x_vals = []
        y_vals = []

        for p in range(n_simulations):
            r_val = paths_r[p][step_k]
            payoff = swap_npv(t_k, r_val)
            if payoff > 0.0:
                itm_indices.append(p)
                x_vals.append(r_val)
                fut_step = exercise_time_idx[p]
                fut_disc = paths_disc[p][fut_step] / max(1e-12, paths_disc[p][step_k])
                y_vals.append(cash_flows[p] * fut_disc)

        if len(itm_indices) > 5:
            sum_1 = float(len(x_vals))
            sum_x = sum(x_vals)
            sum_x2 = sum(x**2 for x in x_vals)
            sum_x3 = sum(x**3 for x in x_vals)
            sum_x4 = sum(x**4 for x in x_vals)
            sum_y = sum(y_vals)
            sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
            sum_x2y = sum((x**2) * y for x, y in zip(x_vals, y_vals))

            M = [
                [sum_1, sum_x, sum_x2, sum_y],
                [sum_x, sum_x2, sum_x3, sum_xy],
                [sum_x2, sum_x3, sum_x4, sum_x2y]
            ]
            try:
                for i in range(3):
                    pivot = M[i][i]
                    if abs(pivot) < 1e-10:
                        raise ZeroDivisionError
                    for j in range(i, 4):
                        M[i][j] /= pivot
                    for k in range(3):
                        if k != i:
                            factor = M[k][i]
                            for j in range(i, 4):
                                M[k][j] -= factor * M[i][j]
                beta0, beta1, beta2 = M[0][3], M[1][3], M[2][3]
            except Exception:
                mean_x = sum_x / sum_1
                mean_y = sum_y / sum_1
                cov_xy = sum_xy - sum_1 * mean_x * mean_y
                var_x = max(1e-9, sum_x2 - sum_1 * mean_x**2)
                beta1 = cov_xy / var_x
                beta0 = mean_y - beta1 * mean_x
                beta2 = 0.0

            for idx, p in enumerate(itm_indices):
                r_val = x_vals[idx]
                cont_val = max(0.0, beta0 + beta1 * r_val + beta2 * (r_val**2))
                imm_payoff = swap_npv(t_k, r_val)
                if imm_payoff > cont_val:
                    cash_flows[p] = imm_payoff
                    exercise_time_idx[p] = step_k

    pv_bermudan = sum(cash_flows[p] * paths_disc[p][exercise_time_idx[p]] for p in range(n_simulations)) / n_simulations

    first_ex_step = exercise_step_indices[0]
    first_ex_time = time_grid[first_ex_step]
    pv_european = sum(swap_npv(first_ex_time, paths_r[p][first_ex_step]) * paths_disc[p][first_ex_step] for p in range(n_simulations)) / n_simulations

    early_exercise_premium = max(0.0, pv_bermudan - pv_european)
    early_ex_prob_pct = round((sum(1 for p in range(n_simulations) if exercise_time_idx[p] < last_ex_step and cash_flows[p] > 0) / n_simulations) * 100.0, 2)

    return {
        "bermudan_swaption_price": round(pv_bermudan, 2),
        "european_swaption_price": round(pv_european, 2),
        "early_exercise_premium": round(early_exercise_premium, 2),
        "early_exercise_probability_pct": early_ex_prob_pct,
        "parameters": {
            "notional": notional,
            "strike_rate_pct": round(strike_rate * 100.0, 2),
            "tenor_years": tenor_years,
            "exercise_schedule": sorted_exercises,
            "mean_reversion_a": mean_reversion_a,
            "volatility_sigma": volatility_sigma,
            "initial_short_rate_pct": round(initial_short_rate * 100.0, 2),
            "simulations": n_simulations
        },
        "model_verdict": (
            "Yüksek Erken Egzersiz Primi (Bermudan Avantajı Belirgin)"
            if early_exercise_premium > 0.10 * pv_bermudan and pv_bermudan > 0
            else "Ilımlı / Düşük Erken Egzersiz Avantajı"
        )
    }


def calculate_credit_portfolio_copula_cdo(
    n_issuers: int,
    notional_per_issuer: float,
    default_probability: float,
    lgd_rate: float,
    asset_correlation: float,
    tranches: Optional[List[Dict[str, float]]] = None,
    copula_type: str = "gaussian",
    t_copula_df: float = 4.0,
    n_simulations: int = 2000,
    seed: int = 42
) -> Dict[str, Any]:
    """Credit Portfolio Multi-Default Risk & Synthetic CDO Tranche Valuation:
    - 1-Factor Latent Asset Model: X_i = sqrt(rho)*M + sqrt(1 - rho)*Z_i
    - Li Gaussian Copula vs Student-t Copula (Subprime tail dependence test)
    - Tranche loss waterfall: Equity (0-3%), Mezzanine (3-7%), Senior (7-10%), Super-Senior (10-100%)
    - Basel Credit Risk Capital & Tail Risk Comparison
    """
    if n_issuers <= 1:
        return {"error": "İhraççı sayısı (n_issuers) en az 2 olmalıdır."}
    if notional_per_issuer <= 0.0:
        return {"error": "İhraççı başına nominal tutar pozitif olmalıdır."}
    if default_probability <= 0.0 or default_probability >= 1.0:
        return {"error": "Temerrüt olasılığı (default_probability) 0 ile 1 arasında olmalıdır."}
    if lgd_rate <= 0.0 or lgd_rate > 1.0:
        return {"error": "Temerrüt halinde kayıp (lgd_rate) 0 ile 1 arasında olmalıdır."}
    if asset_correlation < 0.0 or asset_correlation >= 1.0:
        return {"error": "Varlık korelasyonu (asset_correlation) 0 ile 1 arasında olmalıdır."}

    if not tranches:
        tranches = [
            {"name": "Equity", "attach": 0.00, "detach": 0.03},
            {"name": "Mezzanine", "attach": 0.03, "detach": 0.07},
            {"name": "Senior", "attach": 0.07, "detach": 0.10},
            {"name": "Super Senior", "attach": 0.10, "detach": 1.00}
        ]

    rng = random.Random(seed)
    total_portfolio_notional = n_issuers * notional_per_issuer
    norm_thresh = _norm_inv(default_probability)

    simulated_portfolio_losses = []
    tranche_cum_losses = {t["name"]: 0.0 for t in tranches}
    defaults_count_list = []

    sqrt_rho = math.sqrt(asset_correlation)
    sqrt_1_minus_rho = math.sqrt(1.0 - asset_correlation)
    is_t_copula = (copula_type.lower() == "t" or copula_type.lower() == "student-t")

    for _ in range(n_simulations):
        m_factor = rng.gauss(0.0, 1.0)

        if is_t_copula:
            chi_sq = sum(rng.gauss(0.0, 1.0)**2 for _ in range(int(math.ceil(t_copula_df))))
            scale_w = math.sqrt(chi_sq / t_copula_df)
        else:
            scale_w = 1.0

        num_defaults = 0
        for _ in range(n_issuers):
            z_i = rng.gauss(0.0, 1.0)
            latent_x = (sqrt_rho * m_factor + sqrt_1_minus_rho * z_i) / max(1e-6, scale_w)
            if latent_x < norm_thresh:
                num_defaults += 1

        loss_amount = num_defaults * notional_per_issuer * lgd_rate
        loss_pct = loss_amount / total_portfolio_notional
        simulated_portfolio_losses.append(loss_pct)
        defaults_count_list.append(num_defaults)

        for t in tranches:
            attach = t["attach"]
            detach = t["detach"]
            width = detach - attach
            t_loss = min(width, max(0.0, loss_pct - attach))
            tranche_cum_losses[t["name"]] += t_loss

    avg_portfolio_loss_pct = sum(simulated_portfolio_losses) / n_simulations
    sorted_losses = sorted(simulated_portfolio_losses)
    var_99_loss_pct = sorted_losses[int(0.99 * n_simulations)]
    cvar_99_loss_pct = sum(sorted_losses[int(0.99 * n_simulations):]) / max(1, len(sorted_losses) - int(0.99 * n_simulations))

    tranche_results = []
    for t in tranches:
        width = t["detach"] - t["attach"]
        expected_tranche_loss = tranche_cum_losses[t["name"]] / n_simulations
        expected_tranche_loss_pct_of_tranche = round((expected_tranche_loss / width) * 100.0, 2)
        expected_dollar_loss = round(expected_tranche_loss * total_portfolio_notional, 2)
        tranche_results.append({
            "tranche": t["name"],
            "attachment_pct": round(t["attach"] * 100.0, 1),
            "detachment_pct": round(t["detach"] * 100.0, 1),
            "tranche_thickness_pct": round(width * 100.0, 1),
            "expected_loss_pct_of_tranche": expected_tranche_loss_pct_of_tranche,
            "expected_dollar_loss": expected_dollar_loss
        })

    return {
        "copula_model": "Student-t Copula (Fat Tail / Extreme Clustering)" if is_t_copula else "David X. Li Gaussian Copula",
        "issuers_count": n_issuers,
        "total_notional": total_portfolio_notional,
        "expected_portfolio_loss_pct": round(avg_portfolio_loss_pct * 100.0, 3),
        "expected_portfolio_loss_dollar": round(avg_portfolio_loss_pct * total_portfolio_notional, 2),
        "portfolio_var_99_pct": round(var_99_loss_pct * 100.0, 3),
        "portfolio_cvar_99_pct": round(cvar_99_loss_pct * 100.0, 3),
        "tranche_breakdown": tranche_results,
        "max_simulated_defaults": max(defaults_count_list),
        "risk_assessment": (
            "Kritik Kuyruk Çöküş Riski (Student-t Copula ile Kıdemli Dilim Kayıpları Yüksek)"
            if is_t_copula and cvar_99_loss_pct > 0.08
            else "Standart Gaussian Dağılımı (Kuyruk Riski Düşük Tahmin Edilmiş Olabilir)"
        )
    }


def calculate_deep_hedging_and_fractional_differentiation(
    prices: List[float],
    d_order: float = 0.40,
    weight_threshold: float = 1e-4,
    primary_predictions: Optional[List[int]] = None,
    meta_confidences: Optional[List[float]] = None,
    transaction_cost_bps: float = 10.0
) -> Dict[str, Any]:
    """Marcos Lopez de Prado's Fractional Differentiation & Metalabeling with Deep Hedging CVaR:
    - (1 - B)^d expansion weights calculation for memory preservation with stationarity
    - Fractional differentiated series generation and correlation retention
    - Metalabeling two-step architecture: Primary direction + Meta-model bet sizing
    - Friction-adjusted Deep Hedging CVaR risk metric
    """
    if len(prices) < 10:
        return {"error": "Fiyat serisi en az 10 gözlem içermelidir."}
    if d_order < 0.0 or d_order > 1.0:
        return {"error": "Kesirli fark derecesi (d_order) 0 ile 1 arasında olmalıdır."}

    # Limit weight history to avoid exceeding available price length
    max_history = max(2, min(len(prices) // 2, 50))
    weights = [1.0]
    k = 1
    while k < max_history:
        w_k = -weights[-1] * (d_order - k + 1.0) / k
        if abs(w_k) < weight_threshold:
            break
        weights.append(w_k)
        k += 1

    frac_diff_series = []
    num_w = len(weights)
    for i in range(len(prices)):
        if i < num_w - 1:
            frac_diff_series.append(0.0)
        else:
            val = sum(weights[j] * prices[i - j] for j in range(num_w))
            frac_diff_series.append(val)

    valid_prices = prices[num_w - 1:]
    valid_frac = frac_diff_series[num_w - 1:]

    if len(valid_prices) >= 2:
        mean_p = sum(valid_prices) / len(valid_prices)
        mean_f = sum(valid_frac) / len(valid_frac)
        cov_pf = sum((p - mean_p) * (f - mean_f) for p, f in zip(valid_prices, valid_frac))
        var_p = sum((p - mean_p)**2 for p in valid_prices)
        var_f = sum((f - mean_f)**2 for f in valid_frac)
        memory_retention_corr = round(cov_pf / max(1e-12, math.sqrt(var_p * var_f)), 4)
    else:
        memory_retention_corr = 1.0

    n_pts = len(prices) - 1
    if not primary_predictions or len(primary_predictions) != n_pts:
        primary_predictions = [1 if prices[i+1] >= prices[i] else -1 for i in range(n_pts)]

    if not meta_confidences or len(meta_confidences) != n_pts:
        meta_confidences = [min(0.95, max(0.40, 0.50 + abs(prices[i+1] - prices[i]) / prices[i] * 5.0)) for i in range(n_pts)]

    raw_returns = []
    metalabeled_returns = []
    cost_rate = transaction_cost_bps / 10000.0

    for i in range(n_pts):
        actual_ret = (prices[i+1] - prices[i]) / prices[i]
        prim_dir = primary_predictions[i]
        meta_prob = meta_confidences[i]

        raw_pnl = (prim_dir * actual_ret) - cost_rate
        raw_returns.append(raw_pnl)

        bet_size = max(0.0, 2.0 * meta_prob - 1.0)
        meta_pnl = (prim_dir * actual_ret * bet_size) - (cost_rate * bet_size)
        metalabeled_returns.append(meta_pnl)

    cum_raw = sum(raw_returns)
    cum_meta = sum(metalabeled_returns)

    sorted_meta_ret = sorted(metalabeled_returns)
    var_idx = int(0.05 * len(sorted_meta_ret))
    cvar_95_drawdown = -sum(sorted_meta_ret[:max(1, var_idx)]) / max(1, var_idx)

    return {
        "fractional_order_d": d_order,
        "filter_weights_count": len(weights),
        "memory_correlation_retained": memory_retention_corr,
        "metalabeling_summary": {
            "total_trades": n_pts,
            "raw_strategy_cumulative_return_pct": round(cum_raw * 100.0, 2),
            "metalabeled_strategy_cumulative_return_pct": round(cum_meta * 100.0, 2),
            "performance_boost_pct": round(((cum_meta - cum_raw) / max(1e-6, abs(cum_raw))) * 100.0, 2),
            "metalabeled_cvar_95_downside_pct": round(cvar_95_drawdown * 100.0, 2)
        },
        "hedging_verdict": (
            "Kuvvetli Bellek Korunumu ve Üstün Metalabeling Filtreleme"
            if memory_retention_corr > 0.70 and cum_meta > cum_raw
            else "Durağanlık Öncelikli, Kısmi Bellek Kaybı"
        )
    }


def calculate_forensic_reverse_factoring_spv(
    revenue: float,
    cogs: float,
    reported_cfo: float,
    capex: float,
    short_term_debt: float,
    long_term_debt: float,
    cash_and_equiv: float,
    reported_ebitda: float,
    accounts_receivable: float,
    inventory: float,
    accounts_payable: float,
    reverse_factoring_hidden_payable: float,
    off_balance_sheet_spv_debt: float,
    unbilled_receivables: float,
    doubtful_debt_allowance: float,
    prior_doubtful_debt_allowance: float
) -> Dict[str, Any]:
    """Forensic Accounting Analysis for Hidden Off-Balance Sheet Debt & Reverse Factoring:
    - Working Capital days: DSO, DIO, DPO and Cash Conversion Cycle (CCC)
    - Greensill / Carillion style CFO distortion adjustments: Adjusted CFO = Reported CFO - Reverse Factoring
    - Adjusted Net Debt = Balance Sheet Debt + Reverse Factoring + SPV Debt - Cash
    - Unbilled Receivables & Cookie Jar reserve manipulation tests
    """
    if revenue <= 0.0:
        return {"error": "Hasılat (revenue) pozitif olmalıdır."}
    if cogs <= 0.0:
        return {"error": "Satışların Maliyeti (COGS) pozitif olmalıdır."}
    if reported_ebitda <= 0.0:
        return {"error": "Raporlanan FAVÖK (EBITDA) pozitif olmalıdır."}

    dso = round((accounts_receivable / revenue) * 365.0, 1)
    dio = round((inventory / cogs) * 365.0, 1)
    dpo_reported = round((accounts_payable / cogs) * 365.0, 1)
    dpo_true_trade = round((max(0.0, accounts_payable - reverse_factoring_hidden_payable) / cogs) * 365.0, 1)
    ccc_reported = round(dso + dio - dpo_reported, 1)
    ccc_adjusted = round(dso + dio - dpo_true_trade, 1)

    reported_net_debt = (short_term_debt + long_term_debt) - cash_and_equiv
    adjusted_net_debt = reported_net_debt + reverse_factoring_hidden_payable + off_balance_sheet_spv_debt

    reported_fcf = reported_cfo - capex
    adjusted_cfo = reported_cfo - reverse_factoring_hidden_payable
    adjusted_fcf = adjusted_cfo - capex

    reported_leverage = round(reported_net_debt / reported_ebitda, 2)
    adjusted_leverage = round(adjusted_net_debt / reported_ebitda, 2)

    unbilled_pct_of_ar = round((unbilled_receivables / max(1e-6, accounts_receivable)) * 100.0, 1)
    allowance_delta = doubtful_debt_allowance - prior_doubtful_debt_allowance

    red_flags = []
    if reverse_factoring_hidden_payable > 0.20 * accounts_payable:
        red_flags.append("Ters Faktoring (Reverse Factoring) ile Ticari Borçlarda Gizlenen Banka Kredisi")
    if off_balance_sheet_spv_debt > 0.15 * (short_term_debt + long_term_debt):
        red_flags.append("Bilanço Dışı SPV ile Konsolidasyondan Kaçırılan Finansal Borç")
    if unbilled_pct_of_ar > 25.0:
        red_flags.append(f"Faturası Kesilmemiş Alacaklar Anomalisi (Toplam AR'ın %{unbilled_pct_of_ar}'i)")
    if allowance_delta < 0 and revenue > 0:
        red_flags.append("Cookie Jar Rezervi: Alacak Karşılığı Azaltılarak Suni Faaliyet Kârı Yaratımı")
    if adjusted_leverage - reported_leverage >= 1.5:
        red_flags.append(f"Kritik Kaldıraç Gizleme (Raporlanan {reported_leverage}x -> Gerçek {adjusted_leverage}x)")

    forensic_risk_score = len(red_flags)
    if forensic_risk_score >= 3:
        risk_verdict = "Ağır Manipülasyon & Gizli İflas Riski (Carillion / Greensill Vakası)"
    elif forensic_risk_score >= 1:
        risk_verdict = "Orta Düzey Finansal Mühendislik ve Bilanço Dışı Kaldıraç"
    else:
        risk_verdict = "Düşük Forensik Risk (Şeffaf Bilanço ve Nakit Akışı)"

    return {
        "working_capital_days": {
            "dso_days": dso,
            "dio_days": dio,
            "dpo_reported_days": dpo_reported,
            "dpo_true_trade_days": dpo_true_trade,
            "cash_conversion_cycle_reported": ccc_reported,
            "cash_conversion_cycle_adjusted": ccc_adjusted
        },
        "reported_metrics": {
            "cfo": reported_cfo,
            "fcf": reported_fcf,
            "net_debt": reported_net_debt,
            "net_debt_to_ebitda": reported_leverage
        },
        "forensic_adjusted_metrics": {
            "adjusted_cfo": adjusted_cfo,
            "adjusted_fcf": adjusted_fcf,
            "adjusted_net_debt": adjusted_net_debt,
            "adjusted_net_debt_to_ebitda": adjusted_leverage,
            "hidden_debt_total": reverse_factoring_hidden_payable + off_balance_sheet_spv_debt
        },
        "forensic_indicators": {
            "unbilled_receivables_pct_ar": unbilled_pct_of_ar,
            "allowance_delta": allowance_delta,
            "red_flags_detected": red_flags,
            "risk_score": forensic_risk_score,
            "forensic_verdict": risk_verdict
        }
    }


def calculate_isda_restructuring_ctd(
    cds_spread_bps: float,
    notional: float,
    deliverable_bonds: List[Dict[str, Any]],
    is_manufactured_default: bool = False
) -> Dict[str, Any]:
    """ISDA Determinations Committee (DC) Credit Events & Cheapest-to-Deliver (CTD) Mechanics:
    - Deliverable Obligations universe sorting to find the cheapest bond
    - Auction Recovery Rate (RR) determination
    - Net CDS Payout = (100% - CTD_Price) * Notional
    - 2019 ISDA Narrowly Tailored Credit Event (NTCE) Manufactured Default defense rule
    """
    if not deliverable_bonds:
        return {"error": "En az bir teslim edilebilir tahvil (deliverable_bonds) tanımlanmalıdır."}
    if notional <= 0.0:
        return {"error": "Nominal tutar pozitif olmalıdır."}

    if is_manufactured_default:
        return {
            "isda_decision": "KREDİ OLAYI REDDEDİLDİ (NTCE KURAL İHLALİ)",
            "credit_event_recognized": False,
            "reason": "ISDA 2019 Dar Kapsamlı Kredi Olayı Kuralı: Meşru ekonomik sıkıntı olmaksızın CDS kârı için suni yaratılan temerrütler geçersizdir (Hovnanian / GSO Blackstone emsali).",
            "net_cds_payout": 0.0,
            "cheapest_to_deliver_isin": None
        }

    sorted_bonds = sorted(deliverable_bonds, key=lambda b: b.get("market_price", 100.0))
    ctd_bond = sorted_bonds[0]
    ctd_price = ctd_bond.get("market_price", 100.0)

    recovery_rate_pct = round(ctd_price, 2)
    loss_given_default_pct = round(100.0 - recovery_rate_pct, 2)
    net_cds_payout = round(notional * (loss_given_default_pct / 100.0), 2)

    mat = max(0.5, ctd_bond.get("maturity_years", 5.0))
    implied_bond_spread_bps = round(((100.0 - ctd_price) / mat) * 100.0, 1)
    cds_bond_basis_bps = round(cds_spread_bps - implied_bond_spread_bps, 1)

    return {
        "isda_decision": "KREDİ OLAYI ONAYLANDI (Determination Event)",
        "credit_event_recognized": True,
        "cheapest_to_deliver_bond": {
            "isin": ctd_bond.get("isin", "UNKNOWN"),
            "market_price": ctd_price,
            "coupon_pct": ctd_bond.get("coupon_pct", 0.0),
            "maturity_years": ctd_bond.get("maturity_years", 5.0)
        },
        "auction_recovery_rate_pct": recovery_rate_pct,
        "loss_given_default_pct": loss_given_default_pct,
        "net_cds_payout": net_cds_payout,
        "cds_spread_bps": cds_spread_bps,
        "implied_bond_spread_bps": implied_bond_spread_bps,
        "cds_bond_basis_bps": cds_bond_basis_bps,
        "basis_interpretation": (
            "Pozitif Baz (CDS Tahvilden Pahalı, Koruma Talebi Yüksek)"
            if cds_bond_basis_bps > 0
            else "Negatif Baz (Tahvil İskontosu CDS Spreadini Aşıyor, Arbitraj Fırsatı)"
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Stochastic Rates, Credit Portfolio Copula, Deep Hedging & Forensic Analysis CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    hw_p = subparsers.add_parser("hull-white", help="Hull-White Bermudan Swaption LSM")
    hw_p.add_argument("--notional", type=float, default=10000000.0)
    hw_p.add_argument("--strike", type=float, default=0.04)
    hw_p.add_argument("--tenor", type=float, default=5.0)
    hw_p.add_argument("--exercises", type=float, nargs="+", default=[1.0, 2.0, 3.0, 4.0])
    hw_p.add_argument("--mean-reversion", type=float, default=0.05)
    hw_p.add_argument("--volatility", type=float, default=0.015)
    hw_p.add_argument("--short-rate", type=float, default=0.035)

    copula_p = subparsers.add_parser("credit-copula", help="Credit Portfolio Copula & CDO Tranches")
    copula_p.add_argument("--issuers", type=int, default=100)
    copula_p.add_argument("--notional-per-issuer", type=float, default=1000000.0)
    copula_p.add_argument("--pd", type=float, default=0.03)
    copula_p.add_argument("--lgd", type=float, default=0.60)
    copula_p.add_argument("--correlation", type=float, default=0.25)
    copula_p.add_argument("--copula", type=str, default="gaussian")

    frac_p = subparsers.add_parser("frac-diff", help="Fractional Differentiation & Metalabeling")
    frac_p.add_argument("--prices", type=float, nargs="+", default=[100.0, 102.0, 101.5, 103.0, 105.0, 104.0, 106.0, 108.0, 107.5, 109.0, 111.0, 110.0])
    frac_p.add_argument("--d", type=float, default=0.40)

    forensic_p = subparsers.add_parser("forensic", help="Forensic Reverse Factoring & SPV Debt")
    forensic_p.add_argument("--revenue", type=float, required=True)
    forensic_p.add_argument("--cogs", type=float, required=True)
    forensic_p.add_argument("--cfo", type=float, required=True)
    forensic_p.add_argument("--capex", type=float, required=True)
    forensic_p.add_argument("--debt-st", type=float, required=True)
    forensic_p.add_argument("--debt-lt", type=float, required=True)
    forensic_p.add_argument("--cash", type=float, required=True)
    forensic_p.add_argument("--ebitda", type=float, required=True)
    forensic_p.add_argument("--ar", type=float, required=True)
    forensic_p.add_argument("--inv", type=float, required=True)
    forensic_p.add_argument("--ap", type=float, required=True)
    forensic_p.add_argument("--reverse-factoring", type=float, required=True)
    forensic_p.add_argument("--spv-debt", type=float, default=0.0)
    forensic_p.add_argument("--unbilled", type=float, default=0.0)
    forensic_p.add_argument("--doubtful", type=float, default=0.0)
    forensic_p.add_argument("--prior-doubtful", type=float, default=0.0)

    isda_p = subparsers.add_parser("isda-ctd", help="ISDA Credit Event & CTD")
    isda_p.add_argument("--spread", type=float, default=350.0)
    isda_p.add_argument("--notional", type=float, default=10000000.0)
    isda_p.add_argument("--manufactured", action="store_true")

    args = parser.parse_args()

    if args.command == "hull-white":
        res = calculate_hull_white_swaption_lsm(
            notional=args.notional,
            strike_rate=args.strike,
            tenor_years=args.tenor,
            exercise_years=args.exercises,
            mean_reversion_a=args.mean_reversion,
            volatility_sigma=args.volatility,
            initial_short_rate=args.short_rate
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "credit-copula":
        res = calculate_credit_portfolio_copula_cdo(
            n_issuers=args.issuers,
            notional_per_issuer=args.notional_per_issuer,
            default_probability=args.pd,
            lgd_rate=args.lgd,
            asset_correlation=args.correlation,
            copula_type=args.copula
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "frac-diff":
        res = calculate_deep_hedging_and_fractional_differentiation(
            prices=args.prices,
            d_order=args.d
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "forensic":
        res = calculate_forensic_reverse_factoring_spv(
            revenue=args.revenue,
            cogs=args.cogs,
            reported_cfo=args.cfo,
            capex=args.capex,
            short_term_debt=args.debt_st,
            long_term_debt=args.debt_lt,
            cash_and_equiv=args.cash,
            reported_ebitda=args.ebitda,
            accounts_receivable=args.ar,
            inventory=args.inv,
            accounts_payable=args.ap,
            reverse_factoring_hidden_payable=args.reverse_factoring,
            off_balance_sheet_spv_debt=args.spv_debt,
            unbilled_receivables=args.unbilled,
            doubtful_debt_allowance=args.doubtful,
            prior_doubtful_debt_allowance=args.prior_doubtful
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "isda-ctd":
        mock_bonds = [
            {"isin": "US001", "coupon_pct": 5.0, "maturity_years": 3.0, "market_price": 42.0},
            {"isin": "US002", "coupon_pct": 3.5, "maturity_years": 7.0, "market_price": 36.5},
            {"isin": "US003", "coupon_pct": 6.0, "maturity_years": 10.0, "market_price": 48.0}
        ]
        res = calculate_isda_restructuring_ctd(
            cds_spread_bps=args.spread,
            notional=args.notional,
            deliverable_bonds=mock_bonds,
            is_manufactured_default=args.manufactured
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
