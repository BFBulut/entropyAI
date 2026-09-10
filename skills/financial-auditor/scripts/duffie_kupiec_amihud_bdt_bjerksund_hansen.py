"""Phase 27: Quantitative Financial Engineering & Institutional Risk Architecture.

Core Pillars:
1. Duffie & Singleton (1999) Reduced-Form Credit Risk & ISDA CDS Hazard Rate Bootstrap
2. Kupiec (1995) POF & Christoffersen (1998) Independence Test for Regulatory VaR Backtesting
3. Amihud (2002) Illiquidity Ratio (ILLIQ) & Pastor-Stambaugh (2003) Liquidity Risk Factor
4. Black-Derman-Toy (1990) Short-Rate Lattice & Callable Bond Backward Induction
5. Bjerksund-Stensland (1993/2002) Analytical American Option Model & Optimal Exercise Boundary
6. Hansen-Jagannathan (1991) Stochastic Discount Factor (SDF) Volatility Bounds & CCAPM Diagnostic
"""

import argparse
from dataclasses import dataclass, field
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# 0. NUMERICAL HELPER FUNCTIONS
# ==============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function using error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def _chi2_sf_1df(x: float) -> float:
    """Survival function (1 - CDF) for Chi-Square distribution with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))

def _chi2_sf_2df(x: float) -> float:
    """Survival function (1 - CDF) for Chi-Square distribution with 2 degrees of freedom."""
    if x <= 0:
        return 1.0
    return math.exp(-x / 2.0)


# ==============================================================================
# 1. DUFFIE & SINGLETON (1999) REDUCED-FORM CREDIT RISK & CDS BOOTSTRAP
# ==============================================================================

@dataclass
class CDSBootstrapResult:
    maturities: List[float]
    market_spreads_bps: List[float]
    hazard_rates: List[float]
    survival_probabilities: List[float]
    recovery_rate: float
    discount_factors: List[float]

@dataclass
class CDSValuationResult:
    maturity: float
    contract_spread_bps: float
    par_spread_bps: float
    pv_premium_leg: float
    pv_protection_leg: float
    net_present_value: float
    upfront_fee_pct: float
    upfront_amount: float


class DuffieSingletonCDSEngine:
    """Reduced-form credit risk modeling and piecewise-constant CDS hazard rate bootstrapping.
    
    References:
    - Duffie, D., & Singleton, K. J. (1999). Modeling term structures of defaultable bonds.
    - O'Kane, D., & Turnbull, S. (2003). Explaining the CDS basis. Lehman Brothers.
    """

    @staticmethod
    def bootstrap_hazard_rates(
        maturities: List[float],
        spreads_bps: List[float],
        recovery_rate: float = 0.40,
        risk_free_rate: float = 0.03,
        payment_freq: int = 4  # Quarterly payments (standard ISDA)
    ) -> CDSBootstrapResult:
        """Bootstraps piecewise constant hazard rates lambda_i from market CDS spreads."""
        if len(maturities) != len(spreads_bps):
            raise ValueError("Maturities and spreads must have the same length.")
        if len(maturities) == 0:
            raise ValueError("At least one maturity is required.")
        if not (0.0 <= recovery_rate < 1.0):
            raise ValueError("Recovery rate must be in [0, 1).")

        n = len(maturities)
        spreads = [s / 10000.0 for s in spreads_bps]  # convert bps to decimal
        dt = 1.0 / payment_freq
        lgd = 1.0 - recovery_rate

        hazard_rates: List[float] = []
        survival_probs: List[float] = [1.0]  # Q(0) = 1.0
        discount_factors: List[float] = [math.exp(-risk_free_rate * t) for t in maturities]

        # Iterative bootstrap per maturity bucket
        prev_mat = 0.0
        for i in range(n):
            target_t = maturities[i]
            target_spread = spreads[i]

            # Solve for lambda_i such that PV(Premium) = PV(Protection)
            # Using 1D bisection root finding for lambda_i
            low_lambda = 0.00001
            high_lambda = 2.0

            def objective(candidate_lambda: float) -> float:
                current_hazard_rates = hazard_rates + [candidate_lambda]
                current_maturities = maturities[:i+1]

                total_steps = int(round(target_t * payment_freq))
                pv_prem = 0.0
                pv_prot = 0.0

                q_prev = 1.0
                for step in range(1, total_steps + 1):
                    t = step * dt
                    # Determine survival prob Q(t)
                    q_t = 1.0
                    bucket_prev_t = 0.0
                    for b_idx, b_mat in enumerate(current_maturities):
                        h = current_hazard_rates[b_idx]
                        if t <= b_mat:
                            q_t *= math.exp(-h * (t - bucket_prev_t))
                            break
                        else:
                            q_t *= math.exp(-h * (b_mat - bucket_prev_t))
                            bucket_prev_t = b_mat

                    df = math.exp(-risk_free_rate * t)
                    df_mid = math.exp(-risk_free_rate * (t - 0.5 * dt))

                    prob_survival = q_t
                    prob_default = max(0.0, q_prev - q_t)
                    pv_prem += target_spread * (dt * df * prob_survival + 0.5 * dt * df_mid * prob_default)
                    pv_prot += lgd * df_mid * prob_default
                    q_prev = q_t

                return pv_prot - pv_prem

            for _ in range(60):
                mid_lambda = 0.5 * (low_lambda + high_lambda)
                val = objective(mid_lambda)
                if abs(val) < 1e-9:
                    break
                if val > 0:
                    high_lambda = mid_lambda
                else:
                    low_lambda = mid_lambda

            solved_lambda = 0.5 * (low_lambda + high_lambda)
            hazard_rates.append(solved_lambda)
            cum_survival = survival_probs[-1] * math.exp(-solved_lambda * (target_t - prev_mat))
            survival_probs.append(cum_survival)
            prev_mat = target_t

        return CDSBootstrapResult(
            maturities=maturities,
            market_spreads_bps=spreads_bps,
            hazard_rates=hazard_rates,
            survival_probabilities=survival_probs[1:],
            recovery_rate=recovery_rate,
            discount_factors=discount_factors
        )

    @staticmethod
    def price_cds(
        contract_spread_bps: float,
        maturity: float,
        bootstrap_result: CDSBootstrapResult,
        risk_free_rate: float = 0.03,
        notional: float = 10_000_000.0,
        payment_freq: int = 4
    ) -> CDSValuationResult:
        """Prices an active CDS contract, returning par spread, PV of legs, and upfront."""
        c_spread = contract_spread_bps / 10000.0
        dt = 1.0 / payment_freq
        lgd = 1.0 - bootstrap_result.recovery_rate
        total_steps = int(round(maturity * payment_freq))

        pv_premium_unit = 0.0  # PV of 1 bps premium
        pv_protection = 0.0

        q_prev = 1.0
        for step in range(1, total_steps + 1):
            t = step * dt
            # Calculate Q(t)
            q_t = 1.0
            bucket_prev_t = 0.0
            for b_idx, b_mat in enumerate(bootstrap_result.maturities):
                h = bootstrap_result.hazard_rates[b_idx]
                if t <= b_mat:
                    q_t *= math.exp(-h * (t - bucket_prev_t))
                    break
                else:
                    q_t *= math.exp(-h * (b_mat - bucket_prev_t))
                    bucket_prev_t = b_mat

            df = math.exp(-risk_free_rate * t)
            df_mid = math.exp(-risk_free_rate * (t - 0.5 * dt))
            prob_survival = q_t
            prob_default = max(0.0, q_prev - q_t)

            pv_premium_unit += (dt * df * prob_survival + 0.5 * dt * df_mid * prob_default)
            pv_protection += lgd * df_mid * prob_default
            q_prev = q_t

        par_spread = (pv_protection / pv_premium_unit) if pv_premium_unit > 0 else 0.0
        par_spread_bps = par_spread * 10000.0

        pv_premium_contract = c_spread * pv_premium_unit * notional
        pv_prot_total = pv_protection * notional
        npv = pv_prot_total - pv_premium_contract
        upfront_fee_pct = (npv / notional) * 100.0

        return CDSValuationResult(
            maturity=maturity,
            contract_spread_bps=contract_spread_bps,
            par_spread_bps=round(par_spread_bps, 2),
            pv_premium_leg=round(pv_premium_contract, 2),
            pv_protection_leg=round(pv_prot_total, 2),
            net_present_value=round(npv, 2),
            upfront_fee_pct=round(upfront_fee_pct, 4),
            upfront_amount=round(npv, 2)
        )


# ==============================================================================
# 2. KUPIEC (1995) POF & CHRISTOFFERSEN (1998) REGULATORY VAR BACKTESTING
# ==============================================================================

@dataclass
class KupiecPOFResult:
    total_observations: int
    violations: int
    expected_violations: float
    observed_failure_rate: float
    expected_failure_rate: float
    lr_statistic: float
    p_value: float
    h0_accepted_5pct: bool
    status: str

@dataclass
class ChristoffersenResult:
    n00: int
    n01: int
    n10: int
    n11: int
    pi01: float
    pi11: float
    pi_pooled: float
    lr_ind_statistic: float
    lr_ind_p_value: float
    independence_accepted_5pct: bool
    lr_cc_statistic: float
    lr_cc_p_value: float
    conditional_coverage_accepted_5pct: bool
    clustering_detected: bool

@dataclass
class BaselTrafficLightResult:
    total_observations: int
    violations: int
    zone: str               # "Green", "Yellow", "Red"
    multiplier_penalty: float
    capital_multiplier: float
    regulatory_action: str


class VaRBacktestingEngine:
    """Regulatory backtesting framework for Value-at-Risk models.
    
    References:
    - Kupiec, P. H. (1995). Techniques for verifying the accuracy of risk measurement models.
    - Christoffersen, P. F. (1998). Evaluating interval forecasts.
    - Basel Committee on Banking Supervision (1996/2019). Supervisory framework for VaR backtesting.
    """

    @staticmethod
    def kupiec_pof_test(
        violations: int,
        total_observations: int,
        var_confidence: float = 0.99
    ) -> KupiecPOFResult:
        """Kupiec Proportion of Failures (POF) unconditional coverage test."""
        if total_observations <= 0:
            raise ValueError("Total observations must be positive.")
        if violations < 0 or violations > total_observations:
            raise ValueError("Violations must be between 0 and total observations.")

        p0 = 1.0 - var_confidence
        expected_v = total_observations * p0
        p_hat = violations / total_observations

        if violations == 0:
            lr = -2.0 * ((total_observations) * math.log(1.0 - p0))
        elif violations == total_observations:
            lr = -2.0 * (total_observations * math.log(p0))
        else:
            log_l0 = (total_observations - violations) * math.log(1.0 - p0) + violations * math.log(p0)
            log_l1 = (total_observations - violations) * math.log(1.0 - p_hat) + violations * math.log(p_hat)
            lr = -2.0 * (log_l0 - log_l1)

        lr = max(0.0, lr)
        p_val = _chi2_sf_1df(lr)
        accepted = (p_val >= 0.05)

        if accepted:
            status = "Model Kabul Edildi (İhlal sıklığı teorik beklentiyle istatistiksel olarak uyumlu)"
        elif p_hat > p0:
            status = "Model Reddedildi (Risk hafife alınmış, aşırı ihlal var)"
        else:
            status = "Model Reddedildi (Risk abartılmış, aşırı temkinli model)"

        return KupiecPOFResult(
            total_observations=total_observations,
            violations=violations,
            expected_violations=round(expected_v, 2),
            observed_failure_rate=round(p_hat, 4),
            expected_failure_rate=round(p0, 4),
            lr_statistic=round(lr, 4),
            p_value=round(p_val, 4),
            h0_accepted_5pct=accepted,
            status=status
        )

    @staticmethod
    def christoffersen_test(
        hit_sequence: List[int],
        var_confidence: float = 0.99
    ) -> Tuple[KupiecPOFResult, ChristoffersenResult]:
        """Christoffersen conditional coverage & independence test using Markov chain transitions."""
        n = len(hit_sequence)
        if n < 2:
            raise ValueError("Hit sequence must have at least 2 observations.")

        violations = sum(hit_sequence)
        kupiec = VaRBacktestingEngine.kupiec_pof_test(violations, n, var_confidence)

        n00, n01, n10, n11 = 0, 0, 0, 0
        for t in range(1, n):
            prev = hit_sequence[t - 1]
            curr = hit_sequence[t]
            if prev == 0 and curr == 0:
                n00 += 1
            elif prev == 0 and curr == 1:
                n01 += 1
            elif prev == 1 and curr == 0:
                n10 += 1
            elif prev == 1 and curr == 1:
                n11 += 1

        pi01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
        pi11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
        pi_pooled = (n01 + n11) / (n00 + n01 + n10 + n11) if (n00 + n01 + n10 + n11) > 0 else 0.0

        def log_term(count: int, prob: float) -> float:
            if count == 0:
                return 0.0
            prob = max(1e-12, min(1.0 - 1e-12, prob))
            return count * math.log(prob)

        log_l_null = (
            log_term(n00 + n10, 1.0 - pi_pooled) +
            log_term(n01 + n11, pi_pooled)
        )
        log_l_alt = (
            log_term(n00, 1.0 - pi01) +
            log_term(n01, pi01) +
            log_term(n10, 1.0 - pi11) +
            log_term(n11, pi11)
        )

        lr_ind = max(0.0, -2.0 * (log_l_null - log_l_alt))
        p_val_ind = _chi2_sf_1df(lr_ind)
        ind_accepted = (p_val_ind >= 0.05)

        lr_cc = kupiec.lr_statistic + lr_ind
        p_val_cc = _chi2_sf_2df(lr_cc)
        cc_accepted = (p_val_cc >= 0.05)

        clustering = (pi11 > pi01) and not ind_accepted

        res = ChristoffersenResult(
            n00=n00,
            n01=n01,
            n10=n10,
            n11=n11,
            pi01=round(pi01, 4),
            pi11=round(pi11, 4),
            pi_pooled=round(pi_pooled, 4),
            lr_ind_statistic=round(lr_ind, 4),
            lr_ind_p_value=round(p_val_ind, 4),
            independence_accepted_5pct=ind_accepted,
            lr_cc_statistic=round(lr_cc, 4),
            lr_cc_p_value=round(p_val_cc, 4),
            conditional_coverage_accepted_5pct=cc_accepted,
            clustering_detected=clustering
        )
        return kupiec, res

    @staticmethod
    def basel_traffic_light(
        violations: int,
        total_observations: int = 250
    ) -> BaselTrafficLightResult:
        """Determines Basel II/III/IV Traffic Light zone and regulatory capital multiplier penalty."""
        base_multiplier = 3.0
        penalty_table = {
            0: 0.00, 1: 0.00, 2: 0.00, 3: 0.00, 4: 0.00,
            5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85
        }

        if violations <= 4:
            zone = "Yeşil Bölge (Green Zone)"
            penalty = 0.00
            action = "Model regülasyon tarafından tam geçerli kabul edilir; ek sermaye yükümlülüğü yoktur."
        elif 5 <= violations <= 9:
            zone = "Sarı Bölge (Yellow Zone)"
            penalty = penalty_table.get(violations, 0.85)
            action = "Model denetime tabi tutulur; banka ilave ihtiyati sermaye cezası tahsis etmek zorundadır."
        else:
            zone = "Kırmızı Bölge (Red Zone)"
            penalty = 1.00
            action = "Model kesin olarak reddedilmiştir; içsel model izni askıya alınır, standart kural uygulanır."

        return BaselTrafficLightResult(
            total_observations=total_observations,
            violations=violations,
            zone=zone,
            multiplier_penalty=penalty,
            capital_multiplier=round(base_multiplier + penalty, 2),
            regulatory_action=action
        )


# ==============================================================================
# 3. AMIHUD (2002) ILLIQUIDITY RATIO & PASTOR-STAMBAUGH (2003) LIQUIDITY FACTOR
# ==============================================================================

@dataclass
class AmihudResult:
    sample_size: int
    mean_illiq: float
    median_illiq: float
    illiq_annualized: float
    liquidity_tier: str
    interpretation: str

@dataclass
class PastorStambaughResult:
    sample_size: int
    gamma_coefficient: float
    t_statistic: float
    p_value: float
    liquidity_beta: float
    return_reversal_confirmed: bool
    summary: str


class LiquidityDynamicsEngine:
    """Amihud price impact illiquidity and Pastor-Stambaugh return reversal / liquidity factor.
    
    References:
    - Amihud, Y. (2002). Illiquidity and stock returns: cross-section and time-series effects.
    - Pastor, L., & Stambaugh, R. F. (2003). Liquidity risk and expected stock returns.
    """

    @staticmethod
    def calculate_amihud_illiquidity(
        daily_returns: List[float],
        dollar_volumes: List[float]
    ) -> AmihudResult:
        """Calculates Amihud (2002) daily illiquidity ratio: |R_t| / (Volume_t * Price_t) * 1e6."""
        if len(daily_returns) != len(dollar_volumes):
            raise ValueError("Returns and dollar volumes must match in length.")
        if len(daily_returns) == 0:
            raise ValueError("Data series cannot be empty.")

        illiq_series = []
        for r, dv in zip(daily_returns, dollar_volumes):
            if dv > 0:
                illiq = (abs(r) / dv) * 1_000_000.0
                illiq_series.append(illiq)

        if not illiq_series:
            raise ValueError("All dollar volumes were zero or non-positive.")

        arr = np.array(illiq_series)
        mean_illiq = float(np.mean(arr))
        median_illiq = float(np.median(arr))
        ann_illiq = mean_illiq * math.sqrt(252)

        if mean_illiq < 0.05:
            tier = "Ultra Yüksek Likidite (Mega-Cap Hisse / Ana FX)"
            desc = "1 Milyon Dolarlık işlem piyasa fiyatını neredeyse hiç kaydırmaz (<0.05 bps)."
        elif mean_illiq < 0.50:
            tier = "Yüksek / Dengeli Likidite (Large-Cap)"
            desc = "1 Milyon Dolarlık blok işlem 0.05 - 0.50 bps marjinal fiyat etkisi yaratır."
        elif mean_illiq < 2.00:
            tier = "Orta Likidite (Mid-Cap)"
            desc = "Kurumsal emirler belirgin fiyat kayması (slippage) riski taşır."
        else:
            tier = "Kritik Düşük Likidite (Small-Cap / Sığ Varlık)"
            desc = "Yüksek işlem maliyeti; blok emirler piyasayı derinden sarsar (>2.0 bps etki)."

        return AmihudResult(
            sample_size=len(illiq_series),
            mean_illiq=round(mean_illiq, 6),
            median_illiq=round(median_illiq, 6),
            illiq_annualized=round(ann_illiq, 6),
            liquidity_tier=tier,
            interpretation=desc
        )

    @staticmethod
    def calculate_pastor_stambaugh_reversal(
        stock_returns: List[float],
        dollar_volumes: List[float],
        market_returns: Optional[List[float]] = None
    ) -> PastorStambaughResult:
        """Estimates Pastor-Stambaugh (2003) individual stock reversal parameter gamma_i."""
        n = len(stock_returns)
        if n < 4:
            raise ValueError("At least 4 observations needed for regression.")
        if len(dollar_volumes) != n:
            raise ValueError("Returns and dollar volumes must match in length.")

        m_rets = market_returns if market_returns and len(market_returns) == n else [0.0] * n

        y = []
        x_ret = []
        x_flow = []

        avg_vol = np.mean(dollar_volumes) if np.mean(dollar_volumes) > 0 else 1.0

        for t in range(n - 1):
            excess_t = stock_returns[t] - m_rets[t]
            sign_t = 1.0 if excess_t > 0 else (-1.0 if excess_t < 0 else 0.0)
            flow_t = sign_t * (dollar_volumes[t] / avg_vol)

            y.append(stock_returns[t + 1])
            x_ret.append(stock_returns[t])
            x_flow.append(flow_t)

        y_arr = np.array(y)
        X = np.column_stack([np.ones(len(y)), np.array(x_ret), np.array(x_flow)])

        try:
            beta = np.linalg.inv(X.T @ X) @ (X.T @ y_arr)
            residuals = y_arr - X @ beta
            dof = len(y) - X.shape[1]
            sigma2 = np.sum(residuals**2) / max(1, dof)
            cov_beta = np.linalg.inv(X.T @ X) * sigma2
            se_gamma = math.sqrt(max(1e-12, cov_beta[2, 2]))
            gamma = float(beta[2])
            t_stat = gamma / se_gamma
            p_val = 2.0 * (1.0 - _norm_cdf(abs(t_stat)))
        except np.linalg.LinAlgError:
            gamma, t_stat, p_val = 0.0, 0.0, 1.0

        confirmed = (gamma < 0 and p_val < 0.10)
        summary = (
            f"Gamma = {gamma:.6f} (t={t_stat:.2f}, p={p_val:.4f}). "
            f"{'İşlem kaynaklı fiyat aşımı ve ertesi gün geri çekilme (reversal) doğrulandı.' if confirmed else 'İstatistiki olarak anlamlı negatif geri çekilme tespit edilemedi.'}"
        )

        return PastorStambaughResult(
            sample_size=len(y),
            gamma_coefficient=round(gamma, 6),
            t_statistic=round(t_stat, 4),
            p_value=round(p_val, 4),
            liquidity_beta=round(-gamma * 10.0, 4),
            return_reversal_confirmed=confirmed,
            summary=summary
        )


# ==============================================================================
# 4. BLACK-DERMAN-TOY (1990) SHORT-RATE LATTICE & CALLABLE BOND
# ==============================================================================

@dataclass
class BDTLatticeResult:
    dt: float
    time_steps: int
    rates_tree: List[List[float]]
    state_prices: List[List[float]]
    model_zero_prices: List[float]
    market_zero_prices: List[float]

@dataclass
class CallableBondValuationResult:
    straight_bond_price: float
    callable_bond_price: float
    embedded_call_option_value: float
    optimal_call_triggered: bool
    first_call_time_step: Optional[int]
    yield_to_maturity_pct: float
    yield_to_call_pct: float


class BlackDermanToyLatticeEngine:
    """Black-Derman-Toy (1990) lognormal short-rate binomial lattice with callable bond pricing.
    
    References:
    - Black, F., Derman, E., & Toy, W. (1990). A one-factor model of interest rates and its application to Treasury bond options.
    - Jamshidian, F. (1991). The Black-Derman-Toy model: A simple approach.
    """

    @staticmethod
    def calibrate_bdt_lattice(
        maturities: List[float],
        zero_bond_prices: List[float],
        volatilities: List[float],
        dt: float = 1.0
    ) -> BDTLatticeResult:
        """Calibrates a lognormal short-rate tree r_{i,j} = r_{i,0} * u_i^j to the zero curve."""
        if len(maturities) != len(zero_bond_prices) or len(maturities) != len(volatilities):
            raise ValueError("Maturities, zero prices, and volatilities must have equal length.")
        if len(maturities) == 0:
            raise ValueError("Zero curve points required.")

        n_steps = len(maturities)
        rates_tree: List[List[float]] = []
        state_prices: List[List[float]] = []
        model_zeros: List[float] = []

        # Step 0: Initial short rate
        p1 = zero_bond_prices[0]
        r0 = (1.0 / p1 - 1.0) / dt
        rates_tree.append([r0])
        state_prices.append([1.0])
        model_zeros.append(p1)

        for i in range(1, n_steps):
            sigma_i = volatilities[i]
            u_i = math.exp(2.0 * sigma_i * math.sqrt(dt))
            target_p = zero_bond_prices[i]

            prev_p = state_prices[i - 1]
            prev_r = rates_tree[i - 1]

            q_current = [0.0] * (i + 1)
            for j in range(i + 1):
                term_down = 0.5 * prev_p[j] / (1.0 + prev_r[j] * dt) if j < i else 0.0
                term_up = 0.5 * prev_p[j - 1] / (1.0 + prev_r[j - 1] * dt) if j > 0 else 0.0
                q_current[j] = term_down + term_up

            state_prices.append(q_current)

            low_r = 0.00001
            high_r = 1.0

            def price_objective(r_base: float) -> float:
                val = 0.0
                for j in range(i + 1):
                    r_ij = r_base * (u_i ** j)
                    val += q_current[j] / (1.0 + r_ij * dt)
                return val - target_p

            for _ in range(60):
                mid_r = 0.5 * (low_r + high_r)
                diff = price_objective(mid_r)
                if abs(diff) < 1e-10:
                    break
                if diff > 0:
                    low_r = mid_r
                else:
                    high_r = mid_r

            solved_r0 = 0.5 * (low_r + high_r)
            step_rates = [solved_r0 * (u_i ** j) for j in range(i + 1)]
            rates_tree.append(step_rates)

            m_zero = sum(q_current[j] / (1.0 + step_rates[j] * dt) for j in range(i + 1))
            model_zeros.append(m_zero)

        return BDTLatticeResult(
            dt=dt,
            time_steps=n_steps,
            rates_tree=rates_tree,
            state_prices=state_prices,
            model_zero_prices=[round(x, 6) for x in model_zeros],
            market_zero_prices=zero_bond_prices
        )

    @staticmethod
    def price_callable_bond(
        lattice: BDTLatticeResult,
        face_value: float = 100.0,
        coupon_rate: float = 0.05,
        call_schedule: Optional[Dict[int, float]] = None,
        dt: float = 1.0
    ) -> CallableBondValuationResult:
        """Backward induction valuation of straight and callable bonds on the calibrated BDT lattice."""
        n = lattice.time_steps
        coupon = face_value * coupon_rate * dt
        calls = call_schedule or {}

        v_straight = [face_value + coupon] * n
        v_callable = [face_value + coupon] * n

        call_triggered = False
        first_call_step = None

        for step in range(n - 2, -1, -1):
            r_step = lattice.rates_tree[step]
            m = len(r_step)
            new_straight = [0.0] * m
            new_callable = [0.0] * m

            call_price = calls.get(step, float("inf"))

            for j in range(m):
                r_ij = r_step[j]
                discount = 1.0 / (1.0 + r_ij * dt)

                exp_straight = 0.5 * (v_straight[j + 1] + v_straight[j])
                val_straight = discount * exp_straight + coupon
                new_straight[j] = val_straight

                exp_callable = 0.5 * (v_callable[j + 1] + v_callable[j])
                cont_val = discount * exp_callable + coupon

                if cont_val > call_price:
                    new_callable[j] = call_price
                    call_triggered = True
                    if first_call_step is None or step < first_call_step:
                        first_call_step = step
                else:
                    new_callable[j] = cont_val

            v_straight = new_straight
            v_callable = new_callable

        p_straight = v_straight[0]
        p_callable = v_callable[0]
        call_option_val = max(0.0, p_straight - p_callable)

        ytm = (coupon / p_straight) * 100.0 if p_straight > 0 else 0.0
        ytc = (coupon / p_callable) * 100.0 if p_callable > 0 else 0.0

        return CallableBondValuationResult(
            straight_bond_price=round(p_straight, 4),
            callable_bond_price=round(p_callable, 4),
            embedded_call_option_value=round(call_option_val, 4),
            optimal_call_triggered=call_triggered,
            first_call_time_step=first_call_step,
            yield_to_maturity_pct=round(ytm, 2),
            yield_to_call_pct=round(ytc, 2)
        )


# ==============================================================================
# 5. BJERKSUND-STENSLAND (1993/2002) ANALYTICAL AMERICAN OPTION MODEL
# ==============================================================================

@dataclass
class BjerksundStenslandResult:
    spot: float
    strike: float
    maturity: float
    option_type: str
    american_price: float
    european_price: float
    early_exercise_premium: float
    trigger_boundary: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class BjerksundStenslandEngine:
    """Bjerksund-Stensland (1993/2002) closed-form analytical American option approximation.
    
    References:
    - Bjerksund, P., & Stensland, G. (1993). Closed-form approximation of American options.
    - Bjerksund, P., & Stensland, G. (2002). Closed-form valuation of American options on stocks with dividends.
    """

    @staticmethod
    def _phi(s: float, t: float, gamma: float, h: float, i: float, r: float, b: float, sigma: float) -> float:
        """Bjerksund-Stensland auxiliary expectation integral function."""
        sigma_sq = sigma * sigma
        lambda_val = -r + gamma * b + 0.5 * gamma * (gamma - 1.0) * sigma_sq
        d = -(math.log(s / h) + (b + (gamma - 0.5) * sigma_sq) * t) / (sigma * math.sqrt(t))
        kappa = (2.0 * b / sigma_sq) + (2.0 * gamma - 1.0)
        term1 = math.exp(lambda_val * t) * (s ** gamma)
        term2 = _norm_cdf(d) - ((i / s) ** kappa) * _norm_cdf(d - 2.0 * math.log(i / s) / (sigma * math.sqrt(t)))
        return term1 * term2

    @staticmethod
    def american_call(
        spot: float,
        strike: float,
        maturity: float,
        rate: float = 0.05,
        dividend_yield: float = 0.02,
        volatility: float = 0.25
    ) -> float:
        """Computes analytical American Call option price."""
        if maturity <= 0:
            return max(0.0, spot - strike)
        if spot <= 0 or strike <= 0 or volatility <= 0:
            return 0.0

        b = rate - dividend_yield
        sigma = volatility
        sigma_sq = sigma * sigma

        if b >= rate:
            d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * sigma_sq) * maturity) / (sigma * math.sqrt(maturity))
            d2 = d1 - sigma * math.sqrt(maturity)
            return spot * math.exp(-dividend_yield * maturity) * _norm_cdf(d1) - strike * math.exp(-rate * maturity) * _norm_cdf(d2)

        beta = (0.5 - b / sigma_sq) + math.sqrt((b / sigma_sq - 0.5) ** 2 + 2.0 * rate / sigma_sq)
        b_inf = (beta / (beta - 1.0)) * strike
        b_0 = max(strike, (rate / (rate - b)) * strike)
        h_t = -(b * maturity + 2.0 * sigma * math.sqrt(maturity)) * (b_0 / (b_inf - b_0))
        i_t = b_0 + (b_inf - b_0) * (1.0 - math.exp(h_t))

        if spot >= i_t:
            return spot - strike

        alpha = (i_t - strike) * (i_t ** (-beta))
        phi = BjerksundStenslandEngine._phi

        price = (
            alpha * (spot ** beta) -
            alpha * phi(spot, maturity, beta, i_t, i_t, rate, b, sigma) +
            phi(spot, maturity, 1.0, i_t, i_t, rate, b, sigma) -
            phi(spot, maturity, 1.0, strike, i_t, rate, b, sigma) -
            strike * phi(spot, maturity, 0.0, i_t, i_t, rate, b, sigma) +
            strike * phi(spot, maturity, 0.0, strike, i_t, rate, b, sigma)
        )
        return max(0.0, price)

    @staticmethod
    def american_put(
        spot: float,
        strike: float,
        maturity: float,
        rate: float = 0.05,
        dividend_yield: float = 0.02,
        volatility: float = 0.25
    ) -> float:
        """Computes analytical American Put option price via Put-Call Symmetry transformation."""
        return BjerksundStenslandEngine.american_call(
            spot=strike,
            strike=spot,
            maturity=maturity,
            rate=dividend_yield,
            dividend_yield=rate,
            volatility=volatility
        )

    @staticmethod
    def evaluate_option_with_greeks(
        spot: float,
        strike: float,
        maturity: float,
        rate: float = 0.05,
        dividend_yield: float = 0.02,
        volatility: float = 0.25,
        option_type: str = "call"
    ) -> BjerksundStenslandResult:
        """Calculates American option price, early exercise premium, and Greeks (Delta, Gamma, Vega, Theta, Rho)."""
        is_call = (option_type.lower() == "call")
        pricing_fn = BjerksundStenslandEngine.american_call if is_call else BjerksundStenslandEngine.american_put

        price = pricing_fn(spot, strike, maturity, rate, dividend_yield, volatility)

        d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility**2) * maturity) / (volatility * math.sqrt(maturity))
        d2 = d1 - volatility * math.sqrt(maturity)
        if is_call:
            euro_price = spot * math.exp(-dividend_yield * maturity) * _norm_cdf(d1) - strike * math.exp(-rate * maturity) * _norm_cdf(d2)
        else:
            euro_price = strike * math.exp(-rate * maturity) * _norm_cdf(-d2) - spot * math.exp(-dividend_yield * maturity) * _norm_cdf(-d1)

        premium = max(0.0, price - euro_price)

        ds = 0.01 * spot
        p_up = pricing_fn(spot + ds, strike, maturity, rate, dividend_yield, volatility)
        p_dn = pricing_fn(spot - ds, strike, maturity, rate, dividend_yield, volatility)
        delta = (p_up - p_dn) / (2.0 * ds)
        gamma = (p_up - 2.0 * price + p_dn) / (ds * ds)

        dvol = 0.01
        p_v_up = pricing_fn(spot, strike, maturity, rate, dividend_yield, volatility + dvol)
        p_v_dn = pricing_fn(spot, strike, maturity, rate, dividend_yield, max(0.01, volatility - dvol))
        vega = (p_v_up - p_v_dn) / (2.0 * dvol * 100.0)

        dt = 1.0 / 365.0
        if maturity > dt:
            p_t_dn = pricing_fn(spot, strike, maturity - dt, rate, dividend_yield, volatility)
            theta = (p_t_dn - price)
        else:
            theta = 0.0

        dr = 0.001
        p_r_up = pricing_fn(spot, strike, maturity, rate + dr, dividend_yield, volatility)
        p_r_dn = pricing_fn(spot, strike, maturity, max(0.0, rate - dr), dividend_yield, volatility)
        rho = (p_r_up - p_r_dn) / (2.0 * dr * 100.0)

        sigma_sq = volatility * volatility
        b = rate - dividend_yield
        beta = (0.5 - b / sigma_sq) + math.sqrt((b / sigma_sq - 0.5) ** 2 + 2.0 * rate / sigma_sq)
        b_inf = (beta / (beta - 1.0)) * strike
        b_0 = max(strike, (rate / (rate - b)) * strike) if (rate - b) != 0 else strike
        h_t = -(b * maturity + 2.0 * volatility * math.sqrt(maturity)) * (b_0 / max(0.01, b_inf - b_0))
        trigger = b_0 + (b_inf - b_0) * (1.0 - math.exp(h_t))

        return BjerksundStenslandResult(
            spot=spot,
            strike=strike,
            maturity=maturity,
            option_type="American Call" if is_call else "American Put",
            american_price=round(price, 4),
            european_price=round(euro_price, 4),
            early_exercise_premium=round(premium, 4),
            trigger_boundary=round(trigger, 2),
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            vega=round(vega, 4),
            theta=round(theta, 4),
            rho=round(rho, 4)
        )


# ==============================================================================
# 6. HANSEN-JAGANNATHAN (1991) SDF VOLATILITY BOUNDS & CCAPM DIAGNOSTIC
# ==============================================================================

@dataclass
class HansenJagannathanResult:
    mean_excess_returns: List[float]
    covariance_matrix: List[List[float]]
    max_sharpe_ratio: float
    min_sdf_volatility_bound: float
    risk_free_rate: float
    optimal_tangency_weights: List[float]
    admissible_region_slope: float

@dataclass
class CCAPMDiagnosticResult:
    risk_aversion: float
    time_discount_beta: float
    consumption_growth_mean: float
    consumption_growth_std: float
    theoretical_sdf_mean: float
    theoretical_sdf_std: float
    theoretical_sdf_vol_ratio: float
    required_hj_bound: float
    equity_premium_puzzle_confirmed: bool
    verdict: str


class HansenJagannathanEngine:
    """Hansen-Jagannathan (1991) model-free Stochastic Discount Factor (SDF) volatility bounds.
    
    References:
    - Hansen, L. P., & Jagannathan, R. (1991). Implications of security market data for models of dynamic economies.
    - Mehra, R., & Prescott, E. C. (1985). The equity premium: A puzzle.
    """

    @staticmethod
    def compute_hj_volatility_bound(
        excess_returns: List[float],
        covariance_matrix: List[List[float]],
        risk_free_rate: float = 0.03
    ) -> HansenJagannathanResult:
        """Calculates the dual Hansen-Jagannathan bound sigma(m)/E[m] >= sqrt(mu^T Sigma^{-1} mu)."""
        mu = np.array(excess_returns)
        sigma = np.array(covariance_matrix)

        if len(mu) != sigma.shape[0] or sigma.shape[0] != sigma.shape[1]:
            raise ValueError("Dimension mismatch between excess returns and covariance matrix.")

        try:
            sigma_inv = np.linalg.inv(sigma)
        except np.linalg.LinAlgError:
            sigma_inv = np.linalg.pinv(sigma + 1e-6 * np.eye(len(mu)))

        quad = float(mu.T @ sigma_inv @ mu)
        max_sharpe = math.sqrt(max(0.0, quad))

        w_raw = sigma_inv @ mu
        w_sum = np.sum(w_raw)
        tangency_weights = (w_raw / w_sum).tolist() if abs(w_sum) > 1e-12 else [1.0 / len(mu)] * len(mu)

        e_m = 1.0 / (1.0 + risk_free_rate)
        min_sdf_std = e_m * max_sharpe

        return HansenJagannathanResult(
            mean_excess_returns=[round(x, 4) for x in excess_returns],
            covariance_matrix=[[round(c, 6) for c in row] for row in covariance_matrix],
            max_sharpe_ratio=round(max_sharpe, 4),
            min_sdf_volatility_bound=round(min_sdf_std, 4),
            risk_free_rate=risk_free_rate,
            optimal_tangency_weights=[round(w, 4) for w in tangency_weights],
            admissible_region_slope=round(max_sharpe, 4)
        )

    @staticmethod
    def evaluate_ccapm_pricing_kernel(
        consumption_growth_mean: float = 0.018,
        consumption_growth_std: float = 0.015,
        risk_aversion_gamma: float = 2.0,
        time_discount_beta: float = 0.98,
        hj_bound: float = 0.40
    ) -> CCAPMDiagnosticResult:
        """Diagnoses Mehra-Prescott Equity Premium Puzzle via the Hansen-Jagannathan Volatility Bound."""
        mu_c = consumption_growth_mean
        sigma_c = consumption_growth_std
        gamma = risk_aversion_gamma
        beta = time_discount_beta

        e_m = beta * math.exp(-gamma * mu_c + 0.5 * (gamma ** 2) * (sigma_c ** 2))
        vol_ratio = math.sqrt(max(0.0, math.exp((gamma ** 2) * (sigma_c ** 2)) - 1.0))
        std_m = e_m * vol_ratio

        puzzle = (vol_ratio < hj_bound)
        if puzzle:
            verdict = (
                f"Aşırı Düşük Volatilite (İhlal): CCAPM kernels (gamma={gamma}) oranı {vol_ratio:.4f}, "
                f"gerekli HJ eşiği {hj_bound:.4f}'ün çok altındadır. Hisse senedi getiri primini açıklamak için "
                f"gamma > {round(hj_bound / max(1e-6, sigma_c), 1)} olmalıdır (Equity Premium Puzzle kanıtlandı)."
            )
        else:
            verdict = (
                f"Uyumlu Model: Fiyatlama çekirdeği volatilitesi ({vol_ratio:.4f}), "
                f"Hansen-Jagannathan sınırını ({hj_bound:.4f}) karşılamaktadır."
            )

        return CCAPMDiagnosticResult(
            risk_aversion=gamma,
            time_discount_beta=beta,
            consumption_growth_mean=round(mu_c, 4),
            consumption_growth_std=round(sigma_c, 4),
            theoretical_sdf_mean=round(e_m, 4),
            theoretical_sdf_std=round(std_m, 4),
            theoretical_sdf_vol_ratio=round(vol_ratio, 4),
            required_hj_bound=round(hj_bound, 4),
            equity_premium_puzzle_confirmed=puzzle,
            verdict=verdict
        )


# ==============================================================================
# CLI DISPATCHER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 27: Quantitative Financial Engineering CLI")
    subparsers = parser.add_subparsers(dest="command", help="Financial Pillar Commands")

    cds_p = subparsers.add_parser("cds-bootstrap", help="Duffie-Singleton CDS Hazard Rate Bootstrap")
    cds_p.add_argument("--maturities", type=float, nargs="+", default=[1.0, 2.0, 3.0, 5.0, 10.0])
    cds_p.add_argument("--spreads", type=float, nargs="+", default=[60.0, 85.0, 110.0, 145.0, 180.0])
    cds_p.add_argument("--recovery", type=float, default=0.40)
    cds_p.add_argument("--rate", type=float, default=0.03)

    var_p = subparsers.add_parser("var-backtest", help="Kupiec POF & Christoffersen VaR Backtesting")
    var_p.add_argument("--violations", type=int, default=4)
    var_p.add_argument("--observations", type=int, default=250)
    var_p.add_argument("--confidence", type=float, default=0.99)

    liq_p = subparsers.add_parser("amihud-liq", help="Amihud Illiquidity Ratio")
    liq_p.add_argument("--returns", type=float, nargs="+", default=[0.012, -0.008, 0.015, -0.022, 0.005])
    liq_p.add_argument("--volumes", type=float, nargs="+", default=[50_000_000, 45_000_000, 60_000_000, 75_000_000, 40_000_000])

    bdt_p = subparsers.add_parser("bdt-callable", help="Black-Derman-Toy Callable Bond Valuation")
    bdt_p.add_argument("--zeros", type=float, nargs="+", default=[0.9524, 0.9070, 0.8638, 0.8227])
    bdt_p.add_argument("--vols", type=float, nargs="+", default=[0.15, 0.15, 0.15, 0.15])
    bdt_p.add_argument("--coupon", type=float, default=0.05)
    bdt_p.add_argument("--face", type=float, default=100.0)

    bs_p = subparsers.add_parser("bjerksund-american", help="Bjerksund-Stensland American Option")
    bs_p.add_argument("--spot", type=float, default=100.0)
    bs_p.add_argument("--strike", type=float, default=100.0)
    bs_p.add_argument("--maturity", type=float, default=1.0)
    bs_p.add_argument("--rate", type=float, default=0.05)
    bs_p.add_argument("--dividend", type=float, default=0.02)
    bs_p.add_argument("--vol", type=float, default=0.25)
    bs_p.add_argument("--type", type=str, default="call")

    hj_p = subparsers.add_parser("hansen-jagannathan", help="Hansen-Jagannathan SDF Volatility Bound")
    hj_p.add_argument("--gamma", type=float, default=2.0)
    hj_p.add_argument("--bound", type=float, default=0.40)

    args = parser.parse_args()

    if args.command == "cds-bootstrap":
        res = DuffieSingletonCDSEngine.bootstrap_hazard_rates(
            maturities=args.maturities,
            spreads_bps=args.spreads,
            recovery_rate=args.recovery,
            risk_free_rate=args.rate
        )
        print(json.dumps(res.__dict__, indent=2))
    elif args.command == "var-backtest":
        kupiec = VaRBacktestingEngine.kupiec_pof_test(args.violations, args.observations, args.confidence)
        traffic = VaRBacktestingEngine.basel_traffic_light(args.violations, args.observations)
        print(json.dumps({"kupiec_pof": kupiec.__dict__, "basel_traffic_light": traffic.__dict__}, indent=2))
    elif args.command == "amihud-liq":
        res = LiquidityDynamicsEngine.calculate_amihud_illiquidity(args.returns, args.volumes)
        print(json.dumps(res.__dict__, indent=2))
    elif args.command == "bdt-callable":
        mats = [float(i + 1) for i in range(len(args.zeros))]
        lattice = BlackDermanToyLatticeEngine.calibrate_bdt_lattice(mats, args.zeros, args.vols)
        res = BlackDermanToyLatticeEngine.price_callable_bond(lattice, args.face, args.coupon)
        print(json.dumps(res.__dict__, indent=2))
    elif args.command == "bjerksund-american":
        res = BjerksundStenslandEngine.evaluate_option_with_greeks(
            args.spot, args.strike, args.maturity, args.rate, args.dividend, args.vol, args.type
        )
        print(json.dumps(res.__dict__, indent=2))
    elif args.command == "hansen-jagannathan":
        res = HansenJagannathanEngine.evaluate_ccapm_pricing_kernel(risk_aversion_gamma=args.gamma, hj_bound=args.bound)
        print(json.dumps(res.__dict__, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
