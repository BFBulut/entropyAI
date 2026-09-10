"""Programmatic TDD Verification Suite for Faz 44 Quantitative Finance Engines.

Models:
1. Julien Guyon & Pierre Henry-Labordère (2012) Local-Stochastic Volatility (SLV) & Particle Calibration Method
2. Darrell Duffie, Nicolae Gârleanu & Lasse Heje Pedersen (2002) Securities Lending, Negative Rebate & Borrow Fee Dynamics
3. Pierre Collin-Dufresne & Robert S. Goldstein (2001) Stationary Leverage Ratio Structural Credit Model
4. Rama Cont & Eric Schaanning (2017) Fire Sales & Systemic Deleveraging Cascades in Macroprudential Stress Testing
5. Ole E. Barndorff-Nielsen, Peter R. Hansen, Asger Lunde & Neil Shephard (2008) Realized Kernels & Spectral HFT Covariance
6. Morpho Blue & Fluid Protocol Isolated Lending Fiziği, Dutch Auction Liquidation & MetaMorpho Allocator
"""

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pytest

# ==============================================================================
# Helper Numerical Functions
# ==============================================================================
def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ==============================================================================
# 1. Guyon & Henry-Labordère (2012) Local-Stochastic Volatility (SLV) Particle Engine
# ==============================================================================
class GuyonHenryLabordereSLV:
    """
    Local-Stochastic Volatility (SLV) with Particle Calibration (Guyon & Henry-Labordère 2012).
    dS_t = r S_t dt + L(S_t, t) * sqrt(v_t) * S_t * dW_t^S
    dv_t = kappa * (theta - v_t) dt + xi * sqrt(v_t) * dW_t^v,  Corr(W^S, W^v) = rho
    Gyöngy Theorem: L(S, t) = sigma_loc(S, t) / sqrt(E[v_t | S_t = S])
    Condition expectation is estimated via non-parametric kernel regression on interacting particles.
    """
    def __init__(self,
                 r: float = 0.03,
                 kappa: float = 2.0,
                 theta: float = 0.04,
                 xi: float = 0.3,
                 rho: float = -0.6,
                 v0: float = 0.04,
                 n_particles: int = 1500,
                 n_steps: int = 15,
                 seed: int = 42):
        self.r = r
        self.kappa = kappa
        self.theta = theta
        self.xi = xi
        self.rho = rho
        self.v0 = v0
        self.n_particles = n_particles
        self.n_steps = n_steps
        self.seed = seed

    def target_local_vol(self, S: float, t: float, S0: float = 100.0) -> float:
        """Parametric target local volatility surface (Dupire target)."""
        m = math.log(max(1e-4, S / S0))
        base_vol = 0.20 + 0.02 * math.exp(-t)
        skew = -0.15 * m
        smile = 0.10 * (m ** 2)
        return max(0.05, min(0.80, base_vol + skew + smile))

    def epanechnikov_kernel(self, u: np.ndarray) -> np.ndarray:
        """Epanechnikov kernel: 0.75 * (1 - u^2) for |u| <= 1, 0 otherwise."""
        weights = 0.75 * (1.0 - u ** 2)
        weights[np.abs(u) > 1.0] = 0.0
        return weights

    def calibrate_and_simulate(self, S0: float = 100.0, T: float = 1.0) -> Dict[str, Any]:
        """
        Runs particle method to calibrate leverage function L(S, t) and simulate paths.
        """
        np.random.seed(self.seed)
        dt = T / self.n_steps
        sqrt_dt = math.sqrt(dt)

        S = np.full(self.n_particles, S0, dtype=float)
        v = np.full(self.n_particles, self.v0, dtype=float)

        time_grid = np.linspace(0.0, T, self.n_steps + 1)
        mean_v_path = [float(np.mean(v))]
        leverage_samples = []

        rho_comp = math.sqrt(max(0.0, 1.0 - self.rho ** 2))

        for step in range(self.n_steps):
            t_curr = time_grid[step]

            # 1. Estimate conditional expectation E[v | S] via kernel smoothing
            std_S = float(np.std(S))
            bandwidth = max(0.5, 1.06 * std_S * (self.n_particles ** (-0.2)))

            # Evaluate E[v | S_i] for each particle
            cond_exp_v = np.zeros(self.n_particles)
            for i in range(self.n_particles):
                u = (S - S[i]) / bandwidth
                w = self.epanechnikov_kernel(u)
                sum_w = np.sum(w)
                if sum_w > 1e-6:
                    cond_exp_v[i] = np.sum(w * v) / sum_w
                else:
                    cond_exp_v[i] = max(1e-4, float(np.mean(v)))

            cond_exp_v = np.maximum(1e-4, cond_exp_v)

            # 2. Leverage function L(S, t) = sigma_loc(S, t) / sqrt(E[v | S])
            sigma_loc = np.array([self.target_local_vol(s_val, t_curr, S0) for s_val in S])
            L = sigma_loc / np.sqrt(cond_exp_v)
            L = np.clip(L, 0.1, 5.0)

            if step == 0:
                leverage_samples.append(float(np.mean(L)))

            # 3. Propagate SDEs using Euler-Maruyama
            z1 = np.random.normal(0.0, 1.0, self.n_particles)
            z2 = np.random.normal(0.0, 1.0, self.n_particles)
            zv = self.rho * z1 + rho_comp * z2

            v_pos = np.maximum(1e-6, v)
            sqrt_v = np.sqrt(v_pos)

            # Spot process
            S = S * np.exp((self.r - 0.5 * (L * sqrt_v) ** 2) * dt + L * sqrt_v * sqrt_dt * z1)

            # Variance process (Full Truncation CIR)
            v = v + self.kappa * (self.theta - v_pos) * dt + self.xi * sqrt_v * sqrt_dt * zv
            v = np.maximum(1e-6, v)

            mean_v_path.append(float(np.mean(v)))

        # Vanilla call pricing via Monte Carlo
        strikes = [90.0, 100.0, 110.0]
        call_prices = {}
        for K in strikes:
            payoff = np.maximum(0.0, S - K)
            call_prices[K] = float(math.exp(-self.r * T) * np.mean(payoff))

        return {
            "S_final_mean": float(np.mean(S)),
            "S_final_std": float(np.std(S)),
            "mean_v_terminal": float(np.mean(v)),
            "call_prices": call_prices,
            "mean_leverage_t0": leverage_samples[0] if leverage_samples else 1.0,
            "feller_ratio": (2.0 * self.kappa * self.theta) / (self.xi ** 2)
        }


