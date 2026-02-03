import SwiftUI

/// Reusable error state view with retry button.
/// Shows when API calls fail instead of blank screens.
struct ErrorStateView: View {
    let title: String
    let message: String
    var icon: String = "exclamationmark.triangle.fill"
    var retryAction: (() -> Void)?

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundColor(.Signal.hold)

            Text(title)
                .font(.headline)
                .foregroundColor(.Text.primary)
                .multilineTextAlignment(.center)

            Text(message)
                .font(.subheadline)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            if let retryAction {
                Button(action: retryAction) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.clockwise")
                        Text("Retry")
                    }
                    .font(.headline)
                    .foregroundColor(.Background.primary)
                    .padding(.horizontal, 32)
                    .padding(.vertical, 14)
                    .background(Color.Accent.gold)
                    .cornerRadius(12)
                }
                .padding(.top, 8)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.Background.primary)
    }
}

// MARK: - Preview

#Preview("Error with Retry") {
    ErrorStateView(
        title: "Something went wrong",
        message: "We couldn't load the data. Check your connection and try again.",
        retryAction: { print("Retry tapped") }
    )
}

#Preview("Error without Retry") {
    ErrorStateView(
        title: "No Data Available",
        message: "Score data hasn't been generated yet.",
        icon: "chart.bar.xaxis"
    )
}
