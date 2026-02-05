"""
Tests for Article Processor (REC-173)
"""

import pytest
from datetime import datetime, timedelta

from src.scoring.article_processor import (
    ArticleProcessor,
    ProcessedArticle,
    process_articles_for_ticker,
    format_articles_for_llm,
    BOILERPLATE_RE,
    SOURCE_QUALITY,
)


class TestBoilerplateRemoval:
    """Test boilerplate text removal."""
    
    def test_removes_subscribe_text(self):
        """Should remove subscription prompts."""
        processor = ArticleProcessor()
        text = "Great earnings reported. Subscribe to our newsletter for more."
        cleaned = processor._clean_text(text)
        assert "Subscribe" not in cleaned
        assert "Great earnings reported" in cleaned
    
    def test_removes_click_here(self):
        """Should remove click here prompts."""
        processor = ArticleProcessor()
        text = "Apple stock rises. Click here to read more about it."
        cleaned = processor._clean_text(text)
        assert "Click here" not in cleaned
        assert "Apple stock rises" in cleaned
    
    def test_removes_copyright(self):
        """Should remove copyright notices."""
        processor = ArticleProcessor()
        text = "Quarterly results strong. © 2026 Reuters. All rights reserved."
        cleaned = processor._clean_text(text)
        assert "©" not in cleaned
        assert "All rights reserved" not in cleaned
        assert "Quarterly results strong" in cleaned
    
    def test_removes_advertisement(self):
        """Should remove advertisement markers."""
        processor = ArticleProcessor()
        text = "Stock up 5%. ADVERTISEMENT More news below."
        cleaned = processor._clean_text(text)
        assert "ADVERTISEMENT" not in cleaned
    
    def test_removes_brackets(self):
        """Should remove bracketed references."""
        processor = ArticleProcessor()
        text = "Revenue grew [1] according to reports [Reuters]."
        cleaned = processor._clean_text(text)
        assert "[1]" not in cleaned
        assert "[Reuters]" not in cleaned
    
    def test_preserves_content(self):
        """Should preserve meaningful content."""
        processor = ArticleProcessor()
        text = "Apple reported $89.5 billion in revenue, up 8% YoY"
        cleaned = processor._clean_text(text)
        assert cleaned == text


class TestSourceQuality:
    """Test source quality scoring."""
    
    def test_tier1_sources(self):
        """Tier 1 sources should score 3."""
        processor = ArticleProcessor()
        assert processor._get_source_quality("bloomberg") == 3
        assert processor._get_source_quality("Wall Street Journal") == 3
        assert processor._get_source_quality("financial times") == 3
        assert processor._get_source_quality("wsj_markets") == 3
    
    def test_tier2_sources(self):
        """Tier 2 sources should score 2."""
        processor = ArticleProcessor()
        assert processor._get_source_quality("reuters") == 2
        assert processor._get_source_quality("cnbc") == 2
        assert processor._get_source_quality("marketwatch") == 2
    
    def test_unknown_sources(self):
        """Unknown sources should score 1."""
        processor = ArticleProcessor()
        assert processor._get_source_quality("random_blog") == 1
        assert processor._get_source_quality("unknown") == 1


class TestRelevanceScoring:
    """Test article relevance scoring."""
    
    def test_ticker_in_headline_high_relevance(self):
        """Ticker in headline should have high relevance."""
        processor = ArticleProcessor()
        relevance = processor._calculate_relevance(
            "AAPL",
            "AAPL Stock Rises 5% on Earnings",
            "Apple reported strong results."
        )
        assert relevance == 1.0
    
    def test_ticker_in_summary(self):
        """Ticker in summary should have medium-high relevance."""
        processor = ArticleProcessor()
        relevance = processor._calculate_relevance(
            "AAPL",
            "Tech Stocks Rally Today",
            "AAPL led gains with a 5% increase."
        )
        assert 0.5 <= relevance < 1.0
    
    def test_company_name_relevance(self):
        """Company name mention should have medium relevance."""
        processor = ArticleProcessor()
        relevance = processor._calculate_relevance(
            "AAPL",
            "Apple Launches New iPhone",
            "The tech giant unveiled its latest smartphone."
        )
        assert relevance == 0.7
    
    def test_no_mention_low_relevance(self):
        """No mention should have low relevance."""
        processor = ArticleProcessor()
        relevance = processor._calculate_relevance(
            "AAPL",
            "Tech Sector Overview",
            "General market analysis and trends."
        )
        assert relevance == 0.3