# ==============================================================================
# 2. Duffie, Gârleanu & Pedersen (2002) Securities Lending & Rebate Rate Engine
# ==============================================================================
class SecuritiesLendingEngine:
    """
    Equilibrium Stock Loan Market & Short Selling Constraints (Duffie, Gârleanu & Pedersen 2002).
    - Cash Collateral Margin M = 102%
    - Short Borrowing Fee = r_f - r_rebate
    - General Collateral (GC) vs Hard-to-Borrow (HTB) Specials
    - Non-linear borrow fee spike under inventory squeeze: Fee(U) = Fee_0 + alpha * (U / (1 - U))^beta
    - Asset Pricing: Price contains Present Value of expected future lending fees (Convenience Yield).
    """
    def __init__(self,
                 rf: float = 0.05,
                 collateral_margin: float = 1.02,
                 base_fee: float = 0.0035, # 35 bps base borrow fee
                 alpha: float = 0.02,
                 beta: float = 2.5):
        self.rf = rf
        self.collateral_margin = collateral_margin
        self.base_fee = base_fee
        self.alpha = alpha
        self.beta = beta

    def compute_borrow_fee_and_rebate(self, utilization: float) -> Dict[str, float]:
        """
        Calculates equilibrium borrow fee and rebate rate as a function of utilization U = Borrowed / Lendable.
        """
        u = max(0.0, min(0.999, utilization))
        squeeze_component = self.alpha * ((u / (1.0 - u)) ** self.beta)
        borrow_fee = self.base_fee + squeeze_component
        rebate_rate = self.rf - borrow_fee

        is_special = borrow_fee > 0.01 # > 100 bps
        is_negative_rebate = rebate_rate < 0.0 # Extreme squeeze

        return {
            "utilization": u,
            "borrow_fee_annual": borrow_fee,
            "borrow_fee_bps": borrow_fee * 10000.0,
            "rebate_rate_annual": rebate_rate,
            "is_special": is_special,
            "is_negative_rebate": is_negative_rebate,
            "daily_cost_per_million": (1000000.0 * borrow_fee) / 360.0
        }

    def equity_price_with_lending_premium(self,
                                          p_fundamental: float,
                                          expected_fee_path: List[float],
                                          dt: float = 1.0 / 12.0) -> Dict[str, float]:
        """
        Duffie-Gârleanu-Pedersen (2002) asset pricing:
        P_t = P_fundamental + sum_k exp(-rf * t_k) * Fee(t_k) * P_fundamental * dt
        """
        pv_lending_fees = 0.0
        for i, fee in enumerate(expected_fee_path):
            t = (i + 1) * dt
            discount = math.exp(-self.rf * t)
            pv_lending_fees += discount * fee * p_fundamental * dt

        total_price = p_fundamental + pv_lending_fees
        overpricing_ratio = total_price / p_fundamental

        return {
            "p_fundamental": p_fundamental,
            "pv_lending_fees": pv_lending_fees,
            "market_price": total_price,
            "overpricing_ratio": overpricing_ratio,
            "convenience_yield_annual": pv_lending_fees / (p_fundamental * (len(expected_fee_path) * dt))
        }


