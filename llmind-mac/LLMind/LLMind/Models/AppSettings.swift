import Foundation
import Security

@Observable
final class AppSettings {
    static let shared = AppSettings()

    private enum Keys {
        static let repoRoot = "repoRoot"
        static let provider = "embedProvider"
        static let model = "embedModel"
        static let searchMode = "searchMode"
        static let searchScope = "searchScope"
    }

    var repoRoot: String {
        get { UserDefaults.standard.string(forKey: Keys.repoRoot) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.repoRoot) }
    }

    var provider: EmbedProvider {
        get {
            let raw = UserDefaults.standard.string(forKey: Keys.provider) ?? "ollama"
            return EmbedProvider(rawValue: raw) ?? .ollama
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Keys.provider) }
    }

    var model: String {
        get { UserDefaults.standard.string(forKey: Keys.model) ?? "nomic-embed-text" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.model) }
    }

    var searchMode: SearchMode {
        get {
            let raw = UserDefaults.standard.string(forKey: Keys.searchMode) ?? "hybrid"
            return SearchMode(rawValue: raw) ?? .hybrid
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Keys.searchMode) }
    }

    var searchScope: String {
        get { UserDefaults.standard.string(forKey: Keys.searchScope) ?? "~/" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.searchScope) }
    }

    // MARK: - Keychain API keys

    func apiKey(for provider: EmbedProvider) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.llmind.\(provider.rawValue)",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func setAPIKey(_ key: String, for provider: EmbedProvider) {
        let data = key.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.llmind.\(provider.rawValue)",
            kSecValueData as String: data,
        ]
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }
}
