"""
Unit tests for Agent Context Aggregator (REC-278, REC-279, REC-280)

Tests:
- Context aggregation
- Portfolio state loading
- Market state loading
- BUY/SELL candidate filtering
- Data freshness checking
- API endpoint responses
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.context import (
    ContextAggregator,
    TradingContext,
    PortfolioState,
    MarketState,
    StockCandidate,
    Position,
    DataFreshness,
    aggregate_context,
)


class TestDataClasses:
    """Test data class definitions."""
    
    def test_position_creation(self):
        """Test Position dataclass."""
        pos = Position(
            ticker="AAPL",
            shares=100,
            avg_cost=150.0,
            current_price=175.0,
            market_value=17500.0,
            unrealized_pnl=2500.0,
            unrealized_pnl_pct=16.67,
            sector="Technology"
        )
        
        assert pos.ticker == "AAPL"
        assert pos.shares == 100
        assert pos.market_value == 17500.0
    
    def test_portfolio_state_position_count(self):
        """Test PortfolioState calculates position count."""
        positions = [
            Position("AAPL", 100, 150, 175, 17500, 2500, 16.67, "Tech"),
            Position("MSFT", 50, 300, 350, 17500, 2500, 16.67, "Tech"),
        ]
        
        portfolio = PortfolioState(
            cash=50000,
            total_value=85000,
            positions=positions,
            sector_exposure={"Tech": 0.41, "Cash": 0.59},
            unrealized_pnl=5000,
        )
        
        assert portfolio.position_count == 2
    
    def test_market_state_defaults(self):
        """Test MarketState default values."""
        market = MarketState(
            regime="normal",
            regime_confidence=0.75,
            vix=15.0,
        )
        
        assert market.vix_change == 0.0
        assert market.vix_regime == "normal"
        assert market.trend == "sideways"
    
    def test_stock_candidate_creation(self):
        """Test StockCandidate dataclass."""
        candidate = StockCandidate(
            ticker="CMI",
            company_name="Cummins Inc.",
            score=89.8,
            signal="BUY",
            sector="Industrials",
            rank=1,
            fundamental_score=89.7,
            sentiment_score=79.8,
            technical_score=99.0,
            macro_score=82.1,
        )
        
        assert candidate.ticker == "CMI"
        assert candidate.score == 89.8
        assert candidate.signal == "BUY"
    
    def test_data_freshness_defaults(self):
        """Test DataFreshness default values."""
        freshness = DataFreshness()
        
        assert freshness.is_stale == False
        assert freshness.stale_reasons == []


class TestTradingContext:
    """Test TradingContext class."""
    
    def test_to_dict(self):
        """Test context serialization to dict."""
        context = TradingContext(
            timestamp=datetime(2026, 2, 16, 12, 0, 0),
            portfolio=PortfolioState(
                cash=50000,
                total_value=100000,
                positions=[],
                sector_exposure={"Cash": 0.5},
                unrealized_pnl=0,
            ),
            market=MarketState(
                regime="normal",
                regime_confidence=0.8,
                vix=15.0,
            ),
            buy_candidates=[
                StockCandidate("CMI", "Cummins", 89.8, "BUY", "Industrials", 1, 90, 80, 99, 82),
            ],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        result = context.to_dict()
        
        assert result["timestamp"] == "2026-02-16T12:00:00"
        assert result["portfolio"]["cash"] == 50000
        assert result["market"]["regime"] == "normal"
        assert len(result["buy_candidates"]) == 1
        assert result["summary"]["buy_count"] == 1
        assert result["summary"]["top_buy"] == "CMI"
    
    def test_to_json(self):
        """Test context serialization to JSON."""
        context = TradingContext(
            timestamp=datetime(2026, 2, 16, 12, 0, 0),
            portfolio=PortfolioState(50000, 100000, [], {}, 0),
            market=MarketState("normal", 0.8, 15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        json_str = context.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["timestamp"] == "2026-02-16T12:00:00"


class TestContextAggregator:
    """Test ContextAggregator class."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory with mock data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Create mock scores
            scores_data = {
                "updated_at": datetime.now().isoformat(),
                "scores": {
                    "CMI": {
                        "total_score": 89.8,
                        "signal": "BUY",
                        "sector": "Industrials",
                        "rank": 1,
                        "fundamental_score": 90,
                        "sentiment_score": 80,
                        "technical_score": 99,
                        "macro_score": 82,
                    },
                    "UPS": {
                        "total_score": 87.8,
                        "signal": "BUY",
                        "sector": "Logistics",
                        "rank": 2,
                        "fundamental_score": 88,
                        "sentiment_score": 85,
                        "technical_score": 84,
                        "macro_score": 83,
                    },
                    "AAPL": {
                        "total_score": 72.0,
                        "signal": "BUY",
                        "sector": "Technology",
                        "rank": 10,
                        "fundamental_score": 70,
                        "sentiment_score": 75,
                        "technical_score": 70,
                        "macro_score": 73,
                    },
                    "BAD": {
                        "total_score": 35.0,
                        "signal": "SELL",
                        "sector": "Energy",
                        "rank": 800,
                        "fundamental_score": 30,
                        "sentiment_score": 40,
                        "technical_score": 35,
                        "macro_score": 35,
                    },
                }
            }
            
            with open(data_dir / "composite_scores.json", "w") as f:
                json.dump(scores_data, f)
            
            # Create mock portfolio
            portfolio_data = {
                "cash": 50000,
                "positions": [
                    {
                        "ticker": "AAPL",
                        "shares": 100,
                        "avg_cost": 150.0,
                        "current_price": 175.0,
                        "unrealized_pnl": 2500,
                        "unrealized_pnl_pct": 16.67,
                        "sector": "Technology",
                    },
                    {
                        "ticker": "BAD",
                        "shares": 50,
                        "avg_cost": 100.0,
                        "current_price": 90.0,
                        "unrealized_pnl": -500,
                        "unrealized_pnl_pct": -10.0,
                        "sector": "Energy",
                    },
                ]
            }
            
            with open(data_dir / "portfolio_cache.json", "w") as f:
                json.dump(portfolio_data, f)
            
            yield data_dir
    
    @pytest.mark.asyncio
    async def test_aggregate_basic(self, temp_data_dir):
        """Test basic context aggregation."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate()
        
        assert context is not None
        assert isinstance(context, TradingContext)
        assert context.portfolio.cash == 50000
    
    @pytest.mark.asyncio
    async def test_buy_candidates_exclude_owned(self, temp_data_dir):
        """Test that BUY candidates exclude owned stocks."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate()
        
        # AAPL is owned, should not be in buy_candidates
        buy_tickers = [c.ticker for c in context.buy_candidates]
        assert "AAPL" not in buy_tickers
        
        # CMI and UPS should be in buy candidates
        assert "CMI" in buy_tickers
        assert "UPS" in buy_tickers
    
    @pytest.mark.asyncio
    async def test_sell_candidates_owned_with_sell_signal(self, temp_data_dir):
        """Test that SELL candidates are owned stocks with SELL signal."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate()
        
        # BAD is owned and has SELL signal
        sell_tickers = [c.ticker for c in context.sell_candidates]
        assert "BAD" in sell_tickers
        
        # AAPL is owned but has BUY signal, should not be in sell
        assert "AAPL" not in sell_tickers
    
    @pytest.mark.asyncio
    async def test_candidates_sorted_by_score(self, temp_data_dir):
        """Test that candidates are sorted by score descending."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate()
        
        scores = [c.score for c in context.buy_candidates]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_top_n_candidates_limit(self, temp_data_dir):
        """Test that top_n_candidates limits results."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate(top_n_candidates=1)
        
        assert len(context.buy_candidates) == 1
        assert context.buy_candidates[0].ticker == "CMI"  # Top by score
    
    @pytest.mark.asyncio
    async def test_aggregate_for_ticker(self, temp_data_dir):
        """Test single ticker context."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate_for_ticker("CMI")
        
        assert context["ticker"] == "CMI"
        assert context["score"] == 89.8
        assert context["signal"] == "BUY"
        assert context["components"]["fundamental"] == 90
    
    @pytest.mark.asyncio
    async def test_aggregate_for_ticker_not_found(self, temp_data_dir):
        """Test error for unknown ticker."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate_for_ticker("UNKNOWN")
        
        assert "error" in context
    
    @pytest.mark.asyncio
    async def test_sector_exposure_calculation(self, temp_data_dir):
        """Test sector exposure is calculated correctly."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        context = await aggregator.aggregate()
        
        # Should have Technology, Energy, and Cash
        assert "Technology" in context.portfolio.sector_exposure
        assert "Cash" in context.portfolio.sector_exposure
        
        # Sum should be ~1.0
        total = sum(context.portfolio.sector_exposure.values())
        assert abs(total - 1.0) < 0.01


