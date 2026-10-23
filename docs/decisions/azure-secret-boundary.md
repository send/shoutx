# Azure secret boundary discussion

Status: Proposed

## Context

The maintainer deferred secret implementation on 2026-10-24 while PATH proceeds.
This record is the single home for the unresolved secret-boundary discussion;
it does not introduce a command or change the existing non-secret variable
contract. The implementation handoff links here instead of repeating it.

## Decision drivers

Provider limitations alone do not justify accepting a value that cannot receive
the protection promised by shoutx. Start with a concrete disclosure path and
the protected value, not a proof over all character sets or an audit of Agent,
.NET or ICU. Reuse existing Azure parser and hosted evidence where relevant;
neither proves secret registration or redaction by itself.

Prefer lossless protocol escaping when it preserves the value and closes the
path. Consider rejection before stdout when it cannot. Explicit sanitization
remains an option when necessary and justified by user value and cost; it is
not prohibited merely because the provider owns the consumer implementation.
Do not silently change a secret or declare it protected merely because an
altered value was registered.

## Questions to resolve before implementation

1. **Original-value protection.** Which accepted values can be registered
   faithfully and actually redacted in the supported log path? Separate
   framing/decoding failures, registration restrictions, and log processing.
   Specify rejection conditions for known unprotectable inputs, including
   whether empty, short, multiline or structured values need special treatment.
   These are investigation categories, not claims of discovered vulnerabilities.
2. **Fragments and representations.** Distinguish a registered secret appearing
   within a larger log line from a fragment of that secret appearing alone.
   Identify concrete workflows that print fragments or transformed values.
   Decide what additional registration, rejection or explicit interface can
   usefully cover; do not register every possible substring or promise all
   future transformations are protected.
3. **Sanitization and identity.** Separate registering extra representations of
   the original value from replacing the actual secret with a sanitized value.
   The latter is meaningful only if the caller can use that same replacement
   at the real consumer. Existing credentials cannot generally be changed by a
   masking writer. Determine the interface, collision/semantic effects and
   value-delivery requirements before adopting any transformation.
4. **Timing and transport.** Input restrictions cannot erase a disclosure that
   happened before invocation. Determine registration ordering and safe input
   delivery requirements. Shoutx must not introduce disclosure through its own
   output framing, diagnostics, validation or failure behavior. Do not treat
   retrospective cleanup as an encoder capability.
5. **Separate operations.** Evaluate mask registration and secret-variable
   assignment separately, including scope, mapping, flags and read-only/output
   interactions. A shared encoder does not establish equivalent consumer effects.
6. **Acceptance evidence.** Define synthetic-secret tests for exact registration,
   absence of extra operations, subsequent log redaction and negative controls.
   Observe the actual consumer effect rather than producer success alone. No
   real credentials belong in fixtures, logs or review inputs.

## Decision gate

Before implementing secret support, present the maintainer with the protected
asset, concrete attack paths, accepted/rejected inputs, any explicit
transformation, caller preconditions and finite verification plan. The boundary
is not yet agreed; do not convert this discussion into a blanket exclusion for
all provider masking limitations. Keep accepted contracts in the command
specification and observations in the compatibility record after approval.

New concrete attack details must follow SECURITY.md and confidential durable
tracking, not public issues or this public discussion record. Keep the public
record at the level of design questions and agreed policy.

## References

- [Existing Azure contract](../commands/azure-pipelines.md)
- [Existing Azure evidence](../compatibility/azure-pipelines.md)
- [Azure logging commands](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops)
- [Security reporting](../../SECURITY.md)
