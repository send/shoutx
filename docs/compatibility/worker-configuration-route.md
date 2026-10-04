# Worker configuration inheritance investigation

Status: source route identified; no Worker startup-setting or consumer-linkage
verdict is closed by this note.

This follows the [managed reference inventory](managed-runtime-references.md)
and addresses the startup-selection gap in the
[feasibility audit](unicode-feasibility.md#startup-selection-inputs-to-resolve).
The observation contract belongs to the
[test plan](../test-plan.md#hosted-worker-startup-input-feasibility-observation).
No live schema-v3 result is claimed yet.

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

For each named key, a future `absent` result would establish only absence in
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
