# EPOCH D3.1: REAL-TIME MARKET DATA ENGINE — PRODUCTION ENABLEMENT GUIDE (AUDIT GRADE)
**Product:** LUNIA / ALADDIN  
**Component:** Market Data Engine ("The Eyes") — Real-Time Perception Layer  
**Tier:** Institutional / HFT-Grade  
**Architecture:** Mock-First Core / Pluggable IO (Composition Root Swap)  
**Status:** Ready for Staging → Production (subject to Gates)

────────────────────────────────────────────────────────
## 0) NON-NEGOTIABLE STATEMENT (READ FIRST)
This system is designed **Fail-Closed**.

**If live market data is not VALID, trading is FORBIDDEN.** There are no "best effort" fallbacks to trade on stale/invalid/mock data.

**VALID** is the only admissible state for REAL execution:
- `SnapshotState.VALID` → Execution may proceed (subject to Governance + Risk).
- `SnapshotState.STALE` / `SnapshotState.INVALID` → Execution MUST BLOCK (no exceptions).

────────────────────────────────────────────────────────
## 1) EXECUTIVE SUMMARY
The Real-Time Market Data Engine (D3.1) is implemented with a **Mock-First Architecture**:
- Core logic is complete and tested: snapshot state machine, L2 integrity guards, staleness detection, startup barrier, symbol isolation, bounded buffers, async lock safety, graceful shutdown, health metrics.
- IO layer is pluggable:
  - **MockWebSocketClient** (tests/dev only; deterministic)
  - **CCXTProClient** (production; requires `ccxt.pro`)

Production enablement requires only **Composition Root wiring**:
- Core engine remains unchanged.
- Swap client implementation (Mock → CCXTPro) at startup, under a hard kill-switch.

────────────────────────────────────────────────────────
## 2) SAFETY INVARIANTS (LOCKED — NON-NEGOTIABLE)

### 2.1 Fail-Closed Defaults
- Engine initializes as STALE/UNREADY.
- Engine remains STALE until it constructs the first **VALID** snapshot.
- On disconnect → STALE immediately.
- On no updates for `staleness_threshold_ms` (default 5000ms) → STALE.

### 2.2 Execution Block Contract (Hard Rule)
Any consumer (Execution, Risk, Governance) MUST enforce:

**Precondition for REAL execution:**
- `snapshot.snapshot_state == VALID`

If not VALID:
- MUST return BLOCK (reason codes should be explicit, e.g. `MD_STALE`, `MD_INVALID`, `MD_UNREADY`).
- MUST NOT submit orders.
- MUST NOT "use last known price".

### 2.3 Data Quality Guards (L2 Integrity)
A snapshot becomes INVALID/STALE if any guard fails:
- Crossed book: Best Bid >= Best Ask
- L2 Integrity:
  - price > 0, amount > 0
  - bids strictly descending
  - asks strictly ascending
  - no duplicate price levels
- Partial data poisoning guard:
  - must track `has_ticker`, `has_orderbook`
  - if missing any required component → STALE

### 2.4 Concurrency Safety (No Torn Reads)
- All snapshot read/write MUST be protected by asyncio locks.
- Reads return deep copies; never expose internal mutable references.

### 2.5 Runtime Kill-Switch
- `LUNIA_MARKETDATA_REALTIME_ENABLED=true` is required to enable live mode.
- If enabled but ccxt.pro is missing → fail startup immediately (fail-closed).

### 2.6 No Side Effects
Market data layer is observational:
- MUST NOT submit orders
- MUST NOT call execution adapters
- MUST NOT mutate execution state

────────────────────────────────────────────────────────
## 3) DEPLOYMENT PREREQUISITES

### 3.1 Dependencies (Production)
**Risk Item:** `ccxt.pro` may be paid/commercial and may require proper licensing and distribution approval.

Minimum requirements:
```bash
pip install ccxt.pro pytest-asyncio
```

Policy:
- Tests must NOT require ccxt.pro (mock-first).
- Production runtime MUST fail if realtime is enabled but ccxt.pro is not importable.

### 3.2 Configuration (Environment Variables)
Feature Flags (Kill Switch):
- `LUNIA_MARKETDATA_REALTIME_ENABLED=true|false` (default false)

Exchange Config (secrets — never log):
- `LUNIA_EXCHANGE_ID=binance`
- `LUNIA_EXCHANGE_API_KEY=...`
- `LUNIA_EXCHANGE_SECRET=...`

