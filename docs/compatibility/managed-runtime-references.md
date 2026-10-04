# Published Runner managed reference inventory

Status: partial source-analysis evidence, not reference-correctness closure or
proof of deployment applicability.

This supports the [feasibility audit](unicode-feasibility.md) and the test plan's
[acquisition-target checks](../test-plan.md#sourceconfiguration-acquisition-target-checks).
It narrows package dependency inspection; it does not change a culture/OS
verdict, CLI acceptance or release eligibility.

Under the [2026-10-05 scope revision](../decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements),
this inventory supports analysis of the reference package's normal path, not
mandatory live-deployment linkage. The observations and limitations below are
unchanged; absence of direct references still does not prove absence of every
possible runtime effect.

## Observation and provenance

The [retained report](evidence/managed-references-v2.337.0.json) records a local
metadata-only scan on 2026-10-04 of the three pinned Runner v2.337.0 packages.
The scanner ran on macOS ARM64 with SDK 8.0.424 / .NET 8.0.30, as recorded in
each `scannerHost`. Linux and Windows PE files were read, not executed. This
is not a hosted macOS 15, Linux or Windows execution observation.

The verified archive identities are retained, along with the dependency-file
hash, each scanned asset's hash, selected method names, MemberRef counts and
matches. Scanner source byte hashes identify the code used; the base commit
alone does not include that then-uncommitted code. Every scanned asset and
`Runner.Worker.deps.json` was compared to the corresponding package manifest
from [run 37184265280](https://github.com/send/shoutx/actions/runs/37184265280),
attempt 1. The record preserves those manifest hashes and source job IDs.
`manifestSourceSha256` is SHA-256 of the raw `package-bin-sha256.json` bytes in
artifact `runner-package-evidence-SELECTOR-RID`, directory
`runner-package-evidence/`. The producer is `scripts/test-runner-package.py`.
The wrapper's comparison flags are author-checked results, not scanner output.
The original manifests have 30-day artifact retention; after expiry this
record preserves the compared asset digests and result, not an independently
recheckable copy of the historical manifests. Their hashes cannot recover them.
Fresh scans remain reproducible from the pinned archives but do not recreate
that historical hosted comparison.

| Package | Managed runtime assets scanned | Compared hosted package jobs |
| --- | --- | --- |
| linux-x64 | 209 | ubuntu-22.04 111382850276; ubuntu-24.04 111382850325 |
| osx-arm64 | 209 | macos-15 111382850331 |
| win-x64 | 210 | windows-latest 111382850362 |

All scanned file/dependency hashes match those manifests. The two Linux rows
use the same archive; this does not make their ICU generations or live states
equal. Input archives, complete library bytes and full IL are not retained.
This is an author-checked research record, not a signed build attestation.

## Selected references and interpretation

| Assembly | Observed selected MemberRef names | Inspection consequence |
| --- | --- | --- |
| Runner.Common | CultureInfo default-thread culture/UI-culture setters | Inspect the existing HostContext culture route |
| Runner.Worker | IHostContext.SetDefaultCulture; Environment.SetEnvironmentVariable | Distinguish job culture initialization from ordinary process environment writes |
| Runner.Sdk | Environment.SetEnvironmentVariable | Inspect the keys written, not merely the method name |
| Azure.Core | AppDomain.SetData | May forward to AppContext; cannot dismiss as an unrelated declaring type |
| System.Net.Http | ExecutionContext.SuppressFlow | Inspect the asynchronous call path; reference presence does not identify the stdout loop |
| System.Net.NetworkInformation, Linux only | ExecutionContext.SuppressFlow | Additional Linux dependency path to inspect |

No selected unresolved parent labels were observed in these packages. The
fixture suite separately exercises an unresolved generic parent so it is not
silently discarded. No other selected MemberRef names were observed in this
enumeration; that is **not** absence of every culture/configuration mutation.
The helper's [scope limitations](../../tests/runner-package/managed-references/README.md)
apply, including limited execution-context API coverage (`SuppressFlow` only).
Internal CoreLib behaviour remains part of the fixed-source argument.

The existing [parser note](github-actions-workflow-command-parser.md#processing-culture-connection-still-to-establish)
owns the Runner culture/default and stdout-event source route. Preliminary
source follow-up for the additional references found:

- Pinned Runner [RunnerWebProxy](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Sdk/RunnerWebProxy.cs)
  writes HTTP/HTTPS/no-proxy variables; [JobExtension](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/JobExtension.cs)
  writes the process tracking ID. These identified uses are not observations
  of the live Worker's initial environment.
- Fixed .NET [AppDomain.SetData](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/AppDomain.cs)
  forwards to AppContext.SetData. `Runner.Worker.deps.json` recovered from each
  pinned archive identifies Azure.Core 1.55.0 (the inventory retains its hash,
  not library-version fields); the corresponding official tag resolves to
  `2a044b2970cd3688c393cfb559f4850cb085e85d`. In that source,
  [AzureEventSource](https://github.com/Azure/azure-sdk-for-net/blob/2a044b2970cd3688c393cfb559f4850cb085e85d/sdk/core/Azure.Core/src/Shared/AzureEventSource.cs)
  uses SetData with `_AzureEventSourceNamesInUse` for event-name deduplication,
  not a globalization key. Version/tag correspondence is a source inference,
  not a reproduced build or exhaustive callsite census.
- The fixed runtime's [HttpConnectionPool](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Net.Http/src/System/Net/Http/SocketsHttpHandler/HttpConnectionPool.cs)
  uses a scoped SuppressFlow while creating an authority-expiry timer.
  [NetworkAddressChange.Unix](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Net.NetworkInformation/src/System/Net/NetworkInformation/NetworkAddressChange.Unix.cs)
  does so for a timer and launching its socket event reader. These are inspected
  examples, not yet a complete dependency/call-context argument.

This inventory makes the remaining dependency investigation bounded and
inspectable. It does not establish the effective startup switches, active ICU
binding, actual processing culture, culture transfer or effective native data.
Both cultures in all four feasibility rows remain unverified.

## Reproduction

Verify archive size/SHA-256 against `tests/runner-package/pins.json` before using
the existing package harness's flat `bin/` extractor. Run the
[helper and fixtures](../../tests/runner-package/managed-references/README.md)
with the recorded SDK; compare its source hashes first. Use only immutable,
private package extracts. Match the output's dependency and per-file digests
to the appropriate run-37184265280 package manifest, and compare the selected
reference arrays and asset counts with the retained report. The helper's host
description may differ on a new machine; that does not relabel the original
scan as a new hosted execution.

Missing files, unsupported dependency shapes or failed scans are unavailable
evidence, not successful empty inventories. Report hashes or a changed archive
cannot reconstruct missing original package bytes. No vendor payload upload or
new process/environment inspection is authorized by this experiment.
