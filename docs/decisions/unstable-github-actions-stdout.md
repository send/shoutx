# Unstable GitHub Actions stdout command isolation

Status: Proposed

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

This proposal does not change the current CLI contract by itself. The
implementation PR will update the authoritative design, command
specifications, test plan, release policy, README, and implementation plan in
the same change, then mark this record Accepted. Until then, the current
release policy continues to prohibit a tag from the pre-release stdout surface.

The Cargo feature is named `unstable-github-actions-stdout`. It is absent from
the `default` feature set. When the feature is disabled:

- the four stdout commands are not recognized by the parser or represented in
  its action types;
- their encoding modules and stdout-specific production dependency are not
  compiled into the binary;
- top-level and command help do not list them; and
- invoking any of their names is an unknown-command usage error with status 2
  and empty stdout.

The stable binary does not emit a special "disabled feature" diagnostic,
because that would advertise an unavailable command as part of its interface.
No runtime mechanism can enable the commands.

When the feature is enabled, help places the commands in an explicitly
unstable section and states that their framing decision is unresolved.
`--version` appends ` (unstable-github-actions-stdout)` so captured
logs distinguish the research build from an official binary. The feature does
not weaken validation or failure behavior defined by the existing command
specifications, but those specifications remain pre-release and do not become
a compatibility guarantee merely because the feature compiles.

Official release builds use `--no-default-features` and never enable
`unstable-github-actions-stdout`. This explicit build flag is defense in depth.
The implementation must provide a cross-platform stable-surface verifier that
inspects each packaged executable. The verifier's normative checks will live in
the release and test-plan documents rather than remain duplicated in this
decision record. The proposed checks include:

- `--help` is byte-equal to a reviewed stable-help golden file;
- each command is invoked with arguments that would succeed in an unstable
  build, while stdout is redirected to a temporary file that is never emitted
  to the workflow log;
- each invocation has status 2, empty captured stdout, and the exact ordinary
  unknown-command diagnostic;
- `--version` exactly matches the stable `shoutx VERSION` form without an
  unstable marker;
- a byte scan finds no enumerated stdout protocol marker; and
- the exact release dependency graph omits the optional stdout-only dependency.

The invocation corpus is not the sole proof of absence. All command dispatch
goes through a single enumerable command table, and a release-configuration
test asserts that its complete recognized command set equals the reviewed
stable allowlist. The unstable action variants are also absent in that
configuration, so exhaustive dispatch cannot reach their implementations. The
stable-help golden file is maintained independently rather than regenerated
from the executable. It additionally covers options, which the command-name
allowlist does not. Dependency and binary scans are defense-in-depth checks,
not proof that all aliases are absent.

Binary scanning uses an explicit marker set, including the unstable command
names and the contiguous mask protocol prefix, and a positive control: the same
scanner must find every applicable marker in an unstable artifact built for the
same target and profile. The current annotation encoder assembles its protocol
records from fragments, so no claim is made that a protocol-prefix scan alone
detects annotation commands. The source-configuration table and action-variant
checks are the primary complete-surface evidence; help, invocation, and marker
checks bind that evidence to the packaged artifact.

The README packaged in release archives describes only the stable command
surface. It may explain that stdout research exists and link to the decision,
but it does not provide unstable commands in the normal command list or quick
start. Contributor documentation and the pre-release command specifications
may document the explicit Cargo feature invocation.

## Consequences

- The next implementation change can restore release eligibility for the
  environment-file family without resolving stdout framing.
- Default `cargo build`, `cargo test`, and `cargo clippy` exercise the same
  command surface intended for official binaries.
- CI also runs tests and lints with the exact
  `--features unstable-github-actions-stdout` selection; `--all-features` is
  reserved for dependency-policy inspection. Stdout dogfooding, hosted checks,
  corpus generation, and runner differential tests use the explicitly selected
  build.
- Each unstable integration-test target declares
  `required-features = ["unstable-github-actions-stdout"]` in `Cargo.toml`.
  Explicitly selecting it without the feature is an error; implicit Cargo test
  selection may skip it. Every unstable CI job therefore explicitly selects
  its targets and also uses a feature-on sentinel or an asserted executed-test
  count. Separate default-build tests prove the commands are absent. CI does
  not rely on name-filtered test runs that can succeed after executing zero
  tests.
