"""
CIR_QUANTO_ACD_JOHANSEN_BNS_STABLESWAP.PY
Entropy AI - Faz 33: İleri Finansal Matematik, Türev Fiyatlama & Algoritmik Piyasa Mimarisi

Modüller:
1. Cox-Ingersoll-Ross (CIR) & CIR++ Analitik Kısa Faiz Modeli (Feller Şartı, Sıfır Kupon Fiyatlama, CIR++ Kaydırma)
2. Quanto Opsiyon Değerlemesi & Girsanov Numeraire Değişimi (Çapraz Para Cinsi Drift Düzeltmesi, Siegel Paradoksu)
3. Engle-Russell (1998) Autoregressive Conditional Duration (ACD) Modeli (Yüksek Frekanslı İşlem Süresi & Likidite Kümelenmesi)
4. Johansen Eşbütünleşme Testi & Bertram (2010) Analitik Ornstein-Uhlenbeck Pairs Trading Sınırları
5. Barndorff-Nielsen & Shephard (2004/2006) Gerçekleşen Bipower Varyansı & Gün İçi Sıçrama (Jump) Z-Testi
6. Curve Stableswap AMM Değişmezi & Dinamik Amplifikasyon Parametresi A (Newton-Raphson Solver & Depeg Analitiği)
"""

import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np


# ==============================================================================
# 1. COX-INGERSOLL-ROSS (CIR) & CIR++ ANALİTİK KISA FAİZ MODELİ
# ==============================================================================

class CIRModelEngine:
    """
    Cox, Ingersoll & Ross (1985) ve Brigo-Mercurio CIR++ Modeli.
    dr_t = kappa * (theta - r_t) dt + sigma * sqrt(r_t) dW_t
    Feller koşulu: 2 * kappa * theta > sigma^2
    """

    def __init__(self, kappa: float, theta: float, sigma: float, r0: float):
        if kappa <= 0 or theta <= 0 or sigma <= 0:
            raise ValueError("kappa, theta ve sigma pozitif olmalıdır.")
        if r0 < 0:
            raise ValueError("Başlangıç faizi r0 negatif olamaz.")

        self.kappa = float(kappa)
        self.theta = float(theta)
        self.sigma = float(sigma)
        self.r0 = float(r0)

    @property
    def feller_ratio(self) -> float:
        """Feller oranı: (2 * kappa * theta) / (sigma^2). Oran > 1 ise faiz kesinlikle > 0 kalır."""
        return (2.0 * self.kappa * self.theta) / (self.sigma ** 2)

    @property
    def is_feller_satisfied(self) -> bool:
        """2 * kappa * theta > sigma^2 şartı kontrolü."""
        return self.feller_ratio > 1.0

    def zero_coupon_bond_price(self, t: float, T: float, r_t: Optional[float] = None) -> float:
        """
        Analitik Sıfır Kuponlu Tahvil Fiyatı: P(t, T) = A(t, T) * exp(-B(t, T) * r_t)
        """
        if r_t is None:
            r_t = self.r0
        if T <= t:
            return 1.0

        tau = T - t
        gamma = math.sqrt(self.kappa ** 2 + 2.0 * (self.sigma ** 2))
        exp_gamma_tau = math.exp(gamma * tau)

        denom = (gamma + self.kappa) * (exp_gamma_tau - 1.0) + 2.0 * gamma
        if abs(denom) < 1e-12:
            denom = 1e-12

        B_tau = (2.0 * (exp_gamma_tau - 1.0)) / denom
        numerator_A = 2.0 * gamma * math.exp((self.kappa + gamma) * tau / 2.0)
        power_A = (2.0 * self.kappa * self.theta) / (self.sigma ** 2)
        A_tau = (numerator_A / denom) ** power_A

        price = A_tau * math.exp(-B_tau * r_t)
        return max(0.0, price)

    def yield_to_maturity(self, t: float, T: float, r_t: Optional[float] = None) -> float:
        """Vadeye kadar getiri (Zero Rate): Y(t, T) = -ln(P(t, T)) / (T - t)"""
        if T <= t:
            return self.r0
        price = self.zero_coupon_bond_price(t, T, r_t)
        if price <= 0:
            return 1.0
        return -math.log(price) / (T - t)

    def simulate_paths(self, T: float, steps: int, n_paths: int = 1000, seed: Optional[int] = 42) -> np.ndarray:
        """
        Tam Euler-Maruyama (Full Truncation) simülasyonu ile CIR faiz yolları üretimi.
        """
        if seed is not None:
            np.random.seed(seed)

        dt = T / steps
        rates = np.zeros((n_paths, steps + 1))
        rates[:, 0] = self.r0

        sqrt_dt = math.sqrt(dt)
        for s in range(steps):
            r_prev = np.maximum(rates[:, s], 0.0)
            z = np.random.standard_normal(n_paths)
            dr = self.kappa * (self.theta - r_prev) * dt + self.sigma * np.sqrt(r_prev) * sqrt_dt * z
            rates[:, s + 1] = np.maximum(r_prev + dr, 0.0)

        return rates

    def cir_plus_plus_shift(self, market_discount_factors: Dict[float, float]) -> Dict[float, float]:
        """
        CIR++ Kalibrasyon Kaydırması:
        phi(t) = f_market(0, t) - f_cir(0, t)
        Sıfır kuponlu piyasa fiyatlarına kusursuz uyum sağlar: P^M(0, T) = P^CIR(0, T) * exp(-int_0^T phi(u) du)
        """
        shifts = {}
        for T, p_m in market_discount_factors.items():
            if T <= 0:
                shifts[T] = 0.0
                continue
            p_cir = self.zero_coupon_bond_price(0.0, T, self.r0)
            int_phi = (math.log(p_cir) - math.log(p_m)) / T
            shifts[T] = float(int_phi)
        return shifts


