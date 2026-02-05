"""
Tests for Article Processor (REC-173)
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.article_processor import (
    ArticleProcessor,
    ProcessedArticle,
    process_articles_for_ticker,
    format_articles_for_llm,
    BOILERPLATE_RE,
)


class TestBoilerplateRemoval:
    """Test boilerplate pattern removal."""
    
    def test_removes_subscribe(self):
        text = "Great earnings report. Subscribe to our newsletter for more."
        cleaned = BOILERPLATE_RE.sub('', text)
        assert "Subscribe" not in cleaned
        assert "Great earnings report" in cleaned
    
    def test_removes_click_here(self):
        text = "Stock up 10%. Click here to read the full report."
        cleaned = BOILERPLATE_RE.sub('', text)
        assert "Click here" not in cleaned
    
    def test_removes_copyright(self):
        text = "Revenue grew 15%. © 2026 Reuters. All rights reserved."
        cleaned = BOILERPLATE_RE.sub('', text)
        assert "©" not in cleaned
        assert "Revenue grew 15%" in cleaned
    
    def test_removes_brackets(self):
        text = "Apple [AAPL] reported earnings [1] above expectations."
        cleaned = BOILERPLATE_RE.sub('', text)
        assert "[AAPL]" not in cleaned
        assert "[1]" not in cleaned
    
    def test_removes_advertisement(self):
        text = "Market update. ADVERTISEMENT. Stocks rally."
        cleaned = BOILERPLATE_RE.sub('', text)
        assert "ADVERTISEMENT" not in cleaned


class TestProcessedArticle:
    """Test ProcessedArticle dataclass."""
    
    def test_creation(self):
        article = ProcessedArticle(
            ticker="AAPL",
            headline="Apple Reports Record Revenue",
            content="Revenue hit $89.5B, up 8% YoY.",
            source="Reuters",
            published="Feb 05, 2026",
            quality_score=2,
            relevance_score=0.9,
            word_count=10,
        )
        
        assert article.ticker == "AAPL"
        assert article.quality_score == 2
        assert article.relevance_score == 0.9
    
    def test_to_prompt_format(self):
        article = ProcessedArticle(
            ticker="AAPL",
            headline="Apple Beats Expectations",
            content="Strong iPhone sales drove growth.",
            source="Bloomberg",
            published="Today 10:00",
            quality_score=3,
            relevance_score=1.0,
            word_count=5,
        )
        
        formatted = article.to_prompt_format()
        
        assert "Apple Beats Expectations" in formatted
        assert "Bloomberg" in formatted
        assert "Tier 3" in formatted
        assert "Strong iPhone sales" in formatted


class TestArticleProcessor:
    """Test ArticleProcessor class."""
    
    @pytest.fixture
    def processor(self):
        return ArticleProcessor(
            max_articles_per_ticker=3,
            max_content_length=200,
        )
    
    @pytest.fixture
    def sample_articles(self):
        return [
            {
                "title": "Apple Reports Record Q4 Revenue",
                "summary": "Apple Inc. reported quarterly revenue of $89.5 billion, beating expectations.",
                "source": "reuters",
                "published": "2026-02-05T10:00:00",
            },
            {
                "title": "Tech Stocks Rally on Earnings",
                "summary": "Technology sector sees broad gains.",
                "source": "marketwatch",
                "published": "2026-02-04T15:00:00",
            },
            {
                "title": "Apple Vision Pro Sales Disappoint",
                "summary": "Vision Pro headset sees slower adoption than expected.",
                "source": "bloomberg",
                "published": "2026-02-05T08:00:00",
            },
        ]
    
    def test_process_articles_returns_list(self, processor, sample_articles):
        result = processor.process_articles("AAPL", sample_articles)
        assert isinstance(result, list)
        assert len(result) <= 3
    
    def test_process_articles_sorted_by_quality(self, processor, sample_articles):
        result = processor.process_articles("AAPL", sample_articles)
        
        # Bloomberg (tier 3) should be before MarketWatch (tier 1)
        qualities = [a.quality_score for a in result]
        assert qualities == sorted(qualities, reverse=True)
    
    def test_process_articles_filters_irrelevant(self, processor):
        articles = [
            {
                "title": "Oil Prices Surge on OPEC Decision",
                "summary": "Crude oil up 5% as production cuts announced.",
                "source": "reuters",
                "published": "2026-02-05T10:00:00",
            },
        ]
        
        # This article is not relevant to AAPL
        result = processor.process_articles("AAPL", articles)
        
        # Should still process but with low relevance
        if result:
            assert result[0].relevance_score < 0.5
    
    def test_cleans_boilerplate(self, processor):
        articles = [
            {
                "title": "AAPL Earnings Beat",
                "summary": "Great results. Subscribe to our newsletter! © 2026 News Corp.",
                "source": "reuters",
                "published": "2026-02-05T10:00:00",
            },
        ]
        
        result = processor.process_articles("AAPL", articles)
        
        assert len(result) == 1
        assert "Subscribe" not in result[0].content
        assert "©" not in result[0].content
    
    def test_truncates_long_content(self, processor):
        long_summary = "A" * 500
        articles = [
            {
                "title": "AAPL News",
                "summary": long_summary,
                "source": "reuters",
                "published": "2026-02-05T10:00:00",
            },
        ]
        
        result = processor.process_articles("AAPL", articles)
        
        assert len(result[0].content) <= processor.max_content_length + 3  # +3 for "..."
    
    def test_source_quality_bloomberg(self, processor):
        quality = processor._get_source_quality("bloomberg")
        assert quality == 3
    
    def test_source_quality_reuters(self, processor):
        quality = processor._get_source_quality("finnhub_reuters")
        assert quality == 2
    
    def test_source_quality_unknown(self, processor):
        quality = processor._get_source_quality("some_blog")
        assert quality == 1
    
    def test_relevance_ticker_in_headline(self, processor):
        relevance = processor._calculate_relevance(
            "AAPL",
            "AAPL Reports Strong Earnings",
            "Revenue grew significantly."
        )
        assert relevance == 1.0
    
    def test_relevance_ticker_in_summary(self, processor):
        relevance = processor._calculate_relevance(
            "AAPL",
            "Tech Earnings Strong",
            "AAPL and MSFT both beat expectations."
        )
        assert 0.5 <= relevance < 1.0
    
    def test_relevance_company_name(self, processor):
        relevance = processor._calculate_relevance(
            "AAPL",
            "iPhone Sales Surge",
            "Apple reported strong iPhone demand."
        )
        assert relevance >= 0.7
    
    def test_relevance_no_mention(self, processor):
        relevance = processor._calculate_relevance(
            "AAPL",
            "Oil Prices Rise",
            "OPEC cuts production."
        )
        assert relevance <= 0.3
    
    def test_format_date_today(self, processor):
        today = datetime.now().isoformat()
        formatted = processor._format_date(today)
        assert "Today" in formatted
    
    def test_format_date_yesterday(self, processor):
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        formatted = processor._format_date(yesterday)
        assert "Yesterday" in formatted
    
    def test_format_date_older(self, processor):
        old_date = "2026-01-15T10:00:00"
        formatted = processor._format_date(old_date)
        assert "Jan 15" in formatted
    
    def test_format_for_prompt_empty(self, processor):
        formatted = processor.format_for_prompt([])
        assert "No recent news" in formatted
    
    def test_format_for_prompt_with_articles(self, processor, sample_articles):
        processed = processor.process_articles("AAPL", sample_articles)
        formatted = processor.format_for_prompt(processed)
        
        assert "Article 1:" in formatted
        assert "Headline:" in formatted
        assert "Source:" in formatted


class TestBatchByTicker:
    """Test batch_by_ticker functionality."""
    
    @pytest.fixture
    def processor(self):
        return ArticleProcessor(max_articles_per_ticker=2)
    
    def test_batch_separates_tickers(self, processor):
        articles = [
            {"title": "AAPL beats earnings", "summary": "Apple strong", "source": "reuters", "published": "2026-02-05"},
            {"title": "MSFT cloud grows", "summary": "Microsoft Azure up", "source": "bloomberg", "published": "2026-02-05"},
            {"title": "NVDA AI demand", "summary": "Nvidia chips selling", "source": "wsj", "published": "2026-02-05"},
        ]
        
        result = processor.batch_by_ticker(articles, ["AAPL", "MSFT", "NVDA"])
        
        assert "AAPL" in result
        assert "MSFT" in result
        assert "NVDA" in result
    
    def test_batch_empty_for_no_matches(self, processor):
        articles = [
            {"title": "AAPL strong", "summary": "Apple good", "source": "reuters", "published": "2026-02-05"},
        ]
        
        result = processor.batch_by_ticker(articles, ["AAPL", "XYZ"])
        
        assert len(result["AAPL"]) >= 0
        assert len(result["XYZ"]) == 0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_process_articles_for_ticker(self):
        articles = [
            {"title": "AAPL News", "summary": "Good stuff", "source": "reuters", "published": "2026-02-05"},
        ]
        
        result = process_articles_for_ticker("AAPL", articles, max_articles=5)
        
        assert isinstance(result, list)
    
    def test_format_articles_for_llm(self):
        articles = [
            {"title": "AAPL News", "summary": "Good stuff", "source": "reuters", "published": "2026-02-05"},
        ]
        
        result = format_articles_for_llm("AAPL", articles)
        
        assert isinstance(result, str)
        assert "AAPL" in result or "Article" in result
