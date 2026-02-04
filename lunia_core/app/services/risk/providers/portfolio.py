"""
EPOCH E Phase E3.1: Portfolio Provider
Deterministic portfolio state provision with fail-closed validation
"""
from __future__ import annotations

import time
from typing import Dict, Optional, Callable
from pydantic import BaseModel, Field

from lunia_core.app.services.risk.models import Position
from .base import ProviderErrorCodes


class PortfolioResult(BaseModel):
    """Portfolio provider result"""
    ok: bool
    equity: Optional[float] = None
    peak_equity: Optional[float] = None
    positions: Optional[Dict[str, Position]] = None
    blocking_errors: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class IPortfolioProvider:
    """Interface for portfolio state provision"""
    
    def get_portfolio(self, now_ms: Optional[int] = None) -> PortfolioResult:
        """Get portfolio state"""
        raise NotImplementedError


class InMemoryPortfolioProvider(IPortfolioProvider):
    """
    In-memory portfolio provider with DI
    
    LOCKED INVARIANTS:
    - equity > 0 (MUST)
    - peak_equity >= equity (MUST)
    - Empty positions allowed if equity valid (VALID EMPTY STATE)
    - Side-effect free (read-only)
    """
    
    def __init__(
        self,
        state_callable: Callable[[], tuple[float, float, Dict[str, Position]]],
        source_id: str = "inmemory_portfolio"
    ):
        """
        Initialize with DI
        
        Args:
            state_callable: Function returning (equity, peak_equity, positions)
            source_id: Portfolio source identifier
        """
        self.state_callable = state_callable
        self.source_id = source_id
    
    def get_portfolio(self, now_ms: Optional[int] = None) -> PortfolioResult:
        """Get portfolio state with validation"""
        process_timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        errors = []
        
        try:
            equity, peak_equity, positions = self.state_callable()
            
            # Validate equity
            if equity is None:
                errors.append(ProviderErrorCodes.EQUITY_MISSING)
                return PortfolioResult(ok=False, blocking_errors=errors)
            
            if equity <= 0:
                errors.append(ProviderErrorCodes.EQUITY_INVALID)
                return PortfolioResult(ok=False, blocking_errors=errors)
            
            # Validate peak_equity
            if peak_equity is None or peak_equity < equity:
                errors.append(ProviderErrorCodes.PEAK_EQUITY_INVALID)
                return PortfolioResult(ok=False, blocking_errors=errors)
            
            # Positions can be empty (valid empty state)
            if positions is None:
                positions = {}
            
            # Build metadata
            metadata = {
                "portfolio_source_id": self.source_id,
                "revision_id": "latest",  # Could be version/hash in production
                "data_timestamp": process_timestamp,  # In real impl, from source
                "process_timestamp": process_timestamp,
                "position_count": len(positions)
            }
            
            return PortfolioResult(
                ok=True,
                equity=equity,
                peak_equity=peak_equity,
                positions=positions,
                metadata=metadata
            )
        
        except Exception as e:
            errors.append(ProviderErrorCodes.PROVIDER_EXCEPTION)
            return PortfolioResult(
                ok=False,
                blocking_errors=errors,
                metadata={"exception": str(e)}
            )
