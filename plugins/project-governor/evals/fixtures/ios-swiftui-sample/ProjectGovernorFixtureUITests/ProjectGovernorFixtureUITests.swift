/*
 Purpose: Produce interaction and screenshot evidence for the iOS SwiftUI adapter fixture.
 Responsibilities: Verify native back navigation, edge-swipe pop, scrolling, sheet dismissal, appearance, and English/Chinese launches.
 Inputs/Outputs: Simulator UI in; XCTest assertions and named PNG attachments in the xcresult bundle out.
 Non-goals: These tests do not grade visual aesthetics or replace Project Governor reviewers.
 Key Design Decisions: Screenshots prove rendered state while assertions and gestures separately prove interaction.
 */

import XCTest

final class ProjectGovernorFixtureUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testNavigationBackScrollAndSheetEnglishLight() throws {
        let app = XCUIApplication()
        app.launchEnvironment["PG_APPEARANCE"] = "light"
        app.launchArguments += ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()

        attachScreenshot(named: "home-en-light")
        app.buttons["open-detail"].tap()
        XCTAssertTrue(app.scrollViews["detail-scroll"].waitForExistence(timeout: 5))
        app.scrollViews["detail-scroll"].swipeUp()
        app.buttons["open-sheet"].tap()
        XCTAssertTrue(app.buttons["dismiss-sheet"].waitForExistence(timeout: 5))
        attachScreenshot(named: "sheet-en-light")
        app.buttons["dismiss-sheet"].tap()
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.buttons["open-detail"].waitForExistence(timeout: 5))
    }

    func testInteractivePopChineseDark() throws {
        let app = XCUIApplication()
        app.launchEnvironment["PG_APPEARANCE"] = "dark"
        app.launchArguments += ["-AppleLanguages", "(zh-Hans)", "-AppleLocale", "zh_CN"]
        app.launch()

        app.buttons["open-detail"].tap()
        XCTAssertTrue(app.scrollViews["detail-scroll"].waitForExistence(timeout: 5))
        let leftEdge = app.coordinate(withNormalizedOffset: CGVector(dx: 0.005, dy: 0.5))
        let interior = app.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5))
        leftEdge.press(forDuration: 0.1, thenDragTo: interior)
        XCTAssertTrue(app.buttons["open-detail"].waitForExistence(timeout: 5))
        attachScreenshot(named: "home-zh-dark-after-edge-pop")
    }

    private func attachScreenshot(named name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
