import Cocoa
import SwiftUI

final class SearchWindowController: NSWindowController {
    convenience init() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 580, height: 500),
            styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless],
            backing: .buffered,
            defer: false
        )
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = false
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = NSHostingView(rootView: SearchView())
        self.init(window: panel)
    }

    func toggle() {
        guard let window else { return }
        if window.isVisible {
            hide()
        } else {
            show()
        }
    }

    func show() {
        guard let window, let screen = NSScreen.main else { return }
        let sw = screen.visibleFrame.width
        let sh = screen.visibleFrame.height
        let x = screen.visibleFrame.minX + (sw - window.frame.width) / 2
        let y = screen.visibleFrame.minY + sh * 0.62
        window.setFrameOrigin(NSPoint(x: x, y: y))
        window.makeKeyAndOrderFront(nil)
        window.contentView?.window?.makeFirstResponder(window.contentView)
    }

    func hide() {
        window?.orderOut(nil)
    }
}
