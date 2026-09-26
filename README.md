# shoutx

Prevent injection at CI workflow output boundaries.

`shoutx` safely writes untrusted values from shell-driven workflows to
destination-specific formats and protocols. The first release targets GitHub
Actions environment files. Small reusable encoders for downstream shell and
Markdown contexts are under consideration for v1.0.

Status: early design draft.

## The problem

CI workflows routinely move untrusted values across interpretation boundaries:
pull request titles become step outputs, tool results become environment
variables, and generated paths affect command lookup. These writes are often
assembled with string concatenation:

```sh
echo "title=$PR_TITLE" >> "$GITHUB_OUTPUT"
echo "REPORT_URL=$REPORT_URL" >> "$GITHUB_ENV"
echo "$TOOL_DIR" >> "$GITHUB_PATH"
```

A newline or other control value can change the destination record structure
instead of remaining data. Quoting the shell expansion does not protect the
format being written.

Security scanners can find some unsafe flows. `shoutx` provides the missing
runtime primitive: a destination-aware writer that workflows can use at the
boundary.

## Quick start

Pass expression values through `env:` so they reach the shell as data, then use
`shoutx` at the output boundary:

```yaml
- name: Export workflow values
  id: export
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
    REPORT_URL: ${{ steps.build.outputs.report-url }}
    TOOL_DIR: ${{ github.workspace }}/.tools/bin
  run: |
    shoutx github-actions:output title "$PR_TITLE" >> "$GITHUB_OUTPUT"
    shoutx github-actions:env REPORT_URL "$REPORT_URL" >> "$GITHUB_ENV"
    # PATH entries must name trusted directories.
    shoutx github-actions:path -- "$TOOL_DIR" >> "$GITHUB_PATH"
```

Do not interpolate untrusted `${{ ... }}` expressions directly into `run:`.
GitHub expands them before the generated shell script executes, so injection can
happen before `shoutx` starts. Detecting that workflow pattern is a linter's
responsibility; `shoutx` protects values that reach it as data.

When the value argument is omitted, `shoutx` reads standard input:

```sh
generate-title | shoutx github-actions:output title >> "$GITHUB_OUTPUT"
generate-report | shoutx github-actions:output --multiline report >> "$GITHUB_OUTPUT"
```

Default single-line mode accepts a normal one-line producer by consuming one
optional final CRLF, LF, or bare CR as input framing. Any remaining line break
is rejected:

```console
$ printf 'hello\nworld\n' | shoutx github-actions:output title
error: value contains CR or LF; use --first-line, --join-lines, --join-lines-with, or --multiline
```

Changing the value requires an explicit normalization mode:

```sh
generate-title | shoutx github-actions:output --first-line title >> "$GITHUB_OUTPUT"
generate-summary | shoutx github-actions:output --join-lines summary >> "$GITHUB_OUTPUT"
generate-list | shoutx github-actions:output --join-lines-with ', ' items >> "$GITHUB_OUTPUT"
```

`--multiline` preserves line breaks and emits a valid multiline record. It is
not a raw mode.

## Commands

```text
GitHub Actions writers:
  shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
  shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
  shoutx github-actions:path   [VALUE]

Context encoders under consideration for v1.0 (not yet specified):
  shoutx shell:arg             [VALUE]
  shoutx markdown:text         [VALUE]
```

| Command | Produces | Line-break behavior |
| --- | --- | --- |
| `github-actions:output` | One `$GITHUB_OUTPUT` record | Internal boundaries rejected by default; explicit normalization or `--multiline` |
| `github-actions:env` | One `$GITHUB_ENV` record | Internal boundaries rejected by default; explicit normalization or `--multiline` |
| `github-actions:path` | One `$GITHUB_PATH` record | One final boundary consumed; others rejected |
| `shell:arg` | One POSIX shell word | Preserved in the quoted word |
| `markdown:text` | Markdown that renders the value as text | Preserved |

Namespaced commands identify the interpretation context, not merely a data
type. Provider-specific writers use the `PROVIDER:DESTINATION` form. Reusable
encoders use the `LANGUAGE:CONTEXT` form.

## GitHub Actions writers

`github-actions:output` writes a named value using the `$GITHUB_OUTPUT`
environment-file protocol.

`github-actions:env` writes a named value using the `$GITHUB_ENV`
environment-file protocol.

Both commands validate the record name and reject NUL. Output names match
`[A-Za-z_][A-Za-z0-9_-]*`; environment names match
`[A-Za-z_][A-Za-z0-9_]*`. The environment writer also rejects `GITHUB_*`,
`RUNNER_*`, and `NODE_OPTIONS`, using ASCII case-insensitive comparisons.

All modes except `--multiline` first consume at most one final CRLF, LF, or bare
CR as input framing. Default mode then rejects any remaining CR or LF.
`--first-line` keeps the prefix before the first remaining boundary.
`--join-lines` replaces each remaining boundary with one ASCII space;
`--join-lines-with STRING` uses an explicit separator, which may be empty but
may not contain NUL, CR, or LF. In `--multiline` mode, `shoutx` chooses an
independently generated, collision-resistant delimiter and verifies that it
does not occur in the value before emitting the record.

`github-actions:path` validates and emits one entry for `$GITHUB_PATH`. It
consumes one optional final CRLF, LF, or bare CR as input framing, then rejects
NUL, any remaining line boundary, and empty values. Platform-specific path
rules belong to this command rather than to the caller. This command remains an
MVP candidate until those cross-platform rules and parser tests are complete.

This command prevents one value from becoming multiple `$GITHUB_PATH` records.
It cannot make an attacker-controlled directory safe to add to `PATH`: doing so
can still hijack later command lookup. Path trust and authorization remain the
caller's responsibility.

