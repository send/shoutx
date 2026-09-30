#!/usr/bin/env bash
# Print only a fixed boolean for the workflow's run_ci output.
set -euo pipefail
case "${EVENT_NAME:-}" in
  schedule|workflow_dispatch) echo true; exit 0 ;;
  push)
    if [[ "${BASE_SHA:-}" =~ ^0+$ ]]; then echo true; exit 0; fi
    range="${BASE_SHA:-}..${HEAD_SHA:-}"
    ;;
  pull_request) range="${BASE_SHA:-}...${HEAD_SHA:-}" ;;
  *) echo true; exit 0 ;;
esac
if [[ -z "${BASE_SHA:-}" || -z "${HEAD_SHA:-}" ]]; then echo true; exit 0; fi
set +e
git diff --quiet "$range" -- . \
  ':(exclude)AGENTS.md' ':(exclude)README.md' ':(exclude)SECURITY.md' \
  ':(exclude)docs/**' 2>/dev/null
status=$?
set -e
case "$status" in
  0) echo false ;;
  *) echo true ;; # Includes unknown history: never silently omit full CI.
esac
