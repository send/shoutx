# Threat model

This document defines the security boundary that `shoutx` protects. It covers
the GitHub Actions writers and inventories the remaining deferred boundaries.

Concrete cases and compatibility gates derived from this model are maintained
in the [CLI contract test plan](test-plan.md).

Revision status: implemented writer baseline.

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
    -> output, environment, PATH, or intra-action state
    -> later consumer
```

`shoutx` controls its validation, encoding, diagnostics, and stdout writes. The
caller controls how values reach the process and where stdout is redirected.
The operating system controls process I/O. GitHub Actions controls the
environment-file parser and downstream runtime behavior.

GitHub creates distinct environment-file paths while running a step or action.
The runner reads these files after processing the producer.
`$GITHUB_OUTPUT`, `$GITHUB_ENV`, `$GITHUB_PATH`, and `$GITHUB_STATE` are
therefore protocols between executed code and the runner, not ordinary
application data files. Saved state is exposed only between phases of the same
action.

## Assets

The model aims to protect:

- the structure and namespace of runner command-file records;
- subsequent step environment state;
- command lookup affected by `PATH`;
- intra-action state passed to a later action phase;
- the integrity of generated shell contexts, if their encoder is included;
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

GitHub requires environment files to be written as UTF-8. The CLI contract is
therefore:

- input values are valid UTF-8 text;
- invalid UTF-8 from stdin is rejected before output begins;
- NUL is rejected in every mode;
- emitted records are UTF-8 without a byte-order mark; and
- record framing is emitted explicitly and does not rely on host text-mode
  newline translation.

Command-line arguments are subject to the host process API. Implementations
must reject arguments that cannot be represented as valid UTF-8 rather than
silently replacing data.

Every non-multiline GitHub Actions writer consumes at most one final line
boundary as input framing. The default named-writer mode then rejects both CR
and LF; normalization modes treat each remaining CRLF as one line boundary and
each remaining bare CR or LF as one boundary. `--multiline` preserves all three
forms, including trailing line breaks. Framing normally uses LF; on Windows a
value ending in bare CR requires a CRLF framing separator to prevent the Windows
runner parser from consuming the value's final CR. Here Windows means the
target runner OS, selected from trusted `RUNNER_OS` when present and otherwise
from the native process OS; it does not mean the shell or executable format.

Shell redirection and shell-specific transcoding remain outside `shoutx`'s
control. Supported invocation environments must preserve native-process stdout
bytes unchanged. Windows PowerShell and PowerShell Core before 7.4 are
unsupported. PowerShell Core 7.4 and later is included for direct redirection,
with byte-capture and runner differential coverage in CI. Merged stdout and
stderr are treated as text and are unsupported.

## GitHub Actions boundary inventory

The supported environment-file destinations are:

| Boundary | Status | Interpretation |
| --- | --- | --- |
| `$GITHUB_OUTPUT` | Included | Named step-output records |
| `$GITHUB_ENV` | Included | Named environment-variable records |
| `$GITHUB_PATH` | Included | One path entry per line, then PATH-separator joining |
| `$GITHUB_STATE` | Included | Named intra-action state records for `pre:`, `main:`, and `post:` phases |

Other recognized boundaries are deferred, candidates, or out of scope:

| Boundary | Status | Primary concern |
| --- | --- | --- |
| `$GITHUB_STEP_SUMMARY` | Deferred; no generic Markdown writer planned | GitHub-rendered content integrity rather than runner command-file record injection |
| stdout `add-mask` workflow command | Specified candidate; not implemented | Register one faithfully decoded value for subsequent runner log masking |
| other stdout workflow commands | Deferred | Lines such as `::warning::` and `::stop-commands::` are runner control messages |
| `$GITHUB_ARTIFACTS` | Deferred; 2026-09-28 hosted-runner gate failed | One file or OCI declaration per line |
| `$GITHUB_ARTIFACTS_LIST` | Out of scope | Runner-managed, read-only JSON input |

Inventorying a boundary does not commit `shoutx` to supporting it. It prevents
an unsupported control channel from being mistaken for a protected one.

## Protected and specified boundaries

### `github-actions:output`

The security property is structural integrity of one `$GITHUB_OUTPUT` record.
An attacker-controlled value must not define another output name or terminate a
multiline record early.

Every non-multiline named-writer mode consumes one optional final CRLF, LF, or
bare CR before applying its mode-specific rule. Default mode rejects any
remaining CR or LF.
Multiline mode uses the documented
`NAME<<DELIMITER` framing and verifies, more conservatively, that the selected
delimiter does not occur anywhere in the value. Framing preserves empty values
and trailing LF, CRLF, and bare CR.

The command accepts names matching `[A-Za-z_][A-Za-z0-9_-]*`, up to 255 ASCII
bytes. This matches GitHub's documented action-output identifier grammar,
including established kebab-case output names. It does not protect later use of
the output. If a later `run:` block inserts the output directly as an
expression, shell injection is again possible.

GitHub applies separate limits to job and workflow outputs. Passing `shoutx`
validation does not guarantee that GitHub will accept or propagate the output.

### `github-actions:env`

The security property is structural integrity of one `$GITHUB_ENV` record. An
attacker-controlled value must not define another variable or terminate a
multiline record early.

The command accepts names matching `[A-Za-z_][A-Za-z0-9_]*`, up to 255 ASCII
bytes. It rejects `GITHUB_*`, `RUNNER_*`, and `NODE_OPTIONS` using ASCII
case-insensitive comparisons. This is intentionally stricter than the current
runner file parser and reflects GitHub policy and portable environment-variable
use.

The command does not read the destination file and cannot detect duplicate or
case-colliding assignments made by another invocation. The runner's handling of
such assignments and caller-level uniqueness are outside this command's
guarantee.

The command does not make later uses of the variable safe for shell, SQL, URLs,
templates, or other contexts. It also does not make environment variables an
appropriate channel for secrets.

### `github-actions:path`

The security property is limited to one `$GITHUB_PATH` record. As with other
non-multiline modes, the command consumes at most one final CRLF, LF, or bare CR
as input framing, then rejects NUL, every remaining CR or LF, and empty values
so one input cannot add multiple entries.

The runner's second interpretation step joins accepted lines using the target
OS PATH separator. shoutx therefore also rejects POSIX `:` or Windows `;`, so
one file record cannot become multiple effective PATH entries. It accepts only
fully qualified paths in the target runner dialect and rejects a leading
U+FEFF, whose preservation would otherwise depend on whether the record begins
the file. Target selection follows trusted `RUNNER_OS`, with native fallback;
an unknown value is rejected. It rejects `"` on every target because the
runner's container step host embeds PATH in a quoted `docker exec` argument
string. For the same boundary, a POSIX path ending in backslash is rejected
because .NET argument re-tokenization can consume backslashes or the closing
quote and change the resulting argument.

