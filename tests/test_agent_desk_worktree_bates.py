"""
Automated Test Suite for Agent Desks:
1. Git Worktree Isolation Engine (WorktreeDeskManager / WorktreeManager)
2. David S. Bates (1996) Stochastic Volatility Jump-Diffusion Model (BatesSVJEngine)
"""

import math
from pathlib import Path
import pytest

from src.entropy.agent_desk.core.worktree_manager import (
    WorktreeDeskManager,
    WorktreeManager,
    EphemeralDeskInfo,
    DeskCleanupResult,
    find_free_port,
    worktree_desk_manager,
)
from src.entropy.agent_desk.analysis.bates_svj import (
    BatesParameters,
    BatesSVJEngine,
    BatesPricingResult,
    BatesSurfaceResult,
    black_scholes_call_price,
)


# ==============================================================================
# 1. GIT WORKTREE ISOLATION ENGINE TESTS
# ==============================================================================

def test_worktree_manager_initialization():
    """Verifies that WorktreeDeskManager checks git repos correctly."""
    manager = WorktreeDeskManager()
    assert manager.is_git_repository("C:/EntropiAI") is True
    head = manager.get_current_head("C:/EntropiAI")
    assert head is not None and len(head) == 40


def test_worktree_manager_port_allocation():
    """Verifies that dynamic port allocation avoids collisions and returns valid port."""
    p1 = find_free_port(start_port=8200, max_port=8250)
    p2 = find_free_port(start_port=8251, max_port=8300)
    assert p1 > 0
    assert p2 > 0
    assert p1 != p2


def test_worktree_manager_session_lifecycle():
    """Verifies creation, sandbox env vars, and clean teardown of an ephemeral worktree."""
    manager = WorktreeDeskManager()
    project_root = "C:/EntropiAI"
    office_id = "test_off"
    agent_id = "architect_01"
    task_id = "t_iso_999"

    # 1. Create worktree
    desk = manager.create_ephemeral_desk(
        project_root=project_root,
        office_id=office_id,
        agent_id=agent_id,
        task_id=task_id,
        base_ref="HEAD",
    )

    assert isinstance(desk, EphemeralDeskInfo)
    assert Path(desk.worktree_dir).exists()
    assert (Path(desk.worktree_dir) / ".git").exists()
    assert desk.is_git_worktree is True

    # 2. Verify sandbox environment variables
    env = desk.env_vars
    assert env["DESK_SANDBOX_DIR"] == desk.worktree_dir
    assert env["DESK_PORT"] == str(desk.allocated_port)
    assert env["PORT"] == str(desk.allocated_port)
    assert env["DESK_OFFICE_ID"] == office_id
    assert env["DESK_AGENT_ID"] == agent_id
    assert env["DESK_TASK_ID"] == task_id
    assert env["DESK_IS_WORKTREE"] == "1"

    # 3. Teardown worktree
    teardown_res = manager.cleanup_desk(desk, merge_back=False)
    assert isinstance(teardown_res, DeskCleanupResult)
    assert teardown_res.worktree_removed is True
    assert not Path(desk.worktree_dir).exists()


def test_worktree_manager_context_manager():
    """Verifies context manager semantics and guaranteed teardown."""
    manager = WorktreeDeskManager()
    project_root = "C:/EntropiAI"
    office_id = "test_off_ctx"
    agent_id = "dev_02"
    task_id = "t_ctx_888"

    target_path = None

    with manager.session(project_root, office_id, agent_id, task_id) as desk:
        target_path = Path(desk.worktree_dir)
        assert target_path.exists()
        assert desk.allocated_port > 0

    # Upon exiting context, worktree must be completely removed
    assert not target_path.exists()


# ==============================================================================
# 2. DAVID S. BATES (1996) SVJ MODEL TESTS
# ==============================================================================

def test_bates_parameters_validation():
    """Verifies strict Pydantic parameter boundaries and Feller condition."""
    # Valid parameters satisfying Feller condition: 2 * 2.0 * 0.04 = 0.16 > 0.3^2 = 0.09
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.3,
        rho=-0.7,
        r=0.05,
        q=0.01,
        jump_lambda=0.2,
        jump_mu=-0.1,
        jump_sigma=0.15,
    )

    assert params.s0 == 100.0
    assert params.feller_ratio > 1.0
    assert params.is_feller_satisfied is True
    # mu_J = exp(-0.1 + 0.5 * 0.15^2) - 1.0 = exp(-0.08875) - 1.0 ~= -0.08494
    assert params.jump_compensator < 0.0

    # Negative spot price must raise validation error
    with pytest.raises(Exception):
        BatesParameters(
            s0=-10.0,
            v0=0.04,
            kappa=2.0,
            theta=0.04,
            sigma_v=0.3,
            rho=-0.7,
        )


