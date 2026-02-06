"""
Unit tests for F12.10 Report Generator

Tests:
1. HTML generation
2. All sections render
3. Minimal data handling
4. Full data handling
5. Chart generation
6. Trade analysis
7. Config options
8. PDF generation (mocked)
9. Error handling
10. Missing data graceful handling
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.report_generator import (
    ReportGenerator,
    ReportConfig,
    ReportData,
    ChartGenerator,
    generate_report,
    SIGIL_CSS,
)
from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    BacktestResult,
    BacktestStatus,
    BacktestTrade,
    EquityPoint,
)
from backtest.metrics import PerformanceMetrics, ScoreValidationMetrics


@pytest.fixture
def temp_store():
    """Create a temporary data store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        yield store


@pytest.fixture
def sample_equity_curve():
    """Generate a sample equity curve."""
    dates = [f"2025-01-{d:02d}" for d in range(1, 31)]
    nav = 100000
    curve = []
    for i, date in enumerate(dates):
        nav *= 1.002 + (0.001 * (i % 3 - 1))  # Small fluctuation
        peak = max(nav, 100000 if not curve else max(ep.nav for ep in curve))
        curve.append(EquityPoint(
            date=date,
            nav=nav,
            cash=nav * 0.1,
            positions_value=nav * 0.9,
            daily_return=0.002,
            cumulative_return=(nav / 100000) - 1,
            drawdown=(nav - peak) / peak if nav < peak else 0,
        ))
    return curve


@pytest.fixture
def sample_trades():
    """Generate sample trades."""
    return [
        BacktestTrade(
            trade_id="t1",
            backtest_id="bt_test",
            date="2025-01-02",
            ticker="AAPL",
            side="buy",
            quantity=100,
            price=150.00,
            value=15000,
            score_at_trade=75.0,
            signal_at_trade="BUY",
            commission=15.0,
        ),
        BacktestTrade(
            trade_id="t2",
            backtest_id="bt_test",
            date="2025-01-15",
            ticker="AAPL",
            side="sell",
            quantity=100,
            price=160.00,
            value=16000,
            score_at_trade=45.0,
            signal_at_trade="SELL",
            commission=16.0,
        ),
        BacktestTrade(
            trade_id="t3",
            backtest_id="bt_test",
            date="2025-01-05",
            ticker="MSFT",
            side="buy",
            quantity=50,
            price=400.00,
            value=20000,
            score_at_trade=72.0,
            signal_at_trade="BUY",
            commission=20.0,
        ),
        BacktestTrade(
            trade_id="t4",
            backtest_id="bt_test",
            date="2025-01-20",
            ticker="MSFT",
            side="sell",
            quantity=50,
            price=380.00,
            value=19000,
            score_at_trade=48.0,
            signal_at_trade="SELL",
            commission=19.0,
        ),
    ]


@pytest.fixture
def sample_backtest_result(sample_equity_curve):
    """Create a sample backtest result."""
    return BacktestResult(
        backtest_id="bt_test_20250206_123456_abc123",
        status=BacktestStatus.COMPLETED,
        parameters=BacktestParameters(
            start_date="2025-01-01",
            end_date="2025-01-31",
            initial_capital=100000,
            entry_threshold=70,
            exit_threshold=50,
            max_positions=10,
            rebalance_freq="weekly",
        ),
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        total_return=0.05,
        cagr=0.60,
        volatility=0.15,
        sharpe_ratio=1.5,
        max_drawdown=-0.08,
        win_rate=0.55,
        total_trades=4,
        benchmark_return=0.03,
        alpha=0.02,
        beta=1.1,
        score_ic=0.05,
        hit_rate=0.52,
        equity_curve=sample_equity_curve,
    )


