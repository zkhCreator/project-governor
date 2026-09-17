"""
Purpose: Define Project Governor runtime identity and process exit codes.
Responsibilities: Expose stable version and pass/fail/blocked/error constants.
Inputs/Outputs: No runtime input; imported constants are the output.
Non-goals: This module does not execute workflows or load project state.
Key Design Decisions: Exit codes are part of the public automation interface.
"""

VERSION = "0.1.0"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2
EXIT_ERROR = 3
