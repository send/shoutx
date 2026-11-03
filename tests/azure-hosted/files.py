"""Finite synthetic file-attachment verification. Never print captured data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TYPES = {"summary": "DistributedTask.Core.Summary", "uploadfile": "DistributedTask.Core.FileAttachment"}
KEYS = ["BUILD_BUILDID", "BUILD_SOURCEVERSION", "SYSTEM_JOBID", "SYSTEM_JOBATTEMPT",
        "AGENT_VERSION", "AGENT_OS", "AGENT_OSARCHITECTURE", "ImageOS", "ImageVersion"]


def binary():
    return Path("target/release/shoutx" + (".exe" if os.name == "nt" else "")).resolve(strict=True)


def identity():
    result = {key: os.environ.get(key) for key in KEYS}
    if any(not value for value in result.values()):
        raise RuntimeError("missing identity")
    result["binarySha256"] = hashlib.sha256(binary().read_bytes()).hexdigest()
    return result


def cases(host):
    for command in TYPES:
        for index, tail in enumerate(["plain", "日本語ไทยالعربية😀e\u0301", " space ;] "]):
            name = f"shoutx-{host}-{command}-{index}-{tail}.md"
            content = (f"# Shoutx {host} {command} {index}\n\nSynthetic report.\n\n"
                       "```text\n##vso[task.setvariable variable=SHOUTX_FILES_SENTINEL;]changed\n"
                       "##[error]literal content\n```\n").encode()
            yield command, name, content


def manifest():
    return Path(os.environ["AGENT_TEMPDIRECTORY"]) / "shoutx-files-identity.json"


def emit(host):
    ident = identity()
    root = Path(os.environ["AGENT_TEMPDIRECTORY"]) / "shoutx-files space %0A;%AZP25]"
    root.mkdir(exist_ok=False)
    for index, (command, name, content) in enumerate(cases(host)):
        path = root / name
        path.write_bytes(content)
        args = [str(binary()), "azure-pipelines:" + command]
        # Exercise both native argv and stdin. Native stdout goes to the Agent.
        if index % 2:
            args += ["--", str(path)]
        result = subprocess.run(args, input=b"ignored" if index % 2 else str(path).encode(),
                                stderr=subprocess.PIPE, timeout=30)
        if result.returncode or result.stderr:
            raise RuntimeError("producer failed")
    manifest().write_text(json.dumps(ident), encoding="utf-8")


def get_api(suffix, raw=False):
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    build = os.environ["BUILD_BUILDID"]
    if not build.isascii() or not build.isdigit():
        raise RuntimeError("invalid build id")
    url = f"https://dev.azure.com/kazjuly7/{project}/_apis/build/builds/{build}{suffix}?api-version=7.1"
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + os.environ["SYSTEM_ACCESSTOKEN"]})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("redirect refused")
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise RuntimeError("response too large")
    return data if raw else json.loads(data)


def check_identity(saved, current, build):
    if (saved != current or str(build.get("id")) != current["BUILD_BUILDID"]
            or build.get("sourceVersion") != current["BUILD_SOURCEVERSION"]):
        raise RuntimeError("identity mismatch")


def producer(timeline, current):
    matches = [r for r in timeline.get("records", []) if r.get("type") == "Task"
               and r.get("name") == "Emit file attachments"
               and str(r.get("parentId", "")).lower() == current["SYSTEM_JOBID"].lower()]
    if len(matches) != 1:
        raise RuntimeError("missing or duplicate producer")
    record = matches[0]
    if (record.get("state") != "completed" or record.get("result") != "succeeded"
            or record.get("errorCount", 0) or record.get("warningCount", 0)
            or record.get("issues") or str(record.get("attempt")) != current["SYSTEM_JOBATTEMPT"]):
        raise RuntimeError("producer not clean")
    return record["id"]


def check_names(rows, expected, host):
    # Other native job may already have uploaded its own disjoint names.
    names = [r.get("name") for r in rows]
    if (any(not isinstance(n, str) for n in names)
            or sorted(n for n in names if n.startswith(f"shoutx-{host}-")) != sorted(expected)
            or any(not n.startswith(("shoutx-linux-", "shoutx-windows-")) for n in names)):
        raise RuntimeError("attachment set mismatch")


def check_content(actual, expected):
    if actual != expected:
        raise RuntimeError("attachment bytes mismatch")


def verify(host):
    current = identity()
    check_identity(json.loads(manifest().read_text(encoding="utf-8")), current, get_api(""))
    for attempt in range(6):
        try:
            timeline = get_api("/timeline")
            record = producer(timeline, current)
            for command, attachment_type in TYPES.items():
                expected = [(name, content) for cmd, name, content in cases(host) if cmd == command]
                rows = get_api("/attachments/" + attachment_type)["value"]
                check_names(rows, [name for name, _ in expected], host)
                for name, content in expected:
                    suffix = "/" + "/".join(urllib.parse.quote(p, safe="") for p in
                                              [timeline["id"], record, "attachments", attachment_type, name])
                    check_content(get_api(suffix, raw=True), content)
            break
        except (RuntimeError, ValueError, OSError):
            if attempt == 5:
                raise RuntimeError("attachment verification exhausted") from None
            time.sleep(2)
    print(json.dumps({"identity": current, "host": host, "attachments": 6, "passed": True}))


if __name__ == "__main__":
    try:
        mode, host = sys.argv[1:]
        if host not in ("linux", "windows") or os.environ.get("SHOUTX_FILES_SENTINEL") != "unchanged":
            raise RuntimeError("invalid host or sentinel")
        if mode == "emit":
            emit(host)
        elif mode == "verify":
            verify(host)
        else:
            raise RuntimeError("invalid mode")
    except Exception:
        sys.exit("Azure file verification failed; captured data withheld")
