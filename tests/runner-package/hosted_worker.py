"""Read-only feasibility observation; never dump job messages or process args.

This observes diagnostic process-start culture, job culture input and on-disk
files, not processing-thread state or loaded native mappings. Unknowns stay unknown.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid

MESSAGE = re.compile(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ INFO Worker\] Job message:\r?$", re.M)
STARTUP_CULTURE = re.compile(
    r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ INFO Worker\] Culture: ([^\r\n]*)\r?$", re.M)
FILE_CAP = 16 * 1024 * 1024
TOTAL_CAP = 64 * 1024 * 1024


class Unavailable(Exception):
    pass


def require(condition, code):
    if not condition:
        raise Unavailable(code)


def at_stage(stage, operation, *args):
    try:
        return operation(*args)
    except Unavailable:
        raise
    except Exception:
        raise Unavailable(stage + "-unavailable") from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        key = key.lower()
        require(key not in result, "ambiguous-json")
        result[key] = value
    return result


def identity(environment):
    names = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
             "GITHUB_REPOSITORY", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH",
             "ImageOS", "ImageVersion", "SHOUTX_SOURCE_HEAD",
             "SHOUTX_MATRIX_OS", "SHOUTX_MATRIX_RID")
    result = {name: environment.get(name) for name in names}
    require(all(isinstance(value, str) and 0 < len(value) <= 150 and
                re.fullmatch(r"[A-Za-z0-9_. /-]+", value) for value in result.values()),
            "missing-or-invalid-identity")
    require(all(re.fullmatch(r"[0-9]+", result[name]) for name in
                ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "invalid-run-identity")
    require(all(re.fullmatch(r"[0-9a-f]{40}", result[name]) for name in
                ("GITHUB_SHA", "SHOUTX_SOURCE_HEAD")), "invalid-source-identity")
    return result


def worker_ancestor():
    """Follow only this observer's ancestors; never query command lines/env."""
    if platform.system() == "Windows":
        script = r'''
$ErrorActionPreference = 'Stop'
$probePid = [int]$env:SHOUTX_OBSERVER_PID
for ($i = 0; $i -lt 32; $i++) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$probePid" -Property ProcessId,ParentProcessId,Name,ExecutablePath
    if ($null -eq $p) { exit 1 }
    if ($p.Name -ceq 'Runner.Worker.exe') {
        @{ pid = $p.ProcessId; path = $p.ExecutablePath } | ConvertTo-Json -Compress
        exit 0
    }
    $probePid = [int]$p.ParentProcessId
    if ($probePid -le 0) { exit 1 }
}
exit 1
'''
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                                env=dict(os.environ, SHOUTX_OBSERVER_PID=str(os.getpid())),
                                capture_output=True, text=True, timeout=30)
        require(result.returncode == 0, "worker-ancestry-unavailable")
        found = json.loads(result.stdout)
        return int(found["pid"]), Path(found["path"])
    current = os.getpid()
    for _ in range(32):
        result = subprocess.run(["ps", "-p", str(current), "-o", "ppid=", "-o", "comm="],
                                capture_output=True, text=True, timeout=5)
        require(result.returncode == 0, "worker-ancestry-unavailable")
        parts = result.stdout.strip().split(maxsplit=1)
        require(len(parts) == 2 and parts[0].isdigit(), "worker-ancestry-unavailable")
        path = Path(parts[1])
        if path.name == "Runner.Worker":
            if platform.system() == "Linux":
                path = Path(os.readlink(f"/proc/{current}/exe"))
            return current, path
        current = int(parts[0])
        require(current > 0, "worker-ancestry-unavailable")
    raise Unavailable("worker-ancestry-unavailable")


def project_message(message, expected):
    """Return only an allowlisted projection after exact job-context matching."""
    github = message.get("contextdata", {}).get("github", {})
    require(github.get("t") == 2, "unsupported-context-format")
    pairs = github.get("d", [])
    context = unique_object([(pair["k"], pair["v"]) for pair in pairs])
    # ExecutionContext initializes github.job from system.github.job, then
    # overlays the supplied github context. JobName is a different timeline ref.
    job = message.get("variables", {}).get("system.github.job", {}).get("value")
    job = context.get("job", job)
    if job != expected["GITHUB_JOB"]:
        return None
    matrix = message.get("contextdata", {}).get("matrix", {})
    require(matrix.get("t") == 2, "unsupported-matrix-context")
    matrix_values = unique_object([(pair["k"], pair["v"]) for pair in matrix.get("d", [])])
    if (matrix_values.get("os") != expected["SHOUTX_MATRIX_OS"] or
            matrix_values.get("runtime") != expected["SHOUTX_MATRIX_RID"]):
        return None
    for key, name in (("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"),
                      ("repository", "GITHUB_REPOSITORY"), ("sha", "GITHUB_SHA")):
        if context.get(key) != expected[name]:
            return None
    job_id = str(uuid.UUID(message["jobid"]))
    if "system.culture" not in message.get("variables", {}):
        return {"timelineJobId": job_id, "cultureInput": None, "cultureInputStatus": "absent"}
    variable = message.get("variables", {}).get("system.culture")
    if (not isinstance(variable, dict) or variable.get("issecret") not in (None, False)
            or variable.get("value") is None):
        return {"timelineJobId": job_id, "cultureInput": None, "cultureInputStatus": "unavailable"}
    value = variable.get("value")
    if value not in ("", "en-US"):
        return {"timelineJobId": job_id, "cultureInput": None,
                "cultureInputStatus": "redacted-or-outside-selected-scope"}
    return {"timelineJobId": job_id, "cultureInput": value, "cultureInputStatus": "observed"}


