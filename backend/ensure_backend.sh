#!/bin/bash
# Ensure Sigil backend is running
# Add to crontab: */5 * * * * /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/ensure_backend.sh

cd /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend

# Check if backend is responding
if ! curl -s --max-time 5 http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "$(date): Backend not responding, starting..." >> /tmp/sigil-backend-watchdog.log
    
    # Kill any zombie processes
    pkill -f "uvicorn.*8000" 2>/dev/null
    sleep 2
    
    # Start backend
    source .env 2>/dev/null
    nohup python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 >> /tmp/sigil-backend.log 2>&1 &
    
    echo "$(date): Backend started (PID $!)" >> /tmp/sigil-backend-watchdog.log
fi