Safety Tunables:
- `LUNIA_STALENESS_THRESHOLD_MS=5000`
- `LUNIA_L2_DEPTH=20`
- Optional: `LUNIA_RT_BUFFER_SIZE=1000`
- Optional: `LUNIA_RT_READY_TIMEOUT_SEC=30`

Hard Security Rule:
- NEVER print secrets to stdout.
- NEVER include secrets in exceptions.
- If logging is required, sanitize.

────────────────────────────────────────────────────────
## 4) PRODUCTION WIRING (COMPOSITION ROOT)

### 4.1 Core Logic vs Composition Root (Precision)
- Core Engine modules remain unchanged: models/buffers/manager/guards/state-machine
- Composition Root chooses IO implementation:
  - CCXTProClient in production
  - MockWebSocketClient in tests/dev only

### 4.2 Fail-Closed Wiring Template
This wiring ensures correct behavior:
- If realtime enabled → must use CCXTProClient; if missing → exit(1)
- If realtime disabled → either do not start engine OR start mock engine but mark as non-tradable (execution must still BLOCK)

```python
import os
import sys

from app.services.market_data.realtime.manager import RealTimeMarketDataEngine

def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key, "true" if default else "false").strip().lower()
    return v in ("1", "true", "yes", "on")

REALTIME_ENABLED = _env_bool("LUNIA_MARKETDATA_REALTIME_ENABLED", default=False)

if REALTIME_ENABLED:
    try:
        from app.services.market_data.realtime.interfaces import CCXTProClient
    except ImportError:
        # FAIL-CLOSED: realtime explicitly enabled but dependency missing
        print("❌ CRITICAL: LUNIA_MARKETDATA_REALTIME_ENABLED=true but ccxt.pro is not installed/importable.")
        sys.exit(1)

    client = CCXTProClient()
    print("✅ MARKET DATA MODE: REALTIME (CCXT PRO)")
else:
    # Dev/Test only. Production should usually keep this OFF.
    from app.services.market_data.realtime.interfaces import MockWebSocketClient
    client = MockWebSocketClient()
    print("⚠️ MARKET DATA MODE: MOCK (DEV/TEST ONLY)")

engine = RealTimeMarketDataEngine(
    client=client,
    staleness_threshold_ms=int(os.getenv("LUNIA_STALENESS_THRESHOLD_MS", "5000")),
    buffer_size=int(os.getenv("LUNIA_RT_BUFFER_SIZE", "1000")),
    l2_depth=int(os.getenv("LUNIA_L2_DEPTH", "20")),
)
```

### 4.3 Mandatory Consumer Contract (Execution/Risk)
Do not allow silent misuse. Consumers must implement:
- `await engine.wait_until_ready(symbol, timeout=READY_TIMEOUT)` before REAL trading
- `snapshot.snapshot_state == VALID` check per decision cycle

If you cannot enforce this in code yet:
- Real trading must remain disabled.

────────────────────────────────────────────────────────
## 5) VALIDATION GATES (MANDATORY)
No production promotion without passing ALL gates.

### GATE A — Async Unit Tests (Concurrency + Lifecycle)
Logic tests are not sufficient for asyncio correctness.

Commands:
```bash
pip install pytest-asyncio
pytest tests/epoch_d/test_realtime_engine.py -v
```

Pass Criteria:
- All tests GREEN
- No warnings like: "Task was destroyed but it is pending"
- No deadlocks / tests complete fast (< ~2s typical)

### GATE B — Logic Suite (Core Determinism)
Commands:
```bash
pytest tests/epoch_d/test_d3_logic.py -v
```

Pass Criteria:
- All logic tests GREEN

### GATE C — Import/Startup Sanity (Fail-Closed Wiring)
In a clean environment:
- realtime enabled + missing ccxt.pro must FAIL startup
- realtime disabled must start without importing ccxt.pro

This is a deployment gate, not a unit test.

────────────────────────────────────────────────────────
## 6) STAGING SMOKE TESTS (MANDATORY)
We require two smoke tests:
- Cold start + readiness + VALID snapshots
- Reconnect + stale transition + recovery

### 6.1 Smoke Test 1 — Cold Start Readiness
Create script: `scripts/smoke_test_market_data_cold_start.py`

