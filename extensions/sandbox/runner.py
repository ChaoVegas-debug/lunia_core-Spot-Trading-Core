"""
PHASE 9.2 + 9.3 — STRATEGY RUNNER

Deterministic tick executor with fail-closed exception containment.

PHASE 9.2: Validation pipeline + audit trail
PHASE 9.3: Paper execution + cost reality + cooldown

GUARANTEES:
- Strategy exceptions contained (runner never crashes)
- All ticks produce auditable outcomes
- Rejected intents replaced with safe NOOP
- Paper execution with cost reality (fees, spread, slippage, latency)
- TTL enforcement + cooldown management
- Full audit trail generated
"""

import traceback
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    GovernanceContext,
    MarketSnapshot,
    ShadowPortfolio,
    IntentType,
)
from extensions.sandbox.context_factory import ContextFactory, ContextFactoryError
from extensions.sandbox.validator import ValidationChain, ValidationResult
from extensions.sandbox.audit_store import AuditStore, create_audit_event
from extensions.sandbox.reject_codes import RejectCode, get_metadata
# Phase 9.3 imports
from extensions.sandbox.paper_executor import PaperExecutor
from extensions.sandbox.cooldown_manager import CooldownManager
from extensions.sandbox.paper_types import TradeOutcome


@dataclass
class TickResult:
    """Result of a single tick execution."""
    correlation_id: str
    run_id: str
    ts_ms: int
    
    # Final intent (may be original or safe NOOP if rejected)
    final_intent: StrategyIntent
    
    # Validation result
    validation_result: ValidationResult
    
    # Was the original intent replaced?
    was_replaced: bool
    
    # Strategy execution error (if any)
    strategy_error: Optional[str] = None
    
    # Audit events generated during this tick
    audit_event_ids: List[str] = None
    
    # Phase 9.3: Paper execution outcome
    paper_outcome: Optional[TradeOutcome] = None
    
    def __post_init__(self):
        if self.audit_event_ids is None:
            self.audit_event_ids = []


