"""
Purpose: Orchestrate complete Project Governor verify and review runs.
Responsibilities: Bind candidates/contracts/evidence, execute checks, run isolated reviewers, apply the deterministic gate, and persist traceable results.
Inputs/Outputs: A prepared change or existing run in; `.governance/.runs` artifacts and `changes/<id>/result.json` out.
Non-goals: This module does not implement product changes or automatically approve governance exceptions.
Key Design Decisions: Initial verification plus at most two revisions are allowed; every revision reruns all required checks and reviewers.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from . import VERSION
from .checks import run_automatic_checks, run_ui_checks
from .errors import GovernanceError
from .gate import evaluate_gate, write_report
from .ios import navigation_impact, ui_impact
from .reviewer import run_reviewer
from .snapshot import build_manifest, changed_paths, governance_digest
from .state import governance_root, load_lock, load_project
from .util import canonical_json, read_json, sha256_bytes, sha256_file, utc_now, write_json
from .validation import validate_ledger, validate_spec


def plugin_root() -> Path:
    """Resolve the installed plugin root from this runtime module."""

    return Path(__file__).resolve().parents[2]


def _directory_manifest(root: Path) -> Dict[str, Any]:
    entries = []
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    return {"algorithm": "sha256", "digest": sha256_bytes(canonical_json(entries)), "files": entries}


def _version_consistent(project: Mapping[str, Any], lock: Mapping[str, Any]) -> bool:
    return bool(
        lock.get("plugin", {}).get("version") == VERSION
        and lock.get("runtime", {}).get("version") == VERSION
        and lock.get("adapter", {}).get("name") == "ios-swiftui"
        and lock.get("adapter", {}).get("version") == VERSION
        and lock.get("rule_packs") == project.get("rule_packs")
    )


def _load_change(root: Path, change_id: str) -> tuple:
    change_root = governance_root(root) / "changes" / change_id
    if not change_root.is_dir():
        raise GovernanceError("blocked", "Prepared change does not exist", {"change_id": change_id})
    spec = validate_spec(read_json(change_root / "spec.json"))
    ledger = validate_ledger(read_json(change_root / "ledger.json"))
    result_path = change_root / "result.json"
    previous = read_json(result_path) if result_path.is_file() else {}
    return change_root, spec, ledger, previous


def _synthetic_blocked_review(
    reviewer: str,
    candidate_digest: str,
    contract_digest: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "verdict": "blocked",
        "reviewer": reviewer,
        "candidate_digest": candidate_digest,
        "contract_digest": contract_digest,
        "violations": [],
        "unverified": [{"claim": f"{reviewer} review could not complete", "required_evidence": message}],
    }


def _run_required_reviewers(
    root: Path,
    run_dir: Path,
    run_state: Dict[str, Any],
    manifest: Dict[str, Any],
    lock: Mapping[str, Any],
    only: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    selected = set(only or run_state["required_reviewers"])
    reviews = dict(run_state.get("reviews", {}))
    model = str(lock.get("reviewer", {}).get("model", "inherit"))
    timeout = int(run_state.get("reviewer_timeout_seconds", 900))
    for reviewer in run_state["required_reviewers"]:
        if reviewer not in selected:
            continue
        try:
            reviews[reviewer] = run_reviewer(
                root,
                plugin_root(),
                run_dir,
                run_state,
                manifest,
                reviewer,
                model,
                timeout,
            )
        except GovernanceError as exc:
            blocked = _synthetic_blocked_review(
                reviewer,
                run_state["candidate_digest"],
                run_state["contract_digest"],
                exc.message,
            )
            write_json(run_dir / "reviews" / f"{reviewer}.json", blocked)
            reviews[reviewer] = blocked
    return reviews


def verify_change(root: Path, change_id: str) -> Dict[str, Any]:
    """Run the complete gate for a newly frozen candidate."""

    project = load_project(root)
    lock = load_lock(root)
    change_root, spec, ledger, previous = _load_change(root, change_id)
    maximum_revisions = int(project.get("review_policy", {}).get("maximum_revision_rounds", 2))
    attempt = int(previous.get("attempt", 0)) + 1
    if attempt > maximum_revisions + 1:
        raise GovernanceError(
            "blocked",
            "The change exceeded the configured revision limit",
            {"maximum_revision_rounds": maximum_revisions},
        )

    manifest = build_manifest(root)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_id = f"{change_id}-{timestamp}-{manifest['digest'][:12]}"
    run_dir = governance_root(root) / ".runs" / run_id
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "candidate-manifest.json", manifest)

    changed = changed_paths(root)
    requires_ui = ui_impact(changed, spec["ui_impact"], root)
    navigation_changed = navigation_impact(changed, root)
    automatic_checks = run_automatic_checks(root, project.get("commands", []), evidence_dir)
    ui_evidence = (
        run_ui_checks(root, project, evidence_dir, navigation_changed)
        if requires_ui
        else {"status": "not_required", "runs": []}
    )
    evidence_manifest = _directory_manifest(evidence_dir)
    write_json(run_dir / "evidence-manifest.json", evidence_manifest)

    current_contract_digest = governance_digest(root)
    run_state: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "change_id": change_id,
        "attempt": attempt,
        "created_at": utc_now(),
        "candidate_digest": manifest["digest"],
        "contract_digest": current_contract_digest,
        "evidence_digest": evidence_manifest["digest"],
        "changed_paths": changed,
        "ui_required": requires_ui,
        "navigation_changed": navigation_changed,
        "required_reviewers": ["architecture"] + (["ui"] if requires_ui else []),
        "automatic_checks": automatic_checks,
        "ui_evidence": ui_evidence,
        "candidate_stable": False,
        "protected_state_stable": current_contract_digest == spec["baseline_governance_digest"],
        "version_consistent": _version_consistent(project, lock),
        "evidence_stable": True,
        "pending_exceptions": ledger["exception_requests"],
        "reviewer_timeout_seconds": int(project.get("review_policy", {}).get("reviewer_timeout_seconds", 900)),
        "reviews": {},
    }
    write_json(run_dir / "run.json", run_state)
    run_state["reviews"] = _run_required_reviewers(root, run_dir, run_state, manifest, lock)
    final_manifest = build_manifest(root)
    run_state["candidate_stable"] = final_manifest["digest"] == manifest["digest"]
    run_state["ending_candidate_digest"] = final_manifest["digest"]
    ending_evidence = _directory_manifest(evidence_dir)
    run_state["evidence_stable"] = ending_evidence["digest"] == evidence_manifest["digest"]
    write_json(run_dir / "run.json", run_state)

    gate = evaluate_gate(run_state)
    write_json(run_dir / "gate.json", gate)
    write_report(run_dir / "report.md", run_state, gate)
    result = {
        "change_id": change_id,
        "run_id": run_id,
        "attempt": attempt,
        "verdict": gate["verdict"],
        "candidate_digest": manifest["digest"],
        "contract_digest": current_contract_digest,
        "evidence_digest": evidence_manifest["digest"],
        "required_reviewers": run_state["required_reviewers"],
        "review_verdicts": {
            key: value.get("verdict") for key, value in run_state["reviews"].items()
        },
        "blocked_reasons": gate["blocked_reasons"],
        "failure_reasons": gate["failure_reasons"],
        "completed_at": utc_now(),
    }
    write_json(change_root / "result.json", result)
    return result


def _latest_run(root: Path) -> str:
    runs = governance_root(root) / ".runs"
    candidates = sorted(path.name for path in runs.iterdir() if path.is_dir()) if runs.exists() else []
    if not candidates:
        raise GovernanceError("blocked", "No Project Governor run exists")
    return candidates[-1]


def review_existing(
    root: Path,
    run_id: Optional[str],
    reviewer: str,
) -> Dict[str, Any]:
    """Rerun one or all required reviewers against a still-current candidate."""

    load_project(root)
    lock = load_lock(root)
    selected_run = run_id or _latest_run(root)
    run_dir = governance_root(root) / ".runs" / selected_run
    if not run_dir.is_dir():
        raise GovernanceError("blocked", "Requested run does not exist", {"run_id": selected_run})
    run_state = read_json(run_dir / "run.json")
    manifest = read_json(run_dir / "candidate-manifest.json")
    current_manifest = build_manifest(root)
    if current_manifest["digest"] != manifest["digest"]:
        raise GovernanceError("blocked", "The project no longer matches the frozen candidate")
    if governance_digest(root) != run_state["contract_digest"]:
        raise GovernanceError("blocked", "The governance contract changed after the run")
    requested = run_state["required_reviewers"] if reviewer == "both" else [reviewer]
    unavailable = sorted(set(requested) - set(run_state["required_reviewers"]))
    if unavailable:
        raise GovernanceError("error", "Reviewer was not required for this run", {"reviewers": unavailable})
    run_state["reviews"] = _run_required_reviewers(
        root, run_dir, run_state, manifest, lock, only=requested
    )
    evidence_manifest = read_json(run_dir / "evidence-manifest.json")
    run_state["candidate_stable"] = True
    run_state["protected_state_stable"] = True
    run_state["evidence_stable"] = (
        _directory_manifest(run_dir / "evidence")["digest"] == evidence_manifest["digest"]
    )
    write_json(run_dir / "run.json", run_state)
    gate = evaluate_gate(run_state)
    write_json(run_dir / "gate.json", gate)
    write_report(run_dir / "report.md", run_state, gate)
    return {
        "run_id": selected_run,
        "verdict": gate["verdict"],
        "review_verdicts": {
            key: value.get("verdict") for key, value in run_state["reviews"].items()
        },
        "blocked_reasons": gate["blocked_reasons"],
        "failure_reasons": gate["failure_reasons"],
    }
