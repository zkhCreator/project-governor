# Security Policy

## Supported versions

Security fixes are provided for the latest published `0.1.x` release and the current `main` branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or accidental disclosure. Use the repository's [private vulnerability reporting](https://github.com/zkhCreator/agent-team-skills/security/advisories/new) channel.

Include only the information needed to reproduce and assess the issue:

- Affected version or commit
- Impact and threat model
- Minimal reproduction steps
- Whether credentials, source code, screenshots, or governance evidence may have been exposed
- Any suggested embargo constraints

Remove live secrets and personal data from reports whenever possible. Maintainers will coordinate validation, remediation, and disclosure through the private advisory.

## Security-relevant scope

Reports are especially useful when they concern:

- Candidate or governance digest bypasses
- Reviewer bundle isolation failures
- Protected-path or read-only sandbox escapes
- Command construction, path traversal, or unsafe archive handling
- Schema validation bypasses
- Unexpected disclosure of repository files or evidence
- Supply-chain or GitHub Actions compromise

Differences in model judgment without a violated active rule or missing evidence are quality issues, not security vulnerabilities.

## Security boundary

Project Governor is a local quality gate. It does not claim to be an unbypassable security control, a CI authorization boundary, or a secrets vault. Independent review invokes the user's configured Codex CLI and is subject to that service's account, data-control, and retention settings.
