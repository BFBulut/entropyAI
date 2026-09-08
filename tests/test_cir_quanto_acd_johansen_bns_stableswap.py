"""
TEST_CIR_QUANTO_ACD_JOHANSEN_BNS_STABLESWAP.PY
Entropy AI - Faz 33 Kapsamlı Otomatik Test Paketi (Agentic TDD)
"""

import math
import pytest
import numpy as np
import sys
import os

# scripts dizinini sys.path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../skills/financial-auditor/scripts")))

from cir_quanto_acd_johansen_bns_stableswap import (
    CIRModelEngine,
    QuantoOptionEngine,
    ACDModelEngine,
    JohansenBertramStatArbEngine,
    BNSJumpDetectionEngine,
    CurveStableswapEngine
)


# ==============================================================================
# 1. COX-INGERSOLL-ROSS (CIR) TESTLERİ
# ==============================================================================

def test_cir_initialization_and_feller():
    # 2 * kappa * theta = 2 * 2.0 * 0.05 = 0.20
    # sigma^2 = 0.1^2 = 0.01 -> feller_ratio = 20 > 1 (Feller sağlanır)
    cir = CIRModelEngine(kappa=2.0, theta=0.05, sigma=0.10, r0=0.04)
    assert cir.is_feller_satisfied is True
    assert cir.feller_ratio == pytest.approx(20.0, rel=1e-3)

    # Feller ihlali: sigma yüksek
    cir_violated = CIRModelEngine(kappa=0.5, theta=0.02, sigma=0.4, r0=0.03)
    # 2 * 0.5 * 0.02 = 0.02 vs 0.16 -> ratio = 0.125 < 1
    assert cir_violated.is_feller_satisfied is False

    with pytest.raises(ValueError):
        CIRModelEngine(kappa=-1.0, theta=0.05, sigma=0.1, r0=0.04)


def test_cir_zero_coupon_pricing_and_yield():
    cir = CIRModelEngine(kappa=1.5, theta=0.05, sigma=0.15, r0=0.04)
    p_1y = cir.zero_coupon_bond_price(0.0, 1.0)
    p_5y = cir.zero_coupon_bond_price(0.0, 5.0)

    # Sıfır kuponlu tahvil fiyatı 0 ile 1 arasında olmalı ve vade uzadıkça düşmeli
    assert 0.0 < p_5y < p_1y < 1.0

    y_1y = cir.yield_to_maturity(0.0, 1.0)
    y_5y = cir.yield_to_maturity(0.0, 5.0)
    assert y_1y > 0.0
    assert y_5y > 0.0
    assert abs(math.exp(-y_1y * 1.0) - p_1y) < 1e-6


def test_cir_simulation_and_cir_plus_plus_shift():
    cir = CIRModelEngine(kappa=2.0, theta=0.05, sigma=0.1, r0=0.04)
    paths = cir.simulate_paths(T=1.0, steps=50, n_paths=200, seed=42)
    assert paths.shape == (200, 51)
    # Faizler asla negatif olamaz (Full truncation)
    assert np.all(paths >= 0.0)

    # CIR++ Kaydırma testi
    market_dfs = {0.5: 0.98, 1.0: 0.95, 2.0: 0.90}
    shifts = cir.cir_plus_plus_shift(market_dfs)
    assert len(shifts) == 3
    for T, shift in shifts.items():
        assert isinstance(shift, float)


# ==============================================================================
# 2. QUANTO OPSİYON TESTLERİ
# ==============================================================================

