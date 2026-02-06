"""
F12.10 Report Generator

Generate professional PDF and HTML backtest reports.

Features:
- Executive Summary with key metrics
- Performance metrics table
- Equity curve chart (embedded PNG)
- Drawdown analysis
- Monthly returns heatmap
- Score validation metrics
- Trade log summary
- Methodology notes
- Standard disclaimers

Output Formats:
- HTML (standalone with embedded CSS/images)
- PDF (via weasyprint)
"""

import base64
import io
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    get_data_store,
)
from backtest.metrics import MetricsCalculator, PerformanceMetrics, ScoreValidationMetrics


# ============================================================
# Configuration
# ============================================================

@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "Sigil Backtest Report"
    include_trades: bool = True
    include_charts: bool = True
    output_format: str = "html"  # or "pdf"
    max_trades_shown: int = 50
    chart_width: int = 10
    chart_height: int = 5
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReportData:
    """All data needed for report generation."""
    backtest_result: BacktestResult
    trades: List[BacktestTrade]
    performance_metrics: Optional[PerformanceMetrics] = None
    validation_metrics: Optional[ScoreValidationMetrics] = None
    equity_chart_base64: Optional[str] = None
    drawdown_chart_base64: Optional[str] = None
    heatmap_chart_base64: Optional[str] = None
    monthly_returns: Optional[Dict[str, Dict[str, float]]] = None
    benchmark_equity: Optional[List[float]] = None
    top_winners: Optional[List[Dict]] = None
    top_losers: Optional[List[Dict]] = None


# ============================================================
# CSS Styles (Sigil Dark Theme)
# ============================================================

SIGIL_CSS = """
:root {
    --bg-primary: #0D0D0F;
    --bg-secondary: #1A1A1D;
    --bg-tertiary: #2A2A2E;
    --text-primary: #FFFFFF;
    --text-secondary: #A0A0A0;
    --text-muted: #6B6B6B;
    --gold: #FFB800;
    --gold-light: #FFC933;
    --green: #00C853;
    --red: #FF5252;
    --blue: #448AFF;
    --border: #3A3A3E;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    padding: 2rem;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

/* Header */
.header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 2rem;
    border-bottom: 1px solid var(--border);
}

.header h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.header .subtitle {
    color: var(--text-secondary);
    font-size: 1.1rem;
}

.header .meta {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

/* Sections */
section {
    margin-bottom: 3rem;
}

section h2 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--gold);
    margin-bottom: 1.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--gold);
    display: inline-block;
}

section h3 {
    font-size: 1.2rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 1rem;
}

/* Executive Summary Cards */
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.summary-card {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid var(--border);
}

.summary-card .label {
    color: var(--text-secondary);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.5rem;
}

.summary-card .value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--text-primary);
}

.summary-card .value.positive {
    color: var(--green);
}

.summary-card .value.negative {
    color: var(--red);
}

.summary-card .value.gold {
    color: var(--gold);
}

.summary-card .subvalue {
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.5rem;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
}

th, td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

th {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

td {
    color: var(--text-primary);
}

tr:last-child td {
    border-bottom: none;
}

tr:hover {
    background: var(--bg-tertiary);
}

.positive {
    color: var(--green);
}

.negative {
    color: var(--red);
}

.neutral {
    color: var(--text-secondary);
}

/* Charts */
.chart-container {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 2rem;
    border: 1px solid var(--border);
}

.chart-container img {
    width: 100%;
    height: auto;
    border-radius: 8px;
}

/* Monthly Returns Heatmap */
.heatmap-table {
    font-size: 0.9rem;
}

.heatmap-table th,
.heatmap-table td {
    text-align: center;
    padding: 0.75rem;
    min-width: 60px;
}

.heatmap-cell {
    border-radius: 4px;
    font-weight: 600;
}

/* Methodology */
.methodology {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 2rem;
    border: 1px solid var(--border);
}

.methodology ul {
    list-style: none;
    padding: 0;
}

.methodology li {
    padding: 0.5rem 0;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
}

.methodology li:last-child {
    border-bottom: none;
}

.methodology li strong {
    color: var(--text-primary);
    margin-right: 0.5rem;
}

/* Disclaimers */
.disclaimer {
    background: var(--bg-tertiary);
    border-radius: 8px;
    padding: 1.5rem;
    font-size: 0.85rem;
    color: var(--text-muted);
    line-height: 1.8;
    border-left: 4px solid var(--gold);
}

.disclaimer strong {
    color: var(--text-secondary);
}

/* Two Column Layout */
.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
}

@media (max-width: 768px) {
    .two-col {
        grid-template-columns: 1fr;
    }
    
    .summary-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

/* Footer */
.footer {
    margin-top: 4rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-muted);
    font-size: 0.85rem;
}

.footer .logo {
    color: var(--gold);
    font-weight: 700;
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
}
"""


