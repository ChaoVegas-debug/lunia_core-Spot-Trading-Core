"""
AI Gateway: Tiered Router (Phase 8.1B)

Intelligent routing between FAST and DEEP AI paths.

FAST PATH: Quick triage (<400ms, gpt-4o-mini, cheap)
DEEP PATH: Contextual reasoning (<2s, gpt-4-turbo, expensive)

CRITICAL INVARIANTS:
- Router executes AFTER gates (Kill Switch → BudgetGovernor → CircuitBreaker)
- Two-stage budget enforcement (FAST then DEEP)
- Cost avoidance metric (cost_saved_usd when FAST rejects)
- Fail-operational (fallback to Mock if all paths fail)
- NO provider retries in router (provider handles retries)
"""

import asyncio
import logging
import os
import time
from typing import Dict, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass

from .governance import AIGovernanceConfig
from .budget import BudgetGovernor
from .providers import AbstractProvider, get_provider
from .providers.mock import MockProvider
from .tokenization import estimate_prompt_and_completion, TIKTOKEN_AVAILABLE
from .cost import estimate_cost
from .secrets import redact_sensitive

logger = logging.getLogger(__name__)


class RoutingMode(Enum):
    """Router operating modes."""
    FAST_ONLY = "fast_only"           # Only use FAST path
    FAST_THEN_DEEP = "fast_then_deep" # FAST, escalate to DEEP if needed
    DEEP_ONLY = "deep_only"           # Only use DEEP path (requires approval)


class FastVerdict(Enum):
    """FAST path verdict."""
    APPROVE = "APPROVE"   # Signal OK, no DEEP needed
    REJECT = "REJECT"     # Signal invalid, block
    ESCALATE = "ESCALATE" # Ambiguous, needs DEEP


@dataclass
class RouterMetadata:
    """Router execution metadata (audit trail)."""
    router_enabled: bool
    routing_mode: str
    path_taken: str  # "FAST" | "DEEP" | "FAST_THEN_DEEP" | "MOCK_FALLBACK" | "BLOCKED"
    
    # FAST path
    fast_model: Optional[str] = None
    fast_latency_ms: Optional[int] = None
    fast_cost_est: Optional[float] = None
    fast_cost_actual: Optional[float] = None
    fast_verdict: Optional[str] = None
    fast_confidence: Optional[float] = None
    
    # DEEP path
    deep_model: Optional[str] = None
    deep_latency_ms: Optional[int] = None
    deep_cost_est: Optional[float] = None
    deep_cost_actual: Optional[float] = None
    deep_confidence: Optional[float] = None
    
    # Escalation
    escalation_reason: Optional[str] = None
    escalation_triggered: bool = False
    
    # Cost avoidance
    cost_saved_usd: Optional[float] = None  # When FAST rejects, avoid DEEP cost
    
    # Final decision
    final_decision_source: str = "UNKNOWN"  # "FAST" | "DEEP" | "MOCK"
    
    # Block reason (canonical AI_BLOCKED metadata)
    block_reason: Optional[str] = None  # e.g., "dependency_missing_tiktoken", "invalid_routing_mode"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for logging (with redaction)."""
        return redact_sensitive({
            "router_enabled": self.router_enabled,
            "routing_mode": self.routing_mode,
            "path_taken": self.path_taken,
            "fast_model": self.fast_model,
            "fast_latency_ms": self.fast_latency_ms,
            "fast_cost_est": self.fast_cost_est,
            "fast_cost_actual": self.fast_cost_actual,
            "fast_verdict": self.fast_verdict,
            "fast_confidence": self.fast_confidence,
            "deep_model": self.deep_model,
            "deep_latency_ms": self.deep_latency_ms,
            "deep_cost_est": self.deep_cost_est,
            "deep_cost_actual": self.deep_cost_actual,
            "deep_confidence": self.deep_confidence,
            "escalation_reason": self.escalation_reason,
            "escalation_triggered": self.escalation_triggered,
            "cost_saved_usd": self.cost_saved_usd,
            "final_decision_source": self.final_decision_source,
            "block_reason": self.block_reason,
        })


