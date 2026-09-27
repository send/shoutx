# Pinned runner parser oracle

This test-only xUnit fixture calls `EnvFileKeyValuePairs` and
`AddPathFileCommand.ProcessCommand` from the pinned `actions/runner` checkout
directly. It does not copy or translate the runner's parser implementation.
The fixture also routes effective PATH composition through the runner's
`Handler.AddPrependPathToEnvironment` implementation. On native Linux it runs
the actual `ContainerStepHost` and `ProcessInvoker` against a test helper in
place of Docker, recording how the runner tokenizes its constructed argv.

The baseline is:

- tag: `v2.337.0`
- commit: `397b032cbf865e9c3ddfab89d533ec19325e1273`
- .NET SDK: `8.0.424` (the version pinned by that runner source tree)

CI checks out that exact commit, copies `ShoutxDifferentialL0.cs` into the
runner's existing Test project, builds through the runner's own build graph,
and runs only this fixture with a fully-qualified-name filter. The test reads a
shared JSON corpus whose names, values, and complete input files are base64
encoded so the fixture format cannot alter parsed line boundaries.

The local helper accepts an existing pinned checkout through
`SHOUTX_RUNNER_SOURCE`. It exports that commit into a temporary directory
before adding the fixture, so the caller-owned checkout is never modified.

The pinned runner currently restores transitive packages with published
security advisories. CI therefore disables NuGet audit only for this isolated,
test-only historical oracle build. Those packages are not linked into or
distributed with `shoutx`.
