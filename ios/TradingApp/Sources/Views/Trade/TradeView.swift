import SwiftUI

/// F6.x: Trade Tab
/// Order entry, paper/live indicator, and order status
struct TradeView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = TradeViewModel()
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // F6.2: Paper/Live indicator
                    TradingModeIndicator(isPaper: appState.isPaperTrading)
                    
                    // Stock search / selected stock
                    if viewModel.selectedStock != nil {
                        SelectedStockCard(viewModel: viewModel)
                    } else {
                        StockSearchSection(viewModel: viewModel)
                    }
                    
                    // F6.1: Order entry (when stock selected)
                    if viewModel.selectedStock != nil {
                        OrderEntrySection(viewModel: viewModel)
                    }
                    
                    // F6.4: Order history
                    OrderHistorySection(viewModel: viewModel)
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Trade")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .task {
                await viewModel.fetchTodaysOrders()
            }
            .refreshable {
                await viewModel.fetchTodaysOrders()
            }
            .sheet(isPresented: $viewModel.showPreview) {
                OrderPreviewSheet(viewModel: viewModel, isPaper: appState.isPaperTrading)
            }
            .alert("Order Submitted", isPresented: $viewModel.showConfirmation) {
                Button("OK", role: .cancel) {}
            } message: {
                if let order = viewModel.lastOrder {
                    Text("\(order.side) \(Int(order.quantity)) \(order.ticker) - \(order.status)")
                }
            }
        }
    }
}

// MARK: - Trading Mode Indicator

struct TradingModeIndicator: View {
    let isPaper: Bool
    
    private var isLiveIBKR: Bool {
        !isPaper && IBKRService.shared.isConnected
    }
    
    private var displayText: String {
        if isPaper { return "PAPER TRADING" }
        if isLiveIBKR { return "LIVE TRADING" }
        return "LIVE MODE (IBKR NOT CONNECTED)"
    }
    
    private var displayColor: Color {
        isPaper ? .Signal.hold : .Signal.sell
    }
    
    var body: some View {
        HStack(spacing: 8) {
            // Pulsing dot for live mode
            if isLiveIBKR {
                Circle()
                    .fill(Color.Signal.sell)
                    .frame(width: 8, height: 8)
            }
            
            Image(systemName: isPaper ? "doc.text.fill" : "dollarsign.circle.fill")
            Text(displayText)
                .font(.caption.bold())
        }
        .foregroundColor(displayColor)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(
            displayColor.opacity(0.15)
        )
        .cornerRadius(20)
    }
}

// MARK: - Stock Search Section

struct StockSearchSection: View {
    @ObservedObject var viewModel: TradeViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Search Stock")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.Text.tertiary)
                
                TextField("Search by name or ticker...", text: $viewModel.searchText)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .foregroundColor(.Text.primary)
                    .onChange(of: viewModel.searchText) { _, _ in
                        viewModel.search()
                    }
                
