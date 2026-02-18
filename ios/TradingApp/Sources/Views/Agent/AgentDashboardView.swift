import SwiftUI

struct AgentDashboardView: View {
    @StateObject private var viewModel = AgentDashboardViewModel()
    @State private var showSettings = false
    @State private var showHistory = false
    
    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.status == "paused" && viewModel.recentExecutions.isEmpty {
                    // REC-310: Show loading state on initial load
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.2)
                        Text("Loading agent status...")
                            .font(.subheadline)
                            .foregroundColor(.Text.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
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
                }
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
            .alert("Error", isPresented: .init(
                get: { viewModel.errorMessage != nil },
                set: { if !$0 { viewModel.errorMessage = nil } }
            )) {
                Button("OK") { viewModel.errorMessage = nil }
            } message: {
                Text(viewModel.errorMessage ?? "")
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
                        .foregroundColor(viewModel.isPaused ? .green : .Signal.paused)  // REC-315: WCAG contrast
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(viewModel.isPaused ? Color.green : Color.Signal.paused, lineWidth: 1)
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
                    .background(Color.Signal.paused)  // REC-315: WCAG contrast
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
                .font(.system(.title2, design: .monospaced).weight(.bold))  // REC-309: SF Mono for stats
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
                    .font(.mono)  // REC-309: SF Mono for financial data
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
    @Published var stats: AgentStats?
    @Published var errorMessage: String?
    
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
        case "paused": return .Signal.paused  // REC-315: WCAG contrast
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
        // Use actual success rate from stats if available
        if let stats = stats, stats.totalExecutions > 0 {
            let rate = stats.successRate * 100
            return String(format: "%.0f%%", rate)
        }
        guard totalRuns > 0 else { return "N/A" }
        return "N/A"
    }
    
    var weeklyPnL: String {
        let formatted = abs(weeklyPnLValue).formatted(.currency(code: "USD"))
        return weeklyPnLValue >= 0 ? "+\(formatted)" : "-\(formatted)"
    }
    
    var weeklyPnLPositive: Bool { weeklyPnLValue >= 0 }
    
    func loadData() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        // Load status
        if let statusURL = URL(string: "http://127.0.0.1:8000/api/v1/agent/status") {
            do {
                let (data, _) = try await URLSession.shared.data(from: statusURL)
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let statusStr = json["status"] as? String {
                        status = statusStr
                    }
                    if let runs = json["total_runs"] as? Int {
                        totalRuns = runs
                    }
                }
            } catch {
                errorMessage = "Failed to load status"
            }
        }
        
        // Load pending trades
        if let pendingURL = URL(string: "http://127.0.0.1:8000/api/v1/agent/pending") {
            do {
                let (data, _) = try await URLSession.shared.data(from: pendingURL)
                // Don't use convertFromSnakeCase - PendingTrade has explicit CodingKeys
                let decoder = JSONDecoder()
                let response = try decoder.decode(PendingTradesResponse.self, from: data)
                pendingTrades = response.pending
                print("✅ Loaded \(response.pending.count) pending trades")
            } catch {
                print("❌ Failed to load pending trades: \(error)")
            }
        }
        
        // Load weekly stats
        if let statsURL = URL(string: "http://127.0.0.1:8000/api/v1/agent/stats") {
            do {
                let (data, _) = try await URLSession.shared.data(from: statsURL)
                // AgentStats has explicit CodingKeys, no strategy needed
                let loadedStats = try JSONDecoder().decode(AgentStats.self, from: data)
                stats = loadedStats
                weeklyDecisions = loadedStats.totalDecisions
                weeklyTrades = loadedStats.weeklyTrades
                print("✅ Loaded stats: \(loadedStats.weeklyTrades) weekly trades")
            } catch {
                print("❌ Failed to load stats: \(error)")
            }
        }
        
        // Load recent executions
        if let execURL = URL(string: "http://127.0.0.1:8000/api/v1/agent/executions?limit=10") {
            do {
                let (data, _) = try await URLSession.shared.data(from: execURL)
                // AgentExecution has explicit CodingKeys, no strategy needed
                let response = try JSONDecoder().decode(ExecutionsResponse.self, from: data)
                recentExecutions = response.executions
                print("✅ Loaded \(response.executions.count) recent executions")
            } catch {
                print("❌ Failed to load executions: \(error)")
            }
        }
    }
    
    func refresh() async {
        await loadData()
    }
    
    func togglePause() async {
        let endpoint = isPaused ? "resume" : "pause"
        guard let url = URL(string: "http://127.0.0.1:8000/api/v1/agent/\(endpoint)") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                // Reload all data to refresh UI
                await loadData()
            }
        } catch {
            errorMessage = "Network error: \(error.localizedDescription)"
        }
    }
    
    func approveTrade(_ trade: PendingTrade) async {
        do {
            let response = try await AgentService.shared.approveTrade(pendingId: trade.id)
            if response.success {
                pendingTrades.removeAll { $0.id == trade.id }
                await loadData() // Refresh to get updated executions
            } else {
                // Show error message from backend
                errorMessage = response.message
            }
        } catch {
            errorMessage = "Failed to approve trade: \(error.localizedDescription)"
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
