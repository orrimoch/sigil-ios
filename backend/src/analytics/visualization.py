"""
Sector Analysis Visualization Module (REC-271)

Publication-quality charts for sector performance analysis.
Uses matplotlib for static images and plotly for interactive HTML.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

# Check for plotting libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.colors import LinearSegmentedColormap
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from .sector_analysis import SectorTimeSeries, SectorScore


# Sigil color palette
SIGIL_COLORS = {
    "background": "#0D0D0F",
    "background_light": "#1A1A1F",
    "text": "#FFFFFF",
    "text_secondary": "#9CA3AF",
    "grid": "#2A2A2F",
    "buy": "#4ADE80",
    "hold": "#FBBF24",
    "sell": "#F87171",
    "primary": "#3B82F6",
    "secondary": "#8B5CF6",
    # 12-color palette for sectors
    "sectors": [
        "#3B82F6",  # Blue
        "#10B981",  # Emerald
        "#F59E0B",  # Amber
        "#EF4444",  # Red
        "#8B5CF6",  # Violet
        "#EC4899",  # Pink
        "#14B8A6",  # Teal
        "#F97316",  # Orange
        "#6366F1",  # Indigo
        "#84CC16",  # Lime
        "#06B6D4",  # Cyan
        "#A855F7",  # Purple
    ]
}


def _setup_matplotlib_style():
    """Configure matplotlib for Sigil dark theme."""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    plt.style.use('dark_background')
    plt.rcParams.update({
        'figure.facecolor': SIGIL_COLORS["background"],
        'axes.facecolor': SIGIL_COLORS["background_light"],
        'axes.edgecolor': SIGIL_COLORS["grid"],
        'axes.labelcolor': SIGIL_COLORS["text"],
        'text.color': SIGIL_COLORS["text"],
        'xtick.color': SIGIL_COLORS["text_secondary"],
        'ytick.color': SIGIL_COLORS["text_secondary"],
        'grid.color': SIGIL_COLORS["grid"],
        'grid.alpha': 0.3,
        'font.family': 'sans-serif',
        'font.size': 10,
        'axes.titlesize': 14,
        'axes.labelsize': 11,
        'legend.fontsize': 9,
        'figure.titlesize': 16,
    })


def plot_sector_trends(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str = "Sector Score Trends",
    width: int = 1200,
    height: int = 700,
    format: str = "png"
) -> str:
    """
    Plot sector score trends as line chart.
    
    Args:
        sector_data: Dict of sector name -> SectorTimeSeries
        output_path: Output file path
        title: Chart title
        width: Chart width in pixels
        height: Chart height in pixels
        format: Output format ("png" or "html")
        
    Returns:
        Path to generated file
    """
    if format == "html" and PLOTLY_AVAILABLE:
        return _plot_trends_plotly(sector_data, output_path, title, width, height)
    elif MATPLOTLIB_AVAILABLE:
        return _plot_trends_matplotlib(sector_data, output_path, title, width, height)
    else:
        raise ImportError("Neither matplotlib nor plotly is available. Install one to generate charts.")


def _plot_trends_matplotlib(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str,
    width: int,
    height: int
) -> str:
    """Generate sector trends using matplotlib."""
    _setup_matplotlib_style()
    
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    
    colors = SIGIL_COLORS["sectors"]
    
    for i, (sector, series) in enumerate(sector_data.items()):
        if not series.scores:
            continue
        
        dates = [s.date for s in series.scores]
        scores = [s.mean_score for s in series.scores]
        
        color = colors[i % len(colors)]
        ax.plot(dates, scores, label=sector, color=color, linewidth=2, marker='o', markersize=4)
    
    # Add signal threshold lines
    ax.axhline(y=70, color=SIGIL_COLORS["buy"], linestyle='--', alpha=0.5, label='BUY threshold')
    ax.axhline(y=40, color=SIGIL_COLORS["sell"], linestyle='--', alpha=0.5, label='SELL threshold')
    
    ax.set_xlabel("Date")
    ax.set_ylabel("Mean Score")
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), ncol=1, fontsize=8)
    
    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_path, facecolor=SIGIL_COLORS["background"], edgecolor='none', bbox_inches='tight')
    plt.close()
    
    return output_path


def _plot_trends_plotly(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str,
    width: int,
    height: int
) -> str:
    """Generate interactive sector trends using plotly."""
    fig = go.Figure()
    
    colors = SIGIL_COLORS["sectors"]
    
    for i, (sector, series) in enumerate(sector_data.items()):
        if not series.scores:
            continue
        
        dates = [s.date for s in series.scores]
        scores = [s.mean_score for s in series.scores]
        
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=dates,
            y=scores,
            mode='lines+markers',
            name=sector,
            line=dict(color=color, width=2),
            marker=dict(size=6)
        ))
    
    # Add threshold lines
    fig.add_hline(y=70, line_dash="dash", line_color=SIGIL_COLORS["buy"], opacity=0.5,
                  annotation_text="BUY", annotation_position="right")
    fig.add_hline(y=40, line_dash="dash", line_color=SIGIL_COLORS["sell"], opacity=0.5,
                  annotation_text="SELL", annotation_position="right")
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=SIGIL_COLORS["text"])),
        xaxis_title="Date",
        yaxis_title="Mean Score",
        yaxis=dict(range=[0, 100]),
        template="plotly_dark",
        paper_bgcolor=SIGIL_COLORS["background"],
        plot_bgcolor=SIGIL_COLORS["background_light"],
        font=dict(color=SIGIL_COLORS["text"]),
        width=width,
        height=height,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        hovermode="x unified"
    )
    
    fig.write_html(output_path)
    return output_path


def plot_sector_heatmap(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str = "Sector Score Heatmap",
    width: int = 1200,
    height: int = 600,
    format: str = "png"
) -> str:
    """
    Plot sector scores as heatmap (sectors × dates).
    
    Args:
        sector_data: Dict of sector name -> SectorTimeSeries
        output_path: Output file path
        title: Chart title
        width: Chart width
        height: Chart height
        format: Output format
        
    Returns:
        Path to generated file
    """
    if format == "html" and PLOTLY_AVAILABLE:
        return _plot_heatmap_plotly(sector_data, output_path, title, width, height)
    elif MATPLOTLIB_AVAILABLE:
        return _plot_heatmap_matplotlib(sector_data, output_path, title, width, height)
    else:
        raise ImportError("No plotting library available")


def _plot_heatmap_matplotlib(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str,
    width: int,
    height: int
) -> str:
    """Generate heatmap using matplotlib."""
    _setup_matplotlib_style()
    
    # Prepare data matrix
    sectors = sorted(sector_data.keys())
    if not sectors:
        raise ValueError("No sector data to plot")
    
    # Get all dates
    all_dates = set()
    for series in sector_data.values():
        for score in series.scores:
            all_dates.add(score.date)
    dates = sorted(all_dates)
    
    # Build matrix
    matrix = []
    for sector in sectors:
        row = []
        series = sector_data[sector]
        date_scores = {s.date: s.mean_score for s in series.scores}
        for date in dates:
            row.append(date_scores.get(date, 50))  # Default to neutral
        matrix.append(row)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    
    # Custom colormap: red -> yellow -> green
    colors_list = [SIGIL_COLORS["sell"], SIGIL_COLORS["hold"], SIGIL_COLORS["buy"]]
    cmap = LinearSegmentedColormap.from_list("sigil", colors_list)
    
    im = ax.imshow(matrix, aspect='auto', cmap=cmap, vmin=0, vmax=100)
    
    # Labels
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(sectors)))
    ax.set_yticklabels(sectors)
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("Date")
    ax.set_ylabel("Sector")
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, label="Score")
    cbar.ax.yaxis.label.set_color(SIGIL_COLORS["text"])
    
    plt.tight_layout()
    plt.savefig(output_path, facecolor=SIGIL_COLORS["background"], bbox_inches='tight')
    plt.close()
    
    return output_path


def _plot_heatmap_plotly(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str,
    width: int,
    height: int
) -> str:
    """Generate interactive heatmap using plotly."""
    sectors = sorted(sector_data.keys())
    
    # Get all dates
    all_dates = set()
    for series in sector_data.values():
        for score in series.scores:
            all_dates.add(score.date)
    dates = sorted(all_dates)
    
    # Build matrix
    matrix = []
    for sector in sectors:
        row = []
        series = sector_data[sector]
        date_scores = {s.date: s.mean_score for s in series.scores}
        for date in dates:
            row.append(date_scores.get(date, 50))
        matrix.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=dates,
        y=sectors,
        colorscale=[
            [0, SIGIL_COLORS["sell"]],
            [0.5, SIGIL_COLORS["hold"]],
            [1, SIGIL_COLORS["buy"]]
        ],
        zmin=0,
        zmax=100,
        colorbar=dict(title="Score")
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis_title="Date",
        yaxis_title="Sector",
        template="plotly_dark",
        paper_bgcolor=SIGIL_COLORS["background"],
        plot_bgcolor=SIGIL_COLORS["background_light"],
        width=width,
        height=height
    )
    
    fig.write_html(output_path)
    return output_path


def plot_score_distribution(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str = "Score Distribution by Sector",
    width: int = 1200,
    height: int = 600,
    format: str = "png"
) -> str:
    """
    Plot score distribution as boxplots.
    
    Args:
        sector_data: Dict of sector name -> SectorTimeSeries
        output_path: Output file path
        title: Chart title
        
    Returns:
        Path to generated file
    """
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib required for boxplots")
    
    _setup_matplotlib_style()
    
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    
    # Collect all scores per sector
    sector_scores = {}
    for sector, series in sector_data.items():
        scores = [s.mean_score for s in series.scores]
        if scores:
            sector_scores[sector] = scores
    
    if not sector_scores:
        raise ValueError("No sector scores to plot")
    
    # Sort sectors by median score
    sorted_sectors = sorted(
        sector_scores.keys(),
        key=lambda s: sum(sector_scores[s]) / len(sector_scores[s]),
        reverse=True
    )
    
    data = [sector_scores[s] for s in sorted_sectors]
    
    bp = ax.boxplot(
        data,
        labels=sorted_sectors,
        patch_artist=True,
        medianprops=dict(color=SIGIL_COLORS["text"], linewidth=2),
        whiskerprops=dict(color=SIGIL_COLORS["text_secondary"]),
        capprops=dict(color=SIGIL_COLORS["text_secondary"]),
        flierprops=dict(markerfacecolor=SIGIL_COLORS["primary"], marker='o', markersize=4)
    )
    
    # Color boxes
    colors = SIGIL_COLORS["sectors"]
    for i, patch in enumerate(bp['boxes']):
        patch.set_facecolor(colors[i % len(colors)])
        patch.set_alpha(0.7)
    
    # Add threshold lines
    ax.axhline(y=70, color=SIGIL_COLORS["buy"], linestyle='--', alpha=0.5, label='BUY')
    ax.axhline(y=40, color=SIGIL_COLORS["sell"], linestyle='--', alpha=0.5, label='SELL')
    
    ax.set_ylabel("Score")
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, facecolor=SIGIL_COLORS["background"], bbox_inches='tight')
    plt.close()
    
    return output_path


def plot_signal_distribution(
    sector_data: Dict[str, SectorTimeSeries],
    output_path: str,
    title: str = "Signal Distribution Over Time",
    width: int = 1200,
    height: int = 600,
    sector: Optional[str] = None,
    format: str = "png"
) -> str:
    """
    Plot stacked area chart of BUY/HOLD/SELL distribution.
    
    Args:
        sector_data: Dict of sector name -> SectorTimeSeries
        output_path: Output file path
        title: Chart title
        sector: Optional specific sector (aggregates all if None)
        
    Returns:
        Path to generated file
    """
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib required for signal distribution plot")
    
    _setup_matplotlib_style()
    
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    
    # Aggregate signal distributions
    if sector and sector in sector_data:
        series_list = [sector_data[sector]]
    else:
        series_list = list(sector_data.values())
    
    # Collect data by date
    date_signals: Dict[str, Dict[str, float]] = {}
    
    for series in series_list:
        for score in series.scores:
            if score.date not in date_signals:
                date_signals[score.date] = {"buy": 0, "hold": 0, "sell": 0, "count": 0}
            
            date_signals[score.date]["buy"] += score.pct_buy
            date_signals[score.date]["hold"] += score.pct_hold
            date_signals[score.date]["sell"] += score.pct_sell
            date_signals[score.date]["count"] += 1
    
    # Average across sectors
    dates = sorted(date_signals.keys())
    buy_pcts = []
    hold_pcts = []
    sell_pcts = []
    
    for date in dates:
        count = date_signals[date]["count"]
        if count > 0:
            buy_pcts.append(date_signals[date]["buy"] / count)
            hold_pcts.append(date_signals[date]["hold"] / count)
            sell_pcts.append(date_signals[date]["sell"] / count)
        else:
            buy_pcts.append(0)
            hold_pcts.append(100)
            sell_pcts.append(0)
    
    # Plot stacked area
    ax.stackplot(
        dates,
        buy_pcts,
        hold_pcts,
        sell_pcts,
        labels=['BUY', 'HOLD', 'SELL'],
        colors=[SIGIL_COLORS["buy"], SIGIL_COLORS["hold"], SIGIL_COLORS["sell"]],
        alpha=0.8
    )
    
    ax.set_xlabel("Date")
    ax.set_ylabel("Percentage")
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, facecolor=SIGIL_COLORS["background"], bbox_inches='tight')
    plt.close()
    
    return output_path


def generate_sector_report(
    sector_data: Dict[str, SectorTimeSeries],
    output_dir: str,
    title: str = "Sector Performance Report"
) -> Dict[str, str]:
    """
    Generate complete sector report with all chart types.
    
    Args:
        sector_data: Dict of sector name -> SectorTimeSeries
        output_dir: Output directory for charts
        title: Report title
        
    Returns:
        Dict mapping chart type to file path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generated = {}
    
    # Generate all charts
    try:
        generated["trends"] = plot_sector_trends(
            sector_data,
            str(output_path / "sector_trends.png"),
            title=f"{title} - Score Trends"
        )
    except Exception as e:
        print(f"Warning: Could not generate trends chart: {e}")
    
    try:
        generated["heatmap"] = plot_sector_heatmap(
            sector_data,
            str(output_path / "sector_heatmap.png"),
            title=f"{title} - Heatmap"
        )
    except Exception as e:
        print(f"Warning: Could not generate heatmap: {e}")
    
    try:
        generated["distribution"] = plot_score_distribution(
            sector_data,
            str(output_path / "score_distribution.png"),
            title=f"{title} - Distribution"
        )
    except Exception as e:
        print(f"Warning: Could not generate distribution chart: {e}")
    
    try:
        generated["signals"] = plot_signal_distribution(
            sector_data,
            str(output_path / "signal_distribution.png"),
            title=f"{title} - Signals"
        )
    except Exception as e:
        print(f"Warning: Could not generate signal chart: {e}")
    
    # Generate interactive versions if plotly available
    if PLOTLY_AVAILABLE:
        try:
            generated["trends_interactive"] = plot_sector_trends(
                sector_data,
                str(output_path / "sector_trends.html"),
                title=f"{title} - Score Trends",
                format="html"
            )
        except Exception as e:
            print(f"Warning: Could not generate interactive trends: {e}")
        
        try:
            generated["heatmap_interactive"] = plot_sector_heatmap(
                sector_data,
                str(output_path / "sector_heatmap.html"),
                title=f"{title} - Heatmap",
                format="html"
            )
        except Exception as e:
            print(f"Warning: Could not generate interactive heatmap: {e}")
    
    return generated
