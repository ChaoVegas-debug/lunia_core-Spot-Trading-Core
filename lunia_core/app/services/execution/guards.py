"""
EPOCH C: Execution Guards
Portfolio Conflict Guard + Slippage + Liquidity Guard
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardStatus(str, Enum):
    """Guard check result status"""
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class GuardResult:
    """Guard check result"""
    status: GuardStatus
    reasons: List[str]  # Human-readable
    reason_codes: List[str]  # Machine-readable
    metadata: Optional[Dict[str, Any]] = None  # Additional context


class BaseGuard(ABC):
    """Base class for execution guards"""
    
    @abstractmethod
    def check(self, *args, **kwargs) -> GuardResult:
        """Execute guard check"""
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PORTFOLIO CONFLICT GUARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PortfolioConflictGuard(BaseGuard):
    """
    Portfolio Conflict Guard
    
    Checks:
    1. Opposing positions (BUY with existing SHORT → BLOCK)
    2. Concentration (single asset >25% → BLOCK)
    3. Correlation exposure (>50% → WARN)
    4. Net exposure (>80% → BLOCK)
    
    Tier-based limits.
    """
    
    def __init__(self, tier: str = "INST_LITE"):
        self.tier = tier
        self.config = self._get_config(tier)
    
    def _get_config(self, tier: str) -> Dict[str, float]:
        """Get tier-based configuration"""
        configs = {
            "BEGINNER": {
                "max_single_asset_pct": 0.20,
                "max_correlated_exposure_pct": 0.40,
                "max_net_exposure_pct": 0.60
            },
            "ADV_RETAIL": {
                "max_single_asset_pct": 0.25,
                "max_correlated_exposure_pct": 0.50,
                "max_net_exposure_pct": 0.80
            },
            "INST_LITE": {
                "max_single_asset_pct": 0.40,
                "max_correlated_exposure_pct": 0.60,
                "max_net_exposure_pct": 0.90
            }
        }
        return configs.get(tier, configs["INST_LITE"])
    
    def check(
        self,
        intent: Dict[str, Any],
        portfolio: Dict[str, Any],
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    ) -> GuardResult:
        """
        Check for portfolio conflicts
        
        Args:
            intent: ExecutionIntent dict (asset, action, size_usd)
            portfolio: Portfolio snapshot (positions, equity_usd)
            correlation_matrix: Optional correlation matrix
        
        Returns:
            GuardResult (PASS/WARN/BLOCK)
        """
        reasons = []
        reason_codes = []
        status = GuardStatus.PASS
        
        # Fail-closed: missing portfolio
        if not portfolio or not portfolio.get("equity_usd"):
            return GuardResult(
                status=GuardStatus.BLOCK,
                reasons=["Missing portfolio snapshot - BLOCKED in REAL mode"],
                reason_codes=["MISSING_PORTFOLIO"]
            )
        
        asset = intent.get("asset", "")
        action = intent.get("action", "BUY")
        size_usd = intent.get("size_usd", 0)
        
        positions = portfolio.get("positions", {})
        equity_usd = portfolio.get("equity_usd", 1.0)
        
        # FIX #3: Check reduce_only flag
        reduce_only = intent.get("reduce_only", False)
        
        # Check 1: Opposing Position
        existing_position = positions.get(asset, {})
        if existing_position:
            existing_side = existing_position.get("side", "LONG")
            
            # Only BLOCK if opening opposing position (NOT reduce_only)
            if not reduce_only:
                if action == "BUY" and existing_side == "SHORT":
                    status = GuardStatus.BLOCK
                    reasons.append(f"OPPOSING_POSITION_OPEN: Attempting to BUY while holding SHORT on {asset} (not reduce_only)")
                    reason_codes.append("OPPOSING_POSITION_OPEN")
                elif action == "SELL" and existing_side == "LONG":
                    status = GuardStatus.BLOCK
                    reasons.append(f"OPPOSING_POSITION_OPEN: Attempting to SELL while holding LONG on {asset} (not reduce_only)")
                    reason_codes.append("OPPOSING_POSITION_OPEN")
            else:
                # reduce_only=True: This is a legitimate close/reduce action
                # PASS (or WARN for audit trail)
                if (action == "SELL" and existing_side == "LONG") or (action == "BUY" and existing_side == "SHORT"):
                    if status == GuardStatus.PASS:
                        status = GuardStatus.WARN
                    reasons.append(f"OPPOSING_POSITION_REDUCE_OK: {action} to reduce/close {existing_side} position on {asset} (reduce_only=True)")
                    reason_codes.append("OPPOSING_POSITION_REDUCE_OK")
        
        # Check 2: Concentration Limit
        existing_value = existing_position.get("value_usd", 0) if existing_position else 0
        post_trade_value = existing_value + size_usd
        post_trade_concentration = post_trade_value / equity_usd
        
        if post_trade_concentration > self.config["max_single_asset_pct"]:
            status = GuardStatus.BLOCK
            reasons.append(
                f"CONCENTRATION: {asset} would be {post_trade_concentration:.1%} of portfolio "
                f"(max {self.config['max_single_asset_pct']:.1%})"
            )
            reason_codes.append("CONCENTRATION_EXCEEDED")
        
        # Check 3: Correlation Conflict (WARNING only)
        if correlation_matrix:
            correlated_exposure = 0.0
            for other_asset, position in positions.items():
                if other_asset == asset:
                    continue
                correlation = correlation_matrix.get(asset, {}).get(other_asset, 0.0)
                if correlation > 0.7:  # Highly correlated
                    correlated_exposure += position.get("value_usd", 0)
            
            correlated_exposure += size_usd
            correlated_pct = correlated_exposure / equity_usd
            
            if correlated_pct > self.config["max_correlated_exposure_pct"]:
                if status == GuardStatus.PASS:
                    status = GuardStatus.WARN
                reasons.append(
                    f"CORRELATION: Correlated exposure {correlated_pct:.1%} "
                    f"(max {self.config['max_correlated_exposure_pct']:.1%})"
                )
                reason_codes.append("HIGH_CORRELATION")
        
        # Check 4: Net Exposure
        net_exposure_usd = sum(
            p.get("value_usd", 0) * (1 if p.get("side") == "LONG" else -1)
            for p in positions.values()
        )
        net_exposure_usd += size_usd * (1 if action == "BUY" else -1)
        net_exposure_pct = abs(net_exposure_usd) / equity_usd
        
        if net_exposure_pct > self.config["max_net_exposure_pct"]:
            status = GuardStatus.BLOCK
            reasons.append(
                f"NET_EXPOSURE: {net_exposure_pct:.1%} exceeds limit "
                f"({self.config['max_net_exposure_pct']:.1%})"
            )
            reason_codes.append("NET_EXPOSURE_EXCEEDED")
        
        return GuardResult(
            status=status,
            reasons=reasons,
            reason_codes=reason_codes,
            metadata={
                "post_trade_concentration": post_trade_concentration,
                "net_exposure_pct": net_exposure_pct
            }
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIPPAGE + LIQUIDITY GUARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlippageGuard(BaseGuard):
    """
    Slippage + Liquidity Guard
    
    Checks:
    1. Estimated slippage > max_slippage_pct → BLOCK
    2. Spread > 0.5% → BLOCK
    3. Orderbook depth < 3x order size → BLOCK
    4. Market impact > 5% → BLOCK
    """
    
    MAX_SPREAD_PCT = 0.005  # 0.5%
    MIN_DEPTH_MULTIPLIER = 3.0  # 3x order size
    MAX_IMPACT_PCT = 0.05  # 5%
    ORDERBOOK_STALENESS_SEC = 5  # Max age for orderbook
    
    def check(
        self,
        intent: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> GuardResult:
        """
        Check slippage and liquidity
        
        Args:
            intent: ExecutionIntent dict (asset, size_usd, max_slippage_pct)
            market_data: Market snapshot (mid_price, bid, ask, orderbook, timestamp)
        
        Returns:
            GuardResult (PASS/WARN/BLOCK)
        """
        reasons = []
        reason_codes = []
        status = GuardStatus.PASS
        
        # Fail-closed: missing market data
        if not market_data:
            return GuardResult(
                status=GuardStatus.BLOCK,
                reasons=["Missing market data - BLOCKED in REAL mode"],
                reason_codes=["MISSING_MARKET_DATA"]
            )
        
        # Fail-closed: stale orderbook
        from datetime import datetime, timezone
        orderbook_ts = market_data.get("timestamp")
        if orderbook_ts:
            try:
                # Parse ISO8601 timestamp
                if orderbook_ts.endswith('Z'):
                    orderbook_dt = datetime.fromisoformat(orderbook_ts.replace('Z', '+00:00'))
                else:
                    orderbook_dt = datetime.fromisoformat(orderbook_ts)
                
                # Compare with UTC now
                age_sec = (datetime.now(timezone.utc) - orderbook_dt).total_seconds()
                if age_sec > self.ORDERBOOK_STALENESS_SEC:
                    return GuardResult(
                        status=GuardStatus.BLOCK,
                        reasons=[f"Orderbook stale ({age_sec:.1f}s old, max {self.ORDERBOOK_STALENESS_SEC}s)"],
                        reason_codes=["ORDERBOOK_STALE"]
                    )
            except (ValueError, TypeError):
                # Could not parse timestamp - fail closed
                return GuardResult(
                    status=GuardStatus.BLOCK,
                    reasons=["Invalid orderbook timestamp - cannot verify freshness"],
                    reason_codes=["ORDERBOOK_TIMESTAMP_INVALID"]
                )
        
        mid_price = market_data.get("mid_price")
        bid = market_data.get("bid")
        ask = market_data.get("ask")
        size_usd = intent.get("size_usd", 0)
        max_slippage_pct = intent.get("max_slippage_pct", 0.5) / 100  # Convert % to decimal
        
        if not mid_price or not bid or not ask:
            return GuardResult(
                status=GuardStatus.BLOCK,
                reasons=["Missing price data (mid/bid/ask)"],
                reason_codes=["MISSING_PRICE_DATA"]
            )
        
        # Check 1: Spread
        spread_pct = (ask - bid) / mid_price
        if spread_pct > self.MAX_SPREAD_PCT:
            status = GuardStatus.BLOCK
            reasons.append(f"Spread {spread_pct:.2%} exceeds max {self.MAX_SPREAD_PCT:.2%}")
            reason_codes.append("SPREAD_TOO_WIDE")
        
        # Check 2: Orderbook Depth
        depth_2pct = market_data.get("orderbook_depth_2pct_usd", 0)
        min_depth_required = size_usd * self.MIN_DEPTH_MULTIPLIER
        
        if depth_2pct < min_depth_required:
            status = GuardStatus.BLOCK
            reasons.append(
                f"Insufficient orderbook depth (${depth_2pct:,.0f} < ${min_depth_required:,.0f})"
            )
            reason_codes.append("INSUFFICIENT_LIQUIDITY")
        
        # Check 3: Market Impact Estimate
        depth_1pct = market_data.get("orderbook_depth_1pct_usd", depth_2pct)
        if depth_1pct > 0:
            estimated_impact = size_usd / depth_1pct
            if estimated_impact > self.MAX_IMPACT_PCT:
                status = GuardStatus.BLOCK
                reasons.append(f"Market impact {estimated_impact:.2%} exceeds max {self.MAX_IMPACT_PCT:.2%}")
                reason_codes.append("MARKET_IMPACT_EXCESSIVE")
        
        # Check 4: Estimated Slippage
        # Simple model: slippage proportional to (size / depth)
        estimated_slippage = size_usd / depth_2pct if depth_2pct > 0 else 1.0
        if estimated_slippage > max_slippage_pct:
            status = GuardStatus.BLOCK
            reasons.append(
                f"Estimated slippage {estimated_slippage:.2%} > max {max_slippage_pct:.2%}"
            )
            reason_codes.append("SLIPPAGE_EXCEEDED")
        
        return GuardResult(
            status=status,
            reasons=reasons,
            reason_codes=reason_codes,
            metadata={
                "spread_pct": spread_pct,
                "depth_2pct_usd": depth_2pct,
                "estimated_impact": estimated_impact if depth_1pct > 0 else None,
                "estimated_slippage": estimated_slippage
            }
        )
