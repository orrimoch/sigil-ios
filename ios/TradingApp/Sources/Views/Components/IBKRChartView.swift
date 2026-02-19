import SwiftUI
import Charts

// MARK: - REC-163: Historical Bars Chart View

/// Chart view displaying OHLCV candlestick data from IB Gateway
struct IBKRChartView: View {
    let ticker: String
    
    @State private var bars: [IBKRBar] = []
    @State private var isLoading = true
    @State private var error: String?
    @State private var selectedTimeframe: Timeframe = .oneDay
    @State private var chartType: ChartType = .candlestick
    @State private var selectedBar: IBKRBar?
    
    enum Timeframe: String, CaseIterable {
        case oneDay = "1 D"
        case oneWeek = "1 W"
        case oneMonth = "1 M"
        case threeMonths = "3 M"
        case oneYear = "1 Y"
        
        var displayName: String {
            switch self {
            case .oneDay: return "1D"
            case .oneWeek: return "1W"
            case .oneMonth: return "1M"
            case .threeMonths: return "3M"
            case .oneYear: return "1Y"
            }
        }
        
        var barSize: String {
            switch self {
            case .oneDay: return "5 mins"
            case .oneWeek: return "15 mins"
            case .oneMonth: return "1 hour"
            case .threeMonths: return "1 day"
            case .oneYear: return "1 day"
            }
        }
        
        var yahooPeriod: String {
            switch self {
            case .oneDay: return "1d"
            case .oneWeek: return "5d"
            case .oneMonth: return "1mo"
            case .threeMonths: return "3mo"
            case .oneYear: return "1y"
            }
        }
    }
    
    enum ChartType: String, CaseIterable {
        case candlestick = "Candlestick"
        case line = "Line"
        
        var icon: String {
            switch self {
            case .candlestick: return "chart.bar.fill"
            case .line: return "chart.line.uptrend.xyaxis"
            }
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Header with controls
            HStack {
                // Timeframe picker
                HStack(spacing: 4) {
                    ForEach(Timeframe.allCases, id: \.self) { tf in
                        TimeframeButton(
                            timeframe: tf,
                            isSelected: selectedTimeframe == tf
                        ) {
                            selectedTimeframe = tf
                            Task { await loadBars() }
                        }
                    }
                }
                
                Spacer()
                
                // Chart type toggle
                Menu {
                    ForEach(ChartType.allCases, id: \.self) { type in
                        Button {
                            chartType = type
                        } label: {
                            Label(type.rawValue, systemImage: type.icon)
                        }
                    }
                } label: {
                    Image(systemName: chartType.icon)
                        .foregroundColor(.Brand.primary)
                        .padding(8)
                        .background(Color.Background.tertiary)
                        .cornerRadius(8)
                }
            }
            
            // Selected bar info (tooltip)
            if let bar = selectedBar {
                BarTooltip(bar: bar)
            }
            
            // Chart
            if isLoading {
                ChartPlaceholder()
            } else if let error = error {
                ChartError(message: error) {
                    Task { await loadBars() }
                }
            } else if bars.isEmpty {
                ChartEmpty()
            } else {
                ChartContent(
                    bars: bars,
                    chartType: chartType,
                    selectedBar: $selectedBar
                )
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(16)
        .task {
            await loadBars()
        }
    }
    
    @MainActor
    private func loadBars() async {
        isLoading = true
        error = nil
        selectedBar = nil
        
        // Refresh IBKR connection status from backend
        await IBKRService.shared.refreshStatus()
        
        // Try IBKR first if connected
        if IBKRService.shared.isConnected {
            do {
                bars = try await IBKRService.shared.getHistoricalBars(
                    ticker: ticker,
                    duration: selectedTimeframe.rawValue,
                    barSize: selectedTimeframe.barSize
                )
                isLoading = false
                return
            } catch {
                // Fall through to Yahoo Finance fallback
                #if DEBUG
                debugError(error, context: "IBKR bars failed, falling back to Yahoo")
                #endif
            }
        }
        
        // Fallback: Use Yahoo Finance price history
        do {
            let period = selectedTimeframe.yahooPeriod
            let response = try await APIService.shared.getPriceHistory(symbol: ticker, period: period)
            bars = response.data.prices.map { price in
                IBKRBar(
                    date: price.date,
                    open: price.open,
                    high: price.high,
                    low: price.low,
                    close: price.close,
                    volume: price.volume
                )
            }
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - Supporting Views

private struct TimeframeButton: View {
    let timeframe: IBKRChartView.Timeframe
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(timeframe.displayName)
                .font(.caption.bold())
                .foregroundColor(isSelected ? .Background.primary : .Text.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? Color.Brand.primary : Color.Background.tertiary)
                .cornerRadius(8)
        }
    }
}

private struct BarTooltip: View {
    let bar: IBKRBar
    
    var formattedDate: String {
        // Parse ISO string
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        if let date = formatter.date(from: bar.date) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateFormat = "MMM d, h:mm a"
            return displayFormatter.string(from: date)
        }
        return bar.date
    }
    
    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text(formattedDate)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            HStack(spacing: 12) {
                VStack(spacing: 2) {
                    Text("O")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(bar.open, specifier: "%.2f")")
                        .font(.caption.bold())
                        .foregroundColor(.Text.primary)
                }
                
                VStack(spacing: 2) {
                    Text("H")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(bar.high, specifier: "%.2f")")
                        .font(.caption.bold())
                        .foregroundColor(.Signal.buy)
                }
                
                VStack(spacing: 2) {
                    Text("L")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(bar.low, specifier: "%.2f")")
                        .font(.caption.bold())
                        .foregroundColor(.Signal.sell)
                }
                
                VStack(spacing: 2) {
                    Text("C")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(bar.close, specifier: "%.2f")")
                        .font(.caption.bold())
                        .foregroundColor(.Text.primary)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.Background.tertiary)
        .cornerRadius(8)
    }
}

private struct ChartContent: View {
    let bars: [IBKRBar]
    let chartType: IBKRChartView.ChartType
    @Binding var selectedBar: IBKRBar?
    
