"""
Agent Context Aggregator (REC-278)

Gathers all information needed for trading decisions into a single context object:
- Portfolio state (holdings, cash, P&L)
- Market state (regime, VIX)
- BUY/SELL candidates
- Sector exposures
- Data freshness
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class Position:
    """A single portfolio position."""
    ticker: str
    shares: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sector: str = "Unknown"


@dataclass
class PortfolioState:
    """Current portfolio state."""
    cash: float
    total_value: float
    positions: List[Position]
    sector_exposure: Dict[str, float]  # {sector: percentage}
    unrealized_pnl: float
    realized_pnl_today: float = 0.0
    position_count: int = 0
    
    def __post_init__(self):
        self.position_count = len(self.positions)


@dataclass
class MarketState:
    """Current market conditions."""
    regime: str  # "low_vol" | "normal" | "high_vol" | "crisis"
    regime_confidence: float
    vix: float
    vix_change: float = 0.0
    vix_regime: str = "normal"  # "calm" | "elevated" | "fear" | "panic"
    trend: str = "sideways"  # "up" | "down" | "sideways"


@dataclass
class StockCandidate:
    """A stock candidate for trading."""
    ticker: str
    company_name: str
    score: float
    signal: str  # "BUY" | "HOLD" | "SELL"
    sector: str
    rank: int
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float
    score_change: Optional[float] = None
    insider_score: Optional[float] = None
    volatility: Optional[float] = None


@dataclass
class DataFreshness:
    """Data freshness status."""
    scores_updated: Optional[datetime] = None
    scores_age_hours: Optional[float] = None
    regime_updated: Optional[datetime] = None
    regime_age_hours: Optional[float] = None
    prices_updated: Optional[datetime] = None
    vix_updated: Optional[datetime] = None
    is_stale: bool = False
    stale_reasons: List[str] = field(default_factory=list)


@dataclass
class TradingContext:
    """
    Complete trading context for agent decision-making.
    
    Contains all information needed to make BUY/SELL decisions:
    - Portfolio state
    - Market conditions
    - Top candidates
    - Data freshness
    """
    timestamp: datetime
    portfolio: PortfolioState
    market: MarketState
    buy_candidates: List[StockCandidate]  # Top BUY signals not owned
    sell_candidates: List[StockCandidate]  # Holdings with SELL signal
    hold_review: List[StockCandidate]  # Holdings with score dropped >10 pts
    data_freshness: DataFreshness
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "portfolio": {
                "cash": self.portfolio.cash,
                "total_value": self.portfolio.total_value,
                "position_count": self.portfolio.position_count,
                "unrealized_pnl": self.portfolio.unrealized_pnl,
                "realized_pnl_today": self.portfolio.realized_pnl_today,
                "positions": [asdict(p) for p in self.portfolio.positions],
                "sector_exposure": self.portfolio.sector_exposure,
            },
            "market": asdict(self.market),
            "buy_candidates": [asdict(c) for c in self.buy_candidates],
            "sell_candidates": [asdict(c) for c in self.sell_candidates],
            "hold_review": [asdict(c) for c in self.hold_review],
            "data_freshness": {
                "scores_updated": self.data_freshness.scores_updated.isoformat() if self.data_freshness.scores_updated else None,
                "scores_age_hours": self.data_freshness.scores_age_hours,
                "regime_updated": self.data_freshness.regime_updated.isoformat() if self.data_freshness.regime_updated else None,
                "regime_age_hours": self.data_freshness.regime_age_hours,
                "is_stale": self.data_freshness.is_stale,
                "stale_reasons": self.data_freshness.stale_reasons,
            },
            "summary": {
                "buy_count": len(self.buy_candidates),
                "sell_count": len(self.sell_candidates),
                "hold_review_count": len(self.hold_review),
                "top_buy": self.buy_candidates[0].ticker if self.buy_candidates else None,
                "top_buy_score": self.buy_candidates[0].score if self.buy_candidates else None,
            }
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ContextAggregator:
    """
    Aggregates all trading context from various data sources.
    
    Usage:
        aggregator = ContextAggregator()
        context = await aggregator.aggregate()
    """
    
    # Data freshness thresholds
    MAX_SCORES_AGE_HOURS = 168  # 7 days
    MAX_REGIME_AGE_HOURS = 24
    MAX_PRICES_AGE_MINUTES = 15  # During market hours
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
    
    async def aggregate(
        self,
        top_n_candidates: int = 20,
        include_hold_review: bool = True
    ) -> TradingContext:
        """
        Aggregate all context for trading decision.
        
        Args:
            top_n_candidates: Number of top BUY candidates to include
            include_hold_review: Include holdings with declining scores
            
        Returns:
            Complete TradingContext
        """
        logger.info("Aggregating trading context...")
        
        # Load all data sources
        scores = await self._load_scores()
        portfolio = await self._load_portfolio()
        market = await self._load_market_state()
        freshness = await self._check_data_freshness()
        
        # Get holdings tickers
        holdings = {p.ticker for p in portfolio.positions}
        
        # Find BUY candidates (not owned)
        buy_candidates = [
            self._score_to_candidate(ticker, data)
            for ticker, data in scores.items()
            if data.get("signal") == "BUY" and ticker not in holdings
        ]
        buy_candidates.sort(key=lambda x: x.score, reverse=True)
        buy_candidates = buy_candidates[:top_n_candidates]
        
        # Find SELL candidates (owned with SELL signal)
        sell_candidates = [
            self._score_to_candidate(ticker, data)
            for ticker, data in scores.items()
            if ticker in holdings and data.get("signal") == "SELL"
        ]
        
        # Find HOLD review (owned with score dropped significantly)
        hold_review = []
        if include_hold_review:
            for ticker in holdings:
                if ticker in scores:
                    data = scores[ticker]
                    change = data.get("score_change")
                    if change is not None and change < -10:
                        hold_review.append(self._score_to_candidate(ticker, data))
        
        context = TradingContext(
            timestamp=datetime.now(),
            portfolio=portfolio,
            market=market,
            buy_candidates=buy_candidates,
            sell_candidates=sell_candidates,
            hold_review=hold_review,
            data_freshness=freshness,
        )
        
        logger.info(
            f"Context aggregated: {len(buy_candidates)} BUY candidates, "
            f"{len(sell_candidates)} SELL, {len(hold_review)} hold review"
        )
        
        return context
    
    async def aggregate_for_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Get detailed context for a single ticker.
        
        Useful for debugging or single-stock analysis.
        """
        scores = await self._load_scores()
        
        if ticker.upper() not in scores:
            return {"error": f"Ticker {ticker} not found in scores"}
        
        data = scores[ticker.upper()]
        candidate = self._score_to_candidate(ticker.upper(), data)
        
        market = await self._load_market_state()
        
        return {
            "ticker": ticker.upper(),
            "score": candidate.score,
            "signal": candidate.signal,
            "components": {
                "fundamental": candidate.fundamental_score,
                "sentiment": candidate.sentiment_score,
                "technical": candidate.technical_score,
                "macro": candidate.macro_score,
            },
            "sector": candidate.sector,
            "rank": candidate.rank,
            "score_change": candidate.score_change,
            "market": asdict(market),
        }
    
    async def _load_scores(self) -> Dict[str, Dict]:
        """Load composite scores from JSON."""
        scores_path = self.data_dir / "composite_scores.json"
        
        if not scores_path.exists():
            logger.warning(f"Scores file not found: {scores_path}")
            return {}
        
        with open(scores_path) as f:
            data = json.load(f)
        
        return data.get("scores", {})
    
    async def _load_portfolio(self, user_id: str = "anonymous") -> PortfolioState:
        """
        Load portfolio state from Sigil database.
        
        Priority:
        1. Sigil DB (the app's portfolio) - PRIMARY
        2. IBKR (if connected)
        3. Mock/cached data (fallback)
        """
        # Try to load from Sigil DB first (this is the app's real portfolio)
        try:
            portfolio = await self._load_sigil_portfolio(user_id)
            if portfolio:
                logger.info(f"Loaded portfolio from Sigil DB: ${portfolio.total_value:,.2f}")
                return portfolio
        except Exception as e:
            logger.warning(f"Sigil DB not available: {e}")
        
        # Try IBKR if available
        try:
            from ibkr.ibkr_service import IBKRService
            ibkr = IBKRService()
            
            if ibkr.is_connected:
                portfolio_data = await ibkr.get_portfolio()
                return self._parse_ibkr_portfolio(portfolio_data)
        except Exception as e:
            logger.debug(f"IBKR not available: {e}")
        
        # Fallback to mock/cached portfolio
        return await self._load_mock_portfolio()
    
    async def _load_sigil_portfolio(self, user_id: str = "anonymous") -> Optional[PortfolioState]:
        """Load portfolio from Sigil's SQLite database."""
        import sqlite3
        from pathlib import Path
        
        # Use data_dir if set (for tests), otherwise try standard paths
        if self.data_dir:
            possible_paths = [
                self.data_dir / "sigil.db",
            ]
        else:
            possible_paths = [
                Path(__file__).parent.parent.parent / "data" / "sigil.db",  # backend/data/sigil.db
                Path(__file__).parent.parent / "data" / "sigil.db",  # src/data/sigil.db
                Path("data/sigil.db"),  # relative to cwd
            ]
        
        db_path = None
        for p in possible_paths:
            if p.exists():
                db_path = p
                break
        
        if db_path is None:
            # In test mode with data_dir, this is expected - fall back to mock
            if self.data_dir:
                logger.debug("Sigil database not found in test data_dir, using mock")
            else:
                logger.warning("Sigil database not found")
            return None
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Find the user's portfolio
            # Priority: specific user first, otherwise portfolio with most positions (the active one)
            if user_id and user_id != "anonymous":
                # Specific user requested
                cursor.execute("""
                    SELECT p.id, p.cash_balance, p.user_id,
                           (SELECT COUNT(*) FROM positions WHERE portfolio_id = p.id) as pos_count
                    FROM portfolios p
                    WHERE p.user_id = ?
                    LIMIT 1
                """, (user_id,))
            else:
                # No specific user - find the portfolio with most positions (the active one)
                cursor.execute("""
                    SELECT p.id, p.cash_balance, p.user_id,
                           (SELECT COUNT(*) FROM positions WHERE portfolio_id = p.id) as pos_count
                    FROM portfolios p
                    ORDER BY pos_count DESC
                    LIMIT 1
                """)
            
            row = cursor.fetchone()
            if not row:
                return None
            
            portfolio_id, cash, portfolio_user_id, pos_count = row
            logger.info(f"Using portfolio {portfolio_id} (user: {portfolio_user_id}, {pos_count} positions, ${cash:.2f} cash)")
            
            # Load positions
            cursor.execute("""
                SELECT ticker, quantity, avg_cost FROM positions
                WHERE portfolio_id = ?
            """, (portfolio_id,))
            
            positions = []
            
            # Load sectors from scores.db if available
            scores_db_path = db_path.parent / "scores.db"
            sector_map = {}
            if scores_db_path.exists():
                try:
                    scores_conn = sqlite3.connect(str(scores_db_path))
                    scores_cursor = scores_conn.cursor()
                    scores_cursor.execute("SELECT ticker, sector FROM composite_scores")
                    sector_map = {row[0]: row[1] for row in scores_cursor.fetchall()}
                    scores_conn.close()
                except Exception as e:
                    logger.debug(f"Could not load sectors: {e}")
            
            for ticker, quantity, avg_cost in cursor.fetchall():
                sector = sector_map.get(ticker, "Unknown")
                
                # Use avg_cost as current price estimate (will be updated with live prices)
                current_price = avg_cost
                market_value = quantity * current_price
                unrealized_pnl = 0  # Would need live price to calculate
                
                positions.append(Position(
                    ticker=ticker,
                    shares=quantity,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=0,
                    sector=sector,
                ))
            
            total_positions = sum(p.market_value for p in positions)
            total_value = cash + total_positions
            
            return PortfolioState(
                cash=cash,
                total_value=total_value,
                positions=positions,
                sector_exposure=self._calculate_sector_exposure(positions, total_value),
                unrealized_pnl=sum(p.unrealized_pnl for p in positions),
                realized_pnl_today=0,
            )
            
        finally:
            conn.close()
    
    async def _load_mock_portfolio(self) -> PortfolioState:
        """Load mock portfolio for development/testing."""
        # Check for cached portfolio
        portfolio_path = self.data_dir / "portfolio_cache.json"
        
        if portfolio_path.exists():
            with open(portfolio_path) as f:
                data = json.load(f)
            
            positions = [
                Position(
                    ticker=p["ticker"],
                    shares=p["shares"],
                    avg_cost=p["avg_cost"],
                    current_price=p.get("current_price", p["avg_cost"]),
                    market_value=p["shares"] * p.get("current_price", p["avg_cost"]),
                    unrealized_pnl=p.get("unrealized_pnl", 0),
                    unrealized_pnl_pct=p.get("unrealized_pnl_pct", 0),
                    sector=p.get("sector", "Unknown"),
                )
                for p in data.get("positions", [])
            ]
            
            total_positions = sum(p.market_value for p in positions)
            cash = data.get("cash", 100000)
            
            return PortfolioState(
                cash=cash,
                total_value=cash + total_positions,
                positions=positions,
                sector_exposure=self._calculate_sector_exposure(positions, cash + total_positions),
                unrealized_pnl=sum(p.unrealized_pnl for p in positions),
                realized_pnl_today=data.get("realized_pnl_today", 0),
            )
        
        # Return empty portfolio
        return PortfolioState(
            cash=100000,
            total_value=100000,
            positions=[],
            sector_exposure={"Cash": 1.0},
            unrealized_pnl=0,
            realized_pnl_today=0,
        )
    
    def _calculate_sector_exposure(
        self, positions: List[Position], total_value: float
    ) -> Dict[str, float]:
        """Calculate sector exposure percentages."""
        if total_value == 0:
            return {}
        
        exposure = {}
        for p in positions:
            sector = p.sector or "Unknown"
            exposure[sector] = exposure.get(sector, 0) + p.market_value / total_value
        
        # Add cash
        cash_pct = 1.0 - sum(exposure.values())
        if cash_pct > 0.01:
            exposure["Cash"] = cash_pct
        
        return {k: round(v, 4) for k, v in exposure.items()}
    
    async def _load_market_state(self) -> MarketState:
        """Load current market state (regime, VIX)."""
        regime = "normal"
        regime_confidence = 0.7
        vix = 15.0
        vix_change = 0.0
        vix_regime = "calm"
        
        # Try to load HMM regime
        try:
            from risk.hmm_regime import get_current_regime
            regime_data = await get_current_regime()
            regime = regime_data.get("regime", "normal")
            regime_confidence = regime_data.get("confidence", 0.7)
        except Exception as e:
            logger.debug(f"HMM regime not available: {e}")
        
        # Try to load VIX
        try:
            from risk.vix_service import get_current_vix
            vix_data = await get_current_vix()
            vix = vix_data.get("vix", 15.0)
            vix_change = vix_data.get("change", 0.0)
            vix_regime = vix_data.get("regime", "calm")
        except Exception as e:
            logger.debug(f"VIX service not available: {e}")
        
        # Determine trend (simplified)
        trend = "sideways"
        if vix < 15:
            trend = "up"
        elif vix > 25:
            trend = "down"
        
        return MarketState(
            regime=regime,
            regime_confidence=regime_confidence,
            vix=vix,
            vix_change=vix_change,
            vix_regime=vix_regime,
            trend=trend,
        )
    
    async def _check_data_freshness(self) -> DataFreshness:
        """Check if data sources are fresh enough for trading."""
        freshness = DataFreshness()
        now = datetime.now()
        stale_reasons = []
        
        # Check scores freshness
        scores_path = self.data_dir / "composite_scores.json"
        if scores_path.exists():
            with open(scores_path) as f:
                data = json.load(f)
            
            updated_str = data.get("updated_at")
            if updated_str:
                updated = datetime.fromisoformat(updated_str)
                freshness.scores_updated = updated
                freshness.scores_age_hours = (now - updated).total_seconds() / 3600
                
                if freshness.scores_age_hours > self.MAX_SCORES_AGE_HOURS:
                    stale_reasons.append(
                        f"Scores are {freshness.scores_age_hours:.1f}h old (max: {self.MAX_SCORES_AGE_HOURS}h)"
                    )
        else:
            stale_reasons.append("Scores file not found")
        
        # Check regime freshness
        regime_path = self.data_dir / "hmm_regime.json"
        if regime_path.exists():
            with open(regime_path) as f:
                data = json.load(f)
            
            updated_str = data.get("updated_at")
            if updated_str:
                updated = datetime.fromisoformat(updated_str)
                freshness.regime_updated = updated
                freshness.regime_age_hours = (now - updated).total_seconds() / 3600
                
                if freshness.regime_age_hours > self.MAX_REGIME_AGE_HOURS:
                    stale_reasons.append(
                        f"Regime is {freshness.regime_age_hours:.1f}h old (max: {self.MAX_REGIME_AGE_HOURS}h)"
                    )
        
        freshness.stale_reasons = stale_reasons
        freshness.is_stale = len(stale_reasons) > 0
        
        return freshness
    
    def _score_to_candidate(self, ticker: str, data: Dict) -> StockCandidate:
        """Convert score data dict to StockCandidate."""
        return StockCandidate(
            ticker=ticker,
            company_name=data.get("company_name", ticker),
            score=data.get("total_score", 0),
            signal=data.get("signal", "HOLD"),
            sector=data.get("sector", "Unknown"),
            rank=data.get("rank", 999),
            fundamental_score=data.get("fundamental_score", 50),
            sentiment_score=data.get("sentiment_score", 50),
            technical_score=data.get("technical_score", 50),
            macro_score=data.get("macro_score", 50),
            score_change=data.get("score_change"),
            insider_score=data.get("insider_score"),
            volatility=data.get("volatility"),
        )
    
    def _parse_ibkr_portfolio(self, portfolio_data: Dict) -> PortfolioState:
        """Parse IBKR portfolio response into PortfolioState."""
        positions = []
        for p in portfolio_data.get("positions", []):
            positions.append(Position(
                ticker=p["ticker"],
                shares=p["shares"],
                avg_cost=p["avg_cost"],
                current_price=p["current_price"],
                market_value=p["market_value"],
                unrealized_pnl=p["unrealized_pnl"],
                unrealized_pnl_pct=p["unrealized_pnl_pct"],
                sector=p.get("sector", "Unknown"),
            ))
        
        total_positions = sum(p.market_value for p in positions)
        cash = portfolio_data.get("cash", 0)
        
        return PortfolioState(
            cash=cash,
            total_value=cash + total_positions,
            positions=positions,
            sector_exposure=self._calculate_sector_exposure(positions, cash + total_positions),
            unrealized_pnl=sum(p.unrealized_pnl for p in positions),
            realized_pnl_today=portfolio_data.get("realized_pnl_today", 0),
        )


