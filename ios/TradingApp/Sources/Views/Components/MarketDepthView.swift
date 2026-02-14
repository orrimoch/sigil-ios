import SwiftUI

/// REC-150: Level 2 Market Depth View
/// Displays bid/ask ladder from order book
struct MarketDepthView: View {
    let ticker: String
    
    @State private var depth: MarketDepthData?
    @State private var isLoading = true
    @State private var error: String?
    
    var body: some View {
        VStack(spacing: 0) {
            if isLoading {
                loadingView
            } else if let error = error {
                errorView(error)
            } else if let depth = depth {
                depthContent(depth)
            }
        }
        .background(Color.Background.primary)
        .navigationTitle("Market Depth")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadDepth()
        }
        .refreshable {
            await loadDepth()
        }
    }
    
    // MARK: - Components
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ForEach(0..<10, id: \.self) { _ in
                HStack {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.Background.tertiary)
                        .frame(height: 24)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.Background.tertiary)
                        .frame(height: 24)
                }
            }
        }
        .padding()
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
                Task { await loadDepth() }
            }
            .foregroundColor(.Brand.primary)
        }
        .padding()
    }
    
    @ViewBuilder
    private func depthContent(_ depth: MarketDepthData) -> some View {
        // Header with spread info
        headerCard(depth)
        
        // Order book ladder
        ScrollView {
            VStack(spacing: 0) {
                // Column headers
                HStack {
                    Text("BID SIZE")
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text("PRICE")
                        .frame(width: 80)
                    Text("ASK SIZE")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .font(.caption2.bold())
                .foregroundColor(.Text.tertiary)
                .padding(.horizontal)
                .padding(.vertical, 8)
                
                // Depth levels
                ForEach(0..<min(depth.bids.count, depth.asks.count), id: \.self) { i in
                    depthRow(
                        bid: depth.bids[i],
                        ask: depth.asks[i],
                        maxBidSize: depth.bids.map { $0.size }.max() ?? 1,
                        maxAskSize: depth.asks.map { $0.size }.max() ?? 1
                    )
                }
            }
        }
    }
    
    private func headerCard(_ depth: MarketDepthData) -> some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(ticker)
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)
                    if let last = depth.lastPrice {
                        Text(last.asCurrency)
                            .font(.headline.monospacedDigit())
                            .foregroundColor(.Text.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    if let spread = depth.spread {
                        HStack(spacing: 4) {
                            Text("Spread:")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                            Text(String(format: "$%.4f", spread))
                                .font(.caption.monospacedDigit())
                                .foregroundColor(.Text.secondary)
                        }
                    }
                    if let spreadPct = depth.spreadPercent {
                        Text(String(format: "%.4f%%", spreadPct))
                            .font(.caption.monospacedDigit())
                            .foregroundColor(spreadPct < 0.05 ? .Signal.buy : .Signal.hold)
                    }
                }
            }
            
            // Depth summary
            HStack {
                VStack(spacing: 2) {
                    Text("BID DEPTH")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text(formatSize(depth.bidDepth))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundColor(.Signal.buy)
                }
                .frame(maxWidth: .infinity)
                
                Divider()
                    .frame(height: 30)
                
                VStack(spacing: 2) {
                    Text("ASK DEPTH")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text(formatSize(depth.askDepth))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundColor(.Signal.sell)
                }
                .frame(maxWidth: .infinity)
                
                Divider()
                    .frame(height: 30)
                
                VStack(spacing: 2) {
                    Text("LEVELS")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text("\(depth.levels)")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
        .background(Color.Background.secondary)
    }
    
    private func depthRow(bid: DepthLevel, ask: DepthLevel, maxBidSize: Int, maxAskSize: Int) -> some View {
        HStack(spacing: 0) {
            // Bid side (green)
            ZStack(alignment: .trailing) {
                // Size bar
                GeometryReader { geo in
                    Rectangle()
                        .fill(Color.Signal.buy.opacity(0.3))
                        .frame(width: geo.size.width * CGFloat(bid.size) / CGFloat(maxBidSize))
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }
                
                // Size text
                Text(formatSize(bid.size))
                    .font(.caption.monospacedDigit())
                    .foregroundColor(.Signal.buy)
                    .padding(.trailing, 8)
            }
            .frame(maxWidth: .infinity)
            
            // Price (center)
            VStack(spacing: 0) {
                Text(String(format: "%.2f", bid.price))
                    .font(.caption.bold().monospacedDigit())
                    .foregroundColor(.Signal.buy)
                Text(String(format: "%.2f", ask.price))
                    .font(.caption.bold().monospacedDigit())
                    .foregroundColor(.Signal.sell)
            }
            .frame(width: 80)
            .padding(.vertical, 4)
            
            // Ask side (red)
            ZStack(alignment: .leading) {
                // Size bar
                GeometryReader { geo in
                    Rectangle()
                        .fill(Color.Signal.sell.opacity(0.3))
                        .frame(width: geo.size.width * CGFloat(ask.size) / CGFloat(maxAskSize))
                }
                
                // Size text
                Text(formatSize(ask.size))
                    .font(.caption.monospacedDigit())
                    .foregroundColor(.Signal.sell)
                    .padding(.leading, 8)
            }
            .frame(maxWidth: .infinity)
        }
        .frame(height: 44)
        .background(Color.Background.secondary.opacity(0.5))
    }
    
    private func formatSize(_ size: Int) -> String {
        if size >= 1_000_000 {
            return String(format: "%.1fM", Double(size) / 1_000_000)
        } else if size >= 1000 {
            return String(format: "%.1fK", Double(size) / 1000)
        }
        return "\(size)"
    }
    
    // MARK: - Data Loading
    
    private func loadDepth() async {
        isLoading = true
        error = nil
        
        do {
            depth = try await APIService.shared.getMarketDepth(ticker: ticker)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - Data Models

struct MarketDepthData: Codable {
    let ticker: String
    let bids: [DepthLevel]
    let asks: [DepthLevel]
    let lastPrice: Double?
    let spread: Double?
    let spreadPercent: Double?
    let timestamp: String?
    let bidDepth: Int
    let askDepth: Int
    let levels: Int
}

struct DepthLevel: Codable {
    let price: Double
    let size: Int
    let numOrders: Int
}

// MARK: - API Extension

extension APIService {
    func getMarketDepth(ticker: String, levels: Int = 10) async throws -> MarketDepthData {
        guard let encodedTicker = ticker.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/market-depth/\(encodedTicker)?levels=\(levels)") else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        struct Response: Codable {
            let success: Bool
            let data: MarketDepthData
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Response.self, from: data).data
    }
}

#Preview {
    NavigationStack {
        MarketDepthView(ticker: "AAPL")
    }
}
