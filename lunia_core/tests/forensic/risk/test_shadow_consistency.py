"""Shadow Mode Consistency Tests (PHASE 1)

Verifies:
- Equity consistency between RiskLedger and Portfolio
- HWM monotonicity
- Drawdown math correctness (Decimal)
"""
import pytest
from decimal import Decimal
from forensic.risk.ledger import RiskLedger, RiskState


def test_ledger_initialization():
    """T1: Ledger initializes correctly."""
    ledger = RiskLedger()
    
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    state = ledger.get_state()
    
    assert state.run_id == "test-001"
    assert state.equity_high_water_mark == Decimal("10000")
    assert state.current_equity == Decimal("10000")
    assert state.current_drawdown_pct == Decimal("0")
    assert state.status == "HEALTHY"
    assert state.last_trade_id is None


def test_ledger_double_init_crashes():
    """T1: Double initialization crashes loudly."""
    ledger = RiskLedger()
    
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    with pytest.raises(RuntimeError, match="initialize called twice"):
        ledger.initialize(run_id="test-002", initial_equity=Decimal("5000"))


def test_equity_consistency_after_fills():
    """T1: Equity consistency after each fill.
    
    Ledger.current_equity must match Portfolio.equity exactly.
    """
    ledger = RiskLedger()
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    # Simulate fills with portfolio equity tracking
    fills = [
        ("fill-001", Decimal("10050")),  # Profit
        ("fill-002", Decimal("9980")),   # Loss
        ("fill-003", Decimal("10100")),  # New peak
        ("fill-004", Decimal("9500")),   # Drawdown
    ]
    
    for trade_id, portfolio_equity in fills:
        ledger.update_post_fill(trade_id, portfolio_equity)
        
        state = ledger.get_state()
        
        # HARD ASSERTION: Equity must match exactly (Decimal)
        assert state.current_equity == portfolio_equity, \
            f"[PHASE1_FAIL] Equity mismatch: ledger={state.current_equity} vs portfolio={portfolio_equity}"
        
        assert isinstance(state.current_equity, Decimal), \
            f"[PHASE1_FAIL] current_equity must be Decimal, got {type(state.current_equity)}"


def test_hwm_monotonicity():
    """T2: HWM is monotonically non-decreasing."""
    ledger = RiskLedger()
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    # Simulate equity movements
    equities = [
        Decimal("10500"),  # Increase (new HWM)
        Decimal("9800"),   # Decrease (HWM stays)
        Decimal("10200"),  # Increase (HWM stays)
        Decimal("11000"),  # Increase (new HWM)
        Decimal("10000"),  # Decrease (HWM stays)
    ]
    
    prev_hwm = Decimal("10000")
    
    for i, equity in enumerate(equities):
        ledger.update_post_fill(f"fill-{i}", equity)
        
        state = ledger.get_state()
        
        # HWM must never decrease
        assert state.equity_high_water_mark >= prev_hwm, \
            f"[PHASE1_FAIL] HWM decreased: {state.equity_high_water_mark} < {prev_hwm}"
        
        # HWM must be at least current equity
        assert state.equity_high_water_mark >= equity, \
            f"[PHASE1_FAIL] HWM < equity: {state.equity_high_water_mark} < {equity}"
        
        prev_hwm = state.equity_high_water_mark


def test_drawdown_math_correctness():
    """T3: Drawdown math is correct (Decimal exact)."""
    ledger = RiskLedger()
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    # Create peak
    ledger.update_post_fill("fill-001", Decimal("12000"))
    
    # Create drawdown
    ledger.update_post_fill("fill-002", Decimal("9000"))
    
    state = ledger.get_state()
    
    # Expected DD = (12000 - 9000) / 12000 = 0.25
    expected_dd = Decimal("0.25")
    
    # Decimal exact comparison (with tiny tolerance for rounding)
    assert abs(state.current_drawdown_pct - expected_dd) < Decimal("1e-12"), \
        f"[PHASE1_FAIL] DD mismatch: {state.current_drawdown_pct} != {expected_dd}"
    
    # Type check
    assert isinstance(state.current_drawdown_pct, Decimal), \
        f"[PHASE1_FAIL] DD must be Decimal, got {type(state.current_drawdown_pct)}"


def test_status_mapping():
    """T3: Status mapping is correct."""
    ledger = RiskLedger()
    ledger.initialize(run_id="test-001", initial_equity=Decimal("10000"))
    
    # Test cases: (equity, expected_status, expected_violation)
    test_cases = [
        (Decimal("9500"), "HEALTHY", None),      # 5% DD
        (Decimal("8500"), "WARNING", None),      # 15% DD
        (Decimal("8000"), "CRITICAL", None),     # 20% DD exactly
        (Decimal("7400"), "HALT_OBSERVED", "DRAWDOWN_25PCT"),  # 26% DD
    ]
    
    for equity, expected_status, expected_violation in test_cases:
        ledger.update_post_fill(f"fill-{equity}", equity)
        
        state = ledger.get_state()
        
        assert state.status == expected_status, \
            f"Status mismatch at equity={equity}: {state.status} != {expected_status}"
        
        assert state.active_violation == expected_violation, \
            f"Violation mismatch at equity={equity}: {state.active_violation} != {expected_violation}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
