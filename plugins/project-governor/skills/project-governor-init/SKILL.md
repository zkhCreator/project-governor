---
name: project-governor-init
description: Initialize or recalibrate Project Governor for an iOS SwiftUI repository by inspecting its real build, test, UI evidence, architecture, and design-system capabilities. Use for first-time project setup or an explicitly separate governance update; do not use for ordinary feature implementation.
---

# Project Governor Init

Establish a project-specific governance contract without treating the current repository as automatically correct.

## Workflow

1. Resolve the plugin root as the directory two levels above this skill's directory.
2. Read [references/init-workflow.md](references/init-workflow.md).
3. Run `python3 <plugin-root>/scripts/governor.py inspect --project-root <repo>` before proposing configuration.
4. Present only decisions the scan cannot derive: ambiguous scheme/target, approved reference screens, supported appearance policy, and unresolved conflicts.
5. After the user confirms those decisions, run `initialize` with the selected values. Initialization may write only `.governance/`.
6. For later contract or exception changes, use `recalibrate`; do not combine recalibration with a feature run.

Report each capability as available, unavailable, or blocked. Missing simulator, XCUITest, screenshot, or tool evidence must never be described as covered.
