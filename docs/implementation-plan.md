# Rust implementation plan

This document defines how the agreed CLI contract will be implemented. It is a
sequencing and architecture plan, not an additional product contract. The
[design](design.md), [threat model](threat-model.md), destination-specific
[`commands/`](commands/) specifications, and
[CLI contract test plan](test-plan.md) remain authoritative for observable
behavior.

Status: the plan through native packaging and publication was completed for
v0.1.0. Future-tense milestone language below is retained as a historical
record of the implementation sequence, not as a statement that those features
remain unimplemented.

## Language and compatibility baseline

`shoutx` will be implemented in Rust using Edition 2024 with Rust 1.85 as the
initial minimum supported Rust version (MSRV). The implementation will produce
one native executable and will not require a language runtime on the runner.

Rust is selected because the contract requires byte-preserving process I/O,
explicit handling of non-Unicode process arguments, checked size arithmetic,
and native POSIX and Windows behavior. The MSRV may be raised deliberately in a
later release, but CI must build the declared MSRV until that decision is made.

The initial project uses `rust-toolchain.toml`, Cargo, and direct Cargo commands
rather than requiring mise or another general tool-version manager. A single
language toolchain does not justify an additional bootstrap dependency.
The pinned development toolchain tracks an explicitly selected current stable
release independently of the MSRV. CI tests both current stable and the MSRV;
updating the development pin does not silently change the compatibility
contract.

## Dependency policy

The first implementation increment should have no production dependency unless
a dependency materially reduces security risk. In particular:

- command-line parsing is implemented locally because option recognition stops
  at `NAME` and differs from common parser defaults;
- validation, normalization, UTF-8 handling, and record construction use the
  standard library;
- errors use a small project-specific type rather than a general error wrapper;
  and
- multiline delimiter generation may add a narrowly scoped OS-randomness
  dependency in its own increment.

Development dependencies are acceptable for property testing, Windows process
launch helpers, and test ergonomics. Every dependency must have a concrete use,
be pinned through `Cargo.lock`, and be included in dependency and license
review. The executable must not initialize networking, logging, configuration
discovery, or plugin loading as a side effect.

## Crate and module layout

Begin with one package containing a library and a thin binary:

```text
Cargo.toml
Cargo.lock
src/
  main.rs
  lib.rs
  cli.rs
  error.rs
  input.rs
  process_io.rs
  github_actions/
    mod.rs
    name.rs
    normalize.rs
    record.rs
tests/
  cli_contract.rs
  support/
    mod.rs
    process.rs
    runner_parser.rs
```

The binary owns only process integration: collecting OS arguments with
`std::env::args_os`, lazily opening inherited standard handles when needed,
identifying stdin state, calling the library, writing one prepared stdout
buffer, rendering a safe diagnostic, and selecting the documented exit status.
Business rules belong in the library and are testable without spawning a
subprocess. Stdin is not opened or duplicated when a value operand is present.

`tests/support/runner_parser.rs` is test-only code and must not import or reuse
production record parsing or encoding logic. Sharing constants such as size
limits is also avoided where doing so would make an incorrect production value
self-validating in the oracle.

Do not split the repository into a Cargo workspace until a second independently
versioned package or tool justifies it.

## Core types and data flow

Use types that make validation order visible:

```text
Os arguments / stdin bytes
    -> bounded raw input
    -> validated UTF-8 value
    -> destination-specific validated name
    -> selected line mode
    -> size-checked normalized value or multiline value
    -> complete encoded record buffer
    -> stdout write
```

Suggested internal types are:

- `Command`: the selected provider destination;
- `InputSource`: argv value or stdin;
- `LineMode`: default, first line, join with a validated separator, or
  multiline;
- `RecordName`: a destination-specific validated name;
- `Value`: strict UTF-8 bytes that have passed NUL and input-size checks;
- `EncodedRecord`: the complete immutable stdout buffer; and
- `ShoutxError`: a classified error carrying no untrusted input.

The types need not be public outside the crate. Constructors enforce
invariants; fields that could bypass validation remain private.

The library returns either a complete `EncodedRecord` or an error before the
binary obtains any bytes to write. This prevents validation paths from writing
partial stdout. Output I/O errors remain non-transactional by contract.

