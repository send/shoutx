# Azure secret registration decision

Status: Accepted by the maintainer on 2026-10-24, based on reviewed proposal
`cb20337`. Implementation is authorized; hosted admission remains a separate gate.

## Decision and ownership

Adopt explicit registration of whole values or explicitly selected complete
lines for subsequent ordinary Agent-captured stdout/stderr. Keep registration
separate from credential replacement and secret-variable assignment.

The [mask command specification](../commands/azure-pipelines-mask.md) owns the
CLI, accepted input, resource limits and finite verification plan. The
[design profile](../design.md#azure-pipelines-profile) owns deployment conditions;
the [threat model](../threat-model.md) owns attack paths and caller boundaries.
The [compatibility record](../compatibility/azure-pipelines.md) owns source and
hosted observations. The [handoff](../implementation-plan.md#current-handoff-status)
owns remaining work. This record retains rationale, not a second normative input
table. The Japanese review translation is a private reference, not another source
of truth or a public deliverable.

## Rationale and alternatives

Start with concrete disclosure paths, not a proof over all character sets or an
audit of Agent, .NET or ICU. Provider limitations do not justify accepting a value
under a protection claim that the supported profile cannot deliver. Prefer
lossless protocol encoding; reject known unsupported input before output. If
admission tests expose a real limitation, present evidence and a scoped contract
change rather than silently weakening the test or narrowing accepted scope.

Stdin-only input avoids an additional secret-bearing argv surface. A tested
PowerShell byte-stream example handles the transport cost without shipping a new
helper executable. A user-written replacement cannot inherit byte-fidelity
evidence without equivalent behavior.

The explicit zero short-secret threshold preserves useful short values and
short final lines. A six-scalar rejection floor would tolerate more threshold
settings but discard that utility; the inspected default and upstream tests
did not justify imposing it. Source expectations still require hosted evidence.

Explicit line selection protects separately logged complete lines without
changing credentials. Automatically trimming lines or omitting apparent public
headers would silently choose a different protected asset. The caller instead
authorizes the overmasking cost. Registering the combined original in addition
does not establish protection for arbitrary wrapping or serialization and adds
an unnecessary registration path.

Registering an opaque JSON value does not protect its fields in isolation.
Rejecting JSON-looking text prevents legitimate use without solving fragment
disclosure. Automatically enumerating fields or all substrings adds schema,
workload and overmasking decisions. Known confidential representations therefore
use separate explicit registrations; automatic extraction needs a later concrete
use case and interface.

Sanitization remains a possible product technique when justified by value and
cost, but changing a credential only in the masking writer does not protect the
original used by its service. A sanitized logged representation must actually be
the emitted value; replacement credentials require issuer/consumer agreement.
Neither is an implicit transformation of this command.

Secret-variable assignment introduces name authorization, mapping, output scope
and distinct handler behavior. It is not a shortcut to mask registration and
remains separate. Retrospective log cleanup likewise cannot follow from input
validation or encoding.

## Admission and follow-up

Implementation approval does not mean that source-parser equality proves Agent
registration or log redaction. Execute the finite plan linked above, retain
bounded evidence, and present a merge-ready PR after independent review and
latest-head CI/Codex convergence. Merge requires separate direction; release
preparation remains on hold.

New concrete attack details follow [SECURITY.md](../../SECURITY.md) and confidential
durable tracking, not public issues or exploit details in this record.

## Independent review record

The first read-only Fable review on 2026-10-24 completed successfully using
`claude-fable-5-1`, with no denied inspections. Accepted findings led to an
explicit registration-channel disclosure path and debug-off/later-task
conditions; correction of the short-value recommendation after checking the
zero-default knob; clearer whitespace evidence; explicit Windows delivery cost;
defined argv errors and caller authorization; and a budgeted downstream
completed-log verifier instead of implying the existing parser/timeline tools
already cover handlers and completed logs. Exact redaction and failure outcomes,
line-mode segment authorization and post-approval SSoT edits were also clarified.

Backend behavior beyond the inspected source remains a required future
measurement, not a new gate requiring all backend executions before presenting
this design. This preserves the separation between proposal and implementation
verification.

The follow-up Fable review completed successfully on the same date with the
same model and no denied inspections, finding no blocking design flaws. Its
nonblocking clarifications were incorporated: knob precedence and pipeline
setting, timeline message checks, non-colliding short-value markers, build-once
artifact reuse within the then-proposed 23-job count (before line-mode expansion), accurate token-permission wording,
consistent profile naming, and helper-delivery options. Source observations
remain distinct from unexecuted tests. These clarifications do not change the
proposed security boundary and do not require another review round.

The subsequent line-mode review on 2026-10-24 completed successfully with Fable
and no denied inspections; it found no blocking design flaw. Both medium
findings were accepted: make the zero-threshold condition explicit for short
final lines and calibrate synthetic blocks before crediting line registration.
The low findings were addressed with fixed diagnostics and validation order,
BOM-free delivery, pre-registration binary publication, percent-decoding checks,
captured rejection probes and native-shell scope. The earlier 23-job count is
labeled historical. Workload limits and overmasking remain explicit adoption
decisions. The review's suggestion that the redaction expectation was based
only on legacy tests was corrected against the shared upstream test fixture;
the compatibility record distinguishes that source expectation from live results.
Additional self-review clarified limit-sized stdin transport, inert hosted
delimiters and a bounded transport-normalization probe.

The focused follow-up completed successfully with `claude-fable-5-1` and no
denied inspections. It confirmed both medium findings and the low clarifications
were addressed. Its three remaining wording gaps were fixed: framing probes run
inside existing jobs, BOM bytes are directly checked in helper tests rather than
inferred from hosted wire visibility, and combined-error tests assert validation
precedence. These are test-plan clarifications, not a boundary change; no further
design-review round was required. At that point implementation and hosted
execution had not started; current status is owned by the implementation handoff.
