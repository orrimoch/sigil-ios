#!/bin/bash
# Sigil Backend Startup Script

cd /Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend

# Load environment variables
set -a
source .env 2>/dev/null || true
set +a

# Start uvicorn with --loop asyncio to avoid uvloop permission issues
exec /usr/bin/python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --loop asyncio
