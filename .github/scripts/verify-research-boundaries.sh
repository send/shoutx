#!/usr/bin/env bash
# Same-job package/live observations; no raw logs or annotations are uploaded.
set -euo pipefail

: "${GH_REPO:?}" "${GH_TOKEN:?}" "${GITHUB_RUN_ID:?}" "${RUNNER_TEMP:?}"
research_dir=$(mktemp -d "$RUNNER_TEMP/shoutx-research-verify.XXXXXX")
inventory_ok=true
if ! gh api --paginate --slurp \
  "repos/$GH_REPO/actions/runs/$GITHUB_RUN_ID/jobs?filter=latest&per_page=100" \
  > "$research_dir/pages.json"; then
  inventory_ok=false
fi
if ! jq '[.[].jobs[]]' "$research_dir/pages.json" > "$research_dir/jobs.json"; then
  inventory_ok=false
fi

verify_row() {
  local os=$1 rid=$2 runner_os=$3 job job_id source_attempt check_id attempt
  if [[ "$inventory_ok" != true ]]; then return 1; fi
  job="runner-differential ($os, $rid)"
  # This function is called in a conditional: explicitly check every operation,
  # rather than relying on errexit (which is disabled in this context).
  jq -e --arg job "$job" \
    '[.[] | select(.name == $job)] | length == 1 and .[0].conclusion == "success"' \
    "$research_dir/jobs.json" >/dev/null || return 1
  job_id=$(jq -r --arg job "$job" '.[] | select(.name == $job) | .id' "$research_dir/jobs.json") || return 1
  source_attempt=$(jq -r --arg job "$job" '.[] | select(.name == $job) | .run_attempt' "$research_dir/jobs.json") || return 1
  if ! [[ "$job_id" =~ ^[0-9]+$ && "$source_attempt" =~ ^[1-9][0-9]*$ ]]; then
    return 1
  fi
  check_id=$(jq -r --arg job "$job" '.[] | select(.name == $job) | .check_run_url | split("/")[-1]' "$research_dir/jobs.json") || return 1
  if ! [[ "$check_id" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  for attempt in {1..6}; do
    if curl --fail --silent --show-error --location --max-time 30 \
        --header "Authorization: Bearer $GH_TOKEN" \
        --header 'X-GitHub-Api-Version: 2026-03-10' \
        "https://api.github.com/repos/$GH_REPO/actions/jobs/$job_id/logs" > "$research_dir/log.txt" &&
      gh api --paginate --slurp \
        "repos/$GH_REPO/check-runs/$check_id/annotations?per_page=100" > "$research_dir/annotations-pages.json" &&
      jq 'add' "$research_dir/annotations-pages.json" > "$research_dir/annotations.json" &&
      python -B tests/workflow-smoke/hosted_boundaries.py verify \
        --log "$research_dir/log.txt" --annotations "$research_dir/annotations.json" \
        --os "$runner_os" --job-id "$job_id" --source-attempt "$source_attempt" \
        --evidence "$RUNNER_TEMP/hosted-boundary-evidence/package-matched/$os.json"; then
      return 0
    fi
    echo "$job boundary evidence is incomplete (attempt $attempt of 6)"
    sleep 10 || return 1
  done
  return 1
}

output_dir="$RUNNER_TEMP/hosted-boundary-evidence/package-matched"
mkdir -p "$output_dir"
failed=false
for os in ubuntu-22.04 ubuntu-24.04 macos-15 windows-2025; do
  case "$os" in
    ubuntu-*) rid=linux-x64; runner_os=Linux ;;
    macos-15) rid=osx-arm64; runner_os=macOS ;;
    windows-2025) rid=win-x64; runner_os=Windows ;;
  esac
  printf '{"status":"failed"}\n' > "$output_dir/$os.json"
  if ! verify_row "$os" "$rid" "$runner_os"; then
    echo "Package-matched observation incomplete: $os"
    failed=true
  fi
done
if [[ "$failed" == true ]]; then exit 1; fi
