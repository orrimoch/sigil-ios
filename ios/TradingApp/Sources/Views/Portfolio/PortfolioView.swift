import SwiftUI
import Charts

/// F7.x: Portfolio Tab
/// Shows holdings, P&L, performance chart, and sector allocation
struct PortfolioView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = PortfolioViewModel()
    @State private var showResetConfirm = false
    @State private var selectedTab = 0
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Paper mode indicator
                    if viewModel.isPaper {
                        HStack(spacing: 8) {
                            Image(systemName: "doc.text.fill")
                            Text("PAPER PORTFOLIO")
                                .font(.caption.bold())
                        }
                        .foregroundColor(.Signal.hold)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.Signal.hold.opacity(0.15))
                        .cornerRadius(20)
                    }
                    
                    // F4.1: Portfolio Summary Card
                    PortfolioDetailSummaryCard(viewModel: viewModel)
                    
                    // Cash and positions value
                    HStack(spacing: 12) {
                        StatCard(
                            title: "Cash",
                            value: viewModel.cash.asCurrency,
                            icon: "dollarsign.circle"
                        )
                        StatCard(
                            title: "Invested",
                            value: viewModel.positionsValue.asCurrency,
                            icon: "chart.pie"
                        )
                    }
                    
                    // Tab selector for Holdings / Chart / Sectors
                    Picker("View", selection: $selectedTab) {
                        Text("Holdings").tag(0)
                        Text("Chart").tag(1)
                        Text("Sectors").tag(2)
                    }
                    .pickerStyle(.segmented)
                    
                    switch selectedTab {
                    case 0:
                        // F7.1: Holdings List
                        HoldingsSection(holdings: viewModel.holdings)
                    case 1:
                        // F7.2: Performance Chart
                        PerformanceChartSection(viewModel: viewModel)
                    case 2:
                        // F7.3: Sector Allocation
                        SectorAllocationSection(viewModel: viewModel)
                    default:
                        EmptyView()
                    }
                    
                    // Reset button (paper trading only)
                    if viewModel.isPaper {
                        Button {
                            showResetConfirm = true
                        } label: {
                            HStack {
                                Image(systemName: "arrow.counterclockwise")
                                Text("Reset Paper Portfolio")
                            }
                            .font(.subheadline)
                            .foregroundColor(.Signal.sell)
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(Color.Signal.sell.opacity(0.1))
                            .cornerRadius(12)
                        }
                    }
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Portfolio")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .refreshable {
                await viewModel.fetchAll()
            }
            .task {
                await viewModel.fetchAll()
            }
            .alert("Reset Portfolio?", isPresented: $showResetConfirm) {
                Button("Cancel", role: .cancel) {}
                Button("Reset", role: .destructive) {
                    Task {
                        await viewModel.resetPortfolio()
                    }
                }
            } message: {
                Text("This will clear all positions and reset your cash to $100,000. This cannot be undone.")
            }
        }
    }
}

// MARK: - Portfolio Detail Summary Card

struct PortfolioDetailSummaryCard: View {
    @ObservedObject var viewModel: PortfolioViewModel
    
    var body: some View {
        VStack(spacing: 16) {
            // Total value
            VStack(spacing: 4) {
                Text("Total Value")
                    .font(.subheadline)
                    .foregroundColor(.Text.tertiary)
                
                if viewModel.isLoading {
                    ProgressView()
                } else {
                    Text(viewModel.totalValue.asCurrency)
                        .font(.system(size: 36, weight: .bold, design: .monospaced))
                        .foregroundColor(.Text.primary)
                }
            }
            
            // Daily P&L
            HStack(spacing: 8) {
                let pnlIcon = viewModel.dailyPnl > 0 ? "arrow.up.right" : (viewModel.dailyPnl < 0 ? "arrow.down.right" : "minus")
                
                Image(systemName: pnlIcon)
                
                Text(abs(viewModel.dailyPnl).asCurrency)
                    .fontWeight(.semibold)
                
                Text("(\(String(format: "%+.2f", viewModel.dailyPnlPercent))%)")
            }
            .font(.body)
            .foregroundColor(viewModel.dailyPnl == 0 ? .Signal.neutral : (viewModel.dailyPnl > 0 ? .Signal.buy : .Signal.sell))
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                (viewModel.dailyPnl == 0 ? Color.Signal.neutral : (viewModel.dailyPnl > 0 ? Color.Signal.buy : Color.Signal.sell)).opacity(0.15)
            )
            .cornerRadius(20)
            
            // Total P&L
            if let summary = viewModel.summary {
                HStack {
                    let totalColor: Color = summary.totalPnl == 0 ? .Signal.neutral : (summary.totalPnl > 0 ? .Signal.buy : .Signal.sell)
                    Text("Total P&L")
                        .foregroundColor(.Text.secondary)
                    Spacer()
                    Text(summary.totalPnl.asSignedCurrency)
                        .foregroundColor(totalColor)
                    Text("(\(String(format: "%+.2f", summary.totalPnlPercent))%)")
                        .foregroundColor(totalColor)
                }
                .font(.subheadline)
            }
        }
        .padding()
        .background(Color.Background.card)
        .cornerRadius(16)
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.Text.tertiary)
                Text(title)
                    .foregroundColor(.Text.tertiary)
            }
            .font(.caption)
            
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundColor(.Text.primary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Holdings Section

struct HoldingsSection: View {
    let holdings: [Holding]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Holdings")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if holdings.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "briefcase")
                        .font(.title)
                        .foregroundColor(.Text.tertiary)
                    Text("No positions yet")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    Text("Buy stocks from the Trade tab")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 32)
            } else {
                VStack(spacing: 0) {
                    ForEach(holdings) { holding in
                        HoldingRow(holding: holding)
                        
                        if holding.id != holdings.last?.id {
                            Divider()
                                .background(Color.Border.primary)
                        }
                    }
                }
                .background(Color.Background.secondary)
                .cornerRadius(12)
            }
        }
    }
}

