# Azure secret variable design

Status: Accepted on 2026-10-27; prior-mask revision accepted on 2026-10-28.
Implementation and hosted admission are in progress.

## Purpose and ownership

Runtime credentials need both a named value for later tasks and a secret flag;
mask registration alone does not provide assignment. Use a dedicated writer
whose [contract](../commands/azure-pipelines-secret-variable.md) owns
CLI rules and the finite admission plan. The existing
[mask decision](azure-secret-boundary.md) remains authoritative for registration
rationale; [source observations](../compatibility/azure-pipelines.md#secret-variable-source-observations)
own external behavior. No existing CLI is changed by this decision.

## Choices and alternatives

A dedicated destination makes the secret boundary explicit and keeps values out
of argv. Adding a toggle to the existing argv-capable variable writer would make
the input channel depend on a flag and complicate misuse diagnostics. An implicit
mask-plus-variable sequence adds partial effects and is not a substitute for
verifying the actual secret assignment handler. The approved revision makes
prior masking explicit in the command contract: protect both the original and
wire representations before assignment, while retaining separate assignment
and propagation gates. Partial masking effects are accepted without promising
a transaction or changing the credential.

Include explicit output and read-only options: runtime credentials are useful
across authorized jobs/stages, and callers may request protection from accidental
overwrites. Excluding output merely to reuse same-job mask evidence would leave
that practical use unanswered. These options request Azure behavior; they do
not turn a workflow-controlled mapping into isolation from the workflow author.

Reject multiline values rather than enabling an explicitly unsafe consumer knob
or silently altering credentials. Whole single-line values retain Unicode and
short-value utility under the existing mask conditions. Reject `$(` anywhere
because variable expansion can change the value after assignment; encoding the
logging-command layer does not neutralize the variable layer. The restriction
is explicit and bounded, not a language or general punctuation allowlist.

The semantic cap is deliberately below the documented Windows per-variable
ceiling, leaving substantial room for naming/termination and avoiding the known
impossibility of a 1 MiB environment value. It is a useful producer policy, not
the maximum Azure permits. The [capacity observations](../compatibility/azure-pipelines.md#secret-variable-source-observations)
own the source limits; native admission still verifies the actual environment
path rather than treating upper bounds as a service promise.
Managed variables, variable groups or Key Vault
remain preferable for already provisioned secrets; they do not replace the
runtime-created credential use case.

## Approval and reconsideration

The maintainer approved the dedicated interface, scope options, rejection policy
and finite admission plan. A confirmed inability to preserve a value
or protect a claimed channel requires evidence and an explicit design change.
Sanitizing a credential without issuer/consumer agreement changes the credential,
not its confidentiality. Alternate representations or multiline support need a
separate justified interface. Do not broaden this increment into secret storage,
arbitrary log sanitization or retrospective cleanup.
