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
7. Run `verify` using the configured `review_policy.transport`. With `in-session`, successful check execution returns `verdict: pending`, `phase: awaiting_review`, and `review_requests`; this is a handoff, not a pass or an authorization blocker. For each request, spawn a separate fresh in-session subagent with `fork_turns="none"`, a read-only assignment, its `bundle_path`, supplied `bundle_digest`, and the returned instructions. Give no implementation conversation or prior review findings. The reviewer reads only the bundle and returns the strict response envelope. Save its exact response outside the bundle and candidate (inside the ignored run directory), then call `review-submit --project-root <repo> --run-id <id> --reviewer <role> --agent-id <spawned-agent-id> --response <file>`. Do not author, repair, or amend reviewer verdicts. Continue until all requests are submitted and the gate returns pass/fail/blocked. If malformed output is rejected, ask the same reviewer to correct only its format; never manufacture a verdict. A failure may be revised at most twice; each implementation revision must be a new candidate and rerun every required check.
8. `in-session` never falls back to `codex exec`; report a concrete capability blocker only if the host cannot create fresh agents. External CLI review remains available for separately authorized projects configured with `codex-cli`. An ordinary advisory review is not a formal review: only a request-bound response validated by `review-submit` counts.

The absence of a prior component or reference sample does not by itself produce `blocked`; a declared novel component proceeds directly to the required reviewers. For `fail` or `blocked`, use the report's remediation to fix the candidate or restore evidence, then rerun all required checks within the revision limit. If the current blocker cannot be resolved in this environment, report the concrete next step and why it remains blocked. Ask the user only for a genuine decision or approval they must make. Do not change the rule, reviewer, gate, or contract to make the current candidate pass.
