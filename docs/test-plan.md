# CLI contract test plan

This document defines the test layers, shared input cases, runner differential
strategy, and supported-shell matrix for the `shoutx` CLI. Command-specific
matrices are colocated with the specifications linked below.

The [documentation map](README.md) assigns cross-cutting product requirements
to [design.md](design.md), destination contracts to the linked
[`commands/`](commands/) specifications, and the security boundary by
[threat-model.md](threat-model.md). If this plan disagrees with those files,
the disagreement must be resolved rather than silently encoded in a test.
The [Rust implementation plan](implementation-plan.md) maps these cases to the
current architecture without changing their expected behavior.

## Test layers

The implementation should be tested at four layers:

1. **CLI contract tests** invoke the built executable and assert stdout bytes,
   stderr policy, and exit status.
2. **Encoder property tests** generate names and values and assert that every
   successful record parses to exactly one requested name/value pair.
3. **Runner differential tests** feed emitted bytes to the parser from a pinned
   `actions/runner` release and compare its result with the local parser model.
4. **Workflow smoke tests** exercise documented redirection forms on GitHub-
   hosted runners. These detect integration drift but are not a stable semantic
   oracle because the hosted runner version changes independently.

Tests that expect validation, normalization, delimiter selection, randomness,
or size failure must assert empty stdout. Tests that deliberately cause stdout
I/O failure may observe a prefix and must assert status 1 without assuming
transactional output.

## Build-configuration matrix

### Complementary static analysis

The [CodeQL workflow](../.github/workflows/codeql.yml) analyzes Rust and GitHub
Actions with the security-extended query suite on pull requests, main updates,
and a weekly schedule. It runs independently of the CI change detector so
scheduled queries can inspect unchanged code. Rust uses CodeQL's supported
`none` build mode, not a replacement stable/research Cargo build matrix.
CodeQL supplements Clippy, dependency checks, and the contract tests; a clean
scan does not prove output framing, empty-stdout failure behavior, or runner
compatibility. Required CI and release gates remain unchanged.

### Executable configurations

The stable configuration uses `--no-default-features`; the Cargo default
feature set must remain empty. Its complete command table is exactly `output`,
`env`, `state`, and `path`. Stable help is byte-equal to the reviewed LF golden,
and the four stdout research names must produce the ordinary unknown-command
diagnostic, status 2, and empty stdout with otherwise successful arguments.

The research configuration uses the exact feature
`unstable-github-actions-stdout`. It runs the mask and annotation contract,
corpus, hosted, and runner differential suites and identifies itself in help
and version output. Stable and research builds use separate Cargo target
directories. Every research CI group explicitly selects its feature and has a
feature-on sentinel. Focused corpus and oracle jobs explicitly select test
targets whose `required-features` fail when the feature is missing, then remove
old corpus files and require fresh non-empty outputs. Implicit Cargo target
selection alone is not treated as evidence because it may skip a target.

Source-configuration tests check the complete command table; compile-time
exhaustive dispatch proves that omitted action variants cannot reach an
implementation. The artifact verifier independently checks exact help and
version, successful-form negative invocations, and enumerated binary markers.
Marker scans use a same-target, same-profile feature-enabled binary as a
positive control. The marker set is the four unstable command names. Protocol
prefixes are not evidence because compiler optimization need not retain their
source constants as contiguous bytes. Dependency graphs are checked separately
for both feature configurations. The artifact verifier never prints or uploads
captured stdout, stderr, help, or version bytes on failure; its reports contain
only lengths. Release packaging reruns that verifier against every extracted
native executable.

## Notation

Tables use `LF`, `CR`, and `CRLF` for their corresponding bytes. `BOM` means
the UTF-8 encoding of U+FEFF. `parse(record)` means parsing the complete stdout
with the destination parser on the named platform. Unless stated otherwise,
the name is `result`, input is supplied as one argv value, and success means
status 0 with empty stderr.

For single-line output, environment, and state records, exact stdout is:

```text
NAME=VALUE LF
```

For multiline records, the generated delimiter is nondeterministic. Tests must
validate its grammar and uniqueness, then use the parser result as the oracle
instead of comparing the complete record with a fixture.

## Command-line grammar

Run applicable cases for `github-actions:output`, `github-actions:env`, and
`github-actions:state`.

| Case | Invocation shape | Expected result |
| --- | --- | --- |
| Value operand | `COMMAND NAME VALUE` | `VALUE` is used; stdin is ignored |
| Empty value operand | `COMMAND NAME ""` | Empty value succeeds |
| Dash-prefixed value | `COMMAND NAME -x` | `-x` is value data |
| Literal dash | `COMMAND NAME -` | `-` is value data, not stdin syntax |
| End options | `COMMAND -- NAME VALUE` | Normal success |
| End-options token after name | `COMMAND NAME --` | `--` is the value |
| Mode before name | `COMMAND --first-line NAME VALUE` | Selected mode is applied |
| Mode after name | `COMMAND NAME --first-line` | Token is the value |
| Help before name | `COMMAND --help` | Help on stdout, status 0 |
| Help after name | `COMMAND NAME --help` | Token is the value |
| Version in option position | `shoutx --version` | Exact stable bytes from the design contract on stdout, empty stderr, status 0 |
| Command version before name | `COMMAND --version` | Exact stable bytes from the design contract on stdout, empty stderr, status 0 |
| Version after name | `COMMAND NAME --version` | Token is the value |
| Missing name | `COMMAND` with any stdin state | Do not read stdin; usage diagnostic, status 2 |
| Extra operand | `COMMAND NAME A B` | Usage diagnostic, status 2, empty stdout |
| Conflicting modes | Two mode options | Usage diagnostic, status 2, empty stdout |
| Missing separator | `--join-lines-with` without its argument | Usage diagnostic, status 2, empty stdout |
| Dash separator | `--join-lines-with -x NAME VALUE` | `-x` is the separator |
| Equals separator | `--join-lines-with=-x NAME VALUE` | `-x` is the separator |
| Empty separator | `--join-lines-with= NAME VALUE` | Empty separator succeeds |
| Unknown option | Unknown token before `NAME` | Usage diagnostic, status 2, empty stdout |

For `github-actions:path`, test `COMMAND VALUE`, `COMMAND -- VALUE`, stdin when
VALUE is omitted, and rejection of an extra operand. `--` is required to pass a
value beginning with `-`; without it, the token is an unknown option. Options
other than global help/version and `--` are usage errors. Help and version are
recognized only before VALUE. `COMMAND VALUE --help` is an extra-operand usage
error with status 2 and empty stdout. `COMMAND --` with no following token
selects stdin rather than an empty argv value.

## Input-source selection

| VALUE operand | Stdin state | Expected source and result |
| --- | --- | --- |
| Present | Any bytes, terminal, or closed | Use VALUE without reading stdin |
| Omitted | Non-terminal with bytes within limit | Read through EOF and use all bytes |
| Omitted | Non-terminal exceeding limit | May stop after the first excess byte; status 1 and empty stdout |
| Omitted | Non-terminal at EOF | Empty value |
| Omitted | Terminal | Do not wait; status 2 and empty stdout |
| Omitted | POSIX descriptor closed before process startup | Runtime substitutes `/dev/null`; empty value |
| Omitted | Invalid Windows handle | I/O diagnostic, status 1 and empty stdout |

The argv and stdin variants of every value-validation case must have identical
semantic results where the host process API can represent the value. NUL
requires byte-oriented stdin because host argument APIs cannot represent it.
Invalid UTF-8 requires both byte-oriented stdin and POSIX argv cases. On
Windows, use a small native launcher to pass an unpaired UTF-16 surrogate and
assert status 1 with empty stdout rather than a panic or process abort.
For `github-actions:path`, empty argv and empty stdin are input failures with
status 1 rather than successful empty records.

## Command-specific suites

Detailed command matrices are colocated with their specifications:

- [GitHub Actions named records](commands/github-actions-records.md)
- [GitHub Actions PATH writer](commands/github-actions-path.md)
- [GitHub Actions log-mask command](commands/github-actions-mask.md)
- [GitHub Actions annotation commands](commands/github-actions-annotations.md)

Deferred candidate gates live with their decision records:

- [GitHub Actions artifact declarations](decisions/github-actions-artifacts.md)

## Text validation

Run these cases in every mode, including data that `--first-line` would later
discard.

| Input | Expected result |
| --- | --- |
| Valid ASCII and multibyte UTF-8 | Accepted subject to mode rules |
| BOM at beginning, middle, or end | Preserved as U+FEFF value data |
| Unicode NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR | Preserved as ordinary data |
| Overlong, truncated, surrogate, or otherwise invalid UTF-8 | Status 1, empty stdout |
| NUL at beginning, middle, or end | Status 1, empty stdout |
| Valid prefix, first boundary, then invalid UTF-8 or NUL | Status 1, empty stdout |

Successful output must be valid UTF-8 without an encoder-added BOM.

## Non-multiline line semantics

All non-multiline modes first consume at most one final boundary. The following
matrix is normative; replace notation with actual bytes in tests.

| Input | Default | `--first-line` | `--join-lines` |
| --- | --- | --- | --- |
| empty | empty | empty | empty |
| `a` | `a` | `a` | `a` |
| `a LF` | `a` | `a` | `a` |
| `a CR` | `a` | `a` | `a` |
| `a CRLF` | `a` | `a` | `a` |
| `a LF LF` | reject | `a` | `a ` |
| `a CRLF CRLF` | reject | `a` | `a ` |
| `a CR CR` | reject | `a` | `a ` |
| `a LF b LF` | reject | `a` | `a b` |
| `a CR b CR` | reject | `a` | `a b` |
| `a CRLF b CRLF` | reject | `a` | `a b` |
| `LF a` | reject | empty | ` a` |
| `a LF CR` | reject | `a` | `a ` |
| `a CR LF` | `a` | `a` | `a` |

The final row is one CRLF boundary, not two boundaries. Add generated cases
that tokenize arbitrary sequences using the precedence `CRLF`, then bare `CR`
or `LF`. For `--join-lines-with STRING`, use the same cases with each remaining
boundary replaced by exactly one copy of `STRING`; include empty, ASCII,
multibyte, and 255-byte separators.

Reject separators containing NUL, CR, or LF and separators longer than 255
UTF-8 bytes. Separator validation happens even when the input has no boundary.

`github-actions:path` uses the same optional-final-boundary preprocessing as
the table, then rejects an empty result or any remaining boundary.

## Limits and failure behavior

Test values of 1,048,575, 1,048,576, and 1,048,577 UTF-8 bytes before optional
final-boundary consumption through stdin and directly against the library argv
input path. Host argument-block limits make executable-level argv tests at these
sizes non-portable. The first two sizes succeed if otherwise valid; the last
fails with status 1 and empty stdout. Include a value at or below the input limit
whose many boundaries and 255-byte join separator would expand far beyond 1
MiB. Assert rejection using checked size arithmetic before allocating the
normalized result.

Test names and separators at 254, 255, and 256 bytes. Limits are byte counts,
not Unicode scalar counts. Names are ASCII by grammar; separators need
multibyte cases.

Diagnostics must identify the failed rule without containing the supplied
name, value, separator, generated delimiter, or excerpts derived from them.
Capture stdout and stderr separately. Include a value resembling
`::stop-commands::TOKEN` to ensure it is never copied to a diagnostic. Assert
that no fixed diagnostic line begins with `::`, because runner command handling
can observe stderr as well as stdout.

Cause a broken pipe and another short/failed stdout write using deterministic
synchronization or an injected test writer rather than a scheduling race. The
process must ignore SIGPIPE as a termination mechanism, report an I/O failure on
stderr, and exit 1. A partial stdout prefix is permitted only after writing
began. An invalid Windows stdout handle must also produce status 1. On POSIX,
test and document that a descriptor closed before startup is replaced with
`/dev/null`, so the process cannot detect the discard and may exit 0.

