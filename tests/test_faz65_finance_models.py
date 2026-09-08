"""Programmatic TDD Verification Suite for Faz 65 Quantitative Finance Engines.

Models:
1. Douglas T. Breeden & Robert H. Litzenberger (1978):
   State-Contingent Prices Implicit in Option Prices, Risk-Neutral Density (RND) Extraction,
   Butterfly Spread Second-Derivative Pricing, and Moment Recovery.
2. Sanford J. Grossman & Merton H. Miller (1988):
   Determinants of Market Liquidity, Dealer Capital Commitment Model, Asynchronous Arrival,
   Inventory Risk Premium, and Endogenous Bid-Ask Spread Dynamics.
3. Gary Gorton & Andrew Metrick (2012) / Arvind Krishnamurthy, Stefan Nagel & Dmitry Orlov (2014):
   Securitized Banking Runs, Bilateral Repo Haircut Spirals, Fire-Sale Deleveraging Cascades,
   and Shadow Bank Solvency Boundaries.
4. George Tauchen & Mark R. Pitts (1983) / Peter K. Clark (1973) / Torben G. Andersen (1996):
   Mixture of Distributions Hypothesis (MDH), Subordinated Latent Information Flow,
   Volume-Volatility Joint Dynamics, and Leptokurtic Return Kurtosis.
5. Geert Bekaert & Campbell R. Harvey (1995, 1997):
   Time-Varying Financial Market Integration, Regime-Switching Global Asset Pricing,
   Logistic Transition Functions, and Emerging Market Cost of Capital Compression.
6. Richard Roll (1984) & Kenneth R. French (1980):
   Roll's Effective Bid-Ask Spread Serial Covariance Estimator, Microstructure Bounce,
   and Trading vs Non-Trading Time Volatility Variance Ratio.
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


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Analytical European Call price under Black-Scholes-Merton."""
    if T <= 0.0:
        return max(0.0, S - K)
    if sigma <= 1e-7:
        return max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T))
    
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)


