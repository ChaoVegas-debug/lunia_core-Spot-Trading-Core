# Offline / Proxy Installation Guide

This guide explains how to prepare the Lunia/Aladdin stack for environments without direct access to public package registries.

## Build wheelhouse with internet access

```bash
make wheelhouse
# or customize sources
PIP_INDEX_URL=https://mirror.example.com/simple \
PIP_TRUSTED_HOST=mirror.example.com \
WHEELHOUSE_REQUIREMENTS="lunia_core/requirements/base_minimal.txt lunia_core/requirements/base.txt lunia_core/requirements/test.txt" \
make wheelhouse
```

Artifacts written to `wheelhouse/`:
- downloaded wheels for the selected requirement sets
- copies of the requirement files
- `requirements-resolved.txt` (pip freeze snapshot)
- `manifest.txt` (expected wheel filenames) and `.gitkeep` placeholder

Copy the `wheelhouse/` directory to the target host alongside the repository.

## Offline backend install

On the offline/air‑gapped host:

```bash
make venv
make install-backend-offline
```

This installs all backend dependencies using only the local `wheelhouse/` contents (including PyYAML for compose lint). If a wheel is missing, rebuild the wheelhouse with internet access and retry. If no wheelhouse is present, `make offline-verify` will skip with a reminder to build one.

You can also create a dedicated verification environment without touching the host Python:

```bash
OFFLINE_VENV=.venv_offline_verify make offline-verify
```

## Offline verification / RC gate

After installing from the wheelhouse (or skipping when none is available):

```bash
# optional: ensure env populated (contains ADMIN_EMAIL/PASSWORD etc.)
cp lunia_core/.env.example lunia_core/.env
make offline-verify             # uses wheelhouse-only if present; otherwise skips with guidance
# or run the full RC gate with OFFLINE_CI set (delegates to offline-verify when air-gapped)
OFFLINE_CI=1 make rc-verify
```

The offline verification will:
- validate wheel presence for critical packages (including PyYAML + pytest)
- create a dedicated venv (`.venv_offline_verify` by default) and install from wheelhouse only
- run guards, compose lint, compile Python sources, execute RBAC/auth tests (no skips)
- start the API locally and perform smoke calls (using `.env.example` unless overridden)

If compose lint complains about missing `pyyaml`, rebuild the wheelhouse (`make wheelhouse`) or install from it explicitly:

```bash
pip install --no-index --find-links wheelhouse pyyaml
```

## Frontend in restricted networks

If `npm ci` is blocked, you can either:

1) Build on a connected machine and copy `frontend/dist`:
```bash
cd frontend
npm ci
npm run build
# copy frontend/dist to the offline host and serve via the Dockerfile build args or any static server
```

2) Use the existing multi-stage Docker build with cached registry:
```bash
cd frontend
# set proxy/registry as needed
NPM_CONFIG_REGISTRY=https://registry.npmjs.org/ \
HTTPS_PROXY=http://proxy:3128 \
DOCKER_BUILDKIT=1 docker build -t lunia-frontend:offline .
```

The backend remains usable via `make local-smoke` and `make offline-verify` even when the frontend build is deferred.
