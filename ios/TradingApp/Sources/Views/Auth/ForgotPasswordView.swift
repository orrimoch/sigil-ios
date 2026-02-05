import SwiftUI

/// F11.3: Password Reset Flow
/// Step 1: Enter email → Step 2: Enter code + new password → Success
struct ForgotPasswordView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var email: String = ""
    @State private var code: String = ""
    @State private var newPassword: String = ""
    @State private var confirmPassword: String = ""
    @State private var step: ResetStep = .email
    @State private var localError: String?

    enum ResetStep {
        case email, code, success
    }

    var body: some View {
        ZStack {
            Color.Background.primary.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 28) {
                    Spacer().frame(height: 20)

                    // Icon
                    Image(systemName: step == .success ? "checkmark.shield.fill" : "key.fill")
                        .font(.iconSize(48)).limitedScaling()
                        .foregroundColor(step == .success ? .Signal.buy : .Accent.gold)
                        .padding(.bottom, 8)

                    // Title
                    Text(stepTitle)
                        .font(.title2.bold())
                        .foregroundColor(.Text.primary)

                    Text(stepSubtitle)
                        .font(.subheadline)
                        .foregroundColor(.Text.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 24)

                    // Error
                    if let error = localError ?? authVM.errorMessage {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                            Text(error)
                        }
                        .font(.subheadline)
                        .foregroundColor(.Signal.sell)
                        .padding(.horizontal, 24)
                        .transition(.opacity)
                    }

                    // Step content
                    switch step {
                    case .email:
                        emailStep
                    case .code:
                        codeStep
                    case .success:
                        successStep
                    }

                    Spacer()
                }
            }
        }
        .navigationTitle("Reset Password")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .onChange(of: authVM.resetCode) { _, newCode in
            if newCode != nil {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { step = .code }
            }
        }
        .onChange(of: authVM.resetSuccess) { _, success in
            if success {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { step = .success }
            }
        }
        .onDisappear {
            // Clean up
            authVM.errorMessage = nil
            authVM.resetCode = nil
            authVM.resetSuccess = false
        }
    }

    // MARK: - Step Titles

    private var stepTitle: String {
        switch step {
        case .email: return "Forgot Password?"
        case .code: return "Check Your Email"
        case .success: return "Password Reset!"
        }
    }

    private var stepSubtitle: String {
        switch step {
        case .email: return "Enter the email associated with your account and we'll send a reset code."
        case .code: return "Enter the 6-digit code and your new password."
        case .success: return "Your password has been reset successfully. You're now signed in."
        }
    }

    // MARK: - Step 1: Email

    private var emailStep: some View {
        VStack(spacing: 20) {
            SigilTextField(placeholder: "Email", text: $email, keyboardType: .emailAddress)
                .textContentType(.emailAddress)
                .textInputAutocapitalization(.never)
                .padding(.horizontal, 24)

            Button {
                localError = nil
                authVM.requestPasswordReset(email: email)
            } label: {
                Group {
                    if authVM.isLoading {
                        ProgressView().tint(.Background.primary)
                    } else {
                        Text("Send Reset Code")
                            .font(.headline)
                    }
                }
                .foregroundColor(.Background.primary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(email.isEmpty ? Color.Background.tertiary : Color.Accent.gold)
                .cornerRadius(12)
            }
            .disabled(email.isEmpty || authVM.isLoading)
            .padding(.horizontal, 24)

            Button {
                dismiss()
            } label: {
                Text("Back to Sign In")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
            }
        }
    }

    // MARK: - Step 2: Code + New Password

    private var codeStep: some View {
        VStack(spacing: 20) {
            // DEV: Show the code for testing
            #if DEBUG
            if let devCode = authVM.resetCode {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
                    Text("Dev code: **\(devCode)**")
                }
                .font(.caption)
                .foregroundColor(.Signal.hold)
                .padding()
                .background(Color.Signal.hold.opacity(0.15))
                .cornerRadius(8)
                .padding(.horizontal, 24)
            }
            #endif

            // Code input
            VStack(alignment: .leading, spacing: 8) {
                Text("Reset Code")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .padding(.horizontal, 24)

                CodeInputField(code: $code)
                    .padding(.horizontal, 24)
            }

            // New password
            SigilSecureField(placeholder: "New Password (min 8 chars)", text: $newPassword)
                .textContentType(.newPassword)
                .padding(.horizontal, 24)

            SigilSecureField(placeholder: "Confirm New Password", text: $confirmPassword)
                .textContentType(.newPassword)
                .padding(.horizontal, 24)

            Button {
                localError = nil
                guard newPassword == confirmPassword else {
                    localError = "Passwords don't match."
                    return
                }
                authVM.confirmPasswordReset(email: email, code: code, newPassword: newPassword)
            } label: {
                Group {
                    if authVM.isLoading {
                        ProgressView().tint(.Background.primary)
                    } else {
                        Text("Reset Password")
                            .font(.headline)
                    }
                }
                .foregroundColor(.Background.primary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(canSubmit ? Color.Accent.gold : Color.Background.tertiary)
                .cornerRadius(12)
            }
            .disabled(!canSubmit || authVM.isLoading)
            .padding(.horizontal, 24)

            // Resend
            Button {
                authVM.requestPasswordReset(email: email)
            } label: {
                Text("Resend Code")
                    .font(.subheadline)
                    .foregroundColor(.Accent.gold)
            }
        }
    }

    private var canSubmit: Bool {
        code.count == 6 && newPassword.count >= 8 && confirmPassword.count >= 8
    }

    // MARK: - Step 3: Success

    private var successStep: some View {
        VStack(spacing: 20) {
            Button {
                dismiss()
            } label: {
                Text("Continue to App")
                    .font(.headline)
                    .foregroundColor(.Background.primary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.Accent.gold)
                    .cornerRadius(12)
            }
            .padding(.horizontal, 24)
        }
    }
}

// MARK: - 6-Digit Code Input

struct CodeInputField: View {
    @Binding var code: String
    private let codeLength = 6

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<codeLength, id: \.self) { index in
                let char = index < code.count ? String(code[code.index(code.startIndex, offsetBy: index)]) : ""

                Text(char)
                    .font(.title2.bold().monospacedDigit())
                    .foregroundColor(.Text.primary)
                    .frame(width: 44, height: 56)
                    .background(Color.Background.secondary)
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(
                                index == code.count ? Color.Accent.gold : Color.Background.tertiary,
                                lineWidth: index == code.count ? 2 : 1
                            )
                    )
                    .accessibilityLabel("Digit \(index + 1) of \(codeLength)\(char.isEmpty ? ", empty" : ", \(char)")")
            }
        }
        .overlay(
            // Hidden TextField to capture keyboard input
            TextField("", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .foregroundColor(.clear)
                .tint(.clear)
                .onChange(of: code) { _, newValue in
                    code = String(newValue.filter { $0.isNumber }.prefix(codeLength))
                }
        )
    }
}

#Preview {
    NavigationStack {
        ForgotPasswordView()
            .environmentObject(AuthViewModel())
    }
}
