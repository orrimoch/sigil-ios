#!/bin/bash
# Daily portfolio snapshot cron job
# Run at 11 PM Israel time (after US market close)
# Crontab: 0 23 * * 1-5 /path/to/daily_snapshot_cron.sh

curl -s -X POST http://127.0.0.1:8000/api/v1/portfolio/snapshot/daily | python3 -m json.tool
