"""
Context Engine: RAG-Lite State Aggregator

Builds complete, timestamped context for LLM to prevent hallucinations.

CRITICAL: LLM must see the same system state as the operator.
"""
from typing import Dict, List, Optional
from datetime import datetime
import json


class ContextEngine:
    """
    Context Engine - RAG-Lite for AI Gateway
    
    Aggregates system state into structured context for LLM.
    Prevents hallucinations by providing complete, timestamped truth.
    """
    
    def build_signal_context(
        self,
        signal_event,  # SignalEvent model
        ops_state: Optional[Dict] = None,
        pulse_freshness: Optional[Dict] = None,
        recent_events: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Build complete context for signal analysis.
        
        Args:
            signal_event: SignalEvent from Execution Journal
            ops_state: Current operational state (mode, DEFCON, etc.)
            pulse_freshness: Data freshness metrics
            recent_events: Last N EventBus events
        
        Returns:
            Structured context dictionary
        """
        # Current system time (ISO-8601 UTC)
        system_time = datetime.utcnow().isoformat() + "Z"
        
        # Default ops_state if not provided
        if ops_state is None:
            ops_state = self._get_ops_state_fallback()
        
        # Build context
        context = {
            "system_time": system_time,
            
            "system_state": {
                "mode": ops_state.get("system_mode", "UNKNOWN"),
                "defcon": ops_state.get("defcon"),
                "global_age_seconds": ops_state.get("global_age_seconds"),
                "trading_on": ops_state.get("trading_on", False),
                "global_stop": ops_state.get("global_stop", True),
                "run_mode": ops_state.get("run_mode", "UNKNOWN")
            },
            
            "market_state": {
                "symbol": signal_event.symbol,
                "context": signal_event.market_context or {},
                "regime": self._extract_regime(signal_event.market_context)
            },
            
            "signal": {
                "type": signal_event.signal_type.value,
                "confidence": signal_event.confidence,
                "strategy_id": signal_event.strategy_id,
                "timestamp": signal_event.timestamp.isoformat() + "Z",
                "deterministic_reasoning": signal_event.deterministic_reasoning,
                "risk_filters_applied": signal_event.risk_filters_applied or {}
            },
            
            "recent_events": recent_events or [],
            
            "pulse_freshness": pulse_freshness or {},
            
            "metadata": {
                "context_version": "v1.0",
                "generated_at": system_time
            }
        }
        
        return context
    
    def _get_ops_state_fallback(self) -> Dict:
        """
        Get ops_state with fallback.
        
        In production, this would call actual ops_state service.
        For now, return safe defaults.
        """
        try:
            # TODO: Import and call actual get_ops_state()
            # from lunia_core.app.core.ops_state import get_ops_state
            # return get_ops_state()
            pass
        except Exception:
            pass
        
        # Fail-safe defaults
        return {
            "system_mode": "MANUAL",
            "trading_on": False,
            "global_stop": True,
            "run_mode": "UNKNOWN",
            "global_age_seconds": 999
        }
    
    def _extract_regime(self, market_context: Optional[Dict]) -> str:
        """Extract regime from market context."""
        if not market_context:
            return "UNKNOWN"
        
        return market_context.get("regime", "UNKNOWN")