# ==============================================================================
# 2. QUANTO TÜREV FİYATLAMASI & GİRSANOV NUMERAIRE DEĞİŞİMİ
# ==============================================================================

class QuantoOptionEngine:
    """
    Çapraz Para Cinsi (Cross-Currency) Quanto Opsiyon Fiyatlama Motoru.
    Yabancı hisse/varlık S_t (yabancı para cinsinden), yerel para ödemesi sabit FX kuru F0 üzerinden.
    Radon-Nikodym türevi ve Girsanov dönüşümü ile yabancı ölçüden yerel risk-nötr ölçüye geçiş.
    Quanto drift düzeltmesi: mu_quanto = r_d - q - rho * sigma_S * sigma_X
    """

    def __init__(
        self,
        S0: float,
        K: float,
        T: float,
        r_d: float,      # Yerel faiz oranı (Domestic risk-free rate)
        r_f: float,      # Yabancı faiz oranı (Foreign risk-free rate)
        q: float,        # Temettü verimi (Dividend yield)
        sigma_S: float,  # Varlık oynaklığı (Asset volatility)
        sigma_X: float,  # FX kuru oynaklığı (Exchange rate volatility)
        rho: float,      # Varlık ile FX kuru arasındaki korelasyon
        F0: float = 1.0  # Sabit çevrim FX kuru (Pre-determined FX rate, örn. 1 USD/EUR)
    ):
        if S0 <= 0 or K <= 0 or T <= 0:
            raise ValueError("S0, K ve T pozitif olmalıdır.")
        if sigma_S <= 0 or sigma_X <= 0:
            raise ValueError("Oynaklıklar pozitif olmalıdır.")
        if not (-1.0 <= rho <= 1.0):
            raise ValueError("Korelasyon rho [-1, 1] aralığında olmalıdır.")

        self.S0 = float(S0)
        self.K = float(K)
        self.T = float(T)
        self.r_d = float(r_d)
        self.r_f = float(r_f)
        self.q = float(q)
        self.sigma_S = float(sigma_S)
        self.sigma_X = float(sigma_X)
        self.rho = float(rho)
        self.F0 = float(F0)

    @property
    def quanto_drift_adjustment(self) -> float:
        """Kovaryans sürüklenmesi: - rho * sigma_S * sigma_X"""
        return - self.rho * self.sigma_S * self.sigma_X

    @property
    def effective_quanto_drift(self) -> float:
        """Yerel risk-nötr ölçü altındaki beklenen varlık getiri kayması: r_d - q - rho * sigma_S * sigma_X"""
        return self.r_d - self.q + self.quanto_drift_adjustment

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        return math.exp(-0.5 * (x ** 2)) / math.sqrt(2.0 * math.pi)

    def price_quanto_call(self) -> Dict[str, float]:
        """
        Analitik Quanto Call Değerlemesi ve Greeks.
        Ödeme (yerel para cinsinden): F0 * max(S_T - K, 0)
        """
        sqrt_T = math.sqrt(self.T)
        vol_total = self.sigma_S * sqrt_T

        b_eff = self.effective_quanto_drift

        d1 = (math.log(self.S0 / self.K) + (b_eff + 0.5 * (self.sigma_S ** 2)) * self.T) / vol_total
        d2 = d1 - vol_total

        discount_asset = math.exp((b_eff - self.r_d) * self.T)
        discount_strike = math.exp(-self.r_d * self.T)

        call_price = self.F0 * (self.S0 * discount_asset * self._norm_cdf(d1) - self.K * discount_strike * self._norm_cdf(d2))

        delta = self.F0 * discount_asset * self._norm_cdf(d1)
        gamma = self.F0 * discount_asset * self._norm_pdf(d1) / (self.S0 * vol_total)
        vega = self.F0 * self.S0 * discount_asset * sqrt_T * self._norm_pdf(d1)
        d_price_d_rho = - self.F0 * self.S0 * self.sigma_S * self.sigma_X * self.T * discount_asset * self._norm_cdf(d1)

        return {
            "quanto_call_price": float(call_price),
            "quanto_delta": float(delta),
            "quanto_gamma": float(gamma),
            "quanto_vega": float(vega),
            "d_price_d_rho": float(d_price_d_rho),
            "effective_drift": float(b_eff),
            "quanto_adjustment": float(self.quanto_drift_adjustment)
        }


