import Foundation

@Observable
final class ServerManager {
    private(set) var isRunning = false
    private var task: Process?
    private var healthTimer: Timer?

    func start(repoRoot: String) {
        let uvicorn = "\(repoRoot)/llmind-app/.venv/bin/uvicorn"
        guard FileManager.default.fileExists(atPath: uvicorn) else {
            print("[ServerManager] uvicorn not found at \(uvicorn)")
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: uvicorn)
        process.arguments = ["app.main:app", "--port", "58421", "--no-access-log"]
        process.currentDirectoryURL = URL(fileURLWithPath: "\(repoRoot)/llmind-app")
        process.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                self?.isRunning = false
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                self?.start(repoRoot: repoRoot)
            }
        }
        do {
            try process.run()
            task = process
            scheduleHealthCheck(repoRoot: repoRoot)
        } catch {
            print("[ServerManager] Failed to start: \(error)")
        }
    }

    func stop() {
        healthTimer?.invalidate()
        task?.terminate()
        task = nil
        isRunning = false
    }

    private func scheduleHealthCheck(repoRoot: String) {
        healthTimer?.invalidate()
        healthTimer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in
            Task { @MainActor in
                let reachable = await LLMindAPI.shared.isReachable()
                self?.isRunning = reachable
            }
        }
    }
}
