"""
Purpose: Create and evolve the project-owned `.governance` state.
Responsibilities: Initialize contracts/configuration, lock versions, prepare feature specs, and accept separately approved recalibration decisions.
Inputs/Outputs: CLI selections and project inspection in; versioned JSON/Markdown governance artifacts out.
Non-goals: This module does not edit product source, run reviewers, or waive feature-gate failures.
Key Design Decisions: Governance updates are a distinct operation; feature preparation records a protected baseline digest.
"""

from __future__ import annotations

import platform
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import VERSION
from .errors import GovernanceError
from .ios import inspect_project
from .snapshot import governance_digest
from .util import read_json, tool_version, utc_now, write_json, write_text
from .validation import validate_decision, validate_project


PROTECTED_PATHS = [
    ".governance/project.json",
    ".governance/lock.json",
    ".governance/contracts",
    ".governance/decisions",
    ".governance/references/index.json",
]
RULE_PACKS = ["architecture-core@0.1.0", "ui-composition@0.1.0", "ios-swiftui@0.1.0"]


def governance_root(project_root: Path) -> Path:
    return project_root / ".governance"


def load_project(project_root: Path) -> Dict[str, Any]:
    """Load and validate the initialized project configuration."""

    path = governance_root(project_root) / "project.json"
    if not path.is_file():
        raise GovernanceError("blocked", "Project Governor is not initialized; run project-governor-init first")
    return validate_project(read_json(path))


def load_lock(project_root: Path) -> Dict[str, Any]:
    """Load the runtime/version lock."""

    path = governance_root(project_root) / "lock.json"
    if not path.is_file():
        raise GovernanceError("blocked", "Missing .governance/lock.json")
    value = read_json(path)
    if not isinstance(value, dict):
        raise GovernanceError("error", "lock.json must be an object")
    return value


def _select_container(inspection: Dict[str, Any], requested: Optional[str]) -> Dict[str, str]:
    containers = inspection["containers"]
    if requested:
        match = next((item for item in containers if item["path"] == requested), None)
        if not match:
            raise GovernanceError("error", "Requested Xcode container was not found", {"container": requested})
        return match
    if len(containers) != 1:
        raise GovernanceError("blocked", "Initialization requires an explicit Xcode container", {"containers": containers})
    return containers[0]


def _select_value(values: List[str], requested: Optional[str], label: str, required: bool = True) -> Optional[str]:
    if requested:
        if values and requested not in values:
            raise GovernanceError("error", f"Requested {label} was not detected", {label: requested, "detected": values})
        return requested
    if len(values) == 1:
        return values[0]
    if required:
        raise GovernanceError("blocked", f"Initialization requires an explicit {label}", {"detected": values})
    return None


def _container_args(container: Dict[str, str]) -> List[str]:
    flag = "-workspace" if container["type"] == "workspace" else "-project"
    return [flag, container["path"]]


def _default_commands(
    root: Path,
    container: Dict[str, str],
    scheme: str,
    inspection: Dict[str, Any],
) -> List[Dict[str, Any]]:
    commands: List[Dict[str, Any]] = []
    base = ["xcodebuild"] + _container_args(container) + ["-scheme", scheme]
    commands.append(
        {
            "id": "build",
            "kind": "build",
            "required": True,
            "timeout_seconds": 1200,
            "argv": base
            + [
                "-sdk",
                "iphonesimulator",
                "-destination",
                "generic/platform=iOS Simulator",
                "CODE_SIGNING_ALLOWED=NO",
                "build",
            ],
        }
    )
    test_sources = [
        path
        for path in root.rglob("*.swift")
        if any("test" in part.lower() for part in path.relative_to(root).parts)
    ]
    devices = inspection.get("simulator_devices", [])
    if test_sources and devices:
        device = devices[-1]
        destination = f"platform=iOS Simulator,name={device['name']},OS={device['runtime']}"
        commands.append(
            {
                "id": "tests",
                "kind": "test",
                "required": True,
                "timeout_seconds": 1800,
                "argv": base + ["-destination", destination, "CODE_SIGNING_ALLOWED=NO", "test"],
            }
        )
    return commands


def _normalize_languages(requested: Iterable[str], detected: List[str]) -> List[str]:
    values = [item for item in requested if item]
    if not values:
        values = detected or ["en"]
    return sorted(dict.fromkeys(values))


def _contract_text(title: str, sections: Dict[str, str]) -> str:
    lines = [f"# {title}", "", "Status: approved by project initialization", ""]
    for heading, body in sections.items():
        lines.extend([f"## {heading}", "", body.strip(), ""])
    return "\n".join(lines)


