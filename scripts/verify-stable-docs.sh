#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/shoutx-docs.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

awk '
  /<!-- stable-command-surface:start -->/ { capture=1; next }
  /<!-- stable-command-surface:end -->/ { capture=0; next }
  capture && /^```text$/ { next }
  capture && /^```$/ { next }
  capture { print }
' "$root/README.md" > "$tmp/readme-help.txt"

cmp "$root/tests/fixtures/stable-help.txt" "$tmp/readme-help.txt"

python3 - "$root/README.md" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
fenced = False
marker = None
code = []
for line in text.splitlines():
    fence = re.match(r"^\s*(```+|~~~+)", line)
    if fence:
        token = fence.group(1)[0]
        if not fenced:
            fenced = True
            marker = token
        elif token == marker:
            fenced = False
            marker = None
        continue
    if fenced:
        code.append(line)
if fenced:
    raise SystemExit("README contains an unterminated fenced code block")

pattern = re.compile(
    r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]+:[A-Za-z0-9_-]+)"
    r"(?![A-Za-z0-9_-])"
)
commands = [match.group(1) for match in pattern.finditer("\n".join(code))]
stable = {
    "github-actions:output",
    "github-actions:env",
    "github-actions:state",
    "github-actions:path",
    "github-actions:mask",
    "github-actions:notice",
    "github-actions:warning",
    "github-actions:error",
}
if not stable.issubset(commands):
    raise SystemExit("README code blocks do not demonstrate every stable command")
unexpected = sorted(set(commands) - stable)
if unexpected:
    raise SystemExit(
        "README code block contains a command outside the stable surface: "
        + ", ".join(unexpected)
    )
PY
