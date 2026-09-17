# Privacy

Project Governor has no bundled telemetry, analytics, advertising, account system, hosted backend, or external database.

## Data processed

The runtime may read source code, Git metadata, project contracts, test logs, simulator results, screenshots, and other evidence inside the repository selected by the user. Generated governance runs are stored locally under `.governance/.runs/` unless the user deliberately moves or commits them.

## Independent review

Architecture and UI review use the user's configured Codex CLI. The runtime creates a temporary, allowlisted bundle containing the frozen candidate, current change spec and ledger, approved contracts/rules/references, and current evidence. Sending that bundle to a model is governed by the user's Codex provider configuration, account terms, privacy controls, and retention policy.

The bundle excludes the main implementation conversation, self-evaluation, previous reviewer conversations, and previous candidate results.

## User controls

Before running review, users should:

- Confirm that the repository may be processed by their configured Codex provider
- Remove secrets and unnecessary personal data from source and evidence
- Avoid registering screenshots or logs that contain unrelated sensitive information
- Review `.governance/project.json` and the configured commands
- Delete local `.governance/.runs/` artifacts when they are no longer needed

Project Governor does not upload data independently of the Codex CLI and project commands explicitly invoked by the user.
