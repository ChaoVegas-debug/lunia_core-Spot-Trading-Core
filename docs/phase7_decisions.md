# Phase 7: Architectural Decisions Log

**Date**: February 4, 2026  
**Purpose**: Document key architectural choices and rationale

---

## Decision 1: Mock Provider Only (No Real LLM Integrations)

**Context**: Phase 7.2 requires multi-provider LLM support (OpenAI, Anthropic, local).

**Decision**: Implement ONLY MockProvider for now. Real providers (OpenAI/Anthropic) deferred.

**Rationale**:

1. **No API Keys**: Production deployment requires secure key management (Vault, AWS Secrets Manager)
2. **Cost Control**: Real LLM calls incur cost. Mock provider enables testing without expense.
3. **Core Architecture First**: AI Gateway, circuit breaker, schema validation can be proven with mock.
4. **Fast Iteration**: Mock provider returns immediately, enabling rapid testing.

**Implementation**:

- MockProvider returns deterministic responses based on signal type
- Zero latency (configurable, default 100ms)
- Zero cost
- Valid JSON conforming to `AI_ANALYSIS_SCHEMA`

**Future Work**:

- Add OpenAIProvider (requires `OPENAI_API_KEY` env var)
- Add AnthropicProvider (requires `ANTHROPIC_API_KEY` env var)
- Add cost limit guards before production use

**Status**: ✅ RESOLVED (mock provider sufficient for Phase 7 foundation)

---

## Decision 2: Context Engine Fallback for ops_state

**Context**: ContextEngine needs current ops_state (mode, trading_on, global_stop, etc.)

**Decision**: Implement `_get_ops_state_fallback()` with safe defaults instead of importing actual ops_state module.

**Rationale**:

1. **Circular Import Risk**: ops_state module may import other services, could create cycle
2. **Safe Defaults**: Fallback returns `{mode: "MANUAL", trading_on: False, global_stop: True}`
3. **Fail-Safe**: If ops_state unavailable, fallback prevents crash
4. **TODO Marker**: Code includes `# TODO: Import actual get_ops_state()` for future integration

**Implementation**:

```python
def _get_ops_state_fallback(self) -> Dict:
    try:
        # TODO: from lunia_core.app.core.ops_state import get_ops_state
        # return get_ops_state()
        pass
    except Exception:
        pass
    
    return {
        "system_mode": "MANUAL",
        "trading_on": False,
        "global_stop": True,
        ...
    }
```

**Future Work**:

- Import actual ops_state module after confirming no circular dependencies
- Test with real ops_state values
- Update tests to verify context accuracy

**Status**: ✅ RESOLVED (fallback prevents blocker, TODO marked for production)

---

## Decision 3: Schema Validation as Fail-Closed

**Context**: AI outputs must conform to strict JSON schema. What happens if validation fails?

**Decision**: FAIL-CLOSED — discard invalid outputs entirely.

**Rationale**:

1. **Safety First**: Invalid AI output could mislead operator
2. **Circuit Breaker Integration**: Validation failures count toward circuit breaker threshold
3. **Audit Trail**: All failures logged to `ai_inference_logs` with validation_error
4. **No Partial Trust**: Either output is fully valid or not used at all

**Alternatives Considered**:

- **Partial schema** (accept some fields): Rejected — too error-prone
- **Best-effort parsing**: Rejected — violates fail-closed principle
- **Retry with different prompt**: Rejected — adds latency

**Implementation**:

```python
validated = validate_ai_analysis(analysis_dict)
if not validated:
    self.circuit_breaker.record_failure()
    self._log_inference(..., response_valid=False)
    return None  # Discard
```

**Status**: ✅ RESOLVED (fail-closed safer than best-effort)

---

## Decision 4: Shadow Mode Default = True

**Context**: Should AI outputs be shown to operator immediately or gated?

**Decision**: Shadow Mode = `True` by default. AI outputs NOT shown to operator until validated.

**Rationale**:

1. **Prove First**: AI system must prove reliability before influencing decisions
2. **Metrics Collection**: Shadow mode enables latency/cost/hallucination measurement without risk
3. **Governance Requirement**: Phase 7 Master Prompt mandates Shadow Mode as first state
4. **Exit Criteria**: Clear thresholds (100 inferences, p99 < 1.5s, hallucination < 5%)

**Implementation**:

