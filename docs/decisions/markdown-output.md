# Markdown output decision

Status: Accepted

This decision records why GitHub step-summary output and a generic Markdown
writer are outside `shoutx`'s current scope.

## Decision

`$GITHUB_STEP_SUMMARY` is out of scope, and `markdown:text` is not a v1.0
candidate. GitHub documents job summaries as [GitHub Flavored
Markdown][job-summaries], and its documented [markup pipeline][github-markup]
applies HTML sanitization before rendered content is displayed. The [pinned
runner][runner-step-summary] masks secrets and uploads the step-summary file;
it does not parse the file as command-file records. Under the current threat
model, there is therefore no comparable workflow-execution injection boundary
for a generic Markdown encoder to protect.

HTML sanitization does not make attacker-controlled Markdown trustworthy. It
can still mislead readers, contain links or images, alter document structure,
mention users, or disclose a value that the workflow chose to publish. Those
are content-policy and data-flow concerns rather than the record-injection
problem addressed by the implemented writers. Preserving normal Markdown
usability while distinguishing malicious from intended content also requires
application-specific policy.

This decision does not cover an unredirected process writing attacker-controlled
lines to the workflow log. The `add-mask` command is specified separately and
other GitHub Actions stdout workflow commands remain deferred. A future
Markdown feature requires a concrete threat and named rendering surface rather
than a renderer-independent promise. This conclusion is specific to
GitHub-rendered content and does not treat the same bytes as safe for arbitrary
Markdown or HTML renderers. Any reconsideration must explicitly address links,
images, mentions, Unicode controls, bidirectional text, and embedded HTML for
the selected surface.

[job-summaries]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
[github-markup]: https://github.com/github/markup#github-markup
[runner-step-summary]: https://github.com/actions/runner/blob/v2.337.0/src/Runner.Worker/FileCommandManager.cs
