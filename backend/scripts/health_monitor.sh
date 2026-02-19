#!/bin/bash
# health_monitor.sh - Monitor backend health and auto-restart if down
# Designed to be run via cron every 5 minutes

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/health_monitor.log"
MAX_RETRIES=3
HEALTH_URL="http://127.0.0.1:8000/api/v1/health"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_health() {
    curl -s --max-time 10 "$HEALTH_URL" | grep -q '"status":"ok"'
    return $?
}

# Main
if check_health; then
    # Healthy - no action needed (don't log to reduce noise)
    exit 0
fi

log "Health check FAILED - attempting restart"

# Stop existing
"$SCRIPT_DIR/stop_backend.sh" >> "$LOG_FILE" 2>&1

sleep 2

# Start with retries
for i in $(seq 1 $MAX_RETRIES); do
    log "Restart attempt $i/$MAX_RETRIES"
    "$SCRIPT_DIR/start_backend.sh" >> "$LOG_FILE" 2>&1
    
    sleep 5
    
    if check_health; then
        log "Backend recovered after $i attempt(s)"
        exit 0
    fi
done

# All retries failed - alert needed
log "CRITICAL: Backend failed to recover after $MAX_RETRIES attempts"
echo "CRITICAL: Sigil backend failed to recover after $MAX_RETRIES restart attempts. Check /tmp/backend.log" | tee -a "$LOG_FILE"
exit 1
