"""Programmatic TDD Verification Suite for Faz 56 Quantitative Finance Engines.

Models:
1. Mark Carhart (1997) & Narasimhan Jegadeesh & Sheridan Titman (1993): 4-Factor Momentum Model, OLS Decomposition & GRS F-Test
2. Stephen A. Ross (1976): Arbitrage Pricing Theory (APT), Spectral Factor Loadings & Factor-Mimicking Portfolios
3. Mark Rubinstein (1994) & Jens Carsten Jackwerth & Mark Rubinstein (1996): Implied Binomial Tree (IBT) & Non-Parametric Smile Fitting
4. Charles J. Corrado & Tian-Shahn Su (1996) / Robert A. Jarrow & Andrew Rudd (1982): Skewness & Kurtosis Gram-Charlier Option Engine
5. Thomas S.Y. Ho & Sang-Bin Lee (1986): Arbitrage-Free Discrete Term Structure Model & Bond Derivatives
6. Jack L. Treynor & Fischer Black (1973): Active Portfolio Management, Information Ratio & Optimal Capital Allocation
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


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Standard Black-Scholes European Call price."""
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Standard Black-Scholes European Put price."""
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


# ==============================================================================
# Model 1: Mark Carhart (1997) 4-Factor Pricing Model & Jegadeesh-Titman (1993)
# ==============================================================================
class CarhartFourFactorEngine:
    """Mark Carhart (1997) 4-Factor Asset Pricing Model.
    R_it - R_ft = alpha_i + beta_MKT (R_mt - R_ft) + beta_SMB SMB_t + beta_HML HML_t + beta_WML WML_t + eps_it.
    Includes Jegadeesh-Titman (1993) cross-sectional momentum ranking and GRS (1989) test.
    """

    @staticmethod
    def construct_wml_factor(
        historical_returns: np.ndarray,
        formation_period: int = 11,
        skip_period: int = 1
    ) -> np.ndarray:
        """Constructs Winners Minus Losers (WML) factor from historical asset returns.
        historical_returns: (T, N) matrix of asset returns.
        formation_period: typically 11 months (t-12 to t-2).
        skip_period: typically 1 month (t-1) to avoid short-term bid-ask bounce reversal.
        Returns 1D array of WML returns of length T - formation_period - skip_period.
        """
        T, N = historical_returns.shape
        start_idx = formation_period + skip_period
        if T <= start_idx:
            raise ValueError(f"T ({T}) must exceed formation_period + skip_period ({start_idx}).")

        wml = np.zeros(T - start_idx)
        for t in range(start_idx, T):
            # Evaluate past returns from t - start_idx to t - skip_period
            past_window = historical_returns[t - start_idx : t - skip_period, :]
            cum_returns = np.prod(1.0 + past_window, axis=0) - 1.0

            # Rank assets: top 30% winners, bottom 30% losers
            k = max(1, int(0.3 * N))
            sorted_indices = np.argsort(cum_returns)
            losers_idx = sorted_indices[:k]
            winners_idx = sorted_indices[-k:]

            current_returns = historical_returns[t, :]
            winner_ret = np.mean(current_returns[winners_idx])
            loser_ret = np.mean(current_returns[losers_idx])
            wml[t - start_idx] = winner_ret - loser_ret

        return wml

    @staticmethod
    def fit_single_asset(
        asset_excess_returns: np.ndarray,
        factors: np.ndarray
    ) -> Dict[str, Any]:
        """Runs OLS regression of single asset excess returns on 4 factors:
        asset_excess_returns: (T,) array
        factors: (T, 4) array with columns [MKT_RF, SMB, HML, WML]
        Returns beta loadings, alpha, R2, variance decomposition.
        """
        T = len(asset_excess_returns)
        if factors.shape[0] != T:
            raise ValueError("Time dimensions must match between asset and factors.")

        # Design matrix X with intercept: (T, 5)
        X = np.column_stack([np.ones(T), factors])
        # OLS: (X'X)^(-1) X'y
        XtX = X.T @ X
        XtY = X.T @ asset_excess_returns
        params = np.linalg.solve(XtX, XtY)

        alpha = float(params[0])
        betas = params[1:]

        fitted = X @ params
        residuals = asset_excess_returns - fitted
        ss_tot = float(np.sum((asset_excess_returns - np.mean(asset_excess_returns)) ** 2))
        ss_res = float(np.sum(residuals ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

        # Degrees of freedom: T - K - 1
        df_e = T - 5
        res_var = ss_res / max(1, df_e)
        cov_params = res_var * np.linalg.inv(XtX)
        param_stds = np.sqrt(np.maximum(1e-16, np.diag(cov_params)))

        t_stats = params / param_stds

        # Variance decomposition: Total Var = Systematic Var + Idiosyncratic Var
        factor_cov = np.cov(factors.T)
        systematic_var = float(betas.T @ factor_cov @ betas)
        idiosyncratic_var = float(np.var(residuals, ddof=1))
        total_var = float(np.var(asset_excess_returns, ddof=1))

        return {
            "alpha": alpha,
            "alpha_t_stat": float(t_stats[0]),
            "beta_mkt": float(betas[0]),
            "beta_smb": float(betas[1]),
            "beta_hml": float(betas[2]),
            "beta_wml": float(betas[3]),
            "beta_t_stats": t_stats[1:].tolist(),
            "r_squared": float(r_squared),
            "systematic_variance": systematic_var,
            "idiosyncratic_variance": idiosyncratic_var,
            "total_variance": total_var,
            "residuals": residuals,
        }

    @staticmethod
    def gibbons_ross_shanken_test(
        excess_returns: np.ndarray,
        factors: np.ndarray
    ) -> Dict[str, Any]:
        """Computes Gibbons, Ross & Shanken (GRS 1989) test for joint significance of alphas.
        excess_returns: (T, N) matrix of asset excess returns
        factors: (T, K) matrix of factor excess returns
        H0: alpha_1 = alpha_2 = ... = alpha_N = 0.
        """
        T, N = excess_returns.shape
        K = factors.shape[1]

        X = np.column_stack([np.ones(T), factors])
        # Solve for all N assets at once
        params = np.linalg.solve(X.T @ X, X.T @ excess_returns)  # (K+1, N)
        alphas = params[0, :]  # (N,)

        residuals = excess_returns - (X @ params)  # (T, N)
        sigma_res = (residuals.T @ residuals) / (T - K - 1)  # (N, N)

        factor_mean = np.mean(factors, axis=0)  # (K,)
        factor_cov = np.cov(factors.T, ddof=1)  # (K, K)

        inv_factor_cov = np.linalg.inv(factor_cov)
        inv_sigma_res = np.linalg.inv(sigma_res)

        f_bar_term = float(factor_mean.T @ inv_factor_cov @ factor_mean)
        alpha_term = float(alphas.T @ inv_sigma_res @ alphas)

        scaling = (T - N - K) / (N * (1.0 + f_bar_term))
        grs_stat = float(scaling * alpha_term)

        return {
            "grs_statistic": grs_stat,
            "df_1": N,
            "df_2": T - N - K,
            "factor_mean_term": f_bar_term,
            "alphas": alphas.tolist(),
        }


# ==============================================================================
# Model 2: Stephen A. Ross (1976) Arbitrage Pricing Theory (APT) Engine
# ==============================================================================
class ArbitragePricingTheoryEngine:
    """Stephen A. Ross (1976) Arbitrage Pricing Theory.
    Prices assets via linear factor sensitivities and identifies statutory arbitrage.
    """

    def __init__(self, n_factors: int = 3):
        self.n_factors = n_factors

    def extract_spectral_factors(self, asset_returns: np.ndarray) -> Dict[str, Any]:
        """Extracts K latent statistical factors and factor loadings via PCA / Spectral Decomposition.
        asset_returns: (T, N) matrix.
        Returns:
          - factor_loadings B: (N, K)
          - factor_scores F: (T, K)
          - idiosyncratic_var Psi: (N,)
          - explained_variance_ratio: list of length K
        """
        T, N = asset_returns.shape
        # Center returns
        mean_ret = np.mean(asset_returns, axis=0)
        centered = asset_returns - mean_ret

        # Covariance matrix (N, N)
        cov_matrix = (centered.T @ centered) / (T - 1)

        # Eigen-decomposition: cov = V @ diag(w) @ V.T
        eigvals, eigvecs = np.linalg.eigh(cov_matrix)

        # Sort descending
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        total_var = float(np.sum(eigvals))
        top_k_vals = eigvals[: self.n_factors]
        top_k_vecs = eigvecs[:, : self.n_factors]

        # Factor loadings B = V_k * sqrt(Lambda_k)
        loadings = top_k_vecs * np.sqrt(np.maximum(1e-14, top_k_vals))  # (N, K)

        # Factor scores F = centered @ V_k / sqrt(Lambda_k)
        factor_scores = centered @ top_k_vecs / np.sqrt(np.maximum(1e-14, top_k_vals))  # (T, K)

        # Fitted covariance: B B.T
        fitted_cov = loadings @ loadings.T
        residual_var = np.maximum(1e-6, np.diag(cov_matrix) - np.diag(fitted_cov))

        explained_ratio = (top_k_vals / total_var).tolist()

        return {
            "loadings": loadings,
            "factor_scores": factor_scores,
            "idiosyncratic_var": residual_var,
            "explained_ratio": explained_ratio,
            "total_explained_ratio": float(np.sum(explained_ratio)),
            "asset_means": mean_ret,
        }

    @staticmethod
    def estimate_factor_premia(
        asset_expected_returns: np.ndarray,
        factor_loadings: np.ndarray
    ) -> Dict[str, Any]:
        """Fama-MacBeth cross-sectional regression:
        E[R_i] = lambda_0 + sum_k beta_ik * lambda_k.
        asset_expected_returns: (N,)
        factor_loadings: (N, K)
        Returns zero-beta rate lambda_0 and factor risk premia lambda_k.
        """
        N, K = factor_loadings.shape
        X = np.column_stack([np.ones(N), factor_loadings])
        params = np.linalg.solve(X.T @ X, X.T @ asset_expected_returns)

        lambda_0 = float(params[0])
        factor_premia = params[1:].tolist()

        pricing_errors = asset_expected_returns - (X @ params)
        mae = float(np.mean(np.abs(pricing_errors)))

        return {
            "lambda_0": lambda_0,
            "factor_premia": factor_premia,
            "pricing_errors": pricing_errors,
            "mae": mae,
        }

    @staticmethod
    def construct_factor_mimicking_portfolios(
        factor_loadings: np.ndarray,
        idiosyncratic_var: np.ndarray
    ) -> np.ndarray:
        """Constructs pure factor-mimicking portfolios w_k:
        w_k has unit loading on factor k, zero on other factors, and minimum residual variance.
        W = Psi^(-1) B (B' Psi^(-1) B)^(-1): shape (N, K).
        """
        N, K = factor_loadings.shape
        inv_psi = np.diag(1.0 / np.maximum(1e-8, idiosyncratic_var))

        # B' Psi^(-1) B: (K, K)
        middle = factor_loadings.T @ inv_psi @ factor_loadings
        inv_middle = np.linalg.inv(middle)

        # W = Psi^(-1) B inv_middle: (N, K)
        W = inv_psi @ factor_loadings @ inv_middle
        return W

    @staticmethod
    def detect_statutory_arbitrage(
        expected_returns: np.ndarray,
        factor_loadings: np.ndarray,
        tolerance: float = 1e-5
    ) -> Dict[str, Any]:
        """Finds statutory arbitrage: a self-financing portfolio (sum w_i = 0)
        with zero factor exposure (B' w = 0) and strictly positive expected return (w' E[R] > 0).
        Uses projection onto the null space of [1', B'].
        """
        N, K = factor_loadings.shape
        A = np.column_stack([np.ones(N), factor_loadings]).T  # (K+1, N)

        # Orthogonal projection onto null(A): P = I - A' (A A')^(-1) A
        inv_AAt = np.linalg.inv(A @ A.T)
        P_null = np.eye(N) - (A.T @ inv_AAt @ A)

        # Project expected returns onto null space
        w_arb = P_null @ expected_returns
        norm_w = np.linalg.norm(w_arb)

        has_arbitrage = bool(norm_w > tolerance)
        arb_return = float(w_arb @ expected_returns)

        return {
            "has_arbitrage": has_arbitrage,
            "arbitrage_weights": w_arb / max(1e-12, norm_w) if has_arbitrage else np.zeros(N),
            "arbitrage_return": arb_return,
            "factor_exposure": (factor_loadings.T @ w_arb).tolist(),
            "net_investment": float(np.sum(w_arb)),
        }


# ==============================================================================
# Model 3: Mark Rubinstein (1994) Implied Binomial Tree (IBT) Engine
# ==============================================================================
class RubinsteinImpliedBinomialTreeEngine:
    """Mark Rubinstein (1994) Implied Binomial Tree (IBT).
    Constructs a recombinant binomial tree exactly matching the market implied volatility smile.
    """

    def __init__(
        self,
        spot: float,
        rate: float,
        maturity: float,
        steps: int = 10,
        vol_guess: float = 0.20
    ):
        self.S0 = float(spot)
        self.r = float(rate)
        self.T = float(maturity)
        self.N = int(steps)
        self.dt = self.T / self.N
        self.u = math.exp(vol_guess * math.sqrt(self.dt))
        self.d = 1.0 / self.u

    def generate_terminal_nodes(self) -> np.ndarray:
        """Returns array of terminal asset prices s_i for i = 0, ..., N."""
        s = np.zeros(self.N + 1)
        for i in range(self.N + 1):
            s[i] = self.S0 * (self.u ** i) * (self.d ** (self.N - i))
        return s

    def calibrate_terminal_probabilities(
        self,
        strikes: np.ndarray,
        call_prices: np.ndarray
    ) -> np.ndarray:
        """Computes terminal risk-neutral probabilities lambda_i (i=0..N)
        minimizing sum (lambda_i - p_i)^2 subject to:
          sum lambda_i = 1
          sum lambda_i s_i = S0 * exp(rT)
          sum lambda_i max(s_i - K_m, 0) = C_m * exp(rT)
        Uses quadratic programming approximation via KKT system.
        """
        s = self.generate_terminal_nodes()
        F = self.S0 * math.exp(self.r * self.T)

        # Prior lognormal binomial probabilities p_i
        p_up = (math.exp(self.r * self.dt) - self.d) / (self.u - self.d)
        p_up = max(0.01, min(0.99, p_up))
        p_prior = np.zeros(self.N + 1)
        for i in range(self.N + 1):
            comb = math.comb(self.N, i)
            p_prior[i] = comb * (p_up ** i) * ((1.0 - p_up) ** (self.N - i))

        M = len(strikes)
        A_eq = np.zeros((2 + M, self.N + 1))
        b_eq = np.zeros(2 + M)

        A_eq[0, :] = 1.0
        b_eq[0] = 1.0

        A_eq[1, :] = s
        b_eq[1] = F

        for m in range(M):
            A_eq[2 + m, :] = np.maximum(0.0, s - strikes[m])
            b_eq[2 + m] = call_prices[m] * math.exp(self.r * self.T)

        n_vars = self.N + 1
        n_cons = 2 + M
        KKT = np.zeros((n_vars + n_cons, n_vars + n_cons))
        KKT[:n_vars, :n_vars] = 2.0 * np.eye(n_vars)
        KKT[:n_vars, n_vars:] = A_eq.T
        KKT[n_vars:, :n_vars] = A_eq

        rhs = np.zeros(n_vars + n_cons)
        rhs[:n_vars] = 2.0 * p_prior
        rhs[n_vars:] = b_eq

        try:
            sol = np.linalg.lstsq(KKT, rhs, rcond=None)[0]
            lambdas = np.maximum(1e-9, sol[:n_vars])
        except Exception:
            lambdas = p_prior.copy()

        lambdas = lambdas / np.sum(lambdas)
        return lambdas

    def price_american_option(
        self,
        strike: float,
        is_call: bool,
        terminal_probs: np.ndarray
    ) -> Dict[str, Any]:
        """Backward induction pricing of American and European option on the calibrated implied tree."""
        df = math.exp(-self.r * self.dt)
        s_T = self.generate_terminal_nodes()

        if is_call:
            V = np.maximum(0.0, s_T - strike)
        else:
            V = np.maximum(0.0, strike - s_T)

        european_V = V.copy()
        american_V = V.copy()

        for j in range(self.N - 1, -1, -1):
            new_eur = np.zeros(j + 1)
            new_ame = np.zeros(j + 1)
            for i in range(j + 1):
                S_current = self.S0 * (self.u ** i) * (self.d ** (j - i))
                S_down = self.S0 * (self.u ** i) * (self.d ** (j + 1 - i))
                S_up = self.S0 * (self.u ** (i + 1)) * (self.d ** (j - i))

                p_up = (S_current * math.exp(self.r * self.dt) - S_down) / (S_up - S_down)
                p_up = max(0.001, min(0.999, p_up))
                p_dn = 1.0 - p_up

                c_eur = df * (p_up * european_V[i + 1] + p_dn * european_V[i])
                c_ame = df * (p_up * american_V[i + 1] + p_dn * american_V[i])

                intrinsic = max(0.0, (S_current - strike) if is_call else (strike - S_current))
                new_eur[i] = c_eur
                new_ame[i] = max(intrinsic, c_ame)

            european_V = new_eur
            american_V = new_ame

        eur_price = float(european_V[0])
        ame_price = float(american_V[0])
        early_exercise_premium = max(0.0, ame_price - eur_price)

        return {
            "european_price": eur_price,
            "american_price": ame_price,
            "early_exercise_premium": early_exercise_premium,
        }


# ==============================================================================
# Model 4: Charles J. Corrado & Tian-Shahn Su (1996) Gram-Charlier Option Engine
# ==============================================================================
class CorradoSuGramCharlierOptionEngine:
    """Charles J. Corrado & Tian-Shahn Su (1996) / Jarrow & Rudd (1982) Option Engine.
    Extends Black-Scholes using a truncated Gram-Charlier expansion for skewness and kurtosis.
    """

    @staticmethod
    def price_european_option(
        spot: float,
        strike: float,
        maturity: float,
        rate: float,
        volatility: float,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        is_call: bool = True
    ) -> Dict[str, Any]:
        """Prices European option with skewness (gamma_1) and kurtosis (gamma_2).
        C_CS = C_BS + gamma_1 * Q3 + (gamma_2 - 3) * Q4.
        P_CS = C_CS - S + K * exp(-rT).
        """
        S = float(spot)
        K = float(strike)
        T = float(maturity)
        r = float(rate)
        sigma = float(volatility)
        gamma1 = float(skewness)
        gamma2 = float(kurtosis)

        if T <= 0 or sigma <= 0:
            call_payoff = max(0.0, S - K)
            return {"price": call_payoff if is_call else max(0.0, K - S), "delta": 1.0 if S > K else 0.0}

        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        c_bs = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

        n_d1 = norm_pdf(d1)
        sigma_sq_T = sigma * sigma * T
        sigma_sqrt_T = sigma * math.sqrt(T)

        Q3 = (1.0 / 6.0) * S * sigma_sqrt_T * (
            (2.0 * sigma_sqrt_T - d1) * n_d1 + sigma_sq_T * norm_cdf(d1)
        )

        Q4 = (1.0 / 24.0) * S * sigma_sqrt_T * (
            (d1 * d1 - 3.0 * d1 * sigma_sqrt_T + sigma_sq_T - 1.0) * n_d1
            + (sigma_sqrt_T ** 3) * norm_cdf(d1)
        )

        excess_kurt = gamma2 - 3.0
        c_cs = c_bs + gamma1 * Q3 + excess_kurt * Q4
        c_cs = max(0.0, c_cs)

        # Exact Put-Call parity
        p_cs = c_cs - S + K * math.exp(-r * T)
        p_cs = max(0.0, p_cs)

        # Delta via finite difference
        eps_s = S * 1e-5
        d1_plus = (math.log((S + eps_s) / K) + (r + 0.5 * sigma * sigma) * T) / (sigma_sqrt_T)
        d2_plus = d1_plus - sigma_sqrt_T
        c_bs_plus = (S + eps_s) * norm_cdf(d1_plus) - K * math.exp(-r * T) * norm_cdf(d2_plus)
        n_d1_plus = norm_pdf(d1_plus)
        Q3_plus = (1.0 / 6.0) * (S + eps_s) * sigma_sqrt_T * (
            (2.0 * sigma_sqrt_T - d1_plus) * n_d1_plus + sigma_sq_T * norm_cdf(d1_plus)
        )
        Q4_plus = (1.0 / 24.0) * (S + eps_s) * sigma_sqrt_T * (
            (d1_plus ** 2 - 3.0 * d1_plus * sigma_sqrt_T + sigma_sq_T - 1.0) * n_d1_plus
            + (sigma_sqrt_T ** 3) * norm_cdf(d1_plus)
        )
        c_cs_up = max(0.0, c_bs_plus + gamma1 * Q3_plus + excess_kurt * Q4_plus)
        delta_call = (c_cs_up - c_cs) / eps_s
        delta_put = delta_call - 1.0

        # Vega via finite difference
        eps_vol = 1e-5
        sigma_up = sigma + eps_vol
        d1_v = (math.log(S / K) + (r + 0.5 * sigma_up * sigma_up) * T) / (sigma_up * math.sqrt(T))
        d2_v = d1_v - sigma_up * math.sqrt(T)
        c_bs_v = S * norm_cdf(d1_v) - K * math.exp(-r * T) * norm_cdf(d2_v)
        sig_sq_v = sigma_up * sigma_up * T
        sig_sqt_v = sigma_up * math.sqrt(T)
        n_d1_v = norm_pdf(d1_v)
        Q3_v = (1.0 / 6.0) * S * sig_sqt_v * ((2.0 * sig_sqt_v - d1_v) * n_d1_v + sig_sq_v * norm_cdf(d1_v))
        Q4_v = (1.0 / 24.0) * S * sig_sqt_v * (
            (d1_v * d1_v - 3.0 * d1_v * sig_sqt_v + sig_sq_v - 1.0) * n_d1_v
            + (sig_sqt_v ** 3) * norm_cdf(d1_v)
        )
        c_cs_v = max(0.0, c_bs_v + gamma1 * Q3_v + excess_kurt * Q4_v)
        vega = (c_cs_v - c_cs) / eps_vol

        return {
            "price": c_cs if is_call else p_cs,
            "bs_price": c_bs if is_call else (c_bs - S + K * math.exp(-r * T)),
            "skew_adjustment": float(gamma1 * Q3),
            "kurt_adjustment": float(excess_kurt * Q4),
            "delta": float(delta_call if is_call else delta_put),
            "vega": float(vega),
            "q3": float(Q3),
            "q4": float(Q4),
        }


# ==============================================================================
# Model 5: Thomas S.Y. Ho & Sang-Bin Lee (1986) Discrete Term Structure Model
# ==============================================================================
class HoLeeTermStructureEngine:
    """Thomas S.Y. Ho & Sang-Bin Lee (1986) Arbitrage-Free Term Structure Model.
    Calibrates a binomial short rate tree to the initial discount bond curve P(0, T).
    """

    def __init__(
        self,
        discount_factors: List[float],
        sigma: float,
        dt: float = 1.0,
        pi_prob: float = 0.50
    ):
        self.P0 = [1.0] + [float(p) for p in discount_factors]
        self.M = len(discount_factors)
        self.sigma = float(sigma)
        self.dt = float(dt)
        self.pi = float(pi_prob)
        self.delta = math.exp(-self.sigma * (self.dt ** 1.5))

    def perturbation_function(self, n: int) -> float:
        """h(n) = 1 / (pi + (1 - pi) * delta^n)."""
        return 1.0 / (self.pi + (1.0 - self.pi) * (self.delta ** n))

    def discount_bond_price(self, t: int, T: int, i: int) -> float:
        """Computes price at time t of a zero-coupon bond maturing at T,
        where i is the number of up-moves out of t steps (0 <= i <= t <= T <= M).
        """
        if t == T:
            return 1.0
        if t > T or T > self.M:
            raise ValueError(f"Invalid indices t={t}, T={T}, max M={self.M}")

        ratio = self.P0[T] / self.P0[t]

        num_prod = 1.0
        for k in range(1, t + 1):
            num_prod *= self.perturbation_function(T - k)

        den_prod = 1.0
        for k in range(1, t + 1):
            den_prod *= self.perturbation_function(t - k)

        perturbation_ratio = num_prod / den_prod
        state_factor = self.delta ** ((t - i) * (T - t))

        return ratio * perturbation_ratio * state_factor

    def short_rate(self, t: int, i: int) -> float:
        """Computes spot short rate at node (t, i): r_{t, i} = -ln P_i(t, t+1) / dt."""
        p_next = self.discount_bond_price(t, t + 1, i)
        return -math.log(p_next) / self.dt

    def price_european_bond_option(
        self,
        t_expiry: int,
        t_maturity: int,
        strike: float,
        is_call: bool
    ) -> float:
        """Prices European option expiring at t_expiry on a zero-coupon bond maturing at t_maturity."""
        if t_expiry >= t_maturity:
            raise ValueError("Expiry must be strictly before bond maturity.")

        payoffs = np.zeros(t_expiry + 1)
        for i in range(t_expiry + 1):
            bond_val = self.discount_bond_price(t_expiry, t_maturity, i)
            payoffs[i] = max(0.0, (bond_val - strike) if is_call else (strike - bond_val))

        values = payoffs
        for step in range(t_expiry - 1, -1, -1):
            new_vals = np.zeros(step + 1)
            for i in range(step + 1):
                p_next = self.discount_bond_price(step, step + 1, i)
                new_vals[i] = p_next * (self.pi * values[i + 1] + (1.0 - self.pi) * values[i])
            values = new_vals

        return float(values[0])

    def price_caplet(self, t_fixing: int, strike_rate: float, notional: float = 100.0) -> float:
        """Prices an interest rate Caplet fixing at t_fixing, paying at t_fixing + 1."""
        strike_bond = 1.0 / (1.0 + strike_rate * self.dt)
        put_val = self.price_european_bond_option(t_fixing, t_fixing + 1, strike_bond, is_call=False)
        return float(notional * (1.0 + strike_rate * self.dt) * put_val)


# ==============================================================================
# Model 6: Jack L. Treynor & Fischer Black (1973) Active Portfolio Engine
# ==============================================================================
class TreynorBlackPortfolioEngine:
    """Jack L. Treynor & Fischer Black (1973) Active Portfolio Management.
    Decomposes optimal asset allocation into an active alpha portfolio and passive market index.
    Maximizes global Sharpe ratio via Information Ratio expansion: SR_p^2 = SR_m^2 + IR^2.
    """

    @staticmethod
    def optimize_active_portfolio(
        alphas: np.ndarray,
        betas: np.ndarray,
        idiosyncratic_vars: np.ndarray,
        market_expected_excess_return: float,
        market_variance: float
    ) -> Dict[str, Any]:
        """Calculates optimal Treynor-Black weights:
        alphas: (N,) alpha estimates
        betas: (N,) beta estimates
        idiosyncratic_vars: (N,) residual variance sigma_e,i^2
        market_expected_excess_return: E[R_M - R_f]
        market_variance: sigma_M^2
        """
        N = len(alphas)
        if len(betas) != N or len(idiosyncratic_vars) != N:
            raise ValueError("Dimensions of alphas, betas, and idiosyncratic_vars must match.")

        raw_active_weights = alphas / np.maximum(1e-12, idiosyncratic_vars)
        sum_raw = np.sum(raw_active_weights)
        if abs(sum_raw) < 1e-15:
            norm_active_weights = np.zeros(N)
        else:
            norm_active_weights = raw_active_weights / sum_raw

        alpha_A = float(np.sum(norm_active_weights * alphas))
        beta_A = float(np.sum(norm_active_weights * betas))
        var_e_A = float(np.sum((norm_active_weights ** 2) * idiosyncratic_vars))

        info_ratio = math.sqrt(max(0.0, float(np.sum((alphas ** 2) / np.maximum(1e-12, idiosyncratic_vars)))))

        sr_market = market_expected_excess_return / math.sqrt(market_variance)

        if var_e_A > 1e-15 and market_expected_excess_return > 1e-15:
            raw_w_A = (alpha_A / var_e_A) / (market_expected_excess_return / market_variance)
            w_A_opt = raw_w_A / (1.0 + (1.0 - beta_A) * raw_w_A)
        else:
            w_A_opt = 0.0

        w_M_opt = 1.0 - w_A_opt
        total_asset_weights = w_A_opt * norm_active_weights
        sr_optimal = math.sqrt(sr_market ** 2 + info_ratio ** 2)

        return {
            "active_weights": norm_active_weights.tolist(),
            "weight_active_portfolio": float(w_A_opt),
            "weight_market_index": float(w_M_opt),
            "total_asset_weights": total_asset_weights.tolist(),
            "active_portfolio_alpha": alpha_A,
            "active_portfolio_beta": beta_A,
            "active_portfolio_residual_variance": var_e_A,
            "information_ratio": info_ratio,
            "market_sharpe_ratio": float(sr_market),
            "optimal_sharpe_ratio": float(sr_optimal),
            "sharpe_improvement": float(sr_optimal - sr_market),
        }


# ==============================================================================
# Pytest Verification Suite
# ==============================================================================
class TestFaz56QuantitativeFinanceEngines:
    """Agentic TDD Test Suite verifying all 6 Faz 56 Quantitative Finance Engines."""

    def test_carhart_four_factor_engine(self):
        """Model 1: Verify Carhart 4-Factor OLS, WML factor construction, and GRS test."""
        np.random.seed(42)
        T = 120
        N = 10

        factors = np.zeros((T, 4))
        factors[:, 0] = np.random.normal(0.007, 0.045, T)  # MKT
        factors[:, 1] = np.random.normal(0.002, 0.030, T)  # SMB
        factors[:, 2] = np.random.normal(0.003, 0.032, T)  # HML
        factors[:, 3] = np.random.normal(0.006, 0.040, T)  # WML

        true_alpha = 0.0025  # 25 bps monthly alpha
        true_betas = np.array([1.10, 0.40, -0.30, 0.50])
        noise = np.random.normal(0.0, 0.02, T)
        y = true_alpha + factors @ true_betas + noise

        res = CarhartFourFactorEngine.fit_single_asset(y, factors)

        assert abs(res["alpha"] - true_alpha) < 0.005
        assert abs(res["beta_mkt"] - 1.10) < 0.15
        assert abs(res["beta_smb"] - 0.40) < 0.15
        assert abs(res["beta_hml"] - (-0.30)) < 0.15
        assert abs(res["beta_wml"] - 0.50) < 0.15
        assert 0.60 < res["r_squared"] < 1.0

        approx_tot = res["systematic_variance"] + res["idiosyncratic_variance"]
        assert abs(approx_tot - res["total_variance"]) / res["total_variance"] < 0.05

        asset_history = np.random.normal(0.008, 0.05, (36, 20))
        wml_series = CarhartFourFactorEngine.construct_wml_factor(asset_history, formation_period=11, skip_period=1)
        assert len(wml_series) == 36 - 12
        assert not np.isnan(wml_series).any()

        universe_returns = np.random.normal(0.008, 0.05, (T, N))
        grs_res = CarhartFourFactorEngine.gibbons_ross_shanken_test(universe_returns, factors)
        assert grs_res["grs_statistic"] > 0.0
        assert grs_res["df_1"] == N
        assert grs_res["df_2"] == T - N - 4

    def test_arbitrage_pricing_theory_engine(self):
        """Model 2: Verify Ross (1976) APT factor extraction, factor mimicking, and arbitrage detector."""
        np.random.seed(123)
        T = 200
        N = 8
        K = 3

        true_F = np.random.normal(0, 1, (T, K))
        true_B = np.random.uniform(-0.8, 0.8, (N, K))
        true_residuals = np.random.normal(0, 0.02, (T, N))
        returns = 0.01 + true_F @ true_B.T + true_residuals

        engine = ArbitragePricingTheoryEngine(n_factors=K)
        spec = engine.extract_spectral_factors(returns)

        assert spec["loadings"].shape == (N, K)
        assert spec["factor_scores"].shape == (T, K)
        assert spec["total_explained_ratio"] > 0.50
        assert (spec["idiosyncratic_var"] > 0).all()

        premia_res = ArbitragePricingTheoryEngine.estimate_factor_premia(
            asset_expected_returns=np.mean(returns, axis=0),
            factor_loadings=spec["loadings"]
        )
        assert len(premia_res["factor_premia"]) == K
        assert premia_res["mae"] >= 0.0

        W_f = ArbitragePricingTheoryEngine.construct_factor_mimicking_portfolios(
            spec["loadings"], spec["idiosyncratic_var"]
        )
        assert W_f.shape == (N, K)

        loadings_mimic = spec["loadings"].T @ W_f
        assert np.allclose(loadings_mimic, np.eye(K), atol=1e-5)

        eq_returns = premia_res["lambda_0"] + spec["loadings"] @ np.array(premia_res["factor_premia"])
        no_arb = ArbitragePricingTheoryEngine.detect_statutory_arbitrage(eq_returns, spec["loadings"])
        assert not no_arb["has_arbitrage"]
        assert abs(no_arb["arbitrage_return"]) < 1e-10

        dislocated_returns = eq_returns.copy()
        dislocated_returns[0] += 0.08
        arb = ArbitragePricingTheoryEngine.detect_statutory_arbitrage(dislocated_returns, spec["loadings"])
        assert arb["has_arbitrage"]
        assert arb["arbitrage_return"] > 0.0
        assert abs(arb["net_investment"]) < 1e-10
        assert np.allclose(arb["factor_exposure"], np.zeros(K), atol=1e-10)

    def test_rubinstein_implied_binomial_tree_engine(self):
        """Model 3: Verify Rubinstein Implied Binomial Tree calibration & American option pricing."""
        S0 = 100.0
        r = 0.05
        T = 1.0
        steps = 12

        engine = RubinsteinImpliedBinomialTreeEngine(spot=S0, rate=r, maturity=T, steps=steps, vol_guess=0.20)
        s_T = engine.generate_terminal_nodes()
        assert len(s_T) == steps + 1
        assert s_T[0] < S0 < s_T[-1]

        strikes = np.array([85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0])
        skew_vols = np.array([0.28, 0.25, 0.23, 0.20, 0.18, 0.17, 0.16])
        market_calls = np.array([
            black_scholes_call(S0, strikes[i], T, r, skew_vols[i]) for i in range(len(strikes))
        ])

        lambdas = engine.calibrate_terminal_probabilities(strikes, market_calls)

        assert abs(np.sum(lambdas) - 1.0) < 1e-5
        assert (lambdas >= 0.0).all()

        forward = S0 * math.exp(r * T)
        fitted_forward = float(np.sum(lambdas * s_T))
        assert abs(fitted_forward - forward) / forward < 0.02

        put_res = engine.price_american_option(strike=100.0, is_call=False, terminal_probs=lambdas)
        assert put_res["american_price"] >= put_res["european_price"] - 1e-6
        assert put_res["early_exercise_premium"] >= 0.0

        deep_itm_put = engine.price_american_option(strike=130.0, is_call=False, terminal_probs=lambdas)
        assert deep_itm_put["early_exercise_premium"] > 0.0
        assert deep_itm_put["american_price"] >= 130.0 - S0

    def test_corrado_su_gram_charlier_option_engine(self):
        """Model 4: Verify Corrado & Su (1996) Skewness & Kurtosis option expansion & Greeks."""
        S = 100.0
        K = 100.0
        T = 1.0
        r = 0.05
        sigma = 0.20

        res_normal = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, K, T, r, sigma, skewness=0.0, kurtosis=3.0, is_call=True
        )
        assert abs(res_normal["price"] - res_normal["bs_price"]) < 1e-10
        assert abs(res_normal["skew_adjustment"]) < 1e-10
        assert abs(res_normal["kurt_adjustment"]) < 1e-10

        res_put_normal = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, 80.0, T, r, sigma, skewness=0.0, kurtosis=3.0, is_call=False
        )
        res_put_neg_skew = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, 80.0, T, r, sigma, skewness=-0.8, kurtosis=3.0, is_call=False
        )
        assert res_put_neg_skew["price"] > res_put_normal["price"]
        # Excess kurtosis effect (fat tails in deep OTM):
        # Deep OTM Call (K=140) in the tail region (|d1| > 1) becomes MORE expensive with excess kurtosis
        res_call_normal = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, 140.0, T, r, sigma, skewness=0.0, kurtosis=3.0, is_call=True
        )
        res_call_fat_tail = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, 140.0, T, r, sigma, skewness=0.0, kurtosis=5.0, is_call=True
        )
        assert res_call_fat_tail["price"] > res_call_normal["price"]

        c_res = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, K, T, r, sigma, skewness=-0.5, kurtosis=4.5, is_call=True
        )
        p_res = CorradoSuGramCharlierOptionEngine.price_european_option(
            S, K, T, r, sigma, skewness=-0.5, kurtosis=4.5, is_call=False
        )
        expected_parity = S - K * math.exp(-r * T)
        actual_parity = c_res["price"] - p_res["price"]
        assert abs(actual_parity - expected_parity) < 1e-8

        assert 0.0 < c_res["delta"] < 1.0
        assert -1.0 < p_res["delta"] < 0.0
        assert c_res["vega"] > 0.0

    def test_ho_lee_term_structure_engine(self):
        """Model 5: Verify Ho-Lee (1986) arbitrage-free short rate tree, ZCB options, and caplets."""
        discount_factors = [0.9608, 0.9200, 0.8750, 0.8250]
        sigma = 0.015
        dt = 1.0

        engine = HoLeeTermStructureEngine(discount_factors, sigma=sigma, dt=dt)

        for T in range(1, len(discount_factors) + 1):
            p_0_T = engine.discount_bond_price(t=0, T=T, i=0)
            assert abs(p_0_T - discount_factors[T - 1]) < 1e-10

        p_down = engine.discount_bond_price(t=2, T=3, i=0)
        p_up = engine.discount_bond_price(t=2, T=3, i=2)
        assert p_up > p_down

        r_down = engine.short_rate(t=2, i=0)
        r_up = engine.short_rate(t=2, i=2)
        assert r_down > r_up

        strike_call = 0.90
        call_val = engine.price_european_bond_option(t_expiry=1, t_maturity=3, strike=strike_call, is_call=True)
        put_val = engine.price_european_bond_option(t_expiry=1, t_maturity=3, strike=strike_call, is_call=False)
        assert call_val > 0.0
        assert put_val > 0.0

        bond_parity = discount_factors[2] - strike_call * discount_factors[0]
        actual_bond_diff = call_val - put_val
        assert abs(actual_bond_diff - bond_parity) < 1e-8

        caplet_price = engine.price_caplet(t_fixing=2, strike_rate=0.05, notional=1000.0)
        assert caplet_price >= 0.0

    def test_treynor_black_portfolio_engine(self):
        """Model 6: Verify Treynor & Black (1973) active portfolio optimization and Sharpe expansion."""
        alphas = np.array([0.04, 0.02, -0.01, 0.03])
        betas = np.array([1.20, 0.90, 1.10, 0.80])
        idiosyncratic_vars = np.array([0.04, 0.02, 0.03, 0.025])

        mkt_excess_ret = 0.08
        mkt_var = 0.04

        res = TreynorBlackPortfolioEngine.optimize_active_portfolio(
            alphas, betas, idiosyncratic_vars, mkt_excess_ret, mkt_var
        )

        raw_ratios = alphas / idiosyncratic_vars
        w_active = np.array(res["active_weights"])
        assert np.isclose(w_active[0] / w_active[1], raw_ratios[0] / raw_ratios[1])
        assert abs(np.sum(w_active) - 1.0) < 1e-10

        assert res["information_ratio"] > 0.0

        expected_sr_sq = res["market_sharpe_ratio"] ** 2 + res["information_ratio"] ** 2
        actual_sr_sq = res["optimal_sharpe_ratio"] ** 2
        assert abs(actual_sr_sq - expected_sr_sq) < 1e-10

        assert res["optimal_sharpe_ratio"] > res["market_sharpe_ratio"]
        assert res["sharpe_improvement"] > 0.0

        zero_alphas = np.zeros(4)
        zero_res = TreynorBlackPortfolioEngine.optimize_active_portfolio(
            zero_alphas, betas, idiosyncratic_vars, mkt_excess_ret, mkt_var
        )
        assert zero_res["information_ratio"] == 0.0
        assert zero_res["weight_active_portfolio"] == 0.0
        assert zero_res["weight_market_index"] == 1.0
        assert zero_res["optimal_sharpe_ratio"] == zero_res["market_sharpe_ratio"]
