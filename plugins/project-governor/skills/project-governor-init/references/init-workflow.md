# Initialization workflow

## Inspect first

`inspect` is read-only. Use its JSON report as the source of truth for project containers, schemes, deployment target, locales, navigation/design-system signals, XCUITest coverage, and installed simulator runtimes.

Classify findings as:

- `candidate_patterns`: repeated implementation patterns worth asking the user to approve.
- `legacy_risks`: existing inconsistencies that should not force an immediate repository rewrite.
- `conflicts`: choices that cannot safely be inferred.
- `capabilities`: what the runtime can actually build, test, capture, and review.

## Initialize

Run `initialize` only after scheme ambiguity and the user's real product preferences are resolved. Use repeated flags for languages and UI test identifiers. If the project lacks deterministic UI scenarios, initialize architecture review but leave UI evidence unavailable.

Initialization creates `.governance` only. It must not add an Xcode target, rewrite source files, or approve all current UI as a reference baseline.

An empty approved-reference index is valid. Do not block initialization merely because the product has no suitable reference screen or is creating its first component. Later changes must declare `reference_mode: novel` when no semantically relevant approved reference exists; this routes the candidate directly to review without treating the missing prior sample as missing evidence.

## Recalibrate

Use `recalibrate --accept-current` after a deliberately reviewed contract edit. Add approved exceptions through a decision JSON containing `id`, `summary`, `status: approved`, `rationale`, and `exceptions`. Recalibration updates the locked governance digest and requires subsequent feature candidates to start from the new baseline.

## Reviewer transport updates

For an explicitly authorized governance update, set `review_policy.transport` to `in-session` when the host supports fresh no-history subagents. Keep architecture/UI requirements, commands, rule packs and revision limits intact, document the transport decision, then run `recalibrate --accept-current`. Future changes must prepare against that baseline. Do not retroactively approve or rewrite earlier blocked/pending runs. `codex-cli` remains the compatibility default when the field is absent; it is not an automatic fallback for an in-session project.
