import Foundation

// MARK: - Auth Models

struct AuthUser: Codable {
    let id: String
    let email: String
    let fullName: String
    let createdAt: String?
    let updatedAt: String?
    let isActive: Bool
    let ibkrAccountId: String?
    let settingsJson: String?
}

struct AuthTokens: Codable {
    let accessToken: String
    let refreshToken: String
}

struct AuthResponse: Codable {
    let success: Bool
    let user: AuthUser
    let tokens: AuthTokens
}

struct TokenRefreshResponse: Codable {
    let success: Bool
    let accessToken: String
}

struct ProfileResponse: Codable {
    let success: Bool
    let user: AuthUser
}

struct AuthErrorResponse: Codable {
    let detail: String?
}

// MARK: - AuthService

/// Manages user authentication state, token storage, and API calls.
final class AuthService: ObservableObject {
    static let shared = AuthService()

    // Keychain keys
    private enum Keys {
        static let accessToken  = "sigil_access_token"
        static let refreshToken = "sigil_refresh_token"
        static let currentUser  = "sigil_current_user"
    }

    private let keychain = KeychainHelper.shared
    private let baseURL  = "http://127.0.0.1:8000/api/v1/auth"

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    // MARK: - Published state

    @Published var isLoggedIn: Bool = false
    @Published var currentUser: AuthUser?
    @Published var accessToken: String?

    // MARK: - Init

    private init() {
        restoreSession()
    }

    // MARK: - Session persistence

    /// Try to restore tokens + user from Keychain on launch.
    private func restoreSession() {
        if let token = keychain.loadString(key: Keys.accessToken) {
            accessToken = token
            isLoggedIn  = true
        }
        if let userData = keychain.load(key: Keys.currentUser),
           let user = try? decoder.decode(AuthUser.self, from: userData) {
            currentUser = user
        }
    }

    private func persistSession(user: AuthUser, tokens: AuthTokens) {
        keychain.save(key: Keys.accessToken, string: tokens.accessToken)
        keychain.save(key: Keys.refreshToken, string: tokens.refreshToken)
        if let data = try? JSONEncoder().encode(user) {
            keychain.save(key: Keys.currentUser, data: data)
        }

        accessToken  = tokens.accessToken
        currentUser  = user
        isLoggedIn   = true
    }

    private func clearSession() {
        keychain.delete(key: Keys.accessToken)
        keychain.delete(key: Keys.refreshToken)
        keychain.delete(key: Keys.currentUser)

        accessToken = nil
        currentUser = nil
        isLoggedIn  = false
    }

    // MARK: - Public API

    func register(email: String, password: String, fullName: String) async throws {
        let body: [String: Any] = [
            "email": email,
            "password": password,
            "full_name": fullName,
        ]

        let response: AuthResponse = try await post(path: "/register", body: body)
        await MainActor.run { persistSession(user: response.user, tokens: response.tokens) }
    }

    func login(email: String, password: String) async throws {
        let body: [String: Any] = [
            "email": email,
            "password": password,
        ]

        let response: AuthResponse = try await post(path: "/login", body: body)
        await MainActor.run { persistSession(user: response.user, tokens: response.tokens) }
    }

    func logout() {
        clearSession()
    }

    // MARK: - Password Reset

    func requestPasswordReset(email: String) async throws -> String? {
        let body: [String: Any] = ["email": email]
        let response: [String: Any] = try await postRaw(path: "/password-reset/request", body: body)
        // DEV: backend returns code directly for testing
        return response["code"] as? String
    }

    func confirmPasswordReset(email: String, code: String, newPassword: String) async throws {
        let body: [String: Any] = [
            "email": email,
            "code": code,
            "new_password": newPassword,
        ]
        let response: AuthResponse = try await post(path: "/password-reset/confirm", body: body)
        await MainActor.run { persistSession(user: response.user, tokens: response.tokens) }
    }

    /// Attempt to refresh the access token using the stored refresh token.
    /// Returns the new access token, or throws on failure.
    @discardableResult
    func refreshToken() async throws -> String {
        guard let refresh = keychain.loadString(key: Keys.refreshToken) else {
            throw AuthError.noRefreshToken
        }

        let body: [String: Any] = ["refresh_token": refresh]
        let response: TokenRefreshResponse = try await post(path: "/refresh", body: body)

        await MainActor.run {
            accessToken = response.accessToken
            keychain.save(key: Keys.accessToken, string: response.accessToken)
        }

        return response.accessToken
    }

    /// Fetch fresh profile from backend and update local state.
    func fetchProfile() async throws {
        guard let token = accessToken else { throw AuthError.notAuthenticated }

        var request = URLRequest(url: URL(string: "\(baseURL)/me")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, 200...299 ~= http.statusCode else {
            throw AuthError.serverError
        }

        let profile = try decoder.decode(ProfileResponse.self, from: data)
        await MainActor.run {
            currentUser = profile.user
            if let userData = try? JSONEncoder().encode(profile.user) {
                keychain.save(key: Keys.currentUser, data: userData)
            }
        }
    }

    // MARK: - Networking helpers

    private func postRaw(path: String, body: [String: Any]) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)\(path)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw AuthError.serverError
        }

        guard 200...299 ~= http.statusCode else {
            if let errResp = try? decoder.decode(AuthErrorResponse.self, from: data),
               let detail = errResp.detail {
                throw AuthError.api(detail)
            }
            throw AuthError.httpError(http.statusCode)
        }

        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    private func post<T: Decodable>(path: String, body: [String: Any]) async throws -> T {
        let url = URL(string: "\(baseURL)\(path)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw AuthError.serverError
        }

        guard 200...299 ~= http.statusCode else {
            // Try to extract backend error detail
            if let errResp = try? decoder.decode(AuthErrorResponse.self, from: data),
               let detail = errResp.detail {
                throw AuthError.api(detail)
            }
            throw AuthError.httpError(http.statusCode)
        }

        return try decoder.decode(T.self, from: data)
    }
}

// MARK: - Errors

enum AuthError: Error, LocalizedError {
    case notAuthenticated
    case noRefreshToken
    case serverError
    case httpError(Int)
    case api(String)

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:  return "Not authenticated"
        case .noRefreshToken:    return "No refresh token available"
        case .serverError:       return "Server error"
        case .httpError(let c):  return "HTTP error \(c)"
        case .api(let msg):      return msg
        }
    }
}