def observe_logs(directory, expected):
    files = sorted(directory.glob("Worker_*-utc.log"))
    require(0 < len(files) <= 64, "diagnostic-files-unavailable")
    decoder = json.JSONDecoder(object_pairs_hook=unique_object)
    matches, total = [], 0
    for path in files:
        with path.open("rb") as stream:
            raw = stream.read(FILE_CAP + 1)
        total += len(raw)
        require(len(raw) <= FILE_CAP and total <= TOTAL_CAP, "diagnostic-size-limit")
        value = raw.decode("utf-8-sig")
        marker = MESSAGE.search(value)
        if marker is not None:
            require(MESSAGE.search(value, marker.end()) is None, "multiple-job-message-markers")
            message, _ = at_stage("message-parse", decoder.raw_decode, value[marker.end():].lstrip())
            projected = at_stage("message-projection", project_message, message, expected)
            if projected is not None:
                # Program.MainAsync logs this before Worker receives the job.
                # Never infer it from a missing system.culture or a child locale.
                startup = STARTUP_CULTURE.findall(value[:marker.start()])
                startup_value, startup_status = None, "missing-or-ambiguous"
                if len(startup) == 1:
                    startup_status = "redacted-or-outside-selected-scope"
                    if startup[0] in ("", "en-US"):
                        startup_value, startup_status = startup[0], "observed"
                projected.update(startupCulture=startup_value,
                                 startupCultureStatus=startup_status)
                matches.append(projected)
    require(len(matches) == 1, "missing-or-ambiguous-job-message")
    return matches[0]


def observe(expected):
    pid, executable = at_stage("ancestry", worker_ancestor)
    require(executable.is_absolute() and executable.name in ("Runner.Worker", "Runner.Worker.exe"),
            "worker-path-unavailable")
    binary_dir = executable.parent
    projected = at_stage("diagnostic-read", observe_logs, binary_dir.parent / "_diag", expected)
    # File identities are deliberately named onDisk, never loaded-module attestation.
    names = [executable.name, "Runner.Worker.dll", "Runner.Common.dll",
             "Runner.Sdk.dll", "Sdk.dll",
             "System.Private.CoreLib.dll", "Runner.Worker.runtimeconfig.json", "Runner.Worker.deps.json"]
    names.append({"Linux": "libcoreclr.so", "Darwin": "libcoreclr.dylib", "Windows": "coreclr.dll"}[platform.system()])
    digests, disk_status = {}, "observed"
    try:
        for name in names:
            digest = hashlib.sha256()
            with (binary_dir / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            digests[name] = digest.hexdigest()
    except OSError:
        digests, disk_status = {}, "unavailable"
    return {"status": ("observed-job-culture-input" if projected["cultureInputStatus"] == "observed"
                       else "observed-job-message-without-culture"), "ancestorWorkerPid": pid,
            "recordCorrelation": "unique-context-match-in-ancestor-installation",
            **projected, "onDiskSha256": digests, "onDiskIdentityStatus": disk_status,
            "processingThreadCulture": None, "loadedNativeInputs": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"schemaVersion": 2, "status": "unavailable",
              "scope": "diagnostic process-start culture, job culture input and on-disk identities; not processing-thread/native-state proof"}
    try:
        report["identity"] = identity(os.environ)
        report.update(observe(report["identity"]))
    except Unavailable as error:
        report["reason"] = str(error)  # Only fixed codes constructed in this module.
    except Exception:
        report["reason"] = "observation-unavailable"
    # Never print exceptions, diagnostic paths, job data, or captured subprocess output.
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    except OSError:
        print("Could not write hosted Worker observation.", file=sys.stderr)
        return 1
    return 0  # Collection succeeded; status=unavailable is NOT a successful observation.


if __name__ == "__main__":
    sys.exit(main())