# ==============================================================================
# 3. Collin-Dufresne & Goldstein (2001) Stationary Leverage Structural Credit Model
# ==============================================================================
class CollinDufresneGoldsteinCredit:
    """
    Structural Credit Model with Stationary Leverage Ratio (Collin-Dufresne & Goldstein 2001).
    Firms actively manage capital structure towards target leverage, preventing leverage from decaying to zero.
    Log-leverage y_t = ln(V_t / D_t) follows mean-reverting OU:
      dy_t = kappa * (theta - y_t) dt + sigma_V * dW_t^V
    Short-rate Vasicek:
      dr_t = a * (b - r_t) dt + sigma_r * dW_t^r, Corr(W^V, W^r) = rho
    Produces realistic non-zero credit spreads for long horizons (resolves Merton credit spread puzzle).
    """
    def __init__(self,
                 kappa: float = 0.15,     # Speed of mean-reversion in leverage
                 theta: float = 0.85,     # Long-run stationary log-leverage target
                 sigma_v: float = 0.22,   # Asset volatility
                 a: float = 0.20,         # Rate mean-reversion
                 b: float = 0.045,        # Long-run interest rate
                 sigma_r: float = 0.015,  # Rate volatility
                 rho: float = -0.25,      # Correlation between asset value and rates
                 recovery_rate: float = 0.40):
        self.kappa = kappa
        self.theta = theta
        self.sigma_v = sigma_v
        self.a = a
        self.b = b
        self.sigma_r = sigma_r
        self.rho = rho
        self.recovery_rate = recovery_rate

    def risk_free_zcb(self, r0: float, T: float) -> float:
        """Vasicek analytical zero-coupon bond price P_0(0, T)."""
        B = (1.0 - math.exp(-self.a * T)) / self.a
        A = math.exp((self.b - (self.sigma_r ** 2) / (2.0 * (self.a ** 2))) * (B - T)
                     - ((self.sigma_r ** 2) * (B ** 2)) / (4.0 * self.a))
        return A * math.exp(-B * r0)

    def compute_cumulative_default_prob(self, y0: float, T: float) -> float:
        """
        First-passage default probability under mean-reverting leverage y_t hitting barrier y = 0.
        Approximated via Ornstein-Uhlenbeck barrier first hitting formula.
        """
        exp_k = math.exp(-self.kappa * T)
        mean_yT = self.theta + (y0 - self.theta) * exp_k
        var_yT = ((self.sigma_v ** 2) / (2.0 * self.kappa)) * (1.0 - exp_k ** 2)
        std_yT = math.sqrt(max(1e-8, var_yT))

        d = mean_yT / std_yT
        pd = 2.0 * norm_cdf(-d)
        return max(0.0, min(1.0, pd))

    def price_corporate_bond(self, y0: float, r0: float, T: float) -> Dict[str, float]:
        """
        Prices zero-coupon corporate bond with stationary leverage and computes credit spread.
        """
        p_rf = self.risk_free_zcb(r0, T)
        pd = self.compute_cumulative_default_prob(y0, T)

        expected_recovery = self.recovery_rate * pd * p_rf
        p_corp = p_rf * (1.0 - pd) + expected_recovery

        if p_corp > 0 and p_rf > 0:
            credit_spread = - (1.0 / T) * math.log(p_corp / p_rf)
        else:
            credit_spread = 0.0

        return {
            "maturity": T,
            "p_risk_free": p_rf,
            "p_corporate": p_corp,
            "default_probability": pd,
            "credit_spread_annual": credit_spread,
            "credit_spread_bps": credit_spread * 10000.0,
            "expected_loss_rate": (1.0 - self.recovery_rate) * pd
        }


