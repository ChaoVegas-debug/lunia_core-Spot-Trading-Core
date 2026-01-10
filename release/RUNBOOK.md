# Operator Runbook

## 1. Backend Setup & Start
**Path**: `lunia_core-Spot-Trading-Core/lunia_core`

```bash
cd lunia_core

# 1. Install Dependencies (if new env)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install python-dotenv

# 2. Check Database
# (Created automatically on start if missing)

# 3. Start Server (Default Port 5000)
# Use nohup for background or run in separate terminal
export FLASK_APP=app.services.api.flask_app
flask run --host=0.0.0.0 --port=5000
```

**Health Check**:
```bash
curl http://localhost:5000/health
# Expected: {"status": "ok", ...}
```

## 2. Frontend Setup & Start
**Path**: `lunia_core-Spot-Trading-Core/frontend`

```bash
cd frontend

# 1. Install Node Deps
npm install

# 2. Start Dev Server
npm run dev
# Access at http://localhost:5173
```

**Note**: If port 5173 is busy, Vite will pick next. Check console output.

## 3. Deterministic Seeding (The Source of Truth)
**Path**: `lunia_core-Spot-Trading-Core/lunia_core`

Execute this ONCE to reset demo state to "Golden Snapshot":

```bash
cd lunia_core
source .venv/bin/activate
python seed_full_demo.py
```

**Verification**:
```bash
curl -H "Authorization: Bearer <token>" http://localhost:5000/ops/state
# Should return valid JSON with 'portfolio_equity': 25000
```

## 4. Automated Smoke Test
**Path**: `lunia_core-Spot-Trading-Core/lunia_core`

```bash
cd lunia_core
source .venv/bin/activate
python tools/smoke/verify_cockpit_flow.py
```
**Reports**: `lunia_core/reports/SMOKE_VERIFY_REPORT.md`

## 5. Owner Verification Checklist
See `release/OWNER_VERIFICATION_CHECKLIST.md` for click-by-click verification.