## Runner parser model

The local model should implement only the environment-file behavior needed as
a test oracle, keeping platform line-reading behavior explicit. Given complete
UTF-8 file bytes and a platform mode, it returns an ordered list of parsed
records or the runner-equivalent parse error.

The model must cover:

- normal `NAME=VALUE` records;
- `NAME<<DELIMITER` records;
- ordinal delimiter comparison;
- LF and Windows CRLF line consumption;
- end indices used to extract multiline values without their framing newline;
- empty values and an absent final record terminator;
- malformed headers, missing delimiters, and trailing bare CR; and
- the runner's missing-newline error for an EOF marker with no preceding line
  terminator.

The model is not production code and must not become the sole compatibility
oracle. Unit tests should be derived from inspected runner source before the
model is used to validate the encoder.

The path command uses a separate model of `File.ReadAllLines(...,
Encoding.UTF8)` and `AddPathFileCommand`; it must not reuse the named-record
model. Its required cases and ordering assertions are specified in the
[PATH command specification](commands/github-actions-path.md#runner-parser-and-effective-ordering).

## Differential testing against `actions/runner`

Pin the initial oracle to `actions/runner` v2.337.0. Record both the tag and
resolved commit in the test fixture or dependency metadata. The harness should
compile or invoke the actual environment-file parser from that checkout; a
second handwritten transcription is not an independent oracle.

Run the same corpus through the local model and actual runner parser on the CI
platform matrix defined in `.github/workflows/ci.yml`. Compare ordered names,
exact values, record counts, and success or failure. The corpus includes
applicable deterministic cases
from this document and the linked command specifications, including:

- generated valid names and UTF-8 values across every line mode;
- malformed records that exercise parser error paths;
- delimiter-like substrings at every position;
- empty and unterminated files; and
- Windows trailing-bare-CR multiline framing.

Before each release, inspect the current `actions/runner` source and run the
suite against the newest supported release in addition to the pinned baseline.
A behavior difference blocks a compatibility claim until it is explained and
the contract, model, or supported-version declaration is updated.

### Published Runner runtime evidence

In addition to the source-built oracle, run a small probe against the pinned
published Runner package on the differential CI OS matrix. Verify a reviewed
archive SHA-256 before extraction or execution. Use the package's unmodified
worker runtime configuration, dependency manifest, runtime binaries, and
`Runner.Common` parser assembly; fail if the probe loads its core library or
parser from outside that package. Do not register a runner or start a job worker.

Save machine-readable evidence as a CI artifact: archive and relevant assembly
digests, runtime/build identity, OS/architecture, explicit tested cultures,
globalization flags (including unavailable values), sort version, parser
checks, and matching pinned .NET source digests. Record separately whether
an ICU fast-path precondition was observed. Unknown/NLS observations must not
be presented as confirmation of an ICU source argument. Preserve failure
evidence as well as successful results; absence of fresh evidence fails CI.

This is a package-backed component probe, not an unmodified hosted Worker process
measurement or proof of every Unicode sequence, culture, backend, or runner
version. Under Invariant Culture and `en-US`, also drive the package's actual
OutputManager, ActionCommandManager, command extensions, SecretMasker and
ExecutionContext issue/log handling. Keep only host service discovery, log
storage and server queues synthetic; unexpected service calls fail the probe.
Do not rebuild or transcribe those production implementations.

Use fresh execution state for every corpus case. Check complete and derived
mask registration, subsequent redacted log output, annotation severity,
message and platform-specific properties. Require stopped commands to be
ordinary log output with no mask/issue effect, then verify matching-token
resume restores each command. Include echo suppression, masked annotation
messages and real step-completion annotation conversion. Record executed case
counts and the loaded Worker/SDK assembly identities; missing coverage fails
the harness. Server upload, problem matchers, containers and all other cultures
remain outside this package suite, with broader policies covered by the
source-built oracle and live hosted checks. Neither suite changes stdout
release eligibility or the deferred `th-TH` decision.

### Isolated Unicode implementation verification

The current original-value expansion is specified by the
[annotation](commands/github-actions-annotations.md) and
[mask](commands/github-actions-mask.md) contracts. Its
[decision record](decisions/stdout-unicode-acceptance.md) supersedes the earlier
research work order for this implementation; the historical investigation below
is retained evidence, not a requirement to certify dependency internals.

Verify exact producer bytes and empty stdout on rejection, exhaustive static
lookup agreement with the checked-in membership input, pinned parser round
trips, and actual Worker masking/annotation effects. Metadata tests must include
final TITLE and final FILE, not only a property followed by numeric fields.
The Unicode-property terminator must preserve values and must not create an
extra decoded property. Preserve old ASCII output bytes and consumer-state
negative controls. Run the four-OS Invariant/en-US integration matrix and record
its runtime identities; finite integration is not arbitrary-input proof.

Use `python3 scripts/generate-stdout-start-table.py --check` to verify the
generated representation. Acceptance-set changes require explicit review of
membership and its evidence; renderer success alone is not evidence of safety.
Compare release-mode CLI performance with the recorded, predeclared method in
[the evidence note](compatibility/stdout-unicode-policy.md#producer-performance).
Normal stable/unstable Cargo and Runner oracle gates remain required. Neither
completion here nor any old investigation section enables stable distribution.

<a id="unicode-adoption-completion-criteria"></a>

### Unicode adoption completion criteria (historical research plan)

This section and the native-research sections through **Offline root mapping
graph research** retain the old investigation's criteria and harness semantics.
They are not current adoption completion gates. Their unresolved premises are
not declared proven. The superseding
[framing decision](decisions/github-actions-stdout-framing.md) and the current
verification section below do not require new internal proofs. Existing
executable CI checks remain enabled: a failure must be classified as a relevant
product regression, compatibility drift, or research-instrumentation issue;
this historical label does not authorize ignoring failed CI.

The [research-scope decision](decisions/github-actions-unicode-scope.md) fixes
the initial target; it does not expand CLI acceptance or release eligibility.
Use the dated latest-release baseline in the
[package evidence note](compatibility/runner-package-runtime.md#research-baseline-selection)
and the reviewed archive/source identities in `tests/runner-package/pins.json`.
The initial matrix below snapshots `runner-differential` on the 2026-10-04
scope-decision date. It defines the research target until explicitly revised;
subsequent CI edits do not silently add or remove target rows:

| Hosted CI row | Package architecture | Explicit comparison cultures |
| --- | --- | --- |
| `ubuntu-22.04` | `linux-x64` | Invariant, `en-US` |
| `ubuntu-24.04` | `linux-x64` | Invariant, `en-US` |
| `macos-15` | `osx-arm64` | Invariant, `en-US` |
| `windows-latest` | `win-x64` | Invariant, `en-US` |

These are execution selectors, not immutable OS/backend identities. Retain
the resolved image, OS, architecture, package, runtime, native code/data,
effective settings and observed search/break path for each row and culture.
Explicit Invariant Culture does not enable globalization-invariant mode.
Local research results cannot substitute for a missing row. Do not infer
live Worker culture from these explicitly configured probes or child locale.

The recorded reference snapshots are ubuntu22 / 20260927.309.1,
ubuntu24 / 20260927.320.1, macos15 / 20260907.0337.1 and
win25-vs2026 / 20260925.250.1, respectively. Their observations are retained in
the [feasibility audit](compatibility/unicode-feasibility.md#same-job-observations-after-pr-74).
A current run on the same selector is not necessarily that reference.

The [2026-10-05 scope revision](decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements)
replaces mandatory live Worker linkage with reference-configuration validation
and explicit deployment applicability conditions. Use the
[proposed reference definition](decisions/github-actions-stdout-framing.md#proposed-reference-configuration-boundary),
including package startup and the normal prefilter/parser/extension path.
For each row/culture record package/runtime/native identities, enumerated
startup inputs and their provenance, effective settings and data, and any
difference between the probe harness and that normal path. A successful
explicit-culture probe alone does not establish those correspondences.
The [reference/probe correspondence](compatibility/reference-worker-correspondence.md)
records the bounded host-handoff subclaim and a hash-gated reproduction of
selected original trace fields. That check must match report and trace hashes
before emitting the projection; it neither publishes full logs nor substitutes
initialization properties for native/data or command-path equivalence.

Live observations remain separate interoperability evidence. Record their
run/attempt/job IDs, resolved image/version, architecture and Runner version.
The ordinary live experiment has a different selector matrix, so do not
silently equate `macos-latest` with macOS 15 or `ubuntu-latest` with both
Ubuntu rows. A mismatched observation supports only its own combination.
The [package-matched experiment](#package-matched-feasibility-observations)
provides historical same-job observations, not complete deployment attestation.

Record each deployment condition as observed, unobserved or known-mismatching.
Neither package hashes nor finite API effects establish live culture or loaded
code/data identity. In particular, do not infer the
[server-supplied culture input](compatibility/github-actions-workflow-command-parser.md#finding)
from child locale. Unobserved live Invariant remains unobserved even if
`en-US` is observed. Missing deployment attestation alone no longer blocks
reference-data acquisition or the research recommendation.

Within the reference, native selection, effective mappings/settings and the
probe-to-normal-path argument remain necessary per culture. Acquisition-target
identification permits acquiring data; it is not proof of the acquired data's
contents or of the full parser property. Follow the scope decision's work order
and evidence-insufficient No-Go rule if required reference inputs cannot be
obtained. Ordinary unfinished analysis remains incomplete. Never replace a
missing reference premise with a deployment assumption.

The following are completion checks for proposing Unicode acceptance, not
claims that the current research gate has satisfied them. All are required;
failure/unknown in a prerequisite is not a successful empty result.

| Obligation | Required closure evidence | Current gap / evidence owner |
| --- | --- | --- |
| Effective consumer inputs | Bind the executed package and native implementation, settings, effective tailoring/root mappings and relevant normalization/break properties to the reference configuration's normal consumer path on every row/culture; archive hashes and reproducible acquisition/validation steps. Justify source-to-binary and probe-to-normal-path inferences explicitly. Deployment identity is a separate applicability condition. | Package identity and native observations are partial evidence; the separately opened local root is not the cached collator's proven effective data. See [package identity limits](compatibility/runner-package-runtime.md#identity-chain) and [acquisition research](compatibility/github-actions-workflow-command-parser.md#mapping-data-acquisition-feasibility-local-research). |
| Full data prerequisites | Check the positive leading-weight condition and complete reachable dispatch/rank premises against those effective inputs, including base/tailoring resolution and supplementary summaries; all unsupported references or exhausted bounds stay unverified. | Existing readers are root-only and model 78.1; they do not cover the entire target matrix. See [structural graph research](compatibility/github-actions-workflow-command-parser.md#single-root-structural-graph-experiment). |
| Header, iterator and search composition | Close the fixed-header/prefix and intended-delimiter argument, incoming iterator state, colon FCD/context handling, retained first raw half, offset/termination conditions and external end boundary for arbitrary permitted wire suffixes, at the effective settings. Address resource assumptions separately from mathematical termination. | Existing conditional arguments leave premises open. See [source obligations](compatibility/github-actions-workflow-command-parser.md#remaining-source-argument) and [delimiter entry step](compatibility/github-actions-workflow-command-parser.md#delimiter-mapping-and-conditional-entry-state-step). |
| Independent execution and hosted interoperability | Exercise reference package prefilter/parser/Worker effects, retain identities and negative controls, and continue obtaining and retaining hosted boundary checks as interoperability/regression evidence for their recorded configurations, separately from reference results. Hosted checks neither close nor replace reference proof obligations. New hosted runs support only their recorded configuration, not an unavailable historical image. Preserve retrievable evidence and apply the scope decision's acquisition rule when the reference cannot be reproduced. | Package and live hosted measurements are distinct; finite cases do not establish arbitrary-suffix safety or an unobserved live culture. See [published runtime checks](#published-runner-runtime-evidence) and [live hosted checks](#live-hosted-stdout-boundary-experiment). |
| Adoption and updates | Review the candidate predicate across all target combinations, reproducible generation, lookup cost, fail-before-output verification plan, deployment prerequisites, unknown/updated environments and security response. Record the proposed invariant 16 reconciliation in the framing decision; change normative contracts only in a separately approved coordinated adoption change. | The [approved research scope](decisions/github-actions-unicode-scope.md) authorizes a recommendation and research artifacts, not a product table or changed acceptance contract. [Continuing checks](#continuing-compatibility-checks) do not automatically certify a new environment; framing and release decisions remain separate. |

For closure, preserve the necessary redacted reports, source/run identities,
hashes and reproduction instructions in repository-versioned evidence before
the existing 30-day CI artifacts expire. Link the adopting commit to those
records; temporary paths and expired artifact URLs alone are insufficient.
Do not commit secrets, full job logs or vendor ICU payloads. Raw vendor data
and substantial derived extracts (such as mapping tables or graph dumps) must
not be published through repository commits, CI artifact uploads or other
sharing channels without separate permission/license review. Retain hashes and
acquisition instructions for an appropriately licensed environment instead.
If those records cannot support reproducing a required input/claim, that
obligation remains unverified rather than assuming a hash supplies the bytes.
This adds no artifact-retention automation or permission to publish payloads.

Work order and handling of blocked obligations are owned by the
[scope decision](decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements).
Completion here permits proposing the acceptance change; stable distribution
still requires the separate
[framing](decisions/github-actions-stdout-framing.md) and
[release](release.md) gates. Existing other-culture regressions are retained,
not expanded into additional support obligations by this checklist.

#### Unicode generation and implementation verification plan

This is the prospective implementation plan for the adoption-and-updates
obligation, not a claim that the predicate is proved or a product table exists.
The research goal requires this plan; implementing new CLI acceptance remains
a separate, maintainer-approved task. The existing UCD-derived candidate and
`tests/unicode_candidate_lookup.rs` are research artifacts, not a validated
intersection of the eight reference configurations.

After the effective-data and arbitrary-suffix obligations close, specify a
generation manifest that identifies each reference/culture, effective input
hashes, predicate revision, generator revision and output digest. Derive the
common positive set from all eight justified inputs. An unresolved row or
unsupported data reference must fail verification, not silently remove that
row or certify an empty result. Preserve the existing ASCII union only with
its separate composition argument; do not select by language or hide failures
through trimming or lossy normalization.

For a range-table design, require canonical sorted, disjoint scalar ranges,
scalar-valid endpoints, deterministic byte-for-byte regeneration, and exhaustive
lookup-versus-generated-membership checks. Record reproducible commands and
input acquisition identities under the evidence-retention rules above. A
future generator should validate the complete result before replacing its
output, test failure without replacement, and document its atomic-replacement
and durability limits. The current research generator's direct file write is
not evidence of that property. Publication of vendor data or substantial
derived tables still requires the separate permission/license review above.

An update must review changed inputs and predicates, added/removed ranges,
and the affected proofs across the complete matrix before regenerating an
adoption artifact. Moving CI labels or a newer Unicode version are not automatic
approval. The proposed production representation is an embedded static table,
not runtime JSON parsing, downloading, or consulting producer Unicode tables.

If the proved rule depends only on the first scalar, a binary search of `R`
ranges costs `O(log R)` with `O(R)` read-only table space; decoding that scalar
from an already validated UTF-8 string examines at most four bytes. This does
not remove whole-input validation/encoding: those retain their `O(N)` work
for `N` input bytes. These are conditional bounds, not measured CLI results.
If the suffix proof requires additional scanning/state, revise the algorithm
and bounds before recommending adoption.

Extend the existing warmed-lookup experiment with measurements of the eventual
integration on each target OS/architecture. Separate process startup, input
validation/encoding, lookup and end-to-end cost. Compare against the existing
ASCII policy using short and maximum-size values/metadata, range edges,
accepted and rejected starts including supplementary scalars, escape-heavy
inputs and permitted adversarial suffixes. Record build/toolchain/configuration
identities, repeated timing distributions and peak memory. Explain the proposed
regression budget before using it as a pass/fail criterion; the current manual
microbenchmark has no timing gate and cannot establish unchanged CLI performance.

The eventual CLI tests must cover malformed encoding on supported input
routes, rejected starts, invalid typed metadata, input/encoded-size limits,
and allocation/resource failures that the implementation can handle. Use
controlled fault injection where needed rather than unsafe resource exhaustion;
document failures the runtime cannot catch. For each handled rejection assert
empty stdout, exact exit status and the documented stderr policy. Check successful
wire bytes and decoded values/properties/effects with the independently
characterized reference path in both cultures. These finite tests complement,
not replace, the suffix proof. Do not promise rollback after output starts.

#### Source/configuration acquisition-target checks

Limits of a collector's measurements are not an extra demand for memory dumps
or an exhaustive reflection proof.
The existing [trust assumptions](threat-model.md#trust-assumptions) already
trust the workflow, Runner and OS and exclude arbitrary attacker code in the
same job. Excluding hostile file/log replacement or injected culture changes
under that model is not a new guarantee against them. Ordinary trusted
dependencies and startup configuration still require analysis; trust does not
mean that the intended backend was selected.

The reference source/configuration claim has the following form:
**under the enumerated startup inputs and comparison culture C, the reference
package's normal consumer path uses the implementation/settings characterized
by its probe under C**, independently for Invariant and `en-US`. Account for
package-defined culture defaults, execution-context propagation and caches in
that normal path. This is not a claim that a live job ran under both cultures
or used those inputs. Actual server inputs and live propagation are separately
recorded applicability conditions. Effective mappings for each reference
culture still require their own acquisition argument.

The source route's acquisition-target checklist is below. Completing it is
necessary but not sufficient for reference-correctness closure: the effective-
data binding in the Effective consumer inputs row is subsequent work under the
scope decision's ordering. The 2026-10-05 revision removes live-deployment
absence attestation, not these reference-package checks.

1. State the official-package/source correspondence inference, loader resolution
   and reference-run file-continuity assumptions explicitly. File
   matches can support, but do not independently prove, these inferences. Resolve
   ordinary dependency behaviour rather than demand defence against hostile
   instrumentation outside the threat model.
2. Account for relevant culture setters/defaults/cache resets on the output
   call path, including package dependencies. A package-side managed metadata
   scan of the managed assemblies resolved by the hash-matched `deps.json`,
   targeting the member/search families in the
   [parser source note](compatibility/github-actions-workflow-command-parser.md#processing-culture-connection-still-to-establish), is a bounded
   next check. Absence of direct references is not proof that reflection is
   impossible. Unresolved effects of package dependencies on the normal
   reference path keep that obligation open until justified by source/path
   analysis; they cannot become deployment assumptions merely because the
   Runner is trusted.
3. Resolve each applicable startup-selection input (invariant/NLS mode, app-local
   ICU and version selection, predefined-culture restrictions, and relevant
   loader/data configuration) within the reference, by observation plus
   fixed-source reasoning or an explicit justified configuration inference.
   An input may be irrelevant once the resolved outcome is established; its
   raw value is not inherently required. For deployment-supplied inputs,
   enumerate reference values grounded in corresponding recorded observations
   or package defaults and justify their effects. Record the actual live value
   independently as an applicability condition; it may remain unobserved.
   Do not relabel a live unknown as absent or presume an unknown package-defined
   outcome is the intended one.
4. Identify the resolved native instance and locale-to-collator selection route
   that each explicit culture's acquisition plan must target, and connect this
   route to the reference package observation. This identifies the justified
   acquisition target, not completed reference correctness. Acquiring/binding the
   actual mappings and normalization/break inputs follows under the Effective
   consumer inputs row; it is not a prerequisite for identifying the target.
   Module names and equal break-rule hashes alone cannot identify that route.

No loaded-memory measurement or proof that deployment-added hooks/sidecars are
absent is a mandatory additional item. If a necessary reference input remains
unobtainable after source analysis and justified alternatives, apply the scope
decision's evidence-insufficient recommendation rule. Do not weaken the matrix
or presume the content of missing reference data. An unobserved live input
alone does not require extending the collector or stopping reference analysis.

#### Package environment transport control

The package probe executes the published `Runner.Sdk.ProcessInvoker` against
the harness's absolute Python executable, using `-I -S` and the actual
`hosted_worker.py` presence function. The probe's managed parent selectors must
be absent before testing four child overlays: absent, empty, null, and a fixed
synthetic text value for all six observed configuration keys. Require exact
presence results, synthetic-value comparisons and a parent managed-environment
marker inherited in every case. Values are never emitted. The null case tests
the pinned .NET serializer; Python fixtures supply its expected empty string,
not a Python null environment value. The marker is restored in `finally`;
globalization keys are assigned only to the Python child's overlay, never the
probe parent's environment.

Require success under the package's verified runtime, a 30-second child timeout,
zero stderr, one JSON output line of at most 4096 characters (checked after
buffering, not a bounded-read guarantee), and exact complete result coverage.
Require the invoker and Process assemblies in the hash-verified loaded-assembly
inventory. Run transport after the existing parser/collation phases; a transport
failure must fail the overall probe without discarding those earlier results.
On the first transport counterexample, record the active case and validated
fixed-field mismatch summary, never raw child output; later cases are not run
and are not reported as passed. Launch/JSON/type errors instead retain exception
type and active case, without exception text. Snapshot completed earlier phases
before transport. The harness verifies earlier evidence and file continuity
before the transport gate, recording `preTransportEvidenceVerified`; that flag
does not make the overall failed row successful.
Offline child/verifier tests include missing/extra state, wrong value, absent
marker, invalid mode, missing observations and integer-instead-of-boolean
controls. The positive subprocess fixtures themselves test platform-dependent
Python empty-entry behavior. Run them after package execution in all four rows,
in an independent always-run step: neither test result prevents collecting the
other. They still fail CI and cannot replace the .NET-to-Python experiment.
The inheritance marker must initially be absent, so cleanup cannot overwrite
an existing empty-valued marker. Retain producer source hashes with the package
report, including the child and observer functions.

This tests the SDK invoker-to-Python suffix of the launch route; it does not
execute job/step evaluation, ScriptHandler, a macOS Node wrapper, or the live
Worker. It does not measure startup/native environment, managed cache history,
AppContext, ICU selection or either culture's effective mappings. Use actual
run results, not the presence of this gate, as evidence for that limited route.

#### Offline dependency member-reference inventory

The [research helper](../tests/runner-package/managed-references/README.md)
provides a bounded package-side check for the source/configuration
acquisition-target investigation. Run it only against an immutable flat `bin/`
extraction verified using the pinned archive identities and existing package
harness. It uses the SDK's PE metadata reader, not the target runtime, and must
not load or execute inspected assemblies. This can inspect other package
architectures without claiming to execute those architectures locally.

Its reported scope is selected names in MemberRef tables of the active
dependency target's managed runtime assets. Require complete enumeration and
hash agreement with the corresponding package manifest before using the
inventory. A successful inventory neither closes reference correctness nor
establishes deployment applicability.
No absence-of-mutation claim follows just from missing references. The helper
README owns its invocation, inventory exclusions and supported metadata
shape/limits; excluded routes remain separate source obligations.

CI runs synthetic metadata fixtures and CLI success/failure-projection tests in all
four runner-differential rows with the pinned SDK. These tests need no vendor
data or parent-process access. Actual archive scans and associated source
interpretations belong in the compatibility evidence, separately from the
fixture results. Retain the report, input archive/deps/file identities and
scanner source identities; never publish inspected binary payloads.

### V2 Unicode data-start research

The package probe additionally evaluates a candidate, not a production input
policy. Generate `tests/runner-package/unicode-candidate.json` from the three
official Unicode 14.0.0 files identified by URL and SHA-256 in
`unicode-pins.json`. The generator selects General_Category L/N/P/S with
Grapheme_Cluster_Break Other/L/V/T/LV/LVT/Regional_Indicator, excluding
Default_Ignorable_Code_Point. Unassigned and private-use characters are not
selected. This isolated table is not a superset of the existing ASCII policy
(for example, it excludes space); any future acceptance policy must explicitly
compose it with the current rules, not replace them accidentally.
Regeneration must match the committed bytes before building the
probe. Do not select candidates from the executing runtime's Unicode tables.
The derived data's license is `tests/runner-package/UNICODE-LICENSE.txt`.
It is test-only and not linked into official CLI binaries. Any future crates.io
publication must review source-package contents and third-party license metadata;
registry publication remains deferred by the release policy.

For each existing explicit culture, test all 142,081 candidate starts with six
fixed tails, using mask and warning with an ASCII property header (1,704,972
cases). Separately test ten representative starts (including Thai/Lao
prevowels, conjoining jamo, regional indicator and ASCII punctuation) with every non-NUL Unicode
scalar followed by `x`, using the warning header (11,120,630 cases). Require
the exact separator, command, decoded data and properties, and record the
table digest, elapsed time and completed counts. Bound failure examples per
suite and record only fixed reason labels and numeric scalars/case indices,
never command-shaped strings. A counterexample fails the candidate check
after both cultures' current-policy and research checks complete. Save explicitly
incomplete snapshots before research, so a timeout retains earlier counts
without passing; snapshots lack final package-identity verification and are not
passing evidence. The probe execution limit is 15 minutes; the enclosing
source/package CI job limit is 30 minutes. This is not a guarantee of artifact
upload after a job-level timeout: inspect total job timing as well as probe timing.
Retain failures rather than shrinking
the table to the current platform's passing subset.

Additionally run 500 suffix cases per culture: the same ten starts with eight
repeated motifs at three UTF-16 length budgets (32, 256, 4090), for mask and
warning, plus two near-1-MiB mask inputs per start. Repeat whole motifs to avoid
splitting surrogate pairs and append a terminal `x`. Motifs cover combining
mark ordering, variation/ZWJ sequences, tags/skin tones, Thai/Lao prevowels,
Hangul jamo, regional indicators, command-looking syntax and escaped CR/LF/%.
The annotation cases remain below 4096 semantic UTF-16 units; the larger cases
are mask-only. Require the same exact parser checks and a separate completed
`suffixChecks` count. Retain at most eight numeric failure examples for this
suite as well. These are finite stress cases, not an arbitrary-suffix proof.

After both cultures' parser research completes successfully, also feed generated
research wires through the same package-backed Worker fixture used for the
current-policy corpus. For each culture, combine the ten representative starts
with six tails (plain text, reordered combining marks, variation/ZWJ/skin tone,
Thai/Lao spacing marks, command-looking syntax, and multiline escape-looking
data). Use fresh execution state for each case. Require 120 mask cases
(echo off/on), 180 annotation cases (all three severities), 40 stop/resume cases
(all four commands), and ten masked-annotation cases. Check full and split-line
mask registration (explicit expected lines, including standalone start scalars),
exact subsequent redaction, mask echo off/on and annotation echo-on suppression,
absence of extra issues/log records, exact annotation message/severity/ASCII properties and
provenance, then completed annotation content/location/severity. Both persisted
and console log sinks must agree. Stopped commands remain ordinary log data
without effects even after a wrong resume token; matching-token resume must
restore their intended effects. Check the actual culture at entry and after
each start group and negative control, and record it. Two negative controls
(U+0301 and U+0E33 starts) must demonstrate the known failed-mask/legacy-warning
fallback, including no mask registration and one completed warning.
These are defect-reproduction controls, not desired consumer behavior. A fixed
or different backend can fail a control while accepting candidate inputs safely;
the fixed error rule and `unicode-worker-negative-control` case label distinguish
that drift from a candidate failure. The U+0E33 control is based on the recorded
local observation; new platform results remain evidence to collect. Neither
control directly observes which break iterator is active. Also require the
unrelated fragment `literal` to remain unmasked in each positive mask case.

Record these counts separately in `unicodeWorkerEffects`, marked research-only;
missing or partial counts fail evidence verification; source digests identify
the actual case definitions, not a separately pinned corpus digest. Keep the
research status incomplete until both cultures' worker checks finish; caught
Worker errors set it to failed, whereas timeout snapshots stay incomplete.
Capture only numeric scalar/tail indices, booleans and fixed suite/command labels on failure. These
statuses describe completion, not cause: caught Worker infrastructure errors
also yield failed, and parser exceptions can leave research incomplete. Inspect
`failedPhase`, `errorType`, `errorRule` and `workerCase` together. Offline tests
check rejection of these statuses, not fault injection into the catch path.
Current producer-policy checks still run first for both cultures. The Worker fixture
retains synthetic host services, log storage and server queues: it does not
start a live hosted worker or upload annotations to GitHub.

These generated research wires bypass the then-current, narrower ASCII
guard. They test consumer effects, not producer acceptance or producer-to-worker
round trips for these new values. The separate producer-generated worker corpus
still covers only the current producer policy. No arbitrary-length sequence
proof, Unicode metadata policy, new culture/backend support, or stdout release
permission follows from a pass. The separate `th-TH` issue remains deferred;
legacy framing is exercised only as a failure path, not an adoption option.
Extending producer acceptance requires a subsequent reviewed
contract and implementation change.

To regenerate after obtaining the pinned source files:

```sh
python3 scripts/generate-unicode-candidate.py --source-dir /path/to/ucd-files
python3 scripts/generate-unicode-candidate.py --source-dir /path/to/ucd-files --check
```

The research-only Rust test `tests/unicode_candidate_lookup.rs` checks a
first-scalar binary search against all scalar memberships in the candidate
table, unioned with the existing ASCII/CR/LF rule. It is not called by the CLI.
Its ignored release-mode microbenchmark compares the former ASCII predicate
and the proposed lookup on 16-byte, 4096-byte and 1-MiB inputs, with ASCII,
Japanese, emoji and rejected combining-mark starts:

```sh
CARGO_TARGET_DIR=target/unicode-research cargo test --release --test unicode_candidate_lookup benchmark_candidate_lookup -- --ignored --nocapture --test-threads=1
```

JSON decoding and input construction are outside timing; the proposed eventual
implementation would embed a generated static range table, not load JSON at
runtime. Inputs are already valid Rust strings. This measures warmed lookup
cost only, not UTF-8 validation, process startup, full encoding, I/O or Runner
processing. There is no timing pass/fail threshold. End-to-end and cross-platform
measurements remain required before claiming CLI performance is unchanged.

### Native collation observation

After both cultures' current-policy, Unicode parser and Worker checks finish,
inspect the native ICU objects used by the package's actual `CompareInfo`.
This is an additional research gate, not a producer dependency or a general
Unicode acceptance proof. Require the inspected .NET 8.0.30 build, 64-bit
x64/ARM64 layout, and positive ICU source preconditions before reading the
private `SortHandle` layout pinned by `pal_collation.c`. Observe option zero's
collator and head cached search iterator only, during synchronous inspection.
Overflow nodes and iterators used by earlier Worker calls are not observed;
this is not an attestation of every iterator in the process. Do
not close or mutate borrowed runtime objects. This instrumentation is not an
API supported by .NET and must be reviewed again when its runtime pin changes.

Resolve exports only from ICU already loaded by the process: macOS uses its
fixed system path with `RTLD_NOLOAD`; Linux requires one observed `libicuuc`
and `libicui18n` module and reopens them with `RTLD_NOLOAD`; Windows borrows
observed `icu.dll` or `icuuc.dll`/`icuin.dll` handles. Reject missing/ambiguous
modules, missing exports and disagreement with CoreLib's ICU version. This
does not attest native library file hashes or prove source-to-binary identity.
The macOS path is fixed, not discovered; Windows matching uses module basenames,
not a System32 path attestation. Version agreement does not distinguish two
same-version ICU copies or prove which image supplied the runtime's bindings.

Extract the new/old custom break-rule strings from the digest-verified native
source (read explicitly as UTF-8) into retained `break-rules.json`; compile each
using the selected loaded ICU. Hash the embedded resource bytes and require
that hash to match the build input's retained digest. Compare its binary rule
digest with the observed head iterator's digest.
Require an external iterator matching the new rules. Null, old, ambiguous or
unrecognized results fail this research gate rather than passing as unknown.
Binary rule hashes are platform observations, not one universal pinned hash.

Enumerate all reported contractions including prefix contexts from the actual
collator, recording item/completed counts and the number containing ASCII
colon; require a nonempty enumeration and zero colon contexts. For all 142,081
candidate scalars, require an NFD boundary before the scalar and a consumer GCB
class within the candidate's positive GCB set. Record completed counts and any
violation counts. Also count scalars equal to empty under actual `CompareInfo`
and retain at most 16 numeric examples. A positive count does not demonstrate
unsafe parsing or authorize removing those characters from the candidate table;
the CE-offset suite below additionally requires the observed set to match its
five tested prefixes, failing on set drift to avoid silently omitting new cases.
Investigate drift against that environment's data and review any changed test
set explicitly; do not silently widen it or infer producer acceptance.
These candidates also participate in the preceding exhaustive candidate-start
parser checks with finite suffixes; neither suite proves arbitrary suffixes safe.
The native GCB adapter uses `UCHAR_GRAPHEME_CLUSTER_BREAK = 0x1012` and
`Other/L/LV/LVT/T/V/Regional_Indicator = 0/4/6/7/8/9/12`, checked against
[ICU's public enum definitions](https://github.com/unicode-org/icu/blob/release-76-1/icu4c/source/common/unicode/uchar.h).
This is the same semantic set as `GCB` in `generate-unicode-candidate.py`;
keep the adapter aligned with that generator when changing the candidate policy.

Also require the cached search's collator pointer to equal the observed option
zero collator. Record all eight public collator attributes: French collation,
case-first, case-level, normalization, hiragana-quaternary and numeric collation
must be `UCOL_OFF` (16), strength `UCOL_TERTIARY` (2), and alternate handling
`UCOL_NON_IGNORABLE` (21). Require the public search attribute
`USEARCH_ELEMENT_COMPARISON` (2) to report `USEARCH_STANDARD_ELEMENT_COMPARISON`
(2). This public enum value is distinct from the internal zero-valued search
mode in the source argument. These are drift-detection expectations, not a
direct read of the internal mode: interpreting the getter relies on the
inspected upstream mapping, which returns the standard value for non-wildcard
modes. They are also not a claim that every other setting is unsafe. Definitions are in the public
[collator](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/unicode/ucol.h)
and [search](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/unicode/usearch.h)
headers.

Under those guarded settings, inspect raw forward CE values and UTF-16
low/high offsets through `ucol_openElements`, `ucol_next` and `ucol_getOffset`.
Create and close only owned element iterators, keeping their text pinned until
close; cap each sample at 128 iterations and reject errors or out-of-range
offsets. In the inspected upstream `UCollationPCE::processCE/nextProcessed`
implementations, tertiary plus non-ignorable preserves all three raw weight
components: skipping raw zero therefore selects the same retained elements
and offsets. This is a source-based interpretation, not direct instrumentation
of the cached search's internal processed-element buffer.

Per culture, `ceOffsets` checks 142,081 candidate starts followed by literal
`x`, and 5,560,315 pairs: each of U+0640/U+07FA/U+180A/U+1CD3/U+FE73, required
to be the complete observed empty-equivalent set, followed by every non-NUL
Unicode scalar and literal `x`. In each case, require `::`'s first two raw
elements to match the baseline weights and offsets `[0,1]`, `[1,2]`, and the next retained element to start at
or after 2 without equal low/high offsets. Separately require actual
`CompareInfo.IndexOf` on `::warning::` + data + `::later` to return 9. Retain
the distinction that ASCII candidate starts can take the managed fast path;
the raw iterator still observes ICU elements for those cases. Record
completed counts, failure counts, a positive count of cases skipping raw zero,
elapsed milliseconds and up to 16 numeric counterexamples. Nine
small samples retain full raw CE sequences, including Japanese/emoji and the
negative control U+0301: its search must return the later delimiter at 12, not
9. Require the five prefix samples to contain a raw-zero element spanning
`[2,3]` and every sample's first retained element after the delimiter to have
positive width. A separate canonical-expansion control observes `åa`: its
second nonzero CE must span `[1,1]` and trigger the same zero-width detector;
`IndexOf("a")` must return the literal `a` at index 1. Attribution of the first
position's rejection to the partial-expansion rule is a source-based
interpretation, not an instrumented branch trace. This supplements the U+0301
break boundary control. Offline validation requires the settings, complete finite
coverage, sample properties and both control results. These tests do not
instrument every command header, reuse a live Worker's search buffer or cover
arbitrary-length suffixes; the preceding parser/Worker suites remain separate evidence. The raw iterator
and full-header search are separate observations over different surrounding
text; their agreement does not prove contextual equivalence. The next suite
adds finite coverage of the reported context strings, not arbitrary contexts.

#### Reported context-string offsets

Retain every item from the same contractions/prefix-context enumeration as
numeric Unicode scalars in `contextOffsets.contextScalars`. Reject unexpected
ranges, malformed UTF-16, NUL, duplicate strings or strings exceeding 64 UTF-16
units; retain the existing 100,000-item and bounded CE-iteration limits. Record
the SHA-256 of the compact JSON integer arrays (ASCII, no whitespace). Offline
validation checks the digest, uniqueness, scalar validity, absence of colon and
agreement with the enumeration's item/completed counts. Corpus counts/digests
are observations, not one pinned cross-platform corpus or independent
attestation of the ICU data. No minimum of two scalars is inferred from the
API. Retain the current item index and bounded raw UTF-16 units on enumeration
failure. Enumeration runs before both offset suites, so its drift can prevent
either suite from running; only already-completed phases remain evidence.

For every string, prepend either nothing or each of the five observed
empty-equivalent scalars, and append one of empty, `x`, U+0301, or
U+200D U+0301. Classify each case by whether its first scalar belongs to the
embedded candidate table. Observe CEs over `warning::` + data + `::later`, the
text span used when the native search is called after managed `startIndex = 2`
([pinned overload's span slicing](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Globalization/CompareInfo.cs#L906-L937)).
An ASCII first scalar can instead take the managed fast path: its `IndexOf`
result is still actual runtime behavior, but only the separate raw-CE iterator
observes ICU for that case. Require the eligible cases' first nine elements to
match the fixed header baseline, the delimiter offsets to be `[7,8]`, `[8,9]`, and the next
retained element to start at or after 9 with positive width. Separately require
actual `CompareInfo.IndexOf` on the full `::warning::` record to return 9.
This uses the same surrounding text but is still an owned iterator, not a trace
of the cached search's internal CE buffer.

Record the number of corpus strings whose own first scalar is a candidate,
and separately the eligible/outside completed cases after adding prefixes;
the five nonempty prefixes make even an otherwise outside-start string eligible.
Also record eligible header/next-element/search failure counts, elapsed
milliseconds and up to 16 indexed failure examples including bounded raw CE
sequences. Attach the active case before processing so
caught failures identify the input; native faults still have only the prior
snapshot. With `N` reported strings and `C` candidate-start strings, require
`(5*N+C)*4` eligible and `(N-C)*4` outside checks. Recompute these numbers from
the retained corpus and candidate table in the offline validator, including
membership of the five prefixes. Only outside-start search mismatches are
informative, not failures or a fixed negative-control count; native API errors,
invalid offsets, missing elements and resource bounds still fail for all cases.
Outside cases' header-baseline agreement, next-element boundary and zero-width
conditions are not counted or asserted; only eligible cases use those checks.
The preceding combining-mark and expansion controls remain required.

This checks only the exact reported strings in the specified finite shapes.
It does not enumerate intervening marks for discontiguous contractions, all
context combinations, arbitrary tails, other headers, or every contextual ICU
mechanism. No CLI acceptance follows from these observations.

#### Single-scalar context insertions

The following `insertionOffsets` suite adds one selected scalar at every
internal scalar boundary of each reported context string. It does not select
languages or scripts. Scan every non-NUL Unicode scalar (1,112,063 checks)
with the same loaded ICU's `u_getIntPropertyValue` and select all nonzero
`UCHAR_LEAD_CANONICAL_COMBINING_CLASS` values (`0x1010`). This is the CCC of
the first scalar of the NFD decomposition, not necessarily the undecomposed
scalar's CCC; see the [public property definition](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/unicode/uchar.h#L620-L626).
Retain the ascending `[scalar, leadCCC]` pairs and their compact-JSON SHA-256.
Require nonempty selection, values in `1..255`, at most 4,096 selected scalars,
and all scan calls completed. Retain the active scalar on caught failure.
Counts are observations and may differ between ICU versions. Add three
explicit zero-leading-CCC controls to the insertion set: U+034F, U+200D and
literal `x`. Check known property controls for these and U+0327 (202), U+0306
(230), U+0300 (230), U+0438 (0) and `X` (0).

Require a discriminating raw-offset control: U+0438 U+0327 U+0306 and
U+0438 U+0306 U+0327 must have equal two-element nonzero weight sequences,
but respective offsets `[0,3],[3,3]` and `[0,2],[2,3]`. Inserting U+0300 or
`X` instead must yield three nonzero elements at `[0,1],[1,2],[2,3]`.
These exercise a real zero-width element after the first retained element;
zero width anywhere in the data is not the failure predicate.
The interpretation as discontiguous contraction and CCC blocking follows
the upstream [ICU iterator implementation](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.cpp)
(`nextCE32FromDiscontiguousContraction`): its caller requires a contraction's
trailing-CCC flag and an existing match, plus nonzero leading CCC for the
first skipped scalar; the function also requires a following nonstarter.
Among those conditions, matching across nonstarters requires the preceding
trailing CCC to be less than the next leading CCC. It then emits the
contraction's elements followed by skipped marks. The owned iterator's
public offsets follow [the forward CE adapter](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/coleitr.cpp#L83-L137).
The relevant caller/function conditions and forward CE adapter were also
compared with upstream releases 70.1, 72.1, 74.2 and 76.1; the checked branches
agree (boolean/null/cast spelling differs). This does not attest vendor binary
identity or guarantee the controls' exact element counts on each OS: the
32-bit adapter can split a 64-bit CE, and fresh matrix observations must pass
the controls. This is not a trace of native branch execution.

Require U+0438 U+0306 in the retained context corpus, tying the positive
control to an actual loop case with inserted U+0327 and no prefix. Also record
the full `warning::` + control + `::later` CE sequence and actual separator
index: the header must match the preceding baseline, control elements must
shift to `[9,12],[12,12]`, and `IndexOf` must return 9. Count eligible loop
cases containing a later zero-width nonzero element after the first retained
element, requiring a positive count. This counter alone does not identify the
cause (expansions and continuation halves of split 64-bit CEs can also produce
zero-width elements). The loop must observe the designated control case
exactly once, assert its eligibility, and compare its full elements and search
result against the recorded header control (`controlLoopChecks = 1`). The
validator also checks the control's membership in the candidate table. These later
elements are deliberately not failures. Controls fail closed on data drift.

For every context, internal scalar position and insertion, use the same six
prefixes as the preceding context suite. Append no further data tail before
the fixed `::later` sentinel. Observe raw CEs over `warning::` plus data plus
sentinel, and actual `CompareInfo.IndexOf` over the full `::warning::` record
with start index 2. Reuse the preceding suite's header baseline, candidate
classification, first-retained-element, separate-iterator/managed-fast-path
caveats and outside-start treatment. Every eligible case must preserve the
header, a positive-width next retained element starting at or after offset 9,
and separator index 9. Only outside-start separator shifts are informative;
native validity/resource errors fail all cases. Require at most 20 million
total cases before starting this loop; keep the 128-iteration per-text cap.
This is a work cap, not a time guarantee; retain the existing 900-second whole
probe timeout and record elapsed milliseconds per culture. Fresh matrix
timings determine hosted viability; the cap is not a runtime estimate.
Retain active context index, scalar position, inserted scalar and prefix index
on caught failure, plus up to 16 complete bounded CE failure examples.

Reference the preceding retained context corpus by its digest rather than
duplicating it. Let `P` be the sum of `(scalar length - 1)` over that corpus,
`C` the same sum for candidate-start contexts, and `M` the selected nonstarter
count plus three. The required control ensures `P > 0`; require
`(5*P+C)*M` eligible and `(P-C)*M` outside
checks. A one-scalar context contributes zero positions. Offline validation
recomputes these counts from the retained corpus and candidate table, checks
the sorted unique insertion corpus, properties' bounds/control agreement,
digests, case limits, offsets, statuses and zero eligible failure counters.
It does not independently reproduce the entire native property scan or detect
every self-consistently truncated set: completeness relies on the inspected
all-scalar native loop and its source identity in the complete evidence bundle,
not the self-reported counter alone or this validator in isolation.
Recorded pairs and digest are observational evidence, not external
attestation or a cross-version pinned Unicode property table.

This finite suite does not cover other zero-leading-CCC insertions beyond the
three explicit controls, multiple inserted scalars, insertions before
or after a reported string, arbitrary tails or nested context combinations.
No result expands CLI acceptance or proves all Unicode strings safe. Fresh
four-OS package results remain necessary.

Record results under each culture's `collationObservation` and require both
to pass `collationResearchStatus`. Save an explicitly incomplete snapshot
before native inspection of each culture. Caught errors fail the gate; a
native fault may terminate the process before catch/finally and leave only the
snapshot, which must never pass. Earlier completed suites remain visible but
do not substitute for this gate. Offline tests reject missing/mismatched
coverage, identities, rules and incomplete status; they do not simulate invalid
native pointers. CI must supply fresh results for every package-matrix OS.

These observations test prerequisites of the source argument, not all possible
suffixes, every ICU implementation, future collation data or live hosted
workers. The probe intentionally fails on drift/unsupported observation even
when producer-compatible behavior might still be safe. CLI acceptance,
metadata restrictions, the deferred `th-TH` issue and release eligibility are
unchanged.

### Offline compiled NFC input research

The [compiled NFC input evidence](compatibility/unicode-compiled-nfc-evidence.md)
has a separate hash-gated array locator. Run
`python -B tests/runner-package/test_compiled_nfc.py` for its synthetic format-4
and format-5, distinct/hex/multiline generated fixtures, malformed input, bounds,
cross-chunk capture, whole-file identity before and after the selected range,
size-change controls, bounded metadata/match counts and empty-stdout failure
checks. A Unix-only test verifies FIFO rejection without a writer. These tests
run in the package CI job and do not
verify acquired vendor binaries, the manual initializer observations, complete
normalization semantics or effective native use.

### Offline root mapping graph research

The [cross-generation evidence](compatibility/unicode-root-generation-evidence.md)
records the fixed-source comparison and hash-gated exploratory reproduction.
Run `python -B tests/runner-package/test_icu_source_comparison.py` for the
comparison helper's word boundaries, limited normalization regressions,
non-exported source contents, equal/unequal reports, raw newline sensitivity,
missing/invalid UTF-8 input, CLI failure status and size-cap boundary. Dependency
mode tests additionally cover explicit source slices, missing/duplicate/reversed
boundaries, disclosed replacements, and full-file raw hashes remaining distinct
when the selected portions compare equal. They also cover dependency CLI
wiring/partial-output failures and the retained manifest's shape/internal
equality consistency. Documentation-only edits skip the package job, so run
this test locally when editing that manifest; it does not authenticate source
hashes. It runs
in the multi-OS package job using synthetic fixtures, not acquired ICU sources;
green CI does not verify the retained upstream equality or substitution claims.
Source text equality is not vendor binding or proof of
the reader's complete input profile; keep those conclusions separate.

The [context matching coverage argument](compatibility/unicode-context-matching-evidence.md)
separates conservative value coverage from input-consumption and whole-iterator
claims. `test_mapping_inventory.py` includes a supplementary-unit key with an
intermediate value and high-bit value-versus-jump regressions. These are
synthetic decoder checks, not native execution or a universal proof.

The full-scalar structural graph experiment is separate from the leading-weight
classification below:

```sh
python -B scripts/inspect-icu-graph.py \
  --root-data PATH_TO_ROOT_PAYLOAD --sha256 EXPECTED_PAYLOAD_SHA256
python -B tests/runner-package/test_structural_graph.py
```

It requires no candidate file: all 1,112,063 non-NUL Unicode scalar roots must
complete. Exit 0 means the supplied root's bounded graph walk completed, not
consumer safety; exit 2 emits an incomplete report with the first failing root
and reason. Input/hash/header/usage failures exit 1 without a JSON report.
Cycles, graph-budget exhaustion (`budget`) and shared context-decoder limits
(`decoder_budget`) are separately labeled; unsupported dispatch and other
decoder/data failures remain unverified rather than positive evidence.
An incomplete report uses `structuralGraphAcyclic: null`, even when completed
subgraphs have ranks. Root-only scope and false consumer/acceptance flags must
be preserved.

Offset tags additionally require the sufficient nonnegative arithmetic profile
described in the [offset follow-up](compatibility/unicode-root-generation-evidence.md#offset-arithmetic-follow-up).
Tests cover both compression radices, carry transitions, the signed-shift
boundary, lead overflow, negative intermediate/lower-word rejection, scalar
and width guards, zero step, cached-node counts, empty-set aggregation, and
failure preventing both node caching and complete-walk evidence. Complete-walk
tests assert both zero-node and nonzero-node aggregate results, including
the false native-profile flag; see the linked follow-up for field semantics.
These tests are
synthetic checks of the sufficient predicate, not native equivalence tests.

Limits are 2,000,000 started graph nodes, 4,000,000 examined edges and 128 active
nodes, in addition to the shared decoder's input/context limits. A cycle must
not be confused with a cached shared child; cache only complete subgraphs.
Synthetic tests cover direct/indirect mappings, malformed references, scalar
preconditions, default versus trie argument handling, internal sentinels,
cycles, non-zero node/depth limits reached mid-traversal, edge and decoder
limits, supplementary initial correspondence and its rejection reasons, fast
and recursive Hangul, full root counts and CLI success/failure outputs. The existing
multi-OS package job runs these tests without requiring a private payload.
Native root acquisitions and full graph observations remain separate evidence;
no test or report establishes loaded consumer identity or CLI eligibility.

On a complete walk, `delimiterMappingEvidence` reports the initial colon
CE32, whether it is simple, its raw halves only when simple, and colon-unit
occurrence counts in all visited stored context keys. On an incomplete walk
the whole field is null, so a partial context cache cannot claim absence.
Counts are per entry of each distinct context trie; shared trie references do
not multiply them, and defaults/CE32 values are not text keys. A complete walk
with no reachable context entries reports count zero and absence true; inspect
the count to distinguish this empty-set result from examined nonempty tries.
A false colon
predicate does not change exit 0 for an otherwise complete graph: these are
observations, not a new acceptance gate. `delimiterEntryStateProven` stays
false even when the static predicates hold. Tests cover zero and non-simple
colon mappings, the simple/special low-byte boundary, colon anywhere in a key,
values versus keys, shared context discovery and incomplete reports. Serialized
fixtures with nonempty contexts cover both colon and non-colon keys through
the complete `inspect()` walk and CLI, checking entry counts and exit 0 even
when colon occurs in a key or its mapping is zero. The
[conditional entry-state discussion](compatibility/github-actions-workflow-command-parser.md#delimiter-mapping-and-conditional-entry-state-step)
owns the source argument and its separate premises.

`scripts/inspect-icu-mappings.py` is a separate research reader for an acquired
little-endian ICU 78.1 root UCol-v5 payload (without its data header), not a CLI
allow-list generator or a replacement for the native package gate. It requires
an explicit payload hash and a candidate JSON file:

```sh
python -B scripts/inspect-icu-mappings.py \
  --root-data PATH_TO_ROOT_PAYLOAD --sha256 EXPECTED_PAYLOAD_SHA256 \
  --candidates tests/runner-package/unicode-candidate.json
python -B tests/runner-package/test_mapping_inventory.py
```

The reader walks per-code-point and lead-surrogate summary entries, direct and
expanded elements, non-numeric digit indirections, Hangul/Jamo mappings, and all
default/prefix/contraction values. Prefix alternatives are included even when a
particular header could not select them: this is an overapproximation, not a
reachability proof. It validates complete expansion spans and trailing Jamo
mappings, but classifies the first raw 32-bit half only. Algorithmic offset and
implicit mappings use their common secondary/tertiary bits for this nonzero
classification; their exact primary weights are not reconstructed.
Contraction alternatives are conservatively evaluated with an unavailable
scalar, since the discontiguous path can supply `U_SENTINEL`; a scalar-dependent
alternative is unverified even if a contiguous/default path could evaluate it.

This initial reader models root data only. Missing base data, unsupported
mapping kinds, cycles, out-of-range references or exhausted bounds are
unverified, never accepted. Bounds include 16 MiB input, 64-unit context keys,
100,000 visits per context trie, 4,096 context roots, 100,000 total context
entries, 500,000 uncached mapping visits and depth limits. Numeric collation is
outside this model: only the payload's default option bit is checked, not the
effective consumer attribute. The report records this assumption and the
caller-declared input profile; without the stripped data header it cannot
authenticate the root/format/release identity. The visit cap is intentional and
can be reached on larger candidate sets; this reader does not promise a
full-Unicode run within that cap. Input errors exit 1 without a report; unresolved candidate
mappings produce a diagnostic report and exit 2. Exit 0 means only that this
data-graph calculation completed, including any zero-first-half results.
Every report explicitly denies being an acceptance table, an offset proof or
consumer-identity evidence.
Trie padding, payload slack and reserved section contents are not interpreted;
this is not a complete validator of the serialized data format. Command-line
usage errors also exit 1 without a report (explicit `--help` is informational).

The synthetic unit suite runs alongside the offline package-harness tests in
CI. It exercises compact context values and deltas, intermediate values,
linear and split branches, duplicate/truncated contexts, cycles, expansion
bounds, first-half-versus-whole-element differences, Hangul trailing validation,
lead-unit summaries, resource limits and CLI error exits. Distinct synthetic index blocks also exercise
BMP and supplementary lookups, the `highStart` boundary and the lead-code-unit
path (not just mocked summary values). It requires neither
native ICU nor an OS data dump. It does not attest to traversal completeness on
vendor data; local/native comparisons and their limitations belong in the
[compatibility observation](compatibility/github-actions-workflow-command-parser.md#mapping-data-acquisition-feasibility-local-research).
Actual consumer data identity, normalization-related inputs, arbitrary-suffix
iterator offsets, and other supported OS releases remain separate obligations.

### Current stdout adoption verification

Apply these existing checks to the profile owned by
[design](design.md#stdout-adoption-contract), using the release policy's
candidate and update process. Keep observations separate rather than treating
one suite as proof of another layer:

| Layer | Required evidence and scope |
| --- | --- |
| Producer | Existing stable and feature-on contract/property tests, exact bytes, rejection before output, resource limits, value-free diagnostics, exhaustive lookup agreement, reproducible table check |
| Consumer integration | Pinned source oracle and official-package parser/Worker effects for all profile rows under explicit en-US and Invariant: original mask registration/redaction, selected annotation, message and typed properties, final TITLE/FILE cases |
| Policy compatibility | Existing four-row Unicode-policy probe with data-start, final-field header, and metadata checks; preserve known excluded-configuration mismatches |
| Live effects | Package-matched hosted experiment for each profile row, API annotation verification and external masked-log verification; record live Runner/image identities and leave hidden Worker fields unobserved |
| Regression cost | Reuse the recorded performance baseline for unchanged code; rerun the existing paired benchmark if policy lookup or record construction changes |

Retain stopped-command and feature-state negative controls. A successful
producer, parser, or API annotation query alone cannot establish mask secrecy;
masking requires the log verification described below. The ordinary moving-label
smoke matrix provides additional observations, not automatic support for a new
OS generation. These finite checks support the adopted dependency contract;
they are not arbitrary-suffix or native-implementation proofs.

The following live-test and continuing-check sections describe existing
mechanisms. Startup/module/data-acquisition subsections retain historical
feasibility observations; they do not impose deployment attestation or new
native-proof work on adoption. Runtime identities that a live test cannot
observe must not be fabricated from its explicit-culture package probe.

### Live hosted stdout boundary experiment

The ordinary three-OS hosted test matrix additionally runs
[`hosted_boundaries.py`](../tests/workflow-smoke/hosted_boundaries.py) against
the research binary, with native child stdout inherited directly by the live
Runner. Binary stdin receives UTF-8 bytes; this is not additional shell argv or
pipeline-transcoding coverage. Separate offline tests capture and compare
exact producer bytes before testing consumer effects.

The bounded corpus uses eight starts (two ASCII starts plus Greek, Arabic,
Devanagari, CJK, emoji and supplementary letters) followed immediately by a combining mark and hostile Unicode/command-
looking tails. Annotation cases additionally start with CR and LF; all three
severities exercise Unicode, literal escape-looking text, a decoded newline,
legacy-looking warning syntax and V2-looking error syntax as data. Compare
exact Unicode title, workspace-relative Unicode file, severity, message, line and column fields
from the completed job's paginated annotations API, including multiplicity.
The dedicated step emits ten annotations per severity, at the pinned Runner's
per-step retention cap; existing smoke annotations run in other steps. This is
not an overflow test. The job deliberately emits 33 corpus/smoke annotations;
retention remains verified by API results, not an assumed server capacity.

Eight distinct synthetic mask canaries include command-looking tails. Register
all masks while command processing is active. Suspend command processing only
while printing subsequent canary samples: otherwise legacy syntax embedded in
ordinary log text can itself execute before masking. Resume before annotations,
whose successful effects also test resumption. Compare the complete delimited
log block, not only substring presence: require exactly one redacted sentinel
per case, exact annotation log text/order, and no extra log-visible effects in
that block or tagged annotations. Silent command effects and unrelated steps'
annotations are outside this observation.
Log comparison removes timestamps; the API's complete-message and multiplicity
checks distinguish a command-looking continuation from a separately executed
annotation whose rendered log text could otherwise look the same.
Scan the entire completed log for each synthetic marker, including an encoded
failed registration. This does not test raw legacy-looking log data while
command processing is active or promise arbitrary transformed-secret masking.
Debug-logging runs are not valid evidence for the exact-log experiment. Require
the final ordinary test-step sentinel after the experiment, and retry both log
and annotation retrieval. This rejects a response truncated before that sentinel;
it does not attest transport completeness after it or cover post-action output.

The existing `hosted-annotations` job performs this read-only verification
within PR and main CI, using only Actions/Checks/Contents read permissions.
It checks out the same tested revision; unlike the default-branch
`workflow_run` mask verifier, it is not a trusted external release gate. Retain
that independent verifier and its shell cases. Missing, duplicated, changed
or late/missing API results must not pass. Offline negative controls mutate
logs, annotation fields/counts, identity and mask leaks to test rejection.

Retain per-OS reports for 30 days in `hosted-boundary-evidence`: source run,
attempt, tested merge SHA and source head SHA, verifier attempt, job ID,
Runner version from its setup log, child-visible
OS/architecture/image identity, case counts and log/API/harness digests.
Missing identity fails the experiment.
The attempt is taken from each source job's API metadata, not the verifier's
attempt, so retrying only failed jobs does not relabel earlier successful jobs.
Also record the oracle's pinned version and whether the observed version matches
it. A different version's passing result is evidence for that observed Runner,
not for the pinned implementation. These observations do not measure the live
worker's culture, runtime or globalization backend; culture/backend remain
explicitly unknown. Failure reports and partial artifacts are not passing
evidence; require all three reports and the successful verifier job. Only
synthetic canaries are used; reports do not contain full job logs or raw mask
values. This finite matrix neither expands accepted input nor resolves the
deferred `th-TH` issue nor changes stdout release eligibility.

#### Package-matched feasibility observations

The [feasibility audit](compatibility/unicode-feasibility.md) also emits the existing bounded hosted
corpus in each of the four `runner-differential` jobs, after the package probe.
The hosted verifier waits for those jobs and checks their completed logs and
paginated annotations with the same offline-tested verifier. Its reports are
retained under `package-matched/` in `hosted-boundary-evidence`, with each source
job ID and attempt. This places package and live observations in the same job;
it does not assert binary equality, Worker culture/backend, or equality of
the package's sanitized environment and the Worker's startup environment.
The preceding three-report, 33-annotation and ordinary-test-sentinel rules
describe the ordinary `test` jobs. Each package-matched job instead emits 30
corpus annotations and its own final sentinel, with no dogfood annotations.
All four additional reports and the successful hosted verifier are required;
passing individual reports in a failed/partial run are not a passing matrix.
Once the verifier script starts, one failed row does not suppress collection
of other rows; it writes per-row passed/failed reports and any failure fails
the verifier at the end. A missing report (including prerequisite failure or
timeout before collection/upload) is incomplete evidence, never a pass.

Both variants use Bash and the same Python producer source, with separately
built native binaries from the same source and feature set.
The package-matched variant follows SDK setup, source-oracle and package-probe
steps, so its live Worker's masks, command state and any registered problem
matchers are not fresh. No reset of
that state is claimed. Whole-log leak/identity checks and exact block/API checks
still apply, including interference from preceding steps. A failed emit fails
the package job too. The 30-minute package-job budget includes the extra build
and emit; inspect actual timing before treating it as adequate headroom.
The hosted verifier's 30-minute budget now covers both sets of observations.

The existing three-OS summary remains a summary of the ordinary test jobs,
not an aggregate of these additional reports. A separate summary line reports
the four-row verifier step's outcome. Missing observations fail the hosted
verification job. No new Unicode inputs are accepted.

#### Hosted Worker startup-input feasibility observation

The historical heading/CI label covers two separate observations: process-start
culture and job-supplied culture input. The same four package jobs run this read-only observer
before the live emit. It walks only the observer's process ancestors to locate
`Runner.Worker`, then examines bounded `Worker_*-utc.log` files under that
executable's diagnostic directory in memory. It selects exactly one job message
matching resolved `github.job`, matrix OS/RID, repository, run, attempt and
tested SHA. The job-key source follows the
[inspected consumer path](compatibility/github-actions-workflow-command-parser.md#culture-diagnostic-observation-route),
not assumed equivalence with `JobName`. Duplicate JSON
keys, multiple matches, unsupported structure and bounded-read failures remain
unavailable. It does not enable debug logging, inspect process arguments or
other processes' environments, inject code, modify the Worker, or copy diagnostics elsewhere.

Only the selected culture inputs Invariant/`en-US` may be recorded; secret,
redacted, missing or other culture inputs remain null with a fixed status.
`absent` distinguishes a missing variable from an unavailable/redacted value;
it does not infer the host default culture. Separately, the observer extracts
exactly one `INFO Worker` `Culture:` line preceding the selected job message
in the same file. `startupCulture` may contain only the exact empty string or
`en-US`; no trimming is performed. Other/redacted values, missing lines and
duplicates remain null with a separate `startupCultureStatus`. UI culture,
other trace sources and lines after the job marker are not substitutes.
The existing top-level status still describes job-input availability, not
this independent startup observation. This uses the same diagnostic bounds
and trust limitations, not process memory or parent-environment inspection.
The strict source-emitted line format is intentional: near-miss trace levels,
indentation or spacing are ignored, not counted as matching duplicates.
No authentication against a same-user log writer is claimed. Interpret an empty
name subject to the [backend/default-locale caveat](compatibility/github-actions-workflow-command-parser.md#culture-diagnostic-observation-route);
it does not establish ICU mode. `missing-or-ambiguous` deliberately groups absent,
malformed and duplicate startup lines; it diagnoses no narrower cause.
Fixed failure codes distinguish
ancestry, diagnostic-read, message-parse and projection failures without
including exception text. The observer's offline test is a prerequisite for
the live emit; collection with an unavailable result is not a test failure.
The observer retains job identity, a timeline job GUID, ancestor Worker PID and SHA-256
of explicitly named on-disk Worker/parser/runtime files, not their bytes or
diagnostic contents. The current list also includes `Runner.Sdk.dll` and
`Sdk.dll`, whose source participates in the output-processing chain; historical
seven-file observations do not cover them. The separate `hosted-worker-input-OS-RID` artifact contains
only the JSON projection, for 30 days. Unexpected errors are reported through
fixed codes, not captured messages or tracebacks. Offline synthetic tests check
matching, ambiguity, limits, sensitive-field suppression and no-overwrite.

Successful collection does not mean a successful observation: inspect the JSON
status and the separate `cultureInputStatus`, `startupCultureStatus` and
`onDiskIdentityStatus`. Schema v2 adds the independent process-start fields
and renames v1 `observed-startup-input` to `observed-job-culture-input`.
Historical v1 reports lack the process-start observation, rather than
implicitly measuring a default. No top-level status reflects `startupCulture`.
`observed-job-message-without-culture` means no job culture input was observed;
inspect the separate fields for any process-start observation. A failure
to hash files does not discard a separately observed input. Even
`observed-job-culture-input` is evidence only of a diagnostic job input, not
processing-thread culture, loaded native identities, effective mappings or
transfer to the other culture. A
null culture is not Invariant (which is the explicitly recorded empty string).

Schema v3 additionally records a separate `childConfigurationPresence`
observation in the Python observer's own environment. Its fixed key list is
the four `DOTNET_SYSTEM_GLOBALIZATION_*` selectors for invariant, NLS,
app-local ICU and predefined-only mode, `CLR_ICU_VERSION_OVERRIDE`, and
`ICU_DATA`. Each entry is only `defined` or `absent`; even empty values count
as defined. Values must not be compared, retained in reports or emitted; the
helper makes membership queries only. Python's environment representation may
already contain values and its membership implementation may fetch them
internally; this is not a no-memory-access guarantee. Do not publish arbitrary environment keys,
parent environments, loader paths or process arguments. A failed projection
is independently `unavailable`, never a successful all-absent result.
The workflow requests this observer through isolated Python without a shell
profile or site initialization; it does not sanitize these keys. Key matching
follows `os.environ`: uppercasing on Windows, exact on Unix; this is not a claim
of equivalence to the .NET comparer for arbitrary Unicode key names. Offline
tests exercise every key, empty/secret-like values, membership-only helper queries and failure
separation. Historical schemas have no such observation.

This is child-process evidence at observation time, **not** Worker startup
configuration, AppContext state, ICU binding or culture. Interpretation needs
the [fixed-source inheritance route and remaining conditions](compatibility/worker-configuration-route.md).
In particular, neither an all-absent child projection nor Python isolation
alone excludes job/step overrides or earlier changes in the parent. The
top-level diagnostic status does not describe this additional observation.
The log record does not contain a PID: `ancestorWorkerPid` locates an
installation, not a cryptographic or direct process-to-log binding. Correlation
depends on a trusted ephemeral hosted job and a unique matching matrix context.
Multiple message markers in a file are rejected, rather than selecting a later
marker that preceding workload output could forge. These checks are observation
sanity checks, not authentication of a log writable by the job user.
Review [the audit](compatibility/unicode-feasibility.md) for per-row conclusions.

#### Windows ICU acquisition locator

The research-only `windows_icu_metadata.py` collector obtains acquisition
metadata, not live consumer-linkage evidence. Its purpose, report semantics
and interpretation limits are recorded in the
[reference input inventory](compatibility/unicode-reference-inputs.md#bounded-windows-acquisition-locator).
Synthetic tests must cover exact reference-hash gating, preserved matches when
PE parsing fails, PE field/layout bounds and exact-fit cases, leading-zero key
formatting, input-size limits, ambiguous reference records, fixed failure
reasons, identity allowlisting, native directory return validation and exclusive
report creation with empty stdout. Neither fixture success nor a workflow's
green status establishes a match or the native API's actual behavior.

Run `python -B tests/runner-package/test_windows_icu_metadata.py` locally and in
the runner-package CI step. The dedicated Windows workflow also runs the tests
before collecting only the JSON report. It must react to changes in its pinned
reference projection as well as collector/test/workflow changes. Before retaining
a result, verify the run/repository and reviewed source-head/tested-merge
association, candidate status, expected digest and reference-projection hash.
The latter hashes raw checkout bytes: distinguish the source LF and Windows
CRLF forms using the retained inventory digests and verify the conversion
explicitly. Do not interpret a raw line-ending difference as a different
reference DLL or silently discard it.
A PR result may be retained after reviewing its source commit and tested merge;
manual dispatch is needed to collect from reviewed `main` because the dedicated
workflow has no push trigger. A fork artifact's name alone is never authority.
Preserve useful selected metadata before the artifact expires.
Never upload the vendor DLL or infer reference correctness from a locator.

Also run `python -B tests/runner-package/test_pe_prefix_digest.py` in both
locations. Comparison tests must independently construct the expected hashed
fixture bytes, detect mutations in included headers/gaps/sections, tolerate
only the explicitly excluded field/certificate mutations, and reject malformed
directory counts, header/section overlaps, nonterminal or misaligned certificate
tables and invalid length-prefixed entries. Include multiple rounded entries.
Collector tests must prove the whole-file mismatch skips the comparison and
that comparison failure preserves matched locator metadata without leaking
exception text. Helper and helper-test changes must trigger the dedicated job.
Native observations and candidate comparison results belong in the linked
reference inventory; test success alone establishes neither file equivalence
nor signature or consumer behavior.

For the fixed-path data-candidate extension, run
`python -B tests/runner-package/test_icu_data_candidate.py` locally and in both
CI locations. Verify native directory return bounds and absolute-path handling,
chunked hash equality, exact-cap acceptance and cap+1 rejection, fixed API/read
failure reasons and omission of partial hashes after midstream failure.
Collector tests must prove no data-path access occurs on a mismatching,
unavailable DLL or a DLL whose PE locator is unavailable, and that an observed candidate never changes
the effective-data flag. Synthetic tests must mock data collection rather than
reading the host's real vendor file. Helper/test changes must trigger the
dedicated workflow, and each PowerShell native command must have its own exit
check. Retain bounded metadata only; compare official-update identities
separately from proving the reference's effective data binding.
Prefix-comparison availability is not part of the data-candidate gate.

For the selected package inventory, additionally run
`python -B tests/runner-package/test_icu_package_inventory.py` in both CI
locations. Cover header/TOC/name/offset bounds, sorted unique names, unselected
entry bounds, selected member headers, storage-padding hashes, exact input cap,
the final-entry unknown-length case, and zero/partial/full prefix counts with
the slash boundary. Candidate integration tests must prove
that size or digest mismatch prevents parsing, hashing and parsing share one
read buffer, and malformed matched data yields a closed reason without a
partial inventory. Only fixed selected metadata may leave the job. These
synthetic tests establish collector behavior, not vendor resource semantics;
native observations belong in the reference inventory and do not close its
effective-data obligations.

The offline Linux ELF wrapper additionally runs
`python -B tests/runner-package/test_icu_elf_package.py` in the runner-package
CI matrix. Use synthetic ELF/package bytes, never a host vendor file. Cover
nonidentity VA/file-offset mapping, hash-before-parse rejection, ELF target and
program-table bounds, truncated and zero-fill-only spans, ambiguous overlapping
load segments, resource limits, and rejection of an invalid unselected TOC
entry through the shared inventory. CLI failure tests must assert nonzero exit
and empty stdout, including under optimized Python where assertions disappear.
Supplied symbol coordinates are not independently discovered symbols; these
tests do not prove symbol resolution or native data selection.

The selected resource follow-up adds
`python -B tests/runner-package/test_icu_resource_probe.py` in both CI locations.
Test table/table32 traversal, empty versus missing values, fixed output keys,
header/index/region/key/string bounds and member limits. The
[documented unsupported forms](compatibility/unicode-reference-inputs.md#windows-package-result-and-selected-resource-follow-up)
must yield their closed unavailable category rather than absence.
Package integration tests must cover `en_US` selection, storage identity
preservation on resource failure, and resource-cap refusal. Retain only the
fixed field projection; do not export resource strings, trees or binaries.
For bundle-root-table redirect-key presence, cover missing keys, zero-valued handles and
opaque nonzero handles in both table widths. Presence must neither resolve
the redirect nor leak its value, and must be reported even without
`collations`. Exercise each field-to-key mapping independently and the stored
`RES_BOGUS` case; stored-key presence is not native loader-visible presence.
Native observations of the additional fields must not be
backfilled into artifacts produced by earlier collector versions.
This does not exercise native fallback or prove the effective collation choice.

#### Hosted Worker module-metadata feasibility observation

`tests/runner-package/hosted_modules.py` separately follows its own ancestor
chain to locate Worker and projects module metadata: `/proc/PID/maps`
on Linux, `lsof -nP -a -p PID -d txt -Fn` text-file records on macOS, or
`Process.Modules` through PowerShell on Windows. It requests no dump, stack
data, environment listing or injection. Underlying APIs may read target
loader structures: Windows module enumeration uses process VM-read rights.
That acquisition mechanism is distinct from the strictly limited output.
Windows filters module names before returning paths to Python and rejects
UNC/device-prefix paths; a drive-letter path is not proof of local storage.
Linux accepts coreclr, the globalization shim and numbered ICU
common/international/data filenames; macOS selects only the known Worker-bin
CoreCLR/shim and system ICU paths. Windows accepts CoreCLR, optional shim and
combined/split ICU names. Nonselected metadata is
discarded, not published. Unknown/custom names cannot establish absence of ICU.

The report contains selected basenames, fixed statuses, ancestor PID and
SHA-256 of readable regular on-disk files, never raw maps, addresses, full paths
or library bytes. Mapped-deleted files are not reopened; missing disk files
(including shared-cache-only images) retain null hashes. Each file is capped
at 128 MiB and checked for size/mtime changes during hashing. Linux additionally
compares the maps device/inode with the opened file's identity. This does not
hash mapped memory or authenticate file contents against later writes.
A mismatch is unavailable identity evidence, not proof of a file replacement;
the filesystem's identity reporting may also prevent a match. macOS exact-path
selection can miss symlink-resolved paths, which likewise remain unknown.
File-specific failures preserve other mappings with a fixed failure status.
Metadata larger
than 4 MiB is rejected; native command capture precedes this size check and
has a 30-second timeout. Both streams are captured in memory and discarded;
errors are reduced to fixed codes. Ancestry is rechecked after collection.
These checks do not authenticate against a job user modifying files or processes.

`observed-module-metadata` means at least one selected mapping was observed,
not that every relevant module was found. Read each `modules` entry and its
independent `onDiskStatus`; `selectedClasses` distinguishes observed from
not-observed classes without claiming absence. Empty/ambiguous selected results, denied access,
timeouts and unsupported formats are unavailable, not passing evidence.
The report keeps `activeBackend` and `effectiveData` null and
`loadedBytesAttested` false. File equality would identify on-disk bytes at the
observed paths, not prove mapped bytes are unchanged, native symbol binding,
effective root/tailoring, settings or processing-thread culture.

The four package jobs run the observer after startup-input collection and
before the live emit, with no new job permissions and a two-minute step limit.
A separate
`hosted-worker-modules-OS-RID` artifact retains only its JSON for 30 days.
Exit 0 means collection completed, including explicitly unavailable results;
offline tests and artifact/write failures still fail CI.
The outer step timeout also fails the package job and may prevent later live
emission; it is an operational safety bound, not an unavailable JSON result.
No evidence is claimed when collection/upload cannot complete.
Synthetic tests cover
selection, duplicate/deleted paths, bounds, errors, transport PID, UNC/device-path
rejection, no raw-path disclosure, ancestry changes and no overwrite. The
[feasibility audit](compatibility/unicode-feasibility.md) owns actual availability
and conclusions; a configured collector is not evidence that it ran successfully.

### Continuing compatibility checks

CI runs weekly on Wednesday at 03:37 UTC (12:37 JST) and can be started manually
with `workflow_dispatch`. These events unconditionally select full CI, including
the source/package Runner matrices and live hosted tests, even without code
changes. PR and push events retain their documentation-only skip behavior.
The external completed-log mask verifier also accepts successful scheduled and
manual CI runs, but only on `main` in this repository; it keeps read-only Actions
permission and never checks out triggering code. Manual runs on other refs do
not receive that external verification.

The hosted verification job always attempts a step summary when full CI was
selected. It shows each observed Runner version against the existing pin and
records the current image/version. A mismatch is conspicuous review-required
drift, not automatic failure of successful behavioral checks or permission to
claim support. Missing, failed, inconsistent or stale reports produce an
incomplete summary and fail the summary step. Require the CI result and the
separate completed-log verifier, not just the summary table. Reports retain
their existing 30-day lifetime; there is no historical image-diff service here.

Maintainers should inspect source/runtime changes and fresh results after a
version mismatch, and update pins only in a separately reviewed PR. This job
does not fetch/execute a newly released Runner, change pins, create issues,
contact upstream or expand the support/release boundary. It detects changes to
the observed hosted Runner and behavior, not every new self-hosted release.

The [GitHub event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
notes that scheduled runs use the default branch, may be delayed or dropped,
and public-repository schedules can be disabled after 60 days without activity.
Manual dispatch requires the workflow to exist on the default branch. Confirm
fresh successful runs periodically; an enabled cron is not evidence of execution.
The schedule/manual trigger itself must be exercised after merge; PR CI and
offline event-routing tests are not proof that those triggers fired.

## Shell and workflow matrix

The release matrix should capture executable stdout bytes before testing runner
semantics, so shell transcoding and parser behavior are diagnosed separately.
Windows contract tests must also prove that stdin is read as binary bytes,
without CRLF translation or treating byte `0x1a` as end-of-file. Use
discriminating inputs such as `a CR CRLF`, which default mode rejects only when
the bytes are preserved, and `a 0x1a b`, which must retain the control byte.

| Host | Invocation | Required before guarantee |
| --- | --- | --- |
| Linux GitHub-hosted runner | `sh` direct `>>` | Exact native stdout bytes and semantic round trip |
| Linux GitHub-hosted runner | Explicit Dash direct `>>` | Exact native stdout bytes, status propagation, and semantic round trip |
| Linux GitHub-hosted runner | Bash direct `>>` | Exact native stdout bytes and semantic round trip |
| macOS GitHub-hosted runner | Bash direct `>>` | Exact native stdout bytes and semantic round trip |
| Windows GitHub-hosted runner | PowerShell 7.4+ direct `>>` | Exact native stdout bytes, status propagation, and semantic round trip |
| Windows GitHub-hosted runner | Git Bash direct `>>` | `RUNNER_OS`-selected framing, exact bytes, and semantic round trip |

Legacy Windows PowerShell, PowerShell Core before 7.4, text-writing cmdlets,
`cmd`, and merged stdout/stderr redirection are negative documentation cases,
not supported configurations. A byte-capture-only test may use `>` with a new
temporary file; documented environment-file writes always use `>>` because `>`
can truncate prior records. PowerShell remains outside the release guarantee
until the Windows byte-capture, status-propagation, and runner differential
suites pass. Also test and document the failure of self-hosted Windows fallback
to unsupported Desktop PowerShell.

`github-actions:path` additionally requires the native Linux and Windows
grammar, parser, append-position, and ordering cases in the
[PATH command specification](commands/github-actions-path.md#command-specific-verification),
plus the shell tests in this section. A release must not infer path
compatibility from the named-writer tests.

`github-actions:state` additionally requires a local JavaScript fixture action
rather than an ordinary workflow `run:` step; composite actions cannot declare
a `post:` phase. Its `main` phase writes an attacker-style multiline value
through shoutx to `$GITHUB_STATE`, and its `post` phase verifies the exact
`STATE_NAME` value and the absence of a second attacker-selected key. A
case-collision case must read the first spelling of `STATE_NAME`; the runner
oracle is the discriminating name-spelling test because the Windows process
environment is case-insensitive. The fixture must also show that the state is
scoped to that action rather than exported as a general subsequent-step
environment variable. Generic shell-redirection coverage remains in the
named-writer shell matrix and is not inferred from this JavaScript fixture.

For each supported workflow shell, a negative smoke test must place another
successful command after a rejected `shoutx` invocation and still observe step
failure. This catches shells that would otherwise mask the native exit status.
Also test the runner-default stdin state with `VALUE` omitted, plus PowerShell
argv fidelity for an empty value, embedded quotes, and trailing backslashes.
Run concurrency tests with parallel writers to characterize, but not guarantee
against, interleaving and lifecycle behavior.

## PR acceptance criteria

The implementation PR following this design work should not be considered
ready until:

- every applicable current deterministic verification case in this plan and the
  linked command specifications is automated, including cases outside their
  normative Contract sections; historical research proof objectives are not
  additional implementation obligations;
- property tests establish the one-input-to-one-record invariant;
- the pinned runner differential suite passes on the CI platform matrix;
- supported shell redirection preserves stdout bytes;
- documentation names the tested runner versions and supported invocations;
  and
- a final security-focused review finds no unresolved high- or medium-severity
  contract, test, or implementation gap.
