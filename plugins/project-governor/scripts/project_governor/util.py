"""
Purpose: Provide deterministic filesystem, JSON, hashing, timestamp, and subprocess helpers.
Responsibilities: Centralize atomic writes, canonical JSON, SHA-256, safe command execution, and tool version capture.
Inputs/Outputs: Files, byte streams, and argv lists in; structured values and command results out.
Non-goals: This module does not decide governance verdicts or interpret iOS project structure.
Key Design Decisions: Commands are argv arrays rather than shell strings; JSON is canonicalized for stable digests.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class CommandResult:
    """Captured result for one argv-based process invocation."""

    argv: List[str]
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool = False
    missing_executable: bool = False


def utc_now() -> str:
    """Return a compact UTC timestamp suitable for persisted state."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> bytes:
    """Serialize JSON deterministically for hashing."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read_json(path: Path) -> Any:
    """Read UTF-8 JSON from a path."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    """Atomically write stable, human-readable UTF-8 JSON."""

    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text(path, payload)


def write_text(path: Path, text: str) -> None:
    """Atomically write UTF-8 text while creating parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_bytes(data: bytes) -> str:
    """Return a lowercase SHA-256 hex digest."""

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading the whole file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    argv: Sequence[str],
    cwd: Path,
    timeout: int = 120,
    env: Optional[Mapping[str, str]] = None,
) -> CommandResult:
    """Run one command without a shell and capture all output."""

    command = [str(item) for item in argv]
    merged_env = os.environ.copy()
    if env:
        merged_env.update({str(key): str(value) for key, value in env.items()})
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=merged_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return CommandResult(command, completed.returncode, completed.stdout, completed.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(command, None, stdout, stderr, timed_out=True)
    except FileNotFoundError as exc:
        return CommandResult(command, None, "", str(exc), missing_executable=True)


def first_line(value: str) -> str:
    """Return the first non-empty line of a command response."""

    for line in value.splitlines():
        if line.strip():
            return line.strip()
    return "unavailable"


def tool_version(argv: Sequence[str], cwd: Path) -> str:
    """Capture a best-effort one-line tool version."""

    result = run_command(argv, cwd=cwd, timeout=15)
    if result.returncode == 0:
        return first_line(result.stdout or result.stderr)
    return "unavailable"


def relative_paths(paths: Iterable[Path], root: Path) -> List[str]:
    """Normalize paths relative to a root using POSIX separators."""

    return sorted(path.resolve().relative_to(root.resolve()).as_posix() for path in paths)
