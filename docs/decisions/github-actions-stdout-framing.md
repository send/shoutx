# GitHub Actions stdout workflow-command framing

Status: Proposed

## Context

The implemented mask and typed annotation writers emit GitHub Actions V2
stdout workflow commands. The pinned runner parses the V2 prefix and data
separator with locale-sensitive string operations. An ASCII-only command can
therefore fail after shoutx has successfully written it, and parser fallback
can reinterpret value data.

The versioned parser observations are maintained in the
[GitHub Actions workflow-command compatibility note](../compatibility/github-actions-workflow-command-parser.md).
This record must not restate its culture matrix or parser transcript.

## Decision drivers

- One accepted value must reach exactly the selected runner command with its
  decoded value and typed properties intact.
- Framing must not depend on the value's Unicode contents.
- shoutx-defined syntax is ASCII; command-specific values remain opaque strict
  UTF-8 data without implicit normalization.
- The child process cannot treat its own success as proof that the runner
  worker accepted the record.
- A security claim must hold throughout its explicitly reviewed support scope,
  including OS and globalization backends; culture names selected without
  supporting evidence are insufficient.
- Before a framing decision is accepted, the project must define which self-
  hosted runner versions and host environments its claim covers, how they are
  verified, and how hosted runners are covered separately.

## Considered options

### Keep V2 and reject selected input characters

Not preferred. The known ASCII-only counterexample shows that a Unicode scalar
or category denylist cannot make the delimiter search culture-independent.

### Support only selected runner cultures

Not sufficient by itself. shoutx cannot reliably observe the worker process's
culture, and culture names alone do not account for collation backend or
data-version changes. The subsequently accepted
[Unicode research scope](github-actions-unicode-scope.md) selects explicit
cultures and named environments for investigation; it does not treat a
culture allowlist as a protocol repair or runtime enforcement mechanism.

### Emit both V2 and legacy commands

Not preferred. Normally both forms would execute, duplicating annotations or
mask registration. If one mask form failed and became ordinary output, it
could disclose the value the other form was intended to protect.

### Probe the runner at runtime

Not preferred. Stdout command processing is one-way and the child receives no
acknowledgement that a probe was recognized. A probe with control effects
would also change runner state.

### Use legacy `##[command]data` framing

Not selected by the maintainer as of 2026-10-01. Although shoutx could place a
fixed ASCII prefix at offset zero and use legacy escaping, the syntax is not
documented in the current public GitHub workflow-command reference. Its
uncertain removal horizon is unacceptable for adoption. The ongoing Unicode
investigation stays on V2; legacy parser regressions remain useful evidence
about the consumer's fallback behavior, not a proposal to emit that format.

### Do not release stdout workflow-command writers

Required fallback. If no framing satisfies the product guarantee, the mask and
annotation family remains excluded from releases while environment-file
writers continue independently.

## Interim research mitigation

Input-dependent misparsing under Invariant Culture and `en-US` is the current
mitigation target. Use an explicit ASCII boundary allowlist rather than
extending a Unicode denylist. Constrain the encoded header and first encoded
data character; retain Unicode only after that inspected boundary. Reject
unrepresentable inputs before output rather than altering the value. This
deliberately sacrifices non-ASCII message starts and metadata in the research
feature. The derivation and its runtime limits live in the compatibility note,
not in a universal safety claim.
Keep the exact input rules in the command specifications. Explicit-culture
runner tests must cover rejection counterexamples and accepted-value fidelity.
The `th-TH` ASCII failure is deferred, not fixed or shown to be unreachable.
This prioritization does not accept V2 framing or remove the research feature /
release exclusion. The later [scope decision](github-actions-unicode-scope.md)
defines the target of further research, not a shipped compatibility guarantee.

## Decision

No wire format is accepted by this proposed record yet. Before acceptance, a
candidate must pass the real-runner verification described below, and
the exact encoding contract and compatibility policy must be reviewed. Failure
of evidence within the eventual claimed support scope selects the no-release
fallback rather than silently exempting a failing culture. The research target
is selected, but the supported-culture contract and release compatibility policy
are not yet accepted. A deliberately narrower support proposal must explicitly
address excluded/unknown environments and the deferred `th-TH` failure; a
two-culture test pass alone cannot authorize it.

### Proposed reference-configuration boundary

