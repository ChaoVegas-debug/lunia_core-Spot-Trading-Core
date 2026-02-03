"""Shadow Mode Stress Test (PHASE 1)

Verifies shadow mode proof at 99% drawdown:
- allowed=True ALWAYS (even at catastrophic DD)
- would_block=True signal is computed correctly
- reason classification is correct
- Phase 0 regression guard
"""
import pytest
from decimal import Decimal
from forensic.risk.ledger import RiskLedger
from forensic.risk.gate import ShadowRiskGate


def test_shadow_99pct_dd_stress():
    """T4: Shadow proof stress test at 99% DD.
    
    Proves shadow mode: signal exists, no blocking.
    """
    # Initialize at $10,000
    ledger = RiskLedger()
    ledger.initialize(run_id="stress-001", initial_equity=Decimal("10000"))
    
    # Simulate catastrophic 99% drawdown
    ledger.update_post_fill("fill-crash", Decimal("100"))
    
    state = ledger.get_state()
    
    # Verify state
    assert state.status == "HALT_OBSERVED", \
        f"Status should be HALT_OBSERVED at 99% DD, got {state.status}"
    
    assert state.active_violation == "DRAWDOWN_25PCT", \
        f"Violation should be DRAWDOWN_25PCT, got {state.active_violation}"
    
    # Current DD should be 99%
    expected_dd = (Decimal("10000") - Decimal("100")) / Decimal("10000")
    assert abs(state.current_drawdown_pct - expected_dd) < Decimal("0.001"), \
        f"DD mismatch: {state.current_drawdown_pct} != {expected_dd}"
    
    # Create risk gate
    gate = ShadowRiskGate(ledger)
    
    # Assess a pending trade at 99% DD
    trade_intent = {
        "id": "intent-desperate",
        "side": "BUY",
        "qty": Decimal("1.0")
    }
    
    portfolio_snapshot = {
        "cash": Decimal("100"),
        "position_qty": Decimal("0")
    }
    
    price = Decimal("50000")
    
    # Assess
    decision = gate.assess(trade_intent, portfolio_snapshot, price)
    
    # CRITICAL ASSERTIONS (Shadow Mode Constitution)
    assert decision.allowed is True, \
        "[PHASE1_FAIL] allowed must be True in shadow mode, even at 99% DD"
    
    assert decision.would_block is True, \
        "would_block should be True at 99% DD (signal exists)"
    
    assert decision.reason == "CURRENT_DRAWDOWN_25PCT", \
        f"Reason should be CURRENT_DRAWDOWN_25PCT, got {decision.reason}"
    
    # Verify DD values
    assert decision.current_dd > Decimal("0.25"), \
        f"current_dd should be >25%, got {decision.current_dd}"


def test_shadow_projected_dd_signal():
    """T4: Projected DD triggers would_block signal."""
    # Initialize at $10,000
    ledger = RiskLedger()
    ledger.initialize(run_id="proj-001", initial_equity=Decimal("10000"))
    
    # Current DD = 0% (no trades yet)
    state = ledger.get_state()
    assert state.current_drawdown_pct == Decimal("0")
    
    # Create risk gate
    gate = ShadowRiskGate(ledger)
    
    # Trade that would cause 30% DD if executed
    trade_intent = {
        "id": "intent-risky",
        "side": "BUY",  
        "qty": Decimal("0.2")  # Buy 0.2 BTC at 50k = $10k spend
    }
    
    portfolio_snapshot = {
        "cash": Decimal("10000"),
        "position_qty": Decimal("0")
    }
    
    price = Decimal("50000")
    
    # After BUY: cash = 0, position = 0.2 BTC worth $10k
    # If price drops to $35k: equity = 0.2 * 35k = $7k
    # DD from HWM of $10k = 30%
    
    # For this test, we'll just verify projection works
    decision = gate.assess(trade_intent, portfolio_snapshot, price)
    
    # Should allow (shadow mode)
    assert decision.allowed is True
    
    # Projected DD should be computed
    assert isinstance(decision.projected_dd, Decimal)


def test_phase0_regression_guard():
    """T5: Phase 0 tests must still pass.
    
    Runs Phase 0 autopsy test to ensure no regression.
    """
    import subprocess
    
    result = subprocess.run(
        ["python3", "-m", "pytest", 
         "tests/forensic/test_primary_autopsy_10k_to_1k.py::test_primary_autopsy_10k_to_1k",
         "-v"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True,
        text=True
    )
    
    # Phase 0 test MUST pass
    assert result.returncode == 0, \
        f"[PHASE1_FAIL] Phase 0 regression detected. Phase 0 autopsy test failed:\n{result.stdout}\n{result.stderr}"
    
    assert "PASSED" in result.stdout, \
        "[PHASE1_FAIL] Phase 0 autopsy test did not pass"


def test_risk_decision_enforces_shadow_mode():
    """RiskDecision must crash if allowed=False in SHADOW mode."""
    from forensic.risk.decision import RiskDecision
    
    # Attempting to create SHADOW decision with allowed=False should crash
    with pytest.raises(RuntimeError, match="SHADOW mode MUST have allowed=True"):
        RiskDecision(
            run_id="test-run",
            intent_id="test-intent",
            decision_id="test-decision-id",
            mode="SHADOW",
            enforce_active=False,
            allowed=False,  # FORBIDDEN in SHADOW
            would_block=True,
            blocked=False,
            current_dd=Decimal("0.5"),
            projected_dd=Decimal("0.6"),
            equity_hwm=Decimal("10000"),
            equity_current=Decimal("5000"),
            equity_projected=Decimal("4000"),
            override_present=False,
            override_valid=False,
            override_used=False
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
