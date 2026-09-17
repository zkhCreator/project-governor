/*
 Purpose: Launch the Project Governor SwiftUI evaluation fixture.
 Responsibilities: Create the app scene and apply the test-requested appearance policy.
 Inputs/Outputs: PG_APPEARANCE launch environment in; a ContentView scene out.
 Non-goals: This file does not customize navigation bars or replace native navigation behavior.
 Key Design Decisions: The fixture keeps iOS 26+ native presentation and uses only semantic color roles.
 */

import SwiftUI

@main
struct ProjectGovernorFixtureApp: App {
    private var requestedAppearance: ColorScheme? {
        switch ProcessInfo.processInfo.environment["PG_APPEARANCE"] {
        case "light": .light
        case "dark": .dark
        default: nil
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(requestedAppearance)
        }
    }
}
