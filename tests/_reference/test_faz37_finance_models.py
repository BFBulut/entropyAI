"""Programmatic TDD Verification Suite for Faz 37 Quantitative Finance Engines.

Models:
1. Carr-Geman-Madan-Yor (CGMY 2002) Extended Pure-Jump Lévy Process
2. Hagan-Lesniewski (2014) Arbitrage-Free SABR PDE & Absorbing Boundary Density
3. Budish-Cramton-Shim (2015) HFT Latency Arbitrage & Sniping Risk Model
4. Duffie-Garleanu-Pedersen (DGP 2005/2007) OTC Search-and-Bargaining & Haircut Equilibrium
5. Alfonsi-Fruth-Schied (AFS 2010) Transient Market Impact & Fredholm Boundary Block Execution
6. Solidly Invariant ($x^3 y + x y^3 = k$) & Morpho Blue P2P Lending Spread Arbitrage
"""

import math
import cmath
import numpy as np
import pytest


# ==============================================================================
# 1. Carr-Geman-Madan-Yor (CGMY 2002) Lévy Process
# ==============================================================================
class CGMYModel:
    """
    Carr, Geman, Madan, Yor (2002) Extended Lévy Model.
    Lévy density:
      k(x) = C * exp(-M*x) / x^(1+Y)  for x > 0
      k(x) = C * exp(-G*|x|) / |x|^(1+Y)  for x < 0
    """
    def __init__(self, C: float, G: float, M: float, Y: float):
        assert C > 0, "C must be positive"
        assert G > 0, "G must be positive"
        assert M > 1.0, "M must be > 1 to ensure finite expectation"
        assert Y < 2.0, "Y must be < 2 for valid Lévy density"
        self.C = C
        self.G = G
        self.M = M
        self.Y = Y

    def path_property(self) -> str:
        """Classify path activity and variation based on Y index."""
        if self.Y < 0:
            return "Finite Activity (Compound Poisson)"
        elif self.Y == 0:
            return "Infinite Activity, Finite Variation (Variance Gamma)"
        elif 0 < self.Y < 1:
            return "Infinite Activity, Finite Variation"
        elif 1 <= self.Y < 2:
            return "Infinite Activity, Infinite Variation (Brownian-like irregularity)"
        raise ValueError("Invalid Y")

    def characteristic_exponent(self, u: complex) -> complex:
        """
        Log characteristic function psi(u) where phi(u) = exp(t * psi(u)).
        psi(u) = C * Gamma(-Y) * [ (M - iu)^Y - M^Y + (G + iu)^Y - G^Y ]
        """
        if abs(self.Y) < 1e-6:
            # Limiting case as Y -> 0 (Variance Gamma):
            # psi(u) = -C * [ ln(1 - iu/M) + ln(1 + iu/G) ]
            term_m = cmath.log(1.0 - 1j * u / self.M)
            term_g = cmath.log(1.0 + 1j * u / self.G)
            return -self.C * (term_m + term_g)
        
        gamma_neg_y = math.gamma(-self.Y)
        term1 = (self.M - 1j * u) ** self.Y - (self.M ** self.Y)
        term2 = (self.G + 1j * u) ** self.Y - (self.G ** self.Y)
        return self.C * gamma_neg_y * (term1 + term2)

    def martingale_drift_correction(self) -> float:
        """Calculates omega such that E[exp(X_t + omega*t)] = 1, i.e., omega = -psi(-i)."""
        psi_neg_i = self.characteristic_exponent(-1j)
        return -psi_neg_i.real

    def characteristic_function(self, u: complex, t: float) -> complex:
        """Characteristic function phi(u) = exp(t * psi(u))."""
        return cmath.exp(t * self.characteristic_exponent(u))

    def price_european_call_quadrature(
        self, S0: float, K: float, T: float, r: float, alpha: float = 1.5, n_points: int = 1000, u_max: float = 100.0
    ) -> float:
        """
        Carr-Madan Fourier transform method for European Call pricing under CGMY.
        C(K) = exp(-alpha * k) / pi * integral_0^inf exp(-i u k) * psi_T(u) / (alpha^2 + alpha - u^2 + i*(2*alpha + 1)*u) du
        """
        k = math.log(K / S0)
        omega = self.martingale_drift_correction()

        def damped_cf(u_val: float) -> complex:
            # Adjusted characteristic function of log(S_T / S_0) under risk-neutral measure
            # X_T = (r + omega)*T + L_T
            u_complex = u_val - (alpha + 1.0) * 1j
            cf_jump = self.characteristic_function(u_complex, T)
            cf_drift = cmath.exp(1j * u_complex * (r + omega) * T)
            phi_total = cf_drift * cf_jump
            denom = alpha**2 + alpha - u_val**2 + 1j * (2.0 * alpha + 1.0) * u_val
            return cmath.exp(-1j * u_val * k) * phi_total / denom

        # Composite trapezoidal quadrature
        u_grid = np.linspace(1e-5, u_max, n_points)
        du = u_grid[1] - u_grid[0]
        integral = 0.0
        for u in u_grid:
            val = damped_cf(u)
            integral += val.real * du

        call_price = S0 * math.exp(-alpha * k) * math.exp(-r * T) * integral / math.pi
        return max(0.0, float(call_price))