class TestReportConfig:
    """Tests for ReportConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ReportConfig()
        assert config.title == "Sigil Backtest Report"
        assert config.include_trades is True
        assert config.include_charts is True
        assert config.output_format == "html"
        assert config.max_trades_shown == 50
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ReportConfig(
            title="Custom Report",
            include_trades=False,
            include_charts=False,
            output_format="pdf",
        )
        assert config.title == "Custom Report"
        assert config.include_trades is False
        assert config.include_charts is False
        assert config.output_format == "pdf"
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = ReportConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "Sigil Backtest Report"
        assert d["output_format"] == "html"


class TestChartGenerator:
    """Tests for chart generation."""
    
    def test_equity_curve_generation(self, sample_equity_curve):
        """Test equity curve chart is generated as base64."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        result = gen.generate_equity_curve(sample_equity_curve)
        
        assert isinstance(result, str)
        assert len(result) > 0
        # Check it's valid base64
        import base64
        try:
            decoded = base64.b64decode(result)
            assert decoded[:8] == b'\x89PNG\r\n\x1a\n'  # PNG magic bytes
        except Exception:
            pytest.fail("Generated equity curve is not valid base64 PNG")
    
    def test_equity_curve_empty_data(self):
        """Test equity curve with empty data."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        result = gen.generate_equity_curve([])
        assert result == ""
    
    def test_drawdown_chart_generation(self, sample_equity_curve):
        """Test drawdown chart is generated as base64."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        result = gen.generate_drawdown_chart(sample_equity_curve)
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_drawdown_chart_empty_data(self):
        """Test drawdown chart with empty data."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        result = gen.generate_drawdown_chart([])
        assert result == ""
    
    def test_monthly_heatmap_generation(self, sample_equity_curve):
        """Test monthly returns heatmap is generated."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        heatmap_b64, monthly_returns = gen.generate_monthly_heatmap(sample_equity_curve)
        
        assert isinstance(heatmap_b64, str)
        # Monthly returns should be a dict
        assert isinstance(monthly_returns, dict)
    
    def test_monthly_heatmap_insufficient_data(self):
        """Test heatmap with insufficient data."""
        config = ReportConfig()
        gen = ChartGenerator(config)
        
        heatmap_b64, monthly_returns = gen.generate_monthly_heatmap([])
        assert heatmap_b64 == ""
        assert monthly_returns == {}


class TestReportGenerator:
    """Tests for the main ReportGenerator class."""
    
    def test_html_generation(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML report is generated correctly."""
        # Save test data
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig()
        
        html = generator.generate_report(sample_backtest_result.backtest_id, config)
        
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "Sigil Backtest Report" in html
        assert sample_backtest_result.backtest_id in html
    
    def test_html_contains_executive_summary(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains executive summary section."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report(sample_backtest_result.backtest_id)
        
        assert "Executive Summary" in html
        assert "Total Return" in html
        assert "CAGR" in html
        assert "Sharpe Ratio" in html
        assert "Max Drawdown" in html
    
    def test_html_contains_performance_metrics(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains performance metrics section."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report(sample_backtest_result.backtest_id)
        
        assert "Performance Metrics" in html
        assert "Volatility" in html
        assert "Benchmark Return" in html
        assert "Win Rate" in html
    
    def test_html_contains_methodology(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains methodology section."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report(sample_backtest_result.backtest_id)
        
        assert "Methodology" in html
        assert "Entry Signal" in html
        assert "Exit Signal" in html
        assert "Position Sizing" in html
    
    def test_html_contains_disclaimer(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains disclaimer section."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report(sample_backtest_result.backtest_id)
        
        assert "Disclaimers" in html or "DISCLAIMERS" in html
        assert "HYPOTHETICAL PERFORMANCE" in html
        assert "Past performance" in html
    
    def test_html_contains_charts_when_enabled(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains embedded charts when enabled."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig(include_charts=True)
        html = generator.generate_report(sample_backtest_result.backtest_id, config)
        
        # Charts are embedded as base64 PNG
        assert "data:image/png;base64," in html
        assert "Equity Curve" in html
    
    def test_html_excludes_charts_when_disabled(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML excludes charts when disabled."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig(include_charts=False)
        html = generator.generate_report(sample_backtest_result.backtest_id, config)
        
        # Should not contain embedded images
        assert "data:image/png;base64," not in html
    
    def test_html_contains_trades_when_enabled(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML contains trade summary when enabled."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig(include_trades=True)
        html = generator.generate_report(sample_backtest_result.backtest_id, config)
        
        assert "Trade Summary" in html
        assert "Top Winners" in html or "Top Losers" in html
    
    def test_html_excludes_trades_when_disabled(self, temp_store, sample_backtest_result, sample_trades):
        """Test HTML excludes trades when disabled."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig(include_trades=False)
        html = generator.generate_report(sample_backtest_result.backtest_id, config)
        
        assert "Top Winners" not in html
        assert "Top Losers" not in html
    
    def test_backtest_not_found(self, temp_store):
        """Test error when backtest not found."""
        generator = ReportGenerator(data_store=temp_store)
        
        with pytest.raises(ValueError, match="Backtest not found"):
            generator.generate_report("nonexistent_backtest_id")
    
    def test_minimal_data_handling(self, temp_store):
        """Test report generation with minimal data."""
        # Create backtest with no equity curve or trades
        result = BacktestResult(
            backtest_id="bt_minimal",
            status=BacktestStatus.COMPLETED,
            parameters=BacktestParameters(
                start_date="2025-01-01",
                end_date="2025-01-31",
            ),
            created_at=datetime.now().isoformat(),
            # No metrics, no equity curve
        )
        temp_store.save_backtest_result(result)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report("bt_minimal")
        
        # Should still generate valid HTML
        assert "<!DOCTYPE html>" in html
        assert "bt_minimal" in html
        # Should show N/A for missing metrics
        assert "N/A" in html
    
    def test_output_path_html(self, temp_store, sample_backtest_result, sample_trades):
        """Test saving report to HTML file."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            
            generator = ReportGenerator(data_store=temp_store)
            generator.generate_report(
                sample_backtest_result.backtest_id,
                output_path=str(output_path)
            )
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content
    
    def test_css_is_embedded(self, temp_store, sample_backtest_result, sample_trades):
        """Test that CSS is embedded in HTML (standalone)."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        html = generator.generate_report(sample_backtest_result.backtest_id)
        
        # Check CSS is inline
        assert "<style>" in html
        assert "--bg-primary:" in html
        assert "#FFB800" in html  # Sigil gold color


class TestTradeAnalysis:
    """Tests for trade analysis in reports."""
    
    def test_top_winners_identified(self, temp_store, sample_backtest_result, sample_trades):
        """Test top winning trades are identified."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        report_data = generator._build_report_data(
            sample_backtest_result,
            sample_trades,
            ReportConfig()
        )
        
        # AAPL trade was a winner (+$1000)
        assert report_data.top_winners is not None
        assert len(report_data.top_winners) > 0
        
        aapl_winner = next((t for t in report_data.top_winners if t['ticker'] == 'AAPL'), None)
        assert aapl_winner is not None
        assert aapl_winner['pnl'] > 0
    
    def test_top_losers_identified(self, temp_store, sample_backtest_result, sample_trades):
        """Test top losing trades are identified."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        report_data = generator._build_report_data(
            sample_backtest_result,
            sample_trades,
            ReportConfig()
        )
        
        # MSFT trade was a loser (-$1000)
        # With only 2 trades, MSFT might be in winners (sorted by PnL) if there's only one loser
        # Check that at least one trade has negative PnL
        all_analyzed_trades = (report_data.top_winners or []) + (report_data.top_losers or [])
        msft_trade = next((t for t in all_analyzed_trades if t['ticker'] == 'MSFT'), None)
        
        assert msft_trade is not None, "MSFT trade should be in analyzed trades"
        assert msft_trade['pnl'] < 0, "MSFT trade should be a loser"


