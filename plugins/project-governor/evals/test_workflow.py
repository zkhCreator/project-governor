"""
Purpose: Exercise the Project Governor initialization-to-gate workflow across real process boundaries.
Responsibilities: Verify initialization, explicit recalibration, change preparation, automatic checks, isolated review, and persisted pass results.
Inputs/Outputs: A copied minimal iOS fixture and fake Codex CLI in; a complete temporary `.governance` run out.
Non-goals: This test does not assess model judgment or launch an iOS simulator.
Key Design Decisions: Product files are committed before governance starts so the test can add one non-UI candidate without requiring UI evidence.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from project_governor.state import initialize_project, prepare_change, recalibrate_project
from project_governor.util import read_json, write_json
from project_governor.workflow import verify_change


class WorkflowIntegrationTests(unittest.TestCase):
    def test_initialize_prepare_and_verify_pass(self):
        fixture = PLUGIN_ROOT / "evals" / "fixtures" / "ios-swiftui-sample"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sample"
            shutil.copytree(fixture, root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Project Governor Test",
                    "-c",
                    "user.email=governor@example.invalid",
                    "commit",
                    "-qm",
                    "fixture baseline",
                ],
                cwd=root,
                check=True,
            )

            with patch("project_governor.ios._simulator_inventory", return_value=([], [])):
                initialized = initialize_project(
                    root,
                    "ProjectGovernorFixture.xcodeproj",
                    "ProjectGovernorFixture",
                    None,
                    "17.0",
                    ["en", "zh-Hans"],
                    "system",
                    [],
                    "inherit",
                )
            self.assertEqual(initialized["verdict"], "pass")

            project_path = root / ".governance" / "project.json"
            project = read_json(project_path)
            project["commands"] = [
                {
                    "id": "fixture-check",
                    "kind": "test",
                    "required": True,
                    "timeout_seconds": 30,
                    "argv": [sys.executable, "-c", "print('fixture check passed')"],
                }
            ]
            write_json(project_path, project)
            recalibrate_project(root, accept_current=True, decision_file=None, reviewer_model=None)
            prepared = prepare_change(
                root,
                "add-domain-helper",
                "Add a non-UI domain helper.",
                ["The helper source is present."],
                "Domain",
                "no",
                [],
                ["ProjectGovernorFixture/DomainHelper.swift"],
                ["No UI changes."],
            )
            self.assertEqual(prepared["verdict"], "pass")
            (root / "ProjectGovernorFixture" / "DomainHelper.swift").write_text(
                textwrap.dedent(
                    """\
                    // Purpose: Provide a deterministic non-UI fixture helper.
                    // Responsibilities: Return one stable fixture value.
                    // Inputs/Outputs: No input; a fixture string out.
                    // Non-goals: This file does not render UI or own application state.
                    // Key Decisions: A free function keeps the fixture intentionally small.

                    import Foundation

                    func domainFixtureValue() -> String { "fixture" }
                    """
                ),
                encoding="utf-8",
            )

            fake = Path(temporary) / "fake-codex.py"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, re, sys
                    prompt = sys.argv[-1]
                    candidate = re.search(r'Candidate digest: ([0-9a-f]{64})', prompt).group(1)
                    contract = re.search(r'Contract digest: ([0-9a-f]{64})', prompt).group(1)
                    output = sys.argv[sys.argv.index('-o') + 1]
                    with open(output, 'w', encoding='utf-8') as handle:
                        json.dump({
                            'verdict': 'pass',
                            'reviewer': 'architecture',
                            'candidate_digest': candidate,
                            'contract_digest': contract,
                            'violations': [],
                            'unverified': []
                        }, handle)
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(0o755)
            previous = os.environ.get("PROJECT_GOVERNOR_CODEX")
            os.environ["PROJECT_GOVERNOR_CODEX"] = str(fake)
            try:
                result = verify_change(root, "add-domain-helper")
            finally:
                if previous is None:
                    os.environ.pop("PROJECT_GOVERNOR_CODEX", None)
                else:
                    os.environ["PROJECT_GOVERNOR_CODEX"] = previous

            self.assertEqual(result["verdict"], "pass")
            self.assertEqual(result["review_verdicts"], {"architecture": "pass"})
            self.assertTrue((root / ".governance" / ".runs" / result["run_id"] / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
