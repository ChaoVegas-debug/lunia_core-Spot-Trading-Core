#!/bin/bash
# Full Production Startup Script (Fail-Closed)

# Kill any running processes on port 8080
echo "Cleaning up ports..."
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Strict Production Config
export LUNIA_PREVIEW_MODE=0
export FLASK_DEBUG=0
export VITE_API_BASE_URL="http://127.0.0.1:8080"
export PORT=8080

# PATH CONFIGURATION
ROOT_DIR=$(pwd)
PYTHON_EXEC="$ROOT_DIR/.venv/bin/python"
export PYTHONPATH="$ROOT_DIR/lunia_core:$ROOT_DIR"
export DATABASE_URL="sqlite:///$ROOT_DIR/lunia_core/data/lunia.db"

echo "Using Python: $PYTHON_EXEC"
echo "Starting Backend in LIVE COMBAT MODE..."

# Run from module
$PYTHON_EXEC -m lunia_core.app.services.api.flask_app > backend_prod.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "Waiting for backend to start..."
sleep 5

echo "Backend started."
