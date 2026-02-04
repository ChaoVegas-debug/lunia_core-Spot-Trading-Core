"""
AI Gateway: Main Service

Multi-provider LLM service with institutional governance.

HARD CONSTRAINTS:
- AI Kill Switch (ai_global_enabled flag)
- Budget enforcement (daily + per-signal caps)
- 2s timeout (fail-fast)
- Circuit breaker (5 failures → 60s cooldown)
- Privacy scrubbing (mandatory)
- Schema validation (fail-closed)
- NO execution authority

PHASE 8.0 ADDITIONS:
- Global AI kill switch (checked FIRST)
- BudgetGovernor (persistent DB tracking)
- Cost accounting (every attempt logged)
- Fail-closed on budget errors
"""
import asyncio
import json
import time
import hashlib
import logging
from typing import Dict, Optional
from datetime import datetime

from ..execution_journal.models import AIAnalysis, AIInferenceLog, SignalEvent, AIEventType
from ..execution_journal.budget_model import AIBudgetUsage
from ..auth.database import SessionLocal

from .circuit_breaker import CircuitBreaker
from .privacy import privacy_scrub
from .schema import validate_ai_analysis, get_schema_version
from .providers import AbstractProvider
from .providers.mock import MockProvider
from .governance import AIGovernanceConfig, load_default_config
from .budget import BudgetGovernor

logger = logging.getLogger(__name__)


