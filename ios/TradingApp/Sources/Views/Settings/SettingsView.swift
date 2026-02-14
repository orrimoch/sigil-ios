import SwiftUI
import Combine

/// F8.x: Settings Tab
/// Account settings, IBKR connection, trading mode, notifications
struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = SettingsViewModel()
    
    // Confirmation dialogs
    @State private var showLiveTradingAlert = false
    @State private var showResetAlert = false
    @State private var showPinSetup = false
    
    // Risk settings summary for display
    private var riskSettingsSummary: String {
        let settings = RiskSettingsService.shared.settings
        var active: [String] = []
        
        if settings.hardStop.enabled {
            active.append("Stop-Loss")
        }
        if settings.trailingStop.enabled {
            active.append("Trailing")
        }
        if settings.vixAdjustment.enabled {
            active.append("VIX")
        }
        if settings.positionLimit.enabled {
            active.append("Limits")
        }
        
        return active.isEmpty ? "All protections disabled" : active.joined(separator: ", ")
    }
    
    // Dynamic app version from bundle
    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (Build \(build))"
    }
    
    var body: some View {
        NavigationStack {
            List {
                // F8.3: Trading Mode Section (H1: simplified toggle row)
                Section {
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
                    .tint(.Accent.gold)
                    .accessibilityHint("Switches between paper and live trading mode")
                } header: {
                    Text("Trading Mode")
                        .accessibilityAddTraits(.isHeader)
                } footer: {
                    if !appState.isPaperTrading {
                        Text("⚠️ Live trading uses real money. Trade carefully.")
                            .foregroundColor(.Signal.sell)
                    }
                }
                .listRowBackground(Color.Background.secondary)
                
                // F8.1: Account Settings
                Section {
                    // Portfolio Size
                    Picker(selection: $appState.portfolioSize) {
                        ForEach(PortfolioSize.allCases, id: \.self) { size in
                            VStack(alignment: .leading) {
                                Text(size.rawValue)
                            }
                            .tag(size)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "briefcase.fill")
                                .foregroundColor(.Brand.primary)
                            Text("Portfolio Size")
                                .foregroundColor(.Text.primary)
                        }
                    }
                    
                    // Risk Tolerance
                    Picker(selection: $viewModel.riskTolerance) {
                        ForEach(RiskTolerance.allCases, id: \.self) { risk in
                            Text(risk.rawValue).tag(risk)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "gauge.medium")
                                .foregroundColor(.Brand.primary)
                            Text("Risk Tolerance")
                                .foregroundColor(.Text.primary)
                        }
                    }
                } header: {
                    Text("Account Preferences")
                        .accessibilityAddTraits(.isHeader)
                } footer: {
                    Text(viewModel.riskTolerance.description)
                        .foregroundColor(.Text.tertiary)
                }
                .listRowBackground(Color.Background.secondary)
                
                // F8.2: Broker Connection
                Section {
                    NavigationLink {
                        IBKRConnectionView()
                    } label: {
                        HStack {
                            Image(systemName: "link.circle.fill")
                                .foregroundColor(viewModel.isIBKRConnected ? .Signal.buy : .Brand.primary)
                            
                            VStack(alignment: .leading) {
                                Text("Interactive Brokers")
                                    .foregroundColor(.Text.primary)
                                
                                Text(viewModel.isIBKRConnected ? "Connected" : "Not connected")
                                    .font(.caption)
                                    .foregroundColor(viewModel.isIBKRConnected ? .Signal.buy : .Text.tertiary)
                            }
                            
                            Spacer()
                            
                            if viewModel.isIBKRConnected {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(.Signal.buy)
                            }
                        }
                    }
                } header: {
                    Text("Broker")
                        .accessibilityAddTraits(.isHeader)
                } footer: {
                    Text("Connect IBKR to enable live trading with real money.")
                }
                .listRowBackground(Color.Background.secondary)
                
                // REC-168: Daily Loss Limit (Risk Management)
                if IBKRService.shared.isConnected {
                    DailyLossLimitSettingsSection()
                }
                
                // REC-215: Risk Management Section
                Section {
                    NavigationLink {
                        RiskSettingsView()
                    } label: {
                        HStack {
                            Image(systemName: "shield.lefthalf.filled")
                                .foregroundColor(.Accent.gold)
                            
                            VStack(alignment: .leading) {
                                Text("Risk Management")
                                    .foregroundColor(.Text.primary)
                                
                                Text(riskSettingsSummary)
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                } header: {
                    Text("Risk Protection")
                        .accessibilityAddTraits(.isHeader)
                } footer: {
                    Text("Configure stop-loss orders, trailing stops, and position limits.")
                }
                .listRowBackground(Color.Background.secondary)
                
                // F8.4: Notifications Section (M2: differentiated icon colors, H5: gold tints)
                Section {
                    Toggle(isOn: $viewModel.weeklyScoreAlerts) {
                        HStack {
                            Image(systemName: "chart.bar.fill")
                                .foregroundColor(.Accent.gold)
                            VStack(alignment: .leading) {
                                Text("Weekly Score Updates")
                                    .foregroundColor(.Text.primary)
                                Text("Sundays at 7pm EST")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Accent.gold)
                    
                    Toggle(isOn: $viewModel.tradeConfirmations) {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.Signal.buy)
                            VStack(alignment: .leading) {
                                Text("Trade Confirmations")
                                    .foregroundColor(.Text.primary)
                                Text("When orders are filled")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Accent.gold)
                    
                    Toggle(isOn: $viewModel.scoreAlerts) {
                        HStack {
                            Image(systemName: "bell.badge.fill")
                                .foregroundColor(.Signal.hold)
                            VStack(alignment: .leading) {
                                Text("Score Alerts")
                                    .foregroundColor(.Text.primary)
                                Text("When watched stocks change signal")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Accent.gold)
                } header: {
                    Text("Notifications")
                        .accessibilityAddTraits(.isHeader)
                }
                .listRowBackground(Color.Background.secondary)
                
                // Data & Storage (M7: differentiated Reset styling)
                Section {
                    Button {
                        showResetAlert = true
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Image(systemName: "arrow.counterclockwise")
                                    .foregroundColor(.Signal.sell)
                                Text("Reset Paper Portfolio")
                                    .foregroundColor(.Signal.sell)
                            }
                            Text("Clears all positions and resets to $100,000")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                    
                    Button {
                        viewModel.clearCache()
                    } label: {
                        HStack {
                            Image(systemName: "trash")
                                .foregroundColor(.Text.secondary)
                            Text("Clear Cache")
                                .foregroundColor(.Text.primary)
                        }
                    }
                } header: {
                    Text("Data")
                        .accessibilityAddTraits(.isHeader)
                }
                .listRowBackground(Color.Background.secondary)
                
                // Security Section (M14: gold status, H5: gold toggle tint)
                Section {
                    if AppLockManager.shared.isSetUp {
                        HStack {
                            Image(systemName: "lock.shield.fill")
                                .foregroundColor(.Accent.gold)
                            Text("App Lock")
                                .foregroundColor(.Text.primary)
                            Spacer()
                            Text("Enabled")
                                .foregroundColor(.Accent.gold)
                                .font(.caption)
                        }
                        
                        // F11.2: Biometric toggle
                        if AppLockManager.shared.biometricType != .none {
                            Toggle(isOn: Binding(
                                get: { AppLockManager.shared.biometricEnabled },
                                set: { AppLockManager.shared.setBiometricEnabled($0) }
                            )) {
                                HStack {
                                    Image(systemName: AppLockManager.shared.biometricType.icon)
                                        .foregroundColor(.Accent.gold)
                                    VStack(alignment: .leading) {
                                        Text(AppLockManager.shared.biometricType.label)
                                            .foregroundColor(.Text.primary)
                                        Text("Auto-unlock when available")
                                            .font(.caption)
                                            .foregroundColor(.Text.tertiary)
                                    }
                                }
                            }
                            .tint(.Accent.gold)
                        }
                        
                        Button {
                            showPinSetup = true
                        } label: {
                            Text("Change PIN")
                                .foregroundColor(.Accent.gold)
                        }
                        
                        Button {
                            AppLockManager.shared.resetLock()
                        } label: {
                            Text("Remove App Lock")
                                .foregroundColor(.Signal.sell)
                        }
                    } else {
                        Button {
                            showPinSetup = true
                        } label: {
                            HStack {
                                Image(systemName: "lock.open.fill")
                                    .foregroundColor(.Text.tertiary)
                                Text("Set Up App Lock")
                                    .foregroundColor(.Accent.gold)
                                Spacer()
                                if AppLockManager.shared.biometricType != .none {
                                    Text(AppLockManager.shared.biometricType.label + " + PIN")
                                        .font(.caption)
                                        .foregroundColor(.Text.tertiary)
                                }
                            }
                        }
                    }
                } header: {
                    Text("Security")
                        .accessibilityAddTraits(.isHeader)
                }
                .listRowBackground(Color.Background.secondary)
                
                // Account Section
                Section {
                    Button {
                        AuthService.shared.logout()
                    } label: {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                                .foregroundColor(.Signal.sell)
                            Text("Sign Out")
                                .foregroundColor(.Signal.sell)
                        }
                    }
                } header: {
                    Text("Account")
                        .accessibilityAddTraits(.isHeader)
                }
                .listRowBackground(Color.Background.secondary)
                
                // About Section
                Section {
                    HStack {
                        Text("Version")
                            .foregroundColor(.Text.primary)
                        Spacer()
                        Text(appVersion)
                            .foregroundColor(.Text.secondary)
                    }
                    
                    NavigationLink {
                        LegalView()
                    } label: {
                        Text("Legal & Privacy")
                            .foregroundColor(.Text.primary)
                    }
                    
                    Button {
                        appState.resetOnboarding()
                    } label: {
                        Text("Reset Onboarding")
                            .foregroundColor(.Brand.primary)
                    }
                } header: {
                    Text("About")
                        .accessibilityAddTraits(.isHeader)
                }
                .listRowBackground(Color.Background.secondary)
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(Color.Background.primary)
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .refreshable {
                // Re-sync settings from UserDefaults
                viewModel.reload()
            }
            .alert("Switch to Live Trading?", isPresented: $showLiveTradingAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Enable Live Trading", role: .destructive) {
                    appState.isPaperTrading = false
                }
            } message: {
                Text("Live trading uses real money from your connected broker account. Make sure you understand the risks before proceeding.\n\nYou can switch back to paper trading at any time.")
            }
            .alert("Reset Paper Portfolio?", isPresented: $showResetAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Reset", role: .destructive) {
                    Task {
                        await viewModel.resetPortfolio()
                    }
                }
            } message: {
                Text("This will clear all paper trading positions and reset your virtual cash to $100,000. This cannot be undone.")
            }
            .sheet(isPresented: $showPinSetup) {
                PinSetupView(lockManager: AppLockManager.shared)
            }
        }
    }
}

// MARK: - Settings ViewModel

@MainActor
class SettingsViewModel: ObservableObject {
    @Published var riskTolerance: RiskTolerance {
        didSet {
            UserDefaults.standard.set(riskTolerance.rawValue, forKey: "riskTolerance")
            // REC-126: Sync to backend
            syncPreferencesToBackend()
        }
    }
    
    @Published var weeklyScoreAlerts: Bool {
        didSet {
            UserDefaults.standard.set(weeklyScoreAlerts, forKey: "weeklyScoreAlerts")
            NotificationService.shared.scheduleWeeklyScoreUpdate()
        }
    }
    
    @Published var tradeConfirmations: Bool {
        didSet {
            UserDefaults.standard.set(tradeConfirmations, forKey: "tradeConfirmations")
        }
    }
    
    @Published var scoreAlerts: Bool {
        didSet {
            UserDefaults.standard.set(scoreAlerts, forKey: "scoreAlerts")
        }
    }
    
    @Published var isIBKRConnected = false
    
    private var ibkrCancellable: AnyCancellable?
    
    init() {
        let riskString = UserDefaults.standard.string(forKey: "riskTolerance") ?? "Moderate"
        self.riskTolerance = RiskTolerance(rawValue: riskString) ?? .moderate
        self.weeklyScoreAlerts = UserDefaults.standard.bool(forKey: "weeklyScoreAlerts")
        self.tradeConfirmations = UserDefaults.standard.bool(forKey: "tradeConfirmations")
        self.scoreAlerts = UserDefaults.standard.bool(forKey: "scoreAlerts")
        
        // Set defaults if first launch
        if !UserDefaults.standard.bool(forKey: "settingsInitialized") {
            weeklyScoreAlerts = true
            tradeConfirmations = true
            scoreAlerts = false
            UserDefaults.standard.set(true, forKey: "settingsInitialized")
        }
        
        // Sync IBKR connection state
        self.isIBKRConnected = IBKRService.shared.isConnected
        ibkrCancellable = IBKRService.shared.$isConnected
            .receive(on: RunLoop.main)
            .assign(to: \.isIBKRConnected, on: self)
    }
    
    func reload() {
        let riskString = UserDefaults.standard.string(forKey: "riskTolerance") ?? "Moderate"
        self.riskTolerance = RiskTolerance(rawValue: riskString) ?? .moderate
        self.weeklyScoreAlerts = UserDefaults.standard.bool(forKey: "weeklyScoreAlerts")
        self.tradeConfirmations = UserDefaults.standard.bool(forKey: "tradeConfirmations")
        self.scoreAlerts = UserDefaults.standard.bool(forKey: "scoreAlerts")
    }
    
    func resetPortfolio() async {
        do {
            _ = try await APIService.shared.resetPortfolio()
        } catch {
            #if DEBUG
            debugError(error, context: "Reset")
            #endif
        }
    }
    
    func clearCache() {
        // Clear URL cache
        URLCache.shared.removeAllCachedResponses()
        
        // Clear disk cache (SigilAPICache) — BUG-024 fix
        if let cachesURL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first {
            let apiCache = cachesURL.appendingPathComponent("SigilAPICache")
            try? FileManager.default.removeItem(at: apiCache)
        }
    }
    
    // MARK: - REC-126: Sync Preferences to Backend
    
    func syncPreferencesToBackend() {
        // Only sync if authenticated
        guard AuthService.shared.isLoggedIn else { return }
        
        Task {
            do {
                _ = try await APIService.shared.updatePreferences(
                    riskTolerance: riskTolerance.rawValue.lowercased(),
                    portfolioSize: nil  // Portfolio size handled by AppState
                )
            } catch {
                #if DEBUG
                debugError(error, context: "Failed to sync preferences")
                #endif
            }
        }
    }
    
    func loadPreferencesFromBackend() async {
        // Only load if authenticated
        guard AuthService.shared.isLoggedIn else { return }
        
        do {
            let prefs = try await APIService.shared.getPreferences()
            
            // Update local state from backend
            if let riskStr = prefs.riskTolerance,
               let risk = RiskTolerance(rawValue: riskStr.capitalized) {
                self.riskTolerance = risk
                UserDefaults.standard.set(risk.rawValue, forKey: "riskTolerance")
            }
        } catch {
            #if DEBUG
            debugError(error, context: "Failed to load preferences")
            #endif
        }
    }
}

// MARK: - Risk Tolerance

enum RiskTolerance: String, CaseIterable {
    case conservative = "Conservative"
    case moderate = "Moderate"
    case aggressive = "Aggressive"
    
    var description: String {
        switch self {
        case .conservative:
            return "Lower risk, focus on stable blue-chip stocks. Max 5% per position."
        case .moderate:
            return "Balanced approach with mix of growth and value. Max 10% per position."
        case .aggressive:
            return "Higher risk, focus on high-growth opportunities. Max 15% per position."
        }
    }
}

// MARK: - IBKR Connection View

struct IBKRConnectionView: View {
    @ObservedObject private var ibkrService = IBKRService.shared
    @State private var showRiskDisclosure = false
    @State private var showDisconnectAlert = false
    @State private var connectionError: String?
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            if ibkrService.isConnected {
                // Connected state
                Image(systemName: "checkmark.circle.fill")
                    .font(.iconSize(80)).limitedScaling()
                    .foregroundColor(.Signal.buy)
                
                Text("Connected to IBKR")
                    .font(.title2.bold())
                    .foregroundColor(.Text.primary)
                
                // Account info
                VStack(spacing: 12) {
                    HStack {
                        Text("Account ID")
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        Text(ibkrService.accountId ?? "—")
                            .font(.subheadline.monospacedDigit())
                            .foregroundColor(.Text.primary)
                    }
                    
                    Divider().background(Color.Utility.divider)
                    
                    HStack {
                        Text("Account Type")
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        Text(ibkrService.isPaperAccount ? "Paper" : "Live")
                            .font(.subheadline.bold())
                            .foregroundColor(ibkrService.isPaperAccount ? .Signal.hold : .Signal.sell)
                    }
                    
                    Divider().background(Color.Utility.divider)
                    
                    HStack {
                        Text("Status")
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        HStack(spacing: 6) {
                            Circle()
                                .fill(Color.Signal.buy)
                                .frame(width: 8, height: 8)
                            Text("Active")
                                .font(.subheadline)
                                .foregroundColor(.Signal.buy)
                        }
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                .padding(.horizontal)
                
                Spacer()
                
                Button("Disconnect") {
                    showDisconnectAlert = true
                }
                .foregroundColor(.Signal.sell)
                .padding(.vertical, 10)
                .padding(.horizontal, 20)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.Signal.sell, lineWidth: 1))
                .padding(.bottom, 20)
            } else {
                // Disconnected state
                Image(systemName: "link.circle")
                    .font(.iconSize(80)).limitedScaling()
                    .foregroundColor(.Brand.primary)
                
                Text("Connect to Interactive Brokers")
                    .font(.title2.bold())
                    .foregroundColor(.Text.primary)
                
                Text("Link your IBKR account to enable live trading with real money.")
                    .font(.body)
                    .foregroundColor(.Text.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                
                VStack(alignment: .leading, spacing: 12) {
                    FeatureRow(icon: "checkmark.shield.fill", text: "Secure OAuth authentication")
                    FeatureRow(icon: "lock.fill", text: "Your credentials stay with IBKR")
                    FeatureRow(icon: "arrow.triangle.2.circlepath", text: "Sync orders and positions")
                    FeatureRow(icon: "bell.fill", text: "Real-time trade notifications")
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                .padding(.horizontal)
                
                if let error = connectionError {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Signal.sell)
                        .padding(.horizontal)
                }
                
                Spacer()
                
                VStack(spacing: 12) {
                    Button {
                        showRiskDisclosure = true
                    } label: {
                        if ibkrService.isConnecting {
                            ProgressView()
                                .tint(.white)
                                .frame(maxWidth: .infinity)
                        } else {
                            Text("Connect IBKR")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(ibkrService.isConnecting)
                    
                    Text("By connecting, you agree to our Terms of Service")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
        }
        .background(Color.Background.primary)
        .navigationTitle("IBKR Connection")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showRiskDisclosure) {
            RiskDisclosureSheet(onAccept: {
                Task {
                    await performConnect()
                }
            })
        }
        .alert("Disconnect IBKR?", isPresented: $showDisconnectAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Disconnect", role: .destructive) {
                Task {
                    try? await ibkrService.disconnect()
                }
            }
        } message: {
            Text("You will no longer be able to place live trades until you reconnect.")
        }
        .task {
            await ibkrService.refreshStatus()
        }
    }
    
    private func performConnect() async {
        connectionError = nil
        do {
            try await ibkrService.connect()
        } catch {
            connectionError = error.localizedDescription
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(.Accent.gold)
                .frame(width: 24)
            
            Text(text)
                .font(.subheadline)
                .foregroundColor(.Text.primary)
        }
    }
}

// MARK: - Risk Disclosure Sheet

struct RiskDisclosureSheet: View {
    @Environment(\.dismiss) var dismiss
    @State private var acknowledged = false
    var onAccept: (() -> Void)? = nil
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Risk Disclosure")
                        .font(.title.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text("Please read and acknowledge the following before enabling live trading:")
                        .foregroundColor(.Text.secondary)
                    
                    VStack(alignment: .leading, spacing: 16) {
                        RiskItem(
                            title: "Investment Risk",
                            text: "Trading stocks involves risk of loss. Past performance does not guarantee future results."
                        )
                        
                        RiskItem(
                            title: "AI Recommendations",
                            text: "Our AI scores are for informational purposes only and should not be considered financial advice."
                        )
                        
                        RiskItem(
                            title: "Your Responsibility",
                            text: "You are solely responsible for your trading decisions. Always do your own research."
                        )
                        
                        RiskItem(
                            title: "No Guarantees",
                            text: "We do not guarantee any specific returns or outcomes from following our recommendations."
                        )
                    }
                    
                    Toggle(isOn: $acknowledged) {
                        Text("I understand and accept these risks")
                            .font(.subheadline)
                            .foregroundColor(.Text.primary)
                    }
                    .tint(.Accent.gold)
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    Button("Continue to IBKR") {
                        onAccept?()
                        dismiss()
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(!acknowledged)
                    .opacity(acknowledged ? 1 : 0.5)
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.Accent.gold)
                }
            }
        }
    }
}