// MARK: - Holding Row

struct HoldingRow: View {
    let holding: Holding
    
    var body: some View {
        HStack {
            // Ticker and shares
            VStack(alignment: .leading, spacing: 2) {
                Text(holding.ticker)
                    .font(.body.bold())
                    .foregroundColor(.Text.primary)
                
                Text("\(String(format: "%.2f", holding.shares)) shares")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            // Value and P&L
            VStack(alignment: .trailing, spacing: 2) {
                Text(holding.marketValue.asCurrency)
                    .font(.body.monospacedDigit())
                    .foregroundColor(.Text.primary)
                
                HStack(spacing: 4) {
                    Text(holding.unrealizedPnl.asSignedCurrency)
                    Text("(\(String(format: "%+.1f", holding.unrealizedPnlPercent))%)")
                }
                .font(.caption)
                .foregroundColor(holding.unrealizedPnl == 0 ? .Signal.neutral : (holding.unrealizedPnl > 0 ? .Signal.buy : .Signal.sell))
            }
        }
        .padding()
    }
}

// MARK: - F7.2: Performance Chart Section

struct PerformanceChartSection: View {
    @ObservedObject var viewModel: PortfolioViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Performance")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                // Period selector
                Picker("Period", selection: $viewModel.selectedPeriod) {
                    ForEach(PerformancePeriod.allCases, id: \.self) { period in
                        Text(period.rawValue).tag(period)
                    }
                }
                .pickerStyle(.menu)
                .onChange(of: viewModel.selectedPeriod) { _, _ in
                    Task {
                        await viewModel.fetchHistory()
                    }
                }
            }
            
            if viewModel.isLoadingHistory {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else if viewModel.history.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.title)
                        .foregroundColor(.Text.tertiary)
                    Text("No history yet")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                    Text("History builds as you trade")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 32)
            } else {
                // Performance summary
                if let perf = viewModel.performance {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Period Return")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                            if let change = perf.change, let pct = perf.changePercent {
                                Text("\(change.asSignedCurrency) (\(String(format: "%+.2f", pct))%)")
                                    .font(.title3.bold())
                                    .foregroundColor(change == 0 ? .Signal.neutral : (change > 0 ? .Signal.buy : .Signal.sell))
                            }
                        }
                        Spacer()
                    }
                }
                
                // Chart
                Chart(viewModel.history) { snapshot in
                    LineMark(
                        x: .value("Date", parseDate(snapshot.timestamp)),
                        y: .value("Value", snapshot.totalValue)
                    )
                    .foregroundStyle(Color.Accent.gold)
                    
                    AreaMark(
                        x: .value("Date", parseDate(snapshot.timestamp)),
                        y: .value("Value", snapshot.totalValue)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.Accent.gold.opacity(0.3), Color.clear],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                }
                .chartYScale(domain: .automatic(includesZero: false))
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) { value in
                        AxisGridLine()
                        AxisValueLabel()
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 200)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    func parseDate(_ isoString: String) -> Date {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: isoString) ?? Date()
    }
}

// MARK: - F7.3: Sector Allocation Section

struct SectorAllocationSection: View {
    @ObservedObject var viewModel: PortfolioViewModel
    
    // Sector colors
    let sectorColors: [String: Color] = [
        "Technology": .blue,
        "Healthcare": .green,
        "Financials": .purple,
        "Consumer Cyclical": .orange,
        "Consumer Defensive": .yellow,
        "Communication Services": .pink,
        "Industrials": .gray,
        "Energy": .red,
        "Utilities": .teal,
        "Real Estate": .brown,
        "Basic Materials": .cyan,
        "Unknown": .gray,
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Sector Allocation")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if viewModel.isLoadingSectors {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else if viewModel.sectorAllocation.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "chart.pie")
                        .font(.title)
                        .foregroundColor(.Text.tertiary)
                    Text("No positions yet")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 32)
            } else {
                // Pie chart
                Chart(viewModel.sectorAllocation) { sector in
                    SectorMark(
                        angle: .value("Value", sector.percentage),
                        innerRadius: .ratio(0.5),
                        angularInset: 1.5
                    )
                    .foregroundStyle(colorForSector(sector.sector))
                    .annotation(position: .overlay) {
                        if sector.percentage > 10 {
                            Text("\(Int(sector.percentage))%")
                                .font(.caption2.bold())
                                .foregroundColor(.white)
                        }
                    }
                }
                .frame(height: 200)
                
                // Legend
                VStack(spacing: 8) {
                    ForEach(viewModel.sectorAllocation) { sector in
                        HStack {
                            Circle()
                                .fill(colorForSector(sector.sector))
                                .frame(width: 12, height: 12)
                            
                            Text(sector.sector)
                                .font(.subheadline)
                                .foregroundColor(.Text.primary)
                            
                            Spacer()
                            
                            Text(sector.value.asCurrency)
                                .font(.subheadline.monospacedDigit())
                                .foregroundColor(.Text.secondary)
                            
                            Text("\(String(format: "%.1f", sector.percentage))%")
                                .font(.subheadline.bold())
                                .foregroundColor(.Text.primary)
                                .frame(width: 50, alignment: .trailing)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    func colorForSector(_ sector: String) -> Color {
        sectorColors[sector] ?? .gray
    }
}

// MARK: - Preview

#Preview {
    PortfolioView()
        .environmentObject(AppState())
}
