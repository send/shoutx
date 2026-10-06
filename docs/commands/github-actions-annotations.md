# GitHub Actions annotation commands

This specification covers the implemented `github-actions:notice`,
`github-actions:warning`, and `github-actions:error` commands. Cross-cutting
product invariants remain in [`design.md`](../design.md), and shared testing
policy remains in [`test-plan.md`](../test-plan.md). The Contract section is
normative for these commands; contradictions with the cross-cutting documents
must be resolved.

The commands are included in the normal executable under the
[stdout adoption profile](../design.md#stdout-adoption-contract).
Previously published binaries are unchanged; publication follows the
[release policy](../release.md). External parser evidence is maintained in the
[workflow-command compatibility note](../compatibility/github-actions-workflow-command-parser.md).

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

The shared **Unicode data-boundary policy**, also used by mask, requires the
first semantic scalar to belong to the versioned range set in
`tests/unicode-policy-probe/start-candidate.json`. The executable embeds a
generated representation of that set, not a runtime-loaded file. Existing
U+0020--U+007E, CR and LF starts remain accepted. CR/LF become ASCII escapes.
No leading character is skipped, normalized or replaced. Later scalars remain
strict UTF-8 data subject to the other validation and size rules. A disallowed
start fails with status 1, empty stdout, and the fixed diagnostic
`annotation message is outside the Unicode boundary policy`.

The [integration evidence](../compatibility/stdout-unicode-policy.md) names the
characterized en-US/Invariant configurations and known contrary newer-runtime
observation. The policy does not guarantee arbitrary cultures or versions;
shoutx cannot detect the separate consumer's configuration. The `th-TH` failure
remains deferred.

The semantic message is limited to 4,096 UTF-16 code units, matching the pinned
runner's `ExecutionContext.AddIssue` limit. This prevents ordinary input from
being silently truncated after successful decoding. It cannot guarantee the
final annotation or log message remains byte- or character-identical: the
runner applies secret masking before its length check, and replacement with
`***` can expand the message beyond the limit and cause truncation.

### Metadata

TITLE and FILE are optional strict UTF-8 text fields. They do not use the
message-start table: every non-NUL scalar is data, subject to the structural
validation below and the separate property escaping rules. No padding,
normalization, stripping or replacement is performed.
An explicitly supplied empty value is an input error because the workflow-command parser would omit
an empty property. A leading `=` is rejected because the runner's
empty-entry-removing split would discard it or the complete property. NUL is
rejected. A final Unicode-whitespace scalar other than CR/LF is also rejected
for both fields, retaining the earlier trailing-whitespace diagnostic.
The runner trims the complete encoded property region before splitting it.
Retain the uniform trailing-whitespace restriction rather than making acceptance
depend on a following property or the Unicode-only structural terminator.
CR and LF remain accepted because they are escaped before this runner trim.
Internal spaces and non-leading equals signs are preserved.
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
If TITLE or FILE contains non-ASCII data, append one final comma to the property
region before `::`. This is a structural empty property entry, which the pinned
Runner discards, not part of either value. It separates Unicode property tails
from the V2 delimiter without changing decoded data. Previously accepted ASCII
headers keep their existing bytes. The trailing-whitespace rejection above is
retained uniformly; the extra delimiter does not introduce a normalization mode.
With no properties there is no space before the second `::`.

Message data replaces `%`, CR, and LF with `%25`, `%0D`, and `%0A`.
TITLE and FILE additionally replace `:` and `,` with `%3A` and `%2C`.
Percent is replaced first so literal escape-looking data remains literal after
runner decoding. No physical CR or LF occurs before the final LF, and encoded
property data cannot terminate the physical command line. When the intended V2
separator is recognized, it also cannot terminate command metadata or add
another property. An equals sign that is not first is data inside a property
value because the runner splits each property at only its first effective
equals delimiter.

The complete encoded length is calculated with checked arithmetic before
allocation. All parsing, validation, size checks, encoding, and record
construction finish before stdout writing begins. The shared stdout, stderr,
exit-status, SIGPIPE, and partial-I/O contract applies. Successful output is
intended for direct runner consumption and must not be redirected to an
environment file.

The intended structural guarantee is faithful workflow-command decoding of
one accepted message and the supplied validated metadata as one selected
annotation command while workflow-command processing is active, within the
[design-owned adoption profile](../design.md#stdout-adoption-contract). It
does not authorize content, file association, or severity, or promise provider
retention or presentation. Consumer configuration is not detected or enforced
by shoutx; known excluded-configuration failures remain documented, not fixed
by this scope choice.

## Boundary-specific threat analysis

The [stdout threat inventory](../threat-model.md#stdout-mask-and-annotation-responsibility)
owns attack paths AP1–AP3/AP5 and the distinction between injection and functional
failure. The encoding and typed-command controls are specified above. Broadening
the message or metadata domain requires assessing those controls for the changed
inputs; it does not require establishing every culture's parser behavior.
The following are command-specific effects and limitations, not additional
requirements to certify Runner internals.

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
empty stdout. Cover every ASCII first scalar and representative non-ASCII
prefixes for all severities and both input sources. Include cases with a later
`::` followed by property-looking data and a legacy-looking `##[warning]`
payload. Cover every ASCII scalar and representative non-ASCII scalars at the
start, middle, and end of TITLE and FILE. On rejection assert status 1,
empty stdout, and the exact value-free diagnostic. Run the accepted annotation
corpus under both Invariant Culture and `en-US` in the pinned runner oracle.

Count the semantic message as UTF-16 code units. Accept 4,096 ASCII or BMP
units (with an allowed first scalar), and two ASCII scalars followed by 2,047
supplementary Unicode scalars. Reject the first unit beyond
each applicable boundary, including a supplementary scalar that would cross
the limit. The raw 1 MiB limit is checked before final-boundary consumption and
before the smaller semantic limit.

TITLE and FILE retain the 1 MiB raw limit and do not consume a final line
boundary: CR and LF are preserved property data and encoded. Exercise `%`, CR,
LF, `:`, `,`, spaces, `::`, leading dashes, path separators, and
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
data. Preserve U+200B, U+00AD, and U+FEFF in TITLE/FILE, including alone and at
either field edge. Assert the final structural comma for Unicode metadata and
that it creates no additional decoded property. Cover final TITLE and final
FILE without numeric metadata, as well as properties followed by typed fields.
These scalars remain rejected at the message boundary by the data-start policy;
preserve them in the message after an allowed first scalar. Verify that ASCII
metadata does not acquire the Unicode-only terminator.

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
with delimiter-heavy multiline data, Unicode message starts and tails, and
Unicode TITLE/FILE data alongside the existing ASCII smoke cases,
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

Default help and the packaged README expose all three commands. The three
severities ship together, subject to the shared contract, oracle, hosted, and
release-admission gates.

## References

- [GitHub workflow annotation commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-a-notice-message)
- [Pinned runner workflow-command parser](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Common/ActionCommand.cs)
- [Pinned runner issue command extensions](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs)
- [Pinned runner issue retention and message limit](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ExecutionContext.cs)
- [Pinned runner annotation conversion](https://github.com/actions/runner/blob/v2.337.0/src/Sdk/RSWebApi/Contracts/IssueExtensions.cs)
- [.NET culture-sensitive string comparison guidance](https://learn.microsoft.com/en-us/dotnet/core/extensions/performing-culture-insensitive-string-operations)
- [PowerShell character encoding](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
