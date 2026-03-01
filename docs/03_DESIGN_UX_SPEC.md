<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil iOS — Design & UX Specification

**Project:** iOS Stock Trading App with AI-Powered Recommendations  
**Author:** Blaze Neon  
**Date:** February 2, 2026  
**Version:** 1.0  

---

## Table of Contents

1. [Target User](#target-user)
2. [Design Philosophy](#design-philosophy)
3. [Design Principles](#design-principles)
4. [Visual Design System](#visual-design-system)
5. [Key Screens](#key-screens)
6. [Onboarding Flow](#onboarding-flow)
7. [Interaction Patterns](#interaction-patterns)
8. [Accessibility](#accessibility)
9. [Design Standards](#design-standards)

---

## Target User

### The Busy Builder

Our ideal user is a high-tech professional, 30-40 years old, navigating the demands of a hectic career while wanting their wealth to grow intelligently in the background. They're sophisticated enough to understand markets but too busy (and too smart) to day-trade. They appreciate elegant design, data-driven decisions, and tools that respect their time.

**Key Characteristics:**

- High-tech professional (engineer, PM, founder)
- Age 30-40
- Investable assets: $25K-$500K
- Time available: 5-10 minutes per week
- Sophistication: Understands markets, P/E ratios, basic technicals

**What They Want:**

- Set intelligent parameters, let money work for them
- No babysitting required
- Respect for their intelligence
- Professional, trustworthy aesthetic

---

## Design Philosophy

### "Institutional Trust for the Busy Builder"

Every pixel serves the time-constrained professional. The app should feel like a Bloomberg terminal distilled for mobile — sophisticated enough to earn respect, efficient enough to use in 30 seconds between meetings. No learning curve, no clutter, no wasted taps.

> 🎯 **Design North Star:** If a feature takes more than 3 taps or 10 seconds to understand, redesign it.

### Daily Inspiration

Each app launch displays a rotating motivational quote:

**Example Quotes:**

- *"The stock market is a device for transferring money from the impatient to the patient."* — Warren Buffett
- *"The best move is the one you want to make."* — Bobby Fischer
- *"Simplicity is the ultimate sophistication."* — Leonardo da Vinci
- *"In the middle of difficulty lies opportunity."* — Albert Einstein
- *"Risk comes from not knowing what you're doing."* — Warren Buffett

**Implementation:** 50+ quotes in app bundle, random on launch, subtle typography below header.

---

## Brand Identity & Logo

### The Sigil Mark

<img src="sigil_logo.jpg" alt="Sigil Logo" width="450" />

The Sigil brand identity centers on a hexagonal mark featuring:

- **Hexagonal shape** — Stability, structure, and the interconnected nature of financial markets
- **Circuit-board traces** — Technology, data processing, and algorithmic analysis
- **Upward arrow** — Growth, momentum, and positive returns
- **Navy blue palette** — Trust, professionalism, and depth

### Logo Usage

| Context           | Asset             | Description                                             |
| ----------------- | ----------------- | ------------------------------------------------------- |
| **App Icon**      | Hexagon mark only | Standalone hex on dark background (#0D0D0F)             |
| **Splash Screen** | Full logo         | Hexagon + "Sigil" wordmark, centered on dark background |
| **In-App Header** | Full logo or mark | Scaled proportionally, minimum 24pt height              |
| **Documentation** | Full logo         | With adequate clear space around mark                   |

### Color System

| Token                | Hex       | Usage                                   |
| -------------------- | --------- | --------------------------------------- |
| `background-primary` | `#0D0D0F` | App background, icon background         |
| `brand-blue`         | `#1E3A5F` | Hexagon fill, circuit traces            |
| `brand-accent`       | `#3A7AFF` | Arrow, highlights, interactive elements |
| `text-primary`       | `#FFFFFF` | Primary text on dark backgrounds        |

### Launch Screen

The app launches with a 2-second splash screen:

1. Dark background (#0D0D0F) fades in
2. Full Sigil logo (mark + wordmark) scales up with easeOut animation
3. After 2s, fades out and transitions to the main app
4. Implemented in `LaunchView.swift`

---

## Design Principles

*Every principle flows from serving the Busy Builder.*

| #   | Principle                    | Description                                                             |
| --- | ---------------------------- | ----------------------------------------------------------------------- |
| 1   | **Respect Their Time**       | Glanceable dashboards, instant insights. 30 seconds, not 30 minutes.    |
| 2   | **Accuracy First**           | Numbers are sacred. Right-aligned, monospaced, properly formatted.      |
| 3   | **Sophisticated Simplicity** | High information density without cognitive overload.                    |
| 4   | **Zero Learning Curve**      | Intuitive from first launch. They'll delete before watching a tutorial. |
| 5   | **Dark Mode**                | Non-negotiable. Reduces eye strain, signals professionalism.            |
| 6   | **Confidence-Building**      | Solid, responsive, trustworthy. Subtle haptics, instant feedback.       |
| 7   | **Let Them Forget**          | Set up once, check weekly. Push insights to them.                       |

> 📋 **Validation Checkpoint:** For every design decision, ask: *"Does this respect the Busy Builder's time and intelligence?"*

---

## Visual Design System

### Design References

| Reference                      | What to Learn                                 |
| ------------------------------ | --------------------------------------------- |
| **Bloomberg Terminal**         | Information density, color coding, typography |
| **Interactive Brokers TWS**    | Data tables, order entry, professional charts |
| **Apple Stocks**               | Native iOS patterns, clean dark mode          |
| **Fidelity Active Trader Pro** | Clean layouts, watchlists                     |

---

### Color Palette — "Institutional Dark"

#### Core Colors

| Role          | Hex       | Usage                    |
| ------------- | --------- | ------------------------ |
| Background    | `#000000` | Main background          |
| Surface       | `#0D0D0D` | Cards, elevated surfaces |
| Surface 2     | `#161616` | Modals, input fields     |
| Border        | `#222222` | Dividers, table borders  |
| Border Active | `#333333` | Focus states             |

#### Semantic Colors

| Role           | Hex       | Usage                            |
| -------------- | --------- | -------------------------------- |
| Gain/Positive  | `#00C853` | Price up, profits, buy signals   |
| Loss/Negative  | `#FF1744` | Price down, losses, sell signals |
| Neutral        | `#9E9E9E` | Unchanged, hold                  |
| Primary Action | `#2196F3` | Buttons, links, CTAs             |
| Warning        | `#FFC107` | Alerts, caution                  |
| Info           | `#03A9F4` | Informational                    |

#### Text Colors

| Role           | Hex       | Usage                |
| -------------- | --------- | -------------------- |
| Text Primary   | `#FFFFFF` | Headlines, prices    |
| Text Secondary | `#B0B0B0` | Labels, descriptions |
| Text Muted     | `#707070` | Timestamps, hints    |
| Text Disabled  | `#404040` | Disabled states      |

#### Score Colors

| Range  | Color     | Signal |
| ------ | --------- | ------ |
| 70-100 | `#00C853` | BUY    |
| 40-69  | `#9E9E9E` | HOLD   |
| 0-39   | `#FF1744` | SELL   |

---

### Typography

#### Font Stack

| Purpose      | Font           | Fallback      |
| ------------ | -------------- | ------------- |
| UI Text      | SF Pro Text    | -apple-system |
| Numbers/Data | SF Mono        | Menlo, Monaco |
| Headlines    | SF Pro Display | -apple-system |

#### Type Scale

| Style        | Font           | Size | Weight   | Usage           |
| ------------ | -------------- | ---- | -------- | --------------- |
| Large Value  | SF Mono        | 32pt | Semibold | Portfolio total |
| Price        | SF Mono        | 18pt | Medium   | Stock prices    |
| Table Header | SF Pro         | 12pt | Semibold | Column headers  |
| Table Data   | SF Mono        | 14pt | Regular  | Table cells     |
| Title        | SF Pro Display | 20pt | Semibold | Screen titles   |
| Body         | SF Pro         | 15pt | Regular  | Descriptions    |
| Caption      | SF Pro         | 12pt | Regular  | Timestamps      |

#### Number Formatting

```
Prices:      $185.42      (2 decimals, right-aligned)
Large:       $1,234,567   (comma separators)
Percent:     +2.34%       (sign always shown)
Volume:      1.2M         (abbreviated)
Dates:       Feb 2, 2026  (readable)
Times:       09:30 ET     (with timezone)
```

---

### Data Tables

#### Watchlist Style

```
┌──────────────────────────────────────────────────────────────────┐
│ SYMBOL │    LAST │   CHG │    CHG% │    VOL   │
├──────────────────────────────────────────────────────────────────┤
│ AAPL   │  185.42 │ +4.21 │  +2.33% │   45.2M  │  ← Green
│ MSFT   │  378.91 │ +6.72 │  +1.81% │   22.1M  │  ← Green
│ GOOGL  │  141.80 │ -0.92 │  -0.64% │   18.7M  │  ← Red
└──────────────────────────────────────────────────────────────────┘
```

**Specs:**

- Headers: `#707070`, 12pt, uppercase
- Numbers: SF Mono, 14pt, right-aligned
- Row hover: `#161616`
- Alternating rows: `#0D0D0D` / `#000000`

#### Score Table

```
┌────────────────────────────────────────────────────────────────┐
│ SYMBOL │ SCORE │ SIGNAL │ FUND │ SENT │ MACRO │ TECH │
├────────────────────────────────────────────────────────────────┤
│ AAPL   │    85 │ BUY    │   82 │   90 │    75 │   80 │
│ GOOGL  │    61 │ HOLD   │   65 │   58 │    62 │   60 │
│ AMZN   │    35 │ SELL   │   42 │   38 │    30 │   32 │
└────────────────────────────────────────────────────────────────┘
```

---

### Charts

#### Candlestick Chart

- Background: `#000000`
- Grid: `#1A1A1A` (subtle)
- Axis labels: `#707070`, SF Mono 11pt
- Green candles: `#00C853`
- Red candles: `#FF1744`
- Volume bars: `#2196F3` at 50% opacity

#### Score Gauge

```
        ┌─────────────────┐
        │       85        │   ← Large SF Mono
        │     ───────     │   ← Horizontal progress bar
        │      BUY        │   ← Signal in green
        └─────────────────┘
```

- Track: `#222222`
- Fill: Gradient red → amber → green
- No circular gauges — horizontal bar is cleaner

---

## Key Screens

> 📱 **Screen Design Principle:** Every screen answers one question.
> 
> - Home = "How's my portfolio?"
> - Scores = "What should I buy/sell?"
> - Trade = "Execute."

### Home Dashboard

```
┌────────────────────────────────────────────────────────────────┐
│  Portfolio                                           9:41 AM   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Total Value                                                   │
│  $124,532.18                                                   │
│  +$1,234.56 (+1.00%) today                                     │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  MARKETS                                                       │
│  ┌────────────┬────────────┬────────────┬────────────┐        │
│  │ S&P 500    │ NASDAQ     │ DOW        │ VIX        │        │
│  │ 4,892.45   │ 15,234.12  │ 38,456.78  │ 15.23      │        │
│  │ +0.52%     │ +0.78%     │ +0.31%     │ -2.15%     │        │
│  └────────────┴────────────┴────────────┴────────────┘        │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  TOP AI PICKS                                          See All │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ AAPL │  85 │ BUY  │  185.42 │ +2.33% │ Technology     │   │
│  │ MSFT │  82 │ BUY  │  378.91 │ +1.81% │ Technology     │   │
│  │ NVDA │  78 │ BUY  │  682.35 │ -1.22% │ Technology     │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│    Home      Scores      Trade      Portfolio    Settings     │
└────────────────────────────────────────────────────────────────┘
```

### Stock Detail

```
┌────────────────────────────────────────────────────────────────┐
│  ←  AAPL                                             ★    ⋮   │
├────────────────────────────────────────────────────────────────┤
│  Apple Inc.                                                    │
│  $185.42  +$4.21 (+2.33%)                                     │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              [Price Chart - 1D view]                     │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│  │  1D    5D    1M    3M    6M    1Y    MAX                 │ │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  AI SCORE                                                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Score: 85  │  Signal: BUY  │  Rank: #12 of 400         │ │
│  │                                                          │ │
│  │  Fundamental:  88  ████████████████░░░░                 │ │
│  │  Sentiment:    82  ████████████████░░░░                 │ │
│  │  Macro:        75  ███████████████░░░░░                 │ │
│  │  Technical:    80  ████████████████░░░░                 │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                    [ BUY ]                              │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Score Breakdown (Explainability)

```
┌────────────────────────────────────────────────────────────────┐
│  AAPL Score: 85                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  FUNDAMENTALS (35%)                            Score: 88      │
│  ├─ Value:    72  (P/E slightly high vs sector)               │
│  ├─ Quality:  95  (Strong margins, low debt)                  │
│  └─ Growth:   91  (Revenue +12% YoY, EPS beat)                │
│                                                                │
│  SENTIMENT (25%)                               Score: 82      │
│  ├─ News:     85  (Positive iPhone coverage)                  │
│  ├─ Earnings: 78  (Call tone: confident)                      │
│  └─ Social:   80  (Retail bullish)                            │
│                                                                │
│  MACRO (20%)                                   Score: 75      │
│  └─ Tech sector neutral in current rate environment           │
│                                                                │
│  TECHNICAL (20%)                               Score: 90      │
│  ├─ Momentum: 92  (Above all MAs)                             │
│  ├─ RSI:      65  (Strong but not overbought)                 │
│  └─ Trend:    88  (Higher highs, higher lows)                 │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  📝 SUMMARY                                                    │
│  "Strong buy driven by excellent fundamentals and momentum.    │
│   Slight valuation concern but offset by quality metrics.      │
│   Watch for Fed policy impact on tech sector."                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Onboarding Flow

> **Goal:** Productive within 60 seconds. Respect their intelligence.

### Design Philosophy

- Skip button always visible
- No forced carousels
- Get them to value fast
- No patronizing tutorials

### Flow (4 Screens)

**Screen 1: Welcome**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                     [ Skip → ]  │
│                                                                 │
│              Your Portfolio, On Autopilot.                     │
│                                                                 │
│    We rank S&P 500 stocks weekly using fundamentals,           │
│    momentum, and sentiment. You decide. We execute.            │
│                                                                 │
│    ⏱️ 5 minutes/week. That's it.                                │
│                                                                 │
│                    [ Let's Go ]                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Screen 2: Score System**

```
┌─────────────────────────────────────────────────────────────────┐
│  THE SCORE SYSTEM                                  [ Skip → ]  │
│                                                                 │
│    Every stock gets a score (0-100) updated weekly.            │
│                                                                 │
│    🟢 70+    Strong Buy                                         │
│    🟡 40-70  Hold                                               │
│    🔴 <40   Sell                                                │
│                                                                 │
│    Scores combine:                                              │
│    35% Fundamentals · 25% Sentiment · 20% Macro · 20% Technical│
│                                                                 │
│                    [ Got It ]                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Screen 3: Portfolio Size**

```
┌─────────────────────────────────────────────────────────────────┐
│  PORTFOLIO SIZE                                    [ Skip → ]  │
│                                                                 │
│    How much are you investing?                                  │
│                                                                 │
│    [ < $25K ]  [ $25K-100K ]  [ $100K+ ]                       │
│                                                                 │
│    Based on your selection:                                     │
│    • Recommended positions: 8-12 stocks                        │
│    • Max per stock: 10%                                        │
│    • Min 3 sectors                                             │
│                                                                 │
│                    [ Continue ]                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Screen 4: Ready**

```
┌─────────────────────────────────────────────────────────────────┐
│  YOU'RE SET                                                     │
│                                                                 │
│    ✓ Paper trading enabled                                     │
│    ✓ Weekly notifications ON (Sundays)                         │
│    ✓ Top 10 picks ready                                        │
│                                                                 │
│    💡 Pro tip: Check in Sundays after market close.            │
│                                                                 │
│                  [ Show Me the Scores ]                         │
└─────────────────────────────────────────────────────────────────┘
```

### First-Time Tooltips

| Screen       | Tooltip                                       |
| ------------ | --------------------------------------------- |
| Score List   | "Tap any stock to see details"                |
| Score Detail | "Scroll down to see what's driving the score" |
| Trade Button | "Start with paper trading to practice"        |
| Portfolio    | "This shows your positions and P&L"           |

---

## Interaction Patterns

### Haptics

| Action          | Feedback             |
| --------------- | -------------------- |
| Tap button      | Light impact         |
| Pull to refresh | Medium impact        |
| Trade executed  | Success notification |
| Error           | Error notification   |

### Transitions

- Screen push: 300ms ease-out
- Modal present: 250ms spring
- Pull to refresh: Native iOS behavior

### Loading States

- Skeleton screens for data loading
- Shimmer animation on placeholders
- Never show empty screens

---

## Accessibility

### Requirements

- VoiceOver full support
- Dynamic Type support (up to xxxLarge)
- Minimum touch target: 44×44pt
- Color contrast: WCAG 2.1 AA minimum
- Reduce Motion support

### Color Independence

- Never rely on color alone
- Use icons + color for signals
- BUY = 🟢 + "BUY" text
- SELL = 🔴 + "SELL" text

---

## Design Standards

### Apple HIG Compliance

- Native iOS navigation patterns
- SF Symbols for icons
- Standard gestures (swipe, pull-to-refresh)

### Financial Industry Standards

- Green = positive, Red = negative
- Right-aligned numbers
- Monospace for financial data

### Disclosures

- "Not financial advice" visible at trade confirmation
- Risk acknowledgment in onboarding
- Clear paper vs live mode indicator

---

**Related Docs:**

- `01_PRD.md` — Product requirements, vision, user flows
- `02_TECHNICAL_SPEC.md` — Architecture, APIs, data models
- `04_ANALYTICS_PLAN.md` — Metrics, events, dashboards
- `05_FEATURE_SPEC.md` — All 45 features with acceptance criteria