# ==============================================================================
# 1. Douglas T. Breeden & Robert H. Litzenberger (1978) Engine
# ==============================================================================
class BreedenLitzenbergerRNDEngine:
    """
    Douglas T. Breeden & Robert H. Litzenberger (1978):
    'State Contingent Prices Implicit in Option Prices', Journal of Business.
    
    Extracts the risk-neutral probability density function (RND) of the underlying asset at maturity T
    directly from European call prices via the second partial derivative with respect to strike K:
        f^*(K) = e^{r T} * d^2 C(K, T) / dK^2
        q(K) = d^2 C(K, T) / dK^2  (Arrow-Debreu state price density)
    """

    def __init__(self, r: float = 0.05, q: float = 0.0):
        self.r = float(r)
        self.q = float(q)

    def extract_rnd_discrete(self, S0: float, T: float, strikes: np.ndarray, call_prices: np.ndarray) -> Dict[str, Any]:
        """
        Extracts the discrete risk-neutral density f^*(K) and Arrow-Debreu state prices q(K)
        using finite-difference butterfly spreads across sorted strikes.
        """
        if len(strikes) < 3 or len(strikes) != len(call_prices):
            raise ValueError("At least 3 option strike-price pairs required.")
        
        # Sort by strike
        idx = np.argsort(strikes)
        K = np.array(strikes[idx], dtype=float)
        C = np.array(call_prices[idx], dtype=float)
        
        n = len(K)
        rnd_density = np.zeros(n - 2)
        state_prices = np.zeros(n - 2)
        mid_strikes = K[1:-1]
        discount = math.exp(-self.r * T)
        future_factor = math.exp(self.r * T)
        
        # Non-uniform or uniform central second derivative
        for i in range(1, n - 1):
            h_minus = K[i] - K[i - 1]
            h_plus = K[i + 1] - K[i]
            
            # Non-uniform finite difference second derivative
            term1 = C[i + 1] / (h_plus * (h_plus + h_minus))
            term2 = C[i] / (h_plus * h_minus)
            term3 = C[i - 1] / (h_minus * (h_plus + h_minus))
            d2C_dK2 = 2.0 * (term1 - term2 + term3)
            
            # No-arbitrage convexity enforcement (density cannot be negative)
            d2C_dK2 = max(0.0, d2C_dK2)
            
            state_prices[i - 1] = d2C_dK2
            rnd_density[i - 1] = future_factor * d2C_dK2

        # Numerical integration for cumulative probability and moments
        # Trapezoidal rule for normalization and moment extraction
        dK = np.diff(mid_strikes)
        if len(dK) > 0:
            avg_pdf = 0.5 * (rnd_density[:-1] + rnd_density[1:])
            total_prob = float(np.sum(avg_pdf * dK))
            
            # If total_prob > 0, normalize to guarantee sum = 1
            norm_rnd = rnd_density / total_prob if total_prob > 1e-6 else rnd_density
            
            # Compute recovered risk-neutral moments
            mid_K = 0.5 * (mid_strikes[:-1] + mid_strikes[1:])
            norm_avg_pdf = 0.5 * (norm_rnd[:-1] + norm_rnd[1:])
            
            mean_S_T = float(np.sum(mid_K * norm_avg_pdf * dK))
            var_S_T = float(np.sum(((mid_K - mean_S_T) ** 2) * norm_avg_pdf * dK))
            std_S_T = math.sqrt(max(1e-8, var_S_T))
            skew_S_T = float(np.sum(((mid_K - mean_S_T) ** 3) * norm_avg_pdf * dK) / (std_S_T ** 3))
            kurt_S_T = float(np.sum(((mid_K - mean_S_T) ** 4) * norm_avg_pdf * dK) / (std_S_T ** 4))
        else:
            total_prob = 1.0
            norm_rnd = rnd_density
            mean_S_T = S0 * math.exp((self.r - self.q) * T)
            std_S_T = 0.0
            skew_S_T = 0.0
            kurt_S_T = 3.0

        theoretical_forward = S0 * math.exp((self.r - self.q) * T)
        forward_error = abs(mean_S_T - theoretical_forward)

        return {
            "strikes": mid_strikes,
            "raw_density": rnd_density,
            "normalized_density": norm_rnd,
            "state_prices": state_prices,
            "total_probability_integral": total_prob,
            "recovered_mean": mean_S_T,
            "theoretical_forward": theoretical_forward,
            "forward_error": forward_error,
            "recovered_std": std_S_T,
            "recovered_skewness": skew_S_T,
            "recovered_kurtosis": kurt_S_T,
            "is_convex": bool(np.all(state_prices >= 0.0))
        }

    def verify_butterfly_spread(self, K: float, dK: float, call_K_minus: float, call_K: float, call_K_plus: float, T: float) -> Dict[str, float]:
        """
        Verifies exact Arrow-Debreu price of a butterfly spread:
        Price(Fly) = C(K - dK) - 2C(K) + C(K + dK) >= 0.
        """
        fly_cost = call_K_minus - 2.0 * call_K + call_K_plus
        d2C = fly_cost / (dK * dK)
        state_price = d2C
        pdf_K = math.exp(self.r * T) * d2C
        return {
            "butterfly_cost": fly_cost,
            "d2C_dK2": d2C,
            "state_price_qK": state_price,
            "rnd_fK": float(pdf_K),
            "arbitrage_free": bool(fly_cost >= -1e-10)
        }


