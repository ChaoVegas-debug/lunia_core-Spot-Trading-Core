"""
Epoch 9.5: Fail-Safe Metrics Collector

CRITICAL: This collector CANNOT break the trading loop.
All DB errors are swallowed.
"""
import logging
from typing import Optional

from ..strategy.models import ExecutionProposal
from .models import DecisionEvent

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Fail-safe metrics collector.
    
    Design Law: DB errors NEVER propagate to trading logic.
    """
    
    def __init__(self):
        # In-memory buffer (fallback)
        self._events_buffer = []
    
    def record(self, proposal: ExecutionProposal) -> None:
        """
        Record ExecutionProposal as DecisionEvent.
        
        FAIL-SAFE: Errors logged and swallowed.
        NEVER raises exceptions.
        """
        try:
            # Convert proposal → event
            event = DecisionEvent(
                proposal_id=proposal.id,
                symbol=proposal.symbol,
                side=proposal.side if isinstance(proposal.side, str) else proposal.side.value,
                aggregated_confidence=proposal.aggregated_confidence,
                accepted_strategies=proposal.target_strategies[:],
                rejected_strategies=[
                    {
                        "strategy_id": r.strategy_id,
                        "reason_code": r.reason_code if isinstance(r.reason_code, str) else r.reason_code.value,
                        "detail": r.detail or ""
                    }
                    for r in proposal.rejected_strategies
                ],
                market_state_snapshot=proposal.market_state_snapshot.copy()
            )
            
            # Store in-memory (DB persistence would go here)
            self._events_buffer.append(event)
            
            logger.debug(
                f"Recorded DecisionEvent: {event.id[:8]}... "
                f"({event.symbol} {event.side}, "
                f"{len(event.accepted_strategies)} accepted, "
                f"{len(event.rejected_strategies)} rejected)"
            )
            
        except Exception as e:
            # FAIL-SAFE: Log and swallow
            logger.error(
                f"MetricsCollector.record() failed: {e}",
                exc_info=True,
                extra={"proposal_id": getattr(proposal, 'id', 'unknown')}
            )
            # ❌ NEVER raise — trading loop must continue
    
    def get_events(self) -> list:
        """Get all recorded events"""
        return self._events_buffer.copy()
    
    def clear(self) -> None:
        """Clear buffer (for testing)"""
        self._events_buffer.clear()
