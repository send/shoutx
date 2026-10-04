# Unicode adoption feasibility audit

Status: In progress; not adoption evidence or a support declaration.

This audit follows the [research scope](../decisions/github-actions-unicode-scope.md)
and [completion criteria](../test-plan.md#unicode-adoption-completion-criteria).
It does not change CLI acceptance. Observations below were inspected on
2026-10-04; unknown premises remain unknown, not passing checks.

## Initial baseline availability

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

The 2026-10-04 experiment adds the existing live boundary corpus to all four
package-probe jobs and a completed-job verifier. As of this initial inventory,
there is no inspected hosted run of that extension.
The producer policy and corpus are unchanged; the purpose is same-job identity
matching, not increasing the sample space.

1. Obtain all four same-job observations, covering the missing Ubuntu 22.04
   and macOS 15 rows and replacing cross-job comparisons for Ubuntu 24.04 and
   Windows with same-job evidence. Retain exact image/version and job/attempt
   identities. Baseline setup-log availability alone does not close this gap.
2. Evaluate the source/configuration or direct-observation path connecting
   the live consumer to each explicit culture's implementation/settings,
   including the server-supplied culture input. This is currently unverified
   for **both cultures on every row**, including the two image-matched rows.
3. For rows with a defensible connection, evaluate acquisition of native
   identities, effective root/tailoring, normalization/break inputs and format
   support. No costly mapping expansion is justified by the package counts.
4. Retain a minimal machine-readable non-secret evidence projection and its
   provenance; review the final per-row/per-culture verdict independently.

This is an initial inventory, not a completed feasibility verdict. It neither
drops missing rows nor treats unavailable evidence as proof of impossibility.

## Consumer-state observation route under investigation

The [parser note](github-actions-workflow-command-parser.md#culture-diagnostic-observation-route)
owns the inspected source mechanism and diagnostic limitations.

A possible next observation is an in-job, allowlisted projection of the
relevant diagnostic input, with an explicit binding to this job's Worker.
Availability, trustworthy job/process correlation, redaction and later thread
state still need evaluation. As of this 2026-10-04 initial inventory, no
diagnostic collection has been implemented or run. Even a startup culture record would not alone prove effective
native mappings, runtime identity or the other culture's transfer argument.

## Reproduction of this inventory

Download artifacts from the run above with `gh run download 37175079175
--repo send/shoutx --dir NEW_DIRECTORY`. Each
`runner-package-evidence-OS-RID/runner-package-evidence/` directory contains
`evidence.json` (run, image, package identity) and `probe.json` (explicit
cultures/native observations). `hosted-boundary-evidence/*.json` records
the separate live observations. Query the run's jobs API for job IDs and
attempts. Read only the setup-log identity fields for the two missing
boundary rows; do not retain full job logs in this repository.

The source reports currently have the existing 30-day retention. Their
temporary download is not durable closure evidence; a reviewed projection
and reproducible acquisition record remain part of this audit's work.
