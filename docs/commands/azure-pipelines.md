# Azure Pipelines logging-command writers

Status: implemented, unreleased; not in v1.0.0.
The [design profile](../design.md#azure-pipelines-profile)
owns applicability; the [compatibility record](../compatibility/azure-pipelines.md)
owns observations and hosted verification status.

## Interface

```text
shoutx azure-pipelines:variable [--output] [--read-only] NAME [VALUE]
shoutx azure-pipelines:warning [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]
shoutx azure-pipelines:error   [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]
shoutx azure-pipelines:path [PATH]
```

These are typed writers for `task.setvariable`, `task.logissue` and
`task.prependpath`, not a generic command builder. No raw properties, secret option, masking,
artifact operation, or command-name operand is provided.

Options precede NAME or MESSAGE. `--` ends option parsing. Help/version in
option position have the shared behavior. Options take separate operands,
not `--option=value`. Duplicate flags/options, unknown options, missing option
arguments, missing NAME and extra operands are usage failures (status 2).
After NAME, a single token is VALUE even if it begins with `-`. For MESSAGE
use `--` before a dash-prefixed value.

An explicit value ignores stdin. Otherwise the shared bounded non-terminal
stdin acquisition applies. **All variable/issue value/message bytes, including final
CR/LF, are semantic data and are preserved.** These commands do not consume a
producer newline, trim, normalize, decorate, or offer line-normalization modes.
Use `printf '%s'` when a producer newline is not wanted. This differs from
GitHub writers that consume one final boundary.

### PATH

`azure-pipelines:path` accepts one optional PATH operand and no options other
than the shared help/version and `--`. An explicit operand ignores stdin;
otherwise bounded non-terminal stdin supplies the path. Extra operands and
unknown options exit 2. Empty input, malformed UTF-8, NUL, CR or LF anywhere
(including a final producer newline) exit 1 with empty stdout. Use `printf '%s'`,
not `echo`. The shared 1 MiB input and 8 MiB record limits apply.

The native executable selects its own OS dialect; `RUNNER_OS`, `AGENT_OS` and
other environment selectors do not override it. Producer and consumer must use
the same native OS, within the design-owned profile. No cross-target option is
provided. POSIX paths must begin with `/` and contain no `:`. Windows paths must
be drive-absolute (`[A-Za-z]:` followed by `/` or `\`) or ordinary UNC paths
with two leading separators and nonempty server/share components (neither `.`
nor `?`). Windows permits either slash as a separator, but rejects `;` and
double quotes. Device/verbatim namespace paths are not accepted in this increment.
The list-separator rejection prevents additional PATH entries after decoding;
Windows quotes are excluded to avoid quoted search-path interpretation.
POSIX quotes and trailing backslashes are ordinary native path data and are
preserved. No trimming, normalization, existence check or symlink resolution
is performed. Fully qualified syntax does not establish resource trust or
guarantee that a path exists or is usable by every executable launcher.

Emit `##vso[task.prependpath]PATH` followed by LF, with no properties. Apply the
same escaping table below to PATH. Every accepted path is preserved as command
data. The protected boundary is one selected command and one incoming PATH
entry, not stable duplicate identity or preservation of earlier entries.
Azure can replace earlier entries using its own comparison, or retain an
existing equivalent prefix. Distinct ordinal strings need not coexist, and
the final PATH need not retain the incoming spelling in that prefix case.
The caller authorizes the directory and executables; shoutx does not make
attacker-selected executable lookup safe. Changes apply to subsequent tasks,
not the producing process. Settable-variable restrictions and other Agent
conditions can prevent the effect even after a successful write.

## Validation and limits

All text must be strict UTF-8 without NUL. Values/messages have the shared
1 MiB raw input limit. Empty variable values are accepted; empty issue messages
are rejected. Whitespace and Unicode at any position are data, with no GitHub
data-start policy.

NAME is 1–255 ASCII bytes matching `[A-Za-z_][A-Za-z0-9_.]*`. Reject the
Azure reserved prefixes `endpoint`, `input`, `secret`, `path`, and `securefile`
using ASCII-insensitive prefix matching. This is a deliberately conservative
grammar, not an assertion that the consumer rejects every other name.
Case-insensitive variable identity and environment-name transformations
(uppercasing and replacing dots with underscores) remain Azure semantics.
The caller authorizes NAME; encoding does not prevent selecting a sensitive
variable or colliding with another name after environment export.

FILE is nonempty and at most 4,096 UTF-8 bytes; CODE is nonempty and at most
255 UTF-8 bytes. They are text metadata, not resources opened by shoutx.
CR/LF in these fields is encoded rather than trimmed. LINE and COLUMN are
1–2,147,483,647, spelled with 1–10 ASCII digits and emitted canonically without
leading zeroes. LINE requires FILE; COLUMN requires LINE. No end-position,
title or arbitrary property option is accepted.

Validate all fields and compute expanded record length with checked arithmetic
before allocating output. The complete record, including LF, is capped at
8 MiB. This is a producer resource limit, not an Azure service-size guarantee.
Validation failures exit 1 with empty stdout. Diagnostics never reproduce
input; shared I/O-failure and status behavior applies.

## Wire contract

Escape every variable value, message, PATH and text property byte as follows:

| Byte | Emitted ASCII |
| --- | --- |
| `%` | `%AZP25` |
| CR | `%0D` |
| LF | `%0A` |
| `;` | `%3B` |
| `]` | `%5D` |

All other UTF-8 bytes pass unchanged. Replacement is one pass over input bytes:
never recursively encode generated escapes. The consumer decodes structural
escapes before `%AZP25`, preserving literal input such as `%0A` and `%AZP25`.

Emit exactly one physical line with LF framing and no BOM. Fixed header/order:

```text
##vso[task.setvariable variable=NAME;isOutput=BOOL;isReadOnly=BOOL;]VALUE
##vso[task.logissue type=SEVERITY;sourcepath=FILE;linenumber=N;columnnumber=N;code=CODE;]MESSAGE
```

BOOL is `true` when its flag is present, otherwise `false`. SEVERITY is fixed by
the selected command. Optional issue properties are omitted when absent;
remaining properties retain the shown order and trailing semicolon. NAME is
validated ASCII, not a raw header fragment.

## Consumer effects and limits

Shoutx success means the prepared bytes were written, not that Azure accepted
the operation. Command processing, settable-variable restrictions, read-only
state, variable scope and service quotas are caller/provider conditions.
`--output` selects Azure's output-variable semantics; the workflow must name
the producing step and use the correct dependency mapping.

This increment sets **non-secret variables only**. Do not pass secrets or assume
they will be masked. Issue messages are intentionally logged. Azure may mask,
truncate, format or translate issue content/locations after decoding; exact
parser fields do not promise pixel-identical UI output. An error issue is not
a substitute for explicitly propagating a failing process status.

Inputs must reach shoutx as data. Do not insert untrusted `$(variable)` or
template expressions into shell source; map them through `env:` and quote
shell expansions. Keep native stdout connected directly to the Agent command
stream, disable tracing around sensitive data, and propagate shoutx failures.
The writer does not sanitize other process output or authorize later shell use.

## Verification

- Exact CLI bytes, argv/stdin parity, missing/duplicate/unknown options, `--`,
  help/version, invalid UTF-8/NUL, all field limits and empty stdout on failure.
- Literal escapes, CR/LF, header delimiters, embedded command prefixes, leading
  combining/default-ignorable characters and multilingual/emoji samples.
- Generated Unicode cases parsed with the pinned upstream `Command.TryParse`
  and `CommandStringConvertor`, checking command identity, exact property map,
  exact data and a single physical output line. Include a negative control with
  percent decoding disabled, not a claim of support for that configuration.
- Hosted next-step variable equality (including multiline and output mapping),
  absence of a sentinel second variable, and exactly the requested issue type
  and metadata. Use synthetic non-secret inputs only; record Agent/image
  identities. A local parser check cannot satisfy this hosted gate.
- Existing GitHub command bytes and tests remain unchanged.
- PATH: both dialect grammars, exact argv/stdin bytes, native selector isolation,
  final-newline and list-separator rejection, raw limits and empty-stdout errors.
  Parse producer output using the pinned upstream parser with exact event,
  empty property map and unchanged decoded data. On both hosted generations,
  verify next-task PATH against the original PATH plus the expected prefix,
  exact repeat registration, distinct-ASCII ordering and lookup/execution of a
  caller-owned native fixture binary. Include Unicode and literal-escape paths;
  verifier negative controls must catch altered, missing and additional entries.
  These finite cases do not establish portable duplicate equivalence.
