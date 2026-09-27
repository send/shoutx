# GitHub Actions annotation commands

This specification covers the candidate `github-actions:notice`,
`github-actions:warning`, and `github-actions:error` commands. Cross-cutting
product invariants remain in [`design.md`](../design.md), and shared testing
policy remains in [`test-plan.md`](../test-plan.md). The Contract section is
normative for these commands; contradictions with the cross-cutting documents
must be resolved.

The commands are specified but not yet implemented or exposed by the CLI.

## Contract

The three commands emit one stdout workflow command that asks the GitHub
Actions runner to create an annotation and write its message to the workflow
log. They share one contract and differ only in the fixed command name and
severity. In particular, `github-actions:error` does not set the process exit
status or fail the step; callers that want failure must separately return a
nonzero status.

The usage is:

```text
shoutx github-actions:notice  [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]
shoutx github-actions:warning [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]
shoutx github-actions:error   [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]
```

### Command-line grammar and input

Options precede the optional message operand. Each option may appear at most
once and requires its following operand; `--option=value` is not accepted. An
option operand is data even when it begins with `-`. `--` ends option parsing
and is required for a dash-prefixed argv message. There is no dynamic severity
option and no raw property interface. Keeping three typed commands makes the
selected runner control operation visible at the call site.

MESSAGE follows the single-value source rule: an argv value wins without
reading stdin; otherwise non-terminal stdin is read through EOF. `COMMAND --`
with no following operand selects stdin. At most one final CRLF, LF, or bare CR
is consumed as producer framing. Every remaining line boundary is message data
and is preserved through workflow-command encoding; no lossy line mode is
offered.

Input is strict UTF-8 and NUL is rejected before stdout begins. The raw message
retains the standard 1 MiB acquisition limit. After producer framing, an empty
or Unicode-whitespace-only message is rejected because the pinned runner does
not convert it to an uploaded annotation. Here and below, Unicode whitespace
means the .NET 8 `Char.IsWhiteSpace` set, equivalent for accepted UTF-8 input to
the Unicode `White_Space` property.

The semantic message is limited to 4,096 UTF-16 code units, matching the pinned
runner's `ExecutionContext.AddIssue` limit. This prevents ordinary input from
being silently truncated after successful decoding. It cannot guarantee the
final annotation or log message remains byte- or character-identical: the
runner applies secret masking before its length check, and replacement with
`***` can expand the message beyond the limit and cause truncation.

### Metadata

TITLE and FILE are optional strict UTF-8 text fields. An explicitly supplied
empty value is an input error because the workflow-command parser would omit
an empty property. A leading `=` is rejected because the runner's
empty-entry-removing split would discard it or the complete property. NUL is
rejected. A final Unicode-whitespace scalar is also rejected for both fields.
The runner trims the complete encoded property region before splitting it, so
accepting such a suffix would make preservation depend on whether another
property follows it. CR and LF remain accepted because they are escaped before
this runner trim. Other whitespace and non-leading equals signs are preserved.
Each field is limited to 1 MiB before encoding.

FILE is annotation metadata, not path authorization or an existence check.
The runner may translate a container path to a host path and an absolute
workspace path to repository-relative form. Its relative-path helper also
normalizes platform directory separators before deciding whether a path is
inside the workspace, so destination metadata may differ even for a path that
remains absolute. shoutx does not normalize, resolve, open, or require the path
to exist, and does not promise the resulting UI file association.

Line and column values are unsigned ASCII decimal integers in the range 1
through 2,147,483,647 and are canonicalized on output. This is the conservative
intersection of GitHub's documented one-based positions and the pinned
runner's signed 32-bit parser. Leading zeroes are accepted as input and removed
in output. Signs, whitespace, non-ASCII digits, and other syntax are rejected.

shoutx rejects combinations the runner would otherwise repair or discard:

- `--end-line` requires `--line` and must not be smaller;
- `--column` and `--end-column` require `--line`;
- `--end-column` requires `--column` and must not be smaller; and
- columns are permitted only when `--end-line` is absent or equals `--line`.

Omitting every location field is valid. Metadata validation establishes a
self-consistent request; it does not verify that the named file contains the
specified location.

### Encoding and process behavior

The successful line is:

```text
::SEVERITY OPTIONAL_PROPERTIES::ENCODED_MESSAGE LF
```

When properties are present, one ASCII space separates SEVERITY from the first
property. Properties are emitted in the fixed order `title`, `file`, `line`,
`endLine`, `col`, `endColumn`, separated by commas, with absent fields omitted.
With no properties there is no space before the second `::`.