## Manual CLI parser

The parser operates on `OsString`, not `String`. Conversion to UTF-8 occurs only
after the parser has identified the role of each token, allowing diagnostics to
name the failed rule without reproducing an invalid token.

Parsing is a small state machine:

1. Parse the top-level command or global help/version.
2. For a named writer, recognize options only before `NAME`.
3. `--` ends option parsing.
4. A separate-token `--join-lines-with` always consumes the following token as
   its separator, including a token beginning with `-`.
5. The first non-option token is `NAME`.
6. After `NAME`, at most one token is `VALUE`; it is never interpreted as an
   option.
7. If `VALUE` is absent, select stdin without reading it during parsing.

Mode conflicts, missing option arguments, missing names, unknown options, and
extra operands are usage errors with status 2 and empty stdout. Input and policy
rejections after a syntactically valid invocation use status 1.

`github-actions:path` is not exposed as a functional command until its contract
is complete. `shell:arg` and `markdown:text` were subsequently removed from the
v1.0 candidates after boundary and threat-model review; neither receives a
placeholder whose behavior could be mistaken for stable API.

During incremental development, `--multiline` may be parsed but must not appear
in release artifacts until it is implemented. In the first PR it is rejected
with a non-zero status and empty stdout; it never falls back to single-line
output. Help lists only implemented features. No public release is cut from an
intermediate increment that advertises an unavailable documented mode.

## Input handling

The process layer reads `RUNNER_OS` as an `OsString` and passes a parsed target
OS into the library for commands that require it. Tests pass this dependency
explicitly and do not mutate process-global environment.

### Argument values

On POSIX, inspect the raw `OsStr` bytes and validate them with strict UTF-8.
On Windows, convert `OsStr` only through a non-lossy operation; an unpaired
UTF-16 surrogate must be rejected rather than replaced. Never use
`to_string_lossy` for a name, value, separator, command, or diagnostic.

NUL cannot normally occur in process arguments but is still rejected by shared
value validation. Invalid argument encoding is an input rejection with status 1
after the invocation shape is otherwise valid.

### Standard input

Use `std::io::IsTerminal` before reading. An omitted value with terminal stdin
is a usage error and must not block. An unreadable descriptor reported by the
host API is an I/O error, subject to the POSIX startup substitution below.

A small platform I/O layer lazily duplicates the inherited stdin descriptor or
handle using safe owned-handle APIs, then constructs a `File` and reads it. On
Windows, duplication or reading an invalid handle fails with status 1 and empty
stdout; an executable-level helper creates that state because `Stdio::null()`
is the readable NUL device and is not equivalent.

On POSIX, Rust runtime initialization runs before `main` and reopens a standard
descriptor that was already closed using `/dev/null`. Neither duplication nor
reading can distinguish this substitution from intentional `/dev/null` input,
so startup-closed stdin is accepted as an empty value. This platform limitation
is tested and documented rather than treated as a detectable I/O error.

Read stdin as binary bytes. On Windows, no text-mode CRLF conversion or `0x1a`
end-of-file behavior is permitted. Read until EOF or until the first byte beyond
the 1 MiB limit proves that the input must be rejected. The size limit is
measured before optional final-boundary consumption. A rejected oversized input
need not be drained to EOF.

If a value operand is present, do not inspect, poll, or read stdin, even when
the descriptor is closed.

### Validation order

For a syntactically valid command:

1. validate all argv-resident data, including the name and optional separator;
2. acquire at most the bounded value input;
3. validate the complete acquired value as UTF-8;
4. reject NUL anywhere, including data a lossy mode would discard;
5. perform optional-final-boundary preprocessing;
6. apply the selected mode using checked output-size arithmetic;
7. construct the complete record; and
8. begin stdout output.

Once an input exceeds the hard limit, its remaining UTF-8 and NUL properties do
not affect the result: it is already rejected with no stdout. Diagnostics do not
include rejected bytes or distinguish secrets by content.

## Name and policy validation

Keep destination name policies explicit even when validators can share a
portable grammar:

```text
output  [A-Za-z_][A-Za-z0-9_-]*
env     [A-Za-z_][A-Za-z0-9_]*
state   [A-Za-z_][A-Za-z0-9_]*
```

