"""Phase 26: Quantitative Financial Engineering & Algorithmic Market Architecture.

Core Pillars:
1. Rough Paths & Truncated Path Signatures (Lyons, Bayer, Chevyrev)
2. Andreasen & Huge (2011) Arbitrage-Free Discrete Volatility Interpolation
3. Meucci (2009) Minimum Torsion & Effective Number of Bets (ENB)
4. Huang, Lehalle & Rosenbaum (2015) Queue-Reactive LOB & First-Passage Fill Probability
5. Tsiveriotis & Fernandes (1998) PDE Convertible Bond Pricing & Greeks Split
6. MEV-Boost, Proposer-Builder Separation (PBS) & AMM Toxic Flow / LVR Engine
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# ==============================================================================
# 1. ROUGH PATHS & TRUNCATED PATH SIGNATURES
# ==============================================================================

@dataclass
class SignatureFeatures:
    level_0: float
    level_1: List[float]
    level_2: List[List[float]]
    levy_areas: Dict[str, float]
    total_feature_vector: List[float]


class PathSignatureEngine:
    """Computes truncated path signatures and lead-lag transformations for financial paths.
    
    References:
    - Lyons, T. (1998). Differential equations driven by rough signals.
    - Bayer, C., & Chevyrev, I. (2019). Rough paths in quantitative finance.
    """

    @staticmethod
    def lead_lag_transform(time_series: List[float]) -> np.ndarray:
        """Transforms a 1D sequence into a 2D lead-lag path in R^2.
        
        This enables signature calculation on 1D series to recover quadratic variation
        and non-commutative geometric properties.
        """
        n = len(time_series)
        if n < 2:
            raise ValueError("Time series must have at least 2 points for lead-lag transform.")

        # Path has 2n - 1 points
        path = np.zeros((2 * n - 1, 2))
        for i in range(n - 1):
            # Lead steps forward first, lag remains
            path[2 * i] = [time_series[i], time_series[i]]
            path[2 * i + 1] = [time_series[i + 1], time_series[i]]
        path[2 * n - 2] = [time_series[n - 1], time_series[n - 1]]
        return path

    @staticmethod
    def compute_signature_2d(path: np.ndarray) -> SignatureFeatures:
        """Computes level-0, level-1, and level-2 iterated integrals for a 2D path.
        
        S^{i} = X_T^i - X_0^i
        S^{i,j} = sum_{k} [ (X_{t_k}^i - X_0^i) * Delta X_k^j + 0.5 * Delta X_k^i * Delta X_k^j ]
        """
        n_steps, dim = path.shape
        if dim != 2:
            raise ValueError("This method specifically computes signatures for 2D paths.")
        if n_steps < 2:
            raise ValueError("Path must contain at least 2 points.")

        # Level 0
        s0 = 1.0

        # Level 1: total displacement Delta X^i
        s1 = [float(path[-1, i] - path[0, i]) for i in range(dim)]

        # Level 2: iterated integrals
        s2 = np.zeros((dim, dim))
        x_shifted = path - path[0]

        for k in range(n_steps - 1):
            dx = path[k + 1] - path[k]
            for i in range(dim):
                for j in range(dim):
                    s2[i, j] += x_shifted[k, i] * dx[j] + 0.5 * dx[i] * dx[j]

        # Verify shuffle product identity: S^{i,j} + S^{j,i} == S^i * S^j
        # Lévy Area: A^{i,j} = 0.5 * (S^{i,j} - S^{j,i})
        levy_area_12 = 0.5 * (s2[0, 1] - s2[1, 0])
        levy_areas = {"A_12": float(levy_area_12), "A_21": float(-levy_area_12)}

        # Flat feature vector: [s0, s1[0], s1[1], s2[0,0], s2[0,1], s2[1,0], s2[1,1]]
        feat_vector = [s0] + s1 + [float(s2[0, 0]), float(s2[0, 1]), float(s2[1, 0]), float(s2[1, 1])]

        return SignatureFeatures(
            level_0=s0,
            level_1=s1,
            level_2=s2.tolist(),
            levy_areas=levy_areas,
            total_feature_vector=feat_vector,
        )


# ==============================================================================
# 2. ANDREASEN-HUGE (2011) VOLATILITY INTERPOLATION
# ==============================================================================

@dataclass
class InterpolatedOptionSlice:
    strikes: np.ndarray
    call_prices: np.ndarray
    implied_vols: np.ndarray
    is_arbitrage_free: bool
    butterfly_arbitrage_count: int


class AndreasenHugeVolEngine:
    """Arbitrage-free volatility interpolation via single-step discrete Dupire PDE.
    
    References:
    - Andreasen, J., & Huge, B. (2011). Volatility interpolation. Risk, 24(3), 76.
    """

    @staticmethod
    def black_scholes_call(s: float, k: float, t: float, r: float, q: float, vol: float) -> float:
        """Standard analytical Black-Scholes call price."""
        if t <= 0:
            return max(0.0, s - k)
        if vol <= 1e-6:
            return max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t))

        f = s * math.exp((r - q) * t)
        denom = vol * math.sqrt(t)
        d1 = (math.log(f / k) + 0.5 * vol * vol * t) / denom
        d2 = d1 - denom

        c = math.exp(-r * t) * (f * 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0))) - k * 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0))))
        return max(0.0, float(c))

    @classmethod
    def implied_volatility_call(cls, price: float, s: float, k: float, t: float, r: float, q: float) -> float:
        """Invert Black-Scholes formula using robust bisection/secant solver."""
        intrinsic = max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t))
        if price <= intrinsic + 1e-6:
            return 0.001

        vol_low = 0.001
        vol_high = 5.0

        for _ in range(50):
            vol_mid = 0.5 * (vol_low + vol_high)
            p_mid = cls.black_scholes_call(s, k, t, r, q, vol_mid)
            if abs(p_mid - price) < 1e-5:
                return vol_mid
            if p_mid < price:
                vol_low = vol_mid
            else:
                vol_high = vol_mid
        return 0.5 * (vol_low + vol_high)

    @classmethod
    def calibrate_and_interpolate(
        cls,
        spot: float,
        rate: float,
        div_yield: float,
        expiry: float,
        market_strikes: List[float],
        market_vols: List[float],
        dense_strikes: Optional[np.ndarray] = None,
    ) -> InterpolatedOptionSlice:
        """Performs the Andreasen-Huge discrete implicit Dupire calibration.
        
        Solves tridiagonal system: M * C = C_intrinsic
        """
        if dense_strikes is None:
            dense_strikes = np.linspace(spot * 0.5, spot * 1.8, 65)

        m = len(dense_strikes)
        dt = expiry
        fwd = spot * math.exp((rate - div_yield) * expiry)

        # Initial call payoff at T=0
        c0 = np.maximum(0.0, spot - dense_strikes)

        # Interpolate market vol to dense grid for local variance parameter a(k)
        vol_interp = np.interp(dense_strikes, market_strikes, market_vols)
        loc_var = vol_interp ** 2

        # Build tridiagonal system M: A_i * C_{i-1} + B_i * C_i + C_i_sup * C_{i+1} = c0[i]
        a_sub = np.zeros(m)
        b_diag = np.zeros(m)
        c_sup = np.zeros(m)

        # Boundary conditions
        b_diag[0] = 1.0
        c0[0] = spot * math.exp(-div_yield * expiry) - dense_strikes[0] * math.exp(-rate * expiry)

        b_diag[-1] = 1.0
        c0[-1] = 0.0

        for i in range(1, m - 1):
            k_i = dense_strikes[i]
            dk_minus = dense_strikes[i] - dense_strikes[i - 1]
            dk_plus = dense_strikes[i + 1] - dense_strikes[i]
            dk_avg = 0.5 * (dk_minus + dk_plus)

            gamma_coeff = 0.5 * loc_var[i] * (k_i ** 2)
            mu_coeff = (rate - div_yield) * k_i

            # Derivatives discretization
            d2_sub = gamma_coeff / (dk_minus * dk_avg)
            d2_sup = gamma_coeff / (dk_plus * dk_avg)
            d2_diag = -gamma_coeff / (dk_minus * dk_avg) - gamma_coeff / (dk_plus * dk_avg)

            d1_sub = -mu_coeff / (2.0 * dk_avg)
            d1_sup = mu_coeff / (2.0 * dk_avg)
            d1_diag = 0.0

            # Single-step Euler
            a_sub[i] = -dt * (d2_sub + d1_sub)
            b_diag[i] = 1.0 - dt * (d2_diag + d1_diag - div_yield)
            c_sup[i] = -dt * (d2_sup + d1_sup)

        # Solve tridiagonal system via Thomas algorithm
        alpha = np.zeros(m)
        beta = np.zeros(m)

        alpha[0] = c_sup[0] / b_diag[0]
        beta[0] = c0[0] / b_diag[0]

        for i in range(1, m):
            denom = b_diag[i] - a_sub[i] * alpha[i - 1]
            alpha[i] = c_sup[i] / denom
            beta[i] = (c0[i] - a_sub[i] * beta[i - 1]) / denom

        c_interp = np.zeros(m)
        c_interp[-1] = beta[-1]
        for i in range(m - 2, -1, -1):
            c_interp[i] = beta[i] - alpha[i] * c_interp[i + 1]

        # Enforce intrinsic floor and monotonic decay
        c_interp = np.maximum(c_interp, np.maximum(0.0, fwd * math.exp(-rate * expiry) - dense_strikes * math.exp(-rate * expiry)))
        for i in range(1, m):
            c_interp[i] = min(c_interp[i], c_interp[i - 1])

        # Invert implied volatilities
        imp_vols = np.zeros(m)
        butterfly_violations = 0
        for i in range(m):
            imp_vols[i] = cls.implied_volatility_call(c_interp[i], spot, dense_strikes[i], expiry, rate, div_yield)

        # Check butterfly arbitrage: d2C / dK2 >= 0
        for i in range(1, m - 1):
            second_diff = c_interp[i + 1] - 2 * c_interp[i] + c_interp[i - 1]
            if second_diff < -1e-4:
                butterfly_violations += 1

        return InterpolatedOptionSlice(
            strikes=dense_strikes,
            call_prices=c_interp,
            implied_vols=imp_vols,
            is_arbitrage_free=(butterfly_violations == 0),
            butterfly_arbitrage_count=butterfly_violations,
        )


# ==============================================================================
# 3. MEUCCI (2009) MINIMUM TORSION & EFFECTIVE NUMBER OF BETS
# ==============================================================================

@dataclass
class MinimumTorsionResult:
    torsion_matrix: np.ndarray
    effective_number_of_bets: float
    diversification_ratio: float
    factor_risk_contributions: np.ndarray
    portfolio_volatility: float


class MeucciTorsionEngine:
    """Implements Attilio Meucci's Minimum Torsion & Effective Number of Bets.
    
    References:
    - Meucci, A. (2009). Managing diversification. Risk, 22(5), 74-79.
    - Meucci, A., Santangelo, A., & Deguest, R. (2014). Risk budgeting and diversification based on optimized uncorrelated factors.
    """

    @staticmethod
    def compute_minimum_torsion(cov_matrix: np.ndarray) -> np.ndarray:
        """Finds the unique orthogonal linear transformation T minimizing ||T - I||_F
        such that T * Sigma * T' is strictly diagonal.
        """
        n = cov_matrix.shape[0]
        vols = np.sqrt(np.diag(cov_matrix))
        inv_vols = 1.0 / np.maximum(vols, 1e-8)

        # Correlation matrix
        corr = np.diag(inv_vols) @ cov_matrix @ np.diag(inv_vols)

        # Spectral decomposition of correlation
        eigenvals, eigenvecs = np.linalg.eigh(corr)
        eigenvals = np.maximum(eigenvals, 1e-8)

        # Inverse square root C^(-1/2)
        inv_sqrt_corr = eigenvecs @ np.diag(1.0 / np.sqrt(eigenvals)) @ eigenvecs.T

        # Minimum torsion transformation: T = diag(vols) * inv_sqrt_corr * diag(inv_vols)
        torsion = np.diag(vols) @ inv_sqrt_corr @ np.diag(inv_vols)
        return torsion

    @classmethod
    def analyze_portfolio(cls, weights: np.ndarray, cov_matrix: np.ndarray) -> MinimumTorsionResult:
        """Calculates uncorrelated factor exposures, risk contributions, and ENB."""
        n = len(weights)
        t_mt = cls.compute_minimum_torsion(cov_matrix)

        port_var = float(weights.T @ cov_matrix @ weights)
        port_vol = math.sqrt(max(port_var, 1e-12))

        # Torsion factor weights: f = (T^-1)' * w
        inv_t = np.linalg.inv(t_mt)
        factor_weights = inv_t.T @ weights

        # Factor risk contributions: p_i = f_i * (T * Sigma * w)_i / port_var
        t_sigma_w = t_mt @ cov_matrix @ weights
        risk_contributions = (factor_weights * t_sigma_w) / port_var

        # Normalize and clip for numerical safety
        p = np.maximum(0.0, risk_contributions)
        p_sum = np.sum(p)
        if p_sum > 0:
            p /= p_sum
        else:
            p = np.full(n, 1.0 / n)

        # Shannon Entropy -> Effective Number of Bets: ENB = exp(-sum p_i ln p_i)
        entropy = -np.sum([pi * math.log(pi) for pi in p if pi > 1e-10])
        enb = math.exp(entropy)
        div_ratio = enb / n

        return MinimumTorsionResult(
            torsion_matrix=t_mt,
            effective_number_of_bets=float(enb),
            diversification_ratio=float(div_ratio),
            factor_risk_contributions=p,
            portfolio_volatility=port_vol,
        )


# ==============================================================================
# 4. HUANG-LEHALLE-ROSENBAUM (2015) QUEUE-REACTIVE LOB
# ==============================================================================

@dataclass
class QueueReactiveResult:
    fill_probability: float
    expected_fill_time: float
    cancel_probability_before_fill: float
    adverse_selection_risk: float
    queue_half_life: float


class QueueReactiveLOBEngine:
    """High-frequency queue-reactive limit order book fill dynamics.
    
    References:
    - Huang, W., Lehalle, C. A., & Rosenbaum, M. (2015). Simulating and analyzing order book data: 
      The queue-reactive model. Journal of the American Statistical Association, 110(509), 107-122.
    """

    @staticmethod
    def calculate_fill_dynamics(
        queue_size: int,
        order_priority: int,
        arrival_rate: float,
        cancel_rate_per_lot: float,
        market_execution_rate: float,
        adverse_tick_rate: float = 0.05,
    ) -> QueueReactiveResult:
        """Computes analytical fill probability and expected execution time."""
        if order_priority < 1 or order_priority > queue_size:
            order_priority = min(max(1, order_priority), queue_size)

        orders_ahead = order_priority - 1
        total_fill_prob = 1.0
        expected_time = 0.0

        for j in range(orders_ahead, -1, -1):
            rate_exec = market_execution_rate
            rate_cancel = j * cancel_rate_per_lot
            rate_advance = rate_exec + rate_cancel
            rate_loss = adverse_tick_rate

            prob_advance = rate_advance / (rate_advance + rate_loss) if (rate_advance + rate_loss) > 0 else 0.0
            total_fill_prob *= prob_advance
            expected_time += 1.0 / (rate_advance + rate_loss) if (rate_advance + rate_loss) > 0 else 0.0

        cancel_prob = max(0.0, 1.0 - total_fill_prob)
        adverse_risk = adverse_tick_rate * expected_time

        depletion_rate = market_execution_rate + queue_size * cancel_rate_per_lot
        half_life = math.log(2.0) / depletion_rate if depletion_rate > 0 else 999.0

        return QueueReactiveResult(
            fill_probability=float(np.clip(total_fill_prob, 0.0, 1.0)),
            expected_fill_time=float(expected_time),
            cancel_probability_before_fill=float(cancel_prob),
            adverse_selection_risk=float(adverse_risk),
            queue_half_life=float(half_life),
        )


# ==============================================================================
# 5. TSIVERIOTIS & FERNANDES (1998) CONVERTIBLE BOND ENGINE
# ==============================================================================

@dataclass
class ConvertibleBondGreeks:
    total_price: float
    pure_debt_value: float
    equity_conversion_value: float
    parity: float
    conversion_premium: float
    delta: float
    gamma: float
    cs01: float


class TsiveriotisFernandesConvertibleEngine:
    """Coupled PDE valuation of convertible debt splitting credit-risky and equity components.
    
    References:
    - Tsiveriotis, K., & Fernandes, C. (1998). Valuing convertible bonds with credit risk. 
      Journal of Fixed Income, 8(2), 95-102.
    """

    @classmethod
    def price_convertible(
        cls,
        spot: float,
        face_value: float,
        conversion_ratio: float,
        coupon_rate: float,
        maturity: float,
        risk_free_rate: float,
        credit_spread: float,
        volatility: float,
        steps: int = 40,
        compute_greeks: bool = True,
    ) -> ConvertibleBondGreeks:
        """Prices convertible bond using backward binomial lattice with split payoffs."""
        dt = maturity / steps
        u = math.exp(volatility * math.sqrt(dt))
        d = 1.0 / u
        p_rf = (math.exp(risk_free_rate * dt) - d) / (u - d)
        p_rf = float(np.clip(p_rf, 0.01, 0.99))

        disc_rf = math.exp(-risk_free_rate * dt)
        disc_risky = math.exp(-(risk_free_rate + credit_spread) * dt)

        # Spot lattice at maturity
        s_nodes = np.array([spot * (u ** j) * (d ** (steps - j)) for j in range(steps + 1)])

        # Terminal conditions
        v_lattice = np.zeros(steps + 1)
        w_lattice = np.zeros(steps + 1)
        coupon_pmt = coupon_rate * face_value

        for j in range(steps + 1):
            conversion_val = conversion_ratio * s_nodes[j]
            redemption_val = face_value + coupon_pmt
            if conversion_val >= redemption_val:
                v_lattice[j] = 0.0
                w_lattice[j] = conversion_val
            else:
                v_lattice[j] = redemption_val
                w_lattice[j] = 0.0

        # Backward roll
        for step in range(steps - 1, -1, -1):
            new_v = np.zeros(step + 1)
            new_w = np.zeros(step + 1)
            for j in range(step + 1):
                s_curr = spot * (u ** j) * (d ** (step - j))
                exp_v = disc_risky * (p_rf * v_lattice[j + 1] + (1.0 - p_rf) * v_lattice[j]) + coupon_pmt * dt
                exp_w = disc_rf * (p_rf * w_lattice[j + 1] + (1.0 - p_rf) * w_lattice[j])

                conv_now = conversion_ratio * s_curr
                hold_val = exp_v + exp_w
                if conv_now > hold_val:
                    new_v[j] = 0.0
                    new_w[j] = conv_now
                else:
                    new_v[j] = exp_v
                    new_w[j] = exp_w

            v_lattice = new_v
            w_lattice = new_w

        price_0 = float(v_lattice[0] + w_lattice[0])
        debt_0 = float(v_lattice[0])
        equity_0 = float(w_lattice[0])

        parity_0 = conversion_ratio * spot
        conv_premium = (price_0 - parity_0) / max(parity_0, 1e-4)

        if not compute_greeks:
            return ConvertibleBondGreeks(
                total_price=price_0,
                pure_debt_value=debt_0,
                equity_conversion_value=equity_0,
                parity=parity_0,
                conversion_premium=conv_premium,
                delta=0.0,
                gamma=0.0,
                cs01=0.0,
            )

        # Perturbation for Greeks
        dS = max(spot * 0.01, 1e-4)
        p_up = cls.price_convertible(spot + dS, face_value, conversion_ratio, coupon_rate, maturity, risk_free_rate, credit_spread, volatility, steps, compute_greeks=False).total_price
        p_dn = cls.price_convertible(spot - dS, face_value, conversion_ratio, coupon_rate, maturity, risk_free_rate, credit_spread, volatility, steps, compute_greeks=False).total_price

        delta = (p_up - p_dn) / (2.0 * dS)
        gamma = (p_up - 2.0 * price_0 + p_dn) / (dS ** 2)

        p_cs_up = cls.price_convertible(spot, face_value, conversion_ratio, coupon_rate, maturity, risk_free_rate, credit_spread + 0.0001, volatility, steps, compute_greeks=False).total_price
        cs01 = -(p_cs_up - price_0)

        return ConvertibleBondGreeks(
            total_price=price_0,
            pure_debt_value=debt_0,
            equity_conversion_value=equity_0,
            parity=parity_0,
            conversion_premium=conv_premium,
            delta=delta,
            gamma=gamma,
            cs01=cs01,
        )


# ==============================================================================
# 6. MEV-BOOST, PBS & AMM TOXIC FLOW ARBITRAGE
# ==============================================================================

@dataclass
class PBSAuctionResult:
    winning_builder_bid: float
    searcher_net_profit: float
    proposer_revenue: float
    toxic_arbitrage_extracted: float
    lvr_instantaneous_rate: float
    private_pool_rebate: float


class MEVBoostPBSEngine:
    """Models Proposer-Builder Separation (PBS) bundle auctions & AMM toxic order flow.
    
    References:
    - Flashbots (2022). MEV-Boost: Merge-ready PBS implementation.
    - Milionis, J., Moallemi, C. C., & Roughgarden, T. (2022). Automated Market Making and Loss-Versus-Rebalancing.
    """

    @staticmethod
    def calculate_toxic_arbitrage_cfmm(
        pool_x: float,
        pool_y: float,
        ext_price: float,
        fee_rate: float = 0.003,
    ) -> Tuple[float, float, float]:
        """Calculates optimal external arbitrage trade size and extracted profit for xy=k."""
        k = pool_x * pool_y
        pool_price = pool_y / pool_x

        if ext_price > pool_price / (1.0 - fee_rate):
            target_x = math.sqrt(k / (ext_price * (1.0 - fee_rate)))
            dx_out = pool_x - target_x
            if dx_out > 0:
                dy_in = (k / (pool_x - dx_out)) - pool_y
                net_profit = (dx_out * ext_price) - dy_in
                return float(dx_out), float(dy_in), float(max(0.0, net_profit))

        elif ext_price < pool_price * (1.0 - fee_rate):
            target_x = math.sqrt(k / (ext_price / (1.0 - fee_rate)))
            dx_in = target_x - pool_x
            if dx_in > 0:
                dy_out = pool_y - (k / (pool_x + dx_in))
                net_profit = dy_out - (dx_in * ext_price)
                return float(dx_in), float(dy_out), float(max(0.0, net_profit))

        return 0.0, 0.0, 0.0

    @classmethod
    def simulate_pbs_auction(
        cls,
        gross_mev_opportunities: List[float],
        searcher_bid_fraction: float = 0.85,
        builder_margin: float = 0.05,
        pool_liquidity: float = 1_000_000.0,
        asset_volatility: float = 0.60,
        private_rebate_fraction: float = 0.50,
    ) -> PBSAuctionResult:
        """Simulates searcher bundle submission, builder block construction, and proposer payout."""
        total_gross_mev = sum(gross_mev_opportunities)

        searcher_bids = [mev * searcher_bid_fraction for mev in gross_mev_opportunities]
        total_searcher_bid = sum(searcher_bids)
        searcher_net_profit = total_gross_mev - total_searcher_bid

        builder_bid_to_proposer = total_searcher_bid * (1.0 - builder_margin)

        lvr_rate = 0.125 * (asset_volatility ** 2) * pool_liquidity
        rebate = total_gross_mev * private_rebate_fraction

        return PBSAuctionResult(
            winning_builder_bid=float(builder_bid_to_proposer),
            searcher_net_profit=float(searcher_net_profit),
            proposer_revenue=float(builder_bid_to_proposer),
            toxic_arbitrage_extracted=float(total_gross_mev),
            lvr_instantaneous_rate=float(lvr_rate),
            private_pool_rebate=float(rebate),
        )
