"""
PHASE 13A — SHADOW RUNNER: Supervisor

Multi-loop orchestration with error isolation.

CRITICAL RULES:
- One loop crashes → others continue (error isolation)
- Sequential iteration (no threads in 13A MVP)
- Per-loop statistics and error tracking
"""

from typing import Dict, Any
from .loop import ShadowLoop
from .models import ShadowStepResult


class ShadowSupervisor:
    """
    Multi-strategy shadow supervisor.
    
    Features:
    - Error isolation (per-loop try/except)
    - Sequential sync iteration (MVP)
    - Per-symbol statistics
    """
    
    def __init__(self):
        """Initialize supervisor."""
        self.loops: Dict[str, ShadowLoop] = {}
        self.iteration_count = 0
    
    def add_loop(self, symbol: str, loop: ShadowLoop):
        """
        Add shadow loop for symbol.
        
        Args:
            symbol: Trading symbol
            loop: ShadowLoop instance
        """
        self.loops[symbol] = loop
    
    def run_sync_iteration(self) -> Dict[str, ShadowStepResult]:
        """
        Run one synchronous iteration across all loops.
        
        Returns:
            Dict[symbol → ShadowStepResult]
        """
        self.iteration_count += 1
        results = {}
        
        for symbol, loop in self.loops.items():
            try:
                # Error isolation: each loop wrapped in try/except
                result = loop.tick()
                results[symbol] = result
            except Exception as e:
                # Should never happen (loop.tick() is fail-closed)
                # But for defense-in-depth, create error result
                from .models import ShadowErrorCode
                error_result = ShadowStepResult(
                    timestamp_ms=None,
                    symbol=symbol,
                    status="ERROR",
                    snapshot_health={},
                    error={
                        "code": ShadowErrorCode.EXECUTION_ERROR,
                        "message": f"Supervisor caught exception: {str(e)[:200]}",
                    },
                    audit_ref="SUPERVISOR_CATCH",
                )
                results[symbol] = error_result
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get supervisor status.
        
        Returns:
            Dict with per-symbol statistics
        """
        status = {
            "iteration_count": self.iteration_count,
            "loop_count": len(self.loops),
            "loops": {},
        }
        
        for symbol, loop in self.loops.items():
            loop_stats = loop.get_statistics()
            status["loops"][symbol] = {
                "last_audit_ref": loop_stats["last_audit_ref"],
                "error_count": loop_stats["error_count"],
                "last_error": loop_stats.get("last_error"),
                "tick_count": loop_stats["tick_count"],
                "executed_count": loop_stats["executed_count"],
                "skipped_stale_count": loop_stats["skipped_stale_count"],
                "skipped_noop_count": loop_stats["skipped_noop_count"],
            }
        
        return status
