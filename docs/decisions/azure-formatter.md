# Azure diagnostic and group writers

Status: Proposed, 2026-10-31. Design only; no new CLI is available.

## Context and decision drivers

Build scripts need to label a phase with generated text and emit diagnostic
messages. A typed writer should retain accepted text and select one intended
operation. It does not make arbitrary group-body output safe or manage a group
across processes. The [draft contract](../commands/azure-pipelines-formatter.md)
owns candidate behavior; [source observations](../compatibility/azure-pipelines.md#formatter-design-observations)
own evidence and its limits.

The useful boundary is the path from emitted stdout to Agent command dispatch
and log formatting. Character-set completeness, credential discovery and
general pipeline auditing are not prerequisites. Ordinary Unicode text should
remain accepted without a language-specific allowlist.

## Considered options

| Option | Benefit | Cost and limitation |
| --- | --- | --- |
| Documented formatter syntax for all three operations | Small, consistent surface | Formatting and task commands share stdout; line framing alone is insufficient. No documented formatter escape has been established. Raw debug output cannot be assumed to follow Agent debug gating. |
| Task-command debug plus formatter group/endgroup | Uses the debug route used by Microsoft's task-lib, with existing task-command encoding and Agent debug gating | Mixed wire protocols; the task command is absent from the general logging-command inventory. Service rendering still needs admission. Group has no corresponding established task-command alternative. |
| Explicit visible sanitization | Can display otherwise rejected diagnostic text without executing its original control syntax | Changes the text and needs a specified reversible display notation, collision handling and consumer checks. It is not exact diagnostic data. No silent replacement is acceptable. |
| Defer some or all writers | Avoids shipping an unproven representation | Leaves ordinary dynamic log labels/debug messages without a typed boundary. Fixed trusted labels remain usable. |

## Proposed decision

Prefer task-command debug and formatter group/endgroup, with a deliberately
single-line, unchanged-text contract. The reservation of formatter-looking
text is conservative pending the finite consumer check; it is not a claim that
every reserved input has a demonstrated attack path. The draft names every
restriction so the maintainer can assess its usability cost before adoption.

The maintainer must approve three choices:

1. Use the official task-lib-backed debug route despite its omission from the
   general logging-command list, with support limited to the admitted profile.
2. Reject multiline values, including a final producer newline, rather than
   strip or split them. This makes ordinary multiline tool output unsuitable
   as a direct operand; callers must deliberately choose a single-line label.
3. Initially reserve the explicit protocol-looking substrings in the draft.
   These reject documentation snippets and some tool diagnostics. Either accept
   that cost, approve a later explicit display-escaping design, or defer the
   affected writer. Do not market the proposal as arbitrary-text logging.

No sanitizer is included in this increment. If the rejection cost is unacceptable,
the next task should specify an explicit display mode rather than spend more
time proving all Unicode text safe. Additional source analysis is justified
only by a concrete operation-changing path or a finite failed admission case.

## Verification and endpoint

The draft contract owns the finite producer, Agent and hosted/UI checks.
This design goal ends after independent GPT-6.1 Sol review and presentation
of these decisions; hosted implementation admission is a subsequent approved
task. Passing raw-log assertions alone cannot establish group display effects.

Reconsider the wire choice if Microsoft removes the SDK route, changes the
pinned interpretation path, or admission demonstrates loss of intended text
or operation. Reconsider the conservative reservations when a concrete user
need and bounded consumer evidence support a wider accepted domain.
