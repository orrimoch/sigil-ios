"""
Article Processor for LLM Sentiment Analysis (REC-173)

Cleans, batches, and formats news articles for optimal LLM analysis.
- Removes boilerplate text
- Extracts relevant content
- Batches by ticker (max articles per batch)
- Formats for Claude prompt
"""

import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger


# Boilerplate patterns to remove
BOILERPLATE_PATTERNS = [
    r"Click here to read .*",
    r"Click here for .*",
    r"Subscribe to .*",
    r"Subscribe now.*",
    r"Sign up for .*",
    r"Sign up now.*",
    r"Read more at .*",
    r"Read more here.*",
    r"For more information.*",
    r"©\s*\d{4}.*",
    r"All rights reserved.*",
    r"This article was.*generated.*",
    r"Disclaimer:.*",
    r"ADVERTISEMENT",
    r"Continue reading.*",
    r"Learn more at .*",
    r"Visit .* for more.*",
    r"\[.*?\]",  # Square bracket references like [1], [Reuters]
]

# Compile patterns for efficiency
BOILERPLATE_RE = re.compile(
    '|'.join(BOILERPLATE_PATTERNS), 
    re.IGNORECASE | re.MULTILINE
)

# Source quality tiers (higher = more credible)
SOURCE_QUALITY = {
    # Tier 1 - Premium financial sources
    "wsj": 3, "wall street journal": 3,
    "ft": 3, "financial times": 3,
    "economist": 3,
    "bloomberg": 3,
    
    # Tier 2 - Quality news sources
    "reuters": 2,
    "cnbc": 2,
    "marketwatch": 2,
    "barrons": 2,
    "yahoo finance": 2,
    "seeking alpha": 2,
    
    # Tier 3 - General sources
    "default": 1,
}


@dataclass
class ProcessedArticle:
    """A cleaned and processed article ready for LLM analysis."""
    ticker: str
    headline: str
    content: str  # Cleaned summary/content
    source: str
    published: str
    quality_score: int  # 1-3 based on source
    relevance_score: float  # 0-1 based on ticker mention density
    word_count: int
    
    def to_prompt_format(self) -> str:
        """Format for inclusion in LLM prompt."""
        return f"""**{self.headline}**
- Source: {self.source} (Tier {self.quality_score})
- Date: {self.published}
- Content: {self.content}"""


