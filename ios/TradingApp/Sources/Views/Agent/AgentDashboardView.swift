import SwiftUI

struct AgentDashboardView: View {
    @StateObject private var viewModel = AgentDashboardViewModel()
    @State private var showSettings = false
    @State private var showHistory = false
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Status Card
                    agentStatusCard
                    
                    // Pending Approvals
                    if !viewModel.pendingTrades.isEmpty {
                        pendingApprovalsSection
                    }
                    
                    // Stats Overview
                    statsOverview
                    
                    // Recent Activity
                    recentActivitySection
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("AI Agent")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                AgentSettingsView()
            }
            .sheet(isPresented: $showHistory) {
                AgentHistoryView()
            }
            .refreshable {
                await viewModel.refresh()
            }
            .task {
                await viewModel.loadData()
            }
        }
    }
    
    // MARK: - Agent Status Card
    
    private var agentStatusCard: some View {
        VStack(spacing: 16) {
            HStack {
                // Status indicator
                Circle()
                    .fill(viewModel.statusColor)
                    .frame(width: 12, height: 12)
                
                Text(viewModel.statusText)
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                // Pause/Resume button
                Button {
                    Task {
                        await viewModel.togglePause()
                    }
                } label: {
                    Text(viewModel.isPaused ? "Resume" : "Pause")
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(viewModel.isPaused ? .green : .orange)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(viewModel.isPaused ? Color.green : Color.orange, lineWidth: 1)
                        )
                }
            }
            
            Divider()
            
            // Quick stats
            HStack(spacing: 20) {
                statItem(
                    icon: "clock",
                    label: "Last Run",
                    value: viewModel.lastRunTime
                )
                
                Divider()
                    .frame(height: 40)
                
                statItem(
                    icon: "chart.line.uptrend.xyaxis",
                    label: "Total Runs",
                    value: "\(viewModel.totalRuns)"
                )
                
                Divider()
                    .frame(height: 40)
                
                statItem(
                    icon: "checkmark.circle",
                    label: "Success Rate",
                    value: viewModel.successRate
                )
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func statItem(icon: String, label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .foregroundColor(.Brand.primary)
            Text(value)
                .font(.headline)
                .foregroundColor(.Text.primary)
            Text(label)
                .font(.caption)
                .foregroundColor(.Text.secondary)
        }
        .frame(maxWidth: .infinity)
    }
    
    // MARK: - Pending Approvals Section
    
    private var pendingApprovalsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Pending Approvals")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                Text("\(viewModel.pendingTrades.count)")
                    .font(.subheadline.weight(.bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.orange)
                    .cornerRadius(8)
            }
            
            ForEach(viewModel.pendingTrades) { trade in
                PendingApprovalCard(
                    trade: trade,
                    onApprove: {
                        Task { await viewModel.approveTrade(trade) }
                    },
                    onReject: {
                        Task { await viewModel.rejectTrade(trade) }
                    }
                )
            }
        }
    }
    
    // MARK: - Stats Overview
    
    private var statsOverview: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("This Week")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            HStack(spacing: 12) {
                statsCard(
                    title: "Decisions",
                    value: "\(viewModel.weeklyDecisions)",
                    icon: "brain.head.profile",
                    color: .blue
                )
                
                statsCard(
                    title: "Trades",
                    value: "\(viewModel.weeklyTrades)",
                    icon: "arrow.left.arrow.right",
                    color: .purple
                )
                
                statsCard(
                    title: "P&L",
                    value: viewModel.weeklyPnL,
                    icon: "dollarsign.circle",
                    color: viewModel.weeklyPnLPositive ? .green : .red
                )
            }
        }
    }
    
    private func statsCard(title: String, value: String, icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Spacer()
            }
            
            Text(value)
                .font(.title2.weight(.bold))
                .foregroundColor(.Text.primary)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.Text.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    // MARK: - Recent Activity
    
    private var recentActivitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recent Activity")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                Button("See All") {
                    showHistory = true
                }
                .font(.subheadline)
                .foregroundColor(.Brand.primary)
            }
            
            if viewModel.recentExecutions.isEmpty {
                Text("No recent activity")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            } else {
                ForEach(viewModel.recentExecutions.prefix(3)) { execution in
                    executionRow(execution)
                }
            }
        }
    }
    
    private func executionRow(_ execution: AgentExecution) -> some View {
        HStack {
            // Action badge
            Text(execution.action)
                .font(.caption.weight(.bold))
                .foregroundColor(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(execution.action == "BUY" ? Color.green : Color.red)
                .cornerRadius(4)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(execution.ticker)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.Text.primary)
                
                Text("\(execution.shares) shares")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            
            Spacer()
            
            if let price = execution.fillPrice {
                Text("$\(price, specifier: "%.2f")")
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.Text.primary)
            }
            
            Image(systemName: execution.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundColor(execution.success ? .green : .red)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(8)
    }
}

