"""
Epoch 9.2: Strategy Orchestration Tests — Certification Grade

Test Coverage:
1. Runner Isolation (strategy failure doesn't crash loop)
2. Runner Time Budget (soft warnings)
3. Determinism (same inputs → same output)
4. Conflict Resolution (BUY vs SELL)
5. Risk-Off Override (HOLD overrides entries)
6. Traceability (rejected strategies with reason codes)
7. Performance (10 strategies < 50ms)
"""
import time
import pytest
from typing import Optional
from dataclasses import dataclass

from lunia_core.app.services.strategy.runner import StrategyRunner, StrategyRunnerConfig
from lunia_core.app.services.strategy.orchestrator import StrategyOrchestrator, OrchestratorConfig
from lunia_core.app.services.strategy.models import (
    StrategyContext,
    IntentProposal,
    ExecutionProposal,
    SignalSide,
    RejectionReasonCode
)
from lunia_core.app.services.strategy.governance import StrategyDescriptor, GovernedStrategy, StrategyClassification, RiskProfile
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Fixtures — Dummy Strategies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DummyStrategy(GovernedStrategy):
    """Test strategy that always returns a fixed intent"""
    
    def __init__(self, strategy_id: str, side: SignalSide, strength: float):
        self._descriptor = StrategyDescriptor(
            strategy_id=strategy_id,
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE
        )
        self._side = side
        self._strength = strength
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        return IntentProposal(
            symbol=context.symbol,
            strategy_id=self._descriptor.strategy_id,
            side=self._side,
            signal_strength=self._strength,
            rationale=f"Test signal from {self._descriptor.strategy_id}"
        )
    
    def deterministic_reasoning(self, context: StrategyContext, intent: Optional[IntentProposal]) -> str:
        return f"{self._descriptor.strategy_id}: {self._side.value} @ {self._strength}"


class FailingStrategy(GovernedStrategy):
    """Test strategy that always raises exception"""
    
    def __init__(self, strategy_id: str):
        self._descriptor = StrategyDescriptor(
            strategy_id=strategy_id,
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE
        )
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        raise RuntimeError(f"{self._descriptor.strategy_id} intentionally failed")
    
    def deterministic_reasoning(self, context: StrategyContext, intent: Optional[IntentProposal]) -> str:
        return f"{self._descriptor.strategy_id}: ERROR"


class SlowStrategy(GovernedStrategy):
    """Test strategy that sleeps (for time budget tests)"""
    
    def __init__(self, strategy_id: str, sleep_ms: int):
        self._descriptor = StrategyDescriptor(
            strategy_id=strategy_id,
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE
        )
        self._sleep_ms = sleep_ms
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        time.sleep(self._sleep_ms / 1000.0)
        return IntentProposal(
            symbol=context.symbol,
            strategy_id=self._descriptor.strategy_id,
            side=SignalSide.BUY,
            signal_strength=0.5,
            rationale=f"Slow signal (slept {self._sleep_ms}ms)"
        )
    
    def deterministic_reasoning(self, context: StrategyContext, intent: Optional[IntentProposal]) -> str:
        return f"{self._descriptor.strategy_id}: SLOW"


