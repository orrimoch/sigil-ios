# UX/UI Review: Portfolio Screen

**Screen:** PortfolioView + PortfolioViewModel  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: PortfolioView

### Current State
Navigation stack with: paper mode indicator, portfolio summary card, cash/invested stat cards, segmented picker (Holdings / Chart / Sectors), holdings list, performance chart, sector allocation pie chart, and a paper portfolio reset button.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Portfolio value uses 36pt monospaced bold — good, but inconsistent with HomeView**
   - Current: `.system(size: 36, weight: .bold, design: .monospaced)` in PortfolioDetailSummaryCard
   - HomeView uses `.monoLarge` which is 32pt. Two different sizes for the same data type.
   - Recommended: Use the same font size across both. 32pt (`.monoLarge`) is sufficient.
   - File: `PortfolioView.swift:65`

2. **[HIGH] Daily P&L badge uses capsule shape with 20pt corner radius**
   - Current: Color pill with P&L text inside — `.cornerRadius(20)`
   - Problem: This is a different pattern from the HomeView P&L which uses inline text with no badge
   - Recommended: Pick one pattern and use it consistently
   - File: `PortfolioView.swift:74-82`

3. **[MEDIUM] "PAPER PORTFOLIO" indicator duplicates the one in TradeView**
   - Current: Same amber pill badge
   - Problem: The user already knows it's paper mode from the Trade screen
   - Recommended: Integrate into the navigation bar title or use a more subtle indicator
   - File: `PortfolioView.swift:34-41`

4. **[MEDIUM] Cash and Invested stat cards are too equal in visual weight**
   - Current: Two identical cards side by side
   - Recommended: Merge into a single card with a bar showing the cash/invested split
   - File: `PortfolioView.swift:45-52`

```swift
// Cash/Invested split bar
VStack(alignment: .leading, spacing: 8) {
    HStack {
        Text("Cash")
            .font(.caption).foregroundColor(.Text.secondary)
        Spacer()
        Text("Invested")
            .font(.caption).foregroundColor(.Text.secondary)
    }
    
    GeometryReader { geo in
        let investedRatio = viewModel.positionsValue / max(viewModel.totalValue, 1)
        HStack(spacing: 2) {
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.Accent.gold)
                .frame(width: geo.size.width * investedRatio)
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.Background.tertiary)
        }
    }
    .frame(height: 8)
    
    HStack {
        Text(viewModel.cash.asCurrency)
            .font(.subheadline.monospacedDigit())
        Spacer()
        Text(viewModel.positionsValue.asCurrency)
            .font(.subheadline.monospacedDigit())
    }
    .foregroundColor(.Text.primary)
}
.padding()
.background(Color.Background.secondary)
.cornerRadius(12)
```

5. **[MEDIUM] Segmented picker uses system style — not dark-themed**
   - Current: Default iOS segmented control
   - Problem: System segmented control may not look consistent with the dark theme
   - Recommended: Custom segmented control matching the app design
   - File: `PortfolioView.swift:55-59`

#### Holdings Section

6. **[HIGH] Holdings lack NavigationLink to stock detail**
   - Current: Holdings are static rows with no tap action
   - Recommended: Each holding should navigate to the stock detail view for that ticker
   - File: `PortfolioView.swift:113-130`

```swift
ForEach(holdings) { holding in
    NavigationLink {
        StockDetailView(ticker: holding.ticker)
    } label: {
        HoldingRow(holding: holding)
    }
}
```

7. **[MEDIUM] Holdings don't show current price or shares cost basis**
   - Current: Shows ticker, shares count, market value, unrealized P&L
   - Missing: Current price per share, average cost basis, weight in portfolio
   - Recommended: Add at least current price and portfolio weight percentage
   - File: `PortfolioView.swift:139-156`

8. **[MEDIUM] No sorting options for holdings**
   - Current: Holdings displayed in whatever order the API returns
   - Recommended: Sort by P&L (biggest winners/losers), value, ticker, or recent trade
   - File: `PortfolioView.swift:113`

9. **[LOW] Holdings separator uses `.Border.primary` while other screens use `.Utility.divider`**
   - Current: `Divider().background(Color.Border.primary)` 
   - Other screens: `Divider().background(Color.Utility.divider)`
   - File: `PortfolioView.swift:126`

