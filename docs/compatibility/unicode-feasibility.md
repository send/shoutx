# Unicode adoption feasibility audit

Status: In progress; not adoption evidence or a support declaration.

This audit follows the [research scope](../decisions/github-actions-unicode-scope.md)
and [completion criteria](../test-plan.md#unicode-adoption-completion-criteria).
It does not change CLI acceptance. Observations below were inspected on
2026-10-04; unknown premises remain unknown, not passing checks.

## Same-job observations after PR #74

The successful [run 37177815281](https://github.com/send/shoutx/actions/runs/37177815281)
executed the four package/live jobs at attempt 1. Its source head was
`a5cbc93c53f47255c8e6210466d2ef83242d9430`; the reports record tested PR merge
`b2fb07df49a10afa70e704fcf398ca3f82de91ca`. This supersedes the initial
cross-job/missing-row inventory below for baseline hosted availability.

The [retained projection](evidence/unicode-feasibility-37177815281.json)
preserves selected observations from the four package reports, package-native
reports and matched live reports, plus SHA-256 digests of all 12 source reports.
The author checked source reports and jobs metadata before projecting them;
the projection is not a signed attestation and has no committed generator.
Package-side job/attempt association is an explicit inference from the named
artifact and workflow at the source head, checked against the Actions jobs API;
the package report itself has no job ID/attempt fields. The projection retains
that provenance and the source job timestamps separately. It deliberately excludes full
logs, full annotation responses, corpora, rule/mapping payloads and secrets.

| Target selector | Associated package/live job ID (provenance above) | Image/version | Package ICU (Invariant and en-US) | Duration |
| --- | --- | --- | --- | --- |
| ubuntu-22.04 | 111364128021 | ubuntu22 / 20260927.309.1 | 70.1.0.0 | 7m15s |
| ubuntu-24.04 | 111364128056 | ubuntu24 / 20260927.320.1 | 74.2.0.0 | 6m17s |
| macos-15 | 111364128037 | macos15 / 20260907.0337.1 | 76.1.0.0 | 6m47s |
| windows-latest | 111364128060 | win25-vs2026 / 20260925.250.1 | 72.1.0.4 | 9m20s |

All four live reports record Runner 2.337.0, eight masks and 30 annotations.
The package reports' image/version, run and tested SHA agree exactly with the
live reports; the package/native architectures agree with the corresponding
live X64/ARM64 identities. Hosted verifier job 111365444318 succeeded in 22s.
These timings establish headroom only for this successful run, not for the
worst-case retry paths or future images. Successful full-log and annotation
checks show that preceding job state did not spoil this finite experiment;
they do not prove absence of all prior command effects or problem matchers.

### Per-culture feasibility status

| Target | Culture | Baseline/image observation | Package ICU/settings observation | Live consumer linkage | Effective-data acquisition |
| --- | --- | --- | --- | --- | --- |
| ubuntu-22.04 | Invariant | Matched | Observed | Unverified | Not yet evaluated on this row |
| ubuntu-22.04 | en-US | Matched | Observed | Unverified | Not yet evaluated on this row |
| ubuntu-24.04 | Invariant | Matched | Observed | Unverified | Not yet evaluated on this row |
| ubuntu-24.04 | en-US | Matched | Observed | Unverified | Not yet evaluated on this row |
| macos-15 | Invariant | Matched | Observed | Unverified | Not yet evaluated on this row |
| macos-15 | en-US | Matched | Observed | Unverified | Not yet evaluated on this row |
| windows-latest | Invariant | Matched | Observed | Unverified | Not yet evaluated on this row |
| windows-latest | en-US | Matched | Observed | Unverified | Not yet evaluated on this row |

"Matched" describes run/job/image availability, not observed live culture.
Every live report still records null culture and globalization backend.
Package observations do not turn either unobserved live culture into a measured
one. The archive and managed/runtime digests describe the package probe, not
the live Worker; native library paths are not native binary hashes. Source
digests bind inspected inputs, not reproducible source-to-binary derivation.
These are checked-out working-tree byte digests. The Windows source digests
were independently recomputed from the recorded git commit: all match CRLF
conversion except `unicode-candidate.json`, whose attributes force LF and whose
digest matches LF. This explains those cross-OS digest differences without
assuming code drift. Annotation-response digests are not job identities and
need not differ between rows executing the same corpus; their values here
match the corresponding source reports. The hosted verifier owns exact
semantic comparison of the bounded annotations, not an across-OS assertion
of byte-identical entire API responses.
An API recheck on 2026-10-04 found 30 annotations in each Linux/Windows job
and 31 on macOS: the latter includes a GitHub service notice about ARM64
capacity/queue times in addition to the 30 corpus annotations. Matching by
corpus title, all corpus fields agree across the four responses. The extra
service notice explains why the macOS entire-response digest differs; it is
not an extra corpus effect or a Unicode mismatch.
Root/tailoring, normalization/break input completeness and future reader
portability remain unverified. The next obligation is consumer linkage, not
more accepted-character sampling. No positive feasibility verdict is made.

## Initial baseline availability (historical inventory)

The existing successful [CI run 37175079175](https://github.com/send/shoutx/actions/runs/37175079175),
attempt 1, tested `c6aa1bddd7ed23dc1568a8924704c5494c9ae140`.
Its four package evidence reports and three hosted-boundary reports have
`status: passed`. The package/native probes explicitly selected both Invariant
(serialized culture name `""`) and `en-US`; they did not measure live culture.

| Target | Package job ID | Recorded image/version | Package ICU, both cultures | Matching live boundary job ID |
| --- | --- | --- | --- | --- |
| Ubuntu 22.04 x64 | 111355933985 | ubuntu22 / 20260927.309.1 | 70.1.0.0 | Missing |
| Ubuntu 24.04 x64 | 111355933916 | ubuntu24 / 20260927.320.1 | 74.2.0.0 | 111355933939 |
| macOS 15 ARM64 | 111355933952 | macos15 / 20260907.0337.1 | 76.1.0.0 | Missing |
| Windows x64 | 111355933938 | win25-vs2026 / 20260925.250.1 | 72.1.0.4 | 111355933923 |

The Ubuntu 24.04 and Windows live reports record Runner `2.337.0`, matching
the baseline version and their package jobs' image versions and architectures.
Their version equality does not attest the live binary or globalization state.
The package jobs for Ubuntu 22.04 and macOS 15 also record Runner `2.337.0`
in their setup logs, so baseline hosted execution was available on those
selectors in this run. Those jobs did not run the live boundary corpus.
The existing `macos-latest` boundary job 111355933944 records **macos26** /
20260907.0351.1, ARM64, Runner `2.337.0`; it cannot close the macOS 15 row.

All eight package row/culture combinations observed ICU, a matching cached
search collator, an external break iterator, and these collator attributes:
`french=16`, `alternate=21`, `caseFirst=16`, `caseLevel=16`,
`normalization=16`, `strength=2`, `hiragana=16`, `numeric=16`.
These are package-probe observations, not effective root/tailoring acquisition
or live Worker settings. The 78.1 local root reader has not been validated
against these four generations.

## Remaining feasibility work

PR #74 added the existing live corpus to the package jobs; the same-job
observations above close the initial missing-row inventory, but not the
consumer-state obligations. The producer policy and corpus are unchanged.

1. Preserve each subsequent same-job observation with source identities.
   Baseline and process-start availability are now recorded on all four rows;
   the [module experiment](#hosted-module-metadata-result) also records partial
   native file identities. Active configuration and binding remain unverified.
2. Evaluate the source/configuration or direct-observation path connecting
   the live consumer to each explicit culture's implementation/settings,
   including the server-supplied culture input. This is currently unverified
   for **both cultures on every row**, including the observed startup names.
3. For each row/culture with a justified acquisition-target connection, evaluate acquisition of native
   identities, effective root/tailoring, normalization/break inputs and format
   support. No costly mapping expansion is justified by the package counts.
4. Add any subsequent observation to the durable record and independently
   review the final per-row/per-culture verdict.

This is an in-progress audit, not a completed feasibility verdict. It neither
drops missing rows nor treats unavailable evidence as proof of impossibility.

## Consumer-state observation route under investigation

The [parser note](github-actions-workflow-command-parser.md#culture-diagnostic-observation-route)
owns the inspected source mechanism and diagnostic limitations.

The observer implements an in-job allowlisted projection of that
diagnostic input and named on-disk files, locating Worker through its ancestor
chain and matching job context before extracting a culture. The
[test plan](../test-plan.md#hosted-worker-startup-input-feasibility-observation) records its output
limits. Its first hosted result is recorded below. Trustworthy job/process
correlation and later thread state still need evaluation. Even a process-start
culture record would not alone prove effective
native mappings, loaded runtime identity or the other culture's transfer argument.

### First hosted diagnostic observation

Successful [run 37180154098](https://github.com/send/shoutx/actions/runs/37180154098),
attempt 1, tested source head `64ffc6737b4cd78db632ef127b5d59b355971c68`
through merge `d4a9a6109e14d4a9649a13a0e76a3d086fc7054c`.
The [retained evidence](evidence/hosted-worker-37180154098.json) contains the
four limited observer reports, package comparison fields, live boundary
reports, original report hashes and Actions job metadata. It excludes raw
diagnostics and vendor payloads. Like the earlier projection, this is an
author-selected record, not a signed attestation or a committed generator.

| Selector | Actions job ID | Diagnostic job input | On-disk comparison |
| --- | --- | --- | --- |
| ubuntu-22.04 | 111370934814 | `system.culture` absent | All 7 named files match package |
| ubuntu-24.04 | 111370934876 | `system.culture` absent | All 7 named files match package |
| macos-15 | 111370934787 | `system.culture` absent | All 7 named files match package |
| windows-latest | 111370934726 | `system.culture` absent | All 7 named files match package |

All four reports have `observed-job-message-without-culture`, null
`cultureInput` and `cultureInputStatus: absent`; none measures Invariant.
The matching live reports retain Runner 2.337.0, the exact same run/tested SHA
and image identities, eight masks and 30 annotations. All package reports
passed; the hosted verifier job 111372188999 also succeeded. The image versions
are unchanged from the earlier inventory, but this is a separate observation,
not an inference from image equality alone.

The comparison checks each observer `onDiskSha256` entry against the same
job's package `package-bin-sha256.json`; its seven corresponding entries are
retained separately as `package.onDiskSha256` so this comparison remains
inspectable after artifact expiry. They include Worker, parser assemblies,
CoreLib, CoreCLR and runtime/dependency configuration. It closes the narrow
question of whether those named files can be identified and matched on disk
in this run.
It does not attest loaded bytes, native ICU, process startup options or
processing-thread state. Numeric Actions job IDs are correlated by artifact
selector/RID and the workflow, not equated with diagnostic timeline GUIDs.
The collector's unique-context, trusted-ephemeral-job assumptions remain in
force; its logs are not authenticated against modifications by the job user.
Both cultures on every row therefore remain unverified in the feasibility table.

The next narrow observation uses the source route for the earlier `Culture:`
line described in the parser note. The added extraction and its negative
controls follow the
[test plan](../test-plan.md#hosted-worker-startup-input-feasibility-observation).
Its first hosted result is recorded below. This does not require debug
logging or reading process environments. A source/configuration argument for
transfer to later execution and to the other culture remains a separate step;
the scope decision's [acquisition-target work order](../decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements)
governs any subsequent native-data acquisition.

To reproduce the recorded comparison, download run 37180154098 into a new
directory. Each `hosted-worker-input-SELECTOR-RID/hosted-worker-evidence.json`
is paired with `runner-package-evidence-SELECTOR-RID/runner-package-evidence/`
`evidence.json` and `package-bin-sha256.json`, and with
`hosted-boundary-evidence/package-matched/SELECTOR.json`. Check their SHA-256
against the retained `sourceReportSha256` entries before comparing fields.
All named observed file digests must equal the corresponding package manifest
entries; missing entries are not matches. Original Windows report hashes
include CRLF bytes. Job metadata can be rechecked through the run/jobs APIs.
Artifact expiry does not erase the retained observations, but their hashes
cannot recreate missing original files or prove a new image has the same state.
For an independent package-side check after artifact expiry, download the
public archive at `package.archive.url`, verify its recorded size and SHA-256
before extraction, then hash the seven named `bin/` files and compare with
`package.onDiskSha256`. These names are the top-level bin entries used by
`extract_bin` and the manifest in `scripts/test-runner-package.py`.
This route depends on continued availability of those exact archive bytes;
it reproduces package identities, not the expired live process or diagnostics.

### Process-start culture observation

Successful [run 37181563090](https://github.com/send/shoutx/actions/runs/37181563090),
attempt 1, ran the schema-v2 observer at source head
`4452bd90d06525b15f51a313197aa48b00fbba4f`, tested merge
`eafeab08b56450778a875055372f039e56011090`.
The [retained record](evidence/hosted-worker-37181563090.json) preserves all
four observer and matched live reports, selected package/native observations,
both sides of the named file comparison, API job metadata and 20 source-report
hashes. It uses the same author-selected projection and trusted-ephemeral-job
limitations as the preceding record; it is not a signed attestation.

| Selector | Actions job ID | Observed process-start Culture name | Job culture input | Package ICU, both explicit cultures |
| --- | --- | --- | --- | --- |
| ubuntu-22.04 | 111375026211 | Empty string | Absent | 70.1.0.0 |
| ubuntu-24.04 | 111375026251 | Empty string | Absent | 74.2.0.0 |
| macos-15 | 111375026184 | `en-US` | Absent | 76.1.0.0 |
| windows-latest | 111375026167 | `en-US` | Absent | 72.1.0.4 |

All four `startupCultureStatus` fields are `observed`; every
`cultureInputStatus` is `absent`. The empty Linux names are observations of
`CurrentCulture.Name`, not measurements of ICU-backed Invariant comparison.
The parser note's [default-locale/backend caveat](github-actions-workflow-command-parser.md#culture-diagnostic-observation-route)
still applies. The en-US startup names do not measure the later processing
thread or transfer to Invariant. Both cultures remain unverified for consumer
linkage on every row.

The same-job package probes passed under both explicit cultures and retained
the same eight collator attributes as the earlier inventory, matched cached
search collators and external break iterators. Those facts describe the probe,
not the live Worker. All seven named on-disk Worker/runtime files again match
the package manifest. All four live reports passed with Runner 2.337.0,
eight masks and 30 annotations; verifier job 111376371285 succeeded. The
reported images, run, tested SHA and architectures match the corresponding
package and observer identities. Neither successful effects nor matching
on-disk identities fill the native-state gap.
An API recheck of this run's macOS job found 31 annotations, including one
GitHub service notice about ARM64 queue capacity in addition to the bounded
corpus. Its whole-response digest therefore differs from rows without that
notice; this is not inferred from the earlier run's notification.

Reproduction follows the preceding procedure with run 37181563090. Also retain
and hash each package `probe.json`; the projection selects only explicit
cultures, ICU identity and bounded native-setting fields, not mapping/context
payloads. The original Windows reports use CRLF bytes. The public archive
route rechecks package digests after artifact expiry, not live state.

### Next consumer-linkage obligation

The next consumer-linkage obligation is identifying relevant runtime/native
modules and configuration in the Worker, separately from its child probe.
Read-only module metadata supplies the limited hosted evidence below.
The collector and limits are specified in the
[test plan](../test-plan.md#hosted-worker-module-metadata-feasibility-observation).
Such metadata does not by itself prove active backend,
effective root/tailoring or processing-thread culture. Costly mapping expansion
remains gated on the acquisition-target connection defined by the scope decision.

The proposed macOS route uses the text-file metadata returned by `lsof`, not
`vmmap` on the live Worker. In Apple's published
[`process_text`](https://github.com/apple-oss-distributions/lsof/blob/7a8a1b2a3c0f35c30a5fcd0927f31d441c3e5255/lsof/dialects/darwin/libproc/dproc.c)
this route queries `proc_pidinfo` region/vnode metadata. This is a source-route
inference, not attestation of the hosted utility's build. A local self-process
smoke returned no system ICU text-file entry after explicitly loading ICU;
shared-cache omission is therefore a real availability concern, not proof
that ICU is absent. The prior local `vmmap` smoke could see its system ICU
mapping, but its potential target interaction was not established, so it is
not enabled against a live Worker. Neither smoke closes a hosted row.

On Windows, the documented `Process.Modules` API and inspected fixed .NET
[`module enumeration`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Diagnostics.Process/src/System/Diagnostics/ProcessManager.Win32.cs)
use VM-read/query rights to obtain loader metadata. The collection does not
retain those internal structures. On Linux, the
[`maps` interface](https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html)
is also access-controlled and has ambiguous pathname/deleted markers.
All platforms retain the distinction between an observed module/file and
proof that comparisons use it. System ICU presence, particularly on macOS,
is not discriminating evidence of the .NET globalization mode.

The package probe now records separate bounded on-disk hashes for its selected
ICU common/international paths, so future Worker-side observations can be
compared rather than relying on equal path strings. Historical projections
do not have those hashes. ICU data-library and globalization-shim hashes have
no package-probe counterpart in this experiment; effective-data identity remains
unverified even when common/international hashes match.
A separately mapped globalization shim is recorded
when found, without assuming it is the binding used by CoreLib or that it
must be mapped separately. Shared-cache-only files and inaccessible paths
remain explicitly unverified.

### Hosted module metadata result

Successful [run 37184265280](https://github.com/send/shoutx/actions/runs/37184265280),
attempt 1, tested source head `9aa3887c9e5efbfa811198c8f46981e366a0640b`
through merge `2e1aeed897f1a2c6014dfa238048d5b35216d256`. Its
[retained projection](evidence/hosted-worker-modules-37184265280.json) preserves
the four startup-input and module reports, selected package fields and all four
package-matched live reports, with SHA-256 hashes of 24 original reports.
It is an author-selected projection, not a signed attestation or a committed
generator. Job association uses the workflow/artifact selector and Actions jobs
API, not equality between diagnostic GUIDs and numeric Actions job IDs.

| Selector / job ID | Worker module metadata | Package comparison, both explicit cultures |
| --- | --- | --- |
| ubuntu-22.04 / 111382850276 | CoreCLR, ICU common/international/data 70.1 filenames | Common/international disk hashes match |
| ubuntu-24.04 / 111382850325 | CoreCLR, ICU common/international/data 74.2 filenames | Common/international disk hashes match |
| macos-15 / 111382850331 | CoreCLR only | System ICU disk hashes unavailable; no native ICU match established |
| windows-latest / 111382850362 | CoreCLR and `icu.dll` | Combined ICU disk hash matches both selected library roles |

All four module reports have `observed-module-metadata`. That status means at
least one selected entry, not a complete module inventory. All four report the
optional standalone globalization shim as not observed. Linux map device/inode
matches each opened selected file; Windows/macOS do not make that identity
check. Linux data-library hashes have no package counterpart here. The macOS
ICU omission is consistent with the previously observed `lsof` limitation,
but does not prove its cause or that ICU was absent. Neither an ICU filename
nor module presence measures the active .NET backend/version.

The startup reports again record absent `system.culture`; process-start names
are empty on Linux and `en-US` on macOS/Windows. All **nine** selected
Worker/parser/SDK/runtime disk files match the corresponding package manifest,
including the newly added `Runner.Sdk.dll` and `Sdk.dll`. CoreCLR hashes in the
module report also equal those manifests. This adds disk identities for the
inspected output-event path, not a source-to-binary derivation or loaded-byte
attestation. Historical seven-file reports remain seven-file evidence.

Each live report passed with Runner 2.337.0, eight masks and 30 annotations.
Run/tested SHA, resolved image version and architecture (case-insensitive name
comparison: `Arm64` / `ARM64`) match its paired
package report. Image versions are the same as the first table above; their
actual values are independently retained in this projection. The package ICU
versions remain 70.1.0.0, 74.2.0.0, 76.1.0.0 and 72.1.0.4 respectively, under
both explicit cultures. The observed collator attributes, cached-search match
and external-break presence also remain the package observations recorded
above. Verifier job 111384257500 passed (07:05:48–07:06:05 UTC). These finite
effects do not measure arbitrary-suffix safety or live culture/backend.
An API recheck for this run found an additional `.github` ARM64-capacity service
notice on macOS, retained separately in the projection. This is consistent with an
extra non-corpus entry; whole-response digest equality across OSes is not a
requirement. The successful verifier checks the corpus semantics separately.

The projection also retains actual/compiled **break-iterator** rule digests
and source/resource digests for both cultures. `CollationProbe.Run` obtains
`actualRuleSha256` from `RuleHash(GetBreaker(search))`; these are not collation
root/tailoring digests. Equality of these rule hashes must not be used to claim
equal effective collator mappings. The probe has no retained resolved-collator
locale field; that remains a separate acquisition question.
The projection's `breakRules` fields come from each source culture's
`collationObservation` object, not a source object named `breakRules`.
`ruleResourceSha256` identifies the original JSON bytes, so cross-platform
equality is not required. Its Windows difference is retained without assigning
an unverified cause; compare each row's source bytes independently.

Reproduce by downloading run 37184265280 into a fresh directory. Pair
`hosted-worker-modules-SELECTOR-RID/hosted-worker-modules.json`,
`hosted-worker-input-SELECTOR-RID/hosted-worker-evidence.json`, package
`evidence.json`, `package-bin-sha256.json`, `probe.json`, and the
`hosted-boundary-evidence/package-matched/SELECTOR.json` report. Check the six
original byte digests for each row before comparing fields (Windows CRLF is
significant). For each Linux/Windows culture and common/international role,
verify equality of the observed package hash and the same-name observed Worker
module hash. For macOS, reproduce the reported unknown: both roles have unavailable
status and null hash, and the selected Worker modules contain CoreCLR only.
This reproduces the unavailable result; null hashes are not matches.
Recheck run/attempt/job metadata through the API.

### What these alternatives can and cannot close

The feasibility table's eight consumer-linkage verdicts remain unverified;
the module experiment does not promote either culture to verified. The exact
remaining issue is the relation between the identified on-disk implementation
and the comparison state used by the live Worker, including transfer to the
other explicitly tested culture. It is not another shortage of string samples.

| Evaluated route | Evidence obtained | Remaining limitation / next condition |
| --- | --- | --- |
| Same-job package plus live effects | Matching baseline, image, architecture and finite effects on all four rows | Does not identify comparison culture, backend or effective data |
| Existing Worker diagnostic input/startup record | Absent job culture input and separate startup names on all rows | Does not measure output-processing thread state or culture transfer |
| Selected disk and module metadata | Nine package file matches; native ICU file matches on three rows | Presence does not prove active binding; macOS ICU remains unobserved |
| Pinned source/configuration reasoning | Culture default/async propagation and output-event path identified; runtime config retained | Must justify dependencies, relevant startup overrides and each culture's effective settings/data, rather than infer them from absence of a source assignment |
| Local macOS metadata alternatives | Self-process `vmmap` can expose ICU where `lsof` did not | Target interaction/hosted suitability not established; no live Worker invocation authorized by this experiment |

The retained runtime configuration does not set globalization-invariant or NLS
mode explicitly. This alone is not a mode observation: the inspected runtime
also reads AppContext/environment inputs, and the package harness deliberately
sanitizes its child environment. Equal runtimeconfig bytes therefore cannot
establish equal startup inputs. The parser note owns the
[source route and its limitations](github-actions-workflow-command-parser.md#culture-diagnostic-observation-route).

The next decision is whether a reviewed source-and-configuration argument can
discharge these specific gaps under the existing
[trust assumptions](../threat-model.md#trust-assumptions).
Direct loaded-memory attestation is not mandated as the only
method; conversely, an unproven assumption cannot silently become a fact.
If that argument cannot be justified, report the missing inputs for maintainer
direction under the scope decision's stop rule. Instrumenting or replacing the
Worker, collecting memory/full environments, removing macOS or accepting only
the observed startup culture are not silent fallbacks.

Effective-root/tailoring and normalization/break data acquisition on these
four generations remains gated by identifying and justifying the acquisition
target for each culture, following the scope decision's work order. None of
those target connections has yet been completed here.
The current 78.1 reader has not been applied to 70.1, 74.2, 76.1 or 72.1 here.
The module/file experiment neither proves those formats accessible nor proves
them inaccessible. This audit is still incomplete; no positive feasibility,
Unicode acceptance or release conclusion follows from the successful CI run.

### Source/configuration linkage assessment

The [test plan](../test-plan.md#sourceconfiguration-acquisition-target-checks) owns the
conditional per-culture claim and its four acquisition-target checks. None is discharged
by this run's module observation. The nine-file matches support only the disk
identity component; loader/source correspondence, dependency behaviour,
startup selection and native/locale route remain incomplete. The next bounded
package-side check is a direct-member-reference scan of the assemblies resolved
by the observed `deps.json`; no such scan is claimed in this retained run.
A subsequent [offline inventory](managed-runtime-references.md) records those
selected references and manifest matches for all three package RIDs.
It narrows dependency inspection without discharging the live configuration,
execution-context or native-selection obligations.

#### Startup-selection inputs to resolve

This is the run-specific input assessment, not a second verification gate.
The fixed runtime's `GlobalizationMode` files linked in the parser note read
the following switches. The retained runtimeconfig explicitly sets only
`PredefinedCulturesOnly=false` among these inputs. AppContext/environment and
native loader behaviour are not measured by that file.

| Input / source route | Linux rows | macOS row | Windows row |
| --- | --- | --- | --- |
| `System.Globalization.Invariant` / `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT` | Open: empty startup name ambiguous; ICU mappings support a source inference only if their origin is justified | Open source inference: default-locale route returns Invariant in invariant mode; observed `en-US` excludes that route only after earlier explicit culture overrides are accounted for | Same conditional exclusion as macOS |
| `System.Globalization.UseNls` / `DOTNET_SYSTEM_GLOBALIZATION_USENLS` | Fixed Unix source returns false; not a target selector | Fixed Unix source returns false; not a target selector | Open: outside invariant mode, fixed source selects NLS when requested or default system-ICU loading fails; selected app-local library-load failure is fatal, not an NLS fallback. `icu.dll` presence alone does not exclude another loader |
| `System.Globalization.AppLocalIcu` / `DOTNET_SYSTEM_GLOBALIZATION_APPLOCALICU` | Open selection input; observed system-file matches narrow the possible resolved outcome | Open: this branch has not been excluded, so the system-ICU path has not been established | Open selection input; combined system-file match narrows the observed modules, not necessarily the binding |
| `CLR_ICU_VERSION_OVERRIDE` in fixed `pal_icushim.c` | Version-selection input; mapped filenames/hashes identify observed files but still need the loader-origin argument | Linux-style version-override branch is not the target's system load route | Linux-style version-override branch is not the target's system load route |
| `System.Globalization.PredefinedCulturesOnly` / corresponding `DOTNET_SYSTEM_GLOBALIZATION_PREDEFINED_CULTURES_ONLY` | File value false observed; fixed boolean helper prefers an available AppContext switch over environment. Whether that file supplies the unchanged effective switch and how it affects the selected mode remain unverified | Same | Same |

This table is the runtime selection layer, not an exhaustive effective-data
input list. ICU data loading (including any applicable `ICU_DATA` route),
platform library resolution and application-level AppContext changes need
their respective fixed-source/data arguments. The known package environment
sanitization does not establish the Worker's values. No new live environment
read, raw memory access or behavioural corpus change is part of this report.

## Reproduction of this inventory

For the latest module observation (run 37184265280), use the six-report
[module-result procedure above](#hosted-module-metadata-result), including the
explicit macOS unavailable result. The following procedure describes the older
baseline inventory, not the current module report.

For that baseline inventory, use `gh run download 37177815281 --repo
send/shoutx --dir NEW_DIRECTORY`. Compare each selector's
`hosted-boundary-evidence/package-matched/SELECTOR.json` with its
`runner-package-evidence-SELECTOR-RID/runner-package-evidence/evidence.json`
and `probe.json`. `shasum -a 256` on those files must match that row's
`sourceReportSha256` entries in the retained projection. Read source run/job
metadata with the Actions run/jobs APIs; `run_attempt` is the source job's
attempt, not inferred from the verifier retry. The tested merge SHA comes
from the reports and is distinct from the REST run's head SHA.

The projection retains observed fields after artifact expiry, not the source
files themselves. Their hashes do not recover missing files or ICU bytes.
To repeat the experiment on an available image, use the workflow at the
recorded source commit and the pinned package acquisition instructions in
[the package note](runner-package-runtime.md#reproduction-and-retained-evidence).
A new run can test current identities but cannot recreate an unavailable
historical hosted image. Such drift must not be reported as this observation.

For the historical initial inventory:

Download artifacts from the run above with `gh run download 37175079175
--repo send/shoutx --dir NEW_DIRECTORY`. Each
`runner-package-evidence-OS-RID/runner-package-evidence/` directory contains
`evidence.json` (run, image, package identity) and `probe.json` (explicit
cultures/native observations). `hosted-boundary-evidence/*.json` records
the separate live observations. Query the run's jobs API for job IDs and
attempts. Read only the setup-log identity fields for the two missing
boundary rows; do not retain full job logs in this repository.

The historical initial inventory's reports have the existing 30-day retention;
their temporary download is not durable closure evidence. The later same-job
projection above supersedes this inventory for baseline availability, without
claiming to retain the historical reports themselves.
