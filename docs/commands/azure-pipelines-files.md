# Azure summary and log-file writers

Status: implementation contract, unreleased. The [decision](../decisions/azure-files.md)
owns rationale, and the Azure compatibility record owns provider observations.

## Interface

```text
shoutx azure-pipelines:summary [PATH]
shoutx azure-pipelines:uploadfile [PATH]
```

Each accepts one optional path operand or bounded non-terminal stdin. Explicit
operands (including empty) ignore stdin. Only shared help/version and `--` are
options; extra operands and unknown options exit 2. Malformed first operands
exit 1 before unknown-option classification, like Azure PATH. Terminal stdin
without an operand exits 2. No upload-name, attachment-type or raw option exists.

## Input and output

Input is nonempty strict UTF-8 without NUL, at most 1 MiB. Reject CR and LF
anywhere, including a final producer newline; use `printf '%s'` instead of echo.
Paths use the native executable's OS syntax, with no environment override.
POSIX paths begin with `/` and have a nonempty final component other than `.` or
`..`. Windows accepts drive-absolute or ordinary UNC paths using either slash,
with a file component after the share for UNC and a nonempty final component
other than `.` or `..`; device/verbatim paths
are excluded. Windows rejects ASCII controls U+0000–U+001F, `"`, `<`, `>`, `|`,
`?`, `*`, and `:` except the drive prefix. Colon on POSIX and semicolon on either
OS are data, not PATH-list separators. No trimming, Unicode normalization,
case folding, extension check, existence check or symlink resolution occurs.
Other accepted characters, including spaces, percent escapes and multilingual
text, remain unchanged command data. This syntax does not establish existence,
regular-file identity, accessibility or portability across filesystems.

Emit one fixed header, encoded PATH and LF with no properties:

```text
##vso[task.uploadsummary]PATH
##vso[task.uploadfile]PATH
```

Use the existing [Azure escaping table](azure-pipelines.md#wire-contract).
Validate and construct the entire record before stdout, with an 8 MiB encoded
limit. Validation order: acquisition limit, UTF-8, NUL, nonempty, line breaks,
native syntax, checked record size. Validation failures return 1, empty stdout
and fixed value-free diagnostics. Shared I/O errors apply; a partial write
cannot be rolled back and success does not acknowledge asynchronous upload.

## Responsibility boundary

The attacker may influence a path supplied as data; the caller chooses and
authorizes the operation and resource. Shoutx protects the selected command,
empty property map, one physical record and unchanged decoded path. It does
not authorize a path, constrain it to a directory, inspect/read/hash/upload a
file, prevent symlink or replacement races, redact content or sanitize Markdown.
The caller owns publication permission, path resolution and file identity until
Azure consumes the file. An attacker-selected valid absolute path is still
unsafe when the caller has not authorized that resource.

Azure reads and uploads the file, derives the attachment name from the basename,
and owns collisions, retention, permissions and rendering. Summary requests
attach a Markdown report; uploadfile requests attach a file to task logs.
Their destinations are different. Callers supply UTF-8/ASCII Markdown for
summaries and must not assume registered log masks redact uploaded bytes.
Neither command replays the file as stdout commands. Avoid secrets in both
paths and contents. A literal protocol marker in an authorized file is content,
not an instruction to shoutx.

Reuse the native Ubuntu/Bash and Windows/PowerShell Azure profile and its
percent-decoding prerequisite. Containers, cross-OS path translation and
third-party viewers are outside this increment. No pixel-identical rendering,
undocumented UI behavior or universal accepted-filename portability is promised.

## Finite verification and endpoint

- Producer tests: exact bytes, both stdin/argv, literal escapes and delimiters,
  native absolute paths, Unicode, spaces, POSIX colon/Windows semicolon,
  empty/relative/invalid paths, CR/LF/NUL/invalid UTF-8, limits, option grammar,
  fixed diagnostics and empty stdout on pre-write failure. Test both path
  dialects without claiming a runtime cross-target interface. A nonexistent
  syntactically valid path must be encoded without filesystem access.
- Reuse the pinned actual Agent parser for fixed area/event, empty properties,
  exact decoded data and one record, including negative controls. Inspect only
  the selected handlers and attachment routing needed to interpret the effect.
- Two native hosted jobs, Ubuntu 24.04/Bash and Windows 2025/PowerShell, each
  at most 15 minutes, use synthetic caller-owned files with unique names and
  bounded content. Exercise ASCII, multilingual/combining text, spaces and
  literal escape/delimiter filenames. Include command-looking text only in
  uploaded synthetic contents or captured offline rejected output, never as a
  live injected command. Check exact attachment type/name/content via the
  supported API after the producer completes cleanly, and an unchanged sentinel.
  Bind run/source/job/attempt/Agent/image/binary identity. Missing, altered,
  additional or wrong-type attachments and wrong identity must fail verification.
- Inspect one summary display and a task-log file download route on the Azure
  web view. Record the actual behavior; unspecified display details do not add
  gates beyond the documented destination and intact content. Provider content
  handling is not a general Markdown/security audit.
- Independent review and final-head CI/Codex convergence yield a merge-ready PR.
  No merge, release or tag is included. A concrete framing/fidelity failure gets
  scoped correction; new sensitive attack details follow SECURITY.md.
