"""Programmatic TDD Verification Suite for Faz 64 Quantitative Finance Engines.

Models:
1. Michael B. Gordy (2003): Asymptotic Single Risk Factor (ASRF) Model,
   Basel II/III Regulatory Credit Capital Formula, Asset Correlation Curves, and Portfolio Additivity.
2. Jack L. Treynor & Kay K. Mazuy (1966): Quadratic Market Timing Regression,
   Security Selection Alpha vs Market Timing Gamma Curvature, and Dynamic Beta Sensitivity.
3. Fulvio Corsi (2009) / Andersen, Bollerslev & Diebold (2007):
   Heterogeneous Autoregressive Model of Realized Volatility (HAR-RV & HAR-RV-J),
   Multi-Scale Market Horizons (Daily, Weekly, Monthly), and Continuous vs Jump Decomposition.
4. Tarun Chordia, Richard Roll & Avanidhar Subrahmanyam (2000, 2002):
   Order Imbalance & Market Liquidity Dynamics, Contemporaneous Price Impact,
   Inventory-Induced Return Reversals, and Commonality in Liquidity.
5. Ivo Welch & Amit Goyal (2008) / John Y. Campbell & Samuel B. Thompson (2008):
   Comprehensive Out-of-Sample Equity Premium Predictability Benchmark,
   Expanding Window OOS R^2 Metric, and Economically Motivated Sign/Positivity Constraints.
6. Wayne E. Ferson & Campbell R. Harvey (1991, 1993):
   Conditional Asset Pricing with Time-Varying Risk Betas and Dynamic Macroeconomic State Premia,
   Interaction Regressions, and Predictability Variance Decomposition.
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest


# ==============================================================================
# Helper Math Primitives
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_inv(p: float) -> float:
    """Exact inverse standard normal CDF via rational initialization and Newton-Raphson refinement."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability must be strictly between 0 and 1.")
    
    # Rational initial approximation
    if p < 0.5:
        t = math.sqrt(-2.0 * math.log(p))
        x = -(t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t))
    else:
        t = math.sqrt(-2.0 * math.log(1.0 - p))
        x = t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t)
    
    # Newton-Raphson refinement for machine precision (< 1e-15 error)
    for _ in range(5):
        err = norm_cdf(x) - p
        pdf = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
        if pdf < 1e-15:
            break
        x = x - err / pdf
        
    return float(x)


