"""Programmatic TDD Verification Suite for Faz 60 Quantitative Finance Engines.

Models:
1. Andrea Frazzini & Lasse Heje Pedersen (2014): Betting Against Beta (BAB), Leverage Constraints & Zero-Beta Factor Synthesis Engine
2. Sanford J. Grossman & Joseph E. Stiglitz (1980): Information Acquisition Equilibrium, Grossman-Stiglitz Paradox & Price Informativeness Engine
3. Francis A. Longstaff & Eduardo S. Schwartz (2001): Least-Squares Monte Carlo (LSM) American & Bermudan Option Valuation Engine
4. Robert F. Engle & Simone Manganelli (2004): CAViaR (Conditional Autoregressive Value at Risk), Koenker-Bassett Quantile Loss & Dynamic Quantile (DQ) Test Engine
5. K. Geert Rouwenhorst (1995): Markov Chain Discretization of Highly Persistent Gaussian AR(1) Processes Engine
6. Peter Carr & Dilip Madan (1998, 2001) / Emanuel Derman & Iraj Kani (1998): Model-Free Implied Variance, CBOE VIX Log-Contract Replication & Variance Risk Premium Engine
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
# Model 1: Andrea Frazzini & Lasse Heje Pedersen (2014) Betting Against Beta (BAB)
# ==============================================================================
class BettingAgainstBetaEngine:
    """Andrea Frazzini & Lasse Heje Pedersen (2014) Betting Against Beta (BAB).
    
    Explains the empirical anomaly that high-beta assets earn lower risk-adjusted
    returns than predicted by CAPM due to leverage constraints.
    Synthesizes a market-neutral, zero-beta long-short factor:
        r_BAB = (1 / beta_L) * (r_L - r_f) - (1 / beta_H) * (r_H - r_f)
    """

    @staticmethod
    def estimate_betas(
        asset_returns: np.ndarray,
        market_returns: np.ndarray,
        shrink_weight: float = 0.60
    ) -> np.ndarray:
        """Estimates time-series betas and shrinks them toward 1.0 (Vasicek shrinkage).
        
        beta_i = shrink_weight * beta_ols_i + (1 - shrink_weight) * 1.0
        """
        n_assets = asset_returns.shape[1]
        mkt_var = float(np.var(market_returns, ddof=1))
        if mkt_var < 1e-12:
            return np.ones(n_assets)

        betas = np.zeros(n_assets)
        for i in range(n_assets):
            cov = float(np.cov(asset_returns[:, i], market_returns, ddof=1)[0, 1])
            ols_beta = cov / mkt_var
            betas[i] = shrink_weight * ols_beta + (1.0 - shrink_weight) * 1.0

        return betas

    @staticmethod
    def construct_bab_weights(betas: np.ndarray) -> Dict[str, Any]:
        """Constructs rank-based weights for Low-Beta and High-Beta portfolios.
        
        Rank assets: z_i = rank(beta_i).
        Mean rank: z_bar = mean(z).
        Weights proportional to rank deviation:
            w_raw_L = max(0, z_bar - z_i)
            w_raw_H = max(0, z_i - z_bar)
        Normalized so sum(w_L) = 1 and sum(w_H) = 1.
        De-leveraging factors: k_L = 1 / beta_L, k_H = 1 / beta_H.
        """
        n = len(betas)
        # 1-indexed ranks
        ranks = np.argsort(np.argsort(betas)) + 1.0
        z_bar = float(np.mean(ranks))

        w_raw_L = np.maximum(0.0, z_bar - ranks)
        w_raw_H = np.maximum(0.0, ranks - z_bar)

        sum_L = float(np.sum(w_raw_L))
        sum_H = float(np.sum(w_raw_H))

        if sum_L > 0:
            w_L = w_raw_L / sum_L
        else:
            w_L = np.ones(n) / n

        if sum_H > 0:
            w_H = w_raw_H / sum_H
        else:
            w_H = np.ones(n) / n

        beta_L = float(np.dot(w_L, betas))
        beta_H = float(np.dot(w_H, betas))

        k_L = 1.0 / beta_L if beta_L > 1e-6 else 1.0
        k_H = 1.0 / beta_H if beta_H > 1e-6 else 1.0

        # Net BAB weights (leveraged long low-beta, leveraged short high-beta)
        w_BAB = k_L * w_L - k_H * w_H
        net_beta = float(k_L * beta_L - k_H * beta_H)  # Should be 0.0

        return {
            "w_L": w_L,
            "w_H": w_H,
            "beta_L": beta_L,
            "beta_H": beta_H,
            "k_L": k_L,
            "k_H": k_H,
            "w_BAB": w_BAB,
            "net_beta": net_beta
        }

    @staticmethod
    def backtest_bab_factor(
        asset_returns: np.ndarray,
        market_returns: np.ndarray,
        risk_free_rate: float = 0.0,
        betas: Optional[np.ndarray] = None,
        shrink_weight: float = 1.0
    ) -> Dict[str, Any]:
        """Calculates realized BAB returns, alpha, beta, and Sharpe ratio."""
        if betas is None:
            betas = BettingAgainstBetaEngine.estimate_betas(asset_returns, market_returns, shrink_weight=shrink_weight)
        weights_info = BettingAgainstBetaEngine.construct_bab_weights(betas)

        w_L = weights_info["w_L"]
        w_H = weights_info["w_H"]
        k_L = weights_info["k_L"]
        k_H = weights_info["k_H"]

        # Portfolio return series
        r_L = np.dot(asset_returns, w_L)
        r_H = np.dot(asset_returns, w_H)

        # BAB return: leveraged long low-beta, leveraged short high-beta
        r_BAB = k_L * (r_L - risk_free_rate) - k_H * (r_H - risk_free_rate)

        mean_bab = float(np.mean(r_BAB))
        std_bab = float(np.std(r_BAB, ddof=1))
        sharpe_bab = (mean_bab / std_bab * math.sqrt(252)) if std_bab > 1e-8 else 0.0

        # OLS regression of BAB on Market: r_BAB = alpha + beta * (r_M - r_f)
        excess_mkt = market_returns - risk_free_rate
        cov_bab_mkt = float(np.cov(r_BAB, excess_mkt, ddof=1)[0, 1])
        var_mkt = float(np.var(excess_mkt, ddof=1))
        realized_beta = cov_bab_mkt / var_mkt if var_mkt > 1e-12 else 0.0
        annualized_alpha = (mean_bab - realized_beta * float(np.mean(excess_mkt))) * 252

        return {
            "mean_daily_return": mean_bab,
            "std_daily_return": std_bab,
            "annualized_sharpe": sharpe_bab,
            "annualized_alpha": annualized_alpha,
            "realized_beta": realized_beta,
            "leverage_low_beta": k_L,
            "delever_high_beta": k_H,
            "beta_spread": weights_info["beta_H"] - weights_info["beta_L"]
        }


# ==============================================================================
# Model 2: Sanford J. Grossman & Joseph E. Stiglitz (1980) Information Equilibrium
# ==============================================================================
class GrossmanStiglitzInformationEquilibriumEngine:
    """Sanford J. Grossman & Joseph E. Stiglitz (1980) Information Equilibrium.
    
    Proves the Grossman-Stiglitz Paradox:
    If market prices are completely informationally efficient, no trader has an
    incentive to purchase costly private information (cost c > 0). Hence, prices
    cannot be fully revealing in equilibrium.
    """

    @staticmethod
    def solve_equilibrium(
        cost_c: float,
        risk_aversion_a: float,
        var_theta: float,
        var_epsilon: float,
        var_x: float
    ) -> Dict[str, Any]:
        """Finds the endogenous fraction of informed traders lambda* in [0, 1].
        
        Fundamental payoff: u = theta + epsilon, theta ~ N(0, var_theta), epsilon ~ N(0, var_eps).
        Informed see theta at cost c.
        Uninformed observe only price P. Noise trader supply x ~ N(0, var_x).
        
        Equilibrium condition for interior lambda* in (0, 1):
            Var(theta | uninformed) / Var(theta | informed) = exp(2 * a * c)
        The effective conditional noise variance of uninformed from price signal w is:
            var_w = (a * var_eps / lambda)^2 * var_x
        Precision:
            1 / Var(theta | P) = (1 / var_theta) + (1 / var_w)
        """
        if cost_c <= 0.0:
            return {
                "lambda_star": 1.0,
                "price_informativeness": 1.0,
                "is_paradox_active": False,
                "regime": "all_informed_zero_cost"
            }

        target_var_post = var_epsilon * (math.exp(2.0 * risk_aversion_a * cost_c) - 1.0)

        if target_var_post >= var_theta:
            lambda_star = 0.0
            price_inf = 0.0
            regime = "no_information_acquisition"
        else:
            required_inv_var_w = (1.0 / target_var_post) - (1.0 / var_theta)
            if required_inv_var_w <= 0.0:
                lambda_star = 0.0
                price_inf = 0.0
                regime = "no_information_acquisition"
            else:
                lambda_sq = required_inv_var_w * ((risk_aversion_a * var_epsilon) ** 2) * var_x
                lambda_raw = math.sqrt(lambda_sq)
                if lambda_raw >= 1.0:
                    lambda_star = 1.0
                    regime = "fully_informed_corner"
                else:
                    lambda_star = lambda_raw
                    regime = "interior_equilibrium"

                var_w = ((risk_aversion_a * var_epsilon / max(1e-6, lambda_star)) ** 2) * var_x
                price_inf = var_theta / (var_theta + var_w)

        return {
            "lambda_star": float(lambda_star),
            "price_informativeness": float(price_inf),
            "target_var_post": float(target_var_post),
            "cost_c": cost_c,
            "regime": regime,
            "is_paradox_active": (cost_c > 0.0 and lambda_star < 1.0)
        }

    @staticmethod
    def simulate_price_formation(
        lambda_star: float,
        n_samples: int = 1000,
        var_theta: float = 1.0,
        var_eps: float = 0.5,
        var_x: float = 0.8,
        risk_aversion_a: float = 1.0,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Simulates realized market prices and confirms empirical informativeness."""
        np.random.seed(seed)
        theta = np.random.normal(0.0, math.sqrt(var_theta), n_samples)
        x_noise = np.random.normal(0.0, math.sqrt(var_x), n_samples)

        if lambda_star < 1e-6:
            p = - x_noise
        else:
            alpha_ratio = (risk_aversion_a * var_eps) / lambda_star
            p = theta - alpha_ratio * x_noise

        corr_matrix = np.corrcoef(p, theta)
        emp_corr = float(corr_matrix[0, 1])
        emp_r2 = emp_corr ** 2

        return {
            "empirical_correlation": emp_corr,
            "empirical_r_squared": emp_r2,
            "signal_to_noise": float(var_theta / (((risk_aversion_a * var_eps / max(1e-6, lambda_star)) ** 2) * var_x))
        }


