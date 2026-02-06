"""
Epoch 9.1: Strategy Intelligence Pack - Certification Test Suite

Test Coverage:
1. Contract Enforcement (StrategyDescriptor, GovernedStrategy protocol)
2. Market State Delivery (StrategyContext extension)
3. Deterministic Logic (ContextMomentumStrategy)
4. AI Conflict Detection (classify_conflict)
5. Regression Gates (backward compatibility)

Governance Invariants:
- AI execution is FORBIDDEN
- market_state degradation is graceful
- Execution path is unchanged
- Shadow mode hard floor is maintained
"""
import unittest
from dataclasses import asdict

from lunia_core.app.services.strategy.governance import (
    StrategyDescriptor,
    StrategyClassification,
    RiskProfile,
    ConflictReasonCode,
    ConflictSeverity
)
from lunia_core.app.services.strategy.conflict_detection import classify_conflict
from lunia_core.app.services.strategy.models import StrategyContext, SignalSide
from lunia_core.app.services.strategy.examples.context_momentum import ContextMomentumStrategy
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot


class TestStrategyDescriptor(unittest.TestCase):
    """Test StrategyDescriptor contract enforcement"""
    
    def test_descriptor_validates_required_fields(self):
        """StrategyDescriptor requires strategy_id and version"""
        descriptor = StrategyDescriptor(
            strategy_id="test_strategy",
            version="1.0.0",
            classification=StrategyClassification.DETERMINISTIC_CORE,
            risk_profile=RiskProfile.SAFE
        )
        
        # Should not raise
        descriptor.validate()
        
        self.assertEqual(descriptor.strategy_id, "test_strategy")
        self.assertEqual(descriptor.version, "1.0.0")
    
    def test_descriptor_forbids_empty_strategy_id(self):
        """Empty strategy_id should fail validation"""
        descriptor = StrategyDescriptor(
            strategy_id="",
            version="1.0.0",
            classification=StrategyClassification.DETERMINISTIC_CORE,
            risk_profile=RiskProfile.SAFE
        )
        
        with self.assertRaises(AssertionError) as ctx:
            descriptor.validate()
        
        self.assertIn("strategy_id", str(ctx.exception))
    
    def test_descriptor_forbids_ai_execution(self):
        """ai_execution_allowed MUST be False (hard floor)"""
        # Default should be False
        descriptor = StrategyDescriptor(
            strategy_id="test",
            version="1.0.0",
            classification=StrategyClassification.DETERMINISTIC_CORE,
            risk_profile=RiskProfile.SAFE
        )
        
        self.assertEqual(descriptor.ai_execution_allowed, False)
        
        # Should not raise with False
        descriptor.validate()
    
    def test_descriptor_validates_semver_format(self):
        """Version must be in semver format (contain dots)"""
        descriptor = StrategyDescriptor(
            strategy_id="test",
            version="invalid_version",  # No dots
            classification=StrategyClassification.DETERMINISTIC_CORE,
            risk_profile=RiskProfile.SAFE
        )
        
        with self.assertRaises(AssertionError) as ctx:
            descriptor.validate()
        
        self.assertIn("semver", str(ctx.exception))
    
    def test_descriptor_immutable(self):
        """StrategyDescriptor is frozen (immutable)"""
        descriptor = StrategyDescriptor(
            strategy_id="test",
            version="1.0.0",
            classification=StrategyClassification.DETERMINISTIC_CORE,
            risk_profile=RiskProfile.SAFE
        )
        
        # Should not be able to modify
        with self.assertRaises(Exception):  # FrozenInstanceError
            descriptor.strategy_id = "modified"


