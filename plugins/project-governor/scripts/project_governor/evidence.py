"""Purpose: Import explicitly supplied local verification artifacts into an isolated review bundle.
Responsibilities: Bound paths to the project's evidence directory, reject symlinks, freeze bytes and record provenance.
Inputs/Outputs: A caller-authored manifest in; copied artifacts and a SHA-256 inventory out.
Non-goals: Does not certify caller provenance claims, replace required checks, change rules, or infer a passing verdict.
Key Decisions: Imported artifacts remain evidence for independent reviewers, never instructions or automatic check results.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from .errors import GovernanceError
from .util import canonical_json, sha256_bytes, sha256_file, write_json


def import_evidence(root: Path, manifest_path: Optional[Path], destination: Path) -> Dict[str, Any]:
    if manifest_path is None:
        return {"artifacts": []}
    base = (root / "evidence").resolve()

    def bounded(value: Path) -> Path:
        path = value if value.is_absolute() else root / value
        # Reject symlinks at every level, including the evidence root itself.
        cursor = path.absolute()
        while cursor != root.absolute() and cursor != cursor.parent:
            if cursor.is_symlink():
                raise GovernanceError("blocked", "Supplemental evidence cannot contain symlinks")
            cursor = cursor.parent
        resolved = path.resolve()
        if resolved == base or base not in resolved.parents or not resolved.exists():
            raise GovernanceError("blocked", "Supplemental evidence must exist beneath the project's evidence directory")
        return resolved

    manifest_file = bounded(manifest_path)
    manifest_bytes = manifest_file.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise GovernanceError("blocked", "Supplemental evidence requires schema_version 1")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise GovernanceError("blocked", "Supplemental evidence needs a nonempty artifacts list")
    target = destination / "supplemental"
    target.mkdir(parents=True, exist_ok=False)
    records = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or not artifact["path"]:
            raise GovernanceError("blocked", "Every supplemental artifact requires a path")
        if not isinstance(artifact.get("description"), str) or not artifact["description"].strip():
            raise GovernanceError("blocked", "Every supplemental artifact requires a description")
        source = bounded(Path(artifact["path"]))
        if source == destination.resolve() or source in destination.resolve().parents:
            raise GovernanceError("blocked", "Supplemental artifact cannot contain the destination run")
        if source.is_dir():
            children = sorted(source.rglob("*"))
            if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in children):
                raise GovernanceError("blocked", "Supplemental evidence contains a symlink or special file")
            files = [p for p in children if p.is_file()]
        elif source.is_file():
            files = [source]
        else:
            raise GovernanceError("blocked", "Supplemental evidence must be regular files or directories")
        if not files:
            raise GovernanceError("blocked", "Supplemental artifact is empty")
        inventory = [{"path": str(p.relative_to(source)) if source.is_dir() else source.name,
                      "sha256": sha256_file(p), "size": p.stat().st_size} for p in files]
        digest = sha256_bytes(canonical_json(inventory))
        if artifact.get("digest") is not None and artifact["digest"] != digest:
            raise GovernanceError("blocked", "Supplemental artifact does not match its expected inventory digest")
        copied = target / f"{index:03d}" / source.name
        copied.parent.mkdir(parents=True)
        if source.is_dir():
            shutil.copytree(source, copied)
        else:
            shutil.copy2(source, copied)
        copied_items = sorted(copied.rglob("*")) if source.is_dir() else [copied]
        if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in copied_items):
            raise GovernanceError("blocked", "Supplemental artifact changed while being copied")
        copied_inventory = [{"path": str(p.relative_to(copied)) if source.is_dir() else copied.name,
                             "sha256": sha256_file(p), "size": p.stat().st_size}
                            for p in copied_items if p.is_file()]
        if copied_inventory != inventory:
            raise GovernanceError("blocked", "Supplemental artifact changed while being copied")
        records.append({"path": copied.relative_to(destination).as_posix(),
                        "description": artifact["description"], "inventory_digest": digest,
                        "files": inventory, "provided_provenance": artifact.get("provenance", {}),
                        "provenance_verified_by_import": False})
    result = {"schema_version": 1, "manifest_sha256": sha256_bytes(manifest_bytes), "artifacts": records}
    write_json(target / "index.json", result)
    return result
