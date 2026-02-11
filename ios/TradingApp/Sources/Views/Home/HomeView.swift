import SwiftUI

/// F4.x: Home Dashboard
/// Shows portfolio summary, market overview, top AI picks, alerts
struct HomeView: View {
    @StateObject private var viewModel = HomeViewModel()
    @StateObject private var marketHours = MarketHoursService.shared
    @State private var quote = DailyQuote.random()
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // F4.3: Market Hours Indicator + Risk Indicators Row
                    HStack(spacing: 12) {
                        MarketHoursIndicator(service: marketHours)
                        
                        Spacer()
                        
                        // Risk Module: VIX Indicator
                        if let vix = viewModel.vixValue {
                            VIXIndicator(
                                vix: vix,
                                changePct: viewModel.vixChangePct
                            )
                        }
                        
                        // Risk Module: Regime Badge
                        RegimeBadge(
                            regime: viewModel.marketRegime,
                            confidence: viewModel.regimeConfidence
                        )
                    }
                    .padding(.horizontal)
                    
                    // F4.1: Portfolio Summary Card (H1: portfolio first)
                    PortfolioSummaryCard(
                        value: viewModel.portfolioValue,
                        change: viewModel.dailyChange,
                        changePercent: viewModel.dailyChangePercent
                    )
                    .accessibilityElement(children: .combine)
                    .padding(.horizontal)
                    
                    // F3.2: Daily Quote
                    DailyQuoteCard(quote: quote)
                        .padding(.horizontal)
                    
                    // F4.2: Market Overview
                    MarketOverviewCard(indices: viewModel.marketIndices, errorMessage: viewModel.marketError)
                        .padding(.horizontal)
                    
                    // F4.3: Top AI Picks
                    TopAIPicksCard(picks: viewModel.topPicks)
                        .padding(.horizontal)
                    
                    // REC-259: Smart Money Picks (Crowd Wisdom)
                    SmartMoneyPicksSection()
                        .padding(.horizontal)
                    
                    // F4.4: Alerts Feed
                    AlertsFeedCard(alerts: viewModel.alerts)
                        .padding(.horizontal)
                    
                    // Last updated
                    if let lastUpdated = viewModel.lastUpdated {
                        Text("Updated \(lastUpdated.formatted(.relative(presentation: .named)))")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                            .padding(.bottom)
                    }
                }
                .padding(.vertical)
            }
            .background(Color.Background.primary)
            .navigationTitle("Home")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .refreshable {
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                await viewModel.refresh()
            }
            .task {
                await viewModel.loadData()
            }
            .overlay {
                if viewModel.isLoading && viewModel.topPicks.isEmpty && viewModel.errorMessage == nil {
                    // H9/H13: Skeleton loading state
                    ScrollView {
                        VStack(spacing: 24) {
                            // Portfolio skeleton
                            VStack(alignment: .leading, spacing: 12) {
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 100, height: 14)
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 200, height: 32)
                                RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 160, height: 14)
                            }.padding().background(Color.Background.secondary).cornerRadius(12).padding(.horizontal)
                            // Market skeleton
                            HStack(spacing: 12) {
                                ForEach(0..<2, id: \.self) { _ in
                                    VStack(alignment: .leading, spacing: 4) {
                                        RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 60, height: 12)
                                        RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 80, height: 18)
                                    }.frame(maxWidth: .infinity).padding().background(Color.Background.secondary).cornerRadius(12)
                                }
                            }.padding(.horizontal)
                            // Picks skeleton
                            VStack(spacing: 8) {
                                ForEach(0..<3, id: \.self) { _ in
                                    HStack {
                                        RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 50, height: 16)
                                        Spacer()
                                        RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 44, height: 28)
                                        RoundedRectangle(cornerRadius: 4).fill(Color.Background.tertiary).frame(width: 70, height: 16)
                                    }.padding(.horizontal)
                                }
                            }.padding().background(Color.Background.secondary).cornerRadius(12).padding(.horizontal)
                        }
                        .padding(.vertical)
                        .shimmer()
                    }
                    .background(Color.Background.primary)
                } else if let error = viewModel.errorMessage, viewModel.topPicks.isEmpty {
                    ErrorStateView(
                        title: "Something went wrong",
                        message: error,
                        retryAction: {
                            Task { await viewModel.loadData() }
                        }
                    )
                }
            }
        }
    }
}

// MARK: - F3.2: Daily Quote Card

struct DailyQuoteCard: View {
    let quote: DailyQuote
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "quote.opening")
                    .foregroundColor(.Text.tertiary)
                Spacer()
            }
            
            Text(quote.text)
                .font(.subheadline)
                .foregroundColor(.Text.primary)
                .italic()
            
            Text("— \(quote.author)")
                .font(.caption)
                .foregroundColor(.Text.secondary)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - F4.1: Portfolio Summary Card

