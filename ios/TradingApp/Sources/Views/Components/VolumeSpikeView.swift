import SwiftUI

// MARK: - REC-169: Volume Spike Alerts and Indicators

/// Volume spike badge for stock cards
struct VolumeSpikeBadge: View {
    let volumeRatio: Double
    let alertLevel: String?
    
    private var displayText: String {
        String(format: "%.1fx", volumeRatio)
    }
    
    private var badgeColor: Color {
        switch alertLevel?.uppercased() {
        case "HIGH": return .Signal.sell
        case "MEDIUM": return .Signal.warning
        default: return .Signal.hold
        }
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "waveform.path.ecg")
                .font(.caption2)
            Text(displayText)
                .font(.caption2.bold())
        }
        .foregroundColor(.white)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(badgeColor)
        .cornerRadius(6)
    }
}

/// Volume analysis card for stock detail
struct VolumeAnalysisCard: View {
    let ticker: String
    
    @State private var analysis: IBKRVolumeAnalysis?
    @State private var isLoading = false
    @State private var error: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.Brand.primary)
                Text("Volume Analysis")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                Spacer()
                
                if let analysis = analysis, analysis.isSpike {
                    VolumeSpikeBadge(
                        volumeRatio: analysis.volumeRatio,
                        alertLevel: analysis.alertLevel
                    )
                }
            }
            
            if isLoading {
                HStack {
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("Analyzing volume...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
            } else if let error = error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.Signal.sell)
            } else if let analysis = analysis {
                VStack(spacing: 8) {
                    HStack {
                        VolumeMetric(label: "Current", value: analysis.currentVolume)
                        Spacer()
                        VolumeMetric(label: "Avg (\(analysis.lookbackDays)d)", value: analysis.avgVolume)
                    }
                    
                    // Volume bar comparison
                    VolumeComparisonBar(
                        current: analysis.currentVolume,
                        average: analysis.avgVolume
                    )
                    
                    if analysis.isSpike {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(analysis.alertLevel == "HIGH" ? .Signal.sell : .Signal.warning)
                            Text("Volume \(analysis.volumeRatio, specifier: "%.1f")x above average")
                                .font(.caption)
                                .foregroundColor(.Text.secondary)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .task {
            await loadAnalysis()
        }
    }
    
    @MainActor
    private func loadAnalysis() async {
        guard IBKRService.shared.isConnected else {
            error = "Not connected to IB Gateway"
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            analysis = try await IBKRService.shared.getVolumeAnalysis(ticker: ticker)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

private struct VolumeMetric: View {
    let label: String
    let value: Int
    
    var formattedValue: String {
        if value >= 1_000_000 {
            return String(format: "%.1fM", Double(value) / 1_000_000)
        } else if value >= 1_000 {
            return String(format: "%.0fK", Double(value) / 1_000)
        }
        return "\(value)"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption)
                .foregroundColor(.Text.tertiary)
            Text(formattedValue)
                .font(.subheadline.bold())
                .foregroundColor(.Text.primary)
        }
    }
}

private struct VolumeComparisonBar: View {
    let current: Int
    let average: Int
    
    private var ratio: Double {
        guard average > 0 else { return 0 }
        return min(Double(current) / Double(average), 3.0) // Cap at 3x for display
    }
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background (average)
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.Background.tertiary)
                    .frame(width: geometry.size.width)
                
                // Average marker
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.Text.tertiary.opacity(0.5))
                    .frame(width: geometry.size.width / 3) // 1x mark
                
                // Current volume
                RoundedRectangle(cornerRadius: 4)
                    .fill(ratio >= 2 ? Color.Signal.sell : (ratio >= 1.5 ? Color.Signal.warning : Color.Brand.primary))
                    .frame(width: geometry.size.width * (ratio / 3))
            }
        }
        .frame(height: 8)
    }
}

/// Volume spike alerts list
struct VolumeSpikeAlertsView: View {
    let tickers: [String]
    
    @State private var spikes: [IBKRVolumeAnalysis] = []
    @State private var isLoading = false
    @State private var error: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "waveform.badge.exclamationmark")
                    .foregroundColor(.Signal.sell)
                Text("Volume Spikes")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                if !spikes.isEmpty {
                    Text("\(spikes.count)")
                        .font(.caption.bold())
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.Signal.sell)
                        .cornerRadius(10)
                }
            }
            
            if isLoading {
                HStack {
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("Scanning watchlist...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding()
            } else if let error = error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.Signal.sell)
                    .padding()
            } else if spikes.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.circle")
                        .font(.title)
                        .foregroundColor(.Signal.buy)
                    Text("No unusual volume detected")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding()
            } else {
                ForEach(spikes) { spike in
                    VolumeSpikeRow(spike: spike)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .task {
            await loadSpikes()
        }
    }
    
    @MainActor
    private func loadSpikes() async {
        guard IBKRService.shared.isConnected, !tickers.isEmpty else {
            error = tickers.isEmpty ? "No tickers in watchlist" : "Not connected to IB Gateway"
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            spikes = try await IBKRService.shared.checkWatchlistVolumeSpikes(tickers: tickers)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

private struct VolumeSpikeRow: View {
    let spike: IBKRVolumeAnalysis
    
    private var alertColor: Color {
        switch spike.alertLevel?.uppercased() {
        case "HIGH": return .Signal.sell
        case "MEDIUM": return .Signal.warning
        default: return .Signal.hold
        }
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Alert indicator
            Circle()
                .fill(alertColor)
                .frame(width: 10, height: 10)
            
            // Ticker
            Text(spike.ticker)
                .font(.headline.bold())
                .foregroundColor(.Text.primary)
            
            Spacer()
            
            // Volume ratio
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(spike.volumeRatio, specifier: "%.1f")x")
                    .font(.subheadline.bold())
                    .foregroundColor(alertColor)
                
                Text("vs avg")
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary)
            }
        }
        .padding(.vertical, 8)
    }
}

#Preview {
    VStack(spacing: 20) {
        VolumeSpikeBadge(volumeRatio: 2.5, alertLevel: "HIGH")
        
        VolumeAnalysisCard(ticker: "NVDA")
        
        VolumeSpikeAlertsView(tickers: ["AAPL", "NVDA", "TSLA"])
    }
    .padding()
    .background(Color.Background.primary)
}