class ArticleProcessor:
    """
    Process and batch news articles for LLM sentiment analysis.
    
    Features:
    - Cleans boilerplate text
    - Scores articles by source quality and relevance
    - Batches top N articles per ticker
    - Formats for Claude prompt
    """
    
    def __init__(
        self,
        max_articles_per_ticker: int = 5,
        max_content_length: int = 300,
        min_content_length: int = 20,
    ):
        self.max_articles = max_articles_per_ticker
        self.max_content_length = max_content_length
        self.min_content_length = min_content_length
    
    def process_articles(
        self,
        ticker: str,
        articles: List[Dict],
    ) -> List[ProcessedArticle]:
        """
        Process and filter articles for a ticker.
        
        Args:
            ticker: Stock symbol
            articles: Raw article dicts from news fetcher
        
        Returns:
            List of ProcessedArticle, sorted by quality and relevance
        """
        processed = []
        
        for article in articles:
            try:
                proc = self._process_single(ticker, article)
                if proc:
                    processed.append(proc)
            except Exception as e:
                logger.debug(f"Failed to process article: {e}")
        
        # Sort by quality (desc), then relevance (desc), then recency (desc)
        processed.sort(
            key=lambda a: (a.quality_score, a.relevance_score, a.published),
            reverse=True
        )
        
        # Return top N
        return processed[:self.max_articles]
    
    def _process_single(
        self,
        ticker: str,
        article: Dict,
    ) -> Optional[ProcessedArticle]:
        """Process a single article."""
        headline = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        source = article.get("source", "unknown")
        published = article.get("published", "")
        
        if not headline:
            return None
        
        # Clean the content
        content = self._clean_text(summary)
        
        # Skip if too short after cleaning
        if len(content) < self.min_content_length:
            content = self._clean_text(headline)  # Use headline as fallback
        
        # Truncate if too long
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length].rsplit(' ', 1)[0] + "..."
        
        # Calculate scores
        quality = self._get_source_quality(source)
        relevance = self._calculate_relevance(ticker, headline, summary)
        
        return ProcessedArticle(
            ticker=ticker,
            headline=headline[:200],  # Limit headline length
            content=content,
            source=self._normalize_source(source),
            published=self._format_date(published),
            quality_score=quality,
            relevance_score=relevance,
            word_count=len(content.split()),
        )
    
    def _clean_text(self, text: str) -> str:
        """Remove boilerplate and clean text."""
        if not text:
            return ""
        
        # Remove boilerplate patterns
        cleaned = BOILERPLATE_RE.sub('', text)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Remove leading/trailing punctuation artifacts
        cleaned = cleaned.strip('.,;:- ')
        
        return cleaned
    
    def _get_source_quality(self, source: str) -> int:
        """Get quality score for a source (1-3)."""
        source_lower = source.lower()
        
        for name, score in SOURCE_QUALITY.items():
            if name in source_lower:
                return score
        
        return SOURCE_QUALITY["default"]
    
    def _calculate_relevance(
        self,
        ticker: str,
        headline: str,
        summary: str,
    ) -> float:
        """
        Calculate relevance score (0-1) based on ticker mentions.
        
        Higher score = more directly about this stock
        """
        text = (headline + " " + summary).upper()
        ticker_upper = ticker.upper()
        
        # Direct ticker mention in headline is high relevance
        if ticker_upper in headline.upper():
            return 1.0
        
        # Ticker in summary
        if ticker_upper in text:
            # Count mentions
            mentions = text.count(ticker_upper)
            return min(0.9, 0.5 + (mentions * 0.1))
        
        # Check for company name (from common mappings)
        company_names = self._get_company_names(ticker_upper)
        for name in company_names:
            if name.lower() in text.lower():
                return 0.7
        
        # Generic/sector news
        return 0.3
    
    def _get_company_names(self, ticker: str) -> List[str]:
        """Get company names for a ticker."""
        # Common mappings (extend as needed)
        COMPANY_NAMES = {
            "AAPL": ["Apple", "iPhone", "iPad", "Mac"],
            "MSFT": ["Microsoft", "Azure", "Windows", "Xbox"],
            "GOOGL": ["Google", "Alphabet", "YouTube", "Android"],
            "AMZN": ["Amazon", "AWS", "Prime"],
            "META": ["Meta", "Facebook", "Instagram", "WhatsApp"],
            "TSLA": ["Tesla", "Elon Musk", "Cybertruck"],
            "NVDA": ["Nvidia", "GeForce", "CUDA"],
            "JPM": ["JPMorgan", "Jamie Dimon", "Chase"],
            "V": ["Visa"],
            "MA": ["Mastercard"],
        }
        return COMPANY_NAMES.get(ticker, [])
    
    def _normalize_source(self, source: str) -> str:
        """Normalize source name for display."""
        # Remove prefixes like "finnhub_" or "alphavantage_"
        if "_" in source:
            parts = source.split("_", 1)
            if parts[0] in ("finnhub", "alphavantage", "yahoo"):
                return parts[1].title() if len(parts) > 1 else parts[0].title()
        
        return source.title()
    
    def _format_date(self, date_str: str) -> str:
        """Format date for display."""
        if not date_str:
            return "Unknown"
        
        try:
            # Parse ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # If today, show "Today"
            if dt.date() == datetime.now().date():
                return f"Today {dt.strftime('%H:%M')}"
            
            # If yesterday, show "Yesterday"
            if dt.date() == (datetime.now() - timedelta(days=1)).date():
                return f"Yesterday {dt.strftime('%H:%M')}"
            
            # Otherwise show date
            return dt.strftime("%b %d, %Y")
            
        except Exception:
            return date_str[:10] if len(date_str) >= 10 else date_str
    
    def format_for_prompt(
        self,
        processed_articles: List[ProcessedArticle],
    ) -> str:
        """
        Format processed articles for inclusion in LLM prompt.
        
        Args:
            processed_articles: List of ProcessedArticle
        
        Returns:
            Formatted string for prompt
        """
        if not processed_articles:
            return "No recent news articles found for this stock."
        
        formatted = []
        for i, article in enumerate(processed_articles, 1):
            formatted.append(f"""**Article {i}:**
- Headline: {article.headline}
- Source: {article.source}
- Date: {article.published}
- Content: {article.content}
""")
        
        return "\n".join(formatted)
    
    def batch_by_ticker(
        self,
        articles: List[Dict],
        tickers: List[str],
    ) -> Dict[str, List[ProcessedArticle]]:
        """
        Batch articles by ticker.
        
        Args:
            articles: All articles from news fetch
            tickers: List of tickers to batch for
        
        Returns:
            Dict mapping ticker -> processed articles
        """
        # First, associate articles with tickers
        ticker_articles: Dict[str, List[Dict]] = {t: [] for t in tickers}
        
        for article in articles:
            # Check which tickers this article is relevant to
            headline = article.get("title", "").upper()
            summary = article.get("summary", "").upper()
            text = headline + " " + summary
            
            for ticker in tickers:
                ticker_upper = ticker.upper()
                
                # Check direct mention
                if ticker_upper in text:
                    ticker_articles[ticker].append(article)
                    continue
                
                # Check company names
                for name in self._get_company_names(ticker_upper):
                    if name.upper() in text:
                        ticker_articles[ticker].append(article)
                        break
        
        # Process articles for each ticker
        result = {}
        for ticker, arts in ticker_articles.items():
            result[ticker] = self.process_articles(ticker, arts)
        
        return result


