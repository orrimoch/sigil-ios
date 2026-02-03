import SwiftUI
import Charts

/// F5.3: Stock Detail View
/// Full detail for a single stock with score breakdown
struct StockDetailView: View {
    let ticker: String
    @StateObject private var viewModel: StockDetailViewModel
    @StateObject private var watchlistService = WatchlistService.shared
    @State private var showTradeSheet = false
    @State private var showScoreBreakdown = false
    
    init(ticker: String) {
        self.ticker = ticker
        self._viewModel = StateObject(wrappedValue: StockDetailViewModel(ticker: ticker))
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Price header
                PriceHeader(viewModel: viewModel)
                
                // Price chart (F5.3)
                PriceChartCard(viewModel: viewModel)
                    .padding(.horizontal)
                
                // Score card (F5.3)
                ScoreCard(
                    score: viewModel.score,
                    signal: viewModel.signal,
                    rank: viewModel.rank,
                    percentile: viewModel.percentile,
                    onSignalTap: { showTradeSheet = true }
                )
                .padding(.horizontal)
                
                // Score breakdown (F5.4)
                ScoreBreakdownCard(
                    fundamental: viewModel.fundamentalScore,
                    sentiment: viewModel.sentimentScore,
                    technical: viewModel.technicalScore,
                    macro: viewModel.macroScore,
                    explanation: viewModel.explanation
                )
                .padding(.horizontal)
                
                // Score history chart (F5.5)
                ScoreHistoryCard(history: viewModel.scoreHistory)
                    .padding(.horizontal)
                
                // Key metrics
                KeyMetricsCard(
                    price: viewModel.price,
                    open: viewModel.open,
                    high: viewModel.high,
                    low: viewModel.low,
                    volume: viewModel.volume,
                    previousClose: viewModel.previousClose,
                    metrics: viewModel.metrics
                )
                .padding(.horizontal)
                
                // News sentiment
                NewsSentimentCard(
                    sentiment: viewModel.newsSentiment,
                    articleCount: viewModel.newsCount
                )
                .padding(.horizontal)
                
                // Buy/Sell buttons
                HStack(spacing: 16) {
                    Button("Buy") {
                        showTradeSheet = true
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    
                    Button("Sell") {
                        showTradeSheet = true
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
            .padding(.vertical)
        }
        .background(Color.Background.primary)
        .navigationTitle(ticker)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            await viewModel.loadData()
        }
        .refreshable {
            await viewModel.loadData()
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    watchlistService.toggleWatchlist(ticker)
                } label: {
                    Image(systemName: watchlistService.isWatched(ticker) ? "bell.fill" : "bell")
                        .foregroundColor(watchlistService.isWatched(ticker) ? .Brand.primary : .Text.secondary)
                }
            }
        }
        .sheet(isPresented: $showTradeSheet) {
            TradeEntrySheet(ticker: ticker, currentPrice: viewModel.price)
        }
        .overlay {
            if viewModel.isLoading && viewModel.price == 0 {
                Color.Background.primary.opacity(0.8)
                ProgressView()
                    .tint(.Brand.primary)
            }
        }
    }
}

// MARK: - Price Header

struct PriceHeader: View {
    @ObservedObject var viewModel: StockDetailViewModel
    
    var body: some View {
        VStack(spacing: 8) {
            Text(viewModel.name.isEmpty ? viewModel.ticker : viewModel.name)
                .font(.headline)
                .foregroundColor(.Text.secondary)
            
            Text(viewModel.price.asCurrency)
                .font(.monoLarge)
                .foregroundColor(.Text.primary)
            
            HStack {
                let changeColor: Color = viewModel.change == 0 ? .Signal.neutral : (viewModel.isPositive ? .Signal.positive : .Signal.negative)
                
                Image(systemName: viewModel.change > 0 ? "arrow.up.right" : (viewModel.change < 0 ? "arrow.down.right" : "minus"))
                    .foregroundColor(changeColor)
                
                Text(viewModel.change.asSignedCurrency)
                    .foregroundColor(changeColor)
                
                Text("(\(viewModel.isPositive ? "+" : "")\(String(format: "%.2f", viewModel.changePercent))%)")
                    .foregroundColor(changeColor)
                
                Text("Today")
                    .foregroundColor(.Text.tertiary)
            }
            .font(.subheadline)
        }
        .padding()
    }
}

