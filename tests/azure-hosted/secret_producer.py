"""Bounded synthetic hosted phases. Successful registration wire is inherited."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from mask_producer import emit_block
from secret_cases import (ALL_JOBS, SAME_JOB, SENTINEL, assignments, expected_blocks,
                          CONTROL_PLAIN, CONTROL_OMITTED, CONTROL_WRONG,
                          CONTROL_ORIGINAL, CONTROL_REPLACEMENT)


def require(condition):
    if not condition:
        raise RuntimeError("synthetic secret-variable check failed")


def binary():
    return Path(os.environ["PIPELINE_WORKSPACE"]) / "secret-binary" / (
        "shoutx.exe" if os.name == "nt" else "shoutx")


def input_path(index):
    return Path(os.environ["AGENT_TEMPDIRECTORY"]) / f"shoutx-secret-{index}.bin"


def package():
    binary().parent.mkdir(exist_ok=False)
    shutil.copy2(Path("target/release") / binary().name, binary())
    (binary().parent / "identity.json").write_text(json.dumps({
        "source": os.environ["BUILD_SOURCEVERSION"], "run": os.environ["BUILD_BUILDID"],
        "digest": hashlib.sha256(binary().read_bytes()).hexdigest(),
    }), encoding="utf-8")


def prepare(case):
    identity = json.loads((binary().parent / "identity.json").read_text(encoding="utf-8"))
    require(identity["source"] == os.environ["BUILD_SOURCEVERSION"]
            and identity["run"] == os.environ["BUILD_BUILDID"]
            and identity["digest"] == hashlib.sha256(binary().read_bytes()).hexdigest())
    if os.name != "nt":
        binary().chmod(0o700)
    print("SV_IDENTITY:" + json.dumps({**identity,
          "job": os.environ["SYSTEM_JOBID"], "attempt": os.environ["SYSTEM_JOBATTEMPT"],
          "case": case, "agent": os.environ["AGENT_VERSION"],
          "image": os.environ.get("ImageOS") or os.environ.get("IMAGEOS"),
          "imageVersion": os.environ.get("ImageVersion") or os.environ.get("IMAGEVERSION"),
    }, sort_keys=True), flush=True)
    for index, assignment in enumerate(assignments(case)):
        # Values are synthetic; this file transports bytes to the documented helper.
        path = input_path(index)
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(assignment.value.encode("utf-8"))
    if case in ("size", "control"):
        for value in (b"x" * 16_385, "😀".encode() * 4096 + b"x", b"x\n", b"x$("):
            result = subprocess.run([str(binary()), "azure-pipelines:secret-variable", "Rejected"],
                                    input=value, capture_output=True, timeout=30)
            require(result.returncode == 1 and not result.stdout
                    and result.stderr.startswith(b"error: "))
        print("SV_REJECTIONS_OK", flush=True)
    print("SV_PREPARED", flush=True)


def env_bytes(key):
    if os.name == "nt":
        return os.environ[key].encode("utf-8", errors="strict")
    return os.environb[key.encode("ascii")]


def unmapped(case, index):
    assignment = assignments(case)[index]
    for key in (assignment.name.upper(), f"PUBLISH{index}_" + assignment.name.upper(),
                "FORWARDVALUE", "FORWARDREADONLY"):
        require(key not in os.environ)
    require(os.environ.get("CALLERSENTINEL") == SENTINEL)
    require("SHOUTX_INJECTED" not in os.environ)
    print(f"SV_UNMAPPED_{index}_OK", flush=True)


def consume(case, index, stream):
    assignment = assignments(case)[index]
    require(env_bytes("SV_MAPPED") == assignment.value.encode("utf-8"))
    require(os.environ.get("CALLERSENTINEL") == SENTINEL)
    require("SHOUTX_INJECTED" not in os.environ)
    target = sys.stdout.buffer if stream == "OUT" else sys.stderr.buffer
    for tag, payload in expected_blocks(case, index, stream, False):
        emit_block(target, tag, payload)
    target.write(f"SV_CONSUMED_{index}_{stream}_OK\n".encode())
    target.flush()


def calibrate(stream):
    target = sys.stdout.buffer if stream == "OUT" else sys.stderr.buffer
    for case in (*SAME_JOB, "output"):
        for index in range(len(assignments(case))):
            for tag, payload in expected_blocks(case, index, stream, False):
                emit_block(target, "CAL_" + tag, payload)
    print(f"SV_CALIBRATED_{stream}", flush=True)


def command(args, value):
    # Only public synthetic data enters this fixture. Never capture successful wire.
    result = subprocess.run([str(binary()), *args], input=value.encode(), timeout=30)
    require(result.returncode == 0)


def control(phase):
    if phase == "plain":
        command(["azure-pipelines:variable", "PlainValue"], CONTROL_PLAIN)
        print("SV_PLAIN_REGISTERED", flush=True)
    elif phase == "plain-check":
        require(env_bytes("PLAINVALUE") == CONTROL_PLAIN.encode())
        print("SV_PLAIN_BEGIN\n" + CONTROL_PLAIN + "\nSV_PLAIN_END", flush=True)
    elif phase == "wrong":
        command(["azure-pipelines:mask"], CONTROL_WRONG)
        print("SV_WRONG_REGISTERED", flush=True)
    elif phase == "omission-check":
        print("SV_OMISSION_BEGIN\n" + CONTROL_OMITTED + "\nSV_OMISSION_END", flush=True)
        print("SV_WRONG_BEGIN\n" + CONTROL_OMITTED + "\nSV_WRONG_END", flush=True)
    elif phase == "overwrite":
        command(["azure-pipelines:secret-variable", "Locked"], CONTROL_REPLACEMENT)
        print("SV_OVERWRITE_REQUESTED", flush=True)
    elif phase == "readonly-check":
        require(env_bytes("SV_MAPPED") == CONTROL_ORIGINAL.encode())
        print("SV_READONLY_UNCHANGED", flush=True)
    else:
        raise RuntimeError("unknown control phase")


def main():
    phase = sys.argv[1]
    case = os.environ["SHOUTX_SECRET_CASE"]
    require(case in ALL_JOBS)
    if phase == "package":
        package()
    elif phase == "prepare":
        prepare(case)
    elif phase == "unmapped":
        unmapped(case, int(sys.argv[2]))
    elif phase == "consume":
        consume(case, int(sys.argv[2]), sys.argv[3])
    elif phase == "calibrate":
        calibrate(sys.argv[2])
    elif phase == "control":
        control(sys.argv[2])
    else:
        raise RuntimeError("unknown phase")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Synthetic secret-variable fixture failed; values withheld")
