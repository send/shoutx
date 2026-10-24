# Azure PATH writer plan

Status: Implemented with scoped hosted verification; PR review pending.

The [PATH command contract](../commands/azure-pipelines.md#path) now owns all
acceptance and wire rules. The checklist below records the implementation work
and its rationale, not a second normative specification. Verification results
belong in the [compatibility record](../compatibility/azure-pipelines.md).

## Context

This proposal covers one typed `task.prependpath` writer,
`shoutx azure-pipelines:path [PATH]`. It complements the existing
non-secret variable and issue writers. Its command contract was specified
before implementation. Work ordering
is owned by the [current handoff](../implementation-plan.md#current-handoff-status).

## Boundary and proposed approach

Protect the selected command and one intended effective PATH entry. A path must
not inject another command or become multiple entries when Azure composes PATH.
The caller authorizes the directory and executables; shoutx does not establish
their trustworthiness or authorize executable lookup through them.

Reuse bounded input acquisition, strict UTF-8/NUL checks, value-free diagnostics
and pre-write validation. Use Azure's encoder, not the GitHub file-command
writer. Do not normalize, trim, resolve symlinks or require directory existence.
Keep the existing native hosted Azure profile; containers and self-hosted
agents are not added by this increment.

## Contract work before coding

- Settle path dialect selection for the supported native producer/consumer
  deployment. Do not silently inherit GitHub's `RUNNER_OS` selector. Specify
  behavior for absent, unknown or conflicting selectors if one is introduced.
- Specify fully qualified POSIX/Windows path forms and reject the effective
  target PATH separator. A protocol escape that Azure later decodes cannot
  make a PATH-list separator safe as path data.
- Explicitly constrain the contract to one selected command and one incoming
  PATH entry, not stable duplicate identity or preservation of earlier entries.
  Azure's [observed duplicate handling](../compatibility/azure-pipelines.md#path-source-observations)
  can replace an earlier, ordinally different entry. Do not promise that all
  distinct strings coexist or that deduplication is portable across cultures.
  Input byte fidelity is not a claim about the resulting list's membership.
- Decide CR/LF handling, including a trailing producer newline, explicitly;
  do not inherit GitHub's final-boundary consumption. Reconcile the existing
  Azure final-newline statements in the command contract, design and README
  with the chosen PATH behavior, scoping them to variable/issue writers where
  needed. Assess quotes and other identity-changing syntax at the actual native
  consumer boundary. Import no
  GitHub container-only restrictions without an Azure attack path.
- Define exact fixed wire syntax, input/record limits, argv/stdin behavior,
  option errors and empty-stdout rejection. Maintain byte fidelity for every
  accepted semantic path and no lossy mode in this increment.

## Implementation and verification sequence

1. Follow the pinned command through PATH composition, limiting inspection to
   the native path handler and relevant helper. Record useful source findings
   in the Azure compatibility record. Keep the duplicate-identity limitation
   explicit in the command contract; no collation-internal proof is required
   for that constrained guarantee.
2. Update the Azure command contract and relevant threat inventory. Implement
   explicit Azure path validation, CLI dispatch and help; keep GitHub behavior
   unchanged. Share only grammar helpers whose assumptions actually match.
3. Add exact CLI success/failure tests, argv/stdin parity, invalid encoding,
   limits, literal escapes, multilingual paths, delimiters and negative
   injection controls. Extend the pinned parser suite with exact command/data
   checks, not a local encoder round trip alone.
4. Extend the existing hosted fixture on Ubuntu and Windows. Create synthetic
   caller-owned directories, emit through shoutx, and inspect the subsequent
   task's PATH entries and executable lookup. Assert the expected entry bytes,
   no injected entry/operation, and order for unambiguously distinct ASCII
   fixture entries. Exercise repeat registration on both OS generations and
   distinguish the requested incoming entry from replacement of earlier entries.
   Record any culture/backend identities actually observed as such; unavailable
   Agent identities remain unknown, not inferred from the producer process.
   These fixtures do not establish portable duplicate equivalence. Test rejection
   before stdout separately; do not execute attacker-controlled fixtures.
5. Update complete-surface checks and packaged-binary verification so the new
   command cannot be omitted from a native artifact. Run Cargo tests, fmt,
   Clippy, stable-docs and focused verifier tests. Review the change and converge
   latest-head CI/Codex before requesting merge.

Done means the typed writer, contract, producer/parser tests and scoped hosted
consumer effects agree, with observed source/Agent/image identities retained.
A passing parser test is not hosted evidence. If a concrete incompatibility
appears, fix or explicitly constrain that path rather than expanding into an
Agent audit. Secret support and release work are outside this increment.

## Source starting points

Start from the [retained PATH source observations](../compatibility/azure-pipelines.md#path-source-observations).
Review the linked native composition helper and retain real next-task
observations before finalizing the contract. Existing variable/issue hosted
results are not PATH verification.
