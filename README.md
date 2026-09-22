# shoutx

Prevent injection at CI workflow output boundaries.

`shoutx` safely writes untrusted values from shell-driven workflows to
destination-specific formats and protocols. The first release targets GitHub
Actions environment files, with small reusable encoders for downstream shell
and Markdown contexts.

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

Replace hand-built records with an explicit destination:

```sh
shoutx github-actions:output title "$PR_TITLE" >> "$GITHUB_OUTPUT"
shoutx github-actions:env REPORT_URL "$REPORT_URL" >> "$GITHUB_ENV"
shoutx github-actions:path "$TOOL_DIR" >> "$GITHUB_PATH"
```

When the value argument is omitted, `shoutx` reads standard input:

```sh
generate-title | shoutx github-actions:output title >> "$GITHUB_OUTPUT"
generate-report | shoutx github-actions:output --multiline report >> "$GITHUB_OUTPUT"
```

Single-line records reject line breaks by default:

```console
$ printf 'hello\nworld\n' | shoutx github-actions:output title
error: value contains a line break; use --first-line, --join-lines, or --multiline
```

Changing the value requires an explicit normalization mode:

```sh
generate-title | shoutx github-actions:output --first-line title >> "$GITHUB_OUTPUT"
generate-summary | shoutx github-actions:output --join-lines ' ' summary >> "$GITHUB_OUTPUT"
```

`--multiline` preserves line breaks and emits a valid multiline record. It is
not a raw mode.

## Commands

```text
GitHub Actions writers:
  shoutx github-actions:output [--first-line | --join-lines STRING | --multiline] NAME [VALUE]
  shoutx github-actions:env    [--first-line | --join-lines STRING | --multiline] NAME [VALUE]
  shoutx github-actions:path   [VALUE]

Context encoders:
  shoutx shell:arg             [VALUE]
  shoutx markdown:text         [VALUE]
```

| Command | Produces | Line-break behavior |
| --- | --- | --- |
| `github-actions:output` | One `$GITHUB_OUTPUT` record | Rejected by default; explicit normalization or `--multiline` |
| `github-actions:env` | One `$GITHUB_ENV` record | Rejected by default; explicit normalization or `--multiline` |
| `github-actions:path` | One `$GITHUB_PATH` record | Rejected |
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

Both commands validate the record name and reject NUL. They emit a single-line
record by default. In `--multiline` mode, `shoutx` chooses a collision-resistant
delimiter and verifies that it does not occur as a line in the value before
emitting the record.

`github-actions:path` validates and emits one entry for `$GITHUB_PATH`. It
rejects NUL, line breaks, and empty values. Platform-specific path rules belong
to this command rather than to the caller.

The commands write encoded records to stdout. The caller deliberately chooses
the destination file with shell redirection; `shoutx` does not discover or
modify environment files implicitly.

## Context encoders

`shell:arg` emits one POSIX shell word. It prevents shell-source injection when
the result is parsed exactly once as one word. It does not encode an entire
command line, make `eval` safe, prevent option injection, or repair an unsafe
command interface.

`markdown:text` emits Markdown that renders the input as plain text rather than
as Markdown syntax or embedded HTML. It is intended for values written to job
summaries, comments, and release notes. It does not sanitize arbitrary Markdown
or HTML documents.

## Input and output contract

- If `VALUE` is present, it is the input value.
- If `VALUE` is omitted and stdin is piped, stdin is read through EOF.
- If `VALUE` is omitted and stdin is a terminal, the command fails.
- Encoded output is written to stdout; diagnostics are written to stderr.
- Success emits exactly one value or record and exits with status 0.
- Invalid input emits no partial record and exits non-zero.
- NUL is always rejected.
- Raw passthrough is intentionally unsupported.

## Design principles

### Name the destination context

There is no universally safe string. A value safe as a shell word is not
necessarily safe as a GitHub Actions environment-file record. The command name
makes the next parser explicit.

### Preserve values by default

Escaping and framing should preserve the value whenever the destination can
represent it safely. `--first-line` and `--join-lines` are explicit because they
are lossy transformations. `--multiline` preserves the value.

### Fail closed and atomically

If a value cannot be represented under the selected contract, `shoutx` fails
without writing a partial result. It never silently falls back to raw output.

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
still identify an unintended directory, and a safely quoted argument can still
be interpreted as a command option.

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