struct PortfolioSummaryCard: View {
    let value: Double?
    let change: Double
    let changePercent: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Portfolio Value")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if let value = value {
                Text(value.asCurrency)
                    .font(.monoLarge)
                    .foregroundColor(.Text.primary)
            } else {
                Text("$—")
                    .font(.monoLarge)
                    .foregroundColor(.Text.tertiary)
            }
            
            HStack {
                let changeColor: Color = change == 0 ? .Signal.neutral : (change > 0 ? .Signal.positive : .Signal.negative)
                
                Image(systemName: change > 0 ? "arrow.up.right" : (change < 0 ? "arrow.down.right" : "minus"))
                    .foregroundColor(changeColor)
                
                Text(change.asSignedCurrency)
                    .font(.mono)
                    .foregroundColor(changeColor)
                
                Text("(\(changePercent >= 0 ? "+" : "")\(String(format: "%.2f", changePercent))%)")
                    .font(.caption)
                    .foregroundColor(changeColor)
                
                Text("Today")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - F4.2: Market Overview Card

struct MarketOverviewCard: View {
    let indices: [MarketIndex]
    var errorMessage: String? = nil
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Market Overview")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if indices.isEmpty {
                HStack {
                    Spacer()
                    if let errorMessage = errorMessage {
                        VStack(spacing: 8) {
                            Image(systemName: "chart.line.downtrend.xyaxis")
                                .font(.title)
                                .foregroundColor(.Text.tertiary)
                            Text(errorMessage)
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    } else {
                        ProgressView()
                            .tint(.Brand.primary)
                    }
                    Spacer()
                }
                .padding()
            } else {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    ForEach(indices) { index in
                        IndexTile(index: index)
                            .accessibilityElement(children: .combine)
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

struct IndexTile: View {
    let index: MarketIndex
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(index.name)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            
            Text(index.formattedValue)
                .font(.mono)
                .foregroundColor(.Text.primary)
            
            Text(index.formattedChange)
                .font(.caption)
                .foregroundColor(index.change == 0 ? .Signal.neutral : (index.isPositive ? .Signal.positive : .Signal.negative))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - F4.3: Top AI Picks Card

struct TopAIPicksCard: View {
    let picks: [TopPick]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Top AI Picks")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                NavigationLink("See All") {
                    ScoresView()
                }
                .font(.caption)
                .foregroundColor(.Accent.gold)
            }
            
            if picks.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .font(.title)
                            .foregroundColor(.Text.tertiary)
                        Text("Run the scoring pipeline to see AI picks")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                            .multilineTextAlignment(.center)
                    }
                    Spacer()
                }
                .padding()
            } else {
                VStack(spacing: 8) {
                    ForEach(picks) { pick in
                        NavigationLink {
                            StockDetailView(ticker: pick.ticker)
                        } label: {
                            AIPickRow(pick: pick)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

struct AIPickRow: View {
    let pick: TopPick
    
    var signalColor: Color {
        switch pick.signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(pick.ticker)
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Text(pick.name)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .lineLimit(1)
            }
            .frame(width: 100, alignment: .leading)
            
            // M6: Merged score + signal into single badge (signal color)
            Text("\(pick.score)")
                .font(.caption.bold())
                .foregroundColor(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(signalColor)
                .cornerRadius(4)
            
            Spacer()
            
            Text(pick.formattedPrice)
                .font(.mono)
                .foregroundColor(.Text.primary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - F4.4: Alerts Feed Card

struct AlertsFeedCard: View {
    let alerts: [AlertItem]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recent Alerts")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                if !alerts.isEmpty {
                    Text("\(alerts.count)")
                        .font(.caption.bold())
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color.Brand.primary)
                        .cornerRadius(10)
                }
            }
            
            if alerts.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 8) {
                        Image(systemName: "bell.slash")
                            .font(.title)
                            .foregroundColor(.Text.tertiary)
                        Text("No recent alerts")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                    Spacer()
                }
                .padding()
            } else {
                VStack(spacing: 0) {
                    ForEach(alerts) { alert in
                        AlertRow(alert: alert)
                        
                        if alert.id != alerts.last?.id {
                            Divider()
                                .background(Color.Utility.divider)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

struct AlertRow: View {
    let alert: AlertItem
    
    var body: some View {
        HStack(spacing: 12) {
            // Icon
            Image(systemName: alert.icon)
                .font(.title3)
                .foregroundColor(alert.iconColor)
                .frame(width: 30)
            
            // Content
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(alert.ticker)
                        .font(.caption.bold())
                        .foregroundColor(.Brand.primary)
                    
                    Text(alert.title)
                        .font(.subheadline)
                        .foregroundColor(.Text.primary)
                }
                
                Text(alert.subtitle)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            // Timestamp
            Text(alert.formattedTime)
                .font(.caption)
                .foregroundColor(.Text.tertiary)
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Market Hours Indicator

struct MarketHoursIndicator: View {
    @ObservedObject var service: MarketHoursService
    
    private var statusColor: Color {
        switch service.status {
        case .open: return .Signal.buy
        case .preMarket, .afterHours: return .Signal.hold
        case .closed: return .Text.tertiary
        }
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Pulsing dot for open market
            if service.status == .open {
                Circle()
                    .fill(Color.Signal.buy)
                    .frame(width: 8, height: 8)
                    .modifier(PulseAnimation())
            }
            
            // Status icon
            Image(systemName: service.status.icon)
                .font(.body)
                .foregroundColor(statusColor)
            
            // Status text
            Text(service.statusText)
                .font(.subheadline.bold())
                .foregroundColor(statusColor)
            
            Spacer()
            
            // Next event
            if !service.nextEventText.isEmpty {
                Text(service.nextEventText)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// Pulse animation for open market indicator
struct PulseAnimation: ViewModifier {
    @State private var isPulsing = false
    
    func body(content: Content) -> some View {
        content
            .scaleEffect(isPulsing ? 1.3 : 1.0)
            .opacity(isPulsing ? 0.7 : 1.0)
            .animation(
                .easeInOut(duration: 1.0).repeatForever(autoreverses: true),
                value: isPulsing
            )
            .onAppear { isPulsing = true }
    }
}

// MARK: - Preview

#Preview {
    HomeView()
        .environmentObject(AppState())
}
