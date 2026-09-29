# Decision records

Decision records preserve why the project selected, deferred, rejected, or
replaced a design. They are not command specifications and do not independently
define observable CLI behavior.

Each record has one of these statuses:

- **Proposed**: under review and not authoritative;
- **Accepted**: the current design decision;
- **Deferred**: deliberately postponed until stated conditions change;
- **Rejected**: considered and not selected; or
- **Superseded**: replaced by a linked later decision.

New records should use a stable descriptive filename and this structure where
applicable:

```text
# Decision title

Status: Proposed

## Context
## Decision drivers
## Considered options
## Decision
## Consequences
## Verification requirements
## Reconsideration conditions
## Evidence
```

Evidence belongs in a compatibility note when it is independently useful or
likely to evolve with an external runtime. The decision record links to that
evidence rather than duplicating observations, version matrices, or test
results. Release eligibility remains authoritative in `docs/release.md`.
