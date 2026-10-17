"""Known-subject consumer checks; no feature flag override or registry access."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def expected():
    files = ["shoutx-artifact-plain.txt", "shoutx-artifact-日本語-😀.txt"]
    digest = "sha256:" + hashlib.sha256(b"shoutx artifact fixture\n").hexdigest()
    subjects = [{"name": name, "digest": digest, "kind": "file"} for name in files]
    for algorithm, length in [("sha256", 64), ("sha384", 96), ("sha512", 128)]:
        subjects.append({"name": "shoutx.test/" + algorithm + "@literal tag",
                         "digest": algorithm + ":" + "a" * length, "kind": "oci"})
    return subjects


def emit(binary):
    destination = os.environ.get("GITHUB_ARTIFACTS")
    if not destination:
        raise RuntimeError("artifact command file unavailable")
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    for subject in expected():
        if subject["kind"] == "file":
            (workspace / subject["name"]).write_bytes(b"shoutx artifact fixture\n")
            args = ["file", subject["name"]]
        else:
            args = ["oci", subject["name"], subject["digest"]]
        # Native bytes go directly to the runner-owned file; no text transcoding.
        with open(destination, "ab") as stream:
            result = subprocess.run([binary, "github-actions:artifacts", *args],
                                    stdin=subprocess.DEVNULL, stdout=stream,
                                    stderr=subprocess.PIPE, check=False)
        if result.returncode != 0 or result.stderr:
            raise RuntimeError("artifact producer failed")


def verify():
    source = os.environ.get("GITHUB_ARTIFACTS_LIST")
    if not source:
        raise RuntimeError("artifact list unavailable")
    data = Path(source).read_bytes()
    if not data:
        raise RuntimeError("artifact list empty; consumer processing unavailable")
    payload = json.loads(data)
    wanted = sorted(expected(), key=lambda item: item["name"])
    if payload != {"version": 1, "subjects": wanted}:
        raise RuntimeError("artifact consumer result mismatch")
    print("Verified 5 artifact subjects: exact names, kinds, and digests")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "emit":
            emit(sys.argv[2])
        elif sys.argv[1:] == ["verify"]:
            verify()
        else:
            raise RuntimeError("invalid invocation")
    except Exception:
        # Avoid copying consumer content or paths into command-visible diagnostics.
        sys.exit("artifact integration check failed")