def test_quanto_option_pricing_and_drift_adjustment():
    # S0=100, K=100, T=1.0, r_d=0.05, r_f=0.02, q=0.01
    # sigma_S=0.20, sigma_X=0.15, rho=0.40
    quanto = QuantoOptionEngine(
        S0=100.0, K=100.0, T=1.0,
        r_d=0.05, r_f=0.02, q=0.01,
        sigma_S=0.20, sigma_X=0.15, rho=0.40, F0=1.0
    )
    # Kovaryans sürüklenmesi: - rho * sigma_S * sigma_X = - 0.40 * 0.20 * 0.15 = -0.012
    assert quanto.quanto_drift_adjustment == pytest.approx(-0.012, abs=1e-5)
    # Efektif drift: r_d - q - 0.012 = 0.05 - 0.01 - 0.012 = 0.028
    assert quanto.effective_quanto_drift == pytest.approx(0.028, abs=1e-5)

    res = quanto.price_quanto_call()
    assert res["quanto_call_price"] > 0.0
    assert 0.0 < res["quanto_delta"] < 1.0
    assert res["quanto_gamma"] > 0.0
    assert res["quanto_vega"] > 0.0
    # Pozitif rho durumunda dPrice / dRho negatif olmalıdır
    assert res["d_price_d_rho"] < 0.0


def test_quanto_rho_impact():
    # Negatif korelasyonda drift artar -> call fiyatı daha yüksek olmalıdır
    q_pos = QuantoOptionEngine(S0=100.0, K=100.0, T=1.0, r_d=0.05, r_f=0.02, q=0.0,
                               sigma_S=0.20, sigma_X=0.15, rho=0.50)
    q_neg = QuantoOptionEngine(S0=100.0, K=100.0, T=1.0, r_d=0.05, r_f=0.02, q=0.0,
                               sigma_S=0.20, sigma_X=0.15, rho=-0.50)

    price_pos = q_pos.price_quanto_call()["quanto_call_price"]
    price_neg = q_neg.price_quanto_call()["quanto_call_price"]

    assert price_neg > price_pos


# ==============================================================================
# 3. ENGLE-RUSSELL ACD MODEL TESTLERİ
# ==============================================================================

def test_acd_initialization_and_filtering():
    # omega=0.2, alpha=0.15, beta=0.75 -> alpha+beta = 0.90 < 1.0
    acd = ACDModelEngine(omega=0.2, alpha=0.15, beta=0.75)
    assert acd.unconditional_mean_duration == pytest.approx(0.2 / 0.10, rel=1e-4)

    # Durağanlık ihlali
    with pytest.raises(ValueError):
        ACDModelEngine(omega=0.1, alpha=0.5, beta=0.6)

    # Filtreleme
    durations = [2.0, 1.8, 0.5, 0.4, 0.3, 3.5, 2.1, 1.9, 0.2, 0.3]
    res = acd.filter_durations(durations)
    assert len(res["psi"]) == 10
    assert len(res["residuals"]) == 10
    assert res["log_likelihood"] < 0.0  # Log likelihood negatif


def test_acd_liquidity_clustering():
    acd = ACDModelEngine(omega=0.2, alpha=0.3, beta=0.5)
    # Normal süreler ve ani kümelenme (toksik akış)
    durations = [2.0, 2.0, 2.0, 0.1, 0.05, 0.08, 0.05, 3.0, 2.5]
    clustered_indices = acd.detect_liquidity_clustering(durations, threshold_ratio=0.6)
    assert len(clustered_indices) > 0
    # Kümelenme indeksleri 4-6 aralığında olmalı
    assert any(idx in [4, 5, 6] for idx in clustered_indices)


# ==============================================================================
# 4. JOHANSEN & BERTRAM STAT-ARB TESTLERİ
# ==============================================================================

def test_johansen_cointegration_analysis():
    np.random.seed(42)
    n = 200
    # Rastgele yürüyüş y1
    y1 = np.cumsum(np.random.normal(0, 1, n)) + 100.0
    # Eşbütünleşik y2: y2 = 1.8 * y1 + gürültü
    y2 = 1.8 * y1 + np.random.normal(0, 0.5, n)

    res = JohansenBertramStatArbEngine.johansen_two_asset_cointegration(y1, y2)
    assert "hedge_ratio" in res
    assert "trace_stat_r0" in res
    assert res["is_cointegrated"] is True
    # Hedge ratio 1.8 civarında olmalı
    assert abs(res["hedge_ratio"] - 1.8) < 0.20


