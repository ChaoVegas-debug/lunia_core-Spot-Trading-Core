# Phase 7: Synthetic Advisor Architecture

**Date**: February 4, 2026  
**Version**: 1.0  
**Commits**: 29f96a6 (foundation), 61a40bb (AI Gateway + Context Engine)

---

## Executive Summary

Phase 7 implements a **Synthetic Advisor Layer** to make deterministic trading intelligence legible, auditable, and governed. This is NOT adding intelligence — it's revealing existing intelligence through structured AI analysis.

**Core Principle**: AI has ZERO execution authority. All AI outputs are SECONDARY.

---

## Architecture Overview

```
                        ┌─────────────────────────────────────────┐
                        │   DETERMINISTIC CORE (Phase 1-6)       │
                        │   Strategies, Risk Engine, PLN          │
                        └──────────────┬──────────────────────────┘
                                       │
                                       │ SIGNAL_GENERATED event
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   EXECUTION JOURNAL                     │
                        │   SignalEvent (immutable record)        │
                        │   + deterministic_reasoning             │
                        └──────────────┬──────────────────────────┘
                                       │
                                       │ Trigger AI analysis
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   CONTEXT ENGINE (RAG-lite)             │
                        │   Aggregates: system state, market      │
                        │   state, signal reasoning, freshness    │
                        └──────────────┬──────────────────────────┘
                                       │
                                       │ Complete context
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   AI GATEWAY                            │
                        │   Privacy Scrub → LLM → Schema Validate │
                        │   Circuit Breaker, 2s timeout           │
                        └──────────────┬──────────────────────────┘
                                       │
                                       │ AIAnalysis (if valid)
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   AI AIRLOCK (Governance)               │
                        │   Log to ai_inference_logs              │
                        │   Check conflicts_with_core             │
                        │   Shadow Mode filter                    │
                        └──────────────┬──────────────────────────┘
                                       │
                                       │ (if NOT shadow_mode)
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   UI: SignalsWidget + AdvisorWidget     │
                        │   Display: deterministic + AI reasoning │
                        │   Operator feedback: 👍 / 👎            │
                        └─────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Execution Journal (`/app/services/execution_journal/`)

**Purpose**: Persistent, immutable record of signal generation and reasoning

**Models**:

- **SignalEvent**: Captures what deterministic core decided
  - Fields: strategy_id, symbol, signal_type, confidence, market_context, risk_filters_applied, deterministic_reasoning
  - Invariants: NO UPDATE, replayable, time-bound

- **AIAnalysis**: AI interpretation (1:1 with SignalEvent)
  - Fields: summary, risk_flags, confirmation, conflicts_with_core, operator_feedback
  - Provenance: model_revision, reasoning_version, constitution_hash

- **AIInferenceLog**: Append-only audit trail
  - Fields: context_snapshot, tokens, cost, latency, shadow_mode
  - Use: Cost tracking, hallucination metrics, governance

**Database**: Alembic migration `004_add_execution_journal` creates 3 tables, 13 indexes

---

### 2. AI Gateway (`/app/services/ai_gateway/`)

**Purpose**: Govern LLM interactions with institutional constraints

**Components**:

#### AIGatewayService (`service.py`)

- Orchestrates: Privacy scrub → LLM → Schema validation → Audit log
- Hard timeout: 2 seconds (fail-fast)
- Returns: AIAnalysis or None (fail-closed)

#### Circuit Breaker (`circuit_breaker.py`)

- States: CLOSED | OPEN | HALF_OPEN
- Failure threshold: 5 consecutive failures
- Cooldown: 60 seconds
- Thread-safe with Lock

#### Privacy Scrubber (`privacy.py`)

- Removes: API keys, secrets, credentials, long hashes
- Recursive dict scrubbing
- Validation: `validate_scrubbed()` checks for residual patterns

#### Schema Validator (`schema.py`)

- Hard contract: `AI_ANALYSIS_SCHEMA`
- Required fields: summary, risk_flags, confirmation, confidence_score, conflicts_with_core, reasoning_version, model_revision
- Fail-closed: Invalid outputs discarded entirely

#### Provider Architecture (`providers/`)

- AbstractProvider interface
- MockProvider (testing, no external calls)
- Future: OpenAIProvider, AnthropicProvider (requires API keys)

---

### 3. Context Engine (`/app/services/ai_gateway/context_engine.py`)

**Purpose**: RAG-lite state aggregation to prevent hallucinations

**Context Structure**:

```json
{
  "system_time": "ISO-8601 UTC",
  "system_state": {
    "mode": "MANUAL | AUTO | STOP",
    "trading_on": bool,
    "global_stop": bool,
    "global_age_seconds": int
  },
  "market_state": {
    "symbol": "BTCUSDT",
    "context": {...},
    "regime": "TRENDING | RANGING | ..."
  },
  "signal": {
    "type": "BUY | SELL | HOLD",
    "confidence": 0.0-1.0,
    "strategy_id": "...",
    "deterministic_reasoning": "..."
  },
  "recent_events": [...],
  "pulse_freshness": {...}
}
```

**Principle**: LLM sees the SAME state as operator (via timestamped snapshot)

---

## Governance Constraints

### 1. AI Authority = ZERO

Code enforcement:

- AI Gateway has NO imports to: `ops_state` setter, order execution, strategy mutation
- All AI outputs marked as SECONDARY in UI when `conflicts_with_core = True`

### 2. Shadow Mode (Mandatory First State)

Default: `shadow_mode = True`

In Shadow Mode:

- AI analysis generated and logged
- Metrics collected (latency, cost, hallucination)
- NO UI display
- NO operator influence

Exit criteria:

- 100+ inferences logged
- Latency p99 < 1.5s
- Hallucination rate < 5%
- Cost/signal < $0.01
- Operator approval

### 3. Fail-Closed Semantics

Every failure mode defaults to SAFE:

- Schema validation fails → Discard output
- Timeout exceeded → Return None
- Circuit breaker OPEN → Reject request
- Privacy scrub finds sensitive data → Redact

### 4. Immutable Audit Trail

All AI inferences logged to `ai_inference_logs`:

- Context snapshot (full system state)
- Tokens and cost
- Latency
- Validation result
- Shadow mode flag

NO UPDATE or DELETE allowed (append-only).

---

## Operational Metrics

### Performance Targets

| Metric | Target | Enforcement |
|:-------|:-------|:------------|
| Latency p50 | < 1.0s | Hard timeout at 2s |
| Latency p99 | < 1.5s | Circuit breaker after 5 failures |
| Cost per signal | < $0.01 (shadow) | Logged, monitored |
| Hallucination rate | < 5% | Operator feedback (👍/👎) |

### Cost Accounting

Every inference logs:

- Prompt tokens
- Completion tokens
- Total cost USD
- Provider and model

Aggregation queries:

```sql
-- Daily cost
SELECT DATE(timestamp), SUM(total_cost_usd)
FROM ai_inference_logs
GROUP BY DATE(timestamp);