// MARK: - ViewModel

@MainActor
class AgentDashboardViewModel: ObservableObject {
    @Published var status: String = "paused"
    @Published var pendingTrades: [PendingTrade] = []
    @Published var recentExecutions: [AgentExecution] = []
    @Published var totalRuns: Int = 0
    @Published var weeklyDecisions: Int = 0
    @Published var weeklyTrades: Int = 0
    @Published var weeklyPnLValue: Double = 0
    @Published var isLoading = false
    @Published var lastRunDate: Date?
    
    var isPaused: Bool { status == "paused" }
    
    var statusText: String {
        switch status {
        case "active": return "Agent Active"
        case "running": return "Running..."
        case "paused": return "Agent Paused"
        case "error": return "Error"
        default: return "Unknown"
        }
    }
    
    var statusColor: Color {
        switch status {
        case "active": return .green
        case "running": return .blue
        case "paused": return .orange
        case "error": return .red
        default: return .gray
        }
    }
    
    var lastRunTime: String {
        guard let date = lastRunDate else { return "Never" }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
    
    var successRate: String {
        guard totalRuns > 0 else { return "N/A" }
        // Placeholder - would calculate from actual data
        return "85%"
    }
    
    var weeklyPnL: String {
        let formatted = abs(weeklyPnLValue).formatted(.currency(code: "USD"))
        return weeklyPnLValue >= 0 ? "+\(formatted)" : "-\(formatted)"
    }
    
    var weeklyPnLPositive: Bool { weeklyPnLValue >= 0 }
    
    func loadData() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            // Load status
            let statusResponse = try await AgentService.shared.getStatus()
            status = statusResponse.status
            totalRuns = statusResponse.totalRuns
            
            // Load pending trades
            pendingTrades = try await AgentService.shared.getPendingTrades()
            
            // Load recent executions
            recentExecutions = try await AgentService.shared.getExecutions(limit: 5)
            
            // Load stats
            let stats = try await AgentService.shared.getStats()
            weeklyTrades = stats.weeklyTrades
            weeklyDecisions = stats.totalDecisions
        } catch {
            print("Failed to load agent data: \(error)")
        }
    }
    
    func refresh() async {
        await loadData()
    }
    
    func togglePause() async {
        do {
            if isPaused {
                _ = try await AgentService.shared.resume()
                status = "active"
            } else {
                _ = try await AgentService.shared.pause()
                status = "paused"
            }
        } catch {
            print("Failed to toggle pause: \(error)")
        }
    }
    
    func approveTrade(_ trade: PendingTrade) async {
        do {
            let response = try await AgentService.shared.approveTrade(pendingId: trade.id)
            if response.success {
                pendingTrades.removeAll { $0.id == trade.id }
                await loadData() // Refresh to get updated executions
            }
        } catch {
            print("Failed to approve trade: \(error)")
        }
    }
    
    func rejectTrade(_ trade: PendingTrade) async {
        do {
            let response = try await AgentService.shared.rejectTrade(pendingId: trade.id)
            if response.success {
                pendingTrades.removeAll { $0.id == trade.id }
            }
        } catch {
            print("Failed to reject trade: \(error)")
        }
    }
}

#Preview {
    AgentDashboardView()
}
