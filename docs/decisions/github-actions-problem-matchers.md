# Problem matcher writers

Status: Accepted for implementation; verification and publication are separately gated.

## Decision

Provide typed writers for adding a matcher file and removing by owner or file.
Do not offer a generic command/property emitter or read/validate matcher JSON.
The [command specification](../commands/github-actions-problem-matchers.md)
owns the interface and observable acceptance rules. This decision records the
use case and responsibility split.

The remove subcommand makes owner metadata versus file data explicit, following
the existing artifact writer's typed-operand convention. Each mode has one
value, so bounded argv-or-stdin acquisition follows existing writers.
There is no implicit owner/path guessing and no simultaneous owner and file.

## Practical use and boundary

A reusable action can register a trusted matcher configuration located beneath
its installation directory, or at a caller-approved generated path, and remove
its owners after the associated tool runs. Shell quoting alone does not keep a
path containing physical CR/LF within one workflow-command record. For removal,
an owner inserted into a raw command header can contain a comma, colon delimiter
or line break and alter properties, data or command selection. The workflow may
authorize the selected resource while still needing correct serialization.

The protected operation is delivering exactly the selected add/remove command
with the requested accepted path or owner in its intended field. The writer
does not authorize loading an attacker-chosen JSON file, replacing another
owner's matcher, removing an important matcher, or the regex/configuration
itself. It does not sanitize later tool output or make matcher-produced
annotations trustworthy. Registration and removal lifetime remain caller-owned.

This is analogous to the existing path and artifact writers: resource
authorization is separate from framing. That distinction is not a reason to
exclude a useful framing boundary. Neither failure to load a file nor successful
stdout writing acknowledges registration or removal by the separate Runner.

## Existing controls and bounded verification

Reuse the existing V2 data-start policy for path data and property escaping /
structural termination evidence for owner metadata, checking the new headers
and handlers rather than inheriting annotation-specific limits or behavior.
The new owner header can always use a structural terminator, unlike annotation
headers which preserve older ASCII wire bytes. This permits exact trailing
whitespace without a value-changing trim; the contract and parser tests must
establish that behavior before exposure.
Do not broaden acceptance on the basis of a new universal Unicode proof.
No lossy transformation is proposed. Record framing must be complete before
stdout, with strict encoding, bounded input and value-free producer diagnostics.

Verification should check exact decoded command/data/properties, actual loading
of a synthetic trusted matcher file, and actual removal of the intended owner(s)
while retaining a distinct control matcher. Hosted tests must demonstrate a
positive match before removal and its absence afterwards alongside a still-live
control, so an inactive matcher subsystem cannot pass. Registration by file,
removal by file and removal by owner need separate coverage. Avoid testing
arbitrary regex behavior: use fixed simple patterns and synthetic public text.

## Source observations (2026-10-17)

The official toolkit documents add by JSON file path and removal by owner, and
describes owner-based replacement. Pinned Runner v2.337.0 at
`397b032cbf865e9c3ddfab89d533ec19325e1273` additionally supports removal by file:

- `AddMatcherCommandExtension` requires nonempty data, resolves relative paths
  against the workspace, loads JSON, validates the configuration and calls
  `AddMatchers` when it contains matchers.
- `RemoveMatcherCommandExtension` rejects simultaneous nonempty owner and file
  or neither. It calls `RemoveMatchers` with the owner, or loads a file and takes
  its configured owners. Removing by file is not ownership of the file content.
- `ExecutionContext.AddMatchers` replaces existing owners using ordinal
  case-insensitive comparison; `RemoveMatchers` uses the same comparison.
  This is a consumer identity rule, not additional text normalization by shoutx.
- Both extensions permit command echo. They do not offer a secret channel.

These observations establish a concrete target for tests, not completed
compatibility evidence. The command specification and design-owned applicability
profile will own the supported behavior once the proposal is accepted.

## References

- [Toolkit commands](https://github.com/actions/toolkit/blob/main/docs/commands.md#problem-matchers)
- [Toolkit problem matchers](https://github.com/actions/toolkit/blob/main/docs/problem-matchers.md)
- [Pinned command handlers](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ActionCommandManager.cs)
- [Pinned matcher state operations](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/ExecutionContext.cs)
