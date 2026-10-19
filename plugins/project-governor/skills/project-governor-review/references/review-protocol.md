# Independent review protocol

## Allowed inputs

- frozen candidate files and candidate manifest;
- approved architecture, UI, and task contracts;
- approved references, including Figma nodes fetched at review time;
- active rule packs and approved decision records;
- current change spec and factual change ledger;
- current automated-check logs, screenshots, and interaction results.

Do not use main-agent chat history, self-evaluation, previous candidate reviews, or unapproved project conventions.

## iOS screenshot inspection

Open the image files referenced by the current `inputs/evidence/ui/index.json` and inspect their pixels; an attachment path or passing test log alone does not establish visual appearance. Check that the screenshot belongs to the candidate, simulator runtime, scenario, locale, and appearance under review.

When a required view is missing, the change agent should first use `xcrun simctl io <UDID> screenshot <temporary-path>` on the simulator running the verified candidate, then open the resulting PNG. If `simctl` is unavailable or cannot capture that state, use `use-computer` to inspect Simulator. Record the device, OS, scenario, locale, appearance, and candidate identity for diagnosis. Update the registered XCUITest scenario to attach that state and rerun `verify` to freeze new evidence before independent review. The isolated reviewer must not use an unbound live screen or capture as verdict evidence. Neither screenshot method replaces the registered XCUITest result needed for an interaction claim.

## Figma-node references

An approved reference may be registered in `references/index.json` as a Figma file URL and `figma_node` with no local screenshot. Fetch exactly that node through an available Figma tool (screenshot or design context) and compare it with the bundled runtime screenshots. This is the only input permitted outside the bundle. If Figma is unavailable or the node cannot be read, return the comparison as unverified and name how to obtain it; never judge the design from memory, filenames, or the index text alone.

## Verdicts

- `pass`: the candidate satisfies the assigned active rules and every required claim is verified.
- `fail`: one or more active rules have a concrete, evidence-backed violation.
- `blocked`: required evidence is missing, inconsistent, stale, or unreadable.

The reference index may legitimately be empty. When the spec declares `reference_mode: novel`, the absence of a prior component, before-state screenshot, or approved visual sample is not required evidence and must not cause `blocked`. Review the candidate against contracts, active rules, the factual ledger, related project structures, and available runtime evidence. Continue to block when evidence required to prove a concrete interaction or other active-rule claim is missing.

Every violation must cite an existing `rule_id`, the observed state, the conflict, and evidence paths. Every violation and unverified claim must include a concrete remediation and say whether a user decision is required. For missing evidence, name the test, runtime, artifact, or other proof needed and how to obtain it. For a rule violation, describe a viable correction within the approved contract; a suggested implementation is guidance, not a new requirement. If the approved sources permit several materially different choices, describe the choice and mark it for user decision rather than selecting a new policy. A reviewer cannot change the contract or promote a preference into a new rule. The reviewer does not edit the frozen candidate.

## In-session transport and trust boundary

`review_policy.transport: in-session` is a supported formal transport, not an advisory substitution. The host creates one fresh no-history subagent per request, shares only the whitelisted bundle and request metadata, and records the spawned agent ID when submitting the exact response. The reviewer must not inspect the live repository or other chats. Do not request external CLI authorization for this path.

The runtime validates candidate, governance, evidence, runtime/rules, bundle, request and reviewer identities, preserves the response receipt, rejects replays and superseded runs, and evaluates the same deterministic gate. Each role uses a separate subagent. Modified implementations require a new full verification attempt. Accepted responses cannot be overwritten.

Bundles contain separate read-only files; integrity is checked before accepting output. In-session agents share host capabilities, so this is context/input isolation and enforced content binding, not an OS access-control sandbox. The run context is frozen separately and compared before status/submission, but a same-host actor able to rewrite all anchors is outside this cooperative integrity boundary. Agent IDs attest the host's dispatch record; the runtime cannot independently authenticate model authorship. The implementing agent must never author a reviewer response. External CLI remains an explicit alternative, never an automatic fallback.