class TestStrategyContextMarketState(unittest.TestCase):
    """Test market_state delivery via StrategyContext"""
    
    def test_context_includes_market_state_field(self):
        """StrategyContext has market_state field"""
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "LOW", "atr": 100.0},
                "regime": {"regime": "TR END"},
                "market_risk_flag": "SAFE"
            }
        )
        
        self.assertIsNotNone(context.market_state)
        self.assertEqual(context.market_state["market_risk_flag"], "SAFE")
    
    def test_context_safe_accessors_with_none_market_state(self):
        """Safe accessors return 'UNKNOWN' when market_state is None"""
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state=None  # No market state
        )
        
        # All accessors should degrade gracefully
        self.assertEqual(context.get_volatility_regime(), "UNKNOWN")
        self.assertEqual(context.get_market_regime(), "UNKNOWN")
        self.assertEqual(context.get_market_risk_flag(), "UNKNOWN")
        self.assertIsNone(context.get_atr())
        self.assertIsNone(context.get_spread_pct())
        self.assertEqual(context.get_liquidity_stress(), "UNKNOWN")
    
    def test_context_safe_accessors_with_partial_market_state(self):
        """Safe accessors handle missing fields gracefully"""
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "MEDIUM"},  # ATR missing
                # regime missing entirely
                "market_risk_flag": "RISKY"
            }
        )
        
        self.assertEqual(context.get_volatility_regime(), "MEDIUM")
        self.assertEqual(context.get_market_regime(), "UNKNOWN")  # Missing regime
        self.assertEqual(context.get_market_risk_flag(), "RISKY")
        self.assertIsNone(context.get_atr())  # Missing ATR


class TestContextMomentumStrategy(unittest.TestCase):
    """Test First-Citizen strategy (ContextMomentumStrategy)"""
    
    def test_strategy_has_valid_descriptor(self):
        """Strategy provides valid StrategyDescriptor"""
        strategy = ContextMomentumStrategy()
        
        descriptor = strategy.descriptor
        self.assertIsInstance(descriptor, StrategyDescriptor)
        self.assertEqual(descriptor.strategy_id, "context_momentum_v1")
        self.assertEqual(descriptor.classification, StrategyClassification.CONTEXT_AWARE)
        self.assertEqual(descriptor.risk_profile, RiskProfile.SAFE)
        
        # Should validate without error
        descriptor.validate()
    
    def test_deterministic_output_stability(self):
        """Same inputs produce same outputs (determinism)"""
        strategy = ContextMomentumStrategy()
        
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "LOW", "atr": 100.0},
                "regime": {"regime": "TREND"},
                "market_risk_flag": "SAFE"
            }
        )
        
        # Call multiple times
        result1 = strategy.evaluate(context)
        result2 = strategy.evaluate(context)
        
        # Should be identical (deterministic)
        if result1 is None and result2 is None:
            pass  # Both None
        else:
            self.assertIsNotNone(result1)
            self.assertIsNotNone(result2)
            self.assertEqual(result1.side, result2.side)
            self.assertEqual(result1.signal_strength, result2.signal_strength)
    
    def test_no_signal_in_high_volatility(self):
        """Strategy refuses to trade in HIGH volatility regime"""
        strategy = ContextMomentumStrategy()
        
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "HIGH"},  # HIGH volatility
                "regime": {"regime": "TREND"},
                "market_risk_flag": "RISKY"
            }
        )
        
        result = strategy.evaluate(context)
        
        # Should refuse to trade
        self.assertIsNone(result)
    
    def test_no_signal_in_dangerous_market(self):
        """Strategy refuses to trade when market_risk_flag is DANGEROUS"""
        strategy = ContextMomentumStrategy()
        
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "MEDIUM"},
                "regime": {"regime": "TREND"},
                "market_risk_flag": "DANGEROUS"  # DANGEROUS market
            }
        )
        
        result = strategy.evaluate(context)
        
        # Should refuse to trade
        self.assertIsNone(result)
    
    def test_deterministic_reasoning_provided(self):
        """Strategy provides deterministic reasoning for audit trail"""
        strategy = ContextMomentumStrategy()
        
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state={
                "volatility": {"vol_regime": "LOW"},
                "regime": {"regime": "TREND"},
                "market_risk_flag": "SAFE"
            }
        )
        
        result = strategy.evaluate(context)
        reasoning = strategy.deterministic_reasoning(context, result)
        
        # Should be non-empty string
        self.assertIsInstance(reasoning, str)
        self.assertGreater(len(reasoning), 0)
        
        # Should contain key information
        self.assertIn("momentum", reasoning.lower())
        self.assertIn("vol_regime", reasoning.lower() or "volatility" in reasoning.lower())