class StrategyRunner:
    """
    Fail-closed strategy runner.
    
    SPEC IMPROVEMENT: Injectable clock for deterministic testing.
    """
    
    def __init__(
        self,
        strategy: Any,  # Strategy with generate_intent method
        audit_store: AuditStore,
        clock: Optional[Callable[[], int]] = None,
        enable_paper_execution: bool = True,  # Phase 9.3
    ):
        """
        Initialize runner.
        
        Args:
            strategy: Strategy instance (must have generate_intent method)
            audit_store: Audit store for event logging
            clock: Optional clock function for testing
            enable_paper_execution: Enable Phase 9.3 paper execution (default: True)
        """
        self._strategy = strategy
        self._audit_store = audit_store
        self._context_factory = ContextFactory(clock=clock)
        self._validator = ValidationChain()
        self._clock = clock or (lambda: int(__import__('time').time() * 1000))
        
        # Phase 9.3: Paper execution + cooldown
        self._enable_paper_execution = enable_paper_execution
        if self._enable_paper_execution:
            self._paper_executor = PaperExecutor(audit_store=audit_store)
            self._cooldown_manager = CooldownManager()
        else:
            self._paper_executor = None
            self._cooldown_manager = None
    
    def tick(
        self,
        raw_market: Dict[str, Any],
        raw_portfolio: Dict[str, Any],
        raw_governance: Dict[str, Any],
    ) -> TickResult:
        """
        Execute one tick: context creation → strategy → validation → audit.
        
        GUARANTEE: Runner never crashes. All errors contained and audited.
        
        Args:
            raw_market: Raw market data dict
            raw_portfolio: Raw portfolio data dict
            raw_governance: Raw governance data dict
            
        Returns:
            TickResult with final intent and audit trail
        """
        ts_ms = self._clock()
        correlation_id = None
        run_id = None
        audit_event_ids = []
        
        try:
            # Step 1: Create contexts (fail-closed)
            try:
                governance = self._context_factory.create_governance_context(raw_governance)
                market = self._context_factory.create_market_snapshot(raw_market)
                portfolio = self._context_factory.create_shadow_portfolio(raw_portfolio)
                
                correlation_id = governance.correlation_id
                run_id = governance.run_id
                ts_ms = governance.ts_ms
                
            except ContextFactoryError as e:
                # Context creation failed => create minimal safe NOOP
                correlation_id = raw_governance.get("correlation_id", f"corr_error_{ts_ms}")
                run_id = raw_governance.get("run_id", f"run_error_{ts_ms}")
                
                # Audit context failure
                event = create_audit_event(
                    ts_ms=ts_ms,
                    event_type="context_creation_failed",
                    correlation_id=correlation_id,
                    run_id=run_id,
                    payload={
                        "error": str(e),
                        "reject_code": e.reject_code.value,
                    },
                    reject_code=e.reject_code.value,
                    severity="critical",
                )
                self._audit_store.append(event)
                audit_event_ids.append(event.event_id)
                
                # Return safe fallback
                safe_intent = self._create_safe_noop(
                    correlation_id=correlation_id,
                    ts_ms=ts_ms,
                    run_id=run_id,
                    reason=f"Context creation failed: {e}",
                )
                
                return TickResult(
                    correlation_id=correlation_id,
                    run_id=run_id,
                    ts_ms=ts_ms,
                    final_intent=safe_intent,
                    validation_result=ValidationResult.reject(
                        RejectCode.RUNNER_CONTEXT_CREATION_FAILED,
                        str(e)
                    ),
                    was_replaced=True,
                    strategy_error=f"Context creation error: {e}",
                    audit_event_ids=audit_event_ids,
                )
            
            # Audit tick start
            tick_start_event = create_audit_event(
                ts_ms=ts_ms,
                event_type="tick_start",
                correlation_id=correlation_id,
                run_id=run_id,
                payload={
                    "symbol": market.symbol,
                    "mid_price": market.mid,
                    "risk_state": governance.risk_state.value,
                },
            )
            self._audit_store.append(tick_start_event)
            audit_event_ids.append(tick_start_event.event_id)
            
            # Step 2: Execute strategy (contained)
            intent = None
            strategy_error = None
            
            try:
                # SPEC IMPROVEMENT: Match reference_noop.py signature
                intent = self._strategy.generate_intent(
                    governance=governance,
                    portfolio=portfolio,
                    markets=[market],  # List of markets
                )
                
                # Validate return type
                if not isinstance(intent, StrategyIntent):
                    raise TypeError(f"Strategy returned {type(intent)}, expected StrategyIntent")
                
                # Audit intent generated
                intent_event = create_audit_event(
                    ts_ms=ts_ms,
                    event_type="intent_generated",
                    correlation_id=correlation_id,
                    run_id=run_id,
                    payload={
                        "intent_type": intent.intent_type.value,
                        "strategy_id": intent.strategy_id,
                    },
                    strategy_id=intent.strategy_id,
                    intent_id=intent.intent_id,
                )
                self._audit_store.append(intent_event)
                audit_event_ids.append(intent_event.event_id)
                
            except Exception as e:
                # Strategy crashed => create safe NOOP
                strategy_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                
                # Audit crash
                crash_event = create_audit_event(
                    ts_ms=ts_ms,
                    event_type="strategy_crashed",
                    correlation_id=correlation_id,
                    run_id=run_id,
                    payload={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                    reject_code=RejectCode.STRATEGY_CRASH.value,
                    severity="critical",
                )
                self._audit_store.append(crash_event)
                audit_event_ids.append(crash_event.event_id)
                
                # Create safe NOOP
                intent = self._create_safe_noop(
                    correlation_id=correlation_id,
                    ts_ms=ts_ms,
                    run_id=run_id,
                    reason=f"Strategy crashed: {type(e).__name__}",
                )
            
            # Step 3: Phase 9.3 cooldown pre-check (before validation)
            cooldown_blocked = False
            if self._enable_paper_execution and self._cooldown_manager:
                if intent.intent_type == IntentType.ENTRY:
                    can_enter, cooldown_reason = self._cooldown_manager.can_enter(
                        intent.strategy_id, ts_ms
                    )
                    if not can_enter:
                        cooldown_blocked = True
                        # Audit cooldown block
                        cooldown_event = create_audit_event(
                            ts_ms=ts_ms,
                            event_type="cooldown_blocked_entry",
                            correlation_id=correlation_id,
                            run_id=run_id,
                            payload={"reason": cooldown_reason},
                            intent_id=intent.intent_id,
                            strategy_id=intent.strategy_id,
                        )
                        self._audit_store.append(cooldown_event)
                        audit_event_ids.append(cooldown_event.event_id)
                        
                        # Replace with safe NOOP
                        intent = self._create_safe_noop(
                            correlation_id=correlation_id,
                            ts_ms=ts_ms,
                            run_id=run_id,
                            reason=f"Cooldown blocked: {cooldown_reason}",
                        )
            
            # Step 4: Validate intent
            validation_result = self._validator.validate(intent, governance)
            
            # Audit validation result
            validation_event = create_audit_event(
                ts_ms=ts_ms,
                event_type="intent_validated",
                correlation_id=correlation_id,
                run_id=run_id,
                payload={
                    "is_valid": validation_result.is_valid,
                    "reject_code": validation_result.reject_code.value if validation_result.reject_code else None,
                    "reason": validation_result.reason,
                },
                intent_id=intent.intent_id,
                reject_code=validation_result.reject_code.value if validation_result.reject_code else None,
                severity=get_metadata(validation_result.reject_code).severity.value if validation_result.reject_code else "info",
            )
            self._audit_store.append(validation_event)
            audit_event_ids.append(validation_event.event_id)
            
            # Step 5: If rejected, replace with safe NOOP
            final_intent = intent
            was_replaced = cooldown_blocked or False
            
            if not validation_result.is_valid:
                # Replace with safe NOOP
                final_intent = self._create_safe_noop(
                    correlation_id=correlation_id,
                    ts_ms=ts_ms,
                    run_id=run_id,
                    reason=f"Intent rejected: {validation_result.reason}",
                )
                was_replaced = True
                
                # Audit replacement
                replace_event = create_audit_event(
                    ts_ms=ts_ms,
                    event_type="intent_replaced_with_noop",
                    correlation_id=correlation_id,
                    run_id=run_id,
                    payload={
                        "original_intent_id": intent.intent_id,
                        "fallback_intent_id": final_intent.intent_id,
                        "reject_code": validation_result.reject_code.value,
                        "reason": validation_result.reason,
                    },
                    intent_id=final_intent.intent_id,
                    reject_code=validation_result.reject_code.value,
                )
                self._audit_store.append(replace_event)
                audit_event_ids.append(replace_event.event_id)
            
            # Step 6: Phase 9.3 paper execution
            paper_outcome = None
            if self._enable_paper_execution and self._paper_executor:
                paper_outcome = self._paper_executor.on_tick(
                    intent=final_intent,
                    governance=governance,
                    market=market,
                    now_ts_ms=ts_ms,
                )
                
                # If outcome created, register with cooldown manager
                if paper_outcome and self._cooldown_manager:
                    self._cooldown_manager.register_outcome(paper_outcome)
            
            # Audit tick end
            tick_end_event = create_audit_event(
                ts_ms=ts_ms,
                event_type="tick_end",
                correlation_id=correlation_id,
                run_id=run_id,
                payload={
                    "final_intent_type": final_intent.intent_type.value,
                    "final_intent_id": final_intent.intent_id,
                    "was_replaced": was_replaced,
                },
                intent_id=final_intent.intent_id,
            )
            self._audit_store.append(tick_end_event)
            audit_event_ids.append(tick_end_event.event_id)
            
            return TickResult(
                correlation_id=correlation_id,
                run_id=run_id,
                ts_ms=ts_ms,
                final_intent=final_intent,
                validation_result=validation_result,
                was_replaced=was_replaced,
                strategy_error=strategy_error,
                audit_event_ids=audit_event_ids,
                paper_outcome=paper_outcome,  # Phase 9.3
            )
        
        except Exception as e:
            # Runner internal error (should never happen, but fail-safe)
            error_msg = f"Runner internal error: {e}\n{traceback.format_exc()}"
            
            # Try to create minimal safe state
            if correlation_id is None:
                correlation_id = f"corr_runner_error_{ts_ms}"
            if run_id is None:
                run_id = f"run_runner_error_{ts_ms}"
            
            # Audit runner error
            try:
                error_event = create_audit_event(
                    ts_ms=ts_ms,
                    event_type="runner_internal_error",
                    correlation_id=correlation_id,
                    run_id=run_id,
                    payload={
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                    reject_code=RejectCode.RUNNER_INTERNAL_ERROR.value,
                    severity="critical",
                )
                self._audit_store.append(error_event)
                audit_event_ids.append(error_event.event_id)
            except:
                pass  # Even audit failed, give up gracefully
            
            # Return minimal safe result
            safe_intent = self._create_safe_noop(
                correlation_id=correlation_id,
                ts_ms=ts_ms,
                run_id=run_id,
                reason="Runner internal error",
            )
            
            return TickResult(
                correlation_id=correlation_id,
                run_id=run_id,
                ts_ms=ts_ms,
                final_intent=safe_intent,
                validation_result=ValidationResult.reject(
                    RejectCode.RUNNER_INTERNAL_ERROR,
                    error_msg
                ),
                was_replaced=True,
                strategy_error=error_msg,
                audit_event_ids=audit_event_ids,
            )
    
    def _create_safe_noop(
        self,
        correlation_id: str,
        ts_ms: int,
        run_id: str,
        reason: str,
    ) -> StrategyIntent:
        """
        Create a safe NOOP intent as fallback.
        
        GUARANTEE: Always valid under protocol rules.
        """
        import hashlib
        
        # Deterministic intent_id
        intent_id = hashlib.sha256(
            f"{correlation_id}:{ts_ms}:safe_noop:{reason}".encode('utf-8')
        ).hexdigest()[:16]
        
        return StrategyIntent(
            intent_id=intent_id,
            ts_ms=ts_ms,
            protocol_version=PROTOCOL_VERSION,
            correlation_id=correlation_id,
            intent_type=IntentType.NOOP,
            direction=None,
            symbol=None,
            size_base=None,
            size_quote=None,
            exit_plan=None,
            confidence=1.0,
            rationale=f"SAFE FALLBACK: {reason} (run_id={run_id})",
            strategy_id="runner_safe_fallback",
            strategy_frequency=__import__('extensions.protocol.protocol', fromlist=['StrategyFrequency']).StrategyFrequency.POSITION,
            is_hedge=False,
            is_scaling=False,
        )
