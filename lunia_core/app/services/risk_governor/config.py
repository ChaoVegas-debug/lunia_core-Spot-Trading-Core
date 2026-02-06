"""
Risk Limits Configuration

Conservative institutional defaults with fail-closed philosophy.
All limits configurable but immutable at runtime (frozen).
"""
from typing import Dict

from pydantic import BaseModel, Field


class RiskLimits(BaseModel):
    """
    Portfolio risk limit configuration.
    
    HARD LIMITS: Violations → BLOCK
    SOFT LIMITS: Violations → MANUAL_REVIEW or DOWNGRADE
    
    All percentages expressed as decimals (0.02 = 2%).
    """
    
    # =========================================================================
    # HARD LIMITS (BLOCK)
    # =========================================================================
    
    # Order sizing
    max_order_notional_pct_of_equity: float = 0.02  # 2% max per order
    
    # Position sizing
    max_position_notional_pct_of_equity: float = 0.10  # 10% max per symbol
    
    # Portfolio exposure
    max_total_gross_exposure_pct_of_equity: float = 0.50  # 50% max gross
    max_total_net_exposure_pct_of_equity: float = 0.25  # 25% max net
    
    # Cluster exposure (correlated assets)
    max_cluster_gross_exposure_pct_of_equity: float = 0.25  # 25% max per cluster
    
    # Rate limits
    max_symbol_orders_per_hour: int = 6  # Prevent thrashing
    
    # Data staleness
    snapshot_max_age_ms: int = 10_000  # 10 seconds max staleness
    
    # Circuit breaker
    circuit_breaker_consecutive_blocks: int = 5  # Halt after 5 consecutive blocks
    
    # =========================================================================
    # SOFT LIMITS (WARN)
    # =========================================================================
    
    # Order sizing warnings
    warn_order_notional_pct_of_equity: float = 0.015  # 1.5% warn threshold
    
    # Position sizing warnings
    warn_position_notional_pct_of_equity: float = 0.07  # 7% warn threshold
    
    # Portfolio exposure warnings
    warn_total_gross_exposure_pct_of_equity: float = 0.40  # 40% warn threshold
    
    # Cluster exposure warnings
    warn_cluster_gross_exposure_pct_of_equity: float = 0.20  # 20% warn threshold
    
    # Concentration delta warnings (new order impact)
    warn_symbol_concentration_delta_pct: float = 0.03  # 3% concentration increase
    
    # =========================================================================
    # CORRELATION CLUSTERING
    # =========================================================================
    
    # Map symbols to correlation clusters
    # Example: {"BTC": "CRYPTO_LARGE_CAP", "ETH": "CRYPTO_LARGE_CAP"}
    correlation_clusters: Dict[str, str] = Field(default_factory=dict)
    default_cluster_id: str = "UNCLUSTERED"
    
    # =========================================================================
    # ROLLOUT CONTROLS
    # =========================================================================
    
    # Shadow mode: LOG_ONLY decisions (allow but journal)
    shadow_mode: bool = False
    
    # Soft violation action: "MANUAL_REVIEW" or "DOWNGRADE_TO_DRY_RUN"
    soft_action: str = "MANUAL_REVIEW"
    
    class Config:
        frozen = True
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def get_cluster_id(self, symbol: str) -> str:
        """Get correlation cluster ID for symbol"""
        return self.correlation_clusters.get(symbol, self.default_cluster_id)
    
    def to_snapshot_dict(self) -> Dict:
        """Export limits as dict for audit trail"""
        return {
            "max_order_notional_pct": self.max_order_notional_pct_of_equity,
            "max_position_notional_pct": self.max_position_notional_pct_of_equity,
            "max_gross_exposure_pct": self.max_total_gross_exposure_pct_of_equity,
            "max_net_exposure_pct": self.max_total_net_exposure_pct_of_equity,
            "max_cluster_exposure_pct": self.max_cluster_gross_exposure_pct_of_equity,
            "max_symbol_orders_per_hour": self.max_symbol_orders_per_hour,
            "snapshot_max_age_ms": self.snapshot_max_age_ms,
            "circuit_breaker_threshold": self.circuit_breaker_consecutive_blocks,
            "shadow_mode": self.shadow_mode,
            "soft_action": self.soft_action,
        }
