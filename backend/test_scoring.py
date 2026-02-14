#!/usr/bin/env python3
import os
import sys

# Set key FIRST
# API key should be set in environment or .env file
if not os.getenv('ANTHROPIC_API_KEY'):
    print('Warning: ANTHROPIC_API_KEY not set')

from datetime import date
from pathlib import Path

# Import after key is set
from src.sentiment_historical.kaggle_provider import create_kaggle_provider
from src.sentiment_historical.sentiment_scorer import HistoricalSentimentScorer

print("Testing scorer...")
scorer = HistoricalSentimentScorer()
print(f"Available: {scorer.is_available}")

# Test 5 headlines
provider = create_kaggle_provider(project_root=Path('/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS'))
articles = provider.get_articles_for_universe(date(2019, 6, 1), date(2019, 6, 30))[:5]

print(f"\nScoring {len(articles)} test articles...")
for article in articles:
    score = scorer.score_headline(article.ticker, article.headline)
    print(f"  {article.ticker}: {score} - {article.headline[:50]}...")

print("\nDone!")