class TestPDFGeneration:
    """Tests for PDF generation."""
    
    def test_pdf_requires_weasyprint(self, temp_store, sample_backtest_result, sample_trades):
        """Test PDF generation requires weasyprint."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        generator = ReportGenerator(data_store=temp_store)
        config = ReportConfig(output_format="pdf")
        
        # Mock weasyprint not being installed
        with patch.dict('sys.modules', {'weasyprint': None}):
            with pytest.raises(ImportError, match="weasyprint"):
                generator.generate_report(sample_backtest_result.backtest_id, config)
    
    def test_pdf_generation_mocked(self, temp_store, sample_backtest_result, sample_trades):
        """Test PDF generation with mocked weasyprint."""
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        # Mock weasyprint
        mock_weasyprint = MagicMock()
        mock_html = MagicMock()
        mock_html.write_pdf.return_value = b'%PDF-1.4 mock pdf content'
        mock_weasyprint.HTML.return_value = mock_html
        
        with patch.dict('sys.modules', {'weasyprint': mock_weasyprint}):
            generator = ReportGenerator(data_store=temp_store)
            config = ReportConfig(output_format="pdf")
            
            pdf_bytes = generator.generate_report(sample_backtest_result.backtest_id, config)
            
            assert isinstance(pdf_bytes, bytes)
            mock_weasyprint.HTML.assert_called_once()


class TestConvenienceFunction:
    """Tests for the generate_report convenience function."""
    
    def test_generate_report_function(self, temp_store, sample_backtest_result, sample_trades):
        """Test generate_report convenience function."""
        # Patch get_data_store to return our temp_store
        temp_store.save_backtest_result(sample_backtest_result)
        temp_store.save_trades(sample_backtest_result.backtest_id, sample_trades)
        
        with patch('backtest.report_generator.get_data_store', return_value=temp_store):
            html = generate_report(
                backtest_id=sample_backtest_result.backtest_id,
                output_format="html",
                title="Custom Title",
                include_trades=True,
                include_charts=True,
            )
            
            assert isinstance(html, str)
            assert "Custom Title" in html


class TestSigilCSS:
    """Tests for the embedded CSS."""
    
    def test_css_contains_dark_theme(self):
        """Test CSS contains dark theme colors."""
        assert "--bg-primary: #0D0D0F" in SIGIL_CSS
        assert "--bg-secondary: #1A1A1D" in SIGIL_CSS
    
    def test_css_contains_gold_accent(self):
        """Test CSS contains Sigil gold accent color."""
        assert "--gold: #FFB800" in SIGIL_CSS
    
    def test_css_contains_status_colors(self):
        """Test CSS contains positive/negative status colors."""
        assert "--green: #00C853" in SIGIL_CSS
        assert "--red: #FF5252" in SIGIL_CSS