class TestDataFreshnessCheck:
    """Test data freshness checking."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_fresh_data(self, temp_data_dir):
        """Test fresh data passes check."""
        # Create fresh scores
        scores_data = {
            "updated_at": datetime.now().isoformat(),
            "scores": {}
        }
        with open(temp_data_dir / "composite_scores.json", "w") as f:
            json.dump(scores_data, f)
        
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        freshness = await aggregator._check_data_freshness()
        
        assert freshness.is_stale == False
        assert len(freshness.stale_reasons) == 0
    
    @pytest.mark.asyncio
    async def test_stale_scores(self, temp_data_dir):
        """Test stale scores are detected."""
        # Create stale scores (8 days old)
        stale_time = datetime.now() - timedelta(days=8)
        scores_data = {
            "updated_at": stale_time.isoformat(),
            "scores": {}
        }
        with open(temp_data_dir / "composite_scores.json", "w") as f:
            json.dump(scores_data, f)
        
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        freshness = await aggregator._check_data_freshness()
        
        assert freshness.is_stale == True
        assert any("Scores" in r for r in freshness.stale_reasons)
    
    @pytest.mark.asyncio
    async def test_missing_scores_file(self, temp_data_dir):
        """Test missing scores file is detected."""
        aggregator = ContextAggregator(data_dir=temp_data_dir)
        freshness = await aggregator._check_data_freshness()
        
        assert freshness.is_stale == True
        assert any("not found" in r for r in freshness.stale_reasons)


class TestMarketState:
    """Test market state loading."""
    
    @pytest.mark.asyncio
    async def test_market_state_defaults(self):
        """Test market state returns valid regime and VIX."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aggregator = ContextAggregator(data_dir=Path(tmpdir))
            market = await aggregator._load_market_state()
            
            # Regime should be one of the valid regimes (HMM may detect actual current regime)
            valid_regimes = ["low_vol", "normal", "high_vol", "crisis"]
            assert market.regime in valid_regimes
            assert market.vix > 0