- `AIGatewayService.__init__(shadow_mode=True)`
- All inferences logged with `shadow_mode` flag
- UI queries filter: `WHERE shadow_mode = False` (only show non-shadow outputs)

**Future Work**:

- Implement Shadow Mode toggle in UI (operator control)
- Add dashboard showing shadow metrics (latency, cost, hallucinations)
- Create operator runbook for exiting Shadow Mode

**Status**: ✅ RESOLVED (shadow mode default enforced)

---

## Decision 5: No OpenAI/Anthropic Providers Yet

**Context**: Production use requires real LLM providers.

**Decision**: Defer OpenAI/Anthropic provider implementation to future phase.

**Rationale**:

1. **Cost Control**: Real LLM calls cost money. Need budget/approval first.
2. **Key Management**: Secure API key storage requires infrastructure (Vault, env var encryption)
3. **Rate Limiting**: Production providers need rate limit handling we haven't built yet
4. **Mock Sufficient**: Can test entire architecture with MockProvider

**Future Work** (Phase 7.X):

- Implement OpenAIProvider:
  - Use `openai` Python library
  - Load `OPENAI_API_KEY` from secure vault
  - Handle rate limits (429 responses)
  - Implement token estimation for cost control

- Implement AnthropicProvider:
  - Use `anthropic` Python library
  - Load `ANTHROPIC_API_KEY`
  - Map Anthropic response format to LLMResponse

**Status**: ✅ RESOLVED (defer to future phase, mark as TODO)

---

## Decision 6: Circuit Breaker Threshold = 5 Failures

**Context**: How many consecutive failures before opening circuit?

**Decision**: Threshold = 5 consecutive failures, cooldown = 60 seconds.

**Rationale**:

1. **Not Too Sensitive**: 1-2 failures could be transient network issues
2. **Not Too Lenient**: 10+ failures wastes time and cost
3. **Industry Standard**: Many circuit breakers use 5 as default threshold
4. **Configurable**: Threshold is constructor parameter, can be tuned

**Implementation**:

```python
CircuitBreaker(failure_threshold=5, timeout_seconds=60)
```

**Future Work**:

- Monitor circuit breaker metrics in production
- Tune threshold based on observed failure patterns
- Consider exponential backoff for cooldown

**Status**: ✅ RESOLVED (5 failures, 60s cooldown)

---

## Decision 7: Hard Timeout = 2 Seconds

**Context**: How long to wait for LLM response before failing?

**Decision**: Hard timeout = 2.0 seconds.

**Rationale**:

1. **Phase 7 Master Prompt Requirement**: "<2s hard limit" explicitly mandated
2. **Operator Experience**: Longer timeouts degrade UX (UI feels slow)
3. **Fail-Fast**: 2s is long enough for most LLM calls, but short enough to prevent hangs
4. **Configurable**: Service constructor accepts `timeout_seconds` parameter

**Implementation**:

```python
response = await asyncio.wait_for(
    self.provider.complete(prompt, context),
    timeout=2.0
)
```

**Timeout Behavior**:

- Timeout exceeded → `asyncio.TimeoutError` caught
- Circuit breaker records failure
- Log event type: `AI_TIMEOUT`
- Return `None` (fail-closed)

**Status**: ✅ RESOLVED (2s hard timeout enforced)

---

## Decision 8: Execution Journal = Single Table for Signal Reasoning

**Context**: Should deterministic reasoning be in SignalEvent or separate table?

**Decision**: Include `deterministic_reasoning` TEXT field directly in `SignalEvent` model.

**Rationale**:

1. **1:1 Relationship**: Every signal has exactly one deterministic reasoning
2. **Simpler Query**: No JOIN needed to get signal + reasoning
3. **Atomic Write**: Signal and reasoning inserted together
4. **Read Performance**: Faster for UI display (no extra table lookup)

**Alternatives Considered**:

- **Separate SignalReasoning table**: Rejected — adds complexity for no benefit
- **JSON field in market_context**: Rejected — reasoning is not market data

**Implementation**:

```python
class SignalEvent(Base):
    ...
    deterministic_reasoning = Column(Text)  # Core logic explanation
```

**Status**: ✅ RESOLVED (single table simpler and faster)

---

## Summary

**Total Decisions**: 8  
**Status**: All RESOLVED  
**Next Review**: After Phase 7.4 (UI implementation)

---

**Document Version**: 1.0  
**Last Updated**: February 4, 2026
