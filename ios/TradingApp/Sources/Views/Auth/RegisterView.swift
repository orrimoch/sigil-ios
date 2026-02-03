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
                        .frame(maxWidth: 180)

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
                        SigilTextField(placeholder: "Full Name", text: $fullName)
                            .textContentType(.name)

                        SigilTextField(placeholder: "Email", text: $email, keyboardType: .emailAddress)
                            .textContentType(.emailAddress)
                            .autocapitalization(.none)

                        SigilSecureField(placeholder: "Password (min 8 chars)", text: $password)
                            .textContentType(.newPassword)

                        SigilSecureField(placeholder: "Confirm Password", text: $confirmPassword)
                            .textContentType(.newPassword)
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
                    Image(systemName: "chevron.left")
                        .foregroundColor(.Accent.gold)
                }
            }
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