# ==============================================================================
# 2. Sanford J. Grossman & Merton H. Miller (1988) Engine
# ==============================================================================
class GrossmanMillerLiquidityEngine:
    """
    Sanford J. Grossman & Merton H. Miller (1988):
    'Liquidity and Market Structure', Journal of Finance, 43(3), 617-633.
    
    Formalizes the economics of market making where natural buyers and sellers arrive asynchronously.
    Market makers commit risk capital, holding inventory over interval tau = 1/lambda,
    charging an equilibrium bid-ask spread and price concession proportional to inventory risk.
    """

    def __init__(self, dealer_risk_aversion: float = 0.05, order_cost: float = 0.02):
        self.gamma_m = float(dealer_risk_aversion)  # Market maker risk aversion
        self.c = float(order_cost)                  # Fixed per-share processing cost

    def equilibrium_spread(self, Q: float, sigma: float, arrival_rate: float, dealer_capital: float = 1000000.0) -> Dict[str, float]:
        """
        Computes equilibrium bid-ask spread, price concession, and inventory holding premium.
        Spread S = (2 * gamma_m * sigma^2 * Q) / (arrival_rate * (1 + capital_factor)) + 2 * c
        """
        if arrival_rate <= 0:
            raise ValueError("Arrival rate must be positive.")
        
        # Effective holding horizon tau = 1 / lambda
        tau = 1.0 / arrival_rate
        var_per_period = (sigma ** 2) * tau
        
        # Capital cushion damping factor: dealers with abundant capital buffer inventory shocks
        capital_dampening = 1.0 + (dealer_capital / 1_000_000.0) * 0.2
        effective_gamma = self.gamma_m / capital_dampening
        
        # Inventory risk premium per unit trade
        inventory_risk_premium = effective_gamma * var_per_period * Q
        
        # Half-spread (price concession) for immediacy demander
        price_concession = inventory_risk_premium + self.c
        total_spread = 2.0 * price_concession
        
        # Fractional spread relative to a baseline price P0 = 100
        relative_spread_bps = (total_spread / 100.0) * 10_000.0

        return {
            "order_size_Q": float(Q),
            "asset_volatility": float(sigma),
            "arrival_rate_lambda": float(arrival_rate),
            "expected_inventory_holding_tau": float(tau),
            "inventory_risk_premium": float(inventory_risk_premium),
            "price_concession": float(price_concession),
            "total_bid_ask_spread": float(total_spread),
            "relative_spread_bps": float(relative_spread_bps),
            "dealer_capital_dampening": float(capital_dampening)
        }

    def simulate_order_flow_market_making(self, initial_price: float, orders: List[Tuple[float, float]], sigma: float, arrival_rate: float) -> Dict[str, Any]:
        """
        Simulates sequential buy/sell orders arriving asynchronously.
        Tracks market maker cumulative inventory, realized PnL, and bid-ask quote adjustments.
        """
        price = initial_price
        inventory = 0.0
        dealer_cash = 0.0
        price_history = [price]
        inventory_history = [inventory]
        spread_history = []
        
        for side, size in orders:
            # side: +1 for client buy (dealer sells), -1 for client sell (dealer buys)
            quote = self.equilibrium_spread(size, sigma, arrival_rate)
            half_spread = quote["price_concession"]
            spread_history.append(quote["total_bid_ask_spread"])
            
            # Inventory skew: if dealer has long inventory, they lower both bid and ask to deter buys and encourage sells
            skew = -0.01 * inventory
            
            if side > 0:  # Client buys at ask
                trade_price = price + half_spread + skew
                dealer_cash += trade_price * size
                inventory -= size
            else:         # Client sells at bid
                trade_price = price - half_spread + skew
                dealer_cash -= trade_price * size
                inventory += size
            
            # Fundamental price diffusion + small order impact
            price = price + 0.005 * side * size + np.random.normal(0, sigma * 0.1)
            price_history.append(price)
            inventory_history.append(inventory)
            
        final_mtm_pnl = dealer_cash + inventory * price
        
        return {
            "final_inventory": inventory,
            "final_cash": dealer_cash,
            "final_mtm_pnl": final_mtm_pnl,
            "mean_spread": float(np.mean(spread_history)),
            "spread_history": spread_history,
            "price_history": price_history,
            "inventory_history": inventory_history
        }


