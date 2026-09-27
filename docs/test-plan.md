# CLI contract test plan

This document turns the `shoutx` CLI contract into an implementation test plan.
It covers `github-actions:output`, `github-actions:env`,
`github-actions:state`, `github-actions:path`, the shared input rules, and the
supported workflow-shell redirection paths.

The product contract is defined by the [README](../README.md), the design
decisions by [design.md](design.md), and the security boundary by
[threat-model.md](threat-model.md). If this plan disagrees with those files,
the disagreement must be resolved rather than silently encoded in a test.
The [Rust implementation plan](implementation-plan.md) maps these cases to
implementation increments without changing their expected behavior.

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

### `github-actions:state`

Apply the environment-name grammar cases without its reserved-name policy.
Accepted boundaries include `a`, `_`, `A0`, `GITHUB_ENV`, `RUNNER_OS`,
`NODE_OPTIONS`, and a 255-byte name. Reject an empty name; a leading digit or
hyphen; whitespace; hyphens; `=`, `<`, CR, LF, non-ASCII characters; and a
256-byte name. Every rejection has status 1 and empty stdout.

Feed multiple records to the pinned runner state handler and verify that a
case-colliding later record replaces the value while retaining the first name
spelling. The oracle must obtain the dictionary from
`ExecutionContext.CreateChild` without supplying an existing state dictionary,
and record that construction path; supplying a test-created dictionary with the
expected comparer would prove only the fixture's behavior. This characterizes
destination behavior; one shoutx invocation still emits exactly one requested
record and does not inspect earlier records.

## Workflow artifact declaration candidate

These cases define the pre-implementation gate for the
`github-actions:artifacts` candidate. They do not make the command public until
the hosted-runner availability checks pass.

### Command grammar and input

Test a missing or unknown variant as a usage error. `--help` and `--version`
succeed before the variant and after `file` or `oci` while the first data
operand is expected. `--` before the variant is not accepted. For either
variant, `--` immediately after the variant ends option parsing.

For `github-actions:artifacts file`, test `COMMAND file PATH`, `COMMAND file --
PATH`, stdin when PATH is omitted, empty argv and empty stdin, a dash-prefixed
path with and without `--`, and an extra operand. The argv value wins without
reading stdin. The stdin terminal, closed-handle, invalid UTF-8, NUL, and hard
limit cases follow the existing single-value rules. `COMMAND file --` selects
stdin. A dash-prefixed PATH without `--` is an unknown-option usage error. The
command has no line mode options.

For `github-actions:artifacts oci`, require exactly `REFERENCE DIGEST` after
option parsing. It never reads stdin. Missing or extra operands, an unknown
option, or a dash-prefixed reference without `--` are usage errors with status
2 and empty stdout. Once REFERENCE is consumed, a dash-prefixed DIGEST is data
and fails digest validation with status 1. Empty operands and values that fail
field validation are input errors with status 1 and empty stdout.

### File declarations

A successful file declaration has exact stdout:

```text
file://PATH LF
```

Cover relative, absolute, Unicode, internal-space, leading-space, URI-looking,
OCI-looking, and `#`-prefixed paths on Linux, macOS, and Windows. The explicit
`file://` prefix must force file interpretation and prevent comment skipping.
Consume at most one final CRLF, LF, or bare CR from PATH as producer framing.
Reject an empty result, remaining CR or LF, NUL, `=`, and every trailing scalar
in the Unicode `White_Space` property. Include final NEL, LINE SEPARATOR, and
PARAGRAPH SEPARATOR rejections, plus U+FEFF and U+200B preservation. Assert
empty stdout for every rejection.

