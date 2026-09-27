# GitHub Actions named records

This specification covers `github-actions:output`, `github-actions:env`, and
`github-actions:state`. Cross-cutting product invariants remain in
[`design.md`](../design.md), and shared testing policy remains in
[`test-plan.md`](../test-plan.md). The Contract section is normative for these
commands; contradictions with the cross-cutting documents must be resolved.

## Contract

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

### Implementation constraints

Keep the runner parser model independent of production record construction so
it cannot validate itself.

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

## Boundary-specific threat analysis

### `github-actions:output`

The security property is structural integrity of one `$GITHUB_OUTPUT` record.
An attacker-controlled value must not define another output name or terminate a
multiline record early.

Every non-multiline named-writer mode consumes one optional final CRLF, LF, or
bare CR before applying its mode-specific rule. Default mode rejects any
remaining CR or LF.
Multiline mode uses the documented
`NAME<<DELIMITER` framing and verifies, more conservatively, that the selected
delimiter does not occur anywhere in the value. Framing preserves empty values
and trailing LF, CRLF, and bare CR.

The command accepts names matching `[A-Za-z_][A-Za-z0-9_-]*`, up to 255 ASCII
bytes. This matches GitHub's documented action-output identifier grammar,
including established kebab-case output names. It does not protect later use of
the output. If a later `run:` block inserts the output directly as an
expression, shell injection is again possible.

GitHub applies separate limits to job and workflow outputs. Passing `shoutx`
validation does not guarantee that GitHub will accept or propagate the output.

### `github-actions:env`

The security property is structural integrity of one `$GITHUB_ENV` record. An
attacker-controlled value must not define another variable or terminate a
multiline record early.

The command accepts names matching `[A-Za-z_][A-Za-z0-9_]*`, up to 255 ASCII
bytes. It rejects `GITHUB_*`, `RUNNER_*`, and `NODE_OPTIONS` using ASCII
case-insensitive comparisons. This is intentionally stricter than the current
runner file parser and reflects GitHub policy and portable environment-variable
use.

The command does not read the destination file and cannot detect duplicate or
case-colliding assignments made by another invocation. The runner's handling of
such assignments and caller-level uniqueness are outside this command's
guarantee.

The command does not make later uses of the variable safe for shell, SQL, URLs,
templates, or other contexts. It also does not make environment variables an
appropriate channel for secrets.

### `github-actions:state`

The security property is structural integrity of one `$GITHUB_STATE` record.
An attacker-controlled value must not define another state name or terminate a
multiline record early. Injected state could change later cleanup behavior in
the same action, including which process, path, or resource a `post:` phase
operates on.

The command shares the named-writer value, line-mode, multiline-framing, size,
and failure contracts. It accepts names matching
`[A-Za-z_][A-Za-z0-9_]*`, up to 255 ASCII bytes. It has no environment
reserved-name block because GitHub exposes the value with a `STATE_` prefix.
The runner compares saved state names ordinally without regard to case. A later
case-colliding record replaces the value while retaining the first record's
name spelling. shoutx does not inspect earlier records or prevent that
replacement.

GitHub exposes saved values only to another phase of the same action; a write
from an ordinary workflow step has no such consumer. shoutx does not expand
that scope and does not make later consumption safe. Cleanup code must still
authorize paths, process identifiers, and other state before acting on them.

## Command-specific verification

### Record-name verification

#### `github-actions:output`

Accepted boundaries include `a`, `_`, `A0`, `cache-hit`, and a 255-byte name.
Reject an empty name; a leading digit or hyphen; whitespace; `=`, `<`, CR, LF,
non-ASCII characters; and a 256-byte name. NUL cannot appear in a process
argument on the supported host APIs and therefore needs no executable CLI
case; the grammar still excludes it. Every rejection has status 1 and empty
stdout.

#### `github-actions:env`

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

#### `github-actions:state`

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

### Multiline verification

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
