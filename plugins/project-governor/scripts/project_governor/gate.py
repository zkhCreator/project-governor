"""
Purpose: Produce the final deterministic Project Governor verdict.
Responsibilities: Check automatic results, evidence, reviewer verdicts, digest consistency, protected state, and candidate drift without scoring; surface actions for non-passing results.
Inputs/Outputs: One run-state mapping in; pass/fail/blocked result, resolution steps, and human-readable report out.
Non-goals: This module does not rerun checks, interpret aesthetics, or modify failed candidates.
Key Design Decisions: Blocking integrity/evidence problems take precedence; otherwise any failed required check or reviewer fails the run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .util import utc_now, write_text


def evaluate_gate(run_state: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate the all-conditions gate and return reasons."""

    blocked: List[str] = []
    failed: List[str] = []
    resolution_steps: List[Dict[str, Any]] = []

    def add_action(issue: str, action: str, requires_user_decision: bool = False) -> None:
        resolution_steps.append({
            "issue": issue,
            "action": action,
            "requires_user_decision": requires_user_decision,
        })

    if not run_state.get("candidate_stable", False):
        blocked.append("Candidate content changed during verification.")
        add_action("Candidate changed", "Freeze the current candidate and rerun all checks and reviews against one digest.")
    if not run_state.get("protected_state_stable", False):
        blocked.append("Protected governance state changed after prepare.")
        add_action("Governance changed", "Restore the approved governance state and rerun verification. If the new governance is intended, request a separate decision and prepare a new change.")
    if not run_state.get("version_consistent", False):
        blocked.append("Runtime, adapter, or rule-pack version does not match lock.json.")
        add_action("Version mismatch", "Use the plugin version recorded in lock.json, or separately recalibrate the governance lock.")
    if not run_state.get("evidence_stable", False):
        blocked.append("Evidence changed after it was bound to the run.")
        add_action("Evidence changed", "Rerun verification to bind fresh evidence to the candidate.")
    if run_state.get("pending_exceptions"):
        blocked.append("The change requests a governance exception that is not approved for this feature run.")
        add_action("Unapproved exception", "Revise the candidate to satisfy the current contract and rerun verification. If the exception is necessary, ask the user to decide on a separate governance change.")

    for check in run_state.get("automatic_checks", []):
        if not check.get("required", True):
            continue
        if check.get("status") == "blocked":
            blocked.append(f"Automatic check {check.get('id')} is blocked.")
            add_action(f"Check {check.get('id')} blocked", f"Inspect this check's evidence log, restore its required tool or runtime, and rerun verification.")
        elif check.get("status") != "pass":
            failed.append(f"Automatic check {check.get('id')} failed.")
            add_action(f"Check {check.get('id')} failed", "Inspect the check's failure log, correct the candidate, and rerun verification.")

    if run_state.get("ui_required"):
        ui_evidence = run_state.get("ui_evidence", {})
        if ui_evidence.get("status") == "blocked":
            blocked.append(str(ui_evidence.get("reason", "UI evidence is blocked.")))
            add_action("UI evidence blocked", f"Restore the required UI runtime or interaction evidence, then rerun verification. Reported cause: {ui_evidence.get('reason', 'unknown')}.")
        elif ui_evidence.get("status") != "pass":
            failed.append("Required UI evidence failed.")
            add_action("UI evidence failed", "Inspect the UI test logs and screenshots, correct the candidate or test setup, and rerun verification.")

    required_reviewers = run_state.get("required_reviewers", [])
    reviews = run_state.get("reviews", {})
    for reviewer in required_reviewers:
        review = reviews.get(reviewer)
        if not review:
            blocked.append(f"Missing required {reviewer} review.")
            add_action(f"Missing {reviewer} review", "Restore reviewer execution and rerun the independent review.")
            continue
        if review.get("candidate_digest") != run_state.get("candidate_digest"):
            blocked.append(f"{reviewer} review is bound to a different candidate.")
            add_action(f"{reviewer} candidate mismatch", "Rerun the independent review for the current frozen candidate.")
        if review.get("contract_digest") != run_state.get("contract_digest"):
            blocked.append(f"{reviewer} review is bound to a different contract.")
            add_action(f"{reviewer} contract mismatch", "Rerun the independent review against the approved current contract.")
        for item in review.get("violations", []):
            add_action(f"{reviewer} rule {item.get('rule_id', 'unknown')}", item.get("remediation", "Correct the cited rule violation and rerun verification."), bool(item.get("requires_user_decision", False)))
        for item in review.get("unverified", []):
            add_action(f"{reviewer} unverified: {item.get('claim', 'claim')}", item.get("remediation", f"Obtain the required evidence: {item.get('required_evidence', 'unspecified')}"), bool(item.get("requires_user_decision", False)))
        if review.get("unverified"):
            blocked.append(f"{reviewer} review has unverified claims.")
        if review.get("verdict") == "blocked":
            blocked.append(f"{reviewer} review is blocked.")
            if not review.get("unverified"):
                add_action(f"{reviewer} review blocked", "Inspect the reviewer logs and rerun the independent review.")
        elif review.get("verdict") == "fail":
            failed.append(f"{reviewer} review failed.")
        elif review.get("verdict") != "pass":
            blocked.append(f"{reviewer} review has an invalid verdict.")
            add_action(f"{reviewer} invalid review", "Inspect reviewer output and rerun the independent review with the required schema.")

    verdict = "blocked" if blocked else "fail" if failed else "pass"
    return {
        "verdict": verdict,
        "blocked_reasons": blocked,
        "failure_reasons": failed,
        "resolution_steps": resolution_steps,
        "evaluated_at": utc_now(),
    }


def write_report(path: Path, run_state: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    """Write a concise Markdown gate report."""

    lines = [
        f"# Project Governor Run {run_state.get('run_id', '')}",
        "",
        f"- Change: `{run_state.get('change_id', '')}`",
        f"- Verdict: **{result.get('verdict', 'blocked')}**",
        f"- Candidate: `{run_state.get('candidate_digest', '')}`",
        f"- Contract: `{run_state.get('contract_digest', '')}`",
        "",
        "## Automatic checks",
        "",
    ]
    for check in run_state.get("automatic_checks", []):
        lines.append(f"- `{check.get('id')}`: {check.get('status')}")
    if run_state.get("ui_required"):
        lines.extend(["", "## UI evidence", "", f"- Status: {run_state.get('ui_evidence', {}).get('status')}"])
    lines.extend(["", "## Reviews", ""])
    for reviewer in run_state.get("required_reviewers", []):
        review = run_state.get("reviews", {}).get(reviewer, {})
        lines.append(f"- `{reviewer}`: {review.get('verdict', 'missing')}")
    if result.get("blocked_reasons"):
        lines.extend(["", "## Blocked", ""])
        lines.extend(f"- {reason}" for reason in result["blocked_reasons"])
    if result.get("failure_reasons"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {reason}" for reason in result["failure_reasons"])
    if result.get("resolution_steps"):
        lines.extend(["", "## Resolution steps", ""])
        for step in result["resolution_steps"]:
            decision = " (user decision required)" if step["requires_user_decision"] else ""
            lines.append(f"- **{step['issue']}**: {step['action']}{decision}")
    lines.append("")
    write_text(path, "\n".join(lines))