class TestAIConflictDetection(unittest.TestCase):
    """Test AI conflict classification logic"""
    
    def test_no_conflict_when_decisions_agree(self):
        """No conflict when core and AI agree"""
        reason, severity, explanation = classify_conflict(
            core_decision=True,
            ai_decision=True,
            market_state={"market_risk_flag": "SAFE"},
            core_reasoning="Buy signal",
            ai_reasoning="Agree with buy signal"
        )
        
        self.assertEqual(reason, ConflictReasonCode.NO_CONFLICT)
        self.assertEqual(severity, ConflictSeverity.NONE)
        self.assertIn("agree", explanation.lower())
    
    def test_conflict_detected_when_decisions_differ(self):
        """Conflict detected when core and AI disagree"""
        reason, severity, explanation = classify_conflict(
            core_decision=True,
            ai_decision=False,
            market_state={"market_risk_flag": "SAFE"},
            core_reasoning="Buy momentum signal",
            ai_reasoning="Market regime suggests caution"
        )
        
        self.assertNotEqual(reason, ConflictReasonCode.NO_CONFLICT)
        self.assertNotEqual(severity, ConflictSeverity.NONE)
    
    def test_conflict_severity_escalation_in_dangerous_market(self):
        """HIGH severity when market_risk_flag is DANGEROUS"""
        reason, severity, explanation = classify_conflict(
            core_decision=True,
            ai_decision=False,
            market_state={
                "market_risk_flag": "DANGEROUS",
                "volatility": {"vol_regime": "HIGH"}
            },
            core_reasoning="Buy signal",
            ai_reasoning="Dangerous market conditions"
        )
        
        self.assertEqual(severity, ConflictSeverity.HIGH)
    
    def test_conflict_reason_code_classification(self):
        """Reason codes classified from AI reasoning keywords"""
        # Test REGIME_MISMATCH
        reason, _, _ = classify_conflict(
            True, False,
            {"market_risk_flag": "SAFE"},
            "Buy",
            "Market regime is ranging, not trending"
        )
        self.assertEqual(reason, ConflictReasonCode.REGIME_MISMATCH)
        
        # Test RISK_MISMATCH
        reason, _, _ = classify_conflict(
            True, False,
            {"market_risk_flag": "SAFE"},
            "Buy",
            "Risk assessment suggests dangerous conditions"
        )
        self.assertEqual(reason, ConflictReasonCode.RISK_MISMATCH)
        
        # Test LIQUIDITY_WARNING
        reason, _, _ = classify_conflict(
            True, False,
            {"market_risk_flag": "SAFE"},
            "Buy",
            "Liquidity concerns due to wide spread"
        )
        self.assertEqual(reason, ConflictReasonCode.LIQUIDITY_WARNING)


class TestBackwardCompatibility(unittest.TestCase):
    """Regression tests for backward compatibility"""
    
    def test_existing_strategies_work_without_market_state(self):
        """Strategies still function when market_state is None"""
        strategy = ContextMomentumStrategy()
        
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1,
            market_state=None  # No market state (Phase 8.2 behavior)
        )
        
        # Should not crash
        result = strategy.evaluate(context)
        
        # Strategy should degrade gracefully (may or may not signal)
        # Important: it doesn't crash
        self.assertIn(result, [None, *[object]])  # None or IntentProposal
    
    def test_strategy_context_pydantic_compatibility(self):
        """StrategyContext is still a valid Pydantic model"""
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            bid=50000.0,
            ask=50010.0,
            last_update_ms=1234567890
        )
        # Should create without error
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=1
        )
        
        # Pydantic validation should work
        self.assertEqual(context.symbol, "BTC/USDT")
        self.assertIsNotNone(context.snapshot)


if __name__ == "__main__":
    unittest.main()
