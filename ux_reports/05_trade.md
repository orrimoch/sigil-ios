# UX/UI Review: Trade Screen

**Screen:** TradeView + TradeViewModel  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: TradeView

### Current State
Scrollable trade screen with: Trading mode indicator (paper/live), stock search, selected stock card, order entry form (side toggle, order type, quantity, limit price, estimated total), order preview sheet, and today's order history.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Screen answers too many questions at once**
   - Current: Search + selection + order entry + order history all on one scroll
   - Problem: Violates spec principle: "Every screen answers one question" — Trade = "Execute."
   - Recommended: Split into two views: (1) Stock selection (search), (2) Order entry (after selection). Show order history in a separate tab or collapsible section.
   - File: `TradeView.swift:17-32`

2. **[HIGH] Order entry section nested inside a card (.Background.card) — deep nesting**
   - Current: `OrderEntrySection` has its own `.background(Color.Background.card)` + `.cornerRadius(16)` with a 16pt radius
   - Problem: This differs from the standard 12pt corner radius used everywhere else. Cards inside cards create visual confusion.
   - Recommended: Use consistent 12pt radius. Remove the extra card nesting — just use section spacing.
   - File: `TradeView.swift:226`

3. **[MEDIUM] Trading mode indicator feels like a banner, not a status badge**
   - Current: Full-width pill with icon + text
   - Problem: In paper mode (HOLD color, amber), it could be confused with a warning
   - Recommended: Smaller badge, pinned to the navigation bar or integrated into the nav title
   - File: `TradeView.swift:44-62`

```swift
// More subtle badge
.toolbar {
    ToolbarItem(placement: .principal) {
        HStack(spacing: 6) {
            Text("Trade")
                .font(.headline)
            Text(isPaper ? "PAPER" : "LIVE")
                .font(.caption2.bold())
                .foregroundColor(.white)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(isPaper ? Color.Signal.hold : Color.Signal.sell)
                .cornerRadius(4)
        }
    }
}
```

#### Buy/Sell Toggle

4. **[HIGH] Order side toggle has no visual distinction between selected and unselected**
   - Current: Selected side gets `side.color.opacity(0.2)` background, unselected gets `Color.clear`
   - Problem: 20% opacity is too subtle for a critical choice (buy vs sell). Users could place the wrong order.
   - Recommended: Selected side should have full-opacity fill with white text. Unselected should have a clear border.
   - File: `TradeView.swift:152-167`

```swift
ForEach(OrderSide.allCases, id: \.self) { side in
    Button {
        viewModel.orderSide = side
    } label: {
        HStack {
            Image(systemName: side.icon)
            Text(side.rawValue).fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(viewModel.orderSide == side ? side.color : Color.clear)
        .foregroundColor(viewModel.orderSide == side ? .white : .Text.tertiary)
    }
}
.background(Color.Background.secondary)
.cornerRadius(12)
```

5. **[MEDIUM] No haptic feedback on buy/sell toggle change**
   - Current: Silent toggle
   - Recommended: Light impact haptic, especially important since buy/sell is irreversible
   - File: `TradeView.swift:152`

#### Order Entry

6. **[HIGH] Quantity stepper buttons use mixed accent colors**
   - Current: Minus button = `.Text.secondary`, Plus button = `.Accent.gold`
   - Problem: Inconsistent. Both should use the same color or intentionally differentiate (e.g., sell color for minus, buy color for plus)
   - Recommended: Both use `.Text.secondary` in rest state. Or match the selected order side color.
   - File: `TradeView.swift:192-197,204-209`

7. **[MEDIUM] Order type picker uses system `.segmented` style**
   - Current: Default iOS segmented control
   - Problem: May not honor dark theme consistently. Doesn't use signal colors.
   - Recommended: Custom segmented control matching the dark theme
   - File: `TradeView.swift:176`

