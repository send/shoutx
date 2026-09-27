# GitHub Actions artifact declaration decision

This document records the deferred `$GITHUB_ARTIFACTS` candidate and the
conditions for reconsidering it.

## Candidate contract

GitHub now [documents `$GITHUB_ARTIFACTS`][workflow-artifacts-command] as a
per-step command file containing one file path or OCI reference per line. A
newline in attacker-controlled input
can therefore add a second artifact subject to the job-scoped aggregate. This
is a structural output boundary and a plausible future shoutx destination, but
support remains conditional on hosted-runner availability testing.

The candidate interface is deliberately typed:

```text
shoutx github-actions:artifacts file [PATH]
shoutx github-actions:artifacts oci REFERENCE DIGEST
```

The command name follows the actual `GITHUB_ARTIFACTS` destination. The `file`
and `oci` variants prevent the runner's scheme-free syntax from guessing a
record type from its contents. Successful output always uses an explicit
scheme:

```text
file://PATH LF
oci://REFERENCE@DIGEST LF
```

There is no untyped or raw variant. `github-actions:artifacts file` follows the
usual single-value source rule: an argv `PATH` wins, otherwise stdin is read.
It consumes at most one final CRLF, LF, or bare CR as producer framing and
rejects every remaining CR or LF. `github-actions:artifacts oci` requires both
operands and never reads stdin; omitting either operand or supplying another is
a usage error.

The first token after `github-actions:artifacts` must be `file` or `oci`;
missing and unknown variants are usage errors. `--help` and `--version` are
recognized before the variant and after it while the first data operand is
still expected. A `--` before the variant is not supported. After `file` or
`oci`, `--` ends option parsing. `file --` with no PATH selects stdin. For
`oci`, option parsing ends when REFERENCE is consumed, so the following token
is always DIGEST data even when it begins with `-`.

Both variants require valid UTF-8, reject NUL and `=`, and reject an empty
semantic value. The runner trims the complete declaration before parsing it.
Because the explicit scheme protects whitespace at the beginning of PATH but a
file PATH occupies the end of its record, shoutx rejects a final scalar in the
Unicode `White_Space` property rather than silently changing identity. This is
the set used by .NET 8 `Char.IsWhiteSpace` and includes final NEL, LINE
SEPARATOR, and PARAGRAPH SEPARATOR; U+FEFF and U+200B are not members and remain
data. Other whitespace is preserved. OCI reference whitespace is internal to
its record, before `@DIGEST`, and is preserved; its semantic validity remains
the caller's responsibility.

PATH and REFERENCE each use the standard 1 MiB input limit. In addition, the
complete emitted record, including scheme and LF, must be no larger than the
runner's documented 1 MiB per-step file limit. A near-limit input can therefore
be rejected because of framing overhead. shoutx cannot account for records
already appended by other processes.

The file variant emits `file://` so a path that resembles an OCI reference
cannot change record type. Relative paths are permitted and are resolved by the
runner against `GITHUB_WORKSPACE`, not the step working directory. shoutx does
not canonicalize the path, require it to exist, resolve symlinks, translate
container paths, open it, or calculate its digest. The runner performs those
operations after the producer exits. Consequently shoutx provides record
integrity, not file identity, trust, authorization, or protection against
filesystem races.

The OCI variant accepts a reference as an opaque nonempty UTF-8 field subject
to the structural exclusions above. The caller remains responsible for OCI
reference validity and authorization. `DIGEST` must be lowercase `sha256:`,
`sha384:`, or `sha512:` followed by exactly 64, 96, or 128 lowercase
hexadecimal digits respectively. Uppercase input is rejected rather than
silently normalized. shoutx does not contact a registry or establish that the
reference resolves to the supplied digest.

The runner keys the aggregate by subject name using ordinal comparison; kind is
not part of the key. A file subject's name is only its base name, so distinct
paths with the same base name collide, as can a file base name and an equal OCI
reference. The runner deduplicates an identical name/digest pair, rejects a
conflicting digest for an existing name, and caps the job aggregate at 500
subjects.
shoutx emits one declaration, does not inspect `$GITHUB_ARTIFACTS_LIST`, and
does not promise runner acceptance in the presence of prior declarations.
`$GITHUB_ARTIFACTS_LIST` remains out of scope as a runner-managed read-only JSON
input rather than an output writer boundary.

