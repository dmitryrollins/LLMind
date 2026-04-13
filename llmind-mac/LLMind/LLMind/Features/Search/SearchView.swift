import SwiftUI

struct SearchView: View {
    @State private var vm = SearchViewModel()

    var body: some View {
        VStack(spacing: 0) {
            SearchBarView(
                query: $vm.query,
                mode: $vm.mode,
                showModelPicker: $vm.showModelPicker
            )

            Divider()

            if vm.results.isEmpty && !vm.isLoading && vm.query.isEmpty {
                Text("Type to search enriched images…")
                    .font(.system(size: 13))
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
            } else if vm.results.isEmpty && !vm.isLoading {
                Text("No matches for "\(vm.query)"")
                    .font(.system(size: 13))
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(Array(vm.results.enumerated()), id: \.element.id) { idx, result in
                                ResultRow(
                                    result: result,
                                    isSelected: idx == vm.selectedIndex,
                                    showScore: !vm.query.isEmpty
                                )
                                .id(idx)
                                .onTapGesture { vm.selectedIndex = idx; vm.openSelected() }
                                Divider().padding(.leading, 70)
                            }
                        }
                    }
                    .onChange(of: vm.selectedIndex) { _, new in
                        withAnimation(.easeInOut(duration: 0.1)) { proxy.scrollTo(new) }
                    }
                }
                .frame(maxHeight: 360)
            }

            Divider()

            FooterView(
                resultCount: vm.results.count,
                mode: vm.mode,
                scope: AppSettings.shared.searchScope
            )
        }
        .frame(width: 580)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.5), radius: 32, y: 16)
        .onKeyPress(.upArrow) { vm.moveUp(); return .handled }
        .onKeyPress(.downArrow) { vm.moveDown(); return .handled }
        .onKeyPress(.return) { vm.openSelected(); return .handled }
        .onKeyPress(.return, phases: .down) { event in
            if event.modifiers.contains(.command) { vm.revealSelected(); return .handled }
            return .ignored
        }
        .onKeyPress("c", phases: .down) { event in
            if event.modifiers.contains(.command) { vm.copySelectedPath(); return .handled }
            return .ignored
        }
    }
}