# Convenience functions

def process_articles_for_ticker(
    ticker: str,
    articles: List[Dict],
    max_articles: int = 5,
) -> List[ProcessedArticle]:
    """Process articles for a single ticker."""
    processor = ArticleProcessor(max_articles_per_ticker=max_articles)
    return processor.process_articles(ticker, articles)


def format_articles_for_llm(
    ticker: str,
    articles: List[Dict],
    max_articles: int = 5,
) -> str:
    """Process and format articles for LLM prompt."""
    processor = ArticleProcessor(max_articles_per_ticker=max_articles)
    processed = processor.process_articles(ticker, articles)
    return processor.format_for_prompt(processed)


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== Article Processor Test ===\n")
    
    # Sample articles
    test_articles = [
        {
            "title": "Apple Reports Record Q4 Revenue, Beats Expectations",
            "summary": "Apple Inc. reported quarterly revenue of $89.5 billion, up 8% year over year. iPhone sales grew 10%. Subscribe to our newsletter for more updates. © 2026 Reuters.",
            "source": "reuters",
            "published": "2026-02-05T10:00:00",
        },
        {
            "title": "Tech Stocks Rally on Strong Earnings",
            "summary": "Technology sector sees broad gains as major companies report better than expected results. Click here to read more.",
            "source": "marketwatch",
            "published": "2026-02-04T15:00:00",
        },
        {
            "title": "Apple Vision Pro Sales Disappoint Analysts",
            "summary": "The new Apple Vision Pro headset has seen slower adoption than expected. [ADVERTISEMENT] For more tech news, sign up for our daily briefing.",
            "source": "bloomberg",
            "published": "2026-02-05T08:00:00",
        },
    ]
    
    processor = ArticleProcessor(max_articles_per_ticker=3)
    processed = processor.process_articles("AAPL", test_articles)
    
    print(f"Processed {len(processed)} articles:\n")
    for p in processed:
        print(f"  {p.headline[:50]}...")
        print(f"    Source: {p.source} (Tier {p.quality_score})")
        print(f"    Relevance: {p.relevance_score:.1f}")
        print(f"    Content: {p.content[:80]}...")
        print()
    
    print("\n--- Formatted for LLM ---\n")
    print(processor.format_for_prompt(processed))
