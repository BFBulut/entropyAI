"""CPPI Portfoy Sigortasi, Esit Risk Katkisi (ERC), Hamilton Rejim Degisimi, AMM LVR ve Egemen Borc Takaslari.

Bu modul finansal bilissel mimarinin 5 ileri duzey kurumsal sutununu gerceklestirir:
1. Dinamik Portfoy Sigortasi (CPPI): Multiplier, Cushion, Floor dinamigi, Gap riski ve Cash-lock onleme.
2. Esit Risk Katkisi (ERC / Risk Parity): Marjinal risk katkisi, Spinu dongusel optimizasyonu ve Diversification Ratio.
3. Hamilton Filtresi & Markov Rejim Degisimi (MS-VAR): Boga/Ayi gecis olasiliklari, rekursif filtreleme ve rejime duyarli varlik dagilimi.
4. DeFi Likidite Fizigi: Loss-Versus-Rebalancing (LVR) vs Impermanent Loss, surekli zamanli volatilite maliyeti ve AMM slippage.
5. Egemen Borc Yeniden Yapilandirmasi: Paris/Londra Kulubu, NPV Haircut analitigi ve Debt-for-Nature (Mavi Tahvil) takas modeli.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


# =====================================================================
# 1. Dinamik Portfoy Sigortasi (CPPI)
# =====================================================================

def calculate_cppi_portfolio_insurance(
    initial_asset: float,
    floor_ratio: float,
    multiplier: float,
    price_series: List[float],
    risk_free_rate: float = 0.04,
    ratchet_enabled: bool = False,
    dynamic_vol_adjust: bool = False,
) -> Dict[str, Any]:
    """
    Dinamik Portfoy Sigortasi (CPPI - Constant Proportion Portfolio Insurance).
    
    A_t = E_t + B_t
    Floor: F_t
    Cushion: C_t = max(0, A_t - F_t)
    Exposure: E_t = min(A_t, m_t * C_t)
    
    Eger varlik fiyatinda gunluk dusus > 1 / m ise Gap Riski gerceklesir ve taban delinir.
    Eger C_t <= 0 olursa Cash-Lock gerceklesir ve portfoy tamamen nakde kilitlenir.
    """
    if initial_asset <= 0:
        raise ValueError("Baslangic portfoy degeri pozitif olmalidir.")
    if floor_ratio <= 0.0 or floor_ratio >= 1.0:
        raise ValueError("Floor orani (0, 1) arasinda olmalidir.")
    if multiplier <= 1.0:
        raise ValueError("CPPI carpani 1.0'dan buyuk olmalidir.")
    if not price_series or len(price_series) < 2:
        raise ValueError("En az 2 fiyat adimi gereklidir.")

    n_steps = len(price_series)
    dt = 1.0 / 252.0  # Islem gunu bazli faiz iskonto adimi
    daily_rf = (1.0 + risk_free_rate) ** dt - 1.0

    asset_values = [initial_asset]
    floors = [initial_asset * floor_ratio]
    cushions = [max(0.0, initial_asset - floors[0])]
    multipliers = [multiplier]
    
    initial_exposure = min(initial_asset, multiplier * cushions[0])
    exposures = [initial_exposure]
    cash_holdings = [initial_asset - initial_exposure]

    cash_locked = False
    cash_lock_step: Optional[int] = None
    floor_breached = False
    floor_breach_step: Optional[int] = None

    max_high_water_mark = initial_asset

    # Buy-and-Hold karsilastirmasi
    bh_shares = initial_asset / price_series[0]
    bh_values = [initial_asset]

    for t in range(1, n_steps):
        prev_a = asset_values[-1]
        prev_e = exposures[-1]
        prev_b = cash_holdings[-1]
        prev_f = floors[-1]

        p_prev = price_series[t - 1]
        p_curr = price_series[t]
        asset_return = (p_curr - p_prev) / p_prev

        # Risksiz nakit faiz geliri
        curr_b = prev_b * (1.0 + daily_rf)
        # Riskli varlik getirisi
        curr_e = prev_e * (1.0 + asset_return)

        curr_a = curr_e + curr_b

        # Ratchet mekanizmasi (High-water mark kilitli taban)
        if ratchet_enabled:
            max_high_water_mark = max(max_high_water_mark, curr_a)
            curr_f = max(prev_f * (1.0 + daily_rf), max_high_water_mark * floor_ratio)
        else:
            curr_f = prev_f * (1.0 + daily_rf)

        curr_c = max(0.0, curr_a - curr_f)

        # Taban delinme kontrolu
        if curr_a < curr_f and not floor_breached:
            floor_breached = True
            floor_breach_step = t

        # Cash-lock kontrolu
        if curr_c <= 1e-6 and not cash_locked:
            cash_locked = True
            cash_lock_step = t

        # Dinamik volatilite uyarlamasi (Volatilite yukselince m kuculur)
        if dynamic_vol_adjust and t >= 5:
            recent_ret = [(price_series[i] - price_series[i - 1]) / price_series[i - 1] for i in range(t - 4, t + 1)]
            mean_ret = sum(recent_ret) / len(recent_ret)
            var_ret = sum((r - mean_ret) ** 2 for r in recent_ret) / (len(recent_ret) - 1)
            ann_vol = math.sqrt(max(1e-8, var_ret * 252.0))
            # Hedeflenen risk toleransina gore m ayari
            curr_m = min(multiplier, max(1.5, 0.60 / ann_vol))
        else:
            curr_m = multiplier

        # Yeniden dengeleme (Rebalancing)
        if cash_locked:
            next_e = 0.0
            next_b = curr_a
        else:
            next_e = min(curr_a, curr_m * curr_c)
            next_b = max(0.0, curr_a - next_e)

        asset_values.append(curr_a)
        floors.append(curr_f)
        cushions.append(curr_c)
        multipliers.append(curr_m)
        exposures.append(next_e)
        cash_holdings.append(next_b)
        bh_values.append(bh_shares * p_curr)

    # Maksimum Cekilme (Max Drawdown)
    peak = asset_values[0]
    max_dd = 0.0
    for v in asset_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    bh_peak = bh_values[0]
    bh_max_dd = 0.0
    for v in bh_values:
        if v > bh_peak:
            bh_peak = v
        dd = (bh_peak - v) / bh_peak if bh_peak > 0 else 0.0
        if dd > bh_max_dd:
            bh_max_dd = dd

    final_cppi = asset_values[-1]
    final_bh = bh_values[-1]
    gap_breach_risk_threshold = 1.0 / multiplier

    return {
        "final_asset_value": round(final_cppi, 2),
        "final_buy_and_hold_value": round(final_bh, 2),
        "cppi_return_pct": round(((final_cppi - initial_asset) / initial_asset) * 100, 2),
        "buy_and_hold_return_pct": round(((final_bh - initial_asset) / initial_asset) * 100, 2),
        "max_drawdown_cppi": round(max_dd * 100, 2),
        "max_drawdown_bh": round(bh_max_dd * 100, 2),
        "cash_locked": cash_locked,
        "cash_lock_step": cash_lock_step,
        "floor_breached": floor_breached,
        "floor_breach_step": floor_breach_step,
        "gap_risk_single_day_threshold_pct": round(gap_breach_risk_threshold * 100, 2),
        "final_cushion": round(cushions[-1], 2),
        "final_floor": round(floors[-1], 2),
        "trajectory_summary": {
            "initial_asset": initial_asset,
            "min_asset_value": round(min(asset_values), 2),
            "max_asset_value": round(max(asset_values), 2),
            "min_cushion": round(min(cushions), 2),
        }
    }


# =====================================================================
# 2. Esit Risk Katkisi (ERC - Equal Risk Contribution)
# =====================================================================

def calculate_equal_risk_contribution(
    covariance_matrix: List[List[float]],
    asset_names: Optional[List[str]] = None,
    expected_returns: Optional[List[float]] = None,
    max_iter: int = 200,
    tolerance: float = 1e-6
) -> Dict[str, Any]:
    """
    Esit Risk Katkisi (ERC - Equal Risk Contribution / Risk Parity).
    
    Her bir varligin portfoy riskine katkisi:
    RC_i = w_i * (Sigma * w)_i / sigma_p
    ERC sartinda RC_i = RC_j = sigma_p / N.
    
    Spinu (2013) ve Maillard et al. (2010) dongusel koordinat optimizasyonu.
    """
    n = len(covariance_matrix)
    if n < 2:
        raise ValueError("En az 2 varlik gereklidir.")
    for row in covariance_matrix:
        if len(row) != n:
            raise ValueError("Kovaryans matrisi kare olmalidir.")

    names = asset_names or [f"Varlik_{i+1}" for i in range(n)]

    # Baslangic: Egitimli tahmin olarak ters volatilite (Inverse-Volatility)
    sigmas = [math.sqrt(max(1e-8, covariance_matrix[i][i])) for i in range(n)]
    inv_vol = [1.0 / s for s in sigmas]
    sum_inv_vol = sum(inv_vol)
    w = [iv / sum_inv_vol for iv in inv_vol]

    # Spinu tipi dongusel iterasyon
    for iteration in range(max_iter):
        # Sigma * w vektorunu hesapla
        sigma_w = [sum(covariance_matrix[i][j] * w[j] for j in range(n)) for i in range(n)]
        var_p = sum(w[i] * sigma_w[i] for i in range(n))
        vol_p = math.sqrt(max(1e-12, var_p))

        # Risk Katkilari: RC_i = w_i * sigma_w[i]
        rc = [w[i] * sigma_w[i] for i in range(n)]
        target_rc = var_p / n

        # Konverjans testi: Maksimum RC sapmasi
        max_diff = max(abs(rc[i] - target_rc) for i in range(n))
        if max_diff < tolerance:
            break

        # Koordinat guncellemesi (Quadratic adjustment)
        new_w = list(w)
        for i in range(n):
            # c_i * w_i^2 + b_i * w_i - target = 0
            # sigma_w[i] = Sigma_ii * w_i + sum_{j!=i} Sigma_ij * w_j
            sigma_ii = covariance_matrix[i][i]
            other_cov = sum(covariance_matrix[i][j] * w[j] for j in range(n) if j != i)
            
            # w_i * (sigma_ii * w_i + other_cov) = target_rc
            # sigma_ii * w_i^2 + other_cov * w_i - target_rc = 0
            discriminant = other_cov ** 2 + 4.0 * sigma_ii * target_rc
            if discriminant >= 0:
                root = (-other_cov + math.sqrt(discriminant)) / (2.0 * sigma_ii)
                new_w[i] = max(1e-6, root)
        
        sum_new_w = sum(new_w)
        w = [x / sum_new_w for x in new_w]

    # Nihai portfoy risk metrikleri
    final_sigma_w = [sum(covariance_matrix[i][j] * w[j] for j in range(n)) for i in range(n)]
    port_var = sum(w[i] * final_sigma_w[i] for i in range(n))
    port_vol = math.sqrt(max(1e-12, port_var))

    marginal_rc = [final_sigma_w[i] / port_vol for i in range(n)]
    absolute_rc = [w[i] * marginal_rc[i] for i in range(n)]
    percentage_rc = [(rc_i / port_vol) * 100 for rc_i in absolute_rc]

    # Herfindahl Risk Yogunlasma Indeksi (1/N iken tam 1/N degeri verir)
    hhi_rc = sum((rc_pct / 100.0) ** 2 for rc_pct in percentage_rc)

    # Choueifaty Diversification Ratio (DR)
    weighted_vol_sum = sum(w[i] * sigmas[i] for i in range(n))
    diversification_ratio = weighted_vol_sum / port_vol

    # Klasik 1/N karsilastirmasi
    equal_w = [1.0 / n] * n
    eq_sigma_w = [sum(covariance_matrix[i][j] * equal_w[j] for j in range(n)) for i in range(n)]
    eq_var = sum(equal_w[i] * eq_sigma_w[i] for i in range(n))
    eq_vol = math.sqrt(max(1e-12, eq_var))
    eq_pct_rc = [((equal_w[i] * eq_sigma_w[i] / eq_vol) / eq_vol) * 100 for i in range(n)]

    asset_details = []
    for i in range(n):
        asset_details.append({
            "asset": names[i],
            "erc_weight_pct": round(w[i] * 100, 2),
            "asset_volatility_pct": round(sigmas[i] * 100, 2),
            "marginal_risk_contribution": round(marginal_rc[i], 4),
            "absolute_risk_contribution": round(absolute_rc[i], 4),
            "risk_contribution_pct": round(percentage_rc[i], 2),
            "equal_weight_rc_pct": round(eq_pct_rc[i], 2),
        })

    result = {
        "portfolio_volatility_pct": round(port_vol * 100, 2),
        "equal_weight_volatility_pct": round(eq_vol * 100, 2),
        "diversification_ratio": round(diversification_ratio, 3),
        "risk_concentration_hhi": round(hhi_rc, 4),
        "perfect_parity_hhi": round(1.0 / n, 4),
        "is_perfect_parity": abs(hhi_rc - (1.0 / n)) < 0.01,
        "assets": asset_details,
    }

    if expected_returns and len(expected_returns) == n:
        erc_return = sum(w[i] * expected_returns[i] for i in range(n))
        eq_return = sum(equal_w[i] * expected_returns[i] for i in range(n))
        result["expected_return_erc_pct"] = round(erc_return * 100, 2)
        result["sharpe_ratio_erc"] = round(erc_return / port_vol, 3)
        result["sharpe_ratio_equal_weight"] = round(eq_return / eq_vol, 3)

    return result


# =====================================================================
# 3. Hamilton Filtresi & Markov Rejim Degisimi (MS-VAR)
# =====================================================================

def calculate_hamilton_filter_regime_switching(
    returns: List[float],
    p11: float = 0.95,
    p22: float = 0.90,
    mu_bull: float = 0.0010,
    sigma_bull: float = 0.0080,
    mu_bear: float = -0.0015,
    sigma_bear: float = 0.0220,
) -> Dict[str, Any]:
    """
    James Hamilton (1989) Markov Rejim Degisimi ve Filtrelenmis Olasiliklar.
    
    Durum 1: Boga / Dusuk Volatilite (mu_bull, sigma_bull)
    Durum 2: Ayi-Kriz / Yuksek Volatilite (mu_bear, sigma_bear)
    
    Gecis Olasiliklari:
    P(S_t = 1 | S_{t-1} = 1) = p11
    P(S_t = 2 | S_{t-1} = 2) = p22
    """
    if not returns:
        raise ValueError("Getiri serisi bos olamaz.")
    if not (0.0 < p11 < 1.0 and 0.0 < p22 < 1.0):
        raise ValueError("Gecis olasiliklari (0, 1) arasinda olmalidir.")
    if sigma_bull <= 0 or sigma_bear <= 0:
        raise ValueError("Oynakliklar pozitif olmalidir.")

    # Kararli (Ergodic / Unconditional) Baslangic Olasiliklari
    denom = 2.0 - p11 - p22
    pi_bull = (1.0 - p22) / denom
    pi_bear = (1.0 - p11) / denom

    # Beklenen Kalicilik Sureleri (Expected Duration in Days)
    duration_bull = 1.0 / (1.0 - p11)
    duration_bear = 1.0 / (1.0 - p22)

    prob_bull = pi_bull
    prob_bear = pi_bear

    filtered_bull_probs = []
    filtered_bear_probs = []
    detected_regimes = []

    def normal_pdf(x: float, mu: float, sigma: float) -> float:
        coef = 1.0 / (math.sqrt(2.0 * math.pi) * sigma)
        exponent = -((x - mu) ** 2) / (2.0 * (sigma ** 2))
        return coef * math.exp(max(-50.0, exponent))

    # Rekursif Hamilton Filtreleme
    for r in returns:
        # 1. Tahmin adimi (Prior)
        prior_bull = p11 * prob_bull + (1.0 - p22) * prob_bear
        prior_bear = (1.0 - p11) * prob_bull + p22 * prob_bear

        # 2. Olcum olabilirligi (Likelihood)
        lh_bull = normal_pdf(r, mu_bull, sigma_bull)
        lh_bear = normal_pdf(r, mu_bear, sigma_bear)

        # 3. Guncelleme adimi (Posterior)
        joint_bull = prior_bull * lh_bull
        joint_bear = prior_bear * lh_bear
        total_density = joint_bull + joint_bear

        if total_density > 1e-15:
            prob_bull = joint_bull / total_density
            prob_bear = joint_bear / total_density
        else:
            prob_bull = prior_bull
            prob_bear = prior_bear

        filtered_bull_probs.append(prob_bull)
        filtered_bear_probs.append(prob_bear)
        detected_regimes.append(1 if prob_bull >= 0.50 else 2)

    bull_days = sum(1 for reg in detected_regimes if reg == 1)
    bear_days = len(detected_regimes) - bull_days

    # Rejim gecis sayisi
    regime_switches = sum(1 for i in range(1, len(detected_regimes)) if detected_regimes[i] != detected_regimes[i - 1])

    # Dinamik Rejime Duyarli Varlik Tahsisi Stratejisi
    # Boga ise %80 Hisse / %20 Tahvil; Ayi ise %20 Hisse / %80 Tahvil
    rf_daily = 0.03 / 252.0  # Tahvil / risksiz getiri
    strategy_returns = []
    for t, r in enumerate(returns):
        weight_equity = filtered_bull_probs[t] * 0.80 + (1.0 - filtered_bull_probs[t]) * 0.20
        weight_bonds = 1.0 - weight_equity
        strat_r = weight_equity * r + weight_bonds * rf_daily
        strategy_returns.append(strat_r)

    total_strat_return = 1.0
    for sr in strategy_returns:
        total_strat_return *= (1.0 + sr)

    total_bench_return = 1.0
    for r in returns:
        total_bench_return *= (1.0 + r)

    return {
        "expected_duration_bull_days": round(duration_bull, 1),
        "expected_duration_bear_days": round(duration_bear, 1),
        "unconditional_prob_bull_pct": round(pi_bull * 100, 2),
        "unconditional_prob_bear_pct": round(pi_bear * 100, 2),
        "total_periods": len(returns),
        "bull_regime_periods": bull_days,
        "bear_regime_periods": bear_days,
        "regime_switches_count": regime_switches,
        "final_filtered_bull_prob_pct": round(filtered_bull_probs[-1] * 100, 2),
        "current_regime": "BULL" if filtered_bull_probs[-1] >= 0.50 else "BEAR",
        "dynamic_strategy_return_pct": round((total_strat_return - 1.0) * 100, 2),
        "benchmark_buy_and_hold_return_pct": round((total_bench_return - 1.0) * 100, 2),
        "strategy_outperformance_pct": round((total_strat_return - total_bench_return) * 100, 2),
        "sample_filtered_bull_probabilities": [round(p, 4) for p in filtered_bull_probs[-10:]],
    }


# =====================================================================
# 4. DeFi Likidite Fizigi: Loss-Versus-Rebalancing (LVR) vs Impermanent Loss
# =====================================================================

def calculate_amm_lvr_and_slippage(
    initial_pool_x: float,
    initial_pool_y: float,
    annual_volatility: float,
    days: float,
    daily_swap_volume_usd: float,
    fee_tier: float = 0.0030,
    test_trade_sizes_x: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    DeFi Sabit Carpim Havuzunda (CPMM x*y=k) LVR (Loss-Versus-Rebalancing) ve Slippage.
    
    Milionis, Moallemi, Roughgarden (2022):
    LVR_T = (sigma^2 / 8) * V_pool * T
    
    Impermanent Loss yalnizca (P_T / P_0) uclarina bagliyken;
    LVR arbitrajcilara yol boyunca odenen bilgi rantinin (adverse selection) integralidir.
    
    LP Net Gelir = Toplanan Komisyonlar - LVR
    """
    if initial_pool_x <= 0 or initial_pool_y <= 0:
        raise ValueError("Havuz rezervleri pozitif olmalidir.")
    if annual_volatility <= 0:
        raise ValueError("Oynaklik pozitif olmalidir.")
    if days <= 0:
        raise ValueError("Gun sayisi pozitif olmalidir.")

    # Marjinal fiyat (USD / X)
    p0 = initial_pool_y / initial_pool_x
    k = initial_pool_x * initial_pool_y
    pool_value_usd = 2.0 * math.sqrt(k * p0)  # = 2 * initial_pool_y

    t_years = days / 365.0
    
    # Kümülatif LVR (Loss-Versus-Rebalancing)
    # LVR = (sigma^2 / 8) * V_pool * T
    lvr_cost_usd = (annual_volatility ** 2 / 8.0) * pool_value_usd * t_years
    lvr_ratio_pct = (lvr_cost_usd / pool_value_usd) * 100

    # Toplanan kümülatif swap komisyonu
    total_volume_usd = daily_swap_volume_usd * days
    earned_fees_usd = total_volume_usd * fee_tier

    # Net Kâr / Zarar
    net_lp_profit_usd = earned_fees_usd - lvr_cost_usd
    net_lp_yield_pct = (net_lp_profit_usd / pool_value_usd) * 100

    # Klasik Impermanent Loss karsilastirmasi (fiyat %50 artti varsayimi)
    price_ratio = 1.50
    il_ratio = (2.0 * math.sqrt(price_ratio)) / (1.0 + price_ratio) - 1.0
    il_cost_usd = abs(il_ratio) * pool_value_usd

    # Kayma (Slippage) kapali formu analizi
    test_sizes = test_trade_sizes_x or [
        initial_pool_x * 0.001,  # %0.1
        initial_pool_x * 0.01,   # %1
        initial_pool_x * 0.05,   # %5
        initial_pool_x * 0.10,   # %10
    ]

    slippage_results = []
    for dx in test_sizes:
        # dx satisi karsiliginda alinan dy:
        dy = (initial_pool_y * dx) / (initial_pool_x + dx)
        eff_price = dy / dx
        slippage_pct = ((p0 - eff_price) / p0) * 100
        slippage_results.append({
            "trade_size_x": dx,
            "trade_pct_of_pool": round((dx / initial_pool_x) * 100, 3),
            "effective_price_usd": round(eff_price, 4),
            "marginal_price_usd": round(p0, 4),
            "slippage_pct": round(slippage_pct, 4)
        })

    is_lp_profitable = net_lp_profit_usd > 0

    return {
        "pool_value_initial_usd": round(pool_value_usd, 2),
        "holding_period_days": days,
        "annual_volatility_pct": round(annual_volatility * 100, 2),
        "total_swap_volume_usd": round(total_volume_usd, 2),
        "earned_swap_fees_usd": round(earned_fees_usd, 2),
        "lvr_cost_usd": round(lvr_cost_usd, 2),
        "lvr_to_pool_ratio_pct": round(lvr_ratio_pct, 3),
        "net_lp_profit_usd": round(net_lp_profit_usd, 2),
        "net_lp_yield_pct": round(net_lp_yield_pct, 2),
        "is_lp_profitable": is_lp_profitable,
        "theoretical_il_at_1_5x_price_usd": round(il_cost_usd, 2),
        "theoretical_il_at_1_5x_pct": round(il_ratio * 100, 2),
        "lvr_vs_il_insight": (
            "LVR surekli dinamik arbitraj maliyetidir; IL ise yalnizca uclar arasi statik farktir. "
            f"Fiyat ayni yere donse bile LVR ${round(lvr_cost_usd, 2)} olarak kalici erime yaratir."
        ),
        "trade_slippage_analysis": slippage_results
    }


