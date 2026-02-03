import SwiftUI

/// Lock screen — tries biometric first, PIN fallback
/// 3-tier escalation: 5 tries → 30s, 10 tries → 5min, 15 tries → full wipe
struct LockScreenView: View {
    @ObservedObject var lockManager: AppLockManager
    
    @State private var pin: String = ""
    @State private var showPinEntry: Bool = false
    @State private var errorMessage: String?
    @State private var totalAttempts: Int = 0
    @State private var tierAttempts: Int = 0
    @State private var shakeOffset: CGFloat = 0
    @State private var isLockedOut: Bool = false
    @State private var lockoutSecondsRemaining: Int = 0
    @State private var currentTier: LockoutTier = .first
    @State private var isWiped: Bool = false
    @FocusState private var pinFocused: Bool
    
    private let pinLength = 6
    
    enum LockoutTier {
        case first   // attempts 1-5 → 30s cooldown
        case second  // attempts 6-10 → 5 min cooldown
        case final_  // attempts 11-15 → full wipe
        
        var maxAttempts: Int {
            return 5
        }
        
        var cooldownSeconds: Int {
            switch self {
            case .first: return 30
            case .second: return 300
            case .final_: return 0  // no cooldown — wipe
            }
        }
        
        var next: LockoutTier? {
            switch self {
            case .first: return .second
            case .second: return .final_
            case .final_: return nil
            }
        }
        
        var warningMessage: String {
            switch self {
            case .first: return ""
            case .second: return "⚠️ 5 more failed attempts will erase all app data"
            case .final_: return ""
            }
        }
    }
    
    var body: some View {
        ZStack {
            Color(red: 13/255, green: 13/255, blue: 15/255)
                .ignoresSafeArea()
            
            if isWiped {
                wipedView
            } else {
                VStack(spacing: 32) {
                    Spacer()
                    
                    // Logo
                    Image("SigilLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: 200)
                    
                    if showPinEntry {
                        pinEntryView
                    } else {
                        biometricView
                    }
                    
                    Spacer()
                    Spacer()
                }
                .padding()
            }
        }
        .task {
            await tryBiometric()
        }
    }
    
    // MARK: - Wiped View
    
    private var wipedView: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "exclamationmark.shield.fill")
                .font(.system(size: 64))
                .foregroundColor(.Signal.sell)
            
            Text("App Locked")
                .font(.title.bold())
                .foregroundColor(.Text.primary)
            
            Text("Too many failed PIN attempts.\nAll local data has been erased for security.")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            Text("Please sign in again to continue.")
                .font(.caption)
                .foregroundColor(.Text.tertiary)
            
