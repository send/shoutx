# Offline managed reference inventory

Research helper only; no change to the producer or hosted Worker. It reads PE
metadata without loading or executing the inspected assemblies. Use only a
private, immutable, flat `bin/` extraction of an archive verified against
`../pins.json`, using the existing package harness's `verify` / `extract_bin`.
The helper does not itself authenticate an archive or protect against a local
user replacing files while they are read. Do not publish package binaries.

From the repository root, with the pinned SDK selected:

```sh
mise exec -- dotnet run --project tests/runner-package/managed-references/tests/Tests.csproj
mise exec -- dotnet build tests/runner-package/managed-references/ManagedReferences.csproj
mise exec -- python3 -B tests/runner-package/managed-references/tests/test_cli.py tests/runner-package/managed-references/bin/Debug/net8.0/ManagedReferences.dll
mise exec -- dotnet tests/runner-package/managed-references/bin/Debug/net8.0/ManagedReferences.dll PACKAGE_BIN
```

The JSON reports the exact selected method-name set, dependency-file digest,
active runtime target, every scanned asset's hash and MemberRef count, and
distinct matching name/owner/parent-kind triples (not signatures, overload
counts or field-versus-method distinctions). Names are selected regardless of declaring type;
each result still needs source/call-path analysis. In particular, AppDomain
SetData cannot be dismissed merely because its owner is not AppContext.
Unresolved parent types are retained, not silently dropped. Owner strings are
namespace/type labels, not assembly-qualified binding identities.

The supported input is the `runtime` asset map in the selected `runtimeTarget`
of `Runner.Worker.deps.json`, flattened exactly as in the reviewed packages.
It rejects ambiguous basenames, invalid path segments, nonempty `runtimeTargets`
fallback maps, missing files, nonmanaged images and malformed/oversized input.
It does not resolve satellite resources, native assets, assembly forwarding,
dynamic loading or arbitrary RID fallbacks. Caps are 4 MiB for the dependency
file, 512 managed assets, 128 MiB per assembly, 1 GiB of assembly bytes in total,
one million MemberRefs per
assembly, and 4096 selected references per assembly. JSON depth is capped at 64.
These are input/work-count caps, not a guaranteed CPU or allocation ceiling:
metadata string decoding can allocate before label lengths are checked. The
verified, immutable regular-file input requirement is essential.

`scanned-member-references` is completion of that inventory, not a proof of
absent culture/configuration changes. It does **not** enumerate intramodule
MethodDef calls, indirect calls, reflection, execution order, callsites or
actually loaded live assemblies. Internal CoreLib behaviour still needs its
fixed-source argument. Finding a reference does not show that it ran, nor
that it ran in the stdout-processing execution context.
Execution-context API coverage is limited to `SuppressFlow`; other routes
such as Run/Restore, unsafe thread starts and unsafe queueing are not inventoried.

Expected input/metadata failures exit 1 with fixed stderr and no JSON; usage
errors exit 2. Fatal runtime/resource failures are not suppressed. All scanning
and serialization finish before stdout starts, but stdout I/O failure is not
transactional. Per-file hashes identify read disk bytes, not mapped memory.
Compare them with the corresponding verified package manifest before using
the inventory as research evidence.

Fixtures exercise actual managed metadata (including a generic unresolved
parent), hash checks, every selected name, malformed/missing inputs,
duplicate JSON keys/basenames, traversal-like names, asset-count and per-file
size bounds. They do not exhaust all caps, parent-kind branches or malformed
PE layouts. Fixture
SetCurrentCulture/SetDefaultCulture methods test name matching, not platform
API binding or the completeness of the selected-name family. Fixture
methods containing setters are inspected but never invoked. No vendor payload
or live process is needed by the fixture tests.
The separate CLI tests assert empty stdout, fixed stderr and exact exit codes
for usage, missing/malformed dependency input and missing/non-PE assets, plus
successful single-document JSON output with empty stderr.
