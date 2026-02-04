# UX/UI Review: Launch & Auth Flow

**Screens:** LaunchView, LoginView, RegisterView, ForgotPasswordView  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: LaunchView (Splash)

### Current State
Simple splash screen with logo fade-in + scale animation over 2 seconds, then fade-out to transition.

### Issues Found

1. **[MEDIUM] Background color inconsistency**
   - Current: Hardcoded `Color(red: 13/255, green: 13/255, blue: 15/255)` = `#0D0D0F`
   - Recommended: Use `Color.Background.primary` (`#121418`) from Theme.swift for consistency
   - File: `LaunchView.swift:10`
   - Note: The design spec says background is `#000000` (pure black) or `#0D0D0D`. Theme.swift uses `#121418`. LaunchView uses a third value `#0D0D0F`. **Three different "black" values across three sources — this is a systemic color inconsistency.**

2. **[LOW] No loading state or progress indication**
   - Current: Static logo for 2 seconds, no visual feedback that the app is loading
   - Recommended: Add a subtle shimmer or pulsing ring animation to indicate the app is initializing
   - File: `LaunchView.swift`

3. **[LOW] Missing daily quote integration on launch**
   - Current: Splash shows only the logo
   - Spec says: "Daily inspiration — each app launch displays a rotating motivational quote"
   - Recommended: Consider showing the quote briefly during the splash, or on the transition to the home screen
   - File: `LaunchView.swift`

4. **[MEDIUM] Transition timing is abrupt**
   - Current: 0.8s fade in, 2s hold, 0.3s fade out. The fade-out is too fast relative to the fade-in.
   - Recommended: Matched timing — 0.6s in, 1.5s hold, 0.5s out with easeInOut

```swift
// Recommended launch animation
.onAppear {
    withAnimation(.easeOut(duration: 0.6)) {
        opacity = 1.0
        scale = 1.0
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
        withAnimation(.easeInOut(duration: 0.5)) {
            opacity = 0
            scale = 1.02 // Subtle scale-up on exit
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) {
            showLaunch = false
        }
    }
}
```

---

## Screen: LoginView

### Current State
Dark login screen with Sigil logo, email/password fields, Sign In button (gold), Forgot Password link (gray), biometric option, and Create Account link (gold).

### Issues Found

1. **[CRITICAL] Brand color conflict — Logo uses blue/cyan, UI uses gold accent**
   - Current: The SigilLogo asset uses blue/cyan circuit-board aesthetic. The UI accent is `#FFB800` (gold). `Color.Brand.primary` is `#0066CC` (blue). This creates a **three-way brand identity crisis**.
   - Recommended: The design spec (UX_AGENT.md) says `Brand.primary` / `Accent.gold` = `#FFD700`. The Theme.swift has `Brand.primary = #0066CC` (blue) and `Accent.gold = #FFB800`. These should be unified. Either the logo needs a gold treatment, or the entire app accent needs to match the logo's blue.
   - File: `Theme.swift:10`, Logo asset
   - **This is the single biggest design inconsistency in the entire app.**

2. **[HIGH] Accent color mismatch between spec and implementation**
   - Design Spec: `Brand.primary / Accent.gold = #FFD700`
   - Theme.swift: `Accent.gold = #FFB800`, `Brand.primary = #0066CC`
   - UX_AGENT.md: `Brand.primary = #FFD700`
   - There are three sources of truth and none agree.
   - File: `Theme.swift:9-10,88`

3. **[HIGH] "Forgot Password?" link color inconsistency**
   - Current: Uses `.Text.secondary` (`#8E8E93`) — gray
   - Problem: "Create Account" below it uses `.Accent.gold` — gold. Both are secondary actions but styled completely differently.
   - Recommended: Both should use `.Accent.gold` or both should use `.Text.secondary`. Since "Forgot Password" is arguably more important (users need it urgently), it should at least match "Create Account".
   - File: `LoginView.swift:81-82`

4. **[HIGH] No form validation feedback before submission**
   - Current: The Sign In button is always enabled. Tapping with empty fields presumably shows a server error.
   - Recommended: Disable the button until both fields have content. Add inline validation for email format.
   - File: `LoginView.swift:59-72`

```swift
// Add disable state
.disabled(email.isEmpty || password.isEmpty || authVM.isLoading)
.opacity(email.isEmpty || password.isEmpty ? 0.5 : 1.0)
```

5. **[MEDIUM] Missing input field focus styling**
   - Current: Text fields have a static `Color.Utility.border` stroke. No visual change on focus.
   - Recommended: Add a focus ring color change to `Accent.gold` when the field is active.
   - File: `LoginView.swift` (SigilTextField struct, line ~117)

```swift
struct SigilTextField: View {
    @FocusState private var isFocused: Bool
    // ... existing properties ...
    
    var body: some View {
        TextField(...)
            .focused($isFocused)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isFocused ? Color.Accent.gold : Color.Utility.border, lineWidth: isFocused ? 2 : 1)
            )
    }
}
```

6. **[MEDIUM] Excessive vertical spacing — content floats too high**
   - Current: `Spacer().frame(height: 40)` at top, then `Spacer()` at bottom. The entire form sits in the upper 60% of the screen.
   - Recommended: Use equal top/bottom spacers, or center the content vertically.
   - File: `LoginView.swift:28`

7. **[MEDIUM] Face ID button has low discoverability**
   - Current: Face ID option appears as a small text link below "Forgot Password"
   - Recommended: Make it a larger, more prominent button with a filled icon and border treatment
   - File: `LoginView.swift:85-94`

