# GitHub Actions debug and group commands

Status: implementation contract; not available in a published release.

This file owns observable behavior and destination-specific verification.
The [decision](../decisions/github-actions-log-commands.md) owns rationale;
the [design](../design.md#stdout-adoption-contract) owns consumer scope.

## Contract

```text
shoutx github-actions:debug [MESSAGE]
shoutx github-actions:group [TITLE]
shoutx github-actions:endgroup
```

Debug and group use the shared single-value source rule: argv wins without
reading stdin; otherwise read bounded non-terminal stdin. Terminal stdin with
no operand is usage error 2. Options precede the optional value; `--` ends
options, and `COMMAND --` selects stdin. Only help/version options are accepted;
extra operands and unknown options are usage errors. Endgroup takes no value,
never reads stdin, and accepts only help/version or a bare `--`; after `--`,
any operand is a usage error, including `--help`.
As in the existing CLI, help/version encountered in option position return
immediately and ignore subsequent tokens. They do not validate a write request.
This exception does not apply after a value or after `--`.

Validate strict UTF-8, no NUL, and the shared raw 1 MiB limit before consuming
at most one final CRLF, LF, or bare CR as producer framing. Empty semantic data
is accepted. Nonempty data uses the existing
[Unicode data-start policy](github-actions-annotations.md#command-line-grammar-and-input)
without trimming, decoration, normalization or substitution. This references
only the start policy, not annotation message/metadata constraints. Rejected
starts produce status 1 and `log value is outside the Unicode boundary policy`.
Group additionally rejects any remaining CR or LF with status 1 and
`group title contains CR or LF`. Debug preserves remaining line boundaries in
the decoded message. There is no annotation-style UTF-16-unit limit or separate
whitespace-only rejection. Later Unicode scalars remain data.

Success emits exactly one LF-terminated V2 command:

```text
::debug::ENCODED_MESSAGE LF
::group::ENCODED_TITLE LF
::endgroup:: LF
```

Data encoding replaces percent first (`%25`), then CR (`%0D`) and LF (`%0A`).
No metadata is accepted or emitted. Compute the complete encoded size with
checked arithmetic before allocation and finish validation/construction before
stdout. Maximum output is three times the input limit plus fixed framing;
this is a producer bound, not a provider log-capacity promise. Shared exit
statuses, value-free stderr, SIGPIPE and partial-I/O behavior apply.

Keep stdout connected to the Runner log stream, not an environment file.
Workflow-command processing must be active. Producer success acknowledges
writing only, not consumer processing or UI presentation.

## Consumer effects and boundary

Debug requires Runner debug logging to be enabled (GitHub's
`ACTIONS_STEP_DEBUG=true` setting). When disabled the command is recognized but
does not display its message. Shoutx still validates and emits it: a child
cannot authoritatively infer the consumer setting. Enabled Runner debug output
normalizes CRLF to LF, splits LF, and tags each resulting line as debug.
Thus exact parser data and rendered lines are separate checks; no byte-identical
log rendering or secret-channel guarantee is made.

Group writes a log group marker with the decoded single-line title; endgroup
writes its fixed closing marker. Group nesting, balanced lifetime, body content
and failures between opening and closing remain caller-owned. These commands
do not make arbitrary output inside the group safe. Command echo can add an
encoded group/endgroup echo; debug suppresses that echo. Existing masks may
transform all logged content. Stopped commands appear as ordinary output and
have no requested effect until processing resumes.

The attacker controls message/title data, not command selection or workflow
configuration. Raw physical-line injection and the known V2 fallback-selection
path are in scope; escaping and the start policy address those routes. Group's
single-line rule also prevents input-created continuation log records after
decoding. Misleading titles, terminal styling and other display choices without
a command/record boundary violation are not authorization or UI sanitization
guarantees. Neither writer creates an annotation or changes process exit status
merely because its text looks like an error.

## Command-specific verification

- Exact bytes, status and stderr for argv/stdin, argv precedence, `--`, options,
  empty/space-only data, all optional terminal boundaries and extra operands.
  Endgroup must not read stdin, including invalid or nonterminating input.
- Strict UTF-8 and NUL failures, raw limit minus one/at/plus one, invalid native
  argv encodings, terminal/invalid-handle cases, diagnostic non-disclosure and
  empty stdout on every validation/usage failure. Test encoded expansion and
  literal percent escape sequences independently.
- Unicode starts and tails across scripts, supplementary scalars, combining
  sequences and known disallowed starts; delimiter/property/legacy-looking
  suffixes; group CR/LF rejection and debug mixed line endings. Generated inputs
  must retain exactly one wire line and exact requested parser data/properties.
- Actual pinned V2 parser and ActionCommandManager/handlers under Invariant and
  en-US: exact selected command, empty property map, decoded data, debug output
  enabled and disabled, group/endgroup markers, echo and stopped/resumed states.
  Distinguish emitted log markers from newly executed workflow commands.
- Hosted native profile matrix: enable debug logging for positive checks and
  inspect completed logs for expected debug lines and group/closing markers,
  including Unicode and command-looking data. Missing logs, disabled debug,
  missing/extra records or failed producer steps must fail verification rather
  than being accepted as absence of an injection. Retain source/run/job identity
  and offline verifier negative controls. Preserve existing CI coverage.

## References

- [Official debug command](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-a-debug-message)
- [Official grouping commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#grouping-log-lines)
- [Pinned command handlers](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionCommandManager.cs)
- [Pinned log effects](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ExecutionContext.cs)
