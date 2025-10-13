#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="/opt/lunia_core"
LOG_FILE="/var/log/lunia_install.log"

mkdir -p "$(dirname "${LOG_FILE}")"
touch "${LOG_FILE}"
chmod 644 "${LOG_FILE}"

log() {
  echo "$(date -Iseconds) $*" | tee -a "${LOG_FILE}"
}

trap 'log "Installation failed on line ${LINENO}"' ERR

copy_repo() {
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$1/" "$2/"
  else
    mkdir -p "$2"
    cp -a "$1/"* "$2/"
  fi
}

log "Installing Lunia Core to ${TARGET_DIR}"
copy_repo "${REPO_DIR}" "${TARGET_DIR}"

cd "${TARGET_DIR}"
python3 -m venv .venv

if [[ -n "${HTTP_PROXY:-}" ]]; then
  export http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY:-${HTTP_PROXY}}"
  log "Using proxy settings HTTP_PROXY=${HTTP_PROXY}"
fi

"${TARGET_DIR}/.venv/bin/pip" install --upgrade pip | tee -a "${LOG_FILE}"
"${TARGET_DIR}/.venv/bin/pip" install -r requirements/base.txt | tee -a "${LOG_FILE}"

if [[ "${INSTALL_BACKTEST:-0}" == "1" ]]; then
  if [[ -f requirements/backtester.txt ]]; then
    log "Installing backtester dependencies"
    "${TARGET_DIR}/.venv/bin/pip" install -r requirements/backtester.txt | tee -a "${LOG_FILE}"
  else
    log "WARNING: requirements/backtester.txt not found; skipping backtester dependencies"
  fi
fi

if [ ! -f .env ]; then
  cp .env.example .env
  log "Created .env from template"
fi
chmod 600 .env || true

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

install -m 644 infra/systemd/lunia_api.service /etc/systemd/system/lunia_api.service
install -m 644 infra/systemd/lunia_bot.service /etc/systemd/system/lunia_bot.service
install -m 644 infra/systemd/lunia_sched.service /etc/systemd/system/lunia_sched.service
install -m 644 infra/systemd/lunia_arb.service /etc/systemd/system/lunia_arb.service
if [[ -f infra/logrotate/lunia ]]; then
  install -m 644 infra/logrotate/lunia /etc/logrotate.d/lunia
  log "Installed logrotate configuration"
fi
systemctl daemon-reload
systemctl enable --now lunia_api
systemctl enable --now lunia_sched
systemctl enable --now lunia_arb

if grep -q '^TELEGRAM_BOT_TOKEN=' .env && [[ -n "$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d'=' -f2-)" ]]; then
  systemctl enable --now lunia_bot
  log "Telegram bot enabled"
else
  log "Telegram bot token missing; skipping lunia_bot enable"
fi

REDIS_URL_DEFAULT="redis://localhost:6379/0"
REDIS_URL="${REDIS_URL:-${REDIS_URL_DEFAULT}}"
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -u "${REDIS_URL}" ping >/dev/null 2>&1; then
    log "Redis reachable at ${REDIS_URL}"
  else
    log "WARNING: Redis at ${REDIS_URL} not reachable"
  fi
else
  log "redis-cli not installed; cannot verify Redis connectivity"
fi

log "Installation complete. Useful commands:"
log "  systemctl status lunia_api"
log "  systemctl status lunia_sched"
log "  systemctl status lunia_arb"
log "  curl http://localhost:8080/health"
