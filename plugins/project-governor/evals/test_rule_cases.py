"""
Purpose: Guard the minimum composition of the Project Governor behavioral evaluation corpus.
Responsibilities: Verify case count, expected verdict categories, and required identifiers.
Inputs/Outputs: The checked-in cases JSON in; unittest assertions out.
Non-goals: This test does not substitute for independent model evaluation of the cases.
Key Design Decisions: Holdout flags keep some cases separate from prompt/rule tuning.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class RuleCaseCorpusTests(unittest.TestCase):
    def test_required_case_mix(self):
        path = Path(__file__).resolve().parent / "cases" / "cases.json"
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 12)
        categories = [item["category"] for item in cases]
        self.assertGreaterEqual(categories.count("compliant"), 4)
        self.assertGreaterEqual(categories.count("architecture-violation"), 4)
        self.assertGreaterEqual(categories.count("ui-violation"), 3)
        self.assertGreaterEqual(categories.count("missing-evidence"), 1)
        self.assertTrue(any(item.get("holdout") for item in cases))
        self.assertEqual(len({item["id"] for item in cases}), len(cases))


if __name__ == "__main__":
    unittest.main()
