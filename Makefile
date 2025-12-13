COMPOSE ?= docker compose
COMPOSE_FILES := -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml
ENV_FILE := lunia_core/.env
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
PY_CMD := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)
PYTEST_CMD := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON) -m pytest,pytest)
LOAD_BASE_URL ?= http://localhost:8080

.PHONY: up down logs ps build deploy verify verify-local smoke local-smoke test-api backup restore restore-drill uptime compose-lint load-test wheelhouse install-backend-offline offline-verify no-placeholders no-dead-controls venv install-backend rc-verify

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

verify:
	bash scripts/guard_python_version.sh
	python scripts/preflight.py
	OFFLINE_CI=1 python scripts/health/all_checks.py

verify-local:
	bash scripts/guard_python_version.sh
	$(PY_CMD) scripts/preflight.py
	$(PY_CMD) -m compileall lunia_core/app/services
	bash scripts/no_placeholders.sh
	bash scripts/no_dead_controls.sh
	WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) $(PY_CMD) scripts/compose_lint.py
	$(PYTEST_CMD) tests/test_auth_rbac_endpoints.py tests/test_tenant_admin.py tests/test_panel_wiring_contract.py

smoke:
	$(info Running smoke tests)
	bash scripts/smoke_test.sh

local-smoke:
	$(info Starting local API and running smoke checks)
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
	$(info Running HTTP load test; set BASE_URL=https://api.example.com to target prod)
	BASE_URL=$(LOAD_BASE_URL) python tools/http_load_test.py --base-url "$(LOAD_BASE_URL)" $(ARGS)

wheelhouse:
	$(info Building wheelhouse for offline installs)
	bash scripts/build_wheelhouse.sh

install-backend-offline: venv
	$(info Installing backend from local wheelhouse)
	$(VENV_PIP) install --no-index --find-links wheelhouse -r requirements.txt -r lunia_core/requirements/test.txt
	$(VENV_PIP) install --no-index --find-links wheelhouse pyyaml

offline-verify:
	$(info Running offline verification from wheelhouse)
	bash scripts/offline_verify.sh

no-placeholders:
	$(info Checking for TODO/placeholder markers)
	bash scripts/no_placeholders.sh

no-dead-controls:
	$(info Checking for dead/stub UI controls)
	bash scripts/no_dead_controls.sh

venv:
	python -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip

install-backend: venv
	$(info Installing backend dependencies into $(VENV))
	$(VENV_PIP) install -r requirements.txt -r lunia_core/requirements/test.txt

rc-verify: venv
	$(info Running release-candidate verification pipeline)
	@if [ "$(OFFLINE_CI)" = "1" ]; then \
		OFFLINE_CI=$(OFFLINE_CI) WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) PY_CMD=$(VENV_PYTHON) bash scripts/rc_verify.sh; \
	else \
		$(MAKE) install-backend && OFFLINE_CI=$(OFFLINE_CI) WHEELHOUSE_DIR=$(WHEELHOUSE_DIR) PY_CMD=$(VENV_PYTHON) bash scripts/rc_verify.sh; \
	fi
