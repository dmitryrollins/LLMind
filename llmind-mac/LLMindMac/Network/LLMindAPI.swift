import Foundation

enum LLMindAPIError: Error {
    case serverUnreachable
    case badResponse(Int)
    case decodingFailed
}

struct ScanResponse: Codable {
    let directory: String
    let count: Int
    let files: [FileInfo]

    struct FileInfo: Codable {
        let path: String
        let name: String
        let fileType: String
        let sizeBytes: Int

        enum CodingKeys: String, CodingKey {
            case path, name
            case fileType = "file_type"
            case sizeBytes = "size_bytes"
        }
    }
}

struct SearchResponse: Codable {
    let query: String
    let mode: String
    let total: Int
    let results: [SearchResultDTO]

    struct SearchResultDTO: Codable {
        let path: String
        let filename: String
        let score: Double
        let vectorScore: Double
        let keywordScore: Double
        let description: String
        let fileType: String

        enum CodingKeys: String, CodingKey {
            case path, filename, score, description
            case vectorScore = "vector_score"
            case keywordScore = "keyword_score"
            case fileType = "file_type"
        }
    }
}

actor LLMindAPI {
    static let shared = LLMindAPI()
    private let base = URL(string: "http://127.0.0.1:58421")!
    private let session = URLSession.shared
    private let decoder = JSONDecoder()

    func isReachable() async -> Bool {
        var comps = URLComponents(url: base.appendingPathComponent("/api/scan"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "dir", value: NSHomeDirectory())]
        var req = URLRequest(url: comps.url!)
        req.timeoutInterval = 2
        do {
            let (_, resp) = try await session.data(for: req)
            return (resp as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func search(
        query: String,
        mode: SearchMode,
        provider: EmbedProvider,
        model: String,
        apiKey: String?,
        scope: String,
        top: Int = 20
    ) async throws -> [SearchResult] {
        var comps = URLComponents(url: base.appendingPathComponent("/api/search"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "dir", value: (scope as NSString).expandingTildeInPath),
            URLQueryItem(name: "mode", value: mode.rawValue),
            URLQueryItem(name: "provider", value: provider.rawValue),
            URLQueryItem(name: "model", value: model),
            URLQueryItem(name: "top", value: String(top)),
            URLQueryItem(name: "recursive", value: "true"),
        ]
        if let key = apiKey {
            comps.queryItems?.append(URLQueryItem(name: "api_key", value: key))
        }
        let req = URLRequest(url: comps.url!, timeoutInterval: 30)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw LLMindAPIError.serverUnreachable }
        guard http.statusCode == 200 else { throw LLMindAPIError.badResponse(http.statusCode) }
        let dto = try decoder.decode(SearchResponse.self, from: data)
        return dto.results.map { r in
            SearchResult(
                path: r.path, filename: r.filename,
                score: r.score, vectorScore: r.vectorScore,
                keywordScore: r.keywordScore,
                description: r.description, fileType: r.fileType
            )
        }
    }

    func thumbnailURL(for path: String) -> URL {
        var comps = URLComponents(url: base.appendingPathComponent("/api/thumbnail"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "path", value: path)]
        return comps.url!
    }

    func reveal(path: String) async throws {
        let url = base.appendingPathComponent("/api/reveal")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["path": path])
        let (_, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw LLMindAPIError.badResponse(0)
        }
    }

    func recentFiles(scope: String, limit: Int = 10) async throws -> [ScanResponse.FileInfo] {
        var comps = URLComponents(url: base.appendingPathComponent("/api/scan"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "dir", value: (scope as NSString).expandingTildeInPath),
            URLQueryItem(name: "recursive", value: "true"),
        ]
        let req = URLRequest(url: comps.url!, timeoutInterval: 10)
        let (data, _) = try await session.data(for: req)
        let dto = try decoder.decode(ScanResponse.self, from: data)
        return Array(dto.files.prefix(limit))
    }
}
