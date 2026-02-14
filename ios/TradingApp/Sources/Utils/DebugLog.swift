import Foundation

/// Debug-only logging utility
/// Prints only in DEBUG builds, stripped from release builds
@inline(__always)
func debugLog(_ message: @autoclosure () -> String, file: String = #file, line: Int = #line) {
    #if DEBUG
    let filename = (file as NSString).lastPathComponent
    print("[\(filename):\(line)] \(message())")
    #endif
}

/// Debug-only logging for errors
@inline(__always)
func debugError(_ error: Error, context: String = "", file: String = #file, line: Int = #line) {
    #if DEBUG
    let filename = (file as NSString).lastPathComponent
    if context.isEmpty {
        print("[\(filename):\(line)] Error: \(error.localizedDescription)")
    } else {
        print("[\(filename):\(line)] \(context): \(error.localizedDescription)")
    }
    #endif
}
