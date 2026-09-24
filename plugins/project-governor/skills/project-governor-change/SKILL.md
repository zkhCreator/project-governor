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
4. Search the approved references, design-system structures, and related product surfaces before choosing a reference mode. Run `prepare --reference-mode approved` when a relevant approved pattern exists, or `prepare --reference-mode novel` when the component is genuinely new and no semantic match exists. Use `auto` only while that classification remains safely inferable. Keep `spec.json` factual and `ledger.json` concise.
5. Implement the change without editing protected governance paths.
6. Update the ledger with reused structures, real additions, removals, affected tasks, and any needed exception.
7. Run `verify`. A failure may be revised at most twice; each revision must be a new candidate and rerun every required check.

The absence of a prior component or reference sample does not by itself produce `blocked`; a declared novel component proceeds directly to the required reviewers. For `fail` or `blocked`, use the report's remediation to fix the candidate or restore evidence, then rerun all required checks within the revision limit. If the current blocker cannot be resolved in this environment, report the concrete next step and why it remains blocked. Ask the user only for a genuine decision or approval they must make. Do not change the rule, reviewer, gate, or contract to make the current candidate pass.
