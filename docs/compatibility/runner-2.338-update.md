# Runner v2.338.0 compatibility update

Status: verification in progress; not release admission.

This separately reviewed update advances the test consumer from v2.337.0 to
v2.338.0 without changing shoutx production behavior, accepted inputs, or the
[supported profile](../design.md#stdout-adoption-contract). Historical evidence
keeps its original versions. The [package pins](../../tests/runner-package/pins.json)
own current package/runtime identities; the [oracle metadata](../../tests/runner-oracle/README.md)
owns the source-built test consumer.

## Identity and bounded source review

On 2026-10-17, the official [Runner release](https://github.com/actions/runner/releases/tag/v2.338.0)
resolved to `197ca027b90de199464dee3bb9ff198a1db60967`. The selected Linux x64,
macOS arm64 and Windows x64 asset sizes and SHA-256 digests were taken from its
release API and matched the release notes. The package harness independently
checks downloaded bytes before extraction or execution.

The source requires SDK 8.0.425. Package verification requires runtime 8.0.31
at `1219a42122cf5190c7f512850557e38c422430dc` and checks actual loaded assembly
identities, rather than inferring runtime identity from the SDK version.

The [surface audit](github-actions-surface-audit.md) records unchanged command,
file-command, artifact and extension-registration sources. `HostContext.cs`
(including mask encoders) and `Handlers/Handler.cs` (PATH composition) are also
unchanged between the two checkouts. Existing fixtures remain applicable.

The four runtime sources already consumed by the package probe are byte-identical
between its retained 8.0.30 commit and the new 8.0.31 commit: `CompareInfo.Icu.cs`,
`Interop.ICU.cs`, `pal_icushim.c`, and `pal_collation.c`. Their SHA-256 digests
remain unchanged in the pins. This supports updating the existing research
probe's exact-runtime guard without weakening its identity or layout checks;
it is not a new proof of runtime/ICU safety. No additional internal investigation
or acceptance-table regeneration is part of this update.

## Verification and limits

Retain the existing four-OS source/package and Unicode-policy jobs, controlled
Invariant/en-US configurations, producer checks, artifact declaration/list
effects, and independent hosted mask/annotation log checks. Dedicated log and
matcher workflows separately check their live effects. Hosted Worker versions
are observations, not versions selected by these package pins.

Local source-oracle execution on 2026-10-17 passed all 69 tests with SDK 8.0.425
and runtime 8.0.31. Fresh nonempty corpora covered all implemented families.
The no-default-features Cargo suite, package harness's 21 unit tests, CI scope
tests, trusted-log verifier unit tests, and stable-document checks also passed.
GPT-6 Sol's independent review found two stale documentation references; both
were corrected without changing the test gates or producer behavior.

Fresh hosted run identities and results will be recorded after verification.
The local macOS arm64 package probe also passed both cultures with 806 mask
and 2,781 annotation cases each, loaded runtime 8.0.31 at the pinned commit,
and ICU 78.1. These finite package cases do not override the retained broader
data-start-policy mismatch on this excluded local configuration.

The first hosted CI attempt exposed an offline fixture that assumed the old
pin was always current when asserting the drift summary's `MATCH` label.
The fixture now reads the current reviewed version; explicit `9.9.9` mismatch
and malformed/incomplete controls remain. No live mismatch is suppressed.
Local macOS 26 is outside the supported profile and cannot substitute for the
macOS 15 hosted row. A passing update PR is not final-source release admission;
the [release checklist](../release.md#next-release-preparation) still applies.
