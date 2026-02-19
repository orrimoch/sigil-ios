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
                    
                    // REC-178: Extra bottom padding to ensure Preview Order button is visible
                    Spacer().frame(height: 20)
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
            // GAP-009: Undo toast overlay
            .overlay(alignment: .bottom) {
                if viewModel.showUndoToast, let order = viewModel.lastOrder {
                    UndoToast(
                        order: order,
                        countdown: viewModel.undoCountdown,
                        onUndo: {
                            Task { await viewModel.undoLastOrder() }
                        },
                        onDismiss: viewModel.dismissUndoToast
                    )
                    .padding(.horizontal, 20)
                    .padding(.bottom, 20)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.spring(response: 0.3), value: viewModel.showUndoToast)
        }
    }
}

// MARK: - GAP-009: Undo Toast

struct UndoToast: View {
    let order: OrderData
    let countdown: Int
    let onUndo: () -> Void
    let onDismiss: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.Signal.buy)
            
            VStack(alignment: .leading, spacing: 2) {
                Text("Order Submitted")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.Text.primary)
                Text("\(order.side) \(Int(order.quantity)) \(order.ticker)")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            Button(action: onUndo) {
                Text("Undo (\(countdown)s)")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.Accent.gold)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color.Accent.gold.opacity(0.15))
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.3), radius: 8, y: 4)
    }
}

// MARK: - Trading Mode Indicator

