"""
Purpose: Produce the final deterministic Project Governor verdict.
Responsibilities: Check automatic results, evidence, reviewer verdicts, digest consistency, protected state, and candidate drift without scoring.
Inputs/Outputs: One run-state mapping in; pass/fail/blocked result and human-readable report out.
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
    if not run_state.get("candidate_stable", False):
        blocked.append("Candidate content changed during verification.")
    if not run_state.get("protected_state_stable", False):
        blocked.append("Protected governance state changed after prepare.")
    if not run_state.get("version_consistent", False):
        blocked.append("Runtime, adapter, or rule-pack version does not match lock.json.")
    if not run_state.get("evidence_stable", False):
        blocked.append("Evidence changed after it was bound to the run.")
    if run_state.get("pending_exceptions"):
        blocked.append("The change requests a governance exception that is not approved for this feature run.")

    for check in run_state.get("automatic_checks", []):
        if not check.get("required", True):
            continue
        if check.get("status") == "blocked":
            blocked.append(f"Automatic check {check.get('id')} is blocked.")
        elif check.get("status") != "pass":
            failed.append(f"Automatic check {check.get('id')} failed.")

    if run_state.get("ui_required"):
        ui_evidence = run_state.get("ui_evidence", {})
        if ui_evidence.get("status") == "blocked":
            blocked.append(str(ui_evidence.get("reason", "UI evidence is blocked.")))
        elif ui_evidence.get("status") != "pass":
            failed.append("Required UI evidence failed.")

    required_reviewers = run_state.get("required_reviewers", [])
    reviews = run_state.get("reviews", {})
    for reviewer in required_reviewers:
        review = reviews.get(reviewer)
        if not review:
            blocked.append(f"Missing required {reviewer} review.")
            continue
        if review.get("candidate_digest") != run_state.get("candidate_digest"):
            blocked.append(f"{reviewer} review is bound to a different candidate.")
        if review.get("contract_digest") != run_state.get("contract_digest"):
            blocked.append(f"{reviewer} review is bound to a different contract.")
        if review.get("unverified"):
            blocked.append(f"{reviewer} review has unverified claims.")
        if review.get("verdict") == "blocked":
            blocked.append(f"{reviewer} review is blocked.")
        elif review.get("verdict") == "fail":
            failed.append(f"{reviewer} review failed.")
        elif review.get("verdict") != "pass":
            blocked.append(f"{reviewer} review has an invalid verdict.")

    verdict = "blocked" if blocked else "fail" if failed else "pass"
    return {
        "verdict": verdict,
        "blocked_reasons": blocked,
        "failure_reasons": failed,
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
    lines.append("")
    write_text(path, "\n".join(lines))
