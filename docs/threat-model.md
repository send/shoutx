# Threat model

This document defines the security boundary that `shoutx` intends to protect.
It covers the proposed MVP and will evolve with the implementation.

## Security objective

Given a value controlled by an attacker, `shoutx` emits exactly one valid value
or record for the selected destination context, or emits nothing and fails.

The selected command names one interpretation boundary. Crossing that boundary
safely does not make the value safe for other parsers or authorize the action
represented by the value.

## System model

The normal GitHub Actions data flow is:

```text
untrusted source
    -> shell argument or stdin
    -> shoutx
    -> stdout
    -> shell redirection
    -> GitHub Actions environment file
    -> runner parser
    -> output, environment, or PATH state
    -> later consumer
```

`shoutx` controls only its encoded stdout. The caller controls how stdin and
arguments reach the process and where stdout is redirected. GitHub Actions
controls the environment-file parser and downstream runtime behavior.

GitHub creates a distinct environment-file path for each step. The runner reads
these files after processing the step. `$GITHUB_OUTPUT`, `$GITHUB_ENV`, and
`$GITHUB_PATH` therefore describe protocols between the step and the runner,
not ordinary application data files.

## Adversary

The attacker may control arbitrary text values obtained from, for example:

- pull request and issue titles, bodies, labels, and branch names;
- commit metadata;
- downloaded files, artifacts, and command output;
- API responses and data produced by untrusted build inputs.

The attacker attempts to make a value escape its intended record or context,
create additional records, alter later command lookup, inject shell source, or
change rendered content.

The workflow definition, selected `shoutx` command, redirection target, trusted
installation of `shoutx`, and runner itself are assumed not to be controlled by
the attacker. Workflows that execute attacker-controlled code have already
crossed a stronger trust boundary and are outside this model.

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

This precondition is essential: a destination encoder cannot repair injection
that occurred before it received the value.

## Protected boundaries

### `github-actions:output`

The security property is structural integrity of one `$GITHUB_OUTPUT` record.
An attacker-controlled value must not define another output name or terminate a
multiline record early.

Single-line mode rejects line breaks. Multiline mode uses the documented
`NAME<<DELIMITER` framing and selects a delimiter that does not occur on a line
of its own in the value. The command rejects invalid names according to a
documented, conservative grammar.

This does not protect later use of the output. If a later `run:` block inserts
the output directly as an expression, shell injection is again possible.

### `github-actions:env`

The security property is structural integrity of one `$GITHUB_ENV` record. An
attacker-controlled value must not define another variable or terminate a
multiline record early.

The command does not permit names that GitHub reserves or blocks, and may apply
a grammar stricter than the runner parser. It does not make later uses of the
environment variable safe for shell, SQL, URLs, or other contexts.

### `github-actions:path`

The security property is limited to one `$GITHUB_PATH` record. The command
rejects line breaks so one input cannot add multiple path entries.

There is no encoding that makes an attacker-controlled directory safe to add to
`PATH`. An attacker who controls a directory earlier in command lookup may place
a malicious executable there. The caller must separately establish that the
path is trusted and intended. `github-actions:path` is framing and validation,
not authorization.

### `shell:arg`

If included in the MVP, the security property is one shell word after exactly
one parse by a named shell dialect. It does not cover `eval`, nested parsing,
command options, executable selection, expansions performed before encoding, or
concatenation into a larger shell token without a documented composition rule.

### `markdown:text`

If included in the MVP, the security property must be defined against a named
Markdown dialect and renderer. Rendering attacker-controlled input as text is
different from sanitizing an existing Markdown or HTML document. XSS protection
provided by the hosting renderer is outside `shoutx`'s control and must not be
claimed without an explicit platform contract.

## Attack and guarantee matrix

| Attack | In scope | Intended control |
| --- | --- | --- |
| New output or environment record through a line break | Yes | Reject line breaks or use collision-free multiline framing |
| Early multiline termination | Yes | Verify the delimiter is not a standalone input line |
| Record-name confusion | Yes | Validate against a documented conservative grammar |
| Multiple PATH entries through a line break | Yes | Reject line breaks |
| Command hijacking through an attacker-controlled PATH directory | No | Caller must validate trust and authorization |
| Shell injection in `run:` before `shoutx` starts | No | Pass expressions through `env:` and quote shell expansions |
| Shell injection when a stored output is consumed later | No | Protect the later shell boundary separately |
| Option injection such as a value beginning with `-` | No | Use `--` or an API that separates options from operands |
| Malicious behavior of an executed checkout or artifact | No | Do not execute untrusted code in privileged workflows |
| Concurrent modification of GitHub environment files | No | Requires runner and process isolation outside this tool |
| Denial of service using unbounded input | Yes | Enforce a documented input or buffer limit |
| Secret exposure through diagnostics | Yes | Do not echo rejected values in diagnostics |

## Failure behavior

Commands validate and encode the complete input before writing to stdout. On
invalid input, resource-limit failure, or internal error, they write no encoded
bytes to stdout and exit non-zero. Diagnostics go to stderr and identify the
failed rule without reproducing untrusted or secret values.

Shell redirection itself is outside this atomicity guarantee. In particular,
`>` may create or truncate a destination before the process validates input.
The documented GitHub Actions usage appends with `>>`.

## Encoding details that require tests

- LF and CRLF input, including a final line without a terminator;
- bare CR and NUL;
- empty values, empty first lines, and trailing line breaks;
- names containing `=`, `<<`, whitespace, Unicode, and control characters;
- delimiter equality using the runner's ordinal line comparison;
- values that resemble workflow commands such as `::error::`;
- large inputs at, below, and above the supported limit;
- POSIX and Windows runner path behavior;
- stdout write failures and broken pipes.

Property tests should assert that parsing successful output with a compatible
model of the runner yields exactly the requested name and value and no second
record.

## References

- [Workflow commands for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
- [Script injections](https://docs.github.com/en/actions/concepts/security/script-injections)
- [Variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)
- [GitHub Actions runner environment-file parser](https://github.com/actions/runner/blob/main/src/Runner.Worker/FileCommandManager.cs)
