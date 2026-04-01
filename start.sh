#!/bin/bash
# Servboard launcher — starts API (port 3000) and UI (port 3001)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="$SCRIPT_DIR/.venv/bin/python3"

echo "[Servboard] Cleaning up old processes on ports 3000/3001..."
sudo fuser -k 3000/tcp 3001/tcp 2>/dev/null || true
sleep 1

echo "[Servboard] Starting API server on port 3000..."
"$PYTHON" main.py > api.log 2>&1 &
API_PID=$!

echo "[Servboard] Starting UI server on port 3001..."
"$PYTHON" app.py > ui.log 2>&1 &
UI_PID=$!

echo "[Servboard] API PID=$API_PID (logs in api.log)"
echo "[Servboard] UI PID=$UI_PID (logs in ui.log)"
echo "[Servboard] Dashboard: http://0.0.0.0:3001"

# Wait for BOTH to finish (so systemd keeps running)
wait $API_PID $UI_PID
echo "[Servboard] Processes exited — shutting down..."
kill $API_PID $UI_PID 2>/dev/null

