# Azure Pipelines mask registration

Status: implemented, with scoped hosted admission recorded in the compatibility evidence;
unreleased and not in v1.0.0. The [design profile](../design.md#azure-pipelines-profile)
owns applicability; [compatibility evidence](../compatibility/azure-pipelines.md)
owns observed results. The [decision](../decisions/azure-secret-boundary.md)
owns rationale and alternatives.

## Interface

`shoutx azure-pipelines:mask [--each-line]` accepts bounded non-terminal stdin
only. No positional value, raw properties, variable flags or implicit transforms
are accepted. `--` ends options; bare `--` and `--each-line --` select stdin.
Any operand after `--`, including `--each-line`, is a usage error (2).
Unknown options, duplicate flags and all operands (including malformed OS text)
are usage errors with empty stdout and fixed value-free diagnostics.
Help/version in option position return immediately without reading stdin;
they do not validate subsequent tokens. Terminal stdin fails with usage status 2;
shared read/I/O handling applies. No secret is accepted in argv.

## Validation and line selection

Apply validation in this order: bounded raw acquisition (1 MiB), strict UTF-8,
NUL rejection, then mode/segment/count checks. All validation, checked length
arithmetic and complete buffer construction precede stdout. Every rejection
exits 1 with empty stdout, except the usage failures above. Diagnostics contain
no value, segment index, length or count.

Default mode requires a nonempty value with no CR or LF anywhere, including a
final producer newline. Whitespace-only, short and Unicode values are data;
there is no trimming, language allowlist, normalization or decoration.

With `--each-line`, consume CRLF as one boundary, then standalone CR or LF.
Other Unicode characters remain data. Ignore only zero-byte segments, including
leading/internal/trailing empty segments. Reject if no nonempty segment remains.
Space/tab-only segments are nonempty and preserved. Keep every nonempty segment
exactly, in encounter order, including duplicates; at most 1,024 nonempty
segments are allowed per invocation. Empty segments do not count. A single-line
input produces one entry in either mode. Do not register the combined original
as an additional entry.

For example, `alpha\r\n\r\nbeta\n` registers alpha then beta;
`alpha\nalpha` registers two equal entries; `\n\r\n` fails.
This option selects mask entries, not a replacement credential. Callers retain
the original bytes; shoutx does not return a reconstructed or sanitized value.

## Wire and resource limits

For each selected value emit exactly `##vso[task.setsecret]DATA` followed by
LF, with no properties or added BOM. Apply the existing
[Azure escaping table](azure-pipelines.md#wire-contract) to DATA.
The decoded ordered records must equal the selected values exactly, with no
extra operations. Default mode emits one record; line mode emits the explicitly
selected batch. Cap the entire batch, including all headers/LFs, at 8 MiB.

Count and validate all segments, then calculate the checked aggregate size
before allocating the output buffer. The raw/count limits and maximum sixfold
encoder expansion imply accepted input cannot reach 8 MiB; retain the defensive
aggregate cap and verify the bound/arithmetic. Limits are per invocation, not
a bound on accumulated masks in a job. No new production dependency is needed.

A write failure after output starts can leave a prefix and some registrations.
Neither one prepared buffer nor producer status 0 promises atomic Agent
processing or acknowledgment. These producer ceilings are not established
Azure service limits; admission requires the limit tests below.

## Protected values and caller responsibilities

Within the design-owned mask profile, register complete values/lines before
later ordinary Agent-captured stdout/stderr uses them, including occurrences
inside longer lines. This does not cover arbitrary fragments, transformations,
uploaded files, arbitrary issue metadata or earlier logs. Known confidential
fields or representations require separate explicit registration before use;
if they cannot be registered under this contract, stop that use rather than
claim protection. Structured single-line input is opaque: registering a JSON
document does not register its fields.

Line mode does not hide blank-line counts, boundaries or ordering, nor promise
protection for substrings, differently wrapped text, escaped-newline renderings
or an encoded whole credential. Do not silently sanitize an existing credential:
registering a changed value does not protect the original used at its service.

All nonempty lines, including non-secret headers, short values and whitespace,
are caller-authorized masks. Identical unrelated log text may be hidden.
No automatic secret classifier omits headers. A mask is not a command
neutralizer for arbitrary later process output.

Deliver bytes without echo, argv exposure, tracing, tee or captured-wire
artifacts, and propagate failure before dependent work. Keep native stdout
connected directly to the active Agent stream. Safe byte transport examples
must use Bash's quoted builtin printf or the tested BOM-free Windows helper,
not PowerShell's text pipeline. Large inputs require a bounded byte stream,
not assumptions about environment/argv capacity. Secure acquisition remains
caller-owned. Helper examples are documentation, not a new shipped executable.

Secret-variable assignment remains separate; do not add a secret flag to the
existing variable writer or infer its effects from this registration command.

## Input delivery examples

These examples require the [mask profile](../design.md#azure-pipelines-profile)
and registration in a separate earlier task. See the compatibility record for
tested identities and results.
Do not enable shell tracing or print rejected input.

For a bounded value already securely acquired in Bash, the quoted builtin
`printf` does not append a newline. Propagate either pipeline failure:

```bash
set -euo pipefail
set +x
printf '%s' "$TOKEN" | shoutx azure-pipelines:mask
```

For larger inputs, stream from a trusted acquisition process or an already
securely provisioned file rather than moving the value into argv/environment:

```bash
set -euo pipefail
set +x
shoutx azure-pipelines:mask --each-line < "$SECURE_INPUT_FILE"
```

The [PowerShell helper](../../tests/azure-hosted/mask-stdin.ps1) is a tested-example
source, not an installed shoutx executable. Copy/source it from a trusted pinned
revision. It writes a supplied stream directly to the child's stdin BaseStream,
inherits stdout/stderr and throws a fixed diagnostic on failure. It does not
secure the source file or stream itself:

```powershell
$ErrorActionPreference = 'Stop'
Set-PSDebug -Off
. ./mask-stdin.ps1
$stream = [IO.File]::OpenRead($env:SECURE_INPUT_FILE)
try {
    Register-ShoutxMask -Binary (Get-Command shoutx).Source -InputStream $stream -EachLine
} finally { $stream.Dispose() }
```

The helper's [byte-fidelity test](../../tests/azure-hosted/test_mask_stdin.py)
uses a native stdin sink, including BOM-like data, mixed boundaries, invalid
bytes and a 1 MiB stream; it separately checks child failure propagation.
Windows execution of that test is required before adopting the example.

## Finite verification plan

For compatibility maintenance, reuse
the pinned parser harness and the native Ubuntu 24.04 / Windows 2025 fixture;
do not add new OS profiles or dependency-internal proof obligations.

1. **Producer rejection and exact wire:** exercise empty input, scalar lengths
   1–7 (ASCII and supplementary Unicode), invalid UTF-8/NUL, CR/LF/CRLF in the
   middle and at the end, raw cap and cap+1, literal escapes/delimiters, and
   Unicode/space-preserving cases. Assert status, value-free diagnostics and
   empty stdout for every rejected case. Assert a single fixed command in default
   mode, or the exact ordered segment records in line mode, with no extra
   operation. Cover mixed boundaries, leading/repeated/trailing boundaries,
   blank-only rejection, whitespace retention, duplicate order, one-line parity,
   1,024 and 1,025 nonempty segments, and invalid UTF-8/NUL in the final segment
   after otherwise valid segments. Include boundaries immediately around the raw
   cap, an over-cap input containing invalid UTF-8, and an over-count input with
   a late invalid UTF-8/NUL byte; assert the fixed diagnostic selected by the
   validation order, not merely status 1. Directly test the Windows input helper's
   exact byte delivery with no added BOM using a synthetic stdin-capturing stub.
   Count empty segments separately from the operation limit. Assert the
   aggregate expansion bound and injected output failure without promising
   rollback. Test option duplication/placement, help/version without stdin reads,
   terminal stdin and forbidden argv separately: extra operands return usage
   status 2, empty stdout and no
   operand in diagnostics; bare `--` selects stdin, `-- VALUE` is an error.
   The producer tests are separate from hosted admission.
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
   not partial or displaced redaction. Assert exact surrounding text; this is
   an indirect helper-fidelity check, while step 1 directly checks input bytes.
   Include a literal `%` in the escape case. Percent decoding must be enabled
   as required by the Azure profile;
   otherwise the registered escaped value can differ from the original. A
   different complete replacement token fails the exact expectation but is
   diagnosed separately from exposed secret content; do not silently accept it.
   Assert absence of extra commands. For unique long canaries, scan completed job logs for
   original and registration-wire escaped representations, including the
   registration step itself. For short/whitespace cases, incidental characters
   in unrelated setup logs are not identifiable disclosures: require exact
   delimited payload blocks at every fixture emission and absence of the exact
   value-bearing registration record, not a misleading whole-log single-character
   search. This limits what those tests demonstrate; the fixture must emit no
   other secret-bearing output. Include a
   near-limit case in an isolated job to establish or reduce the selected size
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

   Add four isolated line-mode positive jobs per OS: (a) synthetic PEM-shaped
   LF input with terminal newline, obviously synthetic non-secret headers
   (`SHOUTX SYNTHETIC BLOCK`, not a real private-key label), repeated body lines
   and a short ASCII/base64-like final body line;
   (b) mixed CRLF/CR/LF input with leading/internal/trailing empty segments,
   Unicode and literal escapes/header delimiters; (c) short Unicode and tab-only
   segments with non-colliding markers; (d) 1,024 distinct nonempty segments at
   the raw cap, with a raw-cap+1 and 1,025-segment rejection probe in the same job.
   Each positive job prints the original line layout and each complete segment
   separately inside markers on later-task stdout/stderr. Require exact masked
   nonempty segments and preserved empty boundaries in normalized log records;
   define the log transport's CR/LF normalization separately from producer-byte
   equality. Check every segment, including the first and last, not only samples.
   Run rejection probes before positive registration, capturing their stdout
   locally and never forwarding it to the Agent even on defective acceptance.
   Reject probes must show empty captured stdout locally; log only pass/fail,
   never captured wire. Scan registration-step logs and issues as above, including
   each distinct long segment and its wire form. For short/tab entries use exact
   fixture blocks and the empty issue inventory, not whole-log character scans.
   Test known non-secret headers becoming masked and unrelated text staying
   visible; that demonstrates the acknowledged overmasking tradeoff. These jobs
   use Bash on Ubuntu and PowerShell Core on Windows, not both shells per OS,
   with the documented delivery recipes and byte-for-byte
   input fixtures with CR preserved (not shell text-mode reconstruction).
   Inside each line-mode positive job, before registration, run a small,
   separately delimited unregistered non-secret framing probe (no extra jobs) to
   determine how each task host delivers blank/CR boundaries; freeze the expected
   log-record projection before checking secret blocks. Do not accept arbitrary
   whitespace trimming or missing payload records as transport normalization.
   Use trusted generated stdin for cap-sized cases, not environment variables.
   Command-delimiter examples must not contain a live nested logging-command
   prefix in later plaintext emissions: a mask is not a command neutralizer,
   and a harmless text prefix alone need not disable command scanning. Reserve
   actual nested-prefix injection cases for producer/parser tests; hosted output
   uses inert delimiters while retaining the sentinel-operation checks.
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
   Add one isolated line-mode omission control per OS: register all but a chosen
   distinct synthetic segment, print all segments later and require precisely
   that segment to remain visible. Choose it to avoid overlap with other entries
   or their encoder variants. Offline mutations must also detect a missing last
   registration, duplicated/wrong/reordered decoded records, partial masking,
   unmasked first/last segment and an unexpected operation. Keep negative-control
   outcomes distinct from positive secrecy evidence.
   In that control job, first print unregistered synthetic blocks covering the
   positive jobs' header/body/short/tab shapes, including their actual canary
   values, and require visibility before any registration. Those intentionally
   visible blocks are control evidence only; never use real key labels/material.
   Then register the omission-case subset and check the later-task result.
   Limit permitted plaintext to those exact control blocks; scan the subsequent
   registration step and post-registration blocks independently. Automatic
   masking of a calibration value invalidates that case, requiring replacement
   with a discriminating synthetic value, not a false pass.
5. **Execution budget and completed-log verifier:** run 16 producer jobs per OS:
   six ordinary cases, one whitespace-only case, one near-limit case, and three
   original isolated controls, plus four line-mode cases and one omission control.
   That is 32 producer jobs plus one downstream verifier job, 33 total,
   each capped at 15 minutes; not 33 parallel jobs or a
   promised wall time. Build once per OS in its first producer job and pass the
   source-bound native binary via a pipeline artifact to the remaining fifteen
   jobs, with source/run identity and digest checks; never put secret inputs
   or captured registration wires in that artifact. No extra build jobs are
   needed; publish the binary artifact before any registration step. No other
   files from the producer workspace belong in it. Workload timeouts, including
   the 1,024-entry case, leave the selected cap unadmitted; propose a lower cap
   for approval with a bounded retest instead of relaxing the secrecy check.
   A build/artifact failure means incomplete evidence, not skipped
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
   inference from this matrix or a prerequisite for the selected limited profile.
6. **Retained evidence:** retain tested SHA, job/attempt IDs, Agent/image identities,
   result counts and bounded digests/projections, not raw log bundles or actual
   secrets. Confirm producer, parser, registration and hosted results separately.
   Use fresh-state source tests if diagnosing short/multiline behavior;
   do not launch an unbounded hosted input search. A concrete mismatch creates
   a scoped rule/test correction, not an Agent audit.

The matrix is a finite admission plan, not a claim of universal masking.
Implementation is approved; compatibility admission requires these tests to pass. Observed backend differences should be resolved at the affected
case or profile condition, not by silently assuming a preferred backend.
