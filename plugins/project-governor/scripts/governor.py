#!/usr/bin/env python3
"""
Purpose: Provide the executable entry point for the Project Governor plugin.
Responsibilities: Add the bundled runtime package to Python's import path and delegate to the CLI.
Inputs/Outputs: Process argv in; JSON stdout and documented process exit code out.
Non-goals: This file contains no governance policy or project-specific behavior.
Key Design Decisions: The runtime is self-contained and uses only Python 3.9+ standard library modules.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from project_governor.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
