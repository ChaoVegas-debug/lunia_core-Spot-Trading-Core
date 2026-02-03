"""
PHASE 9.3 — COOLDOWN MANAGER

Deterministic cooldown state manager to prevent rapid re-entry after losses.

GUARANTEE: Deterministic cooldown behavior (no randomness).

RULES:
- Blocks ENTRY only (never blocks EXIT/REDUCE)
- After losing trade (net_pnl < 0), increase consecutive_losses and set cooldown
- After winning trade (net_pnl >= 0), reset consecutive_losses to 0
- Cooldown duration scales linearly with consecutive losses
"""

from typing import Dict, Tuple, Optional
from extensions.sandbox.paper_types import TradeOutcome


class CooldownState:
    """Per-strategy cooldown state."""
    
    def __init__(self):
        self.consecutive_losses: int = 0
        self.cooldown_until_ts_ms: int = 0
        self.last_exit_ts_ms: int = 0


class CooldownManager:
    """
    Manages cooldown state across strategies.
    
    State persists across ticks (in-memory MVP).
    """
    
    def __init__(self, base_cooldown_ms: int = 60000):  # Default: 1 minute
        """
        Initialize cooldown manager.
        
        Args:
            base_cooldown_ms: Base cooldown duration in milliseconds
        """
        self._base_cooldown_ms = base_cooldown_ms
        self._state: Dict[str, CooldownState] = {}
    
    def can_enter(self, strategy_id: str, now_ts_ms: int) -> Tuple[bool, str]:
        """
        Check if strategy can enter new position.
        
        Args:
            strategy_id: Strategy identifier
            now_ts_ms: Current timestamp
            
        Returns:
            (can_enter, reason_str)
            - (True, "") if allowed
            - (False, "reason") if blocked
        """
        if strategy_id not in self._state:
            return (True, "")
        
        state = self._state[strategy_id]
        
        # Check if cooldown is active
        if now_ts_ms < state.cooldown_until_ts_ms:
            remaining_ms = state.cooldown_until_ts_ms - now_ts_ms
            return (
                False,
                f"Cooldown active (consecutive_losses={state.consecutive_losses}, "
                f"remaining_ms={remaining_ms})"
            )
        
        return (True, "")
    
    def register_outcome(self, outcome: TradeOutcome) -> None:
        """
        Register trade outcome and update cooldown state.
        
        Args:
            outcome: Completed trade outcome
        """
        strategy_id = outcome.strategy_id
        
        # Initialize state if needed
        if strategy_id not in self._state:
            self._state[strategy_id] = CooldownState()
        
        state = self._state[strategy_id]
        state.last_exit_ts_ms = outcome.exit_ts_ms
        
        # Update based on outcome
        if outcome.net_pnl < 0:
            # Losing trade: increment consecutive losses and set cooldown
            state.consecutive_losses += 1
            
            # Cooldown duration scales linearly
            cooldown_duration_ms = self._base_cooldown_ms * (1 + state.consecutive_losses)
            state.cooldown_until_ts_ms = outcome.exit_ts_ms + cooldown_duration_ms
        
        else:
            # Winning trade (net_pnl >= 0): reset consecutive losses
            state.consecutive_losses = 0
            state.cooldown_until_ts_ms = 0
    
    def get_state(self, strategy_id: str) -> Optional[Dict[str, any]]:
        """
        Get current cooldown state for strategy (for debugging/audit).
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            State dict or None if no state exists
        """
        if strategy_id not in self._state:
            return None
        
        state = self._state[strategy_id]
        return {
            "consecutive_losses": state.consecutive_losses,
            "cooldown_until_ts_ms": state.cooldown_until_ts_ms,
            "last_exit_ts_ms": state.last_exit_ts_ms,
        }
    
    def reset(self) -> None:
        """Reset all cooldown state (for testing)."""
        self._state.clear()
