"""
PHASE 9.2 — CONTEXT FACTORY

Fail-closed conversion of raw input dicts to protocol objects.

SPEC IMPROVEMENT:
- No permissive fallback parsing for unknown enum strings
- Unknown MarketRegime/VolatilityState => ContextFactoryError
- Injectable clock for deterministic testing

GUARANTEES:
- Required fields enforced
- Type conversions validated
- Enum strings validated strictly
- Timestamps validated
- Correlation IDs generated if missing
"""

import time
import uuid
from typing import Dict, Any, Callable, Optional
from extensions.protocol.protocol import (
    GovernanceContext,
    MarketSnapshot,
    ShadowPortfolio,
    ShadowPosition,
    MarketRegime,
    VolatilityState,
    RiskState,
    TradeDirection,
    TimestampMs,
)
from extensions.sandbox.reject_codes import RejectCode


class ContextFactoryError(Exception):
    """Raised when context creation fails."""
    
    def __init__(self, message: str, reject_code: RejectCode):
        super().__init__(message)
        self.reject_code = reject_code


class ContextFactory:
    """
    Fail-closed factory for creating protocol objects from raw dicts.
    
    SPEC IMPROVEMENT: Injectable clock for deterministic testing.
    """
    
    def __init__(self, clock: Optional[Callable[[], int]] = None):
        """
        Initialize context factory.
        
        Args:
            clock: Optional clock function returning UTC epoch milliseconds.
                   Defaults to real system time.
        """
        self._clock = clock or (lambda: int(time.time() * 1000))
    
    def create_governance_context(self, raw: Dict[str, Any]) -> GovernanceContext:
        """
        Create GovernanceContext from raw dict.
        
        FAIL-CLOSED: Any missing/invalid field raises ContextFactoryError.
        
        Args:
            raw: Raw governance data
            
        Returns:
            Validated GovernanceContext
            
        Raises:
            ContextFactoryError: If validation fails
        """
        try:
            # Generate correlation_id if missing
            correlation_id = raw.get("correlation_id")
            if not correlation_id:
                correlation_id = f"corr_{uuid.uuid4().hex[:12]}"
            
            # Generate run_id if missing
            run_id = raw.get("run_id")
            if not run_id:
                run_id = f"run_{uuid.uuid4().hex[:12]}"
            
            # Timestamp (use clock)
            ts_ms = raw.get("ts_ms")
            if ts_ms is None:
                ts_ms = self._clock()
            
            # Validate timestamp
            if not isinstance(ts_ms, int) or ts_ms <= 0:
                raise ContextFactoryError(
                    f"Invalid timestamp: {ts_ms}",
                    RejectCode.CONTEXT_FACTORY_TIMESTAMP_INVALID
                )
            
            # Parse risk_state enum (SPEC IMPROVEMENT: no fallback)
            risk_state_str = self._require_field(raw, "risk_state", "governance")
            try:
                risk_state = RiskState(risk_state_str)
            except ValueError:
                raise ContextFactoryError(
                    f"Unknown RiskState: {risk_state_str}",
                    RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN
                )
            
            return GovernanceContext(
                ts_ms=ts_ms,
                run_id=run_id,
                correlation_id=correlation_id,
                is_live=self._require_bool(raw, "is_live"),
                is_reduce_only=raw.get("is_reduce_only", False),
                allow_new_entries=raw.get("allow_new_entries", True),
                max_position_size=self._require_float(raw, "max_position_size"),
                max_leverage=self._require_float(raw, "max_leverage"),
                risk_state=risk_state,
                emergency_override_active=raw.get("emergency_override_active", False),
            )
        except ContextFactoryError:
            raise
        except (KeyError, TypeError, ValueError) as e:
            raise ContextFactoryError(
                f"Failed to create GovernanceContext: {e}",
                RejectCode.CONTEXT_FACTORY_TYPE_ERROR
            ) from e
    
    def create_market_snapshot(self, raw: Dict[str, Any]) -> MarketSnapshot:
        """
        Create MarketSnapshot from raw dict.
        
        FAIL-CLOSED: Any missing/invalid field raises ContextFactoryError.
        
        Args:
            raw: Raw market data
            
        Returns:
            Validated MarketSnapshot
            
        Raises:
            ContextFactoryError: If validation fails
        """
        try:
            # Timestamp
            ts_ms = raw.get("ts_ms", self._clock())
            if not isinstance(ts_ms, int) or ts_ms <= 0:
                raise ContextFactoryError(
                    f"Invalid timestamp: {ts_ms}",
                    RejectCode.CONTEXT_FACTORY_TIMESTAMP_INVALID
                )
            
            # Parse enums (SPEC IMPROVEMENT: no fallback)
            volatility_state_str = self._require_field(raw, "volatility_state", "market")
            market_regime_str = self._require_field(raw, "market_regime", "market")
            
            try:
                volatility_state = VolatilityState(volatility_state_str)
            except ValueError:
                raise ContextFactoryError(
                    f"Unknown VolatilityState: {volatility_state_str}",
                    RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN
                )
            
            try:
                market_regime = MarketRegime(market_regime_str)
            except ValueError:
                raise ContextFactoryError(
                    f"Unknown MarketRegime: {market_regime_str}",
                    RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN
                )
            
            return MarketSnapshot(
                symbol=self._require_field(raw, "symbol", "market"),
                ts_ms=ts_ms,
                bid=self._require_float(raw, "bid"),
                ask=self._require_float(raw, "ask"),
                mid=self._require_float(raw, "mid"),
                volume_24h=self._require_float(raw, "volume_24h"),
                volatility_state=volatility_state,
                market_regime=market_regime,
                atr_14=self._require_float(raw, "atr_14"),
                spread_pct=self._require_float(raw, "spread_pct"),
            )
        except ContextFactoryError:
            raise
        except (KeyError, TypeError, ValueError) as e:
            raise ContextFactoryError(
                f"Failed to create MarketSnapshot: {e}",
                RejectCode.CONTEXT_FACTORY_TYPE_ERROR
            ) from e
    
    def create_shadow_portfolio(self, raw: Dict[str, Any]) -> ShadowPortfolio:
        """
        Create ShadowPortfolio from raw dict.
        
        MVP: Pass-through with minimal validation (no money math in Phase 9.2).
        
        Args:
            raw: Raw portfolio data
            
        Returns:
            Validated ShadowPortfolio
            
        Raises:
            ContextFactoryError: If validation fails
        """
        try:
            # Parse positions if provided
            positions = {}
            raw_positions = raw.get("positions", {})
            for symbol, pos_data in raw_positions.items():
                # Parse direction enum
                direction_str = pos_data.get("direction", "neutral")
                try:
                    direction = TradeDirection(direction_str)
                except ValueError:
                    raise ContextFactoryError(
                        f"Unknown TradeDirection: {direction_str}",
                        RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN
                    )
                
                positions[symbol] = ShadowPosition(
                    symbol=symbol,
                    direction=direction,
                    size=float(pos_data.get("size", 0.0)),
                    entry_price=float(pos_data.get("entry_price", 0.0)),
                    current_price=float(pos_data.get("current_price", 0.0)),
                    unrealized_pnl=float(pos_data.get("unrealized_pnl", 0.0)),
                    unrealized_pnl_pct=float(pos_data.get("unrealized_pnl_pct", 0.0)),
                    entry_ts_ms=int(pos_data.get("entry_ts_ms", self._clock())),
                    position_id=pos_data.get("position_id", f"pos_{uuid.uuid4().hex[:8]}"),
                )
            
            return ShadowPortfolio(
                base_currency=raw.get("base_currency", "USD"),
                equity=float(raw.get("equity", 0.0)),
                available_balance=float(raw.get("available_balance", 0.0)),
                margin_used=float(raw.get("margin_used", 0.0)),
                margin_available=float(raw.get("margin_available", 0.0)),
                positions=positions,
                daily_pnl=float(raw.get("daily_pnl", 0.0)),
                total_pnl=float(raw.get("total_pnl", 0.0)),
                peak_equity=float(raw.get("peak_equity", 0.0)),
                drawdown_pct=float(raw.get("drawdown_pct", 0.0)),
            )
        except ContextFactoryError:
            raise
        except (KeyError, TypeError, ValueError) as e:
            raise ContextFactoryError(
                f"Failed to create ShadowPortfolio: {e}",
                RejectCode.CONTEXT_FACTORY_TYPE_ERROR
            ) from e
    
    # Helper methods
    
    def _require_field(self, data: Dict[str, Any], field: str, context: str) -> Any:
        """Require field exists in data."""
        if field not in data:
            raise ContextFactoryError(
                f"Missing required field '{field}' in {context} data",
                RejectCode.CONTEXT_FACTORY_MISSING_FIELD
            )
        return data[field]
    
    def _require_float(self, data: Dict[str, Any], field: str) -> float:
        """Require field exists and is convertible to float."""
        value = data.get(field)
        if value is None:
            raise ContextFactoryError(
                f"Missing required field '{field}'",
                RejectCode.CONTEXT_FACTORY_MISSING_FIELD
            )
        try:
            return float(value)
        except (TypeError, ValueError) as e:
            raise ContextFactoryError(
                f"Field '{field}' must be numeric, got {type(value).__name__}",
                RejectCode.CONTEXT_FACTORY_TYPE_ERROR
            ) from e
    
    def _require_bool(self, data: Dict[str, Any], field: str) -> bool:
        """Require field exists and is boolean."""
        value = data.get(field)
        if value is None:
            raise ContextFactoryError(
                f"Missing required field '{field}'",
                RejectCode.CONTEXT_FACTORY_MISSING_FIELD
            )
        if not isinstance(value, bool):
            raise ContextFactoryError(
                f"Field '{field}' must be boolean, got {type(value).__name__}",
                RejectCode.CONTEXT_FACTORY_TYPE_ERROR
            )
        return value
