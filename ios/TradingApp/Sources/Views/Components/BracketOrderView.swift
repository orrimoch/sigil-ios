import SwiftUI

// MARK: - REC-164: Bracket Order Form

/// Bracket order form with entry, take-profit, and stop-loss prices
struct BracketOrderForm: View {
    let ticker: String
    let currentPrice: Double
    let side: String
    
    @Binding var isPresented: Bool
    
    @State private var quantity: String = "100"
    @State private var entryPrice: String = ""
    @State private var takeProfitPrice: String = ""
    @State private var stopLossPrice: String = ""
    @State private var outsideRth: Bool = false
    
    @State private var isSubmitting = false
    @State private var error: String?
    @State private var result: IBKRBracketResult?
    @State private var showSuccess = false
    
    private var isBuy: Bool { side.uppercased() == "BUY" }
    
    private var entryValue: Double? { Double(entryPrice) }
    private var tpValue: Double? { Double(takeProfitPrice) }
    private var slValue: Double? { Double(stopLossPrice) }
    
    private var isValid: Bool {
        guard let entry = entryValue,
              let tp = tpValue,
              let sl = slValue,
              let qty = Double(quantity),
              qty > 0 else { return false }
        
        if isBuy {
            return tp > entry && sl < entry
        } else {
            return tp < entry && sl > entry
        }
    }
    
    private var riskRewardRatio: Double? {
        guard let entry = entryValue,
              let tp = tpValue,
              let sl = slValue else { return nil }
        
        let risk = abs(entry - sl)
        let reward = abs(tp - entry)
        
        guard risk > 0 else { return nil }
        return reward / risk
    }
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Header
                    OrderHeader(ticker: ticker, side: side, currentPrice: currentPrice)
                    
                    // Quantity
                    QuantityInput(quantity: $quantity)
                    
                    // Price Ladder Visualization
                    PriceLadder(
                        currentPrice: currentPrice,
                        entryPrice: entryValue,
                        takeProfitPrice: tpValue,
                        stopLossPrice: slValue,
                        isBuy: isBuy
                    )
                    
                    // Price Inputs
                    VStack(spacing: 16) {
                        PriceInput(
                            label: "Entry Price",
                            value: $entryPrice,
                            placeholder: String(format: "%.2f", currentPrice),
                            icon: "arrow.right.circle.fill",
                            color: .Brand.primary
                        )
                        
                        PriceInput(
                            label: "Take Profit",
                            value: $takeProfitPrice,
                            placeholder: isBuy ? String(format: "%.2f", currentPrice * 1.05) : String(format: "%.2f", currentPrice * 0.95),
                            icon: "arrow.up.circle.fill",
                            color: .Signal.buy
                        )
                        
                        PriceInput(
                            label: "Stop Loss",
                            value: $stopLossPrice,
                            placeholder: isBuy ? String(format: "%.2f", currentPrice * 0.95) : String(format: "%.2f", currentPrice * 1.05),
                            icon: "arrow.down.circle.fill",
                            color: .Signal.sell
                        )
                    }
                    
                    // Risk/Reward Display
                    if let rr = riskRewardRatio {
                        RiskRewardCard(ratio: rr)
                    }
                    
                    // Extended Hours Toggle
                    Toggle(isOn: $outsideRth) {
                        HStack {
                            Image(systemName: "moon.fill")
                                .foregroundColor(.Brand.primary)
                            Text("Extended Hours")
                                .foregroundColor(.Text.primary)
                        }
                    }
                    .tint(.Brand.primary)
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                    
                    // Error Display
                    if let error = error {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.Signal.sell)
                            .padding()
                            .background(Color.Signal.sell.opacity(0.1))
                            .cornerRadius(8)
                    }
                    
                    // Submit Button
                    Button {
                        Task { await submitBracket() }
                    } label: {
                        HStack {
                            if isSubmitting {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "checkmark.circle.fill")
                                Text("Submit Bracket Order")
                                    .bold()
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(isValid ? (isBuy ? Color.Signal.buy : Color.Signal.sell) : Color.gray)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .disabled(!isValid || isSubmitting)
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Bracket Order")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { isPresented = false }
                }
            }
            .alert("Bracket Order Submitted", isPresented: $showSuccess) {
                Button("Done") { isPresented = false }
            } message: {
                if let result = result {
                    Text("Entry: \(result.entry.status)\nTake Profit: \(result.takeProfit.status)\nStop Loss: \(result.stopLoss.status)")
                }
            }
            .onAppear {
                // Pre-fill with sensible defaults
                entryPrice = String(format: "%.2f", currentPrice)
                takeProfitPrice = String(format: "%.2f", currentPrice * (isBuy ? 1.05 : 0.95))
                stopLossPrice = String(format: "%.2f", currentPrice * (isBuy ? 0.95 : 1.05))
            }
        }
    }
    
    private func submitBracket() async {
        guard let entry = entryValue,
              let tp = tpValue,
              let sl = slValue,
              let qty = Double(quantity) else { return }
        
        isSubmitting = true
        error = nil
        
        do {
            result = try await IBKRService.shared.submitBracketOrder(
                ticker: ticker,
                side: side,
                quantity: qty,
                entryPrice: entry,
                takeProfitPrice: tp,
                stopLossPrice: sl,
                outsideRth: outsideRth
            )
            showSuccess = true
        } catch {
            self.error = error.localizedDescription
        }
        
        isSubmitting = false
    }
}

