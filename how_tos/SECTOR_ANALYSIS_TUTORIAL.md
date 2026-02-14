<img src="../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Sector Performance Analysis Tutorial

**Feature:** REC-271 — Sector Performance Analysis  
**Last Updated:** February 14, 2026  
**Module Location:** `backend/src/analytics/`

---

## What Is Sector Analysis?

Sector Analysis answers these key questions:

> **"Which market sectors are Sigil's scoring model most bullish on?"**
> **"How has sector sentiment changed over time?"**
> **"Where are the rotation opportunities?"**

It aggregates individual stock scores by sector and industry, revealing market-level trends that aren't visible when looking at single stocks.

| Individual Stock Scores | Sector Analysis |
|------------------------|-----------------|
| "NVDA: 80 (BUY)" | "Technology: 49.2 avg, 28.6% SELL signals" |
| "AAPL: 65 (HOLD)" | "Energy: 59.2 avg, strongest sector" |
| One stock at a time | Market-wide view |

---

## Quick Start

```bash
# Navigate to backend
cd ~/Desktop/Cool_Apps/TradingApp_iOS/backend

# List all available sectors and industries
python3 -m src.analytics list-sectors

# Get current sector scores
python3 -m src.analytics sector-scores

# Generate a sector trend chart
python3 -m src.analytics sector-trends --output sector_trends.png

# Generate a full sector report with all charts
python3 -m src.analytics sector-report --output ./reports/sector_analysis/
```

---

## CLI Commands Reference

### `list-sectors` — Explore Available Sectors

Lists all sectors and their sub-industries with stock counts.

```bash
python3 -m src.analytics list-sectors
```

**Output:**
```
📊 AVAILABLE SECTORS & INDUSTRIES
============================================================

🏛️  Technology (126 stocks)
    └─ Semiconductors (21)
    └─ Software - Application (22)
    └─ Software - Infrastructure (25)
    └─ Information Technology Services (13)
    ...

🏛️  Financial Services (134 stocks)
    └─ Asset Management (20)
    └─ Banks - Diversified (16)
    └─ Banks - Regional (31)
    ...

📈 Total: 12 sectors, 131 industries
```

---

### `sector-scores` — Calculate Sector Scores

Calculates aggregated scores for each sector.

```bash
python3 -m src.analytics sector-scores [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--date` | DATE | Latest | Date to analyze (YYYY-MM-DD) |
| `--sector` | STRING | All | Filter by sector name |
| `--industry` | STRING | All | Filter by industry name |
| `--top-n` | INT | All | Limit to top N stocks by market cap |
| `--output` | PATH | stdout | Output file path |
| `--format` | STRING | table | Output format: `table`, `json`, `csv` |

**Examples:**

```bash
# All sectors for today (default)
python3 -m src.analytics sector-scores

# Specific sector detail
python3 -m src.analytics sector-scores --sector "Technology"

# Industry-level analysis
python3 -m src.analytics sector-scores --industry "Semiconductors"

# Top 100 stocks only (mega-caps)
python3 -m src.analytics sector-scores --top-n 100

# Export to CSV for further analysis
python3 -m src.analytics sector-scores --output sector_scores.csv --format csv

# Export to JSON
python3 -m src.analytics sector-scores --output sector_scores.json --format json
```

**Sample Output (table format):**
```
📊 SECTOR SCORES for 2026-02-14
================================================================================

Sector                       Score   Signal     BUY%    HOLD%    SELL%   Stocks
-------------------------------------------------------------------------------------
Energy                       59.2        🟡    20.0%    76.0%     4.0%      50
Industrials                  58.7        🟡    19.8%    72.2%     7.9%     126
Technology                   49.2        🟡    12.7%    58.7%    28.6%     126
Financial Services           43.7        🟡     2.2%    65.7%    32.1%     134
-------------------------------------------------------------------------------------
```

**Understanding the Output:**
- **Score**: Mean score across all stocks in the sector (0-100)
- **Signal**: Sector-level signal based on mean score (🟢 BUY ≥70, 🟡 HOLD 40-69, 🔴 SELL <40)
- **BUY/HOLD/SELL %**: Distribution of individual stock signals within the sector
- **Stocks**: Number of stocks in the sector

---

### `sector-trends` — Visualize Sector Trends

Generates publication-quality charts showing sector performance over time.

