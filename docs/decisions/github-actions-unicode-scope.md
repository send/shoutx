# Scope of V2 Unicode adoption research

Status: Accepted

This accepts only the research scope, not framing, stable support or release
eligibility.

## Context

The maintainer selected a bounded target on 2026-10-04: Invariant Culture and
`en-US`, starting with the current latest Runner rather than requiring support
for historical releases. The existing investigation has conditional iterator
arguments and local data-graph results, but those are not yet a guarantee for
the actual consumer. More samples alone will not discharge those conditions.

## Decision drivers

- Establish explicit completion criteria instead of indefinitely accumulating
  local experiments or attempting every culture and historical runtime.
- Expand Unicode based on a positive acceptance predicate, not particular
  languages, scripts, a five-character denylist or lossy normalization.
- Keep a tested culture distinct from the consumer's OS, backend, data,
  settings and code identities.
- Preserve the existing research-feature and release boundary until a separate
  adoption decision and command-contract change are justified.

## Considered options

- Require all cultures, old Runner versions and arbitrary self-hosted systems:
  not selected for this workstream.
- Assume culture name and a minimum Runner version establish compatibility:
  rejected; neither identifies the effective collation/search implementation.
- Use named hosted-environment observations and explicit consumer prerequisites:
  selected as the initial target, subject to the completion criteria below.

## Decision

The initial target is the latest stable published Runner at this decision's
date, identified in the [package evidence note](../compatibility/runner-package-runtime.md#research-baseline-selection),
under Invariant Culture and `en-US`, on the hosted OS/architecture rows of the
existing differential matrix. The exact verification matrix and completion
criteria belong to the [test plan](../test-plan.md#unicode-adoption-completion-criteria).
Invariant Culture here means the culture used for comparisons; it does not
mean .NET globalization-invariant mode, which is outside the ICU argument.

No retrospective support for older Runner versions, other cultures, arbitrary
self-hosted configurations, NLS/hybrid modes or GitHub Enterprise Server is
required to finish this workstream. This is not evidence that they are safe
or unsafe. The known `th-TH` issue remains deferred. Local macOS experiments
are supporting research, not additional hosted-environment guarantees.

"Starting with the latest" is not an open-ended `Runner >= version` claim.
Subsequent Runner, hosted-image, runtime or globalization-data changes require
reviewed, fresh evidence before their combinations join the verified scope.
The existing [continuing checks](../test-plan.md#continuing-compatibility-checks)
detect some drift; a successful old run or a moving image label is not a
current identity record. Unknown or changed combinations remain unverified.
No runtime rejection of such a worker is promised: shoutx cannot observe or
enforce those prerequisites from the child process.

Scope selection does not establish that an unmodified hosted Worker uses one
of these cultures or the inspected cached search object. Explicit-culture
package probes and live hosted effects are separate evidence. Their connection
must be justified, not inferred from the child locale or a passing corpus.

## Consequences and verification requirements

This section owns the work order and stop rule. The first milestone is a
feasibility pass across every target row/culture. First check whether live
hosted evidence exists with the baseline Runner and matching resolved image;
an unavailable baseline or missing row is an early gap, not a reason to start
expensive format analysis. For available rows, identify the actual ICU
generation and effective root/tailoring relationship, determine whether its
formats and required inputs can be inspected, and establish the package-to-live
consumer link required by the test plan. The existing 78.1 root reader is not
assumed usable unchanged for the other generations. Then consolidate the
remaining header/search/iterator argument and check its data premises.
Only after the [completion criteria](../test-plan.md#unicode-adoption-completion-criteria)
are met should a coordinated acceptance-table and command-contract change be
proposed. Each additional experiment should identify the unresolved obligation
it closes or the counterexample it tests, rather than increase a case count.
If a required input or consumer link cannot be established, stop expansion
work and report the evidence and exact gap for maintainer direction: justify
an alternative argument, explicitly revise the scope, or retain the restricted
research surface. This rule applies at any stage, including live-hosted
linkage in the first feasibility pass. Do not substitute local data, drop a
matrix row or replace a missing premise with finite samples. Scope revisions
require maintainer direction.

The [stdout framing decision](github-actions-stdout-framing.md) remains
Proposed. This record narrows its research target, not its security objectives.
No CLI acceptance, metadata rule, wire syntax, resource limit, masking
semantics, stable build surface or release eligibility changes here. Legacy
framing remains excluded. Stable adoption still requires the coordinated
design/command and release-policy review described by that decision.

## Reconsideration conditions

Revisit the scope if the required evidence cannot be obtained, a target
configuration violates the proposed predicate, GitHub changes its parser or
runtime, or the maintainer requests other environments. Do not broaden the
scope automatically when another configuration happens to pass finite tests.

## Evidence

- [Dated Runner baseline](../compatibility/runner-package-runtime.md#research-baseline-selection)
- [Conditional Unicode arguments and remaining premises](../compatibility/github-actions-workflow-command-parser.md#v2-unicode-data-start-investigation)
- [Verification criteria and distinct package/live coverage](../test-plan.md#unicode-adoption-completion-criteria)