# ==============================================================================
# 3. ENGLE-RUSSELL (1998) AUTOREGRESSIVE CONDITIONAL DURATION (ACD) MODELİ
# ==============================================================================

class ACDModelEngine:
    """
    Engle & Russell (1998) Otoregresif Koşullu Süre (ACD) Modeli.
    İşlemler arasındaki geçen süre: x_i = t_i - t_{i-1}
    Koşullu beklenen süre: psi_i = omega + alpha * x_{i-1} + beta * psi_{i-1}
    Standartlaştırılmış kalıntı: eps_i = x_i / psi_i
    Durağanlık: alpha + beta < 1
    """

    def __init__(self, omega: float, alpha: float, beta: float):
        if omega <= 0 or alpha < 0 or beta < 0:
            raise ValueError("Parametreler pozitif olmalıdır.")
        if alpha + beta >= 1.0:
            raise ValueError("Durağanlık ihlali: alpha + beta < 1 olmalıdır.")

        self.omega = float(omega)
        self.alpha = float(alpha)
        self.beta = float(beta)

    @property
    def unconditional_mean_duration(self) -> float:
        """Koşulsuz ortalama işlem aralığı süresi."""
        return self.omega / (1.0 - self.alpha - self.beta)

    def filter_durations(self, durations: List[float]) -> Dict[str, Any]:
        """
        Gözlemlenen işlem süreleri dizisi üzerinden koşullu beklenen süre (psi) ve
        standartlaştırılmış kalıntıları (epsilon) filtreler.
        """
        n = len(durations)
        if n == 0:
            return {"psi": [], "residuals": [], "mean_psi": 0.0, "log_likelihood": 0.0}

        psi = np.zeros(n)
        psi[0] = self.unconditional_mean_duration

        for i in range(1, n):
            psi[i] = self.omega + self.alpha * durations[i - 1] + self.beta * psi[i - 1]

        residuals = np.array(durations) / psi
        ll = - np.sum(np.log(np.maximum(psi, 1e-12)) + residuals)

        return {
            "psi": psi.tolist(),
            "residuals": residuals.tolist(),
            "mean_psi": float(np.mean(psi)),
            "log_likelihood": float(ll),
            "unconditional_mean": float(self.unconditional_mean_duration)
        }

    def detect_liquidity_clustering(self, durations: List[float], threshold_ratio: float = 0.5) -> List[int]:
        """
        İşlem kümelenmesi (Clustering / Toxic Flow) tespiti:
        Beklenen sürenin ortalamanın threshold_ratio katı altına indiği anlar.
        """
        res = self.filter_durations(durations)
        psi = np.array(res["psi"])
        cutoff = self.unconditional_mean_duration * threshold_ratio
        indices = np.where(psi < cutoff)[0].tolist()
        return indices


