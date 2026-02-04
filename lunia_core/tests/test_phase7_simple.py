"""
Phase 7: Simple Integration Test

Tests AI Gateway + Execution Journal + Context Engine end-to-end.

Usage:
    python3 -m lunia_core.tests.test_phase7_simple
"""
import asyncio
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, '/Users/neomind/alladin/lunia_core-Spot-Trading-Core')

from lunia_core.app.services.execution_journal.models import SignalEvent, SignalType
from lunia_core.app.services.ai_gateway.service import AIGatewayService
from lunia_core.app.services.ai_gateway.context_engine import ContextEngine


async def test_ai_gateway_simple():
    """Simple test of AI Gateway with MockProvider."""
    
    print("═" * 60)
    print("Phase 7: AI Gateway Integration Test")
    print("═" * 60)
    
    # Create mock signal event
    signal_event = SignalEvent(
        strategy_id="test_strategy_v1",
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.85,
        timestamp=datetime.utcnow(),
        market_context={
            "regime": "TRENDING",
            "volatility": 0.02
        },
        risk_filters_applied={
            "pln_passed": True,
            "exposure_cap_hit": False
        },
        deterministic_reasoning="Strong uptrend, RSI oversold, volume increasing"
    )
    
    print(f"\n[1] Created SignalEvent:")
    print(f"    Strategy: {signal_event.strategy_id}")
    print(f"    Symbol: {signal_event.symbol}")
    print(f"    Type: {signal_event.signal_type.value}")
    print(f"    Confidence: {signal_event.confidence}")
    print(f"    Reasoning: {signal_event.deterministic_reasoning}")
    
    # Build context
    context_engine = ContextEngine()
    context = context_engine.build_signal_context(signal_event)
    
    print(f"\n[2] Built Context:")
    print(f"    System Time: {context['system_time']}")
    print(f"    System Mode: {context['system_state']['mode']}")
    print(f"    Trading On: {context['system_state']['trading_on']}")
    print(f"    Signal Type: {context['signal']['type']}")
    
    # Initialize AI Gateway with MockProvider
    ai_gateway = AIGatewayService(
        provider=None,  # Defaults to MockProvider
        timeout_seconds=2.0,
        shadow_mode=True
    )
    
    print(f"\n[3] Initialized AI Gateway:")
    print(f"    Provider: {ai_gateway.provider.__class__.__name__}")
    print(f"    Timeout: {ai_gateway.timeout_seconds}s")
    print(f"    Shadow Mode: {ai_gateway.shadow_mode}")
    print(f"    Circuit Breaker State: {ai_gateway.circuit_breaker.state.value}")
    
    # Analyze signal
    print(f"\n[4] Analyzing signal with AI Gateway...")
    analysis = await ai_gateway.analyze_signal(signal_event, context)
    
    if analysis:
        print(f"\n[5] ✅ AI Analysis received:")
        print(f"    Summary: {analysis.summary}")
        print(f"    Risk Flags: {analysis.risk_flags}")
        print(f"    Confirmation: {analysis.confirmation}")
        print(f"    Confidence Score: {analysis.confidence_score}")
        print(f"    Conflicts with Core: {analysis.conflicts_with_core}")
        print(f"    Latency: {analysis.latency_ms}ms")
        print(f"    Cost: ${analysis.cost_usd:.6f}")
        print(f"    Model: {analysis.model_revision}")
    else:
        print(f"\n[5] ❌ AI Analysis FAILED (returned None)")
        print(f"    Circuit Breaker State: {ai_gateway.circuit_breaker.state.value}")
        return False
    
    # Check circuit breaker stats
    stats = ai_gateway.circuit_breaker.get_stats()
    print(f"\n[6] Circuit Breaker Stats:")
    print(f"    State: {stats['state']}")
    print(f"    Success Count: {stats['success_count']}")
    print(f"    Failure Count: {stats['failure_count']}")
    
    print(f"\n{'═' * 60}")
    print(f"✅ TEST PASSED: AI Gateway functional")
    print(f"{'═' * 60}\n")
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_ai_gateway_simple())
    sys.exit(0 if result else 1)
