import SwiftUI

/// REC-230: Portfolio Risk Badge
/// Shows risk level as a colored badge with tap for explainer modal
/// Colors: 🟢 Low (VaR<5%), 🟡 Medium (5-10%), 🔴 High (>10%)
struct RiskBadge: View {
    let riskScore: RiskScore
    @State private var showExplainer = false
    
    var body: some View {
        Button {
            showExplainer = true
        } label: {
            HStack(spacing: 4) {
                Circle()
                    .fill(riskScore.color)
                    .frame(width: 8, height: 8)
                
                Text(riskScore.label.uppercased())
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(riskScore.color)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(riskScore.color.opacity(0.15))
            .cornerRadius(12)
        }
        .frame(minHeight: 44)  // UX-001: Ensure 44pt touch target
        .contentShape(Rectangle())  // UX-001: Expand tap area
        .accessibilityLabel("Portfolio risk: \(riskScore.label)")  // UX-002: VoiceOver
        .accessibilityHint("Tap to learn more about risk levels")
        .sheet(isPresented: $showExplainer) {
            RiskExplainerView(riskScore: riskScore)
        }
    }
}

/// Risk score classification
enum RiskScore: String, Codable {
    case low
    case medium
    case high
    
    var label: String {
        rawValue.capitalized
    }
    
    var color: Color {
        switch self {
        case .low: return .Signal.buy
        case .medium: return .Accent.gold
        case .high: return .Signal.sell
        }
    }
    
    var description: String {
        switch self {
        case .low:
            return "Your portfolio has relatively low volatility. Daily losses are expected to stay under 5% most of the time."
        case .medium:
            return "Your portfolio has moderate volatility. Daily losses could be 5-10% in adverse conditions."
        case .high:
            return "Your portfolio has elevated volatility. Consider diversifying or reducing position sizes to manage risk."
        }
    }
    
    var icon: String {
        switch self {
        case .low: return "shield.checkmark.fill"
        case .medium: return "exclamationmark.triangle.fill"
        case .high: return "exclamationmark.octagon.fill"
        }
    }
}

/// REC-230: Risk Explainer Modal
/// Explains what the risk score means
struct RiskExplainerView: View {
    let riskScore: RiskScore
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Icon
                Image(systemName: riskScore.icon)
                    .font(.system(size: 60))
                    .foregroundColor(riskScore.color)
                
                // Title
                Text("\(riskScore.label) Risk")
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.Text.primary)
                
                // Description
                Text(riskScore.description)
                    .font(.body)
                    .foregroundColor(.Text.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                
                Divider()
                    .padding(.horizontal)
                
                // What is VaR?
                VStack(alignment: .leading, spacing: 12) {
                    Text("What is VaR?")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("Value at Risk (VaR) estimates the maximum expected loss with 95% confidence over one day. It's based on historical volatility of your holdings.")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    
                    // Risk levels
                    VStack(alignment: .leading, spacing: 8) {
                        riskLevelRow(level: .low, range: "< 5%")
                        riskLevelRow(level: .medium, range: "5% - 10%")
                        riskLevelRow(level: .high, range: "> 10%")
                    }
                    .padding(.top, 8)
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                .padding(.horizontal)
                
                Spacer()
            }
            .padding(.top, 40)
            .background(Color.Background.primary)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.Accent.gold)
                }
            }
        }
    }
    
    private func riskLevelRow(level: RiskScore, range: String) -> some View {
        HStack {
            Circle()
                .fill(level.color)
                .frame(width: 12, height: 12)
            Text(level.label)
                .foregroundColor(.Text.primary)
            Spacer()
            Text("VaR \(range)")
                .foregroundColor(.Text.tertiary)
        }
        .font(.subheadline)
        .accessibilityElement(children: .combine)  // UX-007: Combine for VoiceOver
        .accessibilityLabel("\(level.label) risk: Value at Risk \(range)")
    }
}

/// REC-231: Position Stop Distance View
/// Shows "Stop at $X (-8%)" on each position card
/// Color: green (far), yellow (within 2%), red (within 1%)
struct StopDistanceView: View {
    let stopPrice: Double
    let stopDistancePercent: Double
    let stopType: StopType
    
    enum StopType: String {
        case hard = "Stop"
        case trailing = "Trail"
    }
    
    var distanceColor: Color {
        let absDist = abs(stopDistancePercent)
        if absDist <= 1.0 {
            return .Signal.sell  // Red - within 1%
        } else if absDist <= 2.0 {
            return .Accent.gold  // Yellow - within 2%
        } else {
            return .Signal.buy   // Green - far from stop
        }
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: stopType == .hard ? "hand.raised" : "arrow.down.right")
                .font(.caption)  // UX-003: Larger font for accessibility
            
            Text("\(stopType.rawValue) at $\(stopPrice, specifier: "%.2f") (\(stopDistancePercent, specifier: "%.1f")%)")
                .font(.caption)  // UX-003: Larger font for accessibility
        }
        .foregroundColor(distanceColor)
        // UX-004: VoiceOver accessibility
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(stopType.rawValue) loss at \(String(format: "%.2f", stopPrice)) dollars, \(String(format: "%.1f", abs(stopDistancePercent))) percent from current price")
    }
}

// MARK: - Previews

#Preview("Risk Badge - Low") {
    RiskBadge(riskScore: .low)
        .padding()
        .background(Color.Background.primary)
}

#Preview("Risk Badge - High") {
    RiskBadge(riskScore: .high)
        .padding()
        .background(Color.Background.primary)
}

#Preview("Stop Distance") {
    VStack(spacing: 16) {
        StopDistanceView(stopPrice: 170.66, stopDistancePercent: -8.0, stopType: .hard)
        StopDistanceView(stopPrice: 178.65, stopDistancePercent: -1.5, stopType: .trailing)
        StopDistanceView(stopPrice: 180.00, stopDistancePercent: -0.8, stopType: .hard)
    }
    .padding()
    .background(Color.Background.primary)
}

#Preview("Risk Explainer") {
    RiskExplainerView(riskScore: .medium)
}
