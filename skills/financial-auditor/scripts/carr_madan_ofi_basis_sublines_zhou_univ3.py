"""
Chapter 24 Financial Engineering & Quantitative Auditor Engine:
1. Carr-Madan (1999) Spanning Claims, Log-Contract VIX Replication & Breeden-Litzenberger (1978) State-Price Density Extraction
2. Cont-Kukanov-Stoikov (2014) Level-1 and Deep Order Flow Imbalance (OFI) Multi-Level Price Impact
3. US Treasury Basis Trade, Gross/Net Basis, Carry, Repo Leverage & Delivery Option CTD Analytics
4. Private Equity Subscription Lines of Credit (Capital Call Facilities) IRR Uplift & NAV Financing Mechanics
5. Zhou (2001) First-Passage Structural Credit Model with Jumps & Endogenous Short-Term Spread Resolution
6. Uniswap v3 Concentrated Liquidity Option Replication (Lambert-Neuman), Analytical Greeks & Dynamic Delta Hedging
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# =====================================================================
# 1. Carr-Madan (1999) Spanning & Breeden-Litzenberger (1978) Density
# =====================================================================

def carr_madan_log_contract_replication(
    forward: float,
    strikes: np.ndarray,
    call_prices: np.ndarray,
    put_prices: np.ndarray,
    r: float,
    t: float
) -> Dict[str, Any]:
    """
    Model-free implied variance extraction via Carr-Madan (1999) spanning formula for the log-contract:
    f(S_T) = -ln(S_T / F) => f''(K) = 1 / K^2.
    E^Q[-ln(S_T / F)] = e^{r*T} * [ \\int_0^F (1/K^2) P(K) dK + \\int_F^\\infty (1/K^2) C(K) dK ].
    This constitutes the mathematical foundation of the CBOE VIX Index methodology.
    """
    if forward <= 0.0 or t <= 0.0:
        raise ValueError("Forward price and expiration time must be strictly positive.")
    
    strikes = np.asarray(strikes, dtype=float)
    call_prices = np.asarray(call_prices, dtype=float)
    put_prices = np.asarray(put_prices, dtype=float)
    
    if len(strikes) < 3 or len(strikes) != len(call_prices) or len(strikes) != len(put_prices):
        raise ValueError("Strikes, calls, and puts must have matching lengths (at least 3 quotes).")
    
    sort_idx = np.argsort(strikes)
    strikes = strikes[sort_idx]
    call_prices = call_prices[sort_idx]
    put_prices = put_prices[sort_idx]
    
    # Identify OTM options: Puts for K < F, Calls for K >= F
    otm_prices = np.where(strikes < forward, put_prices, call_prices)
    weights = 1.0 / (strikes ** 2)
    integrand = weights * otm_prices
    
    # Numerical integration using trapezoidal rule
    integral_val = float(np.trapezoid(integrand, strikes))
    
    # Model-free implied variance (annualized)
    discount = math.exp(r * t)
    implied_variance = (2.0 * discount / t) * integral_val
    implied_volatility = math.sqrt(max(0.0, implied_variance))
    
    return {
        "forward": float(forward),
        "expiry_years": float(t),
        "integral_value": integral_val,
        "implied_variance": float(implied_variance),
        "implied_volatility": float(implied_volatility),
        "annualized_vix_points": float(implied_volatility * 100.0)
    }


def breeden_litzenberger_risk_neutral_density(
    strikes: np.ndarray,
    call_prices: np.ndarray,
    r: float,
    t: float
) -> Dict[str, Any]:
    """
    Extract the risk-neutral probability density function (RND) q(K) using Breeden-Litzenberger (1978):
    q(K) = e^{r*T} * d^2 C(K, T) / dK^2
    Calculated via second-order central finite differences across strike quotes.
    """
    strikes = np.asarray(strikes, dtype=float)
    call_prices = np.asarray(call_prices, dtype=float)
    
    if len(strikes) < 5 or len(strikes) != len(call_prices):
        raise ValueError("Requires at least 5 strike quotes to compute second derivatives.")
    
    sort_idx = np.argsort(strikes)
    K = strikes[sort_idx]
    C = call_prices[sort_idx]
    
    n = len(K)
    d2C = np.zeros(n - 2)
    mid_K = K[1:-1]
    
    discount = math.exp(r * t)
    for i in range(1, n - 1):
        h1 = K[i] - K[i - 1]
        h2 = K[i + 1] - K[i]
        # Non-uniform finite difference second derivative
        d2 = 2.0 * (C[i + 1] / (h2 * (h1 + h2)) - C[i] / (h1 * h2) + C[i - 1] / (h1 * (h1 + h2)))
        d2C[i - 1] = max(0.0, d2)  # Non-negative probability condition
    
    raw_density = discount * d2C
    # Normalize density so integral over dK equals ~1.0
    total_area = float(np.trapezoid(raw_density, mid_K))
    norm_density = raw_density / max(1e-9, total_area)
    
    # Statistical moments of extracted risk-neutral distribution
    mean_K = float(np.trapezoid(mid_K * norm_density, mid_K))
    var_K = float(np.trapezoid(((mid_K - mean_K) ** 2) * norm_density, mid_K))
    std_K = math.sqrt(max(0.0, var_K))
    
    if std_K > 1e-8:
        skew_K = float(np.trapezoid((((mid_K - mean_K) / std_K) ** 3) * norm_density, mid_K))
        kurt_K = float(np.trapezoid((((mid_K - mean_K) / std_K) ** 4) * norm_density, mid_K))
    else:
        skew_K, kurt_K = 0.0, 3.0
        
    return {
        "eval_strikes": mid_K.tolist(),
        "risk_neutral_density": norm_density.tolist(),
        "total_area": total_area,
        "mean_strike": mean_K,
        "std_strike": std_K,
        "implied_skewness": skew_K,
        "implied_kurtosis": kurt_K
    }


# =====================================================================
# 2. Cont-Kukanov-Stoikov (2014) OFI & Multi-Level Deep OFI
# =====================================================================

def calculate_level1_ofi(
    bid_prices: np.ndarray,
    bid_sizes: np.ndarray,
    ask_prices: np.ndarray,
    ask_sizes: np.ndarray
) -> np.ndarray:
    """
    Cont, Kukanov & Stoikov (2014) Level-1 Order Flow Imbalance (OFI):
    OFI_n = I{P^b_n >= P^b_{n-1}} V^b_n - I{P^b_n <= P^b_{n-1}} V^b_{n-1}
            - I{P^a_n <= P^a_{n-1}} V^a_n + I{P^a_n >= P^a_{n-1}} V^a_{n-1}
    """
    bp = np.asarray(bid_prices, dtype=float)
    bv = np.asarray(bid_sizes, dtype=float)
    ap = np.asarray(ask_prices, dtype=float)
    av = np.asarray(ask_sizes, dtype=float)
    
    n = len(bp)
    if not (len(bv) == n and len(ap) == n and len(av) == n):
        raise ValueError("Price and size arrays must have identical length.")
    if n < 2:
        return np.zeros(0)
    
    ofi = np.zeros(n - 1)
    for i in range(1, n):
        # Bid side contribution
        if bp[i] > bp[i - 1]:
            delta_bid = bv[i]
        elif bp[i] == bp[i - 1]:
            delta_bid = bv[i] - bv[i - 1]
        else:
            delta_bid = -bv[i - 1]
            
        # Ask side contribution
        if ap[i] < ap[i - 1]:
            delta_ask = av[i]
        elif ap[i] == ap[i - 1]:
            delta_ask = av[i] - av[i - 1]
        else:
            delta_ask = -av[i - 1]
            
        ofi[i - 1] = delta_bid - delta_ask
        
    return ofi


def calculate_deep_ofi(
    level_bids_p: np.ndarray,
    level_bids_v: np.ndarray,
    level_asks_p: np.ndarray,
    level_asks_v: np.ndarray,
    decay_alpha: float = 0.5
) -> Dict[str, Any]:
    """
    Multi-level Deep OFI across K limit order book depths with distance decay weighting:
    w_k = exp(-alpha * (k-1)) / sum(w)
    Integrated Deep OFI = sum_{k=1}^K w_k * OFI^{(k)}
    Estimates immediate price impact beta: Delta P_t = beta * Deep_OFI_t + eps.
    """
    # Shapes: (T, K)
    b_p = np.asarray(level_bids_p, dtype=float)
    b_v = np.asarray(level_bids_v, dtype=float)
    a_p = np.asarray(level_asks_p, dtype=float)
    a_v = np.asarray(level_asks_v, dtype=float)
    
    T, K = b_p.shape
    if T < 2 or K < 1:
        raise ValueError("Must have at least 2 time steps and 1 depth level.")
        
    # Calculate OFI per level
    level_ofis = np.zeros((T - 1, K))
    for k in range(K):
        level_ofis[:, k] = calculate_level1_ofi(b_p[:, k], b_v[:, k], a_p[:, k], a_v[:, k])
        
    # Exponential decay weights across book depth
    k_indices = np.arange(K)
    raw_weights = np.exp(-decay_alpha * k_indices)
    weights = raw_weights / np.sum(raw_weights)
    
    deep_ofi = np.dot(level_ofis, weights)
    
    # Mid-price change
    mid_prices = 0.5 * (b_p[:, 0] + a_p[:, 0])
    delta_mid = mid_prices[1:] - mid_prices[:-1]
    
    # OLS estimation of price impact coefficient: delta_mid = beta * deep_ofi
    var_ofi = np.var(deep_ofi)
    if var_ofi > 1e-12:
        beta = float(np.cov(delta_mid, deep_ofi)[0, 1] / var_ofi)
        corr = float(np.corrcoef(delta_mid, deep_ofi)[0, 1])
        r_squared = float(corr ** 2) if not math.isnan(corr) else 0.0
    else:
        beta, r_squared = 0.0, 0.0
        
    return {
        "num_levels": int(K),
        "num_observations": int(T - 1),
        "decay_weights": weights.tolist(),
        "deep_ofi_series": deep_ofi.tolist(),
        "price_impact_beta": beta,
        "r_squared": r_squared
    }


# =====================================================================
# 3. US Treasury Basis Trade & CTD Analytics
# =====================================================================

def treasury_basis_trade_analysis(
    cash_price: float,
    futures_price: float,
    conversion_factor: float,
    repo_rate: float,
    coupon_rate: float,
    days_to_delivery: float,
    leverage: float = 50.0
) -> Dict[str, Any]:
    """
    US Treasury Cash-Futures Basis Trade relative value analytics:
    - Gross Basis = Cash Price - (Futures Price * Conversion Factor)
    - Carry = (Coupon Income - Repo Financing Cost) over holding period
    - Net Basis (Basis to Carry) = Gross Basis - Carry
    - Implied Repo Rate (IRR) = (Futures Price * CF + Coupon - Cash Price) / Cash Price * (360 / Days)
    - Leveraged ROE under repo leverage (e.g. 50x-100x).
    """
    if cash_price <= 0.0 or futures_price <= 0.0 or conversion_factor <= 0.0 or days_to_delivery <= 0:
        raise ValueError("Prices, conversion factor, and delivery days must be positive.")
    
    year_fraction = days_to_delivery / 360.0
    gross_basis = cash_price - (futures_price * conversion_factor)
    
    # Carry calculation
    coupon_income = cash_price * coupon_rate * year_fraction
    repo_interest = cash_price * repo_rate * year_fraction
    net_carry = coupon_income - repo_interest
    
    net_basis = gross_basis - net_carry
    
    # Implied Repo Rate (breakeven financing rate of the cash leg)
    delivered_value = (futures_price * conversion_factor) + coupon_income
    irr = ((delivered_value - cash_price) / cash_price) * (1.0 / year_fraction)
    
    # Hedge Fund Economics with Repo Leverage
    # Equity margin required per $100 cash face value
    margin_fraction = 1.0 / leverage
    equity_deployed = cash_price * margin_fraction
    
    # Holding period arbitrage profit if held to delivery (assuming net basis converges to 0 at delivery)
    # Arbitrage gain = -Net Basis = Net Carry - Gross Basis
    arbitrage_profit = -net_basis
    levered_roe_period = arbitrage_profit / equity_deployed
    annualized_levered_roe = levered_roe_period * (360.0 / days_to_delivery)
    
    # Margin call sensitivity: basis widening of 10 bps on notional
    basis_widening_shock_bps = 10.0
    drawdown_on_equity = (basis_widening_shock_bps * 0.0001 * cash_price) / equity_deployed
    
    return {
        "gross_basis": float(gross_basis),
        "net_carry": float(net_carry),
        "net_basis": float(net_basis),
        "implied_repo_rate": float(irr),
        "repo_borrowing_rate": float(repo_rate),
        "irr_spread_over_repo_bps": float((irr - repo_rate) * 10000.0),
        "equity_deployed_per_bond": float(equity_deployed),
        "leveraged_roe_annualized": float(annualized_levered_roe),
        "margin_call_equity_drawdown_pct": float(drawdown_on_equity * 100.0)
    }


# =====================================================================
# 4. Private Equity Subscription Lines & NAV Financing Mechanics
# =====================================================================

def _compute_irr(cash_flows: List[Tuple[float, float]], max_iter: int = 100) -> float:
    """
    Computes annualized internal rate of return (IRR) from (time_years, amount) cash flows using Newton-Raphson.
    """
    r = 0.10
    for _ in range(max_iter):
        npv = sum(cf / ((1.0 + r) ** t) for t, cf in cash_flows)
        d_npv = sum(-t * cf / ((1.0 + r) ** (t + 1)) for t, cf in cash_flows)
        if abs(d_npv) < 1e-12:
            break
        r_next = r - npv / d_npv
        if abs(r_next - r) < 1e-7:
            return float(r_next)
        r = r_next
        if r < -0.99:
            r = -0.99
    return float(r)


def subscription_line_irr_impact(
    capital_invested: float,
    exit_proceeds: float,
    investment_horizon_years: float,
    subline_delay_years: float,
    subline_interest_rate: float
) -> Dict[str, Any]:
    """
    Analyzes how Private Equity Subscription Lines of Credit (Capital Call Facilities)
    artificially inflate Net Fund IRR by delaying LP capital calls while causing facility fee drag on MoIC.
    """
    if capital_invested <= 0.0 or exit_proceeds <= 0.0 or investment_horizon_years <= subline_delay_years:
        raise ValueError("Invalid cash flow parameters.")
        
    # Scenario A: Organic Capital Calls (No Subscription Line)
    flows_organic = [
        (0.0, -capital_invested),
        (investment_horizon_years, exit_proceeds)
    ]
    irr_organic = _compute_irr(flows_organic)
    moic_organic = exit_proceeds / capital_invested
    
    # Scenario B: Sub-Line Used (LPs funded at t = subline_delay_years)
    borrowing_cost = capital_invested * subline_interest_rate * subline_delay_years
    lp_delayed_contribution = capital_invested + borrowing_cost
    
    flows_subline = [
        (subline_delay_years, -lp_delayed_contribution),
        (investment_horizon_years, exit_proceeds)
    ]
    irr_subline = _compute_irr(flows_subline)
    moic_subline = exit_proceeds / lp_delayed_contribution
    
    irr_uplift_bps = (irr_subline - irr_organic) * 10000.0
    moic_drag = moic_organic - moic_subline
    
    return {
        "organic_net_irr": float(irr_organic),
        "subline_net_irr": float(irr_subline),
        "irr_artificial_uplift_bps": float(irr_uplift_bps),
        "organic_moic": float(moic_organic),
        "subline_moic": float(moic_subline),
        "moic_fee_drag": float(moic_drag),
        "total_credit_facility_interest": float(borrowing_cost)
    }


def nav_facility_borrowing_capacity(
    portfolio_ebitda: List[float],
    portfolio_multiples: List[float],
    portfolio_senior_debt: List[float],
    max_ltv: float = 0.20
) -> Dict[str, Any]:
    """
    NAV Financing (Fund-Level Net Asset Value Borrowing Capacity):
    Computes total portfolio Net Asset Value (NAV) and maximum non-recourse fund debt capacity.
    """
    if len(portfolio_ebitda) != len(portfolio_multiples) or len(portfolio_ebitda) != len(portfolio_senior_debt):
        raise ValueError("Portfolio arrays must match in dimension.")
        
    ebitda = np.asarray(portfolio_ebitda, dtype=float)
    mult = np.asarray(portfolio_multiples, dtype=float)
    debt = np.asarray(portfolio_senior_debt, dtype=float)
    
    enterprise_values = ebitda * mult
    equity_values = np.maximum(0.0, enterprise_values - debt)
    
    total_ev = float(np.sum(enterprise_values))
    total_senior_debt = float(np.sum(debt))
    total_nav = float(np.sum(equity_values))
    
    max_nav_loan = total_nav * max_ltv
    
    return {
        "total_portfolio_enterprise_value": total_ev,
        "total_portfolio_senior_debt": total_senior_debt,
        "fund_net_asset_value": total_nav,
        "max_allowed_ltv": float(max_ltv),
        "max_nav_facility_capacity": float(max_nav_loan),
        "effective_overall_leverage_ratio": float((total_senior_debt + max_nav_loan) / max(1.0, total_ev))
    }


# =====================================================================
# 5. Zhou (2001) Structural Credit Model with Jumps
# =====================================================================

def zhou_jump_default_probability_and_spread(
    v0: float,
    barrier_vb: float,
    mu: float,
    sigma: float,
    lambda_jump: float,
    mu_jump: float,
    sigma_jump: float,
    maturity: float,
    r_free: float,
    recovery_rate: float = 0.40
) -> Dict[str, Any]:
    """
    Zhou (2001) First-Passage Structural Credit Model with Poisson Jumps:
    Asset value: dV/V = (mu - lambda*nu) dt + sigma dW + (Y - 1) dq.
    Solves the short-term credit spread zero-limit puzzle of classical Merton/Black-Cox models
    by generating strictly positive default intensity even as T -> 0 via downward jump risk.
    """
    if v0 <= barrier_vb or barrier_vb <= 0.0 or maturity <= 0.0:
        raise ValueError("v0 must exceed barrier_vb and maturity must be strictly positive.")
        
    distance_to_default = math.log(v0 / barrier_vb)
    
    # Expected jump size nu = E[Y - 1] where ln(Y) ~ N(mu_jump, sigma_jump^2)
    nu = math.exp(mu_jump + 0.5 * (sigma_jump ** 2)) - 1.0
    drift_compensated = mu - lambda_jump * nu - 0.5 * (sigma ** 2)
    
    # 1. Classical continuous first-passage probability (Black-Cox component)
    d1 = (distance_to_default + drift_compensated * maturity) / (sigma * math.sqrt(maturity))
    d2 = (distance_to_default - drift_compensated * maturity) / (sigma * math.sqrt(maturity))
    factor = math.exp(2.0 * drift_compensated * distance_to_default / (sigma ** 2)) if abs(drift_compensated) > 1e-6 else 1.0
    
    def n_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
        
    pd_continuous = (1.0 - n_cdf(d1)) + factor * (1.0 - n_cdf(d2))
    pd_continuous = max(0.0, min(1.0, float(pd_continuous)))
    
    # 2. Sudden downward jump through the barrier (Zhou jump component)
    prob_jump_occurs = 1.0 - math.exp(-lambda_jump * maturity)
    prob_jump_breaches = n_cdf((-distance_to_default - mu_jump) / sigma_jump) if sigma_jump > 1e-6 else (1.0 if -distance_to_default >= mu_jump else 0.0)
    
    pd_jump = prob_jump_occurs * prob_jump_breaches
    
    # Combined default probability
    total_pd = pd_continuous + pd_jump - (pd_continuous * pd_jump)
    total_pd = max(0.0, min(0.9999, total_pd))
    
    # Implied par credit spread under fractional recovery of treasury (RT)
    implied_spread = -(1.0 / maturity) * math.log(1.0 - (1.0 - recovery_rate) * total_pd)
    
    # Instantaneous short-term credit spread as T -> 0
    instantaneous_short_spread = lambda_jump * (1.0 - recovery_rate) * prob_jump_breaches
    
    return {
        "v0": float(v0),
        "barrier_vb": float(barrier_vb),
        "maturity_years": float(maturity),
        "continuous_default_prob": float(pd_continuous),
        "jump_default_prob": float(pd_jump),
        "total_default_probability": float(total_pd),
        "implied_credit_spread_bps": float(implied_spread * 10000.0),
        "short_term_spread_limit_bps": float(instantaneous_short_spread * 10000.0),
        "merton_zero_limit_solved": bool(instantaneous_short_spread > 0.0001)
    }


# =====================================================================
# 6. Uniswap v3 Option Equivalence & Dynamic Delta Hedging
# =====================================================================

def uniswap_v3_option_replication_and_greeks(
    current_price: float,
    lower_price: float,
    upper_price: float,
    liquidity: float
) -> Dict[str, Any]:
    """
    Lambert (2021) / Neuman (2022) Option Equivalence of Uniswap v3 concentrated liquidity:
    Between [P_a, P_b], the LP position is mathematically identical to a short put (below P_a),
    a short call (above P_b), with continuous fractional delta and severe negative gamma:
    Delta(P) = L * (1 / sqrt(P) - 1 / sqrt(P_b))
    Gamma(P) = -L / (2 * P^{1.5}) < 0
    Theta(P) = Swap Fees accrued per unit time > 0.
    """
    if lower_price >= upper_price or lower_price <= 0.0 or current_price <= 0.0 or liquidity <= 0.0:
        raise ValueError("Invalid price bounds or negative liquidity.")
        
    sqrt_p = math.sqrt(current_price)
    sqrt_a = math.sqrt(lower_price)
    sqrt_b = math.sqrt(upper_price)
    
    if current_price <= lower_price:
        amount_x = liquidity * (1.0 / sqrt_a - 1.0 / sqrt_b)
        amount_y = 0.0
        delta = amount_x
        gamma = 0.0
    elif current_price >= upper_price:
        amount_x = 0.0
        amount_y = liquidity * (sqrt_b - sqrt_a)
        delta = 0.0
        gamma = 0.0
    else:
        amount_x = liquidity * (1.0 / sqrt_p - 1.0 / sqrt_b)
        amount_y = liquidity * (sqrt_p - sqrt_a)
        delta = liquidity * (1.0 / sqrt_p - 1.0 / sqrt_b)
        gamma = -liquidity / (2.0 * (current_price ** 1.5))
        
    portfolio_value_numeraire = (amount_x * current_price) + amount_y
    
    return {
        "current_price": float(current_price),
        "range": [float(lower_price), float(upper_price)],
        "amount_x": float(amount_x),
        "amount_y": float(amount_y),
        "portfolio_value": float(portfolio_value_numeraire),
        "delta": float(delta),
        "gamma": float(gamma),
        "is_in_range": bool(lower_price <= current_price <= upper_price)
    }


def uniswap_v3_dynamic_delta_hedge_simulation(
    prices: np.ndarray,
    lower_price: float,
    upper_price: float,
    liquidity: float,
    fee_rate: float = 0.003,
    volume_per_step: float = 10000.0,
    rebalance_band_delta: float = 0.05
) -> Dict[str, Any]:
    """
    Simulates a dynamic delta-neutral hedging strategy against Uniswap v3 short gamma LP:
    Uses perpetual futures short contracts to offset positive token X delta:
    Target Perp Position = -Delta(P_t).
    Harvests pure swap fees while immunizing directional price risk within tolerance bands.
    """
    prices = np.asarray(prices, dtype=float)
    if len(prices) < 2:
        raise ValueError("Requires at least 2 price steps.")
        
    initial_state = uniswap_v3_option_replication_and_greeks(prices[0], lower_price, upper_price, liquidity)
    initial_value = initial_state["portfolio_value"]
    
    lp_values = [initial_value]
    hedge_pnls = [0.0]
    cumulative_fees = [0.0]
    total_strategy_values = [initial_value]
    
    current_hedge_pos = -initial_state["delta"]
    total_hedge_pnl = 0.0
    total_fees = 0.0
    num_rebalances = 0
    
    for t in range(1, len(prices)):
        p_prev = prices[t - 1]
        p_curr = prices[t]
        
        state = uniswap_v3_option_replication_and_greeks(p_curr, lower_price, upper_price, liquidity)
        lp_val = state["portfolio_value"]
        
        price_diff = p_curr - p_prev
        step_hedge_pnl = current_hedge_pos * price_diff
        total_hedge_pnl += step_hedge_pnl
        
        if state["is_in_range"]:
            step_fee = volume_per_step * fee_rate * (liquidity / max(1.0, liquidity + 50000.0))
            total_fees += step_fee
            
        target_hedge = -state["delta"]
        if abs(target_hedge - current_hedge_pos) > (abs(state["delta"]) * rebalance_band_delta + 1e-5):
            current_hedge_pos = target_hedge
            num_rebalances += 1
            
        strat_val = lp_val + total_hedge_pnl + total_fees
        lp_values.append(lp_val)
        hedge_pnls.append(total_hedge_pnl)
        cumulative_fees.append(total_fees)
        total_strategy_values.append(strat_val)
        
    lp_return_unhedged = (lp_values[-1] - initial_value) / initial_value
    strategy_return_hedged = (total_strategy_values[-1] - initial_value) / initial_value
    
    return {
        "num_steps": len(prices),
        "num_rebalances": int(num_rebalances),
        "final_unhedged_lp_value": float(lp_values[-1]),
        "final_hedged_strategy_value": float(total_strategy_values[-1]),
        "total_swap_fees_collected": float(total_fees),
        "total_hedge_pnl": float(total_hedge_pnl),
        "unhedged_lp_return_pct": float(lp_return_unhedged * 100.0),
        "hedged_strategy_return_pct": float(strategy_return_hedged * 100.0),
        "hedging_delta_benefit": float((strategy_return_hedged - lp_return_unhedged) * 100.0)
    }