class TieredRouter:
    """
    Intelligent router for AI Gateway.
    
    Routes requests between FAST (cheap triage) and DEEP (expensive reasoning).
    
    GATE ORDER (SACRED, DO NOT MODIFY):
    1. Kill Switch (external, before router)
    2. BudgetGovernor (external, before router)
    3. CircuitBreaker (external, before router)
    4. Router (this class)
    5. Provider (FAST or DEEP)
    """
    
    def __init__(
        self,
        governance_config: AIGovernanceConfig,
        budget_governor: BudgetGovernor
    ):
        """
        Initialize Tiered Router.
        
        Args:
            governance_config: Governance configuration
            budget_governor: Budget governor (for per-stage budget checks)
        """
        self.governance_config = governance_config
        self.budget_governor = budget_governor
        
        # Router config (loaded from governance_config extensions)
        self.enabled = getattr(governance_config, 'enable_tiered_router', False)
        self.routing_mode = getattr(
            governance_config,
            'routing_mode',
            RoutingMode.FAST_ONLY.value
        )
        
        # FAST path config
        self.fast_model = getattr(governance_config, 'fast_path_model', 'gpt-4o-mini')
        self.fast_timeout_ms = getattr(governance_config, 'fast_path_timeout_ms', 400)
        self.fast_max_tokens = getattr(governance_config, 'fast_path_max_completion_tokens', 100)
        
        # DEEP path config
        self.deep_model = getattr(governance_config, 'deep_path_model', 'gpt-4-turbo')
        self.deep_timeout_ms = getattr(governance_config, 'deep_path_timeout_ms', 2000)
        self.deep_max_tokens = getattr(governance_config, 'deep_path_max_completion_tokens', 400)
        
        # Escalation config
        self.ambiguity_band = getattr(
            governance_config,
            'escalate_ambiguity_band',
            [0.45, 0.70]
        )
        self.critical_reason_codes = getattr(
            governance_config,
            'escalate_critical_codes',
            ["CONFLICTING_SIGNAL", "HIGH_VOLATILITY"]
        )
        
        # PROD tiktoken rule
        self.production_requires_tiktoken = getattr(
            governance_config,
            'production_requires_tiktoken',
            True
        )
        
        logger.info(
            f"TieredRouter init: enabled={self.enabled}, mode={self.routing_mode}, "
            f"FAST={self.fast_model}, DEEP={self.deep_model}"
        )
    
    async def route(
        self,
        prompt: str,
        context: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], RouterMetadata]:
        """
        Route AI request through FAST and/or DEEP paths.
        
        Args:
            prompt: AI prompt (scrubbed)
            context: Request context (scrubbed)
        
        Returns:
            (analysis_result, router_metadata)
            analysis_result can be None if all paths fail (fail-closed)
        
        GATE ORDERING REMINDER:
        This method is called AFTER:
        - Kill Switch check
        - BudgetGovernor.can_attempt() check
        - CircuitBreaker check
        
        DO NOT re-check these gates here.
        """
        metadata = RouterMetadata(
            router_enabled=self.enabled,
            routing_mode=self.routing_mode,
            path_taken="UNKNOWN"
        )
        
        # If router disabled, behave like Phase 8.1A (linear)
        if not self.enabled:
            logger.debug("Router disabled, using linear path")
            metadata.path_taken = "LINEAR"
            # TODO: Implement linear fallback (STEP 3+)
            return None, metadata
        
        # Check tiktoken PROD rule (LOCKED LAW)
        is_production = (os.getenv("ENVIRONMENT", "development").lower() == "production")
        
        if is_production and self.production_requires_tiktoken and not TIKTOKEN_AVAILABLE:
            logger.error(
                "PRODUCTION + tiktoken missing: AI BLOCKED. Fail-operational to MockProvider. "
                "Install: pip install tiktoken"
            )
            
            # Fail-operational: Use MockProvider
            mock_provider = MockProvider()
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "dependency_missing_tiktoken"
            
            # Execute mock provider (returns deterministic response)
            try:
                mock_result = await mock_provider.complete(prompt, context)
                # Parse mock response (will be deterministic)
                import json
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
        
        # Route based on mode
        if self.routing_mode == RoutingMode.FAST_ONLY.value:
            return await self._route_fast_only(prompt, context, metadata)
        elif self.routing_mode == RoutingMode.FAST_THEN_DEEP.value:
            return await self._route_fast_then_deep(prompt, context, metadata)
        elif self.routing_mode == RoutingMode.DEEP_ONLY.value:
            return await self._route_deep_only(prompt, context, metadata)
        else:
            logger.error(f"Unknown routing mode: {self.routing_mode}")
            metadata.path_taken = "ERROR"
            metadata.block_reason = "invalid_routing_mode"
            return None, metadata
    
    async def _route_fast_only(
        self,
        prompt: str,
        context: Dict[str, Any],
        metadata: RouterMetadata
    ) -> Tuple[Optional[Dict[str, Any]], RouterMetadata]:
        """
        Execute FAST path only.
        
        FAST PATH: Cheap triage (<400ms, gpt-4o-mini).
        Purpose: Reject noise, save DEEP cost.
        """
        import json
        start_time = time.time()
        
        # 1) FAST COST ESTIMATION (PRE-CALL)
        fast_cost_est = self._estimate_fast_cost(prompt)
        metadata.fast_cost_est = fast_cost_est
        metadata.fast_model = self.fast_model
        
        # 2) BUDGET ENFORCEMENT (MUST happen before provider call)
        can_proceed, budget_reason = self.budget_governor.can_attempt(
            estimated_cost_usd=fast_cost_est,
            provider="openai",
            model=self.fast_model
        )
        
        if not can_proceed:
            logger.warning(f"FAST path blocked by budget: {budget_reason}")
            metadata.path_taken = "FAST"
            metadata.final_decision_source = "NONE"
            metadata.block_reason = "fast_budget_blocked"
            return None, metadata
        
        # 3) FAST PROVIDER CALL
        provider = get_provider("openai", model=self.fast_model)
        
        if provider is None:
            logger.error("OpenAI provider unavailable, fallback to Mock")
            mock_provider = MockProvider()
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "provider_unavailable"
            
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
        
        # Execute FAST provider call with timeout
        try:
            timeout_sec = self.fast_timeout_ms / 1000.0
            
            response = await asyncio.wait_for(
                provider.complete(prompt, context),
                timeout=timeout_sec
            )
            
            # Measure latency
            latency_ms = int((time.time() - start_time) * 1000)
            metadata.fast_latency_ms = latency_ms
            
            # Extract actual cost from response
            if hasattr(response, 'usage') and response.usage:
                actual_cost = estimate_cost(
                    self.fast_model,
                    response.usage.get('prompt_tokens', 0),
                    response.usage.get('completion_tokens', 0)
                )
                metadata.fast_cost_actual = actual_cost
            else:
                metadata.fast_cost_actual = fast_cost_est
            
            # 4) FAST RESPONSE SCHEMA VALIDATION
            try:
                fast_result = json.loads(response.content) if hasattr(response, 'content') else {}
            except json.JSONDecodeError as e:
                logger.error(f"FAST response invalid JSON: {e}")
                metadata.path_taken = "MOCK_FALLBACK"
                metadata.final_decision_source = "MOCK"
                metadata.block_reason = "fast_invalid_json"
                
                mock_provider = MockProvider()
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            
            # Validate FAST schema
            if not self._validate_fast_schema(fast_result):
                logger.error("FAST response failed schema validation")
                metadata.path_taken = "MOCK_FALLBACK"
                metadata.final_decision_source = "MOCK"
                metadata.block_reason = "fast_invalid_schema"
                
                mock_provider = MockProvider()
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            
            # Extract FAST metadata
            metadata.fast_verdict = fast_result.get('fast_verdict')
            metadata.fast_confidence = fast_result.get('confidence_fast')
            metadata.path_taken = "FAST"
            metadata.final_decision_source = "FAST"
            
            # 5) COST AVOIDANCE METRIC (LEVEL-12 LAW)
            if metadata.fast_verdict == "REJECT":
                deep_cost_est = self._estimate_deep_cost(prompt)
                metadata.cost_saved_usd = deep_cost_est
                logger.info(f"FAST rejected signal, saved ${deep_cost_est:.4f} DEEP cost")
            
            return fast_result, metadata
            
        except asyncio.TimeoutError:
            logger.error(f"FAST path timeout ({self.fast_timeout_ms}ms exceeded)")
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "fast_timeout"
            
            mock_provider = MockProvider()
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
                
        except Exception as e:
            logger.error(f"FAST path failed: {e}")
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "fast_error"
            
            mock_provider = MockProvider()
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
    
    async def _route_fast_then_deep(
        self,
        prompt: str,
        context: Dict[str, Any],
        metadata: RouterMetadata
    ) -> Tuple[Optional[Dict[str, Any]], RouterMetadata]:
        """
        Execute FAST, escalate to DEEP if needed.
        
        STEP 5: Full FAST→DEEP flow with dual budget enforcement.
        """
        # Execute FAST path first
        fast_result, fast_metadata = await self._route_fast_only(prompt, context, metadata)
        
        # Copy FAST metadata into our metadata
        metadata = fast_metadata
        
        # Check if escalation needed
        should_escalate, escalation_reason = self._should_escalate(fast_result or {})
        
        if should_escalate:
            # Record escalation decision
            metadata.escalation_triggered = True
            metadata.escalation_reason = escalation_reason
            
            # Estimate DEEP cost
            deep_cost_est = self._estimate_deep_cost(prompt)
            metadata.deep_cost_est = deep_cost_est
            
            logger.info(f"Escalation triggered: {escalation_reason}, DEEP cost est: ${deep_cost_est:.4f}")
            
            # DUAL BUDGET ENFORCEMENT (second stage)
            can_proceed_deep, budget_reason = self.budget_governor.can_attempt(
                estimated_cost_usd=deep_cost_est,
                provider="openai",
                model=self.deep_model
            )
            
            if not can_proceed_deep:
                logger.warning(f"DEEP path blocked by budget: {budget_reason}")
                # Return FAST result, block DEEP
                metadata.path_taken = "FAST_ONLY_DUE_TO_BUDGET"
                metadata.final_decision_source = "FAST"
                metadata.block_reason = "deep_budget_blocked"
                return fast_result, metadata
            
            # Execute DEEP path
            deep_result, metadata = await self._execute_deep_path(prompt, context, metadata)
            
            # Final decision source
            if deep_result is not None:
                metadata.path_taken = "FAST_THEN_DEEP"
                metadata.final_decision_source = "DEEP"
                return deep_result, metadata
            else:
                # DEEP failed, return FAST
                metadata.path_taken = "FAST"
                metadata.final_decision_source = "FAST"
                return fast_result, metadata
        else:
            # No escalation - FAST result is final
            metadata.escalation_triggered = False
            metadata.path_taken = "FAST"
            return fast_result, metadata
    
    async def _route_deep_only(
        self,
        prompt: str,
        context: Dict[str, Any],
        metadata: RouterMetadata
    ) -> Tuple[Optional[Dict[str, Any]], RouterMetadata]:
        """
        Execute DEEP path only (requires approval).
        
        STEP 5: DEEP_ONLY mode with budget enforcement.
        """
        # Estimate DEEP cost
        deep_cost_est = self._estimate_deep_cost(prompt)
        metadata.deep_cost_est = deep_cost_est
        metadata.deep_model = self.deep_model
        
        # Budget enforcement (single check for DEEP_ONLY)
        can_proceed, budget_reason = self.budget_governor.can_attempt(
            estimated_cost_usd=deep_cost_est,
            provider="openai",
            model=self.deep_model
        )
        
        if not can_proceed:
            logger.warning(f"DEEP_ONLY path blocked by budget: {budget_reason}")
            metadata.path_taken = "DEEP"
            metadata.final_decision_source = "NONE"
            metadata.block_reason = "deep_budget_blocked"
            return None, metadata
        
        # Execute DEEP path
        deep_result, metadata = await self._execute_deep_path(prompt, context, metadata)
        
        if deep_result is not None:
            metadata.path_taken = "DEEP"
            metadata.final_decision_source = "DEEP"
        else:
            # Already handled by _execute_deep_path
            pass
        
        return deep_result, metadata
    
    async def _execute_deep_path(
        self,
        prompt: str,
        context: Dict[str, Any],
        metadata: RouterMetadata
    ) -> Tuple[Optional[Dict[str, Any]], RouterMetadata]:
        """
        Execute DEEP provider call with full governance.
        
        Returns:
            (deep_result, metadata)
        """
        import json
        start_time = time.time()
        
        # Get DEEP provider
        provider = get_provider("openai", model=self.deep_model)
        
        if provider is None:
            logger.error("OpenAI provider unavailable for DEEP, fallback to Mock")
            mock_provider = MockProvider()
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "provider_unavailable"
            
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
        
        # Execute DEEP provider call with timeout
        try:
            timeout_sec = self.deep_timeout_ms / 1000.0
            
            response = await asyncio.wait_for(
                provider.complete(prompt, context),
                timeout=timeout_sec
            )
            
            # Measure latency
            latency_ms = int((time.time() - start_time) * 1000)
            metadata.deep_latency_ms = latency_ms
            
            # Extract actual cost from response
            if hasattr(response, 'usage') and response.usage:
                actual_cost = estimate_cost(
                    self.deep_model,
                    response.usage.get('prompt_tokens', 0),
                    response.usage.get('completion_tokens', 0)
                )
                metadata.deep_cost_actual = actual_cost
                
                # Record actual cost with budget governor
                self.budget_governor.record_attempt(
                    provider="openai",
                    model=self.deep_model,
                    cost_usd=actual_cost,
                    success=True
                )
            else:
                # Use estimate if usage not available
                metadata.deep_cost_actual = metadata.deep_cost_est
            
            # Parse and validate DEEP JSON response
            try:
                deep_result = json.loads(response.content) if hasattr(response, 'content') else {}
            except json.JSONDecodeError as e:
                logger.error(f"DEEP response invalid JSON: {e}")
                metadata.path_taken = "MOCK_FALLBACK"
                metadata.final_decision_source = "MOCK"
                metadata.block_reason = "deep_invalid_json"
                
                mock_provider = MockProvider()
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            
            # Extract DEEP metadata
            metadata.deep_confidence = deep_result.get('confidence_deep', deep_result.get('confidence', 0.0))
            
            return deep_result, metadata
            
        except asyncio.TimeoutError:
            logger.error(f"DEEP path timeout ({self.deep_timeout_ms}ms exceeded)")
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "deep_timeout"
            
            mock_provider = MockProvider()
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
                
        except Exception as e:
            logger.error(f"DEEP path failed: {e}")
            metadata.path_taken = "MOCK_FALLBACK"
            metadata.final_decision_source = "MOCK"
            metadata.block_reason = "deep_error"
            
            mock_provider = MockProvider()
            try:
                mock_result = await mock_provider.complete(prompt, context)
                mock_analysis = json.loads(mock_result.content) if hasattr(mock_result, 'content') else {}
                return mock_analysis, metadata
            except Exception as e:
                logger.error(f"MockProvider fallback failed: {e}")
                return None, metadata
    
    def _validate_fast_schema(self, fast_result: Dict[str, Any]) -> bool:
        """
        Validate FAST response schema.
        
        Required fields:
        - fast_verdict: "APPROVE" | "REJECT" | "ESCALATE"
        - fast_reason_codes: list[str]
        - confidence_fast: float (0..1)
        - risk_flags_fast: list[str]
        - recommended_action_fast: str
        - notes_fast: str (≤500 chars)
        """
        required_fields = [
            "fast_verdict",
            "fast_reason_codes",
            "confidence_fast",
            "risk_flags_fast",
            "recommended_action_fast",
            "notes_fast"
        ]
        
        # Check required fields exist
        for field in required_fields:
            if field not in fast_result:
                logger.error(f"FAST schema missing required field: {field}")
                return False
        
        # Validate fast_verdict values
        valid_verdicts = ["APPROVE", "REJECT", "ESCALATE"]
        if fast_result["fast_verdict"] not in valid_verdicts:
            logger.error(f"Invalid fast_verdict: {fast_result['fast_verdict']}")
            return False
        
        # Validate confidence_fast range
        confidence = fast_result.get("confidence_fast")
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            logger.error(f"Invalid confidence_fast: {confidence}")
            return False
        
        # Validate notes_fast length
        notes = fast_result.get("notes_fast", "")
        if len(str(notes)) > 500:
            logger.error(f"notes_fast too long: {len(notes)} chars (max 500)")
            return False
        
        return True
    
    def _should_escalate(
        self,
        fast_result: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if FAST result should escalate to DEEP.
        
        Escalation triggers (EXACT):
        1) fast_verdict == "ESCALATE" → escalate
        2) confidence_fast in ambiguity_band [low, high] → escalate
        3) fast_reason_codes contains critical code → escalate
        4) fast_verdict == "REJECT" → NEVER escalate (terminal)
        
        Args:
            fast_result: FAST path result dict
        
        Returns:
            (should_escalate, escalation_reason)
        """
        fast_verdict = fast_result.get("fast_verdict")
        fast_reason_codes = fast_result.get("fast_reason_codes", [])
        confidence_fast = fast_result.get("confidence_fast", 0.0)
        
        # REJECT is terminal - never escalate
        if fast_verdict == "REJECT":
            return False, None
        
        # Trigger 1: Explicit ESCALATE verdict
        if fast_verdict == "ESCALATE":
            return True, "fast_verdict_escalate"
        
        # Trigger 2: Ambiguity band (only if FAST_THEN_DEEP mode)
        if self.routing_mode == RoutingMode.FAST_THEN_DEEP.value:
            low_threshold, high_threshold = self.ambiguity_band
            if low_threshold <= confidence_fast <= high_threshold:
                return True, "ambiguity_band"
        
        # Trigger 3: Critical reason codes
        for code in fast_reason_codes:
            if code in self.critical_reason_codes:
                return True, f"critical_reason_code:{code}"
        
        # Default: do not escalate
        return False, None
    
    def _estimate_fast_cost(self, prompt: str) -> float:
        """Estimate FAST path cost."""
        # TODO: Implement cost estimation (STEP 3)
        prompt_tokens, completion_tokens = estimate_prompt_and_completion(
            prompt,
            model=self.fast_model,
            max_completion_tokens=self.fast_max_tokens
        )
        return estimate_cost(self.fast_model, prompt_tokens, completion_tokens)
    
    def _estimate_deep_cost(self, prompt: str) -> float:
        """Estimate DEEP path cost."""
        # TODO: Implement cost estimation (STEP 3)
        prompt_tokens, completion_tokens = estimate_prompt_and_completion(
prompt,
            model=self.deep_model,
            max_completion_tokens=self.deep_max_tokens
        )
        return estimate_cost(self.deep_model, prompt_tokens, completion_tokens)


# Export public API
__all__ = [
    "TieredRouter",
    "RoutingMode",
    "FastVerdict",
    "RouterMetadata",
]
