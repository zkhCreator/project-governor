"""
Purpose: Verify the public-release audit detects disclosure risks without rejecting supported project conventions.
Responsibilities: Cover sensitive text, structured module comments, workflow references, and repository-tree fallback discovery.
Inputs/Outputs: Temporary candidate files in; unittest assertions and process status out.
Non-goals: These tests do not inspect live GitHub settings, prove copyright ownership, or modify repository visibility.
Key Design Decisions: Tests construct secret-like samples at runtime so the test source itself remains safe to publish.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import public_release_audit as audit_module


class PublicReleaseAuditTests(unittest.TestCase):
    def test_accepts_both_supported_key_decision_headings(self) -> None:
        for heading in ("Key Decisions:", "Key Design Decisions:"):
            with self.subTest(heading=heading), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "sample.py"
                text = (
                    '"""\n'
                    "Purpose: Test.\n"
                    "Responsibilities: Test.\n"
                    "Inputs/Outputs: Input in; output out.\n"
                    "Non-goals: None.\n"
                    f"{heading} Test.\n"
                    '"""\n'
                )
                path.write_text(text, encoding="utf-8")
                errors: list[str] = []

                audit_module._audit_python(root, path, text, errors)

                self.assertEqual(errors, [])

    def test_detects_constructed_secret_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sample.txt"
            secret = "github" + "_pat_" + ("A" * 24)
            text = f"token={secret}\n"
            path.write_text(text, encoding="utf-8")
            errors: list[str] = []

            audit_module._audit_text(root, path, text, errors)

            self.assertTrue(any("fine-grained token" in error for error in errors))

    def test_rejects_mutable_action_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".github/workflows/test.yml"
            path.parent.mkdir(parents=True)
            text = "permissions:\n  contents: read\nsteps:\n  - uses: actions/checkout@main\n"
            path.write_text(text, encoding="utf-8")
            errors: list[str] = []

            audit_module._audit_actions(root, path, text, errors)

            self.assertTrue(any("mutable branch reference" in error for error in errors))

    def test_fallback_discovers_files_outside_a_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "sample.txt"
            expected.write_text("safe\n", encoding="utf-8")

            self.assertEqual(audit_module._candidate_files(root), [expected])

    def test_history_requires_acknowledgment_for_public_author_email(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            sample = root / "sample.txt"
            sample.write_text("safe\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.txt"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Public Test",
                    "-c",
                    "user.email=person@example.com",
                    "commit",
                    "-q",
                    "-m",
                    "Safe fixture",
                ],
                cwd=root,
                check=True,
            )

            errors = audit_module.audit_history(root)
            acknowledged = audit_module.audit_history(root, allow_public_author_emails=True)

            self.assertTrue(any("non-noreply author email" in error for error in errors))
            self.assertEqual(acknowledged, [])


if __name__ == "__main__":
    unittest.main()
