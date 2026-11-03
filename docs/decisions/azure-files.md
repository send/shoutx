# Azure summary and log-file writers

Status: Accepted for implementation, 2026-11-03; unreleased.

Generated build reports and diagnostic files are useful remaining boundaries
in the Azure coverage inventory. Unlike GitHub summary-file contents, Azure
receives a path through its logging-command parser. A typed writer prevents
path data selecting another command or property while leaving file authority
with the caller. The [command contract](../commands/azure-pipelines-files.md)
is the sole source of CLI rules and finite admission requirements.

Use the documented task.uploadsummary/task.uploadfile shorthands, rather than
expose arbitrary attachment types/names. Both Agent handlers derive the name
from the path and delegate to the attachment helper; they select different
fixed types. No file reading or upload client belongs in shoutx.

Require native absolute file-path syntax and reject line breaks without
normalization. Reuse Azure encoding, not prependpath's list-separator policy:
these paths select one file rather than construct PATH. Preserve ordinary
Unicode and punctuation subject to native syntax. A syntactically valid path
is not an authorization decision or a guarantee of filesystem identity.

Do not expand the increment to artifact publishing, build.uploadlog, custom
attachment properties, Markdown sanitization or provider internals auditing.
The finite verification confirms named operations and intact uploaded synthetic
content; undocumented viewer features are observations, not new product gates.