    var body: some View {
        Chart {
            ForEach(Array(bars.enumerated()), id: \.offset) { index, bar in
                if chartType == .line {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("Close", bar.close)
                    )
                    .foregroundStyle(Color.Brand.primary)
                    
                    AreaMark(
                        x: .value("Index", index),
                        y: .value("Close", bar.close)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.Brand.primary.opacity(0.3), Color.Brand.primary.opacity(0)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                } else {
                    // Candlestick: wick (high-low)
                    RectangleMark(
                        x: .value("Index", index),
                        yStart: .value("Low", bar.low),
                        yEnd: .value("High", bar.high),
                        width: 2
                    )
                    .foregroundStyle(bar.close >= bar.open ? Color.Signal.buy : Color.Signal.sell)
                    
                    // Candlestick: body (open-close)
                    RectangleMark(
                        x: .value("Index", index),
                        yStart: .value("Open", bar.open),
                        yEnd: .value("Close", bar.close),
                        width: 8
                    )
                    .foregroundStyle(bar.close >= bar.open ? Color.Signal.buy : Color.Signal.sell)
                }
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing) { value in
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text("$\(price, specifier: "%.0f")")
                            .font(.caption2)
                            .foregroundColor(.Text.tertiary)
                    }
                }
            }
        }
        .frame(height: 200)
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(Color.clear)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { value in
                                guard let frame = proxy.plotFrame else { return }
                                let x = value.location.x - geometry[frame].origin.x
                                if let index: Int = proxy.value(atX: x) {
                                    if index >= 0 && index < bars.count {
                                        selectedBar = bars[index]
                                    }
                                }
                            }
                            .onEnded { _ in
                                // Keep selection visible
                            }
                    )
            }
        }
    }
}

private struct ChartPlaceholder: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.Background.tertiary)
            .frame(height: 200)
            .overlay {
                ProgressView()
                    .tint(.Brand.primary)
            }
    }
}

private struct ChartError: View {
    let message: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.line.downtrend.xyaxis")
                .font(.largeTitle)
                .foregroundColor(.Signal.hold)
            
            Text(message)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            
            Button("Retry", action: onRetry)
                .font(.caption.bold())
                .foregroundColor(.Brand.primary)
        }
        .frame(height: 200)
    }
}

private struct ChartEmpty: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.xaxis")
                .font(.largeTitle)
                .foregroundColor(.Text.tertiary)
            
            Text("No chart data available")
                .font(.caption)
                .foregroundColor(.Text.secondary)
        }
        .frame(height: 200)
    }
}

#Preview {
    VStack {
        IBKRChartView(ticker: "AAPL")
    }
    .padding()
    .background(Color.Background.primary)
}
