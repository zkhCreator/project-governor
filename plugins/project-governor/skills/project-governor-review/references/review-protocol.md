# Independent review protocol

## Allowed inputs

- frozen candidate files and candidate manifest;
- approved architecture, UI, and task contracts;
- active rule packs and approved decision records;
- current change spec and factual change ledger;
- current automated-check logs, screenshots, and interaction results.

Do not use main-agent chat history, self-evaluation, previous candidate reviews, or unapproved project conventions.

## Verdicts

- `pass`: the candidate satisfies the assigned active rules and every required claim is verified.
- `fail`: one or more active rules have a concrete, evidence-backed violation.
- `blocked`: required evidence is missing, inconsistent, stale, or unreadable.

The reference index may legitimately be empty. When the spec declares `reference_mode: novel`, the absence of a prior component, before-state screenshot, or approved visual sample is not required evidence and must not cause `blocked`. Review the candidate against contracts, active rules, the factual ledger, related project structures, and available runtime evidence. Continue to block when evidence required to prove a concrete interaction or other active-rule claim is missing.

Every violation must cite an existing `rule_id`, the observed state, the conflict, and evidence paths. Do not recommend colors, components, layouts, APIs, or code changes. A reviewer cannot change the contract or promote a preference into a new rule.
