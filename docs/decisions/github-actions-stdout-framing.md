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
- A security claim must survive the supported OS and globalization backends
  without a culture allowlist maintained by guesswork.
- Before a framing decision is accepted, the project must define which self-
  hosted runner versions and host environments its claim covers, how they are
  verified, and how hosted runners are covered separately.

## Considered options

### Keep V2 and reject selected input characters

Not preferred. The known ASCII-only counterexample shows that a Unicode scalar
or category denylist cannot make the delimiter search culture-independent.

### Support only selected runner cultures

Not preferred. shoutx cannot reliably observe the worker process's culture,
and a finite allowlist would not account for collation backend or data-version
changes.

### Emit both V2 and legacy commands

Not preferred. Normally both forms would execute, duplicating annotations or
mask registration. If one mask form failed and became ordinary output, it
could disclose the value the other form was intended to protect.

### Probe the runner at runtime

Not preferred. Stdout command processing is one-way and the child receives no
acknowledgement that a probe was recognized. A probe with control effects
would also change runner state.

### Use legacy `##[command]data` framing

Current leading candidate. shoutx can place a fixed ASCII prefix at offset
zero and use the runner's complete legacy escaping for properties and data.
The syntax is not documented in the current public GitHub workflow-command
reference, and its prefix search remains locale-sensitive, so it requires
strong parser evidence, hosted behavior checks, and a forward-compatibility
plan.

### Do not release stdout workflow-command writers

Required fallback. If no framing satisfies the product guarantee, the mask and
annotation family remains excluded from releases while environment-file
writers continue independently.

## Interim research mitigation

Input-dependent misparsing under Invariant Culture and `en-US` is the current
mitigation target. Apply the annotation message-prefix guard to mask values,
rejecting unrepresentable inputs before output rather than altering the value.
Keep the exact input rules in the command specifications. Explicit-culture
runner tests must cover rejection counterexamples and accepted-value fidelity.
The `th-TH` ASCII failure is deferred, not fixed or shown to be unreachable.
This prioritization does not accept V2 framing, establish a supported-culture
allowlist, or remove the research feature / release exclusion.

## Decision

No wire format is accepted by this proposed record yet. Before acceptance, the
legacy candidate must pass the real-runner verification described below, and
the exact encoding contract and compatibility policy must be reviewed. Failure
of that evidence selects the no-release fallback rather than a culture-specific
exception.

### Runner compatibility findings and open policy

This subsection records constraints discovered while evaluating a self-hosted
runner baseline. It is not an active compatibility contract and does not select
one of the policy alternatives below.

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
culture allowlist rejected above.

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

The policy remains open among at least these alternatives:

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
- UTF-8 values are not narrowed to ASCII and are never silently deleted or
  normalized to make framing succeed.
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

For every tested runner environment, the oracle must enumerate every .NET
culture available in each supported CI environment and exercise both the
output prefilter and command manager. For every culture it must prove the fixed
prefix position, selected command, decoded properties, decoded data, and
command-extension side effect. Failures must identify the runner version,
culture, and observed parse result.

The CI environments must span every OS generation in the selected scope. Tests
must report rather than infer the active globalization backend and relevant
version; inability to observe a dimension required by the selected policy is a
gap, not permission to omit it. Hosted checks must separately verify actual
masking and annotation effects.

These tests are continuing compatibility evidence, not a proof over future
cultures or runtime versions. The shared verification policy remains
authoritative in [`test-plan.md`](../test-plan.md), and release eligibility
remains authoritative in [`release.md`](../release.md).

## Reconsideration conditions

Reconsider the accepted framing if GitHub removes or changes the selected
parser, if any culture or backend violates the round trip, or if an upstream
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
