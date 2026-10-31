"""Native stdout fixture, without API credentials or raw rejected-input output."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from formatter_cases import values


def binary():
    return Path(os.environ["PIPELINE_WORKSPACE"]) / "formatter-binary" / (
        "shoutx.exe" if os.name == "nt" else "shoutx")


def line(value):
    sys.stdout.buffer.write(value.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def invoke(command, value=None):
    result = subprocess.run([str(binary()), "azure-pipelines:" + command],
                            input=b"" if value is None else value.encode("utf-8"),
                            stderr=subprocess.PIPE, timeout=30)
    if result.returncode or result.stderr:
        raise RuntimeError("formatter producer failed")


def package():
    binary().parent.mkdir(exist_ok=False)
    shutil.copy2(Path("target/release") / binary().name, binary())
    identity = {"source": os.environ["BUILD_SOURCEVERSION"],
                "run": os.environ["BUILD_BUILDID"],
                "digest": hashlib.sha256(binary().read_bytes()).hexdigest()}
    (binary().parent / "identity.json").write_text(json.dumps(identity))


def emit(capacity=False):
    identity = json.loads((binary().parent / "identity.json").read_text())
    if (identity["source"] != os.environ["BUILD_SOURCEVERSION"]
            or identity["run"] != os.environ["BUILD_BUILDID"]
            or identity["digest"] != hashlib.sha256(binary().read_bytes()).hexdigest()):
        raise RuntimeError("binary identity mismatch")
    if os.name != "nt":
        binary().chmod(0o700)
    if os.environ["SHOUTX_FORMATTER_SENTINEL"] != "unchanged":
        raise RuntimeError("unexpected sentinel state")
    line("SX_FORMATTER_IDENTITY:" + json.dumps({
        **identity, "job": os.environ["SYSTEM_JOBID"],
        "attempt": os.environ["SYSTEM_JOBATTEMPT"],
        "agent": os.environ["AGENT_VERSION"],
        "image": os.environ.get("ImageOS") or os.environ.get("IMAGEOS"),
        "imageVersion": os.environ.get("ImageVersion") or os.environ.get("IMAGEVERSION"),
        "host": os.environ["SHOUTX_FORMATTER_HOST"],
        "debug": os.environ["SHOUTX_FORMATTER_DEBUG"],
    }, sort_keys=True))
    # All rejection output is captured, including on broken acceptance.
    for command in ("debug", "group"):
        for invalid in (b"x\n", b"x\r", b"##[", b"x\0", b"\xff", b"x" * 1_048_577):
            result = subprocess.run([str(binary()), "azure-pipelines:" + command],
                                    input=invalid, capture_output=True, timeout=30)
            if result.returncode != 1 or result.stdout or not result.stderr.startswith(b"error: "):
                raise RuntimeError("rejection control failed")
    for invalid in (b"", b"##vso"):
        result = subprocess.run([str(binary()), "azure-pipelines:group"], input=invalid,
                                capture_output=True, timeout=30)
        if result.returncode != 1 or result.stdout:
            raise RuntimeError("group rejection control failed")
    line("SX_REJECTIONS_OK")
    for name, value in values():
        if (name == "cap") != capacity:
            continue
        line("SX_DEBUG_" + name + "_BEGIN")
        invoke("debug", value)
        line("SX_DEBUG_" + name + "_END")
        line("SX_GROUP_" + name + "_BEGIN")
        invoke("group", value)
        line("SX_INSIDE_" + name)
        invoke("endgroup")
        line("SX_GROUP_" + name + "_END")
    if capacity:
        line("SX_CAPACITY_COMPLETE")
        return
    line("SX_DEBUG_empty_BEGIN")
    invoke("debug", "")
    line("SX_DEBUG_empty_END")
    line("SX_NESTED_BEGIN")
    invoke("group", "outer")
    line("SX_OUTER")
    invoke("group", "inner")
    line("SX_INNER")
    invoke("endgroup")
    line("SX_OUTER_AFTER_INNER")
    invoke("endgroup")
    line("SX_NESTED_END")
    line("SX_AFTER_ALL_GROUPS")
    line("SX_FORMATTER_COMPLETE")


if __name__ == "__main__":
    try:
        mode, = sys.argv[1:]
        if mode == "package":
            package()
        elif mode == "emit":
            emit()
        elif mode == "emit-capacity":
            emit(capacity=True)
        elif mode == "sentinel" and os.environ["SHOUTX_FORMATTER_SENTINEL"] == "unchanged":
            line("SX_SENTINEL_UNCHANGED")
        else:
            raise RuntimeError("invalid fixture selection")
    except Exception:
        sys.exit("Azure formatter fixture failed; captured data withheld")