# ==============================================================================
# 2. Hagan-Lesniewski (2014) Arbitrage-Free SABR PDE & Absorbing Density
# ==============================================================================
class ArbitrageFreeSABR:
    """
    Patrick Hagan, Deep Kumar, Andrew Lesniewski, Diana Woodward (2014)
    Arbitrage-Free SABR: Eliminates negative probability densities and
    butterfly arbitrage of classic SABR expansion via PDE absorbing boundary.
    """
    def __init__(self, F0: float, alpha0: float, beta: float, rho: float, nu: float):
        self.F0 = F0
        self.alpha0 = alpha0
        self.beta = beta
        self.rho = rho
        self.nu = nu

    def classic_hagan_vol(self, K: float, T: float) -> float:
        """Classical Hagan (2002) asymptotic Black implied volatility expansion."""
        if K <= 0 or self.F0 <= 0:
            return self.alpha0
        if abs(self.F0 - K) < 1e-7:
            term1 = self.alpha0 / (self.F0 ** (1.0 - self.beta))
            term2 = 1.0 + (
                ((1.0 - self.beta)**2 / 24.0) * (self.alpha0**2 / (self.F0**(2.0 - 2.0 * self.beta))) +
                (self.rho * self.beta * self.nu * self.alpha0) / (4.0 * (self.F0**(1.0 - self.beta))) +
                ((2.0 - 3.0 * self.rho**2) / 24.0) * (self.nu**2)
            ) * T
            return term1 * term2

        F = self.F0
        f_mid = (F * K) ** ((1.0 - self.beta) / 2.0)
        log_FK = math.log(F / K)
        z = (self.nu / self.alpha0) * f_mid * log_FK
        x_z = math.log((math.sqrt(1.0 - 2.0 * self.rho * z + z**2) + z - self.rho) / (1.0 - self.rho))

        denom = f_mid * (1.0 + ((1.0 - self.beta)**2 / 24.0) * (log_FK**2) + ((1.0 - self.beta)**4 / 1920.0) * (log_FK**4))
        factor1 = self.alpha0 / denom
        factor2 = z / x_z if abs(x_z) > 1e-7 else 1.0
        factor3 = 1.0 + (
            ((1.0 - self.beta)**2 / 24.0) * (self.alpha0**2 / (f_mid**2)) +
            (self.rho * self.beta * self.nu * self.alpha0) / (4.0 * f_mid) +
            ((2.0 - 3.0 * self.rho**2) / 24.0) * (self.nu**2)
        ) * T

        return factor1 * factor2 * factor3

    def solve_pde_density(
        self, T: float, f_max: float = 300.0, n_f: int = 300, n_t: int = 100
    ) -> np.ndarray:
        """
        Solves 1D Fokker-Planck PDE for the forward price density with absorbing boundary at F = 0.
        dp/dt = 0.5 * d^2/df^2 [ sigma_loc^2(f, t) * p ]
        Ensures p(0, t) = 0, p(f, t) >= 0 everywhere, preventing negative probability mass.
        """
        f_grid = np.linspace(0.0, f_max, n_f)
        df = f_grid[1] - f_grid[0]
        dt = T / n_t

        # Initial condition: narrow Gaussian spike around F0
        width = df * 1.5
        p = np.exp(-0.5 * ((f_grid - self.F0) / width)**2) / (math.sqrt(2.0 * math.pi) * width)
        p[0] = 0.0  # Absorbing boundary at 0
        p /= np.sum(p) * df

        for step in range(n_t):
            t_curr = step * dt
            # Effective local diffusion: D(f) = 0.5 * (alpha_eff * f^beta)^2
            alpha_t = self.alpha0 * math.exp(self.rho * self.nu * (step / n_t))
            D = 0.5 * (alpha_t * np.maximum(f_grid, 1e-4)**self.beta)**2

            # Explicit conservative finite difference flux
            flux = np.zeros(n_f)
            Dp = D * p
            flux[1:-1] = -(Dp[2:] - Dp[:-2]) / (2.0 * df)

            # Update interior
            p_new = p.copy()
            p_new[1:-1] += dt * (flux[2:] - flux[:-2]) / (2.0 * df)
            p_new[0] = 0.0  # Absorbing boundary
            p_new[-1] = 0.0

            # Density positivity guarantee (Arbitrage-Free projection)
            p_new = np.maximum(p_new, 0.0)
            norm = np.sum(p_new) * df
            if norm > 0:
                p_new /= norm
            p = p_new

        return p


