# Problem matcher consumer evidence

Status: fixed Runner verification passed before the additional echo/stop matrix;
that matrix and GitHub-hosted lifecycle verification are pending.

## Source observations (2026-10-17)

Pinned Runner v2.337.0 (`397b032cbf865e9c3ddfab89d533ec19325e1273`):

- `AddMatcherCommandExtension` resolves relative file data against the workspace,
  loads and validates JSON, then registers its matchers.
- `RemoveMatcherCommandExtension` accepts either nonempty owner metadata or file
  data. File removal loads the current file and removes its configured owners;
  it is not a remembered association with the registration file.
- `ExecutionContext.AddMatchers` replaces owners using ordinal case-insensitive
  comparison; removal uses the same identity rule.
- Both handlers permit command echo; this is not a secret channel.

Sources: [command handlers](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionCommandManager.cs),
[matcher registry](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ExecutionContext.cs).

## Retained verification

The fresh 30-record producer corpus in `tests/matcher_runner_fixture.rs` is
consumed by `MatcherCommandsPreserveFieldsAndApplyEffects` in the pinned Runner.
It checks exact parsed fields under Invariant and en-US, then exercises real
add/remove handlers and the real registry with a separate control matcher.
The initial local run passed all 69 differential tests on macOS arm64/.NET
8.0.30. This is not evidence that all arbitrary matcher configurations work.

The hosted workflow `matchers.yml` uses fixed synthetic patterns and verifies
both raw logs and check annotations. Its sequence includes an unmatched line
before registration, positive matches after registration, absence after each
removal mode, and a still-live independent control. Relative and absolute paths
are exercised. Reports bind the run/attempt/jobs to source and tested SHAs.
No hosted result is claimed until that workflow passes.

The [command contract](../commands/github-actions-problem-matchers.md) owns
observable behavior; the [decision](../decisions/github-actions-problem-matchers.md)
owns rationale. These observations do not extend the design-owned profile.
