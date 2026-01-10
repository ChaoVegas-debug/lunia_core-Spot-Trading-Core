#!/bin/bash

# Kill any running processes on ports 8080 (backend) and 5173 (frontend)
echo "Cleaning up ports..."
lsof -ti:8080 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

export LUNIA_PREVIEW_MODE=1
export CORS_ALLOW_ORIGINS="*"
export VITE_PREVIEW_MODE=1
VITE_PREVIEW_SIMULATION=1
export VITE_API_BASE_URL="http://localhost:8080"
export FLASK_DEBUG=1
export PORT=8080

# PATH CONFIGURATION
ROOT_DIR=$(pwd)
PYTHON_EXEC="$ROOT_DIR/.venv/bin/python"
NODE_BIN="$ROOT_DIR/node_runtime/bin"
export PATH="$NODE_BIN:$PATH"
export PYTHONPATH="$ROOT_DIR/lunia_core:$ROOT_DIR"
export DATABASE_URL="sqlite:///$ROOT_DIR/lunia_core/data/lunia.db"

echo "Using Python: $PYTHON_EXEC"
echo "Using Node Bin: $NODE_BIN"

echo "Starting Backend in PREVIEW MODE..."
# Run backend in background as module
$PYTHON_EXEC -m lunia_core.app.services.api.flask_app > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "Waiting for backend to start..."
sleep 5

echo "Starting Frontend in PREVIEW MODE..."
cd frontend
# Using npm from PATH (which is now correctly set)
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo "Preview Mode Started!"
echo "Backend: http://localhost:8080"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop."

wait
