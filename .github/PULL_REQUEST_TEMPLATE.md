## Outcome

Describe the user-visible result and why it belongs in Project Governor.

## Scope and interfaces

- Changed public commands, schemas, skills, rules, or contracts:
- Explicit non-goals:

## Validation

- [ ] `python3 scripts/public_release_audit.py --root .`
- [ ] `python3 plugins/project-governor/scripts/governor.py eval`
- [ ] Official plugin/skill validators when applicable
- [ ] Minimum supported pre-iOS-26 and iOS 26+ evidence when iOS UI/navigation is affected

List the exact commands, runtimes, and relevant evidence:

## Public-safety review

- [ ] No secrets, signing material, personal paths, private hosts, or confidential evidence
- [ ] All code, data, screenshots, and assets have known provenance and compatible licensing
- [ ] Privacy, security, changelog, and user documentation are updated when behavior changes
- [ ] New dependencies and network destinations are declared and justified
- [ ] Generated files and local governance runs are excluded

## Risks and limitations

Describe anything unverified, unavailable, or intentionally deferred.