There is no encoding that makes an attacker-controlled directory safe to add to
`PATH`. An attacker who controls a directory earlier in command lookup may place
a malicious executable there. The caller must separately establish that the
path is trusted and intended. `github-actions:path` is framing and validation,
not authorization.

shoutx does not canonicalize, resolve dot segments or symlinks, change path
separators, trim whitespace, inspect the destination file, or require the
directory to exist. Those transformations could change identity or introduce
filesystem races and are outside record framing.

### `github-actions:state`

The security property is structural integrity of one `$GITHUB_STATE` record.
An attacker-controlled value must not define another state name or terminate a
multiline record early. Injected state could change later cleanup behavior in
the same action, including which process, path, or resource a `post:` phase
operates on.

The command shares the named-writer value, line-mode, multiline-framing, size,
and failure contracts. It accepts names matching
`[A-Za-z_][A-Za-z0-9_]*`, up to 255 ASCII bytes. It has no environment
reserved-name block because GitHub exposes the value with a `STATE_` prefix.
The runner compares saved state names ordinally without regard to case. A later
case-colliding record replaces the value while retaining the first record's
name spelling. shoutx does not inspect earlier records or prevent that
replacement.

GitHub exposes saved values only to another phase of the same action; a write
from an ordinary workflow step has no such consumer. shoutx does not expand
that scope and does not make later consumption safe. Cleanup code must still
authorize paths, process identifiers, and other state before acting on them.

### Candidate `github-actions:mask`

The candidate security property is structural integrity of one stdout
`add-mask` workflow command and faithful registration of its decoded value by
the supported runner while command processing is active. After consuming at
most one final producer-framing boundary, shoutx preserves the remaining value
and escapes `%`, CR, and LF so attacker-controlled data cannot terminate the
physical line or create another workflow command.

The candidate rejects NUL, invalid UTF-8, empty values, and values consisting
only of Unicode whitespace before output begins. The last two cases are
necessary because the runner warns and performs no registration for
`String.IsNullOrWhiteSpace` data. A successful shoutx status must not imply a
mask was installed when the runner would deterministically reject it.

The runner registers the exact decoded value and also each trimmed, nonempty
line of a multiline value. This can mask more text than the exact value alone;
blank and whitespace-only lines are not separately registered. These derived
line masks are accepted destination behavior rather than a transformation made
or independently promised by shoutx.

