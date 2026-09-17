"""
Purpose: Enforce the narrow data contracts used by Project Governor.
Responsibilities: Validate project config, change specs, ledgers, decisions, and reviewer output without third-party packages.
Inputs/Outputs: Parsed JSON mappings in; normalized mappings or GovernanceError out.
Non-goals: This module is not a general JSON Schema implementation.
Key Design Decisions: Unknown fields are rejected for reviewer output so it cannot smuggle design advice into the loop.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping, Sequence, Set

from .errors import GovernanceError


REVIEW_KEYS = {
    "verdict",
    "reviewer",
    "candidate_digest",
    "contract_digest",
    "violations",
    "unverified",
}
VIOLATION_KEYS = {"rule_id", "state", "observation", "conflict", "evidence_refs"}
UNVERIFIED_KEYS = {"claim", "required_evidence"}
LEDGER_KEYS = {
    "schema_version",
    "reused_structures",
    "new_concepts",
    "new_entries",
    "new_interaction_patterns",
    "replaced_or_removed",
    "affected_existing_tasks",
    "exception_requests",
    "file_comment_assumptions",
}


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GovernanceError("error", f"{label} must be a JSON object")
    return value


def _require_keys(value: Mapping[str, Any], required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(value))
    if missing:
        raise GovernanceError("error", f"{label} is missing required fields", {"missing": missing})


def _reject_extra(value: Mapping[str, Any], allowed: Iterable[str], label: str) -> None:
    extra = sorted(set(value) - set(allowed))
    if extra:
        raise GovernanceError("blocked", f"{label} contains unsupported fields", {"extra": extra})


def _string_list(value: Any, label: str, allow_empty: bool = True) -> Sequence[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise GovernanceError("error", f"{label} must be an array of strings")
    if not allow_empty and not value:
        raise GovernanceError("error", f"{label} must not be empty")
    return value


def validate_project(value: Any) -> Dict[str, Any]:
    """Validate the stable fields consumed by the runtime."""

    project = dict(_require_mapping(value, "project.json"))
    required = {
        "schema_version",
        "project_id",
        "adapter",
        "ios",
        "commands",
        "ui_scenarios",
        "review_policy",
        "protected_paths",
        "rule_packs",
    }
    _require_keys(project, required, "project.json")
    if project["schema_version"] != 1 or project["adapter"] != "ios-swiftui":
        raise GovernanceError("error", "Unsupported project schema or adapter")
    if not isinstance(project["project_id"], str) or not project["project_id"].strip():
        raise GovernanceError("error", "project_id must be a non-empty string")
    if not isinstance(project["commands"], list) or not isinstance(project["ui_scenarios"], list):
        raise GovernanceError("error", "commands and ui_scenarios must be arrays")
    if not isinstance(project["review_policy"], dict) or not isinstance(project["ios"], dict):
        raise GovernanceError("error", "review_policy and ios must be objects")
    _string_list(project["protected_paths"], "protected_paths")
    _string_list(project["rule_packs"], "rule_packs", allow_empty=False)
    return project


def validate_spec(value: Any) -> Dict[str, Any]:
    """Validate a prepared feature-change specification."""

    spec = dict(_require_mapping(value, "spec.json"))
    required = {
        "schema_version",
        "change_id",
        "goal",
        "acceptance",
        "module",
        "ui_impact",
        "ui_states",
        "scope",
        "non_goals",
        "baseline_governance_digest",
    }
    _require_keys(spec, required, "spec.json")
    _reject_extra(spec, required, "spec.json")
    if spec["schema_version"] != 1:
        raise GovernanceError("error", "Unsupported spec schema")
    if not isinstance(spec["change_id"], str) or not re.match(r"^[a-z0-9][a-z0-9-]*$", spec["change_id"]):
        raise GovernanceError("error", "change_id must be lowercase hyphen-case")
    for field in ("goal", "module", "baseline_governance_digest"):
        if not isinstance(spec[field], str) or not spec[field]:
            raise GovernanceError("error", f"{field} must be a non-empty string")
    if len(spec["baseline_governance_digest"]) != 64:
        raise GovernanceError("error", "baseline_governance_digest must be a SHA-256 digest")
    _string_list(spec["acceptance"], "acceptance", allow_empty=False)
    for field in ("ui_states", "scope", "non_goals"):
        _string_list(spec[field], field)
    if spec["ui_impact"] not in {"auto", "yes", "no"}:
        raise GovernanceError("error", "ui_impact must be auto, yes, or no")
    return spec


def validate_ledger(value: Any) -> Dict[str, Any]:
    """Validate the factual change ledger."""

    ledger = dict(_require_mapping(value, "ledger.json"))
    _require_keys(ledger, LEDGER_KEYS, "ledger.json")
    _reject_extra(ledger, LEDGER_KEYS, "ledger.json")
    if ledger["schema_version"] != 1:
        raise GovernanceError("error", "Unsupported ledger schema")
    for field in LEDGER_KEYS - {"schema_version"}:
        _string_list(ledger[field], field)
    return ledger


def validate_decision(value: Any) -> Dict[str, Any]:
    """Validate a separately approved governance decision."""

    decision = dict(_require_mapping(value, "decision"))
    required = {"id", "summary", "status", "rationale", "exceptions"}
    _require_keys(decision, required, "decision")
    _reject_extra(decision, required | {"approved_at", "expires_at"}, "decision")
    if decision["status"] != "approved":
        raise GovernanceError("blocked", "Only approved decisions can be installed")
    for field in ("id", "summary", "rationale"):
        if not isinstance(decision[field], str) or not decision[field].strip():
            raise GovernanceError("error", f"decision.{field} must be non-empty")
    _string_list(decision["exceptions"], "decision.exceptions", allow_empty=False)
    return decision


def validate_review(
    value: Any,
    expected_reviewer: str,
    candidate_digest: str,
    contract_digest: str,
    allowed_rule_ids: Set[str],
) -> Dict[str, Any]:
    """Validate strict reviewer output and bind it to the current candidate."""

    review = dict(_require_mapping(value, "review output"))
    _require_keys(review, REVIEW_KEYS, "review output")
    _reject_extra(review, REVIEW_KEYS, "review output")
    if review["verdict"] not in {"pass", "fail", "blocked"}:
        raise GovernanceError("blocked", "Reviewer returned an invalid verdict")
    if review["reviewer"] != expected_reviewer:
        raise GovernanceError("blocked", "Reviewer identity does not match the requested review")
    if review["candidate_digest"] != candidate_digest or review["contract_digest"] != contract_digest:
        raise GovernanceError("blocked", "Reviewer output is bound to a different candidate or contract")
    if not isinstance(review["violations"], list) or not isinstance(review["unverified"], list):
        raise GovernanceError("blocked", "Reviewer lists must be arrays")
    for violation in review["violations"]:
        item = _require_mapping(violation, "violation")
        _require_keys(item, VIOLATION_KEYS, "violation")
        _reject_extra(item, VIOLATION_KEYS, "violation")
        if item["rule_id"] not in allowed_rule_ids:
            raise GovernanceError("blocked", "Reviewer cited a rule that is not active", {"rule_id": item["rule_id"]})
        for field in ("state", "observation", "conflict"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise GovernanceError("blocked", f"violation.{field} must be non-empty")
        _string_list(item["evidence_refs"], "violation.evidence_refs", allow_empty=False)
    for unverified in review["unverified"]:
        item = _require_mapping(unverified, "unverified")
        _require_keys(item, UNVERIFIED_KEYS, "unverified")
        _reject_extra(item, UNVERIFIED_KEYS, "unverified")
        for field in UNVERIFIED_KEYS:
            if not isinstance(item[field], str) or not item[field].strip():
                raise GovernanceError("blocked", f"unverified.{field} must be non-empty")
    if review["verdict"] == "pass" and (review["violations"] or review["unverified"]):
        raise GovernanceError("blocked", "A passing review cannot contain violations or unverified claims")
    if review["verdict"] == "fail" and not review["violations"]:
        raise GovernanceError("blocked", "A failing review must contain a violation")
    if review["verdict"] == "blocked" and not review["unverified"]:
        raise GovernanceError("blocked", "A blocked review must identify missing evidence")
    return review
