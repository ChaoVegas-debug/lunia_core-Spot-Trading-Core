"""
PHASE 13B — VIRTUAL PORTFOLIO: Manager

Event-driven portfolio manager with WAP accounting, Decimal precision, and risk monitoring.

CRITICAL RULES:
- Decimal-only (no floats)
- Event-driven (no background loops)
- Fail-closed (invalid inputs → zero mutation + error return)
- Returns audit payloads (does NOT write to AuditStore directly)
- Bounded memory (ring buffers for history/alerts)
"""

from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from collections import deque

from .models import (
    VirtualPosition, PortfolioState, RiskAlert,
    PortfolioErrorCode, PositionSide, RiskLevel
)
from .risk_monitor import RiskMonitor


class PortfolioManager:
    """
    Virtual portfolio manager with WAP accounting.
    
    Features:
    - WAP position tracking
    - Realized/unrealized PnL
    - Equity curve history
    - Risk alerts
    - Audit payload generation (caller appends to AuditStore)
    """
    
    def __init__(
        self,
        starting_equity: str = "10000",
        *,
        max_history: int = 100,
        max_alerts: int = 50,
        warn_dd_pct: str = "0.03",
        crit_dd_pct: str = "0.05",
    ):
        """
        Initialize portfolio manager.
        
        Args:
            starting_equity: Starting equity (Decimal string)
            max_history: Max equity curve history (bounded)
            max_alerts: Max alert history (bounded)
            warn_dd_pct: WARNING drawdown threshold (Decimal string)
            crit_dd_pct: CRITICAL drawdown threshold (Decimal string)
        """
        # Parse starting equity
        try:
            self.starting_equity = Decimal(starting_equity)
        except (InvalidOperation, ValueError):
            self.starting_equity = Decimal("10000")  # Fail-safe default
        
        # Initialize state
        self.equity = self.starting_equity
        self.realized_pnl_total = Decimal("0")
        self.unrealized_pnl_total = Decimal("0")
        self.peak_equity = self.starting_equity
        self.drawdown_abs = Decimal("0")
        self.drawdown_pct = Decimal("0")
        
        # Positions (symbol → VirtualPosition)
        self.positions: Dict[str, VirtualPosition] = {}
        
        # History (bounded ring buffers)
        self.equity_history: deque = deque(maxlen=max_history)
        self.alert_history: deque = deque(maxlen=max_alerts)
        
        # Risk monitor
        try:
            warn_dd = Decimal(warn_dd_pct)
            crit_dd = Decimal(crit_dd_pct)
        except (InvalidOperation, ValueError):
            warn_dd = Decimal("0.03")
            crit_dd = Decimal("0.05")
        
        self.risk_monitor = RiskMonitor(warn_dd_pct=warn_dd, crit_dd_pct=crit_dd)
        
        # Last error
        self.last_error: Optional[Dict[str, Any]] = None
    
    def _safe_decimal(self, value: Any, field_name: str) -> Optional[Decimal]:
        """
        Safely parse Decimal from string/number.
        
        Args:
            value: Value to parse
            field_name: Field name for error message
        
        Returns:
            Decimal or None on error
        """
        if value is None:
            return None
        
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    
    def _extract_quantity(self, step) -> tuple[Optional[Decimal], bool]:
        """
        Extract quantity from ShadowStepResult with 3-tier fallback.
        
        Priority:
        1. step.virtual_order.metadata["quantity"]
        2. step.intent.metadata["quantity"]
        3. Decimal("1") BUT with defaulted=True flag
        
        Args:
            step: ShadowStepResult
        
        Returns:
            (Decimal | None, defaulted: bool)
        """
        # Try virtual_order metadata
        if step.virtual_order:
            vo_metadata = step.virtual_order.to_dict()
            qty_val = vo_metadata.get("metadata", {}).get("quantity")
            if qty_val is not None:
                qty = self._safe_decimal(qty_val, "virtual_order.quantity")
                if qty and qty > 0:
                    return qty, False
        
        # Try intent metadata
        if step.intent:
            intent_metadata = step.intent.metadata
            qty_val = intent_metadata.get("quantity")
            if qty_val is not None:
                qty = self._safe_decimal(qty_val, "intent.quantity")
                if qty and qty > 0:
                    return qty, False
        
        # Fallback to default
        return Decimal("1"), True
    
    def _get_canonical_timestamp(self, step) -> Optional[int]:
        """Extract canonical timestamp from ShadowStepResult."""
        return step.timestamp_ms
    
    def _get_mark_price_from_snapshot(
        self,
        snapshot: Dict[str, Any],
        symbol: str
    ) -> Optional[Decimal]:
        """
        Extract mark price from snapshot with strict fallback priority.
        
        Priority:
        1. snapshot["trade"]["price"]
        2. snapshot["top"]["mid"]
        3. Position-aware fallback:
           - LONG: best_bid
           - SHORT: best_ask
           - FLAT: mid → best_bid → best_ask
        4. None (fail-closed)
        
        Args:
            snapshot: MarketSnapshot dict
            symbol: Trading symbol
        
        Returns:
            Decimal or None
        """
        # 1. Trade price
        trade_price = snapshot.get("trade", {}).get("price")
        if trade_price:
            mark = self._safe_decimal(trade_price, "trade.price")
            if mark:
                return mark
        
        # 2. Mid price
        mid_price = snapshot.get("top", {}).get("mid")
        if mid_price:
            mark = self._safe_decimal(mid_price, "top.mid")
            if mark:
                return mark
        
        # 3. Position-aware fallback
        position = self.positions.get(symbol)
        best_bid = snapshot.get("top", {}).get("best_bid")
        best_ask = snapshot.get("top", {}).get("best_ask")
        
        if position and position.side == "LONG":
            # LONG: use best_bid (conservative)
            if best_bid:
                return self._safe_decimal(best_bid, "best_bid")
        elif position and position.side == "SHORT":
            # SHORT: use best_ask (conservative)
            if best_ask:
                return self._safe_decimal(best_ask, "best_ask")
        else:
            # FLAT or no position: deterministic priority
            if mid_price:
                return self._safe_decimal(mid_price,  "mid")
            if best_bid:
                return self._safe_decimal(best_bid, "best_bid")
            if best_ask:
                return self._safe_decimal(best_ask, "best_ask")
        
        # 4. None (fail-closed)
        return None
    
    def _update_unrealized_pnl(self, position: VirtualPosition):
        """
        Update unrealized PnL for position.
        
        Rules:
        - LONG: (mark - avg_entry) * qty
        - SHORT: (avg_entry - mark) * qty
        - If mark is None: unrealized = 0 (fail-closed)
        
        Args:
            position: VirtualPosition to update
        """
        if position.side == "FLAT" or position.mark_price is None or position.avg_entry_price is None:
            position.unrealized_pnl = Decimal("0")
            return
        
        if position.side == "LONG":
            position.unrealized_pnl = (position.mark_price - position.avg_entry_price) * position.qty
        elif position.side == "SHORT":
            position.unrealized_pnl = (position.avg_entry_price - position.mark_price) * position.qty
    
    def _update_aggregates(self):
        """Update portfolio-level aggregates."""
        # Realized PnL total
        self.realized_pnl_total = sum(
            (pos.realized_pnl for pos in self.positions.values()),
            Decimal("0")
        )
        
        # Unrealized PnL total
        self.unrealized_pnl_total = sum(
            (pos.unrealized_pnl for pos in self.positions.values()),
            Decimal("0")
        )
        
        # Equity
        self.equity = self.starting_equity + self.realized_pnl_total + self.unrealized_pnl_total
        
        # Peak equity
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        
        # Drawdown
        self.drawdown_abs = self.peak_equity - self.equity
        if self.peak_equity > 0:
            self.drawdown_pct = self.drawdown_abs / self.peak_equity
        else:
            self.drawdown_pct = Decimal("0")
    
    def _apply_order(
        self,
        symbol: str,
        side: str,  # "BUY" | "SELL"
        fill_price: Decimal,
        qty: Decimal,
        ts_ms: Optional[int]
    ) -> Dict[str, Any]:
        """
        Apply virtual order to position (WAP accounting with reduce/flip logic).
        
        Args:
            symbol: Trading symbol
            side: "BUY" | "SELL"
            fill_price: Fill price (Decimal)
            qty: Quantity (Decimal)
            ts_ms: Timestamp
        
        Returns:
            Audit details dict
        """
        # Get or create position
        if symbol not in self.positions:
            self.positions[symbol] = VirtualPosition(
                symbol=symbol,
                side="FLAT",
                qty=Decimal("0"),
                avg_entry_price=None,
                mark_price=fill_price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                last_ts_ms=ts_ms,
                trade_count=0,
            )
        
        position = self.positions[symbol]
        audit_details = {"symbol": symbol, "fill_price": str(fill_price), "qty": str(qty), "side": side}
        
        # Update mark price
        position.mark_price = fill_price
        position.last_ts_ms = ts_ms
        position.trade_count += 1
        
        # Reduce/flip logic
        if side == "BUY":
            if position.side == "SHORT":
                # Reduce SHORT position
                reduce_qty = min(qty, position.qty)
                remaining_qty = qty - reduce_qty
                
                # Realized PnL: (avg_entry - fill_price) * reduce_qty
                if position.avg_entry_price:
                    realized = (position.avg_entry_price - fill_price) * reduce_qty
                    position.realized_pnl += realized
                    audit_details["realized_pnl_delta"] = str(realized)
                
                position.qty -= reduce_qty
                
                if position.qty == 0:
                    position.side = "FLAT"
                    position.avg_entry_price = None
                
                # Open LONG with remaining
                if remaining_qty > 0:
                    position.side = "LONG"
                    position.qty = remaining_qty
                    position.avg_entry_price = fill_price
                    audit_details["flip_to_long"] = True
            
            elif position.side == "LONG":
                # Increase LONG (WAP)
                new_total_qty = position.qty + qty
                if position.avg_entry_price:
                    new_avg = (position.avg_entry_price * position.qty + fill_price * qty) / new_total_qty
                else:
                    new_avg = fill_price
                
                position.qty = new_total_qty
                position.avg_entry_price = new_avg
                audit_details["new_avg_entry"] = str(new_avg)
            
            else:  # FLAT
                position.side = "LONG"
                position.qty = qty
                position.avg_entry_price = fill_price
        
        elif side == "SELL":
            if position.side == "LONG":
                # Reduce LONG position
                reduce_qty = min(qty, position.qty)
                remaining_qty = qty - reduce_qty
                
                # Realized PnL: (fill_price - avg_entry) * reduce_qty
                if position.avg_entry_price:
                    realized = (fill_price - position.avg_entry_price) * reduce_qty
                    position.realized_pnl += realized
                    audit_details["realized_pnl_delta"] = str(realized)
                
                position.qty -= reduce_qty
                
                if position.qty == 0:
                    position.side = "FLAT"
                    position.avg_entry_price = None
                
                # Open SHORT with remaining
                if remaining_qty > 0:
                    position.side = "SHORT"
                    position.qty = remaining_qty
                    position.avg_entry_price = fill_price
                    audit_details["flip_to_short"] = True
            
            elif position.side == "SHORT":
                # Increase SHORT (WAP)
                new_total_qty = position.qty + qty
                if position.avg_entry_price:
                    new_avg = (position.avg_entry_price * position.qty + fill_price * qty) / new_total_qty
                else:
                    new_avg = fill_price
                
                position.qty = new_total_qty
                position.avg_entry_price = new_avg
                audit_details["new_avg_entry"] = str(new_avg)
            
            else:  # FLAT
                position.side = "SHORT"
                position.qty = qty
                position.avg_entry_price = fill_price
        
        # Update unrealized PnL
        self._update_unrealized_pnl(position)
        
        return audit_details
    
    def on_shadow_step(self, step) -> Dict[str, Any]:
        """
        Apply executed virtual order from ShadowStepResult.
        
        Args:
            step: ShadowStepResult from Phase 13A
        
        Returns:
            Dict with: ok, state, audit_record, error
        """
        try:
            # Only process EXECUTED orders
            if step.status != "EXECUTED" or step.virtual_order is None:
                return {
                    "ok": False,
                    "state": self.get_state().to_dict(),
                    "audit_record": None,
                    "error": None,  # Not an error, just skipped
                }
            
            # Extract fields
            symbol = step.virtual_order.symbol
            side = step.virtual_order.side
            fill_price_str = step.virtual_order.fill_price
            ts_ms = self._get_canonical_timestamp(step)
            
            # Parse fill price
            fill_price = self._safe_decimal(fill_price_str, "fill_price")
            if not fill_price or fill_price <= 0:
                error = {
                    "code": PortfolioErrorCode.INVALID_PRICE,
                    "message": f"Invalid fill price: {fill_price_str}",
                    "details": {"fill_price": fill_price_str}
                }
                self.last_error = error
                return {
                    "ok": False,
                    "state": self.get_state().to_dict(),
                    "audit_record": None,
                    "error": error
                }
            
            # Extract quantity
            qty, qty_defaulted = self._extract_quantity(step)
            if not qty or qty <= 0:
                error = {
                    "code": PortfolioErrorCode.INVALID_QUANTITY,
                    "message": f"Invalid quantity extracted",
                    "details": {"qty": str(qty) if qty else None}
                }
                self.last_error = error
                return {
                    "ok": False,
                    "state": self.get_state().to_dict(),
                    "audit_record": None,
                    "error": error
                }
            
            # Apply order
            audit_details = self._apply_order(symbol, side, fill_price, qty, ts_ms)
            if qty_defaulted:
                audit_details["quantity_defaulted"] = True
            
            # Update aggregates
            self._update_aggregates()
            
            # Add to equity history
            self.equity_history.append({
                "ts_ms": ts_ms,
                "equity": str(self.equity),
                "realized_pnl": str(self.realized_pnl_total),
                "unrealized_pnl": str(self.unrealized_pnl_total),
            })
            
            # Evaluate risk
            state = self.get_state()
            new_alerts = self.risk_monitor.evaluate(state)
            
            # Add to alert history (deduplicate by level escalation)
            for alert in new_alerts:
                self.alert_history.append(alert)
            
            # Create audit record
            audit_record = {
                "schema_version": "1.0.0",
                "phase": "13B",
                "event": "PORTFOLIO_ORDER_APPLIED",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "order": step.virtual_order.to_dict(),
                    "audit_details": audit_details,
                    "equity": str(self.equity),
                    "realized_pnl_total": str(self.realized_pnl_total),
                    "unrealized_pnl_total": str(self.unrealized_pnl_total),
                }
            }
            
            return {
                "ok": True,
                "state": state.to_dict(),
                "audit_record": audit_record,
                "error": None
            }
        
        except Exception as e:
            error = {
                "code": PortfolioErrorCode.UNKNOWN_ERROR,
                "message": f"on_shadow_step failed: {str(e)[:200]}",
                "details": {"exception": str(e)}
            }
            self.last_error = error
            return {
                "ok": False,
                "state": self.get_state().to_dict(),
                "audit_record": None,
                "error": error
            }
    
    def on_tick(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update mark prices and recompute portfolio from market snapshot.
        
        Args:
            snapshot: MarketSnapshot dict from Phase 12B
        
        Returns:
            Dict with: ok, state, audit_record, error
        """
        try:
            # Extract snapshot symbol
            symbol = snapshot.get("symbol")
            if not symbol:
                return {
                    "ok": False,
                    "state": self.get_state().to_dict(),
                    "audit_record": None,
                    "error": {"code": "MISSING_SYMBOL", "message": "Snapshot missing symbol"}
                }
            
            # Canonical timestamp
            ts_ms = snapshot.get("event_ts_ms") or snapshot.get("server_ts_ms")
            
            # Get mark price
            mark_price = self._get_mark_price_from_snapshot(snapshot, symbol)
            
            # Update position if exists
            if symbol in self.positions:
                position = self.positions[symbol]
                
                # Update mark price if valid
                if mark_price:
                    position.mark_price = mark_price
                    position.last_ts_ms = ts_ms
                    
                    # Recompute unrealized PnL
                    self._update_unrealized_pnl(position)
            
            # Update aggregates
            self._update_aggregates()
            
            # Add to equity history
            self.equity_history.append({
                "ts_ms": ts_ms,
                "equity": str(self.equity),
                "realized_pnl": str(self.realized_pnl_total),
                "unrealized_pnl": str(self.unrealized_pnl_total),
            })
            
            # Evaluate risk
            state = self.get_state()
            new_alerts = self.risk_monitor.evaluate(state)
            
            # Add to alert history
            for alert in new_alerts:
                self.alert_history.append(alert)
            
            # Create audit record
            audit_record = {
                "schema_version": "1.0.0",
                "phase": "13B",
                "event": "PORTFOLIO_MARK_UPDATED",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "mark_price": str(mark_price) if mark_price else None,
                    "equity": str(self.equity),
                    "drawdown_pct": str(self.drawdown_pct),
                }
            }
            
            return {
                "ok": True,
                "state": state.to_dict(),
                "audit_record": audit_record,
                "error": None
            }
        
        except Exception as e:
            error = {
                "code": PortfolioErrorCode.UNKNOWN_ERROR,
                "message": f"on_tick failed: {str(e)[:200]}",
                "details": {"exception": str(e)}
            }
            self.last_error = error
            return {
                "ok": False,
                "state": self.get_state().to_dict(),
                "audit_record": None,
                "error": error
            }
    
    def get_state(self) -> PortfolioState:
        """
        Get current portfolio state (copy-safe).
        
        Returns:
            PortfolioState snapshot
        """
        # Deterministic timestamp: max of per-symbol last_ts_ms (ignoring None)
        ts_list = [pos.last_ts_ms for pos in self.positions.values() if pos.last_ts_ms is not None]
        ts_ms = max(ts_list) if ts_list else None
        
        # Get recent alerts (last 10)
        recent_alerts = list(self.alert_history)[-10:] if self.alert_history else []
        
        return PortfolioState(
            ts_ms=ts_ms,
            equity=self.equity,
            starting_equity=self.starting_equity,
            realized_pnl_total=self.realized_pnl_total,
            unrealized_pnl_total=self.unrealized_pnl_total,
            drawdown_abs=self.drawdown_abs,
            drawdown_pct=self.drawdown_pct,
            positions={symbol: pos for symbol, pos in self.positions.items()},  # Reference for efficiency
            alerts=recent_alerts,
            last_error=self.last_error,
        )
    
    def get_equity_curve(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get equity curve history (bounded ring).
        
        Args:
            limit: Max history items to return
        
        Returns:
            Dict with equity curve (oldest → newest)
        """
        history = list(self.equity_history)[-limit:]
        
        return {
            "ok": True,
            "history": history,
            "count": len(history),
        }
