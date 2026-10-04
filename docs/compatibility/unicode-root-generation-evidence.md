# ICU root-generation evidence

Status: research in progress; not product acceptance or a Go recommendation.

This records observations toward R3/R4 in the [claim inventory](unicode-feasibility.md#claim-inventory).
The [input inventory](unicode-reference-inputs.md) owns acquisition and file
identities. The [parser note](github-actions-workflow-command-parser.md#single-root-structural-graph-experiment)
owns the existing graph model and conditional argument. This note records
cross-generation evidence, not a new effective-consumer assumption.

## Source comparison scope

The inspected upstream commits are:

| Release | Commit |
| --- | --- |
| 70.1 | `a56dde820dc35665a66f2e9ee8ba58e75049b668` |
| 72.1 | `ff3514f257ea10afe7e710e9f946f68d256704b1` |
| 74.2 | `2d029329c82c7792b985024b2bdab5fc7278fbc8` |
| 76.1 | `8eca245c7484ac6cc179e3e5f7c1ea7680810f39` |
| 78.1 | `049e0d6a420629ac7db77256987d083a563287b5` |

For example, the [78.1 source tree](https://github.com/unicode-org/icu/tree/049e0d6a420629ac7db77256987d083a563287b5/icu4c/source)
contains the model's `i18n/collationiterator.cpp`, `coleitr.cpp`,
`utf16collationiterator.cpp`, `collationsettings.h`, and
`common/unicode/ucharstrie.h`. The same paths were inspected at each commit.
Comparisons cover complete files, not selected successful test inputs.

For those five files, raw 70.1-versus-78.1 diffs contain only the explicitly
inspected null/bool spellings, `UChar` to `char16_t`, numeric and enum casts to
`static_cast`, and the unavailable assignment operator changed to `= delete`.
One exact `UStringTrieResult` cast replacement also changes spacing around
the subtraction and shift operators; there is no general whitespace removal.
Applying exactly those spelling substitutions also gives identical text for
the intermediate 72.1, 74.2 and 76.1 files. This is not a generic assertion
that arbitrary casts or arbitrary source transformations preserve behavior.
The source comparison must not substitute for vendor implementation binding,
data validation, dependent helpers or build settings. In particular, the
`UChar` substitution is textual evidence, not proof of the vendor's
`UCHAR_TYPE` build definition or binary ABI.

`collation.h` is deliberately different: 72.1 and later add
`CONTRACT_HAS_STARTER = 0x800`, labelled for ICU4X. None of the compared files
tests this flag; this claim does not cover unexamined dependent helpers.
The graph model's tag-8/9 index extraction ignores bits 8–12, including this
bit; completing that walk is not native validation of the flag's meaning.
Index extraction, mapping tags and the tested
contraction flags remain separate from it. Do not erase a new flag merely to
obtain an equality result. The explicit substitutions for this header also
include a `char` cast and its private constructor declaration becoming
`= delete`; the flag and its comment remain different after substitution.

### Reproduce the source comparison

Acquire the six files named by `PAIRS` in
`scripts/compare-icu-generation-sources.py` from each fixed commit above.
All are under `icu4c/source/i18n/` except `ucharstrie.h`, which is under
`icu4c/source/common/unicode/`. Save them in a local directory as
`FILENAME-70-1`, `FILENAME-72-1`, `FILENAME-74-2`, `FILENAME-76-1`, and
`FILENAME-78.1`. For example, the exact source URL pattern is
`https://raw.githubusercontent.com/unicode-org/icu/COMMIT/icu4c/source/i18n/coleitr.cpp`.
Do not substitute a moving branch. Then run:

```sh
python3 -B scripts/compare-icu-generation-sources.py SOURCE_DIRECTORY
```

The script prints each raw and normalized SHA-256 and per-file equality, not
the source contents. It bounds each file to 1 MiB and decodes UTF-8 without
newline normalization. Its substitution list is explicit; word substitutions
also affect comments, but do not change `UChar32` or `NULLORDER` substrings.
Literal cast replacements are exact substrings, not a C++ parser: for example,
`(uint32_t)ce` also matches the prefix of `(uint32_t)ce32`. Inspect raw diffs;
normalized output alone is not an equivalence proof. The filename suffixes
above intentionally follow the differing upstream release-tag spellings.
Five files should report equality; `collation.h` should report inequality.
Exit 0 means the comparison ran, **not** that every file is identical or the
inputs have authenticated provenance. A failed read may leave earlier
per-file output; nonzero exit is an incomplete comparison, not a passing gate.
The investigator must inspect raw diffs as well as these summaries.

The [expected comparison output](evidence/icu-generation-source-hashes.txt)
retains all 30 raw hashes as well as normalized hashes and equality results.
Compare the complete output with that file, not merely the exit status.
Raw hashes distinguish the exact acquired bytes even when a disclosed
substitution produces the same normalized text. They are evidence identifiers,
not signatures: verify acquisition from the fixed commit URLs above rather
than trusting a correctly named local file.

The evidence file above owns the expected raw and normalized hashes. For
`collation.h`, it pins two normalized classes: 70.1, and all four later
versions. A bare `normalizedIdentical False` does not identify these classes;
neither the classes nor their hashes explain what differs. The description
of the flag difference rests separately on inspection of the source diff.

## Exploratory recovered-payload graph walk

The unchanged 78.1 research graph reader was applied locally to the recovered
70.1, 74.2 and 76.1 `coll/ucadata.icu` root-collation payloads. Both full-file and selected-member hashes
were checked first; the 32-byte little-endian UCol-v5 header was checked and
removed before decoding. The Windows `coll/ucadata.icu` member is byte-identical to the
74.2 member, as established in the input inventory, but that does not prove
the Windows native loader consumes it. This is not `coll/root.res`, whose
resource bytes differ between Windows and Ubuntu 74.2.

| Payload | Headerless SHA-256 | Completed roots | Completed nodes | Edges | Context tries / entries |
| --- | --- | ---: | ---: | ---: | ---: |
| 70.1 | `12fde1cd3a7bc7ea57e96f5552928fb07a57c8f61bafdbd960648d7e5c9e81bd` | 1112063 | 1114987 | 2944 | 63 / 1110 |
| 74.2; identical Windows member | `f1c9a85b806aa521cc3c622cd6c0e4593944bbb5e2b2747f465602708db71ffa` | 1112063 | 1115011 | 2968 | 63 / 1112 |
| 76.1 | `aa84747c6863f68ddb2d4d9aca34fe3169740e57bc7e09c3512724620428dfc7` | 1112063 | 1115163 | 3132 | 77 / 1147 |

The corresponding UCol header `dataVersion` bytes are `[9,112,0,0]`,
`[9,121,0,0]`, and `[9,128,0,0]`. The member hash covers those bytes;
format version 5 alone does not identify the data generation.

All three walks completed without a model failure, with maximum rank 1 and
no cycle. Each found colon CE32 `07360505`, first raw half 120980741, second
half zero, and zero stored context keys containing colon. These are bounded
aggregate observations, not a published mapping table or acceptance set.
Absence of colon in stored keys does not exclude discontiguous consumption
or prove the iterator's entry state.

The reader still declares its original 78.1 scope and reports
`inputProfileVerified`, `consumerIdentityProven`, `offsetsProven`,
`consumerTerminationProven`, `delimiterEntryStateProven`, and `acceptanceTable`
as false; `numericCollation` remains `assumed off`. The observations
above are explicitly cross-generation exploration, not promotion of those
profiles to verified status. There is no native execution or vendor-code
loading in this experiment.

The earlier leading-weight reader conservatively marks U+FDD1 unverified on
all three inputs. This is the already documented extra sentinel/default
branch, not a newly discovered consumer counterexample. The structural graph
reader's source-based default rule completes without deleting that root.
The recipe below reproduces only the structural graph, not the separate
leading-weight observation; that observation is not an additional proof gate.

### Reproduce the exploratory graph walk

From the repository root, use a recovered file and its full hash, member
`coll/ucadata.icu` offset/size/storage hash from the
[Ubuntu](unicode-reference-inputs.md#ubuntu-embedded-data-location-experiment),
[macOS](unicode-reference-inputs.md#macos-distribution-data-recovery), or
[Windows](unicode-reference-inputs.md#windows-package-result-and-selected-resource-follow-up)
inventory, and the matching payload hash above. Do not use `coll/root.res`.
The headerless payload includes any trailing member storage padding, so its
hash depends on the recorded storage size. This checks all three identity
levels without publishing bytes:

```sh
python3 -B - FILE FULL_SHA OFFSET SIZE MEMBER_SHA PAYLOAD_SHA <<'PY'
import hashlib, importlib.util, json, sys
from pathlib import Path
path, full, offset, size, member_sha, payload_sha = sys.argv[1:]
offset, size = int(offset), int(size)
with Path(path).open('rb') as stream:
    data = stream.read(64 * 1024 * 1024 + 1)
assert len(data) <= 64 * 1024 * 1024
assert hashlib.sha256(data).hexdigest() == full
assert 0 <= offset <= len(data) and 32 <= size <= len(data) - offset
member = data[offset:offset + size]
assert hashlib.sha256(member).hexdigest() == member_sha
assert member[:2] == b'\x20\0' and member[2:4] == b'\xda\x27'
assert member[8:11] == b'\0\0\2' and member[12:20] == b'UCol\5\0\0\0'
payload = member[32:]
assert hashlib.sha256(payload).hexdigest() == payload_sha
spec = importlib.util.spec_from_file_location('graph', 'scripts/inspect-icu-graph.py')
graph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph)
result = graph.inspect(payload)
result['exploratoryActualPayloadSha256'] = payload_sha
result['exploratoryMemberDataVersion'] = list(member[20:24])
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['allNonNulScalarRootsCompleted'] else 2)
PY
```

Do not run Python with assertions disabled. This is an offline research
recipe, not a product input validator. It preserves the reader's original
scope/false proof flags, and exit 0 establishes only a complete modeled walk.

## Remaining work

Finish reader-format/dependency validation before promoting these exploratory
profiles. The source helper does not yet cover every decoder dependency;
equal iterator files alone are insufficient. The
[compiled NFC evidence](unicode-compiled-nfc-evidence.md) adds native array and
initializer correspondences, not complete normalization semantics.
Effective root selection, compiled normalization and
break inputs, normal Worker/probe correspondence, arbitrary-suffix state and
the final adoption plan remain separate obligations. None is closed by an
acyclic decoded graph alone.
