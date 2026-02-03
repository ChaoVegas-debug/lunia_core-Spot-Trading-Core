"""
PHASE 11B — Quick Verification Test

Simple test to verify validate.py and complexity.py work correctly.
This is NOT the comprehensive test suite (test_phase11_*.py).
"""

import sys
sys.path.insert(0, '/Users/neomind/alladin/lunia_core-Spot-Trading-Core')

from extensions.genome_dsl import types, validate, complexity


def test_validation_basic():
    """Test basic validation works."""
    # Create simple valid genome with CostGate
    genome = types.StrategyGenome(
        entry_condition=types.And(nodes=[
            types.GreaterThan(
                left=types.PriceMid(),
                right=types.ConstFloat(value=45000.0)
            ),
            types.CostGate(
                expected_profit=types.ATR(window=14),
                cost_multiplier=2.0
            )
        ]),
        exit_condition=types.LessThan(
            left=types.PriceMid(),
            right=types.ConstFloat(value=46000.0)
        ),
        sizing_logic=types.SizingFixed(percent=2.5),
        exit_plan=types.ExitPlanNode(stop_loss_pct=2.0),
        metadata={"strategy_id": "test_001", "name": "Test Strategy"}
    )
    
    result = validate.validate_genome(genome)
    
    print(f"✓ Validation passed: {result.passed}")
    print(f"  Violations: {len(result.violations)}")
    
    assert result.passed == True, f"Expected validation to pass, got violations: {result.violations}"
    print("SUCCESS: Basic validation test passed")


def test_complexity_calculation():
    """Test complexity calculation."""
    # Same genome as above
    genome = types.StrategyGenome(
        entry_condition=types.And(nodes=[
            types.GreaterThan(
                left=types.PriceMid(),
                right=types.ConstFloat(value=45000.0)
            ),
            types.CostGate(
                expected_profit=types.ATR(window=14),
                cost_multiplier=2.0
            )
        ]),
        exit_condition=types.LessThan(
            left=types.PriceMid(),
            right=types.ConstFloat(value=46000.0)
        ),
        sizing_logic=types.SizingFixed(percent=2.5),
        exit_plan=types.ExitPlanNode(stop_loss_pct=2.0),
        metadata={"strategy_id": "test_001", "name": "Test Strategy"}
    )
    
    score = complexity.calculate_complexity(genome)
    
    print(f"✓ Complexity score: {score}")
    print(f"  Within cap (≤30.0): {complexity.enforce_complexity_cap(score)}")
    print(f"  Governance level: {complexity.get_governance_level(score)}")
    
    assert score > 0, "Complexity score should be positive"
    assert score < 30.0, f"Complexity score {score} exceeds cap 30.0"
    assert complexity.enforce_complexity_cap(score) == True
    print("SUCCESS: Complexity calculation test passed")


def test_missing_costgate():
    """Test CostGate detection."""
    # Genome without CostGate
    genome_no_gate = types.StrategyGenome(
        entry_condition=types.GreaterThan(
            left=types.PriceMid(),
            right=types.ConstFloat(value=45000.0)
        ),
        exit_condition=types.LessThan(
            left=types.PriceMid(),
            right=types.ConstFloat(value=46000.0)
        ),
        sizing_logic=types.SizingFixed(percent=2.5),
        exit_plan=types.ExitPlanNode(stop_loss_pct=2.0),
        metadata={"strategy_id": "test_002", "name": "No Gate Test"}
    )
    
    result = validate.validate_genome(genome_no_gate)
    
    print(f"✓ Validation failed (expected): {not result.passed}")
    print(f"  Violations: {len(result.violations)}")
    
    assert result.passed == False, "Expected validation to fail for missing CostGate"
    assert len(result.violations) == 1
    assert result.violations[0].code == "E_COSTGATE_MISSING"
    print(f"  Violation code: {result.violations[0].code}")
    print("SUCCESS: CostGate detection test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 11B VERIFICATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_validation_basic()
        print()
        test_complexity_calculation()
        print()
        test_missing_costgate()
        print()
        print("=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"TEST FAILED ❌: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
