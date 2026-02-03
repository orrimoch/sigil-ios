import SwiftUI

/// First-time PIN setup — shown when user hasn't set up a lock yet
struct PinSetupView: View {
    @ObservedObject var lockManager: AppLockManager
    @Environment(\.dismiss) private var dismiss
    
    @State private var step: SetupStep = .create
    @State private var pin: String = ""
    @State private var confirmPin: String = ""
    @State private var errorMessage: String?
    @State private var shakeOffset: CGFloat = 0
    
    private let pinLength = 6
    
    enum SetupStep {
        case create, confirm
        
        var title: String {
            switch self {
            case .create: return "Create a PIN"
            case .confirm: return "Confirm your PIN"
            }
        }
        
        var subtitle: String {
            switch self {
            case .create: return "Choose a 6-digit PIN to secure your app"
            case .confirm: return "Enter the same PIN again"
            }
        }
    }
    
    var currentPin: Binding<String> {
        step == .create ? $pin : $confirmPin
    }
    
    var body: some View {
        ZStack {
            Color(red: 13/255, green: 13/255, blue: 15/255)
                .ignoresSafeArea()
            
            VStack(spacing: 32) {
                Spacer()
                
                // Icon
                Image(systemName: "lock.shield.fill")
                    .font(.system(size: 48))
                    .foregroundColor(.Brand.primary)
                
                VStack(spacing: 8) {
                    Text(step.title)
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)
                    
                    Text(step.subtitle)
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                }
                
                // PIN dots
                HStack(spacing: 16) {
                    ForEach(0..<pinLength, id: \.self) { index in
                        let currentCount = step == .create ? pin.count : confirmPin.count
                        Circle()
                            .fill(index < currentCount ? (errorMessage != nil ? Color.Signal.sell : Color.Brand.primary) : Color.Background.tertiary)
                            .frame(width: 16, height: 16)
                            .overlay(
                                Circle()
                                    .stroke((errorMessage != nil ? Color.Signal.sell : Color.Brand.primary).opacity(0.3), lineWidth: 1)
                            )
                            .scaleEffect(index < currentCount ? 1.15 : 1.0)
                            .animation(.spring(response: 0.2, dampingFraction: 0.6), value: currentCount)
                    }
                }
                .offset(x: shakeOffset)
                
                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Signal.sell)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
                
                // Number pad
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 16) {
                    ForEach(1...9, id: \.self) { num in
                        numberButton(String(num))
                    }
                    
                    Color.clear.frame(width: 64, height: 64)
                    
                    numberButton("0")
                    
                    // Delete
                    Button {
                        if step == .create && !pin.isEmpty {
                            pin.removeLast()
                        } else if step == .confirm && !confirmPin.isEmpty {
                            confirmPin.removeLast()
                        }
                    } label: {
                        Image(systemName: "delete.backward")
                            .font(.title2)
                            .foregroundColor(.Text.secondary)
                            .frame(width: 64, height: 64)
                    }
                }
                .padding(.horizontal, 40)
                
                // Skip button
                Button {
                    dismiss()
                } label: {
                    Text("Skip for now")
                        .font(.subheadline)
                        .foregroundColor(.Text.tertiary)
                }
                .padding(.top, 8)
                
                Spacer()
            }
            .padding()
        }
    }
    
    private func numberButton(_ digit: String) -> some View {
        Button {
            addDigit(digit)
        } label: {
            Text(digit)
                .font(.title.bold())
                .foregroundColor(.Text.primary)
                .frame(width: 64, height: 64)
                .background(Color.Background.tertiary)
                .clipShape(Circle())
        }
    }
    
    private func addDigit(_ digit: String) {
        errorMessage = nil
        
        if step == .create {
            if pin.count < pinLength {
                pin += digit
            }
            if pin.count == pinLength {
                // Move to confirm step
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    withAnimation {
                        step = .confirm
                    }
                }
            }
        } else {
            if confirmPin.count < pinLength {
                confirmPin += digit
            }
            if confirmPin.count == pinLength {
                // Verify match
                if confirmPin == pin {
                    lockManager.setPin(pin)
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.success)
                    dismiss()
                } else {
                    errorMessage = "PINs don't match. Try again."
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.error)
                    
                    // Shake animation
                    withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) {
                        shakeOffset = 12
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) {
                        withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) {
                            shakeOffset = -10
                        }
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.16) {
                        withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) {
                            shakeOffset = 8
                        }
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.24) {
                        withAnimation(.spring(response: 0.08, dampingFraction: 0.3)) {
                            shakeOffset = -4
                        }
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.32) {
                        withAnimation(.spring(response: 0.1, dampingFraction: 0.5)) {
                            shakeOffset = 0
                        }
                    }
                    
                    // Clear and go back to create step after shake
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                        withAnimation {
                            confirmPin = ""
                            pin = ""
                            step = .create
                            errorMessage = nil
                        }
                    }
                }
            }
        }
    }
}

#Preview {
    PinSetupView(lockManager: AppLockManager())
}
