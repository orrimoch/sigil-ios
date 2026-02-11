import SwiftUI

/// Sector Concentration Warning Banner
/// Shows warning when any sector exceeds concentration threshold (default 30%)
/// Uses HHI (Herfindahl-Hirschman Index) for overall concentration
struct SectorWarningBanner: View {
    let warnings: [SectorWarning]
    let hhi: Double?
    
    @State private var showDetails = false
    
    private var hasWarnings: Bool {
        !warnings.isEmpty
    }
    
    private var concentrationLevel: ConcentrationLevel {
        if let hhi = hhi {
            if hhi > 0.25 { return .high }
            if hhi > 0.15 { return .moderate }
        }
        return warnings.isEmpty ? .healthy : .moderate
    }
    
    enum ConcentrationLevel {
        case healthy
        case moderate
        case high
        
        var color: Color {
            switch self {
            case .healthy: return .Signal.buy
            case .moderate: return .Accent.gold
            case .high: return .Signal.sell
            }
        }
        
        var icon: String {
            switch self {
            case .healthy: return "checkmark.shield.fill"
            case .moderate: return "exclamationmark.triangle.fill"
            case .high: return "exclamationmark.octagon.fill"
            }
        }
        
        var label: String {
            switch self {
            case .healthy: return "Well Diversified"
            case .moderate: return "Moderate Concentration"
            case .high: return "High Concentration"
            }
        }
    }
    
    var body: some View {
        if hasWarnings {
            Button {
                showDetails = true
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: concentrationLevel.icon)
                        .font(.title3)
                        .foregroundColor(concentrationLevel.color)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text(concentrationLevel.label)
                            .font(.subheadline.bold())
                            .foregroundColor(.Text.primary)
                        
                        // Show first warning summary
                        if let firstWarning = warnings.first {
                            Text("\(firstWarning.sector): \(Int(firstWarning.weight * 100))%")
                                .font(.caption)
                                .foregroundColor(.Text.secondary)
                        }
                    }
                    
                    Spacer()
                    
                    if warnings.count > 1 {
                        Text("+\(warnings.count - 1)")
                            .font(.caption.bold())
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(concentrationLevel.color)
                            .cornerRadius(10)
                    }
                    
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .padding()
                .background(concentrationLevel.color.opacity(0.15))
                .cornerRadius(12)
            }
            .accessibilityLabel("Sector concentration warning: \(concentrationLevel.label)")
            .accessibilityHint("Tap for details")
            .sheet(isPresented: $showDetails) {
                SectorConcentrationDetailView(warnings: warnings, hhi: hhi, level: concentrationLevel)
            }
        }
    }
}

// MARK: - Detail View

struct SectorConcentrationDetailView: View {
    let warnings: [SectorWarning]
    let hhi: Double?
    let level: SectorWarningBanner.ConcentrationLevel
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 12) {
                        Image(systemName: level.icon)
                            .font(.system(size: 50))
                            .foregroundColor(level.color)
                        
                        Text(level.label)
                            .font(.title2.bold())
                            .foregroundColor(.Text.primary)
                        
                        if let hhi = hhi {
                            Text("HHI: \(String(format: "%.3f", hhi))")
                                .font(.subheadline.monospacedDigit())
                                .foregroundColor(.Text.secondary)
                        }
                    }
                    .padding(.top)
                    
                    // Warnings list
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Concentration Warnings")
                            .font(.headline)
                            .foregroundColor(.Text.primary)
                        
                        ForEach(warnings) { warning in
                            SectorWarningRow(warning: warning)
                        }
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    // Explanation
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Why This Matters")
                            .font(.headline)
                            .foregroundColor(.Text.primary)
                        
                        Text("Sector concentration increases portfolio risk. If one sector declines significantly, it can have an outsized impact on your returns.")
                            .font(.subheadline)
                            .foregroundColor(.Text.tertiary)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Circle().fill(Color.Signal.buy).frame(width: 10, height: 10)
                                Text("< 30% per sector")
                                    .font(.caption)
                                    .foregroundColor(.Text.secondary)
                                Spacer()
                                Text("Healthy")
                                    .font(.caption.bold())
                                    .foregroundColor(.Signal.buy)
                            }
                            HStack {
                                Circle().fill(Color.Accent.gold).frame(width: 10, height: 10)
                                Text("30-40% per sector")
                                    .font(.caption)
                                    .foregroundColor(.Text.secondary)
                                Spacer()
                                Text("Monitor")
                                    .font(.caption.bold())
                                    .foregroundColor(.Accent.gold)
                            }
                            HStack {
                                Circle().fill(Color.Signal.sell).frame(width: 10, height: 10)
                                Text("> 40% per sector")
                                    .font(.caption)
                                    .foregroundColor(.Text.secondary)
                                Spacer()
                                Text("High Risk")
                                    .font(.caption.bold())
                                    .foregroundColor(.Signal.sell)
                            }
                        }
                        .padding(.top, 8)
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    // HHI Explanation
                    VStack(alignment: .leading, spacing: 8) {
                        Text("What is HHI?")
                            .font(.subheadline.bold())
                            .foregroundColor(.Text.primary)
                        
                        Text("The Herfindahl-Hirschman Index measures overall concentration. Values range from 0 (perfectly diversified) to 1 (single holding). Above 0.25 indicates high concentration.")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    Spacer()
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Sector Concentration")
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
}

