import SwiftUI

/// REC-155: Trading Performance Statistics View
struct PerformanceStatsView: View {
    @State private var stats: PerformanceStats?
    @State private var isLoading = true
    @State private var error: String?
    @State private var selectedPeriod = 30
    
    let periods = [7, 30, 90, 365]
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Period picker
                periodPicker
                
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else if let stats = stats {
                    statsContent(stats)
                } else {
                    emptyView
                }
            }
            .padding()
        }
        .background(Color.Background.primary)
        .navigationTitle("Performance")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadStats()
        }
        .refreshable {
            await loadStats()
        }
    }
    
    // MARK: - Components
    
    private var periodPicker: some View {
        HStack(spacing: 8) {
            ForEach(periods, id: \.self) { days in
                Button {
                    selectedPeriod = days
                    Task { await loadStats() }
                } label: {
                    Text(periodLabel(days))
                        .font(.caption.bold())
                        .foregroundColor(selectedPeriod == days ? .Background.primary : .Text.secondary)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(selectedPeriod == days ? Color.Brand.primary : Color.Background.tertiary)
                        .cornerRadius(8)
                }
            }
        }
    }
    
    private func periodLabel(_ days: Int) -> String {
        switch days {
        case 7: return "1W"
        case 30: return "1M"
        case 90: return "3M"
        case 365: return "1Y"
        default: return "\(days)D"
        }
    }
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ForEach(0..<4, id: \.self) { _ in
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.Background.secondary)
                    .frame(height: 100)
            }
        }
        .shimmer()
    }
    
    private func errorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.Signal.hold)
            Text(message)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            Button("Retry") {
                Task { await loadStats() }
            }
            .foregroundColor(.Brand.primary)
        }
        .padding()
    }
    
    private var emptyView: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.xaxis")
                .font(.largeTitle)
                .foregroundColor(.Text.tertiary)
            Text("No trades in this period")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
        }
        .padding()
    }
    
    @ViewBuilder
    private func statsContent(_ stats: PerformanceStats) -> some View {
        // Win Rate Card
        winRateCard(stats)
        
        // P&L Card
        pnlCard(stats)
        
        // Risk Metrics Card
        riskMetricsCard(stats)
        
        // Execution Quality Card (REC-156)
        executionCard(stats)
    }
    
    private func winRateCard(_ stats: PerformanceStats) -> some View {
        VStack(spacing: 16) {
            HStack {
                Text("Win Rate")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                Spacer()
            }
            
            // Win rate gauge
            HStack(spacing: 24) {
                ZStack {
                    Circle()
                        .stroke(Color.Background.tertiary, lineWidth: 8)
                    Circle()
                        .trim(from: 0, to: CGFloat(stats.winRate) / 100)
                        .stroke(
                            stats.winRate >= 50 ? Color.Signal.buy : Color.Signal.sell,
                            style: StrokeStyle(lineWidth: 8, lineCap: .round)
                        )
                        .rotationEffect(.degrees(-90))
                    
                    VStack(spacing: 2) {
                        Text("\(Int(stats.winRate))%")
                            .font(.title2.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                        Text("Win Rate")
                            .font(.caption2)
                            .foregroundColor(.Text.tertiary)
                    }
                }
                .frame(width: 100, height: 100)
                
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Circle()
                            .fill(Color.Signal.buy)
                            .frame(width: 8, height: 8)
                        Text("\(stats.winningTrades) Wins")
                            .font(.subheadline)
                            .foregroundColor(.Text.primary)
                    }
                    HStack {
                        Circle()
                            .fill(Color.Signal.sell)
                            .frame(width: 8, height: 8)
                        Text("\(stats.losingTrades) Losses")
                            .font(.subheadline)
                            .foregroundColor(.Text.primary)
                    }
                    HStack {
                        Circle()
                            .fill(Color.Text.tertiary)
                            .frame(width: 8, height: 8)
                        Text("\(stats.totalTrades) Total")
                            .font(.subheadline)
                            .foregroundColor(.Text.secondary)
                    }
                }
                
                Spacer()
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func pnlCard(_ stats: PerformanceStats) -> some View {
        VStack(spacing: 16) {
            HStack {
                Text("Profit & Loss")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                Spacer()
                Text(stats.totalPnl.asSignedCurrency)
                    .font(.headline.monospacedDigit())
                    .foregroundColor(stats.totalPnl >= 0 ? .Signal.buy : .Signal.sell)
            }
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                statTile("Avg Win", value: stats.avgWin.asCurrency, color: .Signal.buy)
                statTile("Avg Loss", value: stats.avgLoss.asCurrency, color: .Signal.sell)
                statTile("Largest Win", value: stats.largestWin.asCurrency, color: .Signal.buy)
                statTile("Largest Loss", value: stats.largestLoss.asCurrency, color: .Signal.sell)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func riskMetricsCard(_ stats: PerformanceStats) -> some View {
        VStack(spacing: 16) {
            HStack {
                Text("Risk Metrics")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                Spacer()
            }
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                VStack(spacing: 4) {
                    Text(String(format: "%.2f", stats.profitFactor))
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(stats.profitFactor >= 1 ? .Signal.buy : .Signal.sell)
                    Text("Profit Factor")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
                
                VStack(spacing: 4) {
                    Text(stats.expectancy.asSignedCurrency)
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(stats.expectancy >= 0 ? .Signal.buy : .Signal.sell)
                    Text("Expectancy")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
                
                VStack(spacing: 4) {
                    Text(String(format: "%.2f", stats.avgRiskReward))
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                    Text("Risk/Reward")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func executionCard(_ stats: PerformanceStats) -> some View {
        VStack(spacing: 16) {
            HStack {
                Text("Execution Quality")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                Spacer()
                NavigationLink {
                    SlippageDetailView()
                } label: {
                    Text("Details")
                        .font(.caption)
                        .foregroundColor(.Brand.primary)
                }
            }
            
            HStack(spacing: 24) {
                VStack(spacing: 4) {
                    Text(String(format: "%.4f%%", stats.avgSlippagePercent))
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(stats.avgSlippagePercent < 0.1 ? .Signal.buy : .Signal.hold)
                    Text("Avg Slippage")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
                
                VStack(spacing: 4) {
                    Text(stats.totalSlippageCost.asCurrency)
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(.Signal.sell)
                    Text("Total Cost")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
                
                VStack(spacing: 4) {
                    Text(String(format: "%.1fh", stats.avgHoldTimeHours))
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                    Text("Avg Hold")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func statTile(_ label: String, value: String, color: Color = .Text.primary) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.subheadline.bold().monospacedDigit())
                .foregroundColor(color)
            Text(label)
                .font(.caption2)
                .foregroundColor(.Text.tertiary)
        }
        .frame(maxWidth: .infinity)
    }
    
    // MARK: - Data Loading
    
    private func loadStats() async {
        isLoading = true
        error = nil
        
        do {
            stats = try await APIService.shared.getPerformanceStats(days: selectedPeriod)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - REC-156: Slippage Detail View

struct SlippageDetailView: View {
    @State private var records: [SlippageRecord] = []
    @State private var isLoading = true
    
    var body: some View {
        List {
            if isLoading {
                ForEach(0..<5, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.Background.tertiary)
                        .frame(height: 60)
                }
                .shimmer()
            } else if records.isEmpty {
                Text("No limit orders with slippage data")
                    .foregroundColor(.Text.secondary)
            } else {
                ForEach(records, id: \.orderId) { record in
                    SlippageRow(record: record)
                }
            }
        }
        .listStyle(.plain)
        .background(Color.Background.primary)
        .navigationTitle("Slippage Analysis")
        .task {
            await loadSlippage()
        }
    }
    
    private func loadSlippage() async {
        do {
            records = try await APIService.shared.getSlippageAnalysis()
        } catch {
            #if DEBUG
            debugError(error, context: "Failed to load slippage")
            #endif
        }
        isLoading = false
    }
}

struct SlippageRow: View {
    let record: SlippageRecord
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(record.ticker)
                        .font(.subheadline.bold())
                    Text(record.side)
                        .font(.caption)
                        .foregroundColor(record.side == "BUY" ? .Signal.buy : .Signal.sell)
                }
                Text("\(Int(record.quantity)) shares")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 4) {
                Text(String(format: "%.4f%%", record.slippagePercent))
                    .font(.subheadline.monospacedDigit())
                    .foregroundColor(abs(record.slippagePercent) < 0.1 ? .Signal.buy : .Signal.hold)
                Text(record.costImpact.asSignedCurrency)
                    .font(.caption.monospacedDigit())
                    .foregroundColor(record.costImpact <= 0 ? .Signal.buy : .Signal.sell)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Data Models

struct PerformanceStats: Codable {
    let totalTrades: Int
    let winningTrades: Int
    let losingTrades: Int
    let winRate: Double
    let totalPnl: Double
    let avgWin: Double
    let avgLoss: Double
    let largestWin: Double
    let largestLoss: Double
    let profitFactor: Double
    let expectancy: Double
    let avgRiskReward: Double
    let avgSlippage: Double
    let avgSlippagePercent: Double
    let totalSlippageCost: Double
    let avgHoldTimeHours: Double
}

struct SlippageRecord: Codable {
    let orderId: String?
    let ticker: String
    let side: String
    let quantity: Double
    let limitPrice: Double
    let fillPrice: Double
    let slippage: Double
    let slippagePercent: Double
    let costImpact: Double
}

// MARK: - API Extension

extension APIService {
    func getPerformanceStats(days: Int) async throws -> PerformanceStats {
        guard let token = AuthService.shared.accessToken else {
            throw APIError.httpError(statusCode: 401)
        }
        
        guard let url = URL(string: "\(baseURL)/trading/performance?days=\(days)") else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        struct Response: Codable {
            let success: Bool
            let data: PerformanceStats
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Response.self, from: data).data
    }
    
    func getSlippageAnalysis() async throws -> [SlippageRecord] {
        guard let token = AuthService.shared.accessToken else {
            throw APIError.httpError(statusCode: 401)
        }
        
        guard let url = URL(string: "\(baseURL)/trading/slippage") else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        struct Response: Codable {
            let success: Bool
            let data: SlippageData
        }
        struct SlippageData: Codable {
            let records: [SlippageRecord]
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Response.self, from: data).data.records
    }
}

#Preview {
    NavigationStack {
        PerformanceStatsView()
    }
}
