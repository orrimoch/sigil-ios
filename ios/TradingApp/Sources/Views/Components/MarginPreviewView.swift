import SwiftUI

// MARK: - REC-166: What-If Margin Preview Modal

/// Margin preview sheet shown before order confirmation
struct MarginPreviewSheet: View {
    @Environment(\.dismiss) private var dismiss
    
    let ticker: String
    let side: String
    let quantity: Double
    let orderType: String
    let limitPrice: Double?
    let onConfirm: () -> Void
    
    @State private var whatIfResult: IBKRWhatIfResult?
    @State private var isLoading = true
    @State private var error: String?
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    if isLoading {
                        VStack(spacing: 16) {
                            ProgressView()
                                .scaleEffect(1.5)
                                .tint(.Brand.primary)
                            Text("Calculating margin impact...")
                                .font(.subheadline)
                                .foregroundColor(.Text.secondary)
                        }
                        .frame(maxWidth: .infinity, minHeight: 300)
                    } else if let error = error {
                        VStack(spacing: 16) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.largeTitle)
                                .foregroundColor(.Signal.hold)
                            Text("Unable to calculate margin")
                                .font(.headline)
                            Text(error)
                                .font(.caption)
                                .foregroundColor(.Text.secondary)
                        }
                        .frame(maxWidth: .infinity, minHeight: 300)
                    } else if let result = whatIfResult {
                        // Order Summary
                        OrderSummaryCard(
                            ticker: ticker,
                            side: side,
                            quantity: quantity,
                            orderType: orderType,
                            limitPrice: limitPrice
                        )
                        
                        // Margin Impact
                        MarginImpactCard(result: result)
                        
                        // Commission Estimate
                        CommissionCard(result: result)
                        
                        // Warning if present
                        if let warning = result.warningText, !warning.isEmpty {
                            WarningBanner(message: warning)
                        }
                        
                        // Action Buttons
                        VStack(spacing: 12) {
                            Button {
                                onConfirm()
                                dismiss()
                            } label: {
                                Text("Confirm Order")
                                    .font(.headline.bold())
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(side == "BUY" ? Color.Signal.buy : Color.Signal.sell)
                                    .foregroundColor(.white)
                                    .cornerRadius(12)
                            }
                            
                            Button {
                                dismiss()
                            } label: {
                                Text("Cancel")
                                    .font(.headline)
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.Background.secondary)
                                    .foregroundColor(.Text.primary)
                                    .cornerRadius(12)
                            }
                        }
                        .padding(.top, 10)
                    }
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Margin Preview")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .task {
            await loadWhatIf()
        }
    }
    
    private func loadWhatIf() async {
        isLoading = true
        error = nil
        
        do {
            whatIfResult = try await IBKRService.shared.whatIfOrder(
                ticker: ticker,
                side: side,
                quantity: quantity,
                orderType: orderType,
                limitPrice: limitPrice
            )
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - Supporting Views

private struct OrderSummaryCard: View {
    let ticker: String
    let side: String
    let quantity: Double
    let orderType: String
    let limitPrice: Double?
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Order")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Spacer()
            }
            
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(ticker)
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)
                    Text(orderType)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(side) \(Int(quantity))")
                        .font(.headline.bold())
                        .foregroundColor(side == "BUY" ? .Signal.buy : .Signal.sell)
                    
                    if let price = limitPrice {
                        Text("@ $\(price, specifier: "%.2f")")
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

private struct MarginImpactCard: View {
    let result: IBKRWhatIfResult
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Text("Margin Impact")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Spacer()
            }
            
            // Initial Margin
            MarginRow(
                label: "Initial Margin",
                before: result.initMarginBefore,
                after: result.initMarginAfter,
                change: result.initMarginChange
            )
            
            Divider()
                .background(Color.Background.tertiary)
            
            // Maintenance Margin
            MarginRow(
                label: "Maintenance Margin",
                before: result.maintMarginBefore,
                after: result.maintMarginAfter,
                change: result.maintMarginChange
            )
            
            Divider()
                .background(Color.Background.tertiary)
            
            // Equity
            MarginRow(
                label: "Equity w/ Loan",
                before: result.equityWithLoanBefore,
                after: result.equityWithLoanAfter,
                change: result.equityWithLoanChange
            )
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct MarginRow: View {
    let label: String
    let before: Double
    let after: Double
    let change: Double
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text(label)
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                Spacer()
            }
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Before")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(before, specifier: "%.2f")")
                        .font(.subheadline)
                        .foregroundColor(.Text.primary)
                }
                
                Spacer()
                
                Image(systemName: "arrow.right")
                    .foregroundColor(.Text.tertiary)
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("After")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Text("$\(after, specifier: "%.2f")")
                        .font(.subheadline)
                        .foregroundColor(.Text.primary)
                }
                
                // Change indicator
                Text(change >= 0 ? "+$\(change, specifier: "%.2f")" : "-$\(abs(change), specifier: "%.2f")")
                    .font(.caption.bold())
                    .foregroundColor(change >= 0 ? .Signal.sell : .Signal.buy)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(change >= 0 ? Color.Signal.sell.opacity(0.2) : Color.Signal.buy.opacity(0.2))
                    .cornerRadius(6)
            }
        }
    }
}

private struct CommissionCard: View {
    let result: IBKRWhatIfResult
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Commission Estimate")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Spacer()
            }
            
            HStack {
                Image(systemName: "dollarsign.circle")
                    .foregroundColor(.Brand.primary)
                
                if result.minCommission > 0 && result.maxCommission > 0 {
                    Text("$\(result.minCommission, specifier: "%.2f") - $\(result.maxCommission, specifier: "%.2f")")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                } else {
                    Text("Calculating...")
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                }
                
                Spacer()
                
                Text(result.commissionCurrency)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct WarningBanner: View {
    let message: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.Signal.hold)
            
            Text(message)
                .font(.caption)
                .foregroundColor(.Text.primary)
            
            Spacer()
        }
        .padding()
        .background(Color.Signal.hold.opacity(0.15))
        .cornerRadius(12)
    }
}

#Preview {
    MarginPreviewSheet(
        ticker: "NVDA",
        side: "BUY",
        quantity: 50,
        orderType: "MARKET",
        limitPrice: nil,
        onConfirm: {}
    )
}