-- Hallucination rate
SELECT 
  COUNT(*) FILTER (WHERE operator_feedback = 'thumbs_down') / COUNT(*) AS hallucination_rate
FROM ai_analysis
WHERE operator_feedback IS NOT NULL;
```

---

## Security Model

### 1. Privacy Scrubbing

Before external LLM call:

- Recursive dict scan for sensitive patterns
- Redact: `api_key`, `secret`, `password`, `token`, long hashes
- Validation: `validate_scrubbed()` confirms no leaks

### 2. Zero Trust

AI outputs are UNTRUSTED until:

- Schema validation passes
- Provenance verified
- Logged to immutable audit trail

### 3. Operator Oversight

Operator can:

- View all AI inferences (via TraceDrawer)
- Mark hallucinations (thumbs down feedback)
- Enable/disable Shadow Mode
- Review circuit breaker state

---

## Future Extensions

### Phase 7.5+ (Not Implemented)

- **OpenAI/Anthropic Providers**: Production LLM integrations
- **UI Surfaces**: AdvisorWidget, Signals Widget upgrade
- **Strategy Generation**: AI-assisted strategy ideation (governance-gated)
- **Alert Summarization**: Natural language digest of system events
- **Conversational Interface**: Operator chat with system state

All future extensions MUST comply with Article I (Zero Execution Authority).

---

## Files Modified/Created

| File | Purpose | Lines |
|:-----|:--------|------:|
| `lunia_core/app/services/execution_journal/models.py` | Journal models | 240 |
| `lunia_core/alembic/versions/004_add_execution_journal.py` | Migration | 140 |
| `lunia_core/app/services/ai_gateway/service.py` | Main AI Gateway | 280 |
| `lunia_core/app/services/ai_gateway/circuit_breaker.py` | Fail-fast logic | 90 |
| `lunia_core/app/services/ai_gateway/privacy.py` | Sensitive data scrubbing | 95 |
| `lunia_core/app/services/ai_gateway/schema.py` | JSON validation | 75 |
| `lunia_core/app/services/ai_gateway/context_engine.py` | RAG-lite aggregator | 105 |
| `lunia_core/app/services/ai_gateway/providers/mock.py` | Test provider | 60 |
| `prompts/system_constitution.md` | AI behavioral law | 200 |

**Total**: 9 core files, ~1,285 lines

---

## References

- [Phase 7 Master Prompt (LEVEL 11+)](../docs/phase7_master_prompt.md)
- [AI System Constitution](../prompts/system_constitution.md)
- [Execution Journal Models](../lunia_core/app/services/execution_journal/models.py)
- [AI Gateway Service](../lunia_core/app/services/ai_gateway/service.py)

---

**Architecture Status**: ✅ **Phase 7.1-7.3 COMPLETE**  
**Next**: Phase 7.4 (UI surfaces), Phase 7.5 (End-to-end testing)