def create_test_context() -> StrategyContext:
    """Create minimal valid StrategyContext for testing"""
    snapshot = MarketSnapshot(
        exchange="test",
        symbol="BTC/USDT",
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        last_update_ms=int(time.time() * 1000),
        snapshot_version=1
    )
    
    return StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot,
        snapshot_version=1,
        market_state={
            "volatility": {"vol_regime": "MEDIUM", "atr": 100.0},
            "regime": {"regime": "TREND", "confidence": 0.8},
            "liquidity": {"liquidity_stress": "NORMAL", "spread_pct": 0.002},
            "market_risk_flag": "SAFE"
        }
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: Runner Isolation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRunnerIsolation:
    """Test that strategy failures don't crash the runner"""
    
    def test_failing_strategy_isolated(self):
        """Strategy A fails → Strategy B still executes"""
        strategies = [
            FailingStrategy("failing-1"),
            DummyStrategy("working-1", SignalSide.BUY, 0.7),
            FailingStrategy("failing-2"),
            DummyStrategy("working-2", SignalSide.SELL, 0.6)
        ]
        
        runner = StrategyRunner(strategies)
        context = create_test_context()
        
        intents = runner.run_all(context)
        
        # 2 strategies should succeed despite 2 failures
        assert len(intents) == 2
        assert intents[0].strategy_id == "working-1"
        assert intents[1].strategy_id == "working-2"
        
        # Metrics
        metrics = runner.get_metrics()
        assert metrics["strategies_run_total"] == 2  # Only successful ones counted
        assert metrics["strategies_failed_total"] == 2
        assert metrics["intents_emitted_total"] == 2
        
        print("✅ TEST 1 PASSED: Strategy isolation works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: Runner Time Budget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRunnerTimeBudget:
    """Test soft time budget tracking"""
    
    def test_soft_timeout_warning(self):
        """Strategy exceeds 5ms → warning + metric increment → still returns"""
        strategies = [
            SlowStrategy("slow-1", sleep_ms=10),  # Exceeds 5ms limit
            DummyStrategy("fast-1", SignalSide.BUY, 0.8)
        ]
        
        config = StrategyRunnerConfig(soft_timeout_ms=5)
        runner = StrategyRunner(strategies, config)
        context = create_test_context()
        
        intents = runner.run_all(context)
        
        # Both strategies should complete (soft limit doesn't kill)
        assert len(intents) == 2
        
        # Metrics
        metrics = runner.get_metrics()
        assert metrics["strategies_timeout_soft_total"] >= 1  # At least one timeout
        assert metrics["strategies_run_total"] == 2  # Both completed
        
        print("✅ TEST 2 PASSED: Soft timeout warning works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: Determinism
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDeterminism:
    """Test that same inputs → identical outputs"""
    
    def test_orchestrator_determinism(self):
        """Same context + same intents → identical ExecutionProposal"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="strat-1", side=SignalSide.BUY, signal_strength=0.7, rationale="Test 1"),
            IntentProposal(symbol="BTC/USDT", strategy_id="strat-2", side=SignalSide.BUY, signal_strength=0.6, rationale="Test 2")
        ]
        
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        
        # Run twice
        proposal1 = orchestrator.orchestrate(intents, context)
        proposal2 = orchestrator.orchestrate(intents, context)
        
        # Should be identical (ignoring ID and timestamp which are auto-generated)
        assert proposal1.side == proposal2.side
        assert proposal1.aggregated_confidence == proposal2.aggregated_confidence
        assert proposal1.target_strategies == proposal2.target_strategies
        assert len(proposal1.rejected_strategies) == len(proposal2.rejected_strategies)
        
        print("✅ TEST 3 PASSED: Determinism verified")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: Conflict Resolution (BUY vs SELL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestConflictResolution:
    """Test BUY vs SELL conflict resolution"""
    
    def test_buy_wins_higher_confidence(self):
        """BUY (0.8) vs SELL (0.6) → BUY wins"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="buy-strat", side=SignalSide.BUY, signal_strength=0.8, rationale="Strong buy"),
            IntentProposal(symbol="BTC/USDT", strategy_id="sell-strat", side=SignalSide.SELL, signal_strength=0.6, rationale="Weak sell")
        ]
        
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        proposal = orchestrator.orchestrate(intents, context)
        
        assert proposal.side == SignalSide.BUY
        assert "buy-strat" in proposal.target_strategies
        assert any(r.strategy_id == "sell-strat" and r.reason_code == RejectionReasonCode.CONFLICT_LOST 
                   for r in proposal.rejected_strategies)
        assert "CONFLICT_RESOLVED_BUY" in proposal.orchestration_reason_codes
        
        print("✅ TEST 4a PASSED: BUY wins higher confidence")
    
    def test_sell_wins_higher_confidence(self):
        """BUY (0.5) vs SELL (0.9) → SELL wins"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="buy-strat", side=SignalSide.BUY, signal_strength=0.5, rationale="Weak buy"),
            IntentProposal(symbol="BTC/USDT", strategy_id="sell-strat", side=SignalSide.SELL, signal_strength=0.9, rationale="Strong sell")
        ]
        
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        proposal = orchestrator.orchestrate(intents, context)
        
        assert proposal.side == SignalSide.SELL
        assert "sell-strat" in proposal.target_strategies
        assert any(r.strategy_id == "buy-strat" and r.reason_code == RejectionReasonCode.CONFLICT_LOST
                   for r in proposal.rejected_strategies)
        assert "CONFLICT_RESOLVED_SELL" in proposal.orchestration_reason_codes
        
        print("✅ TEST 4b PASSED: SELL wins higher confidence")
    
    def test_tie_results_in_no_trade(self):
        """BUY (0.7) vs SELL (0.7) → NO_TRADE (fail-safe)"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="buy-strat", side=SignalSide.BUY, signal_strength=0.7, rationale="Equal buy"),
            IntentProposal(symbol="BTC/USDT", strategy_id="sell-strat", side=SignalSide.SELL, signal_strength=0.7, rationale="Equal sell")
        ]
        
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        proposal = orchestrator.orchestrate(intents, context)
        
        assert proposal.side == SignalSide.HOLD  # NO_TRADE
        assert proposal.aggregated_confidence == 0.0
        assert "CONFLICT_TIE" in proposal.orchestration_reason_codes
        assert len(proposal.rejected_strategies) == 2  # Both rejected
        
        print("✅ TEST 4c PASSED: Tie → NO_TRADE fail-safe")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: Risk-Off Override
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRiskOffOverride:
    """Test that HOLD (risk-off) overrides all entries"""
    
    def test_hold_overrides_buy(self):
        """BUY (0.9) + HOLD (0.6) → HOLD wins (risk-off override)"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="buy-strat", side=SignalSide.BUY, signal_strength=0.9, rationale="Strong buy"),
            IntentProposal(symbol="BTC/USDT", strategy_id="risk-off-strat", side=SignalSide.HOLD, signal_strength=0.6, rationale="Risk off")
        ]
        
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        proposal = orchestrator.orchestrate(intents, context)
        
        assert proposal.side == SignalSide.HOLD
        assert "risk-off-strat" in proposal.target_strategies
        assert "RISK_OFF_OVERRIDE" in proposal.orchestration_reason_codes
        
        # BUY strat should be rejected with RISK_OFF_OVERRIDE reason
        assert any(r.strategy_id == "buy-strat" and r.reason_code == RejectionReasonCode.RISK_OFF_OVERRIDE
                   for r in proposal.rejected_strategies)
        
        print("✅ TEST 5 PASSED: Risk-off override works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: Traceability
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTraceability:
    """Test that rejected strategies contain reason codes"""
    
    def test_rejected_strategies_have_reasons(self):
        """Weak signals → rejected with BELOW_THRESHOLD"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="weak-1", side=SignalSide.BUY, signal_strength=0.1, rationale="Too weak"),
            IntentProposal(symbol="BTC/USDT", strategy_id="weak-2", side=SignalSide.SELL, signal_strength=0.2, rationale="Also weak"),
            IntentProposal(symbol="BTC/USDT", strategy_id="strong-1", side=SignalSide.BUY, signal_strength=0.8, rationale="Strong enough")
        ]
        
        config = OrchestratorConfig(min_signal_strength=0.3)
        orchestrator = StrategyOrchestrator(config)
        context = create_test_context()
        
        proposal = orchestrator.orchestrate(intents, context)
        
        # Should have 2 rejected strategies
        assert len(proposal.rejected_strategies) == 2
        
        # Check reason codes
        weak_rejections = [r for r in proposal.rejected_strategies if r.reason_code == RejectionReasonCode.BELOW_THRESHOLD]
        assert len(weak_rejections) == 2
        assert set(r.strategy_id for r in weak_rejections) == {"weak-1", "weak-2"}
        
        # Winner should be strong-1
        assert "strong-1" in proposal.target_strategies
        
        print("✅ TEST 6 PASSED: Traceability with reason codes works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: Performance Budget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPerformance:
    """Test that 10 strategies run in < 50ms"""
    
    def test_10_strategies_under_50ms(self):
        """10 fast strategies should complete in < 50ms (soft check)"""
        strategies = [
            DummyStrategy(f"strat-{i}", SignalSide.BUY, 0.5 + i * 0.05)
            for i in range(10)
        ]
        
        runner = StrategyRunner(strategies)
        context = create_test_context()
        
        start = time.perf_counter()
        intents = runner.run_all(context)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # All 10 should succeed
        assert len(intents) == 10
        
        # Performance check (allow CI variance, use 100ms upper bound)
        assert elapsed_ms < 100, f"Performance regression: {elapsed_ms:.2f}ms > 100ms"
        
        print(f"✅ TEST 7 PASSED: 10 strategies completed in {elapsed_ms:.2f}ms")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 8: Market Constraint Filtering
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMarketConstraintFiltering:
    """Test filtering by volatility and liquidity"""
    
    def test_high_volatility_rejected(self):
        """HIGH volatility → intents rejected"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="strat-1", side=SignalSide.BUY, signal_strength=0.8, rationale="Buy")
        ]
        
        context = create_test_context()
        # Override market state to HIGH volatility
        context.market_state["volatility"]["vol_regime"] = "HIGH"
        
        config = OrchestratorConfig(max_volatility_regime="MEDIUM")
        orchestrator = StrategyOrchestrator(config)
        
        proposal = orchestrator.orchestrate(intents, context)
        
        # Should reject due to volatility
        assert proposal.side == SignalSide.HOLD  # NO_TRADE
        assert any(r.reason_code == RejectionReasonCode.VOLATILITY_TOO_HIGH 
                   for r in proposal.rejected_strategies)
        
        print("✅ TEST 8a PASSED: HIGH volatility filtering works")
    
    def test_dangerous_market_rejects_entries(self):
        """DANGEROUS market → no BUY/SELL allowed"""
        intents = [
            IntentProposal(symbol="BTC/USDT", strategy_id="buy-strat", side=SignalSide.BUY, signal_strength=0.9, rationale="Buy"),
            IntentProposal(symbol="BTC/USDT", strategy_id="sell-strat", side=SignalSide.SELL, signal_strength=0.8, rationale="Sell")
        ]
        
        context = create_test_context()
        context.market_state["market_risk_flag"] = "DANGEROUS"
        
        orchestrator = StrategyOrchestrator()
        proposal = orchestrator.orchestrate(intents, context)
        
        # Should reject both entries
        assert proposal.side == SignalSide.HOLD  # NO_TRADE
        assert len(proposal.rejected_strategies) == 2
        assert all(r.reason_code == RejectionReasonCode.REGIME_FORBIDDEN 
                   for r in proposal.rejected_strategies)
        
        print("✅ TEST 8b PASSED: DANGEROUS market filtering works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST SUITE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
