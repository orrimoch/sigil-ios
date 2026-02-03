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

    var body: some View {
        NavigationStack {
            ZStack {
                Color.Background.primary.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 32) {

                        Spacer().frame(height: 40)

                        // Logo
                        Image("SigilLogo")
                            .resizable()
                            .scaledToFit()
                            .frame(maxWidth: 220)

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
                            SigilTextField(placeholder: "Email", text: $email, keyboardType: .emailAddress)
                                .textContentType(.emailAddress)
                                .autocapitalization(.none)

                            SigilSecureField(placeholder: "Password", text: $password)
                                .textContentType(.password)
                        }
                        .padding(.horizontal, 24)

                        // Sign In button
                        Button {
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
                        .disabled(authVM.isLoading)
                        .padding(.horizontal, 24)

                        // Forgot Password
                        Button {
                            showForgotPassword = true
                        } label: {
                            Text("Forgot Password?")
                                .font(.subheadline)
                                .foregroundColor(.Text.secondary)
                        }

                        // Face ID shortcut
                        if canUseBiometrics {
                            Button {
                                authenticateWithBiometrics()
                            } label: {
                                HStack(spacing: 8) {
                                    Image(systemName: "faceid")
                                    Text("Sign in with Face ID")
                                }
                                .font(.subheadline)
                                .foregroundColor(.Accent.gold)
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

    var body: some View {
        TextField("", text: $text, prompt: Text(placeholder).foregroundColor(.Text.tertiary))
            .keyboardType(keyboardType)
            .foregroundColor(.Text.primary)
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.Utility.border, lineWidth: 1)
            )
    }
}

struct SigilSecureField: View {
    let placeholder: String
    @Binding var text: String

    var body: some View {
        SecureField("", text: $text, prompt: Text(placeholder).foregroundColor(.Text.tertiary))
            .foregroundColor(.Text.primary)
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.Utility.border, lineWidth: 1)
            )
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthViewModel())
}
