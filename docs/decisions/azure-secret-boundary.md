# Azure secret boundary discussion

Status: Proposed

## Context

The maintainer deferred secret implementation on 2026-10-24 while PATH proceeds.
This record is the single home for the unresolved secret-boundary discussion;
it does not introduce a command or change the existing non-secret variable
contract. The implementation handoff links here instead of repeating it.

The maintainer agreed to consider lossless escaping, rejection and, where
justified, explicit sanitization. That agreement sets the investigation
direction; this record remains Proposed because the accepted input rules,
interface and protection boundary have not been decided.

## Decision drivers

Provider limitations alone do not justify accepting a value that cannot receive
the protection promised by shoutx. Start with a concrete disclosure path and
the protected value, not a proof over all character sets or an audit of Agent,
.NET or ICU. Reuse existing Azure parser and hosted evidence where relevant;
neither proves secret registration or redaction by itself.

Prefer lossless protocol escaping when it preserves the value and closes the
path. Consider rejection before stdout when it cannot. Explicit sanitization
remains an option when necessary and justified by user value and cost; it is
not prohibited merely because the provider owns the consumer implementation.
Do not silently change a secret or declare it protected merely because an
altered value was registered.

## Questions to resolve before implementation

1. **Original-value protection.** Which accepted values can be registered
   faithfully and actually redacted in the supported log path? Separate
   framing/decoding failures, registration restrictions, and log processing.
   Specify rejection conditions for known unprotectable inputs, including
   whether empty, short, multiline or structured values need special treatment.
   These are investigation categories, not claims of discovered vulnerabilities.
2. **Fragments and representations.** Distinguish a registered secret appearing
   within a larger log line from a fragment of that secret appearing alone.
   Identify concrete workflows that print fragments or transformed values.
   Decide what additional registration, rejection or explicit interface can
   usefully cover; do not register every possible substring or promise all
   future transformations are protected.
3. **Sanitization and identity.** Separate registering extra representations of
   the original value from replacing the actual secret with a sanitized value.
   The latter is meaningful only if the caller can use that same replacement
   at the real consumer. Existing credentials cannot generally be changed by a
   masking writer. Determine the interface, collision/semantic effects and
   value-delivery requirements before adopting any transformation.
4. **Timing and transport.** Input restrictions cannot erase a disclosure that
   happened before invocation. Determine registration ordering and safe input
   delivery requirements. Shoutx must not introduce disclosure through its own
   output framing, diagnostics, validation or failure behavior. Do not treat
   retrospective cleanup as an encoder capability.
5. **Separate operations.** Evaluate mask registration and secret-variable
   assignment separately, including scope, mapping, flags and read-only/output
   interactions. A shared encoder does not establish equivalent consumer effects.
6. **Acceptance evidence.** Define synthetic-secret tests for exact registration,
   absence of extra operations, subsequent log redaction and negative controls.
   Observe the actual consumer effect rather than producer success alone. No
   real credentials belong in fixtures, logs or review inputs.

## Recommended boundary for maintainer approval

This is a proposal, not an accepted command contract. Start with explicit
registration of an opaque value for subsequent ordinary Agent-captured job
stdout/stderr logs. Protect faithful delivery to registration and redaction of
the entire registered value, including when embedded in a longer line. Do not
equate that with redaction of every fragment, every serialization, uploaded
files, arbitrary issue metadata or previously emitted logs.

