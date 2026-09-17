# Governed change protocol

## Change specification

Before implementation, capture the user goal, observable acceptance criteria, owning module, affected UI states, allowed scope, explicit non-goals, and UI impact. Do not use the spec to justify a preferred implementation.

## Change ledger

Record:

- reused approved structures;
- new concepts, entry points, or interaction patterns;
- replaced or removed structures;
- existing tasks that may regress;
- exception requests;
- assumptions caused by missing file-level comments.

Adding a structure is not forbidden, but it must be visible. Do not use a mechanical one-in/one-out rule.

## Result handling

- `pass`: all required checks, evidence, digests, and reviewers agree.
- `fail`: a test or active rule has an evidence-backed violation. Revise the solution, not the rule.
- `blocked`: evidence, tooling, version, runtime, or approval is unavailable. Stop rather than guessing.

Reviewer feedback identifies violations and evidence only. The main agent remains responsible for finding a new solution.
