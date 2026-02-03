import XCTest
@testable import Sigil

/// Tests for REC-88: Auth gate — wire login into app flow
final class AuthGateTests: XCTestCase {
    
    // MARK: - AuthService Tests
    
    func testAuthServiceIsSingleton() {
        let a = AuthService.shared
        let b = AuthService.shared
        XCTAssertTrue(a === b, "AuthService.shared should be a singleton")
    }
    
    func testAuthServiceInitialState() {
        let service = AuthService.shared
        // Initial state depends on Keychain; but properties should be accessible
        XCTAssertNotNil(service)
    }
    
    func testLogoutClearsSession() {
        let service = AuthService.shared
        service.logout()
        XCTAssertFalse(service.isLoggedIn, "After logout, isLoggedIn should be false")
        XCTAssertNil(service.accessToken, "After logout, accessToken should be nil")
        XCTAssertNil(service.currentUser, "After logout, currentUser should be nil")
    }
    
    // MARK: - AuthViewModel Tests
    
    @MainActor
    func testAuthViewModelInitialState() {
        // First ensure logged out state for clean test
        AuthService.shared.logout()
        
        let vm = AuthViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.errorMessage)
    }
    
    @MainActor
    func testAuthViewModelLoginValidation() {
        let vm = AuthViewModel()
        
        // Empty email/password should show error
        vm.login(email: "", password: "")
        XCTAssertNotNil(vm.errorMessage, "Empty credentials should produce an error message")
        XCTAssertEqual(vm.errorMessage, "Please enter your email and password.")
    }
    
    @MainActor
    func testAuthViewModelRegisterValidation() {
        let vm = AuthViewModel()
        
        // Empty fields
        vm.register(email: "", password: "", fullName: "")
        XCTAssertEqual(vm.errorMessage, "Please fill in all fields.")
        
        // Short password
        vm.register(email: "test@test.com", password: "short", fullName: "Test User")
        XCTAssertEqual(vm.errorMessage, "Password must be at least 8 characters.")
    }
    
    @MainActor
    func testAuthViewModelLogout() {
        let vm = AuthViewModel()
        vm.logout()
        XCTAssertFalse(vm.isLoggedIn, "After logout, viewModel should reflect logged out state")
    }
    
    @MainActor
    func testAuthViewModelPasswordResetValidation() {
        let vm = AuthViewModel()
        
        // Empty email
        vm.requestPasswordReset(email: "")
        XCTAssertEqual(vm.errorMessage, "Please enter your email.")
    }
    
    @MainActor
    func testAuthViewModelConfirmResetValidation() {
        let vm = AuthViewModel()
        
        // Empty fields
        vm.confirmPasswordReset(email: "test@test.com", code: "", newPassword: "")
        XCTAssertEqual(vm.errorMessage, "Please fill in all fields.")
        
        // Short password
        vm.confirmPasswordReset(email: "test@test.com", code: "123456", newPassword: "short")
        XCTAssertEqual(vm.errorMessage, "Password must be at least 8 characters.")
    }
    
    // MARK: - AuthError Tests
    
    func testAuthErrorDescriptions() {
        let errors: [AuthError] = [
            .notAuthenticated,
            .noRefreshToken,
            .serverError,
            .httpError(401),
            .api("Custom error message"),
        ]
        
        for error in errors {
            XCTAssertNotNil(error.errorDescription, "AuthError \(error) should have a description")
        }
        
        XCTAssertEqual(AuthError.api("test").errorDescription, "test")
        XCTAssertEqual(AuthError.httpError(404).errorDescription, "HTTP error 404")
    }
    
    // MARK: - Auth Gate Flow Tests
    
    @MainActor
    func testAuthViewModelSyncsWithService() {
        // Logout first
        AuthService.shared.logout()
        
        let vm = AuthViewModel()
        
        // Should mirror service state
        XCTAssertEqual(vm.isLoggedIn, AuthService.shared.isLoggedIn)
    }
}