class AIGatewayService:
    """
    AI Gateway Service - Synthetic Advisor Layer
    
    Orchestrates LLM inference with governance constraints.
    """
    
    def __init__(
        self,
        provider: Optional[AbstractProvider] = None,
        timeout_seconds: float = 2.0,
        shadow_mode: bool = True,
        governance_config: Optional[AIGovernanceConfig] = None,
        db_session: Optional[any] = None
    ):
        """
        Initialize AI Gateway.
        
        Args:
            provider: LLM provider (default: MockProvider for testing)
            timeout_seconds: Hard timeout for inference (default: 2s)
            shadow_mode: If True, AI outputs not shown to operator
            governance_config: Governance config (default: load_default_config())
            db_session: Database session for budget tracking
        """
        self.provider = provider or MockProvider()
        self.timeout_seconds = timeout_seconds
        self.shadow_mode = shadow_mode
        
        # PHASE 8.0: Governance config (kill switch, budget limits)
        self.governance_config = governance_config or load_default_config()
        logger.info(f"AIGateway initialized: {self.governance_config.sanitized_repr()}")
        
        # PHASE 8.0: Budget Governor (persistent DB tracking)
        self.db_session = db_session or SessionLocal()
        self.budget_governor = BudgetGovernor(self.db_session, self.governance_config)
        
        # Circuit breaker: 5 failures → open for 60s
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.governance_config.circuit_breaker_failures,
            timeout_seconds=self.governance_config.circuit_breaker_reset_seconds
        )
        
        # System constitution hash (for provenance)
        self.constitution_hash = self._compute_constitution_hash()
    
    def _compute_constitution_hash(self) -> str:
        """Compute SHA256 hash of system constitution (AI behavioral law)."""
        # For now, use a placeholder
        # TODO: Load from prompts/system_constitution.md and hash
        constitution_text = "Phase 7 AI Constitution v1.0"
        return hashlib.sha256(constitution_text.encode()).hexdigest()
    
    async def analyze_signal(
        self,
        signal_event: SignalEvent,
        context: Dict
    ) -> Optional[AIAnalysis]:
        """
        Analyze signal with AI (SECONDARY intelligence).
        
        Args:
            signal_event: SignalEvent from Execution Journal
            context: Full system context (from ContextEngine)
        
        Returns:
            AIAnalysis if successful, None if failed (fail-closed)
            
        PHASE 8.0 GOVERNANCE:
        - CHECK 1: AI Kill Switch (ai_global_enabled)
        - CHECK 2: Budget Governor (daily + per-signal caps)
        - CHECK 3: Circuit Breaker
        - ... then existing Phase 7 logic
        """
        # ===== PHASE 8.0: CHECK 1 - AI KILL SWITCH =====
        if not self.governance_config.ai_global_enabled:
            logger.warning("AI_DISABLED_BY_GOVERNANCE (kill switch OFF)")
            self._log_blocked_attempt(
                context=context,
                reason="kill_switch",
                estimated_cost_usd=0.0
            )
            return None
        
        # ===== PHASE 8.0: CHECK 2 - BUDGET GOVERNOR =====
        estimated_cost = self._estimate_cost(context)
        can_proceed, budget_reason = self.budget_governor.can_attempt(
            estimated_cost_usd=estimated_cost,
            provider=self.provider.get_provider_name(),
            model=getattr(self.provider, 'model', None)
        )
        
        if not can_proceed:
            logger.warning(f"AI_BLOCKED_BY_BUDGET: {budget_reason}")
            self._log_blocked_attempt(
                context=context,
                reason=budget_reason,
                estimated_cost_usd=estimated_cost
            )
            
            # Force fallback if configured
            if not self.governance_config.hard_stop_on_budget_exceed:
                self.budget_governor.force_fallback_provider(reason=budget_reason)
            
            return None
        
        # ===== PHASE 7: CHECK 3 - CIRCUIT BREAKER =====
        if not self.circuit_breaker.can_execute():
            self._log_inference(
                event_type=AIEventType.AI_CIRCUIT_BREAKER_OPEN,
                context=context,
                response_valid=False,
                validation_error="Circuit breaker OPEN",
                estimated_cost_usd=estimated_cost
            )
            return None
        
        start_time = time.time()
        
        try:
            # Privacy scrubbing (MANDATORY)
            safe_context = privacy_scrub(context)
            
            # Build prompt
            prompt = self._build_prompt(signal_event, safe_context)
            
            # LLM inference with hard timeout
            response = await asyncio.wait_for(
                self.provider.complete(prompt, safe_context),
                timeout=self.timeout_seconds
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Parse JSON response
            try:
                analysis_dict = json.loads(response.content)
            except json.JSONDecodeError:
                self.circuit_breaker.record_failure()
                self._log_inference(
                    event_type=AIEventType.AI_VALIDATION_FAILED,
                    context=safe_context,
                    response_valid=False,
                    validation_error="Invalid JSON"
                )
                return None
            
            # Schema validation (FAIL-CLOSED)
            validated = validate_ai_analysis(analysis_dict)
            if not validated:
                self.circuit_breaker.record_failure()
                self._log_inference(
                    event_type=AIEventType.AI_VALIDATION_FAILED,
                    context=safe_context,
                    response_valid=False,
                    validation_error="Schema validation failed"
                )
                return None
            
            # Build AIAnalysis model
            analysis = AIAnalysis(
                signal_event_id=signal_event.id,
                model_revision=response.model,
                reasoning_version=validated["reasoning_version"],
                ai_constitution_hash=self.constitution_hash,
                summary=validated["summary"],
                risk_flags=validated["risk_flags"],
                confirmation=validated["confirmation"],
                confidence_score=validated["confidence_score"],
                confidence_reason=validated.get("confidence_reason"),
                conflicts_with_core=validated["conflicts_with_core"],
                conflict_reason=validated.get("conflict_reason"),
                invalid_if=validated.get("invalid_if"),
                latency_ms=latency_ms,
                cost_usd=response.cost_usd
            )
            
            # PHASE 8.0: Record actual cost to budget
            actual_cost = response.cost_usd
            self.budget_governor.record_attempt(
                date=datetime.utcnow().date(),
                provider=self.provider.get_provider_name(),
                model=response.model,
                tokens_prompt=response.prompt_tokens,
                tokens_completion=response.completion_tokens,
                cost_usd=actual_cost
            )
            
            # Log successful inference
            self._log_inference(
                event_type=AIEventType.AI_INFERENCE,
                context=safe_context,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_cost_usd=actual_cost,
                latency_ms=latency_ms,
                provider=self.provider.get_provider_name(),
                model_name=response.model,
                response_valid=True,
                estimated_cost_usd=estimated_cost
            )
            
            self.circuit_breaker.record_success()
            return analysis
            
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            self._log_inference(
                event_type=AIEventType.AI_TIMEOUT,
                context=context,
                response_valid=False,
                validation_error=f"Timeout after {self.timeout_seconds}s"
            )
            return None
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            self._log_inference(
                event_type=AIEventType.AI_INFERENCE,
                context=context,
                response_valid=False,
                validation_error=str(e)
            )
            return None
    
    def _build_prompt(self, signal_event: SignalEvent, context: Dict) -> str:
        """
        Build LLM prompt from signal and context.
        
        Args:
            signal_event: Signal to analyze
            context: System context
        
        Returns:
            Formatted prompt string
        """
        return f"""You are an institutional trading system advisor.

CRITICAL: You have NO execution authority. Your role is to provide SECONDARY analysis of deterministic signals.

SYSTEM CONTEXT:
{json.dumps(context, indent=2)}

DETERMINISTIC SIGNAL (Core Decision):
Strategy: {signal_event.strategy_id}
Symbol: {signal_event.symbol}
Type: {signal_event.signal_type.value}
Confidence: {signal_event.confidence}
Reasoning: {signal_event.deterministic_reasoning}

YOUR TASK:
Analyze this deterministic signal and provide structured JSON response.

REQUIRED OUTPUT (strict JSON schema):
{{
  "summary": "Brief analysis (max 500 chars)",
  "risk_flags": ["risk1", "risk2"],
  "confirmation": true/false (do you agree with core?),
  "confidence_score": 0.0-1.0,
  "confidence_reason": "Why this confidence level",
  "conflicts_with_core": true/false,
  "conflict_reason": "If conflicts, explain why",
  "invalid_if": ["condition1", "condition2"],
  "reasoning_version": "core_v7.0",
  "model_revision": "{self.provider.model}"
}}

RESPOND WITH ONLY JSON, NO PROSE.
"""
    
    def _estimate_cost(self, context: Dict) -> float:
        """
        Estimate USD cost for inference (BEFORE calling LLM).
        
        PHASE 8.0: Used for budget pre-check.
        
        Args:
            context: System context dict
            
        Returns:
            Estimated USD cost (conservative, may overestimate)
        """
        # Very rough estimate: assume 500 prompt + 200 completion tokens
        # At ~$0.01/1K tokens (GPT-4-turbo pricing)
        # Total: ~0.007 USD per inference
        
        # MockProvider = $0.00
        if isinstance(self.provider, MockProvider):
            return 0.0
        
        # Real providers: conservative estimate
        estimated_tokens = 700
        cost_per_1k_tokens = 0.01  # Conservative
        return (estimated_tokens / 1000.0) * cost_per_1k_tokens
    
    def _log_blocked_attempt(
        self,
        context: Dict,
        reason: str,
        estimated_cost_usd: float
    ):
        """
        Log blocked AI attempt (PHASE 8.0).
        
        Even blocked attempts are audited.
        
        Args:
            context: System context
            reason: Block reason (kill_switch, budget, etc.)
            estimated_cost_usd: What it would have cost
        """
        db = SessionLocal()
        try:
            log_entry = AIInferenceLog(
                event_type=AIEventType.AI_BLOCKED,
                context_snapshot=context,
                prompt_tokens=0,
                completion_tokens=0,
                total_cost_usd=0.0,  # Not actually spent
                latency_ms=0,
                provider=self.provider.get_provider_name(),
                model_name=getattr(self.provider, 'model', 'unknown'),
                response_valid=False,
                validation_error=f"Blocked: {reason} (est. cost=${estimated_cost_usd:.4f})",
                shadow_mode=self.shadow_mode
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log blocked attempt: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _log_inference(
        self,
        event_type: AIEventType,
        context: Dict,
        response_valid: bool = False,
        validation_error: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_cost_usd: float = 0.0,
        latency_ms: int = 0,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        estimated_cost_usd: float = 0.0  # PHASE 8.0
    ):
        """Log AI inference to database (immutable audit trail)."""
        db = SessionLocal()
        try:
            log_entry = AIInferenceLog(
                event_type=event_type,
                context_snapshot=context,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost_usd=total_cost_usd,
                latency_ms=latency_ms,
                provider=provider,
                model_name=model_name,
                response_valid=response_valid,
                validation_error=validation_error,
                shadow_mode=self.shadow_mode
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log inference: {e}")
            db.rollback()
        finally:
            db.close()
