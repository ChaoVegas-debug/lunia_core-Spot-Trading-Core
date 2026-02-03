# PRODUCTION RUNBOOK

## OVERVIEW
This runbook details the procedure to start the LUNIA Trading System in **FULL LIVE COMBAT MODE** and verify its connectivity to Binance Mainnet.

## 1. STARTUP
**WARNING**: This will expose the system to real financial risk. Ensure keys are valid.

```bash
# Clean start (Kills existing port 8080 processes)
./scripts/start_prod.sh
```

**What this does**:
- Sets `LUNIA_PREVIEW_MODE=0` (Production Hardening)
- Sets `FLASK_DEBUG=0`
- Starts Backend on Port 8080 (Background)

## 2. VERIFICATION
Run the strict combat readiness verification script.

```bash
python3 scripts/verify_combat_readiness.py
```

**Success Criteria**:
- Output must show `✅ System is in LIVE CONFIGURATION (Mock=False)`
- Output must show `✅ POSITIVE TEST PASSED` (Real Balances).
- Output must show `✅ NEGATIVE TEST PASSED` (Fail-Closed on invalid keys).

**Failure Scenarios**:
1. **"auth-not-proven" (502)**:
   - The system rejected the request because the backend failed to verify keys on startup.
   - **Check Logs**: `tail -n 50 backend_prod.log`
   - **Likely Causes**:
     - Invalid Keys in `.secrets.json`.
     - **IP Ban** (Binance 418/429) -> Wait 2 minutes and retry.
     - System clock desync.

2. **"System is in MOCK mode"**:
   - **CRITICAL**: The fail-closed override failed. Stop immediately.

## 3. FAIL-CLOSED AUDIT
The `verify_combat_readiness.py` script now includes an automated Negative Test:
1. It restarts the backend with invalid keys.
2. It confirms the system returns `502/401` and **NOT** fake balances.
3. It restarts the backend with valid keys.

**Manual Check**:
Rename `.secrets.json`, restart, and verify `/balances` returns 500/502.

