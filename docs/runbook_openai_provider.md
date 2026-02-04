# Phase 8.1A — OpenAI Provider Runbook

**Production Operations Guide**

**Date**: February 4, 2026  
**Owners**: Platform Engineering, AI Systems

---

## Purpose

This runbook covers production deployment, monitoring, incident response, and rollback procedures for the OpenAI Provider (Phase 8.1A).

---

## Pre-Deployment Checklist

### 1. Environment Validation

```bash
# Verify dependencies installed
pip3 list | grep -E '(openai|tiktoken|jsonschema)'

# Expected output:
# jsonschema      4.17.3
# openai          1.12.0
# tiktoken        0.5.2
```

### 2. Secret Configuration

```bash
# Set OpenAI API key (DO NOT commit to repo)
export OPENAI_API_KEY="sk-..."

# Validate key format
python3 -c "from lunia_core.app.services.ai_gateway.secrets import validate_openai_env; print(validate_openai_env())"

# Expected: (True, 'ok')
```

### 3. Governance Configuration

**File**: `lunia_core/app/services/ai_gateway/governance.py`

**Critical settings**:

```python
ai_global_enabled = False  # Start with kill switch OFF
shadow_mode_default = True  # Shadow mode for safety
daily_budget_usd = 1.00  # Conservative cap ($1/day)
per_signal_budget_usd = 0.05  # Conservative cap ($0.05/signal)
```

**DO NOT enable `ai_global_enabled=True` without approval.**

### 4. Database Migration

```bash
# Verify ai_budget_usage table exists
cd lunia_core
alembic current

# Expected: 005_add_ai_budget_tracking (or later)
```

### 5. Test Suite Validation

```bash
# Run all Phase 8.1A tests (NO live spend)
python3 -m pytest tests/test_phase8_1a_openai_provider.py -v

# Expected: 23/23 PASS
```

### 6. Secret Leakage Verification

```bash
# Run CRITICAL test
python3 -m pytest tests/test_phase8_1a_openai_provider.py::test_no_secret_leakage_in_logs -v -s

# Expected: PASS (no "sk-" in logs)
```

---

## Deployment Procedure

### Phase 1: Shadow Mode (Recommended)

**Timeline**: 24-48 hours

**Configuration**:

```python
ai_global_enabled = False  # Kill switch OFF (AI disabled)
shadow_mode_default = True  # Shadow mode (fallback to Mock)
```

**Actions**:

1. Deploy code (commit 4cc76f4 + audit amendments)
2. Monitor logs for `AI_DISABLED_BY_GOVERNANCE` events
3. Verify no unexpected errors
4. **DO NOT proceed to Phase 2 without approval**

### Phase 2: Live Mode (Guarded)

**Prerequisites**:

- Phase 1 complete (24+ hours stable)
- Budget cap approved
- API key validated
- Incident response team on standby

**Configuration**:

```python
ai_global_enabled = True  # Kill switch ON (AI enabled)
shadow_mode_default = False  # Live mode
daily_budget_usd = 1.00  # Conservative cap
per_signal_budget_usd = 0.05  # Conservative cap
```

**Actions**:

1. Update governance config (in code or DB)
2. Restart backend
3. Monitor budget spend (see Monitoring section)
4. Monitor for 429 rate limits
5. Monitor for timeouts

**Rollback trigger**: Any unexpected behavior → revert to Phase 1 immediately

---

## Monitoring

### Budget Spend (Real-Time)

```python
from lunia_core.app.services.ai_gateway.metrics import (
    get_ai_budget_spend_today_usd,
    get_ai_budget_warning_state
)

# Check current spend
spend = get_ai_budget_spend_today_usd(session)
print(f"Today's spend: ${spend:.4f}")

# Check warning state
state = get_ai_budget_warning_state(session, daily_budget_usd=1.0)
if state["warning_triggered"]:
    print("⚠️ WARNING: Budget >80%")
if state["hard_stop_triggered"]:
    print("🛑 HARD STOP: Budget exceeded")
```

