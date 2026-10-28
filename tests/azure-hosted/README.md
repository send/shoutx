# Azure hosted smoke

## Secret variable admission

`azure-secret-variable.yml` and `secret-steps.yml` implement the approved
[finite admission plan](../../docs/commands/azure-pipelines-secret-variable.md#finite-implementation-admission-plan).
Queue an exact, reviewed full commit SHA without parameter overrides. Configure
project-limited job authorization before the first run; the CLI's new-pipeline
default can be collection-wide. Only the final verifier receives the job token.
Use the existing GitHub read connection and native Azure profile.

The pipeline expands to 21 jobs with a 15-minute cap each. Per OS, the ordinary
job builds and publishes only a source-bound binary before registration. Other
jobs download that binary and verify its digest and source/run identity. Secret
input files contain only public synthetic samples, are created in the temporary
job directory and are not uploaded. Bash and PowerShell invoke the documented
stdin helpers without placing the values in argv or capturing successful wire.
The PowerShell helper is exercised with a native byte sink before packaging.

Each assignment has a separate unmapped task and two explicitly mapped tasks,
one for stdout and one for stderr. Consumers compare exact values before logging
calibrated samples. Output assignments additionally cross a job and a stage;
the final verifier inspects the secret flag and value in source timeline metadata
only in memory. Control jobs deliberately expose synthetic calibration, omitted
and non-secret samples; those are not positive secrecy evidence. The isolated
readonly overwrite must actually be emitted, produce an issue, and leave the
original value unchanged in a later task.

The completed-log verifier reuses the mask verifier's bounded, read-only API
retrieval. It rejects missing jobs/tasks/logs, wrong source/job/attempt, incomplete
blocks, unexpected issues or output metadata, changed values and partial masking.
It prints only public identities and counts, never raw logs, wire, secret output
metadata or value hashes. A fixed failure label identifies the failed gate without
revealing the value. Its final success, not individual green producer tasks,
is required for admission; results belong in the compatibility record.

Run the offline controls before queueing:

```sh
python3 -B tests/azure-hosted/test_secret_stdin.py
python3 -B tests/azure-hosted/test_secret_verify.py
```

## Build metadata admission

`azure-metadata.yml` is a dedicated manual fixture for the two metadata writers.
Use a trusted reviewed revision without parameter overrides. It changes only
its own synthetic run number and tags. Linux then Windows run serially, with
four emission/verification pairs per OS, to avoid races on the shared number.
Each job configures percent decoding and the body-based tag API explicitly.

Baseline verification runs before any metadata emission on each OS. Cases cover
ordinary labels, Unicode/literal escapes/reserved tag punctuation, and the
255-UTF-16-unit cap and number boundary spaces. Rejected input stays captured
off the Agent stream.
After each producer task, read the exact number and full tag collection from the
build API and compare the next-task number too. The token is mapped only to
read-only verifier tasks; use project-limited job authorization. The verifier
rejects redirects, bounds responses/retries, checks build/source identities,
and outputs only hashes, counts and observed Agent/image/job identities.

Run `python3 -B tests/azure-hosted/test_metadata.py` for offline missing, extra,
changed and identity-mismatch controls. These tests run in GitHub CI and in each
hosted job. The verifier also checks producer timeline tasks for clean success,
without warnings or issues. Inspect all job/step results before recording
admission; an emitted command or local parser pass alone does not establish
backend acceptance. The compatibility record owns admission status.

## Mask registration admission

The separate manual pipeline `azure-mask.yml` implements the
[finite mask admission plan](../../docs/commands/azure-pipelines-mask.md#finite-verification-plan).
It has 32 producer jobs and one completed-log verifier, with 15-minute job caps.
The first producer builds once per OS and publishes only the native binary and
its source/run/digest identity before registration. Other producers reuse it.
Only the downstream verifier receives the project-scoped read token; configure
project-limited job authorization and least-privilege build-read permissions
before queueing a trusted revision. Do not supply unreviewed parameter overrides.

Producer values are public synthetic test data. Omission/calibration controls
deliberately leave specified values visible and are never positive secrecy
evidence. All other expected payloads are compared exactly; short/whitespace
values use delimited blocks, while long registered values also use whole-job
disclosure searches. Raw completed logs are held only in verifier memory, capped
at 32 MiB per job, and are never saved or printed. Its final report contains
source/run/job/attempt/image/Agent identities, binary/log digests and counts.

Run offline tests before queueing:

```sh
python3 -B tests/azure-hosted/test_mask_stdin.py
python3 -B tests/azure-hosted/test_mask_cases.py
python3 -B tests/azure-hosted/test_mask_verify.py
```

Passing offline tests or defining this pipeline does not establish masking on
Azure. Record actual results in the compatibility record before admission.

## Existing variable issue and PATH smoke

Results and tested identities live in the
[compatibility record](../../docs/compatibility/azure-pipelines.md).
Create a YAML pipeline using
`tests/azure-hosted/azure-pipelines.yml` and manually queue a reviewed source
revision. Automatic push/PR triggers are disabled. Do not run attacker-selected
branches or queue-time overrides with OAuth access.

Prerequisites:

- Azure DevOps Services project, GitHub repository read connection, and a
  Microsoft-hosted free parallel-job allocation.
- The named Ubuntu/Windows images, Rust/rustup, Python 3 and PowerShell Core.
  Cargo uses the repository-pinned Rust toolchain; no published v1.0.0 binary
  contains these new commands.
- Project-scoped build identity with permission to read its own build timeline.
  The token is mapped only into the final read-only verification step. No PAT,
  subscription secret or token is printed or written to a report.

The fixture checks multiline variable fidelity in the next step, named-step
output mapping, read-only registration's initial value, absence of an injected
sentinel variable, and warning/error type, text, code and counts through the
timeline API. Location steps pass the absolute path of the checked-out
`README.md`, line 1, column 3, then verify Azure's relative source path,
coordinates, Code category and formatted message for both severities.
Inspect the hosted UI as well before recording location rendering evidence.
The fixture does not test read-only overwrite enforcement or downstream
job/stage mapping; these remain provider effects, not source-parser guarantees.

PATH steps create caller-owned fixture directories and copy the native shoutx
binary as a uniquely named lookup probe. Repeated registrations must produce
exactly the expected ordered prefix plus the saved original PATH in the next
task, with no additional entry. Unicode and literal-escape directory names
exercise decoded byte fidelity; distinct ASCII directories exercise ordering.
The next step checks executable discovery and runs only that trusted fixture.
Agent culture/backend remain unobserved; exact-repeat results do not establish
portable duplicate equivalence.
Capture the baseline and verify effects using direct `PythonScript@0` tasks:
shell startup may independently prepend its own directory to PATH. Keep the
actual command emission in Bash (Linux) / PowerShell Core (Windows). This
separates Agent PATH effects from shell-startup edits rather than allowing
unexpected entries in the verifier.

An intentional error issue may mark its step/job as succeeded-with-issues; its
step has `continueOnError`. That alone is not evidence of a passed test. Require
the value, PATH/executable and final timeline verification steps to succeed in
both jobs, and inspect the whole run for other failures. Missing timeline data,
wrong attempts or mismatched issues fail the verifier.

Record the reviewed source SHA, run URL/attempt, actual Agent and image
identities and observed results in the compatibility record. A missing identity
must be resolved before declaring the hosted gate complete. Do not treat a
configured YAML file or an offline verifier test as hosted evidence.

Run offline verifier checks with:

```sh
python3 -B tests/azure-hosted/test_smoke.py
```
