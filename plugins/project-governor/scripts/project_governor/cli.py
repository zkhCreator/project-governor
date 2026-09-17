"""
Purpose: Expose the stable Project Governor command-line interface.
Responsibilities: Parse public subcommands, dispatch runtime operations, print JSON, and map verdicts to documented exit codes.
Inputs/Outputs: CLI argv and project files in; JSON stdout plus exit status out.
Non-goals: This module does not contain governance policy or shell-evaluate user input.
Key Design Decisions: Every normal command returns one JSON object; expected blocked states use exit code 2 rather than generic failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from . import EXIT_BLOCKED, EXIT_ERROR, EXIT_FAIL, EXIT_PASS
from .errors import GovernanceError
from .ios import inspect_project
from .state import initialize_project, prepare_change, recalibrate_project
from .workflow import plugin_root, review_existing, verify_change


def _root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Project root does not exist: {path}")
    return path


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=_root, default=Path.cwd(), help="Target Git repository")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="governor.py", description="Project Governor for iOS SwiftUI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Read-only iOS capability scan")
    _add_root(inspect_parser)

    init_parser = subparsers.add_parser("initialize", help="Create confirmed .governance state")
    _add_root(init_parser)
    init_parser.add_argument("--container")
    init_parser.add_argument("--scheme")
    init_parser.add_argument("--target")
    init_parser.add_argument("--minimum-ios")
    init_parser.add_argument("--language", action="append", default=[])
    init_parser.add_argument("--theme-policy", default="system", choices=["system", "light", "dark"])
    init_parser.add_argument("--ui-test-identifier", action="append", default=[])
    init_parser.add_argument("--reviewer-model", default="inherit")

    recalibrate = subparsers.add_parser("recalibrate", help="Relock a separately approved governance update")
    _add_root(recalibrate)
    recalibrate.add_argument("--accept-current", action="store_true")
    recalibrate.add_argument("--decision-file", type=Path)
    recalibrate.add_argument("--reviewer-model")

    prepare = subparsers.add_parser("prepare", help="Prepare a governed feature change")
    _add_root(prepare)
    prepare.add_argument("--change-id", required=True)
    prepare.add_argument("--goal", required=True)
    prepare.add_argument("--acceptance", action="append", default=[], required=True)
    prepare.add_argument("--module", required=True)
    prepare.add_argument("--ui-impact", choices=["auto", "yes", "no"], default="auto")
    prepare.add_argument("--ui-state", action="append", default=[])
    prepare.add_argument("--scope", action="append", default=[])
    prepare.add_argument("--non-goal", action="append", default=[])

    verify = subparsers.add_parser("verify", help="Run checks, evidence, reviewers, and gate")
    _add_root(verify)
    verify.add_argument("--change-id", required=True)

    review = subparsers.add_parser("review", help="Rerun independent review for an existing run")
    _add_root(review)
    review.add_argument("--run-id")
    review.add_argument("--reviewer", choices=["architecture", "ui", "both"], default="both")

    subparsers.add_parser("eval", help="Run Project Governor runtime tests")
    return parser


def _dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command == "inspect":
        return {"verdict": "pass", "inspection": inspect_project(args.project_root)}
    if args.command == "initialize":
        return initialize_project(
            args.project_root,
            args.container,
            args.scheme,
            args.target,
            args.minimum_ios,
            args.language,
            args.theme_policy,
            args.ui_test_identifier,
            args.reviewer_model,
        )
    if args.command == "recalibrate":
        decision = args.decision_file.expanduser().resolve() if args.decision_file else None
        return recalibrate_project(
            args.project_root,
            args.accept_current,
            decision,
            args.reviewer_model,
        )
    if args.command == "prepare":
        return prepare_change(
            args.project_root,
            args.change_id,
            args.goal,
            args.acceptance,
            args.module,
            args.ui_impact,
            args.ui_state,
            args.scope,
            args.non_goal,
        )
    if args.command == "verify":
        return verify_change(args.project_root, args.change_id)
    if args.command == "review":
        return review_existing(args.project_root, args.run_id, args.reviewer)
    raise GovernanceError("error", f"Unsupported command: {args.command}")


def _exit_for(verdict: str) -> int:
    return {
        "pass": EXIT_PASS,
        "fail": EXIT_FAIL,
        "blocked": EXIT_BLOCKED,
        "error": EXIT_ERROR,
    }.get(verdict, EXIT_ERROR)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "eval":
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(plugin_root() / "evals"), "-v"],
            cwd=str(plugin_root()),
            check=False,
        )
        return EXIT_PASS if completed.returncode == 0 else EXIT_FAIL
    try:
        payload = _dispatch(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return _exit_for(str(payload.get("verdict", "error")))
    except GovernanceError as exc:
        payload = {"verdict": exc.verdict, "message": exc.message, "details": exc.details}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return _exit_for(exc.verdict)
    except Exception as exc:  # defensive CLI boundary
        payload = {"verdict": "error", "message": str(exc), "type": type(exc).__name__}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_ERROR