8. **[MEDIUM] Estimated total card doesn't show what's included**
   - Current: Just "Estimated Total" + dollar amount
   - Recommended: Show "X shares × $Y.ZZ = $TOTAL". Transparency builds trust.
   - File: `TradeView.swift:216-223`

```swift
if viewModel.quantityValue > 0 {
    VStack(spacing: 4) {
        HStack {
            Text("\(Int(viewModel.quantityValue)) shares × \(viewModel.currentPrice?.asCurrency ?? "$—")")
                .font(.caption)
                .foregroundColor(.Text.tertiary)
            Spacer()
        }
        HStack {
            Text("Estimated Total")
                .foregroundColor(.Text.secondary)
            Spacer()
            Text(viewModel.estimatedTotal.asCurrency)
                .font(.title3.bold().monospacedDigit())
                .foregroundColor(.Text.primary)
        }
    }
    .padding()
    .background(Color.Background.secondary)
    .cornerRadius(12)
}
```

9. **[MEDIUM] "Preview Order" button disabled state text is confusing**
   - Current: Shows "Enter shares to trade" when quantity is 0, "Preview Order" otherwise
   - Problem: When canSubmitOrder is false but quantity > 0, it still says "Preview Order" but is greyed out — user doesn't know why
   - Recommended: Show specific reason: "Select a stock first", "Enter quantity", etc.
   - File: `TradeView.swift:227-230`

10. **[LOW] Limit price input has no min/max validation feedback**
    - Current: Raw text field for limit price
    - Recommended: Show current market price as reference. Warn if limit price is far from market.
    - File: `TradeView.swift:211-218`

#### Search Section

11. **[MEDIUM] Search results lack visual separation from the search field**
    - Current: Results appear directly below the search field in a card
    - Recommended: Add a small gap (8pt) and/or a subtle shadow to separate
    - File: `TradeView.swift:80-94`

12. **[LOW] Search debounce not visible in code**
    - Current: `onChange` fires `viewModel.search()` on every character
    - Recommended: Add debounce (300ms) to reduce API calls
    - File: `TradeView.swift:84`

#### Order History

13. **[MEDIUM] Order history cancel button is small icon only**
    - Current: `xmark.circle.fill` icon for cancel — 44pt tap target unclear
    - Recommended: Add a text label "Cancel" or ensure the icon has a 44pt touch target
    - File: `TradeView.swift:322-327`

14. **[LOW] Order status dot is only 8pt — below minimum tap target**
    - Current: 8x8pt circle indicator
    - Recommendation: Not interactive so tap target doesn't apply, but ensure it's at least 12pt for visibility
    - File: `TradeView.swift:304`

#### Order Preview Sheet

15. **[HIGH] "Not financial advice" disclaimer MISSING from order preview**
    - Spec says: "Not financial advice visible at trade confirmation"
    - Current: Paper mode shows "This is a simulated trade" but live mode has no disclaimer
    - File: `TradeView.swift:240-241`

16. **[MEDIUM] Sheet presentationDetents([.medium, .large]) — may be too small for all content**
    - Current: Starts at medium height
    - Problem: With all order details + disclaimers, medium might require scrolling
    - Recommended: Default to `.large` with option to snap to `.medium`
    - File: `TradeView.swift:280`

17. **[MEDIUM] Live trade confirmation uses `.destructive` role — red button**
    - Current: "Confirm Trade" is `.destructive` = red
    - Problem: Buying stock isn't destructive. The red color creates false anxiety.
    - Recommended: Use the order side color (green for buy, red for sell)
    - File: `TradeView.swift:272-273`

### Accessibility Issues

- **[HIGH]** Order side toggle buttons lack `accessibilityLabel`. Should say "Buy order" / "Sell order"
- **[HIGH]** Quantity stepper buttons need labels: "Decrease quantity" / "Increase quantity"
- **[MEDIUM]** Order type picker needs accessibilityHint explaining what "Market" vs "Limit" means
- **[MEDIUM]** Price loading state has no VoiceOver announcement
- **[LOW]** Search results should announce count: "3 results found for AAPL"
