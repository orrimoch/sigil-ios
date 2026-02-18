#!/bin/bash
# Backup Sigil SQLite databases to iCloud
# Add to crontab: 0 3 * * * /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/backup_databases.sh

BACKUP_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Sigil_Backups"
SOURCE_DIR="/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/data"
DATE=$(date +%Y-%m-%d)
LOG="/tmp/sigil-backup.log"

echo "$(date): Starting backup..." >> "$LOG"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup databases
for db in sigil.db agent_memory.db crowd_wisdom.db risk_cache.db pattern_memory.db decision_pairs.db; do
    if [ -f "$SOURCE_DIR/$db" ]; then
        cp "$SOURCE_DIR/$db" "$BACKUP_DIR/${db%.db}_$DATE.db"
        echo "  Backed up $db" >> "$LOG"
    fi
done

# Backup important JSON files
for json in composite_scores.json fundamentals.json macro.json; do
    if [ -f "$SOURCE_DIR/$json" ]; then
        cp "$SOURCE_DIR/$json" "$BACKUP_DIR/${json%.json}_$DATE.json"
        echo "  Backed up $json" >> "$LOG"
    fi
done

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*_20*.db" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "*_20*.json" -mtime +7 -delete 2>/dev/null

echo "$(date): Backup complete" >> "$LOG"