The [source observations](../compatibility/azure-pipelines.md#secret-source-observations)
support this distinction but do not yet establish hosted secret compatibility.
In particular, the existing parser and variable/issue/PATH results are reusable
infrastructure, not evidence of successful secret registration or secrecy.

### Candidate interface and input rules

Prefer `shoutx azure-pipelines:mask` with bounded, non-terminal stdin only.
No positional secret, raw command/properties, variable flags or implicit
transformations. This avoids introducing an argv route that process inspection
or command logging could expose. The exact interface remains subject to approval.
Use a fixed `task.setsecret` header and the existing Azure lossless encoding;
validate the complete input and expanded record before stdout. Keep the existing
1 MiB raw / 8 MiB record resource ceilings, subject to the consumer-size tests
below; these are not yet claimed Azure acceptance limits. Diagnostics must not
include the value. Successful writing is not an acknowledgment from the Agent.

| Input category | Recommended initial treatment | Reason and remaining check |
| --- | --- | --- |
| Empty, malformed UTF-8, NUL, over producer limit | Reject before stdout | No useful registration or lossless supported text transport |
| Nonempty short values | Candidate acceptance with the job's short-secret threshold explicitly set to zero | Do not impose a six-character minimum merely because Azure allows configuring one; test short ASCII and supplementary values and require the stated consumer setting |
| CR/LF anywhere, including a final producer newline | Reject before stdout | Ordinary logs are processed as lines; registering only the combined original must not be mistaken for protection of separate emitted lines |
| Unicode, spaces, literal escape text and header delimiters | Preserve; candidate acceptance after finite checks | No language allowlist, trimming, normalization or decoration; include whitespace-only values and warn about caller-authorized overmasking |
| Structured single-line value, such as JSON | Treat as one opaque secret, with explicit caller precondition | Full serialized value and independently logged field values are different protected assets; do not claim field coverage from whole-value registration |
| Known derived representation or confidential field | Register separately before use, applying the same input rules | Preserve the original registration; reject an unsupported representation rather than imply coverage |

Prefer the explicit zero-threshold profile over a six-scalar rejection floor: the
inspected short-secret knob defaults to zero, and upstream tests specify both
short-value and whitespace-only masking. These tests are not hosted results.
Require the trusted pipeline/job `variables:` configuration to set
`AZP_IGNORE_SECRETS_SHORTER_THAN: '0'` before the job starts
and test the actual effect; a child's environment is not proof of the Agent's
configuration. This adds an explicit condition to the existing Azure profile.
A six-scalar floor is an alternative that tolerates the wrapper's configurable
short-secret threshold ceiling, at the cost of rejecting useful short secrets;
it is not evidence that default Azure cannot mask them. If short values pass
under the chosen zero-threshold profile, retain them. If they do not, withhold
that acceptance and report the specific restriction for approval rather than
quietly impose six. Neither scalar count nor byte length measures entropy.
If the supported profile cannot protect a candidate accepted input, narrow the
specific rule or withhold that capability; do not waive the failure as merely
an Azure limitation. Record such a finding privately when security-sensitive.

### Fragments, representations and sanitization

For an opaque token printed as `prefix + token + suffix`, register the token;
this remains whole-value coverage. If a tool logs only a confidential JSON field
or emits a base64/URL-encoded value, that field/representation must also be
registered before the tool runs. The initial proposal uses repeated explicit
registrations rather than guessing JSON fields or enumerating substrings.
The workflow author must know these outputs; a writer cannot inspect all future
process behavior. If a needed representation fails validation, stop that use
instead of continuing under a claim of protection.

Rejecting all JSON-looking inputs would prevent legitimate opaque-secret use
without protecting non-JSON fragments. Automatically traversing structured
values adds schema, short-field and overmasking decisions. It is an alternative
for a later explicit interface if a concrete workflow justifies the cost, not
an implicit promise of this registration primitive.

Do not sanitize an existing credential inside a masking writer: registering a
changed credential does not protect the original used by the service. When the
caller controls the logged representation, a deliberately sanitized log value
can prevent that disclosure, but it must be the value actually emitted. For
new caller-controlled credentials, replacement may be useful only when issuance
and the real consumer use that same replacement; collision/semantic effects and
secure delivery need their own interface. No such transformation is proposed
implicitly here. Lossless protocol encoding is distinct from all these changes.

Multiline credentials are a real use case, not abandoned scope: compare rejecting
them in the first primitive with an explicit line-registration mode. The latter
would treat every nonempty emitted segment as caller-authorized for masking,
reject the entire request before output if any segment is unsupported, define CR/LF segmentation and
limits, and test blank lines, overmasking and terminal-boundary behavior. It does
not change the credential. Its extra contract and false-positive cost should be
approved separately; simply escaping a combined multiline value is insufficient
evidence of line-by-line secrecy. It would also mask non-confidential PEM header
lines; no automatic classifier is implied. A caller-selected segment interface
is another option, with additional caller responsibility and interface cost.

### Caller preconditions and operation separation

Deliver bytes through a non-echoing channel to native stdin, with shell tracing
and verbose command logging disabled, including `system.debug=false`. Do not splice secret expressions into
script source, pass secrets via command arguments, use a tee, or capture the
registration wire as a normal artifact. Keep stdout connected to the active
Agent command stream and check exit status before dependent work. Registration
must precede secret-producing processes; require a later task for this initial
supported sequencing contract, and do not race concurrent producers against
registration. Same-task register-then-run, particularly stderr on a separate
reader, is not admitted by a successful stdout write; characterize it separately
before expanding this sequencing contract. Earlier leaks require incident response, not encoding. The trusted
workflow/Agent and normal command processing remain prerequisites; arbitrary
unmasked destinations are not protected by this channel. The caller authorizes
the registered values: attacker-selected masks can hide unrelated log text.

The registration channel itself is sensitive. If parsing or dispatch fails,
the Agent can log command data without having registered it. Fixed validated
framing and the supported decoding/host configuration address the intended
path; they cannot turn an unsupported or failed consumer into a safe sink.
The inspected dispatcher also has error logging and post-processing debug
output. Test registration-step log exposure explicitly, keep debug off in the
initial profile, and do not interpret a producer exit status as consumer success.
This is a concrete framing/registration disclosure path, not an invitation to
audit arbitrary Agent internals.

For Bash, a quoted `printf '%s' "$SECRET"` pipe is the intended no-newline
delivery form, with tracing disabled and failure propagation. For PowerShell,
do not present `$env:SECRET | shoutx ...` as supported byte delivery. The initial
recipe uses a small reviewed helper example reading the environment and writing UTF-8
bytes to the child's redirected stdin (as the existing Python fixture does),
forwarding only native stdout and propagating failure. Both recipes need the
real-shell tests below. Stdin-only therefore carries a Windows ergonomics cost;
an explicit environment-variable-name input could be considered later, without
accepting the secret itself in argv. Rejecting argv cannot undo its prior exposure.
Prefer a documented, tested helper example, not a new shipped executable.
Shipping a helper as product or relying on user-written helpers are alternatives
requiring explicit approval; the latter cannot inherit byte-fidelity evidence
from the tested example without equivalent behavior.

Secret-variable assignment is separate: it introduces name authorization,
read-only state, settable-variable restrictions, mapping and output scope.
The inspected handler also has distinct multiline and escaped-value handling.
Do not add `--secret` to the existing variable command as a shortcut or assume
its scope/effects follow from a successful `task.setsecret` test.

## Finite verification plan

No hosted secret test has run for this proposal. After boundary approval, reuse
the pinned parser harness and the native Ubuntu 24.04 / Windows 2025 fixture;
do not add new OS profiles or dependency-internal proof obligations.

1. **Producer rejection and exact wire:** exercise empty input, scalar lengths
   1–7 (ASCII and supplementary Unicode), invalid UTF-8/NUL, CR/LF/CRLF in the
   middle and at the end, raw cap and cap+1, literal escapes/delimiters, and
   Unicode/space-preserving cases. Assert status, value-free diagnostics and
   empty stdout for every rejected case. Assert a single fixed command and no
   extra operation for every successful case. Test terminal stdin and forbidden
   argv separately: extra operands return usage status 2, empty stdout and no
   operand in diagnostics; bare `--` selects stdin, `-- VALUE` is an error.
   No public production command is added by this design task.
2. **Parser and registration:** extend the upstream parser corpus with the
   fixed event and exact decoded data. This reuses only its parser capability:
   it currently has no task-handler or masker harness. Obtain actual handler/
   registration effects through isolated hosted cases in step 3 instead of
   making a new Agent build harness mandatory. A local handler harness is a
   bounded diagnostic alternative if needed; it entails test-package pinning,
   license/dependency review and fresh state, not a new production dependency.
   Record backend/settings where observable; do not infer them from producer
   culture. Parser equality alone cannot pass the registration gate.
3. **Native hosted effects:** on both existing OS generations, use synthetic
   non-credential-shaped canaries for six isolated cases: one-character ASCII,
   one supplementary Unicode scalar,
   literal escape/delimiter text, leading/trailing spaces, opaque JSON, and an
   original plus explicitly registered derived value. In a later task print
   whole values alone and within fixed harmless prefixes/suffixes to stdout
   and stderr. The expected literal-value replacement is `***`, grounded in
   upstream tests and to be confirmed live: require exactly `PREFIX***SUFFIX`,
   not partial or displaced redaction. Assert exact surrounding text, absence
   of extra commands. For unique long canaries, scan completed job logs for
   original and registration-wire escaped representations, including the
   registration step itself. For short/whitespace cases, incidental characters
   in unrelated setup logs are not identifiable disclosures: require exact
   delimited payload blocks at every fixture emission and absence of the exact
   value-bearing registration record, not a misleading whole-log single-character
   search. This limits what those tests demonstrate; the fixture must emit no
   other secret-bearing output. Include a
   near-limit case in an isolated job to establish or reduce the proposed size
   ceiling. A completed, exactly masked result within a 15-minute job budget
   passes; timeout/Agent rejection leaves the size unsupported and requires a
   separately justified lower ceiling, not an automatic pass. An exposed value
   is a security failure requiring private handling. Observe extra operations
   with a sentinel variable checked in the next task and exact expected issue
   counts in the timeline; unexpected registration-wire text in logs fails.
   Scan every producer issue message for unique canary/wire forms as a separate
   disclosure sink, not just its issue count. For short/whitespace cases require
   the expected empty issue inventory, avoiding ambiguous character searches.
   Keep short/boundary cases isolated from other registrations so
   accidental masking cannot yield a false pass.
4. **Discriminating controls:** in isolated synthetic jobs, omit registration,
   register a different value, and compare original-only with original-plus-derived
   registration. First calibrate the unregistered canary in a clean job: it must
   be visible, or automatic masking makes it nondiscriminating. For derived
   forms, existing encoders may already mask the original-only case; record that
   separately, do not count it as evidence of the additional registration, and
   use an independently chosen synthetic derived value for a discriminating
   registration control. The verifier must detect intentionally unprotected
   values, not require every provider-derived form to leak. Never classify those
   leak controls as positive secrecy evidence. Include an unrelated non-secret
   sentinel which must remain visible. In short/whitespace cases choose markers
   and delimiters that contain neither the registered value nor its installed
   encoder-derived variants; otherwise the control is invalid, not a masking
   failure. Keep expected Agent housekeeping changes separate from the exact
   fixture blocks. Include offline truncated-log, missing-job,
   changed-field and wrong-source/attempt controls. A missing or partial log
   cannot pass. Deliberately visible control values must never be real secrets.
5. **Execution budget and completed-log verifier:** run 11 producer jobs per OS:
   six ordinary cases, one whitespace-only case, one near-limit case, and three
   isolated controls from step 4. That is 22 producer jobs plus one downstream
   verifier job, 23 total, each capped at 15 minutes; not 23 parallel jobs or a
   promised wall time. Build once per OS in its first producer job and pass the
   source-bound native binary via a pipeline artifact to the remaining ten
   jobs, with source/run identity and digest checks; never put secret inputs
   or captured registration wires in that artifact. No extra build jobs are
   counted. A build/artifact failure means incomplete evidence, not skipped
   passing cases. The producer jobs use real Bash/PowerShell delivery,
   the zero short-secret threshold and debug-off settings. Source/producer
   tests cover the wider 1–7 length matrix without multiplying hosted jobs.
   The existing timeline verifier cannot retrieve its own completed job log.
   Add read-only build-log retrieval in the downstream job after all producer
   jobs terminate, including failed controls. Use project-limited job authorization
   scope and least-privilege build-service permissions; this is not a per-API
   token scope. Use only read endpoints for verification and map its token only
   into the verifier script, not producer scripts. Cap each job's aggregate
   logs at 32 MiB and retrieval at six attempts with 15-second request timeouts,
   require matching job/source/attempt and final sentinels, and never save or
   echo raw responses. Missing/truncated data fails verification. Same-task or
   debug-on characterization is a separately budgeted follow-up, not a passing
   inference from this matrix or a prerequisite for the proposed limited profile.
6. **Retained evidence:** retain tested SHA, job/attempt IDs, Agent/image identities,
   result counts and bounded digests/projections, not raw log bundles or actual
   secrets. Confirm producer, parser, registration and hosted results separately.
   Use fresh-state source tests if diagnosing short/multiline behavior;
   do not launch an unbounded hosted input search. A concrete mismatch creates
   a scoped rule/test correction, not an Agent audit.

The matrix is a finite admission plan, not a claim of universal masking. The
current design goal ends with a reviewed proposal and these explicit missing
measurements; product implementation/adoption requires approval and the relevant
tests to pass. Observed backend differences should be resolved at the affected
case or profile condition, not by silently assuming a preferred backend.

## Decisions requested from the maintainer

- Approve or revise the whole-value, subsequent ordinary job-log boundary, with
  explicit separate registration of known confidential fields/representations.
- Approve or revise stdin-only input, zero-threshold short-value support and
  initial multiline rejection; decide whether multiline line-registration belongs in the first
  implementation instead. Retaining a multiline requirement means expanding
  that explicit contract and its finite tests, not silently dropping the case.
- Approve or revise the explicit configuration and later-task sequencing cost,
  Windows input-helper requirement (recommended tested documentation example,
  versus a shipped helper or user-written helper) and 23-job admission matrix. The alternative
  six-scalar floor trades short-value utility for tolerance of threshold changes.
- Keep secret-variable assignment and credential replacement separate unless a
  concrete use case makes either necessary for the first increment.

## Independent review record

The first read-only Fable review on 2026-10-24 completed successfully using
`claude-fable-5-1`, with no denied inspections. Accepted findings led to an
explicit registration-channel disclosure path and debug-off/later-task
conditions; correction of the short-value recommendation after checking the
zero-default knob; clearer whitespace evidence; explicit Windows delivery cost;
defined argv errors and caller authorization; and a budgeted downstream
completed-log verifier instead of implying the existing parser/timeline tools
already cover handlers and completed logs. Exact redaction and failure outcomes,
line-mode segment authorization and post-approval SSoT edits were also clarified.

Backend behavior beyond the inspected source remains a required future
measurement, not a new gate requiring all backend executions before presenting
this design. This preserves the separation between proposal and implementation
verification.

The follow-up Fable review completed successfully on the same date with the
same model and no denied inspections, finding no blocking design flaws. Its
nonblocking clarifications were incorporated: knob precedence and pipeline
setting, timeline message checks, non-colliding short-value markers, build-once
artifact reuse within the 23-job count, accurate token-permission wording,
consistent profile naming, and helper-delivery options. Source observations
remain distinct from unexecuted tests. These clarifications do not change the
proposed security boundary and do not require another review round.

## Decision gate

Before implementing secret support, present the maintainer with the protected
asset, concrete attack paths, accepted/rejected inputs, any explicit
transformation, caller preconditions and finite verification plan. The boundary
is not yet agreed; do not convert this discussion into a blanket exclusion for
all provider masking limitations. Keep accepted contracts in the command
specification and observations in the compatibility record after approval.
At adoption, move accepted input/CLI rules out of this proposal into
`docs/commands/azure-pipelines.md`, replacing the current no-masking statement;
add the registration-channel disclosure path to the Azure threat inventory;
update the design profile's unresolved-secret status and conditions. Keep only
rationale/alternatives here, avoiding two normative input tables.

New concrete attack details must follow SECURITY.md and confidential durable
tracking, not public issues or this public discussion record. Keep the public
record at the level of design questions and agreed policy.

## References

- [Existing Azure contract](../commands/azure-pipelines.md)
- [Existing Azure evidence](../compatibility/azure-pipelines.md)
- [Azure logging commands](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops)
- [Security reporting](../../SECURITY.md)
