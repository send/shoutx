# Decision records

Decision records preserve why the project selected, deferred, rejected, or
replaced a design. They are not command specifications and do not independently
define observable CLI behavior.

A cross-repository decision may define constraints that the integration must
satisfy. The integration repository owns its concrete public interface and
implementation, while this repository retains the CLI and artifact contracts
identified by the documentation map.

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

Current cross-repository decisions:

- [`official-setup-action.md`](official-setup-action.md) — repository boundary
  and security constraints for the planned official installer action.

GitHub Actions stdout research scope:

- [`github-actions-unicode-scope.md`](github-actions-unicode-scope.md) — bounded
  consumer target for Unicode adoption research; not framing/release approval.
