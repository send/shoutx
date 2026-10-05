# Reference search-cache reset paths

Status: bounded R2/R4 source evidence, inspected 2026-10-05. This does not
promote any row to Go or prove arbitrary-suffix safety. The
[claim inventory](unicode-feasibility.md#claim-inventory) owns those obligations.
This note follows the native cache below the
[managed culture/name cache](reference-culture-cache.md).

## Source scope

The .NET pin is
[`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_collation.c),
specifically `pal_collation.c`. Upstream ICU generation references are:

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