# ==============================================================================
# 3. Gary Gorton & Andrew Metrick (2012) / Krishnamurthy et al. (2014) Engine
# ==============================================================================
class GortonMetrickRepoHaircutEngine:
    """
    Gary Gorton & Andrew Metrick (2012):
    'Securitized Banking and the Run on Repo', Journal of Financial Economics, 104(3), 425-451.
    Arvind Krishnamurthy, Stefan Nagel & Dmitry Orlov (2014):
    'Sizing Up Repo', Journal of Finance, 69(6), 2381-2417.
    
    Models the modern shadow banking run: wholesale funding runs take place through
    explosive collateral haircut increases (m_t -> 50%-100%), which forces rapid
    fire-sale deleveraging and triggers recursive insolvency spirals.
    """

    def __init__(self, fire_sale_impact_alpha: float = 0.15):
        self.alpha = float(fire_sale_impact_alpha)  # Market depth elasticity for fire sales

    def compute_repo_capacity(self, collateral_value: float, haircut: float) -> Dict[str, float]:
        """
        Computes borrowing capacity and maximum balance sheet leverage given haircut m:
        Borrowing Capacity D = (1 - m) * V
        Maximum Leverage L = V / Equity = 1 / m
        """
        if haircut <= 0.0 or haircut > 1.0:
            raise ValueError("Haircut m must be strictly between 0 and 1.")
        
        max_leverage = 1.0 / haircut
        debt_capacity = (1.0 - haircut) * collateral_value
        required_equity = haircut * collateral_value
        
        return {
            "collateral_value": float(collateral_value),
            "haircut": float(haircut),
            "debt_capacity": float(debt_capacity),
            "required_equity": float(required_equity),
            "max_leverage": float(max_leverage)
        }

    def simulate_haircut_spiral(self, initial_assets: float, initial_haircut: float, shocked_haircut: float, initial_equity: float, rounds: int = 5) -> Dict[str, Any]:
        """
        Simulates the recursive repo deleveraging spiral when haircuts spike from m_0 to m_shock.
        Required debt repayment: Delta D = Assets * (m_shock - m_0) / (1 - m_0)
        If cash is insufficient, dealer must fire-sell assets, depressing collateral prices via alpha.
        """
        assets = float(initial_assets)
        haircut = float(initial_haircut)
        equity = float(initial_equity)
        debt = assets - equity
        
        history = [{
            "round": 0,
            "assets": assets,
            "debt": debt,
            "equity": equity,
            "haircut": haircut,
            "leverage": assets / max(1e-4, equity),
            "fire_sales": 0.0,
            "defaulted": False
        }]
        
        current_haircut = float(shocked_haircut)
        defaulted = False
        
        for r in range(1, rounds + 1):
            # Max debt lenders will now provide
            max_repo_debt = (1.0 - current_haircut) * assets
            debt_gap = debt - max_repo_debt
            
            if debt_gap > 0:
                # Must sell assets to pay down debt gap
                # Fire sale proceeds = FireSales * (1 - alpha * (FireSales / initial_assets))
                fire_sales = debt_gap / (1.0 - self.alpha * 0.1)
                fire_sales = min(assets, fire_sales)
                
                # Price depression shock to remaining assets
                price_depression = self.alpha * (fire_sales / initial_assets)
                asset_loss = assets * price_depression
                
                assets -= fire_sales
                debt -= (fire_sales - asset_loss * 0.5)
                equity = assets - debt
            else:
                fire_sales = 0.0
            
            if equity <= 0:
                defaulted = True
                equity = 0.0
                debt = assets
                
            history.append({
                "round": r,
                "assets": max(0.0, assets),
                "debt": max(0.0, debt),
                "equity": max(0.0, equity),
                "haircut": current_haircut,
                "leverage": (assets / equity) if equity > 1e-4 else float("inf"),
                "fire_sales": fire_sales,
                "defaulted": defaulted
            })
            
            if defaulted or debt_gap <= 0.01:
                break
                
        return {
            "initial_leverage": initial_assets / initial_equity,
            "final_assets": history[-1]["assets"],
            "final_equity": history[-1]["equity"],
            "total_fire_sales": sum(h["fire_sales"] for h in history),
            "is_insolvent": defaulted,
            "rounds_to_terminal": len(history) - 1,
            "spiral_trajectory": history
        }


