"""
Purpose: Represent expected governance stops without losing their verdict class.
Responsibilities: Carry pass/fail/blocked/error semantics from runtime layers to the CLI.
Inputs/Outputs: Accept a verdict, message, and optional details; expose them as an exception.
Non-goals: This module does not format user reports or catch unexpected exceptions.
Key Design Decisions: Expected blocked states are data, not generic process failures.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class GovernanceError(Exception):
    """An expected Project Governor stop with a machine-readable verdict."""

    def __init__(
        self,
        verdict: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.verdict = verdict
        self.message = message
        self.details = details or {}
