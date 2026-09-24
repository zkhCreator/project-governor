# Governed change protocol

## Change specification

Before implementation, capture the user goal, observable acceptance criteria, owning module, affected UI states, allowed scope, explicit non-goals, and UI impact. Do not use the spec to justify a preferred implementation.

## Reference mode

Search approved references, the existing design system, and related surfaces before implementation.

- `approved`: a semantically relevant approved reference exists and should be included in review.
- `novel`: the component is genuinely new and no semantically relevant approved reference exists. Record the new concept or interaction in the ledger and send it directly to review.
- `auto`: use only when the classification can remain safely inferred from the candidate and ledger.

An empty reference index or missing before-state screenshot is not, by itself, missing evidence for `novel`. Novel mode does not waive active rules, design-system search, runtime interaction evidence, accessibility, localization, state coverage, or regression checks.

## Change ledger

Record:

- reused approved structures;
- new concepts, entry points, or interaction patterns;
- replaced or removed structures;
- existing tasks that may regress;
- exception requests;
- assumptions caused by missing file-level comments.

Adding a structure is not forbidden, but it must be visible. Do not use a mechanical one-in/one-out rule.

## Result handling

- `pass`: all required checks, evidence, digests, and reviewers agree.
- `fail`: a test or active rule has an evidence-backed violation. Revise the solution, not the rule.
- `blocked`: evidence required for a concrete active-rule claim, tooling, version, runtime, or approval is unavailable. A missing prior reference alone is not a blocking reason for a declared novel component.

Reviewer feedback identifies violations, evidence, and contract-bound remediation. The main agent implements a viable correction or obtains missing proof, then reruns verification. Do not stop at a bare `blocked` verdict; explain the action needed and whether a user decision is genuinely required.
