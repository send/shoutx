"""Dedicated synthetic build-metadata experiment; never print API responses."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request


def values(host, index):
    prefix = "shoutx-" + host + "-"
    numbers = [prefix + "1.2.3", prefix + "αไทย日本語😀%0A;]",
               prefix + "😀" * 115 + "x" * (255 - len(prefix) - 230)]
    tags = [prefix + "ready", prefix + "αไทย日本語😀%0A;]/@?*,#",
            prefix + "😀" * 115 + "t" * (255 - len(prefix) - 230)]
    return numbers[index], tags[index]


def expected_tags(host, index):
    return ([values("linux", n)[1] for n in range(3)] if host == "windows" else []) + [
        values(host, n)[1] for n in range(index + 1)]


def check_metadata(actual, build_id, sha, number, tags):
    if (str(actual.get("id")) != str(build_id) or actual.get("sourceVersion") != sha
            or actual.get("buildNumber") != number
            or not isinstance(actual.get("tags"), list)
            or sorted(actual["tags"]) != sorted(tags)):
        raise RuntimeError("metadata effect or identity mismatch")


def get_build():
    # Fixed organization prevents an environment-supplied origin receiving token.
    project = urllib.parse.quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
    build_id = os.environ["BUILD_BUILDID"]
    if not build_id.isascii() or not build_id.isdigit():
        raise RuntimeError("invalid build identity")
    url = f"https://dev.azure.com/kazjuly7/{project}/_apis/build/builds/{build_id}?api-version=7.1"
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["SYSTEM_ACCESSTOKEN"]})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("redirect refused")
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise RuntimeError("response too large")
    return json.loads(data)


def verify(host, index):
    if index < 0:
        number = (values("linux", 2)[0] if host == "windows"
                  else "shoutx-metadata-initial")
    else:
        number = values(host, index)[0]
    tags = expected_tags(host, index)
    for attempt in range(6):
        try:
            check_metadata(get_build(), os.environ["BUILD_BUILDID"],
                           os.environ["BUILD_SOURCEVERSION"], number, tags)
            break
        except (RuntimeError, ValueError, OSError):
            if attempt == 5:
                raise RuntimeError("metadata verification exhausted") from None
            time.sleep(2)
    if index >= 0 and os.environ.get("BUILD_BUILDNUMBER") != number:
        raise RuntimeError("next-task number mismatch")
    identity = {key: os.environ.get(key) for key in [
        "BUILD_BUILDID", "BUILD_SOURCEVERSION", "SYSTEM_JOBID", "SYSTEM_JOBATTEMPT",
        "AGENT_VERSION", "AGENT_OS", "AGENT_OSARCHITECTURE", "ImageOS", "ImageVersion"]}
    if any(not value for value in identity.values()):
        raise RuntimeError("missing hosted identity")
    print(json.dumps({"identity": identity, "case": index, "host": host,
                      "tagCount": len(tags), "passed": True,
                      "numberSha256": hashlib.sha256(number.encode()).hexdigest()}))


def emit(host, index):
    binary = Path("target/release/shoutx" + (".exe" if os.name == "nt" else "")).resolve(strict=True)
    for command, value in zip(["build-number", "build-tag"], values(host, index)):
        # Rejection probes are captured, never forwarded even on broken acceptance.
        for invalid in ["", "synthetic\n##vso[task.setvariable variable=SHOUTX_METADATA_INJECTED;]yes",
                        "x" * 256, "synthetic\0", "synthetic:"]:
            result = subprocess.run([str(binary), "azure-pipelines:" + command],
                                    input=invalid.encode(), capture_output=True, timeout=30)
            if result.returncode != 1 or result.stdout or not result.stderr.startswith(b"error: "):
                raise RuntimeError("rejection probe failed")
        # Native stdout goes directly to the Agent. This process has no read token.
        result = subprocess.run([str(binary), "azure-pipelines:" + command],
                                input=value.encode(), stderr=subprocess.PIPE, timeout=30)
        if result.returncode or result.stderr:
            raise RuntimeError("metadata producer failed")


def main():
    mode, host, raw_index = sys.argv[1:]
    index = int(raw_index)
    if host not in ("linux", "windows") or index not in (-1, 0, 1, 2):
        raise RuntimeError("invalid fixture selection")
    if os.environ.get("SHOUTX_METADATA_INJECTED"):
        raise RuntimeError("unexpected sentinel operation")
    if mode == "emit" and index >= 0:
        emit(host, index)
    elif mode == "verify":
        verify(host, index)
    else:
        raise RuntimeError("invalid fixture mode")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Azure metadata verification failed; captured data withheld")