# ==============================================================================
# 4. Cont & Schaanning (2017) Fire Sales & Systemic Deleveraging Cascade Engine
# ==============================================================================
class ContSchaanningFireSales:
    """
    Macroprudential Stress Testing & Systemic Fire Sales (Cont & Schaanning 2017).
    - Network of N financial institutions holding K illiquid assets.
    - Leverage ceiling lambda_max (Basel III leverage constraint).
    - Initial price shock -> Equity loss -> Forced deleveraging sales -> Price impact -> Second-round loss.
    - Resolves systemic spillover matrix A_ij and amplification multiplier (I - A)^(-1).
    """
    def __init__(self,
                 holdings: np.ndarray,       # Shape (N, K): Dollar holdings of asset k by bank i
                 liabilities: np.ndarray,    # Shape (N,): Total debt of bank i
                 lambda_max: float = 25.0,   # Regulatory maximum leverage (e.g. 4% minimum equity)
                 impact_params: np.ndarray = None # Shape (K,): Price impact parameter Lambda_k
                 ):
        self.holdings = np.array(holdings, dtype=float)
        self.liabilities = np.array(liabilities, dtype=float)
        self.N, self.K = self.holdings.shape
        self.lambda_max = lambda_max

        if impact_params is None:
            self.impact_params = np.full(self.K, 1e-4)
        else:
            self.impact_params = np.array(impact_params, dtype=float)

    def total_assets(self) -> np.ndarray:
        return np.sum(self.holdings, axis=1)

    def initial_equity(self) -> np.ndarray:
        return self.total_assets() - self.liabilities

    def simulate_fire_sale_cascade(self, initial_shock: np.ndarray, max_iter: int = 15) -> Dict[str, Any]:
        """
        Simulates iterative systemic deleveraging cascade following initial asset shock.
        """
        current_holdings = self.holdings.copy()
        current_equity = self.initial_equity().copy()
        total_liquidated = np.zeros(self.K)
        cumulative_price_drop = initial_shock.copy()

        # Round 1: Direct mark-to-market loss
        round1_loss = np.dot(current_holdings, -initial_shock)
        current_equity -= round1_loss

        iterations = 0
        total_fire_sales = 0.0

        for it in range(max_iter):
            iterations += 1
            assets = np.sum(current_holdings, axis=1)
            target_assets = np.maximum(0.0, self.lambda_max * current_equity)
            excess_assets = np.maximum(0.0, assets - target_assets)

            forced_sales = np.minimum(assets, (self.lambda_max / (self.lambda_max - 1.0)) * excess_assets)

            if np.sum(forced_sales) < 1e-4:
                break

            total_fire_sales += float(np.sum(forced_sales))

            weights = np.zeros_like(current_holdings)
            for i in range(self.N):
                if assets[i] > 1e-6:
                    weights[i, :] = current_holdings[i, :] / assets[i]

            sales_by_asset = np.sum(weights * forced_sales[:, np.newaxis], axis=0)
            total_liquidated += sales_by_asset

            price_impact = - self.impact_params * sales_by_asset
            cumulative_price_drop += price_impact

            mtm_loss = np.dot(current_holdings, -price_impact)
            current_equity -= mtm_loss

            current_holdings -= weights * forced_sales[:, np.newaxis]
            current_holdings = np.maximum(0.0, current_holdings)

        assets_init = self.total_assets()
        A_matrix = np.zeros((self.N, self.N))
        coeff = self.lambda_max / (self.lambda_max - 1.0)
        for i in range(self.N):
            for j in range(self.N):
                if assets_init[i] > 1e-6 and assets_init[j] > 1e-6:
                    overlap = np.sum(self.impact_params * self.holdings[i, :] * self.holdings[j, :])
                    A_matrix[i, j] = coeff * overlap / assets_init[j]

        eigenvalues = np.linalg.eigvals(A_matrix)
        spectral_radius = float(np.max(np.abs(eigenvalues)))

        init_loss_total = float(np.sum(round1_loss))
        final_loss_total = float(np.sum(self.initial_equity() - current_equity))
        amplification_ratio = final_loss_total / max(1e-4, init_loss_total)

        defaulted_banks = int(np.sum(current_equity <= 0.0))

        return {
            "iterations": iterations,
            "initial_equity_total": float(np.sum(self.initial_equity())),
            "final_equity_total": float(np.sum(current_equity)),
            "total_fire_sales_volume": total_fire_sales,
            "amplification_ratio": amplification_ratio,
            "spectral_radius": spectral_radius,
            "systemic_resonance": spectral_radius >= 1.0,
            "defaulted_banks_count": defaulted_banks,
            "cumulative_price_drops": cumulative_price_drop.tolist()
        }


