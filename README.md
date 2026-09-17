# Project Governor

[English](README.md) | [简体中文](README.zh-CN.md)

Project Governor is a Codex plugin for governing iOS and SwiftUI changes with explicit project contracts, reproducible evidence, and independent review.

Version `0.1.0` is an iOS/SwiftUI MVP. It is a local quality gate, not an unbypassable security boundary.

## Why Project Governor?

Feature work tends to accumulate screens, concepts, entry points, and one-off interaction patterns. Project Governor makes those costs visible before a change is accepted:

- Project intent is written down before feature implementation.
- Existing code is evidence, not automatically the correct design standard.
- Product changes cannot silently modify contracts, exceptions, or reviewer settings.
- Build, test, simulator, screenshot, and interaction claims must have real evidence.
- Architecture and UI reviewers receive isolated, read-only bundles without the implementation conversation.
- The final gate uses explicit conditions rather than a weighted score.

## Public skills

| Skill | Purpose |
| --- | --- |
| [`project-governor-init`](plugins/project-governor/skills/project-governor-init/SKILL.md) | Inspect an iOS project, initialize `.governance`, or separately recalibrate an approved contract. |
| [`project-governor-change`](plugins/project-governor/skills/project-governor-change/SKILL.md) | Prepare and implement a bounded feature change, collect evidence, and run the gate. |
| [`project-governor-review`](plugins/project-governor/skills/project-governor-review/SKILL.md) | Rerun a read-only architecture or UI review without editing code or prescribing a solution. |

## How it works

```text
inspect → user confirmation → initialize
                              ↓
                     prepare a change
                              ↓
                    implement candidate
                              ↓
           build/test + simulator evidence
                              ↓
         isolated architecture/UI reviewers
                              ↓
                    pass / fail / blocked
```

The gate passes only when all required checks and reviewers pass, all evidence is present, protected governance state and locked versions match, no candidate drift occurs, and no claim remains unverified.

## Requirements

- macOS
- Git
- Python 3.9 or later; the runtime uses only the standard library
- Codex CLI
- Xcode and the required iOS Simulator runtimes
- A shared Xcode scheme for build and UI-test evidence

UI changes are blocked when deterministic XCUITest scenarios or required runtimes are unavailable. Architecture-only review can still run.

## Install

Install the repository marketplace and then the plugin:

```bash
codex plugin marketplace add zkhCreator/agent-team-skills
codex plugin add project-governor@personal
```

For local development:

```bash
git clone https://github.com/zkhCreator/agent-team-skills.git
codex plugin marketplace add /absolute/path/to/agent-team-skills
codex plugin add project-governor@personal
```

Verify the installation with:

```bash
codex plugin list
```

## Quick start

Open an iOS/SwiftUI repository in Codex and initialize its contract:

```text
Use $project-governor-init to inspect this repository and help me initialize its governance contract.
```

For a feature change:

```text
Use $project-governor-change to implement this feature under the approved project contract: <goal>.
```

For an independent rerun of the latest review:

```text
Use $project-governor-review to review the latest Project Governor candidate.
```

The initialization skill intentionally separates read-only inspection from writes. It asks for confirmation when the Xcode container, scheme, product preference, reference screen, or other contract decision cannot be safely inferred.

## Runtime CLI

The bundled runtime exposes seven stable commands:

```text
governor.py inspect       Read-only project and capability scan
governor.py initialize    Create confirmed .governance state
governor.py recalibrate   Relock a separately approved governance update
governor.py prepare       Create a change spec and factual ledger
governor.py verify        Freeze, check, collect evidence, review, and gate
governor.py review        Rerun review for an existing frozen run
governor.py eval          Run the plugin's test suite
```

Example read-only scan:

```bash
python3 plugins/project-governor/scripts/governor.py inspect \
  --project-root /path/to/ios-project
```

Exit codes are part of the automation interface:

| Code | Meaning |
| --- | --- |
| `0` | Pass |
| `1` | Evidenced check or rule failure |
| `2` | Blocked by missing evidence, incompatible versions, unavailable tooling, drift, or governance conflict |
| `3` | Configuration or internal error |

