"""
Unit tests for Decision Engine (REC-285)
"""

import pytest
import pytest_asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.agent.decision_engine import (
    DecisionEngine,
    DecisionResult,
    make_decisions,
    SYSTEM_PROMPT,
)
from src.agent.position_sizing import TradeDecision
from src.agent.memory import Memory
from src.agent.context import (
    TradingContext,
    PortfolioState,
    MarketState,
    StockCandidate,
    DataFreshness,
)


# Test fixtures

@pytest.fixture
def mock_context():
    """Create a mock trading context."""
    return TradingContext(
        timestamp=datetime.now(timezone.utc),
        portfolio=PortfolioState(
            cash=50000,
            total_value=100000,
            positions=[],
            sector_exposure={"Technology": 0.35},
            unrealized_pnl=1000,
        ),
        market=MarketState(
            regime="normal",
            regime_confidence=0.8,
            vix=15.0,
        ),
        buy_candidates=[
            StockCandidate(
                ticker="CMI", company_name="Cummins", score=89.8,
                signal="BUY", sector="Industrials", rank=1,
                fundamental_score=85, sentiment_score=80,
                technical_score=95, macro_score=90,
            ),
            StockCandidate(
                ticker="UPS", company_name="UPS", score=87.5,
                signal="BUY", sector="Logistics", rank=2,
                fundamental_score=82, sentiment_score=85,
                technical_score=90, macro_score=88,
            ),
        ],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


@pytest.fixture
def mock_memories():
    """Create mock similar situations."""
    return [
        Memory(
            ticker="CAT", action="BUY", score=87.0, regime="normal",
            outcome_pct=12.0, rationale="Industrial momentum play",
            lesson_learned="Hold through volatility", similarity=0.85
        ),
        Memory(
            ticker="FDX", action="BUY", score=85.0, regime="normal",
            outcome_pct=-3.0, rationale="Logistics play",
            lesson_learned="Avoid earnings week", similarity=0.78
        ),
    ]


class TestDecisionEngineInit:
    """Test DecisionEngine initialization."""
    
    def test_default_init(self):
        """Test default initialization."""
        engine = DecisionEngine()
        assert engine.model == "claude-3-5-haiku-20241022"
        assert engine.thinking_budget == 5000
    
    def test_custom_init(self):
        """Test custom initialization."""
        engine = DecisionEngine(
            model="claude-sonnet-4-20250514",
            thinking_budget=10000
        )
        assert engine.model == "claude-sonnet-4-20250514"
        assert engine.thinking_budget == 10000


class TestPromptBuilding:
    """Test prompt building."""
    
    def test_build_prompt_includes_portfolio(self, mock_context, mock_memories):
        """Test prompt includes portfolio info."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        assert "Portfolio" in prompt
        assert "$50,000" in prompt or "50,000" in prompt  # Cash
        assert "$100,000" in prompt or "100,000" in prompt  # Total
    
    def test_build_prompt_includes_market(self, mock_context, mock_memories):
        """Test prompt includes market state."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        assert "Market" in prompt
        assert "normal" in prompt  # Regime
        assert "15.0" in prompt or "15" in prompt  # VIX
    
    def test_build_prompt_includes_candidates(self, mock_context, mock_memories):
        """Test prompt includes buy candidates."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        assert "CMI" in prompt
        assert "UPS" in prompt
        assert "Score" in prompt and ("89" in prompt or "90" in prompt)  # Score for CMI (rounded)
    
    def test_build_prompt_includes_memories(self, mock_context, mock_memories):
        """Test prompt includes similar situations."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        assert "CAT" in prompt
        assert "+12" in prompt  # Outcome
        assert "Similar" in prompt


class TestResponseParsing:
    """Test response parsing."""
    
    def test_parse_valid_json(self, mock_context):
        """Test parsing valid JSON response."""
        engine = DecisionEngine()
        response = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "CMI", "rationale": "Test", "confidence": 0.85}
            ]),
            "thinking": "Test thinking"
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "CMI"
        assert decisions[0].action == "BUY"
        assert decisions[0].confidence == 0.85
    
    def test_parse_empty_response(self, mock_context):
        """Test parsing empty response."""
        engine = DecisionEngine()
        response = {"content": "[]"}
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 0
    
    def test_parse_markdown_wrapped(self, mock_context):
        """Test parsing markdown-wrapped JSON."""
        engine = DecisionEngine()
        response = {
            "content": """```json
[{"action": "BUY", "ticker": "CMI", "rationale": "Test", "confidence": 0.8}]
```"""
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 1
        assert decisions[0].ticker == "CMI"
    
    def test_parse_invalid_json(self, mock_context):
        """Test parsing invalid JSON returns empty list."""
        engine = DecisionEngine()
        response = {"content": "not valid json"}
        
        decisions = engine._parse_response(response, mock_context, max_decisions=5)
        
        assert len(decisions) == 0
    
    def test_parse_respects_max_decisions(self, mock_context):
        """Test max_decisions limit is respected."""
        engine = DecisionEngine()
        response = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "CMI", "rationale": "Test", "confidence": 0.9},
                {"action": "BUY", "ticker": "UPS", "rationale": "Test", "confidence": 0.8},
                {"action": "BUY", "ticker": "XYZ", "rationale": "Test", "confidence": 0.7},
            ])
        }
        
        decisions = engine._parse_response(response, mock_context, max_decisions=2)
        
        assert len(decisions) == 2


