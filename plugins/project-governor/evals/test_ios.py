"""
Purpose: Verify iOS project discovery and UI/navigation routing.
Responsibilities: Cover container, scheme, deployment target, locale, XCUITest, SwiftUI, and navigation signals.
Inputs/Outputs: Synthetic temporary project files in; inspection and impact assertions out.
Non-goals: These tests do not require a simulator or compile Swift.
Key Design Decisions: Static inspection routes evidence requirements but never proves runtime behavior.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.ios import inspect_project, navigation_impact, ui_impact


class IOSInspectionTests(unittest.TestCase):
    def test_discovers_ios_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "Sample.xcodeproj"
            scheme = project / "xcshareddata" / "xcschemes" / "Sample.xcscheme"
            scheme.parent.mkdir(parents=True)
            scheme.write_text("<Scheme/>", encoding="utf-8")
            (project / "project.pbxproj").write_text(
                "isa = PBXNativeTarget; name = Sample; IPHONEOS_DEPLOYMENT_TARGET = 17.0;",
                encoding="utf-8",
            )
            source = root / "Sources" / "RootView.swift"
            source.parent.mkdir()
            source.write_text("import SwiftUI\nstruct RootView: View { var body: some View { NavigationStack {} } }", encoding="utf-8")
            tests = root / "SampleUITests" / "SampleUITests.swift"
            tests.parent.mkdir()
            tests.write_text("let app = XCUIApplication()", encoding="utf-8")
            (root / "en.lproj").mkdir()
            inspection = inspect_project(root)
            self.assertEqual(inspection["containers"][0]["type"], "project")
            self.assertEqual(inspection["schemes"], ["Sample"])
            self.assertEqual(inspection["minimum_ios"], "17.0")
            self.assertIn("en", inspection["locales"])
            self.assertTrue(inspection["ui_test_files"])
            relative = source.relative_to(root).as_posix()
            self.assertTrue(ui_impact([relative], "auto", root))
            self.assertTrue(navigation_impact([relative], root))

    def test_conservative_ui_and_navigation_routing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            domain = root / "Domain.swift"
            domain.write_text("import Foundation\nstruct Value {}\n", encoding="utf-8")
            ui = root / "DashboardView.swift"
            ui.write_text("import SwiftUI\nstruct DashboardView: View {}\n", encoding="utf-8")
            self.assertFalse(ui_impact(["Domain.swift"], "auto", root))
            self.assertTrue(ui_impact(["Domain.swift"], "yes", root))
            self.assertTrue(ui_impact(["DashboardView.swift"], "no", root))
            self.assertFalse(navigation_impact(["Domain.swift"], root))


if __name__ == "__main__":
    unittest.main()
