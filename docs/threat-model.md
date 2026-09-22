# Threat model

This document defines the security boundary that `shoutx` intends to protect.
It covers the proposed MVP and will evolve with the implementation.

Revision status: second design pass, before implementation.

## Security objective

Given an attacker-controlled value, `shoutx` either:

1. validates and emits one representation for the selected destination context;
   or
2. rejects the value before beginning output.

Parsing a successful representation with the supported destination parser must
produce exactly the requested name and value and no additional record.

The selected command names one interpretation boundary. Crossing that boundary
safely does not make the value safe for other parsers, establish that the value
is trusted, or authorize the operation represented by the value.

## System model

The normal GitHub Actions data flow is:

```text
untrusted source
    -> structured workflow data channel
    -> shell argument or stdin
    -> shoutx
    -> stdout
    -> shell redirection
    -> GitHub Actions environment file
    -> runner parser
    -> output, environment, or PATH state
    -> later consumer
```

`shoutx` controls its validation, encoding, diagnostics, and stdout writes. The
caller controls how values reach the process and where stdout is redirected.
The operating system controls process I/O. GitHub Actions controls the
environment-file parser and downstream runtime behavior.

GitHub creates a distinct environment-file path for each step. The runner reads
these files after processing the step. `$GITHUB_OUTPUT`, `$GITHUB_ENV`, and
`$GITHUB_PATH` are therefore protocols between the step and the runner, not
ordinary application data files.

## Assets

The model aims to protect:

- the structure and namespace of runner command-file records;
- subsequent step environment state;
- command lookup affected by `PATH`;
- the integrity of generated shell and Markdown contexts, if their encoders are
  included;
- secrets, tokens, and sensitive values from disclosure in diagnostics; and
- runner availability against unreasonable memory consumption by `shoutx`.

## Adversary

The attacker may control text obtained from, for example:

- pull request and issue titles, bodies, labels, and branch names;
- commit metadata;
- downloaded files, artifacts, caches, and command output;
- API responses and data produced by untrusted build inputs; and
- outputs from an earlier, less-trusted workflow or job.

The attacker attempts to make a value escape its intended record or context,
create additional records, alter later command lookup, inject shell source,
change rendered content, disclose secrets, or exhaust resources.

## Trust assumptions

The following are trusted within this model:

- the workflow definition and selected `shoutx` command;
- the installation and executable resolution of `shoutx`;
- the redirection target chosen by the caller;
- the GitHub Actions runner and operating system; and
- the supported destination parser version.

If an attacker can alter the workflow, replace `shoutx`, redirect output to a
different file, execute arbitrary code in the same job, or modify a self-hosted
runner, the attacker has crossed a stronger boundary than this tool protects.
Executing attacker-controlled checkouts, artifacts, dependencies, or build
scripts in a privileged job is therefore outside this model.

## Precondition: reach `shoutx` as data

An untrusted GitHub expression must not be interpolated directly into `run:`:

```yaml
# Unsafe: expression expansion happens before the shell parses the script.
- run: shoutx github-actions:output title "${{ github.event.pull_request.title }}" >> "$GITHUB_OUTPUT"
```

GitHub evaluates the expression while constructing a temporary shell script.
An attacker can therefore inject shell syntax before `shoutx` starts. Move the
value through an environment variable and quote the shell expansion:

```yaml
- env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: shoutx github-actions:output title "$PR_TITLE" >> "$GITHUB_OUTPUT"
```

Detecting unsafe expression interpolation is a static-analysis concern. A
destination encoder cannot repair injection that occurred before it received
the value.

## Data and encoding model

GitHub requires environment files to be written as UTF-8. The proposed CLI
contract is therefore:

- input values are valid UTF-8 text;
- invalid UTF-8 from stdin is rejected before output begins;
- NUL is rejected in every mode;
- emitted records are UTF-8 without a byte-order mark; and
- record framing emitted by `shoutx` uses LF, independent of the host OS.

Command-line arguments are subject to the host process API. Implementations
must reject arguments that cannot be represented as valid UTF-8 rather than
silently replacing data.

Single-line modes reject both CR and LF. The exact value semantics for CRLF,
bare CR, and trailing line breaks in multiline and normalization modes remain a
CLI design decision and must be resolved before those modes are implemented.

Shell redirection and shell-specific transcoding remain outside `shoutx`'s
control. Supported invocation environments must preserve native-process stdout
bytes unchanged. Legacy Windows PowerShell requires particular care because its
file-writing commands do not use UTF-8 by default.

