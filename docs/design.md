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

## v1 readiness

v1 means practical coverage of GitHub Actions output boundaries within the
product boundary above, not merely a stable version number or implementation
of every runner command. This section owns that criterion and the coverage
inventory; command contracts and release procedures remain in their existing
authoritative documents.

Before proposing v1:

- Resolve the open coverage rows below through a release-included writer with a concrete
  injection-prevention use case, or an explicit exclusion with a documented
  boundary rationale. An unimplemented useful boundary is not an exclusion.
- Verify supported writers against their actual consumers within the declared
  compatibility profile, with usable installation and workflow examples.
- Review the CLI for an interface that can be maintained under v1 compatibility
  expectations, and satisfy the [release gates](release.md). Maintainer approval
  is still required; this inventory does not authorize publication.

The 2026-10-17 review found no remaining implementation gap in this inventory
within the stated product boundary. All intended writers are implemented and
consumer-verified. Rows marked v1.0.0 describe the version containing those
writers, not its publication status; consult
[published releases](https://github.com/send/shoutx/releases) for availability.
Coverage alone does not authorize publication. The [surface audit](compatibility/github-actions-surface-audit.md)
records the sources; the [Runner update](compatibility/runner-2.338-update.md)
tracks verification of the newer package;
the [release checklist](release.md#next-release-preparation) owns the gates for
each future publication. The [CLI review decision](decisions/v1-cli-review.md)
explains why existing destination-specific differences are retained.

The inventory is based on the [official workflow-command surface][workflow-surface]
and the pinned runner's [stdout handlers][runner-command-surface],
[environment-file and summary handlers][runner-file-surface],
[artifact declaration handler][runner-artifact-surface], and
[artifact-list handler][runner-artifact-list-surface]. It classifies
product work, not universal safety of GitHub Actions. Existing evidence is
reused; upstream internals are not investigated without a concrete attack path
through a named shoutx output boundary.

| Surface | Coverage / v1 disposition | Remaining action or rationale |
| --- | --- | --- |
| Output, environment, action state, PATH files | Shipped | Contracts indexed below; authorization of values and paths remains caller-owned. |
| Mask and notice/warning/error annotations | Shipped | Contracts and compatibility profile below; not arbitrary log sanitization. |
| Artifact declarations | Implemented and consumer-verified; v1.0.0 | [Contract](commands/github-actions-artifacts.md), [consumer evidence](compatibility/github-actions-artifacts-availability.md#writer-integration-observations); not in v0.3.0. |
| Debug message and group title | Implemented and consumer-verified; v1.0.0 | [Contract](commands/github-actions-log-commands.md) and [evidence](compatibility/github-actions-log-commands.md); not in v0.3.0. |
| `endgroup`, command echo on/off | Fixed terminator included; no echo data writer required | Endgroup completes the group interface; echo is a trusted fixed control operation. |
| Stop/resume commands | Outside the current writer boundary | Controls a stream-wide protocol with a caller-managed token/lifetime, not one encoded value. Do not present this as protection for arbitrary subprocess output. |
| Add/remove problem matcher | Implemented and consumer-verified; v1.0.0 | [Contract](commands/github-actions-problem-matchers.md), [decision](decisions/github-actions-problem-matchers.md), and [evidence](compatibility/github-actions-problem-matchers.md). Paths/owners select caller-authorized configuration; not in v0.3.0. |
| Job summary / Markdown | Excluded | [Markdown decision](decisions/markdown-output.md): content-policy concerns, not the implemented record boundary. |
| Legacy stdout output/env/state/path commands | Excluded | Use the supported command-file destinations instead; no legacy syntax expansion. |
| Inputs, saved-state reads, artifact-list reads | Not output writers | Consumer-side inputs, not destinations to encode. |
| Toolkit process failure, artifact upload/download, cache, GitHub API operations, internal runner commands | Outside this CLI boundary | Process status, services, or internal control protocols, not additional public value writers. |

The next bounded increment is owned by the
[implementation handoff](implementation-plan.md#current-handoff-status).
An availability regression may defer artifacts with recorded evidence; it does
not require shoutx to repair or prove GitHub's service. Before v1, recheck this
inventory for newly documented practical output boundaries and record the
maintainer's disposition of any remaining upstream-dependent deferral.

[workflow-surface]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
[runner-command-surface]: https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionCommandManager.cs
[runner-file-surface]: https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/FileCommandManager.cs
[runner-artifact-surface]: https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/CreateArtifactsFileCommand.cs
[runner-artifact-list-surface]: https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ArtifactsListFileCommand.cs

## GitHub Actions commands

Provider-specific writers:

```text
shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:state  [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:path   [VALUE]
shoutx github-actions:artifacts file [PATH]
shoutx github-actions:artifacts oci REFERENCE DIGEST
```

The same executable also provides stdout workflow-command writers:

```text
shoutx github-actions:mask    [VALUE]
shoutx github-actions:debug   [MESSAGE]
shoutx github-actions:group   [TITLE]
shoutx github-actions:endgroup
shoutx github-actions:add-matcher [PATH]
shoutx github-actions:remove-matcher owner [OWNER]
shoutx github-actions:remove-matcher file [PATH]
shoutx github-actions:notice  [ANNOTATION OPTIONS] [MESSAGE]
shoutx github-actions:warning [ANNOTATION OPTIONS] [MESSAGE]
shoutx github-actions:error   [ANNOTATION OPTIONS] [MESSAGE]
```

All fourteen GitHub commands are included in default and `--no-default-features` builds,
alongside the seven unreleased Azure commands.
The former research feature is removed. Stdout consumer compatibility is scoped
by the adoption contract below; binary availability does not broaden it.

No reusable context encoder is currently planned for v1.0. The former
`shell:arg` candidate is deferred after boundary review.

## Security invariants

1. A command protects only the interpretation boundary named by that command.
2. Validation, encoding, and resource-limit failures occur before stdout output
   begins. I/O failure after writing begins may leave partial bytes.
3. GitHub Actions single-value non-multiline writers consume at most one final line boundary
   as producer framing as specified by their command contracts. Structured
   operands such as annotation metadata and OCI fields do not inherit that
   preprocessing; fixed commands such as `endgroup` have no input value.
4. Discarding or normalizing content beyond that framing boundary is always
   explicit.
5. Multiline framing never uses a delimiter that can terminate the value.
6. NUL is rejected.
7. Raw passthrough is not provided.
8. Names and paths are validated according to their destination protocol.
9. Diagnostics never reproduce untrusted values or value-derived excerpts.
10. Documentation distinguishes structural encoding from authorization and
   semantic validation.
11. Documentation does not imply protection from injection that occurs before
   `shoutx` starts or after its selected boundary has been crossed.
12. Input is strict UTF-8 and output is UTF-8 without a byte-order mark.
    Framing bytes are chosen for semantic round trips through the local
    supported runner parser and do not rely on host text-mode translation.
13. Every input field has a documented hard size limit; a destination's encoded
    record limit may impose a smaller effective maximum after framing.
14. A stdout workflow-command writer must emit exactly the selected command
    line whose decoded data and properties equal the accepted semantic fields.
    An explicit batch mode may select multiple records only as specified by its
    destination contract; no unrequested record may be added.
    Fixed commands have no value fields. This does not claim that runner log
    masking prevents every disclosure of a value.
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
The [framing decision](decisions/github-actions-stdout-framing.md) explains
adoption, and the release policy governs publication of the implemented surface.

## Artifact consumer scope

The artifact writer targets native standard GitHub-hosted Ubuntu 22.04 x64,
Ubuntu 24.04 x64, macOS 15 arm64, and Windows 2025 x64 jobs with artifact
processing enabled. The pinned source reference is recorded in the
[oracle metadata](../tests/runner-oracle/README.md). The
implementation must pass declaration/list integration on these targets before
support is claimed. Packaging for another architecture does not add its consumer
to this profile. Self-hosted and container observations in tests characterize
the protocol but do not initially extend the supported deployment scope.

Shoutx cannot inspect the consumer feature flag or acknowledge post-step
processing. Actual subject verification, not variable presence, provides
availability evidence. This file-command destination does not use the stdout
command parser or inherit its Unicode data-start restrictions.

## Stdout adoption contract

This section defines the scope for productizing the existing mask and
notice/warning/error implementations, including message, TITLE, and FILE, and
the debug/group/endgroup and problem matcher implementation increments. It
defines their consumer compatibility, not whether a particular release contains
them. Their observable input and encoding rules remain solely in the command
specifications. Previously published binaries are unchanged.

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

The executable's availability is distinct from consumer compatibility. The
same CLI surface may be packaged for other architectures to keep invocation
and byte-level producer behavior consistent; that does not add their native
Runner environments to this profile. Neither installing such an artifact nor
successfully invoking a command certifies its consumer. Unsupported deployment
is not prevented by target-specific compilation, just as an x64 binary cannot
distinguish a standard hosted Worker from an arbitrary self-hosted one.

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

## Azure Pipelines profile

The [Azure practical coverage inventory](azure-coverage.md) owns Azure surface
classifications and proposed priorities. It is a coverage assessment, not an
extension of the command contracts or this applicability profile.

The current source implements variable, warning/error and PATH writers described
by the [Azure command contract](commands/azure-pipelines.md). It is not included
in v1.0.0. The command contract owns destination-specific input and newline
rules. PATH uses the native producer OS dialect, without extending this profile
to cross-OS producers or containers. The coverage inventory proposes priorities;
the maintainer-selected task is owned by the
[current handoff](implementation-plan.md#current-handoff-status).
The [mask contract](commands/azure-pipelines-mask.md) is implemented, with scoped
hosted results in the [compatibility record](compatibility/azure-pipelines.md#mask-hosted-observations).
The [build metadata writers](commands/azure-pipelines.md#build-metadata) are
implemented; the compatibility record owns hosted admission. Tags require trusted
job variable `AGENT_USE_BUILD_TAGS_BODY_API: 'true'` before Agent job startup;
the legacy URL-path API is excluded. This does not expand the OS/shell profile.

Mask registration additionally requires trusted pipeline/job `variables:`
configuration `AZP_IGNORE_SECRETS_SHORTER_THAN: '0'` before job startup,
`system.debug=false`, and secret-using processes in a later task of the same
job, with no racing producers. The threshold is mandatory even for long
multiline credentials, whose final line may be short. A child environment
variable does not establish the Agent setting. Keep shell tracing and verbose
command logging off. Same-task register-then-run and debug-on use are not
admitted by this initial profile. These conditions cannot undo prior disclosure.
The producer does not inspect hidden Agent state or certify acknowledgment.
Percent-decoding mismatch can register a different value; it is not a harmless
display change for masks. The required profile must pass actual registration
and completed-log checks before hosted support is claimed.

The initial verification target is native Microsoft-hosted Ubuntu 24.04 x64
with Bash and Windows 2025 x64 with PowerShell Core 7.4+, normal command
processing and `DECODE_PERCENTS=true`. Pin the source parser version in the
[evidence record](compatibility/azure-pipelines.md); record actual hosted
versions separately before claiming service compatibility. No hidden consumer
settings are discovered by the producer. Self-hosted, containers, classic
release pipelines and percent-decoding-disabled configurations are excluded
from this initial profile, not declared inherently unsafe.

Shoutx owns one typed command's framing, fields, validation, bounded allocation
and value-free diagnostics. Azure owns applying the operation and subsequent
scope, display and variable-export semantics. Callers authorize variable names
and content, deliver inputs as data and propagate process failures. The
[Azure attack inventory](threat-model.md#azure-pipelines-boundary) defines the
bounded security work; dependency-internal proofs are not admission gates.

### Proposed secret variable profile

The [secret-variable proposal](commands/azure-pipelines-secret-variable.md) is
not implemented. Its candidate profile reuses the native Azure profile and mask
prerequisites above, applying the settings to both producing and receiving jobs.
Use ordinary script tasks and caller-authorized names permitted by task restrictions,
without pre-existing read-only collisions, custom-task declared output overrides
or changes to consumer settings. Producer completion must be clean, with no
warning/error issues, before dependent use. These are deployment conditions,
not hidden state that the writer can inspect or enforce. Admission of secret
output mapping across jobs/stages remains a required implementation gate.

## Distribution integrations

The official GitHub Action installs an exact released `shoutx` version from
the native artifacts without duplicating their publication contract. Its
repository boundary, verification requirements, and initial no-cache policy
are recorded in the
[official setup action decision](decisions/official-setup-action.md). The
action is not part of the CLI surface; its repository owns its releases and
interface. The [installation example](../README.md#installation) selects an
existing immutable action release and an exact CLI version.

## Command model

Provider writers use `PROVIDER:DESTINATION`. Reusable encoders use
`LANGUAGE:CONTEXT`.

For commands with an optional single-value operand, that argument is used when
present. Otherwise, input is read from stdin when
stdin is not a terminal. Reading normally continues through EOF, but may stop
when the first byte beyond the hard limit proves the input must be rejected.
With no value and terminal stdin, commands fail with usage status 2 instead of
waiting. An unreadable stdin error exposed by the host API has status 1. On
POSIX, however, Rust runtime initialization replaces an inherited descriptor
that was already closed with `/dev/null`; shoutx cannot distinguish it from an
intentional empty input; command-specific validation decides whether an empty
value is accepted. Windows invalid
handles remain observable I/O failures.

For named-record writers, options precede `NAME`. After `NAME`, one token is treated as `VALUE` even if it
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

Other operand shapes are owned by their command specifications: artifact and
matcher modes precede data, OCI requires two argv fields and never reads stdin,
and endgroup accepts no value and never reads stdin. Help/version in option
position return immediately; they are not validation of a subsequent write.

An official stable binary writes exactly `shoutx VERSION` followed by LF for
`--version`, where `VERSION` is its Cargo package version. It writes no stderr
and exits 0. There is no research-feature suffix.

Encoded output is written to stdout and diagnostics to stderr. This preserves
normal Unix composition and keeps destination selection visible in the calling
workflow.

## v1 CLI compatibility baseline

The proposed v1 baseline is the command surface and linked contracts above,
not a generic parser or encoder API. Maintain command/mode/option names,
documented operand order and input-source selection, status classes, accepted
semantic fields, explicit transformations, and specified wire formats. Keep
`--version` and artifact-layout compatibility under the release contract.
Random multiline delimiters remain nondeterministic as specified. Diagnostics
remain value-free; their human-readable wording and help layout are not a
machine-readable API. The Rust library is an implementation detail, not a
separately promised stable library or plugin interface.

Additive commands or options need their own boundary contract and review.
Incompatible changes to an existing documented CLI require a major-version
decision rather than silently reinterpreting old invocations. Security fixes
and upstream incompatibility may require rejecting previously accepted inputs
or withdrawing a deployment recommendation: follow the incident and
compatibility process in [release.md](release.md#stdout-admission-and-compatibility-maintenance),
disclose the affected behavior, and never silently change the user's value.
Version compatibility does not promise that GitHub will keep every consumer
configuration or provider limit unchanged.

## Command specifications

Destination-specific contracts live beside their threat analysis and focused
verification plan:

- [GitHub Actions named records](commands/github-actions-records.md)
- [GitHub Actions PATH writer](commands/github-actions-path.md)
- [GitHub Actions artifact declarations](commands/github-actions-artifacts.md)
- [GitHub Actions log-mask command](commands/github-actions-mask.md)
- [GitHub Actions annotation commands](commands/github-actions-annotations.md)
- [GitHub Actions debug and group commands](commands/github-actions-log-commands.md)
- [GitHub Actions problem matcher commands](commands/github-actions-problem-matchers.md)
- [Azure Pipelines commands](commands/azure-pipelines.md)
- [Azure Pipelines mask registration](commands/azure-pipelines-mask.md)

## Design decisions

Proposed, accepted, deferred, rejected, and superseded decisions are maintained
separately under the [decision-record policy](decisions/README.md):

- [GitHub Actions stdout workflow-command framing](decisions/github-actions-stdout-framing.md)
- [GitHub Actions debug and group writers](decisions/github-actions-log-commands.md)
- [GitHub Actions problem matcher writers](decisions/github-actions-problem-matchers.md)
- [v1 CLI review](decisions/v1-cli-review.md)
- [Azure build metadata writers](decisions/azure-build-metadata.md)
- [Unstable GitHub Actions stdout command isolation](decisions/unstable-github-actions-stdout.md)
- [Markdown output](decisions/markdown-output.md)
- [GitHub Actions artifact declarations](decisions/github-actions-artifacts.md)
- [POSIX shell-word encoding](decisions/shell-arg.md)

## Open questions

- Remaining GitHub Actions coverage decisions are tracked in
  [v1 readiness](#v1-readiness).
- Whether provider extensions are compiled in, discovered as executables, or
  loaded through another plugin mechanism.
- Compatibility and versioning rules for provider extensions.

## Deferred scope

- Static workflow analysis and attack-path discovery.
- General JSON and HTML encoders.
- Arbitrary document sanitization.
- Providers other than GitHub Actions and the scoped Azure Pipelines increment.
- A stable third-party plugin API.