Masking is prospective and best-effort. It does not protect a value logged
before registration, passed visibly in process arguments, exposed by shell
tracing or host audit facilities, transformed into an unregistered form, or
read by other code running with equivalent job privileges. Very short or
common values can redact unrelated text. If workflow-command processing has
been suspended with `stop-commands`, the runner ignores the candidate output;
the encoded command line is then handled as ordinary log output and can expose
the value. That hidden runner state cannot be detected by the child process and
active command processing is therefore an explicit precondition of the
registration guarantee.

GitHub permits a masked value to be placed in a step output for later use in
the same job, but the runner suppresses job outputs that its secret masker
recognizes. shoutx therefore makes no guarantee that a masked value can cross
job or workflow boundaries as an output.

### Deferred `$GITHUB_ARTIFACTS` candidate

The candidate security property is structural integrity of one typed artifact
declaration. An attacker-controlled newline must not add another file or OCI
subject to the job aggregate, and content resembling another subject type must
not change the selected type. An injected subject could corrupt the set of
materials associated with later provenance or attestation processing.

The proposed writer always emits `file://` or `oci://` and rejects record
boundaries before stdout begins. This does not establish that a declared file
is trusted, immutable, or intended. The runner resolves and opens file paths
after the producing step, follows symlinks, excludes directories, and calculates
the digest. When the step has a job container, the runner translates rooted
container paths inside known mounts and rejects rooted paths outside them;
without a container it uses the rooted path directly. Relative container paths
resolve through the host workspace context rather than the container working
directory. Other special file types are not explicitly excluded. Those
operations create filesystem-identity, blocking-I/O, and time-of-check/time-of-
use concerns outside shoutx's record-framing guarantee.

Likewise, structurally encoding an OCI reference and digest does not validate
the reference against the OCI distribution grammar, contact a registry, or
prove that the named object has that digest. Duplicate, conflicting, and
aggregate-limit behavior depends on declarations outside one shoutx
invocation.

No protection is claimed until hosted-runner testing confirms the feature is
enabled. A runner may currently expose `$GITHUB_ARTIFACTS` while silently
ignoring its contents when both its server feature flag and self-hosted opt-in
environment variable are disabled.

### Deferred shell source encoding

`shell:arg` is not a v1.0 candidate. Although a value can be represented as one
POSIX shell word in source, command substitution does not reparse quote
characters produced by the command. The representation therefore has no safe,
natural runtime consumption pattern. It becomes effective only in source that
is parsed later, where a one-word encoder cannot enforce trusted composition or
exactly one parse and may encourage unsafe `eval` use.

The recommended GitHub Actions pattern remains a value passed through `env:` and
expanded as `"$VALUE"`. A future shell-source feature would require a concrete
destination, named dialect, and composition contract. It would still not cover
command options, executable selection, or application-level authorization.

### Markdown rendering

`markdown:text` is not a v1.0 candidate. GitHub documents job summaries as
[GitHub Flavored Markdown][job-summaries], and its documented
[markup pipeline][github-markup] applies HTML sanitization before rendered
content is displayed. A correctly redirected `$GITHUB_STEP_SUMMARY` write does
not feed Markdown records back into workflow execution. Links, document
structure, mentions, and misleading presentation remain possible, but treating
all such features as unsafe would turn shoutx into an application-specific
content-policy engine and reduce normal Markdown usability without addressing
a comparable runner-protocol injection path.

This conclusion is specific to GitHub-rendered content. It does not treat the
same bytes as safe for an arbitrary Markdown or HTML renderer, and it does not
cover lines written to the workflow log: `add-mask` is specified separately and
other stdout workflow commands remain deferred. A future Markdown feature
requires a concrete threat, a named rendering surface, and explicit decisions
for links, images, mentions, Unicode controls, bidirectional text, and embedded
HTML.

[job-summaries]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
[github-markup]: https://github.com/github/markup#github-markup

## Attack and guarantee matrix