            Button {
                // Reset lock and force back to login
                lockManager.resetLock()
                AuthService.shared.logout()
            } label: {
                Text("Sign In")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.Brand.primary)
                    .cornerRadius(12)
            }
            .padding(.horizontal, 48)
            .padding(.top, 16)
            
            Spacer()
            Spacer()
        }
    }
    
    // MARK: - Biometric View
    
    private var biometricView: some View {
        VStack(spacing: 20) {
            if lockManager.biometricType != .none {
                Button {
                    Task { await tryBiometric() }
                } label: {
                    VStack(spacing: 12) {
                        Image(systemName: lockManager.biometricType.icon)
                            .font(.system(size: 48))
                            .foregroundColor(.Brand.primary)
                        
                        Text("Tap to unlock with \(lockManager.biometricType.label)")
                            .font(.subheadline)
                            .foregroundColor(.Text.secondary)
                    }
                }
            }
            
            Button {
                showPinEntry = true
                pinFocused = true
            } label: {
                Text("Use PIN")
                    .font(.subheadline.bold())
                    .foregroundColor(.Brand.primary)
            }
            .padding(.top, 8)
        }
    }
    
    // MARK: - PIN Entry View
    
    private var pinEntryView: some View {
        VStack(spacing: 24) {
            Text("Enter PIN")
                .font(.title3.bold())
                .foregroundColor(.Text.primary)
            
            // PIN dots
            HStack(spacing: 16) {
                ForEach(0..<pinLength, id: \.self) { index in
                    Circle()
                        .fill(index < pin.count ? (errorMessage != nil ? Color.Signal.sell : Color.Brand.primary) : Color.Background.tertiary)
                        .frame(width: 16, height: 16)
                        .overlay(
                            Circle()
                                .stroke((errorMessage != nil ? Color.Signal.sell : Color.Brand.primary).opacity(0.3), lineWidth: 1)
                        )
                        .scaleEffect(index < pin.count ? 1.15 : 1.0)
                        .animation(.spring(response: 0.2, dampingFraction: 0.6), value: pin.count)
                }
            }
            .offset(x: shakeOffset)
            
            // Error / status messages
            VStack(spacing: 6) {
                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Signal.sell)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
                
                if isLockedOut {
                    let minutes = lockoutSecondsRemaining / 60
                    let seconds = lockoutSecondsRemaining % 60
                    let timeStr = minutes > 0 ? String(format: "%d:%02d", minutes, seconds) : "\(seconds)s"
                    
                    Text("Try again in \(timeStr)")
                        .font(.caption.bold())
                        .foregroundColor(.Signal.sell)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.Signal.sell.opacity(0.15))
                        .cornerRadius(8)
                }
                
                // Wipe warning on tier 2
                if currentTier == .second && !isLockedOut {
                    let remaining = currentTier.maxAttempts - tierAttempts
                    Text("⚠️ \(remaining) more failed \(remaining == 1 ? "attempt" : "attempts") will erase all data")
                        .font(.caption2)
                        .foregroundColor(.Signal.hold)
                        .padding(.top, 4)
                }
            }
            
            // Hidden text field for keyboard input (external keyboard support)
            TextField("", text: $pin)
                .keyboardType(.numberPad)
                .focused($pinFocused)
                .frame(width: 0, height: 0)
                .opacity(0)
                .onChange(of: pin) { _, newValue in
                    let filtered = String(newValue.filter { $0.isNumber }.prefix(pinLength))
                    if filtered != newValue {
                        pin = filtered
                    }
                }
            
            // Number pad
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 16) {
                ForEach(1...9, id: \.self) { num in
                    numberButton(String(num))
                }
                
                // Back to biometric
                if lockManager.biometricType != .none {
                    Button {
                        showPinEntry = false
                        pin = ""
                        Task { await tryBiometric() }
                    } label: {
                        Image(systemName: lockManager.biometricType.icon)
                            .font(.title2)
                            .foregroundColor(.Brand.primary)
                            .frame(width: 64, height: 64)
                    }
                } else {
                    Color.clear.frame(width: 64, height: 64)
                }
                
                numberButton("0")
                
                // Delete
                Button {
                    if !pin.isEmpty && !isLockedOut {
                        pin.removeLast()
                    }
                } label: {
                    Image(systemName: "delete.backward")
                        .font(.title2)
                        .foregroundColor(isLockedOut ? .Text.tertiary : .Text.secondary)
                        .frame(width: 64, height: 64)
                }
                .disabled(isLockedOut)
            }
            .padding(.horizontal, 40)
        }
    }
    
    // MARK: - Number Button
    
    private func numberButton(_ digit: String) -> some View {
        Button {
            guard pin.count < pinLength, !isLockedOut else { return }
            errorMessage = nil
            pin += digit
            if pin.count == pinLength {
                submitPin(pin)
            }
        } label: {
            Text(digit)
                .font(.title.bold())
                .foregroundColor(isLockedOut ? .Text.tertiary : .Text.primary)
                .frame(width: 64, height: 64)
                .background(isLockedOut ? Color.Background.tertiary.opacity(0.5) : Color.Background.tertiary)
                .clipShape(Circle())
        }
        .disabled(isLockedOut)
    }
    
    // MARK: - Actions
    
    private func submitPin(_ enteredPin: String) {
        guard !isLockedOut else { return }
        
        if lockManager.unlock(withPin: enteredPin) {
            // Success
            totalAttempts = 0
            tierAttempts = 0
            currentTier = .first
        } else {
            totalAttempts += 1
            tierAttempts += 1
            let remaining = currentTier.maxAttempts - tierAttempts
            
            // Haptic
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
            
            if remaining > 0 {
                errorMessage = "Wrong PIN — \(remaining) \(remaining == 1 ? "try" : "tries") remaining"
            } else {
                // Tier exhausted
                if let nextTier = currentTier.next {
                    // Move to next tier with cooldown
                    errorMessage = "Too many attempts"
                    startLockout(seconds: currentTier.cooldownSeconds) {
                        currentTier = nextTier
                        tierAttempts = 0
                    }
                } else {
                    // Final tier exhausted → WIPE
                    performWipe()
                    return
                }
            }
            
            triggerShake()
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                pin = ""
            }
        }
    }
    
    private func triggerShake() {
        withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) { shakeOffset = 12 }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) {
            withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) { shakeOffset = -10 }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.16) {
            withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) { shakeOffset = 8 }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.24) {
            withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) { shakeOffset = -4 }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.32) {
            withAnimation(.spring(response: 0.1, dampingFraction: 0.5)) { shakeOffset = 0 }
        }
    }
    
    private func startLockout(seconds: Int, onComplete: @escaping () -> Void) {
        isLockedOut = true
        lockoutSecondsRemaining = seconds
        
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { timer in
            DispatchQueue.main.async {
                lockoutSecondsRemaining -= 1
                if lockoutSecondsRemaining <= 0 {
                    timer.invalidate()
                    isLockedOut = false
                    errorMessage = nil
                    onComplete()
                }
            }
        }
    }
    
    private func performWipe() {
        // Heavy haptic
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.error)
        
        // Clear all cached data
        if let cachesURL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first {
            let apiCache = cachesURL.appendingPathComponent("SigilAPICache")
            try? FileManager.default.removeItem(at: apiCache)
        }
        
        // Clear UserDefaults (keep nothing)
        if let domain = Bundle.main.bundleIdentifier {
            UserDefaults.standard.removePersistentDomain(forName: domain)
        }
        
        // Clear keychain tokens
        AuthService.shared.logout()
        
        // Show wiped screen
        withAnimation(.easeInOut(duration: 0.5)) {
            isWiped = true
        }
    }
    
    private func tryBiometric() async {
        guard lockManager.shouldAutoTriggerBiometric else {
            showPinEntry = true
            return
        }
        
        let success = await lockManager.authenticateWithBiometric()
        if !success {
            showPinEntry = true
        }
    }
}

#Preview {
    LockScreenView(lockManager: AppLockManager())
}
