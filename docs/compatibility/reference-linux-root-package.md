# Linux root-package binding evidence

Status: research in progress; does not close R1–R4 or recommend adoption.

This note connects selected native instructions to the recovered Linux root
members. The [input inventory](unicode-reference-inputs.md) owns package
acquisition and the SHA-256 identities of `libicui18n`, `libicuuc`, and
`libicudata`. Only its matching 70.1 and **74.2-1ubuntu3.1** files are covered;
the earlier, nonmatching 74.2 package is not substituted. This is static
inspection, not execution of the recovered libraries or loaded-byte attestation.

## Request and member-name correspondence

Addresses below are hexadecimal ELF virtual addresses before relocation, not
file offsets. An internal address is identified by its inspected instructions
and callers, not by the nearest exported name printed by a disassembler.

| Observation | ICU 70.1 | ICU 74.2 |
| --- | --- | --- |
| International-library root loader | `12dde0`, size `217` | `145a70`, size `25f` |
| Package-opening call | `12de88` | `145c67`, null file-path branch |
| PLT / GOT for that call | `eb2f0` / `32c9d0` | `f0fa0` / `34aee8` |
| GOT relocation target | `udata_openChoice_70` | `udata_openChoice_74` |
| Package / type / name literals | `icudt70l-coll` / `icu` / `ucadata` | `icudt74l-coll` / `icu` / `ucadata` |
| Common-library request implementation | `ffb00` | `116ec0` |
| Common-package helper call | `1002bd` → `154270` | `11736f` → `16ab10` |
| Descriptor's indirect member lookup | `154339` | `16abea` |

The request implementation classifies a null package, `ICUDATA`, and the
`icudt70l-`/`icudt74l-` or `ICUDATA-` prefixes as ICU data. The exact and prefix
comparisons are bound through PLT relocations to `strcmp` and `strncmp`.
For the observed `-coll` requests, the inspected calls to `StringPiece` and
`CharString::append` construct a basename, `/coll`, `/ucadata`, and `.icu`.
This call-sequence correspondence relies on those string helpers' contracts;
their complete compiled implementations have not been proved here.

The resulting string's pointer at frame offset `-0x80` is passed as the
common-package helper's second argument. That helper preserves it and passes
it as the second argument of the descriptor's indirect lookup. This connects
the name construction to the member lookup, rather than merely finding the
same literal in two libraries.