# ==============================================================================
# Model 3: Francis A. Longstaff & Eduardo S. Schwartz (2001) Least-Squares MC (LSM)
# ==============================================================================
class LeastSquaresMonteCarloEngine:
    """Francis A. Longstaff & Eduardo S. Schwartz (2001) Least-Squares Monte Carlo (LSM).
    
    Values American and Bermudan options by using cross-sectional ordinary least
    squares regression across in-the-money paths to estimate the conditional
    expectation of continuation value.
    """

    @staticmethod
    def simulate_gbm_paths(
        S0: float,
        r: float,
        sigma: float,
        T: float,
        n_steps: int,
        n_paths: int,
        seed: Optional[int] = 42
    ) -> np.ndarray:
        """Simulates Geometric Brownian Motion paths with antithetic variates."""
        if seed is not None:
            np.random.seed(seed)

        dt = T / n_steps
        half_paths = n_paths // 2

        z = np.random.normal(0.0, 1.0, (half_paths, n_steps))
        z = np.vstack([z, -z])

        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = S0

        drift = (r - 0.5 * sigma * sigma) * dt
        vol_sqrt_dt = sigma * math.sqrt(dt)

        for t in range(n_steps):
            paths[:, t + 1] = paths[:, t] * np.exp(drift + vol_sqrt_dt * z[:, t])

        return paths

    @staticmethod
    def price_american_option(
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        n_steps: int = 50,
        n_paths: int = 10000,
        option_type: str = "put",
        basis_degree: int = 3,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Prices an American Put (or Call) option using the LSM algorithm."""
        paths = LeastSquaresMonteCarloEngine.simulate_gbm_paths(
            S0=S0, r=r, sigma=sigma, T=T, n_steps=n_steps, n_paths=n_paths, seed=seed
        )

        dt = T / n_steps
        df = math.exp(-r * dt)

        if option_type.lower() == "put":
            payoffs = np.maximum(K - paths[:, -1], 0.0)
        else:
            payoffs = np.maximum(paths[:, -1] - K, 0.0)

        cash_flows = payoffs.copy()

        for t in range(n_steps - 1, 0, -1):
            S_t = paths[:, t]
            if option_type.lower() == "put":
                immediate_payoff = np.maximum(K - S_t, 0.0)
            else:
                immediate_payoff = np.maximum(S_t - K, 0.0)

            itm_mask = immediate_payoff > 0.0
            if np.sum(itm_mask) < (basis_degree + 2):
                cash_flows = cash_flows * df
                continue

            S_itm = S_t[itm_mask]
            Y = cash_flows[itm_mask] * df
            X = np.column_stack([S_itm ** d for d in range(basis_degree + 1)])

            try:
                beta, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
                continuation_value = np.dot(X, beta)
            except np.linalg.LinAlgError:
                continuation_value = Y

            exercise = immediate_payoff[itm_mask] >= continuation_value

            cash_flows = cash_flows * df
            exercised_indices = np.where(itm_mask)[0][exercise]
            cash_flows[exercised_indices] = immediate_payoff[exercised_indices]

        discounted_t0_cashflows = cash_flows * df

        immediate_t0 = max(0.0, K - S0) if option_type.lower() == "put" else max(0.0, S0 - K)
        sim_price = float(np.mean(discounted_t0_cashflows))
        american_price = max(immediate_t0, sim_price)
        std_err = float(np.std(discounted_t0_cashflows, ddof=1) / math.sqrt(n_paths))

        if option_type.lower() == "put":
            euro_payoffs = np.maximum(K - paths[:, -1], 0.0) * math.exp(-r * T)
        else:
            euro_payoffs = np.maximum(paths[:, -1] - K, 0.0) * math.exp(-r * T)

        euro_price = float(np.mean(euro_payoffs))
        early_exercise_premium = max(0.0, american_price - euro_price)

        return {
            "american_price": american_price,
            "european_price": euro_price,
            "early_exercise_premium": early_exercise_premium,
            "std_error": std_err,
            "ci_95_lower": american_price - 1.96 * std_err,
            "ci_95_upper": american_price + 1.96 * std_err,
            "n_paths": n_paths,
            "n_steps": n_steps
        }


# ==============================================================================
# Model 4: Robert F. Engle & Simone Manganelli (2004) CAViaR
# ==============================================================================
class CAViaRQuantileAutoregressionEngine:
    """Robert F. Engle & Simone Manganelli (2004) CAViaR.
    
    Conditional Autoregressive Value at Risk by Regression Quantiles.
    Directly models the tail quantile autoregressively:
        Symmetric Absolute Value (SAV):
            q_t = beta_1 + beta_2 * q_{t-1} + beta_3 * |r_{t-1}|
        Asymmetric Slope (AS):
            q_t = beta_1 + beta_2 * q_{t-1} + beta_3 * max(r_{t-1}, 0) + beta_4 * -min(r_{t-1}, 0)
    """

    @staticmethod
    def pinball_loss(
        y: np.ndarray,
        q: np.ndarray,
        theta: float = 0.05
    ) -> float:
        """Computes the Koenker-Bassett check/pinball loss function."""
        u = y - q
        loss = np.where(u < 0, u * (theta - 1.0), u * theta)
        return float(np.mean(loss))

    @staticmethod
    def generate_caviar_series(
        returns: np.ndarray,
        params: np.ndarray,
        model_type: str = "SAV"
    ) -> np.ndarray:
        """Recursively computes CAViaR quantile series q_t."""
        t_len = len(returns)
        q = np.zeros(t_len)
        q[0] = float(np.percentile(returns[:min(100, t_len)], 5.0))

        if model_type == "SAV":
            b1, b2, b3 = params[0], params[1], params[2]
            for t in range(1, t_len):
                q[t] = b1 + b2 * q[t - 1] + b3 * abs(returns[t - 1])
        elif model_type == "AS":
            b1, b2, b3, b4 = params[0], params[1], params[2], params[3]
            for t in range(1, t_len):
                r_prev = returns[t - 1]
                pos_part = max(0.0, r_prev)
                neg_part = max(0.0, -r_prev)
                q[t] = b1 + b2 * q[t - 1] + b3 * pos_part + b4 * neg_part
        else:
            raise ValueError(f"Unsupported CAViaR model: {model_type}")

        return q

    @staticmethod
    def fit_caviar(
        returns: np.ndarray,
        theta: float = 0.05,
        model_type: str = "SAV"
    ) -> Dict[str, Any]:
        """Fits CAViaR model parameters via heuristic grid & pattern search."""
        sample_5pct = float(np.percentile(returns, theta * 100))

        if model_type == "SAV":
            best_params = np.array([sample_5pct * 0.1, 0.85, -0.2])
        else:
            best_params = np.array([sample_5pct * 0.1, 0.85, 0.05, -0.3])

        def objective(p):
            if abs(p[1]) >= 0.999:
                return 1e6
            q = CAViaRQuantileAutoregressionEngine.generate_caviar_series(returns, p, model_type)
            return CAViaRQuantileAutoregressionEngine.pinball_loss(returns, q, theta)

        best_loss = objective(best_params)
        candidate_b2 = [0.70, 0.85, 0.92]
        candidate_b3 = [-0.1, -0.2, -0.4]

        for b2 in candidate_b2:
            for b3 in candidate_b3:
                if model_type == "SAV":
                    p = np.array([sample_5pct * (1.0 - b2), b2, b3])
                else:
                    p = np.array([sample_5pct * (1.0 - b2), b2, 0.05, b3])
                loss = objective(p)
                if loss < best_loss:
                    best_loss = loss
                    best_params = p.copy()

        step_sizes = np.ones_like(best_params) * 0.02
        for _ in range(30):
            improved = False
            for i in range(len(best_params)):
                for delta in [-step_sizes[i], step_sizes[i]]:
                    trial = best_params.copy()
                    trial[i] += delta
                    trial_loss = objective(trial)
                    if trial_loss < best_loss:
                        best_loss = trial_loss
                        best_params = trial
                        improved = True
                        break
            if not improved:
                step_sizes *= 0.5
                if np.max(step_sizes) < 1e-4:
                    break

        fitted_quantiles = CAViaRQuantileAutoregressionEngine.generate_caviar_series(
            returns, best_params, model_type
        )
        hit_series = (returns < fitted_quantiles).astype(float)
        hit_rate = float(np.mean(hit_series))

        dq_res = CAViaRQuantileAutoregressionEngine.dynamic_quantile_test(
            returns, fitted_quantiles, theta=theta, lags=4
        )

        return {
            "model_type": model_type,
            "theta": theta,
            "parameters": best_params.tolist(),
            "pinball_loss": best_loss,
            "empirical_hit_rate": hit_rate,
            "target_hit_rate": theta,
            "fitted_quantiles": fitted_quantiles,
            "dq_statistic": dq_res["dq_stat"],
            "dq_p_value": dq_res["p_value"],
            "dq_passed": dq_res["passed"]
        }

    @staticmethod
    def dynamic_quantile_test(
        returns: np.ndarray,
        quantiles: np.ndarray,
        theta: float = 0.05,
        lags: int = 4
    ) -> Dict[str, Any]:
        """Dynamic Quantile (DQ) Test of Engle & Manganelli (2004)."""
        hits = (returns < quantiles).astype(float) - theta
        t_len = len(hits)

        valid_t = t_len - lags
        if valid_t <= (lags + 2):
            return {"dq_stat": 0.0, "p_value": 1.0, "passed": True}

        Y = hits[lags:]
        X = np.ones((valid_t, lags + 1))
        for lag in range(1, lags + 1):
            X[:, lag] = hits[(lags - lag):(t_len - lag)]

        try:
            gamma, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
            pred = np.dot(X, gamma)
            dq_stat = float(np.dot(pred, pred) / (theta * (1.0 - theta)))
        except np.linalg.LinAlgError:
            dq_stat = 0.0

        k = lags + 1
        if dq_stat <= 0.0:
            p_value = 1.0
        else:
            z = ((dq_stat / k) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * k))) / math.sqrt(2.0 / (9.0 * k))
            p_value = float(max(0.0, min(1.0, 1.0 - norm_cdf(z))))

        return {
            "dq_stat": dq_stat,
            "p_value": p_value,
            "degrees_of_freedom": k,
            "passed": bool(p_value > 0.01)
        }


# ==============================================================================
# Model 5: K. Geert Rouwenhorst (1995) Markov Chain Discretization
# ==============================================================================
class RouwenhorstMarkovDiscretizationEngine:
    """K. Geert Rouwenhorst (1995) Markov Chain Discretization.
    
    Discretizes a continuous Gaussian AR(1) process:
        y_t = rho * y_{t-1} + epsilon_t,  epsilon_t ~ N(0, sigma_eps^2)
    onto an N-state discrete Markov chain.
    """

    @staticmethod
    def discretize_ar1(
        rho: float,
        sigma_eps: float,
        n_states: int = 5,
        mu: float = 0.0
    ) -> Dict[str, Any]:
        """Constructs state space grid and transition probability matrix P."""
        if abs(rho) >= 1.0:
            raise ValueError("AR(1) persistence |rho| must be strictly less than 1.0.")
        if n_states < 2:
            raise ValueError("Number of states N must be at least 2.")

        sigma_y = sigma_eps / math.sqrt(1.0 - rho * rho)
        psi = math.sqrt(n_states - 1.0) * sigma_y

        grid = np.linspace(-psi, psi, n_states) + mu

        p = (1.0 + rho) / 2.0
        q = p

        P = np.array([
            [p, 1.0 - p],
            [1.0 - q, q]
        ])

        for n in range(2, n_states):
            P_prev = P
            dim = n + 1
            P_new = np.zeros((dim, dim))

            P_new[:n, :n] += p * P_prev
            P_new[:n, 1:(n + 1)] += (1.0 - p) * P_prev
            P_new[1:(n + 1), :n] += (1.0 - q) * P_prev
            P_new[1:(n + 1), 1:(n + 1)] += q * P_prev

            P_new[1:n, :] /= 2.0
            P = P_new

        pi = np.zeros(n_states)
        for i in range(n_states):
            pi[i] = math.comb(n_states - 1, i) * (0.5 ** (n_states - 1))

        moments = RouwenhorstMarkovDiscretizationEngine.validate_moments(
            grid=grid, P=P, pi=pi, rho=rho, sigma_eps=sigma_eps, mu=mu
        )

        return {
            "n_states": n_states,
            "rho": rho,
            "sigma_eps": sigma_eps,
            "grid": grid,
            "transition_matrix": P,
            "stationary_distribution": pi,
            "moments": moments
        }

    @staticmethod
    def validate_moments(
        grid: np.ndarray,
        P: np.ndarray,
        pi: np.ndarray,
        rho: float,
        sigma_eps: float,
        mu: float = 0.0
    ) -> Dict[str, float]:
        """Validates numerical moments against continuous theoretical values."""
        theo_mean = mu
        theo_var = (sigma_eps ** 2) / (1.0 - rho * rho)
        theo_autocorr = rho

        disc_mean = float(np.dot(pi, grid))
        centered_grid = grid - disc_mean
        disc_var = float(np.dot(pi, centered_grid ** 2))

        outer_dev = np.outer(centered_grid, centered_grid)
        autocov = float(np.sum(pi[:, None] * P * outer_dev))
        disc_autocorr = autocov / disc_var if disc_var > 1e-12 else 0.0

        return {
            "theoretical_mean": theo_mean,
            "discrete_mean": disc_mean,
            "mean_error": abs(disc_mean - theo_mean),
            "theoretical_variance": theo_var,
            "discrete_variance": disc_var,
            "variance_error_rel": abs(disc_var - theo_var) / theo_var,
            "theoretical_autocorr": theo_autocorr,
            "discrete_autocorr": disc_autocorr,
            "autocorr_error": abs(disc_autocorr - theo_autocorr)
        }


# ==============================================================================
# Model 6: Peter Carr & Dilip Madan (1998, 2001) Model-Free Variance & VIX
# ==============================================================================
class CarrMadanModelFreeVarianceEngine:
    """Peter Carr & Dilip Madan (1998, 2001) / Emanuel Derman & Iraj Kani (1998).
    
    Model-Free Implied Variance & CBOE VIX Log-Contract Replication.
    """

    @staticmethod
    def compute_model_free_implied_variance(
        S0: float,
        r: float,
        T: float,
        strikes: np.ndarray,
        call_prices: np.ndarray,
        put_prices: np.ndarray
    ) -> Dict[str, Any]:
        """Calculates model-free implied variance and VIX index level."""
        F0 = S0 * math.exp(r * T)

        idx_star = int(np.where(strikes <= F0)[0][-1])
        S_star = strikes[idx_star]

        n_strikes = len(strikes)
        delta_k = np.zeros(n_strikes)

        delta_k[0] = strikes[1] - strikes[0]
        delta_k[-1] = strikes[-1] - strikes[-2]
        for i in range(1, n_strikes - 1):
            delta_k[i] = (strikes[i + 1] - strikes[i - 1]) / 2.0

        q_prices = np.zeros(n_strikes)
        for i in range(n_strikes):
            K = strikes[i]
            if K < S_star:
                q_prices[i] = put_prices[i]
            elif K > S_star:
                q_prices[i] = call_prices[i]
            else:
                q_prices[i] = 0.5 * (call_prices[i] + put_prices[i])

        integral_term = float(np.sum((delta_k / (strikes ** 2)) * q_prices))
        forward_adj = (1.0 / T) * (((F0 / S_star) - 1.0) ** 2)

        implied_var = (2.0 / T) * math.exp(r * T) * integral_term - forward_adj
        implied_var = max(1e-6, implied_var)
        vix_index = 100.0 * math.sqrt(implied_var)

        return {
            "forward_price": F0,
            "atm_strike": S_star,
            "integral_term": integral_term,
            "forward_adjustment": forward_adj,
            "model_free_variance": implied_var,
            "vix_index": vix_index,
            "annualized_volatility": math.sqrt(implied_var)
        }

    @staticmethod
    def calculate_variance_risk_premium(
        vix_index: float,
        realized_volatility: float
    ) -> Dict[str, float]:
        """Computes Variance Risk Premium (VRP) and Volatility Risk Premium (VolRP)."""
        implied_var = (vix_index / 100.0) ** 2
        realized_var = realized_volatility ** 2

        vrp = implied_var - realized_var
        vol_rp = (vix_index / 100.0) - realized_volatility

        return {
            "vix_implied_variance": implied_var,
            "realized_variance": realized_var,
            "variance_risk_premium": vrp,
            "volatility_risk_premium": vol_rp,
            "vrp_ratio": implied_var / max(1e-6, realized_var)
        }

    @staticmethod
    def verify_carr_madan_spanning_identity(
        S0: float,
        ST: float,
        strikes: np.ndarray,
        S_star: float
    ) -> Dict[str, float]:
        """Numerically validates the Carr-Madan replication identity for log contract."""
        target_payoff = -math.log(ST / S_star)
        linear_stock_term = - (ST - S_star) / S_star

        delta_k = np.zeros_like(strikes)
        delta_k[0] = strikes[1] - strikes[0]
        delta_k[-1] = strikes[-1] - strikes[-2]
        for i in range(1, len(strikes) - 1):
            delta_k[i] = (strikes[i + 1] - strikes[i - 1]) / 2.0

        option_integral = 0.0
        for i in range(len(strikes)):
            K = strikes[i]
            if K <= S_star:
                put_payoff = max(0.0, K - ST)
                option_integral += (delta_k[i] / (K ** 2)) * put_payoff
            else:
                call_payoff = max(0.0, ST - K)
                option_integral += (delta_k[i] / (K ** 2)) * call_payoff

        replicated_payoff = linear_stock_term + option_integral
        error = abs(replicated_payoff - target_payoff)

        return {
            "target_payoff": target_payoff,
            "replicated_payoff": replicated_payoff,
            "absolute_error": error,
            "relative_error": error / max(1e-4, abs(target_payoff))
        }


# ==============================================================================
# Programmatic Verification Test Suite (Agentic TDD)
# ==============================================================================
class TestFaz60QuantitativeFinanceEngines:
    """Agentic TDD test suite validating the 6 Faz 60 Quantitative Finance Engines."""

    def test_betting_against_beta_engine(self):
        """Model 1: Verify Frazzini & Pedersen BAB beta estimation, weighting, and market neutrality."""
        np.random.seed(42)
        n_days = 500
        n_assets = 10

        mkt = np.random.normal(0.0004, 0.012, n_days)
        true_betas = np.linspace(0.4, 1.8, n_assets)
        assets = np.zeros((n_days, n_assets))
        for i in range(n_assets):
            alpha_i = (1.2 - true_betas[i]) * 0.0002
            idio = np.random.normal(0.0, 0.015, n_days)
            assets[:, i] = alpha_i + true_betas[i] * mkt + idio

        est_betas = BettingAgainstBetaEngine.estimate_betas(assets, mkt, shrink_weight=0.60)
        assert len(est_betas) == n_assets
        assert est_betas[0] < est_betas[-1]

        weights = BettingAgainstBetaEngine.construct_bab_weights(est_betas)
        assert abs(weights["net_beta"]) < 1e-10
        assert weights["beta_L"] < weights["beta_H"]
        assert weights["k_L"] > 1.0
        assert weights["k_H"] < 1.0
        assert abs(np.sum(weights["w_L"]) - 1.0) < 1e-6
        assert abs(np.sum(weights["w_H"]) - 1.0) < 1e-6

        # 3. Backtest BAB factor with pure OLS beta weights to verify market-neutrality
        ols_betas = BettingAgainstBetaEngine.estimate_betas(assets, mkt, shrink_weight=1.0)
        backtest = BettingAgainstBetaEngine.backtest_bab_factor(assets, mkt, risk_free_rate=0.0001, betas=ols_betas)
        assert backtest["beta_spread"] > 0.4
        assert abs(backtest["realized_beta"]) < 0.10  # Near-zero realized beta
        assert backtest["annualized_sharpe"] > 0.0

    def test_grossman_stiglitz_information_equilibrium_engine(self):
        """Model 2: Verify Grossman-Stiglitz Paradox, endogenous info fraction, and informativeness."""
        var_theta = 1.5
        var_eps = 0.6
        var_x = 0.8
        risk_aversion_a = 1.2

        # 1. Zero cost -> all informed
        res_zero = GrossmanStiglitzInformationEquilibriumEngine.solve_equilibrium(
            cost_c=0.0, risk_aversion_a=risk_aversion_a,
            var_theta=var_theta, var_epsilon=var_eps, var_x=var_x
        )
        assert res_zero["lambda_star"] == 1.0
        assert res_zero["price_informativeness"] == 1.0

        # 2. Moderate cost -> interior equilibrium
        res_interior = GrossmanStiglitzInformationEquilibriumEngine.solve_equilibrium(
            cost_c=0.40, risk_aversion_a=risk_aversion_a,
            var_theta=var_theta, var_epsilon=var_eps, var_x=var_x
        )
        assert 0.0 < res_interior["lambda_star"] < 1.0
        assert 0.0 < res_interior["price_informativeness"] < 1.0
        assert res_interior["is_paradox_active"] is True

        res_high = GrossmanStiglitzInformationEquilibriumEngine.solve_equilibrium(
            cost_c=2.5, risk_aversion_a=risk_aversion_a,
            var_theta=var_theta, var_epsilon=var_eps, var_x=var_x
        )
        assert res_high["lambda_star"] == 0.0
        assert res_high["price_informativeness"] == 0.0

        sim = GrossmanStiglitzInformationEquilibriumEngine.simulate_price_formation(
            lambda_star=res_interior["lambda_star"],
            n_samples=5000, var_theta=var_theta, var_eps=var_eps, var_x=var_x
        )
        assert 0.20 < sim["empirical_correlation"] < 0.95

    def test_least_squares_monte_carlo_engine(self):
        """Model 3: Verify Longstaff-Schwartz American option pricing and early exercise premium."""
        S0 = 100.0
        K = 100.0
        r = 0.05
        sigma = 0.20
        T = 1.0

        put_res = LeastSquaresMonteCarloEngine.price_american_option(
            S0=S0, K=K, r=r, sigma=sigma, T=T,
            n_steps=25, n_paths=8000, option_type="put", basis_degree=3, seed=123
        )

        assert 5.5 < put_res["american_price"] < 6.5
        assert put_res["american_price"] >= put_res["european_price"]
        assert put_res["early_exercise_premium"] > 0.10
        assert put_res["std_error"] < 0.15
        assert put_res["ci_95_lower"] < put_res["american_price"] < put_res["ci_95_upper"]

        itm_put = LeastSquaresMonteCarloEngine.price_american_option(
            S0=80.0, K=100.0, r=0.05, sigma=0.20, T=1.0,
            n_steps=25, n_paths=8000, option_type="put", seed=123
        )
        assert itm_put["american_price"] >= (100.0 - 80.0)
        assert itm_put["early_exercise_premium"] > 0.50

    def test_caviar_quantile_autoregression_engine(self):
        """Model 4: Verify Engle & Manganelli CAViaR pinball loss, parameter fitting, and DQ test."""
        np.random.seed(42)
        n_days = 600
        returns = np.zeros(n_days)
        sigma = 0.015
        for t in range(n_days):
            sigma = math.sqrt(0.00002 + 0.85 * (sigma ** 2) + 0.10 * (returns[t - 1] ** 2))
            returns[t] = np.random.normal(0.0, sigma)

        q_dummy = np.percentile(returns, 5.0) * np.ones(n_days)
        loss = CAViaRQuantileAutoregressionEngine.pinball_loss(returns, q_dummy, theta=0.05)
        assert loss > 0.0

        caviar_fit = CAViaRQuantileAutoregressionEngine.fit_caviar(
            returns, theta=0.05, model_type="SAV"
        )
        assert len(caviar_fit["parameters"]) == 3
        assert 0.02 <= caviar_fit["empirical_hit_rate"] <= 0.09
        assert caviar_fit["pinball_loss"] < loss

        dq_test = CAViaRQuantileAutoregressionEngine.dynamic_quantile_test(
            returns, caviar_fit["fitted_quantiles"], theta=0.05, lags=4
        )
        assert dq_test["degrees_of_freedom"] == 5
        assert dq_test["dq_stat"] >= 0.0

    def test_rouwenhorst_markov_discretization_engine(self):
        """Model 5: Verify Rouwenhorst AR(1) discretization and exact preservation of moments."""
        rho = 0.95
        sigma_eps = 0.08
        n_states = 5
        mu = 0.02

        res = RouwenhorstMarkovDiscretizationEngine.discretize_ar1(
            rho=rho, sigma_eps=sigma_eps, n_states=n_states, mu=mu
        )

        grid = res["grid"]
        P = res["transition_matrix"]
        pi = res["stationary_distribution"]
        moments = res["moments"]

        assert P.shape == (n_states, n_states)
        row_sums = np.sum(P, axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-8)
        assert np.all(P >= 0.0)

        assert abs(float(np.sum(pi)) - 1.0) < 1e-8
        pi_next = np.dot(pi, P)
        assert np.allclose(pi, pi_next, atol=1e-8)

        assert moments["mean_error"] < 1e-6
        assert moments["variance_error_rel"] < 0.02
        assert moments["autocorr_error"] < 0.02

        extreme_res = RouwenhorstMarkovDiscretizationEngine.discretize_ar1(
            rho=0.99, sigma_eps=0.02, n_states=7
        )
        assert extreme_res["moments"]["autocorr_error"] < 0.015

    def test_carr_madan_model_free_variance_engine(self):
        """Model 6: Verify Carr-Madan spanning identity, model-free implied variance, and VIX."""
        S0 = 100.0
        r = 0.04
        T = 30.0 / 365.0
        F0 = S0 * math.exp(r * T)

        true_sigma = 0.20
        strikes = np.linspace(80.0, 120.0, 81)
        calls = np.zeros_like(strikes)
        puts = np.zeros_like(strikes)

        for i, K in enumerate(strikes):
            d1 = (math.log(S0 / K) + (r + 0.5 * true_sigma ** 2) * T) / (true_sigma * math.sqrt(T))
            d2 = d1 - true_sigma * math.sqrt(T)
            calls[i] = S0 * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
            puts[i] = K * math.exp(-r * T) * norm_cdf(-d2) - S0 * norm_cdf(-d1)

        mfv_res = CarrMadanModelFreeVarianceEngine.compute_model_free_implied_variance(
            S0=S0, r=r, T=T, strikes=strikes, call_prices=calls, put_prices=puts
        )

        assert 19.0 < mfv_res["vix_index"] < 21.0
        assert 0.035 < mfv_res["model_free_variance"] < 0.045

        vrp_res = CarrMadanModelFreeVarianceEngine.calculate_variance_risk_premium(
            vix_index=mfv_res["vix_index"],
            realized_volatility=0.16
        )
        assert vrp_res["variance_risk_premium"] > 0.0
        assert vrp_res["volatility_risk_premium"] > 0.03
        assert vrp_res["vrp_ratio"] > 1.30

        span_res = CarrMadanModelFreeVarianceEngine.verify_carr_madan_spanning_identity(
            S0=S0, ST=105.0, strikes=strikes, S_star=F0
        )
        assert span_res["absolute_error"] < 0.005