class TestArticleProcessing:
    """Test full article processing."""
    
    @pytest.fixture
    def sample_articles(self):
        """Sample articles for testing."""
        return [
            {
                "title": "Apple Reports Record Revenue",
                "summary": "Apple Inc. reported $89.5B revenue. Subscribe now!",
                "source": "bloomberg",
                "published": datetime.now().isoformat(),
            },
            {
                "title": "AAPL Stock Analysis",
                "summary": "Technical analysis of AAPL shows bullish patterns.",
                "source": "marketwatch",
                "published": (datetime.now() - timedelta(days=1)).isoformat(),
            },
            {
                "title": "Tech Sector Update",
                "summary": "General tech news. Click here for more. © 2026",
                "source": "unknown_blog",
                "published": (datetime.now() - timedelta(days=2)).isoformat(),
            },
        ]
    
    def test_processes_articles(self, sample_articles):
        """Should process and return articles."""
        processor = ArticleProcessor(max_articles_per_ticker=5)
        processed = processor.process_articles("AAPL", sample_articles)
        
        assert len(processed) == 3
        assert all(isinstance(p, ProcessedArticle) for p in processed)
    
    def test_sorts_by_quality(self, sample_articles):
        """Should sort by quality score (descending)."""
        processor = ArticleProcessor()
        processed = processor.process_articles("AAPL", sample_articles)
        
        # Bloomberg (tier 1) should be first
        assert processed[0].source == "Bloomberg"
        assert processed[0].quality_score == 3
    
    def test_limits_articles(self, sample_articles):
        """Should limit to max_articles."""
        processor = ArticleProcessor(max_articles_per_ticker=2)
        processed = processor.process_articles("AAPL", sample_articles)
        
        assert len(processed) == 2
    
    def test_cleans_content(self, sample_articles):
        """Should clean boilerplate from content."""
        processor = ArticleProcessor()
        processed = processor.process_articles("AAPL", sample_articles)
        
        # Check that subscribe/click/copyright removed
        for p in processed:
            assert "Subscribe" not in p.content
            assert "Click here" not in p.content
            assert "©" not in p.content
    
    def test_truncates_long_content(self):
        """Should truncate long content."""
        processor = ArticleProcessor(max_content_length=50)
        articles = [{
            "title": "Test",
            "summary": "A" * 200,
            "source": "test",
            "published": datetime.now().isoformat(),
        }]
        
        processed = processor.process_articles("AAPL", articles)
        assert len(processed[0].content) <= 53  # 50 + "..."
    
    def test_handles_empty_articles(self):
        """Should handle empty article list."""
        processor = ArticleProcessor()
        processed = processor.process_articles("AAPL", [])
        assert processed == []
    
    def test_skips_invalid_articles(self):
        """Should skip articles without headlines."""
        processor = ArticleProcessor()
        articles = [
            {"summary": "No title here", "source": "test"},
            {"title": "", "source": "test"},
            {"title": "Valid Title", "summary": "Content", "source": "test"},
        ]
        
        processed = processor.process_articles("AAPL", articles)
        assert len(processed) == 1
        assert processed[0].headline == "Valid Title"


class TestDateFormatting:
    """Test date formatting."""
    
    def test_today_format(self):
        """Today's date should show 'Today HH:MM'."""
        processor = ArticleProcessor()
        now = datetime.now().isoformat()
        formatted = processor._format_date(now)
        assert formatted.startswith("Today")
    
    def test_yesterday_format(self):
        """Yesterday's date should show 'Yesterday HH:MM'."""
        processor = ArticleProcessor()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        formatted = processor._format_date(yesterday)
        assert formatted.startswith("Yesterday")
    
    def test_older_date_format(self):
        """Older dates should show 'Mon DD, YYYY'."""
        processor = ArticleProcessor()
        old_date = "2026-01-15T10:00:00"
        formatted = processor._format_date(old_date)
        assert "Jan 15, 2026" in formatted
    
    def test_handles_empty_date(self):
        """Should handle empty date."""
        processor = ArticleProcessor()
        assert processor._format_date("") == "Unknown"
        assert processor._format_date(None) == "Unknown"


