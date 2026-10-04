# Worker configuration inheritance investigation

Status: same-job child observations retained and source route partially assessed;
no Worker startup-setting or consumer-linkage verdict is closed by this note.

This follows the [managed reference inventory](managed-runtime-references.md)
and addresses the startup-selection gap in the
[feasibility audit](unicode-feasibility.md#startup-selection-inputs-to-resolve).
The observation contract belongs to the
[test plan](../test-plan.md#hosted-worker-startup-input-feasibility-observation).
The first same-job schema-v3 results are retained below. They do not change
the status of the consumer-linkage argument.

## Fixed-source evidence

At the package-corresponding .NET 8.0.30 commit
`a83db3e0eb2defb6220e15dae2f1a0462fdbf99f`,
[ProcessStartInfo.Environment](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Diagnostics.Process/src/System/Diagnostics/ProcessStartInfo.cs)
initializes its dictionary from the current process environment. Its comparer
is ordinal-ignore-case on Windows and ordinal on Unix. This is inheritance of
the managed view at child construction, not recovery of startup/native state.
In fixed [Environment.Variables.Unix](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Environment.Variables.Unix.cs),
GetEnvironmentVariables initializes/reads a managed cache. Managed setters
update that cache, not native `environ`; a managed single-variable getter uses
native GetEnv only while the cache is uninitialized. The two views can diverge.
For Unix, any transfer from the child to the parent's managed view therefore
does **not** establish the input seen by native getenv consumers. In particular,
the shim's version override and ICU's data selection require an independent
native-environment/source argument. Even managed startup reads must be tied
to their time and cache state, not just the later snapshot.
The relationship to Windows native getenv consumers is likewise unestablished;
the Unix analysis does not imply a Windows child-to-native equivalence.
The fixed [native shim](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/native/libs/System.Globalization.Native/pal_icushim.c)
uses native `getenv` for `CLR_ICU_VERSION_OVERRIDE` in its applicable load route.
As one target-generation example,
[ICU 74.2 putil.cpp](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/common/putil.cpp)
has a native `ICU_DATA` getenv branch conditional on build/platform flags. This
does not establish that branch's availability or execution in a hosted build.

In the pinned Runner commit
`397b032cbf865e9c3ddfab89d533ec19325e1273`,
[ProcessInvoker](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Sdk/ProcessInvoker.cs)
overlays the supplied environment on that dictionary, sets `GITHUB_ACTIONS`,
and conditionally sets `CI`. It does not clear the inherited dictionary in
this path. Windows truncates supplied keys/values at NUL before assignment.
The preceding
[ScriptHandler](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/ScriptHandler.cs)
adds PATH and runtime context values and may select a macOS Node wrapper when
`DYLD_INSERT_LIBRARIES` is supplied. Job/step environment evaluation, context
exports and wrappers therefore belong in any inference about inheritance.

The schema-v3 observer uses a custom `python -I -S` shell command, following
Python's documented [isolation](https://docs.python.org/3/using/cmdline.html#cmdoption-I)
and [site suppression](https://docs.python.org/3/using/cmdline.html#cmdoption-S).
The Runner is asked to launch Python directly, rather than an intermediate
Bash; no Python site initialization is requested. The prior explicit Bash
route already requested `--noprofile --norc` in the pinned helper. Resolving
`python` to an interpreter rather than an external wrapper is not established
by the shell string alone.
The pinned [ScriptHandlerHelpers](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/ScriptHandlerHelpers.cs)
splits a custom shell into command and argument format and maps `python` to
`.py`. ScriptHandler resolves the command, substitutes the temporary script
path and writes the script; Windows normalizes CRLF and normally uses UTF-8
without BOM (a retain-default-encoding feature can alter that). The inline
script is ASCII. Actual interpreter resolution/execution remains a hosted-run
check, not a conclusion from a local Python invocation.
It does not deliberately clear configuration keys. This reduces one source of
child-side transformation; it is not proof of an unchanged parent environment
or of arbitrary loader/runtime behaviour. The Python executable and OS remain
part of the existing trusted execution environment.

## What a child presence observation could establish

For each named key, an `absent` result establishes only absence in
that observer's environment mapping. To infer absence in the Worker's managed
view at child construction, the identified
route also needs to account for overrides/removals before and during launch.
To carry that conclusion back to startup, it additionally needs the relevant
parent mutation and (on Unix) cache analysis. This does not infer native getenv
state. A defined key, including an empty-valued key, gives
no value or mode inference. No value is preserved to resolve such a case.

The [inventory's source examples](managed-runtime-references.md#selected-references-and-interpretation)
narrow relevant environment/AppContext mutation sites, but are not yet an
exhaustive call-context argument. Host runtimeconfig precedence and AppContext
selection remain separate from environment presence. ICU data and native
loader selection also require their fixed-source and same-image connection;
these six keys are not an exhaustive loader-configuration inventory.
The pinned Listener's
[Program](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Listener/Program.cs)
also loads a root `.env` file into its environment; that is a Listener path,
not evidence of a Worker-time setter. Earlier action exports and server/job
inputs still need assessment before carrying any observation back to startup.

Thus this bounded child observation can distinguish a potentially usable
absence argument from a remaining defined/unknown input without inspecting a
parent environment or publishing arbitrary values. It does not supply a new
consumer-state oracle. Historical observations are not retroactively assigned
schema-v3 measurements; a new run must retain its own identities. Neither
Invariant nor `en-US` in any row becomes verified through this addition alone.

## Same-job result, run 37190267207

The [retained projection](evidence/hosted-child-configuration-37190267207.json)
records [run 37190267207](https://github.com/send/shoutx/actions/runs/37190267207),
attempt 1, source head `290e1820544cbaa69192c6ce20b30e9b14a4c76d`, tested merge
`06923b5ed9cdf9cd7e1413dc46f8a0593aeb0188`. All four jobs and the hosted-annotation
verifier succeeded. These are new observations, not inferred updates to the
earlier run's reports.

| Selector | Job ID | Resolved image version | Six child keys | Package ICU, both explicit cultures |
| --- | --- | --- | --- | --- |
| ubuntu-22.04 | 111400797815 | ubuntu22 / 20260927.309.1 | all absent | 70.1.0.0 |
| ubuntu-24.04 | 111400797829 | ubuntu24 / 20260927.320.1 | all absent | 74.2.0.0 |
| macos-15 | 111400797837 | macos15 / 20260907.0337.1 | all absent | 76.1.0.0 |
| windows-latest | 111400797833 | win25-vs2026 / 20260925.250.1 | all absent | 72.1.0.4 |

Each child projection has `observed-child-environment`, not `unavailable`.
Worker/module identities agree in full, and available boundary identity fields
agree with the Worker report; the boundary report names the corresponding job
ID. Package evidence agrees on run ID, tested SHA, RID and image; its probe and
manifest are correlated by the same named run artifact, not independent run
identity fields within those files. Live
Runner version is 2.337.0 in every row; all nine named on-disk Worker files
match that job's package manifest. The package archive identities match the
pinned baseline. Each live row passed eight mask and thirty annotation cases.
These are finite effects and identity correlations, not Unicode safety proof.
`identity` comes from the Worker observer; the other source identities and
author-derived agreement checks are retained separately. Architecture labels
are compared after uppercasing (`Arm64` versus `ARM64`), not byte-identically.
Both sides of the nine-file digest comparison are retained; the match flag is
an author-derived result, not a field emitted by the observer.

Startup names remain empty on Linux and `en-US` on macOS/Windows; the matched
job message has no `system.culture` in all four rows. The module reports again
observe Linux CoreCLR and ICU common/international/data files, Windows CoreCLR
and `icu.dll`, and only CoreCLR on macOS. The record preserves the names,
digests and distinct mapped-file identity statuses. No active native binding
or effective data is inferred from module presence. The macOS ICU observation
gap is not turned into a missing-library or non-ICU conclusion.
The macOS check-run annotations API returned 31 entries: the 30 tested
annotations and one `.github`/empty-title service notice about ARM64 queue
capacity. That extra notice was rechecked for this run and explains the
different annotation-list digest; it is not an additional tested command.

The observer step's resolved shell lines, read from those job logs, were
`/usr/bin/python -I -S {0}` on both Linux rows,
`/Library/Frameworks/Python.framework/Versions/Current/bin/python -I -S {0}`
on macOS and
`C:\hostedtoolcache\windows\Python\3.12.10\x64\python.EXE -I -S {0}` on
Windows. This records named launcher resolution and successful execution, not
a separate binary-content attestation. No full job logs or environment values
are retained here.

## Normal overlay preservation and remaining connection

The pinned Runner's
[JobExtension](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/JobExtension.cs)
and [StepsRunner](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/StepsRunner.cs)
normalize evaluated job/step environment nulls to empty strings.
[FileCommandManager](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/FileCommandManager.cs)'s
similarly named `SetEnvironmentVariable` helper writes the deferred/global
step-environment dictionaries and context; it is not a call to
`System.Environment.SetEnvironmentVariable`. Thus a normal `GITHUB_ENV`
export is a subsequent-child overlay, not itself a Worker environment setter.

At the next transport boundary, fixed .NET
[Process.Unix.CreateEnvp](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Diagnostics.Process/src/System/Diagnostics/Process.Unix.cs)
and [Process.Windows.GetEnvironmentVariablesBlock](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Diagnostics.Process/src/System/Diagnostics/Process.Windows.cs)
serialize every entry already in `StartInfo.Environment` as a key/value entry.
At this exact runtime commit, both empty and null values produce `KEY=`; neither
function skips such entries. This conclusion is runtime-pin-specific, not a
claim for later .NET versions. Together with the inspected ProcessInvoker
assignments for the six ASCII keys, this rules out **an empty/null value
deleting an assigned key at that serialization boundary**. It is a source-level statement at that boundary, not
measurement of every intermediate process or recovery of Worker startup state.

The intervening copy site is
[ActionRunner](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionRunner.cs):
it iterates the platform-specific `env` context, assigning each key's string
value to the handler dictionary with `VarUtil.EnvironmentVariableKeyComparer`.
[HandlerFactory](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/HandlerFactory.cs)
passes that dictionary to the handler. The inspected ScriptHandler and
ProcessInvoker paths add/assign entries rather than remove inherited keys;
the Windows skip/truncation rules above are not a general arbitrary-key
preservation claim. This names the inspected path, not an exhaustive absence
of filtering in every possible launcher or dependency.

The inventory's identified direct Worker/SDK process setters write the tracking
ID and proxy keys, not these six selectors. Its Azure.Core example writes a
different AppContext data key. This narrows ordinary managed mutation inspection
under the existing trusted-Runner/source-correspondence assumptions; it is not
an exhaustive intramodule/native mutation census. No new defence against
hostile same-job code or loaded-memory measurement is required by this note.

Mapping this run to the test plan's
[acquisition-target checks](../test-plan.md#sourceconfiguration-acquisition-target-checks):

- **Observed, supporting check 1:** absence in the four observer environments, matching same-job
  package/live identities and the recorded startup/job culture information.
- **Source-supported portion of check 3:** serialization preserves assigned
  keys even for empty/null values; the inspected direct managed setters concern
  other keys.
- **Unclosed portions of checks 3–4 in this run:** transfer through the actual
  launch path, including removal/filtering beyond the inspected paths and the
  observer reporting an inherited empty-valued entry as `defined` on each
  platform. The fixtures at that run did not execute the .NET-to-Python
  empty-entry path; the subsequent control below tests its SDK-to-Python suffix.
  Relevant managed-cache/startup timing, AppContext
  effective settings, and each platform's native/locale selection outcome
  also remain unclosed.
  Native getenv and ICU data selection are not established by this child view.

Both culture verdicts in every row remain unverified. Subsequent work follows
the scope decision's [ordering and stop rule](../decisions/github-actions-unicode-scope.md#consequences-and-verification-requirements),
not a new completion gate in this note.
This input-focused assessment does not discharge check 2's separate
culture/execution-context obligations.

## Transport result, run 37193467498

The [retained transport projection](evidence/environment-transport-37193467498.json)
records [run 37193467498](https://github.com/send/shoutx/actions/runs/37193467498),
attempt 1, PR #82 head `fa2773104ddca446b565b894a35ce4a2c199c699`, tested merge
`3c9d55c1b97fc9a91efbb54a2726684547acc372`. All four package jobs and their
independent Python control steps succeeded. The
[test plan](../test-plan.md#package-environment-transport-control) owns the
experiment's cases, isolation, failure handling and limits.

| Selector | Job ID | Image version | Python | Transport cases |
| --- | --- | --- | --- | --- |
| ubuntu-22.04 | 111410356771 | ubuntu22 / 20260927.309.1 | 3.10.12 | all four passed |
| ubuntu-24.04 | 111410356782 | ubuntu24 / 20260927.320.1 | 3.12.3 | all four passed |
| macos-15 | 111410356770 | macos15 / 20260907.0337.1 | 3.14.7 | all four passed |
| windows-latest | 111410356743 | win25-vs2026 / 20260925.250.1 | 3.12.10 | all four passed |

For every row, all six keys were `absent` in the absent control and `defined`
in the empty, null and text controls. Synthetic-value comparisons and the
separate parent **managed-environment** marker matched in every case. Thus the
tested empty/null entries survive this package SDK-to-Python path, including
Windows CPython; this is no longer merely a serializer-source prediction.
It is not an experiment in a registered Worker, nor is transport separately
repeated under both comparison cultures. No culture linkage is inferred from it.

All package probes report .NET 8.0.30, SDK 8.0.424 and the pinned archives.
The retained CoreLib, Runner.Sdk and System.Diagnostics.Process identities
match their package manifest entries, and CoreCLR selection is separately
retained from the harness. Each report has `preTransportEvidenceVerified=true`;
that records earlier suite verification, not a stronger transport/consumer
claim. The original reports were also rechecked with the repository's managed
identity and completion validators, not accepted merely from a green job.

Separately, each same-job Worker child observer again reports all six keys
absent. Its run, attempt, SHA, matrix RID and resolved image correlate with
the package job (including matrix OS, which separates the two linux-x64 rows).
The job-number association is by artifact name and matrix fields, not a numeric
job ID inside the Worker report. All nine observed on-disk Worker files match the package
manifest. Both sides of the digest comparisons are retained. These are
author-derived correlations, not a new observer measurement. In particular,
System.Diagnostics.Process.dll is hash-identified in the **package** probe,
not added to the nine-file live Worker observation by this record.
The startup names and absent job culture input are preserved independently,
without upgrading them to processing-thread or native-setting observations.

The record also distinguishes the two Python launchers. The package harness
supplies `sys.executable` as the fourth application argument; this is visible
in the hash-checked CoreHost trace. The observer's logged shell line comes from
this run's job logs, transcribed independently of the earlier run. It is
ScriptHandler's display-side resolution; RunAsync resolves the command again.
Equality with that launch-side resolution is a source inference using the same
shell/prepend-path inputs and unchanged PATH/files within the step:

| Row | Package Python argument | Observer logged shell command |
| --- | --- | --- |
| Both Ubuntu rows | `/usr/bin/python` | `/usr/bin/python -I -S {0}` |
| macos-15 | `/Library/Frameworks/Python.framework/Versions/3.14/bin/python` | `/Library/Frameworks/Python.framework/Versions/Current/bin/python -I -S {0}` |
| windows-latest | `C:\hostedtoolcache\windows\Python\3.12.10\x64\python.exe` | `C:\hostedtoolcache\windows\Python\3.12.10\x64\python.EXE -I -S {0}` |

Linux paths match exactly; Windows differs only in ASCII filename case. Treating
the Windows paths as the same executable uses the trusted hosted tool-cache's
normal case-insensitive path resolution. These are named-path observations,
not binary-content attestation; unchanged interpreter/stdlib files during the
job remain a file-continuity assumption. The macOS `Current` link was not
resolved here and is not declared identical. Package-side Python versions in
the table are not a separately measured observer version.

### Direct-launch preservation inference

The fixed-source argument can now distinguish two boundaries. At SDK child
construction, ProcessStartInfo copies the current managed environment and
the SDK invoker only assigns overlay entries. Assignment can change a value,
including to null/empty, but at this runtime pin does not remove one of the
six literal ASCII keys from the serialized child environment. The successful
controls above check the observer's presence function under the package step's
interpreter, not independently every live interpreter. This is a
key-preservation argument, not value equality.

Copying an **inherited empty-valued** entry is a fixed-source premise, not a
measured case: the experiment inherits a non-empty marker and assigns empty/null
values only to child overlays. At the pinned .NET commit,
[Unix GetEnvironmentVariables](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Environment.Variables.Unix.cs)
and [Windows GetEnvironmentVariables](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Environment.Variables.Windows.cs)
retain a valid `KEY=` entry with an empty value, and ProcessStartInfo copies it
without value filtering. This yields the same dictionary state tested by an
empty overlay. The process-level
[Environment.SetEnvironmentVariable](https://github.com/dotnet/runtime/blob/a83db3e0eb2defb6220e15dae2f1a0462fdbf99f/src/libraries/System.Private.CoreLib/src/System/Environment.cs)
API instead normalizes an empty input to null at this pin; it must not be
confused with assignment to the child's dictionary.

For the preceding non-container route, fixed
[DefaultStepHost](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/StepHost.cs)
passes the environment dictionary to the
[Common invoker](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/ProcessInvoker.cs),
which forwards it to the SDK invoker without filtering. Crucially, that
dictionary is an **overlay**, separate from inherited StartInfo.Environment.
Even removing a key from the overlay cannot delete an inherited entry; deletion
would require a parent-side unset or removal from StartInfo.Environment.
The inspected SDK uses only assignments there. The distinct
[NodeScriptActionHandler](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/NodeScriptActionHandler.cs)
removes `NODE_ICU_DATA` from its overlay, not one of these six inherited keys;
that is not a counterexample. ScriptHandler's
[Handler](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/Handlers/Handler.cs)
PATH helper changes PATH; the fixed
[RunnerContext](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/RunnerContext.cs)
and [GitHubContext](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/GitHubContext.cs)
exports use RUNNER_/GITHUB_ prefixes. Normal job/step overlays need not equal
the parent's values for this one-way presence argument to hold.

Consequently, **conditional on the identified direct-launch implementation,
trusted interpreter/OS, the named-interpreter correspondence above,
package/source correspondence and file continuity**, an
absent key in the observer supports absence in the parent's managed snapshot
used for that launch. This applies to the non-container direct Python route
selected by the workflow's Linux and Windows observer steps. It is an inference
from source and observations, not a read of the Worker's environment. It does
not recover an earlier snapshot, initial native `environ`, an AppContext value,
or an ICU loader result. A present child key would not prove parent presence,
since an overlay can introduce it. This supplies a conditional launch-time
managed-view input for acquisition-target check 3 on these platforms, not a
startup-selection outcome; check 4's native/locale route remains untouched.
Neither culture verdict is closed.

Here the trusted-installation correspondence also covers unobserved live
runtime files, notably System.Diagnostics.Process.dll and the Unix native
process-spawn library; their live bytes are not measured by this record.
On Unix, the launch-time managed snapshot comes from its managed cache. On
Windows, enumeration re-reads the Win32 process environment block without such
a cache; that does not establish a Windows CRT getenv consumer's view.
The live observer's `main` passes `os.environ` directly to the same presence
function before its diagnostic collection, without filtering those keys.

The macOS optional wrapper must not be silently treated as a direct launch.
The pinned [macos-run-invoker.js](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Misc/layoutbin/macos-run-invoker.js)
calls Node `spawn` without an environment override. The internal selection in
[NodeUtil](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Common/Util/NodeUtil.cs)
permits only node20; [externals.sh](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Misc/externals.sh)
pins 20.20.2. In that official Node source
[child_process.js](https://github.com/nodejs/node/blob/3626fea570e44896ad99aaf3bf6e59def5adede5/lib/child_process.js),
the default is process.env and defined values, including empty strings, are
included in envPairs. This narrows the wrapper assessment but does not establish
its activation, complete native enumeration/startup behaviour or executed Node
identity in this run. The package transport experiment does not execute it.
The macOS wrapper question therefore remains separate; no matrix row is dropped.

### Reproducing the transport projection

Download each named package artifact and Worker input artifact from run
37193467498. The projection records raw SHA-256 for evidence.json, probe.json, corehost.log,
package-bin-sha256.json and hosted-worker-evidence.json. Verify these before
repeating the identity, file and exact transport-case checks above. The run/job
metadata and three step outcomes (package test, Python control, Worker observer)
are retained from the Actions APIs; run `updated_at` is not a job completion
timestamp. The shell commands are author transcriptions of selected job-log
lines, not independently hashed full-job-log evidence. `probeSha256` hashes
Probe.dll, not probe.json.

PR #82's durable merged source is `c3d33e3d236bf6b5bf5f6cfb494bd0a552febec5`.
The retained source digests match those source bytes on Linux/macOS. On Windows,
14 files match after LF-to-CRLF conversion; unicode-candidate.json remains
byte-identical LF, consistent with its explicit `.gitattributes` rule. Both
raw digest forms are retained: this is a checked conversion relation, not an
assertion that the platform files have identical bytes. The runner-side Git
setting responsible for CRLF was not observed, and a fresh checkout may use a
different form. The pins digest is author-computed from the merged LF repository
file, not emitted by the run as a digest of its checked-out pins file. No source
hash is a loaded-memory attestation.

This minimal author-checked record retains transport results and selected
identities, not all earlier collation results or a full report archive. The
original artifacts have 30-day retention. Their digests cannot recover expired
bytes or recreate the historical hosted image; fresh reproduction has new
run/image identities. The named pinned packages and source commit support
rerunning the experiment. No vendor payload or mapping table is published.
Native/startup settings and effective per-culture inputs remain subject to the
existing acquisition-target checks and stop rule.

## Reproducing run 37190267207

Each row records raw-byte SHA-256, artifact name and relative file path for six
inputs: Worker observation, package evidence, package probe, package manifest,
module observation and live boundary report. Download those named artifacts
from run 37190267207 to a new private directory and compare each digest before
repeating the identity checks described above. For the file comparison, each
`worker.onDiskSha256` entry must equal the same filename's value in
`package-bin-sha256.json`; missing entries are not matches. Compare archive
size/digest to `tests/runner-package/pins.json`. Preserve each explicit culture's
probe result independently; neither a startup name nor one culture's result
substitutes for the other.

The producing change is PR #80. The record includes observer/workflow SHA-256
from the tested merge tree, verified equal to the same two files at the PR head and durable merged
commit `1edf17c483890d4ebb7fbee2b284422061784c79`. The tested merge object was
retrievable by SHA at review time but is not assumed permanently reachable.
Use the recorded merged source and byte hashes if an ephemeral PR ref expires;
that recovers source, not an expired historical hosted environment.
These are child-observer/workflow hashes, not a digest inventory of every
evidence producer (for example the module observer).

Job IDs/times/attempts and the successful verifier job are from the Actions
run/jobs APIs. `updatedAt` is the run API's update timestamp, not a claimed
job-completion timestamp. The shell lines above are author transcriptions from
those jobs' logs, retained separately from the hashed reports; there is no
new independently hashed shell-line artifact. Artifacts have 30-day retention;
job-log retention was not measured separately. The projection is author-checked,
not signed or a full original report archive. Hashes do not recover expired
sources. It preserves observed fields and separately labelled author-derived matches,
but independently rechecking the historical source reports requires those
reports. A fresh execution has new run/image identities and is not a recreation
of an unavailable historical image. No vendor payload or full log publication
is part of this record.
