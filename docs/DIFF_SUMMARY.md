# DIFF SUMMARY

## Critical Changes for Live Combat Enforcement

## Critical Changes for Live Combat Enforcement

### 1. `lunia_core/app/core/exchange/binance_spot.py`
- **FAIL-CLOSED ENFORCEMENT**: Removed auto-mock logic.
- **AUTH GATING**: Introduced `auth_proven` state (VERIFIED/FAILED).
- **CRITICAL**: `place_order` and `get_balances` now RAISE AN ERROR if auth is not verified. 
- **IMPACT**: Zero chance of "Partial State" where keys are invalid but system pretends to work.

### 2. `lunia_core/app/services/api/flask_app.py`
- **STRICT PROD BOOT**: explicitly sets `client.mock = False`.
- **BOOT VERIFICATION**: Calls `client.verify_auth()` on startup.
- **LOGGING**: Logs `CRITICAL` if verification fails. System enters GATED state.

### 3. `scripts/verify_combat_readiness.py` (NEW)
- **FORENSIC VERIFICATION**: A script that inspects deep internal state (`/api/exchanges/debug`) and performs a real data fetch (`/balances` with `X-Data-Source: REAL`).
- **ASSERTIONS**: Fails if `mock` is True, if `env` is not Mainnet, or if balances are fake/empty.

### 4. `scripts/start_prod.sh` (NEW)
- **ENVIRONMENT**: Canonical script to launch backend with `LUNIA_PREVIEW_MODE=0` and `FLASK_DEBUG=0`.

## Security Notes
- No secrets were exposed in logs or diffs.
- `.secrets.json` remains the single source of truth.
