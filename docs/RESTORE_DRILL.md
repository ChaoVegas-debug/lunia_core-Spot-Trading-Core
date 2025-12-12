# Restore Drill

This walkthrough describes how to practice restoring a Lunia deployment from a backup archive.

## Prerequisites
- Docker and Docker Compose installed on the VPS.
- Backups created via `scripts/backup.sh` and copied locally to the VPS.
- DNS already pointing to the host (see `docs/VPS_RUNBOOK.md`).

## Steps
1. Stop running services:
   ```bash
   docker compose -f lunia_core/infra/docker-compose.yml \
     -f lunia_core/infra/docker-compose.prod.yml \
     --env-file lunia_core/.env down
   ```

2. Restore the archive (replace the path with your backup file):
   ```bash
   scripts/restore.sh backups/lunia_backup_<timestamp>.tar.gz
   ```

   This recreates `lunia_core/data`, `lunia_core/logs`, `data/traefik/acme.json`, and `.env` as shipped in the archive.

3. Bring the stack back up:
   ```bash
   make deploy
   ```

4. Run the smoke suite to validate:
   ```bash
   make smoke
   ```

5. Inspect services if anything fails:
   ```bash
   docker compose -f lunia_core/infra/docker-compose.yml \
     -f lunia_core/infra/docker-compose.prod.yml \
     --env-file lunia_core/.env ps

   docker compose -f lunia_core/infra/docker-compose.yml \
     -f lunia_core/infra/docker-compose.prod.yml \
     --env-file lunia_core/.env logs api traefik
   ```

## Notes
- Restores are idempotent; rerunning the commands will overwrite restored files with the archive contents.
- Ensure HTTPS certificates (`data/traefik/acme.json`) are present to avoid rate limits on re-issuance.
- Keep at least one recent backup off the VPS for disaster recovery.
