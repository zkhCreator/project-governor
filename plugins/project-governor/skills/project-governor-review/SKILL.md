---
name: project-governor-review
description: Independently review an existing Project Governor candidate using its isolated evidence bundle. Report evidence-backed violations or missing proof with concrete remediation; do not edit product code or create new blocking rules.
---

# Project Governor Review

Review only the frozen candidate and approved evidence. Do not participate in implementation.

## Workflow

1. Read [references/review-protocol.md](references/review-protocol.md).
2. When dispatched with an in-session request, do not run `review`, spawn another reviewer, or inspect the live project. Read the supplied bundle's `REVIEW_INSTRUCTIONS.md`, `REQUEST.json`, and `review-output.schema.json`; return only an envelope with `request_id`, the supplied `bundle_digest`, `evidence_digest`, and `review` matching that schema. Keep the bundle read-only. The host submits your exact response with your agent ID.
   When invoked without a request, resolve the plugin root and run `python3 <plugin-root>/scripts/governor.py review --project-root <repo> --run-id <id>`. For an in-session run this returns outstanding requests/status without launching CLI reviewers; the host must dispatch a fresh no-history subagent per request. For an authorized `codex-cli` run it retains CLI review.
3. For iOS UI review, open and inspect the current run's exported screenshot attachments. If a needed view is absent, have the change agent inspect the verified simulator with `xcrun simctl io <UDID> screenshot <temporary-path>` first, then open the PNG; use `use-computer` to inspect Simulator only when `simctl` cannot capture it. The change agent updates the registered XCUITest scenario to attach that state and reruns `verify` so it enters the frozen evidence. A live screen outside that evidence cannot support a verdict.
4. If reviewing a bundle directly, use only its candidate snapshot, change spec and ledger, approved contracts/rules/references, and current evidence.
5. Return the strict review schema. For each violation or unverified claim, provide a concrete remediation grounded in the cited rule and available evidence. State when a genuine user decision is required. The reviewer remains read-only; the change agent implements and reruns verification.

Unknown issues that are not covered by an active rule may be noted only as `unverified`; they cannot become a new blocking requirement. For `reference_mode: novel`, review the component directly and do not block solely because no prior component or screenshot exists. Missing interaction evidence required by an active rule still produces `blocked`, with a specific way to obtain the evidence. Do not end the user-facing response at `blocked`: explain the fix or evidence path and continue work where authorized. Ask the user only when the resolution needs a decision they alone can make.
