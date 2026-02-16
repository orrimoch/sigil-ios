import SwiftUI

/// F3.1: App Launch & Onboarding (REC-272 Enhanced)
/// First launch experience (5 screens, <90 sec)
/// - Skip button always visible
/// - Score system explained
/// - Portfolio size selection
/// - IBKR account setup (optional)
/// - Paper trading enabled by default
struct OnboardingView: View {
    @EnvironmentObject var appState: AppState
    @State private var currentPage = 0
    @State private var ibkrAccountId: String = ""
    @State private var showIBKRSetup: Bool = false
    
    private let totalPages = 5
    
    var body: some View {
        ZStack {
            // Background
            Color.Background.primary
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Skip button (always visible)
                HStack {
                    Spacer()
                    Button("Skip") {
                        completeOnboarding()
                    }
                    .font(.body)
                    .foregroundColor(.Text.secondary)
                    .padding()
                }
                
                // Page content
                TabView(selection: $currentPage) {
                    WelcomePage()
                        .tag(0)
                        .accessibilityLabel("Welcome page")
                    
                    ScoreExplanationPage()
                        .tag(1)
                        .accessibilityLabel("Score explanation page")
                    
                    PortfolioSizePage(selectedSize: $appState.portfolioSize)
                        .tag(2)
                        .accessibilityLabel("Portfolio size selection page")
                    
                    // REC-272: IBKR Account Setup Page
                    IBKRSetupPage(
                        accountId: $ibkrAccountId,
                        showSetup: $showIBKRSetup
                    )
                    .tag(3)
                    .accessibilityLabel("IBKR account setup page")
                    
                    PaperTradingPage(isPaperTrading: $appState.isPaperTrading)
                        .tag(4)
                        .accessibilityLabel("Paper trading page")
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                
                // Progress indicators
                HStack(spacing: 8) {
                    ForEach(0..<totalPages, id: \.self) { index in
                        Circle()
                            .fill(index == currentPage ? Color.Accent.gold : Color.Text.tertiary)
                            .frame(width: 8, height: 8)
                    }
                }
                .padding(.vertical, 20)
                
                // Navigation buttons
                HStack(spacing: 16) {
                    if currentPage > 0 {
                        Button {
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            withAnimation {
                                currentPage -= 1
                            }
                        } label: {
                            Text("Back")
                                .font(.headline)
                                .foregroundColor(.Accent.gold)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.Background.secondary)
                                .cornerRadius(12)
                        }
                    }
                    
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        if currentPage == totalPages - 1 {
                            completeOnboarding()
                        } else {
                            withAnimation {
                                currentPage += 1
                            }
                        }
                    } label: {
                        Text(currentPage == totalPages - 1 ? "Get Started" : "Next")
                            .font(.headline)
                            .foregroundColor(.Background.primary)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.Accent.gold)
                            .cornerRadius(12)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
    }
    
    private func completeOnboarding() {
        // REC-272: Save IBKR account if configured
        if showIBKRSetup && !ibkrAccountId.isEmpty {
            Task {
                await saveIBKRConfig()
            }
        }
        appState.completeOnboarding()
    }
    
    // REC-272: Save IBKR configuration to backend
    private func saveIBKRConfig() async {
        guard !ibkrAccountId.isEmpty else { return }
        
        do {
            try await APIService.shared.saveIBKRConfig(
                accountId: ibkrAccountId,
                isPaper: ibkrAccountId.hasPrefix("DU")
            )
        } catch {
            #if DEBUG
            print("Failed to save IBKR config: \(error)")
            #endif
        }
    }
}

// MARK: - Page 1: Welcome

struct WelcomePage: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.iconSize(64))
                .limitedScaling()
                .foregroundColor(.Accent.gold)
            
            Text("Welcome to Sigil")
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundColor(.Text.primary)
            
            Text("AI-powered stock recommendations\nfor the S&P 500")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            Spacer()
            Spacer()
        }
        .padding()
    }
}

// MARK: - Page 2: Score Explanation

struct ScoreExplanationPage: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Text("How Scoring Works")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.Text.primary)
            
            VStack(alignment: .leading, spacing: 16) {
                ScoreComponentRow(
                    icon: "building.columns.fill",
                    title: "Fundamentals",
                    description: "Value, quality, and growth metrics",
                    weight: "35%"
                )
                
                ScoreComponentRow(
                    icon: "newspaper.fill",
                    title: "Sentiment",
                    description: "News and market sentiment",
                    weight: "25%"
                )
                
                ScoreComponentRow(
                    icon: "chart.xyaxis.line",
                    title: "Technical",
                    description: "Price momentum and trends",
                    weight: "20%"
                )
                
                ScoreComponentRow(
                    icon: "globe",
                    title: "Macro",
                    description: "Economic environment",
                    weight: "20%"
                )
            }
            .padding(.horizontal)
            
            // Signal explanation
            HStack(spacing: 20) {
                SignalBadge(signal: "BUY", score: "≥70", color: .Signal.buy)
                SignalBadge(signal: "HOLD", score: "40-69", color: .Signal.hold)
                SignalBadge(signal: "SELL", score: "<40", color: .Signal.sell)
            }
            .padding(.top, 20)
            
            Spacer()
        }
        .padding()
    }
}

