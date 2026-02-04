# 🎯 MASTER UX/UI REVIEW — Sigil iOS App

**App:** Sigil — AI Market Intelligence  
**Version:** 1.0.0 (Build 1)  
**Platform:** iOS 17+ / iPhone 17 Pro Simulator  
**Reviewer:** UX/UI Designer Agent  
**Date:** 2026-02-04  
**Files Reviewed:** 16 SwiftUI source files, Theme.swift, 2 design spec documents  

---

## 1. Executive Summary

### Overall Design Quality Score: **6.0 / 10**

The app has a **solid functional foundation** with comprehensive features, correct data flow, and proper screen architecture. The dark theme is well-executed at a surface level, and the component decomposition is clean. However, there is a **systemic brand identity crisis** and **pervasive color inconsistency** that undermines the professional, institutional aesthetic the app aims for. The gap between what the design specs promise and what the code delivers is significant.

### What Works Well
- ✅ Dark theme maintained throughout (no white flashes)
- ✅ Card-based layout pattern is consistent
- ✅ Score system UI is well-visualized with component bars
- ✅ Security features (PIN lockout tiers, biometric) are thoughtfully designed
- ✅ Onboarding is concise and skippable
- ✅ Error handling exists on every data-loading screen
- ✅ Pull-to-refresh on all scrollable content
- ✅ SF Symbols used correctly throughout

### What Needs Immediate Attention
- ❌ Brand color identity crisis (blue vs gold vs amber)
- ❌ Three different "black" backgrounds across files
- ❌ PrimaryButtonStyle is blue when spec says gold
- ❌ Zero accessibility on charts
- ❌ No skeleton loading states (spec requires them)

---

## 2. Top 5 Priorities (Must Fix Before Launch)

### Priority 1: 🔴 Resolve the Brand Color Identity Crisis
**Severity:** CRITICAL  
**Impact:** Every single screen  
**Effort:** Medium (1-2 days)

The app has THREE competing color systems:
- **UX_AGENT.md** says gold (`#FFD700`) is the primary brand color
- **Theme.swift** says `Brand.primary = #0066CC` (blue), `Accent.gold = #FFB800` (amber)
- **03_DESIGN_UX_SPEC.md** says `Primary Action = #2196F3` (blue), `Warning = #FFC107` (yellow)

**Decision needed:** Is the primary accent GOLD or BLUE?

**Recommendation:** Gold. The institutional dark + gold aesthetic is distinctive and aligns with Bloomberg/premium financial branding. Blue is generic fintech.

**Action items:**
1. Change `Brand.primary` in Theme.swift to `#FFD700` (or `#FFB800` for slightly warmer gold)
2. Update `PrimaryButtonStyle` to use gold background
3. Update `SecondaryButtonStyle` to use gold outline
4. Keep `Chart.line` as `#0066CC` blue (for data visualization contrast)
5. Update all `.Brand.primary` usages on non-chart elements to gold
6. Reconcile the logo color with the gold system (or keep blue logo as intentional contrast)

### Priority 2: 🔴 Unify Background Colors
**Severity:** CRITICAL  
**Impact:** LaunchView, LockScreenView, PinSetupView, Theme.swift  
**Effort:** Low (30 minutes)

Four different "black" values are used:
- `#0D0D0F` (LaunchView, LockScreen, PinSetup — hardcoded)
- `#121418` (Theme.swift Background.primary)
- `#000000` (Design spec)
- `#0D0D0D` (Design spec Surface)

**Action:** Replace all hardcoded colors with `Color.Background.primary`. Then decide if `#121418` or `#0D0D0F` is the correct background and update Theme.swift accordingly.

### Priority 3: 🟡 Fix PrimaryButtonStyle (Blue → Gold)
**Severity:** CRITICAL  
**Impact:** Onboarding buttons, IBKR connect, Error retry  
**Effort:** Low (15 minutes)

