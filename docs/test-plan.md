# CLI contract test plan

This document defines the test layers, shared input cases, runner differential
strategy, and supported-shell matrix for the `shoutx` CLI. Command-specific
matrices are colocated with the specifications linked below.

The product contract is defined by the [README](../README.md), cross-cutting
decisions by [design.md](design.md), destination contracts by the linked
[`commands/`](commands/) specifications, and the security boundary by
[threat-model.md](threat-model.md). If this plan disagrees with those files,
the disagreement must be resolved rather than silently encoded in a test.
The [Rust implementation plan](implementation-plan.md) maps these cases to the
current architecture without changing their expected behavior.

## Test layers

The implementation should be tested at four layers:

1. **CLI contract tests** invoke the built executable and assert stdout bytes,
   stderr policy, and exit status.
2. **Encoder property tests** generate names and values and assert that every
   successful record parses to exactly one requested name/value pair.
3. **Runner differential tests** feed emitted bytes to the parser from a pinned
   `actions/runner` release and compare its result with the local parser model.
4. **Workflow smoke tests** exercise documented redirection forms on GitHub-
   hosted runners. These detect integration drift but are not a stable semantic
   oracle because the hosted runner version changes independently.

Tests that expect validation, normalization, delimiter selection, randomness,
or size failure must assert empty stdout. Tests that deliberately cause stdout
I/O failure may observe a prefix and must assert status 1 without assuming
transactional output.

## Notation

Tables use `LF`, `CR`, and `CRLF` for their corresponding bytes. `BOM` means
the UTF-8 encoding of U+FEFF. `parse(record)` means parsing the complete stdout
with the destination parser on the named platform. Unless stated otherwise,
the name is `result`, input is supplied as one argv value, and success means
status 0 with empty stderr.

For single-line output, environment, and state records, exact stdout is:

```text
NAME=VALUE LF
```

For multiline records, the generated delimiter is nondeterministic. Tests must
validate its grammar and uniqueness, then use the parser result as the oracle
instead of comparing the complete record with a fixture.

## Command-line grammar

Run applicable cases for `github-actions:output`, `github-actions:env`, and
`github-actions:state`.

| Case | Invocation shape | Expected result |
| --- | --- | --- |
| Value operand | `COMMAND NAME VALUE` | `VALUE` is used; stdin is ignored |
| Empty value operand | `COMMAND NAME ""` | Empty value succeeds |
| Dash-prefixed value | `COMMAND NAME -x` | `-x` is value data |
| Literal dash | `COMMAND NAME -` | `-` is value data, not stdin syntax |
| End options | `COMMAND -- NAME VALUE` | Normal success |
| End-options token after name | `COMMAND NAME --` | `--` is the value |
| Mode before name | `COMMAND --first-line NAME VALUE` | Selected mode is applied |
| Mode after name | `COMMAND NAME --first-line` | Token is the value |
| Help before name | `COMMAND --help` | Help on stdout, status 0 |
| Help after name | `COMMAND NAME --help` | Token is the value |
| Version in option position | `shoutx --version` | Version on stdout, status 0 |
| Command version before name | `COMMAND --version` | Version on stdout, status 0 |
| Version after name | `COMMAND NAME --version` | Token is the value |
| Missing name | `COMMAND` with any stdin state | Do not read stdin; usage diagnostic, status 2 |
| Extra operand | `COMMAND NAME A B` | Usage diagnostic, status 2, empty stdout |
| Conflicting modes | Two mode options | Usage diagnostic, status 2, empty stdout |
| Missing separator | `--join-lines-with` without its argument | Usage diagnostic, status 2, empty stdout |
| Dash separator | `--join-lines-with -x NAME VALUE` | `-x` is the separator |
| Equals separator | `--join-lines-with=-x NAME VALUE` | `-x` is the separator |
| Empty separator | `--join-lines-with= NAME VALUE` | Empty separator succeeds |
| Unknown option | Unknown token before `NAME` | Usage diagnostic, status 2, empty stdout |

