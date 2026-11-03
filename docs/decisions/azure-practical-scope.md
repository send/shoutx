# Azure practical scope

Status: Accepted, 2026-11-03. Release preparation remains on hold.

## Context and decision

The ordinary-script boundaries selected in the previous implementation sequence
are implemented, including report and task-log publication in PR #152. A longer
command list alone would not establish greater practical value or safety.
The maintainer selected consolidation of the supported subset and its usage
examples before any further expansion.

The [coverage inventory](../azure-coverage.md) is the sole owner of individual
covered, deferred and outside dispositions and their reconsideration criteria.
Use official artifact tasks for ordinary publication; defer distinct progress,
completion text, section, extension-attachment and build-log writers until a
concrete workflow requires their particular effect. This does not assert that
these fields have no injection risk or that alternatives have identical effects.

## Consequences

Make the current subset usable through a command-selection guide and native
Bash/PowerShell examples, linking to existing command contracts and compatibility
evidence. Do not change accepted inputs, output bytes, deployment conditions or
secret-delivery examples while consolidating documentation. Preserve the known
provider limitations and distinguish a successful write from provider completion.

Practical scope is limited to the design-owned profile and named boundaries.
It is not a general Azure security guarantee, a release decision, or a promise to
support every logging command. New needs follow the inventory's reconsideration
criteria; new sensitive attack details follow SECURITY.md privately.