# ==============================================================================
# Model 1: Michael B. Gordy (2003) Asymptotic Single Risk Factor (ASRF) Engine
# ==============================================================================
class GordyASRFCreditCapitalEngine:
    """Michael B. Gordy (2003) Asymptotic Single Risk Factor (ASRF) Engine.
    
    Foundational model for Basel II / Basel III / Basel IV internal ratings-based (IRB)
    regulatory capital. In an asymptotically fine-grained portfolio with a single
    systemic risk driver X ~ N(0, 1), portfolio VaR decomposes into obligor-level additive capital charges:
    
    K_i = [ LGD_i * Phi( (Phi^-1(PD_i) + sqrt(rho_i) * Phi^-1(q)) / sqrt(1 - rho_i) ) - LGD_i * PD_i ] * MA(M_i)
    """

    @staticmethod
    def basel_asset_correlation(pd: float, asset_class: str = "corporate") -> float:
        """Computes Basel IRB formula asset correlation rho based on PD."""
        pd_clamped = min(max(pd, 1e-6), 0.999)
        decay = math.exp(-50.0 * pd_clamped)
        
        if asset_class.lower() in ("corporate", "bank", "sovereign"):
            # Corporate/Sovereign/Bank formula: rho between 0.12 and 0.24
            rho = 0.12 * ((1.0 - decay) / (1.0 - math.exp(-50.0))) + 0.24 * (1.0 - (1.0 - decay) / (1.0 - math.exp(-50.0)))
        elif asset_class.lower() == "retail_mortgage":
            # Retail residential mortgage: constant 0.15
            rho = 0.15
        elif asset_class.lower() == "retail_revolving":
            # Retail qualifying revolving (credit cards): constant 0.04
            rho = 0.04
        else:
            # Default corporate
            rho = 0.12 * ((1.0 - decay) / (1.0 - math.exp(-50.0))) + 0.24 * (1.0 - (1.0 - decay) / (1.0 - math.exp(-50.0)))
            
        return float(rho)

    @staticmethod
    def maturity_adjustment(pd: float, maturity: float) -> float:
        """Calculates Basel maturity adjustment factor MA(M) for non-retail exposures."""
        pd_clamped = min(max(pd, 1e-6), 0.999)
        b = (0.11852 - 0.05478 * math.log(pd_clamped)) ** 2
        m_clamped = max(1.0, min(maturity, 5.0)) # Basel limits M to [1, 5]
        ma = (1.0 + (m_clamped - 2.5) * b) / (1.0 - 1.5 * b)
        return float(ma)

    @classmethod
    def compute_obligor_capital_charge(
        cls,
        pd: float,
        lgd: float,
        maturity: float = 1.0,
        asset_correlation: Optional[float] = None,
        confidence_level: float = 0.999,
        asset_class: str = "corporate"
    ) -> Dict[str, float]:
        """Calculates capital requirement K, RWA, and conditional default probability."""
        assert 0.0 < pd < 1.0, "PD must be in (0, 1)."
        assert 0.0 <= lgd <= 1.0, "LGD must be in [0, 1]."
        assert 0.5 < confidence_level < 1.0, "Confidence level must be in (0.5, 1)."

        rho = cls.basel_asset_correlation(pd, asset_class) if asset_correlation is None else asset_correlation
        rho = max(1e-4, min(rho, 0.999))

        inv_pd = norm_inv(pd)
        inv_q = norm_inv(confidence_level)
        
        # Gordy conditional default probability at quantile q
        conditional_pd = norm_cdf((inv_pd + math.sqrt(rho) * inv_q) / math.sqrt(1.0 - rho))
        
        # Maturity adjustment
        ma = cls.maturity_adjustment(pd, maturity) if asset_class.lower() in ("corporate", "bank", "sovereign") else 1.0

        # Expected Loss
        el = lgd * pd

        # Capital requirement K (Unexpected Loss)
        k = max(0.0, (lgd * conditional_pd - el) * ma)
        
        # Risk-Weighted Assets (RWA = K * 12.5)
        rwa_factor = k * 12.5

        return {
            "pd": pd,
            "lgd": lgd,
            "maturity": maturity,
            "asset_correlation": rho,
            "conditional_pd_q": conditional_pd,
            "maturity_adjustment": ma,
            "expected_loss": el,
            "capital_requirement_K": k,
            "rwa_factor": rwa_factor
        }

    @classmethod
    def compute_portfolio_capital(
        cls,
        exposures: List[Dict[str, Any]],
        confidence_level: float = 0.999
    ) -> Dict[str, Any]:
        """Aggregates portfolio capital using the ASRF exact additivity theorem."""
        total_ead = 0.0
        total_k_dollars = 0.0
        total_el_dollars = 0.0
        total_rwa_dollars = 0.0
        obligor_results = []

        for exp in exposures:
            ead = exp.get("ead", 1.0)
            pd = exp["pd"]
            lgd = exp["lgd"]
            mat = exp.get("maturity", 1.0)
            ac = exp.get("asset_class", "corporate")
            rho = exp.get("asset_correlation", None)

            res = cls.compute_obligor_capital_charge(
                pd=pd, lgd=lgd, maturity=mat, asset_correlation=rho,
                confidence_level=confidence_level, asset_class=ac
            )
            k = res["capital_requirement_K"]
            el = res["expected_loss"]
            rwa = res["rwa_factor"]

            total_ead += ead
            total_k_dollars += k * ead
            total_el_dollars += el * ead
            total_rwa_dollars += rwa * ead
            
            res_copy = dict(res)
            res_copy["ead"] = ead
            res_copy["capital_dollars"] = k * ead
            obligor_results.append(res_copy)

        portfolio_k_ratio = total_k_dollars / total_ead if total_ead > 0.0 else 0.0
        portfolio_el_ratio = total_el_dollars / total_ead if total_ead > 0.0 else 0.0

        return {
            "total_ead": total_ead,
            "total_capital_dollars": total_k_dollars,
            "total_expected_loss_dollars": total_el_dollars,
            "total_rwa_dollars": total_rwa_dollars,
            "portfolio_capital_ratio": portfolio_k_ratio,
            "portfolio_el_ratio": portfolio_el_ratio,
            "obligors_count": len(exposures),
            "obligor_breakdown": obligor_results
        }


