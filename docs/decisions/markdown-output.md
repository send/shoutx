# Markdown output decision

This decision records why no generic Markdown writer is currently planned.

## Decision

`markdown:text` is not a v1.0 candidate. GitHub documents job summaries as
[GitHub Flavored Markdown][job-summaries], and its documented
[markup pipeline][github-markup] applies HTML sanitization before rendered
content is displayed. A value written to `$GITHUB_STEP_SUMMARY` does not feed
records back into the runner command protocol. Under the current threat model,
there is therefore no comparable workflow-execution injection boundary for a
generic Markdown encoder to protect.

Attacker-controlled Markdown can still mislead readers, contain links, alter
document structure, mention users, or disclose a value that the workflow chose
to publish. Those are content-policy and data-flow concerns rather than the
record-injection problem addressed by the implemented writers. Preserving
normal Markdown usability while distinguishing malicious from intended content
also requires application-specific policy.

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
