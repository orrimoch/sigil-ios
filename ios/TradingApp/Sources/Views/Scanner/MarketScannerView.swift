import SwiftUI

// MARK: - REC-165: Market Scanner Screen

/// Market scanner showing top gainers, losers, most active
struct MarketScannerView: View {
    @State private var selectedScanType: ScanType = .topGainers
    @State private var results: [IBKRScannerResult] = []
    @State private var isLoading = false
    @State private var error: String?
    
    enum ScanType: String, CaseIterable {
        case topGainers = "TOP_PERC_GAIN"
        case topLosers = "TOP_PERC_LOSE"
        case mostActive = "MOST_ACTIVE"
        case hotByVolume = "HOT_BY_VOLUME"
        
        var displayName: String {
            switch self {
            case .topGainers: return "Top Gainers"
            case .topLosers: return "Top Losers"
            case .mostActive: return "Most Active"
            case .hotByVolume: return "Hot by Volume"
            }
        }
        
        var icon: String {
            switch self {
            case .topGainers: return "arrow.up.circle.fill"
            case .topLosers: return "arrow.down.circle.fill"
            case .mostActive: return "flame.fill"
            case .hotByVolume: return "waveform.path.ecg"
            }
        }
        
        var color: Color {
            switch self {
            case .topGainers: return .Signal.buy
            case .topLosers: return .Signal.sell
            case .mostActive: return .Brand.primary
            case .hotByVolume: return .purple
            }
        }
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Scan Type Picker
                ScanTypePicker(selected: $selectedScanType)
                    .padding()
                
                // Results
                ScrollView {
                    if isLoading {
                        LoadingView()
                    } else if let error = error {
                        ErrorView(message: error) {
                            Task { await loadScanner() }
                        }
                    } else if results.isEmpty {
                        ScannerEmptyView()
                    } else {
                        LazyVStack(spacing: 12) {
                            ForEach(results) { result in
                                ScannerResultRow(result: result, scanType: selectedScanType)
                            }
                        }
                        .padding()
                    }
                }
            }
            .background(Color.Background.primary)
            .navigationTitle("Market Scanner")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .refreshable {
                await loadScanner()
            }
            .onChange(of: selectedScanType) { _, _ in
                Task { await loadScanner() }
            }
            .task {
                await loadScanner()
            }
        }
    }
    
    @MainActor
    private func loadScanner() async {
        guard IBKRService.shared.isConnected else {
            error = "Not connected to IB Gateway"
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            results = try await IBKRService.shared.getScannerResults(
                scanCode: selectedScanType.rawValue,
                numRows: 20
            )
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - Scan Type Picker

private struct ScanTypePicker: View {
    @Binding var selected: MarketScannerView.ScanType
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(MarketScannerView.ScanType.allCases, id: \.self) { scanType in
                    ScanTypeButton(
                        scanType: scanType,
                        isSelected: selected == scanType
                    ) {
                        withAnimation(.spring(response: 0.3)) {
                            selected = scanType
                        }
                    }
                }
            }
        }
    }
}

private struct ScanTypeButton: View {
    let scanType: MarketScannerView.ScanType
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: scanType.icon)
                Text(scanType.displayName)
                    .font(.subheadline.bold())
            }
            .foregroundColor(isSelected ? .Background.primary : scanType.color)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(isSelected ? scanType.color : scanType.color.opacity(0.15))
            .cornerRadius(20)
        }
    }
}

// MARK: - Scanner Result Row

private struct ScannerResultRow: View {
    let result: IBKRScannerResult
    let scanType: MarketScannerView.ScanType
    
    var body: some View {
        HStack(spacing: 16) {
            // Rank Badge
            Text("#\(result.rank)")
                .font(.caption.bold())
                .foregroundColor(.Text.tertiary)
                .frame(width: 30)
            
            // Ticker
            VStack(alignment: .leading, spacing: 4) {
                Text(result.ticker)
                    .font(.headline.bold())
                    .foregroundColor(.Text.primary)
                
                Text(result.exchange)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            // Indicator (varies by scan type)
            VStack(alignment: .trailing, spacing: 4) {
                if let distance = result.distance {
                    Text(distance)
                        .font(.subheadline.bold())
                        .foregroundColor(scanType.color)
                }
                
                if let benchmark = result.benchmark {
                    Text(benchmark)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
            }
            
            // Arrow to detail
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.Text.tertiary)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Loading / Error / Empty Views

private struct LoadingView: View {
    var body: some View {
        VStack(spacing: 12) {
            ForEach(0..<10, id: \.self) { _ in
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.Background.secondary)
                    .frame(height: 70)
            }
        }
        .padding()
        .redacted(reason: .placeholder)
    }
}

private struct ErrorView: View {
    let message: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "antenna.radiowaves.left.and.right.slash")
                .font(.iconSize(50)).limitedScaling()
                .foregroundColor(.Signal.hold)
            
            Text("Scanner Unavailable")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                onRetry()
            }
            .font(.headline)
            .foregroundColor(.Brand.primary)
        }
        .padding()
    }
}

private struct ScannerEmptyView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "magnifyingglass")
                .font(.iconSize(50)).limitedScaling()
                .foregroundColor(.Text.tertiary)
            
            Text("No Results")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            Text("Try a different scan type or check back during market hours")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

#Preview {
    MarketScannerView()
}