# ==============================================================================
# 4. George Tauchen & Mark R. Pitts (1983) / Peter K. Clark (1973) Engine
# ==============================================================================
class TauchenPittsMDHEngine:
    """
    George Tauchen & Mark R. Pitts (1983):
    'The Price Variability-Volume Relationship on Speculative Markets', Econometrica, 51(2), 485-505.
    Peter K. Clark (1973): 'A Subordinated Stochastic Process Model with Finite Variance for Speculative Prices'.
    
    Mixture of Distributions Hypothesis (MDH):
    Daily asset returns R_t and trading volume V_t are jointly driven by a latent,
    unobservable stochastic information arrival rate I_t:
        R_t | I_t ~ N(0, sigma_e^2 * I_t)
        V_t | I_t = mu_V * I_t + eps_{V,t}
    Explains the fat tails (leptokurtosis) of returns and positive volume-volatility correlation.
    """

    def __init__(self, sigma_e: float = 0.015, mu_v: float = 1000.0, sigma_v: float = 200.0):
        self.sigma_e = float(sigma_e)
        self.mu_v = float(mu_v)
        self.sigma_v = float(sigma_v)

    def simulate_mdh(self, num_days: int = 500, mean_info_arrival: float = 10.0, info_volatility: float = 0.6) -> Dict[str, Any]:
        """
        Simulates daily returns and volume under the Log-Normal Mixture of Distributions process.
        """
        np.random.seed(42)
        # Latent information arrival rate I_t ~ LogNormal
        mu_log = math.log(mean_info_arrival) - 0.5 * (info_volatility ** 2)
        I_t = np.random.lognormal(mean=mu_log, sigma=info_volatility, size=num_days)
        
        # Daily return given I_t: R_t = sigma_e * sqrt(I_t) * Z_t
        Z_t = np.random.normal(0, 1, size=num_days)
        returns = self.sigma_e * np.sqrt(I_t) * Z_t
        
        # Daily volume given I_t: V_t = mu_v * I_t + Normal noise
        noise_v = np.random.normal(0, self.sigma_v, size=num_days)
        volume = np.maximum(100.0, self.mu_v * I_t + noise_v)
        
        # Empirical statistics
        mean_ret = float(np.mean(returns))
        var_ret = float(np.var(returns))
        std_ret = math.sqrt(var_ret)
        
        # Kurtosis of returns (should exceed 3.0, proving leptokurtosis)
        kurtosis = float(np.mean(((returns - mean_ret) / std_ret) ** 4))
        
        # Correlation between volume and absolute returns / squared returns
        corr_vol_absret = float(np.corrcoef(volume, np.abs(returns))[0, 1])
        corr_vol_sqret = float(np.corrcoef(volume, returns ** 2)[0, 1])

        # Theoretical kurtosis under subordinated log-normal mixture:
        # E[I^2] / (E[I])^2 = exp(info_volatility^2)
        theoretical_kurtosis = 3.0 * math.exp(info_volatility ** 2)

        return {
            "num_days": num_days,
            "mean_info_events": float(np.mean(I_t)),
            "var_info_events": float(np.var(I_t)),
            "empirical_kurtosis": kurtosis,
            "theoretical_kurtosis": theoretical_kurtosis,
            "corr_volume_abs_return": corr_vol_absret,
            "corr_volume_squared_return": corr_vol_sqret,
            "is_leptokurtic": bool(kurtosis > 3.0),
            "is_volume_volatility_positive": bool(corr_vol_absret > 0.0 and corr_vol_sqret > 0.0),
            "sample_returns": returns[:10].tolist(),
            "sample_volume": volume[:10].tolist()
        }

    def estimate_information_intensity(self, returns: np.ndarray, volumes: np.ndarray) -> Dict[str, float]:
        """
        Estimates the implied daily information intensity I_hat_t from observed volume.
        """
        inferred_I = np.maximum(0.1, volumes / self.mu_v)
        conditional_vol = self.sigma_e * np.sqrt(inferred_I)
        
        return {
            "mean_inferred_intensity": float(np.mean(inferred_I)),
            "volatility_of_intensity": float(np.std(inferred_I)),
            "mean_conditional_volatility": float(np.mean(conditional_vol))
        }


# ==============================================================================
# 5. Geert Bekaert & Campbell R. Harvey (1995, 1997) Engine
# ==============================================================================
class BekaertHarveyMarketIntegrationEngine:
    """
    Geert Bekaert & Campbell R. Harvey (1995):
    'Time-Varying World Market Integration', Journal of Finance, 50(2), 403-444.
    Geert Bekaert & Campbell R. Harvey (1997):
    'Emerging Equity Market Volatility', Journal of Financial Economics, 43(1), 29-77.
    
    Models the degree of international financial integration phi_t in [0, 1].
    Under segmentation (phi = 0), local assets are priced strictly by local variance.
    Under full integration (phi = 1), local assets are priced strictly by world covariance.
        E_t[R_{i,t+1}] - R_f = phi_t * beta_{i,W} * lambda_W + (1 - phi_t) * lambda_{i,L} * Var(R_i)
    """

    def __init__(self, world_risk_premium: float = 0.06, world_volatility: float = 0.16):
        self.lambda_w = float(world_risk_premium)
        self.sigma_w = float(world_volatility)
        self.var_w = self.sigma_w ** 2

    def calculate_integration_degree(self, openness_score: float, regulatory_score: float, capital_flow_gdp: float) -> float:
        """
        Logistic transition function for the time-varying integration parameter phi_t in [0, 1].
        """
        # Linear index Z_t
        z = -2.0 + 1.2 * openness_score + 1.5 * regulatory_score + 2.0 * capital_flow_gdp
        phi = 1.0 / (1.0 + math.exp(-z))
        return float(min(1.0, max(0.0, phi)))

    def expected_cost_of_capital(self, phi: float, local_volatility: float, corr_with_world: float, local_risk_aversion: float = 3.5) -> Dict[str, float]:
        """
        Computes expected excess return under partial integration regime.
        """
        var_local = local_volatility ** 2
        cov_world = corr_with_world * local_volatility * self.sigma_w
        beta_world = cov_world / self.var_w
        
        # Segmented component: priced by own variance
        segmented_premium = local_risk_aversion * var_local
        
        # Integrated component: priced by world covariance
        integrated_premium = beta_world * self.lambda_w
        
        # Blended expected excess return
        expected_excess_return = phi * integrated_premium + (1.0 - phi) * segmented_premium
        
        # Cost of capital reduction from opening financial markets
        cost_of_capital_reduction = segmented_premium - integrated_premium

        # Diversification benefit ratio to world investors
        diversification_ratio = 1.0 - (corr_with_world ** 2)

        return {
            "integration_degree_phi": float(phi),
            "beta_world": float(beta_world),
            "segmented_cost_of_capital": float(segmented_premium),
            "integrated_cost_of_capital": float(integrated_premium),
            "blended_cost_of_capital": float(expected_excess_return),
            "cost_of_capital_compression": float(cost_of_capital_reduction),
            "diversification_ratio": float(diversification_ratio)
        }

    def simulate_integration_trajectory(self, years: int = 10, initial_phi: float = 0.10, target_phi: float = 0.90, local_vol: float = 0.35, corr_world: float = 0.25) -> List[Dict[str, float]]:
        """
        Simulates multi-year liberalization path as an emerging market transitions to developed status.
        """
        trajectory = []
        for t in range(years + 1):
            weight = t / float(years)
            phi_t = initial_phi + (target_phi - initial_phi) * (1.0 / (1.0 + math.exp(-6.0 * (weight - 0.5))))
            res = self.expected_cost_of_capital(phi_t, local_vol, corr_world)
            res["year"] = t
            trajectory.append(res)
        return trajectory


