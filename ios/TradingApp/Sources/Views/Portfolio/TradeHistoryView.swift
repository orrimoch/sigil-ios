import SwiftUI

// MARK: - REC-167: Trade History Screen

/// Trade history view showing actual IB executions
struct TradeHistoryView: View {
    @State private var executions: [IBKRTradeExecution] = []
    @State private var isLoading = true
    @State private var error: String?
    @State private var filterSide: String? = nil
    
    var filteredExecutions: [IBKRTradeExecution] {
        guard let side = filterSide else { return executions }
        return executions.filter { $0.side.uppercased().contains(side.uppercased()) }
    }
    
    var totalCommission: Double {
        executions.compactMap { $0.commission }.reduce(0, +)
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Summary Card
                if !executions.isEmpty {
                    SummaryCard(
                        executionCount: executions.count,
                        totalCommission: totalCommission
                    )
                }
                
                // Filter Bar
                TradeHistoryFilterBar(selectedSide: $filterSide)
                
                // Executions List
                if isLoading {
                    LoadingPlaceholder()
                } else if let error = error {
                    ErrorView(message: error) {
                        Task { await loadHistory() }
                    }
                } else if filteredExecutions.isEmpty {
                    EmptyStateView()
                } else {
                    LazyVStack(spacing: 12) {
                        ForEach(filteredExecutions) { execution in
                            ExecutionRow(execution: execution)
                        }
                    }
                }
            }
            .padding()
        }
        .background(Color.Background.primary)
        .navigationTitle("Trade History")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .refreshable {
            await loadHistory()
        }
        .task {
            await loadHistory()
        }
    }
    
    private func loadHistory() async {
        guard IBKRService.shared.isConnected else {
            error = "Not connected to IB Gateway"
            isLoading = false
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            executions = try await IBKRService.shared.getTradeHistory()
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
}

// MARK: - Supporting Views

private struct SummaryCard: View {
    let executionCount: Int
    let totalCommission: Double
    
    var body: some View {
        HStack(spacing: 24) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Executions")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Text("\(executionCount)")
                    .font(.title2.bold())
                    .foregroundColor(.Text.primary)
            }
            
            Divider()
                .frame(height: 40)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("Total Commission")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Text("$\(totalCommission, specifier: "%.2f")")
                    .font(.title2.bold())
                    .foregroundColor(.Brand.primary)
            }
            
            Spacer()
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct TradeHistoryFilterBar: View {
    @Binding var selectedSide: String?
    
    var body: some View {
        HStack(spacing: 12) {
            TradeHistoryFilterChip(label: "All", isSelected: selectedSide == nil) {
                selectedSide = nil
            }
            TradeHistoryFilterChip(label: "Buys", isSelected: selectedSide == "BOT") {
                selectedSide = "BOT"
            }
            TradeHistoryFilterChip(label: "Sells", isSelected: selectedSide == "SLD") {
                selectedSide = "SLD"
            }
            Spacer()
        }
    }
}

private struct TradeHistoryFilterChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption.bold())
                .foregroundColor(isSelected ? .Background.primary : .Text.secondary)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(isSelected ? Color.Brand.primary : Color.Background.secondary)
                .cornerRadius(16)
        }
    }
}

private struct ExecutionRow: View {
    let execution: IBKRTradeExecution
    
    var isBuy: Bool {
        execution.side.uppercased().contains("BOT") || execution.side.uppercased() == "BUY"
    }
    
    var formattedTime: String {
        guard let timeStr = execution.time else { return "-" }
        // Parse ISO 8601 and format nicely
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: timeStr) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateFormat = "MMM d, h:mm a"
            return displayFormatter.string(from: date)
        }
        return timeStr
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Side Indicator
            Circle()
                .fill(isBuy ? Color.Signal.buy : Color.Signal.sell)
                .frame(width: 10, height: 10)
            
            // Ticker and details
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(execution.ticker)
                        .font(.headline.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text(isBuy ? "BUY" : "SELL")
                        .font(.caption.bold())
                        .foregroundColor(isBuy ? .Signal.buy : .Signal.sell)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(isBuy ? Color.Signal.buy.opacity(0.2) : Color.Signal.sell.opacity(0.2))
                        .cornerRadius(4)
                }
                
                Text(formattedTime)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            Spacer()
            
            // Quantity and Price
            VStack(alignment: .trailing, spacing: 4) {
                Text("\(Int(execution.quantity)) @ $\(execution.price, specifier: "%.2f")")
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
                
                if let commission = execution.commission {
                    Text("Fee: $\(commission, specifier: "%.2f")")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

private struct LoadingPlaceholder: View {
    var body: some View {
        VStack(spacing: 12) {
            ForEach(0..<5, id: \.self) { index in
                HStack(spacing: 12) {
                    // Side indicator placeholder
                    Circle()
                        .fill(Color.Background.tertiary)
                        .frame(width: 10, height: 10)
                    
                    VStack(alignment: .leading, spacing: 6) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.Background.tertiary)
                            .frame(width: 80, height: 16)
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.Background.tertiary)
                            .frame(width: 120, height: 12)
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 6) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.Background.tertiary)
                            .frame(width: 100, height: 16)
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.Background.tertiary)
                            .frame(width: 60, height: 12)
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
                .shimmering()
            }
        }
    }
}

private struct ErrorView: View {
    let message: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.largeTitle)
                .foregroundColor(.Signal.hold)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                onRetry()
            }
            .font(.headline)
            .foregroundColor(.Brand.primary)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

private struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.iconSize(50)).limitedScaling()
                .foregroundColor(.Text.tertiary)
            
            Text("No Executions Yet")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            Text("Your trade executions from IB Gateway will appear here")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

// MARK: - Shimmer Modifier

struct ShimmerModifier: ViewModifier {
    @State private var isAnimating = false
    
    func body(content: Content) -> some View {
        content
            .overlay {
                GeometryReader { geometry in
                    let width = geometry.size.width
                    let gradientWidth = width * 0.5
                    
                    LinearGradient(
                        colors: [
                            Color.white.opacity(0),
                            Color.white.opacity(0.4),
                            Color.white.opacity(0)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: gradientWidth)
                    .offset(x: isAnimating ? width : -gradientWidth)
                    .animation(
                        .linear(duration: 1.2)
                        .repeatForever(autoreverses: false),
                        value: isAnimating
                    )
                }
                .mask(content)
            }
            .onAppear {
                // Delay to ensure view is laid out
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    isAnimating = true
                }
            }
    }
}

extension View {
    func shimmering() -> some View {
        modifier(ShimmerModifier())
    }
}

#Preview {
    NavigationStack {
        TradeHistoryView()
    }
}
