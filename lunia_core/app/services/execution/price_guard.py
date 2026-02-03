"""
EPOCH D Phase D3.2: Price Sanity Guard
Pricing guards for fat finger protection and market liquidity checks
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..market_data.realtime.models import MarketSnapshot, SnapshotState


logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    """
    Guard result
    
    Attributes:
        passed: Whether guard passed
        reason_code: Machine-readable reason code
        details: Additional context (sanitized, bounded)
    """
    passed: bool
    reason_code: str
    details: Dict[str, Any]


class PriceSanityGuard:
    """
    Price sanity guard for execution safety
    
    Features:
    - LIMIT orders: price band check vs mid_price (default 5%)
    - MARKET orders: liquidity presence check (bids/asks non-empty)
    - Fail-closed on missing/malformed data
    - Configurable via LUNIA_PRICE_BAND_PCT environment variable
    """
    
    # Reason codes (machine-readable, audit-safe)
    EXECUTION_BLOCKED_MD_NOT_VALID = "EXECUTION_BLOCKED_MD_NOT_VALID"
    EXECUTION_BLOCKED_PRICE_BAND = "EXECUTION_BLOCKED_PRICE_BAND"
    EXECUTION_BLOCKED_NO_LIQUIDITY = "EXECUTION_BLOCKED_NO_LIQUIDITY"
    EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER = "EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER"
    EXECUTION_BLOCKED_GUARD_BAD_CONFIG = "EXECUTION_BLOCKED_GUARD_BAD_CONFIG"
    EXECUTION_BLOCKED_MD_CROSSED_OR_INVALID = "EXECUTION_BLOCKED_MD_CROSSED_OR_INVALID"
    
    def __init__(self, band_pct: Optional[float] = None):
        """
        Initialize price sanity guard
        
        Args:
            band_pct: Price band percentage (overrides env var)
        """
        # Load band_pct from environment or default
        if band_pct is None:
            try:
                band_pct = float(os.getenv("LUNIA_PRICE_BAND_PCT", "5.0"))
            except (ValueError, TypeError):
                logger.error("Invalid LUNIA_PRICE_BAND_PCT, using fail-closed default 0.0")
                band_pct = 0.0  # Fail-closed: reject all orders if config bad
        
        # Validate band_pct range
        if not (0 < band_pct <= 50):
            logger.error(f"Invalid band_pct={band_pct}, must be 0 < band_pct <= 50. Using fail-closed default 0.0")
            band_pct = 0.0  # Fail-closed
        
        self.band_pct = band_pct
        logger.info(f"PriceSanityGuard initialized: band_pct={self.band_pct}%")
    
    def validate(
        self,
        order_spec: Dict[str, Any],
        snapshot: Optional[MarketSnapshot]
    ) -> GuardResult:
        """
        Validate order spec against market snapshot
        
        Features DOUBLE STALENESS CHECK:
        1. snapshot.snapshot_state == VALID
        2. (now_ms - snapshot.received_at_ms) < staleness_threshold
        
        Args:
            order_spec: Order specification dict
            snapshot: Market snapshot
        
        Returns:
            GuardResult
        """
        import os
        import time
        
        # Extract order fields (repo-grounded)
        symbol = order_spec.get("symbol")
        side = order_spec.get("side")  # "BUY" or "SELL"
        order_style = order_spec.get("order_style")  # "LIMIT" or "MARKET"
        price = order_spec.get("price")  # Only for LIMIT orders
        
        # Malformed order check
        if not symbol or not side or not order_style:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER,
                details={"missing_fields": [k for k in ["symbol", "side", "order_style"] if not order_spec.get(k)]}
            )
        
        # Snapshot validity gate (MANDATORY - Part 1 of Double Check)
        if snapshot is None:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_MD_NOT_VALID,
                details={"snapshot_state": "MISSING", "symbol": symbol}
            )
        
        if snapshot.snapshot_state != SnapshotState.VALID:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_MD_NOT_VALID,
                details={
                    "snapshot_state": snapshot.snapshot_state.value,
                    "symbol": symbol,
                    "snapshot_version": snapshot.version
                }
            )
        
        # AGE CHECK (MANDATORY - Part 2 of Double Check - ZOMBIE GUARD)
        # Protects against "VALID but frozen" scenarios where engine is alive but data feed is dead
        staleness_threshold_ms = int(os.getenv("LUNIA_STALENESS_THRESHOLD_MS", "5000"))
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - snapshot.last_update_ms
        
        if age_ms > staleness_threshold_ms:
            return GuardResult(
                passed=False,
                reason_code="EXECUTION_BLOCKED_MD_TOO_OLD",
                details={
                    "age_ms": age_ms,
                    "threshold_ms": staleness_threshold_ms,
                    "symbol": symbol,
                    "snapshot_version": snapshot.version,
                    "snapshot_state": snapshot.snapshot_state.value,
                    "reason": "Zombie snapshot detected (VALID state but ancient timestamp)"
                }
            )
        
        # Check for crossed/invalid state (additional safety)
        if snapshot.snapshot_state == SnapshotState.INVALID:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_MD_CROSSED_OR_INVALID,
                details={
                    "snapshot_state": "INVALID",
                    "symbol": symbol,
                    "bid": snapshot.bid,
                    "ask": snapshot.ask
                }
            )
        
        # Route by order style
        if order_style == "LIMIT":
            return self._validate_limit_order(order_spec, snapshot, price)
        elif order_style == "MARKET":
            return self._validate_market_order(order_spec, snapshot, side)
        else:
            # Unknown order style -> fail-closed
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER,
                details={"unknown_order_style": order_style}
            )
    
    def _validate_limit_order(
        self,
        order_spec: Dict[str, Any],
        snapshot: MarketSnapshot,
        price: Optional[float]
    ) -> GuardResult:
        """
        Validate LIMIT order (price band check)
        
        Args:
            order_spec: Order spec
            snapshot: Market snapshot (VALID)
            price: Order price
        
        Returns:
            GuardResult
        """
        symbol = order_spec["symbol"]
        
        # Price must be present and finite
        if price is None or not math.isfinite(price) or price <= 0:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER,
                details={"invalid_price": price}
            )
        
        # Mid price must be present and finite
        mid = snapshot.mid_price
        if mid is None:
            # Fallback to (bid + ask) / 2 if mid not computed
            if snapshot.bid is not None and snapshot.ask is not None:
                mid = (snapshot.bid + snapshot.ask) / 2.0
            else:
                # No mid price available -> fail-closed
                return GuardResult(
                    passed=False,
                    reason_code=self.EXECUTION_BLOCKED_MD_NOT_VALID,
                    details={"reason": "mid_price_missing", "symbol": symbol}
                )
        
        if not math.isfinite(mid) or mid <= 0:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_MD_NOT_VALID,
                details={"invalid_mid_price": mid}
            )
        
        # Compute deviation
        deviation_pct = abs(price - mid) / mid * 100.0
        
        # Check band
        if deviation_pct > self.band_pct:
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_PRICE_BAND,
                details={
                    "order_price": price,
                    "mid_price": mid,
                    "deviation_pct": round(deviation_pct, 2),
                    "band_pct": self.band_pct,
                    "symbol": symbol,
                    "snapshot_version": snapshot.version
                }
            )
        
        # Passed
        return GuardResult(
            passed=True,
            reason_code="OK",
            details={"deviation_pct": round(deviation_pct, 2)}
        )
    
    def _validate_market_order(
        self,
        order_spec: Dict[str, Any],
        snapshot: MarketSnapshot,
        side: str
    ) -> GuardResult:
        """
        Validate MARKET order (liquidity presence check)
        
        Args:
            order_spec: Order spec
            snapshot: Market snapshot (VALID)
            side: "BUY" or "SELL"
        
        Returns:
            GuardResult
        """
        symbol = order_spec["symbol"]
        
        # Check liquidity presence
        if side == "BUY":
            # Need asks (selling side)
            if not snapshot.asks or len(snapshot.asks) == 0:
                return GuardResult(
                    passed=False,
                    reason_code=self.EXECUTION_BLOCKED_NO_LIQUIDITY,
                    details={
                        "book_side": "asks",
                        "symbol": symbol,
                        "side": side,
                        "snapshot_version": snapshot.version
                    }
                )
            
            # Extract top level for context
            top_ask = snapshot.asks[0]
            details = {
                "book_side": "asks",
                "top_price": top_ask.price,
                "top_amount": top_ask.amount
            }
        
        elif side == "SELL":
            # Need bids (buying side)
            if not snapshot.bids or len(snapshot.bids) == 0:
                return GuardResult(
                    passed=False,
                    reason_code=self.EXECUTION_BLOCKED_NO_LIQUIDITY,
                    details={
                        "book_side": "bids",
                        "symbol": symbol,
                        "side": side,
                        "snapshot_version": snapshot.version
                    }
                )
            
            # Extract top level
            top_bid = snapshot.bids[0]
            details = {
                "book_side": "bids",
                "top_price": top_bid.price,
                "top_amount": top_bid.amount
            }
        
        else:
            # Unknown side -> fail-closed
            return GuardResult(
                passed=False,
                reason_code=self.EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER,
                details={"unknown_side": side}
            )
        
        # Passed
        return GuardResult(
            passed=True,
            reason_code="OK",
            details=details
        )