def test_bertram_optimal_boundaries():
    engine = JohansenBertramStatArbEngine(mu=0.0, theta=2.5, sigma=0.15)
    res = engine.bertram_optimal_boundaries(c=0.002)

    assert res["optimal_entry_level"] < res["optimal_exit_level"]
    assert res["optimal_exit_level"] == 0.0
    assert res["optimal_entry_zscore"] < 0.0
    assert res["expected_trade_duration"] > 0.0
    assert res["expected_return_per_trade"] > 0.0


# ==============================================================================
# 5. BARNDORFF-NIELSEN & SHEPHARD BIPOWER VARIATION TESTLERİ
# ==============================================================================

def test_bns_jump_detection_continuous_case():
    np.random.seed(101)
    # Sıçramasız normal Brown difüzyon getirileri (N=200)
    returns = np.random.normal(0, 0.01, 300)
    res = BNSJumpDetectionEngine.calculate_bipower_variation(returns)

    assert res["realized_variance"] > 0.0
    assert res["bipower_variation"] > 0.0
    # Sürekli durumda RV ile BV birbirine çok yakındır, göreli sıçrama küçüktür
    assert res["relative_jump_share"] < 0.35
    assert res["has_significant_jump_99"] is False


def test_bns_jump_detection_with_discrete_jump():
    np.random.seed(101)
    returns = np.random.normal(0, 0.005, 300)
    # Dev bir gün içi sıçrama ekle (15 standart sapma)
    returns[150] += 0.15

    res = BNSJumpDetectionEngine.calculate_bipower_variation(returns)
    # RV sıçramayı içerirken BV sıçramayı filtreler -> RV >> BV
    assert res["realized_variance"] > res["bipower_variation"]
    assert res["relative_jump_share"] > 0.50
    assert res["z_statistic"] > 2.576
    assert res["has_significant_jump_95"] is True
    assert res["has_significant_jump_99"] is True


# ==============================================================================
# 6. CURVE STABLESWAP AMM DEĞİŞMEZİ TESTLERİ
# ==============================================================================

def test_curve_stableswap_calculate_d_and_swap():
    # 2 coinli havuz, A=100, dengeli rezervler: [1000, 1000]
    engine = CurveStableswapEngine(A=100.0, n_coins=2)
    xp = [1000.0, 1000.0]
    D = engine.calculate_D(xp)
    # Dengeli durumda D tam olarak rezerv toplamına eşittir: 2000
    assert D == pytest.approx(2000.0, rel=1e-4)

    # 10 birim token0 yatırıp token1 çek
    swap = engine.calculate_swap(i=0, j=1, dx=10.0, xp=xp, fee=0.0004)
    assert swap["dy_net"] > 0.0
    # A=100 iken 10 birime karşılık 9.99x birim çıkmalı (çok düşük kayma)
    assert swap["dy_net"] == pytest.approx(9.995, abs=0.05)
    assert swap["slippage_pct"] < 0.10


def test_curve_stableswap_amplification_effect_and_depeg():
    xp = [1000.0, 1000.0]
    # Yüksek A (A=1000) vs Düşük A (A=5)
    curve_high_A = CurveStableswapEngine(A=1000.0, n_coins=2)
    curve_low_A = CurveStableswapEngine(A=5.0, n_coins=2)

    # Büyük işlem dx=200
    swap_high = curve_high_A.calculate_swap(0, 1, 200.0, xp)
    swap_low = curve_low_A.calculate_swap(0, 1, 200.0, xp)

    # Yüksek A'da kayma belirgin şekilde daha düşük olmalıdır
    assert swap_high["slippage_pct"] < swap_low["slippage_pct"]
    assert swap_high["dy_net"] > swap_low["dy_net"]

    # Depeg stres testi
    stress = curve_high_A.depeg_stress_test(xp, drain_ratio=0.7)
    assert stress["marginal_exchange_rate"] > 0.0
    assert stress["stressed_slippage_pct"] > 0.0