## Project-owned state

Initialization writes only `.governance/` in the target repository. Important artifacts include:

```text
.governance/
├── project.json
├── lock.json
├── contracts/
├── references/
├── decisions/
├── changes/<change-id>/
└── .runs/<run-id>/
```

Contracts, decisions, reference configuration, and `lock.json` are protected. A normal feature run cannot change them. If a change needs an exception or new standard, the feature is blocked until a separate `recalibrate` operation approves and locks that decision.

## Independent review

Each reviewer runs in a fresh temporary directory through an ephemeral Codex process with a read-only sandbox and strict JSON output schema. The bundle contains only:

- The frozen candidate snapshot
- The current change spec and factual ledger
- Approved contracts, rules, and references
- Current build, test, screenshot, and interaction evidence
- Bound candidate, contract, and evidence digests

It excludes the main implementation conversation, self-evaluation, prior reviewer conversations, and previous candidate results. Reviewers report rule conflicts and evidence gaps; they do not propose fixes or add temporary rules.

## iOS and SwiftUI policy

The first release enforces several platform-specific boundaries:

- Search for and reuse the project's design system before adding UI vocabulary.
- Preserve native navigation bars, back accessibility, and interactive pop.
- Centralize pre-iOS-26 compatibility in a shared appearance layer.
- Keep iOS 26 and later native Liquid Glass behavior behind availability boundaries.
- Use project semantic colors, localization, and light/dark-mode policy.
- Require both the minimum supported pre-iOS-26 runtime and iOS 26+ evidence for navigation changes.
- Use registered XCUITest scenarios and exported `.xcresult` attachments for interaction claims.

## Development and validation

Run the standard-library test suite:

```bash
python3 plugins/project-governor/scripts/governor.py eval
```

The repository currently includes:

- Unit coverage for digests, untracked files, protected state, rule routing, exit codes, and the gate truth table
- Fake-Codex integration coverage for reviewer isolation, schema enforcement, invalid JSON, extra fields, process failure, and timeout
- A rule corpus with compliant, architecture-violation, UI-violation, missing-evidence, and holdout cases
- A minimal SwiftUI app and UI-test target covering native navigation, edge-swipe return, scrolling, sheets, English, Simplified Chinese, light mode, and dark mode

The fixture has been verified on iOS 17.0 and iOS 26.5, with screenshot attachments exported from both result bundles.

## Repository layout

```text
.agents/plugins/marketplace.json
plugins/project-governor/
├── .codex-plugin/plugin.json
├── skills/
├── scripts/
├── rules/
├── schemas/
└── evals/
```

The plugin does not include an MCP server, hosted service, external database, or SaaS dependency.

## Public repository standard

This repository is prepared for public collaboration under the [Apache License 2.0](LICENSE). Before publishing a revision, run:

```bash
python3 scripts/public_release_audit.py --root .
python3 -m unittest discover -s tests -v
python3 plugins/project-governor/scripts/governor.py eval
```

The automated audit checks the current candidate tree for required community files, common credential material, private absolute paths, generated artifacts, structured Python module comments, JSON validity, workflow permissions, and public plugin metadata. It does not replace the mandatory full-history, ownership, and GitHub-settings review in the [public release standard](docs/PUBLIC_RELEASE.md).

Before changing repository visibility, also run `python3 scripts/public_release_audit.py --root . --history`. Non-noreply commit emails require deliberate acknowledgment; see the release standard before using the acknowledgment flag.

Project policies:

- [Security reporting](SECURITY.md)
- [Privacy and local data handling](PRIVACY.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)
- [Changelog](CHANGELOG.md)

## Current boundaries

- iOS and SwiftUI only in `0.1.0`
- Local quality gate rather than merge protection or a security sandbox
- No cloud evidence storage or CI credential management
- No public marketplace release workflow yet
- Review quality remains bounded by approved contracts, available evidence, and active rule packs