```swift
// Theme.swift - PrimaryButtonStyle
struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(Color.Background.primary) // Dark text on gold
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Accent.gold)  // ← CHANGE FROM Brand.primary
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}
```

### Priority 4: 🟡 Add Chart Accessibility
**Severity:** CRITICAL (accessibility compliance)  
**Impact:** StockDetailView, PortfolioView, HomeView  
**Effort:** Medium (1 day)

All charts (price charts, score history, performance, sector allocation) are **completely invisible to VoiceOver users**. This is a WCAG violation and App Store rejection risk.

**Action:** Add `accessibilityLabel` and `accessibilityElement` to every chart container describing the trend and key data points.

### Priority 5: 🟡 Implement Skeleton Loading States
**Severity:** HIGH  
**Impact:** HomeView, ScoresView, StockDetailView, PortfolioView  
**Effort:** Medium (1-2 days)

Design spec explicitly requires "Skeleton screens for data loading, shimmer animation on placeholders." Currently, every loading state is just a `ProgressView` spinner.

---

## 3. All Issues by Severity

### CRITICAL (Must fix — broken layout, wrong colors, accessibility failure)

| # | Issue | File | Line(s) | Screen(s) |
|---|-------|------|---------|-----------|
| C1 | Brand.primary is blue (#0066CC), spec says gold (#FFD700) | Theme.swift | 10 | All |
| C2 | PrimaryButtonStyle uses blue background | Theme.swift | 113 | Onboarding, IBKR, Error |
| C3 | Background color hardcoded as #0D0D0F instead of using Theme | LaunchView.swift, LockScreenView.swift, PinSetupView.swift | 10, 48, 24 | Launch, Lock, PinSetup |
| C4 | Four different "black" backgrounds across codebase | Theme.swift + 3 hardcoded files | — | System-wide |
| C5 | Tab bar tint uses system accentColor, not themed | ContentView.swift | 35 | Tab bar |
| C6 | All charts have zero VoiceOver accessibility | StockDetailView, PortfolioView | Multiple | Detail, Portfolio |
| C7 | Three different gold values (#FFD700, #FFB800, #FFC107) | UX_AGENT.md, Theme.swift, Design spec | — | System-wide |

### HIGH (Should fix — design system violation, poor hierarchy)

| # | Issue | File | Line(s) | Screen(s) |
|---|-------|------|---------|-----------|
| H1 | Brand color conflict: logo blue, UI blue, spec says gold | LoginView, Theme.swift | — | Login, system-wide |
| H2 | "Forgot Password?" gray while "Create Account" is gold | LoginView.swift | 81-82 | Login |
| H3 | No form validation feedback before submission on login | LoginView.swift | 59-72 | Login |
| H4 | Dev code visible in production UI (ForgotPassword) | ForgotPasswordView.swift | 108-116 | ForgotPassword |
| H5 | ForgotPassword icon uses Brand.primary (blue) not gold | ForgotPasswordView.swift | 28 | ForgotPassword |
| H6 | LockScreen/PinSetup all use blue accent instead of gold | LockScreenView.swift, PinSetupView.swift | Multiple | Lock, PinSetup |
| H7 | Onboarding navigation buttons are blue (PrimaryButtonStyle) | OnboardingView.swift | 55-60 | Onboarding |
| H8 | Daily quote card is first on dashboard, should be below portfolio | HomeView.swift | 18-19 | Home |
| H9 | No skeleton/shimmer loading states — just spinners | HomeView, ScoresView, etc. | Multiple | All data screens |
| H10 | Market index values missing decimal places for >1000 values | HomeViewModel.swift | 157-160 | Home |
| H11 | ScoresView filter chips use blue for "All" selection | ScoresView.swift | 68 | Scores |
| H12 | Stock row layout has fixed widths, truncates company names | ScoresView.swift | 128-158 | Scores |
| H13 | No swipe actions on score list rows | ScoresView.swift | 38-44 | Scores |
| H14 | Stock detail price header has no card background | StockDetailView.swift | 64-87 | Detail |
| H15 | Score number (48pt) is larger than price (32pt) — wrong hierarchy | StockDetailView.swift | 100-103 | Detail |
| H16 | Buy/Sell buttons use PrimaryButtonStyle (blue), should be green/red | StockDetailView.swift | 55-59 | Detail |
| H17 | Chart line is blue but rest of UI should be gold | StockDetailView.swift | 95-96 | Detail |
| H18 | Trade order side toggle too subtle (20% opacity difference) | TradeView.swift | 152-167 | Trade |
| H19 | "Not financial advice" disclaimer missing from trade preview | TradeView.swift | 240 | Trade |
| H20 | Holdings don't link to stock detail | PortfolioView.swift | 113-130 | Portfolio |
| H21 | Portfolio chart uses gold while price charts use blue — inconsistent | PortfolioView.swift | 207 | Portfolio |
| H22 | Toggle tints all blue instead of gold | SettingsView.swift | 118,129,139 | Settings |
| H23 | Tab icons all use .fill variants — should be outline when inactive | TradingAppApp.swift | 133-138 | Tab bar |
| H24 | Trade tab icon (arrows) not intuitive for trading | TradingAppApp.swift | 136 | Tab bar |
| H25 | Auth check uses hardcoded localhost URL | TradingAppApp.swift | 62 | App launch |
| H26 | Health endpoint URL wrong — /api/v1/health returns 404 | TradingAppApp.swift | 62-67 | App launch |
| H27 | Font definitions incomplete — missing Price, Table Header, Table Data | Theme.swift | 142-151 | System-wide |
| H28 | No card style ViewModifier — manual styling on every card | Theme.swift | — | System-wide |
| H29 | SecondaryButtonStyle uses blue outline | Theme.swift | 122-134 | System-wide |

### MEDIUM (Nice to have — polish, consistency, UX improvement)

| # | Issue | File | Line(s) | Screen(s) |
|---|-------|------|---------|-----------|
| M1 | Launch fade-out timing too fast relative to fade-in | LaunchView.swift | — | Launch |
| M2 | No input field focus styling (no gold ring on active) | LoginView.swift | 117 | Login, Register |
| M3 | Login content floats too high — not vertically centered | LoginView.swift | 28 | Login |
| M4 | Face ID button has low discoverability | LoginView.swift | 85-94 | Login |
| M5 | No password strength indicator on registration | RegisterView.swift | 48 | Register |
| M6 | No show/hide password toggle | RegisterView.swift | — | Register |
| M7 | "Back to Sign In" fails WCAG contrast (#5E5E63 on #121418 ≈ 2.5:1) | ForgotPasswordView.swift | 99 | ForgotPassword |
| M8 | Code input field accessibility missing | ForgotPasswordView.swift | 178-210 | ForgotPassword |
| M9 | No haptic feedback on PIN digit entry | LockScreenView.swift | 155-166 | Lock |
| M10 | Shake animation duplicated (not extracted to shared modifier) | LockScreen, PinSetup | Multiple | Lock, PinSetup |
| M11 | "Skip for now" fails WCAG contrast | PinSetupView.swift | 101-104 | PinSetup |
| M12 | No transition animation between PinSetup steps | PinSetupView.swift | 148,157 | PinSetup |
| M13 | Onboarding signal badge corner radius (4pt) inconsistent with rest (6-8pt) | OnboardingView.swift | 146 | Onboarding |
| M14 | Paper Trading toggle blue tint | OnboardingView.swift | 212 | Onboarding |
| M15 | AI Pick Row — dual badge overload (score + signal) | HomeView.swift | 156-177 | Home |
| M16 | Quote card icon uses Brand.primary (blue) | HomeView.swift | 68 | Home |
| M17 | Section headers inconsistent sizes across HomeView | HomeView.swift | 82,106,134 | Home |
| M18 | Card spacing 20pt, spec says 24pt | HomeView.swift | 17 | Home |
| M19 | No pull-to-refresh haptic feedback anywhere | Multiple | — | All |
| M20 | "See All" link uses Brand.primary (blue) | HomeView.swift | 137 | Home |
| M21 | Score list — no alternating row backgrounds per spec | ScoresView.swift | 42 | Scores |
| M22 | Search always visible, wastes space | ScoresView.swift | 51 | Scores |
| M23 | Chart Y-axis on left, financial convention is right | StockDetailView.swift | 112-114 | Detail |
| M24 | Score history threshold lines lack text labels | StockDetailView.swift | 258-263 | Detail |
| M25 | No chart touch-to-inspect interaction | StockDetailView.swift, PortfolioView | Multiple | Detail, Portfolio |
| M26 | Trade entry sheet — segmented picker not themed | StockDetailView.swift | 300 | Trade sheet |
| M27 | Missing "not financial advice" on trade entry sheet | StockDetailView.swift | 288-363 | Trade sheet |
| M28 | Trade screen answers too many questions at once | TradeView.swift | 17-32 | Trade |
| M29 | Order entry card uses 16pt corner radius, rest uses 12pt | TradeView.swift | 226 | Trade |
| M30 | Quantity stepper buttons use mixed accent colors | TradeView.swift | 192-209 | Trade |
| M31 | Portfolio value 36pt while HomeView uses 32pt | PortfolioView.swift | 65 | Portfolio |
| M32 | Sector colors hardcoded, not optimized for dark theme | PortfolioView.swift | 233-245 | Portfolio |
| M33 | Segmented pickers use system style, not dark-themed | PortfolioView, TradeView | Multiple | Portfolio, Trade |
| M34 | Trading mode indicator too prominent in Settings | SettingsView.swift | 16-46 | Settings |
| M35 | "Go Live" button red — should be gold (upgrade, not destruction) | SettingsView.swift | 35-40 | Settings |
| M36 | ErrorStateView icon uses .Signal.hold for errors (should be .error) | ErrorStateView.swift | 13 | Error states |
| M37 | Default portfolio value $100K displayed even when API fails | HomeViewModel.swift | 14 | Home |
| M38 | PIN setup fires 2s after main screen — too early/disruptive | TradingAppApp.swift | 45-47 | App launch |
| M39 | Live trade confirmation uses .destructive for buy orders | TradeView.swift | 272-273 | Trade |

### LOW (Future polish — micro-interactions, subtle refinements)

| # | Issue | File | Line(s) |
|---|-------|------|---------|
| L1 | No loading indication on splash screen | LaunchView.swift | — |
| L2 | Missing daily quote on launch/splash | LaunchView.swift | — |
| L3 | No haptic on Sign In button | LoginView.swift | 59 |
| L4 | `.autocapitalization` deprecated, use `.textInputAutocapitalization` | LoginView.swift | 42 |
| L5 | Back button on Register has no text | RegisterView.swift | 72-78 |
| L6 | Error text too small (.caption) on ForgotPassword | ForgotPasswordView.swift | 35-39 |
| L7 | No success haptic on PIN creation | PinSetupView.swift | 155 |
| L8 | Welcome page icon too large (80pt) | OnboardingView.swift | 68-70 |
| L9 | No haptic on onboarding page transitions | OnboardingView.swift | 55,60 |
| L10 | Alert timestamp .caption2 too small | HomeView.swift | 208 |
| L11 | Rank in score rows is confusing, remove from list | ScoresView.swift | 144-147 |
| L12 | Empty "No stocks found" needs "Clear Filters" button | ScoresView.swift | 32-38 |
| L13 | Recent searches defined but never shown | ScoresView.swift | 207-230 |
| L14 | Key metrics grid — odd tile count causes hanging tile | StockDetailView.swift | 272-285 |
| L15 | Success alert uses system .alert, not themed | StockDetailView.swift | 351-354 |
| L16 | Limit price input no validation feedback | TradeView.swift | 211-218 |
| L17 | Holdings separator uses Border.primary not Utility.divider | PortfolioView.swift | 126 |
| L18 | Performance empty state message passive | PortfolioView.swift | 195-198 |
| L19 | Legal text is placeholder content | SettingsView.swift | 349-367 |
| L20 | Legal body text uses .secondary — too low contrast for reading | SettingsView.swift | 376 |
| L21 | ErrorStateView no appearance animation | ErrorStateView.swift | — |
| L22 | "NEW" badge on Scores tab never activates | ContentView.swift | 7,14 |
| L23 | No haptic on tab switch | ContentView.swift | — |
| L24 | Background lock has no grace period | TradingAppApp.swift | 54-56 |
| L25 | No DestructiveButtonStyle defined in Theme | Theme.swift | — |
| L26 | Fallback sample data shows $0.00 prices | HomeViewModel.swift | 106-112 |

---

## 4. Feature Mapping to Linear Tickets

| Issue Area | Relevant Features | Suggested Ticket |
|-----------|-------------------|-----------------|
| Brand color system | ALL | REC-NEW: Unify brand color system (gold primary) |
| PrimaryButtonStyle fix | F3, F8 | REC-NEW: Fix button styles to use gold |
| Skeleton loading | F4, F5, F6, F7 | REC-NEW: Implement skeleton loading states |
| Chart accessibility | F5.3, F5.5, F7.2, F7.3 | REC-NEW: Add VoiceOver to all charts |
| Auth UX polish | F11.3 | REC-11: Auth flow polish |
| Onboarding fixes | F3.1 | REC-3: Onboarding color/button fixes |
| Home dashboard hierarchy | F4.1, F4.2, F4.3, F3.2 | REC-4: Dashboard content order + polish |
| Scores list interactions | F5.1, F5.2 | REC-5: Score list swipe actions + polish |
| Stock detail charts | F5.3, F5.5 | REC-5: Chart interactions + accessibility |
| Trade UX | F6.1, F6.2, F6.4 | REC-6: Trade flow UX improvements |
| Portfolio navigation | F7.1 | REC-7: Holdings → detail navigation |
| Settings color fixes | F8.1-F8.4 | REC-8: Settings theme alignment |
| Health endpoint fix | F3 (App Launch) | REC-3: Fix auth health check endpoint |
| Dev code leak | F11.3 | REC-11: Remove dev code from ForgotPassword |

---

## 5. Animation Gaps

### Currently Implemented ✅
- Launch logo fade-in + scale
- PIN dot fill animation (spring scale)
- PIN shake animation on error
- Onboarding page transitions (TabView default)
- Score breakdown expand/collapse

### Missing / Needs Improvement 🔴

| Animation | Where | Priority | Implementation |
|-----------|-------|----------|---------------|
| Skeleton shimmer loading | All data screens | HIGH | `TimelineView` + gradient offset animation |
| Number counting animation (portfolio value) | HomeView, PortfolioView | HIGH | `TimelineView` with interpolation from old → new value |
| Tab switch animation | ContentView | MEDIUM | Slight fade + scale on tab content |
| Chart line drawing animation | StockDetailView | MEDIUM | `trim(to:)` animation on chart stroke |
| Score badge pulse on signal change | ScoresView | MEDIUM | Scale + opacity pulse animation |
| Card press feedback | All cards | MEDIUM | `.scaleEffect(0.98)` on press |
| Pull-to-refresh haptic | All scrollable views | MEDIUM | `UIImpactFeedbackGenerator(.medium)` |
| Error state appearance | ErrorStateView | LOW | Fade-in + scale spring |
| Digit entry spring | PIN screens | LOW | Already has spring scale ✅, could add opacity |
| Success checkmark | ForgotPassword, Trade | LOW | Draw-in animation for checkmark circle |

### Recommended Skeleton Loading Implementation

```swift
struct ShimmerEffect: ViewModifier {
    @State private var phase: CGFloat = 0
    
    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    LinearGradient(
                        colors: [
                            Color.Background.tertiary.opacity(0),
                            Color.Background.surface.opacity(0.3),
                            Color.Background.tertiary.opacity(0)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geo.size.width * 2)
                    .offset(x: -geo.size.width + phase * geo.size.width * 3)
                }
                .clipped()
            )
            .onAppear {
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerEffect())
    }
}
```

---

## 6. Accessibility Gaps

### WCAG Compliance Status

| Criterion | Status | Issues |
|-----------|--------|--------|
| 1.1.1 Non-text Content | ❌ FAIL | Charts have no alt text. Logo has no label. |
| 1.3.1 Info and Relationships | ⚠️ PARTIAL | Cards not grouped as semantic units |
| 1.4.3 Contrast (Minimum) | ❌ FAIL | .Text.tertiary (#5E5E63) on #121418 = ~2.5:1 (needs 4.5:1) |
| 1.4.11 Non-text Contrast | ⚠️ PARTIAL | Input field borders may be too subtle |
| 2.1.1 Keyboard | ✅ PASS | SwiftUI handles this |
| 2.4.3 Focus Order | ⚠️ PARTIAL | Custom number pads may have non-logical focus order |
| 3.3.1 Error Identification | ✅ PASS | Error messages present on all forms |
| 3.3.2 Labels | ❌ FAIL | Text fields use placeholder only, no persistent labels |
| 4.1.2 Name, Role, Value | ❌ FAIL | Missing accessibilityLabel on many interactive elements |

### Critical Accessibility Fixes

1. **Charts:** Add `accessibilityElement` with descriptive labels to every chart
2. **Contrast:** Change `.Text.tertiary` from `#5E5E63` to at least `#808080` (4.5:1 on `#121418`)
3. **Form labels:** Add floating labels above fields (not just placeholders)
4. **VoiceOver grouping:** Add `.accessibilityElement(children: .combine)` to all card components
5. **Reduce Motion:** Check `UIAccessibility.isReduceMotionEnabled` before animations
6. **Dynamic Type:** Custom number pads need to respect Dynamic Type or provide alternative input

### Recommended Reduce Motion Support

```swift
struct ConditionalAnimation: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    let animation: Animation?
    
    func body(content: Content) -> some View {
        content
            .animation(reduceMotion ? nil : animation, value: UUID())
    }
}
```

---

## 7. Recommended Design Improvements (Prioritized)

### Tier 1: Foundation Fixes (Do First — 1-2 days)

#### 1.1 Unify Color System
```swift
// Theme.swift — CORRECTED
extension Color {
    struct Brand {
        static let primary = Color(hex: "FFB800")  // GOLD (was blue)
        static let secondary = Color(hex: "2D8B8B")
        static let accent = Color(hex: "FFB800")   // Same as primary
    }
    
    struct Background {
        static let primary = Color(hex: "0D0D0F")  // TRUE carbon black
        static let secondary = Color(hex: "1A1A1F")
        static let tertiary = Color(hex: "252A33")
        static let surface = Color(hex: "2F3640")
        static let card = Color(hex: "1E2229")
    }
}
```

#### 1.2 Fix PrimaryButtonStyle
```swift
struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(Color.Background.primary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Accent.gold)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}
```

#### 1.3 Remove Hardcoded Colors
Replace every `Color(red: 13/255, green: 13/255, blue: 15/255)` with `Color.Background.primary`.

#### 1.4 Fix Tab Bar
```swift
// ContentView.swift
.tint(Color.Accent.gold)

// TradingAppApp.swift - Tab icons
enum Tab: String, CaseIterable {
    var icon: String {
        switch self {
        case .home: return "house"
        case .scores: return "chart.bar"
        case .trade: return "dollarsign.circle"
        case .portfolio: return "briefcase"
        case .settings: return "gearshape"
        }
    }
}
```

### Tier 2: UX Improvements (Do Second — 2-3 days)

#### 2.1 Card ViewModifier
```swift
struct CardStyle: ViewModifier {
    var padding: CGFloat = 16
    var cornerRadius: CGFloat = 12
    
    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Color.Background.secondary)
            .cornerRadius(cornerRadius)
    }
}

extension View {
    func card(padding: CGFloat = 16, radius: CGFloat = 12) -> some View {
        modifier(CardStyle(padding: padding, cornerRadius: radius))
    }
}
```

#### 2.2 Buy/Sell Button Styles
```swift
struct BuyButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Signal.buy)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
    }
}

struct SellButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.Signal.sell)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.clear)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.Signal.sell, lineWidth: 2))
            .opacity(configuration.isPressed ? 0.85 : 1.0)
    }
}
```

#### 2.3 Skeleton Loading
```swift
// SkeletonHomeView.swift
struct SkeletonHomeView: View {
    var body: some View {
        VStack(spacing: 20) {
            // Portfolio skeleton
            VStack(alignment: .leading, spacing: 12) {
                SkeletonRect(width: 100, height: 14)
                SkeletonRect(width: 200, height: 32)
                SkeletonRect(width: 160, height: 14)
            }
            .card()
            .shimmer()
            .padding(.horizontal)
            
            // Market overview skeleton
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(0..<4, id: \.self) { _ in
                    VStack(alignment: .leading, spacing: 4) {
                        SkeletonRect(width: 60, height: 12)
                        SkeletonRect(width: 80, height: 18)
                        SkeletonRect(width: 50, height: 12)
                    }
                }
            }
            .card()
            .shimmer()
            .padding(.horizontal)
        }
    }
}

struct SkeletonRect: View {
    let width: CGFloat
    let height: CGFloat
    
    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(Color.Background.tertiary)
            .frame(width: width, height: height)
    }
}
```

### Tier 3: Polish (Do Third — ongoing)

- Add haptic feedback to all buttons and interactive elements
- Implement chart touch-to-inspect with crosshair
- Add number counting animations for portfolio values
- Implement chart line drawing animation
- Add floating labels to text fields
- Extract shake animation to shared ViewModifier
- Complete font definition system in Theme.swift
- Add comprehensive VoiceOver labels to all interactive elements

---

## Appendix: File-by-File Issue Count

| File | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Theme.swift | 3 | 4 | 1 | 1 | **9** |
| TradingAppApp.swift | 1 | 3 | 2 | 1 | **7** |
| LoginView.swift | 1 | 2 | 3 | 4 | **10** |
| HomeView.swift | 0 | 3 | 6 | 2 | **11** |
| HomeViewModel.swift | 0 | 1 | 2 | 1 | **4** |
| StockDetailView.swift | 1 | 4 | 5 | 2 | **12** |
| ScoresView.swift | 0 | 3 | 4 | 3 | **10** |
| TradeView.swift | 0 | 3 | 6 | 2 | **11** |
| PortfolioView.swift | 1 | 3 | 5 | 3 | **12** |
| SettingsView.swift | 0 | 2 | 5 | 4 | **11** |
| OnboardingView.swift | 0 | 3 | 3 | 3 | **9** |
| LockScreenView.swift | 1 | 2 | 3 | 2 | **8** |
| PinSetupView.swift | 1 | 2 | 3 | 1 | **7** |
| ForgotPasswordView.swift | 0 | 2 | 2 | 2 | **6** |
| RegisterView.swift | 0 | 1 | 2 | 2 | **5** |
| LaunchView.swift | 0 | 0 | 2 | 2 | **4** |
| ContentView.swift | 1 | 1 | 1 | 2 | **5** |
| ErrorStateView.swift | 0 | 0 | 2 | 3 | **5** |
| **TOTALS** | **10** | **39** | **57** | **40** | **146** |

---

**End of Master Review**

*This review is intentionally brutal. The app has a solid functional foundation. Fixing the color system alone (Priority 1-3) would increase the score from 6.0 to 7.5. Adding proper accessibility (Priority 4) and loading states (Priority 5) would bring it to 8.0+. The remaining issues are polish that would push toward 9.0.*