### Budget Usage Breakdown

```python
from lunia_core.app.services.ai_gateway.metrics import get_ai_budget_usage_today

usage = get_ai_budget_usage_today(session)

print(f"Total spend: ${usage['total_spend_usd']:.4f}")
print(f"Total attempts: {usage['total_attempts']}")

for provider, stats in usage["by_provider"].items():
    print(f"{provider}: {stats['attempts']} attempts, ${stats['cost_usd']:.4f}")
```

### Log Monitoring

**Key events to monitor**:

| Event | Severity | Action |
|-------|----------|--------|
| `AI_DISABLED_BY_GOVERNANCE` | INFO | Expected (kill switch OFF) |
| `AI_BLOCKED_BY_BUDGET` | WARNING | Monitor, may hit cap soon |
| `AI_RATE_LIMITED` | WARNING | Monitor 429 rate, may need backoff |
| `AI_TIMEOUT` | ERROR | Investigate OpenAI API latency |
| `AI_PROVIDER_FORCED_FALLBACK` | ERROR | Investigate env/key issue |
| `AI_DEPENDENCY_MISSING` | ERROR | Install tiktoken |

---

## Incident Response

### Incident: Budget Exceeded

**Symptoms**:

- All AI calls blocked
- Logs: `AI_BLOCKED_BY_BUDGET: daily_budget_exceeded`

**Root Cause**: Daily spend >= `daily_budget_usd`

**Immediate Action**:

1. Check current spend:

   ```python
   spend = get_ai_budget_spend_today_usd(session)
   print(f"Spent: ${spend:.4f}")
   ```

2. Verify legitimate usage (not runaway loop)
3. **Options**:
   - **A**: Increase `daily_budget_usd` (requires approval)
   - **B**: Wait until midnight UTC (budget resets)
   - **C**: Emergency: Set `ai_global_enabled=False` (kill switch)

**Prevention**: Lower per-signal cap or reduce signal volume

### Incident: 429 Rate Limit Storm

**Symptoms**:

- Repeated `AI_RATE_LIMITED` events
- Circuit breaker may trip
- Latency spike

**Root Cause**: High signal volume → OpenAI rate limit

**Immediate Action**:

1. Check request rate:

   ```python
   usage = get_ai_budget_usage_today(session)
   print(f"Attempts: {usage['total_attempts']}")
   ```

2. **Options**:
   - **A**: Reduce signal generation frequency
   - **B**: Implement noise gate (Phase 8.2)
   - **C**: Emergency: Set `ai_global_enabled=False`

**Prevention**: Implement noise gate, cooldown logic

### Incident: Timeout Spike

**Symptoms**:

- Repeated `AI_TIMEOUT` events
- Circuit breaker trips
- Gateway falls back to Mock

**Root Cause**: OpenAI API slow (server-side issue)

**Immediate Action**:

1. Check OpenAI status: <https://status.openai.com>
2. **If OpenAI degraded**:
   - Circuit breaker auto-handles (falls back to Mock)
   - Monitor; will auto-recover when OpenAI restores
3. **If OpenAI healthy**:
   - Investigate network latency
   - Check timeout config (default: 30s)

**Prevention**: None (external dependency)

### Incident: Secret Leaked in Logs

**Symptoms**:

- API key visible in application logs

**CRITICAL**: This is a **SEVERITY 1** incident.

**Immediate Action**:

1. **STOP**: Set `ai_global_enabled=False` immediately
2. **ROTATE**: Generate new OpenAI API key
3. **REVOKE**: Delete old API key from OpenAI dashboard
4. **PURGE**: Delete/redact logs containing secret
5. **AUDIT**: Run `test_no_secret_leakage_in_logs` to verify fix
6. **REPORT**: File incident report

**Root Cause**: Bug in `redact_sensitive()` or logging path

**Prevention**: Re-run secret leakage test before every deployment

---

## Rollback Procedures

### Emergency Rollback (Immediate)

