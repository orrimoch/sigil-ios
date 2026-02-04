# UX/UI Review: Scores & Stock Detail

**Screens:** ScoresView, ScoresViewModel, StockDetailView, StockDetailViewModel  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: ScoresView (Score List)

### Current State
NavigationStack with searchable list, filter bar (signal chips + sector picker + sort menu), and stock rows showing ticker, score badge, rank, price, and change. Uses List with plain style.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Filter chips use Brand.primary (blue) for selection**
   - Current: `FilterChip` uses `.Brand.primary` as default active color, signal-specific colors for BUY/HOLD/SELL
   - Problem: "All" chip selected state = blue. Inconsistent with gold accent.
   - Recommended: "All" chip should use `.Accent.gold` when selected
   - File: `ScoresView.swift:68`

2. **[HIGH] Stock score row layout is cramped**
   - Current: Fixed `width: 100` for ticker/name, `width: 44` for score badge, `width: 40` for rank, `width: 80` for price
   - Problem: Company names get truncated. "Amazon.com Inc." becomes "Amazon.com..." 
   - Recommended: Use flexible widths. Score and rank can shrink. Let ticker/name expand.
   - File: `ScoresView.swift:128-158`

```swift
// Better layout
HStack(spacing: 8) {
    // Ticker and name — flexible
    VStack(alignment: .leading, spacing: 2) {
        Text(stock.ticker).font(.headline).foregroundColor(.Text.primary)
        Text(stock.name.isEmpty ? stock.sector : stock.name)
            .font(.caption).foregroundColor(.Text.secondary).lineLimit(1)
    }
    
    Spacer()
    
    // Score badge — fixed width
    Text("\(stock.score)")
        .font(.headline.monospacedDigit())
        .foregroundColor(.white)
        .frame(width: 44)
        .padding(.vertical, 6)
        .background(stock.signalColor)
        .cornerRadius(6)
    
    // Price and change — fixed width
    VStack(alignment: .trailing, spacing: 2) {
        Text(stock.formattedPrice)
            .font(.subheadline.monospacedDigit()).foregroundColor(.Text.primary)
        Text(stock.formattedChange)
            .font(.caption.monospacedDigit())
            .foregroundColor(stock.isPositive ? .Signal.positive : .Signal.negative)
    }
    .frame(width: 85, alignment: .trailing)
}
```

