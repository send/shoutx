"""Manual Azure smoke test using synthetic, non-secret values only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

VALUE = "\u0301\u200bไทย日本語😀 %0A;%AZP25]\r\nnext\n"
INJECTION = "data\n##vso[task.setvariable variable=SHOUTX_INJECTED;]unexpected"
MESSAGE = "\u0301\u200bไทย日本語😀 %0A;]\nsecond"
CODE = "SHOUTX;]%0A"
LOCATION_FILE = "README.md"
LOCATION_MESSAGE = "shoutx location smoke"
LOCATION_CODE = "SHOUTX_LOCATION"


def path_root():
    return Path(os.environ["AGENT_TEMPDIRECTORY"]) / (
        "shoutx-path-" + os.environ["SYSTEM_JOBID"] + "-" + os.environ["SYSTEM_JOBATTEMPT"])


def path_entries(root):
    special = "unicode αไทย日本語😀 %0A]" + ("" if os.name == "nt" else ';"\\')
    return [root / "alpha", root / "bravo", root / special]


def prepare_paths():
    root = path_root()
    root.mkdir(exist_ok=False)
    paths = path_entries(root)
    baseline = os.environ["PATH"]
    if str(root) in baseline:
        raise RuntimeError("fixture already in PATH")
    (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    suffix = ".exe" if os.name == "nt" else ""
    for path in paths:
        path.mkdir()
    shutil.copy2(Path("target/release/shoutx" + suffix), paths[2] / ("shoutx-path-probe" + suffix))


def emit_paths():
    paths = path_entries(path_root())
    # Repeat alpha: expected final order is special, alpha, bravo.
    for index in [0, 1, 0, 2]:
        sys.stdout.buffer.write(invoke(["azure-pipelines:path"], str(paths[index])))
    sys.stdout.buffer.flush()


def check_path_value(actual, baseline, paths, separator):
    expected = separator.join(str(paths[i]) for i in [2, 0, 1])
    if baseline:
        expected += separator + baseline
    if actual != expected:
        raise RuntimeError("PATH effect mismatch")


def verify_paths():
    root = path_root()
    paths = path_entries(root)
    baseline = json.loads((root / "baseline.json").read_text(encoding="utf-8"))
    actual_path = os.environ["PATH"]
    entries = actual_path.split(os.pathsep)
    print(json.dumps({"pathObservation": {
        "entryCount": len(entries), "baselineEntryCount": len(baseline.split(os.pathsep)),
        "fixtureCounts": [entries.count(str(path)) for path in paths],
        "prefixMatches": entries[:3] == [str(paths[i]) for i in [2, 0, 1]],
        "baselineTailMatches": os.pathsep.join(entries[3:]) == baseline,
    }}), flush=True)
    check_path_value(actual_path, baseline, paths, os.pathsep)
    print("Azure PATH comparison passed", flush=True)
    suffix = ".exe" if os.name == "nt" else ""
    expected = paths[2] / ("shoutx-path-probe" + suffix)
    found = shutil.which("shoutx-path-probe" + suffix)
    if found != str(expected):
        raise RuntimeError("executable lookup mismatch")
    print("Azure PATH executable discovery passed", flush=True)
    # Execute the caller-owned native binary, never an input-derived script.
    actual = subprocess.run(["shoutx-path-probe" + suffix, "--version"],
                            capture_output=True, timeout=30)
    source = subprocess.run([str(Path("target/release/shoutx" + suffix).resolve()), "--version"],
                            capture_output=True, timeout=30)
    if (actual.returncode or source.returncode or actual.stderr or source.stderr
            or actual.stdout != source.stdout):
        raise RuntimeError("executable effect mismatch")
    print("Azure next-step PATH bytes, repeat registration, order and executable lookup passed")


def invoke(args, value):
    suffix = ".exe" if os.name == "nt" else ""
    binary = Path("target/release/shoutx" + suffix).resolve(strict=True)
    result = subprocess.run([str(binary), *args], input=value.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.returncode or result.stderr:
        raise RuntimeError("producer failed")
    return result.stdout


def emit_variables():
    for name, value, flags in [
        ("ShoutxValue", VALUE, []),
        ("ShoutxInjection", INJECTION, []),
        ("ShoutxOutput", VALUE, ["--output"]),
        ("ShoutxReadOnly", "fixed", ["--read-only"]),
    ]:
        sys.stdout.buffer.write(invoke(["azure-pipelines:variable", *flags, name], value))
    sys.stdout.buffer.flush()


def verify_variables(env):
    expected = {"SHOUTXVALUE": VALUE, "SHOUTXINJECTION": INJECTION,
                "SHOUTX_OUTPUT_VALUE": VALUE, "SHOUTXREADONLY": "fixed"}
    if any(env.get(k) != v for k, v in expected.items()) or "SHOUTX_INJECTED" in env:
        raise RuntimeError("variable effect mismatch")


def check_timeline(timeline, job, attempt, location=False):
    records = timeline.get("records", [])
    for severity in ["warning", "error"]:
        matching = [r for r in records
                    if (r.get("parentId") or "").lower() == job.lower()
                    and r.get("name") == "shoutx Azure " + severity + (" location" if location else "")
                    and r.get("attempt") == attempt]
        if len(matching) != 1 or matching[0].get("state") != "completed":
            raise RuntimeError("missing completed issue step")
        issues = matching[0].get("issues", [])
        if len(issues) != 1:
            raise RuntimeError("unexpected issue count")
        issue = issues[0]
        message = (f"{LOCATION_FILE}(1,3): {severity} {LOCATION_CODE}: {LOCATION_MESSAGE}"
                   if location else MESSAGE)
        if (issue.get("type") != severity or issue.get("message") != message
                or issue.get("data", {}).get("code") != (LOCATION_CODE if location else CODE)):
            raise RuntimeError("issue effect mismatch")
        if location:
            data = issue.get("data", {})
            if (issue.get("category") != "Code" or data.get("sourcepath") != LOCATION_FILE
                    or data.get("linenumber") != "1" or data.get("columnnumber") != "3"):
                raise RuntimeError("location effect mismatch")
        if (matching[0].get("errorCount", 0) != (1 if severity == "error" else 0)
                or matching[0].get("warningCount", 0) != (1 if severity == "warning" else 0)):
            raise RuntimeError("issue count mismatch")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("unexpected API redirect")


def verify_timeline():
    base = os.environ["SYSTEM_COLLECTIONURI"]
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != "https" or parsed.netloc != "dev.azure.com":
        raise RuntimeError("expected Azure DevOps Services endpoint")
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    build = int(os.environ["BUILD_BUILDID"])
    job = os.environ["SYSTEM_JOBID"]
    attempt = int(os.environ["SYSTEM_JOBATTEMPT"])
    url = f"{base.rstrip('/')}/{project}/_apis/build/builds/{build}/timeline?api-version=7.1"
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["SYSTEM_ACCESSTOKEN"]})
    opener = urllib.request.build_opener(NoRedirect())
    # The server's timeline can lag the completed step. Bounded retries, no
    # captured response/token output and no inferred pass when evidence is absent.
    for retry in range(6):
        with opener.open(request, timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise RuntimeError("timeline too large")
        try:
            check_timeline(json.loads(raw), job, attempt)
            check_timeline(json.loads(raw), job, attempt, location=True)
            break
        except RuntimeError:
            if retry == 5:
                raise
            time.sleep(5)
    identity = {k: os.environ.get(k) for k in
                ["BUILD_SOURCEVERSION", "BUILD_BUILDID", "SYSTEM_JOBID", "SYSTEM_JOBATTEMPT",
                 "AGENT_VERSION", "AGENT_OS", "AGENT_OSARCHITECTURE"]}
    identity["imageOS"] = os.environ.get("ImageOS") or os.environ.get("IMAGEOS")
    identity["imageVersion"] = os.environ.get("ImageVersion") or os.environ.get("IMAGEVERSION")
    print(json.dumps({"issueEffects": "passed", "identity": identity}))


def main():
    phase = sys.argv[1]
    if phase == "emit-variables":
        emit_variables()
    elif phase == "emit-paths":
        emit_paths()
    elif phase == "prepare-paths":
        prepare_paths()
    elif phase == "verify-paths":
        verify_paths()
    elif phase == "verify-variables":
        verify_variables(os.environ)
        print("Azure next-step variable effects passed")
    elif phase in ("warning", "error"):
        sys.stdout.buffer.write(invoke(["azure-pipelines:" + phase, "--code", CODE], MESSAGE))
        sys.stdout.buffer.flush()
    elif phase in ("warning-location", "error-location"):
        severity = phase.split("-")[0]
        source = str(Path(LOCATION_FILE).resolve(strict=True))
        sys.stdout.buffer.write(invoke(["azure-pipelines:" + severity,
                                       "--file", source, "--line", "1", "--column", "3",
                                       "--code", LOCATION_CODE], LOCATION_MESSAGE))
        sys.stdout.buffer.flush()
    elif phase == "verify-timeline":
        verify_timeline()
    else:
        raise RuntimeError("unknown phase")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Azure hosted smoke failed; input and captured diagnostics withheld")
