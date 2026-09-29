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
for `##[` anywhere in the line rather than requiring it at the start. A failed
V2 parse is treated as ordinary log output when legacy parsing also fails. If
the culture-sensitive legacy search succeeds, however, a registered workflow
command found later in the line is executed; value data containing
legacy-looking syntax can therefore become command syntax. The known `th-TH`
counterexample establishes the ordinary-output path, not this second condition.

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
failure and comparing the legacy parser under selected cultures. The current
fixture also drives the counterexample through `OutputManager`, proving
ordinary logging after failed recognition. A separate `OutputManager` case
proves that a failed V2 parse can execute a registered legacy command found
later in the same line; it does not claim that this fallback occurs under the
known `th-TH` counterexample. The oracle runs on Ubuntu 22.04, Ubuntu 24.04,
macOS, and Windows. The current tests do not record the active globalization
backend or its version, so this note does not infer ICU or NLS solely from the
operating-system label.

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

## Self-hosted runner version snapshot

Queries completed at 2026-09-29T08:45:53Z. The official releases API listed
the following stable non-draft, non-prerelease runner versions from v2.329.0
onward. The repository-scoped deprecation endpoint for `send/shoutx` returned
HTTP 200 for each query with these `runtime_deprecates_at` values:

| Runner release | Runtime deprecation |
| --- | --- |
| `v2.329.0` | `2026-01-23T17:10:35Z` |
| `v2.330.0` | `2026-03-13T18:34:13Z` |
| `v2.331.0` | `2026-04-30T21:52:20Z` |
| `v2.332.0` | `2026-05-25T15:23:35Z` |
| `v2.333.0` | `2026-05-29T17:27:54Z` |
| `v2.333.1` | `2026-06-30T15:52:45Z` |
| `v2.334.0` | `2026-08-10T17:08:55Z` |
| `v2.335.0` | `2026-08-14T16:59:37Z` |
| `v2.335.1` | `2026-09-24T15:30:55Z` |
| `v2.336.0` | `2026-11-05T08:04:55Z` |
| `v2.337.0` | JSON null |

The query listed all stable releases through the then-latest v2.337.0. It used
v2.329.0 only as a finite observation bound because GitHub's September 28
announcement named it as the registration floor; this does not show that an
older, already-registered runner could not execute a job. The procedure queried
`GET /repos/send/shoutx/actions/runners/deprecations/{version}` for each. It used
API version `2026-03-10` and an authenticated classic token with `repo` scope
owned by the repository administrator. The timestamps above are the verbatim
JSON strings. These are dated observations, not a substitute for a future
query or evidence that enforcement had occurred exactly at each timestamp.

For this repository, v2.336.0 returned a future runtime-deprecation date and
v2.337.0 returned JSON null in that snapshot. A past date is not evidence that
enforcement occurred at that instant, and null is recorded without inferring
an undocumented meaning. The responses do not establish that another
repository, organization, enterprise, or data-residency region observed the
same schedule.

The `ActionCommand.cs`, `ActionCommandManager.cs`, and `OutputManager.cs` blobs
are identical in v2.336.0 and v2.337.0: respectively
`c51fa5a342806e296ad6af3e15735984feb29155`,
`4b9995fc89dd2c2b5e4115afd646f920de0bef82`, and
`32d1e78c21cbef0727facc67527af3946aa73bc6`. The release commits are
`98aabcd429c4e8402406c56ce2d26387fed3b9ce` and
`397b032cbf865e9c3ddfab89d533ec19325e1273`. Source identity does not prove
packaged-runtime identity: the source trees pin .NET SDK 8.0.422 and 8.0.424
respectively, and installed globalization data can differ by host.

GitHub documents a general 30-day self-hosted update requirement. Its September
28, 2026 announcement distinguishes the registration minimum from runtime
eligibility and says that the announced Enterprise Cloud enforcement does not
apply to GitHub Enterprise Server.

The current oracle builds and executes only v2.337.0 source. It does not test
v2.336.0 or a published runner package and therefore does not establish a
self-hosted compatibility matrix. This section records evidence only; the
proposed interpretation and unresolved policy live in the framing decision.

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
- [`OutputManager.cs` in the pinned runner][pinned-output-manager]
- [GitHub runner releases API][runner-releases-api]
- [GitHub self-hosted runner update policy][runner-update-policy]
- [GitHub runner-version deprecation API][runner-deprecation-api]
- [September 2026 enforcement announcement][runner-enforcement]
- [Runner v2.336.0 release][runner-2336]
- [Runner v2.337.0 release][runner-2337]
- [Microsoft .NET globalization and ICU behavior][dotnet-icu]
- [`ShoutxDifferentialL0.cs`](../../tests/runner-oracle/ShoutxDifferentialL0.cs)
- [PR #42](https://github.com/send/shoutx/pull/42)
- [Issue #43](https://github.com/send/shoutx/issues/43)
- [Microsoft guidance for culture-insensitive string operations][dotnet-guide]

[pinned-parser]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Common/ActionCommand.cs
[pinned-manager]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/ActionCommandManager.cs
[pinned-output-manager]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/Handlers/OutputManager.cs
[runner-releases-api]: https://docs.github.com/en/rest/releases/releases?apiVersion=2026-03-10#list-releases
[runner-update-policy]: https://docs.github.com/en/actions/reference/runners/self-hosted-runners#runner-software-updates-on-self-hosted-runners
[runner-deprecation-api]: https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2026-03-10#get-runner-version-end-of-life-schedule-for-a-repository
[runner-enforcement]: https://github.blog/changelog/2026-09-28-self-hosted-runner-version-enforcement-date-has-moved/
[runner-2336]: https://github.com/actions/runner/releases/tag/v2.336.0
[runner-2337]: https://github.com/actions/runner/releases/tag/v2.337.0
[dotnet-icu]: https://learn.microsoft.com/en-us/dotnet/core/extensions/globalization-icu
[dotnet-guide]: https://learn.microsoft.com/en-us/dotnet/core/extensions/performing-culture-insensitive-string-operations
[u11f02-run]: https://github.com/send/shoutx/actions/runs/36451589798/job/109027454250