@MainActor
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
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            displayColor.opacity(0.15)
        )
        .cornerRadius(12)
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
                        // L12: Fires on every character; debounce is handled in ViewModel via searchTask cancellation
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
                
                // REC-178: Price with daily change
                VStack(alignment: .trailing, spacing: 2) {
                    if viewModel.priceLoading {
                        ProgressView()
                    } else if let price = viewModel.currentPrice {
                        Text(price.asCurrency)
                            .font(.title2.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                        
                        // Daily change (mock for now, would come from API)
                        if let change = viewModel.dailyChange, let changePercent = viewModel.dailyChangePercent {
                            HStack(spacing: 2) {
                                Image(systemName: change >= 0 ? "arrow.up" : "arrow.down")
                                    .font(.caption2)
                                Text(String(format: "%.2f (%.2f%%)", abs(change), abs(changePercent)))
                                    .font(.caption.monospacedDigit())
                            }
                            .foregroundColor(change >= 0 ? .Signal.positive : .Signal.negative)
                        }
                    }
                }
                
                // REC-178: Larger X button (44pt touch target)
                Button {
                    viewModel.clearSelection()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.Text.tertiary)
                        .font(.title2)
                        .frame(width: 44, height: 44)
                }
                .contentShape(Rectangle())
            }
            
            // Score badges with signal-appropriate colors
            if let stock = viewModel.selectedStock {
                HStack(spacing: 16) {
                    ScoreBadge(label: "Score", value: "\(Int(stock.totalScore))", color: signalColor(for: stock.signal))
                    ScoreBadge(label: "Signal", value: stock.signal, color: signalColor(for: stock.signal))
                    ScoreBadge(label: "Rank", value: "#\(stock.rank)", color: .Text.secondary)
                }
            }
            
            // REC-178: View Chart link
            if let ticker = viewModel.selectedStock?.ticker {
                NavigationLink {
                    StockDetailView(ticker: ticker)
                } label: {
                    HStack {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                        Text("View Chart & Details")
                            .font(.subheadline.bold())
                    }
                    .foregroundColor(.Accent.gold)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Color.Accent.gold.opacity(0.1))
                    .cornerRadius(8)
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
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        viewModel.orderSide = side
                    } label: {
                        HStack {
                            Image(systemName: side.icon)
                            Text(side.rawValue)
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(viewModel.orderSide == side ? side.color : Color.clear)
                        .foregroundColor(viewModel.orderSide == side ? .white : .Text.tertiary)
                    }
                    .accessibilityLabel(side == .buy ? "Buy order" : "Sell order")
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
                .tint(Color.Accent.gold)
                
                Text(viewModel.orderType.description)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            // Quantity
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Shares")
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                    
                    Spacer()
                    
                    // REC-177: Show position size when selling
                    if viewModel.orderSide == .sell && viewModel.hasPosition {
                        Text("Position: \(Int(viewModel.positionSize))")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                }
                
                HStack(spacing: 12) {
                    // REC-178: 44pt touch target for minus button
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        let current = Int(viewModel.quantity) ?? 0
                        if current > 1 { viewModel.quantity = String(current - 1) }
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .font(.title)
                            .foregroundColor(.Text.primary)
                            .frame(width: 44, height: 44)
                    }
                    .contentShape(Rectangle())
                    .accessibilityLabel("Decrease quantity")
                    
                    TextField("0", text: $viewModel.quantity)
                        .keyboardType(.numberPad)
                        .font(.title2.bold().monospacedDigit())
                        .foregroundColor(.Text.primary)
                        .multilineTextAlignment(.center)
                        .frame(minWidth: 60)
                    
                    // REC-178: 44pt touch target for plus button
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        let current = Int(viewModel.quantity) ?? 0
                        // REC-177: Cap at position size for sells
                        if viewModel.orderSide == .sell && viewModel.hasPosition {
                            let maxQty = Int(viewModel.positionSize)
                            viewModel.quantity = String(min(current + 1, maxQty))
                        } else {
                            viewModel.quantity = String(current + 1)
                        }
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title)
                            .foregroundColor(.Text.primary)
                            .frame(width: 44, height: 44)
                    }
                    .contentShape(Rectangle())
                    .accessibilityLabel("Increase quantity")
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                
                // REC-177: Quick quantity buttons (REC-178: 44pt min height)
                HStack(spacing: 8) {
                    ForEach([10, 50, 100], id: \.self) { amount in
                        Button {
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            // Cap at position size for sells
                            if viewModel.orderSide == .sell && viewModel.hasPosition {
                                let maxQty = Int(viewModel.positionSize)
                                viewModel.setQuickQuantity(min(amount, maxQty))
                            } else {
                                viewModel.setQuickQuantity(amount)
                            }
                        } label: {
                            Text("\(amount)")
                                .font(.subheadline.bold())
                                .frame(maxWidth: .infinity)
                                .frame(minHeight: 44)
                                .background(Color.Background.tertiary)
                                .foregroundColor(.Text.secondary)
                                .cornerRadius(8)
                        }
                    }
                    
                    // REC-177: "All" button for sells (REC-178: 44pt min height)
                    if viewModel.orderSide == .sell && viewModel.hasPosition {
                        Button {
                            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                            viewModel.setQuantityToPosition()
                        } label: {
                            Text("All")
                                .font(.subheadline.bold())
                                .frame(maxWidth: .infinity)
                                .frame(minHeight: 44)
                                .background(Color.Signal.sell.opacity(0.2))
                                .foregroundColor(.Signal.sell)
                                .cornerRadius(8)
                        }
                    }
                }
                
                // REC-177: Validation error message
                if let error = viewModel.sellValidationError {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption)
                        Text(error)
                            .font(.caption)
                    }
                    .foregroundColor(.Signal.sell)
                    .padding(.top, 4)
                }
            }
            
            // Limit/Stop price (if not market order)
            if viewModel.orderType.needsPrice {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(viewModel.orderType.priceLabel)
                            .font(.subheadline)
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        if let price = viewModel.currentPrice {
                            Text("Market: \(price.asCurrency)")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                    
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
                    
                    // Help text for stop orders
                    if viewModel.orderType == .stop {
                        Text("Order will trigger when price ≤ stop price")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                }
            }
            
            // Estimated total
            if viewModel.quantityValue > 0 {
                VStack(spacing: 8) {
                    if let price = viewModel.currentPrice {
                        Text("\(Int(viewModel.quantityValue)) shares × \(price.asCurrency)")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                    HStack {
                        Text("Estimated Total")
                            .foregroundColor(.Text.secondary)
                        Spacer()
                        Text(viewModel.estimatedTotal.asCurrency)
                            .font(.title3.bold().monospacedDigit())
                            .foregroundColor(.Text.primary)
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
            }
            
            // Preview button
            Button {
                viewModel.previewOrder()
            } label: {
                Text(viewModel.canSubmitOrder ? "Preview Order" : (viewModel.selectedStock == nil ? "Select a stock" : (viewModel.quantityValue <= 0 ? "Enter quantity" : "Preview Order")))
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
        .cornerRadius(12)
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
                    } else if viewModel.orderType == .stop, let stopPrice = viewModel.limitPriceValue {
                        OrderSummaryRow(label: "Stop Price", value: stopPrice.asCurrency)
                        if let marketPrice = viewModel.currentPrice {
                            OrderSummaryRow(label: "Market Price", value: marketPrice.asCurrency, color: .Text.tertiary)
                        }
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
                
                // Disclaimer — LOW FIX SHEET-002: Slightly more visible
                HStack(spacing: 4) {
                    Image(systemName: "info.circle")
                        .font(.caption2)
                    Text("This does not constitute financial advice. Past performance is not indicative of future results.")
                        .font(.caption)
                }
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
                .padding(.vertical, 8)
                .background(Color.Background.tertiary.opacity(0.5))
                .cornerRadius(8)
                
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
                    .frame(minHeight: 44)
                }
            }
        }
        .presentationDetents([.large, .medium])
        .alert("⚠️ LIVE TRADE", isPresented: $viewModel.showLiveTradeConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Confirm \(viewModel.orderSide.rawValue) Trade") {
                Task {
                    await viewModel.confirmLiveTrade()
                }
            }
        } message: {
            Text("This will execute a real trade with real money via your IBKR account. Are you sure you want to proceed?")
        }
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
