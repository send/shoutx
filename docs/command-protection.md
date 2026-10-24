# What each command protects

Use this guide to choose a writer for a CI output boundary and understand what
still needs protection elsewhere. Shoutx keeps input data from becoming an
unrequested record, command or property at that boundary. It does not decide
whether the requested value or operation is trustworthy.

This is a user-facing guide, not another specification. The linked command
contracts own exact input rules and limits; the [design](design.md) owns
supported consumer profiles, and [compatibility records](compatibility/) own
versioned verification results. Rejection is sometimes the safe result: not
every input can be represented by every command.

## Before choosing a command

- Deliver input as data, using a structured workflow channel and quoted shell
  expansion or stdin. Inserting an untrusted expression into shell source can
  cause injection before shoutx starts.
- Send stdout to the stated destination without changing its bytes. Append
  GitHub file-writer output to the intended Runner-created file; leave stdout
  command writers connected to the Runner or Agent. Logging a file-writer's
  output instead can expose multiline value lines as executable stdout workflow
  commands; file framing does not protect that channel.
- Propagate failures and do not fall back to printing rejected input. Validation
  and encoding failures produce no stdout; an I/O failure after writing starts
  can leave partial output. Success acknowledges writing, not consumer execution.
- Authorize names, paths, content and operations separately. Protect a stored
  value again when a later shell, tool or parser consumes it. Neither a mask nor
  a log group makes arbitrary subprocess output safe.