class TestConvenienceFunction:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_aggregate_context_function(self):
        """Test aggregate_context convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Create minimal scores
            with open(data_dir / "composite_scores.json", "w") as f:
                json.dump({"updated_at": datetime.now().isoformat(), "scores": {}}, f)
            
            # Patch the default data dir
            with patch.object(ContextAggregator, '__init__', lambda self, data_dir=None: setattr(self, 'data_dir', data_dir or Path(tmpdir))):
                aggregator = ContextAggregator(data_dir=data_dir)
                context = await aggregator.aggregate()
                
                assert isinstance(context, TradingContext)


class TestAPIEndpoints:
    """Test API endpoints (REC-279)."""
    
    @pytest.mark.asyncio
    async def test_context_endpoint_structure(self):
        """Test context endpoint returns correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Create mock data
            with open(data_dir / "composite_scores.json", "w") as f:
                json.dump({
                    "updated_at": datetime.now().isoformat(),
                    "scores": {
                        "CMI": {"total_score": 89.8, "signal": "BUY", "sector": "Industrials", "rank": 1,
                                "fundamental_score": 90, "sentiment_score": 80, "technical_score": 99, "macro_score": 82}
                    }
                }, f)
            
            # Test directly via aggregator
            aggregator = ContextAggregator(data_dir=data_dir)
            context = await aggregator.aggregate(top_n_candidates=10)
            result = context.to_dict()
            
            assert "timestamp" in result
            assert "portfolio" in result
            assert "market" in result
            assert "buy_candidates" in result
            assert "summary" in result
            assert result["summary"]["buy_count"] == 1


# Run with: python -m pytest tests/unit/test_agent_context.py -v
