import Cocoa

final class HotkeyManager {
    private var eventTap: CFMachPort?
    var onHotkey: (() -> Void)?

    func register() {
        let mask = CGEventMask(1 << CGEventType.keyDown.rawValue)
        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: { proxy, type, event, refcon in
                guard let refcon else { return Unmanaged.passRetained(event) }
                let manager = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()
                let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
                let flags = event.flags
                let isCmd   = flags.contains(.maskCommand)
                let isShift = flags.contains(.maskShift)
                let isSpace = keyCode == 49
                if isCmd && isShift && isSpace {
                    DispatchQueue.main.async { manager.onHotkey?() }
                    return nil
                }
                return Unmanaged.passRetained(event)
            },
            userInfo: Unmanaged.passRetained(self).toOpaque()
        )
        if let tap = eventTap {
            let loop = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), loop, .commonModes)
            CGEvent.tapEnable(tap: tap, enable: true)
        }
    }

    func unregister() {
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
    }
}
