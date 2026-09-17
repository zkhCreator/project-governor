# Contributing

Thank you for helping improve Project Governor. Contributions should preserve its evidence-bound, fail-closed design and keep the repository safe to publish.

## Before starting

1. Search existing issues and pull requests.
2. Open an issue for material behavior, rule, schema, or governance changes.
3. Keep one pull request focused on one problem.
4. Read the file-level comment before changing any code file. Treat its purpose, responsibilities, inputs/outputs, non-goals, and key decisions as the primary intent.

## Development requirements

- Python 3.9 or later
- Git
- Codex CLI for reviewer integration work
- Xcode and relevant simulators for iOS adapter or fixture changes

Run the runtime suite:

```bash
python3 plugins/project-governor/scripts/governor.py eval
```

Run the repository public-release audit:

```bash
python3 scripts/public_release_audit.py --root .
```

Plugin and skill changes must also pass the official Codex `validate_plugin.py` and `quick_validate.py` validators. iOS navigation or UI-evidence changes require representative XCUITest results on the minimum supported pre-iOS-26 runtime and iOS 26 or later.

## Design constraints

- Do not weaken a gate, contract, digest, protected path, or reviewer schema to make a candidate pass.
- Reviewer output may report evidence-backed conflicts and missing evidence, but must not prescribe a solution.
- Do not add product-specific business rules to the generic plugin.
- Keep the runtime compatible with Python 3.9+ and the standard library unless a dependency is separately justified and reviewed.
- Preserve native iOS navigation, accessibility, interactive pop, semantic colors, localization, and availability-gated iOS 26 behavior.
- Every Python file must start with a structured module comment containing Purpose, Responsibilities, Inputs/Outputs, Non-goals, and Key Decisions.

## Public-safety checklist

Every pull request must confirm that it contains no:

- Credentials, tokens, private keys, signing files, or `.env` contents
- Personal absolute paths, private hostnames, or internal-only URLs
- Proprietary code, data, screenshots, or assets without redistribution rights
- Xcode `xcuserdata`, DerivedData, result bundles, or other generated artifacts
- Third-party code or assets without compatible license and attribution

See [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) for the complete release gate.

## Pull requests

Describe the user-visible outcome, changed contracts or public interfaces, tests run, and evidence limitations. Reviewers may request a smaller change when a pull request mixes policy, runtime, and product behavior.

By submitting a contribution, you represent that you have the right to submit it and agree that it is licensed under the repository's [Apache License 2.0](LICENSE).

All contributors must follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
