"""
Purpose: Verify strict Project Governor JSON validation behavior.
Responsibilities: Cover change reference modes, actionable review findings, unknown fields and rules, and verdict invariants.
Inputs/Outputs: In-memory fixture dictionaries in; unittest assertions out.
Non-goals: These tests do not invoke Codex or inspect an Xcode project.
Key Design Decisions: Remediation belongs to a specific finding and cannot add an uncited rule.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.errors import GovernanceError
from project_governor.validation import validate_review, validate_spec


class ReviewValidationTests(unittest.TestCase):
    def base_spec(self):
        return {
            "schema_version": 1,
            "change_id": "new-component",
            "goal": "Add a component.",
            "acceptance": ["The component renders."],
            "module": "Feature",
            "ui_impact": "yes",
            "ui_states": ["default"],
            "scope": ["Feature/NewComponent.swift"],
            "non_goals": [],
            "baseline_governance_digest": "c" * 64,
        }

    def base_review(self):
        return {
            "verdict": "pass",
            "reviewer": "architecture",
            "candidate_digest": "a" * 64,
            "contract_digest": "b" * 64,
            "violations": [],
            "unverified": [],
        }

    def test_valid_pass(self):
        review = self.base_review()
        self.assertEqual(
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})["verdict"],
            "pass",
        )

    def test_rejects_unattached_solution_field(self):
        review = self.base_review()
        review["solution"] = "Add another card"
        with self.assertRaises(GovernanceError) as context:
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})
        self.assertEqual(context.exception.verdict, "blocked")

    def test_rejects_unknown_rule(self):
        review = self.base_review()
        review["verdict"] = "fail"
        review["violations"] = [
            {
                "rule_id": "INVENTED-001",
                "state": "default",
                "observation": "Observation",
                "conflict": "Conflict",
                "evidence_refs": ["candidate/File.swift"],
                "remediation": "Use the approved structure.",
                "requires_user_decision": False,
            }
        ]
        with self.assertRaises(GovernanceError):
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})

    def test_pass_cannot_hide_unverified_claim(self):
        review = self.base_review()
        review["unverified"] = [{"claim": "Back gesture", "required_evidence": "XCUITest", "remediation": "Run the back-gesture XCUITest on the minimum runtime.", "requires_user_decision": False}]
        with self.assertRaises(GovernanceError):
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})

    def test_violation_requires_actionable_remediation(self):
        review = self.base_review()
        review["verdict"] = "fail"
        review["violations"] = [{
            "rule_id": "ARCH-001",
            "state": "default",
            "observation": "The candidate duplicates the approved owner.",
            "conflict": "ARCH-001 requires one owner.",
            "evidence_refs": ["candidate/File.swift"],
            "remediation": "Move the duplicated state into the approved owner and rerun review.",
            "requires_user_decision": False,
        }]
        self.assertEqual(validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})["verdict"], "fail")
        review["violations"][0]["remediation"] = " "
        with self.assertRaises(GovernanceError):
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})

    def test_blocked_requires_remediation_and_decision_flag(self):
        review = self.base_review()
        review["verdict"] = "blocked"
        review["unverified"] = [{
            "claim": "Back gesture",
            "required_evidence": "Minimum-iOS interaction result",
            "remediation": "Run the back-gesture scenario on the minimum supported iOS runtime.",
            "requires_user_decision": False,
        }]
        self.assertEqual(validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})["verdict"], "blocked")
        review["unverified"][0]["requires_user_decision"] = "no"
        with self.assertRaises(GovernanceError):
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})

    def test_legacy_spec_defaults_reference_mode_to_auto(self):
        self.assertEqual(validate_spec(self.base_spec())["reference_mode"], "auto")

    def test_novel_reference_mode_is_valid(self):
        spec = self.base_spec()
        spec["reference_mode"] = "novel"
        self.assertEqual(validate_spec(spec)["reference_mode"], "novel")

    def test_unknown_reference_mode_is_rejected(self):
        spec = self.base_spec()
        spec["reference_mode"] = "skip-review"
        with self.assertRaises(GovernanceError):
            validate_spec(spec)


if __name__ == "__main__":
    unittest.main()
