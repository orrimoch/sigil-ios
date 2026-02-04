import SwiftUI

/// Sigil Registration screen — dark theme with gold accents.
struct RegisterView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var fullName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var localError: String?
    @FocusState private var focusedField: RegisterField?

    private enum RegisterField {
        case fullName, email, password, confirmPassword
    }

    var body: some View {
        ZStack {
            Color.Background.primary.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 28) {

                    Spacer().frame(height: 24)

                    // Logo
                    Image("SigilLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: 120)

                    Text("Create Account")
                        .font(.displayMedium)
                        .foregroundColor(.Text.primary)

                    // Error banner
                    if let error = localError ?? authVM.errorMessage {
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.Utility.error)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // Fields
                    VStack(spacing: 16) {
                        SigilTextField(placeholder: "Full Name", text: $fullName, isFocused: focusedField == .fullName)
                            .textContentType(.name)
                            .focused($focusedField, equals: .fullName)

                        SigilTextField(placeholder: "Email", text: $email, keyboardType: .emailAddress, isFocused: focusedField == .email)
                            .textContentType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .focused($focusedField, equals: .email)

                        SigilSecureField(placeholder: "Password (min 8 chars)", text: $password, isFocused: focusedField == .password)
                            .textContentType(.newPassword)
                            .focused($focusedField, equals: .password)

                        // Password strength indicator
                        if !password.isEmpty {
                            HStack(spacing: 4) {
                                ForEach(0..<4, id: \.self) { i in
                                    RoundedRectangle(cornerRadius: 2)
                                        .fill(i < passwordStrength ? strengthColor : Color.Background.tertiary)
                                        .frame(height: 4)
                                }
                                Text(strengthLabel)
                                    .font(.caption2)
                                    .foregroundColor(strengthColor)
                            }
                        }

                        SigilSecureField(placeholder: "Confirm Password", text: $confirmPassword, isFocused: focusedField == .confirmPassword)
                            .textContentType(.newPassword)
                            .focused($focusedField, equals: .confirmPassword)
                    }
                    .padding(.horizontal, 24)

                    // Create Account button
                    Button {
                        submitRegistration()
                    } label: {
                        Group {
                            if authVM.isLoading {
                                ProgressView()
                                    .tint(.Background.primary)
                            } else {
                                Text("Create Account")
                                    .font(.headline)
                            }
                        }
                        .foregroundColor(.Background.primary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color.Accent.gold)
                        .cornerRadius(12)
                    }
                    .disabled(authVM.isLoading)
                    .padding(.horizontal, 24)

                    // Sign in link
                    Button {
                        dismiss()
                    } label: {
                        Text("Already have an account? Sign In")
                            .font(.subheadline)
                            .foregroundColor(.Accent.gold)
                    }

                    Spacer()
                }
            }
        }
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    dismiss()
                } label: {
                    Label("Back", systemImage: "chevron.left")
                        .foregroundColor(.Accent.gold)
                }
            }
        }
    }

    // MARK: - Password Strength

    private var passwordStrength: Int {
        var strength = 0
        if password.count >= 8 { strength += 1 }
        if password.rangeOfCharacter(from: .uppercaseLetters) != nil { strength += 1 }
        if password.rangeOfCharacter(from: .decimalDigits) != nil { strength += 1 }
        if password.rangeOfCharacter(from: .punctuationCharacters) != nil || password.rangeOfCharacter(from: .symbols) != nil { strength += 1 }
        return strength
    }

    private var strengthColor: Color {
        switch passwordStrength {
        case 0...1: return .Signal.sell
        case 2: return .Signal.hold
        case 3: return .Signal.buy
        default: return .Signal.buy
        }
    }

    private var strengthLabel: String {
        switch passwordStrength {
        case 0...1: return "Weak"
        case 2: return "Fair"
        case 3: return "Good"
        default: return "Strong"
        }
    }

    // MARK: - Validation

    private func submitRegistration() {
        localError = nil

        guard !fullName.trimmingCharacters(in: .whitespaces).isEmpty else {
            localError = "Please enter your name."
            return
        }
        guard !email.trimmingCharacters(in: .whitespaces).isEmpty else {
            localError = "Please enter your email."
            return
        }
        guard password.count >= 8 else {
            localError = "Password must be at least 8 characters."
            return
        }
        guard password == confirmPassword else {
            localError = "Passwords do not match."
            return
        }

        authVM.register(email: email, password: password, fullName: fullName)
    }
}

#Preview {
    NavigationStack {
        RegisterView()
            .environmentObject(AuthViewModel())
    }
}