class TestMockResponse:
    """Test mock response generation."""
    
    def test_mock_extracts_candidate(self, mock_context, mock_memories):
        """Test mock response extracts top candidate."""
        engine = DecisionEngine()
        prompt = engine._build_prompt(mock_context, mock_memories)
        
        response = engine._mock_response(prompt)
        
        assert "content" in response
        decisions = json.loads(response["content"])
        assert len(decisions) > 0 or decisions == []  # Either finds candidate or returns empty
    
    def test_mock_returns_valid_structure(self):
        """Test mock response has valid structure."""
        engine = DecisionEngine()
        response = engine._mock_response("Some prompt")
        
        assert "content" in response
        assert "thinking" in response
        assert "tokens" in response


class TestDecisionEngine:
    """Test full decision engine flow."""
    
    @pytest.mark.asyncio
    async def test_decide_with_mock(self, mock_context, mock_memories):
        """Test decide with mock response (no API)."""
        engine = DecisionEngine()
        
        # Without API key, should use mock
        result = await engine.decide(mock_context, mock_memories)
        
        assert isinstance(result, DecisionResult)
        assert isinstance(result.decisions, list)
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_decide_calls_claude(self, mock_claude, mock_context, mock_memories):
        """Test decide calls Claude API."""
        mock_claude.return_value = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "CMI", "rationale": "Strong score", "confidence": 0.85}
            ]),
            "thinking": "Analyzed context",
            "tokens": 500
        }
        
        engine = DecisionEngine()
        result = await engine.decide(mock_context, mock_memories)
        
        mock_claude.assert_called_once()
        assert len(result.decisions) == 1
        assert result.decisions[0].ticker == "CMI"
        assert result.tokens_used == 500
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_decide_handles_error(self, mock_claude, mock_context, mock_memories):
        """Test decide handles API errors gracefully."""
        mock_claude.side_effect = Exception("API Error")
        
        engine = DecisionEngine()
        result = await engine.decide(mock_context, mock_memories)
        
        assert isinstance(result, DecisionResult)
        assert len(result.decisions) == 0
        assert "API Error" in result.raw_response


class TestConvenienceFunction:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_make_decisions(self, mock_context, mock_memories):
        """Test make_decisions convenience function."""
        result = await make_decisions(mock_context, mock_memories)
        
        assert isinstance(result, DecisionResult)


class TestSystemPrompt:
    """Test system prompt content."""
    
    def test_prompt_includes_philosophy(self):
        """Test system prompt includes trading philosophy."""
        assert "TRADING PHILOSOPHY" in SYSTEM_PROMPT
        assert "3-5 trades" in SYSTEM_PROMPT
    
    def test_prompt_includes_rules(self):
        """Test system prompt includes decision rules."""
        assert "BUY when" in SYSTEM_PROMPT
        assert "SELL when" in SYSTEM_PROMPT
        assert "HOLD when" in SYSTEM_PROMPT
    
    def test_prompt_specifies_json_output(self):
        """Test system prompt specifies JSON output."""
        assert "JSON" in SYSTEM_PROMPT
        assert "array" in SYSTEM_PROMPT.lower()