// MARK: - Price Chart Card (F5.3)

struct PriceChartCard: View {
    @ObservedObject var viewModel: StockDetailViewModel
    
    var body: some View {
        VStack(spacing: 12) {
            // Price chart from API data or fallback to day range
            if !viewModel.priceHistory.isEmpty {
                Chart(viewModel.priceHistory) { item in
                    LineMark(
                        x: .value("Date", item.date),
                        y: .value("Price", item.close)
                    )
                    .foregroundStyle(Color.Brand.primary)
                    
                    AreaMark(
                        x: .value("Date", item.date),
                        y: .value("Price", item.close)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.Brand.primary.opacity(0.3), Color.clear],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                }
                .chartYScale(domain: .automatic(includesZero: false))
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 150)
            } else if viewModel.priceHistoryUnavailable {
                // Price history API unavailable
                VStack(spacing: 8) {
                    if viewModel.high > 0 && viewModel.low > 0 {
                        // Show day range as fallback
                        HStack {
                            VStack(alignment: .leading) {
                                Text("Day Range")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                                Text("\(viewModel.low.asCurrency) — \(viewModel.high.asCurrency)")
                                    .font(.subheadline.monospacedDigit())
                                    .foregroundColor(.Text.primary)
                            }
                            Spacer()
                            VStack(alignment: .trailing) {
                                Text("Open")
                                    .font(.caption)
                                    .foregroundColor(.Text.tertiary)
                                Text(viewModel.open.asCurrency)
                                    .font(.subheadline.monospacedDigit())
                                    .foregroundColor(.Text.primary)
                            }
                        }
                        
                        // Visual range bar
                        GeometryReader { geo in
                            let range = viewModel.high - viewModel.low
                            let pricePosition = range > 0 ? (viewModel.price - viewModel.low) / range : 0.5
                            
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.Background.tertiary)
                                
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(
                                        LinearGradient(
                                            colors: [.Signal.sell, .Signal.hold, .Signal.buy],
                                            startPoint: .leading,
                                            endPoint: .trailing
                                        )
                                    )
                                    .opacity(0.6)
                                
                                Circle()
                                    .fill(Color.white)
                                    .frame(width: 12, height: 12)
                                    .shadow(color: .black.opacity(0.3), radius: 2)
                                    .offset(x: max(0, min(geo.size.width - 12, geo.size.width * pricePosition - 6)))
                            }
                        }
                        .frame(height: 12)
                    } else {
                        Text("Price data unavailable")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 20)
                    }
                }
                .padding(.vertical, 8)
            } else {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.Background.tertiary)
                    .frame(height: 60)
                    .overlay(
                        Text("Loading price data...")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    )
            }
            
            // Period selector
            HStack(spacing: 0) {
                ForEach(StockDetailViewModel.ChartPeriod.allCases, id: \.self) { period in
                    Button(period.rawValue) {
                        viewModel.selectedChartPeriod = period
                    }
                    .font(.caption.bold())
                    .foregroundColor(viewModel.selectedChartPeriod == period ? .Brand.primary : .Text.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(viewModel.selectedChartPeriod == period ? Color.Background.surface : Color.clear)
                    .cornerRadius(4)
                }
            }
            .background(Color.Background.tertiary)
            .cornerRadius(8)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Score Card (F5.3)

struct ScoreCard: View {
    let score: Int
    let signal: String
    let rank: Int
    let percentile: Double
    var onSignalTap: (() -> Void)? = nil
    
    var signalColor: Color {
        switch signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("AI Score")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("\(score)")
                        .font(.system(size: 48, weight: .bold, design: .monospaced))
                        .foregroundColor(.Text.primary)
                    
                    Text("/ 100")
                        .font(.headline)
                        .foregroundColor(.Text.tertiary)
                }
                
                Text("Rank #\(rank) • Top \(String(format: "%.1f", 100 - percentile))%")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            Button {
                onSignalTap?()
            } label: {
                Text(signal)
                    .font(.title2.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 12)
                    .background(signalColor)
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Score Breakdown Card (F5.4)

struct ScoreBreakdownCard: View {
    let fundamental: Double
    let sentiment: Double
    let technical: Double
    let macro: Double
    let explanation: String
    
    @State private var isExpanded = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Button {
                withAnimation {
                    isExpanded.toggle()
                }
            } label: {
                HStack {
                    Text("Score Breakdown")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.Text.secondary)
                }
            }
            
            if isExpanded {
                // Component bars
                ScoreComponentBar(name: "Fundamental", score: fundamental, weight: 35, icon: "building.columns.fill")
                ScoreComponentBar(name: "Sentiment", score: sentiment, weight: 25, icon: "newspaper.fill")
                ScoreComponentBar(name: "Technical", score: technical, weight: 20, icon: "chart.xyaxis.line")
                ScoreComponentBar(name: "Macro", score: macro, weight: 20, icon: "globe")
                
                // Explanation
                if !explanation.isEmpty {
                    Divider()
                        .background(Color.Utility.divider)
                    
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "lightbulb.fill")
                            .foregroundColor(.Brand.accent)
                        
                        Text(explanation)
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

struct ScoreComponentBar: View {
    let name: String
    let score: Double
    let weight: Int
    let icon: String
    
    var scoreColor: Color {
        if score >= 70 { return .Signal.buy }
        if score >= 40 { return .Signal.hold }
        return .Signal.sell
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(.Brand.primary)
                
                Text(name)
                    .font(.subheadline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                Text("\(Int(score))")
                    .font(.subheadline.monospacedDigit().bold())
                    .foregroundColor(scoreColor)
                
                Text("(\(weight)%)")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.Background.tertiary)
                    
                    RoundedRectangle(cornerRadius: 4)
                        .fill(scoreColor)
                        .frame(width: geo.size.width * CGFloat(score) / 100)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: - Score History Card (F5.5)

struct ScoreHistoryCard: View {
    let history: [ScoreHistoryPoint]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Score History (12 weeks)")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if history.isEmpty {
                HStack {
                    Spacer()
                    Text("No history available")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Spacer()
                }
                .padding()
            } else {
                // Simple line chart using SwiftUI Charts
                Chart {
                    ForEach(history) { point in
                        LineMark(
                            x: .value("Date", point.date),
                            y: .value("Score", point.score)
                        )
                        .foregroundStyle(Color.Brand.primary)
                        
                        AreaMark(
                            x: .value("Date", point.date),
                            y: .value("Score", point.score)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.Brand.primary.opacity(0.3), Color.clear],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                    }
                    
                    // Signal threshold lines
                    RuleMark(y: .value("Buy", 70))
                        .foregroundStyle(Color.Signal.buy.opacity(0.5))
                        .lineStyle(StrokeStyle(dash: [5, 5]))
                    
                    RuleMark(y: .value("Sell", 40))
                        .foregroundStyle(Color.Signal.sell.opacity(0.5))
                        .lineStyle(StrokeStyle(dash: [5, 5]))
                }
                .chartYScale(domain: 0...100)
                .chartXAxis {
                    AxisMarks(values: .stride(by: .weekOfYear, count: 4)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .frame(height: 150)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Key Metrics Card

struct KeyMetricsCard: View {
    let price: Double
    let open: Double
    let high: Double
    let low: Double
    let volume: Int
    let previousClose: Double
    let metrics: [KeyMetric]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Key Metrics")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                MetricTile(label: "Open", value: open.asCurrency)
                MetricTile(label: "Previous Close", value: previousClose.asCurrency)
                MetricTile(label: "Day High", value: high.asCurrency)
                MetricTile(label: "Day Low", value: low.asCurrency)
                MetricTile(label: "Volume", value: formatVolume(volume))
                
                ForEach(metrics) { metric in
                    MetricTile(label: metric.label, value: metric.value)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func formatVolume(_ vol: Int) -> String {
        if vol >= 1_000_000 {
            return "\(String(format: "%.1f", Double(vol) / 1_000_000))M"
        } else if vol >= 1_000 {
            return "\(String(format: "%.1f", Double(vol) / 1_000))K"
        }
        return "\(vol)"
    }
}

struct MetricTile: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            
            Text(value)
                .font(.subheadline.monospacedDigit())
                .foregroundColor(.Text.primary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - News Sentiment Card

struct NewsSentimentCard: View {
    let sentiment: String
    let articleCount: Int
    
    var sentimentColor: Color {
        switch sentiment.lowercased() {
        case "positive": return .Signal.buy
        case "negative": return .Signal.sell
        default: return .Signal.hold
        }
    }
    
    var body: some View {
        HStack {
            Image(systemName: "newspaper.fill")
                .font(.title2)
                .foregroundColor(.Brand.primary)
            
            VStack(alignment: .leading, spacing: 2) {
                Text("News Sentiment")
                    .font(.subheadline)
                    .foregroundColor(.Text.primary)
                
                Text("\(articleCount) articles analyzed")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            Text(sentiment.capitalized)
                .font(.caption.bold())
                .foregroundColor(.white)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(sentimentColor)
                .cornerRadius(6)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - Trade Entry Sheet

struct TradeEntrySheet: View {
    let ticker: String
    let currentPrice: Double
    @Environment(\.dismiss) var dismiss
    @State private var quantity = ""
    @State private var isBuy = true
    @State private var isSubmitting = false
    @State private var showSuccess = false
    @State private var errorMessage: String?
    
    var totalValue: Double {
        (Double(quantity) ?? 0) * currentPrice
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Buy/Sell toggle
                Picker("", selection: $isBuy) {
                    Text("Buy").tag(true)
                    Text("Sell").tag(false)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                
                // Stock info
                VStack(spacing: 4) {
                    Text(ticker)
                        .font(.title.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text(currentPrice.asCurrency)
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                }
                
                // Quantity input
                VStack(spacing: 8) {
                    Text("Shares")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    
                    TextField("0", text: $quantity)
                        .font(.system(size: 48, weight: .bold, design: .monospaced))
                        .foregroundColor(.Text.primary)
                        .multilineTextAlignment(.center)
                        .keyboardType(.numberPad)
                }
                
                // Total value
                if let qty = Double(quantity), qty > 0 {
                    VStack(spacing: 4) {
                        Text("Estimated Total")
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                        
                        Text(totalValue.asCurrency)
                            .font(.title2.bold())
                            .foregroundColor(.Text.primary)
                    }
                }
                
                // Error message
                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Signal.sell)
                        .padding()
                        .background(Color.Signal.sell.opacity(0.15))
                        .cornerRadius(8)
                }
                
                Spacer()
                
                // Submit button
                Button {
                    Task { await executeTrade() }
                } label: {
                    HStack {
                        if isSubmitting {
                            ProgressView().tint(.white)
                        } else {
                            Text(isBuy ? "Buy \(ticker)" : "Sell \(ticker)")
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .padding(.horizontal)
                .disabled(quantity.isEmpty || Double(quantity) == 0 || isSubmitting)
            }
            .padding(.vertical)
            .background(Color.Background.primary)
            .navigationTitle("Trade \(ticker)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.Brand.primary)
                }
            }
            .alert("Order Submitted!", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("\(isBuy ? "Bought" : "Sold") \(quantity) shares of \(ticker)")
            }
        }
    }
    
    private func executeTrade() async {
        guard let qty = Double(quantity), qty > 0 else { return }
        isSubmitting = true
        errorMessage = nil
        
        let side = isBuy ? "BUY" : "SELL"
        
        do {
            _ = try await APIService.shared.createOrder(
                ticker: ticker,
                side: side,
                quantity: qty,
                orderType: "MARKET"
            )
            
            // F9.2: Send trade confirmation notification
            NotificationService.shared.sendTradeConfirmation(
                ticker: ticker,
                side: side,
                quantity: qty,
                price: currentPrice,
                total: qty * currentPrice
            )
            
            showSuccess = true
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = error.localizedDescription
        }
        isSubmitting = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        StockDetailView(ticker: "AAPL")
    }
    .environmentObject(AppState())
}
