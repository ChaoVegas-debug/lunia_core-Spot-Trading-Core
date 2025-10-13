PYTHON=python3
VENV=.venv
PIP=$(VENV)/bin/pip
PY=$(VENV)/bin/python

.PHONY: setup run bot sched arb test test-offline up up-monitoring

setup:
$(PYTHON) -m venv $(VENV)
$(PIP) install --upgrade pip
$(PIP) install -r requirements/base.txt

run:
$(PY) -m flask --app app.services.api.flask_app run --host=0.0.0.0 --port=$${PORT:-8080}

bot:
$(PY) -m app.services.telegram.bot

sched:
$(PY) -m app.services.scheduler.worker

arb:
$(PY) -m app.services.arbitrage.worker

test:
$(PY) -m pytest -q

test-offline:
$(PY) -m pytest -q -k "not requires_flask"

up:
docker compose -f infra/docker-compose.yml up -d --build

up-monitoring:
docker compose -f infra/docker-compose.yml --profile monitoring up -d --build
