#!/bin/bash
# backup_databases.sh - Daily SQLite database backup
# Keeps last 7 days of backups

set -e

DATA_DIR="$HOME/Desktop/Cool_Apps/TradingApp_iOS/backend/data"
BACKUP_DIR="$HOME/Desktop/Cool_Apps/TradingApp_iOS/backend/backups"
DATE=$(date +%Y-%m-%d)
BACKUP_PATH="$BACKUP_DIR/$DATE"
RETENTION_DAYS=7

# Create backup directory
mkdir -p "$BACKUP_PATH"

# List of databases to backup
DATABASES=(
    "agent_memory.db"
    "crowd_wisdom.db"
    "decision_pairs.db"
    "pattern_memory.db"
    "pipeline.db"
    "risk_cache.db"
    "scores.db"
    "sigil.db"
    "stocks.db"
    "trading.db"
)

echo "=== Sigil Database Backup - $DATE ==="
BACKED_UP=0
FAILED=0

for db in "${DATABASES[@]}"; do
    if [ -f "$DATA_DIR/$db" ]; then
        # Use SQLite backup command for safe copy
        if sqlite3 "$DATA_DIR/$db" ".backup '$BACKUP_PATH/$db'" 2>/dev/null; then
            SIZE=$(du -h "$BACKUP_PATH/$db" | cut -f1)
            echo "✓ $db ($SIZE)"
            ((BACKED_UP++))
        else
            # Fallback to cp if sqlite3 backup fails
            cp "$DATA_DIR/$db" "$BACKUP_PATH/$db"
            echo "✓ $db (copied)"
            ((BACKED_UP++))
        fi
    else
        echo "⚠ $db not found"
        ((FAILED++))
    fi
done

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
echo "---"
echo "Backed up: $BACKED_UP databases ($TOTAL_SIZE)"
[ $FAILED -gt 0 ] && echo "Missing: $FAILED databases"

# Cleanup old backups
echo "---"
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null
REMAINING=$(ls -1 "$BACKUP_DIR" | wc -l | tr -d ' ')
echo "Backup folders retained: $REMAINING"

echo "=== Backup complete ==="
