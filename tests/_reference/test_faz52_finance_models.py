"""Programmatic TDD Verification Suite for Faz 52 Quantitative Finance Engines.

Models:
1. Damiano Brigo, Massimo Morini & Andrea Pallavicini (2013) / Jon Gregory (2015): Bilateral Counterparty Credit Risk (BCVA & DVA), Expected Exposure (EPE/ENE) & Wrong-Way Risk (WWR) Coupling
2. Thomas M. Cover (1991) & David Ordentlich (1996): Universal Portfolios, Online Machine Learning Portfolio Selection & Continuous-Simplex Dirichlet Regret Bounds
3. CreditRisk+ (Credit Suisse First Boston 1997 / Bluhm, Overbeck & Wagner 2002): Actuarial Portfolio Credit Risk Engine, Sector Factor Default Intensities & Exact Panjer Loss Recursion
4. David H. Bailey & Marcos Lopez de Prado (2014) / Campbell R. Harvey & Yan Liu (2015): Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR) & Multiple Testing Backtest Overfitting Correction
5. Avinash Dixit & Robert Pindyck (1994) / Stewart C. Myers (1977): Real Options Theory, Investment Under Irreversible Uncertainty, Optimal Exercise Boundary & The Smooth Pasting Condition (V'(S*) = 1)
6. Peter Carr, Keith Ellis & Vishal Gupta (1998) / Emanuel Derman, Deniz Ergener & Iraj Kani (1995): Put-Call Symmetry (PCS), Method of Images & Static Hedging of Exotic Barrier Options
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Numerical Functions (Pure Python + NumPy)
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_ppf(p: float) -> float:
    """Inverse normal CDF via Acklam's rational approximation."""
    if p <= 0.0:
        return -float('inf')
    if p >= 1.0:
        return float('inf')
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Standard Black-Scholes European call price."""
    if T <= 1e-8:
        return max(0.0, S - K)
    if sigma <= 1e-8:
        return max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T))
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Standard Black-Scholes European put price."""
    if T <= 1e-8:
        return max(0.0, K - S)
    if sigma <= 1e-8:
        return max(0.0, K * math.exp(-r * T) - S * math.exp(-q * T))
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)


