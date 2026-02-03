"""
PHASE 9.2 — INTENT VALIDATOR

Chain-of-Responsibility validator for fail-closed intent validation.

SPEC IMPROVEMENT:
- Intent_id format must match Protocol v1.0.1 (16-char hex)
- Never raise uncaught exceptions (all errors => ValidationResult.reject)

GUARANTEES:
- Validation chain order is explicit and enforced
- All rejections include stable RejectCode
- Invalid intent => explicit reject (fail-closed)
"""

import re
from dataclasses import dataclass
from typing import Optional, List
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    GovernanceContext,
    IntentType,
    RiskState,
)
from extensions.sandbox.reject_codes import RejectCode, get_metadata


@dataclass
class ValidationResult:
    """Result of intent validation."""
    is_valid: bool
    reject_code: Optional[RejectCode] = None
    reason: Optional[str] = None
    
    @classmethod
    def accept(cls) -> "ValidationResult":
        """Create accepted result."""
        return cls(is_valid=True)
    
    @classmethod
    def reject(cls, code: RejectCode, reason: str) -> "ValidationResult":
        """Create rejected result."""
        return cls(is_valid=False, reject_code=code, reason=reason)


class Validator:
    """Base validator interface."""
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        """
        Validate intent.
        
        MUST NOT raise exceptions (fail-closed: exception => reject).
        
        Args:
            intent: Intent to validate
            governance: Governance context
            
        Returns:
            ValidationResult (accept or reject)
        """
        raise NotImplementedError


class ProtocolValidator(Validator):
    """
    Validates protocol version and schema presence.
    
    Chain position: 1 (first)
    """
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        try:
            # Protocol version must match exactly
            if intent.protocol_version != PROTOCOL_VERSION:
                return ValidationResult.reject(
                    RejectCode.PROTOCOL_VERSION_MISMATCH,
                    f"Intent protocol_version '{intent.protocol_version}' != '{PROTOCOL_VERSION}'"
                )
            
            # Basic schema presence (dataclass should enforce this, but double-check)
            if not hasattr(intent, 'intent_type'):
                return ValidationResult.reject(
                    RejectCode.PROTOCOL_SCHEMA_INVALID,
                    "Intent missing intent_type field"
                )
            
            if not hasattr(intent, 'correlation_id'):
                return ValidationResult.reject(
                    RejectCode.PROTOCOL_SCHEMA_INVALID,
                    "Intent missing correlation_id field"
                )
            
            return ValidationResult.accept()
        
        except Exception as e:
            # Fail-closed: any exception => reject
            return ValidationResult.reject(
                RejectCode.VALIDATOR_INTERNAL_ERROR,
                f"ProtocolValidator internal error: {e}"
            )


class TraceabilityValidator(Validator):
    """
    Validates correlation_id match, intent_id format, and timestamps.
    
    Chain position: 2
    
    SPEC IMPROVEMENT: Intent_id format is 16-char hex (from protocol.py).
    """
    
    # SPEC IMPROVEMENT: 16-char hex pattern from reference_noop.py
    INTENT_ID_PATTERN = re.compile(r'^[0-9a-f]{16}$')
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        try:
            # Correlation ID must match governance
            if intent.correlation_id != governance.correlation_id:
                return ValidationResult.reject(
                    RejectCode.CORRELATION_ID_MISMATCH,
                    f"Intent correlation_id '{intent.correlation_id}' != governance '{governance.correlation_id}'"
                )
            
            # Intent ID must be present
            if not intent.intent_id:
                return ValidationResult.reject(
                    RejectCode.INTENT_ID_MISSING,
                    "Intent intent_id is empty"
                )
            
            # Intent ID must be 16-char hex (SPEC IMPROVEMENT)
            if not self.INTENT_ID_PATTERN.match(intent.intent_id):
                return ValidationResult.reject(
                    RejectCode.INTENT_ID_FORMAT_INVALID,
                    f"Intent intent_id '{intent.intent_id}' must be 16-char hex"
                )
            
            # Timestamp must be valid
            if not isinstance(intent.ts_ms, int) or intent.ts_ms <= 0:
                return ValidationResult.reject(
                    RejectCode.TIMESTAMP_INVALID,
                    f"Intent timestamp '{intent.ts_ms}' is invalid"
                )
            
            # Timestamp must match governance (MVP: strict matching)
            if intent.ts_ms != governance.ts_ms:
                return ValidationResult.reject(
                    RejectCode.TIMESTAMP_MISMATCH,
                    f"Intent ts_ms '{intent.ts_ms}' != governance '{governance.ts_ms}'"
                )
            
            return ValidationResult.accept()
        
        except Exception as e:
            return ValidationResult.reject(
                RejectCode.VALIDATOR_INTERNAL_ERROR,
                f"TraceabilityValidator internal error: {e}"
            )