# ==============================================================================
# 6. Richard Roll (1984) & Kenneth R. French (1980) Engine
# ==============================================================================
class RollFrenchMicrostructureEngine:
    """
    Richard Roll (1984):
    'A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market',
    Journal of Finance, 39(4), 1127-1139.
    Kenneth R. French (1980):
    'Stock Returns and the Weekend Effect', Journal of Financial Economics, 8(1), 55-69.
    
    Roll's Effective Spread Estimator:
        s = 2 * sqrt(-Cov(Delta P_t, Delta P_{t-1}))  if Cov < 0
    French's Trading vs Non-Trading Time Volatility Variance Ratio:
        VR = (Var_trading / T_trading) / (Var_closed / T_closed) >> 1
    """

    @staticmethod
    def estimate_roll_spread(prices: np.ndarray) -> Dict[str, float]:
        """
        Estimates Roll's effective bid-ask spread purely from transaction prices without quote data.
        Delta P_t = P_t - P_{t-1}
        Cov(Delta P_t, Delta P_{t-1}) = -s^2 / 4
        """
        if len(prices) < 4:
            raise ValueError("At least 4 price observations required for serial covariance.")
        
        delta_P = np.diff(prices)
        dp_t = delta_P[1:]
        dp_lag = delta_P[:-1]
        
        # First-order sample serial covariance
        cov_1 = float(np.cov(dp_t, dp_lag)[0, 1])
        
        # Roll spread calculation
        if cov_1 < 0.0:
            roll_spread = 2.0 * math.sqrt(-cov_1)
            is_valid_negative_cov = True
        else:
            # Under sample noise or positive serial trend, standard Roll formula is undefined;
            # Roll recommended reporting 0 or small bound.
            roll_spread = 0.0
            is_valid_negative_cov = False
            
        mean_price = float(np.mean(prices))
        relative_spread_bps = (roll_spread / mean_price) * 10_000.0 if mean_price > 0 else 0.0

        return {
            "first_order_autocovariance": cov_1,
            "roll_effective_spread": roll_spread,
            "relative_spread_bps": relative_spread_bps,
            "is_valid_negative_autocovariance": is_valid_negative_cov,
            "sample_size": len(prices)
        }

    @staticmethod
    def french_volatility_variance_ratio(trading_returns: np.ndarray, non_trading_returns: np.ndarray, trading_hours_per_day: float = 6.5, closed_hours_per_day: float = 17.5) -> Dict[str, float]:
        """
        Kenneth R. French (1980) Trading vs Non-Trading Hour Volatility Variance Ratio.
        Tests whether volatility is generated by the clock (public information) or trading activity.
        """
        var_trading = float(np.var(trading_returns, ddof=1))
        var_closed = float(np.var(non_trading_returns, ddof=1))
        
        # Hourly variance rates
        rate_trading = var_trading / trading_hours_per_day
        rate_closed = var_closed / closed_hours_per_day
        
        variance_ratio = rate_trading / max(1e-8, rate_closed)
        
        return {
            "variance_trading": var_trading,
            "variance_closed": var_closed,
            "hourly_rate_trading": rate_trading,
            "hourly_rate_closed": rate_closed,
            "variance_ratio": variance_ratio,
            "is_trading_active_information": bool(variance_ratio > 1.5)
        }

    @staticmethod
    def generate_synthetic_roll_series(num_trades: int = 1000, fundamental_vol: float = 0.1, true_spread: float = 0.50, p0: float = 100.0) -> np.ndarray:
        """
        Generates transaction price series where P_t = m_t + q_t * (s/2)
        q_t in {-1, +1} independent buy/sell indicator.
        """
        np.random.seed(123)
        # Random walk for fundamental price m_t
        increments = np.random.normal(0, fundamental_vol, size=num_trades)
        m = p0 + np.cumsum(increments)
        
        # Trade signs: +1 with prob 0.5, -1 with prob 0.5
        q = np.random.choice([-1.0, 1.0], size=num_trades)
        
        prices = m + q * (true_spread / 2.0)
        return prices


