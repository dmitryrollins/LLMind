import SwiftUI

struct FooterView: View {
    let resultCount: Int
    let mode: SearchMode
    let scope: String

    var body: some View {
        HStack(spacing: 16) {
            Group {
                keyHint("↑↓", "navigate")
                keyHint("↵", "open")
                keyHint("⌘↵", "reveal")
                keyHint("⌘C", "copy")
            }
            Spacer()
            Text("\(resultCount) result\(resultCount == 1 ? "" : "s") · \(scope) · \(mode.label)")
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private func keyHint(_ key: String, _ action: String) -> some View {
        HStack(spacing: 3) {
            Text(key)
                .padding(.horizontal, 4)
                .padding(.vertical, 1)
                .background(Color(white: 0.2))
                .clipShape(RoundedRectangle(cornerRadius: 3))
                .font(.system(size: 10))
                .foregroundStyle(.quaternary)
            Text(action)
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
    }
}
