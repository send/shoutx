# Unicode reference input inventory

Status: partial R1/R2 evidence, inspected 2026-10-05; no adoption recommendation.

This implements the [claim inventory](unicode-feasibility.md#claim-inventory).
It separates reference inputs, probe observations and deployment conditions.
File identity is not proof of the Unicode acceptance predicate.

## Reference identities and per-culture state

Runner/runtime/source identities remain owned by
[`pins.json`](../../tests/runner-package/pins.json): Runner 2.337.0, runtime
8.0.30, SDK 8.0.424. The
[retained projection](evidence/hosted-worker-modules-37184265280.json) records
run 37184265280, attempt 1, source head
`9aa3887c9e5efbfa811198c8f46981e366a0640b` and tested merge
`2e1aeed897f1a2c6014dfa238048d5b35216d256`. Native reacquisition below compares
against those recorded hashes, not a moving hosted label.

This table is a derived status index keyed to that projection, not a second
definition of the supported matrix. The projection owns observation values;
`pins.json` owns the package/runtime pins. The scope decision owns the fixed
research target. The initial applicability table is populated; complete
reference input/normal-path correctness is still open.

The OS strings used below come from locally retained **same-run** `probe.json`
artifacts, not fields added to the published projection. Their byte hashes
were checked against its `sourceReportSha256.probe` values:

| Artifact (`runner-package-evidence-…`) | Raw probe SHA-256 | Selected field |
| --- | --- | --- |
| `windows-latest-win-x64` | `5dc737390da8b2a0a1c153a70a8cba3d09143f3298f603d874b5a3167c6fff27` | `os`: Microsoft Windows 10.0.26100 |
| `macos-15-osx-arm64` | `5b0bd7ab6ca037027c4f97328168829196186d22437ab48bf168fd41f92d58d0` | `os`: Darwin 24.6.0; xnu-11417.140.69.711.44~1 |

These are selected observations from the original reports, not a cross-run
same-image inference. Raw report retention is finite; the hashes and selected
fields here preserve the provenance without publishing full logs.

| Selector / RID | Recorded image | Probe culture | Probe ICU | Native file reacquisition | Reference correctness |
| --- | --- | --- | --- | --- | --- |
| ubuntu-22.04 / linux-x64 | ubuntu22 / 20260927.309.1 | Invariant | 70.1.0.0 | Common/international match probe; data matches Worker module only | Unproved |
| ubuntu-22.04 / linux-x64 | ubuntu22 / 20260927.309.1 | en-US | 70.1.0.0 | Same files, not proof of identical culture mappings | Unproved |
| ubuntu-24.04 / linux-x64 | ubuntu24 / 20260927.320.1 | Invariant | 74.2.0.0 | Common/international match probe; data matches Worker module only | Unproved |
| ubuntu-24.04 / linux-x64 | ubuntu24 / 20260927.320.1 | en-US | 74.2.0.0 | Same files, not proof of identical culture mappings | Unproved |
| macos-15 / osx-arm64 | macos15 / 20260907.0337.1 | Invariant | 76.1.0.0 | 24G830 distribution cache/data obtained; no historical ICU file hash to compare | Unproved |
| macos-15 / osx-arm64 | macos15 / 20260907.0337.1 | en-US | 76.1.0.0 | Same distribution inputs, not proof of effective culture mappings | Unproved |
| windows-latest / win-x64 | win25-vs2026 / 20260925.250.1 | Invariant | 72.1.0.4 | Combined ICU hash recorded; file not yet reacquired | Unproved |
| windows-latest / win-x64 | win25-vs2026 / 20260925.250.1 | en-US | 72.1.0.4 | Same acquisition gap | Unproved |

Both probe cultures report ICU and retained collator attributes. Normal startup
equivalence is not inferred. R1 remains open for complete startup/native/data
identities, R2 for the normal-path argument, R3/R4 for data and suffix proof.
Finite execution evidence for R5 and outstanding R6 plans are not promoted
by acquisition success.

## Deployment applicability, per observed row

The same deployment observation accompanies both target cultures; a startup
name does not establish either later processing-thread culture.

| Row / job ID | Startup name / job culture input | Processing culture/settings | Disk identity | Native evidence | Added configuration absence / known mismatch |
| --- | --- | --- | --- | --- | --- |
| ubuntu-22.04 / 111382850276 | Observed empty / absent | Unobserved | Nine selected package files match | ICU common/international/data mapped-file identities; common/international hashes match probe | Absence unestablished; no mismatch established for compared fields |
| ubuntu-24.04 / 111382850325 | Observed empty / absent | Unobserved | Nine selected package files match | Same categories for 74.2 | Absence unestablished; no mismatch established for compared fields |
| macos-15 / 111382850331 | Observed en-US / absent | Unobserved | Nine selected package files match | CoreCLR only; ICU module/hash unavailable | Absence unestablished; unavailable identity is not a mismatch |
| windows-latest / 111382850362 | Observed en-US / absent | Unobserved | Nine selected package files match | CoreCLR and combined icu.dll; ICU hash matches both probe roles | Absence unestablished; no mismatch established for compared fields |

An empty startup name does not distinguish Invariant comparisons from
globalization-invariant mode. Startup en-US is not measurement of the later
processing thread. The earlier macos-latest/macOS 26 observation in the
[historical audit](unicode-feasibility.md#initial-baseline-availability-historical-inventory)
is a different configuration, not a failing macOS 15 row. Updated image/version
equality remains unverified everywhere. None of these observations attests
loaded bytes or complete deployment state.

## Ubuntu native-file reacquisition

Official Ubuntu download pages identify
[`libicu70_70.1-2_amd64.deb`](https://packages.ubuntu.com/jammy/amd64/libicu70/download)
and the initial
[`libicu74_74.2-1ubuntu3_amd64.deb`](https://packages.ubuntu.com/noble/amd64/libicu74/download).
The [official archive directory](https://archive.ubuntu.com/ubuntu/pool/main/i/icu/)
also supplies 74.2-1ubuntu3.1. Downloads used HTTPS from that directory, followed
by local SHA-256 hashing. Initial-release hashes match the package-page values;
the update hash is a local download identity, not verification of a signed APT
index. No package was installed or executed.

| Downloaded package | SHA-256 | Outcome |
| --- | --- | --- |
| libicu70_70.1-2_amd64.deb | `58a154f6307289813da2276f900498ef536ae7c0522d2cf31a3c3c5cf62dfd9a` | Three selected files match Ubuntu 22.04 observations |
| libicu74_74.2-1ubuntu3_amd64.deb | `d29c97a21a3e3254731cfac186e4d4e611e5e67d2c9a0430f6acfbd9acaefa2e` | Three files differ from Ubuntu 24.04; not substituted |
| libicu74_74.2-1ubuntu3.1_amd64.deb | `c9a70989678660eed9a1e904c74fa043da8bec8e2036856fc16e31ced79b04f8` | Three selected files match Ubuntu 24.04 observations |

The update was a specific alternative after the initial 74.2 revision failed
identity comparison, not a reference-matrix change. Matching files can be
recovered without rerunning the old VM. This does not recover the VM or prove
which data the collator consumed.

| Selected member | Recovered SHA-256 |
| --- | --- |
| libicudata.so.70.1 | `c1404396288e178c8db2f30203cb8150e4d2c14cacee9a2883e0092f45399cc8` |
| libicui18n.so.70.1 | `24fa78caa9b66c10c90711c51089f45273b643f132031172d54a3e98d711d48e` |
| libicuuc.so.70.1 | `4683f3623dc47a92e862dc3c8770caff81c9f4c7e116bb672fc439737b06d88a` |
| libicudata.so.74.2 | `ddbb3718b8bd9cbd780e5ab08b4503c30a6c4fa0706ebe5d074ed6b596c1714e` |
| libicui18n.so.74.2 | `3550b194eb2cf2e6f798f033eb9ca279d498c21296b4a18790ce158d2023e47b` |
| libicuuc.so.74.2 | `7560aadde38e5f4237a47a1ddd5891f9b36768a77a60faae30beee003ac01901` |

Common/international hashes match both explicit probe cultures and Worker file
observations. Data hashes match the Worker module report; the projection has
no corresponding probe data-library hash. Effective-data binding remains open.

### Reproduction

In a fresh local directory, download the named packages from
`https://archive.ubuntu.com/ubuntu/pool/main/i/icu/` and verify their hashes.
`ar -t PACKAGE.deb` lists `data.tar.zst`. With zstd-capable **bsdtar** (including
the research Mac's tar), hash a member
without extracting or executing it:

```sh
set -o pipefail
ar -p libicu70_70.1-2_amd64.deb data.tar.zst |
  tar -xOf - ./usr/lib/x86_64-linux-gnu/libicuuc.so.70.1 |
  shasum -a 256
```

Repeat for the exact six regular-file members above in their matching packages.
Compare common/international against the selected row's
`package.explicitCultures[].collation.onDiskLibraries` and all three against
`moduleObservation.modules[].onDiskSha256` in the projection. The assessment
used selected-member extraction followed by `shasum`; the streaming command
above was also executed for the 70.1 common library and returned the same hash.
That is a same-author reproduction, not independent review. GNU tar may need
an explicit `--zstd` decompressor for stdin. Only URLs, hashes and procedure are published,
not vendor payloads or mapping tables. Acquisition does not authorize their
redistribution.

Archive pool retention is not promised. If a named revision disappears, seek
an official Ubuntu snapshot or retained original package and require the same
archive/member hashes; do not substitute a newer revision. Such a fallback
was not needed or validated in this acquisition.

## Windows/macOS source-acquisition checks

These checks narrow acquisition routes; they do not establish impossibility
or an adoption No-Go.

### Windows

The retained probe reports `Microsoft Windows 10.0.26100`. The combined
`icu.dll` observation records SHA-256
`2a6a05f37da87d9faad3da6917706a53e669b77a51885e79e1fbb9412f7405db`.
It does not retain PE timestamp/SizeOfImage lookup keys or the library bytes.

On 2026-10-05, querying the official
[Microsoft ICU releases](https://github.com/microsoft/icu/releases) and tags
returned 72.1.0.3 and 72.1.0.1, but no 72.1.0.4 release/tag. The 72.1.0.3
release offers source and Linux symbol archives, not the recorded Windows
combined DLL. The fork's
[README](https://github.com/microsoft/icu/blob/v72.1.0.3/README.md) explicitly
describes Microsoft-specific changes, including locale changes; upstream 72.1
is therefore not substituted for the observed vendor revision. The in-box
72.1.0.4 binary's correspondence to this GitHub fork is itself unestablished;
absence of a release tag is a failed candidate-source route, not evidence that
the Windows binary cannot be obtained. The probe's build prefix alone also
does not select a complete servicing revision.

On 2026-10-05, Microsoft's
[KB5122871 file list](https://download.microsoft.com/download/51e3300c-cf32-4412-91f0-6efb374fc00e/5122871.csv)
was inspected. It explicitly lists an `icu.dll` 72.1.0.4 entry of 2,765,824
bytes with the exact recorded SHA-256 above, not merely a size/version match.
This identifies a concrete official-update acquisition candidate independently
of the probe's incomplete build string. The locally downloaded CSV SHA-256 is
`d47dad23f334d5374a63c9824aef6e4bc0e9d47428ef20b4d68fceea688944bf`.
The list identifies a candidate package; it is not recovery of the DLL bytes.

A remaining alternative is exact-file recovery from an official Windows
distribution or Microsoft's symbol store, followed by comparison with the
recorded SHA-256. Symbol-store keys would first need to be recovered from a
candidate build or additional metadata; the retained SHA-256 is not such a
lookup key. Microsoft's
[debugging documentation](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/debugging-with-symbols)
describes binary as well as symbol retrieval. The release-list check alone
does not exhaust that route. A newly available hosted DLL is also only an
acquisition candidate until its hash matches; it cannot silently replace the
fixed reference.

### Bounded Windows acquisition locator

The research-only `windows-icu-metadata.yml` workflow tests and runs
`tests/runner-package/windows_icu_metadata.py`. It addresses the missing PE
lookup keys above; it is **not** a new live consumer-linkage gate. A current
Windows job is merely a candidate source, not a replacement for the fixed
image. The expected hash is read from this note's retained module projection,
whose file hash is included in the report.

The collector uses the native
[GetSystemDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemdirectoryw)
directory and first reads `icu.dll`, with an 8-MiB cap,
without loading it. The dated KB5122871 observation above places the reference
file below this cap. The 64-MiB
image-size ceiling is a defensive parser bound, not an established reference
image size; exceeding it produces a distinct unavailable-key reason.
Only an exact reference-hash match permits emission of bounded x64 PE
`TimeDateStamp` and `SizeOfImage` fields and a candidate symbol-store key.
The field layout follows the [PE specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format);
Microsoft documents executable lookup by timestamp and image size in
[Using SymStore](https://learn.microsoft.com/en-us/windows/win32/debug/using-symstore).
The key uses eight lowercase hexadecimal timestamp digits (including leading
zeros) followed by unpadded lowercase image-size digits, matching Microsoft's
[PerfView implementation](https://github.com/microsoft/perfview/blob/0b57f2120291cd6701401aa215dda213cf3a7715/src/TraceEvent/Symbols/SymbolReader.cs).
This is a candidate spelling, not a promise about every store's case policy;
the numeric fields are retained so a store-specific spelling can be rebuilt.
The timestamp is a lookup field, not an asserted build date. This is not a
general-purpose PE validator or an Authenticode check.

The artifact contains only hashes, lengths, selected numeric PE fields,
comparison algorithm identifier and file offsets, certificate size/count,
fixed schema/status/reason tokens, observation flags and
allowlisted run/image identifiers; no DLL bytes, raw paths, full environment,
exception text or mapping tables are uploaded. `candidate-mismatch` omits PE
keys but publishes the current candidate's SHA-256 and size. `unavailable`
records a fixed reason for platform/API, file access or input-size failure.
`reference-hash-match-pe-unavailable` preserves the matching digest/size with a
fixed PE-failure reason and no key. No arbitrary exception message is retained.
Successful workflow execution means a report was recorded, not that inspection
or matching succeeded.
Even `reference-hash-match` does not establish loaded identity, effective ICU
data or normal reference-path correctness. Any symbol-store download must be
hashed again before use: a lookup key is not a cryptographic file identity.

The report distinguishes source-head SHA from tested merge SHA and includes
allowlisted event, repository and job key (`GITHUB_JOB`), not numeric Actions
job ID. The latter is associated using the Actions API. Artifact retention is
seven days. The [test plan](../test-plan.md#windows-icu-acquisition-locator)
owns trigger, coverage and retention-verification requirements.

#### Retained locator observation

The reviewed [PR #88](https://github.com/send/shoutx/pull/88) collector ran in
[run 37222847326](https://github.com/send/shoutx/actions/runs/37222847326), attempt
1, job 111496490533, in `send/shoutx` on the `pull_request` event. The API
associated source head `37cbf24d8395f937f4ea40c3fc0022e360ef12d3` with tested
merge `184e6ce2001e188ca3a91842154b62b2e3c5f6e6`; the latter's parents were
`1f0bb707522f978606bd4546a23913f3c7bd6704` and that source head. The report
identified `win25-vs2026` / `20260925.250.1`, the fixed image identifier.
These are acquisition provenance, not proof of deployed loaded bytes.
This schema-version-1 report predates the additive `prefixComparison` field;
its absence is not an unavailable-comparison result.

The report recorded `reference-hash-match`, length 2,765,824, and the exact
reference DLL digest stated above. Selected PE fields were machine `0x8664`,
timestamp `0x526957c3`, image size `0x29e000`, key `526957c329e000`.
The downloaded JSON's raw SHA-256 was
`b3a8f6d3d722c81f20bf01e94cd947b8ca3d9e77a3ea0722e8ca4637058910b8`.
Its reference-projection digest was
`15ba8fb93a70a6712aa8dd937931f0034b6e1b7466438b591dcc3fc690c168de`:
hashing the source projection after LF-to-CRLF conversion reproduces that
Windows checkout digest. The source LF file digest is
`285eabb9d09ed386a306979ce2dcec653e27c091ad6025bf76d3f0cb13718f9e`.
The raw digest distinction is retained, not silently normalized away.

Downloading the [official symbol-store candidate](https://msdl.microsoft.com/download/symbols/icu.dll/526957c329e000/icu.dll)
yielded 2,765,840 bytes with SHA-256
`33bcc0ae43e8cbb2702ec2f73354865bf7bd0cca26ed14c72b840d3a23e57b2f`.
This **does not match** the reference. Matching lookup fields do not authorize
substitution. The candidate's terminal certificate table starts at 2,732,032
and occupies 33,808 bytes. A signing-only difference is a hypothesis, not an
established explanation for the 16-byte file-length difference.

#### Bounded prefix comparison

The collector additionally attempts `pe_prefix_digest.py` only after the
unchanged whole-file reference SHA-256 gate and successful locator parsing,
using the same in-memory bytes. Its `prefixComparison` records either
`available` metadata or the fixed `unsupported-prefix-layout` reason, without
discarding an already established whole-file match or lookup fields. Mismatches
never receive this comparison. This is a research acquisition aid, not a new
acceptance policy or relaxed reference-file identity test.

For the supported x64 PE32+ layout, the comparison hashes **every byte before
the terminal certificate table**, replacing only the four-byte CheckSum and
eight-byte security-directory entry with zero bytes. It validates directory
and header bounds, requires the certificate table to be eight-byte aligned,
outside the headers and every declared nonempty raw section, and ending exactly at EOF.
Walking length-prefixed certificate entries with eight-byte rounding must
consume the complete table. Files outside this narrow layout are unsupported;
this is not a general PE validity test or signature verification.
Section checks use declared file offsets and sizes; the helper does not model
loader rounding, `FileAlignment`, virtual mapping or self-inspection by code.

The algorithm identifier, prefix length, checksum offset, security-directory
offset and digest must all match before interpreting two results as evidence
of equality outside those explicit exclusions (subject to SHA-256's collision
resistance). Certificate size/count are descriptive and may differ. All
pre-certificate gaps and overlays remain included. The digest is deliberately
**not called an Authenticode hash**. The
[PE specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-attribute-certificate-table-image-only)
explains the certificate table's file-offset semantics and signing-related fields;
the [optional-header CheckSum field](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#optional-header-windows-specific-fields-image-only)
notes checksum-dependent loader validation. An equal comparison alone therefore
does not establish equivalent signatures, loading, execution or effective ICU
data. Any later use of a candidate's code for the reference argument must
separately justify the relevance of the excluded bytes to that argument.

The local symbol-store candidate downloaded and inspected on 2026-10-05 gives
prefix length 2,732,032, checksum offset
352, security-directory offset 432 and comparison SHA-256
`a74972bace80cc4880755defce4b7cce6752f90ce0ac091a5eb130ed1be3bd04`.
Its eight raw sections end no later than that prefix boundary; the final one
ends exactly there. The initial candidate-only inspection preceded the
[reference-side result below](#reference-prefix-result-and-next-data-candidate).
No loading equivalence, effective data binding or Windows acquisition closure
is claimed.

To reproduce this candidate-only result, first verify the downloaded file's
whole-file hash against the candidate digest above, then use the reviewed
helper implementing `pe32plus-terminal-certificate-zeroed-prefix-v1`:

```sh
PYTHONPATH=tests/runner-package python3 -c 'import json,sys; from pe_prefix_digest import prefix_digest; f=open(sys.argv[1],"rb"); data=f.read(8*1024*1024+1); f.close(); print(json.dumps(prefix_digest(data),sort_keys=True))' /local/path/to/candidate.dll
```

This explicit local inspection of a nonmatching download does not run through
or bypass the collector's reference gate. Do not publish the input file or
treat this candidate result as a reference-side observation.

#### Reference prefix result and next data candidate

The [PR #89 run 37224210551](https://github.com/send/shoutx/actions/runs/37224210551),
attempt 1, job 111500395100, observed the same fixed image identifier and exact
whole-file DLL hash. Source head was `fbc5b410e09ef4aca966b805733e09473c44c260`;
tested merge `314aad5b5ce690fabcd2bad9752a1ddbcc04ab5a` had parents
`baef30644794b453eac9032fa6c74efb29090152` and that source head. The run's
repository and head repository were `send/shoutx`, event `pull_request`, with
the dedicated metadata workflow. Raw report SHA-256 was
`7a819e5effffe0c8c665f2bca2a79eb29425bb68750e9793486aed15016ba144`;
its reference-projection digest was the same CRLF digest recorded above.

The reference-side algorithm, prefix size, checksum offset,
security-directory offset and digest all equal the local candidate values
above. The reference certificate size is 33,792, count 1; the candidate's is
33,808, count 1. Subject to hash collision resistance, this confines differences
to the explicitly excluded fields and certificate bytes. It is not recovery of
the original signed file, nor proof of equal loader decisions, absence of
self-inspection, effective data or reference-path behavior.

Local static inspection of that candidate supplies a concrete **acquisition
locator**, not a completed ICU load-path argument. Using Xcode's
`llvm-objdump --private-headers` and bounded disassembly, the imported
`GetSystemWindowsDirectoryW` IAT entry is at RVA `0x1ec608`; a call at
`0x5e32a` is in the routine beginning at `0x5e2f8`. That routine appends a path
separator if needed and the string at RVA `0x1f8a60`, `globalization\icu`.
A caller at `0xa1c05` feeds the result to a cached-directory setter.
Separately, code at `0x62305` and `0x62311` supplies `.dat` and `icudtl` string
addresses to the call at `0x62329`, along with the cached directory pointer.
These addresses are relative to the inspected candidate, not function names
inferred from the nearest exported symbol. Full call reachability, fallback
selection, configuration, loading and effective collation resources remain
unproved. No vendor code was loaded to obtain these observations.

This is a default-directory acquisition hypothesis, not a statement that all
ICU builds ignore configuration. In Microsoft's older
[72.1.0.3 putil.cpp](https://github.com/microsoft/icu/blob/807b1beec0dabf8a71f0bfde22da9705267f6a93/icu/icu4c/source/common/putil.cpp),
`dataDirectoryInitFn` returns if a directory was previously set. Its `ICU_DATA`
environment branch is compile-condition dependent; importantly, the later
`ICU_DATA_DIR_WINDOWS` branch replaces that candidate path when its native
directory helper succeeds. It is therefore inaccurate to assume an unconditional
environment-first precedence for the Windows build. That fork's
[udata.cpp](https://github.com/microsoft/icu/blob/807b1beec0dabf8a71f0bfde22da9705267f6a93/icu/icu4c/source/common/udata.cpp)
also conditionally changes linked-in common-data handling and file-access
selection for the Windows-directory build. This older source is not asserted
to be the in-box 72.1.0.4 source. The reference's build conditions, prior
directory/common-data setters, cache state and effective fallback selection
still need their own argument. The collector's lack of environment access
below describes only the collector, not the ICU loader.

The collector's `icu_data_candidate.py` therefore inspects only
`globalization/icu/icudtl.dat` below the native
[GetSystemWindowsDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemwindowsdirectoryw)
directory, and only after the DLL has an exact reference match and valid PE
locator. It does not use environment variables, enumerate directories or try
alternate paths. It hashes the file in bounded chunks with a 64-MiB input cap.
The report adds `dataCandidate` with fixed name/locator tokens, observed size
and SHA-256, or a closed failure reason. `observed-candidate` is deliberately
not `reference-hash-match`; the prior record had no data-file hash. A read
failure discards any partial digest. The observation describes bytes reachable
through that path at read time; path resolution may follow reparse points.
This is an on-disk candidate observation,
not an atomic file snapshot or attestation of loaded bytes. No data bytes or
resource/mapping tables are uploaded, and `effectiveDataEstablished` remains
false. Older reports omit this additive field.

The dated KB5122871 CSV above lists a 31,158,064-byte `icudtl.dat` with SHA-256
`8b1eb674fd6493f2009a8305b0ab0ed083754e9d0590d12d1cae4cf95f6268e9`
in both the x64 and arm64 Windows Server 2025 LCU sections. This supports a
concrete official-update comparison and the selected size cap, not an assertion
that the file is already bound to the reference's effective data.

#### Data candidate observation and bounded package inspection

[Run 37225475724](https://github.com/send/shoutx/actions/runs/37225475724),
attempt 1, job 111504118991, succeeded on the fixed
`win25-vs2026 / 20260925.250.1` image. Its source head was
`d6f9e7c2339bbb29af18719fd6712a02107e5fd1`, tested merge
`2e3b23448626218d503d9719698f528833461eb3` (API-verified parents
`e48b26ef13861e54bbbf8df869a79bf4643155c0` and that head).
The downloaded JSON's raw SHA-256 is
`5b4acd47e35897aa5984369cc7414628e37dc8bac98121d8d20741c0755a03a6`.
It reports the exact reference DLL hash and the same prefix comparison above,
plus a data candidate of **31,158,064 bytes** with the KB5122871 hash above.
This closes the pending candidate observation, not effective-data binding.
No vendor file was downloaded from the job.

The next research collector retains the bounded file buffer after hashing and
inspects it only if both that observed size and SHA-256 match. It does not
reopen the file between hashing and parsing. This prevents mixing two reads,
but does not make the original read an atomic filesystem snapshot. A mismatch
retains candidate metadata and reports `candidate-hash-mismatch`; an unsupported
layout reports a closed reason without partial inventory or exception text.
No names under the assumed prefix yields `prefix-mismatch`, not all absent
members. A successful inventory includes the bounded `prefixNameCount`.
If it is less than `entryCount`, absent selected names can also reflect members
under a different prefix; the count alone does not resolve that ambiguity.

`icu_package_inventory.py` implements a bounded little-endian `CmnD` format-1
offset-TOC inspection, interpreting offsets using upstream ICU 72.1
[`offsetTOCLookupFn`](https://github.com/unicode-org/icu/blob/release-72-1/icu4c/source/common/ucmndata.cpp).
This is a format interpretation, not a claim that upstream source is identical
to Microsoft's binary. Names must be bounded printable ASCII (0x20–0x7E), strictly ordered and
unique; all declared offsets are checked for bounds and data-offset order,
including unselected entries. Exact four-byte format version and strictly
increasing offsets are collector constraints, not claims about ICU's full
accepted format range. Name storage may overlap; it is not fully validated.
The count is capped at 100,000, name storage at 1,024 bytes per name, and input
at 64 MiB. Eight fixed suffixes are projected (the first version omitted `en_US`):
`coll/en.res`, `coll/en_US.res`, `coll/root.res`, `coll/ucadata.icu`, `nfc.nrm`, `nfkc.nrm`,
`brkitr/root.res`, and `brkitr/char.brk`. No full name table, member payload bytes or
mapping table is returned. Windows inspection uses `icudt72l`, confirmed in
the structure observation below; the helper
also permits the other three fixed research generations for local inspection.

Selected non-final entries report offset from the start of the supplied package
(the file offset for Windows), storage size,
SHA-256 and header format/version fields. Storage includes the member header
and padding through the next data offset. The final entry has no such length
in this format: if selected, it reports `last-entry-length-unknown` without a
size or digest. Its member header is not validated: EOF bounds the bytes but
does not supply a next-entry length to the native lookup. An absent exact name
is not proof that ICU lacks those data;
normalization, for example, may be compiled into the native library.
Unselected member payloads are not validated. This is neither a complete ICU
validator nor a collator/mapping decoder. Header or storage-hash agreement
does not establish semantics, fallback selection, or native acceptance.
R1–R4 remain open; the follow-up below records the remaining obligations.

#### Windows package result and selected resource follow-up

[Run 37227207324](https://github.com/send/shoutx/actions/runs/37227207324),
attempt 1, job 111509235154, succeeded with source head
`8b97b3246c0139f2e56c810cc57b64c17c31707f` on the same fixed image.
The tested merge `aa3d661bc42f6b9208826b01886aaf5fee3c9f1d` has API-verified
parents `45baca6e2bf1f2964c52703a772ef61007c8d557` and that head.
The metadata-only JSON raw SHA-256 is
`5f508d09f36ef2df5b7f0c957de47ba0f2ab2f3795c11f6f4f72ebb6135656d1`.
The DLL and data-file identities match the preceding observation.
`entryCount` and `prefixNameCount` both equal **4,512**. The package has a
144-byte CmnD-v1 header. Selected storage observations were:

| Member suffix | File offset | Storage bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `coll/en.res` | 4443344 | 80 | `ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b` |
| `coll/root.res` | 5518464 | 302032 | `a46fbd7d6627bb20670c58a02fec0e90c1fd01cf0d7c483b2c9ed0fac31668e5` |
| `coll/ucadata.icu` | 6085376 | 572656 | `16396c0d5ca673cb0cdf63f91b7aa8d8e1eafafe7dbc77360a177bd75aca1c5c` |
| `nfkc.nrm` | 19852992 | 55120 | `a685cc08f4b43a2201caa43b9a5a23402df8be06f014310e2f5a0eb94c98ebe7` |
| `brkitr/root.res` | 3591888 | 656 | `0ce8dcad47084e4915490c13dbc39eeb11bbb43f7a29e3391c93226846976d19` |
| `brkitr/char.brk` | 641216 | 13776 | `446460cfac65b5340c15ef7bd01fa583df95073254d58364c9c15131d59ffd8e` |

`nfc.nrm` was absent under that exact name. `en_US` was not selected by this
collector version and therefore has **no observation**, not an absent result.
The resources have ResB-v2 headers, collation root UCol-v5, normalization
Nrm2-v4, and character break Brk-v6. Member headers are 32 bytes except the
character-break header (144 bytes).

Local comparison with the recovered Ubuntu 74.2 data found exact storage-hash
matches for `en.res`, `ucadata.icu`, `nfkc.nrm` and `char.brk`. Under SHA-256
collision resistance, these selected byte ranges can share offline analysis.
Both `root.res` files differ; whole-package identity, effective selection and
complete collator equivalence do not follow. In particular, the Windows DLL's
72.1 label must not select a stock upstream data package by version alone.

To test that alternative explicitly, the official
[ICU 72.1 little-endian data ZIP](https://github.com/unicode-org/icu/releases/download/release-72-1/icu4c-72_1-data-bin-l.zip)
was read locally without loading code. ZIP SHA-256:
`1bc02487cbeaec3fc2d0dc941e8b243e7d35cd79899a201df88dc9ec9667a162`;
its 31,251,968-byte `icudt72l.dat` has SHA-256
`d201aaa64229f5d2f418d1934c971fb281ce282e10858be889489f9402d45fe8`.
It has 3,920 entries. Only `en.res` and `char.brk` among the observed storage
ranges match Windows; the other four do not. This is a rejected substitution,
not a missing-data claim. No vendor bytes were published.

The next collector adds the exact `coll/en_US.res` name and a bounded
`resource` projection for `en`, `en_US` and `root`. The interpretation uses
[`uresdata.h`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/uresdata.h)
and [`uresdata.cpp`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/uresdata.cpp).
This commit is the upstream `release-72-1` tag, selected as the 72.1 format and
loader reference, not because a version proves Microsoft's source identity.
Its file blobs were matched to the inspected source. The selected keys follow
[`ucol_res.cpp`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/i18n/ucol_res.cpp):
the loader performs parent/fallback-resolving lookups for `collations` and
`default`. If `ures_openNoDefault` or the `collations` lookup returns
`U_MISSING_RESOURCE_ERROR`, the loader returns the root entry; this is not a
test of a single file's existence. An absent, empty or overlong default becomes
`standard`. If the fallback-resolved type resource's
actual locale is root and its type is `standard`, it returns the root collator
before reading a tailoring binary. Per-file presence fields below are not
loader-visible results. This is upstream
source guidance for the research, **not** established Microsoft binary/source
correspondence or a proved en-US/root fallback path. Explicit parent/alias
resources and build-dependent override data must also be checked; see the
[conditional fallback path](#conditional-resource-fallback-path) below.

The projection accepts only little-endian ResB-v2 with seven indexes and no
pool dependency, bounded to 4 MiB. It checks key/16-bit-unit/bundle regions,
table/table32 bounds and sorted printable-ASCII keys. It traverses only the
root table and `collations` table, with at most 4,096 entries per table and
256 bytes per key including NUL. Short implicit String-v2 values have a 64-unit
scan cap including NUL. Type-0 resource word zero is also recognized as an
empty string, matching the pinned generator's
[`StringBaseResource`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/tools/genrb/reslist.cpp).
These are collector constraints, not ICU's complete accepted format.
It reports resource flags, root type and whether its offset is zero, presence of `collations`,
`default`, and `standard`, the default's equality to the fixed token
`standard`, and the standard resource's type. It also reports root-table
presence of `%%ALIAS`, `%%Parent`, and `%%ParentIsRoot` as `aliasPresent`,
`parentPresent`, and `parentIsRootPresent`. Presence includes a zero-valued
resource handle; it does not validate the value's type or follow a redirect.
This is stored-key presence, an over-approximation of loader-visible presence:
even a stored `0xffffffff` yields true, while the pinned ICU reader uses that
value as `RES_BOGUS` (missing). A true field therefore does not by itself
establish that ICU follows an alias or stops a parent walk. A false field
establishes only that this inspected table lacks the selected key.
It publishes no key list,
string value, tailoring binary, or resource tree. Missing and empty defaults
are distinct. `rootOffsetZero` identifies the offset-zero empty-table encoding;
it is not a general emptiness test for a nonzero-offset table with count zero.
An alias type can be reported but is never resolved.
Unselected resource handles and the contents of `standard` are not validated;
this is selected-path metadata, not validation of the whole resource bundle.
Pools, aliases on traversed paths, other containers and length-prefixed
strings are unsupported, not equivalent to missing values. Resource failure
retains package storage metadata but returns an allowlisted reason:
`format-version`, `pool-or-index-layout`, `container-type`, `string-encoding`,
`limit`, or `layout`. The last covers malformed bounds and unexpected parse
errors and an unterminated key within the key-cap window (including key-cap
overflow); it does not classify native acceptance. `format-version` includes
a non-ResB format identifier. The member-size cap shares
one definition between caller and parser and reports `limit` in either place.
Final package entries with unknown storage length are not parsed.
The additive `resource` field keeps schema version 1; older observations omit it.

Exploratory local inspection of the recovered 70.1/74.2/76.1 candidates found
empty `coll/en.res` and `coll/en_US.res` tables without the no-fallback flag, and root default
`standard`. This identifies selected fields, not locale fallback, absence of
other sources, or native use. The Windows observation below now supplies the
original selected fields. The three redirect-presence fields are absent from
run 37229053857; the later run 37230492630, recorded in the conditional fallback
section below, supplies them without backfilling the older observation.
R1/R2 still require the fixed reference's effective route; R3/R4 still require
mapping/normalization/break prerequisites and arbitrary-suffix composition.

For that local observation, use the full-file identities and acquisition paths
recorded in this inventory. The new `en_US` 80-byte storage regions have SHA-256
`ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b`,
at file offsets 4,183,296 (70.1), 4,352,752 (74.2), and 4,810,672 (76.1).
The first two include the ELF package's 8,192-byte base offset. Their decoded
root handle is type 2 with offset zero, not inferred from the size alone.
The `en` and `root` offsets, sizes and storage hashes are already in the
[Ubuntu member table](#ubuntu-embedded-data-location-experiment) and
[macOS data inventory](#macos); use those rows for their checks.
Reproduce the selected-field check without loading vendor code, supplying both
the full-file and selected storage hashes:

```sh
PYTHONPATH=tests/runner-package python3 -B -c 'import hashlib,sys; from pathlib import Path; from icu_resource_probe import project_resource; b=Path(sys.argv[1]).read_bytes(); assert hashlib.sha256(b).hexdigest()==sys.argv[2]; p,n=map(int,sys.argv[3:5]); member=b[p:p+n]; assert len(member)==n and hashlib.sha256(member).hexdigest()==sys.argv[5]; r=project_resource(member); assert r["status"]=="observed-selected-fields"; print(r)' FILE EXPECTED_FULL_SHA256 OFFSET SIZE EXPECTED_STORAGE_SHA256
```

#### Windows selected-field observation

[Run 37229053857](https://github.com/send/shoutx/actions/runs/37229053857),
attempt 1, job 111514650204, succeeded on the fixed Windows image with source
head `216f042d9b1b25f8aaae2adad95e6f788c59d38e`. The tested merge
`0fbc56b34780d8b61cdb55fab8d7981978530ed6` has API-verified parents
`fd29d90f24633d130d28d4dc6c99a375f08a597a` and that head. The metadata-only
JSON raw SHA-256 is
`e2482d7891039350c7d6d7d8318a47156161a735f4af710fb14b41f4cbe3f61c`.
DLL, data-file and previously selected member identities are unchanged.

`coll/en_US.res` is at file offset **4,443,424**, length **80**, with the same
`ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b`
storage hash as `coll/en.res` in the table above. Both have
`observed-selected-fields`, attributes 0, root type 2, offset zero and no
`collations` key. `coll/root.res` has attributes 0, root type 2, nonzero
offset, and present `collations`, `default`, and `standard`; its default
compares equal to `standard`, whose resource type is 2. This completes these
selected-field observations across the four candidates, not their effective
loading or arbitrary-input safety proof.

#### Conditional resource fallback path

The three new presence fields were checked locally on the recovered
70.1/74.2/76.1 `coll/root.res` byte ranges, after verifying both their
full-file and member hashes against the inventories above. All three fields
were false for each root. The same reproduction command above now emits
these fields. Windows root has different bytes and requires its own
observation, recorded below; the local results are not substituted for it. These are
same-author observations using the documented hash-gated procedure, not an
independent reproduction or committed vendor-data fixture.

The Windows follow-up is now observed in
[run 37230492630](https://github.com/send/shoutx/actions/runs/37230492630),
attempt 1, job 111518933929, source head
`6dc2dd21efa8dd5f6ab4062405767083efc5a4ce`. Tested merge
`363894bdf5d54fbfd450fc7cb93784a0692aae5c` has API-verified parents
`9e3a6ea0eaeb2fcc0a0218daee35b3924f8cacfe` and that head. Metadata JSON raw
SHA-256: `7816aace0f826b15745a4507cf86bf0f66d3ecac59aff527c5159a92a751a321`.
The fixed image and data/member hashes are unchanged. All three fields are
false for `en`, `en_US`, and root, each with `observed-selected-fields`.
This closes the selected Windows root-key observation, not effective native
loading or the vendor-source correspondence below.

The pinned upstream 72.1
[`uresbund.cpp`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/uresbund.cpp)
provides the following source-level route. These are conditional statements
about that source, not an assertion that every vendor binary uses it:

- `ures_openNoDefault` selects `URES_OPEN_LOCALE_ROOT`. The process default
  locale is queried, but the branch inserting its resource chain requires
  `URES_OPEN_LOCALE_DEFAULT_ROOT` and is not selected by this call.
- `init_entry` loads a bundle and can redirect through a nonempty `%%ALIAS`.
  Pool dependencies are another branch; the observed attributes exclude them
  in the selected files, not in arbitrary other data sources.
- After finding an existing real bundle, `findFirstExisting` uses
  `chopLocale`, not the missing-bundle search's locale-fallback tables.
  For `en_US` this produces `en`. `mayHaveParent("en")` is false.
- On this candidate path, `loadParentsExceptRoot` checks no-fallback,
  `%%ParentIsRoot` and `%%Parent` on `en_US`, then inserts `en`. The subsequent
  `chopLocale("en") || mayHaveParent("en")` is false, so the loop does not
  inspect `en`'s parent keys or no-fallback flag. The later root-insertion
  guard checks the tail's missing parent and the initial entry's no-fallback
  flag (`r`, here `en_US`), not `en`'s flag; it also requires `!isRoot` and a
  tail name other than root, both satisfied on this candidate path.
  In contrast, `init_entry` checks
  `%%ALIAS` for each loaded bundle, including root. Subject to loading those
  bytes and excluding an applicable override, root supplies the final parent.
  The absence of special keys in the observed `en_US`/`en` tables follows
  from their type-2 offset-zero empty-table encoding, not backfilled new
  projection fields. The separate Windows follow-up above now observes
  root's alias key absence as well.
- `entryOpen` can insert `usr` override bundles when `U_USE_USRDATA` and its
  path condition hold. The pinned upstream
  [`utypes.h`](https://github.com/unicode-org/icu/blob/ff3514f257ea10afe7e710e9f946f68d256704b1/icu4c/source/common/unicode/utypes.h)
  defines `U_USE_USRDATA` as 0 inside the internal-API section, with no
  `#ifndef U_USE_USRDATA` guard, excluding this branch for an unmodified build
  using that header. The same definition occurs in the fixed upstream
  [70.1](https://github.com/unicode-org/icu/blob/a56dde820dc35665a66f2e9ee8ba58e75049b668/icu4c/source/common/unicode/utypes.h),
  [74.2](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/common/unicode/utypes.h), and
  [76.1](https://github.com/unicode-org/icu/blob/8eca245c7484ac6cc179e3e5f7c1ea7680810f39/icu4c/source/common/unicode/utypes.h)
  headers. Reference vendor implementation correspondence remains to be
  established; a deployment-equivalence assumption cannot close it.

Under this 72.1 source, the resulting **candidate** chain is
`en_US → en → root`. Combined with the
collation loader's root/standard shortcut described above, this identifies
the next premises to close without decoding irrelevant tailoring binaries.
It does not yet establish the .NET locale/keyword input, reference native
implementation, selected package, override branch, or cache provenance.
`res_index` is used by available-locale enumeration in this source; its
irrelevance to the entire selected caller route is not proved merely by its
absence in `entryOpen`. R1–R4 remain unproved.

The next [root-generation evidence](unicode-root-generation-evidence.md)
compares upstream decoder premises and records exploratory graph coverage of
the recovered root payloads. It does not infer effective selection from these
resource-key results.

### macOS

The fixed
[image release](https://github.com/actions/runner-images/releases/tag/macos-15-arm64/20260907.0337)
points to source commit `9312c564c4df0b842ce00a6c202dccb519b8dfdd`. Its
[ARM64 manifest](https://github.com/actions/runner-images/blob/9312c564c4df0b842ce00a6c202dccb519b8dfdd/images/macos/macos-15-arm64-Readme.md)
identifies macOS 15.7.9 (`24G830`), Darwin 24.6.0, image
20260907.0337.1. This is stronger OS identification than the retained probe's
Darwin kernel string, but remains an image manifest, not a native module hash.

The Apple distribution tag listing inspected on 2026-10-05 contains macOS
15.0 through 15.6, with no 15.7 tag. The
[15.6 source distribution](https://github.com/apple-oss-distributions/distribution-macOS/tree/c5dd598fefabbef580b6b286bad79d2c939ee005)
references ICU commit `86abee34b1ba209ab286020ed49cf6029e94c503`
(`ICU-76104.4`). Its
[import metadata](https://github.com/apple-oss-distributions/ICU/blob/86abee34b1ba209ab286020ed49cf6029e94c503/ICU.plist)
names upstream 76.1. That matches the observed major/minor version, not the
identity of the 15.7.9 binary or its effective data. Neither that source nor
the moving ICU `main` branch closes this gap.

The fixed release's `sbom.macos-15.json.zip` was downloaded and locally hashed
as `7d1c2427567bcf9cc903f086d81e7f93fac0a3ee199b8ac84a28d7d9c0c5f9e0`.
Its sole member is `sbom.json`. A case-insensitive `icu` search over SPDX
package names found only `icu4c@78`, version `78.3`, without package checksums;
searching file names for `icucore`, `icudt` or `icu.dll` found none. This does
not identify the system 76.1 library. The SBOM is not a complete inventory of
the effective consumer inputs merely because it belongs to the right image.

The source/SBOM attempts therefore led to the 24G830 distribution acquisition
below, rather than equating 15.6 and 15.7.9.
The absence of a historical hosted regular-file ICU hash remains explicit; a same-version
replacement or the earlier local ICU 78.1 extraction is not equivalent evidence.

On 2026-10-05, the read-only `softwareupdate --list-full-installers` command
on the research Mac listed **15.7.9, build 24G830**, size 15,289,021 KiB.
Apple documents this listing route in its
[installer instructions](https://support.apple.com/en-ie/102662). Thus an
exact-build installer acquisition route is available; the source-tag/SBOM
limitations above do not justify declaring the macOS inputs unobtainable.
No installer was fetched or installed by that listing check. A subsequent
read of Apple's
[`index-15-1.sucatalog.gz`](https://swscan.apple.com/content/catalogs/others/index-15-1.sucatalog.gz)
identified product `140-85388` and its
[`InstallAssistant.pkg`](https://swcdn.apple.com/content/downloads/16/08/140-85388-A_3LX3Q36I6P/zxod6nr7zkovvsml6s628z44gdbc4exa5p/InstallAssistant.pkg),
size 15,655,958,320 bytes. The associated
[MobileAsset metadata](https://swcdn.apple.com/content/downloads/16/08/140-85388-A_3LX3Q36I6P/zxod6nr7zkovvsml6s628z44gdbc4exa5p/com_apple_MobileAsset_MacSoftwareUpdate.plist)
contains OSVersion 15.7.9 / Build 24G830. Local SHA-256 identities of the
downloaded catalog and metadata are respectively
`7013f47e6044457542f31b305012a298d6b9b3c858aad1f53e607cc2a8f67ca7` and
`2c3c461805a2305110eb9eafee76bd7cc9c440d66538b0b635cc388678bffdfb`.
These identify inspected metadata bytes, not a completed package/signature
verification. The catalog is a moving service, not a permanent snapshot URL.

HTTP range reads of the package's 28-byte XAR header and 4,311-byte compressed
TOC identify a top-level `SharedSupport.dmg` of 15,640,665,291 bytes, alongside
Payload, PackageInfo, Scripts and Bom. The TOC inspection does not execute
those scripts. Full package acquisition matched the catalog's size. Locally
computed full-package hashes are
SHA-256 `3a0d0ce4422a51b826699508a50e3f6b559cff7014daaa5b3600bbef935ecc9e`
and SHA-1 `94295f31d12db20110e7036cfc09edc8d9900b38`.

Authentication initially had a verification-context caveat: after download completion, macOS
`pkgutil --check-signature` returned `invalid signature`; `spctl --assess
--type install -vv` returned an internal Code Signing subsystem error. This
was not recorded as successful platform trust validation. Independently, the
compressed TOC SHA-1 matches its stored checksum and the catalog's `Digest`
(`9b45bc4ef6f36decb1e7b41915956193d98d01df`, **not the full-package hash**).
A local RSA/PKCS#1 v1.5 SHA-1 calculation using the embedded leaf certificate
also matches the TOC signature. That arithmetic check does not validate the
certificate chain or explain the platform error. Repeating the same
`pkgutil --check-signature` on the completed file outside the execution sandbox
then exited 0 with **signed Apple Software**, and a chain from Software Update
through Apple Software Update Certification Authority to Apple Root CA.
The leaf SHA-256 fingerprint was
`e074d204ac2498e9dc904a7bc7ced8464119b79d05668028920583b1e896ebb4`.
The sandboxed error is retained as a failed diagnostic context, not a remaining
failed validation of this download. This comparison does not isolate the exact
Code Signing subsystem failure. No trust setting was changed.

`xar` extracted only `SharedSupport.dmg`, without running Payload or Scripts.
The extracted file's locally computed SHA-1,
`82726f6620a1f9f7b25ce054996ee0d07c5ea193`, matches the signed TOC's
`extracted-checksum` and `archived-checksum` for this uncompressed member.
This records the member-to-TOC binding, not merely successful extraction.
`hdiutil attach -readonly -noautoopen` verified the image's CRC32 and mounted
it in a temporary research directory; CRC32 is not authentication. The
contained MobileAsset ZIP is
`com_apple_MobileAsset_MacSoftwareUpdate/9d95c64142a9a426f56d3265d4f8a6fa31585333.zip`.
Its `AssetData/Info.plist` names ProductVersion 15.7.9 and Build 24G830 and
lists both arm64e and x86_64 system cryptex sizes. A model field in that plist
is not used as proof of the ARM64 reference's contents. The nested payloads
are not installed or executed. Recovery results follow; binding their output
to the normal reference path remains work rather than completed evidence.

### macOS distribution data recovery

Intermediate byte identities from this local acquisition are:

| Intermediate | SHA-256 |
| --- | --- |
| `SharedSupport.dmg` extracted by xar | `fd9f33091a442203e4fc365fac8d5a390d4a013f10d657618ba618204605cfce` |
| MobileAsset ZIP named above | `1c76ee0ffbc8bcb4ec74e94d2b68fe31032f90a9a52f39847ae7fa946fa36d45` |
| ZIP member `AssetData/payloadv2/payload.019` | `cab029379ae76a9a237c6ce2b8b48ff43046dc1dd824ed845a137c86e0a1a574` |
| ZIP member `AssetData/payloadv2/image_patches/cryptex-system-arm64e` | `b52cea9e8a7669a14f2a9113d2b6e9b62261dd4bf37d8dcbfed990f3df09121c` |

These hashes permit comparison with this acquisition; they are not separately
signed vendor digests or independent verification of either decoder's output.

The ZIP's `AssetData/payloadv2/image_patches/cryptex-system-arm64e` is a
3,739,720,226-byte `RIDIFF10` patch, not directly a mountable disk image.
A local helper followed the ABI in
[`ipsw`'s pinned restoration wrapper](https://github.com/blacktop/ipsw/blob/5727faf392125073a057291cfe21659667aa9c79/pkg/ota/ridiff/ridiff.go)
to call the research host's existing `/usr/lib/libParallelCompression.dylib`
`RawImagePatch`, with empty base input, two worker threads, exclusive new
output, a 16-GiB output-file cap and 300 CPU-second cap. A guard would reject
`pbzm` in the initial 256 bytes; that marker was absent in this input.
This is use of a private host API for local acquisition, not a supported
product dependency or an independently verified patch decoder. The local
helper's SHA-256 is
`a503aba94359e89fe0d5167b8e3cccf2e4fc806614f1a7867b4eb1d8cd958570`.
It is not archived with this repository, so this cache-restoration step is
not yet a complete third-party reproduction recipe. Do not confuse its
identified local result with a reviewed, portable acquisition tool.

The research host reports macOS **26.6.2 / 25G83**, not the reference OS.
Its `/usr/bin/aa` SHA-256 is
`7c044bed6385a33ff7fc39286a48da7c37fd52420022bbed47038ba7fe6f3109`;
`aa -version` printed usage, so no separate version value is asserted.

The call returned 0 and produced a 5,985,271,808-byte image, locally hashed as
SHA-256 `36e116d370e93fe36bae7b847dbe66d770fe54fba7467bb1ee7f4cd1036c4804`.
A read-only mount
contains `System/Library/CoreServices/SystemVersion.plist` with ProductVersion
15.7.9 and ProductBuildVersion 24G830. Its **system** (not DriverKit)
`System/Library/dyld/dyld_shared_cache_arm64e.map` lists
`/usr/lib/libicucore.A.dylib`, including a `__TEXT` range
`0x183CA8000`–`0x183F73C1C`. The shared cache and its `.01` subcache are
available locally for subsequent code/UUID/section inspection. A map entry is
not extraction of a relocatable library, proof of its runtime binding or a
comparison with the historical hosted process.

Read-only `aa list` scans of the 47 `payload.NNN` archive members found
`usr/share/icu/icudt76l.dat` in `payload.019`. An exact-path, regular-file-only
`aa extract` with filesystem attributes excluded and filesystem compression
disabled recovered **33,979,312 bytes**, SHA-256
`8f4dbfa2ea1a43bd07ba6a12885798b1f7c6f8ead23e1ce08e5625457fe6df76`.
No payload code was executed or installed; recovered vendor bytes remain
local. The following is the extraction procedure used with the identified ZIP;
a second extraction has not been recorded:

```sh
set -o pipefail
unzip -p PATH_TO_ASSET_ZIP AssetData/payloadv2/payload.019 |
  aa extract -include-path usr/share/icu/icudt76l.dat -include-type f \
    -exclude-field attr -afsc-none -d FRESH_LOCAL_DIRECTORY
```

The recovered file has a little-endian `CmnD` v1 header of 144 bytes and 4,855
TOC entries. A bounded offset-TOC inspection found these regions; storage
hashes include each 32-byte member header and padding, not just its payload:

| Member suffix | File offset | Storage bytes | Storage SHA-256 |
| --- | ---: | ---: | --- |
| `coll/en.res` | 4810592 | 80 | `ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b` |
| `coll/root.res` | 5941360 | 347536 | `e9ba5da6fb872dc8ad2d23731013c366e530f94a3e921a3d8daf94e17e027949` |
| `coll/ucadata.icu` | 6572048 | 577504 | `57ca8fa4ed257687cedd0420094edc808122003600fc2de57bfcab787c1972ac` |

The offset-TOC interpretation follows `offsetTOCLookupFn` in the identified
[Apple 15.6 ICU source](https://github.com/apple-oss-distributions/ICU/blob/86abee34b1ba209ab286020ed49cf6029e94c503/icu/icu4c/source/common/ucmndata.cpp):
offsets are relative to the TOC and consecutive data offsets delimit storage.
This identifies the format interpretation used, not 15.7.9 binary/source
correspondence or validation of each member's internal format.

The identical small `en.res` hashes across distributions do not prove equivalent
complete collators. This supersedes the initial acquisition gap for the
distribution data. It
does not close generation-specific decoder validation, vendor code/data load
binding, effective tailoring/fallback, or the historical unobserved file
identity. The reference proof must still connect the recovered distribution
inputs to the declared normal reference path; deployment identity remains a
separate applicability condition.

### macOS cached-library identity and path evidence

Hashing the recovered system cache pair gives:

| File | SHA-256 | Cache UUID |
| --- | --- | --- |
| `dyld_shared_cache_arm64e` | `c88d3a9885614d4ee8be36f0e9a50ee09e640311ca0ea843bc67613933e00184` | `0517ae48-31dc-3086-8d85-545fef4d70b7` |
| `dyld_shared_cache_arm64e.01` | `bc07c9ed09350888003cd15777cdb17053d86c1e97dadd1582f4051d6ac4b296` | `50354eb3-77f7-390a-82ff-add75e24e40f` |

The cache header/mapping layout was checked against Apple's
[`dyld_cache_format.h`](https://github.com/apple-oss-distributions/dyld/blob/fd8d0c4d52320ebf64db34f3cb280310d905c5ae/include/mach-o/dyld_cache_format.h).
Using the map's ICU address and the cache's mapping table locates a 64-bit
ARM64e Mach-O header at primary-file offset **63,602,688**, with 18 load
commands. A bounded load-command walk reports:

- `LC_ID_DYLIB`: `/usr/lib/libicucore.A.dylib`, current version **76.1.0**;
- `LC_UUID`: **5a8ab5d2-79d5-389e-8c2d-27d6c797125a**;
- a `__cstring` region at primary-file offset 66,488,232, length 36,255,
  containing `/usr/share/icu`, `icudt76l` and `icudt76l-coll` among other
  package-name literals.

Cache hashes and UUIDs identify locally reconstructed outputs, not independently
authenticated reconstruction results or historical installed/loaded bytes.
Treating the full installer's 24G830 contents as candidates for the hosted
image is an explicit same-OS-build inference, not proof of on-disk equality;
image provisioning or servicing may differ. The header's version is consistent with the earlier probe's
76.1 report; equality of that version alone is not an implementation identity
proof. No cached library was loaded into the research process.

The older, explicitly identified Apple 15.6 source's
[`dataDirectoryInitFn`](https://github.com/apple-oss-distributions/ICU/blob/86abee34b1ba209ab286020ed49cf6029e94c503/icu/icu4c/source/common/putil.cpp)
has branches for a preselected directory, package data, permitted `ICU_DATA`
environment overrides and compiled-in default directories. The inspected
binary literals are consistent with the system-directory route but do **not**
prove which compile-time branches exist or which path a call executes. This
source comparison does not promote 15.6 source into attested 15.7.9 source.
Binary/source correspondence and the normal reference's effective data loading
remain R2 obligations, not deployment assumptions or reasons to repeat file
hashing without new evidence.

## Ubuntu embedded-data location experiment

A local, read-only ELF64 little-endian section/TOC inspection of the recovered
data libraries found `.rodata` at file offset 8192 in both. Its header is ICU
`CmnD` format 1, with a 144-byte header. The TOCs contain 3,825 (70.1) and
4,083 (74.2) entries. The experiment checked file/section bounds, TOC count and
entry bounds, NUL-terminated sorted names, and increasing data offsets.

The interpretation follows `UDataOffsetTOC` and `offsetTOCLookupFn` in official
[`release-70-1`, a56dde8](https://github.com/unicode-org/icu/blob/a56dde820dc35665a66f2e9ee8ba58e75049b668/icu4c/source/common/ucmndata.cpp)
and
[`release-74-2`, 2d02932](https://github.com/unicode-org/icu/blob/2d029329c82c7792b985024b2bdab5fc7278fbc8/icu4c/source/common/ucmndata.cpp):
offsets are relative to the TOC, and a non-final item's storage length is the
next data offset minus its own. This is a source-based interpretation of the
recovered Ubuntu bytes, not validation of every member or a native comparison.

| Library | Member suffix | File offset | Storage bytes | SHA-256 of storage |
| --- | --- | ---: | ---: | --- |
| 70.1 | `coll/en.res` | 4183216 | 80 | `ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b` |
| 70.1 | `coll/root.res` | 5250016 | 299440 | `7b4313fa560441868f486bde30e3ac3c08b67778d68b0b5d8b7269e1ff07222b` |
| 70.1 | `coll/ucadata.icu` | 5793664 | 550688 | `4acf5c47f636d2edf69bb20d22fa724bf07f6ca53ae759beb81a99f1e631e8ec` |
| 74.2 | `coll/en.res` | 4352672 | 80 | `ee066818c0bfc2e92c9f4486f3087c3669b998786b0363a04467136d80c00d8b` |
| 74.2 | `coll/root.res` | 5409840 | 307808 | `f6bfa76f91688c9137b76c0c6b64b0f16663b10a95b9ef8aa839eccd56c902fd` |
| 74.2 | `coll/ucadata.icu` | 5960464 | 572656 | `16396c0d5ca673cb0cdf63f91b7aa8d8e1eafafe7dbc77360a177bd75aca1c5c` |

Names have `icudt70l/` or `icudt74l/` prefixes. These hashes include the
32-byte member header and any trailing storage padding; they are **not**
headerless indexed-payload hashes. The resource members identify as `ResB`
format 2 and the collation roots as `UCol` format 5. Neither format equality
nor the identical small `en.res` proves equivalent complete collators.

After checking the full-library hash, individual byte-range hashes are
reproducible without loading or publishing the library. For the 70.1
`coll/ucadata.icu` member:

```sh
python3 -c 'import hashlib,sys; f=open(sys.argv[1],"rb"); f.seek(5793664); b=f.read(550688); assert len(b)==550688; print(hashlib.sha256(b).hexdigest())' libicudata.so.70.1
```

This establishes accessible bounded input regions, not effective-data binding
or correct decoding of mappings. Generation-specific root/resource decoding,
locale fallback, normalization data (including any compiled-in data), break
data and consumer connection remain R2/R3 work. The existing 78.1 reader has
not been promoted to a 70.1/74.2 verifier by this experiment.

## Probe/normal-startup differences to resolve (R2)

At this source baseline, `scripts/test-runner-package.py` sanitizes probe
environment overrides and then enables host tracing. It invokes SDK
`dotnet exec` with the package Worker runtimeconfig/deps and added Probe.dll.
`Probe.csproj` uses `UseAppHost=false`. Thus its entry path is not the ordinary
Worker apphost, even though later runtime identities are checked.

The [reference/probe correspondence](reference-worker-correspondence.md)
now retains the original four probe host handoffs and accounts for their
property-bag observations, selector filtering and explicit entry/cwd differences.
It evidences that subclaim, not complete native or command-path equivalence.

Enumerate relevant reference startup inputs with evidence, distinguishing
controlled probe absence from unobserved live values. Use the existing host
source analysis to resolve apphost versus SDK selection, package configuration
and culture/cache propagation. Sharing runtimeconfig alone does not close R2.
Linux file recovery does not settle Windows/macOS selection or data access;
those remain bounded reference acquisition tasks, not a demand to inspect
GitHub's internal deployment.
