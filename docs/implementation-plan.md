# Rust implementation plan

This document defines how the agreed CLI contract will be implemented. It is a
sequencing and architecture plan, not an additional product contract. The
[design](design.md), [threat model](threat-model.md), and
[CLI contract test plan](test-plan.md) remain authoritative for observable
behavior.

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
is complete. `shell:arg` and `markdown:text` likewise remain absent rather than
shipping placeholders whose behavior could be mistaken for stable API.

During incremental development, `--multiline` may be parsed but must not appear
in release artifacts until it is implemented. In the first PR it is rejected
with a non-zero status and empty stdout; it never falls back to single-line
output. Help lists only implemented features. No public release is cut from an
intermediate increment that advertises an unavailable documented mode.

## Input handling

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

Keep output and environment name validators separate even though they share an
ASCII prefix:

```text
output  [A-Za-z_][A-Za-z0-9_-]*
env     [A-Za-z_][A-Za-z0-9_]*
```

Validate the 255-byte limit independently of grammar. Environment reserved-name
comparisons use ASCII case folding only. Do not use locale-sensitive or Unicode
case conversion. Reject prefixes `GITHUB_` and `RUNNER_`, plus exact
`NODE_OPTIONS`; do not broaden those checks by substring matching.

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

Single-line output and environment records are constructed as:

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

On POSIX, explicitly retain Rust's ignored-SIGPIPE behavior at the crate level
and regression-test that `EPIPE` reaches normal error handling as status 1.
This must not require a libc dependency or production `unsafe` code.

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
- Invalid Windows stdin and stdout handles produce status 1; tests do not
  substitute the Windows NUL device or another valid sink.
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

An unrecognized `RUNNER_OS` is relevant only when platform-specific multiline
framing is required. The implementation follows the design contract rather than
silently treating an unknown target as POSIX.

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

## Later PR: `github-actions:path`

`github-actions:path` remains separate because the runner uses path-specific
`File.ReadAllLines` behavior rather than the named environment-file parser. Its
design increment must first resolve:

- BOM behavior for the first appended entry;
- bare-CR splitting on every runner OS;
- empty-line removal;
- absolute and relative path policy;
- Windows drive, UNC, and separator rules;
- whether lexical normalization would change directory identity; and
- ordering and duplicate behavior.

The command is implemented only after its contract and separate parser model
are reviewed. It must not inherit output/environment assumptions by code reuse.

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

Before the first release, add reproducible release builds, artifact checksums,
and provenance appropriate to the chosen distribution channels. Packaging and
distribution remain separate decisions from the encoder implementation.

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
