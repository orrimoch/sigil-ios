#!/bin/bash
# start_backend.sh - Start the Sigil backend server
# Used by LaunchAgent for auto-start on boot

set -e

BACKEND_DIR="$HOME/Desktop/Cool_Apps/TradingApp_iOS/backend"
LOG_FILE="/tmp/backend.log"
PID_FILE="/tmp/backend.pid"

cd "$BACKEND_DIR"

# Export environment
export AUTH_REQUIRED=true

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Backend already running (PID $OLD_PID)"
        exit 0
    fi
fi

# Start uvicorn
echo "Starting Sigil backend at $(date)"
nohup python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# Wait for startup
sleep 3

# Verify
if curl -s --max-time 5 http://127.0.0.1:8000/api/v1/health > /dev/null; then
    echo "Backend started successfully (PID $(cat $PID_FILE))"
    exit 0
else
    echo "Backend failed to start - check $LOG_FILE"
    exit 1
fi