                if viewModel.isSearching {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            
            // Search results
            if !viewModel.searchResults.isEmpty {
                VStack(spacing: 0) {
                    ForEach(viewModel.searchResults) { stock in
                        SearchResultRow(stock: stock)
                            .onTapGesture {
                                viewModel.selectStock(stock)
                            }
                        
                        if stock.id != viewModel.searchResults.last?.id {
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

struct SearchResultRow: View {
    let stock: StockScore
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(stock.ticker)
                    .font(.body.bold())
                    .foregroundColor(.Text.primary)
                
                if let name = stock.companyName, !name.isEmpty {
                    Text(name)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                
                Text(stock.sector)
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(Int(stock.totalScore))")
                    .font(.body.bold())
                    .foregroundColor(signalColor(for: stock.signal))
                
                Text(stock.signal)
                    .font(.caption)
                    .foregroundColor(signalColor(for: stock.signal))
            }
        }
        .padding()
        .contentShape(Rectangle())
    }
    
    func signalColor(for signal: String) -> Color {
        switch signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
}

// MARK: - Selected Stock Card

struct SelectedStockCard: View {
    @ObservedObject var viewModel: TradeViewModel
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(viewModel.selectedStock?.ticker ?? "")
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text(viewModel.selectedStock?.sector ?? "")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                
                Spacer()
                
                // Current price
                if viewModel.priceLoading {
                    ProgressView()
                } else if let price = viewModel.currentPrice {
                    Text(price.asCurrency)
                        .font(.title2.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                }
                
                Button {
                    viewModel.clearSelection()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.Text.tertiary)
                        .font(.title2)
                }
            }
            
            // Score badge
            if let stock = viewModel.selectedStock {
                HStack(spacing: 16) {
                    ScoreBadge(label: "Score", value: "\(Int(stock.totalScore))", color: signalColor(for: stock.signal))
                    ScoreBadge(label: "Signal", value: stock.signal, color: signalColor(for: stock.signal))
                    ScoreBadge(label: "Rank", value: "#\(stock.rank)", color: .Text.secondary)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    func signalColor(for signal: String) -> Color {
        switch signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
}

struct ScoreBadge: View {
    let label: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.body.bold())
                .foregroundColor(color)
            Text(label)
                .font(.caption2)
                .foregroundColor(.Text.tertiary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Order Entry Section

struct OrderEntrySection: View {
    @ObservedObject var viewModel: TradeViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Order Details")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            // Buy/Sell toggle
            HStack(spacing: 0) {
                ForEach(OrderSide.allCases, id: \.self) { side in
                    Button {
                        viewModel.orderSide = side
                    } label: {
                        HStack {
                            Image(systemName: side.icon)
                            Text(side.rawValue)
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(viewModel.orderSide == side ? side.color.opacity(0.2) : Color.clear)
                        .foregroundColor(viewModel.orderSide == side ? side.color : .Text.tertiary)
                    }
                }
            }
            .background(Color.Background.secondary)
            .cornerRadius(12)
            
            // Order type
            VStack(alignment: .leading, spacing: 8) {
                Text("Order Type")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                
                Picker("Order Type", selection: $viewModel.orderType) {
                    ForEach(OrderType.allCases, id: \.self) { type in
                        Text(type.rawValue).tag(type)
                    }
                }
                .pickerStyle(.segmented)
                
                Text(viewModel.orderType.description)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            // Quantity
            VStack(alignment: .leading, spacing: 8) {
                Text("Shares")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                
                HStack(spacing: 12) {
                    Button {
                        let current = Int(viewModel.quantity) ?? 0
                        if current > 1 { viewModel.quantity = String(current - 1) }
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .font(.title2)
                            .foregroundColor(.Text.secondary)
                    }
                    
                    TextField("0", text: $viewModel.quantity)
                        .keyboardType(.numberPad)
                        .font(.title2.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                        .multilineTextAlignment(.center)
                        .frame(minWidth: 60)
                    
                    Button {
                        let current = Int(viewModel.quantity) ?? 0
                        viewModel.quantity = String(current + 1)
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                            .foregroundColor(.Accent.gold)
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
            }
            
            // Limit price (if limit order)
            if viewModel.orderType == .limit {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Limit Price")
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                    
                    HStack {
                        Text("$")
                            .foregroundColor(.Text.tertiary)
                        TextField("0.00", text: $viewModel.limitPrice)
                            .keyboardType(.decimalPad)
                            .font(.title2.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                }
            }
            
            // Estimated total
            if viewModel.quantityValue > 0 {
                HStack {
                    Text("Estimated Total")
                        .foregroundColor(.Text.secondary)
                    Spacer()
                    Text(viewModel.estimatedTotal.asCurrency)
                        .font(.title3.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
            }
            
            // Preview button
            Button {
                viewModel.previewOrder()
            } label: {
                Text(viewModel.canSubmitOrder ? "Preview Order" : (viewModel.quantityValue > 0 ? "Preview Order" : "Enter shares to trade"))
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(viewModel.canSubmitOrder ? viewModel.orderSide.color : Color.Background.tertiary)
                    .foregroundColor(viewModel.canSubmitOrder ? .white : .Text.tertiary)
                    .cornerRadius(12)
            }
            .disabled(!viewModel.canSubmitOrder)
        }
        .padding()
        .background(Color.Background.card)
        .cornerRadius(16)
    }
}

// MARK: - Order Preview Sheet

struct OrderPreviewSheet: View {
    @ObservedObject var viewModel: TradeViewModel
    @Environment(\.dismiss) var dismiss
    let isPaper: Bool
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Paper mode warning
                if isPaper {
                    HStack {
                        Image(systemName: "info.circle.fill")
                        Text("This is a simulated trade. No real money will be used.")
                            .font(.caption)
                    }
                    .foregroundColor(.Signal.hold)
                    .padding()
                    .background(Color.Signal.hold.opacity(0.15))
                    .cornerRadius(12)
                }
                
                // Order summary
                VStack(spacing: 16) {
                    OrderSummaryRow(label: "Stock", value: viewModel.selectedStock?.ticker ?? "")
                    OrderSummaryRow(label: "Action", value: viewModel.orderSide.rawValue, color: viewModel.orderSide.color)
                    OrderSummaryRow(label: "Quantity", value: "\(Int(viewModel.quantityValue)) shares")
                    OrderSummaryRow(label: "Order Type", value: viewModel.orderType.rawValue)
                    
                    if viewModel.orderType == .limit, let limitPrice = viewModel.limitPriceValue {
                        OrderSummaryRow(label: "Limit Price", value: limitPrice.asCurrency)
                    } else if let price = viewModel.currentPrice {
                        OrderSummaryRow(label: "Market Price", value: price.asCurrency)
                    }
                    
                    Divider()
                        .background(Color.Border.primary)
                    
                    HStack {
                        Text("Estimated Total")
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        Text(viewModel.estimatedTotal.asCurrency)
                            .font(.title2.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                
                // Error message
                if let error = viewModel.orderError {
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
                    Task {
                        await viewModel.submitOrder()
                    }
                } label: {
                    HStack {
                        if viewModel.isSubmitting {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Submit \(viewModel.orderSide.rawValue) Order")
                                .fontWeight(.bold)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(viewModel.orderSide.color)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                .disabled(viewModel.isSubmitting)
            }
            .padding()
            .background(Color.Background.primary)
            .navigationTitle("Review Order")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.Accent.gold)
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

struct OrderSummaryRow: View {
    let label: String
    let value: String
    var color: Color = .Text.primary
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.Text.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
                .foregroundColor(color)
        }
    }
}

// MARK: - Order History Section

struct OrderHistorySection: View {
    @ObservedObject var viewModel: TradeViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Today's Orders")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                if viewModel.ordersLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            
            if let error = viewModel.ordersError, viewModel.todaysOrders.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.title)
                        .foregroundColor(.Signal.hold)
                    Text("Couldn't load orders")
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Button {
                        Task { await viewModel.fetchTodaysOrders() }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.clockwise")
                            Text("Retry")
                        }
                        .font(.subheadline.bold())
                        .foregroundColor(.Accent.gold)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 32)
            } else if viewModel.todaysOrders.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "clock")
                        .font(.title)
                        .foregroundColor(.Text.tertiary)
                    Text("No orders today")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 32)
            } else {
                VStack(spacing: 0) {
                    ForEach(viewModel.todaysOrders) { order in
                        OrderHistoryRow(order: order, onCancel: {
                            Task {
                                await viewModel.cancelOrder(order)
                            }
                        })
                        
                        if order.id != viewModel.todaysOrders.last?.id {
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

struct OrderHistoryRow: View {
    let order: OrderData
    let onCancel: () -> Void
    
    var body: some View {
        HStack {
            // Status indicator dot
            Circle()
                .fill(order.statusColor)
                .frame(width: 8, height: 8)
            
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(order.side)
                        .font(.caption.bold())
                        .foregroundColor(order.sideColor)
                    Text("\(Int(order.quantity)) \(order.ticker)")
                        .font(.body.bold())
                        .foregroundColor(.Text.primary)
                }
                
                Text(order.formattedTime)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text(order.status)
                    .font(.caption.bold())
                    .foregroundColor(order.statusColor)
                
                if let price = order.filledPrice {
                    Text(price.asCurrency)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
            }
            
            // Cancel button for pending orders
            if order.status == "PENDING" {
                Button {
                    onCancel()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.Signal.sell)
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
    }
}

// MARK: - Preview

#Preview {
    TradeView()
        .environmentObject(AppState())
}
