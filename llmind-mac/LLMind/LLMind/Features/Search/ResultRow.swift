import SwiftUI

struct ResultRow: View {
    let result: SearchResult
    let isSelected: Bool
    let showScore: Bool

    var body: some View {
        HStack(spacing: 12) {
            AsyncImage(url: LLMindAPI.shared.thumbnailURL(for: result.path)) { phase in
                switch phase {
                case .success(let image):
                    image.resizable().aspectRatio(contentMode: .fill)
                default:
                    RoundedRectangle(cornerRadius: 7)
                        .fill(Color(white: 0.2))
                }
            }
            .frame(width: 44, height: 44)
            .clipShape(RoundedRectangle(cornerRadius: 7))

            VStack(alignment: .leading, spacing: 2) {
                Text(result.filename)
                    .font(.system(size: 13))
                    .lineLimit(1)
                    .foregroundStyle(isSelected ? .primary : .secondary)
                if !result.description.isEmpty {
                    Text(result.description)
                        .font(.system(size: 11))
                        .lineLimit(1)
                        .foregroundStyle(.tertiary)
                }
            }

            Spacer()

            if isSelected {
                HStack(spacing: 4) {
                    KeyHint("↵", label: "Open")
                    KeyHint("⌘↵", label: "Reveal")
                    KeyHint("⌘C", label: "Copy")
                }
            } else if showScore && result.score > 0 {
                Text(String(format: "%.3f", result.score))
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundStyle(scoreColor)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .background(isSelected ? Color(white: 0.18) : Color.clear)
        .contentShape(Rectangle())
    }

    private var scoreColor: Color {
        if result.score > 0.35 { return .cyan }
        if result.score > 0.20 { return .secondary }
        return .tertiary
    }
}

private struct KeyHint: View {
    let key: String
    let label: String
    init(_ key: String, label: String) { self.key = key; self.label = label }
    var body: some View {
        Text("\(key) \(label)")
            .font(.system(size: 10))
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(Color(white: 0.25))
            .clipShape(RoundedRectangle(cornerRadius: 4))
            .foregroundStyle(.secondary)
    }
}