# ==============================================================================
# 4. JOHANSEN EŞBÜTÜNLEŞME TESTİ & BERTRAM (2010) OU PAIRS TRADING
# ==============================================================================

class JohansenBertramStatArbEngine:
    """
    1. Johansen (1991) VECM Eşbütünleşme Analitiği.
    2. Bertram (2010) Ornstein-Uhlenbeck Analitik Optimal Giriş/Çıkış Sınırları.
       dX_t = - theta * (X_t - mu) dt + sigma dW_t
    """

    def __init__(self, mu: float = 0.0, theta: float = 1.0, sigma: float = 0.2):
        if theta <= 0 or sigma <= 0:
            raise ValueError("theta ve sigma pozitif olmalıdır.")
        self.mu = float(mu)
        self.theta = float(theta)
        self.sigma = float(sigma)

    @staticmethod
    def johansen_two_asset_cointegration(y1: np.ndarray, y2: np.ndarray) -> Dict[str, Any]:
        """
        İki serili analitik Johansen eşbütünleşme analitiği ve VECM katsayıları.
        """
        n = len(y1)
        if n < 10:
            raise ValueError("Yeterli veri noktası yok (min 10).")

        dy = np.column_stack([np.diff(y1), np.diff(y2)])
        y_lag = np.column_stack([y1[:-1], y2[:-1]])

        dy_c = dy - np.mean(dy, axis=0)
        y_lag_c = y_lag - np.mean(y_lag, axis=0)

        T_eff = len(dy)
        S00 = (dy_c.T @ dy_c) / T_eff
        S11 = (y_lag_c.T @ y_lag_c) / T_eff
        S01 = (dy_c.T @ y_lag_c) / T_eff
        S10 = S01.T

        try:
            inv_S00 = np.linalg.pinv(S00)
            M = np.linalg.pinv(S11) @ S10 @ inv_S00 @ S01
            eigenvalues, eigenvectors = np.linalg.eig(M)

            idx = np.argsort(np.real(eigenvalues))[::-1]
            eigenvalues = np.real(eigenvalues[idx])
            eigenvectors = np.real(eigenvectors[:, idx])

            trace_stat_r0 = - T_eff * (np.log(max(1e-12, 1.0 - eigenvalues[0])) + np.log(max(1e-12, 1.0 - eigenvalues[1])))
            trace_stat_r1 = - T_eff * np.log(max(1e-12, 1.0 - eigenvalues[1]))

            beta = eigenvectors[:, 0]
            if abs(beta[0]) > 1e-12:
                beta = beta / beta[0]

            is_cointegrated = bool(trace_stat_r0 > 15.49)

            # Cointegrating relation: beta[0]*y1 + beta[1]*y2 = 0 -> y2 = (-beta[0]/beta[1])*y1
            hr_y2_on_y1 = float(-beta[0] / beta[1]) if abs(beta[1]) > 1e-12 else 0.0
            hr_y1_on_y2 = float(-beta[1] / beta[0]) if abs(beta[0]) > 1e-12 else 0.0

            return {
                "eigenvalues": eigenvalues.tolist(),
                "beta_vector": beta.tolist(),
                "hedge_ratio": hr_y2_on_y1,
                "hedge_ratio_y2_on_y1": hr_y2_on_y1,
                "hedge_ratio_y1_on_y2": hr_y1_on_y2,
                "trace_stat_r0": float(trace_stat_r0),
                "trace_stat_r1": float(trace_stat_r1),
                "is_cointegrated": is_cointegrated
            }
        except Exception as e:
            return {"error": str(e), "is_cointegrated": False, "hedge_ratio": 1.0}

    def bertram_optimal_boundaries(self, c: float = 0.001) -> Dict[str, float]:
        """
        Bertram (2010) Analitik Optimal Giriş/Çıkış Sınırları.
        c: Sabit işlem maliyeti (komisyon + slippage).
        """
        scale = self.sigma / math.sqrt(2.0 * self.theta)
        eps = max(1e-6, c / scale)

        d_opt = scale * ((3.0 * eps) ** (1.0 / 3.0) + eps)
        entry_threshold = self.mu - d_opt
        exit_threshold = self.mu

        expected_duration = (math.pi / self.theta) * (d_opt / scale)
        expected_return_per_trade = max(0.0, d_opt - c)

        return {
            "optimal_entry_level": float(entry_threshold),
            "optimal_exit_level": float(exit_threshold),
            "optimal_entry_zscore": float(-d_opt / scale),
            "optimal_distance": float(d_opt),
            "expected_trade_duration": float(expected_duration),
            "expected_return_per_trade": float(expected_return_per_trade),
            "cost_c": float(c)
        }


