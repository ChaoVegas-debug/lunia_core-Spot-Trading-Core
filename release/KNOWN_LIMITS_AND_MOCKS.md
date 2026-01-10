# Known Limits & Mocks (Institutional Disclosure)

## 1. Spot Execution
*   **Status**: **HYBRID**
*   **Logic**: Real (Risk Checks, Balance Checks, Portfolio Allocations).
*   **Routing**: **MOCK**. Orders are intercepted by `ExecutionEngine` and logged, but NOT sent to Binance/OKX.
*   **Evidence**: `app/core/execution/engine.py` (Mock mode default).

## 2. Manual Trade Widget
*   **Status**: **MOCK**
*   **Endpoint**: `POST /trade/spot` (Simulated).
*   **Behavior**: Returns success immediately. Updates local mock balances. Does NOT affect real exchange account.

## 3. Portfolio Executor
*   **Status**: **REAL Logic / MOCK Execution**
*   **Behavior**: `PortfolioExecutor` calculates rebalance orders correctly based on weight diffs. Order placement is mocked.
*   **State**: Updates `last_rebalanced_at` really.

## 4. Scheduler
*   **Status**: **REAL**
*   **Behavior**: `rebalancer.py` runs periodically (if executing). In `flask run`, it acts as an API endpoint trigger or background thread (if configured). Currently triggered via API `/portfolio/{id}/action`.

## 5. Exchange Connectivity
*   **Status**: **MOCK**
*   **Data**: Exchange connection status is simulated in `SystemStateWidget` (Random or Fixed "Connected").
*   **Allocations**: Real (State stored in `ops.json`).

## 6. AI Proposals
*   **Status**: **SEEDED / STATIC**
*   **Behavior**: Proposals are inserted via `seed_full_demo.py`. No live LLM generation loop is active in this demo version.
*   **Reasoning**: Static text "Market volatility decreasing...".

## 7. Risk Limits
*   **Status**: **REAL**
*   **Persistence**: Stored in SQLite `Limit` table.
*   **Enforcement**: `RiskWidget` cross-checks runtime values against DB limits.

## 8. Logs / Audit
*   **Status**: **REAL**
*   **Storage**: SQLite `AuditEvent` table.
*   **Stream**: `/ops/logs` returns real DB entries.
