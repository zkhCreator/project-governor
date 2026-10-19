# Changelog

All notable changes to this project are documented in this file. The project follows Semantic Versioning for published plugin releases.

## Unreleased

- Add the `in-session` review transport: `review_policy.transport: in-session` exports frozen, read-only review requests for fresh host-spawned subagents, and `review-submit` validates and records each exact response against its request, bundle, and evidence digests.
- Preserve supplemental evidence across verification and isolate UI-test destinations per run.
- Accept approved references registered as Figma nodes without local screenshots; reviewers fetch the exact node at review time and report it unverified when Figma is unavailable. Document `.governance/changes/` as local working state that projects may ignore in Git.
- Allow declared novel components with no prior reference sample to proceed directly to review while preserving all active-rule and runtime-evidence requirements.
- Add public-repository governance, privacy, security, contribution, and release-readiness standards.
- Add automated public-release auditing, GitHub Actions validation, CodeQL, issue forms, and pull-request templates.

## 0.1.0 — 2026-09-17

- Add the Project Governor Codex plugin and repository marketplace.
- Add initialization, governed change, and independent review skills.
- Add the standard-library runtime, strict schemas, rule packs, evaluation corpus, and iOS/SwiftUI fixture.
- Verify the fixture on iOS 17.0 and iOS 26.5.
