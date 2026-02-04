"""
EPOCH E Phase E3.1: Composite Risk Context Provider
Orchestrates all sub-providers with fail-closed semantics
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from lunia_core.app.services.strategy.models import IntentProposal
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot
from lunia_core.app.services.governance.context import GovernanceContext

from lunia_core.app.services.risk.models import RiskContext, Position

from .base import IRiskContextProvider, RiskContextBuildResult, ProviderErrorCodes
from .portfolio import IPortfolioProvider
from .marks import IMarkPriceProvider
from .volatility import IVolatilityProvider


logger = logging.getLogger(__name__)


class CompositeRiskContextProvider(IRiskContextProvider):
    """
    Composite provider orchestrating all sub-providers
    
    LOCKED INVARIANTS:
    - NO PARTIAL CONTEXT: if ANY sub-provider fails, ok=False, context=None
    - ONE INTENT → ONE CONTEXT: build_context tied to incoming intent
    - SYMBOL UNIVERSE: intent.symbol minimum required
    - IDEMPOTENCY: same inputs + now_ms → bit-identical output
    - SIDE-EFFECT FREE: read-only operations
    
    DI Architecture:
    - All sub-providers injected via constructor
    - Enables testing with mocks
    """
    
    def __init__(
        self,
        portfolio_provider: IPortfolioProvider,
        marks_provider: IMarkPriceProvider,
        volatility_provider: IVolatilityProvider
    ):
        """
        Initialize with DI
        
        Args:
            portfolio_provider: Portfolio state provider
            marks_provider: Mark price provider
            volatility_provider: Volatility provider
        """
        self.portfolio_provider = portfolio_provider
        self.marks_provider = marks_provider
        self.volatility_provider = volatility_provider
        
        logger.info("CompositeRiskContextProvider initialized")
    
    def build_context(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        gov_context: GovernanceContext,
        now_ms: Optional[int] = None
    ) -> RiskContextBuildResult:
        """
        Build RiskContext from all sub-providers
        
        CRITICAL FLOW:
        1. Get portfolio state
        2. Get mark prices for required symbols
        3. Get volatility for required symbols
        4. If ANY fails → ok=False, context=None (NO PARTIAL CONTEXT)
        5. Else build complete RiskContext
        
        Args:
            intent: IntentProposal (defines symbol universe)
            snapshot: MarketSnapshot
            gov_context: GovernanceContext
            now_ms: Optional timestamp for determinism
        
        Returns:
            RiskContextBuildResult (ok=True with complete context, or ok=False)
        """
        process_timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        all_blocking_errors = []
        all_warnings = []
        all_metadata = {}
        
        try:
            # STEP 1: Get portfolio state
            portfolio_result = self.portfolio_provider.get_portfolio(now_ms)
            
            if not portfolio_result.ok:
                # Portfolio failed → NO PARTIAL CONTEXT
                all_blocking_errors.extend(portfolio_result.blocking_errors)
                all_metadata["portfolio"] = portfolio_result.metadata
                
                return RiskContextBuildResult(
                    ok=False,
                    context=None,
                    blocking_errors=all_blocking_errors,
                    metadata=all_metadata
                )
            
            all_metadata["portfolio"] = portfolio_result.metadata
            
            # STEP 2: Get mark prices
            # Symbol universe: intent.symbol is minimum required
            required_symbols = [intent.symbol]
            
            # Add symbols from positions (for exposure calculation)
            if portfolio_result.positions:
                required_symbols.extend(portfolio_result.positions.keys())
            
            # Deduplicate
            required_symbols = list(set(required_symbols))
            
            marks_result = self.marks_provider.get_mark_prices(
                required_symbols,
                snapshot,
                now_ms
            )
            
            if not marks_result.ok:
                # Marks failed → NO PARTIAL CONTEXT
                all_blocking_errors.extend(marks_result.blocking_errors)
                all_metadata["marks"] = marks_result.metadata
                
                return RiskContextBuildResult(
                    ok=False,
                    context=None,
                    blocking_errors=all_blocking_errors,
                    metadata=all_metadata
                )
            
            all_metadata["marks"] = marks_result.metadata
            
            # STEP 3: Get volatility
            vol_result = self.volatility_provider.get_volatility_map(
                required_symbols,
                now_ms
            )
            
            if not vol_result.ok:
                # Volatility failed → NO PARTIAL CONTEXT
                all_blocking_errors.extend(vol_result.blocking_errors)
                all_metadata["volatility"] = vol_result.metadata
                
                return RiskContextBuildResult(
                    ok=False,
                    context=None,
                    blocking_errors=all_blocking_errors,
                    metadata=all_metadata
                )
            
            all_metadata["volatility"] = vol_result.metadata
            all_warnings.extend(vol_result.warnings)
            
            # STEP 4: Build complete RiskContext
            context = RiskContext(
                portfolio_equity=portfolio_result.equity,
                peak_equity=portfolio_result.peak_equity,
                open_positions=portfolio_result.positions or {},
                mark_prices=marks_result.mark_prices,
                volatility_map=vol_result.volatility_map,
                now_ms=process_timestamp
            )
            
            # STEP 5: Return complete result
            all_metadata["composite"] = {
                "provider_type": "composite",
                "intent_symbol": intent.symbol,
                "symbols_evaluated": required_symbols,
                "process_timestamp": process_timestamp
            }
            
            return RiskContextBuildResult(
                ok=True,
                context=context,
                blocking_errors=[],
                warnings=all_warnings,
                metadata=all_metadata
            )
        
        except Exception as e:
            # Unexpected exception → FAIL-CLOSED
            logger.error(f"CompositeRiskContextProvider exception: {e}", exc_info=True)
            
            all_blocking_errors.append(ProviderErrorCodes.PROVIDER_EXCEPTION)
            all_metadata["exception"] = {
                "error": str(e),
                "type": type(e).__name__
            }
            
            return RiskContextBuildResult(
                ok=False,
                context=None,
                blocking_errors=all_blocking_errors,
                metadata=all_metadata
            )
