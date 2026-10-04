# ICU context matching coverage

Status: research argument for one R3 prerequisite; not native binding, a
general Unicode acceptance rule, or a Go recommendation.

The [root-generation evidence](unicode-root-generation-evidence.md) owns the
five fixed source versions, exact comparison transformations and hashes, and
the three recovered root-payload observations. This note relates the
`ContextTrie` enumerator in `scripts/inspect-icu-mappings.py` to the native
matcher. It does not repeat that input inventory or promote any reader's
`inputProfileVerified` flag.

## Claim and premises

For one fixed context trie whose bounded `ContextTrie.entries(start)` call
finishes successfully, consider the native UCharsTrie matching operations on
the **same units and starting offset**. Under the inspected source's 16-bit
unit / 32-bit value interpretation, every key/value returned by matching from
the root occurs in the enumerated set. Equality of the two accepted languages
is unnecessary: the enumeration may conservatively contain keys that native
branch selection cannot reach.

This claim is about stored keys and returned 32-bit value patterns, not the
sequence of input positions consumed by collation. Its premises include:

- Complete successful enumeration, not a truncated stream of yielded entries.
  `entries` first materializes the traversal and checks nonempty/unique keys.
  A bound, malformed span, or duplicate failure is unverified, not a smaller
  passing inventory.
- A context section within the root reader's 16 MiB payload bound. All
  referenced unit positions and traversed branches must pass the reader's
  bounds. No native pointer/ABI or arbitrary malformed-file safety is claimed.
- The native matcher starts at that trie root or a state actually reached
  from it. Arbitrary caller-supplied state objects are outside this lemma.
- `getValue()` is called only after a has-value result, as required by its
  API. Reading a value from a partial linear match, a no-value node or a
  stopped state is not covered. The prefix, contiguous-contraction and
  discontiguous-contraction value assignments were each inspected for this
  guard.
- The selected native code and input data must separately be bound to the
  reference configuration. Textual similarity to upstream does not establish
  that binding.

## Primary source and decoding correspondence