// MARK: - Warning Row

struct SectorWarningRow: View {
    let warning: SectorWarning
    
    private var severityColor: Color {
        let weight = warning.weight
        if weight > 0.4 { return .Signal.sell }
        if weight > 0.3 { return .Accent.gold }
        return .Signal.buy
    }
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(warning.sector)
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
                
                Text(warning.message)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            // Weight badge
            Text("\(Int(warning.weight * 100))%")
                .font(.subheadline.bold().monospacedDigit())
                .foregroundColor(.white)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(severityColor)
                .cornerRadius(8)
        }
        .padding()
        .background(Color.Background.tertiary)
        .cornerRadius(8)
    }
}

// MARK: - VaR Display Component

/// Portfolio VaR Display
/// Shows Daily Value at Risk with percentage
struct VaRDisplay: View {
    let varDaily: Double
    let varPct: Double
    
    @State private var showExplainer = false
    
    private var varColor: Color {
        if varPct < 5 { return .Signal.buy }
        if varPct < 10 { return .Accent.gold }
        return .Signal.sell
    }
    
    var body: some View {
        Button {
            showExplainer = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "chart.bar.doc.horizontal")
                    .font(.caption)
                    .foregroundColor(varColor)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Daily VaR")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    
                    HStack(spacing: 4) {
                        Text(formatCurrency(varDaily))
                            .font(.caption.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                        
                        Text("(\(String(format: "%.1f", varPct))%)")
                            .font(.caption2.monospacedDigit())
                            .foregroundColor(varColor)
                    }
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Color.Background.tertiary)
            .cornerRadius(8)
        }
        .frame(minHeight: 44)  // Touch target
        .contentShape(Rectangle())
        .accessibilityLabel("Daily Value at Risk: \(formatCurrency(varDaily)), \(String(format: "%.1f", varPct)) percent")
        .accessibilityHint("Tap to learn about VaR")
        .sheet(isPresented: $showExplainer) {
            VaRExplainerView(varDaily: varDaily, varPct: varPct)
        }
    }
    
    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$\(Int(value))"
    }
}

// MARK: - VaR Explainer

struct VaRExplainerView: View {
    let varDaily: Double
    let varPct: Double
    @Environment(\.dismiss) private var dismiss
    
    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$\(Int(value))"
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Image(systemName: "chart.bar.doc.horizontal")
                    .font(.system(size: 60))
                    .foregroundColor(.Brand.primary)
                
                VStack(spacing: 4) {
                    Text("Daily Value at Risk")
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                    
                    Text(formatCurrency(varDaily))
                        .font(.largeTitle.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                    
                    Text("\(String(format: "%.1f", varPct))% of portfolio")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                }
                
                Divider()
                    .padding(.horizontal)
                
                VStack(alignment: .leading, spacing: 12) {
                    Text("What is VaR?")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("Value at Risk (VaR) estimates the maximum loss your portfolio might experience in one day with 95% confidence. In other words, there's only a 5% chance of losing more than this amount in a single day.")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Circle().fill(Color.Signal.buy).frame(width: 10, height: 10)
                            Text("< 5% VaR")
                                .font(.caption)
                            Spacer()
                            Text("Low Risk")
                                .font(.caption.bold())
                                .foregroundColor(.Signal.buy)
                        }
                        HStack {
                            Circle().fill(Color.Accent.gold).frame(width: 10, height: 10)
                            Text("5-10% VaR")
                                .font(.caption)
                            Spacer()
                            Text("Moderate")
                                .font(.caption.bold())
                                .foregroundColor(.Accent.gold)
                        }
                        HStack {
                            Circle().fill(Color.Signal.sell).frame(width: 10, height: 10)
                            Text("> 10% VaR")
                                .font(.caption)
                            Spacer()
                            Text("High Risk")
                                .font(.caption.bold())
                                .foregroundColor(.Signal.sell)
                        }
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
}

// MARK: - Previews

#Preview("Sector Warning") {
    SectorWarningBanner(
        warnings: [
            SectorWarning(sector: "Technology", weight: 0.42, message: "Exceeds 30% threshold"),
            SectorWarning(sector: "Healthcare", weight: 0.35, message: "Approaching concentration limit")
        ],
        hhi: 0.28
    )
    .padding()
    .background(Color.Background.primary)
}

#Preview("Single Warning") {
    SectorWarningBanner(
        warnings: [
            SectorWarning(sector: "Technology", weight: 0.38, message: "Exceeds 30% threshold")
        ],
        hhi: 0.18
    )
    .padding()
    .background(Color.Background.primary)
}

#Preview("VaR Display") {
    VaRDisplay(varDaily: 2500, varPct: 6.2)
        .padding()
        .background(Color.Background.primary)
}

#Preview("VaR Explainer") {
    VaRExplainerView(varDaily: 2500, varPct: 6.2)
}