| Attack | In scope | Intended control |
| --- | --- | --- |
| New output, environment, or state record through a line break | Yes | Consume only one optional final boundary, reject remaining CR/LF, or use verified multiline framing |
| Early multiline termination | Yes | Use an independent delimiter and verify that it does not occur in the value |
| Record-name confusion | Yes | Validate against a documented conservative grammar |
| Multiple PATH entries through a line break | Yes | Consume only one optional final boundary and reject remaining CR/LF |
| Multiple artifact declarations through a line break | Deferred candidate | Emit one typed scheme and reject remaining CR/LF before output if hosted-runner availability later permits implementation |
| Multiple effective PATH entries through the PATH separator | Yes | Reject `:` for POSIX targets and `;` for Windows targets |
| Container runtime option injection through PATH quoting | Yes | Reject `"` on every target before the runner constructs `docker exec` arguments |
| Container path identity change through argument re-tokenization | Yes | Reject a trailing backslash for POSIX targets |
| Append-position-dependent leading BOM | Yes | Reject a leading U+FEFF before output |
| Relative PATH resolution against a later working directory | Yes | Require a fully qualified target-platform path |
| Invalid UTF-8 or NUL | Yes | Reject before output begins |
| Memory exhaustion through large input | Yes | Enforce a documented hard input limit |
| Secret exposure through diagnostics | Yes | Do not reproduce input values in diagnostics |
| Additional workflow commands through mask data | Candidate | Percent-escape `%`, CR, and LF and emit one physical `add-mask` line |
| False mask success for empty or whitespace-only data | Candidate | Reject before stdout because the runner would not register it |
| Disclosure before mask registration or through process tracing | No | Deliver secrets as data, disable tracing, and register before other output |
| Mask ignored and logged while workflow commands are stopped | No | Require active command processing; the child cannot observe runner state |
| Over-masking caused by short values or multiline line registration | No | Document runner substring and per-line behavior; caller chooses the value |
| Command hijacking through an attacker-controlled PATH directory | No | Caller validates trust and authorization |
| Declaring an attacker-selected file or OCI subject | No | Caller validates identity, trust, and authorization |
| Shell injection before `shoutx` starts | No | Use a structured data channel and quoted expansion |
| Injection when a stored value is consumed later | No | Protect the later interpretation boundary |
| Option injection such as a value beginning with `-` | No | Use `--` or an API separating options from operands |
| Stdout workflow-command injection from another process | No | Avoid logging untrusted bytes or suspend command processing safely |
| Malicious behavior of executed code or artifacts | No | Do not execute untrusted code in privileged workflows |
| Concurrent environment-file modification | No | Requires process and runner isolation outside this tool |
| Redirection to an attacker-selected file or symlink | No | Caller owns and validates the destination |
| Secret disclosure in the successfully encoded value | No | Caller selects an appropriate data channel |

## Resource limits

`shoutx` must read and validate the complete input before beginning output. The
value is therefore limited to 1 MiB (1,048,576 UTF-8 bytes), enforced equally
for argv and stdin. The normalized value has the same limit. Record names and
`--join-lines-with` separators are limited to 255 bytes. Implementations must
compute expanded sizes with checked arithmetic and reject them before allocating
the normalized result.

The mask candidate applies the 1 MiB limit after optional stdin framing. Its
workflow-command encoding can expand each input byte to three bytes, so the
complete encoded line can exceed 1 MiB. The implementation must compute that
length before allocation. GitHub publishes no separate maximum for dynamic
masks or workflow-command lines; local success therefore does not promise that
every runner or surrounding log transport will accept an unusually large
value. The runner also derives several alternate representations for each
registered value, which makes large masks operationally expensive even within
the accepted bound.

For the artifact candidate, PATH and REFERENCE each retain the 1 MiB input
limit, while DIGEST has a fixed algorithm-dependent length. The complete
scheme-prefixed record including its final LF must also be at most 1 MiB, so
framing overhead makes the maximum accepted PATH or REFERENCE smaller. This
only bounds one shoutx record; it cannot account for bytes already present in
the per-step command file or subjects already accumulated in the job.

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

Exit status 0 means success, 1 means input or policy rejection, I/O failure, or
internal failure, and 2 means command-line usage error. Help and version output
exit 0. Status 1 does not distinguish a failure before output from an I/O
failure after output began. Implementations ignore SIGPIPE and report EPIPE as
an I/O failure so broken pipes follow the documented status contract.

Once writing begins, an operating-system or I/O failure can leave partial bytes
in stdout or the redirected destination. `shoutx` cannot promise transactional
stdout. It must report the failure through a non-zero exit status when the host
API exposes it. It should use one write operation for a complete constructed
record where possible, but short writes and later writers can still leave or
extend a malformed record.

On POSIX, Rust runtime initialization replaces standard descriptors that were
already closed at process startup with `/dev/null`. Such a stdin is observed as
empty input, and such a stdout can discard output without exposing an error.
This is an explicit host-runtime limitation; supported writer usage redirects
stdout to an opened runner file. Invalid Windows handles and I/O failures that
the host API does expose still require status 1.

