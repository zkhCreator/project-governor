/*
 Purpose: Exercise representative native SwiftUI navigation and sheet behavior for adapter evaluation.
 Responsibilities: Present a root list, push a detail screen, scroll content, and present/dismiss a sheet.
 Inputs/Outputs: User taps and swipe gestures in; visible navigation, sheet, and accessibility state out.
 Non-goals: This fixture is not a reusable design system or a product-specific reference design.
 Key Design Decisions: NavigationStack and the system back button preserve accessibility and interactive pop.
 */

import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            List {
                NavigationLink {
                    DetailView()
                } label: {
                    Label("detail.open", systemImage: "waveform.path.ecg")
                }
                .accessibilityIdentifier("open-detail")
            }
            .navigationTitle("home.title")
            .accessibilityIdentifier("home-list")
        }
    }
}

private struct DetailView: View {
    @State private var showsSheet = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                ForEach(0..<12, id: \.self) { index in
                    Text("detail.row \(index + 1)")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button("sheet.open") {
                    showsSheet = true
                }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("open-sheet")
            }
            .padding()
        }
        .navigationTitle("detail.title")
        .accessibilityIdentifier("detail-scroll")
        .sheet(isPresented: $showsSheet) {
            NavigationStack {
                VStack(spacing: 16) {
                    Text("sheet.title")
                        .font(.title2)
                    Button("sheet.dismiss") {
                        showsSheet = false
                    }
                    .accessibilityIdentifier("dismiss-sheet")
                }
                .navigationTitle("sheet.title")
                .padding()
            }
        }
    }
}