**Trigger**: Any critical incident (secret leak, runaway costs, crashes)

**Action**:

```python
# Option 1: Kill switch (fastest)
# Set in governance.py or DB:
ai_global_enabled = False

# Option 2: Force Mock provider (safer fallback)
# In service.py or config:
provider_override = "mock"

# Restart backend
# AI system now disabled/mocked
```

**Verify**:

- Check logs for `AI_DISABLED_BY_GOVERNANCE`
- No more OpenAI API calls
- System continues trading (deterministic core unaffected)

### Code Rollback (Planned)

**Trigger**: Phase 8.1A causing issues, revert to Phase 8.0

**Action**:

```bash
# Revert to Phase 8.0 (before OpenAI provider)
git checkout dd020f0  # Phase 8.0 commit

# Or revert specific commit
git revert 4cc76f4  # Phase 8.1A commit

# Rebuild/restart
# AI system reverts to Phase 8.0 (no real provider, only Mock)
```

---

## Verification Procedures

### Verify No Secret Leakage

**Frequency**: Before every deployment + weekly audit

**Procedure**:

```bash
# 1. Run test
python3 -m pytest tests/test_phase8_1a_openai_provider.py::test_no_secret_leakage_in_logs -v -s

# 2. Manual log inspection
grep -r "sk-" /path/to/logs/
# Expected: No matches

# 3. DB inspection
SELECT * FROM ai_inference_logs WHERE metadata LIKE '%sk-%';
# Expected: 0 rows
```

### Verify Budget Persistence

**Frequency**: Daily

**Procedure**:

```python
from lunia_core.app.services.ai_gateway.metrics import get_ai_budget_history

history = get_ai_budget_history(session, days=7)
for day in history:
    print(f"{day['date']}: ${day['spend_usd']:.4f}, {day['attempts']} attempts")

# Verify:
# - Spend accumulates correctly
# - No gaps (missing days)
# - Totals match ai_inference_logs
```

### Verify Cost Estimation Accuracy

**Frequency**: Weekly

**Procedure**:

```sql
-- Compare estimated vs actual cost
SELECT 
    DATE(created_at_utc) as date,
    AVG(cost_usd_estimated) as avg_est,
    AVG(cost_usd_actual) as avg_actual,
    (AVG(cost_usd_actual) - AVG(cost_usd_estimated)) / AVG(cost_usd_estimated) * 100 as pct_error
FROM ai_inference_logs
WHERE provider = 'openai'
    AND cost_usd_actual IS NOT NULL
GROUP BY DATE(created_at_utc)
ORDER BY date DESC
LIMIT 7;
```

**Expected**: Estimation error < 10%

**If error > 10%**: Investigate token estimation (tiktoken installed? model mismatch?)

---

## Escalation

### L1: Platform Engineering

**Contact**: Slack #platform-eng

**Scope**:

- Budget exceeded
- Rate limit issues
- Timeout spikes
- Routine monitoring

### L2: AI Systems Lead

**Contact**: Slack #ai-systems (escalate if L1 unresolved)

**Scope**:

- Secret leakage (CRITICAL)
- Provider fallback failures
- Cost estimation errors
- Governance logic bugs

### L3: CTO / Risk Officer

**Contact**: Direct escalation (security incident only)

**Scope**:

- Secret leaked to external party
- Runaway costs (>$100/day)
- Regulatory/compliance violation

---

## Change Management

### Configuration Changes

**Approval required for**:

- `ai_global_enabled` toggle
- `daily_budget_usd` increase
- `per_signal_budget_usd` increase
- Provider selection (`openai` vs `mock`)

**Approval NOT required for**:

- Timeout adjustments (within safe range)
- Retry count adjustments
- Model selection (within same provider)

### Code Changes

**Approval required for**:

- Modifications to BudgetGovernor
- Modifications to secrets.py
- Modifications to gate ordering

**Review required for**:

- Provider implementations
- Token estimation logic
- Cost calculation

---

**Phase 8.1A OpenAI Provider Runbook** — Production Ready
