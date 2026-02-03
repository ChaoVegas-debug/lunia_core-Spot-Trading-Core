"""
PHASE 9.2 — REJECT CODES CATALOG

Stable, immutable rejection reason codes for the enforcement layer.

GUARANTEES:
- Code meanings NEVER change
- Codes are audit-stable (never reused)
- Severity and recoverability are explicit
"""

from enum import Enum
from typing import NamedTuple


class RejectSeverity(Enum):
    """Severity classification for rejections."""
    INFO = "info"              # Informational (e.g., NOOP by design)
    WARNING = "warning"        # Potentially concerning but valid
    ERROR = "error"            # Clear violation, operator review needed
    CRITICAL = "critical"      # System integrity threat


class RejectCode(Enum):
    """
    Stable rejection reason codes.
    
    INVARIANT: Code meanings are immutable. Never change semantics.
    New codes may be added, but existing codes NEVER change meaning.
    """
    
    # Protocol violations (1xx)
    PROTOCOL_VERSION_MISMATCH = "R101"
    PROTOCOL_SCHEMA_INVALID = "R102"
    PROTOCOL_TYPE_ERROR = "R103"
    
    # Traceability violations (2xx)
    CORRELATION_ID_MISMATCH = "R201"
    CORRELATION_ID_MISSING = "R202"
    INTENT_ID_FORMAT_INVALID = "R203"
    INTENT_ID_MISSING = "R204"
    TIMESTAMP_INVALID = "R205"
    TIMESTAMP_MISMATCH = "R206"
    
    # Governance blocks (3xx)
    GOVERNANCE_REDUCE_ONLY = "R301"
    GOVERNANCE_NO_NEW_ENTRIES = "R302"
    GOVERNANCE_RISK_STATE_BLACK = "R303"
    GOVERNANCE_RISK_STATE_RED = "R304"
    GOVERNANCE_EMERGENCY_OVERRIDE = "R305"
    
    # Intent semantics violations (4xx)
    ENTRY_MISSING_EXIT_PLAN = "R401"
    EXIT_PLAN_EMPTY = "R402"
    ENTRY_MISSING_SYMBOL = "R403"
    ENTRY_MISSING_DIRECTION = "R404"
    ENTRY_MISSING_SIZE = "R405"
    EXIT_MISSING_SYMBOL = "R406"
    NOOP_MISSING_RATIONALE = "R407"
    CONFIDENCE_OUT_OF_RANGE = "R408"
    
    # Money sanity violations (5xx)
    SIZE_NEGATIVE = "R501"
    SIZE_ZERO = "R502"
    LEVERAGE_EXCEEDS_LIMIT = "R503"
    POSITION_SIZE_EXCEEDS_LIMIT = "R504"
    
    # Context factory errors (6xx)
    CONTEXT_FACTORY_MISSING_FIELD = "R601"
    CONTEXT_FACTORY_TYPE_ERROR = "R602"
    CONTEXT_FACTORY_ENUM_UNKNOWN = "R603"
    CONTEXT_FACTORY_TIMESTAMP_INVALID = "R604"
    
    # Strategy runtime errors (7xx)
    STRATEGY_CRASH = "R701"
    STRATEGY_TIMEOUT = "R702"
    STRATEGY_INVALID_RETURN = "R703"
    
    # Validator internal errors (8xx)
    VALIDATOR_INTERNAL_ERROR = "R801"
    VALIDATOR_CHAIN_BROKEN = "R802"
    
    # Runner internal errors (9xx)
    RUNNER_INTERNAL_ERROR = "R901"
    RUNNER_CONTEXT_CREATION_FAILED = "R902"


class RejectMetadata(NamedTuple):
    """Metadata for each reject code."""
    code: RejectCode
    severity: RejectSeverity
    recoverable: bool  # Can strategy fix this in next tick?
    audit_level: str   # "debug" | "info" | "warning" | "error" | "critical"
    description: str


