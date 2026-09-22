"""
Purpose: Verify the stable public command-line contract.
Responsibilities: Cover exit-code mapping and public change-preparation options.
Inputs/Outputs: Verdict strings in; integer exit-code assertions out.
Non-goals: This test does not parse CLI arguments or execute a governance workflow.
Key Design Decisions: Unknown verdicts fail closed as internal/configuration errors.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.cli import _exit_for, build_parser


class CLIExitCodeTests(unittest.TestCase):
    def test_documented_exit_codes(self):
        self.assertEqual(_exit_for("pass"), 0)
        self.assertEqual(_exit_for("fail"), 1)
        self.assertEqual(_exit_for("blocked"), 2)
        self.assertEqual(_exit_for("error"), 3)
        self.assertEqual(_exit_for("unknown"), 3)

    def test_prepare_accepts_novel_reference_mode(self):
        args = build_parser().parse_args(
            [
                "prepare",
                "--change-id",
                "new-component",
                "--goal",
                "Add a new component.",
                "--acceptance",
                "It renders.",
                "--module",
                "Feature",
                "--reference-mode",
                "novel",
            ]
        )
        self.assertEqual(args.reference_mode, "novel")


if __name__ == "__main__":
    unittest.main()
