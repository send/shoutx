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

Hosted verification: **not run; account/environment preparation pending**.
Do not infer Azure service support from GitHub CI, a native binary build, or
source-parser success. The local implementation goal can finish without this
gate; publication cannot claim completed Azure verification.

The [manual hosted fixture](../../tests/azure-hosted/README.md) is prepared.
It uses synthetic values, verifies next-step effects and reads the build
timeline for warning/error checks. Source-location translation still requires
a hosted observation before recommending those metadata options.

## Official references

- [Logging commands](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops)
- [Variables and naming restrictions](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/variables?view=azure-devops)
- [Setting and mapping output variables](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/set-variables-scripts?view=azure-devops)
