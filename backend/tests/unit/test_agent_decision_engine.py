"""
Unit tests for Decision Engine (REC-285)

Tests the Claude-powered decision engine with mocked API responses.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.decision_engine import (
    DecisionEngine, DecisionResult, SYSTEM_PROMPT, 
    DEFAULT_MODEL, make_decisions
)
from agent.context import (
    TradingContext, PortfolioState, MarketState, StockCandidate, 
    DataFreshness, Position
)
from agent.memory import Memory
from agent.position_sizing import TradeDecision


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio state."""
    return PortfolioState(
        cash=50000.0,
        total_value=125000.0,
        positions=[
            Position(
                ticker="AAPL",
                shares=50,
                avg_cost=150.0,
                current_price=175.0,
                market_value=8750.0,
                unrealized_pnl=1250.0,
                unrealized_pnl_pct=16.67,
                sector="Technology",
            ),
            Position(
                ticker="MSFT",
                shares=30,
                avg_cost=300.0,
                current_price=380.0,
                market_value=11400.0,
                unrealized_pnl=2400.0,
                unrealized_pnl_pct=26.67,
                sector="Technology",
            ),
        ],
        sector_exposure={"Technology": 0.16, "Cash": 0.40},
        unrealized_pnl=3650.0,
        realized_pnl_today=0.0,
    )


@pytest.fixture
def mock_market():
    """Create a mock market state."""
    return MarketState(
        regime="normal",
        regime_confidence=0.78,
        vix=15.2,
        vix_change=-0.5,
        vix_regime="calm",
        trend="up",
    )


@pytest.fixture
def mock_buy_candidates():
    """Create mock BUY candidates."""
    return [
        StockCandidate(
            ticker="CMI",
            company_name="Cummins Inc",
            score=89.8,
            signal="BUY",
            sector="Industrials",
            rank=1,
            fundamental_score=92.0,
            sentiment_score=85.0,
            technical_score=88.0,
            macro_score=90.0,
            score_change=5.2,
            volatility=0.22,
        ),
        StockCandidate(
            ticker="UPS",
            company_name="United Parcel Service",
            score=87.8,
            signal="BUY",
            sector="Logistics",
            rank=2,
            fundamental_score=88.0,
            sentiment_score=82.0,
            technical_score=90.0,
            macro_score=88.0,
            score_change=3.1,
            volatility=0.18,
        ),
        StockCandidate(
            ticker="CAT",
            company_name="Caterpillar Inc",
            score=85.5,
            signal="BUY",
            sector="Industrials",
            rank=3,
            fundamental_score=86.0,
            sentiment_score=80.0,
            technical_score=87.0,
            macro_score=85.0,
            score_change=2.0,
            volatility=0.25,
        ),
    ]


@pytest.fixture
def mock_sell_candidates():
    """Create mock SELL candidates."""
    return [
        StockCandidate(
            ticker="XYZ",
            company_name="XYZ Corp",
            score=35.0,
            signal="SELL",
            sector="Consumer",
            rank=850,
            fundamental_score=30.0,
            sentiment_score=40.0,
            technical_score=35.0,
            macro_score=38.0,
            score_change=-15.0,
            volatility=0.35,
        ),
    ]


@pytest.fixture
def mock_data_freshness():
    """Create mock data freshness."""
    return DataFreshness(
        scores_updated=datetime.now(timezone.utc),
        scores_age_hours=2.5,
        regime_updated=datetime.now(timezone.utc),
        regime_age_hours=1.0,
        is_stale=False,
        stale_reasons=[],
    )


@pytest.fixture
def mock_context(mock_portfolio, mock_market, mock_buy_candidates, mock_data_freshness):
    """Create a complete mock trading context."""
    return TradingContext(
        timestamp=datetime.now(timezone.utc),
        portfolio=mock_portfolio,
        market=mock_market,
        buy_candidates=mock_buy_candidates,
        sell_candidates=[],
        hold_review=[],
        data_freshness=mock_data_freshness,
    )


