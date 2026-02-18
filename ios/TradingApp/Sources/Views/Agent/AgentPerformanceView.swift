import SwiftUI

/// REC-318: Agent performance attribution view
/// Shows agent trades vs benchmark, win rate, best/worst decisions
struct AgentPerformanceView: View {
    @StateObject private var viewModel = AgentPerformanceViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Summary Cards
                    summarySection
                    
                    // Return Comparison
                    returnComparisonSection
                    
                    // Win Rate
                    winRateSection
                    
                    // Best/Worst Decisions
                    decisionsSection
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Performance")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .task {
                await viewModel.loadData()
            }
            .refreshable {
                await viewModel.loadData()
            }
        }
    }
    
    // MARK: - Summary Section
    
    private var summarySection: some View {
        HStack(spacing: 12) {
            summaryCard(
                title: "Total Return",
                value: viewModel.totalReturnFormatted,
                color: viewModel.totalReturn >= 0 ? .Signal.positive : .Signal.negative
            )
            
            summaryCard(
                title: "vs S&P 500",
                value: viewModel.alphaFormatted,
                color: viewModel.alpha >= 0 ? .Signal.positive : .Signal.negative
            )
        }
    }
    
    private func summaryCard(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            
            Text(value)
                .font(.system(.title2, design: .monospaced).weight(.bold))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    // MARK: - Return Comparison
    
    private var returnComparisonSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Performance Comparison")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            VStack(spacing: 8) {
                comparisonRow(
                    label: "Agent Trades",
                    value: viewModel.agentReturnFormatted,
                    percentage: viewModel.agentReturn,
                    color: .Brand.primary
                )
                
                comparisonRow(
                    label: "S&P 500 Benchmark",
                    value: viewModel.benchmarkReturnFormatted,
                    percentage: viewModel.benchmarkReturn,
                    color: .Text.secondary
                )
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
        }
    }
    
    private func comparisonRow(label: String, value: String, percentage: Double, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(label)
                    .font(.subheadline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                Text(value)
                    .font(.system(.subheadline, design: .monospaced).weight(.medium))
                    .foregroundColor(percentage >= 0 ? .Signal.positive : .Signal.negative)
            }
            
            // Progress bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.Background.tertiary)
                        .frame(height: 6)
                        .cornerRadius(3)
                    
                    Rectangle()
                        .fill(color)
                        .frame(width: max(0, min(geo.size.width, geo.size.width * CGFloat(abs(percentage) / 30))), height: 6)
                        .cornerRadius(3)
                }
            }
            .frame(height: 6)
        }
    }
    
    // MARK: - Win Rate Section
    
    private var winRateSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Win Rate")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            HStack(spacing: 20) {
                // Win rate circle
                ZStack {
                    Circle()
                        .stroke(Color.Background.tertiary, lineWidth: 8)
                        .frame(width: 80, height: 80)
                    
                    Circle()
                        .trim(from: 0, to: CGFloat(viewModel.winRate / 100))
                        .stroke(Color.Signal.buy, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                        .frame(width: 80, height: 80)
                        .rotationEffect(.degrees(-90))
                    
                    Text("\(Int(viewModel.winRate))%")
                        .font(.system(.title3, design: .monospaced).weight(.bold))
                        .foregroundColor(.Text.primary)
                }
                
                // Stats
                VStack(alignment: .leading, spacing: 8) {
                    statRow(label: "Winning Trades", value: "\(viewModel.winningTrades)", color: .Signal.positive)
                    statRow(label: "Losing Trades", value: "\(viewModel.losingTrades)", color: .Signal.negative)
                    statRow(label: "Total Decisions", value: "\(viewModel.totalDecisions)", color: .Text.secondary)
                }
                
                Spacer()
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
        }
    }
    
    private func statRow(label: String, value: String, color: Color) -> some View {
        HStack {
            Text(label)
                .font(.caption)
                .foregroundColor(.Text.secondary)
            
            Spacer()
            
            Text(value)
                .font(.system(.subheadline, design: .monospaced).weight(.medium))
                .foregroundColor(color)
        }
    }
    
    // MARK: - Decisions Section
    
    private var decisionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Notable Decisions")
                .font(.headline)
                .foregroundColor(.Text.primary)
            
            if let best = viewModel.bestDecision {
                decisionCard(
                    title: "Best Decision",
                    decision: best,
                    icon: "arrow.up.circle.fill",
                    color: .Signal.positive
                )
            }
            
            if let worst = viewModel.worstDecision {
                decisionCard(
                    title: "Worst Decision",
                    decision: worst,
                    icon: "arrow.down.circle.fill",
                    color: .Signal.negative
                )
            }
            
            if viewModel.bestDecision == nil && viewModel.worstDecision == nil {
                Text("No completed decisions yet")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.Background.secondary)
                    .cornerRadius(12)
            }
        }
    }
    
    private func decisionCard(title: String, decision: DecisionSummary, icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.caption.weight(.medium))
                    .foregroundColor(.Text.secondary)
                
                Spacer()
                
                Text(decision.returnFormatted)
                    .font(.system(.subheadline, design: .monospaced).weight(.bold))
                    .foregroundColor(color)
            }
            
            HStack {
                Text(decision.action)
                    .font(.caption.weight(.bold))
                    .foregroundColor(decision.action == "BUY" ? .Signal.buy : .Signal.sell)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(decision.action == "BUY" ? Color.Signal.buy.opacity(0.15) : Color.Signal.sell.opacity(0.15))
                    .cornerRadius(4)
                
                Text(decision.ticker)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                Text(decision.date)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            
            if let lesson = decision.lesson {
                Text(lesson)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .italic()
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
}

// MARK: - View Model

@MainActor
class AgentPerformanceViewModel: ObservableObject {
    @Published var totalReturn: Double = 0
    @Published var alpha: Double = 0
    @Published var agentReturn: Double = 0
    @Published var benchmarkReturn: Double = 0
    @Published var winRate: Double = 0
    @Published var winningTrades: Int = 0
    @Published var losingTrades: Int = 0
    @Published var totalDecisions: Int = 0
    @Published var bestDecision: DecisionSummary?
    @Published var worstDecision: DecisionSummary?
    @Published var isLoading = false
    
    var totalReturnFormatted: String {
        let sign = totalReturn >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", totalReturn))%"
    }
    
    var alphaFormatted: String {
        let sign = alpha >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", alpha))%"
    }
    
    var agentReturnFormatted: String {
        let sign = agentReturn >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", agentReturn))%"
    }
    
    var benchmarkReturnFormatted: String {
        let sign = benchmarkReturn >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", benchmarkReturn))%"
    }
    
    func loadData() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            let stats = try await AgentService.shared.getStats()
            
            // Calculate returns from stats
            totalDecisions = stats.totalDecisions
            let winCount = Int(Double(stats.totalDecisions) * stats.successRate)
            winningTrades = winCount
            losingTrades = stats.totalDecisions - winCount
            winRate = stats.successRate * 100
            
            // Use average outcome from stats
            agentReturn = stats.avgOutcome
            benchmarkReturn = 8.5  // S&P 500 average
            totalReturn = agentReturn
            alpha = agentReturn - benchmarkReturn
            
            // Get best/worst decisions
            let decisions = try await AgentService.shared.getDecisions(limit: 50, action: nil)
            let completedDecisions = decisions.filter { $0.outcome != nil }
            
            if let best = completedDecisions.max(by: { ($0.outcome?.outcomePct ?? 0) < ($1.outcome?.outcomePct ?? 0) }) {
                bestDecision = DecisionSummary(
                    ticker: best.ticker,
                    action: best.action,
                    returnPct: best.outcome?.outcomePct ?? 0,
                    date: formatDate(best.timestamp),
                    lesson: nil  // Lesson not in iOS model yet
                )
            }
            
            if let worst = completedDecisions.min(by: { ($0.outcome?.outcomePct ?? 0) < ($1.outcome?.outcomePct ?? 0) }) {
                worstDecision = DecisionSummary(
                    ticker: worst.ticker,
                    action: worst.action,
                    returnPct: worst.outcome?.outcomePct ?? 0,
                    date: formatDate(worst.timestamp),
                    lesson: nil  // Lesson not in iOS model yet
                )
            }
            
        } catch {
            print("Failed to load performance data: \(error)")
        }
    }
    
    private func formatDate(_ timestamp: String) -> String {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: timestamp) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .medium
            return displayFormatter.string(from: date)
        }
        return timestamp
    }
}

// MARK: - Models

struct DecisionSummary {
    let ticker: String
    let action: String
    let returnPct: Double
    let date: String
    let lesson: String?
    
    var returnFormatted: String {
        let sign = returnPct >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", returnPct))%"
    }
}

#Preview {
    AgentPerformanceView()
}
