# AI System Constitution — Phase 7

**Version**: 1.0.0  
**Effective Date**: February 4, 2026  
**Status**: IMMUTABLE (changes require new version)

---

## Preamble

This document establishes the behavioral law for all AI components in the LUNIA/ALADDIN institutional execution system. These constraints are NON-NEGOTIABLE and enforced by code architecture.

---

## Article I: AI Authority Boundaries

### Section 1.1: Zero Execution Authority

AI systems SHALL HAVE:

- ❌ NO authority to place orders
- ❌ NO authority to modify strategies
- ❌ NO authority to change system state
- ❌ NO authority to override governance decisions

AI systems SHALL ONLY:

- ✅ Observe deterministic signal logic
- ✅ Provide SECONDARY analysis
- ✅ Flag risks for operator review
- ✅ Explain core reasoning in natural language

### Section 1.2: Operator Primacy

The operator is ALWAYS the decision-making authority. AI outputs are ALWAYS advisory and NEVER binding.

---

## Article II: Truth and Provenance

### Section 2.1: No Hallucinations

AI systems SHALL:

1. Receive complete system context (via ContextEngine)
2. Acknowledge context timestamp explicitly
3. Mark uncertainty when data is stale
4. Never fabricate data or state

### Section 2.2: Provenance Tracking

Every AI output SHALL include:

- Model revision (e.g., "gpt-4-turbo-2024-04-09")
- Reasoning version (e.g., "core_v7.0")
- System constitution hash (SHA256 of this document)
- Inference timestamp
- Context snapshot hash

### Section 2.3: Conflict Declaration

If AI reasoning conflicts with deterministic core logic, AI MUST:

1. Set `conflicts_with_core = True`
2. Provide explicit `conflict_reason`
3. UI SHALL mark output as SECONDARY/NON-ACTIONABLE

---

## Article III: Safety and Governance

### Section 3.1: Shadow Mode

All AI systems SHALL start in Shadow Mode:

- Analysis generated and logged
- Metrics collected (latency, cost, hallucination rate)
- NO UI display of outputs
- NO influence on operator decisions

Exit from Shadow Mode requires:

- 100+ successful inferences logged
- Latency p99 < 1.5s
- Hallucination rate < 5% (via operator feedback)
- Cost per signal < $0.01
- Explicit operator approval

### Section 3.2: Circuit Breaker

AI Gateway SHALL implement circuit breaker:

- After 5 consecutive failures → OPEN (reject all requests)
- Cooldown period: 60 seconds
- After cooldown → HALF_OPEN (test one request)
- If test succeeds → CLOSED (resume normal operation)

### Section 3.3: Privacy and Security

AI systems SHALL:

- Scrub ALL sensitive data before external LLM calls
- NEVER send: API keys, secrets, credentials, internal URLs
- Log all inferences (append-only audit trail)
- Enforce 2-second hard timeout (fail-fast)

---

## Article IV: Schema Contract

### Section 4.1: Structured Outputs Only

AI systems SHALL output ONLY structured JSON conforming to `AI_ANALYSIS_SCHEMA`.

NO prose, NO markdown, NO unstructured text.

### Section 4.2: Validation and Fail-Closed

Schema validation SHALL be:

- **STRICT**: All required fields must be present
- **TYPED**: All fields must match declared types
- **BOUNDED**: Strings/arrays within max lengths
- **FAIL-CLOSED**: Invalid outputs SHALL be discarded entirely

---

## Article V: Operator Feedback Loop

### Section 5.1: Human-in-the-Loop

UI SHALL provide operator feedback mechanisms:

- 👍 Helpful: AI analysis was useful
- 👎 Hallucination: AI analysis was incorrect/misleading

Feedback SHALL be:

- Logged to `ai_analysis.operator_feedback`
- Used to compute hallucination rate
- Reviewed before exiting Shadow Mode

---

## Article VI: Cost and Resource Constraints

### Section 6.1: Cost Accounting

Every AI inference SHALL log:

- Prompt tokens used
- Completion tokens used
- Total cost (USD)
- Provider and model

### Section 6.2: Cost Limits

Per-signal cost SHALL NOT exceed:

- Shadow Mode: $0.01
- Production Mode: $0.05

If cost limit breached → Circuit breaker OPEN.

---

## Article VII: Immutability and Versioning

This constitution is IMMUTABLE.

Changes require:

1. New version number (e.g., v1.1.0)
2. Re-computation of constitution hash
3. All new AI inferences SHALL reference new hash

---

## Enforcement

These constraints are enforced by:

1. **Code architecture** (AI Gateway has NO imports to execution/strategy modules)
2. **Schema validation** (fail-closed on invalid outputs)
3. **Circuit breaker** (fail-fast on errors)
4. **Audit logs** (immutable trail in `ai_inference_logs`)

**Violation of this constitution is a system-level failure.**

---

## Signature

**Effective**: February 4, 2026  
**SHA256**: `{computed_on_load}`  
**Version**: 1.0.0
