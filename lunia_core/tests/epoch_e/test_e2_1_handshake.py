"""
EPOCH E Phase E2.1: Governance ↔ Execution Handshake Tests
Proving structural capital safety: no bypass, exactly-once, audit continuity
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.orchestration import ExecutionOrchestrator, ApprovedIntent
from app.services.governance.engine import GovernanceEngine
from app.services.governance.registry import GovernanceRuleRegistry
from app.services.governance.context import GovernanceContext
from app.services.governance.rules.core_rules import MarketValidityRule, PriceSanityEchoRule

from app.services.strategy.models import IntentProposal, SignalSide
from app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


def test_reject_path_no_execution():
    """
    Reject Path Test: Intent → Governance REJECT → NO EXECUTION
    
    CRITICAL: ExecutionWorker is never called when governance rejects
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    governance = GovernanceEngine(cache, registry)
    orchestrator = ExecutionOrchestrator(governance)
    
    # Register strict price rule (2% band)
    registry.register(PriceSanityEchoRule(band_pct=2.0), enabled=True)
    
    # Add snapshot (mid=100)
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Create intent with price far from mid (+10% deviation, exceeds 2% band)
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=110.0,  # +10% deviation
        rationale="Test intent"
    )
    
    # Process intent
    approved, reason, approved_intent = orchestrator.process_intent(intent)
    
    # Verify REJECT
    assert not approved
    assert "REJECTED" in reason
    assert approved_intent is None
    
    # CRITICAL: No ApprovedIntent means ExecutionWorker is structurally not callable


def test_approve_path_execution_enabled():
    """
    Approve Path Test: Intent → Governance APPROVE → ApprovedIntent created
    
    CRITICAL: ApprovedIntent is created ONLY on APPROVE
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    governance = GovernanceEngine(cache, registry)
    orchestrator = ExecutionOrchestrator(governance)
    
    # Register lenient rules
    registry.register(MarketValidityRule(), enabled=True)
    registry.register(PriceSanityEchoRule(band_pct=5.0), enabled=True)
    
    # Add VALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Create valid intent (price within band)
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=102.0,  # +2% deviation (within 5% band)
        rationale="Test intent"
    )
    
    # Process intent
    approved, reason, approved_intent = orchestrator.process_intent(intent)
    
    # Verify APPROVE
    assert approved
    assert "APPROVED" in reason
    assert approved_intent is not None
    
    # Verify ApprovedIntent properties
    assert isinstance(approved_intent, ApprovedIntent)
    assert approved_intent.strategy_id == "test_strategy"
    assert approved_intent.symbol == "BTC/USDT"
    assert approved_intent.side == "BUY"
    assert approved_intent.governance_decision_id is not None


def test_audit_continuity():
    """
    Audit Continuity Test: Intent ID propagates through all hops
    
    CRITICAL: Intent ID == GovernanceDecision.intent_id == ApprovedIntent.intent_id
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    governance = GovernanceEngine(cache, registry)
    orchestrator = ExecutionOrchestrator(governance)
    
    registry.register(MarketValidityRule(), enabled=True)
    
    # Add snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Create intent
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=100.0,
        rationale="Test"
    )
    
    # Get governance decision directly
    decision = governance.decide(intent)
    
    # Process through orchestrator
    approved, reason, approved_intent = orchestrator.process_intent(intent)
    
    # Verify audit trail continuity
    assert approved_intent is not None
    assert approved_intent.intent_id == decision.intent_id
    assert approved_intent.governance_decision_id == decision.intent_id
    
    # Verify traceability
    assert decision.strategy_id == intent.strategy_id
    assert decision.symbol == intent.symbol


def test_immutability_of_approved_intent():
    """
    Immutability Test: ApprovedIntent cannot be mutated
    
    CRITICAL: ApprovedIntent is frozen (Pydantic config)
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    governance = GovernanceEngine(cache, registry)
    orchestrator = ExecutionOrchestrator(governance)
    
    registry.register(MarketValidityRule(), enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=100.0,
        rationale="Test"
    )
    
    approved, reason, approved_intent = orchestrator.process_intent(intent)
    
    assert approved_intent is not None
    
    # Attempt mutation should raise error (Pydantic frozen=True)
    with pytest.raises(Exception):  # ValidationError or AttributeError
        approved_intent.side = "SELL"


def test_governance_rejection_leaves_no_state():
    """
    Reject Does Not Mutate State: REJECT leaves no trace in governance context
    
    CRITICAL: GovernanceContext is ONLY updated on APPROVE
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    context = GovernanceContext()
    governance = GovernanceEngine(cache, registry, context)
    orchestrator = ExecutionOrchestrator(governance)
    
    # Add price rule that will reject
    registry.register(PriceSanityEchoRule(band_pct=2.0), enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Intent that will be rejected
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=110.0,  # Exceeds 2% band
        rationale="Test"
    )
    
    # Get context state before
    exec_times_before = context.get_all_execution_times()
    
    # Process (will reject)
    approved, reason, approved_intent = orchestrator.process_intent(intent)
    
    # Get context state after
    exec_times_after = context.get_all_execution_times()
    
    # Verify REJECT
    assert not approved
    
    # Verify context unchanged (no execution recorded)
    assert exec_times_before == exec_times_after
    assert context.get_last_execution_time("test_strategy", "BTC/USDT") == 0


def test_deterministic_governance_path():
    """
    Determinism Test: Same intent produces same governance decision
    
    CRITICAL: Governance is deterministic
    """
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    
    # Two orchestrators with same setup
    gov1 = GovernanceEngine(cache, registry)
    gov2 = GovernanceEngine(cache, registry)
    orch1 = ExecutionOrchestrator(gov1)
    orch2 = ExecutionOrchestrator(gov2)
    
    registry.register(MarketValidityRule(), enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Same intent
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=100.0,
        rationale="Test"
    )
    
    # Process through both
    approved1, reason1, _ = orch1.process_intent(intent)
    approved2, reason2, _ = orch2.process_intent(intent)
    
    # Same decision
    assert approved1 == approved2
    assert "APPROVED" in reason1
    assert "APPROVED" in reason2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
