"""
Purpose: Inspect iOS SwiftUI repositories and derive evidence requirements from real local tooling.
Responsibilities: Detect Xcode containers, schemes, targets, deployment versions, locales, UI tests, design/navigation signals, simulators, and UI-impacting changes.
Inputs/Outputs: A project root or changed-path list in; structured inspection and routing decisions out.
Non-goals: This module does not edit Xcode projects or claim UI behavior from static source inspection.
Key Design Decisions: Missing runtime or XCUITest evidence is surfaced as unavailable/blocked rather than silently downgraded.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .util import run_command


def _read_prefix(path: Path, limit: int = 64 * 1024) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _version_tuple(value: str) -> Tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(item) for item in numbers[:3]) if numbers else tuple()


def _simulator_inventory(root: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    runtimes: List[Dict[str, str]] = []
    devices: List[Dict[str, str]] = []
    if not shutil.which("xcrun"):
        return runtimes, devices
    runtime_result = run_command(["xcrun", "simctl", "list", "runtimes", "--json"], root, timeout=30)
    if runtime_result.returncode == 0:
        try:
            for item in json.loads(runtime_result.stdout).get("runtimes", []):
                if item.get("isAvailable", True) and "iOS" in item.get("name", ""):
                    runtimes.append(
                        {
                            "name": str(item.get("name", "")),
                            "version": str(item.get("version", "")),
                            "identifier": str(item.get("identifier", "")),
                        }
                    )
        except (TypeError, ValueError):
            pass
    device_result = run_command(["xcrun", "simctl", "list", "devices", "available", "--json"], root, timeout=30)
    if device_result.returncode == 0:
        try:
            payload = json.loads(device_result.stdout).get("devices", {})
            for runtime_identifier, values in payload.items():
                runtime = next((item for item in runtimes if item["identifier"] == runtime_identifier), None)
                if not runtime:
                    continue
                for device in values:
                    name = str(device.get("name", ""))
                    if "iPhone" in name and device.get("isAvailable", True):
                        devices.append(
                            {
                                "runtime": runtime["version"],
                                "name": name,
                                "udid": str(device.get("udid", "")),
                            }
                        )
        except (TypeError, ValueError):
            pass
    runtimes.sort(key=lambda item: _version_tuple(item["version"]))
    devices.sort(key=lambda item: (_version_tuple(item["runtime"]), item["name"]))
    return runtimes, devices


def inspect_project(root: Path) -> Dict[str, Any]:
    """Inspect an iOS repository without writing project files."""

    workspaces = sorted(
        path for path in root.rglob("*.xcworkspace") if ".xcodeproj" not in path.as_posix()
    )
    projects = sorted(root.rglob("*.xcodeproj"))
    containers = [
        {"path": path.relative_to(root).as_posix(), "type": "workspace"} for path in workspaces
    ] + [{"path": path.relative_to(root).as_posix(), "type": "project"} for path in projects]

    scheme_paths = sorted(root.rglob("xcshareddata/xcschemes/*.xcscheme"))
    schemes = sorted({path.stem for path in scheme_paths})
    pbx_projects = [path / "project.pbxproj" for path in projects if (path / "project.pbxproj").is_file()]
    pbx_text = "\n".join(_read_prefix(path, 4 * 1024 * 1024) for path in pbx_projects)
    deployment_targets = sorted(set(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*([0-9.]+)", pbx_text)), key=_version_tuple)
    target_names = sorted(set(re.findall(r"isa = PBXNativeTarget;.*?name = ([^;]+);", pbx_text, flags=re.S)))

    locale_paths = sorted(path for path in root.rglob("*.lproj") if path.is_dir())
    locales = sorted({path.stem for path in locale_paths if path.stem != "Base"})
    swift_files = sorted(root.rglob("*.swift"))
    ui_test_files: List[str] = []
    design_signals: List[str] = []
    navigation_signals: List[str] = []
    for path in swift_files:
        relative = path.relative_to(root).as_posix()
        lowered = relative.lower()
        text = _read_prefix(path)
        if "uitest" in lowered or "XCUIApplication" in text:
            ui_test_files.append(relative)
        if any(token in lowered for token in ("designsystem", "design-system", "theme", "token", "palette", "style")):
            design_signals.append(relative)
        if any(token in text for token in ("NavigationStack", "NavigationView", "UINavigationBarAppearance", "navigationBar", ".toolbar")):
            navigation_signals.append(relative)

    runtimes, devices = _simulator_inventory(root)
    minimum_ios = deployment_targets[0] if deployment_targets else None
    pre26_available = any(_version_tuple(item["version"]) < (26,) for item in runtimes)
    ios26_available = any(_version_tuple(item["version"]) >= (26,) for item in runtimes)
    exact_minimum_available = bool(
        minimum_ios
        and any(_version_tuple(item["version"])[:2] == _version_tuple(minimum_ios)[:2] for item in runtimes)
    )
    tool_status = {
        "git": bool(shutil.which("git")),
        "codex": bool(shutil.which("codex")),
        "xcodebuild": bool(shutil.which("xcodebuild")),
        "xcrun": bool(shutil.which("xcrun")),
        "python3": bool(shutil.which("python3")),
    }
    conflicts = []
    if len(containers) != 1:
        conflicts.append("Select one Xcode workspace or project container.")
    if len(schemes) != 1:
        conflicts.append("Select one shared scheme.")
    if not minimum_ios:
        conflicts.append("Confirm the minimum supported iOS version.")
    capabilities = {
        "architecture_review": "available" if tool_status["git"] and tool_status["codex"] else "blocked",
        "build_test": "available" if tool_status["xcodebuild"] and containers and schemes else "blocked",
        "ui_evidence": "available"
        if tool_status["xcrun"] and ui_test_files and devices
        else "blocked",
        "minimum_runtime": "available" if exact_minimum_available else "blocked",
        "ios26_runtime": "available" if ios26_available else "blocked",
    }
    return {
        "adapter": "ios-swiftui",
        "project_root": str(root.resolve()),
        "containers": containers,
        "schemes": schemes,
        "targets": [item.strip('"') for item in target_names],
        "deployment_targets": deployment_targets,
        "minimum_ios": minimum_ios,
        "locales": locales,
        "ui_test_files": ui_test_files,
        "design_system_signals": design_signals,
        "navigation_signals": navigation_signals,
        "simulator_runtimes": runtimes,
        "simulator_devices": devices,
        "tool_status": tool_status,
        "capabilities": capabilities,
        "candidate_patterns": {
            "design_system_files": design_signals,
            "navigation_files": navigation_signals,
        },
        "legacy_risks": [],
        "conflicts": conflicts,
        "runtime_summary": {
            "pre_ios26_available": pre26_available,
            "ios26_or_later_available": ios26_available,
            "minimum_runtime_available": exact_minimum_available,
        },
    }


def ui_impact(changed: Sequence[str], spec_ui_impact: str, root: Path) -> bool:
    """Conservatively route visible changes to UI review."""

    if spec_ui_impact == "yes":
        return True
    for relative in changed:
        if relative.startswith(".governance/"):
            continue
        lowered = relative.lower()
        if any(token in lowered for token in (".xcassets/", ".lproj/", ".strings", "view.swift", "screen.swift", "navigation", "designsystem", "design-system")):
            return True
        if lowered.endswith(".swift"):
            text = _read_prefix(root / relative)
            if "import SwiftUI" in text or re.search(r"\bView\b", text):
                return True
    return False


def navigation_impact(changed: Sequence[str], root: Path) -> bool:
    """Detect navigation-sensitive source changes for compatibility evidence routing."""

    for relative in changed:
        lowered = relative.lower()
        if "navigation" in lowered or "navbar" in lowered:
            return True
        path = root / relative
        if path.suffix == ".swift":
            text = _read_prefix(path)
            if any(token in text for token in ("NavigationStack", "NavigationView", "UINavigationBarAppearance", "navigationBarBackButtonHidden")):
                return True
    return False


def resolve_runtime_devices(
    inspection: Dict[str, Any],
    minimum_ios: Optional[str],
    require_legacy_and_modern: bool,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """Choose one iPhone per required runtime class and explain missing classes."""

    devices = inspection.get("simulator_devices", [])
    selected: List[Dict[str, str]] = []
    missing: List[str] = []
    if require_legacy_and_modern and minimum_ios and _version_tuple(minimum_ios) < (26,):
        minimum = next(
            (item for item in devices if _version_tuple(item["runtime"])[:2] == _version_tuple(minimum_ios)[:2]),
            None,
        )
        if minimum:
            selected.append(minimum)
        else:
            missing.append(f"minimum supported iOS runtime {minimum_ios}")
    modern = next((item for item in devices if _version_tuple(item["runtime"]) >= (26,)), None)
    if modern:
        if modern not in selected:
            selected.append(modern)
    else:
        missing.append("iOS 26 or later runtime")
    if not require_legacy_and_modern and not selected:
        newest = devices[-1] if devices else None
        if newest:
            selected.append(newest)
        else:
            missing.append("an available iPhone simulator")
    return selected, missing
