import SwiftUI

struct AgentHistoryView: View {
    @StateObject private var viewModel = AgentHistoryViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Filter tabs
                filterTabs
                
                // Content
                if viewModel.isLoading {
                    loadingView
                } else if viewModel.isEmpty {
                    emptyView
                } else {
                    historyList
                }
            }
            .background(Color.Background.primary)
            .navigationTitle("Agent History")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
            .task {
                await viewModel.loadData()
            }
        }
    }
    
    // MARK: - Filter Tabs
    
    private var filterTabs: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                filterChip("All", filter: .all)
                filterChip("Decisions", filter: .decisions)
                filterChip("Executions", filter: .executions)
                filterChip("Buy", filter: .buy)
                filterChip("Sell", filter: .sell)
            }
            .padding(.horizontal)
            .padding(.vertical, 12)
        }
        .background(Color.Background.secondary)
    }
    
    private func filterChip(_ title: String, filter: HistoryFilter) -> some View {
        Button {
            viewModel.selectedFilter = filter
            Task { await viewModel.loadData() }
        } label: {
            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundColor(viewModel.selectedFilter == filter ? .white : .Text.primary)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .fill(viewModel.selectedFilter == filter ? Color.Brand.primary : Color.Background.tertiary)
                )
        }
    }
    
    // MARK: - Loading View
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Loading history...")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Empty View
    
    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 48))
                .foregroundColor(.Text.tertiary)
            
            Text("No History Yet")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            Text("Agent activity will appear here")
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - History List
    
    private var historyList: some View {
        List {
            ForEach(viewModel.groupedItems.keys.sorted().reversed(), id: \.self) { date in
                Section {
                    ForEach(viewModel.groupedItems[date] ?? [], id: \.id) { item in
                        historyRow(item)
                    }
                } header: {
                    Text(date)
                        .font(.caption.weight(.medium))
                        .foregroundColor(.Text.secondary)
                }
            }
        }
        .listStyle(.plain)
    }
    
    private func historyRow(_ item: HistoryItem) -> some View {
        HStack(spacing: 12) {
            // Type icon
            ZStack {
                Circle()
                    .fill(item.iconBackground)
                    .frame(width: 36, height: 36)
                
                Image(systemName: item.icon)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(item.iconColor)
            }
            
            // Details
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(item.action)
                        .font(.caption.weight(.bold))
                        .foregroundColor(item.actionColor)
                    
                    Text(item.ticker)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(.Text.primary)
                }
                
                Text(item.subtitle)
                    .font(.system(.caption, design: .monospaced))  // REC-309: SF Mono for prices
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            // Outcome/Status
            VStack(alignment: .trailing, spacing: 4) {
                if let outcome = item.outcome {
                    Text(outcome)
                        .font(.system(.subheadline, design: .monospaced).weight(.medium))  // REC-309: SF Mono for %
                        .foregroundColor(item.outcomeColor)
                }
                
                Text(item.time)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - ViewModel

enum HistoryFilter {
    case all, decisions, executions, buy, sell
}

struct HistoryItem: Identifiable {
    let id: String
    let type: ItemType
    let action: String
    let ticker: String
    let subtitle: String
    let outcome: String?
    let outcomePositive: Bool
    let timestamp: Date
    
    enum ItemType {
        case decision
        case execution
    }
    
    var icon: String {
        switch type {
        case .decision: return "brain.head.profile"
        case .execution: return "arrow.left.arrow.right"
        }
    }
    
    var iconBackground: Color {
        switch type {
        case .decision: return Color.blue.opacity(0.2)
        case .execution: return Color.purple.opacity(0.2)
        }
    }
    
    var iconColor: Color {
        switch type {
        case .decision: return .blue
        case .execution: return .purple
        }
    }
    
    var actionColor: Color {
        action.uppercased() == "BUY" ? .green : .red
    }
    
    var outcomeColor: Color {
        outcomePositive ? .green : .red
    }
    
    var time: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: timestamp)
    }
    
    var dateKey: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: timestamp)
    }
}

@MainActor
class AgentHistoryViewModel: ObservableObject {
    @Published var selectedFilter: HistoryFilter = .all
    @Published var items: [HistoryItem] = []
    @Published var isLoading = false
    
    var isEmpty: Bool { items.isEmpty && !isLoading }
    
    var groupedItems: [String: [HistoryItem]] {
        Dictionary(grouping: items) { $0.dateKey }
    }
    
    func loadData() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            var allItems: [HistoryItem] = []
            let formatter = ISO8601DateFormatter()
            
            // Load based on filter
            switch selectedFilter {
            case .all, .decisions, .buy, .sell:
                let action: String? = {
                    switch selectedFilter {
                    case .buy: return "BUY"
                    case .sell: return "SELL"
                    default: return nil
                    }
                }()
                
                let decisions = try await AgentService.shared.getDecisions(limit: 50, action: action)
                allItems += decisions.map { decision in
                    HistoryItem(
                        id: decision.id,
                        type: .decision,
                        action: decision.action,
                        ticker: decision.ticker,
                        subtitle: "Confidence: \(Int(decision.confidence * 100))%",
                        outcome: decision.outcome.map { "\($0.outcomePct >= 0 ? "+" : "")\(String(format: "%.1f", $0.outcomePct))%" },
                        outcomePositive: decision.outcome?.outcomePct ?? 0 >= 0,
                        timestamp: formatter.date(from: decision.timestamp) ?? Date()
                    )
                }
                
            case .executions:
                break // Will add executions below
            }
            
            // Add executions for all/executions filter
            if selectedFilter == .all || selectedFilter == .executions {
                let executions = try await AgentService.shared.getExecutions(limit: 50)
                allItems += executions.compactMap { execution in
                    guard let dateStr = execution.executedAt,
                          let date = formatter.date(from: dateStr) else { return nil }
                    
                    return HistoryItem(
                        id: execution.id,
                        type: .execution,
                        action: execution.action,
                        ticker: execution.ticker,
                        subtitle: "\(execution.shares) shares @ $\(String(format: "%.2f", execution.fillPrice ?? 0))",
                        outcome: execution.success ? "Filled" : "Failed",
                        outcomePositive: execution.success,
                        timestamp: date
                    )
                }
            }
            
            // Sort by timestamp
            items = allItems.sorted { $0.timestamp > $1.timestamp }
        } catch {
            print("Failed to load history: \(error)")
            items = []
        }
    }
}

#Preview {
    AgentHistoryView()
}
