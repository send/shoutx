# Reference culture names and comparison caches

Status: bounded R2 source argument, inspected 2026-10-05. No row is promoted
to Go. The [claim inventory](unicode-feasibility.md#claim-inventory) owns the
remaining reference obligations. This note connects explicit Invariant/en-US
inputs to the managed sort-handle cache; it does not establish effective ICU
data, native binary/source correspondence or arbitrary search-state safety.

## Managed-to-native names

The .NET source pin is
[`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`](https://github.com/dotnet/runtime/tree/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f).
The relevant files were byte-compared with that official commit. In its
`src/libraries/System.Private.CoreLib/src/System/Globalization/` directory:

- `CultureInfo.CompareInfo` lazily caches a CompareInfo. With user overrides,
  it redirects to `GetCultureInfo(_name).CompareInfo`; comparison properties
  are not supplied by user overrides. `CultureInfo.InteropName` forwards
  `CultureData.InteropName`, which is `_sWindowsName`.
- `CultureData.CreateCultureWithInvariantData` sets `_sWindowsName` to an
  empty string. This is Invariant **Culture**, not globalization-invariant
  mode. The latter bypasses the ICU sort-handle initialization.
- `CultureData.Icu.InitIcuCultureDataCore` passes the requested name to
  `GetLocaleName` and stores its result as `_sWindowsName`. Its later
  `NormalizeCultureName` assigns `_sRealName`, not that interop name.
  The desktop Unix route uses this ICU initialization. Windows with
  `UseNls=false` also uses it, then checks Windows support through
  `GetLocaleInfoEx` without substituting that call's output as the interop name.
- `CompareInfo.InitSort` sets `_sortName` from `culture.SortName`, but passes
  `culture.InteropName` to `IcuInitSortHandle`. The sort-handle cache is keyed
  by this latter name. Its parameter's spelling `sortName` must not be used to
  equate those two fields. The ASCII optimization flag checks `_sortName`;
  observing that flag does not measure the interop name.

[`pal_locale.c`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_locale.c)
implements `GlobalizationNative_GetLocaleName` using `GetLocale` with
canonicalization enabled, hence `uloc_canonicalize`, followed by conversion
back to UTF-16 and `FixupLocaleName` (underscore to hyphen). The managed
wrapper constructs its result from that buffer. This is a name-normalization
route, not a measurement of which tailoring/resource the collator loads.

## Concrete upstream ICU name transformation

Inspected upstream pins are 70.1 `a56dde820dc35665a66f2e9ee8ba58e75049b668`,
72.1 `ff3514f257ea10afe7e710e9f946f68d256704b1`,
74.2 `2d029329c82c7792b985024b2bdab5fc7278fbc8`, and
76.1 `8eca245c7484ac6cc179e3e5f7c1ea7680810f39`. These are generation
references, not assertions that Microsoft/Apple binaries are unpatched builds.

| Explicit Culture | Name passed to the managed sort-handle cache under the inspected ICU mapping | ICU Locale name on successful ordinary construction |
| --- | --- | --- |
| Invariant | Empty string, from the invariant CultureData singleton | Empty string, not the default-locale request |
| en-US | `en-US`, after native canonicalization to `en_US` and .NET hyphen fixup | `en_US` |

In `icu4c/source/common/uloc.cpp`, `_canonicalize` handles the two concrete
names without BCP47-extension conversion: the shortest-subtag test is zero
for empty and two for `en-US`, not one. For `en-US`, language parsing yields
`en`; `US` is not a four-letter script and is a two-letter region. There is
no variant or keyword; the canonicalization map has no `en_US` replacement.
The output is `en_US`. Empty input stays empty and does not take the null
argument's default-locale branch.

The 70.1/72.1/74.2 language/script/country helpers and canonicalization map
match after only null/boolean spelling adjustments. The 74.2 extension
conversion change is outside these two inputs. **76.1 is not treated as
textually equivalent**: its new `ulocimp_getSubtags` and `_getLanguage`,
`_getScript`, `_getRegion` were inspected separately. Their successful paths
produce the same fields for these inputs, and `_canonicalize` joins them with
underscores. This is a concrete-input source argument, not a claim about all
locale names or a finite-test proof about arbitrary message strings.

`icu4c/source/i18n/ucol_res.cpp` passes `ucol_open`'s string through the
implicit `Locale` constructor to `Collator::createInstance`. In
`common/locid.h`/`locid.cpp`, omitted country/variant/keyword arguments default
to null. A non-null empty language is distinct from all-null arguments:
it builds an empty `CharString` and calls `init` with canonicalization false.
`CharString` initializes its buffer with NUL and exposes that buffer via
`data()`. `Locale::init` uses `uloc_getName`; only a null argument requests
the default Locale. The later CLDR canonicalization branch is disabled here.

`i18n/coll.cpp` has a service-registration branch as well as `makeInstance`.
On the latter path, `CollationLoader::loadTailoring` returns the root entry
for an empty/root Locale name. This does not prove that a registered service
cannot intervene in a reference build, nor that en-US resolves to root data.
The existing [resource-fallback analysis](unicode-reference-inputs.md#conditional-resource-fallback-path)
owns those data-selection conditions; upstream names alone do not close them.

## Cache identity is not search-state equivalence

`CompareInfo.Icu.SortHandleCache` locks a dictionary keyed by the interop
name. On a miss it calls `Interop.Globalization.GetSortHandle`; allocation
and native errors throw, and failure to insert closes the new native handle.
Successful existing entries are reused. The interop declaration in
`src/libraries/Common/src/Interop/Interop.Collation.cs` specifies UTF-8 string
marshalling: the invariant name is an empty string, not a null locale argument.

At the fixed .NET native source,
[`pal_collation.c`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_collation.c)
creates the base collator with `ucol_open` and stores it in option slot zero.
`GetCollatorFromSortHandle` returns it directly for options zero; other options
use separate lazily cloned slots. Thus the explicit empty and en-US cache
keys do not share a managed sort-handle entry merely because their effective
collation data might coincide. Native internal sharing is a separate question.

The [existing search argument](github-actions-workflow-command-parser.md#remaining-source-argument)
already records the per-handle/options search pool, custom-break selection
and null fallback. Reuse sets text and pattern, but the existence of those
calls alone is not proof that every relevant ICU search field is reset.
Concurrent overflow nodes and process-cached break rules also remain relevant.
This note therefore does not promote a fresh probe result to arbitrary prior
Worker state, or move those reference-correctness obligations to deployment
assumptions. Actual Culture propagation in a live deployment remains a
different applicability condition.

## Reproduction and evidence limits

Read the named functions from the fixed commits above; the bounded concrete
input walk is the argument, not an executable imitation of ICU. The retained
[source hash manifest](evidence/reference-culture-source-hashes.txt) records raw
bytes, before spelling comparison. Download .NET entries from
`https://raw.githubusercontent.com/dotnet/runtime/<commit>/<path>` and ICU
entries from `https://raw.githubusercontent.com/unicode-org/icu/<commit>/<path>`;
compare each raw SHA-256 with the manifest before repeating the inspection.
No acquired binaries were executed and no vendor data tables are published.
Source identity is not native build identity; source matching and effective
data binding remain in R1/R3, and complete cache/search composition in R2/R4.
