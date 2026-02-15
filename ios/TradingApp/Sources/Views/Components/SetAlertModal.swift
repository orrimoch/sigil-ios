import SwiftUI

/// Modal for setting a price alert (REC-158)
struct SetAlertModal: View {
    let ticker: String
    let currentPrice: Double
    @Environment(\.dismiss) private var dismiss
    
    @State private var condition: PriceAlertCondition = .above
    @State private var targetPrice: String = ""
    @State private var isSubmitting = false
    @State private var showSuccess = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Stock info
                VStack(spacing: 4) {
                    Text(ticker)
                        .font(.title.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text("Current: \(currentPrice.asCurrency)")
                        .font(.headline)
                        .foregroundColor(.Text.secondary)
                }
                .padding(.top)
                
                // Condition picker
                VStack(alignment: .leading, spacing: 8) {
                    Text("Alert when price is")
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                    
                    Picker("Condition", selection: $condition) {
                        ForEach(PriceAlertCondition.allCases, id: \.self) { cond in
                            HStack {
                                Image(systemName: cond.icon)
                                Text(cond.displayName)
                            }
                            .tag(cond)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                .padding(.horizontal)
                
                // Target price input
                VStack(spacing: 8) {
                    Text("Target Price")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    
                    HStack {
                        Text("$")
                            .font(.price).limitedScaling()
                            .foregroundColor(.Text.tertiary)
                        
                        TextField("0.00", text: $targetPrice)
                            .font(.price).limitedScaling()
                            .foregroundColor(.Text.primary)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
                }
                .padding(.horizontal)
                
                // Preview text
                if let target = Double(targetPrice), target > 0 {
                    let changePercent = ((target - currentPrice) / currentPrice) * 100
                    let changeText = changePercent >= 0 ? "+\(String(format: "%.2f", changePercent))%" : "\(String(format: "%.2f", changePercent))%"
                    
                    HStack {
                        Image(systemName: condition.icon)
                            .foregroundColor(condition == .above ? .Signal.buy : .Signal.sell)
                        
                        Text("Alert when \(ticker) goes \(condition.displayName.lowercased()) \(target.asCurrency)")
                            .font(.subheadline)
                            .foregroundColor(.Text.secondary)
                        
                        Text("(\(changeText))")
                            .font(.caption)
                            .foregroundColor(changePercent >= 0 ? .Signal.buy : .Signal.sell)
                    }
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(8)
                    .padding(.horizontal)
                }
                
                // Error message
                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Signal.sell)
                        .padding()
                        .background(Color.Signal.sell.opacity(0.15))
                        .cornerRadius(8)
                        .padding(.horizontal)
                }
                
                Spacer()
                
                // Submit button
                Button {
                    Task { await createAlert() }
                } label: {
                    HStack {
                        if isSubmitting {
                            ProgressView().tint(.white)
                        } else {
                            Image(systemName: "bell.badge.fill")
                            Text("Set Alert")
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .padding(.horizontal)
                .disabled(targetPrice.isEmpty || Double(targetPrice) == nil || Double(targetPrice) == 0 || isSubmitting)
                .padding(.bottom)
            }
            .background(Color.Background.primary)
            .navigationTitle("Set Price Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.Accent.gold)
                }
            }
            .alert("Alert Created!", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                if let target = Double(targetPrice) {
                    Text("You'll be notified when \(ticker) goes \(condition.displayName.lowercased()) \(target.asCurrency)")
                }
            }
            .onAppear {
                // Pre-fill with suggested price based on condition
                if condition == .above {
                    targetPrice = String(format: "%.2f", currentPrice * 1.05)  // 5% above
                } else {
                    targetPrice = String(format: "%.2f", currentPrice * 0.95)  // 5% below
                }
            }
            .onChange(of: condition) { _, newCondition in
                // Update suggested price when condition changes
                if newCondition == .above {
                    targetPrice = String(format: "%.2f", currentPrice * 1.05)
                } else {
                    targetPrice = String(format: "%.2f", currentPrice * 0.95)
                }
            }
        }
    }
    
    private func createAlert() async {
        guard let target = Double(targetPrice), target > 0 else {
            errorMessage = "Please enter a valid price"
            return
        }
        
        // Validation: above condition should have target > current, below should have target < current
        if condition == .above && target <= currentPrice {
            errorMessage = "Target price must be above current price for 'Above' alerts"
            return
        }
        if condition == .below && target >= currentPrice {
            errorMessage = "Target price must be below current price for 'Below' alerts"
            return
        }
        
        isSubmitting = true
        errorMessage = nil
        
        do {
            _ = try await APIService.shared.createPriceAlert(
                ticker: ticker,
                condition: condition,
                targetPrice: target
            )
            showSuccess = true
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isSubmitting = false
    }
}

// MARK: - Preview

#Preview {
    SetAlertModal(ticker: "AAPL", currentPrice: 185.42)
}
