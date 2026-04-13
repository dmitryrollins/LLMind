import Foundation

enum SearchMode: String, CaseIterable {
    case hybrid, vector, keyword

    var label: String {
        switch self {
        case .hybrid: return "hybrid"
        case .vector: return "vector"
        case .keyword: return "keyword"
        }
    }

    var icon: String {
        switch self {
        case .hybrid: return "⚡"
        case .vector: return "〈v〉"
        case .keyword: return "Aa"
        }
    }

    var next: SearchMode {
        let all = SearchMode.allCases
        let idx = all.firstIndex(of: self)!
        return all[(idx + 1) % all.count]
    }
}

enum EmbedProvider: String, CaseIterable, Identifiable {
    case ollama, openai, voyage
    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .ollama: return "Ollama (local)"
        case .openai: return "OpenAI"
        case .voyage: return "Voyage AI"
        }
    }

    var models: [String] {
        switch self {
        case .ollama: return ["nomic-embed-text"]
        case .openai: return ["text-embedding-3-small", "text-embedding-3-large"]
        case .voyage: return ["voyage-3.5"]
        }
    }

    var requiresAPIKey: Bool { self != .ollama }
}

struct SearchResult: Identifiable {
    let id = UUID()
    let path: String
    let filename: String
    let score: Double
    let vectorScore: Double
    let keywordScore: Double
    let description: String
    let fileType: String
}
