# UX/UI Review: Home Dashboard

**Screens:** HomeView + HomeViewModel  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: HomeView (Dashboard)

### Current State
Scrollable dashboard with: Daily Quote card, Portfolio Summary card, Market Overview (2x2 grid), Top AI Picks list, Alerts Feed, and a "last updated" timestamp. Uses NavigationStack with large title.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Daily Quote card is the first thing users see — wrong priority**
   - Current: Quote card sits above the portfolio summary
   - Problem: The user opens the app to check "How's my portfolio?" — the quote pushes the answer down
   - Recommended: Move quote below Portfolio Summary, or into a collapsible section, or show it only on first launch of the day
   - File: `HomeView.swift:18-19`

```swift
VStack(spacing: 20) {
    // Portfolio first — answer the key question immediately
    PortfolioSummaryCard(...)
        .padding(.horizontal)
    
    // Then market context
    MarketOverviewCard(...)
        .padding(.horizontal)
    
    // Quote as subtle inspiration (collapsible)
    DailyQuoteCard(quote: quote)
        .padding(.horizontal)
    
    // Then actionable data
    TopAIPicksCard(...)
        .padding(.horizontal)
}
```

2. **[HIGH] Portfolio value not using monospace font consistently**
   - Current: Uses `.monoLarge` (32pt bold monospaced) ✅ 
   - But change amount uses `.mono` (16pt) which is too small relative to the header
   - Recommended: Change value should be at least 18pt mono
   - File: `HomeView.swift:88-97` (PortfolioSummaryCard)

3. **[HIGH] Market overview card — index values lack proper formatting**
   - Current: Values >1000 show no decimals, values ≤1000 show 2 decimals
   - Problem: S&P 500 at "4,892" looks weird without any decimals. Financial convention is 2 decimals for indices.
   - Recommended: Always show 2 decimals for market indices
   - File: `HomeViewModel.swift:157-160` (MarketIndex.formattedValue)

```swift
var formattedValue: String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .decimal
    formatter.groupingSeparator = ","
    formatter.maximumFractionDigits = 2
    formatter.minimumFractionDigits = 2
    return formatter.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
}
```

4. **[MEDIUM] "Today" label in portfolio card is redundant with "last updated" at bottom**
   - Current: Both "Today" in the P&L row and "Updated X minutes ago" at the bottom
   - Recommended: Remove "Today" from the P&L row; the context is clear
   - File: `HomeView.swift:96-97`

#### Color & Theme

5. **[HIGH] Market index tiles — change text color logic**
   - Current: Uses `.Signal.positive` / `.Signal.negative` / `.Signal.neutral` ✅ 
   - But the tile header "S&P 500" uses `.Text.secondary` — loses visual weight
   - Recommended: Use `.Text.primary` for the index name and reserve secondary for the label
   - File: `HomeView.swift:118`

6. **[MEDIUM] AI Pick Row — dual badge overload**
   - Current: Each row shows BOTH a score badge (colored number) AND a signal badge ("BUY"/"SELL")
   - Problem: Both badges say the same thing (score ≥70 = BUY). Redundant visual noise.
   - Recommended: Show ONLY the signal badge with the score inside, or show score + signal as a single unit
   - File: `HomeView.swift:156-177`

```swift
// Simplified: Score badge with signal text
VStack(spacing: 2) {
    Text("\(pick.score)")
        .font(.headline.monospacedDigit())
        .foregroundColor(.white)
    Text(pick.signal)
        .font(.caption2.bold())
        .foregroundColor(.white.opacity(0.8))
}
.frame(width: 48)
.padding(.vertical, 6)
.background(signalColor)
.cornerRadius(8)
```

7. **[MEDIUM] Quote card icon — `.Brand.primary` (blue) again**
   - Current: `Image(systemName: "quote.opening").foregroundColor(.Brand.primary)`
   - Recommended: `.Accent.gold` or `.Text.tertiary` — the quote is decorative, not actionable
   - File: `HomeView.swift:68`

