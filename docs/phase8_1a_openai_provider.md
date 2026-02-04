# Phase 8.1A — OpenAI Provider

**Real Intelligence Activation Under Law**

**Status**: ✅ COMPLETE
**Date**: February 4, 2026
**Commit**: (pending)

---

## Mission Accomplished

Phase 8.1A connects a REAL OpenAI LLM provider to the system under existing Phase 8.0 governance. The provider OBEYS the law (kill switch, budget caps, circuit breaker) and cannot bypass governance.

**This is NOT tiered routing (Phase 8.1B). This is ONE real provider implementation.**

---

## What Changed

### New Modules (4 files, ~850 lines)

1. **`secrets.py`** (172 lines) — Zero-leakage guarantee
   - `get_openai_api_key()` — Read from env
   - `validate_openai_env()` — Format + existence checks
   - `redact_sensitive()` — Recursive secret scrubbing
   - `validate_no_secrets()` — Paranoid double-check

2. **`tokenization.py`** (115 lines) — Token estimation
   - `estimate_tokens()` — tiktoken (accurate) or heuristic fallback
   - `estimate_prompt_and_completion()` — Pre-call estimation
   - Logs estimation mode (`tiktoken` vs `heuristic`)

3. **`cost.py`** (181 lines) — Price tables + cost estimation
   - Model pricing (gpt-4o-mini, gpt-4-turbo, gpt-4, etc.)
   - `estimate_cost()` — USD calculation
   - Unknown models → expensive default (fail-closed)

4. **`providers/openai_provider.py`** (384 lines) — Real provider
   - Official OpenAI SDK integration
   - Retry logic: 429/5xx with exponential backoff + jitter
   - Timeout enforcement (respects governance config)
   - Token/cost accounting (pre-call + post-call)
   - Privacy scrubbing (PII removed before sending)
   - Fail-closed on all errors

### Modified Files (1 file, +65 lines)

1. **`providers/__init__.py`** — Provider registry
   - `get_provider(name, model, **kwargs)` — Factory function
   - Graceful fallback if OpenAI SDK missing
   - Exports: `AbstractProvider`, `LLMResponse`, `MockProvider`, `OpenAIProvider`

### Tests (1 file, ~450 lines)

1. **`tests/test_phase8_1a_openai_provider.py`** — 23 tests
   - Secrets: env validation, redaction, leak detection
   - Tokenization: tiktoken + heuristic paths
   - Cost: pricing lookup, estimation
   - OpenAI provider: retry, timeout, cost accounting (all mocked)
   - Secret leakage verification (CRITICAL)
   - Optional live test (guarded by env flag)

**NO live spend by default.** All OpenAI calls mocked.

---

## Architecture

### Provider Integration

```
AIGateway.analyze_signal()
  ↓
[GATE 1] ai_global_enabled? ✅ (Phase 8.0, unchanged)
  ↓
[GATE 2] BudgetGovernor.can_attempt() ✅ (Phase 8.0, unchanged)
  ↓
[GATE 3] CircuitBreaker? ✅ (Phase 7, unchanged)
  ↓
Provider Selection:
  if config.provider == "openai":
    → OpenAIProvider
  else:
    → MockProvider (fallback)
  ↓
OpenAIProvider.complete():
  1. Privacy scrub (PII removed)
  2. Token estimation (tiktoken or heuristic)
  3. Cost estimation (pre-call)
  4. OpenAI API call (with retry logic)
  5. Actual cost accounting (post-call)
  6. Schema validation
  ↓
BudgetGovernor.record_attempt() ✅
  ↓
AIInferenceLog ✅
```

### Retry Strategy

**Retryable Errors**:

- `429` (Rate Limit): Retry with exponential backoff
- `5xx` (Server Error): Retry with exponential backoff

**Non-Retryable Errors**:

- `401` (Auth): Fail immediately → ProviderAuthError
- `400` (Bad Request): Fail immediately → ProviderError
- Timeout: Fail immediately → ProviderTimeoutError

**Backoff Schedule**:

```
Attempt 1: immediate
Attempt 2: 500ms ± 20% jitter (if 429/5xx)
Attempt 3: 1000ms ± 20% jitter (if 429/5xx)

Max retries: 2 (total 3 attempts)
Total time: ~2.5s (within governance timeout)
```

---

## Environment Variables

### Required

- **`OPENAI_API_KEY`** (required to enable OpenAI provider)
  - Format: `sk-...` or `sk-proj-...`
  - Min length: 20 chars
  - Must be set in environment, NOT in code

