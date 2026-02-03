"""
EPOCH E Phase E3.1: Volatility Providers
Deterministic v volatility sourcing with strict contracts
"""
from __future__ import annotations

import os
import time
import math
from typing import Dict, Optional, Protocol
from pydantic import BaseModel, Field

from .base import ProviderErrorCodes


class VolResult(BaseModel):
    """Volatility provider result"""
    ok: bool
    volatility_map: Optional[Dict[str, float]] = None
    blocking_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class IVolatilityProvider(Protocol):
    """Interface for volatility provision"""
    
    def get_volatility_map(
        self,
        symbols: list[str],
        now_ms: Optional[int] = None
    ) -> VolResult:
        """Get annualized volatility for symbols"""
        ...


class TestStaticVolatilityProvider:
    """
    Static volatility provider (TESTS ONLY)
    
    CRITICAL: This provider is FORBIDDEN in production
    Must be explicitly flagged in metadata
    """
    
    def __init__(self, static_vol: float = 0.20):
        """
        Initialize with static volatility
        
        Args:
            static_vol: Static annualized volatility (default 20%)
        """
        self.static_vol = static_vol
    
    def get_volatility_map(
        self,
        symbols: list[str],
        now_ms: Optional[int] = None
    ) -> VolResult:
        """Return static volatility for all symbols"""
        process_timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        
        volatility_map = {symbol: self.static_vol for symbol in symbols}
        
        metadata = {
            "source": "TEST_STATIC_ONLY",  # CRITICAL FLAG
            "volatility_value": self.static_vol,
            "data_timestamp": process_timestamp,
            "process_timestamp": process_timestamp,
            "WARNING": "FORBIDDEN IN PRODUCTION"
        }
        
        warnings = ["VOLATILITY_SOURCE_STATIC_TEST_ONLY"]
        
        return VolResult(
            ok=True,
            volatility_map=volatility_map,
            warnings=warnings,
            metadata=metadata
        )


class D2RollingVolatilityProvider:
    """
    D2 rolling window volatility provider (PRIMARY)
    
    LOCKED INVARIANTS:
    - Reads from D2 historical repository (append-only)
    - Computes annualized vol: std(returns) * sqrt(annualization_days)
    - Fail-closed if missing series or samples < min_samples
    - Side-effect free (read-only)
    """
    
    def __init__(
        self,
        d2_repository: Optional[object] = None,  # D2 historical interface (DI)
        window_samples: Optional[int] = None,
        min_samples: Optional[int] = None,
        annualization_days: Optional[int] = None
    ):
        """
        Initialize with D2 repository and config
        
        Args:
            d2_repository: D2 historical data repository (DI)
            window_samples: Rolling window size (default from env)
            min_samples: Minimum required samples (default from env)
            annualization_days: Annualization factor (default 252)
        """
        self.d2_repository = d2_repository
        
        # Load config with fail-fast
        self.window_samples = window_samples or int(os.getenv("LUNIA_VOL_WINDOW_SAMPLES", "120"))
        self.min_samples = min_samples or int(os.getenv("LUNIA_VOL_MIN_SAMPLES", "60"))
        self.annualization_days = annualization_days or int(os.getenv("LUNIA_VOL_ANNUALIZATION_DAYS", "252"))
        
        # Validate config (fail-fast)
        if self.window_samples < 1 or self.min_samples < 1:
            raise ValueError("Invalid volatility config: samples must be > 0")
        if self.min_samples > self.window_samples:
            raise ValueError("min_samples cannot exceed window_samples")
    
    def get_volatility_map(
        self,
        symbols: list[str],
        now_ms: Optional[int] = None
    ) -> VolResult:
        """Compute rolling volatility from D2 returns"""
        process_timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        errors = []
        volatility_map = {}
        
        # Check D2 repository availability
        if self.d2_repository is None:
            errors.append(ProviderErrorCodes.VOL_MISSING)
            return VolResult(
                ok=False,
                blocking_errors=errors,
                metadata={"reason": "No D2 repository available"}
            )
        
        # Fetch returns for each symbol
        for symbol in symbols:
            try:
                # Call D2 repository get_returns (real implementation)
                result = self.d2_repository.get_returns(
                    symbol,
                    end_ms=process_timestamp,
                    window_samples=self.window_samples
                )
                
                if not result.ok:
                    # D2 failed (insufficient samples, missing data, etc.)
                    errors.append(ProviderErrorCodes.VOL_INSUFFICIENT_SAMPLES)
                    return VolResult(
                        ok=False,
                        blocking_errors=errors,
                        metadata={
                            "symbol": symbol,
                            "d2_error": result.error_code
                        }
                    )
                
                # Get returns from D2 result
                returns = result.metadata.get("returns", [])
                
                if len(returns) < self.min_samples:
                    errors.append(ProviderErrorCodes.VOL_INSUFFICIENT_SAMPLES)
                    return VolResult(
                        ok=False,
                        blocking_errors=errors,
                        metadata={
                            "symbol": symbol,
                            "samples_got": len(returns),
                            "min_required": self.min_samples
                        }
                    )
                
                # Compute annualized volatility
                # Formula: std(returns) * sqrt(annualization_days)
                std_dev = self._compute_std(returns)
                annualized_vol = std_dev * math.sqrt(self.annualization_days)
                
                volatility_map[symbol] = annualized_vol
            
            except Exception as e:
                errors.append(ProviderErrorCodes.PROVIDER_EXCEPTION)
                return VolResult(
                    ok=False,
                    blocking_errors=errors,
                    metadata={"symbol": symbol, "exception": str(e)}
                )
        
        # Build metadata
        metadata = {
            "source": "D2_ROLLING",
            "method": "rolling_std_returns",
            "window_samples": self.window_samples,
            "min_samples": self.min_samples,
            "annualization_days": self.annualization_days,
            "data_timestamp": process_timestamp,
            "process_timestamp": process_timestamp
        }
        
        return VolResult(ok=True, volatility_map=volatility_map, metadata=metadata)
    
    def _compute_std(self, values: list[float]) -> float:
        """Compute standard deviation"""
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return math.sqrt(variance)
