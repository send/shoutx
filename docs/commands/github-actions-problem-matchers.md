# GitHub Actions problem matcher commands

Status: implementation contract; not yet exposed by the CLI or published.

This file owns observable behavior and command-specific verification. The
[decision](../decisions/github-actions-problem-matchers.md) owns rationale;
the [design](../design.md#stdout-adoption-contract) owns the consumer profile.

## Interface and input

```text
shoutx github-actions:add-matcher [PATH]
shoutx github-actions:remove-matcher owner [OWNER]
shoutx github-actions:remove-matcher file [PATH]
```

Remove requires one exact ASCII mode, `owner` or `file`, before reading a value.
Missing or unknown modes are usage errors. No mode inference or combined
owner/file request is supported. Add and each remove mode use the existing
single-value grammar: argv wins without reading stdin, otherwise bounded
non-terminal stdin is read. `--` ends options before the value; a lone `--`
selects stdin. Dash-prefixed values require `--`. Extra operands and unknown
options are usage errors. Help/version in option position return immediately,
ignoring later tokens as in existing commands; they are also accepted in place
of remove's mode. A value followed by help/version is an extra-operand error.
Terminal stdin without a value is status 2; invalid native text or observable
I/O errors are status 1. The shared failure and diagnostic contract applies.

All modes validate strict UTF-8, reject NUL and enforce the raw 1 MiB limit
before consuming at most one final CRLF, LF or CR as producer framing. The
semantic value must be nonempty. No other trimming, normalization, case folding
or substitution is performed. Internal CR/LF remain data and are encoded.

PATH uses the shared [Unicode data-start policy](github-actions-annotations.md#command-line-grammar-and-input),
not annotation length or whitespace-only rules. Relative and absolute text
paths are accepted without opening, resolving or checking their existence.
The caller must select an authorized configuration and target-platform path;
shoutx does not certify that an accepted string names a valid file on that OS.

OWNER is one text property, not a path or a data-region value. It does not use
the data-start table. A leading `=` is rejected because the Runner's
empty-entry-removing property split cannot preserve it reliably. Other non-NUL
Unicode scalars, including whitespace and Unicode property tails, are preserved
after the single producer-framing boundary described above. The final
structural comma below prevents property-region trimming from removing trailing
owner whitespace. This is deliberately independent of annotation metadata's
historical trailing-whitespace restriction.

## Output and responsibility

Success emits one UTF-8 LF-terminated command:

```text
::add-matcher::ENCODED_PATH LF
::remove-matcher::ENCODED_PATH LF
::remove-matcher owner=ENCODED_OWNER,:: LF
```

The owner form always ends its property region with one comma. The Runner
discards the empty property entry; it is not part of the owner and does not
create another property. No command accepts raw property names or syntax.
Path data encodes `%`, CR and LF as `%25`, `%0D` and `%0A`. Owner additionally
encodes `:` and `,` as `%3A` and `%2C`. Percent is encoded first, preserving
literal escape-looking text after decoding. Owner-form data is exactly empty;
file forms have no properties. Compute the full encoded size with checked
arithmetic before allocation; maximum expansion is three times the raw limit
plus fixed command framing. Complete validation and construction before stdout.

Keep stdout connected to the Runner command stream and command processing
active. Status 0 acknowledges writing only, not successful registration or
removal. The Runner loads JSON itself, resolves relative paths against the
workspace, and applies its configuration/owner semantics. Files may change
between registration and file-based removal. Removing by file selects the
owners in that file at removal time; it is not a remembered association with
the earlier add operation. Owner identity is ordinal case-insensitive in the
pinned consumer. A missing owner may be a no-op. These effects are not value
normalization performed by shoutx.

The writer protects the selected operation and exact decoded fields, not
authorization of a path, file contents, regex patterns, replacement/removal of
other owners, lifetime management or safety of later logs. It does not parse
matcher JSON, run the associated tool, or validate resulting annotations.
These commands permit echo and consumer diagnostics, so they are not a secret
channel. Consumer failures may mention paths or owners even though shoutx's
own diagnostics never reproduce them.

## Verification required before exposure

- Exact bytes, status and diagnostics for all three modes and both input sources;
  `--`, mode parsing, extra/missing operands, early help/version, dash values,
  argv precedence over invalid/nonterminating stdin, terminal and invalid handles.
- Empty, NUL, invalid UTF-8/native arguments, disallowed path starts and leading
  owner `=` reject before stdout. Raw limit minus one/at/plus one and worst
  expansion are covered without relying on OS argv limits for large values.
- Paths and owners across scripts, supplementary scalars, Unicode tails,
  whitespace, `%`, CR/LF, commas, colons, equals and both protocol-looking
  forms. Check owner trailing whitespace and the final comma independently;
  no inferred property behavior from annotation tests alone.
- Fresh producer records through the fixed actual V2 parser and handlers under
  Invariant and en-US: selected command, exact data and properties, actual
  registration from a synthetic trusted file, remove by owner and remove by
  file, and a distinct retained control. Include relative/absolute paths,
  consumer case-insensitive owner identity, echo and stopped/resumed processing.
- The declared four-profile hosted matrix must prove positive matching before
  removal and removal afterward, while an independent control matcher remains
  active. Use fixed simple patterns and synthetic public text. Missing evidence,
  disabled processing and failed registration must not pass as safe absence.
  Verify requested owner and file modes separately; retain run/source identity.
- Preserve existing command contracts, complete help/command table and packaged
  binary surface checks. No release or broadened consumer scope is implied.