8. **[LOW] No haptic feedback on Sign In button tap**
   - Current: No haptic
   - Recommended: Light impact on tap, success notification on successful login
   - File: `LoginView.swift:59`

9. **[LOW] Missing keyboard avoidance**
   - Current: `ScrollView` handles basic scrolling, but there's no explicit keyboard avoidance for the bottom fields
   - Recommended: Fields should scroll up when keyboard appears. Add `.scrollDismissesKeyboard(.interactively)`
   - File: `LoginView.swift`

10. **[LOW] `autocapitalization` deprecated**
    - Current: `.autocapitalization(.none)` (deprecated in iOS 15+)
    - Recommended: `.textInputAutocapitalization(.never)`
    - File: `LoginView.swift:42`

### Accessibility Issues

- **[HIGH]** No `accessibilityLabel` on the logo image. VoiceOver users hear "SigilLogo, Image" instead of "Sigil - AI Market Intelligence"
- **[MEDIUM]** No `accessibilityHint` on the Sign In button ("Double tap to sign in to your account")
- **[MEDIUM]** Face ID button lacks accessibility description

---

## Screen: RegisterView

### Current State
Registration form with Full Name, Email, Password, Confirm Password fields and Create Account button.

### Issues Found

1. **[HIGH] No password strength indicator**
   - Current: Only "min 8 chars" hint in placeholder. User gets no feedback on password quality.
   - Recommended: Add a password strength meter (weak/medium/strong) below the password field
   - File: `RegisterView.swift:48`

2. **[MEDIUM] No show/hide password toggle**
   - Current: Password fields are SecureFields with no visibility toggle
   - Recommended: Add an eye icon toggle to reveal/hide password
   - File: `RegisterView.swift` (SigilSecureField needs enhancement)

3. **[MEDIUM] Logo too large for a secondary screen**
   - Current: `frame(maxWidth: 180)` — nearly same size as login's 220
   - Recommended: Either reduce to 100-120 or remove entirely on registration. This is a form screen, not a landing page.
   - File: `RegisterView.swift:26-28`

4. **[LOW] Back button uses chevron.left only — no text**
   - Current: Custom toolbar back button with just `chevron.left`
   - Recommended: Add "Back" text or "Sign In" for clarity per iOS HIG
   - File: `RegisterView.swift:72-78`

5. **[LOW] Form submission doesn't trim email whitespace**
   - Current: `trimmingCharacters` on fullName but email check is just `.isEmpty`
   - Recommended: Trim email too, add format validation
   - File: `RegisterView.swift:82-84`

---

## Screen: ForgotPasswordView

### Current State
3-step password reset: email → code entry → success. Has a 6-digit code input component.

### Issues Found

1. **[HIGH] Dev code visible in production UI**
   - Current: Line 108-116 shows a yellow badge with "Dev code: **{code}**". This must NOT ship.
   - Recommended: Wrap in `#if DEBUG` compiler flag
   - File: `ForgotPasswordView.swift:108-116`

```swift
#if DEBUG
if let devCode = authVM.resetCode {
    // Dev code display
}
#endif
```

2. **[HIGH] Icon color uses Brand.primary (blue) — inconsistent with gold accent theme**
   - Current: `.foregroundColor(.Brand.primary)` on the key icon. Brand.primary = blue.
   - Recommended: Use `.Accent.gold` to match the rest of the gold accent system
   - File: `ForgotPasswordView.swift:28`

3. **[MEDIUM] CodeInputField accessibility**
   - Current: Hidden TextField overlay for keyboard input. The visual digit boxes are Text views, not accessible.
   - Recommended: Add `.accessibilityLabel("Reset code digit \(index + 1)")` to each box, and make the container an accessibility element
   - File: `ForgotPasswordView.swift:178-210`

4. **[MEDIUM] Step transition lacks animation polish**
   - Current: `withAnimation { step = .code }` — default animation
   - Recommended: Use a slide transition for step changes

```swift
withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) {
    step = .code
}
```

5. **[LOW] "Back to Sign In" on step 1 uses `.Text.tertiary` — very hard to see**
   - Current: `foregroundColor(.Text.tertiary)` = `#5E5E63`
   - Problem: On `#121418` background, this is approximately 2.5:1 contrast ratio — **fails WCAG AA** (needs 4.5:1)
   - File: `ForgotPasswordView.swift:99`

6. **[LOW] Error text uses `.Signal.sell` with `.caption` font — tiny red text**
   - Current: Small red error text that could be missed
   - Recommended: Use `.subheadline` and add an error icon for visibility
   - File: `ForgotPasswordView.swift:35-39`

---

## Cross-Screen Auth Flow Patterns

### Positive Patterns
- Consistent use of `SigilTextField` / `SigilSecureField` components
- Error banners are present on all auth screens
- Gold CTA buttons are consistent across Login, Register, ForgotPassword
- Dark theme is maintained throughout

### Systemic Issues
1. **Brand color identity crisis** — Logo (blue), Brand.primary (blue), Accent.gold (amber), spec says gold is primary
2. **No animated transitions between auth screens** — navigation push is the default, no custom transitions
3. **No skeleton/shimmer loading states** — just ProgressView spinners
4. **Inconsistent spacing** — each screen uses different top spacer heights (40, 24, 20)
5. **No haptic feedback** anywhere in the auth flow
