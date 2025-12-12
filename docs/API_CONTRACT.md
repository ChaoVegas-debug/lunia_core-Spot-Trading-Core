# API CONTRACT — LUNIA / ALADDIN (PHASE B)

## 1. Overview
- **Runtime**: Flask REST API defined in `app.services.api.flask_app` (registered `/arbitrage` blueprint). Core runtime persists state via `app.core.state` and now uses a lightweight SQLAlchemy layer (SQLite by default) for users, feature flags, limits, and audit trail.
- **Auth model**: JWT bearer tokens via `/auth/login` + `/auth/me` with `AUTH_SECRET` and `AUTH_TOKEN_TTL_SECONDS`; legacy `X-Admin-Token`/`X-OPS-TOKEN` headers remain supported. `AUTH_REQUIRED_FOR_TELEMETRY` controls whether read-only telemetry requires auth (default on).
- **State backend**: runtime state persisted via `logs/state.json`, mutated through `/ops/*`, `/spot/*`, `/ai/*`, `/arbitrage/*`, trading endpoints; relational tables hold RBAC and admin metadata in `data/lunia.db` (configurable via `DATABASE_URL`).
- **Error shape**: JSON with `{"error": <string|list>}` and HTTP status (400 validation, 401 unauthorized, 403 forbidden, 404 not found, 409 conflict). Arbitrage permission errors use the same shape.

## 2. Roles & Permissions
| Role   | Read-only endpoints | Write/Control endpoints | Notes |
|--------|--------------------|-------------------------|-------|
| USER (subscriber) | `/health`, `/cores`, `/status`, `/metrics`, `/portfolio`, `/balances`, `/portfolio/snapshot`, `/arbitrage/opps`, `/ops/activity`, `/ops/logs`, `/ai/signals` (when telemetry auth disabled) | _none_ | JWT optional if `AUTH_REQUIRED_FOR_TELEMETRY=0`, otherwise bearer token required. |
| TRADER | All USER reads + `/spot/strategies`, `/spot/alloc`, `/spot/risk`, `/ops/equity`, `/ops/capital` | Trading demos `/trade/spot/demo`, `/trade/futures/demo`, manual `/signal`, `/ai/run`, ops toggles `/ops/auto_on|auto_off|stop_all|start_all`, `/ops/state` POST | Bearer token role must be TRADER/ADMIN or legacy admin token header. |
| FUND | Same as TRADER + capital/reserve visibility | Mutations gated by admin or trader role; otherwise read-only | Frontend should present control paths only when role allows. |
| ADMIN | Full surface including `/ops/state` (GET/POST), `/ops/auto_on|auto_off|stop_all|start_all`, `/ops/capital` POST, `/spot/*` POST, `/ai/research/analyze_now`, arbitrage controls, `/admin/*` | Requires bearer token role ADMIN or `X-Admin-Token`; arbitrage supports `X-OPS-TOKEN` when configured | Side-effecting endpoints mutate state, trigger trades/backtests, and update audit trail. |

## 3. Endpoints by Zone & Role (contract)

### 1) AUTH / SESSION
- `POST /auth/login` → body `{email, password}`; returns `{access_token, token_type, role, user_id, expires_at, tenant_id?}` (JWT bearer).
- `GET /auth/me` → returns `{user_id, email, role, is_active, tenant_id?}`; requires bearer token.
- `GET /branding` → returns `{brand_name, logo_url?, support_email?, primary_color?, environment?, tenant_id?}`; subject to telemetry guard when `AUTH_REQUIRED_FOR_TELEMETRY=1`.
- `POST /auth/logout` → no-op acknowledgement for UI symmetry.

### 2) USER PANEL (read-only)
- `GET /health` → `{status: "ok"}`. Latency metric recorded. No side effects.
- `GET /cores` → registry of core modules `{<core>: {weight, enabled}}`.
- `GET /status` → `{version, uptime, active_cores, timestamp}` snapshot.
- `GET /ops/activity` → operational components + last control actions `{components, last_actions, warnings}`.
- `GET /portfolio` → portfolio snapshot `{realized_pnl, unrealized_pnl, positions[], equity_usd}`.
- `GET /balances` → wallet balances list.
- `GET /portfolio/snapshot` → aggregated balances + positions + equity/reserves + cap_pct.
- `GET /arbitrage/opps` → last 10 arbitrage opportunities `{opportunities: [...]}`.
- `GET /ops/logs` → recent API log tail `{items: [{ts, level, message}]}`.
- `GET /metrics` → Prometheus text exposition. Honors `AUTH_REQUIRED_FOR_TELEMETRY`; when enabled, send JWT or `X-Admin-Token: <OPS_API_TOKEN>`.

