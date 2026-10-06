#!/usr/bin/env python3
"""Read-only publication gate for source-bound, trusted stdout verification."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stdout_verifier", ROOT / "scripts/verify-stdout-run.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
require = verifier.require
LIMIT = 1024 * 1024


def request(repo, suffix, *, pages=False, binary=False):
    if binary:
        require(not pages)
        return verifier.download(repo, suffix)
    args = ["gh", "api"] + (["--paginate", "--slurp"] if pages else [])
    result = subprocess.run(args + [f"repos/{repo}/{suffix}"], capture_output=True, timeout=90)
    require(result.returncode == 0)
    return json.loads(result.stdout)


def read_report(archive):
    require(len(archive) <= LIMIT)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = bundle.infolist()
        require(len(entries) == 1 and entries[0].filename == "report.json")
        require(0 < entries[0].file_size <= LIMIT and not entries[0].is_dir())
        return json.loads(bundle.read(entries[0]))


def trusted_run(run, repo):
    require(run["path"] == ".github/workflows/verify-mask-logs.yml")
    require(run["event"] == "workflow_run" and run["head_branch"] == "main")
    require(run["repository"]["full_name"] == repo and run["head_repository"]["full_name"] == repo)
    require(run["status"] == "completed" and run["conclusion"] == "success")


def validate_report(report, source, trusted, repo):
    require(report["schema"] == 1 and report["status"] == "passed")
    require(report["sourceRepository"] == repo)
    for key, expected in (("sourceRunId", source["id"]), ("sourceRunAttempt", source["run_attempt"]),
                          ("sourceHeadSha", source["head_sha"]), ("verifierRunId", trusted["id"]),
                          ("verifierRunAttempt", trusted["run_attempt"]), ("verifierSha", trusted["head_sha"])):
        require(report[key] == expected)
    require(set(report["profile"]) == set(verifier.PROFILE))
    require(set(report["ordinary"]) == set(verifier.ORDINARY))
    for group in ("profile", "ordinary"):
        for label, row in report[group].items():
            require(row["status"] == "passed" and row["maskCases"] == 8 and row["annotationCases"] == 30)
            identity = row["identity"]
            require(identity["GITHUB_RUN_ID"] == str(source["id"]))
            require(identity["GITHUB_RUN_ATTEMPT"] == str(source["run_attempt"]))
            require(identity["GITHUB_SHA"] == source["head_sha"] == identity["SHOUTX_SOURCE_HEAD"])
            require(type(row["jobId"]) is int and row["jobId"] > 0)
            for field in ("logSha256", "annotationsSha256"):
                require(re.fullmatch(r"[0-9a-f]{64}", row[field]) is not None)
            if group == "profile":
                verifier.profile_identity(row, label)
            else:
                require(identity["RUNNER_OS"] == verifier.ORDINARY[label][0])


def check(repo, sha):
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None)
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None)
    runs = request(repo, f"actions/workflows/ci.yml/runs?head_sha={sha}&branch=main&per_page=1")["workflow_runs"]
    require(len(runs) == 1)
    source = runs[0]
    verifier.source_identity(source, repo, source["id"], source["run_attempt"], sha)
    pages = request(repo, f'actions/runs/{source["id"]}/attempts/{source["run_attempt"]}/jobs?per_page=100', pages=True)
    jobs = verifier.job_inventory([job for page in pages for job in page["jobs"]],
                                  source["id"], source["run_attempt"], sha)
    require(jobs is not None)
    name = f'stdout-verification-{source["id"]}-{source["run_attempt"]}-{sha}'
    pages = request(repo, f"actions/artifacts?name={name}&per_page=100", pages=True)
    artifacts = [item for page in pages for item in page["artifacts"] if item["name"] == name]
    require(bool(artifacts))
    # Only the designated default-branch workflow_run can supply this evidence.
    candidates = []
    for artifact in artifacts:
        run_id = artifact["workflow_run"]["id"]
        require(type(run_id) is int and run_id > 0)
        run = request(repo, f"actions/runs/{run_id}")
        if run["path"] == ".github/workflows/verify-mask-logs.yml" and run["event"] == "workflow_run":
            candidates.append((artifact, run))
    require(bool(candidates))
    artifact, trusted = max(candidates, key=lambda pair: pair[0]["id"])
    trusted_run(trusted, repo)
    require(not artifact["expired"] and 0 < artifact["size_in_bytes"] <= LIMIT)
    require(type(artifact["id"]) is int and artifact["id"] > 0)
    report = read_report(request(repo, f'actions/artifacts/{artifact["id"]}/zip', binary=True))
    validate_report(report, source, trusted, repo)
    # Confirm a passing workflow did not merely skip the verifier job.
    pages = request(repo, f'actions/runs/{trusted["id"]}/attempts/{trusted["run_attempt"]}/jobs?per_page=100', pages=True)
    verify_jobs = [job for page in pages for job in page["jobs"] if job["name"] == "verify"]
    require(len(verify_jobs) == 1)
    job = verify_jobs[0]
    require(job["run_id"] == trusted["id"] and job["run_attempt"] == trusted["run_attempt"])
    require(job["status"] == "completed" and job["conclusion"] == "success")
    for group in ("profile", "ordinary"):
        for label, row in report[group].items():
            name = (f"test ({label})" if group == "ordinary" else
                    f"runner-differential ({label}, {verifier.PROFILE[label][0]})")
            require(row["jobId"] == jobs[name]["id"])
    verifier.source_identity(request(repo, f'actions/runs/{source["id"]}'),
                             repo, source["id"], source["run_attempt"], sha)
    latest_trusted = request(repo, f'actions/runs/{trusted["id"]}')
    trusted_run(latest_trusted, repo)
    require(latest_trusted["run_attempt"] == trusted["run_attempt"])
    latest_source = request(repo, f"actions/workflows/ci.yml/runs?head_sha={sha}&branch=main&per_page=1")["workflow_runs"]
    require(len(latest_source) == 1 and latest_source[0]["id"] == source["id"])
    verifier.source_identity(latest_source[0], repo, source["id"], source["run_attempt"], sha)
    return {"status": "passed", "sourceRunId": source["id"], "sourceRunAttempt": source["run_attempt"],
            "sourceHeadSha": sha, "verifierRunId": trusted["id"], "artifactId": artifact["id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check(os.environ["GITHUB_REPOSITORY"], args.sha), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile,
            RuntimeError, subprocess.TimeoutExpired):
        print("Publication blocked: complete source-bound stdout verification is required.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
