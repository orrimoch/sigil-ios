import SwiftUI

/// F4.x: Home Dashboard
/// Shows portfolio summary, market overview, top AI picks, alerts
struct HomeView: View {
    @StateObject private var viewModel = HomeViewModel()
    @State private var quote = DailyQuote.random()
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // F3.2: Daily Quote
                    DailyQuoteCard(quote: quote)
                        .padding(.horizontal)
                    
                    // F4.1: Portfolio Summary Card
                    PortfolioSummaryCard(
                        value: viewModel.portfolioValue,
                        change: viewModel.dailyChange,
                        changePercent: viewModel.dailyChangePercent
                    )
                    .padding(.horizontal)
                    
                    // F4.2: Market Overview
                    MarketOverviewCard(indices: viewModel.marketIndices, errorMessage: viewModel.marketError)
                        .padding(.horizontal)
                    
                    // F4.3: Top AI Picks
                    TopAIPicksCard(picks: viewModel.topPicks)
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
                await viewModel.refresh()
            }
            .task {
                await viewModel.loadData()
            }
            .overlay {
                if viewModel.isLoading && viewModel.topPicks.isEmpty {
                    ProgressView()
                        .tint(.Brand.primary)
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
                    .foregroundColor(.Brand.primary)
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
    let value: Double
    let change: Double
    let changePercent: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Portfolio Value")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
            
            Text(value.asCurrency)
                .font(.monoLarge)
                .foregroundColor(.Text.primary)
            
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
                .foregroundColor(.Brand.primary)
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
            
            // AI Score badge
            Text("\(pick.score)")
                .font(.caption.bold())
                .foregroundColor(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(pick.score >= 70 ? Color.Signal.buy : (pick.score >= 40 ? Color.Signal.hold : Color.Signal.sell))
                .cornerRadius(4)
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text(pick.formattedPrice)
                    .font(.mono)
                    .foregroundColor(.Text.primary)
                
                // Signal recommendation badge
                Text(pick.signal)
                    .font(.caption.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(signalColor)
                    .cornerRadius(4)
            }
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
                .font(.caption2)
                .foregroundColor(.Text.tertiary)
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Preview

#Preview {
    HomeView()
        .environmentObject(AppState())
}
