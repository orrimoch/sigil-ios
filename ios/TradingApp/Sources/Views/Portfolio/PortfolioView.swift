import SwiftUI
import Charts

/// F7.x: Portfolio Tab
/// Shows holdings, P&L, performance chart, and sector allocation
struct PortfolioView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = PortfolioViewModel()
    @State private var showResetConfirm = false
    @State private var showSellAllConfirm = false  // REC-177: Sell all portfolio
    @State private var selectedTab = 0
    @State private var autoRefreshEnabled = true  // REC-149: Live P&L updates
    
    // REC-149: Auto-refresh timer (every 10 seconds when enabled)
    private let refreshTimer = Timer.publish(every: 10, on: .main, in: .common).autoconnect()
    
    var body: some View {
        NavigationStack {
            Group {
                if let error = viewModel.error, viewModel.holdings.isEmpty && !viewModel.isLoading {
                    ErrorStateView(
                        title: "Something went wrong",
                        message: error,
                        retryAction: {
                            Task { await viewModel.fetchAll() }
                        }
                    )
                } else {
            ScrollView {
                VStack(spacing: 20) {
                    // M3: Paper mode indicator — subtle inline style
                    if viewModel.isPaper {
                        HStack(spacing: 6) {
                            Image(systemName: "doc.text.fill")
                                .font(.caption2)
                            Text("PAPER")
                                .font(.caption2.bold())
                        }
                        .foregroundColor(.Signal.hold)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(Color.Signal.hold.opacity(0.10))
                        .cornerRadius(12)
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
                    
                    // Tab selector for Holdings / Chart / Sectors / History
                    Picker("View", selection: $selectedTab) {
                        Text("Holdings").tag(0)
                        Text("Chart").tag(1)
                        Text("Sectors").tag(2)
                        if IBKRService.shared.isConnected {
                            Text("History").tag(3)
                        }
                    }
                    .pickerStyle(.segmented)
                    
                    switch selectedTab {
                    case 0:
                        // F7.1: Holdings List
                        HoldingsSection(holdings: viewModel.holdings, onSellAll: {
                            showSellAllConfirm = true
                        })
                    case 1:
                        // F7.2: Performance Chart
                        PerformanceChartSection(viewModel: viewModel)
                    case 2:
                        // F7.3: Sector Allocation
                        SectorAllocationSection(viewModel: viewModel)
                    case 3:
                        // REC-167: Trade History from IB
                        TradeHistoryContent()
                    default:
                        EmptyView()
                    }
                    
                    // M17: Reset button (paper trading only) — text-only, less prominent
                    if viewModel.isPaper {
                        Button {
                            showResetConfirm = true
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "arrow.counterclockwise")
                                Text("Reset Paper Portfolio")
                            }
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                        }
                        .padding(.top, 8)
                    }
                }
                .padding()
            }
            .background(Color.Background.primary)
                } // else
            } // Group
            .navigationTitle("Portfolio")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                // REC-155: Performance stats button
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        PerformanceStatsView()
                    } label: {
                        Image(systemName: "chart.bar.doc.horizontal")
                            .foregroundColor(.Brand.primary)
                    }
                }
            }
            .overlay {
                if viewModel.isLoading && viewModel.holdings.isEmpty && viewModel.error == nil {
                    ScrollView {
                        VStack(spacing: 16) {
                            // Portfolio value skeleton
                            VStack(alignment: .leading, spacing: 8) {
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 120, height: 14)
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 180, height: 32)
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 100, height: 14)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(Color.Background.secondary)
                            .cornerRadius(12)
                            .padding(.horizontal)
                            
                            // Holdings skeleton
                            VStack(spacing: 0) {
                                ForEach(0..<3, id: \.self) { _ in
                                    HStack {
                                        VStack(alignment: .leading, spacing: 4) {
                                            RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 50, height: 16)
                                            RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 80, height: 12)
                                        }
                                        Spacer()
                                        VStack(alignment: .trailing, spacing: 4) {
                                            RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 70, height: 16)
                                            RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 50, height: 12)
                                        }
                                    }
                                    .padding(.horizontal)
                                    .padding(.vertical, 12)
                                }
                            }
                            .background(Color.Background.secondary)
                            .cornerRadius(12)
                            .padding(.horizontal)
                        }
                        .shimmer()
                        .padding(.vertical)
                    }
                    .background(Color.Background.primary)
                }
            }
            .refreshable {
                await viewModel.fetchAll()
            }
            .task {
                await viewModel.fetchAll()
            }
            // REC-149: Auto-refresh P&L every 10 seconds
            .onReceive(refreshTimer) { _ in
                guard autoRefreshEnabled else { return }
                Task {
                    await viewModel.fetchAll()
                }
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
            // REC-177: Sell All Portfolio confirmation
            .alert("Sell All Positions?", isPresented: $showSellAllConfirm) {
                Button("Cancel", role: .cancel) {}
                Button("Sell All", role: .destructive) {
                    Task {
                        await sellAllPositions()
                    }
                }
            } message: {
                Text("This will create MARKET SELL orders for all \(viewModel.holdings.count) position(s). Orders will execute immediately at current market prices.")
            }
        }
    }
    
    // REC-177: Sell all positions
    private func sellAllPositions() async {
        let api = APIService.shared
        
        for holding in viewModel.holdings where holding.shares > 0 {
            do {
                _ = try await api.createOrder(
                    ticker: holding.ticker,
                    side: "SELL",
                    quantity: holding.shares,
                    orderType: "MARKET",
                    limitPrice: nil
                )
            } catch {
                print("Failed to sell \(holding.ticker): \(error)")
            }
        }
        
        // Refresh portfolio after selling
        await viewModel.fetchAll()
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
                    // H1: 32pt to match HomeView's .monoLarge
                    Text(viewModel.totalValue.asCurrency)
                        .font(.monoLarge)
                        .limitedScaling()
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
    var onSellAll: (() -> Void)? = nil  // REC-177: Sell all callback
    
    /// M8: Holdings sorted by market value (largest first)
    private var sortedHoldings: [Holding] {
        holdings.sorted { $0.marketValue > $1.marketValue }
    }
    
    /// Portfolio weight for a holding
    private func weight(for holding: Holding) -> Double {
        let total = holdings.reduce(0) { $0 + $1.marketValue }
        guard total > 0 else { return 0 }
        return holding.marketValue / total * 100
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Holdings")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                // REC-177: Sell All button (only show if holdings exist)
                if !holdings.isEmpty, let sellAll = onSellAll {
                    Button {
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        sellAll()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.down.circle.fill")
                                .font(.caption)
                            Text("Sell All")
                                .font(.caption.bold())
                        }
                        .foregroundColor(.Signal.sell)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color.Signal.sell.opacity(0.15))
                        .cornerRadius(8)
                    }
                }
            }
            
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
                    ForEach(sortedHoldings) { holding in
                        // H6: Navigate to stock detail on tap
                        NavigationLink {
                            StockDetailView(ticker: holding.ticker)
                        } label: {
                            HoldingRow(holding: holding, portfolioWeight: weight(for: holding))
                        }
                        .accessibilityElement(children: .combine)
                        
                        if holding.id != sortedHoldings.last?.id {
                            // M9/L9: Use .Utility.divider for consistency
                            Divider()
                                .background(Color.Utility.divider)
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
    /// M7: Portfolio weight percentage
    var portfolioWeight: Double = 0
    
    var body: some View {
        HStack {
            // Ticker and shares
            VStack(alignment: .leading, spacing: 2) {
                Text(holding.ticker)
                    .font(.body.bold())
                    .foregroundColor(.Text.primary)
                
                // M7: Show shares count and cost basis
                Text("\(String(format: "%.2f", holding.shares)) shares · avg \(holding.avgCost.asCurrency)")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            // Value and P&L
            VStack(alignment: .trailing, spacing: 2) {
                HStack(spacing: 4) {
                    Text(holding.marketValue.asCurrency)
                        .font(.body.monospacedDigit())
                        .foregroundColor(.Text.primary)
                    
                    // M7: Portfolio weight
                    if portfolioWeight > 0 {
                        Text("\(String(format: "%.0f", portfolioWeight))%")
                            .font(.caption2)
                            .foregroundColor(.Text.tertiary)
                    }
                }
                
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
    @State private var selectedPortfolioPoint: (date: Date, value: Double)?
    @State private var portfolioTouchLocation: CGFloat?
    @State private var portfolioHapticTriggered = false
    
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
                // L13: More encouraging empty state CTA
                VStack(spacing: 8) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.title)
                        .foregroundColor(.Text.tertiary)
                    Text("No performance data yet")
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                    Text("Start trading to see your performance")
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
                
                // H10: Portfolio performance chart intentionally uses .Accent.gold (your money)
                // while market price charts use .Brand.primary (blue) for market data.
                // This color differentiation is by design to distinguish personal portfolio
                // from external market data.
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
                .chartOverlay { proxy in
                    GeometryReader { geo in
                        Rectangle()
                            .fill(Color.clear)
                            .contentShape(Rectangle())
                            .gesture(
                                DragGesture(minimumDistance: 0)
                                    .onChanged { value in
                                        let x = value.location.x
                                        guard let date: Date = proxy.value(atX: x) else { return }
                                        if let closest = viewModel.history.min(by: { abs(parseDate($0.timestamp).timeIntervalSince(date)) < abs(parseDate($1.timestamp).timeIntervalSince(date)) }) {
                                            selectedPortfolioPoint = (parseDate(closest.timestamp), closest.totalValue)
                                            portfolioTouchLocation = x
                                            if !portfolioHapticTriggered {
                                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                                portfolioHapticTriggered = true
                                            }
                                        }
                                    }
                                    .onEnded { _ in
                                        selectedPortfolioPoint = nil
                                        portfolioTouchLocation = nil
                                        portfolioHapticTriggered = false
                                    }
                            )
                        
                        if let portfolioTouchLocation, let point = selectedPortfolioPoint {
                            Rectangle()
                                .fill(Color.Text.secondary.opacity(0.5))
                                .frame(width: 1)
                                .position(x: portfolioTouchLocation, y: geo.size.height / 2)
                            
                            VStack(spacing: 2) {
                                Text(point.value.asCurrency)
                                    .font(.caption.bold().monospacedDigit())
                                    .foregroundColor(.Text.primary)
                                Text(point.date, style: .date)
                                    .font(.caption2)
                                    .foregroundColor(.Text.secondary)
                            }
                            .padding(8)
                            .background(Color.Background.tertiary)
                            .cornerRadius(8)
                            .position(x: min(max(portfolioTouchLocation, 60), geo.size.width - 60), y: 20)
                        }
                    }
                }
                // M11: Accessibility for performance chart
                .accessibilityLabel("Portfolio performance chart")
                .accessibilityElement(children: .combine)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    func parseDate(_ isoString: String) -> Date {
        // BUG-027 fix: try with fractional seconds first, then without
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: isoString) {
            return date
        }
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: isoString) {
            return date
        }
        let basic = DateFormatter()
        basic.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        basic.timeZone = TimeZone(identifier: "UTC")
        return basic.date(from: isoString) ?? Date()
    }
}

// MARK: - F7.3: Sector Allocation Section

struct SectorAllocationSection: View {
    @ObservedObject var viewModel: PortfolioViewModel
    
    // M14: Themed sector colors optimized for dark backgrounds
    let sectorColors: [String: Color] = [
        "Technology": Color(hex: "0A84FF"),
        "Healthcare": Color(hex: "30D158"),
        "Financials": Color(hex: "BF5AF2"),
        "Consumer Cyclical": Color(hex: "FF9F0A"),
        "Energy": Color(hex: "FF453A"),
        "Communication Services": Color(hex: "64D2FF"),
        "Industrials": Color(hex: "8E8E93"),
        "Consumer Defensive": Color(hex: "FFD60A"),
        "Basic Materials": Color(hex: "AC8E68"),
        "Real Estate": Color(hex: "5E5CE6"),
        "Utilities": Color(hex: "30B0C7"),
        "Financial Services": Color(hex: "BF5AF2"),
        "Unknown": Color(hex: "8E8E93"),
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
                        // M15: Only show percentage text for slices > 15%
                        if sector.percentage > 15 {
                            Text("\(Int(sector.percentage))%")
                                .font(.caption2.bold())
                                .foregroundColor(.white)
                        }
                    }
                }
                .frame(height: 200)
                // Accessibility for pie chart
                .accessibilityLabel("Sector allocation chart. " + viewModel.sectorAllocation.map { "\($0.sector) \(String(format: "%.0f", $0.percentage)) percent" }.joined(separator: ", "))
                .accessibilityElement(children: .combine)
                
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

// MARK: - Trade History Content (REC-167)

/// Embedded trade history for Portfolio tab (no NavigationStack)
private struct TradeHistoryContent: View {
    @State private var executions: [IBKRTradeExecution] = []
    @State private var isLoading = true
    @State private var error: String?
    
    var body: some View {
        VStack(spacing: 12) {
            if isLoading {
                VStack {
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("Loading executions...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(minHeight: 200)
            } else if let error = error {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.Signal.hold)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                .frame(minHeight: 200)
            } else if executions.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.largeTitle)
                        .foregroundColor(.Text.tertiary)
                    Text("No executions yet")
                        .font(.headline)
                    Text("Your IB Gateway trades will appear here")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                .frame(minHeight: 200)
            } else {
                ForEach(executions) { exec in
                    HStack {
                        Circle()
                            .fill(exec.side.contains("BOT") ? Color.Signal.buy : Color.Signal.sell)
                            .frame(width: 8, height: 8)
                        Text(exec.ticker)
                            .font(.headline)
                        Spacer()
                        VStack(alignment: .trailing) {
                            Text("\(Int(exec.quantity)) @ $\(exec.price, specifier: "%.2f")")
                                .font(.subheadline)
                            if let commission = exec.commission {
                                Text("Fee: $\(commission, specifier: "%.2f")")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                            }
                        }
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                }
            }
        }
        .task {
            await loadHistory()
        }
    }
    
    private func loadHistory() async {
        guard IBKRService.shared.isConnected else {
            error = "Not connected to IB Gateway"
            isLoading = false
            return
        }
        
        do {
            executions = try await IBKRService.shared.getTradeHistory()
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    PortfolioView()
        .environmentObject(AppState())
}
