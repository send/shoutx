# GitHub Actions log-mask command

This specification covers `github-actions:mask`. Cross-cutting product
invariants remain in [`design.md`](../design.md), and shared testing policy
remains in [`test-plan.md`](../test-plan.md). The Contract section is normative
for this command; contradictions with the cross-cutting documents must be
resolved.

The command is available only in source builds that explicitly enable
`unstable-github-actions-stdout`. It is absent from default and official release
binaries, and enabling it does not make the contract release eligible. The
isolation is defined by the [accepted decision](../decisions/unstable-github-actions-stdout.md),
while external parser evidence is maintained in the
[workflow-command compatibility note](../compatibility/github-actions-workflow-command-parser.md).
The contract below records research behavior rather than a stable CLI promise.

## Contract

`github-actions:mask [VALUE]` is intended to register one value with the
current job's runner-side secret masker by writing
one [`add-mask` workflow command][workflow-mask-command] to stdout. Unlike
environment-file writers, its successful stdout is intentionally consumed
directly by the runner and must not be redirected to an environment file.

The command follows the shared single-value source rule. An argv value wins and
stdin is not read; otherwise non-terminal stdin is read through EOF. `--` ends
option parsing and is required for a dash-prefixed argv value. There is no name
operand and there are no first-line, join, or multiline modes. The complete
semantic value is registered rather than normalized into a different secret.
As with the other stdin interfaces, at most one final CRLF, LF, or bare CR is
consumed as producer framing. All remaining CR and LF are value data.

Input is strict UTF-8, rejects NUL, and uses the standard 1 MiB input limit.
After optional producer framing, an empty value or a value consisting only of
Unicode whitespace is rejected before stdout begins. This mirrors the runner's
`String.IsNullOrWhiteSpace` rejection; accepting such a value locally would
report success without registering a mask. The whitespace classification is
the .NET 8 `Char.IsWhiteSpace` set, equivalent here to the Unicode
`White_Space` property. U+FEFF and U+200B are not whitespace under that rule.