struct RiskItem: View {
    let title: String
    let text: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.Signal.hold)
                Text(title)
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
            }
            
            Text(text)
                .font(.caption)
                .foregroundColor(.Text.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.Background.secondary)
        .cornerRadius(8)
    }
}

// MARK: - Legal View

struct LegalView: View {
    var body: some View {
        List {
            Section {
                NavigationLink("Terms of Service") {
                    LegalTextView(title: "Terms of Service", content: termsOfService)
                }
                NavigationLink("Privacy Policy") {
                    LegalTextView(title: "Privacy Policy", content: privacyPolicy)
                }
                NavigationLink("Risk Disclosure") {
                    LegalTextView(title: "Risk Disclosure", content: riskDisclosure)
                }
            }
            .listRowBackground(Color.Background.secondary)
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.Background.primary)
        .navigationTitle("Legal")
        .foregroundColor(.Text.primary)
    }
    
    var termsOfService: String {
        """
        TERMS OF SERVICE

        Last updated: February 2026

        1. ACCEPTANCE OF TERMS
        By downloading, installing, or using Sigil ("the App"), you agree to be bound by these Terms of Service. If you do not agree, do not use the App.

        2. DESCRIPTION OF SERVICE
        Sigil provides AI-generated stock scores and recommendations for informational purposes only. Scores are derived from fundamental, sentiment, technical, and macroeconomic analysis of publicly available data.

        3. NOT FINANCIAL ADVICE
        All content, scores, signals, and recommendations provided by Sigil are for informational and educational purposes only. They do not constitute financial advice, investment advice, trading advice, or any other kind of advice. You should consult a qualified financial advisor before making any investment decisions.

        4. NO WARRANTIES
        The App is provided "as is" without warranties of any kind. We do not guarantee the accuracy, completeness, or timeliness of any scores, data, or analysis. Past performance does not indicate future results.

        5. PAPER TRADING
        Paper trading features simulate trades using virtual currency and do not involve real money. Live trading via Interactive Brokers is subject to IBKR's own terms and conditions.

        6. LIMITATION OF LIABILITY
        In no event shall Sigil or its creators be liable for any direct, indirect, incidental, special, or consequential damages arising from your use of the App or reliance on any information provided.

        7. USER ACCOUNTS
        You are responsible for maintaining the confidentiality of your account credentials. You agree to notify us immediately of any unauthorized use.

        8. MODIFICATIONS
        We reserve the right to modify these terms at any time. Continued use of the App after changes constitutes acceptance of the modified terms.

        9. GOVERNING LAW
        These terms shall be governed by applicable law in the jurisdiction where the service is provided.
        """
    }
    
