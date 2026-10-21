# Pending Azure hosted smoke

This fixture has not yet been run against Azure. Create a YAML pipeline using
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
timeline API. It does not yet test read-only overwrite enforcement, downstream
job/stage mapping or source-location translation; these are provider effects,
not source-parser guarantees. Review location rendering manually with a
caller-approved real source path before recommending location metadata.

An intentional error issue may mark its step/job as succeeded-with-issues; its
step has `continueOnError`. That alone is not evidence of a passed test. Require
the value verification and final timeline verification steps to succeed in
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