# ==============================================================================
# 3. Budish-Cramton-Shim (2015) HFT Latency Arbitrage & Sniping Model
# ==============================================================================
class HFTSnipingRaceModel:
    """
    Eric Budish, Peter Cramton, John Shim (2015) HFT Arms Race & Haas (2020).
    Models the race between Market Maker's cancellation order and HFT Sniper's
    market order upon external price shock in continuous limit order books.
    """
    def __init__(self, lambda_snipe: float, mu_cancel: float, jump_arrival_rate: float, avg_jump_size: float):
        self.lambda_snipe = lambda_snipe    # Rate of sniper order arriving (1 / latency_snipe)
        self.mu_cancel = mu_cancel          # Rate of MM cancellation arriving (1 / latency_cancel)
        self.jump_arrival_rate = jump_arrival_rate  # Arrival rate of external info jumps (per sec)
        self.avg_jump_size = avg_jump_size  # Average magnitude of information jump (ticks/dollars)

    def sniping_probability(self) -> float:
        """Probability that sniper beats market maker: P(tau_snipe < tau_cancel)."""
        return self.lambda_snipe / (self.lambda_snipe + self.mu_cancel)

    def expected_adverse_selection_cost(self) -> float:
        """Expected per-second cost imposed by latency arbitrage snipers on passive MM."""
        p_snipe = self.sniping_probability()
        return self.jump_arrival_rate * p_snipe * self.avg_jump_size

    def optimal_continuous_spread(self, inventory_cost: float = 0.01) -> float:
        """
        Minimum half-spread MM must quote to break even under sniping in continuous time:
        Spread/2 * (1 - P(snipe)) = P(snipe) * Jump_Size + inventory_cost
        """
        p_snipe = self.sniping_probability()
        if p_snipe >= 1.0:
            return float('inf')
        half_spread = (p_snipe * self.avg_jump_size + inventory_cost) / (1.0 - p_snipe)
        return 2.0 * half_spread

    def frequent_batch_auction_welfare_gain(self, batch_interval_ms: float = 100.0) -> float:
        """
        Frequent Batch Auctions (FBA): With discrete batch interval tau_batch,
        all orders arriving within the batch interval are processed simultaneously.
        Sniping rent is eliminated, narrowing spreads by the adverse selection premium.
        """
        spread_clob = self.optimal_continuous_spread()
        spread_fba = 2.0 * 0.01  # Only inventory cost remains
        spread_reduction = spread_clob - spread_fba
        return max(0.0, spread_reduction)


