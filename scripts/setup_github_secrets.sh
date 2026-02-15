#!/bin/bash
# Setup GitHub Secrets for Sigil CI/CD
# Run this script from the project root with appropriate permissions

set -e

echo "=== Setting up GitHub Secrets for Sigil ==="
echo ""
echo "This script will set the required secrets for GitHub Actions."
echo "You'll be prompted to enter each secret value."
echo ""

# Required secrets
echo "--- Required Secrets ---"

echo "1. ANTHROPIC_API_KEY (required for sentiment analysis)"
gh secret set ANTHROPIC_API_KEY

echo ""
echo "--- Optional Secrets (press Enter to skip) ---"

read -p "Set REDDIT_CLIENT_ID? (y/N): " set_reddit
if [[ "$set_reddit" =~ ^[Yy]$ ]]; then
    gh secret set REDDIT_CLIENT_ID
    gh secret set REDDIT_CLIENT_SECRET
fi

read -p "Set FINNHUB_API_KEY? (y/N): " set_finnhub
if [[ "$set_finnhub" =~ ^[Yy]$ ]]; then
    gh secret set FINNHUB_API_KEY
fi

echo ""
echo "=== Secrets configured! ==="
echo "Verify with: gh secret list"
