# Debug/group consumer verification

This note records verification setup and observations, not the command contract
or a release authorization. Behavior is owned by the
[command specification](../commands/github-actions-log-commands.md).

## Pinned source checks

Runner v2.337.0 (`397b032cbf865e9c3ddfab89d533ec19325e1273`) processes debug via
`DebugCommandExtension` and `ExecutionContextExtension.Debug`. Group and endgroup
use `GroupingCommandExtension`; these are not annotation handlers.
`tests/log_runner_fixture.rs` exports 56 producer records. The actual source
oracle checks parser data and empty properties, debug enabled/disabled, echo
on/off and stopped/resumed processing under Invariant and en-US. The local
suite passed 67 tests on 2026-10-17, including the two new culture rows.
This is local controlled evidence, not hosted-profile completion.

## Hosted setup

`.github/workflows/log-commands.yml` uses the four design-profile OS selectors
in dedicated jobs. The repository environment
`shoutx-log-command-verification` has the nonsecret variable
`ACTIONS_STEP_DEBUG=true`, configured on 2026-10-17. It contains no test secret;
do not add deployment credentials to it. This isolates debug logging from the
existing exact mask/annotation-log experiments. The Runner reads the vars
context into its debug setting before running steps; setting only a child's
environment variable is not evidence of consumer configuration.

The producer disables command echo before its measured block, requires
RUNNER_DEBUG=1, and the completed-log verifier additionally
requires actual debug records. It compares the entire sentinel-bounded sequence,
not mere marker presence, and rejects disabled debug, changed, missing or extra
records. API inventory binds each producer job to the run attempt and source
head SHA. Reports separately retain the tested checkout SHA (the synthetic
merge for pull requests), job IDs, log digests and checked counts, not full logs.
Only synthetic public text is emitted. No hostile checkout receives secrets or
write permissions. Documentation-only changes skip this workflow; manual
dispatch remains available.

Hosted run [38996144557, attempt 1](https://github.com/send/shoutx/actions/runs/38996144557)
passed on 2026-10-17 for source head
`ff169bad2e408240673c821cbda78de8c4540939`. The exact-log verifier passed for
all four profile rows, including enabled debug effects and group/endgroup
markers. Producer job IDs were `117289029260` (ubuntu-22.04), `117289029259`
(ubuntu-24.04), `117289028945` (macos-15), and `117289029244` (windows-2025).
The run's `log-command-evidence` artifact retains the tested merge SHA,
log digests and checked counts. This is a live observation, not a guarantee of
future hosted image behavior.