At the fixed 78.1 commit, inspect
[unit matching and branch selection](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/ucharstrie.cpp#L31-L175),
[value access contract](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/unicode/ucharstrie.h#L248-L265),
[value result encoding](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/unicode/ucharstrie.h#L495-L498),
[value/delta helpers](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/unicode/ucharstrie.h#L418-L492),
[node constants](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/unicode/ucharstrie.h#L530-L602),
and [native enumeration](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/ucharstrieiterator.cpp#L106-L237).
Whole-file cross-generation comparison covers both `.cpp` files and the
header, with only the transformations disclosed by the root-generation note.
The following correspondence rests on manual source inspection, not hashes
alone.

| Node/action | Matcher | Research enumeration |
| --- | --- | --- |
| Final value | A lead with bit 15 set supplies a value and no further matching units | Emit the current key and decode the same low-15-bit value lead; stop that path |
| Intermediate value | Decode the node value; skip its extra units before matching the low-six-bit node type | Emit the current key, advance by the same value width, then traverse that node type |
| Linear match | Require the next `node - 0x30 + 1` units, possibly across repeated `next` calls | Append exactly those stored units, then enumerate the child |
| Short branch | Search up to five unit-labelled alternatives; nonfinal values are relative jumps; the last alternative falls through | Visit all alternatives, using the same extra-unit width and post-value jump base; visit the last child after its label |
| Long branch | Compare one pivot, select the delta-jump half or the skip-delta half, with sizes `n/2` and `n-n/2` | Ignore the pivot comparison but visit both halves with those sizes and bases |
| Supplementary code point | `firstForCodePoint`/`nextForCodePoint` feed lead then trail units; a returned value belongs to the result after the trail | Keys are unit sequences, so these are two consecutive enumerated units. A lead-only stored key is an extra conservative case, not a value returned for that supplementary code point. |

The compact-value widths agree: one unit below lead `0x4000`, two below
`0x7fff`, otherwise three after clearing the final bit. Intermediate values
use thresholds `0x4040` and `0x7fc0`; their low six bits belong to the next
node type. Delta widths use `0xfc00` and `0xffff`. The enumerator's explicit
length-one branch rejection means this argument is for completed inventories,
not a generic assertion about every possible serialized branch encoding.

### Coverage argument

Unfold the successful enumeration into its finite traversal tree; shared
serialized positions may appear more than once with different key prefixes.
At the root the native and enumerator positions coincide. For each successful
native transition, a corresponding enumerated path exists:

1. A linear match adds the same units and reaches the same child. Partial
   native linear states have no value until the full segment is consumed.
2. A short branch's selected label is among the labels visited, and both
   decoders use the same final-value or child target. A long branch picks one
   of the two subtrees that enumeration visits. Repeating this choice reduces
   to a short branch.
3. A final or intermediate native value therefore occurs at an enumerated
   path with that key. After an intermediate value, both resume at the same
   following node. A mismatch returns no value and cannot add a new case.

Induction over this finite tree covers any length of matched stored key, not
only a finite sample of input strings. It does not require branch labels or
pivots to make every enumerated path natively reachable. Incorrect ordering
can make enumeration an overapproximation; it is not silently treated as an
exact language equality. This is useful for a positive predicate quantified
over **all** enumerated values, not for a predicate that assumes each listed
key must match.

### Integer interpretation

For values, the Python reader retains the 32-bit pattern. Native `getValue`
returns `int32_t`; the collation call sites cast it to `uint32_t`, preserving
the pattern modulo 2^32, including values with bit 31 set. This uses the
inspected ICU value-decoding interpretation, not proof of an arbitrary
compiler's behavior or ABI.

Jump values are different from returned values. A completed model traversal
requires each post-value/post-delta position plus the decoded nonnegative
offset to be inside the bounded context section. With at most 8 Mi units,
neither a traversed offset nor its target can reach 2^31. Thus a successfully
traversed jump cannot exploit a three-unit offset whose native signed value
would be negative. Returning a value with its high bit set remains allowed;
using such a value as a jump does not satisfy the traversal premise.

## Connection to collation and state restoration

[Prefix matching and ordinary contractions](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/i18n/collationiterator.cpp#L449-L553)
use a context default before matching and replace it only on
`USTRINGTRIE_HAS_VALUE`. The graph inventory includes that two-unit default
as well as every enumerated value. The prefix function reads its own default;
the [contraction dispatch](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/i18n/collationiterator.cpp#L305-L346)
reads and passes the contraction default into the matching function.
Prefix traversal reverses the order of
input code points, but does not reverse the unit encoding within a
supplementary code point; the coverage claim is about the units actually
supplied to the trie, not their positions in the original input.

[Discontiguous matching](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/i18n/collationiterator.cpp#L558-L691)
can reset to the root, replay input, or restore a saved matching state.
[State save/restore](https://github.com/unicode-org/icu/blob/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source/common/unicode/ucharstrie.h#L133-L182)
records the base, position and remaining linear length. A same-base restore
returns a previously reached state; a different-base restore is ignored.
Starting from reachable states, these operations do not invent a new stored
trie value. This limited value-coverage observation does not establish correct
input backtracking or all nested shared-state/buffer interactions.

In particular, discontiguous matching may skip units in the original input.
Absence of colon in stored keys does **not** by itself prove that a colon or
later text cannot be consumed, skipped, normalized or revisited. FCD data,
entry state, offset/end checks, termination and iterator-buffer composition
remain separate R3/R4 obligations. Error sentinels and already-buffered CEs
are not newly returned stored context values and need their own treatment in
the whole-iterator argument.

## Verification and remaining scope

The existing synthetic context tests cover final/intermediate widths, branches
and jumps, linear matches, malformed/truncated inputs, duplicate keys and
resource-bound failures. They are regressions for decoding, not a universal
proof or native execution. The retained completed root-graph walks provide
bounded data observations for the recorded payloads; they do not identify
which data a reference consumer selects.

Additional fixtures retain an intermediate value after a supplementary
UTF-16 pair and distinguish a high-bit returned value from the same bit
pattern used as a rejected out-of-bounds branch jump/delta. They exercise
the two distinctions in this argument without treating synthetic data as
evidence of a native build's identity.
They also cover a supplementary pair crossing a branch edge and two-/three-unit
intermediate values (including a high-bit value) followed by a branch.

This note supplies a source-level coverage argument conditional on the stated
premises. Completing reference native/data binding and the surrounding
collation/search composition is still required before using it in a Go
recommendation. R1–R6 remain unproved overall, and product acceptance is
unchanged.
