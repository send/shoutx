"""Dedicated debug-enabled hosted checks, separate from mask log experiments."""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BEGIN = "SHOUTX_LOG_COMMANDS_BEGIN"
END = "SHOUTX_LOG_COMMANDS_END"
ROWS = ["ubuntu-22.04", "ubuntu-24.04", "macos-15", "windows-2025"]


def cases():
    return [
        ("debug", ""),
        ("debug", " Ελληνικά العربية हिन्दी 日本語 😀 %0A ::error::literal"),
        ("debug", "first\r\n##[warning]literal\n::endgroup::literal"),
        ("group", "日本語_😀 ::error::literal ##[endgroup]literal %0A"),
        ("endgroup", None),
        ("group", ""),
        ("endgroup", None),
    ]


def expected():
    result = []
    for command, value in cases():
        if command == "debug":
            result.extend("##[debug]" + part for part in value.replace("\r\n", "\n").split("\n"))
        else:
            result.append("##[" + command + "]" + (value or ""))
    return result


def emit(binary):
    # This is a precondition check, not substitute evidence for actual debug output.
    if os.environ.get("RUNNER_DEBUG") != "1":
        raise RuntimeError("debug logging must be enabled for this probe")
    # Trusted setup outside the measured block; group/endgroup otherwise permit echo.
    print("::echo::off", flush=True)
    print(BEGIN, flush=True)
    for command, value in cases():
        args = [binary, "github-actions:" + command]
        if value is not None:
            args += ["--", value]
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
        if result.returncode or result.stderr:
            raise RuntimeError("log producer failed")
    print(END, flush=True)


def verify_log(raw):
    text = raw.decode("utf-8-sig")
    lines = [re.sub(r"^\d{4}-\d\d-\d\dT\S+ ", "", line.rstrip("\r"))
             for line in text.split("\n")]
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise RuntimeError("missing or duplicated log sentinels")
    start, end = lines.index(BEGIN), lines.index(END)
    if start >= end or lines[start + 1:end] != expected():
        raise RuntimeError("debug/group effect mismatch")


def api(endpoint):
    return subprocess.check_output(["gh", "api", endpoint], stderr=subprocess.PIPE, timeout=60)


def download_log(repo, job_id):
    # Reuse the existing raw transport: gh's terminal-escape filter is not a
    # reliable binary/log download API. Never print downloaded log contents.
    path = Path(__file__).resolve().parents[2] / "scripts/verify-stdout-run.py"
    spec = importlib.util.spec_from_file_location("stdout_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.download(repo, f"actions/jobs/{job_id}/logs")


def verify_run(destination):
    repo, run, attempt, sha = [os.environ[key] for key in
                             ["GH_REPO", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA"]]
    source_head = os.environ["SHOUTX_SOURCE_HEAD"]
    endpoint = f"repos/{repo}/actions/runs/{run}/attempts/{attempt}/jobs?per_page=100"
    jobs = json.loads(api(endpoint))
    if jobs["total_count"] > 100:
        raise RuntimeError("unexpected job inventory size")
    evidence = []
    for row in ROWS:
        matches = [job for job in jobs["jobs"] if job["name"] == f"log-commands ({row})"]
        if len(matches) != 1 or matches[0]["conclusion"] != "success":
            raise RuntimeError("missing or failed producer job")
        job = matches[0]
        if job["head_sha"] != source_head or job["run_attempt"] != int(attempt):
            raise RuntimeError("producer identity mismatch")
        for retry in range(6):
            try:
                raw = download_log(repo, job['id'])
                verify_log(raw)
                break
            except (RuntimeError, ValueError, subprocess.SubprocessError):
                if retry == 5:
                    raise
                time.sleep(5)
        evidence.append({"label": row, "job": job["id"], "logSha256": hashlib.sha256(raw).hexdigest(),
                         "verifiedRecords": len(expected())})
    Path(destination).write_text(json.dumps({"run": run, "attempt": attempt, "testedSha": sha,
                                           "sourceHead": source_head,
                                           "status": "passed", "jobs": evidence}, indent=2) + "\n")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "emit":
            emit(sys.argv[2])
        elif len(sys.argv) == 3 and sys.argv[1] == "verify":
            verify_run(sys.argv[2])
        else:
            raise RuntimeError("invalid invocation")
    except Exception:
        sys.exit("log-command integration check failed")
