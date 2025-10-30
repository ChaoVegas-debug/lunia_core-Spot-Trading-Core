#!/usr/bin/env bash
set -euo pipefail
say() { echo -e "$@"; }

# === 0. Проверка репозитория ===
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  say "❌ Not a git repo. Run inside repo root."; exit 1
fi
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# === 1. Проверим ключевые файлы Phase 2A ===
need_files=(
  "lunia_core/requirements/base_minimal.txt"
  "lunia_core/requirements/base.txt"
  "lunia_core/requirements/telegram.txt"
  "requirements.txt"
  "scripts/preflight.py"
  "scripts/ensure-no-telegram.sh"
  "scripts/health/all_checks.py"
  ".github/workflows/verify.yml"
  ".env.example.3a"
  "tests/test_telegram_optional.py"
  "tests/test_health_scripts.py"
)
missing=0
for f in "${need_files[@]}"; do
  [[ -f "$f" ]] || { say "❌ missing: $f"; missing=1; }
done
if [[ $missing -eq 1 ]]; then
  say "⛔ Phase 2A baseline incomplete — fix missing files first."; exit 2
fi

# === 2. Восстановление ветки main ===
current_branch="$(git rev-parse --abbrev-ref HEAD || echo HEAD)"
sync_target="$(git rev-parse HEAD)"
git fetch --all || true
if ! git show-ref --verify --quiet refs/heads/main; then
  say "ℹ️ main not found — creating from HEAD"
  git branch -f main "$sync_target"
fi

say "→ checkout main"
git checkout -f main
say "→ hard-sync main to current content"
git reset --hard "$sync_target"
git commit --allow-empty -m "sync(main): reattach verified Phase 2A baseline"

# === 3. Локальные проверки (OFFLINE-safe) ===
say "→ preflight"
python scripts/preflight.py
say "→ guard"
bash scripts/ensure-no-telegram.sh
say "→ infra health (OFFLINE)"
OFFLINE_CI=1 python scripts/health/all_checks.py || true
say "→ smoke tests"
pytest -q -k "telegram_optional or health_scripts" || true

# === 4. Пушим main ===
say "→ pushing main"
set +e
git push origin main
code=$?
set -e
if [[ $code -eq 0 ]]; then
  say "🎉 main successfully pushed and recovered."
  exit 0
fi

# === 5. Fallback: создаём bundle ===
BUNDLE="lunia_core_phase2a_main.bundle"
say "⚠️ Push blocked (code=$code). Creating bundle: $BUNDLE"
git bundle create "$BUNDLE" main
say "📦 Bundle ready: $BUNDLE"
say "To push from your local machine:\n\n  git clone <YOUR_REPO_URL> lunia_core\n  cd lunia_core\n  git pull --allow-unrelated-histories ../$BUNDLE main\n  git push origin main\n"
exit 0
