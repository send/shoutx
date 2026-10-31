# Azure diagnostic and group writer draft

Status: Proposed. Not implemented or approved. The
[decision](../decisions/azure-formatter.md) owns rationale and choices requiring
maintainer approval. This document is the single candidate CLI/admission contract.

## Interface and input

```text
shoutx azure-pipelines:debug [MESSAGE]
shoutx azure-pipelines:group [TITLE]
shoutx azure-pipelines:endgroup
```

Debug/group accept one value operand, or bounded non-terminal stdin when the
operand is absent. An explicit empty operand is data and does not select stdin.
Use `--` for an operand beginning with a dash. Apply the existing Azure
value-command option grammar: help/version return without reading stdin;
unknown options, extra operands and terminal stdin are usage failures (exit 2).
There are no properties, severity switches, multiline mode or raw escape mode.
Endgroup takes no operands, does not read stdin and emits only its fixed record;
extra operands/options fail as usage errors, except normal help/version.

## Proposed value rules

Acquire at most 1 MiB, validate strict UTF-8 and reject NUL. Reject CR and LF at
any position, including the final producer boundary. Reject an empty group
title; allow an empty debug message. Preserve accepted spaces, tabs, combining
characters, supplementary characters, percent sequences and punctuation exactly;
no trim, normalization, case folding or language allowlist.

As an explicit initial reservation, reject the ASCII substring `##[` in either
value and `##vso` in group titles. Match these byte sequences exactly, anywhere
in the value. The formatter reservation is conservative, not proof that each
such occurrence changes an operation. The task-prefix reservation includes
malformed forms to avoid command-processing diagnostics on a formatter line.
No general promise of diagnostic-free handling for every Unicode string is
made. The decision record explains the usability cost and alternatives.

Validation order is acquisition limit, UTF-8, NUL, line breaks, required
nonempty title, reserved substrings, checked output size. Prepare the complete
record before writing stdout. Input/representation/size failures return 1 with
empty stdout and fixed value-free diagnostics. The record limit is 8 MiB,
including the trailing LF. No rejected input is echoed or silently transformed.

## Proposed wire and semantics

Let `E` be the existing [Azure data encoding](azure-pipelines.md#wire-contract).
Debug writes `##vso[task.debug]E(MESSAGE)` plus LF. Group writes
`##[group]TITLE` plus LF; endgroup writes `##[endgroup]` plus LF.
Only debug applies `E`. Percent-looking text in a group title is literal:
there is no assumed formatter percent decoder. Accepted semantic values must
remain unchanged at the admitted log boundary, apart from Azure's existing
masking of registered values and presentation of control whitespace.

Debug requests the Agent's debug path; with debug disabled it may deliberately
produce no diagnostic log. This is not a secrecy mechanism. Group/endgroup
request log grouping, not task execution, timeline issue creation or status
changes. Each invocation emits exactly one record. The caller orders and
balances groups, avoids interleaving producers, and owns all body output.
There is no nesting stack, automatic close, subprocess capture or fallback to
ordinary logs. Sequential shell calls must check each exit status.

Successful exit means output was written, not that Azure accepted or displayed
it. An I/O error after writing starts may leave a prefix and cannot roll back a
group. Do not retry blindly when the consumer may already have seen the record.

## Responsibility and consumer scope

The candidate protects the selected operation and accepted message/title at
this output boundary. Callers authorize disclosure and operation choice and
pass values as quoted data instead of shell source. Body output and later
parsers are separate boundaries. Azure owns debug gating, masking, rendering,
retention and grouping behavior; shoutx neither replaces those components nor
guarantees identical glyphs or terminal presentation.

Reuse the native Ubuntu/Bash and Windows/PowerShell
[Azure profile](../design.md#azure-pipelines-profile), pinned Agent baseline and
percent-decoding prerequisite. Test debug-on and debug-off separately for this
non-secret command. This does not expand mask/secret-variable admission to
debug-on jobs. No secret is appropriate input for these display commands.
Limit grouping admission to Azure DevOps Services' web run-log view; downloaded
logs need only retain the expected records/text, not interactive grouping.
No containers, self-hosted profiles, third-party viewers or whole-stream safety
are added by this proposal.

## Finite implementation admission

Execute only after approval. Reuse existing fixtures and the pinned actual
Agent parser instead of building a new logging framework.

1. **Producer contract:** assert exact bytes, status and fixed diagnostics for
   all three commands, argv/stdin parity, help/version, option termination,
   extra operands, terminal stdin, empty input, whitespace, multilingual and
   supplementary text, combining text, literal percent escapes and delimiters.
   Cover each rejected byte/substring at beginning/middle/end, CR/LF/CRLF and
   final boundaries, invalid UTF-8/NUL, acquisition cap/cap+1, checked record
   size and output errors. Every pre-write failure must leave empty stdout.
   Endgroup must not read a failing or blocking stdin stream.
2. **Actual parser and dispatch evidence:** retain the source path and its pin.
   Check debug's selected area/event, no added properties, exact decoded data
   and one physical record using upstream Command.cs. Check group/endgroup
   are not dispatched as task commands for admitted values. Use synthetic
   command-looking rejected controls only in an offline sink; never forward
   them to hosted stdout. Mutations for a wrong command, changed data, extra
   record and missing validation must make the verifier fail. Source evidence
   and parser results do not themselves prove service/UI formatting.
3. **Four hosted jobs:** one debug-off and one debug-on job on each existing
   native OS, at most 15 minutes per job. Build the reviewed binary once per
   OS and retain source/artifact identity. Each job emits a fixed bounded
   corpus: ASCII, mixed scripts, supplementary/combining text, literal escapes,
   empty debug, tabs/spaces, and a long accepted value up to the input cap.
   Use an isolated group with before/inside/after markers and one balanced
   nested pair. No real secrets, live attack commands or racing producers.
   Check completed logs for the expected message/title bytes, intended debug
   visibility, preserved markers and absence of unexpected issues or changed
   sentinel variables/status. Fetch logs using the existing bounded retrieval
   policy. Missing/truncated logs, wrong source/job/attempt, absent records or
   unexpected issues fail; do not infer success from a producer exit code.
4. **Web-view evidence:** manually inspect those four run logs after completion.
   Record run/task IDs, Agent/image versions, date, view identity and screenshots
   of group title plus collapse/expand effect, nested balance and after-marker
   outside the group. Check debug visibility with the same view settings and
   record any UI filtering separately from Agent omission. Long-value fidelity
   is a completed-log byte check, not a screenshot comparison. Do not claim
   interactive grouping from the presence of wire text alone.
5. **Stop condition:** exact producer/parser assertions plus all four hosted
   outcomes and recorded UI effects are required for implementation admission.
   A concrete failure gets one scoped diagnosis/correction and a rerun of the
   affected checks. If representation, limits or consumer scope must change,
   return that choice for approval; never silently drop cases or launch an
   open-ended character scan. Retain bounded evidence in compatibility, with
   sensitive attack details in private follow-up under SECURITY.md.