# ============================================================
# Chart Generation
# ============================================================

class ChartGenerator:
    """Generate charts for the report."""
    
    def __init__(self, config: ReportConfig):
        self.config = config
        self._setup_style()
    
    def _setup_style(self):
        """Set up matplotlib style for Sigil theme."""
        plt.rcParams.update({
            'figure.facecolor': '#0D0D0F',
            'axes.facecolor': '#1A1A1D',
            'axes.edgecolor': '#3A3A3E',
            'axes.labelcolor': '#A0A0A0',
            'text.color': '#FFFFFF',
            'xtick.color': '#A0A0A0',
            'ytick.color': '#A0A0A0',
            'grid.color': '#3A3A3E',
            'grid.alpha': 0.5,
            'legend.facecolor': '#1A1A1D',
            'legend.edgecolor': '#3A3A3E',
        })
    
    def generate_equity_curve(
        self,
        equity_curve: List[EquityPoint],
        benchmark_equity: Optional[List[float]] = None,
        initial_capital: float = 100000,
    ) -> str:
        """Generate equity curve chart, return as base64 PNG."""
        if not equity_curve:
            return ""
        
        fig, ax = plt.subplots(figsize=(self.config.chart_width, self.config.chart_height))
        
        # Strategy equity
        dates = [datetime.strptime(ep.date if isinstance(ep, EquityPoint) else ep['date'], "%Y-%m-%d") 
                 for ep in equity_curve]
        navs = [ep.nav if isinstance(ep, EquityPoint) else ep['nav'] for ep in equity_curve]
        
        ax.plot(dates, navs, color='#FFB800', linewidth=2, label='Strategy')
        
        # Benchmark (SPY)
        if benchmark_equity and len(benchmark_equity) == len(dates):
            ax.plot(dates, benchmark_equity, color='#448AFF', linewidth=1.5, 
                    linestyle='--', alpha=0.7, label='SPY')
        
        # Initial capital line
        ax.axhline(y=initial_capital, color='#3A3A3E', linestyle=':', linewidth=1, alpha=0.5)
        
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Portfolio Value ($)', fontsize=10)
        ax.set_title('Equity Curve', fontsize=12, fontweight='bold', color='#FFFFFF')
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        # Format dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                   facecolor='#0D0D0F', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def generate_drawdown_chart(self, equity_curve: List[EquityPoint]) -> str:
        """Generate drawdown chart, return as base64 PNG."""
        if not equity_curve:
            return ""
        
        fig, ax = plt.subplots(figsize=(self.config.chart_width, self.config.chart_height * 0.6))
        
        dates = [datetime.strptime(ep.date if isinstance(ep, EquityPoint) else ep['date'], "%Y-%m-%d")
                 for ep in equity_curve]
        drawdowns = [ep.drawdown if isinstance(ep, EquityPoint) else ep.get('drawdown', 0)
                     for ep in equity_curve]
        
        # Convert to percentage
        drawdowns_pct = [d * 100 for d in drawdowns]
        
        ax.fill_between(dates, drawdowns_pct, 0, color='#FF5252', alpha=0.4)
        ax.plot(dates, drawdowns_pct, color='#FF5252', linewidth=1.5)
        
        ax.axhline(y=0, color='#3A3A3E', linestyle='-', linewidth=1)
        
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Drawdown (%)', fontsize=10)
        ax.set_title('Drawdown Analysis', fontsize=12, fontweight='bold', color='#FFFFFF')
        ax.grid(True, alpha=0.3)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                   facecolor='#0D0D0F', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def generate_monthly_heatmap(self, equity_curve: List[EquityPoint]) -> tuple:
        """Generate monthly returns heatmap, return (base64 PNG, monthly_returns dict)."""
        if not equity_curve or len(equity_curve) < 2:
            return "", {}
        
        # Calculate monthly returns
        df = pd.DataFrame([
            {'date': ep.date if isinstance(ep, EquityPoint) else ep['date'],
             'nav': ep.nav if isinstance(ep, EquityPoint) else ep['nav']}
            for ep in equity_curve
        ])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Resample to month-end NAV
        monthly = df.resample('ME').last()
        monthly['return'] = monthly['nav'].pct_change()
        
        # Create pivot table
        monthly['year'] = monthly.index.year
        monthly['month'] = monthly.index.month
        
        pivot = monthly.pivot_table(values='return', index='year', columns='month', aggfunc='first')
        
        # Fill missing months
        all_months = range(1, 13)
        for month in all_months:
            if month not in pivot.columns:
                pivot[month] = np.nan
        pivot = pivot.reindex(columns=sorted(pivot.columns))
        
        # Generate chart
        fig, ax = plt.subplots(figsize=(self.config.chart_width, max(2, len(pivot) * 0.6 + 1)))
        
        # Create heatmap
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        data = pivot.values * 100  # Convert to percentage
        
        # Color map: red for negative, green for positive
        cmap = plt.cm.RdYlGn
        norm = plt.Normalize(vmin=-15, vmax=15)
        
        im = ax.imshow(data, cmap=cmap, norm=norm, aspect='auto')
        
        # Add text annotations
        for i in range(len(pivot)):
            for j in range(12):
                if not np.isnan(data[i, j]):
                    text_color = 'white' if abs(data[i, j]) > 8 else 'black'
                    ax.text(j, i, f'{data[i, j]:.1f}%',
                           ha='center', va='center', color=text_color, fontsize=8)
        
        ax.set_xticks(np.arange(12))
        ax.set_xticklabels(month_names, fontsize=9)
        ax.set_yticks(np.arange(len(pivot)))
        ax.set_yticklabels(pivot.index.astype(int), fontsize=10)
        
        ax.set_title('Monthly Returns (%)', fontsize=12, fontweight='bold', color='#FFFFFF', pad=10)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Return %', fontsize=9)
        cbar.ax.tick_params(labelsize=8)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                   facecolor='#0D0D0F', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        
        # Build monthly returns dict
        monthly_dict = {}
        for year in pivot.index:
            year_str = str(int(year))
            monthly_dict[year_str] = {}
            for month in pivot.columns:
                val = pivot.loc[year, month]
                if not np.isnan(val):
                    monthly_dict[year_str][month_names[month - 1]] = round(val * 100, 2)
        
        return base64.b64encode(buf.read()).decode('utf-8'), monthly_dict


