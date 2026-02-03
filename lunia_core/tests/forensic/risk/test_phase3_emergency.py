"""Phase 3 Emergency Protocol Tests

Tests emergency safety valve bypass logic.
REDUCE-ONLY enforcement, burn ing house scenarios, malicious ambulance protection.
"""
import pytest
from decimal import Decimal
from forensic.risk.ledger import RiskLedger
from forensic.risk.gate import ShadowRiskGate
from forensic.risk.config import RiskConfig, RiskMode
from forensic.execution.liquidator import Liquidator


def test_t1_burning_house_scenario():
    """T1: Burning house - emergency exit works under halt.
    
    Scenario:
    - DD = 30% (system halted)
    - Standard SELL → BLOCKED
    - Emergency SELL → ALLOWED
    - Position → 0
    """
    # Setup: 30% drawdown (halted)
    ledger = RiskLedger()
    ledger.initialize("burning-house", Decimal("10000"))
    ledger.update_post_fill("crash-fill", Decimal("7000"))  # 30% DD
    
    config = RiskConfig(mode=RiskMode.ENFORCE)
    gate = ShadowRiskGate(ledger, config)
    
    portfolio = {
        "cash": Decimal("7000"),
        "position_qty": Decimal("0.1")
    }
    
    # Standard SELL → BLOCKED
    standard_intent = {
        "id": "standard-sell",
        "side": "SELL",
        "qty": Decimal("0.1"),
        "is_emergency": False
    }
    
    standard_decision = gate.assess(standard_intent, portfolio, Decimal("50000"))
    assert standard_decision.allowed is False, "Standard SELL should be blocked at 30% DD"
    assert standard_decision.blocked is True
    assert standard_decision.block_reason == "CURRENT_DRAWDOWN_25PCT"
    
    # Emergency SELL → ALLOWED (safety valve)
    emergency_intent = {
        "id": "emergency-liquidation",
        "side": "SELL",
        "qty": Decimal("0.1"),
        "is_emergency": True,
        "emergency_reason": "PANIC_BUTTON"
    }
    
    emergency_decision = gate.assess(emergency_intent, portfolio, Decimal("50000"))
    assert emergency_decision.allowed is True, "Emergency SELL should bypass enforcement"
    assert emergency_decision.blocked is False
    assert emergency_decision.is_emergency_bypass is True
    assert emergency_decision.emergency_reason == "PANIC_BUTTON"


def test_t2_malicious_ambulance():
    """T2: Malicious ambulance - emergency BUY is forbidden.
    
    Emergency BUY → BLOCKED + VIOLATION log
    """
    ledger = RiskLedger()
    ledger.initialize("malicious-test", Decimal("10000"))
    ledger.update_post_fill("crash", Decimal("7000"))  # 30% DD
    
    config = RiskConfig(mode=RiskMode.ENFORCE)
    gate = ShadowRiskGate(ledger, config)
    
    portfolio = {
        "cash": Decimal("7000"),
        "position_qty": Decimal("0")
    }
    
    # Emergency BUY → VIOLATION
    malicious_intent = {
        "id": "malicious-buy",
        "side": "BUY",
        "qty": Decimal("0.05"),
        "is_emergency": True,
        "emergency_reason": "ATTEMPT_TO_EXPLOIT"
    }
    
    decision = gate.assess(malicious_intent, portfolio, Decimal("50000"))
    
    assert decision.allowed is False, "Emergency BUY must be blocked"
    assert decision.blocked is True
    assert decision.block_reason == "EMERGENCY_BUY_FORBIDDEN"


def test_t3_mechanical_correctness():
    """T3: Liquidator normalization correctness.
    
    Verify:
    - stepSize normalization
    - truncation loss tracking
    - no oversell
    """
    portfolio = {"position_qty": Decimal("0.123456")}
    
    intent = Liquidator.generate_emergency_liquidation(portfolio)
    
    # Verify normalization
    assert intent["side"] == "SELL"
    assert intent["is_emergency"] is True
    assert intent["qty"] == Decimal("0.12345")  # Truncated to stepSize=0.00001
    
    # Verify metadata
    assert intent["metadata"]["raw_qty"] == "0.123456"
    assert intent["metadata"]["normalized_qty"] == "0.12345"
    assert intent["metadata"]["truncation_loss"] == "0.000006"


def test_t4_phase_0_1_2_regression():
    """T4: Regression guard - Phase 0/1/2 remain GREEN."""
    import subprocess
    
    # Phase 0
    result_p0 = subprocess.run(
        ["python3", "-m", "pytest", 
         "tests/forensic/test_primary_autopsy_10k_to_1k.py", "-q"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result_p0.returncode == 0, f"Phase 0 regression: {result_p0.stdout}"
    
    # Phase 1 & 2
    result_p12 = subprocess.run(
        ["python3", "-m", "pytest",
         "tests/forensic/risk/test_shadow_consistency.py",
         "tests/forensic/risk/test_shadow_stress_99pct_dd.py",
         "tests/forensic/risk/test_phase2_enforcement.py", "-q"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result_p12.returncode == 0, f"Phase 1/2 regression: {result_p12.stdout}"


def test_t5_no_position_crash():
    """T5: Liquidator crashes if no position."""
    portfolio = {"position_qty": Decimal("0")}
    
    with pytest.raises(ValueError, match="No position to liquidate"):
        Liquidator.generate_emergency_liquidation(portfolio)


def test_t6_position_too_small_crash():
    """T6: Liquidator crashes if position smaller than stepSize."""
    portfolio = {"position_qty": Decimal("0.000001")}  # < stepSize
    
    with pytest.raises(ValueError, match="Position too small after normalization"):
        Liquidator.generate_emergency_liquidation(portfolio)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
