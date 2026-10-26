# Azure build metadata writers

Status: Proposed; implementation authorized. Verification status belongs in the compatibility record.

## Context and decision

The maintainer selected build numbers and tags from the
[coverage inventory](../azure-coverage.md). Dedicated writers keep tool-derived
metadata in the selected operation without a raw command-name interface.
The [command contract](../commands/azure-pipelines.md#build-metadata) owns the
input and wire rules. Existing Azure encoding is reused; GitHub start-character
restrictions are not imported.

Reject input that would require implicit trimming or renaming. Keep Unicode
data rather than imposing an ASCII/language allowlist. Number validation follows
the documented naming restrictions; its ceiling is exact under a UTF-16
interpretation of the documented character limit, tested at the boundary in the
hosted fixture. The same bounded ceiling for
tags is a producer policy, not a claim about the service's maximum.

The design profile selects the Agent's body-based API because the legacy path
route does not reliably preserve reserved URL characters. The
[source observations](../compatibility/azure-pipelines.md#build-metadata-source-observations)
own this evidence. Caller authorization and provider tag equivalence remain
separate from lossless submission of one requested tag.

## Verification requirements

Use exact producer bytes and the existing pinned source parser, then actual
service metadata on the existing native profile. Serialize number updates and
check each effect before the next update; parallel jobs must not overwrite a
shared number under test. Check tag set differences, not merely membership of
one expected tag. Synthetic rejected input stays captured off the Agent stream.
Offline mutations must demonstrate that missing, changed and extra effects fail.

## Reconsideration conditions

A concrete service mismatch requires a scoped contract/test correction, not a
runtime audit or silent loss. A need for larger tags, explicit normalization,
legacy API support or other metadata commands is a separate decision. This
increment does not authorize publication or merge.