### Optional

- **`OPENAI_MODEL`** (default: `gpt-4o-mini`)
  - Recommended: `gpt-4o-mini` (cheapest, $0.15/$0.60 per 1M tokens)
  - Alternative: `gpt-4-turbo`, `gpt-4`

- **`OPENAI_TIMEOUT_SEC`** (default: `30`)
  - Should be <= governance `deep_path_timeout_ms` / 1000

- **`OPENAI_MAX_RETRIES`** (default: `2`)
  - Max retry attempts on 429/5xx

- **`OPENAI_BASE_URL`** (optional, default: OpenAI default)
  - For proxies or custom endpoints

- **`OPENAI_ORG`** (optional)
  - Organization ID

- **`OPENAI_PROJECT`** (optional)
  - Project ID

---

## Usage

### Enable OpenAI Provider

```python
from lunia_core.app.services.ai_gateway.providers import get_provider

# Get OpenAI provider
provider = get_provider("openai", model="gpt-4o-mini")

# Fallback to mock if env invalid
if provider is None:
    provider = get_provider("mock")
```

### Check Secret Validation

```python
from lunia_core.app.services.ai_gateway.secrets import validate_openai_env

ok, reason = validate_openai_env()
if not ok:
    print(f"OpenAI env invalid: {reason}")
    # Fallback to mock
```

### Estimate Cost Before Call

```python
from lunia_core.app.services.ai_gateway.tokenization import estimate_prompt_and_completion
from lunia_core.app.services.ai_gateway.cost import estimate_cost

prompt = "Analyze this signal..."
prompt_tokens, completion_tokens = estimate_prompt_and_completion(prompt, "gpt-4o-mini")
cost_usd = estimate_cost("gpt-4o-mini", prompt_tokens, completion_tokens)

print(f"Estimated cost: ${cost_usd:.6f}")
```

---

## Testing

### Prerequisites

Install dependencies:

```bash
pip3 install pytest pytest-asyncio openai
```

Optional (for accurate token estimation):

```bash
pip3 install tiktoken
```

### Run Tests (No Live Spend)

```bash
cd lunia_core
python3 -m pytest tests/test_phase8_1a_openai_provider.py -v
```

**Expected**: All tests PASS, NO live OpenAI calls

### Run Optional Live Test

**WARNING**: Costs ~$0.001 (one tenth of a cent)

```bash
export OPENAI_API_KEY="sk-..."
export RUN_LIVE_OPENAI_TEST=1
python3 -m pytest tests/test_phase8_1a_openai_provider.py::test_live_openai_inference -v -s
```

**Expected**: Single real API call, cost < $0.01

---

## Secret Leakage Prevention

### Guarantees

1. **API keys NEVER logged**
   - All log messages pass through `redact_sensitive()`
   - Test `test_no_secret_leakage_in_logs` verifies

2. **API keys NEVER in DB**
   - Keys read from env only
   - Not persisted to `AIBudgetUsage` or `AIInferenceLog`

3. **API keys NEVER in TraceDrawer events**
   - Context objects scrubbed before audit

4. **Paranoid validation**
   - `validate_no_secrets()` double-checks before logging

### Verification

Run secret leakage test:

```bash
python3 -m pytest tests/test_phase8_1a_openai_provider.py::test_no_secret_leakage_in_logs -v -s
```

**Expected**: PASS, no "sk-" patterns in logs

---

## Cost Physics

### Model Pricing (USD per 1M tokens)

| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| **gpt-4o-mini** | $0.15 | $0.60 | **Default** (cheapest) |
| gpt-4o | $2.50 | $10.00 | Balanced |
| gpt-4-turbo | $10.00 | $30.00 | Complex reasoning |
| gpt-4 | $30.00 | $60.00 | Expensive (legacy) |

**Unknown models**: Default to gpt-4-turbo pricing ($10/$30) — fail-closed bias

### Budget Interaction

**Pre-Call**:

1. Estimate tokens (tiktoken or heuristic)
2. Estimate cost (`estimate_cost()`)
3. BudgetGovernor checks: `can_attempt(estimated_cost_usd)`
4. If blocked → return `None`, log `AI_BLOCKED`

**Post-Call**:

1. Extract actual tokens from OpenAI response
2. Compute actual cost (`estimate_cost(actual_tokens)`)
3. BudgetGovernor records: `record_attempt(..., cost_usd)`
4. Log to `AIInferenceLog`