The maintainer's [2026-10-05 research direction](github-actions-unicode-scope.md)
authorizes investigating the following conditional guarantee, not adopting it.
The current product contract and design invariant 16 remain unchanged.

A reference configuration consists of the hash-identified official Runner
package (including its host, runtimeconfig, deps and runtime), recorded OS and
dependencies, enumerated startup inputs, and comparison culture. Startup-input
values must be grounded in corresponding recorded observations or package
defaults, with provenance; "default" alone is not an identity. Its normal
output prefilter, parser and command-extension path are the subject of proof.
Package-defined globalization mode, ICU selection, AppContext settings and
loader behavior remain inside that subject. Differences between an explicit-
culture probe harness and the normal path must be justified, not assumed away.

The candidate guarantee is recognition of exactly the intended V2 command,
with the original decoded value and typed properties and the intended mask
registration or annotation processing. It excludes non-recognition that logs
the command as ordinary text and reinterpretation through another command or
fallback parser. It does not promise prevention of every transformed-secret
disclosure, external-service availability, downstream-parser safety or recovery
from I/O failure after writing begins. Validation, encoding and resource checks
must finish before output begins.

Application to a deployment is conditional on its consumer using the same
implementation, settings, data and culture as the reference. Shoutx
cannot detect or enforce that condition, and producer success is not evidence
of consumer acceptance. Proving absence of deployment-added startup hooks,
sidecars, environment overrides or replacements is outside the candidate
guarantee's proof subject.
Reference mappings, contractions, normalization/break data, search settings and
iterator behavior are proof obligations, not trusted assumptions. Applicability
recording and handling of mismatches follow the scope decision; a known mismatch
does not satisfy this candidate guarantee's conditions.

Excluded environments retain their known risks, including the deferred `th-TH`
mask-registration failure and possible value disclosure. Do not assume users
can select or observe Worker culture. A historical snapshot is not a guarantee
for today's moving hosted-image label. The scope decision fixes the research
matrix; release validity, updates and response policy remain separate decisions.

For future coordinated adoption only, a proposed replacement for invariant 16
would preserve the prohibition on inferring consumer culture from the producer
and the distinction between producer success and consumer acceptance. It would
permit a destination using locale-sensitive delimiters only under explicitly
named, proven consumer conditions, documenting non-enforcement and consequences
outside those conditions. This is a proposal, not a present exception to that
invariant. No-Go leaves the invariant and restricted product surface intact.

### Runner compatibility findings and open policy

This subsection records constraints discovered while evaluating a self-hosted
runner baseline. It is not an active compatibility contract. The later
[scope decision](github-actions-unicode-scope.md) selects the named-hosted
direction for initial Unicode research; it does not resolve the release-policy
requirements below or authorize arbitrary self-hosted configurations.

GitHub's registration floor is not a permanent runtime baseline. The
repository-scoped deprecation API returns planning dates for individual
versions, but a past date is not evidence that enforcement has occurred for
every account. One repository's response also cannot establish a product-wide
support window.

Runner version is not the only compatibility dimension. The same runner source
and .NET SDK can produce different collation behavior on hosts with different
ICU, NLS, or globalization-mode state. shoutx cannot observe the worker
process's runner version, culture, backend, or backend version. A finite matrix
is useful evidence for named environments, but it cannot justify a guarantee
over arbitrary self-hosted systems; treating it as such would recreate the
culture-name-only policy described above as insufficient.

Testing a named environment would require executing the parsing path from the
published runner package, verifying and recording the package digest, version,
architecture, OS generation, globalization mode, and exposed backend version.
An unobservable required dimension would make that matrix entry incomplete.
Package inspection and a source build are supplementary evidence only.

Any accepted policy would also require post-release monitoring for new runner
releases, hosted-image changes, OS globalization-data updates, and deprecation-
schedule changes. Because shoutx cannot reject an unverified worker at runtime,
the user contract must explain what happens while a new environment is
untested. Confidentiality, command-selection, property-framing, and annotation
integrity failures all require a user-visible response and security triage.
The response must follow the authoritative
[release policy](../release.md) and account for the documentation packaged in
an existing release rather than defining asset-mutation rules in this record.

The release compatibility policy remains open among these alternatives,
even though initial research follows the named-hosted direction:

- support only specifically named GitHub-hosted environments, with an explicit
  validity and refresh rule;
