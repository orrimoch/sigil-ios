import SwiftUI

/// F8.x: Settings Tab
/// Account settings, IBKR connection, trading mode, notifications
struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = SettingsViewModel()
    
    // Confirmation dialogs
    @State private var showLiveTradingAlert = false
    @State private var showResetAlert = false
    @State private var showPinSetup = false
    
    var body: some View {
        NavigationStack {
            List {
                // F8.3: Trading Mode Section
                Section {
                    HStack {
                        Image(systemName: appState.isPaperTrading ? "doc.text.fill" : "dollarsign.circle.fill")
                            .foregroundColor(appState.isPaperTrading ? .Signal.hold : .Signal.sell)
                            .font(.title2)
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text(appState.isPaperTrading ? "Paper Trading" : "Live Trading")
                                .font(.headline)
                                .foregroundColor(.Text.primary)
                            
                            Text(appState.isPaperTrading ? "Simulated trades with virtual money" : "Real trades with real money")
                                .font(.caption)
                                .foregroundColor(.Text.secondary)
                        }
                        
                        Spacer()
                        
                        Button {
                            if appState.isPaperTrading {
                                // Switching to live - show warning
                                showLiveTradingAlert = true
                            } else {
                                // Switching to paper - no warning needed
                                appState.isPaperTrading = true
                            }
                        } label: {
                            Text(appState.isPaperTrading ? "Go Live" : "Paper Mode")
                                .font(.caption.bold())
                                .foregroundColor(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(appState.isPaperTrading ? Color.Signal.sell : Color.Signal.hold)
                                .cornerRadius(8)
                        }
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("Trading Mode")
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
                } footer: {
                    Text("Connect IBKR to enable live trading with real money.")
                }
                .listRowBackground(Color.Background.secondary)
                
                // F8.4: Notifications Section
                Section {
                    Toggle(isOn: $viewModel.weeklyScoreAlerts) {
                        HStack {
                            Image(systemName: "chart.bar.fill")
                                .foregroundColor(.Brand.primary)
                            VStack(alignment: .leading) {
                                Text("Weekly Score Updates")
                                    .foregroundColor(.Text.primary)
                                Text("Sundays at 7pm EST")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Brand.primary)
                    
                    Toggle(isOn: $viewModel.tradeConfirmations) {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.Brand.primary)
                            VStack(alignment: .leading) {
                                Text("Trade Confirmations")
                                    .foregroundColor(.Text.primary)
                                Text("When orders are filled")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Brand.primary)
                    
                    Toggle(isOn: $viewModel.scoreAlerts) {
                        HStack {
                            Image(systemName: "bell.badge.fill")
                                .foregroundColor(.Brand.primary)
                            VStack(alignment: .leading) {
                                Text("Score Alerts")
                                    .foregroundColor(.Text.primary)
                                Text("When watched stocks change signal")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .tint(.Brand.primary)
                } header: {
                    Text("Notifications")
                }
                .listRowBackground(Color.Background.secondary)
                
                // Data & Storage
                Section {
                    Button {
                        showResetAlert = true
                    } label: {
                        HStack {
                            Image(systemName: "arrow.counterclockwise")
                                .foregroundColor(.Signal.sell)
                            Text("Reset Paper Portfolio")
                                .foregroundColor(.Signal.sell)
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
                }
                .listRowBackground(Color.Background.secondary)
                
                // Security Section
                Section {
                    if AppLockManager.shared.isSetUp {
                        HStack {
                            Image(systemName: "lock.shield.fill")
                                .foregroundColor(.Signal.buy)
                            Text("App Lock")
                                .foregroundColor(.Text.primary)
                            Spacer()
                            Text("Enabled")
                                .foregroundColor(.Signal.buy)
                                .font(.caption)
                        }
                        
                        Button {
                            showPinSetup = true
                        } label: {
                            Text("Change PIN")
                                .foregroundColor(.Brand.primary)
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
                                    .foregroundColor(.Brand.primary)
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
                }
                .listRowBackground(Color.Background.secondary)
                
                // About Section
                Section {
                    HStack {
                        Text("Version")
                            .foregroundColor(.Text.primary)
                        Spacer()
                        Text("1.0.0 (Build 1)")
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
            print("Reset error: \(error)")
        }
    }
    
    func clearCache() {
        URLCache.shared.removeAllCachedResponses()
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
    @State private var showRiskDisclosure = false
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "link.circle")
                .font(.system(size: 80))
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
            
            Spacer()
            
            VStack(spacing: 12) {
                Button("Connect IBKR") {
                    showRiskDisclosure = true
                }
                .buttonStyle(PrimaryButtonStyle())
                
                Text("By connecting, you agree to our Terms of Service")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color.Background.primary)
        .navigationTitle("IBKR Connection")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showRiskDisclosure) {
            RiskDisclosureSheet()
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(.Brand.primary)
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
                    .tint(.Brand.primary)
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    Button("Continue to IBKR") {
                        // TODO: Open IBKR OAuth
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
                    .foregroundColor(.Brand.primary)
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
        
        By using Sigil, you agree to these terms...
        
        [Full terms would go here]
        """
    }
    
    var privacyPolicy: String {
        """
        PRIVACY POLICY
        
        Last updated: February 2026
        
        Your privacy is important to us...
        
        [Full policy would go here]
        """
    }
    
    var riskDisclosure: String {
        """
        RISK DISCLOSURE
        
        Trading stocks involves substantial risk of loss...
        
        [Full disclosure would go here]
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
                .foregroundColor(.Text.secondary)
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
