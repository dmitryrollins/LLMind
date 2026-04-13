import SwiftUI

struct ModelPickerView: View {
    @Environment(\.dismiss) private var dismiss
    private let settings = AppSettings.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(EmbedProvider.allCases) { provider in
                Section {
                    ForEach(provider.models, id: \.self) { model in
                        Button(action: {
                            settings.provider = provider
                            settings.model = model
                            dismiss()
                        }) {
                            HStack(spacing: 10) {
                                Circle()
                                    .fill(providerColor(provider))
                                    .frame(width: 7, height: 7)
                                Text(model)
                                    .font(.system(size: 13))
                                Spacer()
                                if settings.provider == provider && settings.model == model {
                                    Image(systemName: "checkmark")
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(.indigo)
                                } else if provider.requiresAPIKey {
                                    Text("API key required")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.tertiary)
                                }
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(
                            settings.provider == provider && settings.model == model
                            ? Color.indigo.opacity(0.08) : Color.clear
                        )
                    }
                } header: {
                    Text(provider.displayName.uppercased())
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(.tertiary)
                        .padding(.horizontal, 12)
                        .padding(.top, 10)
                        .padding(.bottom, 4)
                }
            }

            Divider().padding(.top, 4)
            Text("⌘, to manage API keys")
                .font(.system(size: 10))
                .foregroundStyle(.quaternary)
                .padding(10)
        }
        .frame(width: 260)
        .background(.regularMaterial)
    }

    private func providerColor(_ provider: EmbedProvider) -> Color {
        switch provider {
        case .ollama: return .green
        case .openai: return .blue
        case .voyage: return .pink
        }
    }
}
