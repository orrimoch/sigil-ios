import SwiftUI

/// REC-317: Agent onboarding flow - 3-screen introduction when first enabling the agent
struct AgentOnboardingView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var currentPage = 0
    let onComplete: () -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // Page indicator
            HStack(spacing: 8) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(currentPage == index ? Color.Brand.primary : Color.Background.tertiary)
                        .frame(width: 8, height: 8)
                }
            }
            .padding(.top, 20)
            
            // Page content
            TabView(selection: $currentPage) {
                page1.tag(0)
                page2.tag(1)
                page3.tag(2)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            
            // Bottom button
            Button {
                if currentPage < 2 {
                    withAnimation {
                        currentPage += 1
                    }
                } else {
                    onComplete()
                    dismiss()
                }
            } label: {
                Text(currentPage < 2 ? "Continue" : "Get Started")
                    .font(.headline)
                    .foregroundColor(.Background.primary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.Brand.primary)
                    .cornerRadius(12)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
        .background(Color.Background.primary)
    }
    
    // MARK: - Page 1: Meet Your Agent
    
    private var page1: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "cpu.fill")
                .font(.system(size: 80))
                .foregroundColor(.Brand.primary)
            
            Text("Meet Your AI Agent")
                .font(.largeTitle.weight(.bold))
                .foregroundColor(.Text.primary)
                .multilineTextAlignment(.center)
            
            Text("Your personal portfolio manager powered by Claude AI. It analyzes markets, makes decisions, and executes trades — so you don't have to.")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            // Feature bullets
            VStack(alignment: .leading, spacing: 16) {
                featureRow(icon: "chart.line.uptrend.xyaxis", text: "Weekly stock analysis")
                featureRow(icon: "brain.head.profile", text: "AI-powered decisions")
                featureRow(icon: "arrow.triangle.swap", text: "Automated trading")
            }
            .padding(.top, 16)
            
            Spacer()
            Spacer()
        }
        .padding()
    }
    
    // MARK: - Page 2: How It Learns
    
    private var page2: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "lightbulb.fill")
                .font(.system(size: 80))
                .foregroundColor(.Brand.primary)
            
            Text("How It Learns")
                .font(.largeTitle.weight(.bold))
                .foregroundColor(.Text.primary)
                .multilineTextAlignment(.center)
            
            Text("The agent remembers past decisions and their outcomes. Every trade teaches it something new about the market.")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            // Learning bullets
            VStack(alignment: .leading, spacing: 16) {
                featureRow(icon: "clock.arrow.circlepath", text: "Tracks decision outcomes")
                featureRow(icon: "doc.text.magnifyingglass", text: "Analyzes what worked")
                featureRow(icon: "arrow.up.right", text: "Improves over time")
            }
            .padding(.top, 16)
            
            Spacer()
            Spacer()
        }
        .padding()
    }
    
    // MARK: - Page 3: Start Supervised
    
    private var page3: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 80))
                .foregroundColor(.Signal.buy)
            
            Text("You're in Control")
                .font(.largeTitle.weight(.bold))
                .foregroundColor(.Text.primary)
                .multilineTextAlignment(.center)
            
            Text("Start in Supervised Mode — the agent proposes trades, but you approve each one. Move to Autonomous when you're ready.")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            // Mode comparison
            VStack(spacing: 16) {
                modeCard(
                    title: "Supervised",
                    description: "Review & approve trades",
                    icon: "hand.raised.fill",
                    isRecommended: true
                )
                
                modeCard(
                    title: "Autonomous",
                    description: "Trades execute automatically",
                    icon: "bolt.fill",
                    isRecommended: false
                )
            }
            .padding(.top, 8)
            
            Spacer()
            Spacer()
        }
        .padding()
    }
    
    // MARK: - Components
    
    private func featureRow(icon: String, text: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(.Brand.primary)
                .frame(width: 32)
            
            Text(text)
                .font(.body)
                .foregroundColor(.Text.primary)
            
            Spacer()
        }
        .padding(.horizontal, 32)
    }
    
    private func modeCard(title: String, description: String, icon: String, isRecommended: Bool) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(isRecommended ? .Signal.buy : .Text.secondary)
                .frame(width: 40)
            
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    if isRecommended {
                        Text("Recommended")
                            .font(.caption2.weight(.bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.Signal.buy)
                            .cornerRadius(4)
                    }
                }
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isRecommended ? Color.Signal.buy : Color.clear, lineWidth: 1)
        )
        .padding(.horizontal, 24)
    }
}

#Preview {
    AgentOnboardingView(onComplete: {})
}
