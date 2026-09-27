#!/bin/sh
set -eu

binary=$1
shell_under_test=${2:-sh}
tmp=$(mktemp -d "${TMPDIR:-/tmp}/shoutx-smoke.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

printf 'value\n' | "$binary" github-actions:output result >>"$tmp/single"
printf 'result=value\n' >"$tmp/expected-single"
cmp "$tmp/expected-single" "$tmp/single"

"$binary" github-actions:output empty >>"$tmp/empty"
printf 'empty=\n' >"$tmp/expected-empty"
cmp "$tmp/expected-empty" "$tmp/empty"

"$binary" github-actions:state GITHUB_ENV value >"$tmp/state"
printf 'GITHUB_ENV=value\n' >"$tmp/expected-state"
cmp "$tmp/expected-state" "$tmp/state"

printf 'value\r' | "$binary" github-actions:output --multiline result >>"$tmp/multiline"
header=$(sed -n '1p' "$tmp/multiline")
delimiter=${header#result<<}
if [ "${RUNNER_OS:-}" = Windows ]; then
  printf 'result<<%s\nvalue\r\r\n%s\n' "$delimiter" "$delimiter" >"$tmp/expected-multiline"
else
  printf 'result<<%s\nvalue\r\n%s\n' "$delimiter" "$delimiter" >"$tmp/expected-multiline"
fi
cmp "$tmp/expected-multiline" "$tmp/multiline"

if [ "${RUNNER_OS:-}" = Windows ]; then
  path_value='C:\tools'
else
  path_value='/opt/tools'
fi
printf '%s\n' "$path_value" | "$binary" github-actions:path >>"$tmp/path"
printf '%s\n' "$path_value" >"$tmp/expected-path"
cmp "$tmp/expected-path" "$tmp/path"

if "$binary" github-actions:path 'bad"path' >"$tmp/rejected-path"; then
  echo "error: unsafe path was accepted" >&2
  exit 1
fi
test ! -s "$tmp/rejected-path"

if "$shell_under_test" -c '
  set -e
  printf "a\nb\n" | "$1" github-actions:output result >"$2"
  : >"$3"
' _ "$binary" "$tmp/rejected" "$tmp/masked"; then
  echo "error: rejected shoutx invocation was masked" >&2
  exit 1
fi
test ! -e "$tmp/masked"