Validate the 255-byte limit independently of grammar. Environment reserved-name
comparisons use ASCII case folding only. Do not use locale-sensitive or Unicode
case conversion. Reject prefixes `GITHUB_` and `RUNNER_`, plus exact
`NODE_OPTIONS`; do not broaden those checks by substring matching.
State has no reserved-name policy because the runner adds the `STATE_` prefix.
Reuse of the environment grammar must not accidentally reuse its reserved-name
block.

Name failures are policy/input errors with status 1, not CLI grammar errors.

## Line normalization

Line processing operates on validated UTF-8 bytes because CR and LF have stable
single-byte encodings. A tokenizer always recognizes CRLF first, then bare CR
or LF.

For every non-multiline named-writer mode:

1. remove at most one boundary at the absolute end of the value;
2. apply the mode to the remaining bytes; and
3. verify the normalized value is at most 1 MiB before allocation.

Default mode rejects any remaining CR or LF. First-line mode returns the prefix
before the first remaining boundary. Join modes replace each remaining boundary
with exactly one separator.

For joining, first scan without constructing output. Count the bytes retained,
the number of boundaries, and compute
`retained + boundary_count * separator_length` with checked arithmetic. Reject
overflow or a result above 1 MiB, then allocate once and perform the transform.
This prevents a near-limit input and a 255-byte separator from causing a
hundreds-of-megabytes temporary allocation.

## Record construction and process behavior

Single-line output, environment, and state records are constructed as:

```text
NAME `=` VALUE LF
```

The buffer includes all framing and is complete before stdout is opened for
writing. Lazily duplicate the inherited stdout descriptor or handle through the
same safe platform I/O layer and write through an owned `File`. An observable
duplication failure is status 1 with no written bytes. The binary attempts to
write the full buffer through one high-level write operation and then flushes.
Short writes are handled as I/O errors or completed by the standard I/O
primitive; any failure after the first successful byte is allowed to leave a
prefix.

On POSIX, a stdout descriptor closed before runtime initialization has already
been replaced by `/dev/null`; writing succeeds and status 0 is possible even
though the record is discarded. On Windows, invalid handles remain observable
and require status 1. Supported writer invocations redirect stdout to an opened
runner file and do not rely on startup-closed-descriptor detection.

On POSIX, rely on Rust runtime initialization to ignore SIGPIPE and
regression-test that `EPIPE` reaches normal error handling as status 1. This
must not require a libc dependency or production `unsafe` code.

Diagnostics are fixed trusted messages written with fallible `Write` calls,
never `print!`, `println!`, `eprint!`, or `eprintln!`; a diagnostic write failure
does not replace the original exit classification. No diagnostic begins with
`::`, because GitHub runner command processing can observe stderr as well as
stdout.

The production entry point installs a fixed-message panic hook and wraps normal
execution in `catch_unwind`, mapping recoverable internal panics to status 1.
Release profiles retain `panic = "unwind"`. Abort conditions such as allocator
failure are not recoverable process errors and are outside this mapping. The
production crate uses `forbid(unsafe_code)`, and CI denies the Clippy stdout and
stderr print-macro lints.

Help and version output are trusted static data and do not read stdin. They use
the same checked stdout path: successful output exits 0, while an observable
stdout failure exits 1. The POSIX startup substitution remains an exception.
The main function maps only these classes:

| Class | Status |
| --- | --- |
| Success, help, version | 0 |
| Input, policy, randomness, internal, or I/O failure | 1 |
| Command-line usage error | 2 |

## Implementation history

Completed sequencing and superseded increment plans are retained in
[`implementation-history.md`](implementation-history.md). Current command
contracts and lasting command-specific implementation constraints live under
[`commands/`](commands/).

## Current implementation increment

The stdout writers are compiled into the normal executable without a feature
opt-in. Their encoders and input policies are unchanged by promotion. The parser
still dispatches through one enumerable command table, now checked against the
complete eight-command surface. Explicit stdout integration targets and fresh
corpus exports remain in CI; artifact tests exercise the same normal binary.
The former isolation rationale is retained in its superseded decision record.

## Next increment: stdout productization

Implementation is in progress against the finite handoff below. It remains
open until final-candidate verification, evidence, review and main-side external
admission checks complete; code promotion alone does not finish the increment.

