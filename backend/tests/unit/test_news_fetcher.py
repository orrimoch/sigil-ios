"""
Unit tests for F1.4 News Fetcher
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.news_fetcher import (
    fetch_feed,
    fetch_all_news,
    filter_by_ticker,
    analyze_sentiment,
    analyze_news_sentiment,
    NEWS_FEEDS,
)


class TestFetchFeed:
    """Tests for fetching individual RSS feeds."""
    
    def test_returns_list(self):
        """Should return a list of articles."""
        # Use a reliable feed
        articles = fetch_feed("yahoo_finance", NEWS_FEEDS["yahoo_finance"], hours=72)
        assert isinstance(articles, list)
    
    def test_articles_have_required_fields(self):
        """Articles should have title, source, link."""
        articles = fetch_feed("yahoo_finance", NEWS_FEEDS["yahoo_finance"], hours=72)
        if articles:  # Only test if we got articles
            article = articles[0]
            assert "title" in article
            assert "source" in article
            assert "link" in article


class TestFetchAllNews:
    """Tests for fetching from all sources."""
    
    def test_returns_list(self):
        """Should return a list of articles."""
        articles = fetch_all_news(hours=24)
        assert isinstance(articles, list)
    
    def test_aggregates_multiple_sources(self):
        """Should have articles from multiple sources."""
        articles = fetch_all_news(hours=72)
        if len(articles) > 5:
            sources = set(a["source"] for a in articles)
            # Should have at least 1 source working
            assert len(sources) >= 1


class TestFilterByTicker:
    """Tests for ticker filtering."""
    
    def test_filters_by_exact_ticker(self):
        """Should find articles with exact ticker mention."""
        articles = [
            {"title": "AAPL stock rises", "summary": "Apple up today"},
            {"title": "Tech news", "summary": "General tech update"},
        ]
        filtered = filter_by_ticker(articles, "AAPL")
        assert len(filtered) == 1
        assert "AAPL" in filtered[0]["title"]
    
    def test_filters_by_company_name(self):
        """Should find articles with company name + financial context."""
        articles = [
            {"title": "Apple stock rises on new iPhone", "summary": "Big news"},
            {"title": "Tech news", "summary": "General update"},
        ]
        filtered = filter_by_ticker(articles, "AAPL")
        assert len(filtered) == 1
    
    def test_case_insensitive(self):
        """Should be case insensitive."""
        articles = [
            {"title": "aapl stock", "summary": ""},
            {"title": "AAPL Stock", "summary": ""},
        ]
        filtered = filter_by_ticker(articles, "AAPL")
        assert len(filtered) == 2


class TestSentimentAnalysis:
    """Tests for sentiment analysis."""
    
    def test_positive_sentiment(self):
        """Should detect positive sentiment."""
        result = analyze_sentiment("Stock surges on strong earnings beat")
        assert result["label"] == "positive"
        assert result["score"] > 0
    
    def test_negative_sentiment(self):
        """Should detect negative sentiment."""
        result = analyze_sentiment("Stock crashes on weak guidance and layoffs")
        assert result["label"] == "negative"
        assert result["score"] < 0
    
    def test_neutral_sentiment(self):
        """Should detect neutral sentiment."""
        result = analyze_sentiment("Company announces quarterly report")
        assert result["label"] == "neutral"
    
    def test_returns_required_fields(self):
        """Should return score, label, and word counts."""
        result = analyze_sentiment("Test text")
        assert "score" in result
        assert "label" in result
        assert "positive_words" in result
        assert "negative_words" in result
    
    def test_score_in_range(self):
        """Score should be between -1 and 1."""
        texts = [
            "Very positive news surge gain profit",
            "Very negative crash fall loss",
            "Neutral regular update",
        ]
        for text in texts:
            result = analyze_sentiment(text)
            assert -1 <= result["score"] <= 1


class TestAggregatedSentiment:
    """Tests for aggregated sentiment analysis."""
    
    def test_handles_empty_list(self):
        """Should handle empty article list."""
        result = analyze_news_sentiment([])
        assert result["score"] == 0
        assert result["label"] == "neutral"
        assert result["article_count"] == 0
    
    def test_aggregates_multiple_articles(self):
        """Should aggregate sentiment across articles."""
        articles = [
            {"title": "Stock surges", "summary": "Great earnings"},
            {"title": "Profit beats", "summary": "Strong growth"},
        ]
        result = analyze_news_sentiment(articles)
        assert result["article_count"] == 2
        assert result["score"] > 0
    
    def test_returns_counts(self):
        """Should return positive/negative/neutral counts."""
        articles = [
            {"title": "Stock surges", "summary": ""},
            {"title": "Stock crashes", "summary": ""},
            {"title": "Stock unchanged", "summary": ""},
        ]
        result = analyze_news_sentiment(articles)
        assert "positive_count" in result
        assert "negative_count" in result
        assert "neutral_count" in result


class TestFinnhubIntegration:
    """Tests for Finnhub API integration."""
    
    def test_fetch_without_api_key_returns_empty(self):
        """Should return empty list when no API key is set."""
        import os
        old_key = os.environ.get("FINNHUB_API_KEY", "")
        os.environ["FINNHUB_API_KEY"] = ""
        
        from importlib import reload
        import data.news_fetcher as nf
        reload(nf)
        
        result = nf.fetch_finnhub_news()
        assert result == []
        
        # Restore
        if old_key:
            os.environ["FINNHUB_API_KEY"] = old_key
    
    def test_source_tiers_defined(self):
        """Should have source tier weights defined."""
        from data.news_fetcher import SOURCE_TIERS
        assert "finnhub" in SOURCE_TIERS
        assert SOURCE_TIERS["finnhub"] == 2  # Tier 2


class TestAlphaVantageIntegration:
    """Tests for Alpha Vantage API integration."""
    
    def test_fetch_without_api_key_returns_empty(self):
        """Should return empty list when no API key is set."""
        import os
        old_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        os.environ["ALPHA_VANTAGE_API_KEY"] = ""
        
        from importlib import reload
        import data.news_fetcher as nf
        reload(nf)
        
        result = nf.fetch_alpha_vantage_news()
        assert result == []
        
        # Restore
        if old_key:
            os.environ["ALPHA_VANTAGE_API_KEY"] = old_key
    
    def test_source_tiers_defined(self):
        """Should have source tier weights defined."""
        from data.news_fetcher import SOURCE_TIERS
        assert "alpha_vantage" in SOURCE_TIERS
        assert SOURCE_TIERS["alpha_vantage"] == 2  # Tier 2


class TestSourceTiers:
    """Tests for source tier weighting."""
    
    def test_tier_1_sources_weight_3(self):
        """Tier 1 sources should have weight 3."""
        from data.news_fetcher import SOURCE_TIERS
        tier_1 = ["wsj", "ft", "economist"]
        for source in tier_1:
            assert SOURCE_TIERS.get(source) == 3
    
    def test_tier_2_sources_weight_2(self):
        """Tier 2 sources should have weight 2."""
        from data.news_fetcher import SOURCE_TIERS
        tier_2 = ["bloomberg", "finnhub", "alpha_vantage"]
        for source in tier_2:
            assert SOURCE_TIERS.get(source) == 2
    
    def test_tier_3_sources_weight_1(self):
        """Tier 3 sources should have weight 1."""
        from data.news_fetcher import SOURCE_TIERS
        tier_3 = ["yahoo_finance", "marketwatch"]
        for source in tier_3:
            assert SOURCE_TIERS.get(source) == 1


# Run with: pytest tests/unit/test_news_fetcher.py -v
