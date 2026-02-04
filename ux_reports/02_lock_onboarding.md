# UX/UI Review: Lock Screen & Onboarding

**Screens:** LockScreenView, PinSetupView, OnboardingView  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: LockScreenView

### Current State
Full-screen lock with biometric prompt, PIN entry fallback, and 3-tier lockout escalation system. Custom number pad, PIN dot indicators with shake animation on error. Security wipe after 15 failed attempts.

### Issues Found

1. **[CRITICAL] Background color inconsistency (3rd variant)**
   - Current: `Color(red: 13/255, green: 13/255, blue: 15/255)` = `#0D0D0F` (hardcoded)
   - Should be: `Color.Background.primary` (`#121418` from Theme)
   - This is the same issue as LaunchView — hardcoded instead of using the theme system
   - File: `LockScreenView.swift:48`

2. **[HIGH] Brand.primary used as accent color throughout — blue not gold**
   - Current: PIN dots, biometric icon, number pad all use `.Brand.primary` = `#0066CC` (blue)
   - Design spec says primary accent should be gold (`#FFD700` / `#FFB800`)
   - This screen looks like a completely different app from the gold-accented auth screens
   - Files: `LockScreenView.swift:77,85,134,138` and many more lines

3. **[HIGH] Wiped view "Sign In" button uses PrimaryButtonStyle (blue)**
   - Current: Blue button with white text — `Color.Brand.primary` background
   - Problem: Login screen uses gold buttons. This creates a jarring disconnect.
   - File: `LockScreenView.swift:67-72`

4. **[MEDIUM] Number pad buttons have no haptic feedback on digit entry**
   - Current: Only error haptic on wrong PIN. No feedback on each digit press.
   - Recommended: Light impact feedback on each digit tap
   - File: `LockScreenView.swift:155-166`

```swift
private func numberButton(_ digit: String) -> some View {
    Button {
        guard pin.count < pinLength, !isLockedOut else { return }
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
        errorMessage = nil
        pin += digit
        // ...
    }
}
```

5. **[MEDIUM] Lockout timer display could be more prominent**
   - Current: Small caption text with red background
   - Recommended: Larger font, centered, with a circular countdown animation
   - File: `LockScreenView.swift:103-112`

6. **[MEDIUM] Shake animation is implemented with manual DispatchQueue delays**
   - Current: 5 chained `DispatchQueue.main.asyncAfter` calls for shake effect
   - Recommended: Use `TimelineView` or a proper `Animation` with keyframes (iOS 17+)
   - File: `LockScreenView.swift:178-191`

```swift
// iOS 17+ Keyframe animation
withAnimation(.keyframes) { content in
    content.offset(x: KeyframeTrack(\.offset.x) {
        SpringKeyframe(12, spring: .bouncy)
        SpringKeyframe(-10, spring: .bouncy)
        SpringKeyframe(8, spring: .bouncy)
        SpringKeyframe(-4, spring: .bouncy)
        SpringKeyframe(0, spring: .bouncy)
    })
}
```

7. **[MEDIUM] Wipe warning text visibility**
   - Current: Uses `.caption2` font and `.Signal.hold` (amber) color for the critical warning about data erasure
   - Recommended: Use `.subheadline` and a more prominent background treatment
   - File: `LockScreenView.swift:116-121`

8. **[LOW] "App Locked" wipe screen lacks animation**
   - Current: Fades in with `.easeInOut(duration: 0.5)` — feels too gentle for a security event
   - Recommended: Add a red flash or pulse effect to indicate the severity
   - File: `LockScreenView.swift:228`

9. **[LOW] No "Cancel" or back navigation from PIN entry to biometric**
   - Current: The biometric button in the number pad bottom-left returns to biometric, but it's not immediately obvious
   - Recommended: Add a text label "Use Face ID" below the icon
   - File: `LockScreenView.swift:145-153`

### Accessibility Issues

- **[HIGH]** Number pad buttons have no `accessibilityLabel`. VoiceOver reads "1, Button" but should read "One"
- **[MEDIUM]** PIN dots have no accessibility representation. VoiceOver users can't tell how many digits are entered
- **[MEDIUM]** Lockout countdown timer needs `accessibilityLiveRegion` to announce changes

---

## Screen: PinSetupView

### Current State
3-step PIN creation: create PIN → confirm PIN → biometric opt-in. Custom number pad, matching LockScreenView's design.

### Issues Found

1. **[CRITICAL] Same background color hardcoding as LockScreenView**
   - Current: `Color(red: 13/255, green: 13/255, blue: 15/255)` 
   - Should be: `Color.Background.primary`
   - File: `PinSetupView.swift:24`

2. **[HIGH] Same Brand.primary (blue) color used instead of gold**
   - Every interactive element uses blue (`#0066CC`) instead of the gold accent
   - File: `PinSetupView.swift` throughout

3. **[HIGH] Shake animation is copy-pasted from LockScreenView**
   - Current: Identical 5-step DispatchQueue shake code duplicated
   - Recommended: Extract to a shared `ViewModifier` or `View` extension
   - File: `PinSetupView.swift:166-183`

```swift
// Shared shake modifier
struct ShakeEffect: ViewModifier {
    @Binding var trigger: Bool
    @State private var offset: CGFloat = 0
    
    func body(content: Content) -> some View {
        content
            .offset(x: offset)
            .onChange(of: trigger) { _, newValue in
                guard newValue else { return }
                // Keyframe shake animation
                withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) {
                    offset = 12
                }
                // ... (chain or use keyframes)
            }
    }
}
```

