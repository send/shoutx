# Problem matcher consumer evidence

Status: fixed Runner and four-profile GitHub-hosted verification passed.

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
The local run passed all 69 differential tests on macOS arm64/.NET 8.0.30,
including echo on/off, stopped/resumed commands, and registering `TARGET` then
removing by `target`. This is not evidence that all arbitrary matcher
configurations work.

The hosted workflow `matchers.yml` uses fixed synthetic patterns and verifies
both raw logs and check annotations. Its sequence includes an unmatched line
before registration, positive matches after registration, absence after each
removal mode, and a still-live independent control. Relative and absolute paths
are exercised. Reports bind the run/attempt/jobs to source and tested SHAs.
Hosted run [39002778807, attempt 1](https://github.com/send/shoutx/actions/runs/39002778807)
passed on 2026-10-17 for source head
`b07ea3f53911a12f0d6f67104c7495df5824a3f6`. Producer jobs were
`117309019929` (ubuntu-24.04), `117309020166` (ubuntu-22.04),
`117309020137` (macos-15), and `117309020133` (windows-2025).
The verifier confirmed eight exact log records and five warning annotations per
profile. The `matcher-evidence` artifact retains checkout/source SHA, attempt,
job IDs and log/annotation digests. This is an observation, not a guarantee of
future hosted image behavior.

Initial runs exposed two verifier assumptions, not writer failures: Runner logs
the complete matching line but uses the captured message for annotations, and
GitHub may attach a macOS capacity notice. The verifier compares logs and
annotations independently and excludes only that observed infrastructure notice
with its exact message, notice level, `.github` path and line 1 location.
Unexpected or missing matcher effects still fail; negative tests cover both.

GPT-6 Sol reviewed the implementation and the capacity-notice adjustment without
blocking findings. Local checks also passed Rust all-target tests, Clippy with
warnings denied, formatting, stable docs, terminal stdin checks, Python verifier
tests and actionlint. CI and Codex convergence remain PR-level gates.

The [command contract](../commands/github-actions-problem-matchers.md) owns
observable behavior; the [decision](../decisions/github-actions-problem-matchers.md)
owns rationale. These observations do not extend the design-owned profile.
