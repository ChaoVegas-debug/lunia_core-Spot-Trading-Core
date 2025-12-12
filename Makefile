COMPOSE ?= docker compose
COMPOSE_FILES := -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml
ENV_FILE := lunia_core/.env

.PHONY: up down logs ps build deploy verify smoke backup restore restore-drill uptime

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

smoke:
	$(info Running smoke tests)
	bash scripts/smoke_test.sh

backup:
	BACKUP_DIR?=backups bash scripts/backup.sh

restore:
	@if [ -z "$(BACKUP)" ]; then echo "Set BACKUP=<archive> make restore" && exit 1; fi
	bash scripts/restore.sh $(BACKUP)

restore-drill:
	@echo "See docs/RESTORE_DRILL.md for the full drill. Example:" && echo "  make restore BACKUP=backups/lunia_backup_<ts>.tar.gz && make deploy && make smoke"

uptime:
	DOMAIN?=example.com bash scripts/uptime_check.sh
