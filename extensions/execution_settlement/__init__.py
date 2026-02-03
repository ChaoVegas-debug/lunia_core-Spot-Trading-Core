"""
EXECUTION SETTLEMENT — Public API

PHASE 14E: Post-Trade Sync (Ledger & Settlement)

⚠️ CRITICAL GOVERNANCE:
ExecutionSettler is READ-ONLY relative to exchange.

Responsibilities:
- Extract truth from routing/reconciliation
- Append to ledger (idempotent)
- Apply to portfolio (if FILLED)
- Zero double counting

NOT responsible for:
- Trading decisions (Hands Not Brain)
- Order creation/cancellation
- Exchange queries (read-only relative to exchange)

Import Rules:
Settlement MUST NOT be imported by:
- shadow_mode
- genome_dsl (core logic)
- hud_api
- execution_gateway (Phase 14A)
- execution_router (Phase 14C)
- exchange_connectivity (write modules)

Violation = bypass risk or circular dependency.
"""

from .settler import ExecutionSettler
from .ledger import ExecutionLedger
from .models import (
    SettlementResult,
    SettlementStatus,
    SkipReason,
    SettlementError,
    PortfolioApplyResult,
    PortfolioSink,
    stable_json,
    canonical_ts,
    is_terminal_status,
    derive_idempotency_key,
    extract_truth,
)

__all__ = [
    "ExecutionSettler",
    "ExecutionLedger",
    "SettlementResult",
    "SettlementStatus",
    "SkipReason",
    "SettlementError",
    "PortfolioApplyResult",
    "PortfolioSink",
    "stable_json",
    "canonical_ts",
    "is_terminal_status",
    "derive_idempotency_key",
    "extract_truth",
]
