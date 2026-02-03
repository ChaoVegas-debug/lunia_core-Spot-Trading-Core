"""
PHASE 9.3 — PAPER EXECUTOR

Paper execution engine with position tracking and cost reality.

STATE PERSISTENCE: Positions persist across ticks (in-memory MVP).
FAIL-CLOSED: All exceptions caught and audited, never crash runner.
"""

import traceback
from typing import Dict, Optional
from extensions.protocol.protocol import (
    StrategyIntent,
    GovernanceContext,
    MarketSnapshot,
    IntentType,
)
from extensions.sandbox.paper_types import (
    PaperFill,
    PaperPosition,
    TradeOutcome,
    create_trade_outcome,
)
from extensions.sandbox.cost_model import (
    compute_fee,
    compute_spread_cost,
    compute_slippage_cost,
    compute_latency_cost,
    compute_fill_price,
)
from extensions.sandbox.ttl_enforcer import is_ttl_expired
from extensions.sandbox.audit_store import AuditStore, create_audit_event
from extensions.sandbox.serialization import FLOAT_PRECISION


class PaperExecutionError(Exception):
    """Raised when paper execution fails."""
    pass


class PaperExecutor:
    """
    Paper execution engine with cost reality.
    
    STATEFUL:Position state persists across ticks.    
    FAIL-CLOSED: Exceptions caught, audited, and converted to safe outcomes.
    """
    
    def __init__(
        self,
        audit_store: AuditStore,
        fee_rate: float = 0.001,  # 0.1% default fee
        latency_ms: int = 50,  # 50ms default latency
    ):
        """
        Initialize paper executor.
        
        Args:
            audit_store: Audit store for event logging
            fee_rate: Trading fee rate (decimal, e.g., 0.001 = 0.1%)
            latency_ms: Simulated execution latency
        """
        self._audit_store = audit_store
        self._fee_rate = fee_rate
        self._latency_ms = latency_ms
        
        # Position tracking (symbol -> PaperPosition)
        self._positions: Dict[str, PaperPosition] = {}
    
    def on_tick(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
        market: MarketSnapshot,
        now_ts_ms: int,
    ) -> Optional[TradeOutcome]:
        """
        Execute paper tick: check TTL, process intent, apply costs.
        
        GUARANTEE: Never crashes. All errors audited and handled safely.
        
        Args:
            intent: Validated strategy intent
            governance: Governance context
            market: Market snapshot
            now_ts_ms: Current timestamp
            
        Returns:
            TradeOutcome if position closed, None otherwise
        """
        try:
            # Audit execution start
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="paper_exec_start",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={
                    "symbol": market.symbol,
                    "intent_type": intent.intent_type.value,
                    "has_position": market.symbol in self._positions,
                },
                intent_id=intent.intent_id,
            )
            
            # Step 1: Check TTL FIRST (forced exit takes precedence)
            outcome = self._check_ttl_and_force_exit(
                market=market,
                governance=governance,
                intent=intent,
                now_ts_ms=now_ts_ms,
            )
            if outcome:
                return outcome
            
            # Step 2: Process intent
            if intent.intent_type == IntentType.ENTRY:
                outcome = self._process_entry(
                    intent=intent,
                    governance=governance,
                    market=market,
                    now_ts_ms=now_ts_ms,
                )
            elif intent.intent_type == IntentType.EXIT:
                outcome = self._process_exit(
                    intent=intent,
                    governance=governance,
                    market=market,
                    now_ts_ms=now_ts_ms,
                )
            else:
                # NOOP, ADJUST, etc.: no position changes
                outcome = None
            
            # Audit execution end
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="paper_exec_end",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={
                    "outcome_created": outcome is not None,
                    "outcome_id": outcome.outcome_id if outcome else None,
                },
                intent_id=intent.intent_id,
            )
            
            return outcome
        
        except Exception as e:
            # Fail-closed: audit error and return None
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="paper_exec_error",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={
                    "error": error_msg,
                    "symbol": market.symbol,
                },
                severity="critical",
            )
            
            return None
    
    def _check_ttl_and_force_exit(
        self,
        market: MarketSnapshot,
        governance: GovernanceContext,
        intent: StrategyIntent,
        now_ts_ms: int,
    ) -> Optional[TradeOutcome]:
        """Check TTL and force exit if expired."""
        symbol = market.symbol
        
        if symbol not in self._positions:
            return None
        
        position = self._positions[symbol]
        
        # Check TTL
        if position.time_limit_ms and is_ttl_expired(
            position.open_ts_ms,
            now_ts_ms,
            position.time_limit_ms,
        ):
            # Force exit
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="ttl_forced_exit",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={
                    "symbol": symbol,
                    "open_ts_ms": position.open_ts_ms,
                    "time_limit_ms": position.time_limit_ms,
                    "elapsed_ms": now_ts_ms - position.open_ts_ms,
                },
                strategy_id=position.strategy_id,
            )
            
            # Create forced exit outcome
            outcome = self._execute_exit(
                position=position,
                market=market,
                governance=governance,
                intent=intent,
                now_ts_ms=now_ts_ms,
                exit_reason="TTL",
            )
            
            return outcome
        
        return None
    
    def _process_entry(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
        market: MarketSnapshot,
        now_ts_ms: int,
    ) -> Optional[TradeOutcome]:
        """Process ENTRY intent."""
        symbol = intent.symbol or market.symbol
        
        # If position already exists, ignore (deterministic: no replace/scale)
        if symbol in self._positions:
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="entry_ignored_position_exists",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={"symbol": symbol},
                intent_id=intent.intent_id,
            )
            return None
        
        # Determine quantity
        if intent.size_base:
            qty = intent.size_base
        elif intent.size_quote:
            qty = intent.size_quote / market.mid
        else:
            raise PaperExecutionError("ENTRY intent missing size")
        
        # Compute costs
        side = "buy" if intent.direction.value == "long" else "sell"
        
        notional = market.mid * qty
        fee = compute_fee(notional, self._fee_rate)
        spread_cost = compute_spread_cost(side, market.bid, market.ask, qty)
        slippage_cost = compute_slippage_cost(market.mid, qty, market.volatility_state)
        latency_cost = compute_latency_cost(market.mid, qty, self._latency_ms)
        
        # Compute fill price
        fill_price = compute_fill_price(
            side=side,
            bid=market.bid,
            ask=market.ask,
            mid=market.mid,
            qty=qty,
            volatility_state=market.volatility_state,
            latency_ms=self._latency_ms,
        )
        
        # Create fill
        fill = PaperFill(
            side=side,
            symbol=symbol,
            qty=qty,
            price=fill_price,
            ts_ms=now_ts_ms,
            fee=fee,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            latency_cost=latency_cost,
            intent_id=intent.intent_id,
            correlation_id=governance.correlation_id,
            run_id=governance.run_id,
        )
        
        # Create position
        position = PaperPosition(
            symbol=symbol,
            side=intent.direction.value,
            qty=qty,
            avg_entry_price=fill_price,
            open_ts_ms=now_ts_ms,
            entry_intent_id=intent.intent_id,
            run_id=governance.run_id,
            correlation_id=governance.correlation_id,
            strategy_id=intent.strategy_id,
            time_limit_ms=intent.exit_plan.time_limit_ms if intent.exit_plan else None,
        )
        
        # Store position
        self._positions[symbol] = position
        
        # Audit fill
        self._audit_event(
            ts_ms=now_ts_ms,
            event_type="fill_created_entry",
            correlation_id=governance.correlation_id,
            run_id=governance.run_id,
            payload={
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "fill_price": fill_price,
                "fee": fee,
                "spread_cost": spread_cost,
                "slippage_cost": slippage_cost,
                "latency_cost": latency_cost,
            },
            intent_id=intent.intent_id,
            strategy_id=intent.strategy_id,
        )
        
        return None
    
    def _process_exit(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
        market: MarketSnapshot,
        now_ts_ms: int,
    ) -> Optional[TradeOutcome]:
        """Process EXIT intent."""
        symbol = intent.symbol or market.symbol
        
        # Check if position exists
        if symbol not in self._positions:
            self._audit_event(
                ts_ms=now_ts_ms,
                event_type="exit_ignored_no_position",
                correlation_id=governance.correlation_id,
                run_id=governance.run_id,
                payload={"symbol": symbol},
                intent_id=intent.intent_id,
            )
            return None
        
        position = self._positions[symbol]
        
        # Execute exit
        outcome = self._execute_exit(
            position=position,
            market=market,
            governance=governance,
            intent=intent,
            now_ts_ms=now_ts_ms,
            exit_reason="SIGNAL",
        )
        
        return outcome
    
    def _execute_exit(
        self,
        position: PaperPosition,
        market: MarketSnapshot,
        governance: GovernanceContext,
        intent: StrategyIntent,
        now_ts_ms: int,
        exit_reason: str,
    ) -> TradeOutcome:
        """Execute exit and create outcome."""
        symbol = position.symbol
        qty = position.qty
        
        # Determine exit side (opposite of entry)
        if position.side == "long":
            exit_side = "sell"
        else:
            exit_side = "buy"
        
        # Compute costs for exit
        notional = market.mid * qty
        fee = compute_fee(notional, self._fee_rate)
        spread_cost = compute_spread_cost(exit_side, market.bid, market.ask, qty)
        slippage_cost = compute_slippage_cost(market.mid, qty, market.volatility_state)
        latency_cost = compute_latency_cost(market.mid, qty, self._latency_ms)
        
        # Compute fill price
        fill_price = compute_fill_price(
            side=exit_side,
            bid=market.bid,
            ask=market.ask,
            mid=market.mid,
            qty=qty,
            volatility_state=market.volatility_state,
            latency_ms=self._latency_ms,
        )
        
        # Audit exit fill
        self._audit_event(
            ts_ms=now_ts_ms,
            event_type="fill_created_exit",
            correlation_id=governance.correlation_id,
            run_id=governance.run_id,
            payload={
                "symbol": symbol,
                "side": exit_side,
                "qty": qty,
                "fill_price": fill_price,
                "fee": fee,
                "spread_cost": spread_cost,
                "slippage_cost": slippage_cost,
                "latency_cost": latency_cost,
                "exit_reason": exit_reason,
            },
            intent_id=intent.intent_id,
            strategy_id=position.strategy_id,
        )
        
        # Create outcome
        outcome = create_trade_outcome(
            symbol=symbol,
            side=position.side,
            qty=qty,
            entry_ts_ms=position.open_ts_ms,
            exit_ts_ms=now_ts_ms,
            entry_price=position.avg_entry_price,
            exit_price=fill_price,
            fee_total=fee,  # Simplified: only exit fee (could add entry fee if stored)
            spread_total=spread_cost,
            slippage_total=slippage_cost,
            latency_total=latency_cost,
            exit_reason=exit_reason,
            entry_intent_id=position.entry_intent_id,
            exit_intent_id=intent.intent_id,
            entry_run_id=position.run_id,
            exit_run_id=governance.run_id,
            entry_correlation_id=position.correlation_id,
            exit_correlation_id=governance.correlation_id,
            strategy_id=position.strategy_id,
        )
        
        # Remove position
        del self._positions[symbol]
        
        # Audit outcome
        self._audit_event(
            ts_ms=now_ts_ms,
            event_type="outcome_created",
            correlation_id=governance.correlation_id,
            run_id=governance.run_id,
            payload={
                "outcome_id": outcome.outcome_id,
                "symbol": symbol,
                "net_pnl": outcome.net_pnl,
                "gross_pnl": outcome.gross_pnl,
                "exit_reason": exit_reason,
            },
            intent_id=intent.intent_id,
            strategy_id=position.strategy_id,
        )
        
        return outcome
    
    def _audit_event(self, **kwargs):
        """Helper to create and append audit event."""
        event = create_audit_event(**kwargs)
        self._audit_store.append(event)
    
    def get_positions(self) -> Dict[str, PaperPosition]:
        """Get current positions (for debugging/testing)."""
        return dict(self._positions)
    
    def reset(self) -> None:
        """Reset all positions (for testing)."""
        self._positions.clear()