3. **[MEDIUM] Rank display is confusing**
   - Current: "#5" in `.caption` `.Text.tertiary` — visually lost
   - Recommended: Remove rank from the list row (it's implied by sort order). Show rank only in detail view.
   - File: `ScoresView.swift:144-147`

4. **[MEDIUM] "X stocks" count in filter bar is `.caption` `.Text.tertiary` — invisible**
   - Current: Tiny text at the end of the scrollable filter bar
   - Recommended: Move results count to a fixed position (e.g., right-aligned in the header area)
   - File: `ScoresView.swift:106-108`

#### Color & Theme

5. **[MEDIUM] List row background uses `.Background.primary` — no alternating rows**
   - Current: All rows have same background
   - Spec says: "Alternating rows: `#0D0D0D` / `#000000`"
   - Recommended: Add subtle alternating backgrounds
   - File: `ScoresView.swift:42`

```swift
.listRowBackground(
    index.isMultiple(of: 2) ? Color.Background.primary : Color.Background.secondary.opacity(0.5)
)
```

6. **[MEDIUM] Sort menu uses system Menu style — no dark theme styling**
   - Current: Default iOS `Menu` dropdown
   - Problem: May show with light background on some iOS versions. Should explicitly use dark color scheme.
   - File: `ScoresView.swift:89-101`

7. **[LOW] Sector picker sheet background inconsistency**
   - Current: `.scrollContentBackground(.hidden)` + `.background(Color.Background.primary)` — correct approach
   - But list rows use `.Background.secondary` while the navigation bar may default to system dark
   - File: `ScoresView.swift:177-200`

#### Interactions

8. **[HIGH] No swipe actions on stock rows**
   - Current: Tapping navigates to detail. No swipe gestures.
   - Recommended: Add swipe actions for Quick Buy, Add to Watchlist
   - File: `ScoresView.swift:38-44`

```swift
.swipeActions(edge: .trailing) {
    Button {
        // Quick trade
    } label: {
        Label("Trade", systemImage: "arrow.left.arrow.right")
    }
    .tint(.Signal.buy)
}
.swipeActions(edge: .leading) {
    Button {
        WatchlistService.shared.toggleWatchlist(stock.ticker)
    } label: {
        Label("Watch", systemImage: "bell")
    }
    .tint(.Accent.gold)
}
```

9. **[MEDIUM] Search placement is `.navigationBarDrawer(displayMode: .always)`**
   - Current: Search bar always visible, pushing content down
   - Recommended: Consider `.automatic` to let it collapse when scrolling down, saving vertical space
   - File: `ScoresView.swift:51`

10. **[MEDIUM] No haptic feedback on filter chip selection**
    - Current: Silent selection
    - Recommended: Light impact haptic on filter change
    - File: `ScoresView.swift:118`

11. **[LOW] Recent searches feature exists but isn't used in the current UI**
    - Current: `RecentSearchesView` is defined but never shown in ScoresView
    - Recommended: Show below search bar when search is active and text is empty
    - File: `ScoresView.swift:207-230`

#### Loading & Error States

12. **[MEDIUM] Loading state shows centered spinner with "Loading scores..." text**
    - Current: ProgressView + caption text
    - Recommended: Skeleton list with shimmer (matches spec requirement for skeleton loading)
    - File: `ScoresView.swift:25-30`

13. **[LOW] Empty state for "No stocks found" could have a clear-filters button**
    - Current: Magnifying glass icon + text
    - Recommended: Add "Clear Filters" button below
    - File: `ScoresView.swift:32-38`

---

## Screen: StockDetailView

### Current State
Scrollable detail view with: Price header, Price chart (Swift Charts), Score card, Score breakdown (collapsible), Score history chart, Key metrics grid, News sentiment badge, Buy/Sell buttons. Rich and data-dense.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Price header has no card background — floats awkwardly**
   - Current: PriceHeader is just a VStack with padding, no background card
   - Problem: The price is the most important data point but has no visual container. It blends with the scroll background.
   - Recommended: Wrap in a card with `.Background.secondary` background
   - File: `StockDetailView.swift:64-87`

2. **[HIGH] Score display uses 48pt monospaced for the score — too large**
   - Current: `.system(size: 48, weight: .bold, design: .monospaced)` for the score number
   - Problem: A number from 0-100 doesn't need 48pt. The price header is already using `monoLarge` (32pt). The score shouldn't be larger than the price.
   - Recommended: 36pt for score, 32pt for price, maintaining proper hierarchy
   - File: `StockDetailView.swift:100-103`

3. **[HIGH] Buy/Sell buttons at bottom use PrimaryButtonStyle and SecondaryButtonStyle — blue**
   - Current: Buy = `PrimaryButtonStyle` (blue bg), Sell = `SecondaryButtonStyle` (blue outline)
   - Recommended: Buy = green background (`.Signal.buy`), Sell = red outline (`.Signal.sell`)
   - File: `StockDetailView.swift:55-59`

```swift
// Proper Buy/Sell button styling
HStack(spacing: 16) {
    Button("Buy") {
        showTradeSheet = true
    }
    .font(.headline)
    .foregroundColor(.white)
    .frame(maxWidth: .infinity)
    .padding(.vertical, 16)
    .background(Color.Signal.buy)
    .cornerRadius(12)
    
    Button("Sell") {
        showTradeSheet = true
    }
    .font(.headline)
    .foregroundColor(.Signal.sell)
    .frame(maxWidth: .infinity)
    .padding(.vertical, 16)
    .background(Color.clear)
    .cornerRadius(12)
    .overlay(
        RoundedRectangle(cornerRadius: 12)
            .stroke(Color.Signal.sell, lineWidth: 2)
    )
}
```

4. **[MEDIUM] Period selector buttons lack active state styling**
   - Current: Active period has `.Brand.primary` text and `.Background.surface` background
   - Recommended: Gold text for active period, subtle gold tint on background
   - File: `StockDetailView.swift:152-160`

#### Charts

5. **[HIGH] Price chart line uses `.Brand.primary` (blue) — fine for Bloomberg aesthetic but conflicts with gold system**
   - Current: `LineMark.foregroundStyle(Color.Brand.primary)` = blue
   - The chart line being blue while the rest of the app should be gold creates visual dissonance
   - Recommended: If keeping blue for charts (Bloomberg-style), explicitly document this as intentional. Otherwise, use `.Accent.gold`.
   - File: `StockDetailView.swift:95-96`

6. **[MEDIUM] Chart Y-axis on leading side — standard is trailing for financial charts**
   - Current: `.chartYAxis { AxisMarks(position: .leading) }` — price axis on left
   - Financial convention: Price axis on the right
   - Recommended: `.chartYAxis { AxisMarks(position: .trailing) }`
   - File: `StockDetailView.swift:112-114`

7. **[MEDIUM] Score history chart threshold lines lack labels**
   - Current: Dashed lines at 70 and 40 but no text labels
   - Recommended: Add "BUY" and "SELL" text annotations at the threshold lines
   - File: `StockDetailView.swift:258-263`

8. **[MEDIUM] Price chart has no touch-to-inspect interaction**
   - Current: Static chart, no crosshair or point selection
   - Recommended: Add `chartOverlay` with drag gesture to show data point details
   - File: `StockDetailView.swift:91-115`

```swift
.chartOverlay { proxy in
    GeometryReader { geo in
        Rectangle()
            .fill(Color.clear)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        let x = value.location.x - geo[proxy.plotAreaFrame].origin.x
                        guard let date: Date = proxy.value(atX: x) else { return }
                        // Find closest data point and show tooltip
                    }
            )
    }
}
```

#### Score Breakdown

9. **[MEDIUM] Score component bars use GeometryReader for progress — can cause layout issues**
    - Current: Each `ScoreComponentBar` uses a GeometryReader for the progress bar
    - Problem: GeometryReader inside a VStack can cause unexpected sizing. Use `ProgressView` or Gauge instead.
    - File: `StockDetailView.swift:218-227`

10. **[LOW] Explanation icon uses `.Brand.accent` — but that's different from both `.Brand.primary` and `.Accent.gold`**
    - Current: `Image(systemName: "lightbulb.fill").foregroundColor(.Brand.accent)` = `#FFB800`
    - This is actually the gold color! But it's stored as `Brand.accent` instead of `Accent.gold`
    - Shows the naming confusion in the theme system
    - File: `StockDetailView.swift:207`

#### Trade Entry Sheet

11. **[HIGH] Sheet uses default system segmented picker for Buy/Sell**
    - Current: `Picker("", selection: $isBuy) { Text("Buy"), Text("Sell") }.pickerStyle(.segmented)`
    - Problem: System segmented control doesn't use signal colors. Buy should be green-tinted, Sell red-tinted.
    - File: `StockDetailView.swift:300`

12. **[MEDIUM] Quantity input is just a TextField with 48pt mono — no stepper, no quick buttons**
    - Current: Raw text field for quantity
    - Recommended: Add preset buttons (+1, +5, +10, +100) and a stepper
    - File: `StockDetailView.swift:315-320`

13. **[MEDIUM] Missing "Not financial advice" disclosure**
    - Design spec says: "Not financial advice visible at trade confirmation"
    - Current: No such disclosure on the trade entry sheet
    - File: `StockDetailView.swift:288-363`

14. **[LOW] Success alert uses system `.alert` — not styled to match dark theme**
    - Current: `Alert("Order Submitted!")` — default system styling
    - Recommended: Use a custom in-app success banner with gold accent
    - File: `StockDetailView.swift:351-354`

#### Key Metrics

15. **[LOW] Key metrics grid has inconsistent tile count**
    - Current: 5 fixed metrics + N dynamic metrics from API in a 2-column grid
    - Problem: Odd number of tiles creates a hanging last tile
    - Recommended: Always show an even number of metrics, or use a different layout for the remainder
    - File: `StockDetailView.swift:272-285`

### Accessibility Issues

- **[CRITICAL]** Price chart has zero accessibility. VoiceOver users hear nothing about price trends. Need `accessibilityLabel("Price chart showing 3-month trend, currently at $185.42")`
- **[HIGH]** Score breakdown bars have no accessibility values. Should use `accessibilityValue("Fundamental score: 80 out of 100, weight 35 percent")`
- **[HIGH]** Buy/Sell buttons in the bottom area need `accessibilityHint` explaining paper vs live mode
- **[MEDIUM]** Watchlist toggle bell icon needs `accessibilityLabel("Add to watchlist")` or `("Remove from watchlist")`
- **[MEDIUM]** Score history chart inaccessible to VoiceOver
