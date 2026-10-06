# GitHub Actions stdout workflow-command framing

Status: Accepted; implemented in the normal command surface, publication gated.

## Context

The mask and typed annotation writers emit GitHub Actions V2 stdout commands.
The pinned Runner uses locale-sensitive prefix/separator operations. Producer
success therefore cannot prove consumer acceptance. Versioned observations,
including known failures, belong to the
[parser compatibility note](../compatibility/github-actions-workflow-command-parser.md)
and [Unicode policy evidence](../compatibility/stdout-unicode-policy.md).

## Decision

Proceed with productizing the original-value implementation merged in PR #116,
under the [design-owned adoption contract](../design.md#stdout-adoption-contract).
This includes mask, notice/warning/error, message, TITLE, and FILE; it is not a
language-specific subset. The command specifications remain the sole authority
for accepted inputs, encoding, rejection, and limits. This decision does not
authorize a release; normal-build inclusion is implemented by the coordinated
productization change.

The former universal delimiter constraint is replaced explicitly in design
invariant 16. Dependency correctness is trusted within a named compatibility
profile, while shoutx remains responsible for protecting command structure at
its output boundary. Unobservable Worker internals are not a user attestation
requirement. Known harmful incompatibilities still require action, not a
blanket dependency disclaimer. The release policy owns refresh, pending
verification, and failure response.

## Rationale and evidence

The attack inventory AP1–AP5 in the
[threat model](../threat-model.md#stdout-mask-and-annotation-responsibility)
separates command injection, reinterpretation, mask exposure, and property
integrity from functional differences. PR #116 supplies an original-value
implementation and observed Runner effects, not merely a character classifier.
The static positive start set and structural metadata delimiter address the
identified input boundaries without trimming, decoration, or native runtime
dependencies. Their derivation is recorded in the
[Unicode acceptance decision](stdout-unicode-acceptance.md).

The [compatibility record](../compatibility/stdout-unicode-policy.md) links the
controlled package, producer, full-set policy, hosted-effect, and performance
evidence. Controlled en-US/Invariant tests and live hosted effects serve
different purposes; neither is represented as identifying the live Worker's
hidden configuration. Local ICU 78.1 mismatches and the deferred th-TH failure
remain contrary evidence for broader scope, not new research obligations here.

The adoption judgment is that the implemented controls and existing integration
evidence justify the finite productization increment within the design profile.
They do not justify arbitrary self-hosted systems, all cultures, all future
versions, or a proof over every consumer implementation. Requiring complete
native collation proofs would move dependency ownership into shoutx without a
corresponding product boundary. Conversely, dismissing an observed attack path
because the defect is in a dependency would not meet this decision.

## Considered options

- Extend the original ASCII-only boundary mitigation: rejected as the product
  endpoint because it unnecessarily excludes useful original-value Unicode
  inputs. Its historical results remain evidence, not the current input policy.
- Use a culture-name allowlist as a runtime guard: rejected; shoutx cannot
  observe or enforce the live Worker culture, and names alone omit backend
  differences. Reference tests are not such a guard.
- Emit both V2 and legacy commands: rejected because duplicate effects and a
  failed mask line becoming ordinary output are unacceptable.
- Use legacy `##[command]data`: not selected by the maintainer because of its
  uncertain removal horizon. Retain fallback tests, not a legacy emitter.
- Probe the Runner at runtime: rejected as an acknowledgement mechanism;
  stdout commands provide no response to the producer and probes alter state.
- Keep the entire family unpublished indefinitely: not selected on the basis
  of unfinished dependency proofs. A concrete applicable security or unusable
  contract problem can still require withholding an affected release.

## Consequences

The [isolation decision](unstable-github-actions-stdout.md) is superseded for
new builds; previously published binaries are unchanged. The completed
[implementation record](../implementation-history.md#stdout-productization)
covers build/help/package verification and user-facing documentation. Official
admission still follows the [release policy](../release.md#stdout-admission-and-compatibility-maintenance).
Additional stdout commands and expansion of the environment profile are not
part of that increment.

## Historical research proposals

The [pre-adoption version of this record](https://github.com/send/shoutx/blob/92212eb8d07fb019cc546f2475a306473be89714/docs/decisions/github-actions-stdout-framing.md)
preserves the original proposals, evidence links, and unresolved obligations.
They are superseded as adoption criteria, not retroactively proven. The
following retained anchors keep old research references interpretable.

### Interim research mitigation

The former ASCII-only start/metadata mitigation was replaced by PR #116's
original-value policy. Historical experiments must be read using their own
input policy, not as observations of today's implementation.

### Proposed reference-configuration boundary

This was an investigation proposal requiring matching consumer internals and
native source/data proofs. It is not the current product contract. The design
now owns a usable profile and explicit dependency assumptions; callers are not
asked to establish that their hidden Worker internals match a probe exactly.

### Runner compatibility findings and open policy

The earlier open-policy alternatives are resolved by the design profile and
release maintenance policy. Observations concerning version drift remain
relevant; arbitrary self-hosted and GitHub Enterprise Server support has not
been adopted.

### Research verification, not framing acceptance

Retained native research and harness checks remain useful compatibility
evidence. Their unfinished proof goals are not release gates. The
[test plan](../test-plan.md) distinguishes current required checks from
historical investigation objectives; an actual failing applicable check still
requires triage rather than being waived by this paragraph.

## Reconsideration conditions

Reconsider on a demonstrated attack path or round-trip failure within the
profile, a relevant upstream parser/runtime change, or a proposed environment
expansion. Prefer a concrete product-impact assessment and the smallest
effective control. A newly available ordinal protocol may simplify the design,
but its absence does not itself reopen native-internal proof work.
