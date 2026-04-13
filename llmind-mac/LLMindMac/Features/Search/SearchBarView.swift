import SwiftUI

struct SearchBarView: View {
    @Binding var query: String
    @Binding var mode: SearchMode
    @Binding var showModelPicker: Bool

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.tertiary)
                .font(.system(size: 16))

            TextField("Search images…", text: $query)
                .textFieldStyle(.plain)
                .font(.system(size: 17))
                .foregroundStyle(.primary)

            Button(action: { mode = mode.next }) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(modeColor)
                        .frame(width: 6, height: 6)
                    Text(mode.label)
                        .font(.system(size: 11, weight: .semibold))
                }
                .padding(.horizontal, 7)
                .padding(.vertical, 4)
                .background(modeColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(modeColor.opacity(0.3)))
            }
            .buttonStyle(.plain)
            .foregroundStyle(modeColor)

            Button(action: { showModelPicker.toggle() }) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(Color.indigo)
                        .frame(width: 6, height: 6)
                    Text(AppSettings.shared.model.components(separatedBy: "-").first ?? AppSettings.shared.model)
                        .font(.system(size: 11, weight: .semibold))
                }
                .padding(.horizontal, 7)
                .padding(.vertical, 4)
                .background(Color.indigo.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color.indigo.opacity(0.3)))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.indigo)
            .popover(isPresented: $showModelPicker, arrowEdge: .bottom) {
                ModelPickerView()
            }

            Text("ESC")
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
        .padding(.horizontal, 14)
        .frame(height: 52)
    }

    private var modeColor: Color {
        switch mode {
        case .hybrid: return .green
        case .vector: return .blue
        case .keyword: return .red
        }
    }
}
