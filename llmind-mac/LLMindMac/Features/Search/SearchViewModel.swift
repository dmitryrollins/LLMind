import Foundation
import AppKit

@Observable
final class SearchViewModel {
    var query: String = "" {
        didSet { scheduleSearch() }
    }
    var results: [SearchResult] = []
    var selectedIndex: Int = 0
    var isLoading: Bool = false
    var mode: SearchMode = AppSettings.shared.searchMode {
        didSet { AppSettings.shared.searchMode = mode; triggerSearch() }
    }
    var showModelPicker: Bool = false

    private var debounceTask: Task<Void, Never>?
    private let api = LLMindAPI.shared
    private let settings = AppSettings.shared

    // MARK: - Search

    private func scheduleSearch() {
        debounceTask?.cancel()
        debounceTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 300_000_000)
            guard !Task.isCancelled else { return }
            await performSearch()
        }
    }

    private func triggerSearch() {
        debounceTask?.cancel()
        Task { @MainActor in await performSearch() }
    }

    @MainActor
    private func performSearch() async {
        let q = query.trimmingCharacters(in: .whitespaces)

        if q.isEmpty {
            await loadRecentFiles()
            return
        }

        isLoading = true
        defer { isLoading = false }

        let provider = settings.provider
        let model = settings.model
        let apiKey = settings.apiKey(for: provider)
        let scope = settings.searchScope

        do {
            let found = try await api.search(
                query: q, mode: mode,
                provider: provider, model: model,
                apiKey: apiKey, scope: scope
            )
            results = found
            selectedIndex = 0
        } catch {
            if mode != .keyword {
                mode = .keyword
                await performSearch()
            } else {
                results = []
            }
        }
    }

    @MainActor
    private func loadRecentFiles() async {
        do {
            let files = try await api.recentFiles(scope: settings.searchScope)
            results = files.map { f in
                SearchResult(
                    path: f.path, filename: f.name,
                    score: 0, vectorScore: 0, keywordScore: 0,
                    description: "", fileType: f.fileType
                )
            }
            selectedIndex = 0
        } catch {
            results = []
        }
    }

    // MARK: - Keyboard actions

    func moveUp() {
        guard !results.isEmpty else { return }
        selectedIndex = max(0, selectedIndex - 1)
    }

    func moveDown() {
        guard !results.isEmpty else { return }
        selectedIndex = min(results.count - 1, selectedIndex + 1)
    }

    func openSelected() {
        guard let result = selectedResult else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: result.path))
    }

    func revealSelected() {
        guard let result = selectedResult else { return }
        Task { try? await api.reveal(path: result.path) }
    }

    func copySelectedPath() {
        guard let result = selectedResult else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(result.path, forType: .string)
    }

    func cycleMode() {
        mode = mode.next
    }

    var selectedResult: SearchResult? {
        guard !results.isEmpty, selectedIndex < results.count else { return nil }
        return results[selectedIndex]
    }
}
