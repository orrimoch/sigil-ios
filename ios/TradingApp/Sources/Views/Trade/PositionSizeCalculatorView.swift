import SwiftUI

/// REC-147: Position Size Calculator
/// Calculate optimal shares based on risk parameters
struct PositionSizeCalculatorView: View {
    @Environment(\.dismiss) var dismiss
    
    let ticker: String
    let currentPrice: Double
    
    @State private var riskPercent: Double = 1.0
    @State private var stopPercent: Double = 5.0
    @State private var accountSize: Double = 100000
    
    @State private var result: PositionSizeResult?
    @State private var isCalculating = false
    @State private var error: String?
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Ticker info
                    tickerHeader
                    
                    // Input parameters
                    parameterInputs
                    
                    // Calculate button
                    calculateButton
                    
                    // Results
                    if let result = result {
                        resultsCard(result)
                    }
                    
                    // Error
                    if let error = error {
                        errorView(error)
                    }
                    
                    Spacer()
                }
                .padding()
            }
            .background(Color.Background.primary)
            .navigationTitle("Position Calculator")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.Brand.primary)
                }
            }
        }
        .task {
            await calculate()
        }
    }
    
    // MARK: - Components
    
    private var tickerHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(ticker)
                    .font(.title2.bold())
                    .foregroundColor(.Text.primary)
                Text("Current Price")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
            Spacer()
            Text(currentPrice.asCurrency)
                .font(.title2.bold().monospacedDigit())
                .foregroundColor(.Brand.primary)
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private var parameterInputs: some View {
        VStack(spacing: 16) {
            // Account Size
            VStack(alignment: .leading, spacing: 8) {
                Text("Account Size")
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.secondary)
                
                HStack {
                    Text("$")
                        .foregroundColor(.Text.tertiary)
                    TextField("100000", value: $accountSize, format: .number)
                        .keyboardType(.numberPad)
                        .textFieldStyle(.plain)
                        .foregroundColor(.Text.primary)
                }
                .padding()
                .background(Color.Background.tertiary)
                .cornerRadius(8)
            }
            
            // Risk Percent
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Risk Per Trade")
                        .font(.subheadline.bold())
                        .foregroundColor(.Text.secondary)
                    Spacer()
                    Text("\(riskPercent, specifier: "%.1f")%")
                        .font(.subheadline.monospacedDigit())
                        .foregroundColor(.Brand.primary)
                }
                
                Slider(value: $riskPercent, in: 0.5...5.0, step: 0.5)
                    .tint(.Brand.primary)
                
                Text("Recommended: 1-2% for conservative, up to 5% for aggressive")
                    .font(.caption2)
                    .foregroundColor(.Text.tertiary)
            }
            
            // Stop Distance
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Stop Distance")
                        .font(.subheadline.bold())
                        .foregroundColor(.Text.secondary)
                    Spacer()
                    Text("\(stopPercent, specifier: "%.1f")%")
                        .font(.subheadline.monospacedDigit())
                        .foregroundColor(.Signal.sell)
                }
                
                Slider(value: $stopPercent, in: 1.0...20.0, step: 0.5)
                    .tint(.Signal.sell)
                
                HStack {
                    Text("Stop Price:")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                    Text((currentPrice * (1 - stopPercent / 100)).asCurrency)
                        .font(.caption.monospacedDigit())
                        .foregroundColor(.Signal.sell)
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private var calculateButton: some View {
        Button {
            Task { await calculate() }
        } label: {
            HStack {
                if isCalculating {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "function")
                    Text("Calculate Position Size")
                }
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.Brand.primary)
            .foregroundColor(.white)
            .cornerRadius(12)
        }
        .disabled(isCalculating)
    }
    
    private func resultsCard(_ result: PositionSizeResult) -> some View {
        VStack(spacing: 16) {
            // Main result
            VStack(spacing: 4) {
                Text("Recommended Shares")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                Text("\(result.shares)")
                    .font(.price)
                    .limitedScaling()
                    .foregroundColor(.Brand.primary)
            }
            
            Divider()
                .background(Color.Utility.divider)
            
            // Metrics grid
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                resultMetric("Position Value", value: result.positionValue.asCurrency)
                resultMetric("Risk Amount", value: result.riskAmount.asCurrency, color: .Signal.sell)
                resultMetric("Risk %", value: String(format: "%.2f%%", result.riskPercent))
                resultMetric("Stop Distance", value: String(format: "%.2f%%", result.stopPercent * 100))
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
    }
    
    private func resultMetric(_ label: String, value: String, color: Color = .Text.primary) -> some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.Text.tertiary)
            Text(value)
                .font(.subheadline.bold().monospacedDigit())
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
    }
    
    private func errorView(_ message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.Signal.sell)
            Text(message)
                .font(.caption)
                .foregroundColor(.Signal.sell)
        }
        .padding()
        .background(Color.Signal.sell.opacity(0.15))
        .cornerRadius(8)
    }
    
    // MARK: - API Call
    
    private func calculate() async {
        isCalculating = true
        error = nil
        
        do {
            let response = try await APIService.shared.calculatePositionSize(
                ticker: ticker,
                accountSize: accountSize,
                riskPercent: riskPercent,
                stopPercent: stopPercent
            )
            result = response
        } catch {
            self.error = error.localizedDescription
        }
        
        isCalculating = false
    }
}

// MARK: - Data Model

struct PositionSizeResult: Codable {
    let shares: Int
    let positionValue: Double
    let riskAmount: Double
    let riskPercent: Double
    let stopDistance: Double
    let stopPercent: Double
    let ticker: String?
    let entryPrice: Double?
    let stopPrice: Double?
}

// MARK: - API Extension

extension APIService {
    func calculatePositionSize(
        ticker: String,
        accountSize: Double,
        riskPercent: Double,
        stopPercent: Double
    ) async throws -> PositionSizeResult {
        // Use URLComponents for safe query parameter encoding
        guard var components = URLComponents(string: "\(baseURL)/trading/position-size") else {
            throw APIError.invalidURL
        }
        components.queryItems = [
            URLQueryItem(name: "ticker", value: ticker),
            URLQueryItem(name: "account_size", value: String(accountSize)),
            URLQueryItem(name: "risk_percent", value: String(riskPercent)),
            URLQueryItem(name: "stop_percent", value: String(stopPercent))
        ]
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        struct Response: Codable {
            let success: Bool
            let data: PositionSizeResult
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(Response.self, from: data)
        return result.data
    }
}

// MARK: - Preview

#Preview {
    PositionSizeCalculatorView(ticker: "AAPL", currentPrice: 185.50)
}
