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
- The design must account for older self-hosted runners as well as current
  hosted runners.

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

## Decision

No wire format is accepted by this proposed record yet. Before acceptance, the
legacy candidate must pass the real-runner verification described below, and
the exact encoding contract and compatibility policy must be reviewed. Failure
of that evidence selects the no-release fallback rather than a culture-specific
exception.

## Consequences

- Work on additional stdout workflow commands, including `debug`, remains
  paused.
- Existing Unicode-category guards are only pre-release observations and
  cannot justify release eligibility.
- UTF-8 values are not narrowed to ASCII and are never silently deleted or
  normalized to make framing succeed.
- An accepted decision will require one coordinated change to mask,
  annotations, their shared private encoder, and their normative command
  specifications.

## Verification requirements

The pinned runner oracle must enumerate every .NET culture available in each
supported CI environment and exercise both the output prefilter and command
manager. For every culture it must prove the fixed prefix position, selected
command, decoded properties, decoded data, and command-extension side effect.
Failures must identify the culture and observed parse result.

The CI environments must span the supported Linux generations, macOS, and
Windows. Tests must report rather than infer the active globalization backend
and relevant version information where the runtime exposes it. Hosted checks
must separately verify actual masking and annotation effects.

These tests are continuing compatibility evidence, not a proof over future
cultures or runtime versions. The shared verification policy remains
authoritative in [`test-plan.md`](../test-plan.md), and release eligibility
remains authoritative in [`release.md`](../release.md).

## Reconsideration conditions

Reconsider the accepted framing if GitHub removes or changes the selected
parser, if any culture or backend violates the round trip, or if an upstream
ordinal V2 parser becomes available across the supported hosted and
self-hosted runner baseline. An upstream fix alone does not cover older
self-hosted runners.

## Evidence

- [GitHub Actions workflow-command parser compatibility](../compatibility/github-actions-workflow-command-parser.md)
- [PR #42](https://github.com/send/shoutx/pull/42)
- [Upstream-report reminder #43](https://github.com/send/shoutx/issues/43)
