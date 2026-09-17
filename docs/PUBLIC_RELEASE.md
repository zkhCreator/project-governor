# Public Release Standard

This document defines when the repository is safe to make public and when a revision is safe to publish. Passing the automated audit is necessary but not sufficient.

## Mandatory repository properties

- The repository contains README, license, notice, privacy, security, contribution, conduct, support, and changelog files.
- Public documentation describes actual behavior and does not promise unavailable security guarantees.
- Plugin and marketplace manifests validate and contain only public metadata.
- Every tracked file has known provenance and redistribution rights.
- No credential, signing material, private key, personal absolute path, private hostname, proprietary asset, or confidential evidence is present.
- Generated Xcode, Python, simulator, and governance-run artifacts are ignored.
- CI uses least-privilege permissions and supported upstream action versions.
- Runtime behavior and public interfaces are covered by tests proportional to their risk.

## Required checks

Run from the repository root:

```bash
python3 scripts/public_release_audit.py --root .
python3 -m unittest discover -s tests -v
python3 plugins/project-governor/scripts/governor.py eval
```

Before first public visibility, also scan every reachable Git object:

```bash
python3 scripts/public_release_audit.py --root . --history
```

The history audit fails closed when commits contain non-noreply author emails. After the author has confirmed that those identities are intentionally public, acknowledge that specific manual decision with `--allow-public-author-emails`. This acknowledgment does not suppress any secret, private-path, or forbidden-file finding.

Plugin or skill changes must also pass the official Codex plugin and skill validators. Adapter, fixture, navigation, screenshot, or XCUITest changes require successful evidence on the minimum supported pre-iOS-26 runtime and iOS 26 or later.

## Manual review before first public visibility

The automated history audit detects the configured secret patterns in reachable text blobs, but it is not a proof that every possible secret or confidential binary is absent. Before changing repository visibility:

1. Confirm the audit covered every intended commit and branch, not only `HEAD`.
2. Run GitHub secret scanning or a second history-aware scanner when available.
3. Remove leaked credentials from history and revoke/rotate them before publication.
4. Confirm that commit author names and email addresses are intentionally public.
5. Review screenshots, logs, fixtures, test data, bundle identifiers, remote URLs, and Git metadata.
6. Confirm ownership or compatible licensing for every copied file and asset.
7. Confirm that the security advisory and conduct-reporting channels are available to maintainers.
8. Review repository visibility, Actions permissions, branch protection, private vulnerability reporting, and secret-scanning settings on GitHub.

## Change review rules

- Any new dependency requires a license, maintenance, provenance, and data-flow review.
- Any new network destination requires documentation, privacy review, and an explicit user-controlled purpose.
- Any new evidence type must define retention, redaction, and reviewer-bundle behavior.
- Any new GitHub Action must use an official or specifically approved publisher and least-privilege permissions.
- Public examples must use reserved domains, synthetic data, and non-routable credentials.
- Exceptions must be documented in the pull request and approved before merge.

## Release decision

A public release is blocked when any required check fails, evidence is missing, provenance is unknown, or the reviewer cannot determine whether data is safe to disclose. Uncertainty is resolved before publication; it is not converted into an assumed pass.
