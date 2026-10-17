# Debug and group writers

Status: Accepted for implementation; verification and publication separately gated.

## Decision

Add typed debug/group writers and a fixed endgroup operation. The
[command contract](../commands/github-actions-log-commands.md) owns CLI behavior
and its verification. Reuse V2 data framing and the existing positive Unicode
start policy, with explicit checks of these command headers and real handlers.
Do not add a generic command emitter, subprocess wrapper or automatic lifetime.

## Rationale

Untrusted diagnostic text and log-group titles can otherwise introduce another
workflow command through raw line breaks. V2 parsing also has the already
characterized fallback path; reusing its bounded control is preferable to
reopening dependency-internal proofs. Debug/group are distinct consumers, not
annotations: neither creates an issue or uses the annotation retention limit.

Debug prefixes each decoded LF-delimited line when logging is enabled. Group
instead forwards the decoded title following a log group marker. A single-line
title avoids introducing continuation log records through that second operation.
Rejecting internal CR/LF preserves accepted titles without an implicit lossy
sanitizer. This does not establish arbitrary UI rendering or content trust.
Empty data is representable by both handlers; mask/annotation empty-value
restrictions are therefore not inherited. The fixed terminator makes group
usage practical without implying subprocess-output safety.

## Evidence and scope

The inspected source is actions/runner `397b032cbf865e9c3ddfab89d533ec19325e1273`
(v2.337.0): `DebugCommandExtension`, `GroupingCommandExtension`, and
`ExecutionContextExtension.Debug`. Verification must exercise these actual
handlers, debug enabled/disabled, command echo, stopped commands, and hosted
logs on the design-owned profile. Implementation does not authorize release.
