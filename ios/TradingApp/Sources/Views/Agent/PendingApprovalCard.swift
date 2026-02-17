import SwiftUI

struct PendingApprovalCard: View {
    let trade: PendingTrade
    let onApprove: () -> Void
    let onReject: () -> Void
    
    @State private var isExpanded = false
    @State private var isApproving = false
    @State private var isRejecting = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView
            
            // Expanded details
            if isExpanded {
                Divider()
                    .padding(.vertical, 8)
                
                rationaleView
                
                Divider()
                    .padding(.vertical, 8)
                
                actionButtons
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(trade.isBuy ? Color.green.opacity(0.3) : Color.red.opacity(0.3), lineWidth: 1)
        )
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                isExpanded.toggle()
            }
        } label: {
            HStack(spacing: 12) {
                // Action badge
                Text(trade.action)
                    .font(.caption.weight(.bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(trade.isBuy ? Color.green : Color.red)
                    .cornerRadius(6)
                
                // Ticker and shares
                VStack(alignment: .leading, spacing: 2) {
                    Text(trade.ticker)
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("\(trade.shares) shares @ $\(trade.estimatedPrice, specifier: "%.2f")")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                
                Spacer()
                
                // Value
                VStack(alignment: .trailing, spacing: 2) {
                    Text(trade.formattedValue)
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text(timeRemaining)
                        .font(.caption)
                        .foregroundColor(trade.isExpired ? .red : .Text.secondary)
                }
                
                // Expand indicator
                Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                    .foregroundColor(.Text.secondary)
                    .font(.caption)
            }
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // MARK: - Rationale
    
    private var rationaleView: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("AI Rationale", systemImage: "brain.head.profile")
                .font(.caption.weight(.medium))
                .foregroundColor(.Brand.primary)
            
            Text(trade.rationale)
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .lineLimit(5)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    
    // MARK: - Action Buttons
    
    private var actionButtons: some View {
        HStack(spacing: 12) {
            // Reject button
            Button {
                isRejecting = true
                onReject()
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    isRejecting = false
                }
            } label: {
                HStack {
                    if isRejecting {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "xmark")
                    }
                    Text("Reject")
                }
                .font(.subheadline.weight(.medium))
                .foregroundColor(.red)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.red, lineWidth: 1)
                )
            }
            .disabled(isApproving || isRejecting || trade.isExpired)
            
            // Approve button
            Button {
                isApproving = true
                onApprove()
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    isApproving = false
                }
            } label: {
                HStack {
                    if isApproving {
                        ProgressView()
                            .scaleEffect(0.8)
                            .tint(.white)
                    } else {
                        Image(systemName: "checkmark")
                    }
                    Text("Approve")
                }
                .font(.subheadline.weight(.medium))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(trade.isExpired ? Color.gray : Color.green)
                )
            }
            .disabled(isApproving || isRejecting || trade.isExpired)
        }
    }
    
    // MARK: - Helpers
    
    private var timeRemaining: String {
        if trade.isExpired {
            return "Expired"
        }
        
        let formatter = ISO8601DateFormatter()
        guard let expiresDate = formatter.date(from: trade.expiresAt) else {
            return "Unknown"
        }
        
        let remaining = expiresDate.timeIntervalSince(Date())
        if remaining < 3600 {
            return "\(Int(remaining / 60))m left"
        } else {
            return "\(Int(remaining / 3600))h left"
        }
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        PendingApprovalCard(
            trade: PendingTrade(
                id: "1",
                ticker: "AAPL",
                action: "BUY",
                shares: 50,
                estimatedPrice: 178.50,
                estimatedValue: 8925,
                rationale: "Strong technical momentum with RSI crossing above 50. Recent earnings beat expectations by 15%. Institutional buying detected in the last 5 trading days.",
                createdAt: "2024-01-15T10:00:00Z",
                expiresAt: "2024-01-16T10:00:00Z",
                isExpired: false
            ),
            onApprove: {},
            onReject: {}
        )
        
        PendingApprovalCard(
            trade: PendingTrade(
                id: "2",
                ticker: "TSLA",
                action: "SELL",
                shares: 25,
                estimatedPrice: 245.00,
                estimatedValue: 6125,
                rationale: "Breaking below key support level. Volume indicates distribution. Recommend taking profits.",
                createdAt: "2024-01-15T09:00:00Z",
                expiresAt: "2024-01-15T09:30:00Z",
                isExpired: true
            ),
            onApprove: {},
            onReject: {}
        )
    }
    .padding()
    .background(Color.Background.primary)
}