    var privacyPolicy: String {
        """
        PRIVACY POLICY

        Last updated: February 2026

        1. INFORMATION WE COLLECT
        • Account information: email address and encrypted password
        • Usage data: app interactions, feature usage, and crash reports
        • Trading data: paper trading orders, portfolio positions, and watchlists
        • Device information: device model, OS version, and app version

        2. HOW WE USE YOUR INFORMATION
        • To provide and improve the App's functionality
        • To calculate personalized stock scores and alerts
        • To send notifications you have opted into (score alerts, trade confirmations)
        • To diagnose technical issues and improve performance

        3. DATA STORAGE
        • All data is stored locally on your device and on our secured backend servers
        • Passwords are hashed using bcrypt and never stored in plaintext
        • JWT tokens are used for authentication with automatic expiration

        4. DATA SHARING
        We do not sell, trade, or share your personal information with third parties except:
        • When required by law or legal process
        • To protect our rights or safety
        • With Interactive Brokers when you connect a live trading account (subject to their privacy policy)

        5. THIRD-PARTY SERVICES
        The App uses data from Yahoo Finance, SEC EDGAR, FRED, and news RSS feeds. Your use of the App may be subject to their respective terms.

        6. DATA RETENTION
        Account data is retained while your account is active. You may request deletion at any time through the App settings.

        7. SECURITY
        We implement industry-standard security measures including encryption, secure authentication, and biometric protection. However, no system is 100% secure.

        8. YOUR RIGHTS
        You have the right to access, correct, or delete your personal data. Contact us through the App to exercise these rights.

        9. CHANGES TO THIS POLICY
        We may update this policy periodically. We will notify you of significant changes through the App.
        """
    }
    
