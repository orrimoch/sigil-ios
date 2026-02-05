"""
Sentiment Comparison Tool (REC-176)

A/B test LLM vs Keyword sentiment analysis:
- Compare scores side by side
- Track neutral rates
- Measure score variance
- Generate comparison reports
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from loguru import logger

from .sentiment_score import (
    SentimentScoreResult,
    _analyze_with_keywords,
    _analyze_with_llm,
)
from .sentiment_config import get_sentiment_config


@dataclass
class ComparisonResult:
    """Result of comparing LLM vs Keyword for a single ticker."""
    ticker: str
    llm_score: float
    llm_sentiment: str  # Label
    llm_confidence: float
    keyword_score: float
    keyword_sentiment: str
    score_diff: float  # LLM - Keyword
    article_count: int
    llm_rationale: str = ""
    
    @property
    def is_llm_neutral(self) -> bool:
        return 45 <= self.llm_score <= 54
    
    @property
    def is_keyword_neutral(self) -> bool:
        return 45 <= self.keyword_score <= 54
    
    @property
    def both_agree(self) -> bool:
        """Check if both methods agree on direction."""
        if self.is_llm_neutral and self.is_keyword_neutral:
            return True
        llm_direction = "bullish" if self.llm_score > 54 else ("bearish" if self.llm_score < 45 else "neutral")
        kw_direction = "bullish" if self.keyword_score > 54 else ("bearish" if self.keyword_score < 45 else "neutral")
        return llm_direction == kw_direction
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "llm_score": self.llm_score,
            "llm_sentiment": self.llm_sentiment,
            "llm_confidence": self.llm_confidence,
            "keyword_score": self.keyword_score,
            "keyword_sentiment": self.keyword_sentiment,
            "score_diff": self.score_diff,
            "article_count": self.article_count,
            "is_llm_neutral": self.is_llm_neutral,
            "is_keyword_neutral": self.is_keyword_neutral,
            "both_agree": self.both_agree,
        }


@dataclass
class ComparisonReport:
    """Summary report comparing LLM vs Keyword sentiment."""
    generated_at: str = ""
    total_tickers: int = 0
    
    # Neutral rates
    llm_neutral_count: int = 0
    keyword_neutral_count: int = 0
    
    # Score statistics
    avg_llm_score: float = 0.0
    avg_keyword_score: float = 0.0
    avg_score_diff: float = 0.0
    max_score_diff: float = 0.0
    
    # Agreement
    agreement_count: int = 0
    
    # LLM confidence
    avg_confidence: float = 0.0
    
    # Individual results
    results: List[ComparisonResult] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()
    
    @property
    def llm_neutral_rate(self) -> float:
        if self.total_tickers == 0:
            return 0.0
        return self.llm_neutral_count / self.total_tickers
    
    @property
    def keyword_neutral_rate(self) -> float:
        if self.total_tickers == 0:
            return 0.0
        return self.keyword_neutral_count / self.total_tickers
    
    @property
    def agreement_rate(self) -> float:
        if self.total_tickers == 0:
            return 0.0
        return self.agreement_count / self.total_tickers
    
    @property
    def neutral_reduction(self) -> float:
        """How much LLM reduces neutral rate vs keyword."""
        if self.keyword_neutral_rate == 0:
            return 0.0
        return (self.keyword_neutral_rate - self.llm_neutral_rate) / self.keyword_neutral_rate
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_tickers": self.total_tickers,
            "llm_neutral_count": self.llm_neutral_count,
            "llm_neutral_rate": round(self.llm_neutral_rate, 3),
            "keyword_neutral_count": self.keyword_neutral_count,
            "keyword_neutral_rate": round(self.keyword_neutral_rate, 3),
            "neutral_reduction": round(self.neutral_reduction, 3),
            "avg_llm_score": round(self.avg_llm_score, 2),
            "avg_keyword_score": round(self.avg_keyword_score, 2),
            "avg_score_diff": round(self.avg_score_diff, 2),
            "max_score_diff": round(self.max_score_diff, 2),
            "agreement_count": self.agreement_count,
            "agreement_rate": round(self.agreement_rate, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "results": [r.to_dict() for r in self.results],
        }
    
    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Sentiment Analysis Comparison Report",
            "",
            f"**Generated:** {self.generated_at}",
            f"**Tickers Analyzed:** {self.total_tickers}",
            "",
            "## Summary",
            "",
            "| Metric | LLM | Keyword | Improvement |",
            "|--------|-----|---------|-------------|",
            f"| Neutral Rate | {self.llm_neutral_rate:.1%} | {self.keyword_neutral_rate:.1%} | {self.neutral_reduction:.1%} reduction |",
            f"| Avg Score | {self.avg_llm_score:.1f} | {self.avg_keyword_score:.1f} | {self.avg_score_diff:+.1f} |",
            f"| Agreement | {self.agreement_rate:.1%} | - | - |",
            f"| Avg Confidence | {self.avg_confidence:.1%} | N/A | - |",
            "",
            "## Key Findings",
            "",
        ]
        
        # Key findings
        if self.neutral_reduction > 0:
            lines.append(f"✅ LLM reduces neutral rate by **{self.neutral_reduction:.0%}**")
        else:
            lines.append(f"⚠️ LLM has same or higher neutral rate")
        
        if self.agreement_rate > 0.7:
            lines.append(f"✅ High agreement ({self.agreement_rate:.0%}) between methods")
        elif self.agreement_rate > 0.5:
            lines.append(f"🟡 Moderate agreement ({self.agreement_rate:.0%}) between methods")
        else:
            lines.append(f"⚠️ Low agreement ({self.agreement_rate:.0%}) - methods diverge")
        
        lines.extend([
            "",
            "## Score Distribution",
            "",
            "| Ticker | LLM Score | Keyword Score | Diff | LLM Sentiment |",
            "|--------|-----------|---------------|------|---------------|",
        ])
        
        for r in sorted(self.results, key=lambda x: abs(x.score_diff), reverse=True)[:10]:
            diff_emoji = "🟢" if r.score_diff > 10 else ("🔴" if r.score_diff < -10 else "🟡")
            lines.append(
                f"| {r.ticker} | {r.llm_score:.0f} | {r.keyword_score:.0f} | {diff_emoji} {r.score_diff:+.0f} | {r.llm_sentiment} |"
            )
        
        lines.extend([
            "",
            "## Conclusion",
            "",
        ])
        
        if self.neutral_reduction > 0.3:
            lines.append("LLM sentiment analysis significantly improves signal quality by reducing neutral classifications.")
        elif self.neutral_reduction > 0:
            lines.append("LLM sentiment analysis provides modest improvement over keyword method.")
        else:
            lines.append("LLM and keyword methods perform similarly for this dataset.")
        
        return "\n".join(lines)


class SentimentComparator:
    """Compare LLM vs Keyword sentiment analysis."""
    
    def __init__(self):
        self.config = get_sentiment_config()
    
    def compare_single(
        self,
        ticker: str,
        articles: List[Dict],
    ) -> Optional[ComparisonResult]:
        """
        Compare LLM vs Keyword for a single ticker.
        
        Args:
            ticker: Stock symbol
            articles: News articles
        
        Returns:
            ComparisonResult or None if analysis fails
        """
        if not articles:
            return None
        
        # Run keyword analysis
        keyword_result = _analyze_with_keywords(ticker, articles, hours=168)
        
        # Run LLM analysis
        llm_result = _analyze_with_llm(ticker, articles)
        
        if llm_result is None:
            logger.warning(f"LLM analysis failed for {ticker}")
            return None
        
        # Build comparison
        return ComparisonResult(
            ticker=ticker,
            llm_score=llm_result.total_score,
            llm_sentiment=llm_result.details.get("sentiment_label", "unknown"),
            llm_confidence=llm_result.details.get("confidence", 0.5),
            keyword_score=keyword_result.total_score,
            keyword_sentiment="bullish" if keyword_result.total_score > 54 else (
                "bearish" if keyword_result.total_score < 45 else "neutral"
            ),
            score_diff=llm_result.total_score - keyword_result.total_score,
            article_count=len(articles),
            llm_rationale=llm_result.details.get("rationale", ""),
        )
    
    def compare_batch(
        self,
        tickers_articles: Dict[str, List[Dict]],
    ) -> ComparisonReport:
        """
        Compare LLM vs Keyword for multiple tickers.
        
        Args:
            tickers_articles: Dict mapping ticker -> articles
        
        Returns:
            ComparisonReport with all results
        """
        import time
        
        results = []
        
        for i, (ticker, articles) in enumerate(tickers_articles.items(), 1):
            if not articles:
                continue
            
            logger.info(f"Comparing {ticker} ({i}/{len(tickers_articles)})")
            
            result = self.compare_single(ticker, articles)
            if result:
                results.append(result)
            
            # Rate limit
            time.sleep(0.5)
        
        # Build report
        return self._build_report(results)
    
    def _build_report(self, results: List[ComparisonResult]) -> ComparisonReport:
        """Build summary report from results."""
        if not results:
            return ComparisonReport()
        
        report = ComparisonReport(
            total_tickers=len(results),
            results=results,
        )
        
        # Calculate statistics
        report.llm_neutral_count = sum(1 for r in results if r.is_llm_neutral)
        report.keyword_neutral_count = sum(1 for r in results if r.is_keyword_neutral)
        report.agreement_count = sum(1 for r in results if r.both_agree)
        
        report.avg_llm_score = sum(r.llm_score for r in results) / len(results)
        report.avg_keyword_score = sum(r.keyword_score for r in results) / len(results)
        report.avg_score_diff = sum(r.score_diff for r in results) / len(results)
        report.max_score_diff = max(abs(r.score_diff) for r in results)
        report.avg_confidence = sum(r.llm_confidence for r in results) / len(results)
        
        return report
    
    def save_report(
        self,
        report: ComparisonReport,
        output_dir: Path,
    ) -> Tuple[Path, Path]:
        """
        Save report to files.
        
        Returns:
            Tuple of (json_path, markdown_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_path = output_dir / f"comparison_{timestamp}.json"
        md_path = output_dir / f"comparison_{timestamp}.md"
        
        json_path.write_text(json.dumps(report.to_dict(), indent=2))
        md_path.write_text(report.to_markdown())
        
        logger.info(f"Saved comparison report to {output_dir}")
        
        return json_path, md_path


def run_comparison(
    sample_size: int = 5,
    output_dir: Optional[Path] = None,
) -> ComparisonReport:
    """
    Run a comparison test with sample data.
    
    Args:
        sample_size: Number of tickers to compare
        output_dir: Where to save reports (optional)
    
    Returns:
        ComparisonReport
    """
    # Sample test data
    test_data = {
        "AAPL": [
            {"title": "Apple Q4 Revenue Beats Expectations", "summary": "Strong iPhone sales drove growth.", "source": "Reuters", "published": "2026-02-05"},
            {"title": "Apple Vision Pro Faces Slow Adoption", "summary": "Headset sales below forecasts.", "source": "Bloomberg", "published": "2026-02-04"},
        ],
        "TSLA": [
            {"title": "Tesla Cuts Prices in China Again", "summary": "Model 3 and Y prices reduced by 5%.", "source": "Reuters", "published": "2026-02-05"},
            {"title": "Tesla FSD V13 Impresses Reviewers", "summary": "Full Self Driving update shows progress.", "source": "Electrek", "published": "2026-02-04"},
        ],
        "NVDA": [
            {"title": "NVIDIA Blackwell Demand Soars", "summary": "AI chip orders exceed expectations.", "source": "WSJ", "published": "2026-02-05"},
        ],
        "MSFT": [
            {"title": "Microsoft Azure Grows 29%", "summary": "Cloud revenue beats estimates.", "source": "CNBC", "published": "2026-02-05"},
        ],
        "META": [
            {"title": "Meta Ad Revenue Up 25%", "summary": "AI-powered targeting drives growth.", "source": "WSJ", "published": "2026-02-05"},
            {"title": "Reality Labs Loses $4.5B", "summary": "Metaverse investments continue.", "source": "Reuters", "published": "2026-02-04"},
        ],
    }
    
    # Use only requested sample size
    tickers = list(test_data.keys())[:sample_size]
    sample_data = {t: test_data[t] for t in tickers}
    
    comparator = SentimentComparator()
    report = comparator.compare_batch(sample_data)
    
    if output_dir:
        comparator.save_report(report, output_dir)
    
    return report


# CLI for testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Sentiment Comparison Test ===\n")
    
    output_dir = Path(__file__).parent.parent.parent / "data" / "comparison_reports"
    report = run_comparison(sample_size=3, output_dir=output_dir)
    
    print("\n" + report.to_markdown())
