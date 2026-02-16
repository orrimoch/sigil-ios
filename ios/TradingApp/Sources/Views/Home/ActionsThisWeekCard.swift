import SwiftUI

/// GAP-005: Actions This Week Card
/// Shows recommended trades based on portfolio vs AI scores
struct ActionsThisWeekCard: View {
    let actions: [WeeklyAction]
    
    var body: some View {
        if !actions.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "checklist")
                        .foregroundColor(.Accent.gold)
                    Text("Actions This Week")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    Text("\(actions.count)")
                        .font(.caption.weight(.semibold))
                        .foregroundColor(.Accent.gold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.Accent.gold.opacity(0.15))
                        .cornerRadius(8)
                }
                
                ForEach(actions) { action in
                    NavigationLink {
                        StockDetailView(ticker: action.ticker)
                    } label: {
                        HStack(spacing: 12) {
                            // Action type badge
                            HStack(spacing: 4) {
                                Image(systemName: action.type.icon)
                                    .font(.caption)
                                Text(action.type.label)
                                    .font(.caption.weight(.bold))
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(action.type.color)
                            .cornerRadius(6)
                            
                            // Ticker and company
                            VStack(alignment: .leading, spacing: 2) {
                                Text(action.ticker)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundColor(.Text.primary)
                                
                                Text(action.reason)
                                    .font(.caption)
                                    .foregroundColor(.Text.secondary)
                                    .lineLimit(1)
                            }
                            
                            Spacer()
                            
                            // Score
                            Text("\(action.score)")
                                .font(.headline.monospacedDigit())
                                .foregroundColor(action.type == .buy ? .Signal.buy : .Signal.sell)
                        }
                        .padding(.vertical, 8)
                    }
                    
                    if action.id != actions.last?.id {
                        Divider()
                            .background(Color.Utility.divider)
                    }
                }
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
        }
    }
}

#Preview {
    ActionsThisWeekCard(actions: [
        WeeklyAction(type: .buy, ticker: "NVDA", companyName: "NVIDIA", score: 85, reason: "Score 85 — Strong fundamentals"),
        WeeklyAction(type: .sell, ticker: "INTC", companyName: "Intel", score: 38, reason: "Score 38 — Consider reducing")
    ])
    .padding()
    .background(Color.Background.primary)
}