@pytest.fixture
def mock_memories():
    """Create mock memories from past decisions."""
    return [
        Memory(
            ticker="CAT",
            action="BUY",
            score=87.0,
            regime="normal",
            outcome_pct=12.5,
            rationale="Industrial momentum in low vol",
            lesson_learned="Industrial plays work well in calm regimes",
            similarity=0.92,
        ),
        Memory(
            ticker="FDX",
            action="BUY",
            score=85.0,
            regime="normal",
            outcome_pct=-3.2,
            rationale="Logistics momentum",
            lesson_learned="Avoid trading during earnings week",
            similarity=0.85,
        ),
    ]


# ==============================================================================
# Test: Initialization
# ==============================================================================

class TestDecisionEngineInit:
    """Tests for DecisionEngine initialization."""
    
    def test_default_initialization(self):
        """Test default initialization values."""
        engine = DecisionEngine()
        
        assert engine.model == DEFAULT_MODEL
        assert engine.thinking_budget == 2000  # Haiku limit
        assert engine._client is None
    
    def test_custom_model(self):
        """Test initialization with custom model."""
        engine = DecisionEngine(model="claude-sonnet-4-20250514")
        assert engine.model == "claude-sonnet-4-20250514"
    
    def test_custom_thinking_budget(self):
        """Test initialization with custom thinking budget."""
        engine = DecisionEngine(thinking_budget=10000)
        assert engine.thinking_budget == 10000
    
    def test_custom_api_key(self):
        """Test initialization with custom API key."""
        engine = DecisionEngine(api_key="test-key")
        assert engine.api_key == "test-key"


# ==============================================================================
# Test: Prompt Building
# ==============================================================================

class TestPromptBuilding:
    """Tests for prompt building functionality."""
    
    def test_build_prompt_includes_portfolio(self, mock_context):
        """Test that prompt includes portfolio information."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "Current Portfolio" in prompt
        assert "$50,000" in prompt  # Cash
        assert "$125,000" in prompt  # Total value
        assert "Technology" in prompt
    
    def test_build_prompt_includes_market(self, mock_context):
        """Test that prompt includes market state."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "Market State" in prompt
        assert "normal" in prompt  # Regime
        assert "15.2" in prompt  # VIX
        assert "up" in prompt  # Trend
    
    def test_build_prompt_includes_candidates(self, mock_context):
        """Test that prompt includes BUY candidates."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "BUY Candidates" in prompt
        assert "CMI" in prompt
        assert "Industrials" in prompt
        assert "UPS" in prompt
        assert "CAT" in prompt
    
    def test_build_prompt_includes_memories(self, mock_context, mock_memories):
        """Test that prompt includes memories."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        assert "Similar Past Situations" in prompt
        assert "CAT" in prompt
        assert "+12.5%" in prompt
        assert "Industrial plays work well" in prompt
        assert "FDX" in prompt
        assert "-3.2%" in prompt
    
    def test_build_prompt_includes_sell_candidates(self, mock_context, mock_sell_candidates):
        """Test that prompt includes SELL candidates."""
        mock_context.sell_candidates = mock_sell_candidates
        
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "SELL Candidates" in prompt
        assert "XYZ" in prompt
    
    def test_build_prompt_crisis_regime(self, mock_context):
        """Test that prompt shows crisis regime."""
        mock_context.market.regime = "crisis"
        
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "crisis" in prompt


# ==============================================================================
# Test: Response Parsing
# ==============================================================================

