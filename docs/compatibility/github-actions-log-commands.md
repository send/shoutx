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

Hosted results are pending. Passing local fixtures or configured variables do
not establish live consumer acceptance. Retain successful run/source/profile
identities here after the actual matrix completes.
