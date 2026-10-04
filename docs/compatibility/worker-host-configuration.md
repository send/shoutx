# Worker host-configuration source assessment

Status: bounded source assessment; no live startup-setting or culture verdict
is closed. This follows the [startup-state investigation](worker-configuration-route.md#startup-state-source-follow-up)
and addresses its finite host/property route list under acquisition-target
check 3. The [test plan](../test-plan.md#sourceconfiguration-acquisition-target-checks)
owns the conditional claim and the [scope decision](../decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements)
owns the work order and stop rule.

Research-status update, 2026-10-05: the maintainer approved the scope decision's
research direction; the boundary remains a proposal. The live-deployment gap and request for
direction at the end of this note are historical, not a current instruction to
attest all deployed startup inputs. The source/package findings remain useful
for the reference path; additional deployment configuration is now an explicit
applicability condition. No previously unobserved input becomes observed.

The later [reference/probe correspondence](reference-worker-correspondence.md)
uses the original package reports and traces to identify the SDK-to-hostpolicy
handoff and initialization properties. It does not backfill live Worker state
or close the native selection and command-path obligations below.

## Fixed sources and existing observations

Inspected on 2026-10-04: Runner commit
`397b032cbf865e9c3ddfab89d533ec19325e1273`, .NET commit
`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f` and the three archives in
[`pins.json`](../../tests/runner-package/pins.json). Archive hashes were
rechecked before inspecting their member lists and extracted configuration.
This is local package/source inspection, not a new hosted run.

| Package RID | Host files listed under bin | Worker configuration members |
| --- | --- | --- |
| linux-x64 | Runner.Worker, libhostfxr.so, libhostpolicy.so | Runner.Worker.runtimeconfig.json; no runtimeconfig.dev.json member anywhere in archive |
| osx-arm64 | Runner.Worker, libhostfxr.dylib, libhostpolicy.dylib | Runner.Worker.runtimeconfig.json; no runtimeconfig.dev.json member anywhere in archive |
| win-x64 | Runner.Worker.exe, hostfxr.dll, hostpolicy.dll | Runner.Worker.runtimeconfig.json; no runtimeconfig.dev.json member anywhere in archive |

All three main Worker configurations have `includedFrameworks` containing
Microsoft.NETCore.App 8.0.30, no `framework`/`frameworks`, and three
configProperties: PredefinedCulturesOnly=false, MetadataUpdater.IsSupported=false
and EnableUnsafeBinaryFormatterSerialization=false under their respective
System namespaces. None contains STARTUP_HOOKS or additionalProbingPaths.
Reproduce this small inventory
with `tar -tzf` / `unzip -Z1` on the hash-verified archives and parse the named
JSON from an immutable private extract. The three Worker deps files each have a
`libraries` object, with no member key beginning
`Microsoft.NETCore.DotNetHostPolicy/`; each instead
identifies its RID-specific Microsoft.NETCore.App runtime pack at 8.0.30.
No package bytes or vendor data are
published by this note.

The [same-job evidence](worker-configuration-route.md#transport-result-run-37193467498)
matches the live Worker executable and main runtimeconfig to the corresponding
package files on all four rows. It does **not** observe live hostfxr/hostpolicy
bytes or absence of a dev sidecar. Archive member absence cannot substitute
for live file absence. Official package/source correspondence and unchanged
trusted installation remain explicit inferences, not reproducible-build or
loaded-memory attestations.

## Normal apphost route

The fixed Runner's
[JobDispatcher](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Listener/JobDispatcher.cs)
launches the bin-directory Worker executable, with that directory as cwd,
`spawnclient` followed by two pipe handles, and a null environment overlay.
It does not launch the Worker through the SDK `dotnet` command. This is the
normal source path, not an observation of the Listener's complete command line.
The existing ancestry observation identifies the Worker executable separately.

At the .NET pin, the apphost in
[corehost.cpp](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/corehost.cpp)
uses its embedded managed application name relative to its executable, resolves
that path and derives the application root. A local `strings` inspection finds
`Runner.Worker.dll` in each packaged Worker executable. That string observation
supports the expected publish binding; it is not a decoded-slot or dynamic
binding attestation. The normal binding to this DLL is part of the official
package/source-correspondence inference.

The standalone
[hostfxr resolver](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/apphost/standalone/hostfxr_resolver.cpp)
uses [fxr_resolver.cpp](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr_resolver.cpp),
which selects an application-root hostfxr if it exists before consulting
DOTNET_ROOT/global locations. The packaged host file therefore supplies a
specific expected target, conditional on the corresponding live installation.
Package-probe launcher hostfxr versions cannot be substituted for this route.
The muxer's mode detection is another conditional step: with CoreCLR in that
root, the bound Worker DLL and its deps file present there, it selects apphost
rather than legacy split_fx. Those files are in the observed nine-file set;
their startup availability uses the stated file-continuity inference.

The pinned [command-line parser](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/command_line.cpp)
stops host-option parsing at the first unknown argument. `spawnclient` is not a
known host option, so the inspected normal launch supplies no `--runtimeconfig`
or `--depsfile` override. The
[muxer](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/fx_muxer.cpp)
then derives the configuration basename from the bound application path;
[path helpers](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostmisc/utils.cpp)
add `.runtimeconfig.json` and `.runtimeconfig.dev.json`. This narrows the
normal candidate to the Worker main file and its sidecar, not every JSON file
or every SDK installation on the machine.

## Framework and host-property reductions

At this pin, [runtime_config.cpp](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/runtime_config.cpp)
sets the framework-dependent flag when parsing `framework` or `frameworks`.
Parsing `includedFrameworks` fails if that flag is already set. Consequently,
**conditional on the identified host parsing the observed main Worker file
and successfully starting the Worker**, a sidecar cannot leave a shared-
framework mode active: the main file's includedFrameworks would reject it.
This also accounts for partial sidecar processing before a non-fatal dev-parse
failure; a remaining true flag still conflicts with the main file.
It does not rule out sidecar configProperties, which are processed separately.

The muxer's normal app execution reads additional framework definitions and
DOTNET_ADDITIONAL_DEPS only in the framework-dependent branch. Under the
conditions above, those routes are not sources of extra globalization
properties. The self-contained
[hostpolicy resolver](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/fxr/standalone/hostpolicy_resolver.cpp)
normally checks servicing before its expected directory. Its version lookup
specifically searches the deps file's libraries for
`Microsoft.NETCore.DotNetHostPolicy/`. For these inspected deps files the result
is empty, making the servicing check return false. Conditional on the normal
apphost route, those unchanged deps and the app-local hostfxr root, the next
candidate is the application directory, where the package contains hostpolicy.
An empty version also prevents the later **hostpolicy-location** package-layout
probing fallback, not general dependency-asset probing. The exact
[run-37193467498 record](evidence/environment-transport-37193467498.json)
retains the deps-file match in each row's
`worker.onDiskSha256["Runner.Worker.deps.json"]` and
`manifestWorkerFiles["Runner.Worker.deps.json"]`. All four pairs are equal.
This remains a source selection inference, not proof of live hostpolicy bytes
or loaded identity.

The muxer's ordinary execute path supplies `is_sdk_command=false`. Its
additional-property vector is empty on that path; the HOSTFXR_PATH addition
belongs to the SDK branch. It calls hostpolicy's `corehost_main`, which creates
the hostpolicy context, creates CoreCLR and runs the application. The separate
hostpolicy property-setter API exists, but its existence does not add a setter
call to this inspected normal sequence.

[Hostpolicy context construction](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/hostpolicy_context.cpp)
adds named runtime/search-path properties, copies configuration properties,
and handles startup hooks plus bundle/host-contract properties. Its fixed
property additions do not independently write the System.Globalization
switches. Copying unknown configProperties and loading a startup hook are
different: they can affect the relevant state and remain unresolved inputs.
This reduction does not exclude external host APIs or instrumentation by
assertion; their relevance is assessed under the existing trusted-execution
boundary, not a new defence against hostile same-job code.

## Residual inputs and evaluated alternatives

The main file overrides a dev file only for matching keys. Its observed
PredefinedCulturesOnly=false therefore does not exclude an Invariant, UseNls,
AppLocalIcu or STARTUP_HOOKS property from an unobserved sidecar.
The dev file can also contribute `additionalProbingPaths`, which flows through
the muxer's probe paths to the
[dependency resolver](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/deps_resolver.cpp).
The lookup probes are appended after published-deps-directory probes, but this
assessment does not establish their irrelevance for all managed/native assets.
This is a remaining loader input spanning checks 3 and 4, distinct from the
hostpolicy-location version guard above.
Additional lookup probes also enable file-existence checks; their effect is
not described completely by ordering alone.

Asset-level servicing and shared stores are separate loader routes, not
disposed of by the missing HostPolicy package version or by sidecar absence.
The dependency resolver places servicing probes before published-directory
probes when its servicing directory exists, and skips them for entries not
marked serviceable. The pinned
[Unix PAL](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostmisc/pal.unix.cpp)
uses CORE_SERVICING with a fallback servicing location; the
[Windows PAL](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostmisc/pal.windows.cpp)
derives its servicing directory from the applicable Program Files location.
The [shared-store helper](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/corehost/hostpolicy/shared_store.cpp)
returns early for an empty TFM, but these main configurations specify net8.0.
It considers DOTNET_SHARED_STORE and platform/multilevel-dependent global
locations; its host-relative store branch applies only to muxer mode, not this
conditional apphost route. The resolver adds shared-store lookup probes after
the published directory. The six-key observation covers neither new environment
name. No actual store directory, serviceable replacement or relevant resolved
asset is observed by this note. Their applicability/effect on the required
assets remains a check-3/4 loader gap, not a claimed changed binary or a new
requirement to collect raw paths. An identified resolved asset could make an
unused lookup input irrelevant. The later
[selected-deps inspection](reference-worker-correspondence.md#selected-deps-assets-and-servicing)
bounds servicing/store selection for the five identified non-serviceable
libraries and the native-directory contribution. It does not resolve every
managed load, native dependency or effective ICU identity.

At this exact Unix source pin, the fallback is relative `opt/coreservicing`,
not `/opt/coreservicing`: with the normal launch cwd it is beneath bin.
Linux/macOS have no global shared-store locations in this PAL implementation;
under apphost mode their shared-store input reduces to DOTNET_SHARED_STORE.
Windows additionally considers platform global stores through the
environment-only DOTNET_MULTILEVEL_LOOKUP gate (enabled by default). That helper
does not use the separate TFM-based framework-lookup disable for .NET 7+;
net8.0 alone does not exclude Windows global stores. This third environment
gate is also outside the six observed keys. Existing servicing/shared-store
directories, as well as additional probe paths, enable resolver-wide file-
existence checks, including for the published-directory probe. These are
source qualifications, not new live directory or raw-input measurements.

Hostpolicy also reads DOTNET_STARTUP_HOOKS natively and merges it with the
STARTUP_HOOKS property. Fixed
[StartupHookProvider](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/StartupHookProvider.cs)
invokes the named hooks when supported. These ordinary configuration inputs
are not established absent by the six-key child observation or the main file.
An identified resolved outcome could make their raw values irrelevant; absence
is not the only admissible evidence. No hook is observed here and no defect is
inferred. StartupHookProvider additionally supports diagnostic-client hooks;
external diagnostic intervention and deliberately observation-defeating hooks
belong to the existing trusted-execution boundary, not a new mandatory audit
of hostile instrumentation or an added blocker for this source route.

Two non-invasive alternatives were examined:

- **Package plus updater source.** Pinned
  [SelfUpdater](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Listener/SelfUpdater.cs)
  cleans the extraction directory, but creates the versioned destination with
  CreateDirectory and copies into it. Those statements alone do not prove a
  previously empty destination or exclude an added sidecar in a hosted install.
  Archive absence is useful expected-layout evidence, not live absence.
- **Public image construction source.** A bounded textual search of official
  runner-images commit `6d942e630479cd99a93dadfc766af11242bfa402` for
  DOTNET_STARTUP_HOOKS, STARTUP_HOOKS, runtimeconfig.dev, Runner.Listener,
  Runner.Worker, actions/runner/releases and actions-runner- found no matching
  non-Markdown source. The only Markdown match was an image-alt-text substring.
  This is an exact-string search of that snapshot, not proof that no deployment
  mechanism exists. The [README](https://github.com/actions/runner-images/blob/6d942e630479cd99a93dadfc766af11242bfa402/README.md)
  describes VM-image construction; it does not attest these jobs' startup
  inputs. This current snapshot is not relabelled the historical image source.
  Provenance is an author retrieval through GitHub's
  `repos/actions/runner-images/tarball/6d942e630479cd99a93dadfc766af11242bfa402`
  API path, not metadata inside the extracted directory. The downloaded
  archive's SHA-256 was
  `bd35bdc3f55d7472e100fb7736ec75d04bec73562adb097e5fccd0a42aa5d9b9`.
  A future generated tarball need not have identical bytes; the commit pins
  source content. This is not a signed deployment attestation.

The remaining check-3 gap is now specific: justify the actual app-local host
files and property/lookup sources, especially ordinary sidecar and startup-hook effects, or
establish a resolved outcome that makes them irrelevant. The ordinary source
path and default package layout narrow the possibilities but do not establish
the remaining premises. Neither a lack of textual setter hits nor more passing
Unicode samples resolves them.

Historical disposition (before the 2026-10-05 revision): the remaining gap
was submitted for maintainer direction under the
[existing stop rule](../decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements),
whose superseded version is preserved in that decision. At that time, a justified
deployment/configuration argument or a bounded observation of named inputs/outcomes
were candidate alternative routes, not permission to extend the collector
automatically. No scope revision was proposed in that source assessment.
A sidecar-presence or host-file check would
address only those particular inputs; it would not establish all historical
startup-hook behaviour or complete consumer linkage. No such new observation
is implemented here. Native/locale selection and effective data also remain
open. Both cultures on all four rows remain unverified; this is not a negative
proof of Unicode feasibility, an adoption verdict, or research completion.
Current work follows the [claim inventory](unicode-feasibility.md#claim-inventory).
