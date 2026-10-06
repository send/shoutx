# Original-value Unicode acceptance for stdout commands

Status: Accepted; implemented by PR #116, not a stable-distribution decision.

## Decision

PR #116 expanded the then-isolated stdout feature using V2 framing, without adding
decoration, normalization or lossy sanitization. The command specifications own
the acceptance rules; the threat model owns AP1–AP5. This record owns rationale.

For message/mask starts, use a static positive set derived from the retained
full-scalar leading-mapping and grapheme-boundary observations, intersected
across the recovered reference data. Preserve the existing ASCII/escaped-line-
break path. The set is language-independent; later scalars are not checked
against this start predicate. Native runtime libraries and JSON parsing are not
added to shoutx. A generated range table provides bounded, allocation-free lookup.

Metadata uses its own existing property escaping and typed-field validation,
not the data-start table. TITLE/FILE are strict UTF-8 data; literal header
delimiters are escaped. The fixed command/property names and ordinal property
splits in the pinned parser keep content separate from property selection.
The locale-sensitive V2 separator search still requires integration testing;
message-start evidence alone does not validate a changed header.

Do not add a second character table merely because a scalar is unusual or fails
the data-start predicate. The existing oracle regression
`TrailingPropertyCollationMarksCanMoveTheAnnotationSeparator` demonstrates AP5
when an affected TITLE/FILE is the final property. Passing repetition tests
inside an ASCII wrapper or tests with a following numeric property does not
cover this boundary. The selected control terminates newly accepted Unicode
property regions with a structural comma. The pinned parser splits properties
ordinally on commas with `RemoveEmptyEntries`; the trailing empty entry is
discarded, not decoded into any value or property. That fixed punctuation also
separates the final Unicode value from the V2 separator. Existing ASCII records
remain byte-identical. Final-property tests cover both TITLE and FILE, with
transparent suffixes and with/without following numeric fields. This avoids a
second Unicode whitelist and does not sanitize, decorate or change user data.

The generated Rust ranges are reproducible from the checked-in, digest-identified
membership artifact. That artifact reuses existing research observations; its
derivation is not a new proof obligation for all native implementations. Updating
membership is a reviewed policy change, not an automatic Unicode/OS upgrade.
The source observations and target integration must both be reassessed for an
update; a passing renderer only proves faithful representation of the input set.

## Applicability and evidence

This implementation targets the named configurations in the
[candidate integration evidence](../compatibility/stdout-unicode-policy.md).
It does not infer a consumer culture from shoutx's process or promise future
Runner/ICU compatibility. The current local ICU78.1 data-start mismatch remains
contrary evidence for extending that scope. No dependency-internal proof is a
prerequisite for the producer implementation, and no known mismatch is erased.

Distribution was isolated when this decision was implemented. Its later
promotion is governed by the [framing decision](github-actions-stdout-framing.md)
and [release policy](../release.md), not this acceptance decision. PR #116 completed producer contract
tests, actual Runner effects, performance checks and review; the candidate
parser run alone was not completion. The current adoption scope is owned by the
[design](../design.md#stdout-adoption-contract), not by these implementation
observations.
