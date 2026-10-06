# Implementation history

This document preserves the implementation sequencing used to reach the
current architecture. It is historical context, not the active product
contract and does not override the command specifications. It is an archive of
the pre-split plan, not an append-only project log; future completed work belongs
in Git history, pull requests, and release notes unless it explains a lasting
architectural constraint.

## Stdout productization

[PR #118](https://github.com/send/shoutx/pull/118) established source-bound
admission before [PR #119](https://github.com/send/shoutx/pull/119) promoted the
existing stdout writers to normal builds and aligned their tests, native
packages and documentation. This sequence separates delivery of the producer
from admission of its observed consumer configurations; compiling the writers
does not itself authorize publication. The
[productization snapshot](compatibility/stdout-unicode-policy.md#normal-build-productization-snapshot)
retains the candidate observations and main-side external admission result.
The finite implementation handoff completed without publishing a release.
The [release policy](release.md#stdout-admission-and-compatibility-maintenance)
continues to own fresh exact-source admission and release approval.

## First implementation PR

The first implementation PR delivers the project foundation and complete
single-line named writers:

- Cargo package, MSRV declaration, formatting, lint, build, and test CI;
- thin binary and testable library boundary;
- manual parsing for `github-actions:output` and `github-actions:env`;
- value argument and binary stdin selection;
- strict UTF-8, NUL, and pre-normalization size validation;
- output and environment name policy;
- default, `--first-line`, `--join-lines`, and
  `--join-lines-with STRING` modes;
- checked post-normalization sizing before allocation;
- complete single-line record construction;
- stdout, stderr, SIGPIPE, and status behavior; and
- deterministic unit and executable-level contract tests.

The PR does not implement multiline records, the runner parser model,
`github-actions:path`, shell/Markdown encoders, installation packaging, or a
release workflow. No release is published from this increment.

The same PR updates the README so its quick start, command inventory, examples,
and help expectations show only implemented commands and modes. Future commands
remain clearly labeled as planned. In particular, `github-actions:path` and
`--multiline` are not presented as usable until their implementation PRs land.

### First-PR acceptance criteria

- Every applicable deterministic command-line, input-source, name, text,
  non-multiline, size, diagnostic, and I/O case in `test-plan.md` is automated.
- Tests cover argv and stdin separately, including invalid POSIX argv bytes and
  a Windows unpaired surrogate constructed with `OsStringExt::from_wide`.
- Executable-level limit tests use stdin; library tests cover argv-sized values
  beyond host process argument limits.
- Windows stdin tests use discriminating fixtures to prove that CRLF and byte
  `0x1a` reach validation unchanged.
- A maximal join expansion is rejected before allocating the expanded result.
- All validation and usage failures have empty stdout and the specified status.
- A present value operand succeeds without the application touching an invalid
  Windows stdin handle or opening its stdin abstraction.
- Windows CI covers safe unpaired-surrogate and binary-stdin cases. The
  executable invalid-handle cases require the test-only FFI launcher and are a
  mandatory gate in the platform harness PR before any release.
- POSIX descriptors closed before process startup are observed as `/dev/null`;
  stdin becomes an empty value and stdout may discard output with status 0.
- Broken-pipe behavior produces status 1 rather than signal termination.
- A forced recoverable panic maps to status 1, and failed stderr diagnostics do
  not change the original status.
- The code builds and tests on the declared MSRV and current stable Rust on
  Linux, macOS, and Windows.
- Formatting and lints pass with warnings denied for project code.
- No command documented as supported in a release is only a stub.

## Second implementation PR: multiline records

The second PR adds:

- `--multiline` record construction;
- an OS CSPRNG abstraction with injectable deterministic test behavior;
- `SHOUTX_` plus 32 lowercase hexadecimal digits;
- whole-value substring collision checks, retry, bounded exhaustion, and
  randomness-failure handling;
- target runner OS selection from trusted `RUNNER_OS`, with native-OS fallback;
- Windows trailing-bare-CR framing;
- the independent test-only runner parser model; and
- exact layout, parsed-value, and appendability tests.

The CSPRNG abstraction returns raw random bytes; hexadecimal encoding and
delimiter policy remain project code. Randomness is acquired and all collisions
are resolved before constructing or writing stdout.

For the named writers in this increment, an unrecognized `RUNNER_OS` is
relevant only when platform-specific multiline framing is required. The
implementation follows the design contract rather than silently treating an
unknown target as POSIX. The later path writer always requires a recognized
target dialect when `RUNNER_OS` is present.

Read `RUNNER_OS` as `OsString` in the process layer and pass a parsed target-OS
value into the library; tests never mutate global process environment. Matching
is exact and case-sensitive for `Linux`, `Windows`, and `macOS`.

The parser model is implemented and unit-tested from inspected runner fixtures
before it is used as the multiline encoder oracle. It remains independent of
production encoding code.

## Third implementation PR: runner differential tests

The third PR adds the pinned `actions/runner` v2.337.0 differential harness
described by `test-plan.md` and validates the parser model introduced in PR2.

The harness records both tag and commit, and invokes or compiles actual pinned
runner parser code as the independent oracle. It runs natively on Linux and
Windows. Generated property cases compare ordered record count, names, exact
values, and parse failures between the model and real parser.

Workflow smoke tests then establish:

- POSIX `sh` and Bash byte preservation and failure propagation on Linux;
- Bash behavior on macOS;
- PowerShell 7.4+ byte preservation and explicit native-status propagation on
  Windows; and
- Git Bash behavior on a Windows runner, including `RUNNER_OS`-selected
  trailing-bare-CR framing.

Only after this PR passes may PowerShell and the tested runner versions enter a
release compatibility declaration.

Re-evaluate mise when this work introduces a .NET SDK for the runner harness or
several separately versioned development tools. Adopt it only if it replaces a
growing set of installation instructions or repeated local/CI command sequences;
it must remain optional unless the same tasks cannot be expressed clearly with
the native toolchains and CI configuration.

## Next design and implementation PRs: `github-actions:path`

`github-actions:path` remains separate because the runner uses path-specific
`File.ReadAllLines` behavior rather than the named environment-file parser.
The design increment specifies one fully qualified target-platform path,
rejects the effective PATH separator, double quote, leading U+FEFF, and a POSIX
trailing backslash, and performs no lexical or filesystem normalization. It
documents bare-CR splitting, empty-line removal, ordering, and
culture-sensitive duplicate behavior as runner facts rather than shoutx
transformations.

After that contract is reviewed, the implementation increment adds a separate
path validator and parser model, target selection from `RUNNER_OS`, native
Linux and Windows runner differential cases, shell smoke tests, and the public
command. It must not inherit output/environment parser assumptions by code
reuse.

## `github-actions:state` implementation increment

The state contract was specified after v0.1.0 and implemented as a small
named-writer extension. Add the command to the manual parser and help output,
reuse the shared value, line-mode, multiline-framing, size, and record
construction paths, and add a state name policy that shares the environment
grammar without its reserved-name block.

Extend CLI and property-test matrices to all three named destinations. Extend
the pinned runner oracle to call `SaveStateFileCommand` and obtain its state
dictionary from `ExecutionContext.CreateChild` without supplying an existing
state dictionary; record that construction path, since a mock-provided comparer
would make the oracle self-validating. Prove exact value round trips and that a
case-colliding later record replaces the value while retaining the first name
spelling. Add a local JavaScript fixture action whose `main` phase writes state
through shoutx and whose `post` phase verifies `STATE_NAME`. Keep
shell-redirection coverage in the shared named-writer matrix. Public
documentation exposes the command only with the completed implementation.

## Candidate design increment: `github-actions:artifacts`

Do not implement or advertise this command until its hosted-runner availability
gate passes. The proposed parser adds a destination command with two typed
variants:

```text
github-actions:artifacts file [PATH]
github-actions:artifacts oci REFERENCE DIGEST
```

Keep artifact validation separate from named records and PATH mutation. The
file variant may reuse bounded argv/stdin acquisition and final-boundary
consumption, but it has no lossy line modes. The OCI variant is a structured
two-operand command and never consults stdin. Both variants build the complete
explicit-scheme record and validate its encoded size before stdout is opened.

Add a dedicated runner oracle around `CreateArtifactsFileCommand` and
`ArtifactsListFileCommand`. Enable the pinned runner's server-side feature
variable explicitly without mutating process-global state, exercise real
temporary files and native path semantics, and compare the job-scoped aggregate
and JSON list rather than transcribing only the line parser. Test the
self-hosted process-environment fallback separately with cleanup. Test rooted
paths once with a null container and separately with a real `ContainerInfo`
mapping, including outside-mount rejection; a relative container case uses the
host workspace context. The oracle must cover Unicode trimming, schemes,
directory exclusion, hashing, name collisions, deduplication, conflicts,
partial aggregation on conflict or cap failure, and limits without turning
those runner behaviors into shoutx guarantees.

Before implementation, add a temporary hosted-runner probe or equivalent
design-validation workflow across Linux, macOS, and Windows. The probe must
observe a declared subject in a subsequent step; the mere presence of
`GITHUB_ARTIFACTS` is insufficient because the runner silently ignores writes
when processing is disabled. If any supported hosted runner fails the probe,
leave the command deferred rather than publishing a platform-dependent silent
success.

The 2026-09-28 probe failed this gate uniformly on GitHub-hosted Linux, macOS,
and Windows runners: the variables existed, but every later-step list file was
zero bytes. The temporary probe was removed after capturing the result in the
design. No implementation increment should begin until a later probe passes on
all supported operating systems.

## Implemented increment: `github-actions:mask`

The log-mask command is implemented without reusing environment-file
record framing. It extends the manual parser with one optional value operand and no
line-mode options. Reuse bounded argv/stdin acquisition, strict UTF-8 and NUL
validation, one optional final producer-boundary consumption, safe diagnostics,
and the existing single-buffer stdout path. Add a destination-specific
whitespace-only rejection matching .NET 8 `String.IsNullOrWhiteSpace`.

Add a small workflow-command data encoder that replaces `%`, CR, and LF in that
order. It computes the encoded length with checked arithmetic before allocating
and returns a complete immutable `::add-mask::...\n` buffer. Keep this encoder
separate from named records and do not generalize it into a raw workflow-command
API. The command is now present in help. It must not enter a release artifact
until the remaining hosted-log release gate below passes.

Extend the C# runner oracle around `ActionCommandManager`,
`AddMaskCommandExtension`, and the real `SecretMasker`. Compare decoded values,
single-command parsing, multiline per-line registration, whitespace-only
rejection, echo suppression, stopped-command behavior, derived masks, and job
output suppression. Pin these observations to runner v2.337.0 and inspect the
current runner source before release.

CI dogfoods registration with fresh random markers on each supported OS and
shell. A read-only `workflow_run` verifier on the default branch inspects the
completed log from outside the producing job without checking out or executing
the triggering revision. Before the next release, a successful main-branch run
must record this evidence. It must prove redaction on Linux,
macOS, and Windows under each supported shell, including stdin sourced from
quoted environment variables and shell-local variables. Do not use shell tracing or literal secrets in
workflow source. The workflow should distinguish a missing marker caused by a
test setup failure from successful replacement with `***`.