def test_bates_characteristic_function_properties():
    """Verifies that the Bates characteristic function satisfies phi(0) == 1."""
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.3,
        rho=-0.7,
        r=0.05,
        q=0.0,
        jump_lambda=0.15,
        jump_mu=-0.08,
        jump_sigma=0.12,
    )
    engine = BatesSVJEngine(params)

    # At u = 0, E[exp(i * 0 * ln(S_T))] must be exactly 1
    phi_0 = engine.characteristic_function(0.0 + 0.0j, t=1.0)
    assert abs(phi_0 - 1.0) < 1e-10

    # Test martingale property: E[S_T] = S_0 * exp((r - q) * T)
    # E[exp(ln(S_T))] = phi(-i)
    phi_minus_i = engine.characteristic_function(-1.0j, t=1.0)
    expected_forward = params.s0 * math.exp((params.r - params.q) * 1.0)
    assert abs(phi_minus_i.real - expected_forward) / expected_forward < 1e-5


def test_bates_put_call_parity():
    """Verifies that European options priced under Bates SVJ satisfy Put-Call Parity."""
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.5,
        theta=0.04,
        sigma_v=0.25,
        rho=-0.6,
        r=0.04,
        q=0.02,
        jump_lambda=0.2,
        jump_mu=-0.05,
        jump_sigma=0.1,
    )
    engine = BatesSVJEngine(params)
    k = 100.0
    t = 0.75

    res = engine.price_european(strike=k, expiry=t, method="gauss_legendre")
    parity_lhs = res.call_price - res.put_price
    parity_rhs = params.s0 * math.exp(-params.q * t) - k * math.exp(-params.r * t)

    assert abs(parity_lhs - parity_rhs) < 1e-4


def test_bates_carr_madan_fft_vs_quadrature():
    """Verifies that Carr-Madan FFT pricing matches Gauss-Legendre quadrature within tight tolerance."""
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.2,
        rho=-0.5,
        r=0.03,
        q=0.0,
        jump_lambda=0.1,
        jump_mu=-0.05,
        jump_sigma=0.1,
    )
    engine = BatesSVJEngine(params)
    k = 100.0
    t = 1.0

    res_quad = engine.price_european(strike=k, expiry=t, method="gauss_legendre")
    res_fft = engine.price_european(strike=k, expiry=t, method="carr_madan_fft")

    # Relative difference between FFT interpolation and direct quadrature should be < 1.5%
    rel_diff = abs(res_quad.call_price - res_fft.call_price) / res_quad.call_price
    assert rel_diff < 0.015


def test_bates_analytical_limit_merton():
    """
    Verifies the Merton (1976) analytical limit:
    When sigma_v -> 0, Bates SVJ converges to the Merton series expansion.
    """
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=1.0,
        theta=0.04,
        sigma_v=0.001,  # Near zero vol-of-vol
        rho=0.0,
        r=0.05,
        q=0.0,
        jump_lambda=0.25,
        jump_mu=-0.1,
        jump_sigma=0.15,
    )
    engine = BatesSVJEngine(params)

    passed, bates_price, merton_price = engine.verify_merton_limit(
        strike=100.0,
        expiry=1.0,
        tolerance_pct=1.0,
    )
    assert passed is True
    assert abs(bates_price - merton_price) / merton_price < 0.005


def test_bates_analytical_limit_black_scholes():
    """
    Verifies the Black-Scholes (1973) analytical limit:
    When jump_lambda = 0 and sigma_v -> 0, Bates SVJ converges to pure Black-Scholes.
    """
    params = BatesParameters(
        s0=100.0,
        v0=0.04,  # sigma = 0.20
        kappa=1.0,
        theta=0.04,
        sigma_v=0.001,  # Near zero vol-of-vol
        rho=0.0,
        r=0.05,
        q=0.0,
        jump_lambda=0.0,  # No jumps
        jump_mu=0.0,
        jump_sigma=0.1,
    )
    engine = BatesSVJEngine(params)

    passed, bates_price, bs_price = engine.verify_black_scholes_limit(
        strike=100.0,
        expiry=1.0,
        tolerance_pct=1.0,
    )
    assert passed is True
    assert abs(bates_price - bs_price) / bs_price < 0.005
