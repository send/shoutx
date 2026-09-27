# Design notes

This document records decisions and open questions while `shoutx` is being
designed. The README defines the intended product contract; this file may
describe alternatives that have not been accepted.

Security scope and trust assumptions are defined in the
[threat model](threat-model.md).
The contract-derived verification matrix is defined in the
[CLI contract test plan](test-plan.md).
Implementation sequencing and Rust-specific architecture are defined in the
[Rust implementation plan](implementation-plan.md).

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

The next specified provider command is not yet implemented or exposed by the
CLI:

```text
shoutx github-actions:mask [VALUE]
```

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
14. A stdout workflow-command writer emits exactly one command line whose
    decoded data equals the accepted value; it does not claim that runner log
    masking prevents every disclosure of that value.

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

`--help` and `--version` are recognized only while options are being parsed.
After `NAME`, the same tokens are values rather than options.

Encoded output is written to stdout and diagnostics to stderr. This preserves
normal Unix composition and keeps destination selection visible in the calling
workflow.

## GitHub Actions named-writer contract

### Record names

Name policy belongs to the destination rather than to a provider-wide or
universal grammar:

```text
github-actions:output  [A-Za-z_][A-Za-z0-9_-]*
github-actions:env     [A-Za-z_][A-Za-z0-9_]*
github-actions:state   [A-Za-z_][A-Za-z0-9_]*
```

All names are limited to 255 ASCII bytes. Hyphens are supported for outputs
because GitHub's action metadata grammar permits them and established actions
use names such as `cache-hit` and `artifact-id`. Environment and state names
use the portable shell-variable subset because saved state is later exposed as
an environment variable with a `STATE_` prefix.

The environment writer rejects names beginning with `GITHUB_` or `RUNNER_` and
the exact name `NODE_OPTIONS`, using ASCII case-insensitive comparisons. It
does not inspect the destination file, detect assignments from other
invocations, or guarantee uniqueness; duplicate handling remains runner and
caller behavior.

The state writer has no reserved-name block. GitHub exposes a saved name to
another phase of the same action with a `STATE_` prefix, so a name such as
`GITHUB_ENV` does not overwrite `GITHUB_ENV`; it becomes `STATE_GITHUB_ENV`.
The saved value is exposed only to another phase of the same action; this is
not a general workflow environment channel. The pinned runner compares state
names ordinally without regard to case. A later duplicate or case-colliding
record replaces the value but retains the first record's name spelling.
shoutx emits one record and does not inspect the destination file or detect
such collisions.

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

Rust runtime initialization reopens inherited POSIX standard descriptors that
were already closed using `/dev/null`. Consequently a startup-closed POSIX
stdout exposes no I/O error and may discard a successful record with status 0.
This exception does not apply to failures surfaced after writing begins or to
observable invalid Windows handles. Supported writer invocations redirect
stdout to an opened runner environment file.

The cross-platform guarantee is semantic equivalence through the local
supported runner parser, not byte-identical records across operating systems.
Supported invocations must preserve native-process stdout bytes. Legacy Windows
PowerShell and PowerShell Core before 7.4 are unsupported. PowerShell Core 7.4
and later preserves native-command stdout bytes under direct `>` and `>>`
redirection and is included in the release guarantee with differential and
workflow-smoke coverage. Redirecting merged stderr and stdout is unsupported
because PowerShell treats the combined stream as text.

The CLI status contract does not itself guarantee that a workflow shell stops
the step. In PowerShell, callers must enable native-command error propagation
or check `$LASTEXITCODE` immediately after each invocation. Supported workflow
recipes and smoke tests must prove that a rejected write fails the step.

## GitHub Actions path contract

`github-actions:path [VALUE]` emits exactly one LF-terminated entry for
`$GITHUB_PATH`. It has no line-mode options. `--` ends option parsing and is
required for an argv value beginning with `-`.

[GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-system-path)
each line as a directory prepended to PATH for subsequent steps. The parser
details below are grounded in the pinned
[`AddPathFileCommand`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/FileCommandManager.cs#L127-L158),
not inferred from the named environment-file parser.

The command uses the shared strict UTF-8, NUL rejection, 1 MiB input limit,
input-source, diagnostic, exit-status, and pre-write validation rules. It
consumes at most one final CRLF, LF, or bare CR as CLI input framing, then
rejects an empty value or any remaining CR or LF. The emitted bytes are the
remaining value followed by LF; shoutx performs no path normalization.

The target path dialect follows an exact trusted `RUNNER_OS` value of `Linux`,
`macOS`, or `Windows`; if it is absent, the native process OS is used. An
unrecognized value is always rejected because path grammar and the effective
PATH separator are target-specific.

Only fully qualified paths are accepted. POSIX paths must begin with `/`.
Windows accepts these forms:

- an ASCII drive letter, `:`, and `/` or `\`, including a drive root;
- exactly two leading separators in any `/` and `\` combination followed by
  non-empty server and share components separated by either character, where
  neither component is `.` or `?`; or
- an exact `\\?\` prefix followed by either an ASCII drive letter, `:`, and
  `\`, or uppercase `UNC\` plus non-empty server and share components separated
  by `\`.

The verbatim prefixes and their structural separators are backslash-only;
forward slashes later in a verbatim path remain literal data. Drive-relative
forms such as `C:tools`, root-relative forms such as `\tools`, incomplete UNC
forms, mixed-separator spellings of `\\.\` or `\\?\`, Win32 device forms, and
verbatim namespaces other than drive and UNC are rejected. Thus paths under
`GLOBALROOT`, `Volume{...}`, and `pipe` are not accepted. The implementation
does not require the path to exist, resolve `.` or `..`, canonicalize symlinks,
change separator spelling, trim whitespace, or change case.

POSIX `:` and Windows `;` are rejected. Although either character can be path
data in some contexts, the runner later joins accepted lines with the target
OS PATH separator; accepting it would let one line become multiple effective
PATH entries. A double quote is rejected on every target because a container
step host interpolates the resulting PATH into a quoted `docker exec` argument
string; accepting it could terminate that argument and create another runtime
option. A POSIX path ending in `\` is also rejected: .NET re-tokenizes that
argument string, so trailing backslashes can escape the synthetic closing quote
or be collapsed, changing the directory identity. Other platform-specific
invalid filename characters are not validated because shoutx neither accesses
the directory nor claims that the OS will accept it.

A leading U+FEFF is rejected. When the entry is the first content in the
command file, `File.ReadAllLines(..., Encoding.UTF8)` consumes its UTF-8 bytes
as a byte-order mark; when earlier content exists, the same bytes are retained.
Rejecting the ambiguous value makes the result independent of append position.
U+FEFF elsewhere is preserved, and shoutx never emits an encoder-added BOM.

In the pinned v2.337.0 runner, `AddPathFileCommand` uses
`File.ReadAllLines(filePath, Encoding.UTF8)`. It ignores empty lines, processes
non-empty lines in file order, removes a matching earlier path using its
current-culture comparison, and adds the new path to an internal prepend list.
It reverses that list when constructing PATH, so a later distinct entry has
higher command-lookup priority. shoutx emits one entry and does not inspect the
destination file, deduplicate entries, or promise stable duplicate equivalence
across runner cultures.

Current-culture equality can treat distinct Unicode strings as duplicates,
including strings that differ by default-ignorable characters. Exact UTF-8
preservation therefore does not imply stable duplicate identity. On non-Linux
hosts, the runner's later PATH helper also uses an ordinal-ignore-case prefix
check and avoids prepending the complete string when PATH already starts with
that string followed by the PATH separator. These are runner behaviors, not
shoutx deduplication guarantees.

This is structural validation, not authorization. The caller must establish
that the directory and executables reachable through it are trusted.

## GitHub Actions log-mask command

`github-actions:mask [VALUE]` registers one value with the current job's
runner-side secret masker by writing
one [`add-mask` workflow command][workflow-mask-command] to stdout. Unlike
environment-file writers, its successful stdout is intentionally consumed
directly by the runner and must not be redirected to an environment file.

The command follows the shared single-value source rule. An argv value wins and
stdin is not read; otherwise non-terminal stdin is read through EOF. `--` ends
option parsing and is required for a dash-prefixed argv value. There is no name
operand and there are no first-line, join, or multiline modes. The complete
semantic value is registered rather than normalized into a different secret.
As with the other stdin interfaces, at most one final CRLF, LF, or bare CR is
consumed as producer framing. All remaining CR and LF are value data.

Input is strict UTF-8, rejects NUL, and uses the standard 1 MiB input limit.
After optional producer framing, an empty value or a value consisting only of
Unicode whitespace is rejected before stdout begins. This mirrors the runner's
`String.IsNullOrWhiteSpace` rejection; accepting such a value locally would
report success without registering a mask. The whitespace classification is
the .NET 8 `Char.IsWhiteSpace` set, equivalent here to the Unicode
`White_Space` property. U+FEFF and U+200B are not whitespace under that rule.

Successful output is exactly:

```text
::add-mask::ENCODED_VALUE LF
```

The encoder applies replacements in this order: `%` with `%25`, CR with `%0D`,
then LF with `%0A`. No other character is escaped. This is the encoding used by
[`@actions/core.setSecret`][toolkit-command] and inverted by the runner's
workflow-command parser. Escaping `%` first prevents a literal sequence such as
`%0A` from becoming a line break during runner decoding. Encoding CR and LF
ensures the process emits one physical command line, and `::` inside the value
cannot create another command because the runner treats only the first command
separator as structural.

The implementation computes the encoded length with checked arithmetic and
constructs the complete line before opening stdout for writing. The 1 MiB
input can expand to at most 3 MiB plus the fixed prefix and LF. GitHub documents
no separate dynamic-mask or workflow-command line limit, and the pinned runner
applies no explicit command-line length check before its stream reader, so this
is a shoutx resource limit rather than a provider-capacity promise. Large or
structured values remain discouraged under GitHub's
[secure-use guidance][secure-use]: runner registration derives multiple encoded
variants and exact-match redaction becomes less reliable when a value is
transformed.

On receipt, the runner registers both the exact decoded value and every
trimmed, nonempty item produced by splitting it on CR and LF. This occurs even
for a single-line value: registering ` secret ` also registers `secret`. It can
therefore broaden masking for both single-line and multiline values and is
runner behavior, not a shoutx normalization promise. Empty items and
whitespace-only items are not independently registered. Registration is
job-local and affects only subsequent runner output. The command itself is
configured not to echo its data; when workflow-command echoing is enabled, the
runner prints a masked placeholder.

The security property is structural integrity and faithful registration of one
accepted value while workflow-command processing is active. It is not a
confidentiality guarantee. In particular:

- output produced before registration remains visible;
- shell tracing, process inspection, audit logging, or a compromised runner
  can disclose the value before the runner masker sees it;
- transformed, split, or encoded forms are not necessarily masked unless the
  runner derives that exact form or the caller registers it separately;
- short or common values can over-mask unrelated log text;
- a preceding `stop-commands` command causes the runner to ignore `add-mask`
  until the matching resume token, causing the encoded command line itself to
  be logged as ordinary output; shoutx cannot observe that state; and
- values treated as secrets can be suppressed when exported as job outputs,
  even though GitHub documents same-job use through a step output.

Callers should pass sensitive values through stdin or a quoted environment
variable rather than placing them literally in process arguments. They must
ensure workflow-command processing is active and register a value before any
command can log it. If an unmasked value has already reached a workflow log,
masking it later is not remediation; delete the log and rotate the credential.

[toolkit-command]: https://github.com/actions/toolkit/blob/a7911ca44eeaa6d87ad79a4703b750fb0993fb99/packages/core/src/command.ts
[workflow-mask-command]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#masking-a-value-in-a-log
[secure-use]: https://docs.github.com/en/actions/reference/security/secure-use

## Markdown output decision

`markdown:text` is not a v1.0 candidate. GitHub documents job summaries as
[GitHub Flavored Markdown][job-summaries], and its documented
[markup pipeline][github-markup] applies HTML sanitization before rendered
content is displayed. A value written to `$GITHUB_STEP_SUMMARY` does not feed
records back into the runner command protocol. Under the current threat model,
there is therefore no comparable workflow-execution injection boundary for a
generic Markdown encoder to protect.

Attacker-controlled Markdown can still mislead readers, contain links, alter
document structure, mention users, or disclose a value that the workflow chose
to publish. Those are content-policy and data-flow concerns rather than the
record-injection problem addressed by the implemented writers. Preserving
normal Markdown usability while distinguishing malicious from intended content
also requires application-specific policy.

This decision does not cover an unredirected process writing attacker-controlled
lines to the workflow log. The `add-mask` command is specified separately and
other GitHub Actions stdout workflow commands remain deferred. A future
Markdown feature requires a concrete threat and named rendering surface rather
than a renderer-independent promise.

[job-summaries]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
[github-markup]: https://github.com/github/markup#github-markup

## Workflow artifact declaration candidate

GitHub now [documents `$GITHUB_ARTIFACTS`][workflow-artifacts-command] as a
per-step command file containing one file path or OCI reference per line. A
newline in attacker-controlled input
can therefore add a second artifact subject to the job-scoped aggregate. This
is a structural output boundary and a plausible future shoutx destination, but
support remains conditional on hosted-runner availability testing.

The candidate interface is deliberately typed:

```text
shoutx github-actions:artifacts file [PATH]
shoutx github-actions:artifacts oci REFERENCE DIGEST
```

The command name follows the actual `GITHUB_ARTIFACTS` destination. The `file`
and `oci` variants prevent the runner's scheme-free syntax from guessing a
record type from its contents. Successful output always uses an explicit
scheme:

```text
file://PATH LF
oci://REFERENCE@DIGEST LF
```

There is no untyped or raw variant. `github-actions:artifacts file` follows the
usual single-value source rule: an argv `PATH` wins, otherwise stdin is read.
It consumes at most one final CRLF, LF, or bare CR as producer framing and
rejects every remaining CR or LF. `github-actions:artifacts oci` requires both
operands and never reads stdin; omitting either operand or supplying another is
a usage error.

The first token after `github-actions:artifacts` must be `file` or `oci`;
missing and unknown variants are usage errors. `--help` and `--version` are
recognized before the variant and after it while the first data operand is
still expected. A `--` before the variant is not supported. After `file` or
`oci`, `--` ends option parsing. `file --` with no PATH selects stdin. For
`oci`, option parsing ends when REFERENCE is consumed, so the following token
is always DIGEST data even when it begins with `-`.

Both variants require valid UTF-8, reject NUL and `=`, and reject an empty
semantic value. The runner trims the complete declaration before parsing it.
Because the explicit scheme protects whitespace at the beginning of PATH but a
file PATH occupies the end of its record, shoutx rejects a final scalar in the
Unicode `White_Space` property rather than silently changing identity. This is
the set used by .NET 8 `Char.IsWhiteSpace` and includes final NEL, LINE
SEPARATOR, and PARAGRAPH SEPARATOR; U+FEFF and U+200B are not members and remain
data. Other whitespace is preserved. OCI reference whitespace is internal to
its record, before `@DIGEST`, and is preserved; its semantic validity remains
the caller's responsibility.

PATH and REFERENCE each use the standard 1 MiB input limit. In addition, the
complete emitted record, including scheme and LF, must be no larger than the
runner's documented 1 MiB per-step file limit. A near-limit input can therefore
be rejected because of framing overhead. shoutx cannot account for records
already appended by other processes.

The file variant emits `file://` so a path that resembles an OCI reference
cannot change record type. Relative paths are permitted and are resolved by the
runner against `GITHUB_WORKSPACE`, not the step working directory. shoutx does
not canonicalize the path, require it to exist, resolve symlinks, translate
container paths, open it, or calculate its digest. The runner performs those
operations after the producer exits. Consequently shoutx provides record
integrity, not file identity, trust, authorization, or protection against
filesystem races.

The OCI variant accepts a reference as an opaque nonempty UTF-8 field subject
to the structural exclusions above. The caller remains responsible for OCI
reference validity and authorization. `DIGEST` must be lowercase `sha256:`,
`sha384:`, or `sha512:` followed by exactly 64, 96, or 128 lowercase
hexadecimal digits respectively. Uppercase input is rejected rather than
silently normalized. shoutx does not contact a registry or establish that the
reference resolves to the supplied digest.

The runner keys the aggregate by subject name using ordinal comparison; kind is
not part of the key. A file subject's name is only its base name, so distinct
paths with the same base name collide, as can a file base name and an equal OCI
reference. The runner deduplicates an identical name/digest pair, rejects a
conflicting digest for an existing name, and caps the job aggregate at 500
subjects.
shoutx emits one declaration, does not inspect `$GITHUB_ARTIFACTS_LIST`, and
does not promise runner acceptance in the presence of prior declarations.
`$GITHUB_ARTIFACTS_LIST` remains out of scope as a runner-managed read-only JSON
input rather than an output writer boundary.

The current runner implementation enables processing when either the
server-provided `actions_runner_allow_artifacts_file` feature flag or the
self-hosted runner process environment variable
`ACTIONS_RUNNER_ALLOW_ARTIFACTS_FILE` is true. When both are disabled it exposes
the command files but silently ignores declarations and leaves the list file at
zero bytes; when enabled with no subjects, the list contains
`{"version":1,"subjects":[]}`. Before this candidate becomes a supported
command, CI must prove on every supported hosted runner that a file declaration
appears with the expected name and digest in a later step's
`GITHUB_ARTIFACTS_LIST`. The pinned runner oracle must separately enable the
server-side feature variable without changing process-global state and exercise
the actual artifact handlers. Official documentation is the public contract,
but documentation alone is insufficient for a compatibility claim while
silent disablement exists.

The hosted-runner gate was exercised on 2026-09-28 in
[workflow run 36331651232][artifacts-availability-probe] using runner v2.337.0
on `ubuntu-latest` (`ubuntu-24.04`), `macos-latest` (`macos-26-arm64`), and
`windows-latest` (`windows-2025-vs2026`). On all three runners the declaration
file and list file variables were present, but the later step received a
zero-byte list file. This is the runner's disabled behavior, so the availability
gate failed uniformly. `github-actions:artifacts` therefore remains deferred
and must not be implemented or advertised. Reconsideration requires a new
hosted-runner probe that observes the expected subject on every supported OS;
the documented environment variables alone are not evidence that processing is
enabled.

[workflow-artifacts-command]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#declaring-workflow-artifacts
[artifacts-availability-probe]: https://github.com/send/shoutx/actions/runs/36331651232

## Open questions

- When GitHub enables `$GITHUB_ARTIFACTS` processing uniformly on supported
  hosted runners, allowing the deferred candidate to be reconsidered.
- Whether provider extensions are compiled in, discovered as executables, or
  loaded through another plugin mechanism.
- Compatibility and versioning rules for provider extensions.

## Deferred POSIX shell-word encoder

`shell:arg` is not a v1.0 candidate. A portable encoder can represent one
strict UTF-8 value as POSIX shell source by surrounding it with single quotes
and representing each embedded apostrophe outside the quoted region. POSIX,
Bash, and dash all define single quotes as preserving literal characters other
than an embedded single quote. The encoding algorithm is therefore not the
blocking issue.

The missing piece is a safe and natural consumption boundary. Shell command
substitution performs expansion after the surrounding command has already been
tokenized. Quote characters produced by `$(shoutx shell:arg VALUE)` are data,
not source-level quoting syntax: unquoted substitution remains subject to field
splitting and pathname expansion, while double-quoted substitution passes the
encoder's quote characters literally. Command substitution also removes
trailing newlines. Consequently, neither form consumes a generated shell word
as one argument.

The encoded result is useful only when incorporated into shell source that is
parsed later, such as a generated script or a string passed to another shell.
That use requires a trusted source composer to provide token separation,
command structure, output framing, and exactly one later parse. A one-word CLI
cannot enforce those conditions. Encouraging callers to recover the missing
parse with `eval` would directly conflict with the project's exclusion of
dynamic shell evaluation and would make nested parsing easy to introduce.

For ordinary GitHub Actions steps, pass runtime data through `env:` and expand
it as `"$VALUE"`. Other programs should prefer an argv-capable API over shell
source generation. Reconsider a shell encoder only with a concrete source-file
or protocol destination, a named dialect, and a composition contract that does
not rely on `eval`; a generic `shell:arg` command is too easy to consume
incorrectly.

This decision follows the [POSIX shell command language][posix-shell-language]
expansion order and quote-removal rules, the [Bash expansion
documentation][bash-shell-expansions], and the [dash manual][dash-manual].

[posix-shell-language]: https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html
[bash-shell-expansions]: https://www.gnu.org/software/bash/manual/html_node/Shell-Expansions.html
[dash-manual]: https://manpages.debian.org/unstable/dash/dash.1.en.html

## Deferred scope

- Static workflow analysis and attack-path discovery.
- General JSON and HTML encoders.
- Arbitrary document sanitization.
- Providers other than GitHub Actions.
- A stable third-party plugin API.
