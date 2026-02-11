import SwiftUI

/// VIX Fear Gauge Indicator
/// Shows current VIX value with color coding:
/// - Green (< 15): Low volatility
/// - Yellow (15-25): Normal volatility
/// - Red (> 25): High volatility / Fear
struct VIXIndicator: View {
    let vix: Double
    let change: Double?
    let changePct: Double?
    let regime: String?
    
    @State private var showExplainer = false
    
    init(vix: Double, change: Double? = nil, changePct: Double? = nil, regime: String? = nil) {
        self.vix = vix
        self.change = change
        self.changePct = changePct
        self.regime = regime
    }
    
    private var vixColor: Color {
        if vix < 15 {
            return .Signal.buy  // Green - calm
        } else if vix < 25 {
            return .Accent.gold  // Yellow - normal
        } else {
            return .Signal.sell  // Red - fear
        }
    }
    
    private var vixLabel: String {
        if vix < 15 {
            return "Low"
        } else if vix < 25 {
            return "Normal"
        } else {
            return "High"
        }
    }
    
    var body: some View {
        Button {
            showExplainer = true
        } label: {
            HStack(spacing: 8) {
                // VIX icon
                Image(systemName: "waveform.path.ecg")
                    .font(.caption)
                    .foregroundColor(vixColor)
                
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text("VIX")
                            .font(.caption2)
                            .foregroundColor(.Text.tertiary)
                        
                        Text(String(format: "%.1f", vix))
                            .font(.caption.bold().monospacedDigit())
                            .foregroundColor(vixColor)
                    }
                    
                    // Change indicator (if available)
                    if let changePct = changePct {
                        HStack(spacing: 2) {
                            Image(systemName: changePct >= 0 ? "arrow.up" : "arrow.down")
                                .font(.system(size: 8))
                            Text(String(format: "%.1f%%", abs(changePct)))
                                .font(.system(size: 9).monospacedDigit())
                        }
                        .foregroundColor(changePct >= 0 ? .Signal.sell : .Signal.buy)
                    }
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(vixColor.opacity(0.15))
            .cornerRadius(8)
        }
        .frame(minHeight: 44)  // UX-001: Touch target
        .contentShape(Rectangle())
        .accessibilityLabel("VIX at \(String(format: "%.1f", vix)), \(vixLabel) volatility")
        .accessibilityHint("Tap to learn about VIX")
        .sheet(isPresented: $showExplainer) {
            VIXExplainerView(vix: vix, vixLabel: vixLabel, vixColor: vixColor)
        }
    }
}

// MARK: - VIX Explainer Modal

struct VIXExplainerView: View {
    let vix: Double
    let vixLabel: String
    let vixColor: Color
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Icon
                Image(systemName: "waveform.path.ecg")
                    .font(.system(size: 60))
                    .foregroundColor(vixColor)
                
                // Current value
                VStack(spacing: 4) {
                    Text("VIX")
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                    
                    Text(String(format: "%.2f", vix))
                        .font(.largeTitle.bold().monospacedDigit())
                        .foregroundColor(vixColor)
                    
                    Text(vixLabel + " Volatility")
                        .font(.subheadline)
                        .foregroundColor(vixColor)
                }
                
                Divider()
                    .padding(.horizontal)
                
                // What is VIX?
                VStack(alignment: .leading, spacing: 12) {
                    Text("What is the VIX?")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("The VIX (Volatility Index), also known as the \"Fear Gauge,\" measures expected market volatility over the next 30 days based on S&P 500 options prices.")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    
                    // Levels explanation
                    VStack(alignment: .leading, spacing: 8) {
                        vixLevelRow(range: "< 15", label: "Low", description: "Calm market, complacency", color: .Signal.buy)
                        vixLevelRow(range: "15 - 25", label: "Normal", description: "Typical volatility", color: .Accent.gold)
                        vixLevelRow(range: "> 25", label: "High", description: "Elevated fear, uncertainty", color: .Signal.sell)
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
    
    private func vixLevelRow(range: String, label: String, description: String, color: Color) -> some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 12, height: 12)
            
            Text(range)
                .font(.subheadline.monospacedDigit())
                .foregroundColor(.Text.primary)
                .frame(width: 60, alignment: .leading)
            
            Text(label)
                .font(.subheadline.bold())
                .foregroundColor(color)
                .frame(width: 60, alignment: .leading)
            
            Text(description)
                .font(.caption)
                .foregroundColor(.Text.tertiary)
        }
    }
}

// MARK: - Previews

#Preview("VIX Low") {
    VIXIndicator(vix: 12.5, changePct: -5.2)
        .padding()
        .background(Color.Background.primary)
}

#Preview("VIX Normal") {
    VIXIndicator(vix: 18.7, changePct: 2.3)
        .padding()
        .background(Color.Background.primary)
}

#Preview("VIX High") {
    VIXIndicator(vix: 32.4, changePct: 15.8)
        .padding()
        .background(Color.Background.primary)
}

#Preview("VIX Explainer") {
    VIXExplainerView(vix: 18.5, vixLabel: "Normal", vixColor: .Accent.gold)
}
