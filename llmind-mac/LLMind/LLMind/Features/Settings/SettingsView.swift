import SwiftUI

struct SettingsView: View {
    private let settings = AppSettings.shared
    @State private var openAIKey: String = ""
    @State private var voyageKey: String = ""

    var body: some View {
        Form {
            Section("Server") {
                HStack {
                    Text("Repo Root")
                    Spacer()
                    Text(settings.repoRoot.isEmpty ? "Not set" : settings.repoRoot)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button("Change…") { pickRepoRoot() }
                }
            }

            Section("Search") {
                Picker("Default Mode", selection: Binding(
                    get: { settings.searchMode },
                    set: { settings.searchMode = $0 }
                )) {
                    ForEach(SearchMode.allCases, id: \.self) { mode in
                        Text(mode.label).tag(mode)
                    }
                }
                HStack {
                    Text("Search Scope")
                    Spacer()
                    Text(settings.searchScope)
                        .foregroundStyle(.secondary)
                    Button("Change…") { pickScope() }
                }
            }

            Section("API Keys") {
                SecureField("OpenAI API Key", text: $openAIKey)
                    .onSubmit { settings.setAPIKey(openAIKey, for: .openai) }
                SecureField("Voyage AI API Key", text: $voyageKey)
                    .onSubmit { settings.setAPIKey(voyageKey, for: .voyage) }
            }
        }
        .formStyle(.grouped)
        .padding()
        .frame(width: 400)
        .onAppear {
            openAIKey = settings.apiKey(for: .openai) ?? ""
            voyageKey = settings.apiKey(for: .voyage) ?? ""
        }
    }

    private func pickRepoRoot() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select the LLMind repository root"
        if panel.runModal() == .OK, let url = panel.url {
            settings.repoRoot = url.path
        }
    }

    private func pickScope() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select default search folder"
        if panel.runModal() == .OK, let url = panel.url {
            settings.searchScope = url.path
        }
    }
}
