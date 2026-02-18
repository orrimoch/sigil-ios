#!/bin/bash
# Health check for Sigil backend - sends alert if down
# Add to crontab: */10 * * * * /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/health_check.sh

HEALTH_URL="http://localhost:8000/api/v1/health"
LOG="/tmp/sigil-health.log"
ALERT_FILE="/tmp/sigil-alert-sent"

# Check health
if curl -s --max-time 10 "$HEALTH_URL" | grep -q '"status":"ok"'; then
    # Backend is healthy
    if [ -f "$ALERT_FILE" ]; then
        # Was down, now recovered
        rm "$ALERT_FILE"
        echo "$(date): Backend recovered" >> "$LOG"
        osascript -e 'display notification "Sigil backend is back online" with title "Sigil ✅"'
    fi
else
    # Backend is down
    echo "$(date): Backend DOWN!" >> "$LOG"
    
    # Only alert once (don't spam)
    if [ ! -f "$ALERT_FILE" ]; then
        touch "$ALERT_FILE"
        osascript -e 'display notification "Sigil backend is not responding!" with title "Sigil ⚠️" sound name "Basso"'
    fi
    
    # Try to restart
    /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/ensure_backend.sh
fi