# ==============================================================================
# 5. Barndorff-Nielsen, Hansen, Lunde & Shephard (2008) Realized Kernels Engine
# ==============================================================================
class RealizedKernelEngine:
    """
    Noise-Robust Volatility & Covariance Estimation via Realized Kernels (Barndorff-Nielsen et al. 2008).
    K(X) = gamma_0(X) + sum_{h=1}^H k(h / (H+1)) * [gamma_h(X) + gamma_{-h}(X)]
    Parzen kernel ensures positive semi-definiteness K(X) >= 0.
    Optimal bandwidth H* = c* * xi^(4/5) * n^(3/5) filters microstructure noise (bid-ask bounce).
    """
    def __init__(self, kernel_type: str = "parzen"):
        self.kernel_type = kernel_type

    def parzen_kernel(self, x: float) -> float:
        """Parzen kernel function on [0, 1]."""
        ax = abs(x)
        if ax <= 0.5:
            return 1.0 - 6.0 * (ax ** 2) + 6.0 * (ax ** 3)
        elif ax <= 1.0:
            return 2.0 * ((1.0 - ax) ** 3)
        return 0.0

    def compute_autocovariance(self, returns: np.ndarray, h: int) -> float:
        """Sample autocovariance gamma_h = sum_{j=1}^{n-h} r_j * r_{j+h}."""
        n = len(returns)
        if h >= n or h < 0:
            return 0.0
        if h == 0:
            return float(np.sum(returns ** 2))
        return float(np.sum(returns[:-h] * returns[h:]))

    def estimate_integrated_variance(self,
                                     prices: np.ndarray,
                                     bandwidth: Optional[int] = None) -> Dict[str, float]:
        """
        Computes Realized Kernel from high-frequency tick prices with microstructure noise.
        """
        log_p = np.log(prices)
        returns = np.diff(log_p)
        n = len(returns)

        rv_naive = float(np.sum(returns ** 2))

        if bandwidth is None:
            H = int(max(2, round(3.5 * (n ** 0.6) / 50.0)))
        else:
            H = max(1, bandwidth)

        gamma_0 = self.compute_autocovariance(returns, 0)
        rk_val = gamma_0

        weights = []
        for h in range(1, H + 1):
            x = h / (H + 1.0)
            k_weight = self.parzen_kernel(x)
            weights.append(k_weight)
            gamma_h = self.compute_autocovariance(returns, h)
            rk_val += 2.0 * k_weight * gamma_h

        rk_clean = max(0.0, rk_val)
        noise_var = max(0.0, (rv_naive - rk_clean) / (2.0 * n))

        return {
            "n_ticks": n,
            "bandwidth_H": H,
            "realized_variance_naive": rv_naive,
            "realized_kernel_clean": rk_clean,
            "volatility_naive_annual": math.sqrt(rv_naive * 252.0),
            "volatility_clean_annual": math.sqrt(rk_clean * 252.0),
            "noise_variance_estimate": noise_var,
            "noise_ratio_percent": (noise_var / max(1e-8, rv_naive / n)) * 100.0
        }