The current runner implementation enables processing when either the
server-provided `actions_runner_allow_artifacts_file` feature flag or the
self-hosted runner process environment variable
`ACTIONS_RUNNER_ALLOW_ARTIFACTS_FILE` is true. When both are disabled it exposes
the command files but silently ignores declarations and leaves the list file at
zero bytes; when enabled with no subjects, the list contains
`{"version":1,"subjects":[]}`. Before this candidate becomes a supported
command, CI must prove on every supported hosted runner that a file declaration
appears with the expected name and digest in a later step's
`GITHUB_ARTIFACTS_LIST`. The pinned runner oracle must separately enable the
server-side feature variable without changing process-global state and exercise
the actual artifact handlers. Official documentation is the public contract,
but documentation alone is insufficient for a compatibility claim while
silent disablement exists.

The hosted-runner gate was exercised on 2026-09-28 in
[workflow run 36331651232][artifacts-availability-probe] using runner v2.337.0
on `ubuntu-latest` (`ubuntu-24.04`), `macos-latest` (`macos-26-arm64`), and
`windows-latest` (`windows-2025-vs2026`). On all three runners the declaration
file and list file variables were present, but the later step received a
zero-byte list file. This is the runner's disabled behavior, so the availability
gate failed uniformly. `github-actions:artifacts` therefore remains deferred
and must not be implemented or advertised. Reconsideration requires a new
hosted-runner probe that observes the expected subject on every supported OS;
the documented environment variables alone are not evidence that processing is
enabled.

[workflow-artifacts-command]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#declaring-workflow-artifacts
[artifacts-availability-probe]: https://github.com/send/shoutx/actions/runs/36331651232

## Threat-model rationale

### Deferred `$GITHUB_ARTIFACTS` candidate

The candidate security property is structural integrity of one typed artifact
declaration. An attacker-controlled newline must not add another file or OCI
subject to the job aggregate, and content resembling another subject type must
not change the selected type. An injected subject could corrupt the set of
materials associated with later provenance or attestation processing.

The proposed writer always emits `file://` or `oci://` and rejects record
boundaries before stdout begins. This does not establish that a declared file
is trusted, immutable, or intended. The runner resolves and opens file paths
after the producing step, follows symlinks, excludes directories, and calculates
the digest. When the step has a job container, the runner translates rooted
container paths inside known mounts and rejects rooted paths outside them;
without a container it uses the rooted path directly. Relative container paths
resolve through the host workspace context rather than the container working
directory. Other special file types are not explicitly excluded. Those
operations create filesystem-identity, blocking-I/O, and time-of-check/time-of-
use concerns outside shoutx's record-framing guarantee.

Likewise, structurally encoding an OCI reference and digest does not validate
the reference against the OCI distribution grammar, contact a registry, or
prove that the named object has that digest. Duplicate, conflicting, and
aggregate-limit behavior depends on declarations outside one shoutx
invocation.

No protection is claimed until hosted-runner testing confirms the feature is
enabled. A runner may currently expose `$GITHUB_ARTIFACTS` while silently
ignoring its contents when both its server feature flag and self-hosted opt-in
environment variable are disabled.

## Candidate verification gate

These cases define the pre-implementation gate for the
`github-actions:artifacts` candidate. They do not make the command public until
the hosted-runner availability checks pass.

### Command grammar and input

Test a missing or unknown variant as a usage error. `--help` and `--version`
succeed before the variant and after `file` or `oci` while the first data
operand is expected. `--` before the variant is not accepted. For either
variant, `--` immediately after the variant ends option parsing.

For `github-actions:artifacts file`, test `COMMAND file PATH`, `COMMAND file --
PATH`, stdin when PATH is omitted, empty argv and empty stdin, a dash-prefixed
path with and without `--`, and an extra operand. The argv value wins without
reading stdin. The stdin terminal, closed-handle, invalid UTF-8, NUL, and hard
limit cases follow the existing single-value rules. `COMMAND file --` selects
stdin. A dash-prefixed PATH without `--` is an unknown-option usage error. The
command has no line mode options.

For `github-actions:artifacts oci`, require exactly `REFERENCE DIGEST` after
option parsing. It never reads stdin. Missing or extra operands, an unknown
option, or a dash-prefixed reference without `--` are usage errors with status
2 and empty stdout. Once REFERENCE is consumed, a dash-prefixed DIGEST is data
and fails digest validation with status 1. Empty operands and values that fail
field validation are input errors with status 1 and empty stdout.

### File declarations

A successful file declaration has exact stdout:

```text
file://PATH LF
```