# Convenience function
async def aggregate_context(**kwargs) -> TradingContext:
    """Convenience function to aggregate context."""
    aggregator = ContextAggregator()
    return await aggregator.aggregate(**kwargs)


# CLI entry point
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Context Aggregator")
    parser.add_argument("--ticker", "-t", help="Get context for specific ticker")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--top", "-n", type=int, default=10, help="Number of top candidates")
    
    args = parser.parse_args()
    
    async def main():
        aggregator = ContextAggregator()
        
        if args.ticker:
            # Single ticker context
            context = await aggregator.aggregate_for_ticker(args.ticker)
            if args.json:
                print(json.dumps(context, indent=2))
            else:
                print(f"\n=== {args.ticker.upper()} Context ===")
                print(f"Score: {context.get('score', 'N/A')}")
                print(f"Signal: {context.get('signal', 'N/A')}")
                print(f"Sector: {context.get('sector', 'N/A')}")
                print(f"Rank: {context.get('rank', 'N/A')}")
                if context.get('components'):
                    print("\nComponents:")
                    for k, v in context['components'].items():
                        print(f"  {k}: {v}")
        else:
            # Full context
            context = await aggregator.aggregate(top_n_candidates=args.top)
            
            if args.json:
                print(context.to_json())
            else:
                print("\n" + "=" * 60)
                print("TRADING CONTEXT")
                print("=" * 60)
                
                print(f"\n📊 Portfolio:")
                print(f"  Cash: ${context.portfolio.cash:,.0f}")
                print(f"  Total: ${context.portfolio.total_value:,.0f}")
                print(f"  Positions: {context.portfolio.position_count}")
                print(f"  Unrealized P&L: ${context.portfolio.unrealized_pnl:+,.0f}")
                
                print(f"\n📈 Market:")
                print(f"  Regime: {context.market.regime} ({context.market.regime_confidence:.0%})")
                print(f"  VIX: {context.market.vix:.1f} ({context.market.vix_regime})")
                print(f"  Trend: {context.market.trend}")
                
                print(f"\n🟢 BUY Candidates ({len(context.buy_candidates)}):")
                for c in context.buy_candidates[:5]:
                    print(f"  {c.ticker}: {c.score:.1f} ({c.sector})")
                
                if context.sell_candidates:
                    print(f"\n🔴 SELL Candidates ({len(context.sell_candidates)}):")
                    for c in context.sell_candidates:
                        print(f"  {c.ticker}: {c.score:.1f}")
                
                if context.data_freshness.is_stale:
                    print(f"\n⚠️ Data Freshness Issues:")
                    for reason in context.data_freshness.stale_reasons:
                        print(f"  - {reason}")
                else:
                    print(f"\n✅ Data is fresh")
    
    asyncio.run(main())