```bash
python3 -m src.analytics sector-trends [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 30 days ago | Start date (YYYY-MM-DD) |
| `--end` | DATE | Today | End date (YYYY-MM-DD) |
| `--sectors` | STRING | All | Comma-separated sector names |
| `--top-n` | INT | All | Limit to top N stocks by market cap |
| `--chart-type` | STRING | line | Chart type (see below) |
| `--output` | PATH | **Required** | Output file path (PNG or HTML) |
| `--width` | INT | 1200 | Chart width in pixels |
| `--height` | INT | 700 | Chart height in pixels |

**Chart Types:**

| Type | Description | Best For |
|------|-------------|----------|
| `line` | Line chart of mean scores | Trend comparison |
| `heatmap` | Sector × Date heatmap | Quick visual scan |
| `distribution` | Boxplots per sector | Score spread analysis |
| `stacked` | Stacked area of signals | Signal distribution over time |

**Examples:**

```bash
# Basic line chart (last 30 days)
python3 -m src.analytics sector-trends --output trends.png

# Line chart for specific sectors
python3 -m src.analytics sector-trends \
  --sectors "Technology,Healthcare,Energy" \
  --output tech_health_energy.png

# Heatmap for quick visual
python3 -m src.analytics sector-trends \
  --chart-type heatmap \
  --output sector_heatmap.png

# Score distribution boxplots
python3 -m src.analytics sector-trends \
  --chart-type distribution \
  --output score_distribution.png

# Signal distribution over time
python3 -m src.analytics sector-trends \
  --chart-type stacked \
  --output signal_trends.png

# Custom date range and size
python3 -m src.analytics sector-trends \
  --start 2026-01-01 \
  --end 2026-02-14 \
  --width 1600 \
  --height 900 \
  --output large_chart.png

# Interactive HTML chart (if plotly installed)
python3 -m src.analytics sector-trends \
  --output interactive_trends.html \
  --format html