Cover relative, absolute, Unicode, internal-space, leading-space, URI-looking,
OCI-looking, and `#`-prefixed paths on Linux, macOS, and Windows. The explicit
`file://` prefix must force file interpretation and prevent comment skipping.
Consume at most one final CRLF, LF, or bare CR from PATH as producer framing.
Reject an empty result, remaining CR or LF, NUL, `=`, and every trailing scalar
in the Unicode `White_Space` property. Include final NEL, LINE SEPARATOR, and
PARAGRAPH SEPARATOR rejections, plus U+FEFF and U+200B preservation. Assert
empty stdout for every rejection.

The local model must reproduce only runner parsing and resolution behavior
needed for comparison: full-line Unicode trimming, explicit scheme selection,
relative resolution against `GITHUB_WORKSPACE`, native rooted-path handling with
a null container, rooted translation and outside-mount rejection with a job
container, directory exclusion, symlink behavior, base-name selection, and
SHA-256 calculation. Add a relative-container case to verify that it resolves
through the host workspace context. Test these as runner facts, not as
transformations or authorization performed by shoutx. Include a file that
changes between shoutx output and runner processing to demonstrate that shoutx
does not bind file identity or digest. Do not assert that the runner excludes
every non-regular special file.

### OCI declarations

A successful OCI declaration has exact stdout:

```text
oci://REFERENCE@DIGEST LF
```

Test each supported algorithm at its exact lowercase hexadecimal length:
`sha256` with 64 digits, `sha384` with 96, and `sha512` with 128. Reject an
unknown or uppercase algorithm, uppercase or non-hex digits, short and long
digests, empty reference or digest, NUL, CR, LF, and `=`. Include references
containing tags, registry ports, internal `@`, leading or trailing whitespace,
and strings resembling file paths. Verify that the runner returns the exact
reference and digest. The runner lowercases algorithm and hex internally; on
valid shoutx output this normalization must be a no-op.

### Limits, aggregation, and availability

Test records immediately below, at, and above the runner's 1 MiB per-step
command-file limit. A shoutx invocation must reject when its own complete
record exceeds the limit, but tests must not imply that it knows how many bytes
another process already appended. Through the actual runner handler, cover
identical deduplication, same-name conflicting digests, ordinal name
comparison, the 500-subject aggregate cap, and parse-level all-or-nothing
behavior for a step containing a malformed declaration. Parse-level failures
occur before aggregation and add nothing. Conflict and cap failures occur
during aggregation and leave subjects inserted earlier by that same step;
assert this non-transactional runner behavior explicitly.

The pinned runner differential test explicitly enables the server-side
`actions_runner_allow_artifacts_file` variable, without mutating the process
environment, and calls the actual write and list handlers. Separately test the
self-hosted `ACTIONS_RUNNER_ALLOW_ARTIFACTS_FILE` fallback with state restored
afterward. A hosted workflow probe on every supported runner writes a known
temporary file, appends the candidate encoding, and verifies in a later step
that `GITHUB_ARTIFACTS_LIST` contains exactly the expected base name, SHA-256
digest, and `file` kind. It must fail rather than skip when the variable is
absent, the list file is zero bytes, the enabled empty-list JSON remains
unchanged, or the expected subject is absent. Public support is blocked until
this probe passes across the supported matrix.

The recorded hosted-probe result and the condition for reconsideration are
stated in the candidate contract above. Repeat the same positive-subject
assertion before starting implementation.

## Candidate implementation notes

Do not implement or advertise this command until its hosted-runner availability
gate passes. The parser must implement the typed interface defined above.

Keep artifact validation separate from named records and PATH mutation. The
file variant may reuse bounded argv/stdin acquisition and final-boundary
consumption, but it has no lossy line modes. The OCI variant is a structured
two-operand command and never consults stdin. Both variants build the complete
explicit-scheme record and validate its encoded size before stdout is opened.

Add a dedicated runner oracle around `CreateArtifactsFileCommand` and
`ArtifactsListFileCommand`. Enable the pinned runner's server-side feature
variable explicitly without mutating process-global state, exercise real
temporary files and native path semantics, and compare the job-scoped aggregate
and JSON list rather than transcribing only the line parser. Test the
self-hosted process-environment fallback separately with cleanup. Test rooted
paths once with a null container and separately with a real `ContainerInfo`
mapping, including outside-mount rejection; a relative container case uses the
host workspace context. The oracle must cover Unicode trimming, schemes,
directory exclusion, hashing, name collisions, deduplication, conflicts,
partial aggregation on conflict or cap failure, and limits without turning
those runner behaviors into shoutx guarantees.

Before implementation, rerun the hosted availability gate defined above. The
mere presence of `GITHUB_ARTIFACTS` is insufficient; the probe must observe the
declared subject in a subsequent step on every supported operating system.