# ==============================================================================
# Model 2: Jack L. Treynor & Kay K. Mazuy (1966) Quadratic Market Timing Engine
# ==============================================================================
class TreynorMazuyMarketTimingEngine:
    """Jack L. Treynor & Kay K. Mazuy (1966) Quadratic Market Timing Engine.
    
    Estimates portfolio manager skill by decomposing returns into:
    r_p,t - r_f,t = alpha + beta * (r_m,t - r_f,t) + gamma * (r_m,t - r_f,t)^2 + eps_t
    
    alpha: Stock selection skill (Jensen's alpha adjusted for timing).
    beta: Baseline systemic market beta.
    gamma: Market timing ability (gamma > 0 indicates convex timing capability, synthetic call option).
    """

    @staticmethod
    def estimate_timing_ability(
        portfolio_returns: np.ndarray,
        market_returns: np.ndarray,
        risk_free_rate: float = 0.0
    ) -> Dict[str, Any]:
        """Performs OLS estimation of the Treynor-Mazuy quadratic timing model."""
        assert len(portfolio_returns) == len(market_returns), "Returns length mismatch."
        T = len(portfolio_returns)
        assert T >= 15, "Insufficient sample size for quadratic regression (min 15)."

        # Excess returns
        r_p_excess = portfolio_returns - risk_free_rate
        r_m_excess = market_returns - risk_free_rate

        # Design matrix X: [1, r_m_excess, r_m_excess^2]
        X = np.column_stack([
            np.ones(T),
            r_m_excess,
            r_m_excess ** 2
        ])
        y = r_p_excess

        # OLS estimation: theta = (X'X)^-1 X'y
        XtX = X.T @ X
        if np.linalg.cond(XtX) > 1e12:
            theta = np.linalg.pinv(XtX) @ (X.T @ y)
        else:
            theta = np.linalg.solve(XtX, X.T @ y)

        alpha, beta, gamma = float(theta[0]), float(theta[1]), float(theta[2])

        # Residuals and statistics
        y_pred = X @ theta
        residuals = y - y_pred
        sse = float(np.sum(residuals ** 2))
        sst = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - sse / sst if sst > 1e-12 else 0.0

        degrees_of_freedom = max(1, T - 3)
        sigma2_eps = sse / degrees_of_freedom
        cov_theta = sigma2_eps * np.linalg.pinv(XtX)
        se_theta = np.sqrt(np.maximum(1e-14, np.diag(cov_theta)))

        t_alpha = alpha / se_theta[0]
        t_beta = beta / se_theta[1]
        t_gamma = gamma / se_theta[2]

        # Effective dynamic beta at +1 std and -1 std market move
        std_m = float(np.std(r_m_excess, ddof=1))
        beta_up = beta + 2.0 * gamma * std_m
        beta_down = beta - 2.0 * gamma * std_m

        return {
            "sample_size": T,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "se_alpha": float(se_theta[0]),
            "se_beta": float(se_theta[1]),
            "se_gamma": float(se_theta[2]),
            "t_alpha": float(t_alpha),
            "t_beta": float(t_beta),
            "t_gamma": float(t_gamma),
            "r_squared": float(r_squared),
            "residual_std": float(math.sqrt(sigma2_eps)),
            "market_std": std_m,
            "effective_beta_up": float(beta_up),
            "effective_beta_down": float(beta_down),
            "has_market_timing_skill": bool(gamma > 0.0 and t_gamma > 1.96)
        }