Message data replaces `%`, CR, and LF with `%25`, `%0D`, and `%0A`.
TITLE and FILE additionally replace `:` and `,` with `%3A` and `%2C`.
Percent is replaced first so literal escape-looking data remains literal after
runner decoding. No physical CR or LF occurs before the final LF, and encoded
property data cannot terminate the command or add another property. An equals
sign that is not first is data inside a property value because the runner
splits each property at only its first effective equals delimiter.

The complete encoded length is calculated with checked arithmetic before
allocation. All parsing, validation, size checks, encoding, and record
construction finish before stdout writing begins. The shared stdout, stderr,
exit-status, SIGPIPE, and partial-I/O contract applies. Successful output is
intended for direct runner consumption and must not be redirected to an
environment file.

The structural guarantee is faithful workflow-command decoding of one accepted
message and the supplied validated metadata as one selected annotation command
while workflow-command processing is active. It does not authorize the
annotation's content, file association, or severity, and it does not guarantee
provider retention or presentation.

## Boundary-specific threat analysis

Untrusted MESSAGE, TITLE, or FILE data cannot terminate the physical command
line, add a property, change severity, or create a second runner command.
Severity is selected by the command name; there is no raw command name or
arbitrary-property input.

Attacker-controlled content can still mislead readers, associate a diagnostic
with an unrelated file, create alert fatigue, or consume provider limits. The
caller must authorize what may be reported and at which severity.
`github-actions:error` creates an error issue but, unlike toolkit `setFailed`,
does not itself fail the process or step.

The pinned runner keeps at most ten timeline issues per severity per step,
although it continues to write later messages to the log. shoutx emits one
issue and cannot inspect or reserve remaining capacity. The runner also masks
registered secrets before logging and retaining the message. Masking is
best-effort, can change length and content, and is not part of the annotation
writer's structural guarantee.

An issue created in an embedded composite-action context is logged but is not
retained directly on that context. A server-controlled runner feature may
forward embedded issues to the parent step. shoutx cannot observe that feature
state and therefore does not guarantee annotation retention for a composite
action invocation.

When workflow-command processing is suspended with `stop-commands`, the
annotation is not created and the encoded command can appear as ordinary log
text. shoutx cannot observe that state. Issue command extensions set
`OmitEcho`, so workflow-command echoing does not separately echo the raw
command, but the decoded, masked issue message is intentionally logged.

The pinned runner rejects `notice` as a command when its server-provided
`DistributedTask.EnhancedAnnotations` feature flag is disabled; the encoded
line is then handled as ordinary log output and can be examined by problem
matchers. Warning and error remain processed, while the runner reports that
title, end-line, and end-column metadata are unsupported without enhanced
annotations. Hosted GitHub Actions currently documents all three commands, but
shoutx does not promise annotation creation or metadata presentation on a
server or runner where the required feature is disabled.

## Command-specific verification

### Grammar and input

For each severity, test `COMMAND MESSAGE`, `COMMAND -- MESSAGE`, stdin when
MESSAGE is omitted, and `COMMAND --` selecting stdin. Accept every metadata
option once with a separate operand in arbitrary option order. Reject duplicate
options, missing option operands, `--option=value`, unknown options, line-mode
options, and extra message operands as usage errors with status 2 and empty
stdout. Help and version are recognized only where an option can begin, not as
option operands or after MESSAGE.

Apply the shared argv/stdin precedence, terminal, closed-handle, strict UTF-8,
NUL, and 1 MiB acquisition cases. Exercise every final-boundary form through
both message sources, plus multiple terminators and internal mixed boundaries.
Reject empty and Unicode-whitespace-only semantic messages with status 1 and
empty stdout.

Count the semantic message as UTF-16 code units. Accept 4,096 ASCII or BMP
units and 2,048 supplementary Unicode scalars. Reject the first unit beyond
each applicable boundary, including a supplementary scalar that would cross
the limit. The raw 1 MiB limit is checked before final-boundary consumption and
before the smaller semantic limit.

TITLE and FILE retain the 1 MiB raw limit and do not consume a final line
boundary: CR and LF are preserved property data and encoded. Exercise `%`, CR,
LF, `:`, `,`, spaces, `::`, leading dashes, path separators, Unicode, and
literal escape-looking sequences. Test leading `=`, `=x`, and `==x` rejection,
and preservation of internal `a=b` and `a==b`, for both fields. Test empty
TITLE and FILE plus
trailing-Unicode-whitespace rejection for both fields. Confirm that encoded
trailing CR and LF are preserved. The writer does not inspect the filesystem.
Invalid UTF-8 in any of the six option operands, including a Windows unpaired
surrogate, is an input failure with status 1 and empty stdout rather than a
usage error.

### Location validation

Accept decimal `1` and `2147483647` for every numeric option. Reject zero,
negative and positive signs, surrounding whitespace, non-decimal syntax,
non-ASCII digits, and `2147483648` with status 1 and empty stdout. Verify that
accepted leading zeroes are emitted canonically.

