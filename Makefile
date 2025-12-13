COMPOSE ?= docker compose
COMPOSE_FILES := -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml
ENV_FILE := lunia_core/.env
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
PY_CMD := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)
PYTEST_CMD := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON) -m pytest,pytest)
LOAD_BASE_URL ?= http://localhost:8080

.PHONY: up down logs ps build deploy preflight verify verify-local smoke local-smoke test-api backup restore restore-drill uptime compose-lint load-test wheelhouse install-backend-offline offline-verify no-placeholders no-dead-controls venv install-backend rc-verify

up:
	$(COMPOSE) $(COMPOSE_FILES) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) $(COMPOSE_FILES) --env-file $(ENV_FILE) down

logs:
	$(COMPOSE) $(COMPOSE_FILES) --env-file $(ENV_FILE) logs -f

ps:
	$(COMPOSE) $(COMPOSE_FILES) --env-file $(ENV_FILE) ps

build:
	$(COMPOSE) $(COMPOSE_FILES) --env-file $(ENV_FILE) build

deploy:
	bash scripts/deploy_vps.sh

preflight:
	bash scripts/guard_python_version.sh 3.12
	python scripts/preflight.py

verify:
	PY_CMD=$(PY_CMD) OFFLINE_CI=0 WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) bash scripts/rc_verify.sh

verify-local:
	PY_CMD=$(PY_CMD) OFFLINE_CI=0 WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) bash scripts/rc_verify.sh

smoke:
	bash scripts/smoke_test.sh

local-smoke:
	bash scripts/local_smoke.sh

test-api:
	$(PYTEST_CMD) tests/test_auth_rbac_endpoints.py tests/test_tenant_admin.py tests/test_panel_wiring_contract.py

backup:
	BACKUP_DIR?=backups bash scripts/backup.sh

restore:
	@if [ -z "$(BACKUP)" ]; then echo "Set BACKUP=<archive> make restore" && exit 1; fi
	bash scripts/restore.sh $(BACKUP)

restore-drill:
	@echo "See docs/RESTORE_DRILL.md for the full drill. Example:" && echo "  make restore BACKUP=backups/lunia_backup_<ts>.tar.gz && make deploy && make smoke"

uptime:
	DOMAIN?=example.com bash scripts/uptime_check.sh

compose-lint:
	WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) $(PY_CMD) scripts/compose_lint.py

load-test:
	BASE_URL=$(LOAD_BASE_URL) python tools/http_load_test.py --base-url "$(LOAD_BASE_URL)" $(ARGS)

wheelhouse:
	bash scripts/build_wheelhouse.sh

install-backend-offline: venv
	$(VENV_PIP) install --no-index --find-links wheelhouse -r requirements.txt -r lunia_core/requirements/test.txt
	$(VENV_PIP) install --no-index --find-links wheelhouse pyyaml

offline-verify:
	OFFLINE_CI=1 WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) bash scripts/offline_verify.sh

no-placeholders:
	bash scripts/no_placeholders.sh

no-dead-controls:
	bash scripts/no_dead_controls.sh

venv:
	python -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip

install-backend: venv
	$(VENV_PIP) install -r requirements.txt -r lunia_core/requirements/test.txt

rc-verify: venv
	PY_CMD=$(VENV_PYTHON) OFFLINE_CI=$(OFFLINE_CI) WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) bash scripts/rc_verify.sh
