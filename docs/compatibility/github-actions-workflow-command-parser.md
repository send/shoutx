# GitHub Actions workflow-command parser compatibility

This note records compatibility evidence about the GitHub Actions stdout
workflow-command parser. It is descriptive evidence, not a command contract or
a decision to use either supported wire syntax. Normative behavior remains in
the command specifications, framing choices remain in decision records, and
release eligibility remains in the release policy.

## Finding

The pinned runner's V2 parser recognizes commands shaped like
`::command properties::data`. It trims leading whitespace, checks the initial
`::` with the culture-sensitive `StartsWith(string)` overload, and then finds
the data separator with the culture-sensitive .NET call
`message.IndexOf("::", 2)`. A server-supplied `system.culture` job variable can
set the worker's default culture. The child process that emits the line cannot
reliably observe that worker state.

This makes an ASCII protocol delimiter depend on ambient collation. Under
`th-TH` on .NET 8, the pinned parser does not recognize the ordinary
ASCII-only record `::add-mask::secret`. The pinned-parser regression proves
that parsing fails; it does not currently expose which culture-sensitive check
or search result caused that failure. The shoutx process has already completed
successfully, so an `add-mask` caller can receive a false success while the
runner installs no mask. The same V2 parser is used for notice, warning, and
error commands.

`th-TH` is a known counterexample, not a claim that Thai text or one culture is
the cause or the complete affected set. The input demonstrating the failure
contains no Thai or non-ASCII data. The relevant variable is locale-sensitive
protocol parsing whose result can depend on culture, collation backend, and
collation-data version.

## Parser fallback and impact

Before parsing, `OutputManager` uses culture-sensitive searches for either
`::` or `##[` as a prefilter. The command manager then tries the V2 parser
first and its legacy `##[command]data` parser second. The legacy parser searches
for `##[` anywhere in the line rather than requiring it at the start. A
misparsed V2 line can consequently be treated as ordinary log output or execute
an attacker-shaped registered workflow command if value data contains
legacy-looking syntax.

The observable consequences differ by command:

- failed `add-mask` recognition makes `OutputManager` log the unrecognized
  command line as ordinary output, which can expose the value immediately, and
  leaves subsequent occurrences unmasked even though the producer exited
  successfully;
- failed annotation recognition can lose an annotation and log the encoded
  line as ordinary text; and
- a moved separator can change which text the runner treats as properties and
  data.

Environment-file writers do not pass through this stdout parser. This finding
does not override their separate destination-specific compatibility contracts.

## Evidence and environment variation

PR #42 added a pinned-runner regression proving the ASCII-only `th-TH` V2
failure and comparing the legacy parser under selected cultures. The oracle
runs on Ubuntu 22.04, Ubuntu 24.04, macOS, and Windows. The current tests do not
record the active globalization backend or its version, so this note does not
infer ICU or NLS solely from the operating-system label.

That expansion also exposed a separate portability assumption in an existing
test. An assertion expecting U+11F02 to move the V2 separator passed on the
newer environments but failed on Ubuntu 22.04, where the runner decoded the
earlier separator instead. The scalar was removed from the shared portable
runner-oracle assertions; its producer-side rejection remains implemented. The
failed [PR #42 CI run][u11f02-run] is evidence that a
Unicode category or scalar denylist cannot stand in for the destination parser:
the same runner source and .NET SDK can behave differently across platform
collation data.

The tests are evidence and regression detection, not proof over all present
or future cultures. They do not establish a supported-culture allowlist or
show that a Unicode scalar or category restriction can repair V2 framing.

The product-level syntax and data rules are authoritative in
[`design.md`](../design.md). Verification requirements and the framing choice
belong to the decision record below, not this evidence note.

## Open decision and upstream reminder

The framing options and their status are maintained in the
[stdout framing decision record](../decisions/github-actions-stdout-framing.md).
This compatibility note does not select one.

The separate [upstream reminder](https://github.com/send/shoutx/issues/43)
records maintainer-owned follow-up timing.

## Primary evidence

- [`ActionCommand.cs` in the pinned runner][pinned-parser]
- [`ActionCommandManager.cs` in the pinned runner][pinned-manager]
- [`ShoutxDifferentialL0.cs`](../../tests/runner-oracle/ShoutxDifferentialL0.cs)
- [PR #42](https://github.com/send/shoutx/pull/42)
- [Issue #43](https://github.com/send/shoutx/issues/43)
- [Microsoft guidance for culture-insensitive string operations][dotnet-guide]

[pinned-parser]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Common/ActionCommand.cs
[pinned-manager]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs
[dotnet-guide]: https://learn.microsoft.com/en-us/dotnet/core/extensions/performing-culture-insensitive-string-operations
[u11f02-run]: https://github.com/send/shoutx/actions/runs/36451589798/job/109027454250