// MARK: - Supporting Views

private struct OrderHeader: View {
    let ticker: String
    let side: String
    let currentPrice: Double
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(ticker)
                    .font(.title2.bold())
                    .foregroundColor(.Text.primary)
                
                Text("Current: $\(currentPrice, specifier: "%.2f")")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            Text(side)
                .font(.headline.bold())
                .foregroundColor(side == "BUY" ? .Signal.buy : .Signal.sell)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(side == "BUY" ? Color.Signal.buy.opacity(0.2) : Color.Signal.sell.opacity(0.2))
                .cornerRadius(8)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct QuantityInput: View {
    @Binding var quantity: String
    
    var body: some View {
        HStack {
            Text("Quantity")
                .foregroundColor(.Text.secondary)
            
            Spacer()
            
            TextField("100", text: $quantity)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .font(.headline)
                .foregroundColor(.Text.primary)
                .frame(width: 100)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct PriceInput: View {
    let label: String
    @Binding var value: String
    let placeholder: String
    let icon: String
    let color: Color
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(color)
            
            Text(label)
                .foregroundColor(.Text.secondary)
            
            Spacer()
            
            TextField(placeholder, text: $value)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .font(.headline)
                .foregroundColor(.Text.primary)
                .frame(width: 100)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct PriceLadder: View {
    let currentPrice: Double
    let entryPrice: Double?
    let takeProfitPrice: Double?
    let stopLossPrice: Double?
    let isBuy: Bool
    
    var body: some View {
        VStack(spacing: 8) {
            // Take Profit (top for buy)
            if isBuy {
                LadderLevel(label: "TP", price: takeProfitPrice, color: .Signal.buy, isCurrent: false)
            } else {
                LadderLevel(label: "SL", price: stopLossPrice, color: .Signal.sell, isCurrent: false)
            }
            
            // Entry
            LadderLevel(label: "Entry", price: entryPrice, color: .Brand.primary, isCurrent: false)
            
            // Current price indicator
            HStack {
                Text("Current")
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary)
                Spacer()
                Rectangle()
                    .fill(Color.Text.tertiary)
                    .frame(height: 1)
                Spacer()
                Text("$\(currentPrice, specifier: "%.2f")")
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary)
            }
            
            // Stop Loss (bottom for buy)
            if isBuy {
                LadderLevel(label: "SL", price: stopLossPrice, color: .Signal.sell, isCurrent: false)
            } else {
                LadderLevel(label: "TP", price: takeProfitPrice, color: .Signal.buy, isCurrent: false)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct LadderLevel: View {
    let label: String
    let price: Double?
    let color: Color
    let isCurrent: Bool
    
    var body: some View {
        HStack {
            Text(label)
                .font(.caption.bold())
                .foregroundColor(color)
                .frame(width: 40, alignment: .leading)
            
            Rectangle()
                .fill(color.opacity(0.5))
                .frame(height: 2)
            
            if let p = price {
                Text("$\(p, specifier: "%.2f")")
                    .font(.caption.bold())
                    .foregroundColor(color)
            } else {
                Text("--")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
    }
}

private struct RiskRewardCard: View {
    let ratio: Double
    
    var body: some View {
        HStack {
            Image(systemName: "scale.3d")
                .foregroundColor(.Brand.primary)
            
            Text("Risk/Reward Ratio")
                .foregroundColor(.Text.secondary)
            
            Spacer()
            
            Text("1:\(ratio, specifier: "%.1f")")
                .font(.headline.bold())
                .foregroundColor(ratio >= 2 ? .Signal.buy : (ratio >= 1 ? .Signal.hold : .Signal.sell))
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

#Preview {
    BracketOrderForm(
        ticker: "AAPL",
        currentPrice: 185.50,
        side: "BUY",
        isPresented: .constant(true)
    )
}