# ==============================================================================
# 5. BARNDORFF-NIELSEN & SHEPHARD (2004) BIPOWER VARIATION & JUMP DETECTION
# ==============================================================================

class BNSJumpDetectionEngine:
    """
    Barndorff-Nielsen & Shephard (2004, 2006) Bipower Varyansı ve Sıçrama Z-Testi.
    Realized Variance: RV = sum(r_i^2) -> IV + JV
    Realized Bipower Variation: BV = (pi / 2) * sum(|r_i| * |r_{i-1}|) -> IV (Sıçramasız)
    """

    MU_1 = math.sqrt(2.0 / math.pi)
    CONST_V = (math.pi ** 2) / 4.0 + math.pi - 3.0

    @classmethod
    def calculate_bipower_variation(cls, intraday_returns: np.ndarray) -> Dict[str, float]:
        """
        RV, BV, Tri-power Quarticity (TQ) ve Sıçrama Bileşeni ayrıştırması.
        """
        r = np.asarray(intraday_returns, dtype=float)
        N = len(r)
        if N < 5:
            raise ValueError("BNS testi için en az 5 gün içi getiri gereklidir.")

        RV = float(np.sum(r ** 2))
        abs_r = np.abs(r)
        BV = float((1.0 / (cls.MU_1 ** 2)) * np.sum(abs_r[1:] * abs_r[:-1]))

        mu_4_3 = 2.0 ** (2.0 / 3.0) * math.gamma(7.0 / 6.0) / math.sqrt(math.pi)
        r_4_3 = abs_r ** (4.0 / 3.0)
        tq_sum = np.sum(r_4_3[2:] * r_4_3[1:-1] * r_4_3[:-2])
        TQ = float(N * (mu_4_3 ** (-3)) * tq_sum)

        JV = max(0.0, RV - BV)
        relative_jump = JV / RV if RV > 1e-12 else 0.0

        denominator_term = cls.CONST_V * max(1.0, TQ / (BV ** 2 + 1e-12)) / N
        denom = math.sqrt(max(1e-14, denominator_term))

        Z_stat = ((RV - BV) / (RV + 1e-14)) / denom

        has_jump_95 = bool(Z_stat > 1.96)
        has_jump_99 = bool(Z_stat > 2.576)

        return {
            "realized_variance": RV,
            "bipower_variation": BV,
            "jump_variation": JV,
            "relative_jump_share": relative_jump,
            "tri_power_quarticity": TQ,
            "z_statistic": float(Z_stat),
            "has_significant_jump_95": has_jump_95,
            "has_significant_jump_99": has_jump_99,
            "sample_size": N
        }


# ==============================================================================
# 6. CURVE STABLESWAP AMM DEĞİŞMEZİ & DİNAMİK A PARAMETRESİ (EGOROV 2019)
# ==============================================================================

