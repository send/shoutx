#!/bin/sh
set -eu

binary=$1
tmp=$(mktemp -d "${TMPDIR:-/tmp}/shoutx-smoke.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

printf 'value\n' | "$binary" github-actions:output result >>"$tmp/single"
printf 'result=value\n' >"$tmp/expected-single"
cmp "$tmp/expected-single" "$tmp/single"

"$binary" github-actions:output empty >>"$tmp/empty"
printf 'empty=\n' >"$tmp/expected-empty"
cmp "$tmp/expected-empty" "$tmp/empty"

printf 'value\r' | "$binary" github-actions:output --multiline result >>"$tmp/multiline"
header=$(sed -n '1p' "$tmp/multiline")
delimiter=${header#result<<}
if [ "${RUNNER_OS:-}" = Windows ]; then
  printf 'result<<%s\nvalue\r\r\n%s\n' "$delimiter" "$delimiter" >"$tmp/expected-multiline"
else
  printf 'result<<%s\nvalue\r\n%s\n' "$delimiter" "$delimiter" >"$tmp/expected-multiline"
fi
cmp "$tmp/expected-multiline" "$tmp/multiline"

if sh -c '
  set -e
  printf "a\nb\n" | "$1" github-actions:output result >"$2"
  : >"$3"
' _ "$binary" "$tmp/rejected" "$tmp/masked"; then
  echo "error: rejected shoutx invocation was masked" >&2
  exit 1
fi
test ! -e "$tmp/masked"