For `github-actions:path`, test `COMMAND VALUE`, `COMMAND -- VALUE`, stdin when
VALUE is omitted, and rejection of an extra operand. `--` is required to pass a
value beginning with `-`; without it, the token is an unknown option. Options
other than global help/version and `--` are usage errors. Help and version are
recognized only before VALUE. `COMMAND VALUE --help` is an extra-operand usage
error with status 2 and empty stdout. `COMMAND --` with no following token
selects stdin rather than an empty argv value.

## Input-source selection

| VALUE operand | Stdin state | Expected source and result |
| --- | --- | --- |
| Present | Any bytes, terminal, or closed | Use VALUE without reading stdin |
| Omitted | Non-terminal with bytes within limit | Read through EOF and use all bytes |
| Omitted | Non-terminal exceeding limit | May stop after the first excess byte; status 1 and empty stdout |
| Omitted | Non-terminal at EOF | Empty value |
| Omitted | Terminal | Do not wait; status 2 and empty stdout |
| Omitted | POSIX descriptor closed before process startup | Runtime substitutes `/dev/null`; empty value |
| Omitted | Invalid Windows handle | I/O diagnostic, status 1 and empty stdout |

The argv and stdin variants of every value-validation case must have identical
semantic results where the host process API can represent the value. NUL
requires byte-oriented stdin because host argument APIs cannot represent it.
Invalid UTF-8 requires both byte-oriented stdin and POSIX argv cases. On
Windows, use a small native launcher to pass an unpaired UTF-16 surrogate and
assert status 1 with empty stdout rather than a panic or process abort.
For `github-actions:path`, empty argv and empty stdin are input failures with
status 1 rather than successful empty records.

## Command-specific suites

Detailed command matrices are colocated with their specifications:

- [GitHub Actions named records](commands/github-actions-records.md)
- [GitHub Actions PATH writer](commands/github-actions-path.md)
- [GitHub Actions log-mask command](commands/github-actions-mask.md)

Deferred candidate gates live with their decision records:

- [GitHub Actions artifact declarations](decisions/github-actions-artifacts.md)

## Text validation

Run these cases in every mode, including data that `--first-line` would later
discard.

| Input | Expected result |
| --- | --- |
| Valid ASCII and multibyte UTF-8 | Accepted subject to mode rules |
| BOM at beginning, middle, or end | Preserved as U+FEFF value data |
| Unicode NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR | Preserved as ordinary data |
| Overlong, truncated, surrogate, or otherwise invalid UTF-8 | Status 1, empty stdout |
| NUL at beginning, middle, or end | Status 1, empty stdout |
| Valid prefix, first boundary, then invalid UTF-8 or NUL | Status 1, empty stdout |

Successful output must be valid UTF-8 without an encoder-added BOM.

## Non-multiline line semantics

All non-multiline modes first consume at most one final boundary. The following
matrix is normative; replace notation with actual bytes in tests.

| Input | Default | `--first-line` | `--join-lines` |
| --- | --- | --- | --- |
| empty | empty | empty | empty |
| `a` | `a` | `a` | `a` |
| `a LF` | `a` | `a` | `a` |
| `a CR` | `a` | `a` | `a` |
| `a CRLF` | `a` | `a` | `a` |
| `a LF LF` | reject | `a` | `a ` |
| `a CRLF CRLF` | reject | `a` | `a ` |
| `a CR CR` | reject | `a` | `a ` |
| `a LF b LF` | reject | `a` | `a b` |
| `a CR b CR` | reject | `a` | `a b` |
| `a CRLF b CRLF` | reject | `a` | `a b` |
| `LF a` | reject | empty | ` a` |
| `a LF CR` | reject | `a` | `a ` |
| `a CR LF` | `a` | `a` | `a` |

