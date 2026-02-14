"""
Unit Tests for Sector Performance Analysis (REC-271)

Tests sector classification, score aggregation, imputation, and visualization.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from analytics.sector_analysis import (
    SectorClassification,
    SectorScore,
    SectorTimeSeries,
    SectorAnalyzer,
    get_sector_scores,
    get_sector_trends,
)
from analytics.imputation import (
    impute_missing_scores,
    ImputationStats,
    calculate_imputation_confidence,
    get_imputation_warning,
)


# Test fixtures
@pytest.fixture
def sample_stock_universe():
    """Sample stock universe data."""
    return {
        "updated_at": "2026-02-14T10:00:00",
        "count": 6,
        "stocks": [
            {"ticker": "NVDA", "name": "NVIDIA", "sector": "Technology", "industry": "Semiconductors", "market_cap": 4500000000000},
            {"ticker": "AAPL", "name": "Apple", "sector": "Technology", "industry": "Consumer Electronics", "market_cap": 3000000000000},
            {"ticker": "AMD", "name": "AMD", "sector": "Technology", "industry": "Semiconductors", "market_cap": 300000000000},
            {"ticker": "JPM", "name": "JPMorgan", "sector": "Financial Services", "industry": "Banks - Diversified", "market_cap": 600000000000},
            {"ticker": "BAC", "name": "Bank of America", "sector": "Financial Services", "industry": "Banks - Diversified", "market_cap": 300000000000},
            {"ticker": "XOM", "name": "Exxon", "sector": "Energy", "industry": "Oil & Gas Integrated", "market_cap": 500000000000},
        ]
    }


@pytest.fixture
def sample_score_history():
    """Sample score history data."""
    return {
        "NVDA": [
            {"date": "2026-02-14", "total_score": 80.0, "signal": "BUY", "fundamental_score": 75, "sentiment_score": 85, "technical_score": 80, "macro_score": 75},
            {"date": "2026-02-13", "total_score": 78.0, "signal": "BUY", "fundamental_score": 74, "sentiment_score": 82, "technical_score": 78, "macro_score": 74},
        ],
        "AAPL": [
            {"date": "2026-02-14", "total_score": 65.0, "signal": "HOLD", "fundamental_score": 70, "sentiment_score": 60, "technical_score": 65, "macro_score": 65},
            {"date": "2026-02-13", "total_score": 63.0, "signal": "HOLD", "fundamental_score": 68, "sentiment_score": 58, "technical_score": 63, "macro_score": 63},
        ],
        "AMD": [
            {"date": "2026-02-14", "total_score": 72.0, "signal": "BUY", "fundamental_score": 70, "sentiment_score": 75, "technical_score": 72, "macro_score": 70},
        ],
        "JPM": [
            {"date": "2026-02-14", "total_score": 55.0, "signal": "HOLD", "fundamental_score": 60, "sentiment_score": 50, "technical_score": 55, "macro_score": 55},
        ],
        "BAC": [
            {"date": "2026-02-14", "total_score": 48.0, "signal": "HOLD", "fundamental_score": 50, "sentiment_score": 45, "technical_score": 48, "macro_score": 48},
        ],
        "XOM": [
            {"date": "2026-02-14", "total_score": 35.0, "signal": "SELL", "fundamental_score": 40, "sentiment_score": 30, "technical_score": 35, "macro_score": 35},
        ],
    }


@pytest.fixture
def analyzer_with_data(sample_stock_universe, sample_score_history, tmp_path):
    """Create analyzer with mocked data files."""
    # Write temp files
    stock_file = tmp_path / "stock_universe.json"
    score_file = tmp_path / "score_history.json"
    
    with open(stock_file, "w") as f:
        json.dump(sample_stock_universe, f)
    with open(score_file, "w") as f:
        json.dump(sample_score_history, f)
    
    # Patch the data paths
    with patch("analytics.sector_analysis.STOCK_UNIVERSE_FILE", stock_file):
        with patch("analytics.sector_analysis.SCORE_HISTORY_FILE", score_file):
            analyzer = SectorAnalyzer()
            analyzer.load_data()
            yield analyzer


class TestSectorClassification:
    """Tests for SectorClassification dataclass."""
    
    def test_full_path(self):
        """Test full_path property."""
        classification = SectorClassification(
            ticker="NVDA",
            name="NVIDIA",
            sector="Technology",
            industry="Semiconductors",
            market_cap=4500000000000
        )
        assert classification.full_path == "Technology/Semiconductors"
    
    def test_sector_classification_fields(self):
        """Test all fields are set correctly."""
        classification = SectorClassification(
            ticker="AAPL",
            name="Apple Inc",
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=3000000000000
        )
        assert classification.ticker == "AAPL"
        assert classification.name == "Apple Inc"
        assert classification.sector == "Technology"
        assert classification.industry == "Consumer Electronics"
        assert classification.market_cap == 3000000000000


class TestSectorAnalyzer:
    """Tests for SectorAnalyzer class."""
    
    def test_load_data(self, analyzer_with_data):
        """Test data loading."""
        assert len(analyzer_with_data._stocks) == 6
        assert "NVDA" in analyzer_with_data._stocks
        assert "Technology" in analyzer_with_data._sector_index
    
    def test_sectors_property(self, analyzer_with_data):
        """Test sectors property returns sorted list."""
        sectors = analyzer_with_data.sectors
        assert "Technology" in sectors
        assert "Financial Services" in sectors
        assert "Energy" in sectors
        assert sectors == sorted(sectors)
    
    def test_industries_property(self, analyzer_with_data):
        """Test industries property."""
        industries = analyzer_with_data.industries
        assert "Semiconductors" in industries
        assert "Banks - Diversified" in industries
    
    def test_get_sector_industries(self, analyzer_with_data):
        """Test getting industries for a sector."""
        tech_industries = analyzer_with_data.get_sector_industries("Technology")
        assert "Semiconductors" in tech_industries
        assert "Consumer Electronics" in tech_industries
    
    def test_get_stocks_in_sector(self, analyzer_with_data):
        """Test filtering stocks by sector."""
        tech_stocks = analyzer_with_data.get_stocks_in_sector(sector="Technology")
        assert len(tech_stocks) == 3
        tickers = [s.ticker for s in tech_stocks]
        assert "NVDA" in tickers
        assert "AAPL" in tickers
        assert "AMD" in tickers
    
    def test_get_stocks_in_sector_with_top_n(self, analyzer_with_data):
        """Test top N filtering by market cap."""
        tech_stocks = analyzer_with_data.get_stocks_in_sector(sector="Technology", top_n=2)
        assert len(tech_stocks) == 2
        # Should be NVDA and AAPL (highest market cap)
        tickers = [s.ticker for s in tech_stocks]
        assert "NVDA" in tickers
        assert "AAPL" in tickers
    
    def test_get_stocks_by_industry(self, analyzer_with_data):
        """Test filtering by industry."""
        semis = analyzer_with_data.get_stocks_in_sector(industry="Semiconductors")
        assert len(semis) == 2
        tickers = [s.ticker for s in semis]
        assert "NVDA" in tickers
        assert "AMD" in tickers
    
    def test_calculate_sector_score(self, analyzer_with_data):
        """Test sector score calculation."""
        score = analyzer_with_data.calculate_sector_score(
            date="2026-02-14",
            sector="Technology"
        )
        
        assert score.sector == "Technology"
        assert score.date == "2026-02-14"
        assert score.stock_count == 3
        
        # Mean of NVDA(80), AAPL(65), AMD(72) = 72.33
        assert 72 <= score.mean_score <= 73
        
        # 2 BUY (NVDA, AMD), 1 HOLD (AAPL)
        assert score.pct_buy > 60  # ~66.7%
        assert score.pct_hold > 30  # ~33.3%
        assert score.pct_sell == 0
    
    def test_calculate_sector_score_missing_data(self, analyzer_with_data):
        """Test imputation of missing scores."""
        # AMD only has 2026-02-14, not 2026-02-13
        score = analyzer_with_data.calculate_sector_score(
            date="2026-02-13",
            sector="Technology"
        )
        
        # Only NVDA and AAPL have scores for this date
        # AMD should be imputed
        assert score.missing_count == 1
        assert score.stock_count == 3
    
    def test_get_available_dates(self, analyzer_with_data):
        """Test getting available dates."""
        dates = analyzer_with_data.get_available_dates()
        assert "2026-02-14" in dates
        assert "2026-02-13" in dates
    
    def test_get_available_dates_filtered(self, analyzer_with_data):
        """Test date range filtering."""
        dates = analyzer_with_data.get_available_dates(
            start_date="2026-02-14",
            end_date="2026-02-14"
        )
        assert dates == ["2026-02-14"]


class TestImputation:
    """Tests for imputation module."""
    
    def test_impute_missing_scores(self):
        """Test basic imputation."""
        scores = {
            "NVDA": 80.0,
            "AMD": 75.0,
            "INTC": None,  # Missing
        }
        sector_mapping = {
            "NVDA": "Technology",
            "AMD": "Technology",
            "INTC": "Technology",
        }
        
        imputed, stats = impute_missing_scores(scores, sector_mapping)
        
        # INTC should be imputed with sector average (77.5)
        assert imputed["INTC"] == 77.5
        assert stats.missing_count == 1
        assert stats.imputed_count == 1
        assert stats.total_stocks == 3
    
    def test_impute_different_sectors(self):
        """Test imputation uses sector-specific averages."""
        scores = {
            "NVDA": 80.0,
            "AMD": 70.0,
            "JPM": 50.0,
            "BAC": None,  # Missing
        }
        sector_mapping = {
            "NVDA": "Technology",
            "AMD": "Technology",
            "JPM": "Financial Services",
            "BAC": "Financial Services",
        }
        
        imputed, stats = impute_missing_scores(scores, sector_mapping)
        
        # BAC should use Financial Services average (50.0), not Tech average (75.0)
        assert imputed["BAC"] == 50.0
        assert stats.sector_averages["Technology"] == 75.0
        assert stats.sector_averages["Financial Services"] == 50.0
    
    def test_calculate_imputation_confidence(self):
        """Test confidence level calculation."""
        assert calculate_imputation_confidence(2) == "HIGH"
        assert calculate_imputation_confidence(10) == "MEDIUM"
        assert calculate_imputation_confidence(25) == "LOW"
        assert calculate_imputation_confidence(50) == "VERY LOW"
    
    def test_get_imputation_warning(self):
        """Test warning message generation."""
        assert get_imputation_warning(5) is None
        assert "⚠️" in get_imputation_warning(20)
        assert "WARNING" in get_imputation_warning(50)


class TestSectorScore:
    """Tests for SectorScore dataclass."""
    
    def test_sector_score_creation(self):
        """Test SectorScore creation."""
        score = SectorScore(
            date="2026-02-14",
            sector="Technology",
            industry=None,
            mean_score=72.5,
            median_score=73.0,
            std_score=5.5,
            min_score=65.0,
            max_score=80.0,
            pct_buy=66.7,
            pct_hold=33.3,
            pct_sell=0.0,
            stock_count=3,
            missing_count=0
        )
        
        assert score.sector == "Technology"
        assert score.mean_score == 72.5
        assert score.pct_buy == 66.7


class TestSectorTimeSeries:
    """Tests for SectorTimeSeries dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dict."""
        scores = [
            SectorScore(
                date="2026-02-14",
                sector="Technology",
                industry=None,
                mean_score=72.5,
                median_score=73.0,
                std_score=5.5,
                min_score=65.0,
                max_score=80.0,
                pct_buy=66.7,
                pct_hold=33.3,
                pct_sell=0.0,
                stock_count=3,
                missing_count=0
            )
        ]
        
        series = SectorTimeSeries(
            sector="Technology",
            industry=None,
            start_date="2026-02-13",
            end_date="2026-02-14",
            scores=scores
        )
        
        data = series.to_dict()
        assert data["sector"] == "Technology"
        assert len(data["scores"]) == 1
        assert data["scores"][0]["mean_score"] == 72.5


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_get_sector_scores(self, analyzer_with_data, tmp_path):
        """Test get_sector_scores convenience function."""
        # Patch the data paths for the function
        from analytics import sector_analysis
        
        stock_file = tmp_path / "stock_universe.json"
        score_file = tmp_path / "score_history.json"
        
        # Get data from analyzer
        stock_data = {
            "stocks": [
                {"ticker": s.ticker, "name": s.name, "sector": s.sector, 
                 "industry": s.industry, "market_cap": s.market_cap}
                for s in analyzer_with_data._stocks.values()
            ]
        }
        
        with open(stock_file, "w") as f:
            json.dump(stock_data, f)
        with open(score_file, "w") as f:
            json.dump(analyzer_with_data._score_history, f)
        
        with patch.object(sector_analysis, "STOCK_UNIVERSE_FILE", stock_file):
            with patch.object(sector_analysis, "SCORE_HISTORY_FILE", score_file):
                score = get_sector_scores(
                    date="2026-02-14",
                    sector="Technology"
                )
                
                assert score.sector == "Technology"
                assert score.stock_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