Test every dependency and ordering rule: end line without line, either column
without line, end column without column, decreasing line or column ranges, and
columns paired with differing start and end lines all fail before stdout.
Accept a single point, a same-line column range, and a multiline range without
columns. The runner oracle must prove that `ValidateLinesAndColumns` neither
removes nor changes any supplied field for an accepted combination. Defaults
added later during uploaded-annotation conversion are characterized separately.
Include a same-line column range whose line operands use different leading-zero
spellings, and prove canonical output prevents the runner's string comparison
from discarding its columns.

### Encoding and runner behavior

For all severities, verify exact LF-terminated stdout and empty stderr.
Properties use the fixed order regardless of CLI order. Test both encoders'
complete escape sets and literal escape-looking inputs. Feed the complete line
to the pinned runner parser and assert one recognized command with the selected
fixed severity, exact decoded message, and exact decoded properties. Assert
there is no physical CR or LF before the final LF, embedded `::` does not end
data, commas cannot add metadata, and non-leading equals signs remain property
data. Include U+200B, U+00AD, and U+FEFF at the end of the final property and
the start of the message to exercise the runner's culture-sensitive separator
search around default-ignorable characters.

Use the actual pinned `WarningCommandExtension`, `ErrorCommandExtension`, and
`NoticeCommandExtension` with `ExecutionContext.AddIssue`. Verify issue type,
message, category, property data, workspace-relative and container-path
translation, separator rewriting for a non-workspace Windows path containing
both slash forms, secret masking, log tag, `OmitEcho`, and the fact that an
error annotation alone does not change shoutx's exit status.

Characterize the 4,096-UTF-16-unit truncation both without masking and with a
short registered secret whose replacement expands the message. Characterize
the limit of ten retained timeline issues per severity and continued logging
beyond that limit. Exercise an embedded composite-action context both with and
without the server-controlled embedded-issue forwarding feature, and
characterize whether an issue is retained by the parent step. Feed
whitespace-only commands directly to the runner and prove they produce a log
issue but no uploaded annotation. Exercise enhanced annotations both enabled
and disabled, including notice rejection as a command and ordinary encoded-line
logging when disabled. Drive the actual issue-to-annotation conversion used
during step completion rather than testing only `AddIssue` or a detached
conversion helper.

Suspend workflow-command processing and prove all three encoded commands are
treated as ordinary output and create no issue. Resume and prove normal
processing. Hosted Linux, macOS, and Windows checks emit all three severities
with delimiter-heavy multiline and non-ASCII message, title, and file data,
then inspect the completed run through the GitHub API for exact decoded text in
annotations and logs. POSIX shells and Git Bash additionally capture the native
LF-terminated bytes. PowerShell is an unredirected stdout path: it decodes
native output and writes text plus a host newline before the runner consumes
it. The supported PowerShell Core 7.4+ path relies on its UTF-8 default, and the
hosted test proves non-ASCII semantic round trips through the runner `pwsh`
template rather than byte-identical forwarding. Legacy Windows PowerShell,
older PowerShell Core, and a caller-modified non-UTF-8 native-output encoding
are outside this guarantee. Provider UI presentation is characterized rather
than promised as a stable format.

### Implementation constraints

Implement the three commands as one typed family. Keep severity as an enum
rather than a runtime command string and metadata as named fields rather than
an arbitrary property map. TITLE and FILE use bounded option-value conversion
without producer-framing removal. Numeric metadata is parsed into positive
`i32` values before dependency validation.

Message and property encoding may share checked replacement machinery, but
neither becomes a public generic encoder. Keep this stdout workflow-command
path separate from named environment-file framing. Construct the complete
immutable line before opening stdout.

Extend the pinned C# oracle rather than relying only on a local parser model.
The oracle must distinguish parser fidelity from runner policy: location
repair, message truncation, timeline capacity, path translation, feature-flag
handling, embedded-context forwarding, secret masking, and stopped-command
state are destination behavior.

Do not expose the commands in help or README until all three severities pass
the shared contract suite, pinned-runner oracle, and hosted workflow checks.
The family ships together.

## References

- [GitHub workflow annotation commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-a-notice-message)
- [Pinned runner workflow-command parser](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Common/ActionCommand.cs)
- [Pinned runner issue command extensions](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs)
- [Pinned runner issue retention and message limit](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ExecutionContext.cs)
- [Pinned runner annotation conversion](https://github.com/actions/runner/blob/v2.337.0/src/Sdk/RSWebApi/Contracts/IssueExtensions.cs)
- [.NET culture-sensitive string comparison guidance](https://learn.microsoft.com/en-us/dotnet/core/extensions/performing-culture-insensitive-string-operations)
- [PowerShell character encoding](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