- MSRV coverage applies to both the release-flag and explicit unstable-feature
  configurations.
- `cargo deny --all-features` continues to cover dependencies reachable only
  from research code.
- A future stable Cargo feature requires revisiting the release use of
  `--no-default-features`; this decision does not establish a general feature
  policy for plugins or providers.

## Verification requirements

The implementation change must demonstrate all of the following before the
release gate is changed:

1. Builds using the exact release flags expose only the stable environment-file
   commands and pass their complete contract suite. CI asserts the complete
   `[features]` table, including that `default` is empty and that optional
   dependencies do not create unintended implicit features. Per-configuration
   dependency graphs also ensure that test or self-dependencies do not enable
   the unstable feature accidentally.
2. Explicit unstable-feature builds expose the unstable section, carry the
   version marker, and pass the existing mask, annotation, corpus, and
   runner-oracle suites.
3. Default-build negative tests invoke all four omitted command names and
   assert status 2, empty stdout, and the exact ordinary unknown-command
   diagnostic. Their arguments would succeed if the feature were present.
4. Release-workflow dry runs build with `--no-default-features` and repeat the
   layered stable-surface checks against every packaged native executable.
5. A shared stable-surface verifier runs both in ordinary CI and release
   packaging. A source-configuration test compiled in the same job with the
   same toolchain, target, profile, lockfile, and feature flags asserts the
   parser table and action variants. Artifact checks compare help with a
   reviewed, LF-stable golden file; check version and successful-form negative
   invocations using captured files; and scan enumerated markers with an
   unstable-build positive control. The job verifies dependency graphs with
   `--locked`, the release target, and positive and negative feature
   configurations. Failure messages report only the length or digest of every
   captured stream, including stdout, stderr, help, and version. Captures are
   not uploaded as artifacts, and negative invocations use fixed, non-secret
   arguments.
6. Stable and unstable builds use separate Cargo target directories. Every
   dogfood group asserts both that the executable path is under the expected
   target directory and that `--version` has the expected output before
   invoking it. Packaging applies the same identity checks; its unstable scan
   control never enters `dist` or an uploaded artifact. Environment-file and
   stdout workflow smoke tests are separate.
7. Corpus-generation scripts remove any previous output before export, require
   every expected file to be newly created, and explicitly select test targets.
   Every intended unstable suite has a feature-on sentinel or an asserted
   non-zero executed-test count in addition to Cargo `required-features`.
8. README-only changes run an always-required lightweight stable-surface
   documentation job; source, manifest, or release-workflow changes run the
   full stable verifier. For every tag, the release workflow itself reruns the
   stable contract suite with the release feature flags and the dependency
   policy check, then runs the stable verifier against every packaged artifact.
   It therefore never treats a successful aggregate CI result with skipped
   relevant jobs as sufficient release evidence.
9. The release README contains a delimited stable-command block checked against
   the independently maintained allowlist, while prose may link to research.
   Every `shoutx PROVIDER:DESTINATION` invocation in its code blocks must also
   name a stable command. Executable help is checked against the same allowlist
   and its independent golden file rather than against a denylist of current
   unstable names.
10. CI feature selection is explicit for every stdout hosted or differential
   job; a missing feature must fail rather than silently skip intended evidence.

Before this record becomes Accepted, the implementation PR moves the detailed
requirements in the proposed-decision and verification sections to their
authoritative owners and replaces those details here with links. It changes the
release policy from its current commit-level prohibition to the artifact gate;
updates the test plan's feature matrices and version assertions; updates the
threat model's release declaration; and updates the design command surface,
implementation plan, README, command specifications, and contributor
verification guidance. It also adjusts hosted-log job lookup and workflow
smoke-test consumers that currently assume stdout commands are present in the
default build.

Release eligibility remains authoritative in [`../release.md`](../release.md),
shared verification policy in [`../test-plan.md`](../test-plan.md), and
observable command behavior in the command specifications. The implementation
PR updates those owners together rather than treating this rationale as a
second contract.

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
