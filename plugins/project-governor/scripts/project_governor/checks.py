"""
Purpose: Execute configured build, test, and iOS UI evidence checks for a frozen candidate.
Responsibilities: Run argv-only commands, persist logs, execute registered XCUITest matrices, and export xcresult attachments.
Inputs/Outputs: Project configuration and evidence directory in; structured check records out.
Non-goals: This module does not judge design quality or convert missing evidence into a pass.
Key Design Decisions: Tool absence and timeouts are blocked; non-zero product checks are failures; UI claims require exported attachments.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .ios import inspect_project, resolve_runtime_devices
from .util import run_command, sha256_file, write_json, write_text


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "check"


def _status_for_process(returncode: Any, timed_out: bool, missing: bool) -> str:
    if timed_out or missing or returncode is None:
        return "blocked"
    return "pass" if returncode == 0 else "fail"


def _write_process_logs(directory: Path, identifier: str, stdout: str, stderr: str) -> Dict[str, str]:
    stdout_path = directory / f"{identifier}.stdout.log"
    stderr_path = directory / f"{identifier}.stderr.log"
    write_text(stdout_path, stdout)
    write_text(stderr_path, stderr)
    return {"stdout": stdout_path.name, "stderr": stderr_path.name}


def run_automatic_checks(
    root: Path,
    commands: Sequence[Mapping[str, Any]],
    evidence_dir: Path,
) -> List[Dict[str, Any]]:
    """Run project-configured build and test commands."""

    output_dir = evidence_dir / "checks"
    output_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    for index, command in enumerate(commands):
        identifier = _safe_name(str(command.get("id", f"check-{index + 1}")))
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) for item in argv):
            results.append(
                {
                    "id": identifier,
                    "kind": command.get("kind", "unknown"),
                    "required": bool(command.get("required", True)),
                    "status": "blocked",
                    "reason": "Command argv must be a non-empty string array.",
                }
            )
            continue
        process = run_command(
            argv,
            cwd=root,
            timeout=int(command.get("timeout_seconds", 1200)),
        )
        logs = _write_process_logs(output_dir, identifier, process.stdout, process.stderr)
        results.append(
            {
                "id": identifier,
                "kind": command.get("kind", "command"),
                "required": bool(command.get("required", True)),
                "status": _status_for_process(process.returncode, process.timed_out, process.missing_executable),
                "returncode": process.returncode,
                "timed_out": process.timed_out,
                "missing_executable": process.missing_executable,
                "argv": process.argv,
                "logs": logs,
            }
        )
    write_json(output_dir / "index.json", {"checks": results})
    return results


def _container_args(project: Mapping[str, Any]) -> List[str]:
    container_type = project.get("container_type")
    container = project.get("container")
    if container_type not in {"workspace", "project"} or not isinstance(container, str):
        return []
    return ["-workspace" if container_type == "workspace" else "-project", container]


def _review_languages(project: Mapping[str, Any]) -> List[str]:
    languages = project.get("ios", {}).get("languages", [])
    chosen: List[str] = []
    english = next((item for item in languages if item.lower().startswith("en")), None)
    chinese = next((item for item in languages if item.lower().startswith("zh")), None)
    if english:
        chosen.append(english)
    if chinese and chinese not in chosen:
        chosen.append(chinese)
    if not chosen and languages:
        chosen.append(str(languages[0]))
    return chosen or ["en"]


def run_ui_checks(
    root: Path,
    project: Mapping[str, Any],
    evidence_dir: Path,
    navigation_changed: bool,
) -> Dict[str, Any]:
    """Run the registered XCUITest evidence matrix and export screenshots."""

    scenarios = project.get("ui_scenarios", [])
    if not scenarios:
        return {
            "status": "blocked",
            "reason": "No deterministic UI scenario is registered in project.json.",
            "runs": [],
        }
    inspection = inspect_project(root)
    minimum = project.get("ios", {}).get("minimum_version")
    require_compatibility = bool(
        navigation_changed
        and project.get("ios", {}).get("require_pre26_and_ios26_for_navigation", True)
    )
    devices, missing = resolve_runtime_devices(inspection, minimum, require_compatibility)
    if missing:
        return {
            "status": "blocked",
            "reason": "Required simulator evidence is unavailable.",
            "missing": missing,
            "runs": [],
        }
    container_args = _container_args(project)
    scheme = project.get("scheme")
    if not container_args or not isinstance(scheme, str) or not scheme:
        return {"status": "blocked", "reason": "Xcode container or scheme is not configured.", "runs": []}

    languages = _review_languages(project)
    appearances = project.get("ios", {}).get("appearances", ["light", "dark"])
    ui_root = evidence_dir / "ui"
    ui_root.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    for scenario in scenarios:
        identifier = scenario.get("test_identifier")
        if not isinstance(identifier, str) or not identifier:
            results.append({"id": scenario.get("id", "unknown"), "status": "blocked", "reason": "Missing test_identifier"})
            continue
        for device in devices:
            for language in languages:
                for appearance in appearances:
                    run_id = _safe_name(
                        f"{scenario.get('id', 'scenario')}-{device['runtime']}-{language}-{appearance}"
                    )
                    result_bundle = ui_root / f"{run_id}.xcresult"
                    attachments = ui_root / f"{run_id}-attachments"
                    destination = (
                        f"platform=iOS Simulator,name={device['name']},OS={device['runtime']}"
                    )
                    argv = [
                        "xcodebuild",
                        *container_args,
                        "-scheme",
                        scheme,
                        "-destination",
                        destination,
                        "-only-testing:" + identifier,
                        "-testLanguage",
                        language,
                        "-resultBundlePath",
                        str(result_bundle),
                        "CODE_SIGNING_ALLOWED=NO",
                        "test",
                    ]
                    process = run_command(
                        argv,
                        cwd=root,
                        timeout=int(project.get("review_policy", {}).get("ui_test_timeout_seconds", 1800)),
                        env={"PG_APPEARANCE": str(appearance)},
                    )
                    logs = _write_process_logs(ui_root, run_id, process.stdout, process.stderr)
                    status = _status_for_process(process.returncode, process.timed_out, process.missing_executable)
                    attachment_files: List[Dict[str, Any]] = []
                    export_logs = None
                    if status == "pass" and result_bundle.exists():
                        export = run_command(
                            [
                                "xcrun",
                                "xcresulttool",
                                "export",
                                "attachments",
                                "--path",
                                str(result_bundle),
                                "--output-path",
                                str(attachments),
                            ],
                            cwd=root,
                            timeout=180,
                        )
                        export_logs = _write_process_logs(
                            ui_root, f"{run_id}-attachments", export.stdout, export.stderr
                        )
                        if export.returncode != 0:
                            status = "blocked"
                        elif attachments.exists():
                            for path in sorted(attachments.rglob("*")):
                                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                                    attachment_files.append(
                                        {
                                            "path": path.relative_to(evidence_dir).as_posix(),
                                            "sha256": sha256_file(path),
                                        }
                                    )
                    required = int(scenario.get("required_attachments", 1))
                    if status == "pass" and len(attachment_files) < required:
                        status = "blocked"
                    results.append(
                        {
                            "id": run_id,
                            "scenario": scenario.get("id", identifier),
                            "test_identifier": identifier,
                            "runtime": device["runtime"],
                            "device": device["name"],
                            "language": language,
                            "appearance": appearance,
                            "status": status,
                            "returncode": process.returncode,
                            "argv": process.argv,
                            "logs": logs,
                            "attachment_export_logs": export_logs,
                            "attachments": attachment_files,
                        }
                    )
    statuses = {item["status"] for item in results}
    overall = "blocked" if "blocked" in statuses else "fail" if "fail" in statuses else "pass"
    payload = {"status": overall, "runs": results, "navigation_compatibility_required": require_compatibility}
    write_json(ui_root / "index.json", payload)
    return payload