class GovernanceValidator(Validator):
    """
    Validates governance constraints (reduce_only, risk_state, etc.).
    
    Chain position: 3
    """
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        try:
            # Emergency override blocks everything
            if governance.emergency_override_active:
                # Only NOOP is allowed
                if intent.intent_type != IntentType.NOOP:
                    return ValidationResult.reject(
                        RejectCode.GOVERNANCE_EMERGENCY_OVERRIDE,
                        "Emergency override active, all non-NOOP intents blocked"
                    )
            
            # Risk state BLACK blocks everything except NOOP
            if governance.risk_state == RiskState.BLACK:
                if intent.intent_type != IntentType.NOOP:
                    return ValidationResult.reject(
                        RejectCode.GOVERNANCE_RISK_STATE_BLACK,
                        "Risk state BLACK, all trading blocked"
                    )
            
            # Risk state RED blocks new entries
            if governance.risk_state == RiskState.RED:
                if intent.intent_type == IntentType.ENTRY:
                    return ValidationResult.reject(
                        RejectCode.GOVERNANCE_RISK_STATE_RED,
                        "Risk state RED, new entries blocked"
                    )
            
            # Reduce-only mode blocks new entries
            if governance.is_reduce_only:
                if intent.intent_type == IntentType.ENTRY:
                    return ValidationResult.reject(
                        RejectCode.GOVERNANCE_REDUCE_ONLY,
                        "Reduce-only mode, ENTRY intents blocked"
                    )
            
            # allow_new_entries flag
            if not governance.allow_new_entries:
                if intent.intent_type == IntentType.ENTRY:
                    return ValidationResult.reject(
                        RejectCode.GOVERNANCE_NO_NEW_ENTRIES,
                        "Governance disallows new entries"
                    )
            
            return ValidationResult.accept()
        
        except Exception as e:
            return ValidationResult.reject(
                RejectCode.VALIDATOR_INTERNAL_ERROR,
                f"GovernanceValidator internal error: {e}"
            )