### 3) TRADER PANEL (actions)
- `POST /trade/spot/demo` — body `TradeRequest{symbol, side, qty}`; executes mock/testnet spot order via Agent; 200 with `{ok, ...}` or 400 with `error` (pydantic errors list or string). Side effects: places order/logs trade.
- `POST /trade/futures/demo` — body `FuturesTradeRequest{symbol, side, qty, leverage, type}`; validates with `RiskManager`, may set leverage then place futures order; 400 on risk rejection or validation.
- `POST /signal` — body `SignalPayload` or `SignalsEnvelope`; publishes to supervisor bus and executes signals immediately; returns execution result.
- `POST /ai/run` — triggers supervisor signals generation and executes them; returns `{executed, errors, ...}`.
- `GET /ai/signals` — read-only feed of latest supervisor signals `{items: [{ts, symbol, side, confidence, strategy, rationale?, source}]}`.

### 4) FUND PANEL (capital/allocations)
- `GET /ops/equity` — equity + tradable_equity + cap_pct.
- `GET /ops/capital` — same plus per-strategy budgets and reserves.
- `POST /ops/capital` (admin-token) — body `CapitalRequest{cap_pct}`; updates cap and returns updated state + tradable_equity.
- `GET /spot/alloc` — allocation snapshot; `POST /spot/alloc` (admin-token) to update reserves `{portfolio?, arbitrage?}`.
- `GET /portfolio/snapshot` — unified balances/positions/equity view with cap_pct/reserves.

### 5) ADMIN PANEL (system & limits)
- `GET /ops/state` — returns full `OpsState` (auto_mode, global_stop, flags, configs).
- `POST /ops/state` (admin-token) — partial update `OpsStateUpdate`; merges into state.json.
- `POST /ops/auto_on|auto_off|stop_all|start_all` (admin-token) — toggles auto/global stop flags.
- `POST /ops/auto_off` — explicit control alias (admin-token or TRADER role).
- `POST /ops/start_all` — explicit control alias (admin-token or TRADER role).
- `POST /ops/stop_all` — explicit control alias (admin-token or TRADER role).
- `GET/POST /spot/strategies` — read/update strategy weights and enable flag.
- `GET/POST /spot/risk` — read/update risk limits `{max_positions, max_trade_pct, risk_per_trade_pct, max_symbol_exposure_pct, tp_pct_default, sl_pct_default}`.
- `POST /spot/backtest` — run strategy backtest (admin-token); body `{strategy?, symbol?, days?}`; returns `{strategy, symbol, trades, pnl_estimate_pct}`.
- Arbitrage controls (admin-token via `X-OPS-TOKEN`): `POST /arbitrage/scan`, `GET /arbitrage/top?limit=`, `POST /arbitrage/exec`, `POST /arbitrage/auto_on|auto_off|auto/tick`, `GET/POST /arbitrage/filters`, `GET /arbitrage/status`, `GET /arbitrage/status/<exec_id>`.
- AI research: `POST /ai/research/analyze_now` (admin-token) — body `ResearchRequest{pairs?}`; returns `ResearchResponse{results}`.
- Diagnostics: `GET /ops/activity` (components + last actions), `GET /ops/logs` (API log tail).
- RBAC/admin: `/admin/users` GET/POST (create user, list users), `/admin/users/<id>` PUT (role/active update), `/admin/flags` GET, `/admin/flags/<key>` PUT, `/admin/limits` GET/PUT (upsert), `/admin/audit` GET (filterable by actor/action/result, limit default 100).
- `GET /admin/users` — list users.
- `POST /admin/users` — create user (RBAC = ADMIN).
- `PUT /admin/users/{id}` — update role/activation/tenant (RBAC = ADMIN).
- `GET /admin/flags` — list feature flags.
- `PUT /admin/flags/{key}` — upsert feature flag value.
- `GET /admin/limits` — list advisory limits.
- `PUT /admin/limits` — upsert advisory limit.

### 6) SYSTEM / HEALTH
- Covered by `GET /health`, `GET /status`, `GET /metrics`. No write operations.

### 7) AI / SIGNALS
- `POST /ai/run` (see Trader) — auto signals.
- `POST /signal` — manual/override signals.
- `POST /ai/research/analyze_now` — research now (admin-token), no trading side effect beyond research.

