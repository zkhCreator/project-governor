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

## Recalibrate

Use `recalibrate --accept-current` after a deliberately reviewed contract edit. Add approved exceptions through a decision JSON containing `id`, `summary`, `status: approved`, `rationale`, and `exceptions`. Recalibration updates the locked governance digest and requires subsequent feature candidates to start from the new baseline.
