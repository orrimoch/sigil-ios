import SwiftUI

/// HMM Market Regime Badge
/// Shows current market regime with color-coded badge:
/// - 🟢 low_vol: Low volatility regime
/// - 🟡 normal: Normal market conditions
/// - 🟠 high_vol: High volatility regime
/// - 🔴 crisis: Crisis/extreme conditions
struct RegimeBadge: View {
    let regime: String
    let confidence: Double?
    
    @State private var showExplainer = false
    
    init(regime: String, confidence: Double? = nil) {
        self.regime = regime.lowercased()
        self.confidence = confidence
    }
    
    private var regimeConfig: (icon: String, color: Color, label: String) {
        switch regime {
        case "low_vol", "low-vol", "lowvol":
            return ("checkmark.shield.fill", .Signal.buy, "Low Vol")
        case "normal":
            return ("equal.circle.fill", .Accent.gold, "Normal")
        case "high_vol", "high-vol", "highvol":
            return ("exclamationmark.triangle.fill", .orange, "High Vol")
        case "crisis":
            return ("exclamationmark.octagon.fill", .Signal.sell, "Crisis")
        default:
            return ("questionmark.circle.fill", .Text.tertiary, regime.capitalized)
        }
    }
    
    var body: some View {
        Button {
            showExplainer = true
        } label: {
            HStack(spacing: 6) {
                Image(systemName: regimeConfig.icon)
                    .font(.caption)
                    .foregroundColor(regimeConfig.color)
                
                Text(regimeConfig.label.uppercased())
                    .font(.caption2.bold())
                    .foregroundColor(regimeConfig.color)
                
                // Confidence indicator (optional)
                if let conf = confidence, conf > 0 {
                    Text("(\(Int(conf * 100))%)")
                        .font(.system(size: 9).monospacedDigit())
                        .foregroundColor(regimeConfig.color.opacity(0.7))
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(regimeConfig.color.opacity(0.15))
            .cornerRadius(8)
        }
        .frame(minHeight: 44)  // UX-001: Touch target
        .contentShape(Rectangle())
        .accessibilityLabel("Market regime: \(regimeConfig.label)")
        .accessibilityHint("Tap to learn about market regimes")
        .sheet(isPresented: $showExplainer) {
            RegimeExplainerView(regime: regime, regimeConfig: regimeConfig, confidence: confidence)
        }
    }
}

// MARK: - Regime Explainer Modal

struct RegimeExplainerView: View {
    let regime: String
    let regimeConfig: (icon: String, color: Color, label: String)
    let confidence: Double?
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Icon
                Image(systemName: regimeConfig.icon)
                    .font(.system(size: 60))
                    .foregroundColor(regimeConfig.color)
                
                // Current regime
                VStack(spacing: 4) {
                    Text("Market Regime")
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                    
                    Text(regimeConfig.label)
                        .font(.largeTitle.bold())
                        .foregroundColor(regimeConfig.color)
                    
                    if let conf = confidence {
                        Text("\(Int(conf * 100))% confidence")
                            .font(.subheadline)
                            .foregroundColor(.Text.tertiary)
                    }
                }
                
                Divider()
                    .padding(.horizontal)
                
                // What are regimes?
                VStack(alignment: .leading, spacing: 12) {
                    Text("Market Regimes")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("Sigil uses a Hidden Markov Model (HMM) to classify the current market environment based on volatility patterns and market behavior.")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    
                    // Regime explanations
                    VStack(alignment: .leading, spacing: 12) {
                        regimeRow(
                            icon: "checkmark.shield.fill",
                            label: "Low Vol",
                            description: "Calm markets, lower risk. Favorable for most strategies.",
                            color: .Signal.buy
                        )
                        regimeRow(
                            icon: "equal.circle.fill",
                            label: "Normal",
                            description: "Typical market conditions. Standard risk management applies.",
                            color: .Accent.gold
                        )
                        regimeRow(
                            icon: "exclamationmark.triangle.fill",
                            label: "High Vol",
                            description: "Elevated volatility. Consider reducing position sizes.",
                            color: .orange
                        )
                        regimeRow(
                            icon: "exclamationmark.octagon.fill",
                            label: "Crisis",
                            description: "Extreme conditions. Defensive positioning recommended.",
                            color: .Signal.sell
                        )
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
    
    private func regimeRow(icon: String, label: String, description: String, color: Color) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(color)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
    }
}

// MARK: - Previews

#Preview("Low Vol") {
    RegimeBadge(regime: "low_vol", confidence: 0.92)
        .padding()
        .background(Color.Background.primary)
}

#Preview("Normal") {
    RegimeBadge(regime: "normal", confidence: 0.85)
        .padding()
        .background(Color.Background.primary)
}

#Preview("High Vol") {
    RegimeBadge(regime: "high_vol", confidence: 0.78)
        .padding()
        .background(Color.Background.primary)
}

#Preview("Crisis") {
    RegimeBadge(regime: "crisis", confidence: 0.95)
        .padding()
        .background(Color.Background.primary)
}

#Preview("Regime Explainer") {
    RegimeExplainerView(
        regime: "normal",
        regimeConfig: ("equal.circle.fill", .Accent.gold, "Normal"),
        confidence: 0.85
    )
}