# ============================================================
# Report Generator
# ============================================================

class ReportGenerator:
    """Generate backtest reports in HTML and PDF formats."""
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self.metrics_calculator = MetricsCalculator(data_store)
    
    def generate_report(
        self,
        backtest_id: str,
        config: Optional[ReportConfig] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a report for a backtest.
        
        Args:
            backtest_id: ID of the backtest
            config: Report configuration
            output_path: Path to save the report (optional)
            
        Returns:
            Generated HTML content (or PDF bytes if format is pdf)
        """
        config = config or ReportConfig()
        
        # Load backtest data
        result = self.data_store.get_backtest_result(backtest_id)
        if not result:
            raise ValueError(f"Backtest not found: {backtest_id}")
        
        trades = self.data_store.get_trades(backtest_id)
        
        # Build report data
        report_data = self._build_report_data(result, trades, config)
        
        # Generate HTML
        html = self._generate_html(report_data, config)
        
        # Convert to PDF if requested
        if config.output_format.lower() == "pdf":
            pdf_bytes = self._convert_to_pdf(html)
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes)
                logger.info(f"Report saved to {output_path}")
            return pdf_bytes
        
        # Save HTML if output path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(html)
            logger.info(f"Report saved to {output_path}")
        
        return html
    
    def _build_report_data(
        self,
        result: BacktestResult,
        trades: List[BacktestTrade],
        config: ReportConfig,
    ) -> ReportData:
        """Build all data needed for the report."""
        report_data = ReportData(
            backtest_result=result,
            trades=trades,
        )
        
        # Calculate performance metrics
        if result.equity_curve:
            try:
                trades_dict = [t.to_dict() for t in trades]
                report_data.performance_metrics = self.metrics_calculator.calculate_performance_metrics(
                    equity_curve=result.equity_curve,
                    trades=trades_dict,
                    initial_capital=result.parameters.initial_capital,
                    start_date=result.parameters.start_date,
                    end_date=result.parameters.end_date,
                )
            except Exception as e:
                logger.warning(f"Failed to calculate performance metrics: {e}")
        
        # Calculate validation metrics
        try:
            report_data.validation_metrics = self.metrics_calculator.calculate_score_validation_metrics(
                result.parameters.start_date,
                result.parameters.end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to calculate validation metrics: {e}")
        
        # Generate charts
        if config.include_charts and result.equity_curve:
            chart_gen = ChartGenerator(config)
            
            # Equity curve
            try:
                report_data.equity_chart_base64 = chart_gen.generate_equity_curve(
                    result.equity_curve,
                    initial_capital=result.parameters.initial_capital,
                )
            except Exception as e:
                logger.warning(f"Failed to generate equity chart: {e}")
            
            # Drawdown chart
            try:
                report_data.drawdown_chart_base64 = chart_gen.generate_drawdown_chart(result.equity_curve)
            except Exception as e:
                logger.warning(f"Failed to generate drawdown chart: {e}")
            
            # Monthly heatmap
            try:
                heatmap, monthly_returns = chart_gen.generate_monthly_heatmap(result.equity_curve)
                report_data.heatmap_chart_base64 = heatmap
                report_data.monthly_returns = monthly_returns
            except Exception as e:
                logger.warning(f"Failed to generate heatmap: {e}")
        
        # Analyze trades
        if trades:
            report_data.top_winners, report_data.top_losers = self._analyze_trades(trades)
        
        return report_data
    
    def _analyze_trades(self, trades: List[BacktestTrade]) -> tuple:
        """Analyze trades to find top winners and losers."""
        # Match buys and sells to calculate P&L
        trades_by_ticker = {}
        for t in trades:
            if t.ticker not in trades_by_ticker:
                trades_by_ticker[t.ticker] = {'buys': [], 'sells': []}
            if t.side == 'buy':
                trades_by_ticker[t.ticker]['buys'].append(t)
            else:
                trades_by_ticker[t.ticker]['sells'].append(t)
        
        completed_trades = []
        for ticker, ticker_trades in trades_by_ticker.items():
            for sell in ticker_trades['sells']:
                # Find most recent buy before this sell
                buys_before = [b for b in ticker_trades['buys'] if b.date < sell.date]
                if buys_before:
                    buy = buys_before[-1]
                    pnl = (sell.price - buy.price) * sell.quantity
                    pnl_pct = ((sell.price / buy.price) - 1) * 100
                    completed_trades.append({
                        'ticker': ticker,
                        'buy_date': buy.date,
                        'sell_date': sell.date,
                        'buy_price': round(buy.price, 2),
                        'sell_price': round(sell.price, 2),
                        'quantity': sell.quantity,
                        'pnl': round(pnl, 2),
                        'pnl_pct': round(pnl_pct, 2),
                    })
        
        # Sort by P&L
        completed_trades.sort(key=lambda x: x['pnl'], reverse=True)
        
        top_winners = completed_trades[:5] if len(completed_trades) >= 5 else completed_trades
        top_losers = completed_trades[-5:][::-1] if len(completed_trades) >= 5 else []
        
        return top_winners, top_losers
    
    def _generate_html(self, data: ReportData, config: ReportConfig) -> str:
        """Generate HTML report."""
        result = data.backtest_result
        params = result.parameters
        
        # Format helper
        def fmt_pct(val, decimals=2):
            if val is None:
                return "N/A"
            return f"{val * 100:.{decimals}f}%"
        
        def fmt_num(val, decimals=2):
            if val is None:
                return "N/A"
            return f"{val:,.{decimals}f}"
        
        def fmt_money(val):
            if val is None:
                return "N/A"
            return f"${val:,.0f}"
        
        def value_class(val):
            if val is None:
                return ""
            return "positive" if val > 0 else "negative" if val < 0 else ""
        
        # Build HTML
        html_parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.title}</title>
    <style>{SIGIL_CSS}</style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <h1>{config.title}</h1>
            <p class="subtitle">Backtest ID: {result.backtest_id}</p>
            <p class="meta">
                {params.start_date} to {params.end_date} | 
                Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}
            </p>
        </header>
"""]
        
        # Executive Summary
        total_return = result.total_return or 0
        cagr = result.cagr or 0
        sharpe = result.sharpe_ratio or 0
        max_dd = result.max_drawdown or 0
        benchmark = result.benchmark_return or 0
        alpha = result.alpha or 0
        
        html_parts.append(f"""
        <!-- Executive Summary -->
        <section>
            <h2>Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Total Return</div>
                    <div class="value {value_class(total_return)}">{fmt_pct(total_return)}</div>
                    <div class="subvalue">vs SPY: {fmt_pct(benchmark)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">CAGR</div>
                    <div class="value {value_class(cagr)}">{fmt_pct(cagr)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Sharpe Ratio</div>
                    <div class="value gold">{fmt_num(sharpe)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Max Drawdown</div>
                    <div class="value negative">{fmt_pct(max_dd)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Alpha</div>
                    <div class="value {value_class(alpha)}">{fmt_pct(alpha)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Win Rate</div>
                    <div class="value">{fmt_pct(result.win_rate)}</div>
                    <div class="subvalue">{result.total_trades or 0} trades</div>
                </div>
            </div>
        </section>
""")
        
        # Performance Metrics Table
        perf = data.performance_metrics
        html_parts.append(f"""
        <!-- Performance Metrics -->
        <section>
            <h2>Performance Metrics</h2>
            <div class="two-col">
                <div>
                    <h3>Returns</h3>
                    <table>
                        <tr><td>Total Return</td><td class="{value_class(total_return)}">{fmt_pct(total_return)}</td></tr>
                        <tr><td>CAGR</td><td class="{value_class(cagr)}">{fmt_pct(cagr)}</td></tr>
                        <tr><td>Benchmark Return (SPY)</td><td class="{value_class(benchmark)}">{fmt_pct(benchmark)}</td></tr>
                        <tr><td>Alpha</td><td class="{value_class(alpha)}">{fmt_pct(alpha)}</td></tr>
                        <tr><td>Beta</td><td>{fmt_num(perf.beta if perf else 1.0)}</td></tr>
                    </table>
                </div>
                <div>
                    <h3>Risk</h3>
                    <table>
                        <tr><td>Volatility (Ann.)</td><td>{fmt_pct(perf.volatility if perf else result.volatility)}</td></tr>
                        <tr><td>Sharpe Ratio</td><td>{fmt_num(sharpe)}</td></tr>
                        <tr><td>Sortino Ratio</td><td>{fmt_num(perf.sortino_ratio if perf else 0)}</td></tr>
                        <tr><td>Max Drawdown</td><td class="negative">{fmt_pct(max_dd)}</td></tr>
                        <tr><td>Calmar Ratio</td><td>{fmt_num(perf.calmar_ratio if perf else 0)}</td></tr>
                    </table>
                </div>
            </div>
            <div class="two-col" style="margin-top: 1.5rem;">
                <div>
                    <h3>Trading</h3>
                    <table>
                        <tr><td>Total Trades</td><td>{result.total_trades or 0}</td></tr>
                        <tr><td>Win Rate</td><td>{fmt_pct(result.win_rate)}</td></tr>
                        <tr><td>Profit Factor</td><td>{fmt_num(perf.profit_factor if perf else 1.0)}</td></tr>
                        <tr><td>Avg Holding Period</td><td>{fmt_num(perf.avg_holding_period_days if perf else 0, 1)} days</td></tr>
                    </table>
                </div>
                <div>
                    <h3>Capital</h3>
                    <table>
                        <tr><td>Starting Capital</td><td>{fmt_money(params.initial_capital)}</td></tr>
                        <tr><td>Ending Value</td><td>{fmt_money(params.initial_capital * (1 + total_return))}</td></tr>
                        <tr><td>Max Positions</td><td>{params.max_positions}</td></tr>
                        <tr><td>Rebalance Frequency</td><td>{params.rebalance_freq.capitalize()}</td></tr>
                    </table>
                </div>
            </div>
        </section>
""")
        
        # Equity Curve Chart
        if data.equity_chart_base64:
            html_parts.append(f"""
        <!-- Equity Curve -->
        <section>
            <h2>Equity Curve</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{data.equity_chart_base64}" alt="Equity Curve">
            </div>
        </section>
""")
        
        # Drawdown Chart
        if data.drawdown_chart_base64:
            html_parts.append(f"""
        <!-- Drawdown Analysis -->
        <section>
            <h2>Drawdown Analysis</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{data.drawdown_chart_base64}" alt="Drawdown Chart">
            </div>
""")
            # Worst drawdown periods
            if result.equity_curve:
                worst_dd = min(
                    [(ep.drawdown if isinstance(ep, EquityPoint) else ep.get('drawdown', 0), 
                      ep.date if isinstance(ep, EquityPoint) else ep['date'])
                     for ep in result.equity_curve],
                    key=lambda x: x[0]
                )
                html_parts.append(f"""
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Maximum Drawdown</td>
                    <td class="negative">{fmt_pct(worst_dd[0])}</td>
                </tr>
                <tr>
                    <td>Worst Drawdown Date</td>
                    <td>{worst_dd[1]}</td>
                </tr>
            </table>
""")
            html_parts.append("        </section>\n")
        
        # Monthly Returns Heatmap
        if data.heatmap_chart_base64:
            html_parts.append(f"""
        <!-- Monthly Returns -->
        <section>
            <h2>Monthly Returns</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{data.heatmap_chart_base64}" alt="Monthly Returns Heatmap">
            </div>
        </section>
""")
        
        # Score Validation
        val = data.validation_metrics
        if val:
            html_parts.append(f"""
        <!-- Score Validation -->
        <section>
            <h2>Score Validation</h2>
            <div class="two-col">
                <div>
                    <h3>Information Coefficient</h3>
                    <table>
                        <tr><td>Score IC</td><td>{fmt_num(val.score_ic, 4)}</td></tr>
                        <tr><td>IC T-Statistic</td><td>{fmt_num(val.score_ic_t_stat)}</td></tr>
                        <tr><td>IC P-Value</td><td>{fmt_num(val.score_ic_p_value, 4)}</td></tr>
                    </table>
                </div>
                <div>
                    <h3>Hit Rate Analysis</h3>
                    <table>
                        <tr><td>Overall Hit Rate</td><td>{fmt_pct(val.hit_rate)}</td></tr>
                        <tr><td>Quintile Spread</td><td>{fmt_pct(val.quintile_spread)}</td></tr>
                        <tr><td>Signal Flip Rate</td><td>{fmt_pct(val.signal_flip_rate)}</td></tr>
                    </table>
                </div>
            </div>
""")
            # Quintile returns
            if val.quintile_returns:
                html_parts.append("""
            <h3 style="margin-top: 1.5rem;">Quintile Returns</h3>
            <table>
                <tr>
                    <th>Quintile</th>
                    <th>Avg Return</th>
                    <th>Description</th>
                </tr>
""")
                quintile_desc = {
                    'Q1': 'Top 20% (Highest Scores)',
                    'Q2': 'Second 20%',
                    'Q3': 'Middle 20%',
                    'Q4': 'Fourth 20%',
                    'Q5': 'Bottom 20% (Lowest Scores)',
                }
                for q in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
                    ret = val.quintile_returns.get(q, 0)
                    html_parts.append(f"""
                <tr>
                    <td>{q}</td>
                    <td class="{value_class(ret)}">{fmt_pct(ret)}</td>
                    <td style="color: var(--text-muted)">{quintile_desc.get(q, '')}</td>
                </tr>
""")
                html_parts.append("            </table>\n")
            
            html_parts.append("        </section>\n")
        
        # Trade Log Summary
        if config.include_trades and data.trades:
            html_parts.append("""
        <!-- Trade Log Summary -->
        <section>
            <h2>Trade Summary</h2>
""")
            # Top Winners
            if data.top_winners:
                html_parts.append("""
            <h3>Top Winners</h3>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Buy Date</th>
                    <th>Buy Price</th>
                    <th>Sell Date</th>
                    <th>Sell Price</th>
                    <th>P&L</th>
                    <th>Return</th>
                </tr>
""")
                for trade in data.top_winners:
                    pnl_class = value_class(trade['pnl'])
                    html_parts.append(f"""
                <tr>
                    <td><strong>{trade['ticker']}</strong></td>
                    <td>{trade['buy_date']}</td>
                    <td>${trade['buy_price']:,.2f}</td>
                    <td>{trade['sell_date']}</td>
                    <td>${trade['sell_price']:,.2f}</td>
                    <td class="{pnl_class}">${trade['pnl']:,.2f}</td>
                    <td class="{pnl_class}">{trade['pnl_pct']:.1f}%</td>
                </tr>
""")
                html_parts.append("            </table>\n")
            
            # Top Losers
            if data.top_losers:
                html_parts.append("""
            <h3 style="margin-top: 1.5rem;">Top Losers</h3>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Buy Date</th>
                    <th>Buy Price</th>
                    <th>Sell Date</th>
                    <th>Sell Price</th>
                    <th>P&L</th>
                    <th>Return</th>
                </tr>
""")
                for trade in data.top_losers:
                    pnl_class = value_class(trade['pnl'])
                    html_parts.append(f"""
                <tr>
                    <td><strong>{trade['ticker']}</strong></td>
                    <td>{trade['buy_date']}</td>
                    <td>${trade['buy_price']:,.2f}</td>
                    <td>{trade['sell_date']}</td>
                    <td>${trade['sell_price']:,.2f}</td>
                    <td class="{pnl_class}">${trade['pnl']:,.2f}</td>
                    <td class="{pnl_class}">{trade['pnl_pct']:.1f}%</td>
                </tr>
""")
                html_parts.append("            </table>\n")
            
            html_parts.append("        </section>\n")
        
        # Methodology
        html_parts.append(f"""
        <!-- Methodology -->
        <section>
            <h2>Methodology</h2>
            <div class="methodology">
                <ul>
                    <li><strong>Strategy:</strong> Score-based signal generation with weekly rebalancing</li>
                    <li><strong>Entry Signal:</strong> Buy when composite score ≥ {params.entry_threshold}</li>
                    <li><strong>Exit Signal:</strong> Sell when composite score &lt; {params.exit_threshold}</li>
                    <li><strong>Position Sizing:</strong> Equal weight across max {params.max_positions} positions</li>
                    <li><strong>Rebalancing:</strong> {params.rebalance_freq.capitalize()}</li>
                    <li><strong>Transaction Costs:</strong> {params.transaction_cost * 100:.2f}% per trade</li>
                    <li><strong>Slippage Model:</strong> {params.slippage * 100:.2f}% adverse price impact</li>
                    <li><strong>Data Period:</strong> {params.start_date} to {params.end_date}</li>
                    <li><strong>Benchmark:</strong> S&P 500 (SPY ETF)</li>
                </ul>
            </div>
        </section>
""")
        
        # Disclaimers
        html_parts.append("""
        <!-- Disclaimers -->
        <section>
            <h2>Important Disclaimers</h2>
            <div class="disclaimer">
                <p><strong>HYPOTHETICAL PERFORMANCE RESULTS HAVE MANY INHERENT LIMITATIONS.</strong></p>
                <p style="margin-top: 1rem;">
                    No representation is being made that any account will or is likely to achieve profits or losses 
                    similar to those shown. In fact, there are frequently sharp differences between hypothetical 
                    performance results and the actual results subsequently achieved by any particular trading program.
                </p>
                <p style="margin-top: 1rem;">
                    One of the limitations of hypothetical performance results is that they are generally prepared 
                    with the benefit of hindsight. In addition, hypothetical trading does not involve financial risk, 
                    and no hypothetical trading record can completely account for the impact of financial risk in 
                    actual trading. For example, the ability to withstand losses or to adhere to a particular trading 
                    program in spite of trading losses are material points which can also adversely affect actual 
                    trading results.
                </p>
                <p style="margin-top: 1rem;">
                    There are numerous other factors related to the markets in general or to the implementation of 
                    any specific trading program which cannot be fully accounted for in the preparation of hypothetical 
                    performance results and all of which can adversely affect actual trading results.
                </p>
                <p style="margin-top: 1rem;">
                    <strong>Past performance is not indicative of future results.</strong> This backtest report is 
                    for informational purposes only and does not constitute investment advice.
                </p>
            </div>
        </section>
""")
        
        # Footer
        html_parts.append("""
        <!-- Footer -->
        <footer class="footer">
            <div class="logo">SIGIL</div>
            <p>AI-Powered Stock Recommendations</p>
            <p style="margin-top: 0.5rem;">Report generated by Sigil Backtesting Engine</p>
        </footer>
    </div>
</body>
</html>
""")
        
        return ''.join(html_parts)
    
    def _convert_to_pdf(self, html: str) -> bytes:
        """Convert HTML to PDF using weasyprint."""
        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            return pdf
        except ImportError:
            logger.error("weasyprint not installed. Install with: pip install weasyprint")
            raise ImportError("PDF generation requires weasyprint. Install with: pip install weasyprint")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise


