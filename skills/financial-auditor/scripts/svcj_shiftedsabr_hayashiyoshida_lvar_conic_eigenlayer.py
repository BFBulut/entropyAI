"""Phase 30: Quantitative Financial Engineering, Stochastic Volatility with Jumps, Market Incompleteness & Cryptoeconomic Risk.

Core Pillars:
1. Bates & Eraker-Johannes-Polson (2003) SVCJ: Stochastic Volatility with Contemporaneous Jumps in Price & Variance
2. Shifted-SABR & Normal SABR (Bachelier SABR) for Negative and Zero Interest Rates (Hagan et al., Antonov et al. 2015)
3. Hayashi-Yoshida (2005) Asynchronous High-Frequency Covariance & Lead-Lag Latency Arbitrage
4. Liquidity-Adjusted Value-at-Risk & Expected Shortfall (L-VaR & L-ES: Bangia et al. 1999 & Jarrow-Subramanian 1997)
5. Madan-Schoutens (2008) Conic Finance & Two-Price Economy via Choquet Integrals & Wang / MinMaxVar Distortions
6. EigenLayer Re-Staking Topology, Correlated Slashing Cascades & LRT Unbonding De-Peg Arbitrage
"""

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# COMMON PROBABILITY & STATISTICAL UTILITIES
# ==============================================================================

