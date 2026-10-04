# Reference Worker / probe correspondence

Status: partial R1/R2 argument, inspected 2026-10-05. No acceptance change or
Go recommendation. The [claim inventory](unicode-feasibility.md#claim-inventory)
owns overall status; the [reference input inventory](unicode-reference-inputs.md)
owns the fixed rows. This note accounts for the host handoff and separates it
from the still-open native and command-path obligations.

## Two entry paths and a reported hostpolicy generation

The [normal apphost assessment](worker-host-configuration.md#normal-apphost-route)
identifies the package Worker executable, its bound Worker DLL, app-local
hostfxr/hostpolicy and self-contained runtime configuration. The normal
Listener launch uses the bin directory as cwd and `spawnclient` plus two pipe
handles. No SDK launcher is part of that source path.

The [probe launcher](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/scripts/test-runner-package.py) instead builds
`Probe.dll` with the SDK, copies it into the checked package bin directory,
and runs `dotnet exec` with explicit Worker runtimeconfig/deps paths. Its cwd
is the temporary work directory, not bin. `Probe.csproj` disables apphost
generation. The entry assembly, cwd and launcher are real differences, not
made identical by sharing a runtimeconfig file.

The [selected handoff projection](evidence/reference-host-handoff-37184265280.json)
records all four package jobs from run 37184265280. Its identity owner retains
the run/attempt/job/image and source/tested commit associations. Each local
`evidence.json` was matched to that owner's `sourceReportSha256.evidence`,
then `corehost.log` was matched to the report's `corehostTraceSha256` before
extracting fields. The launcher reports hostfxr **10.0.12**, while the invoked
hostpolicy reports **8.0.30** and the pinned runtime commit. The existing
package checks independently identify selected CoreCLR and loaded managed
assemblies; a version banner is not a loaded-file hash or reproduced build.
This projection does not bind hostpolicy's path or loaded bytes to the package
bin file; another copy of the same build could report the same banner.
Official package/source correspondence remains an explicit inference, as in
the [package identity chain](runner-package-runtime.md#identity-chain).

The launcher, Program, WorkerProbe and project files used for this argument
are from source head `9aa3887c9e5efbfa811198c8f46981e366a0640b`. In a separate
author-performed check, git blob bytes matched each report's `sourceDigests`
directly on Unix and after LF-to-CRLF checkout conversion on Windows. That
source comparison is not reproduced by the trace recipe below. Compared at
main commit `05634499c8854b12959d13737ecd3bd4b9567367`, the filter function
and WorkerProbe are unchanged from that head; later Program
and launcher transport additions are not backfilled into this run.

All four traces contain the same twelve property names listed in the
projection. The only `System.Globalization.*` property is
`PredefinedCulturesOnly=false`; `STARTUP_HOOKS`, `HOSTFXR_PATH`, `APP_PATHS`
and `APP_NI_PATHS` are absent. `PROBING_DIRECTORIES` and `FX_DEPS_FILE` are
present but empty. These are **probe initialization** observations, not live
Worker measurements. Paths, property-pointer values and full logs are not
published.

## Why the trace describes the initialization handoff

At .NET commit `a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`,
[`hostpolicy.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/hostpolicy.cpp)
has the ordinary sequence `corehost_main` → context creation →
`create_coreclr` → application execution. While holding its context lock,
`create_coreclr` calls `log_properties` and then passes that same bag to
`coreclr_t::create`.
[`coreclr.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/coreclr.cpp)
defines that single `log_properties` emission, which logs every pair; its
create routine enumerates the bag into the arrays passed to
`coreclr_initialize`. The recipe checks that the one hostpolicy invocation
banner precedes all property lines. There is no intervening property mutation in this
inspected ordinary sequence. This establishes the meaning of the observed
trace under the package/source inference; it is not a claim against arbitrary
external instrumentation or later application writes.

[`hostpolicy_context.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/hostpolicy_context.cpp)
also constructs `HOST_RUNTIME_CONTRACT`; its presence is not evidence of an
unknown SDK-injected globalization setting. Its pointer value is deliberately
not retained. Empty `FX_DEPS_FILE` agrees with the self-contained route.
Empty `PROBING_DIRECTORIES` covers only the lookup entries returned by
[`get_lookup_probe_directories`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp),
not servicing or published-directory probes. This is a muxer-mode probe
observation and is not transferred to the apphost route. It cannot prove every loader
input irrelevant.

## Reference startup inputs and their evidence roles

The package-default side of this comparison means the identified package
configuration with no deployment-added configuration. It is not a statement
that those additions were absent in historical hosted Workers. The proposed
[reference boundary](../decisions/github-actions-stdout-framing.md#proposed-reference-configuration-boundary)
permits that deployment equality condition; it does not permit assuming native
selection or mapping correctness.

| Input | Package/default or probe evidence | Consequence and remaining limit |
| --- | --- | --- |
| Main Worker config/deps | Hash-identified package files; includedFrameworks 8.0.30 and three explicit false properties, recorded in the identity owner | Source analysis selects self-contained hostpolicy; not a claim of identical entry assemblies |
| Worker dev sidecar, additional config properties | No dev sidecar in the three archives; no STARTUP_HOOKS or additionalProbingPaths in the main files | Package-default reference adds none; deployment additions are applicability conditions, not presumed observed absent |
| Invariant / UseNls / AppLocalIcu switches | Not in main package config; not in the observed probe property bag | Environment fallbacks and native load outcome must also be accounted for |
| DOTNET_SYSTEM_GLOBALIZATION_INVARIANT, DOTNET_SYSTEM_GLOBALIZATION_USENLS, DOTNET_SYSTEM_GLOBALIZATION_APPLOCALICU | Removed by the fixed probe environment filter if present | The probe's corresponding overrides are absent; this is controlled harness state, not live environment evidence |
| DOTNET_STARTUP_HOOKS / DOTNET_SHARED_STORE / DOTNET_MULTILEVEL_LOOKUP | Also removed by that filter | No probe hook property; an absent multilevel variable means its platform default, not necessarily disabled lookup |
| CLR_ICU_VERSION_OVERRIDE / ICU_DATA | Explicitly removed by the filter | No corresponding probe override; native default library/data selection still needs R1/R3 binding |
| COMPLUS_, CORECLR_, COR_, LD_, DYLD_ variables | Removed by the filter | Bounds probe instrumentation/loader overrides; not a complete environment inventory |
| COREHOST_TRACE / COREHOST_TRACEFILE | Cleared by the filter, then explicitly set for trace collection | Probe-only diagnostics; no inference that the normal Worker emits this trace |
| CORE_SERVICING, locale variables and retained discovery variables | Not all removed; the filter explicitly retains selected DOTNET_ROOT/CLI names | No claim of a fully sanitized environment or identical lookup inputs; use resolved identities and the normal-path analysis for relevant assets |
| Comparison Culture | Program sets CurrentCulture to Invariant or en-US before obtaining its CompareInfo; Worker checks the expected culture | Fixed reference comparison input, not inference from child locale or observation of live processing-thread culture |

The exact filter and the original report's removed-name list serve different
purposes: the filter specifies what is passed to the probe, while the list
only identifies inherited names that were actually removed. It is not a list
of every relevant environment variable or its value.

The pinned
[`AppContextConfigHelper`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/AppContextConfigHelper.cs)
uses a recognized AppContext switch first, then its named environment fallback,
with default false for the Invariant/UseNls calls. The pinned
[`GlobalizationMode`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Globalization/GlobalizationMode.cs)
uses AppContext then the environment for the app-local ICU string. Consequently
the observed probe property bag plus its controlled filter accounts for these
probe selector inputs; it is more evidence than the main JSON file alone.
On Windows, absent UseNls does **not** establish ICU: failed default ICU loading
also selects NLS. Unix non-invariant initialization instead fails fast when
ICU cannot load. The retained per-culture native observations supply separate
positive probe ICU evidence. Their transfer to the normal reference path is
not inferred just from these selector values.

## Command-path correspondence and what is still open

[`WorkerProbe`](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/tests/runner-package/WorkerProbe.cs) invokes the package
OutputManager, ActionCommandManager, four target extensions, ExecutionContext
and SecretMasker. It substitutes transport/service endpoints, not those
implementations. Its fixture registers a copied encoder list, enables enhanced
annotations, supplies a synthetic repository/workspace and starts with fresh
state. Unexpected service calls fail the probe. Those are named test inputs,
not a measurement of arbitrary preceding workflow state.

| Difference | Evidence established here / already retained | Required continuation |
| --- | --- | --- |
| SDK muxer/hostfxr versus package apphost | Distinct versions and host modes explicitly identified; probe reports the 8.0.30 hostpolicy banner before its initialization bag, and normal package route is source-assessed | Bind hostpolicy path/bytes and relevant resolved assets/settings on normal reference route; do not substitute the SDK launcher source for the package launcher |
| Probe.dll entry and temporary cwd | Explicitly identified; relevant runtime/managed identities are checked by the package harness | Account for cwd-sensitive lookup and normal Worker startup before treating a probe result as full path equivalence |
| Explicit culture / initialized caches | Per-culture CompareInfo/backend and Worker expectations are checked | Bind normal reference comparison/cache/settings path; live culture propagation remains an applicability condition |
| Service doubles / limited extension list / initial state | Actual target processing/effects are exercised with finite controls | The universal framing argument must establish the intended command before dispatch; a reduced extension list cannot rule out every fallback interpretation by itself |
| Native data/search/break path | Probe observations and acquired-file inventories exist separately | Finish effective selection, source/data correspondence and arbitrary-suffix composition (R1/R3/R4) |

The **probe host-property handoff** subclaim is now evidenced. R2 as a whole
remains Unproved; no row or culture is promoted to Go. The next work is the
identified normal-path and effective-input argument, not another live
absence collector or a repetition of passing string samples.

## Reproduce the selected projection

From the repository root, use the four original `runner-package-evidence` directories from run
37184265280, in the identity owner's row order (Ubuntu 22.04, Ubuntu 24.04,
macOS 15, Windows). The following performs no network access and prints only
the selected projection after all identities and fixed expected fields pass.
Raw reports/logs stay local. Isolated Python mode ignores `PYTHONOPTIMIZE`;
the recipe also explicitly rejects disabled assertions before reading inputs.

```sh
python3 -I -B - DIR_UBUNTU22 DIR_UBUNTU24 DIR_MACOS15 DIR_WINDOWS <<'PY'
import hashlib, json, re, sys
from pathlib import Path
if not __debug__:
    raise SystemExit('projection requires assertions enabled')
base = Path('docs/compatibility/evidence')
owner = json.loads((base / 'hosted-worker-modules-37184265280.json').read_bytes())
expected = json.loads((base / 'reference-host-handoff-37184265280.json').read_bytes())
assert expected['sourceRunId'] == owner['sourceRun']['id']
assert expected['identityOwner'] == (base / 'hosted-worker-modules-37184265280.json').as_posix()
assert len(sys.argv) == 5 and len(owner['rows']) == len(expected['rows']) == 4
def read(path, cap):
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    assert len(raw) <= cap
    return raw
for folder, identity, selected in zip(sys.argv[1:], owner['rows'], expected['rows']):
    assert (selected['selector'], selected['rid']) == (identity['selector'], identity['rid'])
    raw = read(Path(folder) / 'evidence.json', 1024 * 1024)
    sha = hashlib.sha256(raw).hexdigest()
    assert sha == identity['sourceReportSha256']['evidence'] == selected['sourceEvidenceSha256']
    evidence = json.loads(raw)
    trace = read(Path(folder) / 'corehost.log', 64 * 1024 * 1024)
    assert hashlib.sha256(trace).hexdigest() == evidence['corehostTraceSha256'] == selected['sourceTraceSha256']
    text = trace.decode('utf-8')
    props, property_lines = {}, []
    lines = text.splitlines()
    banners = [i for i, line in enumerate(lines) if line.startswith('--- Invoked hostpolicy [')]
    assert len(banners) == 1
    for i, line in enumerate(lines):
        if line.startswith('Property '):
            name, sep, value = line[9:].partition(' = ')
            assert sep and name not in props
            props[name] = value
            property_lines.append(i)
    assert property_lines and all(i > banners[0] for i in property_lines)
    assert evidence['launcherHostFxrBuild'] == selected['launcherHostFxrBuild']
    assert re.findall(r'^--- Invoked hostpolicy \[(.*?)\] corehost_main = \{', text, re.M) == selected['invokedHostPolicyBuild']
    assert sorted(props) == selected['propertyNames']
    assert {k: v for k, v in props.items() if k.startswith('System.Globalization.')} == selected['globalizationProperties']
    assert ('STARTUP_HOOKS' in props) == selected['startupHooksPropertyPresent']
    assert ('HOSTFXR_PATH' in props) == selected['hostFxrPathPropertyPresent']
    assert (props.get('PROBING_DIRECTORIES') == '') == selected['probingDirectoriesEmpty']
    assert (props.get('FX_DEPS_FILE') == '') == selected['frameworkDepsFileEmpty']
print(json.dumps(expected, indent=2))
PY
```

This verifies consistency with provenance-checked, hash-bound local
reports, not a signed attestation. Missing artifacts leave reproduction
unavailable; a retained hash is not a substitute for its input bytes.
