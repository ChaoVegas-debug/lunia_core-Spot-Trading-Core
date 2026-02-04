"""
AI Gateway: Main Service

Multi-provider LLM service with institutional governance.

HARD CONSTRAINTS:
- 2s timeout (fail-fast)
- Circuit breaker (5 failures → 60s cooldown)
- Privacy scrubbing (mandatory)
- Schema validation (fail-closed)
- NO execution authority
"""
import asyncio
import json
import time
import hashlib
from typing import Dict, Optional
from datetime import datetime

from ..execution_journal.models import AIAnalysis, AIInferenceLog, SignalEvent, AIEventType
from ..auth.database import SessionLocal

from .circuit_breaker import CircuitBreaker
from .privacy import privacy_scrub
from .schema import validate_ai_analysis, get_schema_version
from .providers import AbstractProvider
from .providers.mock import MockProvider


class AIGatewayService:
    """
    AI Gateway Service - Synthetic Advisor Layer
    
    Orchestrates LLM inference with governance constraints.
    """
    
    def __init__(
        self,
        provider: Optional[AbstractProvider] = None,
        timeout_seconds: float = 2.0,
        shadow_mode: bool = True
    ):
        """
        Initialize AI Gateway.
        
        Args:
            provider: LLM provider (default: MockProvider for testing)
            timeout_seconds: Hard timeout for inference (default: 2s)
            shadow_mode: If True, AI outputs not shown to operator
        """
        self.provider = provider or MockProvider()
        self.timeout_seconds = timeout_seconds
        self.shadow_mode = shadow_mode
        
        # Circuit breaker: 5 failures → open for 60s
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        
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
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self._log_inference(
                event_type=AIEventType.AI_CIRCUIT_BREAKER_OPEN,
                context=context,
                response_valid=False,
                validation_error="Circuit breaker OPEN"
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
            
            # Log successful inference
            self._log_inference(
                event_type=AIEventType.AI_INFERENCE,
                context=safe_context,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_cost_usd=response.cost_usd,
                latency_ms=latency_ms,
                provider=self.provider.get_provider_name(),
                model_name=response.model,
                response_valid=True
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
        model_name: Optional[str] = None
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
            print(f"[AI_GATEWAY] Failed to log inference: {e}")
            db.rollback()
        finally:
            db.close()
