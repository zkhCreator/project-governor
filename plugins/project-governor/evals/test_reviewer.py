"""
Purpose: Verify isolated reviewer orchestration with a fake Codex executable.
Responsibilities: Confirm output-schema invocation, digest binding, strict validation, and persisted review output.
Inputs/Outputs: Temporary candidate and fake CLI in; validated review assertion out.
Non-goals: This test does not evaluate model quality.
Key Design Decisions: The fake executable crosses the same process boundary as real `codex exec`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from project_governor.errors import GovernanceError
from project_governor.reviewer import run_reviewer
from project_governor.snapshot import build_manifest


class ReviewerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        (self.root / "Feature.swift").write_text("// Purpose: fixture\n", encoding="utf-8")
        governance = self.root / ".governance"
        (governance / "contracts").mkdir(parents=True)
        (governance / "contracts" / "architecture.md").write_text("contract", encoding="utf-8")
        (governance / "references").mkdir()
        (governance / "references" / "index.json").write_text('{"approved": []}', encoding="utf-8")
        change = governance / "changes" / "one"
        change.mkdir(parents=True)
        (change / "spec.json").write_text("{}", encoding="utf-8")
        (change / "ledger.json").write_text("{}", encoding="utf-8")
        (change / "result.json").write_text('{"old": true}', encoding="utf-8")
        self.run_dir = governance / ".runs" / "run-one"
        (self.run_dir / "evidence").mkdir(parents=True)
        self.manifest = build_manifest(self.root)
        self.candidate = self.manifest["digest"]
        self.contract = "b" * 64

    def tearDown(self):
        self.temporary.cleanup()

    def _call_fake(self, source: str, timeout: int = 30):
        fake = self.base / "fake-codex.py"
        fake.write_text(textwrap.dedent(source), encoding="utf-8")
        fake.chmod(0o755)
        previous = os.environ.get("PROJECT_GOVERNOR_CODEX")
        os.environ["PROJECT_GOVERNOR_CODEX"] = str(fake)
        try:
            return run_reviewer(
                self.root,
                PLUGIN_ROOT,
                self.run_dir,
                {
                    "change_id": "one",
                    "candidate_digest": self.candidate,
                    "contract_digest": self.contract,
                },
                self.manifest,
                "architecture",
                "inherit",
                timeout,
            )
        finally:
            if previous is None:
                os.environ.pop("PROJECT_GOVERNOR_CODEX", None)
            else:
                os.environ["PROJECT_GOVERNOR_CODEX"] = previous

    def _passing_source(self, extra_field: str = "") -> str:
        extra = f", 'solution': {extra_field!r}" if extra_field else ""
        return f"""\
            #!/usr/bin/env python3
            import json, pathlib, sys
            bundle = pathlib.Path.cwd()
            assert '--ephemeral' in sys.argv
            assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'
            assert pathlib.Path(sys.argv[sys.argv.index('--output-schema') + 1]).is_file()
            assert not (bundle / 'candidate' / '.governance').exists()
            assert (bundle / 'inputs' / 'change' / 'spec.json').is_file()
            assert (bundle / 'inputs' / 'change' / 'ledger.json').is_file()
            assert not (bundle / 'inputs' / 'change' / 'result.json').exists()
            output = sys.argv[sys.argv.index('-o') + 1]
            payload = {{
              'verdict': 'pass',
              'reviewer': 'architecture',
              'candidate_digest': '{self.candidate}',
              'contract_digest': '{self.contract}',
              'violations': [],
              'unverified': []
              {extra}
            }}
            with open(output, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle)
        """

    def test_fake_codex_review(self):
        review = self._call_fake(self._passing_source())
        self.assertEqual(review["verdict"], "pass")
        self.assertTrue((self.run_dir / "reviews" / "architecture.json").is_file())

    def test_invalid_json_blocks(self):
        source = """\
            #!/usr/bin/env python3
            import sys
            with open(sys.argv[sys.argv.index('-o') + 1], 'w', encoding='utf-8') as handle:
                handle.write('not-json')
        """
        with self.assertRaises(GovernanceError) as context:
            self._call_fake(source)
        self.assertEqual(context.exception.verdict, "blocked")

    def test_extra_output_field_blocks(self):
        with self.assertRaises(GovernanceError) as context:
            self._call_fake(self._passing_source("Prescriptive advice"))
        self.assertEqual(context.exception.verdict, "blocked")

    def test_process_failure_blocks(self):
        with self.assertRaises(GovernanceError) as context:
            self._call_fake("#!/usr/bin/env python3\nimport sys\nsys.exit(7)\n")
        self.assertEqual(context.exception.verdict, "blocked")

    def test_timeout_blocks(self):
        with self.assertRaises(GovernanceError) as context:
            self._call_fake("#!/usr/bin/env python3\nimport time\ntime.sleep(3)\n", timeout=1)
        self.assertEqual(context.exception.verdict, "blocked")


if __name__ == "__main__":
    unittest.main()
