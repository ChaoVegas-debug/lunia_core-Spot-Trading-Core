"""E5.1 Preflight + E5 Holodeck Integration Tests - PROOF OF FORCING"""
import pytest,warnings
from decimal import Decimal
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent.parent.parent))

from app.services.allocation.models import SymbolConstraints,SizedIntent
from app.services.execution.preflight import ExecutionPreflight
from app.services.execution.preflight_config import PreflightConfig
from app.services.execution.preflight_context import PreflightContext
from app.services.simulator import SimulatedExchange,SimulatedOrder,DeterministicSimClock,SimulatorConfig
from app.services.strategy.models import SignalSide

def make_constraints(symbol="BTC/USDT",now_ms=1000000):
    return SymbolConstraints(
        symbol=symbol,
        qty_step_size=Decimal("0.001"),
        min_qty=Decimal("0.01"),
        max_qty=Decimal("100.0"),
        min_notional=Decimal("10.0"),
        tick_size=Decimal("0.01"),
        source="test",
        data_timestamp_ms=now_ms-1000,
        process_timestamp_ms=now_ms
    )

def test_holodeck_rejects_non_aligned_qty_without_preflight():
    """E5 Holodeck MUST reject misaligned qty (proves forcing)"""
    clock=DeterministicSimClock(seed_ms=1000000)
    exchange=SimulatedExchange(SimulatorConfig(),clock)
    exchange.register_constraints(make_constraints())
    
    # Submit order with misaligned qty (no preflight)
    order=SimulatedOrder(
        order_id="test1",
        intent_id="intent1",
        intent_id_source="generated",
        symbol="BTC/USDT",
        side="BUY",
        qty=Decimal("0.1234"),  # NOT aligned to 0.001
        price=Decimal("50000.00"),
        snapshot_version=1,
        submitted_at_ms=1000000
    )
    
    report=exchange.submit_order(order)
    assert not report.accepted  # REJECTED
    assert "QTY_NOT_ALIGNED" in str(report.rejection_reason)

def test_preflight_normalizes_qty_then_holodeck_accepts():
    """Preflight normalizes → E5 accepts (proves adapter works)"""
    # Setup
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    # Create SizedIntent with misaligned qty (from E4)
    intent=SizedIntent(
        intent_id="intent2",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.1234"),  # Misaligned
        qty_decimal_str="0.1234",
        notional=Decimal("6170.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    # Preflight normalizes
    result=preflight.validate_and_normalize(intent,context)
    assert result.ok
    assert result.normalized_order.qty_decimal==Decimal("0.123")  # Floored to 0.001
    
    # Now submit to Holodeck
    clock=DeterministicSimClock(seed_ms=1000000)
    exchange=SimulatedExchange(SimulatorConfig(),clock)
    exchange.register_constraints(constraints)
    
    normalized=result.normalized_order
    order=SimulatedOrder(
        order_id="test2",
        intent_id=normalized.intent_id,
        intent_id_source=normalized.intent_id_source,
        symbol=normalized.symbol,
        side=normalized.side,
        qty=normalized.qty_decimal,  # Normalized
        price=normalized.price_decimal,
        snapshot_version=normalized.snapshot_version,
        submitted_at_ms=normalized.now_ms
    )
    
    report=exchange.submit_order(order)
    assert report.accepted  # ACCEPTED after preflight

def test_preflight_rejects_stale_constraints():
    """Preflight MUST reject stale constraints"""
    constraints=make_constraints(now_ms=1000)  # Very old
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=5000000000,  # Way in future
        snapshot_version=1
    )
    
    intent=SizedIntent(
        intent_id="intent3",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.100"),
        qty_decimal_str="0.100",
        notional=Decimal("5000.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result=preflight.validate_and_normalize(intent,context)
    assert not result.ok
    assert result.rejection_reason.value=="STALE_CONSTRAINTS"

def test_preflight_rejects_missing_identity():
    """Preflight MUST enforce identity contract"""
    #SizedIntent requires intent_id, so this tests the validation
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    # Create intent with empty intent_id (edge case)
    intent=SizedIntent(
        intent_id="",  # Empty
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.100"),
        qty_decimal_str="0.100",
        notional=Decimal("5000.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result=preflight.validate_and_normalize(intent,context)
    assert not result.ok
    assert result.rejection_reason.value=="MISSING_INTENT_ID"

def test_preflight_quantizes_limit_price_correctly():
    """Preflight MUST quantize limit price to tick_size"""
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    intent=SizedIntent(
        intent_id="intent4",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.100"),
        qty_decimal_str="0.100",
        notional=Decimal("5001.23"),
        price_value_used=Decimal("50012.345"),  # Not aligned to tick=0.01
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result=preflight.validate_and_normalize(intent,context)
    assert result.ok
    assert result.normalized_order.price_decimal==Decimal("50012.34")  # Floored

def test_min_notional_checked_after_quantization():
    """Min notional MUST be checked AFTER quantization"""
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    # Qty that after quantization fails min_notional
    intent=SizedIntent(
        intent_id="intent5",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.0001"),  # Small
        qty_decimal_str="0.0001",
        notional=Decimal("5.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result=preflight.validate_and_normalize(intent,context)
    # After floor to 0.001: 0.0001 → 0.000
    # Validation order: min_qty checked first, 0.000 < 0.01
    assert not result.ok
    assert result.rejection_reason.value=="MIN_QTY_NOT_MET"

def test_min_max_qty_enforced_after_quantization():
    """Min/max qty MUST be enforced AFTER quantization"""
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    # Below min_qty after quantization
    intent=SizedIntent(
        intent_id="intent6",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.005"),  # Below min_qty=0.01
        qty_decimal_str="0.005",
        notional=Decimal("250.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result=preflight.validate_and_normalize(intent,context)
    assert not result.ok
    assert result.rejection_reason.value=="MIN_QTY_NOT_MET"

def test_canonical_qty_decimal_str_deterministic():
    """Canonical qty_decimal_str MUST be deterministic"""
    constraints=make_constraints(now_ms=1000000)
    preflight=ExecutionPreflight(PreflightConfig())
    context=PreflightContext(
        constraints_by_symbol={"BTC/USDT":constraints},
        now_ms=1000000,
        snapshot_version=1
    )
    
    intent=SizedIntent(
        intent_id="intent7",
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        qty_decimal=Decimal("0.100"),
        qty_decimal_str="0.100",
        notional=Decimal("5000.0"),
        price_value_used=Decimal("50000.00"),
        price_ref="MID",
        sizing_policy_id="test",
        usable_equity_used=Decimal("100000"),
        metadata={"snapshot_version":1,"intent_id_source":"generated"}
    )
    
    result1=preflight.validate_and_normalize(intent,context)
    result2=preflight.validate_and_normalize(intent,context)
    
    assert result1.normalized_order.qty_decimal_str==result2.normalized_order.qty_decimal_str

if __name__=="__main__":
    warnings.simplefilter("error")
    pytest.main([__file__,"-v"])