# ============================================================
# Convenience Functions
# ============================================================

def generate_report(
    backtest_id: str,
    output_format: str = "html",
    output_path: Optional[str] = None,
    title: str = "Sigil Backtest Report",
    include_trades: bool = True,
    include_charts: bool = True,
) -> str:
    """
    Generate a backtest report.
    
    Args:
        backtest_id: ID of the backtest
        output_format: "html" or "pdf"
        output_path: Path to save the report (optional)
        title: Report title
        include_trades: Include trade log summary
        include_charts: Include charts
        
    Returns:
        HTML content or PDF bytes
    """
    config = ReportConfig(
        title=title,
        include_trades=include_trades,
        include_charts=include_charts,
        output_format=output_format,
    )
    
    generator = ReportGenerator()
    return generator.generate_report(backtest_id, config, output_path)


# CLI for testing
if __name__ == "__main__":
    import sys
    
    print("\n=== Report Generator Test ===\n")
    
    # List available backtests
    store = get_data_store()
    backtests = store.list_backtests(limit=5)
    
    if not backtests:
        print("No backtests found. Run a backtest first.")
        sys.exit(1)
    
    print("Available backtests:")
    for bt in backtests:
        print(f"  - {bt.backtest_id} ({bt.status.value})")
    
    # Generate report for the latest completed backtest
    completed = [bt for bt in backtests if bt.status.value == "completed"]
    if not completed:
        print("\nNo completed backtests found.")
        sys.exit(1)
    
    latest = completed[0]
    print(f"\nGenerating report for: {latest.backtest_id}")
    
    try:
        html = generate_report(
            backtest_id=latest.backtest_id,
            output_format="html",
            output_path="test_report.html",
        )
        print(f"\n✅ Report generated successfully!")
        print(f"   Output: test_report.html ({len(html)} bytes)")
    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        raise
