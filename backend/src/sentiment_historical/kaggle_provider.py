"""
Kaggle News Provider (REC-207)

Parses analyst_ratings_processed.csv and maps to Sigil's ticker universe.
Provides historical news data for backtesting (2009-2020).
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Set
from loguru import logger
import json

from .news_provider import NewsProvider, NewsArticle, NewsSource


# Ticker normalization mapping (handle variants like BRK.B vs BRK-B)
TICKER_ALIASES = {
    "BRK.B": "BRK-B",
    "BRK.A": "BRK-A", 
    "BF.B": "BF-B",
    "BF.A": "BF-A",
}


class KaggleNewsProvider(NewsProvider):
    """
    News provider for Kaggle Massive Stock News Analysis dataset.
    
    Dataset: https://www.kaggle.com/datasets/miguelaenlle/massive-stock-news-analysis-db-for-nlpbacktests
    Coverage: 2009-2020
    Primary table: analyst_ratings_processed.csv
    
    Columns used:
    - title: News headline (SENTIMENT INPUT)
    - date: Publication timestamp (TIME MAPPING)
    - stock: Ticker symbol (TICKER FILTER)
    """
    
    def __init__(
        self,
        data_dir: Path,
        universe_path: Optional[Path] = None,
        lazy_load: bool = True,
    ):
        """
        Initialize Kaggle news provider.
        
        Args:
            data_dir: Path to kaggle_sentiment/ directory
            universe_path: Path to fundamentals.json for ticker filtering
            lazy_load: If True, load data on first access (saves memory)
        """
        self.data_dir = Path(data_dir)
        self.universe_path = universe_path
        self._df: Optional[pd.DataFrame] = None
        self._universe: Optional[Set[str]] = None
        self._date_range: Optional[tuple] = None
        self._stats: Optional[Dict[str, Any]] = None
        
        if not lazy_load:
            self._load_data()
    
    def _load_data(self):
        """Load and preprocess the CSV data."""
        csv_path = self.data_dir / "analyst_ratings_processed.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Kaggle CSV not found: {csv_path}")
        
        logger.info(f"Loading Kaggle data from {csv_path}...")
        
        # Load CSV
        self._df = pd.read_csv(
            csv_path,
            index_col=0,
            usecols=[0, 1, 2, 3],  # index, title, date, stock
        )
        
        # Parse dates
        self._df["date"] = pd.to_datetime(
            self._df["date"], 
            errors="coerce",
            utc=True,
        )
        
        # Drop rows with invalid dates
        before = len(self._df)
        self._df = self._df.dropna(subset=["date"])
        after = len(self._df)
        if before != after:
            logger.warning(f"Dropped {before - after} rows with invalid dates")
        
        # Normalize tickers
        self._df["stock"] = self._df["stock"].str.upper().replace(TICKER_ALIASES)
        
        # Calculate date range
        self._date_range = (
            self._df["date"].min().date(),
            self._df["date"].max().date(),
        )
        
        logger.info(
            f"Loaded {len(self._df):,} articles, "
            f"{self._df['stock'].nunique()} tickers, "
            f"range: {self._date_range[0]} to {self._date_range[1]}"
        )
    
    def _load_universe(self) -> Set[str]:
        """Load Sigil's ticker universe for filtering."""
        if self._universe is not None:
            return self._universe
        
        if self.universe_path and self.universe_path.exists():
            try:
                with open(self.universe_path) as f:
                    data = json.load(f)
                
                if "stocks" in data:
                    self._universe = set(data["stocks"].keys())
                else:
                    self._universe = set(data.keys())
                
                # Normalize
                self._universe = {t.upper() for t in self._universe}
                logger.info(f"Loaded {len(self._universe)} tickers from universe")
                
            except Exception as e:
                logger.warning(f"Failed to load universe: {e}")
                self._universe = set()
        else:
            self._universe = set()
        
        return self._universe
    
    @property
    def df(self) -> pd.DataFrame:
        """Lazy-load and return the dataframe."""
        if self._df is None:
            self._load_data()
        return self._df
    
    @property
    def name(self) -> str:
        return "kaggle"
    
    @property
    def source_type(self) -> NewsSource:
        return NewsSource.KAGGLE
    
    @property
    def date_range(self) -> tuple:
        if self._date_range is None:
            _ = self.df  # Trigger load
        return self._date_range
    
    def get_articles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """Get articles for a single ticker."""
        ticker = ticker.upper()
        ticker = TICKER_ALIASES.get(ticker, ticker)
        
        # Filter dataframe
        mask = (
            (self.df["stock"] == ticker) &
            (self.df["date"].dt.date >= start_date) &
            (self.df["date"].dt.date <= end_date)
        )
        
        filtered = self.df[mask]
        
        # Convert to NewsArticle objects
        articles = []
        for _, row in filtered.iterrows():
            articles.append(NewsArticle(
                ticker=ticker,
                headline=row["title"],
                published=row["date"].to_pydatetime(),
                source="kaggle",
                provider=NewsSource.KAGGLE,
            ))
        
        return articles
    
    def get_all_articles(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None,
    ) -> List[NewsArticle]:
        """Get all articles, optionally filtered by tickers."""
        # Date filter
        mask = (
            (self.df["date"].dt.date >= start_date) &
            (self.df["date"].dt.date <= end_date)
        )
        
        # Ticker filter
        if tickers:
            tickers_upper = {t.upper() for t in tickers}
            tickers_normalized = {TICKER_ALIASES.get(t, t) for t in tickers_upper}
            mask = mask & self.df["stock"].isin(tickers_normalized)
        
        filtered = self.df[mask]
        
        # Convert to NewsArticle objects
        articles = []
        for _, row in filtered.iterrows():
            articles.append(NewsArticle(
                ticker=row["stock"],
                headline=row["title"],
                published=row["date"].to_pydatetime(),
                source="kaggle",
                provider=NewsSource.KAGGLE,
            ))
        
        logger.debug(
            f"Retrieved {len(articles)} articles for "
            f"{start_date} to {end_date}"
            f"{f' ({len(tickers)} tickers)' if tickers else ''}"
        )
        
        return articles
    
    def get_articles_for_universe(
        self,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """Get articles filtered to Sigil's ticker universe."""
        universe = self._load_universe()
        
        if not universe:
            logger.warning("No universe loaded, returning all articles")
            return self.get_all_articles(start_date, end_date)
        
        return self.get_all_articles(start_date, end_date, list(universe))
    
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get statistics about data coverage."""
        if self._stats is not None:
            return self._stats
        
        universe = self._load_universe()
        
        # Calculate stats
        total_articles = len(self.df)
        unique_tickers = self.df["stock"].nunique()
        
        # Overlap with universe
        dataset_tickers = set(self.df["stock"].unique())
        overlap = dataset_tickers & universe if universe else set()
        
        self._stats = {
            "total_articles": total_articles,
            "unique_tickers": unique_tickers,
            "date_range": {
                "start": self.date_range[0].isoformat(),
                "end": self.date_range[1].isoformat(),
            },
            "universe_overlap": {
                "matched": len(overlap),
                "universe_size": len(universe),
                "coverage_pct": round(len(overlap) / len(universe) * 100, 1) if universe else 0,
            },
            "articles_per_ticker": {
                "mean": round(total_articles / unique_tickers, 1),
                "median": int(self.df.groupby("stock").size().median()),
            },
        }
        
        return self._stats
    
    def get_ticker_article_counts(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Get article count per ticker for a date range."""
        mask = (
            (self.df["date"].dt.date >= start_date) &
            (self.df["date"].dt.date <= end_date)
        )
        
        if tickers:
            tickers_upper = {t.upper() for t in tickers}
            mask = mask & self.df["stock"].isin(tickers_upper)
        
        counts = self.df[mask].groupby("stock").size().to_dict()
        return counts


# Convenience function
def create_kaggle_provider(
    project_root: Optional[Path] = None,
) -> KaggleNewsProvider:
    """
    Create a KaggleNewsProvider with default paths.
    
    Args:
        project_root: Project root (auto-detected if None)
    
    Returns:
        Configured KaggleNewsProvider
    """
    if project_root is None:
        # Try to find project root
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "kaggle_sentiment").exists():
                project_root = parent
                break
            if (parent / "backend").exists():
                project_root = parent
                break
        
        if project_root is None:
            raise ValueError("Could not find project root")
    
    data_dir = project_root / "kaggle_sentiment"
    universe_path = project_root / "backend" / "data" / "fundamentals.json"
    
    return KaggleNewsProvider(
        data_dir=data_dir,
        universe_path=universe_path,
    )


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Kaggle News Provider Test ===\n")
    
    try:
        provider = create_kaggle_provider()
        
        stats = provider.get_coverage_stats()
        print(f"Total articles: {stats['total_articles']:,}")
        print(f"Unique tickers: {stats['unique_tickers']}")
        print(f"Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
        print(f"Universe overlap: {stats['universe_overlap']['matched']}/{stats['universe_overlap']['universe_size']} tickers")
        
        # Test date range
        test_start = date(2019, 6, 1)
        test_end = date(2019, 11, 30)
        
        articles = provider.get_articles_for_universe(test_start, test_end)
        print(f"\nArticles for Jun-Nov 2019 (universe): {len(articles):,}")
        
        # Sample AAPL
        aapl = provider.get_articles("AAPL", test_start, test_end)
        print(f"AAPL articles: {len(aapl)}")
        
        if aapl:
            print(f"  Sample: {aapl[0].headline[:80]}...")
        
        print("\n✅ Kaggle provider working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
