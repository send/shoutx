"""Synthetic-only hosted producer phases. Never capture successful mask wire."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from mask_cases import blocks, cases


def emit_block(stream, tag, lines):
    stream.write((tag + "_BEGIN\n" + "\n".join(lines) + "\n" + tag + "_END\n").encode())
    stream.flush()


def root():
    return Path(os.environ["AGENT_TEMPDIRECTORY"]) / "shoutx-mask-inputs"


def binary():
    suffix = ".exe" if os.name == "nt" else ""
    return Path(os.environ["PIPELINE_WORKSPACE"]) / "mask-binary" / ("shoutx" + suffix)


def prepare(case):
    identity = json.loads((binary().parent / "identity.json").read_text())
    if (identity["source"] != os.environ["BUILD_SOURCEVERSION"]
            or identity["run"] != os.environ["BUILD_BUILDID"]
            or identity["digest"] != hashlib.sha256(binary().read_bytes()).hexdigest()):
        raise RuntimeError("binary identity mismatch")
    if os.name != "nt":
        binary().chmod(0o700)
    print("SX_IDENTITY:" + json.dumps({
        "source": identity["source"], "run": identity["run"], "digest": identity["digest"],
        "job": os.environ["SYSTEM_JOBID"], "attempt": os.environ["SYSTEM_JOBATTEMPT"],
        "agent": os.environ["AGENT_VERSION"],
        "image": os.environ.get("ImageOS") or os.environ.get("IMAGEOS"),
        "imageVersion": os.environ.get("ImageVersion") or os.environ.get("IMAGEVERSION"),
        "case": case.name,
    }, sort_keys=True), flush=True)
    if case.each_line:
        # Unregistered, non-secret framing probe: retained literally for verifier.
        for name, stream in (("OUT", sys.stdout.buffer), ("ERR", sys.stderr.buffer)):
            emit_block(stream, "SX_FRAMING_" + name, ["AA\r\n\rBB\n\nCC", ""])
    if case.name == "lines_omission":
        for name in ("lines_pem", "lines_mixed", "lines_short"):
            for stream_name, tag, lines in blocks(cases()[name], False):
                stream = sys.stdout.buffer if stream_name == "OUT" else sys.stderr.buffer
                emit_block(stream, "CAL_" + name.upper() + "_" + tag, lines)
    if case.name == "lines_cap":
        for invalid in [b"x" * 1_048_577, b"x\n" * 1025,
                        b"x\n" * 1024 + b"\xff", b"x\n" * 1024 + b"\0"]:
            result = subprocess.run([str(binary()), "azure-pipelines:mask", "--each-line"],
                                    input=invalid, capture_output=True, timeout=30)
            if result.returncode != 1 or result.stdout or not result.stderr.startswith(b"error: "):
                raise RuntimeError("rejection probe failed")
        print("SX_REJECTIONS_OK", flush=True)
    root().mkdir(exist_ok=False)
    for index, value in enumerate(case.inputs):
        (root() / f"{index}.bin").write_bytes(value.encode())
    print("SX_PREPARED", flush=True)


def emit(case):
    if os.environ.get("SHOUTX_INJECTED"):
        raise RuntimeError("unexpected sentinel operation")
    print("SX_UNRELATED_VISIBLE", flush=True)
    for stream_name, tag, lines in blocks(case, False):
        stream = sys.stdout.buffer if stream_name == "OUT" else sys.stderr.buffer
        if tag.endswith("_LAYOUT"):
            lines = [case.layout]
        emit_block(stream, tag, lines)
    print("SX_EMISSION_COMPLETE", flush=True)


if __name__ == "__main__":
    try:
        case = cases()[os.environ["SHOUTX_MASK_CASE"]]
        if sys.argv[1] == "package":
            binary().parent.mkdir(exist_ok=False)
            shutil.copy2(Path("target/release") / binary().name, binary())
            (binary().parent / "identity.json").write_text(json.dumps({
                "source": os.environ["BUILD_SOURCEVERSION"], "run": os.environ["BUILD_BUILDID"],
                "digest": hashlib.sha256(binary().read_bytes()).hexdigest(),
            }), encoding="utf-8")
        elif sys.argv[1] == "prepare":
            prepare(case)
        elif sys.argv[1] == "emit":
            emit(case)
        else:
            raise RuntimeError("invalid phase")
    except Exception:
        sys.exit("Synthetic mask producer failed; values withheld")
