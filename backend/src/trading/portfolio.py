"""
F6.2 & F7.x Paper Trading Portfolio Management

Tracks positions, calculates P&L, supports reset.
F7.2: Portfolio history tracking
F7.3: Sector allocation
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.price_fetcher import fetch_latest_price


# Default starting cash for paper trading
DEFAULT_CASH = 100_000.0

# Data directory for persistence
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
PORTFOLIO_HISTORY_FILE = DATA_DIR / "portfolio_history.json"


@dataclass
class Position:
    """A single stock position."""
    ticker: str
    shares: float
    avg_cost: float
    opened_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.shares * self.avg_cost
    
    def market_value(self, current_price: float) -> float:
        """Current market value."""
        return self.shares * current_price
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Unrealized profit/loss."""
        return self.market_value(current_price) - self.cost_basis
    
    def unrealized_pnl_percent(self, current_price: float) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl(current_price) / self.cost_basis) * 100
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(**data)


@dataclass
class PortfolioSummary:
    """Portfolio summary with P&L."""
    total_value: float
    cash: float
    positions_value: float
    total_pnl: float
    total_pnl_percent: float
    daily_pnl: float
    daily_pnl_percent: float
    positions_count: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class Portfolio:
    """
    Paper trading portfolio manager.
    
    Tracks:
    - Cash balance
    - Stock positions (ticker → Position)
    - Realized and unrealized P&L
    """
    
    def __init__(self, starting_cash: float = DEFAULT_CASH, is_paper: bool = True):
        self.cash = starting_cash
        self.starting_cash = starting_cash
        self.is_paper = is_paper
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        # Previous day's values for daily P&L
        self._prev_total_value: Optional[float] = None
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for a ticker."""
        return self.positions.get(ticker.upper())
    
    def add_position(self, ticker: str, shares: float, price: float) -> Position:
        """
        Add shares to a position (buy).
        
        If position exists, updates average cost.
        """
        ticker = ticker.upper()
        
        # Check if we have enough cash
        cost = shares * price
        if cost > self.cash:
            raise ValueError(f"Insufficient cash: need ${cost:.2f}, have ${self.cash:.2f}")
        
        # Deduct cash
        self.cash -= cost
        
        # Update or create position
        if ticker in self.positions:
            existing = self.positions[ticker]
            total_shares = existing.shares + shares
            total_cost = existing.cost_basis + cost
            existing.shares = total_shares
            existing.avg_cost = total_cost / total_shares
        else:
            self.positions[ticker] = Position(
                ticker=ticker,
                shares=shares,
                avg_cost=price
            )
        
        self.updated_at = datetime.now().isoformat()
        return self.positions[ticker]
    
    def reduce_position(self, ticker: str, shares: float, price: float) -> float:
        """
        Remove shares from a position (sell).
        
        Returns realized P&L from the sale.
        """
        ticker = ticker.upper()
        
        if ticker not in self.positions:
            raise ValueError(f"No position in {ticker}")
        
        position = self.positions[ticker]
        
        if shares > position.shares:
            raise ValueError(f"Cannot sell {shares} shares, only have {position.shares}")
        
        # Calculate realized P&L
        cost_basis = shares * position.avg_cost
        proceeds = shares * price
        pnl = proceeds - cost_basis
        self.realized_pnl += pnl
        
        # Add cash
        self.cash += proceeds
        
        # Update position
        position.shares -= shares
        
        # Remove if empty
        if position.shares <= 0:
            del self.positions[ticker]
        
        self.updated_at = datetime.now().isoformat()
        return pnl
    
    def close_position(self, ticker: str, price: float) -> float:
        """Close entire position at given price."""
        ticker = ticker.upper()
        if ticker not in self.positions:
            raise ValueError(f"No position in {ticker}")
        
        shares = self.positions[ticker].shares
        return self.reduce_position(ticker, shares, price)
    
    def get_summary(self, prices: Optional[Dict[str, float]] = None) -> PortfolioSummary:
        """
        Calculate portfolio summary.
        
        If prices not provided, fetches current prices.
        """
        if prices is None:
            prices = {}
            for ticker in self.positions:
                price_data = fetch_latest_price(ticker)
                if price_data and price_data.get("price"):
                    prices[ticker] = price_data["price"]
        
        # Calculate positions value
        positions_value = 0.0
        for ticker, position in self.positions.items():
            price = prices.get(ticker, position.avg_cost)  # Fallback to avg cost
            positions_value += position.market_value(price)
        
        total_value = self.cash + positions_value
        total_pnl = total_value - self.starting_cash
        total_pnl_percent = (total_pnl / self.starting_cash) * 100 if self.starting_cash > 0 else 0
        
        # Daily P&L (compare to previous close)
        if self._prev_total_value is None:
            self._prev_total_value = total_value
        
        daily_pnl = total_value - self._prev_total_value
        daily_pnl_percent = (daily_pnl / self._prev_total_value) * 100 if self._prev_total_value > 0 else 0
        
        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash=round(self.cash, 2),
            positions_value=round(positions_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_percent=round(total_pnl_percent, 2),
            daily_pnl=round(daily_pnl, 2),
            daily_pnl_percent=round(daily_pnl_percent, 2),
            positions_count=len(self.positions)
        )
    
    def get_holdings(self, prices: Optional[Dict[str, float]] = None) -> List[dict]:
        """Get all holdings with current values."""
        if prices is None:
            prices = {}
            for ticker in self.positions:
                price_data = fetch_latest_price(ticker)
                if price_data and price_data.get("price"):
                    prices[ticker] = price_data["price"]
        
        holdings = []
        for ticker, position in self.positions.items():
            price = prices.get(ticker, position.avg_cost)
            holdings.append({
                "ticker": ticker,
                "shares": position.shares,
                "avg_cost": round(position.avg_cost, 2),
                "current_price": round(price, 2),
                "market_value": round(position.market_value(price), 2),
                "cost_basis": round(position.cost_basis, 2),
                "unrealized_pnl": round(position.unrealized_pnl(price), 2),
                "unrealized_pnl_percent": round(position.unrealized_pnl_percent(price), 2),
                "opened_at": position.opened_at,
            })
        
        # Sort by market value descending
        holdings.sort(key=lambda x: x["market_value"], reverse=True)
        return holdings
    
    def reset(self, starting_cash: float = DEFAULT_CASH):
        """Reset portfolio to initial state."""
        self.cash = starting_cash
        self.starting_cash = starting_cash
        self.positions = {}
        self.realized_pnl = 0.0
        self._prev_total_value = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Serialize portfolio to dict."""
        return {
            "cash": self.cash,
            "starting_cash": self.starting_cash,
            "is_paper": self.is_paper,
            "positions": {t: p.to_dict() for t, p in self.positions.items()},
            "realized_pnl": self.realized_pnl,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        """Deserialize portfolio from dict."""
        portfolio = cls(
            starting_cash=data.get("starting_cash", DEFAULT_CASH),
            is_paper=data.get("is_paper", True)
        )
        portfolio.cash = data.get("cash", portfolio.starting_cash)
        portfolio.realized_pnl = data.get("realized_pnl", 0.0)
        portfolio.created_at = data.get("created_at", datetime.now().isoformat())
        portfolio.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        for ticker, pos_data in data.get("positions", {}).items():
            portfolio.positions[ticker] = Position.from_dict(pos_data)
        
        return portfolio
    
    def save(self, path: Optional[Path] = None):
        """Save portfolio to file."""
        path = path or PORTFOLIO_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["Portfolio"]:
        """Load portfolio from file."""
        path = path or PORTFOLIO_FILE
        if not path.exists():
            return None
        
        with open(path) as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def get_sector_allocation(self, prices: Optional[Dict[str, float]] = None) -> List[dict]:
        """
        F7.3: Get sector allocation breakdown.
        
        Returns list of sectors with value and percentage.
        """
        if prices is None:
            prices = {}
            for ticker in self.positions:
                price_data = fetch_latest_price(ticker)
                if price_data and price_data.get("price"):
                    prices[ticker] = price_data["price"]
        
        # Get sector for each position
        from data.stock_universe import load_universe
        universe_data = load_universe()
        ticker_to_sector = {}
        if universe_data:
            for stock in universe_data.get("stocks", []):
                ticker_to_sector[stock["ticker"]] = stock["sector"]
        
        # Calculate sector values
        sector_values: Dict[str, float] = {}
        total_value = 0.0
        
        for ticker, position in self.positions.items():
            price = prices.get(ticker, position.avg_cost)
            value = position.market_value(price)
            total_value += value
            
            sector = ticker_to_sector.get(ticker, "Unknown")
            sector_values[sector] = sector_values.get(sector, 0) + value
        
        # Build result
        result = []
        for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
            pct = (value / total_value * 100) if total_value > 0 else 0
            result.append({
                "sector": sector,
                "value": round(value, 2),
                "percentage": round(pct, 2),
            })
        
        return result


# ========== Portfolio History ==========

@dataclass
class PortfolioSnapshot:
    """A point-in-time snapshot of portfolio value."""
    timestamp: str
    total_value: float
    cash: float
    positions_value: float
    total_pnl: float
    total_pnl_percent: float
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "PortfolioSnapshot":
        return cls(**data)


class PortfolioHistory:
    """
    F7.2: Tracks portfolio value over time.
    
    Records daily snapshots for charting.
    """
    
    def __init__(self):
        self.snapshots: List[PortfolioSnapshot] = []
        self._load()
    
    def _load(self):
        """Load history from file."""
        if PORTFOLIO_HISTORY_FILE.exists():
            with open(PORTFOLIO_HISTORY_FILE) as f:
                data = json.load(f)
            self.snapshots = [PortfolioSnapshot.from_dict(s) for s in data.get("snapshots", [])]
    
    def _save(self):
        """Save history to file."""
        PORTFOLIO_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "snapshots": [s.to_dict() for s in self.snapshots],
            "updated_at": datetime.now().isoformat(),
        }
        with open(PORTFOLIO_HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def record_snapshot(self, portfolio: Portfolio, prices: Optional[Dict[str, float]] = None):
        """Record current portfolio state."""
        summary = portfolio.get_summary(prices)
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now().isoformat(),
            total_value=summary.total_value,
            cash=summary.cash,
            positions_value=summary.positions_value,
            total_pnl=summary.total_pnl,
            total_pnl_percent=summary.total_pnl_percent,
        )
        
        self.snapshots.append(snapshot)
        
        # Keep last 365 days of data
        self.snapshots = self.snapshots[-365:]
        self._save()
    
    def get_history(self, days: int = 30) -> List[dict]:
        """Get portfolio history for last N days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        result = []
        for snapshot in self.snapshots:
            # Parse ISO timestamp
            try:
                ts = datetime.fromisoformat(snapshot.timestamp.replace("Z", "+00:00"))
                if ts.timestamp() >= cutoff:
                    result.append(snapshot.to_dict())
            except:
                result.append(snapshot.to_dict())
        
        return result
    
    def get_performance(self, days: int = 30) -> dict:
        """Calculate performance metrics over period."""
        history = self.get_history(days)
        
        if len(history) < 2:
            return {
                "period_days": days,
                "start_value": None,
                "end_value": None,
                "change": None,
                "change_percent": None,
            }
        
        start = history[0]
        end = history[-1]
        
        change = end["total_value"] - start["total_value"]
        change_pct = (change / start["total_value"] * 100) if start["total_value"] > 0 else 0
        
        return {
            "period_days": days,
            "start_value": start["total_value"],
            "end_value": end["total_value"],
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "data_points": len(history),
        }
    
    def clear(self):
        """Clear all history."""
        self.snapshots = []
        self._save()


# ========== Global Instances ==========

_portfolio_history: Optional[PortfolioHistory] = None


def get_portfolio_history() -> PortfolioHistory:
    """Get or create the global portfolio history."""
    global _portfolio_history
    
    if _portfolio_history is None:
        _portfolio_history = PortfolioHistory()
    
    return _portfolio_history


# ========== Global Portfolio Instance ==========

_portfolio: Optional[Portfolio] = None


def get_portfolio() -> Portfolio:
    """Get or create the global portfolio instance."""
    global _portfolio
    
    if _portfolio is None:
        # Try to load from file
        _portfolio = Portfolio.load()
        
        if _portfolio is None:
            # Create new paper portfolio
            _portfolio = Portfolio(starting_cash=DEFAULT_CASH, is_paper=True)
            _portfolio.save()
    
    return _portfolio


def reset_portfolio(starting_cash: float = DEFAULT_CASH) -> Portfolio:
    """Reset the global portfolio."""
    global _portfolio
    _portfolio = Portfolio(starting_cash=starting_cash, is_paper=True)
    _portfolio.save()
    return _portfolio
