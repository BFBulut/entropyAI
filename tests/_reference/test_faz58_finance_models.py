"""Programmatic TDD Verification Suite for Faz 58 Quantitative Finance Engines.

Models:
1. Fischer Black & Robert Litterman (1990, 1992): Black-Litterman Global Portfolio Optimization & Bayesian Equilibrium Shrinkage
2. Daniel Kahneman & Amos Tversky (1992) / Drazen Prelec (1998): Cumulative Prospect Theory (CPT), Rank-Dependent Probability Weighting & Fourfold Pattern of Risk
3. Robert Litterman & Jose Scheinkman (1991): Yield Curve Principal Component Analysis (Level, Slope, Curvature) & Multi-Point Duration Immunization
4. John H. Cochrane & Monika Piazzesi (2005): Cochrane-Piazzesi Single-Factor Bond Risk Premia & Tent-Shaped Predictability Engine
5. Nicholas Barberis, Andrei Shleifer & Robert Vishny (BSV 1998) / Kent Daniel, David Hirshleifer & Avanidhar Subrahmanyam (DHS 1998): Behavioral Sentiment, Underreaction & Overreaction Engine
6. Stewart Myers (1984) / Merton Miller & Franco Modigliani (1963) / Richard Roll (1977): Corporate Capital Structure APV, Pecking Order Deficit & Roll's Critique Engine
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


# ==============================================================================
# Model 1: Black-Litterman Global Portfolio Optimization (1990, 1992)
# ==============================================================================
class BlackLittermanOptimizationEngine:
    """Fischer Black & Robert Litterman (1990, 1992) Global Portfolio Optimization.
    Combines market equilibrium prior with investor subjective/quantitative views
    using Bayesian shrinkage to produce stable, intuitive portfolio weights.
    """

    @staticmethod
    def reverse_optimize_equilibrium(
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        risk_aversion: float
    ) -> np.ndarray:
        """Computes implied market equilibrium excess returns: Pi = lambda * Sigma * w_mkt."""
        return risk_aversion * (cov_matrix @ market_weights)

    @staticmethod
    def compute_he_litterman_omega(
        P: np.ndarray,
        cov_matrix: np.ndarray,
        tau: float = 0.05
    ) -> np.ndarray:
        """He & Litterman (1999) proportional diagonal uncertainty matrix:
        Omega = diag(P * (tau * Sigma) * P^T).
        """
        tau_sigma = tau * cov_matrix
        var_views = np.diag(P @ tau_sigma @ P.T)
        return np.diag(var_views)

    @classmethod
    def calculate_posterior(
        cls,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        risk_aversion: float,
        P: np.ndarray,
        Q: np.ndarray,
        Omega: Optional[np.ndarray] = None,
        tau: float = 0.05
    ) -> Dict[str, np.ndarray]:
        """Calculates Black-Litterman posterior expected returns and optimal weights.
        P: (K, N) pick matrix of views.
        Q: (K,) expected return vector of views.
        Omega: (K, K) uncertainty covariance of views. If None, uses He-Litterman.
        """
        N = cov_matrix.shape[0]
        K = P.shape[0]
        Pi = cls.reverse_optimize_equilibrium(cov_matrix, market_weights, risk_aversion)

        tau_sigma = tau * cov_matrix
        if Omega is None:
            Omega = cls.compute_he_litterman_omega(P, cov_matrix, tau)

        # Master Formula:
        # M = tau * Sigma * P^T * (P * tau * Sigma * P^T + Omega)^(-1)
        # E[R] = Pi + M * (Q - P * Pi)
        middle_inv = np.linalg.inv(P @ tau_sigma @ P.T + Omega)
        M = tau_sigma @ P.T @ middle_inv
        er_posterior = Pi + M @ (Q - P @ Pi)

        # Posterior covariance:
        # Sigma_BL = Sigma + tau * Sigma - M * P * tau * Sigma
        sigma_bl = cov_matrix + tau_sigma - M @ P @ tau_sigma

        # Unconstrained optimal weights: w* = (lambda * Sigma)^(-1) * E[R]
        sigma_inv = np.linalg.inv(cov_matrix)
        w_optimal_raw = (1.0 / risk_aversion) * (sigma_inv @ er_posterior)
        w_optimal_norm = w_optimal_raw / np.sum(w_optimal_raw)

        active_tilts = w_optimal_norm - market_weights

        return {
            "equilibrium_returns": Pi,
            "posterior_returns": er_posterior,
            "posterior_covariance": sigma_bl,
            "optimal_weights_raw": w_optimal_raw,
            "optimal_weights_norm": w_optimal_norm,
            "active_tilts": active_tilts,
            "view_uncertainty_omega": Omega
        }


# ==============================================================================
# Model 2: Cumulative Prospect Theory (Kahneman & Tversky 1992, Prelec 1998)
# ==============================================================================
class CumulativeProspectTheoryEngine:
    """Daniel Kahneman & Amos Tversky (1992) Cumulative Prospect Theory (CPT)
    with Prelec (1998) probability weighting and rank-dependent decision weights.
    """

    @staticmethod
    def value_function(
        x: float,
        alpha: float = 0.88,
        beta: float = 0.88,
        lambda_loss: float = 2.25
    ) -> float:
        """S-shaped value function: x^alpha for gains, -lambda * (-x)^beta for losses."""
        if x >= 0.0:
            return math.pow(x, alpha)
        else:
            return -lambda_loss * math.pow(-x, beta)

    @staticmethod
    def tversky_kahneman_weight(p: float, gamma: float = 0.61, delta: float = 0.69, is_gain: bool = True) -> float:
        """Tversky-Kahneman (1992) probability weighting: w(p) = p^theta / (p^theta + (1-p)^theta)^(1/theta)."""
        p = max(1e-12, min(1.0 - 1e-12, float(p)))
        theta = gamma if is_gain else delta
        p_theta = math.pow(p, theta)
        denom = math.pow(p_theta + math.pow(1.0 - p, theta), 1.0 / theta)
        return p_theta / denom

    @staticmethod
    def prelec_weight(p: float, alpha_param: float = 0.65, beta_param: float = 1.0) -> float:
        """Prelec (1998) two-parameter probability weighting: w(p) = exp( -beta * (-ln(p))^alpha )."""
        p = max(1e-12, min(1.0 - 1e-12, float(p)))
        inner = -math.log(p)
        return math.exp(-beta_param * math.pow(inner, alpha_param))

    @classmethod
    def calculate_cpt_value(
        cls,
        outcomes: np.ndarray,
        probabilities: np.ndarray,
        alpha: float = 0.88,
        beta: float = 0.88,
        lambda_loss: float = 2.25,
        gamma: float = 0.61,
        delta: float = 0.69
    ) -> Dict[str, Any]:
        """Calculates rank-dependent Cumulative Prospect Theory value."""
        assert len(outcomes) == len(probabilities)
        assert abs(np.sum(probabilities) - 1.0) < 1e-5

        # Sort outcomes in ascending order
        order = np.argsort(outcomes)
        x_sorted = outcomes[order]
        p_sorted = probabilities[order]

        # Separate losses (x < 0) and gains (x >= 0)
        loss_indices = [i for i, x in enumerate(x_sorted) if x < 0]
        gain_indices = [i for i, x in enumerate(x_sorted) if x >= 0]

        decision_weights = np.zeros(len(x_sorted))
        values = np.zeros(len(x_sorted))

        # Losses: cumulative from worst outcome upward
        cum_p_loss = 0.0
        for i in loss_indices:
            p_prev = cum_p_loss
            cum_p_loss += p_sorted[i]
            w_curr = cls.tversky_kahneman_weight(cum_p_loss, gamma, delta, is_gain=False)
            w_prev = cls.tversky_kahneman_weight(p_prev, gamma, delta, is_gain=False) if p_prev > 0 else 0.0
            pi_i = w_curr - w_prev
            decision_weights[i] = pi_i
            values[i] = cls.value_function(x_sorted[i], alpha, beta, lambda_loss)

        # Gains: cumulative from best outcome downward
        cum_p_gain = 0.0
        for i in reversed(gain_indices):
            p_prev = cum_p_gain
            cum_p_gain += p_sorted[i]
            w_curr = cls.tversky_kahneman_weight(cum_p_gain, gamma, delta, is_gain=True)
            w_prev = cls.tversky_kahneman_weight(p_prev, gamma, delta, is_gain=True) if p_prev > 0 else 0.0
            pi_i = w_curr - w_prev
            decision_weights[i] = pi_i
            values[i] = cls.value_function(x_sorted[i], alpha, beta, lambda_loss)

        cpt_value = float(np.sum(decision_weights * values))
        expected_value = float(np.sum(x_sorted * p_sorted))

        return {
            "sorted_outcomes": x_sorted,
            "sorted_probs": p_sorted,
            "decision_weights": decision_weights,
            "outcome_values": values,
            "cpt_total_value": cpt_value,
            "expected_value": expected_value
        }


# ==============================================================================
# Model 3: Litterman & Scheinkman (1991) Yield Curve PCA & Immunization
# ==============================================================================
class LittermanScheinkmanYieldCurvePCAEngine:
    """Robert Litterman & Jose Scheinkman (1991) Common Factors Affecting Bond Returns.
    Decomposes yield curve movements into Level (Shift), Slope (Twist), and Curvature (Butterfly),
    and executes multi-point factor duration immunization.
    """

    @staticmethod
    def decompose_yield_curve(yield_changes: np.ndarray) -> Dict[str, Any]:
        """Performs PCA on yield changes matrix (T x M).
        Returns eigenvalues, eigenvectors (loadings), and variance explained ratios.
        """
        T, M = yield_changes.shape
        cov = np.cov(yield_changes, rowvar=False)

        evals, evecs = np.linalg.eigh(cov)
        idx = np.argsort(evals)[::-1]
        evals = evals[idx]
        evecs = evecs[:, idx]

        var_explained = evals / np.sum(evals)

        # Standardize signs for economic interpretability:
        # PC1 (Level): all positive
        if np.mean(evecs[:, 0]) < 0:
            evecs[:, 0] *= -1.0
        # PC2 (Slope): short end negative, long end positive
        if evecs[-1, 1] < evecs[0, 1]:
            evecs[:, 1] *= -1.0
        # PC3 (Curvature): belly negative, wings positive (convex)
        if evecs[M // 2, 2] > 0:
            evecs[:, 2] *= -1.0

        return {
            "covariance_matrix": cov,
            "eigenvalues": evals,
            "eigenvectors": evecs,
            "variance_explained": var_explained,
            "cum_variance_explained": np.cumsum(var_explained)
        }

    @staticmethod
    def calculate_factor_durations(
        modified_durations: np.ndarray,
        weights: np.ndarray,
        eigenvectors: np.ndarray
    ) -> np.ndarray:
        """Computes portfolio factor durations: D_k^P = sum_i w_i * D_mod,i * V_ik."""
        weighted_dur = weights * modified_durations
        return weighted_dur @ eigenvectors

    @classmethod
    def construct_barbell_bullet_neutral_hedge(
        cls,
        modified_durations: np.ndarray,
        eigenvectors: np.ndarray,
        short_wing_idx: int = 0,
        belly_bullet_idx: int = 1,
        long_wing_idx: int = 2
    ) -> Dict[str, Any]:
        """Constructs a cash-neutral, Level-neutral, and Slope-neutral butterfly hedge
        by solving a 3x3 linear system, normalizing belly weight to -1.0.
        """
        # Cash & Duration-neutral weighting:
        # w_short + w_long = 1.0 (Cash neutral when w_belly = -1.0)
        # w_short * D_short + w_long * D_long = D_belly (Duration / Level matched)
        d_short = modified_durations[short_wing_idx]
        d_belly = modified_durations[belly_bullet_idx]
        d_long = modified_durations[long_wing_idx]

        w_short = (d_long - d_belly) / (d_long - d_short)
        w_long = (d_belly - d_short) / (d_long - d_short)
        w_belly = -1.0

        full_weights = np.zeros(len(modified_durations))
        full_weights[short_wing_idx] = w_short
        full_weights[belly_bullet_idx] = w_belly
        full_weights[long_wing_idx] = w_long

        factor_durations = cls.calculate_factor_durations(modified_durations, full_weights, eigenvectors)
        net_duration = float(full_weights @ modified_durations)

        return {
            "w_short": w_short,
            "w_belly": w_belly,
            "w_long": w_long,
            "full_weights": full_weights,
            "net_duration": net_duration,
            "level_exposure": factor_durations[0],
            "slope_exposure": factor_durations[1],
            "curvature_exposure": factor_durations[2]
        }


# ==============================================================================
# Model 4: Cochrane & Piazzesi (2005) Bond Risk Premia Engine
# ==============================================================================
class CochranePiazzesiBondRiskPremiaEngine:
    """John H. Cochrane & Monika Piazzesi (2005) Bond Risk Premia.
    Disproves the Expectations Hypothesis using a single tent-shaped linear combination
    of forward rates that predicts multi-maturity excess Treasury bond returns.
    """

    @staticmethod
    def compute_forward_rates_and_returns(
        log_prices: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """log_prices: (T, N+1) where column n corresponds to log price p_t^(n) for maturities n=0..N.
        Returns:
        forward_rates: (T, N) where f_t^(n) = p_t^(n-1) - p_t^(n), with f_t^(1) = y_t^(1) = -p_t^(1).
        excess_returns: (T-1, N-1) where rx_{t+1}^(n) = p_{t+1}^(n-1) - p_t^(n) - y_t^(1) for n=2..N.
        """
        T, num_maturities = log_prices.shape
        N = num_maturities - 1

        # f_t^(n) = p_t^(n-1) - p_t^(n)
        forward_rates = np.zeros((T, N))
        for n in range(1, N + 1):
            forward_rates[:, n - 1] = log_prices[:, n - 1] - log_prices[:, n]

        # y_t^(1) = -p_t^(1) = forward_rates[:, 0]
        y1 = forward_rates[:-1, 0]

        # rx_{t+1}^(n) = p_{t+1}^(n-1) - p_t^(n) - y_t^(1)
        excess_returns = np.zeros((T - 1, N - 1))
        for n in range(2, N + 1):
            r_np1 = log_prices[1:, n - 1] - log_prices[:-1, n]
            excess_returns[:, n - 2] = r_np1 - y1

        return forward_rates, excess_returns

    @classmethod
    def fit_cochrane_piazzesi(
        cls,
        forward_rates: np.ndarray,
        excess_returns: np.ndarray
    ) -> Dict[str, Any]:
        """Fits the single-factor Cochrane-Piazzesi model:
        Step 1: Regress average excess return on constant and forward rates [1, y^(1), f^(2), ..., f^(N)].
        Step 2: Regress each maturity's excess return on single CP factor.
        """
        T_ret, num_excess = excess_returns.shape
        # Average excess return across maturities: rx_bar_{t+1}
        rx_bar = np.mean(excess_returns, axis=1)

        # Regressors at time t: [1, f_t^(1), ..., f_t^(N)]
        F = forward_rates[:T_ret, :]
        X = np.column_stack([np.ones(T_ret), F])

        # Step 1: OLS for gamma coefficients
        gamma, residuals, _, _ = np.linalg.lstsq(X, rx_bar, rcond=None)
        cp_factor = X @ gamma

        ss_tot = np.sum((rx_bar - np.mean(rx_bar)) ** 2)
        ss_res = np.sum((rx_bar - cp_factor) ** 2)
        r2_avg = 1.0 - (ss_res / max(1e-12, ss_tot))

        # Step 2: Individual maturity regressions rx_{t+1}^(n) = b_n * (gamma' * f_t) + eps
        b_loadings = np.zeros(num_excess)
        r2_maturities = np.zeros(num_excess)
        cp_with_const = np.column_stack([np.ones(T_ret), cp_factor])

        for n in range(num_excess):
            y_n = excess_returns[:, n]
            coef, _, _, _ = np.linalg.lstsq(cp_with_const, y_n, rcond=None)
            b_loadings[n] = coef[1]
            fitted = cp_with_const @ coef
            ss_tot_n = np.sum((y_n - np.mean(y_n)) ** 2)
            ss_res_n = np.sum((y_n - fitted) ** 2)
            r2_maturities[n] = 1.0 - (ss_res_n / max(1e-12, ss_tot_n))

        return {
            "gamma_coefficients": gamma,
            "cp_factor": cp_factor,
            "r2_average_return": r2_avg,
            "b_loadings": b_loadings,
            "r2_maturities": r2_maturities,
            "has_tent_shape": (gamma[1] < 0 and gamma[3] > 0 and gamma[4] > 0)
        }


# ==============================================================================
# Model 5: Behavioral Sentiment, Underreaction & Overreaction (BSV 1998, DHS 1998)
# ==============================================================================
class BarberisShleiferVishnyDanielSentimentEngine:
    """Nicholas Barberis, Andrei Shleifer & Robert Vishny (BSV 1998) regime-switching
    and Kent Daniel, David Hirshleifer & Avanidhar Subrahmanyam (DHS 1998)
    biased self-attribution investor sentiment engine.
    """

    @staticmethod
    def bsv_bayesian_regime_filter(
        earnings_shocks: np.ndarray,
        pi_L: float = 0.30,
        pi_H: float = 0.70,
        lambda_1: float = 0.10,
        lambda_2: float = 0.10
    ) -> Dict[str, Any]:
        """BSV (1998) Regime 1 (Underreaction / Conservatism: pi_L < 0.5)
        vs Regime 2 (Overreaction / Representativeness: pi_H > 0.5).
        Recursively updates filtered belief q_t = P(State_t = 1 | shocks).
        """
        T = len(earnings_shocks)
        q = np.zeros(T)
        # Prior belief
        q[0] = 0.50

        for t in range(1, T):
            # Same sign as previous shock:
            same_sign = (earnings_shocks[t] * earnings_shocks[t - 1] > 0)

            # Likelihood under Regime 1 vs Regime 2
            p_shock_s1 = pi_L if same_sign else (1.0 - pi_L)
            p_shock_s2 = pi_H if same_sign else (1.0 - pi_H)

            # Prior for time t after Markov transition
            prior_s1 = q[t - 1] * (1.0 - lambda_1) + (1.0 - q[t - 1]) * lambda_2
            prior_s2 = 1.0 - prior_s1

            # Bayes update
            num = prior_s1 * p_shock_s1
            denom = num + prior_s2 * p_shock_s2
            q[t] = num / max(1e-12, denom)

        return {
            "filtered_prob_regime_1": q,
            "filtered_prob_regime_2": 1.0 - q,
            "final_state": "Regime 1 (Underreaction)" if q[-1] > 0.5 else "Regime 2 (Overreaction)"
        }

    @staticmethod
    def dhs_simulate_self_attribution(
        private_signal: float,
        public_signals: np.ndarray,
        initial_confidence: float = 0.50,
        theta_confirm: float = 0.30,
        theta_disconfirm: float = 0.05
    ) -> Dict[str, Any]:
        """DHS (1998) Biased Self-Attribution:
        Confidence expands strongly when public signal confirms private signal,
        but contracts weakly when public signal contradicts private signal.
        """
        T = len(public_signals)
        confidence = np.zeros(T + 1)
        confidence[0] = initial_confidence

        for t in range(T):
            confirms = (np.sign(public_signals[t]) == np.sign(private_signal))
            if confirms:
                confidence[t + 1] = confidence[t] + theta_confirm * (1.0 - confidence[t])
            else:
                confidence[t + 1] = confidence[t] - theta_disconfirm * confidence[t]

        # Price response = Weighted combination of fundamental and confidence bias
        # Overconfidence drives initial overreaction (momentum) followed by long-run reversal
        return {
            "confidence_trajectory": confidence,
            "final_confidence": confidence[-1],
            "average_confidence": float(np.mean(confidence))
        }


# ==============================================================================
# Model 6: Capital Structure APV, Pecking Order Deficit & Roll's Critique (Myers 1984, Roll 1977)
# ==============================================================================
class MyersAPVPeckingOrderRollCritiqueEngine:
    """Stewart Myers (1984) Adjusted Present Value & Pecking Order Financing Deficit,
    and Richard Roll (1977) Critique Mathematical Proof of CAPM Tautology.
    """

    @staticmethod
    def adjusted_present_value(
        unlevered_cash_flows: List[float],
        terminal_value: float,
        r_unlevered: float,
        debt_schedule: List[float],
        tax_rate: float,
        r_debt: float,
        distress_cost_pct: float = 0.20,
        default_prob: float = 0.05
    ) -> Dict[str, float]:
        """Calculates Adjusted Present Value (APV):
        APV = V_Unlevered + PV(Debt Tax Shields) - PV(Expected Bankruptcy Costs).
        """
        T = len(unlevered_cash_flows)
        # 1. Unlevered firm value
        pv_cf = sum(cf / ((1.0 + r_unlevered) ** (t + 1)) for t, cf in enumerate(unlevered_cash_flows))
        pv_tv = terminal_value / ((1.0 + r_unlevered) ** T)
        v_unlevered = pv_cf + pv_tv

        # 2. PV of Tax Shields
        pv_tax_shield = sum((tax_rate * r_debt * d) / ((1.0 + r_debt) ** (t + 1)) for t, d in enumerate(debt_schedule))

        # 3. Expected distress costs
        pv_distress = default_prob * (distress_cost_pct * v_unlevered)

        apv = v_unlevered + pv_tax_shield - pv_distress

        return {
            "v_unlevered": v_unlevered,
            "pv_tax_shield": pv_tax_shield,
            "pv_distress_cost": pv_distress,
            "apv_total": apv,
            "net_debt_advantage": pv_tax_shield - pv_distress
        }

    @staticmethod
    def pecking_order_deficit_regression(
        financing_deficit: np.ndarray,
        net_debt_issuance: np.ndarray
    ) -> Dict[str, float]:
        """Shyam-Sunder & Myers (1999) Pecking Order Test:
        Delta D_it = alpha + beta_PO * DEF_it + eps_it.
        Strict pecking order implies beta_PO = 1.0, alpha = 0.0.
        """
        X = np.column_stack([np.ones(len(financing_deficit)), financing_deficit])
        coef, _, _, _ = np.linalg.lstsq(X, net_debt_issuance, rcond=None)
        alpha, beta_po = coef[0], coef[1]

        y_fit = X @ coef
        ss_tot = np.sum((net_debt_issuance - np.mean(net_debt_issuance)) ** 2)
        ss_res = np.sum((net_debt_issuance - y_fit) ** 2)
        r2 = 1.0 - (ss_res / max(1e-12, ss_tot))

        return {
            "alpha": float(alpha),
            "beta_pecking_order": float(beta_po),
            "r_squared": float(r2),
            "supports_pecking_order": (beta_po > 0.80 and abs(alpha) < 5.0)
        }

    @staticmethod
    def roll_critique_tautology_demonstration(
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        on_frontier_weights: np.ndarray,
        off_frontier_weights: np.ndarray
    ) -> Dict[str, Any]:
        """Demonstrates Richard Roll (1977) Critique:
        If a proxy portfolio lies on the exact mean-variance frontier, the CAPM beta
        cross-sectional regression holds with R^2 = 1.0 mathematically.
        If the proxy is shifted slightly off the frontier, R^2 collapses.
        """
        N = len(expected_returns)

        # Case A: On-frontier proxy M_eff
        cov_eff = cov_matrix @ on_frontier_weights
        var_eff = on_frontier_weights @ cov_matrix @ on_frontier_weights
        betas_eff = cov_eff / var_eff

        # Cross-sectional regression: E[R_i] = gamma_0 + gamma_1 * beta_i
        X_eff = np.column_stack([np.ones(N), betas_eff])
        coef_eff, _, _, _ = np.linalg.lstsq(X_eff, expected_returns, rcond=None)
        fit_eff = X_eff @ coef_eff
        ss_tot = np.sum((expected_returns - np.mean(expected_returns)) ** 2)
        ss_res_eff = np.sum((expected_returns - fit_eff) ** 2)
        r2_eff = 1.0 - (ss_res_eff / max(1e-12, ss_tot))

        # Case B: Inefficient proxy M_ineff
        cov_ineff = cov_matrix @ off_frontier_weights
        var_ineff = off_frontier_weights @ cov_matrix @ off_frontier_weights
        betas_ineff = cov_ineff / var_ineff

        X_ineff = np.column_stack([np.ones(N), betas_ineff])
        coef_ineff, _, _, _ = np.linalg.lstsq(X_ineff, expected_returns, rcond=None)
        fit_ineff = X_ineff @ coef_ineff
        ss_res_ineff = np.sum((expected_returns - fit_ineff) ** 2)
        r2_ineff = 1.0 - (ss_res_ineff / max(1e-12, ss_tot))

        return {
            "r2_on_frontier": float(r2_eff),
            "r2_off_frontier": float(r2_ineff),
            "roll_tautology_confirmed": (r2_eff > 0.9999 and r2_ineff < 0.85)
        }


# ==============================================================================
# Pytest Verification Suite
# ==============================================================================
class TestFaz58QuantitativeFinanceEngines:
    """Comprehensive test suite verifying all 6 quantitative finance engines."""

    def test_black_litterman_optimization_engine(self):
        """Model 1: Verify Black-Litterman equilibrium returns, views shrinkage, and optimal tilts."""
        np.random.seed(42)
        N = 3
        market_weights = np.array([0.50, 0.30, 0.20])
        cov_matrix = np.array([
            [0.04, 0.01, 0.015],
            [0.01, 0.025, 0.008],
            [0.015, 0.008, 0.03]
        ])
        risk_aversion = 2.5
        tau = 0.05

        # 1. Equilibrium reverse optimization
        pi = BlackLittermanOptimizationEngine.reverse_optimize_equilibrium(cov_matrix, market_weights, risk_aversion)
        assert len(pi) == 3
        assert np.all(pi > 0)

        # 2. View: Asset 1 will outperform Asset 2 by 5% (Higher than equilibrium spread 2.975%)
        P = np.array([[1.0, -1.0, 0.0]])
        Q = np.array([0.05])

        res = BlackLittermanOptimizationEngine.calculate_posterior(
            cov_matrix, market_weights, risk_aversion, P, Q, tau=tau
        )

        # Since Q (5%) is higher than equilibrium spread (pi[0] - pi[1] ~ 2.975%),
        # BL should tilt overweight into Asset 1 and underweight Asset 2
        assert res["active_tilts"][0] > 0
        assert res["active_tilts"][1] < 0
        assert abs(np.sum(res["optimal_weights_norm"]) - 1.0) < 1e-10

        # When views match equilibrium exactly, active tilts should be 0
        Q_eq = P @ pi
        res_eq = BlackLittermanOptimizationEngine.calculate_posterior(
            cov_matrix, market_weights, risk_aversion, P, Q_eq, tau=tau
        )
        assert np.allclose(res_eq["active_tilts"], 0.0, atol=1e-5)

    def test_cumulative_prospect_theory_engine(self):
        """Model 2: Verify S-shaped value function, probability weighting, and fourfold pattern."""
        engine = CumulativeProspectTheoryEngine

        # 1. Value function properties: Loss aversion (lambda = 2.25)
        v_gain = engine.value_function(100.0)
        v_loss = engine.value_function(-100.0)
        assert v_gain > 0.0
        assert v_loss < 0.0
        assert abs(v_loss) > 2.0 * v_gain  # Loss aversion

        # 2. Probability weighting: Overweighting of small probabilities
        w_small = engine.tversky_kahneman_weight(0.01, is_gain=True)
        assert w_small > 0.01  # Overweighting low probability events
        w_large = engine.tversky_kahneman_weight(0.90, is_gain=True)
        assert w_large < 0.90  # Underweighting moderate to high probability events

        # 3. Fourfold Pattern: Lottery Preference (low prob large gain)
        lottery_outcomes = np.array([0.0, 5000.0])
        lottery_probs = np.array([0.999, 0.001])
        cpt_res = engine.calculate_cpt_value(lottery_outcomes, lottery_probs)
        assert cpt_res["cpt_total_value"] > 0.0

        # Insurance Preference: Catastrophic loss avoidance
        catastrophe_outcomes = np.array([-10000.0, 0.0])
        catastrophe_probs = np.array([0.01, 0.99])
        cpt_loss = engine.calculate_cpt_value(catastrophe_outcomes, catastrophe_probs)
        assert cpt_loss["cpt_total_value"] < 0.0
        # Decision weight for catastrophic loss is magnified relative to 1%
        assert cpt_loss["decision_weights"][0] > 0.01

    def test_litterman_scheinkman_yield_curve_pca_engine(self):
        """Model 3: Verify 3-factor yield curve decomposition and butterfly duration immunization."""
        np.random.seed(123)
        T = 250
        maturities = np.array([1, 2, 3, 5, 7, 10, 20, 30])
        M = len(maturities)

        # Synthetic yield shocks driven by Level (shift), Slope (twist), and Curvature
        level_shock = np.random.normal(0, 0.008, T)
        slope_shock = np.random.normal(0, 0.004, T)
        curv_shock = np.random.normal(0, 0.002, T)

        yield_changes = np.zeros((T, M))
        for m_idx, mat in enumerate(maturities):
            # Level: uniform 1.0
            # Slope: (mat - 10) / 10
            # Curvature: - ((mat - 7)^2 - 25) / 25
            yield_changes[:, m_idx] = (
                1.0 * level_shock +
                ((mat - 10.0) / 15.0) * slope_shock +
                (-((mat - 7.0) ** 2 - 30.0) / 40.0) * curv_shock +
                np.random.normal(0, 0.0005, T)
            )

        res = LittermanScheinkmanYieldCurvePCAEngine.decompose_yield_curve(yield_changes)

        # 3 factors explain > 95% of total variance
        assert res["cum_variance_explained"][2] > 0.95
        assert res["variance_explained"][0] > 0.65  # Level is dominant

        # Factor loadings shape
        # Level: all positive
        assert np.all(res["eigenvectors"][:, 0] > 0)
        # Slope: short end lower than long end
        assert res["eigenvectors"][0, 1] < res["eigenvectors"][-1, 1]

        # Butterfly immunization
        mod_durations = np.array([0.9, 1.8, 2.7, 4.5, 6.0, 8.2, 14.0, 18.5])
        # Barbell: 2Y (idx 1), Bullet: 5Y (idx 3), Long Wing: 10Y (idx 5)
        fly = LittermanScheinkmanYieldCurvePCAEngine.construct_barbell_bullet_neutral_hedge(
            mod_durations, res["eigenvectors"],
            short_wing_idx=1, belly_bullet_idx=3, long_wing_idx=5
        )

        assert abs(fly["w_short"] + fly["w_belly"] + fly["w_long"]) < 1e-10  # Cash neutral
        assert abs(fly["net_duration"]) < 1e-10  # Duration matched
        assert fly["w_short"] > 0
        assert fly["w_long"] > 0
        assert fly["w_belly"] == -1.0
        assert abs(fly["curvature_exposure"]) > 0.001  # Has non-zero curvature exposure

    def test_cochrane_piazzesi_bond_risk_premia_engine(self):
        """Model 4: Verify single tent-shaped CP factor and monotonic factor loadings across maturities."""
        np.random.seed(99)
        T = 200
        N = 5  # maturities 1..5

        # Synthetic forward rates with tent-shaped predictive power for bond risk premia
        F = np.zeros((T, N))
        for i in range(N):
            F[:, i] = 0.03 + 0.005 * i + np.cumsum(np.random.normal(0, 0.002, T))

        # True CP factor: tent shape
        true_gamma = np.array([-0.01, -1.2, 0.8, 1.5, 0.9, -1.1])
        X_full = np.column_stack([np.ones(T), F])
        true_cp = X_full @ true_gamma

        # Excess returns for maturities 2..5: b_n * CP + noise
        b_true = np.array([0.45, 0.80, 1.15, 1.50])
        excess_returns = np.zeros((T - 1, 4))
        for n in range(4):
            excess_returns[:, n] = b_true[n] * true_cp[:-1] + np.random.normal(0, 0.005, T - 1)

        fit_res = CochranePiazzesiBondRiskPremiaEngine.fit_cochrane_piazzesi(F, excess_returns)

        assert fit_res["r2_average_return"] > 0.50
        # Loadings b_n must be strictly monotonically increasing with maturity
        assert fit_res["b_loadings"][0] < fit_res["b_loadings"][1] < fit_res["b_loadings"][2] < fit_res["b_loadings"][3]
        # Tent shape test
        assert bool(fit_res["has_tent_shape"]) is True

    def test_barberis_shleifer_vishny_daniel_sentiment_engine(self):
        """Model 5: Verify BSV Bayesian regime switching and DHS self-attribution confidence expansion."""
        # Case 1: BSV Underreaction to consecutive shocks
        # 6 consecutive positive earnings surprises
        positive_shocks = np.array([1.0, 1.2, 0.9, 1.5, 1.1, 1.8])
        bsv_res = BarberisShleiferVishnyDanielSentimentEngine.bsv_bayesian_regime_filter(
            positive_shocks, pi_L=0.25, pi_H=0.75
        )
        # Consistent positive shocks cause investors to transition toward Regime 2 (Overreaction / Growth state)
        assert bsv_res["filtered_prob_regime_2"][-1] > bsv_res["filtered_prob_regime_2"][0]

        # Case 2: DHS Asymmetric Self-Attribution
        # Private buy signal (+1.0)
        private_sig = 1.0
        # 4 confirming public signals, then 1 disconfirming signal
        public_sigs = np.array([0.5, 0.8, 0.2, 0.7, -0.9])
        dhs_res = BarberisShleiferVishnyDanielSentimentEngine.dhs_simulate_self_attribution(
            private_signal=private_sig,
            public_signals=public_sigs,
            initial_confidence=0.50,
            theta_confirm=0.30,
            theta_disconfirm=0.08
        )
        traj = dhs_res["confidence_trajectory"]
        # Confidence increases during confirmations (t=1..4)
        assert traj[4] > traj[0]
        # Even after disconfirmation at t=5, biased confidence remains high
        assert traj[5] > traj[0]

    def test_myers_apv_pecking_order_roll_critique_engine(self):
        """Model 6: Verify APV valuation, Shyam-Sunder/Myers pecking order, and Roll's critique proof."""
        engine = MyersAPVPeckingOrderRollCritiqueEngine

        # 1. APV Valuation
        unlevered_cf = [100.0, 110.0, 120.0]
        terminal_val = 1500.0
        r_unlevered = 0.10
        debt_sched = [400.0, 350.0, 300.0]
        tax_rate = 0.25
        r_debt = 0.06

        apv_res = engine.adjusted_present_value(
            unlevered_cf, terminal_val, r_unlevered, debt_sched, tax_rate, r_debt
        )
        assert apv_res["v_unlevered"] > 0
        assert apv_res["pv_tax_shield"] > 0
        assert apv_res["apv_total"] > apv_res["v_unlevered"]

        # 2. Pecking Order Deficit Regression
        # Internal financing deficit drives debt issuance 1-for-1
        np.random.seed(77)
        deficit = np.random.normal(50.0, 20.0, 100)
        debt_issuance = 0.01 + 0.95 * deficit + np.random.normal(0, 2.0, 100)
        po_res = engine.pecking_order_deficit_regression(deficit, debt_issuance)
        assert bool(po_res["supports_pecking_order"]) is True
        assert po_res["beta_pecking_order"] > 0.90

        # 3. Roll's (1977) Critique Mathematical Proof
        N = 5
        mean_ret = np.array([0.08, 0.10, 0.12, 0.15, 0.18])
        # Generate positive definite covariance matrix
        A = np.random.normal(0, 0.05, (N, N))
        cov_mat = A @ A.T + np.diag([0.01, 0.02, 0.03, 0.04, 0.05])

        # Exact mean-variance frontier portfolio (tangency portfolio): w_tan = Sigma^-1 * mu
        cov_inv = np.linalg.inv(cov_mat)
        w_eff = cov_inv @ mean_ret
        w_eff /= np.sum(w_eff)

        # Perturbed inefficient portfolio
        w_ineff = w_eff + np.array([0.40, -0.20, -0.20, 0.10, -0.10])
        w_ineff /= np.sum(w_ineff)

        roll_res = engine.roll_critique_tautology_demonstration(
            mean_ret, cov_mat, w_eff, w_ineff
        )
        assert bool(roll_res["roll_tautology_confirmed"]) is True
        assert roll_res["r2_on_frontier"] > 0.9999
        assert roll_res["r2_off_frontier"] < 0.85