# ==============================================================================
# Model 3: Fulvio Corsi (2009) HAR-RV Realized Volatility Engine
# ==============================================================================
class CorsiHARRVVolatilityEngine:
    """Fulvio Corsi (2009) Heterogeneous Autoregressive Model of Realized Volatility (HAR-RV).
    
    Models multi-component volatility based on the Heterogeneous Market Hypothesis:
    Traders act on daily (d), weekly (w), and monthly (m) horizons.
    
    RV_{t+1}^(d) = c + beta_d * RV_t^(d) + beta_w * RV_t^(w) + beta_m * RV_t^(m) + eps_{t+1}
    where RV_t^(w) = (1/5) sum_{i=0}^4 RV_{t-i}, RV_t^(m) = (1/22) sum_{i=0}^21 RV_{t-i}.
    Includes jump decomposition HAR-RV-J (Andersen, Bollerslev, Diebold 2007).
    """

    @staticmethod
    def construct_har_features(
        rv_series: np.ndarray,
        bv_series: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """Constructs lagged daily, weekly, and monthly multi-scale features."""
        T = len(rv_series)
        assert T >= 35, "HAR-RV requires at least 35 daily observations (22 monthly lag + calibration)."

        # Target: RV_{t+1} starting from index 22 up to T-1
        # Lagged RV_t^(d) = RV_t
        # Lagged RV_t^(w) = mean(RV_{t-4:t+1})
        # Lagged RV_t^(m) = mean(RV_{t-21:t+1})

        rows = []
        targets = []
        extra_features = {}

        for t in range(21, T - 1):
            rv_d = rv_series[t]
            rv_w = float(np.mean(rv_series[t - 4:t + 1]))
            rv_m = float(np.mean(rv_series[t - 21:t + 1]))
            
            row = [1.0, rv_d, rv_w, rv_m]
            
            if bv_series is not None:
                # Continuous vs Jump components: J_t = max(0, RV_t - BV_t)
                c_d = min(rv_d, bv_series[t])
                j_d = max(0.0, rv_d - bv_series[t])
                row.append(j_d)

            rows.append(row)
            targets.append(rv_series[t + 1])

        X = np.array(rows, dtype=np.float64)
        y = np.array(targets, dtype=np.float64)
        return X, y, extra_features

    @classmethod
    def fit_har_model(
        cls,
        rv_series: np.ndarray,
        bv_series: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Fits OLS HAR-RV model and computes coefficients and goodness-of-fit."""
        X, y, _ = cls.construct_har_features(rv_series, bv_series)
        N = len(y)

        XtX = X.T @ X
        if np.linalg.cond(XtX) > 1e12:
            coeffs = np.linalg.pinv(XtX) @ (X.T @ y)
        else:
            coeffs = np.linalg.solve(XtX, X.T @ y)

        y_pred = X @ coeffs
        residuals = y - y_pred
        sse = float(np.sum(residuals ** 2))
        sst = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - sse / sst if sst > 1e-12 else 0.0
        rmse = math.sqrt(sse / N)

        # QLIKE loss: sum(y / y_pred - ln(y / y_pred) - 1)
        y_pred_safe = np.maximum(1e-8, y_pred)
        qlike = float(np.mean(y / y_pred_safe - np.log(y / y_pred_safe) - 1.0))

        results = {
            "n_observations": N,
            "c": float(coeffs[0]),
            "beta_daily": float(coeffs[1]),
            "beta_weekly": float(coeffs[2]),
            "beta_monthly": float(coeffs[3]),
            "r_squared": float(r_squared),
            "rmse": float(rmse),
            "qlike": float(qlike),
            "persistence_sum": float(coeffs[1] + coeffs[2] + coeffs[3])
        }

        if bv_series is not None:
            results["beta_jump"] = float(coeffs[4])

        return results

    @classmethod
    def predict_next_rv(
        cls,
        recent_rv: np.ndarray,
        model_params: Dict[str, Any],
        recent_bv: Optional[float] = None
    ) -> float:
        """Forecasts t+1 realized volatility using calibrated HAR parameters."""
        assert len(recent_rv) >= 22, "Need at least 22 most recent daily RVs."
        rv_d = recent_rv[-1]
        rv_w = float(np.mean(recent_rv[-5:]))
        rv_m = float(np.mean(recent_rv[-22:]))

        pred = (
            model_params["c"]
            + model_params["beta_daily"] * rv_d
            + model_params["beta_weekly"] * rv_w
            + model_params["beta_monthly"] * rv_m
        )

        if "beta_jump" in model_params and recent_bv is not None:
            jump = max(0.0, rv_d - recent_bv)
            pred += model_params["beta_jump"] * jump

        return max(1e-8, float(pred))


# ==============================================================================
# Model 4: Tarun Chordia, Richard Roll & Avanidhar Subrahmanyam (2000, 2002) Order Imbalance Engine
# ==============================================================================
class ChordiaRollSubrahmanyamOIBEngine:
    """Tarun Chordia, Richard Roll & Avanidhar Subrahmanyam (CRS 2000, 2002) Order Imbalance Engine.
    
    Investigates market microstructure liquidity dynamics:
    - Daily buyer-initiated volume V_B and seller-initiated volume V_S.
    - Normalized Order Imbalance: OIB_t = (V_B,t - V_S,t) / (V_B,t + V_S,t) in [-1, +1].
    - Contemporaneous Price Impact: R_t = a_0 + a_1 * OIB_t + a_2 * OIB_{t-1} + a_3 * R_{t-1} + eps_t.
    - Market Maker Inventory Reversal: a_1 > 0 (buying pressure drives up prices),
      a_2 < 0 (inventory mean-reversion).
    - Commonality in Liquidity: OIB_{i,t} sensitivity to market-wide OIB_m,t.
    """

    @staticmethod
    def compute_order_imbalance_series(
        buy_volumes: np.ndarray,
        sell_volumes: np.ndarray
    ) -> np.ndarray:
        """Calculates normalized order imbalance OIB_t in [-1, 1]."""
        assert len(buy_volumes) == len(sell_volumes), "Volume lengths mismatch."
        total_vol = buy_volumes + sell_volumes
        safe_total = np.where(total_vol > 1e-12, total_vol, 1.0)
        oib = (buy_volumes - sell_volumes) / safe_total
        return np.clip(oib, -1.0, 1.0)

    @classmethod
    def fit_order_imbalance_impact_regression(
        cls,
        returns: np.ndarray,
        oib_series: np.ndarray
    ) -> Dict[str, Any]:
        """Estimates contemporaneous and lagged order imbalance impact on asset returns."""
        assert len(returns) == len(oib_series), "Lengths mismatch."
        T = len(returns)
        assert T >= 20, "Need at least 20 observations for OIB time-series regression."

        # Dependent variable: R_t (t=1..T-1)
        # Regressors: [1, OIB_t, OIB_{t-1}, R_{t-1}]
        y = returns[1:]
        X = np.column_stack([
            np.ones(T - 1),
            oib_series[1:],
            oib_series[:-1],
            returns[:-1]
        ])

        XtX = X.T @ X
        coeffs = np.linalg.pinv(XtX) @ (X.T @ y)

        a0, a1_contemp, a2_lagged, a3_ar1 = coeffs[0], coeffs[1], coeffs[2], coeffs[3]

        residuals = y - (X @ coeffs)
        sse = float(np.sum(residuals ** 2))
        sst = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - sse / sst if sst > 1e-12 else 0.0

        dof = max(1, T - 1 - 4)
        sigma2 = sse / dof
        se = np.sqrt(np.maximum(1e-14, np.diag(sigma2 * np.linalg.pinv(XtX))))

        t_contemp = a1_contemp / se[1]
        t_lagged = a2_lagged / se[2]

        return {
            "sample_size": T - 1,
            "intercept": float(a0),
            "contemporaneous_impact_a1": float(a1_contemp),
            "t_contemporaneous": float(t_contemp),
            "lagged_inventory_reversal_a2": float(a2_lagged),
            "t_lagged": float(t_lagged),
            "ar1_return_coeff_a3": float(a3_ar1),
            "r_squared": float(r2),
            "has_price_impact": bool(a1_contemp > 0 and t_contemp > 1.96),
            "has_inventory_reversal": bool(a2_lagged < 0 and t_lagged < -1.645)
        }

    @classmethod
    def estimate_commonality_in_liquidity(
        cls,
        stock_oib: np.ndarray,
        market_oib: np.ndarray
    ) -> Dict[str, float]:
        """Calculates commonality in liquidity beta: OIB_i,t = alpha + beta_m * OIB_m,t + eps_t."""
        assert len(stock_oib) == len(market_oib), "Series length mismatch."
        T = len(stock_oib)
        X = np.column_stack([np.ones(T), market_oib])
        y = stock_oib

        coeffs = np.linalg.pinv(X.T @ X) @ (X.T @ y)
        alpha, beta_comm = coeffs[0], coeffs[1]

        y_pred = X @ coeffs
        residuals = y - y_pred
        r2 = 1.0 - np.sum(residuals ** 2) / np.sum((y - np.mean(y)) ** 2)

        return {
            "commonality_beta": float(beta_comm),
            "alpha": float(alpha),
            "r_squared": float(r2)
        }


# ==============================================================================
# Model 5: Ivo Welch & Amit Goyal (2008) Return Predictability Benchmark Engine
# ==============================================================================
class WelchGoyalPredictabilityEngine:
    """Ivo Welch & Amit Goyal (2008) Out-of-Sample Return Predictability Benchmark Engine.
    
    Evaluates whether predictive regressions r_{t+1}^e = a + b * x_t beat the naive Historical Average (HA).
    Computes Out-of-Sample R^2:
    R^2_OOS = 1 - sum_{t=T_0}^{T-1} (r_{t+1}^e - r_hat_{t+1}^e)^2 / sum_{t=T_0}^{T-1} (r_{t+1}^e - r_bar_{t+1}^e)^2
    
    Includes Campbell & Thompson (2008) Economic Constraints:
    - Sign constraint on slope (b >= 0)
    - Positivity constraint on expected equity premium (r_hat >= 0)
    """

    @classmethod
    def evaluate_oos_predictability(
        cls,
        excess_returns: np.ndarray,
        predictor: np.ndarray,
        initial_burnin: int = 30,
        apply_campbell_thompson_constraints: bool = True
    ) -> Dict[str, Any]:
        """Runs rolling/expanding window out-of-sample predictability evaluation."""
        assert len(excess_returns) == len(predictor), "Lengths mismatch."
        T = len(excess_returns)
        assert T > initial_burnin + 10, "Insufficient observations beyond burn-in."

        forecasts_model = []
        forecasts_ha = []
        actuals = []

        # Expanding window evaluation
        for t in range(initial_burnin, T - 1):
            y_train = excess_returns[1:t + 1]
            x_train = predictor[:t]

            # 1. Historical Average benchmark: mean of past excess returns
            ha_forecast = float(np.mean(y_train))

            # 2. Predictive model OLS: y_{s+1} = a + b * x_s
            X_mat = np.column_stack([np.ones(len(x_train)), x_train])
            coeffs = np.linalg.pinv(X_mat.T @ X_mat) @ (X_mat.T @ y_train)
            a, b = coeffs[0], coeffs[1]

            # Campbell-Thompson sign restriction
            if apply_campbell_thompson_constraints and b < 0.0:
                b = 0.0
                a = float(np.mean(y_train))

            model_forecast = a + b * predictor[t]

            # Campbell-Thompson positivity restriction: equity premium >= 0
            if apply_campbell_thompson_constraints:
                model_forecast = max(0.0, model_forecast)

            actual_next = excess_returns[t + 1]

            forecasts_model.append(model_forecast)
            forecasts_ha.append(ha_forecast)
            actuals.append(actual_next)

        y_actual = np.array(actuals)
        y_model = np.array(forecasts_model)
        y_ha = np.array(forecasts_ha)

        mspe_model = float(np.mean((y_actual - y_model) ** 2))
        mspe_ha = float(np.mean((y_actual - y_ha) ** 2))

        # Out-of-sample R^2
        r2_oos = 1.0 - mspe_model / mspe_ha if mspe_ha > 1e-14 else 0.0

        # Clark & West (2007) adjusted MSPE test statistic for nested models
        f_stat_cw = (y_actual - y_ha) ** 2 - ((y_actual - y_model) ** 2 - (y_ha - y_model) ** 2)
        cw_stat = float(np.mean(f_stat_cw) / (np.std(f_stat_cw, ddof=1) / math.sqrt(len(f_stat_cw))))

        return {
            "evaluation_periods": len(y_actual),
            "mspe_model": mspe_model,
            "mspe_historical_average": mspe_ha,
            "r2_oos": float(r2_oos),
            "r2_oos_percentage": float(r2_oos * 100.0),
            "clark_west_statistic": cw_stat,
            "outperforms_historical_average": bool(r2_oos > 0.0),
            "statistically_significant_cw": bool(cw_stat > 1.645)
        }


# ==============================================================================
# Model 6: Wayne E. Ferson & Campbell R. Harvey (1991, 1993) Conditional Beta Engine
# ==============================================================================
class FersonHarveyConditionalBetaEngine:
    """Wayne E. Ferson & Campbell R. Harvey (1991, 1993) Conditional Asset Pricing Engine.
    
    Models time-varying beta as an affine function of macroeconomic state variables Z_{t-1}:
    beta_i(Z_{t-1}) = b_{i,0} + b_{i,1}' * Z_{t-1}
    
    Full conditional empirical specification:
    r_{i,t}^e = alpha_{i,0} + alpha_{i,1}' * Z_{t-1} + b_{i,0} * r_{m,t}^e + b_{i,1}' * (Z_{t-1} * r_{m,t}^e) + eps_{i,t}
    
    Tests whether return predictability originates from time-varying risk betas or dynamic macro premiums.
    """

    @classmethod
    def fit_conditional_beta_model(
        cls,
        asset_excess_returns: np.ndarray,
        market_excess_returns: np.ndarray,
        macro_state_variables: np.ndarray
    ) -> Dict[str, Any]:
        """Estimates conditional multi-beta model with macroeconomic instruments."""
        assert len(asset_excess_returns) == len(market_excess_returns), "Lengths mismatch."
        assert len(asset_excess_returns) == len(macro_state_variables), "Instruments length mismatch."
        T = len(asset_excess_returns)
        assert T >= 25, "Need at least 25 observations for conditional model."

        if macro_state_variables.ndim == 1:
            macro_state_variables = macro_state_variables.reshape(-1, 1)

        K_vars = macro_state_variables.shape[1]

        # Interaction terms: Z_{t-1} * r_{m,t}
        interactions = macro_state_variables * market_excess_returns.reshape(-1, 1)

        # Regressors: [1, Z, r_m, Z * r_m]
        X = np.column_stack([
            np.ones(T),
            macro_state_variables,
            market_excess_returns,
            interactions
        ])
        y = asset_excess_returns

        XtX = X.T @ X
        coeffs = np.linalg.pinv(XtX) @ (X.T @ y)

        alpha_0 = float(coeffs[0])
        alpha_macro = coeffs[1:1 + K_vars]
        beta_0 = float(coeffs[1 + K_vars])
        beta_macro = coeffs[1 + K_vars + 1:]

        residuals = y - (X @ coeffs)
        sse = float(np.sum(residuals ** 2))
        sst = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - sse / sst if sst > 1e-12 else 0.0

        # Unconditional static CAPM comparison
        X_static = np.column_stack([np.ones(T), market_excess_returns])
        coeffs_static = np.linalg.pinv(X_static.T @ X_static) @ (X_static.T @ y)
        res_static = y - (X_static @ coeffs_static)
        r2_static = 1.0 - np.sum(res_static ** 2) / sst if sst > 1e-12 else 0.0

        # Time series of conditional betas: beta_t = beta_0 + sum(beta_macro_k * Z_k,t)
        conditional_betas = beta_0 + macro_state_variables @ beta_macro

        return {
            "sample_size": T,
            "n_instruments": K_vars,
            "static_beta": float(coeffs_static[1]),
            "static_alpha": float(coeffs_static[0]),
            "static_r2": float(r2_static),
            "conditional_base_beta_b0": beta_0,
            "beta_macro_interaction_coefficients": [float(b) for b in beta_macro],
            "alpha_0": alpha_0,
            "conditional_r2": float(r2),
            "r2_improvement": float(r2 - r2_static),
            "conditional_beta_mean": float(np.mean(conditional_betas)),
            "conditional_beta_std": float(np.std(conditional_betas, ddof=1)),
            "conditional_beta_min": float(np.min(conditional_betas)),
            "conditional_beta_max": float(np.max(conditional_betas)),
            "has_significant_time_varying_beta": bool(np.std(conditional_betas, ddof=1) > 0.05)
        }


# ==============================================================================
# Pytest Verification Suites (Agentic TDD)
# ==============================================================================
def test_gordy_asrf_credit_capital_engine():
    """Verifies Gordy (2003) ASRF Basel Credit Capital Engine."""
    engine = GordyASRFCreditCapitalEngine

    # Single obligor: corporate with PD=1%, LGD=45%, M=2.5 years
    res = engine.compute_obligor_capital_charge(pd=0.01, lgd=0.45, maturity=2.5, confidence_level=0.999)
    assert 0.12 <= res["asset_correlation"] <= 0.24, "Corporate asset correlation must adhere to Basel bounds."
    assert res["conditional_pd_q"] > 0.01, "99.9% systemic quantile PD must exceed unconditional PD."
    assert 0.0 < res["capital_requirement_K"] < 1.0, "Capital requirement must be bounded and positive."
    assert res["rwa_factor"] == pytest.approx(res["capital_requirement_K"] * 12.5, rel=1e-5)

    # Monotonicity test: higher PD leads to higher conditional PD and higher capital
    res_high_pd = engine.compute_obligor_capital_charge(pd=0.05, lgd=0.45, maturity=2.5)
    assert res_high_pd["conditional_pd_q"] > res["conditional_pd_q"]
    assert res_high_pd["capital_requirement_K"] > res["capital_requirement_K"]

    # Portfolio aggregation test
    portfolio = [
        {"ead": 1000000.0, "pd": 0.005, "lgd": 0.40, "maturity": 1.0, "asset_class": "corporate"},
        {"ead": 2500000.0, "pd": 0.020, "lgd": 0.45, "maturity": 3.0, "asset_class": "corporate"},
        {"ead": 500000.0, "pd": 0.010, "lgd": 0.20, "maturity": 1.0, "asset_class": "retail_mortgage"}
    ]
    port_res = engine.compute_portfolio_capital(portfolio)
    assert port_res["total_ead"] == 4000000.0
    assert port_res["total_capital_dollars"] > 0.0
    assert port_res["total_rwa_dollars"] == pytest.approx(port_res["total_capital_dollars"] * 12.5, rel=1e-5)
    assert len(port_res["obligor_breakdown"]) == 3


def test_treynor_mazuy_market_timing_engine():
    """Verifies Treynor & Mazuy (1966) Quadratic Timing Regression Engine."""
    np.random.seed(42)
    T = 120
    market_returns = np.random.normal(0.008, 0.045, T)
    
    # Simulate a successful market timer with gamma = 1.8 > 0
    true_alpha = 0.002
    true_beta = 0.95
    true_gamma = 1.8
    noise = np.random.normal(0.0, 0.01, T)
    portfolio_returns = true_alpha + true_beta * market_returns + true_gamma * (market_returns ** 2) + noise

    res = TreynorMazuyMarketTimingEngine.estimate_timing_ability(portfolio_returns, market_returns)
    assert abs(res["beta"] - true_beta) < 0.15
    assert abs(res["gamma"] - true_gamma) < 0.50
    assert res["gamma"] > 0.0
    assert res["has_market_timing_skill"] is True
    assert res["effective_beta_up"] > res["effective_beta_down"]
    assert res["r_squared"] > 0.85


def test_corsi_har_rv_volatility_engine():
    """Verifies Corsi (2009) HAR-RV Multi-Scale Realized Volatility Engine."""
    np.random.seed(123)
    T = 200
    # Simulate realistic persistent realized variance series
    base_rv = 0.00015
    rv_sim = [base_rv]
    for _ in range(1, T):
        past_w = np.mean(rv_sim[-5:]) if len(rv_sim) >= 5 else rv_sim[-1]
        past_m = np.mean(rv_sim[-22:]) if len(rv_sim) >= 22 else past_w
        rv_next = 0.05 * base_rv + 0.45 * rv_sim[-1] + 0.30 * past_w + 0.20 * past_m + np.random.normal(0, 0.000008)
        rv_sim.append(max(1e-6, rv_next))
    rv_arr = np.array(rv_sim)

    fit_res = CorsiHARRVVolatilityEngine.fit_har_model(rv_arr)
    assert fit_res["beta_daily"] > 0.0
    assert fit_res["r_squared"] > 0.30
    assert fit_res["rmse"] > 0.0
    assert 0.6 < fit_res["persistence_sum"] < 1.05

    # Test out-of-sample prediction
    pred = CorsiHARRVVolatilityEngine.predict_next_rv(rv_arr[-25:], fit_res)
    assert pred > 0.0
    assert abs(pred - rv_arr[-1]) < 0.0002


def test_chordia_roll_subrahmanyam_oib_engine():
    """Verifies Chordia, Roll & Subrahmanyam (2000, 2002) Order Imbalance Engine."""
    np.random.seed(99)
    T = 150
    buys = np.random.uniform(50000, 150000, T)
    sells = np.random.uniform(50000, 150000, T)

    oib = ChordiaRollSubrahmanyamOIBEngine.compute_order_imbalance_series(buys, sells)
    assert len(oib) == T
    assert np.all(oib >= -1.0) and np.all(oib <= 1.0)

    # Simulate price dynamics driven by OIB: positive contemporaneous, negative lagged reversal
    returns = 0.0002 + 0.015 * oib - 0.008 * np.roll(oib, 1) + np.random.normal(0, 0.004, T)
    res = ChordiaRollSubrahmanyamOIBEngine.fit_order_imbalance_impact_regression(returns, oib)
    
    assert res["contemporaneous_impact_a1"] > 0.0
    assert res["t_contemporaneous"] > 2.0
    assert res["lagged_inventory_reversal_a2"] < 0.0
    assert res["has_price_impact"] is True

    # Commonality in liquidity test
    market_oib = oib + np.random.normal(0, 0.1, T)
    comm_res = ChordiaRollSubrahmanyamOIBEngine.estimate_commonality_in_liquidity(oib, market_oib)
    assert comm_res["commonality_beta"] > 0.5


def test_welch_goyal_predictability_engine():
    """Verifies Welch & Goyal (2008) OOS Return Predictability Benchmark Engine."""
    np.random.seed(77)
    T = 100
    # Dividend-yield style persistent predictor
    x = [0.035]
    for _ in range(1, T):
        x.append(0.002 + 0.94 * x[-1] + np.random.normal(0, 0.002))
    x_arr = np.array(x)

    # Returns with modest predictability
    returns = 0.005 + 0.25 * x_arr + np.random.normal(0, 0.03, T)

    res = WelchGoyalPredictabilityEngine.evaluate_oos_predictability(
        returns, x_arr, initial_burnin=40, apply_campbell_thompson_constraints=True
    )
    assert res["evaluation_periods"] == T - 40 - 1
    assert res["mspe_model"] > 0.0
    assert res["mspe_historical_average"] > 0.0
    assert "r2_oos" in res
    assert "clark_west_statistic" in res


def test_ferson_harvey_conditional_beta_engine():
    """Verifies Ferson & Harvey (1991, 1993) Conditional Multi-Beta Engine."""
    np.random.seed(55)
    T = 140
    market_excess = np.random.normal(0.007, 0.04, T)
    term_spread = np.random.normal(0.015, 0.008, T) # Macro instrument

    # True time-varying beta: beta(Z) = 0.8 + 15.0 * Z
    true_beta_t = 0.8 + 15.0 * term_spread
    asset_excess = 0.001 + true_beta_t * market_excess + np.random.normal(0, 0.012, T)

    res = FersonHarveyConditionalBetaEngine.fit_conditional_beta_model(
        asset_excess, market_excess, term_spread
    )
    assert abs(res["conditional_base_beta_b0"] - 0.8) < 0.25
    assert res["beta_macro_interaction_coefficients"][0] > 5.0
    assert res["conditional_r2"] > res["static_r2"]
    assert res["has_significant_time_varying_beta"] is True