```python
import asyncio
import os
import sys

from app.services.market_data.realtime.manager import RealTimeMarketDataEngine
from app.services.market_data.realtime.models import SnapshotState

async def main():
    if os.getenv("LUNIA_EXCHANGE_API_KEY") is None:
        print("❌ ENV MISSING: LUNIA_EXCHANGE_API_KEY")
        sys.exit(1)

    from app.services.market_data.realtime.interfaces import CCXTProClient

    symbol = "BTC/USDT"
    exchange = os.getenv("LUNIA_EXCHANGE_ID", "binance")
    market_type = os.getenv("LUNIA_MARKET_TYPE", "spot")

    client = CCXTProClient()
    engine = RealTimeMarketDataEngine(client=client, staleness_threshold_ms=5000, buffer_size=1000, l2_depth=20)

    try:
        print("🔥 Cold Start Smoke Test: START")
        await engine.start(exchange=exchange, symbols=[symbol], market_type=market_type)

        ready = await engine.wait_until_ready(symbol, timeout=30.0)
        if not ready:
            raise RuntimeError("❌ Timeout waiting for READY barrier")

        for _ in range(5):
            await asyncio.sleep(1)
            snap = await engine.get_snapshot(symbol)
            print(f"State={snap.snapshot_state} Bid={snap.bid} Ask={snap.ask} Lat={snap.system_latency_ms}ms")

            if snap.snapshot_state != SnapshotState.VALID:
                raise RuntimeError(f"❌ Snapshot not VALID: {snap.snapshot_state}")
            if snap.bid is not None and snap.ask is not None and snap.bid >= snap.ask:
                raise RuntimeError("❌ Crossed book detected in snapshot")

        print("✅ Cold Start Smoke Test: PASS")

    finally:
        print("Stopping engine...")
        await engine.stop()
        print("✅ Shutdown: CLEAN")

if __name__ == "__main__":
    asyncio.run(main())
```

### 6.2 Smoke Test 2 — Reconnect + Stale Transition
Create script: `scripts/smoke_test_market_data_reconnect.py`

Goal:
- Force disconnect (network, or client-level simulated disconnect if supported)
- Verify snapshot transitions VALID → STALE
- Verify recovery returns to VALID within a bounded time window

Implementation details depend on CCXTProClient capabilities and environment.

Minimum requirement:
- staleness monitor must detect prolonged absence of updates and mark STALE
- after reconnection, readiness barrier for that symbol must re-open to VALID

────────────────────────────────────────────────────────
## 7) OBSERVABILITY & ALERTING (MANDATORY)
Expose health metrics via: `await engine.get_health()`

### 7.1 Required Alerts
- Any symbol STALE for > 10s → HIGH → auto-pause trading
- Any symbol INVALID immediately → CRITICAL → emergency stop / kill-switch
- system_latency_ms > 500ms sustained → MEDIUM → investigate network/host load
- dropped_count increasing rapidly → LOW/MEDIUM → increase buffers or reduce depth

### 7.2 Required Operational Rule
Execution must use the market data engine as the truth source:
- If engine reports stale/invalid → execution must BLOCK.

No exceptions.

────────────────────────────────────────────────────────
## 8) ROLLBACK PLAN (INSTANT, FAIL-CLOSED)
If live WebSocket connectivity becomes unstable or ccxt.pro fails:
- Set: `LUNIA_MARKETDATA_REALTIME_ENABLED=false`
- Restart service.

Result:
- Engine may run mock or not run at all.
- Trading is blocked because mock does not yield VALID for REAL execution.
- Capital safety preserved.

────────────────────────────────────────────────────────
## 9) SECURITY NOTES (AUDIT READY)
- Secrets must be loaded via environment only.
- No secret leakage in logs/exceptions.
- If any error message contains sensitive data, sanitize before emitting.

────────────────────────────────────────────────────────
## 10) FINAL CHECKLIST (MUST BE TRUE BEFORE PRODUCTION)
- [ ] ccxt.pro installed and licensed in production environment
- [ ] pytest-asyncio installed in CI
- [ ] GATE A (async tests) GREEN
- [ ] GATE B (logic tests) GREEN
- [ ] GATE C (fail-closed wiring) verified
- [ ] Smoke test cold start PASS
- [ ] Smoke test reconnect PASS (or documented limitation with explicit mitigations)
- [ ] Alerting configured for STALE/INVALID
- [ ] Execution layer blocks on non-VALID snapshots (verified)
- [ ] Kill switch tested (LUNIA_MARKETDATA_REALTIME_ENABLED=false stops trading)