8. **[MEDIUM] Alert row icon colors are inconsistent**
   - Current: `scoreChange` = `.Brand.primary` (blue), `signalChange` = `.Signal.hold` (amber), etc.
   - Problem: Blue icon for score changes creates a mixed-accent situation
   - Recommended: Use `.Accent.gold` for primary alerts, `.Signal.hold` for warnings
   - File: `HomeViewModel.swift:220-226`

#### Typography

9. **[MEDIUM] Section headers inconsistent**
   - Current: "Portfolio Value" = `.subheadline` + `.Text.secondary`, "Market Overview" = `.headline` + `.Text.primary`, "Top AI Picks" = `.headline` + `.Text.primary`
   - Problem: Portfolio label is de-emphasized while it should be the most prominent section
   - Recommended: All section headers should use `.headline` + `.Text.primary`
   - File: `HomeView.swift:82,106,134`

10. **[LOW] Alert timestamp font is `.caption2` — too small**
    - Current: `.caption2` ≈ 11pt
    - Recommended: `.caption` ≈ 12pt for better readability
    - File: `HomeView.swift:208`

#### Spacing & Layout

11. **[MEDIUM] Card spacing is 20pt but spec says section spacing should be 24pt**
    - Current: `VStack(spacing: 20)`
    - Spec: Section spacing = 24pt
    - File: `HomeView.swift:17`

12. **[MEDIUM] No card separators or visual grouping**
    - Current: Cards are just stacked with spacing — hard to distinguish sections
    - Recommended: Add subtle section headers ("MY PORTFOLIO", "MARKETS", "AI PICKS", "ALERTS") above each card group
    - File: `HomeView.swift:17-35`

#### Animations & Loading

13. **[HIGH] Loading state is just a ProgressView spinner**
    - Current: Single centered spinner when data is loading
    - Spec says: "Skeleton screens for data loading, shimmer animation on placeholders"
    - Recommended: Add skeleton cards that shimmer while data loads
    - File: `HomeView.swift:41-44`

```swift
// Skeleton view example
struct SkeletonCard: View {
    @State private var shimmerOffset: CGFloat = -200
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.Background.tertiary)
                .frame(height: 14)
                .frame(width: 120)
            
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.Background.tertiary)
                .frame(height: 28)
                .frame(width: 180)
            
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.Background.tertiary)
                .frame(height: 14)
                .frame(width: 160)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .overlay(shimmerOverlay)
    }
}
```

14. **[MEDIUM] No pull-to-refresh haptic**
    - Current: `.refreshable` with no haptic feedback
    - Recommended: Add medium impact haptic when refresh triggers
    - File: `HomeView.swift:38`

15. **[MEDIUM] "See All" link on AI Picks uses `.Brand.primary` (blue)**
    - Current: `.foregroundColor(.Brand.primary)` = blue
    - Recommended: `.Accent.gold` to match CTA color language
    - File: `HomeView.swift:137`

16. **[LOW] Empty alerts state icon**
    - Current: `bell.slash` icon with "No recent alerts" — good ✅
    - Minor: Could add a subtle suggestion like "Watch stocks to get alerts"
    - File: `HomeView.swift:192-195`

#### Data Integrity

17. **[MEDIUM] Portfolio value shows $100,000 as fallback**
    - Current: `portfolioValue: Double = 100_000` — this is the default value
    - Problem: If portfolio API fails, user sees $100K which could be misleading
    - Recommended: Show a loading/error state instead of a default number
    - File: `HomeViewModel.swift:14`

18. **[LOW] Top picks fallback sample data doesn't show prices**
    - Current: Fallback sample data has `price: 0, change: 0, changePercent: 0`
    - These zeros display as "$0.00" and "+0.0%" — misleading
    - File: `HomeViewModel.swift:106-112`

### Accessibility Issues

- **[HIGH]** Portfolio summary card has no combined accessibility element. VoiceOver reads each piece separately instead of "Portfolio value: $124,532.18, up $1,234.56 or 1 percent today"
- **[HIGH]** Market index tiles lack `accessibilityElement(children: .combine)` — reads as fragmented pieces
- **[MEDIUM]** Alert rows need proper VoiceOver descriptions combining ticker, title, and time
- **[LOW]** "See All" link in AI Picks section should have `accessibilityHint("Shows all scored stocks")`
