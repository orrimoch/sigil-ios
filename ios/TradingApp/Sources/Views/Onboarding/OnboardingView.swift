import SwiftUI

/// F3.1: App Launch & Onboarding
/// First launch experience (4 screens, <60 sec)
/// - Skip button always visible
/// - Score system explained
/// - Portfolio size selection
/// - Paper trading enabled by default
struct OnboardingView: View {
    @EnvironmentObject var appState: AppState
    @State private var currentPage = 0
    
    private let totalPages = 4
    
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
                    
                    PaperTradingPage(isPaperTrading: $appState.isPaperTrading)
                        .tag(3)
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
        appState.completeOnboarding()
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

// MARK: - Page 4: Paper Trading

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