The local model must reproduce only runner parsing and resolution behavior
needed for comparison: full-line Unicode trimming, explicit scheme selection,
relative resolution against `GITHUB_WORKSPACE`, native rooted-path handling with
a null container, rooted translation and outside-mount rejection with a job
container, directory exclusion, symlink behavior, base-name selection, and
SHA-256 calculation. Add a relative-container case to verify that it resolves
through the host workspace context. Test these as runner facts, not as
transformations or authorization performed by shoutx. Include a file that
changes between shoutx output and runner processing to demonstrate that shoutx
does not bind file identity or digest. Do not assert that the runner excludes
every non-regular special file.

### OCI declarations

A successful OCI declaration has exact stdout:

```text
oci://REFERENCE@DIGEST LF
```

Test each supported algorithm at its exact lowercase hexadecimal length:
`sha256` with 64 digits, `sha384` with 96, and `sha512` with 128. Reject an
unknown or uppercase algorithm, uppercase or non-hex digits, short and long
digests, empty reference or digest, NUL, CR, LF, and `=`. Include references
containing tags, registry ports, internal `@`, leading or trailing whitespace,
and strings resembling file paths. Verify that the runner returns the exact
reference and digest. The runner lowercases algorithm and hex internally; on
valid shoutx output this normalization must be a no-op.

### Limits, aggregation, and availability

Test records immediately below, at, and above the runner's 1 MiB per-step
command-file limit. A shoutx invocation must reject when its own complete
record exceeds the limit, but tests must not imply that it knows how many bytes
another process already appended. Through the actual runner handler, cover
identical deduplication, same-name conflicting digests, ordinal name
comparison, the 500-subject aggregate cap, and parse-level all-or-nothing
behavior for a step containing a malformed declaration. Parse-level failures
occur before aggregation and add nothing. Conflict and cap failures occur
during aggregation and leave subjects inserted earlier by that same step;
assert this non-transactional runner behavior explicitly.

The pinned runner differential test explicitly enables the server-side
`actions_runner_allow_artifacts_file` variable, without mutating the process
environment, and calls the actual write and list handlers. Separately test the
self-hosted `ACTIONS_RUNNER_ALLOW_ARTIFACTS_FILE` fallback with state restored
afterward. A hosted workflow probe on every supported runner writes a known
temporary file, appends the candidate encoding, and verifies in a later step
that `GITHUB_ARTIFACTS_LIST` contains exactly the expected base name, SHA-256
digest, and `file` kind. It must fail rather than skip when the variable is
absent, the list file is zero bytes, the enabled empty-list JSON remains
unchanged, or the expected subject is absent. Public support is blocked until
this probe passes across the supported matrix.

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

## Path records

Every successful `github-actions:path` invocation emits the validated path
followed by exactly one LF and no BOM. Test both argv and stdin and verify that
VALUE causes stdin to remain untouched. The command has no lossy or multiline
mode.

Target selection is exact and case-sensitive. Test `RUNNER_OS=Linux`,
`RUNNER_OS=macOS`, and `RUNNER_OS=Windows`, native fallback when the variable is
absent, and rejection of empty, differently cased, invalid-encoding, and other
unknown values. Unlike multiline named records, the target is always relevant.

### POSIX target grammar

Accept `/`, `/a`, `/a b`, `/a/./b`, `/a/../b`, repeated separators, trailing
separators, non-ASCII UTF-8, and U+FEFF away from the first character. Preserve
every accepted byte exactly. Reject relative paths, `./a`, `../a`, an empty
value, a leading U+FEFF, any CR or LF left after common final-boundary
consumption, NUL, and any value containing `:`.
Reject `"` even though it can occur in a POSIX filename, because it crosses the
runner container step-host argument boundary. Reject a path ending in `\` and
include both odd and even runs of trailing backslashes; .NET argument
re-tokenization must not silently change directory identity.

### Windows target grammar

Accept drive-absolute paths using either directory separator, UNC paths, and
fully qualified verbatim drive and UNC forms. Include spaces, dot segments,
repeated and trailing separators, non-ASCII UTF-8, and U+FEFF away from the
first character, and assert exact preservation. Cover `C:\`, `c:/tools`,
`\\server\share`, `//server/share`, `\\?\C:\`, and
`\\?\UNC\server\share`. Normal UNC separators may be mixed, so also accept
`/\server/share` and `\/server\share`.