class CurveStableswapEngine:
    """
    Michael Egorov (2019) Curve Stableswap Havuz Değişmezi (Invariant).
    A * n^n * sum(x_i) + D = A * D * n^n + D^(n+1) / (n^n * prod(x_i))
    """

    def __init__(self, A: float, n_coins: int = 2):
        if A <= 0:
            raise ValueError("Amplifikasyon parametresi A pozitif olmalıdır.")
        if n_coins < 2:
            raise ValueError("En az 2 varlık olmalıdır.")

        self.A = float(A)
        self.n_coins = int(n_coins)

    def calculate_D(self, xp: List[float], max_iter: int = 255, tol: float = 1e-7) -> float:
        """
        Mevcut bakiye vektörü xp için Newton-Raphson ile D invariantını çözer.
        """
        S = sum(xp)
        if S == 0:
            return 0.0

        n = self.n_coins
        Ann = self.A * (n ** n)

        D = S
        for _ in range(max_iter):
            D_P = D
            for x in xp:
                if x <= 0:
                    x = 1e-12
                D_P = (D_P * D) / (x * n)

            D_prev = D
            num = (Ann * S + D_P * n) * D
            den = (Ann - 1.0) * D + (n + 1.0) * D_P

            if den == 0:
                break

            D = num / den

            if abs(D - D_prev) <= tol:
                return float(D)

        return float(D)

    def calculate_y(self, i: int, j: int, x_in: float, xp: List[float], max_iter: int = 255, tol: float = 1e-7) -> float:
        """
        i-inci varlıktan x_in eklenip j-inci varlıktan takas yapıldığında,
        havuzda kalması gereken yeni y_j bakiyesini çözer.
        """
        n = self.n_coins
        Ann = self.A * (n ** n)

        D = self.calculate_D(xp)

        xp_new = list(xp)
        xp_new[i] += x_in

        S_prime = 0.0
        c = D
        for k in range(n):
            if k == j:
                continue
            _x = xp_new[k]
            S_prime += _x
            c = (c * D) / (_x * n)

        c = (c * D) / (Ann * n)
        b = S_prime + D / Ann

        y = D
        for _ in range(max_iter):
            y_prev = y
            num = y * y + c
            den = 2.0 * y + b - D
            if den == 0:
                break
            y = num / den

            if abs(y - y_prev) <= tol:
                return float(y)

        return float(y)

    def calculate_swap(self, i: int, j: int, dx: float, xp: List[float], fee: float = 0.0004) -> Dict[str, float]:
        """
        Takas simülasyonu: dx miktar i verilip net dy miktar j alınır.
        """
        if dx <= 0:
            return {"dy": 0.0, "fee_amount": 0.0, "slippage_pct": 0.0}

        y_new = self.calculate_y(i, j, dx, xp)
        dy_gross = xp[j] - y_new
        fee_amount = dy_gross * fee
        dy_net = max(0.0, dy_gross - fee_amount)

        slippage_pct = ((dx - dy_net) / dx) * 100.0 if dx > 0 else 0.0

        return {
            "dx_in": float(dx),
            "dy_gross": float(dy_gross),
            "fee_amount": float(fee_amount),
            "dy_net": float(dy_net),
            "slippage_pct": float(slippage_pct),
            "new_balance_j": float(y_new)
        }

    def depeg_stress_test(self, xp: List[float], drain_ratio: float = 0.8) -> Dict[str, float]:
        """
        Depeg Stres Testi: Bir varlığın drain_ratio oranı kadarı satıldığında
        amplifikasyon katsayısının sağladığı kayma ve fiyat çöküşünü ölçer.
        """
        D_initial = self.calculate_D(xp)
        dx_stress = xp[0] * drain_ratio
        swap_res = self.calculate_swap(0, 1, dx_stress, xp)

        marginal_price = swap_res["dy_net"] / dx_stress if dx_stress > 0 else 1.0

        return {
            "initial_D": float(D_initial),
            "drain_ratio": float(drain_ratio),
            "stressed_slippage_pct": float(swap_res["slippage_pct"]),
            "marginal_exchange_rate": float(marginal_price),
            "amplification_A": float(self.A)
        }