A non-zero native-process status does not necessarily stop a workflow step.
In particular, PowerShell does not turn every non-zero native status into a
terminating error. Documented recipes must enable native-command error
propagation or check `$LASTEXITCODE` immediately; supported-shell smoke tests
must verify that rejection fails the step.

Diagnostics go to stderr and identify the failed rule without reproducing
untrusted or secret values. Diagnostic text itself must not accidentally form a
GitHub stdout workflow command.

Environment-file writer stdout must be redirected to the selected environment
file. In particular, an unredirected multiline value can place
attacker-controlled lines on the runner command channel, which is outside the
environment-file encoding guarantee. The mask candidate is the deliberate
exception: its stdout is one encoded runner command and must remain connected
to the runner log stream rather than being redirected to an environment file.

Shell redirection is outside the output guarantee. `>` may create or truncate a
destination before `shoutx` validates input. The documented GitHub Actions usage
appends to runner-created files with `>>`.

## Secrets

`shoutx` treats every input value as potentially sensitive:

- diagnostics do not include values or delimiter-derived excerpts;
- debug modes must not print raw input;
- generated delimiters must not be derived from secret input; and
- failures do not suggest retry commands containing the original value.

For environment-file writers, GitHub's log masking and summary masking remain
defense-in-depth rather than part of the `shoutx` guarantee. The mask candidate
guarantees only construction and runner registration of one accepted value,
not comprehensive confidentiality. Successfully writing a secret to an output,
environment variable, PATH entry, summary, command argument, or later parser
may still disclose or misuse it.

## Concurrency and lifecycle

`shoutx` does not coordinate multiple processes writing to the same destination.
Background processes may outlive a step, and self-hosted runners may have weaker
isolation than GitHub-hosted runners. The caller must ensure exclusive,
in-lifecycle writes to the runner-provided file.

Plugin discovery, if added, creates another executable-resolution boundary. A
future plugin design must prevent untrusted working directories or `PATH`
entries from selecting a different provider implementation.

## Required tests

- LF, CRLF, and bare-CR input, including every trailing form, the Windows
  trailing-bare-CR framing case, and a final line without a terminator;
- NUL, invalid UTF-8, and a UTF-8 byte-order mark;
- empty values, empty first lines, and one or more trailing line breaks;
- default-mode inputs with no terminator, exactly one final CRLF/LF/CR, multiple
  final boundaries, internal boundaries, and LF followed by CR;
- first-line and join-mode inputs with no boundary, one final boundary, and
  multiple final or internal boundaries;
- names containing `=`, `<<`, leading `-`, whitespace, Unicode, and controls;
- reserved and blocked names, plus documentation of unsupported duplicate and
  case-collision detection across invocations;
- state names that are reserved for `$GITHUB_ENV` but valid after the `STATE_`
  prefix, plus ordinal case-insensitive replacement in the runner state
  handler;
- delimiter equality using the runner's ordinal line comparison, plus the
  stronger no-substring selection rule;
- values resembling workflow commands such as `::stop-commands::`;
- values containing secrets without diagnostic disclosure;
- absolute POSIX, Windows drive, UNC, and verbatim path forms, plus relative,
  PATH-separator, leading-BOM, and Win32-device rejection;
- container argument behavior for quotes and odd and even trailing-backslash
  runs in POSIX paths;
- path parser BOM position, CR/LF/CRLF splitting, empty-line removal, ordering,
  and culture-invariant duplicate cases;
- inputs at, below, and above the supported hard limit;
- `--`, mutually exclusive modes, `--join-lines-with` arguments beginning with
  `-`, equals-form separators, help/version option position, missing operands,
  and extra operands;
- empty non-terminal stdin, terminal stdin with no value, POSIX startup-closed
  stdin as `/dev/null`, and invalid Windows stdin handles;
- POSIX and Windows runner path behavior;
- byte-for-byte stdout capture under each supported Windows invocation;
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
- [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [Pinned Actions toolkit workflow commands](https://github.com/actions/toolkit/blob/a7911ca44eeaa6d87ad79a4703b750fb0993fb99/packages/core/src/command.ts)
- [Script injections](https://docs.github.com/en/actions/concepts/security/script-injections)
- [Variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)
- [Action metadata syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax)
- [Workflow syntax and output limits](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idoutputs)
- [PowerShell redirection](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_redirection)
- [Pinned GitHub Actions runner v2.337.0 environment-file parser](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/FileCommandManager.cs)
- [Pinned GitHub Actions runner v2.337.0 workflow-command manager](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs)
