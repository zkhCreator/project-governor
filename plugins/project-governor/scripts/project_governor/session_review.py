"""
Purpose: Complete formal Governor review with fresh in-session subagents.
Responsibilities: Export whitelisted snapshots, bind requests to evidence, validate
responses and provenance, and finalize the unchanged deterministic gate.
Inputs/Outputs: A checked frozen run in; durable requests, review receipts and verdict out.
Non-goals: Does not spawn agents, author their verdicts, bypass checks, or fall back to CLI.
Key Design Decisions: The host spawns without history and relays the exact response.
Bundles are separate read-only files with integrity checks, not an OS security boundary;
agent identity is host-attested provenance, not cryptographic proof of authorship.
"""
from __future__ import annotations

import re
import fcntl
from functools import wraps
import uuid
from pathlib import Path
from typing import Any, Dict

from .errors import GovernanceError
from .gate import evaluate_gate, write_report
from .reviewer import create_review_bundle, load_active_rules
from .snapshot import build_manifest, governance_digest
from .state import governance_root, load_lock, load_project
from .util import read_json, utc_now, write_json
from .validation import validate_review


def _run_dir(root: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9A-Z-]*", run_id):
        raise GovernanceError("blocked", "Invalid run ID")
    path = governance_root(root) / ".runs" / run_id
    if path.is_symlink():
        raise GovernanceError("blocked", "Run directory aliases are not supported")
    if not (path / "run.json").is_file():
        raise GovernanceError("blocked", "Requested run does not exist")
    return path


