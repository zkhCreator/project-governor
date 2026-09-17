"""
Purpose: Verify the stable public process exit-code contract.
Responsibilities: Map pass, fail, blocked, error, and unknown verdicts to their documented codes.
Inputs/Outputs: Verdict strings in; integer exit-code assertions out.
Non-goals: This test does not parse CLI arguments or execute a governance workflow.
Key Design Decisions: Unknown verdicts fail closed as internal/configuration errors.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.cli import _exit_for


class CLIExitCodeTests(unittest.TestCase):
    def test_documented_exit_codes(self):
        self.assertEqual(_exit_for("pass"), 0)
        self.assertEqual(_exit_for("fail"), 1)
        self.assertEqual(_exit_for("blocked"), 2)
        self.assertEqual(_exit_for("error"), 3)
        self.assertEqual(_exit_for("unknown"), 3)


if __name__ == "__main__":
    unittest.main()
