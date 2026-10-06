# Design notes

This document defines cross-cutting product decisions and indexes the current
destination-specific contracts. Deferred alternatives are explicitly labeled
and live in decision records rather than inheriting normative status from this
index.

Security scope and trust assumptions are defined in the
[threat model](threat-model.md).
The contract-derived verification matrix is defined in the
[CLI contract test plan](test-plan.md).
Implementation sequencing and Rust-specific architecture are defined in the
[Rust implementation plan](implementation-plan.md).
Destination-specific contracts and deferred-feature decisions are indexed
below and live under [`commands/`](commands/) and [`decisions/`](decisions/).

## Product boundary

`shoutx` prevents injection when CI workflows write values across output
boundaries. It provides destination-specific runtime writers rather than
static workflow analysis or attack-path discovery. A reusable context encoder
would require its own concrete, safely consumable boundary; none is currently
planned for v1.0.

The initial provider is GitHub Actions. Provider-specific behavior is isolated
behind namespaced commands so support for other workflow engines can be added
without pretending their protocols are interchangeable.

## GitHub Actions commands

Provider-specific writers:

```text
shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:state  [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:path   [VALUE]
```

The stdout workflow-command implementations are retained for research behind
the opt-in Cargo feature `unstable-github-actions-stdout`:

```text
shoutx github-actions:mask    [VALUE]
shoutx github-actions:notice  [ANNOTATION OPTIONS] [MESSAGE]
shoutx github-actions:warning [ANNOTATION OPTIONS] [MESSAGE]
shoutx github-actions:error   [ANNOTATION OPTIONS] [MESSAGE]
```

The feature is absent from the default set and from official release binaries.
Feature-enabled help labels this family unstable, and its version output carries
the feature name. This research surface is not a compatibility guarantee.

No reusable context encoder is currently planned for v1.0. The former
`shell:arg` candidate is deferred after boundary review.

## Security invariants

1. A command protects only the interpretation boundary named by that command.
2. Validation, encoding, and resource-limit failures occur before stdout output
   begins. I/O failure after writing begins may leave partial bytes.
3. Every non-multiline GitHub Actions writer consumes at most one final line
   boundary as input framing before applying its mode-specific rule.
4. Discarding or normalizing content beyond that framing boundary is always
   explicit.
5. Multiline framing never uses a delimiter that can terminate the value.
6. NUL is rejected.
7. Raw passthrough is not provided.
8. Names and paths are validated according to their destination protocol.
9. Diagnostics never include untrusted values unless safely represented.
10. Documentation distinguishes structural encoding from authorization and
   semantic validation.
11. Documentation does not imply protection from injection that occurs before
   `shoutx` starts or after its selected boundary has been crossed.
12. Input is strict UTF-8 and output is UTF-8 without a byte-order mark.
    Framing bytes are chosen for semantic round trips through the local
    supported runner parser and do not rely on host text-mode translation.
13. Every input field has a documented hard size limit; a destination's encoded
    record limit may impose a smaller effective maximum after framing.
14. A stdout workflow-command writer must emit exactly one command line whose
    decoded data equals the accepted value; it does not claim that runner log
    masking prevents every disclosure of that value.
15. Syntax defined by shoutx uses only ASCII code points. Matching is exact
    unless a rule explicitly specifies ASCII-only case folding; non-ASCII
    lookalikes, normalization equivalence, Unicode case folding, and
    locale-sensitive comparison do not create command names, option names,
    delimiters, property names, numeric syntax, or escape syntax. A
    command-specific value may accept strict UTF-8 as opaque data.
16. A destination guarantee names its consumer compatibility scope and relies
    on that consumer's protocol implementation, not on producer-side discovery
    of hidden consumer settings. Producer success is not evidence that a
    separate consumer accepted the record. Known incompatibilities must be
    disclosed and handled through the compatibility and release process.

