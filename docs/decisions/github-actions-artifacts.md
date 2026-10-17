# GitHub Actions artifact declaration decision

Status: Accepted

## Decision

Implement a typed artifact declaration writer for the `$GITHUB_ARTIFACTS`
boundary. Observable behavior and command-specific acceptance tests are owned
by the [command specification](../commands/github-actions-artifacts.md).
This decision authorizes implementation, not publication of an unverified
command or a new release.

## Rationale

An attacker-controlled line break can add a subject to the job's declared
artifact set. Explicit file/OCI variants avoid scheme-free type guessing and
preserve the selected record kind. Framing protection does not authorize the
selected resource or establish its identity, trust, immutability, or digest.
The runner-managed artifact list is an input, not another writer destination.

The original hosted availability failure deferred implementation. The
[availability observations](../compatibility/github-actions-artifacts-availability.md)
now show successful actual file-subject processing on the sampled hosts, so
implementation can begin without repeating that exploratory probe. Consumer
verification on the claimed targets and the command-specific acceptance tests
must still pass before advertising support; sampled availability alone is not
support for every environment or OCI behavior.

## Consequences

Keep artifact validation separate from named records and PATH mutation. Reuse
bounded input acquisition, not PATH authorization or stdout annotation policy.
Use the actual pinned declaration/list handlers and native hosted integration
to verify producer records. No registry access, file hashing, filesystem
inspection, or hidden destination selection is added to shoutx itself.

Reconsider compatibility if actual consumer processing regresses; do not infer
availability from exposed variables or repair GitHub's service within shoutx.
