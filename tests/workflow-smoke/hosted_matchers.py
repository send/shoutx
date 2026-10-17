"""Synthetic matcher lifecycle evidence; never prints captured API/log data."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
import time

from hosted_log_commands import ROWS, api, download_log

BEGIN = "SHOUTX_MATCHERS_BEGIN"
END = "SHOUTX_MATCHERS_END"
OWNER = "Ελληνικά_العربية_हिन्दी_日本語_😀,::=%0A "
CONTROL = "shoutx-probe-control"
TARGET_PREFIX = "SHOUTX_MATCH_TARGET:"
CONTROL_PREFIX = "SHOUTX_MATCH_CONTROL:"
CAPACITY_NOTICE = "Due to capacity constraints, jobs targeting macOS arm64 runners may experience longer queue times."


def expected_lines():
    return [TARGET_PREFIX + "before_registration",
            "##[warning]before_owner", "##[warning]control_before_owner",
            TARGET_PREFIX + "after_owner", "##[warning]control_after_owner",
            "##[warning]before_file", TARGET_PREFIX + "after_file",
            "##[warning]control_after_file"]


def expected_annotations():
    return sorted(line.removeprefix("##[warning]") for line in expected_lines()
                  if line.startswith("##[warning]"))


def config(owner, prefix):
    return {"problemMatcher": [{"owner": owner, "severity": "warning",
                                "pattern": [{"regexp": "^" + re.escape(prefix) + "(.+)$",
                                             "message": 1}]}]}


def emit(binary):
    if os.environ.get("RUNNER_DEBUG") == "1":
        raise RuntimeError("matcher effect probe requires debug logging disabled")
    binary = str(Path(binary).resolve())
    # Runner consumes stdout asynchronously: retain the JSON until the hosted
    # job's ephemeral workspace is discarded, not merely until emit exits.
    with nullcontext(tempfile.mkdtemp(prefix="shoutx-matcher-", dir=Path.cwd())) as directory:
        root = Path(directory)
        target = root / "Ελληνικά_العربية_हिन्दी_日本語_😀,%0A.json"
        control = root / "control.json"
        target.write_text(json.dumps(config(OWNER, TARGET_PREFIX)), encoding="utf-8")
        control.write_text(json.dumps(config(CONTROL, CONTROL_PREFIX)), encoding="utf-8")

        def invoke(*args):
            result = subprocess.run([binary, *args], stdin=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, check=False, timeout=10)
            if result.returncode or result.stderr:
                raise RuntimeError("matcher producer failed")

        def line(value):
            print(value, flush=True)

        line("::echo::off")
        line(BEGIN)
        line(TARGET_PREFIX + "before_registration")
        invoke("github-actions:add-matcher", "--", str(control))
        # Both relative and absolute file paths pass through the real handler.
        invoke("github-actions:add-matcher", "--", str(target.relative_to(Path.cwd())))
        line(TARGET_PREFIX + "before_owner")
        line(CONTROL_PREFIX + "control_before_owner")
        invoke("github-actions:remove-matcher", "owner", "--", OWNER)
        line(TARGET_PREFIX + "after_owner")
        line(CONTROL_PREFIX + "control_after_owner")
        invoke("github-actions:add-matcher", "--", str(target))
        line(TARGET_PREFIX + "before_file")
        invoke("github-actions:remove-matcher", "file", "--", str(target))
        line(TARGET_PREFIX + "after_file")
        line(CONTROL_PREFIX + "control_after_file")
        invoke("github-actions:remove-matcher", "owner", "--", CONTROL)
        line(END)


def verify_effects(raw, annotations):
    lines = [re.sub(r"^\d{4}-\d\d-\d\dT\S+ ", "", line.rstrip("\r"))
             for line in raw.decode("utf-8-sig").split("\n")]
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise RuntimeError("missing or duplicate matcher sentinels")
    start, end = lines.index(BEGIN), lines.index(END)
    if start >= end or lines[start + 1:end] != expected_lines():
        raise RuntimeError("matcher lifecycle log mismatch")
    # Observed GitHub infrastructure notice, not produced by the probe. Do not
    # discard arbitrary notices or any warning/error from the test job.
    annotations = [item for item in annotations if not (
        item.get("annotation_level") == "notice" and item.get("message") == CAPACITY_NOTICE
        and item.get("path") == ".github" and item.get("start_line") == 1
        and item.get("end_line") == 1)]
    if any(item["annotation_level"] != "warning" for item in annotations):
        raise RuntimeError("unexpected matcher annotation kind")
    if sorted(item["message"] for item in annotations) != expected_annotations():
        raise RuntimeError("matcher lifecycle annotation mismatch")


def verify_run(destination):
    repo, run, attempt, sha, source = [os.environ[key] for key in
        ["GH_REPO", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "SHOUTX_SOURCE_HEAD"]]
    inventory = json.loads(api(f"repos/{repo}/actions/runs/{run}/attempts/{attempt}/jobs?per_page=100"))
    if inventory["total_count"] > 100 or inventory["total_count"] != len(inventory["jobs"]):
        raise RuntimeError("incomplete matcher job inventory")
    evidence = []
    for row in ROWS:
        jobs = [job for job in inventory["jobs"] if job["name"] == f"matchers ({row})"]
        if len(jobs) != 1:
            raise RuntimeError("missing or duplicated matcher job")
        job = jobs[0]
        if (job["status"] != "completed" or job["conclusion"] != "success"
                or job["head_sha"] != source or job["run_attempt"] != int(attempt)
                or job["run_id"] != int(run)):
            raise RuntimeError("failed or mismatched matcher job")
        check = re.fullmatch(rf"https://api\.github\.com/repos/{re.escape(repo)}/check-runs/([0-9]+)",
                             job["check_run_url"])
        if not check:
            raise RuntimeError("invalid matcher check identity")
        for retry in range(6):
            try:
                raw = download_log(repo, job["id"])
                annotations = json.loads(api(f"repos/{repo}/check-runs/{check[1]}/annotations?per_page=100"))
                verify_effects(raw, annotations)
                break
            except (RuntimeError, ValueError, subprocess.SubprocessError):
                if retry == 5:
                    raise
                time.sleep(5)
        evidence.append({"label": row, "job": job["id"], "logSha256": hashlib.sha256(raw).hexdigest(),
                         "annotationsSha256": hashlib.sha256(json.dumps(annotations, sort_keys=True).encode()).hexdigest(),
                         "verifiedRecords": len(expected_lines()), "verifiedAnnotations": len(expected_annotations()),
                         "totalAnnotations": len(annotations)})
    Path(destination).write_text(json.dumps({"run": run, "attempt": attempt, "testedSha": sha,
        "sourceHead": source, "status": "passed", "jobs": evidence}, indent=2) + "\n")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "emit":
            emit(sys.argv[2])
        elif len(sys.argv) == 3 and sys.argv[1] == "verify":
            verify_run(sys.argv[2])
        else:
            raise RuntimeError("invalid invocation")
    except Exception:
        sys.exit("matcher integration check failed")
