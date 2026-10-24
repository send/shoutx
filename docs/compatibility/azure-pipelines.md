# Azure Pipelines verification record

This file records evidence, not input rules. See the
[command contract](../commands/azure-pipelines.md) and
[design profile](../design.md#azure-pipelines-profile).

## Source baseline

Inspected on 2026-10-20: Azure Pipelines Agent **v5.280.0**, commit
`efa064fee06c75b31cabc0451857ad1e294649c7`.

- [Command parser](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Microsoft.VisualStudio.Services.Agent/Command.cs):
  prefix lookup is Ordinal, the closing bracket/space are character searches,
  and properties are split on ASCII semicolon and the first equals sign before
  unescaping. The decoded body is not recursively parsed by this method.
- [Converter](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/CommandStringConvertor.cs):
  structural escapes decode before `%AZP25`.
- [Worker dispatcher](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/WorkerCommandManager.cs)
  obtains percent-decoding configuration from the consumer context.
- [Knobs](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/Knob/AgentKnobs.cs):
  `DecodePercents` defaults to true, with runtime/environment overrides.
- [Task handlers](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/TaskCommandExtension.cs)
  apply variable restrictions and issue formatting after parsing.

These observations justify bounded command-framing work, not an audit of
Agent, .NET or Unicode internals. GitHub-specific start restrictions are not
transferred to this protocol.

## PATH source observations

Inspected on 2026-10-24 at the source pin above:

- [`TaskPrepandPathCommand`](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/TaskCommandExtension.cs#L852-L874)
  calls `CheckSettableVariable` for `Constants.PathVariable`, requires nonempty
  data without trimming, removes a
  current-culture-equal earlier entry and appends the value.
- The [native handler](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/Handlers/Handler.cs#L269-L304)
  reverses the prepend list and joins it with `Path.PathSeparator` before
  invoking `PathUtil.PrependPath`.
- [`PathUtil.PrependPath`](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/Util/PathUtil.cs#L19-L38)
  returns the incoming string if the old PATH is empty, otherwise joins with
  the native separator. If the old PATH already starts with the incoming
  prefix plus separator under `IOUtil.FilePathStringComparison`, it keeps the
  old PATH (including its spelling). It does not trim, unquote or resolve paths.

These are source observations, not a PATH acceptance
contract or hosted verification. The pin does not establish that later hosted
Agents match it. PATH-specific hosted observations are recorded below.

## Secret source observations

Inspected on 2026-10-24 at the same pinned Agent commit; these observations
inform the [accepted secret boundary](../decisions/azure-secret-boundary.md).
They do not establish hosted secrecy for the newly implemented command.

- [Task command handlers](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/TaskCommandExtension.cs)
  send decoded `task.setsecret` data to `TaskCommandHelper.AddSecret`, which
  ignores empty input and calls the host masker for nonempty data. The
  `task.setvariable` secret branch is different: it checks multiline input
  against `Environment.NewLine` and a knob, registers escaped command data,
  and later applies variable restrictions and assignment.
- [LoggedSecretMasker](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/SecretMasking/LoggedSecretMasker.cs)
  delegates value registration without logging the value. Its `MinSecretLength`
  setter caps a requested threshold at 6. This is a wrapper observation, not
  evidence of the active job threshold, underlying length semantics or hosted
  acceptance of every six-scalar value.
- [AgentKnobs](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/Knob/AgentKnobs.cs)
  defines `MaskedSecretMinLength` from runtime/environment
  `AZP_IGNORE_SECRETS_SHORTER_THAN`, with built-in default `0`.
  `ExecutionContext.InitializeJob` assigns this setting to the wrapper and
  removes short entries. This disproves an inference that six is the default
  minimum. The live job's selected value was not measured here.
  [Upstream masker tests](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Test/L0/SecretMaskerTests/SecretMaskerL0.cs)
  specify `***` for registered short strings and spaces, and show configured
  threshold removal. They are source expectations for backend fixtures, not
  tests executed by this investigation. The top-level helper checks null/empty,
  not null/whitespace; a universal whitespace rejection is not established.
  The same upstream test fixture has both legacy and OSS subclasses. Its
  `MinLengthSetThroughProperty`/`MinLengthSetThroughConstructor` tests set a
  threshold before `AddValue` and expect shorter values to remain visible;
  this is not merely an initialization-time removal expectation. It remains
  source evidence, not an executed backend or hosted result.
  [CompositeKnobSource](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/Knob/CompositeKnobSource.cs)
  chooses the first non-null source in declared order: this knob lists runtime,
  environment, then default. `RuntimeKnobSource` reads the execution context's
  variables; `ExecutionContext.GetVariableValueOrDefault` reads `Variables`.
  Thus an explicit nonempty job variable `'0'` precedes the Agent environment
  in this source path. This knob contract is source-derived here, not claimed
  as an independently documented stable public interface or a live observation.
- [HostContext](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Microsoft.VisualStudio.Services.Agent/HostContext.cs)
  selects legacy or OSS masker via a knob and installs JSON-string, URI-data
  and backslash encoders. No general promise about arbitrary transformed
  representations follows from that list. The adapters delegate registration
  and redaction to their respective libraries; neither backend was executed
  during this inspection and the hosted backend remains unobserved.
  The pinned [OSS adapter](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/SecretMasking/OssSecretMasker.cs)
  passes `defaultRegexRedactionToken: "***"`, delegates `AddValue` and the
  minimum-length property, and documents immediate threshold behavior rather
  than an explicit removal call. Regex-token configuration alone is not proof
  of literal-value redaction; the shared upstream tests supply that expectation.
- [ExecutionContext.Write](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/ExecutionContext.cs)
  normally calls the host masker before writing log messages, with an explicit
  `canMaskSecrets` bypass parameter. The
  [process handler](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/Handlers/ProcessHandler/ProcessHandler.cs)
  tries command processing before ordinary line output. This is a source
  route example, not a measurement of every task host or log destination.
- [WorkerCommandManager](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/WorkerCommandManager.cs)
  returns false on parse failure and has warning/error paths containing command
  input. Its processed-command debug message is in `finally`, after the handler
  attempt, and unescapes the input. This bounded inspection does not show a
  blanket setsecret echo-suppression rule or prove every task host's behavior;
  it motivates registration-step log checks and the proposal's debug-off
  precondition, not a claim of a newly reproduced vulnerability.

The [official logging-command documentation](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops#setsecret-register-a-value-as-a-secret)
describes job-duration registration and subsequent masking, excludes previous
occurrences, and recommends registering transformed values explicitly. Its
general guidance distinguishes complete secrets from fragments and warns
against argv transport. No synthetic secret experiment has yet been run for
this design; the finite proposed tests own the remaining measurements.

## Verification status

Local checks on macOS arm64, 2026-10-20:

- Cargo default-feature-free all-target tests, including the five Azure CLI
  contract tests, and Clippy with warnings denied: passed.
- [Source-parser harness](../../tests/azure-oracle/README.md), .NET SDK
  8.0.425: 665 successful records and five negative controls passed.
- GPT-6 Sol read-only implementation/contract review: no actionable findings.
- Follow-up GPT-6 Sol review of hosted-fixture, token handling, CI wiring and
  documentation: no actionable findings; two offline hosted-verifier tests passed.

The source-component harness is added to the existing four-OS GitHub CI
differential job. CI results must be checked at the final PR head; merely
configuring it is not cross-platform evidence. The local .NET 8 harness does
not execute the full v5.280.0 Agent runtime or task handlers.

## Hosted observations

On 2026-10-21, [run 3](https://dev.azure.com/kazjuly7/shoutx/_build/results?buildId=3)
passed every step in both jobs at source
`3a506e13b96403b88c8c0d16bf8472dc58ddd83b` (PR #138, subsequently merged).
Both job attempts were 1, using Agent 5.280.0, X64:

| Job | Image | Image version |
| --- | --- | --- |
| Linux | ubuntu24 | 20261012.334.1 |
| Windows | win25 | 20261013.288.2 |

The [manual hosted fixture](../../tests/azure-hosted/README.md) verified exact
next-step multiline/Unicode variable values, named-step output mapping,
read-only registration's initial value, and absence of an injected sentinel
variable. Timeline verification confirmed exactly one requested warning and
one requested error per job, including their type, message, code and counts.
The issue samples include leading combining/default-ignorable characters,
Thai/Japanese/emoji, literal `%0A`, delimiters and a newline.

Run 1 exposed a test-harness bug handling the root timeline's null `parentId`;
run 2 was canceled. PR #138 added null-parent regression coverage. Neither run
is counted as a successful hosted gate. Run 3 used the corrected verifier.

On the same date, [run 4](https://dev.azure.com/kazjuly7/shoutx/_build/results?buildId=4)
passed all steps at source `54ab91f0e439ec24b95fc692b8a87f7aadf6b633`.
Both job attempts were 1 with the same Agent/architecture/image identities as
run 3. In addition to repeating the existing checks, it supplied the absolute
checkout path of the real `README.md` with line 1, column 3 for both severities.
Azure's timeline recorded `sourcepath=README.md`, `linenumber=1`,
`columnnumber=3`, category `Code`, and the expected severity/code. Its message
was `README.md(1,3): warning SHOUTX_LOCATION: shoutx location smoke` (or `error`).
The verifier requires these exact observations and the requested issue counts;
it does not accept producer success as evidence of a consumer effect.
The Azure run Summary UI was inspected on 2026-10-21: both the Errors and
Warnings tabs displayed the corresponding `README.md(1,3)` message for Linux
and Windows. This confirms visible file/line/column text, not clickable source
navigation or pixel-identical formatting of arbitrary messages.

Read-only overwrite enforcement
and downstream job/stage mappings are not exercised by this fixture; they
remain Azure/caller semantics rather than producer framing guarantees.
No result here extends the design profile to self-hosted agents, containers,
classic release pipelines or percent-decoding-disabled configurations.

## PATH hosted observations

On 2026-10-24 JST, [run 7](https://dev.azure.com/kazjuly7/shoutx/_build/results?buildId=7)
completed successfully at `876d2b364590c8e74664fd27de2ac548c362eb36`, pipeline 1,
both job attempts 1. The same reviewed writer was used on both native hosts.

| Job | Job ID | Agent / architecture | Image | PATH entries before / after |
| --- | --- | --- | --- | --- |
| Linux | `0da5d1d9-276d-5173-c4c4-9d4d4ed14fdb` | 5.280.0 / X64 | ubuntu24 `20261012.334.1` | 16 / 19 |
| Windows | `2d2b3007-3c5c-5840-9bb0-2b1ea49925f3` | 5.280.0 / X64 | win25 `20261021.299.1` | 74 / 77 |

Both jobs passed exact next-task PATH comparison against the expected prefix
and saved original tail, one occurrence of each fixture entry after repeated
registration, ordering of distinct ASCII directories, and discovery/execution
of the caller-owned native probe from the Unicode/literal-escape directory.
PATH verification logs are 13 (Linux) and 29 (Windows); identity and existing
variable/issue verification logs are 17 and 33. All verification steps and
both complete jobs succeeded, not merely the command-emitting steps. Actual
Agent culture/backend remain unobserved. These finite cases do not establish
portable duplicate identity or applicability outside the design profile.

Runs 5 and 6 failed the initial PATH fixture: the measured shell-child PATH
included shell-startup changes, so it was not the Agent-only baseline the test
expected. No passing PATH evidence is claimed from them. Run 7 captures and
verifies the baseline using direct `PythonScript@0` tasks while retaining
Bash/PowerShell command emission. The verifier still requires exact equality;
it does not ignore or whitelist unexpected entries.

Local macOS arm64 checks passed: all-target Cargo tests, fmt, Clippy, stable-docs,
four offline hosted-verifier tests, and the pinned source parser with 998
successful records (333 PATH) plus five negative controls. These are separate
from the native hosted observations above. PR #142 owns latest-head CI and
review status; the hosted tested source is the explicit SHA above, not a claim
that later documentation-only commits were executed in Azure.

## Release assessment

The observed Agent version matches the pinned source baseline and both image
generations/architectures match the design profile. The four writers have
passed their scoped hosted consumer-effect checks, including issue location
metadata and native PATH effects.
No writer implementation defect or new attack path was observed in these runs.
The location messages were also confirmed in the hosted UI as described above.
The scoped Azure hosted gate is satisfied; clickable source navigation and
pixel-identical rendering of arbitrary messages are not claimed.

The [current implementation handoff](../implementation-plan.md#current-handoff-status)
owns the next work item and whether release preparation is scheduled. These
observations are not permission to publish or proof that release packaging gates passed: version
selection, release notes/metadata, exact release-source checks and maintainer
approval remain separate. Published v1.0.0 binaries are unchanged and contain
none of the Azure commands. The Azure-specific checks do not replace the
existing GitHub consumer and artifact verification gates.

## Official references

- [Logging commands](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops)
- [Variables and naming restrictions](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/variables?view=azure-devops)
- [Setting and mapping output variables](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/set-variables-scripts?view=azure-devops)
