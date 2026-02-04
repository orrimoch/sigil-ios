# UX/UI Review: Settings Screen

**Screen:** SettingsView + IBKRConnectionView + LegalView  
**Reviewer:** UX/UI Agent  
**Date:** 2026-02-04  

---

## Screen: SettingsView

### Current State
Standard iOS List with grouped sections: Trading Mode, Account Preferences, Broker, Notifications, Data, Security, Account, About. Uses `insetGrouped` list style with custom dark theme backgrounds.

### Issues Found

#### Visual Hierarchy

1. **[HIGH] Trading Mode section has too much visual weight**
   - Current: Full icon + title + subtitle + action button, all in a large row with vertical padding
   - Problem: It's the first thing you see and takes up ~100pt of height. Settings should be scannable, not hero sections.
   - Recommended: Simplify to a standard toggle row with mode indicator
   - File: `SettingsView.swift:16-46`

```swift
Section("Trading Mode") {
    Toggle(isOn: Binding(
        get: { !appState.isPaperTrading },
        set: { newValue in
            if newValue { showLiveTradingAlert = true }
            else { appState.isPaperTrading = true }
        }
    )) {
        HStack {
            Image(systemName: appState.isPaperTrading ? "doc.text.fill" : "dollarsign.circle.fill")
                .foregroundColor(appState.isPaperTrading ? .Signal.hold : .Signal.sell)
            Text(appState.isPaperTrading ? "Paper Trading" : "Live Trading")
                .foregroundColor(.Text.primary)
        }
    }
    .tint(.Signal.sell)
}
```

2. **[MEDIUM] Notification toggles have inconsistent icon styling**
   - Current: All notification icons use `.Brand.primary` (blue) with `.fill` variants
   - Problem: Three identical blue icons in a row — no differentiation
   - Recommended: Different icons are already used (chart.bar, checkmark.circle, bell.badge) ✅ but color should match function: weekly = gold, trade = green, alert = amber
   - File: `SettingsView.swift:105-138`

3. **[MEDIUM] "Go Live" button uses `.Signal.sell` (red) background**
   - Current: Red "Go Live" button in paper mode
   - Problem: Red suggests danger/destruction. Going live is a deliberate upgrade, not a destructive action.
   - Recommended: Use `.Accent.gold` for "Go Live" and `.Signal.hold` for "Paper Mode"
   - File: `SettingsView.swift:35-40`

4. **[LOW] Footer warnings use standard foregroundColor without background**
   - Current: "⚠️ Live trading uses real money" as plain red text
   - Recommended: Wrap in a subtle red-tinted card for more visibility
   - File: `SettingsView.swift:44-46`

#### Color & Theme

5. **[HIGH] Toggle tint uses `.Brand.primary` (blue) globally**
   - Current: All toggles use `.tint(.Brand.primary)` = blue
   - Recommended: Gold accent tint for all toggles to match the gold CTA system
   - File: `SettingsView.swift:118,129,139`

6. **[MEDIUM] Section headers use default system styling**
   - Current: Default List section header text (gray, small caps)
   - Problem: System section headers may not perfectly match the dark theme
   - Recommended: Explicitly style with `.foregroundColor(.Text.tertiary)` and `.font(.caption.bold())`
   - File: All sections

7. **[MEDIUM] "Sign Out" button and "Reset Paper Portfolio" both use `.Signal.sell` (red)**
   - Current: Both destructive actions look identical
   - Problem: Sign Out and Reset are very different in severity. Reset is more destructive.
   - Recommended: Sign Out = `.Signal.sell`, Reset = `.Signal.sell` with a more prominent warning treatment
   - File: `SettingsView.swift:143-147,152-156`

#### IBKR Connection View

8. **[HIGH] Connected state "Disconnect" button has no visual containment**
   - Current: Plain red text "Disconnect" at the bottom
   - Recommended: Give it a border or background treatment for better touch target
   - File: `SettingsView.swift:213`

9. **[MEDIUM] Account info section uses `Divider().background(Color.Background.tertiary)`**
   - Current: Different divider color than the rest of the app
   - Rest of app: `Color.Utility.divider` or `Color.Border.primary`
   - File: `SettingsView.swift:199,206`

10. **[MEDIUM] Feature list in disconnected state uses `.Brand.primary` (blue) icons**
    - Current: All feature icons are blue
    - Recommended: Gold accent
    - File: `SettingsView.swift:233-237`

11. **[MEDIUM] PrimaryButtonStyle "Connect IBKR" = blue button**
    - Same systemic issue — PrimaryButtonStyle uses blue, should use gold
    - File: `SettingsView.swift:250`

#### Risk Disclosure Sheet

12. **[MEDIUM] Risk items use `.Signal.hold` (amber) for warning icons**
    - Current: All risk items have amber triangle icons — correct semantically ✅
    - Minor: The sheet cancel button uses `.Brand.primary` (blue) while the main app CTAs are gold
    - File: `SettingsView.swift:320`

13. **[LOW] Risk disclosure toggle uses `.Brand.primary` tint — blue**
    - Current: Blue toggle
    - Recommended: Gold toggle
    - File: `SettingsView.swift:315`

#### Security Section

14. **[MEDIUM] App Lock status shows "Enabled" in green text**
    - Current: `.foregroundColor(.Signal.buy)` for "Enabled" status
    - Problem: Using green (buy signal) for a security setting is semantically wrong
    - Recommended: Use `.Accent.gold` or a custom security green
    - File: `SettingsView.swift:164`

15. **[LOW] Biometric toggle in security section duplicates the one that could be in LockScreen settings**
    - Current: Toggle directly reads/writes `AppLockManager.shared` — works but not reactive
    - Recommended: Use an `@ObservedObject` or `@StateObject` for reactivity
    - File: `SettingsView.swift:170-181`

#### Legal View

16. **[LOW] Legal text content is placeholder**
    - Current: "[Full terms would go here]", "[Full policy would go here]"
    - File: `SettingsView.swift:349,358,367`

17. **[LOW] Legal text view uses `.Text.secondary` for body text — low contrast for long reading**
    - Current: `foregroundColor(.Text.secondary)` = `#8E8E93`
    - Recommended: Use `.Text.primary` for legal text that users must read
    - File: `SettingsView.swift:376`

#### Layout

18. **[MEDIUM] Settings list doesn't have a scroll indicator**
    - Current: Default scroll behavior, which is fine
    - But the list is very long — users may not realize there are more sections below
    - Recommended: Add a subtle "scroll for more" affordance, or alphabetical jump bar
    - File: `SettingsView.swift`

19. **[LOW] Reset Onboarding is buried at the very bottom in "About" section**
    - Current: Last item in the last section
    - This is actually fine — it's a rarely-used feature that shouldn't be prominent ✅

### Accessibility Issues

- **[HIGH]** Trading mode toggle area has multiple interactive elements (info + button) that may confuse VoiceOver navigation. Should be grouped.
- **[MEDIUM]** IBKR connection status dot (8pt circle) needs accessibility representation
- **[MEDIUM]** Risk disclosure acknowledgment toggle needs `accessibilityHint` explaining what it does
- **[LOW]** Section headers should have `accessibilityTraits(.isHeader)` for proper navigation