### 8) RISK / LIMITS
- `GET/POST /spot/risk` (admin-token for POST) — updates persisted risk config.
- Futures validation embedded in `/trade/futures/demo` using `RiskManager` before order placement.

### 9) PORTFOLIO / BALANCE
- `GET /portfolio`, `GET /balances` (read-only as above).

### 10) CONTROL (modes, toggles, cores)
- Ops toggles: `/ops/auto_on`, `/ops/auto_off`, `/ops/stop_all`, `/ops/start_all` (admin-token) — mutate runtime `auto_mode` and `global_stop` flags.
- `GET /ops/state` is the source of truth for runtime mode flags and configs; updated via `/ops/state` or specialized POST endpoints above.

## 4. System States & Modes
- **State source**: `app.core.state` defaults include `auto_mode`, `global_stop`, `trading_on`, `agent_on`, `arb_on`, `sched_on`, `manual_override`, `manual_strategy`, `exec_mode`, `portfolio_equity`, `scalp`, `arb`, `spot`, `reserves`, `ops` (capital caps). Persisted to `logs/state.json` and merged on updates.
- **Modes**:
  - `auto_mode`: enables automated operations (toggled by `/ops/auto_on|auto_off`).
  - `global_stop`: emergency stop flag (`/ops/stop_all` → true, `/ops/start_all` → false).
  - `manual_override` + `manual_strategy`: allow manual strategy selection (updated via `/ops/state`).
  - `exec_mode`: derived from `EXEC_MODE` env (default `dry`).
- **Frontend consumption**: use `GET /ops/state` as source-of-truth; updates only via documented POST endpoints.

## 5. Schemas (stable JSON contracts)
- **TradeRequest**: `{symbol: string, side: "BUY"|"SELL", qty: number>0}`.
- **FuturesTradeRequest**: TradeRequest + `{leverage: number>0 (default 1.0), type: string (uppercased, default "MARKET")}`.
- **SignalsEnvelope**: `{signals: [SignalPayload...], enable: {SPOT: int>=0}}`; SignalPayload = `{symbol: string, side: "BUY"|"SELL", qty: number>0}`.
- **SignalsFeed**: `{items: [{ts, symbol, side, confidence, strategy, rationale?, source}], cursor?: string}`.
- **OpsState**: `{auto_mode: bool, global_stop: bool, trading_on: bool, agent_on: bool, arb_on: bool, sched_on: bool, manual_override: bool, manual_strategy: object|null, scalp: {tp_pct, sl_pct, qty_usd}, arb: {interval, threshold_pct, qty_usd, qty_min_usd, qty_max_usd, auto_mode, filters{min_net_roi_pct, max_net_roi_pct, min_net_usd, top_k, sort_key, sort_dir}}, spot: {enabled, weights{}, max_positions, max_trade_pct, risk_per_trade_pct, max_symbol_exposure_pct, tp_pct_default, sl_pct_default}, reserves: {portfolio, arbitrage}, ops: {capital{cap_pct, hard_max_pct}}, portfolio_equity: float, exec_mode: string}`. Updates accept partials via OpsStateUpdate with same keys optional.
- **CapitalRequest**: `{cap_pct: float 0..1}`.
- **StrategyWeightsRequest**: `{weights: {<strategy>: float}, enabled?: bool}`.
- **ReserveUpdateRequest**: `{portfolio?: float, arbitrage?: float}`.
- **SpotRiskUpdate**: `{max_positions?, max_trade_pct?, risk_per_trade_pct?, max_symbol_exposure_pct?, tp_pct_default?, sl_pct_default?}`.
- **ResearchRequest**: `{pairs?: [string...]}`; **ResearchResponse**: `{results: [object...]}`.
- **ArbitrageOpportunities**: `{opportunities: [object...]}`; filters serialization: `{min_net_roi_pct, max_net_roi_pct, min_net_usd, top_k, sort_key, sort_dir}`.
- **PortfolioSnapshot**: `{realized_pnl: float, unrealized_pnl: float, positions: [{symbol, quantity, average_price, unrealized_pnl}], equity_usd: float}`.
- **BalancesResponse**: `{balances: [{asset, free, locked}]}`.
- **PortfolioAggregate**: `{equity_total_usd, tradable_equity_usd?, cap_pct?, reserves?, positions[], balances[], realized_pnl?, unrealized_pnl?, timestamp}`.
- **ActivityResponse**: `{components: {scheduler|arbitrage|spot|futures: {status, last_tick?, notes?}}, last_actions: [{ts, actor, action, ok, details?}], warnings: []}`.
- **LogsResponse**: `{items: [{ts, level, message}]}`.
- **Trade responses**: `{ok: bool, ...}` on success, `{error: reason}` on failure; futures adds `reason` from risk check or exchange.
- **User**: `{id, email, role, is_active, created_at, last_login_at?}`.
- **FeatureFlag**: `{key, value, updated_at, updated_by?}` with values overriding env defaults.
- **Limit**: `{scope, subject?, key, value, updated_at, updated_by?}` advisory limits surfaced to UI.
- **AuditEvent**: `{id, ts, actor_user_id?, actor_role?, action, target?, result, ip?, user_agent?, metadata?}`.