class TestResponseParsing:
    """Tests for Claude response parsing."""
    
    def test_parse_valid_json_response(self, mock_context):
        """Test parsing a valid JSON response."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {
                    "ticker": "CMI",
                    "action": "BUY",
                    "rationale": "Strong fundamentals and momentum.",
                    "confidence": 0.85
                }
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "CMI"
        assert decisions[0].action == "BUY"
        assert decisions[0].confidence == 0.85
        assert "Strong fundamentals" in decisions[0].rationale
    
    def test_parse_multiple_decisions(self, mock_context):
        """Test parsing multiple decisions."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "Buy CMI", "confidence": 0.85},
                {"ticker": "UPS", "action": "BUY", "rationale": "Buy UPS", "confidence": 0.75},
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 2
        assert decisions[0].ticker == "CMI"
        assert decisions[1].ticker == "UPS"
    
    def test_parse_empty_array(self, mock_context):
        """Test parsing empty array (no trades)."""
        engine = DecisionEngine()
        
        response = {"content": "[]", "thinking": None, "tokens": 50}
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 0
    
    def test_parse_with_markdown_wrapper(self, mock_context):
        """Test parsing JSON wrapped in markdown code block."""
        engine = DecisionEngine()
        
        response = {
            "content": '''```json
[{"ticker": "CMI", "action": "BUY", "rationale": "Good buy", "confidence": 0.8}]
```''',
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "CMI"
    
    def test_parse_invalid_json_returns_empty(self, mock_context):
        """Test that invalid JSON returns empty list."""
        engine = DecisionEngine()
        
        response = {"content": "This is not valid JSON", "thinking": None, "tokens": 50}
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 0
    
    def test_parse_invalid_action_skipped(self, mock_context):
        """Test that invalid actions are skipped."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI", "action": "HOLD", "rationale": "Invalid action", "confidence": 0.5},
                {"ticker": "UPS", "action": "BUY", "rationale": "Valid", "confidence": 0.8},
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "UPS"
    
    def test_parse_missing_ticker_skipped(self, mock_context):
        """Test that decisions without ticker are skipped."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"action": "BUY", "rationale": "No ticker", "confidence": 0.5},
                {"ticker": "CMI", "action": "BUY", "rationale": "Valid", "confidence": 0.8},
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "CMI"
    
    def test_parse_enriches_from_context(self, mock_context):
        """Test that decisions are enriched with context data."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "Buy it", "confidence": 0.8}
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].score == 89.8  # From context
        assert decisions[0].sector == "Industrials"  # From context
    
    def test_parse_uppercase_ticker(self, mock_context):
        """Test that tickers are uppercased."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "cmi", "action": "buy", "rationale": "Buy", "confidence": 0.8}
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert decisions[0].ticker == "CMI"
        assert decisions[0].action == "BUY"
    
    def test_parse_respects_max_decisions(self, mock_context):
        """Test that max_decisions is respected."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "1", "confidence": 0.8},
                {"ticker": "UPS", "action": "BUY", "rationale": "2", "confidence": 0.8},
                {"ticker": "CAT", "action": "BUY", "rationale": "3", "confidence": 0.8},
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=2)
        
        assert len(decisions) == 2


# ==============================================================================
# Test: Decision Making (with mocked Claude)
# ==============================================================================

class TestDecisionMaking:
    """Tests for the decide() method with mocked Claude responses."""
    
    @pytest.mark.asyncio
    async def test_decide_returns_result(self, mock_context):
        """Test that decide() returns a DecisionResult."""
        engine = DecisionEngine()
        
        # Mock the _call_claude method
        engine._call_claude = AsyncMock(return_value={
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "Strong score", "confidence": 0.85}
            ]),
            "thinking": "Analysis...",
            "tokens": 150,
        })
        
        result = await engine.decide(mock_context, [])
        
        assert isinstance(result, DecisionResult)
        assert len(result.decisions) == 1
        assert result.decisions[0].ticker == "CMI"
        assert result.thinking == "Analysis..."
        assert result.tokens_used == 150
    
    @pytest.mark.asyncio
    async def test_decide_with_memories(self, mock_context, mock_memories):
        """Test that decide() uses memories."""
        engine = DecisionEngine()
        
        engine._call_claude = AsyncMock(return_value={
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "Similar to CAT success", "confidence": 0.85}
            ]),
            "thinking": None,
            "tokens": 100,
        })
        
        result = await engine.decide(mock_context, mock_memories)
        
        assert len(result.decisions) == 1
        
        # Verify _call_claude was called with memories in prompt
        call_args = engine._call_claude.call_args
        prompt = call_args.args[0]
        
        assert "CAT" in prompt
        assert "+12.5%" in prompt
    
    @pytest.mark.asyncio
    async def test_decide_handles_api_error(self, mock_context):
        """Test that decide() handles API errors gracefully."""
        engine = DecisionEngine()
        
        engine._call_claude = AsyncMock(side_effect=Exception("API Error"))
        
        result = await engine.decide(mock_context, [])
        
        # Should return empty decisions on error, not raise
        assert result.decisions == []
        assert "API Error" in result.raw_response
    
    @pytest.mark.asyncio
    async def test_decide_empty_candidates(self, mock_context):
        """Test decide() with no candidates."""
        mock_context.buy_candidates = []
        mock_context.sell_candidates = []
        
        engine = DecisionEngine()
        engine._call_claude = AsyncMock(return_value={
            "content": "[]",
            "thinking": None,
            "tokens": 50,
        })
        
        result = await engine.decide(mock_context, [])
        
        assert result.decisions == []


# ==============================================================================
# Test: System Prompt
# ==============================================================================

class TestSystemPrompt:
    """Tests for the system prompt content."""
    
    def test_system_prompt_has_trading_philosophy(self):
        """Test that system prompt includes trading philosophy."""
        assert "TRADING PHILOSOPHY" in SYSTEM_PROMPT
        assert "3-5 trades per week" in SYSTEM_PROMPT
        assert "risk-aware" in SYSTEM_PROMPT.lower()
    
    def test_system_prompt_has_decision_rules(self):
        """Test that system prompt includes decision rules."""
        assert "DECISION RULES" in SYSTEM_PROMPT
        assert "BUY when" in SYSTEM_PROMPT
        assert "SELL when" in SYSTEM_PROMPT
        assert "score" in SYSTEM_PROMPT.lower()
    
    def test_system_prompt_specifies_json_output(self):
        """Test that system prompt specifies JSON output."""
        assert "JSON" in SYSTEM_PROMPT
        assert "array" in SYSTEM_PROMPT.lower()
    
    def test_system_prompt_mentions_confidence(self):
        """Test that system prompt mentions confidence range."""
        assert "confidence" in SYSTEM_PROMPT.lower()


# ==============================================================================
# Test: DecisionResult Dataclass
# ==============================================================================

class TestDecisionResult:
    """Tests for DecisionResult dataclass."""
    
    def test_decision_result_default_values(self):
        """Test DecisionResult default values."""
        result = DecisionResult(decisions=[])
        
        assert result.decisions == []
        assert result.thinking is None
        assert result.raw_response is None
        assert result.model == DEFAULT_MODEL
        assert result.tokens_used == 0
    
    def test_decision_result_with_values(self):
        """Test DecisionResult with values."""
        decision = TradeDecision(
            ticker="CMI",
            action="BUY",
            score=89.8,
            confidence=0.85,
            sector="Industrials",
            rationale="Test"
        )
        
        result = DecisionResult(
            decisions=[decision],
            thinking="Deep analysis",
            raw_response='[{"ticker": "CMI"}]',
            model="claude-sonnet-4",
            tokens_used=500,
        )
        
        assert len(result.decisions) == 1
        assert result.thinking == "Deep analysis"
        assert result.tokens_used == 500


# ==============================================================================
# Test: Mock Response
# ==============================================================================

class TestMockResponse:
    """Tests for the mock response functionality."""
    
    def test_mock_response_with_candidates(self, mock_context):
        """Test mock response extracts top candidate."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        response = engine._mock_response(prompt)
        
        assert "content" in response
        assert "thinking" in response
        
        # Should have extracted CMI as top candidate
        content = json.loads(response["content"])
        if content:  # May be empty or have a decision
            if len(content) > 0:
                assert content[0]["ticker"] == "CMI"
    
    def test_mock_response_no_candidates(self, mock_context):
        """Test mock response with no candidates."""
        mock_context.buy_candidates = []
        
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        response = engine._mock_response(prompt)
        
        # Should return empty array
        content = json.loads(response["content"])
        assert content == []


# ==============================================================================
# Test: Edge Cases
# ==============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_format_portfolio_no_positions(self, mock_context):
        """Test formatting portfolio with no positions."""
        mock_context.portfolio.positions = []
        mock_context.portfolio.position_count = 0
        
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "Current Portfolio" in prompt
        assert "Positions: 0" in prompt
    
    def test_format_market_high_vix(self, mock_context):
        """Test formatting market with high VIX."""
        mock_context.market.vix = 45.0
        mock_context.market.vix_regime = "panic"
        mock_context.market.regime = "crisis"
        
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        assert "45.0" in prompt
        assert "crisis" in prompt
    
    def test_format_no_memories(self, mock_context):
        """Test formatting with no memories."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, [])
        
        # Should indicate no similar situations
        assert "No similar situations found" in prompt
    
    def test_parse_non_list_json(self, mock_context):
        """Test parsing non-list JSON returns empty."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps({"ticker": "CMI", "action": "BUY"}),  # Object, not array
            "thinking": None,
            "tokens": 50,
        }
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert decisions == []
    
    def test_parse_malformed_decision(self, mock_context):
        """Test parsing decision with missing fields."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI"},  # Missing action
                {"ticker": "UPS", "action": "BUY", "rationale": "OK", "confidence": 0.8}
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        # First one should be skipped, second should work
        assert len(decisions) == 1
        assert decisions[0].ticker == "UPS"
    
    def test_ticker_not_in_candidates(self, mock_context):
        """Test parsing ticker not in candidates uses defaults."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "UNKNOWN", "action": "BUY", "rationale": "Test", "confidence": 0.7}
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].score == 0  # Default score for unknown
        assert decisions[0].sector == "Unknown"  # Default sector