def _serialized(operation):
    """Serialize independent host submissions/status writes for one run."""
    @wraps(operation)
    def locked(root, run_id, *args, **kwargs):
        run_dir = _run_dir(root, run_id)
        with (run_dir / ".session.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                return operation(root, run_id, *args, **kwargs)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    return locked


def _bundle_digest(bundle: Path) -> str:
    from .workflow import _directory_manifest
    if not bundle.is_dir() or any(p.is_symlink() for p in bundle.rglob("*")):
        raise GovernanceError("blocked", "Review bundle is missing or contains symlinks")
    return _directory_manifest(bundle)["digest"]


def _assert_current(root: Path, run_dir: Path, state: Dict[str, Any]) -> None:
    from .workflow import _directory_manifest, _version_consistent, plugin_root
    if state.get("run_id") != run_dir.name:
        raise GovernanceError("blocked", "Requested run identity does not match its directory")
    context = read_json(run_dir / "session-context.json")
    current_context = {k: v for k, v in state.items() if k not in {"reviews", "review_receipts"}}
    if context != current_context:
        raise GovernanceError("blocked", "Run context changed; rerun verification")
    project, lock = load_project(root), load_lock(root)
    if state.get("review_transport") != "in-session" or project["review_policy"].get("transport") != "in-session":
        raise GovernanceError("blocked", "Run is not configured for in-session review")
    if not state.get("protected_state_stable") or governance_digest(root) != state["contract_digest"]:
        raise GovernanceError("blocked", "Governance changed; prepare and verify a new candidate")
    if lock.get("governance_digest") != state["contract_digest"] or not _version_consistent(project, lock):
        raise GovernanceError("blocked", "Governance lock or runtime does not match this run")
    if build_manifest(root)["digest"] != state["candidate_digest"]:
        raise GovernanceError("blocked", "Candidate changed; rerun all checks and reviews")
    if _directory_manifest(run_dir / "evidence")["digest"] != state["evidence_digest"]:
        raise GovernanceError("blocked", "Evidence changed; rerun all checks and reviews")
    # Bind active rules/schema/runtime as well as project-owned contracts.
    if _runtime_digest(plugin_root()) != state["review_runtime_digest"]:
        raise GovernanceError("blocked", "Reviewer runtime or rules changed; rerun verification")
    if set(state["review_requests"]) != set(state["required_reviewers"]):
        raise GovernanceError("blocked", "Review request roles do not match required reviewers")
    for role, request in state.get("review_requests", {}).items():
        if _bundle_digest(run_dir / request["bundle"]) != request["bundle_digest"]:
            raise GovernanceError("blocked", f"{role} review bundle changed; rerun verification")
        bundled = read_json(run_dir / request["bundle"] / "REQUEST.json")
        if (bundled.get("run_id") != state["run_id"] or bundled.get("reviewer") != role
                or bundled.get("request_id") != request["request_id"]
                or request.get("evidence_digest") != state["evidence_digest"]
                or bundled.get("evidence_digest") != state["evidence_digest"]):
            raise GovernanceError("blocked", "Bundled request does not match the run")
    if (not set(state["reviews"]).issubset(state["required_reviewers"])
            or set(state["reviews"]) != set(state["review_receipts"])):
        raise GovernanceError("blocked", "Accepted review roles do not match their receipts")
    agents = [r.get("agent_id") for r in state["review_receipts"].values()]
    if any(not isinstance(a, str) or not a.strip() or a in {"root", "/root"} for a in agents) or len(set(agents)) != len(agents):
        raise GovernanceError("blocked", "Accepted reviews require distinct fresh agent identities")
    for role, review in state.get("reviews", {}).items():
        request = state["review_requests"].get(role, {})
        receipt = state.get("review_receipts", {}).get(role, {})
        if (receipt.get("response", {}).get("review") != review
                or any(receipt.get(key) != request.get(key) for key in ("request_id", "bundle_digest", "evidence_digest"))
                or read_json(run_dir / "reviews" / f"{role}.json") != review
                or read_json(run_dir / "reviews" / f"{role}.receipt.json") != receipt):
            raise GovernanceError("blocked", "Accepted review or receipt changed; rerun verification")
        _validate_envelope(receipt.get("response"), request)
        _, rules = load_active_rules(plugin_root(), role)
        validate_review(review, role, state["candidate_digest"], state["contract_digest"], rules)
    result = read_json(governance_root(root) / "changes" / state["change_id"] / "result.json")
    if result.get("run_id") != state["run_id"]:
        raise GovernanceError("blocked", "Review belongs to a superseded run")
    awaiting = set(state["required_reviewers"]) - set(state["reviews"])
    expected = {
        "candidate_digest": state["candidate_digest"], "contract_digest": state["contract_digest"],
        "evidence_digest": state["evidence_digest"], "attempt": state["attempt"],
        "required_reviewers": state["required_reviewers"], "change_id": state["change_id"],
        "review_verdicts": {k: v["verdict"] for k, v in state["reviews"].items()},
        "phase": "awaiting_review" if awaiting else "complete",
        "verdict": "pending" if awaiting else evaluate_gate(state)["verdict"],
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise GovernanceError("blocked", "Run and change result disagree; do not replay stale state")


def _validate_envelope(envelope: Any, request: Dict[str, Any]) -> None:
    if not isinstance(envelope, dict) or set(envelope) != {"request_id", "bundle_digest", "evidence_digest", "review"}:
        raise GovernanceError("blocked", "Invalid review response envelope")
    for key in ("request_id", "bundle_digest", "evidence_digest"):
        if envelope[key] != request[key]:
            raise GovernanceError("blocked", f"Review response {key} mismatch")


def _runtime_digest(plugin: Path) -> str:
    from .util import canonical_json, sha256_bytes, sha256_file
    files = []
    for directory in ("scripts", "rules", "schemas", "skills"):
        for path in sorted((plugin / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files.append({"path": path.relative_to(plugin).as_posix(), "sha256": sha256_file(path)})
    return sha256_bytes(canonical_json(files))


def _persist(root: Path, run_dir: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the run, gate, report and change result on the same verdict."""
    gate = evaluate_gate(state)
    awaiting = [role for role in state["required_reviewers"] if role not in state["reviews"]]
    # Pending is a handoff state; gate.json remains blocked until every review exists.
    verdict = "pending" if awaiting else gate["verdict"]
    write_json(run_dir / "run.json", state)
    write_json(run_dir / "gate.json", gate)
    write_report(run_dir / "report.md", state, gate)
    result = {
        "change_id": state["change_id"], "run_id": state["run_id"],
        "attempt": state["attempt"], "verdict": verdict,
        "phase": "awaiting_review" if awaiting else "complete",
        "candidate_digest": state["candidate_digest"], "contract_digest": state["contract_digest"],
        "evidence_digest": state["evidence_digest"], "required_reviewers": state["required_reviewers"],
        "review_transport": "in-session",
        "review_verdicts": {k: v["verdict"] for k, v in state["reviews"].items()},
        "review_requests": [dict(state["review_requests"][role], reviewer=role,
                                 bundle_path=str(run_dir / state["review_requests"][role]["bundle"]))
                            for role in awaiting],
        "blocked_reasons": gate["blocked_reasons"], "failure_reasons": gate["failure_reasons"],
        "resolution_steps": gate["resolution_steps"], "updated_at": utc_now(),
    }
    if not awaiting:
        result["completed_at"] = utc_now()
    write_json(governance_root(root) / "changes" / state["change_id"] / "result.json", result)
    return result


def start_session_review(root: Path, run_dir: Path, state: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    from .workflow import _directory_manifest, plugin_root
    state["candidate_stable"] = build_manifest(root)["digest"] == state["candidate_digest"]
    state["evidence_stable"] = _directory_manifest(run_dir / "evidence")["digest"] == state["evidence_digest"]
    state["review_runtime_digest"] = _runtime_digest(plugin_root())
    state["review_requests"] = {}
    state["review_receipts"] = {}
    # Export no stale source under a fresh digest.
    if not state["candidate_stable"] or not state["evidence_stable"] or not state["protected_state_stable"]:
        raise GovernanceError("blocked", "Candidate, evidence or contract changed during checks; rerun verification")
    for role in state["required_reviewers"]:
        request_id = uuid.uuid4().hex
        relative = f"requests/{role}/{request_id}/bundle"
        bundle = run_dir / relative
        bundle.mkdir(parents=True, exist_ok=False)
        # Reviewers see check results but never other reviewers' identities or results.
        clean_state = {k: v for k, v in state.items() if k not in {"review_requests", "review_receipts", "reviews"}}
        create_review_bundle(root, plugin_root(), run_dir, clean_state, manifest, role, bundle)
        write_json(bundle / "REQUEST.json", {
            "request_id": request_id, "run_id": state["run_id"], "reviewer": role,
            "evidence_digest": state["evidence_digest"],
            "response_format": {"request_id": request_id, "bundle_digest": "Use handoff bundle_digest",
                                "evidence_digest": state["evidence_digest"], "review": "Object matching review-output.schema.json"},
        })
        digest = _bundle_digest(bundle)
        for path in bundle.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        state["review_requests"][role] = {
            "request_id": request_id, "bundle": relative, "bundle_digest": digest,
            "evidence_digest": state["evidence_digest"],
            "instructions": "Spawn a fresh subagent with fork_turns=none. Read only this bundle, starting with REVIEW_INSTRUCTIONS.md and REQUEST.json. Return the response envelope with the supplied bundle_digest and strict review object. Do not edit files. Parent relays exact output with review-submit --agent-id; never authors or amends a verdict.",
        }
    context_path = run_dir / "session-context.json"
    write_json(context_path, {k: v for k, v in state.items() if k not in {"reviews", "review_receipts"}})
    context_path.chmod(0o444)
    result = _persist(root, run_dir, state)
    _assert_current(root, run_dir, state)
    return result


@_serialized
def session_status(root: Path, run_id: str) -> Dict[str, Any]:
    run_dir = _run_dir(root, run_id)
    state = read_json(run_dir / "run.json")
    _assert_current(root, run_dir, state)
    return _persist(root, run_dir, state)


@_serialized
def submit_session_review(root: Path, run_id: str, reviewer: str, agent_id: str, response_path: Path) -> Dict[str, Any]:
    from .workflow import plugin_root
    run_dir = _run_dir(root, run_id)
    state = read_json(run_dir / "run.json")
    _assert_current(root, run_dir, state)
    if reviewer not in state["required_reviewers"]:
        raise GovernanceError("blocked", "Reviewer was not requested")
    if reviewer in state["reviews"]:
        raise GovernanceError("blocked", "Review already submitted; use a new verification run after fixes")
    if not agent_id.strip() or agent_id in {"root", "/root"}:
        raise GovernanceError("blocked", "A fresh reviewer agent ID is required")
    if any(receipt["agent_id"] == agent_id for receipt in state["review_receipts"].values()):
        raise GovernanceError("blocked", "Each reviewer requires a separate fresh subagent")
    envelope = read_json(response_path)
    request = state["review_requests"][reviewer]
    _validate_envelope(envelope, request)
    _, rules = load_active_rules(plugin_root(), reviewer)
    review = validate_review(envelope["review"], reviewer, state["candidate_digest"], state["contract_digest"], rules)
    _assert_current(root, run_dir, state)
    receipt = {"agent_id": agent_id, "request_id": request["request_id"],
               "bundle_digest": request["bundle_digest"], "evidence_digest": request["evidence_digest"],
               "received_at": utc_now(), "response": envelope}
    state["reviews"][reviewer] = review
    state["review_receipts"][reviewer] = receipt
    write_json(run_dir / "reviews" / f"{reviewer}.json", review)
    write_json(run_dir / "reviews" / f"{reviewer}.receipt.json", receipt)
    return _persist(root, run_dir, state)
