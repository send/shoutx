# Scope of V2 Unicode adoption research

Status: Superseded as an adoption work order; retained research history.

The dated decisions below describe the former research scope and obligations.
They are not current execution or release gates, and unfinished premises have
not become proven facts. The [framing decision](github-actions-stdout-framing.md)
now owns the adoption judgment, the [design](../design.md#stdout-adoption-contract)
owns applicability, and the [release policy](../release.md) owns admission and
maintenance. Retained observations remain usable with their original limits.

## Context

The maintainer selected a bounded target on 2026-10-04: Invariant Culture and
`en-US`, starting with the current latest Runner rather than requiring support
for historical releases. The existing investigation has conditional iterator
arguments and local data-graph results, but those are not yet a guarantee for
the actual consumer. More samples alone will not discharge those conditions.

On 2026-10-05 the maintainer approved the research direction summarized here and directed
its activation. That direction replaces the previous live-deployment linkage gate
with a reference-configuration proof and explicit deployment preconditions.
It does not approve a product guarantee, Unicode acceptance change, or release.
The former gate led the investigation through live startup hooks, sidecars and
loader state; inability to attest those deployment details alone is no longer
a reason to stop this research. Their observations and unknowns remain evidence,
not newly verified facts.

Later on 2026-10-05, the maintainer approved replacing this research goal's
Fable review requirement with a separate-context, read-only `gpt-6-sol`
review to conserve Fable capacity. Findings still require evidence-based
disposition and material corrections require re-review. Latest-head CI and
GitHub Codex convergence, zero unresolved review threads and the merge gate
remain unchanged. An unavailable independent reviewer does not permit merging
unreviewed work. This exception applies to this goal, not the repository's
general review guidance or the research correctness criteria.

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
is an explicit applicability condition, not inferred from the child locale or
a passing corpus. The proposed conditional guarantee and the operational
definition of its reference configuration live in the
[framing proposal](github-actions-stdout-framing.md#proposed-reference-configuration-boundary).

## Consequences and verification requirements

### Superseded 2026-10-04 gate (historical)

The former work order required matched live observations, then a justified
live acquisition-target route, then effective-data binding to each live
consumer/culture before full proof work. Missing linkage stopped expansion
pending maintainer direction: an alternative argument, explicit scope revision
or retention of the restricted surface. The
[original text at 33760a6](https://github.com/send/shoutx/blob/33760a697f9d0b388c56060aae3892e35233807e/docs/decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements)
preserves that gate; it is not the current rule.

### Current work order and stop rule

Historical heading retained for old links. "Current", "requires", and "Go"
in this subsection refer to the 2026-10-05 research order, superseded by the
adoption decision; they do not impose native-proof obligations on productization.

This section owns the research work order and stop rule. The 2026-10-05
direction supersedes the previous requirement to complete live Worker linkage
before acquiring reference data. First inventory the fixed reference inputs
and the existing observations for every row/culture. Identify the reference
package's normal startup and native selection path, the effective ICU
generation, root/tailoring relationship and acquisition target. Then acquire
and validate the corresponding data and discharge the header/search/iterator
premises. Identifying an acquisition target does not establish its contents.
The existing 78.1 root reader is not assumed usable for other generations.

The changes to research gates are limited to:

- Replace mandatory per-row/per-culture live consumer linkage with explicit
  deployment applicability conditions and separately labelled observations.
- Remove only the live-deployment connection and absence-attestation parts of
  acquisition checks. Keep package startup, loader, culture and effective-data
  identification within the reference configuration as proof obligations.
- Bind effective-input evidence to the reference execution path rather than
  requiring attestation of the deployed Worker.
- Use hosted effects as interoperability and regression evidence, not as proof
  of arbitrary-suffix safety or complete deployment identity.

Full data prerequisites, header/iterator/search composition, reproducible
generation, updates, performance and fail-before-output obligations remain.
The [test plan](../test-plan.md#unicode-adoption-completion-criteria) owns their
verification criteria. Reference correctness cannot be reclassified as a
deployment assumption. No unknown observation becomes a passing result.

Maintain a claim inventory with required evidence, existing evidence, remaining
work and a closure condition. Each additional experiment must close an identified
gap or test a counterexample. Do not repeat equivalent experiments without new
evidence; an alternative method must explain which failed premise it avoids.
Finite samples cannot replace an arbitrary-suffix argument.

If a recorded image cannot be rerun, seek other inputs whose identity can be
justified from recorded versions, hashes and acquisition provenance. State the
inference and its limits. If necessary evidence cannot be obtained using the
available sources and methods, record attempts, the exact missing premise and
what would unlock it. This supports an evidence-insufficient **No-Go adoption
recommendation**, not a finding that the configuration is unsafe. Rebasing the
matrix is a separate maintainer decision, not an automatic fallback. Do not
drop a row or silently substitute unrelated local data.

Go requires every necessary reference-correctness obligation to be closed for
both cultures on all four rows. The agent records a recommendation; the
maintainer decides adoption. A counterexample or justified evidence-insufficient
No-Go can conclude this research with the restricted feature retained. Ordinary
unfinished analysis remains undecided and incomplete, not No-Go by convenience.
Unavailable review, authentication or publication facilities are execution
blockers rather than evidence about parser safety. Scope changes or additional
assumptions beyond this direction require maintainer approval.

The outcome is a reviewed implementation recommendation, not an acceptance
change. Preserve evidence and residual risks in the
[feasibility audit](../compatibility/unicode-feasibility.md), with per-row
observed, unobserved and known-mismatch conditions. Record a general Unicode
predicate candidate, composition with existing ASCII rules, generation/update
and performance plans, and implementation tasks or the specific No-Go basis.

The [stdout framing decision](github-actions-stdout-framing.md) remains
Proposed. This record narrows its research target, not its security objectives.
No CLI acceptance, metadata rule, wire syntax, resource limit, masking
semantics, stable build surface or release eligibility changes here. Legacy
framing remains excluded. Stable adoption still requires the coordinated
design/command and release-policy review described by that decision.

## Reconsideration conditions

Consider a separate scope revision after the evidence-insufficient recommendation
described above if required evidence cannot be obtained. Also reconsider if a target
configuration violates the proposed predicate, GitHub changes its parser or
runtime, or the maintainer requests other environments. Do not broaden the
scope automatically when another configuration happens to pass finite tests.

## Evidence

- [Dated Runner baseline](../compatibility/runner-package-runtime.md#research-baseline-selection)
- [Conditional Unicode arguments and remaining premises](../compatibility/github-actions-workflow-command-parser.md#v2-unicode-data-start-investigation)
- [Verification criteria and distinct package/live coverage](../test-plan.md#unicode-adoption-completion-criteria)
