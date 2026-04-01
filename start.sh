#!/bin/bash
# Servboard launcher — starts API (port 3000) and UI (port 3001)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="$SCRIPT_DIR/.venv/bin/python3"

echo "[Servboard] Starting API server on port 3000..."
"$PYTHON" main.py &
API_PID=$!

echo "[Servboard] Starting UI server on port 3001..."
"$PYTHON" app.py &
UI_PID=$!

echo "[Servboard] API PID=$API_PID  UI PID=$UI_PID"
echo "[Servboard] Dashboard: http://0.0.0.0:3001"
echo "[Servboard] API docs:  http://0.0.0.0:3000/docs"

# Wait for either process to exit
wait -n $API_PID $UI_PID
echo "[Servboard] A process exited — shutting down..."
kill $API_PID $UI_PID 2>/dev/null
