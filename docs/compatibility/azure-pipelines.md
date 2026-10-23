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

- [`TaskPrepandPathCommand`](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/TaskCommandExtension.cs#L765-L786)
  checks task restrictions, requires nonempty data, removes a
  current-culture-equal earlier entry and appends the value.
- The [native handler](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Worker/Handlers/Handler.cs#L240-L274)
  reverses the prepend list and joins it with `Path.PathSeparator` before
  invoking `PathUtil.PrependPath`.
- [`PathUtil.PrependPath`](https://github.com/microsoft/azure-pipelines-agent/blob/efa064fee06c75b31cabc0451857ad1e294649c7/src/Agent.Sdk/Util/PathUtil.cs#L19-L38)
  returns the incoming string if the old PATH is empty, otherwise joins with
  the native separator. If the old PATH already starts with the incoming
  prefix plus separator under `IOUtil.FilePathStringComparison`, it keeps the
  old PATH (including its spelling). It does not trim, unquote or resolve paths.

These are source observations, not a PATH acceptance
contract or hosted verification. Real next-task effects remain
to be checked under the [PATH plan](../decisions/azure-path.md). The pin does not
establish that later hosted Agents match it. Hosted observations below cover
only the existing variable and issue writers.

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

## Release assessment

The observed Agent version matches the pinned source baseline and both image
generations/architectures match the design profile. The three writers have
passed the scoped hosted consumer-effect checks, including location metadata.
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
