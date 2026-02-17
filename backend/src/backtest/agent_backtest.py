"""
Agent Backtest Integration (REC-297)

Runs the agent decision logic on historical data and compares
performance against the rules-based backtest.

Uses the same BacktestEngine infrastructure but replaces
signal-based entry/exit with agent decision making.
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import BacktestEngine, Position, PortfolioState
from backtest.data_store import (
    BacktestParameters,
    BacktestResult,
    BacktestTrade,
    BacktestStatus,
    EquityPoint,
    get_data_store,
)

# Agent imports
from agent.context import (
    TradingContext,
    PortfolioState as AgentPortfolioState,
    Position as AgentPosition,
    MarketState,
    StockCandidate,
    DataFreshness,
)
from agent.decision_engine import DecisionEngine, SYSTEM_PROMPT
from agent.position_sizing import PositionSizer, TradeDecision


@dataclass
class AgentBacktestConfig:
    """Configuration for agent backtest."""
    # Time period
    start_date: str = "2019-06-01"
    end_date: str = "2023-12-31"
    
    # Capital
    initial_capital: float = 100_000.0
    
    # Agent settings
    rebalance_freq: str = "weekly"  # weekly, biweekly, monthly
    max_positions: int = 10
    buy_threshold: float = 75.0
    sell_threshold: float = 40.0
    
    # Costs
    transaction_cost_bps: float = 10.0  # 10 bps = 0.1%
    slippage_bps: float = 5.0
    
    # Use actual Claude API or mock?
    use_mock_decisions: bool = True  # Set False for real Claude calls


class AgentBacktestEngine:
    """
    Backtest engine that uses agent decision logic.
    
    Differences from rules-based backtest:
    1. Uses Claude (or mock) for BUY/SELL decisions
    2. Uses risk parity for position sizing
    3. Considers sector exposure and correlations
    """
    
    def __init__(self, config: AgentBacktestConfig = None):
        self.config = config or AgentBacktestConfig()
        self.base_engine = BacktestEngine()
        self.data_store = get_data_store()
        
        # Agent components
        self.decision_engine = DecisionEngine()
        self.position_sizer = PositionSizer()
        
        # Cache
        self._scores_cache: Dict[str, Dict] = {}
        self._prices_cache: Dict[str, Dict[str, float]] = {}
    
    async def run_backtest(
        self,
        progress_callback: Optional[callable] = None
    ) -> BacktestResult:
        """
        Run agent-based backtest on historical data.
        
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting agent backtest: {self.config.start_date} to {self.config.end_date}")
        
        # Create result
        result = BacktestResult(
            backtest_id=f"agent_bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.now().isoformat(),
            status=BacktestStatus.RUNNING,
            parameters=BacktestParameters(
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                initial_capital=self.config.initial_capital,
                rebalance_freq=self.config.rebalance_freq,
                entry_threshold=self.config.buy_threshold,
                exit_threshold=self.config.sell_threshold,
                max_positions=self.config.max_positions,
                transaction_cost_bps=self.config.transaction_cost_bps,
                slippage_bps=self.config.slippage_bps,
            ),
        )
        
        try:
            # Load historical scores
            scores_by_date = await self._load_historical_scores()
            
            if not scores_by_date:
                raise ValueError("No historical scores available for backtest period")
            
            # Initialize portfolio
            portfolio = PortfolioState(
                date=self.config.start_date,
                cash=self.config.initial_capital,
            )
            
            # Generate trading dates
            trading_dates = self.base_engine._get_trading_dates(
                self.config.start_date,
                self.config.end_date,
                self.config.rebalance_freq
            )
            
            logger.info(f"Processing {len(trading_dates)} trading dates with agent logic...")
            
            # Track results
            trades: List[BacktestTrade] = []
            equity_curve: List[EquityPoint] = []
            decisions_log: List[Dict] = []
            peak_nav = self.config.initial_capital
            
            # Process each trading date
            for i, trade_date in enumerate(trading_dates):
                if progress_callback:
                    progress_callback(i + 1, len(trading_dates), f"Agent analyzing {trade_date}")
                
                # Update prices
                self._update_position_prices(portfolio, trade_date)
                
                # Get scores for this date
                date_scores = scores_by_date.get(trade_date, {})
                
                if date_scores:
                    # Build agent context
                    context = self._build_context(portfolio, date_scores, trade_date)
                    
                    # Get agent decisions
                    decisions = await self._get_agent_decisions(context, date_scores)
                    decisions_log.append({
                        "date": trade_date,
                        "decisions": [d.__dict__ for d in decisions]
                    })
                    
                    # Execute decisions
                    new_trades = await self._execute_agent_decisions(
                        portfolio, decisions, context, trade_date
                    )
                    trades.extend(new_trades)
                
                # Calculate NAV
                portfolio.calculate_nav()
                
                # Track drawdown
                if portfolio.nav > peak_nav:
                    peak_nav = portfolio.nav
                drawdown = (portfolio.nav - peak_nav) / peak_nav if peak_nav > 0 else 0
                
                # Calculate daily return
                prev_nav = equity_curve[-1].nav if equity_curve else self.config.initial_capital
                daily_return = (portfolio.nav - prev_nav) / prev_nav if prev_nav > 0 else 0
                
                # Record equity point
                equity_curve.append(EquityPoint(
                    date=trade_date,
                    nav=portfolio.nav,
                    cash=portfolio.cash,
                    positions_value=portfolio.nav - portfolio.cash,
                    daily_return=daily_return,
                    cumulative_return=(portfolio.nav / self.config.initial_capital - 1),
                    drawdown=drawdown,
                ))
            
            # Save results
            if trades:
                self.data_store.save_trades(result.backtest_id, trades)
            
            # Calculate metrics
            result = self._calculate_metrics(result, equity_curve, trades)
            result.equity_curve = equity_curve
            result.status = BacktestStatus.COMPLETED
            result.completed_at = datetime.now().isoformat()
            
            # Save decisions log
            self._save_decisions_log(result.backtest_id, decisions_log)
            
            self.data_store.save_backtest_result(result)
            
            logger.info(f"Agent backtest {result.backtest_id} completed")
            logger.info(f"Total Return: {result.total_return:.2%}")
            logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
            logger.info(f"Max Drawdown: {result.max_drawdown:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"Agent backtest failed: {e}")
            result.status = BacktestStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now().isoformat()
            self.data_store.save_backtest_result(result)
            raise
    
    def _build_context(
        self,
        portfolio: PortfolioState,
        scores: Dict[str, Dict],
        trade_date: str
    ) -> TradingContext:
        """Build TradingContext from backtest state."""
        # Convert positions
        positions = []
        for ticker, pos in portfolio.positions.items():
            positions.append(AgentPosition(
                ticker=ticker,
                shares=int(pos.quantity),
                avg_cost=pos.avg_cost,
                current_price=pos.current_price,
                market_value=pos.current_value,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_pct=(pos.unrealized_pnl / (pos.avg_cost * pos.quantity) * 100) if pos.quantity > 0 else 0,
                sector=scores.get(ticker, {}).get("sector", "Unknown"),
            ))
        
        # Calculate sector exposure
        total_value = portfolio.nav
        sector_exposure = {}
        for pos in positions:
            sector = pos.sector
            weight = pos.market_value / total_value if total_value > 0 else 0
            sector_exposure[sector] = sector_exposure.get(sector, 0) + weight
        
        # Build portfolio state
        agent_portfolio = AgentPortfolioState(
            cash=portfolio.cash,
            total_value=portfolio.nav,
            positions=positions,
            sector_exposure=sector_exposure,
            unrealized_pnl=sum(p.unrealized_pnl for p in positions),
        )
        
        # Build buy candidates (top scores not owned)
        owned_tickers = set(portfolio.positions.keys())
        buy_candidates = []
        for ticker, data in sorted(scores.items(), key=lambda x: x[1].get("total_score", 0), reverse=True):
            if ticker not in owned_tickers and data.get("total_score", 0) >= self.config.buy_threshold:
                buy_candidates.append(StockCandidate(
                    ticker=ticker,
                    company_name=data.get("company_name", ticker),
                    score=data.get("total_score", 0),
                    signal="BUY",
                    sector=data.get("sector", "Unknown"),
                    rank=len(buy_candidates) + 1,
                    fundamental_score=data.get("fundamental_score", 50),
                    sentiment_score=data.get("sentiment_score", 50),
                    technical_score=data.get("technical_score", 50),
                    macro_score=data.get("macro_score", 50),
                ))
                if len(buy_candidates) >= 10:
                    break
        
        # Build sell candidates (owned with low scores)
        sell_candidates = []
        for ticker in owned_tickers:
            score_data = scores.get(ticker, {})
            score = score_data.get("total_score", 50)
            if score < self.config.sell_threshold:
                sell_candidates.append(StockCandidate(
                    ticker=ticker,
                    company_name=score_data.get("company_name", ticker),
                    score=score,
                    signal="SELL",
                    sector=score_data.get("sector", "Unknown"),
                    rank=0,
                    fundamental_score=score_data.get("fundamental_score", 50),
                    sentiment_score=score_data.get("sentiment_score", 50),
                    technical_score=score_data.get("technical_score", 50),
                    macro_score=score_data.get("macro_score", 50),
                ))
        
        # Mock market state (could use historical VIX data)
        market_state = MarketState(
            regime="normal",
            regime_confidence=0.8,
            vix=15.0,
            vix_change=0.0,
            vix_regime="calm",
            trend="sideways",
        )
        
        return TradingContext(
            timestamp=datetime.fromisoformat(trade_date),
            portfolio=agent_portfolio,
            market=market_state,
            buy_candidates=buy_candidates,
            sell_candidates=sell_candidates,
            hold_review=[],
            data_freshness=DataFreshness(),  # Not stale in backtest
        )
    
    async def _get_agent_decisions(
        self,
        context: TradingContext,
        scores: Dict[str, Dict]
    ) -> List[TradeDecision]:
        """Get trading decisions from agent (mock or real)."""
        if self.config.use_mock_decisions:
            return self._mock_agent_decisions(context)
        else:
            # Use real Claude API
            result = await self.decision_engine.decide(context, memories=[])
            return result.decisions
    
    def _mock_agent_decisions(self, context: TradingContext) -> List[TradeDecision]:
        """
        Mock agent decisions based on score thresholds.
        
        Mimics what the agent would do without calling Claude API.
        """
        decisions = []
        
        # SELL decisions (existing positions with low scores)
        for candidate in context.sell_candidates:
            decisions.append(TradeDecision(
                ticker=candidate.ticker,
                action="SELL",
                score=candidate.score,
                confidence=0.8,
                sector=candidate.sector,
                rationale=f"Score {candidate.score:.0f} below threshold",
            ))
        
        # BUY decisions (top candidates, respect position limits)
        current_positions = len(context.portfolio.positions)
        available_slots = self.config.max_positions - current_positions + len(decisions)  # Account for sells
        
        for candidate in context.buy_candidates[:available_slots]:
            decisions.append(TradeDecision(
                ticker=candidate.ticker,
                action="BUY",
                score=candidate.score,
                confidence=0.75,
                sector=candidate.sector,
                rationale=f"Score {candidate.score:.0f}, sector diversification",
            ))
        
        return decisions
    
    async def _execute_agent_decisions(
        self,
        portfolio: PortfolioState,
        decisions: List[TradeDecision],
        context: TradingContext,
        trade_date: str
    ) -> List[BacktestTrade]:
        """Execute agent decisions and return trade records."""
        trades = []
        
        # Process SELLs first (free up cash)
        for decision in [d for d in decisions if d.action == "SELL"]:
            if decision.ticker in portfolio.positions:
                pos = portfolio.positions[decision.ticker]
                
                # Calculate sell amount (using tiered logic from position_sizing)
                sell_pct = self._get_sell_percentage(decision.score, pos)
                shares_to_sell = int(pos.quantity * sell_pct)
                
                if shares_to_sell > 0:
                    price = pos.current_price
                    proceeds = shares_to_sell * price * (1 - self.config.transaction_cost_bps / 10000)
                    
                    # Update position
                    pos.quantity -= shares_to_sell
                    if pos.quantity <= 0:
                        del portfolio.positions[decision.ticker]
                    
                    portfolio.cash += proceeds
                    
                    trades.append(BacktestTrade(
                        date=trade_date,
                        ticker=decision.ticker,
                        action="SELL",
                        quantity=shares_to_sell,
                        price=price,
                        value=proceeds,
                        signal_score=decision.score,
                        rationale=decision.rationale,
                    ))
        
        # Process BUYs
        buy_decisions = [d for d in decisions if d.action == "BUY"]
        if buy_decisions:
            # Use simple position sizing for backtest (equal weight among buys)
            available_cash = portfolio.cash * 0.9  # Keep 10% buffer
            cash_per_position = available_cash / len(buy_decisions)
            
            for decision in buy_decisions:
                if portfolio.cash < 1000:  # Minimum cash threshold
                    break
                
                # Get price
                price = self._get_price(decision.ticker, trade_date)
                if price <= 0:
                    continue
                
                # Calculate shares
                position_value = min(cash_per_position, portfolio.cash * 0.9)
                cost_adjusted = position_value * (1 + self.config.transaction_cost_bps / 10000)
                shares = int(position_value / price)
                
                if shares < 1:
                    continue
                
                actual_cost = shares * price * (1 + self.config.transaction_cost_bps / 10000)
                
                if actual_cost > portfolio.cash:
                    continue
                
                portfolio.cash -= actual_cost
                
                # Add or update position
                if decision.ticker in portfolio.positions:
                    pos = portfolio.positions[decision.ticker]
                    total_shares = pos.quantity + shares
                    pos.avg_cost = (pos.avg_cost * pos.quantity + price * shares) / total_shares
                    pos.quantity = total_shares
                else:
                    portfolio.positions[decision.ticker] = Position(
                        ticker=decision.ticker,
                        quantity=shares,
                        avg_cost=price,
                        opened_at=trade_date,
                        current_price=price,
                        current_value=shares * price,
                    )
                
                trades.append(BacktestTrade(
                    date=trade_date,
                    ticker=decision.ticker,
                    action="BUY",
                    quantity=shares,
                    price=price,
                    value=shares * price,
                    signal_score=decision.score,
                    rationale=decision.rationale,
                ))
        
        return trades
    
    def _get_sell_percentage(self, score: float, position: Position) -> float:
        """Get sell percentage based on score (tiered logic)."""
        pnl_pct = (position.unrealized_pnl / (position.avg_cost * position.quantity) * 100) if position.quantity > 0 else 0
        
        # Stop-loss
        if pnl_pct <= -8.0:
            return 1.0
        if pnl_pct <= -15.0:
            return 1.0
        
        # Score-based tiers
        if score < 40:
            return 1.0
        elif score < 50:
            return 0.5
        elif score < 60:
            return 0.25
        else:
            return 0.1
    
    def _update_position_prices(self, portfolio: PortfolioState, trade_date: str):
        """Update current prices for all positions."""
        for ticker, pos in portfolio.positions.items():
            price = self._get_price(ticker, trade_date)
            if price > 0:
                pos.current_price = price
                pos.current_value = pos.quantity * price
                pos.unrealized_pnl = pos.current_value - (pos.quantity * pos.avg_cost)
    
    def _get_price(self, ticker: str, date: str) -> float:
        """Get price for ticker on date (with caching)."""
        cache_key = f"{ticker}_{date}"
        if cache_key in self._prices_cache:
            return self._prices_cache[cache_key]
        
        price = self.base_engine._get_price_on_date(ticker, date)
        self._prices_cache[cache_key] = price
        return price
    
    async def _load_historical_scores(self) -> Dict[str, Dict[str, Dict]]:
        """Load historical scores for backtest period."""
        from backtest.historical_scores import HistoricalScoreManager
        
        manager = HistoricalScoreManager()
        
        # This returns {date: {ticker: score_data}}
        scores = manager.get_scores_for_period(
            self.config.start_date,
            self.config.end_date
        )
        
        return scores
    
    def _calculate_metrics(
        self,
        result: BacktestResult,
        equity_curve: List[EquityPoint],
        trades: List[BacktestTrade]
    ) -> BacktestResult:
        """Calculate performance metrics."""
        if not equity_curve:
            return result
        
        import numpy as np
        
        # Basic metrics
        final_nav = equity_curve[-1].nav
        initial_nav = self.config.initial_capital
        
        result.total_return = (final_nav / initial_nav) - 1
        result.final_nav = final_nav
        
        # Daily returns
        daily_returns = [ep.daily_return for ep in equity_curve]
        
        # Annualized return
        trading_days = len(equity_curve)
        years = trading_days / 252
        result.annualized_return = (1 + result.total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Volatility
        if daily_returns:
            result.volatility = np.std(daily_returns) * np.sqrt(252)
        
        # Sharpe Ratio (assuming 0% risk-free rate)
        if result.volatility and result.volatility > 0:
            result.sharpe_ratio = result.annualized_return / result.volatility
        
        # Max drawdown
        result.max_drawdown = min(ep.drawdown for ep in equity_curve)
        
        # Trade stats
        result.total_trades = len(trades)
        winning_trades = [t for t in trades if t.action == "SELL" and hasattr(t, 'pnl') and t.pnl > 0]
        result.win_rate = len(winning_trades) / len([t for t in trades if t.action == "SELL"]) if trades else 0
        
        return result
    
    def _save_decisions_log(self, backtest_id: str, decisions_log: List[Dict]):
        """Save agent decisions log for analysis."""
        log_path = Path(__file__).parent.parent.parent / "reports" / f"{backtest_id}_decisions.json"
        log_path.parent.mkdir(exist_ok=True)
        
        with open(log_path, 'w') as f:
            json.dump(decisions_log, f, indent=2, default=str)
        
        logger.info(f"Saved decisions log to {log_path}")


async def run_agent_backtest(
    start_date: str = "2019-06-01",
    end_date: str = "2023-12-31",
    use_mock: bool = True
) -> BacktestResult:
    """
    Run agent backtest and return results.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        use_mock: Use mock decisions (True) or real Claude API (False)
    
    Returns:
        BacktestResult with performance metrics
    """
    config = AgentBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        use_mock_decisions=use_mock,
    )
    
    engine = AgentBacktestEngine(config)
    return await engine.run_backtest()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run agent backtest")
    parser.add_argument("--start", default="2019-06-01", help="Start date")
    parser.add_argument("--end", default="2023-12-31", help="End date")
    parser.add_argument("--real", action="store_true", help="Use real Claude API")
    
    args = parser.parse_args()
    
    result = asyncio.run(run_agent_backtest(
        start_date=args.start,
        end_date=args.end,
        use_mock=not args.real
    ))
    
    print(f"\n{'='*50}")
    print("AGENT BACKTEST RESULTS")
    print(f"{'='*50}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Total Return: {result.total_return:.2%}")
    print(f"Annualized Return: {result.annualized_return:.2%}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown:.2%}")
    print(f"Total Trades: {result.total_trades}")
