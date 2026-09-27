# shoutx

Prevent injection at CI workflow output boundaries.

`shoutx` safely writes untrusted values from shell-driven workflows to
destination-specific formats and protocols. The first release targets GitHub
Actions environment files. Generic context encoders are deferred until a
concrete destination and safe consumption contract justify one.

Status: early implementation. The `github-actions:output`,
`github-actions:env`, `github-actions:path`, `github-actions:state`, and
`github-actions:mask` commands are implemented. Native binaries, checksums, and provenance are available from
the [GitHub releases](https://github.com/send/shoutx/releases).

`github-actions:mask` is present on `main` but is not eligible for the next
binary release until its completed hosted-runner logs have passed the external
redaction check specified in the test plan.

The native-binary packaging and publication contract is specified in the
[release design](docs/release.md).

## Installation

Download the archive for your platform and `SHA256SUMS` from the
[latest GitHub release](https://github.com/send/shoutx/releases/latest). Verify
the archive before extracting it, then place `shoutx` (`shoutx.exe` on Windows)
on `PATH`. The [release verification guide](docs/release.md#verifying-a-published-release)
documents checksum and GitHub artifact-attestation verification.

GitHub Releases is currently the only binary distribution channel; `shoutx`
has not been published to crates.io or a package manager. Automation should pin
an exact release and expected archive digest rather than execute a mutable
`latest` download.

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
  run: |
    shoutx github-actions:output title "$PR_TITLE" >> "$GITHUB_OUTPUT"
    shoutx github-actions:env REPORT_URL "$REPORT_URL" >> "$GITHUB_ENV"
```

Do not interpolate untrusted `${{ ... }}` expressions directly into `run:`.
GitHub expands them before the generated shell script executes, so injection can
happen before `shoutx` starts. Detecting that workflow pattern is a linter's
responsibility; `shoutx` protects values that reach it as data.

When the value argument is omitted, `shoutx` reads standard input:

```sh
generate-title | shoutx github-actions:output title >> "$GITHUB_OUTPUT"
```

Default single-line mode accepts a normal one-line producer by consuming one
optional final CRLF, LF, or bare CR as input framing. Any remaining line break
is rejected:

```console
$ printf 'hello\nworld\n' | shoutx github-actions:output title
error: value contains CR or LF
```

Changing the value requires an explicit normalization mode:

```sh
generate-title | shoutx github-actions:output --first-line title >> "$GITHUB_OUTPUT"
generate-summary | shoutx github-actions:output --join-lines summary >> "$GITHUB_OUTPUT"
generate-list | shoutx github-actions:output --join-lines-with ', ' items >> "$GITHUB_OUTPUT"
generate-notes | shoutx github-actions:output --multiline notes >> "$GITHUB_OUTPUT"
```

## Commands

```text
GitHub Actions writers:
  shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
  shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
  shoutx github-actions:state  [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]
  shoutx github-actions:path   [VALUE]
  shoutx github-actions:mask   [VALUE]

```

| Command | Produces | Line-break behavior |
| --- | --- | --- |
| `github-actions:output` | One `$GITHUB_OUTPUT` record | Internal boundaries rejected by default; explicit normalization |
| `github-actions:env` | One `$GITHUB_ENV` record | Internal boundaries rejected by default; explicit normalization |
| `github-actions:path` | One `$GITHUB_PATH` record | One final boundary consumed; others rejected |
| `github-actions:state` | One `$GITHUB_STATE` record | Internal boundaries rejected by default; explicit normalization |
| `github-actions:mask` | One stdout `add-mask` command | One final boundary consumed; remaining boundaries percent-escaped |

Namespaced commands identify the interpretation context, not merely a data
type. Provider-specific writers use the `PROVIDER:DESTINATION` form. Reusable
encoders use the `LANGUAGE:CONTEXT` form.

## GitHub Actions writers

`github-actions:output` writes a named value using the `$GITHUB_OUTPUT`
environment-file protocol.

`github-actions:env` writes a named value using the `$GITHUB_ENV`
environment-file protocol.

`github-actions:state` writes one
named value to `$GITHUB_STATE` for exposure to another phase of the same action.
Its value and line-mode contract is identical to the output and environment
writers. State names match `[A-Za-z_][A-Za-z0-9_]*`; unlike environment names,
they have no reserved-name block because the runner exposes them with a
`STATE_` prefix. The command is useful only when the producer has a later phase
of the same action that consumes the state.

The implemented named writers validate the record name and reject NUL. Output
names match `[A-Za-z_][A-Za-z0-9_-]*`; environment names match
`[A-Za-z_][A-Za-z0-9_]*`. The environment writer also rejects `GITHUB_*`,
`RUNNER_*`, and `NODE_OPTIONS`, using ASCII case-insensitive comparisons.

All modes except `--multiline` first consume at most one final CRLF, LF, or bare
CR as input framing. Default mode then rejects any remaining CR or LF.
`--first-line` keeps the prefix before the first remaining boundary.
`--join-lines` replaces each remaining boundary with one ASCII space;
`--join-lines-with STRING` uses an explicit separator, which may be empty but
may not contain NUL, CR, or LF. `--multiline` preserves the complete value using
an independently generated, collision-checked delimiter.

`github-actions:path` validates and emits one fully
qualified entry for `$GITHUB_PATH`. Its target dialect follows `RUNNER_OS`,
with native fallback; a present unknown value is always rejected. It
consumes one optional final line boundary, rejects remaining boundaries and
empty values, rejects the target OS PATH separator (`:` on POSIX or `;` on
Windows), and preserves the path without normalization. It also rejects `"` on
every target and a trailing `\` on POSIX, which the runner cannot safely compose
into its container-runtime PATH argument. A leading U+FEFF will be rejected
because the runner would treat it differently at the beginning of the file.

The command provides record framing, not path authorization. An
attacker-controlled directory could still hijack later command lookup.

`github-actions:mask` registers one value with the runner's job-local secret
masker. Its successful stdout must go directly to the runner, not to an
environment file:

```sh
printf %s "$GENERATED_SECRET" | shoutx github-actions:mask
```

It consumes one optional final input boundary and percent-escapes `%`, CR, and
LF into one physical workflow-command line. Empty and Unicode-whitespace-only
values are rejected because the runner would not register them. Masking affects
only subsequent runner output and is best-effort: shell tracing or earlier
output can disclose the value, transformed forms are not universally covered,
short values can over-mask logs, and an active `stop-commands` region causes the
runner to ignore the command. Prefer stdin or a quoted environment variable to
a literal process argument. A masked value may be suppressed if used as a job
output, even though same-job step-output use is supported by GitHub.

The commands write encoded records to stdout. The caller deliberately chooses
the destination file with shell redirection; `shoutx` does not discover or
modify environment files implicitly. Redirect writer output to the intended
environment file; unredirected multiline value lines could otherwise be
interpreted as stdout workflow commands by the runner.

## Context encoders

No context encoder is currently planned for v1.0. The former `shell:arg`
candidate was deferred because shell quoting emitted at runtime cannot be
consumed as syntax through command substitution. It is useful only while
generating source for a later shell parse, where a single-word encoder cannot
enforce safe composition. Prefer an argv-capable API, or use `env:` and
`"$VALUE"` in GitHub Actions. See the
[design decision](docs/decisions/shell-arg.md).

## Input and output contract

- Options precede `NAME`. After `NAME`, one token is `VALUE` even if it begins
  with `-`.
- `--` ends option parsing. Modes are mutually exclusive, extra operands are
  usage errors, and `--join-lines-with=STRING` is accepted.
- For a command without `NAME`, including `github-actions:path` and
  `github-actions:mask`, use `--`
  before a value that could begin with `-`.
- `--help` and `--version` are options only before `NAME`; after `NAME`, those
  tokens are values.
- If `VALUE` is present, it is the input value and stdin is not read.
- If `VALUE` is omitted and stdin is not a terminal, stdin is read through EOF
  unless the first byte beyond the hard limit proves it must be rejected.
- If `VALUE` is omitted and stdin is a terminal, the command exits with usage
  status 2 instead of waiting. An unreadable stdin reported by the host API is
  an I/O failure with status 1. On POSIX, the Rust runtime replaces a descriptor
  that was already closed at process startup with `/dev/null`, so that case is
  indistinguishable from intentional empty stdin and produces an empty value.
- An empty `VALUE` and empty non-terminal stdin both mean an empty value.
- GitHub Actions `run:` steps normally provide non-terminal stdin, so omitting
  `VALUE` can successfully write an empty record when stdin is empty.
- The `github-actions:path` writer rejects that empty value because an
  empty line is not a path entry in the runner protocol.
- `github-actions:mask` also rejects empty and Unicode-whitespace-only values
  because the runner would not install those masks.
- Encoded output is written to stdout; diagnostics are written to stderr.
- Values are limited to 1 MiB of UTF-8 before and after normalization. Names
  and `--join-lines-with` separators are limited to 255 bytes.
- Input is strict UTF-8 and output is UTF-8 without a byte-order mark. Framing
  bytes are emitted explicitly for the local supported runner parser and do
  not rely on host text-mode newline conversion.
- Named-writer single-line records use explicit LF framing on every OS.
  Named-writer multiline records
  normally do the same. For a value ending in bare CR, `RUNNER_OS=Windows`
  selects CRLF framing so the Windows runner preserves that CR. If `RUNNER_OS`
  is absent, the native OS is used; an unrecognized value is rejected only when
  this framing distinction matters.
- Supported redirection must preserve native stdout bytes. CI verifies both
  the `sh` command and an explicit Dash invocation on Linux, `sh` and Bash on
  macOS, and PowerShell Core 7.4+ plus Git Bash on Windows. These shell tests
  run alongside differential tests against the pinned GitHub Actions runner
  v2.337.0 parser. Windows PowerShell 5.1, older PowerShell Core versions,
  text-writing cmdlets, and merged stderr/stdout redirection are unsupported.
- A non-zero `shoutx` status must also be propagated by the workflow shell.
  PowerShell callers must enable native-command error propagation or check
  `$LASTEXITCODE` immediately after each invocation.
- Success emits exactly one value or record and exits with status 0.
- Invalid input emits no partial record and exits with status 1. Command-line
  usage errors exit with status 2.
- An I/O failure exits with status 1 and may leave a partial record if output
  already began.
- On POSIX, a stdout descriptor already closed at process startup is replaced
  with `/dev/null` by the Rust runtime; no write failure is exposed, so output
  is discarded and status 0 is possible. Supported writer usage always
  redirects stdout to the runner file and does not rely on detecting this case.
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
an explicit `--first-line`, `--join-lines`, or `--join-lines-with` mode. Use
`--multiline` for exact value preservation.

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
source, that later shell boundary still requires a safe structured API;
`shoutx` does not currently provide one.

Values may also require application-level validation. A safely encoded path can
still identify an attacker-controlled directory and hijack command lookup. A
safely quoted argument can still be interpreted as a command option.

See [the threat model](docs/threat-model.md) for trust assumptions, attack
coverage, and required failure behavior. The
[design index](docs/design.md) links the destination-specific specifications;
the [CLI contract test plan](docs/test-plan.md) defines their shared cases and
compatibility gates.

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

## Development

Rust development uses Rust 1.98.1, pinned by `rust-toolchain.toml`; normal
builds and tests require only Cargo. The minimum supported Rust version (MSRV)
is separately declared as 1.85 in `Cargo.toml` and continuously tested in CI.
The development pin may advance without changing that compatibility promise;
raising the MSRV requires a deliberate release decision and matching manifest
and CI changes.

The pinned `actions/runner` differential suite additionally needs .NET SDK
8.0.424. `mise.toml` can install that SDK for local development, but mise is
optional:

```sh
mise install
scripts/test-runner-oracle.sh
```

CI installs the same SDK directly and runs the oracle natively on Linux and
Windows.

Dependency policy is declared in `deny.toml`. Contributors with `cargo-deny`
installed can run the same vulnerability, license, duplicate-version, and
source checks as CI with:

```sh
cargo deny --all-features --locked check advisories bans licenses sources
```

## Security

Report suspected vulnerabilities through GitHub's private vulnerability
reporting form rather than a public issue. See the [security policy](SECURITY.md)
for the supported-version policy and the information to include.

## License

MIT