    var riskDisclosure: String {
        """
        RISK DISCLOSURE

        Last updated: February 2026

        IMPORTANT: Please read this disclosure carefully before using Sigil.

        1. INVESTMENT RISK
        Trading and investing in stocks involves substantial risk of loss and is not suitable for every investor. The value of stocks can fluctuate significantly, and you may lose some or all of your invested capital.

        2. AI-GENERATED SCORES
        Sigil's scores and signals are generated by artificial intelligence algorithms analyzing publicly available data. These algorithms have limitations:
        • They rely on historical data which may not predict future performance
        • Sentiment analysis may misinterpret news context
        • Technical indicators can generate false signals
        • Macro analysis may not capture sudden economic shifts

        3. NO GUARANTEE OF ACCURACY
        While we strive for accuracy, our scoring system may contain errors. Scores of 677 stocks are updated weekly and may not reflect real-time market conditions.

        4. PAPER TRADING vs LIVE TRADING
        Paper trading results are simulated and may differ from actual trading due to:
        • Market liquidity and slippage
        • Order execution timing
        • Real market impact of large orders
        • Fees and commissions

        5. INDEPENDENT JUDGMENT
        Always use your own judgment and conduct your own research. Sigil is a tool to supplement, not replace, your investment decision-making process.

        6. SEEK PROFESSIONAL ADVICE
        If you are unsure about any investment, consult a licensed financial advisor who can assess your individual circumstances, risk tolerance, and financial goals.

        BY USING SIGIL, YOU ACKNOWLEDGE THAT YOU HAVE READ AND UNDERSTOOD THIS RISK DISCLOSURE.
        """
    }
}

struct LegalTextView: View {
    let title: String
    let content: String
    
    var body: some View {
        ScrollView {
            Text(content)
                .font(.body)
                .foregroundColor(.Text.primary)
                .padding()
        }
        .background(Color.Background.primary)
        .navigationTitle(title)
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environmentObject(AppState())
}
