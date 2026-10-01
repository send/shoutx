# GitHub Actions workflow-command parser compatibility

This note records compatibility evidence about the GitHub Actions stdout
workflow-command parser. It is descriptive evidence, not a command contract or
a decision to use either supported wire syntax. Normative behavior remains in
the command specifications, framing choices remain in decision records, and
release eligibility remains in the release policy.

## Finding

The pinned runner's V2 parser recognizes commands shaped like
`::command properties::data`. It trims leading whitespace, checks the initial
`::` with the culture-sensitive `StartsWith(string)` overload, and then finds
the data separator with the culture-sensitive .NET call
`message.IndexOf("::", 2)`. A server-supplied `system.culture` job variable can
set the worker's default culture. The child process that emits the line cannot
reliably observe that worker state.

This makes an ASCII protocol delimiter depend on ambient collation. Under
`th-TH` on .NET 8, the pinned parser does not recognize the ordinary
ASCII-only record `::add-mask::secret`. The pinned-parser regression proves
that parsing fails; it does not currently expose which culture-sensitive check
or search result caused that failure. The shoutx process has already completed
successfully, so an `add-mask` caller can receive a false success while the
runner installs no mask. The same V2 parser is used for notice, warning, and
error commands.

`th-TH` is a known counterexample, not a claim that Thai text or one culture is
the cause or the complete affected set. The input demonstrating the failure
contains no Thai or non-ASCII data. The relevant variable is locale-sensitive
protocol parsing whose result can depend on culture, collation backend, and
collation-data version.

## Parser fallback and impact

Before parsing, `OutputManager` uses culture-sensitive searches for either
`::` or `##[` as a prefilter. The command manager then tries the V2 parser
first and its legacy `##[command]data` parser second. The legacy parser searches
for `##[` anywhere in the line rather than requiring it at the start. A failed
V2 parse is treated as ordinary log output when legacy parsing also fails. If
the culture-sensitive legacy search succeeds, however, a registered workflow
command found later in the line is executed; value data containing
legacy-looking syntax can therefore become command syntax. The known `th-TH`
counterexample establishes the ordinary-output path, not this second condition.

The observable consequences differ by command:

- failed `add-mask` recognition makes `OutputManager` log the unrecognized
  command line as ordinary output, which can expose the value immediately, and
  leaves subsequent occurrences unmasked even though the producer exited
  successfully;
- failed annotation recognition can lose an annotation and log the encoded
  line as ordinary text; and
- a moved separator can change which text the runner treats as properties and
  data.

Environment-file writers do not pass through this stdout parser. This finding
does not override their separate destination-specific compatibility contracts.

## Evidence and environment variation

The explicit Invariant Culture / `en-US` regression
`CombiningMaskPrefixCanSelectLegacyWarning` feeds a synthetic `add-mask` value
beginning with a separator-sensitive scalar and containing
`##[warning]fallback` through the pinned
`OutputManager`. It checks that warning execution occurs instead of mask
registration. Unlike the unregistered-command fallback example, this input
starts with a registered V2 command. The
[mask specification](../commands/github-actions-mask.md) defines producer
rejection for this input; this is a regression test for the consumer defect, not an
accepted output.
The accepted mask and annotation corpora are also exercised explicitly under
both cultures. These are source-built oracle checks, not claims of exhaustive
Unicode coverage or measurements of a published hosted worker's runtime.

The earlier category-based mitigation used `unicode-general-category` 1.1.0,
whose tables declare Unicode 16.0.0. That producer table did not establish a
match with the worker's ICU/NLS data: newly assigned scalars, Unicode-version
skew, and differences between category and collation behavior limited that
mitigation. The category set was conservative, not a claim
that every rejected scalar reproduces the U+0301 failure.
Additional local Invariant Culture / `en-US` probes found U+0E33, U+0EB3,
and all five U+1F3FB--U+1F3FF scalars fail V2 parsing despite being outside
the category set. The oracle includes these as raw fallback counterexamples;
the current ASCII boundary policy also rejects them at the boundary.
This input-dependent issue with Thai/Lao characters is distinct from the
deferred `th-TH` culture failure for ordinary ASCII input.
Sequences U+200D U+0301, U+200C U+0E33, and U+E0020 U+1F3FB also fail
under both cultures despite beginning outside the category set. Tests include
these and a mixed run of joining/tag scalars followed by U+0301. The shared
input rule previously looked past a specified leading run for validation.
The current allowlist rejects that leading run instead.

