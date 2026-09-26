# Design notes

This document records decisions and open questions while `shoutx` is being
designed. The README defines the intended product contract; this file may
describe alternatives that have not been accepted.

Security scope and trust assumptions are defined in the
[threat model](threat-model.md).
The contract-derived verification matrix is defined in the
[CLI contract test plan](test-plan.md).

## Product boundary

`shoutx` prevents injection when CI workflows write values across output
boundaries. It provides runtime writers and context encoders rather than static
workflow analysis or attack-path discovery.

The initial provider is GitHub Actions. Provider-specific behavior is isolated
behind namespaced commands so support for other workflow engines can be added
without pretending their protocols are interchangeable.

## MVP command candidates

Provider-specific writers:

```text
shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
shoutx github-actions:path   [VALUE]
```

Reusable context encoders under consideration for v1.0:

```text
shoutx shell:arg      [VALUE]
shoutx markdown:text  [VALUE]
```

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
13. Every input path has the same documented hard size limit.

## Command model

Provider writers use `PROVIDER:DESTINATION`. Reusable encoders use
`LANGUAGE:CONTEXT`.

A value argument is used when present. Otherwise, input is read from stdin when
stdin is not a terminal. With no value and terminal stdin, commands fail with
usage status 2 instead of waiting. A closed stdin descriptor is an I/O failure
with status 1, not an empty value.

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

`--help` and `--version` are recognized only while options are being parsed.
After `NAME`, the same tokens are values rather than options.

Encoded output is written to stdout and diagnostics to stderr. This preserves
normal Unix composition and keeps destination selection visible in the calling
workflow.

## GitHub Actions output and environment contract

### Record names

Name policy belongs to the destination rather than to a provider-wide or
universal grammar:

```text
github-actions:output  [A-Za-z_][A-Za-z0-9_-]*
github-actions:env     [A-Za-z_][A-Za-z0-9_]*
```

Both names are limited to 255 ASCII bytes. Hyphens are supported for outputs
because GitHub's action metadata grammar permits them and established actions
use names such as `cache-hit` and `artifact-id`. Environment names use the
portable shell-variable subset.

The environment writer rejects names beginning with `GITHUB_` or `RUNNER_` and
the exact name `NODE_OPTIONS`, using ASCII case-insensitive comparisons. It
does not inspect the destination file, detect assignments from other
invocations, or guarantee uniqueness; duplicate handling remains runner and
caller behavior.

### Text and line boundaries

Input is strict UTF-8. Invalid byte sequences are rejected rather than replaced
with U+FFFD. A UTF-8 byte-order mark, if present, is value data (U+FEFF) and is
not stripped. NUL is rejected in every mode, including portions discarded by a
lossy mode.

For normalization, a line boundary is CRLF, LF, or bare CR. CRLF is one
boundary. Unicode NEL, LINE SEPARATOR, and PARAGRAPH SEPARATOR are ordinary
value characters because they do not delimit runner command-file records.

Every mode except `--multiline` first consumes at most one final CRLF, LF, or
bare CR as input framing. This rule applies equally to argv and stdin input.
Default mode then rejects the value if any CR or LF remains. It emits `NAME=VALUE`
followed by LF. Thus `abc`, `abc\n`, `abc\r\n`, and `abc\r` all represent
`abc`, while `abc\n\n` and `abc\nxyz\n` fail. This narrow, documented
normalization makes ordinary one-line CLI producers compose naturally without
allowing a value to create another record.

After that common framing step, `--first-line` keeps the prefix before the first
remaining line boundary and discards the boundary and remainder. The complete
input is still read and validated before normalization. An empty first line is
a valid empty value.

After that common framing step, `--join-lines` replaces every remaining line
boundary with one ASCII space (U+0020). `--join-lines-with STRING` replaces
every remaining boundary with `STRING`; the separator may be empty, is limited
to 255 UTF-8 bytes, and may not contain NUL, CR, or LF. Consequently, `a\n`
becomes `a`, `a\n\n` becomes `a `, and `a\n\nb\n` becomes `a  b` with
`--join-lines`.