#### Performance Chart

10. **[HIGH] Chart line uses `.Accent.gold` — inconsistent with HomeView/ScoresView charts using `.Brand.primary` (blue)**
    - Current: Portfolio chart = gold, price charts = blue
    - Problem: Charts should use a consistent color language
    - Recommended: All charts use the same primary line color. Gold for portfolio performance (your money) and blue for market prices (market data) could work if explicitly documented as intentional differentiation.
    - File: `PortfolioView.swift:207,214`

11. **[MEDIUM] Chart lacks touch-to-inspect interaction**
    - Current: Static chart, no crosshair or data point selection
    - Recommended: Add drag gesture to inspect values at specific dates
    - File: `PortfolioView.swift:200-222`

12. **[MEDIUM] Performance period picker uses system Menu picker**
    - Current: `Picker("Period", selection: ...).pickerStyle(.menu)`
    - Recommended: Horizontal chip selector matching the filter bar pattern from ScoresView
    - File: `PortfolioView.swift:178`

13. **[LOW] Chart empty state says "History builds as you trade" — passive**
    - Current: Generic empty message
    - Recommended: Add a CTA: "Start trading to see your performance"
    - File: `PortfolioView.swift:195-198`

#### Sector Allocation

14. **[MEDIUM] Sector colors are hardcoded, not from Theme**
    - Current: `sectorColors` dictionary with system colors like `.blue`, `.green`, `.purple`
    - Problem: System colors may clash with the dark theme. `.yellow` on dark is fine, but `.brown` is hard to see.
    - Recommended: Define sector colors in Theme.swift using custom hex values optimized for dark backgrounds
    - File: `PortfolioView.swift:233-245`

```swift
// Theme-optimized sector colors
static let sectorColors: [String: Color] = [
    "Technology": Color(hex: "0A84FF"),      // Bright blue
    "Healthcare": Color(hex: "30D158"),      // Bright green
    "Financials": Color(hex: "BF5AF2"),      // Bright purple
    "Consumer Cyclical": Color(hex: "FF9F0A"), // Bright orange
    "Energy": Color(hex: "FF453A"),          // Bright red
    "Industrials": Color(hex: "8E8E93"),     // Gray
    // etc.
]
```

15. **[MEDIUM] Pie chart uses SectorMark (iOS 17+) — good, but annotation text is too small**
    - Current: `.caption2.bold()` for percentage in the pie slice
    - Problem: Very hard to read, especially for small slices
    - Recommended: Only show annotation for slices >15%, use legend for smaller ones
    - File: `PortfolioView.swift:254-261`

16. **[LOW] Pie chart inner radius of 0.5 creates a donut — good for readability**
    - Current: `innerRadius: .ratio(0.5)` ✅
    - Minor: Could use the center space to show total portfolio value
    - File: `PortfolioView.swift:251`

#### Paper Portfolio Reset

17. **[MEDIUM] Reset button at the bottom is too easy to accidentally tap**
    - Current: Full-width red-tinted button at the very bottom of the scroll
    - Problem: Users scrolling might accidentally hit it (though there's a confirmation alert)
    - Recommended: Move to Settings only, or make it smaller and more tucked away
    - File: `PortfolioView.swift:62-71`

#### Error State

18. **[MEDIUM] Error state is placed inside a Group with awkward indentation**
    - Current: The error/content conditional creates deeply nested code
    - Recommended: Extract to a computed property for readability
    - File: `PortfolioView.swift:19-26`

### Accessibility Issues

- **[CRITICAL]** Pie chart has zero accessibility. VoiceOver users get nothing. Need `accessibilityLabel("Sector allocation: Technology 45%, Healthcare 30%...")`
- **[HIGH]** Performance chart is inaccessible — need trend description
- **[HIGH]** Total P&L badge should combine all values into one VoiceOver element: "Daily loss $500, down 0.5 percent"
- **[MEDIUM]** Holdings rows need `accessibilityElement(children: .combine)` to read as complete units
- **[LOW]** Reset button needs `accessibilityHint("Resets paper portfolio to $100,000")`