The commands write encoded records to stdout. The caller deliberately chooses
the destination file with shell redirection; `shoutx` does not discover or
modify environment files implicitly. Redirect writer output to the intended
environment file; unredirected multiline value lines could otherwise be
interpreted as stdout workflow commands by the runner.

## Context encoders

If included, `shell:arg` will emit one POSIX shell word. It would prevent
shell-source injection when the result is parsed exactly once as one word. It
does not encode an entire command line, make `eval` safe, prevent option
injection, or repair an unsafe command interface.

If included, `markdown:text` will emit Markdown that renders the input as plain
text rather than as Markdown syntax or embedded HTML. It is intended for values
written to job summaries, comments, and release notes. It does not sanitize
arbitrary Markdown or HTML documents.

## Input and output contract

- Options precede `NAME`. After `NAME`, one token is `VALUE` even if it begins
  with `-`.
- `--` ends option parsing. Modes are mutually exclusive, extra operands are
  usage errors, and `--join-lines-with=STRING` is accepted.
- For a command without `NAME`, including `github-actions:path`, use `--`
  before a value that could begin with `-`.
- `--help` and `--version` are options only before `NAME`; after `NAME`, those
  tokens are values.
- If `VALUE` is present, it is the input value and stdin is not read.
- If `VALUE` is omitted and stdin is not a terminal, stdin is read through EOF.
- If `VALUE` is omitted and stdin is a terminal, the command exits with usage
  status 2 instead of waiting. A closed stdin descriptor is an I/O failure with
  status 1, not an empty value.
- An empty `VALUE` and empty non-terminal stdin both mean an empty value.
- GitHub Actions `run:` steps normally provide non-terminal stdin, so omitting
  `VALUE` can successfully write an empty record when stdin is empty.
- Encoded output is written to stdout; diagnostics are written to stderr.
- Values are limited to 1 MiB of UTF-8 before and after normalization. Names
  and `--join-lines-with` separators are limited to 255 bytes.
- Input is strict UTF-8 and output is UTF-8 without a byte-order mark. Framing
  bytes are emitted explicitly for the local supported runner parser and do
  not rely on host text-mode newline conversion.
- The cross-platform guarantee is a semantic round trip through the local
  supported runner, not byte-identical output. When `RUNNER_OS=Windows`, CRLF
  framing is used where necessary to preserve a multiline value ending in bare
  CR. `RUNNER_OS=Linux` or `macOS` selects LF framing regardless of executable
  host; if `RUNNER_OS` is absent, the native process OS selects the convention.
- Supported redirection must preserve native stdout bytes. POSIX `sh`/`bash`
  redirection and PowerShell Core 7.4 or later direct redirection are intended
  targets, but PowerShell is not part of the release guarantee until
  differential tests pass. Older PowerShell versions, text-writing cmdlets, and
  merged stderr/stdout redirection are unsupported.
- A non-zero `shoutx` status must also be propagated by the workflow shell.
  PowerShell callers must enable native-command error propagation or check
  `$LASTEXITCODE` immediately after each invocation.
- Success emits exactly one value or record and exits with status 0.
- Invalid input emits no partial record and exits with status 1. Command-line
  usage errors exit with status 2.
- An I/O failure exits with status 1 and may leave a partial record if output
  already began.
- NUL is always rejected.
- Raw passthrough is intentionally unsupported.

## Design principles

### Name the destination context

There is no universally safe string. A value safe as a shell word is not
necessarily safe as a GitHub Actions environment-file record. The command name
makes the next parser explicit.

### Preserve values by default

Default single-line mode treats at most one final CRLF, LF, or bare CR as input
framing rather than value data. Other discarded or normalized content requires
an explicit `--first-line`, `--join-lines`, or `--join-lines-with` mode.
`--multiline` preserves the complete value.

### Validate before writing

If a value cannot be represented under the selected contract, `shoutx` fails
before beginning output. It never silently falls back to raw output. An I/O
failure after writing begins can still leave partial bytes in the destination;
stdout and shell redirection are not transactional.

### Keep provider behavior pluggable

CI systems expose different command channels and record protocols. Provider
namespaces keep those rules separate while sharing input handling, validation,
normalization, and encoder primitives.

## Security model

`shoutx` protects the boundary named by the selected command. It does not make
the value safe for every later use.

For example, `github-actions:output` prevents a value from injecting another
GitHub Actions output record. If a later step interpolates that value into shell
source, that later shell boundary still requires a safe API or `shell:arg`.

Values may also require application-level validation. A safely encoded path can
still identify an attacker-controlled directory and hijack command lookup. A
safely quoted argument can still be interpreted as a command option.

See [the threat model](docs/threat-model.md) for trust assumptions, attack
coverage, and required failure behavior. The
[CLI contract test plan](docs/test-plan.md) defines the cases and compatibility
gates that an implementation must satisfy.

## Non-goals

- Static analysis of complete workflows or attack-path discovery.
- Replacing actionlint, zizmor, CodeQL, or policy engines.
- A universal `escape` operation independent of destination context.
- Sanitizing arbitrary documents or command lines.
- Making `eval`, dynamic shell source, or unsafe command APIs safe.
- Raw output disguised as an encoding mode.

`shoutx` complements scanners and linters by giving them a concrete safe pattern
to recommend.

## Planned scope

The MVP supports GitHub Actions. Additional providers can add their own
destination writers without changing the core command model, for example:

```text
shoutx gitlab-ci:dotenv ...
shoutx azure-pipelines:variable ...
```

The exact plugin distribution and discovery mechanism is not yet specified.

## License

MIT