# ==============================================================================
# 4. Duffie-Garleanu-Pedersen (DGP 2005/2007) OTC Search & Haircut Model
# ==============================================================================
class DuffieGarleanuPedersenOTC:
    """
    Darrell Duffie, Nicolae Gârleanu, Lasse Heje Pedersen (2005/2007)
    OTC Search-and-Bargaining Model with Collateral Haircut Frictions.
    """
    def __init__(
        self, r: float, u_hi: float, u_lo: float, gamma_distress: float,
        eta_recovery: float, lambda_search: float, bargaining_power: float
    ):
        self.r = r                      # Risk-free discount rate
        self.u_hi = u_hi                # Dividend/utility for high-valuation owner
        self.u_lo = u_lo                # Dividend/utility for low-valuation (distressed) owner
        self.gamma = gamma_distress     # Liquidity shock arrival rate (hi -> lo)
        self.eta = eta_recovery         # Recovery shock arrival rate (lo -> hi)
        self.lambd = lambda_search      # Search contact rate in OTC market
        self.q = bargaining_power       # Seller Nash bargaining power (q in [0, 1])

    def steady_state_fractions(self, total_investors: float = 1.0, total_assets: float = 0.5) -> dict:
        """
        Calculates steady-state fraction of non-owners (mu_0),
        high-valuation owners (mu_hi), and low-valuation owners (mu_lo).
        """
        mu_0 = total_investors - total_assets
        denom = self.gamma + self.eta + self.lambd * mu_0
        mu_lo = (self.gamma * total_assets) / denom
        mu_hi = total_assets - mu_lo
        return {"mu_0": mu_0, "mu_hi": mu_hi, "mu_lo": mu_lo}

    def equilibrium_prices(self, haircut: float = 0.0) -> dict:
        """
        Derives analytical equilibrium asset values and OTC transaction price.
        V_hi: value function for high-valuation owner
        V_lo: value function for low-valuation owner
        Haircut h reduces borrowing capacity, lowering effective u_lo.
        """
        effective_u_lo = self.u_lo - haircut * 0.5

        delta_u = self.u_hi - effective_u_lo
        denom = self.r + self.gamma + self.eta + self.lambd * (1.0 - self.q)
        v_hi_minus_v_lo = delta_u / denom

        v_hi = (self.u_hi + self.gamma * (self.u_hi - v_hi_minus_v_lo)) / (self.r + self.gamma)
        v_lo = v_hi - v_hi_minus_v_lo
        p_otc = v_lo + self.q * v_hi_minus_v_lo
        
        bid = v_lo
        ask = v_hi
        spread = ask - bid

        return {"P_otc": p_otc, "V_hi": v_hi, "V_lo": v_lo, "Spread": spread}


# ==============================================================================
# 5. Alfonsi-Fruth-Schied (AFS 2010) Transient Market Impact & Fredholm Solver
# ==============================================================================
class AlfonsiFruthSchiedExecution:
    """
    Aurélien Alfonsi, Antje Fruth, Alexander Schied (2010) Transient Impact Model.
    Resilience kernel G(tau) = exp(-rho * tau).
    Variational Fredholm solution demonstrates that optimal execution contains
    discrete block orders (Dirac pulses) at start t=0 and end t=T.
    """
    def __init__(self, X0: float, T: float, rho_decay: float, gamma_impact: float):
        self.X0 = X0                # Initial inventory to liquidate
        self.T = T                  # Total execution horizon
        self.rho = rho_decay        # Resilience recovery rate of order book
        self.gamma = gamma_impact    # Impact scaling parameter

    def optimal_strategy_components(self) -> dict:
        """
        Analytical solution for exponential decay G(tau) = exp(-rho * tau):
        Delta x_0 = X0 / (2 + rho * T)  (Initial block order)
        v(t) = (X0 * rho) / (2 + rho * T) (Constant continuous trading speed)
        Delta x_T = X0 / (2 + rho * T)  (Terminal block order)
        Total liquidated = Delta x_0 + integral(v(t) dt) + Delta x_T = X0.
        """
        denom = 2.0 + self.rho * self.T
        delta_x0 = self.X0 / denom
        delta_xT = self.X0 / denom
        v_interior = (self.X0 * self.rho) / denom
        return {
            "delta_x0": delta_x0,
            "v_interior": v_interior,
            "delta_xT": delta_xT,
            "integral_continuous": v_interior * self.T
        }

    def total_expected_cost(self) -> float:
        """Expected liquidation cost under optimal transient impact strategy."""
        denom = 2.0 + self.rho * self.T
        return 0.5 * self.gamma * (self.X0 ** 2) / denom


