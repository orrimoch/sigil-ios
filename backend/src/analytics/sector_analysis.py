"""
Sector Performance Analysis - Core Module (REC-271)

Aggregates Sigil scores by sector/industry and analyzes trends over time.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import statistics

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"
STOCK_UNIVERSE_FILE = DATA_DIR / "stock_universe.json"
SCORE_HISTORY_FILE = DATA_DIR / "score_history.json"


@dataclass
class SectorClassification:
    """Hierarchical sector classification for a stock."""
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float
    
    @property
    def full_path(self) -> str:
        """Full sector/industry path."""
        return f"{self.sector}/{self.industry}"


@dataclass
class SectorScore:
    """Aggregated sector score for a specific date."""
    date: str
    sector: str
    industry: Optional[str]
    
    # Aggregated metrics
    mean_score: float
    median_score: float
    std_score: float
    min_score: float
    max_score: float
    
    # Distribution
    pct_buy: float      # % with BUY signal (score >= 70)
    pct_hold: float     # % with HOLD signal (40 <= score < 70)
    pct_sell: float     # % with SELL signal (score < 40)
    
    # Coverage
    stock_count: int
    missing_count: int  # Imputed scores


@dataclass
class SectorTimeSeries:
    """Time series of sector scores."""
    sector: str
    industry: Optional[str]
    start_date: str
    end_date: str
    scores: List[SectorScore]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sector": self.sector,
            "industry": self.industry,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "scores": [asdict(s) for s in self.scores]
        }


class SectorAnalyzer:
    """
    Analyzes Sigil scores by sector and industry.
    
    Provides:
    - Sector classification mapping
    - Score aggregation by sector/industry
    - Temporal trend analysis
    - Missing data handling
    """
    
    def __init__(self):
        self._stocks: Dict[str, SectorClassification] = {}
        self._sector_index: Dict[str, List[str]] = defaultdict(list)
        self._industry_index: Dict[str, List[str]] = defaultdict(list)
        self._score_history: Dict[str, List[dict]] = {}
        self._loaded = False
    
    def load_data(self) -> None:
        """Load stock universe and score history."""
        if self._loaded:
            return
        
        # Load stock universe
        if STOCK_UNIVERSE_FILE.exists():
            with open(STOCK_UNIVERSE_FILE) as f:
                data = json.load(f)
                stocks = data.get("stocks", [])
                
                for stock in stocks:
                    ticker = stock.get("ticker", "").upper()
                    if not ticker:
                        continue
                    
                    classification = SectorClassification(
                        ticker=ticker,
                        name=stock.get("name", ""),
                        sector=stock.get("sector", "Unknown"),
                        industry=stock.get("industry", "Unknown"),
                        market_cap=stock.get("market_cap", 0)
                    )
                    
                    self._stocks[ticker] = classification
                    self._sector_index[classification.sector].append(ticker)
                    self._industry_index[classification.industry].append(ticker)
        
        # Load score history
        if SCORE_HISTORY_FILE.exists():
            with open(SCORE_HISTORY_FILE) as f:
                self._score_history = json.load(f)
        
        self._loaded = True
    
    @property
    def sectors(self) -> List[str]:
        """Get list of all sectors."""
        self.load_data()
        return sorted(self._sector_index.keys())
    
    @property
    def industries(self) -> List[str]:
        """Get list of all industries."""
        self.load_data()
        return sorted(self._industry_index.keys())
    
    def get_sector_industries(self, sector: str) -> List[str]:
        """Get all industries within a sector."""
        self.load_data()
        industries = set()
        for ticker in self._sector_index.get(sector, []):
            if ticker in self._stocks:
                industries.add(self._stocks[ticker].industry)
        return sorted(industries)
    
    def get_stocks_in_sector(
        self,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[SectorClassification]:
        """
        Get stocks matching sector/industry filters.
        
        Args:
            sector: Filter by sector name
            industry: Filter by industry name
            top_n: Limit to top N by market cap
            
        Returns:
            List of SectorClassification objects
        """
        self.load_data()
        
        stocks = list(self._stocks.values())
        
        # Apply filters
        if sector:
            stocks = [s for s in stocks if s.sector.lower() == sector.lower()]
        if industry:
            stocks = [s for s in stocks if s.industry.lower() == industry.lower()]
        
        # Sort by market cap (descending)
        stocks.sort(key=lambda s: s.market_cap, reverse=True)
        
        # Apply top N limit
        if top_n:
            stocks = stocks[:top_n]
        
        return stocks
    
    def get_score_for_ticker(self, ticker: str, date: str) -> Optional[dict]:
        """Get score for a specific ticker and date."""
        self.load_data()
        
        history = self._score_history.get(ticker.upper(), [])
        for entry in history:
            if entry.get("date") == date:
                return entry
        return None
    
    def get_available_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """Get all dates with score data within range."""
        self.load_data()
        
        all_dates = set()
        for ticker_history in self._score_history.values():
            for entry in ticker_history:
                all_dates.add(entry.get("date"))
        
        dates = sorted(all_dates)
        
        # Apply date range filter
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]
        
        return dates
    
    def calculate_sector_score(
        self,
        date: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        top_n: Optional[int] = None,
        impute_missing: bool = True
    ) -> SectorScore:
        """
        Calculate aggregated sector score for a date.
        
        Args:
            date: Date to analyze (YYYY-MM-DD)
            sector: Filter by sector
            industry: Filter by industry
            top_n: Limit to top N stocks by market cap
            impute_missing: Fill missing scores with sector average
            
        Returns:
            SectorScore with aggregated metrics
        """
        self.load_data()
        
        # Get stocks matching filters
        stocks = self.get_stocks_in_sector(sector, industry, top_n)
        
        if not stocks:
            return SectorScore(
                date=date,
                sector=sector or "All",
                industry=industry,
                mean_score=0,
                median_score=0,
                std_score=0,
                min_score=0,
                max_score=0,
                pct_buy=0,
                pct_hold=0,
                pct_sell=0,
                stock_count=0,
                missing_count=0
            )
        
        # Collect scores
        scores = []
        missing_count = 0
        
        for stock in stocks:
            score_data = self.get_score_for_ticker(stock.ticker, date)
            if score_data:
                scores.append(score_data.get("total_score", 50))
            else:
                missing_count += 1
        
        # Impute missing scores with sector average
        if impute_missing and missing_count > 0 and len(scores) > 0:
            sector_avg = statistics.mean(scores)
            scores.extend([sector_avg] * missing_count)
        
        if not scores:
            return SectorScore(
                date=date,
                sector=sector or "All",
                industry=industry,
                mean_score=50,
                median_score=50,
                std_score=0,
                min_score=50,
                max_score=50,
                pct_buy=0,
                pct_hold=100,
                pct_sell=0,
                stock_count=len(stocks),
                missing_count=missing_count
            )
        
        # Calculate statistics
        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        std_score = statistics.stdev(scores) if len(scores) > 1 else 0
        min_score = min(scores)
        max_score = max(scores)
        
        # Calculate signal distribution
        buy_count = sum(1 for s in scores if s >= 70)
        sell_count = sum(1 for s in scores if s < 40)
        hold_count = len(scores) - buy_count - sell_count
        
        total = len(scores)
        pct_buy = (buy_count / total) * 100 if total > 0 else 0
        pct_hold = (hold_count / total) * 100 if total > 0 else 0
        pct_sell = (sell_count / total) * 100 if total > 0 else 0
        
        return SectorScore(
            date=date,
            sector=sector or "All",
            industry=industry,
            mean_score=round(mean_score, 2),
            median_score=round(median_score, 2),
            std_score=round(std_score, 2),
            min_score=round(min_score, 2),
            max_score=round(max_score, 2),
            pct_buy=round(pct_buy, 1),
            pct_hold=round(pct_hold, 1),
            pct_sell=round(pct_sell, 1),
            stock_count=len(stocks),
            missing_count=missing_count
        )
    
    def calculate_sector_trends(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> SectorTimeSeries:
        """
        Calculate sector score time series.
        
        Args:
            start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            end_date: End date (YYYY-MM-DD), defaults to today
            sector: Filter by sector
            industry: Filter by industry
            top_n: Limit to top N stocks by market cap
            
        Returns:
            SectorTimeSeries with scores for each date
        """
        self.load_data()
        
        # Default date range: last 30 days
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        dates = self.get_available_dates(start_date, end_date)
        
        scores = []
        for date in dates:
            score = self.calculate_sector_score(
                date=date,
                sector=sector,
                industry=industry,
                top_n=top_n
            )
            scores.append(score)
        
        return SectorTimeSeries(
            sector=sector or "All",
            industry=industry,
            start_date=start_date,
            end_date=end_date,
            scores=scores
        )
    
    def get_all_sector_trends(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> Dict[str, SectorTimeSeries]:
        """
        Get trends for all sectors.
        
        Returns:
            Dict mapping sector name to SectorTimeSeries
        """
        self.load_data()
        
        result = {}
        for sector in self.sectors:
            result[sector] = self.calculate_sector_trends(
                start_date=start_date,
                end_date=end_date,
                sector=sector,
                top_n=top_n
            )
        
        return result
    
    def get_latest_sector_summary(self) -> List[dict]:
        """
        Get summary of latest sector scores.
        
        Returns:
            List of dicts with sector summary data
        """
        self.load_data()
        
        # Get latest date
        dates = self.get_available_dates()
        if not dates:
            return []
        
        latest_date = dates[-1]
        
        summary = []
        for sector in self.sectors:
            score = self.calculate_sector_score(date=latest_date, sector=sector)
            summary.append({
                "sector": sector,
                "date": latest_date,
                "mean_score": score.mean_score,
                "median_score": score.median_score,
                "std_score": score.std_score,
                "pct_buy": score.pct_buy,
                "pct_hold": score.pct_hold,
                "pct_sell": score.pct_sell,
                "stock_count": score.stock_count,
                "signal": "BUY" if score.mean_score >= 70 else "SELL" if score.mean_score < 40 else "HOLD"
            })
        
        # Sort by mean score descending
        summary.sort(key=lambda x: x["mean_score"], reverse=True)
        
        return summary


# Convenience functions
def get_sector_scores(
    date: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    top_n: Optional[int] = None
) -> SectorScore:
    """
    Get aggregated sector scores for a date.
    
    Convenience wrapper around SectorAnalyzer.
    """
    analyzer = SectorAnalyzer()
    if not date:
        dates = analyzer.get_available_dates()
        date = dates[-1] if dates else datetime.now().strftime("%Y-%m-%d")
    
    return analyzer.calculate_sector_score(
        date=date,
        sector=sector,
        industry=industry,
        top_n=top_n
    )


def get_sector_trends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    top_n: Optional[int] = None
) -> SectorTimeSeries:
    """
    Get sector score trends over time.
    
    Convenience wrapper around SectorAnalyzer.
    """
    analyzer = SectorAnalyzer()
    return analyzer.calculate_sector_trends(
        start_date=start_date,
        end_date=end_date,
        sector=sector,
        industry=industry,
        top_n=top_n
    )
