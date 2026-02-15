# GitHub Secrets Configuration

## Required Secrets

| Secret | Description | Required |
|--------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key for sentiment analysis | ✅ Yes |

## Optional Secrets

| Secret | Description | Required |
|--------|-------------|----------|
| `REDDIT_CLIENT_ID` | Reddit API client ID for crowd wisdom | No |
| `REDDIT_CLIENT_SECRET` | Reddit API client secret | No |
| `FINNHUB_API_KEY` | Finnhub API for additional news | No |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage for additional data | No |
| `OPENAI_API_KEY` | Alternative to Anthropic | No |
| `GOOGLE_API_KEY` | Alternative to Anthropic | No |

## Setup

Run the setup script:
```bash
./scripts/setup_github_secrets.sh
```

Or set manually:
```bash
gh secret set ANTHROPIC_API_KEY
```

## Verification

```bash
gh secret list
```