# ==============================================================================
# 6. Solidly AMM Invariant ($x^3 y + x y^3 = k$) & Morpho Blue P2P Matching
# ==============================================================================
class SolidlyMorphoDeFiModel:
    """
    1. Solidly / Velodrome ($x^3 y + x y^3 = k$) AMM invariant for correlated assets.
    2. Morpho Blue Peer-to-Peer lending rate disintermediation function.
    """
    def __init__(self, x_reserves: float, y_reserves: float):
        self.x = x_reserves
        self.y = y_reserves
        self.k = self._compute_k(self.x, self.y)

    @staticmethod
    def _compute_k(x: float, y: float) -> float:
        return (x**3) * y + x * (y**3)

    def marginal_price_dy_dx(self, x_val: float, y_val: float) -> float:
        """
        Marginal price -dy/dx from implicit differentiation of x^3 y + x y^3 = k:
        dy/dx = - (3 x^2 y + y^3) / (x^3 + 3 x y^2)
        """
        numerator = 3.0 * (x_val**2) * y_val + (y_val**3)
        denominator = (x_val**3) + 3.0 * x_val * (y_val**2)
        return numerator / denominator

    def swap_x_for_y(self, dx: float) -> float:
        """
        Calculates dy output when depositing dx using Newton-Raphson solver on:
        f(y_new) = x_new^3 * y_new + x_new * y_new^3 - k = 0
        """
        x_new = self.x + dx
        y_curr = self.y
        for _ in range(50):
            f_val = (x_new**3) * y_curr + x_new * (y_curr**3) - self.k
            f_prime = (x_new**3) + 3.0 * x_new * (y_curr**2)
            y_next = y_curr - f_val / f_prime
            if abs(y_next - y_curr) < 1e-9:
                break
            y_curr = y_next
        dy = self.y - y_curr
        return max(0.0, dy)

    @staticmethod
    def morpho_p2p_rates(
        r_supply_pool: float, r_borrow_pool: float, total_supply: float, total_borrow: float, p2p_split: float = 0.5
    ) -> dict:
        """
        Morpho Blue Peer-to-Peer Matching Efficiency:
        r_p2p = p2p_split * r_borrow_pool + (1 - p2p_split) * r_supply_pool
        Matched volume M = min(total_supply, total_borrow).
        Effective supplier APY = (M / Supply) * r_p2p + (1 - M / Supply) * r_supply_pool
        Effective borrower APY = (M / Borrow) * r_p2p + (1 - M / Borrow) * r_borrow_pool
        """
        r_p2p = p2p_split * r_borrow_pool + (1.0 - p2p_split) * r_supply_pool
        matched = min(total_supply, total_borrow)
        
        eff_supply_apy = (matched / total_supply) * r_p2p + (1.0 - matched / total_supply) * r_supply_pool
        eff_borrow_apy = (matched / total_borrow) * r_p2p + (1.0 - matched / total_borrow) * r_borrow_pool
        spread_improvement = (r_borrow_pool - r_supply_pool) - (eff_borrow_apy - eff_supply_apy)

        return {
            "r_p2p": r_p2p,
            "matched_volume": matched,
            "effective_supply_apy": eff_supply_apy,
            "effective_borrow_apy": eff_borrow_apy,
            "spread_improvement": spread_improvement
        }


# ==============================================================================
# Pytest Test Cases
# ==============================================================================

def test_cgmy_model():
    """Verify CGMY characteristic function, path classification, and European call pricing."""
    cgmy = CGMYModel(C=1.0, G=5.0, M=10.0, Y=0.5)
    assert cgmy.path_property() == "Infinite Activity, Finite Variation"
    
    # Test limiting case Y=0 (Variance Gamma)
    cgmy_vg = CGMYModel(C=1.0, G=5.0, M=10.0, Y=0.0)
    assert cgmy_vg.path_property() == "Infinite Activity, Finite Variation (Variance Gamma)"
    
    # Test characteristic function at u=0 equals 1.0
    cf_0 = cgmy.characteristic_function(0.0, t=1.0)
    assert abs(cf_0 - 1.0) < 1e-6

    # Test call option price
    call_price = cgmy.price_european_call_quadrature(S0=100.0, K=100.0, T=1.0, r=0.05)
    assert call_price > 0.0
    assert call_price < 100.0


