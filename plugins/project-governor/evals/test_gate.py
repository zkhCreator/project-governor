"""
Purpose: Verify the deterministic all-conditions gate truth table.
Responsibilities: Cover pass, test failure, missing evidence, digest drift, and unapproved exceptions.
Inputs/Outputs: In-memory run states in; verdict assertions out.
Non-goals: These tests do not execute external commands.
Key Design Decisions: Integrity and missing evidence block; evidenced rule or test violations fail.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.gate import evaluate_gate


class GateTests(unittest.TestCase):
    def state(self):
        digest = "a" * 64
        contract = "b" * 64
        return {
            "candidate_digest": digest,
            "contract_digest": contract,
            "candidate_stable": True,
            "protected_state_stable": True,
            "version_consistent": True,
            "evidence_stable": True,
            "pending_exceptions": [],
            "ui_required": False,
            "automatic_checks": [{"id": "build", "required": True, "status": "pass"}],
            "required_reviewers": ["architecture"],
            "reviews": {
                "architecture": {
                    "verdict": "pass",
                    "candidate_digest": digest,
                    "contract_digest": contract,
                    "violations": [],
                    "unverified": [],
                }
            },
        }

    def test_pass(self):
        self.assertEqual(evaluate_gate(self.state())["verdict"], "pass")

    def test_failed_check_fails(self):
        state = self.state()
        state["automatic_checks"][0]["status"] = "fail"
        self.assertEqual(evaluate_gate(state)["verdict"], "fail")

    def test_missing_ui_evidence_blocks(self):
        state = self.state()
        state["ui_required"] = True
        state["ui_evidence"] = {"status": "blocked", "reason": "No simulator"}
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_candidate_drift_blocks(self):
        state = self.state()
        state["candidate_stable"] = False
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_pending_exception_blocks(self):
        state = self.state()
        state["pending_exceptions"] = ["UI-003"]
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_each_integrity_condition_blocks(self):
        for field in ("protected_state_stable", "version_consistent", "evidence_stable"):
            with self.subTest(field=field):
                state = self.state()
                state[field] = False
                self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_blocked_automatic_check_blocks(self):
        state = self.state()
        state["automatic_checks"][0]["status"] = "blocked"
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_optional_failed_check_does_not_gate(self):
        state = self.state()
        state["automatic_checks"].append(
            {"id": "optional", "required": False, "status": "fail"}
        )
        self.assertEqual(evaluate_gate(state)["verdict"], "pass")

    def test_missing_or_unverified_reviewer_blocks(self):
        missing = self.state()
        missing["reviews"] = {}
        self.assertEqual(evaluate_gate(missing)["verdict"], "blocked")

        unverified = self.state()
        unverified["reviews"]["architecture"]["verdict"] = "blocked"
        unverified["reviews"]["architecture"]["unverified"] = [
            {"claim": "Interaction", "required_evidence": "XCUITest"}
        ]
        self.assertEqual(evaluate_gate(unverified)["verdict"], "blocked")

    def test_reviewer_failure_fails(self):
        state = self.state()
        state["reviews"]["architecture"]["verdict"] = "fail"
        self.assertEqual(evaluate_gate(state)["verdict"], "fail")

    def test_reviewer_digest_mismatch_blocks(self):
        state = self.state()
        state["reviews"]["architecture"]["candidate_digest"] = "c" * 64
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")

    def test_ui_failure_fails(self):
        state = self.state()
        state["ui_required"] = True
        state["ui_evidence"] = {"status": "fail"}
        self.assertEqual(evaluate_gate(state)["verdict"], "fail")

    def test_blocked_takes_precedence_over_failure(self):
        state = self.state()
        state["candidate_stable"] = False
        state["automatic_checks"][0]["status"] = "fail"
        self.assertEqual(evaluate_gate(state)["verdict"], "blocked")


if __name__ == "__main__":
    unittest.main()
