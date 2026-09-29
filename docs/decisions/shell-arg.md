# POSIX shell-word encoder decision

Status: Deferred

This decision records why the former `shell:arg` candidate is deferred.

## Decision

`shell:arg` is not a v1.0 candidate. A portable encoder can represent one
strict UTF-8 value as POSIX shell source by surrounding it with single quotes
and representing each embedded apostrophe outside the quoted region. POSIX,
Bash, and dash all define single quotes as preserving literal characters other
than an embedded single quote. The encoding algorithm is therefore not the
blocking issue.

The missing piece is a safe and natural consumption boundary. Shell command
substitution performs expansion after the surrounding command has already been
tokenized. Quote characters produced by `$(shoutx shell:arg VALUE)` are data,
not source-level quoting syntax: unquoted substitution remains subject to field
splitting and pathname expansion, while double-quoted substitution passes the
encoder's quote characters literally. Command substitution also removes
trailing newlines. Consequently, neither form consumes a generated shell word
as one argument.

The encoded result is useful only when incorporated into shell source that is
parsed later, such as a generated script or a string passed to another shell.
That use requires a trusted source composer to provide token separation,
command structure, output framing, and exactly one later parse. A one-word CLI
cannot enforce those conditions. Encouraging callers to recover the missing
parse with `eval` would directly conflict with the project's exclusion of
dynamic shell evaluation and would make nested parsing easy to introduce.

For ordinary GitHub Actions steps, pass runtime data through `env:` and expand
it as `"$VALUE"`. Other programs should prefer an argv-capable API over shell
source generation. Reconsider a shell encoder only with a concrete source-file
or protocol destination, a named dialect, and a composition contract that does
not rely on `eval`; a generic `shell:arg` command is too easy to consume
incorrectly.

This decision follows the [POSIX shell command language][posix-shell-language]
expansion order and quote-removal rules, the [Bash expansion
documentation][bash-shell-expansions], and the [dash manual][dash-manual].

[posix-shell-language]: https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html
[bash-shell-expansions]: https://www.gnu.org/software/bash/manual/html_node/Shell-Expansions.html
[dash-manual]: https://manpages.debian.org/unstable/dash/dash.1.en.html