```

---

### `sector-report` — Generate Comprehensive Report

Generates a complete sector analysis report with all chart types and summary data.

```bash
python3 -m src.analytics sector-report [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 30 days ago | Start date |
| `--end` | DATE | Today | End date |
| `--top-n` | INT | All | Limit to top N stocks |
| `--output` | PATH | **Required** | Output directory |

**Example:**

```bash
# Generate full report
python3 -m src.analytics sector-report --output ./reports/sector_analysis/

# Custom date range
python3 -m src.analytics sector-report \
  --start 2026-01-01 \
  --end 2026-02-14 \
  --output ./reports/jan_feb_analysis/
```

**Generated Files:**
```
./reports/sector_analysis/
├── sector_trends.png         # Line chart of sector scores
├── sector_heatmap.png        # Heatmap visualization
├── score_distribution.png    # Boxplot distribution
├── signal_distribution.png   # Stacked area of signals
├── sector_summary.json       # Summary data in JSON
├── sector_trends.html        # Interactive line chart (if plotly)
└── sector_heatmap.html       # Interactive heatmap (if plotly)
```

---

## Use Cases

### 1. Weekly Market Review

Every week, get a quick overview of sector sentiment:

```bash
# Quick summary
python3 -m src.analytics sector-scores

# Visual trends
python3 -m src.analytics sector-trends --output ~/Desktop/weekly_sectors.png
```

**What to look for:**
- Which sectors have the highest average scores?
- Any sectors with high % of BUY signals?
- Any sectors with high % of SELL signals (potential shorts or avoid)?

### 2. Sector Rotation Analysis

Identify sectors gaining or losing momentum:

```bash
# Generate 60-day heatmap
python3 -m src.analytics sector-trends \
  --start $(date -v-60d +%Y-%m-%d) \
  --chart-type heatmap \
  --output sector_rotation.png
```

**What to look for:**
- Color transitions from red→green = improving sentiment
- Color transitions from green→red = deteriorating sentiment
- Compare against economic cycles (e.g., Energy often leads in inflation)

### 3. Industry Deep Dive

Analyze specific industries within a sector:

```bash
# Get Technology sub-industries
python3 -m src.analytics sector-scores --sector "Technology"

# Focus on Semiconductors
python3 -m src.analytics sector-scores --industry "Semiconductors"
```

### 4. Mega-Cap Focus

Analyze only the largest stocks:

```bash
# Top 100 by market cap
python3 -m src.analytics sector-scores --top-n 100

# Trends for top 50
python3 -m src.analytics sector-trends --top-n 50 --output mega_caps.png
```

---

## Understanding the Visualizations

### Line Chart (`--chart-type line`)

Shows mean sector scores over time:
- **Y-axis**: Score (0-100)
- **Lines**: One per sector
- **Dashed lines**: BUY threshold (70) and SELL threshold (40)

**Interpretation:**
- Lines above 70 = bullish sectors
- Lines below 40 = bearish sectors
- Crossing thresholds = potential rotation signals

### Heatmap (`--chart-type heatmap`)

Color-coded matrix of sectors × dates:
- **Rows**: Sectors (sorted by current score)
- **Columns**: Dates
- **Colors**: Red (low) → Yellow (neutral) → Green (high)

**Interpretation:**
- Green rows = consistently bullish
- Red rows = consistently bearish
- Color changes = sentiment shifts

### Distribution (`--chart-type distribution`)

Boxplots showing score spread within each sector:
- **Box**: 25th-75th percentile
- **Line in box**: Median
- **Whiskers**: Min-max range

**Interpretation:**
- Tight boxes = consistent sentiment
- Wide boxes = mixed signals, higher uncertainty
- Outliers = individual stock divergence

### Stacked Area (`--chart-type stacked`)

Shows BUY/HOLD/SELL distribution over time:
- **Green area**: % of stocks with BUY signal
- **Yellow area**: % of stocks with HOLD signal
- **Red area**: % of stocks with SELL signal

**Interpretation:**
- Growing green = more bullish momentum
- Growing red = more bearish momentum
- Large yellow = market uncertainty

---

## Missing Data Handling

If a stock is missing a score for a particular date (e.g., new listing, data gap), the system automatically **imputes** with the sector average.

This ensures:
- No gaps in sector calculations
- Consistent stock counts across dates
- Transparent tracking (imputation count is shown)

**Imputation is noted in output:**
```
Coverage: 126 stocks (3 imputed)
```

**Confidence levels:**
- ≤5% imputed = HIGH confidence
- 6-15% imputed = MEDIUM confidence
- 16-30% imputed = LOW confidence
- >30% imputed = VERY LOW confidence (⚠️ warning shown)

---

## Data Sources

The sector analysis uses existing Sigil data:

| Data | File | Updated |
|------|------|---------|
| Stock Universe | `backend/data/stock_universe.json` | Pipeline run |
| Score History | `backend/data/score_history.json` | Pipeline run |

**Stock Universe includes:**
- 850 stocks (NASDAQ + NYSE, market cap > $10B)
- 12 sectors
- 131 industries
- Market cap for ranking

**Score History includes:**
- Up to 90 days of historical scores
- Per-stock daily scores
- All score components (fundamental, sentiment, technical, macro)

---

## Troubleshooting

### "No data for period"

The score history may not have data for your requested date range.

**Fix:** Check available dates:
```bash
python3 -c "
from src.analytics import SectorAnalyzer
a = SectorAnalyzer()
dates = a.get_available_dates()
print('Available dates:', dates[:5], '...', dates[-5:])
"
```

### "matplotlib required"

Charts require matplotlib to be installed.

**Fix:**
```bash
pip install matplotlib
```

For interactive HTML charts:
```bash
pip install plotly
```

### Low confidence warning

If you see "⚠️ X% of scores were imputed", it means significant data is missing.

**Possible causes:**
- Recent date range (not enough pipeline runs)
- Filtering to a small subset
- New stocks without history

**Fix:** Use a wider date range or fewer filters.

---

## API Usage (Advanced)

You can also use the analytics module programmatically:

```python
from src.analytics import SectorAnalyzer, get_sector_scores, get_sector_trends
from src.analytics import plot_sector_trends, SIGIL_COLORS

# Create analyzer
analyzer = SectorAnalyzer()

# Get latest sector summary
summary = analyzer.get_latest_sector_summary()
for sector in summary[:3]:
    print(f"{sector['sector']}: {sector['mean_score']:.1f} ({sector['signal']})")

# Get time series for a sector
trends = get_sector_trends(sector="Technology", start_date="2026-01-01")
for score in trends.scores[-3:]:
    print(f"{score.date}: {score.mean_score:.1f}")

# Generate custom chart
sector_data = analyzer.get_all_sector_trends()
plot_sector_trends(sector_data, "custom_chart.png", title="My Analysis")
```

---

## Related Documentation

- `docs/08_SECTOR_ANALYSIS_SPEC.md` — Full feature specification
- `docs/04_ANALYTICS_PLAN.md` — Analytics instrumentation
- `how_tos/BACKTESTING_TUTORIAL.md` — Historical backtesting

---

**Happy analyzing! 📊**