# =====================================================================
# 5. Egemen Borc Yeniden Yapilandirmasi & Doğa Karsiligi Borc Takasi
# =====================================================================

def calculate_sovereign_debt_restructuring_and_nature_swap(
    nominal_debt: float,
    old_coupon: float,
    old_maturity_years: int,
    principal_haircut_pct: float,
    new_coupon: float,
    new_maturity_years: int,
    exit_yield: float = 0.11,
    secondary_market_price_pct: float = 0.45,
    nature_conservation_annual_funding: float = 2_500_000.0,
    credit_enhancement_cost: float = 3_000_000.0
) -> Dict[str, Any]:
    """
    Paris Kulubu, Londra Kulubu ve Doga Karsiligi Borc Takasi (Debt-for-Nature / Blue Bond).
    
    1. NPV Haircut Analitigi:
       NPV = sum_{t=1}^T CF_t / (1 + r_exit)^t
       Haircut_NPV = 1 - NPV_yeni / NPV_eski
    
    2. Debt-for-Nature Mekanizmasi:
       Ikincil piyasadan iskonto ile borc geri alimi (Tender Offer),
       Kalkinma bankasi (DFC/IDB) kredi garantisi ile ucuz Mavi Tahvil ihraci,
       Faiz tasarrufundan deniz/cevre koruma fonuna aktarim.
    """
    if nominal_debt <= 0:
        raise ValueError("Nominal borc tutari pozitif olmalidir.")
    if not (0.0 <= principal_haircut_pct < 1.0):
        raise ValueError("Anapara trasi [0, 1) arasinda olmalidir.")
    if exit_yield <= 0:
        raise ValueError("Cikis getirisi pozitif olmalidir.")

    # 1. Eski Sözlesmenin NPV Hesabi
    old_annual_coupon_payment = nominal_debt * old_coupon
    old_npv = sum(old_annual_coupon_payment / ((1.0 + exit_yield) ** t) for t in range(1, old_maturity_years + 1))
    old_npv += nominal_debt / ((1.0 + exit_yield) ** old_maturity_years)

    # 2. Yeni Sözlesmenin NPV Hesabi
    new_nominal = nominal_debt * (1.0 - principal_haircut_pct)
    new_annual_coupon_payment = new_nominal * new_coupon
    new_npv = sum(new_annual_coupon_payment / ((1.0 + exit_yield) ** t) for t in range(1, new_maturity_years + 1))
    new_npv += new_nominal / ((1.0 + exit_yield) ** new_maturity_years)

    # Haircut ayrıştırması
    nominal_haircut = principal_haircut_pct
    npv_haircut = 1.0 - (new_npv / old_npv)

    # Yıllık borç servisi rahatlaması (Ilk yil faiz tasarrufu)
    annual_cashflow_relief = old_annual_coupon_payment - new_annual_coupon_payment

    # 3. Debt-for-Nature / Blue Bond Simülasyonu
    # Piyasa degeri uzerinden ikincil piyasadan geri alim tutari:
    buyback_cost = nominal_debt * secondary_market_price_pct
    new_blue_bond_principal = buyback_cost + credit_enhancement_cost
    
    # Mavi tahvil AAA/AA dereceli kalkınma garantisiyle dusuk kupon tasir
    blue_bond_coupon = 0.0525
    blue_bond_maturity = 18
    new_blue_coupon_payment = new_blue_bond_principal * blue_bond_coupon

    annual_sovereign_savings = old_annual_coupon_payment - new_blue_coupon_payment
    net_fiscal_space_annual = annual_sovereign_savings - nature_conservation_annual_funding
    cumulative_nature_funding_18y = nature_conservation_annual_funding * blue_bond_maturity

    # Paris Kulübü Karşılaştırılabilirlik Testi
    # Eger ticari bankalar (Londra Kulubu) en az Paris Kulubu kadar NPV kaybi ustlenmisse uygundur
    paris_club_min_comparability_haircut = 0.30
    is_comparable_treatment = npv_haircut >= paris_club_min_comparability_haircut

    return {
        "original_debt_nominal": round(nominal_debt, 2),
        "original_npv_at_exit_yield": round(old_npv, 2),
        "restructured_nominal": round(new_nominal, 2),
        "restructured_npv_at_exit_yield": round(new_npv, 2),
        "nominal_haircut_pct": round(nominal_haircut * 100, 2),
        "effective_npv_haircut_pct": round(npv_haircut * 100, 2),
        "annual_cashflow_relief_usd": round(annual_cashflow_relief, 2),
        "debt_for_nature_swap": {
            "secondary_market_repurchase_price_pct": round(secondary_market_price_pct * 100, 2),
            "debt_buyback_cost_usd": round(buyback_cost, 2),
            "new_blue_bond_principal_usd": round(new_blue_bond_principal, 2),
            "sovereign_principal_extinguished_usd": round(nominal_debt - new_blue_bond_principal, 2),
            "annual_gross_debt_service_savings_usd": round(annual_sovereign_savings, 2),
            "nature_conservation_annual_endowment_usd": round(nature_conservation_annual_funding, 2),
            "net_annual_fiscal_space_gained_usd": round(net_fiscal_space_annual, 2),
            "cumulative_18y_conservation_fund_usd": round(cumulative_nature_funding_18y, 2),
        },
        "paris_club_compliance": {
            "comparability_of_treatment_met": is_comparable_treatment,
            "threshold_required_pct": round(paris_club_min_comparability_haircut * 100, 2),
            "actual_creditor_haircut_pct": round(npv_haircut * 100, 2),
        }
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="CPPI, ERC, Hamilton Filter, AMM LVR & Sovereign Debt")
    subparsers = parser.add_subparsers(dest="command")

    # CPPI
    p_cppi = subparsers.add_parser("cppi")
    p_cppi.add_argument("--asset", type=float, default=1000000.0)
    p_cppi.add_argument("--floor", type=float, default=0.85)
    p_cppi.add_argument("--multiplier", type=float, default=3.5)
    p_cppi.add_argument("--prices", type=str, default="100,98,95,92,90,88,85,82,80")

    # ERC
    p_erc = subparsers.add_parser("erc")
    p_erc.add_argument("--names", type=str, default="Tahvil,Hisse,Emtia")

    # Hamilton
    p_ham = subparsers.add_parser("hamilton")
    p_ham.add_argument("--returns", type=str, default="0.001,0.002,-0.001,0.0015,-0.025,-0.030,0.012,-0.018")

    # LVR
    p_lvr = subparsers.add_parser("lvr")
    p_lvr.add_argument("--pool-x", type=float, default=100.0)
    p_lvr.add_argument("--pool-y", type=float, default=300000.0)
    p_lvr.add_argument("--vol", type=float, default=0.75)
    p_lvr.add_argument("--days", type=float, default=90.0)
    p_lvr.add_argument("--daily-vol", type=float, default=500000.0)

    # Debt
    p_debt = subparsers.add_parser("debt")
    p_debt.add_argument("--debt", type=float, default=1000000000.0)
    p_debt.add_argument("--old-coupon", type=float, default=0.08)
    p_debt.add_argument("--haircut", type=float, default=0.25)
    p_debt.add_argument("--new-coupon", type=float, default=0.045)

    args = parser.parse_args()

    if args.command == "cppi":
        prices = [float(x.strip()) for x in args.prices.split(",")]
        res = calculate_cppi_portfolio_insurance(args.asset, args.floor, args.multiplier, prices)
        print(json.dumps(res, indent=2))
    elif args.command == "erc":
        names = [x.strip() for x in args.names.split(",")]
        cov = [
            [0.0100, 0.0040, 0.0060],
            [0.0040, 0.0400, 0.0120],
            [0.0060, 0.0120, 0.0900],
        ]
        res = calculate_equal_risk_contribution(cov, names)
        print(json.dumps(res, indent=2))
    elif args.command == "hamilton":
        rets = [float(x.strip()) for x in args.returns.split(",")]
        res = calculate_hamilton_filter_regime_switching(rets)
        print(json.dumps(res, indent=2))
    elif args.command == "lvr":
        res = calculate_amm_lvr_and_slippage(args.pool_x, args.pool_y, args.vol, args.days, args.daily_vol)
        print(json.dumps(res, indent=2))
    elif args.command == "debt":
        res = calculate_sovereign_debt_restructuring_and_nature_swap(args.debt, args.old_coupon, 7, args.haircut, args.new_coupon, 15)
        print(json.dumps(res, indent=2))
    else:
        parser.print_help()

