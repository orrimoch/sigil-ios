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
            ForEach(0..<5, id: \.self) { _ in
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.Background.secondary)
                    .frame(height: 80)
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
                .font(.system(size: 50))
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
    @State private var phase: CGFloat = 0
    
    func body(content: Content) -> some View {
        content
            .redacted(reason: .placeholder)
            .overlay {
                GeometryReader { geometry in
                    LinearGradient(
                        colors: [
                            Color.clear,
                            Color.white.opacity(0.3),
                            Color.clear
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geometry.size.width * 0.6)
                    .offset(x: -geometry.size.width * 0.3 + phase * geometry.size.width * 1.6)
                }
                .mask(content)
            }
            .onAppear {
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                    phase = 1
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
