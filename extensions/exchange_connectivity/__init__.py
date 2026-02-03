"""
EXCHANGE CONNECTIVITY — Public API

PHASE 12A: Read-only Binance client
PHASE 14B: Write-enabled execution client

⚠️ GOVERNANCE WARNING:
BinanceExecutionClient MUST ONLY be imported by:
- Router layer (to be implemented)
- Tests

NEVER import in:
- shadow_mode
- genome_dsl
- virtual_portfolio
- hud_api
- execution_gateway (Phase 14A)

Violation = bypass of the single chokepoint.
"""

from .binance_client import BinanceClient, build_binance_client_from_env
from .execution_client import BinanceExecutionClient
from .trade_models import OrderResult, OrderStatus, OrderSide, OrderType
from .models import ErrorCode, ErrorObject, Response
from .security import SafeSecret

__all__ = [
    # Phase 12A (Read-Only)
    "BinanceClient",
    "build_binance_client_from_env",
    
    # Phase 14B (Write-Enabled) — RESTRICTED IMPORT
    "BinanceExecutionClient",
    "OrderResult",
    "OrderStatus",
    "OrderSide",
    "OrderType",
    
    # Shared
    "ErrorCode",
    "ErrorObject",
    "Response",
    "SafeSecret",
]
