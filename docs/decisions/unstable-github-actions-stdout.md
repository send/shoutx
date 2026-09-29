# Unstable GitHub Actions stdout command isolation

Status: Accepted

## Context

The implemented `github-actions:mask`, `github-actions:notice`,
`github-actions:warning`, and `github-actions:error` commands depend on the
runner's stdout workflow-command parser. The
[stdout framing decision](github-actions-stdout-framing.md) remains Proposed
because the consumer uses locale-sensitive parsing that shoutx cannot observe
or make reliable from the producer process.

Keeping these commands in the default executable blocks releases of unrelated
environment-file writers. Removing their source would discard useful parser,
encoder, and differential-test work. The project therefore needs a boundary
between code retained for security research and commands shipped as supported
user functionality.

This is distribution isolation, not a repair for stdout framing. Enabling the
code does not make the runner protocol safe or satisfy its release gates.

## Decision drivers

- Official release binaries must not expose a command whose security contract
  depends on the unresolved stdout framing decision.
- `github-actions:output`, `env`, `state`, and `path` must remain independently
  releasable.
- Parser and encoder research must remain executable in CI without presenting
  the commands as part of the normal CLI.
- Accidental inclusion in a release must fail verification even if Cargo
  defaults change later.
- A locally built research binary must be distinguishable from an official
  stable-surface binary.
- There must be no runtime environment variable or hidden option that enables
  omitted commands in an official binary.

## Considered options

### Keep the commands in every binary and rely on documentation

Rejected. A command that accepts a secret and exits successfully can still be
misread as a security guarantee. A release note is not an execution boundary.

### Remove the implementations until framing is resolved

Rejected for now. The implementations and runner oracle are useful evidence,
and deleting them would make continued investigation harder without improving
the stable binary beyond what compile-time exclusion provides.

### Add a runtime opt-in

Rejected. An environment variable, configuration file, or hidden flag could be
enabled accidentally or by surrounding workflow state. The unsupported command
surface must be absent from the executable.

### Publish a second experimental binary

Rejected for the current phase. Publishing it would create another artifact
that users could mistake for a supported security primitive and would require
its own naming, provenance, installation, and support policy.

### Use an opt-in Cargo feature

Accepted. Source builds and CI can include the research surface deliberately,
while default and release builds compile it out.

## Decision

Retain the stdout workflow-command research behind the opt-in Cargo feature
`unstable-github-actions-stdout`. The default feature set is empty, and no
runtime mechanism can enable compiled-out commands. Official releases use
`--no-default-features` and contain only the stable environment-file surface.

Feature-enabled builds identify themselves in help and version output and do
not acquire stable compatibility status. The observable stable and research
surfaces are authoritative in [the design](../design.md) and the individual
[command specifications](../commands/). Shared build-configuration and artifact
verification requirements live in [the test plan](../test-plan.md), and release
eligibility lives in [the release design](../release.md).

## Consequences

- The boundary restores release eligibility for the environment-file family
  without resolving stdout framing.
- Contributor and CI work must deliberately choose between the supported and
  research configurations; the authoritative matrix is in the
  [test plan](../test-plan.md).
- Research remains executable against the pinned and hosted runner evidence
  without being distributed as a supported primitive.
- A future stable Cargo feature requires revisiting the release use of
  `--no-default-features`; this decision does not establish a general feature
  policy for plugins or providers.

## Reconsideration conditions

Remove the feature boundary only after the stdout framing decision becomes
Accepted, its required runner evidence passes, the command specifications are
updated to the accepted framing, and the release policy admits the family.

Reconsider deletion or relocation of the research code if maintaining the
all-feature path delays stable security fixes, creates dependency risk, or
repeatedly allows unstable behavior to leak into default artifacts.

## Evidence

- [GitHub Actions stdout framing decision](github-actions-stdout-framing.md)
- [GitHub Actions workflow-command parser compatibility](../compatibility/github-actions-workflow-command-parser.md)
- [Release design](../release.md)
- [shoutx v0.2.0 release](https://github.com/send/shoutx/releases/tag/v0.2.0)
  (the published executable exposes only the stable environment-file commands)