## 6. Error Model
- **Validation errors**: HTTP 400 with `{"error": [<pydantic error objects>]}` for schema violations.
- **Business/risk errors**: HTTP 400 with `{"error": "<reason>"}` (e.g., futures risk rejection, unknown strategy).
- **Unauthorized**: HTTP 401 with `{"error": "unauthorized"}` or `{"error": "invalid_credentials"}` when bearer token missing/invalid.
- **Auth/role errors**: HTTP 403 with `{"error": "forbidden"}` (missing/invalid admin token) or `{"error": "invalid token"}` for arbitrage blueprint.
- **Not found**: HTTP 404 with `{"error": "not_found"}` for missing arbitrage execution.
- **Conflict**: HTTP 409 with `{"error": "user_exists"}` on duplicate user creation.
- **Success envelope**: JSON payloads as described per endpoint; metrics/health return simple objects.

## 7. Realtime Strategy
- **Polling** (recommended): health/status/ops state, portfolio, balances, arbitrage opportunities, capital/alloc/risk snapshots, strategies, metrics.
- **On-demand POST triggers**: AI run, manual signals, trades, arbitrage scans/execs, backtests — fire-and-refresh via polling.
- **No WebSocket/SSE**: current API is REST-only; frontend should implement periodic polling (e.g., 5–15s for ops/state, 30–60s for balances/portfolio, on-click for controls).

## 8. Admin API (consolidated)
- Control flags: `/ops/state` (GET/POST), `/ops/auto_on`, `/ops/auto_off`, `/ops/stop_all`, `/ops/start_all`.
- Capital & reserves: `/ops/capital` GET/POST, `/ops/equity`, `/spot/alloc` GET/POST.
- Strategy/risk: `/spot/strategies` GET/POST, `/spot/risk` GET/POST, `/spot/backtest` POST.
- Arbitrage operations: `/arbitrage/scan`, `/arbitrage/top`, `/arbitrage/exec`, `/arbitrage/auto_on`, `/arbitrage/auto_off`, `/arbitrage/auto/tick`, `/arbitrage/filters` GET/POST, `/arbitrage/status`, `/arbitrage/status/<exec_id>`.
- AI/Signals: `/ai/research/analyze_now`, `/ai/run`, `/signal`.
- Admin RBAC: `/admin/users` GET/POST, `/admin/users/<id>` PUT, `/admin/flags` GET, `/admin/flags/<key>` PUT, `/admin/limits` GET/PUT, `/admin/audit` GET.

---
**Frontend readiness question:** YES — the contract above enumerates every REST endpoint, schema, role guard, state source, error shape, and polling expectation present in the current backend, enabling panel development without further backend clarification.

### Tenant administration (ADMIN)
- `GET /admin/tenants` → `{ items: Tenant[] }`
- `POST /admin/tenants` → create tenant (slug, name, status, branding fields, domains[])
- `PUT /admin/tenants/{id}` → update tenant core fields/domains
- `GET /admin/tenants/{id}/branding` → `TenantBranding`
- `PUT /admin/tenants/{id}/branding` → update branding
- `PUT /admin/tenants/{id}/limits` → `{ items: Limit[] }` (scope=`tenant`, subject=`tenant.slug`)

Schemas:
- `Tenant`: `{ id, slug, name, status, app_name?, logo_url?, primary_color?, support_email?, environment?, domains[], created_at?, updated_at? }`
- `TenantBranding`: `{ app_name?, logo_url?, primary_color?, support_email?, environment? }`
- `TenantLimitsRequest`: `{ limits: [{ key, value }] }`

Tenant resolution precedence for `/branding` and JWT context:
1. `X-Tenant-Id` header if present and known
2. Hostname match from `tenant_domains` table
3. Fallback to `DEFAULT_TENANT_SLUG`
Non-admin requests must have token tenant match resolved tenant; admin may act cross-tenant.
