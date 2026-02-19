#!/bin/bash
# stop_backend.sh - Stop the Sigil backend server

PID_FILE="/tmp/backend.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping backend (PID $PID)"
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Backend stopped"
    else
        echo "No process at PID $PID"
        rm -f "$PID_FILE"
    fi
else
    # Fallback: kill by pattern
    pkill -f 'uvicorn.*main:app' 2>/dev/null && echo "Killed uvicorn processes" || echo "No uvicorn processes found"
fi