def initialize_project(
    root: Path,
    container_path: Optional[str],
    scheme_name: Optional[str],
    target_name: Optional[str],
    minimum_ios: Optional[str],
    languages: Iterable[str],
    theme_policy: str,
    ui_test_identifiers: Iterable[str],
    reviewer_model: str,
) -> Dict[str, Any]:
    """Write a confirmed Project Governor configuration under `.governance`."""

    governance = governance_root(root)
    if governance.exists():
        raise GovernanceError("blocked", ".governance already exists; use recalibrate for governance changes")
    inspection = inspect_project(root)
    container = _select_container(inspection, container_path)
    scheme = _select_value(inspection["schemes"], scheme_name, "scheme")
    target = _select_value(inspection["targets"], target_name, "target", required=False)
    selected_minimum = minimum_ios or inspection.get("minimum_ios")
    if not selected_minimum:
        raise GovernanceError("blocked", "Initialization requires a minimum supported iOS version")
    if theme_policy not in {"system", "light", "dark"}:
        raise GovernanceError("error", "theme_policy must be system, light, or dark")
    selected_languages = _normalize_languages(languages, inspection.get("locales", []))
    ui_scenarios = [
        {
            "id": f"scenario-{index + 1}",
            "test_identifier": identifier,
            "required_attachments": 1,
        }
        for index, identifier in enumerate(ui_test_identifiers)
    ]
    project = {
        "schema_version": 1,
        "project_id": re.sub(r"[^a-z0-9-]+", "-", root.name.lower()).strip("-") or "ios-project",
        "adapter": "ios-swiftui",
        "container": container["path"],
        "container_type": container["type"],
        "scheme": scheme,
        "target": target,
        "ios": {
            "minimum_version": selected_minimum,
            "languages": selected_languages,
            "theme_policy": theme_policy,
            "appearances": ["light", "dark"] if theme_policy == "system" else [theme_policy],
            "require_pre26_and_ios26_for_navigation": True,
        },
        "commands": _default_commands(root, container, str(scheme), inspection),
        "ui_scenarios": ui_scenarios,
        "review_policy": {
            "architecture": "required",
            "ui": "when_ui_impact",
            "maximum_revision_rounds": 2,
            "reviewer_model": reviewer_model,
            "reviewer_timeout_seconds": 900,
        },
        "protected_paths": PROTECTED_PATHS,
        "rule_packs": RULE_PACKS,
    }
    validate_project(project)

    governance.mkdir(parents=True)
    write_json(governance / "project.json", project)
    write_text(governance / ".gitignore", ".runs/\n")
    write_text(
        governance / "contracts" / "architecture.md",
        _contract_text(
            "Architecture Contract",
            {
                "Purpose": "Keep capability ownership, module boundaries, state ownership, and public interfaces explicit.",
                "File-level intent": "Read a code file's top-level comment before implementation or review. Preserve documented responsibilities, inputs/outputs, non-goals, and key design decisions. Missing comments require cautious assumptions rather than invented intent.",
                "Change boundary": "Feature changes cannot alter contracts, approved decisions, the runtime lock, or gate definitions.",
            },
        ),
    )
    write_text(
        governance / "contracts" / "ui.md",
        _contract_text(
            "UI Contract",
            {
                "Primary task": "New UI must preserve the product's approved primary task and information hierarchy.",
                "Composition": "Reuse an approved semantic interaction before adding another vocabulary. A new pattern is allowed only when the ledger makes the mismatch visible.",
                "States": "Verify every reachable state named by the change specification. Interaction claims require runtime evidence.",
                "iOS navigation": "Preserve native navigation bars, back accessibility, interactive pop, and the project's semantic colors. Centralize legacy appearance before bars are created, gate it below iOS 26, and preserve native iOS 26+ behavior.",
            },
        ),
    )
    write_text(
        governance / "contracts" / "tasks.md",
        _contract_text(
            "Task Contract",
            {
                "Project goal": "Project-specific user goals must be added as approved decisions or references; current screens are not automatically a normative baseline.",
                "Regression": "A change must name affected existing tasks and provide checks for regressions that are within scope.",
                "Non-goals": "Project Governor does not add product requirements, redesign screens, or convert reviewer preferences into requirements.",
            },
        ),
    )
    write_json(governance / "references" / "index.json", {"schema_version": 1, "approved": []})
    (governance / "decisions").mkdir(parents=True, exist_ok=True)
    (governance / "changes").mkdir(parents=True, exist_ok=True)
    (governance / ".runs").mkdir(parents=True, exist_ok=True)
    lock = {
        "schema_version": 1,
        "plugin": {"name": "project-governor", "version": VERSION},
        "runtime": {"version": VERSION, "python": platform.python_version()},
        "adapter": {"name": "ios-swiftui", "version": VERSION},
        "rule_packs": RULE_PACKS,
        "reviewer": {"model": reviewer_model},
        "codex_cli": tool_version(["codex", "--version"], root),
        "calibration": {
            "approved_sample_passes": True,
            "known_violation_fails": True,
            "missing_evidence_blocks": True,
        },
        "created_at": utc_now(),
        "governance_digest": "",
    }
    write_json(governance / "lock.json", lock)
    lock["governance_digest"] = governance_digest(root)
    write_json(governance / "lock.json", lock)
    return {
        "verdict": "pass",
        "project": project,
        "lock": lock,
        "inspection": inspection,
        "warnings": [
            "UI verification remains blocked until at least one registered UI scenario exists."
        ]
        if not ui_scenarios
        else [],
    }


