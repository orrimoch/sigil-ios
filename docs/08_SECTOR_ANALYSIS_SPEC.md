<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sector Performance Analysis Feature Specification

**Ticket:** REC-271  
**Author:** AI Assistant (PM + Developer)  
**Date:** February 14, 2026  
**Status:** Implementation Ready

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals & Benefits](#goals--benefits)
4. [Data Model](#data-model)
5. [CLI Interface Design](#cli-interface-design)
6. [Visualization Approach](#visualization-approach)
7. [Implementation Plan](#implementation-plan)
8. [Technical Specifications](#technical-specifications)
9. [Testing Strategy](#testing-strategy)

---

## Executive Summary

This feature introduces **Sector Performance Analysis** capabilities to Sigil's backend, enabling analysis of score distributions across granular sector/industry classifications over time. It answers the question:

> **"How are different market sectors performing according to Sigil's scoring model, and where is sentiment shifting?"**

The analysis uses existing historical score data and provides CLI-based reporting with publication-quality visualizations.

---

## Problem Statement

### Current Limitations

1. **Aggregate-Only View**: Current scores are per-stock; no aggregate sector-level insights
2. **No Temporal Trends**: Can't see how sector sentiment evolves over time
3. **Missing Context**: A stock's score lacks context without sector comparison
4. **No Market Rotation Detection**: Hard to identify sector rotations or sentiment shifts

### The Opportunity

Sector analysis enables:
- **Market Sentiment Mapping**: Identify which sectors are bullish/bearish
- **Rotation Detection**: Spot capital flows between sectors
- **Relative Strength**: Compare a stock's score against its sector peers
- **Risk Assessment**: Detect concentration of risk in specific sectors

---

## Goals & Benefits

### Primary Goals

| Goal | Metric | Target |
|------|--------|--------|
| Granular Sector Insights | Industry-level analysis | 100+ industries |
| Temporal Analysis | Score trends over time | Up to 90 days |
| Data Quality | Handle missing scores | 0% analysis gaps |
| Visualization | Publication-quality charts | 5+ chart types |

### User Benefits

1. **Portfolio Managers**: Identify overweight/underweight sectors relative to sentiment
2. **Traders**: Spot sector rotation opportunities
3. **Analysts**: Understand market breadth and sentiment distribution
4. **Risk Managers**: Monitor sector concentration risk

---

## Data Model

### Existing Data Sources

#### Stock Universe (`stock_universe.json`)
```json
{
  "stocks": [
    {
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "sector": "Technology",
      "industry": "Semiconductors",
      "market_cap": 4551428538368
    }
  ]
}
```

- **850 stocks** with sector/industry classification
- **12 sectors**: Technology, Financial Services, Healthcare, etc.
- **100+ industries**: Granular sub-classifications (e.g., "Semiconductors", "Software - Application")

#### Score History (`score_history.json`)
```json
{
  "AAPL": [
    {
      "date": "2026-02-14",
      "total_score": 75.0,
      "signal": "BUY",
      "fundamental_score": 80.0,
      "sentiment_score": 70.0,
      "technical_score": 75.0,
      "macro_score": 72.0
    }
  ]
}
```

- **955 tickers** with historical scores
- Up to **90 days** of history per ticker
- **6 score dimensions**: total, fundamental, sentiment, technical, macro, signal

### New Data Structures

#### SectorClassification
```python
@dataclass
class SectorClassification:
    """Hierarchical sector classification."""
    sector: str           # e.g., "Technology"
    industry: str         # e.g., "Semiconductors"
    full_path: str        # e.g., "Technology/Semiconductors"
```

#### SectorScore
```python
@dataclass
class SectorScore:
    """Aggregated sector score for a date."""
    date: str
    sector: str
    industry: Optional[str]
    
    # Aggregated metrics
    mean_score: float
    median_score: float
    std_score: float
    min_score: float
    max_score: float
    
    # Distribution
    pct_buy: float       # % with BUY signal
    pct_hold: float      # % with HOLD signal
    pct_sell: float      # % with SELL signal
    
    # Coverage
    stock_count: int
    missing_count: int   # Imputed scores
```

#### SectorTimeSeries
```python
@dataclass
class SectorTimeSeries:
    """Time series of sector scores."""
    sector: str
    industry: Optional[str]
    date_range: Tuple[str, str]
    scores: List[SectorScore]
```

---

## CLI Interface Design

### Command Structure

```bash
python3 -m src.analytics [COMMAND] [OPTIONS]
```

### Commands

#### `sector-scores` — Calculate Sector Score Distribution

```bash
python3 -m src.analytics sector-scores [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 30 days ago | Start date (YYYY-MM-DD) |
| `--end` | DATE | Today | End date (YYYY-MM-DD) |
| `--sector` | STRING | All | Filter by sector name |
| `--industry` | STRING | All | Filter by industry name |
| `--top-n` | INT | All | Limit to top N stocks by market cap |
| `--output` | PATH | stdout | Output file path (JSON/CSV) |
| `--format` | STRING | json | Output format: `json`, `csv`, `table` |

**Examples:**

```bash
# All sectors, last 30 days
python3 -m src.analytics sector-scores

# Technology sector only
python3 -m src.analytics sector-scores --sector "Technology"

# Specific industry
python3 -m src.analytics sector-scores --industry "Semiconductors"

# Top 100 stocks by market cap
python3 -m src.analytics sector-scores --top-n 100

# Export to CSV
python3 -m src.analytics sector-scores --output sector_scores.csv --format csv
```

#### `sector-trends` — Visualize Sector Trends Over Time

```bash
python3 -m src.analytics sector-trends [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 30 days ago | Start date |
| `--end` | DATE | Today | End date |
| `--sectors` | STRING | All | Comma-separated sector names |
| `--chart-type` | STRING | line | Chart type (see below) |
| `--output` | PATH | Required | Output file path (PNG/HTML) |
| `--width` | INT | 1200 | Chart width in pixels |
| `--height` | INT | 800 | Chart height in pixels |

**Chart Types:**

| Type | Description |
|------|-------------|
| `line` | Line chart of mean scores per sector |
| `heatmap` | Sector × Date heatmap of scores |
| `distribution` | Score distribution boxplots per sector |
| `stacked` | Stacked area of signal distribution |
| `comparison` | Side-by-side sector comparison |

**Examples:**

```bash
# Line chart of all sectors
python3 -m src.analytics sector-trends --output trends.png

# Heatmap for specific sectors
python3 -m src.analytics sector-trends \
  --sectors "Technology,Healthcare,Financial Services" \
  --chart-type heatmap \
  --output heatmap.png

# Score distribution
python3 -m src.analytics sector-trends \
  --chart-type distribution \
  --output boxplot.png
```

#### `sector-report` — Generate Comprehensive Report

```bash
python3 -m src.analytics sector-report [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 30 days ago | Start date |
| `--end` | DATE | Today | End date |
| `--output` | PATH | Required | Output directory |
| `--format` | STRING | html | Report format: `html`, `pdf`, `md` |

Generates a complete report with:
- Summary statistics per sector
- All chart types
- Top/bottom performing sectors
- Signal distribution changes
- Industry-level drill-down

---

## Visualization Approach

### Design Principles

1. **Publication Quality**: Clean, professional charts suitable for reports
2. **Consistent Styling**: Match Sigil brand colors (dark theme, navy/gold accents)
3. **Information Density**: Maximum insight per chart
4. **Accessibility**: Color-blind friendly palettes

### Color Palette

```python
SIGIL_COLORS = {
    "background": "#0D0D0F",      # Dark background
    "text": "#FFFFFF",            # White text
    "grid": "#2A2A2F",            # Subtle grid
    "buy": "#4ADE80",             # Green (BUY)
    "hold": "#FBBF24",            # Yellow (HOLD)
    "sell": "#F87171",            # Red (SELL)
    "primary": "#3B82F6",         # Blue accent
    "secondary": "#8B5CF6",       # Purple accent
    "sectors": [                  # 12-color palette for sectors
        "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
        "#8B5CF6", "#EC4899", "#14B8A6", "#F97316",
        "#6366F1", "#84CC16", "#06B6D4", "#A855F7"
    ]
}
```

### Chart Specifications

#### 1. Sector Score Line Chart
- **Purpose**: Track sector sentiment over time
- **X-axis**: Date
- **Y-axis**: Mean sector score (0-100)
- **Lines**: One per sector, distinct colors
- **Features**: Hover tooltips, legend, signal thresholds (70 BUY, 40 SELL)

#### 2. Sector Heatmap
- **Purpose**: Quick visual of all sectors × dates
- **Rows**: Sectors (sorted by current score)
- **Columns**: Dates
- **Color**: Score gradient (red → yellow → green)
- **Features**: Cell annotations, row/column averages

#### 3. Distribution Boxplots
- **Purpose**: Show score spread within sectors
- **X-axis**: Sectors
- **Y-axis**: Score (0-100)
- **Box**: 25th-75th percentile
- **Whiskers**: Min-max with outliers
- **Features**: Median line, individual stock dots

#### 4. Signal Distribution Stacked Area
- **Purpose**: Track BUY/HOLD/SELL mix over time
- **X-axis**: Date
- **Y-axis**: Percentage (0-100%)
- **Areas**: BUY (green), HOLD (yellow), SELL (red)
- **Features**: Per-sector view or aggregate

#### 5. Industry Treemap
- **Purpose**: Visualize relative size and score by sector/industry
- **Size**: Number of stocks (or market cap)
- **Color**: Mean score
- **Hierarchy**: Sector → Industry → Stock

---

## Implementation Plan

### Phase 1: Core Module (Day 1)

1. **Create analytics module structure**
   ```
   backend/src/analytics/
   ├── __init__.py
   ├── sector_analysis.py      # Core analysis logic
   ├── visualization.py        # Chart generation
   ├── imputation.py          # Missing data handling
   └── __main__.py            # CLI entry point
   ```

2. **Implement sector classification mapping**
   - Load stock universe
   - Build sector → industry → stocks index
   - Support filtering by sector/industry

3. **Implement score aggregation**
   - Load score history
   - Group by sector/industry and date
   - Calculate statistics (mean, median, std, percentiles)

### Phase 2: Missing Data Handling (Day 1)

1. **Detect missing scores**
   - For each date, identify stocks without scores
   
2. **Impute with sector average**
   - Calculate sector mean for that date
   - Fill missing scores with sector mean
   - Track imputation count for transparency

3. **Add imputation metadata**
   - Record which scores were imputed
   - Include imputation % in reports

### Phase 3: Visualization (Day 2)

1. **Set up matplotlib/plotly with Sigil theme**
   - Custom color palette
   - Font settings
   - Dark theme

2. **Implement chart generators**
   - Line chart
   - Heatmap
   - Boxplots
   - Stacked area
   - Treemap (optional)

3. **Add export functionality**
   - PNG (matplotlib)
   - HTML (plotly interactive)

### Phase 4: CLI & Documentation (Day 2)

1. **Build CLI with argparse**
   - Implement all commands
   - Add help text
   - Validate inputs

2. **Write tutorial documentation**
   - Feature overview
   - Step-by-step usage
   - Example outputs

3. **Add unit tests**
   - Test aggregation logic
   - Test imputation
   - Test chart generation

---

## Technical Specifications

### Dependencies

```python
# Add to requirements.txt
matplotlib>=3.8.0
plotly>=5.18.0
pandas>=2.0.0
seaborn>=0.13.0  # Optional: enhanced statistics plots
```

### Performance Considerations

| Operation | Target Time | Strategy |
|-----------|-------------|----------|
| Load score history | <1s | JSON streaming |
| Aggregate by sector | <2s | Pandas groupby |
| Generate chart | <3s | Matplotlib backend |
| Full report | <30s | Parallel chart generation |

### Error Handling

```python
# Validation
- Invalid date range → ValueError with clear message
- Unknown sector/industry → Warning + continue
- No data for period → Empty result with warning

# Missing data
- <50% coverage → Warning about reliability
- 0 stocks in sector → Skip sector in output
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_sector_analysis.py

def test_sector_classification_mapping():
    """Test stock → sector mapping."""
    
def test_score_aggregation_by_sector():
    """Test groupby and statistics calculation."""
    
def test_missing_score_imputation():
    """Test sector average imputation."""
    
def test_date_range_filtering():
    """Test start/end date filtering."""
    
def test_top_n_filtering():
    """Test market cap ranking."""
```

### Integration Tests

```python
# tests/integration/test_sector_cli.py

def test_sector_scores_command():
    """Test CLI sector-scores with real data."""
    
def test_sector_trends_output():
    """Test chart generation creates valid files."""
```

### Manual Verification

1. **Visual QA**: Review generated charts for accuracy
2. **Data Spot-Check**: Verify aggregations match manual calculations
3. **Edge Cases**: Test with minimal data, single sector, etc.

---

## Appendix: Sector Classification Reference

### Available Sectors (12)

| Sector | Stock Count | Industries |
|--------|-------------|------------|
| Technology | 126 | 12 |
| Financial Services | 134 | 14 |
| Industrials | 126 | 21 |
| Healthcare | 99 | 10 |
| Consumer Cyclical | 80 | 21 |
| Energy | 50 | 6 |
| Basic Materials | 48 | 12 |
| Consumer Defensive | 42 | 12 |
| Communication Services | 41 | 6 |
| Real Estate | 38 | 10 |
| Utilities | 36 | 6 |
| Unknown | 30 | 1 |

### Industry Examples (Technology Sector)

- Semiconductors (21 stocks)
- Software - Application (22 stocks)
- Software - Infrastructure (25 stocks)
- Information Technology Services (13 stocks)
- Communication Equipment (10 stocks)
- Computer Hardware
- Consumer Electronics
- Electronic Components
- Semiconductor Equipment & Materials
- Scientific & Technical Instruments
- Electronics & Computer Distribution
- Solar

---

**Related Documents:**
- `01_PRD.md` — Product requirements
- `04_ANALYTICS_PLAN.md` — Analytics instrumentation
- `06_BACKTESTING_SPEC.md` — Historical analysis patterns
- `how_tos/SECTOR_ANALYSIS_TUTORIAL.md` — Usage tutorial

