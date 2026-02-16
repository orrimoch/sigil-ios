import SwiftUI
import LocalAuthentication

/// Sigil Login screen — dark theme with gold accents.
struct LoginView: View {
    @EnvironmentObject var authVM: AuthViewModel

    @State private var email = ""
    @State private var password = ""
    @State private var showRegister = false
    @State private var showForgotPassword = false
    @State private var canUseBiometrics = false
    @FocusState private var focusedField: LoginField?

    private enum LoginField {
        case email, password
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.Background.primary.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 32) {

                        Spacer().frame(height: 60)

                        // Logo
                        Image("SigilLogo")
                            .resizable()
                            .scaledToFit()
                            .frame(maxWidth: 220)
                            .accessibilityLabel("Sigil - AI Market Intelligence")

                        // Title
                        Text("Welcome Back")
                            .font(.displayMedium)
                            .foregroundColor(.Text.primary)

                        // Error banner
                        if let error = authVM.errorMessage {
                            Text(error)
                                .font(.subheadline)
                                .foregroundColor(.Utility.error)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }

                        // Fields
                        VStack(spacing: 16) {
                            SigilTextField(placeholder: "Email", text: $email, keyboardType: .emailAddress, isFocused: focusedField == .email)
                                .textContentType(.emailAddress)
                                .textInputAutocapitalization(.never)
                                .focused($focusedField, equals: .email)

                            SigilSecureField(placeholder: "Password", text: $password, isFocused: focusedField == .password)
                                .textContentType(.password)
                                .focused($focusedField, equals: .password)
                        }
                        .padding(.horizontal, 24)

                        // Sign In button
                        Button {
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            authVM.login(email: email, password: password)
                        } label: {
                            Group {
                                if authVM.isLoading {
                                    ProgressView()
                                        .tint(.Background.primary)
                                } else {
                                    Text("Sign In")
                                        .font(.headline)
                                }
                            }
                            .foregroundColor(.Background.primary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                            .background(Color.Accent.gold)
                            .cornerRadius(12)
                        }
                        .disabled(email.isEmpty || password.isEmpty || authVM.isLoading)
                        .opacity(email.isEmpty || password.isEmpty ? 0.5 : 1.0)
                        .padding(.horizontal, 24)

                        // Forgot Password (LOW FIX AUTH-001: Larger touch target)
                        Button {
                            showForgotPassword = true
                        } label: {
                            Text("Forgot Password?")
                                .font(.subheadline)
                                .foregroundColor(.Accent.gold)
                                .padding(.vertical, 8)
                                .padding(.horizontal, 16)
                        }

                        // Face ID shortcut
                        if canUseBiometrics {
                            Button {
                                authenticateWithBiometrics()
                            } label: {
                                HStack(spacing: 10) {
                                    Image(systemName: "faceid")
                                        .font(.title2)
                                    Text("Sign in with Face ID")
                                        .font(.subheadline.weight(.medium))
                                }
                                .foregroundColor(.Accent.gold)
                                .padding(.vertical, 12)
                                .padding(.horizontal, 24)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 10)
                                        .stroke(Color.Accent.gold.opacity(0.5), lineWidth: 1)
                                )
                            }
                        }

                        // Register link
                        Button {
                            showRegister = true
                        } label: {
                            Text("Create Account")
                                .font(.subheadline)
                                .foregroundColor(.Accent.gold)
                        }

                        Spacer()
                    }
                }
                .scrollDismissesKeyboard(.interactively)
            }
            .navigationDestination(isPresented: $showRegister) {
                RegisterView()
                    .environmentObject(authVM)
            }
            .navigationDestination(isPresented: $showForgotPassword) {
                ForgotPasswordView()
                    .environmentObject(authVM)
            }
            .onAppear {
                checkBiometrics()
            }
        }
    }

    // MARK: - Biometrics

    private func checkBiometrics() {
        let context = LAContext()
        var error: NSError?
        canUseBiometrics = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }

    private func authenticateWithBiometrics() {
        let context = LAContext()
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Sign in to Sigil") { success, _ in
            if success {
                // Biometric OK — if we still have a stored session it's already logged in
                // (AuthService restores from Keychain on init).
                // This is a UX shortcut for re-confirming identity.
                DispatchQueue.main.async {
                    if AuthService.shared.isLoggedIn {
                        authVM.isLoggedIn = true
                    }
                }
            }
        }
    }
}

// MARK: - Reusable styled fields

struct SigilTextField: View {
    let placeholder: String
    @Binding var text: String
    var keyboardType: UIKeyboardType = .default
    var isFocused: Bool = false

    var body: some View {
        TextField("", text: $text, prompt: Text(placeholder).foregroundColor(.Text.tertiary))
            .keyboardType(keyboardType)
            .foregroundColor(.Text.primary)
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isFocused ? Color.Accent.gold : Color.Utility.border, lineWidth: isFocused ? 2 : 1)
            )
    }
}

struct SigilSecureField: View {
    let placeholder: String
    @Binding var text: String
    var isFocused: Bool = false
    @State private var showPassword: Bool = false

    var body: some View {
        HStack(spacing: 0) {
            Group {
                if showPassword {
                    TextField("", text: $text, prompt: Text(placeholder).foregroundColor(.Text.tertiary))
                        .textInputAutocapitalization(.never)
                } else {
                    SecureField("", text: $text, prompt: Text(placeholder).foregroundColor(.Text.tertiary))
                }
            }
            .foregroundColor(.Text.primary)

            Button {
                showPassword.toggle()
            } label: {
                Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                    .foregroundColor(.Text.tertiary)
                    .font(.subheadline)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isFocused ? Color.Accent.gold : Color.Utility.border, lineWidth: isFocused ? 2 : 1)
        )
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthViewModel())
}
