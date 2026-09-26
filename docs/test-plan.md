# CLI contract test plan

This document turns the proposed `shoutx` CLI contract into an implementation
test plan. It covers `github-actions:output`, `github-actions:env`, and the
shared input rules. It also records the minimum tests needed before
`github-actions:path` or PowerShell redirection can be included in a release
guarantee.

The product contract is defined by the [README](../README.md), the design
decisions by [design.md](design.md), and the security boundary by
[threat-model.md](threat-model.md). If this plan disagrees with those files,
the disagreement must be resolved rather than silently encoded in a test.

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

For single-line output and environment records, exact stdout is:

```text
NAME=VALUE LF
```

For multiline records, the generated delimiter is nondeterministic. Tests must
validate its grammar and uniqueness, then use the parser result as the oracle
instead of comparing the complete record with a fixture.

## Command-line grammar

Run applicable cases for both `github-actions:output` and
`github-actions:env`.

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

For `github-actions:path`, test that `--` is required to pass a value beginning
with `-`. Options other than global help/version and `--` are usage errors.

## Input-source selection

| VALUE operand | Stdin state | Expected source and result |
| --- | --- | --- |
| Present | Any bytes, terminal, or closed | Use VALUE without reading stdin |
| Omitted | Non-terminal with bytes | Read through EOF and use all bytes |
| Omitted | Non-terminal at EOF | Empty value |
| Omitted | Terminal | Do not wait; status 2 and empty stdout |
| Omitted | Closed descriptor | I/O diagnostic, status 1 and empty stdout |

The argv and stdin variants of every value-validation case must have identical
semantic results where the host process API can represent the value. NUL
requires byte-oriented stdin because host argument APIs cannot represent it.
Invalid UTF-8 requires both byte-oriented stdin and POSIX argv cases. On
Windows, use a small native launcher to pass an unpaired UTF-16 surrogate and
assert status 1 with empty stdout rather than a panic or process abort.

## Record names

### `github-actions:output`

Accepted boundaries include `a`, `_`, `A0`, `cache-hit`, and a 255-byte name.
Reject an empty name; a leading digit or hyphen; whitespace; `=`, `<`, CR, LF,
non-ASCII characters; and a 256-byte name. NUL cannot appear in a process
argument on the supported host APIs and therefore needs no executable CLI
case; the grammar still excludes it. Every rejection has status 1 and empty
stdout.

### `github-actions:env`

Accepted boundaries include `a`, `_`, `A0`, `PATH`, and a 255-byte name that
is not reserved. Reject all invalid output-name cases above and reject hyphens.
Reject the following policy classes using ASCII case-insensitive comparison:

| Class | Representative cases |
| --- | --- |
| `GITHUB_*` | `GITHUB_ENV`, `github_x`, `GiThUb_` |
| `RUNNER_*` | `RUNNER_OS`, `runner_x`, `RuNnEr_` |
| Exact `NODE_OPTIONS` | `NODE_OPTIONS`, `node_options`, mixed case |

Names such as `GITHUB`, `RUNNER`, `NODE_OPTION`, and `NODE_OPTIONS_X` remain
valid unless another rule rejects them. Duplicate or case-colliding assignments
from separate invocations are not detected by `shoutx` and are not negative
CLI tests. Every grammar or policy rejection has status 1 and empty stdout.

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

## Multiline records

For both named writers, cover empty values, values with no boundary, every mix
of LF/CR/CRLF, multiple trailing boundaries, a trailing bare CR, Unicode, BOM,
and strings resembling runner syntax or workflow commands.

For every success, assert all of the following:

- the delimiter matches `SHOUTX_[0-9a-f]{32}`;
- it was generated independently of the value and does not occur as a byte
  substring anywhere in the value;
- the header is `NAME<<DELIMITER LF`;
- the final delimiter line is LF-terminated;
- parsing produces exactly one record with the requested name and byte-exact
  UTF-8 value; and
- appending another valid record after stdout allows both records to parse.

Injectable randomness is recommended for deterministic collision tests. Force
the first candidate to occur in the value and assert regeneration before any
stdout write. Also test randomness failure and bounded retry exhaustion as
status 1 with empty stdout.

With `RUNNER_OS=Windows`, specifically verify a value ending in bare CR. The
encoder must add a CRLF framing separator, and the Windows runner parser must
return the original bare CR as value data. Repeat while invoking a non-Windows
executable through a Windows runner shell. With `RUNNER_OS=Linux` or `macOS`,
the same value must use LF framing even if the executable host differs. When
`RUNNER_OS` is absent, verify native-OS selection; when it is unrecognized and
the value ends in bare CR, verify status 1 and empty stdout.

## Limits and failure behavior

Test values of 1,048,575, 1,048,576, and 1,048,577 UTF-8 bytes before optional
final-boundary consumption, through argv where supported and through stdin. The
first two sizes succeed if otherwise valid; the last fails with status 1 and
empty stdout. Include a value at or below the input limit whose many boundaries
and 255-byte join separator would expand far beyond 1 MiB. Assert rejection
using checked size arithmetic before allocating the normalized result.

Test names and separators at 254, 255, and 256 bytes. Limits are byte counts,
not Unicode scalar counts. Names are ASCII by grammar; separators need
multibyte cases.

Diagnostics must identify the failed rule without containing the supplied
name, value, separator, generated delimiter, or excerpts derived from them.
Capture stdout and stderr separately. Include a value resembling
`::stop-commands::TOKEN` to ensure it is never copied to a diagnostic.

Cause a broken pipe and another short/failed stdout write. The process must
ignore SIGPIPE as a termination mechanism, report an I/O failure on stderr, and
exit 1. A partial stdout prefix is permitted only after writing began.

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
without CRLF translation or treating byte `0x1a` as end-of-file.

| Host | Invocation | Required before guarantee |
| --- | --- | --- |
| Linux GitHub-hosted runner | POSIX `sh` direct `>>` | Exact native stdout bytes and semantic round trip |
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

`github-actions:path` additionally needs native Linux and Windows tests for
absolute-path grammar, separators, normalization, and runner ordering. Those
rules remain an open design question, so a release must not infer them from the
named-writer tests. Its separate parser model must cover `File.ReadAllLines`,
including bare-CR splitting on every OS, empty-line removal, and BOM handling,
before the command moves from candidate to supported MVP scope.

For each supported workflow shell, a negative smoke test must place another
successful command after a rejected `shoutx` invocation and still observe step
failure. This catches shells that would otherwise mask the native exit status.
Run concurrency tests with parallel writers to characterize, but not guarantee
against, interleaving and lifecycle behavior.

## PR acceptance criteria

The implementation PR following this design work should not be considered
ready until:

- every normative deterministic case above is automated;
- property tests establish the one-input-to-one-record invariant;
- the pinned runner differential suite passes on Linux and Windows;
- supported shell redirection preserves stdout bytes;
- documentation names the tested runner versions and supported invocations;
  and
- a final security-focused review finds no unresolved high- or medium-severity
  contract, test, or implementation gap.
