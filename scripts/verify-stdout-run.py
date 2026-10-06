#!/usr/bin/env python3
"""Trusted default-branch verification of one completed full CI attempt.

No triggering revision, executable, artifact or script is executed. API/log
contents are input data only. Reports never include raw logs or canary values.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hosted", ROOT / "tests/workflow-smoke/hosted_boundaries.py")
hosted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)

PROFILE = {
    "ubuntu-22.04": ("linux-x64", "Linux", "X64", r"ubuntu22"),
    "ubuntu-24.04": ("linux-x64", "Linux", "X64", r"ubuntu24"),
    "macos-15": ("osx-arm64", "macOS", "ARM64", r"macos15"),
    "windows-2025": ("win-x64", "Windows", "X64", r"win25(?:-[A-Za-z0-9_.]+)?"),
}
ORDINARY = {
    "ubuntu-latest": ("Linux", ("BASH_Linux", "SH_Linux", "DASH_LINUX")),
    "macos-latest": ("macOS", ("BASH_macOS", "SH_macOS")),
    "windows-latest": ("Windows", ("PWSH_WINDOWS", "GIT_BASH_WINDOWS")),
}


def require(condition):
    if not condition:
        raise ValueError("incomplete or mismatched verification evidence")


def source_identity(run, repo, run_id, attempt, sha):
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0)
    require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha))
    require(run["id"] == run_id and run["run_attempt"] == attempt and run["head_sha"] == sha)
    require(run["event"] in ("push", "schedule", "workflow_dispatch"))
    require(run["head_branch"] == "main" and run["head_repository"]["full_name"] == repo)
    require(run["repository"]["full_name"] == repo)
    require(run["path"] == ".github/workflows/ci.yml")
    require(run["status"] == "completed" and run["conclusion"] == "success")


def job_inventory(jobs, run_id, attempt, sha):
    by_name = {}
    for job in jobs:
        require(job["name"] not in by_name)
        by_name[job["name"]] = job
    # Docs-only runs are successful CI, but are explicitly not admission evidence.
    parents = ("test", "runner-differential", "unicode-policy")
    if any(name in by_name for name in parents):
        require(all(name in by_name and by_name[name]["conclusion"] == "skipped" for name in parents))
        require(not any(name.startswith(("test (", "runner-differential (", "unicode-policy /"))
                        for name in by_name))
        return None
    required = ["stable-docs", "changes", "dependencies", "msrv", "hosted-annotations", "CI result"]
    required += [f"test ({label})" for label in ORDINARY]
    required += [f"runner-differential ({label}, {row[0]})" for label, row in PROFILE.items()]
    required += [f"unicode-policy / candidate ({label})" for label in PROFILE]
    # Reject added/missing matrix rows, not merely a passing subset.
    for prefix in ("test (", "runner-differential (", "unicode-policy /"):
        require({name for name in by_name if name.startswith(prefix)} ==
                {name for name in required if name.startswith(prefix)})
    for name in required:
        job = by_name[name]
        require(job["status"] == "completed" and job["conclusion"] == "success")
        require(job["run_id"] == run_id and job["run_attempt"] == attempt and job["head_sha"] == sha)
        require(type(job["id"]) is int and job["id"] > 0)
    return by_name


def profile_identity(report, label):
    _, runner_os, architecture, image = PROFILE[label]
    identity = report["identity"]
    require(identity["RUNNER_OS"] == runner_os and identity["RUNNER_ARCH"] == architecture)
    require(re.fullmatch(image, identity["ImageOS"]) is not None)


def api(repo, suffix, *, pages=False, raw=False):
    args = ["gh", "api"]
    if pages:
        args += ["--paginate", "--slurp"]
    result = subprocess.run(args + [f"repos/{repo}/{suffix}"], capture_output=True, timeout=90)
    require(result.returncode == 0)
    return result.stdout.decode("utf-8") if raw else json.loads(result.stdout)


def verify_job(repo, job, runner_os, run_id, attempt, sha):
    check_url = job["check_run_url"]
    match = re.fullmatch(rf"https://api\.github\.com/repos/{re.escape(repo)}/check-runs/([0-9]+)", check_url)
    require(match is not None)
    for retry in range(6):
        try:
            raw = api(repo, f'actions/jobs/{job["id"]}/logs', raw=True)
            pages = api(repo, f"check-runs/{match.group(1)}/annotations?per_page=100", pages=True)
            annotations = [item for page in pages for item in page]
            report = hosted.verify(raw, annotations, runner_os, str(run_id), str(attempt), sha, sha)
            # Retain existing ordinary shell mask leakage checks for every log.
            require(not re.search(r"shoutx-mask-(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", raw))
            report["jobId"] = job["id"]
            report["annotationsSha256"] = hashlib.sha256(json.dumps(annotations, sort_keys=True).encode()).hexdigest()
            return report, raw
        except (ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            if retry == 5:
                raise
            time.sleep(10)


def verify_run(repo, run_id, attempt, sha):
    source_identity(api(repo, f"actions/runs/{run_id}"), repo, run_id, attempt, sha)
    pages = api(repo, f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100", pages=True)
    jobs = job_inventory([job for page in pages for job in page["jobs"]], run_id, attempt, sha)
    result = {"schema": 1, "status": "not-exercised", "sourceRepository": repo,
              "sourceRunId": run_id, "sourceRunAttempt": attempt, "sourceHeadSha": sha,
              "verifierSha": os.environ["GITHUB_SHA"],
              "verifierRunId": int(os.environ["GITHUB_RUN_ID"]),
              "verifierRunAttempt": int(os.environ["GITHUB_RUN_ATTEMPT"])}
    if jobs is None:
        return result
    result["ordinary"] = {}
    result["profile"] = {}
    for label, (runner_os, sentinels) in ORDINARY.items():
        report, raw = verify_job(repo, jobs[f"test ({label})"], runner_os, run_id, attempt, sha)
        for sentinel in sentinels:
            require(f"SHOUTX_MASK_{sentinel}_BEGIN***_END" in raw)
        result["ordinary"][label] = report
    for label, (rid, runner_os, _, _) in PROFILE.items():
        report, _ = verify_job(repo, jobs[f"runner-differential ({label}, {rid})"],
                               runner_os, run_id, attempt, sha)
        profile_identity(report, label)
        result["profile"][label] = report
    # A rerun starting during verification invalidates this attempt's result.
    source_identity(api(repo, f"actions/runs/{run_id}"), repo, run_id, attempt, sha)
    result["status"] = "passed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('{"status":"failed"}\n')
    try:
        repo = os.environ["GITHUB_REPOSITORY"]
        require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None)
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        run = event["workflow_run"]
        result = verify_run(repo, run["id"], run["run_attempt"], run["head_sha"])
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print("Stdout compatibility verification: " + result["status"])
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
        print("Stdout compatibility verification failed; inspect source CI evidence.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