This is a finite implementation handoff, not authorization to publish a
release. Follow the [stdout adoption contract](design.md#stdout-adoption-contract)
and [release policy](release.md); do not reintroduce historical native-runtime
proof obligations as implementation prerequisites.

1. Prepare the admission verification wiring identified by the test plan:
   make the Unicode-policy probe scheduled/manually runnable, pin profile
   selectors to named generations rather than `windows-latest`, extend trusted
   default-branch mask-log verification to all package-matched profile jobs,
   and bind publication eligibility and final publish to its completed source
   run/attempt/SHA and the policy results. Acceptance: event-routing and
   negative-gate tests prevent incomplete or mismatched evidence from admitting
   stdout; current partial orchestration is not mistaken for completed coverage.
2. Promote mask and notice/warning/error together with message and TITLE/FILE
   to the intended official command surface. Update the enumerable dispatch
   table, feature gates, stdout-only dependency configuration, integration-test
   selection, help, and version handling consistently. Acceptance: official
   builds expose exactly the newly agreed allowlist; architecture-specific
   packaging does not silently broaden the design-owned consumer profile. No test is silently lost
   because its former research feature is absent. Existing input acceptance,
   output bytes, diagnostics, and limits remain unchanged.
3. Update artifact inspection, build-target separation, release smoke tests,
   the stable-document checker, and their positive controls for the new
   surface. Acceptance: each release target's native binary and package have
   the intended commands and version output; malformed or unintended surfaces
   still fail verification. Preserve the guarantees of existing file writers.
4. Update the README, installation/release guidance, command-status notices,
   and isolation decision together. Add usable examples referencing the
   design-owned profile and existing mask precautions, without requiring
   Worker-culture attestation. Acceptance: user-facing documents and packaged
   help agree with the tested binary; no research-build instructions are
   presented as the supported installation path.
5. After all productization changes, run proportional local verification and
   full candidate CI, independent review, and latest-head Codex review. Create
   the durable compatibility snapshot from that final candidate, including
   exact source/dependency identities and the completed external gates. Refresh
   affected evidence and the snapshot after any review correction; an initial
   pre-change run cannot certify the resulting binary. Acceptance: all gates
   converge for the final candidate SHA, known mismatches remain visible, and
   no unresolved applicable security finding remains. Publication is a separate
   explicitly authorized task subject to main-source external verification.

Do not include new encoders, decoration, expanded environment support, new
input-policy generation, or Runner/.NET/ICU internal proofs in this increment.
An observed failure is first classified by attack path and product effect;
necessary behavior changes beyond this handoff return to contract review.

## CI and quality gates

CI begins in the first implementation PR and expands with each supported
platform. At minimum it runs:

- formatting checks;
- lints with project warnings denied;
- unit and integration tests on Linux, macOS, and Windows;
- an explicit MSRV `cargo test` job so development dependencies are checked;
- current stable Rust jobs; and
- dependency vulnerability, source, and license policy covering normal and
  development dependencies.

Third-party CI actions are pinned by full commit digest and workflows declare
minimal explicit `permissions`. The release profile keeps overflow checks
enabled as defense in depth even though security-relevant arithmetic uses
checked operations.

Production code forbids `unsafe`. A narrow Windows test launcher may require
platform FFI to create genuinely closed inherited handles; keep it test-only,
document its invariants, and isolate it from production code. An unpaired
surrogate alone uses safe `OsStringExt::from_wide` and does not justify FFI.

Before the first release, implement the repeatable build inputs, artifact
checksums, provenance, and publication gates defined by the
[release design](release.md). Bit-for-bit reproducibility is not claimed until
it is separately demonstrated. Packaging and distribution remain separate
decisions from the encoder implementation.

## Review gates

Each implementation PR is reviewed against the observable contract rather than
only for internal code quality. A PR is not complete when tests merely mirror
the implementation; relevant contract rows must be traceable to independent
expected results.

Before the first release:

1. all named-writer implementation increments are complete;
2. property and pinned-runner differential tests pass;
3. supported workflow shell smoke tests pass;
4. documentation declares exact supported invocations and runner versions;
5. no unresolved high- or medium-severity security review findings remain; and
6. no incomplete command is presented as supported.
