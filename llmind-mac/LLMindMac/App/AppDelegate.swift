import Cocoa
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    let serverManager = ServerManager()
    let menuBarController = MenuBarController()
    let hotkeyManager = HotkeyManager()
    lazy var searchWindowController = SearchWindowController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let repoRoot = AppSettings.shared.repoRoot
        if repoRoot.isEmpty {
            promptForRepoRoot()
        } else {
            serverManager.start(repoRoot: repoRoot)
        }

        menuBarController.setup()
        menuBarController.onShow = { [weak self] in self?.searchWindowController.toggle() }
        menuBarController.onSettings = { [weak self] in self?.openSettings() }

        hotkeyManager.onHotkey = { [weak self] in self?.searchWindowController.toggle() }
        hotkeyManager.register()
    }

    func applicationWillTerminate(_ notification: Notification) {
        serverManager.stop()
        hotkeyManager.unregister()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }

    private func openSettings() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 320),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "LLMind Settings"
        window.center()
        window.contentView = NSHostingView(rootView: SettingsView())
        window.makeKeyAndOrderFront(nil)
    }

    private func promptForRepoRoot() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select the LLMind repository root folder"
        panel.prompt = "Select"
        if panel.runModal() == .OK, let url = panel.url {
            AppSettings.shared.repoRoot = url.path
            serverManager.start(repoRoot: url.path)
        }
    }
}
