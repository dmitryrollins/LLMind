import Cocoa
import SwiftUI

final class MenuBarController {
    private var statusItem: NSStatusItem?
    var onShow: (() -> Void)?
    var onSettings: (() -> Void)?

    func setup() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.title = "⬡"
            button.font = NSFont.systemFont(ofSize: 14, weight: .medium)
            button.action = #selector(statusBarClicked)
            button.target = self
        }
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Show LLMind Search", action: #selector(showSearch), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Settings…", action: #selector(openSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit LLMind", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        for item in menu.items { item.target = self }
        statusItem?.menu = menu
    }

    @objc private func statusBarClicked() { onShow?() }
    @objc private func showSearch() { onShow?() }
    @objc private func openSettings() { onSettings?() }
}