## GitHub Actions boundary inventory

The MVP protects these environment-file destinations:

| Boundary | MVP status | Interpretation |
| --- | --- | --- |
| `$GITHUB_OUTPUT` | Included | Named step-output records |
| `$GITHUB_ENV` | Included | Named environment-variable records |
| `$GITHUB_PATH` | Included | One path entry per line |

Other recognized boundaries are explicitly deferred:

| Boundary | Status | Primary concern |
| --- | --- | --- |
| `$GITHUB_STATE` | Deferred | Named state records used by action `pre:`, `main:`, and `post:` phases |
| `$GITHUB_STEP_SUMMARY` | Deferred to `markdown:text` design | GitHub Flavored Markdown interpretation |
| stdout workflow commands | Deferred | Lines such as `::warning::`, `::add-mask::`, and `::stop-commands::` are runner control messages |
| `$GITHUB_ARTIFACTS` | Deferred | One file or OCI declaration per line |
| `$GITHUB_ARTIFACTS_LIST` | Out of scope | Runner-managed, read-only JSON input |

Inventorying a boundary does not commit `shoutx` to supporting it. It prevents
an unsupported control channel from being mistaken for a protected one.

## Protected boundaries

### `github-actions:output`

The security property is structural integrity of one `$GITHUB_OUTPUT` record.
An attacker-controlled value must not define another output name or terminate a
multiline record early.

Single-line mode rejects CR and LF. Multiline mode uses the documented
`NAME<<DELIMITER` framing and verifies that the selected delimiter does not
occur as a line of its own in the value. Framing must preserve empty values and
trailing line breaks according to the final CLI contract.

The command rejects invalid names according to a documented, conservative
grammar. This does not protect later use of the output. If a later `run:` block
inserts the output directly as an expression, shell injection is again possible.

GitHub applies separate limits to job and workflow outputs. Passing `shoutx`
validation does not guarantee that GitHub will accept or propagate the output.

### `github-actions:env`

The security property is structural integrity of one `$GITHUB_ENV` record. An
attacker-controlled value must not define another variable or terminate a
multiline record early.

The command uses a documented, portable name grammar and fails for names that
GitHub reserves or blocks. At minimum, policy must account for default
`GITHUB_*` and `RUNNER_*` variables, `NODE_OPTIONS`, case-insensitive collisions
on Windows, and duplicate assignments.

The command does not make later uses of the variable safe for shell, SQL, URLs,
templates, or other contexts. It also does not make environment variables an
appropriate channel for secrets.

### `github-actions:path`

The security property is limited to one `$GITHUB_PATH` record. The command
rejects NUL, CR, LF, and empty values so one input cannot add multiple entries.

There is no encoding that makes an attacker-controlled directory safe to add to
`PATH`. An attacker who controls a directory earlier in command lookup may place
a malicious executable there. The caller must separately establish that the
path is trusted and intended. `github-actions:path` is framing and validation,
not authorization.

The final CLI contract must define platform-specific absolute-path, separator,
and normalization rules without changing the path to a different directory.

### `shell:arg`

If included in v1.0, the security property is one shell word after exactly one
parse by a named shell dialect. It does not cover `eval`, nested parsing,
command options, executable selection, expansions performed before encoding, or
concatenation into a larger shell token without a documented composition rule.

The recommended GitHub Actions pattern remains a value passed through `env:` and
expanded as `"$VALUE"`. `shell:arg` is not a replacement for that data channel.

### `markdown:text`

If included in v1.0, the security property must be defined against GitHub
Flavored Markdown and a named renderer. Rendering attacker-controlled input as
text is different from sanitizing an existing Markdown or HTML document.

The design must separately consider links, autolinks, images, mentions, Unicode
control characters, bidirectional text, and embedded HTML. XSS protection
provided by the hosting renderer is outside `shoutx`'s control and must not be
claimed without an explicit platform contract.

## Attack and guarantee matrix

