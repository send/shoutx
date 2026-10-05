# Stdout Unicode policy integration evidence

The command specifications own acceptance, and the
[decision record](../decisions/stdout-unicode-acceptance.md) owns rationale.
This file records observations, not an independent guarantee.

## Data-start candidate

The JSON input in `tests/unicode-policy-probe/start-candidate.json` identifies
the retained root and GCB digests. It contains 1,105,522 starts in 341 ranges;
its SHA256 is `14c8cfe5230d780ad64ec43f5c29c89863d1462ee47c90da390b1f9300273c93`.
The independent data observations retain their original qualifications in
[root-generation evidence](unicode-root-generation-evidence.md) and
[search-state evidence](reference-search-reset.md). No new native proof is claimed.

Run [37359624610](https://github.com/send/shoutx/actions/runs/37359624610) at
commit `5fa93ca34c220d9955825416c9660df8425a8dca` completed on 2026-10-06 JST.
The harness verified the pinned Runner2.337.0 package and loaded runtime8.0.30
and parser/CoreLib identities. Each row was run separately under Invariant and
en-US: 4,422,088 start checks and 72 metadata checks per culture, no mismatches.

| Host | Image | Observed ICU |
| --- | --- | --- |
| Ubuntu22.04 | 20260927.309.1 | 70.1.0.0 |
| Ubuntu24.04 | 20260927.320.1 | 74.2.0.0 |
| macOS15 | 20260907.0337.1 | 76.1.0.0 |
| Windows latest | 20260925.250.1 | 72.1.0.4 |

Every candidate scalar was checked with two suffixes and two command types.
This does not enumerate arbitrary suffixes or establish Worker effects.
The JSON generation data and the measured consumer identities are distinct:
matching generation data alone does not identify the running consumer.

## Contrary and pending evidence

The local macOS26/runtime8.0.30/ICU78.1 configuration reports candidate
misrecognition in both tested cultures. It is outside the table's characterized
configuration set; its result prohibits claiming automatic newer-version support.
No failing-scalar blacklist is added to hide this mismatch.

Local metadata repetition tests over every non-NUL scalar passed in that local
configuration, but are not substitutes for the target-matrix header tests.
The expanded header run
[37361407536](https://github.com/send/shoutx/actions/runs/37361407536), commit
`c8131f20519385ca346405ed95df6e97d8cbc0cb`, passed on the same four images and
both cultures. Each row added 1,112,063 non-NUL scalar repetition cases in
TITLE and FILE with a neighboring typed property: zero header mismatches.
The data-start and 72 metadata cases were rerun with zero mismatches as well.
Repetition inside a field does not enumerate arbitrary header strings or all
field-edge combinations; generated Worker fixtures separately cover edge cases.

The final-property framing run
[37362515725](https://github.com/send/shoutx/actions/runs/37362515725), commit
`2d09bf0d5e4a539942235f032b572b7a1c095a5e`, passed on the same matrix. Each
culture checked 3,336,189 header cases: final TITLE, final FILE and both followed
by a numeric field, using the specification's Unicode-property terminator.
There were zero header, metadata or data-start mismatches. Whitespace scalars
were kept interior to respect the producer's trailing-whitespace restriction.

The local pinned source-built Runner oracle completed all 64 tests, including
generated Unicode producer records, final-property cases with transparent
suffixes, mask registration and subsequent redaction, and annotation Worker
effects. This finite local result does not extend the full candidate table's
applicability to the local ICU78.1 environment. Final PR-hosted producer checks
and independent review remain pending. The current
producer contract tests pass under both stable and feature-enabled builds,
including exact output and all-scalar lookup agreement with the source set.

## Producer performance

Local release-mode CLI comparison on 2026-10-06 used
`scripts/benchmark-stdout-policy.py`: three warmups, 31 alternating paired
samples, elapsed wall time including startup, discarded stdout, and a required
clean exit. The threshold was fixed before candidate measurements: candidate
median at most `max(1.25 * baseline median, baseline median + 0.5 ms)`.
No workload exceeded it.

| Workload | Before, ms | After, ms |
| --- | ---: | ---: |
| Short mask | 1.984 | 1.978 |
| Unicode-tail annotation | 1.868 | 1.880 |
| Annotation limit | 1.823 | 1.839 |
| Supplementary annotation limit | 1.964 | 1.999 |
| 1 MiB mask | 6.338 | 6.318 |
| 1 MiB supplementary mask | 6.962 | 7.006 |
| 1 MiB escaped mask | 6.616 | 6.417 |

Baseline binary SHA256:
`a72012eb13dbe4e0f42efc73469293e1e2bcfae992bf7194c4c84322596b22eb`.
Candidate binary SHA256:
`acad3e1594314336254b11427f96ae9b409cf7dee4c9a7f098b1f7abb46b42ec`.
Both were built with `--release --locked --features unstable-github-actions-stdout`.
These workloads compare inputs accepted by both versions, hence have ASCII
starts. They measure end-to-end regression, not isolated non-ASCII lookup
latency, throughput under load, or a cross-platform timing guarantee.
