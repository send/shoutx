# Compiled NFC input correspondence

Status: research in progress; partial R3 evidence, not a complete normalization
profile, effective-collator proof, or adoption recommendation.

For these qualified candidates, this resolves a specific acquisition question in the
[reference input inventory](unicode-reference-inputs.md): absence of a package
member named `nfc.nrm` does not imply missing NFC data. The fixed candidates
contain compiled arrays corresponding to upstream `norm2_nfc_data.h` (four of
the five source arrays are found on Windows; its threshold stores are examined
separately below).
The [claim inventory](unicode-feasibility.md#claim-inventory) remains Unproved.
The same native input evidence is relevant to both target cultures; it does not
establish either culture's complete effective path.

## Inputs and comparison method

Use the acquisition identities and qualifications in the reference inventory.
The Linux common libraries match the recorded whole-file identities. Windows
uses the official symbol-server candidate and the already documented
excluded-certificate-prefix comparison, **not** an exact historical raw DLL
match. macOS uses the recovered 24G830 distribution's primary arm64e shared
cache, **not** an attestation of the historical hosted process's loaded bytes.

| Candidate | SHA-256 of the complete inspected file |
| --- | --- |
| Linux 70.1 `libicuuc.so.70.1` | `4683f3623dc47a92e862dc3c8770caff81c9f4c7e116bb672fc439737b06d88a` |
| Linux 74.2 `libicuuc.so.74.2` | `7560aadde38e5f4237a47a1ddd5891f9b36768a77a60faae30beee003ac01901` |
| Windows symbol candidate `icu.dll` | `33bcc0ae43e8cbb2702ec2f73354865bf7bd0cca26ed14c72b840d3a23e57b2f` |
| macOS primary `dyld_shared_cache_arm64e` | `c88d3a9885614d4ee8be36f0e9a50ee09e640311ca0ea843bc67613933e00184` |

The comparison inputs are the complete generated headers, obtained from fixed
official commits. These are data correspondences, not claims that the vendors
built their entire libraries from unmodified upstream trees.

| Upstream | Fixed header | Header SHA-256 |
| --- | --- | --- |
| 70.1 | [a56dde82](https://github.com/unicode-org/icu/blob/a56dde820dc35665a66f2e9ee8ba58e75049b668/icu4c/source/common/norm2_nfc_data.h) | `695e6bba1ed19feade29416c466e04a80a1bdf63b3889a48f79c41813a87518a` |
| 72.1 | [ff3514f2](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/norm2_nfc_data.h) | `dc1d5f5523e64492b4708613e441290275663531e7d1076fd41f512b6e618ce3` |
| 74.2 | [2d029329](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/common/norm2_nfc_data.h) | `6270075f4b5f348d656d03697a4a555e56efbc0c02a74f228ab8c698f79511e4` |
| 76.1 | [8eca245c](https://github.com/unicode-org/icu/blob/8eca245c7484ac6cc179e3e5f7c1ea7680810f39/icu4c/source/common/norm2_nfc_data.h) | `e400bd8f44b16d3553a822a185af7e0755aa70e4c8ced2f51f34c6a1edfea5b6` |

The local comparison parsed only the five numeric array initializers below,
checked their declared element counts and packed values in little-endian order
using the declared 32-, 16-, or 8-bit widths. It did not compile or execute the
headers or the acquired libraries. Source inputs were bounded at 4 MiB; each
Linux/Windows binary search at 64 MiB. For macOS, the complete 2,712,977,408-byte
cache was initially hashed by streaming, then only the 2,931,740-byte region
was read and searched. Manual Mach-O load-command inspection identified it as
ICU `__TEXT` at file offset 63,602,688 / unslid address `0x183ca8000`.
The subsequent reproducible helper below hashes and captures in a single pass;
it checks the caller-supplied range, not its Mach-O identity.

## Array locations

Numbers are decimal **file offsets**, not virtual addresses or element indexes.
Each found array occurred once in the searched region. macOS uniqueness is
limited to the specified ICU segment, not the entire shared cache. The upstream
72.1 and 74.2 headers yield equal bytes for these five source arrays. This match
cannot discriminate the Windows generation; its version identification comes
from the separate file/version observations in the input inventory. The Windows
indexes count in the table is a source expectation, not a found binary array.

| Array | Width | 70.1 elements / offset | 74.2 elements / offset | Windows elements / offset | macOS 76.1 elements / offset |
| --- | --- | --- | --- | --- | --- |
| `indexes` | 32 | 20 / 1458912 | 20 / 1561024 | 20 / not found | 22 / 66089528 |
| `trieIndex` | 16 | 1748 / 1439648 | 1788 / 1541696 | 1788 / 2230272 | 1869 / 66105860 |
| `trieData` | 16 | 7974 / 1423680 | 7984 / 1525728 | 7984 / 2214304 | 8129 / 66109598 |
| `extraData` | 16 | 7732 / 1443424 | 7732 / 1545536 | 7732 / 2155136 | 7918 / 66089616 |
| `smallFCD` | 8 | 256 / 1443168 | 256 / 1545280 | 256 / 2154880 | 256 / 66105452 |

The per-array SHA-256 digests establishing the 72.1/74.2 source-byte equality
are below. Four occur in the Windows binary; the full `indexes` sequence does
not. Header hashes above differ because array equality is narrower than
whole-header equality.

| Array | SHA-256 of little-endian source values, equal for 72.1 and 74.2 |
| --- | --- |
| `indexes` | `b56f5704c14a14d4e9db6f1e057f11caf8983765cc5ffe395586762b7038f9b0` |
| `trieIndex` | `2cd6f4ac80e203b8bb2fb5684a31428555692e28373cdb855934bb35c86ae1fd` |
| `trieData` | `d3a174a95a2f157c5221b46cfd44617d55e884b06d28072a8b7dffc41864f521` |
| `extraData` | `b4584f6df86f47571052bdefb1d5ba165354bd71b2b09fb54d41bfbad817cbfe` |
| `smallFCD` | `5d1884701c69f13b0250df48d483bd46cff7426fb01fd3b1c108a3269463a60d` |

Do not substitute `nfkc.nrm` for these NFC inputs. Version 76 has a different
normalization format and two additional indexes; a local acquisition helper
that assumed 20 indexes rejected this header. That rejection was a helper
scope limit, not a native normalization failure. The 76 observation used an
explicit 22-element check instead.

### Reproduce the array observation

[`inspect-compiled-nfc.py`](../../scripts/inspect-compiled-nfc.py) now supports
the observed generated format-4/20-index and format-5/22-index spellings. These
counts are initializer lengths observed in the fixed headers, not an evaluation
of their symbolic `Normalizer2Impl::IX_COUNT` or a rule for every possible
header with that format number. It
requires both expected hashes, rejects unsupported initializer syntax/counts
and widths, and reports only counts, hashes and at most eight file offsets per
array, with a limit of one million occurrences per array. Inputs must be regular
files; Unix FIFOs are opened nonblocking and rejected. It is not a general C++ parser: acquire the exact pinned headers above,
not arbitrary source text with the same-looking declarations. Supplying a hash
does not authenticate its provenance.

For example, from the repository root with the separately acquired inputs in
the working directory:

```sh
python3 -I scripts/inspect-compiled-nfc.py norm2_nfc_data.h-70-1 libicuuc.so.70.1 \
  --source-sha256 695e6bba1ed19feade29416c466e04a80a1bdf63b3889a48f79c41813a87518a \
  --binary-sha256 4683f3623dc47a92e862dc3c8770caff81c9f4c7e116bb672fc439737b06d88a

python3 -I scripts/inspect-compiled-nfc.py norm2_nfc_data.h-76-1 dyld_shared_cache_arm64e \
  --source-sha256 e400bd8f44b16d3553a822a185af7e0755aa70e4c8ced2f51f34c6a1edfea5b6 \
  --binary-sha256 c88d3a9885614d4ee8be36f0e9a50ee09e640311ca0ea843bc67613933e00184 \
  --offset 63602688 --size 2931740
```

For Linux 74.2 and Windows 72.1 use their source/binary identities from the
tables and omit the region arguments, as for Linux 70.1. The binary cap is
4 GiB, the captured search-region cap 64 MiB. The helper hashes the complete
binary and captures the selected region in the same streaming pass; matching
a region does not permit ignoring bytes outside it. Offsets in the report
remain absolute file offsets, even for a selected region.

On 2026-10-05 all four candidates were rechecked with this helper. Each
occurrence count and location matched the table. `allArraysLocated` was true
for both Linux candidates and macOS, false for Windows because its full
indexes array is absent. The two proof flags remained false in every report.
Exit 0 means inspection completed, **not** that every array was found, that the
caller-supplied identities are authoritative, or that the native path is
verified. Inspect the report and compare its scope, counts and offsets with
the retained observation. Malformed inputs, hash failures and unsupported
ranges exit nonzero with empty stdout.

The [test plan](../test-plan.md#offline-compiled-nfc-input-research) owns the
synthetic coverage and command. Passing those tests does not revalidate the
private acquired binaries or the manual native-code observations below.

## Descriptor and initializer references

Finding arrays alone does not show that native code references them. The next
manual static checks identify the pointer-bearing trie descriptor and its initialization
arguments. Addresses in this section are hexadecimal, unslid virtual addresses
unless explicitly identified as RVAs. The array helper does not perform these
descriptor, relocation or instruction checks.
Linux/Windows instructions were inspected with Apple LLVM `llvm-objdump`
21.0.0 using the stated address ranges. macOS instructions were decoded with
the installed Apple LLVM C disassembler using `arm64e-apple-macos`, `apple-m1`
and `+v8.3a`, without executing acquired code. Tool-generated nearest-symbol
labels were not used as evidence of function identity.

### Linux

The 48-byte `UCPTrie` descriptor has two pointers followed by the source
initializer's eleven numeric fields. Using the fixed source's field widths and
alignment, both candidates matched all fields. The two pointers resolve to the
located trie arrays, and each has a matching `R_X86_64_RELATIVE` relocation.

| ICU | Descriptor file offset / virtual address | `createNFCInstance` range | `Normalizer2Impl::init` call |
| --- | --- | --- | --- |
| 70.1 | 1996384 / `0x1e8660` | `[0x9c8f0, 0x9c98a)` | `0x9c95c` → `0x9a1f0` |
| 74.2 | 2073696 / `0x1fa460` | `[0xa46c0, 0xa4752)` | `0xa472b` → `0xa3b00` |

The retained ELF symbol names identify these functions. Inspection of the full
caller routines showed the located indexes in `rsi`, descriptor in `rdx`,
extra data in `rcx`, and small-FCD array in `r8`, with the allocated implementation
object in `rdi`. This is initializer-argument correspondence, not yet the
complete collation caller path.

### Windows

The PE image base is `0x180000000`. The descriptor at RVA `0x1da130`
(file offset 1941808) matches the source numeric fields. Its two pointer slots
have `IMAGE_REL_BASED_DIR64` relocations and address the located trie arrays.
PE section mapping was checked: `.rdata` has both virtual address and raw file
offset `0x1d3000`, so this descriptor's RVA and file offset happen to be equal.

The exported `unorm2_getNFCInstance` at RVA `0xc0770` jumps to `0x44c38`,
which calls `0x44c5c`. The latter's initialization branch calls `0x44e98`,
which calls `0xaaffc` and saves the returned aggregate as the NFC singleton.
The `0xaaffc` routine initializes an allocated implementation object with the
descriptor, extra data and small-FCD pointers. It stores all twelve consumed
16-bit threshold fields as six instruction immediates starting at `0xab079`.
The **values**, not only the store pattern, match the assignments in fixed 72.1
[`Normalizer2Impl::init`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/normalizer2impl.cpp#L430),
including the derived center delta and the zero extra-data pointer adjustment.
In object-field order, the twelve source values are indexes
`8, 9, 18, 10, 14, 11, 15, 16, 17, 12`, followed by
`(indexes[13] >> 3) - 65` and `indexes[13]`. Both that sequence packed as twelve
little-endian `uint16_t` values and the concatenated six 32-bit instruction
immediates have SHA-256
`9a0faf88d3d41c87d0940fbd52fbaee30b3866c6b7dd8dc6dfad4bf5df3a7a6a`.
The instruction starts are `0xab079 + 7*i`, for `i=0..5`; each has the form
`C7 40 offset imm32`, with object offsets `8 + 4*i`. This bounded metadata
records the manual value comparison without publishing an instruction dump.

Thus the missing full indexes-array occurrence is not evidence of changed
thresholds: the observed code directly initializes every threshold consumed by
that source initializer. This does not establish compiler provenance or the
presence of unused serialized-format offsets. The routine transfers control to
RVA `0xb0000`, which constructs the aggregate containing the implementation.
The caller returns its compose member at aggregate offset 8. Internal labels
in this analysis are structural correspondences; nearest-export labels printed
by a disassembler are not internal function-name evidence.

### macOS

The descriptor at file offset 1745632392 / address `0x1e80c3c88` matches all
eleven numeric fields. Its pointer slots are in the actual slide-v5 chain for
page 76 of the mapping beginning at `0x1e7f90000`. Decoding the regular
shared-cache offsets with value-add `0x180000000` yields `0x183f0b204` and
`0x183f0c09e`, the two located arrays. Neither pointer is authenticated.
The format interpretation uses the fixed Apple dyld
[cache header](https://github.com/apple-oss-distributions/dyld/blob/fba6732ffad1c798f31b2129eee4e073e6ae07dc/cache-builder/dyld_cache_format.h)
and [pointer definitions](https://github.com/apple-oss-distributions/dyld/blob/fba6732ffad1c798f31b2129eee4e073e6ae07dc/include/mach-o/fixup-chains.h),
not an assumption that stored pointer words are plain addresses.

The initializer caller at `0x183cd8424` loads the located indexes, descriptor,
extra data and small-FCD pointers into `x1`–`x4` at `0x183cd8488`–`0x183cd84a4`.
It calls `0x183cdb264` at `0x183cd84a8`. The acquired Mach-O symbol table names
that target `icu::Normalizer2Impl::init`; its full body through `0x183cdb2cc`
loads the 76-specific indexes and stores the pointers, consistent with the
fixed 76.1 [source initializer](https://github.com/unicode-org/icu/blob/8eca245c7484ac6cc179e3e5f7c1ea7680810f39/icu4c/source/common/normalizer2impl.cpp#L430).

The exported `Normalizer2Factory::getNFCImpl` at `0x183cd8628` and
`unorm2_getNFCInstance` at `0x183cd8648` call the same singleton path at
`0x183cd84dc`. Its initialization branch calls the initializer caller above.
The first returns the aggregate's implementation pointer; the second returns
its compose member. This is a static factory-path correspondence. It is not a
claim that every collation or search operation has been traced to that factory.

## Conditional ASCII starter gate

The identified headers permit one narrow deduction without decoding their
whole normalization tries. In each of 70.1, 72.1, 74.2 and 76.1,
`IX_MIN_DECOMP_NO_CP` is index 8 and that index contains `0xc0`.
[`Normalizer2Impl::init`](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/common/normalizer2impl.cpp#L430-L434)
copies it into `minDecompNoCP`. The
[`getFCD16`](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/common/normalizer2impl.h#L304-L316)
fast path returns zero whenever `c < minDecompNoCP`, before consulting the
small-FCD array or normalization trie. The enum, assignment and branch were
inspected at all four fixed source commits from the input table. The initializer
casts to `UChar` in 70/72 and `char16_t` in 74/76; `0xc0` fits either type.
Thus an object initialized from these indexes and using this implementation
returns zero for every ASCII scalar, including U+003A. This is conditional
source/data reasoning, not an observation of the reference collator's getter.
The candidate binary/initializer evidence above retains its existing limits.

To reproduce the numeric premise from the repository root, repeat this for
each of the four headers and its SHA-256 from the input table. It uses the
existing bounded numeric-array parser, does not execute the header, and prints
only the selected threshold:

```sh
python3 -I -B - HEADER EXPECTED_SHA256 <<'PY'
import hashlib, runpy, struct, sys
from pathlib import Path
helper = runpy.run_path('scripts/inspect-compiled-nfc.py')
if len(sys.argv) != 3:
    raise SystemExit('expected header and independent expected SHA-256')
expected = helper['sha256'](sys.argv[2])
with helper['open_regular'](Path(sys.argv[1])) as stream:
    raw = stream.read(helper['SOURCE_CAP'] + 1)
if len(raw) > helper['SOURCE_CAP'] or hashlib.sha256(raw).hexdigest() != expected:
    raise SystemExit('source size or identity mismatch')
_, arrays = helper['arrays'](raw)
threshold = struct.unpack_from('<i', arrays['indexes'], 8 * 4)[0]
if threshold != 0xc0:
    raise SystemExit('threshold differs; deduction not established')
print('minDecompNoCP =', threshold)
PY
```

This recipe returned 192 on all four identified headers on 2026-10-05. It does
not mechanically verify the C++ enum, initializer or getter; those are the
separate inspected source premises above.

The result connects to a specific contraction gate. `CollationData::getFCD16`
delegates to its NFC implementation. In
[`nextCE32FromContraction` and `nextCE32FromDiscontiguousContraction`](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/i18n/collationiterator.cpp#L490-L691),
the former only enters discontiguous matching for a mismatch scalar with FCD
greater than `0xff`. The latter rejects a starter in its second lookahead and
rewinds both reads. In its main loop, a newly read scalar with FCD at most
`0xff` breaks the loop before the next match/skip iteration, and the subsequent
`backwardNumSkipped(sinceMatch)` undoes reads since the last match.
Consequently, under the stated NFC premise and valid successful bookkeeping,
a colon is not added by these skip transitions. It can be read temporarily;
this is not a claim that the cursor never crosses it.

The two function bodies agree across the four source versions after the
already documented null/Boolean/character-type spelling changes; 76 additionally
uses explicit `static_cast` for the two returned trie values and two byte
combining-class conversions. This is a bounded source comparison, not native
binary equivalence. Combine this gate with, rather than replace, the
[context-key coverage argument](unicode-context-matching-evidence.md): key
absence alone does not establish the gate's NFC premise. Nor does the gate
alone exclude a contiguous key containing colon, prove nested dispatch or
FCD-buffer behavior, establish termination, or locate the intended delimiter
in the complete header. Effective data/code binding and the surrounding
iterator/search composition remain open.

## Remaining validation

Retain these inputs as bounded metadata; do not publish vendor arrays or full
shared-cache/disassembly dumps. The array checks are reproducible above;
descriptor/relocation and initializer checks remain manual observations rather
than an automated native-equivalence verifier. Retain their addresses and
source-to-binary limitations when using them in the remaining proof, and
complete dependency/format validation before promoting a normalization profile.

The complete effective collation path, generation-specific normalization
semantics, context/FCD composition, break/search behavior and arbitrary suffixes
remain R2–R4 work. No reader profile or proof flag is promoted here; neither
target culture nor any complete reference row is declared Go.
