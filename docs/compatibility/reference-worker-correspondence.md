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

## Application base versus process working directory

The distinct entry assembly and cwd do not by themselves imply distinct
hostpolicy application bases. The following bounded argument combines normal
package/source inference with the recorded probe handoff, not a claim that
the probe's SDK hostfxr is the normal Worker hostfxr.

The historical [launcher](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/scripts/test-runner-package.py#L484-L506)
resolves the temporary work path before constructing `binary = work / "bin"`.
Its [execution arguments](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/scripts/test-runner-package.py#L546-L557)
therefore give absolute paths for `Probe.dll`, Worker runtimeconfig and Worker
deps, while leaving process cwd at `work`. No relative `--depsfile` is used.

In [`args.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/args.cpp#L18-L142),
`parse_arguments` obtains the managed application from host information in
apphost mode and from the first application argument in muxer mode. Both
call `init_arguments`. Its non-bundle `set_root_from_app` resolves the managed
application path and starts with its directory as `app_root`. A nonempty
explicit deps path then **replaces** `app_root` with that deps file's directory.
For the absolute deps path here, this rule does not depend on process cwd.
This explains the 8.0 hostpolicy rule, not the uninspected 10.0.12 hostfxr's
forwarding of command-line arguments. The latter is bridged by the observed
property values below. In the ordinary
Worker route there is no user deps override. The pinned
[`get_init_info_for_app`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/fx_muxer.cpp#L366-L384)
gets an empty deps option by default and [passes that value](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/fx_muxer.cpp#L493-L498)
to `corehost_init_t`. Its [stored value](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/corehost_init.cpp#L19-L26)
is [placed in the interface](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/corehost_init.cpp#L108)
and copied into hostpolicy's `deps_file` by
[`hostpolicy_init_t::init`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/hostpolicy_init.cpp#L17-L38).
Thus its derived Worker deps and
resolved managed application are both in the package bin directory.

| Path | Managed application | Deps selection | Resulting application base |
| --- | --- | --- | --- |
| Package Worker apphost | Bound `Runner.Worker.dll` | Normal derived Worker deps | Resolved directory of the bound Worker DLL, under the existing package/source inference |
| Recorded SDK-launched probe | Copied `Probe.dll` in extracted bin | Explicit absolute Worker deps in the same bin | Observed selected CoreCLR directory, not the temporary parent cwd |

“Same” here means the corresponding package-bin role within each execution,
not equality of the absolute paths of two different installations.
[`deps_resolver_t`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.h#L42-L93)
stores this `args.app_root` as `m_app_dir` and uses `args.deps_path` for the app's
deps input. Its [`get_app_dir`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.h#L147-L175)
returns that directory with a trailing separator for these modes. Its libhost
empty-base and legacy single-file extraction exceptions are not these paths.
[`hostpolicy_context`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/hostpolicy_context.cpp#L272-L315)
uses this result for `APP_CONTEXT_BASE_DIRECTORY`; optional `APP_PATHS` uses
the same base only when its separate configuration switch requests it.
The source also uses `m_app_dir` when processing published-directory deps
entries, but a common seed directory does not identify each winning asset.

The projection's added `applicationBase` fields check the probe independently
of the SDK-forwarding assumption, not independently of the same-author evidence.
They check the probe
side on **all four recorded rows**. After the existing report/trace hash gates,
the recipe requires a single CoreCLR-path line, absolute base/CoreCLR/deps
paths, the base equal to that CoreCLR path's parent, and exactly one app deps
path naming `Runner.Worker.deps.json` in that base. All three retained Boolean
fields are true on all four rows. The historical harness's
[`verify_coreclr`](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/scripts/test-runner-package.py#L426-L431)
already checks that selected CoreCLR path against the extracted package file.
Thus this probe-base result does not assume that SDK 10.0.12 forwards the
argument exactly as hostfxr 8.0 would; it uses the resulting initialization
properties. The probe DLL's placement in bin is also explicit in the launcher,
not inferred solely from the deps override.

Offline path comparison uses target-OS pure-path lexical conventions (including
Windows case folding), not the inspecting machine's filesystem. A Windows
case-sensitive directory could distinguish names that this comparison equates.
The four recorded path sets are ASCII; the recipe requires that bounded
observation rather than claiming arbitrary non-ASCII trace encoding fidelity.
It establishes recorded
path relationships, not symlink resolution or loaded-file attestation. No
paths or full logs are published. The normal Worker result remains the stated
source inference, not a newly observed live Worker base; a linked/versioned
installation directory is not equated to its launch cwd string.

It does **not** make all initialization inputs equal. The
[TPA construction](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp#L514-L548)
adds the managed entry assembly before processing the app deps; the probe has
an additional, different entry assembly. Full TPA equality is neither asserted
nor needed merely to identify the base. Likewise, the existing
[servicing/store assessment](worker-host-configuration.md#residual-inputs-and-evaluated-alternatives)
records a relative Unix fallback `opt/coreservicing`: different cwd values can
still select different lookup locations there. The muxer-only host-relative
shared-store probe is another host-mode difference, and Windows servicing
selection is not disposed of by a cwd argument. Published-directory base
correspondence does not establish which candidate wins each asset lookup or
bind the resolved globalization library/data. Resolved-asset evidence and the
remaining normal startup/cache/native arguments are still required; no
deployment-absence audit is added by this lemma.

## Selected deps assets and servicing

On 2026-10-05, the three local `Runner.Worker.deps.json` files were matched by
SHA-256 to both `worker.onDiskSha256` and `manifestWorkerFiles` in the
[retained identity projection](evidence/environment-transport-37193467498.json).
Both Ubuntu rows use the same Linux file. This is a new inspection of those
identified files, not a new hosted run or an observation of loaded bytes.

Only `targets[runtimeTarget.name]` was inspected, not the union of the portable
and RID targets. All three name `.NETCoreApp,Version=v8.0/<rid>`.

| RID | Libraries | Selected runtime assets | Selected native assets | Non-serviceable libraries |
| --- | ---: | ---: | ---: | ---: |
| linux-x64 | 152 | 209 | 14 | 5 |
| osx-arm64 | 152 | 209 | 14 | 5 |
| win-x64 | 151 | 210 | 14 | 5 |

The five libraries are `Runner.Worker/2.337.0`, `Runner.Common/1.0.0`,
`Runner.Sdk/1.0.0`, `Sdk/1.0.0`, and
`runtimepack.Microsoft.NETCore.App.Runtime.<rid>/8.0.30`. The runtimepack has
162 runtime and all 14 native assets; each of the other four has one runtime
asset and no native assets. Other libraries are serviceable: this observation
does not exempt every dependency from servicing. Within each asset type there
are no duplicate selected asset names, including after ASCII case folding and
the host's `.ni` name adjustment. The probe entry `Probe` is not among them.

At the fixed .NET commit, the following source chain gives this data meaning:

1. [`deps_format.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_format.cpp#L104-L181)
   copies the library's `serviceable` boolean to each asset entry.
   `load_self_contained` uses `process_targets` on the selected target and
   sets `is_rid_specific=false`; a RID in the target name does not change this
   to RID-subdirectory probing.
2. [`deps_resolver.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp#L210-L374)
   orders servicing before published-directory probes and shared/additional
   lookup stores after them. Each servicing probe is skipped for a
   non-serviceable entry. The app probe uses `to_dir_path` for these entries
   and returns immediately on success.
3. [`deps_entry.cpp`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_entry.cpp#L19-L173)
   constructs the published basename path for runtime/native entries.
   When file-existence checking is enabled it requires that path to exist;
   otherwise it accepts the constructed path. Every runtime/native basename
   of the five libraries exists in the inspected local package-bin copies.
   That presence check is not a hash check of those assets. Under the identified
   non-bundle package layout, it covers both existence-check branches, so later
   stores do not win these individual lookups.
4. [`resolve_additional_deps`](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp#L610-L627)
   returns immediately for self-contained applications. Framework deps are
   also not appended on this route. These are source properties, not presumed
   observations that deployment-added files were absent.

The [TPA resolver](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp#L416-L590)
still inserts the entry assembly first and has duplicate/version replacement
rules. Normal Worker and Probe therefore do not have identical TPA lists.
The selected-target non-duplication check removes a competing manifest entry
for the named assets; it does not characterize every managed load or cache.

The [native-directory resolver](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp#L745-L919)
projects resolved native paths to parent directories and deduplicates them.
Because all selected native entries belong to that non-serviceable runtimepack,
the entries contribute the single published-bin directory role on both paths.
This bounds the cwd-sensitive servicing/store difference for these entries;
it does **not** establish OS-loader dependency resolution, active ICU identity,
source/binary correspondence, or complete normal-path equivalence. Those
remain R1/R2 obligations, not new deployment-absence gates.

### Reproduce the deps inspection

Use the extracted `bin` directories from the three pinned official Runner
packages, in Linux/macOS/Windows order. This recipe reads files only; it does
not execute acquired binaries or print vendor asset tables. Do not run Python
with `-O`, which removes its assertions. It verifies deps identity against
both retained fields before inspecting the selected target. Local asset
presence remains separate from the deps hash and from loaded-file identity.

```sh
python3 - /path/linux/bin /path/macos/bin /path/windows/bin <<'PY'
import collections
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

assert len(sys.argv) == 4
owner = json.loads(Path(
    'docs/compatibility/evidence/environment-transport-37193467498.json'
).read_text())
specs = [('linux-x64', 152, 209), ('osx-arm64', 152, 209),
         ('win-x64', 151, 210)]
for directory, (rid, library_count, runtime_count) in zip(sys.argv[1:], specs):
    base = Path(directory)
    raw = (base / 'Runner.Worker.deps.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = [row for row in owner['rows'] if row['rid'] == rid]
    assert len(rows) == (2 if rid == 'linux-x64' else 1)
    for row in rows:
        assert row['worker']['onDiskSha256']['Runner.Worker.deps.json'] == digest
        assert row['manifestWorkerFiles']['Runner.Worker.deps.json'] == digest
    deps = json.loads(raw)
    assert deps['runtimeTarget']['name'] == '.NETCoreApp,Version=v8.0/' + rid
    target = deps['targets'][deps['runtimeTarget']['name']]
    libs = deps['libraries']
    assert len(libs) == library_count and set(target) <= set(libs)
    pack = 'runtimepack.Microsoft.NETCore.App.Runtime.' + rid + '/8.0.30'
    nonserviceable = {name for name, lib in libs.items()
                      if lib['serviceable'] is False}
    assert nonserviceable == {pack, 'Runner.Worker/2.337.0',
        'Runner.Common/1.0.0', 'Runner.Sdk/1.0.0', 'Sdk/1.0.0'}
    for name in nonserviceable:
        assets = target[name]
        assert len(assets.get('runtime', {})) == (162 if name == pack else 1)
        assert len(assets.get('native', {})) == (14 if name == pack else 0)
        for kind in ('runtime', 'native'):
            for asset in assets.get(kind, {}):
                assert (base / PurePosixPath(asset).name).is_file()
    for kind, count in [('runtime', runtime_count), ('native', 14)]:
        names = collections.Counter()
        for library, assets in target.items():
            for asset in assets.get(kind, {}):
                assert asset.isascii() and '\\' not in asset
                name = PurePosixPath(asset).stem
                if name.endswith('.ni'):
                    name = name[:-3]
                names[name.lower()] += 1
                if kind == 'native':
                    assert library == pack
        assert sum(names.values()) == count
        assert max(names.values()) == 1 and 'probe' not in names
    print(rid, digest, 'PASS: counts, names, ownership and local presence')
PY
```

## Command-path correspondence and what is still open

[`WorkerProbe`](https://github.com/send/shoutx/blob/9aa3887c9e5efbfa811198c8f46981e366a0640b/tests/runner-package/WorkerProbe.cs) invokes the package
OutputManager, ActionCommandManager, four target extensions, ExecutionContext
and SecretMasker. It substitutes transport/service endpoints, not those
implementations. Its fixture registers a copied encoder list, enables enhanced
annotations, supplies a synthetic repository/workspace and starts with fresh
state. Unexpected service calls fail the probe. Those are named test inputs,
not a measurement of arbitrary preceding workflow state.

### Registration and successful V2 parsing

At the pinned Runner commit
`397b032cbf865e9c3ddfab89d533ec19325e1273`,
[`HostContext`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/HostContext.cs#L103-L113)
registers the same eleven value encoders, in the same order, as the fixture.
This is registration-list correspondence, not a proof about all encoder
implementations, prior mask registrations or native dependencies.

The normal
[`ExtensionManager`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/ExtensionManager.cs)
lists all four target extension types alongside the other command extensions.
Its `Add` helper resolves the assembly-qualified type with `throwOnError`,
constructs it, checks the result, calls `Initialize`, then appends it. It does
not catch failures in those operations. On successful registry creation,
[`ActionCommandManager`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionCommandManager.cs)
records commands in an ordinal-ignore-case set and dispatch dictionary.
This source chain does not independently establish CLR assembly resolution.

In
[`TryParseV2`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/ActionCommand.cs),
the prefix, separator and command name are derived before consulting the
registered set. The set is used only for `Contains(commandName)`, not to choose
between candidate names. Conditional on the intended separator/name already
being established, that name being present in both sets with the same comparer,
and the parse completing without exception, additional unrelated registered
names do not change the returned command, properties or data. The manager's
short-circuit expression then does not invoke the legacy parser. This is a
source argument about successful V2 parsing, not a finite-test generalization.

It does not transfer malformed-input results from the reduced fixture to the
full registry: a false V2 result, including an exception caught inside the
parser, permits the legacy attempt. The arbitrary-suffix framing and resource
arguments must still establish the premises above. Nor does successful parsing
alone establish dispatch/effects: stopped-command state and the enhanced-
annotation feature gate remain relevant. The fixture explicitly enables that
feature; the normal helper reads the job variable and defaults to false when
it has no value. The existing
[annotation compatibility limitation](../commands/github-actions-annotations.md#boundary-specific-threat-analysis)
owns the feature's consequences. Do not infer a normal server input from the
fixture setting or promote fresh fixture state to arbitrary prior workflow
state. These differences remain part of the reference-path analysis.

| Difference | Evidence established here / already retained | Required continuation |
| --- | --- | --- |
| SDK muxer/hostfxr versus package apphost | Distinct versions and host modes explicitly identified; probe reports the 8.0.30 hostpolicy banner before its initialization bag, and normal package route is source-assessed | Bind hostpolicy path/bytes and relevant resolved assets/settings on normal reference route; do not substitute the SDK launcher source for the package launcher |
| Probe.dll entry and temporary cwd | [Application-base correspondence](#application-base-versus-process-working-directory) identifies the package-bin base; [selected deps](#selected-deps-assets-and-servicing) bound servicing/store selection for named assets and the native-directory contribution | Resolve other managed/native loads, different entry/TPA inputs and normal Worker startup before claiming full path equivalence |
| Explicit culture / initialized caches | Per-culture CompareInfo/backend and Worker expectations are checked; the [culture-name/cache source argument](reference-culture-cache.md) identifies distinct interop-name keys; [search-reset source evidence](reference-search-reset.md) follows selected retained-state resets | Bind effective data and remaining search-cache/settings paths; live culture propagation remains an applicability condition |
| Service doubles / limited extension list / initial state | Actual target processing/effects are exercised with finite controls | The universal framing argument must establish the intended command before dispatch; a reduced extension list cannot rule out every fallback interpretation by itself |
| Native data/search/break path | Probe observations and acquired-file inventories exist separately | Finish effective selection, source/data correspondence and arbitrary-suffix composition (R1/R3/R4) |

The **probe host-property handoff** and **probe base** are observed in the four
recorded rows; the **normal Worker base** is source-inferred. The bounded
correspondence is by directory role, not complete execution equivalence. R2 as a whole
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
from pathlib import Path, PurePosixPath, PureWindowsPath
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
    assert evidence['status'] == 'passed'
    expected_coreclr = {'linux-x64': 'libcoreclr.so', 'osx-arm64': 'libcoreclr.dylib',
                       'win-x64': 'coreclr.dll'}[selected['rid']]
    assert evidence['selectedCoreClr']['file'] == expected_coreclr
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
    clr = re.findall(r"^CoreCLR path = '(.*)', CoreCLR dir = ", text, re.M)
    assert len(clr) == 1
    path_type = PureWindowsPath if selected['rid'] == 'win-x64' else PurePosixPath
    app_base = path_type(props['APP_CONTEXT_BASE_DIRECTORY'])
    coreclr = path_type(clr[0])
    deps = props['APP_CONTEXT_DEPS_FILES'].split(';')
    assert coreclr.name == expected_coreclr
    assert all(p.isascii() for p in [props['APP_CONTEXT_BASE_DIRECTORY'], clr[0], *deps])
    actual_base = {
        'pathsAbsolute': app_base.is_absolute() and coreclr.is_absolute()
                         and all(path_type(p).is_absolute() for p in deps),
        'matchesCoreclrDirectory': app_base == coreclr.parent,
        'depsIsSingleWorkerInBase': len(deps) == 1
                         and path_type(deps[0]) == app_base / 'Runner.Worker.deps.json',
    }
    assert actual_base == selected['applicationBase']
    assert all(actual_base.values())
print(json.dumps(expected, indent=2))
PY
```

This verifies consistency with provenance-checked, hash-bound local
reports, not a signed attestation. Missing artifacts leave reproduction
unavailable; a retained hash is not a substitute for its input bytes.