Reject drive-relative `C:tools`, root-relative `\tools`, plain relative paths,
incomplete UNC forms, Win32 device forms such as `\\.\...`, an empty value, a
leading U+FEFF, any remaining CR or LF, NUL, and any value containing `;`.
Reject `"` and explicitly cover bare `C:`, `\\server`, `//./x`, `/\.\x`,
`//?/C:/x`, `\\?\C:/x`, `\\?\C:`, `\\?\UNC\server`,
`\\?\GLOBALROOT\x`, `\\?\Volume{x}\`, `\\?\pipe\x`, and
`\\.\UNC\server\share`. Reject lowercase `\\?\unc\server\share` because
the verbatim UNC marker is exact and uppercase. Include lower- and uppercase
drive letters. Tests must not require the path to exist or infer validity from
the test host filesystem.

Every path grammar, separator, quote, leading-BOM, and target-selection
rejection has status 1 and empty stdout. This includes an empty or otherwise
unknown `RUNNER_OS` value.

### Runner parser and effective ordering

Implement a separate test-only model of `File.ReadAllLines(path,
Encoding.UTF8)` and path-list handling. Compare it with the pinned runner on
native Linux and Windows. The corpus covers LF, CRLF, and bare CR separators on
both hosts; an initial UTF-8 BOM; U+FEFF after earlier file content; empty and
whitespace-only lines; a final unterminated line; multiple entries; and
duplicates.

Assert that empty lines are ignored but whitespace-only lines are retained,
that later distinct entries appear earlier in the effective PATH, and that the
last runner-equivalent duplicate determines precedence. Because the runner
uses current-culture string comparison, do not turn non-ASCII duplicate
equivalence into a portable shoutx guarantee. Use only printable ASCII for
portable duplicate fixtures, and add one native observation case showing the
runner's treatment of otherwise identical paths where one contains U+200B.
Also observe an embedded U+FEFF case so byte preservation is not confused with
effective duplicate identity.

Append a shoutx record to both an empty command file and a file containing an
earlier record. A supported value must have the same parsed text in both
positions; the leading-U+FEFF rejection specifically prevents the known
position-dependent exception.

The actual-runner fixture calls `AddPathFileCommand.ProcessCommand` with a test
execution context whose `DeferredPrependPath` is null and whose
`Global.PrependPath` is observable. A test-only handler subclass then exposes
the protected `AddPrependPathToEnvironment` path and asserts the final PATH,
including reverse ordering and an original PATH that already starts with the
complete prepend string plus the PATH separator. This distinguishes runner
execution from a local transcription of its list and join logic.

A separate native Linux characterization test exercises the runner's container
branch and its actual `ProcessInvoker` argument-string path. A test helper
standing in for `docker` records the argv it receives. Cover a normal path, a
double quote, and odd and even trailing-backslash runs, and assert the observed
token boundaries and bytes. This test independently grounds the quote and
trailing-backslash rejection instead of merely reproducing the runner's string
concatenation.

## Multiline records

For all three named writers, cover empty values, values with no boundary, every
mix of LF/CR/CRLF, multiple trailing boundaries, a trailing bare CR, Unicode,
BOM, and strings resembling runner syntax or workflow commands.

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
model. Its required cases and ordering assertions are specified under Path
records above.

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
grammar, parser, append-position, ordering, and shell tests above. A release
must not infer path compatibility from the named-writer tests.

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

- every normative deterministic case above is automated;
- property tests establish the one-input-to-one-record invariant;
- the pinned runner differential suite passes on Linux and Windows;
- supported shell redirection preserves stdout bytes;
- documentation names the tested runner versions and supported invocations;
  and
- a final security-focused review finds no unresolved high- or medium-severity
  contract, test, or implementation gap.