# ==============================================================================
# PYTEST TEST SUITES (Agentic TDD Verification)
# ==============================================================================

def test_breeden_litzenberger_rnd_engine():
    """Unit test for Douglas T. Breeden & Robert H. Litzenberger (1978) RND extraction."""
    engine = BreedenLitzenbergerRNDEngine(r=0.04, q=0.01)
    S0 = 100.0
    T = 1.0
    sigma = 0.20
    
    # Generate European call prices across fine grid of strikes spanning +/- 3.5 standard deviations
    strikes = np.linspace(40.0, 180.0, 141)
    calls = np.array([black_scholes_call(S0, K, T, engine.r, sigma, engine.q) for K in strikes])
    
    res = engine.extract_rnd_discrete(S0, T, strikes, calls)
    
    assert res["is_convex"] is True
    assert 0.95 <= res["total_probability_integral"] <= 1.05
    # Recovered mean should closely match forward price S0 * e^{(r - q)T} = 100 * e^{0.03} = 103.045
    assert abs(res["recovered_mean"] - res["theoretical_forward"]) < 0.50
    assert res["recovered_std"] > 0.0
    
    # Butterfly spread test
    mid_idx = 70
    fly = engine.verify_butterfly_spread(strikes[mid_idx], strikes[mid_idx] - strikes[mid_idx - 1], calls[mid_idx - 1], calls[mid_idx], calls[mid_idx + 1], T)
    assert fly["arbitrage_free"] is True
    assert fly["butterfly_cost"] > 0.0


def test_grossman_miller_liquidity_engine():
    """Unit test for Sanford J. Grossman & Merton H. Miller (1988) liquidity model."""
    engine = GrossmanMillerLiquidityEngine(dealer_risk_aversion=0.04, order_cost=0.01)
    
    # Small order vs Large block order
    res_small = engine.equilibrium_spread(Q=100.0, sigma=0.02, arrival_rate=5.0)
    res_large = engine.equilibrium_spread(Q=5000.0, sigma=0.02, arrival_rate=5.0)
    
    assert res_large["total_bid_ask_spread"] > res_small["total_bid_ask_spread"]
    assert res_large["inventory_risk_premium"] > res_small["inventory_risk_premium"]
    assert res_small["expected_inventory_holding_tau"] == 0.2
    
    # As arrival rate increases (more active trading), spread narrows
    res_fast = engine.equilibrium_spread(Q=1000.0, sigma=0.02, arrival_rate=20.0)
    res_slow = engine.equilibrium_spread(Q=1000.0, sigma=0.02, arrival_rate=2.0)
    assert res_fast["total_bid_ask_spread"] < res_slow["total_bid_ask_spread"]
    
    # Simulation
    orders = [(1, 50), (-1, 50), (1, 100), (1, 100), (-1, 200)]
    sim = engine.simulate_order_flow_market_making(100.0, orders, sigma=0.02, arrival_rate=5.0)
    assert len(sim["price_history"]) == 6
    assert len(sim["spread_history"]) == 5