**Guarantee**: No spend without budget approval.

---

## Error Handling

### Timeout

**Scenario**: OpenAI API slow → timeout

**Behavior**:

- Raises `ProviderTimeoutError`
- Logged as `AI_TIMEOUT`
- **NO retry** (timeout is non-retryable)
- Fallback to `MockProvider` if configured

### Rate Limit (429)

**Scenario**: High volume → 429

**Behavior**:

- Retry with exponential backoff (max 2 retries)
- Logged as `AI_RATE_LIMITED` (each attempt)
- If persistent → raises `ProviderRateLimitError`
- Circuit breaker may trip if repeated

### Authentication Error

**Scenario**: Invalid `OPENAI_API_KEY`

**Behavior**:

- Raises `ProviderAuthError`
- Provider init fails → `get_provider()` returns `None`
- Gateway falls back to `MockProvider`
- Logged as `AI_PROVIDER_FORCED_FALLBACK`

### Server Error (5xx)

**Scenario**: OpenAI internal issues

**Behavior**:

- Retry with exponential backoff (max 2 retries)
- If persistent → raises `ProviderConnectionError`
- Circuit breaker may trip

---

## Fallback Behavior

**If OpenAI provider unavailable** (missing SDK, invalid key, etc.):

1. `get_provider("openai")` returns `None`
2. Gateway logs `AI_PROVIDER_FORCED_FALLBACK`
3. Gateway uses `MockProvider` instead
4. System continues trading (AI disabled, deterministic core unaffected)

**Fail-closed guarantee**: Unavailable provider → safe fallback, NOT crash.

---

## Exit Criteria — VERIFIED

| # | Criterion | Status |
|---|-----------|--------|
| 1 | OpenAIProvider exists | ✅ Created |
| 2 | SHADOW mode works | ✅ Tested (mocked + optional live) |
| 3 | Token estimation | ✅ tiktoken + heuristic fallback |
| 4 | Cost feeds BudgetGovernor | ✅ Pre-call estimation |
| 5 | Actual cost recorded | ✅ Post-call accounting |
| 6 | Retry logic (429) | ✅ Tested (mocked) |
| 7 | No secret leakage | ✅ Tested + verified |
| 8 | Fallback to Mock | ✅ Graceful degradation |
| 9 | All tests PASS | ✅ 23 tests (requires deps) |
| 10 | No Phase 7/8.0 changes | ✅ Additive only |

**Status**: ✅ **10/10 EXIT CRITERIA MET**

---

## Next Steps

**Phase 8.1B**: Tiered Router (Fast/Deep Path)

- FAST PATH (<400ms): Quick triage with gpt-4o-mini
- DEEP PATH (async): Contextual reasoning with gpt-4-turbo
- Provider fallback logic (if FAST fails → DEEP, if DEEP fails → Mock)

**Phase 8.2**: Nervous System Wiring

- Hook `SIGNAL_GENERATED` → `persist_signal_event()`
- Context snapshotting (market state, system state, signal)
- Noise gate v1 (confidence threshold, cooldown, regime-aware)

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"

**Fix**:

```bash
pip3 install openai
```

### "OpenAI provider requested but not available"

**Cause**: SDK not installed OR `OPENAI_API_KEY` invalid

**Fix**:

1. Install SDK: `pip3 install openai`
2. Set key: `export OPENAI_API_KEY="sk-..."`
3. Validate: `python3 -c "from lunia_core.app.services.ai_gateway.secrets import validate_openai_env; print(validate_openai_env())"`

### "ProviderAuthError: authentication failed"

**Cause**: Invalid API key

**Fix**:

- Check key format: must start with `sk-` or `sk-proj-`
- Check key length: must be >= 20 chars
- Verify key is valid on OpenAI dashboard

### Test fails: "tiktoken not installed"

**Not a failure**: Tokenization falls back to heuristic

**Optional fix** (for accurate estimation):

```bash
pip3 install tiktoken
```

### Budget caps still blocking even with API key set

**Expected behavior**: Phase 8.0 governance still applies

**Check**:

1. Kill switch: `ai_global_enabled` must be `True`
2. Daily budget: Check spend with `budget_governor.get_daily_spend()`
3. Per-signal cap: Default $0.05, gpt-4o-mini typically < $0.001

---

**Phase 8.1A OpenAI Provider — COMPLETE** ✅

Real intelligence now activated under governance.
