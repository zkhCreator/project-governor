"""
Purpose: Verify strict Project Governor JSON validation behavior.
Responsibilities: Cover change reference modes, valid reviews, forbidden advice fields, unknown rules, and verdict invariants.
Inputs/Outputs: In-memory fixture dictionaries in; unittest assertions out.
Non-goals: These tests do not invoke Codex or inspect an Xcode project.
Key Design Decisions: Reviewer output remains narrow so feedback cannot prescribe implementation.
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

    def test_rejects_solution_field(self):
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
            }
        ]
        with self.assertRaises(GovernanceError):
            validate_review(review, "architecture", "a" * 64, "b" * 64, {"ARCH-001"})

    def test_pass_cannot_hide_unverified_claim(self):
        review = self.base_review()
        review["unverified"] = [{"claim": "Back gesture", "required_evidence": "XCUITest"}]
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
