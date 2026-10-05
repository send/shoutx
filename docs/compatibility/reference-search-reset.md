# Reference search-cache reset paths

Status: bounded R2/R4 source evidence, inspected 2026-10-05. This does not
promote any row to Go or prove arbitrary-suffix safety. The
[claim inventory](unicode-feasibility.md#claim-inventory) owns those obligations.
This note follows the native cache below the
[managed culture/name cache](reference-culture-cache.md).

## Source scope

The .NET pin is
[`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_collation.c),
covering `pal_collation.c` and the managed coordinate path's `String.cs`,
`String.Searching.cs`, `CompareInfo.cs` and `CompareInfo.Icu.cs`. The
[culture-source inventory](evidence/reference-culture-source-hashes.txt) owns
the two CompareInfo file hashes; the manifest below adds the two String files.
Runner's caller is `src/Runner.Common/ActionCommand.cs` at
[`397b032cbf865e9c3ddfab89d533ec19325e1273`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/ActionCommand.cs),
also hashed below. Upstream ICU generation references are:

- [70.1](https://github.com/unicode-org/icu/tree/a56dde820dc35665a66f2e9ee8ba58e75049b668/icu4c/source)
- [72.1](https://github.com/unicode-org/icu/tree/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source)
- [74.2](https://github.com/unicode-org/icu/tree/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source)
- [76.1](https://github.com/unicode-org/icu/tree/8eca245c7484ac6cc179e3e5f7c1ea7680810f39/icu4c/source)

The [source hash manifest](evidence/reference-search-reset-source-hashes.txt)
identifies inspected files, not compiled vendor behavior. Microsoft/Apple
patches, build options and effective rule/data selection remain separate
binding obligations. No acquired binary was executed for this inspection.

## A pool can contain a reverse-search iterator

`GetSearchIteratorUsingCollator` borrows from a SortHandle's options-indexed
linked list using the `USED_STRING_SEARCH` marker and pointer CAS. New handles
use `usearch_openFromCollator` with the customized break iterator, including
the existing null-break fallback. Reused handles receive `usearch_setText`
then `usearch_setPattern`; setter failure restores the handle and returns a
failure result. `RestoreSearchHandle` can restore to any marked slot in that
options list, not necessarily the original node.

`IndexOf` and `ComplexStartsWith` call `usearch_first`; `LastIndexOf` and
`ComplexEndsWith` call `usearch_last`. All return borrowed handles to the pool.
Thus a subsequent forward search cannot assume its previous borrower searched
forward. `SimpleAffix` instead constructs separate collation-element iterators.
These call sites do not set search attributes or replace the collator. This
is a source inventory, not a proof of every concurrency/lifetime condition.

## Successful forward reinitialization

The following are individual state facts, not a claim that a cached object is
wholly identical to a fresh allocation. In `i18n/usearch.cpp`:

1. `usearch_setText` binds the new text/length, calls `ucol_setText`, clears the
   prior match index/length, sets reset state, and updates both external and
   already-created internal break iterators. `usearch_setPattern` binds the
   new pattern and initializes its tables. `initializePattern` recomputes
   prefix/suffix FCD information, invalidates the processed-CE table and
   rebuilds the ordinary CE table. This is **not** `usearch_reset`: search
   attributes are not all reset by these setters.
2. `usearch_first` sets forward direction, sets offset zero and calls `next`.
   `usearch_search` lazily rebuilds the pattern's processed-CE table, sets the
   text offset and constructs a local `CEIBuffer`, checking initialization
   errors before searching. Its first access is `ceb.get(0)`.
3. That buffer starts with `firstIx == limitIx == 0` and initializes the text
   processed iterator. Its first access therefore cannot read an old ring
   entry: `get` calls `nextProcessed` with a fresh success status.

The important distinction in `i18n/ucoleitr.cpp` is that
`UCollationPCE::init` rebinds the iterator and collation settings and clears
`isShifted`, but **does not clear its reverse PCE buffer**. `nextProcessed`
clears that buffer before obtaining the first CE. By contrast,
`previousProcessed` can consume an existing buffer. The forward call order
above, not `init` alone, excludes those retained reverse entries from the
first forward fetch. This does not establish correctness of arbitrary
reverse-search reuse.

`ucol_setText` delegates to `CollationElementIterator::setText` in
`i18n/coleitr.cpp`. On successful allocation it replaces the underlying
UTF-16/FCD iterator and clears `otherHalf_` and direction. `setOffset(0)`
skips the positive-offset unsafe-character backup, calls `resetToOffset(0)`
and clears `otherHalf_` again. Allocation failures and the full underlying
iterator semantics are not proved away by these success-path observations.

## Fresh forward entry and the FCD ASCII fast path

The successful `CollationElementIterator::setText` path above constructs a new
iterator, not a copy of the previous one. In `utf16collationiterator.h`, both
the UTF-16 constructor and the FCD subclass reach
`CollationIterator(data, numeric)`. That base constructor initializes
`cesIndex` to zero, `skipped` to null and `numCpFwd` to -1; the `CEBuffer`
constructor initializes its length to zero. The FCD constructor additionally
sets `checkDir` to 1. Thus the old iterator's backward-forward limit and
skipped replay are not inherited on this successful replacement path.

This distinction matters: `CollationIterator::reset` alone clears the CE
buffer/index and skipped replay, but does **not** assign `numCpFwd`. The
zero-offset reset does not need to repair that field after fresh construction.
The UTF-16 reset positions the cursor at the start; the FCD reset also restores
the raw range and `checkDir == 1`. These facts are not a claim that an arbitrary
reset repairs every possible incoming state, or that allocation/error paths
can be ignored.

For the FCD path, the fixed
[`CollationFCD::hasTccc`](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/i18n/collationfcd.h#L71-L81)
first tests `c >= 0xc0`. Every printable ASCII unit fails that test, without
accessing its index/bit tables. In
[`FCDUTF16CollationIterator::handleNextCE32`](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/i18n/utf16collationiterator.cpp#L210-L241),
forward-checking entry reads one unit; both the next-unit test and
`nextSegment` are inside the `hasTccc` branch. For ASCII that branch is not
entered, the trie lookup is for that unit, and `checkDir` remains positive.
This argument depends on the source guard, not on interpreting the separate
normalization-data threshold as proof about this fast-path table.

Consequently, under the other mapping, numeric-off, bounded-text and successful
operation premises of the
[printable-ASCII header subcase](unicode-root-generation-evidence.md#printable-ascii-header-subcase),
its one-unit/one-CE induction also applies to a freshly forward-initialized FCD
iterator. Simple mappings and non-numeric digit children do not invoke another
text movement path. This includes processing the intended ASCII delimiter,
but not the search's subsequent fetch from the arbitrary Unicode suffix.
Search boundary acceptance, suffix processing and effective code/data binding
remain separate obligations. No language restriction or product acceptance
change follows from this header-only result.

The constructors, successful `setText`, both `resetToOffset` bodies and FCD
`handleNextCE32` were compared across the four pinned generations, with only
`UChar`/`char16_t` and null/boolean spelling normalized. The UTF-16 headers are
byte-identical in 70/72 and in 74/76; their cross-pair differences are type and
null spellings. The FCD guard headers differ only in a deleted private
constructor declaration and explicit integer-cast spellings. This remains
upstream source evidence, not vendor compiled-code attestation.

## Header offsets and caller coordinates

Under the preceding fresh-entry and printable-ASCII mapping premises, the
one-unit/one-CE result also gives a bounded offset result. For header unit `j`
in the searched text, `CollationElementIterator::getOffset` uses the underlying
iterator's offset, not its reverse-offset buffer: direction is zero/positive
at entry and becomes 2 on the first forward call. The non-FCD offset is
`pos - start`; the FCD forward-checking offset is `pos - rawStart`. Before and
after the unit's CE these are therefore `j` and `j + 1`.

`UCollationPCE::nextProcessed` records these offsets immediately before and
after `next`. The checked header CE's nonzero primary survives the assumed
non-shifted processing, so this call does not skip it as ignorable and move
on to later text. `CEIBuffer::get` stores the returned low/high pair unchanged.
Thus each such header unit has a nonempty, single-unit interval in search
coordinates, including each intended colon. The getter and processed-fetch
bodies agree across the four source pins after type/null/boolean spelling
changes; 76 additionally uses equivalent explicit integer-cast spellings.
This does not prove the search's boundary checks or its next suffix fetch.

Those coordinates are relative to the **searched slice**, not the original
Runner message. At the fixed .NET pin,
[`String.IndexOf`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/String.Searching.cs#L238-L266)
routes the start-index overload through CurrentCulture comparison.
[`CompareInfo.IndexOf`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Globalization/CompareInfo.cs#L906-L937)
obtains a span starting at that index and adds the index back only to a
nonnegative result. `String.TryGetSpan` bounds-checks and constructs that
span from `_firstChar + startIndex` with the requested count. The ICU branch
receives that span; even the ASCII helper's native fallback passes the full
span pointer/length, not its current scan cursor. Native `IndexOf` returns
`usearch_first`'s result without another coordinate translation.

Runner's V2 parser searches for `::` starting at 2 in its `TrimStart` result.
If ICU successfully returns the intended delimiter start `j` in the slice,
the managed result is `j + 2`, and Runner starts data at `j + 4` in that
trimmed message. This is conditional coordinate correspondence, not proof
that the intended match succeeds, that trimming preserves arbitrary input,
or that every call takes the native path. The
[existing ASCII fast-path argument](github-actions-workflow-command-parser.md#ascii-boundary-allowlist-derivation)
and remaining suffix/search/effective-binding obligations still apply.

## Break-iterator state

With break iteration compiled in, `getBreakIterator` selects the supplied
external iterator, then an existing internal iterator, otherwise lazily opens
a character iterator for the collator's valid locale and current text.
`isBreakBoundary` delegates to `ubrk_isBoundary`. The null-custom-iterator
route must not be silently equated with the customized rules route.

In `common/ubrk.cpp`, `ubrk_setText` wraps the new UTF-16 input in a UText and
calls the virtual setter. For the inspected RuleBasedBreakIterator setter
in `common/rbbi.cpp`, successful entry resets its break and dictionary
caches, clones the new UText, resets the dummy CharacterIterator and calls
`first`. In `common/rbbi_cache.cpp` and its header:

- Dictionary-cache reset clears the range, position, rule-status indexes and
  stored boundaries.
- Break-cache reset defaults to position/status zero, resets ring indexes,
  and initializes its first boundary/status to zero. It does not erase every
  allocated array element or every auxiliary buffer.
- `first` can seek that zero boundary; `current` then sets the owning
  iterator's position/status and clears `fDone`.

These facts describe the RuleBasedBreakIterator path, not every possible
virtual implementation or rule/data provider. They do not prove that every
retained field is irrelevant to every future call. In particular, auxiliary
side buffers and retained language engines require their own use-path
arguments if a whole-object cache-equivalence claim relies on them.

## Generation comparison and remaining obligations

Selected function bodies were compared across all four source pins, ignoring
only `NULL`/`TRUE`/`FALSE` spelling changes before examining remaining diffs.
`initTextProcessedIter`, `usearch_first/next`, `CEIBuffer::get`,
`getBreakIterator`, processed-iterator initialization and `processCE` retain
the inspected logic. Differences in the other reset functions above include
`UChar` to `char16_t`, explicit casts, null-pointer spelling and removal of
`void` from an empty parameter list. The 74/76 RuleBasedBreakIterator setter
uses `fSCharIter.setText(u"", 0)` for the dummy iterator instead of an empty
UnicodeString. This comparison is not whole-file equivalence or a substitute
for binding a vendor binary to the relevant implementation.

Still open are the effective collator/break data and settings, reference
binary/source correspondence, full retained-state/ownership and error-path
arguments, and composition with arbitrary accepted suffixes. Failure returns
must not be treated as successful command recognition. Nor may these reference
correctness obligations be moved into live-deployment applicability assumptions.
The product acceptance contract remains unchanged.