# ==============================================================================
# Test: Convenience Function
# ==============================================================================

class TestConvenienceFunction:
    """Tests for the make_decisions convenience function."""
    
    @pytest.mark.asyncio
    async def test_make_decisions_function(self, mock_context):
        """Test the make_decisions convenience function."""
        with patch.object(DecisionEngine, 'decide') as mock_decide:
            expected_result = DecisionResult(
                decisions=[
                    TradeDecision(
                        ticker="CMI",
                        action="BUY",
                        score=89.8,
                        confidence=0.8,
                        sector="Industrials",
                        rationale="Test"
                    )
                ],
                tokens_used=100,
            )
            mock_decide.return_value = expected_result
            
            result = await make_decisions(mock_context, [])
            
            assert isinstance(result, DecisionResult)
            mock_decide.assert_called_once()


# ==============================================================================
# Test: Integration with TradeDecision Dataclass
# ==============================================================================

class TestTradeDecisionIntegration:
    """Tests for integration with TradeDecision dataclass."""
    
    def test_decision_has_all_fields(self, mock_context):
        """Test that parsed decisions have all required fields."""
        engine = DecisionEngine()
        
        response = {
            "content": json.dumps([
                {"ticker": "CMI", "action": "BUY", "rationale": "Test rationale", "confidence": 0.85}
            ]),
            "thinking": None,
            "tokens": 100,
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        decision = decisions[0]
        
        # Check all TradeDecision fields
        assert hasattr(decision, 'ticker')
        assert hasattr(decision, 'action')
        assert hasattr(decision, 'score')
        assert hasattr(decision, 'confidence')
        assert hasattr(decision, 'sector')
        assert hasattr(decision, 'rationale')
        
        # Verify values
        assert decision.ticker == "CMI"
        assert decision.action == "BUY"
        assert decision.score == 89.8
        assert decision.confidence == 0.85
        assert decision.sector == "Industrials"
        assert decision.rationale == "Test rationale"


# ==============================================================================
# Run tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
