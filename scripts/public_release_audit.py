"""
Purpose: Audit a repository candidate and, on request, its Git history before public distribution.
Responsibilities: Verify community files, ignored private artifacts, structured Python intent, JSON, manifests, symlinks, action references, disclosure patterns, and historical blobs.
Inputs/Outputs: A repository root in; a deterministic PASS/FAIL report and process exit code out.
Non-goals: This module does not prove copyright ownership, inspect binary media contents, rotate secrets, or change repository visibility.
Key Decisions: The audit uses only Python 3.9+ standard-library modules, fails closed on unreadable candidates, and requires explicit acknowledgment before accepting non-noreply commit identities.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

REQUIRED_FILES = (
    ".editorconfig",
    ".gitattributes",
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "PRIVACY.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/PUBLIC_RELEASE.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/question.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/public-readiness.yml",
    ".github/workflows/codeql.yml",
    ".agents/plugins/marketplace.json",
    "plugins/project-governor/.codex-plugin/plugin.json",
)

REQUIRED_IGNORE_RULES = (
    ".env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.mobileprovision",
    "xcuserdata/",
    "*.xcuserstate",
    "DerivedData/",
    "*.xcresult",
    ".DS_Store",
)

FORBIDDEN_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "DerivedData",
    "xcuserdata",
    ".runs",
}

FORBIDDEN_SUFFIXES = {
    ".cer",
    ".der",
    ".key",
    ".mobileprovision",
    ".p12",
    ".pem",
    ".provisionprofile",
    ".pyc",
    ".xcresult",
    ".xcuserstate",
}

BINARY_SUFFIXES = {
    ".7z",
    ".a",
    ".dylib",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".so",
    ".tar",
    ".tgz",
    ".wav",
    ".xcframework",
    ".zip",
}

SENSITIVE_PATTERNS: Sequence[tuple[str, re.Pattern[str]]] = (
    (
        "private key material",
        re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?" + "PRIVATE KEY-----"),
    ),
    ("AWS access key", re.compile(r"\bAKI" + r"A[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh" + r"[oprsu]_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub" + r"_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI-style secret", re.compile(r"\bsk" + r"-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox" + r"[aboprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{30,}\b")),
    (
        "personal POSIX home path",
        re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    ),
    (
        "personal Windows home path",
        re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._ -]+\\"),
    ),
)

MODULE_SECTIONS = (
    "Purpose:",
    "Responsibilities:",
    "Inputs/Outputs:",
    "Non-goals:",
)


def _candidate_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=str(root),
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        relatives = [item for item in result.stdout.decode("utf-8").split("\0") if item]
        return sorted(root / item for item in relatives if (root / item).is_file() or (root / item).is_symlink())
    return sorted(
        path
        for path in root.rglob("*")
        if (path.is_file() or path.is_symlink()) and ".git" not in path.relative_to(root).parts
    )


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        errors.append(f"Cannot read {path}: {exc}")
        return ""
    if b"\0" in data:
        errors.append(f"Unexpected binary content in text candidate: {path}")
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"Non-UTF-8 text candidate {path}: {exc}")
        return ""


def _audit_required_files(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"Missing required public repository file: {relative}")


def _audit_ignored_artifacts(root: Path, errors: list[str]) -> None:
    ignore_path = root / ".gitignore"
    if not ignore_path.is_file():
        errors.append("Missing .gitignore")
        return
    values = {line.strip() for line in ignore_path.read_text(encoding="utf-8").splitlines()}
    for rule in REQUIRED_IGNORE_RULES:
        if rule not in values:
            errors.append(f".gitignore is missing required public-safety rule: {rule}")


def _audit_path(root: Path, path: Path, errors: list[str]) -> None:
    relative = path.relative_to(root)
    relative_text = relative.as_posix()
    lowered_name = path.name.lower()
    if any(part in FORBIDDEN_PARTS for part in relative.parts):
        errors.append(f"Forbidden generated/private path is a candidate: {relative_text}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"Forbidden credential/generated file is a candidate: {relative_text}")
    if lowered_name == ".env" or (lowered_name.startswith(".env.") and lowered_name != ".env.example"):
        errors.append(f"Environment secret file is a candidate: {relative_text}")
    if path.is_symlink():
        try:
            path.resolve(strict=True).relative_to(root.resolve())
        except (OSError, ValueError):
            errors.append(f"Symlink escapes the repository or is broken: {relative_text}")
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"Candidate exceeds the 5 MiB review limit: {relative_text}")
    except OSError as exc:
        errors.append(f"Cannot stat {relative_text}: {exc}")


def _audit_text(root: Path, path: Path, text: str, errors: list[str]) -> None:
    relative = _relative(root, path)
    _audit_sensitive_text(relative, text, errors)
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.endswith((" ", "\t")):
            errors.append(f"Trailing whitespace in {relative}:{line_number}")
    if text and not text.endswith("\n"):
        errors.append(f"Text file lacks a final newline: {relative}")


def _audit_sensitive_text(location: str, text: str, errors: list[str]) -> None:
    for label, pattern in SENSITIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"Possible {label} in {location}:{line}")


def _audit_json(root: Path, path: Path, text: str, errors: list[str]) -> None:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {_relative(root, path)}: {exc}")


def _audit_python(root: Path, path: Path, text: str, errors: list[str]) -> None:
    relative = _relative(root, path)
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as exc:
        errors.append(f"Invalid Python syntax in {relative}: {exc}")
        return
    docstring = ast.get_docstring(tree, clean=False) or ""
    if not docstring:
        errors.append(f"Python module lacks a file-level comment: {relative}")
        return
    for section in MODULE_SECTIONS:
        if section not in docstring:
            errors.append(f"Python module comment in {relative} lacks {section}")
    if "Key Decisions:" not in docstring and "Key Design Decisions:" not in docstring:
        errors.append(f"Python module comment in {relative} lacks Key Decisions:")


def _audit_manifest(root: Path, errors: list[str]) -> None:
    path = root / "plugins/project-governor/.codex-plugin/plugin.json"
    if not path.is_file():
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if manifest.get("name") != "project-governor":
        errors.append("Plugin manifest name must remain project-governor")
    repository = manifest.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
        errors.append("Plugin manifest repository must be a public HTTPS GitHub URL")
    author_url = manifest.get("author", {}).get("url") if isinstance(manifest.get("author"), dict) else None
    if not isinstance(author_url, str) or not author_url.startswith("https://github.com/"):
        errors.append("Plugin author URL must be a public HTTPS GitHub profile")


def _audit_actions(root: Path, path: Path, text: str, errors: list[str]) -> None:
    relative = _relative(root, path)
    if re.search(r"(?m)^permissions:\s*$", text) is None:
        errors.append(f"GitHub Actions workflow lacks explicit permissions: {relative}")
    for match in re.finditer(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", text):
        reference = match.group(1)
        if "@" not in reference:
            errors.append(f"GitHub Action lacks a version reference in {relative}: {reference}")
            continue
        revision = reference.rsplit("@", 1)[1].lower()
        if revision in {"main", "master", "head", "latest"}:
            errors.append(f"GitHub Action uses a mutable branch reference in {relative}: {reference}")


def audit(root: Path) -> list[str]:
    """Return every current-tree public-release violation."""

    errors: list[str] = []
    _audit_required_files(root, errors)
    _audit_ignored_artifacts(root, errors)
    files = _candidate_files(root)
    for path in files:
        _audit_path(root, path, errors)
        if path.is_symlink() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = _read_text(path, errors)
        _audit_text(root, path, text, errors)
        if path.suffix.lower() == ".json":
            _audit_json(root, path, text, errors)
        if path.suffix.lower() == ".py":
            _audit_python(root, path, text, errors)
        if ".github/workflows" in _relative(root, path):
            _audit_actions(root, path, text, errors)
    _audit_manifest(root, errors)
    return sorted(dict.fromkeys(errors))


def _git(root: Path, arguments: Sequence[str], errors: list[str]) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(root),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        errors.append(f"Git history inspection failed for {' '.join(arguments)}: {detail}")
        return b""
    return result.stdout


def _audit_history_path(path_text: str, errors: list[str]) -> None:
    parts = tuple(part for part in path_text.split("/") if part)
    suffix = Path(path_text).suffix.lower()
    if any(part in FORBIDDEN_PARTS for part in parts):
        errors.append(f"Forbidden generated/private path exists in Git history: {path_text}")
    if suffix in FORBIDDEN_SUFFIXES:
        errors.append(f"Forbidden credential/generated file exists in Git history: {path_text}")
    lowered_name = Path(path_text).name.lower()
    if lowered_name == ".env" or (lowered_name.startswith(".env.") and lowered_name != ".env.example"):
        errors.append(f"Environment secret file exists in Git history: {path_text}")


def audit_history(root: Path, allow_public_author_emails: bool = False) -> list[str]:
    """Return public-release violations found across every reachable Git object."""

    errors: list[str] = []
    objects_output = _git(root, ["rev-list", "--objects", "--all"], errors)
    seen_blobs = set()
    for raw_line in objects_output.decode("utf-8", errors="replace").splitlines():
        object_id, separator, path_text = raw_line.partition(" ")
        if not separator or not path_text:
            continue
        _audit_history_path(path_text, errors)
        if object_id in seen_blobs or Path(path_text).suffix.lower() in BINARY_SUFFIXES:
            continue
        object_type = _git(root, ["cat-file", "-t", object_id], errors).strip()
        if object_type != b"blob":
            continue
        seen_blobs.add(object_id)
        content = _git(root, ["cat-file", "blob", object_id], errors)
        if len(content) > 5 * 1024 * 1024:
            errors.append(f"Historical blob exceeds the 5 MiB review limit: {path_text} ({object_id[:12]})")
            continue
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        _audit_sensitive_text(f"Git blob {object_id[:12]} ({path_text})", text, errors)

    commit_text = _git(root, ["log", "--all", "--format=%H%n%B%x00"], errors)
    for record in commit_text.decode("utf-8", errors="replace").split("\0"):
        if not record.strip():
            continue
        commit_id, _, message = record.strip("\n").partition("\n")
        _audit_sensitive_text(f"commit message {commit_id[:12]}", message, errors)

    author_output = _git(root, ["log", "--all", "--format=%ae"], errors)
    public_emails = {
        email.strip().lower()
        for email in author_output.decode("utf-8", errors="replace").splitlines()
        if email.strip()
        and not email.strip().lower().endswith("@users.noreply.github.com")
        and not email.strip().lower().endswith(".invalid")
    }
    if public_emails and not allow_public_author_emails:
        errors.append(
            "Git history contains "
            f"{len(public_emails)} non-noreply author email address(es); confirm intentional disclosure, "
            "then rerun with --allow-public-author-emails"
        )
    return sorted(dict.fromkeys(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a repository candidate for public release")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--history", action="store_true", help="Also inspect every reachable Git object")
    parser.add_argument(
        "--allow-public-author-emails",
        action="store_true",
        help="Acknowledge that non-noreply commit author emails are intentionally public",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"Public release audit: ERROR\n- Repository root does not exist: {root}")
        return 2
    if args.allow_public_author_emails and not args.history:
        print("Public release audit: ERROR\n- --allow-public-author-emails requires --history")
        return 2
    errors = audit(root)
    if args.history:
        errors.extend(audit_history(root, args.allow_public_author_emails))
        errors = sorted(dict.fromkeys(errors))
    if errors:
        print("Public release audit: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    scope = "candidate files and Git history" if args.history else "candidate files"
    print(f"Public release audit: PASS ({len(_candidate_files(root))} {scope} scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
