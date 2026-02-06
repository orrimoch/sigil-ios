"""
F12.3 Basic Backtest Engine

Execute simulated trades based on historical scores and measure performance.

Features:
- Signal-based entry/exit (BUY when score ≥ threshold, SELL when < threshold)
- Equal-weight position sizing
- Configurable parameters (thresholds, max positions, rebalance frequency)
- Transaction costs and slippage
- Trade log generation
- Equity curve tracking
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from loguru import logger
from collections import defaultdict
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    BacktestResult,
    BacktestTrade,
    BacktestStatus,
    EquityPoint,
    HistoricalScore,
    get_data_store,
)


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = CACHE_DIR / "prices"


@dataclass
class Position:
    """A position in the simulated portfolio."""
    ticker: str
    quantity: float
    avg_cost: float
    opened_at: str
    current_price: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class PortfolioState:
    """Current state of the simulated portfolio."""
    date: str
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    nav: float = 0.0
    daily_return: float = 0.0
    
    def calculate_nav(self) -> float:
        """Calculate total NAV."""
        positions_value = sum(p.current_value for p in self.positions.values())
        self.nav = self.cash + positions_value
        return self.nav


class BacktestEngine:
    """
    Executes backtests by simulating trades based on historical scores.
    
    Strategy Logic:
    1. On each rebalance date, get all scores
    2. Identify BUY signals (score >= entry_threshold)
    3. Identify SELL signals for current positions (score < exit_threshold)
    4. Execute sells first (free up cash)
    5. Execute buys (equal weight allocation)
    6. Track daily NAV and equity curve
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._benchmark_cache: Optional[pd.DataFrame] = None
    
    def run_backtest(
        self,
        params: BacktestParameters,
        progress_callback: Optional[callable] = None,
    ) -> BacktestResult:
        """
        Run a complete backtest.
        
        Args:
            params: Backtest parameters
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            BacktestResult with all metrics
        """
        # Create backtest record
        result = self.data_store.create_backtest(params)
        result.status = BacktestStatus.RUNNING
        self.data_store.save_backtest_result(result)
        
        logger.info(f"Starting backtest {result.backtest_id}")
        logger.info(f"Parameters: {params.start_date} to {params.end_date}, "
                   f"capital=${params.initial_capital:,.0f}")
        
        try:
            # Get historical scores
            scores_by_date = self.data_store.get_historical_scores(
                params.start_date,
                params.end_date
            )
            
            if not scores_by_date:
                raise ValueError("No historical scores available for the date range")
            
            # Pre-fetch prices
            all_tickers = set()
            for date_scores in scores_by_date.values():
                all_tickers.update(date_scores.keys())
            
            logger.info(f"Fetching prices for {len(all_tickers)} tickers...")
            self._prefetch_prices(list(all_tickers), params.start_date, params.end_date)
            
            # Fetch benchmark (SPY)
            self._fetch_benchmark(params.start_date, params.end_date)
            
            # Initialize portfolio
            portfolio = PortfolioState(
                date=params.start_date,
                cash=params.initial_capital,
            )
            
            # Generate trading dates
            trading_dates = self._get_trading_dates(
                params.start_date,
                params.end_date,
                params.rebalance_freq
            )
            
            logger.info(f"Processing {len(trading_dates)} trading dates...")
            
            # Track results
            trades: List[BacktestTrade] = []
            equity_curve: List[EquityPoint] = []
            peak_nav = params.initial_capital
            
            # Process each trading date
            for i, trade_date in enumerate(trading_dates):
                if progress_callback:
                    progress_callback(i + 1, len(trading_dates), f"Processing {trade_date}")
                
                # Update prices for current positions
                self._update_position_prices(portfolio, trade_date)
                
                # Get scores for this date
                date_scores = scores_by_date.get(trade_date, {})
                
                if date_scores:
                    # Execute rebalance trades
                    new_trades = self._execute_rebalance(
                        portfolio,
                        date_scores,
                        params,
                        trade_date
                    )
                    trades.extend(new_trades)
                
                # Calculate NAV
                portfolio.calculate_nav()
                
                # Track drawdown
                if portfolio.nav > peak_nav:
                    peak_nav = portfolio.nav
                drawdown = (portfolio.nav - peak_nav) / peak_nav if peak_nav > 0 else 0
                
                # Calculate daily return
                prev_nav = equity_curve[-1].nav if equity_curve else params.initial_capital
                daily_return = (portfolio.nav - prev_nav) / prev_nav if prev_nav > 0 else 0
                
                # Record equity point
                equity_curve.append(EquityPoint(
                    date=trade_date,
                    nav=portfolio.nav,
                    cash=portfolio.cash,
                    positions_value=portfolio.nav - portfolio.cash,
                    daily_return=daily_return,
                    cumulative_return=(portfolio.nav / params.initial_capital - 1),
                    drawdown=drawdown,
                ))
            
            # Save trades
            if trades:
                self.data_store.save_trades(result.backtest_id, trades)
            
            # Calculate final metrics
            result = self._calculate_metrics(result, equity_curve, trades, params)
            result.equity_curve = equity_curve
            result.status = BacktestStatus.COMPLETED
            result.completed_at = datetime.now().isoformat()
            
            self.data_store.save_backtest_result(result)
            
            logger.info(f"Backtest {result.backtest_id} completed")
            logger.info(f"Total Return: {result.total_return:.2%}")
            logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
            logger.info(f"Max Drawdown: {result.max_drawdown:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            result.status = BacktestStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now().isoformat()
            self.data_store.save_backtest_result(result)
            raise
    
    def _get_trading_dates(
        self,
        start_date: str,
        end_date: str,
        frequency: str
    ) -> List[str]:
        """Generate list of trading dates based on frequency."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        dates = []
        current = start
        
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:
                dates.append(current.strftime("%Y-%m-%d"))
                
                if frequency == "weekly":
                    # Move to next Friday
                    days_until_friday = (4 - current.weekday()) % 7
                    if days_until_friday == 0:
                        days_until_friday = 7
                    current += timedelta(days=days_until_friday)
                elif frequency == "biweekly":
                    current += timedelta(days=14)
                elif frequency == "monthly":
                    # Move to same day next month
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
                else:  # daily
                    current += timedelta(days=1)
            else:
                current += timedelta(days=1)
        
        return dates
    
    def _prefetch_prices(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str
    ) -> None:
        """Pre-fetch all price data."""
        buffer_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        buffer_end = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        
        for ticker in tickers:
            try:
                # Check local cache first
                parquet_path = PRICES_DIR / f"{ticker}.parquet"
                if parquet_path.exists():
                    df = pd.read_parquet(parquet_path)
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    self._price_cache[ticker] = df
                    continue
                
                # Fetch from yfinance
                stock = yf.Ticker(ticker)
                df = stock.history(start=buffer_start, end=buffer_end, interval="1d")
                
                if df.empty:
                    continue
                
                df = df.reset_index()
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df['ticker'] = ticker
                
                self._price_cache[ticker] = df
                
            except Exception as e:
                logger.warning(f"Failed to fetch prices for {ticker}: {e}")
    
    def _fetch_benchmark(self, start_date: str, end_date: str) -> None:
        """Fetch SPY benchmark data."""
        try:
            stock = yf.Ticker("SPY")
            df = stock.history(start=start_date, end=end_date, interval="1d")
            
            if not df.empty:
                df = df.reset_index()
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                self._benchmark_cache = df
                
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark: {e}")
    
    def _get_price(self, ticker: str, date: str) -> Optional[float]:
        """Get closing price for a ticker on a date."""
        df = self._price_cache.get(ticker)
        if df is None:
            return None
        
        # Find closest date <= target date
        mask = df['date'] <= date
        filtered = df[mask]
        
        if filtered.empty:
            return None
        
        return float(filtered.iloc[-1]['close'])
    
    def _update_position_prices(self, portfolio: PortfolioState, date: str) -> None:
        """Update current prices for all positions."""
        for ticker, position in portfolio.positions.items():
            price = self._get_price(ticker, date)
            if price:
                position.current_price = price
                position.current_value = position.quantity * price
                position.unrealized_pnl = position.current_value - (position.quantity * position.avg_cost)
    
    def _execute_rebalance(
        self,
        portfolio: PortfolioState,
        scores: Dict[str, HistoricalScore],
        params: BacktestParameters,
        date: str
    ) -> List[BacktestTrade]:
        """
        Execute rebalancing trades based on scores.
        
        Returns list of executed trades.
        """
        trades = []
        
        # Identify sell signals (current positions with score < exit_threshold)
        sells = []
        for ticker, position in list(portfolio.positions.items()):
            score = scores.get(ticker)
            if score and score.composite_score < params.exit_threshold:
                sells.append((ticker, position, score))
        
        # Execute sells
        for ticker, position, score in sells:
            price = self._get_price(ticker, date)
            if not price:
                continue
            
            # Apply slippage (sell at slightly lower price)
            execution_price = price * (1 - params.slippage)
            value = position.quantity * execution_price
            commission = value * params.transaction_cost
            
            # Update portfolio
            portfolio.cash += value - commission
            del portfolio.positions[ticker]
            
            trades.append(BacktestTrade(
                trade_id=f"t_{date}_{ticker}_sell",
                backtest_id="",  # Set by caller
                date=date,
                ticker=ticker,
                side="sell",
                quantity=position.quantity,
                price=execution_price,
                value=value,
                score_at_trade=score.composite_score,
                signal_at_trade=score.signal,
                commission=commission,
                slippage_cost=position.quantity * price * params.slippage,
            ))
        
        # Identify buy signals
        buy_candidates = []
        for ticker, score in scores.items():
            if ticker not in portfolio.positions:
                if score.composite_score >= params.entry_threshold:
                    price = self._get_price(ticker, date)
                    if price:
                        buy_candidates.append((ticker, score, price))
        
        # Sort by score (highest first)
        buy_candidates.sort(key=lambda x: x[1].composite_score, reverse=True)
        
        # Limit to max_positions - current positions
        available_slots = params.max_positions - len(portfolio.positions)
        buy_candidates = buy_candidates[:max(0, available_slots)]
        
        if not buy_candidates:
            return trades
        
        # Calculate position size (equal weight)
        total_portfolio_value = portfolio.cash + sum(p.current_value for p in portfolio.positions.values())
        target_position_value = total_portfolio_value / params.max_positions
        
        # Execute buys
        for ticker, score, price in buy_candidates:
            # Apply slippage (buy at slightly higher price)
            execution_price = price * (1 + params.slippage)
            
            # Calculate shares to buy
            available_cash = portfolio.cash * 0.99  # Keep 1% buffer
            max_value = min(target_position_value, available_cash)
            
            if max_value < 100:  # Skip if too small
                continue
            
            shares = int(max_value / execution_price)
            if shares < 1:
                continue
            
            value = shares * execution_price
            commission = value * params.transaction_cost
            total_cost = value + commission
            
            if total_cost > portfolio.cash:
                continue
            
            # Update portfolio
            portfolio.cash -= total_cost
            portfolio.positions[ticker] = Position(
                ticker=ticker,
                quantity=shares,
                avg_cost=execution_price,
                opened_at=date,
                current_price=execution_price,
                current_value=value,
            )
            
            trades.append(BacktestTrade(
                trade_id=f"t_{date}_{ticker}_buy",
                backtest_id="",
                date=date,
                ticker=ticker,
                side="buy",
                quantity=shares,
                price=execution_price,
                value=value,
                score_at_trade=score.composite_score,
                signal_at_trade=score.signal,
                commission=commission,
                slippage_cost=shares * price * params.slippage,
            ))
        
        return trades
    
    def _calculate_metrics(
        self,
        result: BacktestResult,
        equity_curve: List[EquityPoint],
        trades: List[BacktestTrade],
        params: BacktestParameters
    ) -> BacktestResult:
        """Calculate all performance metrics."""
        if not equity_curve:
            return result
        
        # Basic returns
        initial_nav = params.initial_capital
        final_nav = equity_curve[-1].nav
        
        result.total_return = (final_nav / initial_nav) - 1
        
        # CAGR
        start = datetime.strptime(params.start_date, "%Y-%m-%d")
        end = datetime.strptime(params.end_date, "%Y-%m-%d")
        years = (end - start).days / 365.25
        
        if years > 0 and final_nav > 0:
            result.cagr = (final_nav / initial_nav) ** (1 / years) - 1
        
        # Volatility and Sharpe
        returns = [ep.daily_return for ep in equity_curve if ep.daily_return != 0]
        
        if len(returns) > 1:
            daily_vol = np.std(returns)
            result.volatility = daily_vol * np.sqrt(252)  # Annualized
            
            # Sharpe (assuming 4% risk-free rate)
            risk_free = 0.04 / 252  # Daily
            excess_return = np.mean(returns) - risk_free
            
            if daily_vol > 0:
                result.sharpe_ratio = (excess_return / daily_vol) * np.sqrt(252)
            else:
                result.sharpe_ratio = 0.0
        
        # Max Drawdown
        drawdowns = [ep.drawdown for ep in equity_curve]
        result.max_drawdown = min(drawdowns) if drawdowns else 0
        
        # Win Rate
        result.total_trades = len(trades)
        
        if trades:
            # Calculate win rate based on sell trades
            sell_trades = [t for t in trades if t.side == "sell"]
            
            if sell_trades:
                # Find corresponding buy trades
                wins = 0
                for sell in sell_trades:
                    # Find the buy trade for this ticker
                    buys = [t for t in trades if t.ticker == sell.ticker and t.side == "buy" and t.date < sell.date]
                    if buys:
                        buy = buys[-1]  # Most recent buy
                        if sell.price > buy.price:
                            wins += 1
                
                result.win_rate = wins / len(sell_trades) if sell_trades else 0.5
            else:
                result.win_rate = 0.5  # No completed trades
        
        # Benchmark comparison
        if self._benchmark_cache is not None and len(self._benchmark_cache) > 0:
            spy_start = self._benchmark_cache.iloc[0]['close']
            spy_end = self._benchmark_cache.iloc[-1]['close']
            result.benchmark_return = (spy_end / spy_start) - 1
            result.alpha = result.total_return - result.benchmark_return
        
        return result


# Convenience function
def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    entry_threshold: float = 70,
    exit_threshold: float = 50,
    max_positions: int = 10,
) -> BacktestResult:
    """Run a backtest with the specified parameters."""
    params = BacktestParameters(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        max_positions=max_positions,
    )
    
    engine = BacktestEngine()
    return engine.run_backtest(params)


# CLI for testing
if __name__ == "__main__":
    print("\n=== Backtest Engine Test ===\n")
    
    # First, ensure we have some historical scores
    from backtest.historical_scores import HistoricalScoreGenerator
    
    generator = HistoricalScoreGenerator()
    generator.generate_from_existing_pipeline()
    
    # Run a small backtest
    params = BacktestParameters(
        start_date="2026-01-01",
        end_date="2026-02-06",
        initial_capital=100000,
        entry_threshold=70,
        exit_threshold=50,
        max_positions=5,
    )
    
    engine = BacktestEngine()
    
    try:
        result = engine.run_backtest(params)
        
        print(f"\n=== Results ===")
        print(f"Backtest ID: {result.backtest_id}")
        print(f"Status: {result.status.value}")
        print(f"Total Return: {result.total_return:.2%}" if result.total_return else "N/A")
        print(f"CAGR: {result.cagr:.2%}" if result.cagr else "N/A")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "N/A")
        print(f"Max Drawdown: {result.max_drawdown:.2%}" if result.max_drawdown else "N/A")
        print(f"Win Rate: {result.win_rate:.2%}" if result.win_rate else "N/A")
        print(f"Total Trades: {result.total_trades}")
        
        if result.benchmark_return:
            print(f"Benchmark (SPY): {result.benchmark_return:.2%}")
            print(f"Alpha: {result.alpha:.2%}")
        
    except Exception as e:
        print(f"Backtest failed: {e}")
        raise
    
    print("\n✅ Backtest Engine working!")