struct ScoreComponentRow: View {
    let icon: String
    let title: String
    let description: String
    let weight: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.Accent.gold)
                .frame(width: 30)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            Text(weight)
                .font(.headline)
                .foregroundColor(.Accent.gold)
        }
    }
}

struct SignalBadge: View {
    let signal: String
    let score: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            Text(signal)
                .font(.caption.bold())
                .foregroundColor(.white)
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(color)
                .cornerRadius(8)
            
            Text(score)
                .font(.caption2)
                .foregroundColor(.Text.secondary)
        }
    }
}

// MARK: - Page 3: Portfolio Size

struct PortfolioSizePage: View {
    @Binding var selectedSize: PortfolioSize
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Text("Portfolio Size")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.Text.primary)
            
            Text("This helps us tailor recommendations\nto your investment size")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            VStack(spacing: 12) {
                ForEach(PortfolioSize.allCases, id: \.self) { size in
                    PortfolioSizeOption(
                        size: size,
                        isSelected: selectedSize == size,
                        action: {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                                selectedSize = size
                            }
                        }
                    )
                }
            }
            .padding(.horizontal)
            
            Spacer()
        }
        .padding()
    }
}

struct PortfolioSizeOption: View {
    let size: PortfolioSize
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(size.rawValue)
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text(size.description)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                
                Spacer()
                
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? .Accent.gold : .Text.tertiary)
                    .font(.title2)
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.Accent.gold : Color.clear, lineWidth: 2)
            )
        }
    }
}

// MARK: - Page 4: IBKR Setup (REC-272)

struct IBKRSetupPage: View {
    @Binding var accountId: String
    @Binding var showSetup: Bool
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "link.circle.fill")
                .font(.iconSize(60)).limitedScaling()
                .foregroundColor(.Accent.gold)
            
            Text("Interactive Brokers")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.Text.primary)
            
            Text("Connect your IBKR account for live trading\n(optional, can be set up later)")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            Toggle(isOn: $showSetup) {
                HStack {
                    Text("Configure IBKR Account")
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Text(showSetup ? "YES" : "SKIP")
                        .font(.caption.bold())
                        .foregroundColor(showSetup ? .Signal.buy : .Text.secondary)
                }
            }
            .toggleStyle(SwitchToggleStyle(tint: .Accent.gold))
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .padding(.horizontal)
            
            if showSetup {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Account ID")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    
                    // LOW FIX ONB-002: Custom styled TextField for Institutional Dark theme
                    TextField("e.g., DU1234567 or U1234567", text: $accountId)
                        .padding(12)
                        .background(Color.Background.secondary)
                        .cornerRadius(8)
                        .foregroundColor(.Text.primary)
                        .autocapitalization(.allCharacters)
                        .disableAutocorrection(true)
                        .keyboardType(.asciiCapable)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.Accent.gold.opacity(0.3), lineWidth: 1)
                        )
                    
                    if accountId.hasPrefix("DU") {
                        HStack {
                            Image(systemName: "checkmark.shield.fill")
                                .foregroundColor(.Signal.hold)
                            Text("Paper trading account detected")
                                .font(.caption)
                                .foregroundColor(.Signal.hold)
                        }
                    } else if accountId.hasPrefix("U") && accountId.count >= 6 {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.Signal.sell)
                            Text("Live trading account - use carefully")
                                .font(.caption)
                                .foregroundColor(.Signal.sell)
                        }
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                .padding(.horizontal)
                
                Text("Your account ID is stored securely in Keychain\nand is never shared with third parties.")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                    .multilineTextAlignment(.center)
            }
            
            Spacer()
        }
        .padding()
    }
}

// MARK: - Page 5: Paper Trading

struct PaperTradingPage: View {
    @Binding var isPaperTrading: Bool
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "doc.text.fill")
                .font(.iconSize(60)).limitedScaling()
                .foregroundColor(.Accent.gold)
            
            Text("Paper Trading")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.Text.primary)
            
            Text("Practice with virtual money before\ntrading with real funds")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            Toggle(isOn: $isPaperTrading) {
                HStack {
                    Text("Enable Paper Trading")
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Text(isPaperTrading ? "ON" : "OFF")
                        .font(.caption.bold())
                        .foregroundColor(isPaperTrading ? .Signal.buy : .Text.secondary)
                }
            }
            .toggleStyle(SwitchToggleStyle(tint: .Accent.gold))
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .padding(.horizontal)
            
            if isPaperTrading {
                HStack {
                    Image(systemName: "checkmark.shield.fill")
                        .foregroundColor(.Signal.buy)
                    Text("Recommended for beginners")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
            }
            
            Spacer()
        }
        .padding()
    }
}

// MARK: - Preview

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