For byte-preserving shell recipes and failure handling, see the
[README](../README.md#input-and-output-contract). Shared trust assumptions live
in the [threat model](threat-model.md).

## GitHub Actions

All fourteen commands below are in [published v1.0.0](releases/v1.0.0.md). See the
[coverage inventory](design.md#v1-readiness) for earlier-version availability
and exclusions. Stdout commands require active workflow-command processing and
the [supported stdout profile](design.md#stdout-adoption-contract); artifact
declarations have their own [consumer scope](design.md#artifact-consumer-scope).
Installing a binary or obtaining exit status 0 does not establish those conditions.

### File writers

| Command | Destination and protected operation | Typical input problem and shoutx's handling | What the caller still owns |
| --- | --- | --- | --- |
| `github-actions:output` | One named step output in `$GITHUB_OUTPUT` | A title containing a newline followed by `extra=value` could create another output with naive `NAME=VALUE` concatenation. Default mode rejects the internal newline; explicit multiline mode frames it as one value. | The chosen output name, provider quotas and safe later consumption. Exporting a value does not make interpolation into a later script safe. |
| `github-actions:env` | One variable assignment in `$GITHUB_ENV` | A newline could add another assignment and alter subsequent steps. Name validation and value framing prevent that extra record. | Whether the requested variable is safe to set, collisions with other assignments and later use. The reserved-name checks are not a general variable authorization policy or secret store. |
| `github-actions:state` | One saved value in `$GITHUB_STATE` for another phase of the same action | An injected second record could change what a cleanup phase acts on. Shoutx frames only the selected state name and value. | Authorizing cleanup paths/processes and handling duplicate names. This is not a general cross-step variable channel. |
| `github-actions:path` | One incoming entry in `$GITHUB_PATH` | A newline can add a record; a target-OS PATH separator can turn one record into several lookup directories. Shoutx rejects these forms and requires a fully qualified path. Its additional quote rules address the Runner's container argument boundary. | Trust in the directory and executables, correct target OS, and lookup precedence. A valid attacker-controlled directory can still hijack a later command. No existence, symlink or canonicalization check is made. |
| `github-actions:artifacts file` | One typed file declaration in `$GITHUB_ARTIFACTS` | A newline could add a subject; text resembling an OCI reference could be mistaken for another type in untyped syntax. Shoutx rejects record boundaries and emits an explicit file scheme. | File identity, authorization, races, aggregate limits and enabled consumer processing. The writer does not open, hash or upload the file. |
| `github-actions:artifacts oci` | One typed OCI subject declaration in `$GITHUB_ARTIFACTS` | Concatenated fields could add a declaration or confuse its structure. Shoutx emits the fixed OCI scheme and validates structural fields and digest syntax. | Reference validity and whether it resolves to the claimed digest. Shoutx does not contact a registry or establish provenance. |

The last two rows are variants of one command. The three named writers share
explicit line-handling modes; these modes are not available on every writer.
`--first-line`, `--join-lines` and `--join-lines-with` deliberately discard or
rewrite parts of the value, after validating the full input. Choose
`--multiline` when the complete original value, including final newlines, must
be preserved. See the named-record contract for exact mode behavior.

For example, in Bash, these synthetic bytes contain an internal newline:

```bash
set -euo pipefail
# Rejects before writing: the input could otherwise define another output.
printf 'hello\nextra=value' | shoutx github-actions:output title >> "$GITHUB_OUTPUT"
```

If the whole text is intentionally one multiline output, choose that mode
instead, not a raw-output fallback:

```bash
set -euo pipefail
printf 'hello\nextra=value' | shoutx github-actions:output --multiline title >> "$GITHUB_OUTPUT"
```

Contracts and focused tests: [named records](commands/github-actions-records.md),
[PATH](commands/github-actions-path.md),
[artifacts](commands/github-actions-artifacts.md).
Consumer verification: [Runner pin update](compatibility/runner-2.338-update.md),
[artifact integration](compatibility/github-actions-artifacts-availability.md#writer-integration-observations).

### Mask registration

`github-actions:mask` writes one `add-mask` command to stdout. Naively embedding
a secret with line breaks in a command can introduce a second physical command
line; misframing can also register a different value or expose the command as
ordinary log text. Shoutx validates its accepted input boundary and encodes the
value as one command, preserving the semantic value rather than silently
changing the secret.

For example, a literal `%0A` in the value must remain those three characters,
not become a newline when decoded. Shoutx escapes the percent before encoding
line breaks. The GitHub single-value framing rule consumes one optional final
producer newline; use a newline-free producer when it is not part of the value.

Register before any output can disclose the value, with tracing disabled and
command processing active. The Runner also derives trimmed nonempty line masks;
short/common values can hide unrelated text. This is not retrospective log
cleaning, protection against process inspection, or a promise to mask every
fragment or transformed representation. Do not continue secret-using work after
registration fails. The accepted prefix policy alone does not establish
compatibility outside the supported profile.

Prefer stdin for secret delivery. Even a quoted shell expansion passed as a
value operand becomes a process argument and can be exposed to process
inspection. Also, the Runner can suppress job outputs recognized as secrets:
masking a value does not guarantee it can be passed across jobs as an output.

Details: [mask contract](commands/github-actions-mask.md),
[stdout verification and limitations](compatibility/stdout-unicode-policy.md).

### Annotations

`github-actions:notice`, `github-actions:warning` and `github-actions:error`
select their respective annotation severities. They write a stdout command
containing a message and optional typed location/title metadata.

With naive concatenation, a message newline can introduce another command;
delimiters in a file or title can change properties. Shoutx encodes message and
property data separately, validates location combinations and keeps the selected
command fixed. For example, a synthetic title `Build,stage=demo` remains title
data, not a new `stage` property.

The caller still authorizes the message, severity and location. Shoutx does not
prevent misleading diagnostics, confirm that a file contains the given line,
or promise annotation retention or unchanged UI rendering. Messages are
intentionally logged and are not a secret channel. In particular,
`github-actions:error` does **not** fail the step; propagate a nonzero process
status separately when failure is intended.

Details: [annotation contract and tests](commands/github-actions-annotations.md),
[stdout verification and limitations](compatibility/stdout-unicode-policy.md).

### Debug and log groups

| Command | Protected operation and example | What it does not protect |
| --- | --- | --- |
| `github-actions:debug` | One debug command. A message with an internal newline is encoded as data instead of creating a new physical workflow-command line. | Debug logging must be enabled for display. Rendered lines may differ from parser data; this is not a secret channel or control over other output. |
| `github-actions:group` | One group-opening command with a single-line title. Shoutx rejects internal title line breaks rather than allowing decoded continuation records. | A group title may still mislead readers. Group bodies, nesting and lifetime remain caller-owned. |
| `github-actions:endgroup` | A fixed closing command with no input value or interpolated fields. It completes the typed group interface. | It does not track an open group, balance nesting, or guarantee cleanup if an earlier operation failed. |

Details: [log-command contract and tests](commands/github-actions-log-commands.md),
[consumer verification](compatibility/github-actions-log-commands.md).

### Problem matchers

| Command | Protected operation and example | What it does not protect |
| --- | --- | --- |
| `github-actions:add-matcher` | One registration request with a path as command data. An embedded newline is encoded instead of introducing another command. | Shoutx does not read or authorize matcher JSON, regexes or the configuration path. A well-framed path can still select a malicious configuration. |
| `github-actions:remove-matcher owner` | One removal request with an owner property. A comma in a synthetic owner such as `demo,stage=check` remains part of the owner, not another property. | The caller chooses which owner may be removed. Consumer case-insensitive identity, missing owners and removal effects remain Runner behavior. |
| `github-actions:remove-matcher file` | One removal request naming a file whose owners the Runner selects. Path text cannot add another physical command. | Removal reads the file's contents at removal time; it is not a remembered association with a previous add. Files can change between operations. |

The removal rows are variants of one command. Keep command processing active;
these writers do not acknowledge registration/removal or sanitize later tool
output. Consumer echo or diagnostics can disclose paths and owners, so these
are not secret channels.

Details: [matcher contract and tests](commands/github-actions-problem-matchers.md),
[consumer verification](compatibility/github-actions-problem-matchers.md).

## Azure Pipelines

These five commands are implemented in the source tree but **unreleased and
absent from v1.0.0**. Use the [Azure profile](design.md#azure-pipelines-profile)
and [hosted verification record](compatibility/azure-pipelines.md) when evaluating
them. All write to the active Agent stdout command stream, not GitHub files.
Their encoding and input rules are not interchangeable with GitHub's.

### Variables and issues

| Command | Protected operation and example | What the caller still owns |
| --- | --- | --- |
| `azure-pipelines:variable` | One non-secret variable assignment. A value containing a newline or a property delimiter remains data instead of adding another command/property. NAME is validated; output/read-only flags are typed options. | Authorization of the name/value, existing read-only state, settable-variable restrictions, scope and later use. Case and dot-to-underscore export collisions are Azure semantics. Do not pass secrets: this command does not register masks or set secret variables. |
| `azure-pipelines:warning` | One warning issue. A synthetic file value `src/demo;code=other` is encoded as file metadata, not an added `code` property. | The content and selected location, quotas and display behavior. The message is logged; this is not a secret channel. |
| `azure-pipelines:error` | One error issue, with the same separation of message and typed metadata. | Reporting an issue does not replace explicitly propagating a failing process status. Content, location and later provider effects remain caller/provider responsibilities. |

For these writers, unlike GitHub's single-value framing, final CR/LF bytes are
value data. Literal escape-looking text round-trips only when the profile's
percent decoding is enabled on the Agent. A successful write does not acknowledge the
Agent's variable assignment or issue creation.

Details: [Azure contract and verification plan](commands/azure-pipelines.md),
[observed consumer effects](compatibility/azure-pipelines.md).

### PATH

`azure-pipelines:path` writes one `task.prependpath` request for one incoming
directory. A newline in naive output can create another command; a native PATH
separator can turn one decoded path into multiple lookup entries. Shoutx
encodes protocol data and rejects line breaks and list separators, using fully
qualified native-OS path syntax.

For example, `/opt/demo:/opt/extra` is rejected on Linux: it would select two
directories, not one. Unlike the GitHub writer, even a final producer newline
is rejected; use a newline-free producer. The producer and consumer must use the
same supported native OS. This is not the GitHub `RUNNER_OS` selection contract.

The caller must trust the directory and executable lookup it enables. Shoutx
does not check existence, resolve symlinks or promise that different strings
remain distinct entries after Azure's comparisons. The effect is for subsequent
tasks, not the producing process, and Agent restrictions can prevent it.

Details: [PATH contract](commands/azure-pipelines.md#path),
[hosted effects](compatibility/azure-pipelines.md#path-hosted-observations).

### Mask registration

`azure-pipelines:mask` accepts stdin only and writes a fixed `task.setsecret`
request. Naive interpolation can split commands or register escape-decoded text
different from the original; shoutx frames and encodes the accepted value rather
than replacing the credential. The default mode registers one nonempty value
without CR/LF, including no final producer newline. Explicit `--each-line`
registers each nonempty line in order, not the combined original as an extra mask.
The whole input is validated before any registration bytes are written.

For example, a synthetic JSON value containing `{"key":"demo"}` registers the
whole JSON text, not the field value `demo`. If that field will also be exposed,
register it separately before use; if a required representation cannot be
registered, stop that use. Line mode retains nonempty whitespace and header
lines, so the caller must authorize the resulting over-masking of unrelated text.

Unlike GitHub's mask command, this profile requires a job-level short-secret
threshold of zero, debug disabled, and registration in a separate earlier task
of the same job without racing producers. Follow the
[profile and exact settings](design.md#azure-pipelines-profile); a child process
environment setting is not a substitute. Use the tested
[byte-stream delivery examples](commands/azure-pipelines-mask.md#input-delivery-examples).

Protection covers complete registered values/lines in later ordinary
Agent-captured stdout/stderr within that profile. It does not cover arbitrary
fragments, transformed credentials, earlier logs or uploaded files. Masking
does not neutralize commands in arbitrary later output, set a secret variable,
or hide values from process inspection. Stop dependent work on registration
failure; a partial I/O failure is not an atomic batch rollback.

Details: [mask contract and tests](commands/azure-pipelines-mask.md),
[scoped hosted verification](compatibility/azure-pipelines.md#mask-hosted-observations).

## Feedback and security reports

For unclear explanations, missing use cases or non-sensitive improvement ideas,
open a [GitHub issue](https://github.com/send/shoutx/issues/new). Name the command,
the intended destination and the behavior you expected; synthetic examples help.

For a suspected vulnerability or a new attack path, do **not** post reproduction
details in a public issue. Follow [SECURITY.md](../SECURITY.md) and use
[private vulnerability reporting](https://github.com/send/shoutx/security/advisories/new).
Reports showing that an exclusion has a wider impact are useful too.
