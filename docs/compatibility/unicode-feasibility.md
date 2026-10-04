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

1. Review the retained same-job evidence projection and its source identities.
   It covers all four rows without treating setup logs alone as boundary tests.
2. Evaluate the source/configuration or direct-observation path connecting
   the live consumer to each explicit culture's implementation/settings,
   including the server-supplied culture input. This is currently unverified
   for **both cultures on every row**, including the two image-matched rows.
3. For rows with a defensible connection, evaluate acquisition of native
   identities, effective root/tailoring, normalization/break inputs and format
   support. No costly mapping expansion is justified by the package counts.
4. Add any subsequent observation to the durable record and independently
   review the final per-row/per-culture verdict.

This is an in-progress audit, not a completed feasibility verdict. It neither
drops missing rows nor treats unavailable evidence as proof of impossibility.

## Consumer-state observation route under investigation

The [parser note](github-actions-workflow-command-parser.md#culture-diagnostic-observation-route)
owns the inspected source mechanism and diagnostic limitations.

The in-progress observer implements an in-job allowlisted projection of that
diagnostic input and named on-disk files, locating Worker through its ancestor
chain and matching job context before extracting a culture. The
[test plan](../test-plan.md#hosted-worker-startup-input-feasibility-observation) records its output
limits. It has synthetic offline tests but, as of this draft, no hosted result.
Availability, trustworthy job/process correlation and later thread state still
need evaluation. Even a startup culture record would not alone prove effective
native mappings, loaded runtime identity or the other culture's transfer argument.

## Reproduction of this inventory

For the current observation, use `gh run download 37177815281 --repo
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
