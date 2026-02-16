# Sigil Infrastructure

## Launchd Services (macOS)

### com.sigil.backend.plist
Auto-starts the FastAPI backend server on boot.

**Install:**
```bash
cp infra/launchd/com.sigil.backend.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sigil.backend.plist
```

**Logs:**
- stdout: `/tmp/sigil_backend.log`
- stderr: `/tmp/sigil_backend_error.log`

### com.sigil.ibgateway.plist
Auto-starts IB Gateway for live trading.

**Prerequisites:**
- IBC installed in `~/ibc/`
- IB Gateway sparse image at `/tmp/ibgateway_volume.sparseimage`

**Install:**
```bash
cp infra/launchd/com.sigil.ibgateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sigil.ibgateway.plist
```

## Environment Variables

### Required
- `AUTH_REQUIRED=true` — Enable authentication (production)
- `DATABASE_URL` — PostgreSQL connection string (Railway provides this)

### LLM Provider (pick one)
- `LLM_PROVIDER=anthropic|openai|google`
- `ANTHROPIC_API_KEY` — For Claude
- `OPENAI_API_KEY` — For GPT
- `GOOGLE_API_KEY` — For Gemini

### IBKR
- `IB_GATEWAY_HOST=127.0.0.1`
- `IB_GATEWAY_PORT=4002`
- `IB_ACCOUNT_ID` — User's IB account (no default)

## Production Deployment Checklist

### Domain & Server
- [ ] Register sigil.app domain
- [ ] Set up Railway/Render account
- [ ] Configure SSL for api.sigil.app
- [ ] Point DNS to production server

### Database
- [x] PostgreSQL support ready (DATABASE_URL)
- [ ] Run initial migration on Railway PostgreSQL

### LLM
- [x] Provider abstraction layer (Anthropic/OpenAI/Google)
- [x] iOS Settings UI for provider display
- [x] Backend API: GET /api/v1/config/llm

### IBKR
- [x] Removed hardcoded credentials
- [x] iOS onboarding flow for account setup
- [ ] Document IBKR setup in Help section

### macOS (Mac mini)
- [x] Backend launchd plist
- [x] IB Gateway launchd plist
