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
loaded `System.Private.CoreLib`, `Runner.Common` and `Runner.Worker` must also come from its
directory and match the extracted-file digests. The end-of-test loaded managed
assembly snapshot is checked the same way (except the separately hashed probe
and runtime-generated service-double assemblies, whose names are checked
against the observed DispatchProxy builder identity).
Their informational versions
must name the pinned runtime and Runner commits. All original extracted bin
files are hashed again after the probe; adding `Probe.dll` is the only change.

These checks bind execution to reviewed package bytes and upstream build
metadata. They are not a reproducible-build proof that source produced those
bytes. The SDK executable and its selected hostfxr still act as the launcher;
hostfxr observations are retained from the trace, not claimed to be package-pinned.
This does not individually attest every loaded native dependency (including
hostpolicy, clrjit and OS ICU data), and this is not the
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
Both CompareInfo source files and their reviewed digests are retained in each artifact.
The artifact also retains digest-pinned `Interop.ICU.cs`, `pal_icushim.c` and
`pal_collation.c`. The latter supports the manual
[native-search investigation](github-actions-workflow-command-parser.md#remaining-source-argument);
source hashes do not attest the loaded native implementation.

## Observations and limits

The probe explicitly tests Invariant Culture and `en-US`; these are probe
settings, not an observation of the live worker's culture. For each culture it
parses the generated Rust mask/annotation corpora with the packaged
`ActionCommand.TryParseV2`, comparing the exact command, data, properties and
separator position. It additionally tests every non-NUL scalar after eight
ASCII starts for mask and an annotation header. The package command-effects
suite below complements this parser-only check. The source-built oracle still
covers broader policy, container/path translation and feature-flag scenarios.

Globalization-mode properties/fields and the instance ASCII fast-path flag are
recorded when exposed. Missing metadata is null, not false. Where the ASCII
flag is true and invariant mode is false, the probe queries the package's
own CoreLib `Interop.Globalization.GetICUVersion` binding for the initialized
ICU version; it never calls `LoadICU` to change the mode. This avoids loading
a separate uninitialized shared shim when CoreCLR statically links that shim.
The export and byte packing were manually checked against pinned
`Interop.ICU.cs` and `pal_icushim.c`; CI verifies those source digests, not that
manual analysis. A zero/missing result is **unknown**, not
ICU version 0 and not permission to substitute the sort version.
`backendFromFlags` reports only reflected mode metadata; the per-culture
`backendObserved` additionally uses the positive CoreLib ICU observation.
The source-precondition result requires no positive NLS/Hybrid flag, invariant
mode false, the ASCII flag true and a nonzero ICU version. In the inspected
source that ASCII flag is initialized on the ICU path, not the NLS path.
The finite parser, command-effects and
[research-only Unicode parser and Worker-effects checks](../test-plan.md#v2-unicode-data-start-research)
do not themselves require ICU preconditions. A future unknown/NLS run
can pass those finite checks without confirming the ICU source argument, but only if
it also reproduces the required negative controls. A fixed or different backend
may fail that control gate without demonstrating unsafe candidate acceptance;
inspect the research case/error labels described in the linked test plan.

The subsequent [native collation observation](../test-plan.md#native-collation-observation)
adds a stricter gate: overall `passed` requires package identity, all preceding
checks, positive ICU preconditions and complete native observations for both
cultures. Unknown/NLS behavior can still
pass the preceding finite suites but no longer passes the complete harness.
Native inspection uses the pinned runtime's private layout after prior suites
finish; it does not run inside an unmodified hosted Worker. Missing exports or
native faults are observation failures, not evidence that an input is unsafe.

The historical runs cited below predate the Unicode candidate extension;
their passing results do not include that research suite or the later Unicode
Worker-effects extension. Consult fresh artifact fields for the latter's
coverage; local macOS results do not attest Linux or Windows behavior.

The local macOS ARM64 run on 2026-09-30 observed .NET 8.0.30 and ICU 78.1.0.0
through CoreLib's binding, with invariant mode false and the ASCII flag true
under both cultures. Each culture passed 793 mask cases, 2,632 annotation
cases and 17,793,008 scalar checks. This is one local observation, not an
inference about other macOS versions or hosted images.

CI is configured to repeat the probe on Ubuntu 22.04, Ubuntu 24.04,
macOS 15 ARM64 and Windows. Consult each run's recorded image and backend
observations; these labels alone are not evidence of execution.
Passing this finite matrix does not establish a supported self-hosted matrix,
all Unicode sequences, or all operating-system collation-data versions.

The [2026-09-30 four-platform run](https://github.com/send/shoutx/actions/runs/36699413944)
at PR head `3d3a87f0151dc0890e2cbe26eab17833093c619b` (tested merge
`c98042c8eaffcfe36c5b9a5271f72b90e0a7811a`) passed with the following
package-probe observations. Both explicit cultures observed the ICU source
preconditions and passed the same counts as the local run above.

| CI label | Recorded image / version | Observed ICU |
| --- | --- | --- |
| Ubuntu 22.04 | ubuntu22 / 20260920.303.1 | 70.1.0.0 |
| Ubuntu 24.04 | ubuntu24 / 20260920.314.1 | 74.2.0.0 |
| macOS 15 ARM64 | macos15 / 20260907.0337.1 | 76.1.0.0 |
| Windows latest | win25-vs2026 / 20260925.250.1 | 72.1.0.4 |

All four selected package CoreCLR/CoreLib 8.0.30 while the external launcher
hostfxr was 10.0.12; launcher version is not the tested runtime version.
Windows exposed `UseNls=false`; Unix omitted that metadata. Missing flags
remain null rather than being filled in from the OS label.

## Package command-effects probe

The follow-up to PR #55 runs the complete generated mask/annotation corpora
through packaged `OutputManager.OnDataReceived`, `ActionCommandManager`, the
four real command extensions and `ExecutionContext`. Each case has fresh job,
step, command-manager and `SecretMasker` state. `ExecutionContext.Write`,
`AddIssue` and step `Complete` are not mocked: assertions observe redacted log
lines at both the console queue and paging-logger input, retained timeline
issues and completion-time annotation conversion. Actual paging-file bytes,
timestamps, rotation and upload are not simulated or claimed.
Worker identity must match the pinned Runner build as well as its archive hash.

Only host service discovery, settings and external log/server sinks are strict
in-process service doubles. Unexpected calls fail instead of silently returning
defaults or opening a network connection. The real packaged SecretMasker uses
the encoder registrations copied from the pinned HostContext constructor;
Pin updates must re-check this registration list against HostContext and the
service-double line counter against PagingLogger; neither is an upstream API
promise. HostContext startup itself is not executed. Dynamic dispatch-proxy assemblies
are test infrastructure, not substituted Runner implementations. Problem
matchers, containers, server upload and live job-worker startup are not tested
by this suite. Hosted checks remain separate evidence of actual upload/UI
behavior, not a consequence of local completion success.

The corpus fixture deliberately sets `github.workspace` and
`github.repository` to empty strings, matching the source oracle's corpus
context. Its file metadata expectations do not claim realistic workspace
relativization or production `repo` insertion (including Windows separator
rewriting); separate source-oracle path scenarios own that coverage.
The entry point is a decoded .NET string event: native stdout decoding and
physical-line splitting in ProcessInvoker/StepHost remain hosted-test concerns.
The parser phase validates wire framing before the effects phase removes LF.
Whitespace-only input and overlong messages rejected by shoutx, issue caps,
mask-expansion truncation and feature-disabled behavior remain broader
source-oracle cases rather than reachable paths in these accepted corpora.

For both Invariant Culture and `en-US`, the suite checks:

- exact-value masking and a changed result for fixture-defined derived samples
  (not a promise that every sample becomes only `***`), absence of raw command echo or
  unexpected issues, and subsequent `ExecutionContext.Write` redaction;
- each notification's severity, message, category, platform-specific metadata,
  runner-added step/first-log numbers, single log entry with echo enabled, retained
  annotation and unchanged successful step result;
- four synthetic stop/wrong-token/resume sequences: stopped lines are ordinary
  unredacted output and have no mask/issue effect, an incorrect token does not
  resume processing, and the matching token restores each command;
- masked `add-mask` echo and a masked annotation with completion-time default
  end positions, title and file preserved.

The local macOS ARM64 run on 2026-09-30 passed 793 mask and 2,632 annotation
effect cases, four stop/resume cases and one echo/masked-annotation case per
culture. Coverage is checked separately from the earlier scalar parser sweep.
These are bounded command-effects observations, not a resolution of `th-TH`,
new Unicode acceptance, or stdout release eligibility. The earlier four-OS
table above predates this extension and is not evidence for these new checks.

The [first command-effects matrix run](https://github.com/send/shoutx/actions/runs/36711931190)
at head `7a046d8` / tested merge `82b8fea7ff04cfbbd17eb5a314e2bb4ebd95c1ce`
passed these counts under both cultures on all four OS labels. Downloaded
artifacts confirmed the pinned Worker build and package identities. Later
review hardening adds the second log-sink comparison and stricter diagnostics;
that earlier run does not claim to test those additions.

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
Runtime instrumentation, additional-dependency and globalization override
environment variables are removed for probe execution; their names, never
values, are recorded. Ordinary host discovery and locale variables remain;
the two tested cultures are explicitly selected inside the probe.
The three ambient OutputManager/stop-token test-policy overrides are removed
as well. `worker-trace.log` and `unicode-worker-trace.log` are deliberately
disabled trace sinks, reopened for each culture; neither is behavioral
evidence or a record of both cultures.

Each `runner-package-evidence-OS-RID` CI artifact retains, for 30 days:

- `evidence.json`: status, pins, package identity, worker configuration,
  selected CoreCLR digest, CI/image identity, harness/probe digests, tool
  versions, removed environment names and host-trace digest;
- `probe.json`: runtime/parser/worker identities, globalization observations,
  explicit cultures, parser-test, current-policy and research Worker counts,
  observed research cultures and negative controls, and synthetic
  service-double assembly names;
- native collation observations in `probe.json`, including module paths,
  resolved ICU version, actual/compiled rule digests, context/scalar counts and
  numeric empty-equivalent examples; extracted `break-rules.json` and its digest
  in `evidence.json`;
- original extracted bin digests, inspected .NET source snapshots, synthetic
  corpora, build/execution logs and `corehost.log`;
- source-built oracle TRX results, including its runtime observations.

The CI aggregate fails if the probe fails; artifact upload runs on failure too.
Consult the status fields and job conclusion, not artifact presence alone.
Download an artifact before retention expires if longer-term audit is needed.
Logs contain synthetic test values and local staging paths, never job secrets.