After producer framing, apply the shared Unicode data-boundary policy
defined in the [annotation input policy](github-actions-annotations.md#command-line-grammar-and-input).
Reject a value outside the allowlist with status 1, empty stdout, and the fixed
diagnostic `mask value is outside the Unicode boundary policy`. The
[compatibility note](../compatibility/github-actions-workflow-command-parser.md)
records the observed delimiter failure and fallback. Do not delete, normalize,
or replace any scalar: registering a changed string would not faithfully mask
the original value. Scalars beyond the inspected prefix remain data.
Applicability is defined by the
[stdout adoption contract](../design.md#stdout-adoption-contract), not by the
allowlist alone. Shoutx does not detect or enforce consumer configuration;
failed recognition can leave the mask unregistered and expose the value. Known
excluded-configuration failures remain in the compatibility evidence.

Successful output is exactly:

```text
::add-mask::ENCODED_VALUE LF
```

The encoder applies replacements in this order: `%` with `%25`, CR with `%0D`,
then LF with `%0A`. No other character is escaped. This is the encoding used by
[`@actions/core.setSecret`][toolkit-command] and inverted by the runner's
workflow-command parser. Escaping `%` first prevents a literal sequence such as
`%0A` from becoming a line break during runner decoding. Encoding CR and LF
ensures the process emits one physical command line. When the runner recognizes
the intended V2 separator, later `::` is data; the current framing does not
establish that precondition across cultures.

The implementation computes the encoded length with checked arithmetic and
constructs the complete line before opening stdout for writing. The 1 MiB
input can expand to at most 3 MiB plus the fixed prefix and LF. GitHub documents
no separate dynamic-mask or workflow-command line limit, and the pinned runner
applies no explicit command-line length check before its stream reader, so this
is a shoutx resource limit rather than a provider-capacity promise. Large or
structured values remain discouraged under GitHub's
[secure-use guidance][secure-use]: runner registration derives multiple encoded
variants and exact-match redaction becomes less reliable when a value is
transformed.

On receipt, the runner registers both the exact decoded value and every
trimmed, nonempty item produced by splitting it on CR and LF. This occurs even
for a single-line value: registering ` secret ` also registers `secret`. It can
therefore broaden masking for both single-line and multiline values and is
runner behavior, not a shoutx normalization promise. Empty items and
whitespace-only items are not independently registered. Registration is
job-local and affects only subsequent runner output. The command itself is
configured not to echo its data; when workflow-command echoing is enabled, the
runner prints a masked placeholder.

The intended security property is structural integrity and faithful
registration of one accepted value while workflow-command processing is
active, within the design profile. This is not a universal-culture or
comprehensive confidentiality guarantee. In particular:

- output produced before registration remains visible;
- shell tracing, process inspection, audit logging, or a compromised runner
  can disclose the value before the runner masker sees it;
- transformed, split, or encoded forms are not necessarily masked unless the
  runner derives that exact form or the caller registers it separately;
- short or common values can over-mask unrelated log text;
- a culture-sensitive parse failure can make the runner log the command line
  itself as ordinary output, exposing the supplied value immediately without
  registering it; see the
  [workflow-command compatibility note](../compatibility/github-actions-workflow-command-parser.md);
- a preceding `stop-commands` command causes the runner to ignore `add-mask`
  until the matching resume token, causing the encoded command line itself to
  be logged as ordinary output; shoutx cannot observe that state; and
- values treated as secrets can be suppressed when exported as job outputs,
  even though GitHub documents same-job use through a step output.

Callers should pass sensitive values through stdin or a quoted environment
variable rather than placing them literally in process arguments. They must
ensure workflow-command processing is active and register a value before any
command can log it. A validation failure means no mask was registered; callers
must not log the rejected value or continue as though masking succeeded.
If an unmasked value has already reached a workflow log,
masking it later is not remediation; delete the log and rotate the credential.

### Implementation constraints

Keep the workflow-command data encoder separate from named-record framing and
do not generalize it into a raw workflow-command API.

[toolkit-command]: https://github.com/actions/toolkit/blob/a7911ca44eeaa6d87ad79a4703b750fb0993fb99/packages/core/src/command.ts
[workflow-mask-command]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#masking-a-value-in-a-log
[secure-use]: https://docs.github.com/en/actions/reference/security/secure-use

## Boundary-specific threat analysis

### Runner behavior and limitations

The [stdout threat inventory](../threat-model.md#stdout-mask-and-annotation-responsibility)
owns attack paths AP1/AP2/AP4. The contract above owns original-value registration
and encoding. Unlike annotation nonarrival alone, mask misrecognition can expose
the secret; successful registration of a changed string is not an adequate
substitute. Assess acceptance changes against those concrete paths within their
documented applicability conditions, not a requirement to certify every culture
or Runner dependency. The following are command-specific effects and limitations.

Mask registration is itself an integrity-sensitive operation, not authorization
to let untrusted input choose arbitrary masks. An attacker-selected value can
hide unrelated log substrings and can cause a matching job output to be
suppressed. The caller remains responsible for deciding which value should be
registered; shoutx only preserves and frames that choice.

The command rejects NUL, invalid UTF-8, empty values, and values consisting
only of Unicode whitespace before output begins. The last two cases are
necessary because the runner warns and performs no registration for
`String.IsNullOrWhiteSpace` data. A successful shoutx status must not imply a
mask was installed when the runner would deterministically reject it.
The prefix validation specified above is an additional, bounded research
mitigation; it is not a complete control for locale-sensitive parsing.

The runner registers the exact decoded value and also every trimmed, nonempty
item produced by splitting it on CR and LF. This applies even without a line
boundary, so ` secret ` additionally registers `secret`. It can mask more text
than the exact value alone; empty and whitespace-only items are not separately
registered. These derived masks are accepted destination behavior rather than
a transformation made or independently promised by shoutx.

Masking is prospective and best-effort. It does not protect a value logged
before registration, passed visibly in process arguments, exposed by shell
tracing or host audit facilities, transformed into an unregistered form, or
read by other code running with equivalent job privileges. Very short or
common values can redact unrelated text. If workflow-command processing has
been suspended with `stop-commands`, the runner ignores the candidate output;
the encoded command line is then handled as ordinary log output and can expose
the value. That hidden runner state cannot be detected by the child process and
active command processing is therefore an explicit precondition of the
registration guarantee.

GitHub permits a masked value to be placed in a step output for later use in
the same job, but the runner suppresses job outputs that its secret masker
recognizes. shoutx therefore makes no guarantee that a masked value can cross
job or workflow boundaries as an output.

## Command-specific verification

These cases define the compatibility suite for `github-actions:mask`.

#### Command grammar and input

Test `COMMAND VALUE`, `COMMAND -- VALUE`, and stdin when VALUE is omitted.
`--` is required for a dash-prefixed argv value; without it the token is an
unknown-option usage error. Reject extra operands and every line-mode option as
usage errors with status 2 and empty stdout. Help and version are recognized
only before VALUE. `COMMAND --` with no following operand selects stdin.

Apply the shared terminal, closed-handle, invalid-encoding, NUL, and 1 MiB input
cases. An argv value wins without reading stdin. For both argv and stdin,
consume at most one final CRLF, LF, or bare CR as producer framing and preserve
every remaining boundary. Exercise each final-boundary form through both input
sources, plus empty input, multiple final terminators, internal mixed
boundaries, and a final boundary following invalid UTF-8 or NUL. Empty semantic
values and values consisting only of the .NET 8 `Char.IsWhiteSpace` set fail
with status 1 and empty stdout. Cover ASCII whitespace, NEL, U+1680, the
U+2000--U+200A range, LINE SEPARATOR, PARAGRAPH SEPARATOR, U+202F, U+205F, and
U+3000. U+FEFF and U+200B are not whitespace, but are rejected at the data
boundary; preserve them after an allowed first scalar.

Through argv and stdin, cover every ASCII first byte and representative
non-ASCII first scalars, including Japanese, emoji, marks, and format characters.
Exhaustively check the shared allowlist over Unicode scalar values. Include
ordinary and `::` / `##[warning]`-looking suffixes; assert the exact fixed
diagnostic, status 1, and empty stdout on rejection. Preserve Unicode after
an allowed first scalar byte-for-byte.
Run the accepted mask corpus through the pinned runner under both Invariant
Culture and `en-US`, checking exact decoded data before mask registration.

#### Encoding and command structure

For every success, exact stdout is:

```text
::add-mask::ENCODED_VALUE LF
```

Test `%`, CR, LF, CRLF, every mixture of them, literal `%0A`, `%0D`, and `%25`,
leading spaces, `::`, strings beginning with another registered command, and
multibyte UTF-8. Assert the replacement order `%` to `%25`, CR to `%0D`, then
LF to `%0A`. Feed the result to the pinned runner parser and verify exactly one
recognized `add-mask` command whose decoded data equals the accepted semantic
value. The emitted bytes must contain no physical CR or LF before the final LF
and must not parse a second command.

Test 1,048,575, 1,048,576, and 1,048,577 raw input bytes before optional final
producer-boundary consumption, using both low-expansion and worst-case
`%`/CR/LF data. The first two succeed when otherwise valid and the last fails,
so specifically assert that a 1,048,576-byte semantic value followed by LF is
rejected before the framing boundary can be consumed. Verify checked encoded-
size calculation before allocation and the exact maximum output length. Do not
assert an undocumented GitHub command line limit.

#### Runner masking behavior

Use the actual pinned `AddMaskCommandExtension` and `SecretMasker`, not only a
local parser transcription. After registration, verify masking of the exact
value as a substring in later output. For every value, verify both the full
decoded value and each trimmed nonempty item from CR/LF splitting are
registered; this includes a single-line value with surrounding whitespace.
Blank and whitespace-only items remain unregistered. Include leading and
trailing whitespace on individual lines, overlapping values, a short common
value demonstrating intentional over-masking, and data for which the runner
derives Base64, JSON, URI, XML, command-line, and PowerShell representations.
The tests characterize those derived masks without making their complete set a
stable shoutx guarantee.

Enable workflow-command echoing and verify that command processing emits only
the masked placeholder, never the supplied value. Suspend command processing
with a valid `stop-commands` token, feed a shoutx mask record, and prove that it
is treated as ordinary output, can expose the encoded value, and installs no
mask; resume processing and prove normal registration works again. This is a
documented precondition, not a condition the shoutx process can detect.

Verify that a masked step output remains usable in a later step of the same job
using GitHub's documented pattern. Separately use a runner oracle to verify that
a matching job output is skipped as potentially secret. The product must not
promise cross-job propagation.

#### Process and workflow coverage

For every validation or size failure, assert empty stdout and a fixed stderr
diagnostic that contains neither the candidate value nor a derived excerpt.
Exercise broken-pipe and short-write behavior under the shared status contract.
Unlike environment-file writers, successful mask output is not redirected.

On every supported hosted OS and shell, register a unique generated marker and
then print it between fixed sentinel strings in a later command in the same
step. Inspect the completed job log through the GitHub API and require the
sentinel form containing `***`, without requiring the verifier to receive the
secret marker. A step cannot prove masking by inspecting its own still-open
log. Include stdin sourced from quoted environment variables and shell-local
variables, ensure shell
tracing is disabled, and do not place the marker literally in workflow source
or argv. Shell tests must also confirm that stdout uses one LF-terminated
command on Windows without depending on text-mode newline conversion.

The external verifier is a `workflow_run` workflow stored on the default
branch. It runs only for successful `push`, `schedule`, or `workflow_dispatch`
executions of CI on `main` from this repository, obtains
the completed log archive with read-only Actions permission, and never checks
out or executes code from the triggering revision. Runtime-generated values
remain unknown to the verifier: fixed per-OS and per-shell sentinels prove
replacement with `***`, while a missing sentinel distinguishes a setup failure.
Documentation-only CI runs, whose hosted test jobs are all skipped, are
recognized and skipped rather than treated as redaction evidence.
