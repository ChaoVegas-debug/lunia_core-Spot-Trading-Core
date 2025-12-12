# Lunia Frontend (Phase C Web Panels)

React + Vite + TypeScript console that follows `docs/API_CONTRACT.md` for the User, Trader, Fund, and Admin panels with unified cockpit layout (Dashboard, Portfolio, Signals, System Activity, Risk, Logs; Controls/Capital for privileged roles).

## Prerequisites

- Node.js 18+
- API reachable at `VITE_API_BASE_URL` (default `http://localhost:8080`)

## Quick start

```bash
cd frontend
cp .env.example .env  # adjust VITE_API_BASE_URL / default role or tokens
npm ci
npm run dev
```

Open http://localhost:5173 and log in with email/password (JWT via `/auth/login`) or, in dev, select a fallback role. Admin/Trader controls require bearer tokens with TRADER/ADMIN role or legacy X-Admin-Token/X-OPS-TOKEN headers. Signals panel consumes `/ai/signals`; System Activity consumes `/ops/activity`; Logs combines `/ops/logs` with UI audit events.

### Offline / restricted registries

Scenario A (registry reachable):
```bash
cd frontend
npm ci
npm run dev
```

Scenario B (registry blocked):
- Build on a connected machine: `npm ci && npm run build`, then copy `frontend/dist` to the target host and serve via the Dockerfile (multi-stage) or any static server.
- Or build with Docker + proxy/cache: `DOCKER_BUILDKIT=1 NPM_CONFIG_REGISTRY=<mirror> HTTPS_PROXY=<proxy> docker build -t lunia-frontend:offline .`

If frontend build is skipped, backend can still be validated via `make local-smoke` / `make offline-verify`.

### Docker build

Build and serve the static bundle (nginx) with the backend stack:

```bash
cd lunia_core/infra
docker compose build frontend --build-arg VITE_API_BASE_URL=http://localhost:8080
docker compose up -d frontend
```

### Scripts

- `npm run dev` — local dev server with hot reload
- `npm run build` — typecheck + production build
- `npm run lint` — ESLint on the src tree
- `npm run typecheck` — TypeScript project references
- `npm run preview` — serve the built assets locally

### Registry / proxy guidance

- Default registry is `https://registry.npmjs.org/` (configurable via `NPM_CONFIG_REGISTRY` or `.npmrc`).
- To switch registry: `npm config set registry <url>`.
- Corporate proxy example:

```bash
export HTTPS_PROXY=http://proxy.example.com:3128
export HTTP_PROXY=http://proxy.example.com:3128
export NO_PROXY=localhost,127.0.0.1
npm ping
```

If the registry is unreachable, set `NPM_CONFIG_REGISTRY` in your shell or Docker build args and rerun `npm ci`.
Use the npm cache to minimize outbound calls: `npm config set cache ~/.npm-cache --global` then `npm ci --prefer-offline`.
CI can skip frontend build when `SKIP_FRONTEND_CI=1` or `SKIP_FRONTEND_BUILD=1` is set, but production deploys should keep the build enabled.

### Polling cadence (per contract)
- System state/status: 2.5–4s
- System activity: 5s
- Portfolio snapshot: 8s
- Risk: 7s
- Signals feed: 12s
- Arbitrage opportunities: 20s

### Role gating
Routes `/user`, `/trader`, `/fund`, `/admin`, `/system`, `/docs` are protected via frontend role context.
Provide JWT (email/password) for bearer authentication; optional legacy `X-Admin-Token` / `X-OPS-TOKEN` fields remain for backwards compatibility. Controls are disabled if role is insufficient, admin tokens are missing, or data is stale per header status chips. Admin panel now wires Users (CRUD), Feature Flags, Limits, and Audit tabs to `/admin/*` endpoints per `docs/API_CONTRACT.md`.