### Multiline framing

`--multiline` preserves the complete value. A successful encoded record parsed
by the local supported runner must yield exactly the requested name and value
and no additional record.

The delimiter is `SHOUTX_` followed by 32 lowercase hexadecimal digits, giving
128 independently generated CSPRNG bits. It is never derived from the value and
contains no whitespace, CR, LF, `=`, or `<<`. Before output begins, shoutx
verifies that the delimiter byte sequence does not occur anywhere in the value;
a collision causes regeneration, and exhaustion or randomness failure causes a
failure with no stdout output.

The complete layout is `NAME<<DELIMITER LF VALUE SEPARATOR DELIMITER LF`. The
final delimiter line is always LF-terminated so another writer can append a new
record safely.

The encoder always adds a framing separator after the exact value. It normally
uses LF. When the target runner OS is Windows and the value ends in bare CR, it
uses CRLF so the Windows runner removes the added CRLF while preserving the
value's original trailing CR. The target follows the trusted `RUNNER_OS` value
when it is present; otherwise it follows the native OS of the `shoutx` process.
An unrecognized `RUNNER_OS` is rejected when this distinction affects framing.
This supports a Linux executable invoked through WSL or Git Bash on a Windows
runner without confusing executable OS with parser OS. The encoded bytes are
platform-dependent but give the same semantic round trip on supported runners.

### Resource and process contract

The value is limited to 1 MiB (1,048,576 UTF-8 bytes) before normalization and
the normalized value is subject to the same limit. These limits apply equally
to argv and stdin. They bound shoutx resource use; they do not guarantee that
GitHub aggregate output limits or a later process environment will accept the
value. Before constructing a normalized value, the implementation computes its
UTF-8 size with checked arithmetic and rejects overflow or a result above the
limit. It must not allocate an expanded value merely to discover that it is too
large.

All validation, normalization, delimiter selection, size checks, and record
construction finish before stdout writing begins. Exit status 0 means success,
1 means input or policy rejection, I/O failure, or internal failure, and 2 means
command-line usage error. Help and version output exit 0. Exit status 1 does not
distinguish a pre-write failure from an I/O failure that may have left partial
bytes. Implementations ignore SIGPIPE and report EPIPE as an I/O failure so a
broken pipe follows the documented status contract. Diagnostics do not
reproduce names, values, separators, or delimiter-derived excerpts.
Implementations should submit the complete constructed record with one stdout
write operation where the host API permits it, reducing but not eliminating the
partial-write window.

The cross-platform guarantee is semantic equivalence through the local
supported runner parser, not byte-identical records across operating systems.
Supported invocations must preserve native-process stdout bytes. Legacy Windows
PowerShell and PowerShell Core before 7.4 are unsupported. PowerShell Core 7.4
and later preserves native-command stdout bytes under direct `>` and `>>`
redirection, but is not included in the release guarantee until differential
tests establish the invocation contract. Redirecting merged stderr and stdout
is unsupported because PowerShell treats the combined stream as text.

The CLI status contract does not itself guarantee that a workflow shell stops
the step. In PowerShell, callers must enable native-command error propagation
or check `$LASTEXITCODE` immediately after each invocation. Supported workflow
recipes and smoke tests must prove that a rejected write fails the step.

## Open questions

- Whether `shell:arg` belongs in v1.0 and which POSIX shells are covered.
- Whether `markdown:text` belongs in v1.0 and what rendering guarantees it
  can accurately make across supported surfaces.
- Cross-platform rules for `$GITHUB_PATH`, especially Windows runners.
- Implementation language, packaging, and supported installation methods.
- Whether provider extensions are compiled in, discovered as executables, or
  loaded through another plugin mechanism.
- Compatibility and versioning rules for provider extensions.

## Deferred scope

- Static workflow analysis and attack-path discovery.
- General JSON and HTML encoders.
- Arbitrary document sanitization.
- Providers other than GitHub Actions.
- A stable third-party plugin API.