# Immutable metadata catalog
REJECT_METADATA = {
    # Protocol violations
    RejectCode.PROTOCOL_VERSION_MISMATCH: RejectMetadata(
        code=RejectCode.PROTOCOL_VERSION_MISMATCH,
        severity=RejectSeverity.CRITICAL,
        recoverable=False,
        audit_level="critical",
        description="Strategy protocol version does not match runner protocol version",
    ),
    RejectCode.PROTOCOL_SCHEMA_INVALID: RejectMetadata(
        code=RejectCode.PROTOCOL_SCHEMA_INVALID,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent does not conform to StrategyIntent schema",
    ),
    RejectCode.PROTOCOL_TYPE_ERROR: RejectMetadata(
        code=RejectCode.PROTOCOL_TYPE_ERROR,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent field has incorrect type",
    ),
    
    # Traceability violations
    RejectCode.CORRELATION_ID_MISMATCH: RejectMetadata(
        code=RejectCode.CORRELATION_ID_MISMATCH,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent correlation_id does not match governance correlation_id",
    ),
    RejectCode.CORRELATION_ID_MISSING: RejectMetadata(
        code=RejectCode.CORRELATION_ID_MISSING,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent missing required correlation_id",
    ),
    RejectCode.INTENT_ID_FORMAT_INVALID: RejectMetadata(
        code=RejectCode.INTENT_ID_FORMAT_INVALID,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent ID format invalid (expected 16-char hex)",
    ),
    RejectCode.INTENT_ID_MISSING: RejectMetadata(
        code=RejectCode.INTENT_ID_MISSING,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent missing required intent_id",
    ),
    RejectCode.TIMESTAMP_INVALID: RejectMetadata(
        code=RejectCode.TIMESTAMP_INVALID,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent timestamp is invalid (not positive integer)",
    ),
    RejectCode.TIMESTAMP_MISMATCH: RejectMetadata(
        code=RejectCode.TIMESTAMP_MISMATCH,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Intent timestamp does not match governance timestamp",
    ),
    
    # Governance blocks
    RejectCode.GOVERNANCE_REDUCE_ONLY: RejectMetadata(
        code=RejectCode.GOVERNANCE_REDUCE_ONLY,
        severity=RejectSeverity.WARNING,
        recoverable=True,
        audit_level="warning",
        description="Governance in reduce-only mode, ENTRY intents blocked",
    ),
    RejectCode.GOVERNANCE_NO_NEW_ENTRIES: RejectMetadata(
        code=RejectCode.GOVERNANCE_NO_NEW_ENTRIES,
        severity=RejectSeverity.WARNING,
        recoverable=True,
        audit_level="warning",
        description="Governance disallows new entries",
    ),
    RejectCode.GOVERNANCE_RISK_STATE_BLACK: RejectMetadata(
        code=RejectCode.GOVERNANCE_RISK_STATE_BLACK,
        severity=RejectSeverity.CRITICAL,
        recoverable=True,
        audit_level="critical",
        description="Risk state BLACK, all trading blocked",
    ),
    RejectCode.GOVERNANCE_RISK_STATE_RED: RejectMetadata(
        code=RejectCode.GOVERNANCE_RISK_STATE_RED,
        severity=RejectSeverity.WARNING,
        recoverable=True,
        audit_level="warning",
        description="Risk state RED, new entries blocked",
    ),
    RejectCode.GOVERNANCE_EMERGENCY_OVERRIDE: RejectMetadata(
        code=RejectCode.GOVERNANCE_EMERGENCY_OVERRIDE,
        severity=RejectSeverity.CRITICAL,
        recoverable=True,
        audit_level="critical",
        description="Emergency override active, all intents blocked",
    ),
    
    # Intent semantics violations
    RejectCode.ENTRY_MISSING_EXIT_PLAN: RejectMetadata(
        code=RejectCode.ENTRY_MISSING_EXIT_PLAN,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="ENTRY intent missing required exit_plan",
    ),
    RejectCode.EXIT_PLAN_EMPTY: RejectMetadata(
        code=RejectCode.EXIT_PLAN_EMPTY,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Exit plan defined but has no exit conditions",
    ),
    RejectCode.ENTRY_MISSING_SYMBOL: RejectMetadata(
        code=RejectCode.ENTRY_MISSING_SYMBOL,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="ENTRY intent missing required symbol",
    ),
    RejectCode.ENTRY_MISSING_DIRECTION: RejectMetadata(
        code=RejectCode.ENTRY_MISSING_DIRECTION,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="ENTRY intent missing required direction",
    ),
    RejectCode.ENTRY_MISSING_SIZE: RejectMetadata(
        code=RejectCode.ENTRY_MISSING_SIZE,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="ENTRY intent missing required size (size_base or size_quote)",
    ),
    RejectCode.EXIT_MISSING_SYMBOL: RejectMetadata(
        code=RejectCode.EXIT_MISSING_SYMBOL,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="EXIT intent missing required symbol",
    ),
    RejectCode.NOOP_MISSING_RATIONALE: RejectMetadata(
        code=RejectCode.NOOP_MISSING_RATIONALE,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="NOOP intent missing required rationale",
    ),
    RejectCode.CONFIDENCE_OUT_OF_RANGE: RejectMetadata(
        code=RejectCode.CONFIDENCE_OUT_OF_RANGE,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Confidence must be in range [0.0, 1.0]",
    ),
    
    # Money sanity violations
    RejectCode.SIZE_NEGATIVE: RejectMetadata(
        code=RejectCode.SIZE_NEGATIVE,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Position size cannot be negative",
    ),
    RejectCode.SIZE_ZERO: RejectMetadata(
        code=RejectCode.SIZE_ZERO,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Position size cannot be zero",
    ),
   RejectCode.LEVERAGE_EXCEEDS_LIMIT: RejectMetadata(
        code=RejectCode.LEVERAGE_EXCEEDS_LIMIT,
        severity=RejectSeverity.WARNING,
        recoverable=False,
        audit_level="warning",
        description="Requested leverage exceeds governance limit",
    ),
    RejectCode.POSITION_SIZE_EXCEEDS_LIMIT: RejectMetadata(
        code=RejectCode.POSITION_SIZE_EXCEEDS_LIMIT,
        severity=RejectSeverity.WARNING,
        recoverable=False,
        audit_level="warning",
        description="Requested position size exceeds governance limit",
    ),
    
    # Context factory errors
    RejectCode.CONTEXT_FACTORY_MISSING_FIELD: RejectMetadata(
        code=RejectCode.CONTEXT_FACTORY_MISSING_FIELD,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Required field missing in raw context data",
    ),
    RejectCode.CONTEXT_FACTORY_TYPE_ERROR: RejectMetadata(
        code=RejectCode.CONTEXT_FACTORY_TYPE_ERROR,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Field type mismatch in raw context data",
    ),
    RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN: RejectMetadata(
        code=RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Unknown enum value in raw context data",
    ),
    RejectCode.CONTEXT_FACTORY_TIMESTAMP_INVALID: RejectMetadata(
        code=RejectCode.CONTEXT_FACTORY_TIMESTAMP_INVALID,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Timestamp value invalid or out of range",
    ),
    
    # Strategy runtime errors
    RejectCode.STRATEGY_CRASH: RejectMetadata(
        code=RejectCode.STRATEGY_CRASH,
        severity=RejectSeverity.CRITICAL,
        recoverable=True,
        audit_level="critical",
        description="Strategy raised unhandled exception",
    ),
    RejectCode.STRATEGY_TIMEOUT: RejectMetadata(
        code=RejectCode.STRATEGY_TIMEOUT,
        severity=RejectSeverity.WARNING,
        recoverable=True,
        audit_level="warning",
        description="Strategy execution exceeded time limit",
    ),
    RejectCode.STRATEGY_INVALID_RETURN: RejectMetadata(
        code=RejectCode.STRATEGY_INVALID_RETURN,
        severity=RejectSeverity.ERROR,
        recoverable=False,
        audit_level="error",
        description="Strategy returned invalid type (expected StrategyIntent)",
    ),
    
    # Validator internal errors
    RejectCode.VALIDATOR_INTERNAL_ERROR: RejectMetadata(
        code=RejectCode.VALIDATOR_INTERNAL_ERROR,
        severity=RejectSeverity.CRITICAL,
        recoverable=False,
        audit_level="critical",
        description="Validator encountered internal error",
    ),
    RejectCode.VALIDATOR_CHAIN_BROKEN: RejectMetadata(
        code=RejectCode.VALIDATOR_CHAIN_BROKEN,
        severity=RejectSeverity.CRITICAL,
        recoverable=False,
        audit_level="critical",
        description="Validation chain interrupted unexpectedly",
    ),
    
    # Runner internal errors
    RejectCode.RUNNER_INTERNAL_ERROR: RejectMetadata(
        code=RejectCode.RUNNER_INTERNAL_ERROR,
        severity=RejectSeverity.CRITICAL,
        recoverable=False,
        audit_level="critical",
        description="Runner encountered internal error",
    ),
    RejectCode.RUNNER_CONTEXT_CREATION_FAILED: RejectMetadata(
        code=RejectCode.RUNNER_CONTEXT_CREATION_FAILED,
        severity=RejectSeverity.CRITICAL,
        recoverable=False,
        audit_level="critical",
        description="Failed to create execution context from raw data",
    ),
}


def get_metadata(code: RejectCode) -> RejectMetadata:
    """Get metadata for a reject code."""
    return REJECT_METADATA[code]
