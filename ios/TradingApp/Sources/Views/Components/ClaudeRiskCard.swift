import SwiftUI

/// Claude AI Risk Analysis Card
/// Displays AI-powered risk assessment for a stock including:
/// - Risk score (0-100)
/// - Risk level badge
/// - Risk factors list
/// - Recommendation with reasoning
struct ClaudeRiskCard: View {
    let riskScore: Int
    let riskLevel: String
    let riskFactors: [RiskFactor]
    let recommendation: String
    let reasoning: String
    
    @State private var isExpanded = true
    
    private var riskColor: Color {
        switch riskLevel.lowercased() {
        case "low":
            return .Signal.buy
        case "medium":
            return .Accent.gold
        case "high":
            return .Signal.sell
        case "very_high", "veryhigh", "very high":
            return .red
        default:
            return .Text.tertiary
        }
    }
    
    private var recommendationIcon: String {
        switch recommendation.lowercased() {
        case "buy", "strong_buy":
            return "arrow.up.circle.fill"
        case "sell", "strong_sell":
            return "arrow.down.circle.fill"
        case "hold", "monitor":
            return "equal.circle.fill"
        case "reduce":
            return "minus.circle.fill"
        default:
            return "questionmark.circle.fill"
        }
    }
    
    private var recommendationColor: Color {
        switch recommendation.lowercased() {
        case "buy", "strong_buy":
            return .Signal.buy
        case "sell", "strong_sell":
            return .Signal.sell
        case "hold", "monitor":
            return .Accent.gold
        case "reduce":
            return .orange
        default:
            return .Text.tertiary
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header with collapse toggle
            Button {
                withAnimation {
                    isExpanded.toggle()
                }
            } label: {
                HStack {
                    Image(systemName: "brain.head.profile")
                        .font(.headline)
                        .foregroundColor(.Brand.primary)
                    
                    Text("AI Risk Analysis")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.Text.secondary)
                }
            }
            
            if isExpanded {
                // Risk Score and Level
                HStack(alignment: .top, spacing: 16) {
                    // Score circle
                    ZStack {
                        Circle()
                            .stroke(Color.Background.tertiary, lineWidth: 8)
                            .frame(width: 80, height: 80)
                        
                        Circle()
                            .trim(from: 0, to: CGFloat(riskScore) / 100)
                            .stroke(riskColor, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                            .frame(width: 80, height: 80)
                            .rotationEffect(.degrees(-90))
                        
                        VStack(spacing: 0) {
                            Text("\(riskScore)")
                                .font(.title2.bold().monospacedDigit())
                                .foregroundColor(.Text.primary)
                            
                            Text("Risk")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                    
                    VStack(alignment: .leading, spacing: 8) {
                        // Risk level badge
                        Text(riskLevel.uppercased())
                            .font(.caption.bold())
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(riskColor)
                            .cornerRadius(6)
                        
                        // Recommendation
                        HStack(spacing: 6) {
                            Image(systemName: recommendationIcon)
                                .foregroundColor(recommendationColor)
                            
                            Text(recommendation.replacingOccurrences(of: "_", with: " ").capitalized)
                                .font(.subheadline.bold())
                                .foregroundColor(recommendationColor)
                        }
                    }
                    
                    Spacer()
                }
                
                Divider()
                    .background(Color.Utility.divider)
                
                // Risk Factors
                if !riskFactors.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Risk Factors")
                            .font(.subheadline.bold())
                            .foregroundColor(.Text.primary)
                        
                        ForEach(riskFactors) { factor in
                            RiskFactorRow(factor: factor)
                        }
                    }
                    
                    Divider()
                        .background(Color.Utility.divider)
                }
                
                // Reasoning
                if !reasoning.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 6) {
                            Image(systemName: "lightbulb.fill")
                                .font(.caption)
                                .foregroundColor(.Brand.accent)
                            
                            Text("Analysis")
                                .font(.subheadline.bold())
                                .foregroundColor(.Text.primary)
                        }
                        
                        Text(reasoning)
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                            .lineSpacing(2)
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("AI Risk Analysis: Risk score \(riskScore), level \(riskLevel), recommendation \(recommendation)")
    }
}

// MARK: - Risk Factor Row

struct RiskFactorRow: View {
    let factor: RiskFactor
    
    private var impactColor: Color {
        switch factor.impact.lowercased() {
        case "high", "severe":
            return .Signal.sell
        case "medium", "moderate":
            return .Accent.gold
        case "low", "minor":
            return .Signal.buy
        default:
            return .Text.tertiary
        }
    }
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Circle()
                .fill(impactColor)
                .frame(width: 8, height: 8)
                .padding(.top, 4)
            
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(factor.factor)
                        .font(.caption)
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Text(factor.impact.uppercased())
                        .font(.system(size: 9).bold())
                        .foregroundColor(impactColor)
                }
                
                if let desc = factor.description, !desc.isEmpty {
                    Text(desc)
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
            }
        }
    }
}

// MARK: - Loading State

struct ClaudeRiskCardLoading: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(.headline)
                    .foregroundColor(.Brand.primary)
                
                Text("AI Risk Analysis")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
            }
            
            VStack(spacing: 8) {
                HStack {
                    Spacer()
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("AI Analysis in progress...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Spacer()
                }
                Text("This may take up to 30 seconds")
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary.opacity(0.7))
            }
            .padding(.vertical, 20)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Error State

struct ClaudeRiskCardError: View {
    let error: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(.headline)
                    .foregroundColor(.Brand.primary)
                
                Text("AI Risk Analysis")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
            }
            
            VStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle")
                    .font(.title)
                    .foregroundColor(.Signal.hold)
                
                Text(error)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                    .multilineTextAlignment(.center)
                
                Button("Retry") {
                    onRetry()
                }
                .font(.caption.bold())
                .foregroundColor(.Brand.primary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Previews

#Preview("Risk Card - Medium") {
    ClaudeRiskCard(
        riskScore: 45,
        riskLevel: "medium",
        riskFactors: [
            RiskFactor(factor: "High P/E Ratio", impact: "medium", description: "Trading at 35x earnings, above sector average"),
            RiskFactor(factor: "Concentrated Position", impact: "high", description: "Represents 12% of portfolio"),
            RiskFactor(factor: "Earnings Volatility", impact: "low", description: nil)
        ],
        recommendation: "monitor",
        reasoning: "AAPL shows moderate risk characteristics. The elevated valuation and portfolio concentration warrant monitoring, but strong fundamentals and cash position provide downside protection."
    )
    .padding()
    .background(Color.Background.primary)
}

#Preview("Risk Card - High") {
    ClaudeRiskCard(
        riskScore: 78,
        riskLevel: "high",
        riskFactors: [
            RiskFactor(factor: "Negative Cash Flow", impact: "high", description: "Burning $50M/quarter"),
            RiskFactor(factor: "High Short Interest", impact: "high", description: "18% of float")
        ],
        recommendation: "reduce",
        reasoning: "Elevated risk profile suggests reducing exposure."
    )
    .padding()
    .background(Color.Background.primary)
}

#Preview("Risk Card - Loading") {
    ClaudeRiskCardLoading()
        .padding()
        .background(Color.Background.primary)
}

#Preview("Risk Card - Error") {
    ClaudeRiskCardError(error: "Unable to analyze. Try again.") {}
        .padding()
        .background(Color.Background.primary)
}
