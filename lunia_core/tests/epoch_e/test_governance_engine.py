"""
EPOCH E Phase E2: Governance Engine Tests
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.governance.engine import GovernanceEngine
from lunia_core.app.services.governance.registry import GovernanceRuleRegistry
from lunia_core.app.services.governance.context import GovernanceContext
from lunia_core.app.services.governance.models import DecisionType
from lunia_core.app.services.governance.rules.core_rules import (
    MarketValidityRule,
    PriceSanityEchoRule,
    StrategyCooldownRule
)

from lunia_core.app.services.strategy.models import IntentProposal, SignalSide
from lunia_core.app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


def test_reject_on_invalid_market():
    """Governance rejects if market snapshot is INVALID"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    engine = GovernanceEngine(cache, registry)
    
    # Register market validity rule
    registry.register(MarketValidityRule(), enabled=True)
    
    # Add INVALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.INVALID,
        mid_price=50000.0,
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
        reference_price=50000.0,
        rationale="Test intent"
    )
    
    # Make decision
    decision = engine.decide(intent)
    
    # Verify REJECT
    assert decision.decision == DecisionType.REJECT
    assert "GOV_MD_INVALID" in decision.reason_codes
    assert decision.strategy_id == "test_strategy"


def test_reject_on_price_deviation():
    """Governance rejects if price deviation exceeds band"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    engine = GovernanceEngine(cache, registry)
    
    # Register price sanity rule (5% band)
    registry.register(PriceSanityEchoRule(band_pct=5.0), enabled=True)
    
    # Add VALID snapshot (mid=100)
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
    
    # Create intent with reference_price far from mid (> 5%)
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=110.0,  # +10% deviation
        rationale="Test intent"
    )
    
    # Make decision
    decision = engine.decide(intent)
    
    # Verify REJECT
    assert decision.decision == DecisionType.REJECT
    assert "GOV_PRICE_DEVIATION" in decision.reason_codes


def test_reject_on_cooldown():
    """Governance rejects if strategy is in cooldown (stateful)"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    context = GovernanceContext()
    engine = GovernanceEngine(cache, registry, context)
    
    # Register cooldown rule (10 seconds)
    registry.register(StrategyCooldownRule(cooldown_ms=10000), enabled=True)
    
    # Add VALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
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
        reference_price=50000.0,
        rationale="Test intent"
    )
    
    # First decision (should APPROVE - no previous execution)
    decision1 = engine.decide(intent)
    assert decision1.decision == DecisionType.APPROVE
    
    # Second decision immediately (should REJECT - cooldown)
    decision2 = engine.decide(intent)
    assert decision2.decision == DecisionType.REJECT
    assert "GOV_STRATEGY_COOLDOWN" in decision2.reason_codes


def test_approve_valid_intent():
    """Governance approves valid intent passing all rules"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    engine = GovernanceEngine(cache, registry)
    
    # Register all rules
    registry.register(MarketValidityRule(), enabled=True)
    registry.register(PriceSanityEchoRule(band_pct=5.0), enabled=True)
    registry.register(StrategyCooldownRule(cooldown_ms=10000), enabled=True)
    
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
    
    # Create valid intent (price within band, first execution)
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=102.0,  # +2% deviation (within 5% band)
        rationale="Test intent"
    )
    
    # Make decision
    decision = engine.decide(intent)
    
    # Verify APPROVE
    assert decision.decision == DecisionType.APPROVE
    assert "APPROVED" in decision.reason_codes
    assert decision.strategy_id == "test_strategy"
    assert decision.symbol == "BTC/USDT"


def test_fail_closed_on_exception():
    """Governance fails closed if rule raises exception"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    engine = GovernanceEngine(cache, registry)
    
    # Create a broken rule that always raises exception
    class BrokenRule(MarketValidityRule):
        @property
        def rule_id(self) -> str:
            return "broken_rule"
        
        def evaluate(self, intent, snapshot, context):
            raise ValueError("Intentional exception")
    
    registry.register(BrokenRule(), enabled=True)
    
    # Add VALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
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
        reference_price=50000.0,
        rationale="Test intent"
    )
    
    # Make decision
    decision = engine.decide(intent)
    
    # Verify REJECT (fail-closed)
    assert decision.decision == DecisionType.REJECT
    assert "GOV_RULE_EXCEPTION" in decision.reason_codes


def test_audit_metadata_present():
    """Every decision has audit metadata"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    engine = GovernanceEngine(cache, registry)
    
    registry.register(MarketValidityRule(), enabled=True)
    
    # Add VALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
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
        reference_price=50000.0,
        rationale="Test intent"
    )
    
    # Make decision
    decision = engine.decide(intent)
    
    # Verify audit trail
    assert decision.intent_id is not None
    assert decision.strategy_id == "test_strategy"
    assert decision.symbol == "BTC/USDT"
    assert len(decision.reason_codes) > 0
    assert decision.metadata is not None
    assert decision.decided_at_ms > 0


def test_state_isolation():
    """Cooldown state is isolated per (strategy_id, symbol)"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    context = GovernanceContext()
    engine = GovernanceEngine(cache, registry, context)
    
    registry.register(StrategyCooldownRule(cooldown_ms=10000), enabled=True)
    
    # Add snapshots for BTC and ETH
    snapshot_btc = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot_btc)
    
    snapshot_eth = MarketSnapshot(
        exchange="binance",
        symbol="ETH/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=3000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("ETH/USDT", snapshot_eth)
    
    # Intent for BTC
    intent_btc = IntentProposal(
        strategy_id="strategy_A",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    # Intent for ETH (same strategy, different symbol)
    intent_eth = IntentProposal(
        strategy_id="strategy_A",
        symbol="ETH/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=3000.0,
        rationale="Test"
    )
    
    # First BTC → APPROVE
    decision_btc1 = engine.decide(intent_btc)
    assert decision_btc1.decision == DecisionType.APPROVE
    
    # First ETH → APPROVE (different symbol, no cooldown)
    decision_eth1 = engine.decide(intent_eth)
    assert decision_eth1.decision == DecisionType.APPROVE
    
    # Second BTC → REJECT (cooldown)
    decision_btc2 = engine.decide(intent_btc)
    assert decision_btc2.decision == DecisionType.REJECT


def test_deterministic_decisions():
    """Same input produces same decision"""
    cache = ThreadSafeSnapshotCache()
    registry = GovernanceRuleRegistry()
    
    # Two separate engines with same rules
    engine1 = GovernanceEngine(cache, registry)
    engine2 = GovernanceEngine(cache, registry)
    
    registry.register(MarketValidityRule(), enabled=True)
    registry.register(PriceSanityEchoRule(band_pct=5.0), enabled=True)
    
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
    
    # Same intent
    intent = IntentProposal(
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=102.0,
        rationale="Test"
    )
    
    # Both engines should produce same decision
    decision1 = engine1.decide(intent)
    decision2 = engine2.decide(intent)
    
    assert decision1.decision == decision2.decision
    assert decision1.reason_codes == decision2.reason_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