class IntentSemanticsValidator(Validator):
    """
    Validates intent-specific semantics (ENTRY must have exit_plan, etc.).
    
    Chain position: 4
    """
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        try:
            intent_type = intent.intent_type
            
            # ENTRY validation
            if intent_type == IntentType.ENTRY:
                # Must have exit_plan
                if intent.exit_plan is None:
                    return ValidationResult.reject(
                        RejectCode.ENTRY_MISSING_EXIT_PLAN,
                        "ENTRY intent must include exit_plan"
                    )
                
                # Exit plan must have at least one condition
                ep = intent.exit_plan
                has_condition = any([
                    ep.stop_loss_price is not None,
                    ep.stop_loss_pct is not None,
                    ep.take_profit_price is not None,
                    ep.take_profit_pct is not None,
                    ep.time_limit_ms is not None,
                    ep.trail_start_pct is not None,
                ])
                if not has_condition:
                    return ValidationResult.reject(
                        RejectCode.EXIT_PLAN_EMPTY,
                        "Exit plan must define at least one exit condition"
                    )
                
                # Must have symbol
                if not intent.symbol:
                    return ValidationResult.reject(
                        RejectCode.ENTRY_MISSING_SYMBOL,
                        "ENTRY intent must specify symbol"
                    )
                
                # Must have direction
                if intent.direction is None:
                    return ValidationResult.reject(
                        RejectCode.ENTRY_MISSING_DIRECTION,
                        "ENTRY intent must specify direction"
                    )
                
                # Must have size
                if intent.size_base is None and intent.size_quote is None:
                    return ValidationResult.reject(
                        RejectCode.ENTRY_MISSING_SIZE,
                        "ENTRY intent must specify size_base or size_quote"
                    )
            
            # EXIT validation
            elif intent_type == IntentType.EXIT:
                if not intent.symbol:
                    return ValidationResult.reject(
                        RejectCode.EXIT_MISSING_SYMBOL,
                        "EXIT intent must specify symbol"
                    )
            
            # NOOP validation
            elif intent_type == IntentType.NOOP:
                if not intent.rationale or not intent.rationale.strip():
                    return ValidationResult.reject(
                        RejectCode.NOOP_MISSING_RATIONALE,
                        "NOOP intent must include non-empty rationale"
                    )
            
            # Confidence validation (all intent types)
            if not (0.0 <= intent.confidence <= 1.0):
                return ValidationResult.reject(
                    RejectCode.CONFIDENCE_OUT_OF_RANGE,
                    f"Confidence {intent.confidence} must be in [0.0, 1.0]"
                )
            
            return ValidationResult.accept()
        
        except Exception as e:
            return ValidationResult.reject(
                RejectCode.VALIDATOR_INTERNAL_ERROR,
                f"IntentSemanticsValidator internal error: {e}"
            )


class MoneySanityValidator(Validator):
    """
    Validates basic money sanity (non-negative sizes, limits).
    
    Chain position: 5 (last)
    
    MVP: Minimal checks only (no portfolio math in Phase 9.2).
    """
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        try:
            # Size validation for ENTRY intents
            if intent.intent_type == IntentType.ENTRY:
                # Size must be positive
                if intent.size_base is not None:
                    if intent.size_base < 0:
                        return ValidationResult.reject(
                            RejectCode.SIZE_NEGATIVE,
                            f"size_base cannot be negative: {intent.size_base}"
                        )
                    if intent.size_base == 0:
                        return ValidationResult.reject(
                            RejectCode.SIZE_ZERO,
                            "size_base cannot be zero"
                        )
                
                if intent.size_quote is not None:
                    if intent.size_quote < 0:
                        return ValidationResult.reject(
                            RejectCode.SIZE_NEGATIVE,
                            f"size_quote cannot be negative: {intent.size_quote}"
                        )
                    if intent.size_quote == 0:
                        return ValidationResult.reject(
                            RejectCode.SIZE_ZERO,
                            "size_quote cannot be zero"
                        )
            
            return ValidationResult.accept()
        
        except Exception as e:
            return ValidationResult.reject(
                RejectCode.VALIDATOR_INTERNAL_ERROR,
                f"MoneySanityValidator internal error: {e}"
            )


class ValidationChain:
    """
    Chain-of-Responsibility validator.
    
    GUARANTEE: Validators execute in strict order.
    """
    
    def __init__(self):
        # SPEC IMPROVEMENT: Explicit validator order
        self._validators: List[Validator] = [
            ProtocolValidator(),
            TraceabilityValidator(),
            GovernanceValidator(),
            IntentSemanticsValidator(),
            MoneySanityValidator(),
        ]
    
    def validate(
        self,
        intent: StrategyIntent,
        governance: GovernanceContext,
    ) -> ValidationResult:
        """
        Run full validation chain.
        
        Stops at first rejection (fail-fast within chain).
        
        Args:
            intent: Intent to validate
            governance: Governance context
            
        Returns:
            ValidationResult (first rejection or final accept)
        """
        try:
            for validator in self._validators:
                result = validator.validate(intent, governance)
                if not result.is_valid:
                    return result  # Fail-fast
            
            return ValidationResult.accept()
        
        except Exception as e:
            # Fail-closed: any chain error => reject
            return ValidationResult.reject(
                RejectCode.VALIDATOR_CHAIN_BROKEN,
                f"Validation chain error: {e}"
            )