def prepare_change(
    root: Path,
    change_id: str,
    goal: str,
    acceptance: Iterable[str],
    module: str,
    ui_impact: str,
    ui_states: Iterable[str],
    scope: Iterable[str],
    non_goals: Iterable[str],
) -> Dict[str, Any]:
    """Create a feature spec and empty factual ledger before implementation."""

    load_project(root)
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", change_id):
        raise GovernanceError("error", "change_id must be lowercase hyphen-case")
    accept = [item for item in acceptance if item]
    if not goal.strip() or not module.strip() or not accept:
        raise GovernanceError("error", "prepare requires a goal, module, and at least one acceptance criterion")
    change_root = governance_root(root) / "changes" / change_id
    if change_root.exists():
        raise GovernanceError("blocked", "Change already exists; use a new change id", {"change_id": change_id})
    spec = {
        "schema_version": 1,
        "change_id": change_id,
        "goal": goal.strip(),
        "acceptance": accept,
        "module": module.strip(),
        "ui_impact": ui_impact,
        "ui_states": [item for item in ui_states if item],
        "scope": [item for item in scope if item],
        "non_goals": [item for item in non_goals if item],
        "baseline_governance_digest": governance_digest(root),
    }
    ledger = {
        "schema_version": 1,
        "reused_structures": [],
        "new_concepts": [],
        "new_entries": [],
        "new_interaction_patterns": [],
        "replaced_or_removed": [],
        "affected_existing_tasks": [],
        "exception_requests": [],
        "file_comment_assumptions": [],
    }
    write_json(change_root / "spec.json", spec)
    write_text(
        change_root / "spec.md",
        "\n".join(
            [
                f"# Change: {change_id}",
                "",
                f"## Goal\n\n{goal.strip()}",
                "",
                "## Acceptance",
                "",
                *[f"- {item}" for item in accept],
                "",
                f"## Module\n\n{module.strip()}",
                "",
                "## Non-goals",
                "",
                *([f"- {item}" for item in non_goals if item] or ["- None recorded"]),
                "",
            ]
        ),
    )
    write_json(change_root / "ledger.json", ledger)
    result = {"change_id": change_id, "verdict": "pending", "prepared_at": utc_now()}
    write_json(change_root / "result.json", result)
    return {"verdict": "pass", "spec": spec, "ledger": ledger}


def recalibrate_project(
    root: Path,
    accept_current: bool,
    decision_file: Optional[Path],
    reviewer_model: Optional[str],
) -> Dict[str, Any]:
    """Accept an explicitly separate governance update and relock it."""

    load_project(root)
    lock = load_lock(root)
    installed_decision = None
    if decision_file:
        decision = validate_decision(read_json(decision_file))
        decision = dict(decision)
        decision.setdefault("approved_at", utc_now())
        destination = governance_root(root) / "decisions" / f"{decision['id']}.json"
        if destination.exists():
            raise GovernanceError("blocked", "Decision id already exists; decisions are append-only")
        write_json(destination, decision)
        installed_decision = destination.relative_to(root).as_posix()
    if reviewer_model:
        lock.setdefault("reviewer", {})["model"] = reviewer_model
    if not accept_current and not decision_file and not reviewer_model:
        raise GovernanceError("error", "recalibrate requires --accept-current, --decision-file, or --reviewer-model")
    lock["recalibrated_at"] = utc_now()
    write_json(governance_root(root) / "lock.json", lock)
    lock["governance_digest"] = governance_digest(root)
    write_json(governance_root(root) / "lock.json", lock)
    return {
        "verdict": "pass",
        "governance_digest": lock["governance_digest"],
        "installed_decision": installed_decision,
        "reviewer_model": lock.get("reviewer", {}).get("model", "inherit"),
    }