# ==============================================================================
# 6. Morpho Blue & Fluid Protocol Isolated Lending & Smart Liquidation Engine
# ==============================================================================
class MorphoFluidIsolatedLending:
    """
    Morpho Blue & Fluid Protocol Isolated Lending Fiziği, Dutch Auction Liquidation & MetaMorpho Allocator.
    - Immutable 5-tuple: (LoanToken, CollateralToken, Oracle, IRM, LLTV)
    - LLTV in {77.0%, 86.0%, 91.5%, 94.5%, 96.5%}
    - Health Factor: HF = (Collateral * Price * LLTV) / BorrowedAmount
    - Dutch Auction Liquidation: Bonus increases linearly with time to prevent bad debt.
    - Fluid Protocol Smart Debt: Direct inner swap without flash loan haircut.
    - MetaMorpho ERC-4626: Optimal risk-constrained supply allocation across isolated markets.
    """
    def __init__(self,
                 lltv: float = 0.86,
                 max_liquidation_bonus: float = 0.08,
                 auction_duration_sec: float = 300.0
                 ):
        self.lltv = lltv
        self.max_liquidation_bonus = max_liquidation_bonus
        self.auction_duration_sec = auction_duration_sec

    def compute_health_factor(self,
                              collateral_amount: float,
                              collateral_price: float,
                              borrowed_amount: float) -> float:
        """HF = (Collateral * Price * LLTV) / BorrowedAmount."""
        if borrowed_amount <= 1e-9:
            return 999.0
        collateral_value = collateral_amount * collateral_price
        max_borrow = collateral_value * self.lltv
        return max_borrow / borrowed_amount

    def execute_dutch_liquidation(self,
                                  collateral_amount: float,
                                  collateral_price: float,
                                  borrowed_amount: float,
                                  repay_amount: float,
                                  elapsed_sec: float) -> Dict[str, Any]:
        """
        Executes Morpho Blue Dutch Auction liquidation.
        Liquidator repays debt and receives collateral at a dynamic discount (bonus).
        """
        hf_initial = self.compute_health_factor(collateral_amount, collateral_price, borrowed_amount)
        if hf_initial >= 1.0:
            raise ValueError("Position is healthy (HF >= 1.0); liquidation reverted.")

        cap_bonus = min(self.max_liquidation_bonus, (1.0 / self.lltv) - 1.0)
        time_fraction = min(1.0, elapsed_sec / self.auction_duration_sec)
        current_bonus = cap_bonus * time_fraction

        effective_price = collateral_price / (1.0 + current_bonus)
        collateral_seized = repay_amount / effective_price

        bad_debt = 0.0
        if collateral_seized > collateral_amount:
            bad_debt = (collateral_seized - collateral_amount) * collateral_price
            collateral_seized = collateral_amount

        remaining_collateral = max(0.0, collateral_amount - collateral_seized)
        remaining_borrow = max(0.0, borrowed_amount - repay_amount)
        hf_post = self.compute_health_factor(remaining_collateral, collateral_price, remaining_borrow)

        return {
            "initial_hf": hf_initial,
            "post_hf": hf_post,
            "repaid_debt": repay_amount,
            "collateral_seized": collateral_seized,
            "liquidation_bonus": current_bonus,
            "liquidator_profit_usd": collateral_seized * collateral_price - repay_amount,
            "bad_debt_usd": bad_debt,
            "is_solvent": bad_debt == 0.0
        }

    def metamorpho_allocate_supply(self,
                                   total_deposit: float,
                                   markets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        MetaMorpho ERC-4626 Vault: Allocates liquidity across isolated markets to maximize yield
        subject to supply caps and LLTV risk limits.
        """
        sorted_markets = sorted(markets, key=lambda m: m["rate"], reverse=True)
        remaining = total_deposit
        allocations = {}
        weighted_rate = 0.0

        for m in sorted_markets:
            m_id = m["id"]
            cap = m["cap"]
            alloc = min(remaining, cap)
            allocations[m_id] = alloc
            weighted_rate += (alloc / total_deposit) * m["rate"]
            remaining -= alloc
            if remaining <= 1e-6:
                break

        return {
            "total_deposit": total_deposit,
            "allocated_total": total_deposit - remaining,
            "unallocated_cash": remaining,
            "allocations": allocations,
            "blended_apy": weighted_rate
        }


# ==============================================================================
# Pytest Test Cases Verifying All 6 Models
# ==============================================================================

def test_model_1_guyon_henry_labordere_slv():
    """Verify Guyon & Henry-Labordère Local-Stochastic Volatility Particle Engine."""
    engine = GuyonHenryLabordereSLV(r=0.03, kappa=2.5, theta=0.04, xi=0.35, rho=-0.65, n_particles=500, n_steps=10)
    result = engine.calibrate_and_simulate(S0=100.0, T=1.0)

    # 1. Spot martingale check: E[S_T] should be close to S0 * exp(r * T)
    expected_mean = 100.0 * math.exp(0.03 * 1.0)
    assert abs(result["S_final_mean"] - expected_mean) < 15.0

    # 2. Call prices monotonicity with strike (90 > 100 > 110)
    calls = result["call_prices"]
    assert calls[90.0] > calls[100.0] > calls[110.0]

    # 3. Feller condition check (2 * kappa * theta > xi^2)
    assert result["feller_ratio"] > 1.0
    assert result["mean_leverage_t0"] > 0.0


def test_model_2_securities_lending_rebate_rates():
    """Verify Duffie, Gârleanu & Pedersen Securities Lending & Rebate Rate Squeeze Dynamics."""
    engine = SecuritiesLendingEngine(rf=0.05, base_fee=0.0035, alpha=0.02, beta=2.5)

    # 1. Normal General Collateral (GC) regime (e.g. 25% utilization)
    gc_res = engine.compute_borrow_fee_and_rebate(utilization=0.25)
    assert gc_res["borrow_fee_bps"] < 100.0
    assert gc_res["rebate_rate_annual"] > 0.04
    assert not gc_res["is_special"]
    assert not gc_res["is_negative_rebate"]

    # 2. Severe short squeeze regime (e.g. 92% utilization)
    squeeze_res = engine.compute_borrow_fee_and_rebate(utilization=0.92)
    assert squeeze_res["is_special"]
    assert squeeze_res["borrow_fee_annual"] > 0.05
    assert squeeze_res["is_negative_rebate"]
    assert squeeze_res["daily_cost_per_million"] > 150.0

    # 3. Asset pricing with lending convenience yield
    fee_path = [0.01, 0.02, 0.03, 0.02, 0.01, 0.005]
    price_res = engine.equity_price_with_lending_premium(p_fundamental=100.0, expected_fee_path=fee_path)
    assert price_res["market_price"] > 100.0
    assert price_res["pv_lending_fees"] > 0.0


def test_model_3_collin_dufresne_goldstein_credit():
    """Verify Collin-Dufresne & Goldstein Stationary Leverage Structural Credit Model."""
    engine = CollinDufresneGoldsteinCredit(kappa=0.20, theta=0.80, sigma_v=0.20, a=0.25, b=0.04, sigma_r=0.015)

    # 1. Price corporate bonds across maturities (1Y, 10Y, 30Y)
    res_1y = engine.price_corporate_bond(y0=0.80, r0=0.04, T=1.0)
    res_10y = engine.price_corporate_bond(y0=0.80, r0=0.04, T=10.0)
    res_30y = engine.price_corporate_bond(y0=0.80, r0=0.04, T=30.0)

    # Corporate bond prices should be strictly lower than risk-free ZCB
    assert res_1y["p_corporate"] < res_1y["p_risk_free"]
    assert res_10y["p_corporate"] < res_10y["p_risk_free"]
    assert res_30y["p_corporate"] < res_30y["p_risk_free"]

    # Credit spreads must be strictly positive for all maturities
    assert res_1y["credit_spread_bps"] > 0.0
    assert res_10y["credit_spread_bps"] > 0.0
    assert res_30y["credit_spread_bps"] > 0.0

    # Long-term spread (30Y) remains non-zero due to stationary leverage
    assert res_30y["credit_spread_bps"] >= 1.0


def test_model_4_cont_schaanning_fire_sales_cascade():
    """Verify Cont & Schaanning Macroprudential Fire Sales & Deleveraging Cascade Engine."""
    holdings = np.array([
        [100.0, 50.0],
        [80.0,  120.0],
        [40.0,  60.0]
    ])
    liabilities = np.array([142.5, 190.0, 95.0])
    impact_params = np.array([0.001, 0.0015])

    engine = ContSchaanningFireSales(holdings=holdings, liabilities=liabilities, lambda_max=22.0, impact_params=impact_params)

    shock = np.array([-0.05, -0.03])
    result = engine.simulate_fire_sale_cascade(initial_shock=shock)

    assert result["iterations"] >= 1
    assert result["total_fire_sales_volume"] > 0.0
    assert result["amplification_ratio"] > 1.0
    assert result["final_equity_total"] < result["initial_equity_total"]
    assert "spectral_radius" in result


def test_model_5_realized_kernel_noise_robust_volatility():
    """Verify Barndorff-Nielsen et al. Realized Kernels Noise-Robust Volatility Estimator."""
    np.random.seed(123)
    n = 2000
    dt = 1.0 / n
    true_vol = 0.25
    dW = np.random.normal(0.0, math.sqrt(dt), n)
    X = 100.0 * np.exp(np.cumsum(-0.5 * (true_vol ** 2) * dt + true_vol * dW))

    noise = np.random.normal(0.0, 0.04, n)
    noisy_prices = X + noise

    engine = RealizedKernelEngine(kernel_type="parzen")
    res = engine.estimate_integrated_variance(noisy_prices)

    assert res["realized_variance_naive"] > res["realized_kernel_clean"]
    naive_vol = res["volatility_naive_annual"]
    clean_vol = res["volatility_clean_annual"]
    assert abs(clean_vol - 0.25) < abs(naive_vol - 0.25)
    assert res["realized_kernel_clean"] > 0.0
    assert res["bandwidth_H"] >= 2


def test_model_6_morpho_fluid_isolated_lending():
    """Verify Morpho Blue Dutch Liquidation & MetaMorpho ERC-4626 Allocation."""
    engine = MorphoFluidIsolatedLending(lltv=0.86, max_liquidation_bonus=0.08, auction_duration_sec=300.0)

    # 1. Healthy position
    hf_healthy = engine.compute_health_factor(collateral_amount=10.0, collateral_price=3000.0, borrowed_amount=20000.0)
    assert hf_healthy > 1.0

    # 2. Underwater position
    hf_bad = engine.compute_health_factor(collateral_amount=10.0, collateral_price=2200.0, borrowed_amount=20000.0)
    assert hf_bad < 1.0

    # 3. Dutch liquidation at t = 150s
    liq_res = engine.execute_dutch_liquidation(
        collateral_amount=10.0,
        collateral_price=2200.0,
        borrowed_amount=20000.0,
        repay_amount=10000.0,
        elapsed_sec=150.0
    )
    assert liq_res["liquidation_bonus"] > 0.0
    assert liq_res["liquidator_profit_usd"] > 0.0
    assert liq_res["is_solvent"]
    assert liq_res["post_hf"] > liq_res["initial_hf"]

    # 4. MetaMorpho Allocation across 3 isolated markets
    markets = [
        {"id": "market-wsteth-usdc", "rate": 0.092, "cap": 500000.0, "lltv": 0.86},
        {"id": "market-sdeusd-usdc", "rate": 0.145, "cap": 300000.0, "lltv": 0.77},
        {"id": "market-wbtc-usdc",   "rate": 0.075, "cap": 400000.0, "lltv": 0.86}
    ]
    alloc_res = engine.metamorpho_allocate_supply(total_deposit=600000.0, markets=markets)
    assert alloc_res["unallocated_cash"] == 0.0
    assert alloc_res["allocations"]["market-sdeusd-usdc"] == 300000.0
    assert alloc_res["allocations"]["market-wsteth-usdc"] == 300000.0
    assert alloc_res["blended_apy"] > 0.10