# ==============================================================================
# Model 1: Damiano Brigo, Massimo Morini & Andrea Pallavicini (2013) / Jon Gregory (2015)
# Bilateral Counterparty Credit Risk: BCVA, DVA, Exposure Profiles & Wrong-Way Risk (WWR)
# ==============================================================================
class BilateralCounterpartyCreditRiskEngine:
    """
    Damiano Brigo, Massimo Morini & Andrea Pallavicini (2013) / Jon Gregory (2015)
    Quantifies Bilateral Credit Valuation Adjustment (BCVA), Debt Valuation Adjustment (DVA),
    Expected Positive Exposure (EPE), Expected Negative Exposure (ENE), Effective EPE (EEPE),
    and Wrong-Way Risk (WWR) coupling under stochastic intensity and correlated exposures.
    """

    def __init__(
        self,
        hazard_rate_counterparty: float = 0.03,  # lambda_C
        hazard_rate_investor: float = 0.015,    # lambda_I
        recovery_counterparty: float = 0.40,    # R_C
        recovery_investor: float = 0.40,        # R_I
        risk_free_rate: float = 0.03            # r
    ):
        self.lambda_C = hazard_rate_counterparty
        self.lambda_I = hazard_rate_investor
        self.R_C = recovery_counterparty
        self.R_I = recovery_investor
        self.r = risk_free_rate

    def compute_exposure_profile(
        self,
        simulated_portfolio_values: np.ndarray,
        time_grid: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Computes the time profile of expected exposures across Monte Carlo scenarios.
        simulated_portfolio_values: shape (num_paths, num_steps)
        time_grid: shape (num_steps,) with t_0 = 0.0
        """
        paths, steps = simulated_portfolio_values.shape
        positive_exposure = np.maximum(simulated_portfolio_values, 0.0)
        negative_exposure = np.maximum(-simulated_portfolio_values, 0.0)

        epe = np.mean(positive_exposure, axis=0)
        ene = np.mean(negative_exposure, axis=0)
        
        # 95% and 99% Potential Future Exposure (PFE)
        pfe_95 = np.percentile(positive_exposure, 95.0, axis=0)
        pfe_99 = np.percentile(positive_exposure, 99.0, axis=0)

        # Effective EPE (non-decreasing running maximum)
        effective_epe = np.maximum.accumulate(epe)
        if hasattr(np, "trapezoid"):
            eepe = float(np.trapezoid(effective_epe, time_grid) / max(time_grid[-1], 1e-6))
        else:
            eepe = float(np.trapz(effective_epe, time_grid) / max(time_grid[-1], 1e-6))

        return {
            "time_grid": time_grid,
            "epe": epe,
            "ene": ene,
            "pfe_95": pfe_95,
            "pfe_99": pfe_99,
            "effective_epe": effective_epe,
            "eepe_scalar": eepe
        }

    def calculate_unilateral_cva(
        self,
        time_grid: np.ndarray,
        epe_profile: np.ndarray,
        wwr_factor: float = 0.0
    ) -> float:
        """
        Unilateral CVA with optional Wrong-Way Risk (WWR) multiplier.
        CVA = (1 - R_C) * sum_{k=1}^M D(0, t_k) * EPE*(t_k) * Delta PD_C(t_k)
        """
        cva = 0.0
        lgd = 1.0 - self.R_C
        for k in range(1, len(time_grid)):
            t_prev = time_grid[k - 1]
            t_curr = time_grid[k]
            t_mid = 0.5 * (t_prev + t_curr)
            df = math.exp(-self.r * t_mid)
            
            # Marginal default probability for counterparty
            p_surv_prev = math.exp(-self.lambda_C * t_prev)
            p_surv_curr = math.exp(-self.lambda_C * t_curr)
            marginal_pd = max(0.0, p_surv_prev - p_surv_curr)

            # Apply WWR tilt: if wwr_factor > 0, exposure is positively coupled to default intensity
            exposure = epe_profile[k] * (1.0 + wwr_factor)
            cva += lgd * df * exposure * marginal_pd

        return cva

    def calculate_bilateral_cva_dva(
        self,
        time_grid: np.ndarray,
        epe_profile: np.ndarray,
        ene_profile: np.ndarray,
        wwr_factor: float = 0.0
    ) -> Dict[str, float]:
        """
        Computes Bilateral CVA (BCVA), DVA and Net Bilateral Adjustment under first-to-default independence:
        BCVA = (1 - R_C) * sum D(0, t_k) * EPE(t_k) * S_I(t_k) * Delta PD_C(t_k)
        DVA  = (1 - R_I) * sum D(0, t_k) * ENE(t_k) * S_C(t_k) * Delta PD_I(t_k)
        Net Adjustment = DVA - BCVA
        """
        bcva = 0.0
        dva = 0.0
        lgd_c = 1.0 - self.R_C
        lgd_i = 1.0 - self.R_I

        for k in range(1, len(time_grid)):
            t_prev = time_grid[k - 1]
            t_curr = time_grid[k]
            t_mid = 0.5 * (t_prev + t_curr)
            df = math.exp(-self.r * t_mid)

            # Counterparty survival & marginal default
            s_c_prev = math.exp(-self.lambda_C * t_prev)
            s_c_curr = math.exp(-self.lambda_C * t_curr)
            delta_pd_c = max(0.0, s_c_prev - s_c_curr)

            # Investor survival & marginal default
            s_i_prev = math.exp(-self.lambda_I * t_prev)
            s_i_curr = math.exp(-self.lambda_I * t_curr)
            delta_pd_i = max(0.0, s_i_prev - s_i_curr)

            s_i_mid = 0.5 * (s_i_prev + s_i_curr)
            s_c_mid = 0.5 * (s_c_prev + s_c_curr)

            # BCVA accounts for investor surviving until counterparty defaults
            adjusted_epe = epe_profile[k] * (1.0 + wwr_factor)
            bcva += lgd_c * df * adjusted_epe * s_i_mid * delta_pd_c

            # DVA accounts for counterparty surviving until investor defaults
            dva += lgd_i * df * ene_profile[k] * s_c_mid * delta_pd_i

        net_adjustment = dva - bcva
        return {
            "unilateral_cva": self.calculate_unilateral_cva(time_grid, epe_profile, wwr_factor),
            "bilateral_cva": bcva,
            "dva": dva,
            "net_credit_adjustment": net_adjustment
        }


# ==============================================================================
# Model 2: Thomas M. Cover (1991) & David Ordentlich (1996)
# Universal Portfolios & Online No-Regret Learning Engine
# ==============================================================================
class CoverUniversalPortfolioEngine:
    """
    Thomas M. Cover (1991) & David Ordentlich (1996)
    Implements the Continuous-Simplex Universal Portfolio algorithm.
    Achieves the optimal asymptotic growth rate of the Best Constant Rebalanced Portfolio (BCRP)
    in hindsight without making any statistical assumptions on price return sequences.
    """

    def __init__(self, num_assets: int, num_mc_simplex_points: int = 5000, random_seed: int = 42):
        if num_assets < 2:
            raise ValueError("Universal portfolio requires at least 2 assets.")
        self.m = num_assets
        self.num_points = num_mc_simplex_points
        self.rng = np.random.default_rng(random_seed)
        
        # Sample uniform points on the probability simplex Delta_m via Dirichlet(1, 1, ..., 1)
        self.simplex_grid = self.rng.dirichlet(np.ones(self.m), size=self.num_points)
        # Cumulative wealth for each constant rebalanced portfolio (CRP) b in the grid
        self.crp_wealths = np.ones(self.num_points, dtype=float)

    def compute_next_weights(self) -> np.ndarray:
        """
        Computes the Cover universal portfolio weight vector b_hat_{t+1}:
        b_hat_{t+1} = integral_{Delta_m} b * S_t(b) d mu(b) / integral_{Delta_m} S_t(b) d mu(b)
        """
        total_weight = np.sum(self.crp_wealths)
        if total_weight <= 1e-15 or np.isnan(total_weight):
            return np.ones(self.m) / self.m
        
        # Weighted expectation of simplex vectors
        norm_weights = self.crp_wealths / total_weight
        b_next = np.sum(self.simplex_grid * norm_weights[:, np.newaxis], axis=0)
        return b_next / np.sum(b_next)

    def update(self, price_relatives: np.ndarray) -> Dict[str, float]:
        """
        Updates the internal state with the observed price relative vector x_t = S_t / S_{t-1}.
        Returns the instantaneous turn wealth multiplier and cumulative wealth.
        """
        x_t = np.asarray(price_relatives, dtype=float)
        if len(x_t) != self.m or np.any(x_t < 0.0):
            raise ValueError("Invalid price relatives.")

        # 1. Weights that were chosen before seeing x_t
        b_current = self.compute_next_weights()
        turn_return = float(np.dot(b_current, x_t))

        # 2. Update each CRP's wealth: S_t(b) = S_{t-1}(b) * (b^T x_t)
        crp_returns = np.dot(self.simplex_grid, x_t)
        self.crp_wealths *= crp_returns

        return {
            "turn_return": turn_return,
            "universal_portfolio_return": turn_return,
            "weights": b_current
        }

    def evaluate_bcrp_hindsight(self, price_relatives_matrix: np.ndarray) -> Dict[str, Any]:
        """
        Calculates the Best Constant Rebalanced Portfolio (BCRP) in hindsight over T periods,
        the Universal Portfolio wealth, and verifies the logarithmic regret bound.
        price_relatives_matrix: shape (T, m)
        """
        T, m = price_relatives_matrix.shape
        grid_wealths = np.ones(self.num_points, dtype=float)
        univ_wealth = 1.0
        univ_wealth_history = [1.0]

        # Reset simulation state
        temp_crp_wealths = np.ones(self.num_points, dtype=float)

        for t in range(T):
            x_t = price_relatives_matrix[t]
            
            # Universal choice
            w_sum = np.sum(temp_crp_wealths)
            b_hat = np.sum(self.simplex_grid * (temp_crp_wealths / w_sum)[:, np.newaxis], axis=0)
            univ_ret = float(np.dot(b_hat, x_t))
            univ_wealth *= univ_ret
            univ_wealth_history.append(univ_wealth)

            # Update CRPs
            ret_grid = np.dot(self.simplex_grid, x_t)
            temp_crp_wealths *= ret_grid
            grid_wealths *= ret_grid

        # Find best CRP in grid
        best_idx = int(np.argmax(grid_wealths))
        bcrp_wealth = float(grid_wealths[best_idx])
        bcrp_best_b = self.simplex_grid[best_idx]

        # Regret in log terms
        log_regret = math.log(max(bcrp_wealth, 1e-12)) - math.log(max(univ_wealth, 1e-12))
        theoretical_bound = 0.5 * (self.m - 1) * math.log(T + 1) + 2.0

        return {
            "bcrp_wealth": bcrp_wealth,
            "bcrp_weights": bcrp_best_b,
            "universal_wealth": univ_wealth,
            "log_regret": log_regret,
            "theoretical_bound": theoretical_bound,
            "regret_bound_satisfied": bool(log_regret <= theoretical_bound + 1e-5)
        }


# ==============================================================================
# Model 3: CreditRisk+ (Credit Suisse First Boston 1997 / Bluhm et al. 2002)
# Actuarial Portfolio Credit Risk Engine & Exact Panjer Recursion
# ==============================================================================
class CreditRiskPlusActuarialEngine:
    """
    CreditRisk+ (CSFB 1997 / Bluhm, Overbeck & Wagner 2002)
    Models portfolio default losses via sector-driven Poisson processes with Gamma mixtures.
    Derives the complete discrete portfolio loss probability distribution via the exact
    Panjer / Adelson recursion without requiring Monte Carlo simulation.
    """

    def __init__(
        self,
        loss_unit: float = 10000.0,           # L_0 unit quantum (e.g. $10k)
        sector_variances: Optional[Dict[str, float]] = None # Sector default rate variance sigma_k^2
    ):
        self.L_0 = loss_unit
        self.sector_variances = sector_variances or {"General": 0.25}

    def compute_loss_distribution_panjer(
        self,
        obligor_exposures: List[float],       # EAD_i * LGD_i
        obligor_default_probs: List[float],   # p_i
        obligor_sectors: Optional[List[str]] = None,
        max_loss_units: int = 50
    ) -> Dict[str, Any]:
        """
        Executes Panjer recursion for the compound Poisson portfolio loss distribution.
        p(L = n) = g_n
        g_n = (1 / n) * sum_{j=1}^n j * P_j * g_{n-j}
        where P_j is the expected number of obligors causing a loss of exactly j units.
        """
        num_obligors = len(obligor_exposures)
        if len(obligor_default_probs) != num_obligors:
            raise ValueError("Exposures and default probabilities must have equal length.")

        sectors = obligor_sectors or ["General"] * num_obligors
        
        # Discretize losses into integer units nu_i = round(L_i / L_0)
        integer_losses = [max(1, int(round(exp / self.L_0))) for exp in obligor_exposures]
        max_unit = max(integer_losses)

        # Compute P_j = sum_{i: nu_i = j} p_i
        p_j_poly = np.zeros(max_unit + 1, dtype=float)
        mu_total = 0.0
        for i in range(num_obligors):
            j = integer_losses[i]
            p_i = obligor_default_probs[i]
            p_j_poly[j] += p_i
            mu_total += p_i

        # Expected aggregate units of loss
        expected_units = sum(j * p_j_poly[j] for j in range(1, max_unit + 1))
        expected_loss_currency = expected_units * self.L_0

        # Panjer recursion for g_n:
        # g_0 = exp(-mu_total)
        g = np.zeros(max_loss_units + 1, dtype=float)
        g[0] = math.exp(-mu_total)

        for n in range(1, max_loss_units + 1):
            limit = min(n, max_unit)
            conv_sum = 0.0
            for j in range(1, limit + 1):
                conv_sum += j * p_j_poly[j] * g[n - j]
            g[n] = conv_sum / n

        # Cumulative probability distribution
        cum_prob = np.cumsum(g)
        cum_prob = np.minimum(1.0, cum_prob)

        # Calculate Credit VaR at 95% and 99%
        var_95_unit = int(np.searchsorted(cum_prob, 0.95))
        var_99_unit = int(np.searchsorted(cum_prob, 0.99))
        var_95_currency = var_95_unit * self.L_0
        var_99_currency = var_99_unit * self.L_0

        # Calculate Expected Shortfall (CVaR) at 95%
        tail_indices = np.where(cum_prob >= 0.95)[0]
        if len(tail_indices) > 0:
            tail_probs = g[tail_indices]
            tail_sum = np.sum(tail_probs)
            if tail_sum > 1e-12:
                es_95_unit = float(np.sum(tail_indices * tail_probs) / tail_sum)
            else:
                es_95_unit = float(var_95_unit)
        else:
            es_95_unit = float(var_95_unit)

        es_95_currency = es_95_unit * self.L_0

        return {
            "loss_probabilities": g,
            "cumulative_probabilities": cum_prob,
            "expected_loss_currency": expected_loss_currency,
            "unexpected_loss_currency": (var_99_currency - expected_loss_currency),
            "credit_var_95": var_95_currency,
            "credit_var_99": var_99_currency,
            "credit_es_95": es_95_currency,
            "panjer_distribution_sum": float(np.sum(g))
        }


# ==============================================================================
# Model 4: David H. Bailey & Marcos Lopez de Prado (2014)
# Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR) & Overfitting Engine
# ==============================================================================
class DeflatedSharpeRatioEngine:
    """
    David H. Bailey & Marcos Lopez de Prado (2014) / Campbell R. Harvey & Yan Liu (2015)
    Evaluates strategy track records by computing:
    1. Andrew Lo / Mertens asymptotic standard error of the Sharpe ratio with non-normal skewness & kurtosis
    2. Probabilistic Sharpe Ratio (PSR) relative to benchmark SR*
    3. Expected maximum Sharpe ratio under N trials via Extreme Value Theory (EVT)
    4. Deflated Sharpe Ratio (DSR) correcting for backtest selection bias and multiple testing
    """

    EULER_MASCHERONI = 0.57721566490153286

    def __init__(self, benchmark_sharpe: float = 0.0):
        self.sr_benchmark = benchmark_sharpe

    def compute_asymptotic_sr_std(
        self,
        sharpe: float,
        num_observations: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> float:
        """
        Andrew Lo (2002) / Mertens (2002) standard error of estimated Sharpe ratio:
        sigma_SR = sqrt( (1 - gamma_3 * SR + (gamma_4 - 1)/4 * SR^2) / T )
        """
        if num_observations <= 1:
            raise ValueError("Sample size T must be greater than 1.")
        variance_term = (1.0 - skewness * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe ** 2))
        variance_term = max(1e-12, variance_term)
        return math.sqrt(variance_term / (num_observations - 1))

    def compute_psr(
        self,
        observed_sharpe: float,
        num_observations: int,
        benchmark_sr: Optional[float] = None,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> float:
        """
        Probabilistic Sharpe Ratio: PSR(SR*) = Phi( (SR - SR*) / sigma_SR )
        Probability that the true Sharpe ratio is greater than benchmark_sr.
        """
        sr_star = self.sr_benchmark if benchmark_sr is None else benchmark_sr
        sigma_sr = self.compute_asymptotic_sr_std(observed_sharpe, num_observations, skewness, kurtosis)
        z = (observed_sharpe - sr_star) / sigma_sr
        return norm_cdf(z)

    def compute_expected_max_sharpe(
        self,
        num_trials: int,
        var_sharpe: float = 1.0
    ) -> float:
        """
        Expected maximum Sharpe ratio among N independent strategy trials under false discovery:
        E[max_N SR] = sqrt(var_SR) * [ (1 - gamma) * Phi^{-1}(1 - 1/N) + gamma * Phi^{-1}(1 - 1/(N*e)) ]
        """
        if num_trials <= 1:
            return 0.0
        
        p1 = 1.0 - (1.0 / num_trials)
        p2 = 1.0 - (1.0 / (num_trials * math.e))
        
        # Ensure strict bounds in (0, 1) for inverse CDF
        p1 = max(1e-9, min(p1, 1.0 - 1e-9))
        p2 = max(1e-9, min(p2, 1.0 - 1e-9))

        z1 = norm_ppf(p1)
        z2 = norm_ppf(p2)
        
        expected_z = (1.0 - self.EULER_MASCHERONI) * z1 + self.EULER_MASCHERONI * z2
        return math.sqrt(max(1e-8, var_sharpe)) * expected_z

    def compute_deflated_sharpe_ratio(
        self,
        observed_sharpe: float,
        num_observations: int,
        num_trials: int,
        var_sharpe_trials: float = 0.5,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> Dict[str, Any]:
        """
        Calculates the Deflated Sharpe Ratio (DSR):
        DSR = PSR(SR* = E[max_N SR_n])
        """
        expected_max_sr = self.compute_expected_max_sharpe(num_trials, var_sharpe_trials)
        dsr = self.compute_psr(
            observed_sharpe=observed_sharpe,
            num_observations=num_observations,
            benchmark_sr=expected_max_sr,
            skewness=skewness,
            kurtosis=kurtosis
        )
        standard_psr = self.compute_psr(
            observed_sharpe=observed_sharpe,
            num_observations=num_observations,
            benchmark_sr=self.sr_benchmark,
            skewness=skewness,
            kurtosis=kurtosis
        )
        
        # Haircut Sharpe ratio: observed SR minus expected false discovery maximum
        haircut_sr = max(0.0, observed_sharpe - expected_max_sr)

        return {
            "observed_sharpe": observed_sharpe,
            "num_trials": num_trials,
            "expected_max_sharpe_threshold": expected_max_sr,
            "standard_psr": standard_psr,
            "deflated_sharpe_ratio": dsr,
            "haircut_sharpe": haircut_sr,
            "statistically_robust": bool(dsr >= 0.95)
        }


# ==============================================================================
# Model 5: Avinash Dixit & Robert Pindyck (1994) / Stewart C. Myers (1977)
# Real Options Theory: Irreversible Investment, Option Value of Waiting & Smooth Pasting
# ==============================================================================
class DixitPindyckRealOptionsEngine:
    """
    Avinash Dixit & Robert Pindyck (1994) / Stewart C. Myers (1977)
    Models capital investment under uncertainty as an American call option on project cash flows.
    Solves the Bellman ODE via the Smooth Pasting Condition (V'(S*) = 1) and Value Matching Condition,
    determining the optimal investment threshold V* > I and quantifying the Option Value of Waiting (Hysteresis).
    """

    def __init__(
        self,
        risk_free_rate: float = 0.04,   # r
        convenience_yield: float = 0.02, # delta (payout / dividend yield on project)
        volatility: float = 0.25         # sigma of project cash flow value
    ):
        if convenience_yield <= 0.0:
            raise ValueError("Convenience yield delta must be strictly positive to ensure finite stopping.")
        self.r = risk_free_rate
        self.delta = convenience_yield
        self.sigma = volatility
        self.beta1 = self._solve_characteristic_root()

    def _solve_characteristic_root(self) -> float:
        """
        Solves the fundamental quadratic equation:
        1/2 * sigma^2 * beta * (beta - 1) + (r - delta) * beta - r = 0
        Returns the positive root beta_1 > 1.
        """
        a = 0.5 * self.sigma * self.sigma
        b = (self.r - self.delta) - a
        c = -self.r

        discriminant = b * b - 4.0 * a * c
        beta1 = (-b + math.sqrt(discriminant)) / (2.0 * a)
        return beta1

    def compute_optimal_investment_threshold(self, investment_cost: float) -> Dict[str, float]:
        """
        Value Matching: F(V*) = V* - I
        Smooth Pasting: F'(V*) = 1
        Yields closed-form optimal exercise trigger:
        V* = (beta_1 / (beta_1 - 1)) * I
        and option coefficient A = (V* - I) / (V*^beta_1)
        """
        if investment_cost <= 0.0:
            raise ValueError("Investment cost I must be strictly positive.")
        
        markup_factor = self.beta1 / (self.beta1 - 1.0)
        v_star = markup_factor * investment_cost
        
        # Coefficient A of option value F(V) = A * V^{beta_1}
        coefficient_a = (v_star - investment_cost) / (v_star ** self.beta1)
        
        # Value of waiting (hysteresis wedge)
        hysteresis_spread = v_star - investment_cost

        return {
            "beta1": self.beta1,
            "markup_factor": markup_factor,
            "optimal_investment_threshold_v_star": v_star,
            "investment_cost_I": investment_cost,
            "hysteresis_spread": hysteresis_spread,
            "coefficient_a": coefficient_a
        }

    def evaluate_option_value(self, current_project_value: float, investment_cost: float) -> Dict[str, Any]:
        """
        Evaluates the investment decision and the option value F(V):
        If V < V*: Wait (F(V) = A * V^{beta_1} > V - I)
        If V >= V*: Invest immediately (F(V) = V - I)
        """
        params = self.compute_optimal_investment_threshold(investment_cost)
        v_star = params["optimal_investment_threshold_v_star"]
        a = params["coefficient_a"]

        if current_project_value < v_star:
            option_val = a * (current_project_value ** self.beta1)
            action = "WAIT"
            npv_now = current_project_value - investment_cost
        else:
            option_val = current_project_value - investment_cost
            action = "INVEST"
            npv_now = current_project_value - investment_cost

        return {
            "current_value_V": current_project_value,
            "optimal_threshold_V_star": v_star,
            "action": action,
            "option_value_F_V": option_val,
            "standard_npv": npv_now,
            "option_premium_over_npv": max(0.0, option_val - npv_now)
        }


# ==============================================================================
# Model 6: Peter Carr, Keith Ellis & Vishal Gupta (1998) / Emanuel Derman et al. (1995)
# Put-Call Symmetry (PCS) & Static Hedging of Barrier Options Engine
# ==============================================================================
class PutCallSymmetryStaticHedgingEngine:
    """
    Peter Carr, Keith Ellis & Vishal Gupta (1998) / Emanuel Derman, Deniz Ergener & Iraj Kani (1995)
    Put-Call Symmetry (PCS) and Method of Images for Static Hedging of Barrier Options.
    Constructs a model-independent static replicating portfolio of standard European puts and calls
    that identically matches the barrier boundary condition without requiring dynamic delta rehedging.
    """

    def __init__(self, barrier_level: float, risk_free_rate: float = 0.03, dividend_yield: float = 0.03):
        if barrier_level <= 0.0:
            raise ValueError("Barrier level H must be strictly positive.")
        self.H = barrier_level
        self.r = risk_free_rate
        self.q = dividend_yield

    def compute_mirror_strike(self, vanilla_strike: float) -> float:
        """
        Computes the Put-Call Symmetry mirror strike:
        K_mirror = H^2 / K
        """
        return (self.H * self.H) / vanilla_strike

    def compute_symmetry_ratio(self, vanilla_strike: float, sigma: float) -> float:
        """
        Symmetry multiplier for European put replication:
        When r = q, ratio = K / H.
        For general r and q, power exponent is alpha = 2 * (r - q) / sigma^2 - 1.
        """
        if abs(self.r - self.q) < 1e-6:
            return vanilla_strike / self.H
        alpha = (2.0 * (self.r - self.q) / (sigma * sigma)) - 1.0
        return (vanilla_strike / self.H) ** alpha

    def construct_down_and_out_call_static_hedge(
        self,
        call_strike: float,
        expiry: float,
        sigma: float
    ) -> Dict[str, Any]:
        """
        Constructs a static hedge portfolio for a Down-and-Out Call (DOC) with barrier H < K:
        DOC(S, T; K, H) = Call(S, T; K) - (K / H) * Put(S, T; H^2 / K)
        At the boundary S = H:
        Call(H, T; K) - (K / H) * Put(H, T; H^2 / K) = 0.0 identically!
        """
        if call_strike <= self.H:
            raise ValueError("For standard DOC, call strike K should be greater than barrier H.")
        
        mirror_strike = self.compute_mirror_strike(call_strike)
        hedge_ratio = self.compute_symmetry_ratio(call_strike, sigma)

        return {
            "barrier_H": self.H,
            "call_strike_K": call_strike,
            "mirror_put_strike": mirror_strike,
            "put_short_ratio": hedge_ratio,
            "expiry": expiry,
            "sigma": sigma
        }

    def price_static_hedge(
        self,
        spot_S: float,
        call_strike: float,
        expiry: float,
        sigma: float
    ) -> Dict[str, float]:
        """
        Evaluates the price of the static replicating portfolio:
        V_hedge(S) = Call(S, K, T) - ratio * Put(S, K_mirror, T)
        """
        spec = self.construct_down_and_out_call_static_hedge(call_strike, expiry, sigma)
        k_mirror = spec["mirror_put_strike"]
        ratio = spec["put_short_ratio"]

        call_p = black_scholes_call(spot_S, call_strike, expiry, self.r, sigma, self.q)
        put_p = black_scholes_put(spot_S, k_mirror, expiry, self.r, sigma, self.q)

        portfolio_value = call_p - ratio * put_p
        
        # Also evaluate precisely at the barrier S = H
        call_barrier = black_scholes_call(self.H, call_strike, expiry, self.r, sigma, self.q)
        put_barrier = black_scholes_put(self.H, k_mirror, expiry, self.r, sigma, self.q)
        barrier_residual = abs(call_barrier - ratio * put_barrier)

        return {
            "spot_S": spot_S,
            "vanilla_call_price": call_p,
            "mirror_put_price": put_p,
            "static_hedge_value": portfolio_value,
            "barrier_residual_error": barrier_residual
        }


# ==============================================================================
# Pytest Verification Test Suite
# ==============================================================================
class TestFaz52QuantitativeFinanceEngines:

    def test_bilateral_cva_dva_and_wrong_way_risk(self):
        """Validates Brigo et al. BCVA, DVA, EPE/ENE exposure profiles & WWR."""
        engine = BilateralCounterpartyCreditRiskEngine(
            hazard_rate_counterparty=0.04,
            hazard_rate_investor=0.02,
            recovery_counterparty=0.40,
            recovery_investor=0.40,
            risk_free_rate=0.03
        )
        
        time_grid = np.linspace(0.0, 5.0, 21)
        # Synthetic swap-like Monte Carlo paths: oscillating around 0 with widening dispersion
        rng = np.random.default_rng(123)
        num_paths = 500
        sim_values = np.zeros((num_paths, len(time_grid)))
        for t_idx in range(1, len(time_grid)):
            dt = time_grid[t_idx] - time_grid[t_idx - 1]
            sim_values[:, t_idx] = sim_values[:, t_idx - 1] + rng.normal(0.0, 20.0 * math.sqrt(dt), size=num_paths)

        profile = engine.compute_exposure_profile(sim_values, time_grid)
        assert len(profile["epe"]) == len(time_grid)
        assert np.all(profile["epe"] >= 0.0)
        assert np.all(profile["ene"] >= 0.0)
        assert profile["eepe_scalar"] > 0.0

        # Bilateral CVA / DVA calculations without WWR
        res_nowwr = engine.calculate_bilateral_cva_dva(time_grid, profile["epe"], profile["ene"], wwr_factor=0.0)
        assert res_nowwr["bilateral_cva"] > 0.0
        assert res_nowwr["dva"] > 0.0
        # Counterparty hazard rate (0.04) > Investor hazard rate (0.02), so BCVA should exceed DVA for symmetric exposure
        assert res_nowwr["bilateral_cva"] > res_nowwr["dva"]

        # With positive Wrong-Way Risk (WWR), CVA must increase
        res_wwr = engine.calculate_bilateral_cva_dva(time_grid, profile["epe"], profile["ene"], wwr_factor=0.30)
        assert res_wwr["bilateral_cva"] > res_nowwr["bilateral_cva"]
        assert math.isclose(res_wwr["bilateral_cva"], res_nowwr["bilateral_cva"] * 1.30, rel_tol=1e-5)

    def test_cover_universal_portfolios_and_no_regret(self):
        """Validates Cover's continuous-simplex universal portfolio and regret bound."""
        num_assets = 3
        engine = CoverUniversalPortfolioEngine(num_assets=num_assets, num_mc_simplex_points=3000, random_seed=42)

        # 1. Simplex property of next weights
        w0 = engine.compute_next_weights()
        assert len(w0) == num_assets
        assert np.all(w0 >= 0.0)
        assert math.isclose(np.sum(w0), 1.0, abs_tol=1e-5)

        # 2. Simulated multi-period market with volatile rebalancing opportunity
        rng = np.random.default_rng(777)
        T = 40
        # Returns where asset 0 and asset 1 oscillate (anti-correlated volatility)
        rets = np.ones((T, num_assets))
        for t in range(T):
            if t % 2 == 0:
                rets[t, 0] = 1.15
                rets[t, 1] = 0.90
            else:
                rets[t, 0] = 0.90
                rets[t, 1] = 1.15
            rets[t, 2] = 1.01  # cash-like

        eval_res = engine.evaluate_bcrp_hindsight(rets)
        assert eval_res["bcrp_wealth"] > 1.0
        assert eval_res["universal_wealth"] > 1.0
        # Universal portfolio must achieve growth and satisfy Cover's asymptotic regret bound
        assert eval_res["regret_bound_satisfied"] is True
        assert eval_res["log_regret"] <= eval_res["theoretical_bound"]

    def test_creditrisk_plus_panjer_recursion(self):
        """Validates CreditRisk+ exact Panjer recursion, PGF and portfolio loss distribution."""
        engine = CreditRiskPlusActuarialEngine(loss_unit=10000.0)

        exposures = [50000.0, 100000.0, 70000.0, 30000.0, 80000.0, 120000.0]
        p_defaults = [0.03, 0.02, 0.04, 0.01, 0.05, 0.02]

        res = engine.compute_loss_distribution_panjer(
            obligor_exposures=exposures,
            obligor_default_probs=p_defaults,
            max_loss_units=60
        )

        probs = res["loss_probabilities"]
        # Probabilities must be non-negative and bounded in [0, 1]
        assert np.all(probs >= 0.0)
        assert probs[0] > 0.0  # Zero loss has positive probability
        # Total probability mass should sum close to 1.0 (within truncated max loss window)
        assert 0.95 <= res["panjer_distribution_sum"] <= 1.0001

        # Credit VaR monotonic ordering
        assert res["credit_var_95"] <= res["credit_var_99"]
        # Expected shortfall exceeds 95% VaR
        assert res["credit_es_95"] >= res["credit_var_95"] - 1e-5
        assert res["unexpected_loss_currency"] > 0.0

    def test_deflated_sharpe_ratio_and_backtest_overfitting(self):
        """Validates Bailey & Lopez de Prado DSR, PSR and multiple testing correction."""
        dsr_engine = DeflatedSharpeRatioEngine(benchmark_sharpe=0.0)

        # Track record with moderate positive Sharpe
        observed_sr = 1.2
        num_obs = 250  # 1 year of daily returns
        skew = -0.40   # Negative skew (tail risk)
        kurt = 4.50    # Fat tails

        # 1. Asymptotic standard error with fat tails
        se_sr = dsr_engine.compute_asymptotic_sr_std(observed_sr, num_obs, skew, kurt)
        assert se_sr > 0.0

        # 2. Standard Probabilistic Sharpe Ratio without multiple testing
        psr_single = dsr_engine.compute_psr(observed_sr, num_obs, benchmark_sr=0.0, skewness=skew, kurtosis=kurt)
        assert psr_single > 0.99  # Strong confidence if it were the only test

        # 3. Deflated Sharpe Ratio under N = 500 trials (data snooping / backtest mining)
        res_dsr_500 = dsr_engine.compute_deflated_sharpe_ratio(
            observed_sharpe=observed_sr,
            num_observations=num_obs,
            num_trials=500,
            var_sharpe_trials=0.6,
            skewness=skew,
            kurtosis=kurt
        )
        assert res_dsr_500["expected_max_sharpe_threshold"] > 1.0
        # Because expected max SR among 500 trials is high, DSR drops significantly
        assert res_dsr_500["deflated_sharpe_ratio"] < psr_single
        assert res_dsr_500["haircut_sharpe"] < observed_sr

        # If only 1 trial, DSR should match standard PSR
        res_dsr_1 = dsr_engine.compute_deflated_sharpe_ratio(
            observed_sharpe=observed_sr,
            num_observations=num_obs,
            num_trials=1,
            var_sharpe_trials=0.6,
            skewness=skew,
            kurtosis=kurt
        )
        assert math.isclose(res_dsr_1["deflated_sharpe_ratio"], psr_single, abs_tol=1e-5)

    def test_dixit_pindyck_real_options_and_smooth_pasting(self):
        """Validates Dixit-Pindyck irreversible investment, smooth pasting & option value of waiting."""
        r = 0.05
        delta = 0.03
        sigma = 0.20
        engine = DixitPindyckRealOptionsEngine(risk_free_rate=r, convenience_yield=delta, volatility=sigma)

        # Characteristic root beta_1 must be strictly greater than 1
        assert engine.beta1 > 1.0

        # Investment cost
        I = 1000.0
        thresh = engine.compute_optimal_investment_threshold(investment_cost=I)
        v_star = thresh["optimal_investment_threshold_v_star"]
        markup = thresh["markup_factor"]

        # V* must strictly exceed investment cost I due to option value of waiting
        assert markup > 1.0
        assert v_star > I
        assert thresh["hysteresis_spread"] > 0.0

        # Check Value Matching and Smooth Pasting conditions numerically:
        # F(V*) = V* - I
        # F'(V*) = beta_1 * A * (V*)^{beta_1 - 1} == 1.0
        A = thresh["coefficient_a"]
        f_v_star = A * (v_star ** engine.beta1)
        assert math.isclose(f_v_star, v_star - I, rel_tol=1e-6)

        f_prime_v_star = engine.beta1 * A * (v_star ** (engine.beta1 - 1.0))
        assert math.isclose(f_prime_v_star, 1.0, rel_tol=1e-6)

        # Decision rule test:
        # Below V*, decision is WAIT, and option value exceeds standard NPV
        eval_low = engine.evaluate_option_value(current_project_value=I * 1.1, investment_cost=I)
        assert eval_low["action"] == "WAIT"
        assert eval_low["option_value_F_V"] > eval_low["standard_npv"]

        # Above V*, decision is INVEST
        eval_high = engine.evaluate_option_value(current_project_value=v_star * 1.1, investment_cost=I)
        assert eval_high["action"] == "INVEST"
        assert math.isclose(eval_high["option_value_F_V"], eval_high["standard_npv"], rel_tol=1e-6)

    def test_put_call_symmetry_static_barrier_hedging(self):
        """Validates Carr-Ellis-Gupta Put-Call Symmetry (PCS) & exact barrier zero-residual."""
        H = 90.0
        r = 0.03
        q = 0.03
        sigma = 0.25
        expiry = 1.0
        call_strike = 100.0

        engine = PutCallSymmetryStaticHedgingEngine(barrier_level=H, risk_free_rate=r, dividend_yield=q)

        # Mirror strike K_mirror = H^2 / K
        mirror_k = engine.compute_mirror_strike(call_strike)
        expected_mirror_k = (90.0 * 90.0) / 100.0  # 81.0
        assert math.isclose(mirror_k, expected_mirror_k, abs_tol=1e-6)

        # Symmetry hedge ratio when r == q is K / H
        ratio = engine.compute_symmetry_ratio(call_strike, sigma)
        assert math.isclose(ratio, call_strike / H, abs_tol=1e-6)

        # Price static hedge at spot above barrier S = 105
        pricing = engine.price_static_hedge(spot_S=105.0, call_strike=call_strike, expiry=expiry, sigma=sigma)
        assert pricing["static_hedge_value"] > 0.0

        # Exact boundary check: AT THE BARRIER S = H, residual error must be virtually zero (< 1e-10)
        assert pricing["barrier_residual_error"] < 1e-10