| Attack | In scope | Intended control |
| --- | --- | --- |
| New output or environment record through a line break | Yes | Reject CR/LF or use verified multiline framing |
| Early multiline termination | Yes | Verify the delimiter is not a standalone input line |
| Record-name confusion | Yes | Validate against a documented conservative grammar |
| Multiple PATH entries through a line break | Yes | Reject CR and LF |
| Invalid UTF-8 or NUL | Yes | Reject before output begins |
| Memory exhaustion through large input | Yes | Enforce a documented hard input limit |
| Secret exposure through diagnostics | Yes | Do not reproduce input values in diagnostics |
| Command hijacking through an attacker-controlled PATH directory | No | Caller validates trust and authorization |
| Shell injection before `shoutx` starts | No | Use a structured data channel and quoted expansion |
| Injection when a stored value is consumed later | No | Protect the later interpretation boundary |
| Option injection such as a value beginning with `-` | No | Use `--` or an API separating options from operands |
| Stdout workflow-command injection from another process | No | Avoid logging untrusted bytes or suspend command processing safely |
| Malicious behavior of executed code or artifacts | No | Do not execute untrusted code in privileged workflows |
| Concurrent environment-file modification | No | Requires process and runner isolation outside this tool |
| Redirection to an attacker-selected file or symlink | No | Caller owns and validates the destination |
| Secret disclosure in the successfully encoded value | No | Caller selects an appropriate data channel |

## Resource limits

`shoutx` must read and validate the complete input before beginning output, so
it requires a hard input-size limit. The exact limit is part of the CLI contract
and must be enforced for both argv and stdin.

Provider limits are separate. GitHub currently documents job outputs of at most
1 MB per job and 50 MB per workflow run, approximated using UTF-16 encoding.
Job summaries have a separate 1 MiB per-step limit. A local `shoutx` success
cannot guarantee that aggregate provider limits have not already been consumed.

Resource-limit diagnostics must not include the rejected value. Temporary files,
if an implementation uses them, must be private, created safely, and removed on
both success and failure.

## Failure and output behavior

Commands validate and encode the complete input before beginning stdout output.
Validation, encoding, and resource-limit failures therefore emit no encoded
bytes to stdout and exit non-zero.

Once writing begins, an operating-system or I/O failure can leave partial bytes
in stdout or the redirected destination. `shoutx` cannot promise transactional
stdout. It must report the failure through a non-zero exit status when the host
API exposes it.

Diagnostics go to stderr and identify the failed rule without reproducing
untrusted or secret values. Diagnostic text itself must not accidentally form a
GitHub stdout workflow command.

Shell redirection is outside the output guarantee. `>` may create or truncate a
destination before `shoutx` validates input. The documented GitHub Actions usage
appends to runner-created files with `>>`.

## Secrets

`shoutx` treats every input value as potentially sensitive:

- diagnostics do not include values or delimiter-derived excerpts;
- debug modes must not print raw input;
- generated delimiters must not be derived from secret input; and
- failures do not suggest retry commands containing the original value.

GitHub's log masking and summary masking are defense-in-depth and are not part
of the `shoutx` guarantee. Successfully writing a secret to an output,
environment variable, PATH entry, summary, or later command may still disclose
or misuse it.

## Concurrency and lifecycle

`shoutx` does not coordinate multiple processes writing to the same destination.
Background processes may outlive a step, and self-hosted runners may have weaker
isolation than GitHub-hosted runners. The caller must ensure exclusive,
in-lifecycle writes to the runner-provided file.

Plugin discovery, if added, creates another executable-resolution boundary. A
future plugin design must prevent untrusted working directories or `PATH`
entries from selecting a different provider implementation.

## Required tests

- LF and CRLF input, including a final line without a terminator;
- bare CR, NUL, invalid UTF-8, and a UTF-8 byte-order mark;
- empty values, empty first lines, and one or more trailing line breaks;
- names containing `=`, `<<`, leading `-`, whitespace, Unicode, and controls;
- reserved, blocked, duplicate, and case-colliding environment names;
- delimiter equality using the runner's ordinal line comparison;
- values resembling workflow commands such as `::stop-commands::`;
- values containing secrets without diagnostic disclosure;
- inputs at, below, and above the supported hard limit;
- POSIX and Windows runner path behavior;
- stdout failures and broken pipes; and
- parallel writers to document unsupported behavior.

Property tests must assert that parsing every successful output with a
compatible runner-parser model yields exactly the requested name and value and
no second record. Differential tests should compare the model against supported
versions of the real GitHub Actions runner.

## Version and specification drift

GitHub documentation and runner behavior can change independently. Every
release must declare the runner versions it was tested against. References to
runner source are pinned for auditability; newer source must be reviewed before
claiming compatibility.

## References

- [Workflow commands for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
- [Script injections](https://docs.github.com/en/actions/concepts/security/script-injections)
- [Variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)
- [Workflow syntax and output limits](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idoutputs)
- [Pinned GitHub Actions runner environment-file parser](https://github.com/actions/runner/blob/50bd7667ef037c0bef8fdc38337a7a797f2279c7/src/Runner.Worker/FileCommandManager.cs)
