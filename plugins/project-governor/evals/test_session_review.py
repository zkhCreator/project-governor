"""
Purpose: Verify the in-session review handoff preserves the formal gate.
Responsibilities: Exercise real snapshot/check/request/submit persistence and reject stale,
forged bindings, missing roles, invalid schemas, duplicate submissions and input drift.
Inputs/Outputs: Disposable Git fixture, real Python check, synthetic reviewer responses.
Non-goals: Synthetic responses test the protocol, not model judgment or iOS rendering.
Key Design Decisions: Codex subprocess execution is forbidden in every in-session test.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from project_governor.errors import GovernanceError
from project_governor.state import initialize_project, prepare_change, recalibrate_project
from project_governor.util import read_json, write_json
from project_governor.workflow import verify_change, review_existing
from project_governor.session_review import submit_session_review, session_status


class SessionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sample"
        shutil.copytree(PLUGIN_ROOT / "evals/fixtures/ios-swiftui-sample", self.root)
        for argv in (["git", "init", "-q"], ["git", "add", "."],
                     ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"]):
            subprocess.run(argv, cwd=self.root, check=True, capture_output=True)
        with patch("project_governor.ios._simulator_inventory", return_value=([], [])):
            initialize_project(self.root, "ProjectGovernorFixture.xcodeproj", "ProjectGovernorFixture",
                               None, "17.0", ["en"], "system", [], "inherit")
        self.project_path = self.root / ".governance/project.json"
        project = read_json(self.project_path)
        project["review_policy"]["transport"] = "in-session"
        project["commands"] = [{"id": "check", "kind": "test", "required": True,
                                "timeout_seconds": 30, "argv": [sys.executable, "-c", "print('check passed')"]}]
        write_json(self.project_path, project)
        recalibrate_project(self.root, True, None, None)
        self.no_cli = patch("project_governor.workflow.run_reviewer", side_effect=AssertionError("CLI must not run"))
        self.no_cli.start()
        self.addCleanup(self.no_cli.stop)

    def start(self, ui=False):
        prepare_change(self.root, "session-change", "Exercise handoff", ["Bound review"], "Domain",
                       "yes" if ui else "no", [], [], [], "novel")
        with patch("project_governor.workflow.run_ui_checks", return_value={"status": "pass", "runs": []}):
            result = verify_change(self.root, "session-change")
        self.run_id = result["run_id"]
        self.run_dir = self.root / ".governance/.runs" / self.run_id
        return result

    def response(self, role="architecture"):
        state = read_json(self.run_dir / "run.json")
        request = state["review_requests"][role]
        return {"request_id": request["request_id"], "bundle_digest": request["bundle_digest"],
                "evidence_digest": request["evidence_digest"], "review": {
                    "verdict": "pass", "reviewer": role, "candidate_digest": state["candidate_digest"],
                    "contract_digest": state["contract_digest"], "violations": [], "unverified": []}}

    def submit(self, response=None, role="architecture", agent="fresh-reviewer"):
        path = Path(self.temporary.name) / "response.json"
        write_json(path, response if response is not None else self.response(role))
        return submit_session_review(self.root, self.run_id, role, agent, path)

    def test_handoff_and_completion_update_every_result(self):
        pending = self.start()
        self.assertEqual(pending["verdict"], "pending")
        self.assertEqual(read_json(self.run_dir / "gate.json")["verdict"], "blocked")
        self.assertEqual(review_existing(self.root, self.run_id, "both")["verdict"], "pending")
        result = self.submit()
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(read_json(self.run_dir / "gate.json")["verdict"], "pass")
        self.assertEqual(read_json(self.root / ".governance/changes/session-change/result.json")["verdict"], "pass")
        self.assertEqual(session_status(self.root, self.run_id)["verdict"], "pass")
        self.assertEqual(read_json(self.run_dir / "reviews/architecture.receipt.json")["agent_id"], "fresh-reviewer")

    def test_ui_requires_two_distinct_reviewers(self):
        self.start(ui=True)
        self.assertEqual(self.submit()["verdict"], "pending")
        with self.assertRaisesRegex(GovernanceError, "separate fresh"):
            self.submit(role="ui")
        self.assertEqual(self.submit(role="ui", agent="fresh-ui")["verdict"], "pass")

    def test_bundle_does_not_expose_previous_reviews_or_governance_history(self):
        self.start(ui=True)
        state = read_json(self.run_dir / "run.json")
        for request in state["review_requests"].values():
            bundle = self.run_dir / request["bundle"]
            self.assertFalse((bundle / "candidate/.governance").exists())
            inputs = read_json(bundle / "inputs/run.json")
            self.assertNotIn("reviews", inputs)
            self.assertNotIn("review_receipts", inputs)
            self.assertNotIn("review_requests", inputs)
            self.assertEqual((bundle / "REVIEW_INSTRUCTIONS.md").stat().st_mode & 0o222, 0)

    def test_invalid_bindings_and_schema_are_rejected_without_accepting_review(self):
        self.start()
        mutations = [lambda r: r.update(request_id="old-request"),
                     lambda r: r.update(bundle_digest="0" * 64),
                     lambda r: r.update(evidence_digest="0" * 64),
                     lambda r: r["review"].update(candidate_digest="0" * 64),
                     lambda r: r["review"].update(contract_digest="0" * 64),
                     lambda r: r["review"].update(reviewer="ui"),
                     lambda r: r["review"].update(unapproved=True),
                     lambda r: r.update(unapproved=True)]
        for mutation in mutations:
            response = self.response()
            mutation(response)
            with self.subTest(response=response), self.assertRaises(GovernanceError):
                self.submit(response)
        self.assertEqual(read_json(self.run_dir / "run.json")["reviews"], {})

    def test_duplicate_submission_and_root_author_rejected(self):
        self.start()
        with self.assertRaisesRegex(GovernanceError, "fresh reviewer"):
            self.submit(agent="/root")
        self.submit()
        with self.assertRaisesRegex(GovernanceError, "already submitted"):
            self.submit()

    def test_candidate_drift_rejected(self):
        self.start()
        (self.root / "new-code.swift").write_text("// changed candidate")
        with self.assertRaisesRegex(GovernanceError, "Candidate changed"):
            self.submit()

    def test_evidence_drift_rejected(self):
        self.start()
        (self.run_dir / "evidence/injected.txt").write_text("changed evidence")
        with self.assertRaisesRegex(GovernanceError, "Evidence changed"):
            self.submit()

    def test_evidence_symlink_rejected_before_export_and_submission(self):
        self.start()
        target = Path(self.temporary.name) / "outside.txt"
        target.write_text("unbound outside evidence")
        (self.run_dir / "evidence/outside.txt").symlink_to(target)
        with self.assertRaisesRegex(GovernanceError, "symlinks"):
            self.submit()
        from project_governor.reviewer import _copy_tree_if_exists
        with self.assertRaisesRegex(GovernanceError, "symlinks"):
            _copy_tree_if_exists(self.run_dir / "evidence", Path(self.temporary.name) / "export")

    def test_contract_drift_rejected(self):
        self.start()
        (self.root / ".governance/contracts/architecture.md").write_text("changed contract")
        with self.assertRaisesRegex(GovernanceError, "Governance changed"):
            self.submit()

    def test_bundle_drift_and_symlink_rejected(self):
        self.start()
        request = read_json(self.run_dir / "run.json")["review_requests"]["architecture"]
        bundle = self.run_dir / request["bundle"]
        (bundle / "injected.txt").write_text("changed bundle")
        with self.assertRaisesRegex(GovernanceError, "bundle changed"):
            self.submit()
        (bundle / "injected.txt").unlink()
        (bundle / "injected.txt").symlink_to(self.root / ".governance/project.json")
        with self.assertRaisesRegex(GovernanceError, "symlinks"):
            self.submit()

    def test_superseded_run_rejected(self):
        self.start()
        result_path = self.root / ".governance/changes/session-change/result.json"
        result = read_json(result_path)
        result["run_id"] = "newer-run"
        write_json(result_path, result)
        with self.assertRaisesRegex(GovernanceError, "superseded"):
            self.submit()

    def test_real_failed_check_cannot_be_overruled_by_review(self):
        project = read_json(self.project_path)
        project["commands"][0]["argv"] = [sys.executable, "-c", "raise SystemExit(1)"]
        write_json(self.project_path, project)
        recalibrate_project(self.root, True, None, None)
        self.start()
        self.assertEqual(self.submit()["verdict"], "fail")

    def test_unverified_and_active_rule_violation_do_not_pass(self):
        self.start()
        response = self.response()
        response["review"].update(verdict="blocked", unverified=[{
            "claim": "Missing proof", "required_evidence": "Behavior test", "remediation": "Run the behavior test",
            "requires_user_decision": False}])
        self.assertEqual(self.submit(response)["verdict"], "blocked")

    def test_unknown_active_rule_rejected(self):
        self.start()
        response = self.response()
        response["review"].update(verdict="fail", violations=[{
            "rule_id": "invented", "state": "state", "observation": "observed", "conflict": "conflict",
            "evidence_refs": ["candidate/file"], "remediation": "fix", "requires_user_decision": False}])
        with self.assertRaisesRegex(GovernanceError, "not active"):
            self.submit(response)

    def test_run_context_cannot_remove_reviewers_or_rewrite_checks(self):
        self.start()
        path = self.run_dir / "run.json"
        original = read_json(path)
        for field, value in (("required_reviewers", []), ("automatic_checks", []),
                             ("candidate_stable", False), ("ui_required", True),
                             ("version_consistent", False)):
            modified = dict(original, **{field: value})
            write_json(path, modified)
            with self.subTest(field=field), self.assertRaisesRegex(GovernanceError, "Run context changed"):
                session_status(self.root, self.run_id)
        write_json(path, original)
        self.assertEqual(self.submit()["verdict"], "pass")

    def test_copied_run_identity_is_rejected(self):
        self.start()
        copied = self.run_dir.with_name(self.run_id + "-copy")
        shutil.copytree(self.run_dir, copied)
        with self.assertRaisesRegex(GovernanceError, "run identity"):
            session_status(self.root, copied.name)

    def test_stale_pending_state_cannot_revert_completed_result(self):
        self.start()
        original = read_json(self.run_dir / "run.json")
        self.submit()
        write_json(self.run_dir / "run.json", original)
        with self.assertRaisesRegex(GovernanceError, "replay stale state"):
            session_status(self.root, self.run_id)
        self.assertEqual(read_json(self.root / ".governance/changes/session-change/result.json")["verdict"], "pass")

    def test_runtime_drift_rejected(self):
        self.start()
        with patch("project_governor.session_review._runtime_digest", return_value="changed"):
            with self.assertRaisesRegex(GovernanceError, "runtime or rules changed"):
                self.submit()

    def test_accepted_receipt_drift_rejected(self):
        self.start(ui=True)
        self.submit()
        write_json(self.run_dir / "reviews/architecture.json", {"verdict": "pass"})
        with self.assertRaisesRegex(GovernanceError, "receipt changed"):
            self.submit(role="ui", agent="fresh-ui")

    def test_detached_saved_envelope_is_rejected(self):
        self.start(ui=True)
        self.submit()
        state = read_json(self.run_dir / "run.json")
        receipt = state["review_receipts"]["architecture"]
        receipt["response"]["request_id"] = "detached-request"
        write_json(self.run_dir / "run.json", state)
        write_json(self.run_dir / "reviews/architecture.receipt.json", receipt)
        with self.assertRaisesRegex(GovernanceError, "request_id mismatch"):
            session_status(self.root, self.run_id)

    def test_active_rule_failure_is_preserved(self):
        self.start()
        response = self.response()
        response["review"].update(verdict="fail", violations=[{
            "rule_id": "ARCH-001", "state": "Fixture state", "observation": "Test finding",
            "conflict": "Test ownership conflict", "evidence_refs": ["candidate/fixture"],
            "remediation": "Repair fixture ownership", "requires_user_decision": False}])
        self.assertEqual(self.submit(response)["verdict"], "fail")

    def test_cli_handoff_and_submit_exit_codes(self):
        prepare_change(self.root, "session-change", "Exercise CLI", ["Bound review"],
                       "Domain", "no", [], [], [], "novel")
        env = dict(os.environ, PROJECT_GOVERNOR_CODEX="/this-executable-must-never-run")
        command = [sys.executable, str(PLUGIN_ROOT / "scripts/governor.py")]
        handoff = subprocess.run(command + ["verify", "--project-root", str(self.root),
                                           "--change-id", "session-change"],
                                 capture_output=True, text=True, env=env)
        self.assertEqual(handoff.returncode, 0, handoff.stdout + handoff.stderr)
        pending = json.loads(handoff.stdout)
        self.assertEqual(pending["verdict"], "pending")
        self.run_id = pending["run_id"]
        self.run_dir = self.root / ".governance/.runs" / self.run_id
        response_path = Path(self.temporary.name) / "cli-response.json"
        write_json(response_path, self.response())
        accepted = subprocess.run(command + ["review-submit", "--project-root", str(self.root),
                                  "--run-id", self.run_id, "--reviewer", "architecture",
                                  "--agent-id", "cli-fresh-agent", "--response", str(response_path)],
                                  capture_output=True, text=True, env=env)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["verdict"], "pass")

    def test_concurrent_submissions_keep_both_reviews(self):
        self.start(ui=True)
        processes = []
        for role in ("architecture", "ui"):
            response_path = Path(self.temporary.name) / (role + ".json")
            write_json(response_path, self.response(role))
            processes.append(subprocess.Popen([
                sys.executable, str(PLUGIN_ROOT / "scripts/governor.py"), "review-submit",
                "--project-root", str(self.root), "--run-id", self.run_id,
                "--reviewer", role, "--agent-id", "fresh-" + role, "--response", str(response_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        state = read_json(self.run_dir / "run.json")
        self.assertEqual(set(state["reviews"]), {"architecture", "ui"})
        self.assertEqual(session_status(self.root, self.run_id)["verdict"], "pass")

    def test_path_traversal_rejected(self):
        self.start()
        with self.assertRaisesRegex(GovernanceError, "Invalid run ID"):
            session_status(self.root, "../../elsewhere")


if __name__ == "__main__":
    unittest.main()
