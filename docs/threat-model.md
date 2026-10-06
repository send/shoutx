# Threat model

This document defines the security boundary that `shoutx` protects. It covers
the GitHub Actions writers and inventories the remaining deferred boundaries.

Shared compatibility gates derived from this model are maintained in the
[CLI contract test plan](test-plan.md); boundary-specific analyses and cases
are colocated in the command specifications linked below.

Revision status: implemented writer baseline; stdout responsibility and attack
classification and adoption boundary clarified on 2026-10-06. This revision
does not change CLI input policy or release contents.

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

For stdout workflow commands, the runner worker is a separate consumer whose
current culture and collation backend are not reliably observable by shoutx.
An exit status of zero from the producer does not prove that this consumer
recognized the emitted record. The known parser behavior and compatibility
evidence are documented in the
[workflow-command compatibility note](compatibility/github-actions-workflow-command-parser.md).

The [design-owned adoption contract](design.md#stdout-adoption-contract)
separates the supported profile, dependency assumptions, and producer duties.
Reference probes do not identify hidden live Worker settings. Known excluded-
configuration failures, including mask disclosure, remain documented risks;
producer success does not remove them.

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
| `$GITHUB_STEP_SUMMARY` | Out of scope | GitHub-rendered Markdown has no runner command-file record structure to inject into; rendered HTML is sanitized, while content integrity remains the producer's responsibility |
| stdout `add-mask` workflow command | Productization accepted; still isolated and absent from releases | Register one faithfully decoded value for subsequent runner log masking |
| stdout annotation workflow commands | Productization accepted; still isolated and absent from releases | Emit one faithfully decoded notice, warning, or error with validated location metadata |
| other stdout workflow commands | Deferred | Lines such as `::stop-commands::` and `::group::` are runner control messages |
| `$GITHUB_ARTIFACTS` | Deferred; 2026-09-28 hosted-runner gate failed | One file or OCI declaration per line |
| `$GITHUB_ARTIFACTS_LIST` | Out of scope | Runner-managed, read-only JSON input |

Inventorying a boundary does not commit `shoutx` to supporting it. It prevents
an unsupported control channel from being mistaken for a protected one.

## Protected and specified boundaries

### Stdout mask and annotation responsibility

This section owns the stdout attack inventory and its classification. Command
specifications own accepted inputs, encoding and command-specific consumer
limitations; compatibility records own observations and their version identities.

The attacker controls values and text metadata, not the selected shoutx command,
workflow configuration or installation. The protected assets are the integrity
of the requested Runner operation and its fields and, for mask, delivery of the
original secret to registration without disclosure caused by misframing.
Annotation content is intentionally logged; annotation is not a secret channel.
Choosing misleading content or an over-broad mask remains caller authorization,
not a structural injection that shoutx promises to prevent.

An in-scope security finding must connect attacker-controlled input through
shoutx output and consumer interpretation to a protected asset. Unexpected
Unicode behavior or an unfinished dependency proof is not itself such a finding.
Faithful decoding remains a product correctness requirement: distinguishing a
functional failure from an attack does not make that failure acceptable behavior.

| Path | Boundary crossing and harm | Current control within the design profile |
| --- | --- | --- |
| AP1: physical-line injection | Value CR/LF produces additional workflow commands | Existing percent-first CR/LF encoding and one-line construction block this route under the documented transport. Retain those controls. |
| AP2: fallback command selection | Intended V2 recognition fails and value text becomes a different registered workflow command | The command specifications' positive start policy and one-line encoding, checked against parser/fallback regressions and generated producer records. New acceptance changes require reassessment. |
| AP3: message-to-property promotion | A shifted V2 separator promotes message data into annotation header fields | The shared data-start policy plus independent command/property round-trip checks. Ordinary display differences are not this path. |
| AP4: mask misregistration or disclosure | Misframing leaves the original secret unregistered, registers a different value, or exposes the command as ordinary log text | Original-value construction, the data-start policy, exact registration and subsequent-redaction checks. A different registered string is not protection of the original. Consumer state and excluded configurations retain the limitations below. |
| AP5: metadata injection | TITLE/FILE data escapes its field or changes other properties, including typed fields | Property escaping, typed-field validation and the structural Unicode-property terminator specified by the annotation contract, verified with final-field and Worker-effect cases independently of message tests. |

AP2–AP4 reuse the
[parser and fallback evidence](compatibility/github-actions-workflow-command-parser.md#parser-fallback-and-impact).
The inventory identifies relevant routes, not an assertion that today's accepted
inputs exploit each route, nor a completed safety argument for broader inputs.
Size exhaustion and diagnostic disclosure retain the shared producer controls;
they do not authorize auditing consumer allocation internals.

Annotation nonarrival, truncation, masking or location translation without a
protected-boundary violation is a functional or applicability issue, not command
injection. For mask, failed recognition can instead have direct confidentiality
impact (AP4). Tests must distinguish parser fidelity from downstream effects.

The workflow must deliver input as data and preserve output transport, and
workflow-command processing must be active. Required annotation features and
consumer configuration are deployment conditions, not state shoutx can inspect
or enforce. The command specifications retain their concrete limitations.
The [design](design.md#stdout-adoption-contract) owns the adoption profile;
command implementations remain isolated until productization is complete.
Known excluded-environment failures, including deferred th-TH behavior, remain
disclosed limitations rather than new investigation tasks.

Shoutx relies on Runner/.NET/ICU providing their specified behavior; it does not
certify those implementations. Reuse relevant observations and assess concrete
harm that affects the proposed output, but do not require complete character-set
or dependency-internal proofs. A known harmful route is not dismissed merely
because its cause is in a dependency. Controls are chosen against such routes,
with their effectiveness and product/maintenance cost made explicit.
Original-value preservation and explicit-loss rules remain owned by the
[design invariants](design.md#security-invariants); no sanitizer is adopted here.

### Command-specific analyses

Detailed boundary analyses are colocated with their command specifications:

- [GitHub Actions named records](commands/github-actions-records.md)
- [GitHub Actions PATH writer](commands/github-actions-path.md)
- [GitHub Actions log-mask command](commands/github-actions-mask.md)
- [GitHub Actions annotation commands](commands/github-actions-annotations.md)

### Deferred and out-of-scope analyses

Detailed rationale for deferred and out-of-scope features is recorded in
decision documents:

- [GitHub Actions artifact declarations](decisions/github-actions-artifacts.md)
- [POSIX shell-word encoding](decisions/shell-arg.md)
- [Markdown output](decisions/markdown-output.md)

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
| Stdout data interpreted as another command or property | Yes | [AP1–AP3 and AP5](#stdout-mask-and-annotation-responsibility); assess a proposed acceptance change against concrete boundary crossings |
| Mask misregistration or disclosure caused by misframing | Yes | [AP4](#stdout-mask-and-annotation-responsibility), within documented consumer preconditions; not comprehensive confidentiality |
| False mask success for empty or whitespace-only data | Yes | Reject before stdout because the runner would not register it |
| Ordinary annotation truncation or metadata repair | Functional contract | Keep the command specification's message limit and location validation; not itself a demonstrated security boundary crossing |
| Mask-induced annotation transformation or truncation | No | Runner secret masking occurs after decoding; document that it can change and expand the message |
| Misleading or excessive attacker-selected annotations | No | Caller authorizes content and severity; shoutx protects only command structure |
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

The mask command applies the 1 MiB limit to raw input before optional final
producer framing is consumed, matching the shared acquisition contract. Its
workflow-command encoding can expand each semantic input byte to three bytes,
so the complete encoded line can exceed 1 MiB. The implementation must compute
that length before allocation. GitHub publishes no separate maximum for dynamic
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
environment-file encoding guarantee. Feature-enabled stdout workflow-command
writers are the deliberate research exception: mask and annotation commands
emit one encoded runner command and must remain connected to the runner log
stream rather than being redirected to an environment file. They are
compile-time absent from supported binaries.

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
defense-in-depth rather than part of the `shoutx` guarantee. The mask command's
intended guarantee is construction and runner registration of one accepted
value within the design profile, not comprehensive confidentiality or support
across all cultures. The authoritative behavior is in the
[mask command specification](commands/github-actions-mask.md). Successfully
writing a secret to an output, environment variable, PATH entry, summary,
command argument, or later parser may still disclose or misuse it.

## Concurrency and lifecycle

`shoutx` does not coordinate multiple processes writing to the same destination.
Background processes may outlive a step, and self-hosted runners may have weaker
isolation than GitHub-hosted runners. The caller must ensure exclusive,
in-lifecycle writes to the runner-provided file.

Plugin discovery, if added, creates another executable-resolution boundary. A
future plugin design must prevent untrusted working directories or `PATH`
entries from selecting a different provider implementation.

## Required tests

The shared test plan covers command-line parsing, input selection, strict UTF-8,
NUL rejection, size limits, diagnostics, exit status, process I/O, supported
shells, and differential testing against the pinned runner. Each command
specification defines its boundary-specific cases:

- [named-record name and multiline cases](commands/github-actions-records.md#command-specific-verification);
- [PATH grammar, parser, ordering, and container cases](commands/github-actions-path.md#command-specific-verification);
- [mask encoding, runner behavior, and hosted-log cases](commands/github-actions-mask.md#command-specific-verification); and
- [annotation grammar, encoding, runner-policy, and hosted-runner cases](commands/github-actions-annotations.md#command-specific-verification).

Together these suites must cover:

- every accepted and rejected record delimiter, line boundary, name, and path
  form that affects structural integrity;
- empty, boundary-sized, invalid-encoding, secret-bearing, and protocol-like
  values without diagnostic disclosure or pre-validation stdout;
- target-OS-dependent behavior on POSIX and Windows runners;
- runner parsing and downstream interpretation that can change the effective
  value, ordering, masking, or record count; and
- unsupported concurrency and lifecycle behavior without implying guarantees.

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