The final row is one CRLF boundary, not two boundaries. Add generated cases
that tokenize arbitrary sequences using the precedence `CRLF`, then bare `CR`
or `LF`. For `--join-lines-with STRING`, use the same cases with each remaining
boundary replaced by exactly one copy of `STRING`; include empty, ASCII,
multibyte, and 255-byte separators.

Reject separators containing NUL, CR, or LF and separators longer than 255
UTF-8 bytes. Separator validation happens even when the input has no boundary.

`github-actions:path` uses the same optional-final-boundary preprocessing as
the table, then rejects an empty result or any remaining boundary.

## Limits and failure behavior

Test values of 1,048,575, 1,048,576, and 1,048,577 UTF-8 bytes before optional
final-boundary consumption through stdin and directly against the library argv
input path. Host argument-block limits make executable-level argv tests at these
sizes non-portable. The first two sizes succeed if otherwise valid; the last
fails with status 1 and empty stdout. Include a value at or below the input limit
whose many boundaries and 255-byte join separator would expand far beyond 1
MiB. Assert rejection using checked size arithmetic before allocating the
normalized result.

Test names and separators at 254, 255, and 256 bytes. Limits are byte counts,
not Unicode scalar counts. Names are ASCII by grammar; separators need
multibyte cases.

Diagnostics must identify the failed rule without containing the supplied
name, value, separator, generated delimiter, or excerpts derived from them.
Capture stdout and stderr separately. Include a value resembling
`::stop-commands::TOKEN` to ensure it is never copied to a diagnostic. Assert
that no fixed diagnostic line begins with `::`, because runner command handling
can observe stderr as well as stdout.

Cause a broken pipe and another short/failed stdout write using deterministic
synchronization or an injected test writer rather than a scheduling race. The
process must ignore SIGPIPE as a termination mechanism, report an I/O failure on
stderr, and exit 1. A partial stdout prefix is permitted only after writing
began. An invalid Windows stdout handle must also produce status 1. On POSIX,
test and document that a descriptor closed before startup is replaced with
`/dev/null`, so the process cannot detect the discard and may exit 0.

## Runner parser model

The local model should implement only the environment-file behavior needed as
a test oracle, keeping platform line-reading behavior explicit. Given complete
UTF-8 file bytes and a platform mode, it returns an ordered list of parsed
records or the runner-equivalent parse error.

The model must cover:

- normal `NAME=VALUE` records;
- `NAME<<DELIMITER` records;
- ordinal delimiter comparison;
- LF and Windows CRLF line consumption;
- end indices used to extract multiline values without their framing newline;
- empty values and an absent final record terminator;
- malformed headers, missing delimiters, and trailing bare CR; and
- the runner's missing-newline error for an EOF marker with no preceding line
  terminator.

The model is not production code and must not become the sole compatibility
oracle. Unit tests should be derived from inspected runner source before the
model is used to validate the encoder.

