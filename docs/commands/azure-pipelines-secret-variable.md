# Azure Pipelines secret variable

Status: Design approved by the maintainer on 2026-10-27; implementation in progress,
not admitted. This specification owns the CLI, input rules and admission plan;
the [decision](../decisions/azure-secret-variable.md) owns rationale. Existing
commands and the published release are unchanged.

## Intended use and interface

Pass a runtime-created credential to a later task without composing a raw
logging command or placing the value in argv:

```text
shoutx azure-pipelines:secret-variable [--output] [--read-only] NAME
```

Only bounded non-terminal stdin supplies the value. NAME follows the existing
[Azure variable name contract](azure-pipelines.md#validation-and-limits), not a
secret-bearing operand. The caller selects and authorizes the name and flags.
There is no value operand, `--secret` toggle, raw property option or line mode.
Use the existing variable option-position grammar, with exactly one operand;
`--` terminates options. Unknown/duplicate flags, extra operands and terminal
stdin are usage failures (2), with empty stdout and fixed diagnostics. Help and
version in option position return immediately without reading stdin. Invalid
NAME is an input failure (1); never echo it in diagnostics. All operand/flag
validation precedes acquisition. Extra operands, including invalid OS text,
are usage errors without attempting to decode or print a possible secret.

Default scope is later tasks in the current job. `--output` explicitly requests
named-step output semantics, including mapping into dependent jobs/stages.
Secret propagation across those scopes is a required admission hypothesis, not
established by the source's timeline secret flag. If it fails, return the design
for approval rather than ship a silently same-job-only output option.
Output mode sets the qualified step/name, not an additional plain NAME binding;
an existing plain binding remains independent and must not be read as this result.
`--read-only` requests Azure's read-only flag; neither flag creates a new access
control mechanism. Both may be combined. Callers configure a named producer
step, authorized dependency mappings and explicit per-task environment mappings
for consumers under the [candidate profile](../design.md#proposed-secret-variable-profile).
Never interpolate the secret into shell
source or dump the environment. No automatic environment export is promised.

## Candidate input and wire contract

Validate bounded raw acquisition (1 MiB), strict UTF-8, NUL, a 16 KiB (16,384-byte)
semantic value cap, nonempty input,
CR/LF, and macro syntax in that order. Reject CR or LF anywhere, including a
final producer newline; do not enable Azure's unsafe multiline-secret knob.
Reject the two-byte ASCII sequence `$(` at any position, even without a closing
`)`, since later variable expansion can change the
credential depending on job state. This is a deliberate conservative boundary
for variable-valued credentials, not a Unicode allowlist. Literal `$`, parentheses,
percent escapes, delimiters, spaces/tabs and other Unicode remain data.
Do not trim, consume producer framing, normalize, case-fold or sanitize.
Single-character and whitespace-only values are permitted subject to the
profile and explicit acceptance of their overmasking cost.

Prepare exactly one record, with fixed properties and ordering:

```text
##vso[task.setvariable variable=NAME;isSecret=true;isOutput=BOOL;isReadOnly=BOOL;]VALUE
```

BOOL is the selected flag's lowercase boolean. Encode VALUE with the existing
[Azure wire escaping](azure-pipelines.md#wire-contract), then append LF. Validate
the complete input and checked record length before output; the producer's
8 MiB record cap applies. Every input/limit/encoding failure exits 1 with empty
stdout and value-free diagnostics. Do not add a preliminary `setsecret` record:
one invocation requests one assignment, not a hidden multi-command transaction.
Output I/O failure may leave a prefix; producer success is not Agent acknowledgment.

The raw acquisition cap is separate from the semantic cap. The proposed semantic
ceiling leaves room below native environment-string limits; it is not a service
capacity guarantee. Actual receiving-path admission is still required, including
aggregate environment overhead. A failure requires an evidenced design change,
not a silent cap reduction or a parser-only claim of consumer delivery.

## Protection and deployment conditions

The [proposed threat boundary](../threat-model.md#proposed-secret-variable-boundary)
separates structural integrity, registration-channel confidentiality and delivery
from caller/provider authorization. Reuse the existing native
[Azure profile](../design.md#azure-pipelines-profile) and its mask prerequisites.
The [proposed profile addition](../design.md#proposed-secret-variable-profile)
owns their application to receiving jobs. This is a candidate extension, not a statement that the
existing mask admission covers secret-variable assignment.

Deliver stdin bytes without echo, argv, tee, captured-wire artifacts or a shell
text-mode conversion. Reuse the proven Bash byte-stream recipe; adapt and test
the existing Windows stream helper for the candidate command and public NAME/
flags without exposing the value in arguments. This remains a documented helper,
not a new credential client. Stop dependent work on producer failure. The
profile's clean-task condition is not automatically enforced by a successful
shell exit or Azure's ordinary success condition: warnings need not fail a task.
Any producer warning/error means the value may be unmasked and must not be
logged or used; the post-approval guide must make that operational limitation
explicit. The writer does not inspect issue inventories or hidden Agent state.
A blocked/rejected Agent command has no assignment or original-value masking
guarantee; do not proceed to log/use the attempted value.

The intended secrecy claim covers the registration channel and subsequent
ordinary Agent-captured stdout/stderr containing the complete value, within the
admitted profile. It does not cover pre-registration output, arbitrary fragments,
transforms, uploaded files or task-specific telemetry. Other confidential
representations need explicit prior mask registration. Secret storage and
authorized mapping are Azure operations, not forbidden disclosures; task logs
and issue messages are distinct sinks. In particular, structured secret output
metadata must not be dumped into a verifier's logs or artifacts.

## Finite implementation admission plan

The approved implementation goal executes this finite plan. Reuse the
existing parser, mask completed-log verifier and native fixtures rather than
building an Agent test framework.

1. **Producer and parser.** Test exact properties and decoded name/value for all
   four flag combinations; argv/terminal/grammar rejection; invalid names,
   UTF-8/NUL, empty values, CR/LF/CRLF and final boundaries, macro prefixes at
   each position (including unclosed sequences), semantic cap/cap+1 and raw
   cap/cap+1. Include `$`, parentheses, literal escapes,
   delimiter and nested-command-looking data as parser-only cases, Unicode,
   one-character and whitespace-only values. Assert exact status/diagnostic,
   empty stdout on every rejection, one record on success, checked sizing and
   stdout failure behavior. Directly verify Windows byte delivery. Wrong flags,
   extra properties/records and changed data must fail negative controls.
2. **Same-job positive effects.** On each existing native OS, use six isolated
   jobs: ordinary single-line credential; Unicode plus literal escapes and inert
   delimiters; one ASCII character; one supplementary scalar; whitespace-only;
   and size admission. Default assignment is followed by an unmapped task and
   a task with an explicit environment mapping. Require absence from automatic
   environment export by looking up only the expected public environment names
   (not dumping the environment), exact mapped values and exact later stdout/stderr masking
   inside calibrated markers. Inspect completed registration logs and producer
   issues as well as later logs. On Windows compare strict UTF-8 re-encoding of
   the environment string without BOM/normalization; on Linux compare UTF-8
   bytes directly. Use no real credentials or live nested commands in plaintext
   log probes. In the ordinary job test initial read-only assignment only.
3. **Explicit output effects.** Add one source job, one dependent job in the same
   stage and one dependent-stage job per OS. Exercise `--output` with and without
   `--read-only`, named-step same-job mapping and dependency/stage mapping.
   Check exact mapped values and later-task masking on both sides, no automatic
   environment export, and unrelated sentinel values unchanged. The source must
   retain the secret flag; inspect structured output metadata only in memory.
   Missing mappings must not be misrepresented as access-control enforcement:
   the workflow author can explicitly map authorized outputs. Include a value
   with literal escapes and Unicode, independent of the ordinary same-job sample.
4. **Size admission.** Use generated stdin, never oversized argv/environment,
   in each OS's isolated size job. Test the semantic cap through the actual
   receiving path, with ASCII and supplementary-Unicode values in separate
   assignment/consumer tasks. Capture cap+1 rejection without forwarding it.
   Escaped wire expansion is a separate parser/resource test, not an environment
   capacity factor. Failure or timeout leaves the cap unadmitted and requires
   a scoped proposal for approval, not automatic fallback. No size search.
5. **Negative controls.** Add one isolated control job per OS, using synthetic
   non-secret-shaped values which are visibly unmasked before registration.
   Require the completed-log verifier to identify omission and wrong-registration
   probes as unprotected, not as positive secrecy evidence. Rejection probes
   capture stdout privately and never forward it to the Agent even if broken.
   Calibrate short/whitespace marker blocks without overlapping registered values.
   Before any registration, assign a distinct synthetic value with the existing
   non-secret writer: automatic environment export and visible later output must
   distinguish it from the secret cases. Within this control job, test read-only
   overwrite using a separate synthetic value and task; mark its expected
   rejection issue explicitly. Configure that task with continue-on-error and
   run the bounded follow-up checks even after its expected failure, without
   treating the resulting success-with-issues as a positive admission result.
   The read-only value
   must remain unchanged for its flag to be admitted. Do not require a blocked
   new value to be masked or visible: its registration can be partial and these
   controls are not positive secrecy evidence. Any observed value-bearing
   rejection diagnostic is a security finding, handled privately before admission.
   Do not add a hosted disallowed-name probe to ordinary unrestricted script
   tasks: without configured restrictions that checker allows assignment.
   The source-derived rejection limitation is retained, but that out-of-profile
   control is not counted as executed evidence.
   Offline mutations must catch missing/truncated logs, wrong SHA/job/attempt,
   missing consumer, changed/truncated mapped value, wrong secret/output flags,
   extra operation, unexpected issues and partial masking. Compare bytes inside
   the consumer without printing values or their hashes; report only fixed
   pass/fail plus public case identifiers.
6. **Budget and evidence.** The plan is 10 jobs per OS (six same-job, three
   output, one control) plus one downstream completed-log verifier: 21 total,
   each at most 15 minutes. Build once per OS and distribute only the reviewed
   binary and identity/digest manifest, before registering values. Use the existing
   project's limited job authorization and read-only verification endpoints;
   expose the token only to the verifier. Reuse the mask verifier's bounded
   retrieval, exact source/job/attempt matching and missing-data failure policy.
   Long canaries require scans for original and wire-escaped forms; short values
   require exact fixture blocks and absence of value-bearing command records,
   not an ambiguous whole-log character search. Unexpected producer issues fail.
   Retain identities and bounded outcomes, never raw secret-bearing logs, wire,
   structured output values or low-entropy secret digests.

## Admission decisions and implementation boundary

Source evidence supports the intended routes, not measured secret-output
propagation or capacity. Implementation must resolve exact delivery, secrecy in
each destination job, read-only behavior and size admission using the finite
plan. A mismatch is a failed gate: correct a demonstrated fixture error or
present a scoped contract/profile change for approval. Never silently drop an
output scope, narrow Unicode support, add a hidden masking command or accept
partial redaction to obtain a pass. Concrete new disclosure details follow
SECURITY.md and private follow-up.

After design approval, implement only this dedicated writer, scoped helper/
tests, profile admission and user guide. No credential minting/storage client,
secret discovery, automatic fragment extraction, multiline replacement scheme,
or audit of unrelated Agent internals is included. Existing non-secret variable
and mask behavior stays unchanged. Publication and merge require later direction.
