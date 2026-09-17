---
name: project-governor-change
description: Implement a requested change in an iOS SwiftUI repository already initialized with .governance, then run Project Governor's evidence-bound checks and independent review. Use for governed feature work; do not silently initialize, relax contracts, or approve exceptions.
---

# Project Governor Change

Solve the user's task inside the approved project boundary, then let deterministic checks and independent reviewers judge the candidate.

## Required sequence

1. Confirm `.governance/project.json` exists. If it does not, route to `$project-governor-init` rather than inventing defaults.
2. Read [references/change-protocol.md](references/change-protocol.md).
3. Read the file-level comment of every target code file before implementation. Treat documented purpose, responsibilities, inputs/outputs, non-goals, and design decisions as primary intent. If no file-level comment exists, record the assumption in the ledger and avoid overconfidence.
4. Run `prepare` before editing product code. Keep `spec.json` factual and `ledger.json` concise.
5. Implement the change without editing protected governance paths.
6. Update the ledger with reused structures, real additions, removals, affected tasks, and any needed exception.
7. Run `verify`. A failure may be revised at most twice; each revision must be a new candidate and rerun every required check.

If an exception, governance change, unavailable runtime, or conflicting standard is required, stop with `blocked`. Do not change the rule, reviewer, gate, or contract to make the current candidate pass.