PR #42 added a pinned-runner regression proving the ASCII-only `th-TH` V2
failure and comparing the legacy parser under selected cultures. The current
fixture also drives the counterexample through `OutputManager`, proving
ordinary logging after failed recognition. A separate `OutputManager` case
proves that a failed V2 parse can execute a registered legacy command found
later in the same line; it does not claim that this fallback occurs under the
known `th-TH` counterexample. The oracle runs on Ubuntu 22.04, Ubuntu 24.04,
macOS, and Windows. The oracle now records runtime/build, OS, architecture,
culture, internal globalization-mode flags, and `CompareInfo.Version`. Its
backend label follows observed flags rather than the OS label. The native
backend library version is not observed; the sort version is not a substitute
for that version. Earlier runs did not record these fields.
When private flags are absent the backend label is `Unknown`, as observed
locally on macOS ARM64 with .NET 8.0.30. Such a run is compatibility regression
evidence, not confirmation that the inspected ICU path executed.

That expansion also exposed a separate portability assumption in an existing
test. An assertion expecting U+11F02 to move the V2 separator passed on the
newer environments but failed on Ubuntu 22.04, where the runner decoded the
earlier separator instead. The scalar was removed from the shared portable
runner-oracle assertions; the ASCII header policy now rejects it. The
failed [PR #42 CI run][u11f02-run] is evidence that a
Unicode category or scalar denylist cannot stand in for the destination parser:
the same runner source and .NET SDK can behave differently across platform
collation data.

The tests are evidence and regression detection, not proof over all present
or future cultures. They do not establish a supported-culture allowlist or
show that a Unicode scalar or category restriction can repair V2 framing.

## ASCII boundary allowlist derivation

The narrow producer policy is specified in the
[annotation contract](../commands/github-actions-annotations.md#command-line-grammar-and-input)
and shared by mask. It restricts the complete encoded header and the first
encoded data character to printable ASCII. It does not restrict subsequent
Unicode data. This deliberately rejects Japanese/emoji message starts and
non-ASCII TITLE/FILE values instead of changing their meaning.

This is a sufficient-condition argument for an inspected implementation, not
a guarantee made by the public Runner or .NET API. In the
[.NET 8.0.0 ICU comparison implementation](https://github.com/dotnet/runtime/blob/v8.0.0/src/libraries/System.Private.CoreLib/src/System/Globalization/CompareInfo.Icu.cs),
Invariant and English sort names enable `_isAsciiEqualityOrdinal`. With
`CompareOptions.None`, `IcuIndexOfCore` can use `IndexOfOrdinalHelper`: it
falls back to native collation when special/non-ASCII characters are encountered
in the searched region or immediately after a candidate match. Otherwise an
ASCII match returns its ordinal position without inspecting the remaining tail.
`HighCharTable` is false throughout U+0020--U+007E, including apostrophe
(U+0027) and hyphen (U+002D); neither forces a native fallback in this code.

For shoutx's fixed command prefix, escaped ASCII properties, and ASCII first
encoded data character, the intended `::` separator is found on that fast
path. Property colons are escaped, so there is no earlier property separator.
Restricting only the last property character would not provide this argument:
non-ASCII earlier in the header could force native collation first. The initial
`StartsWith("::")` similarly has a fixed ASCII command character after its
match. Successful V2 parsing prevents the command manager's legacy fallback.
The `OutputManager` prefilter is only a boolean gate and sees the initial `::`.
CR/LF and percent escaping produce ASCII wire characters while preserving the
decoded value; arbitrary Unicode escape notation is not decoded by Runner.

ICU's [string-search documentation](https://unicode-org.github.io/icu/userguide/collation/string-search.html)
describes grapheme-boundary restrictions, explaining why general categories
alone were insufficient. The allowlist argument above avoids relying on a
producer-maintained approximation of those Unicode boundaries.

The source originally inspected here is .NET **8.0.0**. The
[published-package investigation](runner-package-runtime.md) additionally
checks the corresponding case-sensitive path at a specific **8.0.30** commit
and binds package execution to its build identity. It does not establish the
same behavior for every later .NET 8 patch. NLS, hybrid globalization, other cultures, and
future implementation changes are outside this source argument. In particular,
the known `th-TH` failure is not fixed. The commands remain research-only.
The oracle records its actual runtime and tests every non-NUL Unicode scalar
after each of `A`, `:`, `%`, space, `-`, apostrophe, `#`, and `0`, for mask and
an annotation header with TITLE/FILE under Invariant and `en-US`.
Generated producer corpora additionally combine every allowed first scalar
with selected hostile Unicode tails, check exact data/properties, and exercise
the command manager. These finite checks detect regressions; they are not
exhaustive over Unicode sequences, backends, or runtime versions.

## V2 Unicode data-start investigation

The interim ASCII policy is a sufficient condition only within the inspected
ICU implementation and culture scope above, not a necessary condition for all
observed V2 successes. Preliminary local probes used runtime-dependent
Unicode category and segmentation tables, which cannot be assumed identical
to the consumer's collation data. Those exploratory probes are not the
reproducible cross-platform evidence for this candidate.

Testing an explicit candidate does not contradict the earlier rejection of
category-only mitigations: a positive category/GCB intersection is a hypothesis
to challenge against the consumer, not an approximation declared equivalent
to its parser or a general framing repair.
The reproducible follow-up instead pins Unicode 14.0.0, corresponding to the
oldest ICU generation in the previously measured package matrix
([ICU 70 uses Unicode 14](https://icu.unicode.org/download/70)), and selects
the same candidate on every OS. Its exact predicate and coverage belong to
the [test plan](../test-plan.md#v2-unicode-data-start-research).

This is a V2-only research direction. ICU search includes collation-element
and normalization checks as well as character boundaries; a local passing
table or fixed-length corpus does not prove arbitrary sequences or future
collation data. Neither the CLI's ASCII boundary policy nor metadata acceptance
is changed. Legacy framing is excluded from this investigation by maintainer
direction; the earlier proposed framing record is not an adoption decision.

### Remaining source argument

In [.NET 8.0.30 `pal_collation.c`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_collation.c),
`GetCollatorFromSortHandle` uses the locale's base collator for options zero;
`GlobalizationNative_IndexOf` obtains a search iterator and calls `usearch_first`.
The package harness pins and verifies this native source's digest, not the
correctness of this manual analysis or a source-to-native-binary attestation;
see the [package evidence limits](runner-package-runtime.md).
The nonzero-options custom-rule path must not be assumed to describe this
default search. In [ICU 76.1 `usearch.cpp`](https://github.com/unicode-org/icu/blob/release-76-1/icu4c/source/i18n/usearch.cpp),
the forward search checks collation-element offsets, partial expansions, break
boundaries and an `allowMidclusterMatch` normalization-boundary exception.
Only ICU 76.1 was source-inspected here; these conclusions must not be silently
extended to the other observed ICU versions, including local ICU 78.1.
This argument concerns native `IndexOf`, not the separate fixed-header
`StartsWith`/`SimpleAffix` path.

Importantly, .NET's `CreateCustomizedBreakIterator` first compiles its own newer
rule set, tries an older rule set if that fails, and returns null if neither can
be created. It passes that result to ICU's search iterator. These rules omit
the usual CR/LF non-break rule. Search iterators are cached by sort handle and
options; later iterator creation can reuse the process-cached rule text and
return null if reopening it fails. The selection is not freshly made on every
search call. With a non-null external iterator, the inspected
ICU search uses that iterator and its `allowMidclusterMatch` exception is
disabled; with null it uses its internal character iterator. Neither a default
ICU character-boundary probe nor .NET `StringInfo` alone establishes which path
this search used. Current evidence does not observe the selected custom rule
set or null fallback. It must not label that choice based only on ICU version.

For the newer custom rules, a useful conditional argument is visible directly
in the rule text: an ASCII colon is neither Hangul, Prepend, regional indicator,
linking consonant nor extended pictograph. The rules that can join it directly
to the following character are therefore the Extend/ZWJ and SpacingMark rules.
The candidate's positive GCB set excludes those classes. Provided the consumer
assigns the same relevant properties and this rule set is active, subsequent
characters do not bridge that particular break. This explains the boundary
hypothesis, but says nothing by itself about collation-element contractions,
normalization or the unknown-rule/fallback path.

This inspection identifies proof obligations, not a completed derivation of
the candidate rule across the package matrix:

- Establish that the fixed ASCII header's delimiter collation elements cannot
  be changed by a contraction or contextual rule extending into arbitrary data.
- Establish that the selected first scalar preserves an acceptable end boundary
  for that delimiter even when normalization, ignorables and later combining
  sequences affect the following collation elements.
- Check those properties against the actual consumer collation/break data and
  search implementation for each claimed backend/version. The producer's
  pinned UCD table alone does not establish their stability.

The [ICU search documentation](https://unicode-org.github.io/icu/userguide/collation/string-search.html)
describes language-sensitive matching and normalization; it does not supply
this protocol-specific guarantee. Finite parser stress tests and the separate
package Worker-effects cases in the test plan address observed behavior, not
these universal obligations. The latter use generated research wires, not new
CLI acceptance or a live hosted Worker measurement.

## Self-hosted runner version snapshot

Queries completed at 2026-09-29T08:45:53Z. The official releases API listed
the following stable non-draft, non-prerelease runner versions from v2.329.0
onward. The repository-scoped deprecation endpoint for `send/shoutx` returned
HTTP 200 for each query with these `runtime_deprecates_at` values:

| Runner release | Runtime deprecation |
| --- | --- |
| `v2.329.0` | `2026-01-23T17:10:35Z` |
| `v2.330.0` | `2026-03-13T18:34:13Z` |
| `v2.331.0` | `2026-04-30T21:52:20Z` |
| `v2.332.0` | `2026-05-25T15:23:35Z` |
| `v2.333.0` | `2026-05-29T17:27:54Z` |
| `v2.333.1` | `2026-06-30T15:52:45Z` |
| `v2.334.0` | `2026-08-10T17:08:55Z` |
| `v2.335.0` | `2026-08-14T16:59:37Z` |
| `v2.335.1` | `2026-09-24T15:30:55Z` |
| `v2.336.0` | `2026-11-05T08:04:55Z` |
| `v2.337.0` | JSON null |

The query listed all stable releases through the then-latest v2.337.0. It used
v2.329.0 only as a finite observation bound because GitHub's September 28
announcement named it as the registration floor; this does not show that an
older, already-registered runner could not execute a job. The procedure queried
`GET /repos/send/shoutx/actions/runners/deprecations/{version}` for each. It used
API version `2026-03-10` and an authenticated classic token with `repo` scope
owned by the repository administrator. The timestamps above are the verbatim
JSON strings. These are dated observations, not a substitute for a future
query or evidence that enforcement had occurred exactly at each timestamp.

For this repository, v2.336.0 returned a future runtime-deprecation date and
v2.337.0 returned JSON null in that snapshot. A past date is not evidence that
enforcement occurred at that instant, and null is recorded without inferring
an undocumented meaning. The responses do not establish that another
repository, organization, enterprise, or data-residency region observed the
same schedule.

The `ActionCommand.cs`, `ActionCommandManager.cs`, and `OutputManager.cs` blobs
are identical in v2.336.0 and v2.337.0: respectively
`c51fa5a342806e296ad6af3e15735984feb29155`,
`4b9995fc89dd2c2b5e4115afd646f920de0bef82`, and
`32d1e78c21cbef0727facc67527af3946aa73bc6`. The release commits are
`98aabcd429c4e8402406c56ce2d26387fed3b9ce` and
`397b032cbf865e9c3ddfab89d533ec19325e1273`. Source identity does not prove
packaged-runtime identity: the source trees pin .NET SDK 8.0.422 and 8.0.424
respectively, and installed globalization data can differ by host.

GitHub documents a general 30-day self-hosted update requirement. Its September
28, 2026 announcement distinguishes the registration minimum from runtime
eligibility and says that the announced Enterprise Cloud enforcement does not
apply to GitHub Enterprise Server.

The source-built oracle executes v2.337.0. The additional
[package-backed probe](runner-package-runtime.md) checks its distributed
parser/runtime, but neither tests v2.336.0 nor establishes a supported
self-hosted compatibility matrix. This section records evidence only; the
proposed interpretation and unresolved policy live in the framing decision.

The product-level syntax and data rules are authoritative in
[`design.md`](../design.md). Verification requirements and the framing choice
belong to the decision record below, not this evidence note.

## Open decision and upstream reminder

The framing options and their status are maintained in the
[stdout framing decision record](../decisions/github-actions-stdout-framing.md).
This compatibility note does not select one.

The separate [upstream reminder](https://github.com/send/shoutx/issues/43)
records maintainer-owned follow-up timing.

## Primary evidence

- [`ActionCommand.cs` in the pinned runner][pinned-parser]
- [`ActionCommandManager.cs` in the pinned runner][pinned-manager]
- [`OutputManager.cs` in the pinned runner][pinned-output-manager]
- [GitHub runner releases API][runner-releases-api]
- [GitHub self-hosted runner update policy][runner-update-policy]
- [GitHub runner-version deprecation API][runner-deprecation-api]
- [September 2026 enforcement announcement][runner-enforcement]
- [Runner v2.336.0 release][runner-2336]
- [Runner v2.337.0 release][runner-2337]
- [Microsoft .NET globalization and ICU behavior][dotnet-icu]
- [`ShoutxDifferentialL0.cs`](../../tests/runner-oracle/ShoutxDifferentialL0.cs)
- [PR #42](https://github.com/send/shoutx/pull/42)
- [Issue #43](https://github.com/send/shoutx/issues/43)
- [Microsoft guidance for culture-insensitive string operations][dotnet-guide]

[pinned-parser]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Common/ActionCommand.cs
[pinned-manager]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs
[pinned-output-manager]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/Handlers/OutputManager.cs
[runner-releases-api]: https://docs.github.com/en/rest/releases/releases?apiVersion=2026-03-10#list-releases
[runner-update-policy]: https://docs.github.com/en/actions/reference/runners/self-hosted-runners#runner-software-updates-on-self-hosted-runners
[runner-deprecation-api]: https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2026-03-10#get-runner-version-end-of-life-schedule-for-a-repository
[runner-enforcement]: https://github.blog/changelog/2026-09-28-self-hosted-runner-version-enforcement-date-has-moved/
[runner-2336]: https://github.com/actions/runner/releases/tag/v2.336.0
[runner-2337]: https://github.com/actions/runner/releases/tag/v2.337.0
[dotnet-icu]: https://learn.microsoft.com/en-us/dotnet/core/extensions/globalization-icu
[dotnet-guide]: https://learn.microsoft.com/en-us/dotnet/core/extensions/performing-culture-insensitive-string-operations
[u11f02-run]: https://github.com/send/shoutx/actions/runs/36451589798/job/109027454250
