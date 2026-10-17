# v1 CLI review

Status: Accepted for candidate preparation; not release authorization.

## Decision

Retain the current typed command surface for a v1 candidate. No new writer or
breaking CLI redesign is justified by this review. The
[design](../design.md#v1-readiness) owns coverage and the
[compatibility baseline](../design.md#v1-cli-compatibility-baseline);
[command specifications](../design.md#command-specifications) remain the only
destination-specific contracts. The [release checklist](../release.md#next-release-preparation)
separates remaining publication work from missing product capability.

## Review and rationale

The review used the command table and parser in `src/cli.rs`, input acquisition
and dispatch in `src/main.rs`, each command contract, the help golden,
`tests/*_contract.rs`, and `tests/stable_surface.rs` on main after PR #127.
It covered all fourteen commands, including each artifact/removal mode.
The following differences are intentional, not reasons to force one grammar:

| Family | Why the existing distinction is retained | Contract |
| --- | --- | --- |
| output / env / state | Names are structural fields; options end at NAME. Only these writers offer explicit lossy line modes and exact multiline framing. | [Named records](../commands/github-actions-records.md) |
| path | Adds a command-lookup entry, so absolute target-dialect paths and PATH-separator controls are required. | [PATH](../commands/github-actions-path.md) |
| mask | Empty/whitespace-only input cannot register a mask; accepted input must not be silently changed. | [Mask](../commands/github-actions-mask.md) |
| notice / warning / error | Metadata is structured and independently validated; message limits and empty rejection reflect annotation effects, not a general logging rule. Error severity does not set process failure. | [Annotations](../commands/github-actions-annotations.md) |
| debug / group / endgroup | Debug permits decoded line breaks; group is a single-line title; endgroup is a fixed no-input operation. | [Log commands](../commands/github-actions-log-commands.md) |
| artifacts file / oci | Explicit modes prevent scheme guessing; OCI needs two argv operands, unlike the optional single file value. | [Artifacts](../commands/github-actions-artifacts.md) |
| add-matcher / remove-matcher | File data and owner metadata cross different fields. Removal mode is explicit; owner tails need not inherit annotation's historical restriction. | [Matchers](../commands/github-actions-problem-matchers.md) |

All families retain strict input encoding, bounded fields, value-free diagnostics,
pre-output validation and the shared status classes. A literal `-` is not a
stdin sentinel. `--` is used before dash-leading optional values, but does not
precede a required artifact/removal mode. Equals-style options are not inferred
from the one documented named-writer separator form. Early help/version behavior
is retained rather than redesigned at the stability boundary.

The review found documentation overgeneralizations, not a need to change
production behavior: single-value acquisition was described as universal,
workflow-command fidelity mentioned only data rather than properties, and
some release/status prose predated the newer writers. Correct the owning
documents and references rather than adding a competing global command spec.

## Consequences and reconsideration

Source usability is not a released installation: the new writers are absent
from v0.3.0. Keep working installation examples pinned to released versions and
label source-only examples until a release includes them. Preparing v1 is
reasonable only with the declared consumer scope; do not expand it to all
self-hosted configurations or repair dependencies as a prerequisite.

The [surface audit](../compatibility/github-actions-surface-audit.md) found a
newer Runner release requiring a separately reviewed compatibility update.
Identical output-handler source is useful scope evidence, not runtime admission.
Reconsider this decision if that verification exposes a concrete boundary
failure, an official new output destination reveals a useful unimplemented
writer, or practical use exposes an incompatible CLI requirement. Do not reopen
completed Unicode investigations without such evidence.