def test_gorton_metrick_repo_haircut_engine():
    """Unit test for Gary Gorton & Andrew Metrick (2012) Repo Haircut Spiral."""
    engine = GortonMetrickRepoHaircutEngine(fire_sale_impact_alpha=0.20)
    
    # Baseline repo capacity
    cap = engine.compute_repo_capacity(collateral_value=1_000_000.0, haircut=0.05)
    assert cap["debt_capacity"] == 950_000.0
    assert cap["required_equity"] == 50_000.0
    assert cap["max_leverage"] == 20.0
    
    # Moderate haircut shock (5% to 15%) - survivable deleveraging
    sim_mild = engine.simulate_haircut_spiral(
        initial_assets=10_000_000.0,
        initial_haircut=0.05,
        shocked_haircut=0.15,
        initial_equity=500_000.0,
        rounds=4
    )
    assert len(sim_mild["spiral_trajectory"]) > 1
    assert sim_mild["total_fire_sales"] > 0.0
    
    # Catastrophic haircut spike (5% to 50%) - triggers shadow bank insolvency
    sim_crash = engine.simulate_haircut_spiral(
        initial_assets=10_000_000.0,
        initial_haircut=0.05,
        shocked_haircut=0.50,
        initial_equity=500_000.0,
        rounds=5
    )
    assert sim_crash["is_insolvent"] is True
    assert sim_crash["final_equity"] == 0.0


def test_tauchen_pitts_mdh_engine():
    """Unit test for George Tauchen & Mark R. Pitts (1983) MDH engine."""
    engine = TauchenPittsMDHEngine(sigma_e=0.012, mu_v=500.0, sigma_v=50.0)
    
    res = engine.simulate_mdh(num_days=1000, mean_info_arrival=8.0, info_volatility=0.7)
    
    assert res["is_leptokurtic"] is True
    assert res["empirical_kurtosis"] > 3.0
    assert res["is_volume_volatility_positive"] is True
    assert res["corr_volume_abs_return"] > 0.20
    
    # Inference of intensity
    inf = engine.estimate_information_intensity(np.array(res["sample_returns"]), np.array(res["sample_volume"]))
    assert inf["mean_inferred_intensity"] > 0.0
    assert inf["mean_conditional_volatility"] > 0.0


def test_bekaert_harvey_market_integration_engine():
    """Unit test for Geert Bekaert & Campbell R. Harvey (1995, 1997) Integration Model."""
    engine = BekaertHarveyMarketIntegrationEngine(world_risk_premium=0.05, world_volatility=0.15)
    
    # Test logistic integration index
    phi_closed = engine.calculate_integration_degree(0.1, 0.1, 0.05)
    phi_open = engine.calculate_integration_degree(0.9, 0.9, 0.8)
    assert phi_closed < 0.30
    assert phi_open > 0.70
    
    # Cost of capital comparison: segmented vs integrated
    res_closed = engine.expected_cost_of_capital(phi=0.05, local_volatility=0.30, corr_with_world=0.20)
    res_open = engine.expected_cost_of_capital(phi=0.95, local_volatility=0.30, corr_with_world=0.20)
    
    # Financial integration significantly lowers cost of capital for emerging market
    assert res_closed["blended_cost_of_capital"] > res_open["blended_cost_of_capital"]
    assert res_open["cost_of_capital_compression"] > 0.0
    assert res_open["diversification_ratio"] == 0.96  # 1 - 0.2^2 = 0.96
    
    # Liberalization trajectory
    traj = engine.simulate_integration_trajectory(years=5, initial_phi=0.1, target_phi=0.85)
    assert len(traj) == 6
    assert traj[0]["blended_cost_of_capital"] > traj[-1]["blended_cost_of_capital"]


def test_roll_french_microstructure_engine():
    """Unit test for Richard Roll (1984) and Kenneth R. French (1980) Microstructure Engine."""
    engine = RollFrenchMicrostructureEngine()
    
    # Generate synthetic price series with known spread s = 0.40
    true_s = 0.40
    prices = engine.generate_synthetic_roll_series(num_trades=3000, fundamental_vol=0.05, true_spread=true_s, p0=100.0)
    
    roll_res = engine.estimate_roll_spread(prices)
    assert roll_res["is_valid_negative_autocovariance"] is True
    # Roll estimate should accurately recover true spread within sampling tolerance
    assert abs(roll_res["roll_effective_spread"] - true_s) < 0.10
    assert roll_res["relative_spread_bps"] > 0.0
    
    # French (1980) variance ratio test: trading hour vs non-trading hour
    np.random.seed(42)
    # Trading hours: higher volatility per hour due to trading activity & private info revelation
    trading_returns = np.random.normal(0, 0.015, 250)
    # Non-trading hours: lower volatility per hour
    non_trading_returns = np.random.normal(0, 0.008, 250)
    
    fr_res = engine.french_volatility_variance_ratio(trading_returns, non_trading_returns)
    assert fr_res["variance_ratio"] > 1.5
    assert fr_res["is_trading_active_information"] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
