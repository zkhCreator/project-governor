"""
Purpose: Verify candidate and protected-governance content addressing.
Responsibilities: Cover tracked files, untracked files, ignored/generated exclusions, and lock digest normalization.
Inputs/Outputs: Temporary Git repositories in; manifest/digest assertions out.
Non-goals: These tests do not exercise build commands or reviewer behavior.
Key Design Decisions: Newly created source must affect the candidate while run output never does.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_governor.snapshot import build_manifest, governance_digest


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_manifest_includes_untracked_and_excludes_runs(self):
        (self.root / "Tracked.swift").write_text("// tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "Tracked.swift"], cwd=self.root, check=True)
        (self.root / "New.swift").write_text("// new\n", encoding="utf-8")
        run = self.root / ".governance" / ".runs" / "one"
        run.mkdir(parents=True)
        (run / "report.md").write_text("generated", encoding="utf-8")
        result = self.root / ".governance" / "changes" / "one" / "result.json"
        result.parent.mkdir(parents=True)
        result.write_text("{}", encoding="utf-8")
        manifest = build_manifest(self.root)
        paths = {item["path"] for item in manifest["files"]}
        self.assertIn("Tracked.swift", paths)
        self.assertIn("New.swift", paths)
        self.assertNotIn(".governance/.runs/one/report.md", paths)
        self.assertNotIn(".governance/changes/one/result.json", paths)

    def test_untracked_change_updates_digest(self):
        (self.root / "File.swift").write_text("one", encoding="utf-8")
        first = build_manifest(self.root)["digest"]
        (self.root / "File.swift").write_text("two", encoding="utf-8")
        second = build_manifest(self.root)["digest"]
        self.assertNotEqual(first, second)

    def test_lock_digest_field_is_not_circular(self):
        governance = self.root / ".governance"
        (governance / "contracts").mkdir(parents=True)
        (governance / "contracts" / "ui.md").write_text("contract", encoding="utf-8")
        (governance / "project.json").write_text("{}", encoding="utf-8")
        lock = {"reviewer": {"model": "inherit"}, "governance_digest": ""}
        (governance / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        first = governance_digest(self.root)
        lock["governance_digest"] = first
        (governance / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        self.assertEqual(first, governance_digest(self.root))
        lock["reviewer"]["model"] = "different"
        (governance / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        self.assertNotEqual(first, governance_digest(self.root))


if __name__ == "__main__":
    unittest.main()
