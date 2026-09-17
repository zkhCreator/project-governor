---
name: project-governor-review
description: Independently review an existing Project Governor candidate for architecture or UI contract violations using its isolated evidence bundle. Use when asked to review or rerun a governed candidate; do not edit product code, propose solutions, or create new blocking rules.
---

# Project Governor Review

Review only the frozen candidate and approved evidence. Do not participate in implementation.

## Workflow

1. Read [references/review-protocol.md](references/review-protocol.md).
2. Resolve the plugin root and run `python3 <plugin-root>/scripts/governor.py review --project-root <repo> --run-id <id>`.
3. If reviewing a bundle directly, use only its candidate snapshot, change spec and ledger, approved contracts/rules/references, and current evidence.
4. Return the strict review schema. Report observations and conflicts; never prescribe a change.

Unknown issues that are not covered by an active rule may be noted only as `unverified`; they cannot become a new blocking requirement. Missing interaction evidence produces `blocked`, not an inferred pass.
