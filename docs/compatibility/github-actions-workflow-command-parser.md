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

### Culture diagnostic observation route

The 2026-10-04 [feasibility audit](unicode-feasibility.md) inspected the local
Runner checkout at pinned commit `397b032cbf865e9c3ddfab89d533ec19325e1273`.
[`Worker.SetCulture`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Worker.cs)
consumes the job's culture before starting `JobRunner`.
[`HostContext.SetDefaultCulture`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/HostContext.cs)
sets both default thread cultures and emits a verbose trace of the name.
This establishes a source route, not a hosted job's actual input.
The release default is Info in
[`TraceSetting`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/TraceSetting.cs),
so a missing verbose line does not establish absence of a culture setting.
Worker also logs the job message at Info after initialization. That message
may contain sensitive data and must not be copied into public evidence.
Any diagnostic projection needs trustworthy job/process correlation and
strict output selection; startup information alone does not establish later
thread state, effective native inputs or transfer to an unobserved culture.

For diagnostic job correlation, pinned
[`ExecutionContext`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ExecutionContext.cs)
initializes `github.job` from `system.github.job`, then overlays the supplied
`github` context. `message.JobName` is a timeline reference, not an established
source of `GITHUB_JOB`. The observer follows the resolved context rather than
assuming those two names match.

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
default search. In the upstream ICU versions inspected below,
the forward search checks collation-element offsets, partial expansions, break
boundaries and an `allowMidclusterMatch` normalization-boundary exception.
The upstream comparison is not an attestation of vendor-patched OS binaries.
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
this search used. The parser/Worker suites do not observe the selected custom
rule set or null fallback. The separate
[native observation](../test-plan.md#native-collation-observation) compares the
actual iterator's binary rules with freshly compiled source rules; only its
fresh passing results establish that choice for the option-zero head
iterator at observation time, not overflow nodes or earlier Worker calls. Do not
label the choice based only on ICU version.

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

### Upstream comparison and conditional end-boundary argument

Source inspection on 2026-10-02 compared these upstream releases with the
versions reported by [PR #62's four-OS run](https://github.com/send/shoutx/actions/runs/36895636468)
and the local package probe:

| Observed environment | Reported ICU | Inspected upstream `usearch.cpp` |
| --- | --- | --- |
| Ubuntu 22.04 | 70.1.0.0 | [70.1](https://github.com/unicode-org/icu/blob/release-70-1/icu4c/source/i18n/usearch.cpp) |
| Windows Server 2025 | 72.1.0.4 | [72.1](https://github.com/unicode-org/icu/blob/release-72-1/icu4c/source/i18n/usearch.cpp) |
| Ubuntu 24.04 | 74.2.0.0 | [74.2](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/i18n/usearch.cpp) |
| macOS 15 | 76.1.0.0 | [76.1](https://github.com/unicode-org/icu/blob/release-76-1/icu4c/source/i18n/usearch.cpp) |
| Local macOS ARM64 | 78.1.0.0 | [78.1](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/usearch.cpp) |

These are upstream comparison points, not claims that a version string proves
binary equivalence. In particular, the Windows fourth version component and
Apple's system library are not authenticated by those upstream tags. The CI
run predates the later Python old-rule-evidence hardening; its native probe
implementation already includes the embedded-resource digest check.

The inspected `getBreakIterator`, `usearch_getBreakIterator`,
`nextBoundaryAfter`, `isBreakBoundary` and forward `usearch_search` paths agree
on the relevant behavior: the getter returns the externally supplied iterator,
the internal character iterator is used only when that field is null, and a
non-null external iterator disables `allowMidclusterMatch`. The discriminating
forward-search branch conditions below agree across these versions. This is
not a claim that the entire source files are identical (78.1 changes
pattern-buffer allocation, for example).

The corresponding `UCollationPCE::nextProcessed` implementations skip processed
zero-weight elements and return the offsets associated with the next retained
element. The corresponding `ContractionsAndExpansions::forData` implementations
enumerate tailoring data, then base data for code points not overridden by the
tailoring. See the representative
[processed-element loop](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/i18n/ucoleitr.cpp#L329-L365)
and [base-data traversal](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/i18n/collationsets.cpp#L392-L411).
`ucol_getContractionsAndExpansions` reaches that traversal through
`RuleBasedCollator::internalGetContractionsAndExpansions`; with prefixes enabled,
the set contains prefix and contraction strings, not merely locale-specific
differences. Thus the measured absence of colon from reported contexts does not
omit all root contexts. It still is not a complete proof about CE offsets,
normalization or discontiguous matching. Nor does a zero colon-context count
constrain contexts formed entirely within the data, or enumerate every other
context-sensitive collation mechanism. The traversal is upstream-source
evidence; the counts are observations of the separate OS binaries.

The key conditional argument can now be stated without assuming the first data
scalar has a nonzero collation weight. Let `d` be the UTF-16 index immediately
after the intended two-colon delimiter. Assume the fixed validated header has
no earlier matching delimiter, processing completes without status or resource
errors, the search uses default element comparison and a non-null external
iterator with the newer custom rules, and the delimiter matches in processed
collation-element space with:

- the first matched element starting at the intended delimiter and passing
  the start-boundary/partial-expansion checks;
- the last matched element ending at `d`, with its low offset below `d` (or
  equal to `d` for the handled expansion case);
- the next retained element's low offset at least `d`, and no rejected partial
  expansion after the match;
- an accepted external break at `d`, with no break strictly after the last
  matched element's low offset and before `d`, and no rejecting identical-strength
  comparison.

Default element comparison is source-supported: ICU initializes the attribute
to zero, and the pinned `pal_collation.c` does not call `usearch_setAttribute`.
The [native-observation suite](../test-plan.md#native-collation-observation)
now also records the search object's public attribute, using the public enum
mapping documented in the test plan rather than the internal mode's value.

On this external-new-rule path, the inspected forward search chooses
`mLimit = d`: it keeps the initial `mLimit = maxLimit` (equal to `d` when
`minLimit = maxLimit`),
accepts the already-ended expansion boundary, or obtains `d` from
`nextBoundaryAfter`. This derivation does not cover null/internal or old-rule
iterator paths.
Since `d <= maxLimit`, skipping following zero-weight elements does not itself
invalidate the delimiter. This is a derivation from the branch conditions,
not a proof that all of its premises hold for every candidate/suffix. Runner
uses the returned start index plus the literal delimiter length to slice data,
not ICU's matched length; the match must nevertheless survive these end checks.

All four CI environments and the local probe report the same five candidate
scalars equal to empty under invariant and en-US `CompareInfo`: U+0640 ARABIC
TATWEEL, U+07FA NKO LAJANYALAN, U+180A MONGOLIAN NIRUGU, U+1CD3 VEDIC SIGN
NIHSHVASA and U+FE73 ARABIC TAIL FRAGMENT. Interpretation of the count remains
in the [native-observation test plan](../test-plan.md#native-collation-observation).
Equal-to-empty comparison of an isolated scalar neither demonstrates a failure
nor proves context-independent zero weight. Their finite parser checks pass,
but the third premise above becomes suffix-dependent if the first scalar's
processed elements are all skipped: the next retained element can come from
arbitrary later data. Under default element comparison, a nonterminal next
element with equal low/high offsets rejects the delimiter. A later mapping
whose leading elements are skipped but whose subsequent element is retained
is therefore a case to rule out, not a demonstrated counterexample in the
observed collation data. If the delimiter is rejected, search can continue to
a later delimiter inside the data. Even for a non-ignorable candidate, its
first retained element and contextual offset behavior require justification.

The measured NFD `hasBoundaryBefore` property is stronger than a finite suffix
test: the [API contract](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/common/unicode/normalizer2.h#L463-L476)
describes a context-independent normalization boundary before that scalar.
This is a separate normalization fact, not an end-check executed on the
external-iterator path: the search's direct NFD boundary query is inside
`allowMidclusterMatch`, disabled on that path. To use this fact in the CE-offset
premises requires connecting it to the effective collator's normalization
behavior (and any identical-strength comparison). The native-observation suite
now records those settings and finite raw CE-offset samples under guarded
tertiary/non-ignorable settings. It does not by itself establish arbitrary-context
processed-element offsets or identify
every iterator used by a live Worker.

**Adoption checkpoint:** the evidence supports a conditional candidate, not an
unconditional CLI allow-list expansion. Actual collator/search settings and
finite CE-offset checks are now part of the package research gate; fresh results
are required for each supported test environment, not inferred from local success.
For starts whose elements can all be skipped, finite offset samples cannot
close the suffix-dependent premise: it needs an invariant over all possible
following mappings and contexts at the active settings, or a justified narrower
acceptance rule. Excluding these five alone would not prove the other candidates
safe. For the remaining candidates, establish that their leading retained
elements and contextual offsets satisfy the premises. The
[research-scope decision](../decisions/github-actions-unicode-scope.md) now fixes
the initial investigation target, with explicit
[completion criteria](../test-plan.md#unicode-adoption-completion-criteria).
The supported consumer scope remains undefined as a product contract. Before
implementation, an explicit compatibility decision must establish that scope
and address unobserved/old/null-iterator paths; [the design](../design.md) will
own the accepted boundary. A separate producer cannot enforce the
worker's runtime, culture or iterator choice. This does not
reopen legacy framing, the deferred `th-TH` decision, metadata acceptance or
release eligibility.

### Positive leading-mapping criterion (research proposal)

The next proof target is a positive sufficient condition, not the existing
candidate set minus the five observed empty-equivalent scalars. It is not yet
an acceptance rule or a generated allow-list. It must hold for each supported
consumer configuration; passing one configuration cannot authorize another.

Keep the header, delimiter and external-break premises above as separate
obligations. For the remaining next-element premise, consider the iterator
state immediately after the intended delimiter at `d`. A deliberately strong
sufficient condition is that, for every permitted suffix following an accepted
initial scalar:

- no pending delimiter expansion or continuation remains to be returned;
- the first raw 32-bit element returned after that state is retained by the
  search's processed-element conversion; and
- that call starts at `d` and ends strictly after `d`, without an error.

Here the suffix universe is the wire-encoded image of arbitrary non-NUL
Unicode-scalar sequences following that scalar, subject to the destination's
other validation and size rules, but not its current ASCII-first restriction.
Percent, CR and LF undergo the existing data escaping; literal later `::`
sequences remain in scope. Strict UTF-8 input excludes unpaired surrogates on
the supported UTF-8 consumer-decoding path; see the
[annotation consumer prerequisites](../commands/github-actions-annotations.md).
Non-UTF-8 native-output encodings are outside that scope.
Finite hostile-tail samples do not define or narrow this universe.

This would make the next retained element's low offset `d` and its high offset
greater than `d`, satisfying that particular search check without inspecting
additional elements in that check. Establishing the condition still requires
reasoning about arbitrary later text. It does not prove the other delimiter or break
premises. Nor is it a necessary condition: a scalar failing this stronger rule
could still be safe under a different, separately justified argument.

The requirement is stable **boundary behavior**, not identical weights or
identical consumed lengths for every suffix. A contraction may consume more
than the initial scalar and emit different weights while still satisfying the
condition. Thus contextual mappings, languages and scripts are not rejected
merely for having contractions.

This formulation follows the inspected upstream implementation. The links below
identify the individual releases inspected, not a version-independent API
guarantee. The mapping inventory is based on the 78.1 source; any verifier must
pin and justify its traversal for each supported release and native data set:

- [`UCollationPCE::nextProcessed`](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/i18n/ucoleitr.cpp)
  records offsets around each raw-element call and repeats when the processed
  element is ignorable. Whole-string inequality to empty does not establish
  that the *first* raw element is retained. The
  [normal UTF-16 offset argument below](#normal-utf-16-source-offset-argument-research-draft)
  separately checks this composition against the 78.1 loop.
- [`CollationElementIterator::next`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/coleitr.cpp)
  splits an internal 64-bit element into 32-bit parts; a pending second part
  does not advance the underlying iterator. Checking only a nonzero internal
  64-bit element would therefore be insufficient.
- [`appendCEsFromCE32` and `nextCE32FromDiscontiguousContraction`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.cpp)
  select contextual mappings and append their elements. In the top-level
  discontiguous-match path, the selected contraction mapping is appended
  before the skipped marks. This suggests a mapping-based proof obligation,
  but does not alone prove final iterator offsets for every path.

The proposed verification unit is consequently each reachable leading mapping,
not a list of failing code points or a growing collection of suffix examples.
An exhaustive verifier would need to cover the default and applicable
prefix/contraction branches, base-data fallback, expansions, non-numeric digit
indirection, Hangul/Jamo processing, supplementary scalars and algorithmic
offset/implicit mappings. Unknown mapping types, incomplete traversal, or
settings outside the justified scope must yield **unverified**, not accepted.
It must justify both the first emitted 32-bit element and the source-offset
invariant, including lookahead restoration, skipped-mark handling and the
actual normalization iterator. Enumeration of finite mapping choices does not
by itself prove the behavior of arbitrarily long lookahead.

Prefix mappings also require lookbehind and restoration across `d`: the
applicable branch depends on the preceding encoded header, not just the data
suffix. The header is fixed for a given emitted record, but varies across
supported commands and metadata. A shared table needs an argument covering all
permitted headers, not just the observed zero-colon-context result. This does
not require enumerating header values: the inspected prefix trie stops on a
failed transition, and the first lookbehind scalar is the delimiter's final
colon. Proving that no applicable loaded prefix ends in colon can discharge
the header-dependence part for that configuration. Iterator restoration still
requires its own argument.

In the inspected 78.1 `coleitr.cpp`, `setText(const UnicodeString&)` selects
`UTF16CollationIterator` when `dontCheckFCD()` is true, otherwise
`FCDUTF16CollationIterator`. The former's forward offset is the source-pointer
distance; the latter can report normalization-segment boundaries (see
[`utf16collationiterator.cpp`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/utf16collationiterator.cpp)).
The selector tests the `CHECK_FCD` bit in
[`collationsettings.h`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationsettings.h);
the inspected 74.2
[`RuleBasedCollator::getAttribute`](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/i18n/rulebasedcollator.cpp)
uses that same named bit for `UCOL_NORMALIZATION_MODE`; its setter writes it
as well. This comparison pairs the 78.1 selector/settings source with the 74.2
getter/setter, rather than establishing all parts in one release. These are not
independent settings in that source model. Connecting the observed attribute to the actual
search iterator construction, and proving offsets through all reachable paths
for each supported release, remain obligations; inspecting these methods is not
that proof.

The existing public context-string enumeration is not yet that verifier.
For example, testing a complete prefix-context string can observe the prefix's
first element rather than the target mapping's first element. Default branches
and indirect mappings also need explicit coverage. A standalone upstream build
would be useful for developing the traversal, but would not attest to the
loaded OS collation data. Connecting the proof and exhaustive data checks to
each supported native consumer remains an implementation prerequisite.

The research target is a generated, configuration-scoped positive table whose
entries have this justification. A producer unable to identify its consumer
would need the intersection over all explicitly supported configurations and
headers, not the union or a table selected from the producer's own locale.
That does not establish safety outside the supported scope. Whether and how to
ship such a lookup belongs in a subsequent design decision and command contract,
not this compatibility proposal. Neither the table's final size nor
inclusion/exclusion of particular scalars has been established.
This proposal introduces no trimming, Unicode
normalization, language-specific subset, or CLI acceptance change.

### Normal UTF-16 source-offset argument (research draft)

The following separates source-cursor movement from mapping weights. It is an
argument about the upstream **78.1 non-FCD forward iterator**, not a claim that
the loaded Runner uses this exact implementation. It does not change the CLI
or turn the offline mapping report into an acceptance table.

Let `d` be the source offset immediately after the intended delimiter and `p`
the offset immediately after reading the first complete data scalar. For a
well-formed, explicitly length-bounded UTF-16 string, `p = d + 1` or `d + 2`.
Assume the underlying `pos - start` equals `d` at a scalar boundary and
`CollationElementIterator` is in forward mode (`dir_ > 1`), so its `getOffset()`
uses the underlying iterator rather than backward-offset bookkeeping.
Assume successful forward iteration, numeric collation off, no unreturned
64-bit CE, no pending 32-bit continuation, an empty skipped-mark buffer, and
`numCpFwd < 0` at entry. The last condition excludes the limited forward replay
used by backward iteration. The initial scalar exists; an empty value needs
its own delimiter argument. Allocation failures, invalid data, integer overflow
and resource exhaustion are not successful executions covered here.

These entry conditions matter independently of a numeric offset of `d`:
[`nextCE`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.h)
returns an available buffered CE without reading text, and
[`CollationElementIterator::next`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/coleitr.cpp)
does the same for `otherHalf_`. Establishing the conditions after the actual
encoded header remains a separate consumer obligation.

In
[`UTF16CollationIterator`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/utf16collationiterator.cpp),
`getOffset()` is `pos - start`. `handleNextCE32()` consumes one code unit; the
valid supplementary path consumes its trail through `handleGetTrailSurrogate()`.
This requires the first-read lead-unit trie entry itself to carry the
lead-surrogate tag; well-formed input alone does not validate that data entry.
Plain `FALLBACK_CE32` at that first-read entry is unverified here: `nextCE()`
resolves it via the base data's
[`getCE32(c)`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationdata.h),
a code-point lookup for the lead unit, not a base lead-unit lookup. This
argument does not infer that such fallback consumes the trail or reaches `p`.
At scalar boundaries, forward and backward code-point operations undo each
other when applied to the number of code points actually traversed. End-of-text
returns a sentinel without advancing. The explicit length bound also excludes
the NUL-terminated mode in which `foundNULTerminator()` decrements `pos` and
forward restoration can stop at NUL. Upstream 78.1 `setText(const UnicodeString&)`
passes `s + string_.length()` as the limit; connecting this construction to the
loaded search iterator remains a consumer-identity obligation. The proposed
wire-value universe independently excludes NUL.

These facts give the following local
case analysis of
[`appendCEsFromCE32` and its context helpers](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.cpp):

| Path | Source-cursor effect on successful completion |
| --- | --- |
| Simple, long-primary/secondary, Latin expansion, expansion32, CE64 expansion, offset or implicit mapping | No further text movement after the initial scalar. Multiple emitted CEs do not imply multiple source reads. |
| Non-numeric digit indirection or resolved base fallback | Mapping selection itself does not move the cursor; the selected mapping still needs this case analysis. Plain fallback at the first-read lead-unit entry is excluded as described above. |
| Prefix lookup | At a physical scalar boundary strictly after `start`, the outer backward-one/forward-one pair encloses a lookup that counts actual successful backward reads and restores exactly that count. Lookup restores its entry position, even if it reaches the start of the string. The subsequently selected mapping must be checked separately. |
| Contiguous contraction | Lookahead starts after the original scalar. `sinceMatch` counts successfully read suffix scalars since the last selected match, initially the default. Failed partial matching rewinds that count, not the original scalar. End-of-text adds no count. A final match retains its consumed suffix. Before deciding whether to try discontiguous matching, the helper may rewind `sinceMatch`, refetch one scalar, reduce `lookAhead` by `sinceMatch - 1`, and set `sinceMatch = 1`; this also preserves the lower bound. |
| Hangul | The fast Jamo path does not move text. The recursive path requires the cursor property for **every** emitted L/V/T mapping, not only the first L mapping whose weight determines the first raw half. |
| Lead-surrogate tag | With the tag present at the first-read lead-unit entry and paired input, consumes the trail to reach `p`; the resolved supplementary mapping then needs this case analysis. |
| U0000 tag | The explicitly bounded mode does not take the decrementing NUL-terminator path; its indirect mapping still needs checking. Literal NUL is outside the proposed input universe. |

Numeric digit processing is excluded by the numeric-off assumption, not by a
claim that its lookahead is cursor-neutral. Builder data is outside this runtime
data model: the inspected base `getCE32FromBuilderData()` reports an internal
error. Unresolved fallback and reserved-tag dispatch in `appendCEsFromCE32`
also report errors. Unknown or malformed tags are unverified, not additional
successful cases inferred from this table.

For the contiguous-contraction row, this covers executions that do not enter
`nextCE32FromDiscontiguousContraction`. A prefix may temporarily read before
`d`, so the property is a **return-position lower bound**, not a claim that the
cursor never crosses `d` internally. With valid, terminating mapping dispatch
and cursor-preserving/nondecreasing selected children, the listed paths return
at or after `p`, regardless of the contents or length of their lookahead. The
length bound is the existing input/resource bound, not a chosen test suffix
length. Prefix branch weights may still depend on the header. For virtual
skipped marks or recursively dispatched Jamo, prefix lookup examines the
physical text preceding the current cursor, not necessarily the mapping's own
scalar. Restoring the cursor does not remove these weight dependencies. The
outer backward-one step succeeds under the physical-position lower bound;
that premise must also be maintained for recursive dispatches.

#### Discontiguous matching: shared-buffer accounting

`SkippedState` in the same 78.1 source distinguishes virtual reads from its
`oldBuffer` and physical reads beyond that buffer. While the buffer is non-empty,
`nextSkippedCodePoint()` increments the beyond-buffer counter only after a
successful physical read. In that same non-empty case, `backwardNumSkipped(n)`
asks `SkippedState::backwardNumCodePoints(n)` how many
of those reads must be undone in physical text; rewinding only virtual marks
does not move the source cursor. With no buffer or an empty buffer, there is no
such accounting: the helper rewinds `n` physical scalars directly.
This is the mechanism needed for a
lower-bound argument, rather than an assumption that all skipped marks occupy
the current physical source position.

At the initial top-level discontiguous attempt, the early exits undo only the
one or two suffix scalars just read. Its optional trie replay rewinds
`lookAhead` suffix scalars and then advances the same count: the
`lookAhead - 2` matched scalars followed by the two lookahead scalars. It does
not rewind the original scalar. The matching loop records a new match with
`sinceMatch = 0`; later failure undoes only reads since that match. Thus the
top-level matching phase retains at least the original scalar.

That phase is **not the end of the raw-element call**. After `replaceMatch()`,
the top-level path appends the selected contraction's CEs, then resolves and
appends mappings for the skipped marks. Only after that work does
`nextCEFromCE32()` return the first buffered CE. Nested contractions can read
beyond the virtual buffer, replace it and restart virtual iteration. Therefore
the high offset observed by search is the position after this entire process,
not necessarily the position when the first CE was appended.

The induction below uses shared buffer state rather than a per-call count.
Its invariants are safety properties at accounting points of every finite
execution prefix satisfying the premises, including prefixes of a potentially
nonterminating run. If the raw-element call returns successfully, they imply
the stated return-position bound. This alone does not establish termination
or successful completion for every permitted suffix, and therefore does not
complete the positive leading-mapping criterion.

#### Buffer epochs and the physical lower bound (research draft)

Keep **all entry and execution premises above**, including well-formed UTF-16,
an initially empty skipped buffer, `numCpFwd < 0`, and the non-FCD, forward,
bounded-text and error-free conditions. In addition, all mapping dispatches
reached while processing the suffix must stay
within the described runtime tag model. In particular, the lead-surrogate tag
may occur only at the initial lead-unit dispatch, before `p` is established;
scalar/Jamo/context-result lookups must not introduce a later lead-unit tag.
Numeric processing, builder mappings, malformed data and uninspected overrides
are outside this argument. These are data/code premises to verify, not facts
implied by candidate membership or the current root-reader report.

Dispatch validity includes the scalar argument, not just the tag number.
Recursive Jamo children and the selected top-level discontiguous result are
dispatched with `c = U_SENTINEL`. For these dispatches, including their
indirectly selected mappings while `c` remains sentinel, this argument excludes
`HANGUL_TAG`, `OFFSET_TAG`, `IMPLICIT_TAG`, `U0000_TAG` and
`LEAD_SURROGATE_TAG`. They require a syllable, a code point, NUL, or a lead unit
respectively; an assertion is not a release-mode validity check. Other context
results retain the caller's scalar argument and must satisfy the corresponding
tag's preconditions. A verifier must track this dispatch context through
indirection, not assume that every context result has an ordinary scalar.

Define a *buffer epoch* to begin immediately after `replaceMatch()` leaves a
non-empty `oldBuffer` with its virtual position reset to zero. Let:

- `A` be the physical source cursor at that reset, a scalar boundary;
- `L` be the UTF-16 length of `oldBuffer`, which is fixed until replacement;
- `q` be `SkippedState::pos`, distinct from the physical source pointer; and
- `b = max(q - L, 0)` be the number of physical scalars currently accounted
  for beyond the virtual buffer.

At accounting points outside balanced prefix lookbehind, the proposed epoch
invariant is: the physical cursor equals the position reached by advancing
`b` complete source scalars from `A`. In particular it is at or after `A`.
Inside the buffer `q` is a UTF-16 index, but beyond `L` its excess is a
**scalar count**. Treating `q` uniformly as a physical UTF-16 offset would make
this invariant false for supplementary characters.

The 78.1 `SkippedState`, `nextSkippedCodePoint()` and
`backwardNumSkipped()` source cited above gives these transitions:

| Transition within a non-empty epoch | Effect on the invariant |
| --- | --- |
| Read a virtual mark | `next()` advances `q` by that scalar's UTF-16 width, at most to `L`; physical position and `b = 0` do not change. |
| Read physical text after virtual exhaustion | A successful `nextCodePoint()` advances one source scalar and `incBeyond()` increments `q` by one. Both the physical scalar distance from `A` and `b` increase by one. End-of-text changes neither. |
| Undo `n` scalars with `b >= n` | The helper subtracts `n` from `q` and requests `n` physical backward steps. Both distances decrease by `n`. |
| Undo with `0 < b < n` | It requests only `b` physical backward steps and moves `q` back inside the virtual buffer using code-point-aware indexing. The physical cursor returns to `A`, not before it. |
| Undo while `q <= L` | Only the virtual position changes; no physical backward step is requested. |

The UnicodeString operations used here have separate same-release evidence:
[`char32At`, `moveIndex32` and `doReplace`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/unistr.cpp),
with the inline `replace` overload and `pinIndices` in
[`unistr.h`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/unicode/unistr.h).
`char32At` reads a code point; `moveIndex32` uses bounded UTF-16 code-point
movement. The replacement overload delegates to `doReplace`. For the non-empty
old buffer, the destination range is clamped with `pinIndices`; the empty
old-buffer case instead takes the `start == oldLength` append path.
In `replace(0, q, ...)`, `q` is the **length of the range being replaced**,
not the starting index or inserted length. If `q > L` for a non-empty old
buffer, the removed range is clamped to the entire buffer; the inserted length
is `skipLengthAtMatch`. The same sources implement `remove()` by emptying the
string, `setTo(UChar32)` by replacing its contents, and `append(UChar32)` by
encoding and appending that scalar. These observations assume successful string
operations, consistent with the allocation/error exclusions above.

Prefix lookup is a balanced excursion in physical text: it restores its entry
position and does not modify `q` or `L`. The simultaneous induction hypothesis
is that the physical cursor is at or after `p > d >= 0` at every prefix step,
after `p` has been established, so its outer backward-one step has a preceding
scalar. The initial supplementary lead-unit dispatch can enter at `p - 1`,
but its required lead-surrogate tag consumes the trail before a prefix step.
In a non-empty epoch the bound follows from the anchor invariant; with an empty
buffer it follows from initial consumption, the matching-phase return bound
below, or a prior epoch whose replacement emptied the buffer without changing
the physical lower bound. The invariant is required after
restoration, not during lookbehind. This applies equally when the
mapping's scalar was virtual or a Jamo child; it says nothing about the chosen
prefix weight. The other permitted non-context tags do not move text after
the initial scalar. Recursive Jamo dispatch composes these same transitions.
The ASCII contraction fast path requires both `skipped == nullptr` and
`numCpFwd < 0`, so it cannot bypass this accounting during a non-empty epoch.

`replaceMatch()` changes the virtual buffer and resets `q` to zero without
moving physical text. If the old epoch satisfied its invariant and replacement
leaves a non-empty buffer, the next epoch's anchor is the current physical
position `A' >= A`. This holds whether the replacement retains unread virtual
marks or adds newly skipped physical marks. If replacement leaves the buffer
empty, no new epoch starts, but the physical lower bound is unchanged.
The new buffer need not represent a
contiguous physical substring; its reads are virtual. `clear()` likewise
does not move physical text, but ends buffer accounting.

The empty-buffer case needs a separate argument: there is no beyond counter
to cap a direct rewind. Define matching-phase entry before the first suffix
lookahead read in `appendCEsFromCE32`, not at the later helper call that already
receives a consumed lookahead scalar. From that entry until the matching
phase's final rewind (if any), the buffer's emptiness cannot change.
Those phases do not dispatch another mapping or call `replaceMatch()` or
`clear()`. A newly allocated `SkippedState` is empty; `setFirstSkipped()`,
`skip()` and `recordMatch()` modify new-buffer bookkeeping, not `oldBuffer`.
Thus each direct rewind undoes physical reads counted by that matching phase.
The early exits, contiguous rewind/refetch and optional trie replay described
above cannot back past its entry position. In non-empty mode the same read
counts refer to the virtual-then-physical stream and preserve that mode until
the final rewind. No successful end-of-text probe increments a read count.

Crucially, `replaceMatch()` occurs **after** that final rewind. Mapping
dispatch and recursive draining occur afterward, when the caller has no
outstanding lookahead count to undo. A nested replacement may empty a buffer
mid-drain; subsequent matching then uses the empty-buffer argument at its
new physical entry position, not stale virtual counts. A nested helper can
also create a new top-level drain after that transition. The outer drain's
eventual `clear()` has no physical effect and no delayed rewind follows it.
Having no outstanding per-phase rewind does not imply `b = 0`: physical reads
retained by an earlier match can leave a positive shared beyond-buffer count
across dispatches. The epoch invariant explicitly permits this state.

Starting at `p`, these facts support induction over each finite prefix of
accounting transitions, without assuming the complete call returns or choosing
a maximum nesting depth:
non-empty epochs preserve their anchors, replacement does not decrease them,
and empty-buffer matching returns at or after its entry position. Balanced
lookbehind is the only permitted temporary excursion below an anchor. The
matching-phase facts depend on local read counts and finite input, not on
completion of the enclosing dispatch or drain. Thus they can also be used
in a termination induction. If the complete raw-element call returns, its
physical cursor is therefore
at or after `p`, **under the stated dispatch and entry premises**.

This cursor argument alone does not prove that every suffix yields a finite
successful execution. The conditional termination argument below adds separate
data-graph premises; neither argument has verified those premises for every
loaded consumer. Finite input alone is not a decreasing measure for the whole
algorithm.

#### Termination measure and mapping-graph premise (research draft)

This is a proposed sufficient condition for termination of the same upstream
78.1 forward path. It imports all the preceding entry, valid-dispatch and
successful-operation assumptions. It is not a proof of success despite
allocation failure or native stack exhaustion, an execution-time bound, or a
claim that the current root inventory establishes termination. The relevant
implementation is still
[`CollationIterator`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.cpp);
the finite-input and buffer arguments below do not apply to an uninspected
override or normalization iterator.

At dispatch and completed matching-phase boundaries after `p` is established,
define `N` as the sum of:

- source scalars still unread at the physical cursor; and
- virtual scalars in `oldBuffer` after its current reading position, or zero
  when that position is at or beyond the buffer end.

The scalar currently being dispatched is already consumed and is not counted
in `N`. Neither are already-read virtual prefixes or speculative `newBuffer`
copies. In particular, a positive beyond-buffer count does not add another
copy of already-consumed physical characters. Count scalars, not UTF-16 units.

For one matching phase, let `k` be the number of logical suffix scalars retained
after its final unmatched-lookahead rewind. Reads are from the unread virtual
buffer followed by physical text; the count discipline described above makes
`k >= 0`. A contiguous match leaves the remaining count at `N - k`. A
discontiguous replacement reinserts `s` skipped scalars, where `s` is the
scalar length of the prefix selected by `skipLengthAtMatch`. These are a subset
of the `k` retained scalars, not new input. The resulting remaining count is
`N - k + s <= N`.

The subset property follows from the matching loop, not merely the allocation
size of `newBuffer`: `setFirstSkipped` and `skip` record traversed mismatches;
`recordMatch` freezes only the skipped prefix preceding a successful match.
The final rewind removes reads after that match. If no discontiguous match was
recorded, `skipLengthAtMatch` stays zero, even if speculative marks were copied.
Replacement discards the consumed old-buffer prefix and retains only its
unread tail plus that selected skipped prefix. Already-drained marks before
this matching phase are not resurrected. When a non-empty skipped prefix is
inserted, at least one additional matched scalar is omitted from it, so
`s < k`. Moving skipped physical characters into virtual storage can increase
the buffer length, but not this combined count.

This accounting is at phase boundaries. Speculative reads followed by rewind,
or prefix lookbehind followed by restoration, need not monotonically decrease
`N` instruction by instruction. Each individual matching loop nevertheless
finishes for finite input: it reads new logical scalars without dispatch or
buffer replacement during the loop. Its contiguous rewind/refetch transfers
to the discontiguous helper or exits; it does not restart that loop indefinitely.
The bounded replay and prefix scan also have finite input to traverse.

One further premise is necessary for this proposed proof. Form a finite
**structural dispatch graph** with nodes keyed by the data object, CE32 and
exact scalar argument (or `U_SENTINEL`). Define roots independently of execution:
use mappings for every non-NUL Unicode scalar from the original iterator data,
with the same base resolution as `getDataCE32` and the drain loop. This is a
conservative superset of permitted leading and skipped scalars, not a proposed
CLI allow-list. It avoids defining roots as characters observed in terminating
runs. Narrower roots or scalar-class quotients require separate justification.
The initial supplementary lead-unit path before `p` must also be validated as
described above; these roots describe full-scalar dispatch after that step.
For each initial scalar, verify that the actual initial dispatch reaches its
corresponding graph root, or add the distinct resulting node as another root.
This includes lead-unit shortcuts that select base data directly and the
implicit-unassigned shortcut. Reject non-canonical fallback-tag encodings:
`nextCE()` tests the low byte, while the drain's base-resolution test compares
the complete value with `FALLBACK_CE32`. Agreement cannot be inferred merely
from the scalar being well-formed.

Starting with a finite, identified collection of data objects, compute static
successor closure using bounds-checked arrays and context tries. The scalar
domain plus sentinel is finite; decoded CE32 values and data objects are
finite. Use a visited set so constructing the graph does not itself require
runtime termination. Include both caller-scalar and sentinel interpretations
of contraction results where the forward paths can use them; enumerate
defaults and all trie values rather than following a sampled suffix.

Add edges
for every possible mapping selection without fetching a new scalar for a drain
iteration: prefix/default/context results, contraction results including the
first selected mapping appended by a top-level discontiguous match, non-numeric
digit indirection, valid base resolution, and each recursive Jamo child. Include
all permitted alternatives even when the matching phase may consume input.
Direct CE conversions and finite expansion arrays are terminal work, not
arbitrary recursive CE32 dispatch.

Every tag/scalar pair outside the permitted model fails verification; omission
from an edge list must never mean terminal work. Audit every loop-continuing
switch case as either an edge or an explicit rejection:

- `U0000_TAG` is rejected in this non-NUL/sentinel model, not treated as a leaf.
  A broader model would have to include its `ce32s[0]` successor and validate
  the scalar precondition.
- Lead-surrogate resolution, including its base switch, belongs to the
  separately validated initial lead-unit step. Any later lead-surrogate tag
  in the full-scalar graph is rejected.
- The implicit-to-`FFFD_CE32` branch requires a surrogate scalar and is excluded
  by the well-formed scalar-domain premise. Invalid implicit/sentinel dispatch
  is rejected; valid implicit dispatch is terminal.
- Builder dispatch and its fallback are rejected under the runtime-data
  premise. Base resolution where permitted is an explicit edge; unresolved
  fallback, reserved or unknown tags are verification failures.
- Encoded `NO_CE32` (`1`) is rejected in mapping data, including defaults and
  context-trie values. It is an internal signal for an already-appended
  discontiguous result, not an ordinary selected mapping. Treating such stored
  data as terminal would not establish valid CE emission even if it terminates.

The other selection edges listed above must likewise be complete, with tag
preconditions and expansion lengths/contents checked. Unknown data objects,
invalid pointers/indices, incomplete trie decoding or traversal-budget
exhaustion yield **unverified**, not a successful graph check.

Require the resulting closure to be acyclic. Its finite DAG
height supplies a rank that decreases on every structural dispatch edge. This
is a conservative sufficient premise: a cycle might still terminate by
consuming input, but this argument does not accept it without a separate
justification. A graph of CE32 integers alone is insufficient when the same
value has different base-data or scalar-dependent interpretations.

There are then two kinds of further work:

1. Structural selection/recursion has non-increasing `N` and strictly smaller
   graph rank. A Hangul frame has only finitely many child dispatches; each
   child must satisfy this rule, not merely the first one.
2. A drain iteration obtains its next scalar via `skipped->next()` before
   dispatching it. This reduces `N` by one; the mapping rank may restart at any
   reachable scalar mapping. The first dispatch of the selected contraction
   result is instead a structural edge, not a fictitious new scalar read.

The full inductive claim is: a dispatch entered after `p` with the safety
invariants and measure `(N, rank)` terminates, preserves those invariants at
its return boundary, and returns with `N_out <= N_in`, under the stated
successful-operation premises. This is a simultaneous termination and
postcondition claim, not an assumption that children have already finished.
Terminal conversions establish the base case. Finite matching phases supply
the conservation step before structural selection or draining. Each structural
child is lexicographically smaller; each newly fetched drain scalar lowers
`N` before its child is entered, even if rank increases. The induction
hypothesis supplies termination **and** the non-increase postcondition for
those children. It therefore justifies later Jamo siblings and drain
iterations. Finite structural children per frame and strict decrease on
loop-continuing selections finish the candidate induction on `(N, rank)`.
Nested replacement that empties a buffer changes the accounting mode but does
not increase `N`; creating a new skipped buffer uses the same conservation
equation. There is no need to choose a maximum nesting depth or enumerate
suffix strings for this argument.

The unresolved implementation obligation is to verify the finite, valid,
acyclic structural graph for the complete reachable data of each supported
consumer, and independently attest the source/data and entry-state premises.
The root reader's cycle/depth guard while classifying leading mappings is not
that verification: it does not cover every suffix mapping dispatched while
draining marks, and a traversal cap is not a rank proof. Accordingly this
proposal does not change `offsetsProven: false`, establish runtime acceptance,
or promise a practical worst-case time, heap or native-stack bound. Finite
recursive depth is not proof that the consumer's available stack suffices;
stack exhaustion need not be reported as a `UErrorCode`. These require separate
validation even if the mathematical termination premise can be discharged.

This exposes a distinct coverage requirement for an executable verifier:
classifying the possible **first emitted weight** of the leading scalar does
not classify all cursor-affecting mappings executed before that weight is
returned. The offline root reader below follows leading mapping alternatives
and Jamo children, but does not enumerate arbitrary suffix marks dispatched
while draining `SkippedState`, or prove their cursor behavior. Its existing
`offsetsProven: false` result must remain false. The conditional source argument
above still needs its dispatch premises checked against the complete reachable
data, as well as the termination-graph and consumer-identity obligations;
candidate membership alone cannot stand in for that check.

Once the full return-position property is established, it can be composed
with the positive-first-raw-half criterion: if the first raw half is retained,
the 78.1
[`UCollationPCE::nextProcessed`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/ucoleitr.cpp)
loop need not skip another element. It records `low` before `next()` and `high`
after it, repeating only for an ignorable processed result, so its offsets are
`low = d` and `high >= p > d`. This proves only the next-element premise.
Loaded-code/data identity, the entry state after the delimiter, processed-CE
settings, external break boundaries and other search premises remain separate.
No FCD normalization path, NLS backend, different ICU release, or uninspected
platform fork inherits this argument merely by reporting similar samples.

#### Single-root structural graph experiment

`scripts/inspect-icu-graph.py` implements a bounded, offline structural graph
walk using the existing 78.1 little-endian root decoder. Unlike the earlier
leading-weight inventory, it starts from every non-NUL Unicode scalar and
tracks exact scalar/sentinel arguments. There is only one data object in this
implementation: any required base object or tailoring is unverified, not
implicitly replaced by the supplied root. The shared decoder's `initial()`
establishes initial lead-unit correspondence; the graph walk checks all selected
Jamo children, default and trie successors,
expansion spans, forbidden internal sentinels and scalar-sensitive dispatch.
Successful postorder traversal assigns terminal nodes rank zero and each
structural parent one plus its greatest child rank. The fast Hangul branch
does direct conversions and therefore has no recursive graph edge.

Contraction trie values are checked with both the caller argument and sentinel.
The default is checked only with the caller argument (which may already be
sentinel). This differs deliberately from the more conservative leading-weight
reader. In the inspected `nextCE32FromDiscontiguousContraction`, sentinel
dispatch of the selected result happens only when a top-level match has a
non-empty skipped prefix. `skipLengthAtMatch` starts at zero; a non-empty
selected prefix can be recorded only when a trie value replaces `ce32` at a
successful match. A no-match default cannot reach that sentinel dispatch.
Both argument variants of every trie value remain an overapproximation, not a
claim that every branch is reachable for every header or suffix.

An initial prototype also applied sentinel to the default and stopped at
U+FDD1 on an implicit/sentinel combination. This was an extra verifier branch,
not evidence of a consumer failure. Applying the source-based default rule
above allowed the full root walk to finish without removing any scalar root.

On 2026-10-04 the final walk over the previously acquired local 78.1 payload
(SHA-256 `22e8a8ae4b3291ead304290ca73c5facc4e8c330e21ebf5b2437dbe8b2fd93e0`)
completed 1,112,063 scalar roots, 1,115,181 distinct `(CE32, argument)` nodes,
3,150 examined successor edges and 77 context tries. Maximum completed rank
was 1 and no cycle was found. These counts describe that exact decoded graph,
not the amount of work done by arbitrary ICU searches. The payload is the
separately opened local resource described below, not a new native acquisition
or evidence of the cached collator's actual fallback-object identity.

The tool stops at the first unsupported, invalid, cyclic or over-budget path.
It reports that root, the reason and partial counts; incomplete reports never
claim an acyclic complete graph. `structuralGraphAcyclic: true` means only that
the enumerated graph of the supplied payload passed this model. Input profile,
consumer identity, offsets, consumer termination and acceptance-table flags
remain false. It is not a complete ICU binary-format validator, a supported
consumer matrix gate, an acceptance generator or a runtime performance test.
See the [verification procedure](../test-plan.md#offline-root-mapping-graph-research)
for limits and exit-status semantics.

#### Delimiter mapping and conditional entry-state step

The full graph report also records `delimiterMappingEvidence`, only after all
scalar roots complete. It checks U+003A's initial mapping and every stored key
in the context tries visited by that walk, not merely the leading-weight
candidate inventory. Prefix keys are stored in reverse order, but whether a
key contains the colon UTF-16 unit does not depend on that order. Counts are
per entry in each distinct cached context trie, not per scalar, dispatch
argument, reconstructed context string or native `USet` member. Defaults have
no key and are not counted. Context values are mappings, not text.

On 2026-10-04, the same local payload identified above had colon CE32
`0x07360505`. From the simple CE32 representation and the source conversion,
its first raw half equals that value and its second half is zero by
construction; these are derived values, not independent native measurements.
None of 1,151 entries across the 77 visited context tries had a key containing
colon. The exact difference from the earlier 1,153 reconstructed strings is
**unreconciled**. The enumerations use different units (stored-trie entries
versus strings including the owning scalar and prefix/suffix position), but
that alone does not explain the two-item difference. The counts must not be
treated as mutually corroborating coverage. The new observation was made by
the offline decoder, not a fresh native cross-check.

This supplies evidence for a small **conditional** step in the entry-state
argument. Assume the normal, non-FCD UTF-16 iterator is immediately before the
first intended colon, moving forward, with no pending `otherHalf_`, no unread
buffered CEs, no active skipped-mark replay and `numCpFwd < 0`. Assume its
effective colon mapping is the observed simple mapping, no error occurs and
the guarded processed-CE settings (including non-ignorable alternate handling)
retain that raw element. Under the inspected
78.1 [`nextCE`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationiterator.h#L117-L134)
simple branch, one code unit is consumed and one CE is returned; the buffer
index reaches its length without entering contextual dispatch. The
[`next`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/coleitr.cpp#L103-L138)
conversion has no second half to save. Repeating for the second colon leaves
the physical position at `d`, with no unread delimiter CE or continuation.
The following call can therefore begin at `d` under those entry assumptions.

The report deliberately keeps `delimiterEntryStateProven: false`. Absence
from stored context keys is not by itself proof that an earlier mapping cannot
consume or skip a colon: that requires the relevant canonical-combining/FCD
properties and the contiguous/discontiguous matching rules, as well as the
whole-header entry argument. It also does not establish the search cursor's
actual state after resets or lookahead, processed-weight uniqueness of the
intended delimiter, external break acceptance, effective tailoring/root
identity or the code loaded by the consumer. Non-simple colon mappings are
reported without inferring a raw-half result, even when some could satisfy a
more general rule. The static observations neither prove nor refute consumer
safety; they close no adoption gate on their own.

### Mapping-data acquisition feasibility (local research)

A 2026-10-03 local macOS 26.6.2 (25G83) ARM64 experiment used the Runner-package CoreLib
8.0.30 and the loaded system ICU 78.1. It obtained the cached option-zero
invariant/en-US collators after priming `CompareInfo.IndexOf`, checked their
identity against the cached search collators, and checked the eight observed
collator attributes. This was a separate feasibility probe, not a new package
matrix gate or a live Worker observation.
The macOS product version/build were manually recorded from `sw_vers`; the
emitted evidence records the Darwin kernel description, not those two fields.
The probe and result files are retained only in temporary local storage, not
archived with this repository. The numbers below are therefore unarchived local
observations, not durable CI evidence or prerequisites satisfied for adoption.
Module path/version and successful cached-object identity checks are not a
native code identity attestation; opening the library with `RTLD_NOLOAD` alone
does not establish which image the runtime globalization shim uses.

[`ucol_cloneBinary`](https://unicode-org.github.io/icu-docs/apidoc/dev/icu4c/ucol_8h.html)
returned the same 32-byte image for both cached collators and a separately
opened root collator: a 24-byte header and two indexes containing only options,
with SHA-256 `4aa0f2a38d629773c2befa2b9bf6415303e2c46f441641309906325e1c14072b`.
This is not a complete mapping export. In the inspected 78.1
[`CollationDataWriter`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationdatawriter.cpp),
`cloneBinary` uses `writeTailoring`, and its `data.base == nullptr` branch omits
mappings.
A small or identical clone image therefore cannot establish complete or
identical consumer mappings.

The experiment separately called `udata_open` with package `icudt78l-coll`,
type `icu` and name `ucadata`, following the resource naming in
[`CollationRoot::load`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/i18n/collationroot.cpp).
It checked the data-info header (little-endian `UCol`, format 5, 16-bit UChar)
and used the version-specific **internal** `udata_getLength` export to bound
the copy from `udata_getMemory`. In the inspected upstream
[`udatamem.cpp`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/udatamem.cpp),
the internal function reports payload length excluding the header, or a
negative value if unavailable; the probe rejects
unknown lengths and lengths outside its 16 MiB cap before copying. This is
not a claim that the internal export is portable or supported on every OS.
Applying these length semantics and the writer branch above to Apple's binary
is an upstream-source inference, not vendor-source attestation. The size cap
alone does not prove that a native pointer spans that many readable bytes.
The copied payload was 597,136 bytes, including trailing storage beyond the
597,124-byte indexed total, with SHA-256
`22e8a8ae4b3291ead304290ca73c5facc4e8c330e21ebf5b2437dbe8b2fd93e0`.
That hash excludes the data header and includes 12 trailing storage bytes;
it is not a hash of a standalone `ucadata.icu` file or just the indexed data.
The indexed 597,124 bytes alone hash to
`a7666987ef372e7574ba4d22b7e7d40c4fea133937d206051a9904f836b42eb0`.
The revised probe also rejects trailing storage of 16 bytes or more, following
the upstream length comment's bound; it does not interpret the trailing bytes.

An offline reader of the copied root UTrie2 was checked against the loaded
ICU's `utrie2_openFromSerialized`/`utrie2_get32` on the same copied bytes for
all 1,112,063 non-NUL Unicode scalars, with no lookup mismatches. The reader
used the release-78.1
[`utrie2.h`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/utrie2.h)
and [`serialized layout`](https://github.com/unicode-org/icu/blob/release-78.1/icu4c/source/common/utrie2_impl.h).
For the 142,081 candidates, per-code-point CE32 mapping types were:

| Mapping type | Candidate scalars |
| --- | ---: |
| Simple | 6,977 |
| Long primary / long secondary | 66,380 / 18 |
| Latin expansion / expansion32 / expansion | 384 / 1,772 / 737 |
| Digit indirection | 660 |
| Hangul | 11,172 |
| Algorithmic offset | 53,947 |
| Prefix / contraction | 2 / 32 |

These counts classify code-point lookups, not necessarily the first entries
read by a UTF-16 iterator, transitive mapping branches or safe characters.
In the inspected iterator, a lead-surrogate code-unit entry precedes and may
override the supplementary code-point lookup; those summaries were not checked by this
inventory and must be covered separately. Expansions, digit and Hangul
indirections still need processing, and a mapping's first 32-bit element must
be distinguished from a later retained element. The five previously observed
empty-equivalent candidates had simple zero CE32 entries in this payload;
that observation is not the definition of an exclusion list.

This establishes a feasible local input path for a verifier, not completeness
of a consumer proof. Native agreement checks the copied trie's decoding; it
does not prove that the separately opened resource is the cached collator's
actual fallback data object. The next verifier work is therefore divided into:

1. **Input identity and completeness:** retain native module/data/settings
   identities and hashes, obtain both effective tailoring and root data, and
   justify their connection to the actual consumer. Missing or unsupported
   data acquisition yields unverified, never an empty successful traversal.
   Include normalization/FCD property data, load-time or compiled-in
   unsafe-backward sets, and library code for algorithmic mappings; the
   serialized collation payload alone is not the complete input set.
2. **Finite mapping closure:** traverse each candidate's reachable mapping
   graph, including lead-surrogate code-unit summaries, defaults, context tries
   and indirections; check the first
   emitted 32-bit element at every reachable branch. Bounds, unknown tags,
   unresolved references and incomplete enumeration yield unverified. Do not
   infer closure from the small number of code-point context entries.
3. **Iterator argument:** separately justify source-offset advancement and
   restoration for arbitrary suffixes in the supported iterator/settings
   paths, then combine with the header and break premises above. Finite graph
   coverage or native sample agreement alone does not discharge this step.

The producer would not perform this data traversal for each invocation. Any
eventual shipped lookup remains subject to the separate adoption decision
above. No table entries are authorized by this feasibility experiment.

The subsequent [offline root-graph reader](../test-plan.md#offline-root-mapping-graph-research)
completed on this payload for all 142,081 candidates, visiting 33 distinct
context tries with 888 entries. It reported 142,076 candidates with nonzero
first raw halves for all enumerated alternatives, five with a zero first half
possible, and no unresolved mappings within its root-only model. These are
data-graph classifications, not accepted-character counts. The five emerge
from the positive predicate; their identities are not hard-coded exclusions.

A separate local cross-check reconstructed all root prefix/contraction strings
from the decoded context tries across non-NUL scalars and compared them with a
separately opened root collator's `ucol_getContractionsAndExpansions` output:
both sets contained 1,153 strings, with no differences. For every candidate,
the first raw element of its isolated scalar from `ucol_next` was consistent
with the reader's zero/nonzero alternatives. The 142,081 isolated-scalar checks
do not exercise every context branch. String-set equality tests context-key
enumeration, not every stored branch value or the default mappings. These
cross-check artifacts are also temporary local observations; they do not close
the consumer-identity or arbitrary-suffix offset obligations above.

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