class TestPromptFormatting:
    """Test LLM prompt formatting."""
    
    def test_formats_articles_for_prompt(self):
        """Should format articles for LLM prompt."""
        processor = ArticleProcessor()
        processed = [
            ProcessedArticle(
                ticker="AAPL",
                headline="Apple Revenue Up",
                content="Strong quarterly results.",
                source="Bloomberg",
                published="Today 10:00",
                quality_score=3,
                relevance_score=1.0,
                word_count=3,
            )
        ]
        
        formatted = processor.format_for_prompt(processed)
        
        assert "Article 1" in formatted
        assert "Apple Revenue Up" in formatted
        assert "Bloomberg" in formatted
        assert "Strong quarterly results" in formatted
    
    def test_formats_multiple_articles(self):
        """Should number multiple articles."""
        processor = ArticleProcessor()
        processed = [
            ProcessedArticle("AAPL", f"Headline {i}", "Content", "Source", "Today", 2, 0.5, 1)
            for i in range(3)
        ]
        
        formatted = processor.format_for_prompt(processed)
        
        assert "Article 1" in formatted
        assert "Article 2" in formatted
        assert "Article 3" in formatted
    
    def test_handles_empty_list(self):
        """Should handle empty article list."""
        processor = ArticleProcessor()
        formatted = processor.format_for_prompt([])
        assert "No recent news" in formatted


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_process_articles_for_ticker(self):
        """Should process articles via convenience function."""
        articles = [
            {"title": "AAPL News", "summary": "Content", "source": "test", "published": "2026-02-05"}
        ]
        
        processed = process_articles_for_ticker("AAPL", articles, max_articles=5)
        
        assert len(processed) == 1
        assert processed[0].ticker == "AAPL"
    
    def test_format_articles_for_llm(self):
        """Should format articles via convenience function."""
        articles = [
            {"title": "AAPL News", "summary": "Content", "source": "test", "published": "2026-02-05"}
        ]
        
        formatted = format_articles_for_llm("AAPL", articles)
        
        assert "AAPL News" in formatted
        assert "Article 1" in formatted


class TestSourceNormalization:
    """Test source name normalization."""
    
    def test_removes_prefixes(self):
        """Should remove provider prefixes."""
        processor = ArticleProcessor()
        assert processor._normalize_source("finnhub_reuters") == "Reuters"
        assert processor._normalize_source("alphavantage_wsj") == "Wsj"
        assert processor._normalize_source("yahoo_finance") == "Finance"
    
    def test_preserves_simple_names(self):
        """Should preserve simple source names."""
        processor = ArticleProcessor()
        assert processor._normalize_source("bloomberg") == "Bloomberg"
        assert processor._normalize_source("Reuters") == "Reuters"


class TestBatchByTicker:
    """Test batching articles by ticker."""
    
    def test_batch_by_ticker(self):
        """Should batch articles by ticker."""
        processor = ArticleProcessor(max_articles_per_ticker=2)
        articles = [
            {"title": "AAPL up 5%", "summary": "Apple gains", "source": "test", "published": "2026-02-05"},
            {"title": "MSFT launches", "summary": "Microsoft news", "source": "test", "published": "2026-02-05"},
            {"title": "More Apple news", "summary": "AAPL continues", "source": "test", "published": "2026-02-05"},
        ]
        
        batched = processor.batch_by_ticker(articles, ["AAPL", "MSFT", "GOOGL"])
        
        assert len(batched["AAPL"]) == 2
        assert len(batched["MSFT"]) == 1
        assert len(batched["GOOGL"]) == 0
    
    def test_batch_handles_company_names(self):
        """Should match articles by company name."""
        processor = ArticleProcessor()
        articles = [
            {"title": "Apple launches new product", "summary": "iPhone 17", "source": "test", "published": "2026-02-05"},
        ]
        
        batched = processor.batch_by_ticker(articles, ["AAPL"])
        
        assert len(batched["AAPL"]) == 1