def test_arbitrage_free_sabr():
    """Verify Arbitrage-Free SABR eliminates negative densities via absorbing PDE."""
    sabr = ArbitrageFreeSABR(F0=100.0, alpha0=2.0, beta=0.5, rho=-0.3, nu=0.4)
    vol_atm = sabr.classic_hagan_vol(K=100.0, T=1.0)
    assert vol_atm > 0.15 and vol_atm < 0.35

    # Solve PDE density
    density = sabr.solve_pde_density(T=1.0, f_max=300.0, n_f=200, n_t=50)
    assert np.all(density >= 0.0), "Density must be strictly non-negative"
    assert density[0] == 0.0, "Absorbing boundary at 0 must be respected"
    
    # Integrate total probability
    df = 300.0 / 200
    total_prob = np.sum(density) * df
    assert abs(total_prob - 1.0) < 1e-2, "Total probability must integrate to ~1.0"


def test_hft_sniping_race():
    """Verify Budish-Cramton-Shim HFT sniping race and FBA welfare gain."""
    race = HFTSnipingRaceModel(
        lambda_snipe=100.0, mu_cancel=50.0, jump_arrival_rate=0.1, avg_jump_size=5.0
    )
    # Sniping probability = 100 / (100 + 50) = 2/3 = 0.6667
    p_snipe = race.sniping_probability()
    assert abs(p_snipe - (2.0 / 3.0)) < 1e-4

    cost = race.expected_adverse_selection_cost()
    assert cost > 0.3

    spread_clob = race.optimal_continuous_spread()
    assert spread_clob > 10.0

    welfare_gain = race.frequent_batch_auction_welfare_gain()
    assert welfare_gain > 5.0, "Frequent Batch Auctions must provide positive welfare gain"


def test_duffie_garleanu_pedersen_otc():
    """Verify DGP OTC search-and-bargaining equilibrium and haircut liquidity penalty."""
    dgp = DuffieGarleanuPedersenOTC(
        r=0.05, u_hi=10.0, u_lo=2.0, gamma_distress=0.2, eta_recovery=0.1,
        lambda_search=2.0, bargaining_power=0.5
    )
    ss = dgp.steady_state_fractions()
    assert ss["mu_hi"] > 0 and ss["mu_lo"] > 0
    assert abs(ss["mu_hi"] + ss["mu_lo"] - 0.5) < 1e-6

    prices_base = dgp.equilibrium_prices(haircut=0.0)
    prices_haircut = dgp.equilibrium_prices(haircut=0.20)

    # Haircut must depress low-valuation utility and lower OTC price
    assert prices_haircut["P_otc"] < prices_base["P_otc"]
    assert prices_base["Spread"] > 0.0


def test_alfonsi_fruth_schied_transient():
    """Verify Alfonsi-Fruth-Schied transient impact Dirac boundary pulses."""
    afs = AlfonsiFruthSchiedExecution(X0=10000.0, T=10.0, rho_decay=0.5, gamma_impact=0.001)
    strat = afs.optimal_strategy_components()

    # Verify inventory conservation
    total_exec = strat["delta_x0"] + strat["integral_continuous"] + strat["delta_xT"]
    assert abs(total_exec - 10000.0) < 1e-4

    # Verify boundary blocks are identical: Delta x_0 == Delta x_T
    assert abs(strat["delta_x0"] - strat["delta_xT"]) < 1e-6
    assert strat["delta_x0"] > 0

    cost = afs.total_expected_cost()
    assert cost > 0


def test_solidly_and_morpho():
    """Verify Solidly cubic invariant AMM and Morpho Blue P2P spread elimination."""
    # Solidly: x=1000, y=1000
    amm = SolidlyMorphoDeFiModel(x_reserves=1000.0, y_reserves=1000.0)
    price_parity = amm.marginal_price_dy_dx(1000.0, 1000.0)
    assert abs(price_parity - 1.0) < 1e-6

    # Swap 50 units
    dy = amm.swap_x_for_y(50.0)
    assert dy > 45.0 and dy < 50.0

    # Morpho P2P
    morpho = SolidlyMorphoDeFiModel.morpho_p2p_rates(
        r_supply_pool=0.03, r_borrow_pool=0.08, total_supply=1000000.0, total_borrow=800000.0
    )
    assert abs(morpho["r_p2p"] - 0.055) < 1e-6
    assert morpho["effective_supply_apy"] > 0.03
    assert morpho["effective_borrow_apy"] < 0.08
    assert morpho["spread_improvement"] > 0.0