def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def norm_ppf(p: float) -> float:
    """Standard normal quantile function (inverse CDF) using rational approximation."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability p must be strictly in (0, 1).")
    
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        val = q * (((((((2.5090809287301226727e+3 * r +
                          3.3430575583588128105e+4) * r +
                         6.7265770927008700853e+4) * r +
                        4.5921953931549871457e+4) * r +
                       1.3731693765509461125e+4) * r +
                      1.6444856003732066898e+3) * r +
                     6.4172559304746224345e+1) * r +
                    1.0) / (((((((5.2264952788528545610e+3 * r +
                                  2.8729085735721942674e+4) * r +
                                 3.9307895800092710610e+4) * r +
                                2.1213794576983054817e+4) * r +
                               5.3941960214247511077e+3) * r +
                              6.8718700749205790830e+2) * r +
                             3.2660588998492026362e+1) * r + 1.0)
        return val
    
    r = p if q < 0.0 else 1.0 - p
    r = math.sqrt(-math.log(r))
    if r <= 5.0:
        r -= 1.6
        val = (((((((7.74545014278341407640e-4 * r +
                     2.12137945769830548170e-2) * r +
                    2.04426310338993978564e-1) * r +
                   8.01633519391104642998e-1) * r +
                  1.35084924976722881459e+0) * r +
                 9.14128529597142694902e-1) * r +
                2.14941603842528141516e-1) * r +
               1.08587788589025078170e-3) / (((((((2.01678553254128526910e-4 * r +
                                                  8.67807322029460844720e-3) * r +
                                                 1.28883830341572793400e-1) * r +
                                                7.76304275601438257700e-1) * r +
                                               2.11583726882866659950e+0) * r +
                                              2.56852019228982242190e+0) * r +
                                             1.29736722281774997340e+0) * r + 1.0)
    else:
        r -= 5.0
        val = (((((((2.01033439929228813265e-7 * r +
                     2.71155556874348757815e-5) * r +
                    1.24266129188057279292e-3) * r +
                   2.65321897265764230307e-2) * r +
                  2.96560571828504891230e-1) * r +
                 1.63640453308952015242e+0) * r +
                3.70891299931515216301e+0) * r +
               2.67667347960708688593e+0) / (((((((2.03610414066806987300e-8 * r +
                                                  3.54047474070604353270e-6) * r +
                                                 2.14941603842528141516e-4) * r +
                                                5.83970642288018608880e-3) * r +
                                               7.41284566089304642998e-2) * r +
                                              4.18341258883830341570e-1) * r +
                                             1.0) * r + 1.0)
    return -val if q < 0.0 else val


# ==============================================================================
# 1. BATES & ERAKER-JOHANNES-POLSON (2003) SVCJ ENGINE
# ==============================================================================

@dataclass
class SVCJCalibrationResult:
    call_price: float
    put_price: float
    characteristic_re: float
    characteristic_im: float
    jump_risk_premium: float
    total_variance: float
    skewness: float
    kurtosis: float


class SVCJOptionEngine:
    """Stochastic Volatility with Contemporaneous Jumps in Price and Variance.
    
    References:
    - Eraker, B., Johannes, M., & Polson, N. (2003). The impact of jumps in volatility and returns.
      The Journal of Finance, 58(3), 1269-1300.
    - Bates, D. S. (1996). Jumps and stochastic volatility: Exchange rate processes implicit in Deutsche mark options.
      The Review of Financial Studies, 9(1), 69-107.
    - Duffie, D., Pan, J., & Singleton, K. (2000). Transform analysis and asset pricing for affine jump-diffusions.
      Econometrica, 68(6), 1343-1376.
    """

    def __init__(
        self,
        spot: float = 100.0,
        rate: float = 0.05,
        dividend: float = 0.02,
        v0: float = 0.04,          # Initial variance (20% vol)
        kappa: float = 2.0,        # Mean reversion speed of variance
        theta: float = 0.04,       # Long-run variance
        sigma_v: float = 0.3,      # Vol-of-vol
        rho: float = -0.7,         # Spot-vol correlation
        jump_intensity: float = 0.2, # Jump arrival rate lambda
        mu_s: float = -0.05,       # Mean jump in log-asset
        sigma_s: float = 0.10,     # Volatility of jump in log-asset
        mu_v: float = 0.05,        # Mean jump in variance (exponential)
        rho_j: float = -0.5,       # Correlation between price jump and variance jump
    ):
        if spot <= 0.0 or v0 <= 0.0 or kappa <= 0.0 or theta <= 0.0 or sigma_v <= 0.0:
            raise ValueError("Spot, v0, kappa, theta, and sigma_v must be strictly positive.")
        if abs(rho) > 1.0 or jump_intensity < 0.0 or mu_v <= 0.0:
            raise ValueError("rho must be in [-1, 1], jump_intensity >= 0, mu_v > 0.")
        if rho_j * mu_v >= 1.0:
            raise ValueError("Condition rho_j * mu_v < 1 is required for finite jump expectation.")

        self.spot = spot
        self.rate = rate
        self.dividend = dividend
        self.v0 = v0
        self.kappa = kappa
        self.theta = theta
        self.sigma_v = sigma_v
        self.rho = rho
        self.jump_intensity = jump_intensity
        self.mu_s = mu_s
        self.sigma_s = sigma_s
        self.mu_v = mu_v
        self.rho_j = rho_j

        denom = 1.0 - self.rho_j * self.mu_v
        if denom <= 0.0:
            raise ValueError("Invalid jump parameter configuration: denom <= 0.")
        self.k_bar = (math.exp(self.mu_s + 0.5 * (self.sigma_s ** 2)) / denom) - 1.0

    def characteristic_function(self, u: complex, t: float) -> complex:
        """Computes the analytical characteristic function of ln(S_T) under the risk-neutral measure."""
        i = 1j
        r = self.rate
        q = self.dividend
        sig_v = self.sigma_v
        k = self.kappa
        th = self.theta
        p = self.rho

        drift_adj = (r - q - self.jump_intensity * self.k_bar)

        d = np.sqrt((p * sig_v * i * u - k) ** 2 + (sig_v ** 2) * (i * u + u ** 2))
        g = (k - p * sig_v * i * u - d) / (k - p * sig_v * i * u + d)

        exp_dt = np.exp(-d * t)
        D_t = ((k - p * sig_v * i * u - d) / (sig_v ** 2)) * ((1.0 - exp_dt) / (1.0 - g * exp_dt))

        C_diff = (k * th / (sig_v ** 2)) * ((k - p * sig_v * i * u - d) * t - 2.0 * np.log((1.0 - g * exp_dt) / (1.0 - g)))

        jump_denom = 1.0 - self.mu_v * (D_t + i * u * self.rho_j)
        jump_num = np.exp(i * u * self.mu_s - 0.5 * (u ** 2) * (self.sigma_s ** 2))
        
        if abs(jump_denom) < 1e-12:
            jump_factor = 1.0
        else:
            jump_factor = jump_num / jump_denom

        C_jump = self.jump_intensity * t * (jump_factor - 1.0)
        C_t = C_diff + C_jump

        phi = np.exp(C_t + D_t * self.v0 + i * u * np.log(self.spot) + i * u * drift_adj * t)
        return phi

    def price_european_option(
        self,
        strike: float,
        maturity: float,
        is_call: bool = True,
        num_points: int = 128,
        upper_limit: float = 80.0,
    ) -> float:
        """Prices European option via Gil-Pelaez Fourier inversion."""
        if strike <= 0.0 or maturity <= 0.0:
            raise ValueError("Strike and maturity must be positive.")

        k_log = math.log(strike)
        i = 1j

        def integrand1(u: float) -> float:
            phi_minus_i = self.characteristic_function(-i, maturity)
            phi_val = self.characteristic_function(u - i, maturity)
            val = (np.exp(-i * u * k_log) * phi_val / (i * u * phi_minus_i)).real
            return float(val)

        def integrand2(u: float) -> float:
            phi_val = self.characteristic_function(u, maturity)
            val = (np.exp(-i * u * k_log) * phi_val / (i * u)).real
            return float(val)

        u_nodes, weights = np.polynomial.legendre.leggauss(num_points)
        a = 1e-4
        b = upper_limit
        u_scaled = 0.5 * (b - a) * u_nodes + 0.5 * (b + a)
        w_scaled = 0.5 * (b - a) * weights

        int1 = sum(w * integrand1(u) for u, w in zip(u_scaled, w_scaled))
        int2 = sum(w * integrand2(u) for u, w in zip(u_scaled, w_scaled))

        p1 = 0.5 + (1.0 / math.pi) * int1
        p2 = 0.5 + (1.0 / math.pi) * int2

        p1 = max(0.0, min(1.0, p1))
        p2 = max(0.0, min(1.0, p2))

        df_q = math.exp(-self.dividend * maturity)
        df_r = math.exp(-self.rate * maturity)

        call_price = self.spot * df_q * p1 - strike * df_r * p2
        call_price = max(0.0, call_price)

        if is_call:
            return call_price
        else:
            put_price = call_price - self.spot * df_q + strike * df_r
            return max(0.0, put_price)

    def compute_moments(self, t: float) -> Dict[str, float]:
        """Calculates total variance, annualized volatility, and jump contribution."""
        diff_var = self.v0 * t
        jump_var = self.jump_intensity * t * (self.sigma_s ** 2 + self.mu_s ** 2 + (self.rho_j * self.mu_v) ** 2)
        total_var = diff_var + jump_var
        ann_vol = math.sqrt(total_var / max(1e-6, t))
        jump_share = jump_var / max(1e-12, total_var)

        return {
            "total_variance": total_var,
            "annualized_vol": ann_vol,
            "jump_variance": jump_var,
            "jump_share_pct": jump_share * 100.0,
            "k_bar": self.k_bar,
        }


# ==============================================================================
# 2. SHIFTED-SABR & NORMAL (BACHELIER) SABR FOR NEGATIVE RATES
# ==============================================================================

@dataclass
class ShiftedSABRResult:
    normal_vol: float          # Bachelier / normal implied volatility
    shifted_black_vol: float   # Shifted Black-76 implied volatility
    call_price: float          # Option call price
    put_price: float           # Option put price
    atm_vol: float             # At-the-money normal volatility
    density_positive: bool     # Verification that risk-neutral density is non-negative


class ShiftedSABREngine:
    """Shifted and Normal (Bachelier) SABR Engine for Negative & Low Interest Rates.
    
    References:
    - Hagan, P. S., Kumar, D., Lesniewski, A. S., & Woodward, D. E. (2002). Managing smile risk.
      Wilmott Magazine, 84-108.
    - Antonov, A., Konikov, M., & Spector, M. (2015). Modern SABR Analytics. Springer.
    - Paulot, L. (2015). Asymptotic implied volatility at the second order with applications to the SABR model.
      International Journal of Theoretical and Applied Finance, 18(04), 1550025.
    """

    def __init__(
        self,
        forward_rate: float = 0.015,  # Can be negative (e.g. -0.005)
        shift: float = 0.03,          # Shift s such that forward + shift > 0
        alpha: float = 0.008,         # Initial normal/lognormal vol
        beta: float = 0.0,            # beta = 0 corresponds to Normal SABR (Bachelier)
        rho: float = -0.25,           # Correlation between forward and vol
        nu: float = 0.40,             # Vol-of-vol
    ):
        if forward_rate + shift <= 0.0 and beta > 0.0:
            raise ValueError(f"forward_rate + shift must be strictly positive for beta > 0 (got {forward_rate + shift}).")
        if alpha <= 0.0 or nu < 0.0 or abs(rho) > 1.0:
            raise ValueError("alpha > 0, nu >= 0, and |rho| <= 1 required.")

        self.forward = forward_rate
        self.shift = shift
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.nu = nu

    def normal_sabr_volatility(self, strike: float, maturity: float) -> float:
        """Calculates Hagan's analytical Normal (Bachelier) Implied Volatility (beta = 0).
        
        sigma_N(F, K) = alpha * (zeta / x(zeta)) * [1 + (2 - 3*rho^2)/24 * nu^2 * T]
        where zeta = (nu / alpha) * (F - K).
        """
        f = self.forward
        k = strike
        t = maturity
        a = self.alpha
        r = self.rho
        n = self.nu

        if t <= 0.0:
            return a

        zeta = (n / a) * (f - k)

        if abs(zeta) < 1e-6:
            corr_factor = 1.0 + ((2.0 - 3.0 * (r ** 2)) / 24.0) * (n ** 2) * t
            return float(a * corr_factor)

        sqrt_term = math.sqrt(max(1e-12, 1.0 - 2.0 * r * zeta + zeta ** 2))
        num = sqrt_term + zeta - r
        denom = 1.0 - r
        if num / denom <= 0.0:
            x_zeta = zeta
        else:
            x_zeta = math.log(num / denom)

        base_vol = a * (zeta / x_zeta)
        corr_factor = 1.0 + ((2.0 - 3.0 * (r ** 2)) / 24.0) * (n ** 2) * t
        return float(base_vol * corr_factor)

    def bachelier_option_price(
        self,
        strike: float,
        maturity: float,
        is_call: bool = True,
        discount_factor: float = 1.0,
    ) -> float:
        """Prices European option under Bachelier (Normal) model for any forward/strike (including negative)."""
        f = self.forward
        k = strike
        t = maturity
        sigma_n = self.normal_sabr_volatility(strike, maturity)

        if t <= 0.0:
            return discount_factor * max(0.0, (f - k) if is_call else (k - f))

        std_dev = sigma_n * math.sqrt(t)
        if std_dev < 1e-12:
            return discount_factor * max(0.0, (f - k) if is_call else (k - f))

        d = (f - k) / std_dev
        call_val = discount_factor * ((f - k) * norm_cdf(d) + std_dev * norm_pdf(d))
        call_val = max(0.0, call_val)

        if is_call:
            return call_val
        else:
            put_val = call_val - discount_factor * (f - k)
            return max(0.0, put_val)

    def shifted_black_volatility(self, strike: float, maturity: float) -> float:
        """Hagan Shifted-Black formula for forward rates with shift s."""
        f_shift = self.forward + self.shift
        k_shift = strike + self.shift

        if f_shift <= 0.0 or k_shift <= 0.0:
            raise ValueError(f"Shifted forward and strike must be positive (f={f_shift}, k={k_shift}).")

        a = self.alpha
        b = self.beta if self.beta > 0.0 else 0.5
        r = self.rho
        n = self.nu
        t = maturity

        f_mid = math.sqrt(f_shift * k_shift)
        log_fk = math.log(f_shift / k_shift)

        denom1 = (f_mid ** (1.0 - b)) * (1.0 + (((1.0 - b) ** 2) / 24.0) * (log_fk ** 2))
        zeta = (n / a) * (f_mid ** (1.0 - b)) * log_fk

        if abs(zeta) < 1e-6:
            z_ratio = 1.0
        else:
            sqrt_t = math.sqrt(max(1e-12, 1.0 - 2.0 * r * zeta + zeta ** 2))
            x_z = math.log((sqrt_t + zeta - r) / (1.0 - r))
            z_ratio = zeta / x_z

        term1 = a / denom1
        term2 = 1.0 + (
            (((1.0 - b) ** 2) / 24.0) * (a ** 2) / (f_mid ** (2.0 - 2.0 * b)) +
            0.25 * r * b * n * a / (f_mid ** (1.0 - b)) +
            ((2.0 - 3.0 * (r ** 2)) / 24.0) * (n ** 2)
        ) * t

        return float(term1 * z_ratio * term2)


# ==============================================================================
# 3. HAYASHI-YOSHIDA (2005) ASYNCHRONOUS COVARIANCE & LEAD-LAG
# ==============================================================================

@dataclass
class HayashiYoshidaResult:
    covariance: float          # Hayashi-Yoshida non-synchronous covariance
    correlation: float         # HY correlation coefficient
    rv_x: float                # Realized variance of X
    rv_y: float                # Realized variance of Y
    optimal_lag: float         # Lead-lag time shift tau* (seconds)
    lead_asset: str            # Identifier of the leading asset
    num_overlapping_pairs: int # Count of overlapping tick intervals


class HayashiYoshidaEngine:
    """Asynchronous High-Frequency Covariance Estimator and Lead-Lag Detection.
    
    References:
    - Hayashi, T., & Yoshida, N. (2005). On covariance estimation of non-synchronously observed diffusion processes.
      Bernoulli, 11(2), 359-379.
    - Hoffmann, M., Rosenbaum, M., & Yoshida, N. (2013). Estimation of the lead-lag parameter from non-synchronous data.
      Bernoulli, 19(2), 449-485.
    """

    def __init__(self, times_x: np.ndarray, prices_x: np.ndarray, times_y: np.ndarray, prices_y: np.ndarray):
        if len(times_x) != len(prices_x) or len(times_y) != len(prices_y):
            raise ValueError("Lengths of times and prices arrays must match.")
        if len(times_x) < 2 or len(times_y) < 2:
            raise ValueError("At least 2 points required per series.")

        self.times_x = np.asarray(times_x, dtype=np.float64)
        self.prices_x = np.asarray(prices_x, dtype=np.float64)
        self.times_y = np.asarray(times_y, dtype=np.float64)
        self.prices_y = np.asarray(prices_y, dtype=np.float64)

    def compute_hy_covariance(self, time_shift_y: float = 0.0) -> Tuple[float, float, float, int]:
        """Calculates Hayashi-Yoshida covariance between X and shifted Y.
        
        If tau > 0, Asset X leads Asset Y by tau (event in X appears at t + tau in Y).
        To align them, Y's timestamps are shifted back by tau: s_j - tau.
        """
        dx = np.diff(self.prices_x)
        tx_starts = self.times_x[:-1]
        tx_ends = self.times_x[1:]

        dy = np.diff(self.prices_y)
        ty_starts = self.times_y[:-1] - time_shift_y
        ty_ends = self.times_y[1:] - time_shift_y

        rv_x = float(np.sum(dx ** 2))
        rv_y = float(np.sum(dy ** 2))

        cov = 0.0
        overlap_count = 0

        j_start = 0
        m = len(dy)

        for i in range(len(dx)):
            t_start = tx_starts[i]
            t_end = tx_ends[i]

            while j_start < m and ty_ends[j_start] <= t_start:
                j_start += 1

            j = j_start
            while j < m and ty_starts[j] < t_end:
                if max(t_start, ty_starts[j]) < min(t_end, ty_ends[j]):
                    cov += dx[i] * dy[j]
                    overlap_count += 1
                j += 1

        return cov, rv_x, rv_y, overlap_count

    def detect_lead_lag(
        self,
        max_lag: float = 2.0,
        lag_steps: int = 41,
    ) -> HayashiYoshidaResult:
        """Finds optimal time shift tau* maximizing the absolute Hayashi-Yoshida cross-correlation."""
        lags = np.linspace(-max_lag, max_lag, lag_steps)
        best_corr = -1.0
        optimal_lag = 0.0
        best_cov = 0.0
        best_rv_x = 0.0
        best_rv_y = 0.0
        best_overlaps = 0

        for lag in lags:
            cov, rv_x, rv_y, overlaps = self.compute_hy_covariance(time_shift_y=lag)
            denom = math.sqrt(max(1e-12, rv_x * rv_y))
            raw_corr = cov / denom if denom > 0.0 else 0.0
            corr = max(-1.0, min(1.0, raw_corr))

            if abs(corr) > best_corr:
                best_corr = abs(corr)
                optimal_lag = lag
                best_cov = cov
                best_rv_x = rv_x
                best_rv_y = rv_y
                best_overlaps = overlaps

        lead_asset = "Neutral"
        if optimal_lag > 1e-4:
            lead_asset = "Asset X leads Asset Y"
        elif optimal_lag < -1e-4:
            lead_asset = "Asset Y leads Asset X"

        denom_final = math.sqrt(max(1e-12, best_rv_x * best_rv_y))
        final_corr = max(-1.0, min(1.0, best_cov / denom_final if denom_final > 0.0 else 0.0))

        return HayashiYoshidaResult(
            covariance=best_cov,
            correlation=final_corr,
            rv_x=best_rv_x,
            rv_y=best_rv_y,
            optimal_lag=optimal_lag,
            lead_asset=lead_asset,
            num_overlapping_pairs=best_overlaps,
        )


# ==============================================================================
# 4. LIQUIDITY-ADJUSTED VaR & EXPECTED SHORTFALL (L-VaR & L-ES)
# ==============================================================================

@dataclass
class LVaRResult:
    pure_var: float            # Classical market VaR without liquidity
    exogenous_l_cost: float    # Cost of crossing the stochastic bid-ask spread
    endogenous_l_cost: float   # Permanent/temporary price impact from block size
    total_l_var: float         # L-VaR = pure_var + exo_cost + endo_cost
    l_expected_shortfall: float # Liquidity-Adjusted Expected Shortfall (L-ES)
    liquidity_premium_pct: float # Percentage increase over pure VaR


class LiquidityRiskEngine:
    """Computes Liquidity-Adjusted VaR and ES combining Exogenous & Endogenous Friction.
    
    References:
    - Bangia, A., Diebold, F. X., Schuermann, T., & Stroughair, J. D. (1999). Liquidity on the outside.
      Risk, 12(6), 68-73.
    - Jarrow, R., & Subramanian, A. (1997). Mopping up liquidity. Risk, 10(12), 170-175.
    - Almgren, R., Thum, C., Hauptmann, E., & Li, H. (2005). Direct estimation of equity market impact.
      Risk, 18(7), 58-62.
    """

    def __init__(
        self,
        position_value: float = 10_000_000.0, # Total portfolio dollar value
        order_shares: float = 100_000.0,       # Number of shares to liquidate
        mid_price: float = 100.0,              # Current mid-price
        daily_volume: float = 1_000_000.0,     # Average daily trading volume in shares
        daily_volatility: float = 0.02,        # Asset price volatility (2% daily)
        mean_spread_pct: float = 0.002,        # Average relative bid-ask spread (20 bps)
        vol_spread_pct: float = 0.001,         # Spread volatility (10 bps)
        impact_gamma: float = 0.15,            # Endogenous price impact coefficient
    ):
        if position_value <= 0.0 or mid_price <= 0.0 or daily_volume <= 0.0:
            raise ValueError("Position, mid_price, and daily_volume must be positive.")

        self.position_value = position_value
        self.order_shares = order_shares
        self.mid_price = mid_price
        self.daily_volume = daily_volume
        self.daily_volatility = daily_volatility
        self.mean_spread_pct = mean_spread_pct
        self.vol_spread_pct = vol_spread_pct
        self.impact_gamma = impact_gamma

    def calculate_l_var(
        self,
        confidence_level: float = 0.99,
        holding_period_days: float = 1.0,
    ) -> LVaRResult:
        """Computes Bangia-Jarrow Liquidity-Adjusted VaR and Expected Shortfall."""
        if confidence_level <= 0.5 or confidence_level >= 1.0:
            raise ValueError("confidence_level must be in (0.5, 1.0).")

        z_alpha = norm_ppf(confidence_level)

        pure_var = self.position_value * z_alpha * self.daily_volatility * math.sqrt(holding_period_days)

        stressed_spread = max(0.0, self.mean_spread_pct + z_alpha * self.vol_spread_pct)
        exogenous_cost = 0.5 * self.position_value * stressed_spread

        participation_rate = self.order_shares / max(1.0, self.daily_volume)
        endogenous_cost = self.impact_gamma * (participation_rate ** 0.8) * self.position_value

        total_l_var = pure_var + exogenous_cost + endogenous_cost

        es_z = norm_pdf(z_alpha) / (1.0 - confidence_level)
        pure_es = self.position_value * es_z * self.daily_volatility * math.sqrt(holding_period_days)
        total_l_es = pure_es + exogenous_cost * (es_z / z_alpha) + endogenous_cost

        premium_pct = ((total_l_var - pure_var) / max(1e-6, pure_var)) * 100.0

        return LVaRResult(
            pure_var=pure_var,
            exogenous_l_cost=exogenous_cost,
            endogenous_l_cost=endogenous_cost,
            total_l_var=total_l_var,
            l_expected_shortfall=total_l_es,
            liquidity_premium_pct=premium_pct,
        )


# ==============================================================================
# 5. MADAN-SCHOUTENS (2008) CONIC FINANCE & TWO-PRICE ECONOMY
# ==============================================================================

@dataclass
class ConicTwoPriceResult:
    bid_price: float           # Acceptable bid price b(X)
    ask_price: float           # Acceptable ask price a(X)
    mid_price: float           # Linear expectation (one-price benchmark)
    spread: float              # Conic liquidity spread a(X) - b(X)
    distortion_type: str       # Wang or MinMaxVar
    stress_level: float        # Distortion parameter


class ConicFinanceEngine:
    """Two-Price Economy Valuation via Choquet Expectation under Distorted Probabilities.
    
    References:
    - Madan, D. B., & Schoutens, W. (2016). Applied Conic Finance. Cambridge University Press.
    - Cherny, A., & Madan, D. (2009). New measures for performance evaluation.
      The Review of Financial Studies, 22(7), 2571-2606.
    - Wang, S. S. (2000). A class of extreme risk measures.
      ASTIN Bulletin: The Journal of the IAA, 30(1), 153-167.
    """

    def __init__(self, samples: np.ndarray):
        """Initializes with empirical or simulated cash flow payoff samples X."""
        if len(samples) < 10:
            raise ValueError("At least 10 samples required for conic evaluation.")
        self.samples = np.sort(np.asarray(samples, dtype=np.float64))
        self.n = len(self.samples)

    def _wang_distortion(self, u: float, lambda_param: float) -> float:
        """Wang distortion Psi(u) = Phi(Phi^{-1}(u) - lambda) with lambda >= 0."""
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0
        z = norm_ppf(u)
        return norm_cdf(z - lambda_param)

    def _minmaxvar_distortion(self, u: float, gamma_param: float) -> float:
        """MinMaxVar distortion for survival probabilities: Psi(u) = (1 - (1 - u)^{1/(1+gamma)})^{1+gamma}."""
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0
        p = 1.0 / (1.0 + gamma_param)
        return float((1.0 - ((1.0 - u) ** p)) ** (1.0 + gamma_param))

    def price_cash_flow(
        self,
        distortion_type: str = "wang",
        distortion_param: float = 0.25,
    ) -> ConicTwoPriceResult:
        """Computes acceptable Bid and Ask prices via Choquet Riemann-Stieltjes summation."""
        if distortion_param < 0.0:
            raise ValueError("Distortion parameter must be non-negative.")

        if distortion_type.lower() == "wang":
            dist_fn = lambda u: self._wang_distortion(u, distortion_param)
        elif distortion_type.lower() == "minmaxvar":
            dist_fn = lambda u: self._minmaxvar_distortion(u, distortion_param)
        else:
            raise ValueError(f"Unknown distortion type: {distortion_type}")

        probs = (self.n - np.arange(self.n)) / self.n
        psi_probs = np.array([dist_fn(p) for p in probs])

        delta_psi_bid = np.diff(np.append(psi_probs, 0.0)) * -1.0
        bid_price = float(np.sum(self.samples * delta_psi_bid))

        neg_samples = np.sort(-self.samples)
        probs_ask = (self.n - np.arange(self.n)) / self.n
        psi_probs_ask = np.array([dist_fn(p) for p in probs_ask])
        delta_psi_ask = np.diff(np.append(psi_probs_ask, 0.0)) * -1.0
        ask_price = float(-np.sum(neg_samples * delta_psi_ask))

        linear_mid = float(np.mean(self.samples))
        spread = max(0.0, ask_price - bid_price)

        return ConicTwoPriceResult(
            bid_price=bid_price,
            ask_price=ask_price,
            mid_price=linear_mid,
            spread=spread,
            distortion_type=distortion_type,
            stress_level=distortion_param,
        )


# ==============================================================================
# 6. EIGENLAYER RE-STAKING, CORRELATED SLASHING & LRT DE-PEG ARBITRAGE
# ==============================================================================

@dataclass
class ReStakingRiskResult:
    total_yield_apr: float       # Total gross APR (ETH staking + AVS fees)
    expected_slashing_loss: float# Annual expected loss from slashing
    net_yield_apr: float         # Net APR after slashing and fees
    lrt_fair_ratio: float        # Fair theoretical LRT/ETH ratio under unbonding delay
    secondary_depeg_discount: float # Predicted DEX de-peg discount pct
    liquidation_cascade_risk: str   # Risk classification for lending protocols


class EigenLayerReStakingEngine:
    """Models cryptoeconomic security, slashing correlation, and LRT liquidity peg dynamics.
    
    References:
    - Chitra, T., & Kulkarni, K. (2024). On the Security of Liquid Restaking Tokens. arXiv preprint.
    - Buterin, V. (2023). Don't overload Ethereum's consensus. Vitalik's Blog.
    - Diederichs, E. et al. (2024). Economic Cascades in Shared Security Staking Networks.
    """

    def __init__(
        self,
        base_eth_staking_yield: float = 0.035,
        avs_yields: List[float] = None,
        avs_allocations: List[float] = None,
        avs_slash_severities: List[float] = None,
        independent_failure_prob: float = 0.01,
        systemic_correlated_prob: float = 0.005,
        protocol_fee: float = 0.10,
        unbonding_delay_days: float = 10.0,
    ):
        if avs_yields is None:
            avs_yields = [0.015, 0.020, 0.025]
        if avs_allocations is None:
            avs_allocations = [0.4, 0.35, 0.25]
        if avs_slash_severities is None:
            avs_slash_severities = [0.05, 0.10, 0.20]

        if len(avs_yields) != len(avs_allocations) or len(avs_yields) != len(avs_slash_severities):
            raise ValueError("AVS yields, allocations, and severities must have identical dimensions.")

        self.base_yield = base_eth_staking_yield
        self.avs_yields = np.array(avs_yields, dtype=np.float64)
        self.avs_allocations = np.array(avs_allocations, dtype=np.float64)
        self.avs_severities = np.array(avs_slash_severities, dtype=np.float64)
        self.ind_prob = independent_failure_prob
        self.sys_prob = systemic_correlated_prob
        self.protocol_fee = protocol_fee
        self.unbonding_days = unbonding_delay_days

    def evaluate_restaking_portfolio(
        self,
        opportunity_cost_rate: float = 0.05,
        market_liquidity_factor: float = 1.2,
    ) -> ReStakingRiskResult:
        """Calculates expected return, correlated slashing loss, and fair LRT price peg."""
        gross_avs_yield = float(np.sum(self.avs_yields * self.avs_allocations))
        total_gross_yield = self.base_yield + gross_avs_yield

        total_fail_prob = self.ind_prob + self.sys_prob
        expected_slashing = float(np.sum(self.avs_allocations * self.avs_severities * total_fail_prob))

        net_yield = self.base_yield + (1.0 - self.protocol_fee) * gross_avs_yield - expected_slashing

        t_years = self.unbonding_days / 365.0
        discount_rate = opportunity_cost_rate + expected_slashing * market_liquidity_factor
        lrt_fair_ratio = math.exp(-discount_rate * t_years)

        depeg_discount_pct = (1.0 - lrt_fair_ratio) * 100.0

        if depeg_discount_pct > 3.0:
            cascade_risk = "CRITICAL (High de-peg risk, liquidation trigger in Morpho/Aave)"
        elif depeg_discount_pct > 1.0:
            cascade_risk = "MODERATE (Spreads widening on Curve/Uniswap pools)"
        else:
            cascade_risk = "STABLE (Adequate liquidity buffer and low slashing exposure)"

        return ReStakingRiskResult(
            total_yield_apr=total_gross_yield,
            expected_slashing_loss=expected_slashing,
            net_yield_apr=net_yield,
            lrt_fair_ratio=lrt_fair_ratio,
            secondary_depeg_discount=depeg_discount_pct,
            liquidation_cascade_risk=cascade_risk,
        )
