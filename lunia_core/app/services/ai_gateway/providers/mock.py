"""
AI Gateway Provider: Mock (for testing)

Mock LLM provider for testing without external API calls.
"""
import time
import json
from typing import Dict
from . import AbstractProvider, LLMResponse


class MockProvider(AbstractProvider):
    """
    Mock LLM provider for testing.
    
    Returns deterministic responses based on signal type.
    No external API calls, no cost.
    """
    
    def __init__(self, model: str = "mock-v1", latency_ms: int = 100):
        super().__init__(model=model, api_key=None)
        self.latency_ms = latency_ms
    
    async def complete(self, prompt: str, context: Dict) -> LLMResponse:
        """Generate mock response."""
        # Simulate latency
        time.sleep(self.latency_ms / 1000.0)
        
        # Extract signal type from context
        signal_type = context.get("signal", {}).get("type", "UNKNOWN")
        symbol = context.get("market_state", {}).get("symbol", "UNKNOWN")
        
        # Generate deterministic mock response
        response_dict = {
            "summary": f"Mock analysis for {signal_type} signal on {symbol}",
            "risk_flags": ["mock_risk_1", "mock_risk_2"],
            "confirmation": True,
            "confidence_score": 0.75,
            "confidence_reason": "Mock confidence based on test parameters",
            "conflicts_with_core": False,
            "conflict_reason": "",
            "invalid_if": ["data_age > 30s"],
            "reasoning_version": "core_v7.0",
            "ai_constitution_hash": "0" * 64,  # Mock hash
            "model_revision": self.model
        }
        
        return LLMResponse(
            content=json.dumps(response_dict),
            model=self.model,
            prompt_tokens=100,
            completion_tokens=150,
            latency_ms=self.latency_ms,
            cost_usd=0.0  # Mock: no cost
        )
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Mock provider has zero cost."""
        return 0.0
