# Pre-Deploy Checklist (Release Candidate)

**Version:** RC1
**Date:** 2025-12-15

## 1. Environment Configuration
- [ ] **`.env` Creation**: Copied from `.env.example`?
- [ ] **Secrets**: `OPS_API_TOKEN` and `AUTH_SECRET` generated/secured?
- [ ] **Admin Account**: `ADMIN_EMAIL` and `ADMIN_PASSWORD` set?
- [ ] **Database**: `DATABASE_URL` pointing to persistent volume (e.g., `./data/lunia.db`)?

## 2. Infrastructure
- [ ] **Docker**: Version 20.10+ installed?
- [ ] **Ports**: 80/443 free (if using Traefik) or `PORT` (e.g. 5000/8080) available?
- [ ] **DNS**: Domain A records verified?

## 3. Application Startup
- [ ] **Backend**: Starts without crash loops? `docker compose ps` shows `healthy`?
- [ ] **Frontend**: Accessible via browser?
- [ ] **Logs**: No critical errors in `docker compose logs api`?

## 4. Operational Verification (Smoke Test)
1.  **Login**: Can log in as Admin with env credentials?
2.  **Dashboard**: Does Admin Overview load without 401/403 errors?
3.  **Auditing**: Change a feature flag (e.g. `/admin/flags`). Does it persist? Is audit log created?
4.  **Trader View**: Navigate to `/trade`. Are controls visible?
5.  **Fund View**: Navigate to `/fund`. is Portfolio Summary visible?

## 5. Security Check
- [ ] **Public Access**: Is API exposed properly (HTTPS)?
- [ ] **OPS Token**: Is `X-Admin-Token` required for write ops?
- [ ] **RBAC**: Confirm standard user cannot see Admin panel.

## 6. Rollback Plan
- [ ] **Backup**: Database backed up before deploy?
- [ ] **Image**: Previous valid Docker image tag identified?