The path command uses a separate model of `File.ReadAllLines(...,
Encoding.UTF8)` and `AddPathFileCommand`; it must not reuse the named-record
model. Its required cases and ordering assertions are specified in the
[PATH command specification](commands/github-actions-path.md#runner-parser-and-effective-ordering).

## Differential testing against `actions/runner`

Pin the initial oracle to `actions/runner` v2.337.0. Record both the tag and
resolved commit in the test fixture or dependency metadata. The harness should
compile or invoke the actual environment-file parser from that checkout; a
second handwritten transcription is not an independent oracle.

Run the same corpus through the local model and actual runner parser on native
Linux and Windows hosts. Compare ordered names, exact values, record counts,
and success or failure. The corpus includes:

- every deterministic case in this document;
- generated valid names and UTF-8 values across every line mode;
- malformed records that exercise parser error paths;
- delimiter-like substrings at every position;
- empty and unterminated files; and
- Windows trailing-bare-CR multiline framing.

Before each release, inspect the current `actions/runner` source and run the
suite against the newest supported release in addition to the pinned baseline.
A behavior difference blocks a compatibility claim until it is explained and
the contract, model, or supported-version declaration is updated.

## Shell and workflow matrix

The release matrix should capture executable stdout bytes before testing runner
semantics, so shell transcoding and parser behavior are diagnosed separately.
Windows contract tests must also prove that stdin is read as binary bytes,
without CRLF translation or treating byte `0x1a` as end-of-file. Use
discriminating inputs such as `a CR CRLF`, which default mode rejects only when
the bytes are preserved, and `a 0x1a b`, which must retain the control byte.

| Host | Invocation | Required before guarantee |
| --- | --- | --- |
| Linux GitHub-hosted runner | `sh` direct `>>` | Exact native stdout bytes and semantic round trip |
| Linux GitHub-hosted runner | Explicit Dash direct `>>` | Exact native stdout bytes, status propagation, and semantic round trip |
| Linux GitHub-hosted runner | Bash direct `>>` | Exact native stdout bytes and semantic round trip |
| macOS GitHub-hosted runner | Bash direct `>>` | Exact native stdout bytes and semantic round trip |
| Windows GitHub-hosted runner | PowerShell 7.4+ direct `>>` | Exact native stdout bytes, status propagation, and semantic round trip |
| Windows GitHub-hosted runner | Git Bash direct `>>` | `RUNNER_OS`-selected framing, exact bytes, and semantic round trip |

Legacy Windows PowerShell, PowerShell Core before 7.4, text-writing cmdlets,
`cmd`, and merged stdout/stderr redirection are negative documentation cases,
not supported configurations. A byte-capture-only test may use `>` with a new
temporary file; documented environment-file writes always use `>>` because `>`
can truncate prior records. PowerShell remains outside the release guarantee
until the Windows byte-capture, status-propagation, and runner differential
suites pass. Also test and document the failure of self-hosted Windows fallback
to unsupported Desktop PowerShell.

`github-actions:path` additionally requires the native Linux and Windows
grammar, parser, append-position, and ordering cases in the
[PATH command specification](commands/github-actions-path.md#command-specific-verification),
plus the shell tests in this section. A release must not infer path
compatibility from the named-writer tests.

`github-actions:state` additionally requires a local JavaScript fixture action
rather than an ordinary workflow `run:` step; composite actions cannot declare
a `post:` phase. Its `main` phase writes an attacker-style multiline value
through shoutx to `$GITHUB_STATE`, and its `post` phase verifies the exact
`STATE_NAME` value and the absence of a second attacker-selected key. A
case-collision case must read the first spelling of `STATE_NAME`; the runner
oracle is the discriminating name-spelling test because the Windows process
environment is case-insensitive. The fixture must also show that the state is
scoped to that action rather than exported as a general subsequent-step
environment variable. Generic shell-redirection coverage remains in the
named-writer shell matrix and is not inferred from this JavaScript fixture.

For each supported workflow shell, a negative smoke test must place another
successful command after a rejected `shoutx` invocation and still observe step
failure. This catches shells that would otherwise mask the native exit status.
Also test the runner-default stdin state with `VALUE` omitted, plus PowerShell
argv fidelity for an empty value, embedded quotes, and trailing backslashes.
Run concurrency tests with parallel writers to characterize, but not guarantee
against, interleaving and lifecycle behavior.

## PR acceptance criteria

The implementation PR following this design work should not be considered
ready until:

- every normative deterministic case in this plan and the applicable linked
  command specification is automated;
- property tests establish the one-input-to-one-record invariant;
- the pinned runner differential suite passes on Linux and Windows;
- supported shell redirection preserves stdout bytes;
- documentation names the tested runner versions and supported invocations;
  and
- a final security-focused review finds no unresolved high- or medium-severity
  contract, test, or implementation gap.
