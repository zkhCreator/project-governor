"""
Purpose: Freeze candidate and governance state with content-addressed manifests.
Responsibilities: Enumerate tracked and unignored files, exclude generated caches, hash content, and detect protected-governance drift.
Inputs/Outputs: A Git project root in; deterministic manifest and SHA-256 digests out.
Non-goals: This module does not commit, stash, reset, or otherwise mutate Git state.
Key Design Decisions: Untracked non-ignored files are included so newly added implementation files cannot escape the candidate digest.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .errors import GovernanceError
from .util import canonical_json, read_json, run_command, sha256_bytes, sha256_file


EXCLUDED_PARTS = {".git", "DerivedData", ".build", "build", "__pycache__"}


def _is_excluded(relative: Path) -> bool:
    parts = relative.parts
    if any(part in EXCLUDED_PARTS for part in parts):
        return True
    if len(parts) >= 2 and parts[0] == ".governance" and parts[1] == ".runs":
        return True
    return (
        len(parts) >= 4
        and parts[0] == ".governance"
        and parts[1] == "changes"
        and parts[-1] == "result.json"
    )


def candidate_files(root: Path) -> List[Path]:
    """List Git tracked plus unignored untracked files in stable order."""

    result = run_command(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=root,
        timeout=60,
    )
    if result.returncode != 0:
        raise GovernanceError("blocked", "Candidate freezing requires a readable Git repository", {"stderr": result.stderr})
    paths: List[Path] = []
    for raw in result.stdout.split("\0"):
        if not raw:
            continue
        relative = Path(raw)
        absolute = root / relative
        if _is_excluded(relative) or not absolute.is_file() or absolute.is_symlink():
            continue
        paths.append(absolute)
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())


def build_manifest(root: Path) -> Dict[str, Any]:
    """Build a stable manifest and digest for the current candidate."""

    entries = []
    for path in candidate_files(root):
        relative = path.relative_to(root).as_posix()
        entries.append({"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size})
    digest = sha256_bytes(canonical_json(entries))
    return {"algorithm": "sha256", "digest": digest, "files": entries}


def _protected_file_payload(path: Path, root: Path) -> Dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    if relative == ".governance/lock.json":
        value = read_json(path)
        if isinstance(value, dict):
            value = dict(value)
            value.pop("governance_digest", None)
        data = canonical_json(value)
        return {"path": relative, "sha256": sha256_bytes(data), "size": len(data)}
    return {"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size}


def governance_digest(root: Path) -> str:
    """Hash protected project configuration without a circular lock digest."""

    governance = root / ".governance"
    if not governance.exists():
        raise GovernanceError("blocked", "Project Governor is not initialized")
    paths: List[Path] = []
    for relative in ("project.json", "lock.json"):
        path = governance / relative
        if path.is_file():
            paths.append(path)
    for directory in ("contracts", "decisions"):
        base = governance / directory
        if base.exists():
            paths.extend(path for path in base.rglob("*") if path.is_file() and not path.is_symlink())
    reference_index = governance / "references" / "index.json"
    if reference_index.is_file():
        paths.append(reference_index)
    entries = [_protected_file_payload(path, root) for path in sorted(set(paths))]
    return sha256_bytes(canonical_json(entries))


def changed_paths(root: Path) -> List[str]:
    """Return staged, unstaged, and untracked non-ignored paths."""

    commands = (
        ["git", "diff", "--name-only", "-z"],
        ["git", "diff", "--cached", "--name-only", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    )
    changed = set()
    for command in commands:
        result = run_command(command, cwd=root, timeout=30)
        if result.returncode != 0:
            raise GovernanceError("blocked", "Unable to inspect changed files", {"stderr": result.stderr})
        changed.update(item for item in result.stdout.split("\0") if item)
    return sorted(changed)


def copy_manifest_files(root: Path, manifest: Dict[str, Any], destination: Path) -> None:
    """Copy exactly the frozen candidate files into an isolated directory."""

    import shutil

    for entry in manifest.get("files", []):
        relative = Path(entry["path"])
        source = root / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
