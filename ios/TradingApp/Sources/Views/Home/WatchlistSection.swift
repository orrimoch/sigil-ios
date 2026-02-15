import SwiftUI

/// Watchlist section for Home screen (P2 Feature)
/// Shows user's watched stocks with prices
struct WatchlistSection: View {
    @ObservedObject private var watchlistService = WatchlistService.shared
    @StateObject private var viewModel = WatchlistSectionViewModel()
    @State private var isExpanded = true
    
    var body: some View {
        if !watchlistService.watchedTickers.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                // Header
                Button {
                    withAnimation(.spring(response: 0.3)) {
                        isExpanded.toggle()
                    }
                } label: {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(.Accent.gold)
                        
                        Text("Watchlist")
                            .font(.headline)
                            .foregroundColor(.Text.primary)
                        
                        Spacer()
                        
                        Text("\(watchlistService.watchedTickers.count)")
                            .font(.caption.bold())
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(Color.Accent.gold)
                            .cornerRadius(10)
                        
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                        
                        NavigationLink("Manage") {
                            WatchlistView()
                        }
                        .font(.caption)
                        .foregroundColor(.Accent.gold)
                    }
                }
                .buttonStyle(.plain)
                
                if isExpanded {
                    if viewModel.isLoading && viewModel.stocks.isEmpty {
                        // Loading skeleton
                        VStack(spacing: 8) {
                            ForEach(0..<min(3, watchlistService.watchedTickers.count), id: \.self) { _ in
                                HStack {
                                    VStack(alignment: .leading, spacing: 4) {
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.Background.tertiary)
                                            .frame(width: 50, height: 14)
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.Background.tertiary)
                                            .frame(width: 100, height: 10)
                                    }
                                    Spacer()
                                    VStack(alignment: .trailing, spacing: 4) {
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.Background.tertiary)
                                            .frame(width: 60, height: 14)
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.Background.tertiary)
                                            .frame(width: 40, height: 10)
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        }
                        .shimmer()
                    } else if viewModel.stocks.isEmpty {
                        // Empty state with loading indicator
                        HStack {
                            Spacer()
                            ProgressView()
                                .tint(.Accent.gold)
                            Spacer()
                        }
                        .padding(.vertical, 8)
                    } else {
                        // Watchlist items
                        VStack(spacing: 0) {
                            ForEach(viewModel.stocks.prefix(5)) { stock in
                                NavigationLink {
                                    StockDetailView(ticker: stock.ticker)
                                } label: {
                                    WatchlistRow(stock: stock)
                                }
                                
                                if stock.id != viewModel.stocks.prefix(5).last?.id {
                                    Divider()
                                        .background(Color.Utility.divider)
                                }
                            }
                        }
                        
                        // Show more if >5 stocks
                        if viewModel.stocks.count > 5 {
                            NavigationLink {
                                WatchlistView()
                            } label: {
                                Text("View all \(viewModel.stocks.count) stocks")
                                    .font(.caption)
                                    .foregroundColor(.Accent.gold)
                                    .frame(maxWidth: .infinity)
                                    .padding(.top, 8)
                            }
                        }
                    }
                }
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .task {
                await viewModel.loadWatchlistPrices(tickers: Array(watchlistService.watchedTickers))
            }
            .onChange(of: watchlistService.watchedTickers) { _, newTickers in
                Task {
                    await viewModel.loadWatchlistPrices(tickers: Array(newTickers))
                }
            }
        }
    }
}

// MARK: - Watchlist Row

struct WatchlistRow: View {
    let stock: WatchlistStock
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(stock.ticker)
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Text(stock.name)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .lineLimit(1)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text(stock.price.asCurrency)
                    .font(.mono)
                    .foregroundColor(.Text.primary)
                
                HStack(spacing: 4) {
                    Image(systemName: stock.isPositive ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption2)
                    
                    Text(stock.formattedChange)
                        .font(.caption)
                }
                .foregroundColor(stock.changePercent == 0 ? .Signal.neutral : (stock.isPositive ? .Signal.positive : .Signal.negative))
            }
        }
        .padding(.vertical, 6)
    }
}

// MARK: - Data Model

struct WatchlistStock: Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    var price: Double
    var change: Double
    var changePercent: Double
    
    var isPositive: Bool { changePercent >= 0 }
    
    var formattedChange: String {
        let prefix = changePercent >= 0 ? "+" : ""
        return "\(prefix)\(String(format: "%.2f", changePercent))%"
    }
}

// MARK: - ViewModel

@MainActor
class WatchlistSectionViewModel: ObservableObject {
    @Published var stocks: [WatchlistStock] = []
    @Published var isLoading = false
    
    private let api = APIService.shared
    
    func loadWatchlistPrices(tickers: [String]) async {
        guard !tickers.isEmpty else {
            stocks = []
            return
        }
        
        isLoading = true
        
        var loadedStocks: [WatchlistStock] = []
        
        // Load prices and stock info in parallel
        await withTaskGroup(of: WatchlistStock?.self) { group in
            for ticker in tickers {
                group.addTask {
                    do {
                        // Get price data
                        let price = try await self.api.getPrice(ticker: ticker)
                        
                        // Try to get stock name from stock endpoint
                        var name = ticker
                        if let stockInfo = try? await self.api.getStock(ticker: ticker) {
                            name = stockInfo.name
                        }
                        
                        return WatchlistStock(
                            ticker: ticker,
                            name: name,
                            price: price.price ?? 0,
                            change: price.change ?? 0,
                            changePercent: price.changePercent ?? 0
                        )
                    } catch {
                        // Return placeholder on error
                        return WatchlistStock(
                            ticker: ticker,
                            name: ticker,
                            price: 0,
                            change: 0,
                            changePercent: 0
                        )
                    }
                }
            }
            
            for await stock in group {
                if let stock = stock {
                    loadedStocks.append(stock)
                }
            }
        }
        
        // Sort by ticker
        stocks = loadedStocks.sorted { $0.ticker < $1.ticker }
        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ScrollView {
            WatchlistSection()
                .padding()
        }
        .background(Color.Background.primary)
    }
}
