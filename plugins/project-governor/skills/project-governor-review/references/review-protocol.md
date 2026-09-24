# Independent review protocol

## Allowed inputs

- frozen candidate files and candidate manifest;
- approved architecture, UI, and task contracts;
- active rule packs and approved decision records;
- current change spec and factual change ledger;
- current automated-check logs, screenshots, and interaction results.

Do not use main-agent chat history, self-evaluation, previous candidate reviews, or unapproved project conventions.

## iOS screenshot inspection

Open the image files referenced by the current `inputs/evidence/ui/index.json` and inspect their pixels; an attachment path or passing test log alone does not establish visual appearance. Check that the screenshot belongs to the candidate, simulator runtime, scenario, locale, and appearance under review.

When a required view is missing, the change agent should first use `xcrun simctl io <UDID> screenshot <temporary-path>` on the simulator running the verified candidate, then open the resulting PNG. If `simctl` is unavailable or cannot capture that state, use `use-computer` to inspect Simulator. Record the device, OS, scenario, locale, appearance, and candidate identity for diagnosis. Update the registered XCUITest scenario to attach that state and rerun `verify` to freeze new evidence before independent review. The isolated reviewer must not use an unbound live screen or capture as verdict evidence. Neither screenshot method replaces the registered XCUITest result needed for an interaction claim.

## Verdicts

- `pass`: the candidate satisfies the assigned active rules and every required claim is verified.
- `fail`: one or more active rules have a concrete, evidence-backed violation.
- `blocked`: required evidence is missing, inconsistent, stale, or unreadable.

The reference index may legitimately be empty. When the spec declares `reference_mode: novel`, the absence of a prior component, before-state screenshot, or approved visual sample is not required evidence and must not cause `blocked`. Review the candidate against contracts, active rules, the factual ledger, related project structures, and available runtime evidence. Continue to block when evidence required to prove a concrete interaction or other active-rule claim is missing.

Every violation must cite an existing `rule_id`, the observed state, the conflict, and evidence paths. Every violation and unverified claim must include a concrete remediation and say whether a user decision is required. For missing evidence, name the test, runtime, artifact, or other proof needed and how to obtain it. For a rule violation, describe a viable correction within the approved contract; a suggested implementation is guidance, not a new requirement. If the approved sources permit several materially different choices, describe the choice and mark it for user decision rather than selecting a new policy. A reviewer cannot change the contract or promote a preference into a new rule. The reviewer does not edit the frozen candidate.
