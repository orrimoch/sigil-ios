"""
F12.1 Historical Data Persistence

Store all data needed for backtesting:
- Daily/weekly scores (append-only)
- Backtest results with parameters
- Equity curves
- Trade logs

Uses JSON files for MVP (consistent with existing architecture),
designed for easy migration to SQLite/PostgreSQL later.
"""

import json
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid
from loguru import logger

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"
BACKTEST_DIR = DATA_DIR / "backtest"

# File paths
HISTORICAL_SCORES_FILE = BACKTEST_DIR / "historical_scores.json"
BACKTEST_RESULTS_FILE = BACKTEST_DIR / "backtest_results.json"
BACKTEST_TRADES_FILE = BACKTEST_DIR / "backtest_trades.json"

# Thread lock for file access
_lock = threading.Lock()


class BacktestStatus(str, Enum):
    """Status of a backtest run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HistoricalScore:
    """A point-in-time score snapshot for backtesting."""
    date: str  # ISO date YYYY-MM-DD
    ticker: str
    composite_score: float
    signal: str
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float
    sector: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "HistoricalScore":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BacktestParameters:
    """Parameters for a backtest run."""
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    entry_threshold: float = 70.0
    exit_threshold: float = 50.0
    max_positions: int = 10
    position_sizing: str = "equal_weight"
    rebalance_freq: str = "weekly"
    transaction_cost: float = 0.001  # 0.1%
    slippage: float = 0.001  # 0.1%
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BacktestParameters":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BacktestTrade:
    """A simulated trade in backtest."""
    trade_id: str
    backtest_id: str
    date: str
    ticker: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    value: float
    score_at_trade: float
    signal_at_trade: str
    commission: float = 0.0
    slippage_cost: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BacktestTrade":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EquityPoint:
    """A point in the equity curve."""
    date: str
    nav: float  # Net Asset Value
    cash: float
    positions_value: float
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    """Complete result of a backtest run."""
    backtest_id: str
    status: BacktestStatus
    parameters: BacktestParameters
    created_at: str
    completed_at: Optional[str] = None
    
    # Summary metrics
    total_return: Optional[float] = None
    cagr: Optional[float] = None
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    
    # Benchmark comparison
    benchmark_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    
    # Score validation
    score_ic: Optional[float] = None
    hit_rate: Optional[float] = None
    
    # Equity curve (stored separately for large datasets)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    
    # Error info
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["parameters"] = self.parameters.to_dict()
        d["equity_curve"] = [p.to_dict() if isinstance(p, EquityPoint) else p for p in self.equity_curve]
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "BacktestResult":
        data = data.copy()
        data["status"] = BacktestStatus(data["status"])
        data["parameters"] = BacktestParameters.from_dict(data["parameters"])
        data["equity_curve"] = [
            EquityPoint(**p) if isinstance(p, dict) else p 
            for p in data.get("equity_curve", [])
        ]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BacktestDataStore:
    """
    Manages persistence of all backtest-related data.
    
    Storage Strategy:
    - Historical scores: Append-only, keyed by date
    - Backtest results: Keyed by backtest_id
    - Trades: Keyed by backtest_id
    - Equity curves: Embedded in results (or separate file for large backtests)
    """
    
    def __init__(self, data_dir: Path = BACKTEST_DIR):
        self.data_dir = data_dir
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    # ============================================================
    # Historical Scores
    # ============================================================
    
    def save_historical_scores(self, scores: List[HistoricalScore]) -> int:
        """
        Append historical scores to storage.
        
        Scores are stored by date -> ticker -> score_data structure
        for efficient date-range queries.
        
        Returns:
            Number of scores saved
        """
        if not scores:
            return 0
        
        with _lock:
            existing = self._load_historical_scores_raw()
            
            for score in scores:
                date_key = score.date
                if date_key not in existing:
                    existing[date_key] = {}
                
                existing[date_key][score.ticker] = score.to_dict()
            
            self._save_historical_scores_raw(existing)
            
        logger.info(f"Saved {len(scores)} historical scores")
        return len(scores)
    
    def get_historical_scores(
        self,
        start_date: str,
        end_date: str,
        tickers: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, HistoricalScore]]:
        """
        Get historical scores for a date range.
        
        Args:
            start_date: Start date (inclusive) YYYY-MM-DD
            end_date: End date (inclusive) YYYY-MM-DD
            tickers: Optional list of tickers to filter
            
        Returns:
            Dict[date][ticker] -> HistoricalScore
        """
        raw = self._load_historical_scores_raw()
        result = {}
        
        for date_key, ticker_scores in raw.items():
            if start_date <= date_key <= end_date:
                result[date_key] = {}
                for ticker, score_data in ticker_scores.items():
                    if tickers is None or ticker in tickers:
                        result[date_key][ticker] = HistoricalScore.from_dict(score_data)
        
        return result
    
    def get_score_on_date(self, ticker: str, target_date: str) -> Optional[HistoricalScore]:
        """Get score for a specific ticker on a specific date."""
        raw = self._load_historical_scores_raw()
        if target_date in raw and ticker in raw[target_date]:
            return HistoricalScore.from_dict(raw[target_date][ticker])
        return None
    
    def get_available_date_range(self) -> tuple[Optional[str], Optional[str]]:
        """Get the min and max dates in historical scores."""
        raw = self._load_historical_scores_raw()
        if not raw:
            return None, None
        dates = sorted(raw.keys())
        return dates[0], dates[-1]
    
    def get_historical_score_count(self) -> int:
        """Get total number of historical score records."""
        raw = self._load_historical_scores_raw()
        return sum(len(tickers) for tickers in raw.values())
    
    def _load_historical_scores_raw(self) -> Dict:
        """Load raw historical scores from file."""
        path = self.data_dir / "historical_scores.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load historical scores: {e}")
        return {}
    
    def _save_historical_scores_raw(self, data: Dict) -> None:
        """Save raw historical scores to file."""
        path = self.data_dir / "historical_scores.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    # ============================================================
    # Backtest Results
    # ============================================================
    
    def create_backtest(self, params: BacktestParameters) -> BacktestResult:
        """
        Create a new backtest record.
        
        Returns:
            BacktestResult with generated ID and PENDING status
        """
        backtest_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        result = BacktestResult(
            backtest_id=backtest_id,
            status=BacktestStatus.PENDING,
            parameters=params,
            created_at=datetime.now().isoformat(),
        )
        
        self.save_backtest_result(result)
        logger.info(f"Created backtest {backtest_id}")
        
        return result
    
    def save_backtest_result(self, result: BacktestResult) -> None:
        """Save or update a backtest result."""
        with _lock:
            results = self._load_backtest_results_raw()
            results[result.backtest_id] = result.to_dict()
            self._save_backtest_results_raw(results)
    
    def get_backtest_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Get a backtest result by ID."""
        results = self._load_backtest_results_raw()
        if backtest_id in results:
            return BacktestResult.from_dict(results[backtest_id])
        return None
    
    def list_backtests(
        self,
        limit: int = 50,
        status: Optional[BacktestStatus] = None
    ) -> List[BacktestResult]:
        """List backtest results, newest first."""
        results = self._load_backtest_results_raw()
        
        all_results = [BacktestResult.from_dict(r) for r in results.values()]
        
        if status:
            all_results = [r for r in all_results if r.status == status]
        
        # Sort by created_at descending
        all_results.sort(key=lambda r: r.created_at, reverse=True)
        
        return all_results[:limit]
    
    def delete_backtest(self, backtest_id: str) -> bool:
        """Delete a backtest and its associated trades."""
        with _lock:
            results = self._load_backtest_results_raw()
            if backtest_id not in results:
                return False
            
            del results[backtest_id]
            self._save_backtest_results_raw(results)
            
            # Also delete trades
            trades = self._load_backtest_trades_raw()
            if backtest_id in trades:
                del trades[backtest_id]
                self._save_backtest_trades_raw(trades)
        
        logger.info(f"Deleted backtest {backtest_id}")
        return True
    
    def _load_backtest_results_raw(self) -> Dict:
        """Load raw backtest results from file."""
        path = self.data_dir / "backtest_results.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load backtest results: {e}")
        return {}
    
    def _save_backtest_results_raw(self, data: Dict) -> None:
        """Save raw backtest results to file."""
        path = self.data_dir / "backtest_results.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    # ============================================================
    # Backtest Trades
    # ============================================================
    
    def save_trades(self, backtest_id: str, trades: List[BacktestTrade]) -> int:
        """
        Save trades for a backtest.
        
        Returns:
            Number of trades saved
        """
        if not trades:
            return 0
        
        with _lock:
            all_trades = self._load_backtest_trades_raw()
            all_trades[backtest_id] = [t.to_dict() for t in trades]
            self._save_backtest_trades_raw(all_trades)
        
        logger.info(f"Saved {len(trades)} trades for backtest {backtest_id}")
        return len(trades)
    
    def get_trades(self, backtest_id: str) -> List[BacktestTrade]:
        """Get all trades for a backtest."""
        all_trades = self._load_backtest_trades_raw()
        if backtest_id not in all_trades:
            return []
        
        return [BacktestTrade.from_dict(t) for t in all_trades[backtest_id]]
    
    def _load_backtest_trades_raw(self) -> Dict:
        """Load raw backtest trades from file."""
        path = self.data_dir / "backtest_trades.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load backtest trades: {e}")
        return {}
    
    def _save_backtest_trades_raw(self, data: Dict) -> None:
        """Save raw backtest trades to file."""
        path = self.data_dir / "backtest_trades.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    # ============================================================
    # Portfolio Snapshots (for live tracking)
    # ============================================================
    
    def save_portfolio_snapshot(
        self,
        user_id: str,
        snapshot: Dict[str, Any]
    ) -> None:
        """
        Save a daily portfolio snapshot for live validation tracking.
        
        Args:
            user_id: User identifier
            snapshot: Portfolio state including NAV, positions, etc.
        """
        path = self.data_dir / "portfolio_snapshots.json"
        
        with _lock:
            snapshots = {}
            if path.exists():
                try:
                    with open(path) as f:
                        snapshots = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
            
            if user_id not in snapshots:
                snapshots[user_id] = []
            
            snapshot["timestamp"] = datetime.now().isoformat()
            snapshots[user_id].append(snapshot)
            
            # Keep last 365 days only
            snapshots[user_id] = snapshots[user_id][-365:]
            
            with open(path, "w") as f:
                json.dump(snapshots, f, indent=2)
    
    def get_portfolio_snapshots(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict]:
        """Get portfolio snapshots for a user."""
        path = self.data_dir / "portfolio_snapshots.json"
        
        if not path.exists():
            return []
        
        try:
            with open(path) as f:
                snapshots = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
        
        user_snapshots = snapshots.get(user_id, [])
        
        # Filter by days
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return [s for s in user_snapshots if s.get("timestamp", "") >= cutoff]
    
    # ============================================================
    # Utility Methods
    # ============================================================
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        historical_count = self.get_historical_score_count()
        backtest_count = len(self._load_backtest_results_raw())
        
        min_date, max_date = self.get_available_date_range()
        
        return {
            "historical_scores_count": historical_count,
            "backtest_count": backtest_count,
            "date_range": {
                "min": min_date,
                "max": max_date,
            },
            "data_dir": str(self.data_dir),
        }
    
    def cleanup_old_data(self, days_to_keep: int = 365) -> int:
        """
        Remove historical data older than specified days.
        
        Returns:
            Number of records removed
        """
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
        
        with _lock:
            raw = self._load_historical_scores_raw()
            original_count = sum(len(tickers) for tickers in raw.values())
            
            # Remove old dates
            raw = {date: scores for date, scores in raw.items() if date >= cutoff}
            
            new_count = sum(len(tickers) for tickers in raw.values())
            removed = original_count - new_count
            
            if removed > 0:
                self._save_historical_scores_raw(raw)
                logger.info(f"Cleaned up {removed} old historical score records")
        
        return removed


