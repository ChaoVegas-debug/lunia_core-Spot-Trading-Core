"""
PHASE 13A — SHADOW RUNNER: Adapter

Translates execute_genome output → VirtualOrderSpec (immediate fill).

CRITICAL RULES:
- Fail-closed: missing prices → None (no order)
- No float conversion (prices remain strings)
- Deterministic mapping only
- ENTRY_BUY fills at best_ask
- ENTRY_SELL fills at best_bid
"""

from typing import Dict, Any, Optional, Tuple
from .models import StrategyIntent, VirtualOrderSpec, SignalType, ShadowErrorCode


class ShadowAdapter:
    """
    Adapter translating strategy intent → virtual order spec.
    
    Features:
    - Immediate fill price model (no slippage)
    - Fail-closed price validation
    - Deterministic signal normalization
    """
    
    def __init__(self):
        """Initialize adapter."""
        pass
    
    def normalize_intent(
        self,
        strategy_intent_dict: Dict[str, Any]
    ) -> Tuple[Optional[StrategyIntent], Optional[Dict[str, Any]]]:
        """
        Normalize execute_genome intent dict → StrategyIntent.
        
        Args:
            strategy_intent_dict: Intent dict from execute_genome
        
        Returns:
            (StrategyIntent | None, error_dict | None)
        """
        try:
            intent_type = strategy_intent_dict.get("intent_type", "NOOP")
            direction = strategy_intent_dict.get("direction")
            confidence = strategy_intent_dict.get("confidence", 0.0)
            
            # Map intent_type + direction → SignalType
            if intent_type == "NOOP" or intent_type == "noop":
                signal = "NOOP"
            elif intent_type == "ENTRY" or intent_type == "entry":
                if direction == "LONG" or direction == "long":
                    signal = "ENTRY_BUY"
                elif direction == "SHORT" or direction == "short":
                    signal = "ENTRY_SELL"
                else:
                    # Ambiguous direction
                    signal = "NOOP"
            elif intent_type == "EXIT" or intent_type == "exit":
                signal = "EXIT"
            else:
                signal = "NOOP"
            
            # Build metadata
            metadata = {
                "original_intent_type": intent_type,
                "original_direction": direction,
                "rationale": strategy_intent_dict.get("rationale", "")[:256],  # Cap
            }
            
            normalized = StrategyIntent(
                signal=signal,
                confidence=confidence,
                metadata=metadata
            )
            
            return normalized, None
        
        except Exception as e:
            error = {
                "code": ShadowErrorCode.INTENT_INVALID,
                "message": f"Intent normalization failed: {str(e)[:100]}",
            }
            return None, error
    
    def create_virtual_order(
        self,
        intent: StrategyIntent,
        snapshot: Dict[str, Any],
        symbol: str
    ) -> Tuple[Optional[VirtualOrderSpec], Optional[Dict[str, Any]]]:
        """
        Create virtual order from intent + snapshot.
        
        Args:
            intent: Normalized strategy intent
            snapshot: Market snapshot (Phase 12B)
           symbol: Trading symbol
        
        Returns:
            (VirtualOrderSpec | None, error_dict | None)
        """
        # NOOP → no order
        if intent.signal == "NOOP":
            return None, None
        
        # Extract prices
        best_bid = snapshot.get("top", {}).get("best_bid")
        best_ask = snapshot.get("top", {}).get("best_ask")
        
        # Validate prices (fail-closed)
        if not best_bid or not best_ask:
            error = {
                "code": ShadowErrorCode.PRICE_MISSING,
                "message": "Missing best_bid or best_ask in snapshot",
                "details": {"best_bid": best_bid, "best_ask": best_ask}
            }
            return None, error
        
        # Check for invalid price strings
        if best_bid in ["", "null", "None", "NaN"] or best_ask in ["", "null", "None", "NaN"]:
            error = {
                "code": ShadowErrorCode.PRICE_INVALID,
                "message": "Invalid price strings in snapshot",
                "details": {"best_bid": best_bid, "best_ask": best_ask}
            }
            return None, error
        
        # Map signal → order
        if intent.signal == "ENTRY_BUY":
            order = VirtualOrderSpec(
                symbol=symbol,
                side="BUY",
                action="ENTRY",
                fill_price=best_ask,  # BUY at ask
                price_type="IMMEDIATE_FILL",
                reason=f"ENTRY_BUY intent (confidence={intent.confidence:.2f})"
            )
            return order, None
        
        elif intent.signal == "ENTRY_SELL":
            order = VirtualOrderSpec(
                symbol=symbol,
                side="SELL",
                action="ENTRY",
                fill_price=best_bid,  # SELL at bid
                price_type="IMMEDIATE_FILL",
                reason=f"ENTRY_SELL intent (confidence={intent.confidence:.2f})"
            )
            return order, None
        
        elif intent.signal == "EXIT":
            # For EXIT, assume SELL at bid (fail-closed default)
            # Phase 13B will track position state
            order = VirtualOrderSpec(
                symbol=symbol,
                side="SELL",
                action="EXIT",
                fill_price=best_bid,
                price_type="IMMEDIATE_FILL",
                reason=f"EXIT intent (confidence={intent.confidence:.2f})"
            )
            return order, None
        
        # Unknown signal → no order
        return None, None