The 74.2 loader also has a non-null file-path branch calling `loadFromFile`.
The [root-provider source boundary](unicode-root-generation-evidence.md#root-provider-selection-source-boundary)
explains why a current ordinary getter's null argument is not proof of an
already initialized singleton's provenance. That initialization obligation
remains open.

## Linked descriptor and package format

In the inspected empty common-package-slot path, the code loads a pointer
whose GOT relocation names `icudt70_dat` or `icudt74_dat`. It initializes a
descriptor, normalizes the pointer, validates the common-data header, and
registers a copy. Registration scans ten slots under the mutex: it fills the
first empty slot and does not replace an earlier descriptor with the same
header pointer. This does not prove absence of earlier registrations.

| Observation in common library | ICU 70.1 | ICU 74.2 |
| --- | --- | --- |
| Linked-data GOT reference | `1f7f38` | `209f80` |
| Registration helper | `154190` | `16aa30` |
| Common descriptor array | `1f9e20` | `20bf20` |
| Common-header checker | `d60c0` | `e27d0` |
| `CmnD` dispatch table / first target | `1e9c80` / `cea80` | `1fba20` / `dab80` |

For a header with magic `DA 27`, pointer normalization retains the pointer.
The common-header checker requires native little-endian/ASCII fields and
format major version 1, selects the `CmnD` dispatch table, and records the TOC
at header plus its decoded size. It has a separate `ToCP` branch; that is not
the format of the recovered packages examined here.

The `CmnD` lookup uses unsigned-byte name comparisons through NUL, checking
endpoints and then a binary middle range with shared-prefix skipping. It
returns TOC plus the matching entry's data offset, with length from the next
entry's data offset (or `-1` for the last entry). This is package-name lookup,
not the Culture-sensitive command search whose safety is the overall goal.
Valid bounds and sorted names are data prerequisites, not checks enforced by
that lookup routine.

## Recovered-package observations

For both hash-matched data libraries, the exported data symbol starts at VA
`2000`, maps to file offset 8192, and contains a 144-byte `CmnD` header.
Inspection of every TOC entry found strictly increasing byte-ordered names,
strictly increasing in-bounds data offsets, and NUL-terminated names located
after the TOC entries and before the first data member.

| Observation | ICU 70.1 | ICU 74.2 |
| --- | ---: | ---: |
| Exported data-symbol size, bytes | 29466000 | 30782896 |
| TOC entries | 3825 | 4083 |
| `coll/ucadata.icu` member index, zero-based | 272 | 287 |
| Member file offset | 5793664 | 5960464 |
| Member storage length, including padding | 550688 | 572656 |

The full selected-member storage hashes match the input inventory's recovered
members. Thus this format/lookup correspondence identifies the same spans
used by the existing root-payload analyses. It does not yet prove that the
normal reference execution selects this descriptor.

## Selected-member acceptance and payload handoff

The following additional static observations concern the same hash-matched
libraries, not a new execution experiment. Common-library addresses are used
unless the table explicitly says international library.

| Operation | ICU 70.1 | ICU 74.2 |
| --- | --- | --- |
| Root acceptance callback, international library | `113b30`–`113b6f` | `130f20`–`130f5f` |
| Member acceptance call | `154388`, inline member checks | `16ac1d` → helper `10bae0` |
| Descriptor initialization | `f99e0` | `110880` |
| Descriptor copy | `f9a10` | `1108b0` |
| Descriptor allocation | `fa3a0` | `1127e0` |
| Store selected member length | `1543c1` | `16ad75` |
| `udata_getMemory` | `fede0` | `113630` |
| `udata_getLength` | `fee20` | `113670` |

Both root callbacks require `UDataInfo.size >= 20`, little-endian/ASCII
fields, the four-byte `UCol` format and format major version 5. On success
they optionally copy the four data-version bytes into the supplied context;
they do not compare the member name or type. The member-opening path checks
the `DA 27` magic and supplies **member header plus 4** as the callback's
information pointer. Thus the callback offsets refer to `UDataInfo`, not
to the start of the member header. The recovered root members satisfy those
field tests; acceptance alone is not validation of the collation payload.

The inspected descriptor initializer clears 56 bytes and sets the signed
length field at offset `0x30` to `-1`. Allocation requests 56 bytes, reports
status 7 on allocation failure, and initializes successful allocations with
the ownership flag at `0x18` set. Copying preserves the destination ownership
flag while copying the remaining descriptor fields. This describes the
callers of the allocation wrapper, not a proof of its implementation or hooks.

On the successful member path, the header pointer is stored at descriptor
offset `0x08`, and the TOC lookup's returned storage length at `0x30`.
The inspected success epilogues return that descriptor without rewriting
either field. `udata_getMemory` returns header plus decoded header size;
`udata_getLength` returns stored length minus header size, or `-1` for a null
descriptor or negative stored length. For these recovered members the header
size is 32 bytes. The resulting length includes the member's trailing storage
padding; it is not an independently derived logical collation-data length.

The international-library call bindings are also checked through relocations:
70.1 PLT `eac50` / GOT `32c680` names `udata_getMemory_70`, and `eacc0` /
`32c6b8` names `udata_getLength_70`; the 74.2 counterparts are `f0df0` /
`34ae10` and `f0a80` / `34ac58`. The root loader passes those results to its
reader with a null base argument. This connects the recovered member span to
the headerless reader input on the inspected successful path. It does not
prove the reader's complete semantics, alternative/error paths, earlier
singleton provenance, or that normal reference initialization selects this
package. Those remain reference-correctness obligations, not deployment
assumptions.

## Reproduction and remaining scope

Recover and hash-check the six libraries using the input inventory. A host
LLVM `llvm-objdump` supporting ELF can inspect them without executing them:
use `-T` for exported addresses/sizes, `-R` for relocation bindings, and
`-d --start-address=0xADDRESS --stop-address=0xEND` for the identified ranges.
For internal routines, start on an identified instruction boundary; a
nearest-symbol label alone is not a function identity. Map string/data VAs
through file-backed ELF `PT_LOAD` segments, not an assumed VA=file offset.

For package reproduction, map the complete exported data symbol, validate
the header, read the TOC count and its pairs of little-endian 32-bit name/data
offsets, and check all bounds/order properties above. Offsets are relative to
the TOC immediately after the header. Locate the exact
`icudt70l/coll/ucadata.icu` or `icudt74l/coll/ucadata.icu` name; compute its
storage length from the successor, and compare its SHA-256 with the input
inventory. The offline inspector reuses the existing bounded package inventory:

```sh
python3 -B tests/runner-package/icu_elf_package.py libicudata.so.70.1 \
  --sha256 SHA256_FROM_INPUT_INVENTORY \
  --symbol-va 0x2000 --symbol-size 29466000 --prefix icudt70l
```

Replace `SHA256_FROM_INPUT_INVENTORY` with the full-library hash for
`libicudata.so.70.1` in the [input inventory](unicode-reference-inputs.md).
For 74.2 use its full-library hash from the same inventory, symbol size
30782896 and prefix `icudt74l`. The hash and symbol coordinates are explicit
caller inputs: independently verify them using the inventory and exported
symbol table, rather than treating a successful invocation with arbitrary
arguments as identity evidence. The inspector requires one unambiguous
file-backed `PT_LOAD` mapping of the entire supplied span, ELF64 little-endian
x86-64 shared-object metadata, and the existing package parser's bounded
header/TOC checks. It does not interpret dynamic symbols itself.

`package.members` offsets are relative to the supplied package, not to the ELF
file or the TOC. Add `symbolFileOffset` (8192 in both references) to obtain the
file offsets in the table above. Compare count, member storage size and hash
with the retained observations; exit 0 only means inspection completed.
The output contains selected metadata/hashes, not vendor payloads or a full
name table. Rejected arguments, reads, identities and layouts exit nonzero
without stdout. The 64 MiB file cap accommodates both recovered data libraries;
it is a research resource limit, not a universal ELF size bound. This wrapper
does not reproduce the disassembly or prove loader behavior. Fixture coverage
is specified in the [test plan](../test-plan.md).

Remaining composition includes normal symbol resolution and dependency
selection, initialization/registration ownership, directory/access-mode
selection, the string helpers and remaining reader dependencies. This note
does not prove full native/source equivalence, resource fallback, arbitrary
suffix safety, or the other operating-system rows. None of those missing
reference-correctness claims is moved into a deployment assumption.