These are product requirements, not a mandate to prove dependency internals.
The [stdout threat inventory](threat-model.md#stdout-mask-and-annotation-responsibility)
distinguishes concrete security paths from functional behavior and deployment
conditions. Invariant 16 does not prohibit adopting a protocol implemented with
locale-sensitive operations. It requires a usable scope and an honest account
of dependency assumptions; it neither transfers shoutx's own structural
protection obligations to the caller nor requires proof of dependency internals.

The current GitHub Actions stdout parser investigation and the limits of its
cross-platform evidence are recorded in
[the workflow-command compatibility note](compatibility/github-actions-workflow-command-parser.md).
The compile-time-isolated stdout family remains pre-release. The
[framing decision](decisions/github-actions-stdout-framing.md) governs adoption;
it does not itself change the distributed command surface.

## Stdout adoption contract

This section defines the scope for productizing the existing mask and
notice/warning/error implementations, including message, TITLE, and FILE. It
does not enable them in official binaries. Their observable input and encoding
rules remain solely in the command specifications.

Shoutx owns validation, context-specific escaping, command/property framing,
bounded resource use, value-free diagnostics, and rejection before output.
The Runner owns interpreting the resulting command and applying the effect;
its runtime and OS own their implementation behavior. Callers own safe input
delivery, selecting the intended destination, keeping workflow-command
processing active, and avoiding disclosure before mask registration. Success
means that shoutx wrote the prepared record, not that the Runner acknowledged
it. Mask is not a general secret-management or retrospective log-cleaning tool.

The initial adoption profile is native jobs on standard GitHub-hosted
Ubuntu 22.04 x64, Ubuntu 24.04 x64, macOS 15 arm64, and Windows 2025 x64 images,
without replacing the Runner/runtime or customizing its globalization settings.
The en-US and Invariant controlled-package configurations are reference
verification targets, not settings users must discover or assert for the live
Worker. Existing live integration observations are separate evidence: they do
not identify that process's culture or backend. The maintainer owns comparing
observations and classifying compatibility, rather than asking users to attest
to unobservable Worker properties.

Users can select the named OS generation and avoid consumer customization.
They cannot pin every hosted-image component or make shoutx acknowledge a
consumer effect. Shoutx does not attempt runtime detection or enforcement of
this profile. Moving aliases must still resolve to a named generation; a new
OS generation is not automatically included. Self-hosted runners, containers,
custom globalization configurations, other cultures, and other OS generations
are not initially covered by the adoption profile. This is a compatibility
scope, not a claim that every excluded environment is unsafe.

The [compatibility record](compatibility/stdout-unicode-policy.md) owns observed
versions, coverage, and known mismatches. A passing finite hosted smoke test
does not override a known broader incompatibility on a different configuration.
In particular, the recorded local ICU 78.1 mismatch is not erased by the
macOS 26 hosted smoke success. Neither arbitrary future dependency versions
nor all Unicode/consumer combinations are certified by these observations.

Within the profile, dependency correctness is an explicit assumption, as it is
for other output destinations. A concrete failure affecting command structure,
property interpretation, or mask confidentiality must be assessed against the
[attack inventory](threat-model.md#stdout-mask-and-annotation-responsibility),
not dismissed as somebody else's bug. A functional display mismatch is not
automatically injection. Update verification, pending-status communication,
and responses to incompatibility are owned by the [release policy](release.md).
No hidden fallback, normalization, decoration, or lossy sanitization is added
by this adoption contract.

## Distribution integrations

An official GitHub Action will install an exact released `shoutx` version from
the native artifacts without duplicating their publication contract. Its
repository boundary, verification requirements, and initial no-cache policy
are recorded in the
[official setup action decision](decisions/official-setup-action.md). The
action is not part of the current CLI surface and is not available until its
separate repository publishes an immutable release.

## Command model

Provider writers use `PROVIDER:DESTINATION`. Reusable encoders use
`LANGUAGE:CONTEXT`.

A value argument is used when present. Otherwise, input is read from stdin when
stdin is not a terminal. Reading normally continues through EOF, but may stop
when the first byte beyond the hard limit proves the input must be rejected.
With no value and terminal stdin, commands fail with usage status 2 instead of
waiting. An unreadable stdin error exposed by the host API has status 1. On
POSIX, however, Rust runtime initialization replaces an inherited descriptor
that was already closed with `/dev/null`; shoutx cannot distinguish it from an
intentional empty input and therefore accepts it as empty stdin. Windows invalid
handles remain observable I/O failures.

Options precede `NAME`. After `NAME`, one token is treated as `VALUE` even if it
begins with `-`. A value argument causes stdin to be ignored. An empty argument
and empty non-terminal stdin both represent the empty value; `-` has no special
stdin meaning.

`--` ends option parsing. Mode options are mutually exclusive. At most one
operand may follow `NAME`; extra operands are usage errors. The argument to
`--join-lines-with` is the next token verbatim even when it begins with `-`, and
the `--join-lines-with=STRING` form is also accepted. For commands without a
`NAME` operand, `--` is required when a value begins with `-`.
Callers using the separate-token form must not omit the separator: the parser
always consumes the next token as `STRING` before parsing `NAME`.
Acceptance of the equals form is specific to `--join-lines-with`; it is not a
general CLI convention for other options.

`--help` and `--version` are recognized only while options are being parsed.
After `NAME`, the same tokens are values rather than options.

An official stable binary writes exactly `shoutx VERSION` followed by LF for
`--version`, where `VERSION` is its Cargo package version. It writes no stderr
and exits 0. Feature-enabled research builds append a feature label and are not
official release artifacts.

Encoded output is written to stdout and diagnostics to stderr. This preserves
normal Unix composition and keeps destination selection visible in the calling
workflow.

## Command specifications

Destination-specific contracts live beside their threat analysis and focused
verification plan:

- [GitHub Actions named records](commands/github-actions-records.md)
- [GitHub Actions PATH writer](commands/github-actions-path.md)
- [GitHub Actions log-mask command](commands/github-actions-mask.md)
- [GitHub Actions annotation commands](commands/github-actions-annotations.md)

## Design decisions

Proposed, accepted, deferred, rejected, and superseded decisions are maintained
separately under the [decision-record policy](decisions/README.md):

- [GitHub Actions stdout workflow-command framing](decisions/github-actions-stdout-framing.md)
- [Unstable GitHub Actions stdout command isolation](decisions/unstable-github-actions-stdout.md)
- [Markdown output](decisions/markdown-output.md)
- [GitHub Actions artifact declarations](decisions/github-actions-artifacts.md)
- [POSIX shell-word encoding](decisions/shell-arg.md)

## Open questions

- When GitHub enables `$GITHUB_ARTIFACTS` processing uniformly on supported
  hosted runners, allowing the deferred candidate to be reconsidered.
- Whether provider extensions are compiled in, discovered as executables, or
  loaded through another plugin mechanism.
- Compatibility and versioning rules for provider extensions.

## Deferred scope

- Static workflow analysis and attack-path discovery.
- General JSON and HTML encoders.
- Arbitrary document sanitization.
- Providers other than GitHub Actions.
- A stable third-party plugin API.
