import SwiftUI

/// Full watchlist management view (P2 Feature)
struct WatchlistView: View {
    @ObservedObject private var watchlistService = WatchlistService.shared
    @StateObject private var viewModel = WatchlistViewModel()
    @State private var searchText = ""
    @State private var showAddStock = false
    
    var filteredStocks: [WatchlistStock] {
        if searchText.isEmpty {
            return viewModel.stocks
        }
        return viewModel.stocks.filter {
            $0.ticker.localizedCaseInsensitiveContains(searchText) ||
            $0.name.localizedCaseInsensitiveContains(searchText)
        }
    }
    
    var body: some View {
        List {
            if viewModel.isLoading && viewModel.stocks.isEmpty {
                // Loading skeleton
                ForEach(0..<5, id: \.self) { _ in
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 60, height: 16)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 120, height: 12)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 4) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 70, height: 16)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 50, height: 12)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .shimmer()
                .listRowBackground(Color.Background.secondary)
            } else if watchlistService.watchedTickers.isEmpty {
                // Empty state
                VStack(spacing: 20) {
                    Image(systemName: "star.slash")
                        .font(.system(size: 48))
                        .foregroundColor(.Text.tertiary)
                    
                    Text("No Watchlist")
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text("Add stocks to your watchlist by tapping the ⭐ icon on any stock detail page.")
                        .font(.body)
                        .foregroundColor(.Text.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                    
                    Button {
                        showAddStock = true
                    } label: {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                            Text("Add Your First Stock")
                        }
                        .font(.headline)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .padding(.horizontal, 40)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 60)
                .listRowBackground(Color.Background.primary)
                .listRowSeparator(.hidden)
            } else {
                // Watchlist content
                ForEach(filteredStocks) { stock in
                    NavigationLink {
                        StockDetailView(ticker: stock.ticker)
                    } label: {
                        WatchlistDetailRow(stock: stock)
                    }
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            withAnimation {
                                watchlistService.removeFromWatchlist(stock.ticker)
                            }
                        } label: {
                            Label("Remove", systemImage: "star.slash")
                        }
                    }
                }
                .listRowBackground(Color.Background.secondary)
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.Background.primary)
        .navigationTitle("Watchlist")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .searchable(text: $searchText, prompt: "Search watchlist")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showAddStock = true
                } label: {
                    Image(systemName: "plus")
                        .foregroundColor(.Accent.gold)
                }
            }
        }
        .refreshable {
            await viewModel.loadWatchlistPrices(tickers: Array(watchlistService.watchedTickers))
        }
        .task {
            await viewModel.loadWatchlistPrices(tickers: Array(watchlistService.watchedTickers))
        }
        .onChange(of: watchlistService.watchedTickers) { _, newTickers in
            Task {
                await viewModel.loadWatchlistPrices(tickers: Array(newTickers))
            }
        }
        .sheet(isPresented: $showAddStock) {
            AddToWatchlistSheet()
        }
    }
}

// MARK: - Watchlist Detail Row

struct WatchlistDetailRow: View {
    let stock: WatchlistStock
    
    var body: some View {
        HStack(spacing: 12) {
            // Star icon
            Image(systemName: "star.fill")
                .foregroundColor(.Accent.gold)
                .font(.caption)
            
            // Stock info
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
            
            // Price info
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
        .padding(.vertical, 4)
    }
}

// MARK: - Add to Watchlist Sheet

struct AddToWatchlistSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var watchlistService = WatchlistService.shared
    @State private var searchText = ""
    @State private var searchResults: [SearchResult] = []
    @State private var isSearching = false
    @State private var recentSearches: [String] = []
    