4. **[MEDIUM] Biometric setup buttons don't match app button styles**
   - Current: "Enable Face ID" uses `PrimaryButtonStyle` → blue. "Use PIN Only" uses `.Text.tertiary` link
   - Recommended: Primary button should be gold. Secondary should be outlined.
   - File: `PinSetupView.swift:117-131`

5. **[MEDIUM] "Skip for now" has poor contrast**
   - Current: `.foregroundColor(.Text.tertiary)` = `#5E5E63` on dark background ≈ 2.5:1 contrast
   - Recommended: Use `.Text.secondary` (`#8E8E93`) for minimum 4.5:1 contrast
   - File: `PinSetupView.swift:101-104`

6. **[MEDIUM] No transition animation between create → confirm → biometric steps**
   - Current: `withAnimation { step = .confirm }` with default animation
   - Recommended: Slide transition from right for forward progress
   - File: `PinSetupView.swift:148,157`

7. **[LOW] No success haptic on PIN creation completion**
   - Current: Success haptic only fires on the biometric setup step
   - Recommended: Fire success haptic when PINs match (before biometric step)
   - File: `PinSetupView.swift:155`

---

## Screen: OnboardingView

### Current State
4-page TabView onboarding: Welcome → Score Explanation → Portfolio Size → Paper Trading. Skip button always visible. Bottom navigation with Back/Next buttons.

### Issues Found

1. **[HIGH] Navigation buttons use PrimaryButtonStyle and SecondaryButtonStyle — blue accent**
   - Current: `PrimaryButtonStyle` has blue background (`Color.Brand.primary`)
   - Spec says CTA buttons should be gold
   - File: `Theme.swift:110` (PrimaryButtonStyle definition)
   - This affects EVERY screen that uses PrimaryButtonStyle.

2. **[HIGH] Progress dots use Brand.primary (blue) — should be gold**
   - Current: Active dot is `.Brand.primary` = blue
   - Recommended: `.Accent.gold` for active, `.Text.tertiary` for inactive (current inactive is correct)
   - File: `OnboardingView.swift:48-50`

3. **[HIGH] Page icons all use Brand.primary (blue)**
   - WelcomePage: chart icon = blue
   - ScoreExplanationPage: component icons = blue
   - PaperTradingPage: doc icon = blue
   - Recommended: Use `.Accent.gold` for primary page icons
   - Files: `OnboardingView.swift:70,133,192`

4. **[MEDIUM] Score system explanation — signal badges use hardcoded colors correctly but don't match Theme**
   - Current: `SignalBadge` uses `.Signal.buy`, `.Signal.hold`, `.Signal.sell` — good
   - Issue: But the badge corner radius is `4` while other badges in the app use `6` or `8`
   - File: `OnboardingView.swift:146`

5. **[MEDIUM] Portfolio size selection has no animation on option change**
   - Current: Tapping a portfolio size option instantly changes the selection
   - Recommended: Add a spring animation for the border and checkmark transition
   - File: `OnboardingView.swift:165`

```swift
Button(action: {
    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
        action()
    }
})
```

6. **[MEDIUM] TabView page swiping may interfere with horizontal scrolling**
   - Current: Using `.tabViewStyle(.page(indexDisplayMode: .never))` with custom dots
   - Issue: The "Back" and "Next" buttons AND swipe are both available — which is good, but there's no visual affordance that swiping is possible
   - File: `OnboardingView.swift:40-42`

7. **[MEDIUM] Paper Trading toggle uses `.Brand.primary` tint (blue)**
   - Current: `SwitchToggleStyle(tint: .Brand.primary)`
   - Recommended: Use `.Accent.gold` to match the CTA color
   - File: `OnboardingView.swift:212`

8. **[LOW] Welcome page icon too large**
   - Current: `.font(.system(size: 80))` for the chart icon
   - Recommended: 64pt maximum. 80pt competes with the headline text.
   - File: `OnboardingView.swift:68-70`

9. **[LOW] No haptic feedback on page transitions**
   - Current: Silent page changes
   - Recommended: Light impact on Next/Back button tap
   - File: `OnboardingView.swift:55,60`

10. **[LOW] Skip button placement**
    - Current: Top-right, uses `.Text.secondary` — good for non-intrusive but still accessible
    - Spec says: "Skip button always visible" ✅
    - Minor issue: No animation or confirmation on skip. Consider a brief "Are you sure?" or just fast-forward to completion.

### Accessibility Issues

- **[MEDIUM]** `TabView` pages lack `accessibilityLabel` — VoiceOver doesn't announce "Page 1 of 4"
- **[MEDIUM]** Score component percentages (35%, 25%, etc.) should be accessible as "35 percent weight"
- **[LOW]** `SignalBadge` colors need text alternative (already has text ✅, good)

---

## Cross-Screen Patterns (Lock + Onboarding)

### Positive Patterns
- Security escalation system in LockScreen is well-designed (3 tiers, clear warnings)
- Onboarding content is concise and respects user intelligence
- Skip button always visible in onboarding ✅
- PIN dots with scale animation provide good visual feedback

### Systemic Issues
1. **Brand.primary (blue) vs Accent.gold (amber) confusion persists** — these screens all use blue where gold should be the primary accent
2. **Background color hardcoded** in LockScreen/PinSetup instead of using Theme
3. **Shake animation duplicated** across LockScreen and PinSetup — needs extraction to shared modifier
4. **No Dynamic Type support** visible — custom number pads use fixed 64pt frames that won't adapt
5. **PrimaryButtonStyle** defined as blue throughout the app — needs to be gold per spec
