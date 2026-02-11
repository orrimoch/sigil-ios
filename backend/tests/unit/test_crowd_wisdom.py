"""
Unit tests for Crowd Wisdom module.

REC-251: OpenInsider Data Fetcher
REC-252: Storage Schema
REC-253: Insider Signal Scoring
REC-254: API Endpoints
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
import asyncio

# Import modules under test
from src.crowd_wisdom.insider_fetcher import InsiderFetcher, InsiderTransaction
from src.crowd_wisdom.insider_scorer import InsiderScorer, InsiderScore, calculate_weekly_scores


# ========== Test Data ==========

def create_mock_transaction(
    ticker: str = "AAPL",
    insider_name: str = "Tim Cook",
    insider_title: str = "CEO",
    value: float = 1_000_000,
    quantity: int = 10_000,
    price: float = 100.0
) -> InsiderTransaction:
    """Create a mock InsiderTransaction for testing."""
    return InsiderTransaction(
        filing_date=date.today(),
        trade_date=date.today() - timedelta(days=1),
        ticker=ticker,
        company_name=f"{ticker} Inc",
        insider_name=insider_name,
        insider_title=insider_title,
        trade_type="P",
        price=price,
        quantity=quantity,
        shares_owned=100_000,
        ownership_change_pct=10.0,
        value=value
    )


# ========== InsiderTransaction Tests ==========

class TestInsiderTransaction:
    """Tests for InsiderTransaction dataclass."""
    
    def test_is_executive_ceo(self):
        """CEO should be identified as executive."""
        txn = create_mock_transaction(insider_title="CEO")
        assert txn.is_executive is True
    
    def test_is_executive_cfo(self):
        """CFO should be identified as executive."""
        txn = create_mock_transaction(insider_title="CFO")
        assert txn.is_executive is True
    
    def test_is_executive_president(self):
        """President should be identified as executive."""
        txn = create_mock_transaction(insider_title="Pres, 10%")
        assert txn.is_executive is True
    
    def test_is_not_executive_director(self):
        """Director should not be identified as executive."""
        txn = create_mock_transaction(insider_title="Dir")
        assert txn.is_executive is False
    
    def test_is_director(self):
        """Director should be identified as director."""
        txn = create_mock_transaction(insider_title="Dir")
        assert txn.is_director is True
    
    def test_is_large_owner(self):
        """10% owner should be identified as large owner."""
        txn = create_mock_transaction(insider_title="10%")
        assert txn.is_large_owner is True


# ========== InsiderFetcher Tests ==========

class TestInsiderFetcher:
    """Tests for InsiderFetcher."""
    
    def test_init_default_params(self):
        """Test default initialization."""
        fetcher = InsiderFetcher()
        assert fetcher.max_price == 30.0
        assert fetcher.days_back == 7
    
    def test_init_custom_params(self):
        """Test custom initialization."""
        fetcher = InsiderFetcher(max_price=50.0, days_back=14)
        assert fetcher.max_price == 50.0
        assert fetcher.days_back == 14
    
    def test_parse_date_iso_format(self):
        """Test parsing ISO date format."""
        fetcher = InsiderFetcher()
        result = fetcher._parse_date("2026-02-10")
        assert result == date(2026, 2, 10)
    
    def test_parse_date_invalid(self):
        """Test parsing invalid date."""
        fetcher = InsiderFetcher()
        result = fetcher._parse_date("invalid")
        assert result is None
    
    def test_parse_date_empty(self):
        """Test parsing empty date."""
        fetcher = InsiderFetcher()
        result = fetcher._parse_date("")
        assert result is None
    
    def test_tech_filter_keywords(self):
        """Test tech sector filter using keywords."""
        fetcher = InsiderFetcher()
        
        transactions = [
            create_mock_transaction(ticker="SOFT", insider_name="A"),
            create_mock_transaction(ticker="BANK", insider_name="B"),
            create_mock_transaction(ticker="TECH", insider_name="C"),
        ]
        
        # Modify company names
        transactions[0] = InsiderTransaction(
            **{**transactions[0].__dict__, 'company_name': 'Software Solutions Inc'}
        )
        transactions[1] = InsiderTransaction(
            **{**transactions[1].__dict__, 'company_name': 'Bank of America'}
        )
        transactions[2] = InsiderTransaction(
            **{**transactions[2].__dict__, 'company_name': 'Tech Platform Corp'}
        )
        
        filtered = fetcher._filter_tech_sector(transactions)
        
        # Should include software and tech, exclude bank
        tickers = [t.ticker for t in filtered]
        assert "SOFT" in tickers
        assert "TECH" in tickers
        assert "BANK" not in tickers
    
    def test_cluster_detection_single_insider(self):
        """Single insider should not create cluster."""
        fetcher = InsiderFetcher()
        transactions = [
            create_mock_transaction(ticker="AAPL", insider_name="Tim Cook")
        ]
        
        clusters = fetcher.get_cluster_buys(transactions, min_insiders=3)
        assert len(clusters) == 0
    
    def test_cluster_detection_multiple_insiders(self):
        """Multiple insiders should create cluster."""
        fetcher = InsiderFetcher()
        transactions = [
            create_mock_transaction(ticker="AAPL", insider_name="Tim Cook"),
            create_mock_transaction(ticker="AAPL", insider_name="Jeff Williams"),
            create_mock_transaction(ticker="AAPL", insider_name="Luca Maestri"),
        ]
        
        clusters = fetcher.get_cluster_buys(transactions, min_insiders=3)
        assert "AAPL" in clusters
        assert len(clusters["AAPL"]) == 3


# ========== InsiderScorer Tests ==========

class TestInsiderScorer:
    """Tests for InsiderScorer."""
    
    def test_score_empty_list(self):
        """Empty transaction list should return empty scores."""
        scorer = InsiderScorer()
        scores = scorer.score_transactions([])
        assert len(scores) == 0
    
    def test_score_single_transaction(self):
        """Single transaction should produce score."""
        scorer = InsiderScorer()
        transactions = [create_mock_transaction(value=500_000)]
        
        scores = scorer.score_transactions(transactions)
        
        assert len(scores) == 1
        assert scores[0].ticker == "AAPL"
        assert scores[0].insider_score > 0
    
    def test_score_executive_bonus(self):
        """Executive buy should get bonus points."""
        scorer = InsiderScorer()
        
        # Executive buy
        exec_txn = create_mock_transaction(
            ticker="EXEC",
            insider_title="CEO",
            value=100_000
        )
        
        # Non-executive buy
        other_txn = create_mock_transaction(
            ticker="OTHER",
            insider_title="10%",
            value=100_000
        )
        
        scores = scorer.score_transactions([exec_txn, other_txn])
        
        exec_score = next(s for s in scores if s.ticker == "EXEC")
        other_score = next(s for s in scores if s.ticker == "OTHER")
        
        # Executive should have higher score
        assert exec_score.insider_score > other_score.insider_score
    
    def test_score_cluster_bonus(self):
        """Cluster buying should get bonus points."""
        scorer = InsiderScorer()
        
        # Cluster (3+ insiders)
        cluster_txns = [
            create_mock_transaction(ticker="CLUST", insider_name=f"Insider {i}", value=100_000)
            for i in range(3)
        ]
        
        # Single insider
        single_txn = [create_mock_transaction(ticker="SINGLE", value=300_000)]
        
        scores = scorer.score_transactions(cluster_txns + single_txn)
        
        cluster_score = next(s for s in scores if s.ticker == "CLUST")
        single_score = next(s for s in scores if s.ticker == "SINGLE")
        
        # Cluster should have higher score due to bonus
        assert cluster_score.insider_cluster is True
        assert single_score.insider_cluster is False
    
    def test_score_value_tiers(self):
        """Higher value buys should score higher."""
        scorer = InsiderScorer()
        
        # Large buy
        large_txn = create_mock_transaction(ticker="LARGE", value=10_000_000)
        
        # Small buy
        small_txn = create_mock_transaction(ticker="SMALL", value=10_000)
        
        scores = scorer.score_transactions([large_txn, small_txn])
        
        large_score = next(s for s in scores if s.ticker == "LARGE")
        small_score = next(s for s in scores if s.ticker == "SMALL")
        
        assert large_score.insider_score > small_score.insider_score
    
    def test_signal_strong_buy(self):
        """High score should produce STRONG_BUY signal."""
        scorer = InsiderScorer()
        
        # Create high-scoring transaction
        txns = [
            create_mock_transaction(
                ticker="HIGH",
                insider_title="CEO",
                value=10_000_000,
                insider_name=f"Exec {i}"
            )
            for i in range(3)
        ]
        
        scores = scorer.score_transactions(txns)
        
        assert scores[0].signal == "STRONG_BUY"
        assert scores[0].insider_score >= 70
    
    def test_signal_neutral(self):
        """Low score should produce NEUTRAL signal."""
        scorer = InsiderScorer()
        
        # Create low-scoring transaction
        txn = create_mock_transaction(
            ticker="LOW",
            insider_title="10%",
            value=5_000
        )
        
        scores = scorer.score_transactions([txn])
        
        assert scores[0].signal == "NEUTRAL"
        assert scores[0].insider_score < 50
    
    def test_notable_events_generated(self):
        """Notable events should be generated."""
        scorer = InsiderScorer()
        
        txn = create_mock_transaction(
            ticker="TEST",
            insider_title="CEO",
            insider_name="John Doe",
            value=1_000_000
        )
        
        scores = scorer.score_transactions([txn])
        
        assert len(scores[0].notable_events) > 0
        assert any("CEO" in e or "John Doe" in e for e in scores[0].notable_events)
    
    def test_get_top_picks(self):
        """get_top_picks should return top N stocks."""
        scorer = InsiderScorer()
        
        txns = [
            create_mock_transaction(ticker=f"STOCK{i}", value=(i+1) * 100_000)
            for i in range(10)
        ]
        
        scores = scorer.score_transactions(txns)
        top_5 = scorer.get_top_picks(scores, n=5)
        
        assert len(top_5) == 5
        # Should be sorted by score descending
        for i in range(len(top_5) - 1):
            assert top_5[i].insider_score >= top_5[i+1].insider_score
    
    def test_calculate_weekly_scores_helper(self):
        """Test calculate_weekly_scores convenience function."""
        txns = [
            create_mock_transaction(ticker="AAPL", value=500_000),
            create_mock_transaction(ticker="MSFT", value=300_000),
        ]
        
        scores = calculate_weekly_scores(txns)
        
        assert len(scores) == 2
        assert all(isinstance(s, dict) for s in scores)
        assert all('ticker' in s for s in scores)
        assert all('insider_score' in s for s in scores)


# ========== Integration Tests ==========

class TestIntegration:
    """Integration tests for full pipeline."""
    
    def test_fetcher_to_scorer_pipeline(self):
        """Test fetcher output can be scored."""
        # Create mock transactions
        transactions = [
            create_mock_transaction(ticker="TECH", value=1_000_000),
            create_mock_transaction(ticker="SOFT", value=500_000),
        ]
        
        # Score them
        scorer = InsiderScorer()
        scores = scorer.score_transactions(transactions)
        
        assert len(scores) == 2
        assert all(s.insider_score > 0 for s in scores)


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