- add narrowly named self-hosted environment combinations, while making their
  unobservable runtime preconditions and update gaps user-visible; or
- keep the stdout family out of releases.

GitHub Enterprise Server requires a separate server-version analysis and is
not covered by the current evidence. If any support boundary is accepted, the
design will own it; the README, command specifications, and threat model will
link to or apply that boundary without becoming independent policy. These
questions concern stdout workflow commands only and do not change the separate
contracts of environment-file writers.

## Consequences

- Work on additional stdout workflow commands, including `debug`, remains
  paused.
- Existing annotation and mask prefix guards are only pre-release observations and
  cannot justify release eligibility.
- The interim research allowlist narrows boundary data and annotation metadata;
  accepted values are never silently deleted, prefixed, or normalized to make
  framing succeed. Expanding Unicode acceptance requires a new derivation.
- An accepted decision will require one coordinated change to mask,
  annotations, their shared private encoder, and their normative command
  specifications.

## Verification requirements

A compatibility policy selecting one of the alternatives above must be
complete before this record can become Accepted. The current single-pin,
source-build oracle is insufficient. Acceptance requires a published-runner-
runtime test method; an explicit hosted and, if applicable, self-hosted scope;
hosted validity and refresh rules; user-visible handling of unobservable and
newly updated environments; and a post-release monitoring and failure-response
policy covering every security consequence. It must also reconcile the current
pinned-oracle rule in the test plan and release-level tested-version declaration
in the threat model with their authoritative owners.

Over whatever cultures/environments that pending policy selects, framing
acceptance still requires fixed prefix position, intended command selection,
exact decoded properties/data and the intended command-extension effects.
Its evidence must cover every selected OS generation, report rather than infer
the required backend/version dimensions, and separately verify live hosted
masking/annotation effects. Missing required observations remain gaps. Passing
the bounded research checks below is necessary supporting evidence, not a
substitute for defining and meeting that acceptance policy.

### Research verification, not framing acceptance

For the selected research scope, the oracle must exercise both the output
prefilter and command manager under each explicitly targeted culture on every
target matrix row, as defined by the
[completion criteria](../test-plan.md#unicode-adoption-completion-criteria).
The original all-available-cultures paragraph was an acceptance proposal, not
an already accepted support contract. It is not a requirement of this bounded
research workstream. Which cultures framing acceptance must cover remains part
of the pending compatibility-policy decision; this subsection does not replace
that decision with a two-culture acceptance gate. Retain existing other-culture
negative controls without treating those cultures as research support targets.
Verify fixed prefix position, selected command, decoded
properties/data and command-extension effects. Finite test success does not
prove these properties over arbitrary allowed suffixes; the source/data
argument remains required. Failures must identify the runner version, culture
and observed parse result.

These tests are continuing compatibility evidence, not a proof over future
cultures or runtime versions. The shared verification policy remains
authoritative in [`test-plan.md`](../test-plan.md), and release eligibility
remains authoritative in [`release.md`](../release.md).

## Reconsideration conditions

Reconsider the accepted framing if GitHub removes or changes the selected
parser, if a culture or backend within the eventual accepted scope violates
the round trip, or if an upstream
ordinal V2 parser becomes available throughout the accepted support scope.
Evaluate GitHub Enterprise Server independently if it later enters that scope.

## Evidence

- [GitHub Actions workflow-command parser compatibility](../compatibility/github-actions-workflow-command-parser.md)
- [GitHub runner releases API][runner-releases-api]
- [GitHub self-hosted runner update policy][runner-update-policy]
- [GitHub runner-version deprecation API][runner-deprecation-api]
- [September 2026 enforcement announcement][runner-enforcement]
- [PR #42](https://github.com/send/shoutx/pull/42)
- [Upstream-report reminder #43](https://github.com/send/shoutx/issues/43)

[runner-releases-api]: https://docs.github.com/en/rest/releases/releases?apiVersion=2026-03-10#list-releases
[runner-update-policy]: https://docs.github.com/en/actions/reference/runners/self-hosted-runners#runner-software-updates-on-self-hosted-runners
[runner-deprecation-api]: https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2026-03-10#get-runner-version-end-of-life-schedule-for-a-repository
[runner-enforcement]: https://github.blog/changelog/2026-09-28-self-hosted-runner-version-enforcement-date-has-moved/