    var body: some View {
        NavigationStack {
            VStack {
                if searchText.isEmpty {
                    // Show recent searches or popular stocks
                    VStack(alignment: .leading, spacing: 16) {
                        if !recentSearches.isEmpty {
                            Text("Recent Searches")
                                .font(.headline)
                                .foregroundColor(.Text.primary)
                                .padding(.horizontal)
                            
                            ForEach(recentSearches, id: \.self) { ticker in
                                Button {
                                    addToWatchlist(ticker)
                                } label: {
                                    HStack {
                                        Text(ticker)
                                            .foregroundColor(.Text.primary)
                                        Spacer()
                                        Image(systemName: watchlistService.isWatched(ticker) ? "star.fill" : "plus.circle")
                                            .foregroundColor(watchlistService.isWatched(ticker) ? .Accent.gold : .Brand.primary)
                                    }
                                    .padding()
                                    .background(Color.Background.secondary)
                                    .cornerRadius(8)
                                }
                                .padding(.horizontal)
                                .disabled(watchlistService.isWatched(ticker))
                            }
                        }
                        
                        Text("Popular Stocks")
                            .font(.headline)
                            .foregroundColor(.Text.primary)
                            .padding(.horizontal)
                            .padding(.top)
                        
                        let popularStocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B"]
                        ForEach(popularStocks, id: \.self) { ticker in
                            Button {
                                addToWatchlist(ticker)
                            } label: {
                                HStack {
                                    Text(ticker)
                                        .foregroundColor(.Text.primary)
                                    Spacer()
                                    Image(systemName: watchlistService.isWatched(ticker) ? "star.fill" : "plus.circle")
                                        .foregroundColor(watchlistService.isWatched(ticker) ? .Accent.gold : .Brand.primary)
                                }
                                .padding()
                                .background(Color.Background.secondary)
                                .cornerRadius(8)
                            }
                            .padding(.horizontal)
                            .disabled(watchlistService.isWatched(ticker))
                        }
                        
                        Spacer()
                    }
                    .padding(.vertical)
                } else if isSearching {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if searchResults.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.largeTitle)
                            .foregroundColor(.Text.tertiary)
                        Text("No results for \"\(searchText)\"")
                            .foregroundColor(.Text.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(searchResults) { result in
                            Button {
                                addToWatchlist(result.ticker)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(result.ticker)
                                            .font(.headline)
                                            .foregroundColor(.Text.primary)
                                        Text(result.name)
                                            .font(.caption)
                                            .foregroundColor(.Text.secondary)
                                    }
                                    Spacer()
                                    Image(systemName: watchlistService.isWatched(result.ticker) ? "star.fill" : "plus.circle")
                                        .foregroundColor(watchlistService.isWatched(result.ticker) ? .Accent.gold : .Brand.primary)
                                }
                            }
                            .disabled(watchlistService.isWatched(result.ticker))
                        }
                        .listRowBackground(Color.Background.secondary)
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .background(Color.Background.primary)
            .navigationTitle("Add to Watchlist")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $searchText, prompt: "Search by ticker or name")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.Accent.gold)
                }
            }
            .onChange(of: searchText) { _, newValue in
                Task {
                    await search(query: newValue)
                }
            }
        }
    }
    
    private func addToWatchlist(_ ticker: String) {
        watchlistService.addToWatchlist(ticker)
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        
        // Add to recent searches
        if !recentSearches.contains(ticker) {
            recentSearches.insert(ticker, at: 0)
            if recentSearches.count > 5 {
                recentSearches.removeLast()
            }
        }
    }
    
    private func search(query: String) async {
        guard !query.isEmpty else {
            searchResults = []
            return
        }
        
        isSearching = true
        
        do {
            let response = try await APIService.shared.getStocks(limit: 20)
            let filtered = response.stocks.filter { stock in
                stock.ticker.localizedCaseInsensitiveContains(query) ||
                (stock.name ?? "").localizedCaseInsensitiveContains(query)
            }
            searchResults = filtered.map { SearchResult(ticker: $0.ticker, name: $0.name ?? $0.ticker) }
        } catch {
            searchResults = []
        }
        
        isSearching = false
    }
}

struct SearchResult: Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
}

// MARK: - ViewModel

@MainActor
class WatchlistViewModel: ObservableObject {
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
        
        // Sort alphabetically by ticker
        stocks = loadedStocks.sorted { $0.ticker < $1.ticker }
        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        WatchlistView()
    }
}
