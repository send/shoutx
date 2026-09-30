# Published Runner runtime evidence

This note describes the package-backed probe added after PR #54. It does not
change accepted input, the deferred `th-TH` issue, or stdout release eligibility.
The [workflow-command note](github-actions-workflow-command-parser.md#ascii-boundary-allowlist-derivation)
owns the ASCII fast-path argument; this note connects it to a concrete package.

## Identity chain

The reviewed [pins](../../tests/runner-package/pins.json) bind Runner v2.337.0
to its release commit, three published archives (Linux x64, macOS ARM64,
Windows x64), byte sizes and SHA-256 digests. Archive identities came from the
[official release API](https://api.github.com/repos/actions/runner/releases/tags/v2.337.0)
on 2026-09-30. They are checked before extraction or execution, not refreshed
from the network at test time.

`Runner.Worker.runtimeconfig.json` must declare the self-contained
`Microsoft.NETCore.App` 8.0.30 framework. The probe uses that unmodified file
and `Runner.Worker.deps.json` with `dotnet exec`. The SDK builds the small probe,
not Runner or its runtime. The host trace must select CoreCLR from the package;
loaded `System.Private.CoreLib` and `Runner.Common` must also come from its
directory and match the extracted-file digests. Their informational versions
must name the pinned runtime and Runner commits. All original extracted bin
files are hashed again after the probe; adding `Probe.dll` is the only change.

These checks bind execution to reviewed package bytes and upstream build
metadata. They are not a reproducible-build proof that source produced those
bytes. The SDK executable still acts as the launcher, and this is not the
unaltered `Runner.Worker` entry point or a measurement of an active hosted job
consumer. No runner is registered and no job credentials are used.

## Corresponding .NET source

The .NET 8.0.30 tag resolves to
`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`, matching the observed package core
library's build metadata. The pinned
[CompareInfo.Icu.cs](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Globalization/CompareInfo.Icu.cs)
was compared in full against the previously inspected 8.0.0 file.
The only difference is an added remaining-input check on the no-match path of
`IndexOfOrdinalIgnoreCaseHelper`. `IndexOfOrdinalHelper`,
`StartsWithOrdinalHelper`, `_isAsciiEqualityOrdinal` initialization, and the
ASCII table are unchanged. The case-sensitive `CompareOptions.None` argument
therefore also applies to this **specific** 8.0.30 source revision, subject to
its ICU-mode preconditions. It is not extended to other .NET versions or NLS.
Both source files and their reviewed digests are retained in each artifact.

## Observations and limits

The probe explicitly tests Invariant Culture and `en-US`; these are probe
settings, not an observation of the live worker's culture. For each culture it
parses the generated Rust mask/annotation corpora with the packaged
`ActionCommand.TryParseV2`, comparing the exact command, data, properties and
separator position. It additionally tests every non-NUL scalar after eight
ASCII starts for mask and an annotation header. The source-built oracle still
owns OutputManager, command extension, masking, and path-translation checks.

Globalization-mode properties/fields and the instance ASCII fast-path flag are
recorded when exposed. Missing metadata is null, not false. Where the ASCII
flag is true and invariant mode is false, the probe queries the package's
native globalization bridge by explicit filename for its already-initialized
ICU version; it never calls `LoadICU` to change the mode. The bridge is also
hashed. Its version export and byte packing are checked against pinned
`Interop.ICU.cs` and `pal_icushim.c`. A zero/missing result is **unknown**, not
ICU version 0 and not permission to substitute the sort version.

The local macOS ARM64 run on 2026-09-30 observed .NET 8.0.30, the matching
Runner build, and successful parser checks under both cultures. The ASCII flag
was true, invariant mode false, sort version 34969. `UseNls` and `Hybrid`
metadata were absent, and the native bridge returned zero. Thus the report
does **not** mark full ICU source preconditions observed on that run. Runtime
and source identity have been established more precisely; the remaining
backend observation gap is not silently treated as resolved.

CI repeats the probe on Ubuntu 22.04, Ubuntu 24.04, macOS 15 ARM64 and Windows.
Passing this finite matrix does not establish a supported self-hosted matrix,
all Unicode sequences, or all operating-system collation-data versions.

## Reproduction and retained evidence

With Python 3.10+, the pinned .NET SDK and Cargo available:

```sh
python3 -B tests/runner-package/test_harness.py
python3 scripts/test-runner-package.py --output target/runner-package-evidence
```

For mise-managed development, prefix the second command with `mise exec --`.
`--archive PATH` can reuse a download but never bypasses its digest/size check.
The output directory must be new; an old report cannot satisfy a new run.
The script's staging tree is temporary and removed after success or failure.

Each `runner-package-evidence-OS-RID` CI artifact retains, for 30 days:

- `evidence.json`: status, pins, package identity, worker configuration,
  selected CoreCLR digest, CI/image identity and host-trace digest;
- `probe.json`: runtime/parser identities, globalization observations,
  explicit cultures and parser-test counts;
- original extracted bin digests, inspected .NET source snapshots, synthetic
  corpora, build/execution logs and `corehost.log`;
- source-built oracle TRX results, including its runtime observations.

The CI aggregate fails if the probe fails; artifact upload runs on failure too.
Consult the status fields and job conclusion, not artifact presence alone.
Download an artifact before retention expires if longer-term audit is needed.
Logs contain synthetic test values and local staging paths, never job secrets.