# Singleton instance
_store_instance: Optional[BacktestDataStore] = None


def get_data_store() -> BacktestDataStore:
    """Get the singleton BacktestDataStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = BacktestDataStore()
    return _store_instance


# CLI for testing
if __name__ == "__main__":
    import sys
    
    store = get_data_store()
    
    print("\n=== BacktestDataStore Test ===\n")
    
    # Test saving historical scores
    test_scores = [
        HistoricalScore(
            date="2025-01-01",
            ticker="AAPL",
            composite_score=75.0,
            signal="BUY",
            fundamental_score=80.0,
            sentiment_score=70.0,
            technical_score=75.0,
            macro_score=72.0,
            sector="Technology",
        ),
        HistoricalScore(
            date="2025-01-01",
            ticker="MSFT",
            composite_score=72.0,
            signal="BUY",
            fundamental_score=75.0,
            sentiment_score=68.0,
            technical_score=73.0,
            macro_score=72.0,
            sector="Technology",
        ),
    ]
    
    saved = store.save_historical_scores(test_scores)
    print(f"Saved {saved} test scores")
    
    # Test creating backtest
    params = BacktestParameters(
        start_date="2021-01-01",
        end_date="2025-12-31",
        initial_capital=100000,
    )
    
    result = store.create_backtest(params)
    print(f"Created backtest: {result.backtest_id}")
    
    # Get stats
    stats = store.get_storage_stats()
    print(f"\nStorage stats: {json.dumps(stats, indent=2)}")
    
    print("\n✅ BacktestDataStore working!")
